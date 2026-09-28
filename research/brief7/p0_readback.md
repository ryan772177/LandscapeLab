# Brief 7 Phase 0b — live-editor read-backs

Editor: `/Game/Alpine8K` (rule 11 confirmed), project LandscapeLab (rule 7 verified,
engine 5.8.1). READ-ONLY pass, no save. Raw JSON: `input/p0b_inventory.json`,
`input/p0b_material.json`; lights via `find_second_sun_payload.txt`, cloud via
`read_cloud_state.py`. 2026-09-23.

## PostProcessVolumes — 1 found

`Lighting_alpine_8k_PostProcess` is the scene's only PPV and is the **bench PPV**
(R-LOOK-1: NEVER touch it). PPV_Look (0d) is a NEW actor at higher priority.

| field | ruled | current | match |
|---|---|---|---|
| metering | Manual | `AEM_MANUAL` | ✓ |
| exposure compensation | A-6 solve | bias **−14.2571** (overridden) | ✓ = the A-6 value |
| min / max EV100 | — | 1.0 / 1.0 (manual clamp) | n/a |
| unbound | — | True | — |
| priority | — | 0.0 | PPV_Look must exceed |
| white_temp | — | 3438.6 (overridden) | (bench grading, untouched) |
| color_contrast | — | (1,1,1, w=0.95) overridden | — |
| bloom | — | BM_FFT (convolution), intensity 0.4 | — |
| film grain / vignette | — | 0.0 / 0.0 | — |
| local exposure hi / lo | — | 1.0 / 1.0 (OFF) | — |

## DirectionalLights — 4 found (the "four suns" answer)

| label | lux | K | atmosphere_sun | pitch/yaw | affects world | note |
|---|---|---|---|---|---|---|
| **Lighting_alpine_8k_Sun** | 130000 | 5200 | **TRUE** | −12 / −75 | yes | THE SUN. elev 12 / az 285 matches recipe geometry |
| HeroStage_Key | 25000 | 6500 | false | −22 / −120 | yes (hidden_in_game=false, casts shadows) | hero rig |
| HeroStage_Fill | 7500 | 6500 | false | −8 / −45 | yes | hero rig |
| HeroStage_Rim | 11250 | 6500 | false | −5 / +90 | yes | hero rig |

**Four DirectionalLights exist; exactly ONE is the atmosphere sun.** The other three
are a hero 3-point portrait rig (Key/Fill/Rim) that is STILL lighting the whole world
(`hidden_in_game=false`, `cast_shadows=true`) — the likely source of the "multiple
directional lights competing" warning and a flat/over-filled look. **FLAG for L0:**
should the HeroStage rig be hidden-in-game for the world look? (Not touched this
phase — a light change, deferred to Ryan's grade.)

Sun K = **5200** → PPV_Look WB target = 5200 + 1000 = **6200** (0d rule).

## SkyLight — `Lighting_alpine_8k_SkyLight`

intensity 1.0; `SLS_CAPTURED_SCENE`, real_time_capture True, lower_hemisphere_black
True, affects_world True, visible True. (No ruled target; recorded.)

## ExponentialHeightFog — `Lighting_alpine_8k_Fog`

| field | ruled (0d) | current | match |
|---|---|---|---|
| volumetric ON | ON | present (distribution/dist readable; enable-bool name unreadable, re-read in 0d) | ~ |
| scattering distribution | 0.2 | **0.4** | ✗ → set 0.2 |
| extinction scale | 1.0 | 1.0 | ✓ |
| view distance | 6 km | 6000 | ✓ |
| start distance | 0 | 0 | ✓ |
| fog_density / height_falloff | — | 0.00416 / 0.01932 | (informational) |
| inscattering colours | black (atmosphere-coupled) | color props unreadable by name (re-read 0d) | — |

## SkyAtmosphere (Mie)

mie_scattering_scale 0.010, mie_absorption_scale 0.000444, mie_anisotropy 0.8,
mie_exponential_distribution 1.2, rayleigh_scattering_scale 0.0331, multi_scattering 1.0,
height_fog_contribution 1.0. (No ruled target; recorded.)

## VolumetricCloud — `Lighting_alpine_8k_Clouds` (ACTIVE, all gates permit)

| field | ruled | current | match |
|---|---|---|---|
| layer_bottom_altitude | 2.0 km | 2.0 km | ✓ |
| layer_height | 1.5 km | 1.5 km | ✓ |
| coverage (`Cloud_GlobalCoverage`) | 0.1 | **0.30** | ✗ → set 0.1 |
| material | — | `/Game/Bench/MI_AlpineClouds` | — |

## Landscape material `M_Alpine8K` (as built — PRE-Phase-1)

197 expressions. Structure = a **LinearInterpolate composite over the baked weightmap**
(20 LinearInterpolate, 32 TextureSample); **NO LandscapeLayerBlend, NO
LandscapeLayerCoords** (confirms `height_blend._schema`: LB_HeightBlend has no referent
here). Tiling is done via WorldPosition ÷ constants, not LandscapeLayerCoords.

| feature | ruled (Phase 1) | current (built) | match |
|---|---|---|---|
| per-layer Mapping Scale (R-TILE) | Snow 5.03 / Rock 1.80 / Scree 2.00 / ForestFloor 2.14 / Grass 5.03 | **no LandscapeLayerCoords** — R-TILE never reached the graph (desk fact confirmed) | ✗ Phase 1 owed |
| Nanite displacement | per_layer (max 0.20), center 0.5 | `displacement_scaling` magnitude **0.16**, center 0.5 (single global) | ✗ Phase 1 owed |
| height-blend reweight | k=4, eps=0.02 | absent | ✗ Phase 1 owed |
| grass outputs | Meadow + Blueberry + GroundClutter (boulder_small/river_rock) | **Meadow + Blueberry only** | ✗ Phase 1 owed (GroundClutter) |

**All material rows are the expected pre-rebuild state.** The Phase 1 material rebuild
(merged to main, offline-verified, editor-unrun) is the gated world run owed AFTER
Ryan's L0 grade — this table is the "before".

## Summary of deltas 0c–0d will act on

- **0c:** pre-exposure `CachedLightingPreExposure` (the −14.2571 bench comp reflects the
  live-4 / EV-14.3 clip the warning names).
- **0d (new PPV_Look only):** grade per runbook; fog scattering 0.4 → 0.2; cloud
  coverage 0.30 → 0.1.
- **L0 flag:** the HeroStage 3-point rig lights the world (3 non-sun directional lights).
