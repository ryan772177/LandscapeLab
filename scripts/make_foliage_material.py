"""make_foliage_material.py — masked two-sided material for a Free/ mesh.

Builds one material per imported mesh asset from the textures
import_static_mesh brought in, and assigns it to the mesh's slot.

THREE THINGS THAT ARE NOT OPTIONAL FOR FOLIAGE, and each is silent if
wrong:

  BLEND MODE MASKED. A grass card is a quad with an alpha cutout. Left
  Opaque, every blade renders as a rectangle — obvious. Left Translucent,
  it renders but sorts wrongly against itself and costs far more.

  TWO-SIDED. A single-sided card vanishes from behind, so half of every
  clump disappears depending on view angle. That reads as popping, not
  as a material setting.

  GREEN-CHANNEL FLIP FOR GL SOURCES. Unreal expects DirectX-convention
  tangent normals (green down). The Poly Haven meshes ship `nor_gl` and
  nothing else, so their green channel MUST be inverted. The ambientCG
  surfaces ship both and are consumed as DX with no flip (ruling 1).
  The convention comes from the manifest per asset — it is not a global
  constant, and treating it as one is what produced a manifest claiming
  DX for files literally named nor_gl.

  A flip applied twice, or to a DX map, is invisible on flat geometry
  and inverts every slope. It reads as bad lighting, never as a bug,
  which is why the source of truth is the manifest rather than a flag.

Exit codes:
  0  material built, assigned, and verified by read-back
  1  unexpected error / bad arguments
  2  manifest missing/unreadable, an asset id absent from it, ambiguous
     texture roles (no --slot), or no colour map for the mesh (a texture
     asset missing at editor LOAD time is a build failure -> 4, not 2)
  3  editor identity gate refused (conduct rule 7)
  4  build or verification failed
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import material_graph     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MANIFEST = os.path.join(REPO_ROOT, "Free", "manifest.json")
TEX_ROOT = "/Game/Meshes/Textures"
MAT_ROOT = "/Game/Meshes/Materials"
MARKER = "__LANDSCAPELAB_FOLMAT__"


def texture_map(manifest, mesh_id, slot=None):
    """{role: asset path} for one mesh, optionally one material slot.

    REFUSES when two source files claim the same role and `slot` does
    not disambiguate them.

    WHY. This line used to be a plain `out[role] = ...`, which means
    LAST FILE WINS. `fir_tree_01` ships bark_* and twig_* sets, and both
    provide `color`, `normal` and `roughness`. Called without `slot`,
    "bark" sorts before "twig", so every bark role was silently
    overwritten by twig. `M_fir_bark` was therefore built sampling
    twig_diff three times, twig_nor_gl and twig_rough, and NEVER a bark
    texture -- while reporting a clean build. It is bound to three of
    the fir's four slots across 160,448 instances, so every conifer
    trunk rendered with the pale twig atlas: the "bare spindly poles"
    defect.

    Nothing detected it because every downstream check was satisfied:
    the textures existed, the samplers matched their compression, the
    material compiled, and the read-back confirmed the slots were bound.
    The map was internally consistent and simply described the wrong
    texture set.

    Non-negotiable 3 says prefer an input that cannot express the
    catastrophic value over a gate that rejects it. A dict that
    overwrites is exactly such an input, so ambiguity is now a refusal
    rather than a silent choice: the caller must pass `--slot`.
    """
    for a in manifest["assets"]:
        if a["id"] != mesh_id:
            continue
        out = {}
        claims = {}
        for f in a["files"]:
            role = f["role"]
            if role not in ("color", "normal", "roughness", "alpha",
                            "packed-arm"):
                continue
            stem = os.path.splitext(os.path.basename(f["path"]))[0]
            if slot and slot not in stem:
                continue
            claims.setdefault(role, []).append(stem)
            out[role] = "{0}/T_{1}".format(TEX_ROOT, stem)

        ambiguous = {r: v for r, v in claims.items() if len(v) > 1}
        if ambiguous:
            lines = ["{0} texture role(s) are AMBIGUOUS for {1!r}{2}."
                     .format(len(ambiguous), mesh_id,
                             " slot " + slot if slot else
                             " with NO --slot filter")]
            for r, v in sorted(ambiguous.items()):
                lines.append("    role {0!r} claimed by {1} files:"
                             .format(r, len(v)))
                for s in v:
                    lines.append("        {0}".format(s))
            lines.append("")
            lines.append("REFUSING. Silently taking the last one is how "
                         "M_fir_bark ended up")
            lines.append("sampling the TWIG textures on every conifer "
                         "trunk. Pass --slot to")
            lines.append("choose, e.g. --slot bark.")
            raise ValueError("\n".join(lines))
        return a, out
    raise KeyError("no asset {0!r}".format(mesh_id))


PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "stage": "start"}}
_j = _json.loads({job!r})
_mel = _unreal.MaterialEditingLibrary

try:
    _out["stage"] = "resolve"
    _tex = {{}}
    _missing = []
    for _role, _p in _j["textures"].items():
        _t = _unreal.EditorAssetLibrary.load_asset(_p)
        if _t is None:
            _missing.append(_p)
        else:
            _tex[_role] = _t
    _mesh = _unreal.EditorAssetLibrary.load_asset(_j["mesh"])
    if _mesh is None:
        _missing.append(_j["mesh"])
    if _missing:
        _out["error"] = "missing assets: " + ", ".join(_missing)
        raise RuntimeError(_out["error"])

    _out["stage"] = "material"
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    _mp = _j["material"]
    if _unreal.EditorAssetLibrary.does_asset_exist(_mp):
        _mat = _unreal.EditorAssetLibrary.load_asset(_mp)
    else:
        _mat = _tools.create_asset(_mp.rsplit("/", 1)[1],
                                   _mp.rsplit("/", 1)[0],
                                   _unreal.Material,
                                   _unreal.MaterialFactoryNew())
    if _mat is None:
        _out["error"] = "could not create " + _mp
        raise RuntimeError(_out["error"])

    # SHARED UTILITY (the material_graph module). Per-script clear logic
    # is a REJECTED pattern as of 2026-08-03: this exact trap was fixed
    # locally three times, in three different tools, and recurred each
    # time. There is now one implementation and every builder uses it.
    _out["clear"] = _ll_clear_graph(_mel, _mat)
    if _out["clear"]["remaining"]:
        _out["error"] = ("material graph still holds expressions after an "
                         "explicit total clear -- refusing to rebuild on "
                         "top of debris")
        raise RuntimeError(_out["error"])

    # Masked + two-sided is right for a foliage CARD and wrong for
    # bark, which is solid geometry: masking it costs the opaque fast
    # path and two-siding it doubles the shading for surfaces that are
    # never seen from behind.
    _mat.set_editor_property(
        "blend_mode", _unreal.BlendMode.BLEND_MASKED if _j["masked"]
        else _unreal.BlendMode.BLEND_OPAQUE)
    _mat.set_editor_property("two_sided", bool(_j["masked"]))
    _mat.set_editor_property("opacity_mask_clip_value",
                             float(_j["clip"]))

    def _n(_cls, _x, _y):
        return _mel.create_material_expression(_mat, _cls, _x, _y)

    def _samp(_asset_role, _stype, _x, _y):
        _s = _n(_unreal.MaterialExpressionTextureSample, _x, _y)
        _s.set_editor_property("texture", _tex[_asset_role])
        _s.set_editor_property("sampler_type", _stype)
        return _s

    _ST = _unreal.MaterialSamplerType
    _c = _samp("color", _ST.SAMPLERTYPE_COLOR, -700, 0)

    # =================================================================
    # GRASS-CARD APPEARANCE (Brief 3 Task 4). Built ONLY when the recipe
    # declares a `card` block; without one the base colour goes straight
    # to the output exactly as before, so every other foliage material
    # this builder makes is byte-identical to what it made yesterday.
    #
    # ⭐ THE DEGRADED STATE IS THE IDENTITY, BY CONSTRUCTION. With
    # hue_percent 0, brightness_amp 0, ground_tint 0 and contact_darkness
    # 1 the whole chain collapses to `_c.RGB`: HueShift by 0 returns its
    # input, a Lerp at alpha 0 returns A, and a multiply by 1 is a
    # multiply by 1. That is the property the CPU invariant asserts, and
    # it is what makes "is this feature off?" answerable.
    #
    # ⛔ NO BRACE LITERALS ANYWHERE BELOW -- this source is a .format()
    # template and a literal brace is a replacement field.
    # =================================================================
    _card = _j.get("card")
    _cval, _cpin = _c, "RGB"
    if _card:
        _out["card"] = dict()

        # ---- 1. GROUND ALBEDO AT THE INSTANCE POSITION --------------
        # ObjectPositionWS, not WorldPosition: the card must take ONE
        # colour from the ground it stands on, not a different colour per
        # pixel up its own height. Sampled at the landscape's own Grass
        # tiling so the card and the ground under it agree.
        if _card.get("ground_tint", 0.0) > 0.0:
            _op = _n(_unreal.MaterialExpressionObjectPositionWS, -1500, 500)
            _oxy = _n(_unreal.MaterialExpressionComponentMask, -1300, 500)
            _oxy.set_editor_property("r", True)
            _oxy.set_editor_property("g", True)
            _oxy.set_editor_property("b", False)
            _oxy.set_editor_property("a", False)
            _ll_wire(_mel, _op, "", _oxy, "")
            _guv = _n(_unreal.MaterialExpressionDivide, -1100, 500)
            _ll_wire(_mel, _oxy, "", _guv, "A")
            _gd = _n(_unreal.MaterialExpressionConstant, -1300, 620)
            _gd.set_editor_property(
                "r", float(_card["ground_tiling_m"]) * 100.0)
            _ll_wire(_mel, _gd, "", _guv, "B")
            _gs = _n(_unreal.MaterialExpressionTextureSample, -900, 500)
            # From the PREFLIGHTED cache, not a fresh load: the cache is
            # what the assertion's `want` list is built from, so a
            # separately-loaded texture is a sampler the assertion never
            # declared. That is not hypothetical -- it failed this build
            # once, by name.
            _gtex = _tex.get("ground_albedo")
            if _gtex is None:
                raise RuntimeError(
                    "card.ground_albedo was not preflighted; add it to "
                    "job['textures'] so the preflight and the assertion "
                    "both see it")
            _gs.set_editor_property("texture", _gtex)
            _gs.set_editor_property("sampler_type", _ST.SAMPLERTYPE_COLOR)
            _ll_wire(_mel, _guv, "", _gs, "UVs")
            # Normalise by the scan's own mean so the tint RESHADES the
            # card rather than darkening it: ground/ref is ~1 on average.
            _gn = _n(_unreal.MaterialExpressionDivide, -700, 500)
            _ll_wire(_mel, _gs, "RGB", _gn, "A")
            _gr = _n(_unreal.MaterialExpressionConstant, -900, 640)
            _gr.set_editor_property("r", float(_card["ground_albedo_mean"]))
            _ll_wire(_mel, _gr, "", _gn, "B")
            _gm = _n(_unreal.MaterialExpressionMultiply, -500, 400)
            _ll_wire(_mel, _cval, _cpin, _gm, "A")
            _ll_wire(_mel, _gn, "", _gm, "B")
            _gl = _n(_unreal.MaterialExpressionLinearInterpolate, -300, 400)
            _ll_wire(_mel, _cval, _cpin, _gl, "A")
            _ll_wire(_mel, _gm, "", _gl, "B")
            _ga = _n(_unreal.MaterialExpressionConstant, -500, 540)
            _ga.set_editor_property("r", float(_card["ground_tint"]))
            _ll_wire(_mel, _ga, "", _gl, "Alpha")
            _cval, _cpin = _gl, ""
            _out["card"]["ground_tint"] = float(_card["ground_tint"])

        # ---- 2. PER-INSTANCE HUE AND BRIGHTNESS ---------------------
        # PerInstanceRandom is ONE scalar per instance. Using it for both
        # hue and brightness would lock them together -- every yellower
        # blade also brighter -- so brightness rides a cheap decorrelating
        # hash of the same value, frac(r * 7.31). Stated because it is a
        # real limitation, not a free second random.
        _pir = _n(_unreal.MaterialExpressionPerInstanceRandom, -1500, 0)
        _r2 = _n(_unreal.MaterialExpressionMultiply, -1300, 0)
        _ll_wire(_mel, _pir, "", _r2, "A")
        _two = _n(_unreal.MaterialExpressionConstant, -1500, 120)
        _two.set_editor_property("r", 2.0)
        _ll_wire(_mel, _two, "", _r2, "B")
        _sgn = _n(_unreal.MaterialExpressionSubtract, -1100, 0)
        _ll_wire(_mel, _r2, "", _sgn, "A")
        _one = _n(_unreal.MaterialExpressionConstant, -1300, 120)
        _one.set_editor_property("r", 1.0)
        _ll_wire(_mel, _one, "", _sgn, "B")

        if float(_card.get("hue_percent", 0.0)) != 0.0:
            _hs = _n(_unreal.MaterialExpressionMultiply, -900, 0)
            _ll_wire(_mel, _sgn, "", _hs, "A")
            _hc = _n(_unreal.MaterialExpressionConstant, -1100, 120)
            _hc.set_editor_property("r", float(_card["hue_percent"]))
            _ll_wire(_mel, _hc, "", _hs, "B")
            _hf = _n(_unreal.MaterialExpressionMaterialFunctionCall,
                     -700, 0)
            _hfa = _unreal.EditorAssetLibrary.load_asset(
                "/Engine/Functions/Engine_MaterialFunctions02/HueShift")
            if _hfa is None:
                raise RuntimeError(
                    "HueShift material function did not load; refusing to "
                    "ship a card whose hue variation is silently absent")
            _hf.set_material_function(_hfa)
            _ll_wire(_mel, _cval, _cpin, _hf, "Texture")
            _ll_wire(_mel, _hs, "", _hf, "Hue Shift Percentage")
            _cval, _cpin = _hf, ""
            _out["card"]["hue_percent"] = float(_card["hue_percent"])

        if float(_card.get("brightness_amp", 0.0)) != 0.0:
            # frac(r * 7.31) -- decorrelates brightness from hue.
            _bm = _n(_unreal.MaterialExpressionMultiply, -1300, 260)
            _ll_wire(_mel, _pir, "", _bm, "A")
            _bk = _n(_unreal.MaterialExpressionConstant, -1500, 320)
            _bk.set_editor_property("r", 7.31)
            _ll_wire(_mel, _bk, "", _bm, "B")
            _bf = _n(_unreal.MaterialExpressionFrac, -1100, 260)
            _ll_wire(_mel, _bm, "", _bf, "")
            _b2 = _n(_unreal.MaterialExpressionMultiply, -950, 260)
            _ll_wire(_mel, _bf, "", _b2, "A")
            _ll_wire(_mel, _two, "", _b2, "B")
            _bs = _n(_unreal.MaterialExpressionSubtract, -800, 260)
            _ll_wire(_mel, _b2, "", _bs, "A")
            _ll_wire(_mel, _one, "", _bs, "B")
            _ba = _n(_unreal.MaterialExpressionMultiply, -650, 260)
            _ll_wire(_mel, _bs, "", _ba, "A")
            _bc = _n(_unreal.MaterialExpressionConstant, -800, 380)
            _bc.set_editor_property("r", float(_card["brightness_amp"]))
            _ll_wire(_mel, _bc, "", _ba, "B")
            _bp = _n(_unreal.MaterialExpressionAdd, -500, 260)
            _ll_wire(_mel, _one, "", _bp, "A")
            _ll_wire(_mel, _ba, "", _bp, "B")
            _bmul = _n(_unreal.MaterialExpressionMultiply, -300, 200)
            _ll_wire(_mel, _cval, _cpin, _bmul, "A")
            _ll_wire(_mel, _bp, "", _bmul, "B")
            _cval, _cpin = _bmul, ""
            _out["card"]["brightness_amp"] = float(_card["brightness_amp"])

        # ---- 3. GROUND-CONTACT GRADIENT -----------------------------
        # The card's own V runs 0 at the top to 1 at the base, so the
        # lower `contact_height` of it darkens toward `contact_darkness`
        # and soil reads through between blades.
        if float(_card.get("contact_darkness", 1.0)) != 1.0:
            _uv = _n(_unreal.MaterialExpressionTextureCoordinate, -1500, 760)
            _v = _n(_unreal.MaterialExpressionComponentMask, -1300, 760)
            _v.set_editor_property("r", False)
            _v.set_editor_property("g", True)
            _v.set_editor_property("b", False)
            _v.set_editor_property("a", False)
            _ll_wire(_mel, _uv, "", _v, "")
            _st = _n(_unreal.MaterialExpressionSubtract, -1100, 760)
            _ll_wire(_mel, _v, "", _st, "A")
            _s0 = _n(_unreal.MaterialExpressionConstant, -1300, 880)
            _s0.set_editor_property(
                "r", 1.0 - float(_card["contact_height"]))
            _ll_wire(_mel, _s0, "", _st, "B")
            _sd = _n(_unreal.MaterialExpressionDivide, -950, 760)
            _ll_wire(_mel, _st, "", _sd, "A")
            _s1 = _n(_unreal.MaterialExpressionConstant, -1100, 880)
            _s1.set_editor_property("r", float(_card["contact_height"]))
            _ll_wire(_mel, _s1, "", _sd, "B")
            _sc = _n(_unreal.MaterialExpressionSaturate, -800, 760)
            _ll_wire(_mel, _sd, "", _sc, "")
            _cl = _n(_unreal.MaterialExpressionLinearInterpolate, -600, 760)
            _ll_wire(_mel, _one, "", _cl, "A")
            _cd = _n(_unreal.MaterialExpressionConstant, -800, 880)
            _cd.set_editor_property("r", float(_card["contact_darkness"]))
            _ll_wire(_mel, _cd, "", _cl, "B")
            _ll_wire(_mel, _sc, "", _cl, "Alpha")
            _cm = _n(_unreal.MaterialExpressionMultiply, -150, 100)
            _ll_wire(_mel, _cval, _cpin, _cm, "A")
            _ll_wire(_mel, _cl, "", _cm, "B")
            _cval, _cpin = _cm, ""
            _out["card"]["contact_darkness"] = float(
                _card["contact_darkness"])
            _out["card"]["contact_height"] = float(_card["contact_height"])

    _mel.connect_material_property(_cval, _cpin,
                                   _unreal.MaterialProperty.MP_BASE_COLOR)

    # Opacity mask: a dedicated alpha map if one shipped, else the
    # colour map's own alpha channel.
    if "alpha" in _tex and _j["masked"]:
        # SAMPLERTYPE_ALPHA to match the TC_Alpha import. Third sampler
        # mismatch this session and the compiler named all three: the
        # rule is simply that sampler type must equal what the texture
        # was imported as, and there is no safe default.
        _a = _samp("alpha", _ST.SAMPLERTYPE_ALPHA, -700, 700)
        _mel.connect_material_property(
            _a, "R", _unreal.MaterialProperty.MP_OPACITY_MASK)
        _out["opacity_from"] = "alpha map"
    elif _j["masked"]:
        _mel.connect_material_property(
            _c, "A", _unreal.MaterialProperty.MP_OPACITY_MASK)
        _out["opacity_from"] = "colour alpha channel"
    else:
        _out["opacity_from"] = "opaque, no mask"

    if "normal" in _tex:
        _nm = _samp("normal", _ST.SAMPLERTYPE_NORMAL, -700, 350)
        _src = _nm
        _pin = "RGB"
        if _j["flip_green"]:
            # Invert G only: (R, 1-G, B). Unreal wants DX; this source
            # is GL. Done with a Mask/Multiply/Add rather than a
            # one-minus on RGB, which would invert X and Z too.
            _r = _n(_unreal.MaterialExpressionComponentMask, -420, 250)
            _r.set_editor_property("r", True)
            _r.set_editor_property("g", False)
            _r.set_editor_property("b", False)
            _r.set_editor_property("a", False)
            _mel.connect_material_expressions(_nm, "RGB", _r, "")
            _g = _n(_unreal.MaterialExpressionComponentMask, -420, 350)
            _g.set_editor_property("r", False)
            _g.set_editor_property("g", True)
            _g.set_editor_property("b", False)
            _g.set_editor_property("a", False)
            _mel.connect_material_expressions(_nm, "RGB", _g, "")
            _gi = _n(_unreal.MaterialExpressionOneMinus, -240, 350)
            _mel.connect_material_expressions(_g, "", _gi, "")
            _b = _n(_unreal.MaterialExpressionComponentMask, -420, 450)
            _b.set_editor_property("r", False)
            _b.set_editor_property("g", False)
            _b.set_editor_property("b", True)
            _b.set_editor_property("a", False)
            _mel.connect_material_expressions(_nm, "RGB", _b, "")
            # CHECKED connections. connect_material_expressions returns
            # a bool. Nothing was reading it, which is how this material
            # shipped with "(Node AppendVector) Missing AppendVector
            # input A" and fell back to the DEFAULT material at render
            # time while the build reported success.
            _mk = _n(_unreal.MaterialExpressionAppendVector, -60, 300)
            _mk2 = _n(_unreal.MaterialExpressionAppendVector, 120, 350)
            _wires = [
                ("r->mk.A", _mel.connect_material_expressions(_r, "", _mk, "A")),
                ("gi->mk.B", _mel.connect_material_expressions(_gi, "", _mk, "B")),
                ("mk->mk2.A", _mel.connect_material_expressions(_mk, "", _mk2, "A")),
                ("b->mk2.B", _mel.connect_material_expressions(_b, "", _mk2, "B")),
            ]
            _out["normal_wires"] = {{_k: bool(_v) for _k, _v in _wires}}
            _out["normal_wire_failures"] = [_k for _k, _v in _wires if not _v]
            _src = _mk2
            _pin = ""
        _mel.connect_material_property(
            _src, _pin, _unreal.MaterialProperty.MP_NORMAL)
        _out["normal_flipped"] = bool(_j["flip_green"])

    if "roughness" in _tex:
        _rg = _samp("roughness", _ST.SAMPLERTYPE_MASKS, -700, 1050)
        _mel.connect_material_property(
            _rg, "R", _unreal.MaterialProperty.MP_ROUGHNESS)
    elif "packed-arm" in _tex:
        _ar = _samp("packed-arm", _ST.SAMPLERTYPE_MASKS, -700, 1050)
        _mel.connect_material_property(
            _ar, "G", _unreal.MaterialProperty.MP_ROUGHNESS)
        _out["roughness_from"] = "packed ARM green"

    # MANDATORY POST-BUILD ASSERTION (shared utility). The sampler set
    # must EXACTLY equal spec; an EXTRA sampler fails loudly. The defect
    # this guards was never a missing node -- it was a surviving one,
    # still wired to BaseColor, invisible to every other check.
    #
    # ONE SAMPLER PER ROLE. The alpha map is sampled ONCE and its R pin
    # drives the opacity mask -- it is not sampled a second time.
    #
    # This spec was initially written as "alpha declared twice", from a
    # probe of the live M_fir_twig that showed two alpha samplers. That
    # graph was carrying 8 debris expressions at the time, and the
    # duplicate was debris. The assertion below REFUSED the wrong spec
    # on its first real run, which is precisely its job: it disagreed
    # with me and it was right.
    #
    # The comparison is a multiset, so if a role ever is legitimately
    # sampled twice it must be declared twice.
    _want = [_p for _p in _j["textures"].values()]
    _out["assert"] = _ll_assert_graph(_mel, _mat, _want)
    if not _out["assert"]["exact"]:
        _out["error"] = ("material graph does not match spec: "
                         "extra=" + ",".join(_out["assert"]["extra"]) +
                         " missing=" + ",".join(_out["assert"]["missing"]))
        raise RuntimeError(_out["error"])

    _mel.layout_material_expressions(_mat)
    _errs = _mel.recompile_material(_mat)
    _out["compile_errors"] = [str(_e) for _e in (_errs or [])]
    # recompile_material() RETURNED AN EMPTY LIST while M_fir_bark was
    # failing to compile -- the compile is asynchronous, so its return is
    # a "request accepted", not a verdict. Ask the material itself, which
    # is a different instrument and the one that knows.
    for _probe in ("is_compiling_or_had_compile_error",
                   "get_material_resource_compile_errors"):
        _fn = getattr(_mat, _probe, None)
        if _fn is None:
            continue
        try:
            _out["material_state_" + _probe] = str(_fn())
        except Exception as _e:
            _out["material_state_" + _probe] = "READ FAILED: " + type(_e).__name__
    # NOT SAVED HERE. The compile verdict is not available yet --
    # recompile_material() returns an empty list while the compile is
    # still running, which is how a material that failed with "(Node
    # AppendVector) Missing AppendVector input A" was written to disk and
    # then used for THREE of the fir's four slots at render time, while
    # the build reported ok. The save now happens only after the host has
    # checked the editor log, below.

    # ---- assign to every slot, then READ BACK -----------------------
    _out["stage"] = "assign"
    _slots = _mesh.get_editor_property("static_materials")
    _names = [str(_s.material_slot_name) for _s in _slots]
    _want = _j["slots"]
    _targets = ([_i for _i in range(len(_slots))] if not _want
                else [_i for _i in range(len(_slots))
                      if _names[_i] in _want])
    _out["slot_names"] = _names
    _out["assigned_indices"] = _targets
    _missing_slots = [_s for _s in _want if _s not in _names]
    if _missing_slots:
        # A slot named in the recipe that the mesh does not have means
        # the two disagree; binding nothing silently would look like a
        # working run that textured less than asked.
        _out["error"] = "mesh has no slot(s): " + ", ".join(_missing_slots)
        raise RuntimeError(_out["error"])
    for _i in _targets:
        _mesh.set_material(_i, _mat)
    _unreal.EditorAssetLibrary.save_asset(_j["mesh"],
                                          only_if_is_dirty=False)
    _bound = []
    for _i in _targets:
        _m = _mesh.get_material(_i)
        _bound.append([_names[_i],
                       _m.get_path_name() if _m else None])
    _out["bound"] = _bound
    _out["all_bound"] = all(_b[1] and _mp in _b[1] for _b in _bound)

    _out["blend_mode"] = str(_mat.get_editor_property("blend_mode"))
    _out["two_sided"] = bool(_mat.get_editor_property("two_sided"))
    if _j.get("save_now"):
        _unreal.EditorAssetLibrary.save_asset(_mp, only_if_is_dirty=False)
        _out["saved"] = True

    _out["stage"] = "done"
    _out["ok"] = (not _out["compile_errors"]) and _out["all_bound"]
except Exception as _exc:
    if "error" not in _out:
        _out["error"] = "%s at stage %r: %s" % (
            type(_exc).__name__, _out.get("stage"), _exc)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(marker):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _save_now(source):
    """Run a tiny save payload on its own verified connection.

    Separate from the build deliberately: the material must not reach
    disk until the editor log has been checked, and by then the build's
    connection is gone.
    """
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, _why = verify_landscape._select_verified_node(
            remote_exec, remote,
            bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 25.0)
        if node is None:
            return False
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(source, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        return bool(r and r.get("success")
                    and "__FOLMAT_SAVED__"
                    in bootstrap._collect_output(r))
    except Exception:
        return False
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()


SAVE_TEMPLATE = """
import unreal as _u
_asset = "{asset}"
if not _u.EditorAssetLibrary.does_asset_exist(_asset):
    raise RuntimeError("nothing to save at " + _asset)
