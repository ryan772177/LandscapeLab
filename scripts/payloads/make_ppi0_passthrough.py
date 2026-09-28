"""Build M_PPI0_Passthrough: emit PostProcessInput0 UNMODIFIED.

RULED 2026-09-13. Q12's residual is a log-log slope of ~0.72 somewhere
between the scene-linear buffer and the EXR. This material is the probe
that splits the chain: rendered as an ADDITIONAL pass at BEFORE
TONEMAPPING, it writes whatever the post stack holds at that point,
untouched. If the card's delivered step is exactly -1.000 on this pass
and ~-0.72 on FinalImage, the compression lives entirely AFTER the
split -- in the tonemap pass.

⛔ ENUM MEMBERS ARE RESOLVED OFF THE REFLECTED SURFACE, NOT RECALLED.
5.8 postdates the training data, `BlendableLocation` and `SceneTextureId`
have both been renamed across versions, and a wrong member here would
build a material that compiles and samples the wrong buffer -- the
silent-wrong class. The payload reports WHICH member answered, and
REFUSES if none does.

The graph is deliberately the smallest thing that can be correct:
SceneTexture(PostProcessInput0) -> EmissiveColor. No tint, no scale, no
clamp; anything else would be a stage this probe exists to rule out.
"""
import json as _json
import traceback as _tb

import unreal as _u

MAT_PATH = "/Game/Bench"
MAT_NAME = "M_PPI0_Passthrough"
FULL = MAT_PATH + "/" + MAT_NAME

_out = {"ok": False}


def _pick(enum_cls, wanted):
    """Return (member, name) for the first wanted name the enum exposes."""
    names = [n for n in dir(enum_cls) if not n.startswith("_")]
    for w in wanted:
        for n in names:
            if n.upper() == w.upper():
                return getattr(enum_cls, n), n
    return None, None


try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary

    _out["blendable_location_members"] = sorted(
        n for n in dir(_u.BlendableLocation) if not n.startswith("_"))
    _out["scene_texture_id_has_ppi0"] = [
        n for n in dir(_u.SceneTextureId)
        if "POST_PROCESS_INPUT0" in n.upper() or "PPI" in n.upper()]

    # ⛔ THERE IS NO `BL_BEFORE_TONEMAPPING` IN 5.8. Enumerated members:
    # BL_REPLACING_TONEMAPPER, BL_SCENE_COLOR_AFTER_DOF,
    # BL_SCENE_COLOR_AFTER_TONEMAPPING, BL_SCENE_COLOR_BEFORE_BLOOM,
    # BL_SCENE_COLOR_BEFORE_DOF, BL_SSR_INPUT, BL_TRANSLUCENCY_AFTER_DOF.
    # The location the UI and the older API called "Before Tonemapping"
    # is now **BL_SCENE_COLOR_AFTER_DOF** -- another entry for the
    # names-that-meant-something-else list. Guessing the old name would
    # have raised here; guessing a PLAUSIBLE new one
    # (BL_SCENE_COLOR_BEFORE_BLOOM) would have built a material that
    # compiles and samples a different point in the chain, which is the
    # silent-wrong class this probe exists to avoid.
    _loc, _loc_name = _pick(_u.BlendableLocation,
                            ["BL_SCENE_COLOR_AFTER_DOF"])
    if _loc is None:
        raise RuntimeError(
            "no before-tonemapping member on BlendableLocation; members are "
            + ", ".join(_out["blendable_location_members"]))
    _out["blendable_location_used"] = _loc_name

    _sid, _sid_name = _pick(_u.SceneTextureId,
                            ["PPI_POST_PROCESS_INPUT0",
                             "SCENE_TEXTURE_POST_PROCESS_INPUT0",
                             "POST_PROCESS_INPUT0"])
    if _sid is None:
        raise RuntimeError(
            "no PostProcessInput0 member on SceneTextureId; candidates were "
            + ", ".join(_out["scene_texture_id_has_ppi0"]))
    _out["scene_texture_id_used"] = _sid_name

    if _eal.does_asset_exist(FULL):
        _out["existing"] = ("deleted and rebuilt"
                            if _eal.delete_asset(FULL)
                            else "delete_asset returned False; recreating over it")
    _mat = _u.AssetToolsHelpers.get_asset_tools().create_asset(
        MAT_NAME, MAT_PATH, _u.Material, _u.MaterialFactoryNew())
    if _mat is None:
        raise RuntimeError("could not create " + FULL)

    _mat.set_editor_property("material_domain",
                             _u.MaterialDomain.MD_POST_PROCESS)
    _mat.set_editor_property("blendable_location", _loc)

    _st = _mel.create_material_expression(
        _mat, _u.MaterialExpressionSceneTexture, -400, 0)
    _st.set_editor_property("scene_texture_id", _sid)
    # `Color` is the SceneTexture node's RGB output pin. Wired with the
    # library's connect, then READ BACK below -- connect_material_property
    # is known to ignore failures elsewhere in this project.
    _ok = _mel.connect_material_property(
        _st, "Color", _u.MaterialProperty.MP_EMISSIVE_COLOR)
    _out["connect_returned"] = bool(_ok)

    _mel.recompile_material(_mat)
    # save_asset returns whether the package persisted; a discarded return is
    # rule 12's "value not read back is prose". It is also the ONLY on-disk
    # evidence here -- the load_asset below returns the resident (in-memory)
    # object, so the read-back verifies the BUILT graph, not the saved file.
    if not _eal.save_asset(FULL):
        raise RuntimeError("save_asset returned False for " + FULL)

    # ---- READ BACK the built material (load_asset returns the resident
    #      object, so this verifies the BUILD; save_asset above is the disk
    #      evidence) ----
    _re = _eal.load_asset(FULL)
    _rb = {
        "path": FULL,
        "material_domain": str(_re.get_editor_property("material_domain")),
        "blendable_location": str(
            _re.get_editor_property("blendable_location")),
    }
    try:
        _node = _mel.get_material_property_input_node(
            _re, _u.MaterialProperty.MP_EMISSIVE_COLOR)
        _rb["emissive_input_node"] = type(_node).__name__
        _rb["emissive_scene_texture_id"] = str(
            _node.get_editor_property("scene_texture_id"))
    except Exception as _e2:
        _rb["emissive_input_node"] = "UNREADABLE: %s" % _e2
    _out["readback"] = _rb

    if "POST_PROCESS" not in _rb["material_domain"].upper():
        raise RuntimeError("domain read back as %s" % _rb["material_domain"])
    if "SceneTexture" not in str(_rb.get("emissive_input_node", "")):
        raise RuntimeError(
            "EmissiveColor's input reads back as %r, not a SceneTexture -- "
            "the connect did not take" % _rb.get("emissive_input_node"))
    # rule 12: the two probe-critical values must be COMPARED, not just
    # recorded. A material that compiled but sampled the wrong buffer/location
    # is the silent-wrong class this probe exists to catch.
    if _rb["blendable_location"] != str(_loc):
        raise RuntimeError("blendable_location read back as %s, not %s"
                           % (_rb["blendable_location"], _loc))
    if _rb.get("emissive_scene_texture_id") != str(_sid):
        raise RuntimeError("emissive SceneTexture id read back as %s, not %s"
                           % (_rb.get("emissive_scene_texture_id"), _sid))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1000:]

print("__LL__" + _json.dumps(_out))
