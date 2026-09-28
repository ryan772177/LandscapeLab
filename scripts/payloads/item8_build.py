"""item8_build.py -- build the Item-8 scratch MRQ assets under /Game/Scratch/Item8/.

Runs INSIDE the editor via ue_exec, on /Game/Alpine8K. Creates + SAVES four
assets, reads every load-bearing property back off the saved object, and mutates
NOTHING outside /Game/Scratch/Item8/:

  LS_vista, LS_treeline  -- one LevelSequence each, a SPAWNABLE CameraActor at
       the station transform (90 deg horizontal FOV) bound to a CameraCut track,
       60 frames [0,60). Spawnable (not possessable) so the sequence carries its
       own camera and the -game render needs no actor in the shipped level --
       /Game/Alpine8K is never saved and stays byte-identical.
  Cfg_A  -- MoviePipelinePrimaryConfig: DeferredPassBase (lit), PNG output,
       OutputSetting (4K, _active dir), AntiAliasing (1 temporal / 1 spatial,
       60 rendered warm-up frames for WP-stream + GPU settle). NO
       GameOverrideSetting (its disable_hlods default would turn HLOD off in
       BOTH arms and defeat the measurement).
  Cfg_B  -- Cfg_A + ConsoleVariableSetting with StartConsoleCommands
       ["wp.Runtime.HLOD 0"], EndConsoleCommands ["wp.Runtime.HLOD 1"]
       (MoviePipelineConsoleVariableSetting.h:72/:79 -- the post-load channel).

The temp CameraActor is spawned, captured into the spawnable, then destroyed;
the level is never saved. API resolved against 5.8 source (see the item-8 levers
table): create_asset+LevelSequenceFactoryNew; LevelSequenceEditorSubsystem.
add_spawnable_from_instance (:154, non-deprecated); MovieSceneSequenceExtensions.
get_binding_id (:457); MovieSceneCameraCutSection.set_camera_binding_id (:49).
"""
import json as _json

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')

PKG = "/Game/Scratch/Item8"
FPS = 30
FRAMES = int(CFG["frames"])
RES = CFG["res"]                       # [3840, 2160]
ACTIVE_DIR = CFG["active_dir"]         # absolute output dir for the render
WARMUP = int(CFG["render_warm_up_count"])

_out = {"ok": False, "error": None, "sequences": [], "configs": [],
        "pkg": PKG,
        "_note": "read-backs are off the just-created in-memory objects; "
                 "'saved' is the persistence signal, confirmed on disk by the "
                 "host driver's mtime/sha census."}
