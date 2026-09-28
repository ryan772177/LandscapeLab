#!/usr/bin/env python
"""Brief 5 v3 Task 1 -- run-to-run NOISE FLOOR at treeline and plaza.

READ-ONLY analysis of as-is `-game` perf runs (the runs themselves were launched
by perf_standalone.py; this only reads their sidecars + CSVs). No world touch.

Five as-is samples per zone, all same-build, existing settle 60 s / window 25 s:
  * 2 on disk (the D1 as-is run and the item-1 gpustats run -- both no levers;
    every run sets r.GPUCsvStatsEnable 1, so gpustats differs only by emitting
    the GPU/<pass> columns -- GPU p90 7.229 vs 7.169 at treeline confirms no
    systematic overhead).
  * 3 fresh as-is runs launched this session (_verify/perf/brief5_noise/*_r{1,2,3}).

The D2/D4 density-sweep runs are NOT used: they set grass.DensityScale, which
regenerates landscape grass and moves GPUSceneInstanceCount, so they are not
as-is samples (that is the confound behind audit A5's -21% GPUScene swing).

Per zone: GPU p90 mean/sd/range and GPUSceneInstanceCount mean/sd/range across
the 5 runs. min_detectable_ms = 2 x sd(GPU p90). If the GPUScene sd exceeds 5 %
of its mean, that is flagged as a finding for Task 3 to resolve first.
"""
import csv
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# (sidecar path, csv path) for each as-is sample, per zone. Relative to REPO.
SAMPLES = {
    "treeline": [
        ("_verify/perf/brief5_ab/treeline_asis/standalone_2026-09-19/perf_standalone.json",
         "_verify/perf/brief5_ab/treeline_asis/standalone_2026-09-19/treeline.csv"),
        ("_verify/perf/brief5_ab/treeline_gpustats/standalone_2026-09-20/perf_standalone_gpustats.json",
         "_verify/perf/brief5_ab/treeline_gpustats/standalone_2026-09-20/treeline_gpustats.csv"),
        ("_verify/perf/brief5_noise/treeline_r1/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/treeline_r1/standalone_2026-09-20/treeline.csv"),
        ("_verify/perf/brief5_noise/treeline_r2/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/treeline_r2/standalone_2026-09-20/treeline.csv"),
        ("_verify/perf/brief5_noise/treeline_r3/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/treeline_r3/standalone_2026-09-20/treeline.csv"),
    ],
    "plaza": [
        ("_verify/perf/brief5_ab/plaza_asis/standalone_2026-09-19/perf_standalone.json",
         "_verify/perf/brief5_ab/plaza_asis/standalone_2026-09-19/plaza.csv"),
        ("_verify/perf/brief5_ab/plaza_gpustats/standalone_2026-09-20/perf_standalone_gpustats.json",
         "_verify/perf/brief5_ab/plaza_gpustats/standalone_2026-09-20/plaza_gpustats.csv"),
        ("_verify/perf/brief5_noise/plaza_r1/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/plaza_r1/standalone_2026-09-20/plaza.csv"),
        ("_verify/perf/brief5_noise/plaza_r2/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/plaza_r2/standalone_2026-09-20/plaza.csv"),
        ("_verify/perf/brief5_noise/plaza_r3/standalone_2026-09-20/perf_standalone.json",
         "_verify/perf/brief5_noise/plaza_r3/standalone_2026-09-20/plaza.csv"),
    ],
}
WINDOW_FRAMES = 1500   # same tail the assembler uses for GPUSceneInstanceCount


def gpu_p90(sidecar_rel):
    p = os.path.join(REPO, sidecar_rel)
    d = json.load(open(p, encoding="utf-8"))
    # sidecar holds a single zone under zones{}; take it
    zrec = list(d["zones"].values())[0]
    return zrec["stats_ms"]["GPUTime"]["p90"]


def gpuscene_mean(csv_rel):
    p = os.path.join(REPO, csv_rel)
    with open(p, newline="") as f:
        rd = csv.DictReader(f)
        if "GPUSceneInstanceCount" not in (rd.fieldnames or []):
            return None
        v = [float(r["GPUSceneInstanceCount"]) for r in rd
             if r.get("GPUSceneInstanceCount") not in (None, "")]
    tail = v[-WINDOW_FRAMES:] if len(v) > WINDOW_FRAMES else v
    return round(statistics.mean(tail)) if tail else None


def stats(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return {"n": len(vals), "values": vals, "mean": vals[0] if vals else None,
                "sd": None, "min": min(vals) if vals else None,
                "max": max(vals) if vals else None, "range": None}
    return {
        "n": len(vals),
        "values": vals,
        "mean": round(statistics.mean(vals), 3),
        "sd": round(statistics.stdev(vals), 3),
        "min": min(vals),
        "max": max(vals),
        "range": round(max(vals) - min(vals), 3),
    }


def main():
    out = {
        "_what": "Brief 5 v3 Task 1: run-to-run noise floor at treeline and plaza "
                 "from 5 as-is -game runs each (same build, settle 60 s, "
                 "window 25 s).",
        "_method": "GPU p90 = each run's stats_ms.GPUTime.p90. "
                   "GPUSceneInstanceCount = mean over the last %d frames of each "
                   "run's CSV. min_detectable_ms = 2 x sd(GPU p90 across runs)."
                   % WINDOW_FRAMES,
        "_sample_provenance": "2 on-disk as-is runs (D1 asis + item-1 gpustats) + "
                              "3 fresh as-is runs (brief5_noise/*_r1..r3). D2/D4 "
                              "excluded (grass.DensityScale confound).",
        "window_frames": WINDOW_FRAMES,
        "zones": {},
    }
    for zone, samples in SAMPLES.items():
        gp = [gpu_p90(s) for s, _ in samples]
        gs = [gpuscene_mean(c) for _, c in samples]
        gp_stats = stats(gp)
        gs_stats = stats(gs)
        min_det = round(2 * gp_stats["sd"], 3) if gp_stats["sd"] is not None else None
        gs_cov = (round(100.0 * gs_stats["sd"] / gs_stats["mean"], 2)
                  if gs_stats["sd"] and gs_stats["mean"] else None)
        out["zones"][zone] = {
            "gpu_p90_ms": gp_stats,
            "gpuscene_instance_count": gs_stats,
            "min_detectable_ms": min_det,
            "_min_detectable_def": "2 x sd(GPU p90). A delta below this is NOT "
                                   "distinguishable from run-to-run noise.",
            "gpuscene_sd_pct_of_mean": gs_cov,
            "gpuscene_sd_exceeds_5pct": (gs_cov is not None and gs_cov > 5.0),
            "sample_sidecars": [s for s, _ in samples],
        }
    p = os.path.join(REPO, "research", "brief5", "input", "noise_floor.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    for zone, z in out["zones"].items():
        g = z["gpu_p90_ms"]
        s = z["gpuscene_instance_count"]
        print("%-9s GPU p90 mean %.3f sd %.3f range %.3f  min_det %.3f | "
              "GPUScene mean %s sd %s (%.2f%% %s)"
              % (zone, g["mean"], g["sd"], g["range"], z["min_detectable_ms"],
                 s["mean"], s["sd"], z["gpuscene_sd_pct_of_mean"] or 0.0,
                 "OVER-5%%" if z["gpuscene_sd_exceeds_5pct"] else "ok"))
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
