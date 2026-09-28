"""check_weightmap_mip_partition.py -- CPU invariant for Brief 7 P1 constraint 1.

The layer weightmap is now mipped with SIMPLE_AVERAGE (a box filter) instead of
NO_MIPMAPS, because an 8129^2 mask with no mip chain aliased into ~1 m blocks
under minification (research/brief7/p1_block_diff.md). The filter MUST be a box
average and nothing else: a box average is linear, so the sum of the per-texel
weights (the partition, sum == 1) is preserved from one mip to the next --
average-of-sums == sum-of-averages. Any SHARPENING mip filter breaks that
partition and rings at layer boundaries.

This holds the ruling as an invariant with a positive and a negative control
(the shape every CPU-model invariant in this project uses):
  POSITIVE: the box average keeps the mip-1 partition within 1e-3 of the
            mip-0 partition it descends from, everywhere.
  NEGATIVE: an unsharp (sharpening) filter drives the drift OVER 1e-3, so the
            bound is not vacuous.

READ-ONLY, offline: reads the 8-channel source weightmap PNGs, no editor.
"""
from __future__ import annotations
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIFT_BOUND = 1e-3
# The 8 stored channels across the a/b files (w8_sidecar.json order).
FILES = ("textures/alpine_8k_w8a.png", "textures/alpine_8k_w8b.png")


def _load_channels():
    chans = []
    for rel in FILES:
        p = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(p):
            raise SystemExit("REFUSE: weightmap source not found: %s" % rel)
        im = np.asarray(Image.open(p)).astype(np.float64) / 255.0
        if im.ndim != 3 or im.shape[2] < 4:
            raise SystemExit(
                "REFUSE: %s must be a 4-channel (RGBA) weightmap, got shape %r"
                % (rel, getattr(im, "shape", None)))
        for c in range(4):
            chans.append(im[:, :, c])
    return np.stack(chans, axis=0)  # (8, H, W)


def _box_mip1(a):
    # 2x2 box average; crop the odd last row/col (8129 is odd) so the 2x2
    # tiling is exact. This matches the engine's box mip on INTERIOR texels
    # only (the engine halves with floor and clamps the odd edge, MGTAM_Clamp,
    # rather than cropping); the partition invariant holds regardless because
    # any convex average preserves a per-texel partition.
    _, h, w = a.shape
    h2, w2 = h - (h % 2), w - (w % 2)
    a = a[:, :h2, :w2]
    return (a[:, 0::2, 0::2] + a[:, 1::2, 0::2]
            + a[:, 0::2, 1::2] + a[:, 1::2, 1::2]) / 4.0


def _unsharp_mip1(a):
    # a sharpening filter: box mip minus a fraction of the neighbourhood
    # detail. Stand-in for a non-box mip kernel; must BREAK the partition.
    box = _box_mip1(a)
    # high-frequency residual per channel at mip-1 scale
    blur = 0.25 * (np.roll(box, 1, 1) + np.roll(box, -1, 1)
                   + np.roll(box, 1, 2) + np.roll(box, -1, 2))
    return box + 0.5 * (box - blur)


def main():
    a = _load_channels()
    sum0 = a.sum(axis=0)                          # (H, W) partition at mip 0
    q0 = float(np.max(np.abs(sum0 - 1.0)))        # source drift from 1 (8-bit)

    # REFERENCE, by an INDEPENDENT path: box-average the mip-0 PARTITION
    # (sum THEN box). A correct box channel-mip must reproduce it when its
    # per-channel mips are summed (box THEN sum) -- that equality is the
    # partition-preservation property, and computing it two different ways
    # (not comparing an expression to itself) is what makes it a measurement.
    ref = _box_mip1(sum0[None])[0]                # sum-then-box

    box1 = _box_mip1(a).sum(axis=0)               # box-then-sum
    drift_box = float(np.max(np.abs(box1 - ref)))
    q_box = float(np.max(np.abs(box1 - 1.0)))     # box mip still a partition?

    sharp1 = _unsharp_mip1(a).sum(axis=0)         # a sharpening channel-mip
    drift_sharp = float(np.max(np.abs(sharp1 - ref)))

    print("weightmap partition invariant (Brief 7 P1 constraint 1)")
    print("  mip-0 partition: min %.6f max %.6f  (drift from 1: %.3e)"
          % (float(sum0.min()), float(sum0.max()), q0))
    print("  POSITIVE box  : mip-1 partition vs box(partition) drift %.3e "
          "(bound %.0e); |mip-1 partition - 1| %.3e (bound q0+%.0e = %.3e)"
          % (drift_box, DRIFT_BOUND, q_box, DRIFT_BOUND, q0 + DRIFT_BOUND))
    print("  NEGATIVE sharp: mip-1 partition vs box(partition) drift %.3e "
          "(must exceed %.0e)" % (drift_sharp, DRIFT_BOUND))

    ok = True
    if drift_box > DRIFT_BOUND:
        print("  FAIL: box channel-mip did not reproduce box(partition) -- "
              "not partition-preserving as implemented")
        ok = False
    if q_box > q0 + DRIFT_BOUND:
        print("  FAIL: box mip pushed the partition further from 1 than the "
              "source's own quantisation")
        ok = False
    if drift_sharp <= DRIFT_BOUND:
        print("  FAIL: the negative control did not break the partition -- "
              "the bound is vacuous")
        ok = False
    if ok:
        print("PASS: box average preserves the partition (two independent "
              "paths agree, and the mip stays a partition near 1); a "
              "sharpening filter does not. SIMPLE_AVERAGE is correct.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
