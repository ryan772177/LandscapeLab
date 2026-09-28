"""measure_clutter_meshes.py -- register vendor clutter meshes for the grass pivot gate.

    python scripts/measure_clutter_meshes.py --mesh /Game/... [--mesh ...] --group brief7_p3b_clutter

WHY. `landscape_spec.recipe_normalization_errors` refuses any recipe mesh that
has no VERIFIED row in `Free/_measured/normalized.json` (Blender-normalised)
or `Free/_measured/engine_derived.json` (measured live) or
`Free/_measured/rock_pivots.json` (the rock instrument). A Fab `.uasset` that
never had an FBX cannot get a Blender row (R-ASSET forbids authoring into a
Fab folder), so it is MEASURED on the live asset -- the path the eight
Blueberry varieties took on 2026-08-15 through measure_tree_packs.py -- and
written to `engine_derived.json`, where the grass gate reads
`base_offset_z_m` + `height_m` through `uncorrected_pivot_errors()`.

THE MESH PAYLOAD IS NOT FORKED. `measure_rock_meshes.PAYLOAD` measures
bounds/pivot, Nanite, LOD count and per-LOD triangles on one load; this
imports it exactly as measure_tree_packs.py does (non-negotiable 24).

CONTRACT applied here, so a refusal is VISIBLE (a failing mesh is written
with ok=false, not omitted): pivot_offset_xy_m <= MAX_PIVOT_OFFSET_M (1.0),
|base_offset_z_m| <= MAX_BASE_OFFSET_M (0.25) -- landscape_spec's own limits,
the same ones the material builder re-checks on get_bounds() at the point of
use (rule 12: the registry row is the cheap pre-check, not the proof).

Read-only on the world: loads assets, places nothing, saves no package.
Exit: 0 every mesh measured and ok; 2 refused/argument error; 4 a mesh failed
the contract or could not be measured (rows still written).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap                     # noqa: E402
import landscape_spec                # noqa: E402
import measure_rock_meshes as mrm    # noqa: E402  (payload reused, not copied)
import resource_guard                # noqa: E402
import verify_landscape              # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
REGISTRY = landscape_spec.ENGINE_DERIVED_REPORT
FLOOR_GB = 3.0


def measure(paths, timeout):
    rows = []
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return None
        remote.open_command_connection(node["node_id"])

        def run(src):
            r = remote.run_command(src, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            return bootstrap._collect_output(r) if r else ""

        for path in paths:
            free, _total = resource_guard.available_gb()
            if free < FLOOR_GB:
                print("STOP: {0:.2f} GB free below the {1:.1f} GB floor; "
                      "partial run DECLARED".format(free, FLOOR_GB))
                break
            text = run(mrm.PAYLOAD.format(path=path, marker=mrm.MARKER))
            row = mrm._parse(text)
            if row is None:
                row = {"path": path, "ok": False,
                       "error": "no parseable result (could not look)"}
            rows.append(row)
            print("  {0:<40} ok={1} err={2}".format(
                path.rsplit("/", 1)[-1], row.get("ok"), row.get("error")))
    finally:
        try:
            remote.stop()
        except Exception:
            pass
    return rows


def to_registry_row(row, group, today):
    """measure_rock_meshes row -> engine_derived.json row, contract applied."""
    path = row["path"]
    leaf = path.rstrip("/").split("/")[-1].split(".")[0]
    out = {"object": leaf, "ok": False, "asset": path}
    if not row.get("ok"):
        out["error"] = row.get("error") or "measurement failed"
        return out
    ext = row.get("extent_cm") or [0, 0, 0]
    org = row.get("origin_cm") or [0, 0, 0]
    xy = round(((org[0] ** 2 + org[1] ** 2) ** 0.5) / 100.0, 4)
    bz = round((org[2] - ext[2]) / 100.0, 4)
    h = round(2.0 * ext[2] / 100.0, 3)
    out.update({
        "pivot_offset_xy_m": xy,
        "base_offset_z_m": bz,
        "height_m": h,
        # HALF-extents, the rock-registry convention: landscape_spec.
        # uncorrected_pivot_errors doubles extent_m[2] to get the height
        # (audit F2 -- a full extent here would halve the sink gate).
        "extent_m": [round(ext[0] / 100.0, 3), round(ext[1] / 100.0, 3),
                     round(ext[2] / 100.0, 3)],
        "nanite_enabled": row.get("nanite_enabled"),
        "lod_count": row.get("lod_count"),
        "lod_triangles": row.get("lod_triangles"),
        "material_slots": row.get("material_slots"),
        "provenance": ("vendor Fab content, already .uasset on disk; never went "
                       "through scripts/blender/normalize_asset.py (no FBX; "
                       "R-ASSET forbids authoring into a Fab folder). Measured on "
                       "the LIVE asset by scripts/measure_clutter_meshes.py on "
                       "{0} for Brief 7 Phase 3b ground clutter. Placed by the "
                       "GRASS system, which applies NO pivot correction -- read "
                       "by landscape_spec.uncorrected_pivot_errors(), not merely "
                       "recorded.".format(today)),
        "measured_by": "scripts/measure_clutter_meshes.py",
        "measured_on": today,
        "group": group,
    })
    reasons = []
    if not (xy <= landscape_spec.MAX_PIVOT_OFFSET_M):
        reasons.append("pivot_offset_xy_m {0} > {1}".format(
            xy, landscape_spec.MAX_PIVOT_OFFSET_M))
    if not (abs(bz) <= landscape_spec.MAX_BASE_OFFSET_M):
        reasons.append("|base_offset_z_m| {0} > {1}".format(
            abs(bz), landscape_spec.MAX_BASE_OFFSET_M))
    if h <= 0.0:
        reasons.append("height_m {0} <= 0".format(h))
    out["ok"] = not reasons
    if reasons:
        out["refused_because"] = reasons
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mesh", action="append", required=True,
                    help="/Game path of a StaticMesh (repeatable)")
    ap.add_argument("--group", required=True,
                    help="engine_derived.json group name to write")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--source-out", default=None,
                    help="raw measurement JSON (default Free/_measured/<group>.json)")
    args = ap.parse_args(argv)

    paths = list(dict.fromkeys(args.mesh))
    today = datetime.date.today().isoformat()
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("READ-ONLY on the world: loads assets, places nothing, saves nothing.")
    print("meshes    : {0}".format(len(paths)))
    rows = measure(paths, args.timeout)
    if rows is None:
        return 2
    if len(rows) != len(paths):
        print("PARTIAL: {0} of {1} measured".format(len(rows), len(paths)))

    src_out = args.source_out or os.path.join(
        REPO_ROOT, "Free", "_measured", args.group + ".json")
    with open(src_out, "w", encoding="utf-8") as fh:
        json.dump({"_what": "raw measure_rock_meshes.PAYLOAD rows for group "
                            + args.group, "measured_on": today, "rows": rows},
                  fh, indent=1)
    print("raw rows -> {0}".format(os.path.relpath(src_out, REPO_ROOT)))

    with open(REGISTRY, "r", encoding="utf-8") as fh:
        reg = json.load(fh)
    if not isinstance(reg, dict):
        print("REFUSE: registry top level is not a dict")
        return 2
    reg_rows = [to_registry_row(r, args.group, today) for r in rows]
    for r in reg_rows:
        r["source_measurement"] = os.path.relpath(src_out, REPO_ROOT).replace("\\", "/")
    group = reg.get(args.group)
    if not isinstance(group, dict):
        group = {"_what": "Brief 7 Phase 3b ground-clutter meshes (grass system, "
                          "ForestFloor + Grass layers); rows measured live, "
                          "contract applied, refusals written with ok=false.",
                 "objects": []}
    keep = [o for o in (group.get("objects") or [])
            if isinstance(o, dict) and o.get("object") not in
            {r["object"] for r in reg_rows}]
    group["objects"] = keep + reg_rows
    reg[args.group] = group
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, REGISTRY)          # atomic (audit F10)
    bad = [r for r in reg_rows if not r.get("ok")]
    print("registry  -> {0}: {1} rows written, {2} ok, {3} refused"
          .format(os.path.relpath(REGISTRY, REPO_ROOT), len(reg_rows),
                  len(reg_rows) - len(bad), len(bad)))
    for r in reg_rows:
        print("  {0:<32} ok={1} xy={2} base_z={3} h={4} nanite={5} lods={6} {7}"
              .format(r["object"], r["ok"], r.get("pivot_offset_xy_m"),
                      r.get("base_offset_z_m"), r.get("height_m"),
                      r.get("nanite_enabled"), r.get("lod_triangles"),
                      r.get("refused_because") or r.get("error") or ""))
    if len(rows) != len(paths):
        return 4
    return 4 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
