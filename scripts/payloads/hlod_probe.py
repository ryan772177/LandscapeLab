"""READ-ONLY: what HLOD setup does this world actually have?

Before assigning anything, find out what is already assigned. The world has
`Alpine8K_HLODLayer_Instanced` and `..._Merged` as layer DEFINITIONS and no
built HLOD actors (measured 2026-09-06), so the question is which layer each
class of actor points at and what type each layer is.

EHLODLayerType (HLODLayer.h:31-39): Instancing, MeshMerge, MeshSimplify,
MeshApproximate ("Approximated Mesh"), Custom, CustomHLODActor.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # ---- world settings default -----------------------------------------
    try:
        _ws = _u.GameplayStatics.get_world_settings(_w)
        _dl = _ws.get_editor_property("default_hlod_layer")
        _out["world_default_hlod_layer"] = _dl.get_path_name() if _dl else None
    except Exception as _e1:
        _out["world_default_hlod_layer_error"] = type(_e1).__name__ + ": " + str(_e1)

    # ---- every HLODLayer asset in the project ---------------------------
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _layers = []
    for _ad in _ar.get_assets_by_class(_u.TopLevelAssetPath("/Script/Engine", "HLODLayer"), True):
        _p = str(_ad.package_name) + "." + str(_ad.asset_name)
        _e = {"path": _p}
        try:
            _o = _u.load_asset(_p)
            _e["layer_type"] = str(_o.get_editor_property("layer_type"))
            _e["cell_size"] = _o.get_editor_property("cell_size")
            _e["loading_range"] = _o.get_editor_property("loading_range")
            _e["is_spatially_loaded"] = bool(_o.get_editor_property("is_spatially_loaded"))
            _pl = _o.get_editor_property("parent_layer")
            _e["parent_layer"] = _pl.get_path_name() if _pl else None
        except Exception as _e2:
            _e["error"] = type(_e2).__name__ + ": " + str(_e2)
        _layers.append(_e)
    _out["hlod_layer_assets"] = _layers

    # ---- what each class of actor points at ------------------------------
    _by_class = {}
    _samples = {}
    for _a in _eas.get_all_level_actors():
        _cn = _a.get_class().get_name()
        if not (isinstance(_a, (_u.LandscapeStreamingProxy, _u.Landscape,
                                _u.InstancedFoliageActor, _u.StaticMeshActor))):
            continue
        _key = _cn
        _by_class[_key] = _by_class.get(_key, 0) + 1
        if _key in _samples:
            continue
        _s = {"actor": _a.get_name()}
        for _prop in ("hlod_layer", "is_spatially_loaded"):
            try:
                _v = _a.get_editor_property(_prop)
                _s[_prop] = (_v.get_path_name() if hasattr(_v, "get_path_name")
                             else bool(_v) if isinstance(_v, bool) else str(_v))
            except Exception as _e3:
                _s[_prop + "_error"] = type(_e3).__name__ + ": " + str(_e3)
        _samples[_key] = _s
    _out["actor_counts"] = _by_class
    _out["hlod_layer_by_class"] = _samples

    # ---- do any built HLOD actors exist? ---------------------------------
    _n = 0
    for _a in _eas.get_all_level_actors():
        if isinstance(_a, _u.WorldPartitionHLOD):
            _n += 1
    _out["existing_hlod_actors_in_editor"] = _n
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
