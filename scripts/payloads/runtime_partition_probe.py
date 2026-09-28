"""READ-ONLY: find the URuntimePartition objects and their loading ranges.

Brief 3 Task 0. `runtime_partitions` is private without AllowPrivateAccess
(measured 2026-09-09, get_editor_property refused), but the partition
objects themselves are ordinary subobjects of the hash set, created
NewObject(this, NAME_None) (WorldPartitionRuntimeHashSet.cpp:271/:288), so
they carry auto class-based names. Two routes, both tried and reported:
find_object over candidate auto names, and ObjectIterator filtered by
class + outer. `loading_range` / `cell_size` / `hlod_index` / `name` are
EditAnywhere or plain UPROPERTYs on URuntimePartition(LHGrid).
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False, "found": [], "route": None}


def _row(o):
    r = {"path": o.get_path_name(), "class": o.get_class().get_name()}
    for p in ("name", "loading_range", "cell_size", "hlod_index"):
        try:
            v = o.get_editor_property(p)
            r[p] = str(v) if p == "name" else (
                int(v) if isinstance(v, (int, float)) else str(v))
        except Exception as e:
            r[p + "_error"] = str(e)[:100]
    return r


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _wp = _w.get_world_settings().get_editor_property("world_partition")
    _rh = _u.find_object(_wp, "WorldPartitionRuntimeHashSet_0")
    _out["runtime_hash"] = _rh.get_path_name() if _rh else None
    if _rh is None:
        raise RuntimeError("hash set subobject not found")

    # Route 1: candidate auto names under the hash set
    _seen = set()
    for _i in range(8):
        for _cls in ("RuntimePartitionLHGrid", "RuntimePartitionPersistent",
                     "RuntimePartitionLevelStreaming"):
            _n = "%s_%d" % (_cls, _i)
            try:
                _o = _u.find_object(_rh, _n)
            except Exception:
                _o = None
            if _o is not None and _o.get_path_name() not in _seen:
                _seen.add(_o.get_path_name())
                _out["found"].append(_row(_o))
    if _out["found"]:
        _out["route"] = "find_object(candidate auto names)"
    else:
        # Route 2: ObjectIterator filtered by class, outer chain = our hash set
        try:
            for _o in _u.ObjectIterator():
                try:
                    if not isinstance(_o, _u.RuntimePartition):
                        continue
                    _outer = _o.get_outer()
                    if _outer is not None and _outer.get_path_name() == _rh.get_path_name():
                        if _o.get_path_name() not in _seen:
                            _seen.add(_o.get_path_name())
                            _out["found"].append(_row(_o))
                except Exception:
                    continue
            _out["route"] = "ObjectIterator"
        except Exception as _e2:
            _out["iterator_error"] = str(_e2)[:200]
    _out["ok"] = bool(_out["found"])
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-600:]

print("__LL__" + _json.dumps(_out))
