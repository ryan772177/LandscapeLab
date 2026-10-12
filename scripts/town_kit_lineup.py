"""town_kit_lineup.py -- every wall and door module in one row on the rig, to SEE which carry windows.

    python scripts/town_kit_lineup.py --dry-run
    python scripts/town_kit_lineup.py --go

One probe actor (label TownKit_Lineup, the recipe's probe tag) probe.lineup_dist_m in front of the rig hero
camera, modules side by side along local +X with a probe.lineup_gap_cm gap, visible face (local +Y,
EXTERIOR_SIGN +1 only) toward the camera. Replaces an earlier lineup. Does NOT save. Module list = the planner's
own tables (town_kit_plan WALLS, GROUND_100, DOORS; the corner is an L and is not in the row).
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402


def modules():
    out = []
    for w in sorted(tkp.WALLS):
        out += [(m, w) for m in tkp.WALLS[w]]
    out.append((tkp.GROUND_100, 100))
    out += [(tkp.DOORS[w], w) for w in sorted(tkp.DOORS)]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    pr = tkp._R["probe"]
    if tkp.EXTERIOR_SIGN != 1:
        # a yaw-180 row would need pivots at x + w (audit F8); the confirmed sign is +1, so refuse instead
        raise SystemExit("REFUSE: lineup is written for exterior_sign +1")
    mods = modules()
    gap = float(pr["lineup_gap_cm"])
    total = sum(w for _m, w in mods) + gap * (len(mods) - 1)
    pieces, x = [], -total / 2.0
    for m, w in mods:
        # yaw 0 + EXTERIOR_SIGN +1: visible face local +Y. The house yaw below turns local +Y toward the camera.
        pieces.append({"mesh": m, "x": x, "y": 0.0, "z": 0.0, "yaw": 0.0, "role": "wall"})
        print("%-36s %4d cm at x %.0f" % (m, w, x))
        x += w + gap
    cx, cy = pr["camera_xy_cm"]
    r = math.radians(pr["camera_yaw_deg"])
    # 10 m out (recipe): the probe house stands at 20 m on the same line (lineup01 rendered them overlapping)
    d = float(pr["lineup_dist_m"]) * 100.0
    lx, ly = cx + math.cos(r) * d, cy + math.sin(r) * d
    # local +Y must point back at the camera: +Y = (-sin(yaw), cos(yaw)) = -(cos r, sin r) => yaw = r_deg + 90
    spec = {"level": pr["level"], "label": "TownKit_Lineup", "tags": [pr["tag"]],
            "loc_cm": [lx, ly, 0.0], "ground_trace": True, "ground_offset_cm": 0.0,
            "yaw_deg": pr["camera_yaw_deg"] + 90.0,
            "box_center_cm": [0, 0, 100], "box_extent_cm": [total / 2.0, 50, 100],
            "replace": True, "pieces": pieces}
    print("%d modules, %.0f cm row at (%.0f, %.0f)" % (len(mods), total, lx, ly))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    src = open(os.path.join(bootstrap.REPO_ROOT, "scripts", "payloads", "town_kit_build_house.py"),
               encoding="utf-8").read().replace("__SPEC__", json.dumps(spec))
    code, out, raw = ue_exec.run(src, marker="__LL__", timeout=25, stage_name="town_kit_lineup")
    if not isinstance(out, dict):
        print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
        return 4
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
