"""READ-ONLY: 3D closest-point distance of named actor DESCS from a point.

Brief 3 Task 0 diagnosis, round 2: how far inside the 768 m sphere do the
still-missing actors' desc bounds reach? If every one grazes the rim
(within a cell-quantisation margin), the residual is the engine's
cell-level discretisation, not a streaming defect.
Run via ue_exec with --set NAMES= LOC_X= LOC_Y= LOC_Z= RADIUS_CM=
"""
import json as _json
import math as _math

import unreal as _u

NAMES = __NAMES__
LOC_X = float("__LOC_X__")
LOC_Y = float("__LOC_Y__")
LOC_Z = float("__LOC_Z__")
R = float("__RADIUS_CM__")

_out = {"ok": False, "rows": [], "radius_cm": R}
try:
    _box = _u.Box()
    _box.min = _u.Vector(LOC_X - 3 * R, LOC_Y - 3 * R, -1000000.0)
    _box.max = _u.Vector(LOC_X + 3 * R, LOC_Y + 3 * R, 1000000.0)
    _box.is_valid = True
    _ret = _u.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(_box)
    _descs = _ret if not isinstance(_ret, tuple) else next(
        (p for p in _ret if hasattr(p, "__len__")
         and not isinstance(p, (str, bytes))), None)
    _want = set(NAMES)
    for _d in (_descs or []):
        _n = str(_d.get_editor_property("name"))
        if _n not in _want:
            continue
        _b = _d.get_editor_property("bounds")
        _cx = min(max(LOC_X, float(_b.min.x)), float(_b.max.x))
        _cy = min(max(LOC_Y, float(_b.min.y)), float(_b.max.y))
        _cz = min(max(LOC_Z, float(_b.min.z)), float(_b.max.z))
        _dist = _math.sqrt((_cx - LOC_X) ** 2 + (_cy - LOC_Y) ** 2
                           + (_cz - LOC_Z) ** 2)
        _out["rows"].append({
            "name": _n,
            "closest_point_dist_m": round(_dist / 100.0, 1),
            "inside_sphere_by_m": round((R - _dist) / 100.0, 1),
            "bounds_min": [round(float(_b.min.x) / 100), round(float(_b.min.y) / 100), round(float(_b.min.z) / 100)],
            "bounds_max": [round(float(_b.max.x) / 100), round(float(_b.max.y) / 100), round(float(_b.max.z) / 100)]})
    _out["found"] = len(_out["rows"])
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-400:]

print("__LL__" + _json.dumps(_out))
