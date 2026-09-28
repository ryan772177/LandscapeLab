"""land_difflocks.py -- put the generated strands on the hero's head.

    blender --background <hero_base.blend> --python land_difflocks.py -- \
            <out.blend> [strand_frac] [pts_per_strand]

WHAT THIS DOES, in the order the rulings set:

  3.3  AXIS. DiffLocks is Y-up in real metres. The documented swap is
       Blender_X = X, Blender_Y = -Z, Blender_Z = Y, and the facing was
       MEASURED rather than assumed: a scalp is a CAP, so its root centroid
       sits behind the midpoint of the root bounds (-0.0382 against -0.0200),
       which names the back as -Z and the face as +Z. Under the swap that is
       -Y, the hero's own front.

  3.1  SIMILARITY ONLY -- uniform scale, rotation, translation. Solved by
       fitting a sphere to each scalp independently: 0.09172 m against
       9.2274 cm gives 100.600 cm per metre, which is the METRE-TO-CENTIMETRE
       unit conversion recovered from geometry that knew nothing about units.
       Non-uniform scaling stays refused.

  3.4  DECIMATION. 25,841,408 points is far more than groom rendering needs at
       0.32 mm segments. A fraction of the strands, resampled along their own
       arc length. The full-res npz stays canonical on disk; this is a view.

  3.1  SNAP. The residual head-proportion mismatch closes by moving each ROOT
       to the nearest point on the hero's own face mesh, with the strand body
       carried RIGIDLY by that root delta. Rigid, because this project measured
       the alternative: translating points independently drags hair off the
       skull and uncovers scalp, where a rigid carry preserves every point's
       distance from its root.

  AND THE ROOT UVs, which are not optional. Every pack-derived groom this
  project has bound landed on the hero's JAW, and the named cause was the
  absence of `groom_root_uv`: a binding with no root UVs can only project each
  root onto the nearest triangle of the target. The hero's own authored grooms
  carry it and seat correctly. So each root's UV is read from the hero mesh it
  is being snapped to -- the UV belongs to HIS scalp, not to DiffLocks'.
"""

import json
import os
import sys

import bpy
import mathutils
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# THE DEFAULT IS v1 AND THE PATH IS AN ARGUMENT, deliberately.
#
# This was a hardcoded constant until 2026-08-23, when a SECOND generation
# arrived and it became a per-version quantity written as though only one would
# ever exist. That is the same defect the 8K re-terrain hit six times in one
# night -- a droplet count, a cache path, an output name, each fine while there
# was exactly one of the thing. Overwriting the constant would have made v2
# land and silently made v1 unreproducible.
#
# Passed as the FOURTH positional argument; unset keeps the v1 behaviour byte
# for byte, so the existing chain replays unchanged.
NPZ_DEFAULT = "C:/Users/Admin/UE5LandscapePipeline/characters/AlpineHero/grooms/difflocks_raw/hair_output_strands.npz"
NPZ = NPZ_DEFAULT
SURVEY = "C:/Users/Admin/UE5LandscapePipeline/hero/groomloop/survey/survey_head.json"


