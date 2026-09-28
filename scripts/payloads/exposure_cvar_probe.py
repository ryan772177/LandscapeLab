"""Read back the exposure-adjacent cvars. READ ONLY -- sets nothing.

RULED 2026-09-11: "read back the local-exposure settings once; if
non-default, that is the finding." Pre-exposure is listed as a Q12
candidate and is NOT to be touched; it is read here because a number
that is claimed should be checked against the engine before it is
recorded, not after.
"""
import json

import unreal as _u

NAMES = [
    "r.EyeAdaptation.CachedLightingPreExposure",
    "r.EyeAdaptation.PreExposureOverride",
    "r.EyeAdaptation.MethodOverride",
    "r.EyeAdaptation.LensAttenuation",
    "r.EyeAdaptation.ExponentialTransitionDistance",
    "r.EyeAdaptationQuality",
    "r.LocalExposure",
    "r.LocalExposure.Method",
    "r.LocalExposure.HighlightContrastScale",
    "r.LocalExposure.ShadowContrastScale",
    "r.LocalExposure.DetailStrength",
    "r.LocalExposure.BlurredLuminanceBlend",
    "r.LocalExposure.MiddleGreyBias",
    "r.Tonemapper.Quality",
    "r.TonemapperFilm",
    "r.Color.Mid",
    "r.ExpandGamut",
    "r.TonemapperGamma",
]

# AUDIT P1-5 / FP-4 (2026-09-15): one POSITIVE and one NEGATIVE control
# per batch read. Without them a probe that reads everything as absent
# cannot tell a genuinely-absent cvar from a broken reader. The string
# getter is the discriminator (cvar_exists_probe): a present cvar
# stringifies non-empty, an absent one to "".
POS_CONTROL = "r.ScreenPercentage"                 # must read non-empty
NEG_CONTROL = "r.ThisCVarCannotPossiblyExist_zzz"  # must read empty

_out = {"ok": False, "cvars": {}, "controls_ok": None,
        "control_failures": []}
try:
    for _n in NAMES + [POS_CONTROL, NEG_CONTROL]:
        _row = {}
        try:
            # float getter returns 0.0 for a NON-EXISTENT cvar, so a bare float
            # cannot distinguish absent from zero -- `exists` below is the
            # discriminator. On error, None (not an "ERR" string in a float
            # field, which mixes types).
            _row["float"] = float(
                _u.SystemLibrary.get_console_variable_float_value(_n))
        except Exception as _e:
            _row["float"] = None
            _row["float_error"] = type(_e).__name__
        try:
            _row["int"] = int(
                _u.SystemLibrary.get_console_variable_int_value(_n))
        except Exception:
            _row["int"] = None
        try:
            _s = _u.SystemLibrary.get_console_variable_string_value(_n)
            _row["string"] = str(_s)
            _row["exists"] = bool(_s != "")
        except Exception as _e:
            _row["string"] = None
            _row["string_error"] = type(_e).__name__
            _row["exists"] = None      # could-not-read, not absent
        _out["cvars"][_n] = _row
    _pos = _out["cvars"][POS_CONTROL]
    _neg = _out["cvars"][NEG_CONTROL]
    # POSITIVE must READ AS PRESENT; a string-getter error left exists=None, and
    # the old `if not _pos` (with an "ERR..." string) let that error pass.
    if not _pos.get("exists"):
        _out["control_failures"].append(
            "positive control %s did not read as present (exists=%r)"
            % (POS_CONTROL, _pos.get("exists")))
    # NEGATIVE must read cleanly ABSENT: exists exactly False (None = error).
    if _neg.get("exists") is not False:
        _out["control_failures"].append(
            "negative control %s did not read cleanly absent (exists=%r)"
            % (NEG_CONTROL, _neg.get("exists")))
    _out["n_read"] = len(_out["cvars"])
    _out["controls_ok"] = not _out["control_failures"]
    # The readings are trustworthy only if the reader passed its controls. Each
    # cvar's `exists` says absent vs present; "non-default" is the reader's call.
    _out["ok"] = _out["controls_ok"]
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
