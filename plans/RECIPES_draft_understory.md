## Verification preamble (read first)

**No number in the brief is wrong.** All six checkable claims reproduce against the artefacts: 8 varieties and `density_per_10m2` 12.0 and `cull_distance_m` 45.0 (`recipes/alpine_8k.json:533-641`); worst sink 6.96% (`Free/_measured/engine_derived.json`, Blueberry_01 `base_offset_z_m` -0.0188 / `height_m` 0.27 = 6.963%) against the 25% limit (`scripts/landscape_spec.py:325`); the dropped key at `scripts/make_landscape_material.py:2932`; and the pack gitignored with **0** tracked files (`.gitignore:206`; `git ls-files LandscapeLab/Content/PN_WildBerries` returns 0 rows).

**Three derived records disagree with their own artefacts, and one brief phrase needs narrowing:**

1. `_verify/20260815_d3_blueberry_understory.md` costs the understory at "~500 triangles average ≈ **3.8M**". The share-weighted LOD0 mean over the eight varieties is **371.9 triangles** (`Free/_measured/pn_blueberry.json` `lod_triangles[0]` × `recipes/alpine_8k.json` shares) → **2.84M**, and that is itself a ceiling because LOD1 takes over at screen size 0.147–0.259. The recorded figure is a rounded-up bound, not the measurement.
2. The same artefact prints `Blueberry_01 … LOD0 tris ?`. It is **195** (`Free/_measured/pn_blueberry.json`, `lod_triangles: [195, 98, 64, 64]`). An unknown was recorded where the source file had the number. **FIXED 2026-09-15 (closure A-9 / AUDIT F-4): `_verify/20260815_d3_blueberry_understory.md:56` now reads 195.**
3. That artefact's "baseline 7.75" is the **p50**; the baseline artefact's mean is **7.76** (`_verify/20260815_alpine8k_framecost_pve_spruce.md`). Quoting a mean against a median is a 0.01 ms comparison that the instrument cannot resolve either way — the artefact says as much, but not that the two numbers are different statistics.
4. "MA_Blueberry carries Level 1/2/3 Wind" is right about the system and loose about the location. Read from package bytes: the switch names are declared in the material **functions** — `Level 1/2/3 Wind` in `PN_AnimationShader.uasset`, `Level 1/2/3 Bending` and the Wobble scalars in `PN_MultiBend.uasset` — which `MA_Blueberry.uasset` composes via `PN_WindAnimation` / `PN_Bending`; and the generated child MIs parent to the vendor **`MI_Blueberry_0N`**, not to `MA_Blueberry`.

---

# R-UNDERSTORY — THE BLUEBERRY UNDERSTORY ON THE GRASS SYSTEM (2026-08-15)

**Status: BUILT, SAVED AND READ BACK FROM THE ASSET. The wind-off claim is
STRUCTURAL, not rendered.** Executed attended under D3; restore point
`pre-d3-blueberry-material-rebuild-20260815`. Narrative: `LESSONS.md`
2026-08-15; artefact `_verify/20260815_d3_blueberry_understory.md`.

The forest had a canopy and bare ground under it. This puts a shrub layer
between them **without spending one persistent instance** — R11's machinery,
a second grass species on the same layer, at a tenth of Meadow's density.

## PRECONDITIONS

- R11 (landscape grass) built and rendering; `grass.DensityScale=1.0` pinned.
- R-ASSET intake of `PN_WildBerries`. The pack is **gitignored with 0 tracked
  files** (`.gitignore:206`), so nothing here may write a vendor byte.
- Every variety mesh MEASURED into `Free/_measured/engine_derived.json` by
  `scripts/measure_tree_packs.py`. The pivot gate reads that file; without it
  the recipe is refused, which is the correct failure.
- The material rebuild is **ATTENDED**. B-BUILD-UNKNOWN is open on
  `make_landscape_material.py`, and this run rewrites the whole graph.

## LOCKED VALUES

