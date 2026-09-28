"""Create the HLOD layers Alpine8K needs and assign them. IDEMPOTENT.

MEASURED STARTING POSITION (hlod_probe.py, 2026-09-07): zero built HLOD
actors, and EVERY actor class reports `hlod_layer: None` -- Landscape,
LandscapeStreamingProxy (256), InstancedFoliageActor (1093), StaticMeshActor
(1446). Two layer assets exist for this world and nothing points at them.
That is why nothing has ever built: `SetupHLODActors` creates HLOD actors for
actors that HAVE a layer, and none did.

THE ASSIGNMENT, as ruled:
    foliage    -> MeshApproximate ("Approximated Mesh"), the voxel remesh that
                  produces the coloured-blob-at-the-right-coverage the
                  silhouette threshold asks for
    landscape  -> its own layer, so terrain HLOD is tuned and rebuilt
                  independently of foliage
    props      -> Instancing, parented to Merged (the existing chain)

EHLODLayerType values verified at HLODLayer.h:31-39.

A NOTE ON THE EXISTING CHAIN, NOT FIXED HERE: Alpine8K_HLODLayer_Instanced has
loading_range 76800 and its PARENT Merged has 51200. A parent HLOD level should
outlive its child; here the parent unloads FIRST, which is backwards. Recorded
rather than silently corrected -- changing it changes what every future build
produces, and it deserves its own measurement.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_setup_layers.py
"""
import json as _json
import time as _time

import unreal as _u

PKG = "/Game"
FOLIAGE_LAYER = "Alpine8K_HLODLayer_FoliageApprox"
LANDSCAPE_LAYER = "Alpine8K_HLODLayer_Landscape"
PROPS_LAYER = "/Game/Alpine8K_HLODLayer_Instanced.Alpine8K_HLODLayer_Instanced"

# BOUNDED ASSIGNMENT, and this bound is the whole point.
# 2026-09-07: assigning all 2,796 actors in one operation succeeded in 33.8 s
# and then the SAVE never completed -- 90 minutes at ~5 cores with no log
# output, no files written and no DDC growth, killed without ever learning why.
# "One cell first" applies to the whole chain that reaches the build, not just
# to the step with "build" in its name, and a pilot that skips the setup is not
# a pilot. CENTRE_CM/RADIUS_M restrict the assignment AND the per-package save
# (both happen here, each save timed) so the SAVE COST PER PACKAGE is measured
# on a handful before it is spent on thousands. RADIUS_M <= 0 means the whole
# world and is REFUSED until that cost is known.
CENTRE_CM = __CENTRE_CM__
RADIUS_M = __RADIUS_M__
# DRY_RUN=1 previews what WOULD be assigned/saved without mutating a single actor
# (rule 8: a bounded, irreversible bulk op gets a dry run first). The first live
# use of the save path -- which has never actually run -- should be DRY_RUN=1.
DRY_RUN = bool(int("__DRY_RUN__"))

# 256 m cells, matching the existing layers, so all three chains agree about
# what a cell is. Loading range is the distance the HLOD stays resident to;
# 2 km puts the blob band inside it where the mesh cull cannot reach.
CELL_SIZE = 25600
LOADING_RANGE = 200000.0

