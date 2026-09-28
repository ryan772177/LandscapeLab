"""dump_hlod_landscape_layer.py -- the Landscape HLOD layer, exhaustively.

READ-ONLY. Audit item 5: the layer asset's properties after the
2026-09-13 write, read from a freshly loaded asset.

⭐ WHAT MAKES THIS "FRESHLY LOADED", STATED SO IT IS NOT ASSUMED.
The 09-13 write happened in a DIFFERENT editor process, which has since
exited. This process was launched minutes ago and has never touched the
asset. So the load below is a load FROM DISK by construction -- the
strongest form of the read-back standard, stronger than any in-process
unload/reload, because no handle from the writing session survives to
be read by mistake.

⛔ `dir(unreal.HLODLayer)` LISTS NO PROPERTIES AT ALL. Enumerated this
session: 23 names, ALL of them method descriptors (method_descriptor 17,
methodwithclosure_descriptor 3, builtin_function_or_method 3), ZERO
property descriptors. So a dir()-driven walk returns `str(obj)` and a
dir()-driven audit concludes "HLOD settings expose zero properties to
Python" -- which is how that false claim was reached TWICE, by two
probes that were one measurement (NN0).

The properties are reachable by NAME through `get_editor_property`, and
the names are ground truth in the header, not in Python:
  Engine/Source/Runtime/Engine/Public/WorldPartition/HLOD/HLODLayer.h
  :112 LayerType   :116 HLODBuilderClass   :119 HLODBuilderSettings
  :123 bIsSpatiallyLoaded  :127 CellSize   :131 LoadingRange
  :135 ParentLayer :139 LinkedLayer :143 HLODActorClass
  :147 HLODModifierClass   :155 bForceRayTracingFarField
  :164 EditorLoadingBehavior

⛔ AND THE ONE THAT CHANGES A VERDICT: at :172/:174/:176 the header
declares MeshMergeSettings, MeshSimplifySettings and
MeshApproximationSettings as **_DEPRECATED** on UHLODLayer in 5.8. The
live settings hang off HLODBuilderSettings (:119), a UObject selected
by HLODBuilderClass (:116). Both names are dumped so the audit can see
which one carries the values -- and the deprecated trio is read too,
because "the deprecated struct is empty" is itself the evidence that
the live path is the one in force.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False,
        "_freshness": "loaded from disk in a process launched after the "
                      "writing process exited; no in-process handle "
                      "from the write survives",
        "_name_source": "Engine/Source/Runtime/Engine/Public/"
                        "WorldPartition/HLOD/HLODLayer.h (5.8.1) -- "
                        "dir() exposes NO property descriptors on "
                        "HLODLayer, so names cannot come from Python"}

_SCALAR = (str, int, float, bool, type(None))

# From the header, snake_cased as the Python binding expects.
_LAYER_PROPS = [
    "layer_type", "hlod_builder_class", "hlod_builder_settings",
    "is_spatially_loaded", "cell_size", "loading_range",
    "parent_layer", "linked_layer", "hlod_actor_class",
    "hlod_modifier_class", "force_ray_tracing_far_field",
    "editor_loading_behavior",
]
_DEPRECATED_PROPS = [
    "mesh_merge_settings", "mesh_simplify_settings",
    "mesh_approximation_settings", "hlod_material", "always_loaded",
]


def _walk(_o, _depth=0):
    """Plain-JSON a value, descending INTO structs.

    Structs (StructBase) DO generate property descriptors, unlike the
    UObject above, so dir() works from here down. The depth limit at 5
    stops at engine plumbing, not at settings.
    """
    if isinstance(_o, _SCALAR):
        return _o
    if _depth > 5:
        return "<%s: depth limit>" % type(_o).__name__
    if isinstance(_o, (_u.Name, _u.Text)):
        return str(_o)
    if isinstance(_o, (_u.Array, _u.Set, list, tuple, set)):
        return [_walk(_x, _depth + 1) for _x in _o]
    if isinstance(_o, _u.Map):
        return {str(_k): _walk(_v, _depth + 1) for _k, _v in _o.items()}
    if isinstance(_o, _u.StructBase):
        _d = {"__struct__": type(_o).__name__}
        for _n in sorted(n for n in dir(type(_o)) if not n.startswith("_")):
            _desc = getattr(type(_o), _n, None)
            if callable(_desc) or "method" in type(_desc).__name__:
                continue
            try:
                _d[_n] = _walk(getattr(_o, _n), _depth + 1)
            except Exception as _e:
                _d[_n] = "UNREADABLE: %s" % type(_e).__name__
        return _d
    if isinstance(_o, _u.Object):
        # A UObject nested here (HLODBuilderSettings) has the same
        # no-descriptors problem, so enumerate its own struct members
        # the same way: by name, from whatever it will answer to.
        _d = {"__object__": type(_o).__name__,
              "__path__": _o.get_path_name()}
        for _n in ("mesh_merge_settings", "mesh_approximation_settings",
                   "mesh_simplify_settings", "mesh_proxy_settings",
                   "instancing_settings", "destruction_settings"):
            try:
                _v = _o.get_editor_property(_n)
            except Exception:
                continue
            _d[_n] = _walk(_v, _depth + 1)
        return _d
    if isinstance(_o, type):
        return _o.__name__
    return str(_o)


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(class_paths=[_u.TopLevelAssetPath(
        "/Script/Engine", "HLODLayer")], recursive_paths=True)
    _all = [str(_a.package_name) for _a in _ar.get_assets(_f)]
    _out["all_hlod_layer_assets"] = sorted(_all)

    # Identify by signature and report EVERY candidate rather than
    # silently taking the first (conduct rule 8).
    _cands = sorted(_p for _p in _all
                    if "landscape" in _p.lower() and _p.startswith("/Game/"))
    _out["landscape_layer_candidates"] = _cands
    if len(_cands) != 1:
        _out["error"] = ("expected exactly 1 project Landscape HLOD layer, "
                         "found %d" % len(_cands))
    else:
        _path = _cands[0]
        _L = _u.EditorAssetLibrary.load_asset(_path)
        _out["landscape_layer_path"] = _path
        _out["landscape_layer_class"] = _L.get_class().get_name()

        _props = {}
        _missing = []
        for _n in _LAYER_PROPS:
            try:
                _props[_n] = _walk(_L.get_editor_property(_n))
            except Exception as _e:
                _missing.append(_n)
                _props[_n] = "UNREADABLE: %s: %s" % (type(_e).__name__, _e)
        _out["properties"] = _props
        _out["names_that_would_not_read"] = _missing

        _dep = {}
        for _n in _DEPRECATED_PROPS:
            try:
                _dep[_n] = _walk(_L.get_editor_property(_n))
            except Exception as _e:
                _dep[_n] = "UNREADABLE: %s" % type(_e).__name__
        _out["deprecated_on_layer_in_5_8"] = _dep

        # Is it REFERENCED? A perfectly configured layer nothing points
        # at is an inert field, and the audit is about what is in force.
        _refs = []
        _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
        for _a in _eas.get_all_level_actors():
            for _key in ("hlod_layer", "default_hlod_layer"):
                try:
                    _l = _a.get_editor_property(_key)
                except Exception:
                    continue
                if _l is not None:
                    _refs.append({"actor": _a.get_actor_label(),
                                  "class": _a.get_class().get_name(),
                                  "key": _key,
                                  "layer": _l.get_path_name()})
        _out["actors_naming_an_hlod_layer"] = _refs[:40]
        _out["n_actors_naming_an_hlod_layer"] = len(_refs)
        _out["n_actors_naming_THIS_layer"] = sum(
            1 for _r in _refs if _path in _r["layer"])

        # The world's OWN list, which is a different instrument than
        # walking actors: WorldPartition's runtime hash carries the
        # layers it will actually build.
        try:
            _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
            _ws = _ues.get_editor_world().get_world_settings()
            _dl = _ws.get_editor_property("default_hlod_layer")
            _out["world_default_hlod_layer"] = (
                _dl.get_path_name() if _dl else None)
        except Exception as _e:
            _out["world_default_hlod_layer"] = "UNREADABLE: %s" % type(_e).__name__
        _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
