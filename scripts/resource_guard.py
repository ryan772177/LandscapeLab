"""resource_guard.py — RAM check and a mutual-exclusion lock for heavy work.

WHY THIS EXISTS
This machine has 31.4 GB of RAM (docs/environment.md:18; the 15.4 GB
figure this file used to quote was the RETIRED OmniBook) and the project
has already lost the editor twice in one session: once to a GPU TDR
(DXGI_ERROR_DEVICE_HUNG, LESSONS.md 23.12) and once to a
"World Memory Leaks" assert during a map transition (23.13). Neither was
caused by memory, but both happened while several heavy things were in
flight, and the recovery cost more than the check would have.

TWO GUARANTEES, and they are separate concerns deliberately.

  1. REPORT THE MEMORY BEFORE STARTING. A run that begins with 1.5 GB
     free and dies in the middle is indistinguishable, afterwards, from
     a run that had a logic bug. Logging the number at the top makes the
     post-mortem a lookup instead of an argument.

  2. RUN HEAVY OPERATIONS ONE AT A TIME. Landscape rebuild, foliage
     regeneration and lighting builds all drive the same editor through
     the same UDP port. Two at once do not merely contend for RAM -- they
     interleave mutations in the live editor, which is the failure mode
     no amount of memory fixes.

WHY WARN AND NOT REFUSE (a deliberate ruling, 2026-08-02)
Low memory is a RISK, not a fault. The ruling was made on the retired
16 GB machine, where an open editor left ~1.8 GB free and a refusal
threshold would have refused every run. On the current 31.4 GB machine
an editor open leaves ~10.6 GB free (measured 2026-09-16), well above
WARN_FREE_GB, so the warning fires only when something else is also
eating memory — which is exactly when it should. The ruling stands: the
memory check WARNS, loudly, with the number. The LOCK, by contrast,
REFUSES: two concurrent editor mutations is never something the caller
wanted.

The lock is advisory and cooperative: it only constrains scripts that
call into it. It is not a defence against someone driving the editor by
hand at the same time, and it does not pretend to be.

Stale locks are handled by liveness, not by age: a lock file naming a PID
that no longer exists is reclaimed, because the alternative -- a timeout
-- either strands a genuinely long run or leaves a dead lock in place.
"""

from __future__ import annotations

import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH = os.path.join(REPO_ROOT, ".heavy-op.lock")

# Warn below this. 4 GB is a floor the current 31.4 GB machine clears
# with an editor open (~10.6 GB free, measured 2026-09-16), so the
# warning marks a genuinely tight moment rather than firing every run;
# the runs that actually hurt started near 2 GB on the retired machine.
WARN_FREE_GB = 4.0


def available_gb():
    """(available_gb, total_gb) or (None, None) if it cannot be read.

    Returns None rather than 0 on failure. A memory check that reports
    "0 GB free" when it simply could not look would fire its own warning
    every run and be ignored within a day -- section 2.10, "I could not
    look" is not "it is absent".
    """
    try:
        import ctypes

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

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None, None
        return (st.ullAvailPhys / (1024.0 ** 3),
                st.ullTotalPhys / (1024.0 ** 3))
    except Exception:
        return None, None


def check_memory(label, warn_gb=WARN_FREE_GB, stream=None):
    """Print the memory situation. -> True comfortable / False low /
    None could not read (Pass 3 2026-09-16 F4).

    None, NOT True, on an unreadable instrument: a could-not-look and a
    healthy reading must be distinguishable to any caller that branches
    on the result (rule 13). Truth-testing callers (`if check_memory`)
    keep today's permissive behaviour, since None is falsy — but they at
    least stop reading "could not measure" as "comfortable" the way True
    did. Never raises and never exits: this is an instrument, not a gate.
    """
    out = stream or sys.stdout
    avail, total = available_gb()
    if avail is None:
        out.write("  RAM: COULD NOT BE READ -- proceeding without the "
                  "check. This is not 'memory is fine'.\n")
        return None
    out.write("  RAM: {0:.1f} GB available of {1:.1f} GB "
              "(warn below {2:.1f})\n".format(avail, total, warn_gb))
    if avail < warn_gb:
        out.write("  *** LOW MEMORY WARNING ***  {0} is a heavy operation "
                  "and only {1:.1f} GB is free.\n".format(label, avail))
        out.write("      Close the browser, or any second editor, before "
                  "blaming the result. Proceeding anyway -- low memory is "
                  "a risk, not a fault.\n")
        return False
    return True


