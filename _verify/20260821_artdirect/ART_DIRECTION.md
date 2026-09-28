# THE v22 HAIR AGAINST THE RULED LOOK — 2026-08-21

**What this is.** The comparison nobody had made. Three measured hair defects
were closed on 2026-08-21 (flat, over-the-eyes, bowl) and every one of them was
measured against an INTERNAL metric — scalp exposure, over-face percentage,
hairline spread — with the reference nowhere in the loop. This session put the
groom beside the ruled look and looked at it.

**The ruling is Ryan's and this document does not make it.** It reports what
was rendered, what the two images show, which authored parameters govern each
difference, and what could NOT be measured.

## WHAT WAS RENDERED

    editor        cold launch on /Game/Alpine8K, rule 7 verified
                  305988AB47BCE2F90404FE9F215CBE55, 5.8.1-56057345
    subject       HeroInWorld, the SAVED actor (--respawn no; nothing saved,
                  tracked tree clean afterwards)
    grooms        Hair_v22_bound_b / BND_Hair_v22b, Beard_S_Full,
                  Eyebrows_M_Dense, Mustache_S_Full
    framing       dist 110, fov 26, cam-up 152, look-up 158, 2048 square
                  -- the registry's declared `comparison_framing`, which is
                  what compare_to_reference.py's fixed crops are quoted for

    FRONT_v22_d110_20260822T055012Z.png    the frontal
    REAR_v22_d110_20260822T055154Z.png     the rear, level camera
    REAR_v22_sky_20260822T055402Z.png      the rear, pitched 24.4 deg up
    SHEET_front_v22.png                    reference | current
    SHEET_rear_v22.png                     reference | current  (LAYOUT ONLY)

**The gate ran first and called it a DIAGNOSTIC, correctly.** At this framing:

    Beard      PRESENT   26,934 px  15.8x floor  crown  5%  drift 1.3%
    Eyebrows   PRESENT   11,241 px   6.6x        crown 83%  drift 2.7%
    Hair       PRESENT   87,736 px  51.6x        crown 96%  drift 0.4%
    Mustache   ABSENT     3,523 px   2.1x        crown 38%  drift 11.9%

Mustache ABSENT at 1.1 m is the standing caveat, not a regression. **Hair at
51.6x floor and crown 96% matters here for one reason: it rules out "the hair
did not draw" as an explanation for anything below.** The groom is on him, it
is bound, and it is covering the crown. What follows is about the CUT.

## WHAT THE TWO SHEETS SHOW

**The reference is a long, layered, shaggy mid-length cut. v22 is a short
crop.** This is a difference of CLASS, not of tuning, and it is the headline.

Frontal:

1. **The ears.** The reference's hair falls over and past both ears. v22
   leaves both ears fully exposed, with bare skin above them.
2. **The fringe.** The reference's defining feature is a heavy, irregular
   fringe hanging FORWARD over the forehead to the brow line, with side locks
   reaching the jaw. v22 has no fringe at all — the hairline reads as a clean
   high edge and the front is swept back over the crown.
3. **The silhouette.** Reference: wide, irregular, spiky, standing off the
   skull. v22: a smooth close cap following the skull.

Rear:

4. The reference covers the whole occiput and reaches the collar, tapering
   into choppy points, ears half covered. **v22 ends in a shelf at the
   occiput** with a small central tuft below it, and the nape and neck are
   bare.

## WHAT MATCHES, SO IT IS NOT ALL ONE WAY

- **The three closed defects really are closed.** No strands over the eyes, no
  slicked-flat skull, no ruled bowl line. Those fixes hold in the render.
- **The beard is close.** Coverage and density read like the reference's
  stubble beard; it is the strongest match on the character.
- The hair sits on the head correctly — no floating, no scalp gaps, no
  clipping through the skull.

## THE INTERPRETATION THAT MATTERS

**Two of the three fixes moved TOWARD the reference. One moved AWAY from it,
and it is separable into a half that should stay and a half that should not.**

