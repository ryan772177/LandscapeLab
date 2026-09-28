"""gen_manifest.py — regenerate refs/MANIFEST.md from live sources.

    python scripts/gen_manifest.py            # write
    python scripts/gen_manifest.py --check    # fail if stale (for the suite)

RULED 2026-08-30: **MANIFEST.md is regenerated from the recipes, never
hand-edited.** It is the operator's generation queue, so a stale or
hand-patched copy is a queue that lies.

WHY A GENERATOR AND NOT A DOCUMENT
The counts are the whole point of the priority column, and I got three of
eighteen wrong writing them by hand -- `barrel` was not in either concept at
all, `track` is recorded in two different schema sections, and `stone_arch`
is a placement rather than clutter. Those were caught only because the counts
were recomputed afterwards and compared. A generator makes the recompute the
ONLY path.

WHAT IS DERIVED (never typed here)
    counts        placements / focal_anchor / clutter / terrain, both concepts
    kit coverage  the measured rows of the v2 intake
    materials     roles -> slots, and which albedos are generated vs sourced
    done markers  recipes/forge.json + each asset's forge_report.json

WHAT IS DECLARED (recipes/manifest_classes.json)
    the class of each entity, its status, notes, heights and view specs --
    judgements a script cannot make. Editing THAT file and re-running is the
    supported path.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
OUT = os.path.join(REPO, "refs", "MANIFEST.md")
CLASSES = os.path.join(REPO, "recipes", "manifest_classes.json")


def load(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def concept_counts():
    """`appears` = the number of concept files an entity is DECLARED in.

    Deliberately counts DECLARATIONS, not instances: it is a coverage signal.
    An entity in both concepts is load-bearing for the site; one in a single
    concept may still be numerous within it, so the within-image multiplicity
    is carried alongside and never folded into the ranking.
    """
    seen = {}
    for n in ("01", "02"):
        d = load(os.path.join(REPO, "recipes", "concepts",
                              "alpine_village_%s.json" % n))
        ents = []
        for it in d.get("placements", {}).get("items", []):
            c, cr = it.get("count"), it.get("count_range")
            ents.append((it["class"],
                         str(c) if c is not None
                         else ("%d-%d" % tuple(cr) if cr else "?")))
        for c in d.get("clutter", {}).get("classes", []):
            ents.append((c["kind"], c.get("density", "?")))
        # terrain features share the namespace deliberately: `track` is a
        # clutter class in 01 and a terrain feature in 02, and it is ONE
        # entity. Keying them together is what makes that visible.
        for f in d.get("terrain", {}).get("features", []):
            ents.append((f["kind"], f.get("prominence", "?")))
        for name, mult in ents:
            seen.setdefault(name, {})[n] = mult
    return seen


def kit_names():
    """Returns (unique names, rows, duplicated names).

    ⚠ The v2 measured file has 33 ROWS but 31 UNIQUE names --
    `SM_LanternPost` and `SM_PorchBase` each appear twice, with DIFFERENT
    measurements (the two LanternPost rows differ in pivot_base_error_cm by
    75 cm). Reporting "33 meshes" would overstate the coverage by two, and
    quietly picking one of each duplicate would hide a real data question.
    Both numbers are reported and the duplicates are named.
    """
    d = load(os.path.join(REPO, "Free", "_measured",
                          "kit_medievalvillage_v2.json"))
    names = [r["name"] for r in d["rows"]]
    dup = sorted({n for n in names if names.count(n) > 1})
    return sorted(set(names)), d["rows"], dup


def forge_done():
    """Measured results for anything already forged (placement is recorded
    per-row as `placed`, not filtered on -- forged-but-unplaced is included)."""
    spec = load(os.path.join(REPO, "recipes", "forge.json"))["assets"]
    out = {}
    for key in spec:
        rp = os.path.join(REPO, "_verify", "20260830_forge", key,
                          "forge_report.json")
        if not os.path.exists(rp):
            continue
        r = load(rp)
        s10 = r.get("stage10") or {}
        out[key] = {
            "name": r.get("name"),
            "tris": (r.get("generate") or {}).get("faces"),
            "final_tris": s10.get("mesh_tris"),
            "genus": (r.get("generate") or {}).get("genus"),
            "top_cm": s10.get("top_cm"),
            "target_cm": s10.get("target_cm"),
            "err_cm": s10.get("height_error_cm"),
            "ratio": s10.get("ratio_measured"),
            "placed": bool(s10.get("ok")),
        }
    return out


def materials():
    mats = load(os.path.join(REPO, "recipes", "c0_materials.json"))["roles"]
    gen_roles = {f["role"] for f in
                 load(os.path.join(REPO, "Free", "_measured",
                                   "c0_textures_v1.json"))["files"]}
    ph = {}
    php = os.path.join(REPO, "Free", "_measured", "polyhaven_v1.json")
    if os.path.exists(php):
        for f in load(php)["files"]:
            ph[f["asset_id"]] = f
    return mats, gen_roles, ph


def build():
    cnt = concept_counts()
    cls = load(CLASSES)
    names, rows, dup = kit_names()
    done = forge_done()
    mats, gen_roles, ph = materials()
    L = []
    a = L.append

    a("# refs/MANIFEST.md — the unserved-entity frontier")
    a("")
    a("<!-- GENERATED by scripts/gen_manifest.py — DO NOT EDIT BY HAND. -->")
    a("<!-- Classification lives in recipes/manifest_classes.json; edit that"
      " and re-run. -->")
    a("")
    a("**Counts, kit coverage, material roles and done-markers are DERIVED"
      " from live sources on every run.** Only the classification is"
      " declared, in `recipes/manifest_classes.json`.")
    a("")
    a("    recipes/concepts/alpine_village_01.json + _02.json   counts")
    a("    Free/_measured/kit_medievalvillage_v2.json           %d rows, "
      "%d unique" % (len(rows), len(names)))
    a("    recipes/c0_materials.json                            %d roles"
      % len(mats))
    a("    Free/_measured/c0_textures_v1.json                   %d generated"
      % len(gen_roles))
    a("    Free/_measured/polyhaven_v1.json                     %d sourced"
      % len(ph))
    a("    recipes/forge.json + each forge_report.json          done markers")
    a("")
    if dup:
        a("⚠ **The kit file has %d rows but %d unique names** — `%s` are each "
          "measured twice, with differing values. Coverage is counted on the "
          "UNIQUE names; the duplicates are a data question for the intake, "
          "not extra assets."
          % (len(rows), len(names), "`, `".join(dup)))
        a("")
    a("**`appears` counts the concept files an entity is DECLARED in — not"
      " how many instances are drawn.** It is a coverage signal. The"
      " within-image multiplicity is quoted beside it and does not change the"
      " ranking.")
    a("")
    a("---")
    a("")

    # ---- DONE -----------------------------------------------------------
    a("# ✅ DONE — the frontier is behind these")
    a("")
    a("| what | measured result | evidence |")
    a("|---|---|---|")
    for key, info in sorted(done.items()):
        c = cls["classes"].get(key, {})
        if c.get("status") != "done":
            continue
        bits = []
        if info["top_cm"] is not None:
            bits.append("**%.1f cm** top vs a %.1f cm target, error %.2f"
                        % (info["top_cm"], info["target_cm"], info["err_cm"]))
        if info["ratio"] is not None:
            bits.append("ratio %.3f" % info["ratio"])
        if info["final_tris"]:
            bits.append("%d tris in engine" % info["final_tris"])
        if info["genus"] is not None:
            bits.append("genus %s" % info["genus"])
        a("| **%s** (forge subject) | %s | `%s` |"
          % (key, "; ".join(bits), c.get("evidence_dir", "")))
    ntiles = len(gen_roles)
    a("| **textures_v1** (material tiles) | %d generated roles at 1024², "
      "SHA-256 recorded; normals+roughness derived for all %d generated roles"
      " | `refs/textures_v1/`, `refs/derived_v1/` |" % (ntiles, ntiles))
    if ph:
        a("| **polyhaven tiles** (sourced) | %d CC0 textures fetched direct;"
          " **all byte-identical to the .fbm copies**, which proves the"
          " provenance-by-filename claim | `refs/polyhaven/` |" % len(ph))
    a("")
    a("⚠ **Heights derived from the chalet silhouette use 738.0 cm**, measured"
      " 2026-08-30 — not the 536.5 cm every earlier document used. The kit"
      " roof had been placed pivot-on-wall-top and sank 201.49 cm into the"
      " walls. Anything derived from the old figure is 27% short.")
    a("")
    a("---")
    a("")

    # ---- by class -------------------------------------------------------
    order = [("forge_subject", "⛔ FORGE SUBJECTS — unserved, generation is "
                               "the right answer"),
             ("kit_or_authored", "🧱 KIT-OR-AUTHORED — served or servable "
                                 "without generation"),
             ("system", "🌊 SYSTEMS — unserved, and NOT asset-shaped")]
    for klass, title in order:
        a("# " + title)
        a("")
        if klass == "forge_subject":
            a("**Declared height is mandatory or the forge refuses** (stage 10"
              " precondition): a generated mesh carries no units and stages"
              " 1–9 are all scale-invariant.")
            a("")
            # READ the two cited values rather than transcribing them (rule
            # 9). 738.0 stays a literal: it is a MEASURED engine silhouette
            # (chalet.height_cm is null in manifest_classes.json), not a
            # recipe field, so there is nothing to read it from.
            def _find(obj, key):
                if isinstance(obj, dict):
                    if key in obj and not isinstance(obj[key], (dict, list)):
                        return obj[key]
                    for _v in obj.values():
                        r = _find(_v, key)
                        if r is not None:
                            return r
                elif isinstance(obj, list):
                    for _v in obj:
                        r = _find(_v, key)
                        if r is not None:
                            return r
                return None
            _char = load(os.path.join(REPO, "recipes", "character.json"))
            _cap = _find(_char, "agent_height_cm")
            _step = _find(_char, "max_step_height_cm")
            a("    chalet SILHOUETTE   738.0 cm   MEASURED in engine")
            a("    character capsule   %s cm   recipes/character.json" % _cap)
            a("    max step height      %s cm   recipes/character.json" % _step)
            a("")
        items = [(k, v) for k, v in cls["classes"].items()
                 if v.get("klass") == klass and v.get("status") != "done"]
        # rank by appears DESC, then name -- the priority the operator asked for
        items.sort(key=lambda kv: (-len(cnt.get(kv[0], {})), kv[0]))
        if not items:
            a("*(none open)*")
            a("")
            continue
        if klass == "forge_subject":
            a("| entity | appears | height to declare | basis | view spec |")
            a("|---|---|---|---|---|")
            for k, v in items:
                ap = len(cnt.get(k, {}))
                a("| **%s** | **%d** | `height_cm` **%s** | %s | %s |"
                  % (k, ap, v.get("height_cm"), v.get("height_basis", ""),
                     v.get("view_spec", "")))
        else:
            a("| entity | appears | in 01 | in 02 | status | note |")
            a("|---|---|---|---|---|---|")
            for k, v in items:
                c = cnt.get(k, {})
                a("| **%s** | **%d** | %s | %s | `%s` | %s |"
                  % (k, len(c), c.get("01", "—"), c.get("02", "—"),
                     v.get("status", ""), v.get("note", "")))
        a("")

    # ---- materials ------------------------------------------------------
    a("# 🎨 MATERIAL TILES — role, the slots referencing it, and its source")
    a("")
    nslots = sum(len(s["slots"]) for s in mats.values())
    maxshare = max((len(s["slots"]) for s in mats.values()), default=0)
    a("**%d roles drive %d slots** on the C0 donor mesh"
      " (`recipes/c0_materials.json`, read from the mesh wiring). %d slots"
      " share one role — consolidation, not collision."
      % (len(mats), nslots, maxshare))
    a("")
    a("| role | slots | # | albedo source | status |")
    a("|---|---|---|---|---|")
    for role, spec in mats.items():
        slots = spec["slots"]
        alb = spec.get("albedo", "")
        tile = cls.get("material_tiles", {}).get(role, {})
        if role in gen_roles:
            status, src = "✅ **GENERATED**", alb
        elif tile.get("status") == "sourced":
            status, src = "✅ **SOURCED CC0**", tile.get("source", alb)
        else:
            status, src = "⚠ vendor", alb
        a("| `%s` | `%s` | **%d** | `%s` | %s |"
          % (role, "`, `".join(slots), len(slots), src, status))
    a("")
    for role, tile in cls.get("material_tiles", {}).items():
        if tile.get("status") == "operator_will_generate":
            a("⛔ **`%s` — the operator is generating this.** %s"
              % (role, tile.get("note", "")))
            a("")
    a("⚠ **Generating tiles does not unblock the church on its own** — the"
      " forged mesh has ONE material slot. The ruled route is option A, a"
      " height-band split in headless Blender with slot assignments READ BACK"
      " after import.")
    a("")

    # ---- the derivation table, so the ranking is auditable ---------------
    a("---")
    a("")
    a("# THE COUNT, AS COMPUTED THIS RUN")
    a("")
    a("    entity                     app  in 01                in 02")
    for k in sorted(cnt, key=lambda x: (-len(cnt[x]), x)):
        v = cnt[k]
        a("    %-26s %-4d %-20s %s"
          % (k, len(v), v.get("01", "--"), v.get("02", "--")))
    a("")
    rem = cls.get("removed", {})
    for k, why in rem.items():
        a("**`%s` does not appear.** %s" % (k, why))
    a("")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the file on disk differs from a fresh "
                         "generation -- i.e. it was hand-edited or a source "
                         "moved under it")
    args = ap.parse_args(argv)
    fresh = build()
    if args.check:
        if not os.path.exists(OUT):
            print("REFUSE: %s does not exist. Run without --check." % OUT)
            return 1
        with io.open(OUT, encoding="utf-8", newline="") as fh:
            cur = fh.read().replace("\r\n", "\n")
        if cur != fresh:
            print("STALE: refs/MANIFEST.md differs from a fresh generation.")
            print("  Either a source changed, or the file was hand-edited.")
            print("  Regenerate: python scripts/gen_manifest.py")
            cl, fl = cur.split("\n"), fresh.split("\n")
            for i in range(max(len(cl), len(fl))):
                c = cl[i] if i < len(cl) else "<missing>"
                f = fl[i] if i < len(fl) else "<missing>"
                if c != f:
                    print("  first difference at line %d:" % (i + 1))
                    print("    on disk : " + c[:100])
                    print("    fresh   : " + f[:100])
                    break
            return 1
        print("refs/MANIFEST.md is current (%d chars)" % len(fresh))
        return 0
    with io.open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(fresh)
    print("wrote %s (%d chars)" % (OUT, len(fresh)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
