"""Reach UWorldPartition::RuntimeHash by SUBOBJECT NAME, since the property is
not reflected, and report which HLOD layers this world considers VALID.
READ-ONLY.

WHY BY NAME
    `UWorldPartition::RuntimeHash` is a BARE `UPROPERTY()` at
    `WorldPartition.h:555-556` -- no `EditAnywhere`, no `VisibleAnywhere`, no
    Blueprint access -- and `get_editor_property("runtime_hash")` fails with
    "Failed to find property". The pattern across four properties measured
    today is consistent:

        default_hlod_layer   UPROPERTY(EditAnywhere)            REACHABLE
        world_partition      UPROPERTY(VisibleAnywhere,Instanced) REACHABLE
        persistent_level     UPROPERTY(Transient)               NOT reachable
        runtime_hash         UPROPERTY()                        NOT reachable

    A bare or Transient-only UPROPERTY is serialisation state, not editor-
    facing state, and Python's property path does not expose it. So the object
    is reached as a named subobject of the WorldPartition instead.

WHAT WE ALREADY KNOW WITHOUT THIS PROBE, AND WHAT WE DO NOT
    DEDUCED, soundly: the world is NOT using `UWorldPartitionRuntimeSpatialHash`.
    That class's `IsValidHLODLayer` returns a literal `true`
    (`WorldPartitionRuntimeSpatialHash.h:326`), so the "invalid HLOD layer"
    error could not have been raised under it. Only
    `UWorldPartitionRuntimeHashSet` has a real implementation
    (`WorldPartitionRuntimeHashSet.cpp:377-380`).
    NOT known, and this probe is for it: WHICH layers the HashSet's
    `RuntimePartitions[].HLODSetups[].HLODLayers` actually register. That list
    is the set of layers this world can build, and everything else is inert
    however many actors point at it.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_hash_by_name.py
"""
import json as _json

import unreal as _u

CANDIDATES = [
    "WorldPartitionRuntimeHashSet_0", "WorldPartitionRuntimeHashSet_1",
    "WorldPartitionRuntimeHashSet",
    "WorldPartitionRuntimeSpatialHash_0", "WorldPartitionRuntimeSpatialHash_1",
    "WorldPartitionRuntimeSpatialHash",
    "RuntimeHash", "RuntimeHash_0",
]

_out = {"error": None, "tried": {}}


def _path(_o):
    try:
        return _o.get_path_name() if _o is not None else None
    except Exception:
        return "<unreadable>"


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _ws = _w.get_world_settings()
    _wp = _ws.get_editor_property("world_partition")
    _out["level_path"] = _w.get_path_name()
    _out["world_partition"] = _path(_wp)
    _d = _wp.get_editor_property("default_hlod_layer")
    _out["default_hlod_layer"] = _path(_d)

    _base = _wp.get_path_name() + "."
    _rh = None
    for _name in CANDIDATES:
        try:
            _o = _u.load_object(None, _base + _name)
        except Exception as _e:
            _out["tried"][_name] = "raised " + type(_e).__name__
            continue
        _out["tried"][_name] = _path(_o)
        if _o is not None and _rh is None:
            _rh = _o

    _out["runtime_hash"] = _path(_rh)
    _out["runtime_hash_class"] = (_rh.get_class().get_name()
                                  if _rh is not None else None)

    if _rh is None:
        _out["verdict"] = ("COULD NOT LOOK -- no candidate name resolved. The "
                           "deduction that this is a HashSet still stands on "
                           "the error message, but the VALID LAYER LIST is "
                           "unread and must not be guessed.")
    else:
        _parts = []
        try:
            _rps = _rh.get_editor_property("runtime_partitions")
        except Exception as _e:
            _rps = None
            _out["runtime_partitions_error"] = type(_e).__name__ + ": " + str(_e)
        for _rp in (_rps or []):
            _row = {}
            try:
                _row["name"] = str(_rp.get_editor_property("name"))
            except Exception:
                pass
            try:
                _ml = _rp.get_editor_property("main_layer")
                _row["main_layer_class"] = (_ml.get_class().get_name()
                                            if _ml else None)
            except Exception:
                pass
            _setups = []
            try:
                for _hs in (_rp.get_editor_property("hlod_setups") or []):
                    _s = {}
                    try:
                        _s["name"] = str(_hs.get_editor_property("name"))
                    except Exception:
                        pass
                    try:
                        _s["hlod_layers"] = [
                            _path(_l) for _l in
                            (_hs.get_editor_property("hlod_layers") or [])]
                    except Exception as _e:
                        _s["hlod_layers_error"] = (type(_e).__name__ + ": "
                                                   + str(_e))
                    try:
                        _pl = _hs.get_editor_property("partition_layer")
                        _s["partition_layer_class"] = (
                            _pl.get_class().get_name() if _pl else None)
                    except Exception:
                        pass
                    _setups.append(_s)
            except Exception as _e:
                _row["hlod_setups_error"] = type(_e).__name__ + ": " + str(_e)
            _row["hlod_setups"] = _setups
            _parts.append(_row)
        _out["runtime_partitions"] = _parts

        _valid = []
        for _p in _parts:
            for _s in _p.get("hlod_setups", []):
                _valid.extend(_s.get("hlod_layers", []) or [])
        _out["VALID_HLOD_LAYERS"] = sorted(set(_v for _v in _valid if _v))
        _out["default_is_valid"] = bool(
            _out.get("default_hlod_layer") in _out["VALID_HLOD_LAYERS"])
        _out["verdict"] = ("read OK" if _parts else
                           "hash reached but NO runtime partitions read")
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