Read back from `/Game/Foliage/GT_alpine_8k_Blueberry` and from
`recipes/alpine_8k.json:532-641`. Asset name comes from
`/Game/Foliage/GT_{biome_id}_{name}` (`make_landscape_material.py:2960-2961`)
with `biome_id` `alpine_8k`.

    species        Blueberry     layer Grass     system "grass"
    density        12.0 per 10 m²  (species TOTAL, split by share)
    cull           45.0 m -> end 4500 cm, start 3375 cm (0.75 x, :2682-2685)
    scaling        UNIFORM, scale_x [0.8, 1.4] on every variety
    rotation       random_rotation True, align_to_surface True
    shadows        cast_dynamic_shadow False
    density scaling enable_density_scaling **False** (:2735) — placed
                   deliberately, exempt from scalability thinning

| variety | share | density /10 m² | LOD0 tris | height m | base_z m | sink |
|---|---|---|---|---|---|---|
| `Blueberry_01` | 0.14 | 1.68 | 195 | 0.270 | −0.0188 | **6.96%** |
| `Blueberry_02` | 0.12 | 1.44 | 436 | 0.340 | −0.0078 | 2.29% |
| `Blueberry_03` | 0.12 | 1.44 | 344 | 0.407 | −0.0049 | 1.20% |
| `Blueberry_04` | 0.10 | 1.20 | 434 | 0.291 | −0.0038 | 1.31% |
| `Blueberry_05` | 0.08 | 0.96 | 1,168 | 0.432 | −0.0188 | 4.35% |
| `Blueberry_06` | 0.18 | 2.16 | 96 | 0.212 | −0.0016 | 0.75% |
| `Blueberry_07` | 0.14 | 1.68 | 284 | 0.235 | −0.0093 | 3.96% |
| `Blueberry_08` | 0.12 | 1.44 | 476 | 0.235 | −0.0093 | 3.96% |

Shares sum to exactly 1.00 and densities to exactly 12.0. Sizes and pivots
from `Free/_measured/pn_blueberry.json`; sink is `|base_offset_z_m| / height_m`
as `landscape_spec.uncorrected_pivot_errors()` computes it (`:384`).

**Every variety carries `override_materials`** —
`/Game/Materials/PN_NoWind/MI_MI_Blueberry_0N_nowind`, one per mesh, all
single-slot (`material_slots: 1` on all eight).

## THE PIVOT GATE — THE GRASS SYSTEM CORRECTS NOTHING

`rock_scatter.plan_species` READS `base_offset_z_m` and subtracts it, so a
rock lands on its base whatever the vendor pivot. **The engine's landscape
grass system does no such thing**: it puts the mesh's PIVOT on the surface
and the geometry falls where it falls (`landscape_spec.py:348-362`). A
box-centred pivot buries exactly 50% by construction, which is why the bound
is **`MAX_UNCORRECTED_SINK_FRAC = 0.25`** (`:325`) — half is the stated
disaster line and a quarter is the conservative side of it.

The eight pass with margin: worst is `Blueberry_01` at **6.96%**, i.e. 1.88 cm
of a 27 cm shrub. **That is the vendor's doing, not ours** — these were
authored near their base — and it is a measurement, not a design tolerance.
Two of the three engine-derived tree rows the same recipe names sit at
0.004–0.024%.

`_recipe_mesh_paths_split` adds every **variety** mesh, not just the species
`mesh` (`landscape_spec.py:269-272`), so all eight reach the check rather than
the one named at the species level.

## WIND MUST BE OVERRIDDEN, NEVER EDITED — AND WHY

`MA_Blueberry` composes `PN_WindAnimation` and `PN_Bending`, whose static
switches are `Level 1/2/3 Wind` (`PN_AnimationShader.uasset`) and
`Level 1/2/3 Bending` plus the Wobble scalars (`PN_MultiBend.uasset`) — read
from the package name tables. An animating understory makes every frame A/B
non-deterministic, and this project's method is single-variable frame
comparison against a noise floor in the third decimal place.

Three constraints close off every route but one:

1. **The pack must not be edited.** `LandscapeLab/Content/PN_WildBerries/` is
   gitignored (`.gitignore:206`) with **0 tracked files**. An edit to
   `MA_Blueberry` or to `MI_Blueberry_01` vanishes on re-download and git
   cannot restore it — the Fab-boundary rule's worked example exactly.
