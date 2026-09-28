"""Create /Game/Bench/M_SceneDepth — post-process material emitting LOG2 DEPTH.

WHY A MATERIAL AND NOT A RENDER PASS. There is NO depth pass class in 5.8.
MoviePipelineDeferredPasses.h ships Lit, Unlit, DetailLighting, LightingOnly,
ReflectionsOnly and PathTracer, and nothing else. Depth reaches MRQ only
through `AdditionalPostProcessMaterials`
(TArray<FMoviePipelinePostProcessPass>, :156), and no depth material ships
with the plugin. So it has to be authored.

WHY LOG2 AND NOT RAW CENTIMETRES. The first version emitted raw cm and was
correct in principle and useless in practice: MRQ writes the additional pass
as an 8-bit PNG beside the beauty frame, and depth in centimetres clamps to
white everywhere. Measured 2026-09-09 -- the resulting SceneDepth PNG held
exactly TWO unique values across a 3840x2160 frame, and both stations
produced byte-identical 150,567-byte files.

The EXR that MRQ also writes does carry float depth, but nothing here can
read it: no OpenEXR module, no imageio, and Pillow 12.3 raises
UnidentifiedImageError on it. Adding an EXR dependency to decode a quantity
that only needs RELATIVE precision would be the expensive way round.

    encoded = log2(max(depth_cm, 1)) / 20

covers 1 cm to 2^20 cm = 10.49 km in 0..1. Over 8 bits that is 20/256 =
0.078 log2 units per step, i.e. ~5.6% relative depth precision -- far finer
than the 0-100 / 100-300 / 300-1k / 1-3k / 3-8k m bins it feeds, and it
spends its precision where the bins are narrow (near) rather than uniformly.

    decode:  depth_m = 2 ** (encoded * 20) / 100

CONSTRAINTS, FROM THE STRUCT'S OWN DOC (:36-38): Post Process domain,
Blendable Location = After Tonemapping, and "will need
bDisableMultisampleEffects enabled for pixels to line up (ie: no DoF,
MotionBlur, TAA)" -- so a depth run drops temporal samples to 1, which is
correct for a geometric quantity that must not be averaged across jitter.

Names verified against engine source and the reflected surface, not guessed:
    ESceneTextureId PPI_SceneDepth        MaterialSceneTextureId.h:17
    BL_SceneColorAfterTonemapping = 0     BlendableInterface.h
                                          (BL_AfterTonemapping is DEPRECATED)
"""
import json as _json
import traceback as _tb

import unreal as _u

PKG = "/Game/Bench"
NAME = "M_SceneDepth"
PATH = PKG + "/" + NAME
LOG_DIVISOR = 20.0

_out = {"ok": False, "error": None, "asset": PATH,
        "encoding": "log2(max(depth_cm,1))/%.1f" % LOG_DIVISOR,
        "decode": "depth_m = 2**(v*%.1f)/100" % LOG_DIVISOR}
