"""hlod_cell_sources.py -- what CONTENT is inside each HLOD cell?

READ-ONLY. Closes the gap left by the 2026-09-14 build report: the
attribution splits cells by LAYER, which does not say whether a cell
contains landscape. Layer is where the cell lives; this is what it was
built FROM.

⭐ THE STRUCTURE, and it is two levels deep because of the cascade.
Each HLOD actor carries `SourceActors`
(`HLODActor.h:217`), a `UWorldPartitionHLODSourceActorsFromCell` whose
`Actors` array holds `FWorldPartitionRuntimeCellObjectMapping` entries
with `Package` and `Path` (`HLODSourceActorsFromCell.h:36`,
`WorldPartitionRuntimeCell.h:118-125`). So:

    Instanced cell  -> sources are ORDINARY ACTORS (landscape proxies,
                       foliage, static meshes) from a MainPartition cell
    Merged cell     -> sources are the INSTANCED LAYER'S HLOD ACTORS

A Merged cell therefore contains landscape only TRANSITIVELY, and asking
"does this cell contain a LandscapeStreamingProxy" without resolving the
cascade would answer NO for every Merged cell and be wrong.

⛔ CLASS COMES FROM THE ASSET REGISTRY, NOT FROM LOADING. The registry
stores each external actor's class, so 2,267 cells x N sources can be
classified without pulling meshes and textures into memory. Loading
would give the same class and cost gigabytes. Where the registry has no
entry the row is counted as UNRESOLVED rather than assumed empty -- "I
could not look" is not "it is absent" (NN6).

Every count is reported with its denominator (standing rule 13).
"""
import json as _json
import traceback as _tb
from collections import Counter as _Counter

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
LIMIT = int(CFG.get("limit") or 0)          # 0 = all cells

_out = {"ok": False}


