"""shoot.py — take one editor frame and WAIT FOR IT ON THE HOST.

WHY THIS EXISTS
---------------
`city_shot_payload.txt` used to wait for its own screenshot in a
`_time.sleep()` loop. That payload runs INSIDE the editor on the GAME THREAD,
and `HighResShot` completes over SUBSEQUENT ENGINE TICKS -- so the sleep
blocked the very thread that had to tick, and the frame could not be written
until the watcher gave up. **The watcher was waiting for an event its own
waiting prevented.**

One mechanism, three recorded "mysteries":

  * the watcher wrong 6 of 6, always `ok:false` over a frame that existed
  * the "unexplained 630 s post-capture wedge" -- not a wedge; the editor was
    blocked in that loop, and the log froze along with it
  * an `OUTDIR` copy that had NEVER executed, because it sat after the raise
    on a path that always raised

Measured 2026-08-30: issued 19:11:58.122, gave up after 841.3 s, frame written
0.8 s later. Repeated with the editor FOREGROUNDED -- 843 s vs 848 s at 100x
the editor CPU -- so window focus was never the cause. R-CITYSHOT AMENDED
2026-08-30b.

**Sleeping on the host costs the editor nothing**, so the wait moves here and
the editor is free to tick, render the tiles and write the file.

WHAT "OK" MEANS, IN TWO PLACES
------------------------------
The payload's `ok` now means **ISSUED**. This tool's `ok` means **ON DISK**.
That distinction is the whole point: the old failure was a tool reporting a
verdict about a file it could not observe.

THE FILE IS THE ARTEFACT
------------------------
This polls for a NEW `.png` absent from the listing the payload took before
issuing the command, then waits for its size to settle before claiming it.
It never concludes from a timer.

Usage:
    python scripts/shoot.py --name c0_stage \\
        --loc " -4500,0,900" --rot "0,-2.16,0" --fov 0 --mult 1 \\
        --outdir _verify/20260830_loop

    (Leading space in a negative --loc avoids argparse reading it as a flag.)

Exit codes:
    0  frame on disk and copied
    1  payload error, or COULD NOT LOOK (no JSON / no marker, or an old
       payload without shots_dir/before), or no frame before the deadline
    2  bad arguments (including a malformed --loc/--rot)
    3  no verified editor node (rule 7, from ue_exec)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
PAYLOAD = os.path.join(REPO, "scripts", "city_shot_payload.txt")

# ⛔ 25, NOT a render-sized number. `ue_exec --timeout` is the DISCOVERY
# WINDOW and is SPENT IN FULL (ue_exec.py --timeout; behaviour in
# bootstrap._discover, bootstrap.py:188). On 2026-08-30 a caller passed
# 1200 believing it was a budget for a long render and lost 20 minutes with
# the shot never issued. The payload's own duration is not governed by it --
# and now that the payload returns immediately, it never could be.
DISCOVERY_S = 25.0

# A frame smaller than this is a truncated or empty capture, not a shot. The
# smallest real frame this project has taken is ~2.0 MB; 10 kB is two orders
# of magnitude below that and only has to separate "file" from "no file".
MIN_FRAME_BYTES = 10000

# ⭐ PINNED BY DEFAULT. `HighResShot` with a multiplier renders viewport-size x
# MULT, so frame size follows the editor window -- and on 2026-08-30 restoring
# that window between two shots of the same subject produced 2032x1273 and
# 1263x1349, two different CALIBRATION CLASSES that could not be diffed.
# 2032x1273 is what the first delivered concept frame measured, so anything
# reshot against it stays comparable with what is already banked.
DEFAULT_RES = "2032x1273"


def _triple(text, what):
    # A bad --loc/--rot is a BAD ARGUMENT (exit 2), not a render failure
    # (Pass 3 2026-09-16 F1): SystemExit("string") exits 1 in CPython,
    # the code the contract reserves for "payload ran / no frame" — a
    # series driver retrying exit 1 as transient would loop forever on a
    # pure typo the editor never saw. Print, then SystemExit(2).
    parts = [p for p in text.replace(" ", "").split(",") if p != ""]
    if len(parts) != 3:
        print("REFUSE: --%s needs three comma-separated numbers, got %r"
              % (what, text))
        raise SystemExit(2)
    try:
        return [float(p) for p in parts]
    except ValueError:
        print("REFUSE: --%s must be numeric, got %r" % (what, text))
        raise SystemExit(2)


def poll_for_frame(shots_dir, before, deadline_s, settle_s=2.0, quiet=False):
    """Wait for a NEW png that has stopped growing. Returns a path or None.

    `before` comes from the payload, taken in the editor immediately before
    the console command -- not re-derived here, so an unrelated capture that
    landed between the two cannot be mistaken for ours.
    """
    before = set(before)
    t0 = time.time()
    last_report = 0.0
    while time.time() - t0 < deadline_s:
        try:
            now = set(os.listdir(shots_dir))
        except OSError:
            now = set()
        fresh = sorted(f for f in (now - before) if f.lower().endswith(".png"))
        if fresh:
            path = os.path.join(shots_dir, fresh[-1])
            # Size must SETTLE before the file is claimed. A 22.9 MB frame was
            # claimed mid-write by this project on 2026-08-25.
            #
            # !! THE SETTLE LOOP IS BOUNDED BY THE SAME DEADLINE. It was
            # originally `while True` with the exit condition
            # `cur == size and cur > MIN_BYTES`, so a file that settled BELOW
            # the floor -- a truncated or zero-length capture -- satisfied
            # neither the return nor any exit and the poller SPUN FOREVER,
            # ignoring the deadline it had been given. Found by this tool's
            # own --self-test on its first run, which is the entire argument
            # for making a poller prove itself in three directions.
            size = -1
            while time.time() - t0 < deadline_s:
                try:
                    cur = os.path.getsize(path)
                except OSError:
                    cur = -1
                if cur == size:
                    if cur > MIN_FRAME_BYTES:
                        return path
                    # Settled and too small: it is not a frame. Fold it into
                    # `before` so the next sweep looks PAST it rather than
                    # re-picking the same dud, and keep waiting for a real one.
                    before.add(os.path.basename(path))
                    break
                size = cur
                time.sleep(settle_s)
            else:
                # deadline expired inside the settle loop
                return None
            continue
        el = time.time() - t0
        if not quiet and el - last_report >= 30.0:
            print("    waiting %4.0f s / %.0f s ..." % (el, deadline_s))
            last_report = el
        time.sleep(2.0)
    return None


def self_test():
    """Three directions: it FINDS, it REFUSES, and it does not claim early.

    A poller that only ever returns a path is untested -- the 2026-08-30
    watcher was wrong six times while looking, in its own terms, like it
    worked. Each case below fails in a DIFFERENT direction.
    """
    import tempfile
    import threading

    cases = []

    def record(name, got, want):
        ok = got == want
        cases.append((name, got, want, ok))
        print("  %-4s %-38s -> %-9s want %s"
              % ("ok" if ok else "FAIL", name, got, want))

    d = tempfile.mkdtemp(prefix="shoot_selftest_")

    # POSITIVE CONTROL. If this fails, nothing below means anything -- which
    # is the exact failure the plan-stamp instrument is currently carrying.
    with open(os.path.join(d, "new.png"), "wb") as fh:
        fh.write(b"x" * 20000)
    got = poll_for_frame(d, [], 8.0, settle_s=0.05, quiet=True)
    record("POSITIVE CONTROL (a new png)",
           "FOUND" if got else "NONE", "FOUND")

    # A file already present is NOT ours. This is the direction that matters
    # most: claiming a stale frame reads as success and is undetectable later.
    got = poll_for_frame(d, ["new.png"], 3.0, settle_s=0.05, quiet=True)
    record("pre-existing file is not a new frame",
           "FOUND" if got else "NONE", "NONE")

    # Empty directory -> refuse, do not hang past the deadline.
    d2 = tempfile.mkdtemp(prefix="shoot_selftest_")
    t0 = time.time()
    got = poll_for_frame(d2, [], 3.0, settle_s=0.05, quiet=True)
    el = time.time() - t0
    record("no frame at all -> NONE", "FOUND" if got else "NONE", "NONE")
    record("...and it respects the deadline", el < 12.0, True)

    # A non-png must not satisfy it.
    with open(os.path.join(d2, "notes.txt"), "wb") as fh:
        fh.write(b"y" * 20000)
    got = poll_for_frame(d2, [], 3.0, settle_s=0.05, quiet=True)
    record("a .txt is not a frame", "FOUND" if got else "NONE", "NONE")

    # A tiny file must not satisfy it -- guards the truncated/black-frame case.
    d3 = tempfile.mkdtemp(prefix="shoot_selftest_")
    with open(os.path.join(d3, "tiny.png"), "wb") as fh:
        fh.write(b"z" * 100)
    got = poll_for_frame(d3, [], 3.0, settle_s=0.05, quiet=True)
    record("a 100-byte png is not a frame",
           "FOUND" if got else "NONE", "NONE")

    # STILL GROWING: it must wait for the size to settle, not claim mid-write.
    d4 = tempfile.mkdtemp(prefix="shoot_selftest_")
    target = os.path.join(d4, "growing.png")

    def grow():
        with open(target, "wb") as fh:
            for _ in range(6):
                fh.write(b"q" * 20000)
                fh.flush()
                time.sleep(0.15)

    threading.Thread(target=grow, daemon=True).start()
    time.sleep(0.05)
    got = poll_for_frame(d4, [], 15.0, settle_s=0.25, quiet=True)
    final = os.path.getsize(target)
    record("waits for a growing file to settle",
           got is not None and os.path.getsize(got) == final, True)

    bad = [c for c in cases if not c[3]]
    print("")
    if bad:
        print("SELF-TEST FAILED: %d case(s) did not behave: %s"
              % (len(bad), ", ".join(c[0] for c in bad)))
        return 1
    print("SELF-TEST PASSED: %d case(s), all three directions." % len(cases))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    if argv is None:
        argv = sys.argv[1:]
    if "--self-test" in argv:
        return self_test()
    ap.add_argument("--name", required=True)
    ap.add_argument("--loc", required=True, help="x,y,z in cm")
    ap.add_argument("--rot", required=True,
                    help="ROLL,PITCH,YAW -- roll first, as unreal.Rotator "
                         "takes it. This project has set a -25 deg ROLL "
                         "believing it was pitch, three times.")
    ap.add_argument("--fov", type=float, default=0.0,
                    help="horizontal FOV in degrees, or 0 to keep the "
                         "viewport's own")
    ap.add_argument("--mult", type=int, default=1)
    ap.add_argument("--res", default=DEFAULT_RES,
                    help="explicit output resolution WxH. PINNED BY DEFAULT "
                         "so a series is calibration-comparable; pass "
                         "--res \"\" to fall back to viewport x --mult.")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--project-root", default=None,
                    help="ABSOLUTE path of the project whose editor this shot "
                         "expects. Passed to ue_exec, which verifies the "
                         "connected node against it (rule 7). Defaults to "
                         "UE_PROJECT_ROOT.")
    ap.add_argument("--deadline", type=float, default=1800.0,
                    help="HOST-side wait for the file, in seconds. Generous "
                         "because it costs the editor nothing.")
    args = ap.parse_args(argv)

    loc = _triple(args.loc, "loc")
    rot = _triple(args.rot, "rot")
    outdir = args.outdir
    if not os.path.isabs(outdir):
        outdir = os.path.join(REPO, outdir)

    cmd = [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
           PAYLOAD, "--timeout", str(DISCOVERY_S)]
    # Rule 7 applied to ANOTHER project, not bypassed: the caller declares
    # which editor it expects and ue_exec verifies the connected node against
    # it. Needed for the sample-project census, where the editor is not ours.
    # `shots_dir` still comes back FROM THE PAYLOAD, so the host polls the
    # sample project's own Saved/Screenshots without being told where it is.
    if args.project_root:
        cmd += ["--project-root", args.project_root]
    cmd += [
           "--set", "LOC=%r" % (loc,),
           "--set", "ROT=%r" % (rot,),
           "--set", "FOV=%r" % (args.fov,),
           "--set", "MULT=%d" % args.mult,
           "--set", "RES=%s" % (args.res or ""),
           "--set", "NAME=%s" % args.name,
           "--set", "OUTDIR=%s" % outdir.replace("\\", "/")]

    print("issuing the shot (discovery %.0f s, payload returns immediately)"
          % DISCOVERY_S)
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout or ""
    if p.returncode == 3 or "REFUSE (rule 7)" in out:
        print(out.strip()[-600:])
        return 3
    i, j = out.find("{"), out.rfind("}")
    if i < 0:
        print("COULD NOT LOOK -- the editor returned no JSON.")
        print(out.strip()[-900:])
        print((p.stderr or "").strip()[-400:])
        return 1
    rep = json.loads(out[i:j + 1])
    if rep.get("error"):
        print("the payload reported an error, so no shot was taken:")
        print("  " + str(rep["error"])[:500])
        return 1

    print("  shot command      %s" % rep.get("shot_cmd"))
    print("  camera read-back  loc %s  rot %s  fov %s"
          % (rep.get("readback", {}).get("loc"),
             rep.get("readback", {}).get("rot_roll_pitch_yaw"),
             rep.get("fov_readback")))
    print("  max_loc_err_cm %s  max_rot_err_deg %s"
          % (rep.get("max_loc_err_cm"), rep.get("max_rot_err_deg")))
    if rep.get("ground_check"):
        print("  ground_check      %s" % rep["ground_check"])
    if rep.get("selection_cleared") is False:
        print("  ⚠ SELECTION NOT CLEARED -- a gizmo will be in the frame: %s"
              % rep.get("selection_error"))

    shots = rep.get("shots_dir")
    before = rep.get("before")
    if not shots or before is None:
        print("REFUSE: the payload did not report shots_dir/before. It is "
              "probably the OLD waiting version -- re-check "
              "scripts/city_shot_payload.txt.")
        return 1

    print("  issued. polling %s host-side (deadline %.0f s)"
          % (shots, args.deadline))
    t0 = time.time()
    src = poll_for_frame(shots, before, args.deadline)
    waited = time.time() - t0
    if src is None:
        print("NO FRAME after %.0f s. That is 'could not look', not 'the shot "
              "failed' -- check %s by hand before concluding." % (waited, shots))
        return 1

    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, args.name + ".png")
    shutil.copyfile(src, dst)
    n = os.path.getsize(dst)
    print("FRAME ON DISK after %.0f s" % waited)
    print("  src   %s" % src)
    print("  dst   %s  (%d bytes)" % (dst, n))
    if n <= MIN_FRAME_BYTES:
        print("  ⚠ suspiciously small for a frame; open it before using it.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
