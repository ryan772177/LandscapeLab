import json as _json
import os
import traceback as _tb
import unreal as _u

# TREE LOD PROBE -- read-only. E2 (LOD silhouette audit) needs to know, for
# each placed tree species: how many LODs exist, at what screen size each
# takes over, how many triangles it carries, and whether Nanite is enabled
# (which makes discrete LOD switches moot -- Nanite does its own cluster LOD,
# so there is no switch to audit for a silhouette pop).
#
# The LOD calls are the ones measure_lod_materials.py already proves against
# 5.8: StaticMeshEditorSubsystem.get_lod_count / get_lod_screen_sizes.
# Nanite is read by reflection off `nanite_settings` and reported as UNKNOWN
# rather than guessed if the property is not exposed -- a probe that invents
# a False here would read as "no Nanite" and send E2 auditing a chain that
# does not govern anything.
#
# Spawns nothing, saves nothing, modifies nothing.

# NOTHING CROSSES THE SHELL BOUNDARY. This took the mesh list through
# `ue_exec --set`, and PowerShell strips embedded `"` from arguments to a
# native executable: valid JSON on disk arrived here as
# `[[Conifer, /Game/...]]` with every quote gone. Wrapping the placeholder in
# a raw triple-quoted string only made it PARSE, which defeated ue_exec's
# pre-flight check and moved the same failure into the editor at 240 s a go.
# See LESSONS 2026-09-09q and R-UEEXEC.
#
# So the probe reads the recipe ITSELF, and filters with the same predicate
# `place_foliage.plan()` uses -- skip `system == "grass"` (the landscape
# material's grass output places those, not the foliage planner) and skip
# anything declaring `role` (those are rocks, planned by rock_scatter.py).
# Reading the same source of truth the placement reads is the point: a
# hand-assembled list is a second copy that can disagree.
_root = os.path.dirname(os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
_recipe_path = os.path.join(_root, "recipes", "alpine_8k.json")
with open(_recipe_path, "r", encoding="utf-8-sig") as _fh:
    _recipe = _json.load(_fh)

MESHES = [[_sp["name"], _sp["mesh"]]
          for _sp in (_recipe.get("foliage") or {}).get("species") or []
          if _sp.get("system") != "grass" and "role" not in _sp]

_out = {"ok": False, "error": None, "meshes": []}
try:
    _ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    _eal = _u.EditorAssetLibrary

    for _entry in MESHES:
        _species, _path = _entry[0], _entry[1]
        _rec = {"species": _species, "path": _path, "loaded": False}
        _m = _eal.load_asset(_path) if _eal.does_asset_exist(_path) else None
        if _m is None:
            _rec["error"] = "asset not found"
            _out["meshes"].append(_rec)
            continue
        _rec["loaded"] = True

        # --- Nanite, by reflection; UNKNOWN beats a guess -----------------
        try:
            _ns = _m.get_editor_property("nanite_settings")
            _rec["nanite_enabled"] = bool(_ns.get_editor_property("enabled"))
        except Exception as _e:
            _rec["nanite_enabled"] = None
            _rec["nanite_note"] = "UNKNOWN: %s" % _e

        # --- LOD chain ----------------------------------------------------
        _n = int(_ss.get_lod_count(_m))
        _rec["lod_count"] = _n
        try:
            _rec["screen_sizes"] = [float(_v)
                                    for _v in _ss.get_lod_screen_sizes(_m)]
        except Exception:
            _rec["screen_sizes"] = None

        # `StaticMesh.get_num_triangles(lod)` -- a method on the MESH, not on
        # the subsystem. measure_lod_materials.py:92 already proves it against
        # 5.8 and I wrote `_ss.get_number_triangles(_m, _i)` instead, which
        # raised and left every count None. docs/ue58-api-protocol.md: the
        # reflected surface is the contract, and the proven call was one file
        # away.
        _tris = []
        for _i in range(_n):
            try:
                _tris.append(int(_m.get_num_triangles(_i)))
            except Exception as _e:
                _tris.append(None)
                _rec.setdefault("triangle_errors", []).append(
                    "lod %d: %s" % (_i, _e))
        _rec["triangles_per_lod"] = _tris

        # --- bounds: the silhouette height the pixel maths needs ----------
        try:
            _b = _m.get_bounds()
            _be = _b.box_extent
            _rec["bounds_extent_cm"] = [float(_be.x), float(_be.y),
                                        float(_be.z)]
            _rec["height_cm"] = float(_be.z) * 2.0
            _rec["bounding_sphere_radius_cm"] = float(_b.sphere_radius)
        except Exception as _e:
            _rec["bounds_error"] = str(_e)

        _out["meshes"].append(_rec)

    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _out["traceback"] = _tb.format_exc()

# WRITE IT DOWN. A 25 s editor round trip whose only record is stdout is one
# terminal truncation away from being spent again.
try:
    _dest = os.path.join(_root, "_verify", "bench", "2026-09-07",
                         "tree_lod_probe.json")
    if not os.path.isdir(os.path.dirname(_dest)):
        os.makedirs(os.path.dirname(_dest))
    with open(_dest, "w", encoding="utf-8") as _fh:
        _json.dump(_out, _fh, indent=2)
    _out["written_to"] = _dest
except Exception as _e:
    _out["write_error"] = str(_e)

print(_json.dumps(_out, indent=2))
