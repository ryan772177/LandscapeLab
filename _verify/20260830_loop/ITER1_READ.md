# Concept01_Loop iter1 — the frame that shows the loop's "convergence" was not one

**Frame:** `concept_iter1_frame.png` (engine `HighresScreenshot00105.png`),
1263 × 1349, landed 13:06:43 local.
**Camera, from the payload's read-back:**

    requested  loc [0.0, 300000.0, 180.0]   rot [0, 2.031, 0]   fov 66.7
    readback   loc [0.0, 300000.0, 180.0]   rot [0, 2.030, 0]   fov 66.7
    max_loc_err_cm 0.0                      max_rot_err_deg 0.0
    ground_check "COULD NOT LOOK -- no ground hit under the camera XY"

`loop_v0.json` records `deltas: []` for this iteration. **The frame disagrees
on two counts, and a third is my own fault.**

## 1. THERE IS NO GROUND. THE VILLAGE FLOATS OVER A VOID.

    horizon row 709 of 1349
    below the horizon:  mean luma 0.0062,  54.31% of pixels EXACTLY 0.0

`Stage_Ground` is `/Engine/BasicShapes/Plane` — 1 m — at scale 4000, so it
spans **±2000 m** about the origin. Iteration 1 stages at `offset_y_m 3000.0`,
putting camera at y = 3000 m and the village at y ≈ 3082 m. **Both are off the
edge of the stage.**

**The payload's `ground_check` was not a broken guard — it was the correct
answer.** "COULD NOT LOOK -- no ground hit under the camera XY" is precisely
what a trace into empty space should say, and it said it while every other
instrument reported success.

The builder creates `Stage_Ground` ONCE, guarded by
`if "Stage_Ground" not in _labels`, at the origin — so no iteration after the
first gets ground under it, no matter how far it stages. iter0 at
`offset_y_m 0.0` is on the plane and looks correct; iter1 never could be.

## 2. IT IS STILL CLIPPED, AND THE COUNTER CANNOT SEE IT

    village columns 796..1262 of 1263  =  0.6302 .. 0.9992 of width
    touches the right edge: TRUE
    outermost chalet CENTRE predicted at fraction 0.9975

`chalets_outside_frame: 0` compares chalet **centre** bearings against the
half-FOV. A chalet whose centre sits at 0.9975 of the half-width has half its
body off-frame while the counter reads zero.

**And the widening that was supposed to fix iter0 never applied to the
chalets.** `concept_loop.main()` derives `fov1 = 2.0 * bmax / 0.90` where
`bmax` is the largest **terrain feature** bearing from `csc.bearings(concept)`
= 30.0°. That places the *terrain features* at 0.90 of the half-width. The
chalets sit at 33.22°, beyond every terrain feature, and were never re-checked
by extent against the new FOV. So the delta that closed between iterations
closed on a different quantity from the one that was visibly wrong.

## 3. THE TWO FRAMES ARE NOT COMPARABLE, AND THAT ONE IS MINE

    iter0   2032 x 1273
    iter1   1263 x 1349

I foregrounded the editor between the shots with `ShowWindow(h, SW_RESTORE)`
per R-CITYSHOT step 3, which **resized the editor window and the viewport with
it**. HighResShot captures the active viewport, so the multiplier-1 output
followed. Per `highres_shot.py`'s own warning, a frame at a different
resolution is a **different calibration class** and cannot be diffed against
its pair.

The iteration comparison this pair was taken for is therefore weaker than it
should have been. **Park the viewport size before a shot series, or take the
whole series without touching the window.**

## WHAT THE FRAME DOES CONFIRM

The two-part church reads correctly again — nave, drum, cone spire — at the
widened FOV, and the kit roofs are present on all visible chalets. Ruling 1
survives both frames.
