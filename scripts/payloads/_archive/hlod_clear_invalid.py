"""Clear `hlod_layer` back to None on actors pointing at an UNREGISTERED HLOD
layer, so they inherit the valid world default again.

WHY THESE ASSIGNMENTS ARE WORSE THAN NOTHING
    Under `UWorldPartitionRuntimeHashSet` a layer is valid only if a runtime
    partition registers it (`WorldPartitionRuntimeHashSet.cpp:377-380`).
    `Alpine8K_HLODLayer_FoliageApprox` and `Alpine8K_HLODLayer_Landscape` were
    created 2026-09-07 as standalone assets and are registered by nothing.

    An EXPLICIT `hlod_layer` overrides the world default. So the 25 actors
    carrying these two layers are the only actors in the world EXCLUDED from
    HLOD -- the 2,205 that were never touched inherit the valid default and
    build fine. The 2026-09-07 assignment did not merely fail to help; for
    these 25 it is subtractive.

    Measured on the 2026-09-08 `-SetupHLODs` run with the valid default:
        21  InstancedFoliageActor    -> Alpine8K_HLODLayer_FoliageApprox
         4  LandscapeStreamingProxy  -> Alpine8K_HLODLayer_Landscape
        25  "invalid HLOD layer" errors, exactly

SINGLE VARIABLE
    This clears the layer and nothing else. It does NOT delete the two layer
    assets -- they may yet be registered through the World Settings panel, and
    deleting them would conflate two changes. It does NOT touch any actor whose
    layer is None already or is one of the registered layers.

IDENTIFIED BY PROPERTY, NOT BY LABEL (standing rule 8)
    Actors are selected by reading `hlod_layer` and comparing the resolved
    path against the INVALID set. Labels collide in this project; object paths
    do not.

    DRY_RUN=1 reports what it would clear and writes nothing.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_clear_invalid.py --set DRY_RUN=1
"""
import json as _json
import time as _time

import unreal as _u

DRY_RUN = bool(int("__DRY_RUN__"))

# The two layers no runtime partition registers, established 2026-09-08 from
# the builder's own per-actor error output.
INVALID = (
    "/Game/Alpine8K_HLODLayer_FoliageApprox.Alpine8K_HLODLayer_FoliageApprox",
    "/Game/Alpine8K_HLODLayer_Landscape.Alpine8K_HLODLayer_Landscape",
)

_out = {"error": None, "dry_run": DRY_RUN, "invalid_layers": list(INVALID),
        "found": {}, "cleared": 0, "saved": 0, "failed": []}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()
    if _w.get_path_name().split(".")[0] != "/Game/Alpine8K":
        raise RuntimeError("LEVEL GATE: editor does not hold /Game/Alpine8K")

    _hits = []
    for _a in _eas.get_all_level_actors():
        try:
            _v = _a.get_editor_property("hlod_layer")
        except Exception:
            continue
        if _v is None:
            continue
        _p = _v.get_path_name()
        if _p not in INVALID:
            continue
        _cn = _a.get_class().get_name()
        _k = _cn + " -> " + _p.split("/")[-1]
        _out["found"][_k] = _out["found"].get(_k, 0) + 1
        _hits.append(_a)
    _out["found_total"] = len(_hits)

    if DRY_RUN:
        _out["verdict"] = "DRY_RUN -- nothing written"
    else:
        _pkgs = []
        for _a in _hits:
            try:
                _a.set_editor_property("hlod_layer", None)
                _out["cleared"] += 1
                _pkgs.append(_a.get_package())
            except Exception as _e:
                _out["failed"].append(_a.get_name() + ": " + type(_e).__name__)

        # Save one package at a time so an interruption leaves a partial result
        # AND a count, rather than an unknown state.
        _t0 = _time.time()
        _seen = set()
        for _p in _pkgs:
            _n = _p.get_name()
            if _n in _seen:
                continue
            _seen.add(_n)
            try:
                if _u.EditorLoadingAndSavingUtils.save_packages([_p], False):
                    _out["saved"] += 1
            except Exception as _e:
                _out["failed"].append(_n + ": " + type(_e).__name__)
        _out["save_seconds"] = round(_time.time() - _t0, 3)
        _out["packages_touched"] = len(_seen)

        # ---- READ BACK, by re-scanning the level, not by trusting the set ---
        _still = {}
        for _a in _eas.get_all_level_actors():
            try:
                _v = _a.get_editor_property("hlod_layer")
            except Exception:
                continue
            if _v is not None and _v.get_path_name() in INVALID:
                _cn = _a.get_class().get_name()
                _still[_cn] = _still.get(_cn, 0) + 1
        _out["still_invalid_after"] = _still
        _out["readback_clean"] = (not _still)
        _out["verdict"] = ("CLEARED -- no actor still points at an unregistered "
                           "layer" if not _still else
                           "INCOMPLETE -- some actors still invalid")
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["verdict"] = "COULD NOT LOOK"
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