try:
    _tools = _u.AssetToolsHelpers.get_asset_tools()
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _lses = _u.get_editor_subsystem(_u.LevelSequenceEditorSubsystem)

    # ------------------------------------------------------------------ seqs
    for _st in CFG["stations"]:
        _name = "LS_" + _st["name"]
        _path = PKG + "/" + _name
        try:
            if _u.EditorAssetLibrary.does_asset_exist(_path):
                _u.EditorAssetLibrary.delete_asset(_path)
            _seq = _tools.create_asset(_name, PKG, _u.LevelSequence,
                                       _u.LevelSequenceFactoryNew())
            if _seq is None:
                _out["sequences"].append({"name": _name,
                                          "error": "create_asset -> None"})
                continue
            _seq.set_display_rate(_u.FrameRate(FPS, 1))
            _seq.set_playback_start(0)
            _seq.set_playback_end(FRAMES)

            # temp CameraActor at the station transform; captured into a
            # spawnable, then destroyed. Never saved into the level.
            _cam = _eas.spawn_actor_from_class(
                _u.CameraActor, _u.Vector(0, 0, 0), _u.Rotator(0, 0, 0))
            _loc = _st["loc_cm"]
            _rot = _u.Rotator()
            _rot.pitch = float(_st["pitch_deg"])
            _rot.yaw = float(_st["yaw_deg"])
            _rot.roll = 0.0
            _cam.set_actor_location_and_rotation(
                _u.Vector(_loc[0], _loc[1], _loc[2]), _rot, False, False)
            _cc = _cam.camera_component
            _cc.set_editor_property("field_of_view", float(CFG["fov_h_deg"]))
            _cc.set_editor_property("aspect_ratio", float(RES[0]) / float(RES[1]))
            _cc.set_editor_property("constrain_aspect_ratio", True)

            # READ BACK the temp camera's ACTUAL transform + FOV off the live
            # actor before capture (rule 12): the whole measurement hangs on
            # this camera, so prove the setters took rather than echoing CFG.
            _al = _cam.get_actor_location()
            _ar = _cam.get_actor_rotation()
            _cam_rb = {
                "location_cm": [round(_al.x, 1), round(_al.y, 1),
                                round(_al.z, 1)],
                "pitch_deg": round(_ar.pitch, 3), "yaw_deg": round(_ar.yaw, 3),
                "roll_deg": round(_ar.roll, 3),
                "field_of_view": round(float(
                    _cc.get_editor_property("field_of_view")), 3),
            }
            _eps = 1.0
            _cam_ok = (abs(_al.x - _loc[0]) < _eps and abs(_al.y - _loc[1]) < _eps
                       and abs(_al.z - _loc[2]) < _eps
                       and abs(_ar.pitch - float(_st["pitch_deg"])) < 0.01
                       and abs(_ar.yaw - float(_st["yaw_deg"])) < 0.01
                       and abs(_cam_rb["field_of_view"] - float(CFG["fov_h_deg"]))
                       < 0.01)

            _proxy = _lses.add_spawnable_from_instance(_seq, _cam)
            # destroy the temp actor -- the spawnable template holds a copy
            _eas.destroy_actor(_cam)

            # best-effort read of the SPAWNABLE TEMPLATE transform (proves the
            # capture, not just the source). The template accessor is not
            # guaranteed reflected; record availability, do not fail on absence.
            _tmpl_rb = None
            try:
                _ms = _seq.get_movie_scene()
                for _i in range(_ms.get_spawnable_count()):
                    _sp = _ms.get_spawnable(_i)
                    _ot = _sp.get_object_template()
                    if _ot is not None and hasattr(_ot, "get_actor_location"):
                        _tl = _ot.get_actor_location()
                        _tmpl_rb = [round(_tl.x, 1), round(_tl.y, 1),
                                    round(_tl.z, 1)]
                        break
            except Exception as _te:
                _tmpl_rb = "unreadable: %s" % type(_te).__name__

            _bid = _u.MovieSceneSequenceExtensions.get_binding_id(_seq, _proxy)
            _track = _seq.add_track(_u.MovieSceneCameraCutTrack)
            _sec = _track.add_section()
            _sec.set_range(0, FRAMES)
            _sec.set_camera_binding_id(_bid)

            _saved = bool(_u.EditorAssetLibrary.save_asset(_path))
            _rb = _u.EditorAssetLibrary.load_asset(_path)
            _spawn_names = [str(b.get_name()) for b in _rb.get_spawnables()] \
                if hasattr(_rb, "get_spawnables") else []
            _out["sequences"].append({
                "name": _name, "asset": _path, "saved": _saved,
                "station": _st["name"], "loc_cm": _loc,
                "pitch_deg": _st["pitch_deg"], "yaw_deg": _st["yaw_deg"],
                "fov_h_deg": CFG["fov_h_deg"],
                "camera_readback": _cam_rb, "camera_ok": bool(_cam_ok),
                "spawnable_template_location_cm": _tmpl_rb,
                "playback_frames": _rb.get_playback_end() - _rb.get_playback_start(),
                "spawnables": _spawn_names,
                "tracks": [t.get_class().get_name() for t in _rb.get_tracks()],
                "binding_proxy_guid": str(_proxy.binding_id) if hasattr(
                    _proxy, "binding_id") else None,
            })
        except Exception as _se:
            import traceback as _tb2
            _out["sequences"].append({"name": _name,
                                      "error": "%s: %s" % (type(_se).__name__, _se),
                                      "trace": _tb2.format_exc()[-700:]})

    # --------------------------------------------------------------- configs
    def _build_config(_cfg_name, _hlod_off, _res):
        _cpath = PKG + "/" + _cfg_name
        if _u.EditorAssetLibrary.does_asset_exist(_cpath):
            _u.EditorAssetLibrary.delete_asset(_cpath)
        _cfg = _tools.create_asset(_cfg_name, PKG,
                                   _u.MoviePipelinePrimaryConfig, None)
        if _cfg is None:
            return {"name": _cfg_name, "error": "create_asset -> None"}
        _cfg.find_or_add_setting_by_class(_u.MoviePipelineDeferredPassBase)
        _cfg.find_or_add_setting_by_class(_u.MoviePipelineImageSequenceOutput_PNG)

        _o = _cfg.find_or_add_setting_by_class(_u.MoviePipelineOutputSetting)
        _dir = _u.DirectoryPath()
        _dir.set_editor_property("path", ACTIVE_DIR)
        _o.set_editor_property("output_directory", _dir)
        _o.set_editor_property("file_name_format", "item8.{frame_number}")
        _o.set_editor_property("output_resolution",
                               _u.IntPoint(int(_res[0]), int(_res[1])))
        _o.set_editor_property("override_existing_output", True)
        _o.set_editor_property("zero_pad_frame_numbers", 4)

        _aa = _cfg.find_or_add_setting_by_class(_u.MoviePipelineAntiAliasingSetting)
        _aa.set_editor_property("temporal_sample_count", 1)
        _aa.set_editor_property("spatial_sample_count", 1)
        _aa.set_editor_property("override_anti_aliasing", False)
        _aa.set_editor_property("use_camera_cut_for_warm_up", False)
        _aa.set_editor_property("engine_warm_up_count", 0)
        # RENDERED warm-up: the count is inert without the bool
        # (MoviePipelineAntiAliasingSetting.h:109/:82). These frames really
        # render, so WP far cells stream and the GPU reaches steady state
        # before the measured tail.
        _aa.set_editor_property("render_warm_up_frames", True)
        _aa.set_editor_property("render_warm_up_count", WARMUP)

        _cv_rb = None
        if _hlod_off:
            _cv = _cfg.find_or_add_setting_by_class(
                _u.MoviePipelineConsoleVariableSetting)
            _cv.set_editor_property("start_console_commands",
                                    ["wp.Runtime.HLOD 0"])
            _cv.set_editor_property("end_console_commands",
                                    ["wp.Runtime.HLOD 1"])
            _cv_rb = {
                "start_console_commands": list(_cv.get_editor_property(
                    "start_console_commands")),
                "end_console_commands": list(_cv.get_editor_property(
                    "end_console_commands")),
            }

        _saved = bool(_u.EditorAssetLibrary.save_asset(_cpath))
        _res_rb = _o.get_editor_property("output_resolution")
        return {
            "name": _cfg_name, "asset": _cpath, "saved": _saved,
            "hlod_off_arm": _hlod_off,
            "settings": [s.get_class().get_name()
                         for s in _cfg.get_all_settings()],
            "output_dir_readback": _o.get_editor_property(
                "output_directory").path,
            "file_name_format_readback": _o.get_editor_property(
                "file_name_format"),
            "resolution_readback": [int(_res_rb.x), int(_res_rb.y)],
            "temporal_sample_count_readback": int(
                _aa.get_editor_property("temporal_sample_count")),
            "spatial_sample_count_readback": int(
                _aa.get_editor_property("spatial_sample_count")),
            "render_warm_up_frames_readback": bool(
                _aa.get_editor_property("render_warm_up_frames")),
            "render_warm_up_count_readback": int(
                _aa.get_editor_property("render_warm_up_count")),
            "console_variable_setting_readback": _cv_rb,
            "has_game_override": any(
                "GameOverride" in s.get_class().get_name()
                for s in _cfg.get_all_settings()),
        }

    for _c in CFG["configs"]:
        _out["configs"].append(
            _build_config(_c["name"], bool(_c["hlod_off"]), _c["res"]))

    _seq_ok = all(s.get("saved") and s.get("camera_ok")
                  for s in _out["sequences"]) \
        and len(_out["sequences"]) == len(CFG["stations"])
    _cfg_ok = all(c.get("saved") for c in _out["configs"]) \
        and not any(c.get("has_game_override") for c in _out["configs"])
    # every hlod_off config must carry the HLOD-off commands; every other must
    # NOT carry a ConsoleVariableSetting at all.
    _cv_ok = True
    for _c in _out["configs"]:
        _rb = _c.get("console_variable_setting_readback")
        if _c.get("hlod_off_arm"):
            _cv_ok = _cv_ok and (_rb or {}).get("start_console_commands") == \
                ["wp.Runtime.HLOD 0"] and (_rb or {}).get(
                "end_console_commands") == ["wp.Runtime.HLOD 1"]
        else:
            _cv_ok = _cv_ok and _rb is None
    _out["ok"] = bool(_seq_ok and _cfg_ok and _cv_ok)
    _out["_verdict"] = {"sequences_saved": _seq_ok, "configs_saved": _cfg_ok,
                        "hlod_commands_on_B_only": _cv_ok}
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1800:]

print("__LL__" + _json.dumps(_out))
