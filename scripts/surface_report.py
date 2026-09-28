"""surface_report.py — Brief 3 Task 3's tiling and albedo table.

    python scripts/surface_report.py --frames <dir> [--out J]
    python scripts/surface_report.py --selftest

TWO MEASURES, both on the recaptured stations:

  TILING   per depth bin, `tiling_score`'s autocorrelation peak and its
           Michelson contrast, against the CSF threshold `texel_budget`
           reports for that distance. The on-screen period is DERIVED:
           a tile of T metres at distance d subtends T/d rad, so
           period_px = px_per_deg * (180/pi) * T / d.
  ALBEDO   low-passed luma std/mean over the ground at the 1-4 m scale,
           the band BRIEF 3 sec 3.8 sets at 0.10-0.20.

DEPTH IS USED ONLY AS A DISTANCE, WHICH IS THE ONE THING THE PASS IS FOR.
R-DEPTHBIN's pass is 8-bit LOG depth (5.6% per LSB), so it bins distance
and nothing else -- no positions, no normals (LESSONS 2026-09-11c). The
ground band for a bin is therefore chosen as the ROWS whose median depth
falls in the bin, not by reconstructing geometry.

THE GROUND MASK is depth-only too: not sky, inside the bin, and outside
the grey card's rect. The brief says "ground mask from depth+normal";
the normal half is NOT AVAILABLE from this pass and is not faked -- a
band of rows low in a ground-level frame is ground, and where it is not
(a distant ridge face) it is still ground, just steeper.
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
from haze_metrics import CEILING_M, decode_depth_m, srgb_to_linear  # noqa
from tiling_score import box_blur, score  # noqa

BINS = [(30.0, 100.0), (100.0, 300.0)]
ALBEDO_BAND = (0.10, 0.20)
MIN_CROP = 160                  # px; below this the autocorrelation is noise


def csf_threshold(cpd):
    """Michelson threshold at a spatial frequency, from texel_budget's own
    curve so the two tools cannot drift apart."""
    from texel_budget import csf_threshold_michelson
    return csf_threshold_michelson(cpd)


def ground_rows(depth, lo_m, hi_m, sky):
    """Rows whose MEDIAN in-bin depth sits inside [lo, hi]."""
    rows = []
    for y in range(depth.shape[0]):
        d = depth[y][~sky[y]]
        if d.size < depth.shape[1] * 0.25:
            continue
        med = float(np.median(d))
        if lo_m <= med <= hi_m:
            rows.append(y)
    return rows


def measure_station(beauty_png, depth_png, tile_m, px_per_deg, card_rect=None):
    rgb = np.asarray(Image.open(beauty_png).convert("RGB"))
    depth = decode_depth_m(depth_png)
    if rgb.shape[:2] != depth.shape:
        return {"error": "beauty %s and depth %s differ in shape"
                         % (rgb.shape[:2], depth.shape)}
    lin = srgb_to_linear(rgb.astype(np.float64) / 255.0)
    lum = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    sky = depth > CEILING_M * 0.97
    if card_rect:
        x0, y0, x1, y1 = card_rect
        sky[max(0, y0 - 20):y1 + 20, max(0, x0 - 20):x1 + 20] = True

    out = {"sky_fraction": round(float(sky.mean()), 4), "bins": []}
    for lo, hi in BINS:
        rows = ground_rows(depth, lo, hi, sky)
        row = {"bin_m": [lo, hi], "rows": len(rows)}
        if len(rows) < MIN_CROP:
            row["verdict"] = "NO BAND"
            row["why"] = ("only %d rows have median depth in this bin; "
                          "this station does not see ground there"
                          % len(rows))
            out["bins"].append(row)
            continue
        # THE LONGEST CONTIGUOUS RUN, not first-to-last. Qualifying rows
        # are not contiguous (foliage and occluders interrupt them), and
        # spanning first-to-last silently swept in rows from OTHER bins:
        # measured 2026-09-11, the 30-100 m band came back with a
        # representative distance of 19.3 m and the 100-300 m band with
        # 6.6 m. A band whose own distance is outside its bin is not a
        # measurement of that bin.
        runs, cur = [], [rows[0]]
        for y in rows[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                runs.append(cur)
                cur = [y]
        runs.append(cur)
        best_run = max(runs, key=len)
        row["longest_contiguous_rows"] = len(best_run)
        if len(best_run) < MIN_CROP:
            row["verdict"] = "NO BAND"
            row["why"] = ("%d rows are in the bin but the longest "
                          "CONTIGUOUS run is %d (< %d) -- the band is "
                          "broken up by occluders"
                          % (len(rows), len(best_run), MIN_CROP))
            out["bins"].append(row)
            continue
        y0, y1 = best_run[0], best_run[-1] + 1
        # COLUMNS ARE CHOSEN BY IN-BIN FRACTION, NOT BY ABSENCE OF SKY.
        # Measured 2026-09-11: selecting the widest column run that never
        # contains sky picks whatever fills the frame vertically -- a near
        # trunk or a close slope -- and those columns were 0.0% inside the
        # bin. "No sky" is not "at this distance".
        strip_d = depth[y0:y1, :]
        strip_sky = sky[y0:y1, :]
        colfrac = (((strip_d >= lo) & (strip_d <= hi) & ~strip_sky)
                   .mean(axis=0))
        colok = colfrac >= 0.7
        best, cur, start = (0, 0), 0, 0
        for x, ok in enumerate(colok):
            if ok:
                if cur == 0:
                    start = x
                cur += 1
                if cur > best[1] - best[0]:
                    best = (start, x + 1)
            else:
                cur = 0
        x0, x1 = best
        if x1 - x0 < MIN_CROP:
            row["verdict"] = "NO BAND"
            row["why"] = ("widest column run at >=70%% in-bin is %d px"
                          % (x1 - x0))
            out["bins"].append(row)
            continue
        crop = lum[y0:y1, x0:x1]
        sub = depth[y0:y1, x0:x1]
        inbin = (sub >= lo) & (sub <= hi)
        if inbin.mean() < 0.5:
            row["verdict"] = "NO BAND"
            row["why"] = ("only %.1f%% of the chosen crop is actually in "
                          "[%.0f, %.0f] m -- the crop is not the bin"
                          % (100 * inbin.mean(), lo, hi))
            row["crop_median_depth_m"] = round(float(np.median(sub)), 1)
            out["bins"].append(row)
            continue
        d_rep = float(np.median(sub[inbin]))
        row["crop_fraction_in_bin"] = round(float(inbin.mean()), 4)
        period_px = px_per_deg * (180.0 / math.pi) * tile_m / d_rep
        cpd = d_rep / (tile_m * (180.0 / math.pi))
        thr = csf_threshold(cpd)
        s = score(crop, period_px)
        row.update({"bbox": [int(x0), int(y0), int(x1), int(y1)],
                    "representative_distance_m": round(d_rep, 1),
                    "tile_period_px": round(period_px, 1),
                    "repeat_cpd": round(cpd, 3),
                    "csf_threshold_michelson": round(thr, 4),
                    "peak": s["peak"], "michelson": s["michelson"],
                    "period_found_px": s["period_found_px"]})

        # IS THE PEAK ACTUALLY THE TILE? `score` searches a +-40% ring
        # around the expected period and returns the strongest point in
        # it. If that point sits ON the ring's edge, the maximum is the
        # WINDOW's boundary, not a feature -- the same shape as the p90
        # gradient that returned sqrt(2)/2 for two different blends
        # (R-LAYERS REJECTED). Measured 2026-09-11: near_ground found
        # 205.4 px against a 205.1 floor, vista 60.0 against 59.8. Both
        # pinned, and both were about to be reported as FAIL.
        found = s["period_found_px"]
        w_lo, w_hi = period_px * 0.6, period_px * 1.4
        pinned = found is not None and (found <= w_lo * 1.02
                                        or found >= w_hi * 0.98)
        row["search_window_px"] = [round(w_lo, 1), round(w_hi, 1)]
        if pinned:
            row["verdict"] = "NO VERDICT"
            row["why"] = (
                "the autocorrelation peak sits at the search window's edge "
                "(found %.1f px in [%.1f, %.1f]), so it is the window's "
                "boundary and not the tile's period -- there is no "
                "periodic structure at %.1f px to measure. The michelson "
                "figure beside it is 2*std*sqrt(peak)/mean and is carried "
                "by the crop's own contrast (foliage, shadow), NOT by a "
                "repeat: peak %.4f against ~1.0 for a genuinely tiled crop "
                "and ~0.01 for noise."
                % (found, w_lo, w_hi, period_px, s["peak"]))
        else:
            row["verdict"] = "PASS" if s["michelson"] < thr else "FAIL"
        out["bins"].append(row)

    # ---- albedo variation, 1-4 m scale on the nearest ground ------------
    near = (~sky) & (depth > 2.0) & (depth < 30.0)
    if near.sum() < 50000:
        out["albedo"] = {"verdict": "NO BAND",
                         "why": "only %d near-ground px" % int(near.sum())}
        return out
    ys, xs = np.where(near)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    patch = lum[y0:y1, x0:x1]
    pmask = near[y0:y1, x0:x1]
    d_rep = float(np.median(depth[near]))
    # 1-4 m at d_rep, in pixels: low-pass at the 1 m scale, high-pass at 4 m
    px_per_m = px_per_deg * (180.0 / math.pi) / d_rep
    r_lo = max(1, int(round(px_per_m * 1.0 / 2)))
    r_hi = max(r_lo + 1, int(round(px_per_m * 4.0 / 2)))
    lowp = box_blur(box_blur(patch, r_lo).T, r_lo).T
    verylow = box_blur(box_blur(patch, r_hi).T, r_hi).T
    band = lowp - verylow + float(np.mean(patch[pmask]))
    vals = band[pmask]
    mean = float(np.mean(vals))
    out["albedo"] = {"scale_m": [1.0, 4.0],
                     "representative_distance_m": round(d_rep, 1),
                     "px_per_m": round(px_per_m, 1),
                     "radii_px": [r_lo, r_hi],
                     "px": int(pmask.sum()),
                     "std_over_mean": round(float(np.std(vals) / mean), 4)
                     if mean > 1e-6 else None,
                     "brief_band_for_reference": list(ALBEDO_BAND),
                     "verdict": "NO VERDICT",
                     "why": (
                         "THE DENOMINATOR IS NOT THE BRIEF'S. BRIEF 3 sec 3.8 "
                         "sets 0.10-0.20 for the MEADOW BAND -- ground masked "
                         "to the meadow layer. This number is over ALL near "
                         "ground the depth pass admits, which at near_ground "
                         "is mostly grass cards, blueberry and their shadows, "
                         "and those carry far more variation than the surface "
                         "underneath. Scoring it against the meadow band "
                         "would compare two different populations. The meadow "
                         "mask needs the layer weights FORWARD-PROJECTED with "
                         "a z-buffer from an oblique camera, with foliage "
                         "rejected by comparing projected terrain depth "
                         "against the pass -- not built here.")}
    return out


def selftest():
    """1 a tiled crop scores ABOVE a flat one; 2 an untiled crop passes
    where a tiled one fails at the same threshold; 3 malformed refuses."""
    fails = []

    def check(name, cond):
        print("  %-56s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    n = 512
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    tiled = 0.4 + 0.08 * np.sin(2 * math.pi * xx / 64.0) * np.sin(
        2 * math.pi * yy / 64.0)
    rng = np.random.default_rng(3)
    flat = 0.4 + 0.002 * rng.standard_normal((n, n))
    st, sf = score(tiled, 64.0), score(flat, 64.0)
    print("    tiled %s" % st)
    print("    flat  %s" % sf)
    check("a tiled crop scores far above a flat one",
          st["michelson"] > 10 * sf["michelson"])
    thr = csf_threshold(4.0)
    check("at the CSF threshold the tiled crop FAILS", st["michelson"] > thr)
    check("at the CSF threshold the flat crop PASSES", sf["michelson"] < thr)
    check("threshold comes from texel_budget's curve", thr > 0)

    # direction 3: malformed input REFUSES rather than scoring
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "b.png")
        dp = os.path.join(td, "d.png")
        Image.fromarray(np.uint8(np.full((64, 64, 3), 120))).save(bp)
        Image.fromarray(np.uint8(np.full((32, 32, 3), 10))).save(dp)
        r = measure_station(bp, dp, 5.03, 42.67)
        check("beauty/depth shape mismatch refuses", "error" in r)
        Image.fromarray(np.uint8(np.full((64, 64, 3), 10))).save(dp)
        r2 = measure_station(bp, dp, 5.03, 42.67)
        check("a frame too small for any band reports NO BAND, not a score",
              all(b.get("verdict") == "NO BAND" for b in r2.get("bins", []))
              and r2.get("albedo", {}).get("verdict") == "NO BAND")
    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--frames")
    ap.add_argument("--stations", nargs="+",
                    default=["near_ground", "mid_slope", "vista"])
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        sys.exit("REFUSE: --frames is required")

    rec = json.load(open(a.recipe, encoding="utf-8"))
    tiles = sorted({float(l["tiling_m"]) for l in rec["material"]["layers"]})
    if len(tiles) != 1:
        print("NOTE: layers carry %d different tile sizes %s; the period is "
              "derived per-layer and this report uses the first."
              % (len(tiles), tiles))
    tile_m = tiles[0]
    px_per_deg = 3840.0 / 90.0
    regions = {}
    rp = os.path.join(REPO, "_verify", "bench", "greycard_regions.json")
    if os.path.isfile(rp):
        regions = json.load(open(rp, encoding="utf-8"))

    out = {"_what": "Brief 3 Task 3 tiling + albedo table",
           "tile_m": tile_m, "px_per_deg": round(px_per_deg, 2),
           "frames": a.frames, "stations": {}}
    for st in a.stations:
        b = os.path.join(a.frames, "%s.png" % st)
        d = os.path.join(a.frames, "%sFinalImageSceneDepth.png" % st)
        if not (os.path.isfile(b) and os.path.isfile(d)):
            out["stations"][st] = {"error": "missing beauty or depth frame"}
            continue
        rect = None
        v = regions.get(st)
        if isinstance(v, dict) and v.get("rect_px"):
            rect = [int(x) for x in v["rect_px"]]
        out["stations"][st] = measure_station(b, d, tile_m, px_per_deg, rect)

    print("tile %.2f m, px/deg %.2f" % (tile_m, px_per_deg))
    print("%-12s %-12s %7s %9s %10s %10s %7s"
          % ("station", "bin m", "rows", "dist m", "michelson", "threshold",
             "verdict"))
    for st, r in out["stations"].items():
        if "error" in r:
            print("%-12s %s" % (st, r["error"]))
            continue
        for b in r["bins"]:
            if b.get("verdict") == "NO VERDICT":
                print("%-12s %-12s %7d %9.1f %10.4f %10.4f %7s"
                      % (st, "%.0f-%.0f" % tuple(b["bin_m"]), b["rows"],
                         b["representative_distance_m"], b["michelson"],
                         b["csf_threshold_michelson"], "NO VERDICT"))
                print("%-12s   peak %.4f, period found %.1f px in window %s "
                      "-- PINNED AT THE EDGE, not the tile"
                      % ("", b["peak"], b["period_found_px"],
                         b["search_window_px"]))
            elif b.get("verdict") == "NO BAND":
                print("%-12s %-12s %7d   %s"
                      % (st, "%.0f-%.0f" % tuple(b["bin_m"]), b["rows"],
                         b["why"]))
            else:
                print("%-12s %-12s %7d %9.1f %10.4f %10.4f %7s"
                      % (st, "%.0f-%.0f" % tuple(b["bin_m"]), b["rows"],
                         b["representative_distance_m"], b["michelson"],
                         b["csf_threshold_michelson"], b["verdict"]))
        al = r.get("albedo", {})
        print("%-12s albedo 1-4 m: %s  (brief band %s)  %s"
              % (st, al.get("std_over_mean", al.get("why")),
                 al.get("brief_band_for_reference"),
                 al.get("verdict", "")))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
