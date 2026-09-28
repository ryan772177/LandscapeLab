# THREE CORRECTIONS BEFORE THE RECIPE, AND ONE TO MY OWN PREVIOUS DRAFT

Every number in the prompt checked out. Three claims in the *artefacts the prompt drew from* did not.

**0. RETRACTION of my own previous statement.** I wrote that solving the density arithmetically instead of measuring it would undershoot "~13%, about 29,000 instances". **That is backwards in direction and wrong in magnitude.** The uniform-elevation premise's retention (0.6394) is LOWER than the measured one (0.7222), so dividing by it produces a HIGHER density, not a lower one. Recomputed: solving through the uniform-elevation premise gives **152.1/ha → 247,599 instances, a reserve of 2,401 against the shared 250,000 ceiling**, where solving through the measured retention gives 134.7/ha → 218,934, reserve 31,066 — reproducing the shipped 135/ha to within 0.3/ha. The corrected figures are used below.

**1. `_verify/20260815_d4_rescatter_220k.md:25-26` — "and both carry imposter LODs" is FALSE for `SpruceSapling`, and it is contradicted by a measurement the same session took hours earlier.**

`Free/_measured/pn_spruce_forest.json`, `trees[18]` (`/Game/PN_interactiveSpruceForest/Meshes/small/spruce_small_05`, the placed sapling): `lod_count 4`, `lod_triangles [2604, 1301, 650, 326]`, `lod_screen_sizes [1.0, 0.6, 0.2, 0.1]`, `material_slots 3`, `lod_group "SmallProp"`. There is no 4–6 triangle card and no imposter material slot. `trees[6]` (`spruce_half_01`, the placed sub-canopy) does have one: `lod_count 5`, `lod_triangles [..., 2587, 6]`, `lod_screen_sizes [..., 0.35, 0.17]`, `material_slots 4`. `_verify/20260815_pn_spruce_forest_intake.md:45` records `spruce_small_05` as 4 LODs / 3 slots, and `:18-20` explicitly corrects "21 imposters" to **7**. The sapling tier's cheapness is real, but it comes from a 2,604-triangle LOD0 and `cull_distance_m: 180.0` (`recipes/alpine_8k.json`, `SpruceSapling`) against 730 m for the canopy — not from an imposter. Crediting +0.18 ms to a mechanism one of the two tiers does not have is the wrong lever recorded as the right one.

**2. "closure alone takes the plan to 111,079" (`:55-57`, and `LESSONS.md:16262-16268` "from a uniform 153,796 to 111,079") is not a single-variable delta. The control was never produced.**

153,796 = 92,519 + 61,277, read from `git show a61547a5:foliage/alpine_8k_Conifer.json` / `_ConiferPine.json`. That plan came from a **two-species** recipe, `weight_share` 0.6 / 0.4 (`git show a61547a5:recipes/alpine_8k.json`). 111,079 belongs to the **four-species** recipe — 0.32 / 0.23 / 0.25 / 0.20, with `SpruceSapling`'s slope band widened to `[0.0, 28.0]` against 24.0 for the rest. `git ls-tree --name-only 04c7d283 foliage/` lists only `alpine_8k_Conifer.json` and `alpine_8k_ConiferPine.json`: **no closure-off four-species plan was ever written**, so nothing in the repo isolates the ramp. 111,079 and 219,659 are correct as recorded; "closure alone" is not.

**3. `closure` is absent from `recipes/schema.md` — `grep -c closure recipes/schema.md` → 0.** So is `sink_depth_m` → 0. `place_foliage.py:235` and `import_heightmap.py:864` both cite "schema v1.23"; `recipes/schema.md:1` still reads "v1 (revision 1.5)" and its newest documented revision is v1.16 at `:728`. The validator itself is complete and fails closed (`import_heightmap.py:878-900`), so this is a documentation gap, not a hole in the gate — but CLAUDE.md calls `schema.md` "its normative contract, referenced by twelve files", and the contract of record for two foliage keys is currently a code comment.

