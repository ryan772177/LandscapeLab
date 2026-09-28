"""build_navmesh_chunk.py — build the navmesh, headless, with the bars enforced.

PHASE2_PLAN unit 8. Runs `WorldPartitionNavigationDataBuilder` through the
`WorldPartitionBuilderCommandlet` and measures what the unit asks for:
package bytes on disk, wall clock, and PEAK COMMIT.

WHY A SEPARATE PROCESS AND NOT THE EDITOR
    The builder writes external actor packages. An editor holding those
    packages open is the `unable to unlink old ... Invalid argument` class
    this project already paid for during the density revert. So this
    REFUSES to start while an editor is running, rather than discovering
    the conflict halfway through.

WHY PEAK COMMIT AND NOT WORKING SET
    The Nanite landscape build reached 196.8 GB of COMMIT against 176.6 GB
    of editor private bytes; commit is what actually ran out. Sampled from
    GlobalMemoryStatusEx's ullTotalPageFile / ullAvailPageFile, which is
    the same measure behind this project's recorded 189 GB / 228.8 GB.

THE ABORT BARS ARE ENFORCED, NOT PRINTED
    > 200 GB peak commit or > 30 minutes kills the build. A bar that is
    only reported is a bar that gets discovered afterwards.

Exit codes:
    0  the builder ran clean inside both bars (packages may be new, changed,
       or UNCHANGED if the navmesh was already current -- see the RESULT note);
       --go absent is a DRY RUN and also returns 0 having launched nothing
    2  bad arguments, or an editor is running
    4  ABORTED on a bar, OR the commit bar could not be enforced (every memory
       sample was unreadable, so the abort bar never had a value to test)
    5  the commandlet exited non-zero

NOTE: despite the name this builds the navmesh for the WHOLE --map (default
/Game/Alpine8K) via WorldPartitionNavigationDataBuilder -- there is no
chunk/tile parameter.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap        # noqa: E402
import resource_guard   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
UPROJECT = os.path.join(bootstrap.UE_PROJECT_ROOT, "LandscapeLab.uproject")
CMD_EXE = r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
EXT_ACTORS = os.path.join(bootstrap.UE_PROJECT_ROOT, "Content",
                          "__ExternalActors__")


class _MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def commit_gb():
    """(used_commit_gb, commit_limit_gb) or (None, None) if unreadable.

    None rather than 0: a memory reading that says "0" when it could not
    look would silence the bar it exists to enforce.
    """
    try:
        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None, None
        total = st.ullTotalPageFile / (1024.0 ** 3)
        avail = st.ullAvailPageFile / (1024.0 ** 3)
        return total - avail, total
    except Exception:
        return None, None


def editor_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe"],
                             capture_output=True, text=True).stdout
        return "UnrealEditor.exe" in out
    except Exception:
        # Cannot look -> refuse. A conflicting write is worse than a stall.
        return True


def snapshot(root):
    """path -> size, for every .uasset under root."""
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".uasset"):
                p = os.path.join(dirpath, f)
                try:
                    out[p] = os.path.getsize(p)
                except OSError:
                    pass
    return out


class Sampler(threading.Thread):
    def __init__(self, period=2.0):
        threading.Thread.__init__(self)
        self.daemon = True
        self.period = period
        self.peak_commit = 0.0
        self.limit = None
        self.min_free_phys = None
        self.stop_flag = threading.Event()
        self.unreadable = 0

    def run(self):
        while not self.stop_flag.is_set():
            used, limit = commit_gb()
            if used is None:
                self.unreadable += 1
            else:
                self.peak_commit = max(self.peak_commit, used)
                self.limit = limit
            free, _tot = resource_guard.available_gb()
            if free is not None:
                self.min_free_phys = (free if self.min_free_phys is None
                                      else min(self.min_free_phys, free))
            self.stop_flag.wait(self.period)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", default="/Game/Alpine8K")
    ap.add_argument("--builder", default="WorldPartitionNavigationDataBuilder")
    ap.add_argument("--max-commit-gb", type=float, default=200.0)
    ap.add_argument("--max-minutes", type=float, default=30.0)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--extra", action="append", default=[],
                    help="extra commandlet argument, repeatable")
    args = ap.parse_args(argv)

    cmd = [CMD_EXE, UPROJECT, args.map,
           "-run=WorldPartitionBuilderCommandlet",
           "-Builder=" + args.builder,
           "-SCCProvider=None", "-Unattended", "-NoSplash"] + args.extra

    print("command:")
    print("   " + " ".join('"%s"' % c if " " in c else c for c in cmd))
    print()
    used, limit = commit_gb()
    free, total = resource_guard.available_gb()
    print("before: commit %.1f / %.1f GB   free RAM %.1f / %.1f GB"
          % (used or -1, limit or -1, free or -1, total or -1))
    print("bars:   peak commit <= %.0f GB, wall clock <= %.0f min"
          % (args.max_commit_gb, args.max_minutes))
    print()

    if not args.go:
        print("DRY RUN — nothing launched. Re-run with --go.")
        return 0

    if editor_running():
        print("REFUSE: an UnrealEditor.exe is running (or tasklist could not "
              "be read). The builder writes external actor packages and an "
              "editor holding them open produces 'unable to unlink old ... "
              "Invalid argument', which this project has already paid for.")
        return 2

    before = snapshot(EXT_ACTORS)
    log = os.path.join(REPO_ROOT, "_verify",
                       "navmesh_build_%s.log" % args.builder)
    os.makedirs(os.path.dirname(log), exist_ok=True)

    sampler = Sampler()
    sampler.start()
    t0 = time.time()
    aborted = None
    with open(log, "wb") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            mins = (time.time() - t0) / 60.0
            if sampler.peak_commit > args.max_commit_gb:
                aborted = ("peak commit %.1f GB exceeded the %.0f GB bar"
                           % (sampler.peak_commit, args.max_commit_gb))
            elif mins > args.max_minutes:
                aborted = ("wall clock %.1f min exceeded the %.0f min bar"
                           % (mins, args.max_minutes))
            if aborted:
                proc.kill()
                proc.wait()
                rc = -1
                break
            time.sleep(2.0)
    dt = time.time() - t0
    sampler.stop_flag.set()
    sampler.join(timeout=5.0)

    after = snapshot(EXT_ACTORS)
    new = {p: s for p, s in after.items() if p not in before}
    grew = {p: (after[p] - before[p]) for p in after
            if p in before and after[p] != before[p]}

    print()
    print("=== RESULT ===")
    print("exit code        : %s" % rc)
    print("wall clock       : %.1f s (%.2f min)" % (dt, dt / 60.0))
    print("peak commit      : %.1f GB of %.1f GB limit"
          % (sampler.peak_commit, sampler.limit or -1))
    print("min free RAM     : %.1f GB" % (sampler.min_free_phys or -1))
    if sampler.unreadable:
        print("memory samples UNREADABLE: %d (reported, not counted as 0)"
              % sampler.unreadable)
    print("new packages     : %d, %.2f MB"
          % (len(new), sum(new.values()) / (1024.0 ** 2)))
    print("changed packages : %d, net %+.2f MB"
          % (len(grew), sum(grew.values()) / (1024.0 ** 2)))
    for p in sorted(new)[:10]:
        print("   + %-70s %8.1f KB"
              % (os.path.relpath(p, bootstrap.UE_PROJECT_ROOT),
                 new[p] / 1024.0))
    print("log              : %s" % os.path.relpath(log, REPO_ROOT))

    if aborted:
        print()
        print("*** ABORTED: %s ***" % aborted)
        return 4
    if rc != 0:
        print()
        print("*** commandlet exited %s — read the log before concluding "
              "anything about cost ***" % rc)
        return 5
    if sampler.peak_commit == 0.0 and sampler.unreadable:
        # The abort bar tests peak_commit; if EVERY sample was unreadable it
        # stayed 0.0 and could never fire. `unreadable` was printed but never
        # gated -- so the safety bar the docstring promises is "ENFORCED" was
        # not. Refuse rather than report a build that ran unguarded on commit.
        print()
        print("*** COMMIT BAR NOT ENFORCED: every memory sample was UNREADABLE "
              "(%d), so the %.0f GB abort bar never had a value to test. The "
              "build ran UNGUARDED on commit -- do not treat it as within the "
              "bar. ***" % (sampler.unreadable, args.max_commit_gb))
        return 4
    if not new and not grew:
        # rc==0 is the builder's own success signal, but zero disk change is
        # ambiguous: an already-current navmesh, or a build that wrote nothing.
        # This tool does not re-query navmesh tiles from the engine, so it
        # cannot tell them apart -- say so rather than imply a fresh build.
        print()
        print("NOTE: no packages were written or changed. Either the navmesh "
              "was already current or the builder produced nothing -- this tool "
              "cannot distinguish them (it does not re-query navmesh tiles). "
              "rc was 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
