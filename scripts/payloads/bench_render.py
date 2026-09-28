"""Build an MRQ queue from a profile and START the render (unless dump_only,
which builds the queue, reports settings and returns WITHOUT starting a
render -- _out["started"] is False). Returns immediately.

The render is ASYNCHRONOUS -- render_queue_with_executor kicks off PIE and this
payload returns long before a frame exists. The host polls
MoviePipelineQueueSubsystem.is_rendering() rather than binding a Python
callback to a UE delegate, because a delegate bound from a remote-exec payload
outlives the scope that created it and there is nothing left to call back into.

TWO TRAPS THIS FILE EXISTS TO AVOID, both verified against 5.8 source:

1. UMoviePipelineConsoleVariableSetting::CVars is ScriptNoExport
   (MoviePipelineConsoleVariableSetting.h:129), so it is INVISIBLE to Python.
   Assigning to it would appear to work and set nothing. The exposed path is
   add_or_update_console_variable(name, value).

2. `mrq.temporal_samples` in benchmark.json is NOT a console variable. It is
   UMoviePipelineAntiAliasingSetting::TemporalSampleCount
   (MoviePipelineAntiAliasingSetting.h:59). Feeding it to the cvar setter would
   silently do nothing at all.

Output directory MUST be absolute: the editor resolves relative paths against
its own working directory, which Unreal sets to the engine binaries folder
during startup (LESSONS 2026-08-21 -- ten frames written into the engine
install).
"""
import json as _json

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')

