"""Save the dirty external-actor packages, and REPORT which.

The Bench_ground camera is an external actor, so it lands in
__ExternalActors__ rather than the map. R-LIGHTSAVE's lesson applies
verbatim: applied-and-not-saved is reverted by the next crash.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _dirty = [p for p in _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _dirty += [p for p in
               _u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _names = [str(p.get_path_name()) for p in _dirty]
    _out["dirty_before"] = _names
    _ok = _u.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    _out["save_returned"] = bool(_ok)
    _after = [str(p.get_path_name()) for p in
              _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _after += [str(p.get_path_name()) for p in
               _u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _out["dirty_after"] = _after
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-800:]

print("__LL__" + json.dumps(_out))
