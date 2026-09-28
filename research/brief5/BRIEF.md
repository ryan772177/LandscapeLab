# Brief 5 — the forest: what each tree is drawn as, and how many there are

**Desk, 2026-09-20.** Built on CC's `BASELINE.md` v3 (package sha256 `e03d6ab5…0de4`, verified on
receipt). v3 is accepted as the baseline. This brief derives two things from it and nothing else:
**(A)** the representation ladder — what a live tree is drawn as at each distance — and **(B)** the
density the forest needs to read as a forest. Everything here is either MEASURED by CC, DERIVED by a
tool in `scripts/` with a selftest, or labelled PREDICTED / ASSUMED. `REGISTER.md` has the ledger.

Judge camera throughout: 3840x2160, 90° hFOV (ruled 2026-09-05). Focal length 1920 px, so a tree of
height H at distance D is `1920·H/D` px tall, and `ScreenSize = 1.778·R/D` (CC, SceneManagement.cpp:966/980).

---

## A. The ladder

### A1. What v3 measured, restated as a share of the forest

v3 gave the switch distances. Put against the cull, they say something stronger:

| species | card LOD | engages | tree is | cull | **share of live instances drawn as the card** |
|---|---|---|---|---|---|
| ConiferPine | 32-tri billboard | 127.8 m | 332 px | 512 m | **93.8 %** |
| SpruceSub | 6-tri imposter | 87.5 m | 367 px | 512 m | **97.1 %** |
| SpruceSapling | none (326-tri LOD3) | — | — | 238 m | 0 % |
| Conifer | none (Nanite) | — | — | 512 m | 0 % |

Share = area of the in-cull disc beyond the engage distance, `1 − (D_card/D_cull)²`, uniform density
(`lod_ladder.py`, `card_defect.fraction_of_live_range_shown_as_card`). Two of the four species —
87,167 of 185,385 trees — are geometry for the nearest 3–6 % of their live range and a card for the rest.

At the forest_floor station the non-Nanite trees currently put **~0.51 M triangles** on screen
(tool estimate). That is why the forest costs 0.185 ms: it is mostly cards.

### A2. Is that a visible defect? Not yet measured.

v3 quantified the geometry. Nobody has looked at the picture. The desk PREDICTS the 88–128 m switch is
visible (a static crossed-plane billboard has no parallax and wrong lighting at 332 px), but a
well-baked octahedral imposter can hold up at a few hundred px, and the atlas frame sizes have not been
read back. So the first task is to **see it**: same station, same frame, `foliage.ForceLOD` holding
geometry, against as-is. If the band between 128 m and 512 m does not differ, the desk's claim is
withdrawn and Part A stops there. Falsifiable by design.

### A3. Two gates a card must pass to be shown live

A representation may engage only where the judge camera cannot tell. Operationally:

