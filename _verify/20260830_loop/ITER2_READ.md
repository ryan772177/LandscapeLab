# ITERATION 2 — extent-derived FOV. The delta closed and the picture got worse.

**2026-08-30, overnight #2.** Authorized unit: derive the loop's framing from
chalet EXTENTS rather than terrain bearings.

## THE DERIVATION, AND WHY IT IS ONE-SHOT

    terrain outermost  30.00 deg / 0.95  -> needs half-width 31.58
    chalet edge max    35.39 deg / 0.90  -> needs half-width 39.32
    BINDING            chalet edges       fov 66.7 -> 78.6 deg

Each constraint keeps its own margin and the binding one wins, so both are
satisfied rather than one traded for the other. Terrain lands at 0.76 of the
half-width; chalets at exactly 0.90.

**It is one pass, not a loop, and that is measured rather than assumed.**
`chalet_edge_bearing_max_deg` came back **35.39 in iter0 AND iter1** — across a
60.0 → 66.7 FOV change *and* a 3000 m scene offset. It is invariant because
`concept_solve_camera.solve()` derives only PITCH from the FOV; camera XY never
moves, and a horizontal bearing depends on XY alone. A loop here would converge
on its first step and look like it had done work.

## WHAT CLOSED

    iter1   half-FOV 33.4   OUTSIDE 1
    iter2   half-FOV 39.3   OUTSIDE 0     no render-free deltas remain

`concept_iter2_frame.png` agrees with the arithmetic: the whole village sits
inside the frame with sky and ground beyond the rightmost chalet. The clipping
is genuinely gone.

## ⛔ AND THE FRAME IS WORSE THAN ITER1'S

**Widening the lens fixed the clipping by making the subject smaller.** The
village now occupies a thin strip in the right third; roughly 60% of the frame
is featureless white ground. Concept 01 is an approach shot with a basin and a
meadow — this is a horizon line with a smudge on it.

**So the loop reported "no render-free deltas remain" on its worst-composed
frame yet.** That is not a malfunction: `MEASURED_DIMENSIONS` contains
count, framing, nave, spire and fov — and **not one of them measures how much
of the frame the subject occupies.** The delta list is doing exactly what it
says; the danger is only in reading it as a verdict on the picture, which is
the failure mode `concept_loop.py` already warns about at the top of the file.

### THE NEW INSTANCE IS WORTH NAMING

Earlier the loop was blind to roof-to-wall FIT. This is different and sharper:
**the loop is blind to the cost of its own remedy.** Every one of its measured
deltas is a CONTAINMENT test — is the thing inside the frame — and containment
is monotonic in FOV. So the loop can always close a framing delta by widening,
and no measured dimension will ever object.

A gate that can be satisfied by making the lens wider will be, and it will
report success while the composition degrades to a dot on a horizon.

## WHAT I DID NOT DO, AND WHY

**FOV was the wrong free variable and I used it anyway, because it is the one
that was authorized.** The cheaper fixes are unauthorized tonight:

    move the camera closer   village_distance_m 220.0 is a concept value
    tighten the cluster      cluster_radius_m 45.0 likewise
    accept a clipped edge    a composition call, not an arithmetic one

Queued for the operator rather than decided: **add a subject-fill dimension to
`MEASURED_DIMENSIONS`** — the village's angular extent as a FRACTION of the
frame, with a floor as well as the current ceiling. A floor is what makes the
widen-until-it-fits move stop being free. That is a schema-shaped change to the
loop's contract and it is proposed, not taken.

## SCOPE OF THIS VERDICT

Unchanged and still five measured, five not. `FIT`, `MATERIAL`, `OCCLUSION`,
`LANDFORM` and anything needing a pixel remain outside — and now, explicitly,
so does subject fill.
