# Brief 7 Phase 2 — rocks (R-ROCKS-BACK) HANDOFF (branch look-p2-rocks)

**Handed off deliberately** (CLAUDE.md context-exhaustion liveness rule). This turn already
carried the P1 feather world run to a PASS + `look-p1` tag and the full P2 step-0/0b dark-forest
diagnosis. Re-enabling the August rock set is a fresh, load-bearing authoring unit (8 species of
world-wide scatter), and only ONE of the 8 is fully ratified in RECIPES — the rest need their
densities sourced. Authoring that on an already-long context is the project's named failure mode.
Branch `look-p2-rocks` is created; the groundwork and all decisions are below. Author, PR, stop
before the world run.

## The task (BRIEF7_THE_LOOK.md:153-170, R-ROCKS-BACK)

Re-enable the August rock species on the deposition field at their last ratified densities:
**Boulder, CliffOutcrop, CliffOutcropB, CliffFace, TalusField A/B/C, TalusChannel, TreeStump.**
Water + settlement exclusions; pivot gate (base-centred) on every mesh; Nanite on all rock meshes
verified by Nanite DATA (triangle counts), not the flag. Stills: vista + a cliff station + talus
at 30 m, Look profile. Acceptance: cliffs read as rock at the vista; talus sits on the deposition
field, not a slope band. Commit, tag look-p2. VRAM peak logged.

## The schema — RESOLVED (RECIPES.md R12, ~§3785-3965)

Rock species are NOT a separate recipe section. They are **`foliage.species[]` entries** that
declare `role` (the discriminator); rock and vegetation key sets are disjoint, enforced by
`_validate_rock_species` in `scripts/import_heightmap.py`.

- `role` ∈ {cliff | talus | hero}
- `mask.kind` ∈ {slope | talus | layer}; `mask.layer` must NAME a material layer in this recipe;
  `mask.saturation` REQUIRED when kind==talus
- `density_per_hectare_on_mask` (0,500] — ON-MASK, not map-average (does NOT draw from
  `foliage.density_per_hectare`, which is the tree budget)
- `embed_frac` [0,0.5]; `tumble_deg` [0,90]; `align_to_normal` [0,1] (rocks EMBED — inverts the
  tree world-up rule); `scale_range` 0<min<=max; `cull_distance_m` (0,5000];
  `lod_depth` [1,len(rock_scatter.LOD_PERCENT)] AND == the MEASURED lod_count

**Shared physical facts** go in `foliage.rock_scatter` (read by BOTH the scatter and the material
scree mask — non-negotiable 19; neither keeps a copy). Exact ratified values (RECIPES 3811-3817):

    repose_deg              35.0
    cliff_source_slope_deg  45.0
    source_smooth_m         16.0     (NOT cosmetic — see 3819-3825; cell-scale slope manufactures
                                      phantom cliffs, ~40% of cell-scale cliff area is texture)
    runout_m               120.0
    mfd_exponent             1.3
    max_steps              600        (hitting it is a REFUSAL)
    saturation               0.03     (deposit->prob, p = 1 - exp(-d/s))

The one fully-ratified species entry, verbatim (RECIPES 3833-3839) — use as the shape template:

    {"name":"Boulder","role":"hero",
     "mesh":"/Game/KiteDemo/Environments/Rocks/Medium_Boulder_001/Medium_Boulder_001",
     "mask":{"kind":"layer","layer":"Grass","slope_deg":[0.0,22.0],"exclude_talus_above":0.2},
     "height_m":[120.0,700.0], "density_per_hectare_on_mask":0.35,
     "scale_range":[0.75,1.7], "align_to_normal":0.85, "tumble_deg":12.0,
     "embed_frac":0.18, "cull_distance_m":140.0, "lod_depth":4}

## OPEN ITEMS — must be sourced before authoring (do NOT invent)

