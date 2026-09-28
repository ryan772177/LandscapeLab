"""make_groom_authoring_blend.py — build a Blender file for authoring a groom
ON OUR OWN CHARACTER'S HEAD.

    blender.exe --background --python this.py -- <head.fbx> <out.blend> <z_min> <z_max>

WHY THIS FILE EXISTS. A groom brought in from someone else's .blend seats
wrongly and no binding rescues it, because that head and ours are not related
by a rigid transform -- same 24,049-vertex topology, height ratio 1.1375,
width ratio 1.3285. The fix is not a better binding; it is to author the hair
on OUR head so the roots are in the target's space from the start.

So this takes the face mesh exported from UE and builds an authoring scene
around it:

    - imports the head and VERIFIES it arrived in the space UE reported,
      refusing rather than proceeding if the importer rescaled or moved it
    - adds an empty hair Curves object whose SURFACE is that head, which is
      what makes authored roots attach to it
    - saves to a NEW .blend

IT STARTS FROM AN EMPTY SCENE, not from any vendor file, and it never writes
to one. `--factory-startup` is deliberately NOT passed even here, so the
add-on set matches the file the author will open interactively.

Exit is reported in the JSON line; a refusal carries the measured numbers.
"""

import json
import os
import sys

import bpy


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 4:
        print("__AUTHOR__" + json.dumps(
            {"ok": False,
             "error": "need: <head.fbx> <out.blend> <z_min> <z_max>"}))
        return
    fbx, out_blend = tail[0], tail[1]
    z_min_expected, z_max_expected = float(tail[2]), float(tail[3])

    rep = {"ok": False, "fbx": fbx, "out": out_blend,
           "expected_z": [z_min_expected, z_max_expected],
           "blender": bpy.app.version_string}

    if not os.path.isfile(fbx):
        rep["error"] = "no fbx at " + fbx
        print("__AUTHOR__" + json.dumps(rep))
        return

    # Empty the default startup scene: Cube, Camera, Light are not wanted in
    # an authoring file and a stray Cube is exactly the kind of thing that
    # ends up in an export selection later.
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    # SCENE UNITS MUST MATCH THE CONVENTION THE EXPORTER ROUND-TRIPS, and
    # this was measured rather than assumed:
    #
    #     demo .blend      scale_length 0.01  CENTIMETERS
    #     default startup  scale_length 1.00  METERS
    #
    # The demo file works in centimetres, which is why its head sits at
    # Z 118..151 rather than 1.18..1.51, and why grooms exported from it
    # arrive in UE at centimetre magnitudes with groom_scale 1.0. Building
    # this file on the default metric-metres startup put our head at
    # Z 1.409..1.784 -- a clean factor of 100 out, which the refusal caught.
    u = bpy.context.scene.unit_settings
    u.system = "METRIC"
    u.scale_length = 0.01
    try:
        u.length_unit = "CENTIMETERS"
    except Exception:
        pass
    rep["scene_units"] = {"system": u.system,
                          "scale_length": round(float(u.scale_length), 6)}

    try:
        bpy.ops.import_scene.fbx(
            filepath=fbx,
            # 1.0, and the value is DERIVED FROM TWO MEASUREMENTS rather
            # than reasoned about:
            #     scale_length 1.00, global_scale 1.0   -> Z    1.409 ..    1.784
            #     scale_length 0.01, global_scale 100   -> Z 14087.8   .. 17843.7
            # so scale_length 0.01 already supplies the factor of 100 and
            # global_scale must not supply it again. My first instinct was
            # that the two compose the other way; the refusal caught both
            # attempts, which is the only reason this line is right.
            global_scale=1.0,
            use_manual_orientation=False,
            automatic_bone_orientation=True)
    except Exception as exc:
        rep["error"] = "import raised: %s: %s" % (type(exc).__name__, exc)
        print("__AUTHOR__" + json.dumps(rep))
        return

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    rep["imported_objects"] = [o.name for o in bpy.data.objects]
    if not meshes:
        rep["error"] = "no mesh object after import"
        print("__AUTHOR__" + json.dumps(rep))
        return
    # REPORT EVERY MESH, not just the one chosen. The first run silently
    # picked one of two objects the FBX contained and reported its 19,284
    # verts as though that were the whole head; which object a max() lands on
    # is not something to discover later from a groom that binds to half a
    # face.
    rep["meshes"] = [{"name": o.name, "verts": len(o.data.vertices)}
                     for o in meshes]
    head = max(meshes, key=lambda o: len(o.data.vertices))
    rep["head_object"] = head.name
    rep["head_verts"] = len(head.data.vertices)

    import mathutils
    pts = [head.matrix_world @ mathutils.Vector(c) for c in head.bound_box]
    zs = [p.z for p in pts]
    xs = [p.x for p in pts]
    z_min, z_max = round(min(zs), 3), round(max(zs), 3)
    rep["blender_z"] = [z_min, z_max]
    rep["blender_width_x"] = round(max(xs) - min(xs), 3)

    # THE REFUSAL. A head that arrives at the wrong scale still looks like a
    # head, and a groom authored on it would carry the error invisibly into
    # every character that ever uses this pipeline.
    tol = 1.0
    if abs(z_min - z_min_expected) > tol or abs(z_max - z_max_expected) > tol:
        rep["error"] = (
            "REFUSE: head arrived at Z %.3f..%.3f against UE's %.3f..%.3f. "
            "The importer moved or rescaled it, and a groom authored here "
            "would be in a foreign space -- which is the exact defect this "
            "file exists to avoid. NOT auto-corrected."
            % (z_min, z_max, z_min_expected, z_max_expected))
        print("__AUTHOR__" + json.dumps(rep))
        return

    # An empty hair Curves object, surfaced to the head. This is what makes
    # authored roots attach to THIS mesh; without it the author is drawing in
    # empty space and the roots have nothing to be relative to.
    try:
        hair = bpy.data.hair_curves.new("AlpineHero_Hair_v1")
        hair_ob = bpy.data.objects.new("AlpineHero_Hair_v1", hair)
        bpy.context.scene.collection.objects.link(hair_ob)
        hair_ob.parent = head
        hair.surface = head
        uv_layer = head.data.uv_layers.active
        if uv_layer is not None:
            hair.surface_uv_map = uv_layer.name
            rep["surface_uv_map"] = uv_layer.name
        else:
            rep["surface_uv_map"] = None
            rep["warning"] = ("the head has NO active UV map, so hair roots "
                              "cannot be expressed in surface UV space -- a "
                              "groom authored here would not survive a bind")
        rep["hair_object"] = hair_ob.name
    except Exception as exc:
        rep["hair_object"] = None
        rep["hair_error"] = "%s: %s" % (type(exc).__name__, exc)

    os.makedirs(os.path.dirname(out_blend) or ".", exist_ok=True)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    except Exception as exc:
        rep["error"] = "save raised: %s: %s" % (type(exc).__name__, exc)
        print("__AUTHOR__" + json.dumps(rep))
        return

    rep["bytes"] = os.path.getsize(out_blend) if os.path.isfile(out_blend) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__AUTHOR__" + json.dumps(rep))


main()
