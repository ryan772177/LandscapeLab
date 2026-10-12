"""hlod_setup.py -- run a REAL `-SetupHLODs` on /Game/Alpine8K (creates/destroys HLOD actors; no geometry).

    python scripts/hlod_setup.py --go [--run-dir <ABS>]

Needed whenever SOURCE actors appear or disappear (2026-10-08: the 385 kit houses are absent from every HLOD
actor's source list -- -BuildSingleHLOD rebuilds from the list fixed at the last setup, LESSONS 2026-10-08j).
Uses hlod_build_batched's base_args / launch / running_editors / RE_EXIT_SUMMARY / BASELINE_ERRORS (one place
for those rules; -noxgecontroller is mandatory, R-HLOD 08d).

EXIT, per R-HLOD 08d ("a commandlet that prints Engine exit requested has NOT exited"): waits for the process; if
it is still alive 120 s after the log's "finished execution (result 0)" line AND no package under
__ExternalActors__/Alpine8K has been written in the last 60 s, it is killed and the gap reported. Returns 0 ONLY if
the clean-exit line appeared, no Unreal process is left, and the log's error count <= BASELINE_ERRORS.

ORDER AFTER THIS (audit 2026-10-08): hlod_gitignore.py --apply -> update hlod_build_batched.EXPECTED_PACKAGES from
its count -> hlod_build_batched.py plan -> run. RESTORE LIMIT: HLOD actor packages are UNTRACKED (hlod_gitignore),
so a git tag does NOT restore the actors this destroys or creates; recovery is the tagged world + setup + build.
"""
import argparse
import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import hlod_build_batched as hbb  # noqa: E402

CLEAN_EXIT = "finished execution (result 0)"
EXT = os.path.join(bootstrap.REPO_ROOT, "LandscapeLab", "Content", "__ExternalActors__", "Alpine8K")


def newest_package_age_s():
    newest = max((os.path.getmtime(f) for f in glob.glob(os.path.join(EXT, "**", "*.uasset"), recursive=True)),
                 default=0.0)
    return time.time() - newest


def read(log):
    return open(log, encoding="utf-8", errors="replace").read() if os.path.isfile(log) else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--run-dir", default=os.path.join(bootstrap.REPO_ROOT, "_verify", "hlod",
                                                      time.strftime("%Y%m%d") + "_setup"))
    a = ap.parse_args(argv)
    run_dir = os.path.abspath(a.run_dir)
    if hbb.running_editors():
        print("REFUSE: Unreal process(es) running: %s" % hbb.running_editors())
        return 2
    log = os.path.join(run_dir, "setup.log").replace("\\", "/")
    cmd = hbb.base_args(log) + ["-SetupHLODs"]
    print("command: %s" % " ".join(cmd))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    os.makedirs(run_dir, exist_ok=True)
    t0 = time.time()
    p = hbb.launch(cmd)
    exit_seen, killed, gap = None, False, None
    while p.poll() is None:
        time.sleep(15)
        txt = read(log)
        if exit_seen is None and CLEAN_EXIT in txt:
            exit_seen = time.time()
        if exit_seen and time.time() - exit_seen > 120:
            gap = newest_package_age_s()
            if gap > 60:
                p.kill()
                killed = True
                print("killed: alive 120 s after the clean-exit line, last package write %.0f s ago" % gap)
                break
        if time.time() - t0 > 3600:
            print("ABORT: setup exceeded 60 min")
            p.kill()
            return 4
    deadline = time.time() + 120
    while hbb.running_editors() and time.time() < deadline:
        time.sleep(5)
    left = hbb.running_editors()
    txt = read(log)
    summ = hbb.RE_EXIT_SUMMARY.findall(txt)
    errors = int(summ[-1][0]) if summ else None
    clean = CLEAN_EXIT in txt
    print("rc %s, %.1f min, killed %s, clean-exit line %s, errors %s (baseline %d), Unreal left %s"
          % (p.returncode, (time.time() - t0) / 60, killed, clean, errors, hbb.BASELINE_ERRORS, left))
    print("created/destroyed lines: %s" % len(re.findall(r"(?i)(creat|destroy|delet)\w* HLOD", txt)))
    print("log: %s" % log)
    print("NOTE: the git tag does not restore HLOD actor packages (untracked); recovery = world + setup + build")
    ok = clean and not left and errors is not None and errors <= hbb.BASELINE_ERRORS
    print("VERDICT: %s" % ("OK" if ok else "NOT OK -- do not proceed to the build"))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
