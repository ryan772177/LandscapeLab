#!/usr/bin/env python3
"""Brief 5 V2 -- the real hold cost, per pass. READ-ONLY analysis.

Post-hold as-is (3 runs/station, --csv-gpu-stats) vs the v3 pre-hold as-is.
forest_floor has a v3 baseline (forest_cost.json per_pass_delta_ms.table as_is_ms);
ring_v1 is a new station (no pre-hold baseline -> absolute per-pass only).
Positive control = Basepass + ShadowDepths + Prepass delta. min_detectable 0.016.
"""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
BASE = os.path.join(REPO, "_verify", "perf", "brief5_v2")
MIN_DET = 0.016
WINDOW = 1500


def rundir(tag):
    h = glob.glob(os.path.join(BASE, tag, "standalone_*"))
    return h[0] if h else None


def p90(tag):
    d = rundir(tag)
    j = [f for f in os.listdir(d) if f.startswith("perf_standalone") and f.endswith(".json")][0]
    return list(json.load(open(os.path.join(d, j)))["zones"].values())[0]["stats_ms"]["GPUTime"]["p90"]


def pass_medians(tag):
    d = rundir(tag)
    cf = [f for f in os.listdir(d) if f.endswith(".csv")][0]
    rows = list(csv.DictReader(open(os.path.join(d, cf), newline="")))
    cols = [c for c in rows[0].keys() if c.startswith("GPU/")]
    tail = rows[-WINDOW:]
    return {c.replace("GPU/", ""): statistics.median(
        [float(r[c]) for r in tail if r.get(c) not in (None, "")]) for c in cols}


def station(name, runs):
    tags = ["%s_r%d" % (name, r) for r in runs]
    ps = [p90(t) for t in tags]
    pm = [pass_medians(t) for t in tags]
    avg = {k: statistics.mean(d.get(k, 0) for d in pm) for k in pm[0]}
    return {"gpu_p90": [round(x, 3) for x in ps],
            "gpu_p90_mean": round(statistics.mean(ps), 3),
            "gpu_p90_sd": round(statistics.stdev(ps), 4),
            "pass_medians": avg}


def main():
    v3 = json.load(open(os.path.join(IN, "forest_cost.json")))
    v3_asis = {r["pass"]: r["as_is_ms"]
               for r in v3["per_pass_delta_ms"]["table"]}
    v3_p90 = v3["gpu_p90_ms"]["as_is"]["mean"]  # 11.048

    ff = station("forest_floor", (1, 2, 3))
    rg = station("ring_v1", (1, 2, 3))

    # forest_floor per-pass delta vs v3 as-is
    ff_delta = {}
    for k, v in ff["pass_medians"].items():
        if k in v3_asis:
            ff_delta[k] = round(v - v3_asis[k], 4)
    ff_delta_sorted = dict(sorted(ff_delta.items(), key=lambda kv: -abs(kv[1]))[:12])
    total_delta = round(ff["gpu_p90_mean"] - v3_p90, 3)

    out = {
        "_what": "Brief 5 V2 hold cost per pass. Post-hold as-is vs v3 pre-hold.",
        "_min_detectable_ms": MIN_DET,
        "_positive_control": "Basepass + ShadowDepths + Prepass delta (RHI "
                             "PrimitivesDrawn REJECTED: GPU-driven instanced "
                             "foliage draws indirect and never hits that counter).",
        "forest_floor": {
            "gpu_p90_post_hold": ff["gpu_p90_mean"], "gpu_p90_sd": ff["gpu_p90_sd"],
            "gpu_p90_v3_pre_hold": v3_p90,
            "total_delta_ms": total_delta,
            "total_delta_x_min_det": round(total_delta / MIN_DET, 1),
            "per_pass_delta_ms_top": ff_delta_sorted,
            "control_passes": {k: ff_delta.get(k) for k in
                               ("Basepass", "ShadowDepths", "Prepass",
                                "NaniteVisBuffer", "LumenReflections")},
        },
        "ring_v1": {
            "gpu_p90_post_hold": rg["gpu_p90_mean"], "gpu_p90_sd": rg["gpu_p90_sd"],
            "_no_pre_hold_baseline": "ring_v1 is a V1-derived station; it did not "
                                     "exist pre-hold, so no per-pass DELTA -- "
                                     "absolute pass medians only.",
            "pass_medians": {k: round(v, 4) for k, v in
                             sorted(rg["pass_medians"].items(),
                                    key=lambda kv: -kv[1])[:8]},
        },
    }
    # the disagreement guard is applied after V1 lands (needs the band verdict);
    # record the raw fact here.
    out["_forest_floor_delta_under_0_10ms"] = abs(total_delta) < 0.10
    out["_note_for_V5a"] = (
        "forest_floor hold delta = %+.3f ms (%s min_detectable). If V1 shows the "
        "band rendering GEOMETRY yet this is < 0.10 ms, that is 'V1 and V2 "
        "disagree' -- report both, do not reconcile." % (
            total_delta, out["forest_floor"]["total_delta_x_min_det"]))
    json.dump(out, open(os.path.join(IN, "t3_perf.json"), "w",
                        encoding="utf-8"), indent=1)
    print("forest_floor post-hold %.3f vs v3 %.3f = %+.3f ms (x%.1f)"
          % (ff["gpu_p90_mean"], v3_p90, total_delta,
             out["forest_floor"]["total_delta_x_min_det"]))
    print("control passes delta:", out["forest_floor"]["control_passes"])
    print("ring_v1 post-hold %.3f (sd %s)" % (rg["gpu_p90_mean"], rg["gpu_p90_sd"]))


if __name__ == "__main__":
    main()
