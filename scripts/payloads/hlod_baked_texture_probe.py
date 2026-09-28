"""hlod_baked_texture_probe.py -- read the BAKED texture size off built cells.

READ-ONLY. This is the acceptance for R-HLODTEX: the landscape HLOD
texture size was set to 4096 on all 257 proxies, and the only proof that
the setting reached the geometry is the texture the builder actually
baked.

⛔ WHY NOT THE SOURCE-ACTOR LIST. `AWorldPartitionHLOD`'s editor-only
data -- SourceActors, InputStats, HLODStats, HLODBuildReport, LODLevel
and ten more -- is NOT REFLECTED TO PYTHON. All 15 candidate names from
`HLODActor.h:214-245` raise "Failed to find property" (enumerated
2026-09-14). They are private bare `UPROPERTY()` under
`WITH_EDITORONLY_DATA`. So "which actors went into this cell" cannot be
asked through this API at all.

What IS reachable is the OUTPUT: the actor's components, their static
meshes, those meshes' materials, and the textures those materials
sample. That chain is ordinary reflected API, and it answers the
question that actually matters -- what did the bake produce.

⭐ A CELL WITH NO TEXTURE IS NOT A FAILURE BY ITSELF. Instanced cells
carry ISM components referencing the ORIGINAL meshes and bake nothing;
only MeshMerge/MeshApproximate cells bake. Cells are therefore
classified, not just counted, and the denominator travels with every
number (standing rule 13).
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
WANT = int(CFG.get("want_cells") or 3)
SCAN = int(CFG.get("scan_limit") or 60)

_out = {"ok": False, "target_texture_size": 4096}

try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells_alpine8k"] = len(_hlods)

    _rows = []
    _scanned = 0
    _name_kind = _Counter()
    for _ad in _hlods:
        if len(_rows) >= WANT or _scanned >= SCAN:
            break
        _scanned += 1
        try:
            _obj = _ad.get_asset()
        except Exception:
            continue
        if _obj is None:
            continue
        _label = _obj.get_actor_label()
        _kind = "Merged" if "HLODLayer_Merged/" in _label else (
            "Instanced" if "HLODLayer_Instanced/" in _label else "other")
        _name_kind[_kind] += 1
        if _kind != "Merged":
            continue          # only the baking layer carries a texture

        _row = {"cell": _label, "package": str(_ad.package_name),
                "components": [], "textures": []}
        try:
            _comps = list(_obj.get_components_by_class(
                _u.StaticMeshComponent))
        except Exception as _e:
            _row["component_error"] = "%s: %s" % (type(_e).__name__, _e)
            _comps = []
        for _c in _comps:
            _cd = {"class": type(_c).__name__}
            try:
                _sm = _c.get_editor_property("static_mesh")
            except Exception:
                _sm = None
            if _sm is None:
                _cd["static_mesh"] = None
                _row["components"].append(_cd)
                continue
            _cd["static_mesh"] = _sm.get_path_name()
            try:
                _cd["triangles"] = int(_sm.get_num_triangles(0))
            except Exception:
                pass
            # materials -> textures
            try:
                _mats = list(_sm.get_editor_property("static_materials"))
            except Exception:
                _mats = []
            for _msl in _mats:
                try:
                    _mi = _msl.get_editor_property("material_interface")
                except Exception:
                    _mi = None
                if _mi is None:
                    continue
                try:
                    _texs = list(_u.MaterialEditingLibrary
                                 .get_used_textures(_mi))
                except Exception:
                    _texs = []
                for _t in _texs:
                    try:
                        _w = int(_t.blueprint_get_size_x())
                        _h = int(_t.blueprint_get_size_y())
                    except Exception:
                        try:
                            _w = int(_t.get_editor_property("imported_size").x)
                            _h = int(_t.get_editor_property("imported_size").y)
                        except Exception:
                            _w = _h = None
                    _row["textures"].append({
                        "texture": _t.get_path_name(),
                        "material": _mi.get_path_name(),
                        "size_x": _w, "size_y": _h})
            _row["components"].append(_cd)
        _row["n_textures"] = len(_row["textures"])
        _row["max_dim"] = max(
            [t["size_x"] or 0 for t in _row["textures"]]
            + [t["size_y"] or 0 for t in _row["textures"]] or [0])
        _rows.append(_row)

    _out["cells_scanned"] = _scanned
    _out["kind_seen_while_scanning"] = dict(_name_kind)
    _out["merged_cells_probed"] = len(_rows)
    _out["rows"] = _rows
    _dims = [t["size_x"] for _r in _rows for t in _r["textures"]
             if t["size_x"]]
    _out["all_texture_dims"] = sorted(set(_dims))
    _out["n_textures_total"] = len(_dims)
    _out["verdict"] = (
        "PASS" if _dims and all(_d == 4096 for _d in _dims)
        else ("NO TEXTURES FOUND" if not _dims else "FAIL"))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out, default=str))
