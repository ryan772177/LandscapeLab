# REGISTER addendum — Brief 3

## MEASURED
- B3.1 Real surface ends at the 256 m runtime grid range; proxies stand in the detail band (vista frame; hlod_ladder_vista.json).
- B3.2 near_ground meadow shows no visible repeat (tiling_score peaks 0.05–0.15 at all periods 12–150 px).
- B3.3 Grey card at WB=5200 K: R/G 1.26, B/G 0.74 — horizon sun reddened by the atmosphere past its source temperature.
- B3.10 Surface albedo, LINEAR luma, 4K packs: Snow007A **0.8357**, Ground037 **0.3126**, Rock051 (bound) **0.1805**, Rock016 **0.0712**, Gravel021 **0.0391**, PineNeedles001 0.0171 (mostly black under alpha — not a surface albedo). `scan_surface_stats.py`.
- B3.11 ambientCG publishes **no physical size for these assets at all** — `dimensionX/Y/Z = 0` from its own API, not merely absent from the shipped sidecars. The stretch check is permanently unavailable for this vendor; the derived tile is unaffected (it depends only on resolution and viewing distance).

- **B3.13 THE GRADE CONTRAST BOUNDARY.** `PostProcessCombineLUTs.usf:98`
  applies `ColorContrast.xyz * ColorContrast.w`, and `apply_lighting`
  wrote `Vector4(c,c,c,c)`. **Every frame before commit `3525bc87` had an
  EFFECTIVE contrast exponent of 0.9025 while the recipe declared 0.95;
  every frame after has 0.95.** Any comparison spanning that commit must
  say which side it is on. The recipe now declares the EFFECTIVE value
  and it is written xyz = 1 with the value in w, with the host refusing
  on the product.
- **B3.14 THE SUB-TILE PERIOD IS THE WEIGHTMAP, not shading and not the
  surface textures.** Discriminated on a BaseColor GBuffer pass (albedo,
  no lighting): the structure is PRESENT there and STRONGER than in
  FinalImage — Rock 0.1511→0.1673, Scree 0.3272→0.3897, Grass
  0.4163→0.6227 at 30–100 m. A diagnostic 2-texel weightmap blur then
  moved it: Rock −41.4%, Scree −31.7% at 30–100 m; Rock −26.3%, Scree
  −27.2% at 100–300 m. Grass ROSE 27.8% at 30–100 m, which is consistent
  with Grass being the shader REMAINDER — blurring the stored channels
  reshapes its mask rather than smoothing it. Weightmap restored; nothing
  committed.
- **B3.15 THE SHADE ACCEPTANCE MOVES TO PPI0.** Measured **2.5166**
  against the UNTRANSFORMED band 2.184–2.940 — PASS, mid-band. Each
  channel is divided by the lit card's own channel first, since the lit
  18% neutral IS the white reference and PPI0 carries no white balance.
  The FinalImage reading (2.2598 in a transformed 1.8182–2.2827) is
  recorded beside it and is no longer the acceptance.

- **B3.16 THE BASECOLOR PASS CARRIES THE EXPOSURE — A PRACTICE LINE, NOT
  A ONE-OFF.** `FinalImageBaseColor` maxes at **6.31e-05**, and
  6.31e-05 / 2^−13.5898 = **0.778** (p99 → 0.615): bounded by 1 and
  plausible, so the pass carries the bench's compensation exactly as the
  lit passes do. Read as albedo it is wrong by four orders of magnitude.
  **PRACTICE: every GBuffer read divides by 2^compensation_ev and
  ASSERTS the result lands in a plausible reflectance range** —
  implemented in `task4_bin_tables.py` (refuses outside 0.01–1.0) and
  `task4_meadow_albedo.py`. It hid for two sessions because every prior
  consumer was scale-INVARIANT (the split-(b) discriminator, the period
  spectrum, std/mean), so a constant factor changed none of their
  numbers and nothing complained. **The absence of complaints was not
  evidence of correctness**; the first consumer needing an absolute
  threshold found it immediately — a `> 1e-4` guard that sat above the
  entire frame and excluded every pixel.

