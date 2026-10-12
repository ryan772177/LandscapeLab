"""town_kit_place_streets.py -- driver for scripts/payloads/town_kit_place_streets.py (2026-10-10).

    python scripts/town_kit_place_streets.py            # dry run: trace a sample, report drift, spawn nothing
    python scripts/town_kit_place_streets.py --commit   # place every plan street (refuses if City streets exist)

Plan: city/alpine_basin_town_plan.json (must be the adopted organic plan -- refuses a lattice plan, so this cannot
re-place the old network by accident). Level from the kit manifest. Does NOT save.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args(argv)
    plan_p = os.path.join(REPO, "city", "alpine_basin_town_plan.json")
    plan = json.load(io.open(plan_p, encoding="utf-8"))
    if plan.get("layout") != "organic":
        print("REFUSE: the plan's layout is %r, not organic" % plan.get("layout"))
        return 4
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    import ue_exec
    tpl = io.open(os.path.join(REPO, "scripts", "payloads", "town_kit_place_streets.py"), encoding="utf-8").read()
    cfg = {"level": man["level_path"], "plan": plan_p.replace("\\", "/"), "commit": a.commit}
    code, out, raw = ue_exec.run(tpl.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                 stage_name="town_kit_place_streets")
    if not isinstance(out, dict):
        print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
        return 4
    print(json.dumps({k: v for k, v in out.items() if k != "traceback"}, indent=1))
    if out.get("traceback"):
        print(out["traceback"][-1500:])
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
