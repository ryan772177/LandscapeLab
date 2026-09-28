# Frame cost — Alpine8K with the PVE Nanite Norway Spruce

Measured 2026-08-15, `forest_floor` station, editor viewport, full residency
(1 landscape + 256 proxies, 1024/1024 components), 300 frames, past the
throttle gate at **4.69 CPU-s per wall-second**.

Artefact: `LandscapeLab/Saved/Profiling/CSV/Profile(20260815_013704).csv`
Tag: `pve_spruce`

    column                  n      mean       p50       p90       max
    FrameTime             300    16.68    16.67    16.67    20.30
    GameThreadTime        300     8.83     8.67     9.71    18.11
    RenderThreadTime      300     6.99     6.90     7.75     9.42
    GPUTime               300     7.76     7.75     7.96     8.86
    RHIThreadTime         300     2.97     2.86     3.47     4.67

`FrameTime` is pinned at the editor's 60 fps cap (`UEditorEngine::GetMaxTickRate`
hysteresis, root-caused 2026-08-13). It is NOT a frame-rate result and nothing
here is GPU-bound.

## Against the recorded baseline at the same station

    2026-08-14  fir_tree_01 + ScotsPineTall_01, 4-level LOD chain
                GPUTime 8.14   RenderThread 4.88   GameThread 7.48
    2026-08-15  PVE Nanite Norway Spruce + ScotsPineTall_01
                GPUTime 7.76   RenderThread 6.99   GameThread 8.83

    delta       GPU -0.38 ms (-4.7%)   Render +2.11   Game +1.35

**GPU got slightly CHEAPER while the forest got denser and much taller** —
the spruce is 29.31 m against the fir's 14.52 m, with real needle geometry
where the fir had a 24.02%-opaque alpha atlas. The render and game threads
each cost about 1.5-2 ms more.

## THIS IS NOT A SINGLE-VARIABLE COMPARISON, and the delta must not be quoted as one

Three things changed between the two measurements, not one:

1. the conifer mesh (alpha-tested 505,494-triangle LOD0 with a 4-level chain
   -> Nanite mesh with a ~2,335-triangle fallback)
2. `r.Nanite.Foliage` went 0 -> 1, which ALSO enables Nanite Assemblies,
   Nanite Voxels and TSR thin-geometry detection
   (`RenderUtils.cpp:1369-1385`, `TemporalSuperResolution.cpp:499-502`)
3. `scale_range` [0.7, 1.4] on a 14.52 m tree -> [0.6, 1.15] on a 29.31 m one

Attributing the -0.38 ms to Nanite foliage specifically would be wrong. To
decompose it, the control is cheap because Nanite is PER MESH: keep the flag
on and toggle Nanite on the eight tree assets.

## What IS supportable

- At a ground station inside the forest, with 153,796 instances resident,
  the scene costs **7.76 ms of GPU**, about 47% of a 16.67 ms frame.
- The change did not cost GPU time. Whatever else is true, replacing the
  canopy did not push this station toward a budget it was not already near.
- Editor viewport only. Not PIE, not a packaged build, and the class caveat
  from R13 applies.
