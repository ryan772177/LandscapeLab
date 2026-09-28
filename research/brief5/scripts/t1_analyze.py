#!/usr/bin/env python3
"""Brief 5 T1 -- GPU delta + positive control from the -game A/B runs.

READ-ONLY. arm A = as-is + foliage.DitheredLOD 0; arm B = foliage.ForceLOD 2 +
foliage.DitheredLOD 0. Per station: GPU p90 mean/sd per arm, delta B-A x
min_detectable (0.016 ms forest noise floor), and RHI/PrimitivesDrawn +
RHI/DrawCalls per arm -- the render-side counter that MUST rise A->B (positive
control). The still-based coverage ratio / band SSIM are added by the editor
pass; this is the measurable -game half.
"""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO, "_verify", "perf", "brief5_t1")
MIN_DET = 0.016  # forest_floor noise floor (v3 Task 1)
WINDOW = 1500


def _rundir(tag):
    hits = glob.glob(os.path.join(BASE, tag, "standalone_*"))
    return hits[0] if hits else None


def gpu_p90(tag):
    d = _rundir(tag)
    if not d:
        return None
    j = [f for f in os.listdir(d) if f.startswith("perf_standalone") and f.endswith(".json")][0]
    return list(json.load(open(os.path.join(d, j)))["zones"].values())[0]["stats_ms"]["GPUTime"]["p90"]


def csv_means(tag, cols):
    d = _rundir(tag)
    if not d:
        return {}
    cf = [f for f in os.listdir(d) if f.endswith(".csv")]
    if not cf:
        return {}
    rows = list(csv.DictReader(open(os.path.join(d, cf[0]), newline="")))[-WINDOW:]
    out = {}
    for c in cols:
        v = [float(r[c]) for r in rows if r.get(c) not in (None, "")]
        out[c] = round(statistics.mean(v)) if v else None
    return out


def lod_readback(tag):
    d = _rundir(tag)
    if not d:
        return None
    j = [f for f in os.listdir(d) if f.startswith("perf_standalone") and f.endswith(".json")][0]
    return list(json.load(open(os.path.join(d, j)))["zones"].values())[0].get("lod_lever_readback")


def arm(station, arm_name, runs):
    tags = ["%s_%s_r%d" % (station, arm_name, r) for r in runs]
    p90 = [gpu_p90(t) for t in tags]
    p90 = [x for x in p90 if x is not None]
    cnt = csv_means(tags[0], ["RHI/PrimitivesDrawn", "RHI/DrawCalls"])
    return {
        "runs": len(p90),
        "gpu_p90_ms": [round(x, 3) for x in p90],
        "gpu_p90_mean": round(statistics.mean(p90), 3) if p90 else None,
        "gpu_p90_sd": round(statistics.stdev(p90), 4) if len(p90) > 1 else None,
        "RHI_PrimitivesDrawn": cnt.get("RHI/PrimitivesDrawn"),
        "RHI_DrawCalls": cnt.get("RHI/DrawCalls"),
        "lod_lever_readback": lod_readback(tags[0]),
    }


def main():
    out = {"_what": "Brief 5 T1 -game A/B: GPU delta + positive control. Stills "
                    "coverage/SSIM added by the editor pass.",
           "_min_detectable_ms": MIN_DET, "stations": {}}
    for station in ("ff", "rg"):
        a = arm(station, "armA", (1, 2, 3))
        b = arm(station, "armB", (1, 2, 3))
        delta = (round(b["gpu_p90_mean"] - a["gpu_p90_mean"], 3)
                 if a["gpu_p90_mean"] and b["gpu_p90_mean"] else None)
        prim_rose = (b["RHI_PrimitivesDrawn"] is not None
                     and a["RHI_PrimitivesDrawn"] is not None
                     and b["RHI_PrimitivesDrawn"] > a["RHI_PrimitivesDrawn"])
        out["stations"][station] = {
            "arm_A_asis_dithered0": a,
            "arm_B_forcelod2_dithered0": b,
            "gpu_delta_ms_B_minus_A": delta,
            "gpu_delta_x_min_detectable": (round(delta / MIN_DET, 1)
                                           if delta is not None else None),
            "positive_control_primitives_rose_A_to_B": prim_rose,
            "_primitives_A": a["RHI_PrimitivesDrawn"],
            "_primitives_B": b["RHI_PrimitivesDrawn"],
        }
    p = os.path.join(REPO, "research", "brief5", "input", "t1_game_ab.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    for s, z in out["stations"].items():
        print("%-4s A %.3f  B %.3f  delta %+.3f (x%s)  prims A %s -> B %s rose=%s"
              % (s, z["arm_A_asis_dithered0"]["gpu_p90_mean"] or 0,
                 z["arm_B_forcelod2_dithered0"]["gpu_p90_mean"] or 0,
                 z["gpu_delta_ms_B_minus_A"] or 0,
                 z["gpu_delta_x_min_detectable"], z["_primitives_A"],
                 z["_primitives_B"], z["positive_control_primitives_rose_A_to_B"]))
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
