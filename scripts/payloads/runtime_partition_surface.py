"""READ-ONLY: enumerate the reflected Python surface of one runtime
partition object, and try both spellings of the range property. The
'loading_range' read refused with 'Failed to find property' although
RuntimePartition.h:103-104 declares it public EditAnywhere -- per
ue-api-resolution the reflected surface is the contract, so enumerate it
instead of guessing again."""
import json as _json

import unreal as _u

_out = {"ok": False}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _wp = _w.get_world_settings().get_editor_property("world_partition")
    _rh = _u.find_object(_wp, "WorldPartitionRuntimeHashSet_0")
    _o = _u.find_object(_rh, "RuntimePartitionLHGrid_0")
    _out["path"] = _o.get_path_name()
    _out["dir_filtered"] = sorted(
        n for n in dir(_o)
        if any(k in n.lower() for k in ("load", "range", "name", "cell",
                                        "hlod", "priority", "bounds")))
    for _try in ("LoadingRange", "loading_range", "CellSize", "cell_size",
                 "Name", "HLODIndex"):
        try:
            _v = _o.get_editor_property(_try)
            _out["get_" + _try] = str(_v)
        except Exception as _e:
            _out["get_" + _try + "_err"] = str(_e)[:120]
    _out["python_class"] = type(_o).__name__
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)

print("__LL__" + _json.dumps(_out))
