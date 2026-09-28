"""nanite_batch_build.py — build landscape Nanite in BOUNDED, RESUMABLE batches.

MUTATES actor properties, builds Nanite meshes, and SAVES. Bare invocation is a
DRY RUN.

=====================================================================
WHY THIS EXISTS ALONGSIDE landscape_nanite_build.py
=====================================================================
That script calls `build_landscape_nanite`, which hands the subsystem an EMPTY
TArrayView. Empty means BUILD EVERY REGISTERED PROXY
(LandscapeSubsystem.cpp:1124-1133). On this project's 8129 landscape that is 256
proxies, and the failure is not a slow build -- it is an OOM kill.

THE MECHANISM, read at source rather than inferred from the crash.
ULandscapeSubsystem::BuildNanite loops over every proxy calling
UpdateNaniteRepresentationAsync and only THEN blocks on
FinishAllNaniteBuildsInFlightNow (LandscapeSubsystem.cpp:1159-1181). Every
proxy's static-mesh build is therefore in flight AT ONCE. The editor died at
PeakUsedVirtual 115.47 GiB with the first few proxies still committing, which is
exactly the shape that predicts: memory is set by how many builds are DISPATCHED,
not by how many have finished.

THE ENGINE'S OWN THROTTLE IS DEAD CODE IN 5.8 -- do not reach for it instead.
`landscape.Nanite.MaxSimultaneousMultithreadBuilds` (LandscapeSubsystem.cpp:95)
is read only by WaitLaunchNaniteBuild (:1583), whose ONLY call site in the whole
Landscape module is commented out at LandscapeNaniteComponent.cpp:273 --
"TODO [chris.tchou]: this can deadlock, any waits should be done outside of
async tasks". Bounding the SUBMITTED SET is the only lever the engine leaves,
which is why the plugin exposes the batch parameter.

=====================================================================
WHY force_rebuild IS FALSE, AND WHY THAT IS THE WHOLE RESUME STORY
=====================================================================
LandscapeSubsystem.cpp:1157 drops already-built proxies from the work list:

    RemoveIf(... (InProxy == nullptr) || (!bForceRebuild && InProxy->IsNaniteMeshUpToDate()))

The `!bForceRebuild` is load-bearing. With force ON, every proxy rebuilds and a
crash at proxy 200 costs all 200 again. With force OFF, a re-run skips what is
already built, so a crash costs ONE BATCH. `landscape_nanite_build.py` passes
True -- correct for a first full build, wrong for a resumable one.

=====================================================================
WHAT "DONE" MEANS HERE, AND WHY THE COUNT IS NOT THE PROOF
=====================================================================
IsNaniteMeshUpToDate() returns TRUE for a proxy with Nanite DISABLED and for one
with NO landscape components (Landscape.cpp:443-456). It is a scheduling
predicate, not evidence of a mesh. So this script never reports progress from
it. Completion is measured by a DIFFERENT REPRESENTATION: a
LandscapeNaniteComponent that actually holds a static mesh (non-negotiable 8).
The parent ALandscape of a World Partition grid owns no components and is
EXPECTED to have no mesh -- it is excluded from the denominator, not counted as a
failure.

=====================================================================
MEMORY IS MEASURED, NOT ASSUMED
=====================================================================
The whole point of batching is a memory bound, so an unmeasured bound is no
bound. Between batches this reads the editor process's PEAK counters, which are
lifetime highs the OS maintains -- so a peak reached DURING a batch is still
readable AFTER it, without sampling. Rising peaks across batches would mean the
build accumulates and the batch size must come down; flat peaks mean the bound
holds. That question was explicitly UNKNOWN going in.

Exit codes:
  0  every proxy in scope has a built Nanite mesh
  1  could not look
  2  refused before touching anything
  3  rule 7: no verified editor node
  5  a batch failed, or a flag did not read back
  6  the run stopped early with batches remaining (resumable; re-run)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_NB__"

# ---------------------------------------------------------------------------
# ONE DECLARATION of "does this proxy carry a built Nanite mesh?", injected into
# every payload that asks. Two payloads spelling this themselves is the shape
# non-negotiable 24 forbids -- and the wrong spelling does not raise, it returns
# a confident ZERO.
#
# MEASURED 2026-08-13, and it cost a false verdict. The SINGULAR
# `get_component_by_class(LandscapeNaniteComponent)` + `get_static_mesh()`
# returned None for all 256 proxies at a moment when the saved packages on disk
# demonstrably held 256 Nanite meshes (3.03 GB across 256 external actor
# packages). The PLURAL `get_components_by_class` + the reflected property
# `static_mesh` reads 256/256 on the same world in the same state. This is
# non-negotiable 23: the singular form is a plausible accessor that exists and
# answers wrongly here, which is worse than one that raises.
# ---------------------------------------------------------------------------
MESH_CHECK = r'''
def _has_built_mesh(_a):
    import unreal as _u
    try:
        for _c in list(_a.get_components_by_class(_u.LandscapeNaniteComponent)):
            if _c.get_editor_property("static_mesh") is not None:
                return True
    except Exception:
        return False
    return False
'''

# ---------------------------------------------------------------------------
# Phase A. Prove the binding exists AND that its empty-list gate REFUSES.
#
# Non-negotiable 2: a gate that has only seen good input has not been tested.
# The empty-list case is the one that matters most here, because an empty list
# is precisely the value that means "build all 256" to the subsystem -- the
# catastrophic value this whole tool exists to avoid. Testing it is free: a
# refusal touches nothing.
# ---------------------------------------------------------------------------
PAYLOAD_PROBE = r'''
import json as _json
import unreal as _unreal

_out = {"error": None, "has_binding": False, "empty_refused": None,
        "empty_error": None, "arity": None}
try:
    _fn = getattr(_unreal.LandscapeLabTools, "build_landscape_nanite_for_proxies", None)
    _out["has_binding"] = _fn is not None
    if _fn is not None:
        # POSITIVE CONTROL FIRST. An empty batch must be REFUSED, not expanded.
        _r = _fn([], False)
        _out["arity"] = len(_r) if isinstance(_r, tuple) else -1
        # (submitted, already_up_to_date, success, error)
        _out["empty_refused"] = (not bool(_r[2]))
        _out["empty_error"] = str(_r[3])[:400]
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NB__" + _json.dumps(_out))
'''

# ---------------------------------------------------------------------------
# Phase B. Set the flags, read them back, and enumerate the batch scope.
#
# Read-back before building is not ceremony: UpdateNaniteRepresentationAsync's
# entire body is behind IsNaniteEnabled() (Landscape.cpp:465), so a build over
# actors whose flag did not land returns SUCCESS and produces NOTHING.
#
# Scope is LandscapeStreamingProxy specifically. ALandscape SUBCLASSES
# LandscapeProxy, so an isinstance check on the base class would sweep the
# parent into a batch -- and the subsystem expands a parent to all of its
# streaming proxies (LandscapeSubsystem.cpp:1140-1147), silently turning a batch
# of 8 into a batch of 256. The plugin refuses that; this avoids relying on the
# refusal.
# ---------------------------------------------------------------------------
PAYLOAD_SETUP = r'''
import json as _json
import unreal as _unreal

_enable = __ENABLE__
_skirt = __SKIRT__
_skirt_depth = __SKIRT_DEPTH__

_out = {"error": None, "level": None, "touched": 0, "unreadable": 0,
        "enabled_after": 0, "skirt_after": 0}
try:
    _out["level"] = _unreal.EditorLevelLibrary.get_editor_world().get_path_name()
    _all = _unreal.EditorLevelLibrary.get_all_level_actors()
    _streaming = [a for a in _all if isinstance(a, _unreal.LandscapeStreamingProxy)]
    _parents = [a for a in _all
                if isinstance(a, _unreal.Landscape)
                and not isinstance(a, _unreal.LandscapeStreamingProxy)]

    # SETTING THESE PROPERTIES IS ITSELF A BUILD DISPATCH -- this is the finding
    # that makes the batch parameter insufficient on its own.
    # ALandscapeProxy::PostEditChangeProperty calls
    # InvalidateOrUpdateNaniteRepresentation for bEnableNanite, bNaniteSkirtEnabled
    # AND NaniteSkirtDepth (LandscapeEdit.cpp:6131-6141). So flagging N proxies
    # queues N builds before BuildNanite is called at all, and
    # FinishAllNaniteBuildsInFlightNow then waits on every one of them
    # (LandscapeSubsystem.cpp:1179). MEASURED: flagging 257 actors and then
    # submitting a batch of 8 built all 256 proxies and drove system commit to
    # 189 GB. To bound memory the FLAGGING must be batched too, not just the
    # build call.
    for _a in _streaming + _parents:
        try:
            _a.set_editor_property("enable_nanite", _enable)
            if _skirt:
                _a.set_editor_property("nanite_skirt_enabled", True)
                _a.set_editor_property("nanite_skirt_depth", _skirt_depth)
            _out["touched"] += 1
        except Exception:
            _out["unreadable"] += 1

    for _a in _streaming + _parents:
        try:
            if bool(_a.get_editor_property("enable_nanite")):
                _out["enabled_after"] += 1
            if bool(_a.get_editor_property("nanite_skirt_enabled")):
                _out["skirt_after"] += 1
        except Exception:
            _out["unreadable"] += 1

    del _all, _streaming, _parents
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NB__" + _json.dumps(_out))
'''

# ---------------------------------------------------------------------------
# READ-ONLY enumeration. Separate from PAYLOAD_SETUP on purpose.
#
# The first version of this tool reused the SETTING payload to take its final
# verdict, which re-fired PostEditChangeProperty on all 257 actors -- a check
# that mutates the state it is reporting on (non-negotiable 5). This payload
# sets nothing.
# ---------------------------------------------------------------------------
PAYLOAD_READ = r'''
import json as _json
import unreal as _unreal
__MESH_CHECK__

_out = {"error": None, "level": None, "proxies": [], "parent_count": 0,
        "parent_with_mesh": 0, "enabled": 0}
try:
    _out["level"] = _unreal.EditorLevelLibrary.get_editor_world().get_path_name()
    _all = _unreal.EditorLevelLibrary.get_all_level_actors()
    _streaming = [a for a in _all if isinstance(a, _unreal.LandscapeStreamingProxy)]
    _parents = [a for a in _all
                if isinstance(a, _unreal.Landscape)
                and not isinstance(a, _unreal.LandscapeStreamingProxy)]
    _out["parent_count"] = len(_parents)

    # The parent of a World Partition grid owns no landscape components, so it is
    # EXPECTED to carry no mesh (Landscape.cpp:465 skips the body). Counted with
    # the same accessor as the proxies so the two numbers are comparable, and
    # reported rather than silently excluded.
    for _a in _parents:
        if _has_built_mesh(_a):
            _out["parent_with_mesh"] += 1

    # Stable, sorted order so batch N is the SAME set on a resume.
    _rows = []
    for _a in _streaming:
        try:
            if bool(_a.get_editor_property("enable_nanite")):
                _out["enabled"] += 1
        except Exception:
            pass
        _rows.append({"path": _a.get_path_name(), "mesh": _has_built_mesh(_a)})
    _rows.sort(key=lambda r: r["path"])
    _out["proxies"] = _rows
    del _all, _streaming, _parents
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NB__" + _json.dumps(_out))
'''

# ---------------------------------------------------------------------------
# Phase C. Build ONE batch, then measure the result with a different instrument.
#
# Actors are re-resolved by path name every batch rather than held across calls:
# a stale reference would arrive at the plugin as a null, and the subsystem drops
# nulls silently (LandscapeSubsystem.cpp:1156). The plugin refuses nulls, but the
# cheaper fix is not to manufacture them.
# ---------------------------------------------------------------------------
PAYLOAD_BATCH = r'''
import json as _json
import unreal as _unreal
__MESH_CHECK__

_want = __PATHS__
_force = __FORCE__

_out = {"error": None, "resolved": 0, "missing": [], "submitted": 0,
        "already": 0, "ok": None, "build_error": None, "with_mesh": 0,
        "mesh_paths": []}
try:
    _by_path = {}
    for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_a, _unreal.LandscapeStreamingProxy):
            _by_path[_a.get_path_name()] = _a

    _batch = []
    for _p in _want:
        _a = _by_path.get(_p)
        if _a is None:
            _out["missing"].append(_p)
        else:
            _batch.append(_a)
    _out["resolved"] = len(_batch)

    if _out["missing"]:
        _out["error"] = "REFUSED: %d of %d proxy paths did not resolve." % (
            len(_out["missing"]), len(_want))
    else:
        _sub, _up, _ok, _err = _unreal.LandscapeLabTools.build_landscape_nanite_for_proxies(
            _batch, _force)
        _out["submitted"] = int(_sub)
        _out["already"] = int(_up)
        _out["ok"] = bool(_ok)
        _out["build_error"] = (str(_err) or None) if _err else None

        # DIFFERENT INSTRUMENT. Not IsNaniteMeshUpToDate -- that returns True for
        # a Nanite-disabled proxy and for one with no components
        # (Landscape.cpp:443-456). Ask whether a mesh OBJECT exists.
        for _a in _batch:
            if _has_built_mesh(_a):
                _out["with_mesh"] += 1
                _out["mesh_paths"].append(_a.get_path_name())
    del _by_path
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NB__" + _json.dumps(_out))
'''

# ---------------------------------------------------------------------------
# Phase D. Save. Reports a COUNT, never the package list -- a 256-entry reply is
# how save_level lost its own result to the transport limit (LESSONS 2026-08-09).
# ---------------------------------------------------------------------------
PAYLOAD_SAVE = r'''
import json as _json
import unreal as _unreal

_out = {"error": None, "saved": None, "dirty_before": 0}
try:
    _pkgs = [p for p in _unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _pkgs += [p for p in _unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _out["dirty_before"] = len(_pkgs)
    _out["saved"] = bool(
        _unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    del _pkgs
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NB__" + _json.dumps(_out))
'''


def _mem_snapshot(pid: int | None) -> dict:
    """Editor process peaks + system commit. Peaks are OS-maintained LIFETIME
    highs, so a peak reached inside a batch is still readable after it -- no
    sampler needed. Returns None fields rather than zeros when it cannot look
    (non-negotiable 6)."""
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$o=Get-CimInstance Win32_OperatingSystem;"
        "$commit=[math]::Round(($o.TotalVirtualMemorySize-$o.FreeVirtualMemory)/1024);"
        "$limit=[math]::Round($o.TotalVirtualMemorySize/1024);"
        "$freephys=[math]::Round($o.FreePhysicalMemory/1024);"
        "$p=$null; if (%s -gt 0) { $p=Get-Process -Id %s }"
        "$ws=$null;$pws=$null;$pvm=$null;$ppf=$null;"
        "if ($p) { $ws=[math]::Round($p.WorkingSet64/1MB);"
        "$pws=[math]::Round($p.PeakWorkingSet64/1MB);"
        "$pvm=[math]::Round($p.PeakVirtualMemorySize64/1MB);"
        "$ppf=[math]::Round($p.PeakPagedMemorySize64/1MB) }"
        "@{commit_mb=$commit;commit_limit_mb=$limit;free_phys_mb=$freephys;"
        "ws_mb=$ws;peak_ws_mb=$pws;peak_virtual_mb=$pvm;peak_commit_mb=$ppf}"
        "|ConvertTo-Json -Compress"
    ) % (pid or 0, pid or 0)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout.strip())
    except Exception as e:
        return {"could_not_look": "%s: %s" % (type(e).__name__, e)}


def _fmt_mem(m: dict) -> str:
    if m.get("could_not_look"):
        return "COULD NOT MEASURE (%s)" % m["could_not_look"]
    def g(k):
        v = m.get(k)
        return "n/a" if v is None else "%d" % v
    return ("commit %s/%s MB  free phys %s MB  editor ws %s MB  "
            "PEAK ws %s / commit %s / virtual %s MB"
            % (g("commit_mb"), g("commit_limit_mb"), g("free_phys_mb"), g("ws_mb"),
               g("peak_ws_mb"), g("peak_commit_mb"), g("peak_virtual_mb")))


class Session:
    """One command connection, held for the whole run. Nothing else may touch the
    editor while this is open -- the second client wins silently (LESSONS
    2026-08-10)."""

    def __init__(self, timeout: int):
        self.remote_exec = bootstrap._load_remote_execution()
        self.remote = self.remote_exec.RemoteExecution()
        self.timeout = timeout
        self.node = None

    def __enter__(self):
        self.remote.start()
        node, reason = verify_landscape._select_verified_node(
            self.remote_exec, self.remote,
            bootstrap._norm(bootstrap.UE_PROJECT_ROOT), self.timeout)
        if node is None:
            self.remote.stop()
            raise RuntimeError("rule 7: %s" % reason)
        self.node = node
        self.remote.open_command_connection(node["node_id"])
        return self

    def __exit__(self, *exc):
        try:
            self.remote.stop()
        except Exception:
            pass
        return False

    def run(self, payload: str) -> dict:
        r = self.remote.run_command(payload, unattended=True,
                                    exec_mode=self.remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            return {"error": "NO MARKER — could not look.", "_raw": text[:2000]}
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
        return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch-size", type=int, default=8,
                    help="proxies submitted per call. THE MEMORY BOUND. Default 8.")
    ap.add_argument("--max-batches", type=int, default=0,
                    help="stop after N batches (0 = all). Use to measure before committing.")
    ap.add_argument("--skirt-depth", type=float, default=1.0)
    ap.add_argument("--no-skirt", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="force rebuild. BREAKS RESUMABILITY -- the engine only skips "
                         "already-built proxies when NOT forcing (LandscapeSubsystem.cpp:1157).")
    ap.add_argument("--save-every", type=int, default=1,
                    help="save after every N batches. 0 = never (progress dies with a crash).")
    ap.add_argument("--editor-pid", type=int, default=0,
                    help="editor PID, so memory can be attributed to the process")
    ap.add_argument("--timeout", type=int, default=25,
                    help="node discovery window. 25 per CLAUDE.md; the 6s default is "
                         "unreliable on this machine.")
    ap.add_argument("--verify-only", action="store_true",
                    help="READ-ONLY. Report how many proxies carry a built Nanite "
                         "mesh and exit. Sets nothing -- safe to run at any time, "
                         "including against a build in progress.")
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and changes nothing")
    args = ap.parse_args(argv)

    if args.verify_only:
        with Session(args.timeout) as s:
            d = s.run(PAYLOAD_READ.replace("__MESH_CHECK__", MESH_CHECK))
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1
        rows = d.get("proxies", [])
        with_mesh = sum(1 for r in rows if r["mesh"])
        print("=== VERIFY (read-only) ===")
        print("  level                  %s" % d.get("level"))
        print("  streaming proxies      %d" % len(rows))
        print("  enable_nanite true     %d" % d.get("enabled", 0))
        print("  carrying a built mesh  %d" % with_mesh)
        print("  parent ALandscape      %d (carrying a mesh: %d — expected 0)"
              % (d.get("parent_count", 0), d.get("parent_with_mesh", 0)))
        if not rows:
            print("REFUSED: no LandscapeStreamingProxy actors found.")
            return 2
        if with_mesh != len(rows):
            print("\n%d proxies have NO built Nanite mesh." % (len(rows) - with_mesh))
            return 6
        print("\nEvery streaming proxy carries a built Nanite mesh.")
        return 0

    if args.batch_size < 1:
        print("REFUSED: --batch-size must be >= 1. Zero or negative would mean an "
              "empty list, which the subsystem reads as BUILD ALL 256.")
        return 2

    print("=== PLAN ===")
    print("  batch size          %d proxies per submission" % args.batch_size)
    print("  force rebuild       %s%s" % (args.force,
          "   <- NOT RESUMABLE" if args.force else "   (resumable)"))
    print("  skirt               %s  depth %.2f" % (not args.no_skirt, args.skirt_depth))
    print("  save every          %s" % (args.save_every or "never"))
    print("  max batches         %s" % (args.max_batches or "all"))
    print()
    if not args.go:
        print("DRY RUN. Nothing was contacted. Re-run with --go.")
        return 0

    pid = args.editor_pid or None
    print("MEMORY BEFORE ANYTHING:", _fmt_mem(_mem_snapshot(pid)))
    print()

    t_start = time.time()
    with Session(args.timeout) as s:
        # ---- Phase A: binding + gate -------------------------------------
        print("=== PHASE A — binding present, and does its gate REFUSE? ===")
        d = s.run(PAYLOAD_PROBE)
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1
        if not d.get("has_binding"):
            print("build_landscape_nanite_for_proxies is NOT reflected in this editor.")
            print("The module did not load, or the editor predates the rebuild.")
            return 2
        print("  binding present     yes")
        print("  return arity        %s (expected 4)" % d.get("arity"))
        if d.get("arity") != 4:
            print("REFUSED: unexpected arity. Do not guess the out-param order.")
            return 2
        if not d.get("empty_refused"):
            print("REFUSED: the empty-batch gate ADMITTED an empty list. That value "
                  "means BUILD ALL 256 to the subsystem. Stopping.")
            return 2
        print("  empty batch         REFUSED, correctly")
        print("  refusal said        %s" % (d.get("empty_error") or "")[:160])
        print()

        # ---- Phase B: flags + scope --------------------------------------
        print("=== PHASE B — flags, read-back, and scope ===")
        setup = (PAYLOAD_SETUP
                 .replace("__ENABLE__", "True")
                 .replace("__SKIRT__", repr(bool(not args.no_skirt)))
                 .replace("__SKIRT_DEPTH__", repr(float(args.skirt_depth))))
        read = PAYLOAD_READ.replace("__MESH_CHECK__", MESH_CHECK)
        d = s.run(setup)
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1
        scope = s.run(read)
        if scope.get("error"):
            print("PAYLOAD ERROR:", scope["error"])
            return 1
        proxies = scope.get("proxies", [])
        print("  level               %s" % d.get("level"))
        print("  streaming proxies   %d" % len(proxies))
        print("  parent ALandscape   %d (carrying a mesh: %s — expected 0, excluded "
              "from the batch scope)"
              % (scope.get("parent_count", 0), scope.get("parent_with_mesh")))
        print("  actors touched      %d" % d.get("touched", 0))
        print("  enable_nanite after %d" % d.get("enabled_after", 0))
        print("  skirt after         %d" % d.get("skirt_after", 0))
        print("  unreadable          %d" % d.get("unreadable", 0))
        if d.get("enabled_after", 0) != d.get("touched", 0):
            print("REFUSED: enable_nanite did not read back on every actor. A build "
                  "over an unflagged proxy returns success and builds nothing "
                  "(Landscape.cpp:465).")
            return 5
        if not proxies:
            print("REFUSED: no LandscapeStreamingProxy actors found.")
            return 2

        todo = [p["path"] for p in proxies if not p["mesh"]]
        done_already = len(proxies) - len(todo)
        print("  already have a mesh %d" % done_already)
        print("  TO BUILD            %d" % len(todo))
        print()
        if not todo:
            print("Every streaming proxy already carries a built Nanite mesh.")
            return 0

        batches = [todo[i:i + args.batch_size]
                   for i in range(0, len(todo), args.batch_size)]
        if args.max_batches:
            batches = batches[:args.max_batches]
        print("=== PHASE C — %d batches of up to %d ===" % (len(batches), args.batch_size))
        print()

        built_total = 0
        peak_hi = 0
        for bi, batch in enumerate(batches, 1):
            t0 = time.time()
            payload = (PAYLOAD_BATCH
                       .replace("__MESH_CHECK__", MESH_CHECK)
                       .replace("__PATHS__", json.dumps(batch))
                       .replace("__FORCE__", repr(bool(args.force))))
            r = s.run(payload)
            dt = time.time() - t0

            if r.get("error"):
                print("BATCH %d/%d FAILED: %s" % (bi, len(batches), r["error"]))
                print("Resumable: re-run and already-built proxies are skipped.")
                return 5
            if not r.get("ok"):
                print("BATCH %d/%d refused by the plugin: %s"
                      % (bi, len(batches), r.get("build_error")))
                return 5

            built_total += r.get("with_mesh", 0)
            mem = _mem_snapshot(pid)
            pk = mem.get("peak_commit_mb") or 0
            rise = pk - peak_hi if peak_hi else 0
            peak_hi = max(peak_hi, pk)

            print("BATCH %2d/%d  submitted %2d  already %2d  WITH MESH %2d/%d  %6.1fs"
                  % (bi, len(batches), r.get("submitted", 0), r.get("already", 0),
                     r.get("with_mesh", 0), len(batch), dt))
            print("            %s" % _fmt_mem(mem))
            if rise > 0:
                print("            peak commit ROSE %d MB this batch" % rise)
            if r.get("with_mesh", 0) != len(batch):
                print("            NOTE: %d of %d in this batch have no mesh object."
                      % (len(batch) - r.get("with_mesh", 0), len(batch)))

            if args.save_every and (bi % args.save_every == 0):
                ts = time.time()
                sv = s.run(PAYLOAD_SAVE)
                if sv.get("error"):
                    print("            SAVE could not look: %s" % sv["error"])
                else:
                    print("            saved %s (%d dirty) in %.1fs"
                          % (sv.get("saved"), sv.get("dirty_before", 0), time.time() - ts))
            sys.stdout.flush()

        # ---- Phase E: verdict from a fresh full read ----------------------
        print()
        print("=== VERDICT ===")
        # READ-ONLY. Never the setting payload: re-firing PostEditChangeProperty
        # would invalidate the very meshes being counted.
        d2 = s.run(read)
        final = d2.get("proxies", [])
        with_mesh = sum(1 for p in final if p["mesh"])
        print("  streaming proxies         %d" % len(final))
        print("  enable_nanite true        %d" % d2.get("enabled", 0))
        print("  carrying a built mesh     %d" % with_mesh)
        print("  elapsed                   %.1f min" % ((time.time() - t_start) / 60.0))
        print("  highest peak commit seen  %d MB" % peak_hi)
        print()

        if args.max_batches and with_mesh < len(final):
            print("STOPPED EARLY by --max-batches, %d proxies remain. Re-run to continue; "
                  "built proxies are skipped." % (len(final) - with_mesh))
            return 6
        if with_mesh != len(final):
            print("%d proxies still have NO built Nanite mesh." % (len(final) - with_mesh))
            return 6
        print("Every streaming proxy carries a built Nanite mesh.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
