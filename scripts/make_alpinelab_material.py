"""make_alpinelab_material.py — the mask-driven landscape material.

    python scripts/make_alpinelab_material.py --stats     # no editor
    python scripts/make_alpinelab_material.py --build     # builds
    python scripts/make_alpinelab_material.py --build --assign

WHY THIS IS NOT make_landscape_material.py
------------------------------------------
That builder surfaces /Game/Alpine, which paints landscape LAYERS and
blends by painted weight. AlpineLab_v1 has no layers and no weights. It
has five 4033-square textures Gaea computed from the same simulation
that produced the heightmap, and they are sampled by ABSOLUTE WORLD
POSITION so a texel lands on the ground it describes.

Pointing the layer builder at this terrain would mean inventing layers
to carry data that is already a texture. The two builders share what is
genuinely shared -- `material_graph`'s clear/wire/assert, which is
mandatory infrastructure (non-negotiable 4a) -- and nothing else.

THE THRESHOLDS ARE MEASURED, AND RE-MEASURED AT BUILD TIME
----------------------------------------------------------
Every gain and ramp in the recipe came from a percentile of the actual
PNG. `--stats` recomputes them, and `--build` runs the same computation
and prints PREDICTED COVERAGE for each mask before it touches the
editor. A recipe that has drifted from its data is therefore visible in
the build log rather than only in a render.

This is the CPU reference the project prefers over trusting a graph:
the material's blend is arithmetic, and the same arithmetic is done here
on the real data, so "snow covers 6.5% of the map" is a prediction the
frame can be checked against.

WHAT THE GRAPH DOES
-------------------
    mask UV   = (worldXY - origin) / extent          1 texel : 1 vertex
    detail UV = worldXY / (tile_m * 100)             photogrammetry tiling

    base            = rock
    after sediment  = lerp(base, sediment, ramp(deposits * 128))
    after snow      = lerp(that, snow,     max(ramp(depth), ramp(hard)))
    albedo         *= lerp(1, 1.22, wear)  *  lerp(1, 0.62, flow)
    roughness       = lerp(surface_r, 0.30, flow)

Normal maps are blended by the SAME weights as albedo, computed once and
shared, so a surface cannot show one material's colour with another's
relief.

WHAT IT DOES NOT DO
-------------------
No triplanar, no macro variation, no RVT, no sub-surfaces. Those are R2's
apparatus for /Game/Alpine and every one of them costs GPU on an iGPU that
has already hung once. (Grass output IS built, optionally, when the recipe
declares a `grass` block -- it spawns from the material at zero
instance-budget cost; see the grass section below.) This is the smallest
graph that answers "does the Gaea data drive a surface".
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import alpinelab_source
import bootstrap          # noqa: E402
import material_graph     # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_ALPINELAB_MAT__"
RECIPE = "recipes/alpinelab_v1.json"

# The PNGs the masks were imported FROM. Statistics are taken here, not
# from the imported .uasset: a texture's compression is a rendering
# decision, and the mask's MEANING lives in the source data.
#
# WHERE they are is declared by the RECIPE and resolved by
# alpinelab_source.resolve(). It used to be a constant here AND a second copy
# in scatter_alpinelab.py -- two places describing one fact, which is the
# structure non-negotiable 24 rejects. Bound in main() once the recipe is
# read; module scope no longer knows the answer, deliberately, so nothing can
# read a stale default.
PKG = None
MASK_PNG = None


# =====================================================================
# THE CPU REFERENCE
# =====================================================================

def _ramp(values, edge_in, edge_out):
    """The graph's ramp, in numpy. ONE definition of the shape.

    0 below edge_in, 1 above edge_out, linear between. The material
    builds exactly this out of subtract/divide/saturate, so the two can
    be compared instead of trusted.
    """
    span = edge_out - edge_in
    if abs(span) < 1e-9:
        return (values >= edge_in).astype(np.float64)
    return np.clip((values - edge_in) / span, 0.0, 1.0)


def mask_stats(recipe, verbose=True):
    """Predicted coverage per mask, from the source PNGs."""
    from PIL import Image
    out = {}
    masks = recipe["material"]["masks"]
    if verbose:
        print("PREDICTED COVERAGE (CPU reference over the source PNGs)")
        print("{0:<12s} {1:>7s} {2:>9s} {3:>9s} {4:>9s} {5:>9s}".format(
            "mask", "gain", "p90", "p99", ">0 after", "mean w"))
    for name, png in MASK_PNG.items():
        spec = masks.get(name)
        if spec is None:
            continue
        path = os.path.join(PKG, png)
        if not os.path.isfile(path):
            print("  {0}: SOURCE MISSING {1}".format(name, path))
            continue
        a = np.asarray(Image.open(path)).astype(np.float64) / 65535.0
        g = a * float(spec["gain"])
        w = _ramp(g, float(spec["ramp_in"]), float(spec["ramp_out"]))
        out[name] = {
            "p90": float(np.percentile(a, 90)),
            "p99": float(np.percentile(a, 99)),
            "coverage": float((w > 0.0).mean()),
            "full": float((w >= 1.0).mean()),
            "mean_weight": float(w.mean()),
        }
        if verbose:
            print("{0:<12s} {1:>7.1f} {2:>9.5f} {3:>9.5f} {4:>8.2%} "
                  "{5:>9.4f}".format(name, spec["gain"], out[name]["p90"],
                                     out[name]["p99"], out[name]["coverage"],
                                     out[name]["mean_weight"]))
    if verbose and out:
        # The surfaces actually visible, after the lerp ORDER is applied.
        # Snow is applied last, so it takes ground from both others.
        snow = np.maximum(
            _load_weight(recipe, "snow_depth"),
            _load_weight(recipe, "snow_hard"))
        sed = _load_weight(recipe, "deposits") * (1.0 - snow)
        rock = 1.0 - snow - sed
        print("")
        print("SURFACE SHARE OF THE MAP, after the blend order:")
        print("  rock     {0:>7.2%}".format(float(rock.mean())))
        print("  sediment {0:>7.2%}".format(float(sed.mean())))
        print("  snow     {0:>7.2%}".format(float(snow.mean())))
        out["_share"] = {"rock": float(rock.mean()),
                         "sediment": float(sed.mean()),
                         "snow": float(snow.mean())}
    return out


def _load_weight(recipe, name):
    from PIL import Image
    spec = recipe["material"]["masks"][name]
    a = np.asarray(Image.open(os.path.join(PKG, MASK_PNG[name]))
                   ).astype(np.float64) / 65535.0
    return _ramp(a * float(spec["gain"]),
                 float(spec["ramp_in"]), float(spec["ramp_out"]))


# =====================================================================
# THE PAYLOAD
# =====================================================================

# FORMATTED ALONE, then prepended with the shared fragments at call
# time. Calling .format() on the concatenation raises KeyError on the
# fragments' own dict literals: material_graph's sources are CODE, not a
# template, and escaping their braces to suit this script's formatter
# would be editing shared infrastructure to serve one caller.
PAYLOAD_BODY = '''
import json as _json
import unreal as _unreal
import os as _os
import sys as _sys
# ⭐ ll_must IS IMPORTED, NOT PASTED. ue_exec stages it beside this
# payload; MODE_EXEC_FILE gives us __file__, so the stage dir is on the
# path below. Placed HERE, at the top, so a staging failure raises
# before any graph is touched rather than half way through a build.
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ll_must as _ll_must

_out = {{}}
_spec = _json.loads(r"""{spec}""")
# None when displacement is off. build_spec owns the all-or-nothing preflight,
# so by the time this is not None every surface is known to have a height map
# (non-negotiable 24: one declaration, and the check happens BEFORE the clear).
_disp = _spec.get("displacement")

_mel = _unreal.MaterialEditingLibrary
_eal = _unreal.EditorAssetLibrary
_path = _spec["material_path"]

# PREFLIGHT BEFORE THE DESTRUCTIVE CLEAR (non-negotiable 24). The build
# dies AFTER the clear if a texture is missing, which turns
# refused-before-touching-anything into crashed-mid-rebuild.
_missing = [_p for _p in _spec["all_textures"] if not _eal.does_asset_exist(_p)]
if _missing:
    _out["error"] = "textures missing: " + ", ".join(_missing)
    print("{marker}" + _json.dumps(_out))
    raise SystemExit(0)

if _eal.does_asset_exist(_path):
    _mat = _eal.load_asset(_path)
else:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    _mat = _tools.create_asset(
        _path.rsplit("/", 1)[1], _path.rsplit("/", 1)[0],
        _unreal.Material, _unreal.MaterialFactoryNew())
_out["created"] = _mat is not None
if _mat is None:
    _out["error"] = "could not create or load " + _path
    print("{marker}" + _json.dumps(_out))
    raise SystemExit(0)

_c = _ll_clear_graph(_mel, _mat)
_out["clear"] = _c
if _c["remaining"]:
    _out["error"] = "graph not empty after total clear"
    print("{marker}" + _json.dumps(_out))
    raise SystemExit(0)


def _n(_cls, _x, _y):
    return _mel.create_material_expression(_mat, _cls, _x, _y)


def _const(_v, _x, _y):
    _e = _n(_unreal.MaterialExpressionConstant, _x, _y)
    _e.set_editor_property("r", float(_v))
    return _e


def _c3(_rgb, _x, _y):
    _e = _n(_unreal.MaterialExpressionConstant3Vector, _x, _y)
    _e.set_editor_property("constant", _unreal.LinearColor(
        float(_rgb[0]), float(_rgb[1]), float(_rgb[2]), 1.0))
    return _e


def _tex(_p, _x, _y, _uv, _normal=False, _grey=False):
    _s = _n(_unreal.MaterialExpressionTextureSample, _x, _y)
    _s.set_editor_property("texture", _eal.load_asset(_p))
    if _grey:
        # THE SAMPLER TYPE FOLLOWS THE TEXTURE'S COMPRESSION, AND A
        # MISMATCH IS FATAL, NOT COSMETIC. The masks were recompressed
        # from TC_VECTOR_DISPLACEMENTMAP to TC_GRAYSCALE (BC4) to stop
        # the editor thrashing on their DDC build. That changed what the
        # engine requires from LINEAR_COLOR to LINEAR_GRAYSCALE, the
        # samplers still declared LINEAR_COLOR, and VerifySamplerType
        # errors on EVERY mismatch -- so the whole material stopped
        # compiling and the landscape rendered UE's default checkerboard.
        # Diagnosed by MaterialEditingLibrary.recompile_material, which
        # returns the error list; the editor log only said "Failed to
        # compile Material for platform PCD3D_SM6".
        _s.set_editor_property(
            "sampler_type",
            _unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    if _normal:
        # The sampler is ASSERTED as Normal here (SAMPLERTYPE_NORMAL),
        # not auto-detected. VerifySamplerType errors on EVERY mismatch and
        # applies an extra sRGB check for Normal and Masks -- so a wrong
        # assertion here does not compile silently, it fails the build.
        _s.set_editor_property(
            "sampler_type", _unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    if _uv is not None:
        _ll_wire(_mel, _uv, "", _s, "UVs")
    return _s


def _centred_height(_path, _raw, _x, _y):
    """A height sample re-centred on ITS OWN fully-mipped value.

    Ported from make_landscape_material.py, where it was derived and proven.
    `displacement_scaling.center` is ONE scalar for the whole material and the
    height maps do not agree with it -- measured means run 0.5257 to 0.7602 --
    so a fixed 0.5 lifts each surface by a DIFFERENT constant, spending up to
    half the amplitude as DC and putting a step at every layer boundary that is
    not relief.

    A second TextureSample of the same asset, forced to the smallest mip,
    returns the texture's fully-mipped value; centred = raw - mipped + center.
    THE NEUTRAL IS READ FROM THE TEXTURE, never declared in the recipe, so it
    cannot drift when the asset is reimported or recompressed -- and these maps
    HAVE been recompressed before.
    """
    _mip = _n(_unreal.MaterialExpressionTextureSample, _x, _y)
    _mip.set_editor_property("texture", _eal.load_asset(_path))
    _mip.set_editor_property(
        "sampler_type",
        _unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    # TMVM_MIP_LEVEL = explicitly compute the sample's mip level. const_mip_value
    # is used only when the MipValue pin is unconnected, which it is. 15 is above
    # any mip chain a 4K texture can have; the sampler clamps to the smallest.
    _mip.set_editor_property(
        "mip_value_mode", _unreal.TextureMipValueMode.TMVM_MIP_LEVEL)
    _mip.set_editor_property("const_mip_value", 15)
    _sub = _n(_unreal.MaterialExpressionSubtract, _x + 200, _y)
    _ll_wire(_mel, _raw, "R", _sub, "A")
    _ll_wire(_mel, _mip, "R", _sub, "B")
    _add = _n(_unreal.MaterialExpressionAdd, _x + 360, _y)
    _ll_wire(_mel, _sub, "", _add, "A")
    _ll_wire(_mel, _const(_disp["center"], _x + 200, _y + 90), "", _add, "B")
    return _add


def _mul(_a, _apin, _b, _bpin, _x, _y):
    _e = _n(_unreal.MaterialExpressionMultiply, _x, _y)
    _ll_wire(_mel, _a, _apin, _e, "A")
    _ll_wire(_mel, _b, _bpin, _e, "B")
    return _e


def _lerp(_a, _apin, _b, _bpin, _alpha, _apin2, _x, _y):
    _e = _n(_unreal.MaterialExpressionLinearInterpolate, _x, _y)
    _ll_wire(_mel, _a, _apin, _e, "A")
    _ll_wire(_mel, _b, _bpin, _e, "B")
    _ll_wire(_mel, _alpha, _apin2, _e, "Alpha")
    return _e


def _ramp_node(_src, _pin, _edge_in, _edge_out, _x, _y):
    """(src - in) / (out - in), saturated. The CPU model's twin."""
    _span = _edge_out - _edge_in
    if abs(_span) < 1e-9:
        _span = 1e-6
    _sub = _n(_unreal.MaterialExpressionSubtract, _x, _y)
    _ll_wire(_mel, _src, _pin, _sub, "A")
    _ll_wire(_mel, _const(_edge_in, _x - 200, _y + 80), "", _sub, "B")
    _div = _n(_unreal.MaterialExpressionDivide, _x + 200, _y)
    _ll_wire(_mel, _sub, "", _div, "A")
    _ll_wire(_mel, _const(_span, _x, _y + 160), "", _div, "B")
    _sat = _n(_unreal.MaterialExpressionSaturate, _x + 400, _y)
    _ll_wire(_mel, _div, "", _sat, "")
    return _sat


