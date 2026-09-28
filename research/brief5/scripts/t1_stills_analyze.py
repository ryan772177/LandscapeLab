#!/usr/bin/env python3
"""Brief 5 T1 -- coverage ratio + band SSIM from the two stills.

READ-ONLY. arm A = r.ForceLOD 4 (both card species show their CARD); arm B =
r.ForceLOD 2 (geometry). Same ring_station camera, game view, viewmode lit.
Decision (desk): canopy coverage ratio B/A outside 0.90-1.10 OR band SSIM < 0.90
-> defect CONFIRMED.

Band mask: no scene-depth export, so the mask is NON-SKY (the r.ForceLOD is
global, so the whole forest is under test, not just 128-512 m -- stated). Canopy =
foliage-coloured (green-dominant) non-sky pixels. Also writes 3 x 512 px crop
pairs from the densest-canopy columns.
"""
import json
import os

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STILLS = os.path.join(REPO, "research", "brief5", "derived", "t1_stills")


def load(name):
    return np.asarray(Image.open(os.path.join(STILLS, name)).convert("RGB"),
                      dtype=np.float64)


def masks(im):
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    bright = im.mean(2)
    sky = (b > r + 8) & (b > g) & (bright > 90)      # bluish + bright
    nonsky = ~sky
    canopy = nonsky & (g >= r) & (g >= b) & (bright > 12)  # green foliage, lit
    return sky, nonsky, canopy


def main():
    a = load("brief5_t1_armA_cards.png")
    b = load("brief5_t1_armB_geom.png")
    sky_a, nonsky_a, canopy_a = masks(a)
    sky_b, nonsky_b, canopy_b = masks(b)
    cov_a = canopy_a.sum() / max(1, nonsky_a.sum())
    cov_b = canopy_b.sum() / max(1, nonsky_b.sum())
    ratio = cov_b / cov_a if cov_a else None
    # band SSIM on grayscale over the union non-sky region
    ga = a.mean(2)
    gb = b.mean(2)
    full_ssim, _ = ssim(ga, gb, data_range=255.0, full=True)
    # non-sky-masked SSIM: zero out sky, compare
    m = (nonsky_a | nonsky_b).astype(np.float64)
    nonsky_ssim, _ = ssim(ga * m, gb * m, data_range=255.0, full=True)

    # 3 crop pairs (512 px) from the 3 densest-canopy column bands
    H, W = ga.shape
    colcanopy = canopy_a.sum(0)
    step = W // 3
    crops = []
    for i in range(3):
        seg = colcanopy[i * step:(i + 1) * step]
        cx = int(np.argmax(np.convolve(seg, np.ones(512), "same"))) + i * step
        x0 = max(0, min(W - 512, cx - 256))
        y0 = max(0, H // 2 - 256)
        for tag, im in (("A", a), ("B", b)):
            Image.fromarray(im[y0:y0 + 512, x0:x0 + 512].astype("uint8")).save(
                os.path.join(STILLS, "crop%d_%s.png" % (i + 1, tag)))
        crops.append({"crop": i + 1, "x0": x0, "y0": y0})

    out = {
        "_what": "Brief 5 T1 stills coverage + SSIM. arm A = ForceLOD 4 (cards), "
                 "arm B = ForceLOD 2 (geometry), ring_station.",
        "_band_mask": "NON-SKY (no depth export; r.ForceLOD is global so the whole "
                      "forest is under test, not only 128-512 m).",
        "canopy_coverage": {"arm_A_cards": round(cov_a, 4),
                            "arm_B_geometry": round(cov_b, 4),
                            "ratio_B_over_A": round(ratio, 4) if ratio else None},
        "ssim": {"full_frame": round(float(full_ssim), 4),
                 "non_sky": round(float(nonsky_ssim), 4)},
        "mean_brightness": {"arm_A": round(float(a.mean()), 2),
                            "arm_B": round(float(b.mean()), 2)},
        "crops": crops,
        "decision_rule": "coverage ratio outside 0.90-1.10 OR band SSIM < 0.90 "
                         "-> CONFIRMED",
        "coverage_outside_band": bool(ratio is not None and (ratio < 0.90 or ratio > 1.10)),
        "ssim_below_0_90": bool(float(nonsky_ssim) < 0.90),
    }
    out["verdict"] = ("CONFIRMED" if (out["coverage_outside_band"]
                                      or out["ssim_below_0_90"]) else "cards adequate")
    p = os.path.join(REPO, "research", "brief5", "input", "t1_see_it.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
