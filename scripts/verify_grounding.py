"""verify_grounding.py — how far is every instance from the ground?

Offline, complete, no editor. Reads a placement plan and the heightmap
the recipe was authored against, samples the terrain under every
instance, and reports the signed gap:

    gap > 0   the instance FLOATS that far above the surface
    gap < 0   the instance is SUNK that far into it

WHY A FULL POPULATION AND NOT A SAMPLE
--------------------------------------
The defect this exists to catch is rare by construction. A tree that
floats does so because its XY landed somewhere the planner and the
surface disagree — a seam, an edge, a stale heightmap — and those are a
small fraction of a large set. Sampling 200 of 157,554 instances is
overwhelmingly likely to report a clean bill of health for a map with
hundreds of floaters. So: every instance, every time. It costs about a
second.

WHAT THIS IS NOT
----------------
It is NOT independent of the planner's arithmetic. Both read the same
heightmap and apply the same world transform, so a bug in the SHARED
transform is invisible here and this would report zero gap on a map
where every tree hovers. It catches disagreement between the plan and
the surface, which is a different and narrower claim.

The genuinely independent instrument is the engine: trace down from an
instance and ask the landscape collision where the ground is. That is
`--trace`, which needs a live editor and runs on a sample because it
costs a remote call. Use both — this one for coverage, that one for
truth.

Exit codes:
  0  every instance inside tolerance
  2  the plan or heightmap could not be read
  4  at least one instance outside tolerance
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landscape_spec  # noqa: E402

REPO_ROOT = landscape_spec.REPO_ROOT


def terrain_z_m(height_m, origin_m, spacing_m, x_m, y_m):
    """Bilinear terrain height at world XY, in metres."""
    gx = (x_m - origin_m[0]) / spacing_m
    gy = (y_m - origin_m[1]) / spacing_m
    n_y, n_x = height_m.shape
    gx = np.clip(gx, 0.0, n_x - 1.001)
    gy = np.clip(gy, 0.0, n_y - 1.001)
    x0, y0 = gx.astype(np.int64), gy.astype(np.int64)
    fx, fy = gx - x0, gy - y0
    h00 = height_m[y0, x0]
    h10 = height_m[y0, x0 + 1]
    h01 = height_m[y0 + 1, x0]
    h11 = height_m[y0 + 1, x0 + 1]
    return ((h00 * (1 - fx) + h10 * fx) * (1 - fy)
            + (h01 * (1 - fx) + h11 * fx) * fy)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine.json"))
    ap.add_argument("--plan", action="append", default=None,
                    help="plan JSON; repeatable. Default: every plan the "
                         "recipe names.")
    ap.add_argument("--tolerance-m", type=float, default=0.05,
                    help="allowed |gap| before an instance is a failure")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args(argv)

    with io.open(args.recipe, encoding="utf-8") as fh:
        recipe = json.load(fh)

    # Reuse the PLANNER's own loader rather than re-deriving the frame.
    # Re-deriving it would be a second chance to get origin/spacing
    # wrong, and a disagreement there would show up as a fake grounding
    # error across every instance at once -- noise that looks exactly
    # like the signal. The cost is stated plainly in the docstring: this
    # check is not independent of the planner's transform.
    import place_foliage as pf
    try:
        height_m, _w, _f, origin_m, spacing_m, _fs = pf.load_inputs(
            recipe, None)
    except Exception as exc:
        print("REFUSE: cannot load terrain inputs: {0}".format(exc))
        return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("terrain   : {0}x{1} cells, {2:.2f} m grid, origin {3}".format(
        height_m.shape[1], height_m.shape[0], spacing_m,
        [round(v, 1) for v in origin_m]))
    print("tolerance : +/- {0:.3f} m".format(args.tolerance_m))
    print("")

    plans = args.plan
    if not plans:
        plans = []
        fol = os.path.join(REPO_ROOT, "foliage")
        for sp in (recipe.get("foliage") or {}).get("species") or []:
            if sp.get("system") == "grass":
                continue
            p = os.path.join(fol, "{0}_{1}.json".format(
                recipe["biome_id"], sp["name"]))
            if os.path.isfile(p):
                plans.append(p)

    rc = 0
    print("{0:<14} {1:>9} {2:>9} {3:>9} {4:>9} {5:>9} {6:>8}".format(
        "species", "count", "mean m", "p50 m", "p99 m", "max m", "outside"))
    for path in plans:
        with io.open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        inst = np.asarray(doc["instances"], dtype=np.float64)
        if inst.size == 0:
            continue
        x_m, y_m, z_m = inst[:, 0] / 100.0, inst[:, 1] / 100.0, inst[:, 2] / 100.0
        ground = terrain_z_m(height_m, origin_m, spacing_m, x_m, y_m)
        raw = z_m - ground
        # THE EXPECTED OFFSET IS NOT A CONSTANT, AND MY FIRST VERSION
        # ASSUMED IT WAS. A rock is lifted by its pivot offset and sunk
        # by its embed depth, and BOTH scale with the per-instance
        # scale, which the plan stores in column 6:
        #
        #     expected = -base_offset*scale - embed_frac*mesh_h*scale
        #
        # Treating `pivot_base_offset_m` as a flat correction reported
        # 582 of 759 boulders "outside tolerance" on a placement that
        # was correct — a check wrong in a way that MANUFACTURES
        # failures is worse than no check, because someone acts on it.
        declared = doc.get("pivot_base_offset_m")
        if declared is None:
            # Vegetation: sits on the surface, less its DECLARED sink.
            # A deliberate 0.12 m sink and a 0.12 m error look identical
            # to a check that assumes zero, so the plan states which.
            expected = np.full_like(
                raw, -float(doc.get("sink_depth_m", 0.0) or 0.0))
        else:
            scale = inst[:, 6]
            embed_m = float(doc.get("embed_depth_per_scale_m", 0.0) or 0.0)
            # THE EMBED IS ALONG THE SURFACE NORMAL, NOT STRAIGHT
            # DOWN. `rock_scatter` sinks by `depth * nvec.z`, so on a
            # slope the VERTICAL component is smaller than the depth,
            # and the expectation below (which assumes vertical) is
            # systematically shallow by `depth * (1 - nvec.z)`.
            #
            # I TRIED TO RECONSTRUCT nvec.z FROM THE PLAN AND IT IS NOT
            # THERE. The engine builds up.z = cos(roll)*cos(pitch)
            # (RotationTranslationMatrix.h:82-84), and `orient_to_normal`
            # inverts exactly that, so pitch/roll SHOULD give the normal
            # back. They do not: `tumble_deg` (12 degrees for Boulder)
            # is added to pitch and roll AFTER the solve, deliberately,
            # so a rock does not sit perfectly flush. Using the identity
            # anyway made agreement WORSE — 5 outliers became 44, max
            # 0.103 m became 0.128 m — which is how I found out.
            #
            # An identity that holds inside a solver does not survive a
            # later stage perturbing its output. So instead of inventing
            # the normal, the residual is BOUNDED and allowed for
            # explicitly below.
            expected = -float(declared) * scale - embed_m * scale
        gap = raw - expected
        # A DERIVED allowance, not a widened tolerance. The embed acts
        # along the normal and the expectation assumes vertical, so the
        # unavoidable residual is `embed * scale * (1 - cos(tilt))`.
        # `tilt` here is the instance's TOTAL tilt from the plan, which
        # includes tumble — it overstates the surface component and so
        # errs toward admitting, but it is derived from the geometry
        # rather than chosen to make the run go green.
        allow = np.full_like(gap, args.tolerance_m)
        if declared is not None:
            tilt = np.hypot(np.radians(inst[:, 4]), np.radians(inst[:, 5]))
            allow = allow + embed_m * scale * (1.0 - np.cos(tilt))
        bad = np.abs(gap) > allow
        n_bad = int(bad.sum())
        if n_bad:
            rc = 4
        print("{0:<14} {1:>9,} {2:>9.3f} {3:>9.3f} {4:>9.3f} {5:>9.3f} "
              "{6:>8,}".format(
                  doc.get("species", "?"), len(inst), float(gap.mean()),
                  float(np.percentile(gap, 50)),
                  float(np.percentile(np.abs(gap), 99)),
                  float(np.abs(gap).max()), n_bad))
        if n_bad:
            order = np.argsort(-np.abs(gap))[:args.top]
            print("     worst {0} of {1:,} outside tolerance:".format(
                min(args.top, n_bad), n_bad))
            for i in order:
                print("       gap {0:+8.3f} m at world ({1:10.1f}, {2:10.1f}) "
                      "cm   terrain {3:8.2f} m   instance {4:8.2f} m".format(
                          gap[i], inst[i, 0], inst[i, 1], ground[i], z_m[i]))
    print("")
    if rc:
        print("Instances lie outside tolerance. NOTE this shares the "
              "heightmap and world transform with the planner, so it "
              "measures PLAN-vs-SURFACE disagreement, not absolute "
              "grounding in the engine.")
    else:
        print("Every instance is within tolerance of the authored surface. "
              "This does NOT prove grounding in the engine — the planner "
              "and this check read the same heightmap through the same "
              "transform, so a shared-transform error is invisible to both.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
