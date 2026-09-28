"""Create the Bench_Dolly Level Sequence. IDEMPOTENT (delete-and-rebuild).

Per benchmark.json: a camera cut from Bench_near_ground, 6.0 s at 30 fps,
moving along the camera's FORWARD VECTOR at 1.4 m/s -- 8.4 m total, straight
line, NO EASING. "No easing" is why every key is added with
MovieSceneKeyInterpolation.LINEAR and not the AUTO default: an eased dolly
accelerates, and temporal_stability.py would read that acceleration as a
changing residual and charge it to the world.

The end point is computed from the camera's OWN read-back rotation, not from
the numbers in the recipe, so the path cannot drift from the actor.

YAW: WHY AN OVERRIDE EXISTS, AND WHY IT DOES NOT MUTATE THE ACTOR
    E4 measured the actor's own heading walking INTO dappled canopy shadow --
    the lit share of the ground half fell 41.1% -> 17.7% over 4.2 m. Choosing
    a replacement heading therefore has to change the DIRECTION OF TRAVEL
    while leaving `Bench_near_ground` exactly where the ratified 6 s
    `Bench_Dolly`, the station shots and the perf stations all expect it.

    That is possible because the sequence POSSESSES the camera and keys
    Rotation.X/Y/Z itself: during playback the sequence's keys drive the
    actor, so a per-sequence heading needs no edit to the level at all.
    Rotating the actor and rotating it back would be a mutation with a
    restore step, and a restore step is a thing that can be skipped.

    `YAW=actor` reproduces the pre-2026-09-08 behaviour EXACTLY -- it is the
    read-back value, not a copy of it -- so the ratified dolly is unchanged.

Run via (all THREE parameters are REQUIRED since 2026-09-08):

    python scripts/ue_exec.py scripts/payloads/bench_make_dolly.py \
        --set SEQ_NAME=Bench_Dolly --set SECONDS=6.0 \
        --set YAW=actor                                     # the ratified one
    python scripts/ue_exec.py scripts/payloads/bench_make_dolly.py \
        --set SEQ_NAME=Bench_Dolly_Sunlit --set SECONDS=3.0 \
        --set YAW=<measured>                                 # E4

`YAW` is `actor` or a yaw in DEGREES. Pitch and roll always come from the
actor: E4 re-heads the walk, it does not re-frame the shot, and this project
has set a -25 deg ROLL believing it was pitch three times.
"""
import json as _json
import math as _m

import unreal as _u

SEQ_PKG = "/Game/Bench"
FPS = 30
SPEED_M_S = 1.4
CAM_LABEL = "Bench_near_ground"

# PARAMETERISED 2026-09-08 for E4, which needs a 3 s SUNLIT variant beside the
# ratified 6 s dolly. Both are bare scalars, so `--set` is safe (R-UEEXEC:
# never send a /Game/ path or anything quoted through the shell).
#
# The builder DELETES AND REBUILDS the asset it is given, so a distinct
# SEQ_NAME leaves Bench_Dolly untouched. Passing SEQ_NAME=Bench_Dolly still
# rebuilds the original exactly as before.
SEQ_NAME = r"__SEQ_NAME__"
# Kept as RAW strings and parsed INSIDE the try below, so a missing/invalid
# --set fails into _out["error"] as structured JSON rather than crashing at
# import with no __LL__ marker (the old `float("__SECONDS__")` at module scope
# did exactly that -- a different, harder-to-parse contract from YAW).
SECONDS_RAW = r"__SECONDS__"
# "actor" or a yaw in degrees.
YAW = r"__YAW__"

