"""preview_hair.py — render the authored hair on the head IN BLENDER, and
census where its roots and tips actually are.

    blender.exe --background <authored.blend> --python this.py -- <out_dir>

WHY THIS EXISTS. Every styling look so far cost a full round trip: author,
build the guide stack, export, import to UE, bind, place, render. Four
minutes to see a shape that Blender can draw in seconds, and the shape is
decided entirely on the Blender side. The UE trip proves the GROOM; it has
nothing to say about whether the hair looks right.

AND IT COUNTS RATHER THAN LOOKING. Two defects are open -- a thin crown and
strands across the eyes -- and I have now guessed at both twice. So this
bins the ROOTS by region and asks where the TIPS end up, which turns "the
crown looks bare" into a number that either shows roots there or does not.

The face box is derived from the head's own bounds and the SETTLED facing
(-Y, proven by render), not from a guessed axis.

WHAT IT REPORTS, AND WHICH ONES ARE GATES:

    scalp_exposed_pct       GATE. % of scalp with no hair point within 8 mm.
                            Scalp is where the ROOTS are, not a second copy
                            of the hairline rule.
    scalp_exposed_by_zone   GATE. The same split at |x| < 3 cm, because a
                            parting and a thin nape are one aggregate and
                            two different defects.
    silhouette.*            GATE. Difference render against the head alone
                            through the SAME camera. This is the one that
                            matches the eye: hair_px is how much of the
                            picture is hair, height_gain_cm is how much
                            taller it made him.
    shell_thickness_*       DESCRIPTIVE ONLY. How far the layer sits off the
                            skull. It rose 23% on a change that left the UE
                            render identical, because standoff is not
                            coverage. Do not gate on it.
    tips_in_face_box        DESCRIPTIVE ONLY, kept as the record of a metric
    strands_crossing_*      that could not see its own subject. Both are
                            superseded by silhouette.front.hair_over_face_px.

EVERY ONE OF THE FOUR MISLEADING METRICS THIS FILE HAS CARRIED WAS CAUGHT THE
SAME WAY: an input that should have moved the number did not. Run that test on
a new metric before trusting it, not after it misleads.

HOW THE GATES ARE ENFORCED. This script COUNTS and EMITS a JSON report on the
`__PREVIEW__` line; it does not itself exit non-zero on a failed gate (the one
exception is a missing head/hair, which exits 2). "GATE" above means the
CONSUMER gates on that field (judge.py, score_sides.py). So a consumer MUST
treat a missing GATE key -- or a `silhouette_error` / `scalp_error` field --
as a REFUSAL, never as a pass: the silhouette block is wrapped so a render or
numpy failure cannot abort the census, and it records the error rather than
the metric. A gate value that is absent is "could not look", not "0".
"""

import json
import os
import sys

import bpy
import mathutils

