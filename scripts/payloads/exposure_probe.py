"""READ-ONLY: does the live world's PostProcessVolume actually own exposure?

`recipes/alpine_8k.json` declares `lighting.exposure = {method: manual,
compensation_ev: -1.923}` with a long solve note, and `apply_lighting.py:333-345`
sets `override_auto_exposure_method` + `AEM_MANUAL` + the bias on an unbound
PostProcessVolume. So the DECLARATION and the APPLICATION both exist.

What has never existed is the READ-BACK, and the 2026-09-06 dolly drifted mean
luma 0.3486 -> 0.2749 over 8.4 m, which is what auto-exposure looks like. Under
standing rule 12 that makes the setting prose until something reads it from the
engine. This is that read.

Reports every PostProcessVolume in the level, not just the first: two volumes
with different exposure settings is a state the declaration cannot express and
the frame cannot distinguish.

Run via: python scripts/ue_exec.py scripts/payloads/exposure_probe.py
"""
import json as _json

import unreal as _u

_out = {"error": None, "volumes": []}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    for _a in _eas.get_all_level_actors():
        if not isinstance(_a, _u.PostProcessVolume):
            continue
        _e = {"actor": _a.get_name()}
        try:
            _e["label"] = _a.get_actor_label()
        except Exception:
            pass
        for _p in ("unbound", "priority", "blend_weight", "enabled"):
            try:
                _e[_p] = _a.get_editor_property(_p)
            except Exception:
                pass
        try:
            _s = _a.get_editor_property("settings")
            for _p in ("override_auto_exposure_method", "auto_exposure_method",
                       "override_auto_exposure_bias", "auto_exposure_bias",
                       "override_auto_exposure_min_brightness",
                       "auto_exposure_min_brightness",
                       "override_auto_exposure_max_brightness",
                       "auto_exposure_max_brightness",
                       "override_auto_exposure_speed_up",
                       "auto_exposure_speed_up",
                       "override_auto_exposure_speed_down",
                       "auto_exposure_speed_down"):
                try:
                    _v = _s.get_editor_property(_p)
                    _e[_p] = str(_v) if not isinstance(_v, (int, float, bool)) else _v
                except Exception as _pe:
                    _e[_p] = "ERR " + type(_pe).__name__
        except Exception as _se:
            _e["settings_error"] = type(_se).__name__ + ": " + str(_se)
        _out["volumes"].append(_e)

    _out["volume_count"] = len(_out["volumes"])

    # the engine's own current values for the two cvars the profile now sets
    _cv = {}
    for _n in ("r.DefaultFeature.AutoExposure", "r.EyeAdaptationQuality"):
        try:
            _cv[_n] = _u.SystemLibrary.get_console_variable_float_value(_n)
        except Exception as _ce:
            _cv[_n] = "ERR " + type(_ce).__name__
    _out["editor_cvars_now"] = _cv

    # what the recipe asks for, so host-side comparison needs no second source
    _out["_recipe_declares"] = "lighting.exposure {method, compensation_ev}"
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1000:]

print("__LL__" + _json.dumps(_out))
