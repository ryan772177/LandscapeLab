"""author_hero_hair.py — author a real groom on the hero's own head.

    blender.exe --background <authoring.blend> --python this.py -- <out.abc> [strands] [seed]

WHAT MAKES THIS A REAL GROOM AND THE LAST ATTEMPT NOT ONE. Read off a working
groom (`dump_groom_attributes.py` against the demo file), a groom UE renders
carries these, and the object's GroomProperty NAMES which attribute is which:

    att_groom_root_uv  -> surface_uv_coordinate   (curve domain, FLOAT2)
    att_groom_width    -> radius                  (point domain, FLOAT)
    att_groom_guide    -> groom_is_guide

The previous test groom had `position` and `radius` and nothing else -- no
root UVs, and no GroomProperty at all, so the exporter did not know where its
width or its roots were. It imported with the right curve count and rendered
nothing, which is exactly what a groom with no root UVs should do.

THE SHAPE IS PROCEDURAL AND IT IS NOT ARTIST WORK. It follows the reference's
description -- medium layered, side-swept fringe, nape tapering above the
collar -- as a set of numbers rather than as judgement, and every one of them
is recorded in the sidecar so the next pass can move one knob at a time. Call
it a first draft with a recipe, not a hairstyle.

DETERMINISTIC: seeded RNG, so the same seed replays the same groom.

IT DOES NOT SAVE THE .BLEND.
"""

import json
import math
import os
import random
import sys

import bpy
import mathutils


# ---- the shape, as declared numbers ---------------------------------------
# Fractions are of head HEIGHT measured from the mesh, so the same recipe
# transfers to a character with a different skull without re-tuning.
PARAMS = {
    "face_sign_y": -1.0,        # which way the face points along Y.
                                # SETTLED BY RENDER, not by inference:
                                # _verify/20260821_blender/facing/ holds two
                                # orthographic views of the bare head, and -Y
                                # is the one with eyes, nose and lips on it.
                                # Regenerate for a new character with
                                # scripts/blender/render_head_facing.py --
                                # four minutes, and it ends the argument.
    "hairline_frac": 0.82,      # front hairline height, fraction of head height
    "nape_frac": 0.58,          # how far down the BACK hair grows
    "face_reject_dot": 0.95,    # reject roots whose normal faces the front.
                                # NEARLY INERT NOW, AND DELIBERATELY SO: the
                                # position-based face zone below took over its
                                # job, and at 0.45 it was removing the entire
                                # FOREHEAD -- 22,600 front-silhouette pixels,
                                # measured, which is the bald receding look
                                # every render has shown. It survives only as
                                # a cheap pre-filter.
    "face_zone_z_frac": 0.80,   # the BROW, as a fraction of head height. It
                                # is the top of the measured eye band, so it
                                # is anatomy rather than styling, and the
                                # hairline may move without changing it.
    "face_zone_y_frac": 0.28,   # how far back from the face plane counts as
                                # FACE. No root is placed in that zone below
                                # `face_zone_z_frac`, whatever its normal says
                                # -- the normals at the brow belong to eyelids
                                # and sockets and cannot be trusted there.
    "len_top_cm": 12.0,
    "len_side_cm": 6.5,
    "len_nape_cm": 4.5,         # short at the nape: the taper the rear ref wants
    "len_fringe_cm": 6.0,
    "hairline_wave_cm": 3.0,    # the hairline WANDERS by this much across the
                                # head -- widow's peak and temple recessions.
                                # This is the one that breaks the ruled line;
                                # the fade and the lengths cannot.
    "hairline_soft_cm": 1.2,    # the hairline FADES over this many cm --
                                # density falls to zero and length with it.
                                # 0 gives a ruled line across the forehead,
                                # which is what the bowl actually was.
    "hairline_wisp_scale": 0.55,  # roots inside the fade grow hair this
                                # fraction of the region length
    "layer_gain": 0.30,         # a strand rooted further BACK is this much
                                # longer. NOTE WHAT IT DOES NOT DO: forehead
                                # roots have back_frac ~ 0, so this cannot
                                # touch the fringe edge -- measured, 0 -> 0.70
                                # moved the edge spread 0.694 -> 0.689 cm. It
                                # is length on the back of the head, and it is
                                # kept for that.
    "fringe_tilt": 0.18,        # length asymmetry across X, so the side-swept
                                # fringe is longer on the side it sweeps from
    "len_jitter_lo": 0.72,      # per-strand random length. Roughens the edge;
    "len_jitter_hi": 1.28,      # it cannot break it -- that is `layer_gain`.
    "out_bias": 0.15,           # push hair OUTWARD from the head's centre
                                # line, so side hair falls outside the
                                # cheekbones instead of across the eyes
    "sweep_x": 0.14,            # side-swept fringe: lateral bias, +X
    "gravity": 2.55,             # how hard the strand is pulled down per unit
    "lift_side_frac": 0.10,     # how much of `lift_cm` a SIDEWAYS-facing root
                                # gets. On the crown lift buys height; on the
                                # temple the same number buys flare past the
                                # ears, which is the dome outline.
    "lift_cm": 3.50,             # how far it leaves along the normal first
    "back_bias": 1.00,          # push AWAY from the face as it falls
    "front_sweep_gain": 2.00,   # extra backward drive for FRONT-rooted hair,
                                # so the fringe sweeps over the crown instead
                                # of dropping into the eyes
    "drape_clearance": 0.20,    # cm a strand is held off the scalp when it
                                # would otherwise be inside the head
                                # (`skull_shrink` is gone with the ellipsoid:
                                #  an inert parameter reads like a setting)
    "volume_cm": 1.60,          # hair-layer thickness AT THE TIPS: how far
                                # the mass is held off the skull. 0 gives the
                                # slicked-flat look; this is the body.
    "clump": 0.30,              # pull toward a clump centre
    "noise_cm": 0.45,
    "radius_root_cm": 0.035,
    "radius_tip_cm": 0.012,
    "points_per_strand": 12,
}

