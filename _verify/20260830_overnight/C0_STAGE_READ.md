# C0 side-by-side, on the flat stage — the comparison that is actually valid

`C0_side_by_side_stage.png`, 2032×1273, luma mean 0.7957 std 0.1800,
blown 0.001%, black 0.000%. Left = **ORIGINAL** (Poly Haven), right =
**SWAPPED** (operator's generated set). Same mesh, same sun, same ground
height, no grid and no gizmo.

## ⭐ FIRST: THE STAGE WAS WORTH BUILDING, AND THE NUMBERS SAY SO

    luma difference, on TERRAIN   +0.185
    luma difference, on the STAGE +0.023

**89% of the "difference" I measured on the plaza was lighting, not
materials.** One house sat 2.03 m lower, in tree shade, behind a conifer. Had
that frame been read as a material comparison it would have been wrong by an
order of magnitude, and it would have looked like a confident measurement.

## WHAT THE SWAP ACTUALLY CHANGES

    metric                ORIGINAL   SWAPPED    delta
    luma                    0.7947    0.8177    +0.023
    saturation              0.0532    0.1008    +0.048   (+90%)
    warmth (R-B)           +0.0157   +0.0633    +0.048   (4.0x)
    local contrast (luma std) 0.1575  0.1580    +0.0005  (unchanged)

**The swap is almost purely a CHROMA change.** Nearly twice the saturation and
four times the warmth, with the amount of luminance detail statistically
unchanged. It did not add or remove detail; it recoloured what was there.

## ⭐ AND THE STRUCTURE READS BETTER — for a specific, measurable reason

On the ORIGINAL, the timber framing sits at nearly the same *value* as the
plaster between it, so the X-braces and posts are only just visible. On the
SWAPPED house the same members separate clearly.

**They separate by COLOUR, not by BRIGHTNESS** — which is exactly what the
numbers say: luminance contrast is identical (0.1575 vs 0.1580) while
saturation is up 90%. A half-timbered building is legible as half-timbered
because the frame reads against the infill, and on the swapped house it does.

That is the strongest thing that can be said for the swap on this evidence,
and it is a real one.

## ⛔ WHAT IS **NOT** SETTLED — the aesthetic call is the operator's

The swapped timber reads **warm orange, close to new sawn wood**. The concept
art's chalets are browner and visibly weathered. Whether the new set is
*better* is not a measurement and no verdict is offered here; the numbers say
what changed, not whether it should have.

The roof difference is subtle: both read grey, the swapped one slightly cooler
and more regular in its tile pattern.

## NOTE ON WHAT THIS FRAME COST

The first attempt rendered an **empty plane**, because the mesh and all 21
textures had never been written to disk. That is recorded in full in
`LESSONS.md` and in commit `9b10756a`; the short version is that every
editor-side check passes on an in-memory-only asset, and only the filesystem
could tell the difference.
