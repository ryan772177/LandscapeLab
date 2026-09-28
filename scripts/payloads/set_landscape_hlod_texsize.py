"""set_landscape_hlod_texsize.py -- R-HLODTEX. HLODTextureSize -> 4096.

RULED BY RYAN 2026-09-13. Applies to the Landscape actor AND all 256
LandscapeStreamingProxy actors. `HLODTextureSizePolicy` is NOT touched --
it stays SPECIFIC_SIZE, which is the 5.8 constructor default
(Landscape.cpp:1780-1783) and the only policy under which
`HLODTextureSize` is read at all
(LandscapeHLODBuilder.cpp:111-115, and the header's own EditCondition).

DERIVATION (recorded so the number is checkable, not chosen):
    cell 2000 m / (512 m / 1920 px) ~= 7,500 texels -> 8192 at the
    512 m hand-off; 4096 accepts a 1 km judgement distance for the far
    ground at about a quarter of the memory.

⛔ WHY EVERY PROXY AND NOT JUST THE PARENT. `HLODTextureSize` is marked
`LandscapeOverridable` (LandscapeProxy.h:962), so each proxy carries its
own value and a parent write does not propagate. Writing only the
Landscape actor would leave 256 proxies at 256 and produce a world whose
HLOD texture size depends on which proxy a cell drew from.

⭐ THIS WRITE CHANGES THE HLOD HASH. `ComputeHLODHash` hashes
`HLODTextureSize` whenever the policy is SpecificSize
(LandscapeHLODBuilder.cpp:109-115), so every landscape-bearing HLOD cell
becomes stale by this edit -- which is the intent, and is why the build
follows it.

Idempotent: an actor already at the target is left untouched and counted
separately, so a re-run reports 0 changed rather than 257 changed.
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

TARGET = 4096

_out = {"ok": False, "target": TARGET,
        "_policy": "HLODTextureSizePolicy deliberately NOT written; it is "
                   "already SPECIFIC_SIZE on all 257 (read 2026-09-13) and "
                   "is the only policy under which HLODTextureSize is read"}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape",
                                            "LandscapeStreamingProxy")]
    _out["n_landscape_actors"] = len(_ls)
    _out["n_by_class"] = dict(_Counter(_a.get_class().get_name()
                                       for _a in _ls))

    # ---- PREFLIGHT: refuse before touching anything ---------------------
    # Every actor must be readable AND on SPECIFIC_SIZE. A mixed-policy
    # world would take this write on some actors and silently ignore it
    # on the rest, which is worse than refusing.
    _pre = {"unreadable": [], "wrong_policy": []}
    for _a in _ls:
        try:
            _p = _a.get_editor_property("hlod_texture_size_policy")
            _a.get_editor_property("hlod_texture_size")
        except Exception as _e:
            _pre["unreadable"].append(_a.get_actor_label())
            continue
        if "SPECIFIC_SIZE" not in str(_p):
            _pre["wrong_policy"].append({"actor": _a.get_actor_label(),
                                         "policy": str(_p)})
    _out["preflight"] = {"n_unreadable": len(_pre["unreadable"]),
                         "n_wrong_policy": len(_pre["wrong_policy"]),
                         "unreadable": _pre["unreadable"][:10],
                         "wrong_policy": _pre["wrong_policy"][:10]}
    if _pre["unreadable"] or _pre["wrong_policy"]:
        _out["error"] = ("PREFLIGHT REFUSED: %d unreadable, %d not on "
                         "SPECIFIC_SIZE -- nothing written"
                         % (len(_pre["unreadable"]),
                            len(_pre["wrong_policy"])))
        print("__LL__" + _json.dumps(_out, indent=1, default=str))
        raise SystemExit(0)

    # ---- WRITE ----------------------------------------------------------
    _changed, _already, _failed = [], [], []
    for _a in _ls:
        _lbl = _a.get_actor_label()
        try:
            _cur = int(_a.get_editor_property("hlod_texture_size"))
            if _cur == TARGET:
                _already.append(_lbl)
                continue
            _a.modify()
            _a.set_editor_property("hlod_texture_size", TARGET)
            _changed.append(_lbl)
        except Exception as _e:
            _failed.append({"actor": _lbl,
                            "error": "%s: %s" % (type(_e).__name__, _e)})
    _out["n_changed"] = len(_changed)
    _out["n_already_at_target"] = len(_already)
    _out["n_failed"] = len(_failed)
    _out["failed"] = _failed[:10]

    # ---- SAVE -----------------------------------------------------------
    # These are World Partition external actors: each lives in its own
    # package, so saving the LEVEL is not enough.
    _saved = None
    try:
        _els = _u.EditorLoadingAndSavingUtils
        _dirty = [str(_p.get_name()) for _p in
                  (_els.get_dirty_content_packages() or [])]
        _dirty += [str(_p.get_name()) for _p in
                   (_els.get_dirty_map_packages() or [])]
        _out["dirty_before_save"] = len(_dirty)
        _saved = bool(_els.save_dirty_packages(True, True))
        _out["save_dirty_packages_returned"] = _saved
        _left = [str(_p.get_name()) for _p in
                 (_els.get_dirty_content_packages() or [])]
        _left += [str(_p.get_name()) for _p in
                  (_els.get_dirty_map_packages() or [])]
        # ⭐ THE RETURN VALUE IS NOT THE VERDICT. save_dirty_packages
        # reports that it ran; the dirty list afterwards reports whether
        # anything is still unsaved.
        _out["dirty_after_save"] = len(_left)
        _out["still_dirty_sample"] = _left[:10]
    except Exception as _e:
        _out["save_error"] = "%s: %s" % (type(_e).__name__, _e)

    # ---- READ BACK, from the actors, after the save ---------------------
    _dist = _Counter()
    _raised = 0
    _outliers = []
    for _a in _ls:
        try:
            _v = int(_a.get_editor_property("hlod_texture_size"))
        except Exception:
            _raised += 1
            continue
        _dist[_v] += 1
        if _v != TARGET:
            _outliers.append({"actor": _a.get_actor_label(),
                              "class": _a.get_class().get_name(),
                              "value": _v})
    _out["readback_distribution"] = dict(_dist)
    _out["readback_raised"] = _raised
    _out["readback_ok"] = sum(_dist.values())
    _out["outliers"] = _outliers
    _out["n_outliers"] = len(_outliers)
    _out["all_at_target"] = bool(_raised == 0 and not _outliers
                                 and sum(_dist.values()) == len(_ls))

    # Policy re-read, to prove it was NOT disturbed.
    _pol = _Counter()
    for _a in _ls:
        try:
            _pol[str(_a.get_editor_property("hlod_texture_size_policy"))] += 1
        except Exception:
            pass
    _out["policy_after"] = dict(_pol)

    # ---- HLOD CELL COUNT (actors, not proxies) --------------------------
    _hlod = [_a for _a in _actors
             if "WorldPartitionHLOD" in _a.get_class().get_name()]
    _out["n_hlod_actors_in_editor_world"] = len(_hlod)
    _out["_hlod_count_caveat"] = (
        "This counts HLOD actors LOADED in the editor world right now, "
        "which is not the same as every HLOD cell on disk -- World "
        "Partition streams them. The on-disk figure is 2,267 (the "
        "-SetupHLODs manifest, 2026-09-13).")
    _out["ok"] = True
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
