# Brief 4 CARVE_PLAN T4 — wet_shore implemented (2026-09-19)

**Off-disk. No editor. Audited PASS before first execution.**

## What T4 did
`derive_layer_weights.py`'s `wet_shore` layer (previously hardcoded zero) is
now the damp shoreline RING of each placed lake:
`dilate(footprint, 8 m) & (h >= level)`, strength fading `1 - smoothstep(0, 4 m, h - level)`,
unioned over the three placed lakes. NOT a global `|h-level| <= band` band.

- **Levels** from `recipes/water.json` (via `alpine_8k.json` `water.from_water_recipe`).
- **Footprints** from `hydro_derive.level_slice` (hydrology tool of record) on the
  committed 4x heightmap `research/brief4/input/alpine_8k_height_4x_2033.png`,
  upsampled to 8129 by exact vertex indexing (8129 = 4*2032+1). NN24: one derivation.
- **Constants** `WET_SHORE_BAND_M=4.0`, `WET_SHORE_RING_M=8.0` (module-level, like ROCK_DEG).

## Proof
**Selftest: 24/24 PASS** (was 16). New specimens:
- C (wet_shore): fires on the shore (0.93); **ZERO on same-elevation terrain far
  from the lake (0.000)** — the global-band discriminator; fades with height
  (0.93 > 0.10); weights sum to 1 with wet_shore active; no-water => identically zero.
- D (`--expand`, three directions with counts): wet_shore>0 + dirt_path==0 PASSES;
  dirt_path>0 REFUSES; both==0 PASSES.

**Real-data derive** (scratch prefix `_verify/brief4/t4_wetshore_2026-09-19/w8`):
- POSITIVE CONTROL EXACT — footprints 125.5 / 13.6 / 49.6 ha vs water.json (A/B/D).
- Footprint cells @8129: A 1,254,615; B 136,468; D 495,886.
- Coverage: wet_shore **0.02%** (~26,020 nonzero cells, a thin ring), dirt_path 0.00%,
  snow 9.92 / rock 42.30 / scree 11.97 / forest_floor 10.49 / gravel 0.52 / meadow 24.78.

**`_expand_check` on the real scratch weightmaps** (non-destructive; `expand()` itself
writes the fixed shipped path, so it was NOT run in T4):
- stored-sum over 1: 0.00392 (1/255); remainder vs wet+path+gravel+meadow gap: 0.00784
  (2/255); wet_shore max 1.0; dirt_path max 0.0. PASSES.

## The `--expand` amendment
`remainder == wet_shore + dirt_path + gravel + meadow` (wet added; load-bearing —
dropping it false-passes only while wet==0). `dirt_path` STAYS required-zero. wet_shore
folds into the shader remainder → **shipped PNG byte-identical**; promoting it to a
distinct stored surface is a MATERIAL-PASS item (R-LAYERS5 WHAT IS NOT DONE).

## Auditor findings (all fixed before first execution)
1. collar dropped `& ~fp` (a fine-grid cell inside the coarse footprint above level is shore).
2. `--out-prefix` resolve-and-check guard (absolute prefix escapes `os.path.join(REPO, ...)`).
3. exact vertex-index upsample, not PIL pixel-center resize (docstring precision, rule 9).
4. zero-lakes REFUSE vs pointer-absent declared-zero (rule 13).

## Not done in T4 (editor cascade)
The shipped `w8a`/`w8b`/`weights.png` were NOT regenerated — the canonical regeneration
belongs after the heightmap re-import (T5) and foliage regen (T9). Downstream `w8b`
consumers (`derive_planting_field`, ground-station tools, `check_layer_acceptance`) will
see non-zero wet_shore only when `w8b` is regenerated then.
