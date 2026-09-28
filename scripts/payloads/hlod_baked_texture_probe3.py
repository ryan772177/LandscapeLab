"""hlod_baked_texture_probe3.py -- baked texture size, via the COMPONENT'S MATERIAL.

READ-ONLY. R-HLODTEX acceptance, third route, and the reasons the first
two failed are recorded so the next reader does not repeat them:

  1. `AWorldPartitionHLOD`'s editor-only data is NOT reflected to Python
     -- SourceActors, InputStats, HLODStats and 12 more all raise
     "Failed to find property" (`HLODActor.h:214-245`, private bare
     UPROPERTY under WITH_EDITORONLY_DATA).
  2. `MaterialEditingLibrary.get_used_textures` returned nothing.
  3. The asset REGISTRY lists only the WorldPartitionHLOD actor for the
     cell's package: the baked mesh is an INNER OBJECT
     (`<package>.StaticMesh_Alpine8K_HLODLayer_Merged_0`), not a
     top-level asset, so it has no registry row of its own.

What does work is the ordinary component chain, which this walks and
ENUMERATES rather than guesses: component -> get_material(i) -> the
material's own surface, dumped by name so a failure names what it saw.
"""
import json as _json
import traceback as _tb

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
WANT = int(CFG.get("want_cells") or 3)
SCAN = int(CFG.get("scan_limit") or 60)

_out = {"ok": False, "target_texture_size": 4096}


def _tex_dims(_t):
    _d = {"texture": _t.get_path_name()}
    for _k, _fn in (("x", "blueprint_get_size_x"), ("y", "blueprint_get_size_y")):
        try:
            _d[_k] = int(getattr(_t, _fn)())
        except Exception:
            _d[_k] = None
    if _d.get("x") is None:
        try:
            _s = _t.get_editor_property("imported_size")
            _d["x"], _d["y"] = int(_s.x), int(_s.y)
        except Exception:
            pass
    try:
        _d["compression"] = str(_t.get_editor_property("compression_settings"))
    except Exception:
        pass
    return _d


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells_alpine8k"] = len(_hlods)

    _rows, _scanned = [], 0
    _surface_dumped = False
    for _ad in _hlods:
        if len(_rows) >= WANT or _scanned >= SCAN:
            break
        _scanned += 1
        try:
            _obj = _ad.get_asset()
        except Exception:
            continue
        if _obj is None:
            continue
        _label = _obj.get_actor_label()
        if "HLODLayer_Merged/" not in _label:
            continue

        _row = {"cell": _label, "materials": [], "textures": []}
        try:
            _comps = list(_obj.get_components_by_class(_u.StaticMeshComponent))
        except Exception as _e:
            _row["error"] = "components: %s" % type(_e).__name__
            _rows.append(_row)
            continue
        for _c in _comps:
            try:
                _n = int(_c.get_num_materials())
            except Exception:
                _n = 0
            _row["n_material_slots"] = _n
            for _i in range(_n):
                try:
                    _m = _c.get_material(_i)
                except Exception as _e:
                    _row["materials"].append(
                        {"slot": _i, "error": type(_e).__name__})
                    continue
                if _m is None:
                    _row["materials"].append({"slot": _i, "material": None})
                    continue
                _md = {"slot": _i, "material": _m.get_path_name(),
                       "class": type(_m).__name__}
                # ONE surface dump, so a failure names what was available
                # instead of asserting absence.
                if not _surface_dumped:
                    _out["material_surface"] = sorted(
                        _k for _k in dir(type(_m))
                        if "texture" in _k.lower() or "param" in _k.lower())
                    _surface_dumped = True
                # Route A: texture parameter values on an instance.
                try:
                    _tpv = list(_m.get_editor_property(
                        "texture_parameter_values"))
                except Exception:
                    _tpv = []
                for _p in _tpv:
                    try:
                        _t = _p.get_editor_property("parameter_value")
                    except Exception:
                        _t = None
                    if _t is not None:
                        _row["textures"].append(_tex_dims(_t))
                _md["n_texture_params"] = len(_tpv)
                # Route B: the library's parameter-name list, if A found
                # nothing.
                if not _tpv:
                    try:
                        _names = list(_u.MaterialEditingLibrary
                                      .get_texture_parameter_names(_m))
                        _md["texture_param_names"] = [str(_x) for _x in _names]
                        for _nm in _names:
                            try:
                                _t = (_u.MaterialEditingLibrary
                                      .get_material_instance_texture_parameter_value(
                                          _m, _nm))
                            except Exception:
                                _t = None
                            if _t is not None:
                                _row["textures"].append(_tex_dims(_t))
                    except Exception as _e:
                        _md["param_names_error"] = type(_e).__name__
                _row["materials"].append(_md)
        _row["n_textures"] = len(_row["textures"])
        _rows.append(_row)

    _out["cells_scanned"] = _scanned
    _out["merged_cells_probed"] = len(_rows)
    _out["rows"] = _rows
    _dims = [t[k] for _r in _rows for t in _r["textures"]
             for k in ("x", "y") if t.get(k)]
    _out["n_dim_samples"] = len(_dims)
    _out["distinct_dims"] = sorted(set(_dims))
    _out["verdict"] = ("NO TEXTURES FOUND" if not _dims
                       else ("PASS" if all(_d == 4096 for _d in _dims)
                             else "FAIL"))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out, default=str))