1. **The other 7 species' ratified entries.** RECIPES 3785 says "The rest are specified and
   unplaced — see WHAT IS NOT HERE." So Boulder is the only fully-shipped entry in RECIPES R12.
   Source CliffOutcrop/B, CliffFace, TalusField A/B/C, TalusChannel, TreeStump from: the rest of
   R12 (read the full §3785-3965 + its "WHAT IS NOT HERE"), `plans/RECIPES_draft_*.md` (PN trees /
   understory drafts), and git history of `recipes/alpine.json` around the 8K re-terrain (when the
   rock species were removed — `git log -p --all -- recipes/alpine.json | grep -A30 rock_scatter`).
   Every density/mask is a MEASUREMENT or a ratified ruling — cite it, don't reconstruct.
2. **Mesh paths for the 8K project.** Boulder points at `/Game/KiteDemo/...`. Verify each rock
   mesh asset exists in THIS project (the KiteDemo pack) before referencing it; the cliff/talus
   meshes may be under different packs. `Free/_measured/rock_pivots.json` lists the measured 13.
3. **Pivots are BOX-CENTRED, not based** (RECIPES 3860-3863): `base_offset_z_m ≈ -extent_z`.
   Placing at terrain Z sinks every rock to its waist. `embed_frac` + the base offset from
   `rock_pivots.json` handle grounding — the pivot gate must apply the measured base offset.
4. **Nanite.** RECIPES 3865 measured Nanite=FALSE on all 13 rock meshes. The brief wants Nanite ON
   verified by DATA. So Phase 2 must ENABLE Nanite on the rock meshes and re-verify by built
   triangle data (not the flag) — reconcile with the Aug-9 lesson (Nanite replaces LOD0 with a
   reduced fallback; confirm r.Nanite on in the Look profile). lod_depth must == measured lod_count.
5. **Deposition-field mask.** `rock_scatter.py` (v1.12, OFFLINE) computes the talus deposition
   field from the heightmap + baked weightmap. Talus species use `mask.kind=="talus"` +
   `saturation`. Confirm the baked weightmap in use is the feathered one (post-look-p1).

## Constraints (world-run, DEFERRED — the desk said stop before the world run)

- **ORPHAN SWEEP (rock_scatter.py header + RECIPES R12):** `place_foliage.py --place` removes every
  `FT_*` not in the plan list handed to THAT run. Rocks and vegetation MUST be planned + placed in
  ONE run, or the world's ~217,102 vegetation instances get deleted. The offline `rock_scatter.py`
  plan-write is safe; only the `--place` world run has this hazard.
- RNG-by-index hazard (LESSONS 08-08): placements are NEW, so no re-roll issue.
- Water + settlement exclusions applied (mask-level).

## Pipeline for the author

1. Source the 7 open species entries (item 1) — faithfully, with citations.
2. Add `foliage.rock_scatter` (the 7 shared facts) + the 8 `foliage.species[]` rock entries to
   `recipes/alpine_8k.json`. Schema bump if needed; `_validate_rock_species` must pass.
3. Verify rock mesh paths exist (item 2); run `scripts/measure_rock_meshes.py` for any not in
   `rock_pivots.json`; enable Nanite + re-measure (item 4).
4. `rock_scatter.py` offline plan-write → check the triangle budget + deposition-field mask.
   NO `place_foliage.py --place` (world run) — PR and stop for "merged, go".
5. Post-merge (a later session): ONE place_foliage run with rocks + vegetation together, stills
   (vista + cliff + talus@30m, Look profile), acceptance, tag look-p2.

## State at handoff

Branch `look-p2-rocks` off main @ 09260b57 (P1 feather PASSED + look-p1 tagged; A2 dark forest
diagnosed = foliage imposter LOD). Recipe `alpine_8k.json` has NO rocks yet (removed at 8K
re-terrain). `rock_scatter.py` v1.12 is the offline planner and is unchanged. m=1, world working.


## RESULT — 2026-09-26 (authored, plans written, NOT placed)

