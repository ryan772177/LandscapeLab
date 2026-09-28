"""hlod_build_batched.py -- finish the HLOD rebuild in BOUNDED batches.

RULING, 2026-09-09 (Ryan): batch the HLOD rebuild, ~200 cells per run, a fresh
process per batch. This script is that loop.

WHY BATCHES AT ALL
    Three full-world builds have been spent on 2,267 cells and none finished.
    Build 3 died at 376 of 2,267 after 78 minutes on
    `DXGI_ERROR_DRIVER_INTERNAL_ERROR` / `CreateReservedResource` FAILED at 65%
    of VRAM budget (LESSONS 2026-09-08i). No cause has been established, and
    two earlier editor crashes carry a DIFFERENT signature. With no cause, the
    only honest lever is exposure: a fault should cost one batch, not the run.

================================================================================
HOW A RUN IS BOUNDED -- and this was VERIFIED IN ENGINE SOURCE, not invented
================================================================================

LESSONS 2026-09-08i guessed there was no batch flag and proposed repeated
`-BuildHLODLayer=` or `-BuildSingleHLOD=`. **There IS a batch flag.** The
builder carries the distributed-build sharding machinery, and it works
perfectly well on one machine:

    WorldPartitionHLODsBuilder.cpp:176-178
        GetParamValue("BuildManifest=", BuildManifest);
        GetParamValue("BuilderIdx=",    BuilderIdx);
        GetParamValue("BuilderCount=",  BuilderCount);

    :1062-1095  GetHLODActorsToBuild() -- when BuildManifest is set, the actor
                list comes ONLY from section [HLODBuilder<BuilderIdx>], key
                `+HLODActorGuid`. Section name: :68
                    FString::Printf(TEXT("HLODBuilder%d"), BuilderIndex)

    :580-586    GenerateBuildManifest() runs inside the SETUP step.
    :1418       GetHLODWorkloads(BuilderCount, ...) -- splits the 2,267 actors
                into BuilderCount workloads, KEEPING EACH HIERARCHY GROUP
                WHOLE and child-before-parent (:1236-1262).
    :1426-1427  writes [General] BuilderCount and EngineVersion.

    :287-310    ValidateParams(): a build run with a manifest REFUSES without
                -BuilderIdx, refuses if the file is missing, and refuses if the
                manifest's EngineVersion differs from the running engine's.
                Three ways to fail loudly; none silent.

    :1325-1412  ValidateWorkload(): for every actor in the batch, every entry
                of GetChildHLODActors() must appear EARLIER in the same batch.
                This is why the batches are the ENGINE's partition and not a
                hand-rolled "next 200 by package size" -- a size-ordered list
                would split hierarchy groups and be refused here.

GENERATING THE MANIFEST WRITES NOTHING TO THE WORLD
    The manifest pass runs `-SetupHLODs -ReportOnly`. `bReportOnly` gates the
    only two write paths in this world's generator
    (`WorldPartitionRuntimeHashSetHLODGeneration.cpp:541` the save,
    `:659` the destroy-unreferenced pass), so the 376 already-built cells
    cannot be touched. The script proves it afterwards rather than trusting it:
    the package census must be byte-for-byte and mtime-for-mtime unchanged.

================================================================================
⛔ THE SKIP DOES NOT WORK, AND THAT IS WHY EVERY BATCH FORCES
================================================================================

**Measured 2026-09-09, batch 0, 191 cells, no `-RebuildHLODs`: approve 0,
reject 191, 30 seconds, nothing changed.** 77 of those cells record
`LayerType: MeshMerge(1)` in their own saved build report while the layer asset
reads `EHLODLayerType::MeshApproximate`. The decision is `OldHash != NewHash`
(`HLODRebuildPolicyHashCompare.cpp:33`) and the hashes compare EQUAL. **Why
they are equal is NOT established and no cause is named here** — the one
concrete lead found in source fails its own prediction, and is written down in
LESSONS 2026-09-09 so the next session tests it instead of re-deriving it.

So `-RebuildHLODs` is on by default (`--no-force` to drop it, for testing the
skip only). It sets `bForceBuild` (WorldPartitionHLODsBuilder.cpp:172), which
empties `OldRebuildPolicyDataSet` (WorldPartitionHLODUtilities.cpp:942) and
bypasses the comparison entirely. Forcing is cheap here and the figure is
measured, not assumed: only **115 of 2,267** cells have ever been built under
the MeshApproximate layer, and the 1,225 Instancing cells rebuild at 0.02 s
each (R-HLOD 08d). The manifest shards still do the job they were chosen for —
bounding GPU exposure to ~190 cells per process.

The description below is retained because it is the mechanism the engine
INTENDS, it is what the flags mean, and the next session needs it to test the
lead.

================================================================================
HOW A BATCH IS SUPPOSED TO SKIP CELLS THAT ARE ALREADY CURRENT
================================================================================

`-BuildHLODs` WITHOUT `-RebuildHLODs` leaves bForceBuild false
(WorldPartitionHLODsBuilder.cpp:172), which reaches
`AWorldPartitionHLOD::BuildHLOD(false)` (:839) and then:

    WorldPartitionHLODUtilities.cpp:936-957
        bForceBuild = bIsDirty || InBuildParams.bForceBuild;
        OldDataSet  = bForceBuild ? {} : HLODActor->GetHLODRebuildPolicyDataSet()
        NewDataSet  = ComputeDataForRebuildPolicies(...)
        if (UHLODRebuildPolicy::Evaluate(...) != ApproveRebuild) return false;

    HLODRebuildPolicyHashCompare.cpp:33
        return OldHash != NewHash ? ApproveRebuild : RejectRebuild;

and the hash covers the LAYER's settings, not just the source actors:

    HLODLayer.cpp:278-297  ComputeHLODHash hashes LayerType and
                           HLODBuilderSettings->ComputeHLODHash(...)
    HLODSourceActors.cpp:20-26     -> the layer
    HLODSourceActorsFromCell.cpp:213-220 -> + the source actor set

So the ~705 cells still carrying old **MeshMerge** output hash-mismatch the
current **MeshApproximate / accuracy 1.5** layer and are REBUILT, while the
~320 already rebuilt under that same layer match and are REJECTED. That is the
mechanism the ruling's step 3 asks to read back, and the engine states its
decision per cell, in the log (HLODRebuildPolicy.cpp:88, 121-122, 137):

    LogHLODBuilder: Display: Evaluating HLOD rebuild policies...
    LogHLODBuilder: Display:  * HLODRebuildPolicyHashCompare -> RejectRebuild
    LogHLODBuilder: Display: Evaluated HLOD rebuild policies, final decision: ...

**A REJECTED CELL IS NOT FREE.** The decision is taken AFTER
`LoadSourceActors` (:925), so a skipped cell still pays its source-actor load.
Skipping saves the voxelise/merge/bake, which is the whole cost that matters,
but do not budget a skipped batch at zero.

================================================================================
WHAT IS CHECKED BETWEEN BATCHES, AND WHY EACH CHECK EXISTS
================================================================================

  TRUE EXIT      the OS process list, never the log line. R-HLOD 08d: a
                 commandlet that prints "Engine exit requested ... result 0"
                 has NOT exited -- three runs sat at 0.005 cores for an hour
                 after printing it. `Popen.wait()` returning is necessary and
                 not sufficient; the process table is the instrument.

  TORN PACKAGES  every HLOD package written during the batch must be >= 1 KB
                 and its mtime must precede process exit. This is the check
                 that established "no damage" after builds 2 and 3
                 (LESSONS 2026-09-08i): 0 zero-length, 0 short, newest write
                 3 s BEFORE the crash.

  STALE CENSUS   the number of cells whose OWN saved build report still records
                 `LayerType: MeshMerge(1)` must FALL by the batch's Merged
                 count. `scripts/hlod_report_census.py`.
                 **Package size and triangle count were both tried for this and
                 BOTH misclassify** -- 705 packages over 5 MB against 468 cells
                 at >=100k triangles, and a MeshMerge L1 cell with 8,449
                 triangles in a 19 MB package. Both are downstream of the same
                 event, the geometry a build emitted, so agreeing would not have
                 made either right (non-negotiable 0). The build report records
                 what the build was CONFIGURED with, which is a different fact.
                 It is also a different instrument from the run's own log, so a
                 disagreement between them is itself a finding.

  VRAM PEAK      sampled from nvidia-smi across the batch. Build 3 died at
                 9,899 of 15,235 MB; the editor crashes died at 12,434. Peak
                 per batch is the only number that can support or kill the
                 "accumulation within one process" hypothesis, and it is
                 EVIDENCE, not a cause.

  GPU SIGNATURE  the log is scanned for the two known signatures and for
                 anything else fatal. A crash records signature, batch, the
                 cell in flight and VRAM, then the batch is retried ONCE in a
                 fresh process. A second crash on the same batch stops the run
                 and names the cell.

================================================================================
USAGE
================================================================================

    python scripts/hlod_build_batched.py census
        Read-only. Package census now: total, over 5 MB, under 3 MB, bytes.

    python scripts/hlod_build_batched.py plan [--batches 12]
        Preflight (zero editors, RAM, VRAM), write BUILD_START_MARKER, take the
        baseline census, generate the manifest read-only, and PROVE the world
        was not written. Writes nothing under Content/.

    python scripts/hlod_build_batched.py run [--from 0] [--only 0]
        Run batches. One fresh commandlet per batch. Stops on a second crash of
        the same batch, on a torn package, or on a census that fails to fall.

State accumulates in `_verify/hlod/<date>/batches.json`, so `run --from N`
resumes a session that was interrupted.

NOT DONE BY THIS SCRIPT, deliberately: the git step. `-BuildHLODs` inflates
TRACKED stubs, and `.gitignore` does not apply to tracked paths, so
`scripts/hlod_gitignore.py --apply` must run BEFORE the first commit that would
otherwise carry ~17 GB into history (R-HLOD 08e). This script commits ONLY its
own logs and JSON under `_verify/`.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE_PROJECT_ROOT = os.path.join(REPO_ROOT, "LandscapeLab")
UPROJECT = os.path.join(UE_PROJECT_ROOT, "LandscapeLab.uproject")
LEVEL = "/Game/Alpine8K"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_paths import EDITOR_CMD_EXE  # noqa: E402
from hlod_report_census import read_report  # noqa: E402
import hlod_attribution  # noqa: E402

# What a cell's own saved build report records as the layer it was built with.
# The ONLY sound discriminator -- see the STALE CENSUS note above.
STALE_LAYER = "MeshMerge(1)"
CURRENT_LAYER = "MeshApproximate(3)"

PACKAGE_LIST = os.path.join(REPO_ROOT, "_verify", "hlod", "hlod_packages.txt")
EXPECTED_PACKAGES = 2107   # 2026-09-28: -SetupHLODs after the P3a regen destroyed 886 unreferenced HLOD actors and created new ones; hlod_gitignore.py --apply listed 2,107 by signature (was 2267)

# The mixed-world bands, from CURRENT STATE / LESSONS 2026-09-08i. A cell over
# this is old MeshMerge output (~329k triangles); the rebuilt cells land near
# 1.46 MB (the measured one: 1,455,802 B for 3,988 triangles).
STALE_BYTES = 5 * 1024 * 1024
REBUILT_BYTES = 3 * 1024 * 1024

# Torn-package floor. The Setup stubs were ~130 bytes and every built package
# measured is >= 56 KB, so 1 KB separates "stub or truncated" from "written".
MIN_PACKAGE_BYTES = 1024

POLL_SECONDS = 20
VRAM_POLL_SECONDS = 10

# Ground truth for these came from _verify/hlod/20260908/build3_acc15.log, not
# from reading the source: the format string in the source omits the log
# category and timestamp that the file actually carries.
RE_PROGRESS = re.compile(
    r"\[(\d+) / (\d+)\] Building HLOD actor (\S+?)\.\.\.")
RE_DECISION = re.compile(
    r"Evaluated HLOD rebuild policies, final decision: (\w+)")
RE_BUILT = re.compile(r"#### Built (\d+) HLOD actors ####")
RE_TOBUILD = re.compile(r"#### Building (\d+) HLOD actors ####")

# Two distinct signatures are on record and they are NOT the same fault
# (LESSONS 2026-09-08i). Both are matched, plus a general fatal net, because a
# monitor that greps only the signatures it already knows is silent on the
# third one.
FATAL_PATTERNS = [
    ("gpu_crash", re.compile(r"GPU crash detected")),
    ("device_removed", re.compile(r"Device \d+ Removed: (\S+)")),
    ("reserved_resource", re.compile(r"CreateReservedResource\(")),
    ("device_hung", re.compile(r"DXGI_ERROR_DEVICE_HUNG")),
    ("driver_internal", re.compile(r"DXGI_ERROR_DRIVER_INTERNAL_ERROR")),
    ("assert", re.compile(r"Assertion failed:")),
    ("fatal", re.compile(r"Fatal error")),
    ("builder_error", re.compile(r"LogWorldPartitionHLODsBuilder: Error:")),
]
# The colon is not optional decoration -- the line is tab-separated with a
# colon (`Local Used:\t9899.65 MB`) and a regex written from the prose in
# LESSONS ("Local Used 9,899 of 15,235 MB") does not match it. Checked against
# _verify/hlod/20260908/build3_acc15.log:5009.
RE_VRAM_USED = re.compile(r"Local Used:?\s+([\d,\.]+)\s*MB")

# THE PROCESS EXIT CODE IS NOT A FAILURE SIGNAL ON THIS MACHINE.
# Every HLOD commandlet here ends
#     LogInit: Display: Failure - 2 error(s), 2 warning(s)
# and exits non-zero, because IncrediBuild's Manager.exe holds port 8000 and
# UE cannot bind it (docs/environment.md), so `LogHttpListener: Error:
# HttpListener unable to bind to 127.0.0.1:8000` is logged twice on EVERY run.
# Verified on the two runs that produced the accepted cell:
#   _verify/hlod/20260908/build_one_cell_noxge.log:2420 "Built 6 HLOD actors"
#                                              :2435 "Failure - 2 error(s)"
#   _verify/hlod/20260908/build_onecell_acc15.log:2192 / :2207  identical
# Treating rc != 0 as a crash would retry EVERY batch once and double the run.
# Completion is judged by the builder's own marker instead:
#     #### Built N HLOD actors ####
# and the error COUNT is carried per batch so a run that logs more than the
# baseline two is still visible.
BASELINE_ERRORS = 2
RE_EXIT_SUMMARY = re.compile(
    r"(?:Success|Failure) - (\d+) error\(s\), (\d+) warning\(s\)")


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------

def running_editors():
    """Names+PIDs of any live UnrealEditor process. The process table is the
    instrument -- standing rule 11 and R-HLOD 08d both turn on this."""
    out = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, check=False).stdout
    found = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if not parts or len(parts) < 2:
            continue
        name = parts[0].strip('"')
        if name.lower().startswith("unrealeditor"):
            found.append((name, parts[1]))
    return found


def vram_used_mb():
    """Used VRAM in MiB, or None if nvidia-smi is unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=False).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def available_ram_gb():
    try:
        from resource_guard import available_gb
        return available_gb()
    except Exception:
        return None


