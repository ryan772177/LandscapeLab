"""scratch_tree_scene.py — a flat plane and one of each baked tree, to LOOK at.

WHY THIS EXISTS
---------------
The baked Megaplants conifers cannot be judged from asset thumbnails. On
2026-08-14 a 256x256 unlit thumbnail against a dark checkerboard nearly
produced the report "the baked trees are bare poles" — about a mesh
carrying 331,779 triangles, which a trunk with branches cannot be. The eye
is a poor photometer against a dark background, and canopy density is
exactly the property that trap destroys.

So: real lighting, known exposure, flat neutral ground, one of each variant
side by side, judged from pixels.

WHAT IT DELIBERATELY IS NOT
---------------------------
Not a scatter. Nothing here touches /Game/Alpine8K, no foliage type is
created, no instance is placed, and the level is disposable. The question
"does this canopy read dense" should be answered before 150,000 instances
depend on the answer, not after.

LIGHTING IS NOT DECLARED HERE. `LevelEditorSubsystem.new_level()` makes an
EMPTY partitioned world — no light, no sky, no atmosphere — and this
project has already shipped four pure-black 4K frames from exactly that,
with every tool reporting success. So lighting is a REQUIRED second step:

    python scripts/apply_lighting.py --recipe recipes/alpine_8k.json

pointed at alpine_8k so R13's block stays declared in one place (NN24).
This script REFUSES to pretend it lit anything.

Exit codes:
  0  scene built and saved
  2  editor gate refused (conduct rule 7), bad recipe, or the level exists
     and --replace was not given
  3  the scene was created but a spawn or the save could not be verified
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap             # noqa: E402
import resource_guard        # noqa: E402
import verify_landscape      # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MARKER = "__LANDSCAPELAB_SCRATCH__"
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "tree_scratch.json")

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "error": None, "spawned": [], "level": {level!r}}}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _level = {level!r}

    _exists = _unreal.EditorAssetLibrary.does_asset_exist(_level)
    if _exists and not {replace}:
        _out["error"] = "level already exists; pass --replace to rebuild it"
    else:
        # --replace has to actually REPLACE. new_level() returns False when
        # the asset already exists, so the flag previously only skipped this
        # tool's own refusal and then failed in the engine with a bare
        # "new_level returned False" -- a flag that claimed a capability it
        # did not have. Delete first, and move to an empty map so the level
        # being deleted is not the one open.
        if _exists:
            _les.new_level("/Temp/ScratchSwap")
            _out["deleted_existing"] = bool(
                _unreal.EditorAssetLibrary.delete_asset(_level))
        if not _les.new_level(_level):
            _out["error"] = "new_level returned False"
        else:
            # GROUND. A neutral plane so the silhouette is judged against
            # something, not against the void.
            _g = _unreal.EditorAssetLibrary.load_asset({ground!r})
            if _g is None:
                _out["error"] = "ground mesh not found: " + {ground!r}
            else:
                _ga = _eas.spawn_actor_from_object(
                    _g, _unreal.Vector(0.0, 0.0, 0.0),
                    _unreal.Rotator(0.0, 0.0, 0.0))
                if _ga is not None:
                    _ga.set_actor_scale3d(
                        _unreal.Vector({gscale}, {gscale}, 1.0))
                    _ga.set_actor_label("ScratchGround")
                _out["ground_spawned"] = _ga is not None

                # TREES, one per variant, in a row along +Y.
                _trees = {trees!r}
                _spacing = float({spacing})
                for _i, _p in enumerate(_trees):
                    _m = _unreal.EditorAssetLibrary.load_asset(_p)
                    _row = {{"asset": _p, "spawned": False}}
                    if _m is not None:
                        _loc = _unreal.Vector(0.0, _i * _spacing, 0.0)
                        _a = _eas.spawn_actor_from_object(
                            _m, _loc, _unreal.Rotator(0.0, 0.0, 0.0))
                        if _a is not None:
                            _a.set_actor_label(
                                "Scratch_" + _p.rsplit("/", 1)[-1])
                            _row["spawned"] = True
                            _row["y_cm"] = _i * _spacing
                            try:
                                _b = _a.get_actor_bounds(False)
                                _row["extent_cm"] = [
                                    _b[1].x, _b[1].y, _b[1].z]
                            except Exception:
                                pass
                    else:
                        _row["error"] = "load_asset returned None"
                    _out["spawned"].append(_row)

                _out["saved"] = bool(_les.save_current_level())

                # READ BACK from the world, not from the spawn calls. A
                # spawn that returned an actor and a world that contains it
                # are two different claims.
                _all = _eas.get_all_level_actors()
                _labels = []
                for _a in _all:
                    try:
                        _lbl = _a.get_actor_label()
                    except Exception:
                        continue
                    if _lbl.startswith("Scratch"):
                        _labels.append(_lbl)
                _out["in_world"] = sorted(_labels)
                _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:400]

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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--replace", action="store_true",
                    help="Rebuild the level if it already exists.")
    ap.add_argument("--go", action="store_true",
                    help="Actually build it. Without this it is a dry run.")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)

    try:
        with open(args.recipe, encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as e:
        print("REFUSE: could not read {0}: {1}".format(args.recipe, e))
        return 2

    sc = recipe.get("scratch")
    if not isinstance(sc, dict):
        print("REFUSE: recipe has no `scratch` block")
        return 2
    level = sc.get("level")
    trees = sc.get("trees") or []
    ground = (sc.get("ground") or {}).get("mesh")
    gscale = float((sc.get("ground") or {}).get("scale") or 100.0)
    spacing = float(sc.get("spacing_cm") or 1000.0)

    if not isinstance(level, str) or not level.startswith("/Game/"):
        print("REFUSE: scratch.level must be a /Game/ path")
        return 2
    if not trees:
        print("REFUSE: scratch.trees is empty")
        return 2
    # A scratch scene must not be able to target a real world.
    for guard in ("/Game/Alpine", "/Game/GaeaLab", "/Game/AlpineLab"):
        if level.startswith(guard):
            print("REFUSE: {0} is a real world, not a scratch level. This "
                  "tool creates a NEW level and would replace it."
                  .format(level))
            return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("level     : {0}".format(level))
    print("ground    : {0} at scale {1}".format(ground, gscale))
    print("trees     : {0}, spaced {1:.0f} cm".format(len(trees), spacing))
    for i, t in enumerate(trees):
        print("   y={0:>7.0f} cm  {1}".format(i * spacing, t))
    print("")
    print("LIGHTING IS NOT APPLIED HERE. new_level() makes an EMPTY world "
          "with no light, sky or atmosphere, and this project has already "
          "shipped four pure-black 4K frames from exactly that. Next step:")
    print("   python scripts/apply_lighting.py --recipe recipes/alpine_8k.json")
    if not args.go:
        print("")
        print("DRY RUN. Nothing was created. Re-run with --go.")
        return 0

    free, _total = resource_guard.available_gb()
    print("")
    print("free RAM  : {0:.2f} GB".format(free))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(
            PAYLOAD.format(level=level, trees=trees, ground=ground,
                           gscale=gscale, spacing=spacing,
                           replace=bool(args.replace), marker=MARKER),
            unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
        got = _parse(bootstrap._collect_output(r) if r else "")
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    if got is None:
        print("REFUSE: no parseable result. This is 'I could not look', not "
              "'the scene was not built'.")
        return 3
    if got.get("error"):
        print("REFUSE: {0}".format(got["error"]))
        return 2

    spawned = [s for s in got.get("spawned", []) if s.get("spawned")]
    in_world = got.get("in_world") or []
    print("")
    print("ground spawned : {0}".format(got.get("ground_spawned")))
    print("trees spawned  : {0} of {1}".format(len(spawned), len(trees)))
    for s in got.get("spawned", []):
        nm = s["asset"].rsplit("/", 1)[-1]
        if s.get("spawned"):
            ex = s.get("extent_cm") or []
            print("  {0:<32} y={1:>7.0f} cm  height {2:.2f} m".format(
                nm, s.get("y_cm", 0),
                (2.0 * ex[2] / 100.0) if len(ex) == 3 else float("nan")))
        else:
            print("  {0:<32} FAILED: {1}".format(nm, s.get("error")))
    print("saved          : {0}".format(got.get("saved")))
    print("in world       : {0} actors labelled Scratch*".format(
        len(in_world)))

    # The world read-back is the evidence, not the spawn return values.
    expected = len(trees) + 1
    ok = (len(spawned) == len(trees) and got.get("saved")
          and len(in_world) == expected)
    if not ok:
        print("")
        print("NOT VERIFIED: expected {0} Scratch* actors in the world "
              "(ground + {1} trees), found {2}.".format(
                  expected, len(trees), len(in_world)))
        return 3
    print("")
    print("VERIFIED: every tree is in the saved world, counted by reading "
          "the level back rather than by trusting the spawn calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
