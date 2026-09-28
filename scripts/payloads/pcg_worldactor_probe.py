import json as _json
import os
import traceback as _tb
import unreal as _u

# PCG WORLD ACTOR PROBE -- read-only (Brief 5 item 3a). Reports whether a
# PCGWorldActor exists in /Game/Alpine8K and, if so, its partition grid size;
# if none exists, the class-default (CDO) partition grid size. Spawns nothing,
# saves nothing, modifies nothing. Reflection-first: property names are read
# via get_editor_property in try/except and the available names are listed
# rather than guessed (docs/ue58-api-protocol.md).
_root = os.path.dirname(os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
_out = {"ok": False, "error": None}
try:
    # class resolution -- report UNAVAILABLE rather than crash if the PCG
    # module did not load into this editor.
    _cls = getattr(_u, "PCGWorldActor", None)
    _out["pcg_worldactor_class_available"] = _cls is not None

    _actors = []
    if _cls is not None:
        try:
            _found = _u.GameplayStatics.get_all_actors_of_class(
                _u.EditorLevelLibrary.get_editor_world(), _cls)
            _actors = list(_found) if _found else []
        except Exception as _e:
            _out["get_all_actors_error"] = str(_e)
            # fallback: scan the level actor list by class name
            try:
                _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
                _actors = [a for a in _eas.get_all_level_actors()
                           if a and "PCGWorldActor" in a.get_class().get_name()]
            except Exception as _e2:
                _out["actor_scan_error"] = str(_e2)

    _out["pcg_worldactor_count"] = len(_actors)

    def _read_grid(obj, label):
        rec = {"_source": label}
        for _prop in ("partition_grid_size", "PartitionGridSize",
                      "partition_grid_size_2d"):
            try:
                rec[_prop] = obj.get_editor_property(_prop)
            except Exception as _e:
                rec[_prop + "_err"] = str(_e)
        return rec

    if _actors:
        _out["instance_grid"] = _read_grid(_actors[0], "live PCGWorldActor")
    elif _cls is not None:
        # class default object -- the grid a PCGWorldActor would spawn with
        try:
            _cdo = _u.get_default_object(_cls)
            _out["cdo_grid"] = _read_grid(_cdo, "class default object")
        except Exception as _e:
            _out["cdo_error"] = str(_e)

    # PCG subsystem presence (does the world carry a PCG subsystem at all)
    for _sub in ("PCGSubsystem",):
        _sc = getattr(_u, _sub, None)
        _out[_sub + "_class_available"] = _sc is not None

    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _out["traceback"] = _tb.format_exc()

try:
    _dest = os.path.join(_root, "research", "brief5", "input",
                         "pcg_worldactor_probe.json")
    if not os.path.isdir(os.path.dirname(_dest)):
        os.makedirs(os.path.dirname(_dest))
    with open(_dest, "w", encoding="utf-8") as _fh:
        _json.dump(_out, _fh, indent=2, default=str)
    _out["written_to"] = _dest
except Exception as _e:
    _out["write_error"] = str(_e)

print(_json.dumps(_out, indent=2, default=str))
