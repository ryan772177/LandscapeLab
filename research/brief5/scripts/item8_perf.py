#!/usr/bin/env python3
"""item8_perf.py -- Item-8 I2 (positive control) + I3 (the number), READ-ONLY.

Reads the per-(station,arm) CsvProfiler CSVs collected by item8_capture.py from
_verify/perf/item8/<station>_<arm>/item8_<...>.csv and computes, per station:

  I2 POSITIVE CONTROL (does the HLOD-off command actually apply?):
     medians of ActorCount/WorldPartitionHLOD, GPUSceneInstanceCount,
     SceneCulling/NumStaticInstances over the measured window, arm A vs arm B.
     If NONE drop in B -> the command did not apply -> INCONCLUSIVE (I2 says:
     stop measuring, go to I5). If any drops -> the command applied.

  I3 THE NUMBER:
     GPU p90 per arm over the measured window; A/A delta = the noise floor;
     HLOD share = (A - B) ms, and as % of A, quoted x the A/A floor. Per-pass
     split of the (A - B) delta for Basepass, ShadowDepths, NaniteVisBuffer,
     LumenReflections (+ Prepass).

THE WINDOW. Each render is WARMUP rendered frames (WP-stream + GPU settle) then
FRAMES output frames; the CSV is the whole `-game` session. The render frames
are the steady tail, so the window is the LAST `FRAMES` data rows -- i.e. the
output frames, after the warmup is discarded (the plan's "discard the first 60,
measure 61-120"). A steadiness check (FrameTime cv) flags a window polluted by a
load hitch rather than averaging over it (NN13-adjacent).

VERDICT vocab (ITEM8): MEASURED (control passed, share >= 1x floor) /
MEASURED-NEGLIGIBLE (control passed, share < 1x floor) / INCONCLUSIVE (counters
unchanged = command not applied).
"""
import csv
import glob
import json
import os
import statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(REPO, "_verify", "perf", "item8")
INPUT = os.path.join(REPO, "research", "brief5", "input")
WINDOW = 60                     # measured output frames per render
CONTROL_PASSES = ("Basepass", "ShadowDepths", "Prepass", "NaniteVisBuffer",
                  "LumenReflections")
COUNTERS = ("ActorCount/WorldPartitionHLOD", "GPUSceneInstanceCount",
            "SceneCulling/NumStaticInstances")