# ---- UV SOURCES -----------------------------------------------------
_wp = _n(_unreal.MaterialExpressionWorldPosition, -3000, 0)
_wxy = _n(_unreal.MaterialExpressionComponentMask, -2800, 0)
_wxy.set_editor_property("r", True)
_wxy.set_editor_property("g", True)
_wxy.set_editor_property("b", False)
_wxy.set_editor_property("a", False)
_ll_wire(_mel, _wp, "", _wxy, "")

# mask UV = (worldXY - origin) / extent. One texel per landscape vertex.
_mo = _n(_unreal.MaterialExpressionSubtract, -2600, -200)
_ll_wire(_mel, _wxy, "", _mo, "A")
_ll_wire(_mel, _const(_spec["origin_cm"], -2800, -120), "", _mo, "B")
_mask_uv = _n(_unreal.MaterialExpressionDivide, -2400, -200)
_ll_wire(_mel, _mo, "", _mask_uv, "A")
_ll_wire(_mel, _const(_spec["extent_cm"], -2600, -120), "", _mask_uv, "B")

# ---- MASKS ----------------------------------------------------------
_weights = {{}}
_y = -1400
for _name in _spec["mask_order"]:
    _m = _spec["masks"][_name]
    _s = _tex(_m["texture"], -2100, _y, _mask_uv, _grey=True)
    _g = _mul(_s, "R", _const(_m["gain"], -1900, _y + 90), "", -1750, _y)
    _weights[_name] = _ramp_node(_g, "", _m["ramp_in"], _m["ramp_out"],
                                 -1500, _y)
    _y += 320

