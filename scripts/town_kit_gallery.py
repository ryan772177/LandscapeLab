"""town_kit_gallery.py -- one probe house per kit roof, in a row on the rig, to tune every roof in one pass.

    python scripts/town_kit_gallery.py --dry-run
    python scripts/town_kit_gallery.py --go

Each house's footprint is its roof's native size minus the eave allowance (snapped down), so
plan_roof(..., only=roof) fits that roof near scale 1. Distance, spacing and course count come from the
recipe's probe block (recipes/town_kit.json). Labels TownKit_Gallery_<roof>, tag = the probe tag; each
replaces its earlier self. Stops on the first editor-side failure that returned no result, or after two
failures in a row (standing rule 6). Exit non-zero if any roof fails or does not fit. Does NOT save.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    pr = tkp._R["probe"]
    dist_m, spacing_m, courses = float(pr["gallery_dist_m"]), float(pr["gallery_spacing_m"]), int(pr["gallery_courses"])
    cx, cy = pr["camera_xy_cm"]
    cyaw = math.radians(pr["camera_yaw_deg"])
    fwd = (math.cos(cyaw), math.sin(cyaw))
    side = (-fwd[1], fwd[0])
    # slots come from the FULL recipe roof list, so a roof marked unusable leaves its slot empty and every other
    # house keeps its position (audit 2026-10-06 F4: re-slotting 7->4 put new houses 9 m from stale ones, and
    # replace is by label, so the stale ones stay until the editor restarts -- the gallery never saves)
    names = [r["name"] for r in tkp._R["roofs"]]
    specs, nofit = [], []
    for i, name in enumerate(names):
        if name not in tkp.ROOFS:
            print("%-20s unusable (recipe), slot left empty" % name)
            continue
        sx, sy = tkp.ROOFS[name][1]
        W = int((sx - 2 * tkp.EAVE_CM) // tkp.SNAP_CM * tkp.SNAP_CM)
        D = int((sy - 2 * tkp.EAVE_CM) // tkp.SNAP_CM * tkp.SNAP_CM)
        pieces = tkp.plan_house(W, D, courses, door_side=0, seed=11 + i)
        roof = tkp.plan_roof(W, D, courses, only=name)
        if roof is None:
            print("%s: NO FIT at %dx%d" % (name, W, D))
            nofit.append(name)
            continue
        pieces.append(roof)
        pieces.extend(tkp.plan_gables(W, D, courses, roof))
        off = (i - (len(names) - 1) / 2.0) * spacing_m * 100
        x = cx + fwd[0] * dist_m * 100 + side[0] * off
        y = cy + fwd[1] * dist_m * 100 + side[1] * off
        h = courses * tkp.COURSE_CM / 2.0
        specs.append({"level": pr["level"], "label": "TownKit_Gallery_" + name, "tags": [pr["tag"]],
                      "loc_cm": [x, y, 0.0], "ground_trace": True, "ground_offset_cm": 0.0,
                      "yaw_deg": pr["camera_yaw_deg"] + 90.0 - 180.0,
                      "box_center_cm": [0, 0, h], "box_extent_cm": [W / 2.0, D / 2.0, h],
                      "replace": True, "pieces": pieces})
        print("%-20s %4dx%-4d scale %s yaw %.0f at (%.0f, %.0f)"
              % (name, W, D, [round(v, 2) for v in roof["scale"]], roof["yaw"], x, y))
    if not a.go:
        print("dry run (pass --go)%s" % ("; NO FIT: %s" % nofit if nofit else ""))
        return 4 if nofit else 0
    import ue_exec
    tpl = open(os.path.join(bootstrap.REPO_ROOT, "scripts", "payloads", "town_kit_build_house.py"),
               encoding="utf-8").read()
    bad, streak = 0, 0
    for s in specs:
        code, out, raw = ue_exec.run(tpl.replace("__SPEC__", json.dumps(s)), marker="__LL__", timeout=25,
                                     stage_name="town_kit_gallery")
        ok = isinstance(out, dict) and out.get("ok")
        if ok:
            streak = 0
            print("%-34s ok" % s["label"])
            continue
        bad += 1
        streak += 1
        err = (out or {}).get("error") if isinstance(out, dict) else None
        tail = ((out or {}).get("traceback") if isinstance(out, dict) else (raw or ""))[-800:]
        print("%-34s FAIL code %s: %s\n%s" % (s["label"], code, err, tail))
        if not isinstance(out, dict) or streak >= 2:
            print("STOP: %s" % ("no result from the editor" if not isinstance(out, dict) else "two failures in a row"))
            break
    return 0 if not bad and not nofit else 4


if __name__ == "__main__":
    sys.exit(main())
