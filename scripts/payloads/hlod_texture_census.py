"""hlod_texture_census.py -- baked texture size across BOTH HLOD layers.

READ-ONLY. R-HLODTEX acceptance, done over the whole cell population
rather than a sample that turned out to be one-sided: a 400-cell scan
filtered to the Instanced layer found ZERO, so the registry's ordering
is not what the earlier probe assumed and a 3-cell sample cannot be
trusted to represent either layer.

Tallies every cell by layer, then reads baked textures from the first N
of EACH layer, so the two populations are reported separately with their
own denominators (standing rule 13).

Layer comes from the actor label, which the builder writes as
`<layer>/<source cell>`:

    Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L0_X-16_Y18
    Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-8_Y10

⛔ The SLASH matters. A Merged label CONTAINS the text
"HLODLayer_Instanced" (as its source), so matching without the
separator classifies every Merged cell as Instanced.
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
PER_LAYER = int(CFG.get("per_layer") or 3)
TALLY_LIMIT = int(CFG.get("tally_limit") or 0)     # 0 = all

_out = {"ok": False, "target_texture_size": 4096}


def _tex_dims(_t):
    _d = {"texture": _t.get_path_name().split(".")[-1]}
    for _k, _fn in (("x", "blueprint_get_size_x"),
                    ("y", "blueprint_get_size_y")):
        try:
            _d[_k] = int(getattr(_t, _fn)())
        except Exception:
            _d[_k] = None
    try:
        _d["compression"] = str(_t.get_editor_property("compression_settings"))
    except Exception:
        pass
    return _d


def _textures_of(_obj):
    _tex = []
    try:
        _comps = list(_obj.get_components_by_class(_u.StaticMeshComponent))
    except Exception:
        return _tex, 0
    _slots = 0
    for _c in _comps:
        try:
            _n = int(_c.get_num_materials())
        except Exception:
            _n = 0
        _slots += _n
        for _i in range(_n):
            try:
                _m = _c.get_material(_i)
            except Exception:
                continue
            if _m is None:
                continue
            try:
                _tpv = list(_m.get_editor_property("texture_parameter_values"))
            except Exception:
                _tpv = []
            for _p in _tpv:
                try:
                    _t = _p.get_editor_property("parameter_value")
                except Exception:
                    _t = None
                if _t is not None:
                    _tex.append(_tex_dims(_t))
    return _tex, _slots


def _layer_of(_label):
    if "HLODLayer_Merged/" in _label:
        return "Merged"
    if "HLODLayer_Instanced/" in _label:
        return "Instanced"
    return "other"


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells_alpine8k"] = len(_hlods)

    _tally = _Counter()
    _picked = {"Merged": [], "Instanced": [], "other": []}
    _unloadable = 0
    _n = 0
    for _ad in _hlods:
        if TALLY_LIMIT and _n >= TALLY_LIMIT:
            break
        _n += 1
        try:
            _obj = _ad.get_asset()
        except Exception:
            _obj = None
        if _obj is None:
            _unloadable += 1
            continue
        try:
            _label = _obj.get_actor_label()
        except Exception:
            _unloadable += 1
            continue
        _k = _layer_of(_label)
        _tally[_k] += 1
        if len(_picked[_k]) < PER_LAYER:
            _tex, _slots = _textures_of(_obj)
            _picked[_k].append({"cell": _label, "n_material_slots": _slots,
                                "textures": _tex, "n_textures": len(_tex)})

    _out["cells_examined"] = _n
    _out["cells_unloadable"] = _unloadable
    _out["layer_tally"] = dict(_tally)
    _out["samples"] = _picked

    _summary = {}
    for _k in ("Merged", "Instanced", "other"):
        _dims = [t[c] for r in _picked[_k] for t in r["textures"]
                 for c in ("x", "y") if t.get(c)]
        _summary[_k] = {
            "cells_sampled": len(_picked[_k]),
            "n_dim_samples": len(_dims),
            "distinct_dims": sorted(set(_dims)),
            "all_4096": bool(_dims) and all(_d == 4096 for _d in _dims),
        }
    _out["per_layer_summary"] = _summary
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out, default=str))