- **B3.17 STOCHASTIC TILING DOES NOT REMOVE SCREE'S 85 px PEAK, AND THAT
  IS EVIDENCE ABOUT WHAT THE PEAK IS.** Sweep at variation_scale
  0.25 / 1.0 / 4.0 against a rebuilt OFF control, all four cells at one
  code state, bin 30–100 m, threshold 0.0250:

      OFF (control)  0.08913  peak 85 px  FAIL   broadband 0.86058
      0.25           0.06017  peak 85 px  FAIL   broadband 0.86121
      1.0            0.08439  peak 85 px  FAIL   broadband 0.86865
      4.0            0.05368  peak 85 px  FAIL   broadband 0.86321

  The peak's LOCATION never moves. Stochastic tiling randomises the
  texture's UV offset per cell, so **if this structure were the scan
  repeating, breaking UV continuity would destroy it.** It did not. That
  and its position — 85 px against a predicted 70.9 px for the 2.00 m
  tile, **1.20×** — both say the 85 px structure is NOT the Scree scan's
  tile, and Task 3's one tiling FAIL is probably misattributed.
  **NOT ADOPTED**: no value registered, recipe and material returned to
  OFF.

- **B3.18 ⛔ THE `make_foliage_material` EMPTY-NAME WINDOW — A PRACTICE
  LINE.** `--name` is optional and defaults to empty, while the material
  is built at a COMPUTED name. The post-verdict save called
  `save_asset("/Game/Meshes/Materials/" + args.name)` — a DIRECTORY, not
  an asset — and `save_asset` on a bad path neither raises nor returns
  anything the caller reads, so the payload still printed its success
  marker and the tool reported **"saved after the verdict"**. Measured
  2026-09-13: `M_grass_medium_01` was rebuilt, rendered correctly in
  three captures, and its `.uasset` on disk was still **five weeks old**
  (Aug 2 → Sep 13).
  **PRACTICE: for any material built by this tool in that window,
  DISK-READ checks are SUSPECT and GRAPH-READ audits STAND.** A graph
  read asks the live editor what the material is; a disk read asks what
  was last persisted, and the two diverged silently for five weeks.
  Fixed two ways: the save targets the computed name, and it reads back
  against the editor's DIRTY-PACKAGE LIST — a different instrument from
  the marker the payload prints. (`Package.is_dirty()` does not exist on
  the reflected Package in 5.8; the dirty-census API is the one that
  works.)

- **B3.19 THE HLOD LAYERS THAT ARE NOT IN USE.** `hlod_layer` is **None
  on every actor in the level** — the Landscape, its 256
  LandscapeStreamingProxy actors, all 1093 InstancedFoliageActors, all
  1451 StaticMeshActors. The 1042 `WorldPartitionHLOD` actors belong to
  **`Alpine8K_HLODLayer_Instanced`** and **`Alpine8K_HLODLayer_Merged`**
  only, confirmed across 20 sampled manifest sections (89 actors; no
  other layer name appears).
  **`Alpine8K_HLODLayer_Landscape` and `Alpine8K_HLODLayer_FoliageApprox`
  are UNREFERENCED ASSETS**: editing their settings changes nothing that
  renders, and there are no "Landscape cells" to count or build.

- **B3.20 TASK 3 CLOSED ON THE PLAYER INSTRUMENT.** No texture-tile
  repeat is player-visible at either bin: Grass 30–100 m 0.04005 against
  a 0.05338 threshold (0.75×) PASS; Rock and Scree NO PEAK; all three NO
  PEAK at 100–300 m. n=3, temporal_sample_count 8 read back, TSR, warm-up
  40, display-referred. The temporal-1 figures (Grass 0.10960, Rock
  0.10147, Scree 0.09030, all FAIL) are recorded as the TRUTH-INSTRUMENT
  result — aliasing at temporal 1, **not player-visible**.

## DERIVED
- B3.4 Texel density 815/m at 3 m (4K/90°): tile = tex/815 → 4096: 5.0 m, 2048: 2.5 m. `texel_budget.py`.
- B3.5 Repeat visibility: a 5 m tile is most detectable at 100–250 m (1–2.5 cpd), threshold ~0.6–1.2% Michelson; below 30 m a repeat is not seen.

