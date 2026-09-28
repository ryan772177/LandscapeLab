"""Residency census INSIDE the PIE world, appended to a JSONL.

Run by MRQ itself, not by remote exec: `bench_capture` puts

    py "<abs path to this file>"

into the console-variable setting's `end_console_commands`, so it executes on
the PIE game thread when each shot finishes. Remote exec cannot do this job --
it runs on the game thread too, and MRQ owns the game thread for the whole
render (proven 2026-09-05: not one LogPython line appeared during a capture).

WHY AT SHOT END. `end_console_commands` fires after the shot's frames are
rendered and before PIE tears down, which is the moment that answers the
question that matters: was the world resident WHEN THE FRAME WAS TAKEN. During
a static shot residency only grows, so end-of-shot is a lower bound on what the
frame saw -- and a lower bound is the safe direction for a gate.

THE CENSUS IS THE PROJECT'S EXISTING ONE, moved to the game world.
`measure_frame_cost.py:265-280` counts `LandscapeStreamingProxy` and
`Landscape` actors and sums `get_components_by_class(LandscapeComponent)`.
R-FRAMECOST REJECTED records why it must be `get_components_by_class` and NOT
the `landscape_components` UPROPERTY: that property returns 0 on a fully loaded
world, and the resulting gate prints "THE WORLD WAS NOT THERE" about a world
that was entirely there. "I could not count" is kept distinct from "it was not
there", for the same reason.
"""
import json as _json
import os as _os
import time as _time

import unreal as _u

OUT = _os.environ.get("LL_BENCH_RESIDENCY_OUT") or __OUT_PATH__

_rec = {"error": None, "when": _time.time(), "world": None,
        "landscape_actors": 0, "proxies": 0, "components": 0,
        "components_unreadable": 0, "foliage_actors": 0,
        "foliage_instances": 0, "view_target": None, "is_pie": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_game_world()
    if _w is None:
        raise RuntimeError("get_game_world returned None -- not in PIE")
    _rec["world"] = _w.get_path_name()
    _rec["is_pie"] = "UEDPIE" in _rec["world"]

    # Where the camera is, so residency can be measured AROUND IT. A whole-world
    # census answers "is everything here", which is the right question for a
    # truth frame and the WRONG one for a near-field shot: a dolly through the
    # town does not need cells 4 km away, and refusing it for their absence
    # would be a gate that fails correct work.
    _cam = None
    try:
        _pc0 = _u.GameplayStatics.get_player_controller(_w, 0)
        _vt0 = _pc0.get_view_target() if _pc0 else None
        if _vt0:
            _cam = _vt0.get_actor_location()
    except Exception:
        pass
    _near_m = __NEAR_M__
    _near_cm = float(_near_m) * 100.0
    _rec["near_radius_m"] = _near_m
    _rec["near_components"] = 0
    _rec["near_proxies"] = 0
    _rec["near_foliage_instances"] = 0

    def _within(_actor):
        if _cam is None:
            return False
        _p = _actor.get_actor_location()
        _dx = _p.x - _cam.x
        _dy = _p.y - _cam.y
        return (_dx * _dx + _dy * _dy) <= (_near_cm * _near_cm)

    for _a in _u.GameplayStatics.get_all_actors_of_class(_w, _u.Actor):
        if isinstance(_a, _u.LandscapeStreamingProxy):
            _rec["proxies"] += 1
        elif isinstance(_a, _u.Landscape):
            _rec["landscape_actors"] += 1
        elif isinstance(_a, _u.InstancedFoliageActor):
            _rec["foliage_actors"] += 1
            _n = 0
            for _c in _a.get_components_by_class(
                    _u.HierarchicalInstancedStaticMeshComponent):
                try:
                    _n += int(_c.get_instance_count())
                except Exception:
                    pass
            _rec["foliage_instances"] += _n
            try:
                if _within(_a):
                    _rec["near_foliage_instances"] += _n
            except Exception:
                pass
            continue
        else:
            continue
        try:
            if _within(_a):
                _rec["near_proxies"] += 1
                _k2 = _a.get_components_by_class(_u.LandscapeComponent)
                _rec["near_components"] += len(_k2) if _k2 else 0
        except Exception:
            pass
        try:
            _c = _a.get_components_by_class(_u.LandscapeComponent)
        except Exception:
            _rec["components_unreadable"] += 1
            continue
        if _c is None:
            _rec["components_unreadable"] += 1
        else:
            _rec["components"] += len(_c)

    # Ask World Partition to describe itself FROM INSIDE PIE. The same dump
    # run in the editor prints nothing useful, because the runtime hash only
    # exists in a game world -- which is also why the grid name could not be
    # read from the editor and had to be established from engine source.
    # Here it can report the grids and their EFFECTIVE loading ranges, which is
    # the only way to tell whether wp.Runtime.OverrideRuntimeLoadingRange
    # actually took: the command is an FAutoConsoleCommand and echoes nothing.
    try:
        for _cmd in ("wp.Runtime.DumpWorldPartitions",
                     "wp.Runtime.DumpStreamingSources"):
            _u.SystemLibrary.execute_console_command(_w, _cmd)
        _rec["dumped"] = True
    except Exception as _de:
        _rec["dump_error"] = type(_de).__name__ + ": " + str(_de)

    # THE RESIDENT SET, for the DERIVED gate (ruled 2026-09-09).
    # `bench_expected_set.py` computes, in the editor, which actors the ENGINE
    # says are in the camera's loading range. This is the other half: which
    # actors are actually here in PIE when the shot finishes. The gate is
    # `expected - resident == empty`, and BOTH sets go in the sidecar.
    #
    # SUBSET, NOT EQUALITY. The ruling said "loaded set == expected set", but
    # strict equality is the wrong test and would fail every correct run:
    # always-loaded (non-spatial) actors are resident and are not in the
    # expected set by construction, and cells just outside the range stay
    # resident until they are streamed out. What matters is that nothing
    # EXPECTED is missing, so the recorded verdict is on the missing set.
    try:
        _names = []
        for _a in _u.GameplayStatics.get_all_actors_of_class(_w, _u.Actor):
            try:
                _names.append(_a.get_name())
            except Exception:
                pass
        _rec["resident_actor_count"] = len(_names)
        _rec["resident_actors"] = sorted(_names)
    except Exception as _re:
        _rec["resident_actors_error"] = type(_re).__name__ + ": " + str(_re)

    # where the camera actually was, so a shot can be matched to a station
    try:
        _pc = _u.GameplayStatics.get_player_controller(_w, 0)
        _vt = _pc.get_view_target() if _pc else None
        if _vt:
            _l = _vt.get_actor_location()
            _rec["view_target"] = {
                "label": _vt.get_actor_label() if hasattr(_vt, "get_actor_label") else None,
                "name": _vt.get_name(),
                "location_cm": [round(_l.x, 1), round(_l.y, 1), round(_l.z, 1)]}
    except Exception as _ve:
        _rec["view_target_error"] = type(_ve).__name__ + ": " + str(_ve)
except Exception as _e:
    import traceback as _tb
    _rec["error"] = type(_e).__name__ + ": " + str(_e)
    _rec["trace"] = _tb.format_exc()[-800:]

try:
    _d = _os.path.dirname(OUT)
    if _d and not _os.path.isdir(_d):
        _os.makedirs(_d)
    with open(OUT, "a", encoding="utf-8") as _f:
        _f.write(_json.dumps(_rec) + "\n")
except Exception as _we:
    _u.log_error("residency probe could not write %s: %s" % (OUT, _we))

_u.log("__LL_RESIDENCY__" + _json.dumps(_rec))
