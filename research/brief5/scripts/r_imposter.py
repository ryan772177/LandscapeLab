#!/usr/bin/env python3
"""Brief 5 REPAIR R4 driver -- read-only imposter override diff. Launches ONE
offscreen Alpine8K editor (rule 11: zero editors first), runs
brief5_r4_imposter.py (which writes research/brief5/input/r4_imposter_read.json),
and closes on the hardened R-EDITOR-CLOSE path (quiescence + retried clean live
census + kill by launched PID). No writes beyond the read JSON."""
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
UEPROJ = os.path.join(REPO, "LandscapeLab")
CONTENT = os.path.join(UEPROJ, "Content")
PY = sys.executable
MAP = "/Game/Alpine8K"


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
             "--stage-name", "r4_close_census", "--timeout", "20"],
            capture_output=True, text=True)
        tail = (cen.stdout or "")
        print("CENSUS attempt %d rc %s %s" % (attempt + 1, cen.returncode, tail[-300:]))
        if cen.returncode == 0 and '"clean":' in tail and '"dirty_count":' in tail:
            return True, ('"dirty_count": 0' in tail) and ('"clean": true' in tail)
        time.sleep(8)
    return False, False


def close_editor(pid):
    wait_quiescent()
    parsed, clean = live_census()
    if not (parsed and clean):
        print("REFUSE KILL: census not clean/parseable -- editor LEFT alive")
        return {"killed": False, "census_parsed": parsed, "census_clean": clean}
    if pid:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
    time.sleep(4)
    restore = os.path.join(UEPROJ, "Saved", "Autosaves", "PackageRestoreData.json")
    info = {"killed": True, "census_clean": clean, "still_alive": pid in editor_pids(),
            "package_restore_present": os.path.exists(restore)}
    print("CLOSE", info)
    return info


def main():
    if editor_pids():
        print("REFUSE: UnrealEditor already running (rule 11)")
        return 3
    pid = launch(editor_pids())
    if pid is None or not wait_ready():
        return 1
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", "brief5_r4_imposter.py"),
                        "--stage-name", "r4_imposter", "--timeout", "20"],
                       capture_output=True, text=True)
    print("ue_exec brief5_r4_imposter rc", r.returncode)
    print((r.stdout or "")[-1200:])
    info = close_editor(pid)
    # M3: a refused kill (editor deliberately left alive) is not a clean run.
    if not info.get("killed"):
        print("WARN: editor left alive (census-gated kill refused); exit 2")
        return 2
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
