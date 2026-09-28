"""find_cell_at_station.py -- which HLOD cell sits at a station?

READ-ONLY. Picks the pilot cell by GEOMETRY, because the source-actor
list is not reachable: all 15 editor-only properties on
AWorldPartitionHLOD raise (HLODActor.h:214-245). What IS reachable is
each HLOD actor's transform, and each landscape proxy's transform and
bounds -- so "which cell is at mid_slope, and which landscape proxies
overlap it" can be answered from positions rather than from the
builder's own record.

mid_slope is at [-190000, 100000, 63450.4] cm
(_verify/bench/2026-09-11/bench_stations_derived.json).

Reports candidates from BOTH layers with their distance, and for each
candidate counts landscape proxies whose bounds overlap the cell's
bounds -- the "exactly one LandscapeStreamingProxy" the pilot wants.
"""
import json as _json
import traceback as _tb

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
SX, SY = float(CFG["x"]), float(CFG["y"])
TOP = int(CFG.get("top") or 12)

_out = {"ok": False, "station_cm": [SX, SY]}

try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells"] = len(_hlods)

    # Landscape proxy footprints, once.
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _px = []
    for _a in _eas.get_all_level_actors():
        if _a.get_class().get_name() != "LandscapeStreamingProxy":
            continue
        try:
            _o, _e = _a.get_actor_bounds(False)
            _px.append((_a.get_actor_label(),
                        float(_o.x), float(_o.y),
                        float(_e.x), float(_e.y)))
        except Exception:
            continue
    _out["n_landscape_proxies"] = len(_px)

    _rows = []
    for _ad in _hlods:
        try:
            _obj = _ad.get_asset()
        except Exception:
            continue
        if _obj is None:
            continue
        try:
            _label = _obj.get_actor_label()
            _o, _e = _obj.get_actor_bounds(False)
        except Exception:
            continue
        _cx, _cy = float(_o.x), float(_o.y)
        _ex, _ey = float(_e.x), float(_e.y)
        # Only cells whose footprint actually contains the station.
        if abs(_cx - SX) > _ex or abs(_cy - SY) > _ey:
            continue
        _n_over = 0
        _names = []
        for (_pl, _px_, _py_, _pex, _pey) in _px:
            if (abs(_px_ - _cx) <= (_ex + _pex)
                    and abs(_py_ - _cy) <= (_ey + _pey)):
                _n_over += 1
                if len(_names) < 4:
                    _names.append(_pl)
        _rows.append({
            "label": _label,
            "package": str(_ad.package_name),
            "layer": ("Merged" if "HLODLayer_Merged/" in _label
                      else "Instanced" if "HLODLayer_Instanced/" in _label
                      else "other"),
            "center_cm": [round(_cx), round(_cy)],
            "extent_cm": [round(_ex), round(_ey)],
            "dist_cm": round(((_cx - SX) ** 2 + (_cy - SY) ** 2) ** 0.5),
            "landscape_proxies_overlapping": _n_over,
            "proxy_sample": _names,
        })

    _rows.sort(key=lambda r: (r["landscape_proxies_overlapping"],
                              r["dist_cm"]))
    _out["n_cells_containing_station"] = len(_rows)
    _out["candidates"] = _rows[:TOP]
    _exactly_one = [r for r in _rows
                    if r["landscape_proxies_overlapping"] == 1]
    _out["n_with_exactly_one_proxy"] = len(_exactly_one)
    _out["exactly_one_sample"] = _exactly_one[:6]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
