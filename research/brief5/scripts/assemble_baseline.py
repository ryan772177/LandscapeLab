#!/usr/bin/env python
"""Brief 5 Task 0 item 7 -- assemble density_baseline.json from the census
(item 1), the perf A/B (item 2), and the offline read-backs (items 3-6). Every
number carries its read-back source. READ-ONLY assembler; no world touch."""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def perf_pair(zone):
    a = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_asis/*/perf_standalone.json" % zone))[0]
    h = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_hidden/*/perf_standalone_hidden.json" % zone))[0]
    za = list(json.load(open(a))["zones"].values())[0]
    zh = list(json.load(open(h))["zones"].values())[0]

    def inst(csvp):
        with open(csvp, newline="") as f:
            rd = csv.DictReader(f)
            vals = [float(r["GPUSceneInstanceCount"]) for r in rd
                    if r.get("GPUSceneInstanceCount") not in (None, "")]
        tail = vals[-500:] if len(vals) > 500 else vals
        return round(statistics.mean(tail)) if tail else None
    ac = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_asis/*/%s.csv" % (zone, zone)))[0]
    hc = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_hidden/*/%s_hidden.csv" % (zone, zone)))[0]
    ia, ih = inst(ac), inst(hc)
    ga = za["stats_ms"]["GPUTime"]["p90"]
    gh = zh["stats_ms"]["GPUTime"]["p90"]
    return {
        "as_is_gpu_p90_ms": ga,
        "hidden_gpu_p90_ms": gh,
        "foliage_gpu_cost_ms": round(ga - gh, 3),
        "foliage_gpu_cost_pct": round(100.0 * (ga - gh) / ga, 1),
        "as_is_frametime_p90_ms": za["stats_ms"]["FrameTime"]["p90"],
        "window_s": za.get("window_s_measured"),
        "frames_total_as_is": za.get("frames_total"),
        "frames_total_hidden": zh.get("frames_total"),
        "gpuscene_instances_as_is": ia,
        "gpuscene_instances_hidden": ih,
        "gpuscene_instances_removed": (ia - ih) if (ia and ih) else None,
        "vram_peak_as_is_mib": (za.get("vram_mib") or {}).get("peak_mib"),
        "hide_readback": zh.get("foliage_hide_readback"),
        "station_ok_both": bool(za.get("station_ok") and zh.get("station_ok")),
    }


