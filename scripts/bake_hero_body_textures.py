"""bake_hero_body_textures.py — give the hero a body skin from the stock maps.

WHY STOCK AND NOT HIS OWN
    MetaHuman's editor exports the FACE atlas only -- "Save Face Textures" is
    the whole of it, confirmed by opening the exported basecolor, which is a
    face UV layout, and by Ryan reading the menu: there is no body equivalent.
    Meanwhile the character's body_textures map went TRANSIENT after the rig
    (before it, those entries pointed at real stock assets), and a transient
    texture cannot be duplicated into a real package -- measured 2026-08-16, the
    copy reloads as nothing.

    So the body gets MetaHuman's SHIPPED body maps: real assets, already on
    disk, no export needed. The result is his face on a generic body skin, which
    is a deliberate and stated trade, not an accident.

HOW THE MAPS ARE CHOSEN
    By SEARCHING the asset registry and scoring names, not by pasting paths read
    off a screen hours ago. The tool prints what it picked and why, and refuses
    rather than binding a map it is not confident about.

USAGE
    python scripts/bake_hero_body_textures.py          # dry run, shows picks
    python scripts/bake_hero_body_textures.py --go
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ue_exec  # noqa: E402

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_out = {"error": None, "unreadable": [], "candidates": {}, "chosen": {},
        "bound": [], "verify": {}, "dry_run": __DRY__}

_MEL = _unreal.MaterialEditingLibrary
_BODY = "/Game/Hero/Generated/SKM_HeroBody"
_MIDEST = "/Game/Hero/Generated/Materials"
_SEARCH = ["/MetaHumanCharacter/Optional/BodyTextures",
           "/MetaHumanCharacter/Textures"]


def _score(_name, _want):
    """Score a texture name for a role. Higher is better; 0 means reject."""
    _n = _name.lower()
    if _want == "basecolor":
        if not ("_bc" in _n or "basecolor" in _n or "_d" == _n[-2:]):
            return 0
        _s = 10
    elif _want == "normal":
        if not (_n.endswith("_n") or "normal" in _n):
            return 0
        _s = 10
    elif _want == "cavity":
        if not (_n.endswith("_ca") or "cavity" in _n):
            return 0
        _s = 10
    else:
        return 0
    # Prefer torso/body maps over underwear or accessory maps.
    if "underwear" in _n:
        return 0
    if "chest" in _n or "body" in _n:
        _s += 5
    if "skin" in _n:
        _s += 3
    return _s


try:
    _ar = _unreal.AssetRegistryHelpers.get_asset_registry()
    _found = []
    for _dir in _SEARCH:
        for _a in _ar.get_assets_by_path(_dir, recursive=True):
            _cls = str(_a.asset_class_path.asset_name)
            if "Texture" not in _cls:
                continue
            _found.append(str(_a.package_name))
    _out["searched"] = len(_found)

    for _role in ("basecolor", "normal", "cavity"):
        _ranked = []
        for _p in _found:
            _nm = _p.rsplit("/", 1)[-1]
            _s = _score(_nm, _role)
            if _s > 0:
                _ranked.append((_s, _p))
        _ranked.sort(reverse=True)
        _out["candidates"][_role] = [_p for _s, _p in _ranked[:6]]
        _out["chosen"][_role] = _ranked[0][1] if _ranked else None

    if _out["dry_run"]:
        raise SystemExit

    _missing = [_r for _r, _p in _out["chosen"].items() if not _p]
    if _missing:
        raise RuntimeError("no stock map found for: " + ", ".join(_missing))

    _mesh = _unreal.EditorAssetLibrary.load_asset(_BODY)
    if _mesh is None:
        raise RuntimeError("body mesh did not load")
    _mats = _mesh.get_editor_property("materials")
    _new = []
    for _i, _sm in enumerate(_mats):
        _mi = _sm.get_editor_property("material_interface")
        _p = _mi.get_path_name() if _mi is not None else None
        # Idempotence, same lesson as the face bake: on a re-run the slot holds
        # OUR instance, and taking it as the parent makes it its own parent.
        if _p and "MI_HeroBody_" in _p:
            _up = _mi.get_editor_property("parent")
            if _up is not None:
                _mi = _up
                _p = _mi.get_path_name()
        if _p and "Skin_Body" in _p:
            _name = "MI_HeroBody_%d" % _i
            _full = _MIDEST + "/" + _name
            _inst = _unreal.EditorAssetLibrary.load_asset(_full)
            if _inst is None:
                _inst = _unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    _name, _MIDEST, _unreal.MaterialInstanceConstant,
                    _unreal.MaterialInstanceConstantFactoryNew())
            _inst.set_editor_property("parent", _mi)
            _tpvs = []
            for _pname, _role in (("Basecolor", "basecolor"),
                                  ("Normal", "normal"),
                                  ("Cavity", "cavity"),
                                  ("Color_CHEST", "basecolor"),
                                  ("Cavity_Chest", "cavity")):
                _tex = _unreal.EditorAssetLibrary.load_asset(
                    _out["chosen"][_role])
                if _tex is None:
                    continue
                _info = _unreal.MaterialParameterInfo()
                _info.set_editor_property("name", _pname)
                _tpv = _unreal.TextureParameterValue()
                _tpv.set_editor_property("parameter_info", _info)
                _tpv.set_editor_property("parameter_value", _tex)
                _tpvs.append(_tpv)
                _out["bound"].append({"param": _pname,
                                      "texture": _out["chosen"][_role]})
            # DIRECT ARRAY WRITE. MaterialEditingLibrary's setter returns False
            # for these exact names even though the enumerator lists them --
            # measured on the face bake, same master material.
            _inst.set_editor_property("texture_parameter_values", _tpvs)
            _MEL.update_material_instance(_inst)
            _unreal.EditorAssetLibrary.save_asset(_full, only_if_is_dirty=False)
            _sm.set_editor_property("material_interface", _inst)
        _new.append(_sm)
    _mesh.set_editor_property("materials", _new)
    _unreal.EditorAssetLibrary.save_asset(_BODY, only_if_is_dirty=False)

    # VERIFY BY RELOADING.
    _rl = _unreal.EditorAssetLibrary.load_asset(_BODY)
    _bad = 0
    _ours = 0
    _read = {}
    for _sm in _rl.get_editor_property("materials"):
        _mi = _sm.get_editor_property("material_interface")
        _p = _mi.get_path_name() if _mi is not None else None
        if _p is None or _p.startswith("/Engine/Transient"):
            _bad += 1
        if _p and "MI_HeroBody_" in _p:
            _ours += 1
            _fresh = _unreal.EditorAssetLibrary.load_asset(_p.split(".")[0])
            for _e2 in _fresh.get_editor_property("texture_parameter_values"):
                _pi = _e2.get_editor_property("parameter_info")
                _tx = _e2.get_editor_property("parameter_value")
                _read[str(_pi.get_editor_property("name"))] = (
                    _tx.get_path_name() if _tx else None)
    _out["verify"] = {"transient_or_null": _bad, "hero_body_instances": _ours,
                      "readback": _read}

except SystemExit:
    pass
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)

print("__LL__" + _json.dumps(_out, default=str))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args(argv)

    text = PAYLOAD.replace("__DRY__", "False" if args.go else "True")
    rc, d, _raw = ue_exec.run(text, stage_name="bake_hero_body_textures",
                              timeout=120.0)
    if d is None:
        return 1 if rc != 3 else 3
    print(json.dumps(d, indent=2, default=str)[:5000])
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1
    if not args.go:
        print("\nDRY RUN. Nothing written. Re-run with --go.")
        return 0
    v = d.get("verify") or {}
    if v.get("transient_or_null"):
        print("FAIL: %d slots transient or null" % v["transient_or_null"])
        return 1
    if not v.get("hero_body_instances"):
        print("FAIL: no body material instance was bound")
        return 1
    print("\nOK: body carries %d hero instance(s)." % v["hero_body_instances"])
    print("STATED PLAINLY: these are MetaHuman's SHIPPED body maps, not his.")
    print("The editor exports the face atlas only; there is no body export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
