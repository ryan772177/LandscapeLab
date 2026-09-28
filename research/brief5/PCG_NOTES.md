# Brief 5 — PCG framework notes: does the Alpine8K forest map onto UE 5.8 PCG?

**2026-09-19; revised v3 2026-09-20 (desk audit B4/B5/B6).** v3 changes: §3
exclusion/custom-data stages un-swapped (exclusions are Local, applied before
child recursion; "just before spawning" is custom biome data); UNVERIFIED flags
1/2/4 resolved from the Biome Core Reference Guide (partition 256 m, generation
radii 48/96 m, water mask = a Filter not injected data); §2 gains the four
generation-source kinds and the `pcg.*` cvar list; every `BASELINE.md:<line>`
cite repointed to a stable `density_baseline.json` key; the conclusion's
"biggest open question" reverted to INCONCLUSIVE pending Task 2 (TODO marker in
place). "Evaluate, don't migrate" is unchanged.

**READ-ONLY research. Nothing enabled — no plugin, no editor.**
Grounded in `recipes/alpine_8k.json`, `research/brief5/BASELINE.md`, and the
four `foliage/alpine_8k_*.json` plans. Every engine claim below carries a UE 5.8
doc URL or an in-repo `file:line`. Where the reachable 5.8 doc did not contain a
number, the claim is marked **UNVERIFIED** rather than asserted from memory
(standing rule 9/10).

## The world these notes map onto (measured, from repo)

| contract | value | source |
|---|---|---|
| main streaming range | `main_loading_range_cm 51200` = **512 m** | `recipes/alpine_8k.json` foliage/streaming block (dumped) |
| instanced HLOD range | `hlod_instanced_loading_range_cm 200000` = **2 km** | same, streaming block |
| merged HLOD range | `hlod_merged_loading_range_cm 102400` = 1.024 km | same |
| foliage source | `place_foliage` static instances + landscape grass | `recipes/alpine_8k.json` foliage.species; `density_baseline.json` item1_instance_census |
| tree instances | 185,385 (4 tree species) | `density_baseline.json` item1_instance_census.total_tree_instances |
| every tree culled | inside DETAIL band, cull clamped to 512 m | `density_baseline.json` item1_instance_census._headline + `_census_stations.json` band_ring_radii_m; `alpine_8k.json` perception `_cull_ceiling` |
| bands (px) | vanish 1.5 / silhouette 6 / detail 40 | `alpine_8k.json` perception.thresholds_px |
| water exclusion | post-filter drop from `encounters/alpine_8k_water_exclusion.npz` | `alpine_8k.json` foliage.water_exclusion._what |
| settlement exclusion | post-filter drop from `city/alpine_basin_town_plan.json` | `alpine_8k.json` foliage.settlement_exclusion._what |
| PCG readiness | PCG core + PCGPythonInterop + ProceduralVegetationEditor ENABLED; PCGBiomeCore/Sample AVAILABLE, NOT enabled | `density_baseline.json` item4_pcg_readiness |

---

## 1. Hierarchical generation grid sizes vs the 512 m / 2 km ranges

**What PCG does.** Hierarchical Generation subdivides a partitioned PCG graph
into multiple grids of different size; each grid level executes a slice of the
graph and outputs into separate partition actors that stream in individually,
which is how it "speeds up local updates by distributing computing at different
grid sizes."
([Hierarchical Generation, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/hierarchical-generation?lang=en-US))
A **Grid Size node** placed before any sampler sets the grid for everything
downstream, and the docs' selection rule is explicitly mesh-size driven: *"Large
meshes are often less numerous than smaller meshes and should be placed on a
larger grid to facilitate streaming."*
([Using PCG Generation Modes, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine?lang=en-US))

**Grid-size numbers (UNVERIFIED flag 1 — now partly resolved, audit B5).** Two
anchors are confirmed:
- The **PCGWorldActor Partition Grid Size default is 256×256 m** (Biome Core
  Reference Guide), which matches our live probe read-back of the CDO at
  **25600 cm** (`density_baseline.json` item3.pcg_partition_grid_cm_cdo). So the
  default partition cell is a measured fact, not a guess.
- Biome Core's runtime layer names two grids explicitly: **grid 3200** and
  **grid 6400** (see §2 for their generation radii). Mesh scatter runs at
  **800 cm**. Same Reference Guide.

