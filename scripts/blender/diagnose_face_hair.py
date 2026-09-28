"""diagnose_face_hair.py — WHICH ROOTS put hair over the eyes?

    blender.exe --background <authored.blend> --python this.py -- [out.json]

WHY THIS EXISTS. Hair hangs at the brow and temples through every fix aimed at
it. `front_sweep_gain` 1.2 -> 2.4 moved the count 17,463 -> 17,362. Cutting
`len_side_cm` by 23% moved it 17,378 -> 17,378 -- not approximately, exactly.
Two levers that should have moved it did nothing, which means the strands doing
it are not the strands those levers reach, and I do not know which strands they
ARE. Three fixes have now been aimed at a population I never identified.

So this identifies it. It finds every strand with a point over the face and
reports the DISTRIBUTION OF THEIR ROOTS -- height, facing, lateralness, which
length branch they took, and how far along the strand the offending point sits.
A fix follows from that; it cannot follow from the count alone.

OVER THE FACE IS DEFINED AS THE EYE SEES IT, not by a normal test.
A point is over the face when, from the camera, it lands on him: the ray from
the point AWAY from the camera hits the head, and the point is inside the eye
band. That catches a strand hanging in the AIR beside the temple, which the
nearest-surface-normal test could not -- the nearest skin there is cheek and a
cheek normal points sideways, so the previous metric scored those as fine while
the render showed a dark mass over both sockets.
"""

import json
import os
import sys

import bpy
import mathutils
from mathutils.bvhtree import BVHTree

FACE_SIGN = -1.0        # settled by render: _verify/20260821_blender/facing/


