"""READ-ONLY probe for the benchmark rig. Mutates nothing.

Answers rule 11's "ASK WHICH LEVEL is loaded" before any mutation, traces
ground under the three derived stations (perf_budgets requires a trace, never
the heightmap), and reports whether the Movie Render Queue plugin and any
Bench_* actors already exist.

Run via: python scripts/ue_exec.py scripts/payloads/bench_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()
    _out["level_name"] = _w.get_name()

    # ---- ground traces under the derived stations -------------------------
    _stations = {
        "near_ground": [-210800.0, 278800.0],
        "mid_slope": [-190000.0, 100000.0],
        "vista": [-216400.0, 63600.0],
    }
    _g = {}
    for _n, (_x, _y) in _stations.items():
        _h = _u.SystemLibrary.line_trace_single(
            _w, _u.Vector(_x, _y, 200000.0), _u.Vector(_x, _y, -20000.0),
            _u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            _u.DrawDebugTrace.NONE, True)
        # FHitResult fields are protected in 5.8 Python; to_tuple()[4] is
        # the impact point (scripts/perf_flythrough.py:70).
        _g[_n] = float(_h.to_tuple()[4].z) if _h else None
    _out["traced_ground_cm"] = _g

    # ---- existing Bench_* actors -----------------------------------------
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _found = []
    for _a in _eas.get_all_level_actors():
        try:
            _lbl = _a.get_actor_label()
        except Exception:
            continue
        if _lbl.startswith("Bench_"):
            _loc = _a.get_actor_location()
            _rot = _a.get_actor_rotation()
            _found.append({
                "label": _lbl,
                "class": _a.get_class().get_name(),
                "location_cm": [round(_loc.x, 1), round(_loc.y, 1), round(_loc.z, 1)],
                "rotation_deg": [round(_rot.pitch, 3), round(_rot.yaw, 3),
                                 round(_rot.roll, 3)],
            })
    _out["existing_bench_actors"] = _found

    # ---- Movie Render Queue plugin ---------------------------------------
    _plug = {}
    try:
        for _pn in ("MovieRenderPipeline", "SequencerScripting", "LevelSequenceEditor"):
            _p = _u.PluginBlueprintLibrary.get_plugin_base_dir(_pn)
            _plug[_pn] = {"enabled": bool(_p), "base_dir": _p or None}
    except Exception as _pe:
        _plug["_error"] = type(_pe).__name__ + ": " + str(_pe)
    _out["plugins"] = _plug

    # ---- do the MRQ classes actually resolve in this process? -------------
    _cls = {}
    for _cn in ("MoviePipelineQueueSubsystem", "MoviePipelinePrimaryConfig",
                "MoviePipelineDeferredPassBase", "MoviePipelineImageSequenceOutput_PNG",
                "MoviePipelineOutputSetting", "MoviePipelineAntiAliasingSetting",
                "MoviePipelineConsoleVariableSetting", "MoviePipelinePIEExecutor",
                "LevelSequence", "MovieSceneCameraCutTrack"):
        _cls[_cn] = hasattr(_u, _cn)
    _out["classes_resolve"] = _cls

    # ---- viewport size -----------------------------------------------------
    # This asked SystemLibrary.get_viewport_size until 2026-09-06, which DOES
    # NOT EXIST in 5.8; the AttributeError was swallowed into a null and that
    # null was read across the project as evidence of editor overhead. Fixed
    # here for the same reason it was fixed in measure_frame_cost: a broken
    # call left in a probe is a null that somebody will interpret.
    try:
        _vp = _ues.get_level_viewport_size()
        _out["viewport_size"] = [int(_vp.x), int(_vp.y)] if _vp else None
    except Exception as _ve:
        _out["viewport_size"] = None
        _out["viewport_size_error"] = type(_ve).__name__ + ": " + str(_ve)

    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
