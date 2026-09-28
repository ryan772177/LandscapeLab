"""restyle_p1.py -- PASS 1, STRUCTURE: whorl, radial redirection, departing flow,
crown crisscross.

    blender --background <in.blend> --python this.py -- <out.blend> <params.json>

SPEC -> MECHANISM (this mapping is the deliverable, not the knob values):

  spec 1  one dominant whorl at the posterior crown, offset to his LEFT
          -> a whorl POINT on the fitted scalp sphere at
             normalize(-fwd*back + up*rise + side*left). `side` is measured as
             cross(up, fwd) and is the character's own left.
  spec 1  guides radiate outward from it
          -> for each root, the great-circle tangent pointing AWAY from the
             whorl is computed on the sphere, and the strand is ROTATED ABOUT
             ITS ROOT toward it.
  spec 1  back and sides flow downward with slight flare, lifting off the neck
          -> the target direction blends that radial tangent with -up (down)
             and +normal (flare). The down term ramps with depth below the
             crown, so the crown radiates and the nape falls.
  spec 2  eliminate the hard part; crisscross across the sagittal axis
          -> a lateral term that points ACROSS the midline, signed by which
             side the root is on and belled around the midline, so left-rooted
             strands travel right and right-rooted strands travel left and the
             two interleave.

EVERYTHING IS A ROTATION ABOUT THE ROOT. p' = root + R(p - root). That preserves
each strand's LENGTH and the SHAPE of its curl exactly, and it cannot move a
root -- which the seating proof depends on. The length pass already spent the
one liberty worth taking with strand geometry; structure gets none.

The rotation is CLAMPED per strand (`max_turn_deg`). An unclamped alignment
would rotate a strand that already disagrees with the field by 150 degrees and
fling it through the skull.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "scripts", "blender"))
from head_frame import measure_head

P = {
    "whorl_back": 0.55,        # how far behind centre the whorl sits
    "whorl_rise": 0.78,        # how high
    "whorl_left": 0.30,        # + = character's LEFT
    "radial": 0.85,            # azimuthal swirl away from the whorl
    "down": 0.55,              # EXTRA -up, ramped by depth below crown
    "down_ramp": 1.6,
    "standoff": 0.55,          # weight of the scalp normal: silhouette off skull
    "flare": 0.10,             # extra normal push
    "cross": 1.30,             # crisscross across the midline
    "cross_width": 3.2,        # cm, bell half-width around the sagittal plane
    "part_strip_cm": 1.6,      # half-width of the strip the part is measured in
    "part_offset_cm": 5.0,     # where the comparison bands sit, either side
    "cross_up_lo": 0.35,       # only above this normal-dot-up does cross apply
    "strength": 0.75,          # 0..1 blend toward the target direction
    "max_turn_deg": 42.0,
    "front_hold": 0.55,        # how much the fringe band is EXEMPTED (P2 owns it)
    "seed": 20260823,
}


def fit_sphere(pts):
    A = np.hstack([2 * pts, np.ones((pts.shape[0], 1))])
    b = (pts ** 2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(1e-9, sol[3] + (c ** 2).sum())))


def unit(v, eps=1e-12):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def rodrigues(v, axis, ang):
    """Rotate rows of v about per-row axis by per-row angle."""
    k = unit(axis)
    c = np.cos(ang)[:, None]
    s = np.sin(ang)[:, None]
    return (v * c + np.cross(k, v) * s
            + k * (k * v).sum(1, keepdims=True) * (1.0 - c))


def scalp_visible(pts, centre, up, R, nb=48, cap=0.45, lift=1.03):
    """Fraction of upper-scalp angular cells with NO hair ABOVE the skin.

    THE FIRST VERSION OF THIS SATURATED AT 1.0 ON BOTH ARMS and I nearly
    recorded that as 'coverage complete'. It binned EVERY hair point, including
    the ~100,000 roots that lie ON the scalp by construction, so with 1.2 M
    points every cell was hit no matter what the groom looked like. A metric
    that cannot return anything but 1.0 is not a strict metric, it is a
    constant.

    Two corrections, both necessary: only points at radius > R*lift count (a
    root sitting on the skin is not covering it), and cells are ANGULAR on the
    upper cap rather than a flat disc, so the sides do not dilute the top.
    """
    rel = pts - centre
    r = np.linalg.norm(rel, axis=1)
    dirs = rel / np.maximum(r, 1e-9)[:, None]
    ud = dirs @ up

    e1 = unit(np.cross(up, np.array([1.0, 0.0, 0.0])))
    if np.linalg.norm(e1) < 1e-6:
        e1 = unit(np.cross(up, np.array([0.0, 1.0, 0.0])))
    e2 = np.cross(up, e1)

    on_cap = ud > cap
    above = on_cap & (r > R * lift)
    az = np.arctan2(dirs[above] @ e2, dirs[above] @ e1)
    el = np.arccos(np.clip(ud[above], -1, 1))
    el_max = np.arccos(cap)
    ia = ((az + np.pi) / (2 * np.pi) * nb).astype(int).clip(0, nb - 1)
    ib = (el / el_max * nb).astype(int).clip(0, nb - 1)
    grid = np.zeros((nb, nb), dtype=bool)
    grid[ia, ib] = True
    # cell area on a sphere goes with sin(elevation); weight so the pole does
    # not count for as much as the rim
    w = np.sin(np.linspace(0, el_max, nb) + el_max / (2 * nb))[None, :]
    w = np.repeat(w, nb, axis=0)
    return float(1.0 - (grid * w).sum() / w.sum())


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend = tail[0]
    if len(tail) > 1 and os.path.isfile(tail[1]):
        with open(tail[1], "r", encoding="utf-8") as fh:
            P.update(json.load(fh))

    ob = pick_curves_object(bpy)
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    k = d.curves[0].points_length
    A = buf.reshape(n, 3).astype(np.float64).reshape(-1, k, 3)
    roots = A[:, 0, :]
    n_cur = A.shape[0]

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    up = np.array([0.0, 0.0, 1.0])
    fwd = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fwd)              # character's LEFT
    anat = measure_head(V, up, fwd, side)

    centre, R = fit_sphere(roots)
    rep = {"frame": {"up": up.tolist(), "fwd": fwd.tolist(),
                     "side_is_character_left": side.tolist()},
           "anatomy": anat, "scalp_centre": [round(float(x), 3) for x in centre],
           "scalp_R_cm": round(R, 3), "params": dict(P)}

    dw = unit(-fwd * P["whorl_back"] + up * P["whorl_rise"]
              + side * P["whorl_left"])
    whorl = centre + dw * R
    rep["whorl_point"] = [round(float(x), 3) for x in whorl]

    u = unit(roots - centre)                       # scalp normal per root
    cosang = np.clip(u @ dw, -1.0, 1.0)
    tang = u - dw * cosang[:, None]
    near = np.linalg.norm(tang, axis=1) < 1e-3     # at the whorl itself
    tang[near] = np.cross(dw, up)
    g = unit(tang)                                 # away from the whorl
    rep["whorl_angular_dist_deg"] = {
        "min": round(float(np.degrees(np.arccos(cosang)).min()), 2),
        "p50": round(float(np.degrees(np.arccos(cosang)).mean()), 2),
        "max": round(float(np.degrees(np.arccos(cosang)).max()), 2)}

    up_dot = u @ up
    depth = np.clip((up_dot.max() - up_dot) /
                    max(1e-6, up_dot.max() - up_dot.min()), 0, 1)
    w_down = P["down"] * depth ** P["down_ramp"]

    lat = roots @ side
    bell = np.exp(-(lat / max(1e-6, P["cross_width"])) ** 2)
    crossable = (up_dot > P["cross_up_lo"]).astype(float)
    w_cross = P["cross"] * bell * crossable
    cross_vec = (-np.sign(lat))[:, None] * side[None, :] * w_cross[:, None]

    # ---- THE TARGET DIRECTION. The first version had this wrong and the
    # numbers said so before any frame was taken.
    #
    # It set D = radial_tangent + down*depth + flare, so near the crown (depth
    # ~ 0) D was nearly HORIZONTAL while the strands there hang DOWN -- a ~90
    # degree disagreement, which the clamp then truncated. `turn_deg` came back
    # p90 = max = 42.0, the clamp exactly, on most of the head: the field was
    # not steering the reconstruction, it was fighting it and losing.
    #
    # A whorl does not make hair travel horizontally. It sets the AZIMUTH at
    # which each strand leaves the scalp; gravity still owns the elevation. So
    # the target is gravity-dominant with an azimuthal bias from the whorl, and
    # a standoff along the scalp normal for the silhouette:
    #
    #     D = -up  +  standoff * normal  +  radial * (whorl tangent, horizontal)
    #         + crisscross
    #
    # `g_h` is the whorl tangent with its vertical part removed, so `radial`
    # controls swirl and never fights gravity for elevation.
    g_h = unit(g - up[None, :] * (g @ up)[:, None])
    D = unit((-up)[None, :] * (1.0 + w_down[:, None])
             + u * (P["standoff"] + P["flare"])
             + g_h * P["radial"]
             + cross_vec)

    # the fringe band is P2's to shape; hold it back here so two passes do not
    # both own the same strands
    face_fwd = roots @ fwd
    front = (face_fwd > np.percentile(face_fwd, 78)) & (up_dot < 0.72)
    hold = np.where(front, P["front_hold"], 0.0)
    s = P["strength"] * (1.0 - hold)

    m = unit(A[:, -1, :] - roots)
    axis = np.cross(m, D)
    na = np.linalg.norm(axis, axis=1)
    ang = np.arctan2(na, np.clip((m * D).sum(1), -1.0, 1.0)) * s
    ang = np.clip(ang, 0.0, np.radians(P["max_turn_deg"]))
    degenerate = na < 1e-9
    axis[degenerate] = up
    ang[degenerate] = 0.0

    rel = A - roots[:, None, :]
    out = np.empty_like(A)
    for j in range(k):
        out[:, j, :] = rodrigues(rel[:, j, :], axis, ang)
    B = roots[:, None, :] + out

    L0 = np.linalg.norm(np.diff(A, axis=1), axis=2).sum(1)
    L1 = np.linalg.norm(np.diff(B, axis=1), axis=2).sum(1)
    rep["turn_deg"] = {"mean": round(float(np.degrees(ang).mean()), 2),
                       "p90": round(float(np.percentile(np.degrees(ang), 90)), 2),
                       "max": round(float(np.degrees(ang).max()), 2)}
    rep["length_preserved_max_err_cm"] = round(float(np.abs(L1 - L0).max()), 8)
    rep["root_shift_max_cm"] = round(
        float(np.linalg.norm(B[:, 0, :] - A[:, 0, :], axis=1).max()), 10)
    if rep["root_shift_max_cm"] > 1e-9 or \
            rep["length_preserved_max_err_cm"] > 1e-6:
        rep["error"] = "REFUSE: rotation was not rigid about the root."
        print("__P1__" + json.dumps(rep))
        raise SystemExit(3)

    rep["scalp_visible_top_before"] = round(
        scalp_visible(A.reshape(-1, 3), centre, up, R), 4)
    rep["scalp_visible_top_after"] = round(
        scalp_visible(B.reshape(-1, 3), centre, up, R), 4)

    # ---- THE PART ITSELF. Crossing-fraction is an INDIRECT read: a part is a
    # visible GAP along the sagittal line, and strands can cross the midline
    # while a gap remains, or fail to cross while covering it. So measure the
    # gap: bare scalp inside a narrow strip either side of the sagittal plane.
    def part_ratio(pts):
        """Hair DENSITY over the sagittal line, relative to its neighbours.

        THE OCCUPANCY VERSION OF THIS SATURATED AT 0.0 ON BOTH ARMS -- with 1.2 M
        points and a 4.5 mm bin, every bin along the strip is occupied whatever
        the groom does. That is the second metric in this pass that could only
        return one value, and the finding inside the failure is real: THERE IS
        NO GEOMETRIC GAP. The part the eye sees is not bare scalp with nothing
        over it; it is a density MINIMUM where hair falls away from the midline
        on both sides.
        So measure density, not occupancy. Ratio < 1 means a parting; ratio
        near 1 means the canopy closes over the midline.
        """
        rel = pts - centre
        r = np.linalg.norm(rel, axis=1)
        dirs = rel / np.maximum(r, 1e-9)[:, None]
        cap = (dirs @ up > 0.30) & (r > R * 1.03)
        lat_p = rel @ side
        w = P["part_strip_cm"]
        mid = cap & (np.abs(lat_p) < w)
        off = cap & (np.abs(np.abs(lat_p) - P["part_offset_cm"]) < w)
        if mid.sum() < 50 or off.sum() < 50:
            return None
        # per unit lateral width, so the two bands are comparable
        return round(float((mid.sum() / (2 * w)) /
                           (off.sum() / (4 * w))), 4)

    rep["part_density_ratio_before"] = part_ratio(A.reshape(-1, 3))
    rep["part_density_ratio_after"] = part_ratio(B.reshape(-1, 3))
    rep["_part_ratio_note"] = ("<1 = a parting: less hair over the midline "
                               "than beside it. ->1 = the canopy closes.")

    # PART AXIS: how much hair crosses the sagittal plane in the crown band.
    # A hard part shows as tips staying on their root's own side.
    cb = up_dot > P["cross_up_lo"]
    tip_lat = B[:, -1, :] @ side
    crossed = np.sign(tip_lat[cb]) != np.sign(lat[cb])
    tip_lat0 = A[:, -1, :] @ side
    crossed0 = np.sign(tip_lat0[cb]) != np.sign(lat[cb])
    rep["crown_strands_crossing_midline_pct"] = {
        "before": round(float(crossed0.mean() * 100), 2),
        "after": round(float(crossed.mean() * 100), 2),
        "n": int(cb.sum())}

    d.attributes["position"].data.foreach_set(
        "vector", B.reshape(-1, 3).astype(np.float32).ravel())
    chk = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", chk)
    rep["readback_max_err"] = float(
        np.abs(chk.reshape(-1, 3) - B.reshape(-1, 3)).max())

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["saved"] = out_blend
    print("__P1__" + json.dumps(rep, default=str))


if __name__ == "__main__":
    main()
