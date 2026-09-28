"""probe_hlod_actor_surface.py -- what can Python actually read off an HLOD cell?

READ-ONLY, ONE PASS. `source_actors` raised on all 12 probe cells, and
the reason matters: `SourceActors` is declared `private` under
`WITH_EDITORONLY_DATA` with a bare `UPROPERTY()` and no EditAnywhere or
BlueprintReadWrite (`HLODActor.h:214-216`). A bare private UPROPERTY may
or may not be reachable through `get_editor_property`.

Rather than guess a second name, this enumerates: every candidate
property from the header is tried and the OUTCOME recorded, plus the
method surface. That is the cheap reliable move -- burn one round trip
on the whole surface instead of one guess at a time.
"""
import json as _json
import traceback as _tb

import unreal as _u

# Names from HLODActor.h:214-245, snake_cased.
_CANDIDATES = [
    "source_actors", "input_stats", "hlod_bounds", "min_visible_distance",
    "hlod_stats", "hlod_build_report", "hlod_resources_package_path",
    "lod_level", "require_warmup", "hlod_rebuild_policy_data_set",
    "subactors_hlod_layer", "sub_actors_hlod_layer",
    "hlod_sub_actors", "source_cell_name", "source_cell",
]

_out = {"ok": False}
try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells"] = len(_hlods)
    _ad = _hlods[0]
    _obj = _ad.get_asset()
    _out["sample_package"] = str(_ad.package_name)
    _out["sample_class"] = _obj.get_class().get_name() if _obj else None
    if _obj is None:
        _out["error"] = "get_asset() returned None on the first cell"
    else:
        _out["label"] = _obj.get_actor_label()
        _props = {}
        for _n in _CANDIDATES:
            try:
                _v = _obj.get_editor_property(_n)
            except Exception as _e:
                _props[_n] = "RAISED: %s" % str(_e)[:110]
                continue
            if _v is None:
                _props[_n] = None
            elif isinstance(_v, (str, int, float, bool)):
                _props[_n] = _v
            else:
                _props[_n] = "<%s>" % type(_v).__name__
        _out["properties"] = _props

        # The method surface, in case the data is behind an accessor.
        _out["methods_of_interest"] = sorted(
            _n for _n in dir(type(_obj))
            if any(_k in _n.lower() for _k in
                   ("source", "hlod", "stat", "input", "subactor")))

        # If input_stats resolved, it may carry the referenced-asset
        # counts, which would answer the content question without the
        # source list at all.
        _is = _props.get("input_stats")
        if isinstance(_is, str) and _is.startswith("<"):
            try:
                _isv = _obj.get_editor_property("input_stats")
                _sub = {}
                for _n in sorted(_k for _k in dir(type(_isv))
                                 if not _k.startswith("_")):
                    _d = getattr(type(_isv), _n, None)
                    if callable(_d) or "method" in type(_d).__name__:
                        continue
                    try:
                        _sub[_n] = str(getattr(_isv, _n))[:200]
                    except Exception:
                        pass
                _out["input_stats_fields"] = _sub
            except Exception as _e:
                _out["input_stats_error"] = str(_e)[:200]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
