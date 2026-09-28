"""Does this world author any custom World Partition runtime grids?

`wp.Runtime.OverrideRuntimeLoadingRange -grid=[Name]` is an EXACT FName lookup
(WorldPartitionSubsystem.cpp:563-571 -- no NAME_None wildcard), and the name it
is matched against is `FSpatialHashStreamingGrid::GridName`
(WorldPartitionRuntimeSpatialHash.cpp:187).

When a world authors no custom grids the engine creates one default grid named
"MainGrid" (WorldPartitionRuntimeSpatialHash.cpp:1387-1388). Custom grids are
authored by placing `ASpatialHashRuntimeGridInfo` actors. So the question
"which grid" reduces to "are there any of those actors", which is answerable
without guessing.

Run via: python scripts/ue_exec.py scripts/payloads/bench_grid_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None, "grid_info_actors": [], "count": 0}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _eas.get_all_level_actors():
        if isinstance(_a, _u.SpatialHashRuntimeGridInfo):
            _e = {"name": _a.get_name()}
            try:
                _e["label"] = _a.get_actor_label()
            except Exception:
                pass
            try:
                _g = _a.get_editor_property("grid_settings")
                _e["grid_settings"] = str(_g)[:300]
            except Exception as _ge:
                _e["grid_settings_error"] = type(_ge).__name__ + ": " + str(_ge)
            _out["grid_info_actors"].append(_e)
    _out["count"] = len(_out["grid_info_actors"])
    _out["verdict"] = (
        "no custom grids authored -> the world uses the engine default grid, "
        "GridName 'MainGrid' (WorldPartitionRuntimeSpatialHash.cpp:1387-1388)"
        if _out["count"] == 0 else
        "CUSTOM GRIDS PRESENT -- read their names before overriding a range")
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-700:]

print("__LL__" + _json.dumps(_out))