def _pid_alive(pid):
    """True if a process with this PID exists. Unknown -> True.

    Erring toward 'alive' keeps a lock rather than stealing one. A lock
    wrongly kept costs a re-run; a lock wrongly stolen costs two scripts
    mutating one editor at once, which is the thing this exists to stop.
    """
    if pid <= 0:
        return False
    try:
        import ctypes
        # use_last_error=True + get_last_error(): a bare
        # kernel32.GetLastError() call can be CLOBBERED by ctypes' own
        # intervening Win32 calls (GetProcAddress on first attribute
        # access), so a live-but-access-denied PID could read as ERROR
        # 87 "no such process" and its lock be STOLEN — the exact
        # direction this comment rules out (Pass 3 2026-09-16 F3).
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return ctypes.get_last_error() != 87  # not "no such process"
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return True


def _read_lock():
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


class HeavyOp(object):
    """Context manager: one heavy editor operation at a time.

        with HeavyOp("foliage placement") as ok:
            if not ok:
                return 8
            ...

    Enter prints the memory line and takes the lock. It returns False --
    rather than raising -- if another heavy operation holds it, so the
    caller chooses its own exit code and message.
    """

    def __init__(self, label, warn_gb=WARN_FREE_GB):
        self.label = label
        self.warn_gb = warn_gb
        self.held = False
        self.blocker = None

    def _refuse(self, other):
        self.blocker = other
        print("  REFUSE: '{0}' (pid {1}) has held the heavy-operation "
              "lock since {2}.".format(
                  other.get("label", "?"), other.get("pid", "?"),
                  other.get("started", "?")))
        print("  Heavy operations drive the SAME editor through the "
              "same port; running two interleaves mutations in live "
              "state. Wait for it, or delete {0} if you are certain "
              "it is dead.".format(LOCK_PATH))

    def _payload(self):
        return json.dumps({"pid": os.getpid(), "label": self.label,
                           "started": time.strftime("%Y-%m-%d %H:%M:%S")})

    def __enter__(self):
        print("--- resource guard: {0} ---".format(self.label))
        check_memory(self.label, self.warn_gb)
        # ATOMIC ACQUIRE (Pass 3 2026-09-16 F2): the old check-then-write
        # let two processes both see no live lock and both open('w'),
        # each silently truncating the other — the concurrent-start case
        # the lock exists for. O_CREAT|O_EXCL makes creation the atomic
        # test; only on an EXISTING lock do we run the liveness check.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        for _attempt in (0, 1):
            try:
                fd = os.open(LOCK_PATH, flags)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(self._payload())
                self.held = True
                print("  lock taken (pid {0})".format(os.getpid()))
                return True
            except FileExistsError:
                other = _read_lock()
                # AN UNREADABLE (zero-byte) LOCK MAY BE A LIVE ACQUIRER
                # MID-WRITE (auditor FIX): O_EXCL makes CREATION atomic
                # but not the payload write, so a rival that just created
                # the file has a 0-byte window before its JSON flushes.
                # Re-read once after a short sleep before treating an
                # unreadable lock as dead — a live payload will have
                # landed; a genuinely garbage lock is still garbage.
                if other is None:
                    time.sleep(0.25)
                    other = _read_lock()
                if other and _pid_alive(int(other.get("pid", -1))):
                    self._refuse(other)
                    return False
                # dead holder (or a still-unreadable lock): reclaim ONCE
                print("  reclaiming a lock left by dead pid {0} ({1})".format(
                    (other or {}).get("pid"), (other or {}).get("label")))
                try:
                    os.remove(LOCK_PATH)
                except OSError:
                    pass
                # loop retries O_EXCL — if a third process wins the race
                # to recreate it, the second iteration's FileExistsError
                # re-runs the liveness check rather than truncating.
            except OSError as exc:
                print("  NOTE: could not write {0} ({1}); running WITHOUT "
                      "mutual exclusion.".format(LOCK_PATH, exc))
                return True
        # both attempts lost the recreate race to a live holder
        other = _read_lock()
        if other:
            self._refuse(other)
            return False
        return True

    def __exit__(self, *exc):
        if not self.held:
            return False
        try:
            cur = _read_lock()
            if cur and int(cur.get("pid", -1)) == os.getpid():
                os.remove(LOCK_PATH)
        except OSError:
            pass
        return False


