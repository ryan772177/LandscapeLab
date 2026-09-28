"""measure_frame_cost.py — GPU and thread frame cost, WITH AN ARTEFACT ON DISK.

READ-ONLY with respect to the world: it moves the editor viewport camera and
runs a profiler. It spawns nothing, saves nothing, and mutates no asset.

=====================================================================
WHY THIS EXISTS RATHER THAN ANOTHER VIEWPORT READING
=====================================================================
Every GPU figure on this project's board -- R13's 94.45 / 75.71 ms included --
is an ATTENDED VIEWPORT READING with no artefact. The 2026-08-06 pass audit
filed it as UNVERIFIABLE BY CONSTRUCTION: "a reader cannot tell 'measured'
means 'read off an overlay'". It was correctly class-labelled and still
unfalsifiable from the repo.

UE's CSV profiler writes a per-frame CSV to Saved/Profiling/CSV. That is a
different KIND of evidence: reproducible, re-reducible by someone who was not
in the room, and quotable with a path. `CsvProfile frames=N`
(CsvProfiler.cpp:1076-1080) captures exactly N frames and writes the file
itself, so nothing depends on stopping it at the right moment.

=====================================================================
THE THROTTLE IS MEASURED, NOT ASSUMED AWAY
=====================================================================
This machine throttles a backgrounded editor by ~17.8x (2.03 CPU-s per 20 s
wall vs 36.06 foregrounded), and setting bThrottleCPUWhenNotForeground=False
in the ini DID NOT DELIVER the behaviour. A throttled capture produces frame
times that are real numbers about a state nobody cares about.

So this samples the editor process's CPU time across the capture window and
refuses the result if the ratio says it was throttled. That is a check on the
INSTRUMENT, not on the scene, and it is the difference between "75 ms" and
"75 ms of something".

=====================================================================
CALIBRATION CLASS -- binds every number this prints
=====================================================================
Editor viewport, not PIE and not a packaged build. Whatever cvars the process
is running. Whatever the viewport resolution is. The camera this script was
pointed at. All of it is printed with the result, because R13's figures became
hard to reuse precisely when their class had to be reconstructed.

Exit codes:
  0  measured; CSV path printed
  1  could not look (no marker, no CSV appeared, unparseable)
  2  bad arguments
  3  rule 7: no verified editor node
  5  the editor was THROTTLED during the capture -- no verdict
  6  the world was not resident, residency was not declared, or the
     component count could not be taken -- no verdict
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_FRAME__"

CSV_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Profiling", "CSV")

# Columns worth reporting, in the order they explain a frame.
COLUMNS = ("FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "RHIThreadTime")


PAYLOAD_SETUP = r'''
import json as _json
import unreal as _unreal
_out = {"error": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level"] = _w.get_outer().get_path_name()

    # ---- stop the editor throttling itself out of the measurement --------
    # bThrottleCPUWhenNotForeground lives on UEditorPerformanceSettings
    # (EditorPerformanceSettings.h:74), a UDeveloperSettings with
    # config=EditorSettings -- NOT in DefaultEditorPerProjectUserSettings.ini,
    # which is where this project's earlier fix was written and is why it
    # "did not deliver". EditorEngine.cpp:1807 reads it as
    #   bShouldDisableRendering = !FApp::HasFocus() && bThrottleCPUWhenNotForeground
    # so with it false the viewport keeps rendering unfocused.
    #
    # Set on the live object AND read back. The ini records an override; only
    # the object records what is in effect.
    _out["throttle"] = {"before": {}, "set": [], "readback": {}, "unsettable": []}
    # UEditorPerformanceSettings is UCLASS(minimalapi), so it is NOT exported
    # as unreal.EditorPerformanceSettings. The CDO is still reachable by
    # object path, which is the reflected surface answering rather than the
    # generated wrapper.
    _ps = None
    _how = None
    try:
        _ps = _unreal.get_default_object(getattr(_unreal, "EditorPerformanceSettings"))
        _how = "unreal.EditorPerformanceSettings"
    except Exception:
        try:
            _ps = _unreal.load_object(
                None, "/Script/UnrealEd.Default__EditorPerformanceSettings")
            _how = "CDO by path /Script/UnrealEd.Default__EditorPerformanceSettings"
        except Exception as _le:
            _out["throttle"]["unsettable"].append(
                "could not reach UEditorPerformanceSettings: "
                + type(_le).__name__ + ": " + str(_le))
    _out["throttle"]["reached_via"] = _how
    if _ps is None:
        # The throttle CDO could not be reached; the reason is already in
        # throttle["unsettable"] and printed as "THROTTLE NOT SET". The
        # capture still proceeds (the ini override may already be in force),
        # so this is RECORDED, not a refusal — it does NOT fail closed.
        pass
    # BEFORE any write: this is the positive control on whether the project's
    # ini override is in effect at all. DefaultEditorPerProjectUserSettings.ini
    # carries bThrottleCPUWhenNotForeground=False under the right SECTION but
    # in the wrong FILE for a config=EditorSettings class. If this reads True,
    # that override has never applied.
    # ENUMERATE the reflected property names rather than guessing them. Three
    # guesses have already failed here; the object knows its own names.
    _names = []
    if _ps is not None:
        try:
            for _f in _unreal.get_type_from_class(_ps.get_class()).__dict__:
                _names.append(_f)
        except Exception:
            pass
        if not _names:
            _names = [_n for _n in dir(_ps) if not _n.startswith("_")]
    _out["throttle"]["candidates"] = sorted(
        _n for _n in _names if "hrottle" in _n or "creen_percentage" in _n)
    for _prop in _out["throttle"]["candidates"]:
        try:
            _out["throttle"]["before"][_prop] = _ps.get_editor_property(_prop)
        except Exception as _pe:
            _out["throttle"]["before"][_prop] = "UNREADABLE: " + type(_pe).__name__
    if not _out["throttle"]["candidates"]:
        _out["throttle"]["before"]["(none)"] = (
            "no throttle-like property found on the CDO")
    for _prop in _out["throttle"]["candidates"]:
        if "creen_percentage" in _prop:
            continue
        try:
            _ps.set_editor_property(_prop, False)
            _out["throttle"]["set"].append(_prop)
        except Exception as _pe:
            _out["throttle"]["unsettable"].append(
                _prop + " -> " + type(_pe).__name__ + ": " + str(_pe))
        try:
            _out["throttle"]["readback"][_prop] = bool(_ps.get_editor_property(_prop))
        except Exception:
            _out["throttle"]["readback"][_prop] = None
    _unreal.SystemLibrary.execute_console_command(
        _ues.get_editor_world(), "Slate.bAllowThrottling 0")

    # REALTIME. An editor level viewport redraws ON DEMAND; without this it
    # renders when something changes and the profiler measures the editor UI,
    # not the scene. Symptom that found it: GPUTime was 3.16 ms with the frame
    # full of terrain and 3.12 ms pointed at the empty sky -- a 1.3% difference
    # where the terrain contributes nothing measurable. A number that does not
    # move when the subject is removed is not a measurement of the subject.
    _out["realtime_set"] = False
    try:
        _les.editor_set_viewport_realtime(True)
        _out["realtime_set"] = True
    except Exception as _re:
        _out["realtime_error"] = type(_re).__name__ + ": " + str(_re)

    if __MOVE__:
        _les.editor_set_game_view(True)
        # unreal.Rotator(ROLL, PITCH, YAW). Read from the reflected
        # constructor, not from the C++ FRotator(Pitch, Yaw, Roll) order:
        # PythonStub unreal.py:66750
        #   def __init__(self, roll=0.0, pitch=0.0, yaw=0.0)
        # The first run of this script passed (pitch, yaw, roll) and put a
        # -25 degree ROLL on a level camera. The frame was still full of
        # terrain, so nothing looked wrong -- which is the whole hazard.
        _unreal.EditorLevelLibrary.set_level_viewport_camera_info(
            _unreal.Vector(__CX__, __CY__, __CZ__),
            _unreal.Rotator(__RR__, __RP__, __RY__))
    _loc, _rot = _unreal.EditorLevelLibrary.get_level_viewport_camera_info()
    _out["camera_location"] = [float(_loc.x), float(_loc.y), float(_loc.z)]
    _out["camera_rotation"] = [float(_rot.pitch), float(_rot.yaw), float(_rot.roll)]

    # ⭐ FOV IS SET AND READ BACK. Until 2026-09-05 no FOV was set anywhere in
    # this path, so every figure on the board was taken at whatever the
    # viewport happened to be -- and FOV is the parameter that most directly
    # decides how much geometry is in frame. A GPUTime p90 without a recorded
    # FOV is not a reproducible measurement.
    #
    # Set THEN read: this project has watched setters return success while
    # doing nothing. Both fov_requested and fov_readback are RECORDED so the
    # report shows whether the set took; the host does NOT yet refuse on a
    # disagreement (NN12 follow-up owed — mirror the residency gate: compare
    # the pair and exit 6 on a mismatch).
    if __FOV__ > 0:
        try:
            _lesx = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
            _lesx.set_level_viewport_fov(float(__FOV__), "")
            _gf = _lesx.get_level_viewport_fov("")
            _out["fov_requested"] = float(__FOV__)
            _out["fov_readback"] = None if _gf is None else round(float(_gf), 3)
        except Exception as _fe:
            _out["fov_error"] = type(_fe).__name__ + ": " + str(_fe)
    else:
        _out["fov_requested"] = None
        _out["fov_readback"] = None

    # VIEWPORT SIZE IS RECORDED, NOT SET. The editor viewport is the window,
    # and this tool's own calibration class says "whatever the viewport
    # resolution is". Declaring a resolution the tool cannot impose would be a
    # parameter that exists and is never written -- the exact defect the
    # material Tiling scalar had. So it is MEASURED and written into the
    # result (there is no recipe expectation to compare it against).
    # 2026-09-05: this called _unreal.SystemLibrary.get_viewport_size(_w),
    # WHICH DOES NOT EXIST IN 5.8. Every run since raised
    #   AttributeError: type object 'SystemLibrary' has no attribute
    #   'get_viewport_size'
    # and the except below turned it into a null -- so every perf artefact on
    # record reads "viewport_size": null, and that null was read as evidence of
    # editor overhead (research REGISTER B1.6) when it was a missing function.
    # The editor answer lives on UnrealEditorSubsystem; the GAME answer (for a
    # -game process) is WidgetLayoutLibrary.get_viewport_size(world). Verified
    # against the reflected stub and live: returns [1321, 1421] here.
    try:
        _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
        _vp = _ues.get_level_viewport_size()
        _out["viewport_size"] = [int(_vp.x), int(_vp.y)] if _vp else None
        if _vp is None:
            _out["viewport_size_error"] = "get_level_viewport_size returned None"
    except Exception as _ve:
        _out["viewport_size"] = None
        _out["viewport_size_error"] = type(_ve).__name__ + ": " + str(_ve)

    _out["cvars"] = {}
    for _n in ("r.ScreenPercentage", "r.Nanite.MaxPixelsPerEdge",
               "r.DynamicGlobalIlluminationMethod", "r.ReflectionMethod",
               "r.Nanite.Tessellation", "r.ViewDistanceScale",
               "grass.DensityScale", "foliage.DensityScale"):
        _v = _unreal.SystemLibrary.get_console_variable_float_value(_n)
        _out["cvars"][_n] = float(_v)
    del _w, _loc, _rot
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_FRAME__" + _json.dumps(_out))
'''

PAYLOAD_LOAD_AND_CENSUS = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "loaded_call": None, "load_error": None, "bounds": None,
        "landscape_actors": 0, "proxies": 0, "components": 0,
        "components_unreadable": 0}
try:
    if __LOAD__:
        _ok, _mn, _mx, _err = _unreal.LandscapeLabTools.load_all_world_partition_regions()
        _out["loaded_call"] = bool(_ok)
        _out["load_error"] = _err or None
        _out["bounds"] = [[float(_mn.x), float(_mn.y)], [float(_mx.x), float(_mx.y)]]

    # Census AFTER the load. This asks a question the profiler cannot: not
    # "how fast" but "how much of the world was there".
    for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_a, _unreal.LandscapeStreamingProxy):
            _out["proxies"] += 1
        elif isinstance(_a, _unreal.Landscape):
            _out["landscape_actors"] += 1
        else:
            continue
        try:
            _c = _a.get_components_by_class(_unreal.LandscapeComponent)
        except Exception:
            _out["components_unreadable"] += 1
            continue
        if _c is None:
            _out["components_unreadable"] += 1
        else:
            _out["components"] += len(_c)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_FRAME__" + _json.dumps(_out))
'''

PAYLOAD_CAPTURE = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "issued": False}
try:
    _w = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.SystemLibrary.execute_console_command(_w, "CsvProfile frames=__FRAMES__")
    _out["issued"] = True
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_FRAME__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload):
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    return d, text


def _editor_cpu_seconds():
    """Total CPU seconds of the editor process, or None if it cannot be read.

    None is 'could not look'. The caller must not treat it as zero, which would
    read as a fully throttled editor and refuse a good capture.
    """
    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process UnrealEditor -ErrorAction SilentlyContinue | "
             "Measure-Object -Property CPU -Sum).Sum"],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) if out else None
    except Exception:
        return None


def _newest_csv(before):
    files = set(glob.glob(os.path.join(CSV_DIR, "*.csv")))
    fresh = files - before
    if not fresh:
        return None
    return max(fresh, key=os.path.getmtime)


def _reduce(path, attempts=20, skip_frames=0):
    """Per-column count / mean / p50 / p90 / max, in ms.

    `skip_frames` drops the first N rows before reducing. The editor path
    warms up BEFORE capturing, so it leaves this at 0. A standalone `-game`
    run cannot be told to wait -- `-ExecCmds` fires once at startup and there
    is no channel to trigger the capture later -- so it captures through the
    warmup and discards it here instead. Added rather than copied:
    non-negotiable 4a, a second reducer would drift and both would report
    plausible milliseconds.

    The editor holds the CSV open while it flushes, so a read straight after
    the file appears raises PermissionError on Windows. Retry rather than
    report "no data" — an instrument that gives up early and a scene with no
    cost look identical in the output.
    """
    for i in range(attempts):
        try:
            with open(path, "rb"):
                pass
            break
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(3.0)

    cols = {}
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader):
            if idx < skip_frames:
                continue
            for name in COLUMNS:
                raw = row.get(name)
                if raw in (None, ""):
                    continue
                try:
                    v = float(raw)
                except ValueError:
                    continue
                cols.setdefault(name, []).append(v)
    stats = {}
    for name, vals in cols.items():
        if not vals:
            continue
        s = sorted(vals)
        n = len(s)
        stats[name] = {
            "n": n,
            "mean": sum(s) / n,
            "p50": s[n // 2],
            "p90": s[min(n - 1, int(n * 0.90))],
            "max": s[-1],
        }
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--warmup", type=float, default=20.0,
                    help="seconds to let streaming and shaders settle first")
    ap.add_argument("--camera", default="",
                    help="x,y,z,pitch,yaw,roll -- omit to measure where the viewport already is")
    ap.add_argument("--tag", default="", help="label recorded with the result")
    ap.add_argument("--load-all-regions", action="store_true",
                    help="load every World Partition region before measuring")
    ap.add_argument("--expect-components", type=int, default=0,
                    help="landscape components that MUST be resident. Without "
                         "it a partitioned world gets NO VERDICT: a frame time "
                         "over an unloaded world is a real number about a state "
                         "nobody cares about.")
    ap.add_argument("--fov", type=float, default=0.0,
                    help="horizontal FOV to SET on the viewport and read "
                         "back. 0 leaves it alone and records None. The FOV "
                         "decides how much geometry is in frame, so a cost "
                         "figure without one is not reproducible.")
    ap.add_argument("--min-cpu-ratio", type=float, default=0.30,
                    help="CPU-seconds per wall-second below which the editor is "
                         "judged throttled and no verdict is given")
    args = ap.parse_args(argv)

    move = False
    cam = [0.0] * 6
    if args.camera:
        parts = [p.strip() for p in args.camera.split(",")]
        if len(parts) != 6:
            print("REFUSE: --camera wants x,y,z,pitch,yaw,roll (6 values), got %d"
                  % len(parts))
            return 2
        try:
            cam = [float(p) for p in parts]
        except ValueError:
            print("REFUSE: --camera values must be numbers.")
            return 2
        move = True

    if args.frames < 30:
        print("REFUSE: --frames %d is too few to characterise a distribution."
              % args.frames)
        return 2

    os.makedirs(CSV_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(CSV_DIR, "*.csv")))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])

        setup = (PAYLOAD_SETUP
                 .replace("__MOVE__", repr(bool(move)))
                 .replace("__CX__", repr(cam[0])).replace("__CY__", repr(cam[1]))
                 .replace("__CZ__", repr(cam[2])).replace("__RP__", repr(cam[3]))
                 .replace("__RY__", repr(cam[4])).replace("__RR__", repr(cam[5]))
                 .replace("__FOV__", repr(float(args.fov))))
        d, raw = _run(remote, remote_exec, setup)
        if d is None:
            print("NO MARKER on setup — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("SETUP ERROR:", d["error"])
            return 1

        print("=== CALIBRATION CLASS (binds every number below) ===")
        print("  class          editor viewport — NOT PIE, NOT a packaged build")
        print("  level          %s" % d.get("level"))
        print("  camera loc     %s" % d.get("camera_location"))
        print("  camera rot     %s   (pitch, yaw, roll)" % d.get("camera_rotation"))
        # FOV and viewport size belong in the calibration class and did not
        # appear here until 2026-09-05. Every earlier figure on the board is
        # missing both.
        print("  camera fov     requested %s  READBACK %s"
              % (d.get("fov_requested"), d.get("fov_readback")))
        print("  viewport size  %s   (RECORDED, not set -- the editor "
              "viewport is the window)" % d.get("viewport_size"))
        print("  viewport realtime %s%s"
              % (d.get("realtime_set"),
                 "  " + d["realtime_error"] if d.get("realtime_error") else ""))
        if not d.get("realtime_set"):
            print("  WARNING: realtime could NOT be enabled. An on-demand viewport")
            print("           measures the editor UI, not the scene.")
        thr = d.get("throttle") or {}
        print("  perf settings BEFORE any write (is the ini in effect?):")
        for k, v in (thr.get("before") or {}).items():
            print("      %-38s %s" % (k, v))
        print("  throttle       set %s   readback %s"
              % (thr.get("set"), thr.get("readback")))
        for u in thr.get("unsettable") or []:
            print("  THROTTLE NOT SET: %s" % u)
        for k, v in sorted((d.get("cvars") or {}).items()):
            print("  %-32s %s" % (k, v))
        print("  tag            %s" % (args.tag or "(none)"))
        print()

        cen, raw = _run(remote, remote_exec,
                        PAYLOAD_LOAD_AND_CENSUS.replace(
                            "__LOAD__", repr(bool(args.load_all_regions))))
        if cen is None or cen.get("error"):
            print("CENSUS FAILED:", (cen or {}).get("error", "no marker"))
            print("Refusing to measure a world whose residency is unknown.")
            return 1
        if args.load_all_regions:
            print("load all regions : call=%s  bounds=%s"
                  % (cen.get("loaded_call"), cen.get("bounds")))
            if cen.get("load_error"):
                print("  loader said    : %s" % cen["load_error"])
        print("residency      : %d landscape + %d proxies, %d components resident"
              % (cen.get("landscape_actors", 0), cen.get("proxies", 0),
                 cen.get("components", 0)))
        if cen.get("components_unreadable"):
            print("                 %d actor(s) UNREADABLE - not counted as zero"
                  % cen["components_unreadable"])
        print()

        print("warming up %.0f s so streaming and shader compiles settle ..." % args.warmup)
        time.sleep(args.warmup)

        cpu0 = _editor_cpu_seconds()
        wall0 = time.time()

        cap, raw = _run(remote, remote_exec,
                        PAYLOAD_CAPTURE.replace("__FRAMES__", str(int(args.frames))))
        if cap is None or cap.get("error") or not cap.get("issued"):
            print("Could not start the capture:",
                  (cap or {}).get("error", "no marker"))
            return 1

        print("capturing %d frames ..." % args.frames)
        path = None
        deadline = time.time() + max(120.0, args.frames * 0.5)
        while time.time() < deadline:
            time.sleep(3.0)
            path = _newest_csv(before)
            if path and os.path.getsize(path) > 0:
                # The writer may still be flushing; wait for the size to settle.
                size = -1
                while size != os.path.getsize(path):
                    size = os.path.getsize(path)
                    time.sleep(1.0)
                break
            path = None

        cpu1 = _editor_cpu_seconds()
        wall1 = time.time()
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if path is None:
        print("NO CSV APPEARED in %s within the window." % CSV_DIR)
        print("This is 'I could not measure', not 'the frame cost is fine'.")
        return 1

    # ---- instrument check before scene numbers ---------------------------
    wall = max(wall1 - wall0, 1e-6)
    if cpu0 is None or cpu1 is None:
        print("THROTTLE CHECK: could not read the editor's CPU time.")
        print("Reporting the numbers, but the instrument is UNVERIFIED.")
        ratio = None
    else:
        ratio = (cpu1 - cpu0) / wall
        print("throttle check : %.2f CPU-s per wall-second over %.1f s"
              % (ratio, wall))

    stats = _reduce(path)
    if not stats:
        print("CSV at %s parsed to no usable columns." % path)
        return 1

    print()
    print("=== FRAME COST ===")
    print("  artefact  %s" % path)
    print()
    print("  %-18s %6s %9s %9s %9s %9s" % ("column", "n", "mean", "p50", "p90", "max"))
    for name in COLUMNS:
        s = stats.get(name)
        if not s:
            continue
        print("  %-18s %6d %8.2f %8.2f %8.2f %8.2f"
              % (name, s["n"], s["mean"], s["p50"], s["p90"], s["max"]))
    print()

    resident = cen.get("components", 0)
    unreadable = cen.get("components_unreadable", 0)

    if unreadable and resident == 0:
        print("NO VERDICT - THE COUNT COULD NOT BE TAKEN.")
        print("  %d actor(s) refused their component list; 0 were counted." % unreadable)
        print("  This is NOT 'the world was not there'. The world may be fully")
        print("  resident; the instrument could not look. Fix the read before")
        print("  reading anything into the frame numbers above.")
        return 6

    if args.expect_components > 0 and resident < args.expect_components:
        frac = (100.0 * resident / args.expect_components)
        print("NO VERDICT - THE WORLD WAS NOT THERE.")
        print("  %d of %d landscape components resident (%.1f%%)."
              % (resident, args.expect_components, frac))
        print("  The numbers above are a real measurement of %.1f%% of the level."
              % frac)
        print("  Re-run with --load-all-regions, or lower --expect-components")
        print("  deliberately and quote the fraction beside the result.")
        return 6
    if unreadable:
        print("WARNING: %d actor(s) refused their component list, so %d is a"
              % (unreadable, resident))
        print("         LOWER BOUND on residency, not a census.")

    if args.expect_components <= 0 and cen.get("proxies", 0) > 0:
        print("NO VERDICT - RESIDENCY WAS NOT DECLARED.")
        print("  This world has %d streaming proxies, so part of it can be absent"
              % cen["proxies"])
        print("  without saying so. Pass --expect-components N (the recipe knows N).")
        print("  A frame time over an unloaded world inverted a gate in this")
        print("  project once already; the default here fails closed.")
        return 6

    if ratio is not None and ratio < args.min_cpu_ratio:
        print("NO VERDICT — THE EDITOR WAS THROTTLED.")
        print("  %.2f CPU-s per wall-second is below the %.2f floor."
              % (ratio, args.min_cpu_ratio))
        print("  A backgrounded editor on this machine runs ~17.8x slower, and")
        print("  the ini setting for it does not take effect. Foreground the")
        print("  editor window and re-run. The numbers above are real and are")
        print("  about a state nobody cares about.")
        return 5

    fps = stats.get("FrameTime")
    if fps and fps["mean"] > 0:
        print("  mean frame time %.2f ms  ->  %.1f fps equivalent"
              % (fps["mean"], 1000.0 / fps["mean"]))
    print()
    print("NOT MEASURED HERE: anything about a packaged build or PIE. This is")
    print("the editor viewport, which carries editor-only overhead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