FACE_SIGN = -1.0        # settled by render: _verify/.../facing/


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    out_dir = tail[0] if tail else "."
    os.makedirs(out_dir, exist_ok=True)
    rep = {"blend": bpy.data.filepath}

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    curves = [o for o in bpy.data.objects if o.type == "CURVES"
              and len(o.data.curves) > 0]
    if not meshes or not curves:
        rep["error"] = "need a head and authored hair"
        print("__PREVIEW__" + json.dumps(rep))
        # A missing head/hair is "could not look", not a clean render. Emit the
        # marker (so a consumer still gets the reason) then exit non-zero.
        sys.exit(2)
    hair = max(curves, key=lambda o: len(o.data.curves))
    head = hair.data.surface or max(meshes, key=lambda o: len(o.data.vertices))
    rep["hair"], rep["head"] = hair.name, head.name

    hmw = head.matrix_world
    hp = [hmw @ v.co for v in head.data.vertices]
    z_lo = min(p.z for p in hp)
    z_hi = max(p.z for p in hp)
    height = z_hi - z_lo
    rep["head_z"] = [round(z_lo, 2), round(z_hi, 2)]

    # ---- census -----------------------------------------------------------
    mw = hair.matrix_world
    data = hair.data
    starts = [c.first_point_index for c in data.curves]
    sizes = [c.points_length for c in data.curves]
    roots, tips = [], []
    for i, s in enumerate(starts):
        if sizes[i] == 0:
            # A zero-point curve would make data.points[s + sizes[i] - 1] read
            # data.points[s - 1] -- the PREVIOUS curve's last point -- and log a
            # silently wrong tip. Skip it; roots and tips stay index-aligned.
            continue
        roots.append(mw @ mathutils.Vector(data.points[s].position))
        tips.append(mw @ mathutils.Vector(data.points[s + sizes[i] - 1].position))

    def frac(p):
        return (p.z - z_lo) / height

    bands = {"crown_>0.90": 0, "upper_0.80-0.90": 0, "mid_0.70-0.80": 0,
             "lower_0.60-0.70": 0, "below_0.60": 0}
    for p in roots:
        f = frac(p)
        if f > 0.90:
            bands["crown_>0.90"] += 1
        elif f > 0.80:
            bands["upper_0.80-0.90"] += 1
        elif f > 0.70:
            bands["mid_0.70-0.80"] += 1
        elif f > 0.60:
            bands["lower_0.60-0.70"] += 1
        else:
            bands["below_0.60"] += 1
    rep["root_bands"] = bands
    rep["roots"] = len(roots)

    # TIPS IN THE FACE BOX. "Over the eyes" becomes a count: a tip inside the
    # eye band whose nearest head-surface normal is face-facing (see in_box).
    eye_lo, eye_hi = z_lo + 0.62 * height, z_lo + 0.80 * height
    # OVER THE FACE MEANS OVER FACE-FACING SKIN, NOT MERELY FORWARD OF A LINE.
    # The first box was "forward of the mid-Y plane and inside the eye band",
    # which counts hair standing off the TEMPLE -- and adding 1.6 cm of volume
    # then read as a doubling of hair over the eyes when nothing had moved
    # onto the face. The tell was a crossing figure identical to two decimal
    # places across a change that visibly altered the shell thickness.
    #
    # A point is over the face when the nearest point of the HEAD is on
    # face-facing skin. The BVH already knows that, and it needs no midline.
    from mathutils.bvhtree import BVHTree as _BVH
    _dg0 = bpy.context.evaluated_depsgraph_get()
    _bvh0 = _BVH.FromObject(head, _dg0)
    _hmwi0 = head.matrix_world.inverted()

    def in_box(p):
        if not (eye_lo <= p.z <= eye_hi):
            return False
        loc, nor, idx, d = _bvh0.find_nearest(_hmwi0 @ p)
        if loc is None:
            return False
        return (nor.y * FACE_SIGN) > 0.5

    in_face = sum(1 for p in tips if in_box(p))
    rep["tips_in_face_box"] = in_face
    rep["tips_in_face_pct"] = round(100.0 * in_face / max(1, len(tips)), 2)

    # COUNT EVERY POINT, NOT JUST TIPS -- the tip count is the wrong metric
    # and it lied for five iterations. It read 0.18%, then 0.07%, then 0.02%,
    # then 0.00% while the render showed an unchanged dark mass over both eye
    # sockets, and a hide-the-hair control proved that mass IS the groom
    # (the bare head carries only thin eyelash geometry there).
    #
    # Strands cross the eyes with their MIDDLES and end elsewhere, so a tip
    # census cannot see them. This counts strands with ANY point in the box,
    # which is what "hair over the eyes" means to someone looking at it.
    crossing = 0
    for i, s in enumerate(starts):
        for k in range(sizes[i]):
            if in_box(mw @ mathutils.Vector(data.points[s + k].position)):
                crossing += 1
                break
    rep["strands_crossing_face_box"] = crossing
    rep["strands_crossing_pct"] = round(100.0 * crossing / max(1, len(starts)), 2)

    # ---- SHELL THICKNESS: volume, as a number ----------------------------
    # "It looks slicked flat" and "it has body" are the same statement about
    # ONE measurable thing: how far the hair sits off the skull. Measuring it
    # means a volume change can be confirmed without arguing about a render,
    # and it will catch the case where a parameter moved and the mass did not.
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(head, dg)
    hmwi = head.matrix_world.inverted()
    dists_mid, dists_tip = [], []
    for i, s in enumerate(starts):
        n = sizes[i]
        for k, bucket in ((n // 2, dists_mid), (n - 1, dists_tip)):
            lp = hmwi @ (mw @ mathutils.Vector(data.points[s + k].position))
            loc, nor, idx, d = bvh.find_nearest(lp)
            if loc is not None:
                bucket.append(d)

    def stats(v):
        if not v:
            return None
        v = sorted(v)
        return {"mean_cm": round(sum(v) / len(v), 3),
                "p50_cm": round(v[len(v) // 2], 3),
                "p90_cm": round(v[int(0.9 * (len(v) - 1))], 3)}
    rep["shell_thickness_mid"] = stats(dists_mid)
    rep["shell_thickness_tip"] = stats(dists_tip)

    # ---- SCALP EXPOSURE: the metric that would have caught the parting ----
    # Shell thickness rose 23% at the tips and the UE render was unchanged,
    # because the mass had gone SIDEWAYS into two wings and a back shelf
    # rather than up into body -- and a front view showed a bald stripe down
    # the middle of the crown that no number on this report could see.
    #
    # Thickness says how far the layer sits off the skull. It says nothing
    # about whether the layer is THERE. So: sample the scalp itself and ask,
    # for each sample, how far away the nearest hair point is. Skin with no
    # hair near it is exposed scalp, which is what "parting" and "thin crown"
    # both mean.
    from mathutils.kdtree import KDTree
    all_pts = [mw @ mathutils.Vector(pt.position) for pt in data.points]
    kd = KDTree(len(all_pts))
    for i, p_ in enumerate(all_pts):
        kd.insert(p_, i)
    kd.balance()

    # WHERE IS THE SCALP? THE ROOTS SAY SO, AND NOTHING ELSE DOES.
    #
    # The first definition was "head vertices above the nape whose normal is
    # not strongly face-facing", and it read 28.4 / 28.7 / 28.3 / 29.4% across
    # a SIX-FOLD change in back_bias -- a number that will not move is a
    # number that is not measuring the thing being changed. It was counting
    # cheeks, temples, ears and the back of the neck, whose normals are
    # lateral rather than face-facing, so most of the sample was skin that is
    # SUPPOSED to be bare and the styling could not shift it.
    #
    # The hairy region is the region the author grew roots in. Defining it any
    # other way duplicates the author's swept hairline in a second place, and
    # two lists that must agree are one list badly stored. So: a head vertex
    # is scalp when a ROOT sits within 1.5 cm of it.
    #
    # This is not circular. Roots are not coverage -- the whole failure mode
    # is roots present on the crown while the strands leave and pile at the
    # back. The question asked is: over the skin where hair GROWS, is there
    # any hair NEAR it?
    kd_root = KDTree(len(roots))
    for i, p_ in enumerate(roots):
        kd_root.insert(p_, i)
    kd_root.balance()

    scalp, near = [], []
    for v in head.data.vertices:
        wp = hmw @ v.co
        if kd_root.find(wp)[2] > 1.5:       # not in the hairy region at all
            continue
        scalp.append(wp)
        near.append(kd.find(wp)[2])
    if scalp:
        near_s = sorted(near)
        exposed = sum(1 for d_ in near if d_ > 0.80)
        rep["scalp_samples"] = len(scalp)
        rep["scalp_exposed_pct"] = round(100.0 * exposed / len(scalp), 2)
        rep["scalp_nearest_cm"] = {
            "p50": round(near_s[len(near_s) // 2], 3),
            "p90": round(near_s[int(0.9 * (len(near_s) - 1))], 3)}
        # WHERE the exposure is, not just how much. A parting down the crown
        # and a thin nape are the same aggregate number and different defects,
        # and the aggregate cannot tell them apart -- which is how a midline
        # stripe survived a change that improved the total.
        mid_x = 0.5 * (min(p.x for p in hp) + max(p.x for p in hp))
        zones = {"midline_|x|<3cm": [0, 0], "lateral": [0, 0]}
        for wp, d_ in zip(scalp, near):
            key = ("midline_|x|<3cm" if abs(wp.x - mid_x) < 3.0 else "lateral")
            zones[key][0] += 1
            if d_ > 0.80:
                zones[key][1] += 1
        rep["scalp_exposed_by_zone"] = {
            k: {"n": v[0], "exposed_pct": round(100.0 * v[1] / max(1, v[0]), 2)}
            for k, v in zones.items()}
    else:
        # NN13: zero scalp samples (no head vertex within 1.5 cm of a root --
        # roots detached, wrong units, or a transform mismatch) is "could not
        # measure", not 0% exposed. Record it so a downstream gate on
        # scalp_exposed_pct sees a refusal instead of a silently missing key.
        rep["scalp_samples"] = 0
        rep["scalp_error"] = ("zero scalp samples: no head vertex within 1.5 cm "
                              "of a root")

    # FLARE: how far the hair stands out SIDEWAYS past the head, at ear
    # height. This is the other half of "it reads as a bowl" -- a dome
    # outline, hair flaring past the ears instead of falling down the sides.
    # Geometric rather than render-side, because four render-side statistics
    # have now failed to see their own subject today.
    half_x_head = 0.5 * (max(q.x for q in hp) - min(q.x for q in hp))
    mid_x_head = 0.5 * (min(q.x for q in hp) + max(q.x for q in hp))
    ear_lo, ear_hi = z_lo + 0.62 * height, z_lo + 0.78 * height
    band = [abs(q.x - mid_x_head) for q in all_pts if ear_lo <= q.z <= ear_hi]
    if band:
        band.sort()
        rep["flare_p95_ratio"] = round(
            band[int(0.95 * (len(band) - 1))] / max(1e-6, half_x_head), 3)
        rep["flare_max_ratio"] = round(band[-1] / max(1e-6, half_x_head), 3)

    rep["face_box"] = {"eye_z": [round(eye_lo, 2), round(eye_hi, 2)],
                       "face_sign": FACE_SIGN}

    # ---- render, front and side ------------------------------------------
    # HIDE-THE-HAIR CONTROL. Pass "nohair" as the second argument to render
    # the head alone through the SAME camera and framing.
    #
    # This exists because a dark mass sat over the eye sockets through five
    # styling iterations, surviving a raised hairline, an outward bias, a
    # raised temple line and a sweep-back that took tips_in_face_box to ZERO.
    # A feature that does not respond to any change in the thing you are
    # changing is probably not made of that thing -- and the MetaHuman face
    # mesh carries its own eyelash geometry.
    no_hair = len(tail) > 1 and tail[1].lower() == "nohair"
    for ob in bpy.data.objects:
        ob.hide_render = ob.type not in ("MESH", "CURVES")
    head.hide_render = False
    hair.hide_render = bool(no_hair)
    rep["hair_hidden"] = bool(no_hair)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    try:
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "OBJECT"
        head.color = (0.55, 0.55, 0.58, 1.0)
        hair.color = (0.05, 0.04, 0.03, 1.0)   # dark, so coverage reads
    except Exception:
        pass

    xs = [p.x for p in hp]
    centre = mathutils.Vector((0.5 * (min(xs) + max(xs)),
                               sum(p.y for p in hp) / len(hp),
                               0.5 * (z_lo + z_hi)))
    span = max(max(xs) - min(xs), height)
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span * 1.3
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    d = span * 3.0
    views = {"front": mathutils.Vector((0, FACE_SIGN * d, 0)),
             "side": mathutils.Vector((d, 0, 0)),
             "back": mathutils.Vector((0, -FACE_SIGN * d, 0))}
    rep["views"] = {}
    rep["view_render_errors"] = []
    shots = {}
    for label, off in views.items():
        cam.location = centre + off
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(out_dir, "preview_%s.png" % label)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        rep["views"][label] = path
        # The render op's success is not self-evident from a recorded path;
        # verify the PNG actually landed so a silently failed write is not
        # reported as a rendered view (on a nohair run these are not re-read).
        if not (os.path.isfile(path) and os.path.getsize(path) > 0):
            rep["view_render_errors"].append(label)
        shots[label] = (path, cam.location.copy(), cam.rotation_euler.copy())

    # ---- SILHOUETTE GAIN: what "it isn't slicked flat" actually means ------
    # The shell metric reported 2.0 cm of standoff at mid-strand and 2.9 cm at
    # the tips on a groom the render shows as a thin arc, so the two disagree.
    # They are asking different questions. Standoff is a distance from the
    # skin; nobody looks at a head and sees a distance from the skin. What a
    # person sees is whether the OUTLINE grew -- a haircut with body makes the
    # head bigger, and one that is slicked down does not.
    #
    # So render the head alone through the SAME camera and subtract. The
    # changed pixels are the hair's contribution to the picture, and the
    # topmost changed row minus the topmost head row is how much taller the
    # hair made him, in centimetres via the orthographic scale.
    #
    # This is the project's difference-render gate, run in Blender at four
    # seconds a shot instead of four minutes a shot.
    if not no_hair:
        try:
            import numpy as np
            cm_per_px = cam_data.ortho_scale / float(scene.render.resolution_x)
            hair.hide_render = True
            rep["silhouette"] = {}
            for label, (path, loc, rot) in shots.items():
                cam.location, cam.rotation_euler = loc, rot
                bare = os.path.join(out_dir, "preview_%s_nohair.png" % label)
                scene.render.filepath = bare
                bpy.ops.render.render(write_still=True)

                def _load(pth):
                    im = bpy.data.images.load(pth, check_existing=False)
                    a = np.array(im.pixels[:], dtype=np.float32)
                    w, h = im.size
                    bpy.data.images.remove(im)
                    return a.reshape(h, w, 4)[::-1, :, :3]

                a, b = _load(path), _load(bare)
                diff = np.abs(a - b).max(axis=2)
                changed = diff > 0.02
                n = int(changed.sum())
                # topmost row containing the subject, with and without hair
                bg = b[0, 0]
                subj = (np.abs(b - bg).max(axis=2) > 0.02)
                rows_h = np.nonzero(changed.any(axis=1))[0]
                rows_b = np.nonzero(subj.any(axis=1))[0]
                # None, not 0.0, when there is no changed row or no subject row:
                # "could not measure" must not read as a measured 0 cm gain.
                gain = None
                if len(rows_h) and len(rows_b):
                    gain = round(float(rows_b[0] - rows_h[0]) * cm_per_px, 2)
                rep["silhouette"][label] = {
                    "hair_px": n,
                    "hair_pct_of_frame": round(100.0 * n / changed.size, 2),
                    "height_gain_cm": gain}

                # HAIR DRAWN OVER THE FACE, COUNTED IN PIXELS.
                # Two geometric versions of this have now failed. A tip census
                # missed strands that cross with their middles; a nearest-
                # surface-normal test misses strands hanging in the AIR beside
                # the temple, because the nearest skin there is cheek and a
                # cheek normal points sideways. The second read 3.08% through
                # a 23% cut to side length and a doubling of the sweep -- an
                # input that moves nothing is not the input the number is
                # made of.
                #
                # In the front view this needs no normals at all: hair pixels
                # that land INSIDE the bare head's own silhouette, in the rows
                # the eyes occupy, are hair drawn over the face. That is the
                # thing a person is looking at when they say it.
                # THE BOWL, AS A NUMBER.
                # "It reads as a helmet" and "it reads as layered" are the
                # same statement about ONE measurable thing: where the hair
                # ENDS. A bowl cut ends at the same height everywhere, so the
                # lower edge of the hair silhouette is a flat line; a layered
                # cut ends at many heights and the edge is ragged.
                #
                # So take the lowest hair pixel in every column and report the
                # spread of those heights in centimetres. Low spread IS the
                # bowl. This needs no judgement about the render and it will
                # catch a change that moves the mass without breaking the edge.
                # AND STATE THE DENOMINATOR. Over the WHOLE silhouette this
                # read 2.33 / 3.34 / 3.38 cm across three versions whose
                # renders differ obviously in exactly this respect -- because
                # the sides drop past the ears and swamp the flat bit. The
                # bowl edge is the FRINGE, so the statistic is conditioned on
                # the central columns where the fringe is.
                if label in ("front", "side"):
                    # Default to None so "too few columns/fringe samples to
                    # measure" is distinguishable from a computed value rather
                    # than a silently absent key (this is a silhouette GATE
                    # sub-metric).
                    rep["silhouette"][label]["fringe_edge_spread_cm"] = None
                    rep["silhouette"][label]["fringe_edge_range_cm"] = None
                    cols = np.nonzero(changed.any(axis=0))[0]
                    if len(cols) > 20:
                        c0, c1 = cols[0], cols[-1]
                        span = c1 - c0
                        lo_c = int(c0 + 0.30 * span)
                        hi_c = int(c0 + 0.70 * span)
                        lows = []
                        for c in range(lo_c, hi_c + 1):
                            rr = np.nonzero(changed[:, c])[0]
                            if len(rr):
                                lows.append(rr[-1])
                        if len(lows) > 8:
                            lows = np.array(lows, dtype=np.float32)
                            rep["silhouette"][label]["fringe_edge_spread_cm"] = \
                                round(float(lows.std()) * cm_per_px, 3)
                            rep["silhouette"][label]["fringe_edge_range_cm"] = \
                                round(float(lows.max() - lows.min()) * cm_per_px, 3)

                if label == "front":
                    z_top = centre.z + 0.5 * cam_data.ortho_scale
                    r0 = int((z_top - eye_hi) / cm_per_px)
                    r1 = int((z_top - eye_lo) / cm_per_px)
                    r0, r1 = max(0, r0), min(changed.shape[0], r1)
                    band_h = changed[r0:r1]
                    band_s = subj[r0:r1]
                    over = int((band_h & band_s).sum())
                    rep["silhouette"][label]["eye_band_rows"] = [r0, r1]
                    rep["silhouette"][label]["hair_over_face_px"] = over
            hair.hide_render = False
        except Exception as exc:                        # never fail the run
            rep["silhouette_error"] = repr(exc)
    print("__PREVIEW__" + json.dumps(rep))


main()
