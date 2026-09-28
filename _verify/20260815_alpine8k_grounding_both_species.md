# Grounding on Alpine8K — both species, two representations

Measured 2026-08-15. This closes a debt CURRENT STATE recorded as open, and
it is the FIRST time the 61,277 Scots pines have been traced by any
instrument at all.

## Instrument 1 — heightmap, ALL instances (coverage)

`scripts/verify_grounding.py --recipe recipes/alpine_8k.json`, tolerance
±0.050 m:

    species        count      mean      p50      p99      max   outside
    Conifer       92,519     0.000    0.000    0.001    0.001         0
    ConiferPine   61,277    -0.000   -0.000    0.001    0.001         0

**Quoted with the limitation the tool states about itself:** the planner and
this check read the same heightmap through the same transform, so a shared
transform error is invisible to both. This is COVERAGE across every one of
153,796 instances — not a non-negotiable-0 result.

## Instrument 2 — engine COLLISION, 500-sample per species (independence)

`scripts/trace_grounding.py --n 500`. Gap is
`pivot_Z + sink - landscape_hit_Z`; positive means floating.

    species        hits        min      p50      p90      p99      max   floating  buried
    Conifer     500/500     -0.078   +0.006   +0.013   +0.049   +0.100      0        0
    ConiferPine 500/500     -0.091   +0.006   +0.015   +0.084   +0.169      0        0

Thresholds: floating > 0.45 m (the epsilon derived from measured collision
quantisation), buried < -0.24 m. Both species: **zero of either.**

## Why the pair is the result, not either alone

Non-negotiable 0 requires a confirming instrument that reads a DIFFERENT
representation. Instrument 1 reads the authored heightmap; instrument 2
traces against the engine's collision heightfield. They share no source, and
they agree: p50 +0.006 m on both species, maxima of 0.100 and 0.169 m — well
inside the 0.305 m collision-vs-heightmap quantisation this world measured
at `ad05ba74`.

**The Scots pine result is the new information.** It carries 40% of the
forest and had never been traced. Its numbers are indistinguishable from the
spruce's, which is what "the placement transform is correct for both" looks
like.

## Note on a diagnostic line in the tool's output

`trace_grounding` prints `first hit classes` as a `dir()` listing of the hit
struct rather than a class name. Cosmetic — the counts above come from
`landscape hits : 500 of 500`, and the raw-hit-any-class control also reads
500, so the accessor is finding real hits. Not a defect in the measurement;
worth tidying if that tool is next edited.
