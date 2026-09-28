"""hlodtex_coldread_probe.py -- H-9/D-6: the 1024->32 read-back mechanism.

READ-ONLY. Run TWICE via ue_exec against a FRESHLY LAUNCHED editor
(rule 11 cleared, R-EDITOR-CLOSE afterwards): once as the editor's
first touch of these assets (T+0, the COLD read) and once ~60 s later
(T+60, the warm re-read). The 09-14 anomaly was a getter reporting 32
-- exactly five mips below 1024 -- and the three-getter agreement that
"closed" it was measured on a WARM DDC only (CAP4096_PARTIAL.md sec.4).

Per cell (the same six the warm table used, 3 rebuilt@4096 + 3 @1024),
per texture reached through the component->material chain (the ONLY
reflected route, hlod_baked_texture_probe3.py's finding), this records
IN ORDER with a perf-counter timestamp per read:

    get_size_x / get_size_y          (the fast getter -- the 32 suspect)
    blueprint_get_built_texture_size (the built platform data)
    num mips: texture.get_num_mips() if reflected, else via
              blueprint_get_built_texture_size arithmetic NOT attempted
              -- absence is recorded, never derived

The OFF-DISK source dimensions are the host's job (uasset_lite), not
this payload's: same instrument split as the warm table, so the two
runs stay comparable. A getter that RAISES is recorded as RAISED with
the exception name -- "I could not look" is not a reading (NN6).
"""
import json as _json
import time as _time
import traceback as _tb

import unreal as _u

_CELLS = ["L2_X-2_Y-1", "L2_X-1_Y-6", "L2_X-2_Y1",
          "L2_X-3_Y3", "L2_X0_Y6", "L2_X-6_Y-6"]
_PKG_ROOT = "/Game/__ExternalActors__/Alpine8K"

_out = {"probe": "hlodtex_coldread", "t_payload_start": _time.perf_counter(),
        "cells": {}}


def _read(_fn, _label, _rec):
    _t0 = _time.perf_counter()
    try:
        _v = _fn()
        _rec[_label] = {"value": _v, "t": _t0}
    except Exception as _e:
        _rec[_label] = {"RAISED": type(_e).__name__, "t": _t0}


def _tex_reads(_t):
    _rec = {"path": _t.get_path_name()}
    # blueprint_get_size_x/y — the ONLY size getters reflected on
    # Texture2D (auditor: bare get_size_x/y exist only on
    # SparseVolumeTexture; the warm-DDC table used these same names)
    _read(lambda: [int(_t.blueprint_get_size_x()),
                   int(_t.blueprint_get_size_y())],
          "get_size_xy", _rec)

    def _built():
        _s = _t.blueprint_get_built_texture_size()
        return [int(_s.x), int(_s.y)]
    _read(_built, "built_texture_size", _rec)
    # NO mip-count read: neither get_num_mips nor a num_mips property is
    # reflected on UTexture2D in 5.8 (stub grep 2026-09-16: zero hits on
    # the class; the num_mips hits belong to other classes). The 32
    # signal was a SIZE reading (1024 >> 5), so the two size getters
    # above carry it; absence recorded here rather than derived (NN6).
    return _rec


def _do_cell(_cell, _hit):
    _crec = {"textures": [], "t_cell": _time.perf_counter(),
             "package": str(_hit.package_name)}
    _out["cells"][_cell] = _crec
    _crec["t_before_load"] = _time.perf_counter()
    _actor = _hit.get_asset()          # FIRST TOUCH on the cold run
    _crec["t_loaded"] = _time.perf_counter()
    if _actor is None:
        _crec["error"] = "asset load returned None"
        return
    _comps = _actor.get_components_by_class(_u.StaticMeshComponent)
    for _c in _comps:
        _n = _c.get_num_materials()
        for _i in range(_n):
            _m = _c.get_material(_i)
            if _m is None:
                continue
            try:
                _texs = _u.MaterialEditingLibrary.get_used_textures(_m)
            except Exception:
                _texs = []
            if not _texs:
                # probe3's route: the material instance's texture
                # parameter values
                try:
                    _texs = [_tv.parameter_value for _tv in
                             _m.texture_parameter_values
                             if _tv.parameter_value is not None]
                except Exception as _e:
                    _crec.setdefault("material_errors", []).append(
                        type(_e).__name__)
                    _texs = []
            for _t in _texs:
                if isinstance(_t, _u.Texture2D):
                    _crec["textures"].append(_tex_reads(_t))


try:
    # ONE registry scan, hoisted (auditor: six recursive scans of the
    # external-actors tree were pure waste), via probe3's proven ARFilter
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _flt = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=[_PKG_ROOT],
        recursive_paths=True)
    _hlods = _ar.get_assets(_flt)
    _out["n_hlod_assets"] = len(_hlods)

    def _match(_cell):
        # ANCHORED: the cell token must not be followed by a digit or a
        # minus sign, so L2_X0_Y6 can never take L2_X0_Y-6 or a longer
        # coordinate (auditor point 4)
        for _a in _hlods:
            _nm = str(_a.asset_name)
            _i = _nm.find(_cell)
            if _i < 0:
                continue
            _after = _nm[_i + len(_cell):_i + len(_cell) + 1]
            if _after and (_after.isdigit() or _after == "-"):
                continue
            return _a
        return None

    for _cell in _CELLS:
        # per-cell containment: one raising cell must not burn the
        # remaining cells' one-shot cold state (auditor point 3)
        try:
            _hit = _match(_cell)
            if _hit is None:
                _out["cells"][_cell] = {
                    "error": "no WorldPartitionHLOD asset matching %s"
                             % _cell}
                continue
            _do_cell(_cell, _hit)
        except Exception as _e:
            _out["cells"].setdefault(_cell, {})["error"] = (
                "%s: %s" % (type(_e).__name__, _e))
    _out["ok"] = True
except Exception as _e:
    _out["ok"] = False
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out, default=str))
