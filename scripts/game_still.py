"""game_still.py -- one still from the STANDALONE GAME, not from the editor.

    python scripts/game_still.py --name treeline --x -190000 --y 100000 \
        --pitch -2 --yaw 105 --out-dir _verify/lookdev/game01
    (give the calling tool a timeout of at least --settle + 180 s)

WHY THIS EXISTS (LESSONS 2026-10-01c). An editor HighResShot shows the EDITOR
world: loaded foliage instances, which cull at 512 m, and no World Partition
HLOD. Everything past 512 m is therefore ABSENT from every editor still, at
any load state. Counted from foliage/alpine_8k_*.json on 2026-10-01: the
treeline view sector (+-45 deg) holds 38,968 planned trees between 1 and 2 km
and 126,615 between 2 and 4 km; the editor stills show bare ground there.
A look judgement of anything beyond the cull distance needs this instrument.

HOW. The launch is R-PERFSTANDALONE's (`-game -windowed`, camera by BugItGo,
`r.setRes` in -ExecCmds because -ResX/-ResY lose to config). `-game` has no
Python and no remote channel, and -ExecCmds fires once at startup, so nothing
inside the process can take a screenshot after the world has streamed in.
The frame is therefore taken from OUTSIDE: dwell a fixed wall time, bring the
game window to the foreground, copy its client rectangle off the screen.

WHAT IS READ BACK (rule 12), and what is not:
  * the captured size against the requested size, from the window itself,
    in PHYSICAL pixels (this process declares per-monitor DPI awareness
    first: the display runs at 150% and an unaware process is handed scaled
    coordinates -- LESSONS 16308, RECIPES 7295);
  * the foreground window's PID at capture;
  * the frame's luma mean / std on the 8-bit sRGB-ENCODED pixels (not
    comparable with R-LOOKDEV's display-linear numbers) -- black or flat
    REFUSES;
  * the engine's own `BugItGo to:` line, parsed and compared with the request.
    This proves the command RAN with these numbers. It does not prove where
    the camera ended up: pose_read_back stays false (R-PERFSTANDALONE
    REJECTED: searching the log for the word "BugItGo" passes whether or not
    it ran, because the command line is echoed);
  * the line DisableAllScreenMessages prints;
  * peak VRAM from nvidia-smi against the 13,312 MiB ceiling; over it the
    process is terminated at once, and a poll with NO sample refuses.
  NOT read back: the camera pose, and whether HLOD had finished streaming at
  the capture (hlod_residency_read_back false; --settle is an assumption).

THE WORLD THIS SHOWS IS THE ON-DISK ONE, i.e. the BENCH state: PPV_Look is
saved disabled and the sun at 12 degrees. The Look profile is editor-side
actor state plus cvars; this tool sets none of it. That gap is the point of
the label `bench_on_disk` on every frame.

A frame that fails any check is written as <name>.REJECTED.png.
Exit 0 only when a frame was written and every read-back agreed.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import bootstrap                                    # noqa: E402
import perf_standalone as ps                        # noqa: E402
import resource_guard                               # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
BUGITGO_RE = re.compile(
    r"BugItGo to:.*?X=(-?[\d.]+).*?Y=(-?[\d.]+).*?Z=(-?[\d.]+)")
SCREEN_MSG_LINE = "Onscreen warnings/messages are now DISABLED"

# A PRIVATE handle with declared types, so the shared windll.user32 is not
# reconfigured for every other module in the process.
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
_u32.GetWindowThreadProcessId.restype = wt.DWORD
_u32.IsWindowVisible.argtypes = [wt.HWND]
_u32.IsIconic.argtypes = [wt.HWND]
_u32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_u32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
_u32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
_u32.SetForegroundWindow.argtypes = [wt.HWND]
_u32.GetForegroundWindow.restype = wt.HWND
_u32.GetDpiForWindow.argtypes = [wt.HWND]
_u32.GetDpiForWindow.restype = wt.UINT
_u32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_u32.SetProcessDpiAwarenessContext.restype = wt.BOOL
_u32.keybd_event.argtypes = [wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_void_p]
_ENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
_u32.EnumWindows.argtypes = [_ENUMPROC, wt.LPARAM]


class _BASIC(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wt.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wt.DWORD),
                ("SchedulingClass", wt.DWORD)]


class _IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _EXTENDED(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BASIC), ("IoInfo", _IO),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


_k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int,
                                         ctypes.c_void_p, wt.DWORD]
_k32.SetInformationJobObject.restype = wt.BOOL
_k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
_k32.AssignProcessToJobObject.restype = wt.BOOL


def _kill_on_close_job(proc):
    """Tie `proc` to a job that dies with THIS process. If the calling tool
    kills Python on a timeout, `finally` never runs; the job handle closes
    with the process and Windows terminates the game. Returns (handle, ok) --
    the handle must stay referenced for the life of the run."""
    job = _k32.CreateJobObjectW(None, None)
    if not job:
        return None, False
    info = _EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000   # KILL_ON_JOB_CLOSE
    ok = bool(_k32.SetInformationJobObject(
        job, 9, ctypes.byref(info), ctypes.sizeof(info)))   # ExtendedLimit
    ok = ok and bool(_k32.AssignProcessToJobObject(
        job, wt.HANDLE(int(proc._handle))))
    return job, ok


def _unreal_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe",
                          "/FO", "CSV", "/NH"], capture_output=True, text=True)
    return [ln for ln in (out.stdout or "").splitlines()
            if ln.lower().startswith('"unrealeditor.exe"')]


def _client(hwnd):
    r = wt.RECT()
    _u32.GetClientRect(hwnd, ctypes.byref(r))
    return int(r.right), int(r.bottom)


def _windows_of(pid):
    """Visible top-level windows of `pid`, largest client area first."""
    found = []

    def _cb(hwnd, _lp):
        p = wt.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and _u32.IsWindowVisible(hwnd):
            w, h = _client(hwnd)
            found.append((w * h, hwnd))
        return True

    _u32.EnumWindows(_ENUMPROC(_cb), 0)
    return sorted(found, key=lambda t: t[0], reverse=True)


def _grab(pid):
    """(image, info) of the game window's client area, or (None, info)."""
    from PIL import ImageGrab
    info = {}
    wins = _windows_of(pid)
    info["windows_found"] = len(wins)
    if not wins:
        info["error"] = "the game process has no visible window"
        return None, info
    hwnd = wins[0][1]
    # The project's proven foreground method (lookdev_shot.ps1): an ALT tap
    # so SetForegroundWindow is honoured, restore if minimised, re-check.
    _u32.keybd_event(0x12, 0, 0, None)
    _u32.keybd_event(0x12, 0, 2, None)
    if _u32.IsIconic(hwnd):
        _u32.ShowWindow(hwnd, 9)                     # SW_RESTORE
    _u32.SetForegroundWindow(hwnd)
    time.sleep(2.0)
    info["still_minimised"] = bool(_u32.IsIconic(hwnd))
    fg = _u32.GetForegroundWindow()
    p = wt.DWORD()
    _u32.GetWindowThreadProcessId(fg, ctypes.byref(p))
    info["foreground_pid"] = int(p.value)
    info["foreground_is_game"] = (p.value == pid)
    w, h = _client(hwnd)                             # AFTER the restore
    pt = wt.POINT(0, 0)
    _u32.ClientToScreen(hwnd, ctypes.byref(pt))
    info["client_size"] = [w, h]
    info["client_origin"] = [int(pt.x), int(pt.y)]
    info["window_dpi"] = int(_u32.GetDpiForWindow(hwnd))
    if w <= 0 or h <= 0:
        info["error"] = "the game window has an empty client area"
        return None, info
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + w, pt.y + h),
                         all_screens=True)
    return img.convert("RGB"), info


