"""export_hlod_cell_textures -- read-only diagnostic (2026-10-06).

Loads one HLOD cell package and exports every Texture2D inside it to PNG under OUT_DIR,
so the baked BaseColor border can be inspected texel by texel (black-margin hypothesis,
LESSONS 2026-10-06c). Writes nothing under Content/, saves nothing, dirties nothing it
does not need to (export only).
    PKG     = /Game/__ExternalActors__/... package of the cell
    OUT_DIR = absolute output directory inside the repo
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

PKG = "__PKG__"
OUT_DIR = "__OUT_DIR__"

_out = {"ok": False, "pkg": PKG, "textures": []}
try:
    # Scope guards (audit F2): ue_exec does not reject an unsubstituted placeholder.
    _root = _os.path.normcase(_os.path.normpath(r"C:\Users\Admin\UE5LandscapePipeline")) + _os.sep
    _od = _os.path.normcase(_os.path.normpath(OUT_DIR))
    if not (_os.path.isabs(OUT_DIR) and _od.startswith(_root)):
        raise RuntimeError("OUT_DIR must be an absolute path inside the repo: " + OUT_DIR)
    if not PKG.startswith("/Game/"):
        raise RuntimeError("PKG must start with /Game/: " + PKG)
    import time as _time
    _t0 = _time.time()
    _p = _u.load_package(PKG)
    if _p is None:
        raise RuntimeError("load_package returned None for " + PKG)
    _os.makedirs(OUT_DIR, exist_ok=True)
    for _t in _u.ObjectIterator(_u.Texture2D):
        if not _t.get_path_name().startswith(PKG + "."):
            continue
        _rec = {"name": _t.get_name(), "path": _t.get_path_name(),
                "size": [_t.blueprint_get_size_x(), _t.blueprint_get_size_y()],
                "srgb": bool(_t.get_editor_property("srgb")),
                "compression": str(_t.get_editor_property("compression_settings"))}
        _fn = _os.path.join(OUT_DIR, _t.get_name() + ".png")
        _task = _u.AssetExportTask()
        _task.set_editor_property("object", _t)
        _task.set_editor_property("filename", _fn)
        _task.set_editor_property("automated", True)
        _task.set_editor_property("prompt", False)
        _task.set_editor_property("replace_identical", True)
        # No explicit exporter (audit F1): auto-selection by extension calls
        # SupportsObject, so an HDR-source texture fails cleanly, not check().
        _rec["exported"] = bool(_u.Exporter.run_asset_export_task(_task))
        _rec["file"] = _fn
        _rec["on_disk"] = _os.path.isfile(_fn) and _os.path.getmtime(_fn) >= _t0 - 1
        _rec["errors"] = [str(_x) for _x in (_task.get_editor_property("errors") or [])]
        _out["textures"].append(_rec)
    # Audit F3: this run's export must have succeeded AND written a fresh file.
    _out["ok"] = bool(_out["textures"]) and all(r["exported"] and r["on_disk"] for r in _out["textures"])
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1))