R-HAIRVOLUME (body) and R-HAIRSHAPE (breaking the bowl) both move toward a
shaggy layered cut. R-HAIRFACE drove hair off the face — over-face 5.62% to
0.76% — and the reference's single most recognisable feature is hair falling
over the forehead and temples.

The ROOT half of R-HAIRFACE is correct and must stay: roots were growing on
the brow and eyelids at z <= 168.7 against a hairline at 171.68, and normals
there belong to sockets and cannot be trusted. Hair does not grow out of an
eyelid in any haircut.

The STYLING half is what removed the reference's fringe. `front_sweep_gain`
2.00 and `back_bias` 1.00 drive front-rooted strands backward over the crown.
**Roots off the brow and tips falling forward are not in conflict** — the
reference is exactly that: a normal hairline with long hair falling from it.

## THE LEVERS, WITH THEIR AUTHORED MEANINGS

From `scripts/blender/author_hero_hair.py` PARAMS, which is the declaration of
record. **None of these has been tested this session** — they are named so a
re-authoring pass can move one knob at a time in the 40-second Blender loop
rather than guessing in a 4-minute UE round trip.

    len_side_cm        6.5   sides stop above the ears; the reference's side
                             locks reach the jaw
    len_nape_cm        4.5   with nape_frac 0.58, this is the bare nape; the
                             reference reaches the collar
    len_fringe_cm      6.0   too short to reach the brow from an 0.82 hairline
    len_top_cm        12.0   the only genuinely long region
    front_sweep_gain   2.00  drives the fringe BACK over the crown
    back_bias          1.00  pushes hair away from the face as it falls
    hairline_frac      0.82  a high front hairline
    layer_gain         0.30  length by root depth -- documented as unable to
                             touch the fringe edge (measured 0 -> 0.70 moved
                             it 0.694 -> 0.689 cm), so it is not the lever for
                             item 2 above

## WHAT COULD NOT BE MEASURED — this is not a pass

**1. THE REAR RUBRIC PRODUCED NUMBERS OVER THE WRONG REGION, TWICE, AND EXITED
0 BOTH TIMES.** `rear_metrics.py` is calibrated on the reference, which is a
flat-lit portrait on plain grey. Against a sunlit in-world render it fails in
two different ways:

    level camera   the dark shadowed forest behind the head fuses with the
                   hair into one blob. crown_width_px 1322 in a 2048 frame is
                   FOREST. edge_roughness 283.4 against the reference's 27.96.
    sky behind     the mask is a hollow RING -- the sunlit crown is brighter
                   than luma_max 70, so only the silhouette rim survives.
                   Area understated, perimeter doubled, edge_roughness 142.8.

Its `mask_frac` band [0.005, 0.50] passed both, because a wrong region can be
the right SIZE. **No rear number is reported.** Both masks are on disk —
`rear_mask_render.png`, `rear_mask_sky.png` — and the tool's own docstring
demands they be looked at before its numbers are believed, which is what
caught this.

**2. COLOUR IS STILL UNJUDGED against either reference**, by design:
`compare_to_reference.py` refuses to compare colour numerically because the
reference is flat studio light and ours is a low warm alpine sun with half the
face in shadow. An RGB difference between those is a statement about the lamps.

**3. THE EYE COLOUR IS UNCHANGED AND STILL UNVERIFIED.** Not attempted.

## THE INSTRUMENT THAT WOULD CLOSE THREE THINGS AT ONCE

A flat-lit close rig against a plain background — the same thing the eye-colour
item has needed for four sessions — would make the rear rubric measurable, make
a colour comparison meaningful, and let the iris be read. It is one instrument
serving three open items, and it is the recommended next unit if the ruling
below is "re-author".

## THE RULING THIS DOCUMENT EXISTS TO ENABLE

**Is the v22 cut acceptable as the hero's hair, or should it be re-authored
toward the reference's long layered shag?**

If ACCEPTED, the hair track closes and the levers above are noise.
If RE-AUTHORED, the work is a Blender-side pass on the four length parameters
plus the two sweep drivers, tested one knob at a time against the bare-head
control, and the UE trip proves the groom rather than the haircut.
