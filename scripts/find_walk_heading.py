"""Which heading can the player actually walk, from the spawn, without steering?

Offline, read-only. Answers a question unit 5's walk test cannot answer for
itself: `walk_character.py` drives a STRAIGHT LINE from the PlayerStart with no
steering, and the PlayerStart is now in a town plaza surrounded by 303
buildings. On 2026-08-27 a walk at yaw 30 stalled at 27.3 m against a building
wall and sat there for 410 s.

**THAT IS THE TEST'S PROPERTY, NOT THE WORLD'S** -- R-WALKTEST already records
it: "a straight-line walker with no steering stops there forever". But the
consequence changed when a town was built on the spawn: before, every heading
was open ground; now most headings hit a wall in the first 30 m.

WHAT IT DOES
------------
For each heading it marches outward and stops at the first thing a straight-line
walker cannot pass:

  * a BUILDING footprint, tested as the oriented rectangle the plan declares --
    the same test the foliage clear and the encounter settlement exclusion use
    (non-negotiable 19, one declaration, three consumers)
  * ground steeper than the pawn's walkable floor, from the heightmap

and reports the headings with the longest clear run.

** THIS IS A PREFILTER, AND IT HAS BEEN CALIBRATED AGAINST TWO REAL WALKS. **
It reads the heightmap, the city plan and the foliage plans -- not collision and
not the navmesh.

Its FIRST version could not see trees and was duly wrong in the predicted
direction: it called yaw 260 clear for 238 m and the character stalled at 57.5.
With 219,659 tree instances added it predicts both measured stalls, and predicts
them CONSERVATIVELY, which is the safe direction for a tool used to choose a
test:

    yaw   model says            character measured
    30    22 m (building at 24)      27.3 m
    260   42 m (tree at 44)          57.5 m

Use it to CHOOSE a heading to test. It still cannot see collision geometry the
plans do not describe, and this project has been wrong three times trusting an
offline model's OPEN verdicts -- so a heading it likes is a candidate, never a
conclusion.
"""
import argparse
import io
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from plan_city import Terrain                                # noqa: E402
from design_pass import quad_slope_deg, agent_bar_deg        # noqa: E402


