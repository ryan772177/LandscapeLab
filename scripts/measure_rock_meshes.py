"""measure_rock_meshes.py — pivot + Nanite + LOD for palette rocks, one at a time.

Writes `Free/_measured/rock_pivots.json`, which `rock_scatter.py` refuses
to plan without.

THREE MEASUREMENTS, ONE LOAD
----------------------------
Loading a Fab mesh is the expensive act: it pulls the mesh's materials and
their textures, and on this host a single KiteDemo asset once wanted a
4608 MB texture encode and hung the editor for over twenty minutes. So
every question that needs the asset loaded is asked on the SAME load:

  pivot   `get_bounds()` origin/extent -> horizontal offset and base Z.
          The rocks are native Fab `.uasset`s that never went through
          Blender and never can (R-ASSET forbids authoring into a Fab
          folder), so their pivots are whatever the vendor set. This
          project has not measured them; `ApproxSize` in the registry is
          a bounding-box SIZE, not an origin.
  nanite  the reflected `nanite_settings`. ABSENT IS NOT OFF: UE 5.8's
          `UStaticMesh::GetAssetRegistryTags` writes `NaniteEnabled` as an
          explicit "True"/"False" (StaticMesh.cpp:6225), so a registry row
          WITHOUT the tag was cached by an engine that predates it. That
          is "I could not look", not "it is off" (non-negotiable 6), and
          it is why all 940 meshes came back blank.
  lods    the LOD count. The scatter's cost model assumes a generated
          chain; no Fab rock has a verified one, so until this is measured
          a rock costs its LOD0 triangles at every distance inside its
          cull disc.

LOAD DISCIPLINE
---------------
One asset per remote call. `resource_guard` before each. STOPS on the
first load that leaves less than the floor free, rather than pushing on —
standing rule 6 says diagnose, do not brute-force against a live editor.

The two HAZARD palette entries (GroundRevealRock001/002) are EXCLUDED by
name, not merely skipped: their 8192x8192 texture is the one that hung the
editor, and nothing here needs them.

Exit codes:
  0  every requested mesh measured and written
  2  editor gate refused (rule 7), or no admissible palette entries were selected
  3  stopped early on low memory — partial results still written
  4  a mesh failed to load or returned no bounds
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
MEASURED = os.path.join(REPO_ROOT, "Free", "_measured")
OUT = os.path.join(MEASURED, "rock_pivots.json")
MARKER = "__LANDSCAPELAB_ROCKMEASURE__"

# Excluded BY NAME, not by omission. These are the palette's HAZARD rows.
HAZARD = ("SM_GroundRevealRock001", "SM_GroundRevealRock002")

# Stop if a load leaves less than this free. Chosen from this session's
# observed range (0.8-2.0 GB free): below 1.0 GB the editor has paged
# hard every time.
FLOOR_GB = 1.0

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _m = _unreal.EditorAssetLibrary.load_asset(_p)
        if _m is None:
            _out["error"] = "load_asset returned None"
        else:
            # get_bounds() returns a BoxSphereBounds OBJECT, not a
            # tuple -- .origin and .box_extent. This is the form
            # import_static_mesh.py:291-292 and place_foliage.py:1547-1548
            # both already use; I subscripted it and it raised. Read the
            # working caller, do not assume the shape (NN23).
            _b = _m.get_bounds()
            _o, _e = _b.origin, _b.box_extent
            _out["origin_cm"] = [_o.x, _o.y, _o.z]
            _out["extent_cm"] = [_e.x, _e.y, _e.z]
            # Nanite: reflected settings, not the registry tag.
            try:
                _ns = _m.get_editor_property("nanite_settings")
                _out["nanite_enabled"] = bool(
                    _ns.get_editor_property("enabled"))
            except Exception as _ex:
                _out["nanite_enabled"] = None
                _out["nanite_error"] = str(_ex)[:120]
            # LOD count via the subsystem (EditorStaticMeshLibrary's
            # GetLodCount is deprecated since 5.0).
            try:
                _ss = _unreal.get_editor_subsystem(
                    _unreal.StaticMeshEditorSubsystem)
                _out["lod_count"] = int(_ss.get_lod_count(_m))
            except Exception as _ex:
                _out["lod_count"] = None
                _out["lod_error"] = str(_ex)[:120]
            try:
                _out["material_slots"] = len(_m.static_materials)
            except Exception:
                _out["material_slots"] = None
            # LOD GROUP. `StaticMesh.lod_group` is a Name (PythonStub
            # :387388, enclosing class resolved rather than recalled) and
            # is documented but has no generated @property, so it is read
            # through get_editor_property.
            #
            # WHY IT IS MEASURED AND NOT ASSUMED: an engine LOD group
            # (`LargeTree`, `Foliage`, ...) SUPPLIES default screen sizes
            # and can override the vendor chain; NAME_None means the mesh
            # supplies nothing and every screen size and cull distance
            # must be declared explicitly. Those are opposite obligations
            # for the consumer, so reading "" as "no group" would be the
            # absence-carries-no-information trap (NN17). An unreadable
            # value stays None and is NOT collapsed into "None the group".
            try:
                _lg = _m.get_editor_property("lod_group")
                _out["lod_group"] = str(_lg) if _lg is not None else ""
            except Exception as _ex:
                _out["lod_group"] = None
                _out["lod_group_error"] = str(_ex)[:160]
            # PER-LOD TRIANGLES AND THE REAL SCREEN SIZES.
            # The cost model's LOD_PERCENT/LOD_SCREEN describe a
            # GENERATED chain (R5's conifers, percent = screen_size^2).
            # These rocks ship a VENDOR-authored chain, and modelling it
            # understates the deep LODs badly -- boulder LOD3 models to
            # 32 triangles and actually has 596, an 18x error in the
            # optimistic direction. Both accessors were confirmed on the
            # RUNNING 5.8 editor by enumerating the reflected surface,
            # not recalled: `StaticMesh.get_num_triangles(lod_index)` and
            # `StaticMeshEditorSubsystem.get_lod_screen_sizes(mesh)`.
            _n = _out.get("lod_count")
            try:
                if _n:
                    _out["lod_triangles"] = [
                        int(_m.get_num_triangles(_i)) for _i in range(_n)]
                else:
                    _out["lod_triangles"] = None
            except Exception as _ex:
                _out["lod_triangles"] = None
                _out["lod_tri_error"] = str(_ex)[:160]
            try:
                _ss2 = _unreal.get_editor_subsystem(
                    _unreal.StaticMeshEditorSubsystem)
                _out["lod_screen_sizes"] = [
                    float(_v) for _v in _ss2.get_lod_screen_sizes(_m)]
            except Exception as _ex:
                _out["lod_screen_sizes"] = None
                _out["lod_screen_error"] = str(_ex)[:160]
            _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

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


def palette_rocks(recipe, pass_id=3):
    """Admissible palette entries for one pass. HAZARD excluded.

    `pass_id` was hard-coded to 3 until 2026-08-08. Pass 5's ground
    clutter needs the SAME three measurements for the same reasons —
    a box-centred pivot sinks a stump to its waist exactly as it sinks a
    boulder, and `lod_depth` is validated against the MEASURED
    `lod_count` regardless of what the mesh depicts. Nothing in the
    payload is rock-specific; only this filter was.

    **`admit` stays strictly YES.** CONDITIONAL entries (`dead_leaves`,
    `dead_leaves_flat`) are NOT measured here: admission is a ruling that
    has not been made, and measuring them would quietly produce the
    input that makes placing them look ready. Fail closed.
    """
    out = []
    for e in (recipe.get("palette") or {}).get("entries", []):
        if e.get("pass") != pass_id:
            continue
        if e.get("admit") not in ("YES",):
            continue
        name = e["path"].rsplit("/", 1)[-1]
        if name in HAZARD:
            continue
        out.append((e["id"], e["path"], e["role"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine.json"))
    ap.add_argument("--only", default=None,
                    help="measure just this palette id")
    ap.add_argument("--pass", dest="pass_id", type=int, default=3,
                    help="palette pass to measure (3 = rocks, "
                         "5 = ground clutter). Default 3.")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)

    with open(args.recipe, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)
    rocks = palette_rocks(recipe, args.pass_id)
    if args.only:
        rocks = [r for r in rocks if r[0] == args.only]
    if not rocks:
        print("REFUSE: no admissible pass-{0} entries selected"
              .format(args.pass_id))
        return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("measuring : {0} mesh(es), one load per remote call".format(
        len(rocks)))
    print("excluded  : {0}  (palette HAZARD — 8K texture, 4608 MB encode)"
          .format(", ".join(HAZARD)))
    print("")

    existing = {}
    if os.path.isfile(OUT):
        with open(OUT, "r", encoding="utf-8") as fh:
            existing = json.load(fh)

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

        for pid, path, role in rocks:
            # available_gb returns a TUPLE (available, total), and
            # (None, None) when it cannot read. Read the source, do not
            # assume the shape (NN23). A None reading is treated as
            # "I could not look" and STOPS, rather than being coerced to
            # a number that would sail past the floor (NN6).
            free, _total = resource_guard.available_gb()
            if free is None:
                print("")
                print("STOP: could not read available memory. Refusing to "
                      "load another Fab mesh blind on a host that has hung "
                      "once. Partial results are written.")
                rc = 3
                break
            if free < FLOOR_GB:
                print("")
                print("STOP: {0:.2f} GB free, below the {1:.1f} GB floor. "
                      "Partial results are written; re-run to continue."
                      .format(free, FLOOR_GB))
                rc = 3
                break
            try:
                remote.open_command_connection(node["node_id"])
                r = remote.run_command(
                    PAYLOAD.format(path=path, marker=MARKER),
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
                err = (row or {}).get("error", "no parseable result")
                print("  {0:<26} FAILED: {1}".format(pid, err))
                rc = 4
                continue

            o, e = row["origin_cm"], row["extent_cm"]
            horiz_m = (o[0] ** 2 + o[1] ** 2) ** 0.5 / 100.0
            base_m = (o[2] - e[2]) / 100.0
            existing[path] = {
                "id": pid, "role": role,
                "pivot_offset_xy_m": round(horiz_m, 4),
                "base_offset_z_m": round(base_m, 4),
                "extent_m": [round(v / 100.0, 3) for v in e],
                "nanite_enabled": row.get("nanite_enabled"),
                "lod_count": row.get("lod_count"),
                "material_slots": row.get("material_slots"),
                "lod_triangles": row.get("lod_triangles"),
                "lod_screen_sizes": row.get("lod_screen_sizes"),
            }
            tris = row.get("lod_triangles")
            print("  {0:<26} pivot {1:5.2f} m  base {2:+6.2f} m  "
                  "nanite {3!s:<5} slots {4!s:<3} tris {5:<28} free {6:.1f}GB"
                  .format(pid, horiz_m, base_m, row.get("nanite_enabled"),
                          row.get("material_slots"),
                          "/".join(str(t) for t in tris) if tris
                          else "MEASUREMENT FAILED", free))
    finally:
        remote.stop()

    os.makedirs(MEASURED, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=1, sort_keys=True)
    print("")
    print("wrote {0} ({1} mesh(es) total)".format(
        os.path.relpath(OUT, REPO_ROOT), len(existing)))
    nan = [v for v in existing.values() if v.get("nanite_enabled") is None]
    if nan:
        print("NOTE: {0} mesh(es) returned no Nanite state — reported as "
              "UNKNOWN, never as False.".format(len(nan)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
