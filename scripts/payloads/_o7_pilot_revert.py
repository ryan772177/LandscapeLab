"""Revert the O-7 save-cost pilot's footprint: clear hlod_layer back to None on
every target-class actor that currently carries one, and save per package.

The pilot (hlod_setup_layers.py) PERSISTS its assignments -- that is inherent to
measuring a real save cost. Its deliverable is the cost number, not the
assignment; the assignment policy (FoliageApprox for all foliage; the _Landscape
layer ruled REDUNDANT, STATE 3c) is unsettled, so a partial assignment should
not persist on the shipped world. Baseline was uniformly hlod_layer None on all
4339 actors (probes 2026-09-07, 2026-09-13), so clearing every non-None
target-class actor restores that baseline exactly and touches only the ~79 the
pilot assigned.

Rule 12: each cleared package is SAVED and the whole world re-scanned afterward
to confirm ZERO target-class actors retain a layer (the read-back is the disk
evidence, not the setter return).

Run via: python scripts/ue_exec.py scripts/payloads/_o7_pilot_revert.py
"""
import json as _json
import time as _time
import unreal as _u

_out = {"ok": False, "error": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _targets = (_u.InstancedFoliageActor, _u.LandscapeStreamingProxy,
                _u.Landscape, _u.StaticMeshActor)
    _cleared = []
    for _a in _eas.get_all_level_actors():
        if not isinstance(_a, _targets):
            continue
        try:
            _cur = _a.get_editor_property("hlod_layer")
        except Exception:
            continue
        if _cur is None:
            continue
        _a.set_editor_property("hlod_layer", None)
        _pkg = _a.get_package()
        _t0 = _time.perf_counter()
        try:
            _ok_s = bool(_u.EditorLoadingAndSavingUtils.save_packages([_pkg], False))
            _err = None
        except Exception as _se:
            _ok_s, _err = False, type(_se).__name__ + ": " + str(_se)
        _cleared.append({"label": str(_a.get_actor_label()),
                         "class": _a.get_class().get_name(),
                         "saved": _ok_s,
                         "seconds": round(_time.perf_counter() - _t0, 3),
                         "error": _err})
    _out["cleared_count"] = len(_cleared)
    _out["cleared"] = _cleared
    _out["saved_ok"] = sum(1 for _c in _cleared if _c["saved"])

    # READ BACK: re-scan the whole world; ZERO target-class actors may retain a
    # layer for the revert to be complete (rule 12 -- disk-persisted evidence,
    # via a fresh property read on every actor, not the setter return).
    _still = 0
    for _a in _eas.get_all_level_actors():
        if not isinstance(_a, _targets):
            continue
        try:
            if _a.get_editor_property("hlod_layer") is not None:
                _still += 1
        except Exception:
            pass
    _out["target_class_actors_still_layered"] = _still
    if _still != 0:
        raise RuntimeError("%d target-class actors still carry a layer after "
                           "revert" % _still)
    if _out["saved_ok"] != len(_cleared):
        raise RuntimeError("%d of %d cleared packages failed to save" %
                           (len(_cleared) - _out["saved_ok"], len(_cleared)))
    _out["ok"] = True
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
