"""What does 5.8's reflected Python surface offer for CONSOLE VARIABLES?

Needed because SystemLibrary.get_console_variable_*_value returns 0.0 for
a variable that DOES NOT EXIST (KismetSystemLibrary.cpp:610-622: Value is
initialised to 0.0f, FindConsoleVariable returns null, it logs a warning
and returns the 0.0). A reader that cannot tell zero from absent is not
an instrument.

Enumerate rather than guess (docs/ue58-api-protocol.md).
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _out["unreal_console_names"] = sorted(
        n for n in dir(_u) if "onsole" in n or "CVar" in n or "cvar" in n)
    _out["systemlibrary_console"] = sorted(
        n for n in dir(_u.SystemLibrary) if "console" in n.lower())
    # does a warning reach the log we can see? try a name that cannot exist
    _probe = {}
    for _n in ("r.TonemapperFilm", "r.ThisCVarCannotPossiblyExist_zzz"):
        _row = {}
        for _kind, _fn in (("float",
                            _u.SystemLibrary.get_console_variable_float_value),
                           ("int",
                            _u.SystemLibrary.get_console_variable_int_value),
                           ("bool",
                            _u.SystemLibrary.get_console_variable_bool_value)):
            try:
                _row[_kind] = _fn(_n)
                if _kind == "bool":
                    _row[_kind] = bool(_row[_kind])
                else:
                    _row[_kind] = float(_row[_kind])
            except Exception as _e:
                _row[_kind] = "ERR %s: %s" % (type(_e).__name__, _e)
        _probe[_n] = _row
    _out["getter_behaviour"] = _probe
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-800:]

print("__LL__" + json.dumps(_out))
