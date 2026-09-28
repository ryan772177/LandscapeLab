"""Which stages exist in THIS project's MRQ pipeline config?

READ-ONLY, and it READS rather than infers (ruled 2026-09-12c). The
question Q12 now rests on is what sits between the scene-linear render
and the EXR on disk, and the only honest answer comes from enumerating
the configuration the bench actually builds -- not from recalling what
MRQ usually contains.

The config is constructed the SAME WAY `bench_render` constructs it, by
calling the same `find_or_add_setting_by_class` on the same classes, so
what this lists is what that renders through. Anything it cannot
construct is reported ABSENT rather than skipped.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    _cfg = _u.MoviePipelineMasterConfig() \
        if hasattr(_u, "MoviePipelineMasterConfig") \
        else _u.MoviePipelinePrimaryConfig()
    _out["config_class"] = type(_cfg).__name__

    # The classes bench_render adds, by name so a missing one is visible.
    for _nm in ("MoviePipelineDeferredPassBase",
                "MoviePipelineImageSequenceOutput_PNG",
                "MoviePipelineImageSequenceOutput_EXR",
                "MoviePipelineColorSetting",
                "MoviePipelineOutputSetting",
                "MoviePipelineAntiAliasingSetting",
                "MoviePipelineGameOverrideSetting",
                "MoviePipelineConsoleVariableSetting"):
        _cls = getattr(_u, _nm, None)
        if _cls is None:
            continue
        try:
            _cfg.find_or_add_setting_by_class(_cls)
        except Exception:
            pass

    _stages = []
    for _s in _cfg.get_all_settings():
        _row = {"class": type(_s).__name__, "properties": {}}
        try:
            _row["enabled"] = bool(_s.is_enabled())
        except Exception:
            _row["enabled"] = "ABSENT"
        # Every reflected property whose name hints at colour, curve or
        # transform -- these are the stages that can sit between the
        # scene-linear buffer and the file.
        for _p in sorted(set(dir(type(_s)))):
            if _p.startswith("_"):
                continue
            if not any(t in _p.lower() for t in
                       ("tone", "color", "colour", "ocio", "gamma",
                        "curve", "transform", "encode", "output_type",
                        "srgb", "linear", "exposure", "quantiz")):
                continue
            try:
                _v = _s.get_editor_property(_p)
            except Exception:
                continue
            if callable(_v):
                continue
            _row["properties"][_p] = (
                bool(_v) if isinstance(_v, bool)
                else _v if isinstance(_v, (int, float)) else str(_v))
        _stages.append(_row)
    _out["stages"] = _stages

    # The deferred pass's own post-process chain flags, which decide
    # whether the written buffer has been through the post stack at all.
    _dp = getattr(_u, "MoviePipelineDeferredPassBase", None)
    if _dp is not None:
        _inst = _u.new_object(_dp)
        _out["deferred_pass_properties"] = {
            _p: str(_inst.get_editor_property(_p))
            for _p in sorted(set(dir(_dp)))
            if not _p.startswith("_") and any(
                t in _p.lower() for t in
                ("accumulator", "post", "alpha", "alpha_channel",
                 "render_passes", "disable", "tone", "output"))
            and not callable(getattr(_inst, _p, None))
        }
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-900:]

print("__LL__" + json.dumps(_out))
