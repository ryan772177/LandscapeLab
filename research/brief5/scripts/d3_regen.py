#!/usr/bin/env python
"""Brief 5 D3 -- live foliage regen at the ruled density + VRAM viability gate.

Ryan ruled (re-ASK #1): Go D3 at 812,258 placed instances. This driver runs the
regen and gates viability on the DEVICE_HUNG VRAM ceiling, with a PROVEN git
revert on any failure. Station capture is SIMPLIFIED per Ryan's ruling: VRAM per
station via nvidia-smi in a -game process (no editor-side WP instrumentation);
the -game load-to-settle wall time is the cell-load proxy.

SEQUENCE (each phase logged; abort -> revert + proof):
  0  pre-flight: 0 editors (rule 11); FENCE_TAG exists AND the worktree world ==
     the tag for every WORLD_PATH (so revert-to-tag == revert-to-pre-D3, M4);
     resource_guard PASS (rule 5) or refuse; record pre-D3 shas.
  1  launch editor OFFSCREEN /Game/Alpine8K, wait_ready.
  2  place_foliage --place --ruled-count 812258 (recipe-driven: zone map +
     ceiling from the recipe; orphan sweep + add_instances). Hard timeout.
  3  editor VRAM poll (nvidia-smi). UNMEASURED or > ceiling -> abort BEFORE save.
  4  save_level --save.
  5  close editor: kill every launched PID; PackageRestoreData census.
  6  -game at forest_floor / open_max / plaza (perf_standalone). Parse its OWN
     "OVER ABORT CEILING" verdict; over -> abort. UNMEASURED -> warn, not pass.
  7  verdict. PASS -> world left changed (caller commits). ABORT -> revert.

REVERT (the whole point, and audited): the world is git-tracked, but a save ADDS
new OFPA/EO packages for newly-populated WP cells that `git checkout <tag>` cannot
delete. So revert (a) MOVES every untracked addition under the external-actor/
object dirs to _trash/ (rule 2 -- never `git clean -fd`), (b) `git checkout
<tag> -- WORLD_PATHS`, (c) PROVES restoration with `git diff --quiet <tag>` AND
empty `git status --porcelain` over WORLD_PATHS (a directory file-count is not a
proof -- audit B3).
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
BR = os.path.join(REPO, "research", "brief5")
PY = sys.executable
FENCE_TAG = "pre-density-daylight"

# Single source for the DEVICE_HUNG ceiling (NN24): read perf_standalone's own
# constant so phase 3 and the -game gate cannot drift.
sys.path.insert(0, SCRIPTS)
try:
    from perf_standalone import VRAM_ABORT_MIB
except Exception as _e:  # fallback keeps the driver runnable; make it visible
    VRAM_ABORT_MIB = 13312
    print("[D3] WARN: could not import VRAM_ABORT_MIB from perf_standalone "
          "(%r); using literal %d" % (_e, VRAM_ABORT_MIB), flush=True)

# Every path the D3 place + save may write. The save allow-list
# (save_level.py) authorises the external-actor AND external-OBJECT dirs for the
# level, plus the Foliage FT assets (the placement payload dirties every FT it
# touches). All must be revertable or a dirtied file survives (audit B2).
WORLD_PATHS = [
    "foliage/alpine_8k_Conifer.json",
    "foliage/alpine_8k_ConiferPine.json",
    "foliage/alpine_8k_SpruceSub.json",
    "foliage/alpine_8k_SpruceSapling.json",
    "LandscapeLab/Content/Alpine8K.umap",
    "LandscapeLab/Content/__ExternalActors__/Alpine8K",
    "LandscapeLab/Content/__ExternalObjects__/Alpine8K",
    "LandscapeLab/Content/Foliage",
]
# Dirs whose UNTRACKED additions a checkout cannot remove (audit B1).
ADD_DIRS = [
    "LandscapeLab/Content/__ExternalActors__/Alpine8K",
    "LandscapeLab/Content/__ExternalObjects__/Alpine8K",
    "LandscapeLab/Content/Foliage",
]
STATIONS = [
    ("forest_floor", os.path.join(BR, "input", "forest_station.json")),
    ("open_max", os.path.join(BR, "input", "open_max_station.json")),
    ("plaza", None),   # ratified in perf_budgets.json -> --only plaza
]
LAUNCHED_PIDS = set()


def log(msg):
    print("[D3] " + msg, flush=True)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True)


def editor_pids():
    r = ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | "
           "ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def vram_used_mib():
    """(MiB, None) or (None, reason). rule 13: a reading that could not be taken
    reports null WITH the reason, never 0."""
    r = ps("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")
    if r.returncode != 0:
        return None, "nvidia-smi rc %d: %s" % (r.returncode,
                                               (r.stderr or "").strip()[:120])
    vals = [int(x) for x in (r.stdout or "").split() if x.strip().isdigit()]
    if not vals:
        return None, "nvidia-smi returned no numeric memory.used"
    return max(vals), None


def vram_peak(samples=6, gap=1.5):
    """(peak_mib, n_ok) -- n_ok is the count of successful samples so a measured
    zero is distinct from no-sample (rule 13, audit m12)."""
    peak, n_ok, reasons = 0, 0, []
    for _ in range(samples):
        v, why = vram_used_mib()
        if v is None:
            reasons.append(why)
        else:
            n_ok += 1
            peak = max(peak, v)
        time.sleep(gap)
    return (peak if n_ok else None), n_ok, "; ".join(sorted(set(reasons)))


def file_shas(paths):
    out = {}
    for p in paths:
        ap = os.path.join(REPO, p)
        if os.path.isdir(ap):
            r = git("ls-files", "-s", p)
            out[p] = "tree:%d-index-entries" % len((r.stdout or "").splitlines())
        else:
            r = git("hash-object", p)
            out[p] = (r.stdout or "").strip() or "MISSING"
    return out


def world_matches_tag():
    """(ok, detail): worktree WORLD_PATHS identical to FENCE_TAG and clean.
    This is the real proof -- git diff reads content, not the index (audit B3)."""
    d = git("diff", "--quiet", FENCE_TAG, "--", *WORLD_PATHS)
    st = git("status", "--porcelain", "--", *WORLD_PATHS)
    clean = (st.stdout or "").strip() == ""
    return (d.returncode == 0 and clean), {
        "diff_vs_tag_rc": d.returncode, "porcelain": (st.stdout or "").strip()[:400]}


def kill_all_editors(only_launched=True):
    targets = LAUNCHED_PIDS if only_launched else editor_pids()
    for pid in sorted(targets):
        ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
        log("killed PID %d" % pid)
    time.sleep(4)


def revert(reason):
    log("ABORT: %s" % reason)
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    trash = os.path.join(REPO, "_trash", "d3_revert_" + ts)
    # (a) move untracked additions the checkout cannot delete (rule 2)
    moved = 0
    for d in ADD_DIRS:
        r = git("ls-files", "--others", "--exclude-standard", "--", d)
        for rel in (r.stdout or "").splitlines():
            rel = rel.strip()
            if not rel:
                continue
            src = os.path.join(REPO, rel)
            dst = os.path.join(trash, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.move(src, dst)
                moved += 1
            except OSError as exc:
                log("  WARN could not move %s: %s" % (rel, exc))
    log("  moved %d untracked additions -> %s" % (moved,
        os.path.relpath(trash, REPO) if moved else "(none)"))
    # (b) restore tracked files to the tag
    co = git("checkout", FENCE_TAG, "--", *WORLD_PATHS)
    log("  git checkout %s rc %d %s" % (FENCE_TAG, co.returncode,
                                        (co.stderr or "").strip()[:200]))
    # (c) PROVE restoration by content, not by count
    ok, detail = world_matches_tag()
    log("  restoration proven (diff==tag & clean): %s  %s" % (ok, detail))
    return ok


def run(cmd, timeout, phase):
    log("run(%s): %s" % (phase, " ".join(cmd[-5:])))
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        log("TIMEOUT in %s after %ss" % (phase, timeout))
        return None, "", "timeout"
    dt = round(time.time() - t0, 1)
    log("  rc %d (%ss) %s" % (r.returncode, dt,
                              (r.stdout or "")[-320:].replace("\n", " ")))
    return r.returncode, (r.stdout or ""), (r.stderr or "")


_VERDICT_PATH = os.path.join(BR, "derived", "d3_verdict.json")


def _save(v):
    os.makedirs(os.path.dirname(_VERDICT_PATH), exist_ok=True)
    json.dump(v, open(_VERDICT_PATH, "w", encoding="utf-8"), indent=1)
    log("verdict -> %s" % os.path.relpath(_VERDICT_PATH, REPO))


def _abort(v, reason, code=3):
    # kill ANY UnrealEditor* (not just launched): pre-flight proved zero existed,
    # so every editor alive now is ours, and a stray helper must not hold package
    # locks while revert() moves/checks out (audit MINOR-1).
    kill_all_editors(only_launched=False)
    v["revert_ok"] = revert(reason)
    v.update(aborted=True, reason=reason)
    v["post_shas"] = file_shas(WORLD_PATHS)
    _save(v)
    return code


def main():
    global FENCE_TAG, _VERDICT_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--place-timeout", type=int, default=2400)
    ap.add_argument("--ready-timeout", type=int, default=420)
    ap.add_argument("--allow-unmeasured-vram", action="store_true",
                    help="proceed past a station whose VRAM nvidia-smi could not "
                         "sample (default: an unmeasured DEVICE_HUNG gate aborts)")
    ap.add_argument("--dry", action="store_true",
                    help="pre-flight only; do not touch the editor")
    # Brief 7 Phase 3 (2026-09-27): the driver is re-used for the re-capped
    # density regen. The fence tag, the ruled count and the verdict path were
    # literals for D3; they are parameters now so a second regen cannot
    # silently compare itself against the D3 fence or overwrite D3's verdict.
    ap.add_argument("--fence-tag", default=FENCE_TAG,
                    help="git tag the worktree world must EQUAL before the run "
                         "(revert target). Default: the D3 fence %s" % FENCE_TAG)
    ap.add_argument("--ruled-count", type=int, default=812258,
                    help="the ruled placed-instance count handed to place_foliage "
                         "--ruled-count (D3: 812258)")
    ap.add_argument("--verdict", default=os.path.join(BR, "derived", "d3_verdict.json"),
                    help="where to write the verdict JSON")
    a = ap.parse_args()
    FENCE_TAG = a.fence_tag
    _VERDICT_PATH = a.verdict

    v = {"phases": {}, "vram": {}, "aborted": False, "reason": None,
         "ruled_count": a.ruled_count, "vram_ceiling_mib": VRAM_ABORT_MIB,
         "fence_tag": FENCE_TAG}
    v["pre_shas"] = file_shas(WORLD_PATHS)
    log("pre-D3 world shas: " + json.dumps(v["pre_shas"]))

    # ---- phase 0: pre-flight ------------------------------------------
    pids = editor_pids()
    if pids:
        log("REFUSE: %d editor(s) already running %s (rule 11)"
            % (len(pids), sorted(pids)))
        _save(v)
        return 2
    if git("rev-parse", "-q", "--verify", FENCE_TAG + "^{commit}").returncode != 0:
        log("REFUSE: fence tag %s does not resolve" % FENCE_TAG)
        _save(v)
        return 2
    ok, detail = world_matches_tag()
    if not ok:
        log("REFUSE: worktree world != %s (M4): revert-to-tag would not be "
            "revert-to-pre-D3. %s" % (FENCE_TAG, detail))
        _save(v)
        return 2
    log("pre-flight: worktree world == %s, clean" % FENCE_TAG)
    rg = subprocess.run([PY, os.path.join(SCRIPTS, "resource_guard.py"),
                         "--label", "D3 foliage regen"], cwd=REPO,
                        capture_output=True, text=True)
    log("resource_guard rc %d %s" % (rg.returncode,
                                     (rg.stdout or "").strip()[-200:]))
    if rg.returncode != 0:
        log("REFUSE: resource_guard did not pass (rule 5)")
        _save(v)
        return 2
    if a.dry:
        log("--dry: pre-flight PASS; stopping")
        _save(v)
        return 0

    try:
        # ---- phase 1: launch ------------------------------------------
        pre_pids = editor_pids()
        subprocess.Popen(["powershell", "-NoProfile", "-File",
                          os.path.join(SCRIPTS, "launch_editor.ps1"),
                          "-Map", "/Game/Alpine8K"], cwd=REPO)
        t0 = time.time()
        while time.time() - t0 < 90:
            LAUNCHED_PIDS.update(editor_pids() - pre_pids)
            if LAUNCHED_PIDS:
                break
            time.sleep(2)
        if not LAUNCHED_PIDS:
            return _abort(v, "editor did not appear within 90 s")
        log("launched PIDs %s; waiting for ready" % sorted(LAUNCHED_PIDS))
        ready, t0 = False, time.time()
        while time.time() - t0 < a.ready_timeout:
            LAUNCHED_PIDS.update(editor_pids() - pre_pids)
            if subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")],
                              cwd=REPO, capture_output=True, text=True).returncode == 0:
                ready = True
                break
            time.sleep(6)
        if not ready:
            return _abort(v, "editor not ready within %ss" % a.ready_timeout)
        log("editor ready after %.0fs" % (time.time() - t0))

        # ---- phase 2: place -------------------------------------------
        rc, _o, _e = run([PY, os.path.join(SCRIPTS, "place_foliage.py"),
                          "--recipe", os.path.join(REPO, "recipes", "alpine_8k.json"),
                          "--place", "--timeout", "25",
                          "--ruled-count", str(a.ruled_count)],
                         a.place_timeout, "place")
        v["phases"]["place"] = rc
        if rc != 0:
            return _abort(v, "place_foliage --place rc=%s" % rc)

        # ---- phase 3: editor VRAM gate (before save) ------------------
        peak, n_ok, why = vram_peak()
        v["vram"]["editor_after_place"] = {"peak_mib": peak, "samples_ok": n_ok,
                                           "reason": why}
        log("editor VRAM after place: %s MiB (%d samples, ceiling %d) %s"
            % (peak, n_ok, VRAM_ABORT_MIB, why))
        if peak is None and not a.allow_unmeasured_vram:
            return _abort(v, "editor VRAM UNMEASURED before save (%s); rule 13" % why)
        if peak is not None and peak > VRAM_ABORT_MIB:
            return _abort(v, "editor VRAM %d > %d MiB" % (peak, VRAM_ABORT_MIB))

        # ---- phase 4: save --------------------------------------------
        # WAIT FOR THE EDITOR TO ANSWER BEFORE SAVING (Phase 3 attempt 2,
        # 2026-09-27): right after add_instances of 797,500 rows the game
        # thread is busy and remote discovery can go unanswered for longer
        # than save_level's 6 s default -- it refused with rule 7 ("no editor
        # nodes answered discovery", rc 3) and this driver reverted a GOOD
        # placement. docs/environment.md: use --timeout 25 on this machine.
        _t = time.time()
        _answered = False
        while time.time() - _t < a.ready_timeout:
            if subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py")],
                              cwd=REPO, capture_output=True, text=True).returncode == 0:
                _answered = True
                break
            time.sleep(6)
        log("editor answering before save: %s (%.0fs)" % (_answered, time.time() - _t))
        if not _answered:
            return _abort(v, "editor did not answer discovery before save "
                             "within %ss" % a.ready_timeout)
        rc, _o, _e = run([PY, os.path.join(SCRIPTS, "save_level.py"),
                          "--recipe", os.path.join(REPO, "recipes", "alpine_8k.json"),
                          "--save", "--timeout", "25"], 900, "save")
        v["phases"]["save"] = rc
        if rc != 0:
            return _abort(v, "save_level --save rc=%s" % rc)

        # ---- phase 5: close editor ------------------------------------
        kill_all_editors(only_launched=False)   # any UnrealEditor* now
        _t = time.time()
        while editor_pids() and time.time() - _t < 60:
            time.sleep(3)
        restore = os.path.join(REPO, "LandscapeLab", "Saved", "Autosaves",
                               "PackageRestoreData.json")
        v["package_restore_present_after_close"] = os.path.exists(restore)
        log("editors after close: %s; PackageRestoreData: %s"
            % (sorted(editor_pids()), v["package_restore_present_after_close"]))

        # ---- phase 6: -game station VRAM (editor gone) ----------------
        # INSIDE the try (M5): the -game hours are the longest span; an
        # exception or Ctrl-C here must still kill + revert + save a verdict.
        import re
        measured = 0
        for name, sj in STATIONS:
            cmd = [PY, os.path.join(SCRIPTS, "perf_standalone.py"),
                   "--noxgecontroller", "--tag", "d3_" + name]
            cmd += (["--station-json", sj, "--station-name", name] if sj
                    else ["--only", name])
            rc, out, _e = run(cmd, 1800, "-game " + name)
            st = {"rc": rc, "peak_mib": None, "over_ceiling": None}
            for line in (out or "").splitlines():
                low = line.lower()
                if "vram peak across stations" in low:
                    st["vram_line"] = line.strip()[:180]
                    m = re.search(r"(\d+)\s*MiB", line)
                    if m:
                        st["peak_mib"] = int(m.group(1))
                    st["over_ceiling"] = "OVER ABORT CEILING" in line
                elif "vram: no nvidia-smi sample" in low:
                    st["vram_line"] = line.strip()[:180]
                    st["over_ceiling"] = None
            v["vram"]["game_" + name] = st
            log("  %s VRAM peak %s MiB over_ceiling=%s"
                % (name, st["peak_mib"], st["over_ceiling"]))
            if rc != 0:
                return _abort(v, "-game %s rc=%s" % (name, rc))
            if st["over_ceiling"] is True:
                return _abort(v, "-game %s VRAM %s > %d" % (name, st["peak_mib"],
                                                            VRAM_ABORT_MIB))
            if st["over_ceiling"] is None:
                log("  WARNING: %s VRAM UNMEASURED; ceiling not proven here" % name)
            else:
                measured += 1

        v["aborted"] = False
        v["stations_vram_measured"] = "%d/%d" % (measured, len(STATIONS))
        v["post_shas"] = file_shas(WORLD_PATHS)
        log("D3 PASS: regen complete, editor VRAM %s MiB, -game under ceiling at "
            "%d/%d stations (%d unmeasured -- see verdict)."
            % (v["vram"]["editor_after_place"]["peak_mib"], measured,
               len(STATIONS), len(STATIONS) - measured))
        _save(v)
        return 0
    except BaseException as exc:      # M5: covers phases 1-6 (incl. the -game hours)
        log("EXCEPTION: %r" % exc)
        _abort(v, "exception: %r" % exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
