"""Translate a bench station along its own view axis, or restore it.

    MODE=move  METRES=20.0   -> move, then WRITE the moved camera back
    MODE=restore              -> put it back at the recorded location

⭐ WHY THIS IS A DIAGNOSTIC AND NOT A NEW STATION. The 30-100 m bin
shows a peak at 85-87 px on Rock and Scree and 199 px on Grass, and the
source is unknown. Translating the camera changes WHICH GROUND is in the
bin while leaving every render setting alone, so it separates "a
property of this particular terrain" from "a property of the rendering".

⛔ IT DOES NOT, BY ITSELF, SEPARATE WORLD-SCALE FROM SCREEN-SCALE. The
bin is defined by DEPTH, so after the move the bin still spans 30-100 m
and a world-fixed period of P metres still subtends the same angle at a
given depth. Anything expecting the peak to move to ~66 px on that
argument is mistaken; what moves is the CONTENT.

⛔ THE MOVED CAMERA MUST BE READ BACK AND USED BY THE ANALYSIS. The
depth->world projection is built from the camera's own basis vectors, so
analysing a moved capture against the RATIFIED station file would place
every pixel 20 m from where it actually is and mis-assign the layer
masks. This writes the read-back transform to a JSON the analysis is
pointed at with --cams.

RESTORE IS BY RECORDED ABSOLUTE LOCATION, not by moving back the same
distance: a move-and-move-back accumulates float error and, if the move
step were ever run twice, would leave the station permanently displaced.
"""
import json as _json
import traceback as _tb

import unreal as _u

STATION = "__STATION__"
ACTOR_LABEL = "Bench_" + STATION   # single source: label derives from station
MODE = "__MODE__"
# Parsed inside the try, and only in move mode (restore does not use it), so an
# absent/bad __METRES__ fails into the __LL__ JSON contract rather than crashing
# at import before any marker is printed.
METRES_RAW = "__METRES__"
CAMS = r"__CAMS__"
OUT_CAMS = r"__OUT_CAMS__"

_out = {"ok": False, "mode": MODE, "station": STATION}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _matches = [a for a in _eas.get_all_level_actors()
                if a.get_actor_label() == ACTOR_LABEL]
    if not _matches:
        # NN6 -- "I looked and it is absent", with what WAS there.
        _near = sorted(a.get_actor_label() for a in _eas.get_all_level_actors()
                       if "Bench" in a.get_actor_label())[:20]
        raise RuntimeError("no actor labelled %r; Bench actors present: %r"
                           % (ACTOR_LABEL, _near))
    if len(_matches) > 1:
        # rule 8: labels collide in this project; moving "the first match" would
        # mutate an arbitrary one. Refuse and report the ambiguity by location.
        _locs = [[round(p.x, 1), round(p.y, 1), round(p.z, 1)]
                 for p in (a.get_actor_location() for a in _matches)]
        raise RuntimeError(
            "%d actors share the label %r; refusing to move an ambiguous one "
            "(locations_cm: %r)" % (len(_matches), ACTOR_LABEL, _locs))
    _act = _matches[0]

    with open(CAMS, encoding="utf-8") as _cfh:
        _cams = _json.load(_cfh)
    _ref = _cams["cameras"][STATION]
    _home = [float(v) for v in _ref["loc_cm"]]

    _loc = _act.get_actor_location()
    _out["location_before_cm"] = [_loc.x, _loc.y, _loc.z]
    _out["recorded_home_cm"] = _home

    if MODE == "restore":
        _act.set_actor_location(
            _u.Vector(_home[0], _home[1], _home[2]), False, False)
        _rb = _act.get_actor_location()
        _out["location_after_cm"] = [_rb.x, _rb.y, _rb.z]
        _err = max(abs(_rb.x - _home[0]), abs(_rb.y - _home[1]),
                   abs(_rb.z - _home[2]))
        _out["restore_error_cm"] = _err
        if _err > 1.0:
            raise RuntimeError(
                "restore left the station %.3f cm from its recorded home"
                % _err)
    else:
        METRES = float(METRES_RAW)
        _fwd = [float(v) for v in _ref["forward"]]
        _n = (_fwd[0] ** 2 + _fwd[1] ** 2 + _fwd[2] ** 2) ** 0.5
        if _n == 0.0:
            raise RuntimeError("station %r has a zero-length forward vector; "
                               "cannot move along the view axis" % STATION)
        _d = METRES * 100.0
        _tgt = [_home[0] + _fwd[0] / _n * _d,
                _home[1] + _fwd[1] / _n * _d,
                _home[2] + _fwd[2] / _n * _d]
        _act.set_actor_location(
            _u.Vector(_tgt[0], _tgt[1], _tgt[2]), False, False)
        _rb = _act.get_actor_location()
        _out["location_after_cm"] = [_rb.x, _rb.y, _rb.z]
        _moved = (((_rb.x - _home[0]) ** 2 + (_rb.y - _home[1]) ** 2
                   + (_rb.z - _home[2]) ** 2) ** 0.5) / 100.0
        _out["moved_m"] = _moved
        if abs(_moved - METRES) > 0.05:
            raise RuntimeError(
                "asked for %.2f m, the actor reports %.3f m" % (METRES,
                                                                _moved))
        # Write the camera the frame will ACTUALLY be rendered from.
        _new = dict(_cams)
        _new["cameras"] = dict(_cams["cameras"])
        _c = dict(_ref)
        _c["loc_cm"] = [_rb.x, _rb.y, _rb.z]
        _c["_diagnostic"] = ("translated %.1f m along the view axis from "
                             "the ratified station; NOT a station" % METRES)
        _new["cameras"][STATION] = _c
        _new["_what"] = ("DIAGNOSTIC camera file for a translated capture. "
                         "Never the ratified stations.")
        with open(OUT_CAMS, "w", encoding="utf-8") as _fh:
            _fh.write(_json.dumps(_new, indent=1) + "\n")
        _out["wrote_cams"] = OUT_CAMS
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1000:]

print("__LL__" + _json.dumps(_out))
