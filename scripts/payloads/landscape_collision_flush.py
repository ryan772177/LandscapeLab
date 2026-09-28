"""Flush the deferred landscape collision update, SAME SESSION as the push.

R1 ADOPTION step 4: the edit-layer import path DEFERS collision
(`LandscapeEditInterface.cpp:438-440`); the dirty region lives in MEMORY
and dies with the editor session, so this must run in the session that
pushed (proven 2026-08-06 — the later-session flush is a measured no-op).

The call's return is NOT evidence (a landscape mutation returning "ok"
and moving nothing is a recorded failure mode, three instances) — the
exit gate is `check_collision_truth.py --n 100` EXIT 0, run by the
caller AFTER this. This payload only reports what it called, on what.

Non-mutating aside from the flush itself. Refuses off /Game/Alpine8K
(standing rule 11) and on any Landscape-actor count other than one
(standing rule 8 — identity by class census, not label).
"""
import json as _json
import unreal as _u

_out = {"ok": False, "world": None, "landscape": None, "called": False,
        "error": None}
try:
    _w = _u.get_editor_subsystem(
        _u.UnrealEditorSubsystem).get_editor_world()
    _out["world"] = _w.get_path_name()
    if "/Game/Alpine8K" not in _out["world"]:
        raise RuntimeError("REFUSE (rule 11): world is %s" % _out["world"])
    _lands = list(_u.GameplayStatics.get_all_actors_of_class(
        _w, _u.Landscape))
    _out["landscape_count"] = len(_lands)
    if len(_lands) != 1:
        raise RuntimeError("REFUSE (rule 8): expected exactly 1 Landscape "
                           "actor, found %d" % len(_lands))
    _land = _lands[0]
    _out["landscape"] = _land.get_actor_label()
    _land.force_layers_full_update()
    _out["called"] = True
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:400]
print("__LL__" + _json.dumps(_out, default=str))
