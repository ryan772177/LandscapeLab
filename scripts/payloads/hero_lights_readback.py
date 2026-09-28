"""R-HERO read-back (closure A-3): every DirectionalLight in the level.

READ-ONLY. Reads the six ruled properties off EVERY DirectionalLight --
the three HeroStage_* lights AND the recipe sun -- so the table compares
like with like. Properties verified on the reflected surface
(PythonStub unreal.py): atmosphere_sun_light (bool, :697101),
atmosphere_sun_light_index (int32, :697102), lighting_channels
(LightingChannels struct, channel0/1/2 bools).

Doc basis (closure R-HERO): a DirectionalLight with atmosphere_sun_light
True competes for one of the TWO supported atmosphere-light slots; any
enabled directional light lights the scene unless channels exclude it.

Prints one __LL__ JSON object; sample count is the number of lights
found and a ZERO count is reported as its own field (standing rule 13).
"""
import json

import unreal as _u

_out = {"ok": False, "error": None, "n_directional_lights": 0, "lights": []}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _eas.get_all_level_actors():
        if type(_a).__name__ != "DirectionalLight":
            continue
        _row = {"label": _a.get_actor_label(), "path": _a.get_path_name()}
        _c = _a.get_component_by_class(_u.DirectionalLightComponent)
        if _c is None:
            _row["component"] = "NONE"
            _out["lights"].append(_row)
            continue
        for _p in ("intensity", "affects_world", "visible",
                   "atmosphere_sun_light", "atmosphere_sun_light_index",
                   "cast_shadows"):
            try:
                _v = _c.get_editor_property(_p)
                if isinstance(_v, bool):
                    _row[_p] = bool(_v)
                elif isinstance(_v, (int, float)):
                    _row[_p] = float(_v) if _p == "intensity" else int(_v)
                else:
                    _row[_p] = str(_v)[:80]
            except Exception as _e:
                _row[_p] = "unreadable: " + str(_e)[:80]
        try:
            _lc = _c.get_editor_property("lighting_channels")
            _row["lighting_channels"] = {
                "channel0": bool(_lc.get_editor_property("channel0")),
                "channel1": bool(_lc.get_editor_property("channel1")),
                "channel2": bool(_lc.get_editor_property("channel2")),
            }
        except Exception as _e:
            _row["lighting_channels"] = "unreadable: " + str(_e)[:80]
        _out["lights"].append(_row)
    _out["n_directional_lights"] = len(_out["lights"])
    if _out["n_directional_lights"] == 0:
        _out["error"] = ("ZERO DirectionalLights found -- refusing to read "
                         "silence as an answer (rule 13). Wrong level?")
    else:
        _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
