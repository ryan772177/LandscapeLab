"""sg_trial_place.py -- Shape Grammar trial, EDITOR half for arms A and C: one arm's 8 houses in a row on the rig.

    python scripts/sg_trial_place.py --arm A [--go]
    python scripts/sg_trial_place.py --arm C [--go]

research/town_kit/SHAPE_GRAMMAR_TRIAL.md. Pieces come from _verify/sg_trial/plans.json (scripts/sg_trial_plan.py),
placement follows town_kit_gallery.py exactly (the rig, recipes/town_kit.json probe block, the audited
scripts/payloads/town_kit_build_house.py, replace by label, ground trace). Labels SGTrial_<slot> are the SAME for
every arm, so placing arm C replaces arm A house for house and the camera framing is identical between arms.
Does NOT save (standing rule: the rig is a scratch stage; the trial writes nothing into a level on disk).
Stops on no result or two failures in a row (standing rule 6).
"""
import argparse
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402

REPO = bootstrap.REPO_ROOT
TRIAL = json.load(io.open(os.path.join(REPO, "recipes", "sg_trial.json"), encoding="utf-8"))


def specs_for(arm):
    plans = json.load(io.open(os.path.join(REPO, TRIAL["outputs"], "plans.json"), encoding="utf-8"))
    key = {"A": "arm_a", "C": "arm_c"}[arm]
    pieces_by = {r["index"]: r["pieces"] for r in plans[key]}
    rows = plans["houses"]
    pr = tkp._R["probe"]
    cx, cy = pr["camera_xy_cm"]
    cyaw = math.radians(pr["camera_yaw_deg"])
    fwd = (math.cos(cyaw), math.sin(cyaw))
    side = (-fwd[1], fwd[0])
    dist = float(TRIAL["rig"]["dist_m"]) * 100.0
    gap = float(TRIAL["rig"]["gap_m"]) * 100.0
    widths = [float(r["W_cm"]) for r in rows]
    total = sum(widths) + gap * (len(rows) - 1)
    out, at = [], -total / 2.0
    for slot, r in enumerate(rows):
        W, D = float(r["W_cm"]), float(r["D_cm"])
        off = at + W / 2.0
        at += W + gap
        x = cx + fwd[0] * dist + side[0] * off
        y = cy + fwd[1] * dist + side[1] * off
        courses = r["courses_a"] if arm == "A" else r["courses_c"]
        h = courses * tkp.COURSE_CM / 2.0
        if r["door_side"] != 0:
            raise SystemExit("REFUSE: house %d door_side %d -- the row faces the camera with side 0 (S)"
                             % (r["index"], r["door_side"]))
        out.append({"level": pr["level"], "label": "SGTrial_%02d" % slot, "tags": [pr["tag"]],
                    "loc_cm": [x, y, 0.0], "ground_trace": True, "ground_offset_cm": 0.0,
                    # the gallery's yaw: house local -Y (door side 0) faces the camera
                    "yaw_deg": pr["camera_yaw_deg"] + 90.0 - 180.0,
                    "box_center_cm": [0, 0, h], "box_extent_cm": [W / 2.0 + 100.0, D / 2.0 + 100.0, h],
                    "replace": True, "pieces": pieces_by[r["index"]]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", choices=("A", "C"), required=True)
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    specs = specs_for(a.arm)
    for s in specs:
        print("%s  %3d pieces at (%.0f, %.0f)" % (s["label"], len(s["pieces"]), s["loc_cm"][0], s["loc_cm"][1]))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    tpl = io.open(os.path.join(REPO, "scripts", "payloads", "town_kit_build_house.py"), encoding="utf-8").read()
    bad = streak = 0
    for s in specs:
        code, out, raw = ue_exec.run(tpl.replace("__SPEC__", json.dumps(s)), marker="__LL__", timeout=25,
                                     stage_name="sg_trial_place")
        if isinstance(out, dict) and out.get("ok"):
            streak = 0
            print("%s ok" % s["label"])
            continue
        bad += 1
        streak += 1
        print("%s FAIL code %s: %s" % (s["label"], code, (out or {}).get("error") if isinstance(out, dict)
                                       else (raw or "")[-600:]))
        if not isinstance(out, dict) or streak >= 2:
            print("STOP")
            break
    return 0 if not bad else 4


if __name__ == "__main__":
    sys.exit(main())
