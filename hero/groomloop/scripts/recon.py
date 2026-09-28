"""recon.py -- Phase 0. Import the source .abc and describe EXACTLY what arrived.

    blender --background --python recon.py -- <abc_path> <out_json>

Nothing downstream may assume an object type. Alembic hair can arrive as a
legacy Curve, as the new Curves (hair) type, or as a Mesh depending on how it
was written, and the edit engine is a different program in each case. So this
dumps what is actually there and every later script reads this file.

It also reports ATTRIBUTES per object, because the UE groom pipeline consumes
named attributes (width/radius, groom_group_id, root UV) and an export path
that silently drops them produces strands at UE's 1 cm fallback -- spaghetti.
"""

import json
import os
import sys

import bpy
import mathutils


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def describe_object(ob):
    d = {"name": ob.name, "type": ob.type,
         "matrix_world": [list(r) for r in ob.matrix_world],
         "parent": ob.parent.name if ob.parent else None}
    data = ob.data
    d["data_type"] = type(data).__name__ if data else None

    # --- new-style hair Curves --------------------------------------------
    if ob.type == "CURVES":
        cs = data.curves
        sizes = [c.points_length for c in cs]
        d["curve_count"] = len(cs)
        d["point_count"] = len(data.points)
        if sizes:
            d["points_per_curve"] = {
                "min": min(sizes), "max": max(sizes),
                "mean": round(sum(sizes) / len(sizes), 3),
                "uniform": min(sizes) == max(sizes)}
        d["attributes"] = [{"name": a.name, "domain": a.domain,
                            "data_type": a.data_type}
                           for a in data.attributes]
        d["surface"] = data.surface.name if getattr(data, "surface", None) else None
        d["surface_uv_map"] = getattr(data, "surface_uv_map", None)

    # --- legacy Curve ------------------------------------------------------
    elif ob.type == "CURVE":
        sp = data.splines
        kinds = {}
        pts = []
        for s in sp:
            kinds[s.type] = kinds.get(s.type, 0) + 1
            pts.append(len(s.points) if s.type == "POLY" else len(s.bezier_points))
        d["spline_count"] = len(sp)
        d["spline_types"] = kinds
        d["point_count"] = sum(pts)
        if pts:
            d["points_per_curve"] = {
                "min": min(pts), "max": max(pts),
                "mean": round(sum(pts) / len(pts), 3),
                "uniform": min(pts) == max(pts)}
        d["bevel_depth"] = getattr(data, "bevel_depth", None)
        d["attributes"] = [{"name": a.name, "domain": a.domain,
                            "data_type": a.data_type}
                           for a in getattr(data, "attributes", [])]

    elif ob.type == "MESH":
        d["vertex_count"] = len(data.vertices)
        d["poly_count"] = len(data.polygons)
        d["edge_count"] = len(data.edges)
        d["attributes"] = [{"name": a.name, "domain": a.domain,
                            "data_type": a.data_type}
                           for a in data.attributes]
        d["uv_layers"] = [uv.name for uv in data.uv_layers]

    try:
        pts = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
        d["bbox_min"] = [round(min(p[i] for p in pts), 4) for i in range(3)]
        d["bbox_max"] = [round(max(p[i] for p in pts), 4) for i in range(3)]
        d["bbox_dims"] = [round(d["bbox_max"][i] - d["bbox_min"][i], 4)
                          for i in range(3)]
    except Exception as exc:
        d["bbox_error"] = str(exc)
    return d


def main():
    tail = argv_tail()
    if len(tail) < 2:
        print("__RECON__" + json.dumps({"ok": False, "error": "need <abc> <out>"}))
        return
    abc, out = tail[0], tail[1]

    rep = {"ok": False, "abc": abc,
           "blender": bpy.app.version_string,
           "scene_unit_scale": bpy.context.scene.unit_settings.scale_length,
           "scene_unit_system": bpy.context.scene.unit_settings.system}

    # Empty the startup scene so nothing described below is the default Cube.
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    try:
        res = bpy.ops.wm.alembic_import(filepath=abc, as_background_job=False)
        rep["import_result"] = list(res)
    except Exception as exc:
        rep["error"] = "alembic_import raised: %s" % exc
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        print("__RECON__" + json.dumps(rep))
        return

    objs = list(bpy.data.objects)
    rep["object_count"] = len(objs)
    rep["objects"] = [describe_object(o) for o in objs]
    hist = {}
    for o in objs:
        hist[o.type] = hist.get(o.type, 0) + 1
    rep["type_histogram"] = hist

    mins, maxs = [], []
    for o in rep["objects"]:
        if "bbox_min" in o:
            mins.append(o["bbox_min"])
            maxs.append(o["bbox_max"])
    if mins:
        rep["scene_bbox_min"] = [round(min(m[i] for m in mins), 4) for i in range(3)]
        rep["scene_bbox_max"] = [round(max(m[i] for m in maxs), 4) for i in range(3)]
        rep["scene_bbox_dims"] = [
            round(rep["scene_bbox_max"][i] - rep["scene_bbox_min"][i], 4)
            for i in range(3)]

    # Which export operators exist in THIS build, so Phase 0.4 does not guess.
    ops = []
    for name in dir(bpy.ops.wm):
        if "alembic" in name.lower():
            ops.append("wm." + name)
    for mod in dir(bpy.ops):
        if "groom" in mod.lower() or "turbo" in mod.lower():
            try:
                ops += ["%s.%s" % (mod, o) for o in dir(getattr(bpy.ops, mod))
                        if not o.startswith("_")]
            except Exception:
                pass
    rep["export_operators"] = sorted(set(ops))
    rep["addons_enabled"] = sorted(
        m.__name__ for m in __import__("addon_utils").modules()
        if __import__("addon_utils").check(m.__name__)[1])

    rep["ok"] = True
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print("__RECON__" + json.dumps({"ok": True, "out": out,
                                    "objects": rep["object_count"],
                                    "types": hist}))


if __name__ == "__main__":
    main()
