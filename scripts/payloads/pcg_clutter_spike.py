"""pcg_clutter_spike.py -- Brief 5 Part C, P3 spike (runs INSIDE the editor via ue_exec).

Measures the GAME-THREAD cost of producing ground-clutter instances at three counts
(a density sweep) per class, using the PROVEN foliage-instancing idiom from
place_foliage.py -- `InstancedFoliageActor.add_instances(world, foliage_type, xforms)` --
which placed the world's 157k+ instances and is one-shot reliable. This is the SAME
HISM representation PCG emits (PCG_NOTES.md sec 4), so the render cost (a future -game
pass) is representation-identical.

A PCG graph (SurfaceSampler -> TransformPoints -> StaticMeshSpawner) is ALSO built
best-effort as a feasibility proof; any failure is caught and does NOT abort the
measurement (rule 6: no retry).

SAFETY: the level is NEVER saved. FoliageType assets are created in-memory under
/Game/Scratch/PCG and NOT saved. My clutter foliage types are cleared with
remove_all_instances between arms and never touch the shipped foliage types. The
shipped instances (219,659) are counted-around by matching each ISM component's mesh.
Shipped Alpine8K.umap stays byte-identical on disk (item8_census brackets prove it).

Reports MARKER + one JSON object.
Substituted tokens (string .replace by the driver): __SEED__, __STATION_X__, __STATION_Y__,
__DISC_R_CM__.
"""
import json
import math
import time

import unreal as u

MARKER = "__LLPCG__"
SEED = int("__SEED__")
STATION_X = float("__STATION_X__")   # forest_floor station, cm
STATION_Y = float("__STATION_Y__")
DISC_R_CM = float("__DISC_R_CM__")   # 512 m disc = 51200 cm

SCRATCH_DIR = "/Game/Scratch/PCG"
GRAPH_PATH = SCRATCH_DIR + "/PCG_ClutterSpike"

# Clutter spawn set from P2 (input/clutter_inventory.json): foot-level-safe, non-hazard,
# non-16K-atlas. class -> mesh path + grid band. NO GroundRevealRock (HAZARD), no Inferno.
CLASSES = [
    {"cls": "grass",    "mesh": "/Game/KiteDemo/Environments/Foliage/Grass/FieldGrass/SM_FieldGrass_01", "band": "small"},
    {"cls": "stone",    "mesh": "/Game/DragonCave/Meshes/SM_StoneDebris01_",                              "band": "small"},
    {"cls": "herb",     "mesh": "/Game/KiteDemo/Environments/Foliage/Ferns/SM_Fern_03",                   "band": "mid"},
    {"cls": "shrub",    "mesh": "/Game/KiteDemo/Environments/Foliage/Flowers/Heather/SM_Heather_Mesh_Clumps2", "band": "mid"},
    {"cls": "rock",     "mesh": "/Game/KiteDemo/Environments/Rocks/River_Rock_01/SM_River_Rock_01",       "band": "large"},
    {"cls": "deadwood", "mesh": "/Game/DragonCave/Meshes/SM_Sticks_Small_10",                             "band": "large"},
]
# Count-based sweep: literal D1 (2/m^2) over a 512 m disc = ~1.6M -- unmeasurable in one
# pass. We place a representative COUNT that sweeps and report the effective density
# (count / disc area). ms/1000 is the load-bearing rate the density plan applies.
BASE_COUNT = 5000
MULTS = [1, 2, 4]                      # 5000 / 10000 / 20000
HARD_CAP = 40000                       # per-arm VRAM/time guard
BATCH = 2000
DISC_AREA_M2 = math.pi * (DISC_R_CM / 100.0) ** 2


def _rng(seed):
    s = [seed & 0x7FFFFFFF]

    def nxt():
        s[0] = (1103515245 * s[0] + 12345) & 0x7FFFFFFF
        return s[0] / float(0x7FFFFFFF)
    return nxt


