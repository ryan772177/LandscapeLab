"""read_landscape_hlod_relevance.py -- is the landscape even IN the HLOD?

READ-ONLY. Nothing is written.

The headers say landscape components ARE routed to ULandscapeHLODBuilder
under every layer type: the regrouping happens in the BASE outer
`UHLODBuilder::Build` (HLODBuilder.cpp:349-356), and the concrete
builders override only the INNER Build (HLODBuilderInstancing.h:71,
HLODBuilderMeshApproximate.h:41, LandscapeHLODBuilder.h). So a landscape
bake SHOULD exist in this world -- and the 2026-09-14 census over all
2,267 cells found none.

Something upstream is excluding it, and the header names the candidate:

    ULandscapeComponent::IsHLODRelevant()          Landscape.cpp:2178
        -> CanBeHLODRelevant(this) && bEnableAutoLODGeneration

`bEnableAutoLODGeneration` is AActor::bEnableAutoLODGeneration
(Actor.h:559) -- the "Include in HLOD" checkbox. If it is false on the
landscape proxies, every landscape component is dropped before any
builder sees it, and no HLODTextureSize on earth changes the output.

Also read: ULandscapeNaniteComponent::IsHLODRelevant() returns FALSE
unconditionally (LandscapeNaniteComponent.cpp:222-226), so if the
landscape is Nanite-enabled the NANITE components are excluded by
design and only the plain LandscapeComponents can contribute.

Counts are reported with their denominators (standing rule 13).
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

_out = {"ok": False}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape",
                                            "LandscapeStreamingProxy")]
    _out["n_landscape_actors"] = len(_ls)
    _out["n_by_class"] = dict(_Counter(_a.get_class().get_name()
                                       for _a in _ls))

    _dist = _Counter()
    _raised = 0
    _first_err = None
    _outliers = []
    for _a in _ls:
        try:
            _v = bool(_a.get_editor_property("enable_auto_lod_generation"))
        except Exception as _e:
            _raised += 1
            if _first_err is None:
                _first_err = "%s: %s" % (type(_e).__name__, _e)
            continue
        _dist[_v] += 1
    _out["enable_auto_lod_generation"] = {str(_k): _v
                                          for _k, _v in _dist.items()}
    _out["enable_auto_lod_generation_raised"] = _raised
    _out["enable_auto_lod_generation_first_error"] = _first_err
    _out["read_ok"] = sum(_dist.values())

    # Name the minority, if any -- a 256:1 split hides the 1.
    if len(_dist) > 1:
        _major = _dist.most_common(1)[0][0]
        for _a in _ls:
            try:
                _v = bool(_a.get_editor_property("enable_auto_lod_generation"))
            except Exception:
                continue
            if _v != _major:
                _outliers.append({"actor": _a.get_actor_label(),
                                  "class": _a.get_class().get_name(),
                                  "value": _v})
    _out["outliers"] = _outliers

    # Is the landscape Nanite? If so its Nanite components are excluded
    # by design and only plain LandscapeComponents can contribute.
    _nan = _Counter()
    _ncomp = 0
    for _a in _ls:
        try:
            _nan[bool(_a.get_editor_property("enable_nanite"))] += 1
        except Exception:
            pass
        try:
            _ncomp += len(list(_a.get_components_by_class(
                _u.LandscapeNaniteComponent)))
        except Exception:
            pass
    _out["enable_nanite"] = {str(_k): _v for _k, _v in _nan.items()}
    _out["n_landscape_nanite_components"] = _ncomp

    # Plain landscape components, the ones that COULD be baked.
    _plain = 0
    for _a in _ls[:8]:
        try:
            _plain += len(list(_a.get_components_by_class(
                _u.LandscapeComponent)))
        except Exception:
            pass
    _out["landscape_components_in_first_8_actors"] = _plain
    _out["_note"] = ("component counts are over the first 8 actors only; "
                     "the world holds 257 landscape actors")
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
