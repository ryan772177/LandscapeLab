"""How much of the region is walkable at all, and where is it?

Offline, read-only. Answers the question that must come BEFORE "how much
navmesh should we build": navmesh over ground the agent can never stand on is
build time and package size spent on nothing.

    python scripts/measure_walkable_extent.py
    python scripts/measure_walkable_extent.py --tile-m 1040

WHAT IT MEASURES
----------------
Per-QUAD surface slope from FORWARD differences and the 2-D gradient MAGNITUDE
(see design_pass.quad_slope_deg -- a per-axis test understates slope by up to
sqrt(2), and np.gradient's central differences halve a one-cell step). A quad is
walkable if its slope is at or under the pawn's profile bar, DERIVED from
recipes/character.json rather than typed.

Then it tiles the region at the navmesh-volume size and reports walkable
fraction per tile, so the tiles worth covering can be ranked.

** THIS IS A PREFILTER AND ITS OPTIMISTIC VERDICTS ARE NOT TRUSTED. ** It models
no agent radius, no step height and no connectivity, and this project has twice
had it pass ground the built navmesh refused. Its CLOSED verdicts are the useful
half: a tile that is 2% walkable by slope alone will not become more walkable
once Recast is stricter, so it can be ruled out cheaply. Ruling a tile IN still
costs a real build to confirm.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from plan_city import Terrain                                # noqa: E402
from design_pass import quad_slope_deg, agent_bar_deg        # noqa: E402

TOWN_CM = (-210800.0, 278800.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--tile-m", type=float, default=1040.0,
                    help="navmesh volume edge, to tile the region by")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    world = json.load(open(os.path.join(REPO_ROOT, args.world),
                           encoding="utf-8"))
    T = Terrain(world)
    bar, prof = agent_bar_deg()
    cell = T.px / 100.0

    Z = T.H.astype(np.float64) * (T.zs / 65535.0) / 100.0
    slope = quad_slope_deg(Z, cell)
    walk = slope <= bar

    print("terrain      %s  %d x %d at %.2f m" % (world["heightmap"]["source"],
                                                  T.w, T.h, cell))
    print("agent bar    %.3f deg from terrain_erosion.MOVEMENT_PROFILES[%r]; "
          "profile name %r from recipes/character.json" % (bar, prof, prof))
    print("elevation    %.1f to %.1f m" % (Z.min(), Z.max()))
    print()
    total_km2 = walk.size * cell * cell / 1e6
    print("WHOLE REGION")
    print("  quads          %s   (%.2f km2)" % ("{:,}".format(walk.size),
                                                total_km2))
    print("  walkable       %.2f%%  = %.2f km2"
          % (100.0 * walk.mean(), total_km2 * walk.mean()))
    print("  slope p50 %.1f  p90 %.1f  max %.1f deg"
          % (np.percentile(slope, 50), np.percentile(slope, 90), slope.max()))
    print()

    # tile the region at the navmesh volume size, anchored on the TERRAIN
    # ORIGIN (T.ox, T.oy). NB: this does NOT line up with the built town
    # navmesh volume -- TOWN_CM is used only for dist_from_town_m below, and
    # (TOWN_CM - T.ox)/tile_cm is non-integer, so a town tile is not on a
    # boundary here. This is a coverage survey, not the volume plan.
    step = int(round(args.tile_m / cell))
    ox = T.ox
    oy = T.oy
    nx = walk.shape[1] // step
    ny = walk.shape[0] // step
    rows = []
    for j in range(ny):
        for i in range(nx):
            sub = walk[j * step:(j + 1) * step, i * step:(i + 1) * step]
            cx = ox + (i + 0.5) * step * T.px
            cy = oy + (j + 0.5) * step * T.px
            rows.append({
                "i": i, "j": j,
                "centre_cm": [round(cx, 1), round(cy, 1)],
                "walk_frac": float(sub.mean()),
                "dist_from_town_m": math.hypot(cx - TOWN_CM[0],
                                               cy - TOWN_CM[1]) / 100.0,
            })

    print("TILED AT %.0f m -- %d x %d = %d tiles" % (args.tile_m, nx, ny,
                                                     len(rows)))
    good = [r for r in rows if r["walk_frac"] >= 0.5]
    poor = [r for r in rows if r["walk_frac"] < 0.2]
    # actual tile side is step*cell (step = round(tile_m/cell)); this equals
    # tile_m only when tile_m is a whole number of cells -- use the real side.
    _tile_side_m = step * cell
    print("  >= 50%% walkable   %d tiles  (%.1f km2)"
          % (len(good), len(good) * (_tile_side_m ** 2) / 1e6))
    print("  <  20%% walkable   %d tiles  -- cheap to RULE OUT" % len(poor))
    print()
    print("  The %d nearest tiles to the town, by distance:" % args.top)
    print("    %-10s %-22s %10s %12s" % ("tile", "centre cm", "walk%",
                                         "dist_m"))
    for r in sorted(rows, key=lambda r: r["dist_from_town_m"])[:args.top]:
        print("    %-10s %-22s %9.1f%% %12.0f"
              % ("%d,%d" % (r["i"], r["j"]),
                 "%.0f, %.0f" % tuple(r["centre_cm"]),
                 100.0 * r["walk_frac"], r["dist_from_town_m"]))
    print()
    print("PREFILTER. Optimistic verdicts are not trusted -- no agent radius,")
    print("no step height, no connectivity. The CLOSED verdicts are the useful")
    print("half: a tile this says is 2% walkable will not improve under Recast.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
