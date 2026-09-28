"""check_gn_bakes.py — is the groom's node stack replaying BAKED geometry?

    blender.exe --background <blend> --python this.py

Six inputs were changed with zero effect on the evaluated output -- surface
pointer, parent, every Object socket, all 3,636 authored points, both
snap_curves_to_surface modes, and rest geometry on the target. Evaluated Z
read 131.059..154.646 every single time, measured from real point positions
rather than from bound_box.

A modifier stack that ignores every one of its inputs is not computing. GN
modifiers can BAKE their result and replay it, which would produce exactly
this: 31,570 curves that are correct for the head they were baked on and
deaf to everything afterwards. The demo .blend is 171 MB, which is a lot of
file for 303 authored curves.

This asks each modifier what it has baked, and then turns the stack off one
modifier at a time to see which one owns the frozen output.
"""

import json

import bpy
import mathutils


def world_z(ob, dg):
    src = ob.evaluated_get(dg)
    mw = ob.matrix_world
    try:
        pts = src.data.points
        if len(pts):
            zs = [(mw @ mathutils.Vector(p.position)).z for p in pts]
            return [round(min(zs), 3), round(max(zs), 3), len(src.data.curves)]
    except Exception:
        pass
    return None


out = {"blend": bpy.data.filepath}
curves = [o for o in bpy.data.objects if o.type == "CURVES"]
groom = max(curves, key=lambda o: len(o.data.curves))
out["groom"] = groom.name
out["authored_curves"] = len(groom.data.curves)

dg = bpy.context.evaluated_depsgraph_get()
out["baseline"] = world_z(groom, dg)

mods = []
for m in groom.modifiers:
    rec = {"name": m.name, "type": m.type, "show_viewport": bool(m.show_viewport)}
    if m.type == "NODES":
        rec["node_group"] = m.node_group.name if m.node_group else None
        rec["bake_directory"] = getattr(m, "bake_directory", None)
        rec["bake_target"] = str(getattr(m, "bake_target", None))
        try:
            bakes = []
            for b in m.bakes:
                brec = {}
                for attr in ("bake_id", "bake_mode", "frame_start", "frame_end",
                             "use_custom_path", "use_custom_simulation_frame_range",
                             "directory", "node_type"):
                    if hasattr(b, attr):
                        try:
                            brec[attr] = str(getattr(b, attr))
                        except Exception:
                            pass
                bakes.append(brec)
            rec["bakes"] = bakes
            rec["bake_count"] = len(bakes)
        except Exception as exc:
            rec["bakes_error"] = str(exc)
    mods.append(rec)
out["modifiers"] = mods

# Turn each modifier off in turn and see which one owns the frozen result.
per_mod = {}
for m in groom.modifiers:
    was = m.show_viewport
    m.show_viewport = False
    bpy.context.view_layer.update()
    dg2 = bpy.context.evaluated_depsgraph_get()
    per_mod[m.name] = world_z(groom, dg2)
    m.show_viewport = was
bpy.context.view_layer.update()
out["with_each_disabled"] = per_mod

# And with the WHOLE stack off: that is the authored geometry, and it is the
# control -- if this equals the baseline, the stack contributes nothing at
# all and the 31,570 curves are coming from somewhere else entirely.
states = [(m, m.show_viewport) for m in groom.modifiers]
for m, _ in states:
    m.show_viewport = False
bpy.context.view_layer.update()
dg3 = bpy.context.evaluated_depsgraph_get()
out["all_disabled"] = world_z(groom, dg3)
for m, was in states:
    m.show_viewport = was
bpy.context.view_layer.update()

print("__BAKES__" + json.dumps(out, default=str))
