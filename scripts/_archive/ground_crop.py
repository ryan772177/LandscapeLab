"""ground_crop.py — a 1:1 crop of one depth band, tone-mapped for viewing.

    python scripts/ground_crop.py --frames <dir> --station near_ground \
        --lo 50 --hi 100 --out _verify/bench/<date>/ground_crop_1to1.png

⭐ FOR A HUMAN TO LOOK AT, which is a different job from a metric. The
tiling instruments disagree about WHAT is periodic at ~1 m; the fastest
way to settle what it looks like is to put unscaled pixels in front of
someone.

1:1 MEANS 1:1. No resize, no fit-to-width. A resampled crop of a
periodicity question is worthless -- the resampler has its own kernel
and can both create and destroy the pattern being judged.

TONE-MAPPED ONLY FOR VIEWING. The EXR is scene-linear and this bench
sits ~14 stops down, so a straight write looks black. The transform is
a fixed exposure lift to put the frame's median at mid-grey, then sRGB
encode -- stated here and printed, so nobody reads a measurement off
this file. MEASUREMENTS COME FROM THE EXR.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import exr_card  # noqa: E402
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402

LUMA = (0.2126, 0.7152, 0.0722)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92,
                    1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--station", default="near_ground")
    ap.add_argument("--lo", type=float, default=50.0)
    ap.add_argument("--hi", type=float, default=100.0)
    ap.add_argument("--channel", default=None,
                    help="EXR channel group; default RGBA = FinalImage")
    ap.add_argument("--max-px", type=int, default=1600,
                    help="largest crop side to emit. The crop is CUT to "
                         "this, never RESIZED to it.")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    exr = os.path.join(a.frames, "%s.exr" % a.station)
    dep = os.path.join(a.frames, "%sFinalImageSceneDepth.png" % a.station)
    for p in (exr, dep):
        if not os.path.exists(p):
            print("REFUSE: missing %s" % p)
            return 1

    rgb = exr_card.read_rgb(exr, a.channel)
    depth = decode_depth_m(dep)
    if rgb.shape[:2] != depth.shape:
        print("REFUSE: beauty %s and depth %s differ"
              % (rgb.shape[:2], depth.shape))
        return 1

    band = (~(depth > CEILING_M * 0.97)) & (depth >= a.lo) & (depth <= a.hi)
    n = int(band.sum())
    if n < 10000:
        print("REFUSE: only %d px in the %g-%g m band" % (n, a.lo, a.hi))
        return 3
    # ⛔ THE CROP MUST STAY INSIDE THE BAND. A depth band is a horizontal
    # STRIP: its bounding box is nearly the whole frame, so centring on
    # the centroid and cutting a square overflowed it vertically and the
    # first attempt returned sky (depth 1.7 - 10485 m for a 50-100 m
    # request). Rows are chosen from the band's OWN extent, and the
    # fraction of crop pixels actually in the band is reported so this
    # cannot go unnoticed again.
    rows = np.where(band.any(axis=1))[0]
    cols = np.where(band.any(axis=0))[0]
    ry0, ry1 = int(rows.min()), int(rows.max()) + 1
    cx0, cx1 = int(cols.min()), int(cols.max()) + 1
    h_avail, w_avail = ry1 - ry0, cx1 - cx0
    ch = min(a.max_px, h_avail)
    cw = min(a.max_px, w_avail)
    # Centre on the row with the MOST band pixels -- the strip's spine.
    spine = int(np.argmax(band.sum(axis=1)))
    y0 = int(np.clip(spine - ch // 2, ry0, max(ry0, ry1 - ch)))
    x0 = int(np.clip((cx0 + cx1) // 2 - cw // 2, cx0, max(cx0, cx1 - cw)))
    y1, x1 = y0 + ch, x0 + cw
    crop = rgb[y0:y1, x0:x1, :]
    dcrop = depth[y0:y1, x0:x1]

    lum = crop @ np.array(LUMA)
    med = float(np.median(lum[lum > 0])) if (lum > 0).any() else 1.0
    gain = 0.18 / max(med, 1e-9)
    out = srgb(crop * gain)
    img = (np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8)

    from PIL import Image
    dst = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray(img, "RGB").save(dst)

    print("band %g-%g m: %d px in frame" % (a.lo, a.hi, n))
    print("crop rect [%d, %d, %d, %d]  ->  %d x %d  (1:1, CUT not resized)"
          % (x0, y0, x1, y1, x1 - x0, y1 - y0))
    inband = band[y0:y1, x0:x1]
    frac = float(inband.mean())
    dvals = dcrop[inband]
    print("depth inside the crop, BAND PIXELS ONLY: %.1f - %.1f m "
          "(median %.1f)" % (float(dvals.min()), float(dvals.max()),
                             float(np.median(dvals))))
    print("crop pixels actually in the %g-%g m band: %.1f%%"
          % (a.lo, a.hi, 100.0 * frac))
    if frac < 0.5:
        print("⚠ under half the crop is in the requested band; it is a "
              "strip and a square cut cannot avoid some out-of-band "
              "content. Judge the middle rows.")
    print("VIEWING TRANSFORM ONLY: linear x %.1f (median luma %.6f -> 0.18)"
          " then sRGB. Do not measure from this file." % (gain, med))
    print("wrote %s" % os.path.relpath(dst, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
