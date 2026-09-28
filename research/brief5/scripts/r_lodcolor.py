#!/usr/bin/env python3
"""Brief 5 REPAIR R2 -- prove the (now-persisted) hold TOOK AT RUNTIME. READ-ONLY.

Re-runs C1's Mesh LOD Coloration capture POST-HOLD at the ring station and the
300 m band camera, with the SAME shot payload (brief5_c1_lodcolor.py) and the
SAME classifier (c1_lod_readback.py --prefix r2), so the mask and counting are
identical to C1. Writes stills to derived/r2_lodcolor and r2_renderdata.json, so
the committed C1 NO-OP baseline is untouched.

Then c1_lod_readback.py --prefix r2 produces r2_lod_readback.json; >=90% geometric
LOD in the band => HOLD TOOK, MEASURED (the C1 baseline read ~80% CARD).

Launches ONE offscreen editor on Alpine8K (rule 11: zero editors first), fires
three payloads, closes on R-EDITOR-CLOSE's kill path (quiescence + a clean live
dirty census, retried; kill by the launched PID).
"""
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
UEPROJ = os.path.join(REPO, "LandscapeLab")
CONTENT = os.path.join(UEPROJ, "Content")
SHOTDIR = os.path.join(UEPROJ, "Saved", "Screenshots", "WindowsEditor")
DERIVED = os.path.join(REPO, "research", "brief5", "derived", "r2_lodcolor")
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


def run_shot(force_lod, deep_m, out_name, renderdata_out=None):
    import json
    scratch = {"station": "ring_station_v1", "force_lod": force_lod,
               "deep_offset_m": deep_m, "out_name": out_name,
               "expected_level": "Alpine8K"}
    if renderdata_out:
        scratch["renderdata_out"] = renderdata_out
    with open(os.path.join(REPO, "_scratch_c1.json"), "w", encoding="utf-8") as fh:
        json.dump(scratch, fh, indent=1)
    payload = "brief5_c1_renderdata.py" if renderdata_out else "brief5_c1_lodcolor.py"
    fired = time.time()
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", payload),
                        "--stage-name", "r2_%s" % out_name, "--timeout", "20"],
                       capture_output=True, text=True)
    print("  ue_exec", payload, out_name, "rc", r.returncode,
          (r.stdout or "")[-300:].replace("\n", " "))
    return fired, r.returncode


def poll_shot(out_name, fired, timeout=180):
    want = os.path.join(SHOTDIR, out_name + ".png")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(want) and os.path.getmtime(want) >= fired - 1:
            s1 = os.path.getsize(want)
            time.sleep(2)
            if s1 > 0 and os.path.getsize(want) == s1:
                dst = os.path.join(DERIVED, out_name + ".png")
                shutil.copy2(want, dst)
                print("  SHOT", out_name, os.path.getsize(want))
                return dst
        time.sleep(3)
    print("  NO PNG for", out_name)
    return None


def newest_content_mtime():
    newest = 0.0
    for dp, _dn, fns in os.walk(CONTENT):
        for fn in fns:
            try:
                mt = os.path.getmtime(os.path.join(dp, fn))
                newest = max(newest, mt)
            except OSError:
                pass
    return newest


def wait_quiescent(stable_s=20, timeout=180):
    t0 = time.time()
    last = newest_content_mtime()
    since = time.time()
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
             "--stage-name", "r2_close_census", "--timeout", "20"],
            capture_output=True, text=True)
        tail = (cen.stdout or "")
        print("CENSUS attempt %d rc %s %s" % (attempt + 1, cen.returncode,
                                              tail[-300:]))
        if cen.returncode == 0 and '"clean":' in tail and '"dirty_count":' in tail:
            clean = ('"dirty_count": 0' in tail) and ('"clean": true' in tail)
            return True, clean
        time.sleep(8)
    return False, False


def close_editor(pid):
    wait_quiescent()
    parsed, clean = live_census()
    restore = os.path.join(UEPROJ, "Saved", "Autosaves", "PackageRestoreData.json")
    if not (parsed and clean):
        print("REFUSE KILL: census not clean/parseable -- editor LEFT alive")
        return {"killed": False, "census_parsed": parsed, "census_clean": clean}
    if pid:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
    time.sleep(4)
    info = {"killed": True, "census_clean": clean,
            "still_alive": pid in editor_pids(),
            "package_restore_present": os.path.exists(restore)}
    print("CLOSE", info)
    return info


def main():
    os.makedirs(DERIVED, exist_ok=True)
    if editor_pids():
        print("REFUSE: UnrealEditor already running (rule 11)")
        return 3
    pid = launch(editor_pids())
    if pid is None or not wait_ready():
        return 1
    # the two band stills the classifier consumes (auto = the measured case),
    # plus the render-data corroboration written to r2_renderdata.json.
    f1, _ = run_shot(-1, 0.0, "r2_auto_ring")
    poll_shot("r2_auto_ring", f1)
    f2, _ = run_shot(-1, 300.0, "r2_auto_deep")
    poll_shot("r2_auto_deep", f2)
    run_shot(-1, 0.0, "r2_renderdata_unused", renderdata_out="r2_renderdata.json")
    close_editor(pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
