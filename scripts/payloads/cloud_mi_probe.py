"""READ-ONLY probe of the engine's simple volumetric cloud MI (Task 6).

The brief says "coverage parameter low (0.3) if the MI exposes one". Per
ue-api-resolution, the reflected surface of the RUNNING editor decides
what exists — this enumerates the MI's parameters rather than guessing a
name. Loads the asset (a read), mutates nothing, saves nothing.

NOTE (standing rule 1): if a coverage-like scalar exists it must NOT be
set on the ENGINE MI (that dirties engine content outside both roots); a
child instance in /Game would carry the override. This probe only
answers whether one exists and what it is called.
"""
import json as _json
import traceback as _tb

import unreal as _u

_MI = "/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst"

_out = {"ok": False, "mi": _MI}
try:
    _mi = _u.EditorAssetLibrary.load_asset(_MI)
    if _mi is None:
        raise RuntimeError("load_asset returned None for " + _MI)
    _out["class"] = type(_mi).__name__

    try:
        _parent = _mi.get_editor_property("parent")
        _out["parent"] = _parent.get_path_name() if _parent else None
    except Exception as _e:
        _out["parent_error"] = str(_e)[:200]
        _parent = None

    # Overridden parameters ON the instance
    for _prop, _key in (("scalar_parameter_values", "mi_scalar_overrides"),
                        ("vector_parameter_values", "mi_vector_overrides")):
        try:
            _vals = _mi.get_editor_property(_prop)
            _rows = []
            for _v in _vals:
                try:
                    _info = _v.get_editor_property("parameter_info")
                    _name = str(_info.get_editor_property("name"))
                except Exception:
                    _name = "<unreadable>"
                try:
                    _pv = _v.get_editor_property("parameter_value")
                    _pv = (float(_pv) if isinstance(_pv, (int, float))
                           else str(_pv))
                except Exception:
                    _pv = "<unreadable>"
                _rows.append([_name, _pv])
            _out[_key] = _rows
        except Exception as _e:
            _out[_key + "_error"] = str(_e)[:200]

    # ALL parameters visible on the parent material, via MEL
    if _parent is not None:
        try:
            _out["parent_scalar_params"] = [
                str(n) for n in
                _u.MaterialEditingLibrary.get_scalar_parameter_names(_parent)]
        except Exception as _e:
            _out["parent_scalar_error"] = str(_e)[:200]
        try:
            _out["parent_vector_params"] = [
                str(n) for n in
                _u.MaterialEditingLibrary.get_vector_parameter_names(_parent)]
        except Exception as _e:
            _out["parent_vector_error"] = str(_e)[:200]

    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-600:]

print("__LL__" + _json.dumps(_out))
