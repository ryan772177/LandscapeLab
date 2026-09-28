"""bake_hero_face_textures.py — give the hero his skin.

WHAT THIS SOLVES, AND WHY IT TOOK A DETOUR
    A Python-built MetaHuman is UNTEXTURED WHITE. MetaHuman's Assemble is not
    reflected in 5.8, its skin lives in parameter OVERRIDES on a dynamic
    material instance whose getter hard-refuses that type, and the synthesized
    textures are transient objects that CANNOT be duplicated into real packages
    -- the copy reloads as nothing. All three measured 2026-08-16.

    The way through is the editor's own **Save Face Textures** command, which
    Ryan ran: it writes the synthesized maps out as PNG FILES on disk. Those are
    ordinary images, and everything downstream is ordinary asset work.

    So this tool: imports those PNGs with per-role settings, builds material
    instances parented to the face's real parent materials, binds the maps, and
    assigns them to the mesh.

ROLE IS DECIDED BY FILENAME, AND THE SETTINGS DIFFER PER ROLE
    A normal map imported as sRGB colour is wrong in a way that renders without
    complaint -- this project has a whole recipe about sampler/colour-space
    mismatches. So:

        *_Normal*   sRGB OFF, TC_NORMALMAP
        *_Cavity*   sRGB OFF, TC_MASKS      (a data map, not a picture)
        otherwise   sRGB ON,  TC_DEFAULT    (basecolour and its deltas)

USAGE
    python scripts/bake_hero_face_textures.py            # dry run
    python scripts/bake_hero_face_textures.py --go

Exit codes:
    0  built (or dry run)
    1  payload error or a verification failed
    2  bad arguments / source textures missing
    3  rule 7: no verified editor node
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

SRC_DIR = os.path.join(bootstrap.REPO_ROOT, "hero", "generated", "Textures")
DEST = "/Game/Hero/Generated/Textures"
FACE_MESH = "/Game/Hero/Generated/SKM_HeroFace"
MI_DEST = "/Game/Hero/Generated/Materials"

PAYLOAD = r'''
import json as _json
import unreal as _unreal
import os as _os
import sys as _sys
# ⭐ ll_must IS IMPORTED, NOT PASTED. ue_exec stages it beside this
# payload; MODE_EXEC_FILE gives us __file__, so the stage dir is on the
# path below. Placed HERE, at the top, so a staging failure raises
# before any graph is touched rather than half way through a build.
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ll_must as _ll_must

_out = {"error": None, "unreadable": [], "imported": [], "slots": [],
        "verify": [], "dry_run": __DRY__}

_SRC = __SRC_LIST__
_DEST = "__DEST__"
_MESH = "__FACE_MESH__"
_MIDEST = "__MI_DEST__"
_MEL = _unreal.MaterialEditingLibrary
_TOOLS = _unreal.AssetToolsHelpers.get_asset_tools()


def _role(_name):
    _n = _name.lower()
    if "normal" in _n:
        return "normal"
    if "cavity" in _n:
        return "cavity"
    return "color"


try:
    # ---------- 1. import the PNGs ----------
    _by_role = {}
    for _path in _SRC:
        _name = _path.replace("\\", "/").rsplit("/", 1)[-1]
        _stem = _name[:-4] if _name.lower().endswith(".png") else _name
        _asset = "T_" + _stem
        _full = _DEST + "/" + _asset
        _r = _role(_stem)
        _rec = {"file": _name, "asset": _full, "role": _r}
        if _out["dry_run"]:
            _rec["action"] = "would import"
            _out["imported"].append(_rec)
            _by_role.setdefault(_r, []).append((_stem, None))
            continue

        _t = _unreal.AssetImportTask()
        _t.set_editor_property("filename", _path)
        _t.set_editor_property("destination_path", _DEST)
        _t.set_editor_property("destination_name", _asset)
        _t.set_editor_property("automated", True)
        _t.set_editor_property("replace_existing", True)
        _t.set_editor_property("save", False)
        _TOOLS.import_asset_tasks([_t])
        _tex = _unreal.EditorAssetLibrary.load_asset(_full)
        _rec["imported"] = _tex is not None
        if _tex is not None:
            # PER-ROLE SETTINGS. A normal map imported as sRGB colour renders
            # without complaining and is wrong.
            if _r == "normal":
                _tex.set_editor_property("srgb", False)
                _tex.set_editor_property(
                    "compression_settings",
                    _unreal.TextureCompressionSettings.TC_NORMALMAP)
            elif _r == "cavity":
                _tex.set_editor_property("srgb", False)
                _tex.set_editor_property(
                    "compression_settings",
                    _unreal.TextureCompressionSettings.TC_MASKS)
            else:
                _tex.set_editor_property("srgb", True)
                _tex.set_editor_property(
                    "compression_settings",
                    _unreal.TextureCompressionSettings.TC_DEFAULT)
            # CHECKED SAVE. The srgb/compression read-back below is
            # an in-memory property read and cannot see a failed write.
            _ll_must.must_save(_full, _unreal.EditorAssetLibrary)
            # READ BACK off the asset, not off the setter.
            _rec["srgb"] = bool(_tex.get_editor_property("srgb"))
            _rec["compression"] = str(
                _tex.get_editor_property("compression_settings"))
            _by_role.setdefault(_r, []).append((_stem, _tex))
        _out["imported"].append(_rec)

    if _out["dry_run"]:
        raise SystemExit

    # Pick the PRIMARY map of each role -- the one without an "Animated" delta
    # suffix. The deltas drive expression-dependent detail and are not the base.
    def _primary(_r):
        _c = _by_role.get(_r) or []
        for _stem, _tex in _c:
            if "animated" not in _stem.lower():
                return _tex
        return _c[0][1] if _c else None

    _base = _primary("color")
    _norm = _primary("normal")
    _cav = _primary("cavity")
    _out["primary"] = {
        "basecolor": _base.get_path_name() if _base else None,
        "normal": _norm.get_path_name() if _norm else None,
        "cavity": _cav.get_path_name() if _cav else None,
    }

    # ---------- 2. material instances on the face's SKIN slots ----------
    _mesh = _unreal.EditorAssetLibrary.load_asset(_MESH)
    if _mesh is None:
        raise RuntimeError("face mesh did not load: " + _MESH)
    _mats = _mesh.get_editor_property("materials")
    _new_list = []
    for _i, _sm in enumerate(_mats):
        _mi = _sm.get_editor_property("material_interface")
        _p = _mi.get_path_name() if _mi is not None else None
        # IDEMPOTENCE: on a re-run the slot already holds OUR instance, and
        # taking it as the parent makes the instance its own parent. Walk up to
        # the real MetaHuman material instead. Measured 2026-08-16: the second
        # run wrote MI_HeroFace_14 as MI_HeroFace_14's own parent.
        if _p and "MI_HeroFace_" in _p:
            _up = _mi.get_editor_property("parent")
            if _up is not None:
                _mi = _up
                _p = _mi.get_path_name()
        _rec = {"slot": _i, "parent": _p}
        # Only the SKIN slots get the face maps. Eyes, teeth, eyelashes and the
        # M_Hide slots have their own materials and must not be overwritten.
        if _p and "Skin_Head" in _p:
            _name = "MI_HeroFace_%d" % _i
            _full = _MIDEST + "/" + _name
            _inst = _unreal.EditorAssetLibrary.load_asset(_full)
            if _inst is None:
                _inst = _TOOLS.create_asset(
                    _name, _MIDEST, _unreal.MaterialInstanceConstant,
                    _unreal.MaterialInstanceConstantFactoryNew())
            if _inst is not None:
                _inst.set_editor_property("parent", _mi)
                _bound = []
                # WRITE THE OVERRIDE ARRAY DIRECTLY.
                # MaterialEditingLibrary.set_material_instance_texture_parameter_value
                # returns FALSE for every one of these names -- measured
                # 2026-08-16 against "Basecolor", "Normal", "Cavity" and their
                # VT variants, under both GLOBAL and LAYER_PARAMETER
                # association -- even though all three ARE present in the 80
                # names get_texture_parameter_names reports on the same
                # instance. The setter refusing a name the enumerator lists is
                # the trap; the underlying array does not go through it.
                _tpvs = []
                for _pname, _tex in (("Basecolor", _base), ("Normal", _norm),
                                     ("Cavity", _cav)):
                    if _tex is None:
                        continue
                    try:
                        _info = _unreal.MaterialParameterInfo()
                        _info.set_editor_property("name", _pname)
                        _tpv = _unreal.TextureParameterValue()
                        _tpv.set_editor_property("parameter_info", _info)
                        _tpv.set_editor_property("parameter_value", _tex)
                        _tpvs.append(_tpv)
                        _bound.append(_pname)
                    except Exception as _e:
                        _out["unreadable"].append(
                            "slot %d %s: %s" % (_i, _pname, _e))
                if _tpvs:
                    _inst.set_editor_property("texture_parameter_values", _tpvs)
                _MEL.update_material_instance(_inst)
                _unreal.EditorAssetLibrary.save_asset(
                    _full, only_if_is_dirty=False)
                _sm.set_editor_property("material_interface", _inst)
                _rec["instance"] = _full
                _rec["bound"] = _bound
        _new_list.append(_sm)
        _out["slots"].append(_rec)

    _mesh.set_editor_property("materials", _new_list)
    _unreal.EditorAssetLibrary.save_asset(_MESH, only_if_is_dirty=False)

    # ---------- 3. verify by RELOADING ----------
    _rl = _unreal.EditorAssetLibrary.load_asset(_MESH)
    _tr = _real = _skin = 0
    for _sm in _rl.get_editor_property("materials"):
        _mi = _sm.get_editor_property("material_interface")
        _p = _mi.get_path_name() if _mi is not None else None
        if _p is None or _p.startswith("/Engine/Transient"):
            _tr += 1
        else:
            _real += 1
        if _p and "MI_HeroFace_" in _p:
            _skin += 1
    # RELOAD one of the instances and read its override array. "bound" above is
    # what was ASKED for; this is what the asset actually carries.
    _bound_back = {}
    for _sm in _rl.get_editor_property("materials"):
        _mi = _sm.get_editor_property("material_interface")
        _p = _mi.get_path_name() if _mi is not None else None
        if not (_p and "MI_HeroFace_" in _p):
            continue
        _fresh = _unreal.EditorAssetLibrary.load_asset(_p.split(".")[0])
        if _fresh is None:
            continue
        try:
            for _e2 in _fresh.get_editor_property("texture_parameter_values"):
                _pi = _e2.get_editor_property("parameter_info")
                _tx = _e2.get_editor_property("parameter_value")
                _bound_back[str(_pi.get_editor_property("name"))] = (
                    _tx.get_path_name() if _tx is not None else None)
        except Exception as _e:
            _out["unreadable"].append("readback: " + str(_e))
        break
    _out["verify"] = {"slots": _tr + _real, "transient_or_null": _tr,
                      "real": _real, "hero_skin_instances": _skin,
                      "readback_params": _bound_back}

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

    src = sorted(glob.glob(os.path.join(SRC_DIR, "*.png")))
    if not src:
        print("REFUSE: no PNGs in %s" % SRC_DIR)
        print("        Run 'Save Face Textures' in the MetaHuman editor first;")
        print("        it is the only route to these maps (measured 2026-08-16).")
        return 2
    print("source textures: %d in %s" % (len(src), SRC_DIR))
    for p in src:
        print("  %s" % os.path.basename(p))

    text = (PAYLOAD
            .replace("__SRC_LIST__", repr([p.replace("\\", "/") for p in src]))
            .replace("__DEST__", DEST)
            .replace("__FACE_MESH__", FACE_MESH)
            .replace("__MI_DEST__", MI_DEST)
            .replace("__DRY__", "False" if args.go else "True"))

    rc, d, _raw = ue_exec.run(text, stage_name="bake_hero_face_textures",
                              timeout=90.0)
    if d is None:
        return 1 if rc != 3 else 3
    print(json.dumps(d, indent=2, default=str)[:6000])
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1
    for u in d.get("unreadable", []):
        print("UNREADABLE:", u)
    if not args.go:
        print("\nDRY RUN. Nothing written. Re-run with --go.")
        return 0

    v = d.get("verify") or {}
    if v.get("transient_or_null"):
        print("FAIL: %d slots still transient or null" % v["transient_or_null"])
        return 1
    if not v.get("hero_skin_instances"):
        print("FAIL: no hero skin material instances were bound")
        return 1
    print("\nOK: %d slots, %d real, %d carrying the hero's own skin."
          % (v.get("slots"), v.get("real"), v.get("hero_skin_instances")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
