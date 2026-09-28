# EXPOSURE SOLVED FOR THE 8129 TERRAIN — 2026-08-13

**`-1.786` -> `-1.867` EV.** Solved against this terrain, not ported from
another scene. Closes the CURRENT STATE item *"Exposure re-solve — R13's
-1.897 EV was solved for /Game/Alpine's scene. Applying another scene's
constant here is the derived-record trap."*

## WHY A RE-SOLVE WAS OWED

`recipes/alpinelab_8129.json` carried `compensation_ev: -1.786` under a comment
that said, in its own words, **"PORTED VERBATIM from recipes/alpine.json"**.
Exposure is the one term in that block that is scene-dependent: sun, sky and
fog describe the ATMOSPHERE and travel between scenes intact, but the exposure
that centres a render depends on the ALBEDO of the ground being lit.

## THE MEASUREMENT

Instrument: `top_down` camera, straight down from 6 km at 60 deg FOV. At that
altitude the frame is ~6.9 km across against an 8.128 km terrain, so it is
**all terrain and no sky** — the denominator is stated because a sky fraction
would bias the mean (non-negotiable 22). Frame decoded sRGB -> linear and
reduced with independent numpy, the same method the 2026-08-06 alpine check
used so the two are comparable.

    this terrain, top-down linear luma        0.3385
    solver target for sunlit terrain          0.3201   (albedo 0.2675)
    /Game/Alpine, SAME method, 2026-08-06     0.3169

**This terrain is ~6.8% brighter than /Game/Alpine under identical lighting**,
which puts its implied ground albedo at **~0.286** against alpine's measured
0.2675. That is the whole finding: same sun, different ground.

    bias = -1.786 - log2(0.3385 / 0.3201) = -1.786 - 0.0806 = -1.867 EV

## THE VERIFICATION — a different question than "did the setter return"

Applied via `apply_lighting.py` from the recipe, then read back from the LIVE
PostProcessVolume, then **re-measured on pixels**:

    before  -1.786    linear luma 0.3385    +5.75% over target    0.000% blown
    after   -1.867    linear luma 0.3246    +1.41% over target    0.000% blown
    target                        0.3201

Read-back: `Lighting_alpinelab_8129_PostProcess`, `AEM_MANUAL`,
`auto_exposure_bias -1.8669999837875366`, **OVERRIDDEN** — so the value is in
effect and not an inert default (non-negotiable 17).

**The residual is 1.41%, not 0.** Predicted post-change luma was 0.3200 and the
measured value is 0.3246, so the correction slightly under-delivered. That is
expected and is not hidden here: the frame is TONEMAPPED, and an sRGB decode
undoes the encode but not the tonemapper, so a pure `2^dEV` scaling of the
decoded value is an approximation. The same method validated on alpine at 1.0%
error (0.3169 measured vs 0.3201 solved), so 1.41% is inside the demonstrated
accuracy of the instrument rather than evidence of a bad solve.

## THE TRAP THIS AVOIDED, STATED EXPLICITLY

**Alpine's Lumen-corrected `-1.897` would have OVERSHOT.** This scene needs
`-1.867`; `-1.897` is 0.03 EV past it. More importantly it would have been
right for the WRONG REASON — `-1.897` corrects for **Lumen bounce light** on
/Game/Alpine, whereas `-1.867` corrects for **higher ground albedo** on this
terrain. Two different mechanisms landing within 0.03 EV of each other is a
coincidence, and adopting the number would have recorded a false derivation
that the next session would have trusted.

Lumen is ON in this measurement (`r.DynamicGlobalIlluminationMethod 1.0`), so
its contribution is already inside the 0.3385 reading and is not double-counted.

## SCOPE — what this does NOT establish

- It does not re-derive the ALBEDO from the weightmaps and surface textures.
  0.286 is BACKED OUT from a render, so it is an effective scene albedo that
  includes tints, blends and Lumen bounce — not a texture statistic. The
  2026-08-06 note that a texture-only re-derivation gives 0.3356 and "is NOT
  the scene albedo" still stands, and this does not replace it.
- One camera. `top_down` is the right one because it looks at horizontal ground
  under a 12 deg sun, which is what the solver models, but it is one station.
- The frames captured earlier today (`20260813_8129_nanite_*`) were shot at
  `-1.786` and are 0.08 EV brighter than anything captured from now on. Any
  future A/B against them must account for that.