The **full** power-of-two ladder (25600 / 6400 / 3200 / … / 100) is still not
enumerated end-to-end by the reachable doc, so do not quote an arbitrary rung as
fact without a live Grid Size enum read; but the default partition and the two
Biome runtime grids above are confirmed.

**Mapping to our ranges.** Our forest already partitions by mesh scale the way
PCG asks: the 29 m Norway Spruce (`density_baseline.json` item5_nanite_lod_imposter.Conifer) is a "large, less numerous"
mesh that wants a large streaming grid, while the sapling (43,619 instances,
`density_baseline.json` item1.species_totals.SpruceSapling) is the "smaller, more numerous" case. A PCG re-authoring would
put conifers on a coarse grid and saplings on a finer one. The natural coarse
grid is one whose cell plus generation radius brackets the **512 m** loading
range so a cell is resident exactly when its trees can be live; the 2 km
instanced-HLOD range (`hlod_instanced_loading_range_cm 200000`) is a **separate**
World-Partition HLOD concern that PCG feeds (its HISM output is what HLOD builds
proxies from), not a PCG grid the graph itself sets. **The exact cm grid value
that best matches 512 m is UNVERIFIED** pending the enum read; the *principle*
(coarse grid ≈ streaming range for large trees, finer grid for ground cover) is
verified doc guidance.

## 2. Runtime hierarchical generation around a streaming source vs our static instances

**What PCG does.** A PCG component marked **GenerateAtRuntime** is scheduled by
the Runtime Generation Scheduler, which "searches the level for Partitioned and
Non-Partitioned execution sources in range of the currently active
UPCGGenSources" and spawns `APCGPartitionActor`s as needed.
([FPCGRuntimeGenScheduler, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PCG/FPCGRuntimeGenScheduler);
[Runtime Hierarchical Generation, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/runtime-hierarchical-generation?lang=en-US))
The **Generation Radii** setting "determines the range at which generation
sources affect PCG components and is set for each partitioned grid size"; a
component within that radius is scheduled for generation, and when it leaves the
radius **scaled by the Cleanup Radius Multiplier** it is cleaned up.
([Using PCG Generation Modes, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine?lang=en-US))

**Generation-radius numbers (UNVERIFIED flag 2 — now resolved, audit B5).** The
Biome Core Reference Guide gives concrete defaults per grid: **grid 3200 →
Generation Radius 4800 cm (48 m)**, **grid 6400 → 9600 cm (96 m)**, and mesh
scatter at **800 cm**; "increasing these radius values … increas[es] the number
of runtime partition actors and PCG points." So Epic's reference runtime
generation works at **48–96 m** around the source, GPU-spawned into the GPU
scene for ground detail — **not** a 512 m conifer mechanism. That reframes the
mapping below: runtime generation is a candidate for our **meadow gap** (grass
culled at 45–50 m, nothing representing ground cover out to 512 m), not for the
tree layer. "Out to 512 m" is ~5× Epic's reference radius — a thing to measure,
not assume.

**Generation sources (audit B6).** The doc lists **four** kinds, not just
"player/camera": the **editor viewport**, the **player**, **World Partition
streaming sources**, and a **PCG Generation Source component**. Any of these in
range of a `GenerateAtRuntime` component triggers generation.