# snow = max(depth, hard) -- the hard mask is binary and guarantees the
# core, the graded one gives the edge.
_snow = _n(_unreal.MaterialExpressionMax, -900, -1400)
_ll_wire(_mel, _weights["snow_depth"], "", _snow, "A")
_ll_wire(_mel, _weights["snow_hard"], "", _snow, "B")

# ---- SURFACES -------------------------------------------------------
_surf = {{}}
_y = 200
for _name in _spec["surface_order"]:
    _s = _spec["surfaces"][_name]
    _uv = _n(_unreal.MaterialExpressionDivide, -2400, _y)
    _ll_wire(_mel, _wxy, "", _uv, "A")
    _ll_wire(_mel, _const(_s["tile_m"] * 100.0, -2600, _y + 80), "", _uv, "B")
    _col = _tex(_s["color"], -2100, _y, _uv)
    _tinted = _mul(_col, "RGB", _c3(_s["tint"], -1900, _y + 90), "",
                   -1750, _y)
    _surf[_name] = {{
        "color": _tinted,
        "color_pin": "",
        "normal": _tex(_s["normal"], -2100, _y + 160, _uv, True),
        "rough": _tex(_s["roughness"], -2100, _y + 320, _uv),
    }}
    if _disp is not None:
        # The _D maps are TC_GRAYSCALE with srgb False (read from the live
        # assets), so LINEAR_GRAYSCALE is what VerifySamplerType requires.
        # A mismatch is a BUILD FAILURE, not a silent wrong -- it errors on
        # every mismatch and the landscape renders the default checkerboard.
        _raw_h = _tex(_s["displacement"], -2100, _y + 400, _uv, _grey=True)
        _surf[_name]["disp"] = (
            _centred_height(_s["displacement"], _raw_h, -1700, _y + 400)
            if _disp["centred"] else _raw_h)
        _surf[_name]["disp_pin"] = "" if _disp["centred"] else "R"
    _y += 640

