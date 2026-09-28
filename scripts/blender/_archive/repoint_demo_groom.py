"""repoint_demo_groom.py — append the demo's WORKING hair object and point it
at our head.

    blender.exe --background <authoring.blend> --python this.py -- \
        <demo.blend> <groom_object> <out.abc> [out.blend]

WHY THIS SHAPE OF FIX. Reconstructing a groom's attribute chain from scratch
got as far as strands that import with the right curve count, bind, assign
and draw nothing -- still missing groom_guide_weights, groom_guide_closest,
groom_color, groom_AO, rest_position and surface_normal, all of which the
demo's Geometry Nodes stack produces. Rather than rebuild that stack node by
node, take the one configuration known to survive the exporter and change the
single thing that has to change: WHICH HEAD IT IS ATTACHED TO.

That is what "Attach Hair Curves to Surface" is for. Roots are expressed in
surface UV, so repointing the surface should re-seat them at the same UV
coordinates on a different skull -- which is the whole reason UV attachment
exists, and the reason this is a repoint rather than a transform.

THE DEMO FILE IS READ THROUGH APPEND AND NEVER WRITTEN.

THE CHECK THAT DECIDES IT: after repointing, the groom's bounds must move
onto OUR head's Z range. Every previous attempt produced hair that sat where
it was authored, so "did it move" is the question, and it is asked in numbers
before anything is exported.
"""

import json
import os
import sys

import bpy
import mathutils


