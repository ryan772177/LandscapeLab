"""read_landscape_hlod_overrides.py -- the two levers that suppress a bake.

READ-ONLY. Nothing is written.

TWO LEVERS, and either one alone explains a missing texture:

  HLODMaterialOverride   LandscapeProxy.h:966. Its own EditCondition says
                         the texture-size fields are disabled when it is
                         set -- "Specifying an HLOD Material Override
                         will result in NO TEXTURE being baked for the
                         HLOD mesh." A non-null value here IS the zero.
  HLODTextureSizePolicy  LandscapeProxy.h:958. Only SpecificSize reads
                         HLODTextureSize (LandscapeHLODBuilder.cpp:222).

⭐ INHERITED vs LOCAL. Both are marked `LandscapeOverridable`, so a proxy
may carry its own value or inherit the parent ALandscape's.
`get_editor_property` returns the EFFECTIVE value either way, which is
what the builder reads -- so the effective value is the one that decides
the bake. Which of the two it came from is tracked in
`ALandscapeStreamingProxy::OverriddenSharedProperties`
(LandscapeStreamingProxy.h:37-39), a private bare `UPROPERTY()`
TSet<FName>. This tries to read it and REPORTS THE FAILURE rather than
inferring inheritance from a value match -- two proxies agreeing with
the parent is not evidence that either inherits.

Every count carries its denominator (standing rule 13).
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

_PROPS = ["hlod_material_override", "hlod_texture_size_policy",
          "hlod_texture_size", "hlod_mesh_source_lod_policy"]
# The FName the override set would carry, if it is reachable at all.
_OVERRIDE_KEYS = ["HLODMaterialOverride", "HLODTextureSizePolicy",
                  "HLODTextureSize", "HLODMeshSourceLODPolicy"]

_out = {"ok": False}


def _val(_a, _p):
    try:
        _v = _a.get_editor_property(_p)
    except Exception as _e:
        return "RAISED: %s" % type(_e).__name__
    if _v is None:
        return None
    if isinstance(_v, (bool, int, float, str)):
        return _v
    if hasattr(_v, "get_path_name"):
        return _v.get_path_name()
    return str(_v)


try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _parent = [_a for _a in _actors
               if _a.get_class().get_name() == "Landscape"]
    _proxies = [_a for _a in _actors
                if _a.get_class().get_name() == "LandscapeStreamingProxy"]
    _out["n_parent"] = len(_parent)
    _out["n_proxies"] = len(_proxies)

    # ---- the parent ------------------------------------------------
    _out["parent"] = ({_p: _val(_parent[0], _p) for _p in _PROPS}
                      if _parent else None)
    if _parent:
        _out["parent"]["label"] = _parent[0].get_actor_label()

    # ---- every proxy -----------------------------------------------
    _dist = {_p: _Counter() for _p in _PROPS}
    _raised = {_p: 0 for _p in _PROPS}
    _nonnull_override = []
    _ovr_reachable = None
    _ovr_error = None
    _ovr_dist = _Counter()

    for _a in _proxies:
        for _p in _PROPS:
            _v = _val(_a, _p)
            if isinstance(_v, str) and _v.startswith("RAISED"):
                _raised[_p] += 1
                continue
            _dist[_p][_json.dumps(_v)] += 1
            if _p == "hlod_material_override" and _v is not None:
                _nonnull_override.append({"actor": _a.get_actor_label(),
                                          "override": _v})
        # inherited vs local
        try:
            _s = _a.get_editor_property("overridden_shared_properties")
            _ovr_reachable = True
            _names = sorted(str(_x) for _x in (_s or []))
            _hlod = [_n for _n in _names if "HLOD" in _n]
            _ovr_dist[_json.dumps(_hlod)] += 1
        except Exception as _e:
            if _ovr_reachable is None:
                _ovr_reachable = False
                _ovr_error = "%s: %s" % (type(_e).__name__, str(_e)[:160])

    _out["proxy_distribution"] = {_p: dict(_dist[_p]) for _p in _PROPS}
    _out["proxy_reads_raised"] = _raised
    _out["proxy_read_ok"] = {_p: sum(_dist[_p].values()) for _p in _PROPS}
    _out["n_proxies_with_nonnull_hlod_material_override"] = len(
        _nonnull_override)
    _out["nonnull_override_sample"] = _nonnull_override[:10]

    _out["overridden_shared_properties_reachable"] = _ovr_reachable
    _out["overridden_shared_properties_error"] = _ovr_error
    _out["overridden_hlod_keys_distribution"] = dict(_ovr_dist)
    if _ovr_reachable is False:
        _out["_inherited_vs_local"] = (
            "NOT DETERMINABLE from Python: OverriddenSharedProperties is a "
            "private bare UPROPERTY (LandscapeStreamingProxy.h:37-39) and "
            "does not resolve. The EFFECTIVE value is reported instead, "
            "which is what the builder reads. A value matching the parent "
            "is NOT evidence of inheritance.")

    # The decisive question, stated as a verdict with its denominator.
    _mo = _out["proxy_distribution"]["hlod_material_override"]
    _all_null = (list(_mo.keys()) == ["null"]
                 and _mo.get("null") == len(_proxies))
    _parent_mo = _out["parent"]["hlod_material_override"] if _parent else "?"
    _out["verdict_material_override"] = (
        "ALL NULL (%d/%d proxies, parent %s) -- the override is NOT the zero"
        % (_mo.get("null", 0), len(_proxies), _parent_mo)
        if _all_null and _parent_mo is None else
        "NON-NULL PRESENT -- this IS the zero")
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
