"""probe_material.py — read a material's parameters, textures and compile state.

WHY THIS EXISTS
---------------
Two D2 questions had no instrument in `scripts/` (checked by listing it, per
CLAUDE.md step (a), before writing a line of this):

  1. Does `MA_Imposter` COMPILE in 5.8? The imposter is the entire reason
     `PN_interactiveSpruceForest` was chosen over four more pine variants,
     and "the asset is on disk" is not evidence that it builds. A material
     that fails to compile renders as UE's default checkerboard, which this
     project has already shipped once.
  2. Is the WIND an overridable PARAMETER, or is it wired into the graph?
     The answer decides whether wind can be removed by authoring our own
     Material Instances in a tracked folder (safe) or only by editing the
     vendor master (forbidden — the pack is gitignored with 0 tracked files,
     so an edit vanishes on re-download and git cannot restore it).

READ-ONLY BY DEFAULT, AND THE EXCEPTION IS DECLARED
---------------------------------------------------
Reporting parameters, textures and expression counts touches nothing.

`--recompile` is OPT-IN because `recompile_material` rebuilds shaders and
marks the package dirty. **This tool never saves.**

**AND DIRTY IS NOT THE END OF IT — MEASURED 2026-08-15.** Recompiling vendor
`MA_Imposter` left an AUTOSAVE behind. The editor was closed later that
session, the dirty package was correctly discarded at the Save prompt, and
the NEXT launch came up on a "Restore Packages" modal offering to restore
`MA_Imposter` from that autosave. A modal blocks the game thread, so it
blocks every remote-exec call and MCP tool until someone answers it.

So the real cost of `--recompile` on vendor content is: a dirty package, an
autosave on disk, and a modal on the next launch whose wrong answer
re-applies an edit to gitignored content git cannot restore. Answer it
**Skip Restore**. The warning below prints every run rather than relying on
the reader remembering, and it says all three consequences rather than only
the first — a warning that understates is the prose-rot class (NN25).

WHY THE RETURNED ARRAY AND NOT THE LOG
--------------------------------------
`MaterialEditingLibrary.recompile_material(material) -> Array[str]` RETURNS
the error list (PythonStub:431766). The editor log only says "Failed to
compile". This project learned that on 2026-08-10, when the returned list
named all five offending nodes in one call while the log named none.

An EMPTY returned array is a PASS. A material that could not be LOADED is
"I could not look" and is never reported as a pass (non-negotiable 6).

Exit codes:
  0  every probed asset read, and (if --recompile) compiled with 0 errors
  2  bad arguments
  3  editor gate refused (conduct rule 7)
  4  at least one material returned compile errors
  5  at least one asset could not be read -- I could not look
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
MARKER = "__LANDSCAPELAB_MATPROBE__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None}}
try:
    _p = {path!r}
    _recompile = {recompile!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _a = _unreal.EditorAssetLibrary.load_asset(_p)
        if _a is None:
            _out["error"] = "load_asset returned None"
        else:
            _out["asset_class"] = type(_a).__name__
            _mel = _unreal.MaterialEditingLibrary

            # Parent chain. A MaterialInstance's parent decides which master
            # actually compiles, so it is reported rather than assumed from
            # the folder name.
            try:
                _par = _a.get_editor_property("parent")
                _out["parent"] = _par.get_path_name() if _par else None
            except Exception:
                _out["parent"] = None

            # Parameter names. These are what an MI can override -- the
            # whole wind question.
            for _kind, _fn in (("scalar", _mel.get_scalar_parameter_names),
                               ("switch",
                                _mel.get_static_switch_parameter_names),
                               ("vector", _mel.get_vector_parameter_names),
                               ("texture",
                                _mel.get_texture_parameter_names)):
                try:
                    _out[_kind + "_params"] = sorted(
                        str(_n) for _n in _fn(_a))
                except Exception as _ex:
                    _out[_kind + "_params"] = None
                    _out[_kind + "_error"] = str(_ex)[:120]

            try:
                _out["used_textures"] = sorted(
                    _t.get_path_name() for _t in
                    _mel.get_material_used_textures(_a) if _t)
            except Exception as _ex:
                _out["used_textures"] = None
                _out["textures_error"] = str(_ex)[:120]

            # Expression count only means anything on a Material, not on an
            # instance -- an MI has no graph of its own.
            if isinstance(_a, _unreal.Material):
                try:
                    _out["expressions"] = int(
                        _mel.get_num_material_expressions(_a))
                except Exception as _ex:
                    _out["expressions"] = None
                    _out["expr_error"] = str(_ex)[:120]

            if _recompile and isinstance(_a, _unreal.Material):
                try:
                    _errs = _mel.recompile_material(_a)
                    _out["compile_errors"] = [str(_e) for _e in _errs]
                    _out["compiled"] = True
                except Exception as _ex:
                    _out["compiled"] = False
                    _out["compile_exception"] = str(_ex)[:300]
            _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''

# Which materials reference a given material FUNCTION. This is how the wind
# blast radius is measured rather than guessed at from names.
REFPAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"function": {path!r}, "ok": False, "error": None}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "function does not exist"
    else:
        _f = _unreal.EditorAssetLibrary.load_asset(_p)
        if _f is None:
            _out["error"] = "load_asset returned None"
        else:
            _rows = _unreal.MaterialEditingLibrary\\
                .get_materials_referencing_function(_f)
            _out["referencing"] = sorted(
                str(_r.get_editor_property("package_name")) for _r in _rows)
            _out["count"] = len(_out["referencing"])
            _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        got, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
        return got
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asset", action="append", default=None,
                    help="/Game path to a Material or MaterialInstance "
                         "(repeatable).")
    ap.add_argument("--function", action="append", default=None,
                    help="/Game path to a MaterialFunction; reports which "
                         "materials reference it (repeatable).")
    ap.add_argument("--recompile", action="store_true",
                    help="Recompile each Material and report the RETURNED "
                         "error list. May dirty the package. Never saves.")
    ap.add_argument("--timeout", type=int, default=40)
    args = ap.parse_args(argv)

    if not args.asset and not args.function:
        print("REFUSE: give at least one --asset or --function.")
        return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    if args.recompile:
        print("")
        print("--recompile IS ON. It marks the package DIRTY and leaves an "
              "AUTOSAVE on disk.")
        print("This tool never saves. On VENDOR content, expect all three:")
        print("  1. a dirty package  -> answer any Save prompt DON'T SAVE")
        print("  2. an autosave file -> the next editor launch shows a "
              "'Restore Packages' modal")
        print("  3. that modal BLOCKS the game thread, so remote exec and "
              "MCP both hang until answered -> answer it SKIP RESTORE")
    print("")

    rc = 0
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

        def run(src):
            r = remote.run_command(src, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            return bootstrap._collect_output(r) if r else ""

        for path in (args.asset or []):
            got = _parse(run(PAYLOAD.format(path=path, marker=MARKER,
                                            recompile=bool(args.recompile))))
            name = path.rsplit("/", 1)[-1]
            if got is None:
                print("{0:<34} COULD NOT LOOK (no parseable result)"
                      .format(name))
                rc = max(rc, 5)
                continue
            if not got.get("ok"):
                print("{0:<34} COULD NOT LOOK: {1}".format(
                    name, got.get("error")))
                rc = max(rc, 5)
                continue
            print("{0}  [{1}]".format(path, got.get("asset_class")))
            if got.get("parent"):
                print("    parent      {0}".format(got["parent"]))
            if got.get("expressions") is not None:
                print("    expressions {0}".format(got["expressions"]))
            for kind in ("scalar", "switch", "vector", "texture"):
                vals = got.get(kind + "_params")
                if vals is None:
                    print("    {0:<11} COULD NOT READ".format(kind))
                elif vals:
                    print("    {0:<11} {1}".format(kind, ", ".join(vals)))
                else:
                    print("    {0:<11} (none)".format(kind))
            if got.get("used_textures"):
                print("    textures    {0} used".format(
                    len(got["used_textures"])))
                for t in got["used_textures"]:
                    print("                  {0}".format(t))
            if "compile_errors" in got:
                errs = got["compile_errors"]
                if errs:
                    rc = max(rc, 4)
                    print("    COMPILE     {0} ERROR(S):".format(len(errs)))
                    for e in errs:
                        print("                  {0}".format(e))
                else:
                    print("    COMPILE     0 errors -- compiles clean in 5.8")
            elif got.get("compiled") is False:
                rc = max(rc, 5)
                print("    COMPILE     COULD NOT LOOK: {0}".format(
                    got.get("compile_exception")))
            print("")

        for path in (args.function or []):
            text = run(REFPAYLOAD.format(path=path, marker=MARKER))
            got = _parse(text)
            name = path.rsplit("/", 1)[-1]
            if got is None or not got.get("ok"):
                print("{0:<34} COULD NOT LOOK: {1}".format(
                    name, (got or {}).get("error", "no parseable result")))
                rc = max(rc, 5)
                continue
            print("FUNCTION {0}".format(path))
            print("    referenced by {0} material(s)".format(got["count"]))
            for r in got["referencing"]:
                print("      {0}".format(r))
            print("")
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
