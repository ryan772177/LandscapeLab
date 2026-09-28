#!/usr/bin/env python3
"""Brief 5 D2 (round 2): post-multiplier density ceiling.

Ryan's ASK #1 ruling (2026-09-22): a global per-bin density ceiling on top of
the zone multiplier, so no bin exceeds the densest the budget-capped
forest_floor is allowed to be.

  D_max     = max over forest_floor-disc bins of  trees_now[bin] * ff_cap
              (ff_cap = the forest_floor cull-disc cap = 2.38, the density the
               13.0 ms budget with its 0.1 ms margin permits)
  m_final   = min( m_zone(bin) , D_max / trees_now[bin] )   (blend unchanged)

This tool measures trees_now per 256 m bin from the shipped foliage/ plans,
computes D_max and the dense per-bin trees_now grid the placer needs, identifies
the "open_max" station (the densest post-ceiling bin OUTSIDE every disc, a new
budget station derived like forest_floor and measured in D4), and projects the
ceilinged instance total. Offline, read-only inputs.

Outputs research/brief5/derived/density_ceiling.json.
"""
import json
import os
from collections import defaultdict

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BR = os.path.join(REPO, "research", "brief5")


def _tree_species(recipe):
    """The placed tree species = foliage species that are neither grass nor
    rock (place_foliage.plan skips both). Derived from the recipe so a fifth
    tree cannot silently drop out of trees_now and under-bind the ceiling."""
    return [sp["name"] for sp in recipe["foliage"]["species"]
            if "role" not in sp and sp.get("system") != "grass"]


