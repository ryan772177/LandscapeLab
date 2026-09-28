# Brief 5 — REGISTER

Status: **M** measured by CC (v3) · **D** derived by a desk tool with selftest · **P** desk prediction,
to be replaced by measurement · **A** assumed input · **V** verified in UE 5.8 doc · **U** unverified.

| # | claim | status | source / replaced by |
|---|---|---|---|
| B5.1 | Card LODs engage at 127.8 m (pine, 332 px) and 87.5 m (SpruceSub, 367 px) | M | v3 `switch_distances.json` |
| B5.2 | 93.8 % / 97.1 % of live pine / SpruceSub instances are drawn as the card | D | `lod_ladder.py`; uniform-density assumption → `--plans` style recount optional |
| B5.3 | The 88–128 m switch is a visible defect | **P** | T1 (falsifiable: coverage 0.90–1.10 and SSIM ≥ 0.90 → withdrawn) |
| B5.4 | HLOD Instancing uses the lowest LOD irrespective of screen size | V + M | 5.8 HLOD doc; HLODLayer.h:112 read-back; builder line FILL |
| B5.5 | Card screen size 0.0382 / 0.0264 puts it at 563 m = never live | D | `lod_ladder.py` selftest (card > cull) |
| B5.6 | Constant-density rule reproduces the author's pine LOD1→2 switch (88.4 vs 90.4 m) | D | `BRIEF.md` A5 arithmetic |
| B5.7 | By that rule a 32-tri representation belongs at ~1.19 km; 40 px floor says 1.06 km | D | same; v3 `band_ring_radii_m` |
| B5.8 | Rungs: pine 1444 @ 181 m, 361 @ 362 m; SpruceSub 647 @ 85 m, 162 @ 170 m | D | `derived_ladder.json` |
| B5.9 | Station triangle load 0.51 M → 1.14 M (proposed) / 4.6 M (hold) | D (estimate) | replaced by T3/T4 triangle counter |
| B5.10 | Ladder cost is small against an 11.05 ms frame | **P** | T3/T4 GPU p90 × min_detectable |
| B5.11 | Mesh reduction of card foliage may thin crowns | P | T4 per-rung gate |
| B5.12 | Texel gate: card allowed beyond 1920·H/frame_px | D | `frame_px` **U** until T2 |
| B5.13 | Densest bin 711 trees = 108 stems/ha; best frustum 1844 trees | M | v3 `forest_station.json` |
| B5.14 | Densest-decile canopy cover: baseline (m=1) 0.197 → D3 saved world 0.519 (still WOODLAND, not forest; ceiling-capped) | **M** | `canopy_cover_real.json` on the real saved plans; D2 ceilinged dry-run matched |
| B5.15 | Opaque crown radius = 0.85 × mesh XY half-extent | **A** | T6 sensitivity 0.70 / 1.00; replace if measured |
| B5.16 | Sightline blocked-width fractions (spruce 0.8, Scots pine 0.06) | **A** | replace if measured |
| B5.17 | m = ln(1−T)/ln(1−c); ≈ 2.7 for 0.36 → 0.70; upper bound under min-spacing | D | `canopy_cover.py` selftest (×2 density → u²) |
| B5.18 | ~~Live cost of m ≈ 2.7 ≈ +0.31 ms at forest_floor~~ **FALSIFIED (D4)**: measured **+2.442 ms** at forest_floor (m≈2.56, ceiled) and **+3.057 ms** at plaza. The v3 **0.100 ms/1000-trees upper bound is ~9× low** — D4 measured **0.854 (forest_floor) / 0.980 (plaza) ms/1000 added trees**. The cost model underpredicted by 2.4–3.1 ms at two stations. | **M (falsified)** | `d4_model_error.json`; `d4_perf.json` |
| B5.19 | HLOD proxy GPU share ≈ 0.5 ms (≈1% of frame); instanced proxies −61,427 GPUScene inst (4.37%) when toggled | **M** (treeline ×2.9 floor) | Item 8: `item8_share.json`; MRQ StartConsoleCommands `wp.Runtime.HLOD 0`, 6 `-game` renders |
| B5.20 | NVC classes: forest ≥ 0.60, woodland 0.25–0.60, sparse 0.10–0.25 | desk recall | standard physiognomic classes; target itself is ruling R5-2 |
| B5.21 | `SetLods` regenerates the chain from LOD0 | V | 5.8 "Creating LODs in Blueprints and Python" |
| B5.22 | Nanite foliage wants geometry, not masked cards | V | 5.8 "Working with Nanite-Enabled Content" |
| B5.23 | Recalibrated forest_floor density cap 2.38 → 1.162 (measured slope 1.576 vs old 0.185 ms/unit-m) | **M** | `t4_recalibration.json` from `d4_model_error.json` |
| B5.24 | forest_floor A/A min_detectable = 0.074 ms (not the v3 0.016; ~4.6× higher this build) | **M** | `t4_baseline.json` (3-run A/A) |
| B5.25 | r.Shadow.DistanceScale=0.25 buys +0.128 ms at forest_floor (ShadowDepths −0.221, 3.0×); only rung that pays; big shadow-distance visual trade | **M** | `t4_arm_B.json` |
| B5.26 | r.Shadow.RadiusThreshold (0.03–0.10) and r.Nanite.MaxPixelsPerEdge (2–8): no measurable forest_floor gain (trees too large / not tri-edge-bound) | **M** | `t4_arm_A.json`, `t4_arm_E.json` |
| B5.27 | r.Lumen.Reflections.MaxRoughnessToTrace cuts LumenReflections ~0.25 ms but frame p90 gains only 0.05 ms (< 0.10) | **M** | `t4_arm_D.json` |
| B5.28 | foliage.CullDistanceScale is INERT — all live FoliageTypes have enable_cull_distance_scaling=false; enabling needs an asset write | **M/V** | `density_baseline.json:1115`; FoliageType.h:600 |
| B5.29 | No cheap lever (T4 rungs or runtime cvars) recovers the forest_floor headroom; the ~2.7 ms cost is structural (ShadowDepths + NaniteVisBuffer + LumenReflections) | **M** | `t4_step2_summary.json` |

