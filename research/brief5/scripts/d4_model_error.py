#!/usr/bin/env python
"""Brief 5 D4 Task 1 -- harvest the density cost-model error before the revert.

READ-ONLY. Per station: predicted ms (zone_map/DENSITY_PLAN), measured p90 (D4
3-run median), delta, delta / min_detectable, the per-pass GPU split of the DENSE
world (from the d4pp --csv-gpu-stats CSVs, median over the last WINDOW frames)
against the same-instrument v3 baseline where one exists, and the visible-tree
count delta with ms-per-1000-trees per pass.

Ryan's Task 1: "the model is what failed, not the trees." So this pins WHICH pass
carried the underprediction, measured, not assumed.

Same-instrument v3 per-pass baselines (all GPU/<pass> medians, --csv-gpu-stats):
  forest_floor -> forest_cost.json per_pass_delta_ms.table[*].as_is_ms
  treeline, plaza -> density_baseline.json item1_gpu_passes[zone].top8
  open_max, vista -> NONE (open_max is a new station; vista was not in item1) ->
                     reported with a null v3 and the reason (rule 9/13).

Output: research/brief5/derived/d4_model_error.json.
"""
import csv
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BR = os.path.join(REPO, "research", "brief5")
sys.path.insert(0, os.path.join(REPO, "scripts"))
import perf_standalone as ps  # noqa: E402
sys.path.insert(0, os.path.join(BR, "scripts"))
import derive_forest_station as dfs  # count_at, wrap_pi  # noqa: E402

PASSES = ["Basepass", "ShadowDepths", "LumenReflections", "Prepass",
          "NaniteVisBuffer"]
WINDOW = 1500   # last N frames, matching item1_gpu_passes' method
MIN_DET = {"forest_floor": 0.016, "open_max": 0.016, "treeline": 0.06,
           "plaza": 0.04, "vista": 0.06}
_MIN_DET_SRC = {"forest_floor": "BASELINE v3 forest 0.016",
                "open_max": "forest-class proxy 0.016 (no own measurement)",
                "treeline": "noise_floor.json 0.06", "plaza": "noise_floor.json 0.04",
                "vista": "treeline-class proxy 0.06 (no own measurement)"}

CSV_TAG = {"forest_floor": "forest_floor_d4pp_forest_floor",
           "open_max": "open_max_d4pp_open_max",
           "treeline": "treeline_d4pp_rat", "plaza": "plaza_d4pp_rat",
           "vista": "vista_d4pp_rat"}


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def dense_per_pass(station):
    """median GPU/<pass> ms over the last WINDOW frames of the d4pp CSV."""
    od = sorted(__import__("glob").glob(os.path.join(
        REPO, "_verify", "perf", "standalone_*")))[-1]
    path = os.path.join(od, CSV_TAG[station] + ".csv")
    if not os.path.isfile(path):
        return None, "csv missing: " + os.path.basename(path)
    cols = {p: [] for p in PASSES}
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        want = {p: "GPU/" + p for p in PASSES}
        rows = list(rd)
    tail = rows[-WINDOW:] if len(rows) > WINDOW else rows
    for r in tail:
        for p, cn in want.items():
            v = r.get(cn)
            if v not in (None, ""):
                try:
                    cols[p].append(float(v))
                except ValueError:
                    pass
    return {p: (med(cols[p]) if cols[p] else None) for p in PASSES}, len(tail)


def v3_per_pass(station):
    """same-instrument v3 per-pass baseline (ms) by exact pass name, or {}."""
    if station == "forest_floor":
        t = json.load(open(os.path.join(BR, "input", "forest_cost.json"),
                           encoding="utf-8"))["per_pass_delta_ms"]["table"]
        return {row["pass"]: row.get("as_is_ms") for row in t}
    if station in ("treeline", "plaza"):
        gp = json.load(open(os.path.join(BR, "input", "density_baseline.json"),
                            encoding="utf-8"))["item1_gpu_passes"].get(station, {})
        return {e["pass"]: e["ms"] for e in gp.get("top8", [])}
    return {}


def dense_in_frustum(station, sp_arr, fov_h, res):
    """count_at against the DENSE plans at the station's fixed camera."""
    w, h = res
    half_h = math.radians(fov_h) / 2.0
    half_v = math.atan(math.tan(half_h) * (h / float(w)))
    cams = {
        "forest_floor": ("input", "forest_station.json"),
        "open_max": ("input", "open_max_station.json"),
    }
    if station in cams:
        c = json.load(open(os.path.join(BR, *cams[station]),
                           encoding="utf-8"))["camera"]
    else:
        c = json.load(open(os.path.join(BR, "input", "_census_stations.json"),
                           encoding="utf-8"))["stations"][station]["camera"]
    tot, seg, per = dfs.count_at(c["x_cm"], c["y_cm"], c["z_cm"],
                                 c["yaw_deg"], c["pitch_deg"], sp_arr,
                                 half_h, half_v)
    return tot


