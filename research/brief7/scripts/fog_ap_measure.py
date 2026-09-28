"""fog_ap_measure.py -- per-band foliage saturation / hue / luminance on a still.

Brief 7 P2 step 0 (aerial perspective, blue-shift ladder). One still, three
named crops (near ~40 m, mid ~300 m, far ~1000 m), one number set per crop.

THE MASK IS BY REGION + LUMINANCE, NOT BY COLOUR. The hypothesis under test is
that distant foliage shifts hue toward BLUE; a green-dominant mask (G >= B)
would DROP the very pixels that shifted and report "hue unchanged" as a
mask artefact. So each crop is a rectangle the operator chose from the
calibration frame to contain only trees, and the mask inside it keeps pixels
with luminance in [LUM_LO, LUM_HI] to reject sky / snow / blown highlights.
The kept-pixel COUNT is printed beside every number (rule 13) and a crop
with fewer than MIN_PIXELS kept REFUSES rather than reporting.

saturation = (max-min)/max  (HSV S), luminance = 0.299R+0.587G+0.114B,
hue = circular mean of HSV hue in degrees (0=red, 60=yellow, 120=green,
240=blue), so "toward blue" = hue INCREASES from the ~50-65 deg green-yellow
the far band read on 2026-09-25.

Usage:
    python research/brief7/scripts/fog_ap_measure.py --crops crops.json \
        --still path/to/still.png [--still ...] [--json out.json]

crops.json: {"<camera>": {"near":[x0,y0,x1,y1], "mid":[...], "far":[...]}}
The camera key is matched against the still's basename prefix.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

LUM_LO = 8.0
LUM_HI = 170.0
MIN_PIXELS = 400


def band_stats(rgb: np.ndarray, lum_hi: float = LUM_HI) -> dict:
    r = rgb[..., 0].astype(np.float64)
    g = rgb[..., 1].astype(np.float64)
    b = rgb[..., 2].astype(np.float64)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    keep = (lum >= LUM_LO) & (lum <= lum_hi)
    n = int(keep.sum())
    out = {"pixels_total": int(lum.size), "pixels_kept": n, "lum_hi": lum_hi}
    if n < MIN_PIXELS:
        out["refused"] = "only %d pixels kept (< %d)" % (n, MIN_PIXELS)
        return out
    r, g, b, lum = r[keep], g[keep], b[keep], lum[keep]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    # HSV hue per pixel
    d = np.maximum(mx - mn, 1e-9)
    h = np.zeros_like(mx)
    is_r = mx == r
    is_g = (mx == g) & ~is_r
    is_b = ~(is_r | is_g)
    h[is_r] = (60.0 * ((g - b) / d))[is_r] % 360.0
    h[is_g] = (60.0 * ((b - r) / d) + 120.0)[is_g]
    h[is_b] = (60.0 * ((r - g) / d) + 240.0)[is_b]
    # circular mean weighted by saturation (grey pixels carry no hue)
    w = sat
    ang = np.deg2rad(h)
    cx = float((np.cos(ang) * w).sum())
    cy = float((np.sin(ang) * w).sum())
    hue = float(np.rad2deg(np.arctan2(cy, cx)) % 360.0)
    out.update({
        "lum": round(float(lum.mean()), 2),
        "sat": round(float(sat.mean()), 4),
        "hue": round(hue, 1),
        "rgb": [round(float(r.mean()), 1), round(float(g.mean()), 1),
                round(float(b.mean()), 1)],
    })
    return out


def measure(still: str, crops: dict) -> dict:
    im = np.asarray(Image.open(still).convert("RGB"))
    res = {"still": os.path.basename(still), "size": [im.shape[1], im.shape[0]]}
    for name, box in crops.items():
        if name.startswith("_"):
            continue
        x0, y0, x1, y1 = [int(v) for v in box[:4]]
        lum_hi = float(box[4]) if len(box) > 4 else LUM_HI
        res[name] = band_stats(im[y0:y1, x0:x1], lum_hi)
        res[name]["box"] = [x0, y0, x1, y1]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops", required=True)
    ap.add_argument("--still", action="append", required=True)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    crops_all = json.load(open(a.crops))
    rows = []
    for st in a.still:
        base = os.path.basename(st)
        cam = next((k for k in crops_all if base.startswith(k)), None)
        if cam is None:
            print("REFUSED %s: no crop set whose key prefixes the basename" % base)
            return 1
        r = measure(st, crops_all[cam])
        r["camera"] = cam
        rows.append(r)
        cells = []
        for band in ("near", "mid", "far"):
            if band not in r:
                continue
            b = r[band]
            if "refused" in b:
                cells.append("%s REFUSED(%s)" % (band, b["refused"]))
            else:
                cells.append("%s sat %.3f hue %.1f lum %.1f n=%d" % (
                    band, b["sat"], b["hue"], b["lum"], b["pixels_kept"]))
        print("%-40s | %s" % (base, " | ".join(cells)))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rows, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