def resample(P, n_out):
    """Resample each strand to n_out points along its own arc length.

    Not every n-th point: the strands are dense near the root and a fixed
    stride would shorten some and not others. Arc length keeps the tip AT the
    tip, which is what the silhouette is made of.
    """
    n_cur, n_in, _ = P.shape
    seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
    cum = np.concatenate([np.zeros((n_cur, 1)), np.cumsum(seg, axis=1)], axis=1)
    tot = cum[:, -1:]
    tot[tot < 1e-12] = 1e-12
    u = cum / tot
    tgt = np.linspace(0.0, 1.0, n_out)
    out = np.empty((n_cur, n_out, 3), dtype=np.float64)
    for i in range(n_cur):
        for ax in range(3):
            out[i, :, ax] = np.interp(tgt, u[i], P[i, :, ax])
    return out


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend = tail[0]
    frac = float(tail[1]) if len(tail) > 1 else 0.35
    n_pts = int(tail[2]) if len(tail) > 2 else 28
    global NPZ
    if len(tail) > 3 and tail[3]:
        NPZ = tail[3]
    if not os.path.isfile(NPZ):
        raise SystemExit("REFUSE: no payload at %s" % NPZ)

    rep = {"npz": NPZ, "npz_is_default": NPZ == NPZ_DEFAULT,
           "strand_frac": frac, "points_per_strand": n_pts}

    # ---- the hero's own head, already surveyed ---------------------------
    sv = json.load(open(SURVEY, encoding="utf-8"))
    ch = np.array(sv["frame"]["centre"], dtype=np.float64)
    rh = float(sv["frame"]["radius"])
    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    rep["head_object"] = head.name

    # ---- load and decimate ----------------------------------------------
    d = np.load(NPZ)
    P = d[list(d.keys())[0]]
    rep["source_strands"] = int(P.shape[0])
    rep["source_points_per_strand"] = int(P.shape[1])
    # Evenly spaced through the file rather than the first N: the strands are
    # emitted in generation order and a prefix could be one region of scalp.
    step = max(1, int(round(1.0 / frac)))
    idx = np.arange(0, P.shape[0], step)
    P = P[idx].astype(np.float64)
    rep["kept_strands"] = int(P.shape[0])
    rep["kept_frac_actual"] = round(P.shape[0] / rep["source_strands"], 4)
    P = resample(P, n_pts)

    # ---- similarity transform -------------------------------------------
    def swap(p):
        return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)

    def fit_sphere(p):
        m = np.empty((p.shape[0], 4))
        m[:, :3] = 2 * p
        m[:, 3] = 1
        s, *_ = np.linalg.lstsq(m, (p ** 2).sum(1), rcond=None)
        c = s[:3]
        return c, float(np.sqrt(max(s[3] + float((c ** 2).sum()), 1e-12)))

    S = swap(P)
    cs, rs = fit_sphere(S[:, 0, :])
    scale = rh / rs
    T = ch - scale * cs
    S = S * scale + T
    rep["scale_cm_per_m"] = round(scale, 5)
    rep["translate"] = [round(float(v), 4) for v in T]

    # ---- snap roots to HIS mesh, carry bodies rigidly --------------------
    mw = head.matrix_world
    mwi = mw.inverted()
    me = head.data
    uv_layer = me.uv_layers.active
    rep["uv_layer"] = uv_layer.name if uv_layer else None
    if uv_layer is None:
        raise SystemExit("REFUSE: the hero head mesh carries no UV layer, so "
                         "no root UV can be written -- and a groom without "
                         "groom_root_uv binds onto his jaw.")

    # nearest-vertex UV, via a KD tree over the mesh vertices. Each vertex's UV
    # is the mean of its loop UVs, which is stable across a seam-free scalp.
    vert_uv = {}
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            vert_uv.setdefault(vi, []).append(uv_layer.data[li].uv)
    kd = mathutils.kdtree.KDTree(len(me.vertices))
    for i, v in enumerate(me.vertices):
        kd.insert(v.co, i)
    kd.balance()

    roots = S[:, 0, :]
    snapped = np.empty_like(roots)
    uvs = np.empty((roots.shape[0], 2), dtype=np.float64)
    moved = np.empty(roots.shape[0])
    for i in range(roots.shape[0]):
        wp = mathutils.Vector(roots[i])
        ok, loc, nor, _fi = head.closest_point_on_mesh(mwi @ wp)
        sp = mw @ loc if ok else wp
        snapped[i] = (sp.x, sp.y, sp.z)
        moved[i] = (sp - wp).length
        _co, vi, _dist = kd.find(mwi @ sp)
        uu = vert_uv.get(vi)
        if uu:
            uvs[i] = (sum(u[0] for u in uu) / len(uu),
                      sum(u[1] for u in uu) / len(uu))
        else:
            uvs[i] = (0.0, 0.0)
    delta = snapped - roots
    S = S + delta[:, None, :]          # RIGID carry
    rep["snap_cm"] = {"mean": round(float(moved.mean()), 4),
                      "p90": round(float(np.percentile(moved, 90)), 4),
                      "max": round(float(moved.max()), 4)}

    # ---- the previous groom must GO, not merely be hidden ----------------
    # This blend is saved FROM hero_base.blend, which carries the authored
    # 48,000-strand groom. That is MORE curves than the decimated DiffLocks
    # set, and every picker in this loop -- pick_curves_object, preview_hair,
    # the exporter -- takes the largest Curves object. Leaving it in place
    # means every downstream stage silently measures and ships the OLD hair
    # while the log says DiffLocks. Hiding is not enough: the pickers do not
    # consult visibility.
    rep["removed_prior_curves"] = []
    for o in [x for x in bpy.data.objects if x.type == "CURVES"]:
        rep["removed_prior_curves"].append(
            {"name": o.name, "curves": len(o.data.curves)})
        bpy.data.objects.remove(o, do_unlink=True)

    # ---- build the Curves -----------------------------------------------
    hair = bpy.data.hair_curves.new("AlpineHero_DiffLocks_v1")
    ob = bpy.data.objects.new("AlpineHero_DiffLocks_v1", hair)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = head
    ob.matrix_parent_inverse = mw.inverted()
    hair.add_curves([n_pts] * S.shape[0])

    flat = S.reshape(-1, 3).astype(np.float32).ravel()
    hair.attributes["position"].data.foreach_set("vector", flat)

    at = hair.attributes.get("groom_root_uv")
    if at is None:
        at = hair.attributes.new("groom_root_uv", "FLOAT2", "CURVE")
    at.data.foreach_set("vector", uvs.astype(np.float32).ravel())

    r = hair.attributes.get("radius")
    if r is None:
        r = hair.attributes.new("radius", "FLOAT", "POINT")
    r.data.foreach_set("value",
                       np.full(len(hair.points), 0.018, dtype=np.float32))

    ob["GroomProperty"] = {"att_groom_root_uv": "groom_root_uv",
                           "att_groom_width": "radius"}
    ob["difflocks_transform"] = {
        "scale_cm_per_m": rep["scale_cm_per_m"], "translate": rep["translate"],
        "axis_swap": "Blender = (X, -Z, Y) from DiffLocks Y-up metres",
        "_source": "land_difflocks.py, solved against survey_head.json"}

    # ---- verify by reading it BACK, not by trusting the write ------------
    chk = np.zeros(len(hair.points) * 3, dtype=np.float32)
    hair.attributes["position"].data.foreach_get("vector", chk)
    B = chk.reshape(-1, 3)
    rep["readback"] = {
        "curves": len(hair.curves), "points": len(hair.points),
        "z_cm": [round(float(B[:, 2].min()), 2), round(float(B[:, 2].max()), 2)],
        "y_cm": [round(float(B[:, 1].min()), 2), round(float(B[:, 1].max()), 2)],
        "x_cm": [round(float(B[:, 0].min()), 2), round(float(B[:, 0].max()), 2)],
        "attributes": [x.name for x in hair.attributes],
    }
    sb = sv["skull_bands"]
    rep["hero_bands"] = {"neck": sb["neck_cut_up"], "brow": sb["brow_up"],
                         "crown": sb["crown_up"]}
    rr = B.reshape(S.shape)[:, 0, :]
    rep["roots_on_face_pct"] = round(float(
        ((rr[:, 1] < -8.693) & (rr[:, 2] < sb["brow_up"])).mean() * 100), 3)

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["blend"] = out_blend
    rep["ok"] = True
    print("__LAND__" + json.dumps(rep))


if __name__ == "__main__":
    main()
