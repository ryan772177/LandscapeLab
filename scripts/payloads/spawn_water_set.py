# spawn_water_set — place the WHOLE Brief-4 water set from the derived plan,
# idempotent by LABEL (spawn_water_plane_payload.txt pattern, batched).
#
# Reads water/alpine_8k_water_plan.json FROM DISK inside the editor process
# (R-UEEXEC: never structured data through --set). Only scalar token:
#   __GO__   "1" = mutate; anything else = DRY-RUN (standing rule 8) —
#            reports world, plan totals, per-label exists/spawn intent,
#            touches nothing.
#
# Rule 11 in-band: the report carries the editor world path so the GO=0 run
# answers the wrong-level question BEFORE GO=1 mutates.
# Rotator is (ROLL, PITCH, YAW) — roll first (docs/ue58-api-protocol.md,
# the camera-mirror trap). Verticals use pitch 90 + plan yaw.
# is_spatially_loaded = False on every plane (one quad is free to keep
# resident; a water sheet must never fall out of a shot).
import json as _json
import os as _os
import unreal as _u

_out = {"ok": False, "mode": None, "world": None, "plan": None,
        "spawned": 0, "updated": 0, "actors": [], "error": None}
try:
    _go = "__GO__" == "1"
    _out["mode"] = "GO" if _go else "DRY-RUN"
    _out["world"] = _u.get_editor_subsystem(
        _u.UnrealEditorSubsystem).get_editor_world().get_path_name()

    if _go and "/Game/Alpine8K" not in _out["world"]:
        raise RuntimeError("REFUSE (rule 11): editor world is %s, expected "
                           "/Game/Alpine8K" % _out["world"])

    _root = _os.path.dirname(_os.path.normpath(
        _u.Paths.project_dir().rstrip("/\\")))
    _plan_path = _os.path.join(_root, "water", "alpine_8k_water_plan.json")
    with open(_plan_path, "r", encoding="utf-8") as _f:
        _plan = _json.load(_f)
    _items = [p for s in _plan["surfaces"] for p in s["planes"]] \
        + _plan["falls"]
    _out["plan"] = {"path": _plan_path, "items": len(_items),
                    "totals": _plan.get("totals")}

    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _by_label = {}
    for _a in (_eas.get_all_level_actors() or []):
        _by_label[_a.get_actor_label()] = _a

    _mesh = _u.load_asset(_plan["mesh"].split(".")[0])
    _mat = _u.load_asset(_plan["material"])
    if _mesh is None or _mat is None:
        raise RuntimeError("plane mesh or water material missing: %s / %s"
                           % (_plan["mesh"], _plan["material"]))

    for _it in _items:
        _label = _it["label"]
        _exists = _label in _by_label
        _rec = {"label": _label, "exists": _exists}
        if _go:
            _loc = _u.Vector(float(_it["cx"]), float(_it["cy"]),
                             float(_it["cz"]))
            _rot = _u.Rotator(0.0, float(_it.get("pitch", 0.0)),
                              float(_it.get("yaw", 0.0)))  # ROLL, PITCH, YAW
            _prior = _by_label.get(_label)
            if _prior is not None and not isinstance(_prior,
                                                     _u.StaticMeshActor):
                raise RuntimeError("label collision: %s is a %s, not a "
                                   "StaticMeshActor (rule 8 — identify by "
                                   "signature)" % (_label,
                                                   type(_prior).__name__))
            _actor = _prior or _eas.spawn_actor_from_class(
                _u.StaticMeshActor, _loc)
            _actor.set_actor_label(_label)
            _actor.set_actor_location(_loc, False, False)
            _actor.set_actor_rotation(_rot, False)
            _actor.set_actor_scale3d(_u.Vector(float(_it["sx"]),
                                               float(_it["sy"]), 1.0))
            _smc = _actor.static_mesh_component
            # set_static_mesh returns False both on failure AND on a
            # no-change static component — only call on a real difference
            # (measured 2026-09-01, spawn_water_plane_payload.txt).
            if _smc.static_mesh != _mesh:
                if not bool(_smc.set_static_mesh(_mesh)):
                    raise RuntimeError("set_static_mesh False on REAL change"
                                       " for %s" % _label)
            _smc.set_material(0, _mat)
            _smc.set_editor_property("mobility",
                                     _u.ComponentMobility.STATIC)
            _actor.set_editor_property("is_spatially_loaded", False)
            # read-back (rule 12): location + rotation + scale from the actor
            _rl = _actor.get_actor_location()
            _rr = _actor.get_actor_rotation()
            _rs = _actor.get_actor_scale3d()
            _rm = _smc.get_material(0)
            _rec["readback"] = {
                "loc": [float(_rl.x), float(_rl.y), float(_rl.z)],
                "rot_rpy": [float(_rr.roll), float(_rr.pitch),
                            float(_rr.yaw)],
                "scale": [float(_rs.x), float(_rs.y), float(_rs.z)],
                "material": _rm.get_path_name() if _rm else None}
            if _exists:
                _out["updated"] += 1
            else:
                _out["spawned"] += 1
        _out["actors"].append(_rec)
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:600]
print("__LL__" + _json.dumps(_out, default=str))