# ---- BLEND, one weight set shared by colour, normal and roughness ---
_dep = _weights["deposits"]
_col = _lerp(_surf["rock"]["color"], "", _surf["sediment"]["color"], "",
             _dep, "", -1200, 200)
_col = _lerp(_col, "", _surf["snow"]["color"], "", _snow, "", -1000, 200)

_nrm = _lerp(_surf["rock"]["normal"], "RGB",
             _surf["sediment"]["normal"], "RGB", _dep, "", -1200, 600)
_nrm = _lerp(_nrm, "", _surf["snow"]["normal"], "RGB", _snow, "",
             -1000, 600)

_rgh = _lerp(_surf["rock"]["rough"], "R", _surf["sediment"]["rough"], "R",
             _dep, "", -1200, 1000)
_rgh = _lerp(_rgh, "", _surf["snow"]["rough"], "R", _snow, "", -1000, 1000)

# ---- MODULATORS -----------------------------------------------------
_wm = _spec["modulators"]["wear_lighten"]
_wear_gain = _lerp(_const(1.0, -900, 300), "",
                   _const(_wm["albedo_gain_at_1"], -900, 380), "",
                   _weights["wear"], "", -700, 340)
_col = _mul(_col, "", _wear_gain, "", -500, 200)

_fm = _spec["modulators"]["flow_wet"]
_flow_gain = _lerp(_const(1.0, -900, 460), "",
                   _const(_fm["albedo_gain_at_1"], -900, 540), "",
                   _weights["flow"], "", -700, 500)
