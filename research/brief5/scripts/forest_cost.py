#!/usr/bin/env python
"""Brief 5 v3 Task 3 -- forest foliage GPU cost WHERE THE FOREST IS.

READ-ONLY analysis of 3 as-is + 3 foliage-hidden -game runs at the derived
forest_floor station (research/brief5/input/forest_station.json), all
--csv-gpu-stats. No world touch.

Reports (audit A4/A5/A6):
  * GPU p90 per arm (mean/sd), the foliage delta, a forest min_detectable_ms
    (2 x sd of the as-is p90), and delta / min_detectable.
  * The PER-PASS GPU delta table (as-is median - hidden median per GPU/<pass>),
    which is the answer to "where do trees cost".
  * ms per 1000 in-frustum-in-cull trees (census denominator 1844) -- this
    replaces the withdrawn off-frustum ms/10k.
  * 3c per-species hide: stated NOT AVAILABLE in -game (no process-local
    per-FoliageType lever; the hide is all-foliage). No lever invented.
"""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
BASE = os.path.join(REPO, "_verify", "perf", "brief5_forest")
WINDOW = 1500


def _rundir(arm):
    return glob.glob(os.path.join(BASE, arm, "standalone_*"))[0]


def _sidecar(arm):
    d = _rundir(arm)
    j = [f for f in os.listdir(d) if f.startswith("perf_standalone") and f.endswith(".json")][0]
    return list(json.load(open(os.path.join(d, j)))["zones"].values())[0]


def _csv(arm):
    d = _rundir(arm)
    return os.path.join(d, [f for f in os.listdir(d) if f.endswith(".csv")][0])


def gpu_p90(arm):
    return _sidecar(arm)["stats_ms"]["GPUTime"]["p90"]


def gpuscene(arm):
    rows = list(csv.DictReader(open(_csv(arm), newline="")))[-WINDOW:]
    v = [float(r["GPUSceneInstanceCount"]) for r in rows
         if r.get("GPUSceneInstanceCount") not in (None, "")]
    return round(statistics.mean(v)) if v else None


def pass_medians(arm):
    """median per GPU/<pass> over the last WINDOW frames of each of the arm's
    runs, averaged across runs."""
    arms = [arm] + ["%s_r2" % arm, "%s_r3" % arm]
    per_run = []
    cols = None
    for a in arms:
        rows = list(csv.DictReader(open(_csv(a), newline="")))
        cols = [c for c in rows[0].keys() if c.startswith("GPU/")]
        tail = rows[-WINDOW:]
        med = {c: statistics.median([float(r[c]) for r in tail
                                     if r.get(c) not in (None, "")]) for c in cols}
        per_run.append(med)
    return {c: statistics.mean(r[c] for r in per_run) for c in cols}


def stats(vals):
    return {"n": len(vals), "values": [round(v, 3) for v in vals],
            "mean": round(statistics.mean(vals), 3),
            "sd": round(statistics.stdev(vals), 4) if len(vals) > 1 else None}