Verified correct from the artefacts: falloffs 0.15 / 0.20 / 0.30 / 0.55 (`recipes/alpine_8k.json`); 68/ha → 111,079 and 135/ha → 219,659; acceptance 22.4% / 30.0%. The four plan files sum to exactly 219,659, and I re-derived every acceptance rate independently from the recipe's shares and the placer's own grid rule (`place_foliage.py:218-219`): 22.44 / 23.13 / 24.69 / 29.99%.

---

# R-CLOSURE — THE CANOPY CLOSURE GRADIENT (2026-08-15)

**Ruled by the fable model under delegation (D4):** density rises to ~220,000 as a **closure GRADIENT, never uniform 70%**. The defect being fixed is as much UNIFORMITY as count.

**Status: EXECUTED AND MEASURED (PROVISIONAL, UNPROVEN).** 219,659 placed, counted and saved on `/Game/Alpine8K`; grounding closed by two representations. Never replayed cold.

### PRECONDITIONS

- Engine 5.8, `/Game/Alpine8K` open, `Landscape_Alpine8K` present.
- `recipes/alpine_8k.json` valid against `import_heightmap.py`'s validator, which is where the `closure` contract is actually enforced (`:878-900`) — **not** `recipes/schema.md`, which does not mention the key.
- Every species carrying `closure` is an INSTANCE species. A `system: "grass"` species with `closure` is refused (`import_heightmap.py:880-883`): grass density is governed by the landscape material's weight mask, not by this planner.
- `foliage.canopy` and `foliage.rock_scatter` present — unrelated to closure, but `rock_scatter.py` exits 2 without the latter and the material bake reads it.
- The shared instance ceiling is `MAX_INSTANCES = 250000` at `rock_scatter.py:108`, **imported** by `place_foliage.py:93` rather than retyped. Vegetation and rock compete for one budget.

### EXACT VALUES

`foliage.density_per_hectare` = **135.0** (was 68.0). Valid range: whatever keeps the planned total under 250,000. **This value is a FUNCTION of the ramps below and is not independently meaningful** — see "the density is re-derived".

`foliage.species[].closure`, both keys REQUIRED when the block is present, both finite in `[0, 1]`:

    species         at_low   at_high    tier                     measured height
    Conifer          1.00      0.15     canopy, PVE Norway Spruce      29.313 m
    ConiferPine      1.00      0.20     canopy, Scots Pine Tall        22.110 m
    SpruceSub        1.00      0.30     sub-canopy, spruce_half_01     16.725 m
    SpruceSapling    1.00      0.55     regeneration, spruce_small_05   4.529 m

Heights from `Free/_measured/pve_spruce.json` `trees[0]`; `Free/_measured/palette_live.json` `rows[19]` (`dims_m [9.73, 9.83, 22.11]`); `Free/_measured/pn_spruce_forest.json` `trees[6]` and `trees[18]`. **`at_high` is monotone in measured height across all four tiers** — that is a checkable property of the values, not a stylistic one, and it is what "big crowns go first" means arithmetically.

`at_low` applies at the species' own `height_m[0]`, `at_high` at `height_m[1]`, linear between, **clamped outside** (`placement_priors.py:187-188`). All four species here share the band `[120.0, 640.0] m`; the ramp anchors to the SPECIES band, not to a global one, so two species with different bands get differently-scaled ramps from the same numbers.

`at_high > at_low` is legal and describes a stand that thickens with elevation. `placement_priors.py:178-181` permits it deliberately and does not special-case it — it is wrong for spruce and right for nothing this project plants, so it is left expressible rather than gated.

### WHY IT SCALES WHERE `centred_bias` REDISTRIBUTES, AND THE DISTINCTION IS PHYSICAL

The two functions now sit ten lines apart in one module and look interchangeable. They are not.

`centred_bias` (`placement_priors.py:135-153`) is `clip(1 + bias*(v - ref)*2, 0, 2)` — mean-preserving by construction. Wet ground gains exactly what dry ground loses. That is correct for flow, because **flow says WHERE trees prefer to stand, not HOW MANY there are**: the same trees relocate.

