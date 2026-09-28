"""measure_pie_cost.py — frame cost in PLAY IN EDITOR, with an artefact on disk.

This is PHASE2_PLAN.md unit 1. It is the first PIE measurement this project
has ever taken.

READ-ONLY with respect to the world. PIE runs against a DUPLICATE world
(/Game/UEDPIE_0_<level>), so ending play discards everything it touched. This
spawns nothing persistent, saves nothing, and mutates no asset.

=====================================================================
WHY THE EDITOR-VIEWPORT NUMBERS CANNOT SIMPLY BE CARRIED OVER
=====================================================================
Every frame-cost figure this project owns -- 7.92 ms at forest_floor included
-- was taken in an editor viewport with Slate running, all 256 landscape
proxies FORCE-RESIDENT, and zero gameplay ticking. RECIPES.md:6373 already
calls PIE "a different calibration class that does not exist".

probe_pie measured how different, before this was written:

    editor, force-resident      256 landscape proxies
    PIE, streaming live           4 landscape proxies, 2 foliage actors

Four variables change sign at once, so no editor number may be compared into
PIE and no PIE number back out. Both classes are stamped on every artefact.

=====================================================================
THE DISCRIMINATING FIELD IS NOT GPUTime
=====================================================================
Virtual shadow map page saturation and a large resident instance count
produce THE SAME frame time and lead to OPPOSITE work. GPUTime cannot tell
them apart, so the CSV columns that adjudicate are captured alongside it:

    VSM/FreePages           VirtualShadowMapCacheManager.cpp:685
    VSM/SinglePageCount     VirtualShadowMapArray.cpp:2619
    VSM/FullCount           VirtualShadowMapArray.cpp:2620
    SceneCulling/NumStaticInstances   SceneCulling.cpp:2676

PHASE2_PLAN.md names SinglePageCount and FullCount as the discriminator
against the 2048-page pool (r.Shadow.Virtual.MaxPhysicalPages). THAT IS ONE
STEP OFF AND THE CORRECTION IS KEPT HERE: those two count shadow MAPS, not
pages. FreePages is the direct measure of the pool and is what saturation
actually shows up in. All four are captured; FreePages is the one to read.

The VSM and GPUScene categories are DEFAULT-OFF and must be enabled per
session -- VirtualShadowMapArray.cpp:104 CSV_DEFINE_CATEGORY(VSM, false) and
GPUScene.cpp:48 CSV_DEFINE_CATEGORY(GPUScene, false). SceneCulling is
default-ON (SceneCulling.cpp:105) and needs no command.

=====================================================================
THE STATIONS DERIVE FROM ONE DECLARATION
=====================================================================
Pipeline rule 2: every scene parameter comes from recipe JSON. The control
station is read from recipes/alpine_8k.json -> capture.cameras, by name, at
its recorded absolute position -- it MUST reproduce the editor series or the
comparison is meaningless. The elevated stations are DERIVED from that same
camera's XY at declared heights above the traced ground, so there is one
declaration and two projections of it rather than three typed coordinates
that can drift apart (non-negotiable 24).

Ground comes from a LINE TRACE against collision in the PIE world, not from
the heightmap. That is deliberate: the heightmap is the source the placement
plan already reads, and non-negotiable 0 refuses two checks that share one.

Exit codes:
  0  measured; artefact written (or a --dry-run that started no PIE)
  1  could not look (no marker, no CSV, unparseable, or NO station produced a
     measurement)
  2  bad arguments, OR an editor session is already in play (refused)
  3  rule 7: no verified editor node
  4  a station could not be established (no ground hit, the view did not land
     where it was set, or its CSV recorded 0 frames) -- no verdict for that
     station
  5  PIE did not start, or the editor was THROTTLED during a capture
  6  PIE STARTED AND DID NOT END -- the editor needs attention
"""

from __future__ import annotations

import argparse
import csv
import datetime
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_PIE__"

CSV_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Profiling", "CSV")
VERIFY_DIR = os.path.join(bootstrap.REPO_ROOT, "_verify")
RECIPE = os.path.join(bootstrap.REPO_ROOT, "recipes", "alpine_8k.json")

