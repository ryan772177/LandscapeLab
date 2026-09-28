# Brief 5 R2 — did the (now-persisted) hold take at runtime?

**Two instruments; they disagree, and one is provably contaminated in this scene.**

## Instrument A — RenderData readback (the desk's own C1 no-op oracle): HOLD TOOK, MEASURED

`get_lod_screen_sizes` returns `RenderData->ScreenSize` — the array the runtime LOD
selector reads (StaticMeshEditorSubsystem.cpp:1003-1008). Read in the R2 editor
process (`r2_renderdata.json`), on the meshes the placed HISM foliage reference:

| species | C1 (pre-persist) card ScreenSize | R2 (post-persist) | target | matches_t3_hold |
|---|---|---|---|---|
| ConiferPine LOD3 | 0.16821 | **0.03818** | 0.03818 | **True** (was False) |
| SpruceSub LOD4 | 0.17 | **0.02642** | 0.02642 | **True** (was False) |

This is the exact instrument the desk specified in C1 to distinguish "hold took"
from "no-op." In C1 it read `matches_t3_hold=false` for both (the no-op headline).
Post-R1 it reads **true** for both, in a fresh process. The runtime LOD input now
carries the held card ScreenSize. **The hold is live at runtime.**

## Instrument B — Mesh LOD Coloration classifier: INCONCLUSIVE, and CONTAMINATED here

`c1_lod_readback.py --prefix r2`, same mask/counting as C1 (cvars verified:
r.ForceLOD -1, foliage.ForceLOD -1, all LOD distance scales 1.0):

| station | species | geom% | card boxes | geom boxes | lod_hist |
|---|---|---|---|---|---|
| ring | ConiferPine | 22.6 | 137 | 40 | {4:137, 1:31, 2:9} |
| ring | SpruceSub | 25.1 | 131 | 44 | {1:30, 4:131, 2:14} |

Both < 90% geometric, so by R2's stated rule this instrument returns INCONCLUSIVE.
**But the instrument's premise is false in this scene, proven three ways:**

1. **ConiferPine has 4 LODs (0-3); LOD index 4 cannot exist for it.** Yet its boxes
   are classified overwhelmingly index-4 **yellow** (137 of 177 classified) with
   **zero** of its own card color (blue = LOD3). Yellow is produced ONLY by
   SpruceSub LOD4. So the ConiferPine "card" count is entirely cross-species
   contamination, not ConiferPine's card.
2. **The number does not move between no-op and hold.** C1 (hold was a no-op):
   ConiferPine geom 19.8%, hist {4:158,1:29,2:10}. R2 (hold live): 22.6%,
   {4:137,1:31,2:9}. An instrument that reads the same whether or not the thing
   changed is not measuring the thing (non-negotiable 13 shape).
3. **The contamination source is geometric.** Cull distance is **730 m** for both
   species; the card engages at ~563 m (ConiferPine LOD3 @ 0.03818, SpruceSub LOD4
   @ 0.02642). So cards ARE legitimately drawn in the **563-730 m ring** — and in a
   dense mixed forest those far cards project through the same 2D screen boxes as
   the 128-512 m band instances, dominating the saturated-pixel classification. The
   2D box projection cannot separate a near geometric tree from a far card behind
   it along the same ray.

The coloration classifier is the right instrument for an isolated tree; it is
defeated by depth-overlap in this dense forest with a 730 m cull. It cannot decide
R2 either way, and it read essentially the same in C1 (no-op) and R2 (hold).

## Verdict (CORRECTED per operator ruling 2026-09-21)

**R1f (cold RenderData readback) is the PERSIST gate, and it passed.** RenderData
proves the mesh asset carries the held card ScreenSize on disk and after a load
into a fresh process. It does NOT by itself prove the RUNTIME LOD SELECTOR (the
placed HISM proxies) uses it — that is a separate question the operator flagged
(a proxy/DDC-cached LOD boundary could ignore the new ScreenSize).

**R2 coloration is recorded as INCONCLUSIVE — INSTRUMENT CONTAMINATED, NOT a pass.**
Overlapping 2D boxes with no occlusion: ConiferPine boxes (4 LODs, no LOD4) were
classified overwhelmingly index-4 yellow with 0% of ConiferPine's own card even
pre-hold in C1, which is impossible — so the classifier is not measuring the
target species' in-band LOD.

**A sharper open question the cull number raises.** Applied cull = **512 m**
(`cull_cm 51200`, derived_cull_m 512, clamped to the streaming range — NOT the
recipe's authored 730 m). The held card engages ~540-670 m (D=1.778·R/ScreenSize),
past the 512 m cull, so a hold that TOOK AT RUNTIME would draw **zero** SpruceSub
LOD4 (yellow) anywhere. R2 still shows 131 in-band yellow (C1 166 -> R2 131,
barely moved), and yellow is SpruceSub-LOD4-exclusive. That is consistent with the
runtime still selecting the pre-hold ScreenSize (old LOD4 @0.17 engages ~104 m,
drawn 104-512 m) — i.e. **persisted on disk, runtime effect UNRESOLVED**.

**Resolution is deferred to two uncontaminated instruments (operator-ordered):**
1. `isolated_check` — one ConiferPine + one SpruceSub instance with no other tree
   in its screen box at 250-400 m; coloration reports the single box's LOD colour.
   Yellow/blue card => no runtime effect; green/red geometry => hold took.
2. R3 as a runtime control — a live hold MUST cost something (Basepass +
   ShadowDepths rise well above the 0.016 ms forest_floor noise floor; the blunt
   arm-B force was +2.9 ms). Within noise again => "persisted on disk, no runtime
   effect", stop (reopens the DDC/proxy question).
