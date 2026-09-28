"""Readiness probe for the O-7 pilot: report the loaded world and the total
level-actor count, plus the per-target-class counts the pilot will iterate.

Non-mutating. Confirms (a) the editor serves the port, (b) the world is
/Game/Alpine8K, and (c) World Partition has the actors loaded (the pilot
iterates get_all_level_actors, so a half-streamed world would undercount).
Run twice; a stable count between runs means streaming has settled.
"""
import json as _json
import unreal as _u

_out = {"ok": False, "error": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()
    _n = {"total": 0, "foliage": 0, "landscape": 0, "props": 0}
    for _a in _eas.get_all_level_actors():
        _n["total"] += 1
        if isinstance(_a, _u.InstancedFoliageActor):
            _n["foliage"] += 1
        elif isinstance(_a, (_u.LandscapeStreamingProxy, _u.Landscape)):
            _n["landscape"] += 1
        elif isinstance(_a, _u.StaticMeshActor):
            _n["props"] += 1
    _out["counts"] = _n
    _out["ok"] = True
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
