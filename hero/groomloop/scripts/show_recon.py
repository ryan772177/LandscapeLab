"""Print recon.json in a readable form. Plain CPython, no Blender."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "hero/groomloop/recon/recon.json"
d = json.load(open(path, encoding="utf-8"))
print("blender      ", d["blender"])
print("unit scale   ", d["scene_unit_scale"], d["scene_unit_system"])
print("objects      ", d["object_count"], d["type_histogram"])
print("scene bbox   ", d.get("scene_bbox_min"), "->", d.get("scene_bbox_max"))
print("scene dims   ", d.get("scene_bbox_dims"))
for o in d["objects"]:
    print()
    print("--- %s (%s / %s)" % (o["name"], o["type"], o["data_type"]))
    for k in ("curve_count", "point_count", "points_per_curve", "spline_count",
              "spline_types", "surface", "surface_uv_map",
              "bbox_min", "bbox_max", "bbox_dims"):
        if k in o:
            print("   %-18s %s" % (k, o[k]))
    if o.get("attributes"):
        print("   attributes:")
        for a in o["attributes"]:
            print("      %-26s %-10s %s" % (a["name"], a["domain"], a["data_type"]))
    print("   matrix_world:")
    for r in o["matrix_world"]:
        print("      ", [round(x, 4) for x in r])
print()
print("export ops :", d.get("export_operators"))
groom = [a for a in d.get("addons_enabled", []) if "groom" in a.lower()]
print("groom addon:", groom)
print("addons     :", len(d.get("addons_enabled", [])), "enabled")
