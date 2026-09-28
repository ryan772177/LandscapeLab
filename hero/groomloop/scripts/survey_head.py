"""survey_head.py -- THE SURVEYOR, head half. Runs first, owns the frame.

    blender --background <hero_base.blend> --python survey_head.py -- <out.json>

WHY THERE IS A SURVEYOR AT ALL. Every stage of this pipeline has recomputed the
same handful of facts about the hero's skull, and they drifted every time --
mesh-fraction against skull-fraction, whether the temples count as front, roots
appearing on the neck, and this session's own frame bug where the ROOT CENTROID
was used as the head centre and read `region "crown": 0` while every mask
silently evaluated against a wrong origin. Non-negotiable 24: two places that
must agree are one declaration, badly stored.

So this publishes the frame ONCE and every downstream agent CONSUMES it. Nothing
else may recompute a skull band, a hairline, a brow line or a region predicate.

WHAT IT PUBLISHES
  frame          fitted skull centre + radius, declared up/front axes, units
  skull_bands    z of crown / brow / ear / nape / neck cut, and as fractions
  hairline       swept curve: hairline height per azimuth, front-high to
                 nape-low, with the TEMPLES COUNTED AS FRONT
  boxes          eye and brow boxes, from the mesh, for occlusion scoring
  ears           position and the coverage band each ear spans
  regions        fringe / crown / side_L / side_R / nape as ROOT-SELECTION
                 PREDICATES in normalised skull coordinates -- (up, fwd, side)
                 bands, so a styling agent selects roots without owning any
                 geometry reasoning of its own

EVERY NUMBER IS MEASURED FROM THE HEAD MESH IN THE BLEND. None is a constant
carried from another file, which is the failure this file exists to end.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

# DECLARED, not inferred. Gravity gives you up; nothing in the geometry says
# which way a face points. author_hero_hair.py declares face_sign_y = -1.0 and
# this must agree with it -- it is the one axis fact the surveyor inherits.
UP = np.array([0.0, 0.0, 1.0])
FWD = np.array([0.0, -1.0, 0.0])
SIDE = np.cross(UP, FWD)


def fit_sphere(pts):
    a = np.empty((pts.shape[0], 4), dtype=np.float64)
    a[:, :3] = 2.0 * pts
    a[:, 3] = 1.0
    sol, *_ = np.linalg.lstsq(a, (pts ** 2).sum(axis=1), rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(sol[3] + float((c ** 2).sum()), 1e-12)))


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out = tail[0]
    rep = {"ok": False, "producer": "survey_head.py",
           "blend": bpy.data.filepath}

    # --- the head mesh ----------------------------------------------------
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("REFUSE: no MESH object in this blend to survey")
    head = max(meshes, key=lambda o: len(o.data.vertices))
    rep["head_object"] = head.name
    mw = head.matrix_world
    V = np.array([list(mw @ v.co) for v in head.data.vertices],
                 dtype=np.float64)
    rep["head_verts"] = int(V.shape[0])

    z = V @ UP
    z_lo, z_hi = float(z.min()), float(z.max())
    height = z_hi - z_lo
    rep["mesh_bounds_up"] = [round(z_lo, 3), round(z_hi, 3)]

    # --- the SKULL, not the bust ------------------------------------------
    # THE NECK AND SHOULDERS MUST COME OUT BEFORE ANYTHING IS FITTED. A sphere
    # fitted through the shoulders is not a skull, and every band derived from
    # it would be wrong by tens of centimetres. The cut is taken where the
    # cross-section stops shrinking going down -- the jaw/neck junction -- which
    # is a measurement rather than a fraction someone chose.
    nbins = 60
    edges = np.linspace(z_lo, z_hi, nbins + 1)
    widths = []
    for i in range(nbins):
        m = (z >= edges[i]) & (z < edges[i + 1])
        if m.sum() < 8:
            widths.append(np.nan)
            continue
        s = V[m] @ SIDE
        widths.append(float(s.max() - s.min()))
    widths = np.array(widths)
    mid = np.array([(edges[i] + edges[i + 1]) * 0.5 for i in range(nbins)])
    top_half = mid > (z_lo + 0.55 * height)
    valid = np.isfinite(widths)
    # narrowest slice in the upper part of the bust IS the neck
    cand = valid & (mid > z_lo + 0.30 * height) & (mid < z_lo + 0.75 * height)
    neck_i = int(np.nanargmin(np.where(cand, widths, np.inf)))
    neck_z = float(mid[neck_i])
    rep["neck_cut_up"] = round(neck_z, 3)
    rep["neck_width"] = round(float(widths[neck_i]), 3)

    skull = V[z >= neck_z]
    C, R = fit_sphere(skull[(skull @ UP) >= neck_z + 0.35 * (z_hi - neck_z)])
    rep["frame"] = {
        "centre": [round(float(v), 4) for v in C],
        "radius": round(R, 4),
        "up": "+z", "front": "-y",
        "units": "centimetres (the hero authoring blend is Z-up in cm)",
        "_face_sign_source": "author_hero_hair.py PARAMS face_sign_y = -1.0",
    }

    def norm(P):
        u = (P - C) / R
        return np.stack([u @ UP, u @ FWD, u @ SIDE], axis=1)

    # --- skull bands ------------------------------------------------------
    sk_z = skull @ UP
    crown_z = float(sk_z.max())

    # THE EYE BAND IS MEASURED, AND THIS IS THE FIRST TIME IT EVER HAS BEEN.
    # preview_hair.py used z_lo + 0.62..0.80 * height and author_hero_hair.py
    # gated the face zone at face_zone_z_frac 0.80 of the same bounds -- the
    # SAME ARITHMETIC IN TWO FILES, so their agreement was one measurement and
    # not two. It put the brow at 170.92, and a line drawn there on his own
    # bare-head render sits THREE CENTIMETRES UP HIS FOREHEAD
    # (_verify/20260822_hero_authored/BROW_CHECK.png). Both the root filter and
    # the face repel defended that forehead as if it were his eyes, which is
    # why no fringe could ever form.
    #
    # The socket is OFF THE MIDLINE, so it is found in a column at the eye's
    # own lateral offset. A first attempt took the frontmost vertex per height
    # band across the whole face and returned 176.1 -- the frontmost vertex at
    # eye height is the BROW RIDGE, not the socket.
    x_all, y_all = skull @ SIDE, skull @ FWD
    col = (np.abs(x_all) >= 3.2) & (np.abs(x_all) < 4.4)
    bands = np.linspace(neck_z, crown_z, 60)
    mids, ext = [], []
    for i in range(len(bands) - 1):
        m = col & (sk_z >= bands[i]) & (sk_z < bands[i + 1])
        if m.sum() >= 4:
            mids.append(0.5 * (bands[i] + bands[i + 1]))
            ext.append(float(y_all[m].max()))
    mids, ext = np.array(mids), np.array(ext)
    nose_m = np.abs(x_all) < 1.5
    nose_z = float(sk_z[nose_m][np.argmax(y_all[nose_m])])
    above = mids > nose_z
    sm, se = mids[above], ext[above]
    socket_i = next((i for i in range(1, len(se) - 1)
                     if se[i] <= se[i - 1] and se[i] <= se[i + 1]), None)
    if socket_i is None:
        raise SystemExit("REFUSE: no eye socket recess found in the 3.2-4.4 cm "
                         "column; the brow cannot be measured on this mesh")
    socket_z = float(sm[socket_i])
    # the BROW RIDGE is the forward PEAK immediately above the socket
    brow_i = socket_i + int(np.argmax(se[socket_i:socket_i + 8]))
    brow_z = float(sm[brow_i])
    rep["skull_bands"] = {
        "crown_up": round(crown_z, 3),
        "nose_tip_up": round(nose_z, 3),
        "eye_socket_up": round(socket_z, 3),
        "brow_up": round(brow_z, 3),
        "eye_band_up": [round(socket_z - (brow_z - socket_z), 3),
                        round(brow_z, 3)],
        "neck_cut_up": round(neck_z, 3),
        "_superseded": {
            "fraction_brow_up": round(z_lo + 0.80 * height, 3),
            "_by_how_much_cm": round(z_lo + 0.80 * height - brow_z, 3),
            "_evidence": "_verify/20260822_hero_authored/BROW_CHECK.png",
        },
        "_brow_reading": ("the brow is the forward PEAK of the ridge just "
                          "above the socket recess. It is anatomy, so styling "
                          "moves around it and never moves it -- tying it to "
                          "the hairline would shrink the eye protection "
                          "whenever the hairline was lowered, which is the "
                          "thing being protected."),
    }

    # --- ears -------------------------------------------------------------
    # The ears are the widest thing on the skull below the crown.
    ear_band = (sk_z > neck_z + 0.15 * (crown_z - neck_z))
    ear_band &= (sk_z < neck_z + 0.70 * (crown_z - neck_z))
    eb = skull[ear_band]
    es = eb @ SIDE
    ears = {}
    for name, sel in (("L", es > 0), ("R", es < 0)):
        pts = eb[sel]
        if pts.shape[0] < 10:
            continue
        s = pts @ SIDE
        tip = pts[np.argmax(np.abs(s))]
        # the ear spans the band where |side| is within 92% of its extreme
        thr = 0.92 * float(np.abs(s).max())
        zs = (pts[np.abs(s) >= thr]) @ UP
        ears[name] = {
            "tip": [round(float(v), 3) for v in tip],
            "up_span": [round(float(zs.min()), 3), round(float(zs.max()), 3)],
            "upper_third_up": round(float(zs.min() + (zs.max() - zs.min())
                                          * 2.0 / 3.0), 3),
            "side_extent": round(float(np.abs(s).max()), 3),
        }
    rep["ears"] = ears
    rep["ears"]["_coverage_axis"] = (
        "the sides brief scores EAR UPPER-THIRD COVERAGE: hair must cover from "
        "upper_third_up to up_span[1]. Below that the ear shows, which the "
        "clay target has at the lobe and not at the top.")

    # --- the hairline, as a swept curve ----------------------------------
    # FROM THE GROOM'S OWN ROOTS, which is the only honest source: the hairline
    # is where hair actually starts on this head, not where a fraction says it
    # should. Published per azimuth so a region predicate can ask "is this root
    # in front of the hairline at ITS bearing" rather than against one height.
    hair = pick_curves_object(bpy)
    hd = hair.data
    n_pts = len(hd.points)
    pos = np.zeros(n_pts * 3, dtype=np.float32)
    hd.attributes["position"].data.foreach_get("vector", pos)
    pos = pos.reshape(n_pts, 3).astype(np.float64)
    starts = np.array([c.first_point_index for c in hd.curves],
                      dtype=np.int64)
    roots = pos[starts]
    rep["roots"] = int(roots.shape[0])

    rn = norm(roots)
    az = np.degrees(np.arctan2(rn[:, 2], rn[:, 1]))   # 0 = dead front
    nb = 24
    sweep = []
    for i in range(nb):
        a0, a1 = -180 + i * 360.0 / nb, -180 + (i + 1) * 360.0 / nb
        m = (az >= a0) & (az < a1)
        if m.sum() < 5:
            sweep.append(None)
            continue
        sweep.append({
            "az_deg": round(0.5 * (a0 + a1), 1),
            "n": int(m.sum()),
            "hairline_up": round(float(np.percentile(roots[m] @ UP, 5)), 3),
            "hairline_up_norm": round(float(np.percentile(rn[m][:, 0], 5)), 4),
        })
    rep["hairline_sweep"] = sweep
    rep["hairline_note"] = (
        "TEMPLES COUNT AS FRONT. A hairline read as a single height puts the "
        "temple in the side region, and the brow wisps then live in the gap "
        "between the two -- measured, and it is why an earlier fix needed the "
        "hairline and the sweep to be one fact rather than two.")

    # --- region predicates ------------------------------------------------
    # Published as BANDS IN NORMALISED SKULL COORDINATES (up, fwd, side), each
    # a smoothstep with an inner and outer edge so no region has a hard rim.
    # A styling agent selects its roots with these and owns no geometry
    # reasoning of its own.
    rep["regions"] = {
        "_coords": ("normalised skull coords: u = (root - frame.centre) / "
                    "frame.radius, then up = u.UP, fwd = u.FWD, side = u.SIDE. "
                    "UP = +Z, FWD = -Y, SIDE = UP x FWD."),
        "_form": "smoothstep(lo, hi, value); a root's weight is the product of "
                 "its listed clauses, so bands overlap softly rather than "
                 "partitioning.",
        "_transposition_fixed": (
            "THREE of these bands were written ASCENDING when they needed to "
            "select LOW values, so side_L, side_R and nape all selected the "
            "UPPER skull. The declared 'nape' was therefore the OCCIPUT, which "
            "is why its census read 18,531 -- about the same as crown's 18,076 "
            "-- and why the nape agent's brief told it the region held 622 "
            "roots. 622 was the WEIGHT SUM of the correctly-transposed band "
            "printed beside the wrong count, so the two numbers in the same "
            "row described different things. Found by the nape agent, which "
            "reproduced BOTH published numbers from one root cloud rather than "
            "believing either. Scope: this census is a REPORT, consumed by "
            "agent briefs; edit_engine.py computes its own region weights and "
            "was never affected, so no styling result is invalidated."),
        "fringe": {"fwd": [0.10, 0.55], "up": [-0.30, 0.55],
                   "_owns": "locks breaking down over the brow"},
        "crown": {"up": [0.45, 0.95],
                  "_owns": "lift up-and-forward, chunky separated locks"},
        "side_L": {"side": [0.25, 0.80], "up": [0.45, -0.60],
                   "_owns": "ear coverage and swept-back flow, left"},
        "side_R": {"side": [-0.25, -0.80], "up": [0.45, -0.60],
                   "_owns": "ear coverage and swept-back flow, right"},
        "nape": {"fwd": [-0.20, -0.75], "up": [0.10, -0.70],
                 "_owns": "taper to a soft point above the collar"},
    }

    # Root census per region, so an agent knows how much material it owns
    # BEFORE it starts styling -- the hero has almost no nape roots, and an
    # agent that discovers that after eight iterations has wasted them.
    def ss(lo, hi, x):
        t = np.clip((x - lo) / (hi - lo + 1e-12), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    counts = {}
    axes = {"up": 0, "fwd": 1, "side": 2}
    for name, spec in rep["regions"].items():
        if name.startswith("_"):
            continue
        w = np.ones(rn.shape[0])
        for k, v in spec.items():
            if k in axes:
                w = w * ss(v[0], v[1], rn[:, axes[k]])
        counts[name] = {"roots_w>0.5": int((w > 0.5).sum()),
                        "weight_sum": round(float(w.sum()), 1)}
    rep["region_census"] = counts

    rep["ok"] = True
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
    print("__SURVEY__" + json.dumps({k: rep[k] for k in
                                     ("ok", "head_object", "head_verts",
                                      "roots", "frame", "skull_bands",
                                      "region_census")}))


if __name__ == "__main__":
    main()
