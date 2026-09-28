"""probe_geometry.py -- Phase 0 continued. Where is this hair, and what shape?

    blender --background --python probe_geometry.py -- <abc> <out_json>

The .abc arrived with no surface, no root UVs and an identity matrix, so the
head is not given to us -- it has to be INFERRED from the strand roots. Hair
roots lie on a scalp, so their point cloud IS the scalp, and its centroid and
extent give us the head frame that every region mask will be built on.

It also answers the questions the first recon raised rather than assuming:
  - which axis is up (the roots' thinnest principal direction is the scalp
    normal only near the crown, so instead we use the ROOT-TO-TIP mean, which
    for a groom under gravity points down)
  - what the points-per-curve histogram really looks like, and how many
    degenerate 1-point curves there are (UE asserts >= 2)
  - the curve_type values actually present
  - strand length distribution, which tells fringe from nape
  - the radius range, since radius is the only width carrier in this file
"""

import json
import math
import os
import sys

import bpy

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pick_curves import pick_curves_object
import mathutils


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return round(sorted_vals[i], 5)


def main():
    tail = argv_tail()
    abc, out = tail[0], tail[1]
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.wm.alembic_import(filepath=abc, as_background_job=False)

    ob = pick_curves_object(bpy)
    d = ob.data
    n = len(d.curves)
    rep = {"object": ob.name, "curves": n, "points": len(d.points)}

    sizes = [c.points_length for c in d.curves]
    starts = [c.first_point_index for c in d.curves]

    hist = {}
    for s in sizes:
        hist[s] = hist.get(s, 0) + 1
    rep["points_per_curve_histogram"] = {str(k): hist[k] for k in sorted(hist)}
    rep["degenerate_1pt_curves"] = hist.get(1, 0)
    rep["curves_under_2pts"] = sum(v for k, v in hist.items() if k < 2)

    # curve_type values actually present. Blender: 0 CATMULL_ROM, 1 POLY,
    # 2 BEZIER, 3 NURBS. Guessing this wrong changes what an edit does.
    tvals = {}
    at = d.attributes.get("curve_type")
    if at is not None:
        for i in range(n):
            v = int(at.data[i].value)
            tvals[v] = tvals.get(v, 0) + 1
    rep["curve_type_counts"] = {str(k): v for k, v in sorted(tvals.items())}
    rep["curve_type_legend"] = {"0": "CATMULL_ROM", "1": "POLY",
                                "2": "BEZIER", "3": "NURBS"}

    pos = d.attributes["position"].data
    rad = d.attributes.get("radius")

    roots, tips, lengths, radii = [], [], [], []
    for i in range(n):
        s, sz = starts[i], sizes[i]
        if sz < 1:
            continue
        p0 = mathutils.Vector(pos[s].vector)
        p1 = mathutils.Vector(pos[s + sz - 1].vector)
        roots.append(p0)
        tips.append(p1)
        L = 0.0
        for k in range(sz - 1):
            L += (mathutils.Vector(pos[s + k + 1].vector)
                  - mathutils.Vector(pos[s + k].vector)).length
        lengths.append(L)
        if rad is not None:
            radii.append(float(rad.data[s].value))

    def axis_stats(vs, label):
        o = {}
        for ax, nm in enumerate("xyz"):
            vals = sorted(v[ax] for v in vs)
            o[nm] = {"min": pct(vals, 0.0), "p05": pct(vals, 0.05),
                     "p50": pct(vals, 0.5), "p95": pct(vals, 0.95),
                     "max": pct(vals, 1.0),
                     "mean": round(sum(vals) / len(vals), 5)}
        rep[label] = o

    axis_stats(roots, "root_stats")
    axis_stats(tips, "tip_stats")

    sl = sorted(lengths)
    rep["strand_length"] = {"min": pct(sl, 0), "p05": pct(sl, .05),
                            "p25": pct(sl, .25), "p50": pct(sl, .5),
                            "p75": pct(sl, .75), "p95": pct(sl, .95),
                            "max": pct(sl, 1.0),
                            "mean": round(sum(sl) / len(sl), 5)}
    if radii:
        sr = sorted(radii)
        rep["root_radius"] = {"min": pct(sr, 0), "p50": pct(sr, .5),
                              "max": pct(sr, 1.0)}

    # ROOT CLOUD = THE SCALP. Centroid and the mean root->tip direction, which
    # under gravity points DOWN and so names the up axis without assuming one.
    c = mathutils.Vector((0, 0, 0))
    for r in roots:
        c += r
    c /= len(roots)
    rep["root_centroid"] = [round(v, 5) for v in c]

    mean_dir = mathutils.Vector((0, 0, 0))
    for r, t in zip(roots, tips):
        v = t - r
        if v.length > 1e-9:
            mean_dir += v.normalized()
    mean_dir /= len(roots)
    rep["mean_root_to_tip_unit"] = [round(v, 5) for v in mean_dir]
    ax = max(range(3), key=lambda i: abs(mean_dir[i]))
    rep["inferred_down_axis"] = "xyz"[ax]
    rep["inferred_down_sign"] = 1 if mean_dir[ax] > 0 else -1
    rep["inferred_up_axis"] = "xyz"[ax]
    rep["inferred_up_sign"] = -rep["inferred_down_sign"]

    # Root spread per axis tells which two axes span the scalp.
    spread = {}
    for i, nm in enumerate("xyz"):
        vals = [r[i] for r in roots]
        spread[nm] = round(max(vals) - min(vals), 5)
    rep["root_spread"] = spread

    # OUTLIER CHECK. The scene bbox Y span (2.52) is twice X/Z, which for a
    # head of hair is not a shape -- it is either a stray or a real curtain.
    # Count how many TIPS sit beyond p99 on each axis so a handful of flyaways
    # cannot be mistaken for the groom's real extent.
    for i, nm in enumerate("xyz"):
        vals = sorted(t[i] for t in tips)
        lo, hi = pct(vals, 0.01), pct(vals, 0.99)
        rep.setdefault("tip_p01_p99", {})[nm] = [lo, hi]
        rep.setdefault("tips_beyond_p99", {})[nm] = sum(
            1 for v in vals if v > hi or v < lo)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print("__PROBE__" + json.dumps({"ok": True, "out": out}))


if __name__ == "__main__":
    main()
