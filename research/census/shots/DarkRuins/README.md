# Dark Ruins shots — ONE VIEWPOINT, and very dark

**Not a five-angle survey.** Same failure as the City Sample set, plus a
second problem.

    all five frames   mean luma 1.55-2.06 out of 255 -- near black
    pairwise diff     min 0.02 -- effectively identical images
    BugItGo           fired correctly every time, e.g.
                      "BugItGo to: X=7169.4 Y=5761.6 Z=15447.5 P=-55 Y=20"

## What the fourth attempt DID fix

The capture timing. `r.HighResScreenshotDelay` went 8 → 900 → 1200 frames and
the dwell 75 → 150 s:

    delay    8 frames   0 of 5 filed
    delay  900 frames   1 of 5 filed
    delay 1200 frames   5 of 5 filed

So the shot now reliably lands. That part of the hypothesis was right — the
screenshot was being requested before the world was ready.

## What it did NOT fix

The camera never moves. `-ExecCmds` fires every command in one batch at
startup, and no amount of *capture* delay changes when the *teleport* takes
effect relative to the view being rendered. Four attempts:

    1  plain BugItGo                     five frames of one view
    2  ghost (no-clip) + delay 8         five frames of one view
    3  ghost + delay 900, dwell 110      one frame, same view
    4  ghost + delay 1200, dwell 150     five frames, one view, near black

The frames are genuine Dark Ruins content — a dark ruins interior with
embers — so the project loaded and rendered. They are just all the same
place, and that place is unlit.

## Stopping here, deliberately

This is the fourth bounded attempt. Continuing would be guessing at a
mechanism rather than reasoning about one. The two routes that could actually
work are recorded in BACKLOG:

* **MRQ with a camera possessed by a Level Sequence** — the `Bench_Dolly`
  pattern, which works in our own project and does not depend on `-ExecCmds`
  timing at all.
* **`bRemoteExecution=True` in the sample's `Config/DefaultEngine.ini`**,
  which would let `ue_exec` and `shoot.py` drive these projects the way they
  drive ours. That is a config write outside this repo — standing rule 1
  names it, and the census waiver covered opening and converting, not that.
  **Needs an operator ruling.**

## The metric that cannot judge this

`shot_differentiation` reports `NO VERDICT` and that is deliberate. Calibrated
against a known-bad set it scored the FAILURE 10.37 and the SUCCESS 9.77 —
backwards. Shader compilation between launches recolours a static scene by
more than a camera move changes it. **These frames were judged by eye.**
