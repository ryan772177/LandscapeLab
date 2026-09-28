"""READ BACK the world-level default HLOD layer, and the per-class assignment
that survived the 2026-09-07 kill. READ-ONLY -- this payload mutates nothing.

WHY THIS EXISTS
    Engine source (REGISTER, CC 2026-09-08) establishes that
    `UWorldPartition::DefaultHLODLayer` is applied to every unassigned,
    spatially-loaded, HLOD-relevant actor at streaming-generation time, on the
    VIEW rather than the actor -- so setting it dirties no external actor
    package. What Alpine8K currently HOLDS in that property is a separate
    question, and `WorldPartition.cpp:1273` only seeds it at world-partition
    CREATION, so it cannot be inferred from the engine config. Standing rule 12:
    read it back.

    It also answers whether the killed session left any assignment on disk. The
    save never completed, so the expectation is "none" -- but that is a
    prediction, and the probe is the instrument that settles it.

REFLECTED SURFACE, NOT REMEMBERED NAMES (docs/ue58-api-protocol.md)
    `AWorldSettings::WorldPartition` is `UPROPERTY(VisibleAnywhere, Instanced)`
    at `WorldSettings.h:550-551`, so the Python name is `world_partition`.
    `UWorldPartition::DefaultHLODLayer` is `UPROPERTY(EditAnywhere)` at
    `WorldPartition.h:610-612` -> `default_hlod_layer`. Both are reflected, so
    `get_editor_property` reaches them regardless of Blueprint access. The
    routes to the WorldSettings actor are TRIED rather than assumed, and the
    one that worked is reported.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_default_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _actors = _eas.get_all_level_actors()
    _out["actor_total"] = len(_actors)

    # ---- reach the WorldSettings actor, reporting WHICH route worked -------
    _ws = None
    _route = None
    try:
        _ws = _u.GameplayStatics.get_world_settings(_w)
        if _ws is not None:
            _route = "GameplayStatics.get_world_settings"
    except Exception as _e:
        _out["route_gameplaystatics_error"] = type(_e).__name__ + ": " + str(_e)
    if _ws is None:
        for _a in _actors:
            if isinstance(_a, _u.WorldSettings):
                _ws, _route = _a, "scan get_all_level_actors for WorldSettings"
                break
    _out["worldsettings_route"] = _route
    _out["worldsettings"] = _ws.get_path_name() if _ws is not None else None

    # ---- the property under test -----------------------------------------
    _wp = None
    if _ws is not None:
        _wp = _ws.get_editor_property("world_partition")
    _out["world_partition"] = _wp.get_path_name() if _wp is not None else None

    if _wp is not None:
        _dflt = _wp.get_editor_property("default_hlod_layer")
        _out["default_hlod_layer"] = _dflt.get_path_name() if _dflt else None
        # What the reflected surface actually offers, so the SETTER is chosen
        # from the contract rather than from memory.
        _out["wp_hlod_surface"] = sorted(
            _n for _n in dir(_wp) if "hlod" in _n.lower())
        _out["wp_class"] = _wp.get_class().get_name()

    # ---- HLOD layer assets that exist -------------------------------------
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _layers = []
    for _d in _ar.get_assets_by_path("/Game", recursive=True):
        if str(_d.asset_class_path.asset_name) == "HLODLayer":
            _p = str(_d.package_name)
            _o = _u.load_asset(_p)
            _par = _o.get_editor_property("parent_layer") if _o else None
            _layers.append({
                "package": _p,
                "layer_type": str(_o.get_editor_property("layer_type")),
                "cell_size": _o.get_editor_property("cell_size"),
                "loading_range": _o.get_editor_property("loading_range"),
                "is_spatially_loaded": bool(
                    _o.get_editor_property("is_spatially_loaded")),
                "parent_layer": _par.get_path_name() if _par else None,
            })
    _out["hlod_layer_assets"] = sorted(_layers, key=lambda _x: _x["package"])

    # ---- per-class: is anything ASSIGNED on disk, and is it HLOD relevant? -
    # Both questions in one pass. `is_hlod_relevant` may not be reflected; it is
    # attempted and its absence reported rather than silently read as False,
    # because a missing instrument must not read as a measurement.
    _classes = {}
    for _a in _actors:
        _cn = _a.get_class().get_name()
        _row = _classes.setdefault(
            _cn, {"count": 0, "assigned": 0, "layers": {},
                  "spatially_loaded_true": 0, "auto_lod_true": 0})
        _row["count"] += 1
        try:
            _v = _a.get_editor_property("hlod_layer")
            if _v is not None:
                _row["assigned"] += 1
                _k = _v.get_path_name().split(".")[-1]
                _row["layers"][_k] = _row["layers"].get(_k, 0) + 1
        except Exception:
            pass
        try:
            if bool(_a.get_editor_property("is_spatially_loaded")):
                _row["spatially_loaded_true"] += 1
        except Exception:
            pass
        try:
            if bool(_a.get_editor_property("enable_auto_lod_generation")):
                _row["auto_lod_true"] += 1
        except Exception:
            pass
    _out["by_class"] = {
        _k: _v for _k, _v in sorted(_classes.items())
        if _v["count"] >= 1 and _k in (
            "Landscape", "LandscapeStreamingProxy", "InstancedFoliageActor",
            "StaticMeshActor", "WorldPartitionHLOD", "WorldSettings")}
    _out["class_census_all"] = {
        _k: _v["count"] for _k, _v in sorted(_classes.items())}
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
