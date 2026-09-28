"""edit_engine.py -- Phase 2. One parameterised, procedural reshaper.

    blender --background --python edit_engine.py -- <src_abc> <params_json>
                                                    <out_blend> <out_abc> <log_json>

DESIGN NOTES THAT ARE NOT OPTIONAL
----------------------------------
1. THE CURVES ARE BEZIER. recon says curve_type is 2 for all 94,408 strands,
   and handle_left / handle_right are absolute POINT-domain positions. Moving a
   position without moving its handles kinks the strand at that control point.
   So every transform here is applied to positions AND to both handle arrays
   through the SAME function with the SAME per-point context. That is why the
   ops are written as pure point-transforms rather than as in-place edits.

2. NOTHING MOVES THE OBJECT. The hard rule is import-as-is / export-as-is, so
   all work is on point data in the groom's own frame and the object matrix is
   asserted identity at export.

3. THE FRAME WAS MEASURED, NOT ASSUMED (recon/geometry.json):
       up    = -Y      (mean root->tip is +Y, i.e. hair falls toward +Y)
       front = +Z      (the +Z render looks into the face cavity)
       head centre (0, -1.52098, 0), root cloud radius ~0.105 m
   Region masks are built in that frame and normalised by the scalp radius, so
   a param means the same thing regardless of the file's absolute position.

4. EVERY DISPLACEMENT RAMPS FROM ZERO AT THE ROOT. t = i/(n-1) along the
   strand. A displacement that does not vanish at t=0 lifts roots off the
   scalp, which reads as floating hair and is not recoverable downstream.

5. MASKS ARE SMOOTH. This project has already paid for a hard region box: it
   leaves a visible seam where density stops dead. All region weights use a
   smoothstep band.
"""

import json
import math
import os
import sys

import bpy
import numpy as np


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pick_curves import pick_curves_object
# THE FRAME IS DERIVED PER FILE, NOT HARDCODED.
# These were constants for the pack groom (Y-up, metres). The hero's own
# authoring blend is Z-up in CENTIMETRES, so a hardcoded frame silently applies
# every region mask to the wrong axis and every amplitude at 1/100 strength.
# HEAD and SCALP_R are measured from the strand roots at runtime; the up and
# forward AXES are declared in params because gravity gives you up but nothing
# in the geometry tells you which way the face points.
HEAD = np.array([0.0, 0.0, 0.0])
SCALP_R = 1.0
UP = np.array([0.0, -1.0, 0.0])
FWD = np.array([0.0, 0.0, 1.0])
SIDE = np.array([1.0, 0.0, 0.0])

_AXES = {"+x": np.array([1.0, 0.0, 0.0]), "-x": np.array([-1.0, 0.0, 0.0]),
         "+y": np.array([0.0, 1.0, 0.0]), "-y": np.array([0.0, -1.0, 0.0]),
         "+z": np.array([0.0, 0.0, 1.0]), "-z": np.array([0.0, 0.0, -1.0])}

# Every parameter below that is a LENGTH gets multiplied by `length_unit`, so
# the same numbers mean the same physical thing in a metre file and a
# centimetre one. Ratios, counts, exponents and angles are NOT in this list.
_LENGTH_PARAMS = (
    "fringe_forward_pull", "part_close", "crown_lift", "crown_lock_lift",
    "ear_clearance", "temple_wing", "strand_noise_amp", "flyaway_amp",
    "global_sweep_x", "global_sweep_z", "hem_tuck", "stray_clamp_m",
    "gravity_drop")


def fit_sphere(pts):
    """Algebraic least-squares sphere through the roots -> (centre, radius).

    THE CENTROID IS NOT THE CENTRE, and using it silently breaks every region
    mask. Roots live on a CAP, not a shell -- there is no hair under the chin --
    so their centroid sits near the top of the skull. Measured on the hero:
    centroid z 174.14 against a head spanning 140.9-178.4, which put the crown
    mask's own origin above the crown and made `region_curve_counts["crown"]`
    read 0. The masks all still evaluated, and every one of them was wrong.

    Fitting solves for the centre the cap is a cap OF:
        |p - c|^2 = R^2   ->   2p.c + (R^2 - |c|^2) = |p|^2
    which is linear in (c, k) and one lstsq call.
    """
    a = np.empty((pts.shape[0], 4), dtype=np.float64)
    a[:, :3] = 2.0 * pts
    a[:, 3] = 1.0
    sol, *_ = np.linalg.lstsq(a, (pts ** 2).sum(axis=1), rcond=None)
    c = sol[:3]
    r2 = sol[3] + float((c ** 2).sum())
    return c, float(np.sqrt(max(r2, 1e-12)))


def set_frame(roots, prm):
    """Take the frame from the SURVEY if given; else measure it from the roots.

    THE SURVEY WINS WHEN IT IS PRESENT. Fitting here to the ROOTS and there to
    the SKULL MESH gives two frames that nearly agree -- centre z 169.24 r 9.293
    against 168.995 r 9.227 -- and "nearly" is how region masks drift apart
    between tools. One surveyor, one truth; this consumes it.
    """
    global HEAD, SCALP_R, UP, FWD, SIDE
    src = "roots (sphere fit)"
    sv = prm.get("survey")
    if sv:
        s = json.load(open(sv, encoding="utf-8"))["frame"]
        HEAD = np.asarray(s["centre"], dtype=np.float64)
        SCALP_R = float(s["radius"])
        src = sv
        if str(s["up"]).lower() != str(prm["frame_up"]).lower() \
                or str(s["front"]).lower() != str(prm["frame_fwd"]).lower():
            raise SystemExit(
                "REFUSE: the survey declares up %s / front %s but these params "
                "say %s / %s. A frame disagreement is exactly the drift the "
                "surveyor exists to end -- fix the params, do not override."
                % (s["up"], s["front"], prm["frame_up"], prm["frame_fwd"]))
    else:
        HEAD, SCALP_R = fit_sphere(roots)
    if not np.isfinite(SCALP_R) or SCALP_R < 1e-9:
        raise SystemExit("REFUSE: frame radius is %r; the frame cannot be "
                         "measured from this groom" % SCALP_R)
    UP = _AXES[str(prm["frame_up"]).lower()]
    FWD = _AXES[str(prm["frame_fwd"]).lower()]
    SIDE = np.cross(UP, FWD)
    n = np.linalg.norm(SIDE)
    SIDE = SIDE / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])
    resid = np.linalg.norm(roots - HEAD, axis=1) - SCALP_R
    return {"head": [round(float(v), 5) for v in HEAD],
            "scalp_r": round(SCALP_R, 5),
            # How sphere-like the scalp actually is. A large residual means the
            # fit is describing something that is not a head, and the frame
            # should not be trusted -- reported so it is visible per run rather
            # than assumed once.
            "fit_resid_p90": round(float(np.percentile(np.abs(resid), 90)), 5),
            "roots": int(roots.shape[0]),
            "source": src,
            "up": prm["frame_up"], "fwd": prm["frame_fwd"],
            "side": [round(float(v), 3) for v in SIDE]}

