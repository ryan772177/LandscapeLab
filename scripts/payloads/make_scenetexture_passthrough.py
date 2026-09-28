"""Build a post-process material emitting ONE SceneTexture, unmodified.

    --set SID=PPI_BASE_COLOR --set NAME=M_BaseColor_Passthrough

Generalises `make_ppi0_passthrough`: same domain, same blendable
location (BL_SCENE_COLOR_AFTER_DOF -- 5.8's name for what the UI calls
"Before Tonemapping"), same one-node graph, with the SceneTextureId as a
parameter.

⭐ WHY A BASECOLOR PASS. The bench shows a ~1 m periodicity that is NOT
at any texture tile's period. BaseColor is the GBuffer's albedo: it
carries the weightmap blend and the surface textures and carries NO
lighting at all. So the same tiling instrument run on BaseColor
DISCRIMINATES:

    period present at 1.07 m  ->  the source is WEIGHTS or TEXTURES
    period absent             ->  the source is SHADING

⛔ THE MEMBER IS RESOLVED OFF THE REFLECTED SURFACE and the payload
reports which one answered. A wrong-but-plausible SceneTextureId builds
a material that COMPILES and samples a different buffer, and the
discriminator would then answer a question nobody asked.
"""
import json as _json
import traceback as _tb

import unreal as _u

SID_NAME = "__SID__"
MAT_NAME = "__NAME__"
MAT_PATH = "/Game/Bench"
FULL = MAT_PATH + "/" + MAT_NAME

_out = {"ok": False, "requested_scene_texture_id": SID_NAME}
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary

    _all = sorted(n for n in dir(_u.SceneTextureId) if not n.startswith("_"))
    _out["scene_texture_id_members"] = _all
    if SID_NAME not in _all:
        raise RuntimeError(
            "SceneTextureId has no member %r; members are %s"
            % (SID_NAME, ", ".join(_all)))
    _sid = getattr(_u.SceneTextureId, SID_NAME)

    _locs = sorted(n for n in dir(_u.BlendableLocation)
                   if not n.startswith("_"))
    if "BL_SCENE_COLOR_AFTER_DOF" not in _locs:
        raise RuntimeError("no BL_SCENE_COLOR_AFTER_DOF; members are %s"
                           % ", ".join(_locs))
    _loc = _u.BlendableLocation.BL_SCENE_COLOR_AFTER_DOF

    if _eal.does_asset_exist(FULL):
        _eal.delete_asset(FULL)
    _mat = _u.AssetToolsHelpers.get_asset_tools().create_asset(
        MAT_NAME, MAT_PATH, _u.Material, _u.MaterialFactoryNew())
    if _mat is None:
        raise RuntimeError("could not create " + FULL)

    _mat.set_editor_property("material_domain",
                             _u.MaterialDomain.MD_POST_PROCESS)
    _mat.set_editor_property("blendable_location", _loc)
    _st = _mel.create_material_expression(
        _mat, _u.MaterialExpressionSceneTexture, -400, 0)
    if _st is None:
        raise RuntimeError("create_material_expression returned None for the "
                           "SceneTexture node")
    _st.set_editor_property("scene_texture_id", _sid)
    _out["connect_returned"] = bool(_mel.connect_material_property(
        _st, "Color", _u.MaterialProperty.MP_EMISSIVE_COLOR))
    _mel.recompile_material(_mat)
    # save_asset's bool return is the on-disk evidence; the read-back below uses
    # load_asset, which returns the RESIDENT in-memory object (not a disk
    # round-trip), so it proves the graph was built, not that it persisted.
    _saved = bool(_eal.save_asset(FULL))
    _out["saved"] = _saved
    if not _saved:
        raise RuntimeError("save_asset returned False for " + FULL)

    _re = _eal.load_asset(FULL)
    _node = _mel.get_material_property_input_node(
        _re, _u.MaterialProperty.MP_EMISSIVE_COLOR)
    _rb = {
        "path": FULL,
        "material_domain": str(_re.get_editor_property("material_domain")),
        "blendable_location": str(
            _re.get_editor_property("blendable_location")),
        "emissive_input_node": type(_node).__name__,
        "_note": ("read off the resident in-memory material; _saved is the "
                  "disk evidence"),
    }
    _out["readback"] = _rb
    # A failed connect leaves the emissive input node None; guard before
    # dereferencing it so this is a clean REFUSAL, not a bare AttributeError
    # that never records the read-back.
    if _node is None or "SceneTexture" not in type(_node).__name__:
        raise RuntimeError("EmissiveColor input reads back as %r, not a "
                           "SceneTexture node" % _rb["emissive_input_node"])
    # ⛔ THE FIRST VERSION STRIPPED UNDERSCORES FROM THE READ-BACK AND NOT FROM
    # THE NEEDLE, so it warned on a CORRECT result (a REJECTED entry in the
    # register). Compare the enum MEMBER EXACTLY (identity) instead: a substring
    # test can both false-pass (a name that is a substring of another) and
    # false-warn. A mismatch is a REFUSAL -- a pass sampling the wrong buffer is
    # exactly the silent-wrong class.
    _rb_sid = _node.get_editor_property("scene_texture_id")
    _rb["emissive_scene_texture_id"] = str(_rb_sid)
    if _rb_sid != _sid:
        raise RuntimeError(
            "read-back scene_texture_id %r is not the requested %r (%r) -- the "
            "pass would sample the wrong buffer"
            % (str(_rb_sid), SID_NAME, str(_sid)))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out))