Closure is the opposite KIND of fact. A subalpine stand genuinely thins toward treeline — fewer trees, not the same trees moved uphill — and ends in open krummholz. So `closure_ramp` (`:154-188`) returns a bare multiplier in `[0, 1]` and the caller's count falls with it. **Anything preserving the mean here would describe a forest that does not exist**: it would move trees downhill and leave the treeline exactly as hard-edged as the band that created it.

The test for which one a new prior wants is not "is it a multiplier" but **"if this fact is true, are there fewer things in the world, or the same things somewhere else?"**

**Why it lives in `placement_priors.py` and not in `place_foliage.py`.** Canopy closure against elevation is a physical property of the biome, sibling to `rock_scatter.talus_deposit()` and the flow prior — non-negotiable 19. A rock or clutter pass that wants "denser below treeline" must read THIS. A second ramp in a second tool is free to disagree, and neither tool's verification could detect the disagreement.

### WHY ONE SHARED RAMP IS WRONG

The instinct is a single closure ramp applied to every species. That thins all four tiers together and yields a **scale model of the uniform forest** — the same composition everywhere, just less of it. It fixes the count and not the defect.

Real stands change COMPOSITION with elevation: the big crowns drop out first and the last thing standing is stunted regeneration. Hence the per-tier spread 0.15 → 0.55, a 3.7x difference between canopy and saplings at the top of the band, so the treeline ends **sapling-dominated rather than empty**.

The acceptance rates are the evidence that it landed, from one shared mask and four different ramps: **22.4% canopy against 30.0% saplings** (`_verify/20260815_d4_rescatter_220k.md:18-21`).

### THE DENSITY IS RE-DERIVED AGAINST THE RAMP, NEVER CARRIED OVER

A multiplier that SCALES cannot leave `density_per_hectare` alone. Measured, one dry run:

    68/ha  (unchanged)  -> 111,079    against a ruled ~220,000
    135/ha              -> 219,659    reserve 30,341 under the 250,000 ceiling

**And it must be MEASURED, not computed — the arithmetic route overshoots into the ceiling.** Two retention figures, and the gap between them is the point:

    share-weighted mean of the four ramps, under the
      PREMISE that candidates are uniform in elevation      0.6394
    measured retention (24.78% acceptance with closure
      against 34.31% without)                               0.7222
    ratio                                                   1.1295

**The uniform-elevation premise is false**, and its error is 12.95% in the wrong direction. Solving the density for ~220,000 through each:

    through 0.7222 (measured)         134.7/ha -> 218,934   reserve 31,066
    through 0.6394 (uniform premise)  152.1/ha -> 247,599   reserve  2,401

The measured route reproduces the shipped 135.0/ha to within 0.3/ha. The computed route lands **2,401 instances short of the shared 250,000 ceiling** — and rocks draw on the same budget, so it consumes the entire reserve the ruling asked for.

Two mechanisms the arithmetic cannot see: candidate elevations are not uniform within the band, and `place_foliage.py:260` clips `p` to `[0, 1]` before the Bernoulli draw, so wherever layer weight × flow bias already saturated, the ramp must pull the product below 1 before it removes anything at all.

*Stated rather than buried: the 0.7222 is measured against the two-species pre-D4 plan — see correction 2 at the head of this document. It is sound as the reason to measure rather than compute; it is not a transferable coefficient.*

The planner prints per-species counts before it writes anything, so the derivation costs one dry run.

### ORDERED STEPS

1. **RISKY-OP tag first**, named for the operation: `pre-d4-rescatter-220k-20260815`. This re-rolls every instance in the world.
2. Add `closure` to each instance species in the recipe. **Both keys, every species you want ramped** — a half-declared gradient is refused, not defaulted.
3. **Append any new species to the END of `foliage.species`.** `place_foliage.py:207` keys the RNG as `seed + 7919 * (i + 1)` where `i` enumerates the WHOLE list including grass and rock species. An insertion re-rolls every species after it. Blueberry was appended last in D3, which is the only reason D3 did not disturb the trees.
4. `place_foliage.py --recipe recipes/alpine_8k.json` **dry run**. Read the printed counts.
5. Set `density_per_hectare` from step 4's counts. Re-run the dry run and confirm the total lands under the ceiling with the intended reserve.
6. `place_foliage.py --place`, handing it **every** vegetation plan in the same run — the orphan sweep deletes every `FT_*` the run is not given.
7. `save_level.py --recipe recipes/alpine_8k.json`. **The `--recipe` is not optional**; see REJECTED.
8. Grounding: `verify_grounding` (all instances) **and** `trace_grounding` (engine collision, n ≥ 500 per species). Every position moved, so every species needs tracing — including ones traced before.
9. Frame cost at the ruled station against the ruled abort bar.