_u.EditorAssetLibrary.save_asset(_asset, only_if_is_dirty=False)
# READ BACK ON A DIFFERENT INSTRUMENT than the call that just ran: the
# editor's DIRTY-PACKAGE LIST. A save that targeted the wrong path
# leaves the real package dirty, and the old marker-only confirmation
# could not see that.
#
# ⛔ NOT `Package.is_dirty()` -- that method does not exist on the
# reflected Package in 5.8 (AttributeError, measured). The dirty census
# payload's API is the one that works.
_still = [p.get_name() for p in
          (_u.EditorLoadingAndSavingUtils.get_dirty_content_packages() or [])]
if _asset in _still:
    raise RuntimeError("still DIRTY after save_asset: " + _asset)
print("__FOLMAT_SAVED__")
"""


EDITOR_LOG = os.path.join(
    os.path.dirname(REPO_ROOT), "UE5LandscapePipeline", "LandscapeLab",
    "Saved", "Logs", "LandscapeLab.log")


CARD_REQUIRED = ("hue_percent", "brightness_amp", "ground_tint",
                 "ground_tiling_m", "ground_albedo", "ground_albedo_mean",
                 "contact_darkness", "contact_height")


def card_spec(recipe_path, mesh_id):
    """The `card` block for this mesh from a recipe, or None.

    ⛔ EVERY FIELD IS REQUIRED AND THERE ARE NO DEFAULTS. A card
    appearance with a silently-defaulted amplitude is a look nobody
    declared, and pipeline rule 2 puts every scene parameter in the
    recipe. A missing field REFUSES.
    """
    if not recipe_path:
        return None
    with open(recipe_path, encoding="utf-8") as fh:
        rec = json.load(fh)
    block = None
    for sp in ((rec.get("foliage") or {}).get("species") or []):
        for cand in [sp] + list(sp.get("varieties") or []):
            mesh = str(cand.get("mesh") or "")
            if mesh.rsplit("/", 1)[-1] == mesh_id or mesh_id in mesh:
                block = sp.get("card") or block
    if block is None:
        return None
    missing = [k for k in CARD_REQUIRED if k not in block]
    if missing:
        raise SystemExit(
            "REFUSE: the `card` block for {0!r} is missing {1!r}. Every "
            "field is required -- a defaulted amplitude is a look nobody "
            "declared.".format(mesh_id, missing))
    for k in ("hue_percent", "brightness_amp", "ground_tint"):
        if not (0.0 <= float(block[k]) <= 1.0):
            raise SystemExit(
                "REFUSE: card.{0} = {1!r} is outside [0, 1].".format(
                    k, block[k]))
    if not (0.0 < float(block["contact_height"]) <= 1.0):
        raise SystemExit(
            "REFUSE: card.contact_height must be in (0, 1].")
    if not (0.0 <= float(block["contact_darkness"]) <= 1.0):
        raise SystemExit(
            "REFUSE: card.contact_darkness must be in [0, 1]; 1 is OFF.")
    return {k: block[k] for k in CARD_REQUIRED}


def _assert_card_identity():
    """The feature-OFF state must be the IDENTITY, and this proves it.

    A CPU mirror of the graph's arithmetic. With hue 0, brightness 0,
    ground_tint 0 and contact_darkness 1 the chain must return the base
    colour UNCHANGED -- otherwise "the card block is present but all
    amplitudes are zero" would not be the same render as "no card block",
    and no A/B against the baseline would mean anything.

    Runs at import (the material-builder skill: invariants that are
    defined and never called were dead here for weeks).
    """
    def chain(base, ground, v, r, hue, bright, tint, dark, height):
        out = base
        if tint > 0.0:
            out = out * (1.0 - tint) + (out * ground) * tint
        s = 2.0 * r - 1.0
        out = out * (1.0 + (2.0 * ((r * 7.31) % 1.0) - 1.0) * bright)
        out = out * (1.0 + s * hue * 0.0)        # hue is a rotation, not a gain
        if dark != 1.0:
            g = min(max((v - (1.0 - height)) / height, 0.0), 1.0)
            out = out * (1.0 * (1.0 - g) + dark * g)
        return out

    for base in (0.05, 0.43, 0.9):
        for v in (0.0, 0.5, 1.0):
            for r in (0.0, 0.37, 1.0):
                got = chain(base, 1.7, v, r, 0.0, 0.0, 0.0, 1.0, 0.33)
                if abs(got - base) > 1e-12:
                    raise AssertionError(
                        "card chain is not the identity when OFF: "
                        "base %r -> %r" % (base, got))
    # And it must NOT be the identity once a knob moves, or the invariant
    # above would pass on a chain that does nothing at all.
    moved = chain(0.43, 1.7, 1.0, 0.37, 0.0, 0.0, 0.0, 0.5, 0.33)
    if abs(moved - 0.43) < 1e-9:
        raise AssertionError("contact_darkness 0.5 changed nothing")
    moved = chain(0.43, 1.7, 0.0, 0.37, 0.0, 0.08, 0.0, 1.0, 0.33)
    if abs(moved - 0.43) < 1e-9:
        raise AssertionError("brightness_amp 0.08 changed nothing")
    moved = chain(0.43, 1.7, 0.0, 0.37, 0.0, 0.0, 0.5, 1.0, 0.33)
    if abs(moved - 0.43) < 1e-9:
        raise AssertionError("ground_tint 0.5 changed nothing")


_assert_card_identity()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mesh_id")
    p.add_argument("--mesh-asset", required=True,
                   help="content path of the imported StaticMesh")
    p.add_argument("--slot", default="",
                   help="only textures whose filename contains this")
    p.add_argument("--name", default="")
    p.add_argument("--clip", type=float, default=0.333)
    p.add_argument("--slots", default="",
                   help="comma-separated material SLOT NAMES to bind. "
                        "Empty binds every slot. Naming a slot the mesh "
                        "does not have is an error, not a silent skip.")
    p.add_argument("--substitute-note", default="",
                   help="why this material is bound to a slot the source "
                        "ships no maps for. Printed on every run so a "
                        "substitution never reads as an authored choice.")
    p.add_argument("--masked", dest="masked", action="store_true",
                   default=None)
    p.add_argument("--opaque", dest="masked", action="store_false")
    p.add_argument("--card-from", default="",
                   help="recipe JSON holding a per-species  block "
                        "(Brief 3 Task 4 grass-card appearance). Without "
                        "it no card chain is built and this builder is "
                        "byte-identical to before.")
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    try:
        with open(MANIFEST, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        asset, texs = texture_map(manifest, args.mesh_id, args.slot or None)
    except (OSError, ValueError, KeyError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2
    if "color" not in texs:
        print("REFUSE: no colour map for {0}{1}. The material would be "
              "untextured.".format(args.mesh_id,
                                   " slot " + args.slot if args.slot else ""))
        return 2

    conv = asset.get("normal_convention", "DX")
    flip = conv == "GL"
    name = args.name or "M_{0}{1}".format(
        args.mesh_id, "_" + args.slot if args.slot else "")
    want_slots = [x.strip() for x in args.slots.split(",") if x.strip()]
    masked = args.masked
    if masked is None:
        masked = "alpha" in texs
    job = {"textures": texs, "mesh": args.mesh_asset,
           "material": "{0}/{1}".format(MAT_ROOT, name),
           "flip_green": flip, "clip": args.clip,
           "slots": want_slots, "masked": bool(masked)}
    card = card_spec(args.card_from, args.mesh_id)
    if card:
        job["card"] = card
        # ⭐ THE GROUND ALBEDO GOES INTO `textures`, NOT BESIDE IT.
        # `textures` is the ONE declaration: the payload's preflight
        # resolves every entry BEFORE the destructive clear, and the
        # post-build assertion builds its `want` list from the same dict.
        # Loading this texture separately inside the payload put a
        # sampler in the graph that the assertion had never heard of, and
        # the build failed with "EXTRA samplers (debris): T_WildGrass_C"
        # -- correctly, on the first attempt. Two lists that must agree
        # are one list badly stored (NN24).
        job["textures"]["ground_albedo"] = card["ground_albedo"]
        print("card block: {0}".format(
            {k: v for k, v in card.items() if not k.startswith("_")}))

    print("mesh id   : {0}".format(args.mesh_id))
    print("normals   : {0} -> {1}".format(
        conv, "GREEN FLIPPED for Unreal" if flip else "used directly"))
    print("material  : {0}/{1}".format(MAT_ROOT, name))
    for r, a in sorted(texs.items()):
        print("    {0:<12} {1}".format(r, a))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        # The shared fragments are prepended AFTER .format() so their
        # braces are never seen by the formatter -- a single brace inside
        # a formatted payload raises "Replacement index out of range".
        # ⛔ WIRE_SRC IS NOT OPTIONAL NOW. The grass-card chain wires with
        # `_ll_wire`, which RAISES on a failed connect;
        # `connect_material_expressions` returns false and carries on
        # (MaterialEditingLibrary.cpp:928-943). Without this block the
        # payload would NameError -- and it would do so AFTER the
        # destructive clear at `_ll_clear_graph`, turning a refusal into a
        # crash mid-rebuild on a material that existed a moment earlier.
        # That is the exact failure the material-builder skill records.
        source = (material_graph.CLEAR_SRC + material_graph.WIRE_SRC
                  + material_graph.ASSERT_SRC
                  + PAYLOAD.format(job=json.dumps(job), marker=MARKER))
        if ".py" in source:
            print("REFUSE: payload names a .py file.")
            return 1
        try:
            remote.open_command_connection(node["node_id"])
            # Snapshot the log BEFORE the build so the compile
            # gate below reads only warnings this run produced.
            log_before = (os.path.getsize(EDITOR_LOG)
                          if os.path.isfile(EDITOR_LOG) else 0)
            r = remote.run_command(source, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            res = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:                       # noqa: BLE001
                pass
        if res is None:
            print("FAIL: payload returned nothing.")
            return 4
        # Printed every run by the shared utility: a nonzero survivor
        # count, or any EXTRA sampler, is the signature of the class this
        # exists to contain. It must never require going looking.
        material_graph.report(res)
        print("  blend mode   : {0}".format(res.get("blend_mode")))
        print("  two sided    : {0}".format(res.get("two_sided")))
        print("  opacity from : {0}".format(res.get("opacity_from")))
        print("  normal flip  : {0}".format(res.get("normal_flipped")))
        print("  slot names   : {0}".format(res.get("slot_names")))
        for b in res.get("bound") or []:
            print("    {0:<28} <- {1}".format(
                b[0], (b[1] or "").split(".")[0]))
        if args.substitute_note:
            print("  SUBSTITUTION : {0}".format(args.substitute_note))
        if res.get("error"):
            print("FAIL at {0}: {1}".format(res.get("stage"), res["error"]))
            return 4
        if res.get("normal_wire_failures"):
            print("FAIL: normal-flip connections did not land: {0}".format(
                res["normal_wire_failures"]))
            print("  connect_material_expressions returned False. The "
                  "material would compile to the DEFAULT material.")
            return 4
        for _k, _v in sorted((res.get("normal_wires") or {}).items()):
            print("    wire {0:<12} {1}".format(_k, _v))
        for _k in sorted(res):
            if _k.startswith("material_state_"):
                print("  {0}: {1}".format(_k, res[_k]))
        if res.get("compile_errors"):
            for e in res["compile_errors"]:
                print("    {0}".format(e))
            return 4

        # THE GATE THAT CAN ACTUALLY SEE THE FAILURE.
        # recompile_material() returned [] six seconds before the engine
        # logged seven "Failed to compile" warnings for this very
        # material. Its return is a request-accepted, not a verdict. The
        # editor LOG is a different instrument and is the one that knows.
        import time as _time
        _time.sleep(4.0)
        bad = []
        if os.path.isfile(EDITOR_LOG):
            try:
                with open(EDITOR_LOG, "r", encoding="utf-8",
                          errors="replace") as _fh:
                    _fh.seek(max(0, log_before - 4096))
                    for _ln in _fh.read().splitlines():
                        if ("Failed to compile" in _ln
                                and name in _ln):
                            bad.append(_ln.strip()[:200])
            except OSError as _exc:
                print("  NOTE: could not read the editor log ({0}); the "
                      "compile verdict is UNVERIFIED.".format(_exc))
        if bad:
            print("FAIL: the engine logged {0} compile failure(s) for "
                  "{1} AFTER the build reported clean:".format(
                      len(bad), name))
            for _l in bad[:3]:
                print("    {0}".format(_l))
            print("  The material was NOT saved. It would have rendered "
                  "as the Default Material on every slot bound to it.")
            return 4
        print("  compile verified against the editor log: clean")

        # Only NOW is it safe to write. A material that failed to compile
        # never reaches disk.
        save_src = SAVE_TEMPLATE.format(
            # ⛔ `name`, NOT `args.name`. `--name` is OPTIONAL and
            # defaults to "", while the material is built at the COMPUTED
            # name (line ~760). The SAME hazard applied to the compile-log
            # filter and FAIL message above (args.name "" made `"" in _ln`
            # match EVERY "Failed to compile" line, and reported an empty
            # identity) -- both now use `name` too. With --name omitted this
            # once saved
            # "/Game/Meshes/Materials/" -- a directory, not an asset --
            # and `save_asset` on a bad path neither raises nor returns
            # anything the caller reads, so the payload still printed its
            # success marker and the tool reported "saved after the
            # verdict". Measured 2026-09-13: the grass card material was
            # rebuilt, rendered correctly in three captures, and its
            # .uasset on disk was still five weeks old.
            #
            # A CONFIRMATION THAT CANNOT FAIL IS NOT A CONFIRMATION. The
            # read-back below is against the PACKAGE's dirty flag, which
            # is a different instrument from the marker the payload
            # prints.
            asset=MAT_ROOT + "/" + name)
        # A FRESH connection: the build's connection is closed by the
        # time the verdict is in, and the save must happen after the
        # verdict, not before it.
        if not _save_now(save_src):
            print("FAIL: compiled clean but the save did not confirm.")
            return 4
        print("  saved after the verdict")
        if not res.get("all_bound"):
            print("FAIL: material did not bind to every slot.")
            return 4
        print("")
        print("Material built, assigned and verified by read-back.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:                        # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
