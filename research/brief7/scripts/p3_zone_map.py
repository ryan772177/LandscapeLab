"""p3_zone_map.py -- Brief 7 Phase 3 density zone map: the Brief 5 map, RE-CAPPED.

Brief 7 Phase 3 (BRIEF7_THE_LOOK.md): "zone map with forest_floor cap 1.0 (m=1),
plaza cap 2.157, treeline/vista uncapped at the global target". R-AESTHETIC-1
suspends the ms budgets (perf recorded, not gated), so the caps are RULED
numbers, not solved from a cost model:
  forest_floor 1.0    Ryan 2026-09-23: accept m=1 at forest_floor (T4: the
                      per-tree cost is structural; no cheap lever)
  plaza        2.157  t4_recalibration.json: the plaza cap at the MEASURED
                      per-tree rate (0.980 ms/1000)
  treeline     target the global target 5.48 (canopy_cover m_for.p90_bin)

Everything else -- disc centres, 512 m radius, 128 m blend, 256 m bins, the
target -- is read from research/brief5/derived/zone_map.json and reused
unchanged (one definition of the zones, rule 0). Per-bin m_final is
recomputed with the same blended-min rule place_foliage.load_zone_multiplier
ports, so the placer's own cross-check (max err < 1e-3) is the proof.

THE DENSITY CEILING STAYS (corrected 2026-09-27, same day). The first dry run
ran this map WITHOUT research/brief5/derived/density_ceiling.json and the
placer REFUSED: 1,017,096 planned against the 860,000 ceiling (proven only up
to D3's 812,258). D_max = 1,691 trees per 256 m bin (Ryan's ASK #1, Brief 5)
is the artefact that held D2 at 807k; it is applied AS RULED, not re-derived
at ff_cap 1.0 (a re-derivation would clamp every bin to today's densest
forest_floor bin and cancel the density everywhere -- that reading was the
error in this header's first version). Pass it: --density-ceiling
research/brief5/derived/density_ceiling.json (or recipe foliage.density_ceiling).

Usage:
    python research/brief7/scripts/p3_zone_map.py [--out research/brief7/p3/zone_map.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(REPO, "research", "brief5", "derived", "zone_map.json")
CAPS_RULED = {"forest_floor": 1.0, "plaza": 2.157, "treeline": None}  # None = target
EPS = 1e-9


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "research", "brief7", "p3",
                                                  "zone_map.json"))
    a = ap.parse_args(argv)
    zm = json.load(open(SRC, encoding="utf-8"))
    P = zm["params"]
    target = float(P["target_m"])
    inner, outer = float(P["inner_edge_m"]), float(P["outer_edge_m"])
    disc_r = float(P["disc_radius_m"])
    centers = {n: (float(c[0]), float(c[1])) for n, c in P["disc_centers_m"].items()}
    caps = {}
    for name in centers:
        c = CAPS_RULED[name]
        c = target if c is None else float(c)
        caps[name] = {"cap": round(min(c, target), 4),
                      "cap_basis": ("RULED Brief 7 Phase 3 / Ryan 2026-09-23: accept m=1 at "
                                    "forest_floor" if name == "forest_floor" else
                                    "t4_recalibration.json plaza cap at the measured per-tree "
                                    "rate" if name == "plaza" else
                                    "uncapped: global target (R-AESTHETIC-1, budgets suspended)"),
                      "brief5_cap": zm["caps"][name]["cap"]}

    def blended(name, d_m):
        c = caps[name]["cap"]
        if d_m <= inner:
            return c
        if d_m >= outer:
            return target
        t = (d_m - inner) / (outer - inner)
        return c + (target - c) * t

    bins_out, n_below, n_open, n_in = [], 0, 0, {n: 0 for n in centers}
    for b in zm["bins"]:
        cx, cy = float(b["center_m"][0]), float(b["center_m"][1])
        dist = {n: math.hypot(cx - centers[n][0], cy - centers[n][1]) for n in centers}
        containing = [n for n in centers if dist[n] <= disc_r]
        for n in containing:
            n_in[n] += 1
        contrib = {n: blended(n, dist[n]) for n in centers}
        m_final = min([target] + list(contrib.values()))
        binding = min(contrib, key=contrib.get)
        if m_final >= target - EPS:
            zone, n_open = "open", n_open + 1
        else:
            zone, n_below = binding, n_below + 1
        bins_out.append({"bin": b["bin"], "center_m": b["center_m"], "zone": zone,
                         "m_cap": round(m_final, 4), "m_final": round(m_final, 4),
                         "discs_containing": containing,
                         "dist_to_each_m": {n: round(dist[n], 1) for n in centers},
                         "cover": b.get("cover"), "cover_class": b.get("cover_class")})
    out = {
        "_what": "Brief 7 Phase 3 -- per-zone tree-density multiplier map (256 m bins), "
                 "the Brief 5 zones RE-CAPPED at the ruled Phase 3 caps.",
        "_zone_rule": zm["_zone_rule"] + " RE-CAPPED 2026-09-27: forest_floor 1.0 (m=1), "
                      "plaza 2.157, treeline = target; no density ceiling (see script header).",
        "_sources": {"zones_and_params": "research/brief5/derived/zone_map.json (unchanged)",
                     "caps": "BRIEF7_THE_LOOK.md Phase 3; Ryan 2026-09-23 (m=1 at "
                             "forest_floor); research/brief5/derived/t4_recalibration.json "
                             "(plaza 2.157)"},
        "params": P,
        "caps": caps,
        "summary": {"n_bins": len(bins_out), "n_in_disc": n_in,
                    "n_constrained_below_target": n_below,
                    "n_unconstrained_at_target": n_open},
        "bins": bins_out,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print("wrote %s: %d bins, %d below target, %d at target %.2f; caps %s" % (
        os.path.relpath(a.out, REPO), len(bins_out), n_below, n_open, target,
        {n: caps[n]["cap"] for n in caps}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