# Where the pawn is parked so World Partition streams the station's region in
# before the ground is traced. The terrain spans 0..1552.5 m in world Z
# (CLAUDE.md CURRENT STATE), so 2500 m is clear of it everywhere with margin
# and the top-down trace still starts above the perch.
PERCH_Z_CM = 250000.0

# Thread and GPU columns, in the order they explain a frame, then the columns
# that discriminate BETWEEN two causes of the same frame time.
COLUMNS = (
    "FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "RHIThreadTime",
    "VSM/FreePages", "VSM/SinglePageCount", "VSM/FullCount",
    "VSM/NonNanitePostCullInstanceCount", "VSM/NaniteNumTris",
    "SceneCulling/NumStaticInstances", "SceneCulling/NumDynamicInstances",
)
# The always-on thread/GPU columns: absent means the CSV is empty/incomplete,
# NOT a disabled category (only the VSM/SceneCulling groups are default-off).
CORE_COLUMNS = COLUMNS[:5]


PAYLOAD_PRE = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None, "level": None, "viewport_size": None,
        "cvars": {}}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["in_play"] = bool(_les.is_in_play_in_editor())
    _w = _ues.get_editor_world()
    _out["level"] = _w.get_outer().get_path_name()
    _vp = _ues.get_level_viewport_size()
    if _vp is not None:
        _out["viewport_size"] = [int(_vp.x), int(_vp.y)]
    for _n in ("r.ScreenPercentage", "r.Nanite.MaxPixelsPerEdge",
               "r.DynamicGlobalIlluminationMethod", "r.ReflectionMethod",
               "r.Shadow.Virtual.MaxPhysicalPages", "r.Nanite.Foliage",
               "grass.DensityScale", "foliage.DensityScale", "t.MaxFPS"):
        _out["cvars"][_n] = float(
            _unreal.SystemLibrary.get_console_variable_float_value(_n))
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_BEGIN = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "requested": False}
try:
    _unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).editor_request_begin_play()
    _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


# Enable the default-OFF CSV categories INSIDE the running game world. Issued
# once, after PIE exists, and read back is not possible for CsvCategory -- so
# the honest check is downstream: if the columns are absent from the CSV, the
# reducer reports them ABSENT rather than as zero.
PAYLOAD_CSV_CATEGORIES = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "issued": []}
try:
    _gw = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_game_world()
    if _gw is None:
        _out["error"] = "no game world -- PIE is not running"
    else:
        # "CsvCategory VSM enable", NOT "CsvCategory VSM 1".
        # HandleCSVCategoryCommand (CsvProfiler.cpp:1138-1148) compares the
        # second argument against the literal words "enable" and "disable".
        # "1" matches neither, so bIsOperationValid goes false and the whole
        # command falls through to a usage error WITHOUT enabling anything --
        # and the console command still returns normally, so the caller sees
        # success. PHASE2_PLAN.md prescribes the "1" form; it is a silent
        # no-op and this project measured it as one (VSM columns ABSENT from
        # all three stations of tag pie001).
        #
        # The word is also required for IDEMPOTENCE: with the argument
        # OMITTED the command TOGGLES (:1152-1153), so a second run would
        # turn the category back off.
        for _c in ("CsvCategory VSM enable", "CsvCategory GPUScene enable"):
            _unreal.SystemLibrary.execute_console_command(_gw, _c)
            _out["issued"].append(_c)
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


