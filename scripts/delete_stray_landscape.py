"""delete_stray_landscape.py — remove the stray landscape, by signature.

**THE FIRST DESTRUCTIVE EDITOR MUTATION IN THIS REPO.** It deletes actors
and saves the level. Read the safety model before running it.

WHY IT EXISTS
The level holds two ALandscape actors. `Landscape_Alpine` is the real
1009 import (scale 800/800/500, geometry 63x2x8+1). `Landscape` is a
stray with default scale and 2017 geometry, most likely from a
Create-tab click before switching to Import from File.
`verify_landscape.py` refuses while both exist, so nothing downstream can
run. The manual deletion did not cooperate in the UI.

SAFETY MODEL — five independent gates, each fail-closed

1. **Conduct rule 7** — delegated to bootstrap.py's audited gate. Nothing
   reaches an editor that has not matched UE_PROJECT_ROOT.

2. **Full residency, fail-closed on load failure.** World Partition only
   exposes LOADED actors, so a census taken with regions unloaded is a
   lie. Every landscape actor descriptor is loaded via
   WorldPartitionBlueprintLibrary.load_actors() before anything is
   counted. The run aborts unless ALL of: the desc query and load raised
   no error, the loaded landscape/proxy counts equal the on-disk actor
   descriptor counts (nothing can remain unloaded or unsaved-invisible),
   and the proxy count equals --expect-proxies (default 16 — the
   post-deletion steady state; it was 68 while the stray existed, and 68
   turned out to be a partial-census artefact since the true
   two-landscape total was 80). Surviving a load error would be fatal to
   the model: an --expect-proxies value measured on a partially loaded
   level — as the original 68 was — makes a count-only gate pass exactly
   when loading fails, which is why residency also requires loaded
   counts to equal on-disk descriptor counts. (Python note: get_actor_descs() is a
   bool + out-param UFUNCTION, so the glue returns the Array on success
   and None on failure — iterating None raises, which aborts the run.)

3. **Signature identification, never label.** Proxy labels are NOT
   unique — they are generated from World Partition grid coordinates, and
   four labels currently collide across the two landscapes. The stray is
   identified by ALL THREE of: scale == 100/100/100 (within tolerance),
   derived overall resolution == 2017, and label != the recipe's
   actor_name. Zero matches or two matches aborts.

4. **Positive attribution only — and attribution must be COMPLETE.** A
   proxy is deleted only if its LandscapeActorRef (private
   UPROPERTY(EditAnywhere) on ALandscapeStreamingProxy, readable via
   get_editor_property; LandscapeStreamingProxy.h:35-36) resolves to the
   stray itself. Stronger: if ANY proxy fails to attribute to either the
   keeper or the stray (unreadable, unresolved, or pointing at neither),
   the run aborts before deleting anything — deleting the stray while
   one of its proxies is unattributable would orphan that proxy.

5. **Hard assertion on the keeper.** Before deletion, every actor on the
   kill list is checked against the keeper and its attributed proxies. If
   any overlap is found the script raises and deletes NOTHING. This is an
   assertion, not a filter: a filter silently shrinks the kill list, an
   assertion stops the run.

The full kill list, with attribution evidence per actor, is printed
BEFORE any deletion, and --dry-run stops there.

DIRTY PACKAGES
Ryan reported being in Landscape Sculpt mode with unsaved changes. The
script reports dirty map and content packages before doing anything and,
unless --allow-dirty is given, refuses rather than saving blind. This is
not hypothetical: save_current_level -> FEditorFileUtils::SaveLevel ->
SaveWorld -> SaveExternalPackages saves EVERY dirty external actor
package of the level (FileHelpers.cpp:835, :1220 in UE 5.8), so with
--allow-dirty an in-progress sculpt on the keeper WOULD be committed to
disk by our save.

PRECONDITIONS (manual)
- Exit Landscape mode (use Selection mode) before running. An active
  landscape edit session holds pointers to landscape actors this script
  deletes; the UI delete path handles that, this API path does not.
- git commit the LandscapeLab content BEFORE running (conduct rule 3) —
  with the level under git+LFS, the deletion is recoverable only if the
  before-state was committed.

DRY RUN IS NOT ZERO-EFFECT
--dry-run deletes nothing and never saves, but the residency gate still
calls load_actors(), which changes which World Partition actors are
loaded in the editor session. Disclosed deliberately.

DELETION MECHANICS (verified against UE 5.8 source)
ALandscapeStreamingProxy::CanDeleteSelectedActor returns true
(LandscapeEdit.cpp:6408) and ALandscape::CanDeleteSelectedActor allows
deletion once all related actors are gone (LandscapeEdit.cpp:6462-6468),
so proxies-first-then-parent is the editor's own sanctioned order.
ALandscapeProxy::Destroyed() calls ULandscapeInfo::RecreateLandscapeInfo
on every destroy (Landscape.cpp:5090-5098), so landscape-info bookkeeping
is rebuilt as we go; EditorActorSubsystem::DestroyActors runs each
destroy through World->EditorDestroyActor in a scoped transaction
(EditorActorSubsystem.cpp:546-626). Deleted OFPA actor packages are
removed on the final save through the engine's own checkout+save path.

Pipeline rule 4: this changes the scene. Run scripts/capture.py
afterwards. (A one-line LESSONS.md note is suggested, not required —
the live rule no longer mandates it.)

Exit codes:
  0  stray deleted and level saved (or --dry-run completed)
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  residency gate failed — desc load errored, loaded counts do not
     match on-disk desc counts, or proxy count != --expect-proxies
  5  identification/attribution failed — zero or multiple stray
     candidates, or a proxy attributed to neither landscape. (A THIRD path,
     keeper_set_incomplete, also returns 5 but is currently UNREACHABLE: an
     unreadable landscape_actor_ref raises during identification and aborts
     the payload, so it surfaces as exit 7 below, not here.)
  6  refused: dirty packages present and --allow-dirty not given
  7  deletion or save failed, the post-check found survivors, the payload
     returned NOTHING (connection/parse/exception, incl. an unreadable proxy
     ref that aborts identification), or the payload ended in an unexpected
     stage
  8  SAFETY ASSERTION TRIPPED — the kill list touched the keeper.
     Nothing was deleted. This should never happen; investigate.

Unreal APIs used (all long-stable for UE5; nothing 5.8-only):
  unreal.WorldPartitionBlueprintLibrary.get_actor_descs / .load_actors
  unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages
      / .get_dirty_content_packages
  unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor
  unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level
  unreal.GameplayStatics.get_all_actors_of_class
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import landscape_spec     # noqa: E402 — shared recipe loading
import verify_landscape   # noqa: E402 — shared node selection

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_DELETE__"

# Scale comparison tolerance. The stray's scale is an exact editor
# default; anything near 100 on all three axes is the signature.
SCALE_TOLERANCE = 1e-3


def _payload(keeper_label, stray_scale, stray_resolution, expect_proxies,
             dry_run, allow_dirty):
    """Build the mutation payload.

    Every interpolated value is a validated str, float, int or bool.
    """
    return '''
import json as _json
import unreal as _unreal

_keeper_label = {keeper!r}
_want_scale = float({scale!r})
_want_res = int({res!r})
_expect_proxies = int({expect!r})
_dry_run = {dry!r}
_allow_dirty = {allow_dirty!r}
_tol = {tol!r}

_out = {{"stage": "start", "ok": False, "deleted": [], "kill_list": []}}

_ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
_world = _ues.get_editor_world()
_eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)

# ---- dirty package report -------------------------------------------
_dirty_maps, _dirty_content = [], []
try:
    for _p in _unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        _dirty_maps.append(_p.get_name())
    for _p in _unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        _dirty_content.append(_p.get_name())
    _out["dirty_query_ok"] = True
except Exception as _exc:
    _out["dirty_query_ok"] = False
    _out["dirty_error"] = "%s: %s" % (type(_exc).__name__, _exc)
_out["dirty_maps"] = _dirty_maps
_out["dirty_content"] = _dirty_content

if (_dirty_maps or _dirty_content) and not _allow_dirty:
    _out["stage"] = "refused_dirty"
    print("{marker}" + _json.dumps(_out))
else:
    # ---- load every World Partition actor ---------------------------
    _out["stage"] = "loading"
    _load_error = None
    _guids = []
    _desc_landscapes = 0
    _desc_proxies = 0
    try:
        # bool + out-param UFUNCTION: the Python glue returns the Array
        # on success and None on failure; iterating None raises, which
        # lands in _load_error and fails the residency gate below.
        _descs = _unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
        for _d in _descs:
            _cls = _d.get_editor_property("native_class")
            _name = _cls.get_name() if _cls is not None else ""
            if "Landscape" in _name:
                _guids.append(_d.get_editor_property("guid"))
            if _name == "Landscape":
                _desc_landscapes += 1
            elif _name == "LandscapeStreamingProxy":
                _desc_proxies += 1
        _out["landscape_descs"] = len(_guids)
        if _guids:
            _unreal.WorldPartitionBlueprintLibrary.load_actors(_guids)
    except Exception as _exc:
        _load_error = "%s: %s" % (type(_exc).__name__, _exc)
    _out["load_error"] = _load_error
    _out["desc_landscapes"] = _desc_landscapes
    _out["desc_proxies"] = _desc_proxies

    # ---- census after loading ---------------------------------------
    _landscapes = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape))
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
    _out["landscape_count"] = len(_landscapes)
    _out["proxy_count"] = len(_proxies)
    _out["landscape_labels"] = [_a.get_actor_label() for _a in _landscapes]

    # Residency requires: no load error, loaded == on-disk desc counts
    # (nothing unloaded, nothing unsaved-invisible), and the operator's
    # expected proxy total. Any shortfall aborts before identification.
    _residency_ok = (_load_error is None
                     and len(_landscapes) == _desc_landscapes
                     and len(_proxies) == _desc_proxies
                     and len(_proxies) == _expect_proxies)
    if not _residency_ok:
        _out["stage"] = "residency_failed"
        print("{marker}" + _json.dumps(_out))
    else:
        # ---- identify the stray by SIGNATURE, never by label ---------
        _out["stage"] = "identifying"

        def _derived_resolution(_actor, _all_proxies):
            # LESSON 9: a failed probe is not a negative result. This
            # runs on the IDENTIFICATION path of a deletion. Swallowing
            # the read made an unreadable proxy indistinguishable from a
            # proxy belonging to somebody else, so its components were
            # dropped from the base set and the derived resolution came
            # out of a partial census - the exact shape of lesson 2.6,
            # an invariant measured on incomplete state, feeding a gate
            # that decides what gets destroyed.
            _bases = set()
            _sources = [_actor]
            for _p in _all_proxies:
                try:
                    _ref = _p.get_editor_property("landscape_actor_ref")
                except Exception as _exc:
                    raise RuntimeError(
                        "landscape_actor_ref could not be READ on %s "
                        "(%s: %s). The signature could not be COMPUTED, "
                        "which is not the same as not matching - refusing "
                        "rather than deriving a resolution from a partial "
                        "census." % (_p.get_path_name(),
                                     type(_exc).__name__, _exc))
                if _ref is not None and _ref == _actor:
                    _sources.append(_p)
            for _s in _sources:
                for _c in _s.get_components_by_class(
                        _unreal.LandscapeComponent):
                    _bases.add(int(
                        _c.get_editor_property("section_base_x")))
            if len(_bases) < 2:
                return None
            _sorted = sorted(_bases)
            _steps = set()
            for _i in range(len(_sorted) - 1):
                _steps.add(_sorted[_i + 1] - _sorted[_i])
            if len(_steps) != 1:
                return None
            _step = _steps.pop()
            return _sorted[-1] - _sorted[0] + _step + 1

        _candidates = []
        _profiles = []
        for _a in _landscapes:
            _label = _a.get_actor_label()
            _s = _a.get_actor_scale3d()
            _scale_match = (abs(_s.x - _want_scale) <= _tol and
                            abs(_s.y - _want_scale) <= _tol and
                            abs(_s.z - _want_scale) <= _tol)
            _res = _derived_resolution(_a, _proxies)
            _res_match = (_res == _want_res)
            _label_match = (_label != _keeper_label)
            _profiles.append({{
                "label": _label,
                "scale": [_s.x, _s.y, _s.z],
                "derived_resolution": _res,
                "scale_is_stray": _scale_match,
                "resolution_is_stray": _res_match,
                "not_keeper": _label_match,
            }})
            if _scale_match and _res_match and _label_match:
                _candidates.append(_a)
        _out["profiles"] = _profiles

        if len(_candidates) != 1:
            _out["stage"] = "identification_failed"
            _out["candidate_count"] = len(_candidates)
            print("{marker}" + _json.dumps(_out))
        else:
            _stray = _candidates[0]
            _keepers = [_a for _a in _landscapes if _a != _stray]
            _out["stray_label"] = _stray.get_actor_label()
            _out["keeper_labels"] = [
                _k.get_actor_label() for _k in _keepers]

            # ---- positive attribution only, and it must be total --
            _kill, _spared, _unattributed = [], [], []
            for _p in _proxies:
                _ref, _err = None, None
                try:
                    _ref = _p.get_editor_property("landscape_actor_ref")
                except Exception as _exc:
                    _err = "%s: %s" % (type(_exc).__name__, _exc)
                if _ref is not None and _ref == _stray:
                    _kill.append(_p)
                    _out["kill_list"].append({{
                        "label": _p.get_actor_label(),
                        "path": _p.get_path_name(),
                        "evidence": "landscape_actor_ref -> " +
                                    _stray.get_actor_label(),
                    }})
                elif _ref is not None and any(
                        _ref == _k for _k in _keepers):
                    _spared.append({{
                        "label": _p.get_actor_label(),
                        "owner": _ref.get_actor_label(),
                    }})
                else:
                    _reason = "landscape_actor_ref is None/unresolved"
                    if _err is not None:
                        _reason = "READ FAILED: " + _err
                    elif _ref is not None:
                        _reason = ("resolves to neither keeper nor "
                                   "stray: " + _ref.get_actor_label())
                    _unattributed.append({{
                        "label": _p.get_actor_label(),
                        "reason": _reason,
                    }})
            _out["spared_count"] = len(_spared)
            _out["spared_sample"] = _spared[:8]
            _out["unattributed"] = _unattributed

            # ---- HARD ASSERTION: never touch the keeper ----------
            # LESSON 9, AND THIS IS THE DANGEROUS ONE. This set is the
            # keeper's protection. A swallowed read dropped a keeper's
            # proxy OUT of the protected set - while the very same proxy
            # could still have entered the kill list above, where its
            # read succeeded. So the hard assertion could pass with a
            # keeper's proxy queued for deletion: a guard that weakens
            # silently, precisely when reads are unreliable, which is
            # precisely when it is needed. Any unreadable proxy now
            # trips the assertion instead.
            _keeper_set = set()
            _keeper_unreadable = []
            for _k in _keepers:
                _keeper_set.add(_k.get_path_name())
                for _p in _proxies:
                    try:
                        _r = _p.get_editor_property(
                            "landscape_actor_ref")
                    except Exception as _exc:
                        _keeper_unreadable.append({{
                            "path": _p.get_path_name(),
                            "error": "%s: %s" % (type(_exc).__name__,
                                                 _exc),
                        }})
                        continue
                    if _r is not None and _r == _k:
                        _keeper_set.add(_p.get_path_name())
            _out["keeper_set_unreadable"] = _keeper_unreadable
            _violation = [_a.get_path_name() for _a in
                          ([_stray] + _kill)
                          if _a.get_path_name() in _keeper_set]
            _out["assertion_violations"] = _violation

            if _keeper_unreadable:
                # Refuse BEFORE the mutation, in the same payload as the
                # mutation. Host-side checking is reporting, not gating
                # (lesson 15.3) - and a "refusal" evaluated after the
                # delete is the single most repeated defect in this repo.
                _out["stage"] = "keeper_set_incomplete"
                print("{marker}" + _json.dumps(_out))
            elif _violation:
                _out["stage"] = "assertion_tripped"
                print("{marker}" + _json.dumps(_out))
            elif _unattributed:
                _out["stage"] = "attribution_incomplete"
                print("{marker}" + _json.dumps(_out))
            else:
                _out["kill_total"] = len(_kill) + 1
                if _dry_run:
                    _out["stage"] = "dry_run"
                    _out["ok"] = True
                    print("{marker}" + _json.dumps(_out))
                else:
                    _out["stage"] = "deleting"
                    _failed = []
                    for _p in _kill:
                        _lbl = _p.get_actor_label()
                        _pth = _p.get_path_name()
                        if _eas.destroy_actor(_p):
                            _out["deleted"].append(_pth)
                        else:
                            _failed.append(_lbl)
                    _stray_path = _stray.get_path_name()
                    if _eas.destroy_actor(_stray):
                        _out["deleted"].append(_stray_path)
                    else:
                        _failed.append(_out["stray_label"])
                    _out["failed"] = _failed

                    _after = list(
                        _unreal.GameplayStatics.get_all_actors_of_class(
                            _world, _unreal.Landscape))
                    _out["landscapes_after"] = [
                        _a.get_actor_label() for _a in _after]
                    _out["proxies_after"] = len(list(
                        _unreal.GameplayStatics.get_all_actors_of_class(
                            _world, _unreal.LandscapeStreamingProxy)))

                    if not _failed and len(_after) == len(_keepers):
                        try:
                            _out["saved"] = bool(
                                _unreal.get_editor_subsystem(
                                    _unreal.LevelEditorSubsystem
                                ).save_current_level())
                        except Exception as _exc:
                            _out["saved"] = False
                            _out["save_error"] = "%s: %s" % (
                                type(_exc).__name__, _exc)
                        _out["ok"] = bool(_out.get("saved"))
                        _out["stage"] = "done"
                    else:
                        _out["stage"] = "deletion_incomplete"
                    print("{marker}" + _json.dumps(_out))
'''.format(keeper=keeper_label, scale=float(stray_scale),
           res=int(stray_resolution), expect=int(expect_proxies),
           dry=bool(dry_run), allow_dirty=bool(allow_dirty),
           tol=SCALE_TOLERANCE, marker=MARKER)


def _parse(text):
    idx = text.find(MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(MARKER):].lstrip()
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--stray-scale", type=float, default=100.0,
                        help="Uniform scale identifying the stray.")
    parser.add_argument("--stray-resolution", type=int, default=2017,
                        help="Derived overall resolution of the stray.")
    parser.add_argument("--expect-proxies", type=int, default=16,
                        help="TOTAL streaming-proxy count across ALL "
                             "landscapes after full residency load. Must "
                             "also equal the on-disk desc count. Default 16 "
                             "= Landscape_Alpine's 4x4 grid, the post-"
                             "deletion steady state.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Identify and print the kill list, delete "
                             "nothing. NOTE: still calls load_actors(), "
                             "which changes which World Partition actors "
                             "are loaded in the editor session.")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Proceed despite unsaved packages. WARNING: "
                             "the final save commits ALL dirty external "
                             "actor packages, including an in-progress "
                             "sculpt on the keeper.")
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
    keeper = spec["actor_name"]

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("KEEPER (never deleted): {0!r}".format(keeper))
    print("Stray signature : scale {0}/{0}/{0} AND resolution {1} AND "
          "label != keeper".format(args.stray_scale, args.stray_resolution))
    print("Mode            : {0}".format(
        "DRY RUN — nothing will be deleted" if args.dry_run
        else "DESTRUCTIVE"))
    if not args.dry_run:
        print("")
        print("Preconditions (manual, see docstring):")
        print("  - level committed to git BEFORE this run (conduct rule 3)")
        print("  - Landscape mode exited (Selection mode active)")
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

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(keeper, args.stray_scale, args.stray_resolution,
                          args.expect_proxies, args.dry_run,
                          args.allow_dirty))
        if r is None:
            print("FAIL: the payload returned nothing. Scene state "
                  "unknown — run scripts/landscape_inventory.py.")
            return 7

        # ---- dirty package report --------------------------------
        print("--- unsaved packages ---")
        if not r.get("dirty_query_ok"):
            print("  could not query: {0}".format(r.get("dirty_error")))
        maps = r.get("dirty_maps") or []
        content = r.get("dirty_content") or []
        if not maps and not content:
            print("  none")
        for p in maps:
            print("  MAP     {0}".format(p))
        for p in content:
            print("  CONTENT {0}".format(p))

        stage = r.get("stage")
        if stage == "refused_dirty":
            print("")
            print("REFUSED: unsaved packages exist. Not saving blind — an")
            print("unsaved sculpt would either be committed to disk by our")
            print("save or lost by our deletion. Save or discard in the")
            print("editor, then re-run. --allow-dirty overrides.")
            return 6
        if args.allow_dirty and (maps or content):
            print("")
            print("WARNING: --allow-dirty given. If this run reaches the")
            print("save step, ALL dirty packages listed above are saved")
            print("(SaveLevel -> SaveWorld -> SaveExternalPackages),")
            print("including any in-progress sculpt on the keeper.")

        print("")
        print("--- residency ---")
        print("  landscape actor descs loaded : {0}".format(
            r.get("landscape_descs")))
        print("  descs on disk                : {0} landscapes, {1} "
              "proxies".format(r.get("desc_landscapes"),
                               r.get("desc_proxies")))
        if r.get("load_error"):
            print("  load error: {0}".format(r["load_error"]))
        print("  landscapes visible           : {0} {1}".format(
            r.get("landscape_count"), r.get("landscape_labels")))
        print("  proxies visible              : {0} (need {1}, and must "
              "equal desc count)".format(
                  r.get("proxy_count"), args.expect_proxies))
        if stage == "residency_failed":
            print("")
            print("REFUSED: residency could not be established. Either "
                  "the desc query/load errored, the loaded counts do not "
                  "equal the on-disk desc counts, or the proxy count is "
                  "not {0}. A census taken with regions unloaded is not "
                  "a census, and deleting from it would orphan the "
                  "stray's unloaded proxies.".format(args.expect_proxies))
            return 4

        print("")
        print("--- identification (by signature, never label) ---")
        for p in r.get("profiles") or []:
            print("  {0!r}".format(p["label"]))
            print("     scale {0}  -> stray? {1}".format(
                ["{0:.4g}".format(v) for v in p["scale"]],
                p["scale_is_stray"]))
            print("     derived resolution {0}  -> stray? {1}".format(
                p["derived_resolution"], p["resolution_is_stray"]))
            print("     not the keeper? {0}".format(p["not_keeper"]))
        if stage == "identification_failed":
            print("")
            print("REFUSED: {0} candidates matched all three signature "
                  "conditions; exactly one is required.".format(
                      r.get("candidate_count")))
            return 5

        if stage == "keeper_set_incomplete":
            # NOTE (2026-09-18): this branch is currently UNREACHABLE. The same
            # landscape_actor_ref read runs first in _derived_resolution during
            # identification and RAISES on failure, aborting the payload -> the
            # host sees no result and returns 7 (see the exit-code table). Kept
            # (with the intended refusal below) against a future reorder that
            # reads refs lazily; route the identification read here to revive it.
            print("")
            print("REFUSED: the KEEPER PROTECTION SET could not be built "
                  "completely — nothing was deleted.")
            print("landscape_actor_ref could not be read on {0} "
                  "proxy/proxies:".format(
                      len(r.get("keeper_set_unreadable") or [])))
            for u in r.get("keeper_set_unreadable") or []:
                print("  !! {0}".format(u.get("path")))
                print("     {0}".format(u.get("error")))
            print("")
            print("This is NOT 'those proxies belong to nobody'. It is 'I "
                  "could not find out who owns them', and the difference "
                  "matters here: a proxy missing from the protected set "
                  "can still reach the kill list via the attribution pass, "
                  "where its read succeeded. The safety assertion would "
                  "then pass with a KEEPER's proxy queued for deletion.")
            print("Investigate the unreadable proxies before retrying.")
            return 5

        if stage == "assertion_tripped":
            print("")
            print("SAFETY ASSERTION TRIPPED — nothing was deleted.")
            print("The kill list overlapped the keeper or its proxies:")
            for v in r.get("assertion_violations") or []:
                print("  !! {0}".format(v))
            print("This should be impossible. Investigate before retrying.")
            return 8

        if stage == "attribution_incomplete":
            print("")
            print("REFUSED: {0} proxies could not be attributed to either "
                  "landscape:".format(len(r.get("unattributed") or [])))
            for u in r.get("unattributed") or []:
                print("  ?? {0!r}: {1}".format(u.get("label"),
                                               u.get("reason")))
            print("Deleting the stray now could orphan its own proxies. "
                  "Investigate first; nothing was deleted.")
            return 5

        if stage not in ("dry_run", "done", "deletion_incomplete"):
            print("")
            print("FAIL: payload ended in unexpected stage {0!r}. Scene "
                  "state unknown — run scripts/landscape_inventory.py."
                  .format(stage))
            return 7

        print("")
        print("--- kill list ({0} actors) ---".format(r.get("kill_total")))
        print("  STRAY LANDSCAPE  {0!r}".format(r.get("stray_label")))
        for item in r.get("kill_list") or []:
            print("  proxy {0!r}".format(item["label"]))
            print("        {0}".format(item["path"]))
            print("        evidence: {0}".format(item["evidence"]))
        print("")
        print("  spared: {0} proxies (not positively attributed to the "
              "stray)".format(r.get("spared_count")))
        for s in r.get("spared_sample") or []:
            print("     {0!r} -> owner {1}".format(s["label"], s["owner"]))
        print("  keeper(s) untouched: {0}".format(r.get("keeper_labels")))

        if stage == "dry_run":
            print("")
            print("DRY RUN complete — nothing was deleted.")
            return 0

        print("")
        print("--- result ---")
        print("  deleted {0} actors".format(len(r.get("deleted") or [])))
        if r.get("failed"):
            print("  FAILED to delete: {0}".format(r["failed"]))
        print("  landscapes after : {0}".format(r.get("landscapes_after")))
        print("  proxies after    : {0}".format(r.get("proxies_after")))

        if stage == "deletion_incomplete":
            print("")
            print("FAIL: deletion did not complete cleanly. Level NOT "
                  "saved. Run scripts/landscape_inventory.py.")
            return 7
        if not r.get("saved"):
            print("")
            print("FAIL: deleted, but the level did NOT save: {0}".format(
                r.get("save_error", "unknown")))
            print("Save manually (Ctrl+S) before anything else runs.")
            return 7

        print("")
        print("Level saved. Now:")
        print("  git commit the LandscapeLab content (conduct rule 3 — "
              "the after-state)")
        print("Scene changed — pipeline rule 4 applies:")
        print("  python scripts/capture.py")
        print("  then python scripts/verify_landscape.py")
        print("  (a one-line LESSONS.md note is suggested, not required)")
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
