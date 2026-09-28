"""READ-ONLY: the runtime grid's CELL SIZE and LOADING RANGE, from the WORLD.

WHY THIS EXISTS
    Residency was declared, not derived: `benchmark.json` carried
    `expect_landscape_components: 1024` for the whole world and later `16`
    within 600 m, both typed by hand. Ruled 2026-09-09: the player instrument's
    expectation must be COMPUTED from the grid the world actually runs, so it
    cannot drift from the engine's own streaming behaviour.

    This world uses `UWorldPartitionRuntimeHashSet`, NOT the spatial hash.
    `bench_grid_probe.py` asks whether any `ASpatialHashRuntimeGridInfo` actors
    exist and concludes "MainGrid" from their absence -- correct reasoning for a
    SpatialHash world and aimed at nothing here. REGISTER flagged that as a
    possible mis-aim for the failed force-load lever 2; this payload reads the
    class first and then the fields that class actually has.

REFLECTED CHAIN, every name from the header rather than from memory
    UWorldSettings.world_partition            WorldPartition.h:556 (RuntimeHash)
    UWorldPartition.runtime_hash
    UWorldPartitionRuntimeHashSet.runtime_partitions
                                              WorldPartitionRuntimeHashSet.h:262
    FRuntimePartitionDesc.name / main_layer   :71-85
        NOTE `class` is UE_DEPRECATED(5.8) and replaced by `main_layer` (:75-81)
    URuntimePartition.loading_range           RuntimePartition.h:103-104
    URuntimePartitionLHGrid.cell_size         RuntimePartitionLHGrid.h:57
    URuntimePartitionLHGrid.origin            RuntimePartitionLHGrid.h:60
        both are WITH_EDITORONLY_DATA, which is fine -- this runs in the editor

    `cell_size` exists ONLY on the LHGrid subclass. A partition of another
    class (Persistent, LevelStreaming) has no cell size at all, and this
    reports that rather than substituting a default.

Run: python scripts/ue_exec.py scripts/payloads/bench_grid_derive.py
"""
import json as _json

import unreal as _u

_out = {"error": None, "partitions": []}


def _path(o):
    try:
        return o.get_path_name() if o is not None else None
    except Exception:
        return "<unreadable>"


