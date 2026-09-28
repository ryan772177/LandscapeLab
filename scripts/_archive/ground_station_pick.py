"""ground_station_pick.py — the final pass: raymarch every geometric
survivor and rank by the BINDING constraint.

    python scripts/ground_station_pick.py --candidates <feasibility.json>
        [--march 900] [--out J]

The geometry turned out not to be the hard part. Raymarched, the
survivors clear p25 (48-81 m), p75 (145-365 m) and frac (0.59-0.69)
comfortably; what they fail is MEADOW at 50-300 m, 0.04-0.19 against a
0.50 floor. Ranking by `frac` therefore surfaces the WORST candidates on
the axis that actually decides, which is what the first marched table
did.

So this ranks by meadow_frac among views that already satisfy the three
geometric checks, and reports the whole Pareto picture rather than one
winner -- because if nothing clears 0.50, that is a finding about the
world's meadow distribution and a ruling for Ryan, not a number to nudge.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from bench_station_derive import load_terrain  # noqa: E402
from find_ground_station import (MEADOW_FRAC_MIN, MID_FRAC_MIN,  # noqa: E402
                                 P25_MIN, P75_MAX, _meadow, march_stats)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--march", type=int, default=900)
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    cands = json.load(open(a.candidates, encoding="utf-8"))["winners"]
    Z, ox, oy, px_m = load_terrain(os.path.join(REPO, "recipes",
                                                "alpine_8k.json"))
    meadow = _meadow()
    rows = []
    for w in cands[:a.march]:
        cam = np.array([w["x_cm"] / 100.0, w["y_cm"] / 100.0,
                        w["z_cm"] / 100.0])
        ms = march_stats(Z, ox, oy, px_m, meadow, cam, 0.0, w["yaw"])
        if ms is None:
            continue
        geo = (ms["p25"] >= P25_MIN and ms["p75"] <= P75_MAX
               and ms["frac_mid"] >= MID_FRAC_MIN)
        rows.append({"x_cm": w["x_cm"], "y_cm": w["y_cm"], "z_cm": w["z_cm"],
                     "yaw": w["yaw"], "marched": ms, "geometry_ok": geo,
                     "all_four": bool(geo and (ms["meadow_frac"] or 0)
                                      >= MEADOW_FRAC_MIN)})
    geo_ok = [r for r in rows if r["geometry_ok"]]
    geo_ok.sort(key=lambda r: -(r["marched"]["meadow_frac"] or 0))
    out = {"_what": "ground station pick, ranked by the BINDING constraint",
           "marched": len(rows), "geometry_ok": len(geo_ok),
           "all_four": sum(1 for r in rows if r["all_four"]),
           "thresholds": {"p25_min": P25_MIN, "p75_max": P75_MAX,
                          "frac_mid_min": MID_FRAC_MIN,
                          "meadow_frac_min": MEADOW_FRAC_MIN},
           "best_by_meadow": geo_ok[:15]}
    print("marched %d, geometry ok %d, all four %d"
          % (out["marched"], out["geometry_ok"], out["all_four"]))
    print("\nBEST BY MEADOW, among views that already clear the geometry")
    print("%-28s %5s %7s %7s %7s %7s %8s %s"
          % ("x,y,z cm", "yaw", "p25", "p50", "p75", "frac", "meadow", "all4"))
    for r in geo_ok[:15]:
        s = r["marched"]
        print("%-28s %5.0f %7.1f %7.1f %7.1f %7.3f %8.3f %s"
              % ("%.0f,%.0f,%.0f" % (r["x_cm"], r["y_cm"], r["z_cm"]),
                 r["yaw"], s["p25"], s["p50"], s["p75"], s["frac_mid"],
                 s["meadow_frac"] or 0.0, r["all_four"]))
    if out["all_four"] == 0 and geo_ok:
        print("\nNOTHING CLEARS MEADOW >= %.2f. Best is %.3f. The geometry is "
              "satisfiable; the MEADOW REQUIREMENT is what this world does "
              "not offer at 50-300 m alongside it."
              % (MEADOW_FRAC_MIN, geo_ok[0]["marched"]["meadow_frac"] or 0))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
