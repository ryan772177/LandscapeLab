"""town_kit_nav_probe -- READ-ONLY: what is under a few kit-house doorsteps? (2026-10-08 reachability diagnosis)

Input (substituted): CFG = JSON {"level": "/Game/Alpine8K", "points": [[label, x, y], ...]}
Per point: every hit of a vertical multi-trace (actor label + class + z), and the navmesh projection of the
landscape hit at extents 50 / 500 / 2000 cm (projected z, or null). Changes nothing.
"""
import json as _json
import traceback as _tb
import unreal as _u

CFG = _json.loads(r'''__CFG__''')
_out = {"ok": False, "points": []}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    if _w.get_path_name().split(".")[0] != CFG["level"]:
        raise RuntimeError("wrong level " + _w.get_path_name())
    _nav = _u.NavigationSystemV1.get_navigation_system(_w)
    for _lab, _x, _y in CFG["points"]:
        _hits = _u.SystemLibrary.line_trace_multi(
            _w, _u.Vector(_x, _y, 500000.0), _u.Vector(_x, _y, -500000.0),
            _u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], _u.DrawDebugTrace.NONE, True) or []
        _hl = []
        _land_z = None
        for _h in _hits:
            _t = _h.to_tuple()
            _a = _t[9]
            _nm = _a.get_actor_label() if _a else None
            _cl = _a.get_class().get_name() if _a else None
            _hl.append([_nm, _cl, round(_t[4].z, 1), bool(_t[0])])
            if _cl in ("Landscape", "LandscapeStreamingProxy") and _land_z is None:
                _land_z = _t[4].z
        _proj = {}
        if _land_z is not None:
            for _e in (50.0, 500.0, 2000.0):
                _p = _u.NavigationSystemV1.project_point_to_navigation(
                    _w, _u.Vector(_x, _y, _land_z), None, None, _u.Vector(_e, _e, _e))
                _proj[str(int(_e))] = None if _p is None else [round(_p.x, 1), round(_p.y, 1), round(_p.z, 1)]
        _out["points"].append({"label": _lab, "xy": [_x, _y], "land_z": _land_z, "hits": _hl[:8], "proj": _proj})
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, default=str))