## Rulings assumed (Ryan may overrule)
R5-1 forest_floor budget 12.5 ms · R5-2 canopy target 0.70 for the densest decile · R5-3 in-place vendor mesh edits with `_SRC` duplicates.

## Parked candidates (not tasked)
Lumen reflections +0.324 ms (foliage roughness vs trace threshold) · WPO disable distance = 0 on all types ·
meadow mid-band via PCG runtime grid · per-species cost (no process-local lever exists).

## Withdrawn / superseded
None from the desk this round. v2's "RESOLVED–negligible" HLOD share stays reverted (v3).

## Verification session (V, 2026-09-21) — SUPERSEDED + corrected

- **SUPERSEDED — T1 coverage ratio 1.87 and band SSIM 0.46.** V1 re-ran the "see
  it" test at a ring station with a 15 m camera-clearance rule (the old station
  had a ForceLOD-4 trunk filling ~40% of the frame) and masked to the screen-space
  projection of the 128-512 m ConiferPine+SpruceSub instances. Band-masked, the
  card-vs-geometry difference is SMALL: SSIM(as-is,cards) 0.9166, SSIM(as-is,geom)
  0.9177 (margin +0.0011). The 1.87 / 0.46 figures were dominated by the near
  trunk and DO NOT survive band-masking. (input/v1_hold_took.json.)
- **SUPERSEDED — T3 hold cost +0.042 ms and the RHI_PrimitivesDrawn control.**
  V2 measured the post-hold as-is at forest_floor = 11.023 ms vs v3 pre-hold
  11.048 = -0.025 ms (x-1.6 min_detectable, noise); per-pass control (Basepass
  +0.001, ShadowDepths +0.007, Prepass -0.0005) all ~0. The +0.042 ms was noise.
  RHI_PrimitivesDrawn is abandoned as a control (GPU-driven instanced foliage
  draws indirect and never reaches that CPU counter). (input/t3_perf.json.)
- **T1 CONFIRMED still stands** — on the imposter tiling (desk crop 3), not on the
  superseded coverage/SSIM numbers. The tiling is a close/mid-range live-imposter
  defect; the hold removes it by pushing the card past the 512 m cull.

## Close-out session (C) — 2026-09-21 — two checks, then the picture changes
- **C1 (did the hold take — direct runtime readback) — NO-OP AT RUNTIME, MEASURED.**
  Mesh LOD Coloration + render-data readback in a fresh editor. The render-data
  ScreenSize array the runtime reads still carries the PRE-HOLD card sizes:
  ConiferPine LOD3 = 0.16821, SpruceSub LOD4 = 0.17 (t3_hold targets 0.03818 /
  0.02642), matches_t3_hold = false for both. Colour readback corroborates: the
  128-512 m band is ~80% card / ~19% geometric (legend read from the on-screen
  bar, validated vs BaseEngine.ini); a hold that took would render ~0% card there.
  (input/c1_lod_readback.json, input/c1_renderdata.json, derived/c1_lodcolor/.)
