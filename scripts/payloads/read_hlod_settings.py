"""Read every HLOD layer's settings back from the ASSETS.

Standing rule 12, and the ruling says it in as many words: read the
settings back from the BUILT HLOD assets, not from the config that asked
for them. An .ini or a recipe records a REQUEST; the layer asset records
what the builder will actually use.

Reports, per HLODLayer asset:
  * the layer type (Instancing / MeshMerge / MeshSimplify / MeshApproximate)
  * cell size and loading range -- the two-level structure
  * the simplification settings on whichever builder this layer uses,
    including the geometric tolerance and the triangle budget
  * texture sizing, and whether it is automatic from draw distance

⛔ AND WHICH LAYER THE WORLD ACTUALLY USES. A perfectly configured
HLODLayer asset that nothing references is an inert field. Every level
actor's `hlod_layer` reference is read (the landscape, its streaming
proxies, foliage and static meshes among them), so "configured" (the
layer assets above) and "in use" (`referenced_by_actors`) are separate
columns. NOTE this reads per-ACTOR references, not the World Partition
runtime hash's HLODSetups list.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False}


def _dump(_o, _keys):
    _d = {}
    for _k in _keys:
        try:
            _v = _o.get_editor_property(_k)
        except Exception as _e:
            _d[_k] = "UNREADABLE: %s" % type(_e).__name__
            continue
        try:
            if hasattr(_v, "get_editor_property") and not isinstance(
                    _v, (str, int, float, bool)):
                _d[_k] = "<%s>" % type(_v).__name__
            else:
                _d[_k] = _v if isinstance(
                    _v, (str, int, float, bool, type(None))) else str(_v)
        except Exception:
            _d[_k] = str(_v)
    return _d


try:
    _eal = _u.EditorAssetLibrary
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(class_paths=[_u.TopLevelAssetPath(
        "/Script/Engine", "HLODLayer")], recursive_paths=True)
    _assets = _ar.get_assets(_f)
    _out["hlod_layer_assets"] = [str(a.package_name) for a in _assets]

    _rows = []
    for _a in _assets:
        _path = str(_a.package_name)
        _o = _eal.load_asset(_path)
        # (removed a dead `... if False else ...` branch that referenced an
        # undefined `a` -- a latent NameError if it were ever flipped on.)
        if _o is None:
            _rows.append({"path": _path,
                          "_error": "load_asset returned None"})
            continue
        _r = {"path": _path, "class": type(_o).__name__}
        _r["properties"] = _dump(_o, [
            "layer_type", "cell_size", "loading_range",
            "is_spatially_loaded", "hlod_builder_class",
            "hlod_builder_settings", "parent_layer",
            "always_loaded", "cell_size_int",
        ])
        # the builder settings object, if this layer carries one
        try:
            _bs = _o.get_editor_property("hlod_builder_settings")
        except Exception:
            _bs = None
        if _bs is not None:
            _r["builder_settings_class"] = type(_bs).__name__
            _r["builder_settings_props"] = sorted(
                n for n in dir(_bs) if not n.startswith("_")
                and n not in ("cast", "get_editor_property",
                              "set_editor_property", "get_class",
                              "get_default_object", "get_fname",
                              "get_full_name", "get_name", "get_outer",
                              "get_outermost", "get_package",
                              "get_path_name", "get_typed_outer",
                              "get_world", "modify", "rename",
                              "reset_editor_property", "static_class",
                              "set_editor_properties",
                              "is_editor_property_overridden",
                              "is_package_external", "call_method",
                              "acquire_editor_element_handle"))
            _r["builder_settings"] = _dump(_bs, _r["builder_settings_props"])
        _rows.append(_r)
    _out["layers"] = _rows

    # ---- which layers the WORLD references ---------------------------
    _sub = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _sub.get_editor_world()
    _out["world"] = _w.get_path_name()
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _used = {}
    for _act in _eas.get_all_level_actors():
        for _p in ("hlod_layer",):
            try:
                _v = _act.get_editor_property(_p)
            except Exception:
                continue
            if _v is not None:
                _used.setdefault(_v.get_path_name(), []).append(
                    type(_act).__name__)
    _out["referenced_by_actors"] = {k: sorted(set(v))[:6]
                                    for k, v in _used.items()}
    # NN13: the probe exists to read HLOD layer settings back from the assets; a
    # run that found zero HLODLayer assets read nothing worth reporting. Refuse.
    _out["ok"] = len(_rows) > 0
    if not _out["ok"]:
        _out["refused"] = ("no HLODLayer assets found in the project -- nothing "
                           "to read back")
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