# Diagnostics an op wants to publish from inside the transform closure, which
# does not see `rep`. Read once in main().
_DIAG = {}

DEFAULTS = {
    # fringe
    "fringe_length_scale": 1.0,
    "fringe_clump_count": 6,
    "fringe_gap_strength": 0.0,
    "fringe_forward_pull": 0.0,     # + brings tips down over the brow
    # THE FRINGE ZONE IS A PARAMETER, because the source is a CENTRE PART and
    # the reference is a full fringe. There is almost no hair rooted at the
    # front-centre -- that is the parting -- so a fringe has to be recruited
    # from further back on the top. Lowering fringe_zone_fwd and raising the
    # zone's reach up the skull is what makes that mass available to the
    # forward pull.
    "fringe_zone_fwd": 0.20,
    "fringe_zone_up_lo": -0.10,
    "fringe_zone_up_hi": 0.45,
    # Closes the centre parting by drawing fringe tips toward the midline.
    "part_close": 0.0,
    # HOW LATE ALONG THE STRAND THE FORWARD PULL ACTS. Iteration 003 swept
    # whole strands forward and uncovered the scalp behind their roots --
    # measured as a bald patch on the upper side in the left view. A higher
    # exponent keeps the mid-strand lying on the skull and swings only the
    # tip, which buys fringe reach without paying in scalp exposure.
    "fringe_pull_ramp": 1.5,
    # crown
    "crown_lift": 0.0,
    # CROWN LOCKS -- see op 7. These replace `crown_spike_noise`, which is now
    # a REFUSAL rather than a silent no-op: a params file carrying it was tuned
    # against a mechanism that no longer exists, and inheriting it silently
    # would leave the crown flat while the file still claims to style it.
    # BROW PART -- see op 7b. Opens the centre of the brow band by pushing
    # whatever sits there out to the sides, regardless of which region it is
    # rooted in. A LENGTH, so it scales with length_unit.
    #   lo / hi     the band, in scalp radii above the head centre. Defaults
    #               bracket the survey's measured brow ridge at 167.24 cm on a
    #               head whose centre is 169.00 with radius 9.23.
    #   width       half-width of the central column it acts in, in radii.
    # DEGREES of lateral swing about the root, not a length. The
    # lateral-TRANSLATION version is a REJECTED approach; see op 7b.
    "brow_part": 0.0,
    "brow_part_lo": -0.32,
    "brow_part_hi": -0.06,
    "brow_part_width": 0.50,
    "crown_lock_count": 24,     # how many locks the crown resolves into
    "crown_lock_gather": 0.0,   # 0..1, tips drawn to their lock's mean tip
    "crown_lock_lift": 0.0,     # a LENGTH, radially outward per lock
    # sides
    "side_length_scale": 1.0,
    "ear_clearance": 0.0,
    "temple_wing": 0.0,
    # nape / grading
    "nape_length_scale": 1.0,
    "layer_falloff": 0.0,           # + = shorter at crown, longer at nape
    # texture
    "clump_scale": 0.0,
    "clump_count": 260,
    # LOCK PARTITION BY CURVE INDEX, not by lat/long cell.
    # index_probe.py measured consecutive-index roots at 4.13 mm apart against
    # 125 mm for random pairs -- ratio 0.033 -- with the ratio decaying smoothly
    # with stride (0.033 / 0.049 / 0.093 / 0.166 / 0.310 / 0.578 / 0.780 at
    # stride 1/2/5/10/50/200/1000). That decay is the signature of the ARTIST'S
    # OWN guide grouping: the exporter emitted curves patch by patch.
    # A block of consecutive indices is therefore an authored, spatially
    # coherent patch -- a better lock than anything a quantised grid produces,
    # and free. 0 keeps the lat/long partition.
    "clump_index_block": 0,
    "strand_noise_amp": 0.0,
    "strand_noise_freq": 5.0,
    "flyaway_density": 0.0,
    "flyaway_amp": 0.02,
    "tip_trim_variance": 0.0,
    # global
    "global_length_scale": 1.0,
    # DIRECTIONAL SWEEP. Iterations 004-007 produced a symmetric radial dome
    # -- a mushroom -- while the reference is wind-blown to one side and
    # slightly back. A radial groom cannot become directional by tuning radial
    # parameters, so the direction is its own vector: +X sweeps toward the
    # character's side, -Z sweeps backward off the face.
    "global_sweep_x": 0.0,
    "global_sweep_z": 0.0,
    "sweep_ramp": 1.5,
    # RIGID ROTATION ABOUT THE ROOT -- a different mechanism from the sweep.
    # global_sweep_* TRANSLATES tips, which drags them away from the skull and
    # uncovers scalp: measured, left exposure 22.9 -> 30.8 at 008 and 34.4 at
    # 009. A rotation about the strand's own root REDIRECTS it while preserving
    # every point's distance from that root, so the hair keeps lying on the
    # head while the whole groom leans. Angles in degrees.
    #   rot_up_deg   about the head's UP axis  -> lateral sweep
    #   rot_side_deg about the head's SIDE axis -> forward / backward tilt
    # Constant per strand (not ramped along t), so the strand's authored shape
    # is preserved exactly and only its direction changes.
    "rot_up_deg": 0.0,
    "rot_side_deg": 0.0,
    # HEM TUCK. The mushroom's give-away is an even skirt flaring OUTWARD at
    # the bottom. Real layered hair narrows toward the jaw. Positive values
    # pull the tips of LOW-rooted strands back toward the head axis.
    "hem_tuck": 0.0,
    # Strays: recon put strand length p95 at 0.217 m against a max of 1.42 m,
    # and ~1,890 runaway tips were inflating the scene bbox to 2.5 m. Clamping
    # by SCALING ABOUT THE ROOT keeps the curve count identical, which is what
    # makes it safe -- deleting curves crashed Blender (see export_abc.census).
    # 0 disables.
    "stray_clamp_m": 0.0,
    # FACE REPEL. Pushes any point that ends up inside the published face zone
    # back out of it, ramping in over `face_repel_margin` below the brow so the
    # correction has no hard edge.
    #
    # This is the fifth guard on this region and the only one that acts AFTER
    # styling. R-HAIRFACE closed "hair over the eyes" at authoring time by
    # rejecting ROOTS in the zone -- 17,368 -> 1,689 rendered px -- and that
    # guard cannot see a tip that is pulled in later. Porting iteration 028's
    # fringe parameters onto the hero took his front hair-over-face from 2,413
    # to 9,486 px without placing one root in the zone.
    #
    # 0 disables it. Any positive value REFUSES if the source groom does not
    # publish a face zone, rather than silently styling into his eyes.
    # Hangs the strand with distance from the root -- see op 6d. A LENGTH, so
    # it scales with length_unit like every other displacement here.
    # Path to survey_head.json. When given, the FRAME comes from the surveyor
    # rather than from a local fit -- see set_frame.
    "survey": None,
    "gravity_drop": 0.0,
    "gravity_ramp": 2.0,
    # How much of the drop the crown is spared, 0..1. Unitless.
    "gravity_crown_shield": 0.0,
    "face_repel": 0.0,
    "face_repel_margin": 0.25,   # in scalp radii, below the brow plane
    # FRAME AND UNITS, declared per source file.
    #   pack groom (SC_Hairstyle_Male_11.abc)  up -y, fwd +z, length_unit 1.0
    #   hero authoring blend                   up +z, fwd -y, length_unit 100.0
    # Gravity tells you which way is up; nothing in the geometry tells you
    # which way the face points, so fwd is declared rather than inferred.
    "frame_up": "-y",
    "frame_fwd": "+z",
    "length_unit": 1.0,
    "seed": 20260822,
}


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def build_context(pos, starts, sizes):
    """Per-point context: which curve, t along it, and the curve's root.

    Returned as flat arrays so every op is vectorised -- a Python loop over
    375,774 points costs minutes per iteration and the whole point of the
    Blender side is that a shape question is answered in seconds.
    """
    n_pts = pos.shape[0]
    n_cur = len(starts)
    cid = np.zeros(n_pts, dtype=np.int64)
    t = np.zeros(n_pts, dtype=np.float64)
    for i in range(n_cur):
        s, sz = starts[i], sizes[i]
        cid[s:s + sz] = i
        if sz > 1:
            t[s:s + sz] = np.linspace(0.0, 1.0, sz)
    roots = pos[starts]                       # (n_cur, 3)
    root_per_pt = roots[cid]                  # (n_pts, 3)
    return cid, t, roots, root_per_pt