_col = _mul(_col, "", _flow_gain, "", -300, 200)

_rgh = _lerp(_rgh, "", _const(_fm["roughness_at_1"], -900, 1080), "",
             _weights["flow"], "", -700, 1000)

# ---- GRASS ----------------------------------------------------------
# The landscape grass system, not instanced foliage: the GrassOutput
# node spawns from the material at zero instance-budget cost, which is
# the only way to get ground cover at this density on this machine.
# Construction follows make_landscape_material.py:3093-3181 -- the
# fiddly parts are proven there and are NOT re-derived: grass_density is
# INSTANCES PER 10 SQUARE METRES, and density and cull distances refuse
# plain numbers because they are PerPlatformFloat / PerPlatformInt.
if _spec.get("grass"):
    _g = _spec["grass"]
    _gtpath = _g["grass_type_path"]
    if _eal.does_asset_exist(_gtpath):
        _gt = _eal.load_asset(_gtpath)
    else:
        _gt = _unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            _gtpath.rsplit("/", 1)[1], _gtpath.rsplit("/", 1)[0],
            _unreal.LandscapeGrassType, _unreal.LandscapeGrassTypeFactory())
    _built = []
    for _v in _g["varieties"]:
        _mesh = _eal.load_asset(_v["mesh"])
        if _mesh is None:
            _out.setdefault("grass_missing", []).append(_v["mesh"])
            continue
        _gv = _unreal.GrassVariety()
        _gv.set_editor_property("grass_mesh", _mesh)
        _gv.set_editor_property(
            "grass_density", _unreal.PerPlatformFloat(_v["density"]))
        _gv.set_editor_property(
            "start_cull_distance",
            _unreal.PerPlatformInt(int(_g["cull_cm"] * 0.75)))
        _gv.set_editor_property(
            "end_cull_distance", _unreal.PerPlatformInt(int(_g["cull_cm"])))
        _gv.set_editor_property("align_to_surface", True)
        _gv.set_editor_property("random_rotation", True)
        _built.append(_gv)
    _gt.set_editor_property("grass_varieties", _built)
    # CHECKED SAVE. The read-back below reads PROPERTIES off the
    # in-memory object, which proves the setter ran, not that the
    # package reached disk. must_save proves the second.
    _ll_must.must_save(_gtpath, _eal)

    # READ BACK. A density that did not land is a field that reads like
    # a setting (non-negotiable 17), and PerPlatformFloat is exactly the
    # kind of wrapper that silently refuses a plain number.
    _rows = []
    for _gv in (_gt.get_editor_property("grass_varieties") or []):
        _d = _gv.get_editor_property("grass_density")
        _rows.append(float(_d.get_editor_property("default")))
    _out["grass"] = {{"varieties": len(_rows), "densities": _rows}}

    # WHERE GRASS GROWS: not under snow, and not on stripped ridges.
    # One minus each, multiplied -- the same weights the surfaces use,
    # so the grass cannot disagree with the ground it stands on.
    _one = _const(1.0, 300, -1500)
    _nosnow = _n(_unreal.MaterialExpressionSubtract, 450, -1500)
    _ll_wire(_mel, _one, "", _nosnow, "A")
    _ll_wire(_mel, _snow, "", _nosnow, "B")
    _nowear = _n(_unreal.MaterialExpressionSubtract, 450, -1350)
    _ll_wire(_mel, _const(1.0, 300, -1350), "", _nowear, "A")
    _ll_wire(_mel, _weights["wear"], "", _nowear, "B")
    _gweight = _mul(_nosnow, "", _nowear, "", 620, -1420)

    _gi = _unreal.GrassInput()
    _gi.set_editor_property("name", _g["name"])
    _gi.set_editor_property("grass_type", _gt)
    _go = _n(_unreal.MaterialExpressionLandscapeGrassOutput, 900, -1420)
    _go.set_editor_property("grass_types", [_gi])
    _ll_wire(_mel, _gweight, "", _go, _g["name"])
    _out["grass"]["wired"] = True