## RULED
- B3.6 Loading range 768 m (fallback 512 m on perf), HLOD0 to 2 km — precondition for all surface work.
- B3.7 WB set by the grey card to neutral; warmth as an explicit grade offset (0 on the bench).
- ~~B3.8 shadow_tint_B band 1.10–1.60 under neutral WB (Brief 2b).~~
  **REJECTED and REPLACED 2026-09-12b.** Two faults, either one fatal:
  it measured TERRAIN ALBEDO rather than light (the grey card read the
  light neutral at R 1.026 / B 1.0455 while the metric reported 80% blue
  excess), and it was derived at **WB 5200** then applied at **3481.9** —
  a band quoted without its white point is not a band.
- **B3.12 (replaces B3.8) card-pair shade band 2.184–2.940, AT WHITE
  POINT 3481.9 K.** Metric `(B/luma shade)/(B/luma lit)` on two 18%
  cards of one known albedo, one occluded by a blocker cube, Rec.709
  luma, scene-linear EXR. Derived by `shade_reference.py` (selftest OK)
  across D6500–D10000. **MEASURED 2026-09-13: 2.2598 — PASS.** The same
  frame corroborates two other results from a different code path: the
  lit card reads luma 0.180039 against the 0.18 exposure target and
  B/luma 1.0055 against neutral. Shaded card is 10.06% as bright as the
  lit one (so the blocker occludes), crop std luma 0.000282 (so it is
  uniformly shadowed). `scripts/shade_card_pair.py`.

## PROPOSED
- B3.9 Eight-layer set with derived weights (snow by aspect, forest floor from canopy, scree from flow proxy), height-blend edges, scanned surfaces at derived tiles, stochastic tiling, grass ground-colour matching, proxies with draw-distance texture sizing.

## TOOLS
- `texel_budget.py` — texel density, tile size, CSF repeat threshold by distance.
- `tiling_score.py` — autocorrelation repeat score on a ground crop; self-test PASS (tiled 0.999 vs noise 0.016).
- **`task3_weight_period.py` — the CORRELATION-LENGTH-IN-PIXELS TEST.**
  Open-band (0.3–20 m) period search by the SPECTRUM of the
  autocorrelation, so a repeat and all its harmonics collapse to one
  line; floor snr 100, DERIVED (negatives 3.89 / 9.82 / 18.06, positives
  3.7e5–4.0e6). **Its `cross_bin_check` is the reusable instrument: a
  world-fixed pitch holds its METRES and shrinks in PIXELS with
  distance; a screen-space process holds its PIXELS and grows in
  METRES.** Whichever unit is conserved across two depth bins names the
  domain, and it refuses when neither is conserved clearly. This is what
  stopped Rock's 1.002 m correlation length being reported as the
  1.000 m weightmap texel pitch — measured, it is conserved in pixels
  (Rock 10% vs 119%, Scree 5% vs 107%, Grass 51% vs 172%), so it is
  screen-space and the match was a coincidence of viewing distance.
  **General form: when a number matches a known constant, find the
  parameter the two would disagree about and move it.**
- `task4_bin_tables.py` / `task4_reference_bins.py` — meadow luminance
  variation per depth bin, render and references on the same metric.
  Each REFUSES the wrong capture (FinalImage needs the tone curve ON,
  BaseColor needs it OFF).

## REJECTED
- Typed `tiling_m` — derived from texture resolution and the near viewing distance.
- Snow by height alone — no aspect asymmetry; reads as a texture on a shape.
- Same layer under canopy and in the open.
- Judging surfaces before the loading range matches the ladder.
- **READING PAST A DIAGNOSTIC THAT FIRES EVERY RUN.** Nine payloads printed behind `__RESULT__` while `ue_exec`'s marker is `__LL__`, so every run reported *"COULD NOT LOOK: payload produced no marker"* and fell back to dumping *"raw output (first 3000 chars)"* — and the answer was visible in the dump, so the warning was read past each time. It cost a read silently TRUNCATED at character 2990, mid-object. **A diagnostic that fires on every run and is read past on every run has stopped being a diagnostic**; it has become part of the expected output. The rule: if a tool says it could not look and you can see the answer anyway, you are reading a FALLBACK path, and fallback paths have limits the main path does not (2026-09-11).
- **`corr(G, dH/drow)` POSITIVE FOR DirectX** — the normal-convention
  prediction carried in `.claude/skills/asset-intake/SKILL.md` and copied
  into `scan_surface_stats.py`. **Symptom: every pack reads as the
  opposite of its filename** — six of six ambientCG packs, including the
  three already bound. Correct: **GL positive, DX negative**, because
  rows increase downward while OpenGL's +Y runs up the image, so
  `dH/dy_GL = -dH/drow` and `N_y ∝ +dH/drow`. The skill's own red-channel
  prediction refutes it: the same minus in `(-dH/dx, -dH/dy, 1)` cannot
  apply to X and not to Y. Reference: `scan_surface_stats.py --selftest`,
  which constructs normals analytically under each convention (DX
  -1.0000, GL +1.0000) and so depends on neither the doc nor the vendor
  (2026-09-12).