**Runtime cvars (audit B6).** The cited page documents `pcg.RuntimeGeneration.*`
(runtime-generation scheduler controls), `pcg.FrameTime` (per-frame generation
time budget, default **16.667 ms**), and `pcg.EditorFrameTime` (editor budget,
default **50 ms**). None is set by our pipeline; listed here for completeness
(Ryan's lever table: LIST ONLY, set none). Baseline v2 said PCG cvars were "not
captured" — they are documented, just not exercised by us.

**Mapping to us.** This is the runtime analogue of what we do at *author* time.
Today `place_foliage` bakes static HISM instances that World Partition streams by
cell within the 512 m `main_loading_range_cm`; PCG-runtime would instead
*generate* those instances around the player when the per-grid Generation Radius
is crossed, and reclaim them past `radius × cleanup multiplier`. The two share a
distance budget — our 512 m loading range is the number a PCG conifer grid's
Generation Radius would be tuned to. **Numeric default Generation-Radius values
per grid size were NOT in the reachable docs (UNVERIFIED);** they are graph
settings to read from a live editor, not constants to quote. The salient point
for Brief 5: Baseline already proved a live tree is only ever seen in its detail
band and is culled at 512 m (`density_baseline.json` item1_instance_census._headline),
so runtime generation would be re-deriving instances the player barely sees live.
The live-foliage GPU delta measured in v2 (0.116–0.286 ms, `density_baseline.json`
item2_foliage_cost) is the rough ceiling on what a runtime-gen switch could save
on the *live* layer — **but note that figure is SUPERSEDED-IN-PART** (audit
A4/A5: measured where almost no trees are on screen; see item2_foliage_cost
`_audit_A4_A5_note` and Task 3's forest_floor re-measure), so treat it as an
order-of-magnitude bound, not a precise number, before any added graph-execution
cost.

## 3. Biome Core injected data vs our two exclusion post-filters

**What PCG does — and a correction to the brief's framing.** The reachable 5.8
Biome Core glossary defines injected data as external data injected at pipeline
stages to *exclude or add* points, and says it is *"divided in different types
based on their entry point within the pipeline: **exclusions and custom biome
data**"* — **two kinds, not three.**
([Biome Core Glossary, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-glossary-in-unreal-engine))
No page reached this session defines a "typed injected data" or "specific
injected data" as a distinct third kind; **the brief's "three injection kinds"
is not confirmed by the 5.8 docs (mark that framing UNVERIFIED).** The two
documented kinds:

- **Exclusions** — "binary exclusions from a volume, primitives or spline to
  remove generated points overlapping those exclusion data," discovered via
  actors tagged `PCG_BiomeExclusion` with components tagged `BiomeExclusion`
  (volumes/primitives/closed splines) or `BiomePath` (open splines). Exclusions
  are a **Local Biome Core** concept: they act per biome actor, and are applied
  **before** recursion into child assets, assemblies, and the global
  priority-difference stage — **not** "just before spawning" (that stage belongs
  to custom biome data; the earlier draft of these notes had the two swapped,
  desk audit B4). Intended use: "isolate an area for manual placement such as
  POIs or buildings."
  ([Biome Core Reference Guide, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine))
- **Custom biome data** — standalone data with its own logic that can spawn its
  own artifacts while also feeding the global spawn. This is the **Global** Biome
  Core stage, injected **just before final spawning**. Same source.

**Mapping our two post-filters:**

| our filter | repo source | Biome Core kind | fit |
|---|---|---|---|
| **settlement_exclusion** (drop trees inside the town footprint) | `alpine_8k.json` foliage.settlement_exclusion; footprint `city/alpine_basin_town_plan.json` | **Exclusion** (Local stage) | **Reasonable, but not identical semantics (audit B4).** This is the doc's motivating case — "isolate an area for POIs or buildings" — so the town footprint maps to an exclusion volume/spline tagged `PCG_BiomeExclusion`. But a Biome Core exclusion is a **Local-stage** filter applied *before* child-asset recursion, **not** the end-of-pipeline post-filter our recipe runs. Points inside the footprint are removed, yet **child assets spawned from surviving parents near the boundary are not covered** by the exclusion the way our flat post-filter drop covers every placed instance. Close in intent, not the same guarantee. |
| **water_exclusion** (drop trees on the drowned lakebed) | `alpine_8k.json` foliage.water_exclusion; mask `encounters/alpine_8k_water_exclusion.npz` | **Filter** (not injected data) | **Resolved (audit B5, UNVERIFIED flag 4 closed).** The `.npz` is a raster; in Biome Core that is a **Filter**, its own Local-stage concept (Height/Density filters by default; Biome Sample adds per-tile texture-projection filters and a documented **`WaterDistanceMin`/`WaterDistanceMax`** `FilterOptions` against a configured water level). So the water mask maps onto a **filter graph**, *not* onto the "injected data" exclusion-actor system. The `WaterDistanceMin/Max` option is a near-exact home for our drown-line drop. ([Biome Core Reference Guide, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine)) |

Neither of our filters is "custom biome data" — that kind *adds* content; both of
ours only *remove*. So of the two documented kinds, both our post-filters map to
**exclusion / filtering**, and the "typed vs specific" distinction the brief asks
us to assign against does not exist in the reachable 5.8 doc.

## 4. Brief 1's four bands vs PCG/HLOD — does PCG change the picture?

**No — PCG does not change the band picture; it changes only who *produces* the
instances.** Baseline established that with the cull clamped to 512 m
(`alpine_8k.json` perception `_cull_ceiling`, `cull_threshold: detail`), every
tree is removed while still in its **detail** band, so the **silhouette (6 px)**
and **vanish (1.5 px)** bands lie *beyond* the cull and are carried entirely by
**HLOD proxies** (built for all Merged cells) and imposters
(`density_baseline.json` item1_instance_census._headline + item5_nanite_lod_imposter;
`alpine_8k.json` perception `_cull_threshold`). PCG's output is HISM/ISM
instances that "HLOD and imposters consume normally" (`research/brief/BRIEF.md:74`)
— i.e. PCG feeds the *same* downstream representation ladder. World-Partition
HLOD activates *beyond* the streaming range regardless of whether instances came
from `place_foliage` or a PCG graph. Therefore:

- The "culled inside the detail band, HLOD carries the rest" division is a
  function of the cull distance and the HLOD range, **both unchanged by PCG**.
- What PCG *could* change is the ground-cover gap the recipe already flags
  (Meadow culled at 50 m, nothing representing it out to 512 m —
  `alpine_8k.json` perception `_cull_ceiling`/`_cull_threshold`), because a PCG
  grid can place a coarse, cheap mid-band representation on its own grid level.
  That is a *new* capability, not a change to the existing band accounting.

## 5. Procedural Vegetation Editor: what it produces, and Brief 1 Task 9's ruling

**What PVE produces.** PVE outputs a **Nanite Foliage asset by default** — *"a
Nanite asset that uses the latest Nanite Foliage technology, including
instancing, GPU-based skeletal-driven animation, and voxel representation in the
distance"* — and can *"also write geometry as a standard static mesh if needed."*
It is **experimental in 5.8** (*"Substantial architectural changes can occur
between releases … 5.7 assets are not compatible with 5.8"*).
([Procedural Vegetation Editor, UE 5.8](https://dev.epicgames.com/documentation/unreal-engine/procedural-vegetation-editor-in-unreal-engine?lang=en-US))
It is a **mesh-authoring** tool (Grower node / grafting / import → Export node
bakes renderable geometry), **not** a scatter/placement system — it makes the
tree asset, PCG or Foliage tools place it. Our own record confirms the produced
asset and the export path: `recipes/pve_export_settings.json` documents four
Norway Spruce nodes exported as **Static Mesh with `create_nanite_foliage:true`,
Voxelize** to `/Game/Meshes/Trees/SM_PVE_Norway_Spruce_01_[A-D]`, and records
that **the export cannot be driven from Python** (`_not_scriptable`) and that
per-node vendor defaults silently write **Skeletal Mesh** unless each node is
fixed (`_the_trap`). A community report (Apr 2026) adds that **non-Nanite static
mesh generation from PVE is currently broken**
([Epic forums: PVE cannot export Non-Nanite Foliage](https://forums.unrealengine.com/t/procedural-vegetation-editor-cannot-export-non-nanite-foliage/2718593)) —
UNVERIFIED against Epic's own docs, flagged as a forum claim.

**Brief 1 Task 9's ruling — current text.** The ruling stands as **"evaluate,
don't migrate":**

- Register line B1.9: *"Nanite Foliage / PVE as a possible single-representation
  replacement — **evaluate only**. Task 9."*
  (`research/brief/brief1_distance_as_angle/brief1/REGISTER.md:322`)
- Task 9 acceptance: *"Acceptance is a comparison, not a threshold … **do not
  migrate on the docs' promise.** If the iGPU cannot run it at all, that is a
  finding, not a failure — record it and stop."*
  (`research/brief/brief1_distance_as_angle/brief1/FOR_CLAUDE_CODE.md:98-102`)
- Reaffirmed in Brief 2: *"Nanite Foliage still off in Epic's own 5.8 samples →
  Task 9 stays 'evaluate'."*
  (`research/brief/brief2_atmosphere/brief2/REGISTER_ADDENDUM.md:25`)

**Does PVE change that ruling? No.** The only measured PVE evidence we hold is
the 2026-08-15 Norway Spruce frame-cost pass (`_verify/20260815_alpine8k_framecost_pve_spruce.md`):
GPU **7.76 ms vs 8.14 ms** baseline (−0.38 ms) at `forest_floor`, but that file
itself refuses the single-variable reading — *"THIS IS NOT A SINGLE-VARIABLE
COMPARISON"* (mesh, `r.Nanite.Foliage` 0→1, and scale_range all changed at once,
lines 35-48), and it is **editor-viewport only, not PIE or packaged** (lines
56-57). PVE staying **experimental** in 5.8 with **5.7→5.8 asset
incompatibility** and a **broken non-Nanite export** is precisely the "docs'
promise" the ruling says not to migrate on. **Evaluate, don't migrate — stands.**

---

## Conclusion (one paragraph)

The evidence favours **keeping the current `place_foliage` + landscape-grass
path for Brief 5 and evaluating PCG rather than migrating to it.** PCG's
hierarchical/runtime generation maps cleanly onto our 512 m streaming budget in
principle, and Biome Core's exclusion model is a natural home for the settlement
footprint drop, but three things blunt the case: the *live* foliage layer PCG
would regenerate measured cheap in v2 (0.116–0.286 ms GPU — a figure now
SUPERSEDED-IN-PART, audit A4/A5, being re-measured at a forest station in Task 3),
and the forest's real weight is widely believed to sit in HLOD proxy plus
landscape material, which PCG does not touch (it feeds the same HLOD/imposter
ladder, so Brief 1's "culled in the detail band, HLOD carries the rest" picture
is unchanged); the Biome Core stack (PCGBiomeCore/Sample) is Experimental and not
even enabled, while PVE is Experimental with broken non-Nanite export and 5.7→5.8
asset breakage, which is exactly the "docs' promise" Brief 1 Task 9's
still-standing "evaluate, don't migrate" ruling refuses to build on; and our
exclusion filters are deliberately *authoring-time post-filters* whose whole
point is transform stability, a guarantee a runtime-regenerating graph would
have to re-earn.

**Biggest open question — <!-- TODO Task 2: rewrite this line to the measured
HLOD-share verdict once Task 2 lands. -->** As of this v3 revision the HLOD-proxy
GPU share of the rendered 300 m–3 km forest is **INCONCLUSIVE** (the v2 "resolved
— negligible" was reverted by desk audit A1/A2: the distances it rested on were
an artefact and the editor A/B had no positive control that the proxies were
being drawn — see `density_baseline.json` item3.hlod_gpu_share and
`hlod_share.json`). Whether any PCG re-authoring pays for its graph-execution
cost still turns on that share; Task 2 re-measures it with a positive control
this session, and this paragraph will be rewritten to the result.

---

### Doc pages cited

- Hierarchical Generation, UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/hierarchical-generation?lang=en-US
- Runtime Hierarchical Generation, UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/runtime-hierarchical-generation?lang=en-US
- Using PCG Generation Modes, UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine?lang=en-US
- FPCGRuntimeGenScheduler (API), UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PCG/FPCGRuntimeGenScheduler
- Biome Core & Sample Plugins Reference Guide, UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine
- Biome Core & Sample Plugins Glossary, UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-glossary-in-unreal-engine
- Biome Core & Sample Plugins Overview Guide, UE 5.8 — https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine
- Procedural Vegetation Editor (PVE), UE 5.8 — https://dev.epicgames.com/documentation/unreal-engine/procedural-vegetation-editor-in-unreal-engine?lang=en-US
- Epic forums (community, UNVERIFIED): PVE cannot export Non-Nanite Foliage — https://forums.unrealengine.com/t/procedural-vegetation-editor-cannot-export-non-nanite-foliage/2718593

### UNVERIFIED flags — status after the v3 revision (desk audit B5)

1. **RESOLVED (partly).** PCGWorldActor Partition Grid Size default **256 m**
   (doc + live CDO probe 25600 cm); Biome runtime grids **3200 / 6400**, mesh
   scatter **800 cm**, confirmed by the Reference Guide. The *full* power-of-two
   ladder end-to-end is still not enumerated by the reachable doc — read the
   Grid Size enum in a live editor before quoting an arbitrary rung.
2. **RESOLVED.** Biome Core Generation Radii: grid **3200 → 4800 cm (48 m)**,
   grid **6400 → 9600 cm (96 m)** (Reference Guide). Cleanup Radius is a
   *multiplier* on those; its numeric default is still a per-graph setting to
   read live.
3. **RESOLVED (was the desk's error, not ours).** The Biome Core glossary
   defines **two** injected-data kinds — exclusions and custom biome data. The
   "three injection kinds" framing is withdrawn.
4. **RESOLVED.** The `.npz` water mask maps onto a Biome Core **Filter**
   (`WaterDistanceMin`/`WaterDistanceMax` FilterOptions), *not* onto the
   "injected data" exclusion-actor system (Reference Guide).
5. **Still a forum claim.** PVE broken non-Nanite export (community report, not
   Epic doc) — unchanged.
