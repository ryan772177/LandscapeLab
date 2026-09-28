"""rename_landscape.py — label the landscape to match the recipe.

The New Landscape dialog names its output `Landscape`. The recipe
declares `landscape.actor_name`, and every downstream script finds the
landscape by that label, so the rename is a required step that is easy
to forget in the dialog.

SAFE MUTATION. `set_actor_label` changes a display name only — no
transform, no components, no proxies. None of the World Partition
tearing hazards that make `set_actor_location` unsafe apply here.

Refuses unless there is exactly one candidate: if several landscapes
exist, renaming the wrong one is how you end up with two actors claiming
the same identity, which is the state the deletion script had to untangle
once already.

Also reports the streaming-proxy census, because a freshly imported
landscape sometimes reports zero proxies until World Partition has
built them, and that is worth seeing rather than guessing at.

Exit codes:
  0  renamed, or already correct
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  no landscape, or more than one candidate — refused
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import landscape_spec     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_RENAME__"


def _payload(target):
    return '''
import json as _json
import unreal as _unreal

_target = {target!r}
_out = {{"ok": False, "renamed": False}}

_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

# Force World Partition to materialise everything first, so the census
# reflects the level rather than whatever happens to be resident.
try:
    _guids = []
    for _d in _unreal.WorldPartitionBlueprintLibrary.get_actor_descs():
        _cls = _d.get_editor_property("native_class")
        _nm = _cls.get_name() if _cls is not None else ""
        if _nm in ("Landscape", "LandscapeStreamingProxy"):
            _guids.append(_d.get_editor_property("guid"))
    if _guids:
        _unreal.WorldPartitionBlueprintLibrary.load_actors(_guids)
    _out["descs"] = len(_guids)
except Exception as _exc:
    _out["load_error"] = "%s: %s" % (type(_exc).__name__, _exc)

_all = list(_unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.Landscape))
_proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.LandscapeStreamingProxy))
_out["labels"] = [_a.get_actor_label() for _a in _all]
_out["proxy_count"] = len(_proxies)

_already = [_a for _a in _all if _a.get_actor_label() == _target]
if _already and len(_all) == 1:
    _out["ok"] = True
    _out["note"] = "already correctly labelled"
elif len(_all) != 1:
    _out["note"] = "expected exactly one landscape, found %d" % len(_all)
else:
    _a = _all[0]
    _out["was"] = _a.get_actor_label()
    _a.set_actor_label(_target)
    _out["now"] = _a.get_actor_label()
    _out["renamed"] = (_out["now"] == _target)
    _out["ok"] = _out["renamed"]
    # Components live on the parent until WP splits them onto proxies.
    _out["components_on_actor"] = len(
        _a.get_components_by_class(_unreal.LandscapeComponent))

print("{marker}" + _json.dumps(_out))
'''.format(target=target, marker=MARKER)


def _parse(text):
    i = text.find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        r = remote.run_command(source, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("  command failed: {0}".format((r or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(r))
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        for e in errors:
            print("  - {0}".format(e))
        return 2
    target = spec["actor_name"]

    print("Target label : {0}".format(target))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        r = _run(remote_exec, remote, node["node_id"], _payload(target))
        if r is None:
            print("FAIL: rename payload returned nothing.")
            return 4

        print("  landscape actor descs : {0}".format(r.get("descs")))
        print("  landscapes            : {0}".format(r.get("labels")))
        print("  streaming proxies     : {0}".format(r.get("proxy_count")))
        if r.get("components_on_actor") is not None:
            print("  components ON actor   : {0}".format(
                r["components_on_actor"]))
        if r.get("load_error"):
            print("  load error: {0}".format(r["load_error"]))

        if not r.get("ok"):
            print("")
            print("REFUSE: {0}".format(r.get("note", "unknown")))
            return 4
        if r.get("renamed"):
            print("")
            print("Renamed {0!r} -> {1!r}".format(r.get("was"), r.get("now")))
        else:
            print("")
            print("Already correct: {0}".format(r.get("note")))
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
