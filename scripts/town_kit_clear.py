"""town_kit_clear.py -- driver for scripts/payloads/town_kit_clear_primitives.py (2026-10-06 kit town).

    python scripts/town_kit_clear.py            # dry run: census of the primitive town by kind, nothing destroyed
    python scripts/town_kit_clear.py --commit   # destroy LandscapeLab.City buildings + roofs (refuses unless == expect)

expect = 2 x the building count of the PRIMITIVE plan that was placed (303 buildings + 303 roofs = 606, from
git: city/alpine_basin_town_plan.json at the commit before the kit plan was adopted, 5f544a9c^). Level from the
kit manifest. Does NOT save.
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
PRIMITIVE_PLAN_REV = "5f544a9c^"


def expected():
    raw = subprocess.run(["git", "show", PRIMITIVE_PLAN_REV + ":city/alpine_basin_town_plan.json"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    p = json.loads(raw)
    nb = sum(1 for b in p["buildings"] if b["kind"] == "building")
    nr = len(p.get("roofs") or [])
    return nb + nr, nb, nr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--tag", default=None, help="2026-10-10 re-layout: clear actors with this tag ...")
    ap.add_argument("--kinds", default=None, help="... and one of these comma-separated kind tags ('' = any; "
                                                  "REQUIRED non-empty for tag LandscapeLab.City)")
    ap.add_argument("--expect", type=int, default=None,
                    help="REQUIRED with --tag: the exact count to clear, from a source INDEPENDENT of the world "
                         "census (kit houses: the kit manifest count; City streets: the placed plan's street count)")
    ap.add_argument("--expect-from-tag", action="store_true",
                    help="take --expect from the pre-organic git tag (TownKit: its manifest house count; City "
                         "streets: its plan street count) -- one declaration instead of a hand-typed number")
    a = ap.parse_args(argv)
    if a.expect_from_tag:
        # design review 2026-10-10 (recommended): the counts the teardown must match come from the tag that
        # records the town in the level, validated as the lattice town by town_kit_load_region.pre_organic
        if not a.tag or a.expect is not None:
            print("REFUSE: --expect-from-tag needs --tag and excludes --expect")
            return 2
        if not ((a.tag == "LandscapeLab.TownKit" and not a.kinds) or
                (a.tag == "LandscapeLab.City" and a.kinds == "streets")):
            print("REFUSE: --expect-from-tag knows TownKit (no kinds) and City --kinds streets only")
            return 2
        import town_kit_load_region
        pre_plan, pre_man = town_kit_load_region.pre_organic()
        a.expect = len(pre_man["houses"]) if a.tag == "LandscapeLab.TownKit" else len(pre_plan["streets"])
        print("expect %d from tag %s" % (a.expect, town_kit_load_region.PRE_ORGANIC_REV))
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    # world-tools audit 2026-10-10 F1: --kinds/--expect were silently ignored without --tag
    if not a.tag and (a.kinds is not None or a.expect is not None):
        print("REFUSE: --kinds/--expect need --tag (without it this tool clears the PRIMITIVE buildings+roofs)")
        return 2
    if a.tag:
        if a.expect is None:
            print("REFUSE: --tag needs --expect (an exact count from an independent source)")
            return 2
        exp = a.expect
        kinds = [k for k in (a.kinds or "").split(",") if k] or None
        # F2: no kinds under the City tag would also take the landmark and spire, guarded only by a count
        if a.tag == "LandscapeLab.City" and kinds is None:
            print("REFUSE: tag LandscapeLab.City needs --kinds (any-kind would include the landmark and spire)")
            return 2
        cfg = {"level": man["level_path"], "expect": exp, "commit": a.commit, "tag": a.tag, "kinds": kinds}
        print("tag %s kinds %s: expect %d; level %s; commit %s" % (a.tag, kinds, exp, man["level_path"], a.commit))
    else:
        exp, nb, nr = expected()
        print("primitive plan @%s: %d buildings + %d roofs = expect %d; level %s; commit %s"
              % (PRIMITIVE_PLAN_REV, nb, nr, exp, man["level_path"], a.commit))
        cfg = {"level": man["level_path"], "expect": exp, "commit": a.commit}
    import ue_exec
    tpl = io.open(os.path.join(REPO, "scripts", "payloads", "town_kit_clear_primitives.py"), encoding="utf-8").read()
    code, out, raw = ue_exec.run(tpl.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                 stage_name="town_kit_clear")
    if not isinstance(out, dict):
        print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
        return 4
    print(json.dumps({k: v for k, v in out.items() if k != "traceback"}, indent=1))
    if out.get("traceback"):
        print(out["traceback"][-1500:])
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
