"""Is the MRQ render still going? Read-only, cheap, safe to call repeatedly."""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _sub = _u.get_editor_subsystem(_u.MoviePipelineQueueSubsystem)
    _out["is_rendering"] = bool(_sub.is_rendering())
    _ex = _sub.get_active_executor()
    _out["has_active_executor"] = _ex is not None
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out))
