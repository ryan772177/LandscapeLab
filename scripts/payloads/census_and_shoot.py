"""census_and_shoot.py — load a map, census it, and DERIVE the survey camera
stations. Writes stations to JSON for the host to shoot separately.

WHY THE SHOTS ARE NOT TAKEN HERE
--------------------------------
`-ExecutePythonScript` calls `UUnrealEdEngine::CloseEditor()` as soon as the
script returns -- measured 2026-09-09, log line:

    LogCore: Engine exit requested (reason: UUnrealEdEngine::CloseEditor())
    ... 0.6 s after "tick callback registered, 11 plan steps"

`HighResShot` completes over SUBSEQUENT ticks, and there are none: the first
version registered a slate post-tick callback, and the editor shut down before
a single tick ran. It reported success and filed zero shots.

So this pass derives the stations and the HOST shoots them, one `-game`
launch per station with `BugItGo` + `HighResShot` -- the pattern already
proven in E3 (R-PERFSTANDALONE), where BugItGo was accepted and the frames
were written.

NOTHING IS SAVED. The map is loaded, never saved.
"""
import json as _json
import os as _os
import traceback as _tb

import unreal as _u

_OUT = r"__OUT__"
_MAP = r"__MAP__"
_STATIONS_OUT = r"__STATIONS_OUT__"
_CENSUS_SRC = r"__CENSUS_SRC__"

# An actor bigger than this in any axis is scenery-scale infrastructure -- a
# sky sphere, an atmosphere, a kill volume -- not content the survey should
# frame. Measured on Small_City_LVL: raw bounds reached Z 2,012,409 cm (20 km)
# and would have placed the "wide vista" camera 4 km above the city.
_MAX_ACTOR_EXTENT_CM = 200000.0


def _log(msg):
    _u.log("CENSUSLOG " + str(msg))


def _pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    i = int(max(0, min(len(s) - 1, round(p * (len(s) - 1)))))
    return float(s[i])


def _survey(bounds):
    """(name, x, y, z, pitch, yaw) per station, from robust world bounds."""
    x0, y0, x1, y1 = bounds["x0"], bounds["y0"], bounds["x1"], bounds["y1"]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    span = max(x1 - x0, y1 - y0, 5000.0)
    ground = bounds["ground_z"]
    return [
        ("wide_vista",     cx - span * 0.45, cy - span * 0.45,
         ground + span * 0.28, -20.0, 45.0),
        ("mid_distance",   cx - span * 0.16, cy - span * 0.16,
         ground + span * 0.06,  -9.0, 45.0),
        ("ground_closeup", cx - span * 0.03, cy - span * 0.03,
         ground + 175.0,        -3.0, 45.0),
        ("against_sky",    cx + span * 0.06, cy + span * 0.06,
         ground + 250.0,        14.0, -135.0),
        ("overview_high",  cx, cy, ground + span * 0.55, -55.0, 20.0),
    ]


_out = {"ok": False, "errors": [], "map": _MAP}
try:
    if _MAP and not _MAP.startswith("/Game/__"):
        _u.EditorLoadingAndSavingUtils.load_map(_MAP)
        _log("loaded " + _MAP)

    if _CENSUS_SRC:
        with open(_CENSUS_SRC, "r", encoding="utf-8") as fh:
            _src = fh.read()
        exec(compile(_src, _CENSUS_SRC, "exec"), {"__name__": "__census__"})
        _log("census executed")

    # ---- robust bounds --------------------------------------------------
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _xs, _ys, _zs, _kept, _skipped = [], [], [], 0, 0
    for _a in _eas.get_all_level_actors():
        try:
            _o, _e = _a.get_actor_bounds(False)
        except Exception:
            continue
        if _e.x <= 0.0 and _e.y <= 0.0:
            continue
        if (_e.x > _MAX_ACTOR_EXTENT_CM or _e.y > _MAX_ACTOR_EXTENT_CM
                or _e.z > _MAX_ACTOR_EXTENT_CM):
            _skipped += 1          # sky sphere / atmosphere / kill volume
            continue
        _kept += 1
        _xs.append(float(_o.x))
        _ys.append(float(_o.y))
        _zs.append(float(_o.z - _e.z))     # actor BASE, i.e. near the ground

    if not _xs:
        raise RuntimeError("no usable actor bounds in %s" % _MAP)

    # Percentiles, not min/max: one stray actor at the edge of the streaming
    # grid should not define where the survey stands.
    _b = {"x0": _pct(_xs, 0.05), "x1": _pct(_xs, 0.95),
          "y0": _pct(_ys, 0.05), "y1": _pct(_ys, 0.95),
          "ground_z": _pct(_zs, 0.50),
          "actors_kept": _kept, "actors_skipped_oversize": _skipped}
    _log("bounds x %.0f..%.0f  y %.0f..%.0f  ground %.0f  (kept %d, skipped %d)"
         % (_b["x0"], _b["x1"], _b["y0"], _b["y1"], _b["ground_z"],
            _kept, _skipped))

    _st = [{"name": n, "loc": [x, y, z], "pitch": p, "yaw": w}
           for (n, x, y, z, p, w) in _survey(_b)]
    _out["bounds"] = _b
    _out["stations"] = _st
    try:
        _out["current_world"] = _u.get_editor_subsystem(
            _u.UnrealEditorSubsystem).get_editor_world().get_path_name()
    except Exception as _e:
        _out["current_world"] = "ERR %s" % _e

    _os.makedirs(_os.path.dirname(_STATIONS_OUT), exist_ok=True)
    with open(_STATIONS_OUT, "w", encoding="utf-8") as fh:
        _json.dump(_out, fh, indent=1, default=str)
    _out["ok"] = True
    _out["stations_written"] = _STATIONS_OUT
except Exception as _e:  # noqa
    _out["errors"].append(str(_e) + " | " + _tb.format_exc()[:600])

print("__LL__" + _json.dumps(_out, default=str))