2. **The grass system offers no per-instance material hook.** There is no
   foliage-type layer to hang it on; `GrassVariety` is the whole contract.
3. **`GrassVariety.override_materials` really exists in 5.8** — `Array
   [MaterialInterface]`, "Material Overrides", **PythonStub :121628**, inside
   `class GrassVariety(StructBase)` at :121598. Resolved against this install,
   not remembered.

So: **child MIs in a tracked folder, referenced by the variety.**
`scripts/make_nowind_material_instances.py` creates them (`DEST_DIR
= "/Game/Materials/PN_NoWind"`, `:72`; `WIND_SWITCHES` the six names at
`:67-70`; naming `"MI_" + <source> + "_nowind"` at `:135`) and **reads every
switch back off the created asset**, refusing on a missing or disagreeing one
(exit 4). Static switches, not scalars: a switch set false compiles the branch
out; a scalar set to zero still evaluates it every frame (`:20-26`).

**The doubled prefix is deliberate and now load-bearing.** The sources are
already `MI_`-prefixed, so the children are `MI_MI_Blueberry_0N_nowind`.
Cosmetic — and renaming them breaks the override paths recorded in the recipe
and in `Free/_measured/pn_blueberry_nowind_overrides.json`. Leave it.

## PROCEDURE

```
1. python scripts/measure_tree_packs.py --pack PN_WildBerries      # pivots
2. register the measured rows in Free/_measured/engine_derived.json
3. python scripts/make_nowind_material_instances.py --meshes <8> --go
4. edit recipes/alpine_8k.json: the grass species + 8 varieties + overrides
5. python scripts/make_landscape_material.py --assign               # ATTENDED
6. In-editor console: grass.FlushCache      (see OPEN — unverifiable)
7. python scripts/read_grass_type.py /Game/Foliage/GT_alpine_8k_Blueberry \
       --expect-all-overridden
8. python scripts/capture.py --tag <tag>
```

Step 7 is not optional and is not a formality. See REJECTED.

## VERIFICATION

Three representations, and they share no code:

- **The builder's own read-back** re-reads `grass_varieties` off the saved
  asset and re-sums the densities rather than counting the list it set
  (`make_landscape_material.py:2738-2772`).
- **`scripts/read_grass_type.py`**, which shares nothing with the builder and
  turns the expectation into a REFUSAL: exit 4 on a failed expectation, exit 5
  on "could not look" (`:16-23`). `--expect-all-overridden` is the flag that
  would have caught the defect below on the day it was written.
- **The package bytes on disk, offline, with no editor.**
  `LandscapeLab/Content/Foliage/GT_alpine_8k_Blueberry.uasset` (17,972 B) has
  all eight `/Game/PN_WildBerries/Meshes/Blueberry/Blueberry_0N` **and** all
  eight `/Game/Materials/PN_NoWind/MI_MI_Blueberry_0N_nowind` in its name
  table, alongside `GrassVarieties` / `EGrassScaling::Uniform`. This is the
  cross-representation check non-negotiable 0 asks for: the builder, its
  read-back and the audits all run inside one editor; the bytes do not.

Recorded alongside, from the D3 artefact:

    M_Alpine8K   147,145 B  sha 0152ecb529abe45c7aca3f23c3358d263b05eb31
                            a941a211d3f1dfb03def4928     (was 146,819)
    graph        298 expressions, 298 reachable, 0 ORPHANED
    samplers     37 audited, 0 mismatches
    frame        _verify/20260815_alpine8k_d3_blueberry_forest_floor.png

**The material's size and SHA-256 were re-derived from the file on disk in
this session and match exactly.** The expression, sampler and vendor-boundary
counts are quoted from the artefact and were NOT re-measured offline.

## COST MODEL — so −0.01 ms is not read as free

    cull disc     pi * 45^2            =  6,361.7 m²
    units of 10 m²                     =    636.2
    x 12.0 per 10 m²                   =  7,634 instances
    x 371.9 tris (share-weighted LOD0) =  2.84M triangles, WORST CASE

