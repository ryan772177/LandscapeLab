"""Find a REFLECTED route from the editor world to AWorldSettings, and from
there to UWorldPartition. READ-ONLY.

WHY
    Two routes are already eliminated by measurement, 2026-09-08:
      * `unreal.GameplayStatics.get_world_settings` -- AttributeError, the
        function does not exist in 5.8.
      * `UWorld::PersistentLevel` -- "Failed to find property
        'persistent_level' ... on 'World'". It IS `UPROPERTY(Transient)` at
        `World.h:952-953`, so being a UPROPERTY in C++ is NOT sufficient for
        the Python attribute to exist. That is docs/ue58-api-protocol.md's
        point exactly: the REFLECTED surface is the contract, and C++ source is
        where you form the hypothesis, not where you confirm it.

    This payload asks the editor what it actually has, instead of proposing a
    third guess. It reports every candidate and dumps the filtered `dir()` of
    each object it reaches, so the next payload picks a name from a printed
    contract.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_route_discovery.py
"""
import json as _json

import unreal as _u


def _filt(_obj, _words):
    try:
        _n = dir(_obj)
    except Exception as _e:
        return "dir() failed: " + type(_e).__name__
    return sorted(_x for _x in _n
                  if any(_wd in _x.lower() for _wd in _words))


_out = {"error": None, "routes": {}}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()
    _out["world_class"] = _w.get_class().get_name()
    _out["world_surface"] = _filt(
        _w, ["level", "setting", "partition", "hlod", "subsystem"])

    _ws = None

    # -- route A: GameplayStatics.get_all_actors_of_class -------------------
    try:
        _found = _u.GameplayStatics.get_all_actors_of_class(_w, _u.WorldSettings)
        _out["routes"]["A_get_all_actors_of_class"] = {
            "count": len(_found),
            "paths": [_a.get_path_name() for _a in _found][:4],
        }
        if _found:
            _ws = _found[0]
    except Exception as _e:
        _out["routes"]["A_get_all_actors_of_class"] = (
            "FAILED " + type(_e).__name__ + ": " + str(_e))

    # -- route B: EditorActorSubsystem, unfiltered class sweep --------------
    # get_all_level_actors returned no WorldSettings on 2026-09-08; recorded
    # again here so the elimination is in the same artefact as the survivor.
    try:
        _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
        _hits = [_a for _a in _eas.get_all_level_actors()
                 if isinstance(_a, _u.WorldSettings)]
        _out["routes"]["B_get_all_level_actors"] = {
            "count": len(_hits),
            "paths": [_a.get_path_name() for _a in _hits][:4],
        }
        if _ws is None and _hits:
            _ws = _hits[0]
    except Exception as _e:
        _out["routes"]["B_get_all_level_actors"] = (
            "FAILED " + type(_e).__name__ + ": " + str(_e))

    # -- route C: name the subobject directly -------------------------------
    # A WP map's WorldSettings lives in the map package as a subobject of the
    # persistent level. Guessing the suffix is fragile, so several are tried
    # and every result is reported rather than only the first success.
    _base = _w.get_path_name() + ":PersistentLevel."
    _tried = {}
    for _suffix in ("WorldSettings_0", "WorldSettings_1", "WorldSettings"):
        try:
            _o = _u.load_object(None, _base + _suffix)
        except Exception as _e:
            _o = None
            _tried[_suffix] = "raised " + type(_e).__name__
            continue
        _tried[_suffix] = _o.get_path_name() if _o else None
        if _ws is None and _o is not None:
            _ws = _o
    _out["routes"]["C_named_subobject"] = _tried

    # -- what we got --------------------------------------------------------
    _out["worldsettings_found"] = _ws.get_path_name() if _ws is not None else None
    if _ws is not None:
        _out["worldsettings_class"] = _ws.get_class().get_name()
        _out["worldsettings_package"] = _ws.get_package().get_name()
        _out["worldsettings_surface"] = _filt(
            _ws, ["partition", "hlod", "lod"])
        try:
            _wp = _ws.get_editor_property("world_partition")
            _out["world_partition"] = _wp.get_path_name() if _wp else None
            if _wp is not None:
                _out["world_partition_class"] = _wp.get_class().get_name()
                _out["wp_surface"] = _filt(_wp, ["hlod", "default", "stream"])
                _d = _wp.get_editor_property("default_hlod_layer")
                _out["default_hlod_layer_CURRENT"] = (
                    _d.get_path_name() if _d else None)
        except Exception as _e:
            _out["world_partition_error"] = type(_e).__name__ + ": " + str(_e)
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
