"""set_landscape_scale.py — set the landscape scale from the recipe.

WHY THIS IS SCRIPTABLE WHEN set_actor_location WAS NOT
`set_actor_scale3d` / `set_actor_location` are runtime setters: they do
not fire PostEditChangeProperty, so `ULandscapeInfo::FixupProxiesTransform`
never runs and the streaming proxies keep their old transforms — the
parent moves and the terrain stays behind.

But `ALandscapeProxy::PostEditChangeProperty` explicitly handles
`RelativeScale3D` (LandscapeEdit.cpp:5954-6020: locks X and Y to the same
magnitude, updates `Info->DrawScale`, regenerates collision) and then at
:6644-6652 calls `Info->FixupProxiesTransform(true)` for
RelativeScale3D / RelativeLocation / RelativeRotation.

So setting the property through the editor property system — which does
raise PostEditChangeProperty — gets the same fixup the Details panel
gets. That is the whole difference.

VERIFY IMMEDIATELY AFTER. The claim above is read from source, not
observed, so this script re-reads every proxy's implied origin
(world - scale * section_base) and refuses to report success unless they
all still agree. A torn landscape is exactly what that check exists to
catch, and it is better to learn it here than three steps later.

Exit codes:
  0  scale set and proxies still consistent
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  landscape missing or not unique, OR the editor payload returned nothing
  5  scale did not take
  6  SCALE SET but the proxy tear-check did NOT pass -- either the proxies are
     TORN (the fixup did not run: do not save, re-import or restore the
     previous scale) OR the tear-check census was INCOMPLETE (tear state
     UNVERIFIED).
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
# Default to the SHIPPED 8K world, NOT landscape_spec's pre-8K default: a no-arg
# run of a scale MUTATION must target Landscape_Alpine8K, not the HISTORY
# Landscape_Alpine (scale_xy 400, CLAUDE.md marks it HISTORY). Pass --recipe
# for any other world.
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine_8k.json")
MARKER = "__LANDSCAPELAB_SCALE__"
TOL_CM = 1.0


def _payload(actor_name, sx, sy, sz):
    return '''
import json as _json
import unreal as _unreal

_target = {actor!r}
_want = [float({sx!r}), float({sy!r}), float({sz!r})]
_tol = {tol!r}
_out = {{"ok": False, "torn": None}}

_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

try:
    _guids = []
    for _d in _unreal.WorldPartitionBlueprintLibrary.get_actor_descs():
        _c = _d.get_editor_property("native_class")
        if (_c.get_name() if _c else "") in ("Landscape",
                                             "LandscapeStreamingProxy"):
            _guids.append(_d.get_editor_property("guid"))
    if _guids:
        _unreal.WorldPartitionBlueprintLibrary.load_actors(_guids)
except Exception as _exc:
    _out["load_error"] = "%s: %s" % (type(_exc).__name__, _exc)

_hits = [_a for _a in _unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.Landscape) if _a.get_actor_label() == _target]
_out["matches"] = len(_hits)

if len(_hits) == 1:
    _a = _hits[0]
    _root = _a.root_component
    _before = _root.get_editor_property("relative_scale3d")
    _out["before"] = [_before.x, _before.y, _before.z]

    # Property-system write: raises PostEditChangeProperty, which is what
    # routes into FixupProxiesTransform. A plain set_actor_scale3d would
    # not.
    _root.set_editor_property(
        "relative_scale3d",
        _unreal.Vector(_want[0], _want[1], _want[2]))

    _after = _root.get_editor_property("relative_scale3d")
    _out["after"] = [_after.x, _after.y, _after.z]
    _out["took"] = (abs(_after.x - _want[0]) < 1e-4 and
                    abs(_after.y - _want[1]) < 1e-4 and
                    abs(_after.z - _want[2]) < 1e-4)

    # Tear check: every component's implied origin must agree.
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
    # LESSON 9. This loop assembles the components the TEAR CHECK will
    # measure, and the tear check is the only thing standing between a
    # wrong inference and a landscape torn into 1024 pieces that
    # disagree by 7.8 km (lesson 6.3 — it has happened here). A
    # swallowed read silently removed a proxy from the census, so the
    # check verified agreement across the components it could see and
    # reported success. Fewer components read = fewer chances to
    # disagree, so the swallow made the check WEAKER exactly as reads
    # became less reliable.
    _srcs = [_a]
    _unreadable = []
    for _p in _proxies:
        try:
            _r = _p.get_editor_property("landscape_actor_ref")
        except Exception as _exc:
            _unreadable.append({{
                "path": _p.get_path_name(),
                "error": "%s: %s" % (type(_exc).__name__, _exc),
            }})
            continue
        if _r is not None and _r == _a:
            _srcs.append(_p)
    _out["ownership_unreadable"] = _unreadable

    _mins = [None, None]
    _maxs = [None, None]
    _n = 0
    for _s in _srcs:
        for _c in _s.get_components_by_class(_unreal.LandscapeComponent):
            _bx = int(_c.get_editor_property("section_base_x"))
            _by = int(_c.get_editor_property("section_base_y"))
            _loc = _c.get_world_location()
            _ox = _loc.x - _after.x * _bx
            _oy = _loc.y - _after.y * _by
            _n += 1
            for _i, _v in ((0, _ox), (1, _oy)):
                if _mins[_i] is None or _v < _mins[_i]:
                    _mins[_i] = _v
                if _maxs[_i] is None or _v > _maxs[_i]:
                    _maxs[_i] = _v
    _out["components_checked"] = _n
    if _n and _mins[0] is not None:
        _spread = max(_maxs[0] - _mins[0], _maxs[1] - _mins[1])
        _out["origin_spread_cm"] = _spread
        _out["implied_origin"] = [_mins[0], _mins[1]]
        _out["torn"] = _spread > _tol
    # `ok` requires a COMPLETE census, not just an agreeing one. Without
    # the `not _unreadable` term the tear check reports success whenever
    # the proxies it failed to read are the ones that disagree — a gate
    # satisfied by the failure it guards against (lesson 1.3), on the
    # write path of an operation that has already torn a landscape once.
    _out["ok"] = (bool(_out.get("took"))
                  and (_out.get("torn") is False)
                  and not _unreadable)

print("{marker}" + _json.dumps(_out))
'''.format(actor=actor_name, sx=sx, sy=sy, sz=sz, tol=TOL_CM,
           marker=MARKER)


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

    sx, sy, sz = spec["scale_x"], spec["scale_y"], spec["scale_z"]
    print("Landscape : {0}".format(spec["actor_name"]))
    print("Target    : {0} / {1} / {2}".format(sx, sy, sz))
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

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(spec["actor_name"], sx, sy, sz))
        if r is None:
            print("FAIL: payload returned nothing. Run "
                  "verify_landscape.py before doing anything else.")
            return 4
        if r.get("matches") != 1:
            print("REFUSE: need exactly one landscape labelled {0!r}, "
                  "found {1}".format(spec["actor_name"], r.get("matches")))
            return 4

        print("  before : {0}".format(r.get("before")))
        print("  after  : {0}".format(r.get("after")))
        print("  components checked : {0}".format(
            r.get("components_checked")))
        if r.get("origin_spread_cm") is not None:
            print("  implied-origin spread : {0:.3f} cm".format(
                r["origin_spread_cm"]))
        if not r.get("took"):
            print("")
            print("FAIL: the scale did not take.")
            return 5
        if r.get("torn"):
            print("")
            print("TORN: components disagree on the landscape origin by "
                  "{0:.1f} cm — FixupProxiesTransform did NOT run.".format(
                      r.get("origin_spread_cm", 0.0)))
            print("DO NOT SAVE. Re-import, or restore the previous scale "
                  "from the Details panel, which fires the fixup.")
            return 6
        unreadable = r.get("ownership_unreadable") or []
        if unreadable:
            print("")
            print("SCALE WAS WRITTEN, BUT THE TEAR CHECK IS INCOMPLETE — "
                  "treat this landscape as UNVERIFIED.")
            print("landscape_actor_ref could not be read on {0} "
                  "proxy/proxies, so their components were never "
                  "measured:".format(len(unreadable)))
            for u in unreadable:
                print("  !! {0}".format(u.get("path")))
                print("     {0}".format(u.get("error")))
            print("")
            print("The components that WERE read agree (spread {0:.3f} cm "
                  "over {1}), but a tear is a DISAGREEMENT between "
                  "components, so a census missing members is exactly the "
                  "census most likely to report agreement. DO NOT SAVE "
                  "until the unreadable proxies are explained."
                  .format(r.get("origin_spread_cm", 0.0),
                          r.get("components_checked")))
            return 6
        print("")
        print("Scale set; all {0} components still agree on the origin "
              "(spread {1:.3f} cm). Proxies followed.".format(
                  r.get("components_checked"),
                  r.get("origin_spread_cm", 0.0)))
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