def bounds_z(ob, dg=None):
    src = ob.evaluated_get(dg) if dg is not None else ob
    try:
        pts = [ob.matrix_world @ mathutils.Vector(c) for c in src.bound_box]
        zs = [p.z for p in pts]
        return [round(min(zs), 3), round(max(zs), 3)]
    except Exception as exc:
        return "unreadable: %s" % exc


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 3:
        print("__REPOINT__" + json.dumps(
            {"ok": False,
             "error": "need: <demo.blend> <groom_object> <out.abc> [out.blend]"}))
        return
    demo, groom_name, out_abc = tail[0], tail[1], tail[2]
    out_blend = tail[3] if len(tail) > 3 else ""

    rep = {"ok": False, "demo": demo, "groom_object": groom_name,
           "out": out_abc}

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        rep["error"] = "no head mesh in the authoring file"
        print("__REPOINT__" + json.dumps(rep))
        return
    head = max(meshes, key=lambda o: len(o.data.vertices))
    head_uv = head.data.uv_layers.active
    rep["head"] = head.name
    rep["head_verts"] = len(head.data.vertices)
    rep["head_uv"] = head_uv.name if head_uv else None
    rep["head_z"] = bounds_z(head)

    # ---- append the groom object, with everything it drags along ----------
    before_objs = set(o.name for o in bpy.data.objects)
    try:
        with bpy.data.libraries.load(demo, link=False) as (src, dst):
            if groom_name not in src.objects:
                dst.objects = []
                rep["error"] = ("no object %r in the demo. Present: %s"
                                % (groom_name, sorted(src.objects)[:30]))
            else:
                dst.objects = [groom_name]
    except Exception as exc:
        rep["error"] = "append raised: %s: %s" % (type(exc).__name__, exc)
    if rep.get("error"):
        print("__REPOINT__" + json.dumps(rep))
        return

    new_objs = [bpy.data.objects[n] for n in
                (set(o.name for o in bpy.data.objects) - before_objs)]
    for o in new_objs:
        if o.name not in bpy.context.scene.objects:
            bpy.context.scene.collection.objects.link(o)
    rep["appended_objects"] = sorted(o.name for o in new_objs)

    groom = None
    for o in new_objs:
        if o.type == "CURVES":
            groom = o
            break
    if groom is None:
        rep["error"] = "appended nothing of type CURVES"
        print("__REPOINT__" + json.dumps(rep))
        return
    rep["groom"] = groom.name
    rep["groom_curves_authored"] = len(groom.data.curves)
    rep["groom_z_before"] = bounds_z(groom)
    rep["old_surface"] = groom.data.surface.name if groom.data.surface else None
    rep["old_surface_uv"] = groom.data.surface_uv_map or None

    # ---- REPOINT ----------------------------------------------------------
    groom.parent = head
    groom.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    groom.data.surface = head
    if head_uv is not None:
        groom.data.surface_uv_map = head_uv.name

    # Every modifier socket that named the old surface object now names ours.
    # Done by SOCKET TYPE and by what it currently points at, rather than by
    # socket name, because a stack that calls it "Surface" in one group and
    # "Surface Object" in another would otherwise be half-repointed -- and a
    # half-repointed groom is exactly the kind of thing that looks fine and
    # is wrong.
    rewired = []
    old_surfaces = set()
    if rep["old_surface"]:
        old_surfaces.add(rep["old_surface"])
    for o in new_objs:
        if o.type == "MESH":
            old_surfaces.add(o.name)
    for mod in groom.modifiers:
        if mod.type != "NODES" or mod.node_group is None:
            continue
        try:
            items = [i for i in mod.node_group.interface.items_tree
                     if getattr(i, "in_out", "") == "INPUT"
                     and getattr(i, "socket_type", "") == "NodeSocketObject"]
        except Exception:
            continue
        for it in items:
            ident = getattr(it, "identifier", None)
            if ident is None:
                continue
            try:
                cur = mod.properties.inputs[ident].to_dict().get("value")
            except Exception:
                cur = None
            cur_name = getattr(cur, "name", None) if cur is not None else None
            if cur_name is None or cur_name in old_surfaces:
                try:
                    mod.properties.inputs[ident]["value"] = head
                    rewired.append("%s.%s: %s -> %s"
                                   % (mod.name, getattr(it, "name", ident),
                                      cur_name, head.name))
                except Exception as exc:
                    rewired.append("%s.%s FAILED %s" % (mod.name, ident, exc))
    rep["rewired"] = rewired
    rep["modifiers"] = [m.name for m in groom.modifiers]

    # ---- MOVE THE AUTHORED CURVES ONTO OUR SKULL --------------------------
    # Repointing the surface is necessary and NOT sufficient: read back from a
    # fresh load, data.surface, the parent and every Object socket all name
    # our head, and the evaluated groom still sits at its original Z. These
    # modifiers attach and interpolate; they do not reposition roots. The
    # authored curve positions are the position.
    #
    # So map the demo head's bounding box onto ours, per axis, and carry the
    # authored points with it. PER AXIS because the two skulls are not related
    # by a uniform scale -- measured, height ratio 1.1375 against width ratio
    # 1.3285 -- so a single factor would leave the hair too narrow or too tall.
    #
    # This is a COARSE FIT and it is labelled one. It puts the groom on the
    # right head at roughly the right size; it does not make the roots follow
    # our scalp's contour, which is what the shrinkwrap in the stack is then
    # there to do.
    src_head = None
    for o in new_objs:
        if o.type == "MESH" and len(o.data.vertices) > 5000:
            src_head = o
            break
    rep["source_head"] = src_head.name if src_head else None
    if src_head is not None:
        def bbox(ob):
            pts = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
            return (mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                    mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
        s_lo, s_hi = bbox(src_head)
        d_lo, d_hi = bbox(head)
        scale = mathutils.Vector((
            (d_hi.x - d_lo.x) / max(1e-6, s_hi.x - s_lo.x),
            (d_hi.y - d_lo.y) / max(1e-6, s_hi.y - s_lo.y),
            (d_hi.z - d_lo.z) / max(1e-6, s_hi.z - s_lo.z)))
        rep["fit_scale"] = [round(scale.x, 4), round(scale.y, 4), round(scale.z, 4)]
        rep["src_head_bbox_z"] = [round(s_lo.z, 3), round(s_hi.z, 3)]

        mw = groom.matrix_world
        mwi = mw.inverted()
        pts = groom.data.points
        n = len(pts)
        for i in range(n):
            p = mw @ mathutils.Vector(pts[i].position)
            q = mathutils.Vector((
                d_lo.x + (p.x - s_lo.x) * scale.x,
                d_lo.y + (p.y - s_lo.y) * scale.y,
                d_lo.z + (p.z - s_lo.z) * scale.z))
            lq = mwi @ q
            pts[i].position = (lq.x, lq.y, lq.z)
        rep["points_moved"] = n
        rep["groom_z_fitted"] = bounds_z(groom)

    # ---- THE CHECK: did it move onto our head? ---------------------------
    dg = bpy.context.evaluated_depsgraph_get()
    try:
        ev = groom.evaluated_get(dg)
        rep["groom_curves_evaluated"] = len(ev.data.curves)
        rep["evaluated_attrs"] = [a.name for a in ev.data.attributes]
        pts = [groom.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
        zs = [p.z for p in pts]
        rep["groom_z_after"] = [round(min(zs), 3), round(max(zs), 3)]
    except Exception as exc:
        rep["evaluated_error"] = str(exc)

    hz = rep.get("head_z")
    gz = rep.get("groom_z_after")
    if isinstance(hz, list) and isinstance(gz, list):
        # The groom should overlap the head's upper half. Being anywhere near
        # its ORIGINAL Z means the repoint did not take.
        overlap = not (gz[1] < hz[0] or gz[0] > hz[1])
        rep["moved_onto_head"] = bool(overlap and gz[1] > hz[0] + 0.4 * (hz[1] - hz[0]))
        rep["verdict"] = ("groom Z %s vs head Z %s -- %s"
                          % (gz, hz,
                             "on the head" if rep["moved_onto_head"]
                             else "NOT on the head; the repoint did not take"))

    if out_blend:
        try:
            os.makedirs(os.path.dirname(out_blend) or ".", exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            rep["saved_blend"] = out_blend
        except Exception as exc:
            rep["save_error"] = str(exc)

    # ---- export -----------------------------------------------------------
    for o in bpy.context.selected_objects:
        o.select_set(False)
    groom.select_set(True)
    bpy.context.view_layer.objects.active = groom
    os.makedirs(os.path.dirname(out_abc) or ".", exist_ok=True)
    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_abc, check_existing=False, groom_scale=1.0,
            groom_width_scale=True, groom_radius_to_diameter=True,
            groom_animation=False, node_execution=False)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__REPOINT__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__REPOINT__" + json.dumps(rep))


main()
