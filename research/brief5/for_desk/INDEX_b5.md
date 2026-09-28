# Brief 5 (the forest) — send-back to the desk

**2026-09-21.** The desk deliverable arrived (via Downloads) and Brief 5 T0–T6
ran. v3 baseline stands. Fence honoured: T0/T1/T2/T6 read-only; T3 modified
exactly ScotsPineTall_01 + spruce_half_01 (+ their _SRC dupes) + recipes/
alpine_8k.json; no actor/FoliageType/level/HLOD-layer/Nanite change; editor closed
per R-EDITOR-CLOSE; world level byte-identical. Suite NO FAILURES across 34 checks.

## Headline
**The card defect is real and the fix is cheap.** Two of four species draw as a
6–32-triangle card for 88–97% of their live range (v3). The hold fix — push the
card's ScreenSize so it engages at 563 m (past the 512 m cull) — costs **+0.042 ms**
at forest_floor (×2.6 min_detectable), far under the 12.5 ms budget. Applied and
saved. The rung optimisation (T4) is unnecessary to meet budget.

## Per-task result
| task | verdict | evidence |
|---|---|---|
| **T0** tools in | PASS | both selftests PASS; `lod_ladder.py` re-derive **byte-identical** to `derived/derived_ladder.json`; 3 LOD scales = 1.0. |
| **T1** see-it | **CONFIRMED** (stills + texel gate) | Stills (`t1_see_it.json`, `derived/t1_stills/`): arm A = `r.ForceLOD 4` (both card species show their CARD, clamped), arm B = `r.ForceLOD 2` (geometry), ring_station, game-view. **Canopy coverage ratio B/A = 1.87** (geometry fills 1.87× the card's canopy — far outside 0.90–1.10) and **band SSIM = 0.46** (< 0.90): BOTH gates fail → defect CONFIRMED. The crop pairs show a flat dark billboard slab (card) vs a detailed 3-D trunk + foliage (geometry) — exactly the desk's predicted flat-card defect. `-game` A/B (`t1_game_ab.json`): ForceLOD honoured; GPU +2.900 ms (forest_floor, ×181) / +3.547 ms (ring, ×222) — the cost of forcing geometry (arm B ≈ 14 ms) bounds the *blanket* hold, not the surgical one. Also confirmed by T2's texel gate + v3's 93.8/97.1 % card-share. (Band mask = non-sky; r.ForceLOD is global so the whole forest is under test, no depth export.) |
| **T2** cards | done | `t2_cards.json`: ScotsPine card = crossed **billboard** (32 tris, 2048² atlas, dithered False); spruce_half card = octahedral **imposter** (6 tris, 4096² atlas, dithered True). Texel gate (`derived_ladder_texel.json`): **SpruceSub imposter magnified 87.5–125 m → gate VIOLATED**; ConiferPine billboard passes texel (its defect is parallax). frame_px: imposter 256 (4096/16 octahedral default), billboard 512 (estimate — the grid lives in the imposter material function, not a scalar). |
| **T3** hold | PASS | card engage **563.3 m** (ConiferPine) / **563.1 m** (SpruceSub) ≥ 563; last-LOD tris 32/6 + slots unchanged; `_SRC` dupes; **recipe == asset** (`check_recipe_lods.py` in the suite); forest_floor **+0.042 ms** ≤ 12.5 ms. |
| **T4** rungs | NOT NEEDED | the hold is +0.042 ms at forest_floor, under budget; the rung optimisation only reduces hold tris. Documented, not run. |
| **T5** HLOD stale | report only | `t5_hlod_staleness.json`: lowest-LOD geometry unchanged → HLOD not functionally stale; ~1225 Instanced cells conservatively source-stale from the re-save. NO build. |
| **T6** is-it-a-forest | done | `canopy_cover.json` + `canopy_cover_map.png`: **NO forest bins**; woodland 0.011, sparse 0.461, open 0.528; max cover **0.285 < the desk's predicted 0.36** (even sparser); m_for.p90_bin **5.48**. Sensitivity at crown 0.70/0.85/1.00. Crown radius (bounds half-extent, cheap ASSUMED-input read): ConiferPine 489 cm, SpruceSub 192 cm. |

## Cost table (× min_detectable = 0.016 ms, forest_floor)
| state | forest_floor GPU p90 | Δ vs 11.048 | × min_det |
|---|---|---|---|
| as-is (cards) | 11.048 (v3) / 11.098 (gate) | — | — |
| arm B (ForceLOD 2, blanket geometry) | 14.097 | +3.049 | ×190 (over budget) |
| **T3 hold (card→563 m)** | **11.090** | **+0.042** | **×2.6 (under budget)** |

## What the desk may derive Brief 5 from
The hold fix is shipped and measured (+0.042 ms, under budget); recipe == asset
for all four tree species with a suite check; the card composition + texel gate;
the canopy measurement (woodland, m_for.p90 5.48). Density stays measure-only
(item 8 + R5-2).

## What it still may not
The HLOD proxy GPU *share* (item 8) is still INCONCLUSIVE; density regeneration
waits on item 8 and the ruled target. (T1 coverage/SSIM is now captured —
CONFIRMED. The band mask is non-sky, not a 128–512 m depth mask, since r.ForceLOD
is global; the whole forest is under test, which only strengthens the verdict.)

## Manifest (this package)
- `for_desk/INDEX_b5.md`, `OVERNIGHT_LOG.md`
- `BASELINE.md`, `PCG_NOTES.md`, `BRIEF.md`, `FOR_CLAUDE_CODE.md`, `REGISTER.md`, `ITEM8_PLAN.md`
- `input/`: `t1_game_ab.json`, `t2_cards.json`, `t3_hold.json`, `t5_hlod_staleness.json`, `tree_lod_probe_t3.json`, `switch_distances.json`, `levers_b5.md`, `noise_floor.json`, `forest_station.json`, `ring_station.json`, `forest_cost.json`, + v3 inputs
- `derived/`: `derived_ladder.json`, `derived_ladder_texel.json`, `canopy_cover.json`, `canopy_cover_map.png`
- `scripts/`: `lod_ladder.py`, `canopy_cover.py`, `derive_forest_station.py`, `derive_ring_station.py`, `t1_analyze.py`, `t3_update_recipe.py`, `plot_canopy_map.py`, `switch_distances.py`, ...
- `GIT_LFS_AUDIT.md`; tools `scripts/check_recipe_lods.py`, `scripts/push_chunked.py`
