# COPIED 2026-10-10 from C:/Users/Admin/Gemini2UE/scripts/classify_topdown.py (sha256 1fc59680b56abecd...). Town-from-image adapter for plan.layout "image".
# Dependencies (standing rule 5): opencv-contrib-python 5.0 (cv2.ximgproc), shapely 2.2.0, sknw 0.15, numba 0.68.0 (host Python 3.12, pip).
"""classify_topdown.py - split a painted top-down map into colour classes as 8-bit masks.

Purpose: a Gemini top-down map (terrain or town) is painted in a handful of
colours (water, grass, forest, rock, snow, roads, roofs). K-means in CIE Lab
space (OpenCV, installed on the host) clusters the pixels; each cluster becomes
one 8-bit greyscale mask PNG, resized to the target landscape size, which is
the format Epic documents for layer weightmaps (one 8-bit single-channel image
per layer at the landscape's resolution). The palette JSON records the mean
colour of every cluster and its pixel share so a reader (Claude or a person)
can NAME the clusters afterwards; this tool never guesses what a colour means.

Masks are soft: a Gaussian blur of --feather pixels on the hard cluster mask
avoids one-pixel steps at the edges. The masks of all clusters sum to 255 at
every pixel before feathering; after feathering the sum stays within a few
units, which the report measures.

Usage:
    python scripts/classify_topdown.py refs/topdown/valley_map.png --k 6 --size 1009 --out-dir data/layers/valley

Exit codes: 0 written, 2 bad input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import cv2
import numpy as np

LEGAL = (505, 1009, 2017, 4033, 8129)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--size", type=int, default=1009, choices=LEGAL, help="output mask size (match the heightmap)")
    ap.add_argument("--feather", type=float, default=1.5, help="Gaussian sigma in output pixels")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)

    bgr = cv2.imread(a.src, cv2.IMREAD_COLOR)
    if bgr is None:
        print(f"ERROR: cannot read {a.src}")
        return 2
    h, w = bgr.shape[:2]
    side = min(h, w)
    top, left = (h - side) // 2, (w - side) // 2
    sq = bgr[top:top + side, left:left + side]
    work = cv2.resize(sq, (a.size, a.size), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(work, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)

    cv2.setRNGSeed(a.seed)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, labels, centres = cv2.kmeans(lab, a.k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(a.size, a.size)

    # order clusters by share, largest first, so names are stable across runs
    shares = np.bincount(labels.ravel(), minlength=a.k) / float(a.size * a.size)
    order = np.argsort(-shares)
    remap = {int(old): int(new) for new, old in enumerate(order)}
    labels = np.vectorize(remap.get)(labels)
    centres = centres[order]
    shares = shares[order]

    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.src))[0]
    palette = []
    masks = []
    for c in range(a.k):
        hard = (labels == c).astype(np.float32)
        soft = cv2.GaussianBlur(hard, (0, 0), a.feather) if a.feather > 0 else hard
        masks.append(soft)
        lab_c = np.uint8([[centres[c]]])
        bgr_c = cv2.cvtColor(lab_c, cv2.COLOR_LAB2BGR)[0, 0]
        rgb_c = [int(bgr_c[2]), int(bgr_c[1]), int(bgr_c[0])]
        p = os.path.join(a.out_dir, f"{stem}_class{c:02d}.png")
        cv2.imwrite(p, np.round(np.clip(soft, 0, 1) * 255).astype(np.uint8))
        palette.append({"class": c, "mean_rgb": rgb_c, "hex": "#%02x%02x%02x" % tuple(rgb_c),
                        "share": float(shares[c]), "mask": os.path.abspath(p), "name": None,
                        "_name": "to be filled by the reader after looking at the swatch and the source image"})

    total = np.sum(masks, axis=0)
    # a colour swatch sheet so the clusters can be named by eye
    sw = np.zeros((64, 64 * a.k, 3), np.uint8)
    for c in range(a.k):
        rgb = palette[c]["mean_rgb"]
        sw[:, c * 64:(c + 1) * 64] = (rgb[2], rgb[1], rgb[0])
    swatch = os.path.join(a.out_dir, f"{stem}_swatches.png")
    cv2.imwrite(swatch, sw)
    # a labelled preview: each pixel painted with its cluster mean colour
    prev = np.zeros_like(work)
    for c in range(a.k):
        rgb = palette[c]["mean_rgb"]
        prev[labels == c] = (rgb[2], rgb[1], rgb[0])
    preview = os.path.join(a.out_dir, f"{stem}_clusters.png")
    cv2.imwrite(preview, prev)

    report = {
        "source": os.path.abspath(a.src), "source_sha256": sha256_of(a.src),
        "source_size_px": [w, h], "crop": [left, top, side, side],
        "size_px": [a.size, a.size], "k": a.k, "feather_sigma_px": a.feather,
        "mask_sum_min_max": [float(total.min()), float(total.max())],
        "palette": palette, "swatches": os.path.abspath(swatch), "clusters_preview": os.path.abspath(preview),
        "ue_note": "each mask is an 8-bit single-channel PNG at the landscape resolution, the weightmap format Epic documents; name the classes, then map names to landscape layers",
    }
    with open(os.path.join(a.out_dir, f"{stem}_classes.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps({k: report[k] for k in ("size_px", "k", "mask_sum_min_max")}, indent=1))
    for p in palette:
        print(f"  class {p['class']:02d}  {p['hex']}  share {p['share']:.3f}")
    print("swatches:", swatch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
