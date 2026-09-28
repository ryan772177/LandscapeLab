---
name: scatter-placement
description: Placing foliage, rocks or clutter as instances — the orphan-sweep trap that deletes everything not in the current run, pivot correction, plan adoption, grounding verification, and the density philosophy. Use when running place_foliage, rock_scatter, or adding any scatter species.
when_to_use: placing foliage or rocks; adding a species to a recipe; running place_foliage --place; verifying grounding; tuning scatter density
allowed-tools: Read, Grep, Glob
---

# Scatter placement

Sources: `RECIPES.md` R4, R5, R12, `scripts/place_foliage.py`,
`scripts/rock_scatter.py`, `scripts/verify_grounding.py`.

## READ THIS BEFORE PLACING ANYTHING

**`place_foliage.py`'s payload runs an ORPHAN SWEEP** over
`/Game/Foliage` (`place_foliage.py:449-472`): every `FT_*` asset whose
name is not in the plan list handed to THAT run gets
`remove_all_instances`.

**Placing rocks in a separate run from vegetation deletes all 157,554
conifers, silently, and the run reports success.**

Rocks and vegetation are planned and placed in **ONE run**. Rock plans
are written by `rock_scatter.py --write` and re-adopted by
`adopt_rock_plans`, which REFUSES rather than warning — every way it can
go wrong ends with instances destroyed:

- plan file missing → the rock is swept on the next run
- plan file empty → ditto, and the sweep reads as intentional
- mesh or species disagrees → places a different asset than the recipe
  names, and the name-keyed sweep cannot tell

**A missing plan is NOT "no rocks this time". It is an unfinished
pipeline.**

## Pivots

Vegetation goes through Blender to a base-centre pivot and the ruling-(c)
gate enforces ≤1.0 m horizontal / ≤0.25 m vertical.

**Fab rocks are box-centred by the vendor and always will be** —
R-ASSET forbids authoring into a Fab folder, so they can never be
normalised. `base_offset_z_m ≈ −extent_z`.

So the plan **DECLARES** its correction (`pivot_base_offset_m`) and the
payload verifies the declaration against the live asset:

    declared -> require |declared - measured| <= 0.01 m
    absent   -> require |measured| <= 0.25 m   (unchanged)

**Strictly stronger than the limit it replaces**, because the old gate
could not see a plan computed against a STALE measurement. And it cannot
be satisfied by omission. **When a correct input cannot satisfy a gate,
make the input CARRY ITS PROOF** — do not loosen the gate or exempt the
input.

## Verify grounding over EVERY instance

`verify_grounding.py`, not a sample: a floater is rare by construction,
so sampling 200 of 157,554 returns a clean bill of health for a map with
hundreds.

It **shares the heightmap and world transform with the planner**, so a
shared-transform error is invisible to both — it measures plan-vs-surface
agreement, not absolute grounding. It says so in its own success message.

Expected offsets are declared, not assumed: `sink_depth_m` for
vegetation, `pivot_base_offset_m` and `embed_depth_per_scale_m` for
rocks. **A deliberate 0.12 m sink and a 0.12 m error look identical to a
check that assumes zero.**

## Cost model

**Read the LOD chain from the ASSET.** `LOD_PERCENT` models
`percent = screen_size²`, which is how R5's conifer chain was
GENERATED. Vendor chains do not follow it — measured against modelled,
per mesh, the error ranges from **20.3× understated to 0.4×
overstated**, so no single correction factor is valid.

`lod_depth` is a **COUNT**, not a deepest index. It was both once, and
`LOD_PERCENT[4]` on a 4-tuple killed a plan eight minutes in.

## Density philosophy (ruled)

**Sparse and clustered beats uniform.** Clutter gathers under trees,
along drainage, at cliff bases — the **deposition and flow fields are
legitimate placement priors**, not white noise. A talus field that
ignores what is above it reads as noise, and the difference is
measurable: the naive slope band is 1,460 ha of this map, 90.4% of it
with no cliff feeding it.

## Reporting

`mask ha` is the **PROBABILITY-WEIGHTED** area (Σ p × cell area), not the
count of cells with p > 0. For a soft mask those differ by ~20×, and
only the weighted figure divides into a density that means anything.
