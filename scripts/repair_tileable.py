"""Make a non-tiling texture tile, deterministically, then RE-RUN THE GATE.

THE METHOD — offset-and-blend, and it is chosen because it is provable
----------------------------------------------------------------------
    A = the original
    B = A rolled by half its width and half its height
    M = a smooth mask, 1 in the centre of A, 0 at A's borders
    result = M*A + (1-M)*B

At A's border M is 0, so the result there IS B. And B at A's border is A's
CENTRE content, which is continuous across that line by construction. So the
result tiles, and it does so for a reason that can be stated rather than
observed.

The cost is honest and worth naming: the blend softens detail in a band around
the old seam, and on a strongly directional texture (planks) it can leave a
faint ghost. That is why the gate is re-run on the OUTPUT rather than the
repair being assumed to work.

WHAT IT WILL NOT DO
-------------------
It never overwrites the operator's authored file. Output is
`<name>_tiled.<ext>` beside the original. A texture that still fails after
repair is REPORTED WITH ITS NUMBER as needs-regeneration, not quietly shipped.

**AND IT CANNOT FIX A DISCONTINUITY IN THE IMAGE'S MIDDLE.** The method works
by substituting the centre content at the borders, so it assumes the centre is
continuous. The first self-test put a hard step at exactly x = w/2, which the
half-offset moves ONTO the border — so B was broken precisely where the blend
depends on it, and the repair moved 74.57x to 69.70x, i.e. nowhere. That is a
real limit, not a bug: a texture with a seam through its middle is a different
defect and needs regenerating, not healing. The self-test now uses a
REPRESENTATIVE non-tiling texture — continuous interior, mismatched edges,
which is what a generated tile actually looks like.

Usage:
    python scripts/repair_tileable.py refs/textures_v1/*.jpg
    python scripts/repair_tileable.py --self-test
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_tileable as vt                        # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blend_mask(h, w, feather=0.35):
    """1 in the centre, 0 at the borders, smooth (raised cosine) between.

    `feather` is the fraction of each axis the ramp occupies at each edge.
    Wider feather = better hiding of the old seam, more softening overall.
    """
    def axis(n):
        x = np.linspace(0.0, 1.0, n, endpoint=False)
        f = max(feather, 1e-6)
        r = np.ones(n)
        lo = x < f
        hi = x > (1.0 - f)
        r[lo] = 0.5 - 0.5 * np.cos(np.pi * x[lo] / f)
        r[hi] = 0.5 - 0.5 * np.cos(np.pi * (1.0 - x[hi]) / f)
        return r
    return np.outer(axis(h), axis(w))


def repair(a, feather=0.35):
    h, w = a.shape[:2]
    b = np.roll(np.roll(a, h // 2, axis=0), w // 2, axis=1)
    m = blend_mask(h, w, feather)[..., None]
    return np.clip(m * a + (1.0 - m) * b, 0.0, 1.0)


def load(p):
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB")).astype(np.float32) / 255.0


def save(a, p):
    Image.fromarray((np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)).save(
        p, quality=95)


def verdict(a):
    rv, rh, _, _ = vt.seam_ratio(a)
    ramp, r2 = vt.light_ramp(a)
    worst = max(rv, rh)
    ok = worst <= vt.SEAM_RATIO_MAX and not (
        ramp > vt.RAMP_MAX and r2 >= vt.RAMP_R2_MIN)
    return worst, ramp, r2, ok


def self_test():
    """Prove the repair actually repairs, on an image built to fail."""
    print("SELF-TEST — repair a REPRESENTATIVE non-tiling texture")
    print("  (continuous interior, mismatched edges: non-integer periods,")
    print("   which is what a generated tile actually looks like)")
    n = 256
    yy, xx = np.mgrid[0:n, 0:n]
    # 4.3 and 3.7 periods -- deliberately NOT integers, so the left edge does
    # not meet the right and the top does not meet the bottom, while the
    # interior stays perfectly smooth.
    det = (0.12 * np.sin(2 * np.pi * 4.3 * xx / n)
           + 0.08 * np.sin(2 * np.pi * 3.7 * yy / n)
           + 0.04 * np.sin(2 * np.pi * 8.3 * (xx + yy) / n))
    a = np.clip(0.5 + np.stack([det, det * .9, det * .8], -1), 0, 1)
    before = verdict(a)
    after = verdict(repair(a))
    print("  before  seam %7.2fx  ok=%s" % (before[0], before[3]))
    print("  after   seam %7.2fx  ok=%s" % (after[0], after[3]))
    good = (not before[3]) and after[3]
    print()
    print("repair %s" % ("WORKS: refused before, passes after"
                         if good else "!! DID NOT FIX THE CASE IT EXISTS FOR"))
    return 0 if good else 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--feather", type=float, default=0.35)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    paths = a.paths or sorted(glob.glob(os.path.join(
        REPO, "refs", "textures_v1", "*.jpg")))
    paths = [p for p in paths if "_tiled." not in os.path.basename(p)]
    if not paths:
        print("NOTHING TO REPAIR — that is 'I could not look', not a pass.")
        return 5

    print("seam repair — offset/blend, feather %.2f, gate bar %.1fx"
          % (a.feather, vt.SEAM_RATIO_MAX))
    print()
    print("  %-18s %10s %10s   %s" % ("texture", "seam before", "seam after",
                                      "verdict"))
    still, done = [], []
    for p in paths:
        img = load(p)
        b_worst, _, _, b_ok = verdict(img)
        rep = repair(img, a.feather)
        w2, ramp2, r2, ok2 = verdict(rep)
        root, ext = os.path.splitext(p)
        out = root + "_tiled" + ext
        save(rep, out)
        print("  %-18s %9.2fx %9.2fx   %s"
              % (os.path.basename(p), b_worst, w2,
                 "REPAIRED" if ok2 else "STILL FAILING"))
        (done if ok2 else still).append((os.path.basename(p), w2))
    print()
    print("  repaired %d of %d -> <name>_tiled%s beside the originals"
          % (len(done), len(paths), ext))
    if still:
        print()
        print("  STILL FAILING AFTER REPAIR — fall back to the role's original")
        print("  Poly Haven map and record as NEEDS REGENERATION:")
        for n, v in still:
            print("      %-20s %.2fx against a %.1fx bar" % (n, v, vt.SEAM_RATIO_MAX))
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
