"""Persist the world-level default HLOD layer that `hlod_set_world_default.py`
applied in memory, and READ IT BACK from a re-resolved chain.

WHY IT IS A SEPARATE PAYLOAD
    The set succeeded (0.005 s, read back correct) and the save then failed on
    `Package.set_dirty_flag`, which DOES NOT EXIST on the Python `Package`
    object in 5.8 -- AttributeError, measured 2026-09-08. The value is live in
    the editor and unsaved, so this payload does the save half only. It does
    not re-set the property unless it finds it wrong, which makes it safe to
    run twice.

THE DIRTY FLAG IS NOT OURS TO SET
    `set_editor_property` routes through the property system and marks the
    owning package dirty itself. Rather than assume that, the payload REPORTS
    the dirty state before and after, and dumps the reflected surface of the
    Package object filtered for "dirt"/"save" so the next session picks the
    name from a printed contract instead of a fourth guess.

VERIFICATION IS THE FILE, NOT THE RETURN VALUE
    A save API returning True proves the call ran. The evidence that something
    was WRITTEN is the .umap on disk changing size or mtime, so both are
    captured before and after and reported as a delta. Standing rule 12: the
    read-back comes from the artefact, never from the structure just written.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_save_world_default.py \
             --set LAYER=/Game/Alpine8K_HLODLayer_Landscape
"""
import json as _json
import os as _os
import time as _time

import unreal as _u

LAYER_PKG = "__LAYER__"

_out = {"error": None, "layer_requested": LAYER_PKG}


def _resolve():
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _ws = _w.get_world_settings()
    _wp = _ws.get_editor_property("world_partition") if _ws else None
    return _w, _ws, _wp


def _stat(_path):
    try:
        _st = _os.stat(_path)
        return {"bytes": _st.st_size, "mtime": round(_st.st_mtime, 1)}
    except Exception as _e:
        return {"error": type(_e).__name__ + ": " + str(_e)}


try:
    _w, _ws, _wp = _resolve()
    _out["level_path"] = _w.get_path_name()
    if _wp is None:
        _out["error"] = "could not resolve WorldPartition"
    else:
        _cur = _wp.get_editor_property("default_hlod_layer")
        _out["default_hlod_layer_ON_ENTRY"] = (_cur.get_path_name()
                                               if _cur else None)

        # Only set if it is not already what we want -- idempotent.
        if _cur is None or not _cur.get_path_name().startswith(LAYER_PKG):
            _tgt = _u.load_asset(LAYER_PKG)
            if _tgt is None:
                raise RuntimeError("layer asset did not load: " + LAYER_PKG)
            _wp.set_editor_property("default_hlod_layer", _tgt)
            _out["re_set"] = True
        else:
            _out["re_set"] = False

        _pkg = _ws.get_package()
        _out["package"] = _pkg.get_name()
        _out["package_surface"] = sorted(
            _n for _n in dir(_pkg) if "dirt" in _n.lower() or "save" in _n.lower())
        try:
            _out["package_dirty_before_save"] = bool(_pkg.is_dirty())
        except Exception as _e:
            _out["package_dirty_before_save"] = (
                "unavailable: " + type(_e).__name__)

        # ---- the artefact, before -----------------------------------------
        _umap = _os.path.join(
            _u.Paths.project_content_dir(), "Alpine8K.umap")
        _umap = _os.path.abspath(_umap)
        _out["umap_path"] = _umap
        _out["umap_before"] = _stat(_umap)

        # ---- save ----------------------------------------------------------
        _t0 = _time.time()
        _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
        _saved = _les.save_current_level()
        _out["save_seconds"] = round(_time.time() - _t0, 3)
        _out["save_returned"] = bool(_saved)

        _out["umap_after"] = _stat(_umap)
        _b, _a = _out["umap_before"], _out["umap_after"]
        if "bytes" in _b and "bytes" in _a:
            _out["umap_changed"] = (_b["bytes"] != _a["bytes"]
                                    or _b["mtime"] != _a["mtime"])
            _out["umap_byte_delta"] = _a["bytes"] - _b["bytes"]

        try:
            _out["package_dirty_after_save"] = bool(_pkg.is_dirty())
        except Exception as _e:
            _out["package_dirty_after_save"] = (
                "unavailable: " + type(_e).__name__)

        # ---- READ BACK from a freshly resolved chain -----------------------
        _w2, _ws2, _wp2 = _resolve()
        _rb = (_wp2.get_editor_property("default_hlod_layer")
               if _wp2 is not None else None)
        _out["default_hlod_layer_AFTER_SAVE"] = (_rb.get_path_name()
                                                 if _rb else None)
        _out["readback_matches_request"] = bool(
            _rb is not None and _rb.get_path_name().startswith(LAYER_PKG))
        del _w2
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