_out = {"ok": False, "error": None, "created": [], "assigned": {}}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _tools = _u.AssetToolsHelpers.get_asset_tools()

    def _layer(name, layer_type, spatially_loaded, loading_range):
        path = PKG + "/" + name + "." + name
        if _u.EditorAssetLibrary.does_asset_exist(PKG + "/" + name):
            obj = _u.load_asset(path)
            action = "existing"
        else:
            obj = _tools.create_asset(name, PKG, _u.HLODLayer, None)
            action = "created"
        obj.set_editor_property("layer_type", layer_type)
        obj.set_editor_property("cell_size", CELL_SIZE)
        obj.set_editor_property("loading_range", loading_range)
        obj.set_editor_property("is_spatially_loaded", spatially_loaded)
        # F3: the save return is the on-disk evidence; the read-back below uses
        # load_asset, which returns the RESIDENT in-memory object, not a disk
        # round-trip -- so it confirms the setters took, not that they persisted.
        saved = bool(_u.EditorAssetLibrary.save_asset(PKG + "/" + name))
        rb = _u.load_asset(path)
        _out["created"].append({
            "name": name, "action": action,
            "saved": saved,
            "layer_type_readback": str(rb.get_editor_property("layer_type")),
            "cell_size_readback": rb.get_editor_property("cell_size"),
            "loading_range_readback": rb.get_editor_property("loading_range"),
            "is_spatially_loaded_readback": bool(
                rb.get_editor_property("is_spatially_loaded")),
        })
        if not saved:
            raise RuntimeError("save_asset returned False for HLOD layer " + name)
        return rb

    _fol = _layer(FOLIAGE_LAYER, _u.HLODLayerType.MESH_APPROXIMATE, True, LOADING_RANGE)
    _lnd = _layer(LANDSCAPE_LAYER, _u.HLODLayerType.MESH_MERGE, True, LOADING_RANGE)
    _props = _u.load_asset(PROPS_LAYER)
    # F5: load_asset returns None for a missing asset; assigning None to every
    # StaticMeshActor would CLEAR their layer, silently, so refuse instead.
    if _props is None:
        raise RuntimeError("props HLOD layer not found: " + PROPS_LAYER +
                           " -- refusing (assigning None would clear the layer "
                           "on every StaticMeshActor)")

    # ---- assign, bounded -------------------------------------------------
    # F6: RADIUS_M <= 0 is the whole world, whose save cost is exactly what is
    # NOT yet known (docstring). Refuse it here rather than let a "pilot" become
    # the 2,796-actor run that hung for 90 minutes on 2026-09-07.
    if float(RADIUS_M) <= 0:
        raise RuntimeError(
            "RADIUS_M <= 0 requests the WHOLE WORLD; this pilot exists to bound "
            "the per-package save cost first. Use a small RADIUS_M (a few cells).")
    _r_cm = float(RADIUS_M) * 100.0
    _cx, _cy = float(CENTRE_CM[0]), float(CENTRE_CM[1])
    _out["dry_run"] = DRY_RUN
    _out["bound"] = {"centre_cm": [_cx, _cy], "radius_m": RADIUS_M}

    def _in_bound(_actor):
        _p = _actor.get_actor_location()
        return ((_p.x - _cx) ** 2 + (_p.y - _cy) ** 2) <= (_r_cm * _r_cm)

    # F7: "already assigned" (a legitimate idempotent skip) and "errored" are
    # different outcomes -- the first version counted both as "skipped", which
    # hid failures as no-ops. They are separated, and the errors kept.
    _n = {"foliage": 0, "landscape": 0, "props": 0,
          "already": 0, "out_of_bound": 0, "errors": 0}
    _errors = []
    _candidates = 0     # matched a target class AND fell inside the bound
    _touched = []
    for _a in _eas.get_all_level_actors():
        _tgt = None
        if isinstance(_a, _u.InstancedFoliageActor):
            _tgt, _k = _fol, "foliage"
        elif isinstance(_a, (_u.LandscapeStreamingProxy, _u.Landscape)):
            _tgt, _k = _lnd, "landscape"
        elif isinstance(_a, _u.StaticMeshActor):
            _tgt, _k = _props, "props"
        if _tgt is None:
            continue
        try:
            if not _in_bound(_a):
                _n["out_of_bound"] += 1
                continue
        except Exception as _be:
            _n["errors"] += 1
            _errors.append({"label": str(_a.get_actor_label()),
                            "phase": "in_bound", "error": type(_be).__name__})
            continue
        _candidates += 1
        try:
            _cur = _a.get_editor_property("hlod_layer")
            if _cur is not None and _cur.get_path_name() == _tgt.get_path_name():
                _n["already"] += 1
                continue
            if not DRY_RUN:
                _a.set_editor_property("hlod_layer", _tgt)
            _n[_k] += 1
            _touched.append(_a)
        except Exception as _ae:
            _n["errors"] += 1
            _errors.append({"label": str(_a.get_actor_label()),
                            "phase": "assign", "error": type(_ae).__name__})
    _out["assigned"] = _n
    _out["errors_detail"] = _errors
    _out["candidates_in_bound"] = _candidates

    # F4/NN13: a pilot that found no target-class actor inside its bound MEASURED
    # NOTHING; do not report success over an empty sample.
    if _candidates == 0:
        _out["refused"] = ("no target-class actor fell inside the bound "
                           "(centre %r, radius %s m) -- nothing to assign or "
                           "measure" % ([_cx, _cy], RADIUS_M))
        raise RuntimeError(_out["refused"])

    # ---- SAVE, per package, timed -- THE POINT OF THE PILOT ---------------
    # F1: assignment without a save persists NOTHING and measures nothing -- the
    # docstring's whole rationale is the per-package SAVE cost. Save one package
    # at a time (save_dirty.py: the BULK call is what hung the whole-world run),
    # capturing each return and its wall time.
    _saves = []
    if not DRY_RUN:
        for _a in _touched:
            _pkg = _a.get_package()
            _t0 = _time.perf_counter()
            try:
                _ok_s = bool(_u.EditorLoadingAndSavingUtils.save_packages(
                    [_pkg], False))
                _err = None
            except Exception as _se:
                _ok_s, _err = False, type(_se).__name__ + ": " + str(_se)
            _dt = _time.perf_counter() - _t0
            _saves.append({"label": str(_a.get_actor_label()),
                           "package": _pkg.get_name(),
                           "saved": _ok_s, "seconds": round(_dt, 3),
                           "error": _err})
    _saved_ok = sum(1 for _s in _saves if _s["saved"])
    _out["saves"] = _saves
    _out["save_summary"] = {
        "packages": len(_saves), "saved_ok": _saved_ok,
        "failed": len(_saves) - _saved_ok,
        "total_seconds": round(sum(_s["seconds"] for _s in _saves), 3),
        "max_seconds": (round(max(_s["seconds"] for _s in _saves), 3)
                        if _saves else 0.0),
    }
    # rule 12: an assignment that did not persist is transient -- the next editor
    # load will not see it. Every touched package must have saved.
    if not DRY_RUN and _touched and _saved_ok != len(_touched):
        raise RuntimeError(
            "%d of %d assigned actor packages failed to save; the assignment is "
            "NOT persisted" % (len(_touched) - _saved_ok, len(_touched)))

    # ---- READ BACK, from the actors that were actually ASSIGNED ----------
    # The first version sampled the first actor of each class regardless of
    # whether it was inside the bound, so on a bounded run it read unassigned
    # actors and reported null for everything -- a read-back that proves
    # nothing, which under standing rule 12 is the same as having none. This is
    # the in-memory value; save_summary is the disk evidence.
    _rb = {}
    for _a in _touched:
        _cn = _a.get_class().get_name()
        if _cn in _rb:
            continue
        try:
            _v = _a.get_editor_property("hlod_layer")
            _rb[_cn] = _v.get_path_name().split("/")[-1] if _v else None
        except Exception as _e2:
            _rb[_cn] = "ERR " + type(_e2).__name__
    _out["hlod_layer_readback_by_class"] = _rb
    _out["_readback_scope"] = ("in-memory value on the actors this run ASSIGNED "
                               "(not the first of each class); save_summary is "
                               "the disk evidence")
    _out["ok"] = True
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
