"""town_kit_probe.py -- build ONE kit house on the rig level for the orientation / look probe (2026-10-06).

    python scripts/town_kit_probe.py --dry-run
    python scripts/town_kit_probe.py --go [--w 700 --d 550 --courses 2 --corner-yaw 0 --exterior -1]

Fast loop (STATE: prove on the rig, promote after): places a test house ~20 m in front of the rig hero camera
(82100, 82800, yaw 225) on traced landscape ground, label TownKit_Probe, tag LandscapeLab.TownKitProbe.
--corner-yaw / --exterior override the planner's UNCONFIRMED orientation constants so the probe can be
re-run until the stills are right; the confirmed values then go into town_kit_plan (and the recipe).
Replaces an earlier probe house of the same label. Does NOT save.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402

RIG_LEVEL = "/Game/LookDevMtn"
CAM = (82100.0, 82800.0)
CAM_YAW = 225.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--w", type=int, default=700)
    ap.add_argument("--d", type=int, default=550)
    ap.add_argument("--courses", type=int, default=2)
    ap.add_argument("--dist-m", type=float, default=20.0)
    ap.add_argument("--corner-yaw", type=float, default=None)
    ap.add_argument("--exterior", type=int, choices=(-1, 1), default=None)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.corner_yaw is not None:
        tkp.CORNER_YAW_OFFSET = a.corner_yaw
    if a.exterior is not None:
        tkp.EXTERIOR_SIGN = a.exterior
    pieces = tkp.plan_house(a.w, a.d, a.courses, door_side=0, seed=3)
    roof = tkp.plan_roof(a.w, a.d, a.courses)
    if roof is not None:
        pieces.append(roof)
        pieces.extend(tkp.plan_gables(a.w, a.d, a.courses, roof))
    print("roof: %s" % (roof and "%s yaw %.0f scale %s" % (roof["mesh"], roof["yaw"],
                                                         [round(v, 3) for v in roof["scale"]])))
    r = math.radians(CAM_YAW)
    x, y = CAM[0] + math.cos(r) * a.dist_m * 100, CAM[1] + math.sin(r) * a.dist_m * 100
    spec = {"level": RIG_LEVEL, "label": "TownKit_Probe", "tags": ["LandscapeLab.TownKitProbe"],
            "loc_cm": [x, y, 0.0], "ground_trace": True, "ground_offset_cm": 0.0,
            # door side (south, local -Y) faces the camera: house yaw = camera yaw + 90 - 180 ... set so the
            # house's local -Y points back toward the camera
            "yaw_deg": CAM_YAW + 90.0 - 180.0,
            "box_center_cm": [0, 0, a.courses * tkp.COURSE_CM / 2.0],
            "box_extent_cm": [a.w / 2.0, a.d / 2.0, a.courses * tkp.COURSE_CM / 2.0],
            "replace": True, "pieces": pieces}
    print("probe house %dx%d cm, %d courses, %d pieces at (%.0f, %.0f), exterior %d corner_yaw %.0f"
          % (a.w, a.d, a.courses, len(pieces), x, y, tkp.EXTERIOR_SIGN, tkp.CORNER_YAW_OFFSET))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    src = open(os.path.join(bootstrap.REPO_ROOT, "scripts", "payloads", "town_kit_build_house.py"),
               encoding="utf-8").read().replace("__SPEC__", json.dumps(spec))
    code, out, raw = ue_exec.run(src, marker="__LL__", timeout=25, stage_name="town_kit_probe")
    if not isinstance(out, dict):
        print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
        return 4
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