try:
    _tools = _u.AssetToolsHelpers.get_asset_tools()
    if _u.EditorAssetLibrary.does_asset_exist(PATH):
        _out["existing"] = ("deleted and rebuilt (idempotent)"
                            if _u.EditorAssetLibrary.delete_asset(PATH)
                            else "delete_asset returned False; recreating over it")

    _mat = _tools.create_asset(NAME, PKG, _u.Material, _u.MaterialFactoryNew())
    if _mat is None:
        raise RuntimeError("create_asset returned None for " + PATH)
    _mat.set_editor_property("material_domain", _u.MaterialDomain.MD_POST_PROCESS)
    _mat.set_editor_property(
        "blendable_location",
        _u.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)

    _mel = _u.MaterialEditingLibrary

    def _expr(_cls, _x, _y, _label):
        _e = _mel.create_material_expression(_mat, _cls, _x, _y)
        if _e is None:
            raise RuntimeError("create_material_expression returned None for "
                               + _label)
        return _e

    _st = _expr(_u.MaterialExpressionSceneTexture, -900, 0, "SceneTexture")
    _st.set_editor_property("scene_texture_id", _u.SceneTextureId.PPI_SCENE_DEPTH)

    # max(depth, 1) -- log2(0) is -inf, and the sky's depth is either enormous
    # or zero depending on the platform. Clamping the low end costs nothing
    # (1 cm is far nearer than any camera gets) and removes the NaN.
    _mx = _expr(_u.MaterialExpressionMax, -650, 0, "Max")
    _mx.set_editor_property("const_b", 1.0)

    _lg = _expr(_u.MaterialExpressionLogarithm2, -450, 0, "Log2")

    _dv = _expr(_u.MaterialExpressionDivide, -250, 0, "Divide")
    _dv.set_editor_property("const_b", LOG_DIVISOR)

    _steps = []
    _steps.append(["SceneTexture.Color -> Max.A",
                   _mel.connect_material_expressions(_st, "Color", _mx, "A")])
    _steps.append(["Max -> Log2",
                   _mel.connect_material_expressions(_mx, "", _lg, "")])
    _steps.append(["Log2 -> Divide.A",
                   _mel.connect_material_expressions(_lg, "", _dv, "A")])
    _steps.append(["Divide -> EmissiveColor",
                   _mel.connect_material_property(
                       _dv, "", _u.MaterialProperty.MP_EMISSIVE_COLOR)])
    _out["connections"] = _steps
    if not all(bool(s[1]) for s in _steps):
        raise RuntimeError("a connection was refused: %s" % _steps)

    _mel.recompile_material(_mat)
    # save_asset's return is the on-disk-persistence signal (the read-back below
    # re-reads the resident in-memory object, not a disk load).
    _saved = bool(_u.EditorAssetLibrary.save_asset(PATH))
    _out["saved"] = _saved
    if not _saved:
        raise RuntimeError("save_asset returned False for " + PATH)

    _rb = _u.EditorAssetLibrary.load_asset(PATH)
    if _rb is None:
        raise RuntimeError("re-load returned None for " + PATH)
    _exprs = _mel.get_material_expressions(_rb) or []
    _st_id = None
    for _ex in _exprs:
        if type(_ex).__name__ == "MaterialExpressionSceneTexture":
            _st_id = str(_ex.get_editor_property("scene_texture_id"))
            break
    _out["readback"] = {
        "material_domain": str(_rb.get_editor_property("material_domain")),
        "blendable_location": str(_rb.get_editor_property("blendable_location")),
        "expressions": len(_exprs),
        "scene_texture_id": _st_id,
        "_note": ("read off the resident in-memory material (load_asset returns "
                  "the just-created object); _saved is the disk evidence"),
    }
    # rule 12: COMPARE the probe-critical values, don't just record them -- a
    # material sampling the wrong buffer/location compiles clean.
    _exp_dom = str(_u.MaterialDomain.MD_POST_PROCESS)
    _exp_bl = str(_u.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)
    _exp_st = str(_u.SceneTextureId.PPI_SCENE_DEPTH)
    if _out["readback"]["material_domain"] != _exp_dom:
        raise RuntimeError("material_domain read back %s, not %s"
                           % (_out["readback"]["material_domain"], _exp_dom))
    if _out["readback"]["blendable_location"] != _exp_bl:
        raise RuntimeError("blendable_location read back %s, not %s"
                           % (_out["readback"]["blendable_location"], _exp_bl))
    if _st_id != _exp_st:
        raise RuntimeError("scene_texture_id read back %s, not %s (PPI_SCENE_"
                           "DEPTH)" % (_st_id, _exp_st))
    if _out["readback"]["expressions"] < 4:
        raise RuntimeError("expected >=4 expressions, read back %d"
                           % _out["readback"]["expressions"])
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, default=str))
