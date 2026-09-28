"""read_light_colours.py -- audit item 4: sky.color, read back from the ACTOR.

READ-ONLY. apply_lighting is NOT re-run: the recipe has not changed, so
the values on the actors are the ones the last apply_lighting wrote, and
re-running it would be a lighting write this session is fenced against.

THE CLAIM UNDER TEST. `recipes/alpine_8k.json` declares
`lighting.sky.color` as LINEAR. `scripts/apply_lighting.py:155`
sRGB-encodes it, and `:396` writes the encoded triple with

    _slc.set_light_color(LinearColor(r, g, b, 1.0))

because C++ `SetLightColor(FLinearColor, bool bSRGB = true)` exposes ONE
argument to Python, so the engine always DECODES as sRGB and should land
back on the recipe's linear value.

⛔ THE READ-BACK IS THEREFORE A ROUND TRIP, NOT A COMPARISON. Reading
the actor and comparing to the recipe tests encode-then-decode end to
end. Comparing to the ENCODED triple would only prove the setter ran --
the failure standing rule 12 exists to catch.

⛔ AND `light_color` IS AN FColor (8-BIT), NOT AN FLinearColor. Reading
it back gives 0-255 integers, so the comparison has a QUANTISATION
FLOOR of 1/255 and any verdict must be stated against that floor rather
than against an exact match. `get_light_color` is read too where the
binding offers it, because the two may not agree and the disagreement
would itself be the finding.

The SUN is read as well: the item says "the sun's light colour", and the
recipe's `sky.color` goes to the SKYLIGHT. Both are reported so the
question is answered whichever actor was meant -- and the level holds
FOUR DirectionalLights, so every one is listed rather than "the sun"
being resolved to whichever came first.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False}


def _col(_o, _prop):
    try:
        _c = _o.get_editor_property(_prop)
    except Exception as _e:
        return {"error": "%s: %s" % (type(_e).__name__, _e)}
    _d = {"repr": str(_c)}
    for _ch in ("r", "g", "b", "a"):
        try:
            _d[_ch] = getattr(_c, _ch)
        except Exception:
            pass
    return _d


try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()

    _rows = []
    for _a in _actors:
        _cls = _a.get_class().get_name()
        if _cls not in ("SkyLight", "DirectionalLight"):
            continue
        _row = {"label": _a.get_actor_label(), "class": _cls}
        try:
            _lc = _a.light_component
        except Exception:
            _lc = None
        if _lc is None:
            try:
                _lc = _a.get_component_by_class(_u.LightComponentBase)
            except Exception as _e:
                _row["component_error"] = "%s: %s" % (type(_e).__name__, _e)
        if _lc is not None:
            _row["component_class"] = type(_lc).__name__
            _row["light_color"] = _col(_lc, "light_color")
            for _p in ("intensity", "temperature", "use_temperature"):
                try:
                    _row[_p] = _lc.get_editor_property(_p)
                except Exception:
                    pass
            # A DIFFERENT accessor for the same value. If the getter and
            # the property disagree, that disagreement is the finding.
            try:
                _row["get_light_color"] = str(_lc.get_light_color())
            except Exception as _e:
                _row["get_light_color"] = "UNAVAILABLE: %s" % type(_e).__name__
        _rows.append(_row)

    _out["lights"] = _rows
    _out["n_skylight"] = sum(1 for _r in _rows if _r["class"] == "SkyLight")
    _out["n_directional"] = sum(1 for _r in _rows
                                if _r["class"] == "DirectionalLight")
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
