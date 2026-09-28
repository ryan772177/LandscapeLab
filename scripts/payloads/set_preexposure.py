"""Set CachedLightingPreExposure and PROVE the value landed.

RULED BY RYAN 2026-09-12: the pre-exposure fence is lifted for this test.

THE HYPOTHESIS UNDER TEST. near_ground measures shadow_tint_B 1.8051
against a 1.60 ceiling -- shade too blue -- and doubling Mie moved it the
WRONG WAY (1.8051 -> 1.8379) while dropping scene luminance 9%. Blue
staying pinned while luminance falls is the signature of a source colour
that CANNOT MOVE, which is what a CLIPPED real-time sky capture would
look like. The editor warns on every lighting apply that sky captures are
being clipped.

WHY 16 AND NOT A SMALL STEP. Pre-exposure is a MULTIPLIER: each doubling
buys 1 EV of headroom. The default 4 gives a usable range of about
[-8, +12] EV; the warning names 14, which is ~2 EV over, so 4 -> 16.
This is sized to RESOLVE the clipping outright if clipping is real. A
timid step risks a null result that means "not enough" rather than "not
the cause", and the whole value of this test is that a null result KILLS
the hypothesis. (16 is the value this test was designed around; the value
actually applied is the WANT parameter, so this rationale holds only when
WANT is 16.)

THE VALUE IS SET AND READ BACK. A console command that silently does
nothing is indistinguishable from one that worked, and the string getter
is the existence test -- the float getter returns 0.0 for a missing
variable (KismetSystemLibrary.cpp:610-622), which is how four
non-existent names once read as "all zeroed, non-default, the finding".
"""
import json

import unreal as _u

NAME = "r.EyeAdaptation.CachedLightingPreExposure"
WANT = __WANT__

_out = {"ok": False, "name": NAME, "requested": WANT}
try:
    _sl = _u.SystemLibrary

    def _read():
        _s = _sl.get_console_variable_string_value(NAME)
        if _s is None or _s == "":
            return None, ""
        return float(_sl.get_console_variable_float_value(NAME)), _s

    _before, _bs = _read()
    _out["before"] = _before
    _out["before_string"] = _bs
    if _before is None:
        # Refuse through the normal single print with ok:False -- NOT a
        # raise SystemExit(0), which exits SUCCESS on a refusal (a caller keying
        # on exit status would read the refusal as success; the contract is the
        # ok field).
        _out["error"] = ("the variable does not exist -- refusing to set a "
                         "name the engine does not know")
    else:
        # %.9g so the command carries the full requested precision that the
        # read-back is then compared against (%g truncated to 6 sig figs).
        _sl.execute_console_command(None, "%s %.9g" % (NAME, WANT))
        _after, _as = _read()
        _out["after"] = _after
        _out["after_string"] = _as
        _out["landed"] = (_after is not None
                          and abs(_after - float(WANT)) <= 1e-4 * max(1.0, WANT))
        if not _out["landed"]:
            _out["error"] = ("set did NOT take: requested %g, reads %s. A "
                             "console command that silently does nothing looks "
                             "exactly like one that worked." % (WANT, _after))
        _out["ok"] = bool(_out["landed"])
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