_out = {"ok": False, "error": None}
try:
    SECONDS = float(SECONDS_RAW)
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # ---- the station camera ----------------------------------------------
    # Collect ALL matches and refuse on a collision (rule 8: labels collide);
    # the old first-match break would silently drive the dolly off the wrong
    # actor's transform.
    _cams = [_a for _a in _eas.get_all_level_actors()
             if _a and _a.get_actor_label() == CAM_LABEL]
    if not _cams:
        raise RuntimeError("no actor labelled " + CAM_LABEL)
    if len(_cams) > 1:
        raise RuntimeError("%d actors share label %r -- refusing to guess "
                           "which is the station camera" % (len(_cams),
                                                            CAM_LABEL))
    _cam = _cams[0]

    _loc = _cam.get_actor_location()
    _rot = _cam.get_actor_rotation()

    # Pitch and roll ALWAYS come from the actor; only yaw may be overridden.
    if YAW.strip().lower() == "actor":
        _yaw_deg = float(_rot.yaw)
        _yaw_src = "actor read-back"
    else:
        _yaw_deg = float(YAW)
        _yaw_src = "override"

    _p = _m.radians(_rot.pitch)
    _y = _m.radians(_yaw_deg)
    _fwd = (_m.cos(_p) * _m.cos(_y), _m.cos(_p) * _m.sin(_y), _m.sin(_p))
    _dist_cm = SPEED_M_S * SECONDS * 100.0
    _end = (_loc.x + _fwd[0] * _dist_cm,
            _loc.y + _fwd[1] * _dist_cm,
            _loc.z + _fwd[2] * _dist_cm)
    _out["camera"] = {
        "label": CAM_LABEL,
        "start_cm": [round(_loc.x, 3), round(_loc.y, 3), round(_loc.z, 3)],
        "rotation_deg": [round(_rot.pitch, 4), round(_yaw_deg, 4), round(_rot.roll, 4)],
        "actor_rotation_deg": [round(_rot.pitch, 4), round(_rot.yaw, 4),
                               round(_rot.roll, 4)],
        "yaw_source": _yaw_src,
        "yaw_arg": YAW,
        "actor_mutated": False,
        "forward_unit": [round(v, 6) for v in _fwd],
        "travel_cm": _dist_cm,
        "end_cm": [round(v, 3) for v in _end],
        "_note": ("travel is along the FULL 3D forward vector as benchmark.json "
                  "declares, so a -2 deg pitch makes the path descend "
                  "%.1f cm over the walk" % abs(_fwd[2] * _dist_cm)),
    }

    # ---- delete-and-rebuild the sequence (idempotent) --------------------
    _path = SEQ_PKG + "/" + SEQ_NAME
    if _u.EditorAssetLibrary.does_asset_exist(_path):
        _u.EditorAssetLibrary.delete_asset(_path)
        _out["existing_asset"] = "deleted and rebuilt (idempotent)"
    _tools = _u.AssetToolsHelpers.get_asset_tools()
    _seq = _tools.create_asset(SEQ_NAME, SEQ_PKG, _u.LevelSequence,
                               _u.LevelSequenceFactoryNew())
    if _seq is None:
        raise RuntimeError("create_asset returned None for " + _path)

    _seq.set_display_rate(_u.FrameRate(FPS, 1))
    _seq.set_playback_start_seconds(0.0)
    _seq.set_playback_end_seconds(SECONDS)

    # ---- possess the camera, cut to it -----------------------------------
    _bind = _seq.add_possessable(_cam)
    _bid = _u.MovieSceneObjectBindingID()
    _bid.set_editor_property("guid", _bind.get_id())

    _cut_track = _seq.add_track(_u.MovieSceneCameraCutTrack)
    _cut = _cut_track.add_section()
    _cut.set_range_seconds(0.0, SECONDS)
    _cut.set_camera_binding_id(_bid)

    # ---- the straight-line move ------------------------------------------
    _xf_track = _bind.add_track(_u.MovieScene3DTransformTrack)
    _xf = _xf_track.add_section()
    _xf.set_range_seconds(0.0, SECONDS)

    _chans = {}
    for _c in _xf.get_all_channels():
        _chans[str(_c.channel_name)] = _c
    _out["transform_channels"] = sorted(_chans.keys())

    _end_frame = int(round(FPS * SECONDS))
    if _end_frame < 1:
        raise RuntimeError("SECONDS=%s gives end_frame %d (<1 frame); refusing "
                           "to build a zero-length dolly" % (SECONDS_RAW,
                                                             _end_frame))
    _keyed = {}
    _targets = {
        "Location.X": (_loc.x, _end[0]),
        "Location.Y": (_loc.y, _end[1]),
        "Location.Z": (_loc.z, _end[2]),
        "Rotation.X": (_rot.roll, _rot.roll),
        "Rotation.Y": (_rot.pitch, _rot.pitch),
        "Rotation.Z": (_yaw_deg, _yaw_deg),
    }
    for _name, (_v0, _v1) in _targets.items():
        _ch = _chans.get(_name)
        if _ch is None:
            _keyed[_name] = "CHANNEL ABSENT"
            continue
        _ch.add_key(_u.FrameNumber(0), float(_v0), 0.0,
                    _u.MovieSceneTimeUnit.DISPLAY_RATE,
                    _u.MovieSceneKeyInterpolation.LINEAR)
        _ch.add_key(_u.FrameNumber(_end_frame), float(_v1), 0.0,
                    _u.MovieSceneTimeUnit.DISPLAY_RATE,
                    _u.MovieSceneKeyInterpolation.LINEAR)
        _keyed[_name] = [round(float(_v0), 3), round(float(_v1), 3)]
    _out["keys"] = _keyed
    _out["end_frame"] = _end_frame
    # NN13: if the expected transform channels were not found, ZERO keys were
    # written and the dolly moves nothing -- do not report success.
    _absent = [k for k, v in _keyed.items() if v == "CHANNEL ABSENT"]
    if _absent:
        raise RuntimeError("transform channels absent, no keys written: %s "
                           "(found %s)" % (_absent, _out["transform_channels"]))

    # save_asset's bool return is the on-disk-persistence signal (rule 12).
    _out["saved"] = bool(_u.EditorAssetLibrary.save_asset(_path))
    if not _out["saved"]:
        raise RuntimeError("save_asset returned False for " + _path)

    # ---- READ BACK the sequence METADATA (rate/range/tracks). NOTE the `keys`
    #      above are the SET values echoed, not a re-read of the channels, and
    #      load_asset returns the resident object -- so this verifies the
    #      sequence structure and _saved is the persistence evidence; it does
    #      not re-read the transform keys themselves. ----
    _rb = _u.EditorAssetLibrary.load_asset(_path)
    if _rb is None:
        raise RuntimeError("read-back load_asset returned None for " + _path)
    _dr = _rb.get_display_rate()
    _out["readback"] = {
        "asset": _path,
        "display_rate": "%d/%d" % (_dr.numerator, _dr.denominator),
        "playback_start_s": _rb.get_playback_start_seconds(),
        "playback_end_s": _rb.get_playback_end_seconds(),
        "playback_start_frame": _rb.get_playback_start(),
        "playback_end_frame": _rb.get_playback_end(),
        "possessables": [str(_b.get_name()) for _b in _rb.get_possessables()],
        "tracks": [t.get_class().get_name() for t in _rb.get_tracks()],
    }
    _frames = _rb.get_playback_end() - _rb.get_playback_start()
    _out["readback"]["frames_rendered"] = _frames
    _out["readback"]["_frame_note"] = (
        "playback is [%d, %d); MRQ renders %d frames, so the LAST rendered "
        "frame is %d and sits %.3f m along, not the full %.3f m -- the end key "
        "is at frame %d which is one past the last rendered frame."
        % (_rb.get_playback_start(), _rb.get_playback_end(), _frames,
           _frames - 1, (_frames - 1) / float(_end_frame) * (_dist_cm / 100.0),
           _dist_cm / 100.0, _end_frame))
    _out["ok"] = True
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1800:]

print("__LL__" + _json.dumps(_out))
