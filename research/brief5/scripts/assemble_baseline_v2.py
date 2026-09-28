#!/usr/bin/env python
"""Brief 5 overnight: fold items 1 (GPU passes), 2 (density sweep), 3 (editor
read-backs + HLOD A/B) into density_baseline.json, and add pointers to the
deputy outputs (4,5,6,7). READ-ONLY assembler; overwrites density_baseline.json
with the complete v2. No world touch."""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")


def _sidecar(zone, sub, fname):
    p = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_%s/*/%s"
                               % (zone, sub, fname)))[0]
    return list(json.load(open(p))["zones"].values())[0]


def _gpuscene(zone, sub):
    c = glob.glob(os.path.join(REPO, "_verify/perf/brief5_ab/%s_%s/*/%s*.csv"
                               % (zone, sub, zone)))[0]
    with open(c, newline="") as f:
        rd = csv.DictReader(f)
        v = [float(r["GPUSceneInstanceCount"]) for r in rd
             if r.get("GPUSceneInstanceCount") not in (None, "")]
    tail = v[-1500:] if len(v) > 1500 else v
    return round(statistics.mean(tail)) if tail else None


def gpu_passes(zone):
    c = glob.glob(os.path.join(
        REPO, "_verify/perf/brief5_ab/%s_gpustats/*/%s_gpustats.csv"
        % (zone, zone)))[0]
    with open(c, newline="") as f:
        rd = csv.DictReader(f)
        cols = [x for x in rd.fieldnames if x.startswith("GPU/")]
        rows = list(rd)
    tail = rows[-1500:] if len(rows) > 1500 else rows
    st = {x.replace("GPU/", ""): statistics.median(
          [float(r[x]) for r in tail if r.get(x) not in (None, "")])
          for x in cols}
    denom = sum(st.values())
    top = sorted(st.items(), key=lambda kv: -kv[1])[:8]
    return {
        "sum_of_passes_ms": round(denom, 3),
        "n_frames": len(tail),
        "top8": [{"pass": k, "ms": round(v, 3),
                  "pct_of_frame": round(100 * v / denom, 1)} for k, v in top],
    }


