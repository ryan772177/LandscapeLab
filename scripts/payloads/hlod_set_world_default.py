"""Set the WORLD-LEVEL default HLOD layer. One property, one package, zero of
the 2,796 external actor packages.

WHY THIS INSTEAD OF ASSIGNING ACTORS
    2026-09-07: assigning HLOD layers to ~2,796 actors put the editor into a
    sustained 5-6.6 core spin on the following save -- no log, no files, no DDC
    growth, reproduced twice. Engine source (REGISTER, CC 2026-09-08) shows the
    assignment is not required: `UWorldPartition::DefaultHLODLayer`
    (`WorldPartition.h:610-612`) is applied to every unassigned,
    spatially-loaded, HLOD-relevant actor at STREAMING GENERATION time by
    `ResolveHLODLayer` (`WorldPartitionStreamingGeneration.cpp:868-875`), via
    `SetRuntimeHLODLayer` (:549-553) which writes the streaming-generation VIEW,
    not the persisted actor desc. Nothing is written to `__ExternalActors__`.

THE ROUTE IS REFLECTED, NOT REMEMBERED (docs/ue58-api-protocol.md)
    Three routes were TRIED on 2026-09-08 and two are eliminated:

      * `unreal.GameplayStatics.get_world_settings` -- does NOT exist in 5.8.
        AttributeError.
      * `world.get_editor_property("persistent_level")` -- "Failed to find
        property 'persistent_level' ... on 'World'", even though
        `UWorld::PersistentLevel` IS `UPROPERTY(Transient)` at
        `World.h:952-953`. Being a UPROPERTY in C++ is NOT sufficient for the
        Python attribute to exist; the reflected surface is the contract.
      * `AWorldSettings` is ALSO absent from
        `EditorActorSubsystem.get_all_level_actors()` (0 hits of 3,269 actors).

    What works, printed by `hlod_route_discovery.py`:

        UWorld.get_world_settings()      a METHOD on World, not GameplayStatics
        AWorldSettings::WorldPartition   WorldSettings.h:550-551
                                         UPROPERTY(VisibleAnywhere, Instanced)
        UWorldPartition::DefaultHLODLayer
                                         WorldPartition.h:610-612
                                         UPROPERTY(EditAnywhere)

    NOTE `default_hlod_layer` does NOT appear in `dir(world_partition)` --
    `get_editor_property` reaches reflected properties that are not exposed as
    Python attributes, so an absence from `dir()` is not an absence from the
    contract. Every hop is checked and reported. A None hop ABORTS before
    mutating -- a half-applied chain is worse than an unapplied one.

WHAT WAS ALREADY THERE, AND IT CORRECTS A PRIOR CONCLUSION
    Measured 2026-09-08: `default_hlod_layer` was ALREADY
    `/Game/Alpine8K_HLODLayer_Instanced` before this payload ran. So the
    2026-09-07 conclusion -- "the layers were never ASSIGNED, and that is why
    nothing could build" -- is WRONG. Actors reading `hlod_layer: None` were
    inheriting the world default at generation time all along. "Never built"
    had a simpler cause: the build was never successfully run.
    The existing default is still the wrong layer for the job: INSTANCING, with
    `loading_range` 76800 cm = 768 m, INSIDE the ~1 km World Partition streaming
    range it is supposed to outlive, and parented to a `Merged` layer whose own
    range is SHORTER still (51200) and which is not spatially loaded.

STANDING RULE 12
    Declared, APPLIED, and READ BACK FROM THE ENGINE. The read-back re-resolves
    the whole chain from the world rather than reusing the object just written,
    because the latter proves only that the setter ran. It reads back twice:
    once after the set, once after the save.

DRY_RUN=1 reports the chain and the current value and mutates NOTHING.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_set_world_default.py \
        --set LAYER=/Game/Alpine8K_HLODLayer_Landscape --set DRY_RUN=1
"""
import json as _json
import time as _time

import unreal as _u

LAYER_PKG = "__LAYER__"
DRY_RUN = bool(int("__DRY_RUN__"))

_out = {"error": None, "dry_run": DRY_RUN, "layer_requested": LAYER_PKG,
        "chain": {}, "aborted": None}


