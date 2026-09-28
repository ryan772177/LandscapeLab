"""READ-ONLY: where do HLOD proxies replace real content at the vista?

Ruling 5, 2026-09-10. 5.8 has no HLOD visualize / proxy-only view mode
(VERIFIED: the r-dot HLOD cvars belong to the legacy LODActor system;
wp.Runtime carries only the on/off toggle and warmup knobs), so the
boundary is MEASURED FROM THE RESIDENCY SETS: actor descriptors give
every actor's position and grid; the 2026-09-09 target-class run's
resident set (runtime grid live in PIE) says which of them were loaded
at the vista station. The boundary sits between the farthest resident
main-grid actor and the nearest non-resident one; the resident HLOD
actors' distance span says where proxies stand.

Same descriptor API as the derived-residency expectation payload
(WorldPartitionBlueprintLibrary.get_intersecting_actor_descs; FActorDesc
name/bounds/runtime_grid/is_spatially_loaded, all BlueprintReadOnly).
Distances are 2D XY from the bounds centre, matching the loading range's
horizontal-radius semantics.

Run via ue_exec with --set LOC_X=<cm> LOC_Y=<cm> RADIUS_CM=<cm>
RESIDENT_FILE=<absolute path to the extracted resident-set json>.
"""
import json as _json
import math as _math
import traceback as _tb

import unreal as _u

LOC_X = float("__LOC_X__")
LOC_Y = float("__LOC_Y__")
R = float("__RADIUS_CM__")
RESIDENT_FILE = r"__RESIDENT_FILE__"

_out = {"ok": False, "loc_cm": [LOC_X, LOC_Y], "radius_cm": R}
try:
    _res = set(_json.load(open(RESIDENT_FILE, encoding="utf-8"))
               ["resident_actors"])
    _out["resident_names"] = len(_res)

    _box = _u.Box()
    _box.min = _u.Vector(LOC_X - R, LOC_Y - R, -1000000.0)
    _box.max = _u.Vector(LOC_X + R, LOC_Y + R, 1000000.0)
    _box.is_valid = True
    _ret = _u.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(_box)
    _descs = None
    if isinstance(_ret, tuple):
        for _part in _ret:
            if hasattr(_part, "__len__") and not isinstance(_part, (str, bytes)):
                _descs = _part
    else:
        _descs = _ret
    _out["descs_in_box"] = len(_descs) if _descs is not None else 0

    _groups = {}
    _matched = 0
    for _d in (_descs or []):
        if not _d.get_editor_property("is_spatially_loaded"):
            continue
        _g = str(_d.get_editor_property("runtime_grid"))
        _g = _g if _g and _g not in ("None", "") else "<main>"
        _b = _d.get_editor_property("bounds")
        _cx = (float(_b.min.x) + float(_b.max.x)) / 2.0
        _cy = (float(_b.min.y) + float(_b.max.y)) / 2.0
        _dist = _math.sqrt((_cx - LOC_X) ** 2 + (_cy - LOC_Y) ** 2)
        _n = str(_d.get_editor_property("name"))
        _is_res = _n in _res
        if _is_res:
            _matched += 1
        _grp = _groups.setdefault(_g, {
            "resident": 0, "non_resident": 0,
            "resident_max_dist_cm": None, "resident_min_dist_cm": None,
            "non_resident_min_dist_cm": None,
            "farthest_resident": None, "nearest_non_resident": None})
        if _is_res:
            _grp["resident"] += 1
            if (_grp["resident_max_dist_cm"] is None
                    or _dist > _grp["resident_max_dist_cm"]):
                _grp["resident_max_dist_cm"] = round(_dist, 1)
                _grp["farthest_resident"] = _n
            if (_grp["resident_min_dist_cm"] is None
                    or _dist < _grp["resident_min_dist_cm"]):
                _grp["resident_min_dist_cm"] = round(_dist, 1)
        else:
            _grp["non_resident"] += 1
            if (_grp["non_resident_min_dist_cm"] is None
                    or _dist < _grp["non_resident_min_dist_cm"]):
                _grp["non_resident_min_dist_cm"] = round(_dist, 1)
                _grp["nearest_non_resident"] = _n
    _out["matched_resident_names"] = _matched
    _out["groups"] = _groups

    # Per-CLASS maxima for the acceptance ("real landscape/foliage to
    # >= 700 m by bounds-centre"): big-bounds actors like nav chunks
    # inflate the group max and are not what the clause is about.
    _cls = {}
    for _d in (_descs or []):
        if not _d.get_editor_property("is_spatially_loaded"):
            continue
        _g = str(_d.get_editor_property("runtime_grid"))
        if _g and _g not in ("None", ""):
            continue
        _n = str(_d.get_editor_property("name"))
        if _n not in _res:
            continue
        _k = ("landscape" if _n.startswith("LandscapeStreamingProxy")
              else "foliage" if _n.startswith("InstancedFoliageActor")
              else "other")
        _b = _d.get_editor_property("bounds")
        _cx = (float(_b.min.x) + float(_b.max.x)) / 2.0
        _cy = (float(_b.min.y) + float(_b.max.y)) / 2.0
        _dist = _math.sqrt((_cx - LOC_X) ** 2 + (_cy - LOC_Y) ** 2)
        _row = _cls.setdefault(_k, {"resident": 0, "max_dist_m": 0.0})
        _row["resident"] += 1
        if _dist / 100.0 > _row["max_dist_m"]:
            _row["max_dist_m"] = round(_dist / 100.0, 1)
    _out["resident_main_by_class"] = _cls
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-700:]

print("__LL__" + _json.dumps(_out))
