"""Can the editor's MESSAGE LOG be read from Python?

READ-ONLY. The pre-exposure / sky-capture-clipping warning Ryan sees is
NOT in LandscapeLab.log -- searched, live and all backups. It is a Slate
notification, so the only ways to its text are the UI or a reflected API.

This enumerates the reflected surface rather than guessing a name: an API
remembered is an API guessed, and UE 5.8 postdates the training data.
Reports what EXISTS; reads nothing it has not first confirmed.
"""
import json

import unreal as _u

_out = {"ok": False}
try:
    # 1. module-level names that could reach a message log
    _names = sorted(n for n in dir(_u)
                    if any(k in n.lower() for k in
                           ("messagelog", "message_log", "logmessage",
                            "tokenizedmessage", "mapcheck")))
    _out["module_names"] = _names

    # 2. any subsystem whose name suggests it
    _subs = sorted(n for n in dir(_u)
                   if n.endswith("Subsystem")
                   and any(k in n.lower() for k in ("message", "log", "valid")))
    _out["subsystems"] = _subs

    # 3. if a MessageLog type exists, what does it expose?
    for _n in _names:
        try:
            _cls = getattr(_u, _n)
            _out.setdefault("members", {})[_n] = sorted(
                m for m in dir(_cls) if not m.startswith("_"))[:40]
        except Exception as _e:
            _out.setdefault("members", {})[_n] = "ERR %s" % type(_e).__name__

    # 4. the SkyLight / SkyAtmosphere actors' own state, which is what the
    #    warning is ABOUT -- recorded here so the reading is not lost even
    #    if the log text cannot be reached
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _sky = []
    for _a in _sub.get_all_level_actors():
        _cn = type(_a).__name__
        if _cn in ("SkyLight", "SkyAtmosphere", "DirectionalLight"):
            _row = {"label": _a.get_actor_label(), "class": _cn}
            _c = None
            for _p in ("sky_light_component", "sky_atmosphere_component",
                       "directional_light_component"):
                try:
                    _c = _a.get_editor_property(_p)
                    break
                except Exception:
                    continue
            if _c is not None:
                for _p in ("real_time_capture", "intensity",
                           "source_type", "cubemap_resolution",
                           "lower_hemisphere_is_black"):
                    try:
                        _v = _c.get_editor_property(_p)
                        _row[_p] = (float(_v) if isinstance(_v, (int, float))
                                    else str(_v))
                    except Exception:
                        pass
            _sky.append(_row)
    _out["sky_actors"] = _sky
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = traceback.format_exc()[-700:]

print("__LL__" + json.dumps(_out))
