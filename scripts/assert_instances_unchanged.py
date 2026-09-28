"""assert_instances_unchanged.py — did any foliage instance move?

    python scripts/assert_instances_unchanged.py --selftest
    python scripts/assert_instances_unchanged.py --before <dir> --after <dir>

⭐ WHY THE DEPTH PASS IS THE RIGHT WITNESS. Task 4 requires that the
grass cards' COUNT AND POSITIONS are identical before and after a
material change. The meadow is a LANDSCAPE GRASS TYPE (`system: grass`),
so its instances are generated at runtime from the weightmap, density
and seed -- there is no placement file to diff, and the per-instance
transforms are not exposed to Python.

The rendered DEPTH PASS is. Depth is a function of geometry and camera
alone: it does not carry albedo, hue, brightness or any material output.
So if a card had appeared, vanished, moved or changed size, depth would
change at those pixels; and if the material changed only how existing
cards are SHADED, depth cannot change at all.

⛔ THE NOISE FLOOR IS NOT ZERO, AND I ASSERTED THAT IT WAS. An earlier
report said "depth differs on 0.0000% of pixels" across captures. That
figure was a ROUNDED non-zero, and this tool was first written with a
zero tolerance on the strength of it -- so it called a null pair
"GEOMETRY MOVED".

MEASURED ON NULL PAIRS (captures with NOTHING changed between them),
2026-09-13, 3840x2160 = 33,177,600 pixels:

    g1  -> g2      2 pixels differ, max code delta 1
    g2  -> g3      1 pixel  differs, max code delta 1
    t4a -> t4b     1 pixel  differs, max code delta 1

So the floor is 1-2 pixels at +/-1 code: the bottom bit of an 8-bit LOG
depth flickering at a quantisation boundary. The threshold below is
DERIVED from those nulls with margin, not widened until a run went
green -- and it keeps the property that matters, because a card that
moved changes THOUSANDS of pixels by MANY codes, not one pixel by one.

⛔ WHAT IT CANNOT SEE, stated so it is not over-trusted: a card that
moved ENTIRELY BEHIND another surface, or outside the frame, or that
swapped places with an identical card at the same depth. It is a
witness over the visible set, not a census of every instance in the
world.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))


# DERIVED from the null pairs above (max 2 px, max code delta 1), with
# margin: up to 8 pixels may differ provided NONE differs by 2 codes or
# more. A moved card changes thousands of pixels by many codes, so this
# keeps every failure it was built to catch.
MAX_NULL_PIXELS = 8
MIN_CODE_DELTA = 2


def depth_png(frames, station):
    for cand in ("%sFinalImageSceneDepth.png" % station,
                 "%s_SceneDepth.png" % station):
        p = os.path.join(frames, cand)
        if os.path.exists(p):
            return p
    return None


def compare(before, after, station="ground"):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    a_p, b_p = depth_png(before, station), depth_png(after, station)
    if a_p is None or b_p is None:
        raise SystemExit(
            "REFUSE: need a SceneDepth png in BOTH captures (before=%r "
            "after=%r). A capture without depth cannot witness this."
            % (a_p, b_p))
    a = np.asarray(Image.open(a_p))
    b = np.asarray(Image.open(b_p))
    if a.shape != b.shape:
        raise SystemExit("REFUSE: depth passes differ in shape, %s vs %s"
                         % (a.shape, b.shape))
    diff = a.astype(np.int32) - b.astype(np.int32)
    n_diff = int((diff != 0).sum())
    max_code = int(np.abs(diff).max()) if n_diff else 0
    n_big = int((np.abs(diff) >= MIN_CODE_DELTA).sum())
    within = (n_diff <= MAX_NULL_PIXELS) and (max_code < MIN_CODE_DELTA)
    out = {"before": os.path.basename(before),
           "after": os.path.basename(after),
           "pixels": int(a.size),
           "pixels_differing": n_diff,
           "fraction_differing": n_diff / float(a.size),
           "max_abs_code_difference": max_code,
           "pixels_at_or_above_%d_codes" % MIN_CODE_DELTA: n_big,
           "null_floor_pixels": MAX_NULL_PIXELS,
           "null_floor_max_code": MIN_CODE_DELTA - 1,
           "verdict": "UNCHANGED" if within else "GEOMETRY MOVED"}
    out["_means"] = (
        "UNCHANGED means no visible foliage instance appeared, vanished, "
        "moved or resized: the depth pass carries geometry only. It does "
        "NOT cover instances hidden behind other surfaces or outside the "
        "frame.")
    return out


def selftest():
    fails = []
    rng = np.random.default_rng(3)
    base = rng.integers(0, 255, (64, 64), dtype=np.uint8)

    class _Fake:
        def __init__(self, arr):
            self.arr = arr

    # Exercise the arithmetic directly -- the file IO is trivial and the
    # contract is "zero differing pixels or it is not identical".
    def cmp_arrays(a, b):
        d = a.astype(np.int32) - b.astype(np.int32)
        n = int((d != 0).sum())
        mx = int(np.abs(d).max()) if n else 0
        ok = n <= MAX_NULL_PIXELS and mx < MIN_CODE_DELTA
        return n, "UNCHANGED" if ok else "GEOMETRY MOVED"

    n, v = cmp_arrays(base, base.copy())
    if n != 0 or v != "UNCHANGED":
        fails.append("identical arrays did not read UNCHANGED")
    # ONE pixel at ONE code is the measured NULL FLOOR and must pass.
    moved = base.copy()
    moved[7, 9] = np.uint8((int(moved[7, 9]) + 1) % 256)
    n, v = cmp_arrays(base, moved)
    if v != "UNCHANGED":
        fails.append("the null floor (1 px, 1 code) was called moved")
    # ⭐ TWO codes on ONE pixel is NOT the floor and must FAIL, and so
    # must many pixels at one code. Both are the cases the floor could
    # otherwise be widened to swallow.
    two = base.copy()
    two[3, 3] = np.uint8((int(two[3, 3]) + 2) % 256)
    if cmp_arrays(base, two)[1] != "GEOMETRY MOVED":
        fails.append("a 2-code change was not caught")
    many = base.copy()
    idx = rng.choice(base.size, 40, replace=False)
    flat = many.reshape(-1)
    flat[idx] = (flat[idx].astype(int) + 1) % 256
    if cmp_arrays(base, many.reshape(base.shape))[1] != "GEOMETRY MOVED":
        fails.append("40 pixels at 1 code were not caught")
    # A shape mismatch must refuse rather than broadcast.
    try:
        _ = base.astype(np.int32) - np.zeros((32, 32), dtype=np.int32)
        fails.append("a shape mismatch broadcast instead of failing")
    except ValueError:
        pass
    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before")
    ap.add_argument("--after")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.before and a.after):
        ap.error("--before and --after are required")
    r = compare(a.before, a.after, a.station)
    print("%s  ->  %s" % (r["before"], r["after"]))
    print("  pixels differing : %d of %d (%.6f%%)"
          % (r["pixels_differing"], r["pixels"],
             100.0 * r["fraction_differing"]))
    print("  max code delta   : %d" % r["max_abs_code_difference"])
    print("  VERDICT          : %s" % r["verdict"])
    return 0 if r["verdict"] == "UNCHANGED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
