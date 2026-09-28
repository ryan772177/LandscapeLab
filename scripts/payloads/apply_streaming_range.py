"""Set the runtime grid loading ranges from the recipe (Brief 3 Task 0).

Layers are identified BY PROPERTY SIGNATURE (LoadingRange, CellSize) --
Name and HLODIndex are unreflected on this class ('protected' to the
accessor; measured 2026-09-10), and rule 8 prefers signatures over labels
for anything hard to reverse. EXPECTED signatures (read live before this
was written): main 25600/12800, instanced 51200/25600, merged
102400/51200. Any object that matches none, or two that match one,
REFUSES -- a range written to the wrong layer restreams the world wrongly
and nothing downstream says so.

EXACT-CASE property names: the class has no generated Python wrapper, so
'LoadingRange' works and 'loading_range' does not (measured).

The one-time-init proof (no SetupHLODs re-run needed):
WorldPartitionRuntimeHashSet.cpp:264-303 -- SetDefaultValues is
WITH_EDITOR and check(RuntimePartitions.IsEmpty()); :125-134 --
GetLoadingRange consults the stored property (plus the override cvar) at
streaming time. Streaming data regenerates each PIE start.

Saves the MAP package (the hash set lives inside WorldSettings) after
read-back, bounded to the dirty map list, then re-asks the dirty state.

Run via ue_exec with --set MAIN_CM= INST_CM= MERGED_CM=
"""
import json as _json
import traceback as _tb

import unreal as _u

MAIN_CM = int("__MAIN_CM__")
INST_CM = int("__INST_CM__")
MERGED_CM = int("__MERGED_CM__")

# (expected current LoadingRange, expected CellSize) -> role.
# Known HISTORICAL values are all listed -- the applier must recognise
# any state a prior ruling left the world in (25600 pristine; 76800 the
# 2026-09-10 768 m era that the perf gate RED'd back down).
_SIG = {(25600, 12800): "main", (76800, 12800): "main",
        (51200, 25600): "instanced",
        (102400, 51200): "merged"}
# already-applied signatures, so a re-run is idempotent rather than refused
_SIG_APPLIED = {(MAIN_CM, 12800): "main", (INST_CM, 25600): "instanced",
                (MERGED_CM, 51200): "merged"}
_TARGET = {"main": MAIN_CM, "instanced": INST_CM, "merged": MERGED_CM}

_out = {"ok": False, "layers": {}, "save": None}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _lvl = _w.get_path_name().split(".")[0]
    _out["level_path"] = _w.get_path_name()
    if _lvl != "/Game/Alpine8K":
        raise RuntimeError("LEVEL GATE: editor holds %r" % _lvl)

    _wp = _w.get_world_settings().get_editor_property("world_partition")
    _rh = _u.find_object(_wp, "WorldPartitionRuntimeHashSet_0")
    if _rh is None:
        raise RuntimeError("hash set subobject not found")

    _found = {}
    for _i in range(8):
        try:
            _o = _u.find_object(_rh, "RuntimePartitionLHGrid_%d" % _i)
        except Exception:
            _o = None
        if _o is None:
            continue
        _lr = int(_o.get_editor_property("LoadingRange"))
        _cs = int(_o.get_editor_property("CellSize"))
        _role = _SIG.get((_lr, _cs)) or _SIG_APPLIED.get((_lr, _cs))
        _row = {"path": _o.get_path_name(), "loading_range_before": _lr,
                "cell_size": _cs, "role": _role}
        if _role is None:
            raise RuntimeError(
                "layer %s has signature (%d, %d) matching NO known role "
                "-- refusing to write ranges into an unrecognised grid"
                % (_o.get_path_name(), _lr, _cs))
        if _role in _found:
            raise RuntimeError(
                "TWO layers match role %r -- ambiguous, refusing" % _role)
        _found[_role] = (_o, _row)

    _missing = [r for r in ("main", "instanced", "merged")
                if r not in _found]
    if _missing:
        raise RuntimeError("roles not found: %s" % _missing)

    for _role, (_o, _row) in _found.items():
        _o.modify()
        _o.set_editor_property("LoadingRange", _TARGET[_role])
        _row["loading_range_after"] = int(
            _o.get_editor_property("LoadingRange"))
        _row["applied"] = _row["loading_range_after"] == _TARGET[_role]
        _out["layers"][_role] = _row
    if not all(r["applied"] for r in _out["layers"].values()):
        raise RuntimeError("a read-back disagrees with the target")

    # Save the MAP package only (bounded): the hash set lives inside it.
    _dirty = list(_u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    _names = [p.get_name() for p in _dirty]
    _saved = bool(_u.EditorLoadingAndSavingUtils.save_packages(_dirty, True)) \
        if _dirty else None
    _after = [p.get_name() for p in
              _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _out["save"] = {"dirty_map_packages": _names, "saved": _saved,
                    "still_dirty_after": _after}
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-600:]

print("__LL__" + _json.dumps(_out))
