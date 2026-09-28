"""dump_live_cvars.py -- audit item 4: every cvar this build actually has.

READ-ONLY (a diagnostic dump; changes no state).

WHY THIS EXISTS. Pass 1 rules names dead -- r.LandscapeLODBias,
landscape.ForcedLOD, r.Shadow.Virtual.Nanite.Enable, foliage.WindEnabled
-- by QUOTING an earlier enumeration, and the audit README says so in as
many words: "Every 'DOES NOT EXIST in 5.8' is quoted from an earlier
live enumeration, not re-run." This re-runs it against
5.8.1-56057345+++UE5+Release-5.8.

HOW. Python exposes only four console getters, all by name --
get_console_variable_{bool,float,int,string}_value -- and NO enumeration
(verified this session: the whole console surface on SystemLibrary is
those four plus execute_console_command). So the enumeration has to come
from the engine's own dump: `Help` writes every registered variable and
command to Saved/ConsoleHelp.html.

⭐ THE TWO CONTROLS TRAVEL WITH THE READ (probe standard). A name that
MUST resolve and a name that CANNOT exist are both probed through the
same getter as the real queries. If the positive comes back empty, or
the negative comes back non-empty, the getter is not discriminating and
every "does not exist" below is unsupported -- so the controls are
reported next to the answers, not in a separate run.
"""
import json as _json
import os as _os
import traceback as _tb

import unreal as _u

_out = {"ok": False}

# Names that are IN FORCE and worth reading. Each is either written by
# a profile or consulted by a gate.
#
# ⛔ THE SETTLED-ABSENT NAMES WERE REMOVED 2026-09-14 (AUDIT 6, probe
# standard: "no probing of names already known absent"). They were
# confirmed absent on 2026-09-13 by TWO instruments -- the string getter
# and the engine's own 11,073-entry `Help` enumeration -- with both
# controls passing, and AUDIT V-3 records that as CONFIRMED. Re-asking
# a settled question every run costs a round trip and, worse, makes the
# output look like an open investigation.
#
# Removed: r.LandscapeLODBias, landscape.ForcedLOD,
# r.Shadow.Virtual.Nanite.Enable, foliage.WindEnabled, r.Wind.Enable,
# r.TonemapperFilm, r.ExpandGamut, r.LocalExposure.* (x2 here, x6 in
# the wider record), r.Landscape.MaxLODLevel.
# The full absent list lives in AUDIT V-3 and in the enumeration at
# research/audit/inputs/cvars_5.8_live.txt -- grep that file, do not
# re-probe.
#
# ⭐ THE NEGATIVE CONTROL STAYS. It is the one deliberately-absent name
# that must keep being asked, because it is what proves the getter can
# still tell absent from present.
_QUERY = [
    "r.ForceLOD",
    "r.Shadow.Virtual.ResolutionLodBiasDirectional",
    "r.VT.AnisotropicFiltering", "r.VT.MaxAnisotropy",
    "r.MaxAnisotropy", "r.ScreenPercentage", "r.AntiAliasingMethod",
    "sg.ShadowQuality", "sg.FoliageQuality",
    "sg.TextureQuality", "sg.ViewDistanceQuality", "sg.EffectsQuality",
    "sg.AntiAliasingQuality", "sg.GlobalIlluminationQuality",
    "sg.ReflectionQuality", "sg.PostProcessQuality",
]
_CONTROL_POS = "r.ScreenPercentage"
_CONTROL_NEG = "r.ThisCVarCannotPossiblyExist_zzz"


def _probe(_n):
    """A cvar's existence and value, through the string getter.

    The STRING getter is the right instrument: the int/float getters
    return 0 for an absent name and 0 for a name whose value is zero,
    which is the same number for two different facts.
    """
    _r = {"name": _n}
    try:
        _s = _u.SystemLibrary.get_console_variable_string_value(_n)
    except Exception as _e:
        _r["exists"] = None
        _r["error"] = "%s: %s" % (type(_e).__name__, _e)
        return _r
    _r["string"] = _s
    _r["exists"] = bool(_s != "")
    for _k, _f in (("int", _u.SystemLibrary.get_console_variable_int_value),
                   ("float",
                    _u.SystemLibrary.get_console_variable_float_value)):
        try:
            _r[_k] = _f(_n)
        except Exception:
            _r[_k] = None
    return _r

try:
    _out["engine_version"] = _u.SystemLibrary.get_engine_version()
    _out["control_positive"] = _probe(_CONTROL_POS)
    _out["control_negative"] = _probe(_CONTROL_NEG)
    _ok_controls = (_out["control_positive"].get("exists") is True
                    and _out["control_negative"].get("exists") is False)
    _out["controls_pass"] = _ok_controls
    if not _ok_controls:
        # NN6: degrade naming the gap, rather than reporting numbers the
        # instrument has just failed to justify.
        _out["error"] = ("CONTROLS FAILED -- the string getter does not "
                         "discriminate present from absent, so no "
                         "existence verdict below is supported")
    _out["queried"] = [_probe(_n) for _n in _QUERY]

    # The full enumeration, from the engine's own dump.
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _saved = _u.Paths.convert_relative_path_to_full(_u.Paths.project_saved_dir())
    _help = _os.path.join(_saved, "ConsoleHelp.html")
    _before = _os.path.getmtime(_help) if _os.path.isfile(_help) else None
    _u.SystemLibrary.execute_console_command(_w, "Help")
    _after = _os.path.getmtime(_help) if _os.path.isfile(_help) else None
    _out["console_help_path"] = _help
    _out["console_help_existed_before"] = _before is not None
    _out["console_help_rewritten"] = (_before != _after)
    _out["console_help_bytes"] = (
        _os.path.getsize(_help) if _os.path.isfile(_help) else None)
    _out["ok"] = _ok_controls
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
