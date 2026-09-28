# FRAME COST AT NANITE + DISPLACEMENT — 8129 terrain, 2026-08-13

**Single-variable A/B taken in ONE editor session, one process, one viewport
size, at two cameras.** The variable is the `r.Nanite` cvar, set and read back
by `render_condition.py` both directions and restored to 1 at the end.

## CALIBRATION CLASS — binds every number below

    class        editor viewport — NOT PIE, NOT a packaged build
    level        /Game/GaeaLab/AlpineLab_8129
    landscape    8129², 66,080,641 vertices, 1 m/vertex, 1024 components
    residency    1 landscape + 256 proxies, 1024 of 1024 components — DECLARED
                 and asserted by the tool on every run
    material     M_AlpineLab_8129, displacement magnitude 0.16, tessellation on
    Nanite       256/256 proxies carry a BUILT Nanite mesh
    foliage      NONE on this terrain (no rock or tree scatter placed)
    cvars        r.Nanite.MaxPixelsPerEdge 1.0, r.Nanite.Tessellation 1.0,
                 r.DynamicGlobalIlluminationMethod 1.0, r.ReflectionMethod 1.0,
                 r.ScreenPercentage 100.0, r.ViewDistanceScale 1.0
    machine      RTX 5080 Laptop, Core Ultra 9 275HX, 31.4 GB RAM
    process      PID 13952, cold-loaded from disk

**NOT comparable to R13's 94.45 / 75.71 ms** — those are the retired iGPU.

## THE MEASUREMENT — 300 frames per run, CSV artefact per run

### ground_origin — eye height, 1.7 m, on the 314 m high point at world origin

    metric            Nanite ON    Nanite OFF     delta        %
    GPUTime mean          4.95         3.75      +1.20 ms   +32.0%
    GPUTime p50           4.91         3.75      +1.16 ms
    GPUTime p90           5.14         3.79      +1.35 ms
    RenderThreadTime      4.60         3.54      +1.06 ms   +29.9%
    RHIThreadTime         2.30         2.16      +0.14 ms
    GameThreadTime        6.61         6.19      +0.42 ms
    FrameTime            16.67        16.70                 (a 60 fps CAP)

### peak_orbit — oblique, 1200 m altitude

    metric            Nanite ON    Nanite OFF     delta        %
    GPUTime mean          4.05         3.22      +0.83 ms   +25.8%
    GPUTime p50           4.03         3.00      +1.03 ms
    GPUTime p90           4.16         3.58      +0.58 ms
    RenderThreadTime      4.57         3.66      +0.91 ms   +24.9%
    RHIThreadTime         1.99         1.87      +0.12 ms
    GameThreadTime        7.00         6.66      +0.34 ms
    FrameTime            16.67        16.67                 (a 60 fps CAP)

## WHAT IT MEANS

**Nanite landscape plus displacement costs about 1.2 ms of GPU at ground level
and 0.8 ms from the air — roughly 25-32% on top of the non-Nanite path.** At
4.95 ms worst case that is about **30% of a 16.67 ms frame**, leaving ~11.7 ms
of headroom before the 60 fps cap.

**The cost is real and it is small in absolute terms.** It buys the silhouette
that the 4 m heightmap sampling cap could never represent, measured separately
at 41.1x the noise floor at ground level with visible stepped strata,
terraces and cast shadow in the frames.

**FrameTime is pinned at 16.67 ms in ALL FOUR RUNS**, so none of these is
GPU-bound and none is a frame-rate result. These are per-frame GPU costs
against a cap.

## THE 60 fps CAP IS ROOT-CAUSED, AND IT CANNOT BE LIFTED BY A CVAR

Chased 2026-08-13 and settled at a source line rather than by cvar roulette.
**Not `t.MaxFPS`** — it reads **0.0** (unlimited) in this process, so the
board's long-standing suspect is not the cause here. **Not vsync** —
`r.VSync` 0.0, and setting `rhi.SyncInterval` 1 -> 0 moved FrameTime not at
all (16.67 -> 16.71, inside run-to-run variance). **Not frame smoothing** —
`bSmoothFrameRate` is False. **Not the battery heuristic** — the machine is on
AC (`PowerLineStatus Online`, `Win32_Battery` status 2).

