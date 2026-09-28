# PIE frame cost — PHASE2_PLAN.md unit 1, tag `unit6_collision_on`

**The first PIE measurement this project has taken.**

## CALIBRATION CLASS — binds every number below

| | |
|---|---|
| class | **PLAY IN EDITOR** — not editor viewport, not PIE-in-new-window, not a cook |
| level | `/Game/Alpine8K` |
| viewport px | [1076, 1292] |
| streaming | **LIVE** — not force-resident |
| frames per station | 300 |
| GameMode | engine default; the level has **no PlayerStart** and pawn is `DefaultPawn` |

Cvars in effect at capture time:

| cvar | value |
|---|---|
| `foliage.DensityScale` | 1.0 |
| `grass.DensityScale` | 1.0 |
| `r.DynamicGlobalIlluminationMethod` | 1.0 |
| `r.Nanite.Foliage` | 1.0 |
| `r.Nanite.MaxPixelsPerEdge` | 1.0 |
| `r.ReflectionMethod` | 1.0 |
| `r.ScreenPercentage` | 100.0 |
| `r.Shadow.Virtual.MaxPhysicalPages` | 2048.0 |
| `t.MaxFPS` | 0.0 |

**No editor-viewport figure may be compared into this table, and nothing here may be compared back out.** `RECIPES.md:5889` already calls PIE a different calibration class.

## Station `forest_floor_control`

control -- must reproduce the editor series at this camera

| | |
|---|---|
| view point | [377886.3756929784, -303056.87569307454, 28678.943556246693] cm |
| view rotation | [3.049999952316283, 134.99999999999997, -1.9906664892021657e-16] (pitch, yaw, roll) |
| FOV in PIE | 90.0 deg — **not matched to the recipe camera's `fov_deg`, and not to the editor viewport's either.** One of the uncontrolled variables between the two classes |
| ground (line trace vs collision) | not traced — station uses the recipe's absolute Z |
| view vs target drift | 285.1 cm |
| resident landscape proxies | 4 |
| resident foliage actors | 9 |
| editor CPU ratio during capture | 2.87 CPU-s per wall-s |
| csv | `Profile(20260816_222708).csv` |

| column | n | mean | p50 | p90 | max |
|---|---|---|---|---|---|
| `FrameTime` | 300 | 16.675 | 16.667 | 16.673 | 19.028 |
| `GameThreadTime` | 300 | 8.261 | 8.128 | 8.790 | 16.610 |
| `RenderThreadTime` | 300 | 5.618 | 5.585 | 5.946 | 6.988 |
| `GPUTime` | 300 | 8.335 | 8.317 | 8.543 | 9.788 |
| `RHIThreadTime` | 300 | 3.028 | 3.012 | 3.299 | 3.698 |
| `VSM/FreePages` | 300 | 1733.170 | 1739.000 | 1740.000 | 1741.000 |
| `VSM/SinglePageCount` | 300 | 0.000 | 0.000 | 0.000 | 0.000 |
| `VSM/FullCount` | 300 | 17.000 | 17.000 | 17.000 | 17.000 |
| `VSM/NonNanitePostCullInstanceCount` | 300 | 541.073 | 551.000 | 585.000 | 595.000 |
| `VSM/NaniteNumTris` | 300 | 0.000 | 0.000 | 0.000 | 0.000 |
| `SceneCulling/NumStaticInstances` | 300 | 346285.000 | 346285.000 | 346285.000 | 346285.000 |
| `SceneCulling/NumDynamicInstances` | 300 | 2.000 | 2.000 | 2.000 | 2.000 |

## How to read the VSM columns

`VSM/FreePages` against the `r.Shadow.Virtual.MaxPhysicalPages` pool is the direct saturation signal. `SinglePageCount` and `FullCount` count shadow **maps**, not pages — `PHASE2_PLAN.md` names those two as the discriminator and that is one step off; the correction is recorded in `measure_pie_cost`'s docstring.

Citations, each opened against this install: `VirtualShadowMapArray.cpp:104` (`CSV_DEFINE_CATEGORY(VSM, false)`), `:2619`, `:2620`; `VirtualShadowMapCacheManager.cpp:685`; `GPUScene.cpp:48`; `SceneCulling.cpp:105` (default **on**), `:2676`.