def _inside(path, root):
    try:
        return os.path.commonpath([bootstrap._norm(path),
                                   bootstrap._norm(root)]) == bootstrap._norm(root)
    except ValueError:
        return False


def main():
    # FIRST, before any window call: physical pixels everywhere (-4 =
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2).
    dpi_ok = bool(_u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--x", type=float, required=True)
    ap.add_argument("--y", type=float, required=True)
    ap.add_argument("--pitch", type=float, default=0.0)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--eye", type=float, default=ps.EYE_CM)
    ap.add_argument("--out-dir", required=True,
                    help="repo-relative or absolute; must be inside the repo")
    ap.add_argument("--res", default="1600x900")
    ap.add_argument("--settle", type=float, default=100.0,
                    help="seconds of dwell before the capture")
    ap.add_argument("--recipe", default=os.path.join(
        REPO_ROOT, "recipes", "alpine_8k.json"))
    ap.add_argument("--hide-pawn", action="store_true",
                    help="ShowFlag.SkeletalMeshes 0: the third-person pawn "
                         "otherwise fills the frame. Hides EVERY skeletal mesh "
                         "(the world has none besides the pawn today). "
                         "REJECTED alternative: ToggleDebugCamera in the same "
                         "-ExecCmds as BugItGo spawns the debug camera at the "
                         "PlayerStart view, not at the teleported pawn "
                         "(2026-10-01, forest_floor_dbg: Loc -211127,278570).")
    ap.add_argument("--diag-cmd", action="append", default=[],
                    help="DIAGNOSTIC console command for an A/B (repeatable), "
                         "e.g. 'wp.Runtime.HLOD 0'. Not read back in-process "
                         "(some, like wp.Runtime.HLOD, are commands, not "
                         "cvars): the A/B FRAME is the instrument. A run with "
                         "one is therefore never ok and its frame is always "
                         "written as .REJECTED.png -- it cannot be mistaken "
                         "for a look still.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not NAME_RE.match(args.name):
        print("REFUSE: --name must match [A-Za-z0-9_-]+ (it becomes a file "
              "name in two roots)")
        return 2
    out_dir = os.path.abspath(os.path.join(REPO_ROOT, args.out_dir))
    png_ok = os.path.join(out_dir, args.name + ".png")
    png_bad = os.path.join(out_dir, args.name + ".REJECTED.png")
    jpath = os.path.join(out_dir, args.name + ".json")
    log_path = os.path.join(ps.LOG_DIR, "game_still_%s.log" % args.name)
    for p in (png_ok, png_bad, jpath):
        if not _inside(p, REPO_ROOT):
            print("REFUSE: output is outside the repo (standing rule 1): " + p)
            return 2
    if not _inside(log_path, bootstrap.UE_PROJECT_ROOT):
        print("REFUSE: the log is outside the UE project dir: " + log_path)
        return 2

    rw, rh = (int(v) for v in args.res.lower().split("x"))
    recipe = json.load(open(args.recipe, encoding="utf-8"))
    level = recipe["landscape"]["level_path"]
    z = ps.heightmap_z(args.x, args.y, recipe) + args.eye

    cmds = ["r.setRes %dx%dw" % (rw, rh),
            "BugItGo %.1f %.1f %.1f %.1f %.1f 0" % (
                args.x, args.y, z, args.pitch, args.yaw),
            "DisableAllScreenMessages"]
    if args.hide_pawn:
        cmds.append("ShowFlag.SkeletalMeshes 0")
    for _dc in args.diag_cmd:
        if "," in _dc or "'" in _dc or '"' in _dc:
            print("REFUSE: --diag-cmd may not contain , or quotes: the "
                  "-ExecCmds parser splits on them")
            return 2
        cmds.append(_dc)
    cmd = [ps.UE_EXE, ps.UPROJECT, level, "-game", "-windowed",
           "-ResX=%d" % rw, "-ResY=%d" % rh,
           "-ExecCmds=%s" % ",".join(cmds),
           "-nosplash", "-NoLoadingScreen", "-AbsLog=%s" % log_path]
    rec = {"name": args.name, "ok": False, "cmd": cmd, "level": level,
           "camera": {"x_cm": args.x, "y_cm": args.y, "z_cm": round(z, 1),
                      "pitch_deg": args.pitch, "yaw_deg": args.yaw,
                      "z_source": "heightmap + eye (placement aid, not a trace)",
                      "pose_read_back": False},
           "state": "bench_on_disk", "hlod_residency_read_back": False,
           "view": ("player camera, skeletal meshes hidden" if args.hide_pawn
                    else "player camera (third-person pawn in frame)"),
           "requested_res": [rw, rh], "settle_s": args.settle,
           "dpi_awareness_set": dpi_ok}
    if args.dry_run:
        print(json.dumps(rec, indent=1))
        return 0

    running = _unreal_running()
    if running:
        print("REFUSE: %d UnrealEditor.exe process(es) already running "
              "(standing rule 11). Wait for zero." % len(running))
        return 2
    _avail, _total = resource_guard.available_gb()
    rec["free_ram_gb"] = _avail
    rec["ram_comfortable"] = resource_guard.check_memory("game_still")

    os.makedirs(out_dir, exist_ok=True)
    for stale in (png_ok, png_bad):
        if os.path.isfile(stale):
            os.replace(stale, stale + ".prev")       # never leave an old frame
    t0 = time.time()                                 # beside a new verdict
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    job, job_ok = _kill_on_close_job(proc)
    rec["kill_on_close_job"] = job_ok
    vram = []
    aborted = None
    img = None
    try:
        while time.time() - t0 < args.settle:
            if proc.poll() is not None:
                aborted = "the game process exited during the dwell (rc %s)" % proc.returncode
                break
            m = ps.gpu_mem_used_mib()
            vram.append((time.time(), m))
            if isinstance(m, int) and m > ps.VRAM_ABORT_MIB:
                aborted = "VRAM %d MiB over the %d ceiling" % (m, ps.VRAM_ABORT_MIB)
                break
            time.sleep(5.0)
        if aborted is None:
            img, info = _grab(proc.pid)
            rec["capture"] = info
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=60)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    rec["dwell_s"] = round(time.time() - t0, 1)
    problems = []
    if aborted:
        problems.append(aborted)
    if not dpi_ok:
        problems.append("DPI awareness could not be set; window coordinates "
                        "may be scaled")
    rec["vram_mib"] = ps._vram_reduce(vram, t0)
    if rec["vram_mib"] is None:
        rec["vram_note"] = "VRAM UNMEASURED this run, not zero (rule 13)"
        problems.append("no VRAM sample was obtained, so the ceiling was "
                        "never checked")
    if img is not None:
        import numpy as np
        a = np.asarray(img).astype(float) / 255.0
        luma = a @ np.array([0.2126, 0.7152, 0.0722])
        rec["frame"] = {"size": [img.size[0], img.size[1]],
                        "encoding": "srgb_encoded_8bit (NOT display-linear)",
                        "luma_mean_encoded": round(float(luma.mean()), 4),
                        "luma_std_encoded": round(float(luma.std()), 4)}
        # THE GAME WINDOW IS DPI-UNAWARE (window_dpi 96 on a 150% display,
        # first run 2026-10-01): Windows bitmap-stretches its 1600x900 client
        # to 2400x1350 physical pixels. So the capture is the requested frame
        # times ONE uniform display scale, and it is resampled back down. Any
        # other size -- unequal axes, or a scale below 1 -- is still refused.
        sx, sy = img.size[0] / float(rw), img.size[1] / float(rh)
        rec["frame"]["display_scale"] = [round(sx, 4), round(sy, 4)]
        if abs(sx - sy) > 0.01 or sx < 0.999 or sx > 3.0:
            problems.append("captured %dx%d, requested %dx%d" % (
                img.size[0], img.size[1], rw, rh))
        elif sx > 1.001:
            from PIL import Image as _Image
            img = img.resize((rw, rh), _Image.LANCZOS)
            rec["frame"]["resampled_to"] = [rw, rh]
        if luma.mean() < 0.01 or luma.std() < 0.005:
            problems.append("frame is black or flat")
        if not rec["capture"].get("foreground_is_game"):
            problems.append("the game window was not the foreground window")
        if rec["capture"].get("still_minimised"):
            problems.append("the game window was still minimised")
    elif not aborted:
        problems.append(rec.get("capture", {}).get("error", "no frame"))
    try:
        log = open(log_path, encoding="utf-8", errors="replace").read()
        hits = [tuple(float(v) for v in m.groups())
                for m in BUGITGO_RE.finditer(log)]
        want = (args.x, args.y, z)
        good = [h for h in hits
                if all(abs(a_ - b_) <= 1.0 for a_, b_ in zip(h, want))]
        rec["log"] = {"bugitgo_to_lines": len(hits),
                      "bugitgo_matching_request": len(good),
                      "bugitgo_first": hits[0] if hits else None,
                      "screen_messages_disabled_line": SCREEN_MSG_LINE in log,
                      "world_partition_lines": sum(
                          1 for ln in log.splitlines() if "WorldPartition" in ln)}
        if not good:
            problems.append("no engine `BugItGo to:` line matches the request "
                            "(%d such lines found)" % len(hits))
        if not rec["log"]["screen_messages_disabled_line"]:
            problems.append("DisableAllScreenMessages left no line in the log")
    except OSError as e:
        problems.append("log unreadable: %s" % e)
    if args.diag_cmd:
        rec["diagnostic_cmds"] = list(args.diag_cmd)
        problems.append("DIAGNOSTIC run (%s): an A/B frame, not a look still"
                        % "; ".join(args.diag_cmd))
    rec["problems"] = problems
    rec["ok"] = not problems
    if img is not None:
        dest = png_ok if rec["ok"] else png_bad
        img.save(dest)
        rec["png"] = os.path.relpath(dest, REPO_ROOT)
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    print(json.dumps({k: rec[k] for k in rec if k != "cmd"}, indent=1))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
