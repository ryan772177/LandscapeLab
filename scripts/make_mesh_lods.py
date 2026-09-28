"""make_mesh_lods.py — build the LOD chain for recipe-named meshes.

WHY THIS EXISTS
`fir_tree_01_c_LOD0` is 505,494 triangles with exactly ONE LOD. At 28,302
instances that is 14.3 billion triangles a frame with culling off, which
is what returned DXGI_ERROR_DEVICE_HUNG, and still 62M a frame with a
300 m cull. The cull distance made the level openable; this is the change
that makes it affordable.

The asset is not bad — it is a photogrammetry delivery being used at
source resolution. A game-ready conifer is ~5k-30k at LOD0 and a few
hundred at distance. The missing step is decimation, not a different
tree.

THE INDEX TRAP, and why this script's input is shaped the way it is.
`FStaticMeshReductionOptions::ReductionSettings[0]` IS LOD 0:

    StaticMeshEditorSubsystem.cpp:401-403
      // Set up LOD 0
      StaticMesh->GetSourceModel(0).ReductionSettings.PercentTriangles =
          ReductionOptions.ReductionSettings[0].PercentTriangles;

So a list of [0.25, 0.06, 0.015] does NOT mean "three LODs below the
source" — it means "decimate the source to 25%, then add two LODs". The
mesh would be permanently damaged and the run would report success.

Therefore THE RECIPE DESCRIBES LOD1..N ONLY and this script prepends
LOD 0 at percent_triangles 1.0 itself. There is no way to express
"decimate LOD 0" in the recipe, which is the point. A gate that refuses
a bad value is good; an input that cannot represent the bad value is
better.

Note also `SetNumSourceModels(1)` at :399 — the existing chain above
LOD 0 is discarded first, so re-running rebuilds rather than appends.
That is what makes this idempotent (hard rule 3).

VERIFICATION IS BY TRIANGLE COUNT, NOT BY LOD COUNT. `get_num_lods()`
returning 4 proves four source models exist, not that any geometry was
reduced — a chain of four identical LODs would pass that check and
change nothing about the frame cost. Each level's ACTUAL triangle count
is read back and compared against the requested percentage, and a level
that did not reduce is a failure.

Exit codes:
  8  another heavy operation holds the lock (scripts/resource_guard.py)
  0  every requested chain built and verified by per-level triangle
     read-back, then saved (screen sizes are read back but NOT compared)
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  remote exec failed, the probe returned nothing, the StaticMeshEditor
     subsystem was unavailable, a chain did not verify, or a save failed
  6  nothing to do — neither lod_targets nor a foliage species declares `lods`
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import resource_guard   # noqa: E402 — RAM check + heavy-op lock
import landscape_spec     # noqa: E402 — shared recipe loading
import verify_landscape   # noqa: E402 — shared node selection
import make_landscape_material  # noqa: E402 — _guard_payload lives here

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")
MARKER = "__LANDSCAPELAB_LODS__"

# A reduced level must land within this fraction of its requested
# triangle count. Generous, because the reducer works on whole triangles
# across four material sections and cannot hit an arbitrary percentage
# exactly; tight enough that "did not reduce at all" cannot pass.
COUNT_TOLERANCE = 0.35


def lod_target_jobs(recipe):
    """[{asset, chain}] for every entry in a top-level `lod_targets` list.

    WHY THIS EXISTS, added 2026-08-14. Building an LOD chain and DECLARING A
    SPECIES are two different acts, and this tool conflated them: its only
    input was `foliage.species`, so anything needing a chain had to pretend
    to be a placement declaration and was then judged by the FOLIAGE
    validator.

    That bit on the Megaplants conifers. They are baked in-engine by
    `bake_skeletal_to_static.py`, so they have no row in the Blender
    normalisation report and `_validate_foliage` refused all eight -- a gate
    that is exactly right about placement (never place a mesh of unknown
    provenance) and irrelevant to decimation. A staging file that gave them
    `weight_share` also over-subscribed the Grass layer to 4.8, a complaint
    about a placement property of something that was never going to be
    placed.

    `lod_targets` says what it means: build a chain on this mesh. It is
    validated NARROWLY -- path shape and chain sanity -- and it is NOT a
    placement declaration, so no consumer can read it as one.
    """
    out = []
    targets = recipe.get("lod_targets")
    if not isinstance(targets, list):
        return out
    for t in targets:
        chain = (t or {}).get("lods")
        mesh = (t or {}).get("mesh")
        if not chain or not isinstance(mesh, str):
            continue
        out.append({
            "name": t.get("name") or mesh.rsplit("/", 1)[-1],
            "asset": mesh,
            "chain": [{"percent": 1.0,
                       "screen_size": float(chain[0].get("screen_size_lod0",
                                                         1.0))}]
                     + [{"percent": float(c["percent_triangles"]),
                         "screen_size": float(c["screen_size"])}
                        for c in chain],
        })
    return out


def validate_lod_targets(recipe):
    """[] or a list of error strings. Narrow on purpose -- see above."""
    targets = recipe.get("lod_targets")
    if targets is None:
        return []
    errs = []
    if not isinstance(targets, list) or not targets:
        return ["lod_targets must be a non-empty list"]
    for i, t in enumerate(targets):
        where = "lod_targets[{0}]".format(i)
        if not isinstance(t, dict):
            errs.append("{0} is not an object".format(where))
            continue
        mesh = t.get("mesh")
        if not isinstance(mesh, str) or not mesh.startswith("/Game/"):
            errs.append("{0}.mesh must be a /Game/ path, got {1!r}"
                        .format(where, mesh))
        chain = t.get("lods")
        if not isinstance(chain, list) or not chain:
            errs.append("{0}.lods must be a non-empty list".format(where))
            continue
        prev_p, prev_s = 1.0, None
        for j, c in enumerate(chain):
            w = "{0}.lods[{1}]".format(where, j)
            try:
                p = float(c["percent_triangles"])
                s = float(c["screen_size"])
            except (KeyError, TypeError, ValueError):
                errs.append("{0} needs numeric percent_triangles and "
                            "screen_size".format(w))
                continue
            # LOD 0 is prepended by this script at 1.0 and can never come
            # from the file -- the index trap in the module docstring. So a
            # declared percent of 1.0 or more is refused rather than
            # silently prepended to, which would decimate the source.
            if not (0.0 < p < 1.0):
                errs.append("{0}.percent_triangles must be in (0, 1); "
                            "got {1}. LOD 0 is prepended by this script at "
                            "1.0 and is not expressible here.".format(w, p))
            elif p >= prev_p:
                errs.append("{0}.percent_triangles {1} does not reduce "
                            "below the previous level's {2}".format(
                                w, p, prev_p))
            if not (0.0 < s < 1.0):
                errs.append("{0}.screen_size must be in (0, 1); got {1}"
                            .format(w, s))
            elif prev_s is not None and s >= prev_s:
                errs.append("{0}.screen_size {1} is not below the previous "
                            "level's {2}".format(w, s, prev_s))
            prev_p, prev_s = p, s
    return errs


def lod_jobs(recipe):
    """[{asset, chain}] for every species declaring `lods`."""
    out = []
    fol = recipe.get("foliage")
    if not isinstance(fol, dict):
        return out
    for sp in fol.get("species") or []:
        chain = (sp or {}).get("lods")
        if not chain:
            continue
        mesh = sp.get("mesh")
        if not isinstance(mesh, str) or not mesh.startswith("/Game/"):
            continue
        out.append({
            "name": sp["name"],
            "asset": mesh,
            # LOD 0 is PREPENDED here, at 1.0, and never comes from the
            # recipe. See the module docstring.
            "chain": [{"percent": 1.0,
                       "screen_size": float(chain[0].get("screen_size_lod0",
                                                         1.0))}]
                     + [{"percent": float(c["percent_triangles"]),
                         "screen_size": float(c["screen_size"])}
                        for c in chain],
        })
    return out


PAYLOAD = '''
import json as _json
import unreal as _unreal

_jobs = _json.loads({jobs!r})
_tol = float({tol})
_out = {{"ok": False, "rows": []}}

_ss = _unreal.get_editor_subsystem(_unreal.StaticMeshEditorSubsystem)
if _ss is None:
    _out["error"] = "StaticMeshEditorSubsystem unavailable"
else:
    for _j in _jobs:
        _row = {{"name": _j["name"], "asset": _j["asset"]}}
        _m = _unreal.EditorAssetLibrary.load_asset(_j["asset"])
        if _m is None:
            _row["error"] = "asset not found"
            _out["rows"].append(_row)
            continue

        _row["before_lods"] = int(_m.get_num_lods())
        _row["before_tris"] = int(_m.get_num_triangles(0))
        _row["before_sections"] = int(_m.get_num_sections(0))

        _settings = []
        for _c in _j["chain"]:
            _s = _unreal.StaticMeshReductionSettings()
            _s.set_editor_property("percent_triangles", _c["percent"])
            _s.set_editor_property("screen_size", _c["screen_size"])
            _settings.append(_s)
        _opts = _unreal.StaticMeshReductionOptions()
        # Explicit screen sizes come from the recipe (hard rule 2), so
        # auto-compute is OFF -- with it on the engine derives its own
        # and the recipe's values are silently ignored.
        _opts.set_editor_property("auto_compute_lod_screen_size", False)
        _opts.set_editor_property("reduction_settings", _settings)

        _n = _ss.set_lods(_m, _opts)
        _row["set_lods_returned"] = int(_n) if _n is not None else None

        # READ BACK PER LEVEL. get_num_lods() proves source models exist,
        # not that anything was reduced; a chain of identical LODs would
        # pass that and change nothing about the frame cost.
        _row["after_lods"] = int(_m.get_num_lods())
        _levels = []
        for _i in range(_row["after_lods"]):
            _levels.append({{
                "lod": _i,
                "tris": int(_m.get_num_triangles(_i)),
                "sections": int(_m.get_num_sections(_i)),
            }})
        _row["levels"] = _levels
        try:
            _row["screen_sizes"] = [round(float(_x), 4) for _x in
                                    _ss.get_lod_screen_sizes(_m)]
        except Exception as _e:
            _row["screen_sizes"] = None
            _row["screen_size_read_error"] = "%s: %s" % (
                type(_e).__name__, _e)

        # Did each level actually reduce to roughly what was asked?
        _base = float(_row["before_tris"])
        _bad = []
        # A zero-triangle base would make every _want 0, every per-level
        # check would `continue`, and the row would verify VACUOUSLY and
        # save. Refuse the degenerate base outright.
        if _row["before_tris"] <= 0:
            _bad.append("LOD 0 reports %d triangles -- refusing to "
                        "evaluate a chain against a degenerate base"
                        % _row["before_tris"])
        if len(_levels) != len(_j["chain"]):
            _bad.append("expected %d levels, got %d"
                        % (len(_j["chain"]), len(_levels)))
        else:
            for _i, _c in enumerate(_j["chain"]):
                _want = _base * _c["percent"]
                _got = float(_levels[_i]["tris"])
                if _want <= 0.0:
                    continue
                _err = abs(_got - _want) / _want
                _levels[_i]["want"] = int(_want)
                _levels[_i]["err"] = round(_err, 4)
                # LOD 0 must be UNTOUCHED, not merely close.
                if _i == 0:
                    if _levels[0]["tris"] != _row["before_tris"]:
                        _bad.append(
                            "LOD 0 changed from %d to %d triangles -- the "
                            "source mesh was decimated"
                            % (_row["before_tris"], _levels[0]["tris"]))
                elif not (_err <= _tol):
                    _bad.append(
                        "LOD %d wanted ~%d triangles, got %d (%.0f%% off)"
                        % (_i, int(_want), _levels[_i]["tris"], _err * 100.0))
                # A level that did not shrink at all is the failure this
                # whole script exists to prevent.
                if _i > 0 and _levels[_i]["tris"] >= _levels[_i - 1]["tris"]:
                    _bad.append(
                        "LOD %d (%d tris) is not smaller than LOD %d (%d)"
                        % (_i, _levels[_i]["tris"], _i - 1,
                           _levels[_i - 1]["tris"]))
                # Material sections must survive, or slots go unbound and
                # the tree renders with holes at distance.
                if _levels[_i]["sections"] != _row["before_sections"]:
                    _bad.append(
                        "LOD %d has %d material sections, LOD 0 had %d"
                        % (_i, _levels[_i]["sections"],
                           _row["before_sections"]))
        _row["problems"] = _bad
        _row["ok"] = not _bad
        if _row["ok"]:
            # READ THE SAVE BACK (rule 12). save_asset returns a bool; a
            # save that fails WITHOUT raising (returns False) was reported
            # saved=True unconditionally, which also made the "NOT SAVED"
            # guard downstream dead. Keep the real bool: the _out["ok"]
            # aggregate (below) already gates on `saved`, so a failed save
            # now surfaces as NOT SAVED -> exit 4, not a false success.
            _row["saved"] = bool(_unreal.EditorAssetLibrary.save_asset(
                _j["asset"], only_if_is_dirty=False))
        _out["rows"].append(_row)

    _out["ok"] = bool(_out["rows"]) and all(
        _r.get("ok") and _r.get("saved") for _r in _out["rows"])

print("{marker}" + _json.dumps(_out))
'''


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[i + len(marker):]
                                                   .lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=25.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    # load_recipe RETURNS (recipe, error); it does not raise. Every
    # sibling script unpacks it — treating it as raising left `recipe`
    # bound to the tuple and crashed lod_jobs (audit 2026-08-02, F1).
    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    # load_recipe PARSES ONLY — the schema validator lives in the
    # importer and nothing has run it on this input. Run the foliage
    # block through it before trusting a single value (audit 2026-08-02,
    # F3; same pattern as place_foliage). Without this, an unvalidated
    # `lods` entry reaches float() and the payload raw.
    # `lod_targets` is validated narrowly and does NOT go through the
    # foliage validator: it is not a placement declaration. See
    # lod_target_jobs for why conflating the two was the defect.
    terrs = validate_lod_targets(recipe)
    if terrs:
        print("REFUSE: lod_targets invalid:")
        for e in terrs:
            print("  - {0}".format(e))
        return 2

    # The FOLIAGE path is unchanged: a species that will be placed is still
    # judged by the full foliage validator, provenance row included. Only
    # run it when the recipe actually declares foliage, so a pure
    # lod_targets file is not refused for lacking a block it does not use.
    if recipe.get("foliage"):
        import import_heightmap as ih  # noqa: E402 — validator owns shape
        errs = ih._validate_foliage(recipe.get("foliage"), recipe)
        if errs:
            print("REFUSE: foliage block invalid:")
            for e in errs:
                print("  - {0}".format(e))
            return 2

    jobs = lod_target_jobs(recipe) + lod_jobs(recipe)
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    if not jobs:
        print("No lod_targets and no foliage species declares `lods`. "
              "Nothing to do.")
        return 6

    for j in jobs:
        print("")
        print("{0}  ->  {1}".format(j["name"], j["asset"]))
        for i, c in enumerate(j["chain"]):
            print("  LOD {0}: {1:>6.1%} of LOD 0   screen size {2}{3}"
                  .format(i, c["percent"], c["screen_size"],
                          "   (prepended, never from the recipe)"
                          if i == 0 else ""))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        print("--- editor identity gate (conduct rule 7) ---")
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Nothing was changed.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))

        source = PAYLOAD.format(jobs=json.dumps(jobs), tol=COUNT_TOLERANCE,
                                marker=MARKER)
        # The transport guard is make_landscape_material's, not
        # verify_landscape's — the original attribute did not exist and
        # would have raised before send (audit 2026-08-02, F2).
        source = make_landscape_material._guard_payload(source)
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(source, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("FAIL: {0}".format((r or {}).get("result")))
            print("Mesh state UNKNOWN: the payload may have mutated the "
                  "mesh in memory before failing. Do NOT save anything "
                  "until this is re-run clean or the editor is restarted.")
            return 4
        res = _parse(bootstrap._collect_output(r))
        if res is None:
            print("FAIL: the payload returned nothing. Mesh state UNKNOWN.")
            return 4
        if res.get("error"):
            print("FAIL: {0}".format(res["error"]))
            return 4

        bad = 0
        for row in res.get("rows") or []:
            print("")
            print("  {0}  ({1})".format(row["name"], row["asset"]))
            if row.get("error"):
                print("    ERROR: {0}".format(row["error"]))
                bad += 1
                continue
            print("    before : {0} LOD(s), {1:,} triangles, {2} sections"
                  .format(row["before_lods"], row["before_tris"],
                          row["before_sections"]))
            for lv in row.get("levels") or []:
                extra = ""
                if lv.get("want") is not None and lv["lod"] > 0:
                    extra = "   wanted ~{0:,}  ({1:.0%} off)".format(
                        lv["want"], lv.get("err", 0.0))
                print("    LOD {0} : {1:>9,} triangles, {2} sections{3}"
                      .format(lv["lod"], lv["tris"], lv["sections"], extra))
            print("    screen sizes : {0}".format(row.get("screen_sizes")))
            base = row["before_tris"]
            tot = sum(lv["tris"] for lv in row.get("levels") or [])
            print("    LOD 0 preserved : {0}".format(
                (row.get("levels") or [{}])[0].get("tris") == base))
            print("    chain total     : {0:,} triangles".format(tot))
            for prob in row.get("problems") or []:
                print("    PROBLEM: {0}".format(prob))
            if not row.get("ok"):
                bad += 1
            elif not row.get("saved"):
                print("    NOT SAVED")
                bad += 1

        print("")
        if bad or not res.get("ok"):
            print("FAIL: {0} mesh(es) did not verify. Nothing was saved for "
                  "those.".format(bad))
            print("HOWEVER: each failed mesh is now DIRTY IN EDITOR MEMORY "
                  "with the rejected chain applied. A save was withheld, "
                  "but saving a level saves EVERY dirty external package — "
                  "an unrelated save would silently persist the failed "
                  "chain. Fix and re-run this script, or restart the "
                  "editor, before anything else saves.")
            return 4
        print("LODs built, verified by per-level triangle count, and saved.")
        print("Hard rule 4: run scripts/capture.py and add a changelog line.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    # RESOURCE GUARD. Heavy operations log the memory situation before
    # they start and hold a lock so two never drive the same editor at
    # once (scripts/resource_guard.py). Low memory WARNS; a concurrent
    # heavy op REFUSES at exit 8.
    try:
        with resource_guard.HeavyOp('static-mesh LOD rebuild') as _guard_ok:
            if not _guard_ok:
                sys.exit(8)
            sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:                        # noqa: BLE001
        print("UNEXPECTED {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
