"""diagnose_capture_world.py — which WORLD does the capture photograph?

Read-only.

WHY
A positive control failed twice: hiding an entire landscape proxy, with
the hide verified by read-back on the actor, changed the captured frame
by no more than the noise between two identical captures. Camera moves DO
reach captures. So the dead segment is specifically ACTOR MUTATION ->
CAPTURED PIXELS, and the first suspect is that the mutation and the
screenshot are not looking at the same UWorld.

WHAT IT COMPARES, AND WHY THESE PAIRS
Three independent paths to "the world" and "its actors". Agreement does
not prove one world; DISAGREEMENT proves more than one, which is the
finding that would explain everything.

  1. UnrealEditorSubsystem.get_editor_world()   <- what every mutation
     payload in this project uses, including the failed control
  2. EditorActorSubsystem.get_all_level_actors()  <- editor context, no
     world argument; if its landscape count differs from (1)'s, the two
     APIs are addressing different worlds
  3. EditorLevelLibrary.get_editor_world()      <- the deprecated UE4
     path, kept here precisely because it resolves the world by a
     different route

It also reports every loaded UWorld it can reach, because this editor
session began on /Temp/Untitled_1 and loaded /Game/Alpine over it. A
retained outgoing world is exactly the condition that fataled the editor
earlier today (EditorServer.cpp:1951, FPyReferenceCollector), and a
SURVIVING one that the viewport still draws would be the same defect
wearing a quieter costume.

Reports the hidden-state of landscape actors too: if the control's hide
is still visible here but not in the pixels, the mutation landed in a
world nobody photographs.

Exit codes:
  0  probe ran (read the verdict lines)
  1  unexpected error
  3  editor identity gate refused
  4  probe returned nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_WORLDDIAG__"

# No file extensions in the payload (PythonScriptPlugin.cpp:813-830).
PROBE = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False}}

def _wid(_w):
    if _w is None:
        return None
    try:
        return {{"path": _w.get_path_name(),
                "name": _w.get_name(),
                "outer": _w.get_outer().get_path_name()
                         if _w.get_outer() is not None else None}}
    except Exception as _e:
        return {{"error": type(_e).__name__}}

try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w1 = _ues.get_editor_world()
    _out["world_UnrealEditorSubsystem"] = _wid(_w1)

    try:
        _w2 = _unreal.EditorLevelLibrary.get_editor_world()
        _out["world_EditorLevelLibrary"] = _wid(_w2)
        _out["same_object"] = (_w1 == _w2)
    except Exception as _e:
        _out["world_EditorLevelLibrary"] = "UNAVAILABLE: " + type(_e).__name__

    # Landscape census by TWO routes.
    _by_world = 0
    _hidden_by_world = 0
    for _cls in (_unreal.Landscape, _unreal.LandscapeStreamingProxy):
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(_w1, _cls):
            _by_world += 1
            try:
                if _a.is_temporarily_hidden_in_editor():
                    _hidden_by_world += 1
            except Exception:
                pass
    _out["landscape_via_GameplayStatics_world"] = _by_world
    _out["landscape_hidden_via_world"] = _hidden_by_world

    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _all = _eas.get_all_level_actors()
    _by_editor = 0
    _hidden_by_editor = 0
    for _a in _all:
        if isinstance(_a, (_unreal.Landscape,
                           _unreal.LandscapeStreamingProxy)):
            _by_editor += 1
            try:
                if _a.is_temporarily_hidden_in_editor():
                    _hidden_by_editor += 1
            except Exception:
                pass
    _out["landscape_via_EditorActorSubsystem"] = _by_editor
    _out["landscape_hidden_via_editor"] = _hidden_by_editor
    _out["total_level_actors"] = len(_all)

    # Every loaded UWorld this process can see.
    _worlds = []
    try:
        for _o in _unreal.find_objects(None, _unreal.World):
            _worlds.append(_o.get_path_name())
    except Exception:
        try:
            for _o in _unreal.EditorAssetLibrary.list_assets(
                    "/Temp", True, False):
                _worlds.append("temp-asset: " + str(_o))
        except Exception as _e:
            _worlds.append("ENUM FAILED: " + type(_e).__name__)
    _out["worlds_loaded"] = _worlds[:20]
    _out["worlds_count"] = len(_worlds)

    del _w1
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

for _n in ("_w1", "_w2", "_a", "_o", "_all", "_ues", "_eas"):
    globals().pop(_n, None)

print("{marker}" + _json.dumps(_out))
'''.format(marker=MARKER)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    if (".p" + "y") in PROBE:
        print("REFUSE: payload carries a file extension.")
        return 1

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
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        try:
            remote.open_command_connection(node["node_id"])
            res = remote.run_command(PROBE, unattended=True,
                                     exec_mode=remote_exec.MODE_EXEC_FILE)
            text = bootstrap._collect_output(res or {})
            i = text.find(MARKER)
            out = json.JSONDecoder().raw_decode(
                text[i + len(MARKER):].lstrip())[0] if i >= 0 else None
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass

        if not out or not out.get("ok"):
            print("FAIL: probe returned nothing usable ({0}).".format(
                (out or {}).get("error", "no result")))
            return 4

        print("")
        for k in ("world_UnrealEditorSubsystem", "world_EditorLevelLibrary",
                  "same_object"):
            print("  {0:<34} {1}".format(k, out.get(k)))
        print("")
        print("  {0:<34} {1}".format(
            "landscape via world", out.get("landscape_via_GameplayStatics_world")))
        print("  {0:<34} {1}".format(
            "landscape via editor subsystem",
            out.get("landscape_via_EditorActorSubsystem")))
        print("  {0:<34} {1}".format(
            "hidden (world route)", out.get("landscape_hidden_via_world")))
        print("  {0:<34} {1}".format(
            "hidden (editor route)", out.get("landscape_hidden_via_editor")))
        print("  {0:<34} {1}".format(
            "total level actors", out.get("total_level_actors")))
        print("")
        print("  loaded UWorlds: {0}".format(out.get("worlds_count")))
        for w in out.get("worlds_loaded") or []:
            print("    {0}".format(w))

        a = out.get("landscape_via_GameplayStatics_world")
        b = out.get("landscape_via_EditorActorSubsystem")
        print("")
        if a != b:
            print("FINDING: the two routes DISAGREE ({0} vs {1}). The "
                  "mutation path and the editor's own actor list are not "
                  "addressing the same set of actors.".format(a, b))
        else:
            print("Both routes agree on {0} landscape actors. That does "
                  "NOT prove one world — it means the world the mutations "
                  "use is the world the editor lists. If the pixels still "
                  "disagree, suspicion moves to the VIEWPORT (which world "
                  "it draws, and whether the shot is served stale).".format(a))
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