Every open item above is closed or ruled-on-record; one NEW item is open for the desk.

| item | outcome |
|---|---|
| 1. the 7 species | VERBATIM from `recipes/alpine.json` HEAD (authored at e5f32271; removed by the "minus the rocks" ruling, R-ALPINE8K). TreeStump is `clutter` (R12 §6b/6d), not hero. |
| 2. mesh paths | all 9 `.uasset` files exist under `LandscapeLab/Content/KiteDemo/...`; all 9 measured in `rock_pivots.json` |
| 3. pivots | box-centred offsets applied by the planner (`pivot_base_offset_m` declared per plan); ruling (c) OK ×9 |
| 4. Nanite | already TRUE on all 8 declared (the 08-09 replay had taken; the 08-03 registry was stale). Data verified: vendor LOD0 counts as Nanite tris; fallback LOD0 reduced; lod_count unchanged |
| 5. deposition field | RULED + FIXED 2026-09-26/27: router on the 16 m landform, saturation derived from the field (0.4615; talus masks at ratio). Run 2: apron 305.4 ha, talus 2,486, 13,883 rocks — bound met (apron ≥ 250, talus ≤ 3×). R12 AMENDED 2026-09-26b. (First pass on the raw surface: 112.6 ha, pit-concentrated.) |

Fixed on the way (each cited in the R12 amendment): RGB→RGBA + remainder read;
planner-side water/settlement post-filter; `foliage.canopy` plan + radius;
`saturation` cell-scaling; `--other-instances` measured (185,385).

Plans: `foliage/alpine_8k_{Boulder,TreeStump,CliffOutcrop,CliffOutcropB,CliffFace,
TalusField,TalusFieldB,TalusFieldC,TalusChannel}.json`, **13,883 instances** (run 2, landform
router, derived saturations), all gates PASS, `check_plan_freshness` fresh. Logs:
`research/brief7/rocks_dryrun.log` (raw surface, saturation 0.03), `rocks_write.log` (raw,
0.001875, 12,758 — superseded), `rocks_dryrun2.log` (landform, run 1), `rocks_write2.log`
(landform, run 2 = the plans), `rocks_nanite.log`, `rocks_measure.log`.

**Owed (audit-3, 2026-09-27):** (a) `make_variant_map.py` now routes the scree mask on the
landform too — the NEXT weightmap/variant bake changes the Pass-2 scree mask (a world change,
not done here); (b) the recipe `_saturation_note` SCOPE sentence omits `make_variant_map.py`
as a consumer — edit it at the next planner run (the plans stamp the recipe whole-file, so a
comment edit now would stale nine fresh stamps for a 2 h re-run).

**World run (a later session, after ultrareview + the talus ruling):** ONE
`place_foliage.py --place` handed the four tree plans AND the nine rock plans, stills
(vista + cliff + talus@30 m, Look profile), acceptance, tag look-p2. A rocks-only run deletes
185,385 trees (orphan sweep).


## WORLD RUN — 2026-09-27, DONE (tag `look-p2`)

PR #5 merged (main 7d9318f5). `place_foliage.py --place --place-committed` (new flag — plain
`--place` re-plans first and is blocked) placed the 13 committed plans in ONE run: planned
199,268 = counted 199,268, orphan swept FT_Scrub (0 instances), rocks 13,883 new, trees rebuilt
from their committed rows. `save_foliage_actors --go` → 1,518 IFAs, 1,064 M + 424 new packages
(commit 14a4194b). Proven cold after a relaunch: 199,268 / 1,518. VRAM peak 5,049 MiB.
Stills: `research/brief7/stills/p2_rocks/`. `capture.py` froze the editor after the run (R-CITYSHOT
REJECTED 2026-09-27); stills via shoot.py. Visual acceptance = Ryan on the stills.

## WITHDRAWN — 2026-09-27 (Ryan, on the stills): rocks add nothing; world restored to pre-rocks-place-20260927; R12 RULED 2026-09-27c.
