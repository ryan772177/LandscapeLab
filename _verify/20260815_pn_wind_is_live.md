# The PN spruce wind ANIMATES with no Blueprint — measured

2026-08-15, scratch level `/Game/Scratch/TreeQuadPN`, R13 lighting borrowed
from `recipes/alpine_8k.json`. Station `canopy_close`: `spruce_half_01` at
12 m, camera pitched up, 1280x720.

## Method

Three `highres_shot` frames from ONE parked camera, ~5 s apart, nothing
touched between them. `PN_GlobalUpdater` and `PN_Bending_Component` were
never placed — no Blueprint of any kind is in this level.

## Result

    frames        mae      vs 0.00298 floor   px >2%   max local
    1 vs 2      0.00611        2.05x           4.36%     0.7333
    1 vs 3      0.00410        1.38x           3.66%     0.6824
    2 vs 3      0.00561        1.88x           4.27%     0.7255

**The mean is modest and the mean is the wrong statistic.** 2.4% of the
frame changes by more than 10%, and local differences reach **0.73** — a
concentrated change diluted across a mostly-empty frame, which is the
misleading-denominator shape (NN22).

Conditioned on where it happens:

    row band            mean|diff|   px >2%
    top 25% (sky)         0.00733     1.79%
    upper mid (canopy)    0.01964    10.32%
    lower mid             0.00757     4.27%
    bottom 25% (ground)   0.00483     1.04%

## What makes it evidence rather than a number

The amplified difference image is a **clean silhouette of the tree**:
canopy saturated, the bare lower branches picked out individually, sky and
the flat untextured ground plane essentially black.

A static scene re-rendered twice produces TAA/jitter noise spread along
edges everywhere. This is not that. The change is confined to the geometry
that would move if wind were displacing it, and absent from the two large
regions that cannot move — the sky and a flat plane. **The spatial pattern
matches the mechanism**, which is the standard this project holds a
measurement to.

Artefacts: the frames are `HighresScreenshot00037-39.png`; the diff
visualisation was generated at 6x amplification.

## Consequences

1. **The wind needs no `PN_GlobalUpdater`.** The D2 ruling deferred wind on
   the grounds that the Blueprint is a runtime dependency and wiring it
   would breach pipeline rule 1. That reason does not apply — the material
   drives the animation from engine Time on its own. **The ruling's
   CONCLUSION still stands, for a different and better reason:** an
   animating canopy makes every frame-to-frame comparison non-deterministic.

2. **The removal mechanism is cheap and touches no vendor byte.** Wind is
   carried on STATIC SWITCH parameters — `Level 1 Wind`, `Level 2 Wind`,
   `Level 3 Wind` (and the three `Bending` siblings) — on `MA_Summer`,
   `MA_Winter` and `MA_Imposter`. A static switch set false in a Material
   Instance COMPILES THE BRANCH OUT rather than merely zeroing it. So
   wind-off child MIs in a tracked folder achieve it with the vendor pack
   left byte-identical, which matters because the pack is gitignored with
   0 tracked files and git cannot restore an edit to it.

3. **OPEN, AND IT REACHES BACKWARDS.** The forest already standing in
   `/Game/Alpine8K` is 153,796 Megaplants/PVE trees whose materials have
   NEVER been tested for this. If they animate too, then every PIXEL
   comparison taken on that world since the spruce adoption has an inflated
   noise floor — including the canopy A/Bs. **Frame COST is unaffected**
   (that is a timing measurement, not a pixel one), so the 8.14 -> 7.76 ms
   result stands. The check is one park plus three shots in Alpine8K and it
   has not been run, because loading that world is expensive and this is not
   blocking D2.

4. **The project's 0.00298 noise floor was derived on terrain**, before any
   animated foliage existed. It should not be quoted against a
   vegetation-filled frame without re-deriving it.

---

## Addendum — the wind-off overrides, PROVEN BY RENDER

Seven child Material Instances created under `/Game/Materials/PN_NoWind/`
(ours, tracked), each parented to the vendor MI it replaces, with all six
static switches set false. **No vendor byte written** -- `check_fab_boundary`
unchanged.

Applied to `Scratch_spruce_half_01` via `override_materials`, then the
SAME three-frame test re-run from the SAME parked camera:

    BEFORE  wind ON (vendor materials)
      1v2  mae 0.006112   px>2%  4.36%   max 0.7333
      1v3  mae 0.004100   px>2%  3.66%   max 0.6824
      2v3  mae 0.005612   px>2%  4.27%   max 0.7255
      MEAN      0.005275

    AFTER   wind OFF (nowind overrides)
      1v2  mae 0.002468   px>2%  2.00%   max 0.3294
      1v3  mae 0.002157   px>2%  1.99%   max 0.6314
      2v3  mae 0.002304   px>2%  1.73%   max 0.6275
      MEAN      0.002310

**2.3x quieter, and now 0.78x the bare-terrain noise floor** -- i.e. below
the level at which this project's own instruments call two frames identical.

**THE CHARACTER OF THE DIFFERENCE CHANGED, WHICH IS THE REAL RESULT.** The
before-diff is a SOLID FILLED silhouette of the tree. The after-diff is
sparse SPECKLE tracing the same outline: isolated bright pixels, no filled
regions. Bulk motion displaces whole areas; sub-pixel sampling flicker on
alpha-tested needle edges produces exactly this speckle. The systematic
motion is gone and what remains is temporal sampling noise living where such
noise belongs.

**Stated as a limit rather than glossed:** this test cannot fully separate a
small residual motion from TAA speckle. It shows the whole-frame statistic
below the floor and the spatial character changed from filled to scattered.
Those two together are the evidence; neither alone would be.

**Scope of what was proven.** Only `spruce_half_01` carries overrides in
the scratch level; the other four trees still run vendor materials with wind
ON. The camera frames `half_01`, so this is a valid single-subject test --
but nothing here says the other 19 meshes behave the same, and each mesh
scattered later needs its own overrides built by the same tool.

Frames: `_verify/20260815_pn_nowind_frame_a.png` / `_b.png`.
Override map: `Free/_measured/pn_nowind_overrides.json` -- POSITIONAL, in
slot order. `spruce_small_05` orders its slots trunk/leaf/branch while
`spruce_half_01` orders trunk/branch/leaf, so a list built by name-guessing
rather than read from `static_materials` would silently repaint the tree.