def main():
    fs = json.load(open(os.path.join(IN, "forest_station.json")))
    n_trees = fs["in_frustum_in_cull_total"]

    asis = [gpu_p90("asis"), gpu_p90("asis_r2"), gpu_p90("asis_r3")]
    hidden = [gpu_p90("hidden"), gpu_p90("hidden_r2"), gpu_p90("hidden_r3")]
    a_st, h_st = stats(asis), stats(hidden)
    delta = round(a_st["mean"] - h_st["mean"], 3)
    min_det = round(2 * a_st["sd"], 4) if a_st["sd"] else None
    x_min_det = round(delta / min_det, 1) if min_det else None

    gs_asis = gpuscene("asis")
    gs_hidden = gpuscene("hidden")
    gs_removed = gs_asis - gs_hidden

    pa = pass_medians("asis")
    ph = pass_medians("hidden")
    pass_delta = sorted(((c.replace("GPU/", ""), round(pa[c] - ph.get(c, 0.0), 4),
                          round(pa[c], 4), round(ph.get(c, 0.0), 4))
                         for c in pa), key=lambda t: -abs(t[1]))

    ms_per_1000 = round(delta / (n_trees / 1000.0), 4) if n_trees else None

    out = {
        "_what": "Brief 5 v3 Task 3: forest foliage GPU cost at the derived "
                 "forest_floor station (3 as-is + 3 hidden -game runs, "
                 "--csv-gpu-stats).",
        "station": fs["camera"],
        "in_frustum_in_cull_trees": n_trees,
        "in_frustum_in_cull_meets_5000_target": fs["meets_5000_target"],
        "_target_note": fs.get("_target_note"),
        "gpu_p90_ms": {"as_is": a_st, "hidden": h_st, "foliage_delta_ms": delta},
        "forest_min_detectable_ms": min_det,
        "_forest_min_detectable_def": "2 x sd(as-is GPU p90) at this station "
                                      "(its own noise floor; Task 1 measured only "
                                      "treeline/plaza).",
        "foliage_delta_x_min_detectable": x_min_det,
        "foliage_delta_distinguishable": (x_min_det is not None and x_min_det >= 1.0),
        "gpuscene": {"as_is": gs_asis, "hidden": gs_hidden,
                     "removed_by_hide": gs_removed,
                     "_note": "removed = trees in the 512 m streaming disc (all "
                              "directions) + landscape grass, NOT just the "
                              "in-frustum trees. Deterministic across runs "
                              "(sd 0 -- same as Task 1)."},
        "per_pass_delta_ms": {
            "_method": "as-is median - hidden median per GPU/<pass>, median over "
                       "the last %d frames of each run, averaged over 3 runs. "
                       "Positive = the pass got cheaper when foliage was hidden "
                       "(i.e. that is where the trees cost)." % WINDOW,
            "table": [{"pass": p, "delta_ms": dd, "as_is_ms": av, "hidden_ms": hv}
                      for p, dd, av, hv in pass_delta[:14]],
        },
        "ms_per_1000_in_frustum_in_cull_trees": ms_per_1000,
        "_ms_per_1000_note": ("delta / (in_frustum_in_cull/1000). ATTRIBUTES the "
                              "whole foliage delta (which also removed grass and "
                              "off-frustum in-cull trees) to the %d in-frustum "
                              "trees, so it is an UPPER BOUND on per-visible-tree "
                              "cost. Replaces the withdrawn off-frustum ms/10k. "
                              "Carries x%s min_detectable." % (n_trees, x_min_det)),
        "per_species_hide_3c": "NOT AVAILABLE in -game. foliage.DensityScale 0 / "
                               "ShowFlag.Foliage 0 hide ALL foliage; there is no "
                               "process-local per-FoliageType console lever to "
                               "isolate the Nanite spruce from the card-LOD "
                               "species. Per the queue: stated, not invented. A "
                               "per-species split needs an editor actor-level "
                               "hide (Task 4 reads per-species representation "
                               "instead).",
    }
    p = os.path.join(IN, "forest_cost.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("forest_floor as-is p90 %.3f (sd %s) hidden %.3f (sd %s) delta %.3f  "
          "min_det %.4f  x%.1f  distinguishable %s"
          % (a_st["mean"], a_st["sd"], h_st["mean"], h_st["sd"], delta,
             min_det, x_min_det, out["foliage_delta_distinguishable"]))
    print("GPUScene as-is %d hidden %d removed %d" % (gs_asis, gs_hidden, gs_removed))
    print("ms per 1000 in-frustum-in-cull trees (%d): %.4f" % (n_trees, ms_per_1000))
    print("top passes by |delta| (ms):")
    for p2, dd, av, hv in pass_delta[:8]:
        print("   %-26s %+.4f  (as-is %.4f hidden %.4f)" % (p2, dd, av, hv))
    print("wrote", os.path.relpath(os.path.join(IN, "forest_cost.json"), REPO))


if __name__ == "__main__":
    main()
