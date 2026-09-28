"""T0 read-only probe: establish the 5.8 water surface LIVE (no mutation).

Resolves the stub-vs-uproject contradiction (the PythonStub carries Water*
classes but LandscapeLab.uproject does not enable the Water plugin) and
confirms the static-water-mesh path's assets load and are suitable, so T2
records a PROVEN material/mesh rather than a quoted one.
"""
import json as _json
import unreal as _u

_out = {"ok": False, "error": None}
try:
    # (1) Is the Water plugin actually usable at runtime in THIS build?
    _wb = {}
    for _cn in ("WaterBody", "WaterBodyLake", "WaterBodyRiver", "WaterZone",
                "WaterBrushManager"):
        _cls = getattr(_u, _cn, None)
        _wb[_cn] = (_cls is not None)
    # try to actually resolve the class object (present in stub != loadable)
    try:
        _lake = _u.WaterBodyLake
        _wb["WaterBodyLake_is_class"] = isinstance(_lake, type)
    except Exception as _e0:
        _wb["WaterBodyLake_is_class"] = "ERR " + type(_e0).__name__
    _out["water_plugin_runtime"] = _wb

    # (2) The static-water-mesh path assets.
    _eal = _u.EditorAssetLibrary
    _static = {}
    _mpath = "/Game/Materials/M_SideWater"
    _static["M_SideWater_exists"] = bool(_eal.does_asset_exist(_mpath))
    if _static["M_SideWater_exists"]:
        _m = _u.load_asset(_mpath)
        _static["M_SideWater_class"] = _m.get_class().get_name()
        # read the material levers that decide if it renders as translucent water
        for _p in ("material_domain", "blend_mode", "shading_model",
                   "two_sided"):
            try:
                _static["M_SideWater_" + _p] = str(_m.get_editor_property(_p))
            except Exception as _ep:
                _static["M_SideWater_" + _p] = "ERR " + type(_ep).__name__
    _ppath = "/Engine/BasicShapes/Plane"
    _static["Plane_exists"] = bool(_eal.does_asset_exist(_ppath))
    if _static["Plane_exists"]:
        _pm = _u.load_asset(_ppath)
        _static["Plane_class"] = _pm.get_class().get_name()
        try:
            _b = _pm.get_bounds().box_extent
            _static["Plane_box_extent"] = [_b.x, _b.y, _b.z]
        except Exception as _eb:
            _static["Plane_box_extent"] = "ERR " + type(_eb).__name__
    _out["static_water_path"] = _static
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
