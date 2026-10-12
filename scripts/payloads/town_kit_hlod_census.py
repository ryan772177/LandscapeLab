"""town_kit_hlod_census -- READ-ONLY: which HLOD actors cover the kit town, and what the default HLOD layer is.

Input (substituted): CFG = JSON {"level": "/Game/Alpine8K", "box": [[minx, miny], [maxx, maxy]]}
Reports the WorldPartition's default_hlod_layer (design review 2026-10-06 finding 6: a MeshApproximate default
would make the town rebuild expensive) and, for every loaded WorldPartitionHLOD actor whose bounds intersect the
box, its label and bounds. Changes nothing.
"""
import json as _json
import traceback as _tb
import unreal as _u

CFG = _json.loads(r'''__CFG__''')
_out = {"ok": False}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    if _w.get_path_name().split(".")[0] != CFG["level"]:
        raise RuntimeError("wrong level " + _w.get_path_name())
    _wp = _w.get_world_partition() if hasattr(_w, "get_world_partition") else None
    _dl = None
    for _src in (_wp, _w.get_world_settings()):
        if _src is None:
            continue
        for _pn in ("default_hlod_layer", "DefaultHLODLayer"):
            try:
                _v = _src.get_editor_property(_pn)
                _dl = {"from": _src.get_class().get_name(), "layer": _v.get_path_name() if _v else None}
                break
            except Exception:
                pass
        if _dl:
            break
    _out["default_hlod_layer"] = _dl
    if _dl and _dl.get("layer"):
        _lay = _u.load_asset(_dl["layer"])
        try:
            _out["default_layer_type"] = str(_lay.get_editor_property("layer_type"))
        except Exception as _e:
            _out["default_layer_type"] = "unreadable: %s" % _e
    (_x0, _y0), (_x1, _y1) = CFG["box"]
    _rows = []
    for _a in _u.get_editor_subsystem(_u.EditorActorSubsystem).get_all_level_actors():
        if _a.get_class().get_name() != "WorldPartitionHLOD":
            continue
        _o, _e = _a.get_actor_bounds(False)
        if _o.x + _e.x < _x0 or _o.x - _e.x > _x1 or _o.y + _e.y < _y0 or _o.y - _e.y > _y1:
            continue
        _rows.append({"label": _a.get_actor_label(), "min": [_o.x - _e.x, _o.y - _e.y], "max": [_o.x + _e.x, _o.y + _e.y]})
    _out["hlod_in_box"] = _rows
    _out["n_in_box"] = len(_rows)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, default=str))
