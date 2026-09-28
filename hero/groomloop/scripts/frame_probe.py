"""frame_probe.py -- establish the head frame in THIS blend by measurement.

    blender --background <blend> --python this.py --

Every op in the restyle spec is directional -- a whorl at the posterior crown
offset to the character's LEFT, a sweep to his RIGHT, flow DOWN the back. All of
those are meaningless without knowing which axis is up, which is forward and
which way the character faces, and this project has already shipped a groom
whose clump partition used hardcoded Y-up components on a blend that was not
Y-up.

So: measure. The head mesh gives up (the long axis through the skull), forward
(the nose direction, found as the extreme along the horizontal axis with the
narrowest cross-section), and side follows by cross product.
"""

import json

import bpy
import numpy as np


def main():
    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    curves = [o for o in bpy.data.objects
              if o.type == "CURVES" and len(o.data.curves) > 0]
    cu = max(curves, key=lambda o: len(o.data.curves))
    d = cu.data
    n = len(d.points)
    P = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", P)
    P = P.reshape(n, 3).astype(np.float64)
    k = d.curves[0].points_length
    A = P.reshape(-1, k, 3)
    roots, tips = A[:, 0, :], A[:, -1, :]

    rep = {"head_object": head.name, "head_verts": int(V.shape[0]),
           "curves_object": cu.name, "curves": int(A.shape[0]),
           "points_per_curve": int(k)}
    for nm, arr in (("head", V), ("roots", roots), ("tips", tips)):
        rep[nm + "_min"] = [round(float(x), 3) for x in arr.min(0)]
        rep[nm + "_max"] = [round(float(x), 3) for x in arr.max(0)]
        rep[nm + "_mean"] = [round(float(x), 3) for x in arr.mean(0)]

    # UP = the axis with the largest head extent that is NOT the narrowest.
    ext = V.max(0) - V.min(0)
    rep["head_extent"] = [round(float(x), 3) for x in ext]
    up_axis = int(np.argmax(ext))
    # the narrowest axis of a head is LEFT-RIGHT
    side_axis = int(np.argmin(ext))
    fwd_axis = 3 - up_axis - side_axis
    rep["axes_by_extent"] = {"up": up_axis, "side": side_axis,
                             "fwd": fwd_axis}

    # FORWARD SIGN: the nose. Take the head slab around the roots' mean height
    # and ask which end of the forward axis reaches further from the centroid.
    c = V.mean(0)
    band = V[np.abs(V[:, up_axis] - np.median(roots[:, up_axis])) <
             0.22 * ext[up_axis]]
    f = band[:, fwd_axis] - c[fwd_axis]
    rep["fwd_sign"] = 1 if abs(f.max()) > abs(f.min()) else -1
    rep["fwd_reach"] = [round(float(f.min()), 3), round(float(f.max()), 3)]

    # ROOT COVERAGE along up: where the scalp actually is
    rep["root_up_pct"] = [round(float(np.percentile(roots[:, up_axis], p)), 3)
                          for p in (1, 25, 50, 75, 99)]
    rep["head_up_range"] = [round(float(V[:, up_axis].min()), 3),
                            round(float(V[:, up_axis].max()), 3)]
    print("__FR__" + json.dumps(rep))


main()
