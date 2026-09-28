"""brief5_editor_census.py -- Brief 5 v3 read-only editor pass.

Covers Task 2d (HLOD cell distances from GRID INDEX, not bounds), Task 4a (fresh
tree LOD/bounds probe), Task 4c (HLOD layer types + what the proxies are), and
Task 4d (FoliageType flags + Nanite Foliage project setting + per-mesh Nanite).

READ-ONLY: loads assets and reads the asset registry; spawns nothing, hides
nothing, saves nothing. Writes two JSON artefacts and prints a __LL__ marker.

APIs verified this session (research/brief5/input/levers_verified.md + recon):
 - get_actor_bounds returns DEGENERATE extents for Instanced HLOD actors, so 2d
   derives cell centre from the name grid index: centre=(idx+0.5)*cellsize,
   cellsize(L)=L0*2^L, L0=25600 cm (find_instanced_cell_by_grid.py).
 - HLODLayer: layer_type/cell_size/loading_range/parent_layer via
   get_editor_property (HLODLayer.h; cell_size/loading_range deprecated 5.7 but
   still reflected -- flagged).
 - FoliageType_InstancedStaticMesh at /Game/Foliage/FT_<name>; props
   enable_density_scaling / enable_cull_distance_scaling / cull_distance(.min/.max)
   / cast_shadow / world_position_offset_disable_distance (FoliageType.h).
 - URendererSettings.enable_nanite_foliage (r.Nanite.Foliage).
"""
import json as _json
import math as _math
import os as _os
import re as _re
import traceback as _tb
import unreal as _u

_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))

# The four stations this census reports against (cm). treeline/plaza/vista from
# the ratified spline read-backs; forest_floor from forest_station.json.
STATIONS = {
    "treeline": (-190000.0, 100000.0, 63367.4),
    "plaza": (-210800.0, 278800.0, 18847.2),
    "vista": (-216400.0, 63600.0, 76426.2),
}
_forest_floor_load_error = None
try:
    _fs = _json.load(open(_os.path.join(_root, "research", "brief5", "input",
                                        "forest_station.json"), encoding="utf-8"))
    _c = _fs["camera"]
    STATIONS["forest_floor"] = (_c["x_cm"], _c["y_cm"], _c["z_cm"])
except Exception as _fe:
    _forest_floor_load_error = str(_fe)  # non-silent: surfaced in the output

TREE_SPECIES = ["Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"]
L0_CELL = 25600.0
_RX = _re.compile(r"_L(\d+)_X(-?\d+)_Y(-?\d+)")


