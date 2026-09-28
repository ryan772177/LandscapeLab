"""Does a cvar EXIST in this engine, and what does it currently read?

READ-ONLY. An API remembered is an API guessed, and a cvar that does not
exist sets silently and reads back as whatever the caller hoped. The
string getter is the existence test: a missing cvar returns the empty
string, which is distinguishable from any real value including "0".
"""
import json

import unreal as _u

NAMES = "__NAMES__"

_out = {"ok": False, "cvars": {}}
try:
    for _n in [s for s in NAMES.split(",") if s]:
        _row = {}
        try:
            _s = _u.SystemLibrary.get_console_variable_string_value(_n)
        except Exception as _e:
            _s = None
            _row["string_error"] = str(_e)
        _row["string"] = _s
        # EXISTS is decided by the string getter, not by the float getter:
        # the float getter returns 0.0 for a missing cvar, which is a real
        # value a real cvar could also hold.
        _row["exists"] = bool(_s is not None and _s != "")
        for _fn, _tag in (
                (_u.SystemLibrary.get_console_variable_float_value, "float"),
                (_u.SystemLibrary.get_console_variable_int_value, "int"),
                (_u.SystemLibrary.get_console_variable_bool_value, "bool")):
            try:
                _row[_tag] = _fn(_n)
            except Exception:
                _row[_tag] = "ABSENT"
        _out["cvars"][_n] = _row
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-600:]

print("__LL__" + json.dumps(_out))
