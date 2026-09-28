"""sky_saturation.py — how saturated is the zenith band?

Brief 2 Task 4's acceptance: zenith-band saturation LOWER than the frame it is
compared against. More Mie scattering whitens the sky, most visibly at the
horizon but measurably at the zenith too, and a less saturated sky means a
less saturated sky-light capture, which is the lever for shadow tint once sky
intensity is already at 1.0.

    saturation = (max(RGB) - min(RGB)) / max(RGB)      linear, per pixel

reported as the MEDIAN over the zenith band. Median because a sun disc or a
cloud edge in frame would drag a mean and say nothing about the sky.

THE ZENITH BAND is the top `--band` fraction (default 0.15) of the SKY MASK,
not of the frame. Using frame rows would sample terrain at a station that
looks up a slope, and would sample different amounts of sky at each station.
The mask is measure_concept_look's, the same one every other Brief 2 metric
uses.

Also reports the horizon band (the bottom 15% of the sky mask) and the
zenith-to-horizon saturation RATIO, because that ratio is what "the sky is a
gradient" means numerically and it is the thing Mie actually changes: Mie
lifts the horizon toward white faster than the zenith.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_concept_look import sky_mask  # noqa: E402


def _lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def measure(path, band=0.15):
    srgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    lin = _lin(srgb)
    m, step = sky_mask(srgb)
    # sky_mask may be computed on a downsampled grid; bring the frame to it.
    if m.shape != lin.shape[:2]:
        h, w = m.shape
        ys = (np.linspace(0, lin.shape[0] - 1, h)).astype(int)
        xs = (np.linspace(0, lin.shape[1] - 1, w)).astype(int)
        lin = lin[np.ix_(ys, xs)]
    out = {"frame": path.replace("\\", "/"),
           "sky_fraction_of_frame": round(float(m.mean()), 5)}
    rows = np.nonzero(m.any(axis=1))[0]
    if rows.size == 0:
        out["_why"] = "no sky in frame"
        return out
    lo, hi = rows.min(), rows.max()
    span = max(1, hi - lo + 1)
    n = max(1, int(round(span * band)))

    mx = lin.max(axis=2)
    mn = lin.min(axis=2)
    with np.errstate(divide="ignore", invalid="ignore"):
        sat = np.where(mx > 1e-6, (mx - mn) / mx, 0.0)
    lum = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]

    def bandstats(r0, r1, label):
        sel = np.zeros_like(m)
        sel[r0:r1, :] = True
        sel = sel & m
        if sel.sum() < 200:
            return None
        return {"pixels": int(sel.sum()),
                "saturation_median": round(float(np.median(sat[sel])), 5),
                "luma_median": round(float(np.median(lum[sel])), 5),
                "rgb_median_linear": [round(float(np.median(lin[..., c][sel])), 5)
                                      for c in range(3)],
                "_rows": [int(r0), int(r1)], "_band": label}

    out["zenith"] = bandstats(lo, lo + n, "top %.0f%% of sky" % (band * 100))
    out["horizon"] = bandstats(hi - n + 1, hi + 1, "bottom %.0f%% of sky" % (band * 100))
    if out["zenith"] and out["horizon"] and out["horizon"]["saturation_median"]:
        out["zenith_over_horizon_saturation"] = round(
            out["zenith"]["saturation_median"]
            / out["horizon"]["saturation_median"], 4)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--band", type=float, default=0.15)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    rows = []
    for f in a.frames:
        r = measure(f, a.band)
        rows.append(r)
        n = os.path.splitext(os.path.basename(f))[0]
        z, h = r.get("zenith"), r.get("horizon")
        if not z:
            print("  %-22s -- %s" % (n, r.get("_why", "no zenith band")))
            continue
        print("  %-22s zenith sat %.5f  luma %.5f  |  horizon sat %s  |  z/h %s"
              % (n, z["saturation_median"], z["luma_median"],
                 ("%.5f" % h["saturation_median"]) if h else "-",
                 r.get("zenith_over_horizon_saturation", "-")))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "Brief 2 Task 4: median linear saturation of "
                                "the zenith band of the SKY MASK (not frame "
                                "rows), with the horizon band and their ratio.",
                       "rows": rows}, fh, indent=1)
        print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
