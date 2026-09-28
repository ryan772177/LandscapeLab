# Concept01_Loop iter0 — the first graded frame of the render batch

**Frame:** `concept_iter0_frame.png` (engine `HighresScreenshot00104.png`),
2032 x 1273, saved 2026-08-30 19:26:00 UTC.
**Camera, from the payload's own read-back, not from the plan:**

    requested  loc [0.0, 0.0, 180.0]   rot [0, 1.799, 0]   fov 60.0
    readback   loc [0.0, 0.0, 180.0]   rot [0, 1.800, 0]   fov 60.0
    max_loc_err_cm 0.0                 max_rot_err_deg 0.0

## THE LEVEL IS A TWO-BAY STAGE, AND THAT WAS MISREAD ONCE TODAY

`concept_build_payload.txt` clears prior actors by **iteration tag** (`_ITAG`),
not by concept tag. So iterations do NOT replace one another — they stage side
by side:

    Concept_iter0   36 actors   y      0.0 ->  11881.5
    Concept_iter1   36 actors   y 300000.0 -> 311881.5
    tags  LandscapeLab.Concept 72 | .iter0 36 | .iter1 36
          .greybox 38 | .kit 32

`offset_y_m` moves the camera AND the village together — `_at()` returns
`(dist*cos, _OY + dist*sin)` — which is why both iterations record identical
chalet bearings (10.99 / 33.22) and differ only in fov and pitch.

**Consequence: neither concept frame needs a rebuild.** Both geometries are
already live. The remaining iter1 shot is a camera move, nothing more.

*This was inferred wrongly twice before it was read: first that iter0 needed a
builder re-run, then that iter1's build had cleared iter0. Both came from
guessing the clear semantics instead of opening `_ITAG`. The actor query
settled it in one call.*

## MEASURED

    luma mean 0.7972   std 0.0860   min 0.1033   max 0.9593
    blown 0.000%       black 0.000%
    structured columns   0.687 -> 0.981 of frame width

    bearing 10.99 deg -> frame fraction 0.668
    bearing 22.00 deg -> frame fraction 0.850   (village centre)
    bearing 33.22 deg -> frame fraction 1.067   OFF FRAME

std 0.0860 is LOW against R-CITYSHOT's delivered frames (0.2294 oblique,
0.2037 eye level). That is not an exposure fault — it is a stage with no
landform and an untextured ground plane, and it is expected here.

## READ BY EYE — recorded separately from the measurements above

1. **The two-part church is correct and legible.** Nave box, drum, cone spire;
   tallest element in the silhouette. Ruling 1 renders as specified.
2. **The right-hand chalet is cut by the frame edge.** iter0's recorded delta
   -- "1 chalet(s) outside the 60 deg frame" -- is confirmed optically and not
   only arithmetically. This is the delta iter1 exists to fix.
3. **The ground is a blown featureless white plane.** Known and declared in the
   builder's own `deferred` list; not a defect of this frame.
4. **NEW, and not caught by the arithmetic: the roofs splay wider than the wall
   boxes.** `SM_House02_Roof` is scaled to a 10 x 8 m footprint and reads as
   drooping flaps rather than a seated gable. The loop's measurements are
   heights and bearings, so nothing in `loop_v0.json` could have found this --
   it took the picture. Logged to BACKLOG rather than fixed here.

## THE WATCHER WAS WRONG FOR THE FIFTH TIME

    HighResShot issued   19:11:58.122
    payload gave up      19:25:59.442   after 841.3 s, ok=false, RuntimeError
    frame written        19:26:00.244   0.8 s later

Five for five. The file is the artefact; the payload's verdict is a timer.

**And the log itself froze for the whole interval** -- no line between
`Cmd: HighResShot 1` at 19:11:58 and the payload's return at 19:25:59, with the
editor at 0.015-0.019 cpu-s per wall-s throughout. That is evidence, not yet a
conclusion, that the "630 s post-capture wedge" and the render are the SAME
blocking event rather than a stall that follows a completed frame. One
observation; recorded for the open BACKLOG item, which stays open.
