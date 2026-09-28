# Hair strips — what the frame shows

`hair_strips.png`, 2032×1273, luma mean 0.5956 std 0.1991, blown 0.000%,
black 0.000%. Tonally non-trivial, so it is safe to read.
Landed at 02:35, **after the watcher gave up at 841.2 s — the fifth time.**

## ⭐ THE UV QUESTION IS ANSWERED: THE CARDS DO LAND ON THE MASK SHEET

The strands render as **individual cut-out shapes with ragged, feathered
edges** — not as solid rectangles and not as nothing. That is exactly what a
correctly-aligned opacity mask looks like, and it is the one thing this frame
was needed for. The brief said report rather than re-UV; **there is nothing to
report as broken.**

The colour reads olive/brown-warm, which is the root→tip lerp between concept
02's measured shadow and sun rgb doing what it was built to do.

## ⛔ THE FRAME ITSELF HAS TWO DEFECTS, BOTH MINE

1. **The editor drew its own UI into the shot.** The reference grid covers the
   whole ground plane, the red/green world axes run through the middle, and the
   **rotation gizmo of the last-selected actor is drawn as a large protractor
   directly over the centre strip.** On the open world this was invisible
   against terrain and foliage; on a bare scratch stage it dominates.
   *Fixed in the payload* — `ShowFlag.Grid 0`, `ShowFlag.Navigation 0`, and the
   selection is cleared, because no ShowFlag removes the gizmo.
2. **The camera looks into the cards EDGE-ON.** The mesh is 40.4 × 0.7 × 31.1
   cm — a flat sheet in X-Z with 7 mm of depth in Y — and the camera looked
   along **+X**, straight into that 7 mm edge. The strands read as thin
   slivers. The camera must look along **Y** to see the card face.

Neither defect touches the material. Both are framing, and both are fixed
before the remaining frames rather than after.

## WHAT IS NOT JUDGED

Root and tip colour. They are placeholders from concept 02's palette and the
operator's swatches are gated, so no opinion on the colour is offered.
