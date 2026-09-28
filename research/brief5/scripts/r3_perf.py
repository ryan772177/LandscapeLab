#!/usr/bin/env python3
"""Brief 5 REPAIR R3 -- what the PERSISTED hold costs, and whether it took at
runtime. READ-ONLY analysis of post-persist -game runs.

R2's coloration was contaminated and the isolated read was scene-defeated, so R3
is the decisive UNCONTAMINATED runtime control (operator ruling): a hold that is
LIVE at runtime pushes 128-512 m card-band trees from a 6/32-tri card to their
geometry LOD, which MUST cost something in Basepass + ShadowDepths + Prepass. The
blunt arm-B force (all foliage LOD2) was +2.9 ms; the targeted hold is smaller but
must clear the forest_floor noise floor (min_detectable 0.016 ms) if it took.

  forest_floor delta vs the v3 PRE-hold baseline (forest_cost.json as_is):
    Basepass+ShadowDepths+Prepass rise > 0.016 ms  => HOLD TOOK AT RUNTIME
    within noise                                    => PERSISTED ON DISK, NO
                                                       RUNTIME EFFECT (reopens the
                                                       DDC/proxy question) -- STOP
  Then rule forest_floor p90 vs R5-1 (12.5 ms): <= => under budget (record margin);
  > => over, T4 (rungs) back on the list (list, do not run).

Reads _verify/perf/brief5_r3/{forest_floor,ring_v1}_r{1,2,3}/standalone_*/. Reuses
t3_perf's p90 + pass_medians readers.
"""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
BASE = os.path.join(REPO, "_verify", "perf", "brief5_r3")
MIN_DET = 0.016
R5_1_BUDGET = 12.5
WINDOW = 1500


def rundir(tag):
    h = glob.glob(os.path.join(BASE, tag, "standalone_*"))
    return h[0] if h else None


def p90(tag):
    d = rundir(tag)
    j = [f for f in os.listdir(d) if f.startswith("perf_standalone")
         and f.endswith(".json")][0]
    return list(json.load(open(os.path.join(d, j)))["zones"].values())[0][
        "stats_ms"]["GPUTime"]["p90"]


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
    missing = [t for t in tags if rundir(t) is None]
    if missing:
        return {"error": "missing run dirs: %s" % missing}
    ps = [p90(t) for t in tags]
    pm = [pass_medians(t) for t in tags]
    avg = {k: statistics.mean(d.get(k, 0) for d in pm) for k in pm[0]}
    return {"gpu_p90": [round(x, 3) for x in ps],
            "gpu_p90_mean": round(statistics.mean(ps), 3),
            "gpu_p90_sd": round(statistics.stdev(ps), 4) if len(ps) > 1 else 0.0,
            "pass_medians": avg}


def main():
    v3 = json.load(open(os.path.join(IN, "forest_cost.json")))
    v3_asis = {r["pass"]: r["as_is_ms"] for r in v3["per_pass_delta_ms"]["table"]}
    v3_p90 = v3["gpu_p90_ms"]["as_is"]["mean"]

    ff = station("forest_floor", (1, 2, 3))
    rg = station("ring_v1", (1, 2, 3))
    out = {"_what": "Brief 5 R3 -- PERSISTED hold cost + runtime control.",
           "_min_detectable_ms": MIN_DET, "_r5_1_budget_ms": R5_1_BUDGET,
           "_baseline": "v3 pre-hold forest_cost.json (as_is), same station, "
           "--csv-gpu-stats.",
           "forest_floor": ff, "ring_v1": rg}

    if "error" in ff:
        out["verdict"] = "INCOMPLETE: " + ff["error"]
        _write(out)
        print(out["verdict"])
        return

    # per-pass delta vs v3 pre-hold
    ff_delta = {k: round(v - v3_asis[k], 4) for k, v in ff["pass_medians"].items()
                if k in v3_asis}
    control = {k: ff_delta.get(k) for k in ("Basepass", "ShadowDepths", "Prepass",
                                            "NaniteVisBuffer", "LumenReflections")}
    ctrl_sum = round(sum(v for v in (ff_delta.get("Basepass"),
                                     ff_delta.get("ShadowDepths"),
                                     ff_delta.get("Prepass")) if v is not None), 4)
    total_delta = round(ff["gpu_p90_mean"] - v3_p90, 3)
    out["forest_floor_delta_vs_prehold"] = {
        "per_pass_top": dict(sorted(ff_delta.items(), key=lambda kv: -abs(kv[1]))[:12]),
        "control_passes": control,
        "basepass+shadowdepths+prepass_ms": ctrl_sum,
        "control_x_min_detectable": round(ctrl_sum / MIN_DET, 1),
        "gpu_p90_total_delta_ms": total_delta,
        "gpu_p90_total_x_min_detectable": round(total_delta / MIN_DET, 1)}

    # RUNTIME CONTROL verdict
    took = ctrl_sum > MIN_DET
    out["runtime_control"] = {
        "instrument": "Basepass+ShadowDepths+Prepass delta vs v3 pre-hold",
        "value_ms": ctrl_sum, "noise_floor_ms": MIN_DET,
        "verdict": ("HOLD TOOK AT RUNTIME (control rise %.4f ms = %.1fx the noise "
                    "floor)" % (ctrl_sum, ctrl_sum / MIN_DET)) if took else
                   ("PERSISTED ON DISK, NO RUNTIME EFFECT (control %.4f ms within "
                    "the %.3f ms noise floor) -- reopens the DDC/proxy question; "
                    "STOP" % (ctrl_sum, MIN_DET))}

    # R5-1 budget ruling (only meaningful if the hold took)
    ff_p90 = ff["gpu_p90_mean"]
    out["r5_1_ruling"] = {
        "forest_floor_p90_ms": ff_p90, "budget_ms": R5_1_BUDGET,
        "under_budget": ff_p90 <= R5_1_BUDGET,
        "margin_ms": round(R5_1_BUDGET - ff_p90, 3),
        "if_over": ("T4 (rungs) back on the list with derived_ladder.json "
                    "target_tris -- LIST, do not run, do not revert the hold")}
    out["verdict"] = out["runtime_control"]["verdict"]
    _write(out)
    print("forest_floor post-persist p90 %.3f vs v3 pre-hold %.3f = %+.3f ms"
          % (ff_p90, v3_p90, total_delta))
    print("control (Basepass+ShadowDepths+Prepass) delta = %+.4f ms (%.1fx noise)"
          % (ctrl_sum, ctrl_sum / MIN_DET))
    print("VERDICT:", out["verdict"])
    print("R5-1:", "UNDER" if out["r5_1_ruling"]["under_budget"] else "OVER",
          "budget, margin %.3f ms" % out["r5_1_ruling"]["margin_ms"])


def _write(out):
    json.dump(out, open(os.path.join(IN, "r3_perf.json"), "w", encoding="utf-8"),
              indent=1)


if __name__ == "__main__":
    main()
