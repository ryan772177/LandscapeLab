"""Dirty-package census, REPORT ONLY. Saves nothing, closes nothing.

R-EDITOR-CLOSE step 1 names `scripts/payloads/dirty_package_census_payload.txt`
and THAT FILE DOES NOT EXIST (checked 2026-09-08, whole repo). A recipe step
whose tool is missing silently degrades into "skip step 1", which is exactly
the step that authorises a kill. This is the replacement.

MAP AND CONTENT PACKAGES ARE QUERIED SEPARATELY, as the recipe requires, and
each query has its OWN error slot: "I could not look" must never collapse into
"nothing is dirty". If either call raises, `can_conclude` goes false and the
census refuses to authorise anything.

APIs: `EditorLoadingAndSavingUtils.get_dirty_map_packages()` and
`.get_dirty_content_packages()` -- both in use in `save_dirty.py`.

Run via: python scripts/ue_exec.py scripts/payloads/dirty_census.py
"""
import json as _json

import unreal as _u

_out = {"error": None, "map": {}, "content": {}, "can_conclude": True}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    for _key, _fn in (("map", "get_dirty_map_packages"),
                      ("content", "get_dirty_content_packages")):
        try:
            _pkgs = getattr(_u.EditorLoadingAndSavingUtils, _fn)()
            _names = sorted(_p.get_name() for _p in _pkgs)
            _out[_key] = {"count": len(_names), "names": _names[:40],
                          "truncated": len(_names) > 40}
        except Exception as _e:
            _out[_key] = {"error": type(_e).__name__ + ": " + str(_e)}
            _out["can_conclude"] = False

    if _out["can_conclude"]:
        _out["total_dirty"] = (_out["map"].get("count", 0)
                               + _out["content"].get("count", 0))
        _out["verdict"] = ("CLEAN" if _out["total_dirty"] == 0
                           else "DIRTY -- do not kill, save or wait")
    else:
        _out["verdict"] = "COULD NOT LOOK -- not a clean census, do not kill"
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["can_conclude"] = False
    _out["verdict"] = "COULD NOT LOOK -- not a clean census, do not kill"
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