def pct(n, d):
    return round(100.0 * n / max(1, d), 2)


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    out_path = tail[0] if tail else None
    rep = {"blend": bpy.data.filepath}

    curves = [o for o in bpy.data.objects if o.type == "CURVES"
              and len(o.data.curves) > 0]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not curves or not meshes:
        rep["error"] = "need a head and authored hair"
        print("__DIAG__" + json.dumps(rep))
        return
    hair = max(curves, key=lambda o: len(o.data.curves))
    head = hair.data.surface or max(meshes, key=lambda o: len(o.data.vertices))
    rep["hair"], rep["head"] = hair.name, head.name

    # The chosen head must have vertices, or min()/max() below raise before any
    # __DIAG__ line is emitted (the consumer would get silence, not a report).
    if not head.data.vertices:
        rep["error"] = "chosen head mesh %r has no vertices" % head.name
        print("__DIAG__" + json.dumps(rep))
        return

    hmw = head.matrix_world
    hmwi = hmw.inverted()
    hp = [hmw @ v.co for v in head.data.vertices]
    z_lo = min(p.z for p in hp)
    z_hi = max(p.z for p in hp)
    # Floor the span: a planar-in-Z mesh gives height 0 and every `/ height`
    # below would ZeroDivisionError.
    height = (z_hi - z_lo) or 1e-6
    mid_x = 0.5 * (min(p.x for p in hp) + max(p.x for p in hp))
    half_x = 0.5 * (max(p.x for p in hp) - min(p.x for p in hp))
    eye_lo, eye_hi = z_lo + 0.62 * height, z_lo + 0.80 * height
    rep["eye_band_z"] = [round(eye_lo, 2), round(eye_hi, 2)]

    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(head, dg)

    # AWAY FROM THE CAMERA, AND THE SIGN IS THE WHOLE TEST.
    # The face is at FACE_SIGN * Y, so the camera sits on that side and looks
    # back along -FACE_SIGN. "Away from the camera", which is the direction
    # that must hit the head for a point to be drawn OVER him, is therefore
    # -FACE_SIGN * Y.
    #
    # Written the other way round first, and the DISTRIBUTION is what caught
    # it, not the count: 87% of the offending strands came back rooted at the
    # NAPE, facing backwards, low on the skull. Nape hair cannot be over the
    # eyes. A ray pointing at the camera hits the skull from behind for every
    # strand behind the head, so the test scored the back of the head as the
    # face. The count alone (25.74%) looked plausible and was meaningless.
    into = mathutils.Vector((0.0, -FACE_SIGN, 0.0))
    into_local = (hmwi.to_3x3() @ into).normalized()

    def over_face(p_world):
        if not (eye_lo <= p_world.z <= eye_hi):
            return False
        lp = hmwi @ p_world
        # OUTSIDE THE HEAD FIRST. A point BURIED IN THE SKULL also has head
        # geometry between it and the far side, so the ray test alone scores
        # it as drawn over the face. Measured: 62.3% of the strands this
        # flagged had their offending point at the BACK of the head, which is
        # a point inside the volume, not hair on the brow. A buried strand is
        # a different defect and the drape is what owns it.
        loc, nor, idx, d = bvh.find_nearest(lp)
        if loc is None or (lp - loc).dot(nor) <= 0.0:
            return False
        hit, hnor, hidx, hdist = bvh.ray_cast(lp, into_local, 100.0)
        return hit is not None

    # POSITIVE AND NEGATIVE CONTROL, RUN BEFORE THE CENSUS IS TRUSTED.
    # This test has now been written with the sign both ways and BOTH produced
    # a plausible-looking count over an impossible distribution -- 87% and then
    # 100% of the offending strands rooted at the nape, which cannot be hair
    # over the eyes. Reasoning about the sign a third time is not a method.
    #
    # So: take a point that IS unambiguously over the face (just in front of
    # the face surface, in the eye band) and one that is unambiguously not
    # (just behind the back of the skull, same height). If the test does not
    # separate them, nothing below it means anything and the run refuses.
    z_mid = 0.5 * (eye_lo + eye_hi)
    ys = [p.y for p in hp if eye_lo <= p.z <= eye_hi and abs(p.x - mid_x) < 2.0]
    y_face = (min(ys) if FACE_SIGN < 0 else max(ys)) if ys else 0.0
    y_back = (max(ys) if FACE_SIGN < 0 else min(ys)) if ys else 0.0
    probe_front = mathutils.Vector((mid_x, y_face + FACE_SIGN * 3.0, z_mid))
    probe_back = mathutils.Vector((mid_x, y_back - FACE_SIGN * 3.0, z_mid))
    ctrl = {"in_front_of_face": bool(over_face(probe_front)),
            "behind_the_skull": bool(over_face(probe_back)),
            "y_face": round(y_face, 2), "y_back": round(y_back, 2)}
    rep["control"] = ctrl
    y_face_g, y_back_g = y_face, y_back
    if not (ctrl["in_front_of_face"] and not ctrl["behind_the_skull"]):
        rep["error"] = ("REFUSED: the over-face test does not discriminate. "
                        "A point 3 cm in front of the face must score and one "
                        "3 cm behind the skull must not.")
        print("__DIAG__" + json.dumps(rep))
        return

    mw = hair.matrix_world
    data = hair.data
    starts = [c.first_point_index for c in data.curves]
    sizes = [c.points_length for c in data.curves]

    # Root normals: nearest head vertex normal is close enough for a census and
    # needs no re-derivation of the author's sampling.
    from mathutils.kdtree import KDTree
    kd = KDTree(len(head.data.vertices))
    for i, v in enumerate(head.data.vertices):
        kd.insert(hmw @ v.co, i)
    kd.balance()
    nrm3 = hmw.to_3x3()

    hairline_z = z_lo + 0.82 * height          # local constant, NOT recipe-sourced
    top_frac = 0.86                            # the len_top_cm branch

    offenders = []
    for i, s in enumerate(starts):
        n = sizes[i]
        first_t = None
        first_p = None
        for k in range(n):
            p = mw @ mathutils.Vector(data.points[s + k].position)
            if over_face(p):
                # A single-point strand has no along-length position; guard the
                # n==1 case rather than dividing by zero.
                first_t = k / float(n - 1) if n > 1 else 0.0
                first_p = p
                break
        if first_t is None:
            continue
        root = mw @ mathutils.Vector(data.points[s].position)
        _, vi, _ = kd.find(root)
        nv = (nrm3 @ head.data.vertices[vi].normal)
        if nv.length > 1e-9:
            nv.normalize()
        facing = nv.y * FACE_SIGN
        t_h = (root.z - z_lo) / height
        if facing > 0.2 and root.z > hairline_z:
            branch = "fringe"
        elif t_h > top_frac:
            branch = "top"
        elif root.z < hairline_z:
            branch = "nape"
        else:
            branch = "side"
        offenders.append({
            "t_h": t_h, "facing": facing, "absnx": abs(nv.x),
            "branch": branch, "first_t": first_t,
            "lateral": abs(root.x - mid_x) / max(1e-6, half_x),
            # WHERE THE OFFENDING POINT IS, not only where its root is.
            # The root distribution alone said "nape", which is impossible for
            # hair over the eyes, so the point's own position is the thing to
            # look at: y as a fraction from the face plane (0) to the back of
            # the skull (1), and lateral distance from the midline.
            "pt_y_frac": (first_p.y - y_face_g) / max(1e-6, (y_back_g - y_face_g)),
            "pt_lateral": abs(first_p.x - mid_x) / max(1e-6, half_x),
            "pt_z_frac": (first_p.z - z_lo) / height,
            # THE ROOT'S OWN POSITION, not an inference from a normal.
            # `facing` above comes from the nearest head VERTEX normal, and
            # this mesh carries eyelids, sockets and interior surfaces whose
            # normals point backwards a centimetre from the brow -- so a brow
            # root can be labelled "back-facing" and fall into the nape
            # branch. Position cannot be wrong in that way.
            "root_y_frac": (root.y - y_face_g) / max(1e-6, (y_back_g - y_face_g)),
            "root_lat": abs(root.x - mid_x) / max(1e-6, half_x),
            "root_z_frac": t_h,
        })

    # THE HAIRLINE PROFILE, IN GEOMETRY.
    # Three separate mechanisms aimed at the ruled line across the forehead --
    # length layering, a density fade, a lateral wave -- each moved the
    # render-side edge statistic by nothing. That is either three wrong
    # mechanisms or one wrong measurement, and the cheapest way to tell them
    # apart is to measure the hairline where it is DEFINED rather than where
    # it is drawn: bin the front-facing roots by x and take the lowest root in
    # each bin. If the wave is happening, this spreads; if it is not, the
    # render metric was never the problem.
    all_roots = [mw @ mathutils.Vector(data.points[s].position) for s in starts]
    front_roots = [r for r in all_roots
                   if (r.y - y_face_g) / max(1e-6, (y_back_g - y_face_g)) < 0.40]
    if len(front_roots) > 40:
        nb = 12
        lo_x = min(r.x for r in front_roots)
        hi_x = max(r.x for r in front_roots)
        wid = (hi_x - lo_x) / nb or 1e-6
        bins = [[] for _ in range(nb)]
        for r in front_roots:
            j = min(nb - 1, int((r.x - lo_x) / wid))
            bins[j].append(r.z)
        mins = [min(b) for b in bins if len(b) >= 3]
        if len(mins) >= 6:
            m = sum(mins) / len(mins)
            var = sum((v - m) ** 2 for v in mins) / len(mins)
            rep["hairline_profile"] = {
                "bins": len(mins),
                "spread_cm": round(var ** 0.5, 3),
                "range_cm": round(max(mins) - min(mins), 3),
                "front_roots": len(front_roots)}

    rep["strands"] = len(starts)
    rep["over_face_strands"] = len(offenders)
    rep["over_face_pct"] = pct(len(offenders), len(starts))
    if offenders:
        def dist(key, edges, labels):
            counts = [0] * len(labels)
            for o in offenders:
                v = o[key]
                for j, e in enumerate(edges):
                    if v <= e:
                        counts[j] += 1
                        break
                else:
                    counts[-1] += 1
            return {labels[j]: pct(counts[j], len(offenders))
                    for j in range(len(labels))}

        rep["by_branch"] = {}
        for o in offenders:
            rep["by_branch"][o["branch"]] = rep["by_branch"].get(o["branch"], 0) + 1
        rep["by_branch_pct"] = {k: pct(v, len(offenders))
                                for k, v in rep["by_branch"].items()}
        rep["root_height_pct"] = dist(
            "t_h", [0.80, 0.84, 0.88, 0.92, 1.01],
            ["<=0.80", "0.80-0.84", "0.84-0.88", "0.88-0.92", ">0.92"])
        rep["root_facing_pct"] = dist(
            "facing", [-0.2, 0.2, 0.6, 1.01],
            ["back<=-0.2", "-0.2..0.2", "0.2..0.6", ">0.6"])
        rep["root_lateral_pct"] = dist(
            "lateral", [0.25, 0.50, 0.75, 1.01],
            ["<=0.25", "0.25-0.50", "0.50-0.75", ">0.75"])
        rep["first_crossing_t_pct"] = dist(
            "first_t", [0.25, 0.50, 0.75, 1.01],
            ["<=0.25", "0.25-0.50", "0.50-0.75", ">0.75"])
        rep["point_depth_pct"] = dist(
            "pt_y_frac", [0.0, 0.15, 0.35, 0.60, 99.0],
            ["in_front_of_face", "face_0-0.15", "0.15-0.35",
             "0.35-0.60", "back_>0.60"])
        rep["point_lateral_pct"] = dist(
            "pt_lateral", [0.25, 0.50, 0.75, 1.01],
            ["<=0.25", "0.25-0.50", "0.50-0.75", ">0.75"])
        rep["point_height_pct"] = dist(
            "pt_z_frac", [0.64, 0.68, 0.72, 0.76, 1.01],
            ["<=0.64", "0.64-0.68", "0.68-0.72", "0.72-0.76", ">0.76"])
        rep["ROOT_depth_pct"] = dist(
            "root_y_frac", [0.15, 0.35, 0.60, 99.0],
            ["front_<=0.15", "0.15-0.35", "0.35-0.60", "back_>0.60"])
        rep["ROOT_lateral_pct"] = dist(
            "root_lat", [0.25, 0.50, 0.75, 1.01],
            ["<=0.25", "0.25-0.50", "0.50-0.75", ">0.75"])
        rep["ROOT_height_pct"] = dist(
            "root_z_frac", [0.74, 0.78, 0.82, 0.86, 1.01],
            ["<=0.74", "0.74-0.78", "0.78-0.82", "0.82-0.86", ">0.86"])

    print("__DIAG__" + json.dumps(rep))
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(rep, fh, indent=2)
        # Confirm the file landed rather than trusting the write silently.
        if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            print("wrote %s (%d bytes)" % (out_path, os.path.getsize(out_path)))
        else:
            print("WARNING: %s did not write back" % out_path)


main()
