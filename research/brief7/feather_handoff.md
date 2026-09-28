# Brief 7 P1 — feather branch HANDOFF (look-p1-feather)

**Handed off deliberately** (context-exhaustion liveness rule): the feather is a large,
load-bearing artefact — a regenerated 8129² weightmap that drives the whole material, plus a
snow-line registration proof — and this session already made two diagnostic misses (wrong file,
wrong fix). The groundwork below is done + verified; a fresh session authors the change with this
spec in hand. Author on `look-p1-feather`, PR, stop for "merged, go" (world rebuild after merge).

## Ryan's four constraints (the spec)

1. **Do NOT blur the binary PNG.** Re-composite from the smooth w8 source: the 8→4 step is where
   the quantisation happened. SUM of grouped weights per stored layer (no winner-take-all), Σ ≤ 1
   enforced by scaling, Meadow = remainder as today. Then a **Gaussian σ = 1.5 texels (≈3 m ramps)**
   on the four stored channels, renormalised. Recipe: `weightmap.feather_sigma_px` (1.5), schema
   bump, validator refuses the old argmax path.
2. **Invariants on the new PNG:** feathered fraction (texels strictly 0<x<255) ≥ 25 % per channel
   at layer boundaries; Σ ≤ 255 everywhere; snow-by-aspect registration unchanged (re-run
   `hillshade_snow_check` + skyline IoU — proves the feather didn't drift the snow line).
3. **Surface lookup re-bakes from the feathered masks after merge** (argmax on smooth inputs is
   fine — the render needed ramps, not the lookup).
4. **Acceptance after merge:** rebuild k=0, displacement true; slope + near_ground + the same tight
   crop. Pass = boundaries 2–4 m fades near and far, no blocks; then the original P1 acceptance.
   Tag look-p1.

## Confirmed root (this session)

The imported `textures/alpine_8k_weights.png` is **near-BINARY**: R 92.5% / G 90.6% / B 82.6% /
A 97.8% of texels pure 0-or-255, only ~6–12% feathered. The upstream `w8a` stored channels are
already near-binary (snow: 87.6% <0.1, 7.7% >0.9, 4.67% mid — the precedence masks have narrow
ramps). Hard masks → hard 1 m block edges → the shatter. Mips do NOT fix it (they generate fine on
this NPOT/D3D12 — proven by lod_bias 6 changing the render; PadToPowerOfTwo not needed).

## Fix site — RESOLVED (was ambiguous)

`scripts/derive_layer_weights.py` has TWO collapse functions:
- **`collapse()` (line 563) = RETIRED v1** (R=snow, G=rock+scree, B=remainder). Do NOT touch — it
  does not produce the live PNG. Its own docstring at line 655 says so.
- **`expand()` (line 652) = LIVE producer.** Writes the five-layer contract **R=Snow, G=Rock,
  B=Scree, A=ForestFloor, meadow = 1−(R+G+B+A) derived in the shader**. Currently a byte COPY of
  `w8a`'s 4 stored channels (line 690: `img = round(clip(wa)*255)`), which is why it is near-binary.

The channel means confirm this contract: R̄=25 (snow 10%), Ḡ=108 (rock 42%), B̄=30 (scree 12%),
Ā=24 (forest 9%), remainder≈26% (grass) — matches the surface-lookup shares.

## Implementation plan (bounded)

In `expand()`, after line 684 (stored channels loaded), BEFORE `_expand_check` + write:
1. Read `sigma = recipe["material"]["weightmap_feather_sigma_px"]` (RECIPE path is the module const
   at line 74; load it). The four stored are already grouped sums of one w8 channel each (no
   argmax) — constraint 1's "sum of grouped, no winner-take-all" is satisfied by expand (it is a
   copy, not an argmax); the NEW work is the Gaussian.
2. `from scipy.ndimage import gaussian_filter`; feather each stored channel:
   `snow, rock, scree, forest = [gaussian_filter(c, sigma) for c in (snow,rock,scree,forest)]`
   (scipy 1.18 is installed — environment.md).
3. Renormalise so Σ(stored) ≤ 1 per texel (preserve the shader remainder ≥ 0): compute
   `s = snow+rock+scree+forest`; where `s > 1`, scale all four by `1/s`. (Feather can push Σ up at
   convex boundaries.) Re-run `_expand_check` on the feathered+scaled values — it must still find
   remainder ≥ 0.
4. Re-stack + quantise + write (line 690-691 pattern), now on the feathered channels.
5. `_expand_check` interacts with `wa`/`wb`; the feather is on the STORED channels only, meadow is
   the shader remainder — do not feather wb.

Recipe: add `material.weightmap_feather_sigma_px = 1.5`; schema bump in `recipes/schema.md`; the
recipe validator (`import_heightmap._validate_*` / wherever `material` is validated) **refuses a
recipe with no `weightmap_feather_sigma_px`** (constraint 1's "validator refuses the old argmax
path" — absent field == the old un-feathered path).

## Invariants to add (constraint 2) — a new `check_weightmap_feather.py`, wired into run_offline_suite

- **feathered fraction ≥ 25% per channel AT BOUNDARIES.** Define boundary texels as those whose
  channel is non-extreme OR adjacent to a different-argmax neighbour; assert ≥25% of boundary
  texels are strictly 0<x<255 per channel. (The global feathered fraction will be lower because
  most of the map is a single dominant layer — measure AT boundaries, not globally.)
- **Σ ≤ 255 everywhere** (the four stored channels; the shader remainder must stay ≥ 0).
- **snow registration:** re-run `scripts/hillshade_snow_check.py` on the new PNG + a skyline IoU
  vs the pre-feather snow mask — the snow line must not drift (σ=1.5 is a ±3 m ramp, so the 50%
  isoline should hold). This one may need a render for the skyline IoU — confirm offline-ness of
  hillshade_snow_check first.

## Already applied this session (kept)

- `T_Alpine_8k_Weights.uasset` mip_gen_settings = **SIMPLE_AVERAGE** (merged look-p1-weightmap-mips,
  applied to the asset; a real distance-aliasing improvement, harmless, kept). lod_bias reset to 0.
- Recipe `height_blend.k = 0`, `displacement.enabled = true` (main).
- World reverted to `pre-p1-material` (working).

## Post-merge sequence (constraint 3/4)

Regenerate `alpine_8k_weights.png` (offline, via the feathered expand) → re-import the weightmap
(mips already SIMPLE_AVERAGE) → rebuild material at k=0 → re-bake surface lookup (argmax on the
smooth feathered masks) → re-shoot slope + near_ground + the tight crop. Pass = 2–4 m boundary
fades near+far, no blocks → original P1 acceptance (no shards, small rocks) → **tag look-p1**.
Then A2 HLOD Lumen-FarField at P2 step 0.
