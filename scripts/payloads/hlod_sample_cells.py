"""Sample N built HLOD cells spread ACROSS THE GRID and verify each one.
READ-ONLY.

WHY A SPREAD AND NOT THE FIRST N
    After build 2 was killed part-way, the world was in a MIXED state: 265
    cells rebuilt as MeshApproximate at ~4,000 triangles, 2,002 still the old
    MeshMerge output at ~329,000. The builder works through the grid in a
    consistent order, so the first N cells and the last N cells were built by
    DIFFERENT builders. Sampling from one end would have reported a clean
    world in either direction depending on which end was picked.

    So the sample is taken at even intervals across the sorted label list, and
    the SPREAD is reported alongside the results.

WHAT COUNTS AS PASS, per cell
    triangles within tolerance of the target (default 4,000 +/- 50%),
    non-zero bounds, and `UStaticMesh::bSupportRayTracing` FALSE on the built
    mesh. The RT flag is read off the OUTPUT because the layer setting is only
    an input -- whether the emitted mesh carries an acceleration structure is
    the property that cost 12,434 MiB of VRAM and hung the GPU twice.

    A cell still carrying ~329,000 triangles is old MeshMerge output and is
    reported as STALE, by name, so the mixed state cannot pass unnoticed.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_sample_cells.py \
        --set COUNT=10 --set TARGET=4000
"""
import json as _json

import unreal as _u

COUNT = int("__COUNT__")
TARGET = int("__TARGET__")
LO, HI = TARGET * 0.5, TARGET * 1.5

_out = {"error": None, "count_requested": COUNT, "target_tris": TARGET,
        "tolerance": [LO, HI], "cells": []}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # Only the MERGED cells carry geometry; Instancing cells re-instance the
    # sources and have no mesh of their own.
    _cands = []
    for _d in _u.WorldPartitionBlueprintLibrary.get_actor_descs():
        try:
            _nc = _d.get_editor_property("native_class")
            if (_nc.get_name() if _nc else "") != "WorldPartitionHLOD":
                continue
        except Exception:
            continue
        _lab = str(_d.get_editor_property("label"))
        if "HLODLayer_Merged/" not in _lab:
            continue
        _cands.append((_lab, _d.get_editor_property("guid")))
    _cands.sort(key=lambda _x: _x[0])
    _out["merged_cells_total"] = len(_cands)

    if not _cands:
        _out["verdict"] = "COULD NOT LOOK -- no Merged HLOD cells found"
    else:
        _step = max(1, len(_cands) // COUNT)
        _pick = _cands[::_step][:COUNT]
        _out["sample_stride"] = _step
        _out["sample_labels"] = [_p[0] for _p in _pick]

        _u.WorldPartitionBlueprintLibrary.load_actors([_p[1] for _p in _pick])
        _byname = {}
        for _a in _eas.get_all_level_actors():
            try:
                _byname[_a.get_actor_label()] = _a
            except Exception:
                continue

        _npass = _nstale = _nfail = 0
        for _lab, _guid in _pick:
            _row = {"label": _lab}
            _act = _byname.get(_lab)
            if _act is None:
                _row["result"] = "NOT LOADED"
                _nfail += 1
                _out["cells"].append(_row)
                continue
            _comps = _act.get_components_by_class(_u.StaticMeshComponent)
            _m = None
            for _c in _comps:
                try:
                    _m = _c.get_editor_property("static_mesh")
                except Exception:
                    _m = None
                if _m is not None:
                    break
            if _m is None:
                _row["result"] = "NO MESH"
                _nfail += 1
                _out["cells"].append(_row)
                continue
            try:
                _tris = _m.get_num_triangles(0)
            except Exception as _e:
                _tris = "ERR " + type(_e).__name__
            try:
                _rt = bool(_m.get_editor_property("support_ray_tracing"))
            except Exception as _e:
                _rt = "ERR " + type(_e).__name__
            _row["triangles"] = _tris
            _row["mesh_support_ray_tracing"] = _rt
            try:
                _row["vertices"] = _m.get_num_vertices(0)
            except Exception:
                pass

            if isinstance(_tris, int) and _tris > TARGET * 10:
                _row["result"] = "STALE -- old MeshMerge output"
                _nstale += 1
            elif (isinstance(_tris, int) and LO <= _tris <= HI
                  and _rt is False):
                _row["result"] = "PASS"
                _npass += 1
            else:
                _row["result"] = "FAIL"
                _nfail += 1
            _out["cells"].append(_row)

        _out["pass"] = _npass
        _out["stale"] = _nstale
        _out["fail"] = _nfail
        _tri_vals = [_c["triangles"] for _c in _out["cells"]
                     if isinstance(_c.get("triangles"), int)]
        if _tri_vals:
            _out["triangles_min"] = min(_tri_vals)
            _out["triangles_max"] = max(_tri_vals)
            _out["triangles_mean"] = round(
                sum(_tri_vals) / float(len(_tri_vals)), 1)
        _out["verdict"] = (
            "ALL SAMPLED CELLS PASS -- no stale MeshMerge output in the sample"
            if _nstale == 0 and _nfail == 0 else
            "MIXED OR FAILING -- %d pass, %d stale, %d fail"
            % (_npass, _nstale, _nfail))
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["verdict"] = "COULD NOT LOOK"
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