def main():
    d4 = json.load(open(os.path.join(BR, "derived", "d4_perf.json"),
                        encoding="utf-8"))["stations"]
    zpred = json.load(open(os.path.join(BR, "derived", "zone_map.json"),
                          encoding="utf-8"))["projected_ms_per_station"]
    # v3 (m=1) visible counts
    v3vis = {"forest_floor": 1844, "plaza": 903, "treeline": 0, "vista": 34,
             "open_max": None}
    # dense in-frustum needs the placed plans loaded once
    _r8k, fov_h, res, sp_arr = dfs.load(os.path.join(REPO, "foliage"))

    out = {"_what": "Brief 5 D4 Task 1 -- density cost-model error, per station.",
           "_window_frames": WINDOW, "_passes": PASSES,
           "_predicted_source": "zone_map.json projected_ms_per_station "
                                 "(DENSITY_PLAN projection)",
           "stations": {}}
    for st in ["forest_floor", "open_max", "treeline", "plaza", "vista"]:
        measured = d4[st]["gpu_p90_median"]
        pred = (zpred.get(st) or {}).get("projected_ms")
        delta = (round(measured - pred, 3) if (measured is not None
                                               and pred is not None) else None)
        md = MIN_DET[st]
        dpp, nrows = dense_per_pass(st)
        v3pp = v3_per_pass(st)
        pass_rows = {}
        for p in PASSES:
            dv = dpp.get(p) if dpp else None
            bv = v3pp.get(p)
            pass_rows[p] = {"dense_ms": (round(dv, 4) if dv is not None else None),
                            "v3_ms": (round(bv, 4) if bv is not None else None),
                            "delta_ms": (round(dv - bv, 4)
                                         if (dv is not None and bv is not None)
                                         else None)}
        dense_vis = dense_in_frustum(st, sp_arr, fov_h, res)
        v3_vis = v3vis.get(st)
        vis_delta = (dense_vis - v3_vis if v3_vis is not None else None)
        # ms per 1000 ADDED trees, per pass (only where v3 pass + vis delta exist)
        per1000 = {}
        for p in PASSES:
            d_ms = pass_rows[p]["delta_ms"]
            if d_ms is not None and vis_delta:
                per1000[p] = round(d_ms / (vis_delta / 1000.0), 4)
            else:
                per1000[p] = None
        total_delta = delta
        total_per1000 = (round(total_delta / (vis_delta / 1000.0), 4)
                         if (total_delta is not None and vis_delta) else None)
        out["stations"][st] = {
            "predicted_ms": pred,
            "measured_p90_ms": measured,
            "delta_ms": delta,
            "min_detectable_ms": md, "_min_det_src": _MIN_DET_SRC[st],
            "delta_over_min_det": (round(delta / md, 1)
                                   if delta is not None else None),
            "over_ruled_line": d4[st]["gpu_over"],
            "per_pass": pass_rows,
            "_v3_per_pass_available": bool(v3pp),
            "_v3_per_pass_note": ("same-instrument v3 baseline (GPU/<pass> "
                                  "median)" if v3pp else
                                  "NO same-instrument v3 baseline at this station"
                                  " (open_max is new; vista not in item1)"),
            "visible_trees": {"v3_m1": v3_vis, "dense": dense_vis,
                              "delta": vis_delta},
            "ms_per_1000_added_trees_total": total_per1000,
            "ms_per_1000_added_trees_per_pass": per1000,
            "_csv_rows_used": nrows,
        }
    json.dump(out, open(os.path.join(BR, "derived", "d4_model_error.json"),
                        "w", encoding="utf-8"), indent=1)
    # print
    print("Brief 5 D4 model error -- predicted vs measured GPU p90")
    print("%-13s %9s %9s %8s %10s  %s" %
          ("station", "predict", "measure", "delta", "d/min_det", "ms/1000 added"))
    for st, v in out["stations"].items():
        print("%-13s %9s %9s %8s %10s  %s  (vis %s->%s)" % (
            st, v["predicted_ms"], v["measured_p90_ms"], v["delta_ms"],
            v["delta_over_min_det"], v["ms_per_1000_added_trees_total"],
            v["visible_trees"]["v3_m1"], v["visible_trees"]["dense"]))
    print("\nper-pass dense ms (which pass carries the cost):")
    for st, v in out["stations"].items():
        pr = v["per_pass"]
        print("  %-13s " % st + "  ".join(
            "%s %s" % (p[:5], pr[p]["dense_ms"]) for p in PASSES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
