"""Read the TONE-CURVE state from inside a deferred-pass render.

Runs via `py "<file>"` from MRQ's end_console_commands, so it executes
in the render's own console context rather than in an idle editor.

⭐ WHY THIS EXISTS. `MoviePipelineColorSetting.disable_tone_curve` is
what the SETTER wrote. Rule 12 says a value that is not read back from
the thing that honours it is prose -- and the things that honour the
tone curve are the VIEW's show flag and the volume's `tone_curve_amount`,
not the MRQ property. Those are the primary reads; alongside them this
records r.Tonemapper.Quality / r.Color.Min / r.Color.Max and, per
PostProcessVolume, the tone_curve_amount / tonemapping_method /
expand_gamut value+override pairs.

`showflag.tonecurve` values are the engine's show-flag convention:
0 = forced off, 1 = forced on, 2 = follow the default. A 2 therefore
does NOT mean "on"; it means nobody forced it either way at the console,
which is exactly the ambiguity that makes reading the MRQ property
insufficient.
"""
import json
import traceback

import unreal as _u

OUT_PATH = __OUT_PATH__

_row = {"what": "tone curve state during a deferred-pass render"}
try:
    for _n in ("showflag.tonecurve", "r.Tonemapper.Quality",
               "r.Color.Min", "r.Color.Max"):
        try:
            _s = _u.SystemLibrary.get_console_variable_string_value(_n)
            _ex = bool(_s != "")
            # The float getter returns 0.0 for a NON-EXISTENT cvar; only record
            # it when the cvar actually exists, so 0.0 cannot read as a value.
            _row[_n] = {"string": _s, "exists": _ex,
                        "float": (float(
                            _u.SystemLibrary.get_console_variable_float_value(
                                _n)) if _ex else None)}
        except Exception as _e:
            _row[_n] = {"error": str(_e)[:120]}

    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _vols = []
    for _a in _sub.get_all_level_actors():
        if type(_a).__name__ != "PostProcessVolume":
            continue
        _s2 = _a.get_editor_property("settings")
        _v = {"label": _a.get_actor_label()}
        for _p in ("tone_curve_amount", "override_tone_curve_amount",
                   "tonemapping_method", "override_tonemapping_method",
                   "expand_gamut", "override_expand_gamut"):
            try:
                _x = _s2.get_editor_property(_p)
                _v[_p] = (bool(_x) if isinstance(_x, bool)
                          else float(_x) if isinstance(_x, (int, float))
                          else str(_x))
            except Exception:
                _v[_p] = "ABSENT"
        _vols.append(_v)
    _row["post_process_volumes"] = _vols
    _row["volume_count"] = len(_vols)
    # NN13 + rule 12: ok must mean "the tone-curve state was actually read
    # back", not merely "no exception escaped". Require at least one
    # PostProcessVolume, the show-flag cvar to have read cleanly, and at least
    # one volume with a real (non-ABSENT) tone_curve_amount -- the value the
    # docstring names as the thing that honours the curve.
    _sf = _row.get("showflag.tonecurve", {})
    _tone_seen = any(isinstance(_vv.get("tone_curve_amount"), (int, float))
                     for _vv in _vols)
    _row["ok"] = bool(_vols) and ("error" not in _sf) and _tone_seen
    if not _row["ok"]:
        _row["refused"] = ("no PostProcessVolume / show-flag unreadable / no "
                           "tone_curve_amount read: %d volumes, tone_seen=%s"
                           % (len(_vols), _tone_seen))
except Exception as _e:
    _row["ok"] = False
    _row["error"] = "%s: %s" % (type(_e).__name__, _e)
    _row["trace"] = traceback.format_exc()[-500:]

try:
    with open(OUT_PATH, "a", encoding="utf-8") as _fh:
        _fh.write(json.dumps(_row) + "\n")
except Exception as _we:
    # The JSONL artefact is the whole reason OUT_PATH exists; do not swallow a
    # failed write -- emit a distinct marker so the caller can detect the miss.
    print("__TONECURVE_WRITE_FAILED__" + json.dumps(
        {"out_path": str(OUT_PATH), "error": str(_we)[:200]}))
print("__TONECURVE__" + json.dumps(_row))
