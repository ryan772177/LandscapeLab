# Benchmark #2 — concept_coast through the v0 brief extractor

**Date:** 2026-08-31. **Input:** `Free/gemini_v1/concept_coast.jpg`.
**Question:** does the spike's image→brief→terrain→city flow generalize to a
second concept, and what breaks?

## What ran

Same chain as the spike: `analyse_concept` → hand-authored `layout_brief.json`
(7 entities) → base gen (seed 20260831) → 7 stamp placements → adopt (hash
`90f01ae8…`) → aux maps → `find_city_site` → `plan_city` (**84 buildings,
289 street segments, 0 pruned — fully connected**) → preview.

## What the benchmark caught (this is its job)

1. **Placement ORDER is semantics.** The coastal-cliffs ADD stamp buried the
   cove and ocean MIN carves (cove measured at 33° mean slope). The image's
   truth is carves-cut-cliffs, so carves must run LAST. Two blind parameter
   iterations failed before a direct measurement found this; the fix was
   reordering, then one measured amplitude iteration (60→20 m of carve
   relief) put the cove at 3.4° mean slope and the site finder ranked it #1 —
   at (-142, 354) m, 28 m elevation: where the image puts the town.
   **Tool consequence:** the brief schema needs an explicit carve/add
   ordering rule, not an implicit list order.
2. **Coasts break the lighting instrument's premise.** `analyse_concept`'s
   open-ground band caught the GLOWING SEA (R-B −0.201, teal) as "sunlit
   ground". The extractor needs a water mask before the light split.
3. **Sea level is a real feature, not a nice-to-have.** The west third is low
   (~96 m) but reads as land in every preview. A coast concept needs a water
   plane and a shore-carve primitive.
4. **The preview's river extraction doesn't transfer.** A fixed 99th-percentile
   flow threshold painted speckles here; channel extraction must adapt to the
   drainage distribution.

## Verdict

The flow generalizes: second concept, zero code changes, working city on the
intended site after 4 terrain iterations (2 blind, then measure-first). The
iteration loop is where the tool's automation effort should go — every fix
this session came from measuring the surface, which a loop can do without a
human.

## Files

`layout_brief.json`, `coast_bench.json` (recipe), `city_recipe.json`,
`city_sites.json`, `city_plan.json`, `preview_full.png`, `preview_city.png`,
`terrain/coast_bench*.png` + aux.
