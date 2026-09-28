#!/usr/bin/env python3
"""Brief 5 C1/C2 capture driver. Launches ONE persistent editor (offscreen) on a
given map, fires ue_exec shot payloads against the live editor (each schedules a
HighResShot that completes over the editor's own ticks), polls
Saved/Screenshots/WindowsEditor for each shot's EXACT expected filename (mtime >=
the moment it was fired -- survives re-run overwrite), copies it to a derived dir,
then closes the editor by the PID THIS driver launched (never machine-wide).
READ-ONLY: no save, no asset/level edit.

Refuses to launch unless zero UnrealEditor* processes are already running
(rule 11: the port serves whichever editor holds it, and a machine-wide kill
would take a foreign editor with unsaved work).

Usage:
  python c_capture.py c1     # Alpine8K: legend refs + auto ring + auto deep
  python c_capture.py c2     # Showroom: discover, then lit 150/300 + card 150
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
UEPROJ = os.path.join(REPO, "LandscapeLab")
SHOTDIR = os.path.join(UEPROJ, "Saved", "Screenshots", "WindowsEditor")
PY = sys.executable
LAUNCHED_PID = None


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def editor_pids():
    r = _ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def launch(map_path):
    global LAUNCHED_PID
    pre = editor_pids()
    if pre:
        print("REFUSE: %d UnrealEditor process(es) already running %s (rule 11)"
              % (len(pre), sorted(pre)))
        return False
    ps = ["powershell", "-NoProfile", "-File",
          os.path.join(SCRIPTS, "launch_editor.ps1"), "-Map", map_path]
    print("LAUNCH", map_path)
    subprocess.Popen(ps, cwd=REPO)
    # capture the PID this driver launched
    t0 = time.time()
    while time.time() - t0 < 60:
        new = editor_pids() - pre
        if new:
            LAUNCHED_PID = sorted(new)[0]
            print("LAUNCHED PID", LAUNCHED_PID)
            return True
        time.sleep(2)
    print("REFUSE: no new UnrealEditor process appeared within 60 s")
    return False


def wait_ready(timeout=300):
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


def run_payload(scratch_name, scratch_obj, payload):
    json.dump(scratch_obj, open(os.path.join(REPO, scratch_name), "w",
                                encoding="utf-8"), indent=1)
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", payload)],
                       capture_output=True, text=True)
    tail = (r.stdout or "")[-500:]
    print("  ue_exec", payload, "rc", r.returncode, tail.replace("\n", " ")[-380:])
    return r.returncode, tail


def poll_shot(out_name, fired_at, dst_name=None, timeout=180):
    """Wait for SHOTDIR/<out_name>.png with mtime >= fired_at, size-stable."""
    want = os.path.join(SHOTDIR, out_name + ".png")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(want) and os.path.getmtime(want) >= fired_at - 1:
            s1 = os.path.getsize(want)
            time.sleep(2)
            if s1 > 0 and os.path.getsize(want) == s1:
                dst = os.path.join(DERIVED, (dst_name or out_name) + ".png")
                shutil.copy2(want, dst)
                print("  SHOT", dst_name or out_name, os.path.getsize(want))
                return dst
        time.sleep(3)
    print("  NO PNG for", out_name, "(expected", want, ")")
    return None


def close_editor():
    cen = subprocess.run([PY, os.path.join(SCRIPTS, "census_project.py")],
                         capture_output=True, text=True)
    print("CENSUS rc", cen.returncode, (cen.stdout or "")[-300:])
    if LAUNCHED_PID:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue"
            % LAUNCHED_PID)
    time.sleep(4)
    left = editor_pids()
    print("LAUNCHED PID", LAUNCHED_PID, "still alive:", LAUNCHED_PID in left,
          "| all editors now:", sorted(left))
    restore = os.path.join(UEPROJ, "Saved", "Autosaves", "PackageRestoreData.json")
    print("PackageRestoreData present:", os.path.exists(restore))


def c1():
    global DERIVED
    DERIVED = os.path.join(REPO, "research", "brief5", "derived", "c1_lodcolor")
    os.makedirs(DERIVED, exist_ok=True)
    if not launch("/Game/Alpine8K") or not wait_ready():
        return
    results = []

    def shot(force_lod, deep_m, name):
        fired = time.time()
        rc, tail = run_payload("_scratch_c1.json",
                               {"station": "ring_station_v1", "force_lod": force_lod,
                                "deep_offset_m": deep_m, "out_name": name,
                                "expected_level": "Alpine8K"},
                               "brief5_c1_lodcolor.py")
        png = poll_shot(name, fired)
        results.append({"name": name, "rc": rc, "png": png})

    for fl in (0, 1, 2, 3, 4):
        shot(fl, 0.0, "c1_ref_lod%d" % fl)
    shot(-1, 0.0, "c1_auto_ring")
    shot(-1, 300.0, "c1_auto_deep")
    # render-data readback (no shot) -- needed on NO-OP, captured regardless
    rc, tail = run_payload("_scratch_c1.json",
                           {"station": "ring_station_v1", "force_lod": -1,
                            "deep_offset_m": 0.0, "out_name": "unused",
                            "expected_level": "Alpine8K"},
                           "brief5_c1_renderdata.py")
    results.append({"name": "renderdata", "rc": rc})
    json.dump(results, open(os.path.join(DERIVED, "_capture_manifest.json"), "w"),
              indent=1)
    close_editor()


def c2():
    global DERIVED
    DERIVED = os.path.join(REPO, "research", "brief5", "derived", "c2_showroom")
    os.makedirs(DERIVED, exist_ok=True)
    if not launch("/Game/PN_interactiveSpruceForest/Map/Showroom") or not wait_ready():
        return
    # discovery (placements + target), no shot
    rc, tail = run_payload("_scratch_c2.json",
                           {"expected_level": "Showroom"}, "brief5_c2_discover.py")
    results = [{"name": "discover", "rc": rc, "tail": tail}]
    # one HighResShot per invocation (F1): lit 150, lit 300, forced-card 150
    for dist, card, name in ((150.0, False, "c2_showroom_150_lit"),
                             (300.0, False, "c2_showroom_300_lit"),
                             (150.0, True, "c2_showroom_150_card")):
        fired = time.time()
        rc, _ = run_payload("_scratch_c2shot.json",
                            {"dist_m": dist, "force_card": card, "out_name": name,
                             "expected_level": "Showroom"}, "brief5_c2_shot.py")
        png = poll_shot(name, fired)
        results.append({"name": name, "rc": rc, "png": png})
    json.dump(results, open(os.path.join(DERIVED, "_capture_manifest.json"), "w"),
              indent=1)
    close_editor()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("c1", "c2"):
        print("usage: c_capture.py c1|c2")
        sys.exit(2)
    {"c1": c1, "c2": c2}[sys.argv[1]]()