def main():
    recipe = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                            encoding="utf-8-sig"))
    SPECIES = _tree_species(recipe)
    BIOME = recipe["biome_id"]
    zm = json.load(open(os.path.join(BR, "derived", "zone_map.json"),
                        encoding="utf-8"))
    P, caps = zm["params"], zm["caps"]
    bin_cm = float(P["bin_cm"])
    bin_m = bin_cm / 100.0
    target = float(P["target_m"])
    inner = float(P["inner_edge_m"])
    outer = float(P["outer_edge_m"])
    R_m = float(P["disc_radius_cm"]) / 100.0
    centers = {n: (float(c[0]), float(c[1]))
               for n, c in P["disc_centers_m"].items()}
    capm = {n: float(caps[n]["cap"]) for n in centers}
    ff_cap = capm["forest_floor"]
    ffx, ffy = centers["forest_floor"]

    def mzone(cx, cy):
        m = target
        for n, (dx, dy) in centers.items():
            d = ((cx - dx) ** 2 + (cy - dy) ** 2) ** 0.5
            c = capm[n]
            t = min(max((d - inner) / (outer - inner), 0.0), 1.0)
            m = min(m, c + (target - c) * t)
        return m

    # trees_now per bin from the shipped plans (all four tree species, m=1)
    tn = defaultdict(int)
    for sp in SPECIES:
        d = json.load(open(os.path.join(REPO, "foliage", "%s_%s.json"
                                        % (BIOME, sp)), encoding="utf-8"))
        for r in d["instances"]:
            ix = int(np.floor(r[0] / bin_cm))
            iy = int(np.floor(r[1] / bin_cm))
            tn[(ix, iy)] += 1

    # D_max from the forest_floor disc (the budget-capped zone sets the ceiling)
    ff_bins = []
    for (ix, iy), c in tn.items():
        cx, cy = (ix + 0.5) * bin_m, (iy + 0.5) * bin_m
        if ((cx - ffx) ** 2 + (cy - ffy) ** 2) ** 0.5 <= R_m:
            ff_bins.append(((ix, iy), c))
    if not ff_bins:
        raise ValueError("no forest_floor-disc bins hold trees; cannot set D_max")
    dmax_bin, dmax_trees_now = max(ff_bins, key=lambda kv: kv[1])
    D_max = dmax_trees_now * ff_cap

    # dense grid over the bin bounding box of the current forest
    ixs = [k[0] for k in tn]
    iys = [k[1] for k in tn]
    ix0, ix1 = min(ixs), max(ixs)
    iy0, iy1 = min(iys), max(iys)
    nx, ny = ix1 - ix0 + 1, iy1 - iy0 + 1
    grid = np.zeros((ny, nx), dtype=np.int64)
    for (ix, iy), c in tn.items():
        grid[iy - iy0, ix - ix0] = c

    # projection + open_max (densest post-ceiling bin outside every disc)
    tot_now = int(sum(tn.values()))
    tot_zone = tot_ceil = 0.0
    n_bound = 0
    open_max = None
    for (ix, iy), c in tn.items():
        cx, cy = (ix + 0.5) * bin_m, (iy + 0.5) * bin_m
        mz = mzone(cx, cy)
        mf = min(mz, D_max / c) if c > 0 else mz
        if mf < mz - 1e-9:
            n_bound += 1
        tot_zone += c * mz
        post = c * mf
        tot_ceil += post
        in_disc = any(((cx - dx) ** 2 + (cy - dy) ** 2) ** 0.5 <= R_m
                      for (dx, dy) in centers.values())
        if not in_disc:
            if open_max is None or post > open_max["post_ceiling_count"]:
                open_max = {"bin": [ix, iy],
                            "center_m": [round(cx, 1), round(cy, 1)],
                            "trees_now": int(c), "m_zone": round(mz, 4),
                            "m_final": round(mf, 4),
                            "post_ceiling_count": round(post, 1)}

    out = {
        "_what": "Brief 5 D2 round 2 -- post-multiplier per-bin density ceiling.",
        "_rule": ("Ryan ASK#1 2026-09-22: D_max = max over forest_floor-disc bins "
                  "of trees_now*ff_cap; m_final = min(m_zone, D_max/trees_now); "
                  "blend unchanged. A fourth budget station open_max (densest "
                  "post-ceiling bin outside all discs) is added, budget 13.0, "
                  "measured in D4 like the others."),
        "ff_cap": round(ff_cap, 4),
        "D_max": round(D_max, 3),
        "D_max_bin": list(dmax_bin),
        "D_max_trees_now": int(dmax_trees_now),
        "bin_cm": bin_cm,
        "target_m": target,
        "grid": {"ix0": ix0, "iy0": iy0, "nx": nx, "ny": ny,
                 "trees_now": grid.tolist()},
        "open_max": open_max,
        "projected": {
            "total_now": tot_now,
            "total_zone_no_ceiling": round(tot_zone, 0),
            "total_ceiled": round(tot_ceil, 0),
            "ratio_ceiled": round(tot_ceil / tot_now, 3),
            "bins_ceiling_bound": n_bound,
            "bins_total": len(tn),
            "note_vs_500k": ("<=500k: MAX_INSTANCES may be raised to it"
                             if tot_ceil <= 500000 else
                             ">500k: STOP and show Ryan the count (his rule)"),
        },
        "_sources": {
            "trees_now": "foliage/alpine_8k_<species>.json (shipped, m=1)",
            "ff_cap/m_zone": "research/brief5/derived/zone_map.json",
        },
    }
    dest = os.path.join(BR, "derived", "density_ceiling.json")
    json.dump(out, open(dest, "w", encoding="utf-8", newline="\n"), indent=1)
    print("wrote", os.path.relpath(dest, REPO))
    print("ff_cap=%.3f  D_max=%.1f trees/bin (bin %s, %d trees now)"
          % (ff_cap, D_max, dmax_bin, dmax_trees_now))
    print("projected: now=%d  no-ceiling=%.0f (%.2fx)  CEILED=%.0f (%.2fx)  bound=%d/%d"
          % (tot_now, tot_zone, tot_zone / tot_now, tot_ceil,
             tot_ceil / tot_now, n_bound, len(tn)))
    print("open_max station:", open_max)
    print(out["projected"]["note_vs_500k"])
    return out


if __name__ == "__main__":
    main()
