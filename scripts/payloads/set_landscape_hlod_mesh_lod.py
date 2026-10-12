"""set_landscape_hlod_mesh_lod -- HLOD mesh source LOD for the landscape cells (2026-10-05).

Sets HLODMeshSourceLODPolicy = SPECIFIC_LOD and HLODMeshSourceLOD = TARGET_LOD on the
Landscape actor AND all 256 LandscapeStreamingProxy actors, saves, reads back.

WHY. Every landscape HLOD cell was built from LowestDetailLOD (LOD6 on this 127-quad
component: 127 m quads, 32 triangles per 508 m cell) with the Nanite skirt the builder
always adds (LandscapeHLODBuilder.cpp:351-359), one LOD quad deep x Z scale 500 = 635 m.
The far field reads faceted, and where the coarse surface misses the real terrain the
skirts show as straight black wedges (research/hlod_seams/FINDINGS.md; A/B seams01).
At LOD2: 4.1 m quads, 20.5 m skirt.

Both properties are LandscapeOverridable (LandscapeProxy.h:969-975): each proxy carries
its own value, so every proxy is written, as R-HLODTEX does for the texture size.
Both are hashed by ComputeHLODHash (LandscapeHLODBuilder.cpp:117-121), so the 256
landscape cells become stale by this write -- the intent; rebuild them by date.
AutomaticLOD is NOT used: its bounds radius is scaled by the Z scale 500 (:183) and
would most likely select LOD0.

Idempotent; preflight refuses before writing if any actor is unreadable.
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

TARGET_LOD = 2
_POL = _u.LandscapeHLODMeshSourceLODPolicy.SPECIFIC_LOD

_out = {"ok": False, "target_lod": TARGET_LOD, "target_policy": str(_POL)}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape", "LandscapeStreamingProxy")]
    _out["n_landscape_actors"] = len(_ls)
    _out["n_by_class"] = dict(_Counter(_a.get_class().get_name() for _a in _ls))
    # Exact class split, not a total (audit F3; standing rule 8 -- this project
    # once had two landscapes).
    if _out["n_by_class"] != {"Landscape": 1, "LandscapeStreamingProxy": 256}:
        raise RuntimeError("expected 1 Landscape + 256 LandscapeStreamingProxy, found %r"
                           % _out["n_by_class"])

    # Pre-write dirty census (audit F2): save_dirty_packages below saves EVERY
    # dirty package, so anything already dirty would ride along unseen.
    _els = _u.EditorLoadingAndSavingUtils
    _pre_dirty = [str(_p.get_name()) for _p in (_els.get_dirty_content_packages() or [])]
    _pre_dirty += [str(_p.get_name()) for _p in (_els.get_dirty_map_packages() or [])]
    if _pre_dirty:
        _out["error"] = "PREFLIGHT REFUSED: %d package(s) already dirty -- nothing written" % len(_pre_dirty)
        _out["pre_dirty"] = _pre_dirty[:20]
        print("__LL__" + _json.dumps(_out, indent=1, default=str))
        raise SystemExit(0)

    # The builder CLAMPS the source LOD to the LOD count, which MaxLODLevel caps
    # (LandscapeHLODBuilder.cpp:198, Landscape.cpp:2005-2008): a property read-back
    # of 2 would not prove the build uses 2 (audit F1, rule 12). Refuse if any
    # actor's max_lod_level is set and below the target.
    _mll = _Counter()
    _mll_bad = []
    for _a in _ls:
        _v = int(_a.get_editor_property("max_lod_level"))
        _mll[_v] += 1
        if _v != -1 and _v < TARGET_LOD:
            _mll_bad.append({"actor": _a.get_actor_label(), "max_lod_level": _v})
    _out["max_lod_level_distribution"] = dict(_mll)
    _out["_upper_bound_note"] = ("valid LODs 0..6 rest on SubsectionSizeQuads 127 (spec), which Python "
                                 "cannot read (no edit flag, LandscapeProxy.h:926-927)")
    if _mll_bad:
        _out["error"] = "PREFLIGHT REFUSED: max_lod_level below target on %d actor(s)" % len(_mll_bad)
        _out["max_lod_level_bad"] = _mll_bad[:10]
        print("__LL__" + _json.dumps(_out, indent=1, default=str))
        raise SystemExit(0)

    _unread = []
    _before = _Counter()
    for _a in _ls:
        try:
            _before[(str(_a.get_editor_property("hlod_mesh_source_lod_policy")),
                     int(_a.get_editor_property("hlod_mesh_source_lod")))] += 1
        except Exception:
            _unread.append(_a.get_actor_label())
    _out["before"] = {"%s / %d" % k: v for k, v in _before.items()}
    if _unread:
        _out["error"] = "PREFLIGHT REFUSED: %d unreadable -- nothing written" % len(_unread)
        _out["unreadable"] = _unread[:10]
        print("__LL__" + _json.dumps(_out, indent=1, default=str))
        raise SystemExit(0)

    _changed, _already, _failed = [], [], []
    for _a in _ls:
        _lbl = _a.get_actor_label()
        try:
            if (_a.get_editor_property("hlod_mesh_source_lod_policy") == _POL
                    and int(_a.get_editor_property("hlod_mesh_source_lod")) == TARGET_LOD):
                _already.append(_lbl)
                continue
            _a.modify()
            _a.set_editor_property("hlod_mesh_source_lod_policy", _POL)
            _a.set_editor_property("hlod_mesh_source_lod", TARGET_LOD)
            _changed.append(_lbl)
        except Exception as _e:
            _failed.append({"actor": _lbl, "error": "%s: %s" % (type(_e).__name__, _e)})
    _out["n_changed"] = len(_changed)
    _out["n_already_at_target"] = len(_already)
    _out["n_failed"] = len(_failed)
    _out["failed"] = _failed[:10]

    _dirty = [str(_p.get_name()) for _p in (_els.get_dirty_content_packages() or [])]
    _dirty += [str(_p.get_name()) for _p in (_els.get_dirty_map_packages() or [])]
    _out["dirty_before_save"] = len(_dirty)
    _out["saved_packages"] = _dirty
    _out["save_dirty_packages_returned"] = bool(_els.save_dirty_packages(True, True))
    _left = [str(_p.get_name()) for _p in (_els.get_dirty_content_packages() or [])]
    _left += [str(_p.get_name()) for _p in (_els.get_dirty_map_packages() or [])]
    _out["dirty_after_save"] = len(_left)
    _out["still_dirty_sample"] = _left[:10]

    _after = _Counter()
    for _a in _ls:
        _after[(str(_a.get_editor_property("hlod_mesh_source_lod_policy")),
                int(_a.get_editor_property("hlod_mesh_source_lod")))] += 1
    _out["readback"] = {"%s / %d" % k: v for k, v in _after.items()}
    _out["all_at_target"] = (_after.get((str(_POL), TARGET_LOD), 0) == len(_ls))
    _out["ok"] = bool(_out["all_at_target"] and not _failed and not _left)
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
