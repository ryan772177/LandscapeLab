#!/usr/bin/env python
"""Brief 5 D4 -- full -game perf of the D3 density world vs the ratified budgets.

READ-ONLY: standalone -game processes load the saved level and mutate nothing
(restored by process exit). No editor, no git, no world write.

3 runs per station of forest_floor / open_max / treeline / plaza / vista (GPU +
game-thread p90 per run, median across runs), compared to the per-zone budgets
with the ratified +10% tolerance. forest_floor and open_max use Ryan's 13.0 ms
ceiling (they are Brief-5 ground stations, not in perf_budgets.json). Ratified
stations come from one spline batch per run; the two ground stations use their
station-json. Aggregation is offline afterward.

Ryan's D4 rule: ANY station over budget (median GPU p90 > budget x 1.10) -> the
density upgrade busts the GPU budget; D3 must be reverted (a separate deliberate
step) and the run goes to D7. This tool MEASURES and flags; it does NOT revert.

Output: research/brief5/derived/d4_perf.json + a table.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
BR = os.path.join(REPO, "research", "brief5")
PY = sys.executable

# GPU budgets (recipes/perf_budgets.json per_zone_ms) + Ryan's 13.0 for the two
# ground stations. GPU_LINE is the RULED pass/fail line (Ryan, D4 ruling
# 2026-09-22): NO 10% tolerance anywhere EXCEPT treeline, whose line is 7.7
# (7.0 nominal + its standing tolerance). game budget 6.0 all, hard.
GPU_BUDGET = {"forest_floor": 13.0, "open_max": 13.0,
              "treeline": 7.0, "plaza": 10.5, "vista": 8.5}
GPU_LINE = {"forest_floor": 13.0, "open_max": 13.0,
            "treeline": 7.7, "plaza": 10.5, "vista": 8.5}
GAME_BUDGET = {k: 6.0 for k in GPU_BUDGET}
GAME_LINE = {k: 6.0 for k in GPU_BUDGET}
TOL = 0.0
RATIFIED = ["treeline", "plaza", "vista"]   # from the spline batch
GROUND = {"forest_floor": os.path.join(BR, "input", "forest_station.json"),
          "open_max": os.path.join(BR, "input", "open_max_station.json")}


def log(m):
    print("[D4] " + m, flush=True)


def run(cmd, timeout):
    log("run: " + " ".join(cmd[-6:]))
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        log("  TIMEOUT after %ss" % timeout)
        return None
    log("  rc %d (%.0fs)" % (r.returncode, time.time() - t0))
    return r.returncode


def outdir_today():
    import datetime
    # perf_standalone writes standalone_<today>; find the newest matching dir
    cands = sorted(glob.glob(os.path.join(REPO, "_verify", "perf",
                                          "standalone_*")))
    return cands[-1] if cands else None


def read_zone(tag_glob, zone):
    """Latest perf_standalone json matching tag_glob -> that zone's p90s."""
    od = outdir_today()
    if not od:
        return None
    files = sorted(glob.glob(os.path.join(od, tag_glob)),
                   key=os.path.getmtime)
    for f in reversed(files):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        z = (d.get("zones") or {}).get(zone)
        if not z:
            continue
        s = z.get("stats_ms") or {}
        vm = (z.get("gpu_mem_csv") or {}).get("peak_by_column", {}).get(
            "GPUMem/LocalUsedMB")
        return {"gpu_p90": (s.get("GPUTime") or {}).get("p90"),
                "game_p90": (s.get("GameThreadTime") or {}).get("p90"),
                "frame_p90": (s.get("FrameTime") or {}).get("p90"),
                "vram_local_mib": vm, "file": os.path.basename(f)}
    return None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--skip-measure", action="store_true",
                    help="aggregate existing d4_* jsons only (no -game runs)")
    a = ap.parse_args()

    if not a.skip_measure:
        pids = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "Get-Process UnrealEditor* -ErrorAction "
                               "SilentlyContinue | Measure-Object | "
                               "ForEach-Object Count"], capture_output=True,
                              text=True).stdout.strip()
        if pids and pids != "0":
            log("REFUSE: %s UnrealEditor process(es) running (rule 11)" % pids)
            return 2
        for r in range(1, a.runs + 1):
            run([PY, os.path.join(SCRIPTS, "perf_standalone.py"),
                 "--noxgecontroller", "--tag", "d4_rat_r%d" % r], a.timeout)
            for name, sj in GROUND.items():
                run([PY, os.path.join(SCRIPTS, "perf_standalone.py"),
                     "--noxgecontroller", "--station-json", sj,
                     "--station-name", name,
                     "--tag", "d4_%s_r%d" % (name, r)], a.timeout)

    # ---- aggregate -----------------------------------------------------
    rows = {}
    for name in GPU_BUDGET:
        per_run = []
        for r in range(1, a.runs + 1):
            if name in RATIFIED:
                z = read_zone("*d4_rat_r%d*.json" % r, name)
            else:
                z = read_zone("*d4_%s_r%d*.json" % (name, r), name)
            if z:
                per_run.append(z)
        gpu = median([z["gpu_p90"] for z in per_run])
        game = median([z["game_p90"] for z in per_run])
        gb, gmb = GPU_BUDGET[name], GAME_BUDGET[name]
        gl, gml = GPU_LINE[name], GAME_LINE[name]
        rows[name] = {
            "runs": len(per_run),
            "gpu_p90_median": gpu, "gpu_budget": gb, "gpu_line": gl,
            "gpu_over": (gpu is not None and gpu > gl),
            "game_p90_median": game, "game_budget": gmb, "game_line": gml,
            "game_over": (game is not None and game > gml),
            "vram_local_mib": median([z["vram_local_mib"] for z in per_run]),
            "per_run_gpu": [z["gpu_p90"] for z in per_run],
        }
    over = [n for n, v in rows.items() if v["gpu_over"] or v["game_over"]]
    out = {
        "_what": "Brief 5 D4 -- density world -game perf vs ratified budgets.",
        "_rule": ("Ryan D4 (2026-09-22): any station over its RULED line (median "
                  "GPU p90 > line; no 10% tolerance except treeline 7.7) -> "
                  "revert D3, go to D7. This tool measures + flags only."),
        "runs": a.runs, "tolerance_frac": TOL,
        "gpu_lines": GPU_LINE,
        "stations": rows,
        "over_budget_stations": over,
        "verdict": ("REVERT_D3" if over else "PASS_TO_ASK2"),
    }
    json.dump(out, open(os.path.join(BR, "derived", "d4_perf.json"),
                        "w", encoding="utf-8"), indent=1)
    print("\nBrief 5 D4 -- GPU p90 (median of %d) vs RULED line (no tol exc treeline 7.7)" % a.runs)
    print("%-13s %8s %8s  %-5s | %8s %8s %-5s" %
          ("station", "gpu_p90", "line", "GPU", "game_p90", "line", "GAME"))
    for n in ["forest_floor", "open_max", "treeline", "plaza", "vista"]:
        v = rows[n]
        print("%-13s %8s %8.1f  %-5s | %8s %8.1f %-5s  (%d runs)" % (
            n, v["gpu_p90_median"], v["gpu_line"],
            "OVER" if v["gpu_over"] else "ok",
            v["game_p90_median"], v["game_line"],
            "OVER" if v["game_over"] else "ok", v["runs"]))
    print("\nVERDICT:", out["verdict"], "| over:", over or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