def _pctl(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo = int(_math.floor(k))
    hi = int(_math.ceil(k))
    if lo == hi:
        return round(s[lo], 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


out = {"ok": False}
try:
    eal = _u.EditorAssetLibrary
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)

    # ---- Task 4c part 1: HLOD layer assets -------------------------------
    hlod_layers = {}
    for lpath in ("/Game/Alpine8K_HLODLayer_Instanced",
                  "/Game/Alpine8K_HLODLayer_Merged"):
        rec = {"path": lpath, "exists": eal.does_asset_exist(lpath)}
        if rec["exists"]:
            a = eal.load_asset(lpath)
            for prop, key in (("layer_type", "layer_type"),
                              ("cell_size", "cell_size_cm_DEPRECATED_5_7"),
                              ("loading_range", "loading_range_cm_DEPRECATED_5_7")):
                try:
                    v = a.get_editor_property(prop)
                    rec[key] = str(v)
                except Exception as e:
                    rec[key] = "UNKNOWN: %s" % e
            try:
                pl = a.get_editor_property("parent_layer")
                rec["parent_layer"] = pl.get_path_name() if pl else None
            except Exception as e:
                rec["parent_layer"] = "UNKNOWN: %s" % e
        hlod_layers[lpath] = rec
    out["hlod_layers"] = hlod_layers

    # ---- Task 2d: HLOD cell distances from the grid index -----------------
    ar = _u.AssetRegistryHelpers.get_asset_registry()
    arf = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine", "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    hlods = ar.get_assets(arf)
    cells = []           # (layer, level, cx, cy)
    by_layer_level = {}
    parsed = unparsed = 0
    for ad in hlods:
        try:
            obj = ad.get_asset()
            label = obj.get_actor_label() if obj else None
        except Exception:
            label = None
        if not label:
            unparsed += 1
            continue
        m = _RX.search(label)
        if not m:
            unparsed += 1
            continue
        parsed += 1
        lvl, ix, iy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        layer = ("Merged" if "HLODLayer_Merged" in label
                 else "Instanced" if "HLODLayer_Instanced" in label else "other")
        cs = L0_CELL * (2 ** lvl)
        cx = (ix + 0.5) * cs
        cy = (iy + 0.5) * cs
        cells.append((layer, lvl, cx, cy))
        by_layer_level[(layer, lvl)] = by_layer_level.get((layer, lvl), 0) + 1
    out["hlod_cells_total"] = len(cells)
    out["hlod_labels_parsed"] = parsed
    out["hlod_labels_unparsed"] = unparsed
    out["hlod_cells_by_layer_level"] = {"%s_L%d" % k: v
                                        for k, v in by_layer_level.items()}
    # distances per station per layer-level (from cell centre, 2D horizontal)
    dist = {}
    for zone, (sx, sy, _sz) in STATIONS.items():
        dist[zone] = {}
        buckets = {}
        for layer, lvl, cx, cy in cells:
            d_m = _math.sqrt((cx - sx) ** 2 + (cy - sy) ** 2) / 100.0
            buckets.setdefault((layer, lvl), []).append(d_m)
        for (layer, lvl), ds in buckets.items():
            dist[zone]["%s_L%d" % (layer, lvl)] = {
                "n": len(ds), "min": _pctl(ds, 0.0), "p10": _pctl(ds, 0.10),
                "p50": _pctl(ds, 0.50), "p90": _pctl(ds, 0.90),
                "max": _pctl(ds, 1.0)}
        # nearest HLOD cell of any layer/level
        allds = [_math.sqrt((cx - sx) ** 2 + (cy - sy) ** 2) / 100.0
                 for _l, _lv, cx, cy in cells]
        dist[zone]["_nearest_any_m"] = round(min(allds), 1) if allds else None
    out["hlod_cell_distance_m"] = dist
    out["_forest_floor_load_error"] = _forest_floor_load_error
    out["_2d_method"] = ("cell centre = (grid_index + 0.5) * cellsize, "
                         "cellsize(L)=25600*2^L cm; distance is 2D horizontal "
                         "from station to cell centre. Grid index parsed from the "
                         "actor label (get_actor_bounds is degenerate for "
                         "Instanced HLOD).")

    # ---- Task 4a: fresh tree LOD/bounds probe -----------------------------
    recipe = _json.load(open(_os.path.join(_root, "recipes", "alpine_8k.json"),
                             encoding="utf-8-sig"))
    meshes_cfg = [[s["name"], s["mesh"]]
                  for s in (recipe.get("foliage") or {}).get("species") or []
                  if s.get("system") != "grass" and "role" not in s]
    probe = {"_date": "2026-09-20", "_what": "Brief 5 v3 Task 4a fresh tree LOD "
             "probe (re-run of tree_lod_probe logic, today's date).", "meshes": []}
    per_mesh_nanite = {}
    for name, path in meshes_cfg:
        rec = {"species": name, "path": path, "loaded": False}
        m = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if m is None:
            rec["error"] = "asset not found"
            probe["meshes"].append(rec)
            continue
        rec["loaded"] = True
        # nanite + shape preservation (Task 4d per-mesh)
        try:
            ns = m.get_editor_property("nanite_settings")
            rec["nanite_enabled"] = bool(ns.get_editor_property("enabled"))
            nano = {"enabled": rec["nanite_enabled"]}
            for cand in ("preserve_area", "fallback_target",
                         "fallback_percent_triangles", "fallback_relative_error",
                         "keep_percent_triangles", "trim_relative_error",
                         "position_precision", "displacement_uv_channel"):
                try:
                    nano[cand] = str(ns.get_editor_property(cand))
                except Exception:
                    pass
            per_mesh_nanite[name] = nano
        except Exception as e:
            rec["nanite_enabled"] = None
            rec["nanite_note"] = "UNKNOWN: %s" % e
        rec["lod_count"] = int(ss.get_lod_count(m))
        try:
            rec["screen_sizes"] = [float(v) for v in ss.get_lod_screen_sizes(m)]
        except Exception:
            rec["screen_sizes"] = None
        tris = []
        for i in range(rec["lod_count"]):
            try:
                tris.append(int(m.get_num_triangles(i)))
            except Exception:
                tris.append(None)
        rec["triangles_per_lod"] = tris
        try:
            b = m.get_bounds()
            be = b.box_extent
            rec["bounds_extent_cm"] = [float(be.x), float(be.y), float(be.z)]
            rec["height_cm"] = float(be.z) * 2.0
            rec["bounding_sphere_radius_cm"] = float(b.sphere_radius)
        except Exception as e:
            rec["bounds_error"] = str(e)
        probe["meshes"].append(rec)

    # ---- Task 4d: FoliageType flags + project Nanite Foliage --------------
    ft_dir = "/Game/Foliage"
    foliage_types = {}
    for name in TREE_SPECIES:
        p = "%s/FT_%s" % (ft_dir, name)
        rec = {"path": p, "exists": eal.does_asset_exist(p)}
        if rec["exists"]:
            ft = eal.load_asset(p)
            for prop in ("enable_density_scaling", "enable_cull_distance_scaling",
                         "cast_shadow", "world_position_offset_disable_distance",
                         "affect_distance_field_lighting"):
                try:
                    rec[prop] = ft.get_editor_property(prop)
                except Exception as e:
                    rec[prop] = "UNKNOWN: %s" % e
            try:
                cd = ft.get_editor_property("cull_distance")
                rec["cull_distance_min"] = int(cd.min)
                rec["cull_distance_max"] = int(cd.max)
            except Exception as e:
                rec["cull_distance"] = "UNKNOWN: %s" % e
        foliage_types[name] = rec
    out["foliage_types"] = foliage_types
    out["per_mesh_nanite"] = per_mesh_nanite

    # project Nanite Foliage setting
    try:
        rs = _u.get_default_object(_u.RendererSettings)
        out["project_nanite_foliage_enabled"] = bool(
            rs.get_editor_property("enable_nanite_foliage"))
    except Exception as e:
        out["project_nanite_foliage_enabled"] = "UNKNOWN: %s" % e

    # write the fresh probe
    _pd = _os.path.join(_root, "_verify", "bench", "2026-09-20")
    if not _os.path.isdir(_pd):
        _os.makedirs(_pd)
    with open(_os.path.join(_pd, "tree_lod_probe_v3.json"), "w",
              encoding="utf-8") as fh:
        _json.dump(probe, fh, indent=2)
    out["tree_lod_probe_v3"] = "_verify/bench/2026-09-20/tree_lod_probe_v3.json"
    out["ok"] = True
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input",
                          "editor_census_v3.json")
    with open(_dest, "w", encoding="utf-8") as fh:
        _json.dump(out, fh, indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

# COMPACT status only -- the full result is on disk. A truncated dump of `out`
# would be invalid JSON and ue_exec would decode-fail on a SUCCESSFUL run
# (auditor should-fix). So print a small, always-valid summary object.
_status = {
    "ok": out.get("ok"),
    "error": out.get("error"),
    "written_to": out.get("written_to"),
    "tree_lod_probe_v3": out.get("tree_lod_probe_v3"),
    "hlod_cells_total": out.get("hlod_cells_total"),
    "hlod_cells_by_layer_level": out.get("hlod_cells_by_layer_level"),
    "project_nanite_foliage_enabled": out.get("project_nanite_foliage_enabled"),
}
print("__LL__" + _json.dumps(_status, default=str))
