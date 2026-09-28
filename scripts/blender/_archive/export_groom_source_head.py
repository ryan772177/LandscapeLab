"""export_groom_source_head.py — export the mesh a groom was AUTHORED on.

    blender.exe --background <file.blend> --python this.py -- <out.fbx> <object>

WHY THIS EXISTS. A groom binding transfers hair from the mesh it was authored
on to the mesh it must sit on, and it needs BOTH. Everything about the custom
groom worked except seating, and the measurement says why:

    UE hero face   Z 140.88 .. 178.44   height 37.56
    Blender head   Z 118.16 .. 151.18   height 33.02
    Blender groom  Z 131.06 .. 154.74

The demo file's head carries the same 24,049-vertex MetaHuman topology as our
archetype but sits lower and is 12% shorter -- it is the demo author's own
character, not the archetype. So the groom's roots are in THAT head's space,
and binding it to our face with no source is asking for an identity transfer
between two different heads. The rendered result was hair on the collarbone,
which is what a ~24 cm downward error looks like.

Exporting this head gives the binding its missing half. It is not a fix
applied to the groom; it is the input the binding always wanted.

IT NEVER SAVES THE .BLEND. The source file is a vendor original.
"""

import json
import os
import sys

import bpy


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 2:
        print("__HEAD__" + json.dumps(
            {"ok": False, "error": "need: <out.fbx> <object_name>"}))
        return
    out_path, obj_name = tail[0], tail[1]

    rep = {"ok": False, "out": out_path, "object": obj_name,
           "blend": bpy.data.filepath}

    ob = bpy.data.objects.get(obj_name)
    if ob is None:
        rep["error"] = ("no object named %r. Present: %s"
                        % (obj_name, sorted(o.name for o in bpy.data.objects)))
        print("__HEAD__" + json.dumps(rep))
        return

    # Record what is being exported, so the UE side can check it arrived
    # intact rather than trusting the exporter.
    try:
        rep["verts"] = len(ob.data.vertices)
        import mathutils
        pts = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
        zs = [p.z for p in pts]
        rep["z_range"] = [round(min(zs), 4), round(max(zs), 4)]
    except Exception as exc:
        rep["measure_error"] = str(exc)

    # Select ONLY this mesh and its armature. The armature comes along because
    # a groom binding wants a SKELETAL mesh on the UE side, and an FBX mesh
    # with no skin arrives as a static mesh.
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    arm = None
    for m in ob.modifiers:
        if m.type == "ARMATURE" and m.object is not None:
            arm = m.object
            break
    if arm is None and ob.parent is not None and ob.parent.type == "ARMATURE":
        arm = ob.parent
    if arm is not None:
        arm.select_set(True)
        rep["armature"] = arm.name
    else:
        rep["armature"] = None

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    try:
        bpy.ops.export_scene.fbx(
            filepath=out_path,
            use_selection=True,
            object_types={"MESH", "ARMATURE"},
            add_leaf_bones=False,
            bake_anim=False,
            # No unit rescaling: the whole point is to preserve the space the
            # groom's roots are expressed in. A silently rescaled source mesh
            # would make the binding correct about the wrong geometry.
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_NONE",
            use_mesh_modifiers=False)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__HEAD__" + json.dumps(rep))
        return

    if not os.path.isfile(out_path):
        rep["error"] = "exporter returned but no file at " + out_path
        print("__HEAD__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_path)
    rep["ok"] = rep["bytes"] > 0
    print("__HEAD__" + json.dumps(rep))


main()