def selftest():
    """Offline, deterministic proof of the three behaviours -- no editor, no
    real heavy op, a TEMP lock path so the live .heavy-op.lock is untouched.
    Added 2026-09-20 (Brief 5 replay R10 had no selftest)."""
    import io
    import tempfile
    global LOCK_PATH
    # 1. check_memory verdicts by pushing warn_gb to the extremes.
    avail, _total = available_gb()
    if avail is not None:
        buf = io.StringIO()
        assert check_memory("t", warn_gb=0.0, stream=buf) is True, "comfortable"
        buf = io.StringIO()
        assert check_memory("t", warn_gb=1e9, stream=buf) is False, "low fires"
        assert "LOW MEMORY" in buf.getvalue(), "low prints the warning"
    # 2. liveness: this process is alive; a huge PID is not.
    assert _pid_alive(os.getpid()) is True, "own pid alive"
    assert _pid_alive(2000000000) is False, "bogus pid dead"
    assert _pid_alive(0) is False, "pid 0 rejected"
    # 3. lock acquire / release / refuse-live / reclaim-dead, on a temp path.
    real = LOCK_PATH
    tmpd = tempfile.mkdtemp(prefix="rg_selftest_")
    LOCK_PATH = os.path.join(tmpd, ".heavy-op.lock")
    try:
        op = HeavyOp("selftest-A")
        assert op.__enter__() is True and op.held, "acquire"
        assert os.path.exists(LOCK_PATH), "lock file written"
        # a second op while the first (this live pid) holds it -> REFUSE
        op2 = HeavyOp("selftest-B")
        assert op2.__enter__() is False and op2.blocker is not None, "refuse live"
        op.__exit__()
        assert not os.path.exists(LOCK_PATH), "release removes the lock"
        # a lock left by a dead pid is reclaimed
        with open(LOCK_PATH, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"pid": 2000000000, "label": "ghost",
                                 "started": "2000-01-01 00:00:00"}))
        op3 = HeavyOp("selftest-C")
        assert op3.__enter__() is True and op3.held, "reclaim dead holder"
        op3.__exit__()
    finally:
        LOCK_PATH = real
        try:
            if os.path.exists(os.path.join(tmpd, ".heavy-op.lock")):
                os.remove(os.path.join(tmpd, ".heavy-op.lock"))
            os.rmdir(tmpd)
        except OSError:
            pass
    print("resource_guard selftest OK: memory verdicts, liveness, "
          "lock acquire/release/refuse/reclaim")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
        sys.exit(0)
    avail, total = available_gb()
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("lock file : {0}".format(LOCK_PATH))
    if avail is None:
        print("memory    : UNREADABLE")
    else:
        print("memory    : {0:.1f} GB free of {1:.1f} GB".format(avail, total))
    cur = _read_lock()
    if cur:
        print("held by   : {0} (pid {1}, since {2}) alive={3}".format(
            cur.get("label"), cur.get("pid"), cur.get("started"),
            _pid_alive(int(cur.get("pid", -1)))))
    else:
        print("held by   : nobody")
