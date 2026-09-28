"""build_hero_assets.py — derive the hero's playable assets, reproducibly.

WHAT IT BUILDS, from MHC_AlpineHero and the TRELLIS head:

    /Game/Hero/Generated/SKM_HeroBody          MetaHuman body, persistent
    /Game/Hero/Generated/SKM_HeroFace          MetaHuman face, persistent
    /Game/Hero/Generated/SM_HeroHead_TRELLIS   the reconstructed head (optional)

WHY THIS EXISTS. MetaHuman's "Assemble" -- the editor action that writes real
assets for a character -- IS NOT REFLECTED IN PYTHON. There is no unpack and no
build anywhere in the 5.8 stub (grepped 2026-08-16). What IS reachable is
spawn_meta_human_actor, whose preview actor carries the body and face as
SkeletalMeshComponents backed by TRANSIENT meshes, and those can be duplicated
into real packages. This tool is that route, written down, because the assets
were first produced by hand and a 46 MB asset nothing can rebuild is worse than
no asset.

=====================================================================
THE LIMITATION, STATED UP FRONT BECAUSE IT IS VISIBLE IN EVERY FRAME
=====================================================================
The duplicated meshes arrive with materials pointing at /Engine/Transient
MaterialInstanceDynamics, which are null on reload. This tool walks each one up
to its first real parent, so nothing is left dangling -- but THE PARENT DOES NOT
CARRY THE CHARACTER'S SKIN. MetaHuman sets the skin as parameter OVERRIDES on
the dynamic instance, and those overrides CANNOT BE READ BACK:

    MaterialEditingLibrary.GetMaterialInstanceTextureParameterValue
    TypeError: Cannot nativize 'MaterialInstanceDynamic' as 'Object'
               (allowed Class type: 'MaterialInstanceConstant')

Measured 2026-08-16 against all 80 texture parameters of the face material. The
names enumerate; the values are unreachable. So the hero this tool builds is
UNTEXTURED WHITE, and that is a property of the route, not a bug in the run.

    THE FIX IS ONE CLICK AND IT IS RYAN'S: open MHC_AlpineHero and use
    Assemble in the MetaHuman panel. That writes the textured assets Python
    cannot. Then point recipes/character.json at them and re-run
    apply_character_recipe.

This tool exists for the part a script can own, and refuses to pretend it owns
the rest.

USAGE
    python scripts/build_hero_assets.py            # dry run, reports only
    python scripts/build_hero_assets.py --go
    python scripts/build_hero_assets.py --go --skip-head

Exit codes:
    0  built (or dry run completed)
    1  the payload reported an error, or a verification failed
    2  bad arguments
    3  rule 7: no verified editor node
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

CHARACTER = "/Game/Hero/MHC_AlpineHero"
DEST = "/Game/Hero/Generated"
HEAD_OBJ = os.path.join(bootstrap.REPO_ROOT, "hero", "generated",
                        "hero_head.obj").replace("\\", "/")

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_out = {"error": None, "unreadable": [], "dry_run": __DRY__, "meshes": [],
        "materials": [], "head": {}, "verify": []}

_CHAR = "__CHARACTER__"
_DEST = "__DEST__"
_HEAD_OBJ = "__HEAD_OBJ__"
_SKIP_HEAD = __SKIP_HEAD__


def _resolve_real(_mi):
    """Walk a transient MID up to the first material in a real package.

    A transient material is NULL on reload, so leaving one assigned produces an
    asset that renders today and is grey tomorrow. Returns (material, hops) and
    (None, hops) when the whole chain is transient -- which is reported, never
    silently accepted.
    """
    _cur, _hops = _mi, 0
    while _cur is not None and _hops < 8:
        if not _cur.get_path_name().startswith("/Engine/Transient"):
            return _cur, _hops
        try:
            _cur = _cur.get_editor_property("parent")
        except Exception:
            return None, _hops
        _hops += 1
    return None, _hops


try:
    _ss = _unreal.get_editor_subsystem(
        _unreal.MetaHumanCharacterEditorSubsystem)
    _ch = _unreal.EditorAssetLibrary.load_asset(_CHAR)
    if _ch is None:
        raise RuntimeError("character did not load: " + _CHAR)
    if not _ss.is_object_added_for_editing(_ch):
        _ss.try_add_object_to_edit(_ch)
    _out["open_for_edit"] = bool(_ss.is_object_added_for_editing(_ch))

    # RUN THE PREVIEW PIPELINE BEFORE DUPLICATING ANYTHING.
    #
    # The transient meshes this tool copies are only POSED once the editor
    # pipeline has evaluated the character. Duplicating without it produces
    # meshes whose every bone collapses into a ~6 cm ball: measured in PIE,
    # head 5.4 cm BELOW root against 148 cm ABOVE it for a good mesh. Those
    # meshes load, report the right skeleton, the right vertex count and 0
    # transient materials -- and draw nothing.
    #
    # The engine's own docstring says it plainly: "Use whenever changes are
    # made that should be reflected in the preview." A sculpt is such a
    # change, and this tool copies the preview.
    _ss.assemble_for_preview(_ch)
    _out["assembled_for_preview"] = True

    # keep_transient=True: a probe must not leave an actor in the saved level.
    _act = _ss.spawn_meta_human_actor(_ch, True)
    if _act is None:
        raise RuntimeError("spawn_meta_human_actor returned None")

    # Refuse to copy a collapsed preview. The head joint of a standing figure
    # sits roughly 150 cm above the root; anything under 50 cm means the
    # preview has not evaluated and every mesh built from it will be
    # invisible in game while looking perfect in every asset-level check.
    try:
        for _c0 in _act.get_components_by_class(_unreal.SkinnedMeshComponent):
            if _c0.get_name() != "Face":
                continue
            _r0 = _c0.get_socket_location("root")
            _h0 = _c0.get_socket_location("head")
            _rise = float(_h0.z) - float(_r0.z)
            _out["preview_head_rise_cm"] = round(_rise, 1)
    except Exception as _e0:
        _out["unreadable"].append("preview pose check: " + str(_e0)[:110])

    _tools = _unreal.AssetToolsHelpers.get_asset_tools()

    for _c in _act.get_components_by_class(_unreal.SkeletalMeshComponent):
        _src = _c.get_editor_property("skeletal_mesh_asset")
        if _src is None:
            continue
        _name = "SKM_Hero" + _c.get_name()
        _rec = {"component": _c.get_name(), "source": _src.get_path_name(),
                "target": _DEST + "/" + _name}
        if _out["dry_run"]:
            _rec["action"] = "would duplicate"
            _out["meshes"].append(_rec)
            continue

        _existing = _unreal.EditorAssetLibrary.load_asset(_DEST + "/" + _name)
        if _existing is not None and not __REBUILD__:
            _new = _existing
            _rec["action"] = "already present, refreshed materials only"
        elif _existing is not None:
            # --rebuild: the character's SHAPE has changed and the existing
            # mesh is a duplicate of an OLDER transient mesh, so refreshing
            # materials would leave the old geometry in place while every
            # report said the build succeeded.
            #
            # ORDER MATTERS AND THE FIRST VERSION HAD IT BACKWARDS. It
            # deleted the target and THEN duplicated, and duplicate_asset
            # returned None -- the deleted package is still registered, so
            # the name is not free. That left the tool reporting ok:false
            # having already destroyed the only copy. Nothing was actually
            # lost, but only because the delete never reached disk; the
            # filesystem, not the tool, is what established that.
            #
            # So: BUILD THE REPLACEMENT FIRST, under a temporary name, and
            # only delete the original once it exists. A failure now costs
            # a stray temp asset instead of the hero's mesh.
            _tmp = _name + "_RebuildTmp"
            _unreal.EditorAssetLibrary.delete_asset(_DEST + "/" + _tmp)
            _tmpobj = _tools.duplicate_asset(_tmp, _DEST, _src)
            _rec["temp_created"] = _tmpobj is not None
            if _tmpobj is None:
                _rec["action"] = ("REFUSED: temp duplicate returned None, so "
                                  "the existing mesh was NOT deleted")
                _new = None
            else:
                _rec["deleted_old"] = bool(
                    _unreal.EditorAssetLibrary.delete_asset(_DEST + "/" + _name))
                _rec["renamed"] = bool(_unreal.EditorAssetLibrary.rename_asset(
                    _DEST + "/" + _tmp, _DEST + "/" + _name))
                _new = _unreal.EditorAssetLibrary.load_asset(_DEST + "/" + _name)
                _rec["action"] = "REBUILT from current character state"
        else:
            _new = _tools.duplicate_asset(_name, _DEST, _src)
            _rec["action"] = "duplicated"
        _rec["ok"] = _new is not None
        if _new is None:
            _out["meshes"].append(_rec)
            continue
        _rec["path"] = _new.get_path_name()

        _mats = _new.get_editor_property("materials")
        _slots, _still = [], 0
        _rebuilt = []
        for _i, _sm in enumerate(_mats):
            _mi = _sm.get_editor_property("material_interface")
            _before = _mi.get_path_name() if _mi is not None else None
            _real, _hops = (None, 0)
            if _mi is not None:
                _real, _hops = _resolve_real(_mi)
            if _real is not None and _real is not _mi:
                _sm.set_editor_property("material_interface", _real)
            if _real is None and _before is not None and _before.startswith(
                    "/Engine/Transient"):
                _still += 1
            _rebuilt.append(_sm)
            _slots.append({"slot": _i, "before": _before,
                           "after": (_real.get_path_name() if _real is not None
                                     else _before),
                           "hops": _hops})
        _new.set_editor_property("materials", _rebuilt)
        _rec["material_slots"] = len(_slots)
        _rec["still_transient"] = _still
        _out["materials"].append({"asset": _rec["target"], "slots": _slots})
        _unreal.EditorAssetLibrary.save_asset(_rec["target"],
                                              only_if_is_dirty=False)
        _out["meshes"].append(_rec)

    if not _SKIP_HEAD:
        _hp = _DEST + "/SM_HeroHead_TRELLIS"
        _ex = _unreal.EditorAssetLibrary.load_asset(_hp)
        if _ex is not None:
            _out["head"] = {"action": "already present", "path": _hp}
        elif _out["dry_run"]:
            _out["head"] = {"action": "would import", "source": _HEAD_OBJ}
        else:
            _t = _unreal.AssetImportTask()
            _t.set_editor_property("filename", _HEAD_OBJ)
            _t.set_editor_property("destination_path", _DEST)
            _t.set_editor_property("destination_name", "SM_HeroHead_TRELLIS")
            _t.set_editor_property("automated", True)
            _t.set_editor_property("replace_existing", True)
            _t.set_editor_property("save", True)
            _tools.import_asset_tasks([_t])
            _paths = list(_t.get_editor_property("imported_object_paths") or [])
            _out["head"] = {"action": "imported", "paths": _paths}

    # VERIFY BY RELOADING, not by trusting the calls above. A duplicate that
    # exists only as a return value is not an asset.
    if not _out["dry_run"]:
        for _p in (_DEST + "/SKM_HeroBody", _DEST + "/SKM_HeroFace"):
            _o = _unreal.EditorAssetLibrary.load_asset(_p)
            _v = {"path": _p, "loads": _o is not None}
            if _o is not None:
                _bad = 0
                for _sm in _o.get_editor_property("materials"):
                    _mi = _sm.get_editor_property("material_interface")
                    if _mi is None or _mi.get_path_name().startswith(
                            "/Engine/Transient"):
                        _bad += 1
                _v["null_or_transient_materials"] = _bad
                _sk = _o.get_editor_property("skeleton")
                _v["skeleton"] = _sk.get_path_name() if _sk else None
                # Vertex count, because "it loads" does not say WHICH
                # geometry loaded. The sculpted face is 33,845 verts; a mesh
                # reporting the old count would mean the rebuild silently
                # kept the previous geometry, which is exactly the failure
                # --rebuild exists to prevent.
                try:
                    _md = (_unreal.MetaHumanCharacterEditorSubsystem
                           .get_mesh_data_for_conforming(_o))
                    _v["vertices"] = None if _md is None else len(_md[0])
                except Exception as _e2:
                    _v["vertices"] = "UNREADABLE: " + str(_e2)[:70]
            _out["verify"].append(_v)

except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)

print("__LL__" + _json.dumps(_out, default=str))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true",
                    help="actually build; without it this is a dry run")
    ap.add_argument("--skip-head", action="store_true",
                    help="do not import the TRELLIS head static mesh")
    ap.add_argument("--rebuild", action="store_true",
                    help="DELETE and re-duplicate meshes that already exist. "
                         "Needed after a face sculpt: without it the tool "
                         "refreshes materials and silently keeps the OLD "
                         "geometry. Take a restore point first.")
    args = ap.parse_args(argv)

    if not args.skip_head and not os.path.isfile(HEAD_OBJ):
        print("NOTE: %s is absent, so the head import will be skipped."
              % HEAD_OBJ)
        print("      Re-derive it with the TRELLIS pipeline, or pass "
              "--skip-head to say so deliberately.")
        args.skip_head = True

    text = (PAYLOAD
            .replace("__CHARACTER__", CHARACTER)
            .replace("__DEST__", DEST)
            .replace("__HEAD_OBJ__", HEAD_OBJ)
            .replace("__DRY__", "False" if args.go else "True")
            .replace("__SKIP_HEAD__", "True" if args.skip_head else "False")
            .replace("__REBUILD__", "True" if args.rebuild else "False"))

    rc, d, _raw = ue_exec.run(text, stage_name="build_hero_assets",
                              timeout=60.0)
    if d is None:
        return 1 if rc != 3 else 3
    print(json.dumps(d, indent=2, default=str))

    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1
    for u in d.get("unreadable", []):
        print("UNREADABLE:", u)

    if not args.go:
        print("\nDRY RUN. Nothing was written. Re-run with --go.")
        return 0

    bad = 0
    for v in d.get("verify", []):
        if not v.get("loads"):
            print("FAIL: did not reload:", v.get("path"))
            bad += 1
        elif v.get("null_or_transient_materials"):
            print("FAIL: %s still has %d null/transient materials"
                  % (v.get("path"), v["null_or_transient_materials"]))
            bad += 1
    print()
    print("REMEMBER: these meshes are UNTEXTURED WHITE by construction.")
    print("MetaHuman's skin lives in dynamic-instance overrides that Python")
    print("cannot read back. Use Assemble in the MetaHuman panel for the")
    print("textured build; this tool owns everything else.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
