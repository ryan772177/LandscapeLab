"""shade_pair_remove.py -- remove the shade card-pair instrument actors.

The card pair (two 18% cards + a blocker cube) is an INSTRUMENT, not
scene content. R-SHADE: instrument actors left in a station's frame
change what every later capture of that station measures, silently. So
after the shade acceptance is measured, the pair is removed and the
level saved.

Identified by OUR OWN EXACT LABEL PREFIXES and nothing else (standing
rule 8): the two prefixes this project's shade tool writes. Anything
else is left untouched. Prints one __LL__ JSON line with the removed
labels and the save verdict; a zero removal count is reported as its own
field, not read as success.
"""
import json

import unreal as _u

_PREFIXES = ("Bench_ShadeCard_", "Bench_ShadeBlocker_")

_out = {"ok": False, "error": None, "removed": [], "n_removed": 0}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
    for _a in list(_eas.get_all_level_actors()):
        _lb = _a.get_actor_label()
        if any(_lb.startswith(_p) for _p in _PREFIXES):
            _out["removed"].append(_lb)
            _eas.destroy_actor(_a)
    _out["n_removed"] = len(_out["removed"])
    # Read back: none of our labels may survive the destroy.
    _survivors = [a.get_actor_label() for a in _eas.get_all_level_actors()
                  if any(a.get_actor_label().startswith(_p)
                         for _p in _PREFIXES)]
    _out["survivors"] = _survivors
    if _survivors:
        _out["error"] = "labels survived destroy: %r" % _survivors
    else:
        _saved = _les.save_current_level()
        _out["saved"] = bool(_saved)
        _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