def _prop(o, name):
    """Each read is its own try/except: this editor answers in 60-180 s and one
    missing field must not cost the whole round trip (the IntPoint lesson)."""
    try:
        return o.get_editor_property(name)
    except Exception as e:
        return "ERR:%s: %s" % (type(e).__name__, e)


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    _wp = _w.get_world_settings().get_editor_property("world_partition")
    _out["world_partition"] = _path(_wp)

    # `runtime_hash` is NOT reachable by get_editor_property or attribute:
    # WorldPartition.h:555-556 declares it as a bare UPROPERTY() with no
    # EditAnywhere/BlueprintReadOnly, so it is reflected for serialisation and
    # absent from the editor-property surface. Measured 2026-09-09, both routes
    # refused. find_object on the sub-object DOES reach it.
    _rh = None
    for _cand in ("WorldPartitionRuntimeHashSet_0", "WorldPartitionRuntimeSpatialHash_0"):
        try:
            _rh = _u.find_object(_wp, _cand)
        except Exception:
            _rh = None
        if _rh is not None:
            _out["runtime_hash_route"] = "find_object(%s)" % _cand
            break
    _out["runtime_hash"] = _path(_rh)
    _out["runtime_hash_class"] = (_rh.get_class().get_name()
                                  if hasattr(_rh, "get_class") else str(_rh))

    _rps = _prop(_rh, "runtime_partitions") if hasattr(_rh, "get_class") else None
    if isinstance(_rps, str):
        _out["runtime_partitions_error"] = _rps
        _rps = None

    for _rp in (_rps or []):
        _row = {}
        _row["name"] = str(_prop(_rp, "name"))
        _ml = _prop(_rp, "main_layer")
        _row["main_layer"] = _path(_ml)
        _row["main_layer_class"] = (_ml.get_class().get_name()
                                    if hasattr(_ml, "get_class") else str(_ml))
        if hasattr(_ml, "get_class"):
            _lr = _prop(_ml, "loading_range")
            _row["loading_range_cm"] = _lr
            _cs = _prop(_ml, "cell_size")
            _row["cell_size_cm"] = _cs
            _og = _prop(_ml, "origin")
            try:
                _row["origin_cm"] = [float(_og.x), float(_og.y), float(_og.z)]
            except Exception:
                _row["origin_cm"] = str(_og)
        # HLOD setups (added 2026-09-10, ruling 5): each carries its OWN
        # partition layer with its OWN loading range -- these are the outer
        # rungs of the streaming ladder. Names from
        # WorldPartitionRuntimeHashSet.h:27-51 (FRuntimePartitionHLODSetup:
        # Name, PartitionLayer, bIsSpatiallyLoaded) read on 2026-09-10.
        _hs = _prop(_rp, "hlod_setups")
        if isinstance(_hs, str):
            _row["hlod_setups_error"] = _hs
        else:
            _row["hlod_setups"] = []
            for _s in (_hs or []):
                _srow = {"name": str(_prop(_s, "name"))}
                # AUDIT 2026-09-10 F5: _prop returns an error STRING on
                # failure and never raises; bool() of that string would
                # record a failed read as a confident True.
                _sv = _prop(_s, "is_spatially_loaded")
                if isinstance(_sv, str):
                    _srow["is_spatially_loaded_error"] = _sv
                else:
                    _srow["is_spatially_loaded"] = bool(_sv)
                _pl = _prop(_s, "partition_layer")
                if hasattr(_pl, "get_class"):
                    _srow["layer_class"] = _pl.get_class().get_name()
                    _srow["loading_range_cm"] = _prop(_pl, "loading_range")
                    _srow["cell_size_cm"] = _prop(_pl, "cell_size")
                else:
                    _srow["partition_layer"] = str(_pl)
                _row["hlod_setups"].append(_srow)
        _out["partitions"].append(_row)

    # PENDING: the engine's own answer, not a count derived here.
    # UWorldPartitionSubsystem::IsAllStreamingCompleted is
    # UFUNCTION(BlueprintCallable) at WorldPartitionSubsystem.h:95-96, but it is
    # a UWorldSubsystem -- get_editor_subsystem REFUSES it ("allowed Class
    # type: EditorSubsystem") and unreal.SubsystemBlueprintLibrary does not
    # exist in Python. Trying instance routes and reporting which answers.
    _subs = {}

    def _sub(label, fn):
        try:
            v = fn()
            _subs[label] = ("ok:%s" % v) if v is not None else "ok:None"
        except Exception as e:
            _subs[label] = "ERR:%s: %s" % (type(e).__name__, str(e)[:120])

    _sub("world.get_subsystem",
         lambda: _w.get_subsystem(_u.WorldPartitionSubsystem)
         .is_all_streaming_completed())
    _sub("GameplayStatics",
         lambda: _u.GameplayStatics.get_game_instance(_w))
    _sub("WorldPartitionBlueprintLibrary.get_runtime_world_bounds",
         lambda: str(_u.WorldPartitionBlueprintLibrary
                     .get_runtime_world_bounds())[:120])
    _out["pending_routes"] = _subs

    # THE PARTITION NAME, which is the key the loading-range override uses.
    # FRuntimePartitionStreamingData::GetLoadingRange (WorldPartitionRuntime
    # HashSet.cpp:125-135) consults UWorldPartitionSubsystem::GetOverride
    # LoadingRange(Name, ...) and returns the override when one is set -- so
    # `wp.Runtime.OverrideRuntimeLoadingRange -grid=<Name>` DOES work on a
    # HashSet world, keyed on the PARTITION name and not on a SpatialHash grid
    # name. That name is unreachable through runtime_partitions (private), but
    # every actor carries the grid it was assigned to in the reflected
    # AActor.runtime_grid, so the set of names is recoverable from the actors.
    _grids = {}
    try:
        _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
        _all = _eas.get_all_level_actors()
        _out["actors_sampled"] = len(_all)
        for _a in _all:
            try:
                _g = str(_a.get_editor_property("runtime_grid"))
            except Exception:
                _g = "<unreadable>"
            _k = _g if _g else "<empty=default main partition>"
            _grids[_k] = _grids.get(_k, 0) + 1
    except Exception as e:
        _out["runtime_grid_error"] = "%s: %s" % (type(e).__name__, e)
    _out["runtime_grids_on_actors"] = _grids

except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = _tb.format_exc()[-800:]

print("__LL__" + _json.dumps(_out))