def _p90(vals):
    if not vals:
        return None
    s = sorted(vals)
    # linear-interpolated 90th percentile
    k = 0.9 * (len(s) - 1)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _read_csv(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    return rows


def _floatcol(rows, col):
    out = []
    for r in rows:
        v = r.get(col)
        if v in (None, ""):
            continue
        try:
            out.append(float(v))
        except ValueError:
            pass
    return out


RENDER_FRAME_MIN_MS = 0.1       # GPU/Basepass above this = a real MRQ render frame
KEEP_STEADY = 30                # steady render frames measured (discard warm-up)


def analyse_run(csv_path):
    """Measure the GPU cost of the MRQ RENDER frames, not the idle pump.

    ⛔ THE INSTRUMENT TRAP THIS SOLVES (found at runtime 2026-09-21). A `-game`
    command-line MRQ render does its rendering OFF the main game-loop frame, so
    the CsvProfiler's per-row `GPUTime` (p50 ~0.07 ms) is the near-idle offscreen
    pump, NOT the 4K render. The render appears only on the ~60+few rows where a
    render pass fired: those rows carry real `GPU/Basepass` etc. So a render
    frame is identified by `GPU/Basepass > RENDER_FRAME_MIN_MS`, the per-frame
    GPU cost is the SUM of the `GPU/*` pass columns on that row, and the window
    is the last KEEP_STEADY render frames (the first ~20+ spike on shader/Nanite/
    TSR init -- one frame hit 3.6 s -- and are discarded)."""
    rows = _read_csv(csv_path)
    gcols = [c for c in rows[0].keys() if c and c.startswith("GPU/")]
    render = []
    for r in rows:
        try:
            bp = float(r.get("GPU/Basepass") or 0.0)
        except ValueError:
            bp = 0.0
        if bp <= RENDER_FRAME_MIN_MS:
            continue
        tot = 0.0
        row_pass = {}
        for c in gcols:
            v = r.get(c)
            if v in (None, ""):
                continue
            try:
                fv = float(v)
            except ValueError:
                continue
            tot += fv
            row_pass[c[len("GPU/"):]] = fv
        counters = {}
        for cc in COUNTERS:
            cv = r.get(cc)
            try:
                counters[cc] = float(cv) if cv not in (None, "") else None
            except ValueError:
                counters[cc] = None
        render.append({"total": tot, "pass": row_pass, "counters": counters})
    if len(render) < KEEP_STEADY:
        return {"error": "only %d render frames (< %d); GPU/Basepass never rose"
                % (len(render), KEEP_STEADY),
                "csv": os.path.relpath(csv_path, REPO).replace("\\", "/")}
    steady = render[-KEEP_STEADY:]
    totals = [x["total"] for x in steady]
    mean_t = statistics.mean(totals)
    cv = statistics.pstdev(totals) / mean_t if mean_t else None
    all_passes = set()
    for x in steady:
        all_passes.update(x["pass"])
    passes = {p: statistics.median([x["pass"].get(p, 0.0) for x in steady])
              for p in all_passes}
    counters = {}
    for cc in COUNTERS:
        v = [x["counters"][cc] for x in steady if x["counters"].get(cc)
             is not None]
        counters[cc] = statistics.median(v) if v else None
    return {
        "csv": os.path.relpath(csv_path, REPO).replace("\\", "/"),
        "n_rows": len(rows), "render_frames": len(render),
        "steady_frames": len(steady),
        "gpu_p90_ms": round(_p90(totals), 4),
        "gpu_mean_ms": round(mean_t, 4),
        "frametime_cv": round(cv, 4) if cv is not None else None,
        "window_steady": (cv is not None and cv < 0.15),
        "pass_medians_ms": {k: round(v, 4) for k, v in passes.items()},
        "counters": counters,
    }


def _load_manifest():
    p = os.path.join(REPO, "research", "brief5", "input",
                     "item8_capture_manifest.json")
    if not os.path.isfile(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


_MANIFEST = _load_manifest()


def _run_csv(station, arm):
    """Return (csv_path, tag, res) for the FINAL OK attempt of this arm, chosen
    from the capture manifest -- NOT "4K first" glob (audit #2): a hung 4K
    attempt superseded by a 1080p retry must not be analysed, and A/B must not
    silently mix resolutions."""
    if _MANIFEST:
        final = None
        for r in (_MANIFEST.get("phases", {}).get("renders") or []):
            if r.get("station") == station and r.get("arm") == arm \
                    and r.get("ok") and r.get("csv"):
                final = r                      # last ok attempt wins
        if final:
            return (os.path.join(REPO, final["csv"]),
                    final.get("tag"), tuple(final.get("res") or ()))
    # fallback (no manifest): prefer 4K then _lo, res unknown
    tag = "%s_%s" % (station, arm)
    for cand in (tag, tag + "_lo"):
        hits = glob.glob(os.path.join(OUT, cand, "item8_%s.csv" % cand))
        if hits:
            res = (1920, 1080) if cand.endswith("_lo") else (3840, 2160)
            return hits[0], cand, res
    return None, None, None


COUNTER_DROP_FRAC = 0.01        # >=1% relative drop counts as "dropped" (#10)


def station_report(station):
    arms, used_res = {}, {}
    for arm in ("A1", "A2", "B"):
        path, used, res = _run_csv(station, arm)
        if not path or not os.path.isfile(path):
            arms[arm] = {"error": "no CSV for %s_%s" % (station, arm)}
            continue
        r = analyse_run(path)
        r["_used_run"] = used
        r["_res"] = list(res) if res else None
        used_res[arm] = tuple(res) if res else None
        arms[arm] = r
    rep = {"station": station, "arms": arms}
    if any("error" in arms[a] for a in ("A1", "A2", "B")):
        rep["verdict"] = "INCOMPLETE: missing a run (%s)" % ", ".join(
            "%s(%s)" % (a, arms[a].get("error"))
            for a in ("A1", "A2", "B") if "error" in arms[a])
        return rep

    # MIXED-RESOLUTION GUARD (#2): A and B must be the SAME resolution or the
    # delta is a resolution delta wearing an HLOD-share label.
    res_set = {used_res.get(a) for a in ("A1", "A2", "B") if used_res.get(a)}
    if len(res_set) > 1:
        rep["resolutions"] = {a: used_res.get(a) for a in ("A1", "A2", "B")}
        rep["verdict"] = "INCOMPLETE-MIXED-RES: arms rendered at %s -- A/B not " \
                         "comparable" % sorted(str(r) for r in res_set)
        return rep
    rep["resolution"] = list(next(iter(res_set))) if res_set else None

    a1, a2, b = arms["A1"], arms["A2"], arms["B"]
    # ---- I2 positive control: counters A (mean of A1,A2) vs B ----
    ctrl = {}
    n_comparable, any_dropped = 0, False
    for c in COUNTERS:
        av = [x for x in (a1["counters"].get(c), a2["counters"].get(c))
              if x is not None]
        a_med = statistics.mean(av) if av else None
        b_med = b["counters"].get(c)
        comparable = a_med is not None and b_med is not None
        n_comparable += 1 if comparable else 0
        # relative drop, not a bare `<` (#10): a one-unit dip is noise
        dropped = comparable and (a_med - b_med) / max(abs(a_med), 1e-9) \
            >= COUNTER_DROP_FRAC
        any_dropped = any_dropped or dropped
        ctrl[c] = {"A": a_med, "B": b_med, "comparable": comparable,
                   "delta_B_minus_A": (round(b_med - a_med, 1) if comparable
                                       else None),
                   "dropped_in_B": dropped}
    if n_comparable == 0:
        # rule 13: no counter could be compared -> the counter control is
        # UNMEASURABLE. It is NOT "the command did not apply" -- that claim
        # needs a comparison. The pixel diff (item8_pixels) is the other, and
        # per the plan STRONGER, positive control; defer to it.
        counter_verdict = "UNMEASURABLE (0 of %d counter columns present in " \
            "both arms; 0 compared) -- defer to the item8_pixels A/B frame " \
            "diff, the stronger positive control" % len(COUNTERS)
        counter_state = "UNMEASURABLE"
    elif any_dropped:
        counter_verdict = "command APPLIED (a render counter dropped >= %d%% " \
            "in B)" % int(COUNTER_DROP_FRAC * 100)
        counter_state = "APPLIED"
    else:
        counter_verdict = "command did NOT apply (%d counter(s) compared, none " \
            "dropped) -> INCONCLUSIVE" % n_comparable
        counter_state = "NOT_APPLIED"
    rep["positive_control_I2"] = {
        "counters": ctrl, "n_counters_compared": n_comparable,
        "any_counter_dropped_in_B": any_dropped,
        "counter_control_state": counter_state, "verdict": counter_verdict}

    # ---- I3 the number ----
    a_p90 = [x for x in (a1["gpu_p90_ms"], a2["gpu_p90_ms"]) if x is not None]
    noise_floor = (round(abs(a1["gpu_p90_ms"] - a2["gpu_p90_ms"]), 4)
                   if len(a_p90) == 2 else None)
    a_mean = round(statistics.mean(a_p90), 4) if a_p90 else None
    share_ms = (round(a_mean - b["gpu_p90_ms"], 4)
                if a_mean is not None and b["gpu_p90_ms"] is not None else None)
    share_pct = (round(100.0 * share_ms / a_mean, 2)
                 if share_ms is not None and a_mean else None)
    share_x_floor = (round(share_ms / noise_floor, 1)
                     if share_ms is not None and noise_floor else None)
    a_pass = {}
    for k in set(list(a1["pass_medians_ms"]) + list(a2["pass_medians_ms"])):
        vs = [d["pass_medians_ms"][k] for d in (a1, a2)
              if k in d["pass_medians_ms"]]
        a_pass[k] = statistics.mean(vs) if vs else None
    pass_delta = {}
    for k in CONTROL_PASSES:
        av, bv = a_pass.get(k), b["pass_medians_ms"].get(k)
        if av is not None and bv is not None:
            pass_delta[k] = round(av - bv, 4)

    steady = {a: arms[a].get("window_steady") for a in ("A1", "A2", "B")}
    all_steady = all(steady.values())
    # verdict gate: a genuine NOT_APPLIED is INCONCLUSIVE; an unsteady window is
    # INCOMPLETE-UNSTEADY (#6, do not quote MEASURED over a load-hitch window);
    # otherwise MEASURED / MEASURED-NEGLIGIBLE vs the A/A floor.
    if counter_state == "NOT_APPLIED":
        verdict = "INCONCLUSIVE"
    elif not all_steady:
        verdict = "INCOMPLETE-UNSTEADY"
    elif share_ms is not None and noise_floor is not None and \
            share_ms >= noise_floor:
        verdict = "MEASURED"
    else:
        verdict = "MEASURED-NEGLIGIBLE"
    rep["number_I3"] = {
        "gpu_p90_ms": {"A1": a1["gpu_p90_ms"], "A2": a2["gpu_p90_ms"],
                       "A_mean": a_mean, "B": b["gpu_p90_ms"]},
        "noise_floor_ms_AA": noise_floor,
        "hlod_share_ms": share_ms,
        "hlod_share_pct_of_A": share_pct,
        "hlod_share_x_noise_floor": share_x_floor,
        "per_pass_delta_A_minus_B_ms": pass_delta,
        "windows_steady": steady,
        "positive_control_source": counter_state,
        "_note": ("positive_control_source UNMEASURABLE means the counter "
                  "control could not run; the verdict then rests on the "
                  "item8_pixels A/B frame diff being nonzero beyond the "
                  "512 m band."),
    }
    rep["verdict"] = verdict
    return rep


def main():
    out = {"_what": "Item-8 I2+I3: HLOD proxy GPU share from -game MRQ A/A/B.",
           "_window_frames": WINDOW, "stations": {}}
    for st in ("vista", "treeline"):
        out["stations"][st] = station_report(st)
        v = out["stations"][st].get("verdict", "?")
        n = out["stations"][st].get("number_I3", {})
        print("%-9s %-20s share %s ms (x%s floor) A_mean %s B %s"
              % (st, v, n.get("hlod_share_ms"),
                 n.get("hlod_share_x_noise_floor"),
                 (n.get("gpu_p90_ms") or {}).get("A_mean"),
                 (n.get("gpu_p90_ms") or {}).get("B")))
    p = os.path.join(INPUT, "item8_perf.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("wrote", os.path.relpath(p, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
