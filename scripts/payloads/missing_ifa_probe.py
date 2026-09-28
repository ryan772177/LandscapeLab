"""READ-ONLY: what ARE the residency-missing InstancedFoliageActors?

Brief 3 Task 0 diagnosis. The same 12 IFAs at vista (and 1 at
near_ground) are missing at BOTH 180 and 300 warm-up frames -- not a
streaming tail, a class that never loads. The editor world holds every
actor, so inspect them there: instance counts per component, bounds
extent, runtime grid, spatial flag. An IFA with ZERO instances would be
dropped from streaming generation (no content, no cell) while its
descriptor still carries bounds -- which would make the EXPECTATION
wrong, not the world.
"""
import json as _json
import traceback as _tb

import unreal as _u

NAMES = __NAMES__

_out = {"ok": False, "rows": []}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _byname = {}
    for _a in _eas.get_all_level_actors():
        _byname[_a.get_name()] = _a
    for _n in NAMES:
        _row = {"name": _n}
        _a = _byname.get(_n)
        if _a is None:
            _row["editor_world"] = "NOT LOADED in editor world"
            _out["rows"].append(_row)
            continue
        _row["class"] = type(_a).__name__
        try:
            _row["runtime_grid"] = str(_a.get_editor_property("runtime_grid"))
        except Exception as _e:
            _row["runtime_grid_err"] = str(_e)[:80]
        try:
            _row["is_spatially_loaded"] = bool(
                _a.get_editor_property("is_spatially_loaded"))
        except Exception:
            pass
        _tot = 0
        _comps = 0
        try:
            for _c in _a.get_components_by_class(
                    _u.FoliageInstancedStaticMeshComponent):
                _comps += 1
                _tot += int(_c.get_instance_count())
        except Exception as _e:
            _row["count_err"] = str(_e)[:100]
        _row["foliage_components"] = _comps
        _row["instances_total"] = _tot
        try:
            _o, _ext = _a.get_actor_bounds(False)
            _row["bounds_extent_m"] = [round(float(_ext.x) / 100, 1),
                                       round(float(_ext.y) / 100, 1),
                                       round(float(_ext.z) / 100, 1)]
        except Exception as _e:
            _row["bounds_err"] = str(_e)[:80]
        _out["rows"].append(_row)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-500:]

print("__LL__" + _json.dumps(_out))