# ---- OUTPUTS --------------------------------------------------------
if _disp is None:
    _mat.set_editor_property("use_material_attributes", False)
    _mel.connect_material_property(_col, "", _unreal.MaterialProperty.MP_BASE_COLOR)
    _mel.connect_material_property(_rgh, "", _unreal.MaterialProperty.MP_ROUGHNESS)
    _mel.connect_material_property(_nrm, "", _unreal.MaterialProperty.MP_NORMAL)
else:
    # MP_Displacement EXISTS at value 32 (SceneTypes.h:181) but is
    # UMETA(Hidden), so it is NOT in the Python MaterialProperty enum and
    # connect_material_property CANNOT wire it. The only route is
    # use_material_attributes + MakeMaterialAttributes, which carries
    # FExpressionInput Displacement, into MP_MATERIAL_ATTRIBUTES (33, exposed).
    #
    # Metallic and Specular are left unwired deliberately:
    # FMaterialAttributesInput::CompileWithDefault falls back to the registered
    # defaults (Specular .5 / Metallic 0), so this is the SAME shading the
    # three-pin route produced, not a black metal landscape.
    _dsp = _lerp(_surf["rock"]["disp"], _surf["rock"]["disp_pin"],
                 _surf["sediment"]["disp"], _surf["sediment"]["disp_pin"],
                 _dep, "", -1200, 1400)
    _dsp = _lerp(_dsp, "", _surf["snow"]["disp"], _surf["snow"]["disp_pin"],
                 _snow, "", -1000, 1400)

    _mma = _n(_unreal.MaterialExpressionMakeMaterialAttributes, 600, 600)
    # Every wire below is CHECKED -- _ll_wire raises on a failed connect.
    # ConnectMaterialExpressions returns false and connects NOTHING for an
    # unresolvable pin name, leaving a material that compiles clean and
    # renders the default. These four names are exactly what non-negotiable 23
    # says not to trust from memory.
    _ll_wire(_mel, _col, "", _mma, "BaseColor")
    _ll_wire(_mel, _rgh, "", _mma, "Roughness")
    _ll_wire(_mel, _nrm, "", _mma, "Normal")
    _ll_wire(_mel, _dsp, "", _mma, "Displacement")
    _mat.set_editor_property("use_material_attributes", True)
    _mel.connect_material_property(
        _mma, "", _unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)

    # THE MATERIAL-LEVEL GATE. enable_tessellation is "Whether or not
    # tessellation is enabled. Required for displacement to work."
    # (PythonStub :81519). Without it the Displacement pin is wired, compiles,
    # and does NOTHING -- the silent-no-op shape this project keeps paying for.
    _mat.set_editor_property("enable_tessellation", True)
    _scaling = _mat.get_editor_property("displacement_scaling")
    _scaling.set_editor_property("magnitude", float(_disp["magnitude"]))
    _scaling.set_editor_property("center", float(_disp["center"]))
    _mat.set_editor_property("displacement_scaling", _scaling)

    # READ BACK. A gate that did not land is worse than one that is off,
    # because the graph says displacement and the renderer says none.
    _out["displacement"] = {{
        "use_material_attributes": bool(
            _mat.get_editor_property("use_material_attributes")),
        "enable_tessellation": bool(
            _mat.get_editor_property("enable_tessellation")),
        "magnitude": float(_mat.get_editor_property(
            "displacement_scaling").get_editor_property("magnitude")),
        "center": float(_mat.get_editor_property(
            "displacement_scaling").get_editor_property("center")),
    }}

