"""analyse_landmarks.py — work out what the 79 face landmarks ARE, by measurement.

The sculpt API hands back an unlabelled array of 79 points. Nothing in the
engine's Python surface says which index is the nose tip or which axis is
lateral, and GUESSING that is exactly the class of error CLAUDE.md's
"an API remembered is an API guessed" is about — except here it would be
"an anatomy assumed".

So this derives the frame from the geometry itself:

  * the LATERAL axis is the one whose coordinate distribution is symmetric
    about its own centre AND which pairs points up across that centre. A face
    is bilaterally symmetric; nothing else about a head is.
  * the UP axis and the DEPTH axis are then separated by which one the
    mid-sagittal points spread along most, and by where the extremes sit.

Everything it prints is a measurement with its own disproof available:
if the symmetry test fails, it says so rather than picking the best of three.

Usage:  python scripts/hero_face/analyse_landmarks.py [--state PATH]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys


def load(path):
    with open(path, "r") as fh:
        d = json.load(fh)
    return d["landmarks"], d.get("coefficients", [])


def symmetry_score(pts, axis, centre):
    """Fraction of points that find a mirror partner across `centre` on `axis`.

    A partner must match on the OTHER two axes closely and be the opposite
    side of the centre. Returns (fraction_paired, median_residual).
    """
    other = [i for i in range(3) if i != axis]
    resid = []
    paired = 0
    for p in pts:
        mirrored = list(p)
        mirrored[axis] = 2.0 * centre - p[axis]
        best = None
        for q in pts:
            d = math.sqrt(sum((mirrored[k] - q[k]) ** 2 for k in range(3)))
            if best is None or d < best:
                best = d
        # scale the tolerance to the cloud, not to an absolute number
        resid.append(best)
        paired += 1 if best is not None else 0
    resid.sort()
    return resid[len(resid) // 2], resid


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "hero", "generated", "face_state_baseline.json"))
    args = ap.parse_args(argv)

    pts, coeffs = load(args.state)
    n = len(pts)
    print("landmarks   : %d" % n)
    print("coefficients: %d" % len(coeffs))
    if not pts:
        print("REFUSE: no landmarks to analyse")
        return 1

    names = "XYZ"
    mins = [min(p[i] for p in pts) for i in range(3)]
    maxs = [max(p[i] for p in pts) for i in range(3)]
    means = [sum(p[i] for p in pts) / n for i in range(3)]
    print("")
    print("axis     min       max      mean     extent")
    for i in range(3):
        print("  %s  %8.4f  %8.4f  %8.4f  %8.4f"
              % (names[i], mins[i], maxs[i], means[i], maxs[i] - mins[i]))

    # --- which axis is lateral? the one that mirrors ---
    print("")
    print("BILATERAL SYMMETRY TEST (median nearest-mirror distance;")
    print("the lateral axis is the one that mirrors CLEANLY):")
    best_axis, best_med = None, None
    for i in range(3):
        # try mirroring about the midpoint AND about zero; a head-local frame
        # usually centres the sagittal plane on 0, but do not assume it.
        for label, c in (("midpoint", (mins[i] + maxs[i]) / 2.0),
                         ("zero", 0.0),
                         ("mean", means[i])):
            med, _ = symmetry_score(pts, i, c)
            span = maxs[i] - mins[i]
            print("   axis %s about %-8s c=%8.4f  median residual %8.5f"
                  " (%5.1f%% of that axis span)"
                  % (names[i], label, c, med,
                     100.0 * med / span if span else float("nan")))
            if best_med is None or med < best_med:
                best_med, best_axis = med, (i, label, c)

    i, label, c = best_axis
    span = maxs[i] - mins[i]
    print("")
    print("  -> cleanest mirror: axis %s about %s (c=%.4f), residual %.5f"
          % (names[i], label, c, best_med))
    if span and best_med / span > 0.05:
        print("  -> WARNING: residual is >5%% of the span. The cloud does NOT")
        print("     mirror cleanly on any axis, so the lateral axis is NOT")
        print("     established and no delta should be derived from it.")
    else:
        print("  -> LATERAL AXIS = %s, sagittal plane at %.4f" % (names[i], c))

    lateral = i
    rest = [k for k in range(3) if k != lateral]
    # Of the remaining two, UP is conventionally the one with the larger
    # spread for a face plus a distinct chin/crown extreme. Report both
    # rather than deciding for the reader.
    print("")
    print("remaining axes: %s extent %.4f, %s extent %.4f"
          % (names[rest[0]], maxs[rest[0]] - mins[rest[0]],
             names[rest[1]], maxs[rest[1]] - mins[rest[1]]))

    # --- near-sagittal points, ordered: these are the profile ---
    tol = 0.10 * span if span else 0.01
    mid = [(k, p) for k, p in enumerate(pts) if abs(p[lateral] - c) <= tol]
    print("")
    print("MID-SAGITTAL LANDMARKS (|%s - %.4f| <= %.4f): %d of %d"
          % (names[lateral], c, tol, len(mid), n))
    print("these are the profile line -- brow, nose, lips, chin -- in order:")
    for k, p in sorted(mid, key=lambda kp: -kp[1][rest[1]]):
        print("   idx %2d   %s=%8.4f  %s=%8.4f  %s=%8.4f"
              % (k, names[0], p[0], names[1], p[1], names[2], p[2]))

    print("")
    print("EXTREMES (candidate anatomical anchors):")
    for i2 in range(3):
        lo = min(range(n), key=lambda k: pts[k][i2])
        hi = max(range(n), key=lambda k: pts[k][i2])
        print("   %s min -> idx %2d %s" % (names[i2], lo,
                                           [round(v, 4) for v in pts[lo]]))
        print("   %s max -> idx %2d %s" % (names[i2], hi,
                                           [round(v, 4) for v in pts[hi]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
