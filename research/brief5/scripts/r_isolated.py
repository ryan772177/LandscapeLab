#!/usr/bin/env python3
"""Brief 5 isolated_check capture (operator-ordered R2 follow-up). READ-ONLY.

Launches ONE offscreen Alpine8K editor (rule 11), fires brief5_c1_lodcolor.py at
the two isolated camera stations (find_isolated_instances.py) with auto LOD
(force_lod -1), copies the stills to derived/iso_lodcolor, closes on the hardened
R-EDITOR-CLOSE path. Then iso_analyze.py classifies each target's single box.

The two stills answer the runtime question directly: at 300 m, inside the 512 m
cull, a hold that TOOK renders the target as geometry (red/green LOD1/2); a hold
with NO runtime effect renders the pre-hold card (ConiferPine blue LOD3 / SpruceSub
yellow LOD4).
"""
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
UEPROJ = os.path.join(REPO, "LandscapeLab")
CONTENT = os.path.join(UEPROJ, "Content")
SHOTDIR = os.path.join(UEPROJ, "Saved", "Screenshots", "WindowsEditor")
DERIVED = os.path.join(REPO, "research", "brief5", "derived", "iso_lodcolor")
PY = sys.executable
MAP = "/Game/Alpine8K"
SHOTS = [("iso_ConiferPine_station", "iso_conifer"),
         ("iso_SpruceSub_station", "iso_spruce"),
         # render-sanity CONTROL: ring_station_v1 provably rendered trees in R2.
         # If this renders geometry and the two iso shots are white, the iso
         # LOCATIONS don't render (not an offscreen-render failure).
         ("ring_station_v1", "iso_control_ring")]


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def editor_pids():
    r = _ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def main_editor_pids():
    r = _ps("Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def launch(pre):
    subprocess.Popen(["powershell", "-NoProfile", "-File",
                      os.path.join(SCRIPTS, "launch_editor.ps1"), "-Map", MAP],
                     cwd=REPO)
    t0 = time.time()
    while time.time() - t0 < 60:
        new = main_editor_pids() - pre
        if new:
            pid = sorted(new)[0]
            print("LAUNCHED PID", pid)
            return pid
        time.sleep(2)
    print("REFUSE: no new UnrealEditor.exe within 60 s")
    return None


def wait_ready(timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")],
                          capture_output=True, text=True).returncode == 0:
            print("EDITOR READY", round(time.time() - t0, 1), "s")
            return True
        time.sleep(6)
    print("EDITOR NOT READY")
    return False


def run_shot(station, out_name):
    scratch = {"station": station, "force_lod": -1, "deep_offset_m": 0.0,
               "out_name": out_name, "expected_level": "Alpine8K"}
    with open(os.path.join(REPO, "_scratch_c1.json"), "w", encoding="utf-8") as fh:
        json.dump(scratch, fh, indent=1)
    fired = time.time()
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", "brief5_c1_lodcolor.py"),
                        "--stage-name", out_name, "--timeout", "20"],
                       capture_output=True, text=True)
    print("  ue_exec", out_name, "rc", r.returncode,
          (r.stdout or "")[-260:].replace("\n", " "))
    return fired


def poll_shot(out_name, fired, timeout=180):
    want = os.path.join(SHOTDIR, out_name + ".png")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(want) and os.path.getmtime(want) >= fired - 1:
            s1 = os.path.getsize(want)
            time.sleep(2)
            if s1 > 0 and os.path.getsize(want) == s1:
                shutil.copy2(want, os.path.join(DERIVED, out_name + ".png"))
                print("  SHOT", out_name, os.path.getsize(want))
                return True
        time.sleep(3)
    print("  NO PNG for", out_name)
    return False


def newest_content_mtime():
    newest = 0.0
    for dp, _dn, fns in os.walk(CONTENT):
        for fn in fns:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(dp, fn)))
            except OSError:
                pass
    return newest


def wait_quiescent(stable_s=20, timeout=180):
    t0 = time.time()
    last, since = newest_content_mtime(), time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        cur = newest_content_mtime()
        if cur > last:
            last, since = cur, time.time()
        elif time.time() - since >= stable_s:
            return True
    return False


def live_census():
    for attempt in range(3):
        cen = subprocess.run(
            [PY, os.path.join(SCRIPTS, "ue_exec.py"),
             os.path.join(SCRIPTS, "dirty_package_census_payload.txt"),
             "--stage-name", "iso_close_census", "--timeout", "20"],
            capture_output=True, text=True)
        tail = (cen.stdout or "")
        print("CENSUS attempt %d rc %s %s" % (attempt + 1, cen.returncode, tail[-260:]))
        if cen.returncode == 0 and '"clean":' in tail and '"dirty_count":' in tail:
            return True, ('"dirty_count": 0' in tail) and ('"clean": true' in tail)
        time.sleep(8)
    return False, False


def close_editor(pid):
    wait_quiescent()
    parsed, clean = live_census()
    if not (parsed and clean):
        print("REFUSE KILL: census not clean/parseable -- editor LEFT alive")
        return
    if pid:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
    time.sleep(4)
    print("CLOSE killed", pid, "editors now", sorted(editor_pids()))


def main():
    os.makedirs(DERIVED, exist_ok=True)
    for st, _ in SHOTS:
        if not os.path.exists(os.path.join(REPO, "research", "brief5", "input",
                                           st + ".json")):
            print("REFUSE: missing station %s.json -- run find_isolated_instances.py"
                  % st)
            return 2
    if editor_pids():
        print("REFUSE: UnrealEditor already running (rule 11)")
        return 3
    pid = launch(editor_pids())
    if pid is None or not wait_ready():
        return 1
    for station, out_name in SHOTS:
        f = run_shot(station, out_name)
        poll_shot(out_name, f)
    close_editor(pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
