"""R-HERO discriminator arm (closure A-3): set affects_world on the
HeroStage_* DirectionalLights, and READ IT BACK off the component.

LIVE-LEVEL ONLY -- this payload NEVER SAVES. The change exists in the
running editor for the discriminator capture and is restored by a second
run with the opposite value before the editor closes. The packages go
dirty; the close gate will name them, and the close report must show the
restore read-back beside the kill authorisation.

The CONFIG-JSON substitution literal is {"affects_world": true|false}.
(The literal itself is not written here: src.replace substitutes EVERY
occurrence, docstrings included.) Only actors whose label starts with
"HeroStage" are touched; the sun is NEVER touched by this payload, by
construction.

Prints one __LL__ JSON object with per-light read-backs and the count;
zero matched lights is an error, not a success (rule 13).
"""
import json

import unreal as _u

_CFG = json.loads(r'''__CONFIG_JSON__''')

_out = {"ok": False, "error": None, "requested_affects_world": None,
        "n_matched": 0, "lights": []}
try:
    _want = bool(_CFG["affects_world"])
    _out["requested_affects_world"] = _want
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _eas.get_all_level_actors():
        try:
            _lab = _a.get_actor_label()
        except Exception:
            continue
        if not _lab.startswith("HeroStage"):
            continue
        if type(_a).__name__ != "DirectionalLight":
            continue
        _c = _a.get_component_by_class(_u.DirectionalLightComponent)
        if _c is None:
            _out["lights"].append({"label": _lab, "component": "NONE"})
            continue
        _c.set_editor_property("affects_world", _want)
        _rb = bool(_c.get_editor_property("affects_world"))
        _out["lights"].append({"label": _lab,
                               "affects_world_readback": _rb,
                               "matches_request": _rb == _want})
    _out["n_matched"] = len(_out["lights"])
    if _out["n_matched"] == 0:
        _out["error"] = ("ZERO HeroStage_* DirectionalLights matched -- "
                         "nothing was set, and that is a finding, not a "
                         "success (rule 13).")
    elif not all(_l.get("matches_request") for _l in _out["lights"]):
        _out["error"] = "at least one read-back does not match the request"
    else:
        _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