def _resolve():
    """Re-walk the chain from the editor world. Returns (wp, ws) or (None, None)."""
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _ws = _w.get_world_settings()
    if _ws is None:
        return None, None, _w, "get_world_settings() returned None"
    _wp = _ws.get_editor_property("world_partition")
    if _wp is None:
        return None, _ws, _w, "world_partition is None (world is not partitioned?)"
    return _wp, _ws, _w, None


try:
    _wp, _ws, _w, _why = _resolve()
    _out["level_path"] = _w.get_path_name()
    _out["chain"] = {
        "world_settings": _ws.get_path_name() if _ws is not None else None,
        "world_settings_package": (_ws.get_package().get_name()
                                   if _ws is not None else None),
        "world_partition": _wp.get_path_name() if _wp is not None else None,
        "world_partition_class": (_wp.get_class().get_name()
                                  if _wp is not None else None),
    }
    if _wp is None:
        _out["aborted"] = _why or "chain incomplete"
    else:
        _before = _wp.get_editor_property("default_hlod_layer")
        _out["default_hlod_layer_BEFORE"] = (_before.get_path_name()
                                             if _before else None)
        # The reflected HLOD surface, so a later session picks the setter from
        # the contract rather than from this file.
        _out["wp_hlod_surface"] = sorted(
            _n for _n in dir(_wp) if "hlod" in _n.lower())

        _target = _u.load_asset(LAYER_PKG)
        _out["layer_loaded"] = _target.get_path_name() if _target else None
        if _target is None:
            _out["aborted"] = "layer asset did not load: " + LAYER_PKG
        elif DRY_RUN:
            _out["aborted"] = "DRY_RUN -- nothing mutated"
        else:
            _out["layer_type"] = str(_target.get_editor_property("layer_type"))
            _out["layer_cell_size"] = _target.get_editor_property("cell_size")
            _out["layer_loading_range"] = _target.get_editor_property(
                "loading_range")

            _t0 = _time.time()
            _wp.set_editor_property("default_hlod_layer", _target)
            _out["set_seconds"] = round(_time.time() - _t0, 3)

            # READ-BACK 1 -- re-resolved from the world, not the object written.
            _wp2, _ws2, _w2, _ = _resolve()
            _rb1 = (_wp2.get_editor_property("default_hlod_layer")
                    if _wp2 is not None else None)
            _out["default_hlod_layer_AFTER_SET"] = (_rb1.get_path_name()
                                                    if _rb1 else None)

            # ---- save exactly the package that holds it ---------------------
            # Named from the engine (`_ws.get_package()`), not assumed to be the
            # map package. `save_packages` on ONE named package, not the bulk
            # dirty-package API -- although 2026-09-07 established the bulk API
            # was NOT the spin's cause, a targeted save is still the smaller
            # claim and its cost is attributable.
            _pkg = _ws2.get_package() if _ws2 is not None else _ws.get_package()
            _pkg.set_dirty_flag(True)
            _out["package_saved"] = _pkg.get_name()
            _t1 = _time.time()
            _saved = _u.EditorLoadingAndSavingUtils.save_packages([_pkg], False)
            _out["save_seconds"] = round(_time.time() - _t1, 3)
            _out["save_returned"] = bool(_saved)

            # READ-BACK 2 -- after the save, chain re-resolved again.
            _wp3, _, _w3, _ = _resolve()
            _rb2 = (_wp3.get_editor_property("default_hlod_layer")
                    if _wp3 is not None else None)
            _out["default_hlod_layer_AFTER_SAVE"] = (_rb2.get_path_name()
                                                     if _rb2 else None)
            # Exact object-path compare, not startswith: a prefix match would
            # accept /Game/FooBar when /Game/Foo was requested.
            _out["readback_matches_request"] = bool(
                _rb2 is not None
                and _rb2.get_path_name() == _target.get_path_name())
            del _w2, _w3
    # A single consolidated verdict so the caller need not synthesise success
    # from scattered fields: a dry run succeeds if the chain resolved and the
    # target loaded; a real run only if BOTH the read-back matched and the save
    # returned true.
    if _out["error"]:
        _out["ok"] = False
    elif DRY_RUN:
        _out["ok"] = (_wp is not None
                      and _out.get("layer_loaded") is not None)
    else:
        _out["ok"] = bool(_out.get("readback_matches_request")
                          and _out.get("save_returned"))
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1500:]
    _out["ok"] = False

print("__LL__" + _json.dumps(_out))
