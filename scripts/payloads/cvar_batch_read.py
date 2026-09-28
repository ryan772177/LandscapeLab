"""Batch-read console variables, DISTINGUISHING absent from zero, with
controls that can fail.

⛔ THE DEFECT THIS CLOSES. SystemLibrary.get_console_variable_float_value
returns 0.0 for a variable THAT DOES NOT EXIST --
KismetSystemLibrary.cpp:610-622 initialises `float Value = 0.0f`, and
when FindConsoleVariable returns null it logs a warning and returns that
0.0. On 2026-09-11 that read r.LocalExposure.* as "all zeroed, therefore
non-default, therefore the finding" when those names simply do not exist.
A reader that cannot tell zero from absent is not an instrument.

THE EXISTENCE TEST is the STRING getter, verified 2026-09-11:

    r.ScreenPercentage  -> '100'   exists
    r.ExpandGamut       -> ''      ABSENT in 5.8
    r.TonemapperFilm    -> ''      ABSENT in 5.8
    <impossible name>   -> ''      absent

An existing cvar whose value is 0 stringifies as '0', which is non-empty
-- so empty string means absent, and that is the discriminator.

THE CONTROLS RUN IN EVERY BATCH, both directions, and the batch REFUSES
if either misbehaves. A read-back that cannot fail is not a read-back.
  POSITIVE  r.ScreenPercentage must EXIST and be non-zero
  NEGATIVE  an impossible name must read ABSENT
The ruling named r.TonemapperFilm (default 1) as the fixed control; it
does NOT EXIST in 5.8 and would have read absent forever, so it is kept
in the batch as a THIRD, documented negative control instead.
"""
import json

import unreal as _u

POS_CONTROL = "r.ScreenPercentage"
NEG_CONTROL = "r.ThisCVarCannotPossiblyExist_zzz"
DOC_CONTROL = "r.TonemapperFilm"

NAMES = __NAMES_JSON__


def _read(_n):
    _r = {"name": _n}
    try:
        _s = _u.SystemLibrary.get_console_variable_string_value(_n)
        _s = "" if _s is None else str(_s)
    except Exception as _e:
        return dict(_r, exists=None, error="string getter: %s" % _e)
    _r["string"] = _s
    _r["exists"] = len(_s) > 0
    if not _r["exists"]:
        _r["value"] = None
        _r["note"] = ("ABSENT -- no such console variable. The float "
                      "getter would report 0.0 for this.")
        return _r
    try:
        _r["value"] = float(
            _u.SystemLibrary.get_console_variable_float_value(_n))
    except Exception as _e:
        _r["value"] = None
        _r["error"] = "float getter: %s" % _e
    return _r


_out = {"ok": False, "cvars": {}}
try:
    for _n in NAMES:
        _out["cvars"][_n] = _read(_n)
    _p = _read(POS_CONTROL)
    _ng = _read(NEG_CONTROL)
    _dc = _read(DOC_CONTROL)
    _out["controls"] = {"positive": _p, "negative": _ng,
                        "documented_absent": _dc}
    _fail = []
    # POSITIVE: distinguish an instrument error from ABSENT from a zero value --
    # the old code labelled a string-getter error "reads ABSENT" and a float-
    # getter error "reads zero".
    _pe = _p.get("exists")
    if _pe is None:
        _fail.append("positive control %s errored: %s"
                     % (POS_CONTROL, _p.get("error")))
    elif not _pe:
        _fail.append("positive control %s reads ABSENT" % POS_CONTROL)
    elif _p.get("value") is None:
        _fail.append("positive control %s value unreadable: %s"
                     % (POS_CONTROL, _p.get("error")))
    elif not _p.get("value"):
        _fail.append("positive control %s reads zero" % POS_CONTROL)
    # NEGATIVE: an instrument error (exists=None) is NOT a clean ABSENT; only
    # exists is False passes. The old `if _ng.get("exists")` let None fail open.
    if _ng.get("exists") is not False:
        _fail.append("negative control %s did not read cleanly ABSENT "
                     "(exists=%r)" % (NEG_CONTROL, _ng.get("exists")))
    # DOCUMENTED-ABSENT: advertised as a control, so it must gate too -- a
    # control that is read but never checked is prose (rule 12).
    if _dc.get("exists"):
        _fail.append("documented-absent control %s reads PRESENT" % DOC_CONTROL)
    # NN13: report the sample count, and refuse a batch that read ZERO cvars --
    # "ok" over an empty request is success wearing silence's clothes.
    _out["n_read"] = len(_out["cvars"])
    if not NAMES:
        _fail.append("zero cvars requested -- nothing to read")
    _out["control_failures"] = _fail
    _out["controls_ok"] = not _fail
    _out["ok"] = not _fail
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-800:]

print("__LL__" + json.dumps(_out))
