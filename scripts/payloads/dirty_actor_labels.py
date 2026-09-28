"""Resolve DIRTY external-actor packages to the ACTORS they contain.

READ-ONLY. R-EDITOR-CLOSE requires the dirty packages be ENUMERATED
before a close decision -- "say why losing them is acceptable". A list of
opaque `__ExternalActors__/Alpine8K/9/L6/5MIUARSXM5OIDCHXTVE8MU` paths
does not support that sentence; an actor LABEL does.

A World Partition actor lives in its own package, so the mapping is
one actor per dirty package -- but it is resolved by asking each actor
for its package rather than by parsing the path, because the path is an
opaque hash and a parse would be a guess.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    # THE DIRTY SET COMES FROM THE SAME API THE CENSUS USES, not from a
    # per-package `is_dirty` -- `Package` has no such attribute in 5.8, and
    # guessing it cost a round trip. Both content and map packages are
    # queried SEPARATELY for the census's own stated reason: a failure in
    # one must not silently report the other as "nothing dirty".
    _dirty_names = set()
    _probe_err = []
    for _fn in ("get_dirty_content_packages", "get_dirty_map_packages"):
        try:
            for _p in getattr(_u.EditorLoadingAndSavingUtils, _fn)():
                _dirty_names.add(str(_p.get_name()))
        except Exception as _pe:
            _probe_err.append("%s: %s" % (_fn, _pe))
    if _probe_err:
        _out["probe_errors"] = _probe_err

    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _rows = []
    _seen = set()
    for _a in _sub.get_all_level_actors():
        try:
            _name = str(_a.get_outermost().get_name())
        except Exception:
            continue
        if _name not in _dirty_names or _name in _seen:
            continue
        _seen.add(_name)
        _rows.append({
            "label": _a.get_actor_label(),
            "class": type(_a).__name__,
            "package": _name,
        })
    _out["dirty_actors"] = sorted(_rows, key=lambda r: (r["class"],
                                                        r["label"]))
    _out["dirty_actor_count"] = len(_rows)

    # Dirty packages that resolved to NO actor (the map itself, an asset,
    # or an actor already unloaded) are listed rather than omitted -- a
    # reader who cannot tell "none" from "not looked for" is how a census
    # lies, and these are exactly the ones a label list would hide.
    _out["dirty_total"] = len(_dirty_names)
    _out["unresolved_dirty"] = sorted(_dirty_names - _seen)
    _out["level"] = str(_u.EditorLevelLibrary.get_editor_world().get_name())
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
