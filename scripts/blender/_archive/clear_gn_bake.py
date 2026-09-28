"""clear_gn_bake.py — drop the baked geometry so the groom stack recomputes.

    blender.exe --background <blend> --python this.py -- [out.blend]

THE FINDING THIS ACTS ON. The groom's interpolation modifier, "Curly hair _
modded to custom head" (node group "GroomExporter Curly Hair"), carries a
DISK bake pointing into the demo author's own cache:

    bake_target     DISK
    bake_directory  //..\\..\\..\\Documents\\blendcache_Groom_Metahuman_Test_52\\...
    bakes           1   bake_id 1309841462, STILL

So its 31,570 curves are READ FROM DISK, baked against HIS head. That is why
six separate input changes -- surface pointer, parent, every Object socket,
all 3,636 authored points, both snap_curves_to_surface modes, and rest
geometry on our target -- moved the evaluated output by exactly nothing.

The discriminating control was already in the data: disabling the voxelyze
modifier produced 180,926 curves spanning Z 128.143..178.434, whose top
matches our head's 178.437. Something in the stack DOES reach our skull once
the frozen path is disturbed.

WHAT THIS DOES: clears the bake so the stack evaluates for real, then reads
the Z band from actual point positions.
"""

import json
import sys

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


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    out_blend = tail[0] if tail else ""

    out = {"blend": bpy.data.filepath}
    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    groom = max(curves, key=lambda o: len(o.data.curves))
    head = groom.data.surface
    out["groom"] = groom.name
    out["head"] = head.name if head else None
    if head is not None:
        mw = head.matrix_world
        zs = [(mw @ v.co).z for v in head.data.vertices]
        out["head_z"] = [round(min(zs), 3), round(max(zs), 3)]

    dg = bpy.context.evaluated_depsgraph_get()
    out["before"] = world_z(groom, dg)

    cleared = []
    for m in groom.modifiers:
        if m.type != "NODES":
            continue
        n_bakes = 0
        try:
            n_bakes = len(m.bakes)
        except Exception:
            pass
        had_dir = getattr(m, "bake_directory", "") or ""
        if n_bakes == 0 and not had_dir:
            continue
        # Try the operator first: it is the engine's own way to drop a bake.
        deleted = None
        try:
            with bpy.context.temp_override(object=groom, active_object=groom,
                                           selected_objects=[groom]):
                res = bpy.ops.object.geometry_node_bake_delete_single(
                    session_uid=groom.session_uid, modifier_name=m.name,
                    bake_id=int(m.bakes[0].bake_id) if n_bakes else 0)
                deleted = list(res)
        except Exception as exc:
            deleted = "operator failed: %s: %s" % (type(exc).__name__, exc)
        # Belt and braces: point the bake somewhere that holds nothing, so a
        # surviving cache entry cannot be found and replayed. Recorded rather
        # than done silently -- this is a deliberate cache miss, not a fix.
        try:
            m.bake_directory = ""
        except Exception:
            pass
        cleared.append({"modifier": m.name, "bakes_before": n_bakes,
                        "bake_directory_before": had_dir,
                        "delete_op": deleted,
                        "bakes_after": len(m.bakes) if hasattr(m, "bakes") else None})
    out["cleared"] = cleared

    bpy.context.view_layer.update()
    dg2 = bpy.context.evaluated_depsgraph_get()
    out["after"] = world_z(groom, dg2)
    out["moved"] = out["after"] != out["before"]
    hz = out.get("head_z")
    if hz and out["after"]:
        az = out["after"]
        out["on_head"] = bool(az[1] > hz[0] + 0.4 * (hz[1] - hz[0])
                              and az[0] > hz[0] - 12.0)
        out["verdict"] = ("groom %s vs head %s -- %s"
                          % (az[:2], hz,
                             "ON THE HEAD" if out["on_head"]
                             else "still not on the head"))

    if out_blend:
        try:
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            out["saved"] = out_blend
        except Exception as exc:
            out["save_error"] = str(exc)

    print("__CLEARBAKE__" + json.dumps(out, default=str))


main()
