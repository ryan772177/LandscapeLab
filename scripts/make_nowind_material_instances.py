"""make_nowind_material_instances.py — wind-off child MIs, zero vendor edits.

WHY
---
The PN spruce materials ANIMATE. Measured 2026-08-15, three frames 5 s apart
from one parked camera with no Blueprint in the level: the difference image
is a clean silhouette of the tree, sky and static ground plane black
(`_verify/20260815_pn_wind_is_live.md`). An animating canopy makes every
pixel A/B non-deterministic, and this project's whole method is
single-variable frame comparison against a floor in the third decimal place.

WHY NOT JUST EDIT THE VENDOR MATERIAL
-------------------------------------
`PN_interactiveSpruceForest` is gitignored with **0 tracked files**. An edit
to `MA_Summer` or to a vendor MI vanishes on re-download and git cannot
restore it — RECIPES' Fab-boundary rule names exactly this shape as its
worked example. So nothing here writes a vendor byte. It creates CHILD
instances in a tracked folder and leaves the pack identical.

WHY STATIC SWITCHES AND NOT SCALARS
-----------------------------------
Wind rides STATIC SWITCH parameters — `Level 1/2/3 Wind` and the three
`Bending` siblings — measured on `MA_Summer`, `MA_Winter` and `MA_Imposter`
by `scripts/probe_material.py`. A static switch set false COMPILES THE
BRANCH OUT; a scalar set to zero still evaluates the branch every frame.
Switching is both cheaper and more certain.

`Bending` is switched off with `Wind` deliberately. It is the same
interactive-animation system (driven by `PN_Bending_Component`), and a
second animated path left on would reintroduce exactly the
non-determinism this exists to remove. `Plant or Tree` and `Snow` are NOT
touched — they select an appearance, not a motion.

FAILING CLOSED
--------------
A switch that is not present on the parent chain is a REFUSAL, not a
silent skip. Silently skipping is how a "wind-off" material ships with the
wind on, and the name would then assert something no longer true. Every
switch is READ BACK from the created asset after being set, and a
disagreement refuses.

Exit codes:
  0  every instance created, every switch set and read back false
  2  bad arguments, or a mesh/material could not be resolved
  3  editor gate refused (conduct rule 7)
  4  a switch was missing on the parent chain, or read back wrong
  5  no parseable result — I could not look
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MARKER = "__LANDSCAPELAB_NOWIND__"

# The six switches. ONE DECLARATION, consumed by both the payload and the
# read-back assertion, because two lists that must agree are one list badly
# stored (non-negotiable 24).
WIND_SWITCHES = [
    "Level 1 Wind", "Level 2 Wind", "Level 3 Wind",
    "Level 1 Bending", "Level 2 Bending", "Level 3 Bending",
]

DEST_DIR = "/Game/Materials/PN_NoWind"

# `--apply-in-open-level` refuses these. A material override written onto an
# actor in a real world is scene state that outlives the process and that no
# recipe declares, which pipeline rule 2 forbids.
REAL_WORLD_GUARD = ["/Game/Alpine", "/Game/GaeaLab", "/Game/AlpineLab"]

# Default targets: the two meshes the recipe scatters. Named here rather
# than discovered, so this tool cannot quietly widen its blast radius.
DEFAULT_MESHES = [
    "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01",
    "/Game/PN_interactiveSpruceForest/Meshes/small/spruce_small_05",
]

PAYLOAD = '''
import json as _json
import unreal as _unreal

_MESHES = {meshes!r}
_SWITCHES = {switches!r}
_DEST = {dest!r}
_DRY = {dry!r}

_out = {{"ok": False, "error": None, "meshes": []}}
try:
    _mel = _unreal.MaterialEditingLibrary
    _eal = _unreal.EditorAssetLibrary
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()

    if not _DRY and not _eal.does_directory_exist(_DEST):
        _eal.make_directory(_DEST)

    for _mp in _MESHES:
        _row = {{"mesh": _mp, "ok": False, "slots": []}}
        if not _eal.does_asset_exist(_mp):
            _row["error"] = "mesh does not exist"
            _out["meshes"].append(_row)
            continue
        _mesh = _eal.load_asset(_mp)
        if _mesh is None:
            _row["error"] = "load_asset returned None"
            _out["meshes"].append(_row)
            continue

        # Slot ORDER is the contract: override_materials is positional, so
        # the list handed to the FoliageType must be in slot order with no
        # holes. Read it from static_materials rather than rebuilt.
        _sms = _mesh.static_materials
        for _i, _sm in enumerate(_sms):
            _slot = {{"index": _i, "source": None, "created": None,
                      "switches": {{}}, "error": None}}
            try:
                _src = _sm.material_interface
            except Exception as _ex:
                _slot["error"] = "no material_interface: " + str(_ex)[:100]
                _row["slots"].append(_slot)
                continue
            if _src is None:
                _slot["error"] = "slot has no material"
                _row["slots"].append(_slot)
                continue
            _slot["source"] = _src.get_path_name()
            _name = _src.get_name()
            _new_name = "MI_" + _name + "_nowind"
            _new_path = _DEST + "/" + _new_name
            _slot["created"] = _new_path

            # Which of the six the PARENT actually declares. A switch the
            # parent does not have cannot be turned off, and pretending
            # otherwise is the failure this tool refuses on.
            try:
                _have = set(str(_n) for _n
                            in _mel.get_static_switch_parameter_names(_src))
            except Exception as _ex:
                _slot["error"] = "could not read parent switches: " + str(_ex)[:100]
                _row["slots"].append(_slot)
                continue
            _missing = [_s for _s in _SWITCHES if _s not in _have]
            if _missing:
                _slot["error"] = "parent lacks switches: " + ", ".join(_missing)
                _row["slots"].append(_slot)
                continue

            if _DRY:
                _slot["ok"] = True
                _row["slots"].append(_slot)
                continue

            if _eal.does_asset_exist(_new_path):
                _mi = _eal.load_asset(_new_path)
            else:
                _mi = _tools.create_asset(
                    _new_name, _DEST, _unreal.MaterialInstanceConstant,
                    _unreal.MaterialInstanceConstantFactoryNew())
            if _mi is None:
                _slot["error"] = "create_asset returned None"
                _row["slots"].append(_slot)
                continue

            _mel.set_material_instance_parent(_mi, _src)
            for _s in _SWITCHES:
                _mel.set_material_instance_static_switch_parameter_value(
                    _mi, _s, False)
            _mel.update_material_instance(_mi)
            _eal.save_asset(_new_path)

            # READ BACK from the saved asset, reloaded, not from the object
            # we just wrote to.
            _eal.load_asset(_new_path)
            _chk = _eal.load_asset(_new_path)
            for _s in _SWITCHES:
                try:
                    _v = _mel.get_material_instance_static_switch_parameter_value(
                        _chk, _s)
                    _slot["switches"][_s] = bool(_v)
                except Exception as _ex:
                    _slot["switches"][_s] = "READ FAILED: " + str(_ex)[:60]
            _bad = [_k for _k, _v in _slot["switches"].items() if _v is not False]
            if _bad:
                _slot["error"] = "read back NOT false: " + ", ".join(_bad)
            else:
                _slot["ok"] = True
            _row["slots"].append(_slot)

        _row["ok"] = bool(_row["slots"]) and all(
            _s.get("ok") for _s in _row["slots"])
        _row["overrides"] = [_s.get("created") for _s in _row["slots"]]
        _out["meshes"].append(_row)

    _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


# Applying the overrides to actors in the OPEN level, so the claim can be
# tested by a DIFFERENT INSTRUMENT than the one that made it.
#
# Reading the six switches back off the asset only proves the setter wrote
# the field it was told to write (non-negotiable 8). The claim being made is
# "the canopy no longer moves", and the only instrument that answers that is
# a render: park a camera, shoot frames seconds apart, diff. This flag exists
# to make that test possible without hand-editing a level.
#
# SCRATCH LEVELS ONLY. It refuses to touch a real world, because a material
# override written onto an actor in /Game/Alpine8K is scene state that
# outlives the process and did not come from a recipe (pipeline rule 2).
APPLYPAYLOAD = '''
import json as _json
import unreal as _unreal

_MAP = {mapping!r}
_GUARD = {guard!r}

_out = {{"ok": False, "error": None, "level": None, "applied": []}}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _lvl = _les.get_current_level()
    _wname = _lvl.get_outer().get_path_name() if _lvl else "?"
    _out["level"] = _wname
    _bad = [_g for _g in _GUARD if _g in _wname]
    if _bad:
        _out["error"] = ("REFUSE: '" + _wname + "' is a real world, not a "
                         "scratch level. Overrides applied to actors there "
                         "are scene state no recipe declares.")
    else:
        _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
        for _a in _eas.get_all_level_actors():
            _comp = _a.get_component_by_class(_unreal.StaticMeshComponent)
            if _comp is None:
                continue
            _sm = _comp.static_mesh
            if _sm is None:
                continue
            _p = _sm.get_path_name().split(".")[0]
            _ovr = _MAP.get(_p)
            if not _ovr:
                continue
            _mats = []
            for _mp in _ovr:
                _m = _unreal.EditorAssetLibrary.load_asset(_mp)
                _mats.append(_m)
            if any(_m is None for _m in _mats):
                _out["applied"].append({{"actor": _a.get_actor_label(),
                                         "error": "an override failed to load"}})
                continue
            _comp.set_editor_property("override_materials", _mats)
            _back = [_x.get_path_name().split(".")[0] if _x else None
                     for _x in _comp.get_editor_property("override_materials")]
            _out["applied"].append({{
                "actor": _a.get_actor_label(), "mesh": _p,
                "wrote": len(_mats),
                "read_back_matches": _back == [_o.split(".")[0]
                                               for _o in _ovr]}})
        _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mesh", action="append", default=None,
                    help="/Game path to a StaticMesh (repeatable).")
    ap.add_argument("--apply-in-open-level", action="store_true",
                    help="Set the created overrides on matching actors in "
                         "the OPEN level, so the wind-off claim can be "
                         "tested by RENDER rather than by reading back the "
                         "field the setter wrote. Scratch levels only.")
    ap.add_argument("--dest", default=DEST_DIR)
    ap.add_argument("--go", action="store_true",
                    help="Create the assets. Without this it is a dry run "
                         "that only checks the parents carry the switches.")
    ap.add_argument("--out", default=os.path.join(
        REPO_ROOT, "Free", "_measured", "pn_nowind_overrides.json"))
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args(argv)

    meshes = args.mesh or DEFAULT_MESHES

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("dest      : {0}   (OURS, tracked — no vendor byte is written)"
          .format(args.dest))
    print("switches  : {0}".format(", ".join(WIND_SWITCHES)))
    print("meshes    : {0}".format(len(meshes)))
    print("mode      : {0}".format("CREATE" if args.go else "DRY RUN"))
    print("")

    payload = PAYLOAD.format(meshes=meshes, switches=WIND_SWITCHES,
                             dest=args.dest, dry=(not args.go),
                             marker=MARKER)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(payload, unattended=True,
                              exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r) if r else ""
        apply_text = None
        if args.apply_in_open_level and args.go:
            # Built from the SAME parsed result the report below prints, so
            # the overrides applied and the overrides reported cannot differ.
            i0 = (text or "").find(MARKER)
            pre = None
            if i0 >= 0:
                try:
                    pre, _ = json.JSONDecoder().raw_decode(
                        text[i0 + len(MARKER):].lstrip())
                except ValueError:
                    pre = None
            mp = {}
            for row in (pre or {}).get("meshes", []):
                if row.get("ok") and row.get("overrides"):
                    mp[row["mesh"]] = row["overrides"]
            if mp:
                ap_payload = APPLYPAYLOAD.format(
                    mapping=mp, guard=REAL_WORLD_GUARD, marker=MARKER)
                r2 = remote.run_command(ap_payload, unattended=True,
                                        exec_mode=remote_exec.MODE_EXEC_FILE)
                apply_text = bootstrap._collect_output(r2) if r2 else ""
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    i = (text or "").find(MARKER)
    if i < 0:
        print("REFUSE: no marker — I could not look.")
        print(text[-1500:] if text else "(no output at all)")
        return 5
    try:
        got, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    except ValueError:
        print("REFUSE: unparseable result.")
        return 5

    if got.get("error"):
        print("REFUSE: payload error: {0}".format(got["error"]))
        return 5

    rc = 0
    mapping = {}
    for row in got.get("meshes", []):
        name = row["mesh"].rsplit("/", 1)[-1]
        print("{0}".format(row["mesh"]))
        if row.get("error"):
            print("   REFUSE: {0}".format(row["error"]))
            rc = max(rc, 2)
            continue
        for s in row.get("slots", []):
            src = (s.get("source") or "?").rsplit("/", 1)[-1].split(".")[0]
            if s.get("error"):
                print("   [{0}] {1:<34} REFUSE: {2}".format(
                    s["index"], src, s["error"]))
                rc = max(rc, 4)
                continue
            if not args.go:
                print("   [{0}] {1:<34} parent carries all {2} switches"
                      .format(s["index"], src, len(WIND_SWITCHES)))
                continue
            print("   [{0}] {1:<34} -> {2}   all {3} switches read back FALSE"
                  .format(s["index"], src,
                          (s.get("created") or "?").rsplit("/", 1)[-1],
                          len(WIND_SWITCHES)))
        if row.get("ok") and args.go:
            mapping[row["mesh"]] = row.get("overrides")
        print("")

    if not args.go:
        print("DRY RUN. Nothing created. Re-run with --go.")
        return rc

    if rc == 0 and mapping:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"dest": args.dest, "switches": WIND_SWITCHES,
                       "overrides_by_mesh": mapping}, fh, indent=2)
            fh.write("\n")
        print("wrote {0}".format(os.path.relpath(args.out, REPO_ROOT)))
        print("")
        print("The override list is POSITIONAL and in slot order. Whatever "
              "consumes it must hand it to FoliageType.override_materials "
              "unchanged — a reordered list silently repaints the tree.")

    if args.apply_in_open_level and args.go:
        print("")
        print("--- applying to the OPEN level (so a RENDER can test this) ---")
        j = (apply_text or "").find(MARKER)
        if j < 0:
            print("REFUSE: no marker from the apply step — I could not look.")
            return max(rc, 5)
        try:
            ap_got, _ = json.JSONDecoder().raw_decode(
                apply_text[j + len(MARKER):].lstrip())
        except ValueError:
            print("REFUSE: unparseable apply result.")
            return max(rc, 5)
        print("level: {0}".format(ap_got.get("level")))
        if ap_got.get("error"):
            print(ap_got["error"])
            return max(rc, 2)
        if not ap_got.get("applied"):
            print("NOTHING APPLIED — no actor in this level uses those "
                  "meshes. That is 'I could not test it', not 'it passed'.")
            return max(rc, 5)
        for a in ap_got["applied"]:
            if a.get("error"):
                print("  {0:<28} REFUSE: {1}".format(a["actor"], a["error"]))
                rc = max(rc, 4)
            else:
                print("  {0:<28} {1} override(s), read back matches: {2}"
                      .format(a["actor"], a["wrote"],
                              a["read_back_matches"]))
                if not a["read_back_matches"]:
                    rc = max(rc, 4)
        print("")
        print("NOW TAKE THE RENDER. Three frames seconds apart from one "
              "parked camera and diff them; that — not the switch read-back "
              "above — is what proves the canopy stopped moving.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
