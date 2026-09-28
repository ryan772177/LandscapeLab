"""Parse the HLOD actor LABEL grid and locate the cell over a target point.
READ-ONLY.

WHY LABELS AND NOT BOUNDS
    After `-SetupHLODs` but before `-BuildHLODs`, every HLOD actor desc reports
    `Bounds` of zero extent at the origin -- measured 2026-09-08 across all
    2,230. The actors exist; they have no geometry yet, so they have no bounds
    yet. Selecting a build target by proximity is therefore impossible and the
    LABEL is the only spatial information available.

    Labels look like:
        Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L1_X-14_Y1
        Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-14_Y-16

    so they carry <source>_L<level>_X<i>_Y<j>. This payload reports the index
    RANGE per (layer, level) so the cell size can be DERIVED from the observed
    span against the known world extent, rather than assumed to be the layer
    asset's `cell_size` -- HLOD levels may rescale and that is exactly the kind
    of assumption this project keeps paying for.

    The world spans 8129 m centred on the origin: -406400..406400 cm.
    A level whose X index runs -16..15 is therefore on 25600 cm cells.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_label_grid.py \
        --set TX=-241764 --set TY=293185
"""
import json as _json
import re as _re

import unreal as _u

TX = float("__TX__")
TY = float("__TY__")
WORLD_MIN = -406400.0
WORLD_MAX = 406400.0

_pat = _re.compile(r"_L(-?\d+)_X(-?\d+)_Y(-?\d+)$")

_out = {"error": None, "target_cm": [TX, TY]}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _descs = _u.WorldPartitionBlueprintLibrary.get_actor_descs()
    _groups = {}
    _unparsed = []
    for _d in _descs:
        try:
            _nc = _d.get_editor_property("native_class")
            if (_nc.get_name() if _nc else "") != "WorldPartitionHLOD":
                continue
        except Exception:
            continue
        _label = str(_d.get_editor_property("label"))
        _grid = str(_d.get_editor_property("runtime_grid"))
        _m = _pat.search(_label)
        if not _m:
            _unparsed.append(_label)
            continue
        _lvl, _xi, _yi = int(_m.group(1)), int(_m.group(2)), int(_m.group(3))
        _key = _grid + " | L" + str(_lvl)
        _g = _groups.setdefault(_key, {"count": 0, "x": [], "y": [],
                                       "labels": {}})
        _g["count"] += 1
        _g["x"].append(_xi)
        _g["y"].append(_yi)
        _g["labels"][(_xi, _yi)] = _label

    _summary = {}
    for _key, _g in sorted(_groups.items()):
        _xmin, _xmax = min(_g["x"]), max(_g["x"])
        _ymin, _ymax = min(_g["y"]), max(_g["y"])
        _span = _xmax - _xmin + 1
        _span_y = _ymax - _ymin + 1
        # DERIVED, not assumed: world extent divided by observed index span.
        # Derive per-axis and use the Y cell for the Y index (the old code used
        # the X-derived cell for BOTH, silently wrong when X and Y coverage /
        # spans differ). cell_axes_agree flags a non-square/partial grid where
        # the derivation is unreliable.
        _cell = (WORLD_MAX - WORLD_MIN) / _span if _span else None
        _cell_y = (WORLD_MAX - WORLD_MIN) / _span_y if _span_y else None
        _tx_i = int((TX - WORLD_MIN) // _cell) + _xmin if _cell else None
        _ty_i = int((TY - WORLD_MIN) // _cell_y) + _ymin if _cell_y else None
        _hit = _g["labels"].get((_tx_i, _ty_i))
        _summary[_key] = {
            "count": _g["count"],
            "x_range": [_xmin, _xmax], "y_range": [_ymin, _ymax],
            "index_span": _span, "index_span_y": _span_y,
            "derived_cell_cm": round(_cell, 1) if _cell else None,
            "derived_cell_cm_y": round(_cell_y, 1) if _cell_y else None,
            "cell_axes_agree": (abs(_cell - _cell_y) < 1.0
                                if (_cell and _cell_y) else None),
            "target_index": [_tx_i, _ty_i],
            "label_at_target": _hit,
            "_derivation": ("cell = 812800 cm world extent / observed index "
                            "span PER AXIS; index = floor((target - "
                            "world_min)/cell) offset by the observed minimum "
                            "index. Unreliable if cell_axes_agree is false "
                            "(coverage is partial/non-square)."),
        }
    _out["groups"] = _summary
    _out["unparsed_label_count"] = len(_unparsed)
    _out["unparsed_sample"] = _unparsed[:5]
    _out["hlod_total"] = sum(_g["count"] for _g in _groups.values())
    # NN13: zero HLOD actors parsed is not a clean grid -- distinguish "found
    # and gridded" from "found nothing".
    _out["ok"] = _out["hlod_total"] > 0
    if not _out["ok"]:
        _out["note"] = ("no parseable WorldPartitionHLOD actor labels found "
                        "(%d unparsed) -- nothing to grid" % len(_unparsed))
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
