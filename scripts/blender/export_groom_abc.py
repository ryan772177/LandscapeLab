"""export_groom_abc.py — drive GroomExporter headlessly to an .abc.

    blender.exe --background <file.blend> --python this.py -- <out.abc> \
        <node_group> <node_call> [groom_scale]

NO --factory-startup: the add-on is installed via user Preferences and would
not register without them, and a missing add-on and a disabled one look the
same from inside a script.

IT NEVER SAVES THE .BLEND. The source file is a vendor original under the
hard floor. There is no save call in here; read-only is structural, not a
promise.

WHY THIS IS SCRIPTABLE AT ALL, since the fallback plan assumed it might not
be: `bpy.ops.groom.buttonexport` takes filepath, groom_scale,
groom_width_scale, groom_radius_to_diameter, groom_animation and the
node_group / node_call pair that names WHICH export configuration to run.
It needs no window and no click.

THE EXPORT SET IS CHOSEN BY NODE GROUP, WHICH IS ALSO THE VARIANT FILTER.
The demo file authors one export configuration per style: "Curly hair" holds
a single Curve Selector, "Metahuman Braid Bun" holds five. Naming the group
IS excluding the other variants, so exclusion is a property of the file's own
authoring rather than a list this script maintains -- which is the difference
between a filter that can drift and one that cannot.

VERIFICATION IS THE CALLER'S JOB AND IT IS NOT OPTIONAL. This prints the
evaluated curve count of every Curves object so the exported .abc can be
checked against the inventory. An .abc that silently contains a second style,
or nothing, is a file that imports fine and is wrong.
"""

import json
import os
import sys

import bpy


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 3:
        print("__EXPORT__" + json.dumps(
            {"ok": False, "error": "need: <out.abc> <node_group> <node_call> "
                                   "[groom_scale]"}))
        return
    out_path, node_group, node_call = tail[0], tail[1], tail[2]
    groom_scale = float(tail[3]) if len(tail) > 3 else 1.0

    rep = {"ok": False, "out": out_path, "node_group": node_group,
           "node_call": node_call, "groom_scale": groom_scale,
           "blend": bpy.data.filepath, "blender": bpy.app.version_string}

    # Inventory BEFORE the export, so the count comparison has a source that
    # is not the exporter's own report.
    dg = bpy.context.evaluated_depsgraph_get()
    inv = {}
    for ob in bpy.data.objects:
        if ob.type != "CURVES":
            continue
        try:
            ev = ob.evaluated_get(dg)
            inv[ob.name] = {"authored": len(ob.data.curves),
                            "evaluated": len(ev.data.curves),
                            "points_evaluated": len(ev.data.points)}
        except Exception as exc:
            inv[ob.name] = {"error": str(exc)}
    rep["inventory"] = inv

    if bpy.data.node_groups.get(node_group) is None:
        rep["error"] = ("no node group named %r. Present: %s"
                        % (node_group,
                           sorted(g.name for g in bpy.data.node_groups)[:40]))
        print("__EXPORT__" + json.dumps(rep))
        return

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    before = os.path.getsize(out_path) if os.path.isfile(out_path) else None
    rep["existed_before"] = before

    # ---- SELECTION IS THE EXPORT FILTER, AND `node_execution` SUPPLIES IT --
    # ExporterOperators.GetCurvesObjects(context) iterates
    # `context.selected_objects` and keeps the CURVES ones. Headless nothing
    # is selected, so with node_execution=False that list is empty and the
    # exporter dies on `curvesObjects[0]` with an IndexError -- which reads
    # like a broken add-on and is a missing precondition.
    #
    # AlembicGroomExporter.execute is `if self.node_execution:
    # ...export_preparation()`, and export_preparation is what deselects all,
    # selects the node group's own objects and stamps the groom attributes on
    # them. So node_execution=True is not an "advanced" flag, it is the flag
    # that makes an export from a node group work at all. Passing False was
    # my error, not the add-on's.
    #
    # export_preparation reads self.unique_nodes without building it, and
    # unique_nodes is filled by update_attributes(), which is normally driven
    # by UI node-tree updates (its update() touches bpy.context.space_data,
    # which is None headless). bpy.ops.groom.nodeupdate is the add-on's own
    # way to force it, so it is used rather than reaching into the node.
    try:
        res_upd = bpy.ops.groom.nodeupdate(node_group=node_group,
                                           node_call=node_call)
        rep["nodeupdate"] = list(res_upd)
    except Exception as exc:
        rep["nodeupdate_error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_path,
            check_existing=False,
            groom_scale=groom_scale,
            groom_width_scale=True,
            groom_radius_to_diameter=True,
            groom_animation=False,
            node_group=node_group,
            node_call=node_call,
            node_execution=True)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "operator raised: %s: %s" % (type(exc).__name__, exc)
        print("__EXPORT__" + json.dumps(rep))
        return

    if not os.path.isfile(out_path):
        rep["error"] = ("operator returned %s but no file at %s -- a return "
                        "of FINISHED is not evidence a file was written"
                        % (rep.get("operator_result"), out_path))
        print("__EXPORT__" + json.dumps(rep))
        return

    rep["bytes"] = os.path.getsize(out_path)
    rep["ok"] = rep["bytes"] > 0
    if not rep["ok"]:
        rep["error"] = "wrote a ZERO BYTE file"
    print("__EXPORT__" + json.dumps(rep))


main()
