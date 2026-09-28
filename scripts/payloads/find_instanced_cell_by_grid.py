"""find_instanced_cell_by_grid.py -- locate a cell from its NAME, not its bounds.

READ-ONLY.

`get_actor_bounds` returns degenerate extents for Instanced-layer HLOD
actors -- their ISM components are not registered in this editor session
-- so a bounds search finds only Merged cells and would pick the wrong
population for a landscape pilot.

The name carries the grid coordinate exactly:

    Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L<n>_X<x>_Y<y>

and the runtime grid's cell size is 25600 cm at L0, doubling per level
(the world's loading range and cell size were read on 2026-09-13:
cell_size 25600). So cell centre = (index + 0.5) * cellsize(level), and
containment is exact arithmetic rather than a bounds query that depends
on what happens to be loaded.

Reports every cell whose footprint contains the station, per level, for
BOTH layers.
"""
import json as _json
import re as _re
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
SX, SY = float(CFG["x"]), float(CFG["y"])
L0 = float(CFG.get("cell_size_l0") or 25600.0)

_RX = _re.compile(r"_L(\d+)_X(-?\d+)_Y(-?\d+)")

_out = {"ok": False, "station_cm": [SX, SY], "cell_size_l0_cm": L0}

try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells"] = len(_hlods)

    _hits = []
    _levels = _Counter()
    _parsed = 0
    _unparsed = 0
    for _ad in _hlods:
        try:
            _obj = _ad.get_asset()
            _label = _obj.get_actor_label() if _obj else None
        except Exception:
            _label = None
        if not _label:
            continue
        _m = _RX.search(_label)
        if not _m:
            _unparsed += 1
            continue
        _parsed += 1
        _lvl, _ix, _iy = int(_m.group(1)), int(_m.group(2)), int(_m.group(3))
        _layer = ("Merged" if "HLODLayer_Merged/" in _label
                  else "Instanced" if "HLODLayer_Instanced/" in _label
                  else "other")
        _levels["%s_L%d" % (_layer, _lvl)] += 1
        _cs = L0 * (2 ** _lvl)
        _cx = (_ix + 0.5) * _cs
        _cy = (_iy + 0.5) * _cs
        if abs(_cx - SX) <= _cs * 0.5 and abs(_cy - SY) <= _cs * 0.5:
            _hits.append({
                "label": _label,
                "package": str(_ad.package_name),
                "layer": _layer, "level": _lvl,
                "grid": [_ix, _iy],
                "cell_size_cm": _cs,
                "centre_cm": [round(_cx), round(_cy)],
                "dist_cm": round(((_cx - SX) ** 2 + (_cy - SY) ** 2) ** 0.5),
            })

    _out["labels_parsed"] = _parsed
    _out["labels_unparsed"] = _unparsed
    _out["cells_by_layer_level"] = dict(_levels)
    _hits.sort(key=lambda h: (h["layer"], h["level"]))
    _out["containing_station"] = _hits
    _out["n_containing"] = len(_hits)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
