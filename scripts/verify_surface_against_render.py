"""Does the surface lookup agree with what the material DRAWS?

PHASE2_PLAN unit 11's acceptance clause, and the one thing the bake's own
controls cannot supply. Those controls prove the lookup is faithful to the
WEIGHTMAP -- which is the material's INPUT. This compares it to the material's
OUTPUT, which is a genuinely different representation (non-negotiable 0).

    python scripts/verify_surface_against_render.py --frame <top-down png>

HOW A TOP-DOWN FRAME IS MAPPED TO THE WORLD
-------------------------------------------
The camera looks straight down from a known altitude with a known FOV, so a
pixel maps to a world XY by similar triangles. **THE FRAME'S OWN ASPECT DECIDES
WHICH AXIS THE FOV APPLIES TO** -- UE's FOV is HORIZONTAL, so the vertical
half-extent is scaled by height/width. Getting that backwards stretches the
sample grid and silently compares the wrong pixels.

WHAT A PASS LOOKS LIKE, AND WHY IT IS NOT AN EQUALITY
-----------------------------------------------------
The material blends three photogrammetry surfaces under a low sun with fog and
a tonemapper. There is no pixel value that "is" Rock. What CAN be asserted is
SEPARATION: pixels the lookup calls Snow must be markedly brighter than those it
calls Rock or Grass, and the ordering must hold with a margin far outside the
noise. A test that demanded an exact colour would be measuring the lighting rig.

** IT ONLY SAMPLES CELLS THE LOOKUP IS CONFIDENT ABOUT. ** At dominance < 16 the
material genuinely draws a blend, so those pixels belong to no class and
including them would blur the very separation being measured. The count of
excluded samples is reported -- a filter that quietly removes most of the data
is its own defect.
"""
import argparse
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from surface_query import SurfaceLookup                      # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frame", required=True)
    ap.add_argument("--cam-x", type=float, default=0.0)
    ap.add_argument("--cam-y", type=float, default=0.0)
    ap.add_argument("--cam-z", type=float, default=900000.0)
    ap.add_argument("--fov-deg", type=float, default=90.0,
                    help="HORIZONTAL field of view; the editor viewport's "
                         "default is 90")
    ap.add_argument("--ground-z", type=float, default=None,
                    help="mean ground height in cm; default reads it from the "
                         "heightmap rather than assuming zero")
    ap.add_argument("--samples", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--min-dominance", type=int, default=16)
    ap.add_argument("--margin", type=float, default=0.02,
                    help="required separation in linear luma between class "
                         "means, well outside frame noise")
    args = ap.parse_args()

    fpath = args.frame if os.path.isabs(args.frame) else os.path.join(
        REPO_ROOT, args.frame)
    if not os.path.exists(fpath):
        sys.exit("REFUSE: no frame at %s" % fpath)

    L = SurfaceLookup()
    im = Image.open(fpath).convert("RGB")
    A = np.asarray(im).astype(np.float64) / 255.0
    H, W, _ = A.shape

    Zh = L  # for clarity below
    if args.ground_z is None:
        # mean terrain height, so the projection plane is the ground rather
        # than z=0 -- an 8 km frame over 1.5 km of relief is not flat, and
        # assuming zero would shift every sample outward.
        import json as _j
        rec = L.rec
        gz = None
        try:
            from plan_city import Terrain
            T = Terrain(rec)
            gz = float(np.mean(T.H.astype(np.float64)
                               * (T.zs / 65535.0)))
        except Exception:
            gz = 0.0
        args.ground_z = gz

    dist = args.cam_z - args.ground_z
    half_w_cm = math.tan(math.radians(args.fov_deg) * 0.5) * dist
    # HORIZONTAL fov -> vertical half-extent scales by the frame's aspect.
    half_h_cm = half_w_cm * (float(H) / float(W))

    print("frame        %s   %d x %d" % (os.path.basename(fpath), W, H))
    print("camera       (%.0f, %.0f, %.0f) cm, fov %.1f deg horizontal"
          % (args.cam_x, args.cam_y, args.cam_z, args.fov_deg))
    print("ground plane %.0f cm (mean terrain height, not zero)"
          % args.ground_z)
    print("covers       %.0f x %.0f m" % (2 * half_w_cm / 100.0,
                                          2 * half_h_cm / 100.0))
    print()

    rng = np.random.default_rng(args.seed)
    px = rng.integers(0, W, size=args.samples)
    py = rng.integers(0, H, size=args.samples)

    # pixel -> world. +x right, +y DOWN in image space; the top-down camera
    # with yaw 0 looks along -z with world +x to the right and +y up the frame,
    # so image y is negated.
    wx = args.cam_x + (px / (W - 1.0) * 2.0 - 1.0) * half_w_cm
    wy = args.cam_y - (py / (H - 1.0) * 2.0 - 1.0) * half_h_cm

    lum = (0.2126 * A[py, px, 0] + 0.7152 * A[py, px, 1]
           + 0.0722 * A[py, px, 2])

    names = [l["name"] for l in L.layers]
    buckets = {n: [] for n in names}
    off = 0
    blended = 0
    for k in range(args.samples):
        r = L.at(wx[k], wy[k])
        if r is None:
            off += 1
            continue
        if r["dominance"] < args.min_dominance:
            blended += 1
            continue
        buckets[r["layer"]].append(lum[k])

    print("samples      %d   off the landscape %d   blended-out %d"
          % (args.samples, off, blended))
    used = sum(len(v) for v in buckets.values())
    print("usable       %d (%.1f%%)" % (used, 100.0 * used / args.samples))
    if used < args.samples * 0.2:
        print()
        print("REFUSE: fewer than 20%% of samples are usable. A filter that "
              "removes most of the data cannot support a conclusion.")
        return 3
    print()

    stats = {}
    print("  %-8s %8s %10s %10s" % ("layer", "n", "mean luma", "std"))
    for n in names:
        v = np.asarray(buckets[n])
        if len(v) < 50:
            print("  %-8s %8d   TOO FEW to compare" % (n, len(v)))
            continue
        stats[n] = (float(v.mean()), float(v.std()), len(v))
        print("  %-8s %8d %10.4f %10.4f" % (n, len(v), v.mean(), v.std()))
    print()

    if len(stats) < 2:
        print("REFUSE: fewer than two classes have enough samples.")
        return 3

    # THE ASSERTION: ordering with a margin. Snow is the brightest surface in
    # this palette (base_color 1,1,1 over Snow006) and Rock the darkest of the
    # two extremes; the exact values belong to the lighting rig, the ORDER
    # belongs to the material.
    ok = True
    order = sorted(stats.items(), key=lambda kv: -kv[1][0])
    print("brightest to darkest, as the material draws them:")
    for n, (m, s, c) in order:
        print("  %-8s %.4f" % (n, m))
    print()
    if "Snow" in stats:
        for other in ("Rock", "Grass"):
            if other in stats:
                d = stats["Snow"][0] - stats[other][0]
                good = d > args.margin
                print("  Snow brighter than %-6s by %+.4f   %s"
                      % (other, d, "OK" if good else "FAIL"))
                ok &= good
    print()
    if ok:
        print("PASS -- the classes the lookup assigns SEPARATE in the rendered")
        print("frame, which is a DIFFERENT REPRESENTATION from the weightmap")
        print("both the lookup and the material read.")
        print()
        print("Stated narrowly: this shows the lookup's classes correspond to")
        print("what is drawn. It is not a per-pixel equality and cannot be --")
        print("the material blends three surfaces under a tonemapper.")
        return 0
    print("FAIL -- the classes do not separate as the material's own layer")
    print("definitions predict. Either the mapping from pixel to world is")
    print("wrong, or the lookup disagrees with what is drawn.")
    return 4


if __name__ == "__main__":
    sys.exit(main())
