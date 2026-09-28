# Brief 5 — verification session (V) send-back

**2026-09-21.** Read-only except V5b (one config change). No git push, no history
op. The desk rejected three numbers; two are SUPERSEDED, and the picture is
corrected. Editor closed clean per R-EDITOR-CLOSE; world byte-identical.

## Bottom line
The desk was right on all three rejections. **T1's coverage/SSIM (1.87 / 0.46)
and T3's +0.042 ms hold cost are SUPERSEDED.** Band-masked, the card-vs-geometry
difference at 128-512 m is small, and the surgical hold's cost is ~0 ms. The T1
CONFIRMED verdict still stands, but on the imposter TILING (close/mid range), not
on the polluted numbers. The hold is still the right fix (removes the live card),
still under budget (1.48 ms margin), so T4 stays off the list.

## Per-task
| task | result | file |
|---|---|---|
| **V0** history rewrite recorded | Done, plain sentences: `git lfs migrate import --above=100MB` at reflog 05:27, why the rule was broken (Ryan's explicit authorization + the >100 MB github reject wall), refs rewritten (main; tag re-pointed 0e8787a2->7e796801; pre-lfs-migrate-old on e64922d4, LOCAL only), per-file blob disposition (all >100 MB moved to LFS, none dropped), LFS 39,539-across-history vs 9,254-at-HEAD, and a correction of the "clean push" impression. | `for_desk/OVERNIGHT_LOG.md` |
| **V1** did the hold take? | T1 numbers **SUPERSEDED**. New ring station (15 m clearance, no near trunk); screen-space band mask (projected 128-512 m ConiferPine+SpruceSub bboxes, no depth). Band-masked SSIM(as-is,cards) **0.9166** vs SSIM(as-is,geom) **0.9177** (margin +0.0011 -> hold took, but marginal; card vs geometry differ little at band distances). AGREES with V2. | `input/v1_hold_took.json`, `derived/t1v1_stills/` (asis/armA/armB + 3 crop trios + band_mask) |
| **V2** real hold cost | forest_floor post-hold **11.023** ms vs v3 pre-hold 11.048 = **-0.025 ms (x-1.6, noise)**; per-pass control Basepass +0.001 / ShadowDepths +0.007 / Prepass -0.0005 -- all ~0. The +0.042 ms was noise. ring_v1 (920 band trees, no pre-hold baseline) 10.926. **V1 and V2 AGREE** (small band effect, ~0 cost). | `input/t3_perf.json` |
| **V3** imposter root-cause | Favoured **H1**: the octahedral MA_Imposter's frame selection/blend fails under HISM instanced rendering (samples one atlas cell -> square tiles). H2 (RoundingOffset/frame-count) and H3 (placement scale/bounds) less favoured. Decider NOT run: open the vendor `Showroom` map read-only and view the imposter at 100-300 m. | `input/imposter_defect.json`, `input/imposter_defect_read.json` |
| **V4** far-forest tiles? | The far forest at treeline is SPARSE (woodland, T6) + heavily haze-obscured; **no clear square-tile defect at 700-1800 m**. The tiling is a close/mid-range phenomenon (imposter large on screen), which the hold removes. | `input/v4_far_forest.json`, `derived/v4_treeline/` |
| **V5a** cost table | forest_floor post-hold **11.023 ms << 12.5 ms** (R5-1), margin **1.48 ms**. **T4 rungs NOT back on the list.** ~1.48 ms density headroom at forest_floor (but the HLOD share, item 8, gates a global density multiplier). | `input/v5a_cost_table.json` |
| **V5b** gc.auto | `git config --unset gc.auto` -- done (was already unset from the prior turn). | — |

## Levers row filled
`RHI/PrimitivesDrawn` REJECTED as a foliage control: GPU-driven instanced foliage
is drawn via the indirect path (`InstanceCullingContext` / GPUScene indirect
draw), so the CPU-side primitive counter excludes it. Per-pass GPU ms is the
control used in V2. (Header:line for the indirect path not opened this session —
flagged; the empirical proof is V2's per-pass split.)

## Acceptance
V0 in plain sentences ✓; t3_perf.json with 3 runs/station ✓; V1 band-masked ✓;
four new stills (v1 asis/armA/armB + v4 treeline) ✓; imposter_defect.json names a
favoured hypothesis ✓; REGISTER SUPERSEDED lines ✓; tree clean, no push, editor
closed clean ✓.
