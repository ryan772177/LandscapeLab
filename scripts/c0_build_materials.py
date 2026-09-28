"""Host side of the C0 material build: substitute the role table, run, report.

The payload is a FILE and the role table is injected as a Python literal. Two
recorded traps decide that shape:

  * a remote-exec payload must never contain the string ".py" -- ExecuteFile
    runs FindFirst over the whole command and turns the script into a path
    (logged 2026-08-01, cost two hours).
  * PowerShell strips double quotes out of a --set value, so a JSON blob
    handed through the shell arrives as a Python syntax error. Writing the
    substituted payload to a file from Python has neither failure mode.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# UE renames Blender's dotted material names. Exactly one differs on the C0
# donor: UE `Material_001_ncl_1` is Blender `Material.001`. The other nine
# match exactly. Explicit, not a rule -- a rule that guesses names is how the
# wrong texture lands on the wrong face.
SLOT_ALIAS = {"Material_001_ncl_1": "Material.001"}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="recipes/c0_materials.json")
    ap.add_argument("--derived", default="refs/derived_v1")
    ap.add_argument("--dest", default="/Game/Scratch/C0House")
    ap.add_argument("--master-name", default="M_C0_House")
    ap.add_argument("--tex-prefix", default="T_C0_")
    ap.add_argument("--mi-prefix", default="MI_C0_")
    ap.add_argument("--uv-density",
                    help="JSON from church_uv_density.py. With it, each role "
                         "gets Tiling = metres_per_uv / tile_m -- DERIVED, "
                         "never typed. Without it, Tiling stays at the "
                         "master default and the role table must not declare "
                         "tile_m, because declaring an intent that is then "
                         "silently ignored is worse than not declaring it.")
    a = ap.parse_args()

    man_path = os.path.join(REPO, a.manifest)
    with open(man_path, encoding="utf-8") as f:
        man = json.load(f)

    roles = {}
    missing = []
    spread = []
    dens = None
    if a.uv_density:
        with open(os.path.join(REPO, a.uv_density), encoding="utf-8") as fh:
            dens = json.load(fh)
    for role, spec in man["roles"].items():
        row = {"A": spec["albedo"],
               "N": a.derived + "/" + role + "_N.png",
               "R": a.derived + "/" + role + "_R.png"}
        for k, rel in row.items():
            if not os.path.exists(os.path.join(REPO, rel)):
                missing.append(role + "/" + k + " -> " + rel)
        # TILING: derived from the MEASURED uv density and the DECLARED
        # real-world tile size. Refuses the half-configured case rather than
        # quietly rendering at the unwrap's arbitrary scale.
        if dens is not None and "tile_m" in spec:
            # a role owns one slot (`slot`) or many (`slots`)
            names = spec.get("slots") or ([spec["slot"]]
                                          if spec.get("slot") else [])
            got = []
            for nm in names:
                key = SLOT_ALIAS.get(nm, nm)
                e = dens.get("slots", {}).get(key)
                if e and e.get("metres_per_uv_median") is not None:
                    got.append((nm, float(e["metres_per_uv_median"])))
            if not got:
                missing.append(role + "/tiling -> no density for slot(s) "
                               + str(names))
            else:
                vals = [v for _, v in got]
                med = sorted(vals)[len(vals) // 2]
                row["tiling"] = round(med / float(spec["tile_m"]), 4)
                # ⚠ ONE INSTANCE, ONE Tiling. If a role's slots disagree on
                # density, no single value serves them all -- say so, loudly,
                # rather than pick the median and call it derived.
                if len(vals) > 1 and max(vals) / max(1e-9, min(vals)) > 1.25:
                    spread.append(
                        "%s: %d slots span %.4f-%.4f m/uv (%.1fx). One "
                        "instance carries ONE Tiling, so %.4f is a "
                        "COMPROMISE, not a derivation: %s"
                        % (role, len(got), min(vals), max(vals),
                           max(vals) / min(vals), row["tiling"],
                           ", ".join("%s=%.3f" % g for g in got)))
        elif "tile_m" in spec:
            missing.append(role + "/tiling -> tile_m declared but no "
                                  "--uv-density given; refusing to ignore it")
        roles[role] = row
    if missing:
        print("REFUSING -- source maps absent, so the import would create")
        print("assets with no content and report success:")
        for m in missing:
            print("    " + m)
        return 2

    tmpl_path = os.path.join(REPO, "scripts",
                             "c0_build_materials_payload.txt")
    with open(tmpl_path, encoding="utf-8") as f:
        tmpl = f.read()
    assert "ROLES_JSON" in tmpl, "payload lost its substitution point"
    src = tmpl.replace("ROLES_JSON", repr(roles))
    # The four constants travel the same route as ROLES_JSON -- written into
    # the payload FILE from Python, never through a shell. PowerShell strips
    # double quotes out of a --set value, so a path handed through the shell
    # arrives as a Python syntax error (recorded at the top of this file).
    for _tok, _val in (("__DEST__", a.dest),
                       ("__MASTER_NAME__", a.master_name),
                       ("__TEX_PREFIX__", a.tex_prefix),
                       ("__MI_PREFIX__", a.mi_prefix)):
        assert _tok in src, "payload lost " + _tok
        src = src.replace(_tok, _val)

    out_path = os.path.join(
        REPO, "LandscapeLab", "Saved",
        "build_materials_gen_%s.txt" % a.master_name)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(src)

    if spread:
        print("")
        print("⚠ UV DENSITY DISAGREES ACROSS SLOTS OF ONE ROLE:")
        for s in spread:
            print("    " + s)
        print("")
    print("running the build for %d roles, %d textures"
          % (len(roles), len(roles) * 3))
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         out_path, "--timeout", "25"],
        capture_output=True, text=True)
    # ue_exec re-emits the decoded marker payload as indented JSON on success
    # (ue_exec.py:339, `print(json.dumps(d, indent=2))` in main), so there is
    # no `__LL__` line left to scan for. Grepping for one found nothing and
    # reported "could not look" over a run that had completely succeeded --
    # a wrapper mis-parse that reads exactly like an editor failure. Take the
    # outermost JSON object instead. (ue_exec.py:155 is the RAW dump on the
    # decode-FAILURE path -- braces there could fool find/rfind, but only
    # when the payload was already unparseable.)
    text = p.stdout or ""
    i, j = text.find("{"), text.rfind("}")
    blob = text[i:j + 1] if 0 <= i < j else None
    if blob is None:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print((p.stdout or "")[-1500:])
        print((p.stderr or "")[-800:])
        return 5

    res = json.loads(blob)
    if res.get("error"):
        print("BUILD FAILED: " + str(res["error"])[:600])
    bad_t = [t for t in res["textures"] if t["error"] or not t["imported"]]
    print("")
    # "imported" means loaded AND its settings read back clean -- a texture
    # that loaded but failed a settings gate (error set after imported=True)
    # counts as failed only, not in both tallies.
    print("  textures  %d imported, %d failed"
          % (sum(1 for t in res["textures"]
                 if t["imported"] and not t["error"]), len(bad_t)))
    for t in bad_t:
        print("    !! %-16s %s  %s" % (t["role"], t["kind"], t["error"]))
    if res.get("master"):
        m = res["master"]
        print("  master    %s  expressions %s -> %s"
              % (m.get("path"), m.get("expressions_before"),
                 m.get("expressions_after")))
        for k, v in sorted((m.get("sampler_types") or {}).items()):
            print("            %-10s %s" % (k, v))
    ce = res.get("compile_errors")
    if ce is None:
        print("  compile   NOT CAPTURED -- that is not a pass")
    elif ce:
        print("  compile   %d ERROR(S):" % len(ce))
        for e in ce[:8]:
            print("            " + e[:150])
    else:
        print("  compile   clean, 0 errors")
    if res.get("instances"):
        print("  instances")
        for i in res["instances"]:
            print("    %-14s set %s  readback %s  %s"
                  % (i["role"],
                     "".join("Y" if i["set"][k] else "n"
                             for k in ("BaseColor", "Roughness", "Normal")),
                     "".join("Y" if i["readback"][k] else "n"
                             for k in ("BaseColor", "Roughness", "Normal")),
                     i["error"] or "ok"))
    print("")
    ok = bool(res.get("ok"))
    print("BUILD %s" % ("OK" if ok else "!! NOT OK"))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
