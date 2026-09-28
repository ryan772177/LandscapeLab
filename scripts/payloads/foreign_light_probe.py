"""Are the HeroStage lights actually LIGHTING the Alpine8K scene?

READ-ONLY. Three DirectionalLights the recipe does not govern were found
in /Game/Alpine8K: HeroStage_Key 25000, HeroStage_Rim 11250,
HeroStage_Fill 7500 lux -- 43750 lux beside a 130000 lux recipe sun.

PRESENCE IS NOT CONTRIBUTION. A light can be hidden, set to affect
nothing, or be an editor-only actor. The question the shadow-tint work
actually needs answered is whether these reach the frame, so this reads
the properties that decide it rather than inferring from the label.

`apply_lighting` reported "foreign 0" and said so honestly as "strong
evidence, not proof" -- World Partition exposes nothing from unloaded
cells. This runs after a bench capture forced residency.
"""
import json

import unreal as _u

_WANT = ("visible", "hidden", "is_hidden_ed", "affects_world",
         "cast_shadows", "intensity", "light_color", "mobility",
         "is_spatially_loaded", "affect_translucent_lighting",
         "cast_static_shadows", "cast_dynamic_shadows")

_out = {"ok": False, "lights": []}
try:
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _sub.get_all_level_actors():
        if type(_a).__name__ != "DirectionalLight":
            continue
        _row = {"label": _a.get_actor_label()}
        # actor-level
        for _p in ("is_hidden_ed", "is_spatially_loaded"):
            try:
                _row[_p] = bool(_a.get_editor_property(_p))
            except Exception:
                pass
        try:
            _row["hidden_in_game"] = bool(_a.get_editor_property("hidden"))
        except Exception:
            pass
        try:
            _l = _a.get_actor_location()
            _row["loc_m"] = [round(_l.x / 100.0), round(_l.y / 100.0),
                             round(_l.z / 100.0)]
        except Exception:
            pass
        # component-level
        _c = None
        for _p in ("directional_light_component", "light_component"):
            try:
                _c = _a.get_editor_property(_p)
                if _c is not None:
                    break
            except Exception:
                continue
        if _c is not None:
            for _p in _WANT:
                try:
                    _v = _c.get_editor_property(_p)
                    if isinstance(_v, bool):
                        _row[_p] = bool(_v)
                    elif isinstance(_v, (int, float)):
                        _row[_p] = float(_v)
                    else:
                        _row[_p] = str(_v)[:60]
                except Exception:
                    pass
        _out["lights"].append(_row)
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
