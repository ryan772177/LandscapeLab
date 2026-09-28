"""hlod_baked_texture_probe2.py -- baked texture size, via the PACKAGE.

READ-ONLY. R-HLODTEX acceptance.

The first probe reached the baked static mesh (3,992-4,000 triangles,
so the bake produced geometry) and then found zero textures, because the
material -> texture hop went through
`MaterialEditingLibrary.get_used_textures`, which returned nothing.

⭐ THE SHORTER ROUTE IS THE REGISTRY. An HLOD cell's baked assets live
in the CELL'S OWN PACKAGE -- the mesh reads
`<package>.StaticMesh_Alpine8K_HLODLayer_Merged_0`, so the material and
the baked texture are siblings in that package. Listing the package's
assets asks the registry a question it already has the answer to, and
skips the material API entirely.

Texture dimensions come from `blueprint_get_size_x/y` where available
and from `imported_size` otherwise; BOTH are reported per texture so a
disagreement between them is visible rather than resolved silently.
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
WANT = int(CFG.get("want_cells") or 3)
SCAN = int(CFG.get("scan_limit") or 60)

_out = {"ok": False, "target_texture_size": 4096}


def _dims(_t):
    _d = {}
    for _k, _fn in (("bp_x", "blueprint_get_size_x"),
                    ("bp_y", "blueprint_get_size_y")):
        try:
            _d[_k] = int(getattr(_t, _fn)())
        except Exception:
            _d[_k] = None
    try:
        _isz = _t.get_editor_property("imported_size")
        _d["imported_x"] = int(_isz.x)
        _d["imported_y"] = int(_isz.y)
    except Exception:
        _d["imported_x"] = _d["imported_y"] = None
    return _d


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_cells_alpine8k"] = len(_hlods)

    _rows, _scanned = [], 0
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
        if "HLODLayer_Merged/" not in _label:
            continue
        _pkg = str(_ad.package_name)
        # Every asset the builder wrote into this cell's package.
        try:
            _sibs = _ar.get_assets_by_package_name(
                _u.Name(_pkg), include_only_on_disk_assets=False) or []
        except Exception as _e:
            _sibs = []
        _classes = _Counter()
        _texrows = []
        for _s in _sibs:
            try:
                _cn = str(_s.asset_class_path.asset_name)
            except Exception:
                _cn = "?"
            _classes[_cn] += 1
            if "Texture" not in _cn:
                continue
            try:
                _t = _s.get_asset()
            except Exception:
                _t = None
            if _t is None:
                _texrows.append({"asset": str(_s.asset_name),
                                 "error": "did not load"})
                continue
            _r = {"asset": str(_s.asset_name), "class": _cn}
            _r.update(_dims(_t))
            try:
                _r["compression"] = str(
                    _t.get_editor_property("compression_settings"))
                _r["srgb"] = bool(_t.get_editor_property("srgb"))
            except Exception:
                pass
            _texrows.append(_r)
        _rows.append({"cell": _label, "package": _pkg,
                      "package_assets": dict(_classes),
                      "textures": _texrows,
                      "n_textures": len(_texrows)})

    _out["cells_scanned"] = _scanned
    _out["merged_cells_probed"] = len(_rows)
    _out["rows"] = _rows

    _all = []
    for _r in _rows:
        for _t in _r["textures"]:
            for _k in ("bp_x", "bp_y", "imported_x", "imported_y"):
                if _t.get(_k):
                    _all.append(_t[_k])
    _out["n_texture_dim_samples"] = len(_all)
    _out["distinct_dims"] = sorted(set(_all))
    _out["verdict"] = (
        "NO TEXTURES FOUND" if not _all
        else ("PASS" if all(_d == 4096 for _d in _all) else "FAIL"))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out, default=str))
