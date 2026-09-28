"""R-METER step 1 — read back metering and BOTH MRQ warm-up counts.

READ-ONLY, and it must run BEFORE the first capture (RULED 2026-09-12b).

WHY BOTH COUNTS. `bench_render` sets engine_warm_up_count and
use_camera_cut_for_warm_up=False, and NEVER SETS render_warm_up_count --
so that one is whatever the class default is, and nothing in the repo
records it. The Q12 hypothesis is that engine warm-up does not advance
eye adaptation and only render warm-up does, which would leave Histogram
metering unconverged and produce exactly the 0.731 power-law response
the exposure chain shows.

PROPERTY NAMES ARE ENUMERATED, NOT GUESSED. UE 5.8 postdates the
training data and an API remembered is an API guessed; the reflected
surface is the contract. Anything not found is reported ABSENT rather
than defaulted -- a reader that cannot tell "missing" from "zero" is how
four non-existent names once read as a finding.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    # ---- 1. the live metering state, from the PostProcessVolume ----------
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ppvs = []
    for _a in _sub.get_all_level_actors():
        if type(_a).__name__ != "PostProcessVolume":
            continue
        _row = {"label": _a.get_actor_label()}
        # ABSENT, not dropped (docstring 14-17): the first version swallowed a
        # failed read with `except: pass`, so the reader could not tell a missing
        # field from an unread one -- the exact missing-vs-zero confusion the
        # probe claims to avoid. Read each property individually and mark ABSENT.
        for _p in ("unbound", "priority", "enabled"):
            try:
                _v = _a.get_editor_property(_p)
                _row[_p] = (bool(_v) if isinstance(_v, bool)
                            else float(_v) if isinstance(_v, (int, float))
                            else str(_v))
            except Exception:
                _row[_p] = "ABSENT"
        _s = _a.get_editor_property("settings")
        for _p in ("auto_exposure_method", "auto_exposure_bias",
                   "auto_exposure_min_brightness",
                   "auto_exposure_max_brightness",
                   "auto_exposure_speed_up", "auto_exposure_speed_down",
                   "auto_exposure_apply_physical_camera_exposure",
                   "override_auto_exposure_method",
                   "override_auto_exposure_bias",
                   "override_auto_exposure_apply_physical_camera_exposure"):
            try:
                _v = _s.get_editor_property(_p)
                _row[_p] = (bool(_v) if isinstance(_v, bool)
                            else float(_v) if isinstance(_v, (int, float))
                            else str(_v))
            except Exception:
                _row[_p] = "ABSENT"
        _ppvs.append(_row)
    _out["post_process_volumes"] = _ppvs

    # ---- 2. the MRQ anti-aliasing setting's warm-up properties -----------
    _aa_cls = _u.MoviePipelineAntiAliasingSetting
    _names = sorted(n for n in dir(_aa_cls) if "warm" in n.lower())
    _out["aa_warmup_property_names"] = _names

    _aa = _u.new_object(_aa_cls)
    _aa_rb = {}
    for _p in ("render_warm_up_count", "engine_warm_up_count",
               "use_camera_cut_for_warm_up", "render_warm_up_frames"):
        try:
            _v = _aa.get_editor_property(_p)
            _aa_rb[_p] = bool(_v) if isinstance(_v, bool) else int(_v)
        except Exception:
            _aa_rb[_p] = "ABSENT"
    _out["mrq_antialiasing_defaults"] = _aa_rb
    # rule 12: these are the CLASS DEFAULTS off a fresh object, NOT the applied
    # job values. bench_render sets engine_warm_up_count and
    # use_camera_cut_for_warm_up at capture, so those two differ from what runs;
    # render_warm_up_count is never set, so its default here IS what runs -- which
    # is the one the Q12 hypothesis turns on.
    _out["mrq_antialiasing_defaults_note"] = (
        "class defaults, not applied job values; only render_warm_up_count's "
        "default is what actually runs (bench_render never sets it)")

    # ---- 3. what the camera actor carries, since physical exposure ------
    #        can arrive from a CineCamera rather than the volume
    _cams = []
    for _a in _sub.get_all_level_actors():
        if "Camera" not in type(_a).__name__:
            continue
        _c = {"label": _a.get_actor_label(), "class": type(_a).__name__}
        try:
            _cc = _a.get_editor_property("camera_component")
            _pp = _cc.get_editor_property("post_process_settings")
        except Exception:
            _pp = None      # so the props below record ABSENT, not vanish
        for _p in ("auto_exposure_method",
                   "auto_exposure_apply_physical_camera_exposure",
                   "override_auto_exposure_method"):
            try:
                _v = _pp.get_editor_property(_p)
                _c[_p] = (bool(_v) if isinstance(_v, bool) else str(_v))
            except Exception:
                _c[_p] = "ABSENT"
        _cams.append(_c)
    _out["camera_count"] = len(_cams)
    _out["cameras"] = _cams[:12]   # capped; camera_count carries the true total
    # NN13: the probe exists to read the LIVE metering state, which lives on a
    # PostProcessVolume or a camera. Found neither -> nothing was read; refuse
    # rather than report success over zero metering sources.
    _out["ok"] = (len(_ppvs) > 0) or (len(_cams) > 0)
    if not _out["ok"]:
        _out["refused"] = ("no PostProcessVolume or camera in level -- no live "
                           "metering source to read")
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-800:]

print("__LL__" + json.dumps(_out))
