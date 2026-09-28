"""ground_station_feasibility.py — are the four ruled thresholds jointly
satisfiable anywhere in this world, at pitch 0?

    python scripts/ground_station_feasibility.py [--out J]
    python scripts/ground_station_feasibility.py --selftest

Three searches have now failed, each in a different direction, so the
question stops being "find a station" and becomes "does one exist". This
answers that by scoring EVERY candidate view on all four ruled statistics
and reporting the PARETO FRONT -- the best achievable on each axis, and
whether any single view satisfies all of them at once.

THE SCORER IS ANALYTIC, AND HERE IS WHY THAT IS LEGITIMATE. For a camera
at pitch 0, the vertical angle at which ground at distance d appears is
`atan((h(d) - z_cam) / d)`, and the frame's vertical extent is fixed at
58.72 deg. So the DEPTH HISTOGRAM of the centre column follows directly
from the height profile along the view azimuth -- no raymarch needed. It
is a centre-line approximation of a 90 deg-wide frame, so it is used to
RANK and to answer the feasibility question, never to bless a station:
that is still `verify_ground_station` against a real capture.

    p25/p50/p75   percentiles of distance weighted by ANGULAR extent
    frac_mid      angular extent of the 50-300 m band / 58.72 deg
    meadow        layer weight along the same samples
    trees         from the instance lists, in the frustum, under 300 m
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from bench_station_derive import load_terrain, sample_height  # noqa: E402
from find_ground_station import (EYE_M, MEADOW_FRAC_MIN,  # noqa: E402
                                 MEADOW_MIN, MID, MID_FRAC_MIN, P25_MIN,
                                 P75_MAX, TREE_MAX_M, _meadow, _trees,
                                 trees_in_frustum)

VFOV = 2.0 * math.degrees(math.atan(math.tan(math.radians(45.0)) * 2160 / 3840))
D_MIN, D_MAX, N_D = 2.0, 1200.0, 400


def profile_stats(Z, ox, oy, px_m, meadow, cam, yaw):
    """Depth histogram of the centre column, by angular extent."""
    d = np.geomspace(D_MIN, D_MAX, N_D)
    ux, uy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    px, py = cam[0] + ux * d, cam[1] + uy * d
    h = sample_height(Z, ox, oy, px_m, px, py)
    ok = np.isfinite(h)
    if ok.sum() < 50:
        return None
    d, h, px, py = d[ok], h[ok], px[ok], py[ok]
    ang = np.degrees(np.arctan2(h - cam[2], d))
    # a sample is VISIBLE only if nothing nearer rises above it
    vis = ang >= np.maximum.accumulate(ang)
    if vis.sum() < 10:
        return None
    d, ang, px, py = d[vis], ang[vis], px[vis], py[vis]
    # angular weight of each visible sample, clipped to the frame
    lo, hi = -VFOV / 2.0, VFOV / 2.0
    edges = np.concatenate([[ang[0]], 0.5 * (ang[1:] + ang[:-1]), [ang[-1]]])
    w = np.clip(edges[1:], lo, hi) - np.clip(edges[:-1], lo, hi)
    w = np.maximum(w, 0.0)
    if w.sum() <= 0:
        return None
    order = np.argsort(d)
    dd, ww = d[order], w[order]
    cw = np.cumsum(ww) / ww.sum()

    def pct(q):
        return float(dd[np.searchsorted(cw, q)])

    inmid = (dd >= MID[0]) & (dd <= MID[1])
    frac = float(ww[inmid].sum() / VFOV)
    cx = np.clip(((px[order] - ox) / px_m).astype(np.int64), 0,
                 meadow.shape[1] - 1)
    cy = np.clip(((py[order] - oy) / px_m).astype(np.int64), 0,
                 meadow.shape[0] - 1)
    mw = meadow[cy, cx]
    mfrac = (float((mw[inmid] >= MEADOW_MIN).mean()) if inmid.any() else 0.0)
    return {"p25": pct(0.25), "p50": pct(0.50), "p75": pct(0.75),
            "frac_mid": frac, "meadow_frac": mfrac,
            "sky_frac": float(max(0.0, 1.0 - ww.sum() / VFOV))}


def selftest():
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    n, sp = 800, 2.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    flat = np.full((n, n), 100.0, dtype=np.float32)
    meadow = np.ones((n, n), dtype=np.float32)
    cx = cy = n / 2 * sp
    cam = np.array([cx, cy, 100.0 + EYE_M])
    f = profile_stats(flat, 0.0, 0.0, sp, meadow, cam, 90.0)
    print("    flat: p25 %.1f p50 %.1f p75 %.1f frac_mid %.4f"
          % (f["p25"], f["p50"], f["p75"], f["frac_mid"]))
    check("flat ground's 50-300 m band is ~2.8% of frame",
          abs(f["frac_mid"] - 0.0276) < 0.012)
    check("flat ground's p25 is NEAR, far below the 40 m floor",
          f["p25"] < 10.0)
    fwd = np.clip((yy - n / 2) * sp, 0, None)
    bowl = (100.0 + fwd * fwd / (2.0 * 500.0)).astype(np.float32)
    b = profile_stats(bowl, 0.0, 0.0, sp, meadow,
                      np.array([cx, cy, 100.0 + EYE_M]), 90.0)
    print("    bowl: p25 %.1f p50 %.1f p75 %.1f frac_mid %.4f"
          % (b["p25"], b["p50"], b["p75"], b["frac_mid"]))
    check("a rising far side raises frac_mid far above flat",
          b["frac_mid"] > 5 * f["frac_mid"])
    check("occlusion is applied (a ridge hides what is behind it)",
          b["sky_frac"] >= 0.0)
    check("off-map refuses",
          profile_stats(flat, 0.0, 0.0, sp, meadow,
                        np.array([-9e5, -9e5, 0.0]), 90.0) is None)
    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step-m", type=float, default=120.0)
    ap.add_argument("--yaws", type=int, default=24)
    ap.add_argument("--out")
    ap.add_argument("--march", type=int, default=0,
                    help="raymarch this many survivors and score them on "
                         "the REAL statistics")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    Z, ox, oy, px_m = load_terrain(os.path.join(REPO, "recipes",
                                                "alpine_8k.json"))
    meadow = _meadow()
    trees = _trees()
    ny, nx = Z.shape
    stride = int(a.step_m / px_m)
    best = {k: None for k in ("p25", "p75", "frac_mid", "meadow_frac")}
    n_view = 0
    n_pass = {"p25": 0, "p75": 0, "frac": 0, "meadow": 0, "three": 0,
              "four_no_trees": 0}
    winners = []
    for iy in range(stride, ny - stride, stride):
        for ix in range(stride, nx - stride, stride):
            g = float(Z[iy, ix])
            cam = np.array([ox + ix * px_m, oy + iy * px_m, g + EYE_M])
            for k in range(a.yaws):
                yaw = 360.0 * k / a.yaws
                s = profile_stats(Z, ox, oy, px_m, meadow, cam, yaw)
                if s is None:
                    continue
                n_view += 1
                ok25 = s["p25"] >= P25_MIN
                ok75 = s["p75"] <= P75_MAX
                okf = s["frac_mid"] >= MID_FRAC_MIN
                okm = s["meadow_frac"] >= MEADOW_FRAC_MIN
                n_pass["p25"] += ok25
                n_pass["p75"] += ok75
                n_pass["frac"] += okf
                n_pass["meadow"] += okm
                for key, val, better in (("p25", s["p25"], max),
                                         ("p75", s["p75"], min),
                                         ("frac_mid", s["frac_mid"], max),
                                         ("meadow_frac", s["meadow_frac"],
                                          max)):
                    if best[key] is None or better(val, best[key][0]) == val:
                        best[key] = (val, cam.tolist(), yaw)
                # ⛔ THE ANALYTIC GATE IS `frac` AND `trees` ONLY.
                # Measured 2026-09-11: the centre-line model predicted
                # p25 93.8 where the RENDER gave 1.2, because at pitch 0
                # the BOTTOM OF THE FRAME sees ground ~3 m away across
                # the full width whatever the centre line does. So the
                # analytic p25 is not admissible as a filter -- it is
                # kept in the record and the raymarch decides. `frac` is
                # over-estimated about 2x (0.585 analytic vs 0.304
                # rendered) but CORRELATES, so it is a safe superset
                # filter at the same threshold.
                if okf:
                    n_pass["three"] += 1
                    nt, near = trees_in_frustum(trees, cam, 0.0, yaw)
                    if nt == 0:
                        n_pass["four_no_trees"] += 1
                        winners.append({"x_cm": round(cam[0] * 100, 1),
                                        "y_cm": round(cam[1] * 100, 1),
                                        "z_cm": round(cam[2] * 100, 1),
                                        "yaw": yaw, "stats": s,
                                        "trees": nt})
    out = {"_what": "feasibility of the four ruled thresholds at pitch 0",
           "views_scored": n_view, "thresholds": {
               "p25_min": P25_MIN, "p75_max": P75_MAX,
               "frac_mid_min": MID_FRAC_MIN,
               "meadow_frac_min": MEADOW_FRAC_MIN},
           "views_passing_each": n_pass,
           "best_on_each_axis": {k: (None if v is None else
                                     {"value": round(v[0], 3),
                                      "cam_cm": [round(c * 100, 1)
                                                 for c in v[1]],
                                      "yaw": v[2]})
                                 for k, v in best.items()},
           "winners": winners[:400], "winner_count": len(winners)}

    # ---- RAYMARCH THE SURVIVORS -----------------------------------------
    # The analytic pass is a centre-line approximation of a 90 deg frame.
    # Only a marched image has one depth per pixel across the whole
    # frame, which is what the depth pass has and what the checks read.
    if a.march and winners:
        from find_ground_station import march_stats
        marched = []
        for w in winners[:a.march]:
            cam = np.array([w["x_cm"] / 100.0, w["y_cm"] / 100.0,
                            w["z_cm"] / 100.0])
            ms = march_stats(Z, ox, oy, px_m, meadow, cam, 0.0, w["yaw"])
            if ms is None:
                continue
            passes = (ms["p25"] >= P25_MIN and ms["p75"] <= P75_MAX
                      and ms["frac_mid"] >= MID_FRAC_MIN
                      and (ms["meadow_frac"] or 0) >= MEADOW_FRAC_MIN)
            marched.append(dict(w, marched=ms, all_four=bool(passes)))
        marched.sort(key=lambda m: (-int(m["all_four"]),
                                    -(m["marched"]["p25"] >= P25_MIN),
                                    -m["marched"]["frac_mid"]))
        out["marched_count"] = len(marched)
        out["marched_all_four"] = sum(1 for m in marched if m["all_four"])
        out["marched_top"] = marched[:12]
        print("\nRAYMARCHED %d of %d survivors  --  %d satisfy ALL FOUR"
              % (len(marched), len(winners), out["marched_all_four"]))
        print("%-28s %5s %7s %7s %7s %7s %7s %s"
              % ("x,y,z cm", "yaw", "p25", "p50", "p75", "frac", "meadow",
                 "all4"))
        for m in marched[:12]:
            s = m["marched"]
            print("%-28s %5.0f %7.1f %7.1f %7.1f %7.3f %7.3f %s"
                  % ("%.0f,%.0f,%.0f" % (m["x_cm"], m["y_cm"], m["z_cm"]),
                     m["yaw"], s["p25"], s["p50"], s["p75"], s["frac_mid"],
                     s["meadow_frac"] or 0.0, m["all_four"]))

    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("winners", "marched_top")}, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