1. **Texel gate.** A card is magnified wherever the tree is taller on screen than one atlas frame.
   Allowed only beyond `D = 1920·H / frame_px`. (Same rule as Brief 3's texel budget, applied to an atlas.)
   Needs `frame_px` per card — Task 2 reads it back; the tool takes `--frame-px`.
2. **Silhouette gate.** Brief 1's `lod_silhouette_check`, card vs the last geometric LOD, at the engage
   distance. Plus canopy coverage ratio 0.90–1.10 (cards that thin or fatten the crown fail).

The 40 px detail floor is not a third gate: it is where *geometry* stops mattering. v3 showed every
tree is still above it at the cull (pine 83 px, SpruceSub 63 px, Conifer 110 px at 512 m; the floor
sits at 1061 / 803 / 1407 m). So between 512 m and ~1 km the HLOD card is doing detail-band work, and
that is acceptable exactly when the card passes gates 1–2 there. Which it will far more easily at 83 px
than at 332 px.

### A4. The card's other job, and why this fix is cheap

World Partition **Instancing** HLOD layers replace each mesh with an ISM at its **lowest LOD**, regardless
of screen size (UE 5.8 HLOD doc; CC read back `layer_type = INSTANCING`). So the card has two jobs: live
LOD, and HLOD representation beyond 512 m. The second job does not depend on the card's screen size at
all. Therefore:

> **Set the card's screen size so it engages at 1.10 × cull_max. It is never drawn live; HLOD still uses it.**

No new asset, no HLOD content change, one array per mesh. The ladder then needs something between the
last geometric LOD and the cull.

### A5. The missing rungs — derived from the asset author's own density

The asset authors already told us the triangle density they accept: they engaged LOD G (the last
geometric LOD) at D_G. Hold that on-screen density constant:

    required_tris(D) = tris_G · (D_G / D)²

Check: ConiferPine LOD1→LOD2 by this rule lands at 88.4 m; the author put it at 90.4 m. They used the
same rule. And by it a 32-triangle representation belongs at **~1.19 km** — not 128 m — which agrees
with the independent 40 px floor (1.06 km). Two rules, one answer.

Rungs at ×2 distance (×¼ triangles), stopping before the cull or below 100 tris (`lod_ladder.py`):

| species | G | new rung 1 | new rung 2 | card |
|---|---|---|---|---|
| ConiferPine | LOD2 5777 @ 90 m | **1444 tris @ 181 m** (ss 0.1189) | **361 tris @ 362 m** (ss 0.0595) | ss 0.0382 → 563 m |
| SpruceSub | LOD3 2587 @ 42.5 m | **647 tris @ 85 m** (ss 0.1750) | **162 tris @ 170 m** (ss 0.0875) | ss 0.0264 → 563 m |

Full arrays in `derived/derived_ladder.json` → `proposed.screen_sizes`.

Two ways to get there, in order:

- **Hold** (`fallback_hold`): no new geometry; LOD G held to the cull. Visually the safe upper bound.
  Station load **~4.6 M tris** (9×).
- **Proposed**: insert the rungs. Station load **~1.14 M tris** (2.2×). Needs mesh reduction of card
  foliage, which often thins crowns — so every rung is gated (A3.2) and a failed rung is dropped, not shipped.

Cost is PREDICTED small (foliage raster is 0.13 ms of an 11.05 ms frame today) and is to be MEASURED
against the v3 noise floor (0.016 ms at forest_floor), not argued.

### A6. Nanite is not the shortcut here

Epic's 5.8 guidance for foliage under Nanite is geometry rather than masked cards, with Preserve Area.
ScotsPineTall and spruce_half are masked-card trees. Brief 1 Task 9 ("evaluate, don't migrate") stands.
The Norway Spruce (PVE, Nanite) needs no ladder and gets none.

---

## B. Density

### B1. The forest is, by measurement, a woodland

v3: densest 256 m bin holds 711 trees = **108 stems/ha**; the best frustum in the world holds 1844 trees.
Closed montane spruce forest carries several hundred stems/ha. But stems/ha is the wrong unit for a
picture. The right one is **canopy cover** — the fraction of ground under a crown — because that is what
reads as "forest" from a ridge and what closes the sky from the floor. NVC physiognomic classes:
forest ≥ 0.60, woodland 0.25–0.60, sparse 0.10–0.25.

Desk PREDICTION for the densest bin (station species mix, crown radius 0.85 × mesh half-extent, scale 1):
mean crown 40 m², n·A = 0.44, **cover ≈ 0.36 — woodland**. If that is the densest bin, the world has no
forest in it. `canopy_cover.py` replaces the prediction with a measurement from the four plans
(rasterised crowns, no placement-model assumption), per bin, at three crown factors.

### B2. The multiplier

Independent crowns leave `u = exp(−nA)` uncovered; m× the trees leaves `u^m`. So from measured cover c
to target T:

    m = ln(1 − T) / ln(1 − c)

For c = 0.36, T = 0.70: **m ≈ 2.7** (an upper bound — min-spacing placement overlaps less). Proposed
lever: one global multiplier on the recipe's existing density field, set to `m_for.p90_bin`, so the
densest tenth becomes forest and the gradient to the treeline is untouched.

### B3. What that costs, and why it waits

Live layer: v3's 0.100 ms / 1000 visible trees (upper bound) × (2.7 − 1) × 1.844 ≈ **+0.31 ms** at the
worst station, before the ladder. Affordable. But the HLOD layer's instance count scales by m too, and
its GPU share is **INCONCLUSIVE** (BACKLOG item 8). So: **measure cover now (read-only); regenerate
nothing until item 8 lands and the target is ruled.**

---

## Rulings the desk is assuming (overrule any of them)

- **R5-1** forest_floor GPU budget **12.5 ms** p90 at 4K (75 % of 16.67). The station had none.
- **R5-2** canopy target **0.70** for the densest decile of bins; gradient preserved.
- **R5-3** vendor meshes (ScotsPineTall_01, spruce_half_01) edited **in place**, pristine `_SRC`
  duplicates kept beside them; reversible by git.

## Parked (registered, not tasked)

Lumen reflections are the largest foliage pass (+0.324 ms) — candidate: foliage roughness vs the Lumen
trace threshold. `world_position_offset_disable_distance = 0` on all four types — candidate: disable
where sway < 1 px. Meadow gap (grass culled at 45–50 m, nothing to 512 m) — PCG runtime grid is the
candidate, per PCG_NOTES §4. None of these is touched by this brief.
