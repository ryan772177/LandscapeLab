"""update_foliage_culls.py — re-derive culls and apply them WITHOUT
re-scattering.

RULED 2026-09-11 (R-RANGE at 512): derived culls clamp to
recipe.streaming.main_loading_range_cm — the detail band ends where the
world streams out. This tool re-derives every species' cull via
place_foliage._cull_cm_for (ONE deciding implementation, the
check_derived_culls sharing rule), rewrites the plan JSONs' cull_cm +
cull_derivation, and sets `cull_distance` on the placed FT_<species>
assets in /Game/Foliage — the exact property, interval shape (min =
0.75×max) and read-back the placement payload uses. Instances are NEVER
touched: density is out of scope by standing instruction.

The engine step is the R-LIGHTSAVE unit: apply → read back → save the
FT assets → commit (filesystem verdict). NOTE the read-back is IN MEMORY (off
the same FT object just set), so it proves the setter took, not that the value
PERSISTED; persistence is verified by a different instrument -- the FT .uasset
files must show as MODIFIED to git (they have existed since placement) -- not
by re-reading the saved value off disk.

  python scripts/update_foliage_culls.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402
from place_foliage import _cull_cm_for, _species_heights  # noqa: E402

REPO = bootstrap.REPO_ROOT
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
FOLIAGE = os.path.join(REPO, "foliage")
FT_DIR = "/Game/Foliage"

PAYLOAD = '''
import json as _json
import unreal as _u
TARGETS = __TARGETS__
_out = {"ok": False, "rows": [], "save": None}
try:
    _ass = _u.get_editor_subsystem(_u.EditorAssetSubsystem)
    _touched = []
    for _name, _cull_cm in TARGETS:
        _p = "__FT_DIR__/FT_" + _name
        _row = {"name": _name, "path": _p, "cull_cm": _cull_cm}
        _ft = (_u.EditorAssetLibrary.load_asset(_p)
               if _u.EditorAssetLibrary.does_asset_exist(_p) else None)
        if _ft is None:
            _row["error"] = "asset not found"
            _out["rows"].append(_row)
            continue
        _ft.set_editor_property(
            "cull_distance",
            _u.Int32Interval(int(_cull_cm * 0.75), int(_cull_cm)))
        _got = _ft.get_editor_property("cull_distance")
        _row["readback_min"] = int(_got.min)
        _row["readback_max"] = int(_got.max)
        _row["applied"] = int(_got.max) == int(_cull_cm)
        _touched.append(_ft)
        _out["rows"].append(_row)
    _save = {"marked": 0, "saved": None, "packages": []}
    for _a in _touched:
        try:
            _a.modify()
        except Exception:
            pass
        try:
            if _ass.set_dirty_flag(_a, True):
                _save["marked"] += 1
        except Exception:
            pass
        try:
            _n = str(_a.get_outermost().get_name())
            if _n not in _save["packages"]:
                _save["packages"].append(_n)
        except Exception:
            pass
    if _touched:
        _save["saved"] = bool(_ass.save_loaded_assets(_touched, False))
    _out["save"] = _save
    _out["ok"] = all(r.get("applied") for r in _out["rows"]
                     if "error" not in r) and not any(
        "error" in r for r in _out["rows"])
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-500:]
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=25.0)
    a = ap.parse_args(argv)

    with open(RECIPE, encoding="utf-8") as fh:
        recipe = json.load(fh)
    perception = recipe.get("perception")
    heights = _species_heights()
    rng_cm = int((recipe.get("streaming") or {}).get(
        "main_loading_range_cm") or 0)
    if not perception or not rng_cm:
        print("REFUSE: need both recipe.perception and "
              "recipe.streaming.main_loading_range_cm.")
        return 2
    species = (recipe.get("foliage") or {}).get("species")
    if not species:
        print("REFUSE: recipe has no foliage.species.")
        return 2

    changed, targets, skipped = [], [], []
    for sp in species:
        name = sp["name"]
        cull_cm, d = _cull_cm_for(sp, perception, heights, rng_cm)
        plan = os.path.join(FOLIAGE, "%s_%s.json"
                            % (recipe["biome_id"], name))
        if not os.path.isfile(plan):
            # Do not silently drop a species with no plan file -- report it.
            skipped.append(name)
            print("  SKIP %-14s no plan file (%s)"
                  % (name, os.path.basename(plan)))
            continue
        with open(plan, encoding="utf-8") as fh:
            doc = json.load(fh)
        old = int(doc.get("cull_cm") or 0)
        print("  %-14s %8.1f m -> %8.1f m  (%s)"
              % (name, old / 100.0, cull_cm / 100.0, d["applied"]))
        if old == cull_cm:
            continue
        changed.append((plan, doc, cull_cm, d))
        targets.append((name, cull_cm))

    if not changed:
        print("Nothing stale; every plan matches today's derivation.")
        return 0
    if a.dry_run:
        print("DRY RUN: %d plan(s) would change; nothing written."
              % len(changed))
        return 0

    # ENGINE FIRST, PLANS AFTER (audit 2026-09-11 F2): plans written
    # before a failed payload would leave check_derived_culls PASSING
    # over a stale engine -- the checker compares plan vs derivation and
    # both would be new. Nothing is written to disk until the engine has
    # applied, read back, and SAVED.
    payload = (PAYLOAD.replace("__TARGETS__", repr(targets))
               .replace("__FT_DIR__", FT_DIR))
    code, dta, raw = ue_exec.run(payload, marker="__LL__",
                                 timeout=a.timeout,
                                 stage_name="ll_update_culls", quiet=True)
    if dta is None or not dta.get("ok"):
        print("FAIL: FT update payload did not complete cleanly; NO plan "
              "was rewritten (engine-first ordering).")
        print(json.dumps(dta, indent=1)[:1500] if dta else (raw or "")[-800:])
        return 4
    for r in dta["rows"]:
        print("  FT_%(name)-12s -> max %(readback_max)s cm  applied=%(applied)s"
              % r)
    save = dta.get("save") or {}
    print("  save: marked %s saved %s" % (save.get("marked"),
                                          save.get("saved")))
    # AUDIT 2026-09-11 F1: the SAVE verdict is enforced, and from a
    # different instrument -- the FT files must show as MODIFIED to git,
    # not merely exist (they have existed since placement).
    if save.get("saved") is not True:
        print("FAIL: the editor did not report the FT save succeeding; "
              "no plan was rewritten.")
        return 5

    files = ["foliage/%s_%s.json" % (recipe["biome_id"], n)
             for n, _ in targets]
    ft_files = ["LandscapeLab/Content" + FT_DIR[len("/Game"):]
                + "/FT_%s.uasset" % n for n, _ in targets]
    st = subprocess.run(["git", "status", "--porcelain", "--"] + ft_files,
                        cwd=REPO, capture_output=True, text=True,
                        timeout=120)
    dirty_ft = {ln[3:].strip().replace("\\", "/")
                for ln in st.stdout.splitlines() if ln.strip()}
    not_written = [f for f in ft_files if f not in dirty_ft]
    if not_written:
        print("FAIL: the editor reported a save but git sees no change "
              "in: %s -- the culls live only in editor memory. No plan "
              "was rewritten." % not_written)
        return 5

    for plan, doc, cull_cm, d in changed:
        doc["cull_cm"] = cull_cm
        doc["cull_derivation"] = d
        with open(plan, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        print("  wrote %s" % os.path.relpath(plan, REPO))
    msg_path = None
    try:
        fd, msg_path = tempfile.mkstemp(prefix=".ll_culls_", suffix=".txt",
                                        dir=REPO)
        with os.fdopen(fd, "w") as fh:
            fh.write("update_foliage_culls: derived culls clamped to the "
                     "512 m streaming range\n\nRULED 2026-09-11 (R-RANGE). "
                     "Re-derived, not typed; instances untouched.\n")
            for n, c in targets:
                fh.write("  %s -> %d cm\n" % (n, c))
        r = subprocess.run(["git", "add", "--"] + files + ft_files,
                           cwd=REPO, capture_output=True, text=True,
                           timeout=120)
        if r.returncode != 0:
            print("FAIL: git add: " + (r.stderr or r.stdout).strip())
            return 5
        r = subprocess.run(["git", "commit", "-F", msg_path, "--"]
                           + files + ft_files, cwd=REPO,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print("FAIL: git commit: " + (r.stderr or r.stdout).strip())
            return 5
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=REPO, capture_output=True, text=True,
                           timeout=120)
        print("  committed: %s" % h.stdout.strip())
    finally:
        if msg_path and os.path.exists(msg_path):
            try:
                os.remove(msg_path)
            except OSError:
                pass
    print("Culls re-derived, applied, read back, SAVED and committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
