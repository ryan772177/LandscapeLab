#!/usr/bin/env python
"""Brief 7 Phase 3b -- runtime ground clutter through the grass system, end to end.

The world's LEVEL is never saved by this driver: a grass species lives in
`GT_alpine_8k_<name>` assets + the LandscapeGrassOutput of M_Alpine8K, both of
which the material builder saves itself. Revert = `git checkout <fence> --`
those tracked assets (+ move any NEW GT package to _trash/).

SEQUENCE (each phase logged; the verdict JSON is rewritten after every phase):
  0  pre-flight: zero editors (rule 11); fence tag exists; resource_guard;
     shas of the tracked material + grass-type assets recorded.
  1  launch editor WINDOWED /Game/Alpine8K (stills need a window, LESSONS
     2026-09-25), wait for bootstrap (rule 7 node match).
  2  level check payload: must be Alpine8K (rule 11). Grass output inputs
     BEFORE the rebuild recorded.
  3  measure_clutter_meshes: the new vendor meshes get engine_derived rows
     (pivot contract applied live). Any refusal -> abort BEFORE the rebuild.
  4  offline recipe validation: exactly the two pre-existing 'lighting' dot-py
     INVALIDs may remain (measured on main 2026-09-27); anything else aborts.
  5  make_landscape_material.py --assign (the rebuild that writes the grass
     types and re-wires the GrassOutput). rc != 0 -> revert + abort.
  6  read-back (rule 12, second instrument): read_grass_type.py per species,
     variety counts asserted; the three pre-existing species re-read unchanged.
  7  grass.FlushCache; Look profile; camera at the forest_floor station; dwell;
     grass.DumpGrassData -bygrasstype -> LandscapeLab.log lines recorded.
  8  stills (Look profile, ground-traced camera, settle): forest_floor,
     forest_floor_ground (pitch -25), plaza, treeline. Shot ONLY if the Look
     profile read back ok (audit F3).
  9  bench profile restore READ BACK (the setprofile payload raises if a bench
     value did not take).
 10  dirty census; Content quiet >= 120 s; kill launched PIDs; PackageRestoreData.
 11  -game perf at forest_floor / open_max / plaza (perf_standalone, recorded
     not gated -- R-AESTHETIC-1): GPU p90 + VRAM peak per station.
 12  verdict.

Harness note (LESSONS 2026-09-21/22): run this DETACHED (PowerShell
Start-Process with stdout to research/brief7/p3b/run.log). The editor is
launched detached from here and driven with short ue_exec calls; the long
host calls (rebuild, shoot, -game) are subprocesses of this detached driver.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
PY = sys.executable
OUT = os.path.join(REPO, "research", "brief7", "p3b")
STILLS = os.path.join(REPO, "research", "brief7", "stills", "p3b_clutter")
LOG = os.path.join(REPO, "LandscapeLab", "Saved", "Logs", "LandscapeLab.log")
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
BR5 = os.path.join(REPO, "research", "brief5")

NEW_SPECIES = {"MeadowFar": 1, "ForestLitter": 2, "ForestShrub": 4, "ForestStones": 2}
OLD_SPECIES = {"Meadow": 4, "GroundClutter": 2, "Blueberry": 8}
# KiteDemo only: the DragonCave / Atlantis_Ruins packs are gitignored and NOT on
# disk (run 1, 2026-09-27: "asset does not exist" x6). Ferns, heather, the two
# rocks already carry rock_pivots.json rows; these three need engine_derived rows.
NEW_MESHES = [
    "/Game/KiteDemo/Environments/Foliage/Grass/FieldGrass/SM_FieldGrass_01",
    "/Game/KiteDemo/Environments/Foliage/Leaves/SM_DeadLeaves",
    "/Game/KiteDemo/Environments/Foliage/Leaves/SM_DeadLeaves_Flat",
]
TRACKED_ASSETS = [
    "LandscapeLab/Content/Materials/M_Alpine8K.uasset",
    "LandscapeLab/Content/Foliage/GT_alpine_8k_Meadow.uasset",
    "LandscapeLab/Content/Foliage/GT_alpine_8k_GroundClutter.uasset",
    "LandscapeLab/Content/Foliage/GT_alpine_8k_Blueberry.uasset",
]
PRE_EXISTING_INVALID = 2   # the two 'lighting' dot-py INVALIDs, measured on main 2026-09-27

# stations: forest_floor from the Brief 5 derived station; plaza/treeline from
# recipes/perf_budgets.json (spline.stations); near_ground = the P1 basin still.
STATIONS = {
    "forest_floor": {"x": -166400.0, "y": 192000.0, "pitch": -5.0, "yaw": 100.0},
    "forest_floor_ground": {"x": -166400.0, "y": 192000.0, "pitch": -25.0, "yaw": 100.0},
    "plaza": {"x": -210800.0, "y": 278800.0, "pitch": -2.0, "yaw": -12.8},
    "treeline": {"x": -190000.0, "y": 100000.0, "pitch": -2.0, "yaw": 105.0},
}
# Brief 7 P4 station pass: the five stations (perf_budgets spline + the derived
# forest_floor) + slope (= bench mid_slope = treeline XY) + the far-slope
# overlook that A2/FOG_TUNE used as the cliff/far-shading camera (cams.json camA).
P4_STATIONS = {
    "plaza": {"x": -210800.0, "y": 278800.0, "pitch": -2.0, "yaw": -12.8},
    "main_street": {"x": -204847.3, "y": 278048.0, "pitch": -2.0, "yaw": -12.9},
    "treeline": {"x": -190000.0, "y": 100000.0, "pitch": -2.0, "yaw": 105.0},
    "vista": {"x": -216400.0, "y": 63600.0, "pitch": -4.0, "yaw": 60.0},
    "forest_floor": {"x": -166400.0, "y": 192000.0, "pitch": -5.0, "yaw": 100.0},
    "slope": {"x": -190000.0, "y": 100000.0, "pitch": -12.0, "yaw": 105.0},
    "cliff_overlook": {"x": -201186.0, "y": 219000.0, "pitch": -9.0, "yaw": 270.0, "eye": 1599.8},
}
PERF = [
    ("forest_floor", os.path.join(BR5, "input", "forest_station.json")),
    ("open_max", os.path.join(BR5, "input", "open_max_station.json")),
    ("plaza", None),
]

V = {"started": datetime.datetime.now().isoformat(timespec="seconds"),
     "phases": {}, "aborted": None, "notes": []}
LAUNCHED = set()
PRE_UNTRACKED = set()   # GT_alpine_8k_* basenames untracked BEFORE the run (audit F6)


def log(msg):
    print("[P3B %s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg), flush=True)


_VERDICT_NAME = "verdict.json"


def save():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, _VERDICT_NAME), "w", encoding="utf-8") as fh:
        json.dump(V, fh, indent=1, default=str)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True)


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True)


def run(cmd, timeout, label, cwd=REPO):
    log("run: %s" % " ".join(os.path.basename(c) if os.sep in c else c for c in cmd))
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, out, err = r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired as e:
        rc, out, err = -999, (e.stdout or "") if isinstance(e.stdout, str) else "", "TIMEOUT"
    dt = time.time() - t0
    with open(os.path.join(OUT, "run_%s.log" % label), "a", encoding="utf-8") as fh:
        fh.write("### %s rc=%s dt=%.0fs\n%s\n--- stderr ---\n%s\n" % (" ".join(cmd), rc, dt, out, err))
    log("  -> rc=%s in %.0fs" % (rc, dt))
    return rc, out, err


def ue(payload, sets=None, timeout=25, host_timeout=900):
    cmd = [PY, os.path.join(SCRIPTS, "ue_exec.py"), os.path.join(SCRIPTS, payload),
           "--timeout", str(timeout)]
    for k, v in (sets or {}).items():
        cmd += ["--set", "%s=%s" % (k, v)]
    rc, out, err = run(cmd, host_timeout, "ue_" + payload.replace(".txt", ""))
    i, j = out.find("{"), out.rfind("}")
    rep = None
    if i >= 0 and j > i:
        try:
            rep = json.loads(out[i:j + 1])
        except ValueError:
            rep = None
    return rc, rep, out


def editor_pids():
    r = ps("Get-Process UnrealEditor* -ErrorAction SilentlyContinue | ForEach-Object { $_.Id }")
    return {int(x) for x in (r.stdout or "").split() if x.strip().isdigit()}


def free_ram_gb():
    r = ps("(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory")
    try:
        return round(int((r.stdout or "").strip()) / 1048576.0, 2)
    except Exception:
        return None


def shader_workers():
    r = ps("(Get-Process ShaderCompileWorker* -ErrorAction SilentlyContinue | Measure-Object).Count")
    try:
        return int((r.stdout or "").strip())
    except Exception:
        return None


def editor_ws_gb():
    r = ps("(Get-Process UnrealEditor -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum")
    try:
        return round(int((r.stdout or "").strip()) / 1073741824.0, 2)
    except Exception:
        return None


def vram_mib():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True)
        return int((r.stdout or "").strip().splitlines()[0])
    except Exception:
        return None


def shas(paths):
    out = {}
    for p in paths:
        r = git("hash-object", p)
        out[p] = (r.stdout or "").strip() or None
    return out


def newest_content_age_s():
    newest = 0.0
    for root, _d, files in os.walk(CONTENT):
        for f in files:
            try:
                m = os.path.getmtime(os.path.join(root, f))
            except OSError:
                continue
            if m > newest:
                newest = m
    return time.time() - newest


def kill_editors():
    # ONLY the PIDs this run launched (audit F1; rules 8 and 11). A pre-existing
    # editor is refused at pre-flight and never force-killed by a run that does
    # not own it -- LAUNCHED is empty there, so this kills nothing.
    for pid in sorted(editor_pids() & LAUNCHED):
        ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid)
        log("killed PID %d" % pid)
    time.sleep(5)


def revert(fence):
    """Tracked assets back to the fence; NEW grass-type packages to _trash/."""
    r = git("checkout", fence, "--", *TRACKED_ASSETS)
    log("revert checkout rc=%s %s" % (r.returncode, (r.stderr or "").strip()[:200]))
    tracked = set((git("ls-files", "LandscapeLab/Content/Foliage").stdout or "").split())
    dest = os.path.join(REPO, "_trash", "p3b_revert_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    moved = []
    for f in glob.glob(os.path.join(CONTENT, "Foliage", "GT_alpine_8k_*.uasset")):
        rel = os.path.relpath(f, REPO).replace("\\", "/")
        # audit F6: only packages THIS run created -- untracked now AND absent
        # from the pre-flight untracked snapshot.
        if rel not in tracked and os.path.basename(f) not in PRE_UNTRACKED:
            os.makedirs(dest, exist_ok=True)
            shutil.move(f, os.path.join(dest, os.path.basename(f)))
            moved.append(rel)
    d = git("diff", "--quiet", fence, "--", *TRACKED_ASSETS)
    V["revert"] = {"moved_to_trash": moved, "diff_vs_fence_clean": d.returncode == 0}
    log("revert: moved %d new packages; diff vs fence clean=%s" % (len(moved), d.returncode == 0))


def abort(reason, fence=None, do_revert=False):
    V["aborted"] = reason
    log("ABORT: " + reason)
    kill_editors()
    if do_revert and fence:
        revert(fence)
    save()
    log("P3B ABORT")
    return 3


def main():
    global _VERDICT_NAME          # one declaration, before any use (SyntaxError otherwise)
    ap = argparse.ArgumentParser()
    ap.add_argument("--fence-tag", required=True)
    ap.add_argument("--ready-timeout", type=int, default=1800)
    ap.add_argument("--skip-perf", action="store_true")
    ap.add_argument("--offscreen", action="store_true",
                    help="launch -RenderOffScreen (smaller RAM footprint); stills are SKIPPED (need a window)")
    ap.add_argument("--build-map", default=None,
                    help="build the material on THIS light map instead of Alpine8K, WITHOUT --assign "
                         "(M_Alpine8K is already assigned; the rebuild is in place). Run 5 measured the "
                         "Alpine8K editor at 25.4 GB private / <1 GB free with a warm DDC -- the 797k-tree "
                         "world itself no longer leaves room for a shader-compiling rebuild.")
    ap.add_argument("--perf-only", action="store_true",
                    help="no editor: run the three -game perf stations only (phase 11) and write "
                         "verdict_perf.json -- used to re-measure after an ini cvar change")
    ap.add_argument("--save-proxies", action="store_true",
                    help="(with --stills-only) before the stills, SAVE every LandscapeStreamingProxy + "
                         "Landscape package so PreSave -> BuildGrassMaps refreshes the per-component "
                         "grass-type list from M_Alpine8K (a game world never does; -game had NO "
                         "landscape grass at all, GPUSceneInstanceCount tail 49,863 both runs)")
    ap.add_argument("--perf-tag", default="p3b_rtgrass", help="perf_standalone --tag prefix in --perf-only mode")
    ap.add_argument("--station-set", default="p3b", choices=["p3b", "p4"],
                    help="which camera set the stills phase shoots (p4 = five stations + slope + cliff_overlook)")
    ap.add_argument("--stills-dir", default=None, help="override the stills output dir")
    ap.add_argument("--still-suffix", default="_look_p3b")
    ap.add_argument("--stills-only", action="store_true",
                    help="windowed launch, Look stills + bench restore + close only (no measure/rebuild/read-back)")
    a = ap.parse_args()
    V["mode"] = {"offscreen": a.offscreen, "stills_only": a.stills_only, "skip_perf": a.skip_perf,
                 "build_map": a.build_map}
    map_path = a.build_map or "/Game/Alpine8K"
    expect_level = map_path.rstrip("/").split("/")[-1]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(STILLS, exist_ok=True)
    V["fence_tag"] = a.fence_tag
    fence = a.fence_tag
    if a.perf_only:
        if editor_pids():
            return abort("editors running: %s" % sorted(editor_pids()))
        V["mode"]["perf_only"] = True
        _VERDICT_NAME = "verdict_perf.json"
        rc = close_and_perf(a)
        return rc

    # ---- 0 pre-flight ----------------------------------------------------
    if editor_pids():
        return abort("editors already running: %s" % sorted(editor_pids()))
    if git("rev-parse", "-q", "--verify", "refs/tags/" + fence).returncode != 0:
        return abort("fence tag %s does not exist" % fence)
    rc, out, _ = run([PY, os.path.join(SCRIPTS, "resource_guard.py")], 120, "guard")
    V["phases"]["guard"] = {"rc": rc, "tail": out.strip()[-300:]}
    V["pre_shas"] = shas(TRACKED_ASSETS)
    _tracked = set((git("ls-files", "LandscapeLab/Content/Foliage").stdout or "").split())
    V["pre_gt_all"] = sorted(os.path.basename(f) for f in
                             glob.glob(os.path.join(CONTENT, "Foliage", "GT_alpine_8k_*.uasset")))
    PRE_UNTRACKED.update(os.path.basename(f) for f in
                         glob.glob(os.path.join(CONTENT, "Foliage", "GT_alpine_8k_*.uasset"))
                         if os.path.relpath(f, REPO).replace("\\", "/") not in _tracked)
    V["pre_gt_untracked"] = sorted(PRE_UNTRACKED)
    save()

    # ---- 1 launch --------------------------------------------------------
    pre = editor_pids()
    launch = ["powershell", "-NoProfile", "-File", os.path.join(SCRIPTS, "launch_editor.ps1"),
              "-Map", map_path]
    if not a.offscreen:
        launch.append("-Windowed")
    subprocess.Popen(launch, cwd=REPO)
    t0 = time.time()
    while time.time() - t0 < 120 and not LAUNCHED:
        LAUNCHED.update(editor_pids() - pre)
        time.sleep(3)
    if not LAUNCHED:
        return abort("editor did not appear within 120 s")
    log("launched PIDs %s; waiting for bootstrap" % sorted(LAUNCHED))
    ready = False
    t0 = time.time()
    while time.time() - t0 < a.ready_timeout:
        LAUNCHED.update(editor_pids() - pre)
        if subprocess.run([PY, os.path.join(SCRIPTS, "bootstrap.py"), "--timeout", "25"],
                          cwd=REPO, capture_output=True, text=True).returncode == 0:
            ready = True
            break
        time.sleep(10)
    if not ready:
        return abort("editor not ready within %s s" % a.ready_timeout)
    V["phases"]["launch"] = {"pids": sorted(LAUNCHED), "ready_s": round(time.time() - t0)}
    log("editor ready after %.0f s" % (time.time() - t0))
    # RAM SETTLE (run 2, 2026-09-27): bootstrap answers while the 797k-tree
    # world is still loading and free RAM dips to ~1.7 GB; the measurement
    # tool's 3 GB floor then declares a partial run. Wait for two consecutive
    # samples >= 6 GB free (15 s apart) before touching the editor.
    # Run 3 (2026-09-27): free RAM sat at 0.7-1.7 GB for the whole 900 s. The
    # operator's disk cleanup deleted LandscapeLab/DerivedDataCache, so this
    # launch rebuilds the DDC (ShaderCompileWorker fleet + derived data) --
    # cold and slow, not a steady state. Wait up to 2 h, and require BOTH
    # zero ShaderCompileWorker processes and >= 6 GB free, twice in a row.
    t1 = time.time()
    okc = 0
    n = 0
    if a.stills_only:
        # The Alpine8K editor at 797k trees sits at ~25 GB private and never
        # reaches 6 GB free (runs 3-5); the stills session is the light work the
        # P3a stills already did under that pressure. Log RAM, do not gate.
        okc = 2
        V["notes"].append("stills-only: RAM settle gate NOT applied (Alpine8K editor ~25 GB private by measurement); free %s GB" % free_ram_gb())
        log(V["notes"][-1])
    while okc < 2 and time.time() - t1 < 7200:
        free = free_ram_gb()
        workers = shader_workers()
        ews = editor_ws_gb()
        if free is not None and free >= 6.0 and workers == 0:
            okc += 1
            if okc >= 2:
                break
        else:
            okc = 0
        if n % 4 == 0:
            log("free RAM %s GB, ShaderCompileWorker x%s, editor WS %s GB; waiting for the load/DDC to settle"
                % (free, workers, ews))
        n += 1
        time.sleep(15)
    V["phases"]["ram_settle"] = {"free_gb": free_ram_gb(), "shader_workers": shader_workers(),
                                 "editor_ws_gb": editor_ws_gb(), "waited_s": round(time.time() - t1)}
    if okc < 2:
        return abort("free RAM / shader workers never settled within 7200 s (last %s GB, workers %s)"
                     % (free_ram_gb(), shader_workers()))
    log("RAM settled: %s GB free after %.0f s" % (free_ram_gb(), time.time() - t1))
    save()

    # ---- 2 level check ---------------------------------------------------
    rc, rep, _ = ue("brief7_level_check_payload.txt")
    V["phases"]["level_check"] = rep
    if not rep or not rep.get("ok") or expect_level not in str(rep.get("world_path") or ""):
        return abort("rule 11: level check failed (expected %s): %s" % (expect_level, rep or "no JSON"))
    log("level %s; grass inputs before: %s" % (rep.get("world_path"), rep.get("grass_output_inputs")))
    save()

    # ---- 3 measure the new meshes ---------------------------------------
    if a.stills_only:
        log("stills-only mode: skipping measure / validate / rebuild / read-back")
        rc, out = 0, ""
    cmd = [PY, os.path.join(SCRIPTS, "measure_clutter_meshes.py"), "--group", "brief7_p3b_clutter",
           "--timeout", "25"]
    for m in NEW_MESHES:
        cmd += ["--mesh", m]
    if a.stills_only:
        _VERDICT_NAME = "verdict_stills.json"
        if a.save_proxies:
            log("saving landscape proxies (PreSave -> BuildGrassMaps): batches of 32; this is a WORLD write")
            rc, rep, _ = ue("brief7_save_landscape_proxies_payload.txt", {"BATCH": 32, "APPLY": "True"},
                            timeout=25, host_timeout=7200)
            V["phases"]["save_proxies"] = rep
            save()
            if not rep or not rep.get("ok") or rep.get("batch_failures"):
                return abort("landscape proxy save failed: %s" % (rep or "no JSON"))
            log("saved %s packages (%s proxies, %s landscapes), dirty after %s; grass sample before %s after %s"
                % (rep.get("saved_ok"), rep.get("proxies"), rep.get("landscapes"), rep.get("dirty_after"),
                   rep.get("grass_types_sample_before"), rep.get("grass_types_sample_after")))
        return stills_and_close(a, fence)
    rc, out, err = run(cmd, 1800, "measure")
    V["phases"]["measure"] = {"rc": rc, "tail": out.strip()[-1500:]}
    save()
    if rc != 0:
        return abort("measure_clutter_meshes rc=%s (a mesh failed the pivot contract or could not be measured)" % rc)

    # ---- 4 offline validation -------------------------------------------
    rc, out, err = run([PY, os.path.join(SCRIPTS, "import_heightmap.py"), "--recipe", RECIPE, "--offline"],
                       600, "validate")
    invalid = [l.strip() for l in out.splitlines() if "INVALID" in l]
    V["phases"]["validate"] = {"rc": rc, "invalid": invalid}
    save()
    if len(invalid) != PRE_EXISTING_INVALID or any("lighting" not in l for l in invalid):
        return abort("recipe validation: %d INVALID lines (expected only the %d pre-existing lighting ones): %s"
                     % (len(invalid), PRE_EXISTING_INVALID, invalid[:6]))

    # ---- 5 rebuild -------------------------------------------------------
    vr0 = vram_mib()
    build_cmd = [PY, os.path.join(SCRIPTS, "make_landscape_material.py"), "--recipe", RECIPE,
                 "--timeout", "25"]
    if a.build_map:
        log("build map %s: rebuilding M_Alpine8K IN PLACE without --assign (already assigned to the "
            "Alpine8K landscape since 2026-09-25; the asset path is unchanged)" % a.build_map)
        build_cmd += ["--build-level", a.build_map]
    else:
        build_cmd.append("--assign")
    rc, out, err = run(build_cmd, 3600, "rebuild")
    V["phases"]["rebuild"] = {"rc": rc, "vram_before": vr0, "vram_after": vram_mib(),
                              "tail": out.strip()[-3000:]}
    save()
    if rc != 0:
        return abort("make_landscape_material rc=%s" % rc, fence, do_revert=True)
    V["post_shas"] = shas(TRACKED_ASSETS)
    V["post_gt"] = sorted(os.path.basename(f) for f in
                          glob.glob(os.path.join(CONTENT, "Foliage", "GT_alpine_8k_*.uasset")))

    # ---- 6 read-back -----------------------------------------------------
    rb = {}
    bad = []
    for sp, n in list(NEW_SPECIES.items()) + list(OLD_SPECIES.items()):
        rc, out, err = run([PY, os.path.join(SCRIPTS, "read_grass_type.py"), "--asset",
                            "/Game/Foliage/GT_alpine_8k_" + sp, "--expect-varieties", str(n),
                            "--timeout", "60"], 600, "readback")
        rb[sp] = {"rc": rc, "expect_varieties": n, "tail": out.strip()[-900:]}
        if rc != 0:
            bad.append(sp)
    V["phases"]["readback"] = rb
    save()
    if bad:
        return abort("read_grass_type failed for %s" % bad, fence, do_revert=True)
    log("read-back OK for %d grass types" % len(rb))
    if a.build_map:
        log("build map run: stills need the Alpine8K world in a WINDOWED editor -- run --stills-only next")
        V["phases"]["stills"] = {"skipped": "built on %s; run --stills-only" % a.build_map}
        return close_and_perf(a)

    return stills_and_close(a, fence)


def stills_and_close(a, fence):
    """Phases 7-11. Stills need a WINDOW (LESSONS 2026-09-25); an --offscreen run skips 7-9."""
    if a.offscreen:
        log("offscreen mode: stills SKIPPED (need a windowed editor); run --stills-only afterwards")
        V["phases"]["stills"] = {"skipped": "offscreen launch"}
        return close_and_perf(a)
    # ---- 7 flush + look + dwell + dump -----------------------------------
    ue("brief7_console_exec_payload.txt", {"CMDS": '["grass.FlushCache"]'})
    rc, rep, _ = ue("brief7_p0e_setprofile_payload.txt", {"PROFILE": "look"})
    V["phases"]["profile_look"] = rep
    look_ok = bool(rep and rep.get("ok"))          # audit F3: read back, compared
    if not look_ok:
        V["notes"].append("LOOK PROFILE DID NOT READ BACK OK -- stills SKIPPED: %s" % (rep or "no JSON"))
        log(V["notes"][-1])
    st = STATIONS["forest_floor"]
    rc, rep, _ = ue("brief7_place_cam_payload.txt",
                    {"X": st["x"], "Y": st["y"], "PITCH": st["pitch"], "YAW": st["yaw"], "EYE": 175.0})
    V["phases"]["grass_dump_cam"] = rep                # audit F4: a 0-line dump vs no camera
    if not (rep and rep.get("ok")):
        V["notes"].append("grass dump: camera never arrived at forest_floor: %s" % (rep or "no JSON"))
        log(V["notes"][-1])
    log("dwell 45 s at forest_floor for grass generation")
    time.sleep(45)
    log_size = os.path.getsize(LOG) if os.path.isfile(LOG) else 0
    ue("brief7_console_exec_payload.txt", {"CMDS": '["grass.DumpGrassData -bygrasstype"]'})
    time.sleep(8)
    dump = []
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(log_size)
            tail = fh.read()
        dump = [l.strip() for l in tail.splitlines() if "GT_alpine_8k_" in l or "GrassType" in l or "grass" in l.lower()][:80]
    except OSError:
        pass
    V["phases"]["grass_dump"] = {"lines": dump, "n": len(dump)}
    log("grass dump lines: %d" % len(dump))
    save()

    # ---- 8 stills --------------------------------------------------------
    stills = {}
    station_set = P4_STATIONS if a.station_set == "p4" else STATIONS
    stills_dir = a.stills_dir or STILLS
    os.makedirs(stills_dir, exist_ok=True)
    for name, st in (station_set.items() if look_ok else []):
        if not look_ok:
            break
        rc, rep, _ = ue("brief7_place_cam_payload.txt",
                        {"X": st["x"], "Y": st["y"], "PITCH": st["pitch"], "YAW": st["yaw"],
                         "EYE": st.get("eye", 175.0)})
        if not rep or not rep.get("ok"):
            stills[name] = {"error": "place_cam: %s" % (rep or "no JSON")}
            continue
        time.sleep(35)
        rc, out, err = run([PY, os.path.join(SCRIPTS, "shoot.py"), "--name", name + a.still_suffix,
                            # '=' form: a negative coordinate as a separate token reads as an
                            # option to argparse ("--loc: expected one argument", 2026-09-27).
                            "--loc=" + rep["shoot_loc"], "--rot=0,%s,%s" % (st["pitch"], st["yaw"]),
                            "--outdir", stills_dir, "--deadline", "600"], 700, "shoot")
        png = os.path.join(stills_dir, name + a.still_suffix + ".png")
        stills[name] = {"rc": rc, "cam": rep.get("cam_loc"), "png": os.path.exists(png)}
        log("still %s rc=%s png=%s" % (name, rc, os.path.exists(png)))
        save()
    V["phases"]["stills"] = stills if look_ok else {"skipped": "Look profile not read back ok"}
    V["vram_editor_peak"] = vram_mib()

    # ---- 9 bench restore read back --------------------------------------
    rc, rep, _ = ue("brief7_p0e_setprofile_payload.txt", {"PROFILE": "bench"})
    V["phases"]["profile_bench_restore"] = rep
    V["bench_restore_ok"] = bool(rep and rep.get("ok"))   # audit F5: compared, not just recorded
    if not V["bench_restore_ok"]:
        V["notes"].append("BENCH RESTORE DID NOT READ BACK OK (runtime state only; editor killed unsaved): %s" % (rep or "no JSON"))
        log(V["notes"][-1])
    save()

    return close_and_perf(a)


def close_and_perf(a):
    if getattr(a, "perf_only", False):
        return perf_phase(a)
    # ---- 10 close --------------------------------------------------------
    rc, rep, _ = ue("dirty_package_census_payload.txt")
    V["phases"]["dirty_census"] = rep
    for _ in range(40):
        age = newest_content_age_s()
        if age >= 120:
            break
        log("Content newest write %.0f s ago; waiting" % age)
        time.sleep(15)
    V["phases"]["content_quiet_s"] = round(newest_content_age_s())
    kill_editors()
    restore = os.path.join(REPO, "LandscapeLab", "Saved", "Autosaves", "PackageRestoreData.json")
    V["phases"]["close"] = {"editors_after": sorted(editor_pids()),
                            "package_restore_data": os.path.exists(restore)}
    save()

    return perf_phase(a)


def perf_phase(a):
    # ---- 11 -game perf ---------------------------------------------------
    if not a.skip_perf:
        perf = {}
        for name, sj in PERF:
            tag = (a.perf_tag + "_" + name) if getattr(a, "perf_only", False) else "p3b_" + name
            cmd = [PY, os.path.join(SCRIPTS, "perf_standalone.py"), "--noxgecontroller", "--tag", tag]
            if getattr(a, "perf_only", False):
                # rule 12: perf_standalone SETS then RE-QUERIES each --set-cvar into the
                # -game log, so the ini value is read back, not assumed.
                cmd += ["--set-cvar", "grass.GrassMap.UseRuntimeGeneration 1"]
            cmd += (["--station-json", sj, "--station-name", name] if sj else ["--only", name])
            rc, out, err = run(cmd, 2400, "perf_" + name)
            rec = {"rc": rc}
            for line in out.splitlines():
                if "GPU p90" in line:
                    rec["line"] = line.strip()[:200]
                    m = re.search(r"GPU p90 ([\d.]+)", line)
                    if m:
                        rec["gpu_p90_ms"] = float(m.group(1))
                    m = re.search(r"Game p90 ([\d.]+)", line)
                    if m:
                        rec["game_p90_ms"] = float(m.group(1))
                if "vram peak across stations" in line.lower():
                    m = re.search(r"(\d+)\s*MiB", line)
                    if m:
                        rec["vram_peak_mib"] = int(m.group(1))
                    rec["over_ceiling"] = "OVER ABORT CEILING" in line
            perf[name] = rec
            log("perf %s: %s" % (name, rec))
            save()
        V["phases"]["perf"] = perf

    V["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    save()
    log("P3B DONE")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise                      # a normal exit is not an abort (run 8 logged one)
    except BaseException as exc:
        V["aborted"] = "exception: %r" % (exc,)
        kill_editors()
        save()
        log("P3B ABORT (exception) %r" % (exc,))
        raise
