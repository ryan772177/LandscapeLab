import json as _json
import os
import unreal as _u

# HLOD SHARE PASS -- step 1: ENUMERATE (read-only). How many WorldPartitionHLOD
# actors are resident in /Game/Alpine8K right now, are they visible, and where
# are they relative to the three perf stations? Answers whether the "distant
# forest is HLOD" inference has any resident HLOD to attribute cost to. Spawns
# nothing, hides nothing, saves nothing.
_root = os.path.dirname(os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
_out = {"ok": False}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _all = _eas.get_all_level_actors()
    _hlod = [a for a in _all if a and "HLOD" in a.get_class().get_name()]
    _out["total_actors"] = len(_all)
    _out["hlod_actor_count"] = len(_hlod)
    # class histogram of the HLOD-named actors
    _hist = {}
    for a in _hlod:
        cn = a.get_class().get_name()
        _hist[cn] = _hist.get(cn, 0) + 1
    _out["hlod_class_histogram"] = _hist

    _stations = {
        "treeline": (-190000.0, 100000.0, 63367.4),
        "plaza": (-210800.0, 278800.0, 18847.2),
        "vista": (-216400.0, 63600.0, 76426.2),
    }

    def _dist(loc, s):
        import math
        return math.sqrt((loc.x - s[0]) ** 2 + (loc.y - s[1]) ** 2
                         + (loc.z - s[2]) ** 2) / 100.0

    _samples = []
    _vis = 0
    for a in _hlod:
        try:
            hidden = bool(a.is_hidden_ed()) if hasattr(a, "is_hidden_ed") else None
        except Exception:
            hidden = None
        if hidden is False:
            _vis += 1
        if len(_samples) < 8:
            try:
                loc = a.get_actor_location()
                near = {k: round(_dist(loc, s), 1) for k, s in _stations.items()}
            except Exception:
                near = None
            _samples.append({"name": a.get_actor_label(),
                             "class": a.get_class().get_name(),
                             "hidden_ed": hidden, "dist_m_to_stations": near})
    _out["hlod_visible_in_editor"] = _vis
    _out["hlod_samples"] = _samples

    # nearest HLOD actor to each station (of a bounded scan)
    _nearest = {k: None for k in _stations}
    for a in _hlod[:4000]:
        try:
            loc = a.get_actor_location()
        except Exception:
            continue
        for k, s in _stations.items():
            d = _dist(loc, s)
            if _nearest[k] is None or d < _nearest[k][0]:
                _nearest[k] = (round(d, 1), a.get_actor_label())
    _out["nearest_hlod_to_station"] = {k: {"dist_m": v[0], "name": v[1]}
                                       for k, v in _nearest.items() if v}
    _out["ok"] = True
except Exception as _e:
    import traceback
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = traceback.format_exc()

try:
    _dest = os.path.join(_root, "research", "brief5", "input",
                         "hlod_share_enumerate.json")
    with open(_dest, "w", encoding="utf-8") as _fh:
        _json.dump(_out, _fh, indent=2, default=str)
    _out["written_to"] = _dest
except Exception as _e:
    _out["write_error"] = str(_e)
print(_json.dumps(_out, indent=2, default=str))