def main():
    b = json.load(open(os.path.join(IN, "density_baseline.json")))
    b["_v2"] = ("2026-09-20 overnight: items 1 (GPU passes), 2 (density sweep), "
                "3 (editor read-backs + HLOD A/B inconclusive) folded in; "
                "deputy outputs 4-7 pointered. "
                "[SUPERSEDED-IN-PART v3 2026-09-20: HLOD verdict reverted to "
                "INCONCLUSIVE (desk audit A1/A2); the ms/10k figures withdrawn "
                "as off-frustum population (audit A4). Numbers annotated, not "
                "deleted. See _v3.]")
    b["_v3"] = ("2026-09-20 v3 re-measure session. Corrections folded by this "
                "assembler: (1) item3.hlod_gpu_share is now READ from "
                "hlod_share.json (was hand-edited after assembly -- audit B2), "
                "verdict INCONCLUSIVE; (2) item2 per-10k figures WITHDRAWN "
                "(audit A4) and, where shown, COMPUTED from item2_foliage_cost "
                "inputs, not literals (audit B2); (3) audit notes A4/A5 added to "
                "the item2 blocks. v3 COMPLETE: task1_noise_floor + "
                "task3_forest_cost + task4_editor_census folded; "
                "item3.hlod_gpu_share verdict INCONCLUSIVE (2c/2d: composition "
                "measured, GPU share still open); BASELINE.md rebuilt as v3.")
    b["item2_foliage_cost"]["_audit_A4_A5_note"] = (
        "SUPERSEDED-IN-PART (v3). Audit A4: these deltas were measured where "
        "almost no trees are on screen (census visible live trees: treeline 0, "
        "plaza 903 of 185,385; plaza's 903 are mostly landscape grass, not "
        "trees). treeline 0.116 ms is the cost of OFF-frustum instances, not "
        "visible density. Audit A5: treeline 0.116 ms (one run per arm) is the "
        "same size as the D1/D2/D4 run-to-run spread (0.096 ms), so it is not "
        "distinguishable from noise; plaza 0.286 ms is ~3.6x the spread and "
        "survives. Task 3 re-measures forest cost at a forest_floor station "
        "(>=5000 in-frustum-in-cull trees) with a Task-1 noise floor beside it.")

    # item 1 -- per-pass GPU attribution (the 7.1 ms named)
    b["item1_gpu_passes"] = {
        "_source": "perf_standalone.py --csv-gpu-stats -> GPU/<pass> columns "
                   "(FRealtimeGPUProfiler); median over the p90 window.",
        "_method": "share = pass median / sum-of-passes (the profiler's own "
                   "accounting incl. Unaccounted). Measured GPU p90 beside it.",
        "treeline": dict(gpu_passes("treeline"),
                         measured_gpu_p90_ms=_sidecar(
                             "treeline", "gpustats",
                             "perf_standalone_gpustats.json")["stats_ms"]["GPUTime"]["p90"]),
        "plaza": dict(gpu_passes("plaza"),
                      measured_gpu_p90_ms=_sidecar(
                          "plaza", "gpustats",
                          "perf_standalone_gpustats.json")["stats_ms"]["GPUTime"]["p90"]),
        "_verdict": "treeline GPU is spent on atmosphere (VolumetricCloud), "
                    "Nanite raster (NaniteVisBuffer), shadows, TSR and post -- "
                    "the fixed frame cost -- NOT live foliage geometry (whose "
                    "hide-delta was 0.116 ms). plaza is NaniteVisBuffer-dominated "
                    "(buildings) plus shadows. Density is not where the frame "
                    "goes.",
    }

    # item 2 -- density sweep
    def sweep(zone, budget):
        d1 = _sidecar(zone, "asis", "perf_standalone.json")
        rows = [{"D": 1, "gpu_p90": d1["stats_ms"]["GPUTime"]["p90"],
                 "vram_peak_mib": (d1.get("vram_mib") or {}).get("peak_mib"),
                 "gpuscene": _gpuscene(zone, "asis"), "honoured": "n/a(default)"}]
        for D, tag in ((2, "d2"), (4, "d4")):
            z = _sidecar(zone, tag, "perf_standalone_%s.json" % tag)
            rows.append({"D": D, "gpu_p90": z["stats_ms"]["GPUTime"]["p90"],
                         "vram_peak_mib": (z.get("vram_mib") or {}).get("peak_mib"),
                         "gpuscene": _gpuscene(zone, tag),
                         "foliage_densityscale_readback":
                             z["foliage_hide_readback"].get("foliage.DensityScale"),
                         "honoured": z["foliage_hide_readback"].get("_honoured")})
        return {"budget_ms": budget, "budget_tol_ms": round(budget * 1.10, 2),
                "rows": rows}
    b["item2_density_sweep"] = {
        "_source": "perf_standalone.py --density-scale {1,2,4}",
        "treeline": sweep("treeline", 7.0),
        "plaza": sweep("plaza", 10.5),
        "_finding": "foliage.DensityScale read back at 2/4 (honoured on the "
                    "foliage lever) but GPUScene instances did NOT rise -- placed "
                    "HISM foliage is capped at its authored count, so "
                    "DensityScale>1 is a NO-OP on trees; grass showed no "
                    "measurable regen at these stations. NEITHER zone approaches "
                    "budget at any scale. Per audit B3, this lever cannot TEST a "
                    "denser forest at all (scalability down-lever, opt-in per "
                    "FoliageType Enable Density Scaling); it is not evidence "
                    "there is no budget crossing. grass.DensityScale bare-query "
                    "echo could not be parsed (rule-13 tool gap; safe direction).",
        "_audit_A5_note": "The 'instance-count wobble is streaming variance' "
                    "claim is unquantified: plaza GPUScene swung 196553 -> 167914 "
                    "-> 155054 (-21%) across nominally identical runs. If that is "
                    "noise, 'removed 126,386' carries tens of thousands of "
                    "uncertainty; if not, it is unexplained. Task 1 (noise floor) "
                    "measures GPUScene sd per zone before any sub-0.2 ms delta is "
                    "quoted.",
        "_marginal_cost_from_down_direction_WITHDRAWN": {
            "_WITHDRAWN": "audit A4: these are the GPU cost of instances that "
                     "were OFF the declared frustum. Census visible live trees: "
                     "treeline 0, plaza 903 (overwhelmingly landscape grass, not "
                     "trees) of 185,385. The treeline hide removed 10,860 "
                     "instances, none in the declared frustum. Different "
                     "populations, not comparable, NOT a marginal cost of "
                     "VISIBLE density. Superseded by Task 3 (forest_floor station, "
                     "ms/1000 in-frustum-in-cull trees).",
            "_computed_from_inputs_for_provenance_only": {
                "_formula": "foliage_gpu_cost_ms / gpuscene_instances_removed "
                            "* 10000 (COMPUTED here from item2_foliage_cost, not "
                            "a literal -- audit B2)",
                "treeline_ms_per_10k": round(
                    b["item2_foliage_cost"]["treeline"]["foliage_gpu_cost_ms"]
                    / b["item2_foliage_cost"]["treeline"]
                    ["gpuscene_instances_removed"] * 10000, 3),
                "plaza_ms_per_10k": round(
                    b["item2_foliage_cost"]["plaza_ground_cover"]
                    ["foliage_gpu_cost_ms"]
                    / b["item2_foliage_cost"]["plaza_ground_cover"]
                    ["gpuscene_instances_removed"] * 10000, 3),
            },
        },
    }

    # item 3 -- editor read-backs
    TLP_DATE = "2026-09-07"  # tree_lod_probe capture date (audit C: 13 days old)
    tlp = json.load(open(os.path.join(
        REPO, "_verify", "bench", TLP_DATE, "tree_lod_probe.json")))
    pcg = json.load(open(os.path.join(IN, "pcg_worldactor_probe.json")))
    # item3 HLOD block is READ from hlod_share.json (audit B2: it was hand-edited
    # after assembly in v2, so re-running silently reverted it). Now single-source.
    hlod = json.load(open(os.path.join(IN, "hlod_share.json")))
    b["item3_editor_readbacks"] = {
        "_source": "offscreen editor read-only pass (pcg_worldactor_probe.py, "
                   "tree_lod_probe.py); closed per R-EDITOR-CLOSE.",
        "_tree_lod_probe_date": TLP_DATE,
        "_tree_lod_probe_age_note": ("the per_mesh LOD/triangle read-backs below "
                   "are from the %s tree_lod_probe.json (audit C: 13 days old at "
                   "v3). Task 4a re-probes fresh at today's date." % TLP_DATE),
        "pcg_worldactor_present": pcg.get("pcg_worldactor_count", 0) > 0,
        "pcg_worldactor_count": pcg.get("pcg_worldactor_count"),
        "pcg_partition_grid_cm_cdo": (pcg.get("cdo_grid") or {}).get(
            "partition_grid_size"),
        "per_mesh": [{"species": m["species"], "nanite": m.get("nanite_enabled"),
                      "lod_count": m.get("lod_count"),
                      "screen_sizes": m.get("screen_sizes"),
                      "triangles_per_lod": m.get("triangles_per_lod")}
                     for m in tlp.get("meshes", [])],
        "conifer_nanite_fallback_tris": next(
            (m["triangles_per_lod"][0] for m in tlp.get("meshes", [])
             if m["species"] == "Conifer"), None),
        "hlod_gpu_share": {
            "_source": "READ from research/brief5/input/hlod_share.json "
                       "(single source, audit B2). Task 2 overwrites that file "
                       "with the positive-control re-measure.",
            "verdict": hlod.get("verdict", hlod.get("_verdict_v3")),
            "detail_file": "research/brief5/input/hlod_share.json",
            "reason": hlod.get("_verdict_reason", hlod.get("_verdict_v3_reason")),
            "composition_512m_to_2km": (hlod.get("_what_IS_measured_task2d_4c")
                                        or {}).get("answer_512m_to_2km"),
        },
    }

    # Task 1 (v3) -- run-to-run noise floor; min_detectable_ms per zone.
    nf_path = os.path.join(IN, "noise_floor.json")
    if os.path.exists(nf_path):
        nf = json.load(open(nf_path))
        b["task1_noise_floor"] = nf
        b["task1_noise_floor"]["_finding"] = (
            "As-is GPUSceneInstanceCount is DETERMINISTIC across 5 runs per zone "
            "(sd 0.0; treeline 57876, plaza 196553). This REFUTES audit A5's "
            "reading of the D1/D2/D4 -21%% GPUScene swing as 'streaming variance' "
            "-- as-is residency does not wobble; the swing was the D2/D4 "
            "grass.DensityScale lever regenerating landscape grass, not noise. "
            "GPU p90 min_detectable_ms: treeline %s, plaza %s. Every delta quoted "
            "in v3 carries 'x min_detectable' beside it; anything <1x is reported "
            "'not distinguishable'." % (
                nf["zones"]["treeline"]["min_detectable_ms"],
                nf["zones"]["plaza"]["min_detectable_ms"]))

    # Task 3 (v3) -- forest foliage cost where the forest is.
    fc_path = os.path.join(IN, "forest_cost.json")
    fs_path = os.path.join(IN, "forest_station.json")
    if os.path.exists(fc_path):
        fc = json.load(open(fc_path))
        b["task3_forest_cost"] = fc
        if os.path.exists(fs_path):
            b["task3_forest_cost"]["_station_derivation"] = \
                "research/brief5/input/forest_station.json"
        b["task3_forest_cost"]["_headline"] = (
            "At a real forest station (%d in-frustum-in-cull trees, the MAX "
            "achievable at 90 deg hFOV / 512 m cull -- 5000 is not reachable on "
            "this forest, %s), foliage costs %s ms GPU p90 (x%s min_detectable, "
            "distinguishable). It is spent mostly in LumenReflections + shadows "
            "+ base pass, NOT NaniteVisBuffer. ms per 1000 in-frustum-in-cull "
            "trees = %s (upper bound; the delta also removed grass and "
            "off-frustum trees). This REPLACES the withdrawn off-frustum ms/10k."
            % (fc["in_frustum_in_cull_trees"],
               fc["in_frustum_in_cull_meets_5000_target"],
               fc["gpu_p90_ms"]["foliage_delta_ms"],
               fc["foliage_delta_x_min_detectable"],
               fc["ms_per_1000_in_frustum_in_cull_trees"]))

    # Task 4 (v3) -- editor read-only census + switch distances.
    ec_path = os.path.join(IN, "editor_census_v3.json")
    sd_path = os.path.join(IN, "switch_distances.json")
    if os.path.exists(ec_path) or os.path.exists(sd_path):
        t4 = {"_source": "brief5_editor_census.py (offscreen read-only, closed "
                         "per R-EDITOR-CLOSE) + switch_distances.py (offline)."}
        if os.path.exists(ec_path):
            ec = json.load(open(ec_path))
            t4["hlod_layers"] = ec.get("hlod_layers")
            t4["foliage_types"] = ec.get("foliage_types")
            t4["per_mesh_nanite"] = ec.get("per_mesh_nanite")
            t4["project_nanite_foliage_enabled"] = (
                "True (r.Nanite.Foliage=True, DefaultEngine.ini:63; editor "
                "get_default_object read-back UNKNOWN -- class not exposed to "
                "Python, config is the instrument)")
            t4["hlod_cell_distance_m"] = ec.get("hlod_cell_distance_m")
        if os.path.exists(sd_path):
            sd = json.load(open(sd_path))
            t4["switch_distances"] = sd
            t4["_switch_finding"] = (
                "Every LOD/billboard/imposter switch happens ABOVE the 40 px "
                "detail floor: ConiferPine -> 32-tri billboard at 127.8 m (332 px "
                "tall), SpruceSub -> 6-tri imposter at 87.5 m (367 px), sapling "
                "lowest LOD at 49.1 m (177 px). So 'seen only at DETAIL' (a pixel "
                "band) hides that the MESH representation drops to cards while the "
                "tree is still hundreds of px tall (audit A8, quantified).")
            t4["_recipe_vs_asset_finding"] = (
                "ConiferPine recipe LODs [0.5,0.21,0.088] != asset "
                "[1.50,0.336,0.238,0.168]: 3 vs 4 LODs, billboard at asset ss "
                "0.168 (127.8 m) vs the recipe's 0.088 (~2x farther). The built "
                "asset's LOD chain is not the recipe's spec.")
        t4["_enable_density_scaling_all_false"] = (
            "All four FoliageTypes have enable_density_scaling=False -> confirms "
            "audit B3: foliage.DensityScale (a scalability lever, opt-in per type) "
            "has NO effect on these trees. The density lever cannot test them.")
        b["task4_editor_census"] = t4

    b["_deputy_outputs"] = {
        "item4_reference_coverage": "research/brief5/input/reference_coverage.json",
        "item5_dolly_manifest": "research/brief5/input/dolly_manifest.json",
        "item6_pcg_notes": "research/brief5/PCG_NOTES.md",
        "item7_replay_inventory": "research/brief5/input/replay_inventory.json",
    }

    json.dump(b, open(os.path.join(IN, "density_baseline.json"), "w",
                      encoding="utf-8"), indent=1)
    print("density_baseline.json v2 written")
    for z in ("treeline", "plaza"):
        p = b["item1_gpu_passes"][z]
        print("  %s top pass: %s %.1f%%  (sum %.2f ms, p90 %.2f)"
              % (z, p["top8"][0]["pass"], p["top8"][0]["pct_of_frame"],
                 p["sum_of_passes_ms"], p["measured_gpu_p90_ms"]))


if __name__ == "__main__":
    main()
