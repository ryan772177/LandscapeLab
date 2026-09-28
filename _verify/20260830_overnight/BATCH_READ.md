# The render batch, delivered 2026-08-30 — and the watcher fix proved in the doing

Three frames, three levels, all at **2032 × 1273** (pinned), all through
`scripts/shoot.py`.

## ⭐ THE HEADLINE IS THE COST, NOT THE PICTURES

    frame issued -> on disk, BEFORE the fix    848 s  and  843 s
    frame issued -> on disk, AFTER the fix       4 s,   4 s,   4 s

**The render was never slow. The watcher was preventing it.** The payload slept
on the game thread; `HighResShot` completes over engine ticks; so the frame
could not be written until the watcher gave up at its 841 s deadline. Moving
the wait to the host took ~14 minutes per frame down to **4 seconds** — and the
whole 3-frame batch, previously budgeted at ~45 minutes of dead channel, cost
about 90 seconds of rendering.

Total wall time per shot is 31 s, of which **25 s is `ue_exec`'s discovery
window** — the render is now the cheapest part of taking a frame.

R-CITYSHOT AMENDED 2026-08-30c is hereby PROVEN, not merely built.

## 1. `concept_iter1_reshoot.png` — the two builder fixes confirmed optically

    2032 x 1273   luma mean 0.7920  std 0.0914  blown 0.000%
    exact-zero pixels below the horizon:  0.00%   (was 54.31%)

**The void is gone.** `Stage_Ground` grew 4000 → 8162.5 (±4081 m) for an
iteration staged at 3000 m, derived from need rather than declared.

**And the framing counter now agrees with the photograph.** With edges instead
of centres:

    iter0   chalets_outside_frame 4   (centre-only said 1)   edge_max 35.39
    iter1   chalets_outside_frame 1   (centre-only said 0)   edge_max 35.39

Predicted frame fraction for a 35.39° edge against iter1's 33.35° half-FOV is
**1.040 — off frame**, and the village does still run to the right edge.
Instrument and picture now say the same thing.

⛔ **CONSEQUENCE: THE LOOP HAS NOT CONVERGED.** `deltas: []` for iteration 1
this morning was an artefact of the centre-bearing bug. It now correctly
reports `1 chalet(s) outside the 67 deg frame`. Closing it needs the FOV
derived from **chalet extents** rather than terrain-feature bearings — already
on BACKLOG as "THE ITER1 FOV WIDENING FIXED THE WRONG QUANTITY", and NOT done
here because it is a design change beyond the reshoot ruling.

## 2. `c0_stage_graded.png` — the graded donor pair

    2032 x 1273   luma mean 0.8114  std 0.1833  blown 0.008%  black 0.000%

Both houses render fully: timber framing, shingle roof, stone base, window
openings. **The 47-files-on-disk verification holds up visually** — this is the
frame class that came back an empty plane before `verify_on_disk.py` existed.

The grade difference reads as intended, ORIGINAL cooler/greyer against SWAPPED
warmer in the timber. Subtle at this framing; a tighter crop would judge it
better if a finer call is ever needed.

*Cosmetic, not a defect: the stage ground ends in a black band at the horizon.
The subject sits well inside it.*

## 3. `hair_stage_variants.png` — and an editor sprite that ate a variant

    2032 x 1273   luma mean 0.6338  std 0.1840  blown 0.000%

**The yaw-90 ruling is confirmed.** The cards render FACE-ON as tapered strand
geometry, not the edge-on slivers of the first attempt.

### ⛔ THE FIRST TAKE WAS UNUSABLE AND EVERY TONAL CHECK PASSED

The `DirectionalLight`'s **editor billboard sprite and its blue arrow** rendered
directly over the CENTRE variant and hid it completely. Three variants staged,
two judgeable. The frame measured mean 0.6049, std 0.1873, 0.000% blown — **a
sprite is perfectly well-exposed content as far as a histogram is concerned.**

This is R-CITYSHOT step 1's lesson with a different flag: the 2026-08-27
oblique carried orange nav wireframes for exactly the same reason. Now issued
in the payload, names verified in `ShowFlagsValues.inl` (`BillboardSprites`
:213, `LightRadius` :291) rather than recalled. Re-shot; cost 4 seconds.

### THE THREE VARIANTS ARE MEASURABLY DISTINCT — AND MY FIRST LABELLING WAS BACKWARDS

Staged positions, read from the editor rather than inferred from the frame:

    Hair_Hero_A  x -80.6   MI_Hair_Hero
    Hair_Hero_B  x   0.0   MI_Hair_Hero
    Hair_NPC     x +80.6   MI_Hair_NPC

**UE's right-vector at yaw 90 is −X, so screen-left is +X** — the image order is
mirrored relative to the X layout:

    screen  actor        material        strand px   luma     R-B warmth
    left    Hair_NPC     MI_Hair_NPC        2346     0.2721      0.063
    centre  Hair_Hero_B  MI_Hair_Hero       2440     0.2568      0.111
    right   Hair_Hero_A  MI_Hair_Hero       2520     0.2537      0.102

Corrected, the result is the expected one: **the two `MI_Hair_Hero` instances
cluster together and `MI_Hair_NPC` is the outlier** — cooler and lighter.

*Had the screen-position guess been reported, it would have claimed the two
Hero variants differ MORE than Hero-vs-NPC — the exact opposite. A camera
convention is not a thing to infer from a picture when the level can be asked.*

## WHAT THE BATCH COST

    3 editor launches (scratch levels need their own; open_level.py wants a
      landscape recipe and hand-rolling a load payload is a known crash)
    4 shots (one re-shot for the sprite defect)  ~16 s of rendering in total

⚠ **One process error worth recording:** the first editor did not honour
`CloseMainWindow` within 20 s and a second was launched on top of it, so two
editors briefly served the same project and either could have answered
discovery. Caught before any remote work, resolved by stopping the superseded
PID. **Wait for zero editors before launching the next one** — the level query
that confirmed each editor's map is what makes this safe, and it should stay
mandatory between levels.
