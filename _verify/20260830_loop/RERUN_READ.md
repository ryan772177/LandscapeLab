# THE CONCEPT LOOP, RE-RUN ON THE FIXED ROOF PLACEMENT — 2026-08-30

**Both iterations rebuilt in a verified editor** (rule 7: one node, project
matches `UE_PROJECT_ROOT`, 5.8.1; rule 11: zero editors before launch, level
measured as `/Game/Scratch/Concept01_Loop` before any mutation).

`ITER0_READ.md` and `ITER1_READ.md` are the ORIGINAL reads and are left as
written — they record what was true when they were written, and what was true
was wrong.

## WHAT MOVED

    chalet SILHOUETTE   536.5  ->  738.0 cm
    church nave         804.8  -> 1107.0 cm   (1.50x, unchanged ratio)
    church spire       1341.3  -> 1845.0 cm   (2.50x, unchanged ratio)

The RATIOS never changed and were never wrong. `nave_over_silhouette` was
1.50 and `spire_over_silhouette` 2.50 before and after — the loop was
correctly building the ruled proportions **against a reference that was 27%
short**, because the kit roof was sunk 201.49 cm into the walls it sat on.

## THE INDEPENDENT AGREEMENT, WHICH IS THE POINT

The re-run's spire lands at **1845.0 cm**. The forge's stage 10, a completely
separate code path with its own chalet assembly, placed the forged church at
**1845.0 cm** earlier the same day.

Those two numbers were 1341.3 in both places before the fix, and they are
1845.0 in both places after it. **Two paths that share a defect agree; two
paths that share a correction also agree** — so this is consistency, not
proof, and it is worth exactly as much as the measurement each side did
independently. What makes it evidence is that the fix was applied to the two
payloads separately and neither reads the other's output.

## WHAT DID NOT MOVE, AND SHOULD NOT HAVE

    iter0  framing 4 chalets outside the 60 deg frame  + fov at 1.00
    iter1  framing 1 chalet outside the 67 deg frame

Identical to the pre-fix run. Correct: those deltas are HORIZONTAL — bearings
from the camera to the cluster — and the roof fix is entirely vertical. A
delta list that had shifted here would have meant the fix reached something it
had no business touching.

**So the loop still has not converged, for the same reason as before**, and
the authorized next unit is unchanged: extent-derived FOV.

## OPTICAL CONFIRMATION

`concept_iter1_roofseated.png`, shot at the SAME camera as
`concept_iter1_reshoot.png` — loc [0, 300000, 180], rot [0, 2.031, 0], fov
66.7, read back to 0.0 cm / 0.0 deg error — so the two frames differ only by
the fix.

    before   thin dark arches smeared across the tops of the wall boxes;
             the chalets read as plain white boxes
    after    gabled roof masses SITTING ON the walls, with visible pitch and
             volume; the chalets read as houses, and the spire is taller

## NOT CONTAMINATED: the town plan

`city/alpine_basin_town_plan.json` carries `ridge_height_cm` values near this
range (564.6, 790.6, 511.6) and one of them is close to 536.5. **Coincidence,
checked rather than assumed**: `plan_city.py:504` derives it as
`round(w_o * 0.5, 1)` — half each roof's own overall width, per building. It
does not read the chalet silhouette. The 303-building plan is unaffected by
this defect.
