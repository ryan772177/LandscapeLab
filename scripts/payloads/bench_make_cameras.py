"""Create (or update) the three benchmark CameraActors. IDEMPOTENT.

FIND-OR-CREATE BY LABEL, so re-running rebuilds deterministically rather than
accumulating duplicates (pipeline rule 3). Ground is TRACED here, never taken
from the heightmap -- perf_budgets.json requires it, for cause: this project
shipped a render/collide divergence of p90 30.98 m once, and the gap measured
across these three stations today ranges 2.3 cm to 1.33 m.

X/Y/yaw/pitch come from _verify/bench/2026-09-05/bench_stations_derived.json
(RECIPES R-BENCHSTATION). Z is trace + eye height.

Run via: python scripts/ue_exec.py scripts/payloads/bench_make_cameras.py
"""
import json as _json

import unreal as _u

EYE_CM = 175.0
FOV_H = 90.0
STATIONS = [
    # label,               x,          y,         pitch,  yaw
    ("Bench_near_ground", -210800.0,  278800.0,   -2.0,  -12.8),
    ("Bench_mid_slope",   -190000.0,  100000.0,   -2.0,  105.0),
    ("Bench_vista",       -216400.0,   63600.0,   -4.0,   60.0),
]

_out = {"error": None, "cameras": [], "created": 0, "updated": 0}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # The editor viewport size. SystemLibrary.get_viewport_size does NOT exist
    # in 5.8 (AttributeError), which is why measure_frame_cost has been
    # recording null; the editor answer is on UnrealEditorSubsystem.
    try:
        _vp = _ues.get_level_viewport_size()
        _out["level_viewport_size"] = [int(_vp.x), int(_vp.y)] if _vp else None
    except Exception as _ve:
        _out["level_viewport_size"] = None
        _out["level_viewport_size_error"] = type(_ve).__name__ + ": " + str(_ve)

    _by_label = {}
    for _a in _eas.get_all_level_actors():
        try:
            _by_label.setdefault(_a.get_actor_label(), []).append(_a)
        except Exception:
            pass

    for _label, _x, _y, _pitch, _yaw in STATIONS:
        _hit = _u.SystemLibrary.line_trace_single(
            _w, _u.Vector(_x, _y, 200000.0), _u.Vector(_x, _y, -20000.0),
            _u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            _u.DrawDebugTrace.NONE, True)
        if not _hit:
            _out["cameras"].append({"label": _label, "error": "TRACE MISSED"})
            continue
        # FHitResult fields are protected in 5.8 Python; to_tuple()[4] is the
        # impact point (scripts/perf_flythrough.py:70).
        _gz = float(_hit.to_tuple()[4].z)
        _loc = _u.Vector(_x, _y, _gz + EYE_CM)
        _rot = _u.Rotator(roll=0.0, pitch=_pitch, yaw=_yaw)

        # Labels collide in this project (rule 8): identify by CLASS as well as
        # label. Refuse if >1 actor holds the label, or if a non-CameraActor
        # holds it (do not relocate or shadow an unrelated actor).
        _all_with_label = _by_label.get(_label, [])
        _cams_with_label = [_a for _a in _all_with_label
                            if isinstance(_a, _u.CameraActor)]
        if len(_all_with_label) > 1 or len(_cams_with_label) > 1:
            _out["cameras"].append({
                "label": _label,
                "error": "AMBIGUOUS: %d actor(s) carry this label (%d cameras); "
                         "refusing to guess which is the station"
                         % (len(_all_with_label), len(_cams_with_label))})
            continue
        if _all_with_label and not _cams_with_label:
            _out["cameras"].append({
                "label": _label,
                "error": "label held by a %s, not a CameraActor; refusing to "
                         "mutate it" % type(_all_with_label[0]).__name__})
            continue
        if _cams_with_label:
            _cam = _cams_with_label[0]
            _was = "updated"
        else:
            _cam = _eas.spawn_actor_from_class(_u.CameraActor, _loc, _rot)
            if _cam is None:
                _out["cameras"].append({"label": _label,
                                        "error": "SPAWN returned None"})
                continue
            _cam.set_actor_label(_label)
            _was = "created"
        _cam.set_actor_location_and_rotation(_loc, _rot, False, True)
        _cam.set_editor_property("is_spatially_loaded", False)
        _comp = _cam.camera_component
        _comp.set_editor_property("field_of_view", FOV_H)

        # READ BACK, never trust the set (the 2026-09-05 FOV pattern) -- AND
        # compare, so a silent drift between requested and applied is a per-
        # station failure rather than two numbers a downstream reader must diff.
        _rl = _cam.get_actor_location()
        _rr = _cam.get_actor_rotation()
        _fov = float(_comp.get_editor_property("field_of_view"))
        _spl = bool(_cam.get_editor_property("is_spatially_loaded"))
        _drift = []
        if (abs(_rl.x - _x) > 1.0 or abs(_rl.y - _y) > 1.0
                or abs(_rl.z - (_gz + EYE_CM)) > 1.0):
            _drift.append("location")
        if abs(_rr.pitch - _pitch) > 0.1 or abs(_rr.yaw - _yaw) > 0.1 \
                or abs(_rr.roll) > 0.1:
            _drift.append("rotation")
        if abs(_fov - FOV_H) > 0.01:
            _drift.append("fov")
        if _spl:
            _drift.append("is_spatially_loaded")
        _entry = {
            "label": _label,
            "action": _was,
            "traced_ground_cm": round(_gz, 3),
            "eye_cm": EYE_CM,
            "requested_location_cm": [_x, _y, round(_gz + EYE_CM, 3)],
            "readback_location_cm": [round(_rl.x, 3), round(_rl.y, 3), round(_rl.z, 3)],
            "requested_rotation_deg": [_pitch, _yaw, 0.0],
            "readback_rotation_deg": [round(_rr.pitch, 4), round(_rr.yaw, 4),
                                      round(_rr.roll, 4)],
            "readback_fov_h_deg": _fov,
            "readback_is_spatially_loaded": _spl,
            "actor_name": _cam.get_name(),
        }
        if _drift:
            _entry["error"] = "read-back drift in: " + ", ".join(_drift)
            _out["cameras"].append(_entry)
            continue
        _out["cameras"].append(_entry)
        if _was == "created":
            _out["created"] += 1
        else:
            _out["updated"] += 1
    del _w
    # Top-level verdict: a per-station miss/ambiguity/drift must not read as
    # success. ok only when every station produced a configured camera.
    _out["stations"] = len(STATIONS)
    _out["stations_failed"] = sum(1 for _c in _out["cameras"] if _c.get("error"))
    _out["ok"] = (_out["error"] is None
                  and (_out["created"] + _out["updated"]) == len(STATIONS))
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
