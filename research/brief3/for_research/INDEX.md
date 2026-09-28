# Brief 3 send-back — index (2026-09-15)

Every artefact with the INSTRUMENT it was measured on. ⚠ This send-back is
**PROVISIONAL**: two Task 5 acceptances came back as FINDINGS (not clean
passes), B-2 is disk-blocked, and the desk owes two rulings (below).

## Task 5 acceptance (B-1) — findings, not passes

| artefact | what | instrument | verdict |
|---|---|---|---|
| `TASK5_ACCEPTANCE_B1.md` | the write-up of both findings | — | FINDINGS |
| `fog_contrast_{vista,mid_slope}.json` | 300 m–1 km luminance contrast vs fog_budget T | **ppi0** (scene-linear) | metric OUT OF CLASS at altitude — content, not fog; mid_slope FAIL, vista PASS, both content artefacts |
| `proxy_albedo_{vista,mid_slope}.json` | proxy-vs-real albedo per layer | **BaseColor GBuffer ÷ 2^comp**, proxy=player HLOD vs real=LOD0 | NULL — proxy and real pixel-identical; the bench force-loads real cells, so HLOD proxies never render in a bench frame |

Stills (3840×2160, target class, `instrument: finalimage_linear` RGBA +
`ppi0`/`basecolor`/`depth` channels in the multilayer EXR), referenced by
path, not copied:
- `_verify/bench/2026-09-15/target_b1_vista/` , `target_b1_mid_slope/` (player/proxy)
- `_verify/bench/2026-09-15/target_b1_vista_real/` , `target_b1_mid_slope_real/` (LOD0/HLOD-off real)

## Card readings — the joint WB solve (A-6)

| artefact | what | instrument |
|---|---|---|
| `wb_joint_solve_a6.json` | first-order vs joint 2×2 WB solve | finalimage_linear EXR card |

Confirm capture card: **R/G 1.0014, B/G 0.998** (both in 0.97–1.03) at
white_temp 3438.6 / white_tint −0.0248. See `R-SHADEBAND_A7_VERDICT.md`
for the shade band (2.065–2.998 @ 3438.6 K, floor D6000) and the 2.1896
PASS.

## Tiling / weightmap / surface

| artefact | what | instrument |
|---|---|---|
| `TASK3_RECORD.md` | Task 3 tiling verdicts | player (temporal 8, TSR) |
| `weightmap_alpine_8k_w8_sidecar.json` | the 8-channel weight derivation (snow-by-aspect, forest-floor-from-canopy, scree-from-flow) | derived offline from heightmap + Gaea masks + placement JSON |

Albedo library (linear luma, current surfaces, `scan_surface_stats.py`):
Snow007A 0.836, gray_rocks 0.179, rocks_ground_04 0.223, forest_floor
0.276, wild_grass 0.141.

## Task 0 — the loading-range perf tables

| artefact | what | instrument |
|---|---|---|
| `task0_perf_range512.json` | standalone −game 4K perf at R-RANGE 512 m (in force) | standalone -game, GPU p90/zone |
| `task0_perf_range768.json` | standalone −game 4K perf at 768 m | standalone -game, GPU p90/zone |

## Cloud (B-4)

| artefact | what | instrument |
|---|---|---|
| `CLOUD_COVERAGE_B4.md` | Cloud_GlobalCoverage 0.1 vs 0.3 | depth sky-mask + FinalImage luminance |

## Register

| artefact | what |
|---|---|
| `register_diff_since_brief3.md` | REGISTER_ADDENDUM B3.20–B3.29 + Q17, and the in-force grade/shade values |

## ⛔ NOT in this send-back (blocked / owed)

- **B-2 (cost of 4096 A/B)** — DISK-BLOCKED. Two landscape-HLOD rebuilds
  (256 then 4096) need ~42 GB; only 28 GB free. Needs Ryan to clear
  `C:\UnrealDDC` (31.8 GB). Not started.
- **A clean Task 5 acceptance** — both Task 5 sub-acceptances are findings
  about the INSTRUMENT (fog metric out of class at altitude; proxies not
  in a bench frame), not tunable defects. Two rulings owed from the desk:
  (1) whether the fog-contrast acceptance should move to near_ground/valley
  where it has power, and (2) whether rendered proxy albedo needs a
  streaming-respecting capture (the baked 4096 texture is already verified
  off disk, 256/256).
- **Electric Dreams HLOD proxy props** (B-6) — the census tool is built
  and collects the four props (ours: 4096/SPECIFIC_SIZE ×257), but the ED
  sample project is not installed on this machine.

## Instruments legend

- **ppi0** — BL_SCENE_COLOR_AFTER_DOF pass-through, scene-linear, pre-grade, exposure-linear. Albedo/contrast/anything absolute.
- **finalimage_linear** — the −linear EXR RGBA: tone-curve-off FinalImage, POST-grade (carries WB). Card/WB.
- **basecolor** — FinalImageBaseColor GBuffer ÷ 2^compensation = reflectance.
- **player** — dev/target MRQ, no GameOverride, project TSR, temporal 8 on target.
- **truth / LOD0** — --game-override disable_hlods + use_lod_zero: the real landscape material, no HLOD proxy.
