"""make_metahuman_character.py — create the hero's MetaHuman Character asset.

Creates an EMPTY MetaHuman Character asset at a tracked path and stops. The
sculpting is Ryan's — this exists so the asset lands in the right place with
the right name, tracked by git, rather than wherever a right-click happened.

=====================================================================
WHY NOT UNDER /Game/Characters/
=====================================================================
`LandscapeLab/Content/Characters/` is GITIGNORED, deliberately: it holds the
128-file copy of the engine template mannequin, which is re-derivable by
re-running one copy command.

**A hand-sculpted MetaHuman is the opposite of re-derivable.** It is authored
work with no source to regenerate it from, and putting it in an ignored tree
would mean the one asset in this project that CANNOT be rebuilt is the one
git never sees. So the hero lives at /Game/Hero/, which is tracked.

That distinction — re-derivable content is ignored, authored content is
tracked — is the same rule `.gitignore` already applies to vendor packs
versus `recipes/`.

=====================================================================
WHAT THIS DOES NOT DO
=====================================================================
It does not sculpt, texture, dress or assemble anything. MetaHuman Creator is
an interactive tool and the character's LOOK is a design decision. This tool
refuses to pretend otherwise.

Exit codes:
  0  created (or already present)
  1  could not look / creation failed
  2  bad arguments
  3  rule 7: no verified editor node
  4  MetaHuman is not enabled in this editor
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_MH__"


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "enabled": None, "existed": None, "created": None,
        "path": None, "class": None}
try:
    _en = [str(_n) for _n in
           _unreal.PluginBlueprintLibrary.get_enabled_plugin_names()]
    _out["enabled"] = ("MetaHumanCharacter" in _en
                       and "MetaHumanCoreTech" in _en)
    if not _out["enabled"]:
        _out["error"] = ("MetaHumanCharacter and MetaHumanCoreTech must BOTH "
                         "be enabled. MetaHumanCharacter.uplugin does not "
                         "declare CoreTech and will not start without it.")
    else:
        _full = "__ROOT__/__NAME__"
        _ex = _unreal.EditorAssetLibrary.load_asset(_full)
        if _ex is not None:
            _out["existed"] = True
            _out["path"] = _ex.get_path_name()
            _out["class"] = _ex.get_class().get_name()
        else:
            _out["existed"] = False
            _tools = _unreal.AssetToolsHelpers.get_asset_tools()
            _a = _tools.create_asset(
                "__NAME__", "__ROOT__", _unreal.MetaHumanCharacter,
                _unreal.MetaHumanCharacterFactoryNew())
            if _a is None:
                _out["error"] = "create_asset returned None"
            else:
                _unreal.EditorAssetLibrary.save_asset(_full, False)
                # Read back off a FRESH load, not off the object just made --
                # this proves it is on disk, not merely in memory.
                _rb = _unreal.EditorAssetLibrary.load_asset(_full)
                _out["created"] = _rb is not None
                if _rb is not None:
                    _out["path"] = _rb.get_path_name()
                    _out["class"] = _rb.get_class().get_name()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_MH__" + _json.dumps(_out))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="/Game/Hero",
                    help="content path. Must NOT be under /Game/Characters, "
                         "which is gitignored as re-derivable engine content.")
    ap.add_argument("--name", default="MHC_AlpineHero")
    ap.add_argument("--go", action="store_true",
                    help="actually create it. Without this, plans only.")
    args = ap.parse_args(argv)

    if args.root.rstrip("/").startswith("/Game/Characters"):
        print("REFUSE: %s is inside the gitignored engine-mannequin tree." % args.root)
        print("        A hand-sculpted MetaHuman cannot be regenerated, so it")
        print("        must live somewhere git tracks.")
        return 2

    print("plan: create an EMPTY MetaHuman Character")
    print("      %s/%s" % (args.root, args.name))
    print("      tracked by git; the sculpting is yours, not this tool's")
    if not args.go:
        print("")
        print("DRY RUN — nothing created. Re-run with --go.")
        return 0

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(
            PAYLOAD.replace("__ROOT__", args.root).replace("__NAME__", args.name),
            unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            print("NO MARKER — could not look.")
            print(text[:1500])
            return 1
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d.get("enabled") is False:
        print("REFUSE:", d.get("error"))
        return 4
    if d.get("error"):
        print("FAILED:", d["error"])
        return 1

    if d.get("existed"):
        print("ALREADY EXISTS — nothing done.")
    else:
        print("CREATED and saved.")
    print("  path  %s" % d.get("path"))
    print("  class %s" % d.get("class"))
    print("")
    print("NEXT, AND IT IS RYAN'S: open it in the Content Browser and sculpt.")
    print("This tool made an empty asset; it did not decide what the hero")
    print("looks like, and it will not pretend to have.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
