"""find_head_crop.py -- measure where the head is, instead of guessing a crop.

    python find_head_crop.py <image> [<image> ...]

A three-panel sheet that crops each source by eye is a sheet whose panels are
not comparable, and this project has twice produced a comparison that read as a
difference in hair and was a difference in framing.

So: find the subject by measuring. The reference portraits and the game frames
share a property -- the subject is warm and the surround is not -- so a
skin/hair-tone mask over a background of forest or studio grey localises the
head well enough to crop from. The reported box is a MEASUREMENT with its own
coverage number, so a bad one is visible as a bad number rather than silently
producing a wrong panel.
"""

import sys

import numpy as np
from PIL import Image


def head_box(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float64)
    h, w, _ = a.shape
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    # warm subject: red-dominant, not black, not blown
    warm = (R > G + 8) & (G >= B - 6) & (mx > 40) & (mx < 250) & (sat > 0.12)

    cols, rows = warm.sum(0), warm.sum(1)
    if warm.sum() < 500:
        return None, float(warm.mean())

    def span(v, frac=0.06):
        thr = v.max() * frac
        idx = np.where(v > thr)[0]
        return (int(idx[0]), int(idx[-1])) if idx.size else (0, len(v) - 1)

    x0, x1 = span(cols)
    y0, y1 = span(rows)
    # the head is the TOP of the warm region; take a square-ish box from y0
    side = max(x1 - x0, 1)
    y1 = min(h - 1, y0 + int(side * 1.25))
    pad = int(side * 0.18)
    x0 = max(0, x0 - pad)
    x1 = min(w - 1, x1 + pad)
    y0 = max(0, y0 - pad)
    y1 = min(h - 1, y1 + pad)
    return (x0 / w, y0 / h, x1 / w, y1 / h), float(warm.mean())


for p in sys.argv[1:]:
    box, cov = head_box(p)
    if box is None:
        print("%-46s NO SUBJECT FOUND (warm coverage %.4f)" % (p, cov))
    else:
        print("%-46s crop %.3f,%.3f,%.3f,%.3f   warm coverage %.4f"
              % (p.split("/")[-1], *box, cov))
