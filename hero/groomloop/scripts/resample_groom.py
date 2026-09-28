"""resample_groom.py -- rebuild a landed groom at a different points-per-curve.

    blender --background <in.blend> --python resample_groom.py -- <out.blend> <k>

WHY. The degeneracy hypothesis was tested and ACQUITTED -- min strand 2.69 cm,
zero segments under 1e-2 cm, zero non-finite, and the groom that DRAWS is dirtier
on every one of those measures (min segment 0.0092 cm against ours 0.0806, one
segment under 1e-2, and 166 roots sharing a spot against our 10).

But the same probe found a real difference I had asserted parity on without
measuring: the working groom is **12 points per curve**, not 28. My own pipeline
document says 28/28. So points-per-curve is an untested variable and this makes
it a single-variable test.

Rebuilds rather than edits, because `add_curves` on an EXISTING Curves crashes
Blender 5.2 (EXCEPTION_ACCESS_VIOLATION) -- building fresh is the supported path.
Roots are NOT re-snapped: the existing points already sit where the snap put
them, and re-running closest_point_on_mesh over 100,943 roots costs ten minutes
to reproduce a value that is already correct.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend, k = tail[0], int(tail[1])

    src = pick_curves_object(bpy)
    d = src.data
    n = len(d.points)
    pos = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", pos)
    P = pos.reshape(n, 3).astype(np.float64)
    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    n_cur = len(d.curves)
    k_in = int(sizes[0])
    assert (sizes == k_in).all(), "source is not uniform"
    A = P.reshape(n_cur, k_in, 3)

    uv = np.zeros(n_cur * 2, dtype=np.float32)
    at = d.attributes.get("groom_root_uv")
    if at is None:
        raise SystemExit("REFUSE: source carries no groom_root_uv")
    at.data.foreach_get("vector", uv)
    uv = uv.reshape(n_cur, 2)

    rad = np.zeros(n, dtype=np.float32)
    r = d.attributes.get("radius")
    if r is not None:
        r.data.foreach_get("value", rad)
    rad_val = float(rad[0]) if r is not None else 0.018

    # ARC-LENGTH resample, not every n-th point: a fixed stride shortens some
    # strands and not others, and the tip is what the silhouette is made of.
    seg = np.linalg.norm(np.diff(A, axis=1), axis=2)
    cum = np.concatenate([np.zeros((n_cur, 1)), np.cumsum(seg, axis=1)], axis=1)
    tot = cum[:, -1:].copy()
    tot[tot < 1e-12] = 1e-12
    u = cum / tot
    tgt = np.linspace(0.0, 1.0, k)
    B = np.empty((n_cur, k, 3), dtype=np.float64)
    for i in range(n_cur):
        for ax in range(3):
            B[i, :, ax] = np.interp(tgt, u[i], A[i, :, ax])

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    uvmap = d.surface_uv_map or (head.data.uv_layers.active.name
                                 if head.data.uv_layers.active else "")

    for o in [x for x in bpy.data.objects if x.type == "CURVES"]:
        bpy.data.objects.remove(o, do_unlink=True)

    hair = bpy.data.hair_curves.new("AlpineHero_DiffLocks_k%d" % k)
    ob = bpy.data.objects.new("AlpineHero_DiffLocks_k%d" % k, hair)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = head
    ob.matrix_parent_inverse = head.matrix_world.inverted()
    hair.add_curves([k] * n_cur)
    hair.attributes["position"].data.foreach_set(
        "vector", B.reshape(-1, 3).astype(np.float32).ravel())
    a2 = hair.attributes.get("groom_root_uv") or hair.attributes.new(
        "groom_root_uv", "FLOAT2", "CURVE")
    a2.data.foreach_set("vector", uv.astype(np.float32).ravel())
    r2 = hair.attributes.get("radius") or hair.attributes.new(
        "radius", "FLOAT", "POINT")
    r2.data.foreach_set("value",
                        np.full(len(hair.points), rad_val, dtype=np.float32))
    hair.surface = head
    hair.surface_uv_map = uvmap

    chk = np.zeros(len(hair.points) * 3, dtype=np.float32)
    hair.attributes["position"].data.foreach_get("vector", chk)
    C = chk.reshape(-1, 3).reshape(n_cur, k, 3)
    L = np.linalg.norm(np.diff(C, axis=1), axis=2).sum(1)
    rep = {"in_k": k_in, "out_k": k, "curves": n_cur,
           "points": len(hair.points),
           "strand_len_cm": {"min": round(float(L.min()), 4),
                             "mean": round(float(L.mean()), 4),
                             "max": round(float(L.max()), 4)},
           "surface": hair.surface.name, "surface_uv_map": hair.surface_uv_map,
           "attributes": [x.name for x in hair.attributes]}
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["saved"] = out_blend
    print("__RS__" + json.dumps(rep))


if __name__ == "__main__":
    main()
