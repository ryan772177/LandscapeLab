# Survey shots — status across all four projects

**One project of four has a real multi-angle survey.** This records what
worked, what did not, and the one thing I still cannot explain.

| project / map | shots | route |
|---|---|---|
| **Electric Dreams — far range** | **5 of 5, verified by eye** | remote exec + `shoot.py` |
| Electric Dreams — close range | 0 of 5 | same route, editor wedged |
| Dark Ruins | 0 of 5 | same route, shots issued, no frames written |
| City Sample | 5 frames, ONE viewpoint | `-ExecCmds`, camera never moved |
| Valley of the Ancient | none | editor cannot open (C++ source port) |

## What is proven

`-ExecCmds` **cannot** do this. Four attempts across two projects, escalating
`r.HighResScreenshotDelay` 8 → 900 → 1200 frames and adding `ghost` no-clip
flight. It fires every command in one batch at startup, so `HighResShot`
lands before the teleport reaches the rendered view. The delay fixed the
*capture* (0 → 1 → 5 frames filed) and never fixed the *camera*.

Remote execution + `shoot.py` **does** work — it moves the editor viewport and
waits host-side, so the editor stays alive and ticking. Electric Dreams'
far-range map produced five genuinely distinct frames: a mesa vista with
distant mountains, a forest-floor close-up with ferns and dappled light, a
steep overview. That set is the proof the route is sound.

## What failed, and honestly why I do not know

Two projects ran the *same* tooling against a *fresh* editor and produced
nothing:

    Electric Dreams close range   one HighResShot issued, then the log went
                                  SILENT for 20+ minutes. Wedged.
    Dark Ruins                    HighResShot issued at 21:40 and again at
                                  21:50 -- so the editor kept accepting
                                  commands -- and NO frame was ever written.
                                  Not wedged; just producing nothing.

Those are two *different* failure shapes, which argues against a single tidy
cause. Untested candidates:

* the close-range world is 71 × 68 m against far-range's 3.3 km, so a station
  could sit inside geometry;
* Dark Ruins is a dark interior scene and its earlier `-ExecCmds` frames
  measured mean luma 1.55–2.06 out of 255 — whether that is the map or the
  camera is still unresolved;
* editor state accumulated across a survey plus two census runs in one
  session (but Dark Ruins had a fresh editor, which weakens this).

**No cause is claimed.** Every explanation above is a hypothesis I did not
test, and this session has produced enough confident-sounding wrong ones.

## The trap that nearly filed a false success, four times

`Main__wide_vista.png` and its siblings existed in the output directory from
the earlier `-ExecCmds` run — the *same filenames* the new survey writes. A
file count said "5 filed". The mtimes said ninety minutes stale.

That is the fourth instance in this session of asking *"is there a file?"*
when the question is *"is there a file **from this run**?"* — after
`capture_truth` globbing a station PNG, the LOD driver matching `lod0` by
substring, and `wait_for` returning on mere existence.

The fix here was structural, not vigilance: the stale set was moved to
`_trash/darkruins_execcmds_oneviewpoint/` so the directory was **empty**, and
any PNG appearing in it could only be from this run.

## To finish this

The `-ExecCmds` sets for City Sample and Dark Ruins stay, with their READMEs
saying plainly that they are one viewpoint. They are genuine project content
and useful as a record of the look; they are not surveys.

A working survey for the remaining three needs the frame-write failure
diagnosed first — not another run of the same tooling.
