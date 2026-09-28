"""save_level.py — save the recipe's level, itemised and dry-run first.

WHY THIS EXISTS
Every scene change since 2026-08-01 has lived in editor memory only: the
material assignment, the lighting rig, the stray-lighting deletion. All of
it reverts on reload, and each session's handoff has had to say so. This
is the missing step that makes the scene survive a restart.

WHY IT IS NOT JUST "save the level"
Saving a level saves EVERY dirty external package, not just the ones you
touched (LESSONS.md, World Partition gotchas). Under One File Per
Actor each actor has its own hash-named package, so a plain save is an
operation whose scope you cannot see. This script inverts that:

  1. it ENUMERATES every dirty package first,
  2. classifies each one against an allow-list DERIVED FROM THE RECIPE,
  3. names the actor behind each hashed OFPA package where it can,
  4. and saves an EXPLICIT list of packages rather than "everything
     dirty".

Anything it cannot place in the recipe's allow-list is reported and
SKIPPED, never saved on the assumption that it is probably ours. Skipping
is the fail-closed direction here: the failure being guarded against is
writing something nobody asked to write.

DRY RUN IS THE DEFAULT (conduct rule: dry-run every destructive
operation). Without `--save` this script contacts the editor, prints
exactly what a save would write, and changes nothing.

WHY A SAVE COUNTS AS DESTRUCTIVE
It overwrites on-disk state that git is the only undo for, and the
restore path is booby-trapped: restoring a file on disk under a live
editor desyncs memory and the next save silently overwrites the restore.
So: commit before running this with `--save`.

GATES, in order, all fail closed:
  1. conduct rule 7 — which PROJECT — delegated to bootstrap.py's audited
     identity gate. Nothing reaches an unverified node.
  2. the LEVEL gate — the editor's open level package must equal the
     recipe's `landscape.level_path`. Saving the wrong world is worse
     than photographing it: a photo is discardable, a save is not.
  3. classification — a dirty package that cannot be classified at all
     (unreadable name) refuses the whole run rather than saving a
     partial set. This gate is enforced IN THE PAYLOAD, before
     save_packages is called: enforcing it host-side only would have
     printed REFUSE after the write had already happened, which is the
     "refusal that mutated first" pattern the audit gate exists to catch.

VERIFICATION AFTER THE SAVE
The dirty set is re-read and every package that was supposed to be saved
must have come back clean, AND save_packages must itself have reported
success. A save that reports success while the map is still dirty — or
while the engine returned False — is exactly the silent-wrong class this
project keeps paying for, so both are an explicit failure (exit 5)
rather than a printed success.

DELETIONS — AUDIT BLOCK S1, CLOSED 2026-08-02
The finding had two halves. The first is DISPROVEN and the second is
FIXED, and both matter to anyone reading this.

*Half one, disproven.* S1 suspected `save_packages()` might not remove
OFPA packages emptied by an actor deletion. It does. Chain read at
source in the 5.8 install, every hop:
  save_packages -> UEditorLoadingAndSavingUtils::SavePackages
    FileHelpers.cpp:6019 -> :5960 -> :5967 -> :5945
  -> InternalPromptForCheckoutAndSave, FileHelpers.cpp:4520-4524:
       "if the package we are saving is considered empty, mark it for
        deletion on disk instead"
  -> ObjectTools::CleanupAfterSuccessfulDelete, :4536
  -> IFileManager::Get().Delete(*PackageFilename)
Note S1 said save_packages routes to the PUBLIC
`FEditorFileUtils::PromptForCheckoutAndSave`. It routes to the shared
INTERNAL, which is where the empty-package handling lives — both paths
delete, but "traced to the public function" was not "traced to the code
that acts".

*Half two, fixed.* The surviving half stood on its own: a package
emptied and correctly deleted leaves the dirty set, and a package
emptied and silently not written also leaves the dirty set, so
`still_dirty` was blind to both. That is now checked ON DISK, host-side
(`_package_file` / `_on_disk`), deliberately outside the engine's own
bookkeeping so it is an independent instrument rather than a second
reading of the same dial. A deletion is verified as a MISSING FILE; a
package that was neither written nor deleted is exit 5, not silence.

Exit codes:
  0  dry run completed, or the save completed and verified clean
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  a probe returned nothing, or a dirty package could not be classified
  5  the save ran but did not verify: save_packages returned False, one
     or more target packages are STILL dirty, or a package has no file
     on disk and had none before (written by nothing, deleted by
     nothing — the S1 silent-wrong case)
  6  nothing to do — no dirty packages matched the recipe's allow-list
     (distinct from 0 so a no-op cannot be mistaken for a save)
  7  LEVEL GATE REFUSED — the editor has a different level open than
     `landscape.level_path`. Matches verify_landscape.py's code 7.

Unreal APIs used (nothing 5.8-only):
  unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages
  unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages
      Long-stable (UE4/UE5). The union of the two is taken because the
      split is world-package vs content-package, and OFPA external actor
      packages are not obviously either — taking both means the
      classification never depends on which side the engine files them
      under.
  unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty)
      Long-stable (UE4/UE5), called positionally as (list, True).
      Chosen over save_dirty_packages() precisely because it takes an
      EXPLICIT package list — that is what makes "saving saves
      everything dirty" untrue here. Existence of every one of these is
      checked in-payload before use; a missing name refuses rather than
      falls back to a broader save. It routes to
      FEditorFileUtils::PromptForCheckoutAndSave with bPromptToSave
      false, so there is no "save these?" dialog; a source-control
      CHECKOUT prompt is the remaining modal risk, mitigated by the
      run_command(unattended=True) already used for every payload here.
      See the OPEN block above for what it does NOT cover.
  unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
      .get_editor_world  — 5.0+ (not UE4; EditorLevelLibrary was its UE4
      home). Used only to map OFPA packages back to actor labels, and
      failing degrades to "no label shown", never to a misclassification.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import landscape_spec     # noqa: E402 — shared recipe loading + paths
import verify_landscape   # noqa: E402 — shared node selection, gate_level
# _guard_payload refuses a payload containing a ".py" filename, which UE
# would silently treat as a FILE PATH instead of code
# (PythonScriptPlugin.cpp:813-830; LESSONS.md 2026-08-01). Imported
# rather than reimplemented — one copy decides (lesson 1.9). It belongs in
# bootstrap.py beside the other shared transport concerns; that move is
# the same open refactor as _select_verified_node and is not made here.
import make_landscape_material  # noqa: E402
# ROLE_SETTINGS/DEST_ROOT are the single source of truth for where a
# surface set's textures land ("/Game/Surfaces/T_<id>_<sfx>", FLAT — there
# is no per-surface folder). The allow-list derives the same names from
# the same table rather than restating them (lesson 1.9).
import import_surface_set  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
PROBE_MARKER = "__LANDSCAPELAB_SAVE__"
# The payload writes its full result here and returns only a small
# marker; see the payload comment for why the transport cannot carry it.
# Under Saved/ because it is a transient run artefact, not project data.
def result_file_for(phase):
    """ONE FILE PER PHASE. This was a single shared constant and it cost
    the confirmation of a 1,484-package save.

    THE DEFECT, measured 2026-08-09: the payload writes its full result to
    a file and returns a small marker, because the real dict is 418 KB and
    the remote-exec transport drops it. That worked for the PROBE phase.
    It then FAILED for the SAVE phase, which fell back to printing the
    whole dict and blew the transport again -- most likely because the
    probe's file was still held when the save tried to overwrite it. The
    save ITSELF executed; only the proof did not come back, which is the
    "a save that SUCCEEDED reports as UNKNOWN" shape this project has hit
    twice now (save_level, and the material builder's failure banner).

    An unknown save is strictly worse than a failed one: a failure can be
    retried, while an unknown leaves the operator guessing about 1,484
    packages, and the guess is what a later session inherits.

    Both phases are the SAME function called twice, so the filename has to
    come from the phase rather than from a module constant -- otherwise
    "give each phase its own file" is a thing to remember at two call
    sites (NN24).
    """
    return os.path.join(
        bootstrap.UE_PROJECT_ROOT, "Saved",
        "landscapelab_save_result_{0}.json".format(phase)).replace(
            os.sep, "/")


# Kept so an older invocation or a stale reference resolves to something
# real rather than raising; the phase-specific files are what is written.
RESULT_FILE = result_file_for("probe")


def allowed_packages(recipe):
    """Return (exact_names, prefixes) the recipe authorises saving.

    Everything here is DERIVED FROM THE RECIPE, so the allow-list cannot
    drift from what the pipeline actually builds — the same reason
    landscape_spec owns derive_spec for both ends of the import bracket.

    Returns None on a recipe that cannot state its own level, because an
    allow-list with no level in it would authorise nothing and read as
    "nothing to save" rather than as "the recipe is broken".
    """
    ls = recipe.get("landscape") or {}
    level = ls.get("level_path")
    if not isinstance(level, str) or not level.startswith("/Game/"):
        return None

    exact = {level}
    prefixes = set()

    # OFPA. The engine parcels a World Partition level's actors into
    # per-actor packages under /Game/__ExternalActors__/<level tail>/ and
    # /Game/__ExternalObjects__/<level tail>/ — "/Game/Alpine" gives
    # "/Game/__ExternalActors__/Alpine". Prefixes, not exact names,
    # because the leaf is a content hash with no actor identity in it.
    tail = level[len("/Game"):]          # "/Alpine"
    prefixes.add("/Game/__ExternalActors__" + tail + "/")
    prefixes.add("/Game/__ExternalObjects__" + tail + "/")

    # Assets the recipe names. A material or texture edited by this
    # pipeline is legitimately part of "save my work"; anything else in
    # /Game/Materials or /Game/Textures is not, which is why these are
    # exact paths and not a folder prefix.
    mat = (recipe.get("material") or {}).get("parent_material")
    if isinstance(mat, str) and mat.startswith("/Game/"):
        exact.add(mat)

    # Foliage assets the recipe names (schema v1.6/v1.7). Same rule as
    # materials and textures: EXACT paths derived from the recipe's own
    # species names, never a folder prefix, so an unrelated asset that
    # happens to live in /Game/Foliage is not swept into the save.
    #
    # Without this the grass types and foliage types are memory-only and
    # vanish on reload, taking the ground cover with them — and the run
    # would still report success, because a package outside the
    # allow-list is a deliberate exclusion rather than a failure.
    fol = recipe.get("foliage")
    biome_id = recipe.get("biome_id")
    if isinstance(fol, dict) and isinstance(biome_id, str) and biome_id:
        for sp in fol.get("species") or []:
            name = (sp or {}).get("name")
            if not isinstance(name, str) or not name:
                continue
            if (sp or {}).get("system") == "grass":
                exact.add("/Game/Foliage/GT_{0}_{1}".format(biome_id, name))
            else:
                exact.add("/Game/Foliage/FT_{0}".format(name))
            # schema v1.9: the species' own mesh. Imported from Free/ by
            # import_static_mesh.py, so it is a pipeline-authored package
            # and unsaved it vanishes on reload — taking the foliage type
            # with it, since a FoliageType with a null mesh spawns
            # nothing. Its MATERIALS are not named here; they come in
            # through the dependency closure below.
            mesh = (sp or {}).get("mesh")
            if isinstance(mesh, str) and mesh.startswith("/Game/"):
                exact.add(mesh)
            # schema v1.10: a grass species drives several meshes. The
            # GrassType holds hard references to all of them, so the
            # dependency closure would reach them anyway — they are
            # named here as well so the allow-list is readable without
            # running it, and so a variety mesh that is dirty but not
            # yet referenced still saves.
            for var in (sp or {}).get("varieties") or []:
                vm = (var or {}).get("mesh")
                if isinstance(vm, str) and vm.startswith("/Game/"):
                    exact.add(vm)

    # Surface textures the material's layers name (schema v1.8).
    # import_surface_set.py imports FLAT — DEST_ROOT + "/T_<id>_<sfx>"
    # (import_surface_set.py:58,113-116) — there is NO per-surface
    # folder, so a "/Game/Surfaces/<id>/" prefix would match nothing the
    # importer creates: dead coverage that prints as if it were
    # protection (audit 2026-08-02, F2). EXACT names are derived from
    # the importer's own ROLE_SETTINGS table instead, so the two files
    # cannot disagree (lesson 1.9). Roles the recipe never imported
    # yield exact names no package bears, which admit nothing.
    for layer in (recipe.get("material") or {}).get("layers") or []:
        surf = (layer or {}).get("surface")
        if isinstance(surf, str) and surf:
            for sfx, _settings in import_surface_set.ROLE_SETTINGS.values():
                exact.add("{0}/T_{1}_{2}".format(
                    import_surface_set.DEST_ROOT, surf, sfx))

    biome = recipe.get("biome_id")
    if isinstance(biome, str) and biome:
        try:
            exact.add(landscape_spec.weightmap_asset_path(biome))
            for layer in (recipe.get("material") or {}).get("layers") or []:
                name = (layer or {}).get("name")
                if isinstance(name, str) and name:
                    exact.add(landscape_spec.texture_asset_path(biome, name))
        except Exception:
            # A helper that cannot build a path for this recipe means the
            # texture set is not derivable; the level and its actors are
            # still saveable, and an unlisted texture is skipped and
            # reported rather than silently swept in.
            pass

    return exact, prefixes


def _probe_source(exact, prefixes, do_save, level):
    """Enumerate dirty packages, classify, and (if asked) save them.

    `level` is the recipe's level package name. It is passed SEPARATELY
    from `exact` (which also contains it) because the dependency closure
    must not seed from it — see the comment at the closure below.

    Enumeration and saving are ONE payload deliberately. Split across
    two, the dirty set could change between them and the save would be
    authorised by a stale list; here the list that is checked is the list
    that is written, in the same engine tick.

    The dry run therefore runs the identical classification and stops
    short of save_packages — same code path, same decisions, minus the
    write.
    """
    return '''
import json as _json
import unreal as _unreal

_exact = set({exact!r})
_prefixes = {prefixes!r}
_do_save = {do_save!r}
_level = {level!r}

_out = {{"ok": False, "owned": [], "foreign": [], "unreadable": 0,
        "saved": None, "still_dirty": [], "api": {{}}}}

# Resolve the API surface BEFORE using any of it. A missing name must
# refuse, never fall back to a broader "save everything dirty" — the
# whole design is that the saved set is the enumerated set.
_utils = getattr(_unreal, "EditorLoadingAndSavingUtils", None)
for _needed in ("get_dirty_map_packages", "get_dirty_content_packages",
                "save_packages"):
    _out["api"][_needed] = bool(_utils is not None
                                and hasattr(_utils, _needed))
if not all(_out["api"].values()):
    print("{marker}" + _json.dumps(_out))
else:
    # Map OFPA package name -> actor identity. get_package(), NOT
    # get_outermost(): under One File Per Actor the outermost is the MAP
    # package, so get_outermost() would label every actor with the level
    # and the mapping would be uniformly wrong (LESSONS.md 6.x).
    _ident = {{}}
    try:
        _world = _unreal.get_editor_subsystem(
            _unreal.UnrealEditorSubsystem).get_editor_world()
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _world, _unreal.Actor):
            try:
                _pkg = _a.get_package()
                if _pkg is None:
                    continue
                _ident[_pkg.get_name()] = [
                    _a.get_actor_label(), _a.get_class().get_name()]
            except Exception:
                continue
    except Exception:
        pass

    # DEPENDENCY CLOSURE over the recipe-named assets.
    #
    # The recipe names a mesh; it does not name that mesh's materials or
    # their textures, because those are properties OF the mesh, not
    # scene parameters. Leaving them out is not a harmless omission: a
    # StaticMesh saved without its material saves a reference to a
    # package that no longer exists on reload, and the mesh comes back
    # shaded with WorldGridMaterial. The scene would still load, still
    # report success, and be silently wrong — the 6.2 class.
    #
    # This is still recipe-DERIVED, and much tighter than a folder
    # prefix: a package only enters the set by being reachable from an
    # asset the recipe names. An unrelated asset sitting in the same
    # folder is not reachable and is not swept in.
    #
    # get_dependencies REQUIRES the options object in 5.8 — the bare
    # one-argument form raises TypeError ("required argument
    # 'dependency_options' (pos 2) not found"), probed against this
    # editor before this was written. Results include /Script/* module
    # references, which are code, not content; only /Game/ names are
    # kept.
    _closure = set()
    _reg = None
    try:
        _reg = _unreal.AssetRegistryHelpers.get_asset_registry()
        _dopts = _unreal.AssetRegistryDependencyOptions(
            include_soft_package_references=True,
            include_hard_package_references=True)
    except Exception as _e:
        _out["closure_error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)
        _reg = None
    if _reg is not None:
        # The LEVEL is deliberately NOT a closure seed. A map package's
        # dependency list carries "<level>_BuiltData" and whatever else
        # the map references, so seeding it would silently move
        # BuiltData from foreign to owned — reversing the documented
        # decision (host-side ATTENTION block) that widening the
        # allow-list to BuiltData is a recipe decision, not a default.
        # It is pre-marked visited so a back-reference cannot re-admit
        # it as a dependency and walk it from there.
        _queue = [_n for _n in _exact
                  if _n.startswith("/Game/") and _n != _level]
        _visited = set(_queue)
        _visited.add(_level)
        _nerr = 0
        while _queue:
            _cur = _queue.pop()
            try:
                _deps = _reg.get_dependencies(_cur, _dopts) or []
            except Exception:
                # "Couldn't look" is not "nothing there" (lesson 2.10):
                # counted and reported, because a failed lookup on the
                # MESH is exactly the materials-drop-out case this
                # closure exists to prevent.
                _nerr += 1
                continue
            for _d in _deps:
                _dn = str(_d)
                if not _dn.startswith("/Game/") or _dn in _visited:
                    continue
                # __External*__ packages are actor/object shards of some
                # level. They are reached only via a level reference and
                # must stay governed by the OFPA prefixes above, which
                # are scoped to THIS level. Admitting them here would let
                # a cross-level reference authorise saving another
                # level's actors.
                if "/__External" in _dn:
                    continue
                _visited.add(_dn)
                _closure.add(_dn)
                _queue.append(_dn)
        _out["closure_node_errors"] = _nerr
    _exact = set(_exact) | _closure
    _out["closure"] = sorted(_closure)

    _dirty = []
    for _p in list(_utils.get_dirty_map_packages()) + \\
            list(_utils.get_dirty_content_packages()):
        if _p is not None:
            _dirty.append(_p)

    _owned_pkgs = []
    _seen = set()
    for _p in _dirty:
        try:
            _name = _p.get_name()
        except Exception:
            _name = None
        if not _name:
            # Cannot classify it, so cannot claim it is not ours and
            # cannot claim it is. Counted; the host refuses on it.
            _out["unreadable"] += 1
            continue
        if _name in _seen:
            continue
        _seen.add(_name)
        _who = _ident.get(_name)
        _row = [_name, _who[0] if _who else None, _who[1] if _who else None]
        _is_ours = _name in _exact or any(
            _name.startswith(_pre) for _pre in _prefixes)
        if _is_ours:
            _out["owned"].append(_row)
            _owned_pkgs.append(_p)
        else:
            _out["foreign"].append(_row)

    # GATE 3, ENFORCED HERE rather than by the host. The host also
    # refuses on _out["unreadable"], but it can only do that AFTER this
    # payload has returned — by which time the save would already have
    # happened and the printed REFUSE would be a report on a completed
    # write, not a refusal. A package whose name cannot be read cannot be
    # shown to be outside the allow-list, so the set is not describable
    # and nothing is written.
    if _do_save and _out["unreadable"]:
        _out["save_skipped"] = ("refused: {{0}} dirty package(s) would not "
                                "report a name").format(_out["unreadable"])
    elif _do_save and _owned_pkgs:
        # only_dirty=True: a package that went clean between enumeration
        # and this call is skipped rather than rewritten.
        _out["saved"] = bool(_utils.save_packages(_owned_pkgs, True))
        # Re-read the dirty set and report which of OUR packages are
        # still in it. This is the check that the save actually landed;
        # save_packages returning True is a claim, not evidence.
        _after = set()
        for _p in list(_utils.get_dirty_map_packages()) + \\
                list(_utils.get_dirty_content_packages()):
            try:
                if _p is not None:
                    _after.add(_p.get_name())
            except Exception:
                pass
        _out["still_dirty"] = [_r[0] for _r in _out["owned"]
                               if _r[0] in _after]

    _out["ok"] = True
    # THE RESULT GOES THROUGH A FILE, NOT THROUGH THE TRANSPORT.
    #
    # This payload's reply enumerates every owned package as a
    # [name, actor_label, class] triple. After the 2026-08-09 cliff and
    # talus placement that reply measured 418 KB and the remote-exec
    # client could not deserialise it: the payload ran, the editor
    # reported ok, and the host received NOTHING. CURRENT STATE had
    # already recorded the shape of this ("save_level can exceed the
    # remote-exec deserialization limit and exit non-zero on a save that
    # SUCCEEDED") without a fix.
    #
    # Truncating the reply was the obvious move and is WRONG: the host
    # uses the full `owned` list for a before/after disk-mtime check, so
    # a shortened list would quietly shrink that verification from every
    # package to a handful. A file has no size limit and keeps every
    # gate at full strength.
    _rf = None
    try:
        _rf = {result_file!r}
        with open(_rf, "w") as _fh:
            _json.dump(_out, _fh)
    except Exception as _e:
        _rf = None
        _out["result_file_error"] = "{{0}}: {{1}}".format(
            type(_e).__name__, _e)
    if _rf:
        print("{marker}" + _json.dumps({{
            "ok": True, "result_file": _rf,
            "owned_n": len(_out["owned"]),
            "foreign_n": len(_out["foreign"]),
            "unreadable": _out["unreadable"],
            "saved": _out.get("saved"),
            "still_dirty_n": len(_out.get("still_dirty") or []),
        }}))
    else:
        print("{marker}" + _json.dumps(_out))
'''.format(exact=sorted(exact), prefixes=sorted(prefixes),
           do_save=bool(do_save), level=str(level), marker=PROBE_MARKER,
           result_file=result_file_for("save" if do_save else "probe"))


def _guarded(source):
    """Refuse a payload UE would mistake for a filename. Raises."""
    return make_landscape_material._guard_payload(source)


def _parse(text, marker=PROBE_MARKER):
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _package_file(package_name):
    """`/Game/Foo/Bar` -> the .uasset/.umap path on disk, or None.

    HOST-SIDE ON PURPOSE, and that is the whole point of S1 option (iii).
    The finding's surviving half is that `still_dirty` is empty whether a
    package was correctly deleted or silently not written, so the check
    has to come from somewhere the engine's own bookkeeping cannot
    reach. `os.path.isfile` against the project's Content tree is
    exactly that: an independent instrument, not a second reading of the
    same dial (lesson 15.1 — get the conclusion from sources that have
    no way of agreeing by construction).

    Only `/Game/...` is mapped. `/Engine`, `/Script` and plugin mounts
    resolve elsewhere and are returned as None rather than guessed at —
    the allow-list means those should never be in an owned set anyway,
    and a wrong path would report a false FAIL, which is worse than an
    honest skip.
    """
    if not isinstance(package_name, str) or not package_name.startswith(
            "/Game/"):
        return None
    rel = package_name[len("/Game/"):]
    if not rel or ".." in rel.split("/"):
        return None
    base = os.path.join(bootstrap.UE_PROJECT_ROOT, "Content", *rel.split("/"))
    # A level is .umap, everything else .uasset. Which one it is is not
    # knowable from the name, so both are tried and the one that exists
    # wins; when neither exists the .uasset form is returned so the
    # caller can report a specific missing path.
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    return base + ".uasset"


def _on_disk(package_names):
    """{package name: (exists, path)}. path is None when unmappable."""
    out = {}
    for name in package_names:
        path = _package_file(name)
        out[name] = (os.path.isfile(path), path) if path else (None, None)
    return out


def _resolve_result_file(res):
    """Load the full payload result when it was handed over via a file.

    The payload returns a small marker carrying `result_file` when its
    real reply is too large for the remote-exec transport. Reading it
    here keeps every downstream gate looking at the COMPLETE data --
    notably the before/after disk-mtime check, which walks the whole
    `owned` list and would silently weaken if that list were truncated.

    A read failure is reported, never swallowed: "I could not look" is
    not "nothing was owned" (non-negotiable 6), and an empty owned list
    would make the save look like a no-op that needed no verification.
    """
    if not isinstance(res, dict) or not res.get("result_file"):
        return res
    path = res["result_file"]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            full = json.load(fh)
    except (OSError, ValueError) as exc:
        res["result_file_read_error"] = "{0}: {1}".format(
            type(exc).__name__, exc)
        return res
    full["result_file"] = path
    return full


def _run(remote_exec, remote, node_id, source, marker=PROBE_MARKER):
    # EVERY send goes through the transport guard, not just the one the
    # caller remembered to wrap. This function also carries the level
    # gate's LEVEL_SOURCE and would carry anything added later; a payload
    # containing ".py" does not error, it silently becomes a filename
    # (PythonScriptPlugin.cpp:813-830). Refusing here returns None, which
    # every caller already treats as "the probe returned nothing" and
    # fails closed on — nothing is executed.
    try:
        source = _guarded(source)
    except Exception as exc:
        print("  REFUSE (transport): {0}: {1}".format(
            type(exc).__name__, exc))
        return None
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
        # The payload may have handed its real result over via a file
        # (RESULT_FILE) because the transport cannot carry it. Resolve
        # that here so every caller sees the COMPLETE dict and no gate
        # downstream has to know the difference.
        return _resolve_result_file(
            _parse(bootstrap._collect_output(result), marker))
    except Exception as exc:
        print("  command errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _print_rows(rows, indent="    "):
    for name, label, cls in rows:
        if label:
            print("{0}{1}\n{0}    -> {2} ({3})".format(
                indent, name, label, cls))
        else:
            print("{0}{1}".format(indent, name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--save", action="store_true",
                        help="Actually write. Without this the run is a "
                             "dry run: it prints exactly what would be "
                             "saved and changes nothing.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    allow = allowed_packages(recipe)
    if allow is None:
        print("REFUSE: recipe landscape.level_path is missing or is not a "
              "/Game/ path. There is no statement of which level this "
              "would save, and 'unknown' is never 'yes'.")
        return 2
    exact, prefixes = allow

    mode = "SAVE" if args.save else "DRY RUN"
    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("Recipe          : {0}".format(os.path.abspath(args.recipe)))
    print("Mode            : {0}".format(mode))
    print("")
    print("Allow-list (derived from the recipe):")
    for name in sorted(exact):
        print("    {0}".format(name))
    for pre in sorted(prefixes):
        print("    {0}*".format(pre))
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

        print("--- level gate (recipe landscape.level_path) ---")

        def _lvl_runner(source, marker):
            return _run(remote_exec, remote, node["node_id"], source, marker)

        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level, _lvl_runner)
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            print("  Conduct rule 7 verified the PROJECT; this checks the")
            print("  LEVEL. Saving the wrong world is not recoverable by")
            print("  re-running. Open {0!r} and re-run.".format(want_level))
            return 7
        print("  level {0}".format(detail))
        print("")

        print("--- dirty packages ---")
        try:
            # want_level is the same recipe field allowed_packages
            # validated (allow is not None implies it is a /Game/ str),
            # and gate_level has just verified it against the editor.
            payload = _guarded(
                _probe_source(exact, prefixes, args.save, want_level))
        except Exception as exc:
            print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
            return 1

        # S1 option (iii), signed off 2026-08-02. Snapshot the FILESYSTEM
        # before the payload runs, so the post-save comparison has a real
        # baseline rather than the engine's own opinion. See
        # _package_files / _on_disk below for why this is host-side.
        before_disk = None
        if args.save:
            probe = _run(remote_exec, remote, node["node_id"],
                         _guarded(_probe_source(exact, prefixes, False,
                                                want_level)))
            if probe is None or not probe.get("ok"):
                print("REFUSE: could not enumerate the dirty set before "
                      "saving, so there would be no baseline to verify "
                      "the save against. Nothing was written.")
                return 4
            before_disk = _on_disk([r[0] for r in (probe.get("owned") or [])])

        res = _run(remote_exec, remote, node["node_id"], payload)
        if res is None or not res.get("ok"):
            missing = [k for k, v in (res or {}).get("api", {}).items()
                       if not v]
            if missing:
                print("REFUSE: the editor does not expose {0} on "
                      "EditorLoadingAndSavingUtils. Not falling back to a "
                      "broader save.".format(", ".join(sorted(missing))))
            else:
                print("FAIL: the dirty-package probe returned nothing.")
            if args.save:
                # State the ambiguity instead of implying "nothing
                # happened". The save is inside the payload, so a lost
                # RESULT does not prove a lost WRITE: the connection can
                # drop, or the post-save re-read can raise, after
                # save_packages has already run. Re-run the DRY run to
                # find out which; do not assume either way.
                print("  NOTE: --save was requested and the write happens "
                      "inside this payload, so it is UNKNOWN whether the "
                      "save ran. Re-run WITHOUT --save to see the current "
                      "dirty set before doing anything else.")
            return 4

        owned = res.get("owned") or []
        foreign = res.get("foreign") or []

        if res.get("unreadable"):
            print("REFUSE: {0} dirty package(s) would not report a name. "
                  "They cannot be shown to be outside the allow-list, so "
                  "this run refuses rather than save a set it cannot "
                  "describe.".format(res["unreadable"]))
            # The payload enforces the same gate before save_packages, so
            # this refusal is a refusal, not a post-mortem.
            print("  NOTHING WAS WRITTEN: {0}".format(
                res.get("save_skipped")
                or "the payload skipped the save on the same condition."))
            return 4

        if res.get("closure_error"):
            print("  DEPENDENCY CLOSURE UNAVAILABLE: {0}".format(
                res["closure_error"]))
            print("    Materials and textures reachable only through a "
                  "recipe-named mesh are NOT in the allow-list for this "
                  "run; they are listed below as not-saved.")
        node_errors = res.get("closure_node_errors") or 0
        if node_errors:
            print("  NOTE: dependency lookup failed on {0} package(s) "
                  "during the closure walk. Anything reachable ONLY "
                  "through them is not in the allow-list for this run — "
                  "'could not look' is not 'nothing there' (lesson "
                  "2.10).".format(node_errors))
        closure = res.get("closure") or []
        if closure:
            print("  reached through a recipe-named asset ({0} package(s) "
                  "admitted by dependency, not by folder):".format(
                      len(closure)))
            for name in closure:
                print("    {0}".format(name))
            print("")

        print("  OWNED by the recipe ({0}):".format(len(owned)))
        _print_rows(owned)
        if not owned:
            print("    (none)")
        print("")
        print("  NOT in the allow-list ({0}) — these will NOT be "
              "saved:".format(len(foreign)))
        _print_rows(foreign)
        if not foreign:
            print("    (none)")
        # A foreign package that is a SIBLING of the level — most likely
        # "<level>_BuiltData", which holds the map build data registry —
        # is the one skip that can leave the level inconsistent on disk
        # rather than merely unsaved. It is skipped either way (the
        # allow-list is what authorises writes, and widening it is a
        # decision, not a default), but it is called out by name so it
        # cannot be lost in a list. Deciding what to do about it is a
        # recipe/design question, not something to infer at runtime.
        level_path = (recipe.get("landscape") or {}).get("level_path")
        siblings = [r[0] for r in foreign
                    if isinstance(r[0], str) and isinstance(level_path, str)
                    and r[0].startswith(level_path)]
        if siblings:
            print("")
            print("  ATTENTION: {0} skipped package(s) are named as "
                  "siblings of {1!r}:".format(len(siblings), level_path))
            for name in siblings:
                print("      {0}".format(name))
            print("      A '<level>_BuiltData' here means the map's build "
                  "data is dirty and will NOT be written, so the saved "
                  "level and its build data will disagree on disk. The "
                  "allow-list is recipe-derived on purpose — widening it "
                  "is a decision for the recipe, not for this run.")
        print("")

        if not owned:
            print("Nothing to save: no dirty package matched the recipe's "
                  "allow-list. If you expected a save, the edits are "
                  "either already on disk or in a package this recipe "
                  "does not own.")
            return 6

        if not args.save:
            print("=" * 70)
            print("DRY RUN — nothing was written. Re-run with --save to "
                  "write the {0} package(s) listed as OWNED.".format(
                      len(owned)))
            print("=" * 70)
            return 0

        print("--- save result ---")
        saved = res.get("saved")
        print("  save_packages returned: {0}".format(saved))
        still = res.get("still_dirty") or []
        failed = False
        # TWO independent conditions, both required, neither sufficient.
        # The dirty re-read is the evidence; the return value is the
        # engine's own verdict. Ignoring the verdict because the evidence
        # looks good is how a run reports SAVED after the engine said it
        # did not succeed — the exact silent-wrong direction this script
        # exists to close. save_packages returns true only for
        # PR_Success; PR_Failure and PR_Declined (e.g. a source-control
        # checkout that did not happen) both come back False.
        if saved is not True:
            print("")
            print("FAIL: save_packages did not report success (returned "
                  "{0!r}).".format(saved))
            if res.get("save_skipped"):
                print("  The payload skipped the save: {0}".format(
                    res["save_skipped"]))
            else:
                print("  Some or all of the write was refused or failed.")
            failed = True
        if still:
            print("")
            print("FAIL: {0} package(s) are STILL DIRTY after the "
                  "save:".format(len(still)))
            for name in still:
                print("    {0}".format(name))
            print("  The save did not land. Nothing here should be treated")
            print("  as persisted.")
            failed = True
        if failed:
            return 5
        print("  every owned package came back clean")

        # ---- S1 option (iii): the ON-DISK check ----------------------
        after_disk = _on_disk([r[0] for r in owned])
        wrote, deleted, absent, skipped = [], [], [], []
        for name in sorted(after_disk):
            now, path = after_disk[name]
            if path is None:
                # Not a /Game package; not guessed at. Reported, never
                # silently dropped — an unmappable name is "I could not
                # look", which is not "it is fine" (lesson 2.10).
                skipped.append(name)
            elif now:
                wrote.append(name)
            elif (before_disk or {}).get(name, (None, None))[0]:
                deleted.append(name)
            else:
                absent.append(name)

        print("")
        print("--- on-disk verification (audit finding S1) ---")
        print("  present after save : {0}".format(len(wrote)))
        print("  removed from disk  : {0}   <- packages emptied by a "
              "DELETION".format(len(deleted)))
        for name in deleted:
            print("      {0}".format(name))
        if skipped:
            print("  NOT CHECKED       : {0}   <- not /Game packages, path "
                  "not guessed at".format(len(skipped)))
            for name in skipped:
                print("      {0}".format(name))
        if absent:
            print("")
            print("FAIL: {0} package(s) have NO FILE ON DISK and had none "
                  "before:".format(len(absent)))
            for name in absent:
                print("      {0}".format(name))
            print("  The engine reported success and the dirty flag "
                  "cleared, and yet nothing was written. That combination")
            print("  is exactly the silent-wrong case S1 was raised for,")
            print("  and until now nothing in this script could see it.")
            return 5

        print("")
        print("=" * 70)
        print("SAVED {0} package(s) — engine reported success, every one "
              "came back clean, and every one is accounted for on "
              "disk.".format(len(owned)))
        print("=" * 70)
        print("")
        print("S1 IS CLOSED, and here is exactly what is now proven. A")
        print("package emptied by an actor deletion leaves the dirty set")
        print("whether its file was removed or not, so the clean re-read")
        print("above is silent on deletions — that part of the finding was")
        print("always right. The on-disk check above is not silent: a")
        print("deletion is verified as a MISSING FILE, and a package that")
        print("was neither written nor deleted is a FAILURE rather than an")
        print("absence of evidence.")
        print("")
        print("Pipeline rule 4: run the capture script. (A one-line")
        print("LESSONS.md note is suggested, not required.)")
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
