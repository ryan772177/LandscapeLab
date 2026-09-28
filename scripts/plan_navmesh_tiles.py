"""Derive the navmesh tile grid as RECIPE DATA, one declaration for N volumes.

    python scripts/plan_navmesh_tiles.py                 report only
    python scripts/plan_navmesh_tiles.py --write         update the recipe

WHY THIS EXISTS
---------------
`PHASE2_PLAN.md:250` -- *"World-scale navmesh. Unit 8 builds one chunk. The
other 63 are a decision, not a plan."* -- and unit 8's own note rules that the
navigable region is **authored, versioned recipe data**, not an emergent
accident. This is that derivation.

Until now the two built volumes were hand-authored entries. Forty-nine
hand-authored entries would be forty-nine chances to mistype a bound, and no
single place that says what the grid IS. Non-negotiable 24: volumes become
PROJECTIONS of one declaration.

WHY FULL COVERAGE, AND WHY THIS IS NOT A DESIGN RULING I INVENTED
-----------------------------------------------------------------
Measured 2026-08-27: the playable world is bounded by WHERE NAVMESH WAS BUILT,
not by terrain -- a relay sweep stops at 350-1050 m and almost every ray stops
exactly on a NavBounds volume EDGE. The RULED boundary is the region edge
(WORLD_VISION ruling 3, 8064 m per region, adjacent borders walkable). Every
metre between the two is an unruled invisible wall, and this project already
spent a week diagnosing one of those as a "sealed basin".

Where the walkable component genuinely ends inside the region -- the 25.4% of
ground over the agent bar -- the boundary is TERRAIN, which is honest and
self-explaining. Where a volume ends, the boundary is an artefact.

THE GRID IS ANCHORED ON WHAT IS ALREADY BUILT
---------------------------------------------
Tile (0,0) is exactly `NavBounds_Town` and (1,0) exactly `NavBounds_TownEast`,
so the two existing volumes ARE grid cells and are carried through with their
original hand-measured bounds and basis text untouched. A grid that renamed or
moved them would invalidate the reachability sidecars bound to them.

Z: MEASURED, AND FROM WHICH INSTRUMENT
--------------------------------------
The existing two volumes took z from 625 collision traces each. This takes z
from the HEIGHTMAP, which is a different instrument -- and the two are known to
agree: `check_collision_truth` over 500 random points on this landscape reads
|collision - heightmap| p50 0.011, p90 0.039, max 0.168 m. Against margins of
11 m below and 20 m above, a 0.17 m disagreement cannot matter.

Stating the instrument is the point. A z that came from the heightmap and is
described as "measured" would be the derived-record trap.
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

TILE_CM = 104000.0          # 1040 m, the proven volume size
MARGIN_BELOW_CM = 1100.0    # the convention the two built volumes used
MARGIN_ABOVE_CM = 2000.0
TILE_SIZE_UU = 1600.0       # bounds must be multiples of this
MIN_TILE_FRAC = 0.30        # a clipped edge tile below this is a sliver
KEEP = ("NavBounds_Town", "NavBounds_TownEast")


def snap(v, m=TILE_SIZE_UU):
    return math.floor(v / m) * m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--min-walk-frac", type=float, default=0.05,
                    help="skip a tile whose walkable fraction is below this. "
                         "A CLOSED verdict from the slope prefilter is the "
                         "half that is trusted -- ground this steep will not "
                         "become walkable once Recast adds agent radius and "
                         "step height.")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    wpath = os.path.join(REPO_ROOT, args.world)
    world = json.loads(io.open(wpath, encoding="utf-8").read())
    T = Terrain(world)
    bar, prof = agent_bar_deg()
    cell = T.px / 100.0

    nav = world.get("navigation") or {}
    existing = {v["name"]: v for v in nav.get("bounds_volumes", [])}
    for n in KEEP:
        if n not in existing:
            sys.exit("REFUSE: %s is not in the recipe. The grid is anchored "
                     "on it; without it the tiling would not line up with "
                     "what is already built." % n)

    anchor = existing["NavBounds_Town"]
    ax, ay = float(anchor["min_cm"][0]), float(anchor["min_cm"][1])
    # assert the anchor really is one tile, rather than assuming it
    for k, lo, hi in (("x", anchor["min_cm"][0], anchor["max_cm"][0]),
                      ("y", anchor["min_cm"][1], anchor["max_cm"][1])):
        if abs((float(hi) - float(lo)) - TILE_CM) > 1.0:
            sys.exit("REFUSE: NavBounds_Town is %.0f cm on %s, not the %.0f "
                     "the grid assumes" % (float(hi) - float(lo), k, TILE_CM))

    # landscape extent
    lx0, ly0 = T.ox, T.oy
    lx1, ly1 = T.ox + (T.w - 1) * T.px, T.oy + (T.h - 1) * T.px

    # Z as WORLD cm, using the SAME datum plan_city.Terrain.z_cm applies
    # (oz + (h/65535 - 0.5)*zs), so the volume z bounds below are correct even
    # when location_z != z_scale/2. For alpine_8k oz==zs/2, so this equals the
    # old 0-based H*zs/65535 and the output is unchanged. (Slope is a gradient,
    # so the constant offset does not affect it either way.)
    Z = T.oz + (T.H.astype(np.float64) / 65535.0 - 0.5) * T.zs   # centimetres
    slope = quad_slope_deg(Z / 100.0, cell)
    walk = slope <= bar

    i0 = int(math.floor((lx0 - ax) / TILE_CM))
    i1 = int(math.ceil((lx1 - ax) / TILE_CM))
    j0 = int(math.floor((ly0 - ay) / TILE_CM))
    j1 = int(math.ceil((ly1 - ay) / TILE_CM))

    tiles = []
    skipped = []
    slivers = []
    for j in range(j0, j1):
        for i in range(i0, i1):
            x0 = ax + i * TILE_CM
            y0 = ay + j * TILE_CM
            x1, y1 = x0 + TILE_CM, y0 + TILE_CM
            # Clip to the landscape; a volume over nothing builds nothing.
            cx0, cy0 = max(x0, lx0), max(y0, ly0)
            cx1, cy1 = min(x1, lx1), min(y1, ly1)
            # !! AND DROP SLIVERS. The grid is anchored on NavBounds_Town, not
            # on the landscape corner, so the outermost row and column are
            # always partial. The first version only required the clipped
            # extent to exceed one TileSizeUU (16 m) and duly emitted tiles
            # 96 m tall -- 81 volumes where the region holds about 64, each
            # sliver costing a volume and its chunk actors for a strip of
            # ground the neighbouring tile could not use anyway.
            if (cx1 - cx0) < MIN_TILE_FRAC * TILE_CM or \
                    (cy1 - cy0) < MIN_TILE_FRAC * TILE_CM:
                slivers.append((i, j, (cx1 - cx0) / 100.0,
                                (cy1 - cy0) / 100.0))
                continue
            gi0 = int((cx0 - T.ox) / T.px)
            gi1 = int((cx1 - T.ox) / T.px)
            gj0 = int((cy0 - T.oy) / T.px)
            gj1 = int((cy1 - T.oy) / T.px)
            sub_w = walk[gj0:min(gj1, walk.shape[0]),
                         gi0:min(gi1, walk.shape[1])]
            sub_z = Z[gj0:gj1 + 1, gi0:gi1 + 1]
            if sub_w.size == 0 or sub_z.size == 0:
                # Defensive only: a tile that passed the sliver gate above is
                # anchored within the landscape, so its clipped extent always
                # spans >=1 sample. If this ever fires the grid math is wrong
                # -- record it rather than dropping it into no tally.
                slivers.append((i, j, 0.0, 0.0))
                continue
            frac = float(sub_w.mean())
            zmin = float(sub_z.min()) - MARGIN_BELOW_CM
            zmax = float(sub_z.max()) + MARGIN_ABOVE_CM
            rec = {"i": i, "j": j, "walk_frac": frac,
                   "min_cm": [snap(cx0), snap(cy0), snap(zmin)],
                   "max_cm": [snap(cx1), snap(cy1),
                              snap(zmax) + TILE_SIZE_UU],
                   "z_span_m": (zmax - zmin) / 100.0}
            if frac < args.min_walk_frac:
                skipped.append(rec)
                continue
            tiles.append(rec)

    print("world        %s" % args.world)
    print("agent bar    %.3f deg, profile %r" % (bar, prof))
    print("tile         %.0f m, anchored on NavBounds_Town at (%.0f, %.0f)"
          % (TILE_CM / 100.0, ax, ay))
    print("landscape    x %.0f..%.0f   y %.0f..%.0f cm" % (lx0, lx1, ly0, ly1))
    print()
    # Sum each tile's ACTUAL clipped footprint, not a full TILE_CM^2 -- edge
    # tiles are clipped to the landscape and were over-counted at full area.
    _kept_km2 = sum(((t["max_cm"][0] - t["min_cm"][0]) / 100.0)
                    * ((t["max_cm"][1] - t["min_cm"][1]) / 100.0)
                    for t in tiles) / 1e6
    print("tiles kept   %d   (%.2f km2 of volume, edge tiles at CLIPPED area)"
          % (len(tiles), _kept_km2))
    print("tiles below %.0f%% walkable, SKIPPED: %d"
          % (100 * args.min_walk_frac, len(skipped)))
    print("edge SLIVERS dropped (< %.0f%% of a tile after clipping): %d"
          % (100 * MIN_TILE_FRAC, len(slivers)))
    zs = [t["z_span_m"] for t in tiles]
    if zs:
        zs.sort()
        print("z span       p50 %.0f m   min %.0f   max %.0f"
              % (zs[len(zs) // 2], zs[0], zs[-1]))
    print()

    # NN13: a zero-tile plan is not a plan. Without this guard max(xs) below
    # raises ValueError on an empty list -- a crash where a clean REFUSE
    # belongs (matching the sys.exit("REFUSE ...") gates earlier).
    if not tiles:
        sys.exit("REFUSE: zero tiles planned -- no tile met the %.0f%% "
                 "walkable fraction after clipping. An empty navmesh plan is "
                 "not a plan." % (100 * args.min_walk_frac))

    # the tile-budget check the recipe validator will run
    xs = [t["min_cm"][0] for t in tiles] + [t["max_cm"][0] for t in tiles]
    ys = [t["min_cm"][1] for t in tiles] + [t["max_cm"][1] for t in tiles]
    side = max(max(xs) - min(xs), max(ys) - min(ys))
    layers = float(nav.get("average_layers_per_tile", 1.5))
    ts = float(nav.get("tile_size_uu", TILE_SIZE_UU))
    per_side = int(math.ceil(side / ts)) + 1
    total = int(math.ceil(per_side * per_side * layers))
    print("navmesh tile budget: union side %.0f cm / TileSizeUU %.0f"
          % (side, ts))
    print("  %d per side, x %.1f layers = %s tiles against the 1,048,576 "
          "hard limit" % (per_side, layers, "{:,}".format(total)))
    if total > 1048576:
        print("  REFUSE: over the hard limit -- the engine logs an error and "
              "SILENTLY CLAMPS")
        return 3
    print()

    vols = []
    for t in tiles:
        nm = None
        for k in KEEP:
            ek = existing[k]
            if (abs(float(ek["min_cm"][0]) - t["min_cm"][0]) < 1.0
                    and abs(float(ek["min_cm"][1]) - t["min_cm"][1]) < 1.0):
                nm = k
                break
        if nm:
            # CARRIED THROUGH UNTOUCHED. Their z came from 625 collision
            # traces each and their basis records that; regenerating them
            # from the heightmap would replace a measurement with a weaker
            # one, and renaming them would invalidate every reachability
            # sidecar bound to them.
            vols.append(existing[nm])
            continue
        vols.append({
            "name": "NavBounds_R%+03d%+03d" % (t["i"], t["j"]),
            "min_cm": t["min_cm"],
            "max_cm": t["max_cm"],
            "basis": (
                "Tile (%d, %d) of the %.0f m navmesh grid anchored on "
                "NavBounds_Town, derived by scripts/plan_navmesh_tiles from "
                "one declaration rather than hand-authored. Walkable fraction "
                "%.1f%% at the %.3f deg walk bar. Z from the HEIGHTMAP, not "
                "from collision traces: those two agree on this landscape at "
                "p50 0.011 / p90 0.039 / max 0.168 m over 500 random points "
                "(check_collision_truth), which cannot matter against margins "
                "of %.0f m below and %.0f m above. Bounds are multiples of "
                "TileSizeUU %.0f so chunk actors do not straddle tiles."
                % (t["i"], t["j"], TILE_CM / 100.0, 100.0 * t["walk_frac"],
                   bar, MARGIN_BELOW_CM / 100.0, MARGIN_ABOVE_CM / 100.0,
                   TILE_SIZE_UU)),
        })

    print("  %-22s %-34s %8s" % ("name", "min_cm", "walk%"))
    for v, t in zip(vols, tiles):
        print("  %-22s %-34s %7.1f%%"
              % (v["name"], "%.0f, %.0f, %.0f" % tuple(v["min_cm"]),
                 100.0 * t["walk_frac"]))

    if not args.write:
        print()
        print("REPORT ONLY -- nothing written. Re-run with --write.")
        return 0

    world["navigation"]["bounds_volumes"] = vols
    io.open(wpath, "w", encoding="utf-8", newline="\n").write(
        json.dumps(world, indent=1) + "\n")
    print()
    print("wrote %d volumes into %s" % (len(vols), args.world))
    print("The two built volumes were carried through UNCHANGED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
