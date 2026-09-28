"""Read the Task 4 grass-card chain back out of the BUILT material.

Standing rule 12: declared, applied AND read back from the engine. This
payload is the READ-BACK leg only -- it does not declare or apply; it
reports what a separate builder actually produced.

Reports the node classes present and every scalar amplitude in the graph
-- both Constant nodes (property `r`) and ScalarParameter defaults -- so
the recipe's amplitudes can be matched against what the shader will
actually use, not against what the builder was asked for.
"""
import json as _json
import traceback as _tb

import unreal as _u

MAT = "/Game/Meshes/Materials/M_grass_medium_01"
_out = {"ok": False, "material": MAT}
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _mat = _eal.load_asset(MAT)
    # F2: load_asset returns None for a missing asset; get_material_expressions
    # would then yield [] and the whole probe would report ok:true over a
    # material that does not exist. Refuse instead.
    if _mat is None:
        raise RuntimeError("material not found: " + MAT)
    _all = list(_mel.get_material_expressions(_mat))
    _classes = {}
    _consts = []
    _params = []
    _funcs = []
    _texs = []
    for _e in _all:
        _cn = type(_e).__name__.replace("MaterialExpression", "")
        _classes[_cn] = _classes.get(_cn, 0) + 1
        if _cn == "Constant":
            _consts.append(round(float(_e.get_editor_property("r")), 6))
        elif _cn == "MaterialFunctionCall":
            try:
                _f = _e.get_editor_property("material_function")
                _funcs.append(_f.get_name() if _f else None)
            except Exception:
                _funcs.append("UNREADABLE")
        elif _cn == "TextureSample":
            try:
                _t = _e.get_editor_property("texture")
                _texs.append(_t.get_name() if _t else None)
            except Exception:
                # F4: match the func path's sentinel -- a swallowed read here
                # silently undercounts textures_sampled while ok stays true.
                _texs.append("UNREADABLE")
        elif _cn == "ScalarParameter":
            # F6: amplitudes may be parameters, not Constant nodes.
            try:
                _params.append({
                    "name": str(_e.get_editor_property("parameter_name")),
                    "default": round(float(
                        _e.get_editor_property("default_value")), 6)})
            except Exception:
                _params.append({"name": "UNREADABLE", "default": None})
    _out["expressions"] = len(_all)
    _out["class_counts"] = _classes
    _out["constants"] = sorted(_consts)
    _out["scalar_parameters"] = sorted(_params, key=lambda p: str(p["name"]))
    # F3: _funcs/_texs may hold None alongside strings; sorted() on that raises
    # TypeError in Py3 and would discard the whole read via the outer except.
    _out["function_calls"] = sorted(_funcs, key=lambda x: (x is None, x))
    _out["textures_sampled"] = sorted(_texs, key=lambda x: (x is None, x))
    _out["has_per_instance_random"] = "PerInstanceRandom" in _classes
    _out["has_object_position"] = "ObjectPositionWS" in _classes
    _out["has_texture_coordinate"] = "TextureCoordinate" in _classes
    _out["base_color_input"] = None
    try:
        _node = _mel.get_material_property_input_node(
            _mat, _u.MaterialProperty.MP_BASE_COLOR)
        _out["base_color_input"] = type(_node).__name__ if _node else None
    except Exception as _e:
        _out["base_color_input"] = "UNREADABLE: %s" % type(_e).__name__
    _out["two_sided"] = bool(_mat.get_editor_property("two_sided"))
    _out["blend_mode"] = str(_mat.get_editor_property("blend_mode"))
    # F1/NN13 + F5: a read that found no expressions, or could not read the
    # base-color input (the core grass-card chain), has read nothing worth
    # trusting -- do not report success over it.
    _bc = _out["base_color_input"]
    _base_ok = _bc is not None and not str(_bc).startswith("UNREADABLE")
    _out["ok"] = (len(_all) > 0) and _base_ok
    if not _out["ok"]:
        _out["refused"] = ("expressions=%d, base_color_input=%r -- nothing "
                           "readable to report" % (len(_all), _bc))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]
print("__LL__" + _json.dumps(_out))
