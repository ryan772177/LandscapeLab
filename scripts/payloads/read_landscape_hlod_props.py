"""read_landscape_hlod_props.py -- the FOUR real landscape-HLOD levers.

READ-ONLY. Nothing is assigned, nothing is mutated.

⭐ WHY THESE FOUR AND NOT THE HLODLayer's SETTINGS.
`ULandscapeComponent::GetCustomHLODBuilderClass()` returns
`ULandscapeHLODBuilder::StaticClass()` UNCONDITIONALLY
(LandscapeComponent.cpp:97-100), and `HLODBuilder.cpp:354` regroups
every source component by that class before building. So a landscape
component is never handed to the layer's MeshMerge builder, and
`mesh_merge_settings.material_settings.texture_sizing_type` -- the
2026-09-13 Task 5 write -- cannot reach it under ANY layer assignment.

What DOES govern the landscape HLOD mesh lives on the proxy itself
(LandscapeProxy.h):

    :958  HLODTextureSizePolicy        ELandscapeHLODTextureSizePolicy
    :963  HLODTextureSize              int32
    :966  HLODMaterialOverride         UMaterialInterface*
    :971  HLODMeshSourceLODPolicy      ELandscapeHLODMeshSourceLODPolicy
    :954  bUseLandscapeForCullingInvisibleHLODVertices   (read too --
          it is in the same HLOD category and costs nothing)

All are marked `LandscapeOverridable`, which means the parent Landscape
actor holds a value and each proxy MAY override it. So reading the
Landscape actor alone would not answer the question: a single divergent
proxy is invisible from the parent. Every one of the 257 actors is read.

⛔ AND THE READ REPORTS ITS OWN SAMPLE COUNT (standing rule 13). Reads
that RAISED are counted separately from values that came back, because
"all 257 agree" computed over 3 successful reads is not agreement.
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

_PROPS = ["hlod_texture_size_policy", "hlod_texture_size",
          "hlod_material_override", "hlod_mesh_source_lod_policy",
          "hlod_mesh_source_lod",
          "use_landscape_for_culling_invisible_hlod_vertices"]

_out = {"ok": False,
        "_source": "LandscapeProxy.h:953-974 (5.8.1); names snake_cased",
        "_why": "ULandscapeComponent::GetCustomHLODBuilderClass() returns "
                "ULandscapeHLODBuilder unconditionally "
                "(LandscapeComponent.cpp:97-100), so the HLODLayer's "
                "MeshMerge settings cannot govern landscape HLOD; these "
                "proxy properties do."}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape",
                                            "LandscapeStreamingProxy")]
    _out["n_landscape_actors"] = len(_ls)
    _out["n_by_class"] = dict(_Counter(
        _a.get_class().get_name() for _a in _ls))

    _dist = {p: _Counter() for p in _PROPS}
    _raised = {p: 0 for p in _PROPS}
    _rows = []
    _first_error = {}
    for _a in _ls:
        _row = {"label": _a.get_actor_label(),
                "class": _a.get_class().get_name()}
        for _p in _PROPS:
            try:
                _v = _a.get_editor_property(_p)
            except Exception as _e:
                _raised[_p] += 1
                _row[_p] = "RAISED"
                _first_error.setdefault(
                    _p, "%s: %s" % (type(_e).__name__, _e))
                continue
            if _v is None:
                _s = None
            elif isinstance(_v, (bool, int, float, str)):
                _s = _v
            elif hasattr(_v, "get_path_name"):
                _s = _v.get_path_name()
            else:
                _s = str(_v)
            _row[_p] = _s
            _dist[_p][_json.dumps(_s)] += 1
        _rows.append(_row)

    _out["distribution"] = {p: dict(_dist[p]) for p in _PROPS}
    _out["reads_that_raised"] = _raised
    _out["first_error_per_property"] = _first_error
    _out["n_read_ok_per_property"] = {
        p: sum(_dist[p].values()) for p in _PROPS}

    # ⭐ THE OUTLIERS, NAMED. A distribution that is 256:1 hides the 1
    # unless it is listed, and the 1 is the whole reason for reading
    # every proxy instead of the parent.
    _outliers = []
    for _p in _PROPS:
        if len(_dist[_p]) <= 1:
            continue
        _major = _dist[_p].most_common(1)[0][0]
        for _r in _rows:
            if _json.dumps(_r.get(_p)) != _major:
                _outliers.append({"actor": _r["label"], "class": _r["class"],
                                  "property": _p, "value": _r.get(_p),
                                  "majority_value": _json.loads(_major)})
    _out["outliers"] = _outliers
    _out["n_outliers"] = len(_outliers)
    _out["parent_landscape"] = [
        _r for _r in _rows if _r["class"] == "Landscape"]
    _out["sample_proxies"] = [
        _r for _r in _rows if _r["class"] == "LandscapeStreamingProxy"][:3]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
