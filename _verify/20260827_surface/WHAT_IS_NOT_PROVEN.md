# Unit 11: what the render DID and DID NOT settle — 2026-08-27

Superseding the earlier version of this file, which recorded the independent
check as not obtained. It was obtained on the third attempt.

## The acceptance clause is MET, for the class that can carry it

`PHASE2_PLAN` unit 11 asks for a positive control that the query agrees with
**the material's own layer choice**. The bake's own controls could not supply
that — they compare the lookup to the material's INPUT, the same weightmap, and
non-negotiable 0 says instruments sharing a source are one measurement.

A top-down render is a different representation. `verify_surface_against_render.py`
samples it at 30,000 points, maps each pixel to world XY, and asks the lookup
what should be there:

    samples 30,000   off the landscape 19,006   blended-out 113
    usable  10,881 (36.3%)

    layer        n     mean luma      std
    Snow      2260        0.7703   0.1349
    Rock      4085        0.7064   0.1178
    Grass     4536        0.6940   0.1002

    Snow brighter than Rock   by +0.0638   (margin required 0.02)
    Snow brighter than Grass  by +0.0763

**The classes the lookup assigns separate in the pixels the material drew.**
Snow's base colour is 1,1,1 over Snow006, so it should be the brightest surface
in the palette, and it is — by three times the required margin.

## What this is NOT, stated so nobody quotes it as more

**It is not a per-pixel equality and cannot be.** The material blends three
photogrammetry surfaces under a low sun with fog and a tonemapper; no pixel
value "is" Rock. What is asserted is ORDERING WITH A MARGIN, which belongs to
the material's layer definitions; the absolute values belong to the lighting
rig.

**ROCK AND GRASS ARE NOT SEPARATED BY THIS TEST.** They differ by 0.0124 in mean
luma against per-class standard deviations of 0.10–0.12 — inside the noise. The
test deliberately does not assert that pair, and a future version that wanted to
would need chroma rather than luma, or a flat-lit rig. So:

- Snow vs everything: **corroborated by a second representation**
- Rock vs Grass: **corroborated only by provenance** — both read the weightmap

**Only 36.3% of samples were usable**, because a 90° top-down frame from 900 km…
from 9 km altitude covers 16.9 × 10.6 km against an 8.1 km landscape, so most
samples land off the map. That is reported rather than hidden; a filter that
quietly removes most of the data cannot support a conclusion, and the tool
refuses below 20%.

## The mapping, because it is the easiest thing to get silently wrong

UE's FOV is HORIZONTAL, so the vertical half-extent is scaled by
height/width — 2032 × 1273 here. Reversing that stretches the sample grid and
compares the wrong pixels while still producing plausible-looking numbers. The
projection plane is the MEAN TERRAIN HEIGHT (523 m), not z = 0: over 1.5 km of
relief, assuming zero would shift every sample outward.

## How the frame was obtained, since it took three attempts

Two attempts produced nothing in ~25 minutes. The third succeeded — and the
frame from the SECOND attempt landed anyway, after its driver had been stopped:
the editor had accepted the `HighResShot` and completed it later. The editor
reads `responding=False` while doing this, which looks like a hang and is not:
measured at **6.04 CPU-s per wall-second**, it was working the whole time.

One attempt was wasted on my own error — `ue_exec --timeout 900`, where that is
the DISCOVERY window and is spent in full.
