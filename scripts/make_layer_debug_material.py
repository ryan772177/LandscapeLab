"""make_layer_debug_material.py — DIAGNOSTIC layer-visualisation material.

**THIS IS NOT SCENE OUTPUT.** It builds a debug material that paints each
recipe layer in a flat, deliberately artificial colour so the slope/height
blend *geometry* can be seen and judged independently of appearance. If
the blend is wrong, it should be obvious in flat colours rather than
hidden behind plausible-looking terrain.

THE FENCE (formalised at Ryan's instruction — treat as inviolable)
  1. Writes to a clearly-named debug asset path: /Game/Debug/M_LayerDebug
     by default. Never to material.parent_material.
  2. Captures produced from it carry a `_debug` suffix and go to
     captures/ like any other capture.
  3. Changelog entries for debug renders are marked DIAGNOSTIC, never
     presented as scene output.
  4. It does not satisfy the auto-material milestone deliverable and must
     never be described as if it does.

The debug colours are NOT recipe `base_color` values. They are fixed,
maximally-distinguishable primaries chosen so adjacent layers cannot be
confused. That is legitimate precisely because this is a diagnostic
instrument, not scene authoring — hard rule 2 governs scene parameters,
and a debug colour ramp is an instrument reading, like the colour of a
thermal camera's false-colour palette. The material this proves out will
take its colours from the recipe.

SCENE MUTATION: creates assets (material, and optionally assigns it to
the landscape with --assign). Asset creation goes through
unreal.AssetTools / MaterialEditingLibrary — the editor API — which
conduct rule 4 permits; rule 4 forbids direct on-disk .uasset edits.
Find-or-create, so re-runs never duplicate (hard rule 3).

WHERE THE MASKS COME FROM — CHANGED 2026-08-01, READ THIS
When the recipe carries a baked weightmap, this material samples THAT,
exactly as `make_landscape_material.py` does, using the UV derivation
imported from `make_landscape_material.weightmap_uv_params`.

It used to always compute slope bands from the vertex normal. That is the
measurement the weightmap bake exists to REPLACE — the shader normal is
the normal of the decimated mesh, so it flattens with every LOD step. Left
alone, this instrument would have kept working and started visualising a
decision the shipping material no longer makes, in confident false
colour, while being used to diagnose that very material. The vertex-normal
path is retained only for a recipe with no weightmap, and the run prints
which source is in use.

The material is UNLIT and writes to EMISSIVE. A lit false-colour readout
is not a measurement: sun angle, sky colour and fog tint the colours, so a
warm cast is ambiguous between "different layer here" and "differently lit
here". If the shading model cannot be set, that is reported and base
colour stays connected — a lit frame is never silently read as unlit.

HOW THE VERTEX-NORMAL MASKS ARE BUILT (fallback path only)
Slope: the vertex normal's world Z equals cos(slope). cos is monotonically
decreasing over 0..90 deg, so `slope <= S` is exactly `normal.z >= cos(S)`.
The recipe's degree thresholds are converted to cosines on the CPU and
compared directly, which avoids needing an inverse-trig expression at all.

Height: absolute world Z, compared against thresholds converted from the
recipe's heightmap-zero-relative `height_m` using the schema's datum
formula, world_z_cm = actor_z_cm + height_m*100 - z_scale_cm/2.

Band masks feather OUTWARD: each mask is 1 across its entire inclusive
band — including exactly at the thresholds, so first-match-wins holds at
shared boundaries like Snow/Grass at 1536 m — and ramps to 0 over the
feather width OUTSIDE the band. (An inward ramp would reach 0 AT the
threshold, painting the near-black "unmatched" colour along every shared
layer edge and faking a coverage gap that is not in the recipe.) Feather
widths are diagnostic instrument constants scaled by (1-blend_sharpness),
IMPORTED from make_landscape_material so they cannot drift from the shipping
material: up to `mlm.SLOPE_FEATHER_MAX_DEG` degrees per slope edge (12 deg at
blend_sharpness 0), converted per edge to normal.z units via sin(edge)*dtheta
because a constant cosine-unit width is wildly non-uniform in degrees; and up
to `mlm.HEIGHT_FEATHER_MAX_FRAC` of the height range per height edge (6%).
They are instrument scaling, not scene parameters.

Layer priority: schema v1 evaluates layers first-match-wins. In a shader
that is reproduced by compositing from the LAST layer to the FIRST, each
Lerp'd over the accumulated result, so layer 0 ends up on top.

Exit codes:
  0  material built (and assigned, if --assign)
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid (incl. a
     non-positive emissive scale, whether from --emissive-scale or the recipe)
  3  editor identity gate refused (conduct rule 7)
  4  material build failed in the editor
  5  --assign requested but the landscape was not found or not unique

Unreal APIs used (long-stable for UE5 except where flagged):
  unreal.AssetToolsHelpers.get_asset_tools().create_asset
  unreal.MaterialFactoryNew
  unreal.MaterialEditingLibrary.create_material_expression
      / connect_material_expressions / connect_material_property
      / recompile_material / layout_material_expressions
      (5.8 note: recompile_material RETURNS the compile-error array,
      TArray<FString> — MaterialEditingLibrary.h:263-267. Earlier UE5
      returned nothing; the `or []` below tolerates both.)
  unreal.EditorAssetLibrary.does_asset_exist / load_asset / save_asset

NO landscape usage flag is set, deliberately: UE 5.8 REMOVED
MATUSAGE_Landscape from EMaterialUsage (MaterialInterface.h:76-136 — the
enum runs SkeletalMesh..Curves with no Landscape entry). The material's
own resource answers IsUsedWithLandscape() false unconditionally
(MaterialShared.cpp:1869-1872); landscape rendering supplies its own
FLandscapeMaterialResource whose IsUsedWithLandscape() is true
(LandscapeRender.cpp:3926-3929). Calling the pre-5.8 flag API would
raise AttributeError on the missing enum entry.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import import_heightmap   # noqa: E402 — shared schema v1.1 material validator
import landscape_spec     # noqa: E402 — shared recipe loading
import make_landscape_material as mlm  # noqa: E402 — normative feather widths
import verify_landscape   # noqa: E402 — shared node selection

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_LAYERDEBUG__"

DEFAULT_ASSET_PATH = "/Game/Debug/M_LayerDebug"

# Fixed, maximally-distinguishable diagnostic colours. NOT recipe values.
# Chosen so adjacent layers can never be visually confused, and so nobody
# mistakes a debug render for scene output.
DEBUG_PALETTE = [
    [1.0, 0.0, 1.0],   # magenta
    [0.0, 1.0, 1.0],   # cyan
    [1.0, 1.0, 0.0],   # yellow
    [1.0, 0.35, 0.0],  # orange
    [0.2, 1.0, 0.2],   # green
    [0.4, 0.4, 1.0],   # blue
]
UNMATCHED_COLOUR = [0.05, 0.05, 0.05]  # near-black: matched no layer


def _layer_thresholds(recipe):
    """Convert recipe layer bounds into shader-comparable numbers.

    Returns a list of dicts, in recipe order, each carrying:
      cos_hi / cos_lo      — normal.z bounds (note the inversion: a LARGER
                             slope means a SMALLER normal.z)
      z_lo / z_hi          — absolute world Z in cm
      slope_feather_lo/_hi — per-edge OUTWARD feather in normal.z units
                             (lo edge = the steep s_hi bound, hi edge =
                             the flat s_lo bound)
      height_feather       — per-edge OUTWARD feather in cm

    Feather widths are instrument constants (see module docstring), from
    blend_sharpness (1 = hard edge, 0 = wide). The slope feather is
    specified in DEGREES (max mlm.SLOPE_FEATHER_MAX_DEG = 12 per edge) and
    converted per edge via the
    local derivative sin(edge)*dtheta, because a constant cosine-unit
    width spans ~42 degrees at the flat end but ~1.5 near vertical —
    a distortion that would misread as a recipe problem. At edges of 0 or
    90 degrees sin() -> 0 and the clamp makes the edge hard, which is
    correct: those are the range extremes.
    """
    ls = recipe["landscape"]
    actor_z = float(ls["location_cm"][2])
    z_scale = float(ls["z_scale_cm"])

    def world_z(height_m):
        # schema.md "Height datum (normative)"
        return actor_z + height_m * 100.0 - z_scale / 2.0

    out = []
    for i, layer in enumerate(recipe["material"]["layers"]):
        s_lo, s_hi = [float(v) for v in layer["slope_deg"]]
        h_lo, h_hi = [float(v) for v in layer["height_m"]]
        sharp = float(layer["blend_sharpness"])
        # R2, ruled 2026-08-01: the feather width is NORMATIVE and shared
        # with the real material. This file previously carried its own
        # 10 deg / 5% constants, which meant the instrument disagreed with
        # the thing it measures — it rendered every band ~20% narrower
        # than the shipping material and its coverage readings were not
        # comparable to anything. Imported, not copied, so they cannot
        # drift again.
        feather_deg = (1.0 - sharp) * mlm.SLOPE_FEATHER_MAX_DEG
        feather_rad = math.radians(feather_deg)
        out.append({
            "index": i,
            "name": layer["name"],
            "cos_lo": math.cos(math.radians(s_hi)),  # steepest -> lowest z
            "cos_hi": math.cos(math.radians(s_lo)),  # flattest -> highest z
            "z_lo": world_z(h_lo),
            "z_hi": world_z(h_hi),
            "slope_feather_lo": max(
                1e-4, math.sin(math.radians(s_hi)) * feather_rad),
            "slope_feather_hi": max(
                1e-4, math.sin(math.radians(s_lo)) * feather_rad),
            "height_feather": max(
                1.0, (1.0 - sharp) * z_scale * mlm.HEIGHT_FEATHER_MAX_FRAC),
            "colour": DEBUG_PALETTE[i % len(DEBUG_PALETTE)],
        })
    return out


def _payload(asset_path, layers, assign, actor_name,
             weightmap=None, org_x=0.0, org_y=0.0, span_cm=1.0,
             emissive_scale=1.0):
    return '''
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

_asset_path = {asset!r}
_layers = _json.loads({layers!r})
_unmatched = _json.loads({unmatched!r})
_assign = {assign!r}
_actor_name = {actor!r}
_weightmap = {weightmap!r}
_org_x = {org_x!r}
_org_y = {org_y!r}
_span_cm = {span_cm!r}
_emissive_scale = {emissive_scale!r}

_out = {{"ok": False, "created": False, "assigned": False, "layers": [],
        "mask_source": "weightmap" if _weightmap else "vertex_normal",
        "unlit": False}}

_pkg_path, _asset_name = _asset_path.rsplit("/", 1)

# Find-or-create (hard rule 3): never a second asset on re-run.
if _unreal.EditorAssetLibrary.does_asset_exist(_asset_path):
    _mat = _unreal.EditorAssetLibrary.load_asset(_asset_path)
else:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    _mat = _tools.create_asset(_asset_name, _pkg_path, _unreal.Material,
                               _unreal.MaterialFactoryNew())
    _out["created"] = True

if _mat is None:
    _out["error"] = "could not find or create material"
else:
    _mel = _unreal.MaterialEditingLibrary
    # Rebuild from scratch every run so the graph always reflects the
    # recipe rather than accumulating stale nodes.
    _mel.delete_all_material_expressions(_mat)
    # No landscape usage flag: UE 5.8 removed MATUSAGE_Landscape from
    # EMaterialUsage (MaterialInterface.h:76-136); the landscape's own
    # material resources report landscape usage (LandscapeRender.cpp:3926).

    _x, _y = -1800, 0

    def _const(_v, _px, _py):
        _n = _mel.create_material_expression(
            _mat, _unreal.MaterialExpressionConstant, _px, _py)
        _n.set_editor_property("r", float(_v))
        return _n

    def _const3(_rgb, _px, _py):
        _n = _mel.create_material_expression(
            _mat, _unreal.MaterialExpressionConstant3Vector, _px, _py)
        _n.set_editor_property(
            "constant", _unreal.LinearColor(
                float(_rgb[0]), float(_rgb[1]), float(_rgb[2]), 1.0))
        return _n

    def _node(_cls, _px, _py):
        return _mel.create_material_expression(_mat, _cls, _px, _py)

    # --- inputs: normal.z (= cos slope) and world Z -------------------
    _normal = _node(_unreal.MaterialExpressionVertexNormalWS, _x, -400)
    _nmask = _node(_unreal.MaterialExpressionComponentMask, _x + 250, -400)
    _nmask.set_editor_property("r", False)
    _nmask.set_editor_property("g", False)
    _nmask.set_editor_property("b", True)
    _nmask.set_editor_property("a", False)
    _mel.connect_material_expressions(_normal, "", _nmask, "")

    _wpos = _node(_unreal.MaterialExpressionWorldPosition, _x, 200)
    _zmask = _node(_unreal.MaterialExpressionComponentMask, _x + 250, 200)
    _zmask.set_editor_property("r", False)
    _zmask.set_editor_property("g", False)
    _zmask.set_editor_property("b", True)
    _zmask.set_editor_property("a", False)
    _mel.connect_material_expressions(_wpos, "", _zmask, "")

    def _band(_value_node, _lo, _hi, _f_lo, _f_hi, _px, _py):
        """Soft in-range mask, feathered OUTWARD:
        saturate((v - (lo - f_lo)) / f_lo) * saturate(((hi + f_hi) - v) / f_hi)
        == 1 across the whole inclusive band [lo, hi] — including exactly
        at the thresholds, so first-match-wins holds where two layers
        share a boundary — ramping to 0 over the feather OUTSIDE the
        band. The obvious inward ramp saturate((v-lo)/f) reaches 0 AT the
        threshold, which would paint the near-black unmatched colour
        along every shared layer edge: a fake coverage gap."""
        _lo_edge = _lo - _f_lo
        _hi_edge = _hi + _f_hi
        _sub_lo = _node(_unreal.MaterialExpressionSubtract, _px, _py)
        _mel.connect_material_expressions(_value_node, "", _sub_lo, "A")
        _mel.connect_material_expressions(
            _const(_lo_edge, _px - 200, _py + 60), "", _sub_lo, "B")
        _div_lo = _node(_unreal.MaterialExpressionDivide, _px + 200, _py)
        _mel.connect_material_expressions(_sub_lo, "", _div_lo, "A")
        _mel.connect_material_expressions(
            _const(_f_lo, _px, _py + 120), "", _div_lo, "B")
        _sat_lo = _node(_unreal.MaterialExpressionSaturate, _px + 400, _py)
        _mel.connect_material_expressions(_div_lo, "", _sat_lo, "")

        _sub_hi = _node(_unreal.MaterialExpressionSubtract, _px, _py + 220)
        _mel.connect_material_expressions(
            _const(_hi_edge, _px - 200, _py + 280), "", _sub_hi, "A")
        _mel.connect_material_expressions(_value_node, "", _sub_hi, "B")
        _div_hi = _node(_unreal.MaterialExpressionDivide, _px + 200,
                        _py + 220)
        _mel.connect_material_expressions(_sub_hi, "", _div_hi, "A")
        _mel.connect_material_expressions(
            _const(_f_hi, _px, _py + 340), "", _div_hi, "B")
        _sat_hi = _node(_unreal.MaterialExpressionSaturate, _px + 400,
                        _py + 220)
        _mel.connect_material_expressions(_div_hi, "", _sat_hi, "")

        _mul = _node(_unreal.MaterialExpressionMultiply, _px + 600, _py + 110)
        _mel.connect_material_expressions(_sat_lo, "", _mul, "A")
        _mel.connect_material_expressions(_sat_hi, "", _mul, "B")
        return _mul

    # --- per-layer masks ---------------------------------------------
    # THE INSTRUMENT MUST MEASURE WHAT THE SHIPPING MATERIAL DECIDES.
    # When the recipe carries a baked weightmap, the shipping material
    # takes its masks from that texture and NOT from the vertex normal —
    # so a debug material still computing normal.z bands would visualise a
    # decision the shipping material no longer makes, and would do it
    # convincingly. The UV derivation is imported from
    # make_landscape_material.weightmap_uv_params so the two cannot drift.
    _masks = []
    if _weightmap:
        _wmt = _unreal.EditorAssetLibrary.load_asset(_weightmap)
        if _wmt is None:
            _out["error"] = "weightmap asset not found: " + str(_weightmap)
            raise RuntimeError(_out["error"])
        _wxy = _node(_unreal.MaterialExpressionWorldPosition, -1800, 700)
        _xym = _node(_unreal.MaterialExpressionComponentMask, -1600, 700)
        _xym.set_editor_property("r", True)
        _xym.set_editor_property("g", True)
        _xym.set_editor_property("b", False)
        _xym.set_editor_property("a", False)
        _mel.connect_material_expressions(_wxy, "", _xym, "")
        _org = _node(_unreal.MaterialExpressionConstant2Vector, -1800, 860)
        _org.set_editor_property("r", float(_org_x))
        _org.set_editor_property("g", float(_org_y))
        _rel = _node(_unreal.MaterialExpressionSubtract, -1400, 700)
        _mel.connect_material_expressions(_xym, "", _rel, "A")
        _mel.connect_material_expressions(_org, "", _rel, "B")
        _uvw = _node(_unreal.MaterialExpressionDivide, -1150, 700)
        _mel.connect_material_expressions(_rel, "", _uvw, "A")
        _mel.connect_material_expressions(
            _const(float(_span_cm), -1400, 830), "", _uvw, "B")
        _wsamp = _node(_unreal.MaterialExpressionTextureSample, -850, 700)
        _wsamp.set_editor_property("texture", _wmt)
        _wsamp.set_editor_property(
            "sampler_type", _unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        _wsamp.set_editor_property(
            "sampler_source",
            _unreal.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS)
        _mel.connect_material_expressions(_uvw, "", _wsamp, "UVs")
        _chan = ["R", "G", "B"]
        for _i, _L in enumerate(_layers):
            # A pass-through Multiply by 1: the compositor below needs an
            # expression node per layer, and a bare channel output cannot
            # be reused as one.
            _mk = _node(_unreal.MaterialExpressionMultiply, 1000, _i * 900)
            _mel.connect_material_expressions(
                _wsamp, _chan[_i % 3], _mk, "A")
            _mel.connect_material_expressions(
                _const(1.0, 800, _i * 900 + 120), "", _mk, "B")
            _masks.append(_mk)
            _out["layers"].append(
                {{"name": _L["name"], "colour": _L["colour"],
                  "channel": _chan[_i % 3]}})
    else:
        for _i, _L in enumerate(_layers):
            _py = _i * 900
            _slope_mask = _band(_nmask, _L["cos_lo"], _L["cos_hi"],
                                _L["slope_feather_lo"],
                                _L["slope_feather_hi"], 200, _py)
            _height_mask = _band(_zmask, _L["z_lo"], _L["z_hi"],
                                 _L["height_feather"], _L["height_feather"],
                                 200, _py + 450)
            _both = _node(_unreal.MaterialExpressionMultiply, 1000, _py + 220)
            _mel.connect_material_expressions(_slope_mask, "", _both, "A")
            _mel.connect_material_expressions(_height_mask, "", _both, "B")
            _masks.append(_both)
            _out["layers"].append(
                {{"name": _L["name"], "colour": _L["colour"],
                  "channel": None}})

    # --- composite last-to-first so layer 0 wins (first-match-wins) ---
    _acc = _const3(_unmatched, 1400, -400)
    for _i in range(len(_layers) - 1, -1, -1):
        _col = _const3(_layers[_i]["colour"], 1400, _i * 900 + 400)
        _lerp = _node(_unreal.MaterialExpressionLinearInterpolate,
                      1700 + (len(_layers) - _i) * 220, _i * 900)
        _mel.connect_material_expressions(_acc, "", _lerp, "A")
        _mel.connect_material_expressions(_col, "", _lerp, "B")
        _mel.connect_material_expressions(_masks[_i], "", _lerp, "Alpha")
        _acc = _lerp

    # UNLIT, and the readout goes to EMISSIVE.
    #
    # A lit debug material is not a measurement: sun angle, sky colour and
    # fog all tint the false colours, so a warm cast on one face is
    # ambiguous between "this layer is different here" and "this face is
    # lit differently". Unlit + emissive removes lighting from the readout
    # entirely, which is the whole point of a false-colour instrument.
    # (Height fog still applies to distant pixels; near ones are clean.)
    #
    # Reflected names verified against the RUNNING 5.8 editor, not assumed:
    # ObjectTools.list_properties on /Game/Debug/M_LayerDebug reports
    # `shadingModel` with enum EMaterialShadingModel including MSM_Unlit.
    # Failure to set it is RECORDED, not swallowed — reading a lit frame
    # as if it were unlit is exactly the wrong answer this exists to avoid.
    try:
        _mat.set_editor_property(
            "shading_model", _unreal.MaterialShadingModel.MSM_UNLIT)
        _out["unlit"] = True
    except Exception as _exc:
        _out["unlit"] = False
        _out["unlit_error"] = "%s: %s" % (type(_exc).__name__, _exc)

    # EMISSIVE MUST BE SCALED TO THE SCENE'S EXPOSURE OR THE READOUT IS
    # BLACK. Emissive is an absolute scene-luminance value, and this scene
    # is exposed for an 18000 lux sun. A false colour of 1.0 against that
    # exposure lands far below the floor and renders as black — visually
    # identical to "no layer matched", which would make the instrument
    # report a coverage gap that does not exist. The scale is taken from
    # the recipe's own sun intensity so it tracks whatever lighting the
    # recipe specifies rather than being a magic number.
    _emit = _node(_unreal.MaterialExpressionMultiply, 2600, -200)
    _mel.connect_material_expressions(_acc, "", _emit, "A")
    _mel.connect_material_expressions(
        _const(float(_emissive_scale), 2400, -100), "", _emit, "B")
    _out["emissive_scale"] = float(_emissive_scale)

    _mel.connect_material_property(
        _emit, "", _unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if not _out["unlit"]:
        # Could not go unlit, so the surface is still shaded — keep base
        # colour connected too rather than rendering a black landscape.
        _mel.connect_material_property(
            _acc, "", _unreal.MaterialProperty.MP_BASE_COLOR)
        _mel.connect_material_property(
            _const(1.0, 1400, -700), "",
            _unreal.MaterialProperty.MP_ROUGHNESS)

    _mel.layout_material_expressions(_mat)
    _errors = _mel.recompile_material(_mat)
    _out["compile_errors"] = [str(_e) for _e in (_errors or [])]
    # CHECKED SAVE -- see make_landscape_material for the defect.
    _ll_must.must_save(_asset_path, _unreal.EditorAssetLibrary)

    if _assign:
        _world = _unreal.get_editor_subsystem(
            _unreal.UnrealEditorSubsystem).get_editor_world()
        _hits = [_a for _a in
                 _unreal.GameplayStatics.get_all_actors_of_class(
                     _world, _unreal.Landscape)
                 if _a.get_actor_label() == _actor_name]
        _out["landscape_matches"] = len(_hits)
        if len(_hits) == 1:
            # Record what was assigned before, so it can be restored.
            _prev = _hits[0].get_editor_property("landscape_material")
            _out["previous_material"] = (
                _prev.get_path_name() if _prev is not None else None)
            # Routed through the BlueprintSetter EditorSetLandscapeMaterial
            # (LandscapeProxy.h:603), which fires PostEditChangeProperty;
            # the LandscapeOverridable shared-property sync copies it to
            # every loaded streaming proxy (Landscape.cpp:5148-5155).
            _hits[0].set_editor_property("landscape_material", _mat)
            _out["assigned"] = True

    _out["ok"] = not _out["compile_errors"]

print("{marker}" + _json.dumps(_out))
'''.format(asset=asset_path, layers=json.dumps(layers),
           unmatched=json.dumps(UNMATCHED_COLOUR), assign=bool(assign),
           actor=actor_name, marker=MARKER, weightmap=weightmap,
           org_x=float(org_x), org_y=float(org_y), span_cm=float(span_cm),
           emissive_scale=float(emissive_scale))


def _parse(text):
    idx = text.find(MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(MARKER):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  command did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(result))
    except Exception as exc:
        print("  command errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--emissive-scale", type=float, default=None,
                        help="Multiplier on the unlit false colours. "
                             "Defaults to the recipe's sun intensity_lux, "
                             "because emissive is an absolute luminance "
                             "and an unscaled 1.0 renders black against a "
                             "scene exposed for daylight.")
    parser.add_argument("--asset-path", default=DEFAULT_ASSET_PATH,
                        help="Debug material path. Must live under /Game/"
                             "Debug/ so it can never be confused with the "
                             "recipe's parent_material.")
    parser.add_argument("--assign", action="store_true",
                        help="Also assign the debug material to the "
                             "landscape so it can be captured.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    if (not args.asset_path.startswith("/Game/Debug/")
            or args.asset_path.endswith("/")
            or len(args.asset_path) <= len("/Game/Debug/")):
        print("REFUSE: --asset-path must be /Game/Debug/<AssetName>. This "
              "is a diagnostic instrument and must never be written where "
              "scene materials live.")
        return 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        print("REFUSE: recipe geometry is not buildable:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    # Full schema v1.1 material validation (shared with import_heightmap):
    # without it, out-of-range or non-finite layer values would flow
    # straight into shader constants.
    mat_errors = import_heightmap._validate_material(recipe.get("material"))
    if mat_errors:
        print("REFUSE: material block invalid (schema v1.1):")
        for e in mat_errors:
            print("  - {0}".format(e))
        return 2

    try:
        layers = _layer_thresholds(recipe)
    except (KeyError, TypeError, ValueError) as exc:
        print("REFUSE: cannot derive layer thresholds: {0}: {1}".format(
            type(exc).__name__, exc))
        return 2

    print("=" * 70)
    print("DIAGNOSTIC MATERIAL — NOT SCENE OUTPUT")
    print("=" * 70)
    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("Asset           : {0}".format(args.asset_path))
    print("Assign to actor : {0}".format(
        spec["actor_name"] if args.assign else "no (--assign not given)"))
    print("")
    print("Layer bands, as the shader will compare them:")
    for L in layers:
        print("  {0:<8} colour {1}".format(L["name"], L["colour"]))
        print("     slope {0}..{1} deg  ->  normal.z {2:.4f}..{3:.4f}"
              "  feather -{4:.4f}/+{5:.4f} outward".format(
                  recipe["material"]["layers"][L["index"]]["slope_deg"][0],
                  recipe["material"]["layers"][L["index"]]["slope_deg"][1],
                  L["cos_lo"], L["cos_hi"],
                  L["slope_feather_lo"], L["slope_feather_hi"]))
        print("     height {0}..{1} m   ->  world Z {2:.0f}..{3:.0f} cm"
              "  feather {4:.0f} cm outward".format(
                  recipe["material"]["layers"][L["index"]]["height_m"][0],
                  recipe["material"]["layers"][L["index"]]["height_m"][1],
                  L["z_lo"], L["z_hi"], L["height_feather"]))
    print("  unmatched colour {0}".format(UNMATCHED_COLOUR))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        # Same UV derivation the shipping material uses — imported, never
        # recomputed, so the instrument cannot start reading different
        # texels than the material it is diagnosing.
        # weightmap_uv_params also returns the VARIANT-MAP and MACRO-MAP
        # assets (schema v1.14). The debug material visualises neither, so
        # both are unpacked and ignored deliberately rather than dropped by
        # a short unpack that would break the moment the shared function
        # changed shape.
        (wm_asset, _wm_variant, _wm_macro, wm_ox, wm_oy,
         wm_span) = mlm.weightmap_uv_params(recipe)

        # Emissive scale. An unlit false colour is an ABSOLUTE luminance,
        # and this scene is exposed for its sun; at 1.0 the whole readout
        # renders black, which is indistinguishable from "no layer
        # matched" — the instrument would report a coverage gap that does
        # not exist. Default it from the recipe's own sun intensity so it
        # follows the lighting instead of being a magic number.
        emissive_scale = args.emissive_scale
        if emissive_scale is None:
            emissive_scale = float(
                (((recipe.get("lighting") or {}).get("sun") or {})
                 .get("intensity_lux")) or 1.0)
        if not (emissive_scale > 0.0):
            print("REFUSE: emissive scale must be positive; got "
                  "{0!r}".format(emissive_scale))
            return 2
        print("  mask source     : {0}".format(
            "baked weightmap {0}".format(wm_asset) if wm_asset
            else "vertex normal (recipe has no weightmap)"))
        print("")

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(args.asset_path, layers, args.assign,
                          spec["actor_name"], weightmap=wm_asset,
                          org_x=wm_ox, org_y=wm_oy, span_cm=wm_span,
                          emissive_scale=emissive_scale))
        if r is None:
            print("FAIL: the build payload returned nothing.")
            return 4
        if r.get("error"):
            print("FAIL: {0}".format(r["error"]))
            return 4

        print("--- result ---")
        print("  material {0}".format(
            "CREATED" if r.get("created") else "reused (find-or-create)"))
        for entry in r.get("layers") or []:
            print("    {0:<8} {1}".format(entry["name"], entry["colour"]))
        if r.get("compile_errors"):
            print("  COMPILE ERRORS:")
            for e in r["compile_errors"]:
                print("    {0}".format(e))
            return 4
        print("  compiled clean")
        # Surface the shading model (docstring: "that is reported"). The
        # payload records whether MSM_UNLIT took; if it did not, the frame is
        # LIT and its false colours are ambiguous between "different layer" and
        # "differently lit" -- the exact confusion this instrument exists to
        # avoid, so it must not go unstated.
        if r.get("unlit"):
            print("  shading model  : UNLIT (false colours read as authored)")
        else:
            print("")
            print("  WARNING: shading model could NOT be set to UNLIT ({0}); "
                  "base colour is connected as a fallback, so this frame is "
                  "LIT. Sun/sky/fog tint the readout — do NOT read coverage "
                  "from it.".format(r.get("unlit_error") or "no error recorded"))

        if args.assign:
            print("  landscape matches: {0}".format(
                r.get("landscape_matches")))
            if not r.get("assigned"):
                print("")
                print("FAIL: could not assign — need exactly one landscape "
                      "labelled {0!r}.".format(spec["actor_name"]))
                return 5
            print("  assigned to {0!r}".format(spec["actor_name"]))
            print("  previous landscape_material: {0}".format(
                r.get("previous_material")))
            print("")
            print("  NOTE: the assignment is IN-MEMORY ONLY. This script")
            print("  deliberately does not save the level, so the debug")
            print("  material will NOT survive an editor restart or level")
            print("  reload — restore by reassigning the previous material")
            print("  above, or by restarting without saving. Conversely, if")
            print("  the level IS saved for any other reason while this is")
            print("  assigned, the debug material persists into the map.")

        print("")
        print("=" * 70)
        print("REMINDER: this is a DIAGNOSTIC material. Captures from it")
        print("must carry a _debug suffix, and any changelog entry must be")
        print("marked DIAGNOSTIC. It is not the auto-material deliverable.")
        print("=" * 70)
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
