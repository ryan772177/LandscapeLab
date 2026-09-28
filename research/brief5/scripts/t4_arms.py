#!/usr/bin/env python
"""Brief 5 T4 step 2 -- shadow/cull cvar ladder at forest_floor (Ryan option 2).

READ-ONLY -game: cvar levers via perf_standalone --set-cvar (startup -ExecCmds).
No editor, no .ini/.uasset writes. World stays at pre-density-daylight (as-is,
185k trees). Each arm is measured vs the SAME as-is baseline (3 runs), never vs
another arm.

Modes:
  --baseline                         3 as-is runs at forest_floor -> t4_baseline.json
                                     (GPU p90 + per-pass + the A/A min_detectable check)
  --arm A --cvar "r.Shadow.RadiusThreshold" --values 0.03,0.06,0.1 --default 0.01
                                     3 runs per value -> t4_arm_A.json (delta vs
                                     baseline, x min_det, per-pass, verdict)

Per-pass = median GPU/<pass> over the last WINDOW frames of the --csv-gpu-stats
CSV (same method as d4_model_error). GPU p90 = stats_ms.GPUTime.p90 (median of 3).
Positive control (arm): ShadowDepths (or the arm's target pass) must move
>= 3 x min_det on at least one rung, else the arm is INCONCLUSIVE, not negligible.
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
BR = os.path.join(REPO, "research", "brief5")
T4 = os.path.join(BR, "t4")
PY = sys.executable
FF_STATION = os.path.join(BR, "input", "forest_station.json")
PASSES = ["Basepass", "ShadowDepths", "LumenReflections", "Prepass",
          "NaniteVisBuffer"]
WINDOW = 1500
MIN_DET_FF = 0.016   # BASELINE v3 forest floor; re-confirmed by the A/A here


def newest_perf_dir():
    return sorted(glob.glob(os.path.join(REPO, "_verify", "perf",
                                         "standalone_*")))[-1]


def run_once(tag, cvar=None):
    cmd = [PY, os.path.join(SCRIPTS, "perf_standalone.py"), "--noxgecontroller",
           "--csv-gpu-stats", "--station-json", FF_STATION,
           "--station-name", "forest_floor", "--tag", tag]
    if cvar:
        cmd += ["--set-cvar", cvar]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
    print("  run %s rc %d (%.0fs)" % (tag, r.returncode, time.time() - t0),
          flush=True)
    return r.returncode


def read_run(tag):
    """(gpu_p90, {pass: ms}) for the run tagged `tag`."""
    od = newest_perf_dir()
    js = sorted(glob.glob(os.path.join(od, "*%s*.json" % tag)))
    gpu = None
    for f in reversed(js):
        d = json.load(open(f, encoding="utf-8"))
        z = (d.get("zones") or {}).get("forest_floor")
        if z:
            gpu = (z.get("stats_ms") or {}).get("GPUTime", {}).get("p90")
            break
    # per-pass from the CSV
    cs = sorted(glob.glob(os.path.join(od, "forest_floor_%s*.csv" % tag)))
    pp = {p: None for p in PASSES}
    if cs:
        rows = list(csv.DictReader(open(cs[-1], newline="")))
        tail = rows[-WINDOW:] if len(rows) > WINDOW else rows
        for p in PASSES:
            vals = []
            for r in tail:
                v = r.get("GPU/" + p)
                if v not in (None, ""):
                    try:
                        vals.append(float(v))
                    except ValueError:
                        pass
            if vals:
                vals.sort()
                pp[p] = vals[len(vals) // 2]
    return gpu, pp


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    return None if not xs else (xs[len(xs) // 2] if len(xs) % 2
                                else 0.5 * (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]))


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def do_baseline(runs):
    os.makedirs(T4, exist_ok=True)
    gpus, pps = [], []
    for i in range(1, runs + 1):
        if run_once("t4base_r%d" % i) != 0:
            print("baseline run %d failed" % i)
        g, pp = read_run("t4base_r%d" % i)
        gpus.append(g)
        pps.append(pp)
    per_pass = {p: med([pp[p] for pp in pps]) for p in PASSES}
    aa_sd = sd(gpus)
    aa_min_det = (2 * aa_sd) if aa_sd is not None else None
    out = {"_what": "T4 step 2 forest_floor as-is baseline (A/A).",
           "runs": runs, "gpu_p90_runs": gpus, "gpu_p90_median": med(gpus),
           "per_pass_median": per_pass,
           "AA_sd_ms": aa_sd, "AA_min_detectable_ms": aa_min_det,
           "min_det_ref_0.016": MIN_DET_FF,
           "AA_confirms_min_det": (aa_min_det is not None
                                   and aa_min_det <= MIN_DET_FF * 2.5)}
    json.dump(out, open(os.path.join(T4, "t4_baseline.json"), "w",
                        encoding="utf-8"), indent=1)
    print("baseline GPU p90 median %.3f; A/A min_det %.4f (ref 0.016)"
          % (med(gpus) or -1, aa_min_det or -1))
    return out


def do_arm(name, cvar, values, default, target_pass):
    base = json.load(open(os.path.join(T4, "t4_baseline.json"), encoding="utf-8"))
    b_gpu = base["gpu_p90_median"]
    b_pp = base["per_pass_median"]
    # Use the MEASURED A/A noise floor for every verdict (rule 13), not the
    # 0.016 reference -- the A/A on this build gave a larger floor.
    global MIN_DET_FF
    MIN_DET_FF = base.get("AA_min_detectable_ms") or MIN_DET_FF
    rungs = []
    for val in values:
        gpus, pps = [], []
        for i in range(1, 4):
            tag = "t4%s_%s_r%d" % (name, str(val).replace(".", "p"), i)
            if run_once(tag, cvar="%s %s" % (cvar, val)) != 0:
                print("arm %s val %s run %d failed" % (name, val, i))
            g, pp = read_run(tag)
            gpus.append(g)
            pps.append(pp)
        gm = med(gpus)
        ppm = {p: med([pp[p] for pp in pps]) for p in PASSES}
        gpu_gain = (b_gpu - gm) if (b_gpu is not None and gm is not None) else None
        tgt_delta = ((b_pp.get(target_pass) or 0) - (ppm.get(target_pass) or 0)
                     if ppm.get(target_pass) is not None else None)
        rungs.append({
            "value": val, "gpu_p90_median": gm, "gpu_p90_runs": gpus,
            "gpu_gain_vs_baseline_ms": (round(gpu_gain, 4) if gpu_gain is not None else None),
            "gpu_gain_x_min_det": (round(gpu_gain / MIN_DET_FF, 1) if gpu_gain is not None else None),
            "per_pass_median": {p: round(ppm[p], 4) if ppm[p] is not None else None for p in PASSES},
            "target_pass": target_pass,
            "target_pass_delta_ms": (round(tgt_delta, 4) if tgt_delta is not None else None),
            "target_pass_delta_x_min_det": (round(tgt_delta / MIN_DET_FF, 1) if tgt_delta is not None else None),
        })
    # positive control: target pass moves >= 3x min_det on >= 1 rung
    pc = any((r["target_pass_delta_x_min_det"] or 0) >= 3.0 for r in rungs)
    best = max(rungs, key=lambda r: (r["gpu_gain_vs_baseline_ms"] or -9))
    if not pc:
        verdict = "INCONCLUSIVE (positive control failed: %s never moved >=3x min_det)" % target_pass
    elif (best["gpu_gain_vs_baseline_ms"] or 0) >= 0.10:
        verdict = "KEEP (best gain %.3f ms at %s=%s)" % (best["gpu_gain_vs_baseline_ms"], cvar, best["value"])
    else:
        verdict = "DROP (best gain %.3f ms < 0.10)" % (best["gpu_gain_vs_baseline_ms"] or 0)
    out = {"_what": "T4 step 2 arm %s: %s at forest_floor vs the as-is baseline." % (name, cvar),
           "cvar": cvar, "default": default, "values": values,
           "target_pass": target_pass, "baseline_gpu_p90": b_gpu,
           "min_detectable_ms": MIN_DET_FF, "rungs": rungs,
           "positive_control_pass": pc, "verdict": verdict}
    json.dump(out, open(os.path.join(T4, "t4_arm_%s.json" % name), "w",
                        encoding="utf-8"), indent=1)
    print("ARM %s verdict: %s" % (name, verdict))
    for r in rungs:
        print("  %s=%s  GPU p90 %.3f  gain %s ms (%sx)  %s delta %s (%sx)" % (
            cvar, r["value"], r["gpu_p90_median"] or -1,
            r["gpu_gain_vs_baseline_ms"], r["gpu_gain_x_min_det"],
            target_pass, r["target_pass_delta_ms"], r["target_pass_delta_x_min_det"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--baseline-runs", type=int, default=3)
    ap.add_argument("--arm")
    ap.add_argument("--cvar")
    ap.add_argument("--values", help="comma list, e.g. 0.03,0.06,0.1")
    ap.add_argument("--default")
    ap.add_argument("--target-pass", default="ShadowDepths")
    a = ap.parse_args()
    if a.baseline:
        do_baseline(a.baseline_runs)
    if a.arm:
        vals = [v.strip() for v in a.values.split(",")]
        do_arm(a.arm, a.cvar, vals, a.default, a.target_pass)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
