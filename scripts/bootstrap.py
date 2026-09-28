"""bootstrap.py — remote-exec connectivity check + editor identity gate.

READ-ONLY. This script never mutates the scene, never writes assets, and
never writes any file. It answers two questions, in this order:

  1. Is the editor we can reach actually OUR project?  (conduct rule 7)
  2. If so, what engine version is it running?

HOW IDENTITY IS ESTABLISHED (conduct rule 7)
Node discovery is passive. The UDP "pong" payload an editor broadcasts
already carries `project_root` (absolute, ConvertRelativePathToFull of
FPaths::ProjectDir()), `project_name`, and `engine_version` — see
Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/
Private/PythonScriptRemoteExecution.cpp:44-51 (protocol) and :262-271
(construction). `project_root` is omitted when no project is loaded, i.e.
an editor sitting at the project browser is determinately "not us".

So NOTHING is executed against any editor in order to identify it. We
select the single node whose pong `project_root` equals UE_PROJECT_ROOT,
and only then open a command connection — to that one verified node.

Pong data is self-reported over unauthenticated UDP, so after selection we
re-verify by evaluating one read-only expression on the selected node and
comparing the answer again. Defense in depth, not the primary gate. Every
failure path refuses: this script exits non-zero rather than guessing.

Exit codes:
  0  verified: exactly one node is UE_PROJECT_ROOT; version reported
  1  unexpected error (bad args, missing engine module, socket failure)
  2  no editor nodes discovered within the discovery window
  3  nodes discovered, none has UE_PROJECT_ROOT loaded
  4  more than one node claims UE_PROJECT_ROOT (ambiguous — refuse)
  5  indeterminate: malformed pong path, or post-selection confirmation
     failed or disagreed with the pong

Unreal APIs used (all long-stable, present since UE4; nothing 5.8-only):
  unreal.Paths.project_dir, unreal.Paths.convert_relative_path_to_full,
  unreal.SystemLibrary.get_engine_version
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# --- Roots -------------------------------------------------------------
# REPO_ROOT is derived from this file's location rather than hardcoded, so
# the two cannot drift. UE_PROJECT_ROOT is the safety root conduct rule 7
# compares against. --project-root may only ever narrow to a path inside
# REPO_ROOT; the gate must not be retargetable at arbitrary directories.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE_PROJECT_ROOT = os.path.join(REPO_ROOT, "LandscapeLab")

try:
    from engine_paths import ENGINE_ROOT
except ImportError:  # imported with scripts/ not on sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine_paths import ENGINE_ROOT
REMOTE_EXEC_DIR = os.path.join(
    ENGINE_ROOT, "Engine", "Plugins", "Experimental",
    "PythonScriptPlugin", "Content", "Python",
)

MARKER = "__LANDSCAPELAB_CONFIRM__"

# Pure read of the loaded project's path and engine version. No asset
# access, no mutation. Sent ONLY to the already-identified node.
CONFIRM_PROBE = """
import json as _json
import unreal as _unreal

print("{marker}" + _json.dumps({{
    "project_dir": _unreal.Paths.convert_relative_path_to_full(
        _unreal.Paths.project_dir()
    ),
    "engine_version": _unreal.SystemLibrary.get_engine_version(),
}}))
""".format(marker=MARKER)


def _norm(path: str) -> str:
    """Canonical comparable form of a path.

    realpath resolves symlinks/junctions and expands 8.3 short names on
    Windows (falling back to lexical normalization for nonexistent paths),
    so a junction inside REPO_ROOT cannot retarget the rule 7 gate at a
    directory elsewhere on disk. normcase makes the comparison case- and
    separator-insensitive; normpath strips any trailing separator. Every
    comparison in this script passes both sides through this function.
    """
    if not path or not isinstance(path, str):
        return ""
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def _load_remote_execution():
    """Import the engine's remote_execution module, or fail loudly."""
    module_path = os.path.join(REMOTE_EXEC_DIR, "remote_execution.py")
    if not os.path.isfile(module_path):
        raise RuntimeError(
            "remote_execution.py not found at {0}. Check the UE 5.8 install "
            "path, or whether the module moved out of Experimental/."
            .format(module_path)
        )
    if REMOTE_EXEC_DIR not in sys.path:
        sys.path.insert(0, REMOTE_EXEC_DIR)
    # Suppress bytecode caching for this import: it must not create a
    # __pycache__ under Program Files (conduct rule 1 — no writes outside
    # REPO_ROOT / UE_PROJECT_ROOT).
    prev_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import remote_execution  # noqa: E402  (path must be set up first)
    finally:
        sys.dont_write_bytecode = prev_dont_write
    return remote_execution


def _collect_output(result: dict) -> str:
    """Flatten a command_result's output entries into one string.

    Entries are discrete log lines that may not carry their own newline
    (PythonScriptRemoteExecution.cpp:80-83), so join on newlines — an
    unrelated log line must not concatenate onto our JSON payload.
    """
    if not result:
        return ""
    chunks = []
    for entry in result.get("output") or []:
        if isinstance(entry, dict):
            chunks.append(str(entry.get("output", "")))
        else:
            chunks.append(str(entry))
    return "\n".join(chunks)


