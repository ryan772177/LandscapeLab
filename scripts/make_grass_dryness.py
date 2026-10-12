"""make_grass_dryness.py -- world-space dry/green patches on the FieldGrass meadow.

    python scripts/make_grass_dryness.py [--recipe recipes/grass_dryness.json] [--dry-run]

WHY. The vendor FieldGrass "dead colour" mask is per-blade (positive control,
LESSONS 2026-10-03o), so landscape-scale dry patches need a material we own.

WHAT, in the editor, idempotent:
  1. duplicate source_material -> target_dir/target_material, ONCE (no vendor
     byte is written; the copy keeps wind, subsurface and opacity);
  2. inject, ONCE (detected by the LL_DryStrength parameter): BaseColor =
     original BaseColor input * lerp(1, LL_DryTint, dryness), where
     dryness = LL_DryStrength * saturate((noise - LL_DryLo) / LL_DryWidth) and
     noise = Noise(AbsoluteWorldPosition * LL_DryInvScale), Gradient-ALU,
     output 0..1, levels from the recipe (a node property, fixed at injection);
  3. find-or-create one child MI per source instance, parented to the copy,
     carrying the source instance's own parameter values plus the recipe's
     LL_Dry* values; save; READ BACK every LL_Dry* value from the reloaded MI.
The grass types point at the MIs through variety override_materials in the
landscape recipe (read back by make_landscape_material).
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

MARKER = "__LL_DRY__"
DEFAULT = os.path.join(bootstrap.REPO_ROOT, "recipes", "grass_dryness.json")
KEYS = {"schema_version", "source_material", "source_instances", "target_dir",
        "target_material", "target_instance_prefix", "noise_scale_m",
        "noise_levels", "threshold", "dry_tint", "strength"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate(r):
    e = [k for k in r if not k.startswith("_") and k not in KEYS]
    e = ["unknown key %r" % k for k in e]
    e += ["missing key %r" % k for k in sorted(KEYS) if k not in r]
    if e:
        return e
    if r["schema_version"] != "grass-dryness-1.0":
        e.append("schema_version must be grass-dryness-1.0")
    for k in ("source_material", "target_dir"):
        if not str(r[k]).startswith("/Game/"):
            e.append("%s must be a /Game/ path" % k)
    if not str(r["target_dir"]).startswith("/Game/Materials/"):
        e.append("target_dir must be under /Game/Materials/ (tracked, never vendor)")
    si = r["source_instances"]
    if not (isinstance(si, list) and si and all(str(x).startswith("/Game/") for x in si)):
        e.append("source_instances must be a non-empty list of /Game/ paths")
    if not (_num(r["noise_scale_m"]) and 1.0 <= r["noise_scale_m"] <= 5000.0):
        e.append("noise_scale_m must be in [1, 5000]")
    import re
    for k in ("target_material", "target_instance_prefix"):
        if not (isinstance(r[k], str) and re.fullmatch(r"[A-Za-z0-9_]+", r[k])):
            e.append("%s must match [A-Za-z0-9_]+ (no path separators)" % k)
    if not (isinstance(r["noise_levels"], int) and not isinstance(r["noise_levels"], bool)
            and 1 <= r["noise_levels"] <= 6):
        e.append("noise_levels must be an int in [1, 6]")
    t = r["threshold"]
    if not (isinstance(t, list) and len(t) == 2 and all(_num(x) for x in t)
            and 0.0 <= t[0] < t[1] <= 1.0):
        e.append("threshold must be [lo, hi], 0 <= lo < hi <= 1 (lo == hi is a hard edge)")
    d = r["dry_tint"]
    if not (isinstance(d, list) and len(d) == 3 and all(_num(x) and 0.0 < x <= 4.0 for x in d)):
        e.append("dry_tint must be [r, g, b] multipliers in (0, 4]")
    if not (_num(r["strength"]) and 0.0 <= r["strength"] <= 1.0):
        e.append("strength must be in [0, 1]")
    return e


def _cpu_dryness(noise, lo, hi, strength):
    """CPU mirror of the injected term (one channel of the tint lerp weight)."""
    return strength * min(1.0, max(0.0, (noise - lo) / (hi - lo)))


def _self_test():
    f = []
    if _cpu_dryness(0.0, 0.45, 0.7, 1.0) != 0.0:
        f.append("noise 0 must be fully green")
    if _cpu_dryness(1.0, 0.45, 0.7, 1.0) != 1.0:
        f.append("noise 1 must be fully dry")
    if abs(_cpu_dryness(0.575, 0.45, 0.7, 1.0) - 0.5) > 1e-12:
        f.append("threshold midpoint must be 0.5")
    if _cpu_dryness(1.0, 0.45, 0.7, 0.0) != 0.0:
        f.append("strength 0 must be the identity")
    return f


PAYLOAD = r'''
import json as _json
import unreal as _u
_R = _json.loads(__RECIPE__)
_out = dict(ok=False, injected=False, mis=[])
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _at = _u.AssetToolsHelpers.get_asset_tools()
    _tgt = _R["target_dir"] + "/" + _R["target_material"]
    if not _eal.does_asset_exist(_tgt):
        if _eal.duplicate_asset(_R["source_material"], _tgt) is None:
            raise RuntimeError("duplicate failed: " + _tgt)
        _out["duplicated"] = True
    _m = _eal.load_asset(_tgt)
    _inv0 = 1.0 / (float(_R["noise_scale_m"]) * 100.0)
    _lo0 = float(_R["threshold"][0])
    _wd0 = float(_R["threshold"][1]) - _lo0
    _sg0 = float(_R["strength"])
    _t0 = [float(x) for x in _R["dry_tint"]]
    def _injected():
        # Marker param AND BaseColor fed by a Multiply: the marker alone made
        # a half-built graph look finished (audit 2026-10-03).
        _b = _mel.get_material_property_input_node(_m, _u.MaterialProperty.MP_BASE_COLOR)
        return ("LL_DryStrength" in [str(n) for n in _mel.get_scalar_parameter_names(_m)]
                and isinstance(_b, _u.MaterialExpressionMultiply))
    if not _injected():
        _bc = _mel.get_material_property_input_node(_m, _u.MaterialProperty.MP_BASE_COLOR)
        if _bc is None:
            raise RuntimeError("copy has no BaseColor input")
        _bcpin = str(_mel.get_material_property_input_node_output_name(
            _m, _u.MaterialProperty.MP_BASE_COLOR))
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
        try:
            _wp = _n(_u.MaterialExpressionWorldPosition, -2200, 1200)
            _inv = _sp("LL_DryInvScale", _inv0, -2200, 1350)
            _mp = _n(_u.MaterialExpressionMultiply, -2000, 1250)
            _w(_wp, "", _mp, "A"); _w(_inv, "", _mp, "B")
            _nz = _n(_u.MaterialExpressionNoise, -1800, 1250)
            _nz.set_editor_property("scale", 1.0)
            _nz.set_editor_property("levels", int(_R["noise_levels"]))
            _nz.set_editor_property("output_min", 0.0)
            _nz.set_editor_property("output_max", 1.0)
            # Resolve the enum member by reflection: the Python spelling of
            # NOISEFUNCTION_GradientALU is not guessed (ue58-api-protocol).
            _cands = [n for n in dir(_u.NoiseFunction) if "GRADIENT" in n and "ALU" in n]
            if len(_cands) != 1:
                raise RuntimeError("NoiseFunction GradientALU not unique: " + str(
                    [n for n in dir(_u.NoiseFunction) if n.startswith("NOISE")]))
            _nz.set_editor_property("noise_function", getattr(_u.NoiseFunction, _cands[0]))
            _out["noise_function"] = _cands[0]
            # GetWorldPositionInputName(Absolute) = "World Position", NOT
            # "Position" (audit 2026-10-03, MaterialShared.cpp:6310).
            _w(_mp, "", _nz, "World Position")
            _lo = _sp("LL_DryLo", _lo0, -1600, 1400)
            _wd = _sp("LL_DryWidth", _wd0, -1600, 1500)
            _sb = _n(_u.MaterialExpressionSubtract, -1400, 1250)
            _w(_nz, "", _sb, "A"); _w(_lo, "", _sb, "B")
            _dv = _n(_u.MaterialExpressionDivide, -1250, 1250)
            _w(_sb, "", _dv, "A"); _w(_wd, "", _dv, "B")
            _st = _n(_u.MaterialExpressionSaturate, -1100, 1250)
            _w(_dv, "", _st, "")
            _sg = _sp("LL_DryStrength", _sg0, -1100, 1400)
            _ms = _n(_u.MaterialExpressionMultiply, -950, 1250)
            _w(_st, "", _ms, "A"); _w(_sg, "", _ms, "B")
            _one = _n(_u.MaterialExpressionConstant3Vector, -950, 1100)
            _one.set_editor_property("constant", _u.LinearColor(1.0, 1.0, 1.0, 1.0))
            _tv = _n(_u.MaterialExpressionVectorParameter, -950, 1450)
            _tv.set_editor_property("parameter_name", "LL_DryTint")
            _tv.set_editor_property("default_value", _u.LinearColor(_t0[0], _t0[1], _t0[2], 1.0))
            _lp = _n(_u.MaterialExpressionLinearInterpolate, -750, 1250)
            _w(_one, "", _lp, "A"); _w(_tv, "", _lp, "B"); _w(_ms, "", _lp, "Alpha")
            _fin = _n(_u.MaterialExpressionMultiply, -550, 1000)
            _w(_bc, _bcpin, _fin, "A"); _w(_lp, "", _fin, "B")
            if not _mel.connect_material_property(_fin, "", _u.MaterialProperty.MP_BASE_COLOR):
                raise RuntimeError("BaseColor reconnect failed")
            _errs = _mel.recompile_material(_m)
            if _errs:
                raise RuntimeError("compile errors: " + str([str(x) for x in _errs]))
        except Exception:
            # Roll the half-built graph back so a rerun starts clean; nothing saved.
            for _x in _made:
                try:
                    _mel.delete_material_expression(_m, _x)
                except Exception:
                    pass
            _mel.connect_material_property(_bc, _bcpin, _u.MaterialProperty.MP_BASE_COLOR)
            raise
        if not _injected():
          raise RuntimeError("injection read-back failed: BaseColor is not our Multiply")
        _eal.save_asset(_tgt, only_if_is_dirty=False)
        _out["injected"] = True
    _out["injection_readback"] = bool(_injected())
    _m = _eal.load_asset(_tgt)
    _out["material_params"] = sorted(str(n) for n in _mel.get_scalar_parameter_names(_m)
                                     if str(n).startswith("LL_"))
    _want = dict(LL_DryInvScale=1.0 / (float(_R["noise_scale_m"]) * 100.0),
                 LL_DryLo=float(_R["threshold"][0]),
                 LL_DryWidth=float(_R["threshold"][1]) - float(_R["threshold"][0]),
                 LL_DryStrength=float(_R["strength"]))
    _tint = [float(x) for x in _R["dry_tint"]]
    for _i, _src in enumerate(_R["source_instances"]):
        _path = _R["target_dir"] + "/" + _R["target_instance_prefix"] + str(_i)
        _s = _eal.load_asset(_src)
        if _s is None:
            raise RuntimeError("source instance missing: " + _src)
        if _eal.does_asset_exist(_path):
            _mi = _eal.load_asset(_path)
        else:
            _mi = _at.create_asset(_path.rsplit("/", 1)[1], _R["target_dir"],
                                   _u.MaterialInstanceConstant,
                                   _u.MaterialInstanceConstantFactoryNew())
        _sbm = _s.get_base_material() if hasattr(_s, "get_base_material") else None
        if _sbm is None or _sbm.get_path_name().split(".")[0] != _R["source_material"]:
            raise RuntimeError("source instance " + _src + " does not derive from source_material")
        _mel.set_material_instance_parent(_mi, _m)
        for _pn in _mel.get_static_switch_parameter_names(_s):
            _mel.set_material_instance_static_switch_parameter_value(
                _mi, _pn, _mel.get_material_instance_static_switch_parameter_value(_s, _pn))
        for _pn in _mel.get_scalar_parameter_names(_s):
            _mel.set_material_instance_scalar_parameter_value(
                _mi, _pn, _mel.get_material_instance_scalar_parameter_value(_s, _pn))
        for _pn in _mel.get_vector_parameter_names(_s):
            _mel.set_material_instance_vector_parameter_value(
                _mi, _pn, _mel.get_material_instance_vector_parameter_value(_s, _pn))
        for _pn in _mel.get_texture_parameter_names(_s):
            _mel.set_material_instance_texture_parameter_value(
                _mi, _pn, _mel.get_material_instance_texture_parameter_value(_s, _pn))
        for _k, _v in _want.items():
            _mel.set_material_instance_scalar_parameter_value(_mi, _k, _v)
        _mel.set_material_instance_vector_parameter_value(
            _mi, "LL_DryTint", _u.LinearColor(_tint[0], _tint[1], _tint[2], 1.0))
        _mel.update_material_instance(_mi)
        _eal.save_asset(_path, only_if_is_dirty=False)
        _c = _eal.load_asset(_path)
        _rb = dict((_k, _mel.get_material_instance_scalar_parameter_value(_c, _k)) for _k in _want)
        _tc = _mel.get_material_instance_vector_parameter_value(_c, "LL_DryTint")
        _rb["LL_DryTint"] = [_tc.r, _tc.g, _tc.b]
        _ok = all(abs(_rb[_k] - _want[_k]) <= 1e-6 * max(1.0, abs(_want[_k])) for _k in _want) \
            and all(abs(a - b) <= 1e-5 for a, b in zip(_rb["LL_DryTint"], _tint)) \
            and _c.get_editor_property("parent").get_path_name().split(".")[0] == _tgt
        _out["mis"].append(dict(path=_path, readback=_rb, ok=bool(_ok)))
    _out["ok"] = (all(x["ok"] for x in _out["mis"]) and len(_out["material_params"]) >= 4
                  and _out["injection_readback"])
except Exception as _e:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=25.0)
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
    clean = dict((k, v) for k, v in r.items() if not k.startswith("_"))
    src = PAYLOAD.replace("__RECIPE__", repr(json.dumps(clean)))
    if a.dry_run:
        print("dry run: recipe valid; payload %d bytes" % len(src))
        return 0
    # ue_exec.run: project-match gate (rule 7), staging, marker parse. The
    # resolved payload is also written under _verify so the run is reproducible.
    import ue_exec
    out_dir = os.path.join(bootstrap.REPO_ROOT, "_verify", "grass_dryness")
    os.makedirs(out_dir, exist_ok=True)
    io.open(os.path.join(out_dir, "payload.txt"), "w", encoding="utf-8").write(src)
    _code, out, raw = ue_exec.run(src, marker="__LL__", timeout=a.timeout,
                                  stage_name="grass_dryness")
    if not isinstance(out, dict):
        print("FAIL (code %s): payload returned nothing -- COULD NOT LOOK\n%s"
              % (_code, (raw or "")[-1500:]))
        return 4
    io.open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8").write(
        json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
