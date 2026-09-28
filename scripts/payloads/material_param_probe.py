import json as _json
import traceback as _tb
import unreal as _u

# What vector parameters do these engine materials ACTUALLY expose, and what
# is their blend mode / shading model?
#
# WHY: `MaterialInstanceDynamic.set_vector_parameter_value(name, v)` succeeds
# for ANY name, and `get_vector_parameter_value(name)` reads back what was
# just written -- from the MID's own override table, not from the material
# graph. So "set it and read it back" cannot distinguish a real parameter
# from a typo. Non-negotiable 0: the instrument shared its source with the
# claim. This asks the MATERIAL instead.

CANDIDATES = [
    "/Engine/EngineMaterials/EmissiveMeshMaterial",
    "/Engine/EngineDebugMaterials/DebugMeshMaterial",
    "/Engine/EngineDebugMaterials/LevelColorationUnlitMaterial",
    "/Engine/EngineDebugMaterials/BlackUnlitMaterial",
    "/Engine/EngineMaterials/WorldGridMaterial",
]

_out = {"ok": False, "error": None, "materials": []}
try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    for _p in CANDIDATES:
        _rec = {"path": _p, "exists": _eal.does_asset_exist(_p)}
        if not _rec["exists"]:
            _out["materials"].append(_rec)
            continue
        _m = _eal.load_asset(_p)
        _rec["class"] = _m.get_class().get_name() if _m else None
        for _fn, _key in (("get_vector_parameter_names", "vector_params"),
                          ("get_scalar_parameter_names", "scalar_params")):
            try:
                _rec[_key] = [str(_n) for _n in getattr(_mel, _fn)(_m)]
            except Exception as _e:
                _rec[_key] = "ERR: %s" % _e
        for _prop in ("blend_mode", "shading_model", "two_sided"):
            try:
                _rec[_prop] = str(_m.get_editor_property(_prop))
            except Exception as _e:
                _rec[_prop] = "ERR: %s" % _e
        _out["materials"].append(_rec)
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _out["traceback"] = _tb.format_exc()

print(_json.dumps(_out, indent=2))
