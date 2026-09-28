"""apply_landscape_transform.py — set the live landscape's transform from
the recipe.

SCENE MUTATION. This is the first script in the repo that changes the
editor's state. It moves the landscape actor to `landscape.location_cm`
and, with --allow-scale, corrects its scale to the recipe's values. It
then saves the level.

WHY THIS EXISTS
The New Landscape dialog's Location field is the landscape's CENTRE, not
the actor origin: the actor lands at `dialog_location + offset` where
`offset = -(component_count * quads_per_component / 2) * scale`
(LandscapeEditorDetailCustomization_NewLandscape.cpp:1219). The first
spec printout fed `landscape.location_cm` straight into that field, so
the actor was created at -403200, -403200 instead of the origin. Rather
than rebuild the landscape by hand, this script reconciles the live actor
to the recipe — which is what a recipe-driven pipeline should be able to
do anyway.

IDEMPOTENT (hard rule 3). It sets absolute values read from the recipe,
never deltas. Running it twice changes nothing the second time, and it
says so rather than re-saving a clean level.

SCALE IS GUARDED. Changing a landscape's scale after creation rescales
the terrain and is not a cosmetic fix, so a scale mismatch is REPORTED
and REFUSED by default — BEFORE anything is mutated, so an exit-5
refusal always means the scene is untouched. --allow-scale opts in
explicitly.

WORLD PARTITION IS REFUSED. In a WP level the terrain's components live
on LandscapeStreamingProxy actors, and the editor aligns those to the
parent only via ALandscape::PostEditMove ->
ULandscapeInfo::FixupProxiesTransform (LandscapeEdit.cpp:5138-5147,
Landscape.cpp:6113-6174) — an interactive-move hook that a scripted
set_actor_location never fires. Moving only the parent would leave the
terrain behind while the actor reports the recipe origin. If any
streaming proxy exists (or the proxy census fails), this script refuses
with exit 7 before touching anything. On a WP level, fix placement by
recreating the landscape from landscape_spec.py's corrected printout.

The save path is safe for external actors: save_current_level ->
FEditorFileUtils::SaveLevel -> SaveWorld appends the world package's
external (OFPA) actor packages via SaveExternalPackages
(FileHelpers.cpp:835, :1220), so in non-WP-but-OFPA setups the moved
actor's own package is included in the save.

Conduct rule 7 applies in full and is delegated to bootstrap.py's audited
gate — nothing reaches a node that has not matched UE_PROJECT_ROOT. The
landscape is located through verify_landscape.py's probe, so the same
"exactly one landscape actor" contract is enforced here before anything
is written.

Hard rule 4: this changes the scene, so a changelog entry is required
after running. The capture leg of rule 4 needs scripts/capture.py, which
does not exist yet — see the note printed on success.

Exit codes:
  0  transform matches the recipe (either already, or after this run)
  1  unexpected error / bad arguments
  2  recipe missing, unparseable, or geometrically illegal
  3  editor identity gate refused (conduct rule 7)
  4  landscape actor missing, duplicated, or ambiguous
  5  scale mismatch and --allow-scale was not given (nothing changed)
  6  the mutation did not take (not saved), or the level could not be
     saved
  7  World Partition streaming proxies present — scripted landscape
     moves are unsupported; refused before any change

Unreal APIs used (all long-stable for UE5; nothing 5.8-only):
  unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world
  unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level
  unreal.GameplayStatics.get_all_actors_of_class / unreal.Landscape
  Actor.set_actor_location / set_actor_scale3d / get_actor_label
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import landscape_spec     # noqa: E402 — shared derivation
import verify_landscape   # noqa: E402 — shared probe and node selection

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MUTATE_MARKER = "__LANDSCAPELAB_MUTATE__"
TOLERANCE = verify_landscape.TOLERANCE


def _mutate_source(actor_name, location, scale, set_scale, save):
    """Build the mutation payload.

    All recipe-derived values are interpolated as Python literals via
    !r on validated types (str for the label, float for the numbers), so
    there is no path from recipe text to executable code.
    """
    return '''
import json as _json
import unreal as _unreal

_target = {actor!r}
_want_loc = [float({lx!r}), float({ly!r}), float({lz!r})]
_want_scale = [float({sx!r}), float({sy!r}), float({sz!r})]
_set_scale = {set_scale!r}
_save = {save!r}
_tol = {tol!r}

_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()
_out = {{"ok": False}}

_all = list(_unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.Landscape))
_matches = [_a for _a in _all if _a.get_actor_label() == _target]
_out["landscape_total"] = len(_all)
_out["matching"] = len(_matches)

_proxies = None
try:
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
except Exception:
    _proxies = None
_out["proxy_total"] = None if _proxies is None else len(_proxies)

if _proxies is None or len(_proxies) > 0:
    # World Partition (or indeterminate): the terrain's components live
    # on LandscapeStreamingProxy actors. The editor aligns proxies to
    # the parent ONLY via ALandscape::PostEditMove ->
    # ULandscapeInfo::FixupProxiesTransform (LandscapeEdit.cpp:5138-5147,
    # Landscape.cpp:6113-6174) — an interactive-move hook a scripted
    # set_actor_location never fires. Moving only the parent tears the
    # world: actor at the recipe origin, terrain still where it was.
    # Refuse before touching anything.
    _out["refused_world_partition"] = True
    _out["ok"] = True
elif len(_all) == 1 and len(_matches) == 1:
    _a = _matches[0]
    _before_l = _a.get_actor_location()
    _before_s = _a.get_actor_scale3d()
    _out["before_location"] = [_before_l.x, _before_l.y, _before_l.z]
    _out["before_scale"] = [_before_s.x, _before_s.y, _before_s.z]

    _loc_ok = (abs(_before_l.x - _want_loc[0]) <= _tol and
               abs(_before_l.y - _want_loc[1]) <= _tol and
               abs(_before_l.z - _want_loc[2]) <= _tol)
    _scale_ok = (abs(_before_s.x - _want_scale[0]) <= _tol and
                 abs(_before_s.y - _want_scale[1]) <= _tol and
                 abs(_before_s.z - _want_scale[2]) <= _tol)
    _out["location_already_correct"] = _loc_ok
    _out["scale_already_correct"] = _scale_ok

    if (not _scale_ok) and (not _set_scale):
        # Refuse BEFORE touching anything. A refusal printed after a
        # partial apply-and-save would be a lie about the scene's state.
        _out["refused_scale"] = True
        _out["changed"] = False
        _out["saved"] = None
        _out["ok"] = True
    else:
        _changed = False
        if not _loc_ok:
            _a.set_actor_location(
                _unreal.Vector(_want_loc[0], _want_loc[1], _want_loc[2]),
                False, True)
            _changed = True
        if _set_scale and not _scale_ok:
            _a.set_actor_scale3d(
                _unreal.Vector(_want_scale[0], _want_scale[1],
                               _want_scale[2]))
            _changed = True
        _out["changed"] = _changed

        _after_l = _a.get_actor_location()
        _after_s = _a.get_actor_scale3d()
        _out["after_location"] = [_after_l.x, _after_l.y, _after_l.z]
        _out["after_scale"] = [_after_s.x, _after_s.y, _after_s.z]

        _took = (abs(_after_l.x - _want_loc[0]) <= _tol and
                 abs(_after_l.y - _want_loc[1]) <= _tol and
                 abs(_after_l.z - _want_loc[2]) <= _tol and
                 abs(_after_s.x - _want_scale[0]) <= _tol and
                 abs(_after_s.y - _want_scale[1]) <= _tol and
                 abs(_after_s.z - _want_scale[2]) <= _tol)
        _out["took"] = _took

        # Never persist a mutation that did not land on the recipe
        # values — a failed move must stay unsaved and revertable.
        if _save and _changed and _took:
            try:
                _out["saved"] = bool(_unreal.get_editor_subsystem(
                    _unreal.LevelEditorSubsystem).save_current_level())
            except Exception as _exc:
                _out["saved"] = False
                _out["save_error"] = "{{0}}: {{1}}".format(
                    type(_exc).__name__, _exc)
        else:
            _out["saved"] = None
        _out["ok"] = True

print("{marker}" + _json.dumps(_out))
'''.format(actor=actor_name,
           lx=location[0], ly=location[1], lz=location[2],
           sx=scale[0], sy=scale[1], sz=scale[2],
           set_scale=bool(set_scale), save=bool(save), tol=TOLERANCE,
           marker=MUTATE_MARKER)


def _parse(text):
    idx = text.find(MUTATE_MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(MUTATE_MARKER):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
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
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  command did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(result))
    except Exception as exc:
        print("  command errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _vec(values):
    return "[{0}]".format(", ".join("{0:.1f}".format(v) for v in values))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--allow-scale", action="store_true",
                        help="Also correct scale. Rescaling an existing "
                             "landscape changes the terrain -- opt in.")
    parser.add_argument("--no-save", action="store_true",
                        help="Apply the transform but leave the level "
                             "dirty for manual saving.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        print("REFUSE: recipe geometry is not buildable:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    want_loc = spec["location_cm"]
    want_scale = [spec["scale_x"], spec["scale_y"], spec["scale_z"]]

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("Landscape       : {0}".format(spec["actor_name"]))
    print("Target location : {0}".format(_vec(want_loc)))
    print("Target scale    : {0}{1}".format(
        _vec(want_scale),
        "" if args.allow_scale else "  (checked, not applied)"))
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
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        result = _run(remote_exec, remote, node["node_id"],
                      _mutate_source(spec["actor_name"], want_loc,
                                     want_scale, args.allow_scale,
                                     not args.no_save))
        if result is None:
            print("FAIL: the mutation payload returned nothing. The scene "
                  "may or may not have changed — run verify_landscape.py.")
            return 6

        if result.get("refused_world_partition"):
            print("REFUSE: this level uses World Partition streaming "
                  "proxies ({0} found).".format(
                      result.get("proxy_total", "?")))
            print("  The terrain's components live on proxy actors that "
                  "follow the parent")
            print("  only through the editor's interactive-move hook "
                  "(ALandscape::PostEditMove")
            print("  -> FixupProxiesTransform); a scripted move tears the "
                  "world apart. Nothing")
            print("  was changed. Fix placement by recreating the "
                  "landscape from the corrected")
            print("  landscape_spec.py printout, then re-run "
                  "verify_landscape.py.")
            return 7

        total = result.get("landscape_total", 0)
        matching = result.get("matching", 0)
        if not result.get("ok"):
            print("FAIL: refusing to mutate.")
            print("  landscape actors in level: {0}".format(total))
            print("  labelled {0!r}: {1}".format(
                spec["actor_name"], matching))
            print("  Exactly one landscape, correctly labelled, is "
                  "required before anything is written.")
            return 4

        print("--- transform ---")
        print("  before  location {0}  scale {1}".format(
            _vec(result["before_location"]), _vec(result["before_scale"])))

        if result.get("refused_scale"):
            print("")
            print("REFUSE: scale does not match the recipe and --allow-scale "
                  "was not given.")
            print("  Rescaling an existing landscape changes the terrain; "
                  "it is not a cosmetic")
            print("  correction. Nothing was changed or saved.")
            return 5

        print("  after   location {0}  scale {1}".format(
            _vec(result["after_location"]), _vec(result["after_scale"])))

        after = result["after_location"]
        if any(abs(after[i] - want_loc[i]) > TOLERANCE for i in range(3)):
            print("")
            print("FAIL: the location did not take. Live is {0}, recipe "
                  "wants {1}. The level was NOT saved.".format(
                      _vec(after), _vec(want_loc)))
            return 6

        if args.allow_scale:
            after_s = result["after_scale"]
            if any(abs(after_s[i] - want_scale[i]) > TOLERANCE
                   for i in range(3)):
                print("")
                print("FAIL: the scale did not take. Live is {0}, recipe "
                      "wants {1}. The level was NOT saved.".format(
                          _vec(after_s), _vec(want_scale)))
                return 6

        if not result.get("changed"):
            print("")
            print("Already correct — nothing changed, level not saved.")
            return 0

        saved = result.get("saved")
        if saved is False:
            print("")
            print("FAIL: the transform was applied but the level did NOT "
                  "save.")
            if result.get("save_error"):
                print("  {0}".format(result["save_error"]))
            print("  Save manually in the editor (Ctrl+S) before running "
                  "anything else.")
            return 6

        print("")
        if saved:
            print("Applied and level saved.")
        elif args.no_save:
            print("Applied. Level NOT saved (--no-save) — save before "
                  "running anything else.")
        else:
            print("Applied, but the save state is indeterminate — check "
                  "the editor before running anything else.")
        print("")
        print("SCENE CHANGED — hard rule 4 requires a changelog entry, and")
        print("a capture. scripts/capture.py does not exist yet, so the")
        print("capture leg cannot be satisfied; record that gap rather")
        print("than treating rule 4 as met.")
        print("Next: python scripts/verify_landscape.py")
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
