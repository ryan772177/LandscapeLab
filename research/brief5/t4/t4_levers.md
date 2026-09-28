# T4 step 2 — cvar levers, FILLed from local UE 5.8 source (header wins)

Ryan ruling: shadow/cull cvar ladder at forest_floor. One lever per arm, each vs
the same as-is baseline. Cull (reduces visible trees) runs LAST. Cvars via
`-ExecCmds` on the `-game` command line only (perf_standalone --set-cvar); no
.ini/.uasset/.umap/material/mesh/FoliageType writes this step.

Engine: `C:\Program Files\Epic Games\UE_5.8\Engine\Source`.

| arm | cvar | default | source (header:line) | ladder | target pass | visible trade? |
|---|---|---|---|---|---|---|
| A | `r.Shadow.RadiusThreshold` | 0.01 | Renderer/Private/ShadowSetup.cpp:117 (GMinScreenRadiusForShadowCaster) | 0.03, 0.06, 0.10 | ShadowDepths | NO (culls small shadow casters only) |
| B | `r.Shadow.DistanceScale` | 1.0 | Core/Private/HAL/ConsoleManager.cpp:4520 (<1 = shorter distance) | 0.75, 0.5, 0.25 | ShadowDepths | YES (shadow reach) — stills |
| D | `r.Lumen.Reflections.MaxRoughnessToTrace` | -1.0 | Renderer/Private/Lumen/LumenReflections.cpp:109 (>=0 overrides PPV; lower = fewer traced) | 0.3, 0.1, 0.0 | LumenReflections | YES (reflection look) — stills |
| E | `r.Nanite.MaxPixelsPerEdge` | 1.0 | Renderer/Private/Nanite/NaniteCullRaster.cpp:135 (px edge target; higher = coarser) | 2, 4, 8 | NaniteVisBuffer | YES (Nanite silhouette) — stills |

Not run this step (asset writes / cull-last):
- arm C `UFoliageType::bCastContactShadow` / `bCastDynamicShadow` — per-type asset property, tier 2 only, persist protocol + ASK #3 PASS required.
- arm F `foliage.CullDistanceScale` (needs `bEnableCullDistanceScaling` per type) / `Foliage.MinimumScreenSize` — LAST, reduces visible trees; only if A/B/D/E do not reach the forest_floor target.

Decision rule per arm (Ryan): MEASURED gain < 0.10 ms → drop; ≥ 0.10 ms → keep for the stack. Positive control: the target pass must move ≥ 3× min_detectable (0.016) on ≥ 1 rung, else the arm is INCONCLUSIVE, not negligible.
