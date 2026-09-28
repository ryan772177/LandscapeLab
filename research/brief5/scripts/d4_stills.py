#!/usr/bin/env python
"""Brief 5 D4 Task 2 -- five-station reference stills of the dense world.

Reference, NOT a gate (Ryan looks; no ruling). Launches the editor offscreen,
sets the viewport to each station's camera and shoots a 4K HighResShot of the
saved 812,258-tree world, then copies the PNGs to research/brief5/derived/
d4_stills/. Read-only (no spawn, no save). Must run BEFORE the Task 3 revert.
"""
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
BR = os.path.join(REPO, "research", "brief5")
UEPROJ = os.path.join(REPO, "LandscapeLab")
SHOTDIR = os.path.join(UEPROJ, "Saved", "Screenshots", "WindowsEditor")
OUT = os.path.join(BR, "derived", "d4_stills")
PY = sys.executable
LAUNCHED = set()


def log(m):
    print("[D4stills] " + m, flush=True)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def editor_pids():
    r = ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
           "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def cameras():
    ff = json.load(open(os.path.join(BR, "input", "forest_station.json"),
                        encoding="utf-8"))["camera"]
    om = json.load(open(os.path.join(BR, "input", "open_max_station.json"),
                        encoding="utf-8"))["camera"]
    cen = json.load(open(os.path.join(BR, "input", "_census_stations.json"),
                        encoding="utf-8"))["stations"]
    return [("forest_floor", ff), ("open_max", om),
            ("treeline", cen["treeline"]["camera"]),
            ("plaza", cen["plaza"]["camera"]),
            ("vista", cen["vista"]["camera"])]


def main():
    os.makedirs(OUT, exist_ok=True)
    if editor_pids():
        log("REFUSE: editor already running (rule 11)")
        return 2
    pre = editor_pids()
    subprocess.Popen(["powershell", "-NoProfile", "-File",
                      os.path.join(SCRIPTS, "launch_editor.ps1"),
                      "-Map", "/Game/Alpine8K"], cwd=REPO)
    t0 = time.time()
    while time.time() - t0 < 90:
        LAUNCHED.update(editor_pids() - pre)
        if LAUNCHED:
            break
        time.sleep(2)
    if not LAUNCHED:
        log("no editor appeared")
        return 3
    log("launched %s; waiting ready" % sorted(LAUNCHED))
    ready, t0 = False, time.time()
    while time.time() - t0 < 420:
        if subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")], cwd=REPO,
                          capture_output=True, text=True).returncode == 0:
            ready = True
            break
        time.sleep(6)
    if not ready:
        log("editor not ready")
        for p in LAUNCHED:
            ps("Stop-Process -Id %d -Force" % p)
        return 3
    log("ready")

    results = {}
    try:
        for name, c in cameras():
            shot = "d4_still_" + name
            json.dump({"camera": c, "name": shot},
                      open(os.path.join(REPO, "_scratch_d4still.json"), "w",
                           encoding="utf-8"), indent=1)
            fired = time.time()
            r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                                os.path.join(SCRIPTS, "payloads", "d4_still.py")],
                               cwd=REPO, capture_output=True, text=True, timeout=180)
            tail = (r.stdout or "")[-300:].replace("\n", " ")
            log("%s ue_exec rc %d %s" % (name, r.returncode, tail[-200:]))
            # poll SHOTDIR/<shot>.png, mtime >= fired, size-stable
            want = os.path.join(SHOTDIR, shot + ".png")
            got, t1 = None, time.time()
            while time.time() - t1 < 180:
                if os.path.isfile(want) and os.path.getmtime(want) >= fired - 2:
                    s1 = os.path.getsize(want)
                    time.sleep(2)
                    if os.path.getsize(want) == s1 and s1 > 0:
                        got = want
                        break
                time.sleep(3)
            if got:
                dst = os.path.join(OUT, name + ".png")
                shutil.copy2(got, dst)
                results[name] = {"ok": True, "png": os.path.relpath(dst, REPO),
                                 "bytes": os.path.getsize(dst)}
                log("  %s -> %s (%d bytes)" % (name, dst, os.path.getsize(dst)))
            else:
                results[name] = {"ok": False, "reason": "shot not on disk"}
                log("  %s: shot not found" % name)
    finally:
        for p in sorted(LAUNCHED):
            ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % p)
        time.sleep(4)
        log("editors after close: %s" % sorted(editor_pids()))

    json.dump({"_what": "Brief 5 D4 Task 2 five-station reference stills (dense "
                        "world, 4K, before revert).", "stills": results},
              open(os.path.join(BR, "derived", "d4_stills.json"), "w",
                   encoding="utf-8"), indent=1)
    n_ok = sum(1 for v in results.values() if v.get("ok"))
    log("DONE: %d/5 stills captured -> %s" % (n_ok, os.path.relpath(OUT, REPO)))
    return 0 if n_ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
