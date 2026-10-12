"""check_town_kit_ufunctions -- cold-boot check (R-GAMEPLAY): are SpawnKitHouse / SetKitInstances reflected?"""
import json as _json
import unreal as _u

_out = {"plugin_enabled": None, "has_spawn": False, "has_set": False}
try:
    _out["plugin_enabled"] = "LandscapeLabEditor" in [str(p) for p in _u.PluginBlueprintLibrary.get_enabled_plugin_names()]
except Exception as _e:
    _out["plugin_enabled"] = "READ FAILED: %s" % _e
_t = getattr(_u, "LandscapeLabTools", None)
_out["class_reflected"] = _t is not None
if _t is not None:
    _out["has_spawn"] = hasattr(_t, "spawn_kit_house")
    _out["has_set"] = hasattr(_t, "set_kit_instances")
_out["ok"] = bool(_out["has_spawn"] and _out["has_set"])
print("__LL__" + _json.dumps(_out))