def _parse_marker(text: str):
    """Decode the JSON object that follows MARKER, or None."""
    idx = text.find(MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(MARKER):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _confirm(remote_exec, remote, node_id: str):
    """Run the read-only confirmation probe on the verified node.

    Returns the decoded payload dict, or None if it could not be read.
    """
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  confirmation connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(
            CONFIRM_PROBE, unattended=True,
            exec_mode=remote_exec.MODE_EXEC_FILE,
        )
        if not result or not result.get("success"):
            print("  confirmation probe did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse_marker(_collect_output(result))
    except Exception as exc:
        print("  confirmation probe errored: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _discover(remote, timeout: float, settle: float = 0.5):
    """Poll for remote nodes until the discovery window closes.

    Waits the full window rather than returning on first sight: a missed
    node is the dangerous case, since a second editor arriving late could
    be the one that should have made this run ambiguous and refused.
    """
    deadline = time.time() + timeout
    seen = {}
    while time.time() < deadline:
        for node in remote.remote_nodes:
            seen[node["node_id"]] = node
        time.sleep(settle)
    return list(seen.values())


def _describe(node: dict) -> str:
    return "{0} (user={1}, machine={2}, project={3})".format(
        node.get("node_id"),
        node.get("user", "?"),
        node.get("machine", "?"),
        node.get("project_name") or "<none loaded>",
    )


def _resolve_project_root(raw: str) -> str:
    """Validate the requested safety root, or raise.

    The rule 7 comparison target may only ever be REPO_ROOT or something
    beneath it — otherwise the flag would turn the gate into a
    pass-through for an arbitrary project on disk.
    """
    candidate = _norm(raw)
    repo = _norm(REPO_ROOT)
    if candidate != repo and not candidate.startswith(repo + os.sep):
        raise ValueError(
            "--project-root must be inside REPO_ROOT ({0}); refusing to "
            "retarget the rule 7 gate at {1}".format(REPO_ROOT, raw)
        )
    return candidate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--project-root", default=UE_PROJECT_ROOT,
        help="Project dir the connected editor must match. Must be inside "
             "REPO_ROOT.",
    )
    parser.add_argument(
        "--timeout", type=float, default=6.0,
        help="Seconds to spend discovering editor nodes (default: 6).",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits with code 2 on bad arguments, which would collide
        # with this script's "no nodes discovered" exit code. Remap onto
        # the documented contract: bad args -> 1 (--help stays 0).
        return 0 if exc.code == 0 else 1

    print("REPO_ROOT        : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT  : {0}".format(args.project_root))
    print("")

    try:
        expected = _resolve_project_root(args.project_root)
    except ValueError as exc:
        print("REFUSE: {0}".format(exc))
        return 1

    if not os.path.isdir(args.project_root):
        print("REFUSE: UE_PROJECT_ROOT is not a directory on disk. Nothing "
              "to verify against; not contacting any editor.")
        return 1

    remote_exec = _load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        print("Discovering editor nodes on {0}:{1} for {2:.0f}s ...".format(
            remote_exec.DEFAULT_MULTICAST_GROUP_ENDPOINT[0],
            remote_exec.DEFAULT_MULTICAST_GROUP_ENDPOINT[1],
            args.timeout,
        ))
        nodes = _discover(remote, args.timeout)

        if not nodes:
            print("No editor nodes answered. Either no editor is running "
                  "with a project loaded, the Python Editor Scripting "
                  "Plugin is off, or Remote Execution is disabled.")
            return 2

        print("Found {0} node(s):".format(len(nodes)))
        matches, malformed = [], []
        for node in nodes:
            raw = node.get("project_root")
            if raw is None:
                # No project loaded (pong omits the field) — determinately
                # not us. Not "indeterminate".
                status = "no project loaded"
            elif not isinstance(raw, str) or not os.path.isabs(raw):
                # Non-string, empty, or relative. A relative path would be
                # resolved against OUR cwd by _norm and could falsely equal
                # the expected root; a real editor always reports absolute
                # (ConvertRelativePathToFull). Treat as unclassifiable.
                malformed.append(node)
                status = "MALFORMED project_root: {0!r}".format(raw)
            elif _norm(raw) == expected:
                matches.append(node)
                status = "MATCH -> {0}".format(raw)
            else:
                status = "other project -> {0}".format(raw)
            print("  - {0}: {1}".format(_describe(node), status))
        print("")

        # Fail closed on any node we cannot classify, before deciding on
        # matches: a malformed node could itself be a second UE_PROJECT_ROOT
        # editor, so the "exactly one" guarantee cannot be established.
        if malformed:
            print("REFUSE (rule 7): {0} node(s) reported a project path "
                  "that could not be parsed. Not executing.".format(
                      len(malformed)))
            return 5
        if not matches:
            print("REFUSE (rule 7): no reachable editor has "
                  "UE_PROJECT_ROOT open. Not executing.")
            return 3
        if len(matches) > 1:
            print("REFUSE (rule 7): {0} editors claim UE_PROJECT_ROOT. "
                  "Ambiguous target; close all but one.".format(len(matches)))
            return 4

        node = matches[0]
        print("Selected by discovery: {0}".format(_describe(node)))
        print("Confirming identity on the selected node ...")

        info = _confirm(remote_exec, remote, node["node_id"])
        if not info or not info.get("project_dir"):
            print("REFUSE (rule 7): could not confirm the selected editor's "
                  "project path. Not executing.")
            return 5
        if _norm(info["project_dir"]) != expected:
            print("REFUSE (rule 7): editor reported {0}, which is not "
                  "UE_PROJECT_ROOT. Discovery data disagreed with the live "
                  "editor. Not executing.".format(info["project_dir"]))
            return 5

        print("")
        print("VERIFIED: {0}".format(_describe(node)))
        print("  project dir     : {0}".format(info["project_dir"]))
        print("  engine version  : {0}".format(
            info.get("engine_version") or node.get("engine_version", "?")))
        print("  engine root     : {0}".format(node.get("engine_root", "?")))
        print("")
        print("Remote execution OK. Editor identity matches "
              "UE_PROJECT_ROOT.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
