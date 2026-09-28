"""scatter_alpinelab.py — rock meshes onto AlpineLab_v1, mask-driven.

    python scripts/scatter_alpinelab.py                  # plan only
    python scripts/scatter_alpinelab.py --place          # plan and place
    python scripts/scatter_alpinelab.py --clear          # remove them

PLANNING IS OFFLINE AND THE EDITOR IS NEVER CONSULTED FOR IT. Positions
come from the same PNGs the material samples, so a rock lands on the
ground its mask describes -- the mask is not a second opinion about the
terrain, it IS the terrain's own simulation output.

WHY NOT rock_scatter.py / place_foliage.py
------------------------------------------
Those serve /Game/Alpine. They read `foliage.rock_scatter` out of
alpine.json, derive a talus DEPOSITION FIELD from that heightmap, and
place through FoliageTypes with an ORPHAN SWEEP that deletes instances
it did not plan. Pointing them at a different world with a different
heightmap would either refuse (they check) or sweep a level they know
nothing about. AlpineLab has what those tools spend most of their code
computing: Gaea already ran the erosion and exported the fields.

Placement here goes through the FOLIAGE PATH (the one this project has
proven, after add_component_by_class turned out not to exist in 5.8): one
FoliageType_InstancedStaticMesh asset per species (`FT_AL_<name>`) whose
instances are added to the level's InstancedFoliageActor. Re-placing is
idempotent because each species' prior instances are removed first
(`remove_all_instances`, per FoliageType). NOTE: a bare `--clear` only sweeps
legacy label-prefixed actors (an earlier, superseded implementation made
those) and does NOT remove the foliage instances this tool places; that
cleanup happens per-FoliageType during a `--place` run. Removing instances on
a bare `--clear` is an open follow-up, not a claim this docstring should make.

THE BUDGET IS THE DESIGN CONSTRAINT, NOT THE MESH RESOLUTION
------------------------------------------------------------
"The highest-resolution meshes we can hold" is a question about
instances x triangles at a cull distance, not about picking the biggest
mesh. `scree_slab_001` is 33,855 triangles at LOD0 and 829 at LOD3, so
what it costs depends almost entirely on how many are close. The plan
prints the worst-case triangle load inside each species' cull disc
before anything is placed, and REFUSES above the declared ceiling.

Ground Z comes from the heightmap by the same arithmetic the landscape
uses:

    z_m = (v / 65535 - 0.5) * 512 * scale_z / 100

which reproduces the summit at 461.7 m -- the value a collision trace
independently returned to 1 cm.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bootstrap          # noqa: E402
import alpinelab_source
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_SCATTER__"
RECIPE = "recipes/alpinelab_v1.json"
PIVOTS = "Free/_measured/rock_pivots.json"
ACTOR_PREFIX = "AlpineLabScatter_"

# Declared by the RECIPE, resolved by alpinelab_source.resolve(), bound in
# main(). Formerly a constant here and a second copy in
# make_alpinelab_material.py; see alpinelab_source.py for why one copy of a
# build path is the only safe number of copies.
PKG = None
MASK_PNG = None
HEIGHTMAP_PNG = None


def _load(name):
    from PIL import Image
    return np.asarray(Image.open(os.path.join(PKG, name))
                      ).astype(np.float32) / 65535.0


def _slope_deg(height01, scale_z, scale_xy, smooth_px=1):
    """Terrain slope in degrees, from the heightmap.

    Metres per texel is scale_xy / 100 (scale_xy is CM per texel; 100 cm =
    1 m at this scale, so it is 1.0 m here), and the vertical span is
    512 * scale_z / 100 metres over 0..1.
    """
    span_m = 512.0 * scale_z / 100.0
    h_m = height01 * span_m
    gy, gx = np.gradient(h_m, scale_xy / 100.0)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def build_plan(recipe, pivots, seed=20260809):
    """Positions per species. Pure numpy; no editor, no engine."""
    land = recipe["landscape"]
    scale_z = float(land["scale_z"])
    scale_xy = float(land["scale_xy"])
    origin = float(land["origin_cm"])
    span_m = 512.0 * scale_z / 100.0

    height = _load(HEIGHTMAP_PNG)
    masks = {k: _load(v) for k, v in MASK_PNG.items()}
    slope = _slope_deg(height, scale_z, scale_xy)
    snow = np.maximum(masks["snow_depth"], masks["snow_hard"])

    rows, cols = height.shape
    area_ha = (rows * cols) * (scale_xy / 100.0) ** 2 / 10000.0

    rng = np.random.default_rng(seed)
    plans = {}
    print("terrain: {0}x{1} texels, {2:,.0f} ha, height span {3:.1f} m"
          .format(cols, rows, area_ha, span_m))
    print("slope: p50 {0:.1f} deg  p90 {1:.1f}  max {2:.1f}".format(
        *np.percentile(slope, [50, 90, 100])))
    print("")
    print("{0:<18s} {1:>9s} {2:>9s} {3:>10s} {4:>12s}".format(
        "species", "eligible", "planned", "per ha", "worst tris"))

    for name, sp in recipe["scatter"]["species"].items():
        if name.startswith("_"):
            continue
        mesh = pivots_by_id(pivots, sp["mesh_id"])
        sel = np.ones_like(height, dtype=bool)
        for key, (lo, hi) in sp["mask_window"].items():
            if key == "slope_deg":
                src = slope
            elif key == "height01":
                src = height
            else:
                src = masks[key]
            sel &= (src >= lo) & (src <= hi)
        if sp.get("max_snow") is not None:
            sel &= snow <= float(sp["max_snow"])

        eligible = int(sel.sum())
        want = int(round(eligible * (scale_xy / 100.0) ** 2 / 10000.0
                         * float(sp["per_hectare"])))
        want = min(want, int(sp.get("max_instances", 10 ** 9)))
        if eligible == 0 or want <= 0:
            print("{0:<18s} {1:>9,d} {2:>9,d}   (nothing eligible)"
                  .format(name, eligible, 0))
            plans[name] = []
            continue

        idx = np.flatnonzero(sel.ravel())
        pick = rng.choice(idx, size=min(want, idx.size), replace=False)
        r_i, c_i = np.divmod(pick, cols)
        # Jitter inside the texel so a scatter does not read as a grid.
        jx = rng.random(pick.size) - 0.5
        jy = rng.random(pick.size) - 0.5
        wx = origin + (c_i + jx) * scale_xy
        wy = origin + (r_i + jy) * scale_xy
        hv = height[r_i, c_i].astype(np.float64)
        wz = (hv - 0.5) * span_m * 100.0

        s_lo, s_hi = sp["scale_range"]
        scl = rng.uniform(s_lo, s_hi, pick.size)
        yaw = rng.uniform(0.0, 360.0, pick.size)
        # base_offset_z_m is where the mesh's own base sits relative to
        # its pivot; embed_m pushes it further in so it does not read as
        # a prop resting on the surface.
        z_off = (-float(mesh["base_offset_z_m"]) * scl
                 - float(sp["embed_m"])) * 100.0

        plans[name] = {
            "mesh": mesh["path"],
            "mesh_id": sp["mesh_id"],
            "cull_m": float(sp["cull_m"]),
            "rows": np.stack([wx, wy, wz + z_off, scl, yaw], axis=1)
                      .round(2).tolist(),
        }
        # A species may override the per-instance triangle figure. The
        # fir does: charging a 505,494-triangle LOD0 to every instance
        # in a 420 m disc predicts two billion triangles, which is
        # arithmetic about a state the renderer never enters. The
        # override is recorded in the recipe WITH the LOD it represents,
        # so the number cannot read as a measurement of LOD0.
        tri0 = int(sp.get("budget_tris_per_instance")
                   or mesh["lod_triangles"][0])
        dens_ha = want / (eligible * (scale_xy / 100.0) ** 2 / 10000.0)
        # Worst case: every instance inside the cull disc at LOD0.
        in_disc = dens_ha * math.pi * (float(sp["cull_m"]) / 100.0) ** 2
        print("{0:<18s} {1:>9,d} {2:>9,d} {3:>10.2f} {4:>12,.0f}"
              .format(name, eligible, want, dens_ha, in_disc * tri0))
        plans[name]["worst_tris"] = in_disc * tri0

    return plans


def pivots_by_id(pivots, mesh_id):
    # `_direct:` is the deliberate escape hatch for a mesh that is not in
    # the rock registry -- the fir, which came through the Blender
    # normalisation path and has its own measurement file. It is spelled
    # loudly so it cannot be used by accident: an unmeasured mesh has no
    # pivot, and placing one is how a tree ends up buried or hovering.
    if mesh_id.startswith("_direct:"):
        return {"path": mesh_id.split(":", 1)[1],
                "base_offset_z_m": 0.0,
                "lod_triangles": [0],
                "id": mesh_id}
    for path, v in pivots.items():
        if v.get("id") == mesh_id:
            out = dict(v)
            out["path"] = path
            return out
    raise SystemExit("REFUSE: no measured mesh with id '{0}' in {1}. "
                     "A mesh this tool has never measured has no pivot "
                     "and would be placed floating or buried."
                     .format(mesh_id, PIVOTS))


PAYLOAD_BODY = '''
import json as _json
import unreal as _unreal

_out = {{"placed": {{}}, "errors": []}}
# THE PLAN COMES FROM A FILE, NOT FROM THE COMMAND STRING.
# 58,556 rows inline is several megabytes of Python source shipped
# through remote execution, and this project has already watched that
# transport drop a 418 KB reply on save_level. A path is 80 bytes.
with open(r"{planfile}", "r") as _fh:
    _spec = _json.load(_fh)
_eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
_eal = _unreal.EditorAssetLibrary
_prefix = _spec["prefix"]

# LEGACY LABEL SWEEP. This destroys level actors whose label starts with
# the prefix -- the output of an EARLIER, superseded per-actor implementation.
# The current foliage path (below) makes NO label-prefixed actors, so on this
# world the loop typically kills nothing. Idempotency of THIS tool's actual
# output is provided by remove_all_instances per FoliageType (below), NOT by
# this sweep. The destroyed count is still reported.
_killed = 0
for _a in list(_eas.get_all_level_actors()):
    try:
        if _a.get_actor_label().startswith(_prefix):
            _eas.destroy_actor(_a)
            _killed += 1
    except Exception as _e:
        _out["errors"].append("destroy: " + type(_e).__name__)
_out["cleared"] = _killed

if not _spec["place"]:
    print("{marker}" + _json.dumps(_out))
    raise SystemExit(0)

# THE FOLIAGE PATH, which is the one this project has proven.
# An earlier version of this payload called
# Actor.add_component_by_class -- an API that DOES NOT EXIST in 5.8's
# reflected surface, confirmed by grepping the generated stub after the
# editor raised AttributeError. Non-negotiable 23: an API remembered is
# an API guessed. place_foliage.py already had the answer:
#   FoliageType_InstancedStaticMesh            stub 390277
#   FoliageType_InstancedStaticMeshFactory     stub 390588
#   InstancedFoliageActor.remove_all_instances stub 589752
#   InstancedFoliageActor.add_instances        stub 589763
_tools = _unreal.AssetToolsHelpers.get_asset_tools()
_ues2 = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
_world = _ues2.get_editor_world()

for _name, _sp in _spec["species"].items():
    _mesh = _eal.load_asset(_sp["mesh"])
    if _mesh is None:
        _out["errors"].append("mesh missing: " + _sp["mesh"])
        continue
    _ftpath = _spec["ft_dir"] + "/FT_AL_" + _name
    if _eal.does_asset_exist(_ftpath):
        _ft = _eal.load_asset(_ftpath)
    else:
        _ft = _tools.create_asset(
            "FT_AL_" + _name, _spec["ft_dir"],
            _unreal.FoliageType_InstancedStaticMesh,
            _unreal.FoliageType_InstancedStaticMeshFactory())
    if _ft is None:
        _out["errors"].append("no foliage type for " + _name)
        continue
    _ft.set_editor_property("mesh", _mesh)
    # FoliageType.h:292 -- CullDistance 0 DISABLES culling rather than
    # meaning "unlimited". This project lost a GPU to that once.
    _ft.set_editor_property("cull_distance", _unreal.Int32Interval(
        int(_sp["cull_m"] * 100 * 0.7), int(_sp["cull_m"] * 100)))
    _eal.save_asset(_ftpath, False)

    _unreal.InstancedFoliageActor.remove_all_instances(_world, _ft)

    _buf = []
    _n = 0
    for _r in _sp["rows"]:
        _buf.append(_unreal.Transform(
            _unreal.Vector(_r[0], _r[1], _r[2]),
            _unreal.Rotator(0.0, 0.0, _r[4]),
            _unreal.Vector(_r[3], _r[3], _r[3])))
        if len(_buf) >= 2000:
            _unreal.InstancedFoliageActor.add_instances(_world, _ft, _buf)
            _n += len(_buf)
            _buf = []
    if _buf:
        _unreal.InstancedFoliageActor.add_instances(_world, _ft, _buf)
        _n += len(_buf)

    # add_instances returns None, so the ONLY evidence is the engine's
    # own component count -- read back, never inferred from the loop.
    _eng = 0
    for _ifa in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.InstancedFoliageActor):
        for _c in _ifa.get_components_by_class(
                _unreal.InstancedStaticMeshComponent):
            _sm = _c.get_editor_property("static_mesh")
            # get_path_name() returns "/Game/X/SM_Foo.SM_Foo" -- the
            # OBJECT path, with the asset name after a dot. Comparing it
            # to the recipe's package path "/Game/X/SM_Foo" is false for
            # every mesh, and the first version of this read-back
            # reported 0 placed for all six species while the engine
            # actually held 30,589. A read-back that cannot match is
            # worse than none: it reports a catastrophe that did not
            # happen.
            if _sm is not None and \
                    _sm.get_path_name().split(".")[0] == _sp["mesh"]:
                _eng += _c.get_instance_count()
    _out["placed"][_name] = {{
        "asked": _n,
        "engine": _eng,
        "mesh": _sp["mesh"],
    }}

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    for line in text.splitlines():
        if MARKER in line:
            try:
                return json.loads(line.split(MARKER, 1)[1])
            except Exception:
                return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=RECIPE)
    ap.add_argument("--place", action="store_true")
    ap.add_argument("--clear", action="store_true",
                    help="sweep legacy label-prefixed actors and place "
                         "nothing (does NOT remove the foliage instances this "
                         "tool places -- those clear per-FoliageType on --place)")
    ap.add_argument("--seed", type=int, default=20260809)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args(argv)

    with open(os.path.join(bootstrap.REPO_ROOT, args.recipe),
              encoding="utf-8") as fh:
        recipe = json.load(fh)

    # Bind the source location from the recipe. Refuses rather than
    # defaulting -- see alpinelab_source.py.
    global PKG, MASK_PNG, HEIGHTMAP_PNG
    try:
        PKG, MASK_PNG, HEIGHTMAP_PNG = alpinelab_source.resolve(
            recipe, args.recipe)
    except alpinelab_source.SourceError as exc:
        print("REFUSE:", exc)
        return 2
    print("source   : {0}".format(PKG))
    with open(os.path.join(bootstrap.REPO_ROOT, PIVOTS),
              encoding="utf-8") as fh:
        pivots = json.load(fh)

    plans = {}
    if not args.clear:
        plans = build_plan(recipe, pivots, args.seed)
        total = sum(len(p["rows"]) for p in plans.values() if p)
        worst = sum(p.get("worst_tris", 0) for p in plans.values() if p)
        ceil_n = int(recipe["scatter"]["budget"]["max_instances"])
        ceil_t = float(recipe["scatter"]["budget"]["max_worst_tris"])
        print("")
        print("TOTAL     {0:,} instances (ceiling {1:,})".format(
            total, ceil_n))
        print("WORST     {0:,.0f} triangles in a cull disc (ceiling "
              "{1:,.0f})".format(worst, ceil_t))
        if total > ceil_n or worst > ceil_t:
            print("")
            print("REFUSE: over the declared budget. Lower a density or "
                  "a cull distance in the recipe; do not raise the "
                  "ceiling to fit the plan.")
            return 3
        if not args.place:
            print("")
            print("PLAN ONLY. Nothing placed. Re-run with --place.")
            return 0

    spec = {
        "prefix": ACTOR_PREFIX,
        "ft_dir": "/Game/AlpineLab_v1/Foliage",
        "place": bool(args.place and not args.clear),
        "species": {k: v for k, v in plans.items() if v},
    }
    planfile = os.path.join(bootstrap.REPO_ROOT, "foliage",
                            "alpinelab_scatter.json")
    os.makedirs(os.path.dirname(planfile), exist_ok=True)
    with open(planfile, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    print("plan file : {0}  ({1:,} bytes)".format(
        planfile, os.path.getsize(planfile)))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            # THE PAYLOAD GOES TO A FILE AND WE SEND ITS PATH.
            # MODE_EXEC_FILE means what it says: the engine treats the
            # command as a FILENAME. Sending source text inline works
            # only for short commands and otherwise surfaces as
            #   "Could not load Python file
            #    'C:/Program Files/.../Win64/<the entire payload>'"
            # -- the engine resolving the source as a path relative to
            # its own binaries directory. Measured on 2026-08-09 by
            # bisecting the payload byte by byte; the boundary was
            # reproducible, which is what ruled out a busy editor.
            src = PAYLOAD_BODY.format(
                marker=MARKER, planfile=planfile.replace("\\", "/"))
            payload_file = os.path.join(
                bootstrap.UE_PROJECT_ROOT, "Saved",
                "landscapelab_scatter_payload.py")
            os.makedirs(os.path.dirname(payload_file), exist_ok=True)
            with open(payload_file, "w", encoding="utf-8") as fh:
                fh.write(src)
            r = remote.run_command(
                payload_file.replace("\\", "/"),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            raw = bootstrap._collect_output(r) if r else ""
            data = _parse(raw)
            if data is None:
                print("NO PARSEABLE RESULT -- full output, untruncated:")
                print(raw[-6000:])
                return 4
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    print("")
    print("cleared actors : {0}".format(data.get("cleared")))
    for name, got in (data.get("placed") or {}).items():
        flag = "ok" if got["asked"] == got["engine"] else "MISMATCH"
        print("  {0:<18s} asked {1:>7,d}   engine {2:>7,d}   {3}".format(
            name, got["asked"], got["engine"], flag))
    for e in data.get("errors") or []:
        print("  ERROR {0}".format(e))
    placed = sum(v["engine"] for v in (data.get("placed") or {}).values())
    print("TOTAL IN ENGINE: {0:,}".format(placed))
    if data.get("errors"):
        return 5
    print("")
    print("The LEVEL is not saved. File > Save All to persist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