# THE SHAPE MODEL, AND WHY IT CHANGED.
#
# The first version blended the strand direction from the surface normal
# toward "down" as a function of length: dir = lerp(normal, down, t * droop).
# With 12 points that puts the first step at t = 0.09, so the strand leaves
# the scalp almost exactly along the normal and only turns near the tip. The
# render showed it precisely: a mane radiating outward like a dandelion,
# because on a sphere every normal points somewhere different and nothing was
# pulling them together.
#
# This integrates instead. A strand leaves along the normal for `lift_cm` --
# real hair does stand off the scalp briefly -- and from there each step
# accumulates gravity, so the curve bends the way a hanging thing bends:
# gently at first, hard once it is clear of the head. That is one parameter
# with a physical meaning rather than a blend factor tuned by eye.


# ---- SWEEPING WITHOUT EDITING THE FILE ------------------------------------
# Every styling trial used to mean an edit to the PARAMS block above, so a
# sweep of four variants was four edits' worth of churn and the version that
# produced a given render could not be named afterwards. Any key may be
# overridden for one run with an environment variable, and the run PRINTS what
# it was given, so a render is always traceable to its numbers.
def _apply_env_overrides():
    used = {}
    for k in list(PARAMS.keys()):
        v = os.environ.get("HAIR_" + k.upper())
        if v is None:
            continue
        cur = PARAMS[k]
        PARAMS[k] = int(v) if isinstance(cur, int) else float(v)
        used[k] = PARAMS[k]
    if used:
        print("__PARAM_OVERRIDES__" + json.dumps(used))
    return used