_out = {"error": None, "jobs": []}
try:
    _sub = _u.get_editor_subsystem(_u.MoviePipelineQueueSubsystem)
    if _sub.is_rendering():
        raise RuntimeError("a render is already in progress; refusing to queue")

    _q = _sub.get_queue()
    _q.delete_all_jobs()

    for _spec in CFG["jobs"]:
        _job = _q.allocate_new_job(_u.MoviePipelineExecutorJob)
        _job.job_name = _spec["name"]
        _job.map = _u.SoftObjectPath(CFG["map"])
        _job.sequence = _u.SoftObjectPath(_spec["sequence"])
        _cfg = _job.get_configuration()

        _pass = _cfg.find_or_add_setting_by_class(_u.MoviePipelineDeferredPassBase)
        _cfg.find_or_add_setting_by_class(_u.MoviePipelineImageSequenceOutput_PNG)

        # ---- ADDITIONAL POST-PROCESS PASSES (Q12 probe, 2026-09-13) ------
        # Renders the SAME frame a second time through a post-process
        # material and writes it as its own file. Used to SPLIT the chain:
        # a material at BL_SCENE_COLOR_AFTER_DOF -- which is what 5.8 calls
        # the location the UI names "Before Tonemapping" -- emitting
        # PostProcessInput0 unmodified writes the buffer as it stands
        # BEFORE the tonemap pass. Comparing the card's delivered step on
        # that file against FinalImage says which side of the split the
        # 0.72 compression lives on.
        #
        # high_precision_output is forced TRUE: the whole point is to read
        # scene-linear values above 1.0, and an 8-bit pass would clamp
        # them and answer the question wrongly in the safe-looking
        # direction.
        _pp_rb = []
        for _pp in (CFG.get("extra_pp_passes") or []):
            _m = _u.EditorAssetLibrary.load_asset(_pp["material"])
            if _m is None:
                raise RuntimeError("post-process material not loadable: %s"
                                   % _pp["material"])
            _entry = _u.MoviePipelinePostProcessPass()
            _entry.set_editor_property("enabled", True)
            _entry.set_editor_property("name", _pp["name"])
            _entry.set_editor_property("material", _m)
            _entry.set_editor_property("high_precision_output", True)
            _cur = list(_pass.get_editor_property(
                "additional_post_process_materials"))
            _cur.append(_entry)
            _pass.set_editor_property("additional_post_process_materials",
                                      _cur)
        for _e in _pass.get_editor_property(
                "additional_post_process_materials"):
            if not bool(_e.get_editor_property("enabled")):
                continue
            _mm = _e.get_editor_property("material")
            _pp_rb.append({
                "name": str(_e.get_editor_property("name")),
                "material": (_mm.get_path_name() if _mm else None),
                "high_precision_output": bool(
                    _e.get_editor_property("high_precision_output")),
            })

        # ---- OPTIONAL SCENE-LINEAR PASS (RULED 2026-09-11) ---------------
        # The tone curve is a property of the COLOR SETTING, not of the
        # deferred pass -- verified at the source rather than guessed:
        # MoviePipelineColorSetting.h, "bDisableToneCurve: If true the
        # Filmic Tone Curve will not be applied. Disabling this will allow
        # you to export linear data for EXRs. Force Disabled if Open Color
        # IO is enabled."
        #
        # WHY IT IS NEEDED. The display-referred EXRs this bench had been
        # writing are CLAMPED: measured 2026-09-11, near_ground.exr's RGBA
        # channel maxes at EXACTLY 1.00000. Every card reading taken off
        # them was therefore post-tonemap, which is why a ruled -1.5943 EV
        # exposure step delivered only 65% of itself.
        #
        # OCIO FORCE-DISABLES IT, so the OCIO state is read back too --
        # a silently-ignored flag here would produce a linear-LOOKING file
        # that is still tonemapped, and nothing downstream could tell.
        if CFG.get("linear"):
            _col = _cfg.find_or_add_setting_by_class(
                _u.MoviePipelineColorSetting)
            _col.set_editor_property("disable_tone_curve", True)
            _exr = _cfg.find_or_add_setting_by_class(
                _u.MoviePipelineImageSequenceOutput_EXR)
            # ⭐ THE EXR FORMAT IS NOW DECLARED, NOT DEFAULTED.
            # Until 2026-09-14 this class was added and never configured,
            # so compression took the constructor's PIZ
            # (MoviePipelineEXROutput.h:213) and multilayer took whatever
            # the default was -- an undeclared format on the file every
            # look acceptance is measured from.
            #
            # ZIP (16 scanlines) = EEXRCompressionFormat::ZIP = 3
            # (MoviePipelineEXROutput.h:62). Lossless, and better than
            # PIZ on the low-noise content these frames are.
            # multilayer False: one pass per file, because the readers
            # here (OpenEXR 3.3.2 via exr_card) address files, not layers.
            #
            # ⛔ BIT DEPTH IS NOT A PROPERTY OF THIS CLASS. The EXR output
            # reflects Compression (:231), bMultilayer (:237) and bMultipart
            # (:245); only the first two are touched here (bMultipart is left
            # at its False default). Half vs full float is decided by
            # the PASS, through high_precision_output; the beauty pass
            # is left at half (16-bit float), which is the look
            # instrument's declared depth.
            _exr_rb = {}
            try:
                _comp = CFG.get("exr_compression", "ZIP")
                _enum = getattr(_u, "EEXRCompressionFormat", None)
                if _enum is None:
                    _exr_rb["compression_error"] = (
                        "EEXRCompressionFormat is not reflected to Python; "
                        "compression left at the engine default")
                else:
                    _exr.set_editor_property("compression",
                                             getattr(_enum, _comp))
                _exr.set_editor_property("multilayer",
                                         bool(CFG.get("exr_multilayer", False)))
            except Exception as _ee:
                _exr_rb["error"] = "%s: %s" % (type(_ee).__name__, _ee)
            # Read back from the setting, not from the request.
            for _k in ("compression", "multilayer"):
                try:
                    _exr_rb[_k] = str(_exr.get_editor_property(_k))
                except Exception as _ee:
                    _exr_rb[_k] = "UNREADABLE: %s" % type(_ee).__name__
            _out.setdefault("exr_output", {})[_spec["name"]] = _exr_rb
            _ocio = _col.get_editor_property("ocio_configuration")
            _out.setdefault("linear", {})[_spec["name"]] = {
                "disable_tone_curve_readback": bool(
                    _col.get_editor_property("disable_tone_curve")),
                "ocio_is_enabled_readback": bool(
                    _ocio.get_editor_property("is_enabled")) if _ocio
                else None,
            }

        # ---- OPTIONAL SCENE-DEPTH PASS -----------------------------------
        # There is NO depth pass class in 5.8 -- MoviePipelineDeferredPasses.h
        # ships Lit/Unlit/DetailLighting/LightingOnly/ReflectionsOnly/
        # PathTracer and nothing else -- so depth arrives as an ADDITIONAL
        # POST-PROCESS MATERIAL (:156) that we author (/Game/Bench/M_SceneDepth).
        #
        # The struct's own doc (:36-38) says such a material "will need
        # bDisableMultisampleEffects enabled for pixels to line up (ie: no
        # DoF, MotionBlur, TAA)". So a depth pass CANNOT align with a
        # temporal x8 beauty frame, and the caller drops temporal samples to
        # 1 for a depth run. That is correct for a geometric quantity: depth
        # must not be averaged across jittered samples.
        #
        # 32-BIT EXR, NOT PNG (as the primary artefact). The material
        # emits LOG2-ENCODED depth — log2(max(depth_cm,1))/20, decode via
        # haze_metrics.decode_depth_m — NOT raw centimetres (a raw-cm
        # first version clipped and was replaced; make_depth_material.py
        # docstring). The log encoding is exactly what makes the 8-bit
        # PNG usable too: 256 steps of log2 depth resolve the far bins a
        # linear-cm PNG would collapse.
        if CFG.get("depth_material"):
            _dm = _u.load_asset(CFG["depth_material"])
            if _dm is None:
                raise RuntimeError("depth material not found: %s"
                                   % CFG["depth_material"])
            _ppp = _u.MoviePipelinePostProcessPass()
            # `enabled`, NOT `b_enabled`. The C++ is `bool bEnabled`
            # (MoviePipelineDeferredPasses.h:26) and UE's Python bindings
            # strip the leading b from boolean UPROPERTYs. Probed from the
            # live struct rather than guessed a second time -- the reflected
            # surface is the contract (docs/ue58-api-protocol.md).
            _ppp.set_editor_property("enabled", True)
            _ppp.set_editor_property("name", "SceneDepth")
            _ppp.set_editor_property("material", _dm)
            # ⛔ APPEND, NEVER REPLACE. This was
            # set_editor_property(..., [_ppp]), which silently DROPPED any
            # pass added earlier -- so `--depth` together with `--pp-pass`
            # produced an EXR with SceneDepth and no PPI0, and the only
            # symptom was a missing channel much later. Same shape as the
            # staged-probe filename collision fixed the same day: two
            # writers, one slot, last one wins.
            _cur_d = list(_pass.get_editor_property(
                "additional_post_process_materials"))
            _cur_d.append(_ppp)
            _pass.set_editor_property("additional_post_process_materials",
                                      _cur_d)
            _pass.set_editor_property("disable_multisample_effects", True)
            _cfg.find_or_add_setting_by_class(
                _u.MoviePipelineImageSequenceOutput_EXR)
            # READ THE MATERIAL BACK off the attached pass (rule 12), the same
            # way the extra-PP path does (:85-88) -- reporting CFG's requested
            # value proved a pass was ADDED, not WHICH material rides it.
            _dm_rb = None
            for _e in (_pass.get_editor_property(
                    "additional_post_process_materials") or []):
                if str(_e.get_editor_property("name")) == "SceneDepth":
                    _mm = _e.get_editor_property("material")
                    _dm_rb = _mm.get_path_name() if _mm else None
            _out.setdefault("depth", {})[_spec["name"]] = {
                "material": _dm_rb,                     # READ BACK, not requested
                "material_requested": CFG["depth_material"],
                "additional_pp_readback": len(
                    _pass.get_editor_property(
                        "additional_post_process_materials") or []),
                "disable_multisample_effects_readback": bool(
                    _pass.get_editor_property("disable_multisample_effects")),
            }

        _o = _cfg.find_or_add_setting_by_class(_u.MoviePipelineOutputSetting)
        _dir = _u.DirectoryPath()
        _dir.set_editor_property("path", _spec["output_dir"])
        _o.set_editor_property("output_directory", _dir)
        _o.set_editor_property("file_name_format", _spec["file_name_format"])
        _o.set_editor_property("output_resolution",
                               _u.IntPoint(CFG["res"][0], CFG["res"][1]))
        _o.set_editor_property("override_existing_output", True)

        _aa = _cfg.find_or_add_setting_by_class(_u.MoviePipelineAntiAliasingSetting)
        _aa.set_editor_property("temporal_sample_count", int(CFG["temporal_samples"]))
        _aa.set_editor_property("spatial_sample_count", int(CFG["spatial_samples"]))
        # AUDIT V-5 (2026-09-15): the setting's `anti_aliasing_method`
        # defaults to AAM_NONE and the config dump SHOWS that value, which
        # reads as "AA is off". It is INERT: with `override_anti_aliasing`
        # False the method is not applied and the PROJECT'S TSR runs. Set
        # the override False EXPLICITLY so the dump's AAM_NONE cannot be
        # misread as an active choice -- the value is prose, not a setting.
        # (This override is read BACK only on the dump_only path, via
        # get_all_settings; the per-job render sidecar does not re-read it.)
        _aa.set_editor_property("override_anti_aliasing", False)
        # EngineWarmUpCount only applies when bUseCameraCutForWarmUp is FALSE
        # (its EditCondition, MoviePipelineAntiAliasingSetting.h:100). Set
        # explicitly rather than trusting a default -- a warm-up that silently
        # does not happen is exactly the class of defect this whole block is
        # here to prevent.
        _aa.set_editor_property("use_camera_cut_for_warm_up", False)
        _aa.set_editor_property("engine_warm_up_count", int(CFG["warm_up_frames"]))

        # ---- RENDER warm-up (R-METER retest, 2026-09-12c) -----------------
        # ⛔ THE COUNT IS INERT WITHOUT THE BOOL. `render_warm_up_count`
        # defaults to 32 and `render_warm_up_frames` defaults to FALSE, so
        # every capture this project has ever taken ran with ZERO RENDERED
        # warm-up frames while a sidecar recorded a warm-up of 300 -- that
        # 300 is the ENGINE count, which ticks the game thread and does not
        # render. Engine warm-up does not advance anything that lives in
        # the RENDER thread's frame history.
        #
        # Both are set and both are read back, because the bool is the one
        # that decides whether the count means anything and nothing on disk
        # recorded it until this run.
        _aa.set_editor_property("render_warm_up_frames",
                                bool(CFG.get("render_warm_up_frames", True)))
        _aa.set_editor_property("render_warm_up_count",
                                int(CFG.get("render_warm_up_count", 32)))

        # ---- game overrides ----------------------------------------------
        # Added for the TRUTH frame, or whenever the caller asks for one
        # explicitly via CFG["game_override"]. Before 2026-09-14 the only
        # trigger was `truth`, which meant a DEV capture carried NO
        # GameOverride setting at all -- so every dev-profile question
        # about disable_hlods / use_lod_zero / cinematic_quality_settings
        # was being asked about a setting that was not in the config.
        _go_rb = None
        _go_req = CFG.get("game_override") or {}
        if CFG.get("truth") or _go_req:
            _go = _cfg.find_or_add_setting_by_class(_u.MoviePipelineGameOverrideSetting)
            if CFG.get("truth"):
                _go.set_editor_property("override_view_distance_scale", True)
                _go.set_editor_property("view_distance_scale",
                                        int(CFG["truth"]["view_distance_scale"]))
                _go.set_editor_property("flush_streaming_managers", True)
            # Caller-requested properties are applied AFTER the truth
            # block so an explicit request wins over the implicit one,
            # and the read-back below reports what actually stuck rather
            # than what was asked for.
            _go_applied, _go_refused = [], {}
            for _k, _v in _go_req.items():
                try:
                    _go.set_editor_property(_k, _v)
                    _go_applied.append(_k)
                except Exception as _ge:
                    _go_refused[_k] = "%s: %s" % (type(_ge).__name__, _ge)

            # The reflected GameOverride surface (far more than the four that
            # used to be reported), NOT literally every property: the
            # DEPRECATED game_mode_override is kept for back-compat and its
            # live replacement soft_game_mode_override (:83) is NOT captured.
            # Names are ground truth from
            # MoviePipelineGameOverrideSetting.h:79-151, not from memory.
            _GO_PROPS = [
                "game_mode_override", "cinematic_quality_settings",
                "texture_streaming", "use_lod_zero", "disable_hlods",
                "use_high_quality_shadows", "shadow_distance_scale",
                "shadow_radius_threshold", "override_view_distance_scale",
                "view_distance_scale", "flush_grass_streaming",
                "override_grass_cull_distance_scale",
                "grass_cull_distance_scale",
                "override_grass_density_scale", "grass_density_scale",
                "flush_streaming_managers",
                "override_virtual_texture_feedback_factor",
                "virtual_texture_feedback_factor",
            ]
            _go_rb = {"_requested": _go_req,
                      "_applied": _go_applied,
                      "_refused": _go_refused,
                      "_is_enabled": bool(_go.is_enabled())
                      if hasattr(_go, "is_enabled") else None}
            for _k in _GO_PROPS:
                try:
                    _gv = _go.get_editor_property(_k)
                except Exception as _ge:
                    _go_rb[_k] = "UNREADABLE: %s" % type(_ge).__name__
                    continue
                _go_rb[_k] = (_gv if isinstance(_gv, (bool, int, float,
                                                      str, type(None)))
                              else str(_gv))

        _cv = _cfg.find_or_add_setting_by_class(_u.MoviePipelineConsoleVariableSetting)
        for _n, _v in CFG["cvars"].items():
            _cv.add_or_update_console_variable(_n, float(_v))

        # start commands: things that are COMMANDS, not variables, so
        # add_or_update_console_variable cannot express them.
        _starts = list(CFG.get("start_commands") or [])
        if _starts:
            _cv.set_editor_property("start_console_commands", _starts)
        # end commands: the in-PIE residency probe. Remote exec cannot run
        # here -- MRQ owns the game thread for the whole render.
        _ends = list(CFG.get("end_commands") or [])
        if _ends:
            _cv.set_editor_property("end_console_commands", _ends)

        # READ BACK the config, which is the only channel that can prove the
        # ScriptNoExport trap was avoided.
        _cv_rb = {}
        for _e in _cv.get_console_variables():
            try:
                _cv_rb[str(_e.get_editor_property("name"))] = float(
                    _e.get_editor_property("value"))
            except Exception:
                pass
        _res_rb = _o.get_editor_property("output_resolution")
        _out["jobs"].append({
            "name": _job.job_name,
            "sequence": str(_job.sequence),
            "map": str(_job.map),
            "output_dir_readback": _o.get_editor_property("output_directory").path,
            "file_name_format_readback": _o.get_editor_property("file_name_format"),
            "resolution_readback": [int(_res_rb.x), int(_res_rb.y)],
            "temporal_sample_count_readback": int(
                _aa.get_editor_property("temporal_sample_count")),
            "spatial_sample_count_readback": int(
                _aa.get_editor_property("spatial_sample_count")),
            "engine_warm_up_count_readback": int(
                _aa.get_editor_property("engine_warm_up_count")),
            "use_camera_cut_for_warm_up_readback": bool(
                _aa.get_editor_property("use_camera_cut_for_warm_up")),
            # The BOOL first: a count without it is prose (rule 12).
            "render_warm_up_frames_readback": bool(
                _aa.get_editor_property("render_warm_up_frames")),
            "render_warm_up_count_readback": int(
                _aa.get_editor_property("render_warm_up_count")),
            # The ENABLED additional passes, read off the setting -- so a
            # probe pass that silently failed to attach is visible in the
            # sidecar rather than inferred from a missing file.
            "extra_pp_passes_readback": _pp_rb,
            "start_console_commands_readback": list(
                _cv.get_editor_property("start_console_commands")),
            "end_console_commands_readback": list(
                _cv.get_editor_property("end_console_commands")),
            "game_overrides_readback": _go_rb,
            "cvars_config_readback": _cv_rb,
            "cvars_requested": CFG["cvars"],
            "cvars_match": (sorted(_cv_rb.keys()) == sorted(CFG["cvars"].keys())
                            and all(abs(_cv_rb[k] - float(CFG["cvars"][k])) < 1e-6
                                    for k in CFG["cvars"])),
        })

    # engine-side cvar values BEFORE the render. MRQ applies its own during the
    # shot and restores them after, so this is the surrounding state, NOT proof
    # of what the frames were rendered with. Labelled accordingly.
    _pre = {}
    for _n in CFG["cvars"]:
        try:
            _pre[_n] = _u.SystemLibrary.get_console_variable_float_value(_n)
        except Exception as _ce:
            _pre[_n] = "ERR: " + type(_ce).__name__
    _out["engine_cvars_before_render"] = _pre

    # ---- DUMP-ONLY: the config as the ENGINE holds it -------------------
    # Audit item 2. Placed HERE, after every setting is built and before
    # anything is started, so what is dumped is the object the render
    # would have used -- not a second reconstruction of it. A separate
    # "dump the config" tool would be a second implementation of this
    # construction, and two lists that must agree are one list badly
    # stored (NN24).
    if CFG.get("dump_only"):
        # ⛔ SILENCE THE DEPRECATION WARNINGS, AND RECORD THEM INSTEAD.
        # 2026-09-14: this dump touches every attribute twice (the
        # callable test, then the read), and UE raises a Python
        # DeprecationWarning on EACH touch of a deprecated property.
        # MoviePipelineGameOverrideSetting has two of them --
        # `disable_hlo_ds` (renamed to `disable_hlods`) and
        # `game_mode_override` (superseded by SoftGameModeOverride) --
        # and the resulting warning volume broke the remote-exec
        # response outright: "Remote party failed to send a valid
        # response". The warnings are INFORMATION, not noise, so they
        # are captured into the dump rather than merely muted.
        import warnings as _warnings
        _dep = []

        def _catch(_msg, _cat, _fn, _ln, _file=None, _line=None):
            _s = str(_msg)
            if _s not in _dep:
                _dep.append(_s)

        _old_showwarning = _warnings.showwarning
        _warnings.showwarning = _catch
        _warnings.simplefilter("always", DeprecationWarning)
        _dump = {"map": CFG["map"], "settings": []}
        for _s in _cfg.get_all_settings():
            _row = {"class": _s.get_class().get_name(),
                    "is_enabled": bool(_s.is_enabled())
                    if hasattr(_s, "is_enabled") else None,
                    "properties": {}}
            # UObject settings expose NO property descriptors to dir()
            # (verified 2026-09-14 on HLODLayer: 23 names, all methods).
            # So ask the engine for names the only way Python can: try
            # every snake_case attribute the binding does expose, and
            # record what refuses rather than hiding it.
            for _n in sorted(n for n in dir(_s) if not n.startswith("_")):
                if callable(getattr(_s, _n, None)):
                    continue
                try:
                    _v = _s.get_editor_property(_n)
                except Exception:
                    continue
                try:
                    if isinstance(_v, (bool, int, float, str, type(None))):
                        _row["properties"][_n] = _v
                    elif isinstance(_v, (_u.Array, list, tuple)):
                        _row["properties"][_n] = [str(_x) for _x in _v]
                    else:
                        _row["properties"][_n] = str(_v)
                except Exception as _pe:
                    _row["properties"][_n] = "UNREADABLE: %s" % type(_pe).__name__
            _dump["settings"].append(_row)
        # The cvar list is ScriptNoExport as a FIELD and has to come
        # through the accessor (see trap 1 at the top of this file).
        try:
            _dump["console_variables"] = [
                {"name": str(_e.get_editor_property("name")),
                 "value": float(_e.get_editor_property("value")),
                 "is_enabled": bool(_e.get_editor_property("is_enabled"))}
                for _e in _cv.get_console_variables()]
        except Exception as _de:
            _dump["console_variables"] = "UNREADABLE: %s" % type(_de).__name__
        _warnings.showwarning = _old_showwarning
        # The deprecated names the ENGINE itself flagged while this dump
        # read them. AUDIT.md 2.2 lists "deprecations (e.g.
        # disable_hlo_ds -> disable_hlods)" as something the API pass
        # must check; this is the engine answering that question
        # directly, rather than a reader inferring it from a name.
        _dump["deprecation_warnings_raised_by_this_dump"] = _dep
        _out["config_dump"] = _dump
        _out["dump_only"] = True
        _out["started"] = False
        # Fall through to the single print at the bottom rather than
        # exiting here: SystemExit is a BaseException, the remote-exec
        # harness owns the frame this runs in, and an early exit from
        # inside the try would take the marker with it.

    # ORDERING MATTERS AND THE FIRST VERSION GOT IT WRONG.
    # render_queue_with_executor(CLASS) CONSTRUCTS the executor and STARTS the
    # render in one call, so anything configured on the returned object is set
    # AFTER the render is already under way. The 2026-09-05 first attempt did
    # exactly that with set_is_rendering_offscreen and the render sat at
    # "Job 1/3, 0% Completed" indefinitely.
    # render_queue_with_executor_instance(INSTANCE) exists precisely so the
    # executor can be built and configured BEFORE it is handed the queue.
    if not CFG.get("dump_only"):
        _exec = _u.new_object(_u.MoviePipelinePIEExecutor)
        if CFG.get("offscreen", True):
            try:
                _exec.set_is_rendering_offscreen(True)
            except Exception as _oe:
                _out["offscreen_error"] = type(_oe).__name__ + ": " + str(_oe)
        _out["executor_configured_before_start"] = True
        _sub.render_queue_with_executor_instance(_exec)
        _out["started"] = True
        _out["is_rendering"] = bool(_sub.is_rendering())
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1800:]

print("__LL__" + _json.dumps(_out))