# --------------------------------------------------------------------------
# census -- bytes on disk, an instrument independent of the engine's log
# --------------------------------------------------------------------------

def load_package_list():
    """The signature-verified HLOD package set, from hlod_gitignore.py's
    manifest. Membership is by the `WorldPartitionHLOD` class signature in the
    bytes, NOT by path -- World Partition hash-buckets HLOD packages into the
    same directories as landscape proxies (standing rule 8, R-HLOD 08e).

    Re-verified against disk on every load rather than trusted: a manifest is a
    derived record and this is rule 9's whole point.
    """
    if not os.path.isfile(PACKAGE_LIST):
        raise SystemExit("missing package list: %s\n"
                         "Regenerate with: python scripts/hlod_gitignore.py"
                         % PACKAGE_LIST)
    rels = []
    with open(PACKAGE_LIST, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                rels.append(line)
    return rels


def census():
    """(summary dict, {relpath: (size, mtime_ns)}) for the HLOD package set."""
    rels = load_package_list()
    per = {}
    missing = []
    over, under, short, total_bytes = 0, 0, 0, 0
    for rel in rels:
        full = os.path.join(REPO_ROOT, rel.replace("/", os.sep))
        try:
            st = os.stat(full)
        except OSError:
            missing.append(rel)
            continue
        per[rel] = (st.st_size, st.st_mtime_ns)
        total_bytes += st.st_size
        if st.st_size > STALE_BYTES:
            over += 1
        elif st.st_size < REBUILT_BYTES:
            under += 1
        if st.st_size < MIN_PACKAGE_BYTES:
            short += 1
    return {
        "packages_listed": len(rels),
        "packages_present": len(per),
        "packages_missing": len(missing),
        "missing_sample": missing[:5],
        "over_5mb": over,
        "under_3mb": under,
        "shorter_than_1kb": short,
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / 1e9, 3),
    }, per


