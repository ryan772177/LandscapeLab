"""Diagnose check_collision_truth's ~50% landscape-hit rate on Alpine8K.

READ-ONLY. Traces the same window the gate uses (expected height +50 m /
-300 m, TraceTypeQuery1, trace_complex True, line_trace_multi) at a fixed
grid of points and reports, PER POINT, the class name and Z of every hit
returned — so "the trace returned nothing" and "the trace stopped at a
non-landscape blocker" become distinguishable (they have different fixes:
residency vs channel/ignore-list).

Points are read from the heightmap-derived list staged by the caller at
_verify/brief4/collision_probe_points.json (R-UEEXEC: data via disk, not
--set). Each entry: [x_cm, y_cm, expected_z_cm].
"""
import json as _json
import os as _os
import unreal as _u

_out = {"ok": False, "world": None, "points": [], "error": None}
try:
    _w = _u.get_editor_subsystem(
        _u.UnrealEditorSubsystem).get_editor_world()
    _out["world"] = _w.get_path_name()
    _root = _os.path.dirname(_os.path.normpath(
        _u.Paths.project_dir().rstrip("/\\")))
    with open(_os.path.join(_root, "_verify", "brief4",
                            "collision_probe_points.json")) as _f:
        _pts = _json.load(_f)
    _chan = _u.TraceTypeQuery.TRACE_TYPE_QUERY1
    _dbg = _u.DrawDebugTrace.NONE
    _ignore = _u.Array(_u.Actor)
    for _x, _y, _z in _pts:
        _s = _u.Vector(_x, _y, _z + 5000.0)
        _e = _u.Vector(_x, _y, _z - 30000.0)
        _hits = _u.SystemLibrary.line_trace_multi(
            _w, _s, _e, _chan, True, _ignore, _dbg, True)
        _rec = {"xy": [_x, _y], "expected_z": _z, "hits": []}
        for _h in (_hits or []):
            try:
                _d = _h.to_dict()
            except Exception:
                _rec["hits"].append({"class": "TO_DICT_FAILED"})
                continue
            _act = _d.get("hit_actor")
            _loc = _d.get("impact_point") or _d.get("location")
            _rec["hits"].append({
                "class": type(_act).__name__ if _act else None,
                "label": _act.get_actor_label() if _act else None,
                "z": float(_loc.z) if _loc else None,
                "blocking": (bool(_d["blocking_hit"])
                             if "blocking_hit" in _d else "KEY_MISSING")})
        _out["points"].append(_rec)
    del _w
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:400]
print("__LL__" + _json.dumps(_out, default=str))