### VERIFICATION

**Count, by an instrument that cannot see the recipe.** The placer's own in-world verification returns 219,659 against a planned 219,659 (`_verify/20260815_d4_rescatter_220k.md:11-12`), 1,095 packages saved and re-read clean, 0 removed.

**Composition, by arithmetic independent of the placer.** Acceptance = placed / candidates, where candidates are re-derived from `density_per_hectare × weight_share` through `cell_m = sqrt(10000/target)` and `cells = floor(span_m / cell_m)` (`place_foliage.py:218-219`) with `span_m = 8128.0`. Independently reproduces 22.44 / 23.13 / 24.69 / 29.99% against the recorded 22.4 / 23.1 / 24.7 / 30.0. **The gradient is verified by the SPREAD between tiers, not by the total** — a total can be hit by any number of wrong compositions.

**Grounding, two representations, no shared source** (`:61-85`). Heightmap, every instance, tolerance ±0.050 m: max 0.001 m, 0 outside, all four species — quoted with the tool's own disclaimer that it is COVERAGE, not independence. Engine collision, 500 per species: 500/500 hits, p50 +0.005 to +0.006 m, 0 floating, 0 buried. They agree at p50.

**Frame cost.** GPU **7.92 ms** at `forest_floor` against an **11 ms** abort bar; D3's baseline was **7.74 ms** (`_verify/20260815_d3_blueberry_understory.md:20`). +65,863 instances (+42.8%) for **+0.18 ms**.

**Frames:** `_verify/20260815_alpine8k_d4_forest_floor.png` (mean 0.5195, 0.088% blown), `_verify/20260815_alpine8k_d4_ridge_wide.png` (mean 0.7553, 0.047% blown).

**NOT ESTABLISHED, and it stays that way until someone measures it:** no frame A/B against the pre-D4 state at a matched resolution, so no pixel-difference claim is made; and aerial readability is NOT adjudicated by `ridge_wide`, because untuned aerial perspective swamps the forest at that range — a pre-existing recorded issue, not a D4 regression.

---

## R-CLOSURE REJECTED

**Raising `density_per_hectare` alone to fix "the forest reads as scrub".**
SYMPTOM: the same flat forest, thicker. Every elevation inside `[120, 640] m` stays equally likely, the stand runs at uniform density to the top edge and stops dead, and no count addresses that. CORRECT: the band is a HARD WINDOW; make it a gradient first, then set the density against the gradient.

**Expressing closure through `centred_bias`.**
SYMPTOM: the placed count does not fall. The bias is mean-preserving (`placement_priors.py:152`), so trees are redistributed downhill and the treeline is exactly as hard-edged as before — a change that measures as "applied" and renders as nothing. CORRECT: `closure_ramp`. The two functions are adjacent and look interchangeable; the distinction is argued in the docstring at `:156-166` for exactly that reason.

**One shared ramp for all four tiers.**
SYMPTOM: composition is constant with elevation — a scale model of the uniform forest. The top of the band empties instead of turning to krummholz, and the compositional half of the ruling is silently dropped while the count half passes. CORRECT: per-tier `at_high`, monotone in measured height: 0.15 / 0.20 / 0.30 / 0.55.

**Carrying `density_per_hectare` across the ramp unchanged.**
SYMPTOM: 111,079 instances against a ruled ~220,000 — a 49% shortfall that **nothing refuses**, because the ceiling gate at `place_foliage.py:520` only fires when a plan is too LARGE. A plan that is quietly half the intended size exits 0 and reports success. CORRECT: re-derive the density against the ramp before placing.

