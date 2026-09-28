"""rotate_groom.py -- diagnose and correct a groom yawed about the head.

    blender --background <in.blend> --python this.py -- <out.blend> <deg|diagnose>

The operator reports the hair sitting 90 degrees CLOCKWISE on the hero.

MY FRAME CHECK COULD NOT HAVE CAUGHT THAT, and it is worth saying why before
fixing it. `resolve_frame.py` corroborates the frame with "tips hang BELOW their
roots" -- a statement about the UP axis alone. A groom rotated in YAW still has
its tips below its roots, so the corroboration passes untouched. I verified the
one axis that could not be wrong and reported the frame as corroborated.

DIAGNOSE FIRST. A groom yawed by 90 degrees has its mass where its front-back
extent should be and vice versa, so the discriminator is the ASPECT of the tip
cloud in the head's own frame: a correct groom is longer front-to-back than
side-to-side (a head is), and a yawed one is the reverse. The nape/fringe split
is the second reading: the frontmost roots should carry the SHORTEST hair.

Rotation is about the scalp-fit centre and the UP axis, applied to every point
including roots -- so unlike every other op in this pipeline it DOES move roots,
by design, because the whole cloud is in the wrong place. Re-snapping is not
needed: a rotation about the head's own vertical axis keeps roots on a
head-shaped surface, and the measured snap distance is reported so that claim is
checkable rather than assumed.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def fit_sphere(pts):
    A = np.hstack([2 * pts, np.ones((pts.shape[0], 1))])
    sol, *_ = np.linalg.lstsq(A, (pts ** 2).sum(1), rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(1e-9, sol[3] + (c ** 2).sum())))


def describe(A, centre, up, fwd, side, label):
    tips = A[:, -1, :]
    roots = A[:, 0, :]
    rel = tips - centre
    f, s = rel @ fwd, rel @ side
    ext_f = float(np.percentile(f, 95) - np.percentile(f, 5))
    ext_s = float(np.percentile(s, 95) - np.percentile(s, 5))
    L = np.linalg.norm(np.diff(A, axis=1), axis=2).sum(1)
    rf = roots @ fwd
    front = rf > np.percentile(rf, 80)
    back = rf < np.percentile(rf, 20)
    return {
        "label": label,
        "tip_extent_frontback_cm": round(ext_f, 3),
        "tip_extent_leftright_cm": round(ext_s, 3),
        "aspect_fb_over_lr": round(ext_f / max(1e-6, ext_s), 4),
        "len_front_roots_cm": round(float(L[front].mean()), 3),
        "len_back_roots_cm": round(float(L[back].mean()), 3),
        "front_over_back_len": round(
            float(L[front].mean() / max(1e-6, L[back].mean())), 4),
    }


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend, arg = tail[0], tail[1]

    ob = pick_curves_object(bpy)
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    k = d.curves[0].points_length
    A = buf.reshape(n, 3).astype(np.float64).reshape(-1, k, 3)

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    up = np.array([0.0, 0.0, 1.0])
    fwd = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fwd)
    centre, R = fit_sphere(A[:, 0, :])

    rep = {"scalp_centre": [round(float(x), 3) for x in centre],
           "scalp_R_cm": round(R, 3),
           "head_extent_frontback_cm": round(
               float((V @ fwd).max() - (V @ fwd).min()), 3),
           "head_extent_leftright_cm": round(
               float((V @ side).max() - (V @ side).min()), 3)}
    rep["before"] = describe(A, centre, up, fwd, side, "as-is")

    if arg == "diagnose":
        for deg in (-90.0, 90.0, 180.0):
            th = np.radians(deg)
            c, s = np.cos(th), np.sin(th)
            rel = A - centre
            x, y = rel @ side, rel @ fwd
            z = rel @ up
            rot = (centre + np.stack([x * c - y * s, x * s + y * c, z], -1)
                   @ np.stack([side, fwd, up]))
            rep["if_%+d" % int(deg)] = describe(rot, centre, up, fwd, side,
                                                "%+d deg" % int(deg))
        print("__ROT__" + json.dumps(rep))
        return

    deg = float(arg)
    th = np.radians(deg)
    c, s = np.cos(th), np.sin(th)
    rel = A - centre
    x, y, z = rel @ side, rel @ fwd, rel @ up
    B = centre + np.stack([x * c - y * s, x * s + y * c, z], -1) @ np.stack(
        [side, fwd, up])
    rep["rotated_deg"] = deg
    rep["after"] = describe(B, centre, up, fwd, side, "%+g deg" % deg)

    # roots must still land on the head. Rotation about the head's own vertical
    # axis should keep them there; MEASURE it rather than asserting it.
    from mathutils import Vector
    mw = head.matrix_world
    inv = mw.inverted()
    dists = []
    for i in range(0, B.shape[0], max(1, B.shape[0] // 400)):
        p = Vector(B[i, 0, :].tolist())
        ok, loc, nrm, idx = head.closest_point_on_mesh(inv @ p)
        if ok:
            dists.append((mw @ loc - p).length)
    dists = np.array(dists)
    rep["root_to_head_cm"] = {"n": int(dists.size),
                              "mean": round(float(dists.mean()), 4),
                              "p90": round(float(np.percentile(dists, 90)), 4),
                              "max": round(float(dists.max()), 4)}

    d.attributes["position"].data.foreach_set(
        "vector", B.reshape(-1, 3).astype(np.float32).ravel())
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["saved"] = out_blend
    print("__ROT__" + json.dumps(rep))


main()
