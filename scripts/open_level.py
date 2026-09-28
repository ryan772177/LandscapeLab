"""open_level.py — open the recipe's level, with the discard made explicit.

Exists because the level gate (schema v1.2) can refuse but cannot fix, and
because "just open the right level" is the single most common way a session
gets unblocked. Doing it by hand is fine; doing it here makes the one
DESTRUCTIVE case impossible to perform by accident.

THE DESTRUCTIVE CASE. Opening a level discards whatever unsaved state the
editor currently holds, and git cannot restore state that was never written
to a file. So:

  * If the current level is already the recipe's level, this is a no-op
    and reports so (hard rule 3: re-running changes nothing).
  * If the current level is a saved /Game/ level that exists on disk AND
    nothing map-side is dirty, switching loses nothing and proceeds.
  * Otherwise — an unsaved (`/Temp/...`) level, a level with no asset on
    disk, a non-/Game/ world, dirty map or external-actor packages, or a
    dirty-package query that FAILED — this REFUSES unless `--discard` is
    passed. A fresh UE session with no default startup map always opens an
    empty `/Temp/Untitled_1`, so the refusal is common AND usually
    harmless — but "usually harmless" is exactly the reasoning that loses
    somebody's afternoon, so the caller states the intent instead.

`--discard` names what it does. It is not `--force`. It does NOT override
"I could not read what is currently open" — that is a hard refusal, because
consent to discard a known thing is not consent to discard an unknown one.

WHY THE GUARD IS THE ONLY GUARD (read at the source, UE 5.8):
  * `ULevelEditorSubsystem::LoadLevel` opens with
    `TGuardValue<bool> UnattendedScriptGuard(GIsRunningUnattendedScript,
    true)` (LevelEditorSubsystem.cpp:540) and delegates to
    `UEditorLoadingAndSavingUtils::LoadMap` -> `FEditorFileUtils::LoadMap`.
  * `FEditorFileUtils::LoadMap` calls `ShouldAbortBecauseOfUnsavedWorld()`
    (FileHelpers.cpp:3286).
  * That function's ONLY protection is
    `FMessageDialog::Open(EAppMsgType::YesNo, EAppReturnType::Yes, "The
    unsaved level {0} will be lost.  Continue?")` (EditorServer.cpp:2131).
    Under `GIsRunningUnattendedScript` a message dialog returns its default
    — which here is **Yes** — so the engine's own warning is suppressed and
    the world is discarded silently.
  So: nothing downstream of this script will ask. Every refusal has to
  happen here, before `load_level` is called at all.

WHY `/Temp/` IS PART OF THE TEST, AND WHY IT IS NOT THE WHOLE TEST.
`/Temp/` is the engine's temp package root (`TempRootPath = TEXT("/Temp/")`,
PackageName.cpp:808); `GEditor->NewMap` builds untitled worlds there via
`CreatePackage(nullptr)` (EditorServer.cpp:2215-2218), and the engine tests
for exactly this with `LevelPackageName.StartsWith(TEXT("/Temp/Untitled"))`
(EditorServer.cpp:5724). So the prefix is sound as far as it goes. It is
still only a proxy: the engine's real criterion for "this world will be
lost" is dirty AND no package on disk (EditorServer.cpp:2120-2128), and
neither of those is a path prefix. This script therefore uses an ALLOW-list
(a saved, on-disk `/Game/` level with nothing map-side dirty is safe to
switch away from) rather than a deny-list of known-bad prefixes. An
allow-list cannot be wrong in the unsafe direction — only in the annoying
one, and the annoying direction is a re-run with `--discard`.

  Known false refusal: a genuinely saved level under a plugin content root
  (e.g. `/SomePlugin/Maps/Foo`) is not under `/Game/` and will be refused
  without `--discard`. No such level exists in this project; the refusal is
  recoverable and the file on disk is untouched, so this is left as-is
  rather than widening the allow-list on speculation.

DIRTY PACKAGES. A map transition loses dirty MAP packages and the dirty
EXTERNAL-ACTOR packages of the level being unloaded (OFPA gives each actor
its own hash-named package, so a World Partition level's real work is
mostly there, not in the .umap). Both are gated. Dirty CONTENT packages
(materials, textures) survive a map transition in memory, so they are
REPORTED but deliberately NOT gated — refusing on them would be friction
with no safety gain. If the dirty query itself errors, that is "I could not
look", and it refuses (lesson 10).

ATOMIC WITH THE LOAD. The guard is evaluated twice: once client-side off a
read-only probe, so a refusal never sends a payload that can load anything,
and once again INSIDE the load payload immediately before `load_level`.
The second evaluation is what makes it sound — between two remote calls a
human can open a different level, and a guard that ran in an earlier round
trip guards the wrong world.

VERIFIED BY READ-BACK. The load is not trusted. `load_level` returns a
bool, which is captured; after loading, the current level is read again and
compared against the target. A mismatch is a failure, not a warning.
`load_level` returning without raising says the call happened, not that the
world changed (lesson 6.3).

Conduct rule 7 is delegated to bootstrap.py's audited gate. Nothing reaches
a node that has not matched UE_PROJECT_ROOT.

Unreal APIs used (all long-stable for UE5; nothing 5.8-only):
  unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world
  unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level
  unreal.EditorAssetLibrary.does_asset_exist
  unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages
      / .get_dirty_content_packages

Exit codes (a per-script contract; the numbers do NOT line up with
verify_landscape.py's, which uses 7 for its level gate):
  0  the recipe's level is open (already, or loaded now), or --dry-run
     finished having changed nothing
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  the target level asset does not exist in the project
  5  the load was attempted and could NOT be confirmed — payload returned
     nothing, load_level returned False, or read-back shows a different
     level open. Treat the editor's state as unknown and look.
  6  REFUSED as destructive — discarding the current level or dirty
     map/external-actor packages would lose unsaved work, and --discard
     was not passed. Nothing was loaded.
  7  COULD NOT DETERMINE what is currently open, or the pre-checks did not
     complete. Nothing was loaded. Distinct from 6 on purpose: "I could
     not look" is not "I looked and refused", and --discard overrides
     neither.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import import_heightmap   # noqa: E402 — shared recipe validation
import landscape_spec     # noqa: E402 — shared recipe loading
import verify_landscape   # noqa: E402 — shared node selection + level probe

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_OPENLEVEL__"


# CORRECTED 2026-08-06 — MY FIRST DIAGNOSIS OF THIS WAS WRONG, AND THE
# PROJECT ALREADY KNEW THE ANSWER.
#
# Symptom: the editor reported
#     Could not load Python file 'C:/.../Win64/<the whole source>'
# after prose was added to the payload. I attributed it to SIZE (the
# payload had grown 8,683 -> 14,246 bytes) and added a size ceiling.
# Minifying then fixed it, which appeared to confirm the theory.
#
# It did not. `save_level` carries a PayloadTransportError guard that
# names the real mechanism with an engine citation: a payload containing
# a '.p'+'y' substring makes UE treat the ENTIRE script as a FILENAME
# instead of running it (PythonScriptPlugin.cpp:813-830). My added prose
# cited other scripts BY FILENAME, so it carried that substring;
# minification fixed the failure by deleting those comments, not by
# reducing bytes. Coincident cure, wrong cause — and step (a) of the
# operating loop would have found the existing guard in one grep.
#
# So the gate below checks BOTH, and names the extension case first
# because that is the one with a source line behind it. The byte ceiling
# is kept as a weak secondary bound — 8,683 is simply the largest size
# proven to run here, not a measured limit, and it is labelled as such
# rather than presented as knowledge.
# ONLY the Python extension. '.c'+'pp' was in this tuple for one draft
# and was removed: payloads have carried "EditorServer.cpp:1951" in their
# refusal text for many successful runs, so forbidding it would be a gate
# firing for the wrong reason — worse than no gate (lesson 14.3), and it
# would have blocked the engine citations that make the refusals useful.
_FORBIDDEN_IN_PAYLOAD = (".p" + "y",)
_MAX_PAYLOAD_BYTES = 8683


def _minify(src):
    """Strip full-line comments and blank lines from a payload.

    THE PAYLOAD IS TRANSMITTED; THE EXPLANATION DOES NOT HAVE TO BE.
    Comments in the payload string cost bytes on the wire against a hard
    ceiling, so they are stripped at send time while staying in the file
    for whoever reads it next. Only lines whose STRIPPED form starts with
    '#' are removed, so string literals are untouched unless one contains
    a line beginning with '#' — the caller compiles the result, which is
    what catches that.
    """
    out = []
    for line in src.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# =====================================================================
# THE PRE-LOAD REFERENCE SCRUB — reasoning kept HOST-SIDE on purpose.
#
# EVERY BYTE OF THE PAYLOAD BELOW IS TRANSMITTED to the editor, and the
# remote-exec channel has a size ceiling. Documenting the scrub inside
# the payload string took it from 8,683 to 14,246 bytes, past that
# ceiling; the command arrived TRUNCATED, and the plugin fell back to
# treating the fragment as a FILE PATH:
#
#     command failed: Could not load Python file
#     'C:/Program Files/.../Win64/<the whole source>'
#
# which reads as a missing file rather than as an oversized command.
# Explanatory prose therefore lives here, where it costs nothing, and
# the payload carries only pointers to it. This is the same ceiling that
# makes save_level exit non-zero on a save that SUCCEEDED.
#
# WHAT THE SCRUB IS FOR
# On a map transition UEditorEngine::VerifyLoadMapWorldCleanup
# (EditorServer.cpp:1951) verifies that nothing still references the
# world being torn down. A survivor is a FATAL ERROR, not a warning: it
# takes the editor down and every unsaved package with it.
#
# WHY gc.collect() WAS NEVER ENOUGH — reproduced 2026-08-05, on a fresh
# editor, with the gc.collect() guard already in place:
#
#     Old Package /Temp/Untitled_1 not cleaned up by GC! ... referenced
#     by GCObjectReferencer -> FPyReferenceCollector::AddReferencedObjects
#     Script Stack (1 frames): LevelEditorSubsystem.LoadLevel
#
# The old guard assumed the only references were the ones its own
# payload made. Remote-exec MODE_EXEC_FILE code runs in the PERSISTENT
# console dicts (PythonScriptPlugin.cpp:1858 -> :1807-1810), so a
# top-level name bound by an EARLIER payload is a LIVE GLOBAL when the
# next one runs. A live global is not garbage; gc.collect() cannot free
# it and never could. The specific chain: capture.py runs
# verify_landscape.LEVEL_SOURCE as its level gate, LEVEL_SOURCE bound
# _world/_om/_pkg and deleted none, capture refused on the wrong level,
# and the next load fataled over those globals.
#
# WHY IT LIVES HERE AND NOT IN 23 PRODUCERS
# 23 sites across 18 files bind a world wrapper into a persistent
# payload namespace. Individually patching them is the pattern
# non-negotiable 4a rejects, and no discipline binds payloads not yet
# written. open_level.py is the ONLY script that performs a map
# transition, so the guard sits at that choke point and scrubs by
# REACHABILITY, not authorship — every global rooting a UObject,
# whoever bound it, including inside lists and dicts, plus capture.py's
# builtins task stash. This payload's own dirty-package loop leaks `_p`
# the same way and is covered by the same scrub.
#
# ASSERTED, NOT TRUSTED: the namespace is re-read with the same
# predicate after the scrub, and the load REFUSES if anything survives.
# _UOBJECT_BASE is resolved from the live reflected surface and refuses
# when absent — an unresolved base would make isinstance() match
# nothing, report a clean namespace, and authorise the exact fatal it
# guards against (non-negotiable 1).
#
# Proven offline, three directions, by scripts/test_open_level_scrub.py.
# =====================================================================
def _payload(target, discard, dry_run):
    """Build the load payload.

    `target` is a recipe value already validated by
    import_heightmap._validate_landscape: a non-empty str starting with
    '/Game/' and not ending in '/'. It is interpolated with !r, so even an
    unvalidated string could only ever arrive as a Python string literal —
    but validation runs first regardless, because a syntactically safe
    '/Temp/Untitled_1' would still be a semantically catastrophic target.

    `discard` and `dry_run` are coerced to bool before interpolation, so
    they can only render as True or False.

    The guard is re-evaluated here, immediately before load_level, so it is
    atomic with the load rather than separated from it by a round trip.
    """
    raw = '''
import gc as _gc
import json as _json
import unreal as _unreal

_target = {target!r}
_discard = {discard!r}
_dry_run = {dry_run!r}

# UObject wrapper base; None = cannot scrub, and the load refuses.
# See the host-side block above _payload() for why.
_UOBJECT_BASE = getattr(_unreal, "Object", None)

_out = {{"ok": False, "checked": False, "exists": False, "loaded": False,
        "would_load": False, "refused": None, "overridden": [],
        "unreadable_before": False,
        "before": None, "after": None, "before_on_disk": None,
        "dirty_query_ok": False, "dirty_maps": [], "dirty_actors": [],
        "dirty_content": [], "load_returned": None, "error": None}}


def _current():
    """Package path of the open level, or None if it cannot be read.

    Same derivation as verify_landscape.LEVEL_SOURCE: the WORLD's outer
    package, not the world object, so a saved map reads '/Game/Alpine'
    with no '.Alpine' suffix. None means "could not look", never "no
    level" - the caller treats it as a refusal.

    RETURNS A STRING AND RETAINS NOTHING. Every UObject wrapper it makes
    is deleted before returning, because a surviving Python reference to
    the outgoing UWorld is FATAL across a map transition - see the
    _release_world_refs note below. Do not "simplify" this back into a
    one-line return: the whole point is that no wrapper outlives the call.
    """
    _w = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world()
    if _w is None:
        return None
    _p = _w.get_outer()
    _path = _p.get_path_name() if _p is not None else None
    del _p
    del _w
    return _path


# Names this payload still needs after the scrub. Everything else in the
# persistent namespace is fair game: payloads are self-contained.
_KEEP_GLOBALS = ("_unreal", "_json", "_gc", "_out", "_target", "_discard",
                 "_dry_run", "_current", "_release_world_refs",
                 "_holds_uobject", "_surviving_uobject_globals",
                 "_KEEP_GLOBALS")


def _holds_uobject(_v, _depth=0):
    """True if _v is a UObject wrapper or shallowly contains one.

    Containers count: `_found = [actor]` roots the world too.
    """
    if isinstance(_v, _UOBJECT_BASE):
        return True
    if _depth >= 2:
        return False
    if isinstance(_v, (list, tuple, set, frozenset)):
        for _e in _v:
            if _holds_uobject(_e, _depth + 1):
                return True
        return False
    if isinstance(_v, dict):
        for _e in _v.values():
            if _holds_uobject(_e, _depth + 1):
                return True
        return False
    return False


def _surviving_uobject_globals():
    """Names in the persistent namespace that still root a UObject."""
    _g = globals()
    _bad = []
    for _k in list(_g.keys()):
        if _k.startswith("__") or _k in _KEEP_GLOBALS:
            continue
        try:
            if _holds_uobject(_g[_k]):
                _bad.append(_k)
        except Exception:
            pass
    return _bad


def _release_world_refs():
    """Drop every global rooting a UObject. Returns the names dropped.

    gc.collect() alone is NOT sufficient - persistent-console globals
    from earlier payloads are live, not garbage. Host-side block above
    _payload() carries the root cause and the engine citations.
    """
    _g = globals()
    _dropped = []
    for _k in _surviving_uobject_globals():
        try:
            del _g[_k]
            _dropped.append(_k)
        except Exception:
            pass
    # capture.py parks live screenshot tasks on `builtins` deliberately;
    # they are UObjects and nothing can be mid-capture at a level load.
    try:
        import builtins as _b
        _stash = getattr(_b, "_LANDSCAPELAB_SHOT_TASKS", None)
        if _stash:
            _dropped.append(
                "builtins._LANDSCAPELAB_SHOT_TASKS({{0}} task(s))".format(
                    len(_stash)))
            _stash.clear()
    except Exception:
        pass
    _gc.collect()
    return _dropped


try:
    _out["before"] = _current()
    _before = _out["before"]

    # What is dirty? A map transition loses dirty map packages and the
    # dirty external-actor packages of the level being unloaded. Dirty
    # content packages survive in memory, so they are reported only.
    # dirty_query_ok separates "nothing is dirty" from "I could not ask".
    try:
        _els = _unreal.EditorLoadingAndSavingUtils
        for _p in _els.get_dirty_map_packages():
            _out["dirty_maps"].append(_p.get_name())
        for _p in _els.get_dirty_content_packages():
            _n = _p.get_name()
            if "/__ExternalActors__/" in _n:
                _out["dirty_actors"].append(_n)
            else:
                _out["dirty_content"].append(_n)
        _out["dirty_query_ok"] = True
    except Exception as _exc:
        _out["dirty_query_ok"] = False
        _out["dirty_error"] = "{{0}}: {{1}}".format(type(_exc).__name__, _exc)

    # Existence is checked BEFORE any load is attempted. Asking the editor
    # to open a level that is not there is how you end up with an empty
    # Untitled replacing a perfectly good world.
    _out["exists"] = bool(_unreal.EditorAssetLibrary.does_asset_exist(_target))

    # Does the CURRENT level have an asset on disk? This is the engine's
    # own criterion for "this world would be lost"
    # (UEditorEngine::ShouldAbortBecauseOfUnsavedWorld, EditorServer.cpp
    # 2120-2128), and it does not depend on any path prefix. None means
    # the question could not be answered, which is not a yes.
    if isinstance(_before, str) and _before:
        try:
            _out["before_on_disk"] = bool(
                _unreal.EditorAssetLibrary.does_asset_exist(_before))
        except Exception:
            _out["before_on_disk"] = None

    # Every pre-check that gates the load has now run. Anything that sets
    # "error" while checked is False means the decision was never made,
    # so no load can have happened - the caller must not read a False
    # "exists" as "the asset is absent" when it only means "I never got
    # far enough to look".
    _out["checked"] = True

    if not _out["exists"]:
        _out["error"] = "no asset at " + _target
    elif not (isinstance(_before, str) and _before):
        # Hard refusal. --discard authorises discarding a KNOWN world.
        _out["unreadable_before"] = True
        _out["refused"] = [
            "the currently open level could not be read (got "
            + repr(_before) + "). Refusing rather than loading over an "
            "unknown world; --discard does not override this."]
    elif _before == _target:
        # Idempotent: already open, nothing to load, nothing to discard.
        _out["loaded"] = False
        _out["after"] = _before
        _out["ok"] = True
    else:
        # ALLOW-list. Safe to switch away only from a saved, on-disk
        # /Game/ level with nothing map-side dirty. Everything else needs
        # --discard.
        _reasons = []
        if not _before.startswith("/Game/"):
            _reasons.append(
                "the open level " + repr(_before) + " is not under /Game/ "
                "- it is an unsaved or non-content world")
        if _out["before_on_disk"] is not True:
            _reasons.append(
                "the open level " + repr(_before) + " has no asset on disk "
                "(on_disk=" + repr(_out["before_on_disk"]) + "), so it has "
                "never been saved and cannot be recovered")
        if not _out["dirty_query_ok"]:
            _reasons.append(
                "the dirty-package query failed, so unsaved work cannot be "
                "ruled out: " + str(_out.get("dirty_error")))
        elif _out["dirty_maps"] or _out["dirty_actors"]:
            _reasons.append(
                "a map transition would discard these unsaved packages: "
                + ", ".join(_out["dirty_maps"] + _out["dirty_actors"]))

        if _reasons and not _discard:
            _out["refused"] = _reasons
        else:
            if _reasons:
                # --discard was given. Record EXACTLY what it overrode, so
                # the report names the work being thrown away instead of
                # implying there was none (lesson 12).
                _out["overridden"] = _reasons
            if _dry_run:
                _out["would_load"] = True
                _out["ok"] = True
            else:
                # Scrub, then ASSERT the scrub. Nothing between here and
                # load_level may touch the world.
                _out["released_refs"] = _release_world_refs()
                if _UOBJECT_BASE is None:
                    _out["refused"] = [
                        "unreal.Object did not resolve, so the pre-load "
                        "reference scrub could not run. Refusing rather "
                        "than fataling at EditorServer.cpp:1951."]
                elif _surviving_uobject_globals():
                    _out["survivors"] = _surviving_uobject_globals()
                    _out["refused"] = [
                        "these names still root a UObject after the "
                        "scrub; a map transition would fatal the editor: "
                        + ", ".join(_out["survivors"])]
                else:
                    _ok = _unreal.get_editor_subsystem(
                        _unreal.LevelEditorSubsystem).load_level(_target)
                    # load_level returns bool and raises nothing on failure
                    # (LevelEditorSubsystem.cpp:538-563) - capture it, or a
                    # refusal inside the engine reads as a successful call.
                    _out["load_returned"] = bool(_ok)
                    _out["loaded"] = bool(_ok)
                    # READ BACK. load_level returning proves the call
                    # happened, not that the world changed.
                    _out["after"] = _current()
                    _out["ok"] = (_out["after"] == _target)
                    if not _out["ok"]:
                        _out["error"] = ("load_level returned "
                                         + repr(bool(_ok))
                                         + " but the open level is "
                                         + repr(_out["after"]))
except Exception as _exc:
    _out["error"] = "{{0}}: {{1}}".format(type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''.format(target=target, discard=bool(discard), dry_run=bool(dry_run),
           marker=MARKER)
    lean = _minify(raw)
    # Compile BOTH. If stripping ever changes meaning — a '#' opening a
    # line inside a string literal is the realistic way — this raises
    # here, on the host, instead of arriving at the editor as a
    # SyntaxError or, worse, as something that runs differently.
    compile(raw, "<payload>", "exec")
    compile(lean, "<payload-minified>", "exec")
    return lean


def _run(remote_exec, remote, node_id, source):
    """Run the load payload on an ALREADY-VERIFIED node."""
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
        return verify_landscape._parse_probe(
            bootstrap._collect_output(r), MARKER)
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _report_dirty(r):
    """Print what the editor reports as dirty, on every outcome."""
    if not r.get("dirty_query_ok"):
        print("  dirty query : FAILED — {0}".format(
            r.get("dirty_error") or "reason not reported"))
        return
    for label, key in (("dirty maps   ", "dirty_maps"),
                       ("dirty actors ", "dirty_actors"),
                       ("dirty content", "dirty_content")):
        names = r.get(key) or []
        note = "  (not discarded by a map transition)" \
            if key == "dirty_content" and names else ""
        print("  {0}: {1}{2}".format(
            label, ", ".join(names) if names else "none", note))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=6.0)
    p.add_argument("--discard", action="store_true",
                   help="permit discarding UNSAVED work: a never-saved "
                        "current level, or dirty map/external-actor "
                        "packages. Neither can be recovered by git. Does "
                        "NOT override an unreadable current level.")
    p.add_argument("--dry-run", action="store_true",
                   help="run every check and report the decision without "
                        "loading anything (lesson 3).")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    errors = import_heightmap._validate_recipe(recipe,
                                               os.path.abspath(args.recipe))
    if errors:
        print("REFUSE: recipe invalid:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    target = recipe["landscape"]["level_path"]
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Target    : {0}  (recipe landscape.level_path)".format(target))
    if args.dry_run:
        print("Mode      : DRY RUN — nothing will be loaded")
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

        # Read the CURRENT level first, off the audited read-only payload,
        # so an obvious refusal never sends anything that could load. The
        # authoritative guard runs again inside the load payload; this one
        # exists to fail early and to report.
        #
        # verify_landscape._run_probe takes the marker as a parameter, so
        # LEVEL_SOURCE is reused verbatim with its own LEVEL_MARKER. It is
        # NOT rewritten to carry this script's marker: LEVEL_SOURCE is an
        # already-.format()ed payload, and a blind string substitution on
        # it would silently degrade to "no marker found" — reported as
        # "could not read the level" — if the payload ever changed.
        probe = verify_landscape._run_probe(
            remote_exec, remote, node["node_id"],
            verify_landscape.LEVEL_SOURCE, verify_landscape.LEVEL_MARKER)
        if probe is None:
            print("REFUSE: the level probe returned nothing. That is 'I "
                  "could not look', not 'nothing is open' — refusing "
                  "rather than loading over an unknown world.")
            return 7
        if probe.get("error"):
            print("REFUSE: level unreadable: {0}".format(probe["error"]))
            return 7
        current = probe.get("level")
        if not isinstance(current, str) or not current:
            # An empty string is not a level. Checking `is None` alone
            # would let "" through as a non-/Temp/ path and classify an
            # unreadable world as safe to discard.
            print("REFUSE: the editor reported no usable current level "
                  "(level={0!r}, world={1!r}, outermost={2!r}). That is "
                  "'I could not look', not 'nothing is open'.".format(
                      current, probe.get("world"), probe.get("outermost")))
            return 7
        print("  current level : {0}".format(current))

        if current == target:
            print("")
            print("Already open. Nothing to do (idempotent).")
            return 0

        # Client-side half of the allow-list. The dirty half can only be
        # answered by the payload, which re-checks all of it anyway.
        if not current.startswith("/Game/") and not args.discard:
            print("")
            print("REFUSE: the open level {0!r} is not a saved /Game/ level "
                  "— it is an unsaved world. Opening {1!r} would discard it "
                  "permanently; git cannot restore a level that was never "
                  "written to a file.".format(current, target))
            print("  Re-run with --discard if that is intended, or save it "
                  "first.")
            return 6
        if not current.startswith("/Game/"):
            print("  --discard given: {0!r} {1} discarded".format(
                current, "WOULD be" if args.dry_run else "will be"))
        print("")

        source = _payload(target, args.discard, args.dry_run)
        size = len(source.encode("utf-8"))
        print("  payload {0} bytes (proven ceiling {1})".format(
            size, _MAX_PAYLOAD_BYTES))
        bad = [t for t in _FORBIDDEN_IN_PAYLOAD if t in source]
        if bad:
            print("")
            print("REFUSE: the payload contains {0!r}. UE treats a script "
                  "carrying a file extension as a FILENAME and reports "
                  "'Could not load Python file <the whole source>' — which "
                  "reads as a missing file, not as a bad payload "
                  "(PythonScriptPlugin.cpp:813-830). Name scripts without "
                  "the extension inside payload strings.".format(bad[0]))
            return 2
        if size > _MAX_PAYLOAD_BYTES:
            print("")
            print("REFUSE: the load payload is larger than the biggest "
                  "size proven to execute on this host. Over the real "
                  "ceiling the editor does not report an oversized "
                  "command — it stops recognising the source as literal "
                  "code and reports 'Could not load Python file' with "
                  "the whole payload as the path, which reads as a "
                  "missing file. Refusing here names the actual cause. "
                  "Move prose out of the payload string; it is "
                  "transmitted, and _minify() already strips comments.")
            return 2
        print("")

        r = _run(remote_exec, remote, node["node_id"], source)
        if r is None:
            print("FAIL: the load payload returned nothing. The editor's "
                  "state is UNKNOWN — the load may or may not have run. "
                  "Check which level is open before doing anything else.")
            return 5

        # "checked" is set only after every pre-check completed, and
        # strictly before any load. False means the decision was never
        # reached, so nothing was loaded — and a False "exists" here means
        # "never looked", not "absent" (lesson 10).
        if not r.get("checked"):
            print("FAIL: the load payload could not complete its "
                  "pre-checks: {0}".format(r.get("error") or "no reason "
                                           "reported"))
            print("  Nothing was loaded.")
            return 7

        _report_dirty(r)

        if r.get("unreadable_before"):
            for reason in r.get("refused") or []:
                print("REFUSE: {0}".format(reason))
            return 7
        if not r.get("exists"):
            print("REFUSE: {0}".format(r.get("error")
                                       or "target level not found"))
            return 4
        if r.get("refused"):
            print("")
            print("REFUSE: opening {0!r} would discard unsaved work:".format(
                target))
            for reason in r["refused"]:
                print("  - {0}".format(reason))
            print("  Nothing was loaded. Save it first, or re-run with "
                  "--discard.")
            return 6
        overridden = r.get("overridden") or []
        if overridden:
            print("")
            print("*** --discard is OVERRIDING these refusals ***")
            for reason in overridden:
                print("  ! {0}".format(reason))

        if r.get("would_load"):
            print("")
            if overridden:
                print("DRY RUN: would load {0} AND PERMANENTLY DISCARD the "
                      "work listed above. Nothing was changed.".format(
                          target))
            else:
                print("DRY RUN: would load {0}; nothing unrecoverable would "
                      "be discarded. Nothing was changed.".format(target))
            return 0
        if r.get("error"):
            print("FAIL: {0}".format(r["error"]))
            return 5
        print("  load_level returned : {0}".format(r.get("load_returned")))
        print("  read-back           : {0}".format(r.get("after")))
        if not r.get("ok"):
            print("FAIL: read-back does not match the target.")
            return 5
        print("")
        print("Open and VERIFIED by read-back: {0}".format(target))
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
