"""make_rvt_blend_material.py -- ground the meadow boulders with the landscape RVT.

    python scripts/make_rvt_blend_material.py [--recipe recipes/rvt_blend_boulders.json] [--dry-run]

Stage C of research/rvt_lookdev_design.md. In the editor, idempotent:
  1. duplicate source_material -> target_dir/target_material ONCE (no vendor
     byte written);
  2. inject ONCE (detected by the LL_RVTBlendCm parameter AND the Material
     Attributes output being our BlendMaterialAttributes): output =
     BlendMaterialAttributes(A = original attributes, B = Make(BaseColor,
     Roughness, Normal from the colour RVT; Normal transformed WORLD->TANGENT),
     Alpha = LL_RVTBlendStrength * saturate(1 - (WorldZ - RVT WorldHeight) /
     LL_RVTBlendCm)), pixel attributes blended, vertex attributes from A (the
     rock keeps its shape). Compile errors refuse; a failed injection is rolled
     back before anything is saved;
  3. child MIs per source instance carrying its scalar/vector/texture/static-
     switch values plus LL_RVT*; saved and re-read through the engine.
RVT asset paths are read from rvt_recipe (the ONE declaration, design change 4).
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

DEFAULT = os.path.join(bootstrap.REPO_ROOT, "recipes", "rvt_blend_boulders.json")
KEYS = {"schema_version", "rvt_recipe", "source_material", "source_instances", "target_dir",
        "target_material", "target_instance_names", "blend_cm", "strength"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate(r):
    e = ["unknown key %r" % k for k in r if not k.startswith("_") and k not in KEYS]
    e += ["missing key %r" % k for k in sorted(KEYS) if k not in r]
    if e:
        return e
    if r["schema_version"] != "rvt-blend-1.0":
        e.append("schema_version must be rvt-blend-1.0")
    if not str(r["target_dir"]).startswith("/Game/Materials/"):
        e.append("target_dir must be under /Game/Materials/ (tracked, never vendor)")
    if not re.fullmatch(r"[A-Za-z0-9_]+", str(r["target_material"])):
        e.append("target_material must match [A-Za-z0-9_]+")
    si, tn = r["source_instances"], r["target_instance_names"]
    if not (isinstance(si, list) and isinstance(tn, list) and si and len(si) == len(tn)):
        e.append("source_instances and target_instance_names must be equal-length lists")
    elif not all(re.fullmatch(r"[A-Za-z0-9_]+", str(x)) for x in tn):
        e.append("target_instance_names must match [A-Za-z0-9_]+")
    if not (_num(r["blend_cm"]) and 1.0 <= r["blend_cm"] <= 1000.0):
        e.append("blend_cm must be in [1, 1000]")
    if not (_num(r["strength"]) and 0.0 <= r["strength"] <= 1.0):
        e.append("strength must be in [0, 1]")
    try:
        rv = json.load(io.open(os.path.join(bootstrap.REPO_ROOT, r["rvt_recipe"]), encoding="utf-8"))
        types = [t["material_type"] for t in rv["textures"]]
        if "BASE_COLOR_NORMAL_ROUGHNESS" not in types or "WORLD_HEIGHT" not in types:
            e.append("rvt_recipe must declare a BASE_COLOR_NORMAL_ROUGHNESS and a WORLD_HEIGHT texture")
    except (OSError, ValueError, KeyError) as x:
        e.append("rvt_recipe unreadable: %s" % x)
    return e


def _cpu_alpha(world_z, rvt_h, blend_cm, strength):
    """CPU mirror of the injected Alpha."""
    return strength * min(1.0, max(0.0, 1.0 - (world_z - rvt_h) / blend_cm))


def _self_test():
    f = []
    if _cpu_alpha(100.0, 100.0, 25.0, 1.0) != 1.0:
        f.append("at ground level the rock must be fully ground-coloured")
    if _cpu_alpha(125.0, 100.0, 25.0, 1.0) != 0.0:
        f.append("blend_cm above ground the rock must be untouched")
    if _cpu_alpha(80.0, 100.0, 25.0, 1.0) != 1.0:
        f.append("below ground clamps to 1")
    if _cpu_alpha(100.0, 100.0, 25.0, 0.0) != 0.0:
        f.append("strength 0 must be the identity")
    return f


PAYLOAD = r'''
import json as _json
import os as _os
import sys as _sys
import unreal as _u
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ll_must as _ll_must
_R = _json.loads(__RECIPE__)
_out = dict(ok=False, injected=False, mis=[])
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _at = _u.AssetToolsHelpers.get_asset_tools()
    _rvt_c = _eal.load_asset(_R["rvt_color"])
    _rvt_h = _eal.load_asset(_R["rvt_height"])
    if _rvt_c is None or _rvt_h is None:
        raise RuntimeError("RVT assets missing: run make_rvt first")
    _tgt = _R["target_dir"] + "/" + _R["target_material"]
    if not _eal.does_asset_exist(_tgt):
        if _eal.duplicate_asset(_R["source_material"], _tgt) is None:
            raise RuntimeError("duplicate failed: " + _tgt)
        _out["duplicated"] = True
    _m = _eal.load_asset(_tgt)
    _MA = _u.MaterialProperty.MP_MATERIAL_ATTRIBUTES
    def _injected():
        _b = _mel.get_material_property_input_node(_m, _MA)
        return ("LL_RVTBlendCm" in [str(n) for n in _mel.get_scalar_parameter_names(_m)]
                and isinstance(_b, _u.MaterialExpressionBlendMaterialAttributes))
    # Substrate: a FrontMaterial-connected master would bypass the blend
    # silently (audit 2026-10-03, Material.cpp:3821-3833); the world->tangent
    # normal transform is only right for a tangent-space-normal master (Q3).
    if _mel.get_material_property_input_node(_m, _u.MaterialProperty.MP_FRONT_MATERIAL) is not None:
        raise RuntimeError("master has FrontMaterial connected: the blend would be bypassed")
    if not _m.get_editor_property("tangent_space_normal"):
        raise RuntimeError("master is not tangent-space-normal: world->tangent would be wrong")
    if not _injected():
        _a = _mel.get_material_property_input_node(_m, _MA)
        if _a is None:
            raise RuntimeError("copy has no Material Attributes input")
        _apin = str(_mel.get_material_property_input_node_output_name(_m, _MA))
        _made = []
        def _n(cls, x, y):
            _x = _mel.create_material_expression(_m, cls, x, y)
            _made.append(_x)
            return _x
        def _w(a, ap, b, bp):
            if not _mel.connect_material_expressions(a, ap, b, bp):
                raise RuntimeError("wire failed into " + type(b).__name__ + "." + bp)
        def _sp(name, v, x, y):
            _p = _n(_u.MaterialExpressionScalarParameter, x, y)
            _p.set_editor_property("parameter_name", name)
            _p.set_editor_property("default_value", float(v))
            return _p
        def _rvs(tex, x, y):
            _s = _n(_u.MaterialExpressionRuntimeVirtualTextureSample, x, y)
            _s.set_editor_property("virtual_texture", tex)
            _s.set_editor_property("material_type", tex.get_editor_property("material_type"))
            _s.set_editor_property("single_physical_space", tex.get_editor_property("single_physical_space"))
            _s.set_editor_property("adaptive", tex.get_editor_property("adaptive"))
            return _s
        try:
            _sc = _rvs(_rvt_c, -1600, 2000)
            _sh = _rvs(_rvt_h, -1600, 2400)
            _wp = _n(_u.MaterialExpressionWorldPosition, -1600, 2700)
            _wz = _n(_u.MaterialExpressionComponentMask, -1400, 2700)
            for _k, _v in (("r", False), ("g", False), ("b", True), ("a", False)):
                _wz.set_editor_property(_k, _v)
            _w(_wp, "", _wz, "")
            _dz = _n(_u.MaterialExpressionSubtract, -1200, 2600)
            _w(_wz, "", _dz, "A"); _w(_sh, "WorldHeight", _dz, "B")
            _bcm = _sp("LL_RVTBlendCm", _R["blend_cm"], -1200, 2800)
            _dv = _n(_u.MaterialExpressionDivide, -1000, 2600)
            _w(_dz, "", _dv, "A"); _w(_bcm, "", _dv, "B")
            _om = _n(_u.MaterialExpressionOneMinus, -850, 2600)
            _w(_dv, "", _om, "")
            _st = _n(_u.MaterialExpressionSaturate, -700, 2600)
            _w(_om, "", _st, "")
            _sg = _sp("LL_RVTBlendStrength", _R["strength"], -700, 2800)
            _al = _n(_u.MaterialExpressionMultiply, -550, 2600)
            _w(_st, "", _al, "A"); _w(_sg, "", _al, "B")
            _tn = _n(_u.MaterialExpressionTransform, -1300, 2200)
            _tn.set_editor_property("transform_source_type",
                                    _u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
            _tn.set_editor_property("transform_type",
                                    _u.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
            _w(_sc, "Normal", _tn, "")
            _mk = _n(_u.MaterialExpressionMakeMaterialAttributes, -900, 2100)
            _w(_sc, "BaseColor", _mk, "BaseColor")
            _w(_sc, "Roughness", _mk, "Roughness")
            _w(_tn, "", _mk, "Normal")
            _bl = _n(_u.MaterialExpressionBlendMaterialAttributes, -300, 1800)
            _bl.set_editor_property("pixel_attribute_blend_type", _u.MaterialAttributeBlend.BLEND)
            _bl.set_editor_property("vertex_attribute_blend_type", _u.MaterialAttributeBlend.USE_A)
            _w(_a, _apin, _bl, "A"); _w(_mk, "", _bl, "B"); _w(_al, "", _bl, "Alpha")
            if not _mel.connect_material_property(_bl, "", _MA):
                raise RuntimeError("Material Attributes reconnect failed")
            _errs = _mel.recompile_material(_m)
            if _errs:
                raise RuntimeError("compile errors: " + str([str(x) for x in _errs]))
        except Exception:
            for _x in _made:
                try:
                    _mel.delete_material_expression(_m, _x)
                except Exception:
                    pass
            _mel.connect_material_property(_a, _apin, _MA)
            raise
        if not _injected():
            raise RuntimeError("injection read-back failed")
        _ll_must.must_save(_tgt, _eal)
        _out["injected"] = True
    _out["injection_readback"] = bool(_injected())
    _want = dict(LL_RVTBlendCm=float(_R["blend_cm"]), LL_RVTBlendStrength=float(_R["strength"]))
    for _src, _nm in zip(_R["source_instances"], _R["target_instance_names"]):
        _s = _eal.load_asset(_src)
        if _s is None:
            raise RuntimeError("source instance missing: " + _src)
        _sbm = _s.get_base_material()
        if _sbm is None or _sbm.get_path_name().split(".")[0] != _R["source_material"]:
            raise RuntimeError("source instance " + _src + " does not derive from source_material")
        _path = _R["target_dir"] + "/" + _nm
        if _eal.does_asset_exist(_path):
            _mi = _eal.load_asset(_path)
        else:
            _mi = _at.create_asset(_nm, _R["target_dir"], _u.MaterialInstanceConstant,
                                   _u.MaterialInstanceConstantFactoryNew())
        _mel.set_material_instance_parent(_mi, _m)
        for _pn in _mel.get_scalar_parameter_names(_s):
            _mel.set_material_instance_scalar_parameter_value(
                _mi, _pn, _mel.get_material_instance_scalar_parameter_value(_s, _pn))
        for _pn in _mel.get_vector_parameter_names(_s):
            _mel.set_material_instance_vector_parameter_value(
                _mi, _pn, _mel.get_material_instance_vector_parameter_value(_s, _pn))
        for _pn in _mel.get_texture_parameter_names(_s):
            _mel.set_material_instance_texture_parameter_value(
                _mi, _pn, _mel.get_material_instance_texture_parameter_value(_s, _pn))
        for _pn in _mel.get_static_switch_parameter_names(_s):
            _mel.set_material_instance_static_switch_parameter_value(
                _mi, _pn, _mel.get_material_instance_static_switch_parameter_value(_s, _pn))
        for _k, _v in _want.items():
            _mel.set_material_instance_scalar_parameter_value(_mi, _k, _v)
        _mel.update_material_instance(_mi)
        _ll_must.must_save(_path, _eal)
        _c = _eal.load_asset(_path)
        _rb = dict((_k, _mel.get_material_instance_scalar_parameter_value(_c, _k)) for _k in _want)
        _ok = (all(abs(_rb[_k] - _want[_k]) < 1e-5 for _k in _want)
               and _c.get_editor_property("parent").get_path_name().split(".")[0] == _tgt)
        _out["mis"].append(dict(path=_path, readback=_rb, ok=bool(_ok)))
    _out["ok"] = all(x["ok"] for x in _out["mis"]) and _out["injection_readback"]
except Exception:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=180.0)
    a = ap.parse_args(argv)
    f = _self_test()
    if f:
        print("SELF-TEST FAILED: " + "; ".join(f))
        return 3
    r = json.load(io.open(a.recipe, encoding="utf-8"))
    errs = validate(r)
    if errs:
        print("REFUSE:\n  " + "\n  ".join(errs))
        return 2
    rv = json.load(io.open(os.path.join(bootstrap.REPO_ROOT, r["rvt_recipe"]), encoding="utf-8"))
    by_type = dict((t["material_type"], rv["asset_dir"] + "/" + t["name"]) for t in rv["textures"])
    clean = dict((k, v) for k, v in r.items() if not k.startswith("_"))
    clean["rvt_color"] = by_type["BASE_COLOR_NORMAL_ROUGHNESS"]
    clean["rvt_height"] = by_type["WORLD_HEIGHT"]
    src = PAYLOAD.replace("__RECIPE__", repr(json.dumps(clean)))
    if a.dry_run:
        print("dry run: recipe valid; RVTs %s / %s; payload %d bytes"
              % (clean["rvt_color"], clean["rvt_height"], len(src)))
        return 0
    import ue_exec
    out_dir = os.path.join(bootstrap.REPO_ROOT, "_verify", "rvt")
    os.makedirs(out_dir, exist_ok=True)
    io.open(os.path.join(out_dir, "rvt_blend_payload.txt"), "w", encoding="utf-8").write(src)
    code, out, raw = ue_exec.run(src, marker="__LL__", timeout=a.timeout, stage_name="rvt_blend")
    if not isinstance(out, dict):
        print("FAIL (code %s): COULD NOT LOOK\n%s" % (code, (raw or "")[-1500:]))
        return 4
    io.open(os.path.join(out_dir, "rvt_blend_result.json"), "w", encoding="utf-8").write(
        json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
