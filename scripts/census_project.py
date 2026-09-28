"""census_project.py — read-only census + survey shots for one sample project.

TWO PASSES, AND WHY
-------------------
  pass 1  editor, `-ExecutePythonScript`: load the map, run the research-desk
          census, derive the survey camera stations, write both to JSON.
  pass 2  `-game`, one launch per station: `BugItGo` to the station then
          `HighResShot`, dwell, collect the frame.

Pass 2 is separate because **`-ExecutePythonScript` calls
`UUnrealEdEngine::CloseEditor()` the moment the script returns**, and
`HighResShot` completes over SUBSEQUENT ticks. Measured 2026-09-09: a slate
post-tick callback registered, the editor exited 0.6 s later, and the run
reported success with zero shots filed. No amount of waiting inside that
script can work -- there are no ticks left to wait for.

`-game` + `-ExecCmds` is the pattern E3 proved (R-PERFSTANDALONE): BugItGo is
accepted and HighResShot writes the frame.

ue_exec IS NOT USABLE HERE. The sample projects have no `bRemoteExecution` in
their Config (ours is LandscapeLab/Config/DefaultEngine.ini:139), and adding
it would be a config write outside this repo that standing rule 1 forbids.

NOTHING IS SAVED, in either pass.
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE = r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
STAGE = os.path.join(REPO, "LandscapeLab", "Saved", "LLPython")
LOGS = os.path.join(REPO, "LandscapeLab", "Saved", "Logs")

PROJECTS = {
    "CitySample": {
        "uproject": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\CitySample_5.8\data\CitySample.uproject",
        "map": "/Game/Map/Small_City_LVL", "engine": "5.8", "convert": False,
    },
    "ElectricDreams": {
        # THE PCG REFERENCE -- the one target neither other census could
        # populate. City Sample and Dark Ruins both returned pcg_graphs 0,
        # correctly: neither uses PCG.
        #
        # IT HAS A C++ MODULE (ElectricDreamsSample) BUT NO REBUILD WALL.
        # Valley is blocked because its modules are 5.7 binaries under a 5.8
        # engine. This project declares EngineAssociation 5.8 and ships a
        # 5.8 UnrealEditor-ElectricDreamsSample.dll, so the versions match and
        # there is nothing to compile. The presence of a module is NOT the
        # thing that blocks -- the version mismatch is.
        "uproject": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\ElectricDreamsSample_5.8\data\ElectricDreamsSample.uproject",
        # EditorStartupMap is /Game/Levels/Startup -- the THIRD project in
        # this census whose editor opens on a loading map. Census the
        # close-range map by default; pass --map for the far-range one:
        #     --map /Game/Levels/PCG/ElectricDreams_PCG
        "map": "/Game/Levels/PCG/ElectricDreams_PCGCloseRange",
        "engine": "5.8", "convert": False,
    },
    "DarkRuins": {
        # THE VAULT COPY, NOT THE LAUNCHER'S INSTALL. "Install to Engine" put
        # a second copy under OneDrive\Documents\Unreal Projects, and
        # converting 25.5 GB there would push the whole project through
        # OneDrive sync mid-conversion -- churn, and a real risk of file locks
        # while the editor is rewriting assets. Both copies carry the same
        # 13,717 uassets and 79 umaps; this one is outside any sync root.
        #
        # Blueprint-only (no Modules in the uproject), so unlike Valley it has
        # no C++ modules to rebuild. 5.6 -> 5.8 converts in place; disposable
        # copy, operator-authorised.
        "uproject": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\DarkRuinac4b642bf8b9V1\data\DarkRuins.uproject",
        # EditorStartupMap AND GameDefaultMap are both /Game/Main.Main, so
        # this project has no loading-map trap -- named explicitly anyway.
        "map": "/Game/Main",
        "engine": "5.6", "convert": True,
    },
    "ValleyOfTheAncient": {
        # EditorStartupMap is /Game/AncientContent/Maps/Startup, so an editor
        # opened without an explicit map censuses the LOADING map -- the exact
        # trap the first City Sample pass fell into. GameDefaultMap names the
        # real one and that is what is loaded here.
        "uproject": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\AncientGame_5.7\data\AncientGame.uproject",
        "map": "/Game/AncientContent/Maps/AncientWorld",
        "engine": "5.7", "convert": True,
    },
}


def stage_script(name, src_path, subs):
    src = io.open(src_path, encoding="utf-8").read()
    for k, v in subs.items():
        src = src.replace("__%s__" % k, str(v))
    left = [x for x in sorted(set(re.findall(r"__[A-Z_]+__", src)))
            if x != "__LL__"]
    if left:
        raise SystemExit("REFUSE: unsubstituted placeholders %s in %s"
                         % (left, os.path.basename(src_path)))
    compile(src, name, "exec")          # a payload that cannot compile costs
    os.makedirs(STAGE, exist_ok=True)   # a second, not a six-minute launch
    dst = os.path.join(STAGE, name)
    io.open(dst, "w", encoding="utf-8", newline="").write(src)
    return dst


def wait_for(path, proc, deadline_s, label, since):
    """Wait for `path` to be written AFTER `since`.

    EXISTENCE IS NOT COMPLETION, AND THIS COST A FALSE RESULT. The first
    version returned True the moment the file existed. On a re-run the file
    was already there from the previous pass, so it returned instantly,
    terminated the editor before its script had even run, and printed the OLD
    census as this run's -- with the OLD errors in it. I read that as "the fix
    did not work" when the fix had never been exercised.

    Third time this trap has appeared in this session: `capture_truth`
    globbing a station PNG, the LOD driver matching "lod0" by substring, and
    now this. The shape is always the same -- asking "is there a file?" when
    the question is "is there a file FROM THIS RUN?".
    """
    t0 = time.time()

    def fresh():
        try:
            return os.path.exists(path) and os.path.getmtime(path) >= since
        except OSError:
            return False

    while time.time() - t0 < deadline_s:
        time.sleep(10.0)
        if fresh():
            time.sleep(4.0)
            return True
        if proc.poll() is not None:
            print("  %s: process exited (%.0f s), fresh output: %s"
                  % (label, time.time() - t0, fresh()))
            return fresh()
        print("  %s ... %.0f s" % (label, time.time() - t0))
    return fresh()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=sorted(PROJECTS))
    ap.add_argument("--map", default="")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--shot-dwell", type=float, default=110.0)
    ap.add_argument("--shot-delay-frames", type=int, default=900,
                    help="r.HighResScreenshotDelay, in FRAMES. The capture is "
                         "deferred this long after the request, which is the "
                         "only way to get the shot AFTER the teleport when "
                         "every command fires in one -ExecCmds batch at "
                         "startup. 8 frames produced five identical views.")
    ap.add_argument("--skip-shots", action="store_true")
    a = ap.parse_args()

    cfg = PROJECTS[a.project]
    if not os.path.exists(cfg["uproject"]):
        raise SystemExit("REFUSE: no uproject at %s" % cfg["uproject"])
    mp = a.map or cfg["map"]
    tag = mp.rsplit("/", 1)[-1] if mp else "default"
    rx, ry = (int(v) for v in a.res.lower().split("x"))

    cdir = os.path.join(REPO, "research", "census")
    out_json = os.path.join(cdir, "%s__%s.json" % (a.project, tag)).replace("\\", "/")
    st_json = os.path.join(cdir, "%s__%s.stations.json" % (a.project, tag)).replace("\\", "/")
    shot_dir = os.path.join(cdir, "shots", a.project)
    os.makedirs(shot_dir, exist_ok=True)

    # ---------------- pass 1: census + stations --------------------------
    census = stage_script("census_%s_inner.py" % a.project.lower(),
                          os.path.join(REPO, "scripts", "payloads",
                                       "sample_census.py"),
                          {"OUT": out_json, "MAPS": ""})
    driver = stage_script("census_%s_driver.py" % a.project.lower(),
                          os.path.join(REPO, "scripts", "payloads",
                                       "census_and_shoot.py"),
                          {"OUT": out_json, "MAP": mp,
                           "STATIONS_OUT": st_json,
                           "CENSUS_SRC": census.replace("\\", "/")})
    log1 = os.path.join(LOGS, "census_%s.log" % a.project.lower())
    print("pass 1: census %s  map=%s" % (a.project, mp or "(project default)"))
    launch_t = time.time() - 1.0     # anchor BEFORE launch, for freshness
    p1 = subprocess.Popen([UE, cfg["uproject"],
                           "-ExecutePythonScript=%s" % driver,
                           "-nosplash", "-AbsLog=%s" % log1])
    got_fresh = wait_for(st_json, p1, 2400, "pass1", launch_t)
    try:
        p1.terminate(); p1.wait(timeout=90)
    except Exception:
        try: p1.kill()
        except Exception: pass

    result = {"project": a.project, "map": mp, "engine": cfg["engine"],
              "converted_in_place": cfg["convert"],
              "json": os.path.relpath(out_json, REPO),
              "json_written": os.path.exists(out_json),
              "log_pass1": os.path.relpath(log1, REPO)}
    if os.path.exists(out_json):
        d = json.load(open(out_json, encoding="utf-8"))
        result["current_world"] = d.get("current_world")
        result["sections"] = {k: (len(v) if isinstance(v, (list, dict)) else v)
                              for k, v in (d.get("sections") or {}).items()}
    result["pass1_produced_fresh_output"] = got_fresh
    if not got_fresh:
        result["shots"] = ("NO FRESH STATIONS -- pass 1 did not write output "
                           "for THIS run. Any files on disk are from an "
                           "earlier pass and must not be read as this "
                           "result.")
        print(json.dumps(result, indent=2))
        return 1
    if not os.path.exists(st_json):
        result["shots"] = "NO STATIONS -- pass 1 did not derive them"
        print(json.dumps(result, indent=2))
        return 1
    stations = json.load(open(st_json, encoding="utf-8"))
    result["bounds"] = stations.get("bounds")
    result["stations_world"] = stations.get("current_world")

    if a.skip_shots:
        result["shots"] = "skipped"
        print(json.dumps(result, indent=2))
        return 0

    # ---------------- pass 2: one -game launch per station ---------------
    shot_delay_frames = a.shot_delay_frames
    shots_src = os.path.join(os.path.dirname(cfg["uproject"]), "Saved",
                             "Screenshots", "WindowsEditor")
    filed = []
    for st in stations.get("stations", []):
        before = set(glob.glob(os.path.join(shots_src, "*.png")))
        x, y, z = st["loc"]
        # `ghost` BEFORE BugItGo, AND IT IS NOT OPTIONAL.
        #
        # Measured 2026-09-09: BugItGo was accepted and logged the right
        # coordinates -- "BugItGo to: X=-27006 Y=-25505 Z=48479" -- and every
        # frame still came back as the same ground-level plaza view. The pawn
        # has gravity and collision, so it teleports 480 m up and FALLS BACK
        # before the screenshot lands. Five stations, five frames, one
        # viewpoint; they differed only in shader-compile state, which is what
        # made them look like five different shots at a glance.
        #
        # `ghost` puts the pawn in no-clip flight, so the teleport holds.
        # r.HighResScreenshotDelay lets the frame settle after the move.
        # THE DELAY IS IN FRAMES, AND 8 WAS EFFECTIVELY ZERO.
        #
        # Attempt 1 (plain BugItGo) and attempt 2 (ghost + delay 8) both gave
        # five frames of the same plaza. `ghost` addressed the wrong
        # hypothesis -- the pawn falling -- and the real problem is that
        # `-ExecCmds` fires every command in one batch at startup, so
        # HighResShot was requested before the teleport had reached the
        # rendered view. 8 frames is under a fifth of a second.
        #
        # r.HighResScreenshotDelay defers the CAPTURE by N frames from the
        # request, which is the only lever available inside a single
        # `-ExecCmds` batch. Set high enough that the world has streamed and
        # the camera has settled.
        cmds = ",".join([
            "r.setRes %dx%dw" % (rx, ry),
            "ghost",
            "BugItGo %.1f %.1f %.1f %.1f %.1f 0" % (x, y, z, st["pitch"],
                                                    st["yaw"]),
            "r.HighResScreenshotDelay %d" % shot_delay_frames,
            "HighResShot %dx%d" % (rx, ry),
        ])
        log2 = os.path.join(LOGS, "shot_%s_%s.log" % (a.project.lower(),
                                                      st["name"]))
        p2 = subprocess.Popen([UE, cfg["uproject"], mp, "-game", "-windowed",
                               "-ResX=%d" % rx, "-ResY=%d" % ry,
                               "-ExecCmds=%s" % cmds, "-nosplash",
                               "-NoLoadingScreen", "-AbsLog=%s" % log2])
        t0 = time.time()
        got = None
        while time.time() - t0 < a.shot_dwell + 180:
            time.sleep(10.0)
            fresh = sorted(set(glob.glob(os.path.join(shots_src, "*.png")))
                           - before, key=os.path.getmtime)
            if fresh and time.time() - t0 > a.shot_dwell * 0.4:
                got = fresh[-1]
                break
            if p2.poll() is not None:
                break
        try:
            p2.terminate(); p2.wait(timeout=60)
        except Exception:
            try: p2.kill()
            except Exception: pass
        if got:
            dst = os.path.join(shot_dir, "%s__%s.png" % (tag, st["name"]))
            shutil.copy2(got, dst)
            filed.append(os.path.relpath(dst, REPO))
            print("  shot %-16s -> %s" % (st["name"], os.path.basename(dst)))
        else:
            print("  shot %-16s NO FRAME" % st["name"])
    result["shots_filed"] = filed

    # ---- DID THE CAMERA ACTUALLY MOVE? ----------------------------------
    # Camera placement cannot be verified in-process, so this is the only
    # available check -- and on the first run it would have FAILED: BugItGo
    # logged the right coordinates and every frame was the same plaza. Without
    # this, five frames of one viewpoint file as a five-angle survey.
    #
    # Compared on a downscale, because shader compilation progresses between
    # launches and recolours a scene that has not moved. Structural difference
    # survives the downscale; a colour shift largely does not.
    try:
        from PIL import Image
        import numpy as np
        import itertools
        arrs = [np.asarray(Image.open(os.path.join(REPO, f))
                           .convert("L").resize((160, 90))).astype(float)
                for f in filed]
        diffs = [float(np.abs(a - b).mean())
                 for a, b in itertools.combinations(arrs, 2)]
        result["shot_differentiation"] = {
            "min_pairwise_mean_abs_diff": round(min(diffs), 2) if diffs else None,
            "max_pairwise_mean_abs_diff": round(max(diffs), 2) if diffs else None,
            "_metric": "greyscale, 160x90",
            "verdict": "NO VERDICT -- THIS METRIC CANNOT ANSWER THE QUESTION",
            "_why_no_verdict":
                "Calibrated against a KNOWN-BAD set (5 frames of one "
                "viewpoint, camera provably never moved) and it scored "
                "min 10.37 -- HIGHER than a run whose camera did move "
                "(9.77). A threshold that ranks the failure above the "
                "success is worse than no threshold. Shader compilation "
                "progresses between launches and recolours a static scene "
                "by more than a camera move changes it, and greyscale does "
                "not suppress that. VISUAL CONFIRMATION IS REQUIRED; do not "
                "file these as a multi-angle survey on the strength of a "
                "number.",
        }
    except Exception as e:
        result["shot_differentiation"] = {"error": str(e)}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
