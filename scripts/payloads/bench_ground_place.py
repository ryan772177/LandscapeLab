"""Find-or-create the Bench_ground camera actor, by LABEL.

RULED BY RYAN 2026-09-11. The station is a durable part of the world so
the surface metrics are re-measurable, not a transform that lives only in
a shell history.

FIND-OR-CREATE BY LABEL, not spawn: re-running must MOVE the existing
actor, never accumulate duplicates (standing rule 3's shape). The
transform is read back FROM THE ACTOR afterwards, because a set that was
silently clamped or ignored would otherwise be indistinguishable from
one that took.
"""
import json

import unreal as _u

LABEL = "Bench_ground"
LOC = (__LOC_X__, __LOC_Y__, __LOC_Z__)
ROT_PYR = (__PITCH__, __YAW__, 0.0)
FOV = __FOV__

_out = {"ok": False, "label": LABEL}
try:
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _found = [a for a in _sub.get_all_level_actors()
              if a.get_actor_label() == LABEL]
    _out["found_existing"] = len(_found)
    # rule 8: labels collide, so refuse an ambiguous match and confirm the
    # class before mutating (do not move an unrelated actor sharing the label).
    if len(_found) > 1:
        raise RuntimeError(
            "%d actors share label %r -- refusing to mutate by an ambiguous "
            "label" % (len(_found), LABEL))
    if _found:
        _cam = _found[0]
        if not isinstance(_cam, _u.CameraActor):
            raise RuntimeError("label %r is held by a %s, not a CameraActor"
                               % (LABEL, type(_cam).__name__))
        _out["action"] = "reused"
    else:
        _cam = _sub.spawn_actor_from_class(
            _u.CameraActor, _u.Vector(*LOC),
            _u.Rotator(roll=0.0, pitch=ROT_PYR[0], yaw=ROT_PYR[1]))
        if _cam is None:
            raise RuntimeError("spawn_actor_from_class returned None")
        _cam.set_actor_label(LABEL)
        _out["action"] = "created"

    # ⛔ MARK IT DIRTY, OR THE MOVE IS NOT SAVED AND NOBODY IS TOLD.
    # Measured 2026-09-12: three sessions moved this actor, each read the
    # transform back EXACT (max_loc_err_cm 0.0), each rendered from the
    # new place -- and none of it persisted, because
    # set_actor_location_and_rotation does not dirty the package. The
    # dirty census then reported "nothing dirty" and that read as
    # success. A new session loaded the actor from disk at the ORIGINAL
    # v1 location and the residency gate caught the mismatch against the
    # derivation. A read-back that proves the setter ran IN MEMORY is not
    # evidence that anything was written.
    _cam.modify()
    _cam.set_actor_location_and_rotation(
        _u.Vector(*LOC),
        _u.Rotator(roll=0.0, pitch=ROT_PYR[0], yaw=ROT_PYR[1]),
        False, True)
    _cam.modify()
    try:
        _pkg = _cam.get_outermost()
        _pkg.set_dirty_flag(True)
        _out["package"] = str(_pkg.get_path_name())
        _out["dirty_after_move"] = bool(_pkg.is_dirty())
    except Exception as _e:
        _out["dirty_note"] = "%s: %s" % (type(_e).__name__, _e)
    try:
        _cc = _cam.camera_component
        _cc.set_editor_property("field_of_view", float(FOV))
    except Exception as _e:
        _out["fov_note"] = "%s: %s" % (type(_e).__name__, _e)

    # spatially loaded FALSE so the station is visible whatever cell is
    # streamed -- the same reason apply_lighting pins its rig
    try:
        _cam.set_editor_property("is_spatially_loaded", False)
    except Exception as _e:
        _out["spatial_note"] = "%s: %s" % (type(_e).__name__, _e)

    _l = _cam.get_actor_location()
    _r = _cam.get_actor_rotation()
    _out["location_readback_cm"] = [round(_l.x, 1), round(_l.y, 1),
                                    round(_l.z, 1)]
    _out["rotation_readback_pyr"] = [round(_r.pitch, 4), round(_r.yaw, 4),
                                     round(_r.roll, 4)]
    try:
        _out["fov_readback"] = float(
            _cam.camera_component.get_editor_property("field_of_view"))
    except Exception:
        _out["fov_readback"] = None
    try:
        _out["spatial_readback"] = bool(
            _cam.get_editor_property("is_spatially_loaded"))
    except Exception:
        _out["spatial_readback"] = None
    _out["max_loc_err_cm"] = max(
        abs(_out["location_readback_cm"][i] - LOC[i]) for i in range(3))
    _out["max_rot_err_deg"] = max(
        abs(_out["rotation_readback_pyr"][0] - ROT_PYR[0]),
        abs(((_out["rotation_readback_pyr"][1] - ROT_PYR[1]) + 180) % 360 - 180))
    _out["fov_err"] = (abs(_out["fov_readback"] - float(FOV))
                       if _out["fov_readback"] is not None else None)
    # ok must reflect the read-backs AND that the package is dirtied (the whole
    # 2026-09-12 lesson: a move that did not dirty the package did not persist).
    # NOTE persistence is DEFERRED to an external save; this only dirties.
    _out["persistence"] = "deferred to an external save; this payload only dirties"
    _out["ok"] = (
        _out["max_loc_err_cm"] <= 1.0
        and _out["max_rot_err_deg"] <= 0.1
        and _out["fov_err"] is not None and _out["fov_err"] <= 0.01
        and _out.get("spatial_readback") is False
        and _out.get("dirty_after_move") is True)
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-900:]

print("__LL__" + json.dumps(_out))