def region_weights(roots, prm=None):
    """Smooth 0..1 masks per CURVE, from its root position on the scalp."""
    prm = prm or DEFAULTS
    loc = (roots - HEAD) / SCALP_R
    up = loc @ UP          # +1 crown, -1 under
    fwd = loc @ FWD        # +1 face, -1 back
    side = loc @ SIDE

    w = {}
    # Crown EXCLUDES the fringe. Measured on iteration 001: crown_lift was
    # lifting front-rooted strands straight up, fighting fringe_forward_pull
    # in the same run and leaving the forehead MORE exposed than the source.
    # Two ops pulling the same strands in opposite directions is not a
    # parameter problem.
    crown_raw = smoothstep(0.25, 0.85, up)
    fz = prm["fringe_zone_fwd"]
    fringe_raw = (smoothstep(fz, fz + 0.55, fwd)
                  * smoothstep(prm["fringe_zone_up_lo"],
                               prm["fringe_zone_up_hi"], up))
    w["crown"] = crown_raw * (1.0 - 0.85 * fringe_raw)
    # fringe: front AND upper. Both conditions smooth, multiplied, so the
    # boundary is a gradient in two directions rather than a rectangle.
    w["fringe"] = fringe_raw
    w["side"] = smoothstep(0.35, 0.85, np.abs(side)) * (1.0 - smoothstep(0.55, 1.0, up))
    w["temple"] = (smoothstep(0.40, 0.85, np.abs(side))
                   * smoothstep(0.05, 0.55, fwd)
                   * (1.0 - smoothstep(0.35, 0.9, up)))
    w["nape"] = smoothstep(-0.10, -0.70, fwd) * (1.0 - smoothstep(-0.55, 0.15, up))
    w["_up"] = up
    w["_fwd"] = fwd
    w["_side"] = side
    return w


def rng_per_curve(n_cur, seed, salt):
    return np.random.default_rng(seed + salt).random(n_cur)


def curve_lengths(pos, starts, sizes):
    """Polyline length per curve, vectorised over the flat point array."""
    seg = np.zeros(pos.shape[0], dtype=np.float64)
    d = np.linalg.norm(pos[1:] - pos[:-1], axis=1)
    seg[1:] = d
    # zero the segment that spans a curve boundary
    seg[starts] = 0.0
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    return cum[starts + sizes] - cum[starts]


