"""Force-load every World Partition region in the EDITOR world, then census.

This is the project's own loader (R-FRAMECOST, 2026-08-12), not a new one.
`LandscapeLabTools.load_all_world_partition_regions()` builds an
FLoaderAdapterShape over the editor world bounds and loads it -- the same shape
the editor's own region tool uses.

WHY THE EDITOR AND NOT PIE. MRQ renders in PIE, and PIE DUPLICATES the editor
world (`UWorldPartition::PostDuplicatePIE` in the log). Actors loaded in the
editor are therefore present to be duplicated. The runtime path --
`wp.Runtime.OverrideRuntimeLoadingRange` -- was tried first and moved residency
not at all (12/1024 before, 12/1024 after, with the command confirmed executing
in the log), so this is the second instrument, not the first guess.

RETURN ORDER IS (success, min, max, error). R-FRAMECOST documented
(min, max, success, error) until 2026-09-06; unpacking that way puts a Vector
where the bool belongs and a Vector is truthy, so a failed load would read as a
successful one.

Run via: python scripts/ue_exec.py scripts/payloads/bench_load_regions.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _ok, _mn, _mx, _err = _u.LandscapeLabTools.load_all_world_partition_regions()
    _out["load_ok"] = bool(_ok)
    _out["load_error"] = _err or None
    _out["bounds_cm"] = [[float(_mn.x), float(_mn.y)], [float(_mx.x), float(_mx.y)]]

    _c = {"landscape_actors": 0, "proxies": 0, "components": 0,
          "components_unreadable": 0, "foliage_actors": 0, "foliage_instances": 0}
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    for _a in _eas.get_all_level_actors():
        if isinstance(_a, _u.LandscapeStreamingProxy):
            _c["proxies"] += 1
        elif isinstance(_a, _u.Landscape):
            _c["landscape_actors"] += 1
        elif isinstance(_a, _u.InstancedFoliageActor):
            _c["foliage_actors"] += 1
            for _h in _a.get_components_by_class(
                    _u.HierarchicalInstancedStaticMeshComponent):
                try:
                    _c["foliage_instances"] += int(_h.get_instance_count())
                except Exception:
                    pass
            continue
        else:
            continue
        try:
            _k = _a.get_components_by_class(_u.LandscapeComponent)
        except Exception:
            _c["components_unreadable"] += 1
            continue
        if _k is None:
            _c["components_unreadable"] += 1
        else:
            _c["components"] += len(_k)
    _out["editor_census"] = _c
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out))
