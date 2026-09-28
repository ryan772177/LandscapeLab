"""Measure what a concept image will actually tell you, before describing it.

Three things are genuinely measurable from a single image and feed the
atmosphere block of a scene recipe:

  SHADOW BEARING  the dominant orientation of shadow streaks on open ground,
                  via a structure tensor. This is an IMAGE-SPACE bearing, not
                  a world azimuth -- converting it needs the camera solve, and
                  saying otherwise would be inventing precision.
  LIGHT SPLIT     colour of sunlit vs shadowed ground, sampled by luma
                  percentile within the same region. Drives sun colour and
                  sky/ambient tint.
  HAZE            how saturation and black level move with distance, using
                  image height as the depth proxy on a level-ish shot.

Everything printed is a measurement. The reading of the image -- what the
things ARE -- is done by eye and recorded separately, with provenance.

Usage: python scripts/analyse_concept.py refs/alpine_village_01.jpg [--band 0.6 0.95]
"""
import argparse
import sys

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def structure_tensor_bearing(g):
    """Dominant orientation of linear features, degrees, 0 = image +x (right)."""
    gy, gx = np.gradient(g.astype(np.float64))
    jxx, jyy, jxy = (gx * gx).sum(), (gy * gy).sum(), (gx * gy).sum()
    # principal direction of the structure tensor; features run PERPENDICULAR
    # to the dominant gradient, so add 90 deg.
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    bearing = (np.degrees(theta) + 90.0) % 180.0
    coherence = (np.hypot(jxx - jyy, 2.0 * jxy) / (jxx + jyy + 1e-12))
    return bearing, float(coherence)


def light_split(arr, lum, y0, y1):
    """Sunlit/shadow split on a ground band: mean RGB of the top/bottom 15%
    by luma. Returns (hi_rgb, lo_rgb) as float triples. THE definition of
    the brief's lighting_measured.sunlit_rgb and sunlit_rb_split
    (= hi_rgb[0] - hi_rgb[2]); brief_author imports this so the CLI and
    the authored brief cannot drift."""
    reg = arr[y0:y1, :, :].reshape(-1, 3)
    rl = lum[y0:y1, :].reshape(-1)
    hi = reg[rl >= np.percentile(rl, 85)]
    lo = reg[rl <= np.percentile(rl, 15)]
    return ([float(hi[:, c].mean()) for c in range(3)],
            [float(lo[:, c].mean()) for c in range(3)])


def minluma_rise(lum, H):
    """Aerial-haze proxy: p1 luma of the far band (y 0.05-0.20 of height)
    minus p1 luma of the near band (y 0.50-0.65). Positive = lifted blacks
    with distance. THE definition of lighting_measured.minluma_rise."""
    far = np.percentile(lum[int(0.05 * H):int(0.20 * H)], 1)
    near = np.percentile(lum[int(0.50 * H):int(0.65 * H)], 1)
    return float(far - near)


def load_image(path):
    """Image -> (arr float [0,1] HxWx3, lum, sat, H, W)."""
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.float32) / 255.0
    H, W, _ = arr.shape
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    mx, mn = arr.max(2), arr.min(2)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return arr, lum, sat, H, W


def measure_for_brief(image_path, band=(0.60, 0.85)):
    """The three measurable lighting_measured fields, as a dict. Used by
    forge_tool/brief_author.py; the CLI below prints the same quantities from
    the same functions.

    Default band 0.60-0.85 is DELIBERATELY not the CLI's 0.62-0.97: every
    recorded brief measurement used 0.6-0.85 (the proven-brief provenance
    strings), and reproducing those numbers exactly is this function's
    calibration test. The CLI default predates the briefs."""
    arr, lum, _, H, _ = load_image(image_path)
    y0, y1 = int(band[0] * H), int(band[1] * H)
    hi, _ = light_split(arr, lum, y0, y1)
    return {
        "_source": "analyse_concept.measure_for_brief band %.2f-%.2f"
                   % tuple(band),
        "sunlit_rb_split": round(hi[0] - hi[2], 3),
        "minluma_rise": round(minluma_rise(lum, H), 3),
        "sunlit_rgb": [round(v, 3) for v in hi],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--band", nargs=2, type=float, default=[0.62, 0.97],
                    help="vertical band of open ground, as fractions of height")
    a = ap.parse_args()

    arr, lum, sat, H, W = load_image(a.image)

    print("%s  %dx%d" % (a.image, W, H))
    print("  overall luma mean %.4f  std %.4f  sat mean %.4f"
          % (lum.mean(), lum.std(), sat.mean()))

    y0, y1 = int(a.band[0] * H), int(a.band[1] * H)
    band = lum[y0:y1, :]
    bearing, coh = structure_tensor_bearing(band)
    print()
    print("  SHADOW BEARING (image space, band y=%.2f..%.2f of height)"
          % tuple(a.band))
    print("    dominant feature bearing : %.1f deg from image +x" % bearing)
    print("    coherence                : %.3f  (0 = isotropic, 1 = perfectly linear)")
    print("    coherence value          : %.3f" % coh)
    print("    NOTE: image-space only. World azimuth needs the camera solve.")

    hi3, lo3 = light_split(arr, lum, y0, y1)
    print()
    print("  LIGHT SPLIT on that ground band")
    print("    sunlit  (top 15%%) RGB  %.3f %.3f %.3f   luma %.3f"
          % (hi3[0], hi3[1], hi3[2],
             0.2126 * hi3[0] + 0.7152 * hi3[1] + 0.0722 * hi3[2]))
    print("    shadow  (bot 15%%) RGB  %.3f %.3f %.3f   luma %.3f"
          % (lo3[0], lo3[1], lo3[2],
             0.2126 * lo3[0] + 0.7152 * lo3[1] + 0.0722 * lo3[2]))
    warm_hi = hi3[0] - hi3[2]
    warm_lo = lo3[0] - lo3[2]
    print("    R-B  sunlit %+0.3f   shadow %+0.3f   -> %s"
          % (warm_hi, warm_lo,
             "WARM light, COOL shadow" if warm_hi > warm_lo else "no warm/cool split"))

    print()
    print("  HAZE by image height (depth proxy; 0.0 = top of frame)")
    for f0, f1 in ((0.05, 0.20), (0.20, 0.35), (0.35, 0.50), (0.50, 0.65)):
        s = slice(int(f0 * H), int(f1 * H))
        print("    y %.2f-%.2f   luma %.3f   sat %.3f   min-luma %.3f"
              % (f0, f1, lum[s].mean(), sat[s].mean(),
                 np.percentile(lum[s], 1)))
    print("    rising min-luma with distance = lifted blacks = aerial haze")
    return 0


if __name__ == "__main__":
    sys.exit(main())
