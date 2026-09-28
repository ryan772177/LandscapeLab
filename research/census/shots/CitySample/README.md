# City Sample shots — ONE VIEWPOINT, not a five-angle survey

**Read this before using these frames.** They are genuine `Small_City_LVL`
content at 1920x1080, and they are useful as a record of how City Sample
looks. They are **not** the wide-vista / mid / ground / sky / overview survey
their filenames promise. All five are the same ground-level plaza.

## What happened

The five `-game` launches each issued `BugItGo` to a different station, and
the engine accepted every one — from the logs:

    wide_vista      BugItGo to: X=-66637 Y=-65136 Z=24700  P=-20 Y=45
    overview_high   BugItGo to: X=-27006 Y=-25505 Z=48479  P=-55 Y=20

Every resulting frame is the same plaza at eye level. Three attempts:

1. **plain `BugItGo`** — the pawn has gravity and collision, so it teleports
   247 m / 485 m up and falls back before the shot lands.
2. **`ghost` first** (no-clip flight) + `r.HighResScreenshotDelay 8` — same
   result.
3. Confirmed visually against `overview_high`, which should be 485 m up
   looking down at 55°, and is a street-level view of the same benches.

The likely cause is timing: `-ExecCmds` fires every command in one batch at
startup, so `HighResShot` is issued in the same breath as the teleport, before
the pawn has settled — and City Sample runs its own camera logic on top. E3's
`-game` perf runs moved the camera successfully because their capture ran for
90 s *after* the teleport; a screenshot has no such window.

## The trap worth remembering

The five frames differ pairwise by 10–30 mean absolute value, so a numeric
"are these different?" test **passes**. That difference is **shader
compilation progressing between launches** — the same plaza rendered with
purple-green buildings in one frame and green-teal in another.

I wrote a differentiation check to catch exactly this failure, then calibrated
it against the known-bad set: **the bad set scored 10.37, higher than the good
set's 9.77.** The check ranked the failure above the success. It now reports
its numbers with `NO VERDICT` and says visual confirmation is required.

**A metric that has not been run against a known-bad case is not a check.**

## Status

The census JSON — the actual deliverable — is unaffected and verified:
`current_world` is `/Game/Map/Small_City_LVL.Small_City_LVL`, with 16 HLOD
layers and the city's world-partition record.

A working multi-angle survey needs a different mechanism (a camera actor
possessed by a Level Sequence, or an editor viewport driven across ticks —
neither reachable through `-ExecutePythonScript`, which closes the editor the
moment the script returns). Recorded in BACKLOG rather than attempted a
fourth time.
