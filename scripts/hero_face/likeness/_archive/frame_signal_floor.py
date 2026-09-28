"""frame_signal_floor.py -- is a frame difference above this rig's own repeat noise?

    python frame_signal_floor.py <repeat_a.png> <repeat_b.png> <before.png> [crop]

Two captures of an UNCHANGED subject give the floor; the before/after pair gives
the signal; the ratio is the answer. Quoting a mean |diff| without that ratio is
the mistake this project made for a week on `/Game/Alpine` -- every A/B was
judged against a floor of 0.00298 measured on a different scene, over-crediting
differences by about four times.

The two repeat frames must be the SAME state, captured the same way, in the same
session. If they are not, the number below is not a floor.
"""

import sys

import numpy as np
from PIL import Image

CROP = (0.34, 0.245, 0.66, 0.755)


def crop(p, c=CROP):
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float64)
    h, w, _ = a.shape
    return a[int(h * c[1]):int(h * c[3]), int(w * c[0]):int(w * c[2])]


def main():
    ra, rb, before = sys.argv[1], sys.argv[2], sys.argv[3]
    A, B, C = crop(ra), crop(rb), crop(before)
    floor = float(np.abs(A - B).mean())
    sig = float(np.abs(C - A).mean())
    print("  repeat floor, same state : %.3f" % floor)
    print("  before vs after          : %.3f" % sig)
    print("  signal / floor           : %.1fx" % (sig / max(1e-6, floor)))
    d = np.abs(C - A).mean(2)
    h = d.shape[0]
    print("  where it changed, top to bottom:")
    for i in range(5):
        band = d[int(h * i / 5):int(h * (i + 1) / 5)]
        print("    band %d  %.3f  (%.1fx floor)"
              % (i + 1, band.mean(), band.mean() / max(1e-6, floor)))


main()
