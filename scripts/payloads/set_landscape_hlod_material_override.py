"""set_landscape_hlod_material_override -- HLODMaterialOverride on the landscape (2026-10-06).

Sets ALandscapeProxy.HLODMaterialOverride (LandscapeProxy.h:965-967, LandscapeOverridable)
= MATERIAL on the Landscape actor and all 256 LandscapeStreamingProxy actors, saves, reads
back. With an override the landscape HLOD builder skips the texture bake
(LandscapeHLODBuilder.cpp:382-385) -- the bake that leaves the black cell-edge strip
(LESSONS 2026-10-06e). Hashed (:72-75): the 256 landscape cells go stale, rebuild by date.
Ryan chose this fix 2026-10-06. Same guards as set_landscape_hlod_mesh_lod (audited):
exact 1+256 split, pre-write dirty census, idempotent, saved-package list, read-back.
    MATERIAL = object path of the override material, refused unless it loads
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

MATERIAL = "__MATERIAL__"

_out = {"ok": False, "material": MATERIAL}

try:
    _m = _u.EditorAssetLibrary.load_asset(MATERIAL)
    if _m is None or not isinstance(_m, _u.MaterialInterface):
        raise RuntimeError("override material does not load as a MaterialInterface: " + MATERIAL)
    # The landscape HLOD meshes are Nanite (LandscapeHLODBuilder.cpp:325, 372): refuse a
    # material whose base lacks the Nanite usage flag (audit F4).
    if not bool(_m.get_base_material().get_editor_property("used_with_nanite")):
        raise RuntimeError("override material's base material is not used_with_nanite")
    _want = _m.get_path_name()
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape", "LandscapeStreamingProxy")]
    _out["n_by_class"] = dict(_Counter(_a.get_class().get_name() for _a in _ls))
    if _out["n_by_class"] != {"Landscape": 1, "LandscapeStreamingProxy": 256}:
        raise RuntimeError("expected 1 Landscape + 256 LandscapeStreamingProxy, found %r"
                           % _out["n_by_class"])

    _els = _u.EditorLoadingAndSavingUtils
    _pre = [str(_p.get_name()) for _p in (_els.get_dirty_content_packages() or [])]
    _pre += [str(_p.get_name()) for _p in (_els.get_dirty_map_packages() or [])]
    if _pre:
        _out["error"] = "PREFLIGHT REFUSED: %d package(s) already dirty -- nothing written" % len(_pre)
        _out["pre_dirty"] = _pre[:20]
        print("__LL__" + _json.dumps(_out, indent=1, default=str))
        raise SystemExit(0)

    def _cur(_a):
        _v = _a.get_editor_property("hlod_material_override")
        return _v.get_path_name() if _v is not None else None

    _out["before"] = dict(_Counter(str(_cur(_a)) for _a in _ls))
    _changed, _already, _failed = [], [], []
    for _a in _ls:
        _lbl = _a.get_actor_label()
        try:
            if _cur(_a) == _want:
                _already.append(_lbl)
                continue
            _a.modify()
            _a.set_editor_property("hlod_material_override", _m)
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

    _after = _Counter(str(_cur(_a)) for _a in _ls)
    _out["readback"] = dict(_after)
    _out["all_at_target"] = (_after.get(_want, 0) == len(_ls))
    _out["ok"] = bool(_out["all_at_target"] and not _failed and not _left)
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