def make_transform(P, ctx, w, prm, n_cur, ctx_starts, ctx_sizes):
    """Return a function mapping any point array (positions OR handles).

    The same closure is applied to position, handle_left and handle_right, so
    a control point and its two handles move together and the strand keeps its
    tangents. Applying an op to positions alone is the kink bug.
    """
    cid, t, roots, root_per_pt = ctx

    # --- per-curve length multiplier -------------------------------------
    length_mul = np.ones(n_cur)
    length_mul *= 1.0 + (prm["fringe_length_scale"] - 1.0) * w["fringe"]
    length_mul *= 1.0 + (prm["side_length_scale"] - 1.0) * w["side"]
    length_mul *= 1.0 + (prm["nape_length_scale"] - 1.0) * w["nape"]
    # layer grading: crown short -> nape long, driven by the root's own height
    grade = 1.0 - prm["layer_falloff"] * np.clip(w["_up"], -1.0, 1.0)
    length_mul *= grade
    if prm["tip_trim_variance"] > 0:
        r = rng_per_curve(n_cur, prm["seed"], 11)
        length_mul *= 1.0 + prm["tip_trim_variance"] * (r - 0.5) * 2.0
    length_mul *= prm["global_length_scale"]

    # Stray clamp, applied LAST so it bounds the result of every other length
    # op rather than being undone by them.
    if prm["stray_clamp_m"] > 0:
        L = curve_lengths(P, ctx_starts, ctx_sizes)
        proj = L * length_mul
        over = proj > prm["stray_clamp_m"]
        length_mul = np.where(over,
                              length_mul * (prm["stray_clamp_m"]
                                            / np.maximum(proj, 1e-9)),
                              length_mul)

    length_mul = np.clip(length_mul, 0.05, 6.0)
    lm_pt = length_mul[cid][:, None]

    # --- clump targets ----------------------------------------------------
    # CLUMPS ARE SPATIAL, NOT RANDOM. Iteration 001 assigned clump ids by
    # rng.integers over all 94,408 curves, so every clump's mean root was the
    # head centroid and "pull toward your clump" degenerated into "pull toward
    # the middle" for every strand on the head. Measured as a fuzzy ball with
    # MORE exposed forehead than the source.
    #
    # A clump is now a patch of NEARBY roots, found by quantising each root's
    # direction on the scalp into a lat/long cell. And the attractor is the
    # clump's mean TIP, not its mean root: hair clumps converge at the ENDS,
    # which is what opens gaps between pieces.
    def spatial_clumps(count, salt):
        dirs = roots - HEAD
        nrm = np.linalg.norm(dirs, axis=1, keepdims=True)
        u = dirs / np.maximum(nrm, 1e-9)
        # THE PARTITION USES THE DECLARED FRAME, NOT HARDCODED COMPONENTS.
        # This was arctan2(u[0], u[2]) and arcsin(-u[1]) -- longitude around Y,
        # latitude along Y -- which is the PACK GROOM's up axis. On the hero,
        # who is Z-up with front -Y, it partitioned FRONT-TO-BACK instead of
        # into side-by-side locks, so `clump_count` subdivided the wrong way
        # and raising it dragged fringe tips into his eyes. Found by the round-2
        # fringe agent and confirmed at these lines.
        #
        # Every clumping result in rounds 1 and 2 was tuned on the wrong
        # partition -- including this project's best score -- so the fix is a
        # re-tune, not a free win.
        #
        # For the pack groom the corrected form is the old one MIRRORED in x
        # (SIDE comes out -X there), i.e. the same partition under a different
        # labelling, so nothing about that groom's history is invalidated.
        theta = np.arctan2(u @ SIDE, u @ FWD)          # longitude about UP
        phi = np.arcsin(np.clip(u @ UP, -1.0, 1.0))    # latitude
        nlon = max(1, int(round(math.sqrt(count * 2.0))))
        nlat = max(1, int(round(count / max(nlon, 1))))
        li = np.clip(((theta + math.pi) / (2 * math.pi) * nlon).astype(int),
                     0, nlon - 1)
        pi_ = np.clip(((phi + math.pi / 2) / math.pi * nlat).astype(int),
                      0, nlat - 1)
        cid_local = li * nlat + pi_
        ncell = nlon * nlat
        # mean TIP per cell, via bincount so it stays vectorised
        tips_local = P[ctx_starts + ctx_sizes - 1]
        cnt = np.bincount(cid_local, minlength=ncell).astype(np.float64)
        cen = np.zeros((ncell, 3))
        for ax in range(3):
            cen[:, ax] = np.bincount(cid_local, weights=tips_local[:, ax],
                                     minlength=ncell)
        cen /= np.maximum(cnt, 1.0)[:, None]
        empty = cnt < 1
        cen[empty] = HEAD
        return cid_local, cen, tips_local

    def index_clumps(block):
        """Lock partition from the authored curve order. See clump_index_block."""
        cid_local = (np.arange(n_cur) // block).astype(np.int64)
        ncell = int(cid_local.max()) + 1
        tips_local = P[ctx_starts + ctx_sizes - 1]
        cnt = np.bincount(cid_local, minlength=ncell).astype(np.float64)
        cen = np.zeros((ncell, 3))
        for ax in range(3):
            cen[:, ax] = np.bincount(cid_local, weights=tips_local[:, ax],
                                     minlength=ncell)
        cen /= np.maximum(cnt, 1.0)[:, None]
        return cid_local, cen, tips_local

    if int(prm["clump_index_block"]) > 0:
        cl_id, cl_cen, tips_arr = index_clumps(int(prm["clump_index_block"]))
    else:
        cl_id, cl_cen, tips_arr = spatial_clumps(
            max(1, int(prm["clump_count"])), 3)
    clump_tgt_pt = cl_cen[cl_id][cid]
    own_tip_pt = tips_arr[cid]

    # Fringe clumps: a separate, much COARSER spatial set, so the forehead
    # breaks into a countable number of pieces with scalp between them rather
    # than into uniform frizz.
    fcl_id, fcl_cen, _ = spatial_clumps(max(1, int(prm["fringe_clump_count"])), 7)
    fringe_tgt_pt = fcl_cen[fcl_id][cid]

    # Crown locks: a third partition, coarser again, so the crown resolves into
    # a countable number of standing locks. See op 7.
    kcl_id, kcl_cen, _ = spatial_clumps(max(1, int(prm["crown_lock_count"])), 11)
    crown_tgt_pt = kcl_cen[kcl_id][cid]

    # --- per-strand noise phase ------------------------------------------
    ng = np.random.default_rng(prm["seed"] + 5)
    phase = ng.random((n_cur, 3)) * 6.2831853
    phase_pt = phase[cid]

    fly = (rng_per_curve(n_cur, prm["seed"], 13) < prm["flyaway_density"])
    fly_pt = fly[cid][:, None].astype(np.float64)

    w_fringe_pt = w["fringe"][cid][:, None]
    w_crown_pt = w["crown"][cid][:, None]
    w_side_pt = w["side"][cid][:, None]
    w_temple_pt = w["temple"][cid][:, None]
    side_sign = np.sign(w["_side"])[cid][:, None]
    w_up_pt = w["_up"][cid][:, None]
    t_pt = t[:, None]

    def xf(A):
        out = A.copy()
        # 1. length scale about the root (handles scale with it, so a
        #    lengthened strand keeps its curvature instead of straightening)
        out = root_per_pt + (out - root_per_pt) * lm_pt

        # 2. clumping: converge toward the clump's mean TIP, ramped along the
        #    strand so roots stay put and only the ends gather. The offset is
        #    measured from THIS strand's own tip, so a strand already at the
        #    clump centre does not move -- that is what keeps clumping from
        #    collapsing the whole groom inward.
        if prm["clump_scale"] > 0:
            k = prm["clump_scale"] * (t_pt ** 1.6)
            out = out + (clump_tgt_pt - own_tip_pt) * k

        # 3. fringe separation: the same convergence on a much coarser set,
        #    masked to the fringe, so the forehead reads as a countable number
        #    of pieces with scalp visible between them.
        if prm["fringe_gap_strength"] > 0:
            k = prm["fringe_gap_strength"] * (t_pt ** 1.3) * w_fringe_pt
            out = out + (fringe_tgt_pt - own_tip_pt) * k

        # 4. crown lift along up, ramped, so the top gains height not the roots
        if prm["crown_lift"] != 0:
            out = out + UP * (prm["crown_lift"] * (t_pt ** 1.4) * w_crown_pt)

        # 5. fringe forward pull: brings tips down across the brow (+Z front,
        #    and downward is +Y, so this is a forward-and-down vector)
        if prm["fringe_forward_pull"] != 0:
            # forward AND downward. "Down" is -UP in whatever frame this file
            # uses; it was hardcoded to +Y for the pack groom and would have
            # pulled the hero's fringe straight up.
            v = (FWD * 0.75 + (-UP) * 0.65)
            out = out + v * (prm["fringe_forward_pull"]
                             * (t_pt ** prm["fringe_pull_ramp"])
                             * w_fringe_pt)

        # 5b. close the centre parting: draw fringe tips toward the midline so
        #     the two curtains meet over the forehead instead of framing it.
        if prm["part_close"] != 0:
            out = out - SIDE * (side_sign * prm["part_close"]
                                * (t_pt ** 1.4) * w_fringe_pt)

        # 6. ear clearance / temple wing: push laterally outward
        if prm["ear_clearance"] != 0:
            out = out + SIDE * (side_sign * prm["ear_clearance"]
                                * (t_pt ** 1.2) * w_side_pt)
        if prm["temple_wing"] != 0:
            out = out + SIDE * (side_sign * prm["temple_wing"]
                                * (t_pt ** 1.5) * w_temple_pt)

        # 6a. RIGID ROTATION ABOUT THE ROOT. Applied BEFORE the translations so
        #     the tuck and sweep act on the already-redirected strand.
        #     Rodrigues, vectorised; the angle is per-curve so each strand
        #     turns as a unit and keeps its authored curvature.
        if prm["rot_up_deg"] != 0 or prm["rot_side_deg"] != 0:
            off = out - root_per_pt
            for axis_vec, deg in ((UP, prm["rot_up_deg"]),
                                  (SIDE, prm["rot_side_deg"])):
                if deg == 0:
                    continue
                ang = math.radians(deg)
                k = axis_vec / np.linalg.norm(axis_vec)
                ca, sa = math.cos(ang), math.sin(ang)
                cross = np.cross(np.broadcast_to(k, off.shape), off)
                dot = off @ k
                off = (off * ca + cross * sa
                       + np.outer(dot, k) * (1.0 - ca))
            out = root_per_pt + off

        # 6b. GLOBAL DIRECTIONAL SWEEP -- the wind-blown axis. Applied to every
        #     strand so the whole groom leans, which is what separates a
        #     wind-blown cut from a radial dome.
        if prm["global_sweep_x"] != 0 or prm["global_sweep_z"] != 0:
            ramp = t_pt ** prm["sweep_ramp"]
            out = out + SIDE * (prm["global_sweep_x"] * ramp)
            out = out + FWD * (prm["global_sweep_z"] * ramp)

        # 6c. HEM TUCK -- narrow the skirt. Only strands rooted LOW get it, and
        #     it pulls their tips toward the head's vertical axis, so the
        #     outline tapers toward the jaw instead of flaring.
        if prm["hem_tuck"] != 0:
            low = np.clip(-w_up_pt, 0.0, 1.5)
            # Radial component in the plane perpendicular to UP, through HEAD.
            # Previously this zeroed component [1] outright, which is only the
            # up axis in the pack groom's Y-up frame.
            rel = out - HEAD
            radial = rel - np.outer(rel @ UP, UP)
            rn = np.linalg.norm(radial, axis=1, keepdims=True)
            rdir = radial / np.maximum(rn, 1e-9)
            out = out - rdir * (prm["hem_tuck"] * (t_pt ** 1.6) * low)

        # 6d. GRAVITY DROP -- the strand hangs as it gets further from the root.
        #     THE ONE MECHANISM THE PACK GROOM NEVER NEEDED. That groom was
        #     authored as a long hairstyle whose strands already fell; the
        #     hero's are authored along the SCALP NORMAL, so they leave the head
        #     radially and every length increase goes straight OUTWARD. Scaling
        #     his sides up to reach the jaw therefore produced a flared mane
        #     (side silhouette 121,817 -> 190,209 px, flare_max 0.697 -> 0.967)
        #     instead of the reference's curtain, and no combination of the
        #     existing parameters could have fixed it -- ear_clearance pulls
        #     laterally and hem_tuck is inert on a groom with no low roots.
        #
        #     Quadratic in t, like real hair: near the root the follicle sets
        #     the direction, and weight only wins further out.
        #
        #     THE CROWN IS SHIELDED, and that is not a fudge. Applied at full
        #     strength everywhere, the drop pulls crown strands down the two
        #     sides of the skull and OPENS A PARTING along the midline --
        #     measured, midline scalp exposure 1.88 -> 8.47% while lateral
        #     exposure improved to 2.01%. On a real head the crown hair is the
        #     shortest and lies against the skull, so weight barely moves it;
        #     the drape belongs to the long hair at the sides and back.
        if prm["gravity_drop"] != 0:
            g_w = 1.0 - prm["gravity_crown_shield"] * w_crown_pt
            out = out + (-UP) * (prm["gravity_drop"]
                                 * (t_pt ** prm["gravity_ramp"]) * g_w)

        # 7. CROWN LOCKS -- coherent gathers, replacing per-strand fuzz.
        #
        # WHAT WAS HERE AND WHY IT IS GONE. `crown_spike_noise` displaced each
        # strand by sin(phase + t) with a per-strand phase drawn INDEPENDENTLY
        # PER AXIS -- `phase = rng.random((n_cur, 3))` -- so every strand
        # wandered in its own random direction, with no coherence between
        # neighbours and no anatomical direction at all. It made raggedness
        # without gathering: measured, it drove `edge_roughness` UP while the
        # clay wants it DOWN, and the round-2 texture agent identified it as the
        # entire residual of that axis after clumping had done all it could.
        # It is the halo you see standing off the skull in every render since
        # round 1. Clumping could never reach it, because clumping gathers and
        # this scattered.
        #
        # THE REPLACEMENT GATHERS. The crown gets its own partition -- coarser
        # than the body clumps, so it resolves into a countable number of locks
        # rather than a texture -- and each strand's tip is drawn toward its
        # lock's mean tip. That opens scalp BETWEEN locks and merges strands
        # WITHIN them, which is the mechanism the texture agent measured
        # edge_roughness actually responding to.
        #
        # Then each lock stands up along its OWN root direction from the head
        # centre, so locks separate outward and diverge instead of translating
        # together. Radial, so it is the one direction that cannot make two
        # neighbouring locks collide.
        if prm["crown_lock_gather"] > 0:
            out = out + (crown_tgt_pt - own_tip_pt) * (
                prm["crown_lock_gather"] * (t_pt ** 1.6) * w_crown_pt)
        if prm["crown_lock_lift"] != 0:
            rad = ctx[3] - HEAD
            rdir = rad / np.maximum(
                np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
            out = out + rdir * (prm["crown_lock_lift"] * (t_pt ** 1.8)
                                * w_crown_pt)

        # 7b. BROW PART -- open the centre of the brow by moving hair sideways.
        #
        # WHY A NEW OP RATHER THAN MORE FRINGE TUNING. `fringe: brow` carries
        # 67% of all remaining weighted error: ours reads 0.0254 in the central
        # brow band against the clay's 0.0007. The round-2 fringe agent proved
        # the fringe knobs cannot reach it -- it gathered the fringe almost
        # entirely off the forehead and brow moved 0.0234 -> 0.0204 -- and
        # attribute_brow.py says why: only 51% of the offending strands are
        # rooted in the fringe at all. 19% are side, 16% crown, 15% temple, and
        # the TEMPLE is the guiltiest per capita at 9.8% of its own region. No
        # single region owns this.
        #
        # AND IT IS NOT A LENGTH PROBLEM. The clay's centre-brow is OPEN with
        # the locks swept to the sides; ours hangs straight down over it. The
        # difference is lateral, so the fix is lateral: push whatever is in the
        # central brow band OUT of it, away from the midline, whichever region
        # it came from. Shortening would remove the fringe the reference wants.
        #
        # Ramped by depth into the band and by t, so nothing moves at the root
        # and the strands at the edge of the band are barely touched -- no seam.
        # Signed by which side of the midline the point already sits on, so it
        # opens a part rather than sweeping everything one way.
        if prm["brow_part"] != 0:
            # ROTATION ABOUT THE ROOT, NOT TRANSLATION.
            #
            # REJECTED FIRST VERSION, measured: pushing POINTS sideways out of
            # the band made the axis WORSE at every strength -- brow 0.0254 ->
            # 0.0305 / 0.0299 / 0.0332 -- and took two of three runs from
            # ACCEPT to REJECT. Translating a mid-strand point BOWS the strand,
            # which puts more of its length inside the band than it removes.
            # (Its band mask was also a 0.18 cm sliver at first, and fixing
            # that did not rescue it, which is what makes this a mechanism
            # failure rather than a tuning one.)
            #
            # This project measured the same distinction on 2026-08-21 and
            # wrote it down: rotate strands about their own root, do not
            # translate their tips. Translation drags hair off the skull and
            # uncovers scalp; a rigid rotation preserves every point's distance
            # from its root, so the strand keeps lying on the head while its
            # DIRECTION changes.
            #
            # The mask is per-CURVE and keyed on the ROOT, so a strand either
            # belongs to the part or it does not, and one that does keeps its
            # authored shape exactly.
            r_side = (roots - HEAD) @ SIDE
            r_up = (roots - HEAD) @ UP
            r_fwd = (roots - HEAD) @ FWD
            m = (smoothstep(prm["brow_part_width"] * SCALP_R,
                            0.35 * prm["brow_part_width"] * SCALP_R,
                            np.abs(r_side))
                 * smoothstep(0.05, 0.45, r_fwd / SCALP_R)
                 * smoothstep(prm["brow_part_lo"], prm["brow_part_lo"] + 0.5,
                              r_up / SCALP_R))
            ang = np.radians(prm["brow_part"]) * m * np.sign(r_side)
            ang_pt = ang[cid][:, None]
            off = out - root_per_pt
            kk = UP / np.linalg.norm(UP)
            ca, sa = np.cos(ang_pt), np.sin(ang_pt)
            cross = np.cross(np.broadcast_to(kk, off.shape), off)
            dot = (off @ kk)[:, None]
            out = root_per_pt + (off * ca + cross * sa + dot * kk * (1.0 - ca))
            # THE TRANSFORM IS A CLOSURE AND `rep` IS NOT IN ITS SCOPE -- and
            # it is called three times, once each for positions and both handle
            # arrays, so writing a report from in here would triple-count
            # anyway. A module-level slot, read once in main().
            _DIAG["brow_part"] = {
                "curves_in_part": int((m > 0.5).sum()),
                "max_deg": round(float(np.degrees(np.abs(ang)).max()), 2)}

        # 8. general strand noise -- breaks the silhouette everywhere
        if prm["strand_noise_amp"] > 0:
            f = prm["strand_noise_freq"]
            s = np.stack([np.sin(phase_pt[:, 0] + t_pt[:, 0] * f),
                          np.sin(phase_pt[:, 1] + t_pt[:, 0] * f * 1.31),
                          np.sin(phase_pt[:, 2] + t_pt[:, 0] * f * 0.79)], 1)
            out = out + s * (prm["strand_noise_amp"] * (t_pt ** 1.25))

        # 9. flyaways -- a sparse subset thrown further, to break the outline
        if prm["flyaway_density"] > 0:
            s = np.stack([np.sin(phase_pt[:, 0] * 2.7),
                          np.sin(phase_pt[:, 1] * 2.1) - 0.5,
                          np.sin(phase_pt[:, 2] * 3.3)], 1)
            out = out + s * (prm["flyaway_amp"] * (t_pt ** 2.0) * fly_pt)
        return out

    return xf, length_mul


def main():
    tail = argv_tail()
    src, params_path, out_blend, out_abc, log_path = tail[:5]

    prm = dict(DEFAULTS)
    user = json.load(open(params_path, encoding="utf-8"))
    # A RETIRED PARAMETER IS NAMED, not lumped in with typos. Every params file
    # from rounds 1-3 carries `crown_spike_noise`, and the generic
    # unknown-parameter message would send whoever hit it looking for a spelling
    # mistake instead of telling them the mechanism was replaced and why.
    RETIRED = {
        "crown_spike_noise":
            "replaced by crown_lock_gather / crown_lock_lift / "
            "crown_lock_count. It displaced each strand by sin(phase + t) with "
            "a phase drawn independently PER AXIS, so strands wandered in "
            "random directions with no coherence between neighbours -- "
            "raggedness without gathering, which drove edge_roughness the "
            "wrong way and was the entire residual of that axis after round 2. "
            "Set it to 0 and tune the crown_lock_* knobs instead.",
    }
    retired = [k for k in user if k in RETIRED and not k.startswith("_")]
    if retired:
        raise SystemExit("REFUSE: retired parameter(s) in this params file.\n"
                         + "\n".join("  %s: %s" % (k, RETIRED[k])
                                     for k in retired))
    unknown = [k for k in user if k not in DEFAULTS and not k.startswith("_")]
    prm.update({k: v for k, v in user.items() if not k.startswith("_")})

    rep = {"ok": False, "src": src, "params": {k: prm[k] for k in DEFAULTS},
           "unknown_params": unknown, "label": user.get("_label", "")}
    # Fail closed on a typo'd parameter. A silently ignored key reads in the
    # log as a variable that was tested when it never was.
    if unknown:
        rep["error"] = "unknown parameters: %s" % unknown
        json.dump(rep, open(log_path, "w", encoding="utf-8"), indent=2)
        print("__EDIT__" + json.dumps({"ok": False, "error": rep["error"]}))
        return

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    if src.lower().endswith(".blend"):
        # The authored .blend is authoritative for the hero source: it carries
        # groom_root_uv and the GroomProperty mapping, and a round trip through
        # .abc is not the place to discover one of them was dropped.
        bpy.ops.wm.open_mainfile(filepath=src)
    else:
        bpy.ops.wm.alembic_import(filepath=src, as_background_job=False)
    ob = pick_curves_object(bpy)
    d = ob.data

    n_cur = len(d.curves)
    n_pts = len(d.points)
    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)

    def read(attr):
        a = d.attributes.get(attr)
        if a is None:
            return None
        buf = np.zeros(n_pts * 3, dtype=np.float32)
        a.data.foreach_get("vector", buf)
        return buf.reshape(n_pts, 3).astype(np.float64)

    pos = read("position")
    hl = read("handle_left")
    hr = read("handle_right")

    ctx = build_context(pos, starts, sizes)

    # Frame from THIS file's roots, then scale every length parameter into the
    # file's units, so identical params mean identical geometry in a metre file
    # and a centimetre one.
    rep["frame"] = set_frame(ctx[2], prm)
    u = float(prm["length_unit"])
    if u != 1.0:
        for k in _LENGTH_PARAMS:
            prm[k] = prm[k] * u
        rep["length_params_scaled_by"] = u

    # Native units -> centimetres. This was a hardcoded x100, i.e. a silent
    # assumption that every file is in metres. Reporting a 21.3 cm reshape of
    # the hero's groom as "moved_max_cm 2128" is the kind of number that reads
    # as catastrophic and sends a session diagnosing an op that was behaving.
    TO_CM = 100.0 / float(prm["length_unit"])

    w = region_weights(ctx[2], prm)
    xf, length_mul = make_transform(pos, ctx, w, prm, n_cur, starts, sizes)

    new_pos = xf(pos)
    new_hl = xf(hl) if hl is not None else None
    new_hr = xf(hr) if hr is not None else None

    def write(attr, arr):
        if arr is None:
            return
        a = d.attributes.get(attr)
        if a is None:
            return
        a.data.foreach_set("vector", arr.astype(np.float32).ravel())

    # FINAL STRAY CLAMP, on the RESULT. The clamp inside the length multiplier
    # acts on each curve's ORIGINAL length, and every displacement op after it
    # (clump, sweep, rotation, noise) can lengthen a strand again -- measured
    # in UE, iter_016 came out with max_curve_length 114 cm against the vendor
    # file's 26 cm. A bound that other operations can undo is not a bound, so
    # it is re-applied here where nothing follows it.
    if prm["stray_clamp_m"] > 0:
        Lf = curve_lengths(new_pos, starts, sizes)
        over = Lf > prm["stray_clamp_m"]
        n_over = int(over.sum())
        if n_over:
            f = np.ones(n_cur)
            f[over] = prm["stray_clamp_m"] / np.maximum(Lf[over], 1e-9)
            f_pt = f[ctx[0]][:, None]
            rp = ctx[3]
            new_pos = rp + (new_pos - rp) * f_pt
            if new_hl is not None:
                new_hl = rp + (new_hl - rp) * f_pt
            if new_hr is not None:
                new_hr = rp + (new_hr - rp) * f_pt
        rep.setdefault("final_clamp", {})["curves_clamped"] = n_over
        rep["final_clamp"]["max_len_cm_before"] = round(float(Lf.max()) * TO_CM, 3)
        rep["final_clamp"]["max_len_cm_after"] = round(
            float(curve_lengths(new_pos, starts, sizes).max()) * TO_CM, 3)

    # FACE REPEL -- LAST, after the stray clamp, for the same reason the clamp
    # is late: an op that runs before another op can undo it is not a guard.
    if prm["face_repel"] > 0:
        fz = ob.get("face_zone")
        if fz is None:
            raise SystemExit(
                "REFUSE: face_repel is %g but this groom publishes no "
                "'face_zone'. Only author_hero_hair.py writes it, so a pack "
                "groom cannot be styled with this guard on. Set face_repel 0 "
                "and accept that nothing stops tips entering his eyes, or "
                "author the source on his own head."
                % prm["face_repel"])
        f_pt_ = np.asarray(fz["face_pt"], dtype=np.float64)
        f_n = np.asarray(fz["face_n"], dtype=np.float64)
        b_pt = np.asarray(fz["brow_pt"], dtype=np.float64)
        b_n = np.asarray(fz["brow_n"], dtype=np.float64)
        f_n = f_n / max(float(np.linalg.norm(f_n)), 1e-12)
        b_n = b_n / max(float(np.linalg.norm(b_n)), 1e-12)
        margin = max(prm["face_repel_margin"] * SCALP_R, 1e-9)

        def repel(P):
            # Depth INTO the face zone, positive inside each plane.
            s_face = (P - f_pt_) @ f_n
            s_brow = (P - b_pt) @ b_n
            # Ramp the correction in below the brow so there is no hard seam
            # across the forehead -- the same reason every mask here is a
            # smoothstep rather than a box.
            g = smoothstep(0.0, margin, np.clip(s_brow, 0.0, None))
            d = np.clip(s_face, 0.0, None) * g * prm["face_repel"]
            return P - d[:, None] * f_n

        # REPORT THE DEPTH, NOT THE MEMBERSHIP.
        # The first version counted points INSIDE the zone before and after, and
        # it printed `before == after` EXACTLY on every candidate across four
        # agents -- a guard self-reporting zero effect. The texture agent raised
        # it rather than assuming the guard was fine.
        #
        # The op was working; the COUNTER could not see it. At strength s a point
        # at depth d moves to d*(1-s), so below strength 1.0 no point can ever
        # LEAVE the zone and the count is identical by construction. A metric
        # that is pinned by arithmetic is not evidence of anything.
        def depth(P):
            return np.clip((P - f_pt_) @ f_n, 0.0, None) * (
                ((P - b_pt) @ b_n) > 0)

        d0 = depth(new_pos)
        n0 = int((d0 > 0).sum())
        new_pos = repel(new_pos)
        if new_hl is not None:
            new_hl = repel(new_hl)
        if new_hr is not None:
            new_hr = repel(new_hr)
        d1 = depth(new_pos)
        rep["face_repel"] = {
            "points_in_zone": n0,
            "penetration_cm_before": [round(float(d0.sum() * TO_CM), 3),
                                      round(float(d0.max() * TO_CM), 4)],
            "penetration_cm_after": [round(float(d1.sum() * TO_CM), 3),
                                     round(float(d1.max() * TO_CM), 4)],
            "penetration_removed_frac": round(
                1.0 - float(d1.sum()) / max(float(d0.sum()), 1e-12), 4),
            "strength": prm["face_repel"], "margin_units": round(margin, 4),
            "_reading": ("at strength s a point at depth d moves to d*(1-s), so "
                         "membership cannot change below s = 1.0 and only the "
                         "DEPTH is informative"),
            "zone_source": fz.get("_source")}

    write("position", new_pos)
    write("handle_left", new_hl)
    write("handle_right", new_hr)
    d.update_tag()

    rep.update(_DIAG)
    rep["stats"] = {
        "curves": n_cur, "points": n_pts,
        "length_mul": {"min": round(float(length_mul.min()), 4),
                       "p50": round(float(np.median(length_mul)), 4),
                       "max": round(float(length_mul.max()), 4)},
        "region_curve_counts": {
            k: int((w[k] > 0.5).sum()) for k in
            ("crown", "fringe", "side", "temple", "nape")},
        "moved_mean_cm": round(float(
            np.linalg.norm(new_pos - pos, axis=1).mean() * TO_CM), 4),
        "moved_max_cm": round(float(
            np.linalg.norm(new_pos - pos, axis=1).max() * TO_CM), 4)}

    os.makedirs(os.path.dirname(os.path.abspath(out_blend)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["blend"] = out_blend
    rep["ok"] = True
    json.dump(rep, open(log_path, "w", encoding="utf-8"), indent=2)
    print("__EDIT__" + json.dumps({"ok": True, "stats": rep["stats"],
                                   "blend": out_blend}))


if __name__ == "__main__":
    main()
