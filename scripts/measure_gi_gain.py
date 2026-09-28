"""measure_gi_gain.py — how much light does Lumen ADD to this world?

OFFLINE. Reads two capture sets and compares them. No editor, no writes.

WHY THIS EXISTS
---------------
`atmosphere_solve.py` solves exposure from PHYSICAL quantities:

    lum  = lambert_luminance(albedo, ground_illuminance, incidence)
    bias = log2(target * white_point / lum)

That model is DIRECT LIGHT ONLY — a Lambertian surface lit by the sun.
It has no term for indirect bounce, so re-running it "under Lumen"
returns the identical answer. The solver cannot see Lumen, and asking it
to would be asking a model to report something it does not contain.

The honest fix keeps the solver physical and supplies the one thing it
lacks as a MEASURED coefficient:

    lum_with_gi = lum * gi_gain
    bias_lumen  = bias_direct - log2(gi_gain)

This script measures `gi_gain`, and it is the provenance for that number.

THE PAIR MUST DIFFER IN LUMEN AND NOTHING ELSE
----------------------------------------------
On 2026-08-09 a first estimate of 1.238 was taken from a Lumen-ON set
against a Lumen-OFF set whose CLOUDS were also on. Volumetric clouds
change scene lighting AND animate between runs (B-CLOUD-NOISE: the sky
moved mae 0.06469 between two identical-settings captures, more than the
ground moved at 0.02853). That estimate was therefore confounded and is
not used. Both sets must be captured with clouds OFF via
`render_condition.py`, which reads every cvar back.

SKY IS EXCLUDED, AND THAT IS THE POINT
--------------------------------------
Lumen changes bounce light on GEOMETRY. Sky pixels are unaffected, so
including them drags the measured gain toward 1.0 by an amount that
depends only on how much sky the camera happens to frame — a
misleading-denominator error (non-negotiable 22). Sky is identified from
the pair itself: a pixel whose ratio is ~1.0 did not respond to Lumen.
That is a definition grounded in the measurement rather than in a colour
guess about what sky looks like.

Exit codes:
  0  measured
  2  REFUSED: the two sets do not pair up (no shared camera), OR they pair but
     no camera carried enough SUNLIT responding pixels to measure a gain
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES = os.path.join(REPO_ROOT, "captures", "alpine")

# Below this the sRGB quantisation step is a large fraction of the value
# and the ratio becomes noise. Deep shadow carries no exposure signal.
DARK_FLOOR = 0.02


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luma(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    lin = srgb_to_linear(a)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def by_camera(tag):
    """{camera: path} for every frame carrying `tag`."""
    out = {}
    for fn in os.listdir(CAPTURES):
        if not fn.endswith(".png") or tag not in fn:
            continue
        m = re.match(r"alpine__(.+?)__\d{8}T\d{6}Z__", fn)
        if m:
            out[m.group(1)] = os.path.join(CAPTURES, fn)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--on-tag", default="lumen_on_clouds_off")
    ap.add_argument("--off-tag", default="lumen_off_clouds_off")
    ap.add_argument("--respond-above", type=float, default=1.02,
                    help="ratio above which a pixel counts as RESPONDING "
                         "to Lumen rather than being sky")
    ap.add_argument("--sunlit-above", type=float, default=0.25,
                    help="OFF-frame luma above which a pixel is treated as "
                         "SUNLIT. The off frame is direct-light-only, so "
                         "its brightness IS the sunlit/shadow "
                         "discriminator. Default 0.25 sits just below "
                         "R13's solved sunlit target of 0.3201.")
    args = ap.parse_args(argv)

    on, off = by_camera(args.on_tag), by_camera(args.off_tag)
    shared = sorted(set(on) & set(off))
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("on  tag   : {0}  ({1} frames)".format(args.on_tag, len(on)))
    print("off tag   : {0}  ({1} frames)".format(args.off_tag, len(off)))
    print("paired    : {0}".format(len(shared)))
    if not shared:
        print("REFUSE: no camera appears in BOTH sets.")
        return 2
    missing = sorted((set(on) ^ set(off)))
    if missing:
        print("NOT PAIRED (excluded, and named rather than dropped "
              "silently): {0}".format(", ".join(missing)))
    print("")

    # SUNLIT AND SHADOW ARE REPORTED SEPARATELY, AND MUST BE.
    # A first version of this script took one median over every
    # responding pixel and returned 1.5753 with a spread of 7.25. The
    # spread was the finding: in shadow the direct term is ~0, so bounce
    # is ALL the light and the ratio runs 3-8x, while sunlit ground moves
    # only 1.03-1.24. Those are two different physical populations and
    # averaging them answers no question anyone asked.
    #
    # The exposure solve targets SUNLIT TERRAIN — R13's 0.3201 is a
    # sunlit figure and `lambert_luminance` computes direct sunlit
    # luminance — so the SUNLIT gain is the one that belongs in the
    # solve. The shadow gain is reported because it is the real story of
    # what Lumen does to this world, and because a reader who saw only
    # the sunlit number would wrongly conclude Lumen barely matters.
    print("{0:<18s} {1:>9s} {2:>8s} {3:>8s} {4:>9s} {5:>9s}"
          .format("camera", "off luma", "SUNLIT", "shadow", "sunlit%",
                  "shadow%"))
    per_cam = []
    for cam in shared:
        a, b = luma(off[cam]), luma(on[cam])
        if a.shape != b.shape:
            print("{0:<18s}  SHAPE MISMATCH — excluded".format(cam))
            continue
        lit = a > DARK_FLOOR
        if not lit.any():
            print("{0:<18s}  entirely below the dark floor — excluded"
                  .format(cam))
            continue
        ratio = np.ones_like(a)
        ratio[lit] = b[lit] / a[lit]
        responds = lit & (ratio > args.respond_above)

        sun = responds & (a > args.sunlit_above)
        shade = responds & (a <= args.sunlit_above)
        g_sun = float(np.median(ratio[sun])) if sun.sum() > 500 else None
        g_shade = float(np.median(ratio[shade])) if shade.sum() > 500 else None
        per_cam.append((cam, g_sun, float(sun.mean())))
        print("{0:<18s} {1:>9.4f} {2:>8s} {3:>8s} {4:>8.1%} {5:>8.1%}"
              .format(cam, float(a[lit].mean()),
                      "—" if g_sun is None else "{0:.4f}".format(g_sun),
                      "—" if g_shade is None else "{0:.4f}".format(g_shade),
                      float(sun.mean()), float(shade.mean())))

    gains = np.array([g for _, g, f in per_cam
                      if g is not None and f > 0.05])
    print("")
    if gains.size == 0:
        print("REFUSE: no camera carried enough SUNLIT responding pixels. "
              "Without them the exposure gain is unmeasured — that is 'I "
              "could not look', not 'the gain is 1.0'.")
        return 2
    med = float(np.median(gains))
    print("SUNLIT GI GAIN across {0} cameras with >5% sunlit-responding:"
          .format(gains.size))
    print("  median {0:.4f}   p10 {1:.4f}   p90 {2:.4f}   spread {3:.4f}"
          .format(med, float(np.percentile(gains, 10)),
                  float(np.percentile(gains, 90)),
                  float(gains.max() - gains.min())))
    print("")
    print("  THIS is the number for the exposure solve, because the solve")
    print("  targets sunlit terrain. The shadow column is larger by a")
    print("  multiple and is NOT an error bar on it — it is a different")
    print("  quantity, and mixing the two was this script's first bug.")
    print("")
    print("  exposure correction = -log2(gain) = {0:+.3f} EV".format(
        -np.log2(med)))
    print("  applied to R13's solved -1.786 EV -> {0:+.3f} EV".format(
        -1.786 - np.log2(med)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
