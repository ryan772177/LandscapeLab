"""Task 5 read-back: point sample_census's HLOD reader at OUR layers.

⭐ WHY THIS AND NOT MY OWN PROBE. Last session I concluded the
MeshApproximate / MeshMerge settings are not exposed to Python, having
tested 25 candidate names and `dir()` on the class and the CDO. The
census reader tries names I did NOT test -- `mesh_approximation_settings`,
`mesh_merge_settings`, `mesh_simplify_settings`, `material_settings` -- as
NESTED properties of the builder-settings object. If any of those answer, my
conclusion was too strong and this is the correction.

So: the census's own logic, applied to this project's layers, printing
the EXACT property names as the reader sees them. Whatever comes back is
the Task 5 read-back; whatever does not is recorded as unexposed, by
name, rather than as a general claim.

READ-ONLY. Reproduces `sec_hlod_layers` rather than importing it, because
the census file lives under research/ and is not on the editor's path. The
logic is a HAND COPY (TOP/NESTED lists), so it can DRIFT from
research/census/sample_census.py -- treat "verbatim" as intent, not a guarantee;
diff against the source if the census reader changes.
"""
import json as _json
import traceback as _tb

import unreal as _u

OURS = ("/Game/Alpine8K_HLODLayer_Instanced",
        "/Game/Alpine8K_HLODLayer_Merged",
        "/Game/Alpine8K_HLODLayer_FoliageApprox",
        "/Game/Alpine8K_HLODLayer_Landscape")

# Verbatim from research/census/sample_census.py sec_hlod_layers()
TOP = ["layer_type", "cell_size", "loading_range", "is_spatially_loaded",
       "parent_layer", "force_ray_tracing_far_field",
       "editor_loading_behavior"]
NESTED = ("mesh_approximation_settings", "mesh_merge_settings",
          "mesh_simplify_settings", "material_settings")


def _jsonable(v):
    if isinstance(v, (int, float, bool, str, type(None))):
        return v
    try:
        return v.get_path_name()
    except Exception:
        return str(v)


def _all_props(obj):
    d = {}
    for n in dir(obj):
        if n.startswith("_") or callable(getattr(obj, n, None)):
            continue
        try:
            d[n] = _jsonable(obj.get_editor_property(n))
        except Exception:
            pass
    return d


_out = {"ok": False, "_reader": "sample_census.sec_hlod_layers, verbatim"}
try:
    _eal = _u.EditorAssetLibrary
    _res = {}
    for _p in OURS:
        if not _eal.does_asset_exist(_p):
            _res[_p] = {"_error": "asset does not exist"}
            continue
        _L = _eal.load_asset(_p)
        _rec = {}
        for _n in TOP:
            try:
                _rec[_n] = _jsonable(_L.get_editor_property(_n))
            except Exception as _e:
                _rec[_n] = "UNREADABLE: %s" % type(_e).__name__
        try:
            _bs = _L.get_editor_property("hlod_builder_settings")
            _rec["builder_settings_class"] = _bs.get_class().get_name()
            _rec["builder_settings"] = _all_props(_bs)
            _rec["builder_settings_property_names"] = sorted(
                _rec["builder_settings"].keys())
            _nested_found = {}
            for _inner in NESTED:
                try:
                    _sub = _bs.get_editor_property(_inner)
                except Exception as _e:
                    _nested_found[_inner] = "ABSENT (%s)" % type(_e).__name__
                    continue
                if _sub is None:
                    # present-but-None is not an existing empty struct.
                    _nested_found[_inner] = "ABSENT (None value)"
                    continue
                try:
                    _props = _all_props(_sub)
                    _nested_found[_inner] = {
                        "struct": type(_sub).__name__,
                        "property_names": sorted(_props.keys()),
                        "values": _props,
                    }
                except Exception as _e:
                    # per-name guard, so one bad struct does not suppress the
                    # rest of the NESTED read-back for this layer.
                    _nested_found[_inner] = "READ-ERROR: %s" % type(_e).__name__
            _rec["nested"] = _nested_found
        except Exception as _e:
            _rec["builder_settings_error"] = str(_e)[:200]
        _res[_p] = _rec
    _out["layers"] = _res
    _read_ok = sum(1 for r in _res.values() if "_error" not in r)
    _out["layers_read"] = _read_ok
    # NN13: ok:True over zero readable layers is success wearing silence's
    # clothes -- require at least one layer actually read.
    _out["ok"] = _read_ok > 0
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
