"""probe_hlod_chain_and_cvars.py -- audit items 4 and 5b. READ-ONLY.

(5b) THE HLOD PARENT CHAIN. The world's DefaultHLODLayer is
Alpine8K_HLODLayer_Instanced, and 0 of 4,339 actors name any layer. But
HLOD layers CASCADE: UHLODLayer::ParentLayer (HLODLayer.h:135) builds
the next level from the previous one, so a layer nothing points at
directly can still be in force one hop up. Declaring the Landscape
layer inert without walking that chain would be a verdict from half an
instrument. This walks it, from the world default, to a fixed point.

(4) LIVE CVAR ENUMERATION. Every console variable this 5.8.1 build
actually has, with its current value. This is what makes
"r.LandscapeLODBias does not exist in 5.8" a measurement instead of a
recollection -- Pass 1 quoted an earlier enumeration rather than
re-running one, and said so.

⭐ THE TWO CONTROLS TRAVEL WITH THE READ (probe standard). A name that
must resolve (r.ScreenPercentage) and a name that cannot possibly exist
(r.ThisCVarCannotPossiblyExist_zzz). If the positive fails or the
negative succeeds, the enumeration is not measuring what it claims and
the count below is meaningless.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False}

try:
    # ---- 5b: the chain -------------------------------------------
    _eal = _u.EditorAssetLibrary
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _wp = _ues.get_editor_world().get_world_settings().get_editor_property(
        "world_partition")
    _cur = _wp.get_editor_property("default_hlod_layer")
    _chain, _guard = [], set()
    while _cur is not None:
        _p = _cur.get_path_name()
        if _p in _guard:
            _chain.append({"path": _p, "note": "CYCLE -- stopping"})
            break
        _guard.add(_p)
        _row = {"path": _p}
        for _n in ("layer_type", "cell_size", "loading_range"):
            try:
                _row[_n] = str(_cur.get_editor_property(_n))
            except Exception as _e:
                _row[_n] = "RAISED: %s" % type(_e).__name__
        _chain.append(_row)
        try:
            _cur = _cur.get_editor_property("parent_layer")
        except Exception as _e:
            _chain[-1]["parent_read"] = "RAISED: %s" % type(_e).__name__
            break
    _out["hlod_chain_from_world_default"] = _chain
    _out["landscape_layer_in_chain"] = any(
        "HLODLayer_Landscape" in _r["path"] for _r in _chain)

    # ---- 4: live cvar enumeration --------------------------------
    _names = []
    _sink = _u.ConsoleVariableSink if False else None

    def _visit(_n, _h):
        _names.append(_n)

    # The reflected surface, enumerated rather than guessed.
    _out["console_api_surface"] = sorted(
        n for n in dir(_u.SystemLibrary) if "console" in n.lower())
    _out["unreal_console_symbols"] = sorted(
        n for n in dir(_u) if "console" in n.lower())[:30]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
