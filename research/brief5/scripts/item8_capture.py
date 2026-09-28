#!/usr/bin/env python3
"""item8_capture.py -- Item-8 HLOD-share driver: build scratch MRQ assets,
render the A/A/B `-game` MRQ pairs, clean up, and prove the world byte-identical.

PHASES (each launch is gated on ZERO editors first -- rule 11):
  0  census BEFORE (offline; world is clean at session start)
  1  BUILD:  launch editor on /Game/Alpine8K, ue_exec item8_build.py to create +
             save /Game/Scratch/Item8/{LS_vista,LS_treeline,Cfg_A,Cfg_B,
             Cfg_A_lo,Cfg_B_lo}; close by launched PID. The level is NEVER saved.
  2  RENDER: for each station in {vista, treeline} x arm in {A1, A2, B}, launch a
             `-game` MRQ command-line render (UnrealEditor-Cmd.exe ... -game
             -LevelSequence=... -MoviePipelineConfig=... -RenderOffScreen
             -csvGpuStats -ExecCmds="CsvProfile frames=..."). The in-process
             executor self-exits when the render completes
             (MovieRenderPipelineCommandLine.cpp:68/:114). VRAM is polled vs the
             13,312 MiB abort ceiling; the newest CsvProfiler CSV and the last
             output frame are collected per run.
  3  CLEANUP: launch editor, ue_exec item8_cleanup.py to delete
             /Game/Scratch/Item8/, close.
  4  census AFTER + compare -> byte-identical verdict.

GPU SAFETY (fence): a DEVICE_HUNG (device-removed in the log, or VRAM over the
abort ceiling) -> close all, wait 5 min, retry THAT render once at 1080p (the
_lo config). A SECOND DEVICE_HUNG -> stop all GPU work, keep proxy_fraction
0.05727 as the instrument of record, still run cleanup + census, write the
report. Renders are STRICTLY sequential (one GPU job at a time).

READ-ONLY on the shipped world: the only writes are /Game/Scratch/Item8/**,
created in phase 1 and deleted in phase 3; the census brackets prove it.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)
import bootstrap                                    # noqa: E402
import measure_frame_cost as mfc                    # noqa: E402
import ue_exec                                      # noqa: E402
import perf_standalone as ps                        # noqa: E402  (heightmap_z, VRAM)

UE_CMD = r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
UPROJECT = os.path.join(bootstrap.UE_PROJECT_ROOT, "LandscapeLab.uproject")
LOG_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Logs")
PAYLOADS = os.path.join(SCRIPTS, "payloads")
CENSUS = os.path.join(os.path.dirname(__file__), "item8_census.py")

OUT = os.path.join(REPO, "_verify", "perf", "item8")
ACTIVE = os.path.join(OUT, "_active")
DERIVED = os.path.join(REPO, "research", "brief5", "derived", "item8")
INPUT = os.path.join(REPO, "research", "brief5", "input")

RES_4K = [3840, 2160]
RES_LO = [1920, 1080]
FRAMES = 60                 # output frames per render
WARMUP = 60                 # RENDERED warm-up frames (WP stream + GPU settle)
FOV_H = 90.0
EYE_CM = 175.0
VRAM_ABORT_MIB = ps.VRAM_ABORT_MIB          # 13312
RENDER_DEADLINE_S = 1200.0
VRAM_POLL_S = 5.0
COOLDOWN_S = 300.0          # 5 min after a DEVICE_HUNG (fence)

PY = sys.executable
LAUNCHED_PID = None
device_hung_count = [0]     # mutable box, module-level tally


# ----------------------------------------------------------------- editor mgmt
def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def editor_pids():
    r = _ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def launch_editor(map_path):
    global LAUNCHED_PID
    pre = editor_pids()
    if pre:
        print("REFUSE: %d editor(s) already running %s (rule 11)"
              % (len(pre), sorted(pre)))
        return False
    subprocess.Popen(["powershell", "-NoProfile", "-File",
                      os.path.join(SCRIPTS, "launch_editor.ps1"),
                      "-Map", map_path], cwd=REPO)
    t0 = time.time()
    while time.time() - t0 < 90:
        new = editor_pids() - pre
        if new:
            LAUNCHED_PID = sorted(new)[0]
            print("LAUNCHED editor PID", LAUNCHED_PID, "on", map_path)
            return True
        time.sleep(2)
    print("REFUSE: no new editor appeared within 90 s")
    return False


def wait_ready(timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("EDITOR READY", round(time.time() - t0, 1), "s")
            return True
        time.sleep(6)
    print("EDITOR NOT READY within", timeout, "s")
    return False


def close_editor():
    global LAUNCHED_PID
    if LAUNCHED_PID:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue"
            % LAUNCHED_PID)
    time.sleep(4)
    left = editor_pids()
    restore = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Autosaves",
                           "PackageRestoreData.json")
    info = {"launched_pid": LAUNCHED_PID,
            "pid_still_alive": LAUNCHED_PID in left if LAUNCHED_PID else None,
            "editors_after": sorted(left),
            "package_restore_data_present": os.path.exists(restore)}
    print("CLOSE", json.dumps(info))
    LAUNCHED_PID = None
    return info


def kill_all_editors():
    for pid in editor_pids():
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
    time.sleep(4)


# --------------------------------------------------------------------- census
def census(tag):
    path = os.path.join(OUT, "census_%s.json" % tag)
    r = subprocess.run([PY, CENSUS, "snapshot", path],
                       capture_output=True, text=True)
    print("CENSUS %s: %s" % (tag, (r.stdout or "").strip()))
    return path


def census_compare(before, after):
    r = subprocess.run([PY, CENSUS, "compare", before, after],
                       capture_output=True, text=True)
    print(r.stdout[-600:] if r.stdout else "(no compare output)")
    # re-run in-process to capture the structured verdict
    sys.path.insert(0, os.path.dirname(CENSUS))
    import item8_census as ic
    return ic.compare(json.load(open(before, encoding="utf-8")),
                      json.load(open(after, encoding="utf-8")))


# ---------------------------------------------------------------------- build
def stations():
    recipe = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                            encoding="utf-8-sig"))
    out = []
    for name, x, y, pitch, yaw in (("vista", -216400.0, 63600.0, -4.0, 60.0),
                                   ("treeline", -190000.0, 100000.0, -2.0, 105.0)):
        z = float(ps.heightmap_z(x, y, recipe)) + EYE_CM
        out.append({"name": name, "loc_cm": [float(x), float(y),
                                             round(float(z), 2)],
                    "pitch_deg": float(pitch), "yaw_deg": float(yaw)})
    return out


def build_phase():
    sts = stations()
    cfg = {
        "frames": FRAMES, "res": RES_4K, "fov_h_deg": FOV_H,
        "render_warm_up_count": WARMUP,
        "active_dir": ACTIVE.replace("\\", "/"),
        "stations": sts,
        "configs": [
            {"name": "Cfg_A", "hlod_off": False, "res": RES_4K},
            {"name": "Cfg_B", "hlod_off": True, "res": RES_4K},
            {"name": "Cfg_A_lo", "hlod_off": False, "res": RES_LO},
            {"name": "Cfg_B_lo", "hlod_off": True, "res": RES_LO},
        ],
    }
    text = open(os.path.join(PAYLOADS, "item8_build.py"),
                encoding="utf-8").read().replace(
        "__CONFIG_JSON__", json.dumps(cfg))
    if not launch_editor("/Game/Alpine8K"):
        return None, sts
    if not wait_ready():
        close_editor()                 # never leak a launched editor (rule 11)
        return None, sts
    code, parsed, raw = ue_exec.run(text, timeout=120,
                                    stage_name="item8_build")
    close_editor()
    print("BUILD ue_exec code", code, "ok",
          parsed.get("ok") if parsed else None)
    if parsed and not parsed.get("ok"):
        print("  BUILD verdict:", json.dumps(parsed.get("_verdict")))
        if parsed.get("error"):
            print("  BUILD error:", parsed.get("error"))
    json.dump(parsed or {"raw": raw[-1500:]},
              open(os.path.join(INPUT, "item8_build.json"), "w",
                   encoding="utf-8"), indent=1)
    return parsed, sts


# --------------------------------------------------------------------- render
def _seq_path(station):
    return "/Game/Scratch/Item8/LS_%s.LS_%s" % (station, station)


def _cfg_path(arm_hlod_off, lo):
    base = "Cfg_B" if arm_hlod_off else "Cfg_A"
    if lo:
        base += "_lo"
    return "/Game/Scratch/Item8/%s.%s" % (base, base)


def _log_has_device_hung(logpath):
    if not os.path.isfile(logpath):
        return False
    try:
        txt = open(logpath, encoding="utf-8", errors="replace").read()
    except Exception:
        return False
    for needle in ("DXGI_ERROR_DEVICE_REMOVED", "DXGI_ERROR_DEVICE_HUNG",
                   "Device removed", "GPU Crash", "D3D device being lost",
                   "DEVICE_HUNG"):
        if needle.lower() in txt.lower():
            return True
    return False


def render_one(station, arm, hlod_off, lo=False):
    """One `-game` MRQ render. Returns a record dict. Sequential; polls VRAM."""
    tag = "%s_%s%s" % (station, arm, "_lo" if lo else "")
    if editor_pids():
        return {"tag": tag, "error": "editors present before render (rule 11)"}
    # Empty the shared _active output dir WITHOUT a recursive/forced delete
    # (standing rule 2): move any leftover frames to _trash/ (git is the first
    # undo, _trash the second). No rmtree.
    os.makedirs(ACTIVE, exist_ok=True)
    stale = glob.glob(os.path.join(ACTIVE, "item8.*.png"))
    if stale:
        trash = os.path.join(REPO, "_trash", "item8_active_%s" % tag)
        os.makedirs(trash, exist_ok=True)
        for f in stale:
            try:
                os.replace(f, os.path.join(trash, os.path.basename(f)))
            except OSError:
                pass
    dest = os.path.join(OUT, tag)
    os.makedirs(dest, exist_ok=True)
    logpath = os.path.join(LOG_DIR, "item8_%s.log" % tag)
    csv_before = set(glob.glob(os.path.join(mfc.CSV_DIR, "*.csv")))
    os.makedirs(mfc.CSV_DIR, exist_ok=True)
    res = RES_LO if lo else RES_4K
    cmd = [
        UE_CMD, UPROJECT, "/Game/Alpine8K", "-game", "-windowed",
        "-ResX=%d" % res[0], "-ResY=%d" % res[1], "-RenderOffScreen",
        "-LevelSequence=%s" % _seq_path(station),
        "-MoviePipelineConfig=%s" % _cfg_path(hlod_off, lo),
        "-csvGpuStats", "-ExecCmds=CsvProfile frames=60000",
        "-nosplash", "-NoLoadingScreen", "-noxgecontroller",
        "-AbsLog=%s" % logpath,
    ]
    rec = {"tag": tag, "station": station, "arm": arm, "hlod_off": hlod_off,
           "res": res, "cmd": cmd, "cfg": _cfg_path(hlod_off, lo),
           "sequence": _seq_path(station)}
    print("RENDER", tag, "->", _cfg_path(hlod_off, lo))
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    vram_samples, hung, vram_over = [], False, False
    deadline = t0 + RENDER_DEADLINE_S
    while time.time() < deadline:
        m = ps.gpu_mem_used_mib()
        if m is not None:
            vram_samples.append((time.time(), m))
            if m > VRAM_ABORT_MIB:
                vram_over = True
                print("  VRAM %d MiB OVER abort ceiling %d -- killing render"
                      % (m, VRAM_ABORT_MIB))
                break
        if _log_has_device_hung(logpath):
            hung = True
            print("  DEVICE_HUNG marker in log -- killing render")
            break
        if proc.poll() is not None:
            break                                   # self-exit = render done
        time.sleep(VRAM_POLL_S)
    rec["dwell_s"] = round(time.time() - t0, 1)
    exited = proc.poll()
    if exited is None:
        try:
            proc.terminate(); proc.wait(timeout=60)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    rec["proc_exit"] = proc.poll()
    rec["vram_peak_mib"] = max((m for _, m in vram_samples), default=None)
    rec["vram_over_ceiling"] = vram_over
    rec["device_hung_marker"] = hung or _log_has_device_hung(logpath)
    rec["hung"] = bool(hung or vram_over or rec["device_hung_marker"])
    # collect the CSV + frames
    csv_new = mfc._newest_csv(csv_before)
    if csv_new:
        dst_csv = os.path.join(dest, "item8_%s.csv" % tag)
        shutil.copy2(csv_new, dst_csv)
        rec["csv"] = os.path.relpath(dst_csv, REPO).replace("\\", "/")
    else:
        rec["csv"] = None
    frames = sorted(glob.glob(os.path.join(ACTIVE, "item8.*.png")))
    rec["frames_written"] = len(frames)
    if frames:
        # MOVE every frame out of _active into dest/frames/ (preserves the
        # evidence AND empties _active for the next render -- no delete). The
        # last frame is also copied to dest/frame_last.png for the analysers.
        framedir = os.path.join(dest, "frames")
        os.makedirs(framedir, exist_ok=True)
        moved = []
        for f in frames:
            d = os.path.join(framedir, os.path.basename(f))
            try:
                os.replace(f, d)
                moved.append(d)
            except OSError:
                moved.append(f)
        last = moved[-1]
        dst_frame = os.path.join(dest, "frame_last.png")
        shutil.copy2(last, dst_frame)
        rec["last_frame"] = os.path.relpath(dst_frame, REPO).replace("\\", "/")
        rec["last_frame_name"] = os.path.basename(last)
        # N1: a swallowed os.replace could leave a stale frame in _active and
        # over-count frames_written; re-glob and refuse if any residual remains.
        residual = glob.glob(os.path.join(ACTIVE, "item8.*.png"))
        rec["active_residual"] = len(residual)
    else:
        rec["last_frame"] = None
        rec["active_residual"] = len(glob.glob(
            os.path.join(ACTIVE, "item8.*.png")))
    rec["log"] = os.path.relpath(logpath, REPO).replace("\\", "/") \
        if os.path.isfile(logpath) else None
    rec["ok"] = bool(rec["csv"] and frames and not rec["hung"]
                     and rec["frames_written"] >= FRAMES
                     and rec.get("active_residual", 0) == 0)
    print("  %s dwell %.0fs exit %s VRAMpeak %s frames %d csv %s hung %s"
          % (tag, rec["dwell_s"], rec["proc_exit"], rec["vram_peak_mib"],
             rec["frames_written"], bool(rec["csv"]), rec["hung"]))
    return rec


def render_with_safety(station, arm, hlod_off):
    """render_one wrapped in the fence GPU-safety protocol."""
    rec = render_one(station, arm, hlod_off, lo=False)
    if not rec.get("hung"):
        return [rec]
    device_hung_count[0] += 1
    print("!! DEVICE_HUNG #%d on %s. Closing all, cooling %ds."
          % (device_hung_count[0], rec["tag"], COOLDOWN_S))
    kill_all_editors()
    if device_hung_count[0] >= 2:
        print("!! SECOND DEVICE_HUNG -- stopping ALL GPU work (fence). "
              "0.05727 stays the instrument of record.")
        rec["safety_stop"] = True
        return [rec]
    time.sleep(COOLDOWN_S)
    print("   retry %s at 1080p (fence: 1080p only after one DEVICE_HUNG)"
          % rec["tag"])
    rec2 = render_one(station, arm, hlod_off, lo=True)
    if rec2.get("hung"):
        device_hung_count[0] += 1
        print("!! DEVICE_HUNG #%d on the 1080p retry -- stopping ALL GPU work."
              % device_hung_count[0])
        kill_all_editors()
        rec2["safety_stop"] = True
    return [rec, rec2]


def render_phase():
    runs = []
    stopped = False
    first = True
    for station in ("vista", "treeline"):
        for arm, hlod_off in (("A1", False), ("A2", False), ("B", True)):
            recs = render_with_safety(station, arm, hlod_off)
            runs.extend(recs)
            if any(r.get("safety_stop") for r in recs):
                stopped = True
                break
            # SMOKE GATE: if the very first render produced no valid frames and
            # did NOT hang, the sequence/config/camera is wrong -- abort before
            # spending five more GPU renders on a broken instrument (audit Q1).
            if first:
                first = False
                final = recs[-1]
                if not final.get("hung") and \
                        final.get("frames_written", 0) < FRAMES:
                    print("SMOKE GATE: first render wrote %d/%d frames and did "
                          "not hang -- aborting campaign (instrument defect, "
                          "not GPU). csv=%s" % (final.get("frames_written", 0),
                                                FRAMES, final.get("csv")))
                    stopped = True
                    break
        if stopped:
            break
    return runs, stopped


# -------------------------------------------------------------------- cleanup
def cleanup_phase():
    if not launch_editor("/Game/Alpine8K"):
        print("CLEANUP: could not launch editor -- Item8 scratch NOT deleted")
        return None
    if not wait_ready():
        close_editor()
        print("CLEANUP: editor not ready -- Item8 scratch NOT deleted")
        return None
    text = open(os.path.join(PAYLOADS, "item8_cleanup.py"),
                encoding="utf-8").read()
    code, parsed, raw = ue_exec.run(text, timeout=90,
                                    stage_name="item8_cleanup")
    close_editor()
    print("CLEANUP ue_exec code", code, "ok",
          parsed.get("ok") if parsed else None)
    json.dump(parsed or {"raw": raw[-1200:]},
              open(os.path.join(INPUT, "item8_cleanup.json"), "w",
                   encoding="utf-8"), indent=1)
    return parsed


# ------------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    os.makedirs(INPUT, exist_ok=True)
    manifest = {"_what": "Item-8 capture driver manifest.", "phases": {}}

    before = census("before")
    manifest["phases"]["census_before"] = before

    build, sts = build_phase()
    manifest["phases"]["build_ok"] = bool(build and build.get("ok"))
    manifest["stations"] = sts
    if not (build and build.get("ok")):
        print("BUILD FAILED -- aborting renders, running cleanup + census.")
        cleanup_phase()
        after = census("after")
        cmp = census_compare(before, after)
        manifest["phases"]["census_verdict"] = cmp["verdict"]
        _write_manifest(manifest)
        return 1

    runs, stopped = render_phase()
    manifest["phases"]["renders"] = runs
    manifest["phases"]["render_stopped_on_safety"] = stopped
    manifest["phases"]["device_hung_count"] = device_hung_count[0]

    cleanup = cleanup_phase()
    manifest["phases"]["cleanup_ok"] = bool(cleanup and cleanup.get("ok"))

    after = census("after")
    manifest["phases"]["census_after"] = after
    cmp = census_compare(before, after)
    manifest["phases"]["census_verdict"] = cmp["verdict"]
    manifest["phases"]["census_detail"] = {
        k: cmp[k] for k in ("added_non_scratch", "removed_non_scratch",
                            "stat_changed_non_scratch", "world_umap_identical",
                            "item8_scratch_present_after", "n_files_compared")}
    _write_manifest(manifest)
    # Judge only the FINAL attempt per (station, arm): a hung 4K attempt
    # superseded by a successful 1080p retry must not fail the campaign (audit
    # #13). runs are appended in order, so the last with a given (station, arm)
    # is the final attempt.
    final_by_arm = {}
    for r in runs:
        if r.get("station") and r.get("arm"):
            final_by_arm[(r["station"], r["arm"])] = r
    finals = list(final_by_arm.values())
    ok = (manifest["phases"]["census_verdict"].startswith("CLEAN")
          and bool(finals)
          and all(r.get("ok") for r in finals if not r.get("safety_stop")))
    print("\nITEM8 CAPTURE %s" % ("OK" if ok else "INCOMPLETE"))
    print("  census:", manifest["phases"]["census_verdict"])
    return 0 if ok else 1


def _write_manifest(manifest):
    p = os.path.join(INPUT, "item8_capture_manifest.json")
    json.dump(manifest, open(p, "w", encoding="utf-8"), indent=1)
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    sys.exit(main())