_mel.recompile_material(_mat)
_eal.save_asset(_path, False)

_a = _ll_assert_graph(_mel, _mat, _spec["all_textures"])
_out["assert"] = _a
try:
    _out["expressions"] = len(
        _mat.get_editor_property("expression_collection").expressions)
except Exception as _e:
    # A count is a nicety; a failed read reports itself rather than
    # taking the build down (non-negotiable 6).
    _out["expressions"] = "could not read: " + type(_e).__name__

# ---- OPTIONAL ASSIGNMENT -------------------------------------------
if _spec["assign"]:
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _lands = [_a2 for _a2 in _eas.get_all_level_actors()
              if isinstance(_a2, _unreal.Landscape)]
    if len(_lands) != 1:
        _out["assign"] = "REFUSED: {{0}} landscapes".format(len(_lands))
    else:
        _lands[0].set_editor_property("landscape_material", _mat)
        _back = _lands[0].get_editor_property("landscape_material")
        _out["assign"] = ("ok" if _back is not None
                          and _back.get_path_name().startswith(_path)
                          else "READBACK MISMATCH: " + str(_back))
        _out["assigned_path"] = _back.get_path_name() if _back else None

for _v in ("_mel", "_eal", "_mat", "_wp", "_wxy", "_mask_uv", "_col",
           "_nrm", "_rgh", "_snow", "_weights", "_surf", "_lands"):
    globals().pop(_v, None)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    for line in text.splitlines():
        if MARKER in line:
            try:
                return json.loads(line.split(MARKER, 1)[1])
            except Exception:
                return None
    return None


