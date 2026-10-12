"""town_kit_load_region.py -- make the whole town resident in the editor (World Partition region load).

    python scripts/town_kit_load_region.py --dry-run
    python scripts/town_kit_load_region.py --go

Box = union of (a) the primitive town that is in the level now (city/alpine_basin_town_plan.json at
5f544a9c^, the plan before the kit plan was adopted -- the teardown census must see every one of its actors)
and (b) the kit manifest's houses, (c) the plan's streets and, for an organic plan, (d) the pre-organic tag's
lattice streets and houses (2026-10-10), grown by MARGIN_M. Calls LandscapeLabTools.load_world_partition_region_box.
Before step 4 of research/town_kit/DESIGN.md (teardown) and the foliage clearance: get_all_level_actors and the
foliage actor walk only see LOADED actors, so an unloaded cell would make both report fewer and pass.
"""
import argparse
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
MARGIN_M = 50.0
PRIMITIVE_PLAN_REV = "5f544a9c^"
PRE_ORGANIC_REV = "pre-organic-town-20261010"     # git tag: the lattice kit town still in the level


def _git_json(rev, rel):
    r = subprocess.run(["git", "show", "%s:%s" % (rev, rel)], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("REFUSE: git show %s:%s failed (%s) -- is the tag created?" % (rev, rel, r.stderr.strip()))
    return json.loads(r.stdout)


def pre_organic():
    """(plan, manifest) of the lattice kit town at the PRE_ORGANIC_REV tag. REFUSES when the tag is missing (git
    raises) AND when its content is not the lattice town (delta audit 2026-10-10 F-B: a tag misplaced on an organic
    commit would duplicate the current files and silently shrink every box built from it)."""
    pre_plan = _git_json(PRE_ORGANIC_REV, "city/alpine_basin_town_plan.json")
    pre_man = _git_json(PRE_ORGANIC_REV, "city/alpine_basin_town_kit_manifest.json")
    if pre_plan.get("layout", "lattice") != "lattice" or not any(s.get("kind") == "ring" for s in pre_plan["streets"]):
        raise SystemExit("REFUSE: tag %s does not hold the lattice town (layout %r)"
                         % (PRE_ORGANIC_REV, pre_plan.get("layout")))
    return pre_plan, pre_man


def town_points(houses_and_streets_only=False):
    """THE ONE DECLARATION of where town actors stand, in the level now or about to be: [(x, y)] cm. Used by the
    region load (teardown census) AND by town_kit_hlod_cells (which cells to rebuild -- design review 2026-10-10 C1:
    selecting by NEW houses only would leave baked proxies of the deleted lattice in every unrebuilt cell)."""
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    plan = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_plan.json"), encoding="utf-8"))
    pts = []
    if not houses_and_streets_only:
        old = _git_json(PRIMITIVE_PLAN_REV, "city/alpine_basin_town_plan.json")
        pts += [b["loc_cm"][:2] for b in old["buildings"]] + [r["loc_cm"][:2] for r in (old.get("roofs") or [])]
    pts += [h["loc_cm"][:2] for h in man["houses"]]
    # 2026-10-10 organic re-layout: the current plan's streets, and -- once the organic plan is adopted -- the
    # PRE-ORGANIC plan's 838 lattice streets and manifest's 385 houses, which the teardown must see (an unloaded
    # cell would make the census report fewer). Before the tag exists those ARE the current files.
    pts += [s["loc_cm"][:2] for s in plan["streets"]]
    if plan.get("layout") == "organic":
        pre_plan, pre_man = pre_organic()
        pts += [s["loc_cm"][:2] for s in pre_plan["streets"]] + [h["loc_cm"][:2] for h in pre_man["houses"]]
    return pts, man["level_path"]


def town_box():
    pts, level = town_points()
    m = MARGIN_M * 100.0 + 1500.0      # + the largest half-diagonal of any footprint (15 m plan max)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs) - m, min(ys) - m, 0.0], [max(xs) + m, max(ys) + m, 0.0], level


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    lo, hi, level = town_box()
    print("town box X %.0f..%.0f  Y %.0f..%.0f cm (%.0f x %.0f m) in %s"
          % (lo[0], hi[0], lo[1], hi[1], (hi[0] - lo[0]) / 100, (hi[1] - lo[1]) / 100, level))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    payload = ("import json, unreal as u\n"
               "w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()\n"
               "lvl = w.get_path_name().split('.')[0]\n"
               "out = {'level': lvl}\n"
               "if lvl != %r:\n"
               "    out.update(ok=False, error='open level is %%s' %% lvl)\n"
               "else:\n"
               "    ok, err = u.LandscapeLabTools.load_world_partition_region_box(u.Vector(*%r), u.Vector(*%r))\n"
               "    out.update(ok=bool(ok), error=str(err) or None)\n"
               "print('__LL__' + json.dumps(out))\n") % (level, lo, hi)
    code, out, raw = ue_exec.run(payload, marker="__LL__", timeout=25, stage_name="town_kit_load_region")
    print(out if isinstance(out, dict) else "COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
    return 0 if isinstance(out, dict) and out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
