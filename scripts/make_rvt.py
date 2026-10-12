"""make_rvt.py -- Runtime Virtual Texture assets, volumes and landscape binding.

    python scripts/make_rvt.py [--recipe recipes/rvt_lookdev.json] [--dry-run] [--apply [--assets-only]]

--assets-only (2026-10-04): step 2 only, from ANY level -- a world's RVT assets
must exist before its RVT-blend materials and landscape material are built,
and those shader builds run on a light level, never beside the 8K world.

Stage B of research/rvt_lookdev_design.md. Without --apply nothing is sent to
the editor (dry run = recipe validation + the planned transform). With --apply,
in the editor, idempotent:
  1. refuse unless r.VirtualTextures reads 1 and the open level is `level`;
  2. find-or-create each RVT asset (RuntimeVirtualTextureFactory); set
     material_type, tile_size, tile_count (adaptive is never touched: setting
     it re-clamps tile_count), compress_textures; save; READ BACK;
  3. find-or-spawn one RuntimeVirtualTextureVolume per RVT, identified by actor
     TAG (never by label); set virtual_texture_component.virtual_texture; set
     the actor transform by hand -- the unit-cube volume maps location = min
     corner, scale3d = size (RuntimeVirtualTextureSetBounds.cpp:84-88); READ BACK;
  4. set the landscape parent's runtime_virtual_textures to the RVTs in recipe
     order (LandscapeOverridable: propagates to proxies that did not override);
     READ BACK on the parent and on every streaming proxy.
Saving the landscape proxies is left to the existing save payload
(brief7_save_landscape_proxies_payload), run by the caller after this.
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

DEFAULT = os.path.join(bootstrap.REPO_ROOT, "recipes", "rvt_lookdev.json")
TYPES = {"BASE_COLOR", "MASK4", "BASE_COLOR_NORMAL_ROUGHNESS", "BASE_COLOR_NORMAL_SPECULAR",
         "BASE_COLOR_NORMAL_SPECULAR_Y_CO_CG", "BASE_COLOR_NORMAL_SPECULAR_MASK_Y_CO_CG",
         "WORLD_HEIGHT", "DISPLACEMENT"}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate(r):
    e = []
    for k in ("schema_version", "level", "asset_dir", "bounds_cm", "textures", "main_pass"):
        if k not in r:
            e.append("missing %r" % k)
    if e:
        return e
    if r["main_pass"] not in ("NEVER", "EXCLUSIVE", "ALWAYS"):
        e.append("main_pass must be NEVER, EXCLUSIVE or ALWAYS")
    if r["schema_version"] != "rvt-1.0":
        e.append("schema_version must be rvt-1.0")
    if not str(r["asset_dir"]).startswith("/Game/"):
        e.append("asset_dir must be a /Game/ path")
    b = r["bounds_cm"]
    if not (isinstance(b, dict) and all(isinstance(b.get(k), list) and len(b[k]) == 3
                                        and all(_num(x) for x in b[k]) for k in ("min", "size"))
            and all(x > 0 for x in b["size"])):
        e.append("bounds_cm must be {min: [x,y,z], size: [x,y,z] > 0}")
    tx = r["textures"]
    if not (isinstance(tx, list) and tx):
        return e + ["textures must be a non-empty list"]
    names, tags = set(), set()
    for t in tx:
        tag = "textures[%r]" % t.get("name")
        if not re.fullmatch(r"[A-Za-z0-9_]+", str(t.get("name", ""))):
            e.append(tag + ".name must match [A-Za-z0-9_]+")
        if not re.fullmatch(r"[A-Za-z0-9_]+", str(t.get("tag", ""))):
            e.append(tag + ".tag must match [A-Za-z0-9_]+")
        if t.get("material_type") not in TYPES:
            e.append(tag + ".material_type must be one of %s" % sorted(TYPES))
        if not (isinstance(t.get("tile_count"), int) and not isinstance(t.get("tile_count"), bool)
                and 1 <= t["tile_count"] <= 12):
            e.append(tag + ".tile_count must be an int log2 in [1, 12]")
        if not (isinstance(t.get("tile_size"), int) and not isinstance(t.get("tile_size"), bool)
                and 0 <= t["tile_size"] <= 4):
            e.append(tag + ".tile_size must be an int in [0, 4] (64..1024 px)")
        if not isinstance(t.get("compress_textures"), bool):
            e.append(tag + ".compress_textures must be a bool")
        if t.get("name") in names or t.get("tag") in tags:
            e.append(tag + ": duplicate name or tag")
        names.add(t.get("name")); tags.add(t.get("tag"))
    return e


PAYLOAD = r'''
import json as _json
import os as _os
import sys as _sys
import unreal as _u
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ll_must as _ll_must
_R = _json.loads(__RECIPE__)
_AO = __ASSETS_ONLY__
_out = dict(ok=False, assets=[], volumes=[], landscape=None)
try:
    if _u.SystemLibrary.get_console_variable_int_value("r.VirtualTextures") != 1:
        raise RuntimeError("r.VirtualTextures is not 1")
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    _lvl = _w.get_path_name().split(".")[0]
    if not _AO and _lvl != _R["level"]:
        raise RuntimeError("open level is " + _lvl + ", recipe wants " + _R["level"])
    _eal = _u.EditorAssetLibrary
    _at = _u.AssetToolsHelpers.get_asset_tools()
    _rvts = []
    for _t in _R["textures"]:
        _p = _R["asset_dir"] + "/" + _t["name"]
        if _eal.does_asset_exist(_p):
            _a = _eal.load_asset(_p)
        else:
            _a = _at.create_asset(_t["name"], _R["asset_dir"], _u.RuntimeVirtualTexture,
                                  _u.RuntimeVirtualTextureFactory())
        if _a is None:
            raise RuntimeError("RVT asset neither loadable nor creatable: " + _p)
        _a.set_editor_property("material_type",
                               getattr(_u.RuntimeVirtualTextureMaterialType, _t["material_type"]))
        _a.set_editor_property("tile_size", int(_t["tile_size"]))
        _a.set_editor_property("tile_count", int(_t["tile_count"]))
        _a.set_editor_property("compress_textures", bool(_t["compress_textures"]))
        _ll_must.must_save(_p, _eal)
        _c = _eal.load_asset(_p)
        _rb = dict(material_type=str(_c.get_editor_property("material_type")),
                   tile_size=_c.get_editor_property("tile_size"),
                   tile_count=_c.get_editor_property("tile_count"),
                   compress=_c.get_editor_property("compress_textures"),
                   size_px=_c.get_size())
        _ok = (_c.get_editor_property("material_type") == getattr(
                   _u.RuntimeVirtualTextureMaterialType, _t["material_type"])
               and _rb["tile_size"] == _t["tile_size"] and _rb["tile_count"] == _t["tile_count"]
               and _rb["compress"] == _t["compress_textures"])
        _out["assets"].append(dict(path=_p, readback=_rb, ok=bool(_ok)))
        _rvts.append(_c)
    if _AO:
        # --assets-only: the RVT assets carry no level state, so they can be
        # created from a light level before the world is loaded (2026-10-04).
        _out["assets_only"] = True
        _out["ok"] = bool(_out["assets"]) and all(x["ok"] for x in _out["assets"])
    else:
        _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
        _acts = _sub.get_all_level_actors()
        _mn = _R["bounds_cm"]["min"]
        _sz = _R["bounds_cm"]["size"]
        for _t, _a in zip(_R["textures"], _rvts):
            _tag = _t["tag"]
            _found = [x for x in _acts if isinstance(x, _u.RuntimeVirtualTextureVolume)
                      and _tag in [str(g) for g in x.tags]]
            if len(_found) > 1:
                raise RuntimeError("more than one volume tagged " + _tag)
            if _found:
                _v = _found[0]
            else:
                _v = _sub.spawn_actor_from_class(_u.RuntimeVirtualTextureVolume,
                                                 _u.Vector(_mn[0], _mn[1], _mn[2]))
                _v.tags = [_u.Name(_tag)]
                _v.set_actor_label(_tag)
            _comp = _v.get_editor_property("virtual_texture_component")
            _comp.set_editor_property("virtual_texture", _a)
            _v.set_actor_location(_u.Vector(_mn[0], _mn[1], _mn[2]), False, False)
            _v.set_actor_rotation(_u.Rotator(0.0, 0.0, 0.0), False)
            _v.set_actor_scale3d(_u.Vector(_sz[0], _sz[1], _sz[2]))
            _l = _v.get_actor_location(); _s = _v.get_actor_scale3d()
            _vt = _comp.get_editor_property("virtual_texture")
            _ok = (_vt is not None and _vt.get_path_name() == _a.get_path_name()
                   and all(abs(a - b) < 0.5 for a, b in zip([_l.x, _l.y, _l.z], _mn))
                   and all(abs(a - b) < 0.5 for a, b in zip([_s.x, _s.y, _s.z], _sz)))
            _out["volumes"].append(dict(tag=_tag, label=_v.get_actor_label(),
                                        location=[_l.x, _l.y, _l.z], scale=[_s.x, _s.y, _s.z],
                                        rvt=_vt.get_path_name() if _vt else None, ok=bool(_ok)))
        _ls = [x for x in _acts if isinstance(x, _u.Landscape)]
        if len(_ls) != 1:
            raise RuntimeError("expected exactly one Landscape parent, found " + str(len(_ls)))
        _ls[0].set_editor_property("runtime_virtual_textures", _rvts)
        # Pinned, not left to the default (review 2026-10-03; LandscapeProxy.h:663).
        _ls[0].set_editor_property("virtual_texture_render_pass_type",
                                   getattr(_u.RuntimeVirtualTextureMainPassType, _R["main_pass"]))
        _want = [a.get_path_name() for a in _rvts]
        _px = [x for x in _acts if isinstance(x, _u.LandscapeStreamingProxy)]
        _got_parent = [a.get_path_name() for a in _ls[0].get_editor_property("runtime_virtual_textures")]
        _px_ok = sum(1 for x in _px if [a.get_path_name() for a in
                     x.get_editor_property("runtime_virtual_textures")] == _want)
        _pt = str(_ls[0].get_editor_property("virtual_texture_render_pass_type"))
        _out["landscape"] = dict(parent=_got_parent == _want, proxies=len(_px), proxies_ok=_px_ok,
                                 render_pass_type=_pt)
        _out["ok"] = (all(x["ok"] for x in _out["assets"]) and all(x["ok"] for x in _out["volumes"])
                      and _out["landscape"]["parent"] and len(_px) > 0 and _px_ok == len(_px)
                      and _R["main_pass"] in _pt)
except Exception:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=DEFAULT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--assets-only", action="store_true",
                    help="with --apply: create/read back the RVT assets only; no level check, "
                         "no volumes, no landscape binding (any open level)")
    ap.add_argument("--dry-run", action="store_true", help="the default; explicit form")
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args(argv)
    r = json.load(io.open(a.recipe, encoding="utf-8"))
    errs = validate(r)
    if errs:
        print("REFUSE:\n  " + "\n  ".join(errs))
        return 2
    clean = dict((k, v) for k, v in r.items() if not k.startswith("_"))
    print("plan: %d RVT(s); volume min %s size %s" % (len(r["textures"]), r["bounds_cm"]["min"],
                                                       r["bounds_cm"]["size"]))
    if a.assets_only and not a.apply:
        print("REFUSE: --assets-only needs --apply")
        return 2
    if not a.apply:
        print("dry run: nothing sent (pass --apply)")
        return 0
    import ue_exec
    # Flag token first: the recipe text pasted after it can never be rewritten
    # by a later replace (audit 2026-10-04, finding 2).
    src = PAYLOAD.replace("__ASSETS_ONLY__", repr(bool(a.assets_only)))
    src = src.replace("__RECIPE__", repr(json.dumps(clean)))
    out_dir = os.path.join(bootstrap.REPO_ROOT, "_verify", "rvt")
    os.makedirs(out_dir, exist_ok=True)
    io.open(os.path.join(out_dir, "make_rvt_payload.txt"), "w", encoding="utf-8").write(src)
    code, out, raw = ue_exec.run(src, marker="__LL__", timeout=a.timeout, stage_name="make_rvt")
    if not isinstance(out, dict):
        print("FAIL (code %s): COULD NOT LOOK\n%s" % (code, (raw or "")[-1500:]))
        return 4
    io.open(os.path.join(out_dir, "make_rvt_result.json"), "w", encoding="utf-8").write(
        json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