def main():
    census = json.load(open(os.path.join(REPO, "research/brief5/input/_census_stations.json")))

    baseline = {
        "_what": "Brief 5 Task 0 -- density and cost baseline the desk derives "
                 "Brief 5 from. Read-only against the world except the two perf "
                 "A/B pairs (which mutate nothing and restore state by process "
                 "exit).",
        "_date": "2026-09-19",
        "_world": "/Game/Alpine8K @ streaming.main_loading_range_cm 51200 (512 m)",
        "_commit_base": "678570b8 (groundwork); fixes applied after audit FIX",

        # ---- item 1: instance census ------------------------------------
        "item1_instance_census": {
            "_source": "research/brief5/scripts/density_census.py -> "
                       "research/brief5/input/_census_stations.json",
            "total_tree_instances": census["total_tree_instances"],
            "species_totals": census["species_totals"],
            "band_ring_radii_m": census["band_ring_radii_m"],
            "per_station_visible": {
                z: {"visible_total": census["stations"][z]["visible_total"],
                    "band_totals_visible": census["stations"][z]["band_totals_visible"],
                    "per_species": census["stations"][z]["per_species"]}
                for z in census["stations"]},
            "_headline": "Every tree species is culled INSIDE its detail band "
                         "(detail ring 238-1149 m vs the 512 m streaming-clamped "
                         "cull), so a live instance is only ever seen at DETAIL; "
                         "the shape and blob bands are carried entirely by HLOD. "
                         "treeline shows 0 visible live instances in the declared "
                         "frustum -- its 224 near in-cull trees are excluded by "
                         "azimuth (163) or elevation (61); the forest it renders "
                         "300 m-3 km is HLOD proxy beyond the 512 m cull.",
            "_frustum_caveat": census["_frustum_caveat"],
        },

        # ---- item 2: foliage cost attribution ---------------------------
        "item2_foliage_cost": {
            "_method": "standalone -game 4K (3840x2160), -noxgecontroller, "
                       "settle 60 s, 25 s steady-state p90 window. Two runs per "
                       "zone: as-is and foliage-hidden (foliage.DensityScale 0 + "
                       "grass.DensityScale 0 + grass.Enable 0 + ShowFlag.Foliage "
                       "0, cvars read back from the log). GPU p90 delta = the "
                       "foliage's GPU cost. Static geometry (landscape, "
                       "buildings, HLOD proxies) is present in BOTH runs and "
                       "cancels in the delta.",
            "_zone_choice": "treeline = the forest/tree case. plaza = the only "
                            "tree-free ground-cover zone (trees are "
                            "settlement-excluded there), used as the meadow / "
                            "ground-cover isolation -- NO sub-conifer-band "
                            "meadow exists on this world (land elevation min "
                            "95 m, p05 196 m; the lakes took the low ground), so "
                            "a pure no-tree meadow camera is not derivable.",
            "treeline": perf_pair("treeline"),
            "plaza_ground_cover": perf_pair("plaza"),
            "_headline": "Foliage GPU cost is small: treeline 0.116 ms (1.6%), "
                         "plaza ground-cover 0.286 ms (3.0%). Removing 10,860 "
                         "(treeline) / 126,386 (plaza) GPUScene instances barely "
                         "moved GPU p90 -- live foliage instancing is near-free "
                         "on this GPU. The forest's GPU weight lives in the HLOD "
                         "proxies (beyond the 512 m cull, NOT touched by the hide "
                         "levers) and the landscape, not in live instances.",
        },

        # ---- item 3: ground clutter -------------------------------------
        "item3_ground_clutter": {
            "_source": "recipes/alpine_8k.json foliage.species (pipeline rule 2 "
                       "source of truth); BACKLOG confirms rocks carry no "
                       "instances in Alpine8K.",
            "Meadow": {"system": "grass (landscape grass)", "cull_m": 50.0,
                       "density_per_10m2": 120.0, "layer": "Grass",
                       "placed_by": "landscape grass type GT_alpine_Meadow "
                                    "(procedural; NOT enumerable from a plan)",
                       "instance_count": "procedural -- generated per-frame "
                                         "within cull; not a fixed count. See "
                                         "item 2 GPUScene deltas for the live "
                                         "resident count near a station."},
            "Blueberry": {"system": "grass (landscape grass)", "cull_m": 45.0,
                          "density_per_10m2": 12.0, "layer": "Grass",
                          "placed_by": "landscape grass (procedural)",
                          "instance_count": "procedural"},
            "rocks_litter": "NONE placed in Alpine8K. rock_scatter in the recipe "
                            "is a talus deposition FIELD (a shared physical fact "
                            "read by the material scree mask), not placed meshes; "
                            "the FT_* rock/talus types carry zero instances "
                            "(BACKLOG 2026-08-16). No litter/deadfall species "
                            "exists in the recipe.",
        },

        # ---- item 4: PCG readiness --------------------------------------
        "item4_pcg_readiness": {
            "_source": "LandscapeLab/LandscapeLab.uproject Plugins; "
                       "UE_5.8/Engine/Plugins (read-only, standing rule 1).",
            "pcg_core_plugin": "PCG -- engine plugin, non-Experimental, enabled "
                               "by default in 5.8 (Engine/Plugins/PCG/PCG.uplugin)",
            "pcg_python_interop": "PCGPythonInterop ENABLED in the project",
            "procedural_vegetation_editor": "ProceduralVegetationEditor ENABLED "
                                            "in the project (Experimental engine "
                                            "plugin)",
            "biome_core": "PCGBiomeCore -- AVAILABLE in the engine "
                          "(Engine/Plugins/Experimental/PCGBiomeCore), NOT "
                          "enabled in the project",
            "biome_sample": "PCGBiomeSample -- AVAILABLE in the engine "
                            "(Experimental), NOT enabled in the project",
            "pcg_world_actor": "NOT verified this session -- PROJECT_STATE.json "
                               "is the stale pre-8K recovery (FT_Conifer only) "
                               "and carries no PCG block; a live editor read is "
                               "needed. Ryan's lever table records PCGWorldActor "
                               "presence + partition grid as READ-BACK.",
            "existing_graphs": "NONE authored for Alpine8K (no PCG graph asset in "
                               "the foliage pipeline; foliage is placed by "
                               "place_foliage + landscape grass, not PCG).",
            "r_pcg_cvars": "LIST ONLY (Ryan's lever table); none set by the "
                           "pipeline. Not captured this session (no editor).",
        },

        # ---- item 5: Nanite + LOD/imposter state ------------------------
        "item5_nanite_lod_imposter": {
            "_source": "Free/_measured/{pve_spruce,pn_spruce_forest,pn_blueberry,"
                       "fab_registry_KiteDemo}.json (measured); "
                       "recipes/alpine_8k.json species LODs; "
                       "scripts/read_nanite_state.py is the live read-back tool "
                       "of record (Ryan's lever table = READ-BACK).",
            "Conifer": {"mesh": "SM_PVE_Norway_Spruce_01_A", "nanite": True,
                        "lod0_triangles": "Nanite (no fixed LOD0; fallback proxy "
                                          "overstates, do not quote -- "
                                          "alpine_8k.json Conifer capsule note)",
                        "imposter": "Nanite auto-LOD; no billboard atlas"},
            "ConiferPine": {"mesh": "ScotsPineTall_01", "nanite": False,
                            "lod0_triangles": 27824,
                            "lods_screen_size": [0.5, 0.21, 0.088],
                            "imposter": "billboard atlas "
                                        "(ScotsPineTall_01_Atlas_Billboards_Tex), "
                                        "switches at the last LOD screen_size 0.088"},
            "SpruceSub": {"mesh": "spruce_half_01", "nanite": False,
                          "imposter": "octahedral imposter "
                                      "(half_01_imposter, MI_half_01_imposter_"
                                      "nowind in override_materials); mesh-baked "
                                      "switch ScreenSize needs an editor read"},
            "SpruceSapling": {"mesh": "spruce_small_05", "nanite": False,
                              "cull_m": 238.27,
                              "imposter": "small-mesh LODs; switch ScreenSize "
                                          "needs an editor read"},
            "Blueberry": {"mesh": "Blueberry_03 + 7 varieties", "nanite": False,
                          "imposter": "grass cards, cull 45 m"},
            "Meadow": {"mesh": "grass_medium_01 variants", "nanite": False,
                       "imposter": "grass cards, cull 50 m"},
            "_note": "Only Conifer (Norway Spruce) is Nanite; the other three "
                     "tree species are traditional LOD-chain meshes with "
                     "billboard/imposter far-LODs. Exact per-mesh imposter "
                     "ScreenSize and Conifer's Nanite fallback tris require a "
                     "read_nanite_state.py editor pass (not run this session -- "
                     "scope limits the editor to the two perf A/B pairs).",
        },

        # ---- item 6: HLOD ------------------------------------------------
        "item6_hlod": {
            "_source": "recipes/alpine_8k.json streaming; the perf CSV columns.",
            "instanced_hlod_loading_range_cm": 200000,
            "merged_hlod_loading_range_cm": 102400,
            "main_streaming_range_cm": 51200,
            "per_zone_gpu_share": "NOT ATTRIBUTABLE from the CSV -- there is no "
                                  "HLOD GPU-time column. The CSV carries "
                                  "GPUSceneInstanceCount, NaniteStreaming/* and "
                                  "SceneCulling/NumStaticInstances, but none "
                                  "isolates the HLOD proxy GPU cost. Stated as "
                                  "not attributable (item 6 fallback).",
            "_inference": "The treeline A/B (foliage delta 0.116 ms while the "
                          "rendered forest spans 300 m-3 km) implies most of the "
                          "treeline forest GPU cost is HLOD proxy + landscape, "
                          "since the hide levers remove live foliage/grass but "
                          "not HLOD -- but this is an inference from the delta, "
                          "not a measured HLOD share.",
        },
    }

    outp = os.path.join(REPO, "research/brief5/input/density_baseline.json")
    json.dump(baseline, open(outp, "w", encoding="utf-8"), indent=1)
    print("wrote", os.path.relpath(outp, REPO))
    for z in ("treeline", "plaza_ground_cover"):
        c = baseline["item2_foliage_cost"][z]
        print("  %-20s foliage %.3f ms (%.1f%%)  instances removed %s"
              % (z, c["foliage_gpu_cost_ms"], c["foliage_gpu_cost_pct"],
                 c["gpuscene_instances_removed"]))


if __name__ == "__main__":
    main()
