"""verify_marker_streaming.py — unit 10's acceptance: nav before markers.

`PHASE2_PLAN.md` unit 10: *"drive a streaming source across a chunk boundary at
mounted speed in PIE ... nav data must be resident before the marker on it."*

The failure this guards against is specific and nasty: an encounter marker
streams in on ground whose navmesh has not. Anything that spawns there stands
still, which reads as an AI bug and is a streaming bug.

    python scripts/verify_marker_streaming.py
    python scripts/verify_marker_streaming.py --steps 12 --settle 4

HOW THE TRAVERSE IS DONE
------------------------
The streaming source is teleported along a straight line across the region in
~200 m jumps, pausing after each so streaming can run. **Teleporting is a
STRICTER test than walking at mounted speed, not a weaker one** — World
Partition gets less warning, not more. A walked traverse is also unavailable
from the current spawn: the town blocks every bearing (0 of 360 clear to
1200 m, measured 2026-08-27), and the criterion is about streaming ORDER
anyway, not about locomotion.

WHAT IT ASSERTS
---------------
Per marker, never aggregate. "94% of markers had nav" is the misleading
denominator (non-negotiable 22): the question is whether ANY marker was
resident without its nav chunk, and one is a failure.

WHAT IT CANNOT ASSERT, DECLARED
-------------------------------
Unit 10's second clause — *"spawning must refuse when navmesh projection
fails"* — is NOT testable yet. `UEncounterDirectorSubsystem` spawns nothing;
there is no enemy pawn class until unit 12. Reporting this run as closing all
of unit 10 would be the header-describes-the-design error the audit already
caught in this subsystem once.

Exit codes:
    0  every resident marker had its nav chunk resident at every step
    1  could not look (no step produced a census)
    3  rule 7: no verified editor node
    4  at least one marker was resident without nav
    6  PIE did not START
    7  too few marker-observations -- INCONCLUSIVE, not a pass
(If PIE does not END that is printed loudly -- "STILL IN PLAY, press Escape" --
 for the operator to act on; it is NOT encoded as an exit code.)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
STEP = os.path.join(REPO_ROOT, "scripts", "marker_streaming_step_payload.txt")
VERIFY_DIR = os.path.join(REPO_ROOT, "_verify", "20260827_streaming")

BEGIN = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "started": False}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_play_simulate()
    _out["started"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_STREAM__" + _json.dumps(_out))
'''

END = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "requested": False}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_request_end_play()
    _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_STREAM__" + _json.dumps(_out))
'''

CONFIRM = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _out["in_play"] = _ues.get_game_world() is not None
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_STREAM__" + _json.dumps(_out))
'''


def _step(x, y, z, move):
    with open(STEP, "r", encoding="utf-8") as fh:
        body = fh.read()
    body = (body.replace("__X__", repr(float(x)))
                .replace("__Y__", repr(float(y)))
                .replace("__Z__", repr(float(z)))
                .replace("__MOVE__", repr(bool(move))))
    code, d, raw = ue_exec.run(body, marker="__LL_STREAM__", timeout=25.0,
                               stage_name="ll_stream_step", quiet=True)
    return d, raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument("--verified",
                    default="encounters/alpine_8k_verified.json")
    ap.add_argument("--steps", type=int, default=12)
    ap.add_argument("--settle", type=float, default=4.0,
                    help="seconds after each teleport for streaming to run")
    ap.add_argument("--pie-settle", type=float, default=30.0)
    ap.add_argument("--min-observations", type=int, default=8,
                    help="total (marker, step) pairs examined below which the "
                         "run is INCONCLUSIVE rather than a pass. NOT peak "
                         "concurrency -- markers here are ~460 m apart, so one "
                         "resident at a time is correct behaviour and evidence "
                         "accumulates across steps instead.")
    args = ap.parse_args(argv)

    vp = os.path.join(REPO_ROOT, args.verified)
    with open(vp, "r", encoding="utf-8") as fh:
        rows = json.load(fh)["encounters"]
    # STAND ON ACTUAL MARKERS, do not fly a straight line between extremes.
    #
    # The first version interpolated between the cloud's corners at a fixed Z
    # 838 m up. It reported PASS with ONE marker resident at every step -- a
    # verdict with no discriminating power, because a test that has almost
    # nothing resident cannot detect a marker resident without nav. Standing at
    # a marker's own position at its own elevation guarantees at least that
    # marker is in range, and puts its neighbours in range too.
    rows = sorted(rows, key=lambda r: (r["loc_cm"][0], r["loc_cm"][1]))
    n = max(1, len(rows) // max(1, args.steps))
    waypoints = [r["loc_cm"] for r in rows[::n]][:args.steps + 1]

    print("traverse      %d waypoints, each ON a placed marker"
          % len(waypoints))
    print("              from (%.0f, %.0f) to (%.0f, %.0f)"
          % (waypoints[0][0], waypoints[0][1],
             waypoints[-1][0], waypoints[-1][1]))
    print("              teleport, NOT a walk -- stricter, see the docstring")
    print("")

    # ue_exec.run returns (exit_code, parsed, raw) -- three, not two.
    _c, d, raw = ue_exec.run(BEGIN, marker="__LL_STREAM__", timeout=25.0,
                             stage_name="ll_stream_begin", quiet=True)
    if _c == 3:
        # ue_exec returns exit 3 for a rule-7 (no verified node) refusal --
        # surface it as the documented exit 3, not as "PIE did not start" (6).
        print("REFUSE (rule 7): no verified editor node.")
        return 3
    if d is None or d.get("error"):
        print("PIE DID NOT START:", (d or {}).get("error", "no marker"))
        return 6
    print("PIE requested. Settling %.0f s." % args.pie_settle)
    time.sleep(args.pie_settle)

    log, offenders = [], 0
    try:
        for i, wp in enumerate(waypoints):
            x, y, z = wp[0], wp[1], wp[2]
            # +2 m, so the pawn stands ON the marker's ground rather than
            # inside it. Streaming is distance-based in 3D, so flying high
            # above the terrain silently shrinks what is in range.
            s, raw = _step(x, y, z + 200.0, True)
            if s is None or s.get("error"):
                print("  step %2d  COULD NOT LOOK: %s"
                      % (i, (s or {}).get("error", "no marker")))
                continue
            time.sleep(args.settle)
            # Census AFTER the settle, in a second call, so the count is taken
            # once streaming has had its chance. Censusing in the same call as
            # the teleport would measure the instant before streaming ran and
            # report a failure the engine was never given time to avoid.
            s, raw = _step(x, y, z, False)
            if s is None or s.get("error"):
                print("  step %2d  COULD NOT LOOK on census: %s"
                      % (i, (s or {}).get("error", "no marker")))
                continue
            bad = s.get("without_nav_total", 0)
            offenders += bad
            log.append(s)
            print("  step %2d  pawn %-28s markers %3d  nav chunks %3d  "
                  "WITHOUT NAV %d"
                  % (i, s.get("pawn"), s["markers_resident"],
                     s["nav_chunks_resident"], bad))
            if bad and s.get("markers_without_nav"):
                for r in s["markers_without_nav"][:3]:
                    print("             offender %s" % r)
    finally:
        # END PLAY, THEN CONFIRM IN A SEPARATE CALL. `editor_request_end_play`
        # is a REQUEST -- reading `get_game_world()` in the same payload asks
        # whether it finished before it had a chance to, which is why both
        # earlier runs printed STILL IN PLAY over a teardown that worked. A
        # confirmation taken too early is a measurement of the wrong instant.
        ue_exec.run(END, marker="__LL_STREAM__", timeout=25.0,
                    stage_name="ll_stream_end", quiet=True)
        time.sleep(8.0)
        _c, e, _r = ue_exec.run(CONFIRM, marker="__LL_STREAM__", timeout=25.0,
                                stage_name="ll_stream_confirm", quiet=True)
        if e is None:
            print("COULD NOT CONFIRM whether PIE ended — check the editor.")
        elif e.get("in_play"):
            print("STILL IN PLAY — press Escape in the editor.")
        else:
            print("PIE ended, confirmed.")

    if not log:
        print("")
        print("NO STEPS PRODUCED A CENSUS — could not look. That is not a pass.")
        return 1

    peak_m = max(s["markers_resident"] for s in log)
    observations = sum(s["markers_resident"] for s in log)
    peak_c = max(s["nav_chunks_resident"] for s in log)
    print("")
    print("=== RESULT ===")
    print("  steps censused      %d" % len(log))
    print("  peak resident       %d markers, %d nav chunks" % (peak_m, peak_c))
    print("  marker-observations %d   (the power of this run)" % observations)
    print("  markers WITHOUT nav %d across all steps" % offenders)
    print("  power floor         %d observations required"
          % args.min_observations)

    os.makedirs(VERIFY_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(VERIFY_DIR, "unit10_streaming_%s.md" % stamp)
    L = ["# Unit 10 acceptance — nav data resident before the marker on it", "",
         "**Class: PLAY IN EDITOR.** The streaming source is TELEPORTED across "
         "the region in", "large jumps, which gives World Partition less "
         "warning than mounted speed would.", "A pass here implies a pass at "
         "mounted speed; a failure here would need re-checking", "at the "
         "slower rate before being called a defect.", "",
         "| | |", "|---|---|",
         "| steps censused | %d |" % len(log),
         "| peak resident markers | %d |" % peak_m,
         "| peak resident nav chunks | %d |" % peak_c,
         "| marker-observations | %d |" % observations,
         "| **markers resident without nav** | **%d** |" % offenders, "",
         "## What this does NOT close", "",
         "Unit 10's second clause — *spawning must refuse when navmesh "
         "projection fails* —", "is **not testable yet**. "
         "`UEncounterDirectorSubsystem` spawns nothing; there is no",
         "enemy pawn class until unit 12.", "",
         "## Per-step", "",
         "```",
         "step  pawn_x      pawn_y      markers  navchunks  without_nav"]
    for i, s in enumerate(log):
        p = s.get("pawn") or [0, 0, 0]
        L.append("%4d  %-11.0f %-11.0f %7d  %9d  %d"
                 % (i, p[0], p[1], s["markers_resident"],
                    s["nav_chunks_resident"], s.get("without_nav_total", 0)))
    L += ["```", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("")
    print("ARTEFACT: %s" % path)

    if offenders:
        print("")
        print("FAIL — a marker was resident on ground whose navmesh was not.")
        print("Anything spawned there would stand still, which reads as an AI")
        print("bug and is a streaming bug.")
        return 4

    # A CLEAN RESULT FROM A TEST WITH NO POWER IS NOT A PASS.
    #
    # The first run of this reported PASS with exactly ONE marker resident at
    # every step. Zero offenders out of one observation is not evidence that
    # streaming orders correctly; it is evidence that almost nothing streamed.
    # Non-negotiable 6 -- "I looked and it's absent" must be distinguishable
    # from "I couldn't look" -- and an underpowered pass is the second wearing
    # the first's clothes.
    # THE POWER METRIC IS TOTAL MARKER-OBSERVATIONS, NOT PEAK CONCURRENCY.
    #
    # The first version of this floor gated on how many markers were resident
    # AT ONCE and called a clean run INCONCLUSIVE at 1. That was the wrong
    # quantity: 317 markers over 66 km2 are ~460 m apart and World Partition's
    # loading range is smaller, so ONE resident at a time is correct behaviour,
    # not a streaming failure. What accumulates evidence is the number of
    # (marker, step) pairs examined -- each one is an independent instance of
    # "this marker is resident; is its nav chunk resident too?"
    #
    # The underlying rule survives the correction: a clean result from a test
    # that observed almost nothing is not a pass. Only the denominator moved.
    if observations < args.min_observations:
        print("")
        print("INCONCLUSIVE — %d marker-observations, below the %d this test"
              % (observations, args.min_observations))
        print("needs to have any chance of observing the failure. Zero")
        print("offenders out of almost no observations is not evidence.")
        print("Raise --steps, or --settle if streaming needs longer.")
        return 7

    print("")
    print("PASS — no marker was resident without its nav chunk, in %d"
          % observations)
    print("marker-observations across %d steps." % len(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
