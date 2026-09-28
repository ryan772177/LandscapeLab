"""tiling_score.py — measure whether a rendered ground surface REPEATS
visibly. The eye is a pattern detector tuned to 1-8 cycles/degree; a tiled
texture whose repeat survives in that band with contrast above threshold
reads as a grid however good the texture is.

Method
  1. take a crop of the frame that is ground only (bbox given by the caller;
     from a station this is a known region, e.g. the lower third excluding
     the grey card), convert to linear luma
  2. remove the low-frequency lighting gradient (wide blur subtracted), so
     shadows and slope shading do not count as a "repeat"
  3. 2-D autocorrelation (FFT); look for the strongest off-centre peak within
     a period window (pixels) supplied by the caller from texel_budget: the
     tile's expected on-screen period at that crop's distance, +-40%
  4. report the peak's normalised height (0 = no repeat, 1 = perfect tile)
     and its equivalent Michelson contrast (2*peak_std/mean), against the
     CSF threshold for that period's angular frequency

The verdict is comparative: run before/after macro variation or hex-tiling
and the number must fall under the threshold that texel_budget reports for
that distance. Self-test builds a synthetic tiled crop and a noise crop and
checks the score separates them.

Usage
  python tiling_score.py frame.png --bbox x0 y0 x1 y1 --period-px 180 \
      [--threshold 0.006] [--out score.json]
  python tiling_score.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from PIL import Image


def luma_linear(rgb8):
    s = rgb8.astype(np.float64) / 255.0
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def box_blur(a, r):
    k = 2 * r + 1
    c = np.cumsum(np.pad(a, ((r, r), (0, 0)), mode="edge"), axis=0)
    a = (c[k - 1:] - np.vstack([np.zeros((1, a.shape[1])), c[:-k]])) / k
    c = np.cumsum(np.pad(a, ((0, 0), (r, r)), mode="edge"), axis=1)
    return (c[:, k - 1:] - np.hstack([np.zeros((a.shape[0], 1)), c[:, :-k]])) / k


def score(crop_luma, period_px, tol=0.4):
    L = crop_luma
    hi = L - box_blur(L, max(4, int(period_px)))        # remove lighting gradient
    hi = hi - hi.mean()
    if hi.std() < 1e-6:
        return {"peak": 0.0, "michelson": 0.0, "period_found_px": None}
    F = np.fft.fft2(hi)
    ac = np.fft.ifft2(F * np.conj(F)).real
    ac = np.fft.fftshift(ac) / ac.max()
    h, w = ac.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    lo, hi_r = period_px * (1 - tol), period_px * (1 + tol)
    ring = (r >= lo) & (r <= hi_r)
    if not ring.any():
        return {"peak": 0.0, "michelson": 0.0, "period_found_px": None}
    peak = float(ac[ring].max())
    idx = np.unravel_index(np.argmax(np.where(ring, ac, -1)), ac.shape)
    found = float(np.sqrt((idx[0] - cy) ** 2 + (idx[1] - cx) ** 2))
    # the repeating component's contrast: fraction of variance that is periodic,
    # expressed as Michelson relative to the crop's mean luminance
    periodic_std = hi.std() * np.sqrt(max(peak, 0.0))
    mich = float(2.0 * periodic_std / max(L.mean(), 1e-6))
    return {"peak": round(peak, 4), "michelson": round(mich, 4), "period_found_px": round(found, 1)}


def selftest():
    rng = np.random.default_rng(5)
    H = W = 512
    yy, xx = np.mgrid[0:H, 0:W]
    tile = rng.uniform(0.3, 0.7, (64, 64))
    tiled = np.tile(tile, (8, 8))                      # perfect 64-px repeat
    noise = rng.uniform(0.3, 0.7, (H, W))
    for _ in range(2):
        noise = (noise + np.roll(noise, 1, 0) + np.roll(noise, 1, 1)) / 3
    grad = 0.2 * (yy / H)                                # a lighting gradient on both
    a = score(tiled + grad, 64)
    b = score(noise + grad, 64)
    ok = a["peak"] > 0.6 and b["peak"] < 0.25 and abs(a["period_found_px"] - 64) < 6
    print("selftest:", "PASS" if ok else "FAIL", a, b)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frame", nargs="?")
    ap.add_argument("--bbox", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--period-px", type=float)
    ap.add_argument("--threshold", type=float, default=None, help="CSF threshold from texel_budget for this distance")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.frame and a.bbox and a.period_px):
        print("need frame, --bbox and --period-px"); return 2
    im = np.asarray(Image.open(a.frame).convert("RGB"))
    x0, y0, x1, y1 = a.bbox
    L = luma_linear(im[y0:y1, x0:x1])
    rep = score(L, a.period_px)
    rep.update({"frame": a.frame, "bbox": a.bbox, "period_px_expected": a.period_px})
    if a.threshold is not None:
        rep["threshold"] = a.threshold
        rep["verdict"] = "PASS" if rep["michelson"] < a.threshold else "FAIL: repeat visible"
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
