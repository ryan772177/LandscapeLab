"""fog_vs_sky.py — does the fog take its colour from the sky?

Brief 2 Task 1's acceptance. The flat NON-SKY band at the elevated stations
is measured against the horizon sky directly above it, in LINEAR RGB:

    fog_vs_sky_dE = || median(non-sky featureless) - median(horizon sky) ||

Acceptance: < 0.08. The acceptance STATIONS are mid_slope and vista, but the
PASS/FAIL verdict is emitted for every frame supplied on the command line.

WHY LINEAR AND WHY MEDIAN. sRGB distance is perceptual-ish but compresses
highlights, and the quantity of interest is a RADIOMETRIC one -- whether the
fog is inscattering the same light the sky is. Median rather than mean
because both regions have outliers (a bright rim, a dark tree edge) and the
question is about the bulk of each.

WHY THE HORIZON SKY AND NOT THE WHOLE SKY. The sky is a gradient: zenith is
much deeper blue than the horizon. Fog at distance converges on the sky it is
looking THROUGH, which is the horizon, not the zenith. Comparing against the
whole sky's median would fail a correctly-coloured fog.

THE TILE GRID (tile=16, var_thresh=1e-5) MATCHES
`bench_capture.featureless_split`, so the non-sky band this measures lines up
with the tiles that report counts. CAVEAT: measure() recomputes the flat/sky
masks inline and applies NO `exclude_rect_px`, so if featureless_split is run
WITH an exclusion (a grey card in frame) the two sets DIVERGE -- this would
count the grey-card tiles that report excludes, biasing the non-sky median.
mid_slope and vista carry no grey card, so they agree today; add the same
exclusion here before trusting a grey-carded station.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_capture as bc  # noqa: E402


def srgb_to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def measure(path, band, tile=16, var_thresh=1e-5, horizon_rows=0.25,
            depth_path=None):
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im).astype("float64") / 255.0
    g = np.asarray(im.convert("L")).astype("float64") / 255.0
    h, w = g.shape
    h2, w2 = h // tile * tile, w // tile * tile
    nty, ntx = h2 // tile, w2 // tile

    var = g[:h2, :w2].reshape(nty, tile, ntx, tile).var(axis=(1, 3))
    flat = var < var_thresh
    tc = rgb[:h2, :w2].reshape(nty, tile, ntx, tile, 3).mean(axis=(1, 3))
    # SKY MASK: depth when a depth pass is given (RULED 2026-09-10 --
    # geometric, immune to the Brief-2 desaturation that eroded the colour
    # band, LESSONS 2026-09-09e), colour otherwise. A tile-grid mismatch
    # RAISES inside featureless-land: wrong station or resolution must
    # refuse, never fall back to colour and produce a plausible number.
    if depth_path is not None:
        is_sky = bc.sky_mask_from_depth(depth_path, tile)
        if is_sky.shape != (nty, ntx):
            return {"frame": path.replace("\\", "/"),
                    "fog_vs_sky_dE": None,
                    "_why": ("depth tile grid %s != beauty %s (%s) -- "
                             "refusing" % (is_sky.shape, (nty, ntx),
                                           depth_path))}
    else:
        r, gg, b = tc[..., 0], tc[..., 1], tc[..., 2]
        is_sky = (b - r) >= float(band["min_blue_minus_red"])
        if band.get("require_monotonic_bgr", True):
            is_sky = is_sky & (b >= gg) & (gg >= r)

    non_sky_flat = flat & ~is_sky
    # HORIZON SKY: sky tiles in the rows just above the LOWEST sky tile in
    # each column, i.e. hugging the skyline rather than the zenith. Taken as
    # the bottom `horizon_rows` of the sky region overall, which is robust
    # when the skyline is ragged.
    sky_rows = np.nonzero(is_sky.any(axis=1))[0]
    horizon = np.zeros_like(is_sky)
    if sky_rows.size:
        lo, hi = sky_rows.min(), sky_rows.max()
        span = max(1, int(round((hi - lo + 1) * horizon_rows)))
        horizon[max(lo, hi - span + 1):hi + 1, :] = True
    horizon = horizon & is_sky

    lin = srgb_to_linear(tc)
    out = {
        "frame": path.replace("\\", "/"),
        "sky_mask": "depth" if depth_path is not None else "colour",
        "non_sky_flat_tiles": int(non_sky_flat.sum()),
        "horizon_sky_tiles": int(horizon.sum()),
    }
    if non_sky_flat.sum() == 0 or horizon.sum() == 0:
        out["fog_vs_sky_dE"] = None
        out["_why"] = ("no %s tiles -- cannot compare"
                       % ("non-sky featureless" if non_sky_flat.sum() == 0
                          else "horizon sky"))
        return out

    m_band = np.median(lin[non_sky_flat], axis=0)
    m_sky = np.median(lin[horizon], axis=0)
    out["non_sky_median_linear"] = [round(float(v), 5) for v in m_band]
    out["horizon_sky_median_linear"] = [round(float(v), 5) for v in m_sky]
    out["fog_vs_sky_dE"] = round(float(np.linalg.norm(m_band - m_sky)), 5)
    out["acceptance"] = "< 0.08"
    out["verdict"] = "PASS" if out["fog_vs_sky_dE"] < 0.08 else "FAIL"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--depth", action="append", default=None,
                    help="scene-depth pass per frame, positionally matched "
                         "to `frames`; pass '-' for a frame with no depth "
                         "(that frame falls back to the COLOUR mask, which "
                         "is unreliable on Brief-2-era desaturated skies)")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    depths = a.depth or []
    if depths and len(depths) != len(a.frames):
        ap.error("--depth given %d time(s) for %d frame(s); match them "
                 "positionally, '-' for none" % (len(depths), len(a.frames)))
    rows = [measure(f, bc.SKY_BAND,
                    depth_path=(depths[i] if depths and depths[i] != "-"
                                else None))
            for i, f in enumerate(a.frames)]
    for r in rows:
        name = os.path.splitext(os.path.basename(r["frame"]))[0]
        if r.get("fog_vs_sky_dE") is None:
            print("  %-14s dE  --      %s" % (name, r.get("_why")))
        else:
            print("  %-14s dE %.5f  %s   band %s  sky %s"
                  % (name, r["fog_vs_sky_dE"], r["verdict"],
                     r["non_sky_median_linear"], r["horizon_sky_median_linear"]))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "Brief 2 Task 1: linear-RGB distance between "
                                "the non-sky featureless median and the "
                                "horizon-sky median. Acceptance < 0.08.",
                       "rows": rows}, fh, indent=1)
        print("wrote %s" % a.out)
    # This IS Brief 2 Task 1's acceptance gate: a FAIL or a could-not-compare
    # must reach the EXIT CODE, not exit 0 while the verdict says otherwise.
    nulls = [r for r in rows if r.get("fog_vs_sky_dE") is None]
    fails = [r for r in rows if r.get("verdict") == "FAIL"]
    if nulls:
        print("REFUSE: %d frame(s) could not be compared (no tiles / depth "
              "grid mismatch)." % len(nulls))
        return 3
    if fails:
        print("FAIL: %d frame(s) at or above the 0.08 acceptance." % len(fails))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
