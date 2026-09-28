"""probe_wp_default_hlod.py -- the world's DefaultHLODLayer. READ-ONLY.

Closes the gap the reference probe opened. 0 of 4,339 actors name an
HLOD layer (measured, 0 read errors), so per-actor assignment is not how
this world gets its HLOD. The other channel is the WORLD's default, and
it is NOT on WorldSettings -- which is why reading
`world_settings.default_hlod_layer` raised:

  Engine/Source/Runtime/Engine/Public/WorldPartition/WorldPartition.h
  :612  TObjectPtr<class UHLODLayer> DefaultHLODLayer;   (on UWorldPartition)
  :343  UHLODLayer* GetDefaultHLODLayer() const

So the answer to "is Alpine8K_HLODLayer_Landscape in force" is here, not
on the actors. Enumerates the route to the WorldPartition object rather
than guessing it.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False}

try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _ws = _w.get_world_settings()
    _out["world"] = _w.get_path_name()

    # Enumerate the reflected surface in ONE pass instead of guessing
    # an accessor at a time (ue-api-resolution).
    _out["worldsettings_names_with_partition"] = sorted(
        n for n in dir(type(_ws)) if "partition" in n.lower())
    _out["unreal_names_with_worldpartition"] = sorted(
        n for n in dir(_u) if "worldpartition" in n.lower())[:30]

    _wp = None
    for _route in ("world_partition",):
        try:
            _wp = _ws.get_editor_property(_route)
            _out["route"] = "WorldSettings.%s" % _route
            break
        except Exception as _e:
            _out["route_%s_failed" % _route] = "%s: %s" % (
                type(_e).__name__, _e)
    if _wp is None:
        try:
            _wp = _u.WorldPartitionBlueprintLibrary.get_world_partition()
            _out["route"] = "WorldPartitionBlueprintLibrary.get_world_partition()"
        except Exception as _e:
            _out["route_bplib_failed"] = "%s: %s" % (type(_e).__name__, _e)

    if _wp is None:
        _out["error"] = "could not reach the UWorldPartition object"
    else:
        _out["world_partition_class"] = type(_wp).__name__
        for _n in ("default_hlod_layer", "enable_streaming",
                   "runtime_hash", "server_streaming_mode"):
            try:
                _v = _wp.get_editor_property(_n)
            except Exception as _e:
                _out[_n] = "RAISED: %s: %s" % (type(_e).__name__, _e)
                continue
            if _v is None:
                _out[_n] = None
            elif isinstance(_v, (str, int, float, bool)):
                _out[_n] = _v
            elif hasattr(_v, "get_path_name"):
                _out[_n] = _v.get_path_name()
            else:
                _out[_n] = str(_v)
        _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