def main():
    _apply_env_overrides()          # effective values land in rep["params"]
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if not tail:
        print("__HAIR__" + json.dumps({"ok": False, "error": "need <out.abc>"}))
        return
    out_abc = tail[0]
    want = int(tail[1]) if len(tail) > 1 else 12000
    seed = int(tail[2]) if len(tail) > 2 else 20260821
    # Radius is overridable so the "is width the reason nothing renders"
    # question can be asked as a single-variable test with an absurd value,
    # rather than by reasoning about units.
    if len(tail) > 3:
        PARAMS["radius_root_cm"] = float(tail[3])
    if len(tail) > 4:
        PARAMS["radius_tip_cm"] = float(tail[4])

    rep = {"ok": False, "out": out_abc, "seed": seed, "params": dict(PARAMS)}
    rng = random.Random(seed)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        rep["error"] = "no mesh in the authoring file"
        print("__HAIR__" + json.dumps(rep))
        return
    head = max(meshes, key=lambda o: len(o.data.vertices))
    me = head.data
    mw = head.matrix_world
    nrm_m = mathutils.Matrix(mw).to_3x3().inverted().transposed()
    rep["head"] = head.name

    world = [mw @ v.co for v in me.vertices]
    zs = [p.z for p in world]
    ys = [p.y for p in world]
    z_lo, z_hi = min(zs), max(zs)
    height = z_hi - z_lo

    # WHICH WAY IS THE FACE? SETTLED BY RENDER, READ FROM PARAMS.
    #
    # Two automatic tests were tried and neither is reliable: a mid-height
    # slice comparing |max Y| to |min Y| about the ORIGIN (correct here
    # only because this head happens to sit near Y = 0), and a slice
    # centroid reach test, which is wrong -- at 72% of head height the
    # OCCIPUT is the protruding feature, not the nose, so it named the
    # back of the skull as the face.
    #
    # A protrusion test cannot tell a nose from an occiput without knowing
    # where the eyes are. Two orthographic renders of the bare head can,
    # and they cost four minutes: _verify/20260821_blender/facing/ shows
    # -Y carrying eyes, nose and lips, and +Y the occiput and nape.
    #
    # So the value is DECLARED and the picture is its justification.
    # scripts/blender/render_head_facing.py regenerates it per character.
    face_sign = float(PARAMS["face_sign_y"])
    rep["face_sign_y"] = face_sign
    rep["face_sign_source"] = ("DECLARED in PARAMS -- automatic derivation was "
                               "wrong in both directions; see the comment")
    for label, frac in (("slice_0.55", 0.55), ("slice_0.72", 0.72)):
        band = [p for p in world if abs(p.z - (z_lo + frac * height)) < 0.08 * height]
        if band:
            ym = sum(p.y for p in band) / len(band)
            rep.setdefault("face_sign_evidence", {})[label] = {
                "reach_+y": round(max(p.y for p in band) - ym, 2),
                "reach_-y": round(ym - min(p.y for p in band), 2)}

    # ---- root selection: scalp, not face ---------------------------------
    uv_layer = me.uv_layers.active
    if uv_layer is None:
        rep["error"] = "head has no active UV map; a groom needs root UVs"
        print("__HAIR__" + json.dumps(rep))
        return
    rep["uv_map"] = uv_layer.name
    # vertex -> uv, taken from any loop that uses it
    vert_uv = {}
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            if vi not in vert_uv:
                u = uv_layer.data[li].uv
                vert_uv[vi] = (float(u[0]), float(u[1]))

    hairline_z = z_lo + PARAMS["hairline_frac"] * height
    nape_z = z_lo + PARAMS["nape_frac"] * height

    # THE FACE ZONE, BY POSITION, BECAUSE THE NORMALS THERE LIE.
    # Both existing guards -- `face_reject_dot` and the swept `required_z` --
    # read the vertex NORMAL, and a MetaHuman face carries eyelids, sockets
    # and lash geometry at exactly the brow whose normals do not point
    # forward. A brow vertex therefore passes the face rejection AND gets a
    # low `t_face`, which drops its required height toward the nape and makes
    # it a legal root.
    #
    # Diagnosed rather than guessed (`diagnose_face_hair.py`): of the strands
    # putting hair over the eyes, 99.4% had ROOTS at or below 0.74 of head
    # height -- z 168.7 against a hairline at 171.68 -- 88% in the front third
    # of the head and 87% within a quarter-width of the midline, and 98.5%
    # were already over the face within the first quarter of the strand. They
    # are not strands falling into his eyes. They are hair growing on his brow.
    #
    # Y is measured over the SKULL only (above the nape), so the shoulders of
    # the bust do not stretch the range.
    # THE BROW LINE IS ANATOMY AND DOES NOT MOVE WITH THE HAIRCUT.
    # Tying the face zone to `hairline_z` couples the two: lowering the
    # hairline to bring hair forward at the sides would also shrink the
    # protection over the eyes, which is the thing being protected. The top of
    # the eye band is the brow, it is a property of the head, and the styling
    # parameters may move around it freely.
    # THE BROW IS MEASURED, NOT A FRACTION OF THE MESH BOUNDS.
    # `face_zone_z_frac` 0.80 put it at 170.93 on this head; the socket-recess
    # measurement puts it at 167.24, and a line drawn at 170.93 on his own
    # bare-head render sits three centimetres up his forehead. Every root this
    # filter rejected between 167.24 and 170.93 was forehead hair being refused
    # as if it were growing on his eye, which is why four attempts at a fringe
    # produced a bare brow. See scripts/blender/head_frame.py for the method and
    # _verify/20260822_hero_authored/BROW_CHECK.png for the evidence.
    import sys as _s
    import os as _o
    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    from head_frame import measure_head as _measure_head
    _hf = _measure_head(
        np.array([[q.x, q.y, q.z] for q in world], dtype=np.float64)
        if "np" in dir() else
        __import__("numpy").array([[q.x, q.y, q.z] for q in world]),
        __import__("numpy").array([0.0, 0.0, 1.0]),
        __import__("numpy").array([0.0, face_sign, 0.0]),
        __import__("numpy").array([1.0, 0.0, 0.0]))
    brow_z = float(_hf["brow_up"])
    rep["head_frame"] = _hf
    rep["_brow_source"] = ("MEASURED by head_frame.measure_head; the "
                           "face_zone_z_frac fraction would have said %.3f"
                           % _hf["_superseded_fraction_brow_up"])

    skull_y = [q.y for q in world if q.z >= nape_z]
    y_face_end = min(skull_y) if face_sign < 0 else max(skull_y)
    y_back_end = max(skull_y) if face_sign < 0 else min(skull_y)
    y_span = (y_back_end - y_face_end) or 1e-6

    xs_all = [q.x for q in world]
    head_mid_x0 = 0.5 * (min(xs_all) + max(xs_all))
    head_half_x0 = 0.5 * (max(xs_all) - min(xs_all))
    wave_phase = (seed % 1000) * 0.017

    cand = []
    soft_roots = set()          # accepted inside the hairline fade
    for vi, p in enumerate(world):
        if vi not in vert_uv:
            continue
        n = (nrm_m @ me.vertices[vi].normal).normalized()
        facing_front = n.y * face_sign
        # THE FACE IS REJECTED BY ORIENTATION, THE NECK BY HEIGHT.
        # Both are needed and each was tried alone. Orientation alone at a
        # tight threshold also removed the front half of the CROWN, whose
        # normals tilt slightly forward, and left a bald dome. Height alone
        # let the neck grow hair.
        if facing_front > PARAMS["face_reject_dot"]:
            continue
        # NO HAIR ON THE FRONT OF THE FACE BELOW THE HAIRLINE. A statement
        # about anatomy, tested against POSITION, so no normal can defeat it.
        # This is the third guard on the same region and the first that does
        # not consult a normal -- prefer an input that cannot express the bad
        # value over a test that has to reject it.
        if (p.y - y_face_end) / y_span <= PARAMS["face_zone_y_frac"] \
                and p.z < brow_z:
            continue
        # THE HAIRLINE SWEEPS: HIGH AT THE FRONT, LOW AT THE NAPE.
        # A single height cut is not a hairline. With `hairline_frac` 0.66 of
        # the FULL mesh bounds the cut landed at Z 165.7 -- and the eye band
        # measures 164.2..170.9, so the "hairline" was across his brow and
        # hair grew from it straight down over his eyes.
        #
        # The fractions are of a mesh that includes the NECK, so they are not
        # skull fractions and cannot be read as anatomy. What is anatomical is
        # that the required height depends on WHICH WAY THE SCALP FACES:
        # forward-facing scalp must be high (above the brow), back-facing
        # scalp may run right down to the nape.
        # THE TEMPLES COUNT AS FRONT. Interpolating on front-ness alone gives
        # a side-facing root t = 0.5, so its required height is the MIDPOINT
        # between nape and hairline -- Z 168 here, and the eye band measures
        # 164.2..170.9. The hairline ran straight through his eye sockets at
        # the temples, and strands rooted there fell into them.
        #
        # A real hairline rises at the temples as well as across the forehead,
        # so sideways-facing scalp is held to the same height as forward-
        # facing scalp. Only genuinely BACK-facing scalp runs down to the nape.
        t_face = min(1.0, max(0.0, max((facing_front + 1.0) * 0.5, abs(n.x))))
        required_z = nape_z + (hairline_z - nape_z) * t_face
        # AND THE LINE IS IRREGULAR ACROSS ITS WIDTH.
        # A fade alone does not break it: every column gets the same
        # statistical treatment, so the boundary simply moves DOWN and stays
        # level. Measured -- `hairline_soft_cm` 0 -> 3.5 moved the fringe edge
        # spread 0.691 -> 0.711 cm, i.e. nothing, while costing over-face
        # 0.74 -> 2.89%.
        #
        # What makes a real hairline read as a hairline is that it WANDERS:
        # a widow's peak, temple recessions, a couple of centimetres of
        # irregularity along its length. That is variation in the threshold as
        # a function of position, not variation in the strands, and it is the
        # only one of the three that can change a per-column statistic.
        #
        # Two incommensurable sines so the wave does not repeat over the head,
        # phase from the seed so a given character is deterministic.
        # RAISE-ONLY. A symmetric wave lowers the line in half its columns,
        # and near the temples -- where the face zone does not reach, because
        # a temple is not the front of the face -- that puts roots below the
        # brow. Measured: a +-2.2 cm wave took over-face 0.74% -> 4.94%,
        # undoing the previous fix to buy irregularity.
        #
        # A hairline that only ever RECEDES reads just as irregular and
        # cannot push hair toward the eyes. The trade disappears rather than
        # being balanced.
        w = PARAMS["hairline_wave_cm"]
        if w > 0.0:
            fx = (p.x - head_mid_x0) / max(1e-6, head_half_x0)
            lobe = (0.6 * math.sin(fx * 7.3 + wave_phase)
                    + 0.4 * math.sin(fx * 17.1 + wave_phase * 2.1))
            required_z += w * 0.5 * (1.0 + lobe)        # in [0, w]
        # A HAIRLINE IS A GRADIENT, NOT A THRESHOLD, AND THAT IS THE BOWL.
        # `p.z >= required_z` is a hard cut: a vertex qualifies or it does
        # not, so root density goes from full to zero across one vertex and
        # the render draws a line. Measured on the front view, the lowest hair
        # pixel per column across the central 40% had a spread of 0.696 cm
        # over a 2.639 cm range -- a level line ruled across his forehead.
        #
        # AND THE LINE IS MADE OF ROOTS, NOT TIPS. `layer_gain` 0 -> 0.70
        # moved that spread 0.694 -> 0.689 cm while the front silhouette grew
        # 22%, which is the tell: no length parameter can break an edge that
        # is drawn by where the hair STARTS. Real hairlines are diffuse --
        # thinning wisps over a couple of centimetres, not a shaved border.
        #
        # So within `hairline_soft_cm` below the line a vertex is accepted
        # with a probability that falls to zero, and those roots grow SHORTER
        # hair. Density and length both fade, which is what the edge of a
        # hairline actually does.
        soft = PARAMS["hairline_soft_cm"]
        if p.z >= required_z:
            cand.append(vi)
        elif soft > 0.0 and p.z >= required_z - soft:
            frac = (p.z - (required_z - soft)) / soft      # 0 at the bottom
            if rng.random() < frac * frac:
                cand.append(vi)
                soft_roots.add(vi)
    if not cand:
        rep["error"] = "no scalp candidates"
        print("__HAIR__" + json.dumps(rep))
        return
    rep["scalp_candidates"] = len(cand)

    # ---- SAMPLE BY AREA, NOT BY VERTEX ------------------------------------
    # Roots were drawn uniformly over candidate VERTICES, and vertex density
    # on this mesh is nothing like uniform: a census of the previous groom put
    # 51.2% of 20,000 roots BELOW 0.60 of head height and only 2.9% on the
    # crown above 0.90. The render agreed -- a bald dome with a band of hair
    # round the sides.
    #
    # The cranium is large faces and few vertices; the neck and jaw are the
    # opposite. Weighting each candidate by the area it represents makes the
    # root DENSITY uniform over the scalp, which is what "even coverage"
    # actually means and what a vertex count silently is not.
    vert_area = [0.0] * len(me.vertices)
    for poly in me.polygons:
        share = poly.area / max(1, len(poly.vertices))
        for vi in poly.vertices:
            vert_area[vi] += share
    weights = [vert_area[vi] for vi in cand]
    total_w = sum(weights)
    if total_w <= 0.0:
        weights = [1.0] * len(cand)
        total_w = float(len(cand))
    cum = []
    acc = 0.0
    for w_ in weights:
        acc += w_
        cum.append(acc)
    import bisect
    roots = [cand[bisect.bisect_left(cum, rng.random() * total_w)]
             for _ in range(want)]
    rep["root_sampling"] = "area-weighted"
    rep["scalp_area_cm2"] = round(total_w, 2)

    # ---- THE SKULL, QUERIED, SO HAIR CAN DRAPE OVER IT --------------------
    # A strand rooted on top of the skull has a normal of roughly +Z, gravity
    # pulls it straight down, and nothing stops it: it falls THROUGH the head
    # and re-emerges at eye level. That is the bare crown and the strands
    # across the eyes, and it is one cause rather than two.
    #
    # AN ELLIPSOID WAS TRIED TWICE AND FAILED IN BOTH DIRECTIONS. The
    # enclosing fit gave radii [9.54, 14.36, 13.96] with its centre dragged
    # 6.88 cm toward the face by the temple roots, and pushed strands onto a
    # shell in FRONT of the head -- worse than no fix. Shrinking it to the
    # 90th percentile x 0.82 gave [6.56, 6.06, 5.05], so far inside the skull
    # that nothing intersected and the render was identical to no drape at
    # all. A cranium with a face attached is not an ellipsoid, and two
    # failures in opposite directions from one family of fix is the signal to
    # change family rather than to pick a third constant.
    #
    # So ask the mesh. A BVH tree answers "where is the nearest surface, and
    # which way does it face" exactly, with no shape assumption at all.
    from mathutils.bvhtree import BVHTree
    dg_head = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(head, dg_head)
    mwi = mw.inverted()
    rep["collision"] = "BVHTree.FromObject + find_nearest, per point"

    def drape(p_world, clearance):
        """Push a point out of the head if it is inside it.

        Points OUTSIDE are left alone: hair hanging beside the head should
        hang, not be dragged onto the scalp. Only genuine penetration is
        corrected, which is the property both ellipsoids failed to have.

        The inside test is the sign of (point - nearest) . normal, which is
        exact for a closed surface and needs no notion of a centre -- the
        thing that made the ellipsoid centre-fitting go wrong.
        """
        lp = mwi @ p_world
        loc, nor, idx, dist = bvh.find_nearest(lp)
        if loc is None:
            return p_world
        inside = (lp - loc).dot(nor) < 0.0
        if inside or dist < clearance:
            return mw @ (loc + nor * clearance)
        return p_world

    # ---- build the strands ------------------------------------------------
    head_mid_x = 0.5 * (min(p.x for p in world) + max(p.x for p in world))
    head_half_x = 0.5 * (max(p.x for p in world) - min(p.x for p in world))
    P = PARAMS["points_per_strand"]
    hair = bpy.data.hair_curves.new("AlpineHero_Hair_v1")
    hair_ob = bpy.data.objects.new("AlpineHero_Hair_v1", hair)
    bpy.context.scene.collection.objects.link(hair_ob)

    # PUBLISH THE FACE ZONE ON THE OBJECT, so downstream tools consume the
    # producer's numbers instead of re-deriving them.
    #
    # This zone already exists above as a ROOT filter: no root is placed in
    # front of the face plane below the brow. That guard is complete for
    # authoring and blind to everything after it -- a later tool that pulls
    # TIPS forward puts hair over his eyes without placing a single root in
    # the zone, which is exactly what the ported 028 parameters did (front
    # hair-over-face 2,413 -> 9,486 px).
    #
    # Written as two PLANES rather than as the three scalars, because the
    # consumer works in a frame declared per file (the hero's blend is Z-up in
    # centimetres, a pack groom is Y-up in metres) and a plane needs no
    # translation between them. Each normal points INTO the excluded region,
    # so a point is in the face zone when it is on the positive side of both.
    #
    # Non-negotiable 24: this is ONE declaration with two consumers, not two
    # lists that have to be kept in agreement.
    _face_zone = {
        "face_pt": [0.0, y_face_end + PARAMS["face_zone_y_frac"] * y_span,
                    0.0],
        "face_n": [0.0, face_sign, 0.0],
        "brow_pt": [0.0, 0.0, brow_z],
        "brow_n": [0.0, 0.0, -1.0],
        "_source": "author_hero_hair.py face_zone_y_frac/face_zone_z_frac",
    }
    hair_ob["face_zone"] = _face_zone
    # Report from the plain dict, NOT by reading the ID property back: Blender
    # returns the lists as IDPropertyArray, which json refuses, and the failure
    # lands at the very end of a run that has already done all its work.
    rep["face_zone"] = _face_zone
    hair_ob.parent = head
    hair.surface = head
    hair.surface_uv_map = uv_layer.name
    hair.add_curves([P] * len(roots))

    pts = hair.points
    down = mathutils.Vector((0.0, 0.0, -1.0))
    w = 0
    uvs = []
    for si, vi in enumerate(roots):
        root = world[vi]
        n = (nrm_m @ me.vertices[vi].normal).normalized()
        t_h = (root.z - z_lo) / height
        facing = n.y * face_sign
        forward = facing > 0.2
        # How front-of-head this root is, 0 at the nape and 1 at the hairline.
        # Drives how hard the strand is swept back rather than dropped.
        #
        # THE SAME EXPRESSION THE HAIRLINE USES, AND IT HAS TO BE.
        # The hairline counts a TEMPLE as front (`abs(n.x)`, because sideways
        # scalp sits at the front of the head even though its normal points
        # sideways). This did not, so a temple root got t_root ~ 0.5, half the
        # backward drive, and 6.5 cm of side length carried it from z 171.7
        # straight down into the eye band at 165 -- the wisps hanging over
        # both eyes in every front render. Raising `front_sweep_gain` from 1.2
        # to 2.4 moved the crossing figure 3.10% -> 3.06%, which is the tell:
        # the strands doing it were never being swept.
        #
        # One physical fact -- how front-of-head is this root -- written twice
        # and differently. It is now written once.
        t_root = min(1.0, max(0.0, max((facing + 1.0) * 0.5, abs(n.x))))

        # length by region -- the recipe's whole shape lives in these lines
        if forward and root.z > hairline_z:
            length = PARAMS["len_fringe_cm"]
        elif t_h > 0.86:
            length = PARAMS["len_top_cm"]
        elif root.z < hairline_z:
            length = PARAMS["len_nape_cm"]
        else:
            length = PARAMS["len_side_cm"]

        # LAYERING, AND IT IS WHAT STOPS THE BOWL.
        # Measured: the fringe edge -- the lowest hair pixel per column across
        # the central 40% of the front view -- had a spread of 0.696 cm over a
        # 2.639 cm range. A nearly level line drawn across his forehead, which
        # is exactly what a bowl cut is.
        #
        # The cause is structural, not a value: every forehead root sits on
        # the same hairline arc and every one gets the same length, so the
        # tips land on an arc parallel to it. Random jitter cannot fix that --
        # it roughens the line without breaking it, because the mean is what
        # draws the edge.
        #
        # Real layering is systematic: a strand rooted further BACK is longer,
        # so it falls PAST the strand in front of it rather than ending beside
        # it. That is one multiplier with a physical reading, and it applies
        # to every region rather than being a fringe special case.
        back_frac = (root.y - y_face_end) / y_span
        length *= 1.0 + PARAMS["layer_gain"] * max(0.0, min(1.0, back_frac))

        # AND THE SWEEP IS AN ASYMMETRY, NOT ONLY A DIRECTION.
        # A side-swept fringe is longer on the side it sweeps FROM. `sweep_x`
        # already pushes it sideways; without a length difference the sweep
        # slides a level edge sideways and it stays level.
        side_f = (root.x - head_mid_x) / max(1e-6, head_half_x)
        length *= 1.0 + PARAMS["fringe_tilt"] * side_f

        # WISPS AT THE HAIRLINE. A root accepted inside the fade is at the
        # edge of the growth region, and hair there is short as well as
        # sparse. Fading density alone still ends every strand on the same
        # arc, just with fewer of them.
        if vi in soft_roots:
            length *= PARAMS["hairline_wisp_scale"]

        length *= rng.uniform(PARAMS["len_jitter_lo"], PARAMS["len_jitter_hi"])

        # clump centre: a nearby direction shared by neighbouring strands, so
        # the result reads as locks rather than as fur
        cl = mathutils.Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
        cl.normalize()

        # AWAY FROM THE FACE, derived from the measured facing sign rather
        # than hardcoded, so a character whose mesh faces the other way does
        # not grow hair forward over its eyes.
        back = mathutils.Vector((0.0, -face_sign, 0.0))
        # OUTWARD FIRST, SWEPT SECOND.
        # `sweep_x` pushed every strand toward +X regardless of which side of
        # the head it grew on, so on the -X side it carried hair INWARD across
        # the face -- the clumps sitting over both eye sockets. A person's
        # hair falls outside the cheekbones; only the styling sweep is
        # one-directional.
        # AND THE OUTWARD BIAS IS A RAMP, NOT A SIGN.
        # `sign()` is a step function at the midline: two strands born a
        # millimetre apart on either side get thrown a full bias-width in
        # OPPOSITE directions, which is a parting by construction. Measured
        # on the crown, scalp exposure was 29.21% within 1.5 cm of the midline
        # against 8.64% laterally -- a 3.4x stripe, in the same place the
        # front render showed bare skin. A strand growing ON the centre line
        # has no outward direction, and the code now says so.
        side = (root.x - head_mid_x) / max(1e-6, 0.35 * head_half_x)
        side = max(-1.0, min(1.0, side))
        sweep = mathutils.Vector((
            side * PARAMS["out_bias"] + PARAMS["sweep_x"] * (1.0 if forward else 0.4),
            0.0, 0.0))
        up = max(0.0, n.z)
        lift_eff = PARAMS["lift_cm"] * (PARAMS["lift_side_frac"]
                                        + (1.0 - PARAMS["lift_side_frac"]) * up)
        seg = length / (P - 1)
        # Leave along the normal, then let gravity take it. `lift_cm` is how
        # much of the strand is spent standing off the scalp before the fall
        # dominates -- the thing the previous blend got wrong by spreading it
        # over the whole strand.
        d = n.copy()
        prev = root.copy()
        for k in range(P):
            if k == 0:
                lp = mw.inverted() @ root
                pts[w].position = (lp.x, lp.y, lp.z)
                w += 1
                continue
            t = float(k) / (P - 1)
            travelled = seg * k
            # Gravity accumulates once the strand is clear of the scalp.
            #
            # LIFT IS ALONG THE SCALP NORMAL, AND THAT MEANS SOMETHING
            # DIFFERENT ON THE CROWN THAN ON THE TEMPLE. On top of the head
            # the normal points up, so lift buys HEIGHT -- the body that made
            # the volume fix work. On the side of the head it points sideways,
            # so the same number buys FLARE, and flare past the ears is the
            # dome outline half of "it reads as a bowl".
            #
            # One number cannot mean both. Lift is scaled by how upward the
            # root normal is, so hair on top stands up and hair on the sides
            # lies down, which is what hair does.
            g = PARAMS["gravity"] * max(0.0, travelled - lift_eff) / max(1e-6, length)
            # FRONT HAIR IS SWEPT BACK, NOT DROPPED.
            # With the hairline at Z 173 and 7.5 cm of length, a strand that
            # simply falls lands at 165.5 -- and the eye band is 164.2..170.9.
            # Hair over the eyes was arithmetic, not a defect: a 7.5 cm fringe
            # falling forward reaches the eyes on a real person too. The
            # reference sweeps it back over the crown, so front-rooted strands
            # get proportionally more backward drive than side or back ones.
            back_gain = PARAMS["back_bias"] * (1.0 + PARAMS["front_sweep_gain"] * t_root)
            d = d + down * (g * seg) + back * (back_gain * seg * t) \
                  + sweep * (seg * t)
            d = d.lerp(cl, PARAMS["clump"] * seg * t)
            if d.length < 1e-6:
                d = n.copy()
            d.normalize()
            pos = prev + d * seg
            pos += mathutils.Vector((rng.gauss(0, 1), rng.gauss(0, 1),
                                     rng.gauss(0, 1))) * (PARAMS["noise_cm"] * t / P)
            # DRAPE: a strand may not pass through the skull. Without this a
            # crown strand falls straight down through the head and comes out
            # over the eyes, which is exactly what two renders showed.
            # CONSTANT clearance, not scaled by t. Under the ellipsoid it was
            # a fraction of a radius and scaling made sense; it is now a
            # distance in centimetres, and a strand near its root needs the
            # same few millimetres of standoff as one near its tip.
            # VOLUME AS A THICKENING SHELL, AND IT IS PAID FOR IN COVERAGE.
            # Real hair has body because strands rest on the strands beneath
            # them, so the layer is thin at the roots and thick further out.
            #
            # BUT INFLATING THE SHELL STRIPS THE SCALP, and that is measured
            # rather than argued. Across three versions the tip shell went
            # 1.21 -> 2.63 -> 3.24 cm and the fraction of scalp with no hair
            # within 8 mm went 11.5 -> 20.6 -> 32.1%. Pushing a point out
            # along the surface normal on a convex skull spreads neighbouring
            # points apart as r^2, so body bought at a constant rate along the
            # strand is bought straight out of coverage. The UE render was
            # unchanged across the last of those steps while the thickness
            # number rose 23%.
            #
            # So the ramp is QUADRATIC: the strand lies on the head through
            # its first half and only the outer part stands off, which is
            # where a real lock rests on the ones beneath it. The remaining
            # expansion is paid for with strand count, not absorbed silently.
            pos = drape(pos, PARAMS["drape_clearance"] + PARAMS["volume_cm"] * t * t)
            # Re-derive the direction from where the point ACTUALLY ended up,
            # so the next step continues along the draped path rather than the
            # one that went through the head.
            d = (pos - prev)
            if d.length > 1e-6:
                d.normalize()
            lp = mw.inverted() @ pos
            pts[w].position = (lp.x, lp.y, lp.z)
            w += 1
            prev = pos
        uvs.append(vert_uv[vi])

    # ---- THE ATTRIBUTES THAT MAKE IT A GROOM ------------------------------
    # radius, point domain, tapering root to tip
    try:
        r0, r1 = PARAMS["radius_root_cm"], PARAMS["radius_tip_cm"]
        for si in range(len(roots)):
            for k in range(P):
                pts[si * P + k].radius = r0 + (r1 - r0) * (float(k) / (P - 1))
        rep["radius"] = [r0, r1]
    except Exception as exc:
        rep["radius_error"] = str(exc)

    # ROOT UV AS **FLOAT_VECTOR**, CURVE DOMAIN, UNDER OUR OWN NAME.
    #
    # Not FLOAT2, and the reason is a bug in the exporter rather than a
    # preference. Its FLOAT2 branch builds a flat array of 2N floats and
    # copies it into an (N,2) view without reshaping:
    #     could not broadcast input array from shape (24000,) into (12000,2)
    # Its FLOAT_VECTOR branch works. The demo file never trips this because
    # its Geometry Nodes stack converts surface_uv_coordinate from FLOAT2
    # (authored) to FLOAT_VECTOR (evaluated) before the exporter sees it --
    # measured on both sides of that stack.
    #
    # A groom with no GN stack hands over the raw FLOAT2 and dies. So the
    # root UV is written as a FLOAT_VECTOR with w=0 under a custom name,
    # which also avoids fighting Blender over the built-in attribute's type.
    try:
        a = hair.attributes.get("groom_root_uv")
        if a is None:
            a = hair.attributes.new("groom_root_uv", "FLOAT_VECTOR", "CURVE")
        for si, uv in enumerate(uvs):
            a.data[si].vector = (uv[0], uv[1], 0.0)
        rep["root_uv_attr"] = {"name": "groom_root_uv",
                               "type": "FLOAT_VECTOR",
                               "written": len(uvs)}
    except Exception as exc:
        rep["root_uv_error"] = str(exc)

    rep["curves"] = len(roots)
    rep["points"] = w
    rep["authored_attrs"] = [x.name for x in hair.attributes]

    b = [hair_ob.matrix_world @ mathutils.Vector(c) for c in hair_ob.bound_box]
    bz = [p.z for p in b]
    rep["groom_z"] = [round(min(bz), 3), round(max(bz), 3)]
    rep["head_z"] = [round(z_lo, 3), round(z_hi, 3)]

    # ---- TELL THE EXPORTER WHICH ATTRIBUTE IS WHICH -----------------------
    # Without these names the exporter writes neither width nor root UVs, and
    # the result imports with a correct curve count and renders nothing.
    try:
        gp = hair_ob.GroomProperty
        gp.att_groom_root_uv = "groom_root_uv"
        gp.att_groom_width = "radius"
        rep["groom_property"] = {"att_groom_root_uv": gp.att_groom_root_uv,
                                 "att_groom_width": gp.att_groom_width}
    except Exception as exc:
        rep["groom_property_error"] = str(exc)

    # ---- export -----------------------------------------------------------
    for o in bpy.context.selected_objects:
        o.select_set(False)
    hair_ob.select_set(True)
    bpy.context.view_layer.objects.active = hair_ob
    os.makedirs(os.path.dirname(out_abc) or ".", exist_ok=True)
    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_abc, check_existing=False, groom_scale=1.0,
            groom_width_scale=True, groom_radius_to_diameter=True,
            groom_animation=False, node_execution=False)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__HAIR__" + json.dumps(rep))
        return
    if not os.path.isfile(out_abc):
        rep["error"] = "no file at " + out_abc
        print("__HAIR__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc)
    rep["ok"] = rep["bytes"] > 0

    # OPTIONALLY SAVE THE AUTHORED SCENE, to a NEW file.
    # Added after a downstream stage ran against the authoring template and
    # found `hair_curves: 0` -- the strands live only in this process unless
    # they are written somewhere, and the template contains an EMPTY hair
    # object by design. A second stage that needs the authored curves needs
    # them on disk. Never writes the template or any vendor file.
    if len(tail) > 5 and tail[5]:
        out_blend = tail[5]
        try:
            os.makedirs(os.path.dirname(out_blend) or ".", exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            rep["saved_blend"] = out_blend
            rep["saved_bytes"] = os.path.getsize(out_blend)
        except Exception as exc:
            rep["save_error"] = "%s: %s" % (type(exc).__name__, exc)

    print("__HAIR__" + json.dumps(rep))


main()
