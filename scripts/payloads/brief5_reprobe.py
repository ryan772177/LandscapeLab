"""brief5_reprobe.py -- Brief 5 T3: fresh tree LOD probe after set_lod_screen_sizes.
READ-ONLY. Writes _verify/bench/2026-09-21/tree_lod_probe_t3.json."""
import json
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
recipe = json.load(open(os.path.join(root, "recipes", "alpine_8k.json"),
                        encoding="utf-8-sig"))
meshes = [[s["name"], s["mesh"]]
          for s in (recipe.get("foliage") or {}).get("species") or []
          if s.get("system") != "grass" and "role" not in s]
ss = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
eal = unreal.EditorAssetLibrary
out = {"_date": "2026-09-21",
       "_what": "Brief 5 T3 fresh re-probe after set_lod_screen_sizes",
       "meshes": []}
for name, path in meshes:
    m = eal.load_asset(path) if eal.does_asset_exist(path) else None
    if not m:
        out["meshes"].append({"species": name, "error": "not found"})
        continue
    n = int(ss.get_lod_count(m))
    r = {"species": name, "path": path, "lod_count": n}
    try:
        r["nanite_enabled"] = bool(
            m.get_editor_property("nanite_settings").get_editor_property("enabled"))
    except Exception:
        r["nanite_enabled"] = None
    try:
        r["screen_sizes"] = [float(x) for x in ss.get_lod_screen_sizes(m)]
    except Exception:
        r["screen_sizes"] = None
    r["triangles_per_lod"] = [int(m.get_num_triangles(i)) for i in range(n)]
    b = m.get_bounds()
    be = b.box_extent
    r["bounds_extent_cm"] = [float(be.x), float(be.y), float(be.z)]
    r["height_cm"] = float(be.z) * 2.0
    r["bounding_sphere_radius_cm"] = float(b.sphere_radius)
    out["meshes"].append(r)
dest = os.path.join(root, "_verify", "bench", "2026-09-21")
if not os.path.isdir(dest):
    os.makedirs(dest)
with open(os.path.join(dest, "tree_lod_probe_t3.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("__LL__" + json.dumps({
    "ok": True, "written": "_verify/bench/2026-09-21/tree_lod_probe_t3.json",
    "cards": {m["species"]: (m.get("screen_sizes") or [None])[-1]
              for m in out["meshes"] if m["species"] in ("ConiferPine", "SpruceSub")}}))
