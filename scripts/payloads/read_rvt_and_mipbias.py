"""Does the ground go through a runtime virtual texture, and what is each
layer's Automatic View Mip Bias?

⭐ WHY BOTH, AND WHY NOW. The 30-100 m peaks were attributed to ALIASING
of sub-pixel detail against the sampling grid (REGISTER B3.17, measured
at temporal 1). The two material-side levers that change how that detail
is filtered are:

  RVT -- if the ground renders through a runtime virtual texture, the
         filtering path is the VT one and its own anisotropy cvars
         govern, not the ordinary sampler's.
  AUTOMATIC VIEW MIP BIAS -- a per-TextureSample flag that shifts the mip
         selection to match the temporal jitter. With it OFF, a
         temporally-jittered renderer samples sharper than the pixel
         footprint and aliases; that is exactly the reported signature.

⛔ WHAT IS DELIBERATELY NOT DONE HERE. `r.MaxAnisotropy` is a STARTUP
value -- a console change does not reach the samplers already created
(UE-116243) -- so testing it at runtime would produce a "no effect"
result that means nothing. It is READ and reported, never set. The VT
anisotropy cvars ARE runtime and are read too, but only reported.

READ-ONLY.
"""
import json as _json
import traceback as _tb

import unreal as _u

MAT = "/Game/Materials/M_Alpine8K"
_out = {"ok": False, "material": MAT}
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _mat = _eal.load_asset(MAT)
    # F2: load_asset returns None for a missing/renamed asset; get_material_
    # expressions(None) would then yield [] and the probe would report ok:true
    # over a material that does not exist. Refuse instead.
    if _mat is None:
        raise RuntimeError("material not found: " + MAT)
    _all = list(_mel.get_material_expressions(_mat))
    _out["expressions"] = len(_all)

    # ---- 1. RUNTIME VIRTUAL TEXTURE -------------------------------------
    _rvt_nodes = []
    for _e in _all:
        _cn = type(_e).__name__
        # F6: "RuntimeVirtualTexture" already contains "VirtualTexture", so the
        # second disjunct was dead; one substring test suffices.
        if "VirtualTexture" in _cn:
            _r = {"class": _cn}
            for _p in ("virtual_texture", "material_type", "output_attributes"):
                try:
                    _v = _e.get_editor_property(_p)
                    _r[_p] = (_v.get_path_name()
                              if hasattr(_v, "get_path_name") else str(_v))
                except Exception:
                    _r[_p] = "ABSENT"   # F5: missing != dropped
            _rvt_nodes.append(_r)
    _out["rvt_nodes_in_graph"] = _rvt_nodes
    # A landscape can also be told to WRITE to an RVT from the actor, with
    # no node in the material at all -- so ask the actor too.
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ls_rvt = []
    _ls_found = 0
    for _a in _eas.get_all_level_actors():
        if type(_a).__name__ != "Landscape":
            continue
        _ls_found += 1
        for _p in ("runtime_virtual_textures",):
            try:
                _v = _a.get_editor_property(_p)
            except Exception:
                continue
            try:
                _ls_rvt.append({_p: [x.get_path_name() for x in _v]
                                if _v else []})
            except Exception:
                _ls_rvt.append({_p: str(_v)})
        for _p in ("virtual_texture_num_lods", "virtual_texture_lod_bias",
                   "virtual_texture_render_pass_type"):
            try:
                _ls_rvt.append({_p: str(_a.get_editor_property(_p))})
            except Exception:
                pass
    _out["landscape_rvt_properties"] = _ls_rvt
    _out["landscape_actors_seen"] = _ls_found
    _has_rvt_list = any(
        isinstance(list(d.values())[0], list) and list(d.values())[0]
        for d in _ls_rvt)
    # F4: absent != False. A False from "no Landscape actor was inspected" reads
    # identically to a genuine "landscape has no RVT" -- so only say False when a
    # landscape was actually read, else UNKNOWN.
    if _rvt_nodes or _has_rvt_list:
        _out["ground_uses_rvt"] = True
    elif _ls_found == 0:
        _out["ground_uses_rvt"] = "UNKNOWN (no Landscape actor inspected)"
    else:
        _out["ground_uses_rvt"] = False

    # ---- 2. AUTOMATIC VIEW MIP BIAS, per texture sample ------------------
    _rows = []
    for _e in _all:
        if not isinstance(_e, _u.MaterialExpressionTextureSample):
            continue
        try:
            _t = _e.get_editor_property("texture")
        except Exception:
            _t = None
        if _t is None:
            continue
        _r = {"texture": _t.get_name()}
        for _p in ("automatic_view_mip_bias", "auto_view_mip_bias",
                   "const_mip_value", "mip_value_mode", "sampler_source"):
            try:
                _r[_p] = str(_e.get_editor_property(_p))
            except Exception:
                _r[_p] = "ABSENT"   # F5: property genuinely missing, not dropped
        _rows.append(_r)
    _rows.sort(key=lambda r: r["texture"])
    _out["texture_samples"] = _rows
    _bias = sorted(set(r.get("automatic_view_mip_bias", "UNREADABLE")
                       for r in _rows))
    _out["automatic_view_mip_bias_values_present"] = _bias

    # ---- 3. THE CVARS, READ ONLY ----------------------------------------
    _cv = {}
    for _n in ("r.VT.AnisotropicFiltering", "r.VT.MaxAnisotropy",
               "r.MaxAnisotropy", "r.VirtualTextures",
               "r.VT.EnableAutoImport", "r.Streaming.MipBias"):
        _v = _u.SystemLibrary.get_console_variable_string_value(_n)
        _cv[_n] = {"value": _v, "exists": _v != ""}
    _out["cvars"] = _cv
    _out["_maxanisotropy_note"] = (
        "r.MaxAnisotropy is a STARTUP value -- a console change does not "
        "reach samplers already created (UE-116243). It is READ here and "
        "never set; a runtime A/B on it would return 'no effect' for a "
        "reason that has nothing to do with the world.")
    # F1/F3/NN13: the probe's primary question is per-TextureSample mip bias; a
    # run that read zero texture samples (or no expressions) answered nothing and
    # would leave automatic_view_mip_bias_values_present == []. Refuse.
    _out["ok"] = _out["expressions"] > 0 and len(_rows) > 0
    if not _out["ok"]:
        _out["refused"] = ("expressions=%d, texture_samples=%d -- no mip-bias "
                           "read to report" % (_out["expressions"], len(_rows)))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
