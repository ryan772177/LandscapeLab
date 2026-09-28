"""Read the LOCAL EXPOSURE settings off the post-process volume. READ ONLY.

RULED 2026-09-11: "read back the local-exposure settings once; if
non-default, that is the finding."

⛔ WHY NOT CVARS. A first pass read r.LocalExposure.* through
get_console_variable_float_value and got 0.0 for every one -- which is
ALSO what that call returns for a cvar that DOES NOT EXIST. The tell was
r.TonemapperFilm reading 0.0 when its default is 1. Local exposure is a
PostProcessSettings block (Scene.h:2037), so it is read here from the
volume, where an unset property is distinguishable from a zero one by
its bOverride_ companion.

Engine defaults (Scene.h): HighlightContrastScale and ShadowContrastScale
default to 1.0, which means NO local adjustment. BlurredLuminanceBlend
0.6, MiddleGreyBias 0, DetailStrength 1.

THE "FINDING" IS AN OVERRIDDEN FIELD. This does not compare values against
those defaults (they are prose for the reader); instead the ruling's "if
non-default, that is the finding" is surfaced directly as each field's
override_ companion -- an overridden local-exposure field is the operator
having set it away from default. `overridden_fields` per volume, and
`any_overridden` overall, carry that.
"""
import json

import unreal as _u

FIELDS = [
    "local_exposure_method",
    "local_exposure_highlight_contrast_scale",
    "local_exposure_shadow_contrast_scale",
    "local_exposure_detail_strength",
    "local_exposure_blurred_luminance_blend",
    "local_exposure_blurred_luminance_kernel_size_percent",
    "local_exposure_middle_grey_bias",
    "local_exposure_highlight_threshold",
    "local_exposure_shadow_threshold",
]

_out = {"ok": False}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    try:
        _out["level_path"] = _ues.get_editor_world().get_path_name()
    except Exception:
        _out["level_path"] = None      # provenance: which level was read
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _vols = [a for a in _sub.get_all_level_actors()
             if isinstance(a, _u.PostProcessVolume)]
    _rows = []
    for _v in _vols:
        _s = _v.get_editor_property("settings")
        if _s is None:
            _rows.append({"label": str(_v.get_actor_label()),
                          "error": "settings struct is None"})
            continue
        _row = {"label": str(_v.get_actor_label()),
                "unbound": bool(_v.get_editor_property("unbound")),
                "priority": float(_v.get_editor_property("priority")),
                "fields": {}}
        _overridden = []
        for _f in FIELDS:
            _e = {}
            try:
                _e["value"] = _s.get_editor_property(_f)
                _e["value"] = (float(_e["value"])
                               if isinstance(_e["value"], (int, float))
                               else str(_e["value"]))
            except Exception as _ex:
                _e["value"] = "ABSENT (%s)" % type(_ex).__name__
            try:
                _e["overridden"] = bool(
                    _s.get_editor_property("override_" + _f))
                if _e["overridden"]:
                    _overridden.append(_f)
            except Exception as _oe:
                # distinguish could-not-read from a genuine False.
                _e["overridden"] = "UNKNOWN (%s)" % type(_oe).__name__
            _row["fields"][_f] = _e
        _row["overridden_fields"] = _overridden
        _rows.append(_row)
    _out["post_process_volumes"] = _rows
    _out["volume_count"] = len(_vols)
    _out["any_overridden"] = any(r.get("overridden_fields") for r in _rows)
    # NN13: zero volumes read is not success (a consumer must not read "no local
    # exposure override" out of "no volume existed").
    _out["ok"] = len(_vols) > 0
    if not _out["ok"]:
        _out["refused"] = "no PostProcessVolume in level; nothing to read"
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