def rect_hit(px, py, cx, cy, sx, sy, yaw_deg, margin):
    """Is (px,py) inside an oriented rectangle plus margin?"""
    th = math.radians(yaw_deg)
    dx, dy = px - cx, py - cy
    lx = dx * math.cos(-th) - dy * math.sin(-th)
    ly = dx * math.sin(-th) + dy * math.cos(-th)
    return abs(lx) <= sx * 0.5 + margin and abs(ly) <= sy * 0.5 + margin


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--city", default="city/alpine_basin_town_plan.json")
    ap.add_argument("--headings", type=int, default=72)
    ap.add_argument("--max-m", type=float, default=1500.0)
    ap.add_argument("--step-m", type=float, default=2.0)
    ap.add_argument("--body-margin-cm", type=float, default=45.0,
                    help="half the character's capsule width, so a heading "
                         "that merely grazes a wall is not called clear")
    ap.add_argument("--trunk-radius-cm", type=float, default=38.0,
                    help="conifer trunk capsule radius. The vendor capsule on "
                         "SM_PVE_Norway_Spruce_01_A measures ~38 cm at unit "
                         "scale and is scaled per instance.")
    ap.add_argument("--no-foliage", action="store_true",
                    help="ignore trees -- the behaviour of the FIRST version, "
                         "kept so the difference can be measured rather than "
                         "asserted")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    world = json.loads(io.open(os.path.join(REPO_ROOT, args.world),
                               encoding="utf-8").read())
    city = json.loads(io.open(os.path.join(REPO_ROOT, args.city),
                              encoding="utf-8").read())
    T = Terrain(world)
    bar, prof = agent_bar_deg()
    cell = T.px / 100.0

    ps = None
    for v in (world.get("navigation") or {}).get("bounds_volumes", []):
        pass
    # the spawn is the town plaza; the plan records the site centre
    ps = city.get("site_centre_cm")
    if not ps:
        sys.exit("REFUSE: the city plan declares no site_centre_cm")
    cx0, cy0 = float(ps[0]), float(ps[1])

    Z = T.H.astype(np.float64) * (T.zs / 65535.0) / 100.0
    slope = quad_slope_deg(Z, cell)

    blockers = []
    for b in city.get("buildings", []):
        l = b["loc_cm"]
        s = b.get("size_cm", [600.0, 600.0, 600.0])
        blockers.append((float(l[0]), float(l[1]), float(s[0]), float(s[1]),
                         float(b.get("yaw_deg", 0.0))))
    lm = city.get("landmark")
    if lm:
        l, s = lm["loc_cm"], lm.get("size_cm", [1100.0, 1100.0, 1100.0])
        blockers.append((float(l[0]), float(l[1]), float(s[0]), float(s[1]),
                         float(lm.get("yaw_deg", 0.0))))

    # ---- TREES, because the first version could not see them --------------
    # The first run of this tool called yaw 260 clear for 238 m; the character
    # stalled at 57.5 m. Its own docstring predicted that: it read the
    # heightmap and the city plan, and the town has ~3,700 trees left standing
    # in the gaps between structures. Trees are QUERY-COLLIDABLE (R-TREECOLLIDE
    # made them so deliberately, and a PIE trace proved it), so a trunk stops a
    # straight-line walker exactly as a wall does.
    #
    # 219,659 instance transforms are on disk in foliage/*.json, so this costs
    # a file read rather than an editor query.
    trees = np.zeros((0, 3), dtype=np.float64)
    if not args.no_foliage:
        pts = []
        fdir = os.path.join(REPO_ROOT, "foliage")
        for name in sorted(os.listdir(fdir)):
            if not name.startswith(world["biome_id"]) or \
                    not name.endswith(".json"):
                continue
            d = json.loads(io.open(os.path.join(fdir, name),
                                   encoding="utf-8").read())
            for r in (d.get("instances") or []):
                # [x, y, z, yaw, pitch, roll, scale]
                pts.append((float(r[0]), float(r[1]), float(r[6])))
        trees = np.asarray(pts, dtype=np.float64) if pts else trees

    print("spawn        (%.0f, %.0f) cm -- the town plaza" % (cx0, cy0))
    print("trees        %s instances%s"
          % ("{:,}".format(len(trees)),
             "  (IGNORED -- --no-foliage)" if args.no_foliage else ""))
    print("agent bar    %.3f deg, profile %r" % (bar, prof))
    print("blockers     %d building footprints + landmark" % len(blockers))
    print("headings     %d at %.0f deg apart, marched to %.0f m at %.1f m"
          % (args.headings, 360.0 / args.headings, args.max_m, args.step_m))
    print()

    rows = []
    n = int(args.max_m / args.step_m)
    for h in range(args.headings):
        yaw = 360.0 * h / args.headings
        th = math.radians(yaw)
        clear = 0.0
        why = "reached the limit"
        for i in range(1, n + 1):
            d = i * args.step_m
            x = cx0 + d * 100.0 * math.cos(th)
            y = cy0 + d * 100.0 * math.sin(th)
            hit = False
            for (bx, by, sx, sy, byaw) in blockers:
                if abs(bx - x) > 4000.0 or abs(by - y) > 4000.0:
                    continue
                if rect_hit(x, y, bx, by, sx, sy, byaw, args.body_margin_cm):
                    hit = True
                    why = "building at %.0f m" % d
                    break
            if hit:
                break
            if len(trees):
                # radius scales with the instance, plus the character's own
                # half-width -- a trunk that merely grazes the capsule still
                # stops a walker with no steering.
                dx = trees[:, 0] - x
                dy = trees[:, 1] - y
                near = (np.abs(dx) < 500.0) & (np.abs(dy) < 500.0)
                if near.any():
                    rr = args.trunk_radius_cm * trees[near, 2] \
                        + args.body_margin_cm
                    if (dx[near] * dx[near] + dy[near] * dy[near]
                            <= rr * rr).any():
                        why = "tree at %.0f m" % d
                        break
            i_ = int((x - T.ox) / T.px)
            j_ = int((y - T.oy) / T.px)
            if not (1 <= i_ < slope.shape[1] - 1
                    and 1 <= j_ < slope.shape[0] - 1):
                why = "off the landscape at %.0f m" % d
                break
            if float(slope[j_, i_]) > bar:
                why = "slope %.1f deg at %.0f m" % (float(slope[j_, i_]), d)
                break
            clear = d
        rows.append({"yaw": yaw, "clear_m": clear, "stopped_by": why})

    rows.sort(key=lambda r: -r["clear_m"])
    print("  %-8s %10s   %s" % ("yaw", "clear_m", "stopped by"))
    for r in rows[:args.top]:
        print("  %-8.0f %10.0f   %s" % (r["yaw"], r["clear_m"],
                                        r["stopped_by"]))
    print()
    blocked = [r for r in rows if r["clear_m"] < 100.0]
    print("headings clear for < 100 m: %d of %d" % (len(blocked), len(rows)))
    print()
    print("PREFILTER -- heightmap, city plan and foliage plans; NOT collision")
    print("and NOT the navmesh. Calibrated against two real walks and")
    print("conservative on both. A heading it likes is a CANDIDATE to test,")
    print("never a conclusion that the walk would succeed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
