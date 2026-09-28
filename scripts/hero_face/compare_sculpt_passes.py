"""compare_sculpt_passes.py — did the second pass widen the face, in absolute terms?

The ratio tables produced by render_face_mesh_offline.py normalise each mesh
by ITS OWN cranium width. That is the right normalisation for comparing a
mesh against a photograph, and the WRONG one for comparing two meshes to each
other: if the cranium widened between passes, the denominator moved and the
two tables are not comparable band by band.

So this compares the two passes in ABSOLUTE units at matched heights, which
is the question actually being asked -- did the jaw get wider, or did only
the skull?
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np


def profile(p, n):
    z = p[:, 2]
    zmin, zmax = z.min(), z.max()
    rows = []
    for i in range(n):
        hi = zmax - (zmax - zmin) * i / n
        lo = zmax - (zmax - zmin) * (i + 1) / n
        sel = (z >= lo) & (z <= hi)
        w = (p[sel, 0].max() - p[sel, 0].min()) if sel.sum() > 3 else float("nan")
        rows.append(((zmax - (hi + lo) / 2.0) / (zmax - zmin), w))
    return rows


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=os.path.join(
        root, "hero", "generated", "face_mesh_sculpted.json"))
    ap.add_argument("--b", default=os.path.join(
        root, "hero", "generated", "face_mesh_final.json"))
    ap.add_argument("--bins", type=int, default=16)
    args = ap.parse_args(argv)

    a = np.asarray(json.load(open(args.a))["vertices"], dtype=np.float64)
    b = np.asarray(json.load(open(args.b))["vertices"], dtype=np.float64)
    pa = profile(a, args.bins)
    pb = profile(b, args.bins)

    print("pass 1 z span %.5f   pass 2 z span %.5f"
          % (a[:, 2].max() - a[:, 2].min(), b[:, 2].max() - b[:, 2].min()))
    print("")
    print("  depth/H   width pass1   width pass2    change")
    for (d1, w1), (d2, w2) in zip(pa, pb):
        if np.isnan(w1) or np.isnan(w2):
            continue
        print("   %.3f      %.5f       %.5f     %+6.2f%%"
              % (d1, w1, w2, 100.0 * (w2 - w1) / w1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