def _disc_transforms(n, seed, z0):
    """n transforms uniformly in the forest_floor disc at a fixed ground z (world space)."""
    rnd = _rng(seed)
    out = []
    for _ in range(n):
        rr = DISC_R_CM * (rnd() ** 0.5)     # uniform-in-disc radius
        th = 6.2831853 * rnd()
        x = STATION_X + rr * math.cos(th)
        y = STATION_Y + rr * math.sin(th)
        yaw = 360.0 * rnd()
        out.append(u.Transform(u.Vector(x, y, z0),
                               u.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
                               u.Vector(1.0, 1.0, 1.0)))
    return out


def _center_z():
    """One line trace at the station centre for a representative ground z (cm)."""
    world = u.EditorLevelLibrary.get_editor_world()
    hit = u.SystemLibrary.line_trace_single(
        world, u.Vector(STATION_X, STATION_Y, 300000.0),
        u.Vector(STATION_X, STATION_Y, -100000.0),
        u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], u.DrawDebugTrace.NONE, True)
    # repo-proven ground-Z access (c0_verify_pair_payload.txt:43); stub HitResult
    # exposes no property accessors, so read the tuple.
    return hit.to_tuple()[4].z if hit else 20000.0


def _count_for_mesh(world, mesh):
    """Sum instances of ISM components whose static mesh == mesh (isolate my type from the
    219k shipped instances)."""
    total = 0
    for a in u.GameplayStatics.get_all_actors_of_class(world, u.InstancedFoliageActor):
        for c in a.get_components_by_class(u.InstancedStaticMeshComponent):
            try:
                if c.get_editor_property("static_mesh") == mesh:
                    total += int(c.get_instance_count())
            except Exception:
                pass
    return total


def measure_arms():
    world = u.EditorLevelLibrary.get_editor_world()
    tools = u.AssetToolsHelpers.get_asset_tools()
    z0 = _center_z()
    results = []
    n_measured = 0
    for ci, c in enumerate(CLASSES):
        mesh = u.EditorAssetLibrary.load_asset(c["mesh"])
        if mesh is None:
            results.append({"cls": c["cls"], "mesh": c["mesh"], "error": "load_asset None"})
            continue
        try:
            tris = mesh.get_num_triangles(0)
        except Exception:
            tris = None
        # one in-memory foliage type per class (NOT saved)
        ft_path = SCRATCH_DIR + "/FT_spike_" + c["cls"]
        if u.EditorAssetLibrary.does_asset_exist(ft_path):
            u.EditorAssetLibrary.delete_asset(ft_path)
        ft = tools.create_asset("FT_spike_" + c["cls"], SCRATCH_DIR,
                                u.FoliageType_InstancedStaticMesh,
                                u.FoliageType_InstancedStaticMeshFactory())
        if ft is None:
            results.append({"cls": c["cls"], "mesh": c["mesh"], "error": "create foliage type None"})
            continue
        ft.set_editor_property("mesh", mesh)
        try:
            for mult in MULTS:
                n = min(BASE_COUNT * mult, HARD_CAP)
                capped = n < BASE_COUNT * mult
                u.InstancedFoliageActor.remove_all_instances(world, ft)
                xforms = _disc_transforms(n, SEED + ci * 1000 + mult, z0)
                t0 = time.time()
                buf = []
                for xf in xforms:
                    buf.append(xf)
                    if len(buf) >= BATCH:
                        u.InstancedFoliageActor.add_instances(world, ft, buf)
                        buf = []
                if buf:
                    u.InstancedFoliageActor.add_instances(world, ft, buf)
                dt_ms = (time.time() - t0) * 1000.0
                got = _count_for_mesh(world, mesh)
                results.append({
                    "cls": c["cls"], "band": c["band"], "mesh": c["mesh"], "lod0_tris": tris,
                    "requested": n, "instances": got, "capped": capped,
                    "effective_density_per_m2": round(got / DISC_AREA_M2, 5),
                    "add_gamethread_ms": round(dt_ms, 3),
                    "add_ms_per_1000": round(dt_ms / (got / 1000.0), 4) if got else None,
                })
                if got:
                    n_measured += 1
        finally:
            u.InstancedFoliageActor.remove_all_instances(world, ft)
            u.SystemLibrary.collect_garbage()
    return results, n_measured


