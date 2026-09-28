"""Create one 1-frame Level Sequence per bench station. IDEMPOTENT.

MRQ renders SEQUENCES, not loose cameras, so a still needs a sequence whose
only content is a camera cut to that station's CameraActor for a single frame.
ONE tiny LevelSequence asset per station (holding a possessable, a camera-cut
track and a section), rebuilt from scratch each run so it cannot drift from the
actor it points at.

Run via: python scripts/ue_exec.py scripts/payloads/bench_make_stills.py
"""
import json as _json

import unreal as _u

PKG = "/Game/Bench"
FPS = 30
# THE STATION LIST COMES FROM THE CALLER. It used to be hardcoded here as
# well as in bench_capture, and on 2026-09-11 that cost a silent failure
# of exactly the shape NN24 predicts: `ground` was added to
# bench_capture.STATIONS and not to this copy, so /Game/Bench/
# Bench_Still_ground was never created, MRQ was handed a job whose
# SEQUENCE DOES NOT EXIST, and it rendered nothing -- no frames, no
# error, three runs and ~20 minutes of polling an idle log. Two lists
# that must agree are one list, badly stored.
STATIONS = _json.loads('__STATIONS_JSON__')

_out = {"ok": False, "error": None, "sequences": [],
        "_readback_note": ("playback/possessables/tracks are read off the "
                           "resident in-memory sequence just created (not a "
                           "disk load); `saved` is the persistence signal")}
try:
    # NN13: zero stations is not success (the exact silent-failure this file's
    # header documents).
    if not STATIONS:
        raise ValueError("STATIONS is empty -- refusing (zero stills built)")
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # Collect cameras by label AND record collisions (rule 8: labels collide).
    _cams = {}
    _collisions = set()
    for _a in _eas.get_all_level_actors():
        try:
            _lbl = _a.get_actor_label()
        except Exception:
            continue
        if _lbl.startswith("Bench_"):
            if _lbl in _cams:
                _collisions.add(_lbl)
            _cams[_lbl] = _a
    _out["label_collisions"] = sorted(_collisions)

    _tools = _u.AssetToolsHelpers.get_asset_tools()
    for _st in STATIONS:
        _name = "Bench_Still_" + _st
        _path = PKG + "/" + _name
        _lbl = "Bench_" + _st
        # Per-station try: one bad station records its own error and continues
        # rather than aborting the whole batch.
        try:
            if _lbl in _collisions:
                _out["sequences"].append(
                    {"name": _name, "error": "label %r collides -- ambiguous "
                     "camera" % _lbl})
                continue
            _cam = _cams.get(_lbl)
            if _cam is None:
                _out["sequences"].append({"name": _name,
                                          "error": "camera missing"})
                continue
            if not isinstance(_cam, _u.CameraActor):
                _out["sequences"].append(
                    {"name": _name, "error": "label %r is a %s, not a "
                     "CameraActor" % (_lbl, type(_cam).__name__)})
                continue
            if _u.EditorAssetLibrary.does_asset_exist(_path):
                _u.EditorAssetLibrary.delete_asset(_path)
            _seq = _tools.create_asset(_name, PKG, _u.LevelSequence,
                                       _u.LevelSequenceFactoryNew())
            if _seq is None:
                _out["sequences"].append({"name": _name,
                                          "error": "create_asset returned None"})
                continue
            _seq.set_display_rate(_u.FrameRate(FPS, 1))
            _seq.set_playback_start(0)
            _seq.set_playback_end(1)          # exactly ONE frame: [0, 1)

            _bind = _seq.add_possessable(_cam)
            _bid = _u.MovieSceneObjectBindingID()
            _bid.set_editor_property("guid", _bind.get_id())
            _track = _seq.add_track(_u.MovieSceneCameraCutTrack)
            _sec = _track.add_section()
            _sec.set_range(0, 1)
            _sec.set_camera_binding_id(_bid)
            _saved = bool(_u.EditorAssetLibrary.save_asset(_path))

            _rb = _u.EditorAssetLibrary.load_asset(_path)
            if _rb is None:
                _out["sequences"].append({"name": _name,
                                          "error": "read-back load returned None"})
                continue
            _loc = _cam.get_actor_location()
            _cc = _cam.camera_component
            _out["sequences"].append({
                "name": _name,
                "asset": _path,
                "saved": _saved,
                "camera": _cam.get_actor_label(),
                "camera_location_cm": [round(_loc.x, 1), round(_loc.y, 1),
                                       round(_loc.z, 1)],
                "camera_fov_h": (float(_cc.get_editor_property("field_of_view"))
                                 if _cc else None),
                "playback_frames": _rb.get_playback_end() - _rb.get_playback_start(),
                "possessables": [str(_b.get_name()) for _b in _rb.get_possessables()],
                "tracks": [t.get_class().get_name() for t in _rb.get_tracks()],
            })
        except Exception as _se:
            _out["sequences"].append({"name": _name,
                                      "error": "station failed: %s"
                                      % str(_se)[:200]})
            continue
    del _w
    # Top-level verdict: every station must have produced a SAVED sequence.
    _built = [s for s in _out["sequences"] if s.get("asset") and s.get("saved")]
    _out["built"] = len(_built)
    _out["ok"] = (len(_built) == len(STATIONS))
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
