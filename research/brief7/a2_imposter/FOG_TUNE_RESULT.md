# Brief 7 — fog tune (aerial perspective) measured ladder: height fog reduces grey but cannot blue-shift

2026-09-25, Look profile, windowed. Measured, not eyeballed. No fog value persisted (see verdict).

## Read-backs first (baseline, Look profile)

    ExponentialHeightFog  fog_density 0.00416  fog_height_falloff 0.0193  start_distance 0
                          volumetric_fog_extinction_scale 1.0  scattering_distribution 0.2
    SkyAtmosphere         aerial_pespective_view_distance_scale = 1.0  (UE's own misspelling)
                          height_fog_contribution 1.0

The Look profile does NOT currently set fog — fog is a shared scene value (= the bench/Brief-2 baseline).

## Camera + bands

One elevated forest-overlook camera (loc (-201186, 219000, 21722), rot (0,-9,270), FOV 70): near tree
canopy (foreground, ≲100 m), a right-side mid cluster, and a distant tree line (mid-left). Foliage
measured by a green mask; saturation = (max-min)/max, luminance, hue in each crop. NOTE: foliage is
ignored by line traces, so the exact band distances are visual estimates (near ≲100 m, mid ~200–400 m,
far ~700–1000 m). The far band is small (~650 px) — the true 1000 m+ grey clusters (A2 measured sat 0.05
at the slope station) are farther than this camera cleanly frames, so the far band UNDERSTATES the worst
grey.

## The ladder (7 renders): density × start_distance, + extinction on the best

| cell | density | start m | near sat | mid sat | far sat | far/near | far hue | far lum |
|---|---|---|---|---|---|---|---|---|
| d42_s0 (baseline) | 0.0042 | 0 | 0.494 | 0.517 | 0.262 | 0.53 | 49.3 | 68.1 |
| d25_s0 | 0.0025 | 0 | 0.499 | 0.519 | 0.294 | 0.59 | 49.6 | 66.5 |
| d15_s0 | 0.0015 | 0 | 0.501 | 0.520 | 0.320 | 0.64 | 50.3 | 64.1 |
| d42_s150 | 0.0042 | 150 | 0.501 | 0.523 | 0.281 | 0.56 | 49.0 | 66.4 |
| d25_s150 | 0.0025 | 150 | 0.504 | 0.522 | 0.308 | 0.61 | 49.4 | 64.8 |
| **d15_s150 (best)** | 0.0015 | 150 | 0.504 | 0.523 | **0.327** | **0.65** | 49.8 | 63.8 |
| d15_s150 + ext0.5 | 0.0015 | 150 | 0.504 | 0.523 | 0.327 | 0.65 | 49.8 | 64.5 |

## Against the targets

- **300 m: sat ≥ 0.60 × sat40, lum within 15%.** The mid band (~300 m proxy) is sat ~0.52 vs near ~0.50
  (ratio ~1.04) at ALL densities → PASS regardless of fog. 300 m is barely fogged.
- **1000 m: sat ≥ 0.30 × sat40 (= ~0.15), hue toward blue.** The far band (~700–1000 m) is sat 0.262
  (baseline) → 0.327 (best), all ≥ 0.15 → sat PASSES in this band. BUT the **hue stays ~49° (green-yellow)
  on every cell — NO blue shift → FAIL the "toward the sky (blue)" clause.** And the true 1000 m+ clusters
  (A2 sat 0.05) are below 0.15 and this camera undersamples them, so the 1000 m sat likely FAILS at the
  real worst distance.
- **4 km ridge faded with form:** the snow ridge reads with form and fades toward sky in all cells (it is
  snow, not foliage) — qualitatively OK, fog-insensitive here.

## Verdict — height fog is the WRONG lever for the blue aerial perspective; no value persisted

- Lowering `fog_density` 0.0042 → 0.0015 (+ `start_distance` 150 m) reduces the distant grey wash MODESTLY
  (far sat +25%: 0.262 → 0.327; far luminance 68 → 64). Directionally right, best cell **d15_s150**.
  `volumetric_fog_extinction_scale` is INERT here (0.5 == 1.0 → volumetric fog not contributing).
- But **height fog cannot produce the target's "hue shifted toward the sky (blue)"** — its inscattering is
  grey/warm, so distant foliage DESATURATES (grey) rather than blue-shifting. Every cell's far hue is
  green-yellow. A human-vision aerial perspective (green fading to BLUE) is a **SkyAtmosphere** function:
  `aerial_pespective_view_distance_scale` (currently 1.0). That lever was marked read-only for this round,
  so it was read back, not tuned.
- Per "none pass → report the table and the closest cell; desk rules": the blue-hue clause fails on all
  cells, so **no fog value was persisted.** Closest cell = **d15_s150** (a modest de-greying). Fog restored
  to baseline (0.0042); it was never saved, so on-disk fog is unchanged; bench untouched.

## Recommendation (desk to rule)

Two options:
1. **Adopt d15_s150 as a Look-profile fog field** (density 0.0015, start_distance 150 m) for a modest
   de-greying at distance — cheap, harmless, but does NOT give the blue aerial perspective.
2. **Authorize the SkyAtmosphere lever** — LOWER `aerial_pespective_view_distance_scale` (< 1.0) so the
   atmosphere tints distant content toward the blue sky sooner (true aerial perspective). This is the lever
   that hits "green fading to blue, not grey". Recommend a 3-cell ladder {1.0, 0.5, 0.25} × the d15_s150 fog,
   measuring far-band hue shift toward blue. Bench restores the Brief-2 atmosphere on switch.

Stills: `research/brief7/a2_imposter/fog/` (fog_d42_s0 … fog_d15_s150_ext05, + calibration frames).