- **A CONTROL THAT SHARES NO TERM WITH THE DEFECT.** The red-channel
  control PASSED on all six packs while the green verdict was inverted —
  red is identical in both conventions, so it tests the gradient's sign
  and is structurally blind to the y-flip. **A control guards only the
  terms it shares with the claim.** Ask not "did the control pass" but
  "which way could this be wrong without moving the control", and if
  there is such a way, the control is not evidence about it (2026-09-12).
- **`PineNeedles001` AS THE NEEDLE-LITTER LAYER.** It PASSES the 16-bit
  height gate and is still not a surface: **opaque fraction 0.033 — 96.7%
  of texels transparent**, an overlay decal. Tell before measuring: it
  ships an Opacity map and NO ambient occlusion. A ground layer must
  cover the texel it is asked to cover; a height gate does not test
  coverage (2026-09-12, `scan_surface_stats.py`).
- A CONCAVITY GATE on the ground-station search — **98.6% of cells have a concave azimuth**, so it rejected 387 of 1,760 views and had **zero selectivity**. Promoted from a selftest fixture into a gate without ever measuring its selectivity against the world (2026-09-11, `derive_ground_station` v2).

## AUDIT §8–§10 — entries added 2026-09-14 (overnight)

- **B3.21 (SUPERSEDES the 2026-09-13 Task 5 acceptance; AUDIT H-1)
  LANDSCAPE HLOD DOES NOT RUN THROUGH AN HLODLayer's MeshMerge
  SETTINGS.** `ULandscapeComponent::GetCustomHLODBuilderClass()` returns
  `ULandscapeHLODBuilder` UNCONDITIONALLY
  (`LandscapeComponent.cpp:97-100`), and `HLODBuilder.cpp:354` regroups
  every source component by that class before building. So the 09-13
  write of `mesh_merge_settings.material_settings.texture_sizing_type`
  onto `Alpine8K_HLODLayer_Landscape` could not have governed the
  landscape under ANY layer assignment. **That acceptance is VOID, not
  failed** — nothing it changed was ever read by the thing it meant to
  change. The real levers are six `ALandscapeProxy` properties
  (`LandscapeProxy.h:953-974`), all `LandscapeOverridable`.
  **AND the earlier reading of "0 of 4,339 actors name an HLOD layer"
  as "the landscape is outside HLOD" was wrong in the expensive
  direction**: a null per-actor `HLODLayer` FALLS BACK to the world
  default (`WorldPartitionRuntimeHashSetConversions.cpp:45`), so
  everything has been in Instanced → Merged all along, and assigning the
  Landscape layer would have been a 257-actor streaming change dressed
  as a correction. `_Landscape` and `_FoliageApprox` are REDUNDANT;
  deletion deferred to the audit rewrite session.

- **B3.22 (AUDIT R-1) EVERY COMPARISON REPORTS ITS SAMPLE COUNT BESIDE
  ITS VERDICT, AND A ZERO COUNT REFUSES.** Promoted to CLAUDE.md
  standing rule 13. Pointer: the 2026-09-13 GameOverride precedence
  test, where two instruments were declared to agree and the second had
  parsed **0 of 22** values, because a bare `sg.X` console query prints
  nothing at all. "No differences found" from an instrument that found
  nothing to compare is silence wearing agreement's clothes, and in a
  report the two read identically. Rule 12's sibling — 12 catches a
  value never read back, 13 catches **a read that returned nothing and
  was counted as confirmation**.

