#!/usr/bin/env python3
"""item8_diffcrop.py -- the I4 tiling evidence that the distance-placed crops
could not deliver. READ-ONLY.

The auto crops in item8_pixels.py place by flat-ground distance, which saturates
at the horizon without a depth pass and landed on mid-field snow/road, not the
far forest. This instead finds the densest cluster of A-vs-B DIFFERING pixels
(which ARE the toggled HLOD proxies, by construction) and writes an
A | B | diff strip there, x3 brightened for the dark offscreen exposure. The
diff panel shows the removed proxy band directly: a natural conifer tree-line
silhouette (no square billboard tiling) at the rendered proxy distances.
"""
import os

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(REPO, "_verify", "perf", "item8")
DST = os.path.join(REPO, "research", "brief5", "derived", "item8")
CROP = 512
DIFF_THRESH = 8
BRIGHTEN = 3.0


def _load(tag):
    p = os.path.join(OUT, tag, "frame_last.png")
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def main():
    os.makedirs(DST, exist_ok=True)
    for st in ("vista", "treeline"):
        A, B = _load("%s_A1" % st), _load("%s_B" % st)
        diff = (np.abs(A - B).max(axis=2) > DIFF_THRESH)
        h, w = diff.shape
        ii = np.zeros((h + 1, w + 1), np.int64)
        ii[1:, 1:] = np.cumsum(np.cumsum(diff.astype(np.int64), 0), 1)
        best, bxy = -1, (0, 0)
        for y in range(0, h - CROP, 64):
            for x in range(0, w - CROP, 64):
                s = (ii[y + CROP, x + CROP] - ii[y, x + CROP]
                     - ii[y + CROP, x] + ii[y, x])
                if s > best:
                    best, bxy = s, (x, y)
        x, y = bxy

        def bright(a):
            return np.clip(a.astype(np.float32) * BRIGHTEN, 0, 255).astype(np.uint8)
        Aa = bright(A[y:y + CROP, x:x + CROP])
        Bb = bright(B[y:y + CROP, x:x + CROP])
        dd = (diff[y:y + CROP, x:x + CROP][..., None]
              * np.array([255, 0, 255], np.uint8)).astype(np.uint8)
        sep = np.full((CROP, 6, 3), 255, np.uint8)
        strip = np.concatenate([Aa, sep, Bb, sep, dd], axis=1)
        fn = os.path.join(DST, "diffcrop_%s_A-B-diff.png" % st)
        Image.fromarray(strip).save(fn)
        print("%s: densest diff window px (%d,%d), %d diff px in crop -> %s"
              % (st, x, y, best, os.path.relpath(fn, REPO)))


if __name__ == "__main__":
    main()
