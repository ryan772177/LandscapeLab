"""Which runtime hash does this world use, and which HLOD layers does it
consider VALID? READ-ONLY.

WHY, AND IT IS THE CAUSE OF A ZERO-ACTOR BUILD
    2026-09-08, `-SetupHLODs` reported `#### World contains 0 HLOD actors ####`
    after logging, once per actor, thousands of times:

        Actor /Game/Alpine8K.City_St_622 has an invalid HLOD layer
        /Game/Alpine8K_HLODLayer_Landscape.Alpine8K_HLODLayer_Landscape

    That message is `WorldPartitionStreamingGenerationLogErrorHandler.cpp:143`,
    raised from `WorldPartitionStreamingGeneration.cpp:2037` when
    `IsValidHLODLayer(RuntimeGrid, HLODLayer)` is false. There are three
    implementations and they do not agree:

        UWorldPartitionRuntimeSpatialHash::IsValidHLODLayer
            WorldPartitionRuntimeSpatialHash.h:326   returns literal TRUE
        UWorldPartitionRuntimeHash::IsValidHLODLayer  (base)
            WorldPartitionRuntimeHash.h:225          returns literal FALSE
        UWorldPartitionRuntimeHashSet::IsValidHLODLayer
            WorldPartitionRuntimeHashSet.cpp:377-380 the only REAL one

    The HashSet one resolves through
    `ResolveRuntimePartitionForHLODLayer` (:388-435): it finds the runtime
    partition for the actor's grid, then searches that partition's
    `HLODSetups` for an entry whose `HLODLayers` array CONTAINS the layer.
    Not found -> nullptr -> invalid -> the actor is dropped from HLOD.

    **So an HLOD layer is not valid because it exists and is assigned. It is
    valid because a runtime partition REGISTERS it.** A free-standing
    `UHLODLayer` asset that nothing lists is inert no matter how many actors
    point at it -- which is what `Alpine8K_HLODLayer_Landscape` is.

    A SECOND THING TO CHECK WHILE WE ARE HERE. The research REGISTER's
    "three failed force-load levers" recorded lever 2 as
    `wp.Runtime.OverrideRuntimeLoadingRange -grid=MainGrid`, with the grid name
    derived as the engine default from `WorldPartitionRuntimeSpatialHash.cpp`.
    If this world's hash is a HashSet rather than a SpatialHash, that grid name
    was resolved against the wrong class and the lever was aimed at nothing.
    This probe reports the class, so that elimination can be re-judged instead
    of standing on an assumption.

REFLECTED NAMES, from WorldPartitionRuntimeHashSet.h
    UWorldPartition::RuntimeHash              WorldPartition.h:556
    UWorldPartitionRuntimeHashSet::RuntimePartitions   :262-263
    FRuntimePartitionDesc::Name / MainLayer / HLODSetups  :71-85
    FRuntimePartitionHLODSetup::HLODLayers / PartitionLayer  :39-48

Run via: python scripts/ue_exec.py scripts/payloads/hlod_runtimehash_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None}


def _path(_o):
    try:
        return _o.get_path_name() if _o is not None else None
    except Exception:
        return "<unreadable>"


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _ws = _w.get_world_settings()
    _wp = _ws.get_editor_property("world_partition")
    _out["world_partition"] = _path(_wp)

    _d = _wp.get_editor_property("default_hlod_layer")
    _out["default_hlod_layer"] = _path(_d)

    _rh = _wp.get_editor_property("runtime_hash")
    _out["runtime_hash"] = _path(_rh)
    _out["runtime_hash_class"] = (_rh.get_class().get_name()
                                  if _rh is not None else None)
    # THE decisive field: which IsValidHLODLayer is in play.
    _out["_which_isvalid"] = {
        "WorldPartitionRuntimeSpatialHash": "always TRUE -- any layer passes",
        "WorldPartitionRuntimeHashSet": "REAL -- layer must be in a partition's HLODSetups",
        "other": "base returns FALSE -- nothing would ever build",
    }

    _parts = []
    if _rh is not None:
        try:
            _rps = _rh.get_editor_property("runtime_partitions")
        except Exception as _e:
            _rps = None
            _out["runtime_partitions_error"] = type(_e).__name__ + ": " + str(_e)
        for _rp in (_rps or []):
            _row = {}
            for _f in ("name", "class"):
                try:
                    _row[_f] = str(_rp.get_editor_property(_f))
                except Exception:
                    pass
            try:
                _ml = _rp.get_editor_property("main_layer")
                _row["main_layer"] = _path(_ml)
                _row["main_layer_class"] = (_ml.get_class().get_name()
                                            if _ml else None)
            except Exception as _e:
                _row["main_layer_error"] = type(_e).__name__
            _setups = []
            try:
                for _hs in (_rp.get_editor_property("hlod_setups") or []):
                    _s = {}
                    try:
                        _s["name"] = str(_hs.get_editor_property("name"))
                    except Exception:
                        pass
                    try:
                        _s["hlod_layers"] = [_path(_l) for _l in
                                             (_hs.get_editor_property("hlod_layers") or [])]
                    except Exception as _e:
                        _s["hlod_layers_error"] = type(_e).__name__ + ": " + str(_e)
                    try:
                        _pl = _hs.get_editor_property("partition_layer")
                        _s["partition_layer"] = _path(_pl)
                        _s["partition_layer_class"] = (_pl.get_class().get_name()
                                                       if _pl else None)
                    except Exception as _e:
                        _s["partition_layer_error"] = type(_e).__name__
                    _setups.append(_s)
            except Exception as _e:
                _row["hlod_setups_error"] = type(_e).__name__ + ": " + str(_e)
            _row["hlod_setups"] = _setups
            _parts.append(_row)
    _out["runtime_partitions"] = _parts

    # Flatten: exactly which layers this world will accept.
    _valid = []
    for _p in _parts:
        for _s in _p.get("hlod_setups", []):
            _valid.extend(_s.get("hlod_layers", []) or [])
    _out["VALID_HLOD_LAYERS"] = sorted(set(_valid))
    _out["default_is_valid"] = bool(
        _out.get("default_hlod_layer") in _out["VALID_HLOD_LAYERS"])
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
