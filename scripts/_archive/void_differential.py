"""void_differential.py — did the GroundAlbedo change reach the render at all?

WHY THIS EXISTS
    `void_mask.py` decides "is this pixel magenta" with absolute floors
    (r-g > 0.25, b-g > 0.25, r > 0.2, b > 0.2). That is the right test when
    the magenta is bright. The SkyAtmosphere ground term is not necessarily
    bright:

        SkyAtmosphere.usf:826
        L += Light0Illuminance * TransmittanceToLight0 * Throughput
             * NdotL0 * Atmosphere.GroundAlbedo.rgb / PI

    NdotL0 is the sun's cosine at the planet surface, and this recipe's sun
    sits at 12 deg elevation, so the term is ~0.21, then /PI, then tonemapped
    at -1.923 EV. A frame that IS showing the virtual planet can therefore
    report void_fraction 0.000 -- a FALSE ZERO. Brief 2 gates every later
    atmosphere number on that reading, so a zero has to be earned.

WHAT IT DOES
    Compares the SAME station rendered twice, once at the original albedo and
    once at magenta, and reports where the two differ. This needs no absolute
    threshold and no assumption about brightness:

        pixels differ  -> those pixels ARE the virtual planet surface (void)
        nothing differs -> the albedo did not reach the render, OR there is
                           genuinely no planet surface in frame. The two are
                           distinguished by whether ANY pixel moved at all.

    A zero from void_mask is only trustworthy when this reports a non-trivial
    difference somewhere OR independently confirms the render responded.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--magenta", required=True)
    ap.add_argument("--out")
    ap.add_argument("--thresh", type=float, default=2.0 / 255.0,
                    help="per-channel difference counted as a real change")
    a = ap.parse_args(argv)

    A = np.asarray(Image.open(a.baseline).convert("RGB")).astype(np.float64) / 255.0
    B = np.asarray(Image.open(a.magenta).convert("RGB")).astype(np.float64) / 255.0
    if A.shape != B.shape:
        print("REFUSE: %s vs %s differ in shape" % (A.shape, B.shape))
        return 2

    d = np.abs(B - A)
    dmax = d.max(axis=2)
    changed = dmax > a.thresh

    # Of the changed pixels, which moved TOWARD magenta (R and B up, G down)?
    # That is the signature of the ground term specifically, as opposed to
    # temporal-sampling noise, which has no preferred hue direction.
    dr, dg, db = (B[..., 0] - A[..., 0]), (B[..., 1] - A[..., 1]), (B[..., 2] - A[..., 2])
    toward_magenta = changed & (dr > 0) & (db > 0) & (dg < dr) & (dg < db)

    rep = {
        "baseline": a.baseline, "magenta": a.magenta,
        "changed_fraction": round(float(changed.mean()), 6),
        "toward_magenta_fraction": round(float(toward_magenta.mean()), 6),
        "max_abs_diff": round(float(dmax.max()), 5),
        "mean_abs_diff": round(float(dmax.mean()), 6),
        "_read": ("changed_fraction 0 means the GroundAlbedo change did not "
                  "alter this frame at all -- so a void_mask zero on it says "
                  "nothing about void, only that nothing responded. A "
                  "non-zero toward_magenta_fraction localises the virtual "
                  "planet surface without any absolute brightness floor."),
    }
    ys, xs = np.nonzero(toward_magenta)
    rep["toward_magenta_bbox_xyxy"] = (
        [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        if xs.size else None)

    vis = (A * 255).astype(np.uint8).copy()
    vis[toward_magenta] = (0, 255, 0)
    dest = os.path.splitext(a.magenta)[0] + "_diff.png"
    Image.fromarray(vis).save(dest)
    rep["overlay"] = dest.replace("\\", "/")

    js = json.dumps(rep, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(js)
    print(js)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