def _class_of(_ar, _pkg):
    """Asset class for an external-actor package name, from the registry."""
    try:
        _ads = _ar.get_assets_by_package_name(_u.Name(_pkg),
                                              include_only_on_disk_assets=False)
    except Exception:
        return None
    for _ad in (_ads or []):
        try:
            return str(_ad.asset_class_path.asset_name)
        except Exception:
            try:
                return str(_ad.asset_class)
            except Exception:
                return None
    return None


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()

    # Every HLOD cell on disk, not just the ones the editor has loaded.
    # ⛔ THE FILTER MUST NAME THE LEVEL. Without a package path the
    # registry returns every world's HLOD cells -- 2,395 against
    # Alpine8K's 2,267, i.e. 128 belonging to Canyon, CoastBench,
    # ForgeWorld and the rest. A count that silently spans worlds is
    # the "plausible artefact from the wrong level" failure in table
    # form.
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _hlods = _ar.get_assets(_f)
    _out["n_hlod_cells_on_disk"] = len(_hlods)
    _all_f = _u.ARFilter(class_paths=[_u.TopLevelAssetPath(
        "/Script/Engine", "WorldPartitionHLOD")], recursive_paths=True)
    _out["n_hlod_cells_all_worlds"] = len(_ar.get_assets(_all_f))

    _cells = []
    _by_layer = _Counter()
    _cells_with_landscape = _Counter()
    _unresolved = 0
    _n_done = 0

    # Pass 1: read every cell's DIRECT source classes.
    _direct = {}          # cell package -> {class: count}
    _cellinfo = {}        # cell package -> {"name":..., "layer":...}
    for _ad in _hlods:
        if LIMIT and _n_done >= LIMIT:
            break
        _n_done += 1
        _pkg = str(_ad.package_name)
        # ⛔ NOT load_asset(package_name). An external ACTOR package's
        # object is not addressable by its package name -- that returns
        # None for every cell, which the first probe reported as 12 of
        # 12 "unloadable". AssetData.get_asset() resolves the object
        # the registry already knows about.
        try:
            _obj = _ad.get_asset()
        except Exception:
            _obj = None
        if _obj is None:
            _unresolved += 1
            continue
        try:
            _name = _obj.get_actor_label()
        except Exception:
            _name = str(_ad.asset_name)
        # The folder the actor is filed under IS its layer.
        _layer = None
        try:
            _l = _obj.get_editor_property("subactors_hlod_layer")
            _layer = _l.get_path_name() if _l else None
        except Exception:
            pass
        if not _layer:
            # Fall back to the name, which carries the source grid, and
            # to the folder path the builder logs.
            _layer = _name
        _sa = None
        try:
            _sa = _obj.get_editor_property("source_actors")
        except Exception as _e:
            _cellinfo[_pkg] = {"name": _name, "error":
                               "source_actors: %s" % type(_e).__name__}
            continue
        _classes = _Counter()
        _srcpkgs = []
        if _sa is not None:
            try:
                _acts = _sa.get_editor_property("actors") or []
            except Exception:
                _acts = []
            for _m in _acts:
                try:
                    _sp = str(_m.get_editor_property("package"))
                except Exception:
                    continue
                _srcpkgs.append(_sp)
                _c = _class_of(_ar, _sp)
                _classes[_c or "UNRESOLVED"] += 1
        _direct[_pkg] = {"name": _name, "classes": dict(_classes),
                         "sources": _srcpkgs}
        _cellinfo[_pkg] = {"name": _name}

    _out["cells_read"] = len(_direct)
    _out["cells_unloadable"] = _unresolved

    # Pass 2: resolve the cascade. A Merged cell's sources are HLOD
    # actors; substitute each one's OWN direct classes so the answer is
    # about content, not about the layer below.
    _rows = []
    for _pkg, _d in _direct.items():
        _eff = _Counter()
        _via_hlod = 0
        for _sp in _d["sources"]:
            if _sp in _direct:
                _via_hlod += 1
                for _c, _n in _direct[_sp]["classes"].items():
                    _eff[_c] += _n
            else:
                _c = _class_of(_ar, _sp)
                _eff[_c or "UNRESOLVED"] += 1
        _has_ls = _eff.get("LandscapeStreamingProxy", 0) > 0
        _rows.append({
            "cell": _d["name"],
            "package": _pkg,
            "n_sources": len(_d["sources"]),
            "n_sources_that_are_hlod": _via_hlod,
            "direct_classes": _d["classes"],
            "effective_classes": dict(_eff),
            "has_landscape_proxy": _has_ls,
            "n_landscape_proxies": _eff.get("LandscapeStreamingProxy", 0),
        })

    _out["rows"] = _rows[:400]           # sample for the artefact
    _out["n_rows"] = len(_rows)
    _out["cells_with_landscape"] = sum(1 for _r in _rows
                                       if _r["has_landscape_proxy"])
    # Layer split, by the cell NAME's own prefix (the builder files a
    # cell under its layer and names it after its source).
    _split = _Counter()
    for _r in _rows:
        _k = ("Merged" if "HLODLayer_Merged" in _r["cell"]
              or _r["n_sources_that_are_hlod"] > 0 else "Instanced")
        _split[(_k, bool(_r["has_landscape_proxy"]))] += 1
    _out["layer_split"] = {"%s|landscape=%s" % (k[0], k[1]): v
                           for k, v in _split.items()}
    # Distinct landscape proxies reached, against the 257 in the world.
    _seen = set()
    for _pkg, _d in _direct.items():
        for _sp in _d["sources"]:
            if _class_of(_ar, _sp) == "LandscapeStreamingProxy":
                _seen.add(_sp)
    _out["distinct_landscape_proxies_reached"] = len(_seen)
    _out["class_totals"] = dict(_Counter(
        {k: sum(r["effective_classes"].get(k, 0) for r in _rows)
         for r in _rows for k in r["effective_classes"]}))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-2000:]

print("__LL__" + _json.dumps(_out, default=str))