Against R11's locked grass budget of 29.8M triangles and a scene already
drawing 153,796 trees, that is roughly +10% on grass instance count. LOD1
takes over at screen size 0.147–0.259 on these meshes, so 2.84M is a ceiling
the frame does not actually pay.

Measured GPU at `forest_floor`: **7.74 ms mean, p90 7.87** against a baseline
of 7.76 mean / 7.75 p50 (`_verify/20260815_alpine8k_framecost_pve_spruce.md`).
The abort bar was +1.5 ms. **The honest statement is "under the measurement
floor", not "free"** — a delta of 0.01–0.02 ms is smaller than the spread of
the instrument that produced it.

## OPEN — stated plainly

- **`grass.FlushCache` cannot be verified.** It is a command-style cvar that
  self-resets, so `render_condition` reads back 0 and REFUSES to vouch for it
  — correctly, since it cannot tell "ran and reset" from "never took". The
  capture shows the understory rendering, so the cache is evidently current;
  the cvar's own read-back is simply not an available instrument.
- **The wind-off claim is STRUCTURAL.** The overrides are proven present on
  the asset; **no frame-pair test has been run on the understory.** The tree
  case was measured (`_verify/20260815_pn_wind_is_live.md`) and this shares
  its mechanism — which is an argument, not a measurement.
- **Nothing was scattered and no world was saved by D3.** It touches the
  landscape material and the grass types only.
- **The pivot gate is applied to engine-derived rows regardless of who places
  them** (`landscape_spec.py:442-444`). For an INSTANCED species
  `place_foliage` does correct the pivot, so the 25% bound is stricter than
  that path needs. Harmless today (worst engine-derived row 0.071%); it would
  refuse a legitimately box-centred instanced tree, and the refusal message
  would name the grass system for a species that is not on it.

## REJECTED

- **`override_materials` declared on a variety and dropped in the transform**
  → `grass_entries()` rewrites each recipe variety into
  `{mesh, density, smin, smax}` at `make_landscape_material.py:2932-2937`, and
  **that dict is the only thing the payload ever sees.** The recipe declared
  the overrides, the validator accepted them (`import_heightmap.py:804-837`),
  the payload was written to set them and to fail closed on an unloadable one
  (`:2694-2727`), and the builder **reported success**. Connectivity passed.
  Samplers passed. All eight varieties read back **`overrides: NONE`** off the
  saved asset. → **CORRECT: carry the key through the transform**
  (`:2953-2954`), set only when present so a species that declares none keeps
  an ABSENT key rather than an empty list that reads like a decision
  (non-negotiable 21). **Nothing else could have caught this** — a grass type
  with no overrides is a perfectly well-formed grass type, so both audits are
  blind to it by construction. The instrument that found it reads the SAVED
  asset and shares no code with the builder: `scripts/read_grass_type.py`,
  with `--expect-all-overridden` as a REFUSAL, never a printed observation.
  **The general rule: a payload can only be correct about fields it receives.
  When a builder transforms its input, the transform is the contract, and a
  key omitted there is unreachable however carefully the far end handles it.**
- **A merged "verified" registry with `if ok: continue`** →
  `recipe_normalization_errors` merged the Blender-normalised and
  engine-derived registries into one map and continued on any hit, so
  **registering a mesh as engine-derived EXEMPTED it from the pivot gate
  entirely.** The two do not carry the same guarantee: BLENDER-NORMALISED
  means the pivot is at the base *by construction*; ENGINE-DERIVED means
  somebody MEASURED it and the pivot is wherever the vendor left it. Blueberry
  is a grass species made of vendor `.uasset` meshes — exactly the combination
  the hole was shaped for. → **CORRECT: tag provenance at merge time**
  (`landscape_spec.py:226`) **and run the check on engine-derived rows**
  (`:442-444`). *This hole was opened earlier in the same session that needed
  the gate — a widening done for a good reason that silently removed the
  guarantee three lines away.*
