"""enable_landscape_nanite.py — turn landscape Nanite on (or off), and BUILD it.

WHY THIS IS A SCRIPT AND NOT A CLICK, and why it is separate from
`apply_nanite.py`. That script enables Nanite on STATIC MESHES declared in
the recipe palette (the rocks). This one operates on the LANDSCAPE, which
is a different property on a different class with a different build
trigger, and conflating them would put a 257-actor world mutation behind a
flag on a mesh tool.

WHAT IT IS FOR. The terrain's silhouette is capped at 4.00 m per heightmap
texel (2017 vertices at scale_xy_cm 400 over 8.064 km). Landscape Nanite
DISPLACEMENT is the only route to finer silhouette that does not re-import
the terrain and re-derive all 171,069 placements. Nanite is the CARRIER:
enabling it without the displacement material buys no silhouette at all,
because it renders the same 4 m geometry as a Nanite mesh. So this script
is step 9 of the displacement unit, never a thing to run on its own.

THE TWO FACTS THAT DECIDE HOW THIS WORKS, read at the source:

1. SETTING THE PROPERTY DOES NOT BUILD ANYTHING BY DEFAULT.
   ALandscape::PostEditChangeProperty (LandscapeEdit.cpp:6708-6717) calls
   InvalidateOrUpdateNaniteRepresentation on a bEnableNanite change, and
   that function (Landscape.cpp:587-606) branches:

       if (Subsystem->IsLiveNaniteRebuildEnabled())  UpdateNaniteRepresentation()
       else                                          InvalidateNaniteRepresentation()

   IsLiveNaniteRebuildEnabled() is exactly `LiveRebuildNaniteOnModification
   > 0` (LandscapeSubsystem.cpp:1561-1564), fed by the cvar
   `landscape.Nanite.LiveRebuildOnModification`, which DEFAULTS TO 0.
   ULandscapeSubsystem::BuildNanite is LANDSCAPE_API but carries no
   UFUNCTION, so it is absent from the reflected Python surface and cannot
   be called directly — checked in the generated stub, not assumed.

   So without the cvar this script would report "enable_nanite True" over a
   landscape whose Nanite mesh was never built: a property that arrived and
   meant something else. `--build` sets the cvar FIRST, so the property
   change itself performs the build.

2. ONE WRITE COVERS ALL 257 ACTORS.
   bNaniteToggled forces bPropagateToProxies (LandscapeEdit.cpp:6743), and
   the propagation calls
   Proxy->SynchronizeSharedProperties(this, bInExecutePostEditChangeProperty
   = true) on every proxy (:6749-6759) — which runs each proxy's own
   PostEditChangeProperty and therefore each proxy's Nanite update. Writing
   the property on all 257 by hand would re-enter that path 257 times.

THIS MUTATES THE WORLD IN MEMORY AND SAVES NOTHING. Deliberate. The
displacement result has to be LOOKED AT before 1,484 packages are written,
and the world on disk is its own restore point until then. Saving is a
separate, explicit step with its own tool (`save_level.py`).

EXIT CODES
  0  applied and read back as asked
  2  refused before touching anything
  3  editor identity gate (conduct rule 7)
  5  applied but the read-back DISAGREES — the world is in an unknown
     state and must be inspected, not re-run
  6  the wrong level is open
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

MARKER = "__LANDSCAPELAB_LSNANITE__"
REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

PAYLOAD = '''
import json as _json
import unreal as _unreal

_want = bool({want})
_do_build = bool({do_build})
_actor = {actor!r}

_out = {{"ok": False, "error": None, "before": {{}}, "after": {{}},
        "parents": 0, "proxies": 0, "mismatch": [], "cvar": None,
        "nanite_components": {{}}}}

try:
    _sl = _unreal.SystemLibrary
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _all = _eas.get_all_level_actors()
    _proxies = [_a for _a in _all if isinstance(_a, _unreal.LandscapeProxy)]
    _parents = [_a for _a in _proxies
                if not isinstance(_a, _unreal.LandscapeStreamingProxy)]
    _out["parents"] = len(_parents)
    _out["proxies"] = len(_proxies) - len(_parents)

    # The parent ALandscape is the ONE write; the engine propagates. Refuse
    # rather than guess if the world does not have exactly one.
    _named = [_a for _a in _parents if str(_a.get_actor_label()) == _actor]
    if len(_named) != 1:
        _out["error"] = (
            "expected exactly 1 parent Landscape labelled " + _actor
            + ", found " + str(len(_named)) + " (of " + str(len(_parents))
            + " parent landscapes). Refusing: propagation is defined from a "
              "single parent and this world does not present one.")
        raise RuntimeError(_out["error"])
    _land = _named[0]

    for _a in _proxies:
        _out["before"][str(_a.get_actor_label())] = bool(
            _a.get_editor_property("enable_nanite"))

    # THE BUILD TRIGGER, set BEFORE the property write because the property
    # write is what consumes it (Landscape.cpp:598).
    if _do_build:
        _sl.execute_console_command(
            _land.get_world(), "landscape.Nanite.LiveRebuildOnModification 1")
        _out["cvar"] = _sl.get_console_variable_float_value(
            "landscape.Nanite.LiveRebuildOnModification")
        # A cvar that did not take means the property write below would
        # only INVALIDATE, and the script would report a build it never
        # did. Three landscape mutations on this project have returned
        # "ok" and moved nothing.
        if not _out["cvar"]:
            _out["error"] = (
                "landscape.Nanite.LiveRebuildOnModification reads "
                + str(_out["cvar"]) + " after being set to 1. Without it "
                "the property change only invalidates the Nanite "
                "representation and NOTHING IS BUILT. Refusing before the "
                "write so this cannot report a build that did not happen.")
            raise RuntimeError(_out["error"])

    # ONE property-system write. set_editor_property raises
    # PostEditChangeProperty, which is the whole mechanism -- a direct
    # field poke would not propagate and would not build.
    _land.set_editor_property("enable_nanite", _want)

    for _a in _proxies:
        _lbl = str(_a.get_actor_label())
        _got = bool(_a.get_editor_property("enable_nanite"))
        _out["after"][_lbl] = _got
        if _got != _want:
            _out["mismatch"].append(_lbl)

    # A DIFFERENT REPRESENTATION THAN THE FLAG (non-negotiable 0/8). The
    # flag says what was ASKED FOR; a LandscapeNaniteComponent carrying a
    # static mesh says the build actually produced geometry.
    #
    # THIS IS A SNAPSHOT OF AN ASYNCHRONOUS PROCESS, AND SAYING SO IS THE
    # WHOLE POINT. The builds are dispatched async and throttled by
    # `landscape.Nanite.MaxAsyncProxyBuildsPerSecond` (default 6.0), so
    # reading the count immediately after the property write measures how
    # far the queue has got, NOT the final state. The first version of
    # this block returned "0 of 257 with a built mesh" some 34 seconds
    # after the write, on a world where all 256 geometry-bearing proxies
    # built correctly a few minutes later — a definite-looking zero
    # reported over work that was still in flight, which is the
    # "I could not look" class wearing a number (non-negotiable 6).
    #
    # `unreadable` is now separated from `absent` for the same reason: an
    # accessor that raised must never be counted as "no mesh".
    _with_mesh = 0
    _unreadable = 0
    _without = []
    for _a in _proxies:
        try:
            _nc = list(_a.get_components_by_class(
                _unreal.LandscapeNaniteComponent))
        except Exception:
            _unreadable += 1
            continue
        _has = False
        for _c in _nc:
            try:
                if _c.get_editor_property("static_mesh") is not None:
                    _has = True
                    break
            except Exception:
                _unreadable += 1
                _has = None
                break
        if _has:
            _with_mesh += 1
        elif _has is False and len(_without) < 8:
            _without.append(str(_a.get_actor_label()))
    _out["nanite_components"] = {{
        "proxies_total": len(_proxies),
        "with_built_mesh": _with_mesh,
        "unreadable": _unreadable,
        "first_without": _without,
        "snapshot_of_async_build": True,
    }}

    _out["ok"] = not _out["mismatch"]
except Exception as _e:
    if not _out["error"]:
        _out["error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--off", action="store_true",
                    help="disable Nanite instead of enabling it")
    ap.add_argument("--build", action="store_true",
                    help="set landscape.Nanite.LiveRebuildOnModification so "
                         "the property change BUILDS the Nanite meshes. "
                         "Without this the change only invalidates them.")
    ap.add_argument("--go", action="store_true",
                    help="actually apply; a bare run is a dry run")
    args = ap.parse_args(argv)

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        for e in errors:
            print("  - {0}".format(e))
        return 2

    want = not args.off
    actor = spec["actor_name"]
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("landscape : {0}".format(actor))
    print("enable_nanite -> {0}".format(want))
    print("build         : {0}".format(
        "YES (live rebuild cvar set first)" if args.build
        else "NO — invalidate only, nothing is built"))
    print("")
    if not args.go:
        print("DRY RUN. Nothing was sent. Re-run with --go to apply.")
        print("This mutates the world IN MEMORY and saves nothing; the copy")
        print("on disk stays as its own restore point until save_level.py.")
        return 0

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

        def _runner(source, marker):
            try:
                remote.open_command_connection(node["node_id"])
            except Exception as exc:
                print("  connection failed: {0}".format(exc))
                return None
            try:
                r = remote.run_command(source, unattended=True,
                                       exec_mode=remote_exec.MODE_EXEC_FILE)
                if not r or not r.get("success"):
                    print("  command failed: {0}".format(
                        (r or {}).get("result")))
                    return None
                return bootstrap._collect_output(r)
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass

        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level,
            lambda s, m: _parse_generic(_runner(s, m), m))
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            return 6
        print("  level {0}".format(detail))
        print("")

        src = PAYLOAD.format(want=want, do_build=bool(args.build),
                             actor=actor, marker=MARKER)
        got = _parse(_runner(src, MARKER))
        if got is None:
            print("COULD NOT READ the reply. The operation may or may not "
                  "have run — this is UNKNOWN, not a failure. Read the "
                  "state back with read_nanite_state.py before retrying.")
            return 5
        if got.get("error"):
            print("ERROR: {0}".format(got["error"]))
            return 5

        print("parent landscapes : {0}".format(got.get("parents")))
        print("streaming proxies : {0}".format(got.get("proxies")))
        if got.get("cvar") is not None:
            print("live-rebuild cvar : {0}".format(got["cvar"]))
        before = got.get("before") or {}
        after = got.get("after") or {}
        print("enable_nanite     : {0} -> {1} of {2} actors".format(
            sum(1 for v in before.values() if v),
            sum(1 for v in after.values() if v), len(after)))
        nc = got.get("nanite_components") or {}
        print("")
        print("A DIFFERENT REPRESENTATION THAN THE FLAG:")
        print("  proxies with a BUILT Nanite mesh : {0} of {1}".format(
            nc.get("with_built_mesh"), nc.get("proxies_total")))
        if nc.get("unreadable"):
            print("  COULD NOT READ on {0} — UNKNOWN, not absent".format(
                nc["unreadable"]))
        if nc.get("first_without"):
            print("  first without a mesh: {0}".format(
                ", ".join(nc["first_without"])))
        # The count above is a SNAPSHOT of an asynchronous, throttled
        # build queue (landscape.Nanite.MaxAsyncProxyBuildsPerSecond,
        # default 6/s). A low number here means "not yet", not "failed",
        # and the honest instrument says so rather than letting the
        # reader take a zero as a verdict.
        if nc.get("snapshot_of_async_build"):
            print("")
            print("  NOTE: Nanite meshes build ASYNCHRONOUSLY and are")
            print("  throttled to ~6 proxies/second, so this count is how")
            print("  far the queue had got at this instant — NOT the final")
            print("  state. A low count is 'not yet', not 'failed'. Re-read")
            print("  it later; the parent ALandscape legitimately has no")
            print("  mesh in a World Partition world, since the geometry")
            print("  lives in the streaming proxies.")
        if got.get("mismatch"):
            print("")
            print("MISMATCH on {0} actor(s); the world is in an unknown "
                  "state.".format(len(got["mismatch"])))
            return 5
        print("")
        print("Applied IN MEMORY. Nothing was saved.")
        return 0
    finally:
        try:
            remote.stop()
        except Exception:
            pass


def _parse_generic(text, marker):
    i = (text or "").find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(marker):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    sys.exit(main())
