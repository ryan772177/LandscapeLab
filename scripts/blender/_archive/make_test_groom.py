"""make_test_groom.py — put a MECHANICAL test groom on the authoring head and
export it, to prove the space fix round-trips.

    blender.exe --background <authoring.blend> --python this.py -- <out.abc> [n_curves]

THIS IS NOT HAIR. It is a regular grid of short straight strands rooted on
the scalp and pointing along the surface normal. Nobody should look at it and
judge a hairstyle; the only question it answers is whether strands authored
on OUR head arrive in UE ON THAT HEAD.

That question is worth a dedicated artefact because every previous custom
groom failed on exactly this and looked plausible while failing. A test groom
whose correct result is obvious -- an even bristle over the scalp -- cannot be
mistaken for a success when it lands on the collarbone.

IT DOES NOT SAVE THE .BLEND. The authoring file stays as built.
"""

import json
import os
import sys

import bpy
import mathutils


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if not tail:
        print("__TESTGROOM__" + json.dumps(
            {"ok": False, "error": "need: <out.abc> [n_curves]"}))
        return
    out_abc = tail[0]
    want = int(tail[1]) if len(tail) > 1 else 2000

    rep = {"ok": False, "out": out_abc, "blend": bpy.data.filepath}

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        rep["error"] = "no mesh in the authoring file"
        print("__TESTGROOM__" + json.dumps(rep))
        return
    head = max(meshes, key=lambda o: len(o.data.vertices))
    rep["head"] = head.name

    # ROOTS ON THE UPPER SKULL ONLY. Rooting over the whole face mesh would
    # put "hair" on the nose and make a wrong result look right-ish, which
    # defeats the purpose of a test whose correct answer is obvious.
    verts = head.data.vertices
    mw = head.matrix_world
    world = [mw @ v.co for v in verts]
    zs = [p.z for p in world]
    z_lo, z_hi = min(zs), max(zs)
    cut = z_lo + 0.72 * (z_hi - z_lo)
    idx = [i for i, p in enumerate(world) if p.z >= cut]
    rep["scalp_band_z"] = [round(cut, 3), round(z_hi, 3)]
    rep["scalp_verts"] = len(idx)
    if not idx:
        rep["error"] = "no vertices above the scalp cut"
        print("__TESTGROOM__" + json.dumps(rep))
        return
    step = max(1, len(idx) // want)
    idx = idx[::step][:want]

    POINTS = 8
    LENGTH = 6.0        # centimetres, in a centimetre scene
    hair = bpy.data.hair_curves.new("TestGroom")
    hair_ob = bpy.data.objects.new("TestGroom", hair)
    bpy.context.scene.collection.objects.link(hair_ob)
    hair_ob.parent = head
    hair.surface = head
    uv = head.data.uv_layers.active
    if uv is not None:
        hair.surface_uv_map = uv.name
    rep["surface_uv_map"] = uv.name if uv else None

    hair.add_curves([POINTS] * len(idx))
    pts = hair.points
    nrm = mathutils.Matrix(mw).to_3x3().inverted().transposed()
    w = 0
    for vi in idx:
        root = world[vi]
        n = (nrm @ verts[vi].normal).normalized()
        for k in range(POINTS):
            t = float(k) / (POINTS - 1)
            p = root + n * (LENGTH * t)
            # Curves points are in OBJECT space and the hair object is
            # parented to the head, so undo the head's transform.
            lp = mw.inverted() @ p
            pts[w].position = (lp.x, lp.y, lp.z)
            w += 1
    # STRAND RADIUS. Curves created through the API carry no radius, and the
    # exporter's groom_width_scale/radius_to_diameter read exactly that
    # attribute -- so the first test groom exported at zero width, imported
    # with the right curve count, bound cleanly and rendered NOTHING. The
    # gate called it ABSENT at 2.1x the floor, which is the signature of a
    # groom that is present and drawing no pixels.
    RADIUS = 0.03           # cm, in a centimetre scene: a plausible strand
    try:
        for i in range(w):
            pts[i].radius = RADIUS
        rep["radius"] = RADIUS
    except Exception as exc:
        # Fall back to the generic attribute API rather than assuming the
        # per-point property exists under that name in this Blender.
        try:
            attr = hair.attributes.get("radius")
            if attr is None:
                attr = hair.attributes.new("radius", "FLOAT", "POINT")
            for i in range(w):
                attr.data[i].value = RADIUS
            rep["radius"] = RADIUS
            rep["radius_via"] = "attributes API"
        except Exception as exc2:
            rep["radius"] = None
            rep["radius_error"] = "%s / %s" % (exc, exc2)

    rep["curves"] = len(idx)
    rep["points"] = w

    dg = bpy.context.evaluated_depsgraph_get()
    try:
        ev = hair_ob.evaluated_get(dg)
        rep["curves_evaluated"] = len(ev.data.curves)
    except Exception as exc:
        rep["curves_evaluated"] = "unreadable: %s" % exc

    b = [hair_ob.matrix_world @ mathutils.Vector(c) for c in hair_ob.bound_box]
    bz = [p.z for p in b]
    rep["groom_z"] = [round(min(bz), 3), round(max(bz), 3)]

    # Export WITHOUT a node group: select the object ourselves and let the
    # exporter read its GroomProperty defaults. node_execution=True would
    # require an authored export node group, which this file has none of.
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
        print("__TESTGROOM__" + json.dumps(rep))
        return

    if not os.path.isfile(out_abc):
        rep["error"] = "operator returned but no file at " + out_abc
        print("__TESTGROOM__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc)
    rep["ok"] = rep["bytes"] > 0
    print("__TESTGROOM__" + json.dumps(rep))


main()