def layer_census():
    """{LayerType: count} across every HLOD package, from each cell's own
    saved build report. The stale count is the entry for STALE_LAYER."""
    counts = collections.Counter()
    for rel in load_package_list():
        full = os.path.join(REPO_ROOT, rel.replace("/", os.sep))
        rep = read_report(full)
        counts[rep[1] if rep else "<no report>"] += 1
    return dict(counts)


def stride_sample(per, count=12):
    """Cells sampled at even intervals across the SORTED path list.

    Not the first N. After build 2 was killed part-way the world was mixed, and
    the builder does not write in a representative order, so a sample from
    either end reports a clean world or a stale one depending on which end --
    the reasoning already recorded in scripts/payloads/hlod_sample_cells.py.
    """
    keys = sorted(per)
    if not keys:
        return []
    step = max(1, len(keys) // count)
    picked = keys[::step][:count]
    return [{"package": k, "bytes": per[k][0],
             "band": ("STALE>5MB" if per[k][0] > STALE_BYTES
                      else "rebuilt<3MB" if per[k][0] < REBUILT_BYTES
                      else "middle")}
            for k in picked]


# --------------------------------------------------------------------------
# commandlet
# --------------------------------------------------------------------------

def base_args(log_path):
    """The invariant part of every HLOD commandlet on this machine.

    `-noxgecontroller` is MANDATORY and not a preference: without it
    IsRunningCommandlet() is true, AvoidUsingLocalMachine exempts commandlets
    (XGEControllerModule.cpp:97-111), shader jobs go to a local IncrediBuild
    that never returns them, and the run wedges at 0.044 cores forever.
    R-HLOD 08d, measured both ways.
    """
    return [
        EDITOR_CMD_EXE, UPROJECT, LEVEL,
        "-run=WorldPartitionBuilderCommandlet",
        "-Builder=WorldPartitionHLODsBuilder",
        "-noxgecontroller", "-AllowCommandletRendering",
        "-unattended", "-nosplash", "-nopause",
        "-abslog=%s" % log_path,
    ]


def launch(args):
    """Fresh process, its own process group so a Ctrl-C here cannot reach it
    mid-write."""
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(args, cwd=REPO_ROOT, creationflags=flags,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def scan_log(path):
    """Progress, decisions and fatal signatures from a commandlet log.

    Read defensively: the log is being written by another process and carries a
    BOM, so it is opened with errors='replace' rather than assumed clean.
    """
    res = {"last_index": 0, "total": 0, "last_cell": None,
           "approve": 0, "reject": 0, "built": None, "to_build": None,
           "fatal": [], "vram_at_fault_mb": None,
           "log_errors": None, "log_warnings": None}
    if not os.path.isfile(path):
        return res
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = RE_PROGRESS.search(line)
                if m:
                    res["last_index"] = int(m.group(1))
                    res["total"] = int(m.group(2))
                    res["last_cell"] = m.group(3)
                    continue
                m = RE_DECISION.search(line)
                if m:
                    if m.group(1) == "ApproveRebuild":
                        res["approve"] += 1
                    elif m.group(1) == "RejectRebuild":
                        res["reject"] += 1
                    continue
                m = RE_BUILT.search(line)
                if m:
                    res["built"] = int(m.group(1))
                    continue
                m = RE_TOBUILD.search(line)
                if m:
                    res["to_build"] = int(m.group(1))
                    continue
                m = RE_VRAM_USED.search(line)
                if m:
                    res["vram_at_fault_mb"] = float(
                        m.group(1).replace(",", ""))
                    continue
                m = RE_EXIT_SUMMARY.search(line)
                if m:
                    res["log_errors"] = int(m.group(1))
                    res["log_warnings"] = int(m.group(2))
                    continue
                for name, pat in FATAL_PATTERNS:
                    fm = pat.search(line)
                    if fm:
                        res["fatal"].append(
                            {"signature": name, "line": line.strip()[:300]})
                        break
    except OSError:
        pass
    return res


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

def parse_manifest(path):
    """{section: [guid, ...]} plus [General]. Hand-parsed because the file is a
    UE FConfigFile, and configparser rejects its repeated `+HLODActorGuid`
    keys."""
    sections, general = {}, {}
    cur = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                sections.setdefault(cur, [])
            elif "=" in line and cur:
                key, val = line.split("=", 1)
                if key.strip() == "+HLODActorGuid":
                    sections[cur].append(val.strip())
                elif cur == "General":
                    general[key.strip()] = val.strip()
    sections.pop("General", None)
    return general, sections


def cmd_plan(args, run_dir):
    editors = running_editors()
    if editors:
        raise SystemExit("REFUSING: %d UnrealEditor process(es) alive: %s\n"
                         "Standing rule 11: wait for ZERO editors."
                         % (len(editors), editors))

    ram = available_ram_gb()
    vram = vram_used_mb()
    print("preflight  editors=0  RAM avail=%s GB  VRAM used=%s MiB"
          % (ram, vram))

    marker = os.path.join(run_dir, "BUILD_START_MARKER")
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("batched HLOD build, %d batches\n" % args.batches)
    print("marker     %s" % marker)

    before, per_before = census()
    print("census     %s" % json.dumps(before))

    manifest = os.path.join(run_dir, "HLODBuildManifest.ini")
    log_path = os.path.join(run_dir, "manifest_setup.log")
    cmd = base_args(log_path) + [
        "-SetupHLODs", "-ReportOnly",
        "-BuildManifest=%s" % manifest,
        "-BuilderCount=%d" % args.batches,
    ]
    print("manifest   %s" % " ".join(cmd[3:]))
    t0 = time.time()
    proc = launch(cmd)
    rc = proc.wait()
    mins = (time.time() - t0) / 60.0
    # rc is recorded, not tested -- see BASELINE_ERRORS. The manifest checks
    # below are what decide whether this pass worked.
    print("manifest   rc=%d in %.1f min (rc is NOT a failure signal here)"
          % (rc, mins))

    left = running_editors()
    if left:
        raise SystemExit("REFUSING: manifest pass did not truly exit: %s" % left)

    if not os.path.isfile(manifest):
        raise SystemExit("no manifest written; see %s" % log_path)

    general, sections = parse_manifest(manifest)
    total_guids = sum(len(v) for v in sections.values())
    print("manifest   sections=%d guids=%d general=%s"
          % (len(sections), total_guids, general))

    if total_guids != EXPECTED_PACKAGES:
        # A manifest covering fewer than the expected cells means the uncovered
        # stale cells never get a batch. That is a plan failure, not a warning
        # to print past (every other plan guard raises); require an explicit
        # --allow-partial to proceed.
        msg = ("manifest holds %d GUIDs, expected %d -- uncovered cells will "
               "never be built" % (total_guids, EXPECTED_PACKAGES))
        if not args.allow_partial:
            raise SystemExit("REFUSING: %s. Pass --allow-partial to override."
                             % msg)
        print("WARNING (--allow-partial): %s" % msg)

    # The read-back that ReportOnly actually held: nothing under Content/
    # changed. Compared on (size, mtime_ns) per package, not on a total.
    after, per_after = census()
    changed = [k for k in per_before
               if k in per_after and per_after[k] != per_before[k]]
    if changed or after["packages_present"] != before["packages_present"]:
        raise SystemExit(
            "REFUSING: -ReportOnly WROTE to the world -- %d package(s) changed,"
            " e.g. %s. Stop and diagnose before any build."
            % (len(changed), changed[:3]))
    # NN13: "0 of 0 changed" is not proof ReportOnly wrote nothing -- it is a
    # census over zero packages. Require a real sample before accepting it.
    if len(per_before) == 0:
        raise SystemExit("REFUSING: the baseline census found 0 packages; the "
                         "'wrote nothing' read-back would be over zero samples.")
    print("readback   ReportOnly wrote nothing: 0 of %d packages changed"
          % len(per_before))

    state = {
        "run_dir": run_dir,
        "batches": args.batches,
        "manifest": manifest,
        "engine_version": general.get("EngineVersion"),
        "guids_total": total_guids,
        "section_sizes": {k: len(v) for k, v in sorted(sections.items())},
        "baseline_census": before,
        "baseline_stride": stride_sample(per_before),
        "records": [],
    }
    write_state(run_dir, state)
    print("plan       OK -> %s" % os.path.join(run_dir, "batches.json"))
    return 0


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

def state_path(run_dir):
    return os.path.join(run_dir, "batches.json")


def read_state(run_dir):
    with open(state_path(run_dir), "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_state(run_dir, state):
    with open(state_path(run_dir), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


# --------------------------------------------------------------------------
# the batch loop
# --------------------------------------------------------------------------

def run_batch(state, run_dir, idx, attempt, force=True):
    """One fresh commandlet for one manifest section. Returns a record."""
    tag = "batch_%02d" % idx if attempt == 1 else "batch_%02d_retry" % idx
    log_path = os.path.join(run_dir, "%s.log" % tag)
    cmd = base_args(log_path) + ["-BuildHLODs"]
    if force:
        # NOT optional here -- the hash skip rejects cells that are stale by
        # the very setting that changed. Measured, batch 0, 2026-09-09.
        cmd.append("-RebuildHLODs")
    cmd += [
        "-BuildManifest=%s" % state["manifest"],
        "-BuilderIdx=%d" % idx,
    ]

    before, per_before = census()
    layers_before = layer_census()
    start_ns = time.time_ns()
    t0 = time.time()
    print("\n=== %s (attempt %d)%s ===" % (tag, attempt,
                                           "" if force else " [NO FORCE]"),
          flush=True)
    print("    cells in section: %d   stale(%s) now: %d"
          % (state["section_sizes"].get("HLODBuilder%d" % idx, -1),
             STALE_LAYER, layers_before.get(STALE_LAYER, 0)), flush=True)

    proc = launch(cmd)
    vram_peak, last_report = 0, 0.0
    while proc.poll() is None:
        time.sleep(VRAM_POLL_SECONDS)
        v = vram_used_mb()
        if v is not None:
            vram_peak = max(vram_peak, v)
        now = time.time()
        if now - last_report >= POLL_SECONDS:
            last_report = now
            s = scan_log(log_path)
            print("    [%5.1f min] %d/%d  approve=%d reject=%d  "
                  "vram=%s peak=%d  %s"
                  % ((now - t0) / 60.0, s["last_index"], s["total"],
                     s["approve"], s["reject"], v, vram_peak,
                     s["last_cell"] or "-"), flush=True)
            if s["fatal"]:
                print("    FATAL seen in log: %s"
                      % s["fatal"][0]["signature"], flush=True)
    exit_ns = time.time_ns()
    rc = proc.returncode
    minutes = (time.time() - t0) / 60.0

    # TRUE EXIT: the process table, not the log line and not Popen alone.
    # R-HLOD 08d -- "Engine exit requested ... result 0" was printed by three
    # runs that then held 2-4.5 GB at 0.005 cores until killed an hour later.
    deadline = time.time() + 120
    leftovers = running_editors()
    while leftovers and time.time() < deadline:
        time.sleep(5)
        leftovers = running_editors()

    s = scan_log(log_path)
    after, per_after = census()

    # TORN PACKAGES: everything written during this batch must be a whole file.
    written = [k for k, (_, mt) in per_after.items() if mt >= start_ns]
    torn = [k for k in written if per_after[k][0] < MIN_PACKAGE_BYTES]
    newest_ns = max((per_after[k][1] for k in written), default=0)
    # The gap between the last package write and process death. After build 3
    # this read 3 seconds and was the evidence that nothing was caught
    # mid-write (LESSONS 2026-09-08i). A NEGATIVE value means a package's mtime
    # is later than the process exit -- something else is writing there, and
    # that would invalidate every census below.
    write_to_exit_s = (round((exit_ns - newest_ns) / 1e9, 3)
                       if newest_ns else None)

    rec = {
        "batch": idx,
        "attempt": attempt,
        "log": os.path.relpath(log_path, REPO_ROOT).replace(os.sep, "/"),
        "returncode": rc,
        "minutes": round(minutes, 2),
        "true_exit": not leftovers,
        "leftover_processes": leftovers,
        "cells_seen": s["last_index"],
        "cells_in_batch": s["total"],
        "approve_rebuild": s["approve"],
        "reject_rebuild": s["reject"],
        "built_reported": s["built"],
        "last_cell": s["last_cell"],
        # ⭐ PER-LAYER AND PER-CELL ATTRIBUTION, from the shared module.
        # `approve_rebuild` above is a bare count and carries no cell
        # identity -- which is how "46 cells built" on 2026-09-13 told
        # nobody whether the Landscape layer had been exercised. This
        # pairs every `Building HLOD actor <layer>/<cell>` line with the
        # decision that follows it, and reports its own pairing health
        # so a desynced read cannot pass as a clean one (rule 13).
        "attribution": hlod_attribution.attribute(log_path),
        "packages_written": len(written),
        "torn_packages": torn,
        "last_write_to_exit_seconds": write_to_exit_s,
        "vram_peak_mb": vram_peak,
        "vram_at_fault_mb": s["vram_at_fault_mb"],
        "log_errors": s["log_errors"],
        "log_warnings": s["log_warnings"],
        "errors_over_baseline": (None if s["log_errors"] is None
                                 else s["log_errors"] - BASELINE_ERRORS),
        # `#### Built N ####` is a COMPLETION marker only -- the loop reached
        # the end. It counts cells VISITED, not cells built: batch 0 printed
        # "Built 191" over 191 rejections and zero geometry. Never read it as
        # progress. R-HLOD REJECTED 2026-09-09.
        "completed": s["built"] is not None,
        "fatal": s["fatal"][:5],
        "over_5mb_before": before["over_5mb"],
        "over_5mb_after": after["over_5mb"],
        "over_5mb_delta": before["over_5mb"] - after["over_5mb"],
        "census_after": after,
        "stride_after": stride_sample(per_after),
    }

    # THE READ-BACK THAT DECIDES WHETHER THIS BATCH DID ANYTHING: what the
    # cells now record about the layer they were built with. Independent of
    # the run's own log and of package bytes.
    layers_after = layer_census()
    rec["layers_before"] = layers_before
    rec["layers_after"] = layers_after
    rec["stale_before"] = layers_before.get(STALE_LAYER, 0)
    rec["stale_after"] = layers_after.get(STALE_LAYER, 0)
    rec["stale_delta"] = rec["stale_before"] - rec["stale_after"]
    rec["current_after"] = layers_after.get(CURRENT_LAYER, 0)
    print("    done rc=%d in %.1f min | approve=%d reject=%d | "
          "STALE %d -> %d (-%d), current=%d | vram peak %d MiB | "
          "true_exit=%s | written=%d torn=%d last_write_to_exit=%ss"
          % (rc, minutes, s["approve"], s["reject"],
             rec["stale_before"], rec["stale_after"], rec["stale_delta"],
             rec["current_after"], vram_peak, rec["true_exit"],
             len(written), len(torn), write_to_exit_s), flush=True)
    print(hlod_attribution.format_attribution(rec["attribution"]), flush=True)
    return rec


def commit_batch(run_dir, rec):
    """Commit this batch's log and state. Message through a FILE, always --
    standing rule 3: the fourth mangled message in one session promoted this,
    and a rule that depends on remembering which characters the shell eats is
    the weakest kind of rule.

    ONLY _verify/ paths are staged. The inflated HLOD packages under Content/
    are TRACKED stubs being rewritten in place, and committing them would put
    ~17 GB into history permanently (R-HLOD 08e).
    """
    msg_path = os.path.join(run_dir, "_commitmsg.txt")
    body = (
        "HLOD batch %02d: %d cells de-staled, %d -> %d left, %.1f min,"
        " VRAM peak %d MiB\n"
        "\n"
        "Batch %d of the ruled batched rebuild. -BuildHLODs -RebuildHLODs\n"
        "-BuilderIdx=%d against the engine-generated manifest, fresh process.\n"
        "approve=%d reject=%d  rc=%d  true_exit=%s  torn=%d\n"
        "Stale count is cells whose OWN build report still records %s.\n"
        % (rec["batch"], rec["stale_delta"], rec["stale_before"],
           rec["stale_after"], rec["minutes"], rec["vram_peak_mb"],
           rec["batch"], rec["batch"], rec["approve_rebuild"],
           rec["reject_rebuild"], rec["returncode"], rec["true_exit"],
           len(rec["torn_packages"]), STALE_LAYER))
    if rec["fatal"]:
        body += "\nFATAL: %s\n  in flight: %s\n" % (
            rec["fatal"][0]["signature"], rec["last_cell"])
    with open(msg_path, "w", encoding="utf-8") as fh:
        fh.write(body)
    rel = os.path.relpath(run_dir, REPO_ROOT).replace(os.sep, "/")
    subprocess.run(["git", "add", "--", rel], cwd=REPO_ROOT, check=False)
    cp = subprocess.run(["git", "commit", "-F", msg_path],
                        cwd=REPO_ROOT, capture_output=True, text=True)
    # Surface a failed commit rather than discarding it: the audit-trail commit
    # this promises would otherwise silently not happen (state is still on disk
    # via write_state, so a resume works, but the operator must know).
    if cp.returncode != 0:
        print("    WARNING: batch %d commit did not succeed (rc=%d): %s"
              % (rec["batch"], cp.returncode,
                 (cp.stderr or cp.stdout or "").strip().splitlines()[-1:]),
              flush=True)


def stop_requested(run_dir):
    """True if someone dropped a STOP file in the run dir.

    WHY A FILE AND NOT A SIGNAL: pausing this loop used to mean killing the
    driver and whatever commandlet had just started, which costs the cell in
    flight and then needs a torn-package census to prove it cost nothing more.
    A file checked BETWEEN batches stops at the only moment where there is
    provably nothing half-written -- the previous batch is committed and the
    next process has not launched.

        touch _verify/hlod/<run>/STOP
    """
    return os.path.exists(os.path.join(run_dir, "STOP"))


def cmd_run(args, run_dir):
    state = read_state(run_dir)
    editors = running_editors()
    if editors:
        raise SystemExit("REFUSING: UnrealEditor already running: %s" % editors)
    if stop_requested(run_dir):
        raise SystemExit("REFUSING: STOP file present in %s. Remove it to run."
                         % run_dir)

    indices = ([args.only] if args.only is not None
               else list(range(args.start, state["batches"])))

    for idx in indices:
        # Checked BETWEEN batches only: the previous batch is committed and no
        # commandlet is running, so a pause here writes nothing and costs
        # nothing. Never mid-batch.
        if stop_requested(run_dir):
            print("\nSTOP file seen -- pausing cleanly before batch %d.\n"
                  "Resume with: run --start %d" % (idx, idx), flush=True)
            break
        attempt = 1
        while True:
            rec = run_batch(state, run_dir, idx, attempt,
                            force=not args.no_force)
            state["records"].append(rec)
            write_state(run_dir, state)
            commit_batch(run_dir, rec)

            if rec["torn_packages"]:
                raise SystemExit(
                    "STOP: %d torn package(s) after batch %d: %s"
                    % (len(rec["torn_packages"]), idx,
                       rec["torn_packages"][:3]))
            if not rec["true_exit"]:
                raise SystemExit(
                    "STOP: batch %d did not truly exit; live: %s"
                    % (idx, rec["leftover_processes"]))
            w2e = rec["last_write_to_exit_seconds"]
            if w2e is not None and w2e < 0:
                raise SystemExit(
                    "STOP: a package under __ExternalActors__ was written %.3f s"
                    " AFTER batch %d's process exited. Something other than "
                    "this build is writing there; every census below is void."
                    % (-w2e, idx))
            # NOT rc != 0 -- see BASELINE_ERRORS. A batch failed if the
            # builder never printed its own completion marker, or a fatal
            # signature appeared, or it logged more errors than the machine's
            # standing baseline of two port-8000 bind failures.
            #
            # AND NOT the "Built N" marker on its own -- it counts cells
            # VISITED. The batch is only a success if the ARTEFACT moved: the
            # number of cells recording the stale layer must have fallen.
            # A forced batch containing Merged cells that de-stales none of
            # them has done nothing, however cleanly it exited.
            over = rec["errors_over_baseline"]
            # ⚠ KNOWN LIMITATION (Pass 3 2026-09-18, OPEN item): stale_before/
            # stale_delta come from layer_census(), which counts the WHOLE WORLD,
            # not this batch's section. So a batch whose section held ZERO stale
            # cells (all already current) leaves the whole-world stale count
            # unchanged while OTHER batches keep it > 0 -> did_nothing fires and
            # can HALT a batch that actually built cleanly. A correct test must
            # scope stale to this section's GUIDs (sections["HLODBuilder%d"]);
            # that needs a GUID->package map and a live editor to verify, so it
            # is deferred rather than rewritten blind here.
            did_nothing = (not args.no_force and rec["stale_before"] > 0
                           and rec["stale_delta"] <= 0)
            failed = (rec["fatal"] or not rec["completed"] or did_nothing
                      or (over is not None and over > 0))
            if failed:
                why = (rec["fatal"][0]["signature"] if rec["fatal"]
                       else "no completion marker" if not rec["completed"]
                       else "stale count did not fall (%d -> %d)"
                       % (rec["stale_before"], rec["stale_after"])
                       if did_nothing
                       else "%d errors over baseline" % over)
                if attempt == 1:
                    print("    FAILED batch %d (%s). Retrying ONCE, fresh "
                          "process." % (idx, why), flush=True)
                    attempt = 2
                    continue
                raise SystemExit(
                    "STOP: batch %d failed TWICE. Cell in flight: %s. "
                    "Reason: %s. VRAM at fault: %s MiB. Peak VRAM: %s MiB."
                    % (idx, rec["last_cell"], why, rec["vram_at_fault_mb"],
                       rec["vram_peak_mb"]))
            break

    final, per_final = census()
    layers = layer_census()
    print("\nFINAL size census:  %s" % json.dumps(final))
    print("FINAL layer census: %s" % json.dumps(layers))
    print("stride: %s" % json.dumps(stride_sample(per_final), indent=2))
    stale = layers.get(STALE_LAYER, 0)
    no_report = layers.get("<no report>", 0)
    current = layers.get(CURRENT_LAYER, 0)
    # NN13: stale==0 is satisfied both when every cell is CURRENT and when every
    # report was unreadable ("<no report>"). Require POSITIVE confirmation --
    # zero unreadable reports and the current-layer count accounting for the
    # present packages -- before declaring the world uniform.
    uniform = (stale == 0 and final["packages_missing"] == 0
               and no_report == 0
               and current == final["packages_present"])
    if uniform:
        print("\nWORLD UNIFORM: all %d present packages record %s, none stale, "
              "none unreadable." % (current, CURRENT_LAYER))
    else:
        print("\nNOT DONE: %d cells record %s; %d packages missing; %d reports "
              "unreadable; %d current of %d present."
              % (stale, STALE_LAYER, final["packages_missing"], no_report,
                 current, final["packages_present"]))
    state["final_census"] = final
    state["final_layers"] = layers
    state["final_stride"] = stride_sample(per_final)
    write_state(run_dir, state)
    # A full run (not --only) that did not reach a uniform world must not exit 0
    # -- a caller/hook keying on the code was silently told success. A single
    # --only batch legitimately does not finish the world, so keep 0 there.
    if args.only is None and not uniform:
        return 1
    return 0


def cmd_census(args, run_dir):
    summary, per = census()
    print(json.dumps(summary, indent=2))
    print(json.dumps(stride_sample(per, args.batches), indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["census", "plan", "run"])
    ap.add_argument("--batches", type=int, default=12,
                    help="manifest sections; 2267/12 = ~189 cells each")
    ap.add_argument("--start", type=int, default=0,
                    help="first batch index for `run`")
    ap.add_argument("--only", type=int, default=None,
                    help="run exactly one batch index")
    ap.add_argument("--no-force", action="store_true",
                    help="drop -RebuildHLODs. Only for re-testing the skip: "
                         "measured 2026-09-09 it rejects cells that are stale "
                         "by the setting that changed, and does nothing.")
    ap.add_argument("--run-dir", default=None,
                    help="default _verify/hlod/<YYYYMMDD>")
    ap.add_argument("--allow-partial", action="store_true",
                    help="let `plan` proceed when the manifest covers fewer "
                         "than the expected cells (uncovered stale cells then "
                         "never get a batch -- a claim you own).")
    args = ap.parse_args(argv)

    run_dir = args.run_dir or os.path.join(
        REPO_ROOT, "_verify", "hlod", time.strftime("%Y%m%d"))
    os.makedirs(run_dir, exist_ok=True)

    return {"census": cmd_census, "plan": cmd_plan,
            "run": cmd_run}[args.command](args, run_dir)


if __name__ == "__main__":
    sys.exit(main())
