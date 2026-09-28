# Brief 7 — blue-shift ladder (SkyAtmosphere AP scale × volumetric albedo): NONE PASS, no value persisted

2026-09-26, Look profile (sun 35°, PPV_Look on, sg Epic, TSR), windowed editor, 3840×2160 stills.
Measured, not eyeballed. Fence `pre-a2-fog` stands; fog/atmosphere restored live to the on-disk
baseline after the ladder (read back: density 0.00416, start 0, albedo white, AP scale 1.0); nothing saved.

## Read-backs first (baseline, live)

    ExponentialHeightFog  fog_density 0.00416  fog_height_falloff 0.01932  start_distance 0
                          enable_volumetric_fog True  volumetric_fog_albedo (255,255,255)
                          extinction_scale 1.0  scattering_distribution 0.2
                          fog_inscattering_luminance (0,0,0)  ambient_contribution_color_scale (1,1,1)
    SkyAtmosphere         aerial_pespective_view_distance_scale 1.0  height_fog_contribution 1.0
    cvars                 r.VolumetricFog 1   r.SupportExpFogMatchesVolumetricFog 0
                          Slate.bAllowThrottling 1 -> 0 (set by the render preamble on every shot)

Engine header, not doc prose: `SkyAtmosphereComponent.h:154` — "Makes the aerial perspective look
THICKER by scaling distances from view to surfaces" → the ladder went {1, 2, 4} (thicker), measured.

## Cameras, crops, mask

- **camA** forest overlook, loc (−201186, 219000, 21722) rot (0,−9,270) FOV 70 (the FOG_TUNE camera).
  near = large foreground spruce cluster (~40 m), mid = upper right cluster (~150–300 m), far = the
  small tree line on the snow slope top-left (~700–900 m; ~80 px trees at 2742 px focal).
- **camB** mid_slope bench station [−190000, 100000] pitch −2 yaw 105 FOV 90, ground-traced +1.75 m
  (z 63366). far = the ~1140 m dark-cube cluster the A2 stills measured at sat 0.05 (world ≈ (−201555, 213461)).
- Mask = crop rectangle + luminance in [8, lum_hi] (170 near/mid, 140 far) — by REGION, not colour, so
  a blue-shifted pixel cannot be masked out. Kept-pixel counts beside every number (rule 13).
- Settle: camera placed, 25 s host-side sleep, then shoot (a 4 s settle leaves foliage at card LODs;
  the first unsettled baseline is kept as `camA_base.png` for the record).
- Crops: `ap/crops.json`; driver `research/brief7/scripts/fog_ap_ladder.py`; measure
  `fog_ap_measure.py`; raw `ap/ladder_measure.json`, `ap/ladder_log.json`.

## The ladder — 7 cells (+ baseline), density 0.0015 / start 150 m held on every ladder cell

| cell | AP scale | albedo | camA near sat / hue | camA mid sat / hue | camA far sat / hue / lum | camB far (1140 m) sat / hue / lum |
|---|---|---|---|---|---|---|
| base_d42 (on-disk) | 1.0 | white | 0.529 / 44.1 (n 691k) | 0.475 / 48.5 (n 431k) | 0.257 / 36.3 / 95.2 (n 11.9k) | 0.161 / 233.1 / 94.2 (n 182k) |
| ap1_white | 1.0 | white | 0.530 / 43.3 | 0.487 / 47.8 | **0.294** / 37.2 / 93.1 | **0.192** / 232.7 / 86.6 |
| ap2_white | 2.0 | white | 0.529 / 43.4 | 0.483 / 47.7 | 0.259 / 36.0 / 93.6 | 0.187 / 228.9 / 92.7 |
| ap4_white | 4.0 | white | 0.528 / 43.4 | 0.478 / 47.9 | 0.207 / 33.8 / 96.1 | 0.187 / 225.3 / 102.5 |
| ap1_sky | 1.0 | (140,179,255) | 0.529 / 43.4 | 0.487 / 47.9 | 0.294 / 37.1 / 92.7 | 0.193 / 232.6 / 86.7 |
| ap2_sky | 2.0 | (140,179,255) | 0.529 / 43.4 | 0.483 / 47.7 | 0.258 / 36.0 / 93.5 | 0.187 / 228.8 / 92.7 |
| ap4_sky | 4.0 | (140,179,255) | 0.528 / 43.5 | 0.479 / 48.1 | 0.207 / 33.3 / 96.1 | **NOT SHOT** (see below) |

