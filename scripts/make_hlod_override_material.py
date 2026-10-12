"""make_hlod_override_material.py -- far-terrain HLOD override material (2026-10-06).

    python scripts/make_hlod_override_material.py [--recipe recipes/hlod_override_alpine8k.json] [--dry-run]

Builds `material_path` (find-or-create, total clear via material_graph, rebuild, exact
sampler assertion, compile, save, read back). The graph:

    uv        = (WorldPosition.xy - origin + pixel_cm/2) / (pixels * pixel_cm)
                -> pixel centres on landscape vertices, clamped by the texture
    w         = T_Alpine_8k_Weights(uv)   RGBA = Snow Rock Scree ForestFloor
    cav       = T_Alpine_8k_Cavity(uv)    RGB  = cavity lichen damp (same UV)
    grass     = saturate(1 - (r + g + b + a))
    w_rock'   = w_G * prod_ch lerp(1, tint_ch, cav_ch * strength_ch)   (v2, 2026-10-06:
                the near material's cavity/lichen/damp formula; tints/strengths from
                recipe rock_modulation, cross-checked against alpine_8k material.cavity)
    BaseColor = sum(w_i * color_i) with w_rock' for Rock (linear, fitted colours)
    Roughness = sum(w_i * roughness_i) with the PLAIN rock weight
    no normal input (the LOD2 HLOD geometry carries the shape)

Used with Nanite is set and read back (the HLOD cell meshes are Nanite).
Without --dry-run it needs a running editor (any level); it touches only this material.
Setting it on the landscape is a separate step (payloads/set_landscape_hlod_material_override).
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import material_graph  # noqa: E402

DEFAULT = os.path.join(bootstrap.REPO_ROOT, "recipes", "hlod_override_alpine8k.json")
LAYERS = ("Snow", "Rock", "Scree", "ForestFloor", "Grass")
CHANNELS = {"Snow": "R", "Rock": "G", "Scree": "B", "ForestFloor": "A", "Grass": "remainder"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate(r):
    e = []
    if r.get("schema_version") != "hlod-override-1.0":
        e.append("schema_version must be hlod-override-1.0")
    if not re.fullmatch(r"/Game/[A-Za-z0-9_/]+", str(r.get("material_path", ""))):
        e.append("material_path must be a /Game/ path")
    if not re.fullmatch(r"/Game/[A-Za-z0-9_/]+", str(r.get("weights_texture", ""))):
        e.append("weights_texture must be a /Game/ path")
    o = r.get("landscape_origin_cm")
    if not (isinstance(o, list) and len(o) == 2 and all(_num(x) for x in o)):
        e.append("landscape_origin_cm must be [x, y]")
    if not (isinstance(r.get("weightmap_pixels"), int) and r["weightmap_pixels"] > 1):
        e.append("weightmap_pixels must be an int > 1")
    if not (_num(r.get("pixel_cm")) and r["pixel_cm"] > 0):
        e.append("pixel_cm must be > 0")
    if r.get("channels") != CHANNELS:
        e.append("channels must be exactly %r (the world weightmap layout)" % CHANNELS)
    if not re.fullmatch(r"/Game/[A-Za-z0-9_/]+", str(r.get("cavity_texture", ""))):
        e.append("cavity_texture must be a /Game/ path")
    rm = r.get("rock_modulation") or {}
    if sorted(rm) != ["B", "G", "R"]:
        e.append("rock_modulation must have exactly R, G, B")
    for ch, v in rm.items():
        t = (v or {}).get("tint")
        if not (isinstance(t, list) and len(t) == 3 and all(_num(x) and 0.0 <= x <= 2.0 for x in t)):
            e.append("rock_modulation.%s.tint must be 3 numbers in [0, 2]" % ch)
        if not (_num((v or {}).get("strength")) and 0.0 <= v["strength"] <= 1.0):
            e.append("rock_modulation.%s.strength must be in [0, 1]" % ch)
    L = r.get("layers") or {}
    if sorted(L) != sorted(LAYERS):
        e.append("layers must be exactly %s" % (LAYERS,))
    for k in LAYERS:
        v = L.get(k) or {}
        c = v.get("color_linear")
        if not (isinstance(c, list) and len(c) == 3 and all(_num(x) and 0.0 <= x <= 1.0 for x in c)):
            e.append("layers.%s.color_linear must be 3 numbers in [0, 1]" % k)
        if not (_num(v.get("roughness")) and 0.0 <= v["roughness"] <= 1.0):
            e.append("layers.%s.roughness must be in [0, 1]" % k)
    # Audit F3 (non-negotiable 24): values copied from the world recipe must still
    # equal it, or this recipe has drifted silently.
    try:
        w = json.load(io.open(os.path.join(bootstrap.REPO_ROOT, "recipes", "alpine_8k.json"),
                              encoding="utf-8"))
        ls = w["landscape"]
        loc = ls.get("location_cm") or ls.get("location")
        if loc is not None and [float(loc[0]), float(loc[1])] != [float(x) for x in r.get("landscape_origin_cm", [])]:
            e.append("landscape_origin_cm %r != alpine_8k landscape location %r" % (r.get("landscape_origin_cm"), loc[:2]))
        if float(ls["scale_xy_cm"]) != float(r.get("pixel_cm", -1)):
            e.append("pixel_cm != alpine_8k landscape.scale_xy_cm %s" % ls["scale_xy_cm"])
        res = (w.get("heightmap") or {}).get("resolution")
        if res is not None and int(res) != int(r.get("weightmap_pixels", -1)):
            e.append("weightmap_pixels != alpine_8k heightmap.resolution %s" % res)
        wl = dict((l["name"], l) for l in w["material"]["layers"])
        for k in LAYERS:
            if k in wl and float(wl[k]["roughness"]) != float(((r.get("layers") or {}).get(k) or {}).get("roughness", -1)):
                e.append("layers.%s.roughness != alpine_8k material layer roughness %s" % (k, wl[k]["roughness"]))
        if loc is None:
            e.append("alpine_8k landscape location not found -- cannot cross-check the origin")
        cv = w["material"]["cavity"]
        src = {"R": (cv["tint"], cv["strength"]), "G": (cv["lichen"]["tint"], cv["lichen"]["strength"]),
               "B": (cv["damp"]["tint"], cv["damp"]["strength"])}
        for ch, (t, st) in src.items():
            v = (r.get("rock_modulation") or {}).get(ch) or {}
            if [float(x) for x in v.get("tint", [])] != [float(x) for x in t] or float(v.get("strength", -1)) != float(st):
                e.append("rock_modulation.%s != alpine_8k material.cavity (%s, %s)" % (ch, t, st))
        if cv.get("layers") != ["Rock"]:
            e.append("alpine_8k cavity applies to %r; this material models Rock only" % cv.get("layers"))
    except (OSError, ValueError, KeyError) as x:
        e.append("cannot cross-check against recipes/alpine_8k.json: %s" % x)
    return e


PAYLOAD = material_graph.CLEAR_SRC + material_graph.WIRE_SRC + material_graph.ASSERT_SRC + r'''
import json as _json
import unreal as _u
_R = _json.loads(__RECIPE__)
_out = dict(ok=False)
try:
    _mel = _u.MaterialEditingLibrary
    _eal = _u.EditorAssetLibrary
    _tex = _eal.load_asset(_R["weights_texture"])
    if _tex is None:
        raise RuntimeError("weights texture missing: " + _R["weights_texture"])
    # Preflight BEFORE the clear (audit F2): LINEAR_COLOR is the engine's choice for
    # this texture only if sRGB is off, the LOD group is not 8/16BitData and it is
    # not virtual-textured (MaterialExpressionUtils.cpp:25-47).
    _tx = dict(srgb=bool(_tex.get_editor_property("srgb")),
               compression=str(_tex.get_editor_property("compression_settings")),
               lod_group=str(_tex.get_editor_property("lod_group")),
               vt=bool(_tex.get_editor_property("virtual_texture_streaming")))
    _out["texture"] = _tx
    _NOT_LC = ("NORMALMAP", "GRAYSCALE", "ALPHA", "MASKS", "DISTANCE_FIELD_FONT")
    if (_tx["srgb"] or _tx["vt"] or "8BIT_DATA" in _tx["lod_group"] or "16BIT_DATA" in _tx["lod_group"]
            or any(_k in _tx["compression"] for _k in _NOT_LC)):
        raise RuntimeError("weights texture state does not admit LINEAR_COLOR: " + str(_tx))
    _ctex = _eal.load_asset(_R["cavity_texture"])
    if _ctex is None:
        raise RuntimeError("cavity texture missing: " + _R["cavity_texture"])
    _ctx = dict(srgb=bool(_ctex.get_editor_property("srgb")),
                compression=str(_ctex.get_editor_property("compression_settings")),
                lod_group=str(_ctex.get_editor_property("lod_group")),
                vt=bool(_ctex.get_editor_property("virtual_texture_streaming")))
    _out["cavity_texture"] = _ctx
    if (_ctx["srgb"] or _ctx["vt"] or "8BIT_DATA" in _ctx["lod_group"] or "16BIT_DATA" in _ctx["lod_group"]
            or any(_k in _ctx["compression"] for _k in _NOT_LC)):
        raise RuntimeError("cavity texture state does not admit LINEAR_COLOR: " + str(_ctx))
    _path = _R["material_path"]
    _dir, _name = _path.rsplit("/", 1)
    if _eal.does_asset_exist(_path):
        _mat = _eal.load_asset(_path)
    else:
        _mat = _u.AssetToolsHelpers.get_asset_tools().create_asset(
            _name, _dir, _u.Material, _u.MaterialFactoryNew())
    if _mat is None:
        raise RuntimeError("material neither loadable nor creatable: " + _path)
    _c = _ll_clear_graph(_mel, _mat)
    _out["clear"] = _c
    if _c["remaining"]:
        raise RuntimeError("graph not empty after total clear")

    def _n(_cls, _x, _y):
        return _mel.create_material_expression(_mat, _cls, _x, _y)

    def _const(_v, _x, _y):
        _e = _n(_u.MaterialExpressionConstant, _x, _y)
        _e.set_editor_property("r", float(_v))
        return _e

    def _const3(_v, _x, _y):
        _e = _n(_u.MaterialExpressionConstant3Vector, _x, _y)
        _e.set_editor_property("constant", _u.LinearColor(float(_v[0]), float(_v[1]), float(_v[2]), 1.0))
        return _e

    # uv = (wp.xy - origin + pixel/2) / (pixels * pixel)
    _wp = _n(_u.MaterialExpressionWorldPosition, -1800, 0)
    _xy = _n(_u.MaterialExpressionComponentMask, -1600, 0)
    for _ch, _on in (("r", True), ("g", True), ("b", False), ("a", False)):
        _xy.set_editor_property(_ch, _on)
    _ll_wire(_mel, _wp, "", _xy, "")
    _half = 0.5 * float(_R["pixel_cm"])
    _off = _n(_u.MaterialExpressionConstant2Vector, -1600, 120)
    _off.set_editor_property("r", -float(_R["landscape_origin_cm"][0]) + _half)
    _off.set_editor_property("g", -float(_R["landscape_origin_cm"][1]) + _half)
    _add = _n(_u.MaterialExpressionAdd, -1400, 0)
    _ll_wire(_mel, _xy, "", _add, "A")
    _ll_wire(_mel, _off, "", _add, "B")
    _div = _n(_u.MaterialExpressionDivide, -1200, 0)
    _ll_wire(_mel, _add, "", _div, "A")
    _ll_wire(_mel, _const(float(_R["weightmap_pixels"]) * float(_R["pixel_cm"]), -1400, 160), "", _div, "B")

    _ts = _n(_u.MaterialExpressionTextureSample, -1000, 0)
    _ts.set_editor_property("texture", _tex)
    # AutoSetSampleType fires on texture assignment (MaterialExpressions.cpp:2627-2631):
    # read the ENGINE's choice before writing ours, and refuse on disagreement.
    _auto = _ts.get_editor_property("sampler_type")
    _out["sampler_auto"] = str(_auto)
    if _auto != _u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR:
        raise RuntimeError("engine picked sampler " + str(_auto) + ", expected LINEAR_COLOR")
    _ts.set_editor_property("sampler_type", _u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    _ll_wire(_mel, _div, "", _ts, "UVs")

    # grass = saturate(1 - (r + g + b + a))
    _s1 = _n(_u.MaterialExpressionAdd, -760, 300)
    _ll_wire(_mel, _ts, "R", _s1, "A"); _ll_wire(_mel, _ts, "G", _s1, "B")
    _s2 = _n(_u.MaterialExpressionAdd, -620, 300)
    _ll_wire(_mel, _s1, "", _s2, "A"); _ll_wire(_mel, _ts, "B", _s2, "B")
    _s3 = _n(_u.MaterialExpressionAdd, -480, 300)
    _ll_wire(_mel, _s2, "", _s3, "A"); _ll_wire(_mel, _ts, "A", _s3, "B")
    _om = _n(_u.MaterialExpressionOneMinus, -340, 300)
    _ll_wire(_mel, _s3, "", _om, "")
    _gr = _n(_u.MaterialExpressionSaturate, -200, 300)
    _ll_wire(_mel, _om, "", _gr, "")

    # Rock modulation: prod_ch (1 + cav_ch * strength_ch * (tint_ch - 1)) -- algebraically
    # lerp(1, tint, cav * strength), the near material's cavity/lichen/damp formula.
    _cs = _n(_u.MaterialExpressionTextureSample, -1000, 1400)
    _cs.set_editor_property("texture", _ctex)
    _cauto = _cs.get_editor_property("sampler_type")
    _out["cavity_sampler_auto"] = str(_cauto)
    if _cauto != _u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR:
        raise RuntimeError("engine picked cavity sampler " + str(_cauto) + ", expected LINEAR_COLOR")
    _cs.set_editor_property("sampler_type", _u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    _ll_wire(_mel, _div, "", _cs, "UVs")
    _mod = None
    _yy = 1400
    for _ch in ("R", "G", "B"):
        _rm = _R["rock_modulation"][_ch]
        _k = [float(_rm["strength"]) * (float(_t) - 1.0) for _t in _rm["tint"]]
        _mk = _n(_u.MaterialExpressionMultiply, -760, _yy)
        _ll_wire(_mel, _cs, _ch, _mk, "A")
        _ll_wire(_mel, _const3(_k, -900, _yy + 60), "", _mk, "B")
        _one = _n(_u.MaterialExpressionAdd, -600, _yy)
        _ll_wire(_mel, _mk, "", _one, "A")
        _ll_wire(_mel, _const(1.0, -760, _yy + 60), "", _one, "B")
        if _mod is None:
            _mod = _one
        else:
            _mm = _n(_u.MaterialExpressionMultiply, -440, _yy)
            _ll_wire(_mel, _mod, "", _mm, "A")
            _ll_wire(_mel, _one, "", _mm, "B")
            _mod = _mm
        _yy += 160
    _rockw = _n(_u.MaterialExpressionMultiply, -300, 1400)
    _ll_wire(_mel, _ts, "G", _rockw, "A")
    _ll_wire(_mel, _mod, "", _rockw, "B")

    _w = dict(Snow=(_ts, "R"), Rock=(_ts, "G"), Scree=(_ts, "B"), ForestFloor=(_ts, "A"), Grass=(_gr, ""))
    # Colour uses the MODULATED rock weight; roughness keeps the plain weight.
    _wc = dict(_w, Rock=(_rockw, ""))
    _col_acc = None
    _rgh_acc = None
    _y = -600
    for _k in ("Snow", "Rock", "Scree", "ForestFloor", "Grass"):
        _src, _pin = _w[_k]
        _L = _R["layers"][_k]
        _mc = _n(_u.MaterialExpressionMultiply, -100, _y)
        _csrc, _cpin = _wc[_k]
        _ll_wire(_mel, _csrc, _cpin, _mc, "A")
        _ll_wire(_mel, _const3(_L["color_linear"], -300, _y), "", _mc, "B")
        _mr = _n(_u.MaterialExpressionMultiply, -100, _y + 900)
        _ll_wire(_mel, _src, _pin, _mr, "A")
        _ll_wire(_mel, _const(_L["roughness"], -300, _y + 900), "", _mr, "B")
        if _col_acc is None:
            _col_acc, _rgh_acc = _mc, _mr
        else:
            _a1 = _n(_u.MaterialExpressionAdd, 100, _y)
            _ll_wire(_mel, _col_acc, "", _a1, "A"); _ll_wire(_mel, _mc, "", _a1, "B")
            _a2 = _n(_u.MaterialExpressionAdd, 100, _y + 900)
            _ll_wire(_mel, _rgh_acc, "", _a2, "A"); _ll_wire(_mel, _mr, "", _a2, "B")
            _col_acc, _rgh_acc = _a1, _a2
        _y += 140

    if not _mel.connect_material_property(_col_acc, "", _u.MaterialProperty.MP_BASE_COLOR):
        raise RuntimeError("connect BaseColor failed")
    if not _mel.connect_material_property(_rgh_acc, "", _u.MaterialProperty.MP_ROUGHNESS):
        raise RuntimeError("connect Roughness failed")

    _mat.set_editor_property("used_with_nanite", True)
    _a = _ll_assert_graph(_mel, _mat, [_R["weights_texture"], _R["cavity_texture"]])
    _out["assert"] = _a
    if not _a["exact"]:
        raise RuntimeError("graph does not match spec")
    _errs = _mel.recompile_material(_mat)
    _out["compile_errors"] = [str(_x) for _x in (_errs or [])]
    if _out["compile_errors"]:
        raise RuntimeError("compile errors: " + str(_out["compile_errors"]))
    # The return can be empty while the compile is still running
    # (make_foliage_material lesson): record the material's own state too.
    for _probe in ("is_compiling_or_had_compile_error", "get_material_resource_compile_errors"):
        _fn = getattr(_mat, _probe, None)
        if _fn is not None:
            try:
                _out["material_state_" + _probe] = str(_fn())
            except Exception as _e:
                _out["material_state_" + _probe] = "READ FAILED: " + type(_e).__name__
    _ll_must.must_save(_path, _eal)
    _m2 = _eal.load_asset(_path)
    _out["readback"] = dict(
        used_with_nanite=bool(_m2.get_editor_property("used_with_nanite")),
        n_expressions=len(list(_mel.get_material_expressions(_m2))),
        samplers=_ll_assert_graph(_mel, _m2, [_R["weights_texture"], _R["cavity_texture"]])["got"])
    _out["ok"] = bool(_out["readback"]["used_with_nanite"] and _a["exact"]
                      and not _out["compile_errors"])
except Exception:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    r = json.load(io.open(a.recipe, encoding="utf-8"))
    errs = validate(r)
    if errs:
        print("REFUSE:\n  " + "\n  ".join(errs))
        return 2
    clean = dict((k, v) for k, v in r.items() if not k.startswith("_"))
    src = PAYLOAD.replace("__RECIPE__", repr(json.dumps(clean)))
    src = ("import os as _os, sys as _sys\n"
           "_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n"
           "import ll_must as _ll_must\n") + src
    compile(src, "payload", "exec")
    if a.dry_run:
        print("dry run: recipe valid; payload %d bytes compiles" % len(src))
        return 0
    import ue_exec
    out_dir = os.path.join(bootstrap.REPO_ROOT, "_verify", "hlod_override")
    os.makedirs(out_dir, exist_ok=True)
    io.open(os.path.join(out_dir, "build_payload.txt"), "w", encoding="utf-8").write(src)
    code, out, raw = ue_exec.run(src, marker="__LL__", timeout=25, stage_name="hlod_override")
    if not isinstance(out, dict):
        print("FAIL (code %s): COULD NOT LOOK\n%s" % (code, (raw or "")[-1500:]))
        return 4
    io.open(os.path.join(out_dir, "build_result.json"), "w", encoding="utf-8").write(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