- **C1 ROOT CAUSE — the T3 hold NEVER PERSISTED (false-success `saved:true`).**
  The live tree .uasset mtimes predate the T3 run — ScotsPineTall_01.uasset
  2026-08-02, spruce_half_01.uasset 2026-08-14 — while only the _SRC backups
  carry the T3 mtime (2026-09-21 06:29). Both meshes are gitignored (git not
  involved). The T3 in-memory readback was lost on editor close; tree_lod_probe_
  t3.json and alpine_8k.json's "recipe == asset" note inherited the lost value
  and are STALE. This also explains V1 (SSIM tie) and V2 (~0 ms) — the hold was
  never applied, so nothing changed.
- **C2 (Showroom imposter) — the imposter does NOT tile in the vendor demo.**
  spruce_half_01 is placed there as HISM (FoliageInstancedStaticMeshComponent) +
  static actors with the SAME half_01_imposter material; forced-card and auto at
  150 m render clean billboards, no square tiles. **H1 (octahedral frame-blend
  fails under HISM) DISCONFIRMED.** Favoured now H4: the Alpine8K tiling is
  scene-specific (card drawn large/close because the hold never persisted;
  Lumen HWRT + exposure vs flat demo lighting). (input/imposter_defect.json,
  derived/c2_showroom/.)

## REPAIR session (R) — 2026-09-21 — the hold re-applied, persisted, and proven live

- **SUPERSEDES T3 "PASS" and V2 (and the C-session's open runtime question).** T3
  claimed the hold shipped; C1 showed it never persisted; this session RE-APPLIED
  it with a persist protocol and PROVED it reaches disk AND drives the runtime.
- **R1 — HOLD PERSISTED (the persist gate).** `SetLodScreenSizes` never marks the
  package dirty (StaticMeshEditorSubsystem.cpp:1020-1097), so T3's default save
  was a clean-package no-op. Fix: `Object.modify(True)` + `save_loaded_asset(
  only_if_is_dirty=False)`. Proven two ways in a DIFFERENT process from the writer:
  both `.uasset` sha256+mtime changed on disk (ScotsPineTall_01 c6ca202c→3b8a0b5a,
  spruce_half_01 0539bda4→c830a651), and a cold `get_lod_screen_sizes` in a fresh
  editor PID (32556 vs apply 21944) = the targets [.,.,.,0.03818] / [.,.,.,.,0.02642]
  within 1e-4, tris 32/6, slots 5/4, `is_lod_screen_size_auto_computed()` False.
  `r1_persist.json`. Status: **M**.
- **R2 — coloration INCONCLUSIVE (instrument contaminated).** Overlapping 2D boxes,
  no occlusion; ConiferPine (4 LODs) classified index-4 yellow with 0% of its own
  card in BOTH C1 and R2 (rule 13 shape). RenderData readback flipped
  matches_t3_hold False→True (persist+load, not runtime proof). `r2_lod_readback.json`,
  `r2_verdict.md`. Status: **INCONCLUSIVE**.
- **isolated_check — scene-defeated.** Synthesized isolated cameras rendered white
  (high-alpine cells outside the offscreen render region; a ring control rendered
  1.12M sat px); the dense band has no zero-intruder/frontmost box. ConiferPine
  best box leaned geometry (95.5% red LOD1). Not a clean read; deferred to R3.
- **R3 — HOLD TOOK AT RUNTIME (the decisive control).** 6 `-game` runs post-persist.
  forest_floor GPU p90 12.645 ms vs v3 pre-hold 11.048 = **+1.597 ms (99.8×
  noise)**; Basepass+ShadowDepths+Prepass **+1.131 ms (70.7× the 0.016 ms floor)** —
  the card→geometry conversion the hold performs. `r3_perf.json`. Status: **M**.
- **R5-1 ruling — OVER budget.** forest_floor p90 12.645 > 12.5 ms by 0.145 ms →
  T4 (rungs, `derived_ladder.json` target_tris) LISTED, not run; hold NOT reverted.
- **R4 — imposter override hypothesis DISCONFIRMED (read-only).** The recipe
  override `MI_half_01_imposter_nowind` EXISTS at `/Game/Materials/PN_NoWind/`
  (C2's exists:false checked the wrong folder). It shares base `MA_Imposter` and
  every scalar/vector/texture param with the vendor MI; the ONLY delta is two
  static switches (Level 1 Bending, Level 1 Wind) OFF — WPO only, not octahedral
  frame selection. `imposter_defect.json` R4 block. H4 stands, now resolved by
  R1+R3. Status: **M**.
- **check_recipe_lods** now refuses any probe not stamped cold_readback+distinct;
  reads `tree_lod_probe_cold.json`. Offline suite: NO FAILURES.