- **B3.23 (AUDIT S-1/S-2) THE SKY LIGHT IS WHITE, AND ITS COLOUR WAS
  sRGB-ENCODED TWICE FOR THE LIFE OF THE CODE.** `set_light_color`
  ENCODES — `bSRGB = true` means *emit sRGB bytes*
  (`LightComponent.cpp:1130-1134` → `Color.cpp:251-267`) — and
  `apply_lighting` pre-encoded as well, on a docstring's claim that the
  engine would *decode*. Recipe linear `[0.42, 0.6, 1.0]` was stored as
  `FColor(215, 231, 255)`, i.e. `encode(encode(recipe))`, so the light
  ran at linear `(0.6795, 0.7991, 1.0)` — **R 62 % high, G 33 % high, B
  exact**, because 1.0 is a fixed point of the curve and the one channel
  a human would spot-check could never show the defect.
  Ruled to `[1, 1, 1]`: a physical real-time-captured sky light is not
  tinted, and all four sky lights in the Epic sample census read white.
  ⛔ **The white read-back cannot prove the fix** — the broken path
  produces identical bytes at 1.0 — so the fix is proven separately on a
  discriminating colour.

- **B3.24 (AUDIT S-9) HLOD BATCH SIZE IS A VRAM DECISION, NOT A
  SCHEDULING ONE.** Measured on batch 0 of the 2026-09-14 build: VRAM
  climbs ~64 MiB per cell within a batch and is reset only at the batch
  boundary. 191 cells peaked at **14,701 MiB against the 15.2 GB budget**
  whose breach produced `DEVICE_HUNG` on 2026-09-12 — within 500 MB.
  Re-planned to 24 batches of 92–98 cells, projecting a ~6.9 GB peak.
  ⚠ The 12-way and 24-way partitions **do not nest** (new section 0
  shares 98 of batch 0's 191 cells; sections 1–3 share none), so there
  is no clean resume point across a re-partition and batch 0's 191 cells
  are rebuilt. Verified by comparing GUID sets, not assumed.

- **B3.25 (AUDIT S-12) ONE TRUTH INSTRUMENT.** `--instrument truth`
  (editor + HighResShot, NO MoviePipeline, therefore NO GameOverride)
  and `--truth` (MRQ with all 20 GameOverride properties) were two
  different instruments wearing one word, and nothing in a sidecar said
  which you had. `--truth` survives and its sidecar must record all 20
  or the capture REFUSES; `--instrument truth` exits 2 with an
  explanation of what it lacked.

- **⚠ B3.12'S BAND IS NOW QUOTED AT A WHITE POINT THAT NO LONGER HOLDS.**
  B3.12 states the card-pair shade band 2.184–2.940 **AT WHITE POINT
  3481.9 K**. The 2026-09-14 re-solve moved `white_temp_k` to **3415.7**
  (and `white_tint` to −0.0113, `compensation_ev` to −14.2571). This is
  precisely the fault B3.8 was rejected for: *a band quoted without its
  white point is not a band* — and a band quoted with a STALE one is no
  better. The band must be re-derived by `shade_reference.py` at 3415.7
  before the next shade acceptance, or the measurement re-taken at the
  old white point. **Not re-derived overnight: it needs a ruling on
  which white point the band belongs to.**

## AUDIT CLOSURE — Block A entries added 2026-09-15

- **B3.26 (A-6, R-WB2x2 / AUDIT H-10) THE WHITE BALANCE IS A COUPLED 2x2,
  AND THE JOINT SOLVE NULLS THE RESIDUAL THE FIRST-ORDER SOLVE LEFT.**
  The 09-13/09-14 first-order solve nulled each axis on its own slope and
  left B/G 1.0332 (out of 0.97-1.03) — the off-diagonal coupling it
  dropped (temp moves B/G at -3.678e-4/K; tint moves R/G at +0.588/unit).
  Solved jointly from the measured card against the full 2x2 matrix of
  the 09-14 run: white_temp_k 3415.7 -> 3438.6, white_tint -0.0113 ->
  -0.0248. CONFIRMED on a certified capture: card R/G 1.0014, B/G 0.998,
  both in band. Solver `scripts/wb_joint_solve.py` (selftest 4/4).
- **B3.27 (A-7, R-SHADEBAND) THE SHADE BAND TRACKS THE WHITE POINT, AND
  A-6 MOVED IT.** Re-derived at the in-force 3438.6 K:
  `shade_reference.py --white 3438.6` -> **2.229-2.998** (the desk's
  2.254-3.029 was @ 3415.7, before A-6). `shade_card_pair.py`'s selftest
  now RE-DERIVES the band from shade_reference at BAND_WHITE_K, so it
  cannot drift from its white point again. Measured on the 09-13 PPI0
  instrument: **2.1896**. The recipe's FinalImage pair 2.587-3.764 is
  STRUCK (FinalImage is not the band's domain).
  **AMENDED same day (R-SHADEBAND, LOW-SUN FLOOR): the shade illuminant
  floor is D6000 not D6500 for a sun below ~30 deg.** The shade card sees
  hemispherical skylight only, which is warmer (less blue) than the D6500
  overhead-daylight default at low sun (Hernandez-Andres et al. 2001,
  JOSA A 18). Sun at 12 deg -> floor D6000 -> band **2.065-2.998**, and
  **2.1896 is PASS** (it sits at ~D6380). No new capture; only the band's
  shade range moved. shade_card_pair.py carries BAND_FLOOR_K = 6000 and
  its selftest re-derives at that floor. This is the in-force band.
- **B3.28 (A-8, R-GATE / AUDIT S-11) THE CONTENT GATE MODELS CANOPY
  POROSITY.** `pct_sky_effective = pct_sky + 0.21 x pct_canopy`, threshold
  UNCHANGED at 0.20. Porosity 0.21 DERIVED (17.25 missed sky-points /
  81.33 canopy at near_ground), predicts mid_slope and vista on stations
  it was not derived from. Read-back over the last 14 captures: near_ground
  prediction 0.0075 -> 0.1783 (was 17.8x-25.4x low), 0 refused (was 1
  false-refusal); the mid_slope void (0.9383) still REFUSES; the ground
  station (pct_canopy None) DEGRADES with the gap named (NN6).
- **B3.29 (A-9 hygiene) THE PRE-09-13 WARM-UP CAVEAT NAMES BOTH
  MECHANISMS** (eye adaptation + sky-light real-time-capture
  time-slicing), the S-7 slope note (0.7598 is a look-chain quantity,
  never enters a PPI0 solve), F-4 (Blueberry_01 LOD0 tris ?->195), V-5
  (the AA method AAM_NONE is inert — override set False explicitly), and
  the exposure cvar probe now carries a positive+negative control pair
  (P1-5/FP-4). The stale band literal 2.184-2.940/3481.9 was swept from
  all three live-code prose sites in the same commit (rule 4/9).

## OPEN
- Q16 Does a runtime-grid range change require SetupHLODs? Memory cost at 768 m at each zone (E3).
- Q17 CLOSED 2026-09-15 (B-4): **the parameter is not coverage.** Measured at vista, lowering Cloud_GlobalCoverage 0.3->0.1 RAISED the bright-cloud fraction of the sky (9.5%->28.2%) and sky median luma (0.1875->0.2116) -- **non-monotonic/inverted**. 0.3 is NOT near-total overcast (~10% bright cloud, dim). Recipe UNCHANGED at 0.3 (report, do not tune). **The sweep for a cloud LOOK is DEFERRED to Brief 4** (needs a reference sky; no value moves before then). See _verify/bench/2026-09-15/CLOUD_COVERAGE_B4.md.
- B-6 CLOSED 2026-09-15 (S-10): the four ALandscapeProxy HLOD bake props are now in sample_census (landscape_hlod section); Alpine8K reads 4096 / SPECIFIC_SIZE / None / LOWEST_DETAIL_LOD x257. **The Electric Dreams comparison is closed as UNAVAILABLE** -- the Epic sample projects are not installed on this machine -- and our DERIVATION STANDS on its own basis (cell 2000 m / (512 m / 1920 px) ~= 7,500 -> 4096 at a 1 km judgement distance); it never depended on matching ED. See _verify/bench/2026-09-15/LANDSCAPE_HLOD_CENSUS_B6.md.
- Brief 2c Lumen far-field — by ruling.