**Solving the new density arithmetically through the mean ramp instead of measuring it.**
SYMPTOM: **152.1/ha, placing 247,599 against a 250,000 shared ceiling — a 2,401-instance reserve where the ruling asked for ~30,000**, and rocks draw on the same budget. The premise that candidates are uniformly distributed in elevation is false, and it understates retention by 12.95% (0.6394 against a measured 0.7222), so dividing by it inflates the density. The second invisible mechanism is `place_foliage.py:260`, which clips `p` to `[0, 1]` before the draw: where layer weight × flow already saturated, the ramp removes nothing until it has pulled the product below 1. CORRECT: one dry run — the planner prints counts before it places anything. *(This entry corrects an earlier draft of this recipe, which stated the error as an UNDERSHOOT of ~13%. It is an overshoot, and the magnitude at the ceiling is what makes it dangerous.)*

**Declaring `closure` on a `system: "grass"` species.**
SYMPTOM: refused at `import_heightmap.py:880-883` — *"closure applies to instanced species; grass density is governed by the landscape material's weight mask, not by this planner."* The refusal is right: `place_foliage.plan()` skips grass species at `:190-191` and never reaches the ramp, so the key would have been an INERT FIELD that reads like a setting (non-negotiable 21).

**Declaring `at_low` without `at_high` (or a value outside `[0, 1]`).**
SYMPTOM: refused at `:893-896` and `:898-900`. Defaulting either would make an incomplete block MEAN something; a value above 1 would be a second density knob wearing a gradient's name, and the placed count would stop being predictable from the recipe.

**Inserting a new species anywhere but the end of `foliage.species`.**
SYMPTOM: every species after the insertion point gets a different seed and its whole plan is re-rolled with every row different, because `place_foliage.py:207` keys the RNG on the enumerate index over the full list — grass and rock species included. Placed and saved instances move. Same hazard already recorded for `rock_scatter.py`, which is what makes it a class rather than an accident. CORRECT: append. Keying by species NAME would fix it structurally and must be done before more is placed, never after.

**Running `save_level.py` without `--recipe` after a re-scatter.**
SYMPTOM: exit 7 — *"recipe targets '/Game/Alpine' but the editor has '/Game/Alpine8K' open"*. It defaults to `recipes/alpine.json`, and it carries a package ALLOW-LIST derived from the recipe, so it would have saved 219,659 instances under a list scoped to a different world. The gate that looks like bureaucracy on every green run is the one that matters on the red one.

**Crediting the frame-cost win to imposter LODs on both new tiers.**
SYMPTOM: the recorded explanation cites a mechanism `SpruceSapling` does not have. `Free/_measured/pn_spruce_forest.json` `trees[18]` (`spruce_small_05`): `lod_count 4`, chain `[2604, 1301, 650, 326]`, `material_slots 3`, `lod_group "SmallProp"` — no 4–6 triangle card, no imposter slot. Only `trees[6]` (`spruce_half_01`) carries one, at LOD4 = 6 triangles, screen size 0.17, in a fourth material slot. CORRECT: the sapling tier is cheap because of a 2,604-triangle LOD0 and `cull_distance_m: 180.0` against the canopy's 730.0. **This is a derived record contradicting a measurement the same session took earlier** — `_verify/20260815_pn_spruce_forest_intake.md:45` has the LOD chain right, and `:18-20` explicitly corrects the imposter count to 7. Non-negotiable 15: a derived record verifies against the artefact at the moment it is written.

**Assigning any 4-LOD `lod_group` to a mesh that carries an imposter.**
Not committed, recorded because the temptation is standing: `spruce_half_01` ships `lod_group "None"` with a 5-entry chain, and its LOD4 IS the imposter. Setting a 4-LOD group deletes it. `spruce_small_05` is already `SmallProp` with 4 LODs, which is consistent — it never had one. `ScotsPineTall_01` carries its own billboard tier at LOD3 = 32 triangles across 5 material slots (`palette_live.json` `rows[19]`), so the same hazard applies to it.