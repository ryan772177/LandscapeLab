"""Read the stochastic-tiling binding back out of the built graph.

Standing rule 12: declared, applied AND read back from the engine, or
the field is a comment. This reads what the GRAPH holds -- which
TextureSamples are in derivative mip mode, what feeds their UVs, and the
TextureVariation call's scalar inputs -- rather than what the recipe
asked for.

⛔ IT MUST ALSO SHOW WHAT IS *NOT* STOCHASTIC. A pass that only confirms
the intended layer says nothing about whether the shifted UVs leaked
into a neighbour, and leaking is the specific hazard of routing samples
through a slot that the band loop sets and clears. So every sample in
the material is listed with its UV source.
"""
import json as _json
import traceback as _tb

import unreal as _u

MAT = "/Game/Materials/M_Alpine8K"
_out = {"ok": False, "material": MAT}


def _key(_e):
    try:
        return _e.get_path_name()
    except Exception:
        return str(_e)


try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _mat = _eal.load_asset(MAT)
    # load_asset returns None for a missing/renamed asset; get_material_
    # expressions(None) would then yield [] and the probe would report ok:true
    # over a material that does not exist. Refuse.
    if _mat is None:
        raise RuntimeError("material not found: " + MAT)
    _all = list(_mel.get_material_expressions(_mat))
    _inputs, _bykey = {}, {}
    for _e in _all:
        _bykey[_key(_e)] = _e
        try:
            _inputs[_key(_e)] = [i for i in
                                 (_mel.get_inputs_for_material_expression(
                                     _mat, _e) or []) if i is not None]
        except Exception:
            _inputs[_key(_e)] = []

    def _upstream(_start, _want, _max_depth=4):
        """First upstream expression of class `_want`, with its depth."""
        _stack = [(_key(_start), 0)]
        _seen = set()
        while _stack:
            _k, _d = _stack.pop(0)
            if _k in _seen or _d > _max_depth:
                continue
            _seen.add(_k)
            _e = _bykey.get(_k)
            if _e is None:
                continue
            if _d and isinstance(_e, _want):
                return _e, _d
            for _i in _inputs.get(_k, []):
                _stack.append((_key(_i), _d + 1))
        return None, None

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
        _call, _cd = _upstream(_e, _u.MaterialExpressionMaterialFunctionCall)
        _fn = None
        if _call is not None:
            try:
                _mf = _call.get_editor_property("material_function")
                _fn = _mf.get_name() if _mf else None
            except Exception:
                _fn = "UNREADABLE"
        _rows.append({
            "texture": _t.get_name(),
            "mip_value_mode": str(_e.get_editor_property("mip_value_mode")),
            "uv_via_function": _fn,
            "function_depth": _cd,
        })
    _rows.sort(key=lambda r: r["texture"])
    _out["samples"] = _rows
    _out["n_samples"] = len(_rows)
    _out["stochastic_textures"] = sorted(
        r["texture"] for r in _rows if r["uv_via_function"])
    _out["derivative_textures"] = sorted(
        r["texture"] for r in _rows if "DERIVATIVE" in r["mip_value_mode"])

    # The TextureVariation call's own scalar inputs, read from the graph.
    _calls = []
    for _e in _all:
        if not isinstance(_e, _u.MaterialExpressionMaterialFunctionCall):
            continue
        try:
            _mf = _e.get_editor_property("material_function")
            _nm = _mf.get_name() if _mf else None
        except Exception:
            _nm = "UNREADABLE"
        _consts = []
        for _i in _inputs.get(_key(_e), []):
            _cn = type(_i).__name__
            if "Constant" in _cn and "Vector" not in _cn:
                try:
                    _consts.append(round(float(
                        _i.get_editor_property("r")), 6))
                except Exception:
                    _consts.append("UNREADABLE")   # don't undercount silently
            elif "StaticBool" in _cn:
                try:
                    _consts.append(bool(_i.get_editor_property("value")))
                except Exception:
                    _consts.append("UNREADABLE")
        _calls.append({"function": _nm, "scalar_inputs": sorted(
            (str(c) for c in _consts))})
    _out["function_calls"] = _calls
    # NN13: the probe reads per-TextureSample stochastic binding; zero samples
    # (or no expressions) read nothing worth reporting. Refuse.
    _out["ok"] = _out["n_samples"] > 0
    if not _out["ok"]:
        _out["refused"] = ("expressions=%d, texture_samples=0 -- nothing read "
                           "to report" % len(_all))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
