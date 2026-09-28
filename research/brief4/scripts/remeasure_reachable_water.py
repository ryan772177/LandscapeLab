"""remeasure_reachable_water.py -- Brief-4 CARVE_PLAN T6 figure re-measure.

The two one-screen-spec MEASUREMENT figures go stale by construction when
water is placed (RULING §4.3):
  - z-span 0-1552.5 m
  - 36.53 km² reachable of 49.27 walkable

WALKABLE is the offline 1 m per-quad instrument (measure_walkable_extent.py:
quad_slope_deg <= the character bar) -- this reproduces the 49.27 baseline
EXACTLY before any water number is trusted (rule 13: a re-measure whose
instrument does not reproduce the prior value is not a measurement). Water
is then subtracted: a cell inside a §7 water footprint is not walkable
ground (water non-walkable, RULING).

REACHABLE (36.53) is the NAVMESH lattice (R-NAVGRID), a different
instrument. The offline 1 m BFS reachable is reported here as the
component-connectivity estimate and to bound the water impact; the
NAVMESH-authoritative re-measure needs a rebuild with NavArea_Null
modifiers over the lake footprints and is FOLDED to a nav-modifier rebuild
pass, with the submerged-walkable area below as its target.

Usage:
  python remeasure_reachable_water.py [--out <dir>]
"""
import argparse
import datetime as _dt
import io
import json
import os
import sys

import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from plan_city import Terrain                       # noqa: E402
from design_pass import quad_slope_deg, agent_bar_deg  # noqa: E402


def _load(p):
    with io.open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    date = _dt.date.today().isoformat()
    out = a.out or os.path.join(REPO, "_verify", "brief4",
                                "t6_reachable_%s" % date)
    os.makedirs(out, exist_ok=True)

    world = _load(os.path.join(REPO, "recipes/alpine_8k.json"))
    T = Terrain(world)
    bar, prof = agent_bar_deg()
    cell = T.px / 100.0
    Z = T.H.astype(np.float64) * (T.zs / 65535.0) / 100.0
    slope = quad_slope_deg(Z, cell)          # (h-1, w-1) on the quad grid
    walk = slope <= bar
    qh, qw = walk.shape
    cell_km2 = cell * cell / 1e6

    # z-span from the FULL heightmap (incl. actor-z datum), matching T5a
    ls = world["landscape"]
    az = float(ls["location_cm"][2])
    zs = float(ls["z_scale_cm"])
    zmin = (az + (T.H.min() / 65535.0 - 0.5) * zs) / 100.0
    zmax = (az + (T.H.max() / 65535.0 - 0.5) * zs) / 100.0

    # water footprint (derived union, 4 m grid) -> the 1 m quad grid by
    # exact index repeat (8128 = 4*2032; each 4 m cell -> 4x4 quads).
    z = np.load(os.path.join(REPO, "encounters/alpine_8k_water_exclusion.npz"),
                allow_pickle=False)
    wmask = z["mask"]                        # (2033, 2033), [row, col]
    up = np.repeat(np.repeat(wmask[:qh // 4, :qw // 4], 4, 0), 4, 1)
    if up.shape != (qh, qw):
        # pad/crop to the quad grid (the +1 vertex row/col has no quad)
        u = np.zeros((qh, qw), bool)
        h2, w2 = min(qh, up.shape[0]), min(qw, up.shape[1])
        u[:h2, :w2] = up[:h2, :w2]
        up = u
    walk_dry = walk & ~up

    def reach_cells(mask):
        lab, _n = ndimage.label(mask, structure=np.ones((3, 3), np.uint8))
        ps = next(c for c in world["capture"]["cameras"]
                  if c["name"] == "hero_spawn")
        ai = min(max(int(round((ps["location_cm"][1] - T.oy) / T.px)), 0),
                 qh - 1)     # row  <- y
        aj = min(max(int(round((ps["location_cm"][0] - T.ox) / T.px)), 0),
                 qw - 1)     # col  <- x
        home = int(lab[ai, aj])
        if home == 0:
            ys, xs = np.nonzero(mask)
            if not len(xs):
                return 0
            k = int(np.argmin((ys - ai) ** 2 + (xs - aj) ** 2))
            home = int(lab[ys[k], xs[k]])
        return int((lab == home).sum())

    walk_km2 = int(walk.sum()) * cell_km2
    walk_dry_km2 = int(walk_dry.sum()) * cell_km2
    submerged_km2 = int((walk & up).sum()) * cell_km2
    reach_pre = reach_cells(walk) * cell_km2
    reach_post = reach_cells(walk_dry) * cell_km2

    result = {
        "_what": "Brief-4 T6 re-measure: walkable + reachable, post-carve, "
                 "water subtracted. Walkable = the offline 1 m quad instrument "
                 "(reproduces the 49.27 baseline). Reachable = offline BFS; "
                 "navmesh-authoritative re-measure folded to a nav-modifier "
                 "rebuild.",
        "date": date, "agent_profile": prof, "agent_bar_deg": round(bar, 6),
        "cell_m": cell,
        "z_span_m": [round(zmin, 3), round(zmax, 3)],
        "walkable_km2": round(walk_km2, 2),
        "walkable_dry_km2": round(walk_dry_km2, 2),
        "walkable_submerged_km2": round(submerged_km2, 2),
        "reachable_pre_water_bfs_km2": round(reach_pre, 2),
        "reachable_post_water_bfs_km2": round(reach_post, 2),
        "reachable_lost_to_water_km2": round(reach_pre - reach_post, 2),
        "spec_navmesh_reachable_km2": 36.53,
        "_navmesh_note": "36.53 is the NAVMESH lattice (R-NAVGRID). The offline "
            "1 m BFS above is a DIFFERENT instrument (optimistic, no agent "
            "radius/step) and need not equal it. The navmesh-authoritative "
            "re-measure needs a rebuild carving the lake footprints as "
            "NavArea_Null; target reduction = walkable_submerged_km2.",
    }
    json.dump(result, open(os.path.join(out, "reachable_remeasure.json"), "w"),
              indent=1)
    for k, v in result.items():
        if not k.startswith("_"):
            print("%-32s %s" % (k, v))
    print("wrote", os.path.join(out, "reachable_remeasure.json"))


if __name__ == "__main__":
    main()