Pixel counts per cell are within ±2% of the baseline row (camA far 11.9–12.3k, camB far 168–182k).

**camB_ap4_sky was not shot.** The ladder driver was killed by the host (system memory critically low:
1.9 GB free with the editor at 18.2 GB RSS) after 13 of 14 frames and before its restore cell; the
restore was then applied by hand and read back. Per the harness rule the run was not restarted. The
missing cell is the albedo arm of ap4, and the albedo arm is inert on all five other pairs (below), so
the verdict does not rest on it.

## Against the pass criteria (sat40 = camA near ≈ 0.53, hue40 ≈ 44°)

| clause | threshold | result |
|---|---|---|
| sat300 ≥ 0.6·sat40 | ≥ 0.32 | PASS every cell (mid 0.475–0.487; ratio ≈ 0.9) — 300 m is barely fogged |
| sat1000 ≥ 0.3·sat40 | ≥ 0.159 | PASS every cell, camA far 0.207–0.294; camB 1140 m cluster 0.187–0.193 (marginal; baseline 0.161) |
| hue1000 shifted ≥ 15° toward blue from hue40 | camA far ≥ 59° | **FAIL every cell.** camA far hue 33–37° — it moves the WRONG way: raising AP scale 1→4 shifts the far foliage hue 37.2→33.8 (toward orange) and drops far sat 0.294→0.207. |
| ridge fades with form | qualitative | OK on all cells (snow ridges keep form, fade to the horizon haze; horizon haze gets brighter/greyer at AP 4, lum 86.6→102.5 on the camB cluster). |

camB's cluster reads hue ~230° at BASELINE — that is the shadow side of dark imposter cards under a
blue sky on white snow, present before any lever moves, and the lever moves it AWAY from blue
(233→225°) while brightening it (haze). It is not aerial-perspective blue.

## Verdict — none pass; closest = ap1_white; both levers are the wrong instruments for "blue"

1. **Volumetric-fog Albedo is INERT** here: white vs sky-tinted (0.55,0.70,1.0) differ by ≤0.001 sat and
   ≤0.4° hue on all five measured pairs. Consistent with the fog tune's inert `extinction_scale`: the
   height-fog aerial perspective in this scene is the analytic exponential fog, and the volumetric
   in-scatter is not what colours the far band.
2. **AP view-distance scale >1 makes the far band GREYER and WARMER, not bluer.** The aerial perspective
   this SkyAtmosphere produces at ground level under a 35° sun is dominated by warm/grey Mie haze
   (mie_scattering_scale 0.010, anisotropy 0.8; Rayleigh 0.0331 — p0_readback), then graded warm by
   PPV_Look (WB 6200). More of it = more grey, hue toward orange. The direction was measured, not assumed.
3. **Closest cell = ap1_white** = AP scale unchanged (1.0) at the fog-tune cell d15_s150: best far sat on
   both cameras (camA 0.294, camB 0.192), hue unchanged. That is the same "modest de-greying, no blue"
   the fog tune already reported. **Not applied** (the blue clause fails; "none pass → table + closest,
   stop for the desk").

## What would produce a blue shift (for the desk; NOT tried, outside the authorised levers)

- The colour of aerial perspective is the ratio of Rayleigh to Mie in-scatter along the view ray.
  Blue needs Rayleigh-dominant haze: lower `mie_scattering_scale` (0.010 → ~0.003) and/or raise
  `rayleigh_scattering_scale`, with the AP scale then usable to bring it closer. Both are SkyAtmosphere
  fields the bench (Brief 2 atmosphere) also sees, so they need Look-profile ownership + bench restore.
- Or accept warm haze as this world's aerial perspective (the reference stills are a warm alpine) and
  strike the blue clause: then ap1_white/d15_s150 is the cell to persist.

## Side results (kept)

- `Slate.bAllowThrottling 0` folded into `scripts/render_preamble.txt`; bench A/A 3840×2160,
  8,294,400 px: pre/pre control MAD 5.58, pre/post MAD 1.56 → inside noise. Every ladder shot serviced
  in 4 s. (`ap/benchAA_{0,1,2}.png`)
- Foliage-LOD settle: the first, unsettled camA baseline rendered every tree as dissolving imposter
  cubes; 25 s after camera placement the same frame is full geometry (`camA_base.png` vs `camA_base_d42.png`).
