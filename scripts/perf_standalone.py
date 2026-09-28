"""perf_standalone.py — E3: frame cost in a STANDALONE `-game` process.

WHY THIS EXISTS RATHER THAN perf_flythrough.py
----------------------------------------------
Both existing perf tools drive the EDITOR viewport, and the editor is the
suspect. `check_perf.py` has been RED on plaza at Game 14.00 ms against a
12.00 budget, and REGISTER records the reason to doubt it: "game thread
pinned at 13.9-14.15 ms on all four zones regardless of content". A number
that does not move when the content moves is measuring the instrument.

So this measures the same four ratified stations with the editor gone.

**IT DOES NOT RE-RATIFY ANYTHING.** The budgets in `recipes/perf_budgets.json`
are law and are untouched. This writes a second, independent measurement
beside them and says how the two differ. Whether the budgets should move is an
operator decision, not this script's.

HOW A STANDALONE RUN IS DRIVEN, AND WHAT THAT COSTS
---------------------------------------------------
`-game` has no Python and no remote channel, so `-ExecCmds` -- which fires
ONCE at startup -- is the only lever. Two consequences, both handled here
rather than hidden:

  * THE CAMERA IS MOVED WITH `BugItGo`, not `ViewActor`. BugItGo takes the
    ratified coordinates straight from perf_budgets.json and needs no camera
    actor to exist under a name this script cannot verify offline. The move is
    NOT verified in-process: `getall PlayerController Location` prints nothing
    (`Location` is not a reflected UPROPERTY on the controller), and searching
    the log for "BugItGo" only proves the line was echoed. Camera placement is
    instead checked AFTER the run by CROSS-STATION DIFFERENTIATION -- if the
    stations' timings come back near-identical, BugItGo moved nothing and the
    run is flagged suspect.

  * THE WINDOW IS THE TAIL OF THE CAPTURE. Warmup cannot be timed, and the
    first attempt -- drop WARMUP_S from the front -- left nothing at all: the
    whole capture was 755 frames of startup, because at the resolution the
    run actually got, the engine outran the requested frame count before the
    world was up. Taking the LAST MIN_WINDOW_S needs no assumption about when
    loading finished. A capture too short to contain a full window is
    reported short, not averaged over whatever arrived.

  * RESOLUTION IS FORCED WITH `r.setRes` AND READ BACK FROM ENGINE METADATA.
    `-ResX/-ResY` LOSES to config: the first run logged
    `Set CVar [[r.setres:1280x720]]` and measured 720p while reporting 4K,
    because the read-back regex matched the command line the log echoes.
    The honest source is the CsvProfiler's `systemresolution.resx/resy`.

Reuses `measure_frame_cost._reduce` and `._newest_csv`: non-negotiable 4a.

VRAM + RESIDENCY (added 2026-09-19b, Brief-4 T11 rule-12 gap)
-------------------------------------------------------------
T11 found this tool declared no VRAM/residency, so its perf numbers could not
answer "did the water push VRAM toward the DEVICE_HUNG ceiling". Now:
  * VRAM PEAK is measured by polling `nvidia-smi memory.used` through the dwell
    and taking the peak over the steady-state window (the same tail the timings
    use), reported against the 13,312 MiB abort ceiling. A system instrument,
    so it does not depend on any UE CSV column existing; a box without
    nvidia-smi records vram = null WITH the reason (rule 13), never zero.
  * An in-engine GPU-mem CSV cross-check is attempted via `r.GPUCsvStatsEnable`
    (non-negotiable 8: a second instrument); ABSENT, not fabricated, when the
    build writes no such columns.
  * RESIDENCY is read from each station's log as WP-streaming-active evidence
    (Initialize + GenerateStreaming) plus the DECLARED loading range from the
    recipe. A steady-state resident-cell COUNT is NOT reachable via
    startup-only ExecCmds in `-game` and is declared as such, not faked.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import bootstrap                                    # noqa: E402
import measure_frame_cost as mfc                    # noqa: E402

UE_EXE = r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
UPROJECT = os.path.join(bootstrap.UE_PROJECT_ROOT, "LandscapeLab.uproject")
LOG_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Logs")

RES_X, RES_Y = 3840, 2160
MIN_WINDOW_S = 25.0
SETTLE_S = 60.0        # world load + streaming + shader warmup, discarded
MARGIN_S = 20.0        # slack so the tail is comfortably inside steady state
FRAMES = 60000         # effectively unbounded: the DWELL bounds the capture,
                       # not the frame count. A frame budget that expires
                       # mid-run ends the capture wherever it happens to be.
EYE_CM = 175.0
COLUMNS = ("GPUTime", "GameThreadTime", "RenderThreadTime", "FrameTime")

# VRAM budget (docs/environment.md): the DEVICE_HUNG abort ceiling the HLOD
# builds were held under, and the card's physical VRAM. Both MiB. The perf run
# reports its peak against these -- water is new GPU cost on a machine that has
# lost the GPU to a driver timeout once, so this closes the rule-12 gap T11
# named (perf_standalone declared no VRAM/residency).
VRAM_ABORT_MIB = 13312
VRAM_PHYSICAL_MIB = 16303
# nvidia-smi is a system tool (C:\WINDOWS\system32), not a Python dependency;
# no pip install and nothing to record under standing rule 5. It is queried,
# never installed. A run on a machine without it records vram = null WITH the
# reason, never a fabricated number (rule 13).
NVIDIA_SMI = shutil.which("nvidia-smi") or r"C:\WINDOWS\system32\nvidia-smi.exe"


def gpu_mem_used_mib():
    """Whole-GPU VRAM used, MiB, from nvidia-smi -- or None if it cannot be
    read. This is a SYSTEM measurement (the driver reports it), applied and
    read back outside the engine, so it does not depend on any UE CSV column
    existing. It includes any other GPU consumer on the box; on a dedicated
    perf run the UnrealEditor -game process dominates, and that caveat is
    recorded beside the number rather than hidden.
    """
    try:
        out = subprocess.run(
            [NVIDIA_SMI, "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return None
        line = (out.stdout or "").strip().splitlines()
        return int(line[0].strip()) if line else None
    except Exception:
        return None


def _vram_reduce(samples, window_start_wall):
    """-> {peak, mean, n, peak_window, n_window, ...} over VRAM samples
    [(wall_time, mib)]. `peak_window` is the peak over samples at or after
    window_start_wall -- a wall-clock SUPERSET of the timing tail (wider by
    MARGIN_S at the front), conservative for a ceiling check; `peak` is over
    the whole dwell. A run with no successful sample returns None -- a missing
    measurement never reads as zero (rule 13)."""
    vals = [m for _, m in samples if isinstance(m, int)]
    if not vals:
        return None
    win = [m for t, m in samples if isinstance(m, int)
           and t >= window_start_wall]
    peak = max(vals)
    return {
        "peak_mib": peak,
        "mean_mib": round(sum(vals) / len(vals), 1),
        "n_samples": len(vals),
        "peak_window_mib": max(win) if win else None,
        "n_window": len(win),
        "abort_ceiling_mib": VRAM_ABORT_MIB,
        "physical_mib": VRAM_PHYSICAL_MIB,
        "headroom_to_abort_mib": VRAM_ABORT_MIB - peak,
        "over_abort_ceiling": peak > VRAM_ABORT_MIB,
        "_caveat": "whole-GPU used (nvidia-smi memory.used); includes any "
                   "other consumer, but the -game process dominates a "
                   "dedicated run.",
    }


def gpu_mem_from_csv(path):
    """Best-effort in-engine GPU-memory columns from the CsvProfiler output
    (r.GPUCsvStatsEnable). Column names vary by build, so take any column whose
    name reads as GPU/VRAM/streaming memory and report its peak. Returns {}
    when none appear -- ABSENT, never a fabricated zero (rule 13). This is the
    SECOND VRAM instrument beside nvidia-smi; when both are present they can be
    compared, and when the CSV carries none the nvidia-smi poll stands alone."""
    import csv as _csv
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            reader = _csv.DictReader(fh)
            # GPU/VRAM-qualified memory columns only. The bare `mem.*mb`
            # alternative was dropped (auditor LOW-3): it also matched a
            # system-RAM `*Memory*MB` column, which would then masquerade as an
            # in-engine GPU cross-check. GPUTime/etc never match (no mem|mb).
            cols = [c for c in (reader.fieldnames or [])
                    if c and re.search(
                        r"(gpu|vram|texture ?pool|streaming).*(mem|mb)",
                        c, re.I)]
            if not cols:
                return {}
            peak = {c: None for c in cols}
            n = 0
            for row in reader:
                n += 1
                for c in cols:
                    try:
                        v = float(row.get(c) or "")
                    except ValueError:
                        continue
                    if peak[c] is None or v > peak[c]:
                        peak[c] = v
            parsed = {c: round(peak[c], 1) for c in cols if peak[c] is not None}
            # Columns matched but nothing parsed is a read that returned
            # nothing -- return {} so the caller's ABSENT note attaches, rather
            # than a truthy empty dict that silently bypasses it (auditor
            # LOW-4, rule 13).
            if not parsed:
                return {}
            return {"peak_by_column": parsed, "n_rows": n}
    except Exception:
        return {}


def heightmap_z(x_cm, y_cm, recipe):
    """Ground Z from the heightmap. A PLACEMENT AID, not a trace.

    perf_budgets.json is explicit that ground is traced in-editor, and that
    this project once shipped a render/collide divergence of p90 30.98 m. The
    measured gap at near_ground is 2.3 cm, so for standing a camera at eye
    height the heightmap is adequate -- and the standalone pawn collides
    anyway. Recorded as `z_source` so nobody reads it as a trace.
    """
    import numpy as np
    from PIL import Image
    ls = recipe["landscape"]
    hm = os.path.join(REPO_ROOT, recipe["heightmap"]["source"])
    a = np.asarray(Image.open(hm)).astype(float)
    n = a.shape[0]
    scale = float(ls["scale_xy_cm"])
    loc = ls["location_cm"]
    z_scale = float(ls["z_scale_cm"])
    col = int(round((x_cm - loc[0]) / scale))
    row = int(round((y_cm - loc[1]) / scale))
    col = max(0, min(n - 1, col))
    row = max(0, min(n - 1, row))
    frac = a[row, col] / 65535.0
    return loc[2] + (frac - 0.5) * z_scale


def newest_log():
    logs = glob.glob(os.path.join(LOG_DIR, "*.log"))
    return max(logs, key=os.path.getmtime) if logs else None


def run_station(zone, x, y, z, pitch, yaw, outdir, dry=False,
                settle_s=SETTLE_S, local_ddc_path=None, noxge=False,
                no_remote_shader=False, hide_foliage=False, tag="",
                density_scale=None, hide_hlod=False, csv_gpu_stats=False,
                force_lod=None, dithered_lod=None, set_cvars=None):
    before = set(glob.glob(os.path.join(mfc.CSV_DIR, "*.csv")))
    os.makedirs(mfc.CSV_DIR, exist_ok=True)
    label = zone + (("_" + tag) if tag else "")
    log_name = "perf_standalone_%s.log" % label
    # ORDER MATTERS AND EVERY ITEM EARNS ITS PLACE.
    #   r.setRes  -- `-ResX/-ResY` on the command line LOSES to config. The
    #               first run logged `LogConfig: Set CVar [[r.setres:1280x720]]`
    #               and the engine's own metadata recorded
    #               systemresolution.resx=1280: a 720p measurement wearing a
    #               4K label. ExecCmds runs after config, so it wins.
    #   BugItGo   -- moves the camera to the ratified station.
    #   NO getall -- `getall PlayerController Location` printed NOTHING:
    #               `Location` is not a UPROPERTY on the controller. So camera
    #               placement is UNVERIFIED IN-PROCESS and is declared as such
    #               rather than asserted. Cross-station differentiation is the
    #               only check available and is applied after the run: if the
    #               four stations come back near-identical, BugItGo did not
    #               move anything and the run must be discarded.
    #   CsvProfile-- last, so the capture starts after the move.
    _cmds = [
        "r.setRes %dx%dw" % (RES_X, RES_Y),
        "BugItGo %.1f %.1f %.1f %.1f %.1f 0" % (x, y, z, pitch, yaw),
    ]
    # FOLIAGE-HIDE A/B (Brief 5 Task 0 item 2). Four levers, belt and braces --
    # the delta between an as-is run and this one is the FOLIAGE cost:
    #   foliage.DensityScale 0  -- HISM foliage (the placed trees) not spawned
    #   grass.DensityScale 0    -- landscape grass density to zero
    #   grass.Enable 0          -- landscape grass generation off
    #   r.ShowFlag.Foliage 0    -- per-frame render suppression (the reliable one
    #                              for anything already spawned)
    # Then re-QUERY the three cvars (bare name prints the value) so the log is a
    # read-back of what was honoured, not an assumption (rule 12/13). ShowFlag has
    # no getter; its read-back is the GPU delta itself plus the absence of
    # "not recognized". These fire at startup with the rest of -ExecCmds.
    if hide_foliage:
        # ShowFlag.Foliage -- NOT r.ShowFlag.Foliage: show-flag cvars register
        # as "ShowFlag.<Name>" with no r. prefix (ShowFlags.cpp:1116). The r.
        # form logs "Command not recognized", which trips command_not_recognized
        # and self-poisons station_ok (audit F2, 2026-09-19).
        _cmds += ["foliage.DensityScale 0", "grass.DensityScale 0",
                  "grass.Enable 0", "ShowFlag.Foliage 0",
                  "foliage.DensityScale", "grass.DensityScale", "grass.Enable"]
    elif density_scale is not None:
        # DENSITY SWEEP (item 2). Set both foliage + grass density scale to N and
        # read both back. NOTE placed HISM foliage cannot exceed its authored
        # instance count -- foliage.DensityScale > 1 is a no-op on trees; only
        # landscape grass (procedural) regenerates denser. The GPUScene instance
        # count per run tells which lever actually moved. Same read-back machinery
        # as the hide path (audit F1 regex).
        _cmds += ["foliage.DensityScale %g" % density_scale,
                  "grass.DensityScale %g" % density_scale,
                  "foliage.DensityScale", "grass.DensityScale", "grass.Enable"]
    elif hide_hlod:
        # HLOD-SHARE A/B (item 3d). Disable HLOD rendering; the GPU p90 delta vs
        # an as-is run is the HLOD proxy share. r.HLOD covers the legacy system;
        # wp.Runtime.HLOD covers World Partition HLOD (this world is partitioned).
        # Read both back. If a cvar is unregistered the log shows it and the
        # read-back is None (safe: reported not-honoured, not a false zero).
        _cmds += ["r.HLOD 0", "wp.Runtime.HLOD 0", "r.HLOD", "wp.Runtime.HLOD"]
    elif force_lod is not None or dithered_lod is not None:
        # T1 LADDER A/B. foliage.ForceLOD / foliage.DitheredLOD are CVARs (unlike
        # wp.Runtime.HLOD), so startup -ExecCmds delivery holds. Set, then bare
        # re-query for read-back (rule 12/13). arm A: --dithered-lod 0 only.
        # arm B: --force-lod 2 --dithered-lod 0.
        if force_lod is not None:
            _cmds += ["foliage.ForceLOD %d" % force_lod]
        if dithered_lod is not None:
            _cmds += ["foliage.DitheredLOD %d" % dithered_lod]
        if force_lod is not None:
            _cmds += ["foliage.ForceLOD"]
        if dithered_lod is not None:
            _cmds += ["foliage.DitheredLOD"]
    # Brief 5 T4 step 2: arbitrary cvar levers (r.Shadow.RadiusThreshold,
    # r.Shadow.DistanceScale, r.Nanite.MaxPixelsPerEdge, ...) via startup
    # -ExecCmds. Each "name value" is SET, then the bare "name" is re-queried so
    # the log carries the applied value for read-back (rule 12: applied + read
    # back, never declared-only). Format per item: "r.Shadow.RadiusThreshold 0.03".
    for _cv in (set_cvars or []):
        _cv = _cv.replace("=", " ").strip()
        _name = _cv.split()[0]
        _cmds += [_cv, _name]
    _cmds += [
        # In-engine VRAM cross-check beside the nvidia-smi poll (non-negotiable
        # 8: two instruments, different representations). GPUCsvStatsEnable
        # asks the CsvProfiler to emit GPU-memory columns; the exact column
        # names vary by build, so the reader below takes whatever "*MB" GPU
        # columns appear and reports ABSENT rather than a number if none do.
        "r.GPUCsvStatsEnable 1",
        "CsvProfile frames=%d" % FRAMES,
    ]
    exec_cmds = ",".join(_cmds)
    cmd = [UE_EXE, UPROJECT, "/Game/Alpine8K",
           "-game", "-windowed",
           "-ResX=%d" % RES_X, "-ResY=%d" % RES_Y,
           "-ExecCmds=%s" % exec_cmds,
           "-nosplash", "-NoLoadingScreen",
           "-AbsLog=%s" % os.path.join(LOG_DIR, log_name)]
    # `-csvGpuStats` (item 1): the CsvProfiler then emits per-pass GPU-TIME
    # columns (the "GPU/<pass>" stat group from FRealtimeGPUProfiler), which
    # r.GPUCsvStatsEnable alone did NOT produce (it gave GPU-memory only).
    # This is the -game per-pass attribution instrument for the 7.1 ms.
    if csv_gpu_stats:
        cmd.append("-csvGpuStats")
    # ⛔ DIAGNOSTIC LEVER, NOT A MEASUREMENT KNOB. `-LocalDataCachePath` is
    # the documented command-line override of the `Local` DDC backend
    # (BaseEngine.ini:2866, CommandLineOverride=LocalDataCachePath). It exists
    # here ONLY to answer whether the 2026-09-14 pre-LoadMap hang follows the
    # cache: five launches against C:\UnrealDDC hung at engine init with 0.3 s
    # of CPU in 20 s, and the one log line unique to those runs was that
    # cache's maintenance pass. A run using this flag measures a DIFFERENT
    # DDC than the ratified runs and its timings are NOT comparable to them.
    if local_ddc_path:
        cmd.append("-LocalDataCachePath=%s" % local_ddc_path)
    # `-noxgecontroller`: `hlod_build_batched.base_args` calls this MANDATORY
    # for commandlets on this machine -- without it shader jobs go to a local
    # IncrediBuild that never returns them (R-HLOD 08d,
    # XGEControllerModule.cpp:97-111). This launcher has NEVER passed it, and
    # both the 2026-09-11 runs that WORKED and the 2026-09-14 runs that hung
    # log `Using XGE Controller for shader compilation`. So its absence is not
    # what distinguishes them -- but the XGE path is still the dispatcher that
    # wedged, and this flag bypasses it. Diagnostic until proven.
    if noxge:
        cmd.append("-noxgecontroller")
    # `-NoRemoteShaderCompile`: the engine-level switch for the same outcome,
    # with no plugin dependency -- FShaderCompilingManager::IsRemoteCompilingEnabled
    # gates ALL distributed backends on it, where -noxgecontroller disables only
    # the XGE controller plugin. Compared head to head 2026-09-14.
    if no_remote_shader:
        cmd.append("-NoRemoteShaderCompile")
    rec = {"zone": zone, "label": label, "hide_foliage": hide_foliage,
           "density_scale": density_scale, "hide_hlod": hide_hlod,
           "csv_gpu_stats": csv_gpu_stats,
           "cmd": cmd, "exec_cmds": exec_cmds,
           "camera": {"x_cm": x, "y_cm": y, "z_cm": z,
                      "pitch_deg": pitch, "yaw_deg": yaw},
           "requested_res": [RES_X, RES_Y]}
    if dry:
        rec["dry_run"] = True
        return rec

    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    # DWELL FOR A FIXED WALL TIME. DO NOT RACE THE FILE.
    #
    # The previous version polled for the CSV to exist with size > 0 and then
    # terminated. The profiler writes INCREMENTALLY, so that caught a
    # PARTIAL file about 8 s in and the kill truncated the capture -- and
    # those 8 s were the level load, carrying a 4,626 ms GameThread hitch. It
    # looked like a completed measurement.
    #
    # Dwelling a fixed time needs no assumption about the profiler's flush
    # behaviour: let the world load and settle, keep running well past that,
    # then stop and take the TAIL.
    deadline = t0 + settle_s + MIN_WINDOW_S + MARGIN_S
    # VRAM window: a wall-clock SUPERSET of the timing tail. The timings use
    # the last MIN_WINDOW_S of frames; this window starts MARGIN_S earlier
    # (== t0 + settle_s), so it is wider at the front. That is conservative for
    # a ceiling check -- a superset can only over-report the peak vs the abort
    # ceiling, never under -- and it needs no assumption about the exact frame
    # the timing tail begins at. Sample nvidia-smi through the dwell.
    window_start_wall = deadline - (MIN_WINDOW_S + MARGIN_S)
    vram_samples = []
    while time.time() < deadline:
        m = gpu_mem_used_mib()
        if m is not None:
            vram_samples.append((time.time(), m))
        time.sleep(5.0)
        if proc.poll() is not None:
            break
    rec["dwell_s"] = round(time.time() - t0, 1)
    rec["vram_mib"] = _vram_reduce(vram_samples, window_start_wall)
    if rec["vram_mib"] is None:
        rec["vram_note"] = ("nvidia-smi produced no sample (absent or errored) "
                            "-- VRAM UNMEASURED this run, not zero (rule 13).")
    csv_path = mfc._newest_csv(before)
    try:
        proc.terminate()
        proc.wait(timeout=60)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    # ---- read the LOG back: did the console accept BugItGo, and at what res?
    lp = os.path.join(LOG_DIR, log_name)
    if not os.path.exists(lp):
        lp = newest_log()
    rec["log"] = os.path.relpath(lp, REPO_ROOT) if lp else None
    if lp and os.path.exists(lp):
        txt = open(lp, "r", encoding="utf-8", errors="replace").read()
        # ---- RESOLUTION, from the ENGINE, not from my own command line ----
        # The CsvProfiler writes `systemresolution.resx/resy` as metadata. The
        # first version regexed `ResX=(\d+)` and matched the COMMAND LINE the
        # log echoes verbatim, reporting [3840, 2160] over a 1280x720 run.
        # That is reading back my own input -- the same class of error as
        # trusting a MaterialInstanceDynamic's parameter getter.
        mres = re.findall(
            r'systemresolution\.resx="(\d+)".*?systemresolution\.resy="(\d+)"',
            txt, re.S)
        rec["viewport_res_readback"] = ([int(mres[-1][0]), int(mres[-1][1])]
                                        if mres else None)
        rec["res_matches_request"] = (
            rec["viewport_res_readback"] == [RES_X, RES_Y])
        setres = re.findall(r"Set CVar \[\[r\.setres:(\d+)x(\d+)", txt)
        rec["config_setres_seen"] = ([int(setres[-1][0]), int(setres[-1][1])]
                                     if setres else None)

        # CAMERA MOVE is NOT verifiable in-process: `getall PlayerController
        # Location` prints nothing (Location is not reflected), so the old
        # regex here was permanently dead (locs always empty -> camera_moved
        # always None) -- a null verification that read as if it fired. Removed;
        # camera placement is checked by cross-station differentiation in main().
        rec["command_not_recognized"] = bool(
            re.search(r"[Cc]ommand not recognized", txt))

        # FOLIAGE-HIDE READ-BACK. When a bare cvar name is issued the engine
        # logs `<name> = <value>`. Parse the LAST such line per cvar so the
        # record proves the hide was honoured, not merely requested (rule 13).
        if force_lod is not None or dithered_lod is not None:
            def _read2(cv):
                mm = re.findall(re.escape(cv) + r'\s*=\s*"?([-\d.eE+]+)"?', txt)
                return mm[-1] if mm else None

            def _eq2(v, t):
                try:
                    return abs(float(v) - t) < 1e-6
                except (TypeError, ValueError):
                    return False
            lb = {}
            oks = []
            if force_lod is not None:
                lb["foliage.ForceLOD"] = _read2("foliage.ForceLOD")
                oks.append(_eq2(lb["foliage.ForceLOD"], force_lod))
            if dithered_lod is not None:
                lb["foliage.DitheredLOD"] = _read2("foliage.DitheredLOD")
                oks.append(_eq2(lb["foliage.DitheredLOD"], dithered_lod))
            lb["_honoured"] = all(oks) if oks else None
            rec["lod_lever_readback"] = lb
        if hide_foliage or density_scale is not None or hide_hlod:
            # The engine echoes a bare-cvar query as `name = "value"` -- the
            # value is QUOTED (ConsoleManager.cpp:3230/:3247). A `[-\d.]+`
            # capture cannot start at the `"`, so it parsed 0 of 3 every run
            # (audit F1). Quote-tolerant capture, last match, None->unhonoured.
            def _eq(v, target):
                try:
                    return abs(float(v) - target) < 1e-6
                except (TypeError, ValueError):
                    return False

            def _read(cv):
                mm = re.findall(re.escape(cv) + r'\s*=\s*"?([-\d.eE+]+)"?', txt)
                return mm[-1] if mm else None
            hb = {}
            if hide_hlod:
                # HLOD A/B (item 3d). Honoured if EITHER HLOD lever read back 0;
                # this world is partitioned, so wp.Runtime.HLOD is load-bearing.
                for cv in ("r.HLOD", "wp.Runtime.HLOD"):
                    hb[cv] = _read(cv)
                hb["_parsed_n"] = "%d/2" % sum(
                    hb[c] is not None for c in ("r.HLOD", "wp.Runtime.HLOD"))
                hb["_honoured"] = (_eq(hb["r.HLOD"], 0.0)
                                   or _eq(hb["wp.Runtime.HLOD"], 0.0))
            else:
                for cv in ("foliage.DensityScale", "grass.DensityScale",
                           "grass.Enable"):
                    hb[cv] = _read(cv)
                hb["_parsed_n"] = "%d/3" % sum(hb[c] is not None for c in (
                    "foliage.DensityScale", "grass.DensityScale", "grass.Enable"))
                if hide_foliage:
                    hb["ShowFlag.Foliage"] = (
                        "issued as ShowFlag.Foliage 0 (no getter; read-back is "
                        "the GPU delta + no 'not recognized')")
                    # grass.DensityScale is belt to grass.Enable's braces; Enable
                    # 0 subsumes it, so the verdict gates on foliage.DensityScale
                    # + grass.Enable (audit F5). Its parsed value is recorded.
                    hb["_honoured"] = (_eq(hb["foliage.DensityScale"], 0.0)
                                       and _eq(hb["grass.Enable"], 0.0))
                else:
                    # density sweep: both scales must read back == N.
                    hb["_target"] = density_scale
                    hb["_honoured"] = (
                        _eq(hb["foliage.DensityScale"], density_scale)
                        and _eq(hb["grass.DensityScale"], density_scale))
            rec["foliage_hide_readback"] = hb

        # RESIDENCY (World Partition). perf_budgets.json requires residency to
        # be declared on a partitioned world (measure_frame_cost REFUSES exit 6
        # otherwise): a cost number taken with regions unloaded measures an
        # emptier world. In -game there is no Python channel and ExecCmds fires
        # once at startup, so a steady-state resident-cell COUNT is not in the
        # default log. What IS provable from the log: the game world's WP
        # initialized and generated its streaming grid -- i.e. the world is
        # STREAMED (bounded by the declared loading range), not monolithically
        # loaded. Recorded as evidence with its limit, not as a cell count.
        _wp = bool(re.search(
            r"UWorldPartition::Initialize : World = /Game/Alpine8K\.Alpine8K"
            r".*?World Type = Game", txt))
        _gen = "GenerateStreaming for 'Alpine8K'" in txt
        rec["residency"] = {
            "wp_initialized_game": _wp,
            "generate_streaming_seen": _gen,
            "streaming_active": bool(_wp and _gen),
            "_source": "log markers (LogWorldPartition)",
            "_limit": "the default -game log carries WP Initialize + "
                      "GenerateStreaming but NOT a steady-state resident-cell "
                      "count; this proves the world is STREAMED and bounded by "
                      "the declared loading range, not that N cells were "
                      "resident. A cell count needs LogWorldPartition Verbose "
                      "or a wp.Runtime dump, neither reachable via startup-only "
                      "ExecCmds.",
        }

    if not csv_path:
        rec["error"] = "no CSV appeared within the window"
        return rec

    dst = os.path.join(outdir, "%s.csv" % label)
    shutil.copy2(csv_path, dst)
    rec["csv"] = os.path.relpath(dst, REPO_ROOT)

    # ---- frame timeline, to convert the warmup into a row count -----------
    full = mfc._reduce(dst)
    ft = full.get("FrameTime")
    if not ft:
        rec["error"] = "CSV carries no FrameTime column"
        return rec
    # TAKE THE TAIL, NOT A FIXED WARMUP SKIP.
    #
    # The first attempt dropped `WARMUP_S` worth of frames from the front and
    # left NOTHING: the whole capture was 755 frames of startup, because at
    # 720p during load the engine outran the requested frame count before the
    # world was up. Selecting the LAST MIN_WINDOW_S of the capture needs no
    # assumption about when loading finished -- the tail is steady state by
    # construction, and if the capture is too short to contain a full window
    # that is reported rather than averaged over whatever arrived.
    mean_ms = ft["mean"]
    rec["frames_total"] = ft["n"]
    want = int(MIN_WINDOW_S * 1000.0 / mean_ms) if mean_ms > 0 else ft["n"]
    skip = max(0, ft["n"] - want)
    rec["frames_dropped_from_front"] = skip
    remaining = ft["n"] - skip
    rec["window_s_measured"] = round(remaining * mean_ms / 1000.0, 1)
    rec["window_ok"] = rec["window_s_measured"] >= MIN_WINDOW_S * 0.95
    rec["capture_s_total"] = round(ft["n"] * mean_ms / 1000.0, 1)
    # NN13: if the tail window collapsed to zero frames, do not emit stats_ms
    # -- a mean over zero samples is not a measurement.
    if remaining <= 0:
        rec["error"] = "measured window is empty (%d frames)" % remaining
        return rec
    stats = mfc._reduce(dst, skip_frames=skip)
    rec["stats_ms"] = {k: {kk: round(vv, 3) for kk, vv in v.items()}
                       for k, v in stats.items() if k in COLUMNS}
    # In-engine GPU-memory cross-check (best-effort; ABSENT if the build wrote
    # no such columns). nvidia-smi vram_mib remains the VRAM instrument of
    # record; this is a second, engine-internal view when available.
    _gm = gpu_mem_from_csv(dst)
    rec["gpu_mem_csv"] = _gm or {
        "_absent": "no GPU-memory columns in the CSV -- r.GPUCsvStatsEnable "
                   "may be a no-op on this build. nvidia-smi vram_mib is the "
                   "VRAM instrument of record."}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join("_verify", "perf"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="one zone name")
    ap.add_argument("--set-cvar", action="append", default=[],
                    help="Brief 5 T4: an extra cvar lever to set at -game startup "
                         "via -ExecCmds, e.g. --set-cvar 'r.Shadow.RadiusThreshold "
                         "0.03'. Repeatable. Each is set and re-queried for "
                         "read-back. Cvar-only; writes no .ini/.uasset.")
    ap.add_argument("--settle", type=float, default=SETTLE_S,
                    help="seconds to let the world load and settle BEFORE the "
                         "measured window. The default assumes a WARM DDC. On "
                         "a cold cache the first station spends its whole "
                         "dwell compiling shaders -- measured 2026-09-08: "
                         "8,263 jobs still dispatching at expiry and no CSV "
                         "was ever written.")
    ap.add_argument("--local-ddc-path", default=None,
                    help="DIAGNOSTIC ONLY: override the Local DDC backend "
                         "path for this run. A run using this measures a "
                         "DIFFERENT cache, so its timings are NOT comparable "
                         "to the ratified runs.")
    ap.add_argument("--no-remote-shader-compile", action="store_true",
                    help="add -NoRemoteShaderCompile: disables ALL distributed "
                         "shader backends at the engine level, no plugin "
                         "dependency.")
    ap.add_argument("--noxgecontroller", action="store_true",
                    help="add -noxgecontroller to the -game launch, bypassing "
                         "the XGE shader dispatcher. Diagnostic for the "
                         "2026-09-14 pre-LoadMap hang.")
    ap.add_argument("--hide-foliage", action="store_true",
                    help="Brief 5 Task 0 item 2: append foliage.DensityScale 0 "
                         "+ grass.DensityScale 0 + grass.Enable 0 + "
                         "r.ShowFlag.Foliage 0, and read the cvars back. The "
                         "GPU p90 delta vs the as-is run is the foliage cost.")
    ap.add_argument("--tag", default="",
                    help="suffix for the log/csv name, so an as-is and a "
                         "hidden run of the same zone do not collide "
                         "(e.g. --tag hidden).")
    ap.add_argument("--density-scale", type=float, default=None,
                    help="Brief 5 item 2 density sweep: set foliage.DensityScale "
                         "and grass.DensityScale to this value and read both "
                         "back. NOTE placed HISM foliage cannot exceed its "
                         "authored count (>1 is a no-op on trees); only "
                         "landscape grass regenerates denser. Mutually "
                         "exclusive with --hide-foliage.")
    ap.add_argument("--hide-hlod", action="store_true",
                    help="Brief 5 item 3d HLOD-share A/B: append r.HLOD 0 + "
                         "wp.Runtime.HLOD 0. WARNING (v3 2026-09-20): this does "
                         "NOT WORK as an HLOD-share instrument. wp.Runtime.HLOD "
                         "is an FAutoConsoleCommand (HLODRuntimeSubsystem.cpp:149) "
                         "delivered via startup -ExecCmds (one-shot, fires before "
                         "the far cells stream); as-is vs hidden are byte-identical "
                         "on every render counter (GPUSceneInstanceCount, "
                         "SceneCulling/NumStaticInstances, ActorCount/"
                         "WorldPartitionHLOD, GPUTime). The GPU p90 delta is NOT "
                         "the HLOD share. Needs a post-settle channel (-game MRQ). "
                         "See research/brief5/input/hlod_task2_gamepath.md.")
    ap.add_argument("--csv-gpu-stats", action="store_true",
                    help="Brief 5 item 1: add -csvGpuStats so the CsvProfiler "
                         "emits per-pass GPU-TIME columns (GPU/<pass>).")
    ap.add_argument("--station-json", default=None,
                    help="Brief 5 v3 Task 3: path to a JSON carrying a 'camera' "
                         "{x_cm,y_cm,z_cm,pitch_deg,yaw_deg}. Runs ONE custom "
                         "station (label from --station-name) INSTEAD of the "
                         "ratified spline. Does not touch perf_budgets.json; the "
                         "z is recomputed as heightmap+eye, identical to the "
                         "spline path (the custom z_cm is used only as a check).")
    ap.add_argument("--station-name", default="custom",
                    help="label for the --station-json custom station.")
    ap.add_argument("--force-lod", type=int, default=None,
                    help="Brief 5 T1: append foliage.ForceLOD N (cvar, -1=auto; "
                         "HISM.cpp:48). Forces every foliage instance to LOD N -- "
                         "arm B holds geometry over the card. Read back.")
    ap.add_argument("--dithered-lod", type=int, default=None,
                    help="Brief 5 T1: append foliage.DitheredLOD N (cvar, "
                         "HISM.cpp:69). Set 0 in BOTH arms (UE-46298: dithered LOD "
                         "renders wrong under ForceLOD). Read back.")
    a = ap.parse_args()
    _modes = sum([a.hide_foliage, a.density_scale is not None, a.hide_hlod])
    if _modes > 1:
        ap.error("--hide-foliage / --density-scale / --hide-hlod are mutually "
                 "exclusive")
    if (a.force_lod is not None or a.dithered_lod is not None) and _modes:
        ap.error("--force-lod / --dithered-lod are for the T1 ladder A/B; not "
                 "combinable with the hide/density/hlod levers")

    budgets = json.load(open(os.path.join(REPO_ROOT, "recipes",
                                          "perf_budgets.json"),
                             encoding="utf-8-sig"))
    recipe = json.load(open(os.path.join(REPO_ROOT, "recipes",
                                         "alpine_8k.json"),
                            encoding="utf-8-sig"))
    spline = budgets["spline"]
    eye = float(spline.get("eye_height_cm", EYE_CM))
    # Brief 5 v3 Task 3: a custom forest_floor station, WITHOUT editing the
    # ratified perf_budgets.json (it is law). z is recomputed heightmap+eye
    # below, exactly as for a spline station, so the derived z_cm (which was
    # itself heightmap+eye) is only a cross-check, not a second code path.
    if a.station_json:
        _sj = json.load(open(a.station_json, encoding="utf-8"))
        _c = _sj["camera"]
        spline = dict(spline)
        spline["stations"] = [{"zone": a.station_name,
                               "xy_cm": [_c["x_cm"], _c["y_cm"]],
                               "pitch_deg": _c["pitch_deg"],
                               "yaw_deg": _c["yaw_deg"],
                               "_z_cm_check": _c.get("z_cm")}]
    # The DECLARED residency parameter: the world's WP loading range. check_perf
    # matches an artefact to the world by this same key, so recording it makes
    # the perf run self-describing about the residency it was taken at.
    loading_range_cm = (recipe.get("streaming") or {}).get(
        "main_loading_range_cm")

    # The subdir used to be the HARDCODED literal "standalone_2026-09-07"
    # -- a date baked into the tool, so every later run masqueraded as
    # the 09-07 one (caught 2026-09-10 when the range sweeps landed in
    # oddly-named nests). The artefact's identity now comes from the run.
    import datetime as _dt
    outdir = os.path.join(REPO_ROOT, a.outdir,
                          "standalone_" + _dt.date.today().isoformat())
    os.makedirs(outdir, exist_ok=True)

    out = {
        "_what": "E3: frame cost measured in a STANDALONE -game process, at "
                 "the four ratified perf stations.",
        "_not_a_ratification": "recipes/perf_budgets.json is LAW and is "
                               "untouched. This is a second instrument "
                               "reported beside it. Whether any budget should "
                               "move is an operator decision.",
        "engine": UE_EXE, "project": UPROJECT, "level": "/Game/Alpine8K",
        "requested_res": [RES_X, RES_Y], "fov_h_deg": spline.get(
            "fov_horizontal_deg"),
        "_fov_h_deg_note": ("declared from the spline but NOT applied to the "
                            "-game process (BugItGo/ExecCmds set no FOV) and "
                            "NOT read back -- it is the engine default here; "
                            "treat this value as prose, not a measurement "
                            "(rule 12)."),
        "eye_height_cm": eye,
        "settle_s": a.settle, "margin_s": MARGIN_S,
        "local_ddc_path_override": a.local_ddc_path,
        "noxgecontroller": a.noxgecontroller,
        "no_remote_shader_compile": a.no_remote_shader_compile,
        "min_window_s": MIN_WINDOW_S,
        "frames_requested": FRAMES,
        "declared_loading_range_cm": loading_range_cm,
        "_residency_note": ("VRAM peak is measured per station (nvidia-smi poll "
                            "over the steady-state window, vs the "
                            "%d MiB abort ceiling) and an in-engine GPU-mem CSV "
                            "cross-check is attempted; WP streaming-active is "
                            "read from each station's log. This closes the T11 "
                            "rule-12 gap (the tool declared no VRAM/residency). "
                            "A steady-state resident-cell COUNT is still not "
                            "reachable via startup-only ExecCmds in -game."
                            % VRAM_ABORT_MIB),
        "z_source": "heightmap-derived + eye height; a PLACEMENT AID, not a "
                    "trace. perf_budgets.json requires an in-editor trace; "
                    "the measured gap at near_ground is 2.3 cm and the "
                    "standalone pawn collides.",
        "camera_command": "BugItGo (not ViewActor): it takes the ratified "
                          "coordinates directly and needs no named camera "
                          "actor. The log is checked for the echo AND for "
                          "'not recognized'.",
        "zones": {},
    }

    for st in spline["stations"]:
        zone = st["zone"]
        if a.only and zone != a.only:
            continue
        x, y = st["xy_cm"]
        z = heightmap_z(x, y, recipe) + eye
        rec = run_station(zone, x, y, z, st["pitch_deg"], st["yaw_deg"],
                          outdir, dry=a.dry_run, settle_s=a.settle,
                          local_ddc_path=a.local_ddc_path,
                          noxge=a.noxgecontroller,
                          no_remote_shader=a.no_remote_shader_compile,
                          hide_foliage=a.hide_foliage, tag=a.tag,
                          density_scale=a.density_scale,
                          hide_hlod=a.hide_hlod, csv_gpu_stats=a.csv_gpu_stats,
                          force_lod=a.force_lod, dithered_lod=a.dithered_lod,
                          set_cvars=a.set_cvar)
        # Per-station verdict: stats alone are NOT success. The resolution must
        # match the request, no command may have been rejected, and the window
        # must be long enough -- all computed already but previously ignored.
        if "stats_ms" in rec:
            rec["station_ok"] = bool(rec.get("window_ok")
                                     and rec.get("res_matches_request")
                                     and not rec.get("command_not_recognized"))
        else:
            rec["station_ok"] = False
        out["zones"][zone] = rec
        if a.dry_run:
            print("  %-12s DRY" % zone)
        elif "stats_ms" not in rec:
            print("  %-12s %s" % (zone, rec.get("error")))
        else:
            _g = (rec.get("stats_ms", {}).get("GPUTime") or {}).get("p90")
            _t = (rec.get("stats_ms", {}).get("GameThreadTime") or {}).get("p90")
            _vr = (rec.get("vram_mib") or {}).get("peak_mib")
            print("  %-12s %-8s window %.1f s  GPU p90 %s  Game p90 %s  "
                  "VRAM peak %s MiB"
                  % (zone, "ok" if rec["station_ok"] else "SUSPECT",
                     rec.get("window_s_measured", 0), _g, _t,
                     _vr if _vr is not None else "n/a"))
            if not rec["station_ok"]:
                print("       ^ res_match=%s cmd_not_recognized=%s window_ok=%s"
                      % (rec.get("res_matches_request"),
                         rec.get("command_not_recognized"),
                         rec.get("window_ok")))

    # A RUN THAT MEASURED NOTHING MUST NOT OVERWRITE A RUN THAT DID.
    #
    # Measured 2026-09-08, twice in ten minutes. First: every station returned
    # "no CSV appeared" on a cold DDC -- I had emptied it hours earlier to free
    # 92 GB -- and the sidecar was rewritten with four empty records, wiping a
    # complete result. Second: a `--dry-run --only plaza` wrote a single
    # dry_run record over the restored file. Git had it both times, and rule 3
    # earned its keep, but a tool should not need rescuing from itself.
    #
    # A dry run writes NOTHING: it exists to show what would be launched.
    # CROSS-STATION DIFFERENTIATION -- the only camera-move check available
    # (see the module docstring). If two or more stations' GPU p90 come back
    # near-identical, BugItGo likely moved nothing and every station measured
    # the same view.
    _p90 = [(z, (r.get("stats_ms", {}).get("GPUTime") or {}).get("p90"))
            for z, r in out["zones"].items()]
    _p90 = [(z, v) for z, v in _p90 if isinstance(v, (int, float))]
    out["camera_differentiation"] = None
    if len(_p90) >= 2:
        _vals = [v for _, v in _p90]
        _spread = (max(_vals) - min(_vals)) / max(min(_vals), 1e-6)
        out["gpu_p90_spread_frac"] = round(_spread, 4)
        if _spread < 0.02:
            out["camera_differentiation"] = (
                "SUSPECT: %d stations' GPU p90 agree within %.1f%% -- BugItGo "
                "may not have moved the camera" % (len(_p90), 100 * _spread))

    # VRAM SUMMARY across stations, vs the abort ceiling (the T11 acceptance
    # line). Peak of each station's steady-state-window peak where available,
    # else its dwell peak. None if no station got a sample.
    _peaks = []
    for r in out["zones"].values():
        vm = r.get("vram_mib")
        if isinstance(vm, dict):
            p = vm.get("peak_window_mib") or vm.get("peak_mib")
            if isinstance(p, int):
                _peaks.append(p)
    if _peaks:
        _mx = max(_peaks)
        out["vram_summary"] = {
            "peak_mib": _mx,
            "abort_ceiling_mib": VRAM_ABORT_MIB,
            "physical_mib": VRAM_PHYSICAL_MIB,
            "headroom_to_abort_mib": VRAM_ABORT_MIB - _mx,
            "over_abort_ceiling": _mx > VRAM_ABORT_MIB,
            "n_stations_measured": len(_peaks),
        }
        print("VRAM peak across stations: %d MiB vs %d abort (%+d headroom)%s"
              % (_mx, VRAM_ABORT_MIB, VRAM_ABORT_MIB - _mx,
                 "  ** OVER ABORT CEILING **" if _mx > VRAM_ABORT_MIB else ""))
    else:
        out["vram_summary"] = None
        print("VRAM: no nvidia-smi sample on any station (UNMEASURED, not zero)")

    # Sidecar name carries the tag so a same-day as-is and hidden A/B pair do
    # not overwrite each other (audit F3 -- only the CSVs were tag-named, the
    # sidecar was always perf_standalone.json, so the second run clobbered the
    # first's VRAM/read-back/verdict).
    dest = os.path.join(outdir, "perf_standalone%s.json"
                        % (("_" + a.tag) if a.tag else ""))
    if a.dry_run:
        print("dry run: no sidecar written")
        return 0
    measured = [z for z in out["zones"].values() if z.get("stats_ms")]
    if not measured:
        # Nothing measured must NEVER exit 0, whether or not a prior file
        # exists -- and it must not overwrite a good prior result.
        if os.path.exists(dest):
            print("REFUSING to write %s: no station produced data and a result "
                  "already exists there. Nothing measured, nothing overwritten."
                  % os.path.relpath(dest, REPO_ROOT))
        else:
            with open(dest, "w", encoding="utf-8") as fh:
                json.dump(out, fh, indent=2)
            print("wrote %s (NO station measured)"
                  % os.path.relpath(dest, REPO_ROOT))
        for k, v in out["zones"].items():
            print("    %-12s %s" % (k, v.get("error") or "no stats"))
        return 1
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote %s" % os.path.relpath(dest, REPO_ROOT))
    # A measured run is not a clean run: a station that failed its own checks,
    # or a suspect cross-station spread, must reach the exit code.
    _suspect = [z for z, r in out["zones"].items()
                if r.get("stats_ms") and not r.get("station_ok")]
    if _suspect or out["camera_differentiation"]:
        if _suspect:
            print("SUSPECT stations (measured but failed their own checks): %s"
                  % ", ".join(_suspect))
        if out["camera_differentiation"]:
            print(out["camera_differentiation"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
