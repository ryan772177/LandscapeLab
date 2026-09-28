"""export_groom_object.py — export the largest Curves object in a .blend.

    blender.exe --background <blend> --python this.py -- <out.abc>

Separated from the authoring and repair stages so an export can be repeated
without re-running them. Selection-driven (node_execution=False), which needs
GroomProperty on the object to name the attributes -- the appended demo groom
carries those already.

Reports the ROOT BAND from real point positions before exporting, because a
groom that is in the wrong place exports perfectly well and the count tells
you nothing.
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
        print("__EXPORT2__" + json.dumps({"ok": False, "error": "need <out.abc>"}))
        return
    out_abc = tail[0]
    rep = {"ok": False, "out": out_abc, "blend": bpy.data.filepath}

    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    if not curves:
        rep["error"] = "no curves object"
        print("__EXPORT2__" + json.dumps(rep))
        return
    groom = max(curves, key=lambda o: len(o.data.curves))
    rep["groom"] = groom.name

    dg = bpy.context.evaluated_depsgraph_get()
    ev = groom.evaluated_get(dg)
    mw = groom.matrix_world
    zs = [(mw @ mathutils.Vector(p.position)).z for p in ev.data.points]
    rep["evaluated"] = {"curves": len(ev.data.curves), "points": len(ev.data.points),
                        "z": [round(min(zs), 3), round(max(zs), 3)]}
    # IS IT STILL HAIR? Asked before asking where it is.
    # The crown check below passed a groom of 180,926 curves carrying 184,259
    # points -- 1.02 points per curve -- and UE died importing it:
    #     Assertion failed: CurveNumVertices >= 2
    #     GroomBuilder.cpp:2403
    # A Z-band check answers "is it in the right place" and says nothing
    # about whether the thing in that place is a strand. Both questions, and
    # this one first, because it is the one that takes the editor down.
    n_c = len(ev.data.curves)
    n_p = len(ev.data.points)
    rep["points_per_curve"] = round(n_p / max(1, n_c), 3)
    if n_c and (n_p / n_c) < 2.0:
        rep["error"] = ("REFUSE: %.3f points per curve. UE asserts "
                        "CurveNumVertices >= 2 (GroomBuilder.cpp:2403) and "
                        "takes the editor down on import. These are not "
                        "strands." % rep["points_per_curve"])
        print("__EXPORT2__" + json.dumps(rep))
        return

    head = groom.data.surface
    if head is not None:
        hz = [(head.matrix_world @ v.co).z for v in head.data.vertices]
        rep["head_z"] = [round(min(hz), 3), round(max(hz), 3)]
        # THE PRECONDITION: the crown must sit at the head's crown. The bottom
        # is free -- long hair legitimately hangs past the jaw -- so testing
        # the whole span would refuse a correct groom.
        rep["crown_delta_cm"] = round(rep["evaluated"]["z"][1] - max(hz), 3)
        rep["crown_ok"] = abs(rep["crown_delta_cm"]) < 3.0
        if not rep["crown_ok"]:
            rep["error"] = ("REFUSE: groom crown is %.3f cm from the head's "
                            "crown; roots are not on this skull"
                            % rep["crown_delta_cm"])
            print("__EXPORT2__" + json.dumps(rep))
            return

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
        print("__EXPORT2__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__EXPORT2__" + json.dumps(rep))


main()
