"""Save every dirty package, with the LEVEL GATE kept.

Used when `save_level.py` cannot get through. On 2026-09-07 that client sat 30
minutes at 0.7 s of CPU with its payload never reaching the editor (no
LogPython line), while `ue_exec` had worked three times in the preceding hour.
This goes through `ue_exec`, which is the channel that works.

THE LEVEL GATE IS NOT OPTIONAL AND IS REPRODUCED HERE. `save_level.py` refused
correctly on 2026-09-05 when its default recipe targeted `/Game/Alpine` while
the editor held `/Game/Alpine8K`. Rule 7 verifies the PROJECT; this verifies
the LEVEL, and saving the wrong world is not recoverable by re-running.

Run via:
  python scripts/ue_exec.py scripts/payloads/save_dirty.py --set LEVEL=/Game/Alpine8K
"""
import json as _json

import unreal as _u

EXPECT_LEVEL = "__LEVEL__"

_out = {"error": None, "saved": 0, "failed": [], "dirty_before": 0}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _lvl = _w.get_path_name().split(".")[0]
    _out["level_path"] = _w.get_path_name()
    if _lvl != EXPECT_LEVEL:
        raise RuntimeError("LEVEL GATE: editor holds %r, expected %r -- refusing "
                           "to save the wrong world" % (_lvl, EXPECT_LEVEL))

    _dirty = [p for p in _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _dirty += [p for p in _u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _seen, _uniq = set(), []
    for _p in _dirty:
        _n = _p.get_name()
        if _n not in _seen:
            _seen.add(_n)
            _uniq.append(_p)
    _out["dirty_before"] = len(_uniq)

    # Saves ONE AT A TIME so an interruption leaves a partial result and a
    # count, rather than nothing.
    #
    # CORRECTION 2026-09-07, same day: an earlier version of this comment said
    # the bulk `save_dirty_packages()` call was the reason a whole-world save
    # hung and that this loop was "the path that finishes". THAT WAS WRONG --
    # the loop reproduces the same spin. The 0.110 s per-package figure was
    # measured after a BOUNDED assignment of ~10 actors; the hang follows a
    # ~2,796-actor assignment regardless of which save API is used. Two things
    # differed between the runs and I credited the one I had been thinking
    # about. The loop is kept for its progress and partial-result properties,
    # NOT because it fixes anything. See LESSONS 2026-09-07.
    import time as _time
    _t0 = _time.time()
    for _p in _uniq:
        try:
            if _u.EditorLoadingAndSavingUtils.save_packages([_p], True):
                _out["saved"] += 1
            else:
                _out["failed"].append(_p.get_name())
        except Exception as _pe:
            _out["failed"].append(_p.get_name() + " :: " + type(_pe).__name__)
    _out["elapsed_s"] = round(_time.time() - _t0, 2)
    _out["mean_per_package_s"] = (round(_out["elapsed_s"] / max(len(_uniq), 1), 4))

    # READ BACK: ask again, do not trust the return value
    _after = [p.get_name() for p in
              _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _after += [p.get_name() for p in
               _u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _out["dirty_after"] = len(set(_after))
    _out["still_dirty_sample"] = sorted(set(_after))[:8]
    _out["cleared"] = _out["dirty_before"] - _out["dirty_after"]
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