- **Editing `MA_Blueberry` or the vendor `MI_Blueberry_0N` to disable wind** →
  gitignored, 0 tracked files, gone on re-download, and git cannot restore it.
  It would look like committed work for exactly as long as nobody re-downloads
  the pack. → **CORRECT: child MIs in `/Game/Materials/PN_NoWind`, referenced
  through `GrassVariety.override_materials`.**
- **Setting the wind SCALARS to zero instead of the static switches** → the
  branch still evaluates every frame, and a future parameter push could set it
  back. A static switch set false compiles the branch out
  (`make_nowind_material_instances.py:20-26`). → **CORRECT: the six switches,
  Wind AND Bending together** — Bending is the same interactive-animation
  system and leaving it on reintroduces the non-determinism the whole exercise
  removes.
- **Placing the understory as INSTANCES** → 7,634 instances inside a 45 m disc
  is the *local* figure; the shrub layer covers the forest floor, and the
  instance budget is a shared 250,000 ceiling already holding 153,796 trees.
  Precedent is the 2026-08-08 carpet-density ruling: carpet density belongs on
  the grass system, instances are for sparse landmarks. → **CORRECT:
  `system: "grass"`, at zero persistent-instance cost.**
- **A grass species' `slope_deg` and `height_m`** → **MANDATORY INERT
  FIELDS, and they read like placement constraints that are not in force.**
  The validator REQUIRES both on every species with no grass exemption
  (`import_heightmap.py:923-934` — contrast `:914`, which correctly exempts
  grass from `weight_share`), and **nothing consumes them on the grass path**:
  `grass_entries()` reads only name, layer, `density_per_10m2`, `varieties`,
  `mesh`, `scale_range` and `cull_distance_m`
  (`make_landscape_material.py:2880-2977`), and `place_foliage.py:191-192`
  skips grass species entirely. So `recipes/alpine_8k.json:536-543` states
  "blueberry between 120 and 640 m, below 30°" and the understory in fact
  follows the Grass weight mask wherever it exists. This is the class the
  schema already forbids for KEYS — an inert field reads like a setting. →
  **CORRECT (not yet built): exempt grass species from the slope/height
  requirement as `weight_share` already is, or make the grass output actually
  read them.** Until then, do not tune those numbers expecting anything to
  move. *Note Meadow carries the same two inert keys, so this is a pre-existing
  pattern the understory inherited, not a new one.*
- **Believing the offline gate suite covers this** → `prove_gates.py:78` pins
  `RECIPE` to **`recipes/alpine.json`**, and the string `alpine_8k` appears
  nowhere in that file. `run_uncorrected_pivot_probes` (`:691-762`) therefore
  mutates the first grass species with varieties in *alpine.json*, which is
  **Meadow**, and `alpine.json` names no PN or PVE mesh at all — so the
  engine-derived provenance branch the D3 fix added is **never reached by the
  standing suite**. The box-centred probes and the neither-registry probe are
  real and still fire; the blueberry rows and the branch written for them have
  no standing coverage. → **CORRECT: parameterise the suite over both recipes,
  or add an alpine_8k probe.** Until then the fix is proven by an ad-hoc run,
  which is what UNPROVEN means.
- **Reading `recipes/schema.md` to learn what a variety may declare** →
  `override_materials` is absent from it. The v1.10 varieties table
  (`recipes/schema.md:539-570`) lists `mesh`, `share`, `scale_range` and
  nothing else, and the newest revision heading in the file is v1.16 (`:728`),
  while the validator's own comment calls the key **v1.22**
  (`import_heightmap.py:809`). The validator refuses unknown keys, so the
  normative contract is the document that misleads: a fresh session reading
  schema.md would conclude the key is illegal. → **CORRECT: schema.md gains a
  v1.22 section.** This is the same lag already recorded for the rock-species
  contract; it is now two revisions wide.
- **Quoting "~500 triangles average"** → the share-weighted LOD0 mean is
  **371.9**, and the unweighted mean is 429.1. Neither is 500. The 3.8M figure
  is a rounded-up bound presented as a calculation. → **CORRECT: 2.84M worst
  case, and say that LOD1 at screen size 0.147–0.259 means the frame never
  pays it.**