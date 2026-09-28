"""texel_budget.py — derive ground-texture tile size, texture resolution and
anti-tiling requirements from the camera and the eye, instead of typing
`tiling_m: 2.0`.

TWO QUESTIONS, BOTH ANGULAR

1. How many texels per metre does the ground need at the distances a player
   looks at it?  Render pixels per metre at distance d (level ground, camera
   at eye height h, looking down at the ground point) is approximately

       px_per_m(d) = ppd * (180/pi) / d            (ppd = width / hfov_deg)

   at 4K / 90 deg, ppd = 42.67 -> 2445/d px per metre.  For the texture to be
   sampled at ~1 texel per pixel (no visible blur, no aliasing beyond what
   mips handle) at the NEAREST distance that matters (a player looks at the
   ground ~2-4 m ahead), the texture needs that many texels per metre:
   at 3 m -> 815 texels/m -> a 4096 texture spans 5.0 m, a 2048 spans 2.5 m.
   Tile size is therefore DERIVED from texture resolution and the near
   viewing distance, not chosen for looks.

2. When does a tile repeat become visible?  The eye's contrast sensitivity
   peaks at ~3-5 cycles/degree.  A tile of T metres at distance d repeats
   with an angular period of  T * (180/pi) / d  degrees, i.e. a spatial
   frequency of  d / (T * 57.3)  cycles/degree.  Repetition is MOST visible
   when that frequency sits in the CSF peak band (1-8 cpd) and the repeat's
   residual contrast exceeds the threshold there (~0.5-1% Michelson at the
   peak, rising to ~3% at 0.5 cpd and ~10% at 20 cpd).  The tool reports, for
   a given tile size, the distance band in which the repeat is in the
   sensitive band, and the maximum residual contrast a tile may carry there
   before it reads as a pattern.  That number is the target for macro
   variation / anti-tiling strength, measured by tiling_score.py.

Usage
  python texel_budget.py --fov-h 90 --res 3840 2160 --eye-m 1.7 \
      --near-m 3 --tex 4096 --tile-m 2.0 [--out texel.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys


def csf_threshold_michelson(cpd):
    """Approximate Barten/Campbell-Robson contrast threshold vs spatial
    frequency (photopic, large field). Piecewise-log fit; good to ~2x."""
    pts = [(0.25, 0.10), (0.5, 0.03), (1.0, 0.012), (2.0, 0.006), (4.0, 0.005),
           (8.0, 0.008), (16.0, 0.03), (32.0, 0.15), (60.0, 1.0)]
    if cpd <= pts[0][0]:
        return pts[0][1]
    for (f0, c0), (f1, c1) in zip(pts, pts[1:]):
        if f0 <= cpd <= f1:
            t = (math.log(cpd) - math.log(f0)) / (math.log(f1) - math.log(f0))
            return math.exp(math.log(c0) + t * (math.log(c1) - math.log(c0)))
    return 1.0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fov-h", type=float, default=90.0)
    ap.add_argument("--res", type=int, nargs=2, default=[3840, 2160])
    ap.add_argument("--eye-m", type=float, default=1.7)
    ap.add_argument("--near-m", type=float, default=3.0, help="nearest ground distance a player attends to")
    ap.add_argument("--tex", type=int, default=4096, help="albedo texture resolution")
    ap.add_argument("--tile-m", type=float, default=None, help="current tile size to evaluate")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    ppd = a.res[0] / a.fov_h
    k = ppd * 180.0 / math.pi  # px per metre at 1 m
    rep = {"camera": {"fov_h": a.fov_h, "res": a.res, "px_per_deg": round(ppd, 2)},
           "px_per_m_at": {"%gm" % d: round(k / d, 1) for d in (1, 2, 3, 5, 10, 20, 50)}}
    need = k / a.near_m
    rep["texels_per_m_needed_at_near"] = round(need, 1)
    rep["derived_tile_m_for_tex"] = {str(t): round(t / need, 2) for t in (1024, 2048, 4096, 8192)}
    rep["_tile_note"] = ("tile_m = tex / texels_per_m_needed: the largest tile that still gives ~1 texel per "
                         "render pixel at the near distance. Larger tiles blur up close; smaller tiles repeat "
                         "more often at distance.")
    tiles = [a.tile_m] if a.tile_m else [rep["derived_tile_m_for_tex"][str(a.tex)]]
    rep["tiling_visibility"] = {}
    for T in tiles:
        rows = []
        for d in (2, 3, 5, 8, 12, 20, 30, 50, 80, 120, 200):
            cpd = d / (T * 57.2958)
            thr = csf_threshold_michelson(cpd)
            rows.append({"distance_m": d, "repeat_cpd": round(cpd, 3),
                         "threshold_contrast": round(thr, 4),
                         "in_sensitive_band": 1.0 <= cpd <= 8.0})
        worst = min(rows, key=lambda r: r["threshold_contrast"])
        rep["tiling_visibility"]["tile_%gm" % T] = {
            "rows": rows,
            "most_sensitive_distance_m": worst["distance_m"],
            "max_residual_repeat_contrast": worst["threshold_contrast"],
            "_read": ("At the most sensitive distance the tile's repeating component must carry less than "
                      "max_residual_repeat_contrast (Michelson) or it reads as a pattern. Measure it with "
                      "tiling_score.py on a ground crop; macro variation / hex-tiling must bring it under.")}
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
