"""Read every Bench_<station> camera's transform and basis, from the actor.

READ-ONLY. Needed to project a screen pixel to a world position: with a
depth pass giving distance along the ray, the world point is
cam + normalize(forward + x*tan(hfov/2)*right + y*tan(vfov/2)*up) * d.

BASIS VECTORS COME FROM THE ACTOR, not from a yaw/pitch reconstruction.
`greycard_place` already carries the reason in its own docstring -- the
roll-for-pitch confusion has cost this project three defects -- and the
same applies here: a hand-built rotation matrix is a fourth chance to
get it wrong, and the actor will simply answer.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False, "cameras": {}}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _eas.get_all_level_actors():
        _lb = _a.get_actor_label()
        if not _lb.startswith("Bench_"):
            continue
        _st = _lb[len("Bench_"):]
        # Skip the instrument actors placed INTO stations (cards, blockers)
        # -- they are labelled Bench_GreyCard_*, Bench_ShadeCard_* etc.
        if "_" in _st and _st.split("_")[0] in ("GreyCard", "ShadeCard",
                                                "ShadeBlocker"):
            continue
        if "Camera" not in type(_a).__name__:
            continue
        _p = _a.get_actor_location()
        _row = {
            "class": type(_a).__name__,
            "loc_cm": [round(float(_p.x), 3), round(float(_p.y), 3),
                       round(float(_p.z), 3)],
        }
        for _nm, _fn in (("forward", _a.get_actor_forward_vector),
                         ("right", _a.get_actor_right_vector),
                         ("up", _a.get_actor_up_vector)):
            _v = _fn()
            _row[_nm] = [round(float(_v.x), 6), round(float(_v.y), 6),
                         round(float(_v.z), 6)]
        try:
            _cc = _a.get_editor_property("camera_component")
            _row["fov_deg"] = round(float(
                _cc.get_editor_property("field_of_view")), 4)
        except Exception:
            _row["fov_deg"] = None
        _out["cameras"][_st] = _row
    _out["ok"] = bool(_out["cameras"])
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-700:]

print("__LL__" + _json.dumps(_out))