`UEditorEngine::GetMaxTickRate`, `EditorEngine.cpp:2523-2566`:

    if( !bSmoothFrameRate && GIsEditor && !GIsPlayInEditorWorld )
    {
        MaxTickRate = 1.0f / DeltaTime;                      // <- the current rate
        ... FMath::Max(MaxTickRate, SmoothedFrameRateRange.GetLowerBoundValue())   //   5
        ... FMath::Min(MaxTickRate, SmoothedFrameRateRange.GetUpperBoundValue())   // 120
    }

**`MaxTickRate = 1.0f / DeltaTime` clamps the editor to the rate it is ALREADY
RUNNING AT.** It is a hysteresis loop: once anything parks the editor at 60 —
a slow load, a stall, a vsynced first frame — the previous frame's DeltaTime
sets this frame's ceiling and it stays there. `SmoothedFrameRateRange` is
`[5, 120]`, so there is also a hard **120 fps editor ceiling that applies even
though smoothing is disabled**, which the comment above it says outright:
*"Clamp editor frame rate, even if smoothing is disabled"*.

The same function carries the two other rates this project has measured
without naming their source: `MaxTickRate = 3.0f` under
`ShouldThrottleCPUUsage()` — the **333.33 ms / 3 fps** backgrounded idle the
throttle investigation measured on 2026-08-10 — and the 60 Hz battery limit,
*"Laptops should throttle to 60 hz in editor to reduce battery drain"*,
defeatable with `r.DontLimitOnBattery 1` if this machine is ever run unplugged.

**CONSEQUENCE FOR THIS PROJECT'S MEASUREMENTS: editor frame RATE is not a
valid headroom instrument, and never was.** `FrameTime` in the editor reports
the clamp, not the scene. GPU/RenderThread/GameThread times are unaffected by
it — the work is done and the engine then sleeps — so they remain valid, and
they are what every conclusion here rests on.

**HEADROOM, stated from the instrument that is valid:** 4.95 ms of GPU work in
a 16.67 ms frame is **~30% GPU utilisation** at 60 fps, with ~11.7 ms unused.
A GPU-bound ceiling of ~200 fps is arithmetic from 4.95 ms and is NOT a
measurement — nothing here demonstrates the editor reaching it.

## WHY THIS IS AN A/B AND NOT A COMPARISON TO THE BOARD

The recorded pre-Nanite figure (GPUTime 5.07 mean, 2026-08-12) **names neither
its camera nor its viewport size**, so it cannot support a single-variable
claim; today's Nanite-OFF control at the same camera reads 3.75. The two
numbers are not in conflict — they are not the same measurement. Everything
above is taken within one session precisely to avoid that trap.

## THE INSTRUMENT WAS CHECKED, NOT ASSUMED

Every run passed the tool's throttle gate — **3.65 / 2.17 / 2.54 / 3.38
CPU-seconds per wall-second**, against the ~0.08 that a throttled editor
produces. The editor was forced foreground for the duration of each capture.
Residency was declared and asserted at 1024 of 1024 components on every run;
the tool refuses (exit 6) on a partitioned world without it.

## ARTEFACTS

    LandscapeLab/Saved/Profiling/CSV/Profile(20260813_211156).csv   ground ON
    LandscapeLab/Saved/Profiling/CSV/Profile(20260813_211517).csv   ground OFF
    LandscapeLab/Saved/Profiling/CSV/Profile(20260813_212035).csv   peak   OFF
    LandscapeLab/Saved/Profiling/CSV/Profile(20260813_212337).csv   peak   ON

## CAVEAT ON THE CONTROL, STATED PLAINLY

`r.Nanite 0` disables Nanite RENDERING, so the OFF runs also lose displacement
(tessellation requires the Nanite path). The delta is therefore the cost of
**Nanite + displacement together**, not of Nanite alone. That is the right
question for this terrain — the two were adopted as one unit — but it is not a
decomposition, and nothing here says how the 1.2 ms splits between them.
