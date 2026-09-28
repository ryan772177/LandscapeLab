"""trace_station_ground.py — trace the ACTUAL ground under each survey station.

WHY A TRACE AND NOT A MEDIAN
----------------------------
The station derivation used ONE global `ground_z` -- the median actor base
across the whole world. On Electric Dreams that world is 3.3 km across with
mesas and canyons, so the median is metres of rock away from the ground at any
particular XY. shoot.py refused two stations outright:

    ground_closeup   the camera is 24.0 m BELOW the ground
    against_sky      the camera is 67.3 m BELOW the ground

That refusal is the tool working. This gives it a per-station answer instead.

Traces straight down from high above each station's XY and returns the hit Z,
so the caller can place the camera at hit + eye height. A station with no hit
is reported as such rather than silently defaulted -- "I could not find the
ground" and "the ground is at zero" must not look the same.
"""
import json as _json
import traceback as _tb

import unreal as _u

STATIONS = _json.loads(r"""__STATIONS__""")
TRACE_TOP_CM = float("__TRACE_TOP_CM__")
TRACE_BOTTOM_CM = float("__TRACE_BOTTOM_CM__")

_out = {"ok": False, "error": None, "stations": []}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()

    for _st in STATIONS:
        _x, _y = float(_st["loc"][0]), float(_st["loc"][1])
        _rec = {"name": _st["name"], "x": _x, "y": _y}
        _start = _u.Vector(_x, _y, TRACE_TOP_CM)
        _end = _u.Vector(_x, _y, TRACE_BOTTOM_CM)
        try:
            _hit = _u.SystemLibrary.line_trace_single(
                _w, _start, _end,
                _u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                # bTraceComplex=TRUE. With False the trace uses SIMPLE
                # collision, which on this world sat ~10 m below the visible
                # surface -- shoot.py's own ground check then refused the
                # station as underground and it was right. bench_make_cameras
                # passes True for exactly this reason.
                True, [], _u.DrawDebugTrace.NONE, True)
        except Exception as _e:
            _hit = None
            _rec["trace_error"] = str(_e)[:160]
        if _hit:
            # FHitResult fields are PROTECTED in 5.8 Python -- `impact_point`
            # raises AttributeError. `to_tuple()[4]` is the impact point.
            # This repo already knew that (bench_make_cameras.py:59, citing
            # perf_flythrough.py:70) and I wrote a fresh trace without
            # grepping for the existing one. Step (a) is a SEARCH, not a
            # recall.
            _rec["ground_z"] = float(_hit.to_tuple()[4].z)
            _rec["hit"] = True
        else:
            _rec["hit"] = False
            _rec["ground_z"] = None
            _rec["_note"] = ("NO GROUND HIT between z %.0f and %.0f at this "
                             "XY. Reported rather than defaulted: 'could not "
                             "find the ground' and 'the ground is at zero' "
                             "must not look the same."
                             % (TRACE_TOP_CM, TRACE_BOTTOM_CM))
        _out["stations"].append(_rec)

    _out["world"] = _w.get_path_name()
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _out["traceback"] = _tb.format_exc()[:600]

print("__LL__" + _json.dumps(_out, default=str))
