# FOR_CLAUDE_CODE — Brief 2 tasks

Read `CLAUDE.md`, then `BRIEF.md` §0, §3, §4, §5. Every task is one variable, one capture set (three player stations at the target profile, plus near_ground truth where stated), and one measurement line. Measurements come from `scripts/measure_concept_look.py` on the 1920-wide stills (copy it and `scripts/fog_budget.py`, `scripts/void_mask.py` into the repo's `scripts/`; each is a new element under the NEW-ELEMENT RULE). Lighting changes go through `apply_lighting` and the recipe's lighting block — never a hand edit in the editor — and every value is read back into the capture sidecar.

Session goal line: **"Brief 2: void test, fog coupling, fog derivation, sky light — one variable per capture."** E3/E4 continue in their own sessions; do not interleave.

Prerequisite: Brief 1's `perception` block exists (E1 done) and HLOD is built.

---

## Task 0 — The void test (decides who owns the flat band)

1. Payload: read back the SkyAtmosphere component's `ground_albedo`; set it to (255,0,255); confirm read-back; capture mid_slope and vista at the player instrument; restore the original; confirm read-back. Never save.
2. `python scripts/void_mask.py <still>` on both. Record `void_fraction` and look at `_void.png`.
3. **If void_fraction > 0.001**: the band is unrendered world. Set the far HLOD layer's `loading_range` to 1,600,000 cm (16 km; City Sample's value), spatially loaded; VERIFY in `HLODLayer.h` / `WorldPartitionHLODsBuilder.cpp` whether a range change needs `-SetupHLODs` to take effect, and run it if so (no `-BuildHLODs`). Recapture, recount. Also compare near_ground player vs truth skyline IoU (`compare_skyline.py` from the forge desk, or the measure's skyline arrays): must exceed 0.9 once the massif appears in the player frame.
4. **If void_fraction == 0**: the band is fog; skip to Task 1 and expect the ΔE measurement to explain it.

**Acceptance:** void_fraction 0.000 at both elevated stations, near_ground player/truth skyline IoU > 0.9. Log at both altitudes: which reading was right, with the number.

## Task 1 — Fog takes its colour from the sky

1. Project setting `r.SupportSkyAtmosphereAffectsHeightFog=1` via the editor API (standing rule 4), read back from the engine log/cvar.
2. Recipe fog block: `inscattering_luminance` black, `start_distance` 0, `directional_inscattering` on with luminance black (the atmosphere supplies both), `sky_atmosphere_ambient_contribution_color_scale` 1,1,1. Apply via `apply_lighting`; read back.
3. Recapture the three stations.

**Acceptance:** fog_vs_sky ΔE at mid_slope and vista < 0.08 (linear RGB distance between the non-sky featureless median and the horizon-sky median — add this as a fourth column to the featureless report).

## Task 2 — Fog density and falloff, derived

1. Read the world's Z range from the adopted heightmap sidecar and the valley floor from the recipe (the town's plaza Z is a fine datum).
2. `python scripts/fog_budget.py --world-z-min <min> --world-z-max <max> --valley-z <datum> --cam-z <datum+10> --targets 1000:0.75 4000:0.30 8000:0.10 --out _verify/bench/<date>/fog_budget.json`. VERIFY the UNIT constant against `HeightFogCommon.ush` first; if the engine's scaling differs, change `UNIT` and re-run — the targets stay.
3. Write `fog_density`, `fog_height_falloff`, datum Z into the recipe fog block with the derivation path in the sidecar; volumetric fog on, extinction 1.0, scattering distribution 0.4. Apply, read back, recapture all three plus near_ground truth.

**Acceptance:** near_ground haze_rise > +0.01 and far_contrast in 0.25–0.45; vista: far ridges softened but skyline still extractable (skyline mean not within 0.02 of the sky fraction — i.e. the ridge line is still found). Lock as R-FOG with the targets as the stated basis.

## Task 3 — Sky light

1. Recipe: `sky.intensity` 1.0, real-time capture on, lower hemisphere black. Apply, read back, recapture near_ground (player + truth).
2. Re-derive exposure with `polish` against the reference; expect the EV to move from −1.923 toward −1.0. Read back. Recapture.

**Acceptance:** shadow_tint_B at near_ground in 1.3–1.7; mean luma of the sunlit meadow band within 10% of its pre-change value after the exposure re-derivation (i.e. we lowered the fill, not the sun). If shadow_tint_B is still > 1.7, do NOT go below 1.0 — proceed to Task 4.

## Task 4 — Sky saturation via the atmosphere

1. If `atmosphere_solve.py` has a fit mode against a measured sky gradient, run it on the Alpine8K concept references' skies (measure with `measure_concept_look.py --out`, use the `gradient_zenith_to_horizon_linear` block); otherwise start from Electric Dreams' Mie scattering scale 0.01 / anisotropy 0.8, Rayleigh default, sourced in the recipe comment.
2. Apply, read back, recapture all three.

**Acceptance:** zenith band saturation lower than before; shadow_tint_B not higher; fog_vs_sky ΔE not higher (fog and sky move together now — that is Task 1 paying off).

## Task 5 — White balance and a quiet grade

1. Recipe PPV: `white_temp` = sun temperature + 1000 K (rule from BRIEF §3, cite ED/DR); contrast 0.95; bloom FFT intensity 0.4 (engine default kernel); grain 0; vignette 0; chromatic aberration 0. Apply, read back. Recapture near_ground.

**Acceptance:** highlight_tint (sunlit meadow median / luma) each channel within 0.9–1.1. Lock as R-GRADE; the bench profile forces grain/vignette 0 regardless of future taste changes and reads it back.

## Task 6 — Volumetric clouds

1. Spawn one `VolumetricCloud` (find-or-create by label) on the engine's `m_SimpleVolumetricCloud_Inst` (VERIFY path for 5.8), bottom 2.0 km, height 1.5 km; coverage parameter low (0.3) if the MI exposes one. Read back. Recapture vista and the E4 dolly.

**Acceptance:** vista sky fraction unchanged within 2 points (clouds are not sky-coloured; the split will count them non-sky — note the featureless columns and accept the shift), dolly score (tile-wise tool, when delivered) not above the pre-cloud baseline by more than 10%. If the dolly shimmers, `r.VolumetricCloud.ReprojectionQuality`/TSR settings are the next lever, not removal.

## Task 7 — Brief 2b, Lumen far-field on HLOD proxies (LAST; separate session; ruling first)

Proxies rebuilt with `support_ray_tracing=True` (the batched builder), `r.LumenScene.FarField=1`, `FarField.MaxTraceDistance` = 1,000,000. Score on vista shadow-side slopes (shadow_tint_B of the far band) and on peak VRAM at open. Ryan rules on go/no-go with the numbers; the RT-fence from R-RTFENCE stays on.

---

## Order and dependencies

0 → 1 → 2 → 3 → 4 → 5 → 6; 7 by ruling. 0–2 fit one session; 3–5 another; 6 with E4's dolly.

## Send-back

`_verify/bench/<date>/for_research/` after Task 2 and again after Task 5 (three player stills + truth, 1920-wide), the featureless four-column table, the fog_budget.json, the measurement lines, and REGISTER diffs. Brief 3 (surface: ground, rock, forest floor, snow by aspect, tiling) is written against the post-Task-5 near_ground frame.