def build_pcg_graph():
    """Best-effort PCG graph authoring proof (SurfaceSampler->Transform->StaticMeshSpawner)."""
    try:
        tools = u.AssetToolsHelpers.get_asset_tools()
        if u.EditorAssetLibrary.does_asset_exist(GRAPH_PATH):
            u.EditorAssetLibrary.delete_asset(GRAPH_PATH)
        graph = tools.create_asset("PCG_ClutterSpike", SCRATCH_DIR, u.PCGGraph, u.PCGGraphFactory())
        if graph is None:
            return {"ok": False, "error": "create_asset PCGGraph -> None"}
        sampler_node, sampler = graph.add_node_of_type(u.PCGSurfaceSamplerSettings)
        sampler.set_editor_property("points_per_squared_meter", 2.0)
        xf_node, _xf = graph.add_node_of_type(u.PCGTransformPointsSettings)
        spawn_node, spawn = graph.add_node_of_type(u.PCGStaticMeshSpawnerSettings)
        spawn.set_mesh_selector_type(u.PCGMeshSelectorWeighted)
        sel = spawn.get_editor_property("mesh_selector_instance")
        entry = u.PCGMeshSelectorWeightedEntry(weight=1)
        desc = entry.get_editor_property("descriptor")
        desc.set_editor_property("static_mesh", u.load_asset(CLASSES[0]["mesh"]))
        entry.set_editor_property("descriptor", desc)
        sel.set_editor_property("mesh_entries", [entry])
        inp = graph.get_input_node()
        outp = graph.get_output_node()
        wired = []
        for a, apin, b, bpin in [(inp, "Out", sampler_node, "In"),
                                 (sampler_node, "Out", xf_node, "In"),
                                 (xf_node, "Out", spawn_node, "In"),
                                 (spawn_node, "Out", outp, "In")]:
            try:
                graph.add_edge(a, u.Name(apin), b, u.Name(bpin))
                wired.append([apin, bpin, True])
            except Exception as e:
                wired.append([apin, bpin, str(e)[:80]])
        try:
            radii = u.PCGRuntimeGenerationRadii()
            radii.set_editor_property("radius400", u.PerQualityLevelFloat(30000.0))
            graph.set_editor_property("generation_radii", radii)
            radii_ok = True
        except Exception as e:
            radii_ok = str(e)[:120]
        saved = bool(u.EditorAssetLibrary.save_asset(GRAPH_PATH))
        return {"ok": bool(saved), "saved": saved, "nodes": len(graph.nodes()),
                "edges_wired": wired, "runtime_radii_set": radii_ok, "graph_path": GRAPH_PATH}
    except Exception as e:
        return {"ok": False, "error": repr(e)[:300]}


def main():
    world = u.EditorLevelLibrary.get_editor_world()
    wpath = world.get_path_name() if world else "None"
    wname = world.get_name() if world else "None"
    # rule 11: require Alpine8K specifically ("Alpine8K" excludes the pre-8K "/Game/Alpine").
    if "Alpine8K" not in wpath and "Alpine8K" not in wname:
        return {"error": "WRONG LEVEL: expected Alpine8K, got path=%r name=%r -- refusing"
                % (wpath, wname)}
    out = {"world_name": wname, "world_path": wpath, "disc_area_m2": round(DISC_AREA_M2, 1),
           "station_cm": [STATION_X, STATION_Y], "disc_r_cm": DISC_R_CM, "seed": SEED,
           "base_count": BASE_COUNT, "mults": MULTS,
           "_note": "add_gamethread_ms = wall-clock of InstancedFoliageActor.add_instances "
                    "(the foliage/PCG spawn stage, game thread). GPU render cost NOT measured "
                    "here -- owed: -game MRQ pass."}
    out["pcg_graph"] = build_pcg_graph()
    arms, n_measured = measure_arms()
    out["arms"] = arms
    out["n_measured_arms"] = n_measured
    if n_measured == 0:
        out["error"] = "ZERO measured arms (rule 13): no instances placed"
    return out


try:
    _res = main()
    _err = _res.get("error")
except Exception as _e:
    _res, _err = {}, repr(_e)
print(MARKER + json.dumps({"ok": _err is None, "error": _err, "result": _res}))
