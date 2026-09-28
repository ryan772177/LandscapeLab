"""add_rest_geometry.py — give our head the Capture Rest Geometry modifier the
demo's heads carry, then re-check whether the groom follows.

    blender.exe --background <repointed.blend> --python this.py -- [out.blend]

THE ASYMMETRY THIS TESTS. The demo's `head_lod0_mesh` and
`head_lod0_mesh_scalp` BOTH carry a "Capture Rest Geometry" Geometry Nodes
modifier. Our exported head carries none, because it came from UE as a plain
FBX.

That matters because the groom's evaluated attributes include
`rest_position`, and the stack's output position tracks neither the authored
curve points nor the surface pointer nor `snap_curves_to_surface` -- all three
were changed and the evaluated Z stayed 131.059..154.646 to three decimals.
Something baked is driving it, and rest geometry captured on the SURFACE is
the candidate the demo file itself points at.

If the groom follows once our head captures its own rest geometry, the route
opens. If it does not, the stack is bound to the mesh it was authored against
in a way no pointer change reaches, and that is worth knowing definitively
rather than suspected.

MEASURED FROM POINTS, NOT bound_box -- that cache read identical across four
operations that could not all have left the groom unchanged.
"""

import json
import sys

import bpy
import mathutils


def world_z(ob, dg=None):
    src = ob.evaluated_get(dg) if dg is not None else ob
    mw = ob.matrix_world
    try:
        pts = src.data.points
        if len(pts):
            zs = [(mw @ mathutils.Vector(p.position)).z for p in pts]
            return [round(min(zs), 3), round(max(zs), 3)]
    except Exception:
        pass
    zs = [(mw @ mathutils.Vector(c)).z for c in src.bound_box]
    return [round(min(zs), 3), round(max(zs), 3)]


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    out_blend = tail[0] if tail else ""

    rep = {"blend": bpy.data.filepath}
    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    if not curves:
        rep["error"] = "no curves object"
        print("__REST__" + json.dumps(rep))
        return
    groom = max(curves, key=lambda o: len(o.data.curves))
    head = groom.data.surface
    if head is None:
        rep["error"] = "the groom declares no surface"
        print("__REST__" + json.dumps(rep))
        return
    rep["groom"] = groom.name
    rep["head"] = head.name
    rep["head_modifiers_before"] = [m.name for m in head.modifiers]

    dg = bpy.context.evaluated_depsgraph_get()
    rep["evaluated_z_before"] = world_z(groom, dg)

    ng = bpy.data.node_groups.get("Capture Rest Geometry")
    rep["node_group_present"] = ng is not None
    if ng is None:
        rep["error"] = ("no 'Capture Rest Geometry' node group in this file; "
                        "it should have arrived with the appended demo heads")
        print("__REST__" + json.dumps(rep))
        return

    if "Capture Rest Geometry" not in [m.name for m in head.modifiers]:
        m = head.modifiers.new(name="Capture Rest Geometry", type="NODES")
        m.node_group = ng
        rep["added"] = True
    else:
        rep["added"] = False
    rep["head_modifiers_after"] = [m.name for m in head.modifiers]

    # Force a full re-evaluation rather than trusting the previous depsgraph.
    bpy.context.view_layer.update()
    dg2 = bpy.context.evaluated_depsgraph_get()
    rep["evaluated_z_after"] = world_z(groom, dg2)
    try:
        ev = groom.evaluated_get(dg2)
        rep["evaluated_curves"] = len(ev.data.curves)
        rep["evaluated_attrs"] = [a.name for a in ev.data.attributes]
    except Exception as exc:
        rep["evaluated_error"] = str(exc)

    hz = world_z(head)
    rep["head_z"] = hz
    az = rep["evaluated_z_after"]
    rep["moved"] = az != rep["evaluated_z_before"]
    rep["on_head"] = bool(az[1] > hz[0] + 0.4 * (hz[1] - hz[0]))
    rep["verdict"] = ("groom %s vs head %s -- %s%s"
                      % (az, hz,
                         "ON THE HEAD" if rep["on_head"] else "not on the head",
                         "" if rep["moved"] else ", and it did not move at all"))

    if out_blend:
        try:
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            rep["saved"] = out_blend
        except Exception as exc:
            rep["save_error"] = str(exc)

    print("__REST__" + json.dumps(rep, default=str))


main()
