"""set_grade_probe.py -- set ONE grade term for a slope probe. NOT SAVED.

A probe value must not persist. `apply_lighting` saves every package it
touches and commits, which is right for a ruled value and wrong for a
measurement step: four probes would leave four commits of lighting
packages and four chances to forget the revert.

This writes the live PostProcessVolume and saves NOTHING. PIE duplicates
the EDITOR world, so an unsaved editor change is what the MRQ render
sees -- which is exactly what a probe needs and exactly why it must be
put back afterwards. The caller is responsible for restoring; the
read-back below is what lets it prove the restore.

⛔ PROPERTY NAMES ARE TAKEN FROM apply_lighting, NOT INVENTED.
    apply_lighting.py:737-740   override_white_temp / white_temp
                                override_white_tint / white_tint
    apply_lighting.py:658-659   override_auto_exposure_bias /
                                auto_exposure_bias
Two lists that must agree are one list badly stored (NN24); this is the
second reader of that list, so it cites the first rather than restating
it from memory.

Every term is written WITH its override, because a value without its
override is not a setting (rule 12).
"""
import json as _json
import traceback as _tb

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')

_SETTABLE = {
    "white_temp": ("override_white_temp", float),
    "white_tint": ("override_white_tint", float),
    "auto_exposure_bias": ("override_auto_exposure_bias", float),
}

_out = {"ok": False, "requested": CFG}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _vols = [_a for _a in _eas.get_all_level_actors()
             if type(_a).__name__ == "PostProcessVolume"]
    _out["n_postprocess_volumes"] = len(_vols)
    if len(_vols) != 1:
        # Conduct rule 8: identify by signature and refuse on ambiguity
        # rather than taking the first of several.
        _out["error"] = ("expected exactly 1 PostProcessVolume, found %d -- "
                         "refusing to guess which one grades the bench"
                         % len(_vols))
        _out["volumes"] = [_a.get_actor_label() for _a in _vols]
    else:
        _v = _vols[0]
        _out["volume"] = _v.get_actor_label()
        _s = _v.get_editor_property("settings")

        _before = {}
        for _k in _SETTABLE:
            try:
                _before[_k] = float(_s.get_editor_property(_k))
            except Exception as _e:
                _before[_k] = "UNREADABLE: %s" % type(_e).__name__
        _out["before"] = _before

        _applied, _refused = [], {}
        for _k, _val in CFG.items():
            if _k not in _SETTABLE:
                _refused[_k] = "not a probe-settable term"
                continue
            _ovr, _cast = _SETTABLE[_k]
            try:
                _s.set_editor_property(_ovr, True)
                _s.set_editor_property(_k, _cast(_val))
                _applied.append(_k)
            except Exception as _e:
                _refused[_k] = "%s: %s" % (type(_e).__name__, _e)
        # The struct is fetched by VALUE in some bindings, so write it
        # back up. Harmless if it was a reference; fatal to the probe if
        # it was a copy and this is skipped (the grass_varieties defect).
        _v.set_editor_property("settings", _s)

        # READ BACK FROM A RE-FETCHED STRUCT, not from `_s` -- reading
        # the object we just wrote proves only that the setter ran.
        _s2 = _v.get_editor_property("settings")
        _after = {}
        for _k in _SETTABLE:
            try:
                _after[_k] = float(_s2.get_editor_property(_k))
                _after[_k + "_override"] = bool(
                    _s2.get_editor_property(_SETTABLE[_k][0]))
            except Exception as _e:
                _after[_k] = "UNREADABLE: %s" % type(_e).__name__
        _out["after"] = _after
        _out["applied"] = _applied
        _out["refused"] = _refused
        _out["matches_request"] = all(
            abs(_after.get(_k, 1e9) - float(_v2)) < 1e-4
            for _k, _v2 in CFG.items() if _k in _SETTABLE)
        _out["saved"] = False
        _out["_saved_note"] = ("DELIBERATELY UNSAVED -- this is a probe. "
                               "PIE duplicates the editor world, so the "
                               "render sees it; the caller must restore it.")
        _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
