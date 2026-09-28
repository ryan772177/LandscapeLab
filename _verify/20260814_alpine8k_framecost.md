# FRAME COST ON /Game/Alpine8K — 2026-08-14

**One valid measurement, one INVALID control that is reported as invalid.**

## CALIBRATION CLASS — binds every number here

    class        editor viewport — NOT PIE, NOT a packaged build
    level        /Game/Alpine8K
    landscape    8129², 66,080,641 vertices, 1 m/vertex, 1024 components
    residency    1 landscape + 256 proxies, 1024 of 1024 — asserted every run
    material     M_Alpine8K, displacement 0.4 m, tessellation on
    Nanite       256/256 proxies carry a built mesh
    foliage      154,018 conifers + grass system at 120 /10m²
    exposure     -1.923 EV
    machine      RTX 5080 Laptop, Core Ultra 9 275HX, 31.4 GB RAM

## THE MEASUREMENTS

    station                       GPUTime  RenderThread  GameThread  RHI
    diag_topdown, 9 km, no foliage   4.09      4.39         7.42     2.01
    forest_floor ground, foliage     8.14      4.88         7.48     2.44
    forest_floor, "foliage off"      8.17      4.84         7.48     2.45

All runs passed the throttle gate (3.87 / 3.93 / 3.93 CPU-s per wall-second
against the ~0.08 a throttled editor produces) with full residency asserted.

## THE CONTROL IS INVALID AND THE NULL RESULT IS NOT EVIDENCE

`foliage.DensityScale 0` and `grass.DensityScale 0` were set and READ BACK as 0.
The frame did not change: GPUTime 8.14 → 8.17, GameThread 7.48 → 7.48,
RenderThread 4.88 → 4.84. Everything is inside run-to-run noise.

**That is not "vegetation is free". That is "the variable never moved."** Both
cvars govern foliage SPAWNING and generation, not already-placed
`InstancedFoliageActor` instances, and the grass system additionally needs a
cache flush before a density change takes effect. The 154,018 conifers were
placed as instances and kept rendering throughout.

This is the project's own rule firing again: **a null result is only evidence
when the instrument was capable of a non-null one.** It was written after an
`r.ScreenPercentage` control that also failed to separate, and it applies
unchanged here.

**SO THE COST OF VEGETATION ON THIS TERRAIN IS UNMEASURED.** The honest
statement is that a ground station with foliage costs 8.14 ms of GPU and a
9 km top-down without it costs 4.09 ms — but those are different CAMERAS as
well as different content, so the difference is not attributable.

## THE VALID CONTROL — RUN, AND IT MOVES

The lever was chosen by reading engine source rather than guessing a name:

    foliage.CullAll   HierarchicalInstancedStaticMesh.cpp:64
                      "If greater than zero, everything is considered culled."
    grass.Enable      LandscapeGrass.cpp:146
                      "1: Enable Grass; 0: Disable Grass"

Both render-state, both set and read back, both restored afterwards.

    forest_floor, SAME camera     GPUTime  RenderThread  GameThread  RHI
    vegetation ON                    8.14      4.88         7.48     2.44
    vegetation CULLED                5.86      4.73         7.35     2.40
    DELTA                           +2.28     +0.15        +0.13    +0.04
                                  (+38.9%)

**VEGETATION COSTS 2.28 ms OF GPU at this ground station** — 154,018 conifers
plus grass at 120 /10m², against 5.86 ms for the terrain alone.

**The pair of controls is the real result.** `DensityScale 0` gave 8.14 → 8.17;
`CullAll 1` gave 8.14 → 5.86. Both were set and read back as requested. One
moved the variable and one did not, and no amount of staring at the first
number would have revealed which. **The control that separates is the one that
proves the other was broken.**

## WHAT IS ESTABLISHED

- Terrain + Nanite + displacement at a GROUND station, no vegetation:
  **5.86 ms of GPU**.
- Vegetation adds **2.28 ms** — total **8.14 ms**, about 49% of a 16.67 ms
  frame, leaving ~8.5 ms of headroom.
- Terrain + Nanite + displacement top-down at 9 km: **4.09 ms**. Not comparable
  to the ground figures — different camera as well as different content.
- `FrameTime` is pinned at 16.67 ms in every run. That is the editor's clamp,
  root-caused 2026-08-13 to `UEditorEngine::GetMaxTickRate`'s
  `MaxTickRate = 1.0f / DeltaTime` hysteresis, and it is NOT a frame-rate result.

**Caveat that survives all of it:** the conifer is `fir_tree_01`, whose canopy is
a 24.02%-opaque binary atlas. A denser replacement will cost more than 2.28 ms.
This figure is a floor for the forest, not a budget for the intended one.

Artefacts: `Saved/Profiling/CSV/Profile(20260814_010459).csv`,
`Profile(20260814_060325).csv`, `Profile(20260814_060523).csv`,
`Profile(20260814_061?).csv` (veg culled).
