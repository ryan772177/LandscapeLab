#!/usr/bin/env python3
"""Brief 5 D1a driver -- BUILD the T4 rung chains on scratch duplicates and prove
them COLD, with a shipped-mesh byte-identity guarantee. Host-side, two editor
passes, modeled on research/brief5/scripts/r_apply.py (the proven R-EDITOR-CLOSE
+ zero-editor-gate + distinct-PID-cold pattern).

    a. sha256+mtime of the two SHIPPED meshes and their _SRC dupes BEFORE.
    b. editor pass 1 (offscreen): brief5_t4_build.py duplicates each mesh to
       /Game/Scratch/T4/<species>_gate, builds the rungs from LOD G, assembles the
       chain preserving the authored card, sets screen sizes, saves the scratch mesh.
    c. close pass 1 (R-EDITOR-CLOSE: quiescence -> live dirty census -> kill by the
       launched PID). sha256 of the shipped meshes + _SRC AFTER: ALL must be
       UNCHANGED -- if any shipped/_SRC mesh changed, the fence broke: STOP.
    d. editor pass 2 (fresh, cold): brief5_t4_cold.py reads back each scratch gate
       chain (count, per-LOD tris, screen sizes, auto-compute) in a DISTINCT PID;
       must match the target chain.

Writes research/brief5/input/t4_build.json. Does NOT write t4_scratch_gates.json
(that is the render-gate phase's output: coverage ratio + silhouette IoU per rung).

REFUSES to launch unless zero UnrealEditor* processes are running (rule 11).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
UEPROJ = os.path.join(REPO, "LandscapeLab")
CONTENT = os.path.join(UEPROJ, "Content")
INPUT = os.path.join(REPO, "research", "brief5", "input")
PY = sys.executable
MAP = "/Game/Alpine8K"

# shipped meshes + their pristine _SRC dupes -- all must stay byte-identical (fence)
GUARDED = {
    "ConiferPine": os.path.join(CONTENT, "KiteDemo", "Environments", "Trees",
                                "ScotsPineTall_01", "ScotsPineTall_01.uasset"),
    "ConiferPine_SRC": os.path.join(CONTENT, "KiteDemo", "Environments", "Trees",
                                    "ScotsPineTall_01", "ScotsPineTall_01_SRC.uasset"),
    "SpruceSub": os.path.join(CONTENT, "PN_interactiveSpruceForest", "Meshes",
                              "half", "high", "spruce_half_01.uasset"),
    "SpruceSub_SRC": os.path.join(CONTENT, "PN_interactiveSpruceForest", "Meshes",
                                  "half", "high", "spruce_half_01_SRC.uasset"),
}


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


def sha_mtime(path):
    if not os.path.exists(path):
        return {"present": False}
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"present": True, "sha256": h.hexdigest(),
            "mtime": round(os.path.getmtime(path), 3), "size": os.path.getsize(path)}


def snapshot():
    return {k: sha_mtime(v) for k, v in GUARDED.items()}


def launch(pre):
    ps = ["powershell", "-NoProfile", "-File",
          os.path.join(SCRIPTS, "launch_editor.ps1"), "-Map", MAP]
    print("LAUNCH", MAP)
    subprocess.Popen(ps, cwd=REPO)
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
        r = subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("EDITOR READY", round(time.time() - t0, 1), "s")
            return True
        time.sleep(6)
    print("EDITOR NOT READY within", timeout, "s")
    return False


def newest_content_mtime():
    newest = 0.0
    for dp, _dn, fns in os.walk(CONTENT):
        for fn in fns:
            try:
                mt = os.path.getmtime(os.path.join(dp, fn))
                if mt > newest:
                    newest = mt
            except OSError:
                pass
    return newest


def wait_quiescent(stable_s=25, timeout=240):
    t0 = time.time()
    last = newest_content_mtime()
    stable_since = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        cur = newest_content_mtime()
        if cur > last:
            last = cur
            stable_since = time.time()
        elif time.time() - stable_since >= stable_s:
            print("QUIESCENT: Content tree stable %ds" % stable_s)
            return True
    print("NOT QUIESCENT within", timeout, "s (proceeding to census anyway)")
    return False


def run_payload(payload, stage, nonce, out_json):
    if os.path.exists(out_json):
        try:
            trash = os.path.join(REPO, "_trash")
            os.makedirs(trash, exist_ok=True)
            os.replace(out_json, os.path.join(
                trash, "%s.%d.%s" % (os.path.basename(out_json), os.getpid(),
                                     time.strftime("%Y%m%d_%H%M%S"))))
        except OSError as e:
            print("  REFUSE run: could not move stale %s: %s"
                  % (os.path.basename(out_json), e))
            return 99, "trash move failed: %s" % e
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", payload),
                        "--stage-name", stage, "--timeout", "60",
                        "--set", "NONCE=%s" % nonce],
                       capture_output=True, text=True)
    out = (r.stdout or "")
    print("  ue_exec", payload, "rc", r.returncode)
    print(out[-1800:])
    return r.returncode, out


def read_verified(out_json, expected_nonce, rc):
    if rc != 0:
        return None, "payload rc=%s (nonzero)" % rc
    if not os.path.exists(out_json):
        return None, "no output file written (%s)" % os.path.basename(out_json)
    try:
        obj = json.load(open(out_json, encoding="utf-8"))
    except Exception as e:
        return None, "output file did not parse: %s" % e
    if str(obj.get("nonce")) != str(expected_nonce):
        return None, ("nonce mismatch: file %r != expected %r (STALE)"
                      % (obj.get("nonce"), expected_nonce))
    return obj, "ok"


def live_census():
    parsed = clean = False
    dirty_count = None
    rc = None
    for attempt in range(3):
        cen = subprocess.run(
            [PY, os.path.join(SCRIPTS, "ue_exec.py"),
             os.path.join(SCRIPTS, "dirty_package_census_payload.txt"),
             "--stage-name", "t4_close_census", "--timeout", "20"],
            capture_output=True, text=True)
        tail = (cen.stdout or "")
        rc = cen.returncode
        print("CENSUS attempt %d rc %s %s" % (attempt + 1, rc, tail[-400:]))
        parsed = (rc == 0 and '"clean":' in tail and '"dirty_count":' in tail)
        if parsed:
            clean = ('"dirty_count": 0' in tail) and ('"clean": true' in tail)
            m = re.search(r'"dirty_count":\s*(\d+)', tail)
            dirty_count = int(m.group(1)) if m else None
            return parsed, clean, dirty_count, rc
        time.sleep(8)
    return parsed, clean, dirty_count, rc


def close_editor(pid):
    wait_quiescent()
    parsed, clean, dirty_count, cen_rc = live_census()
    restore = os.path.join(UEPROJ, "Saved", "Autosaves", "PackageRestoreData.json")
    info = {"launched_pid": pid, "package_restore_present": os.path.exists(restore),
            "census_rc": cen_rc, "census_parsed": parsed, "census_clean": clean,
            "census_dirty_count": dirty_count}
    if not clean:
        info["killed"] = False
        info["_REFUSE_KILL"] = ("census not clean/parseable -- editor LEFT alive "
                                "for diagnosis (R-EDITOR-CLOSE step 4).")
        print("CLOSE (REFUSE KILL)", json.dumps(info, default=str))
        return info
    if pid:
        _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
    time.sleep(4)
    left = editor_pids()
    info["killed"] = True
    info["still_alive"] = pid in left
    info["editors_now"] = sorted(left)
    info["package_restore_present_post_kill"] = os.path.exists(restore)
    print("CLOSE", json.dumps(info, default=str))
    return info


def _save(rec):
    with open(os.path.join(INPUT, "t4_build.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, default=str)


def new_nonce(tag):
    return "%s_%d_%d" % (tag, int(time.time()), os.getpid())


def main():
    os.makedirs(INPUT, exist_ok=True)
    rec = {"_what": "Brief 5 D1a -- build the T4 rung chains on scratch duplicates, "
           "prove them cold, and prove the shipped meshes stayed byte-identical.",
           "map": MAP}

    if editor_pids():
        print("REFUSE: UnrealEditor already running (rule 11)")
        rec["error"] = "editor already running at start"
        _save(rec)
        return 3

    rec["before"] = snapshot()
    print("BEFORE", json.dumps(rec["before"], indent=1))

    # BUILD pass
    build_pid = launch(editor_pids())
    if build_pid is None or not wait_ready():
        rec["error"] = "build editor did not become ready"
        _save(rec)
        return 1
    rec["build_pid"] = build_pid
    bnonce = new_nonce("build")
    rec["build_nonce"] = bnonce
    rc, _ = run_payload("brief5_t4_build.py", "brief5_t4_build", bnonce,
                        os.path.join(INPUT, "t4_build_editor.json"))
    rec["build_rc"] = rc
    bobj, breason = read_verified(os.path.join(INPUT, "t4_build_editor.json"), bnonce, rc)
    rec["build_editor"] = bobj if bobj is not None else \
        {"error": "build output rejected: %s" % breason}
    rec["build_verified"] = bobj is not None

    rec["build_close"] = close_editor(build_pid)
    rec["after"] = snapshot()
    print("AFTER", json.dumps(rec["after"], indent=1))

    # FENCE PROOF: every guarded (shipped + _SRC) mesh must be byte-identical.
    unchanged = {}
    for k in GUARDED:
        b, a = rec["before"].get(k, {}), rec["after"].get(k, {})
        unchanged[k] = bool(b.get("present") and a.get("present")
                            and b.get("sha256") == a.get("sha256"))
    rec["shipped_unchanged"] = unchanged
    rec["shipped_byte_identical"] = all(unchanged.values())
    if not rec["shipped_byte_identical"]:
        rec["verdict"] = "FENCE BROKE -- a shipped/_SRC mesh changed"
        _save(rec)
        print("VERDICT: FENCE BROKE -- stopping.")
        return 1

    # COLD verify in a fresh process
    if editor_pids():
        rec["error"] = "editor still alive before cold pass"
        _save(rec)
        return 1
    cold_pid = launch(editor_pids())
    if cold_pid is None or not wait_ready():
        rec["error"] = "cold editor did not become ready"
        _save(rec)
        return 1
    rec["cold_pid"] = cold_pid
    cnonce = new_nonce("cold")
    rec["cold_nonce"] = cnonce
    rc2, _ = run_payload("brief5_t4_cold.py", "brief5_t4_cold", cnonce,
                         os.path.join(INPUT, "t4_cold_editor.json"))
    rec["cold_rc"] = rc2
    cold, creason = read_verified(os.path.join(INPUT, "t4_cold_editor.json"), cnonce, rc2)
    rec["cold_verified"] = cold is not None
    rec["cold_reject_reason"] = None if cold is not None else creason
    rec["cold_editor"] = cold if cold is not None else \
        {"error": "cold output rejected: %s" % creason}
    rec["cold_close"] = close_editor(cold_pid)

    if cold is None:
        rec["PASS"] = False
        rec["verdict"] = "COLD READ REJECTED (%s)" % creason
        _save(rec)
        print("VERDICT:", rec["verdict"])
        return 1

    cold_distinct = bool(cold.get("editor_pid") is not None
                         and cold.get("editor_pid") != build_pid
                         and cold_pid != build_pid)
    rec["cold_process_distinct"] = cold_distinct
    rec["cold_all_match"] = bool(cold.get("all_match"))
    rec["PASS"] = bool(rec["shipped_byte_identical"] and rec["cold_all_match"]
                       and cold_distinct and rec.get("build_verified")
                       and (bobj or {}).get("ok"))
    rec["verdict"] = ("GATE MESHES BUILT + COLD-VERIFIED, SHIPPED BYTE-IDENTICAL"
                      if rec["PASS"] else "BUILD/COLD CHECK FAILED")
    _save(rec)
    print("VERDICT:", rec["verdict"], "| PASS:", rec["PASS"])
    return 0 if rec["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
