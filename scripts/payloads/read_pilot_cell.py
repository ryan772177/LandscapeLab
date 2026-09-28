"""read_pilot_cell.py -- what is inside ONE named HLOD cell, after a build.

READ-ONLY. The pilot question: after `-BuildSingleHLOD` on an
Instanced-layer L2 cell (the level the 256 landscape proxies land in),
does a LANDSCAPE bake exist, and at what size?

Reads every component, its mesh, its materials and their textures, and
classifies each texture as BAKED (a generated `*_Material_*` sibling in
the cell's own package) or SOURCE (vendor art referenced by an
instanced mesh). That distinction is the whole answer: an Instancing
layer referencing a 4096 tree texture is not a landscape bake.

Denominators travel with every count (standing rule 13).
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
LABEL = CFG["label"]

_out = {"ok": False, "label": LABEL}


def _tex(_t, _cellpkg):
    _p = _t.get_path_name()
    _d = {"path": _p, "name": _p.split(".")[-1]}
    for _k, _fn in (("x", "blueprint_get_size_x"),
                    ("y", "blueprint_get_size_y")):
        try:
            _d[_k] = int(getattr(_t, _fn)())
        except Exception:
            _d[_k] = None
    _d["in_cell_package"] = _p.startswith(_cellpkg)
    _d["looks_baked"] = ("_Material_" in _p) or _d["in_cell_package"]
    _d["mentions_landscape"] = "andscape" in _p
    try:
        _d["compression"] = str(_t.get_editor_property("compression_settings"))
    except Exception:
        pass
    return _d


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _target = None
    _scanned = 0
    for _ad in _ar.get_assets(_f):
        _scanned += 1
        try:
            _o = _ad.get_asset()
            if _o is not None and _o.get_actor_label() == LABEL:
                _target = (_ad, _o)
                break
        except Exception:
            continue
    _out["cells_scanned_to_find_it"] = _scanned
    if _target is None:
        _out["error"] = "cell not found by label"
        print("__LL__" + _json.dumps(_out, default=str))
        raise SystemExit(0)

    _ad, _obj = _target
    _pkg = str(_ad.package_name)
    _out["package"] = _pkg

    _comps = []
    _tex_rows = []
    _classes = _Counter()
    for _c in _obj.get_components_by_class(_u.ActorComponent):
        _cn = type(_c).__name__
        _classes[_cn] += 1
        if not isinstance(_c, _u.StaticMeshComponent):
            continue
        _cd = {"class": _cn}
        try:
            _sm = _c.get_editor_property("static_mesh")
        except Exception:
            _sm = None
        if _sm is not None:
            _cd["static_mesh"] = _sm.get_path_name()
            _cd["mesh_in_cell_package"] = _sm.get_path_name().startswith(_pkg)
            try:
                _cd["triangles_lod0"] = int(_sm.get_num_triangles(0))
            except Exception:
                pass
        try:
            _n = int(_c.get_num_materials())
        except Exception:
            _n = 0
        _cd["n_material_slots"] = _n
        _mats = []
        for _i in range(_n):
            try:
                _m = _c.get_material(_i)
            except Exception:
                continue
            if _m is None:
                continue
            _mats.append(_m.get_path_name())
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
                    _tex_rows.append(_tex(_t, _pkg))
        _cd["materials"] = _mats[:6]
        _comps.append(_cd)

    _out["component_classes"] = dict(_classes)
    _out["static_mesh_components"] = _comps
    _out["n_static_mesh_components"] = len(_comps)
    _out["textures"] = _tex_rows
    _out["n_textures"] = len(_tex_rows)

    _baked = [t for t in _tex_rows if t["looks_baked"]]
    _src = [t for t in _tex_rows if not t["looks_baked"]]
    _out["n_baked_textures"] = len(_baked)
    _out["n_source_textures"] = len(_src)
    _out["baked_dims"] = sorted({t["x"] for t in _baked if t.get("x")})
    _out["source_dims"] = sorted({t["x"] for t in _src if t.get("x")})
    _out["n_textures_mentioning_landscape"] = sum(
        1 for t in _tex_rows if t["mentions_landscape"])
    _out["verdict"] = (
        "NO BAKE IN THIS CELL (%d textures, all source)" % len(_tex_rows)
        if not _baked else
        "BAKE PRESENT: %d baked textures, dims %s"
        % (len(_baked), _out["baked_dims"]))
    _out["ok"] = True
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, default=str))
