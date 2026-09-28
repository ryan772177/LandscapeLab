"""What does MoviePipelineColorSetting actually expose, and is a setting
added by find_or_add_setting_by_class ENABLED?

2026-09-11: disable_tone_curve read back TRUE and the EXR still came out
identical to the sRGB-decoded PNG, so the flag was set on something that
was not in effect. A read-back of a VALUE is not a read-back of whether
the setting APPLIES.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _out["color_setting_props"] = sorted(
        n for n in dir(_u.MoviePipelineColorSetting)
        if not n.startswith("_"))
    _cfg = _u.MoviePipelineMasterConfig() if hasattr(
        _u, "MoviePipelineMasterConfig") else _u.MoviePipelinePrimaryConfig()
    _out["config_class"] = type(_cfg).__name__
    _s = _cfg.find_or_add_setting_by_class(_u.MoviePipelineColorSetting)
    _out["added_class"] = type(_s).__name__
    _probe = {}
    for _n in ("is_enabled", "get_is_user_customized", "disable_tone_curve"):
        try:
            _v = getattr(_s, _n)
            _probe[_n] = bool(_v()) if callable(_v) else str(_v)
        except Exception as _e:
            _probe[_n] = "ERR %s" % _e
    for _n in ("enabled", "disable_tone_curve"):
        try:
            _probe["prop:" + _n] = str(_s.get_editor_property(_n))
        except Exception as _e:
            _probe["prop:" + _n] = "ERR %s" % _e
    _out["probe"] = _probe

    # what settings does a fresh config hold, and are they enabled?
    _s.set_editor_property("disable_tone_curve", True)
    try:
        _s.set_editor_property("enabled", True)
        _probe["set_enabled"] = "ok"
    except Exception as _e:
        _probe["set_enabled"] = "ERR %s" % _e
    _rows = []
    for _st in _cfg.get_all_settings():
        _row = {"class": type(_st).__name__}
        try:
            _row["is_enabled"] = bool(_st.is_enabled())
        except Exception as _e:
            _row["is_enabled"] = "ERR %s" % _e
        _rows.append(_row)
    _out["settings_in_config"] = _rows
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-1200:]

print("__LL__" + json.dumps(_out))
