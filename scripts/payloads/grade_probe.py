"""Every COLOUR-GRADING term on the live PostProcessVolume, read back.

READ-ONLY. Q12's residual is a log-log slope of ~0.72, and a colour
grading CONTRAST applied about a pivot is exactly a power law: it maps
log2(x) linearly with slope = contrast. So the grade is not a suspect by
analogy -- it is the one stage in the chain whose documented behaviour
has the shape of the defect.

Names are ENUMERATED off the reflected surface, not recalled: 5.8's
FPostProcessSettings splits grading into global/shadows/midtones/
highlights, each with saturation, contrast, gamma, gain and offset, and
each has an `override_` companion that decides whether it is in force at
all. A value without its override is not a setting (rule 12).
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _vols = []
    for _a in _sub.get_all_level_actors():
        if type(_a).__name__ != "PostProcessVolume":
            continue
        _s = _a.get_editor_property("settings")
        _row = {"label": _a.get_actor_label(), "grading": {}}
        try:
            _row["unbound"] = bool(_a.get_editor_property("unbound"))
            _row["priority"] = float(_a.get_editor_property("priority"))
            _row["blend_weight"] = float(
                _a.get_editor_property("blend_weight"))
        except Exception:
            pass
        for _p in sorted(set(dir(type(_s)))):
            if _p.startswith("_"):
                continue
            _l = _p.lower()
            if not any(t in _l for t in
                       ("contrast", "gamma", "gain", "saturation", "offset",
                        "color_grading", "film", "tone", "expand_gamut",
                        "scene_color_tint", "blue_correction",
                        "white_temp", "white_tint")):
                continue
            try:
                _v = _s.get_editor_property(_p)
            except Exception:
                continue
            if callable(_v):
                continue
            _row["grading"][_p] = (
                bool(_v) if isinstance(_v, bool)
                else _v if isinstance(_v, (int, float)) else str(_v))
        _vols.append(_row)
    _out["volumes"] = _vols
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-800:]

print("__LL__" + json.dumps(_out))
