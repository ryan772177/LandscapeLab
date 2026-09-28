#!/usr/bin/env python3
"""Brief 5 REPAIR R1 driver -- APPLY the LOD hold so it PERSISTS, then PROVE it
in a COLD process. Host-side, two editor passes.

    a. mtime + sha256 of both live .uasset files BEFORE
    b-d. editor pass 1 (offscreen): brief5_r1_apply.py reads auto-compute, sets
         the target ScreenSizes, marks the package dirty, and force-saves.
    e. close editor 1 (R-EDITOR-CLOSE: quiescence wait -> census -> kill by the
       PID THIS driver launched). mtime + sha256 AFTER: BOTH .uasset must differ
       from (a). If either is unchanged -> STOP, verdict WRITE DID NOT LAND, no
       workaround.
    f. editor pass 2 (fresh process, cold): brief5_r1_cold.py reads
       get_lod_screen_sizes / tris / slots / auto-compute; must equal the targets
       within 1e-4, invariants intact, auto-compute False, and its editor PID
       must DIFFER from pass 1's.

Writes research/brief5/input/r1_persist.json (a-f) and, on success,
tree_lod_probe_cold.json (the cold probe check_recipe_lods reads).

REFUSES to launch unless zero UnrealEditor* processes are already running
(rule 11). Offscreen -> CloseMainWindow is False by design, so pass 1 and pass 2
both end on the kill path after the quiescence + census gate proves it is safe.
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

UASSETS = {
    "ConiferPine": os.path.join(
        CONTENT, "KiteDemo", "Environments", "Trees", "ScotsPineTall_01",
        "ScotsPineTall_01.uasset"),
    "SpruceSub": os.path.join(
        CONTENT, "PN_interactiveSpruceForest", "Meshes", "half", "high",
        "spruce_half_01.uasset"),
}


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def editor_pids():
    # BROAD match for the rule-11 REFUSE gate: any UnrealEditor* process counts.
    r = _ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def main_editor_pids():
    # EXACT match for the KILL target: only the UnrealEditor.exe game/editor
    # process, never a helper like UnrealEditor-Cmd (MINOR-3).
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
            "mtime": round(os.path.getmtime(path), 3),
            "size": os.path.getsize(path)}


def snapshot():
    return {k: sha_mtime(v) for k, v in UASSETS.items()}


def launch(pre):
    ps = ["powershell", "-NoProfile", "-File",
          os.path.join(SCRIPTS, "launch_editor.ps1"), "-Map", MAP]
    print("LAUNCH", MAP)
    subprocess.Popen(ps, cwd=REPO)
    t0 = time.time()
    while time.time() - t0 < 60:
        new = main_editor_pids() - pre   # the UnrealEditor.exe, not a helper
        if new:
            pid = sorted(new)[0]
            print("LAUNCHED PID", pid)
            return pid
        time.sleep(2)
    print("REFUSE: no new UnrealEditor.exe process within 60 s")
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
    """No kill during a write. After the payload's synchronous save returns, the
    editor may still drain DDC/shader writes; wait until the newest Content mtime
    stops advancing for stable_s (R-EDITOR-CLOSE quiet gate, adapted so our own
    fresh save does not read as 'write in flight' forever)."""
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
    # move any stale editor-output file to _trash/ FIRST so a failed run can
    # never be read as this run's evidence (BLOCKER-2). Rule 2: removals go to
    # _trash/, never an in-place delete (the invalidation and its undo both
    # survive). A move failure REFUSES the run (rc 99) rather than launching
    # blind.
    if os.path.exists(out_json):
        try:
            trash = os.path.join(REPO, "_trash")
            os.makedirs(trash, exist_ok=True)
            os.replace(out_json, os.path.join(
                trash, "%s.%d.%s" % (os.path.basename(out_json), os.getpid(),
                                     time.strftime("%Y%m%d_%H%M%S"))))
        except OSError as e:
            print("  REFUSE run: could not move stale %s to _trash: %s"
                  % (os.path.basename(out_json), e))
            return 99, "trash move failed: %s" % e
    r = subprocess.run([PY, os.path.join(SCRIPTS, "ue_exec.py"),
                        os.path.join(SCRIPTS, "payloads", payload),
                        "--stage-name", stage, "--timeout", "20",
                        "--set", "NONCE=%s" % nonce],
                       capture_output=True, text=True)
    out = (r.stdout or "")
    print("  ue_exec", payload, "rc", r.returncode)
    print(out[-1600:])
    return r.returncode, out


def read_verified(out_json, expected_nonce, rc):
    """Read the editor-output JSON only if the payload ran (rc==0), the file was
    freshly written this run, and its nonce matches. Returns (obj_or_None,
    reason)."""
    if rc != 0:
        return None, "payload rc=%s (nonzero)" % rc
    if not os.path.exists(out_json):
        return None, "no output file written (%s)" % os.path.basename(out_json)
    try:
        obj = json.load(open(out_json, encoding="utf-8"))
    except Exception as e:
        return None, "output file did not parse: %s" % e
    if str(obj.get("nonce")) != str(expected_nonce):
        return None, ("nonce mismatch: file %r != expected %r (STALE FILE)"
                      % (obj.get("nonce"), expected_nonce))
    return obj, "ok"


def live_census():
    """Run the LIVE dirty census, retrying for remote-discovery flakiness (the
    first R1 run got rc 3 'no verified node' mid-stream). Returns (parsed, clean,
    dirty_count, last_rc)."""
    parsed = clean = False
    dirty_count = None
    rc = None
    for attempt in range(3):
        cen = subprocess.run(
            [PY, os.path.join(SCRIPTS, "ue_exec.py"),
             os.path.join(SCRIPTS, "dirty_package_census_payload.txt"),
             "--stage-name", "r1_close_census", "--timeout", "20"],
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
    # R-EDITOR-CLOSE: quiescence (no kill during a write) -> LIVE dirty census
    # (what would be lost) -> kill by the launched PID (offscreen: no window to
    # CloseMainWindow, so the kill path is the plan; safety comes from the census
    # being clean + the tree being quiet + an empty PackageRestoreData).
    wait_quiescent()
    parsed, clean, dirty_count, cen_rc = live_census()
    restore = os.path.join(UEPROJ, "Saved", "Autosaves", "PackageRestoreData.json")
    info = {"launched_pid": pid,
            "package_restore_present": os.path.exists(restore),
            "census_rc": cen_rc,
            "census_parsed": parsed,
            "census_clean": clean,
            "census_dirty_count": dirty_count}

    # MAJOR-2: the census GATES the kill. Refuse to kill on a non-clean or
    # non-parsing census -- report and leave the editor for diagnosis (an
    # unsaved package or an unreadable census both mean "do not kill blind").
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


def _save(persist):
    with open(os.path.join(INPUT, "r1_persist.json"), "w",
              encoding="utf-8") as fh:
        json.dump(persist, fh, indent=1, default=str)


def new_nonce(tag):
    # host-side, no Workflow restrictions: a per-run token the editor payload
    # must echo back into its output file, so a stale file cannot be read as
    # this run's evidence (BLOCKER-2).
    return "%s_%d_%d" % (tag, int(time.time()), os.getpid())


def main():
    os.makedirs(INPUT, exist_ok=True)   # MINOR-2
    persist = {"_what": "Brief 5 REPAIR R1 -- apply the LOD hold with a persist "
               "protocol and prove it cold. mtime+sha256 before/after + cold "
               "readback in a distinct process.",
               "map": MAP,
               "_src_backup_caveat": "the _SRC pristine backups are ~1/5 the live "
               "size (duplicate_asset dropped regenerable bulk/DDC data); this "
               "write is float-only (ScreenSize), no geometry/Nanite touch, so the "
               "live .uasset size stays ~unchanged and the sha diff is the ScreenSize "
               "floats."}

    if editor_pids():
        print("REFUSE: UnrealEditor already running (rule 11)")
        persist["error"] = "editor already running at start"
        _save(persist)
        return 3

    # (a) BEFORE
    persist["before"] = snapshot()
    print("BEFORE", json.dumps(persist["before"], indent=1))

    # (b-d) APPLY pass
    apply_pid = launch(editor_pids())
    if apply_pid is None or not wait_ready():
        persist["error"] = "apply editor did not become ready"
        _save(persist)
        return 1
    persist["apply_pid"] = apply_pid
    apply_nonce = new_nonce("apply")
    persist["apply_nonce"] = apply_nonce
    rc, _ = run_payload("brief5_r1_apply.py", "brief5_r1_apply", apply_nonce,
                        os.path.join(INPUT, "r1_apply_editor.json"))
    persist["apply_rc"] = rc
    apply_obj, apply_reason = read_verified(
        os.path.join(INPUT, "r1_apply_editor.json"), apply_nonce, rc)
    persist["apply_editor"] = apply_obj if apply_obj is not None else \
        {"error": "apply output rejected: %s" % apply_reason}
    persist["apply_editor_verified"] = apply_obj is not None

    # (e) close + AFTER
    persist["apply_close"] = close_editor(apply_pid)
    persist["after"] = snapshot()
    print("AFTER", json.dumps(persist["after"], indent=1))

    changed = {}
    for k in UASSETS:
        b, a = persist["before"].get(k, {}), persist["after"].get(k, {})
        changed[k] = bool(b.get("present") and a.get("present")
                          and b.get("sha256") != a.get("sha256")
                          and a.get("mtime") != b.get("mtime"))
    persist["changed_on_disk"] = changed
    persist["all_changed"] = all(changed.values())

    if not persist["all_changed"]:
        persist["verdict"] = "WRITE DID NOT LAND"
        persist["_stop"] = ("At least one .uasset is unchanged (sha AND mtime). "
                            "Per R1(e): STOP, no workaround this session. See "
                            "apply_editor.saved_return / dirty_pre_save for what "
                            "the save logged.")
        _save(persist)
        print("VERDICT: WRITE DID NOT LAND -- stopping.")
        return 1

    # (f) COLD verify in a fresh process
    if editor_pids():
        persist["error"] = ("editor still alive before cold pass (apply close "
                            "may have REFUSED the kill on a non-clean census)")
        _save(persist)
        print("ABORT:", persist["error"])
        return 1
    cold_pid = launch(editor_pids())
    if cold_pid is None or not wait_ready():
        persist["error"] = "cold editor did not become ready"
        _save(persist)
        return 1
    persist["cold_pid"] = cold_pid
    cold_nonce = new_nonce("cold")
    persist["cold_nonce"] = cold_nonce
    rc2, _ = run_payload("brief5_r1_cold.py", "brief5_r1_cold", cold_nonce,
                         os.path.join(INPUT, "r1_cold_editor.json"))
    persist["cold_rc"] = rc2
    cold, cold_reason = read_verified(
        os.path.join(INPUT, "r1_cold_editor.json"), cold_nonce, rc2)
    persist["cold_verified"] = cold is not None
    persist["cold_reject_reason"] = None if cold is not None else cold_reason
    persist["cold_editor"] = cold if cold is not None else \
        {"error": "cold output rejected: %s" % cold_reason}
    persist["cold_close"] = close_editor(cold_pid)

    # a rejected cold read is NOT evidence -- fail closed (BLOCKER-2, MAJOR-1).
    if cold is None:
        persist["PASS"] = False
        persist["verdict"] = "COLD READ REJECTED (%s)" % cold_reason
        _save(persist)
        print("VERDICT:", persist["verdict"])
        return 1

    editor_pid_in_payload = cold.get("editor_pid")
    persist["cold_process_distinct"] = bool(
        editor_pid_in_payload is not None
        and editor_pid_in_payload != apply_pid
        and cold_pid != apply_pid)
    persist["cold_all_match"] = bool(cold.get("all_match"))
    persist["cold_invariants_ok"] = bool(cold.get("all_invariants_ok"))
    persist["cold_auto_off"] = bool(cold.get("all_auto_off"))
    # PASS gates on: both assets changed on disk, cold values match, invariants
    # hold, auto-compute OFF cold (MAJOR-3), and the cold read came from a
    # distinct process.
    persist["PASS"] = bool(persist["all_changed"] and persist["cold_all_match"]
                           and persist["cold_invariants_ok"]
                           and persist["cold_auto_off"]
                           and persist["cold_process_distinct"])
    persist["verdict"] = "HOLD PERSISTED" if persist["PASS"] else "COLD CHECK FAILED"
    _save(persist)

    # write the cold probe check_recipe_lods reads -- ONLY on a genuine PASS
    # (distinct process + all cold checks green).
    if persist["PASS"] and cold.get("meshes"):
        probe = {"_what": "Brief 5 R1 COLD LOD probe -- get_lod_screen_sizes read "
                 "in a FRESH editor process (PID %s), distinct from the apply "
                 "process (PID %s). check_recipe_lods requires cold_readback=True."
                 % (editor_pid_in_payload, apply_pid),
                 "cold_readback": True,
                 "distinct_from_apply": persist["cold_process_distinct"],
                 "cold_editor_pid": editor_pid_in_payload,
                 "apply_pid": apply_pid,
                 "nonce": cold_nonce,
                 "meshes": [{"species": m["species"],
                             "screen_sizes": m.get("screen_sizes")}
                            for m in cold["meshes"]]}
        with open(os.path.join(INPUT, "tree_lod_probe_cold.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(probe, fh, indent=1, default=str)
        print("wrote tree_lod_probe_cold.json")

    print("VERDICT:", persist["verdict"], "| PASS:", persist["PASS"])
    return 0 if persist["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
