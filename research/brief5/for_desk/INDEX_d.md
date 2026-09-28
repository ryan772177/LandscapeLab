# INDEX_d — Brief 5 Daylight Density (D0b → D4): dry-run, regen, measure, REVERT

**10-line summary.**
1. The density upgrade was built, measured live, and **REVERTED** — it fits VRAM but busts the GPU frame budget.
2. Lever: one zone-map multiplier (m up to 5.48) + a post-multiplier per-bin density ceiling (D_max = 1,691 trees/bin) → **812,258 placed trees** (4.4×).
3. **VRAM fit** (D3): editor peak 5,211 MiB, -game ~4,990, vs the 13,312 DEVICE_HUNG ceiling.
4. **GPU busted** (D4, 3-run median): forest_floor **15.342 > 13.0**, open_max **14.151 > 13.0**, plaza **12.939 > 10.5**; treeline 7.261 (< 7.7 ok), vista 8.235 (< 8.5 ok); game thread all < 6.0.
5. **The model failed, not the trees**: predicted 12.90/9.882, measured 15.342/12.939 → underpredicted **+2.442 / +3.057 ms** (152× / 76× min_detectable).
6. The v3 **0.100 ms/1000-trees "upper bound" was ~9× low** — D4 measured **0.854 (forest_floor) / 0.980 (plaza) ms/1000 added trees**.
7. **Which pass carried it (measured)**: ShadowDepths (ff 3.19) + NaniteVisBuffer (ff 2.20) — shadow-depth + Nanite raster, not the v3 "not Nanite raster" inference.
8. Densest-decile canopy cover: baseline 0.197 → density **0.519** (still woodland, not the 0.60 forest target; the 0.151 gap is T4's job).
9. **Revert PROVEN**: git diff tag..HEAD empty, 6/6 LFS-oid match the fence tag, working tree clean; cold -game forest_floor **12.620 ms** in the 12.645 ± 3×0.016 band (counter moved 15.342 → 12.620).
10. **Blocked forward**: T4 gate session must recalibrate the zone map from `d4_model_error.json` before any density re-run; clutter cost (D5) still owed; the SpruceSub build-stall root cause owed before any rung rebuild.

## Cost table — GPU p90 (ms) per station: as-is → hold → density (reverted)

| station | as-is (v3 pre-hold) | hold (m=1, shipped) | density (D3 812k) | ruled line | verdict |
|---|---|---|---|---|---|
| forest_floor | 11.048 | 12.645 (cold 12.620) | **15.342** | 13.0 | **OVER +2.34** |
| open_max | — (new station) | — | **14.151** | 13.0 | **OVER +1.15** |
| plaza | — | 9.476 | **12.939** | 10.5 | **OVER +2.44** |
| treeline | — | 7.139 | 7.261 | 7.7 | ok |
| vista | — | 8.164 | 8.235 | 8.5 | ok |

HLOD per-station share (item 8, B5.19, not re-measured — D6 skipped as there is nothing to rebuild): treeline ≈ 0.576 ms (≈1% of the MRQ frame); scales with tree count but the live-tree GPU cost dominated the budget bust, so HLOD was not the deciding factor.

## Canopy cover per decile — before vs the (reverted) density world

| percentile | baseline (m=1, shipped) | density (D3, reverted) |
|---|---|---|
| p50 | 0.091 | 0.343 |
| p75 | 0.159 | 0.496 |
| p90 (densest decile) | 0.197 | **0.519** (target 0.60) |
| max bin | 0.285 | 0.562 |
| forest-class bins | 0% | 0% (ceiling capped below 0.60) |
| woodland-class | 1.1% | 61.1% |

## Gallery

**NOT captured** — an offscreen editor does not land a HighResShot PNG (known -game/offscreen non-viability, item 8); windowed risks the 2026-09-12 GPU-Present crash on this DEVICE_HUNG machine, and MRQ was too heavy for a reference-only deliverable. The dense world's numbers (model error + per-pass split) are the substantive record; the picture is the only loss. (`d4_stills.json` records the miss.)

## REGISTER status

- **B5.14** P → **M**: densest-decile cover baseline 0.197 → density 0.519 (woodland, not forest), measured on the real saved plans.
- **B5.18** → **FALSIFIED**: the 0.100 ms/1000-trees upper bound is ~9× low (measured 0.854/0.980); the cost model underpredicted 2.4–3.1 ms.
- **B5.19** stands (M, item 8 HLOD share).

## Deliverables (research/brief5/derived/)

`zone_map.json`+`.png` (D0b, ff cap 2.38) · `density_ceiling.json` (D_max 1,691) · `d2_zone_counts_ceiled.json` · `canopy_cover_ceiled.json`+`canopy_cover_map_ceiled.png` · `canopy_cover_real.json` (B5.14) · `d3_verdict.json` (VRAM PASS) · `d4_perf.json` (REVERT_D3) · `d4_model_error.json` (the model failure) · `d4_stills.json` (stills miss). Tooling: `zone_map.py`, `density_ceiling.py`, `d2_dryrun.py`, `d3_regen.py`, `d4_perf.py`, `d4_model_error.py`, `d4_stills.py`; `place_foliage.py` gained `--density-zone-map`/`--density-ceiling`/`--out-dir`.
