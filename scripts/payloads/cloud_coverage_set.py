"""cloud_coverage_set.py -- set Cloud_GlobalCoverage on the child MI, read back (B-4).

Sets the named scalar on /Game/Bench/MI_AlpineClouds (the CHILD instance
the recipe uses -- never the engine MI, standing rule 1) and READS IT
BACK off the asset (rule 12). Saves the MI so MRQ, which renders the
editor world, sees the value. The caller restores 0.3 afterwards.

CONFIG_JSON substitution literal is {"value": <float>}. Prints one __LL__
JSON line with before/after read-backs and the save verdict.
"""
import json

import unreal as _u

_CFG = json.loads(r'''__CONFIG_JSON__''')
_MI = "/Game/Bench/MI_AlpineClouds"
_PARAM = "Cloud_GlobalCoverage"

_out = {"ok": False, "error": None, "mi": _MI, "param": _PARAM}
try:
    _want = float(_CFG["value"])
    _out["requested"] = _want
    _mi = _u.EditorAssetLibrary.load_asset(_MI)
    if _mi is None:
        raise RuntimeError("load_asset returned None for " + _MI)
    _out["class"] = type(_mi).__name__
    _out["before"] = float(
        _u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            _mi, _PARAM))
    _u.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        _mi, _PARAM, _want)
    _after = float(
        _u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            _mi, _PARAM))
    _out["after"] = _after
    _out["matches_request"] = abs(_after - _want) < 1e-6
    _saved = _u.EditorAssetLibrary.save_asset(_MI, only_if_is_dirty=False)
    _out["saved"] = bool(_saved)
    _out["ok"] = _out["matches_request"] and _out["saved"]
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
