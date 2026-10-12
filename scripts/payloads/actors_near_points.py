"""actors_near_points -- read-only: which actors (on disk, loaded or not) sit near given points.

Uses WorldPartitionBlueprintLibrary.GetIntersectingActorDescs (WorldPartitionBlueprintLibrary.h:
146-151): actor DESCRIPTORS, read from disk, nothing loaded, nothing dirtied. Reports class,
label, bounds size and package for each descriptor whose bounds are smaller than MAX_EXTENT_CM
(so landscape proxies, HLOD cells and volumes that merely cover the point are summarised, not
listed).
    POINTS        = JSON list of [x, y, z] in cm
    HALF_CM       = half size of the query box
    MAX_EXTENT_CM = descriptors with a larger bounds extent are only counted
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter
import unreal as _u

POINTS = _json.loads("__POINTS__")
HALF_CM = float("__HALF_CM__")
MAX_EXTENT_CM = float("__MAX_EXTENT_CM__")

_out = {"ok": False, "points": []}
try:
    _wbl = _u.WorldPartitionBlueprintLibrary
    # Which level answered (audit F3; standing rule 11).
    _out["level"] = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world().get_path_name()
    for _p in POINTS:
        _box = _u.Box(_u.Vector(_p[0] - HALF_CM, _p[1] - HALF_CM, _p[2] - HALF_CM),
                      _u.Vector(_p[0] + HALF_CM, _p[1] + HALF_CM, _p[2] + HALF_CM))
        # bool + one out-array UFUNCTION -> the array on true, None on false
        # (PyGenUtil.cpp:1161-1184), never a tuple (audit F2).
        _descs = _wbl.get_intersecting_actor_descs(_box)
        if _descs is None:
            _out["points"].append({"point": _p, "query_ok": False})
            continue
        _small, _big = [], _Counter()
        for _d in _descs:
            _b = _d.get_editor_property("bounds")
            _mn, _mx = _b.min, _b.max
            _ext = max(_mx.x - _mn.x, _mx.y - _mn.y, _mx.z - _mn.z)
            # FActorDesc.Class is an FSoftObjectPath whose str() is struct text with an
            # address (audit F1): use the native class name instead.
            _nc = _d.get_editor_property("native_class")
            _cls = _nc.get_name() if _nc else ""
            if _ext > MAX_EXTENT_CM:
                _big[_cls] += 1
                continue
            _c = [(_mn.x + _mx.x) / 2, (_mn.y + _mx.y) / 2, (_mn.z + _mx.z) / 2]
            _small.append({"class": _cls, "label": str(_d.get_editor_property("label")),
                           "center": [round(x) for x in _c],
                           "size": [round(_mx.x - _mn.x), round(_mx.y - _mn.y), round(_mx.z - _mn.z)],
                           "package": str(_d.get_editor_property("actor_package")),
                           "spatial": bool(_d.get_editor_property("is_spatially_loaded"))})
        _small.sort(key=lambda d: (d["center"][0] - _p[0]) ** 2 + (d["center"][1] - _p[1]) ** 2)
        _out["points"].append({"point": _p, "query_ok": True, "n_descs": len(_descs), "large_by_class": dict(_big),
                               "small": _small[:40], "n_small": len(_small)})
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1))