# -------------------------------------------------------------------------
# A STATION IS ESTABLISHED IN THREE STEPS, NOT ONE, AND THE ORDER IS THE
# WHOLE POINT. Both halves were learned by a refusal on the first run:
#
#   1. TELEPORT FIRST, THEN TRACE. World Partition streams around the PAWN.
#      Tracing for ground at a station 4.8 km from where the pawn is standing
#      hits nothing, because that region was never loaded -- which reads
#      identically to "there is no terrain there".
#
#   2. READ THE VIEW POINT ON A LATER TICK THAN THE TELEPORT.
#      APlayerController::GetPlayerViewPoint returns the camera manager's
#      CACHED view point, gated on GetCameraCacheTime() > 0 with the engine's
#      own comment "Whether camera was updated at least once"
#      (PlayerController.cpp). Read in the same payload as the teleport it
#      returns the cache from before the move -- the origin, where the pawn
#      spawned -- and the drift gate correctly refuses it.
# -------------------------------------------------------------------------
PAYLOAD_TELEPORT = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "pawn_loc_cm": None}
try:
    _gw = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_game_world()
    if _gw is None:
        _out["error"] = "no game world -- PIE is not running"
    else:
        _pawn = _unreal.GameplayStatics.get_player_pawn(_gw, 0)
        _pc = _unreal.GameplayStatics.get_player_controller(_gw, 0)
        if _pawn is None or _pc is None:
            _out["error"] = "no pawn or no controller in the PIE world"
        else:
            _pawn.set_actor_location(
                _unreal.Vector(__X__, __Y__, __Z__), False, True)
            # DefaultPawn takes pitch and yaw from the CONTROLLER
            # (bUseControllerRotationPitch/Yaw), so the camera follows the
            # control rotation and not the actor rotation.
            _pc.set_control_rotation(
                _unreal.Rotator(0.0, __PITCH__, __YAW__))
            _pl = _pawn.get_actor_location()
            _out["pawn_loc_cm"] = [float(_pl.x), float(_pl.y), float(_pl.z)]
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_TRACE = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "ground_z_cm": None, "ground_why": None}
try:
    _gw = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_game_world()
    if _gw is None:
        _out["error"] = "no game world"
    else:
        # Against COLLISION, top-down. Deliberately not the heightmap: that is
        # the source the placement plan already reads, and non-negotiable 0
        # refuses two checks that share one source.
        _hit = _unreal.SystemLibrary.line_trace_single(
            _gw, _unreal.Vector(__X__, __Y__, 500000.0),
            _unreal.Vector(__X__, __Y__, -100000.0),
            _unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            _unreal.DrawDebugTrace.NONE, True)
        if _hit is None:
            _out["ground_why"] = ("no collision hit between +5000 m and "
                                  "-1000 m -- is the region streamed in?")
        else:
            # FHitResult fields are PROTECTED in 5.8; to_dict is the accessor.
            # get_editor_property("location") refuses, and a sibling tool once
            # read six clean HITS as six MISSES that way.
            _dd = _hit.to_dict()
            _loc = None
            for _k in _dd:
                if _k.lower() in ("location", "impact_point"):
                    _loc = _dd[_k]
                    break
            if _loc is None:
                _out["ground_why"] = "hit result carries no location key"
            else:
                _out["ground_z_cm"] = float(_loc.z)
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_VIEW = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "pawn_loc_cm": None,
        "view_loc_cm": None, "view_rot": None, "fov_deg": None, "fov_why": None,
        "proxies": 0, "foliage_actors": 0}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _gw = _ues.get_game_world()
    if _gw is None:
        _out["error"] = "no game world -- PIE is not running"
    else:
        _pawn = _unreal.GameplayStatics.get_player_pawn(_gw, 0)
        _pc = _unreal.GameplayStatics.get_player_controller(_gw, 0)
        if _pawn is None or _pc is None:
            _out["error"] = "no pawn or no controller in the PIE world"
        else:
            _pl = _pawn.get_actor_location()
            _out["pawn_loc_cm"] = [float(_pl.x), float(_pl.y), float(_pl.z)]
            # The setters wrote the pawn and the control rotation. THIS is a
            # different instrument (non-negotiable 8): it reads what the
            # camera actually is, via the camera manager's cache, which is
            # why it is read on a later tick than the teleport.
            _vl, _vr = _pc.get_player_view_point()
            _out["view_loc_cm"] = [float(_vl.x), float(_vl.y), float(_vl.z)]
            _out["view_rot"] = [float(_vr.pitch), float(_vr.yaw), float(_vr.roll)]
            # FOV is a calibration variable, not a setting to match. The
            # editor captures used the VIEWPORT's FOV, which is not the
            # recipe's fov_deg either -- so this is read and REPORTED, and
            # no claim is made that the two classes share it.
            try:
                _cm = _unreal.GameplayStatics.get_player_camera_manager(_gw, 0)
                _out["fov_deg"] = float(_cm.get_fov_angle()) if _cm else None
            except Exception as _fe:
                _out["fov_why"] = type(_fe).__name__ + ": " + str(_fe)

        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.LandscapeStreamingProxy):
            _out["proxies"] += 1
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.InstancedFoliageActor):
            _out["foliage_actors"] += 1
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_RESIDENCY = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "proxies": 0, "foliage_actors": 0}
try:
    _gw = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_game_world()
    if _gw is None:
        _out["error"] = "no game world"
    else:
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.LandscapeStreamingProxy):
            _out["proxies"] += 1
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.InstancedFoliageActor):
            _out["foliage_actors"] += 1
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_CAPTURE = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "issued": False}
try:
    _gw = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_game_world()
    if _gw is None:
        _out["error"] = "no game world"
    else:
        # CsvProfile frames=N captures exactly N frames and writes the file
        # itself (CsvProfiler.cpp:1076-1080), so nothing depends on stopping
        # it at the right moment.
        _unreal.SystemLibrary.execute_console_command(
            _gw, "CsvProfile frames=__FRAMES__")
        _out["issued"] = True
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_END = r'''
import json as _json
import unreal as _unreal
_out = {"error": None}
try:
    _unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).editor_request_end_play()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_CONFIRM = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None}
try:
    _out["in_play"] = bool(_unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).is_in_play_in_editor())
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
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
    """Editor process CPU seconds, or None if unreadable.

    None is 'could not look'. Treating it as zero would read as a fully
    throttled editor and refuse every good capture.
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


def _reduce(path, attempts=20):
    """Per-column count / mean / p50 / p90 / max.

    A column that is ABSENT from the CSV is absent from the result. It is
    never reported as zero: a disabled CSV category and a genuinely zero
    counter are different facts and must not print the same (non-negotiable 6).
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
        present = set(reader.fieldnames or ())
        for row in reader:
            for name in COLUMNS:
                if name not in present:
                    continue
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
        s = sorted(vals)
        n = len(s)
        stats[name] = {"n": n, "mean": sum(s) / n, "p50": s[n // 2],
                       "p90": s[min(n - 1, int(n * 0.90))], "max": s[-1]}
    return stats, sorted(present)


def _newest_csv(before):
    fresh = set(glob.glob(os.path.join(CSV_DIR, "*.csv"))) - before
    return max(fresh, key=os.path.getmtime) if fresh else None


def _load_camera(name):
    with open(RECIPE, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    for c in d.get("capture", {}).get("cameras", []):
        if c.get("name") == name:
            return c
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true",
                    help="actually start PIE and capture. Without it, reads only.")
    ap.add_argument("--tag", default="pie001", help="label recorded with the result")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--control-camera", default="forest_floor",
                    help="recipe camera used as the control station")
    ap.add_argument("--elevated-m", type=float, default=250.0,
                    help="height above traced ground for the in-cull station")
    ap.add_argument("--airship-m", type=float, default=1500.0,
                    help="height above traced ground for the airship station")
    ap.add_argument("--settle", type=float, default=30.0,
                    help="seconds for PIE to start before the first station")
    ap.add_argument("--station-settle", type=float, default=25.0,
                    help="seconds for streaming to settle after a teleport")
    ap.add_argument("--camera-settle", type=float, default=6.0,
                    help="seconds for the camera manager's cached POV to catch "
                         "up with the teleport before it is read back")
    ap.add_argument("--max-drift-cm", type=float, default=500.0,
                    help="refuse a station whose VIEW POINT is further than "
                         "this from where it was set")
    ap.add_argument("--min-cpu-ratio", type=float, default=0.30,
                    help="refuse a capture taken while the editor was throttled")
    args = ap.parse_args(argv)

    if args.frames < 30:
        print("REFUSE: --frames %d is too few to characterise a distribution."
              % args.frames)
        return 2

    ctrl = _load_camera(args.control_camera)
    if ctrl is None:
        print("REFUSE: no camera named %r in %s" % (args.control_camera, RECIPE))
        return 2
    cx, cy, cz = [float(v) for v in ctrl["location_cm"]]
    cp, cyaw = float(ctrl["rotation_deg"][0]), float(ctrl["rotation_deg"][1])
    recipe_fov = ctrl.get("fov_deg")

    # ONE declaration, three projections of it. The control keeps the recipe's
    # absolute Z because it must reproduce the editor series; the other two
    # take that camera's XY and a height above traced ground.
    stations = [
        {"name": args.control_camera + "_control", "x": cx, "y": cy,
         "absz": cz, "agl": None, "pitch": cp, "yaw": cyaw,
         "why": "control -- must reproduce the editor series at this camera"},
        {"name": "canopy_%dm" % int(args.elevated_m), "x": cx, "y": cy,
         "absz": None, "agl": args.elevated_m * 100.0, "pitch": -20.0,
         "yaw": cyaw,
         "why": "elevated, inside the 730 m cull radius -- forest in-cull and unoccluded"},
        {"name": "airship_%dm" % int(args.airship_m), "x": cx, "y": cy,
         "absz": None, "agl": args.airship_m * 100.0, "pitch": -30.0,
         "yaw": cyaw,
         "why": "airship altitude -- the aerial readability case"},
    ]

    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(VERIFY_DIR, exist_ok=True)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    started = False
    results = []
    rc = 0
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])

        pre, raw = _run(remote, remote_exec, PAYLOAD_PRE)
        if pre is None:
            print("NO MARKER on the pre-play read — could not look.")
            print(raw[:2000])
            return 1
        if pre.get("error"):
            print("PRE ERROR:", pre["error"])
            return 1
        if pre.get("in_play"):
            print("REFUSE: the editor is ALREADY in play. This tool will not")
            print("        adopt a session it did not start.")
            return 2

        print("=== CALIBRATION CLASS (binds every number below) ===")
        print("  class            PLAY IN EDITOR — not the editor viewport,")
        print("                   not a packaged build, not a cook")
        print("  level            %s" % pre.get("level"))
        print("  viewport size    %s"
              % (pre["viewport_size"] if pre.get("viewport_size")
                 else "COULD NOT READ"))
        print("  streaming        LIVE (not force-resident)")
        for k, v in sorted((pre.get("cvars") or {}).items()):
            print("  %-32s %s" % (k, v))
        print("")
        print("=== STATIONS ===")
        for s in stations:
            print("  %-24s %s" % (s["name"], s["why"]))

        if not args.go:
            print("")
            print("DRY RUN — PIE was NOT started. Re-run with --go.")
            return 0

        d, raw = _run(remote, remote_exec, PAYLOAD_BEGIN)
        if d is None or d.get("error"):
            print("BEGIN FAILED:", (d or {}).get("error", "no marker"))
            return 5
        started = True
        print("")
        print("PIE requested. Settling %.0f s." % args.settle)
        time.sleep(args.settle)

        d, raw = _run(remote, remote_exec, PAYLOAD_CSV_CATEGORIES)
        if d is None or d.get("error"):
            print("WARNING: CSV categories not enabled: %s"
                  % ((d or {}).get("error", "no marker")))
            print("         VSM and GPUScene columns will be ABSENT, and the")
            print("         reducer will say so rather than print zeros.")
        else:
            print("CSV categories issued: %s" % ", ".join(d["issued"]))

        for s in stations:
            print("")
            print("=== STATION %s ===" % s["name"])
            def _tp(z):
                return _run(remote, remote_exec,
                            PAYLOAD_TELEPORT
                            .replace("__X__", repr(s["x"]))
                            .replace("__Y__", repr(s["y"]))
                            .replace("__Z__", repr(float(z)))
                            .replace("__PITCH__", repr(s["pitch"]))
                            .replace("__YAW__", repr(s["yaw"])))

            # ---- step 1: get the pawn there FIRST, so the region streams.
            # World Partition streams around the PAWN. A ground trace taken
            # while the pawn is kilometres away hits nothing, and "not
            # streamed" reads exactly like "no terrain here".
            perch = s["absz"] if s["absz"] is not None else PERCH_Z_CM
            d, raw = _tp(perch)
            if d is None or d.get("error"):
                print("  COULD NOT PLACE THE PAWN: %s"
                      % ((d or {}).get("error", "no marker")))
                rc = max(rc, 4)
                continue
            print("  perch            %s cm — waiting %.0f s for streaming"
                  % (d.get("pawn_loc_cm"), args.station_settle))
            time.sleep(args.station_settle)

            # ---- step 2: now the ground is loaded, trace for it.
            ground_z = None
            if s["absz"] is not None:
                target_z = s["absz"]
                print("  ground           not traced — this station uses the "
                      "recipe's absolute Z")
            else:
                t, _ = _run(remote, remote_exec,
                            PAYLOAD_TRACE.replace("__X__", repr(s["x"]))
                                         .replace("__Y__", repr(s["y"])))
                if t is None or t.get("error"):
                    print("  TRACE FAILED: %s" % ((t or {}).get("error", "no marker")))
                    rc = max(rc, 4)
                    continue
                ground_z = t.get("ground_z_cm")
                if ground_z is None:
                    print("  COULD NOT FIND GROUND: %s" % t.get("ground_why"))
                    rc = max(rc, 4)
                    continue
                target_z = ground_z + s["agl"]
                print("  ground (traced vs COLLISION)  %.1f cm" % ground_z)

                # ---- step 3: move to the real station height.
                d, raw = _tp(target_z)
                if d is None or d.get("error"):
                    print("  COULD NOT PLACE THE PAWN AT STATION HEIGHT: %s"
                          % ((d or {}).get("error", "no marker")))
                    rc = max(rc, 4)
                    continue

            tl = [s["x"], s["y"], target_z]

            # ---- step 4: LET THE CAMERA CATCH UP, then read it.
            # GetPlayerViewPoint returns the camera manager's cached POV,
            # gated on GetCameraCacheTime() > 0. Read in the same tick as the
            # teleport it returns the pre-move cache.
            time.sleep(args.camera_settle)
            d, raw = _run(remote, remote_exec, PAYLOAD_VIEW)
            if d is None:
                print("  NO MARKER reading the view — could not look.")
                rc = max(rc, 4)
                continue
            if d.get("error"):
                print("  COULD NOT READ THE VIEW:", d["error"])
                rc = max(rc, 4)
                continue

            print("  target           %s cm" % tl)
            print("  pawn read-back   %s cm" % d.get("pawn_loc_cm"))
            print("  VIEW POINT       %s cm  rot %s"
                  % (d.get("view_loc_cm"), d.get("view_rot")))
            print("  FOV in PIE       %s deg   (recipe camera declares %s — "
                  "NOT matched, recorded as a class difference)"
                  % (d.get("fov_deg") if d.get("fov_deg") is not None
                     else "COULD NOT READ " + str(d.get("fov_why")),
                     recipe_fov))

            # The setter wrote the pawn; the view point is a different
            # instrument. If they disagree the frame belongs to another place.
            vl = d.get("view_loc_cm")
            if not vl:
                print("  REFUSE: no view point — cannot say where this frame is.")
                rc = max(rc, 4)
                continue
            drift = max(abs(vl[i] - tl[i]) for i in range(3))
            print("  view vs target   max axis drift %.1f cm" % drift)
            if drift > args.max_drift_cm:
                print("  REFUSE: the camera is not where the station was set.")
                print("          A frame measured here is about somewhere else.")
                rc = max(rc, 4)
                continue

            res, _ = _run(remote, remote_exec, PAYLOAD_RESIDENCY)
            prox = (res or {}).get("proxies")
            foli = (res or {}).get("foliage_actors")
            print("  resident         %s landscape proxies, %s foliage actors"
                  % (prox, foli))

            before = set(glob.glob(os.path.join(CSV_DIR, "*.csv")))
            cpu0 = _editor_cpu_seconds()
            t0 = time.time()
            d2, _ = _run(remote, remote_exec,
                         PAYLOAD_CAPTURE.replace("__FRAMES__", str(args.frames)))
            if d2 is None or d2.get("error"):
                print("  CAPTURE NOT ISSUED:", (d2 or {}).get("error", "no marker"))
                rc = max(rc, 1)
                continue

            path = None
            for _ in range(120):
                time.sleep(5.0)
                path = _newest_csv(before)
                if path:
                    break
            wall = time.time() - t0
            cpu1 = _editor_cpu_seconds()
            if path is None:
                print("  NO CSV APPEARED after %.0f s — could not look." % wall)
                rc = max(rc, 1)
                continue

            ratio = None
            if cpu0 is not None and cpu1 is not None and wall > 0:
                ratio = (cpu1 - cpu0) / wall
            if ratio is None:
                print("  CPU ratio        COULD NOT READ — throttle unverified")
            else:
                print("  CPU ratio        %.2f CPU-s per wall-s" % ratio)
            if ratio is not None and ratio < args.min_cpu_ratio:
                print("  REFUSE: the editor was THROTTLED during this capture.")
                print("          The numbers are real and about a state nobody")
                print("          cares about. Foreground the editor and re-run.")
                rc = max(rc, 5)
                continue

            stats, present = _reduce(path)
            print("  csv              %s" % os.path.basename(path))
            # NN13: FrameTime is the always-on core column; 0 frames means the
            # CSV is empty or not a frame log, so this station measured NOTHING.
            # Skip it rather than append an empty stats dict that the artefact
            # and the `if results` success gate would read as a measurement.
            _ft = stats.get("FrameTime")
            if not _ft or _ft.get("n", 0) == 0:
                print("    FrameTime recorded 0 frames — the CSV is empty or "
                      "not a frame log; this station measured NOTHING and is "
                      "NOT counted (non-negotiable 13).")
                rc = max(rc, 4)
                continue
            for name in COLUMNS:
                if name in stats:
                    st = stats[name]
                    print("    %-38s n=%-5d mean %12.3f  p50 %12.3f  p90 %12.3f"
                          % (name, st["n"], st["mean"], st["p50"], st["p90"]))
                elif name in CORE_COLUMNS:
                    print("    %-38s ABSENT — no frames for this CORE column "
                          "(the CSV is incomplete, not a disabled category)"
                          % name)
                else:
                    print("    %-38s ABSENT from the CSV (not zero — the "
                          "category did not record)" % name)
            results.append({"station": s, "stats": stats, "csv": path,
                            "proxies": prox, "foliage_actors": foli,
                            "cpu_ratio": ratio, "view": d.get("view_loc_cm"),
                            "view_rot": d.get("view_rot"),
                            "fov_deg": d.get("fov_deg"),
                            "ground_z_cm": ground_z,
                            "target": tl,
                            "drift_cm": drift,
                            "columns_present": present})

        print("")
        print("=== ENDING PLAY ===")
        _run(remote, remote_exec, PAYLOAD_END)
        time.sleep(10.0)
        d3, _ = _run(remote, remote_exec, PAYLOAD_CONFIRM)
        if d3 is None or d3.get("in_play"):
            print("  STILL IN PLAY (or unconfirmable). Press Escape in the")
            print("  editor and do not run another capture until it reads False.")
            return 6
        started = False
        print("  confirmed ended.")

        if results:
            out = _write_artefact(args, pre, results)
            print("")
            print("ARTEFACT: %s" % out)
        else:
            print("")
            print("NO STATION PRODUCED A MEASUREMENT — no artefact written.")
            rc = max(rc, 1)
        return rc

    finally:
        if started:
            print("")
            print("WARNING: leaving with PIE possibly still running.")
        try:
            remote.stop()
        except Exception:
            pass


def _write_artefact(args, pre, results):
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    path = os.path.join(VERIFY_DIR, "%s_pie_unit1_%s.md" % (stamp, args.tag))
    L = []
    L.append("# PIE frame cost — PHASE2_PLAN.md unit 1, tag `%s`" % args.tag)
    L.append("")
    L.append("**The first PIE measurement this project has taken.**")
    L.append("")
    L.append("## CALIBRATION CLASS — binds every number below")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| class | **PLAY IN EDITOR** — not editor viewport, not PIE-in-new-window, not a cook |")
    L.append("| level | `%s` |" % pre.get("level"))
    L.append("| viewport px | %s |" % (pre.get("viewport_size") or "COULD NOT READ"))
    L.append("| streaming | **LIVE** — not force-resident |")
    L.append("| frames per station | %d |" % args.frames)
    L.append("| GameMode | engine default; the level has **no PlayerStart** and pawn is `DefaultPawn` |")
    L.append("")
    L.append("Cvars in effect at capture time:")
    L.append("")
    L.append("| cvar | value |")
    L.append("|---|---|")
    for k, v in sorted((pre.get("cvars") or {}).items()):
        L.append("| `%s` | %s |" % (k, v))
    L.append("")
    L.append("**No editor-viewport figure may be compared into this table, "
             "and nothing here may be compared back out.** `RECIPES.md:6373` "
             "already calls PIE a different calibration class.")
    L.append("")
    for r in results:
        s = r["station"]
        L.append("## Station `%s`" % s["name"])
        L.append("")
        L.append("%s" % s["why"])
        L.append("")
        L.append("| | |")
        L.append("|---|---|")
        L.append("| view point | %s cm |" % r["view"])
        L.append("| view rotation | %s (pitch, yaw, roll) |" % r["view_rot"])
        L.append("| FOV in PIE | %s deg — **not matched to the recipe camera's "
                 "`fov_deg`, and not to the editor viewport's either.** One of "
                 "the uncontrolled variables between the two classes |"
                 % r["fov_deg"])
        L.append("| ground (line trace vs collision) | %s |"
                 % ("%s cm" % r["ground_z_cm"] if r["ground_z_cm"] is not None
                    else "not traced — station uses the recipe's absolute Z"))
        L.append("| view vs target drift | %.1f cm |" % r["drift_cm"])
        L.append("| resident landscape proxies | %s |" % r["proxies"])
        L.append("| resident foliage actors | %s |" % r["foliage_actors"])
        L.append("| editor CPU ratio during capture | %s |"
                 % ("COULD NOT READ" if r["cpu_ratio"] is None
                    else "%.2f CPU-s per wall-s" % r["cpu_ratio"]))
        L.append("| csv | `%s` |" % os.path.basename(r["csv"]))
        L.append("")
        L.append("| column | n | mean | p50 | p90 | max |")
        L.append("|---|---|---|---|---|---|")
        for name in COLUMNS:
            if name in r["stats"]:
                st = r["stats"][name]
                L.append("| `%s` | %d | %.3f | %.3f | %.3f | %.3f |"
                         % (name, st["n"], st["mean"], st["p50"], st["p90"],
                            st["max"]))
            else:
                L.append("| `%s` | — | **ABSENT from the CSV** — the category "
                         "did not record. This is *not* a zero. | | | |" % name)
        L.append("")
    L.append("## How to read the VSM columns")
    L.append("")
    L.append("`VSM/FreePages` against the `r.Shadow.Virtual.MaxPhysicalPages` "
             "pool is the direct saturation signal. `SinglePageCount` and "
             "`FullCount` count shadow **maps**, not pages — `PHASE2_PLAN.md` "
             "names those two as the discriminator and that is one step off; "
             "the correction is recorded in `measure_pie_cost`'s docstring.")
    L.append("")
    L.append("Citations, each opened against this install: "
             "`VirtualShadowMapArray.cpp:104` (`CSV_DEFINE_CATEGORY(VSM, false)`), "
             "`:2619`, `:2620`; "
             "`VirtualShadowMapCacheManager.cpp:685`; "
             "`GPUScene.cpp:48`; "
             "`SceneCulling.cpp:105` (default **on**), `:2676`.")
    L.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return path


if __name__ == "__main__":
    sys.exit(main())
