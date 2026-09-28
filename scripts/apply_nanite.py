"""apply_nanite.py — enable Nanite on recipe-declared meshes, REPLAYABLY.

WHY THIS IS A SCRIPT AND NOT A CLICK
------------------------------------
Every rock in this project is native Fab content living under a
gitignored vendor tree (`git check-ignore`: 17 of 17). `RECIPES.md`'s
Fab-boundary rule 2 names this exact operation as its worked example:

    "AN IN-PLACE MODIFICATION IS NOT A COMMITTABLE DERIVATIVE. Enabling
     Nanite on a Fab static mesh, or changing its LOD or collision, edits
     an ignored file: the asset re-downloads in its original state and
     the change is gone. Express it as a REPLAYABLE STEP in the recipe
     instead."

So the declaration lives in `recipes/<biome>.json` as `nanite: true` on a
palette entry, and this script is the replay. After any vendor
re-download the state is restored by running it again — which is strictly
better than committing bytes, because it is idempotent and survives a
vendor update.

WHAT NANITE ACTUALLY BUYS HERE, MEASURED RATHER THAN ASSUMED
------------------------------------------------------------
Nothing in silhouette. `Free/_measured/palette_live.json` records the
whole palette as already low-poly — largest rock 33,855 triangles, the
long-placed `boulder_medium_01` only 4,136 — and Nanite cannot add detail
an asset never had. The 2026-08-08 ruling withdrew that half of the
argument.

What survives is TEMPORAL: Nanite removes discrete LOD transitions, and
LOD popping across a moving camera is the one defect class no still frame
in this project has ever been able to test. That is the whole case, and
it is why this is worth doing for a 30 s clip and would not be worth
doing for stills.

WHAT IS DELIBERATELY EXCLUDED
-----------------------------
Meshes consumed by the GRASS system (`system: "grass"` species and their
`varieties`) are REFUSED even if declared. Landscape grass instances go
down a different rendering path from instanced static meshes, and whether
it honours Nanite is not established on this install. Those meshes are
2,038-2,572 triangles, so Nanite buys nothing measurable on them anyway —
the cost of being wrong is a broken ground surface and the benefit is
approximately zero, which is an easy call to fail closed on.

Alpha-masked foliage is excluded for the reason `import_static_mesh.py`
already gives: Nanite's masked support exists in 5.8 but costs the fast
path, and the cheap certain configuration is Nanite off with real LODs.

THE READ-BACK IS THE PROOF
--------------------------
`nanite_settings.enabled` is set via `set_nanite_settings(..., apply_changes
=True)`, then read back from the reloaded mesh, and `get_num_nanite_triangles()`
confirms Nanite DATA actually built — a DIFFERENT instrument (non-negotiable
8). The SAVE is proven by its own return: `save_loaded_asset` returns False
WITHOUT raising on a failed write, so a mesh that built in memory but did not
persist is a REFUSAL, not a warning. This project has three recorded editor
mutations that "returned ok and moved nothing".

Exit codes:
  0  every declared mesh reports nanite enabled (or --dry-run listed targets)
  2  editor gate refused, the recipe declares nothing, or every declared mesh
     is barred (all grass-excluded)
  4  a mesh failed to load or was not modifiable, or a memory guard tripped
  5  a mesh was set and did NOT read back enabled, the flag read back enabled
     but Nanite data is empty, or the rebuild did not persist to disk
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import resource_guard     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MARKER = "__LANDSCAPELAB_NANITE__"
FLOOR_GB = 1.0

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None,
        "before": None, "after": None,
        "tris_before": None, "nanite_tris": None, "nanite_verts": None}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _m = _unreal.EditorAssetLibrary.load_asset(_p)
        if _m is None:
            _out["error"] = "load_asset returned None"
        else:
            _ns = _m.get_editor_property("nanite_settings")
            _out["before"] = bool(_ns.get_editor_property("enabled"))
            _out["tris_before"] = int(_m.get_num_triangles(0))
            _ns.set_editor_property("enabled", bool({want!r}))
            # THE RESOLVED API. `StaticMesh.build()` does NOT exist in
            # 5.8 -- it was guessed, and all 8 meshes failed on it
            # (non-negotiable 23). The generated stub at
            # Intermediate/PythonStub/unreal.py:627174 gives the real
            # surface, and apply_changes=True is what rebuilds the mesh.
            _sub = _unreal.get_editor_subsystem(
                _unreal.StaticMeshEditorSubsystem)
            _sub.set_nanite_settings(_m, _ns, True)
            # CAPTURE the save return -- save_loaded_asset returns a bool and
            # can report False WITHOUT raising, so a discarded return can
            # claim a persisted rebuild that never reached disk (rule 12).
            _out["saved"] = bool(
                _unreal.EditorAssetLibrary.save_loaded_asset(_m, False))
            # VERIFY WITH A DIFFERENT INSTRUMENT (non-negotiable 8).
            # Reading back `enabled` only proves the flag we wrote is the
            # flag that is there. get_num_nanite_triangles() asks whether
            # Nanite DATA actually got built, which is the thing we
            # actually want to be true.
            _m2 = _unreal.EditorAssetLibrary.load_asset(_p)
            _ns2 = _m2.get_editor_property("nanite_settings")
            _out["after"] = bool(_ns2.get_editor_property("enabled"))
            _out["nanite_tris"] = int(_m2.get_num_nanite_triangles())
            _out["nanite_verts"] = int(_m2.get_num_nanite_vertices())
            _out["ok"] = True
except Exception as _e:
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


def grass_meshes(recipe):
    """Mesh paths consumed by the GRASS system — excluded, see docstring."""
    out = set()
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(sp, dict) or sp.get("system") != "grass":
            continue
        if isinstance(sp.get("mesh"), str):
            out.add(sp["mesh"])
        for v in sp.get("varieties") or []:
            if isinstance((v or {}).get("mesh"), str):
                out.add(v["mesh"])
    return out


def declared(recipe):
    """[(id, path)] for palette entries carrying `nanite: true`."""
    out = []
    for e in (recipe.get("palette") or {}).get("entries", []):
        if e.get("nanite") is True:
            out.append((e["id"], e["path"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine.json"))
    ap.add_argument("--dry-run", action="store_true",
                    help="list what WOULD be modified and exit")
    args = ap.parse_args(argv)

    with open(args.recipe, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)

    want = declared(recipe)
    if not want:
        print("REFUSE: no palette entry declares `nanite: true`. This "
              "script does not choose targets — the recipe does, so the "
              "replay and the intent cannot drift apart.")
        return 2

    barred = grass_meshes(recipe)
    todo, skipped = [], []
    for pid, path in want:
        (skipped if path in barred else todo).append((pid, path))

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("declared  : {0}".format(len(want)))
    for pid, path in todo:
        print("  ENABLE  {0:<22s} {1}".format(pid, path))
    for pid, path in skipped:
        print("  REFUSED {0:<22s} consumed by the GRASS system; the "
              "landscape grass path is not established to honour Nanite "
              "on this install and these meshes are small enough that it "
              "buys nothing".format(pid))
    if not todo:
        print("")
        print("REFUSE: every declared mesh is barred.")
        return 2
    if args.dry_run:
        print("")
        print("DRY RUN — nothing modified.")
        return 0

    print("")
    print("NOTE: these are gitignored Fab assets. This modification is a "
          "REPLAYABLE STEP (RECIPES.md Fab-boundary rule 2), not a "
          "committable derivative. check_fab_boundary.py WILL report them "
          "as changed, and that is expected and declared.")
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    rc = 0
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2

        for pid, path in todo:
            free, _total = resource_guard.available_gb()
            if free is None:
                print("STOP: could not read available memory. Refusing to "
                      "rebuild another Fab mesh blind on a host that has "
                      "hung once.")
                return 4
            if free < FLOOR_GB:
                print("STOP: {0:.2f} GB free, below the {1:.1f} GB floor."
                      .format(free, FLOOR_GB))
                return 4
            try:
                remote.open_command_connection(node["node_id"])
                r = remote.run_command(
                    PAYLOAD.format(path=path, want=True, marker=MARKER),
                    unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                text = bootstrap._collect_output(r) if r else ""
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass
            row = _parse(text)
            if row is None or not row.get("ok"):
                print("  {0:<22s} FAILED: {1}".format(
                    pid, (row or {}).get("error", "no parseable result")))
                rc = max(rc, 4)
                continue
            if row.get("after") is not True:
                print("  {0:<22s} SET AND DID NOT TAKE — reads {1!r}"
                      .format(pid, row.get("after")))
                rc = max(rc, 5)
                continue
            # The flag is not the evidence. Nanite DATA is.
            ntris = row.get("nanite_tris")
            if not ntris:
                print("  {0:<22s} FLAG SET BUT NANITE DATA IS EMPTY "
                      "({1!r} nanite triangles). The flag being true and "
                      "the data existing are different claims, and only "
                      "the second one renders."
                      .format(pid, ntris))
                rc = max(rc, 5)
                continue
            # The rebuild must reach DISK, not just editor memory (rule 12).
            if row.get("saved") is not True:
                print("  {0:<22s} BUILT BUT NOT SAVED — save_loaded_asset "
                      "returned {1!r}; the rebuild is in editor memory only "
                      "and will not survive a reload or a vendor re-download."
                      .format(pid, row.get("saved")))
                rc = max(rc, 5)
                continue
            print("  {0:<22s} nanite {1} -> {2}   src {3:>6,} tris  "
                  "nanite {4:>8,} tris / {5:>8,} verts   free {6:.1f}GB"
                  .format(pid, row.get("before"), row.get("after"),
                          row.get("tris_before") or 0, ntris,
                          row.get("nanite_verts") or 0, free))
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    print("")
    if rc == 0:
        print("ALL DECLARED MESHES REPORT NANITE ENABLED, read back from "
              "the asset rather than from the struct that was written.")
        print("Re-run this after any vendor re-download; that is what "
              "makes it a replayable step rather than a lost edit.")
    else:
        print("INCOMPLETE (rc={0}). Do not treat the palette as "
              "Nanite-enabled.".format(rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
