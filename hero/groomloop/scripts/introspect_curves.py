"""introspect_curves.py -- what does bpy.types.Curves actually support in 5.2?

Written after a hand-rolled cull (create new hair_curves, add_curves, copy
attributes element-wise) crashed Blender with EXCEPTION_ACCESS_VIOLATION.
Before writing a second version of that, ask the API what it provides -- a
built-in removal is both safer and faster than rebuilding 375k points from
Python.
"""
import json
import sys

import bpy

a = sys.argv
out = (a[a.index("--") + 1:] or ["curves_api.json"])[0]

rep = {"blender": bpy.app.version_string}
rep["Curves_methods"] = sorted(
    m for m in dir(bpy.types.Curves) if not m.startswith("__"))
rep["Curves_funcs"] = sorted(
    m for m in dir(bpy.types.Curves)
    if not m.startswith("_") and callable(getattr(bpy.types.Curves, m, None)))
rep["CurveSlice"] = sorted(
    m for m in dir(bpy.types.CurveSlice) if not m.startswith("__"))
rep["object_ops_curves"] = sorted(
    o for o in dir(bpy.ops.curves) if not o.startswith("_"))
rep["geometry_ops"] = sorted(
    o for o in dir(bpy.ops.geometry) if not o.startswith("_"))
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=2)
print("__API__" + json.dumps({
    "remove_curves": "remove_curves" in rep["Curves_methods"],
    "add_curves": "add_curves" in rep["Curves_methods"],
    "resize_curves": "resize_curves" in rep["Curves_methods"],
    "set_types": "set_types" in rep["Curves_methods"],
    "curves_ops": rep["object_ops_curves"]}))
