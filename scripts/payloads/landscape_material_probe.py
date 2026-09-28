"""Which material is the landscape ACTUALLY using?

READ-ONLY. Rebuilding `recipe.material.parent_material` and reporting
success proves nothing if the landscape actor references a DIFFERENT
material -- the build succeeds, the asset changes, and the world does
not. That is the wrong-target class of plausible artefact, and the only
way to rule it out is to ask the actor.

CLAUDE.md's spec line names `M_Alpine8K`; the recipe names
`M_AutoLandscape`. Both exist on disk. This settles which one the engine
holds.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _all = _sub.get_all_level_actors()
    _rows = []
    for _a in _all:
        if not isinstance(_a, _u.Landscape):
            continue
        _row = {"label": _a.get_actor_label(),
                "class": type(_a).__name__}
        for _prop in ("landscape_material", "landscape_hole_material"):
            try:
                _m = _a.get_editor_property(_prop)
                _row[_prop] = (_m.get_path_name() if _m else None)
            except Exception as _e:
                _row[_prop] = "ERR %s" % type(_e).__name__
        _rows.append(_row)
    _out["landscapes"] = _rows

    _out["assets"] = {}
    for _p in ("/Game/Materials/M_AutoLandscape",
               "/Game/Materials/M_Alpine8K"):
        _out["assets"][_p] = bool(
            _u.EditorAssetLibrary.does_asset_exist(_p))
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