def build_spec(recipe, assign):
    mat = recipe["material"]
    surfaces = {k: v for k, v in mat["surfaces"].items()
                if not k.startswith("_")}
    masks = {k: v for k, v in mat["masks"].items() if not k.startswith("_")}
    all_tex = []
    for m in masks.values():
        all_tex.append(m["texture"])
    for s in surfaces.values():
        all_tex += [s["color"], s["normal"], s["roughness"]]

    # DISPLACEMENT IS ALL-OR-NOTHING, AND THE PREFLIGHT DECIDES IT HERE.
    # Every surface must declare a height map or none may. A partial set
    # would blend a real height against a missing one and put a cliff at the
    # layer boundary -- and it would do so AFTER the destructive graph clear,
    # which is the sub-surface trap R2 already paid for (non-negotiable 24:
    # the preflight and the assertion must derive from one declaration).
    disp = (mat.get("displacement") or {})
    disp_on = bool(disp.get("enabled"))
    if disp_on:
        missing = [k for k, s in surfaces.items() if not s.get("displacement")]
        if missing:
            raise SystemExit(
                "REFUSE: material.displacement.enabled is true but these "
                "surfaces declare no `displacement` texture: %s. Displacement "
                "is all-or-nothing; a partial set puts a step at every layer "
                "boundary. Refusing BEFORE the graph is cleared."
                % ", ".join(sorted(missing)))
        # DECLARE THE SAMPLE COUNT, NOT THE TEXTURE COUNT. _ll_assert_graph
        # compares MULTISETS by default (material_graph.py:155) -- a texture
        # sampled twice must be declared twice -- and that is the stricter
        # check, so the fix for a mismatch is to declare the truth rather than
        # to switch it to _distinct=True and weaken it.
        #
        # With centre_on_mip on, _centred_height adds a SECOND TextureSample of
        # each height map forced to its smallest mip, so each is sampled twice:
        # 14 + 3*2 = 20. This is the same +1-per-_D-map that R2 records for
        # /Game/Alpine ("every _D map connected 2 (raw + forced-mip), was 1").
        _per_disp = 2 if bool(disp.get("centre_on_mip", True)) else 1
        for s in surfaces.values():
            all_tex.extend([s["displacement"]] * _per_disp)

    return {
        "displacement": ({"magnitude": float(disp["magnitude"]),
                          "center": float(disp.get("center", 0.5)),
                          "centred": bool(disp.get("centre_on_mip", True))}
                         if disp_on else None),
        "material_path": mat["path"],
        "origin_cm": recipe["landscape"]["origin_cm"],
        "extent_cm": recipe["landscape"]["extent_cm"],
        "masks": masks,
        "mask_order": ["flow", "wear", "deposits", "snow_depth", "snow_hard"],
        "surfaces": surfaces,
        "surface_order": ["rock", "sediment", "snow"],
        "modulators": {k: v for k, v in mat["modulators"].items()
                       if not k.startswith("_")},
        "all_textures": all_tex,
        "assign": bool(assign),
        "grass": mat.get("grass"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=RECIPE)
    ap.add_argument("--stats", action="store_true",
                    help="CPU reference only. No editor.")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--assign", action="store_true",
                    help="also set it as the landscape's material")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)

    path = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    with open(path, encoding="utf-8") as fh:
        recipe = json.load(fh)

    # Bind the source location from the recipe. Refuses rather than
    # defaulting -- see alpinelab_source.py.
    global PKG, MASK_PNG
    try:
        PKG, MASK_PNG, _ = alpinelab_source.resolve(recipe, args.recipe)
    except alpinelab_source.SourceError as exc:
        print("REFUSE:", exc)
        return 2

    print("recipe   : {0}".format(args.recipe))
    print("source   : {0}".format(PKG))
    print("material : {0}".format(recipe["material"]["path"]))
    print("")
    mask_stats(recipe)
    print("")

    if not args.build:
        print("STATS ONLY. Nothing was built. Re-run with --build.")
        return 0

    spec = build_spec(recipe, args.assign)
    print("textures : {0} declared".format(len(spec["all_textures"])))
    print("assign   : {0}".format("YES" if args.assign else "no"))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            payload = (material_graph.CLEAR_SRC
                       + material_graph.WIRE_SRC
                       + material_graph.ASSERT_SRC
                       + PAYLOAD_BODY.format(
                           marker=MARKER,
                           spec=json.dumps(spec).replace('"""', '')))
            # DELIVERED AS A FILE. MODE_EXEC_FILE means the command IS a
            # filename; sending source inline happens to work for short
            # commands and silently fails for longer ones, surfacing as
            # "Could not load Python file 'C:/.../Win64/<your source>'".
            # Measured 2026-08-09 by bisecting a payload byte by byte.
            payload_file = os.path.join(
                bootstrap.UE_PROJECT_ROOT, "Saved",
                "landscapelab_material_payload.py")
            os.makedirs(os.path.dirname(payload_file), exist_ok=True)
            with open(payload_file, "w", encoding="utf-8") as fh:
                fh.write(payload)
            r = remote.run_command(
                payload_file.replace("\\", "/"),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            raw = bootstrap._collect_output(r) if r else ""
            data = _parse(raw)
            if data is None:
                print("NO PARSEABLE RESULT. The LAST 6000 chars of the output "
                      "follow -- the tail, where a payload failure surfaces. "
                      "Printed (not parsed) because a build you cannot repeat "
                      "cheaply must leave its evidence readable (NN14).")
                print(raw[-6000:])
                return 4
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data.get("error"):
        print("BUILD REFUSED: {0}".format(data["error"]))
        return 3
    print("clear    : {0}".format(data.get("clear")))
    a = data.get("assert") or {}
    print("assert   : exact={0}  got={1}  extra={2}  missing={3}".format(
        a.get("exact"), len(a.get("got") or []), a.get("extra"),
        a.get("missing")))
    if not a.get("exact"):
        print("THE GRAPH DOES NOT MATCH SPEC. Extra nodes are the failure "
              "mode this assertion exists for.")
        return 5
    if "assign" in data:
        print("assign   : {0}  -> {1}".format(data["assign"],
                                              data.get("assigned_path")))
        if data["assign"] != "ok":
            return 5
    print("")
    print("BUILT. The material is saved; the LEVEL is not -- if --assign "
          "was used, File > Save All in the editor to persist it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
