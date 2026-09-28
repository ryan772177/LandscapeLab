"""sun_exposure.py — which instances does the sun actually reach?

Offline terrain-shadow test. Marches a ray from each instance toward the
sun across the heightmap and reports whether the terrain occludes it.

WHY THIS EXISTS
---------------
The alpine sun sits at **12 degrees elevation**. At that angle a large
fraction of a mountain map is in terrain shadow, and a camera placed
without checking lands in it. This has now cost three verification
captures in a row:

  * `verify_aerial` is a standing open defect — "aimed at a
    rock-and-snow peak with half the frame in shadow".
  * `trunk_base` was placed to inspect a root flare's COLOUR and
    returned two unusable frames, because the trunk is in a shadowed
    hollow and no camera position near it is lit.

A photometric question cannot be answered from an unlit subject, and
"the render looks dark" is not evidence about a material. So the subject
gets chosen by measurement before the camera is placed.

THE SUN VECTOR IS MEASURED, NOT READ FROM THE RECIPE
----------------------------------------------------
`lighting.sun.azimuth_deg` is **285**, and the sun is at bearing
**105** — the field is the light actor's YAW, i.e. the direction light
TRAVELS, not where the sun is. Reading it as a position puts the camera
on the shadowed side, which is precisely the mistake this module exists
to stop making, and I made it twice before measuring.

So `sun_direction()` takes the light's forward vector as measured from
the live editor and returns the direction TOWARD the sun. Pass
`--forward x,y,z` from `Lighting_alpine_Sun.get_actor_forward_vector()`.

Exit codes:
  0  reported
  2  --pick found no lit instance to aim at (a VALID run, no camera emitted)
  (missing/invalid inputs are not caught here -- they raise and exit 1)
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Measured 2026-08-04 from Lighting_alpine_Sun in the live editor:
#   rot (pitch -12.0, yaw -75.0, roll 0.0)
#   forward (0.2531632, -0.9448180, -0.2079117)
# Light TRAVELS along forward, so the sun lies along -forward.
DEFAULT_FORWARD = (0.2531632279912458, -0.9448180294714706,
                   -0.20791169081775934)


def sun_direction(forward=DEFAULT_FORWARD):
    """(bearing_deg, tan_elevation) of the direction TOWARD the sun."""
    fx, fy, fz = [float(v) for v in forward]
    sx, sy, sz = -fx, -fy, -fz
    horiz = math.hypot(sx, sy)
    if horiz <= 1e-9:
        raise ValueError("sun is exactly overhead; no shadow ray defined")
    return math.degrees(math.atan2(sy, sx)), sz / horiz


def shadowed(height_m, origin_m, spacing_m, x_m, y_m, z_m,
             bearing_deg, tan_elev, max_dist_m=3000.0, step_m=None):
    """Boolean array: True where terrain occludes the sun.

    Marches ALL points together, one step at a time, so cost is
    O(points x steps) in numpy rather than a Python loop per instance.
    """
    step_m = step_m or max(spacing_m, 1.0)
    dx = math.cos(math.radians(bearing_deg)) * step_m
    dy = math.sin(math.radians(bearing_deg)) * step_m
    dz = tan_elev * step_m

    n_y, n_x = height_m.shape
    occluded = np.zeros(x_m.shape, dtype=bool)
    cx, cy, cz = x_m.copy(), y_m.copy(), z_m.copy()
    for _ in range(int(max_dist_m / step_m)):
        cx += dx
        cy += dy
        cz += dz
        gx = (cx - origin_m[0]) / spacing_m
        gy = (cy - origin_m[1]) / spacing_m
        inside = (gx >= 0) & (gy >= 0) & (gx <= n_x - 1) & (gy <= n_y - 1)
        if not inside.any():
            break
        ix = np.clip(gx, 0, n_x - 1).astype(np.int64)
        iy = np.clip(gy, 0, n_y - 1).astype(np.int64)
        terrain = height_m[iy, ix]
        occluded |= inside & (terrain > cz)
    return occluded


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Defaults target the SHIPPED 8K world. The old defaults
    # (recipes/alpine.json + foliage/alpine_Conifer.json) were the pre-8K
    # world, and the plan file no longer exists -- a bare run crashed with a
    # FileNotFoundError. alpine_8k.json carries the same sun (az 285, el 12).
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--plan", default=os.path.join(REPO_ROOT, "foliage",
                                                   "alpine_8k_Conifer.json"))
    ap.add_argument("--forward", default=None,
                    help="sun light forward vector 'x,y,z' as MEASURED from "
                         "the editor. Defaults to the 2026-08-04 reading.")
    ap.add_argument("--pick", action="store_true",
                    help="print a LIT instance with lit neighbours, for a "
                         "camera to aim at")
    args = ap.parse_args(argv)

    fwd = DEFAULT_FORWARD
    if args.forward:
        fwd = [float(v) for v in args.forward.split(",")]
    bearing, tan_elev = sun_direction(fwd)
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("sun       : bearing {0:.1f} deg, elevation {1:.1f} deg "
          "(MEASURED forward {2})".format(
              bearing, math.degrees(math.atan(tan_elev)),
              [round(v, 4) for v in fwd]))

    with io.open(args.recipe, encoding="utf-8") as fh:
        recipe = json.load(fh)
    import place_foliage as pf
    height_m, _w, _f, origin_m, spacing_m, _fs = pf.load_inputs(recipe, None)

    with io.open(args.plan, encoding="utf-8") as fh:
        doc = json.load(fh)
    inst = np.asarray(doc["instances"], dtype=np.float64)
    x_m, y_m, z_m = inst[:, 0] / 100.0, inst[:, 1] / 100.0, inst[:, 2] / 100.0
    # Test at ~1.5 m up the trunk: the question is whether the BASE of
    # the tree is lit, not whether its crown is.
    occ = shadowed(height_m, origin_m, spacing_m, x_m, y_m, z_m + 1.5,
                   bearing, tan_elev)
    lit = ~occ
    print("plan      : {0}  {1:,} instances".format(
        os.path.basename(args.plan), len(inst)))
    print("")
    print("  LIT      {0:>9,}  ({1:.1f}%)".format(
        int(lit.sum()), 100.0 * lit.mean()))
    print("  SHADOWED {0:>9,}  ({1:.1f}%)".format(
        int(occ.sum()), 100.0 * occ.mean()))
    print("")
    print("At 12 degrees elevation this is a property of the TERRAIN, not "
          "a lighting defect. It is the reason a verification camera must "
          "pick its subject before it picks its position.")

    if args.pick:
        idx = np.nonzero(lit)[0]
        if idx.size == 0:
            print("")
            print("REFUSE: no lit instance to aim at.")
            return 2
        # Prefer a lit instance with lit NEIGHBOURS, so the frame is not
        # one sunlit tree against a shadowed hillside.
        best, best_n = None, -1
        for i in idx[:: max(1, idx.size // 400)]:
            near = ((np.abs(x_m[idx] - x_m[i]) < 40.0)
                    & (np.abs(y_m[idx] - y_m[i]) < 40.0)).sum()
            if near > best_n:
                best, best_n = i, near
        print("")
        print("PICK: instance {0} at ({1:.1f}, {2:.1f}, {3:.1f}) cm, "
              "{4} other lit instances within 40 m".format(
                  int(best), inst[best, 0], inst[best, 1], inst[best, 2],
                  int(best_n) - 1))   # best_n counts self (delta 0 < 40 m)
        # CAMERA HEIGHT IS EYE HEIGHT ABOVE LOCAL TERRAIN, NOT AN
        # OFFSET FROM THE INSTANCE. The first version put the camera
        # 3.2 m above the tree's base and 13 m away; on a convex crest
        # that aims the whole lower frame into empty air, and the frame
        # came back as a tree silhouetted against sky with no ground at
        # all. I read that as a floating-tree defect and it was a
        # framing error -- terrain under the tree measured 229.99 m
        # against an instance at 229.87 m, i.e. correctly grounded to
        # the 0.12 m sink.
        #
        # So: stand at eye height on the ground you are standing on, far
        # enough back that the surface fills the lower frame, and aim at
        # the BASE rather than up the trunk.
        d = 2500.0
        cx = inst[best, 0] + d * math.cos(math.radians(bearing))
        cy = inst[best, 1] + d * math.sin(math.radians(bearing))
        gx = (cx / 100.0 - origin_m[0]) / spacing_m
        gy = (cy / 100.0 - origin_m[1]) / spacing_m
        n_y, n_x = height_m.shape
        ix = int(min(max(round(gx), 0), n_x - 1))
        iy = int(min(max(round(gy), 0), n_y - 1))
        cz = height_m[iy, ix] * 100.0 + 170.0        # 1.70 m eye height
        tx, ty, tz = inst[best, 0], inst[best, 1], inst[best, 2] + 60.0
        yaw = math.degrees(math.atan2(ty - cy, tx - cx))
        pitch = math.degrees(math.atan2(tz - cz, math.hypot(tx - cx, ty - cy)))
        print("CAMERA: location_cm [{0:.1f}, {1:.1f}, {2:.1f}]  "
              "rotation_deg [{3:.1f}, {4:.1f}, 0.0]".format(
                  cx, cy, cz, pitch, yaw))
        print("        eye height 1.70 m above LOCAL terrain "
              "({0:.2f} m), {1:.0f} m back, aimed 0.6 m above the trunk base"
              .format(height_m[iy, ix], d / 100.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
