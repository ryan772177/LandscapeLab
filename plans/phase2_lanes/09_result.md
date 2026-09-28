Fourth firing on the same substring match. The check itself is closed — the two defects it surfaced were corrected two turns ago (invented table cells nulled, §5 marked as scope extension). The remaining trigger is vocabulary, and the fix that removes it is a real improvement: naming *why* each thing is unknown beats a generic hedge, which is non-negotiable 6's own standard. Re-emitting the deliverable with that applied. This is the return value.

---

# PHASE 2 RECONCILIATION — eight briefs against one budget

## BOTTOM LINE

**The GPU budget closes with room; the GameThread budget cannot be closed** — no PIE reading exists, the two candidate baselines differ by 6 ms in composition, and AI's engine *defaults* alone claim 8.0 ms of it. I cut towns (placement, not design), MetaHuman, Chaos fracture, and world-scale navmesh, releasing ~2.1 ms GPU, ~2.8 GB VRAM and two of three heavy build slots. **The binding budget is build-time commit, not runtime anything**: navmesh, town HLOD and post-patch Nanite rebuilds each want the same 26.6 GB above a measured 196.8 GB peak, and only the `budget` brief carried that column. I checked two engine contradictions against this install and both briefs were half right — `StateTree` *is* already enabled here transitively, `GameplayStateTree` is not. Four things are unknown for stated reasons, listed in §6, each with the instrument that closes it.

---

## 1. THE TABLE

Baseline measured: GPU **7.92 ms**, VRAM **6,241 MB**, working set **8.25 GB** (`_verify/20260815_d4_rescatter_220k.md`, `Profile(20260815_144921).csv`). Ceilings: 16.67 ms / **15,235 MB** measured RHI budget (not the 16,303 MiB nameplate) / 31.44 GB / 223.42 GB commit.

**`null` means no domain brief supplied a figure — distinct from 0, which means measured or ruled at no cost.**

| Subsystem | GPU ms | VRAM MB | RAM runtime | GameThread ms | Build commit | Basis |
|---|---:|---:|---:|---:|---:|---|
| **Terrain + vegetation (spent)** | **7.92** | **6,241** | **8.25 GB** | 8.88¹ | 196.8 GB peak | **measured** |
| Player character | **null**² | **null**² | **null**² | **null**² | — | **no design delivered** |
| Enemies, ≤12 visible, Significance-tiered | 1.10 | 600 | 0.3 GB | 3.0³ | — | proposed |
| Navmesh (one region, not the world) | 0.00 | 0 | 150 MB⁴ | 0.3 | **UNKNOWN** | derived from struct sizes |
| Physics: tree query collision + ragdoll | 0.10 | 0 | 0.1 GB | 1.5³ | — | proposed |
| Tree-chop swap (no GeometryCollection) | 0.10 | 100 | trivial | 0.2 | — | proposed |
| Encounters (data + no-tick markers) | 0.00 | 0 | trivial | 0.1 | — | derived |
| Quest / dialogue / save (data + UMG) | 0.20 | 100 | trivial | 0.3 | — | proposed |
| VFX | **null**² | **null**² | **null**² | **null**² | — | **no domain proposed any** |
| **Phase 2 allocated** | **1.50** | **800** | **~0.5 GB** | **5.4** | serialized | |
| **Held unallocated** | **7.25** | **8,194** | **22.6 GB** | — | **26.6 GB** | |
| **SUM** | **9.42 / 16.67** | **7,041 / 15,235** | **8.8 / 31.4 GB** | **14.3 / 16.67** | **196.8 / 223.4** | |

**Closes: GPU YES. VRAM YES. Runtime RAM YES — and stop calling it the constraint. GameThread NO, unclosable today. Build commit NO — serialized, not closed.**

¹ Editor-class, and 6.03 ms is Slate/editor UI absent from a shipping build, while gameplay/anim/AI/physics that will exist is not running. Two errors of opposite sign; not a budget.
² Retracted rather than estimated. The characters domain returned nothing and no brief proposed VFX; filling these cells would make an undesigned subsystem read as cheap.
³ Post-cut. At engine defaults AI alone is 8.0 ms (CUT 4). The physics brief stamps all four of its own rows UNMEASURED.
⁴ `DetourNavMesh.h` / `RecastNavMeshGenerator.cpp` struct sizes. `dtReal` is `double` here, so any remembered UE4 figure is ~2× low.

**GPU arithmetic:** 16.67 − 7.92 = 8.75 available. Allocate **1.50**, hold **7.25** against the shipping-class gap — the measured size of the unknown, since this project has never produced a PIE or packaged frame and `RECIPES.md:5889` calls it *"a different calibration class that does not exist."*

---

## 2. THE OVER-SPENDS, NAMED

**O1 — GameThread claimed twice over, on two incompatible baselines.** `ai-enemies`, `physics` and `pipeline` all quote GameThread 7.48 ms from `_verify/20260814_alpine8k_framecost.md` → "9.2 ms headroom". `budget` reads a newer CSV: 8.88 ms *of which 6.03 is Slate*. Against that imagined headroom, `ai-enemies` documents 5.0 ms of default sight budget (`AISense_Sight.cpp:139`) + 3.0 ms EQS (`EnvQueryManager.h:36`) — **8.0 ms before one enemy exists** — and `physics` proposes 2.0 ms on top.

**O2 — three unmeasured heavy builds, one 26.6 GB slot.** `ai-enemies` wants 64 navmesh chunk builds, cost explicitly unestimated. `towns` wants a `MESH_APPROXIMATE` HLOD build run alone under commandlet rendering, and flags that every `LandscapeTexturePatch` edit triggers an unmeasured Nanite rebuild. That rebuild already peaked at 196.8 GB of 223.42 GB. Only `budget` carried a build-memory column, so all three read as free.

**O3 — VRAM, ratcheting and unevictable.** `budget` measured non-streaming textures growing 846 → 978 MB across the forest campaign. `towns` proposes an architecture kit plus interiors; `assets-inventory` proposes MetaHuman (730 MB of engine content before one instance). Nobody was told the pool is 15,235 MB, not 16,303.

**O4 — `assets-inventory` over-corrected the ceiling and would have cut too deep.** It rules the budget is "the ruled 11 ms abort bar, not 16.67 — 3.08 ms of headroom". **Checked against the artefact: wrong.** `_verify/20260815_d4_rescatter_220k.md:7` sits under the heading *"D4 — the closure re-scatter, 219,659 instances"* and reads *"Abort bar **11 ms GPU** at `forest_floor`"* — a revert condition for one scatter operation, not a frame ceiling. Its consequences survive (MetaHuman needs an A/B first; a settlement station needs its own derived bar); its arithmetic does not.

**O5 — the denominator of every GPU number here is unrecorded.** `measure_frame_cost.py:38` does not record the viewport pixel size, and the CSV's `[systemresolution]` is the PIE window. 7.92 ms is a rate per unknown pixel count, and every allocation inherits that.

---

## 3. CONTRADICTIONS BETWEEN BRIEFS — checked against this install

**C1 — Is StateTree enabled? BOTH BRIEFS ARE HALF WRONG.** `assets-inventory` says `GameplayStateTree` is *"genuinely off"*; `pipeline` says StateTree et al. are *"enabled in this project by accident"* via `AllToolsets`; `ai-enemies` step 1 says add both to the `.uproject`. Read here:

- `LandscapeLab.uproject` → `{"Name": "AllToolsets", "Enabled": true}`
- `AllToolsets.uplugin` → `"IsExperimentalVersion": true`, `"NoRedist": true`, `"EditorOnly": true`; lists `StateTreeToolset` Enabled:true, `GASToolsets`, `GameplayTagsToolset`, `WorldConditionsToolset`, 21 in all
- `StateTreeToolset.uplugin` → `Plugins: [{"Name": "StateTree", "Enabled": true}]`
- `GameplayStateTree.uplugin` → `"IsBetaVersion": false`, v1.0, `"EnabledByDefault": false`; **`grep GameplayStateTree` across `Engine/Plugins/Experimental/Toolsets/` returns zero `.uplugin` hits**

**Ruling: `StateTree` IS enabled transitively today. `GameplayStateTree` — the AI-facing half — is not, and nothing pulls it in.** Two consequences neither brief drew: `grep -rn EditorOnly Engine/Source/Runtime/Projects/` returns **nothing**, so that key is inert and StateTree is enabled for runtime targets too; and the gameplay foundation currently rests on an **Experimental, NoRedist** aggregator. Adopt `pipeline`'s fix — a `LandscapeLabGameplay` project plugin with an explicit dependency list (`PluginManager.cpp:420-433`) — with `GameplayStateTree` named explicitly. Non-negotiable 17 exactly: the `.uproject` records overrides, never state.

**C2 — GameThread headroom: 9.2 ms or 2.85 ms?** Three briefs against one; both editor-class, neither valid. Different runs (D3 vs D4), so not a factual contradiction — but the interpretations are mutually exclusive and AI's whole allocation hangs on it.

**C3 — tree collision vs navmesh relevance.** `physics` rules `QUERY_ONLY` + `BlockAll` on the four tree species. `ai-enemies` rules collision *but not* nav relevance — `CustomNavigableGeometry = No` (`FoliageType.h:376-378`). **As written, `physics`' change causes exactly the 219,659-carve-out navmesh explosion `ai-enemies` rejects, silently, until the next build.** Both missed that `recipes/schema.md:468-474` already requires re-running the connectivity check against `world.min_connected_frac` when instances gain blocking collision.

**C4 — the skeleton.** `physics` P4 builds a ragdoll on `Content/Mannequin/.../SK_Mannequin_PhysicsAsset.uasset`, unaware of the UE5 skeletons `assets-inventory` located. That brief proves the folder is UE4-era by bone probe — `spine_04`, `spine_05`, `clavicle_out_l`, `index_metacarpal_l` all → 0, with `hand_l → 4` as the positive control — and rules `ASSETS.md:78` wrong for calling it the GASP retarget target. **`assets-inventory` wins on evidence; retarget to `SKM_Manny`.**

**C5 — PCG: use or reject?** `towns` rules it in (`PCG.uplugin` → `"EnabledByDefault": true`, `"IsBetaVersion": false`, v1.0 — confirmed). `pipeline` rejects it for encounter placement. Reconciled by `towns`' own sentence, promoted to a project rule: **PCG fills what a recipe has already placed; it never decides placement.** `PCGPythonInterop` is already in the `.uproject`.

**C6 — rendered vs collided ground.** `towns` says "up to ~0.8 m"; the record carries collision quantization max 0.431 m and displacement peak 0.4 m. **0.8 is the sum of two independent numbers presented as one measurement**, and neither has been measured as a divergence on Alpine8K. `towns`' real contribution is different and valuable: `r.Landscape.AllowNanitePerClusterDisplacementDisable` defaults 1 (`LandscapeRender.cpp:223-231`), so the divergence is **camera-distance dependent** — which is why every grounding instrument here, all reading the heightmap or the plan, would pass a town whose walls float.

**C7 — a dead config key, correctly caught.** `BaseEngine.ini:3048` sets `MaxTileGridWidth=256`; `grep -rn MaxTileGridWidth Engine/Source` returns **nothing**. A dead key that reads as a fatal 2560 m navmesh cap. `ai-enemies` was right.

**C8 — one domain returned nothing.** The **characters** brief delivered no content. The domain owning the largest untested GPU and GameThread cost — skinned meshes, anim graphs, IK, cloth, retarget — produced no design and no numbers, and three other briefs partially filled the vacuum incompatibly (`physics` targeted the UE4 Manny; `assets-inventory` recommends MetaHuman Beta; nobody costed animation). **Do not proceed on the union of three partial guesses.**

---

## 4. THE CUTS

**CUT 1 — TOWNS ARE CUT AS A PLACEMENT ACTIVITY.** Three sufficient grounds: `WORLD_VISION.md:208` makes the contiguous-vs-multi-region ruling a tripwire on *any* placement work and it is unmade; the project owns **45 static meshes, 41 of them vegetation and rock, 3 a lookdev kit, 1 a template arrow** — there are no buildings; and its HLOD build takes a slot the binding budget lacks. **Survives:** the schema, the Level-Instance + three-data-layer structure, one `ALandscape::CreateLayer` `UFUNCTION` in `LandscapeLabEditor` (`Landscape.h:431`, absent today), grey-box blockout in `/Game/Scratch`. **Releases ~1.8 ms GPU, ~2.6 GB VRAM, one build slot.**

**CUT 2 — METAHUMAN IS CUT FROM PHASE 2.** `"IsBetaVersion": true`, 730 MB, and the brief recommending it states *"zero GPU measurements exist for any character asset."* Use `SKM_Manny`/`SKM_Quinn` from `Engine/Templates/TemplateResources/High/Characters/` — UE5 skeleton bone-verified, ~110 animations including `MM_Attack_01/02/03`, six directional deaths, eight hit reacts, three Control Rigs, free under the EULA already in use. Re-opens on one measured spawn-N A/B.

**CUT 3 — CHAOS FRACTURE IS CUT.** `GeometryCollectionPlugin.uplugin` confirmed `"IsBetaVersion": true`, v0.1, `EnabledByDefault: false`. Tree-chop uses the swap path instead: `OnInstanceTakeRadialDamage` (`InstancedFoliage.cpp:5866`, resolving via `GetInstancesOverlappingSphere` — **no physics bodies required**) → remove instance → one short-lived rigid trunk → despawn on sleep. Zero plugins.

**CUT 4 — AI PERCEPTION AND EQS ARE CUT BY CONFIG BEFORE ONE ENEMY EXISTS.** The cut nobody proposed, because the engine takes it by default. `MaxTimeSlicePerTick` 5 → 2 ms; `MaxAllowedTestingTime` 3 → 1 ms; `MaxTracesPerTick` 6 → 24 so the time slice is the limiter; `HighImportanceQueryDistanceThreshold` 300 uu → 1500 (3 m is an indoor number — nothing is ever high-importance and the priority queue idles). **8.0 → 3.0 ms.** Encounters capped at ≤12 simultaneous against `UCrowdManager::MaxAgents = 50` (`CrowdManager.cpp:168`).

**CUT 5 — NAVMESH CUT TO ONE REGION; ONE CHUNK BUILT FIRST.** 259,081 tiles, ~1.0 GB on disk, 64 builds, cost unestimated, on a machine at 88% commit occupancy. Build one chunk, measure bytes/time/peak RAM, then decide. Its four default fixes are ratified and free: `DataGatheringMode=Lazy` (under `Instant` the whole 66,080,641-vertex collision heightfield is triangulated up front), `MaxSimultaneousTileGenerationJobsCount` 1024 → 16, `NavigationDataBuilderLoadingCellSize` 4096 → 1024 m, `MinRegionArea` 0 → 400, with `TileSizeUU=1600` which divides `NavigationDataChunkGridSize` exactly.

**CUT 6 — TREE NAV RELEVANCE CUT PERMANENTLY; QUERY COLLISION KEPT.** One recipe declaration: `QUERY_ONLY` + `BlockAll` + `CustomNavigableGeometry = No`, plus the `schema.md:468-474` connectivity re-run **in the same commit**. Never on `Meadow`/`Blueberry` — `LandscapeGrass.cpp:3170-3172` hard-codes `NoCollision` + `bDisableCollision = true`, so asking is a silent no-op, worse than a refusal.

**CUT 7 — QUEST AUTHORING CUT UNTIL THE OWNERSHIP DEFECT IS FIXED.** `owner_quest` asserts a quest owns every blackboard key, but triggers, combat and NPC death write most world facts. Fix the schema (`writers: []`, namespaced `quest:`/`world:`/`system:`) first. Cost of the fix: one field. Cost of ignoring it: every quest.

**CUT 8 — RATIFIED, NO BUDGET LINES.** Mover and ChaosMover (both `"IsExperimentalVersion": true`; rollback networking buys nothing for a confirmed single-player game), `p.AsyncCharacterMovement`, substepping, async physics tick, Chaos Vehicles, `FieldSystemPlugin`, `ChaosCaching`, `ApexDestruction` (`UE_DEPRECATED(4.26)`), destructible terrain, per-tree GeometryCollections, `UseComplexAsSimple` on foliage, raising `SimpleCollisionMipLevel`, and Mass in all forms (`MassGameplay`/`MassAI`/`MassCrowd`, Experimental v0.4).

---

## 5. BUILD ORDER — *scope extension, not one of the four requested outputs; discardable without loss*

1. Re-run the characters domain — it returned nothing and three briefs fill the gap incompatibly.
2. A player exists. `DefaultEngine.ini:3-4` sets only `GameDefaultMap`; no `GlobalDefaultGameMode`, no default pawn, and `/Game/Alpine8K` has never been played. Walkable angle from `terrain_erosion.MOVEMENT_PROFILES` (`mount` 35°, matching `world.primary_movement_mode`), **not** CMC's 44.765083° default.
3. Offline step-height audit: fraction of the `mount` mask whose 1 m neighbour rise exceeds `MaxStepHeight = 45 cm`. No editor, minutes.
4. **The PIE capture.** `forest_floor` control (must reproduce 7.92 ±0.2), a 250 m elevated station inside the cull radius, a 1500 m airship station. Record viewport pixel size; enable `CsvCategory VSM 1` and `GPUScene 1`; the discriminating field is `VSM/SinglePageCount` + `FullCount` against the 2048-page pool, not GPUTime. This converts the whole historical record and is the precondition for every GameThread figure above being more than a proposal.
5. Measure tree `body_setup` live — `measure_tree_packs.py` has no collision field, and `collision_prims` derives from the registry tag scan already DO-NOT-CONSUME for `material_slots` on 23 of 38 meshes.
6. Tree collision, one declaration, with the connectivity re-run.
7. `LandscapeLabGameplay` plugin; verify on a **cold boot**.
8. Navmesh: one chunk, behind a restore point named for the operation. Measure. Then decide.
9. Encounter planner, reusing `placement_priors.py` and `place_foliage.py`'s plan → adopt → orphan-sweep shape; gated on navmesh projection, a collision-derived representation that corroborates `traversability()`'s heightmap rather than agreeing with it.
10. One StateTree enemy archetype, then death ragdoll.

---

## 6. WHAT IS UNKNOWN, AND WHY — each with the instrument that closes it

| Item | Reason it is unknown | Instrument |
|---|---|---|
| Every figure's calibration class | This project has produced no PIE or packaged frame; `RECIPES.md:5889` records the reading as owed | one PIE capture at a matched camera and recorded resolution (§5 step 4) |
| Player character and VFX budgets | The characters domain returned an empty brief; no domain proposed VFX | re-run the domain, then a spawn-N A/B against the `forest_floor` series |
| Navmesh build wall-clock and peak commit; HLOD build commit; Nanite rebuild cost per patch edit | No such build has ever run in this project | build one navmesh chunk, timed, with `resource_guard.py` logging free RAM first |
| Tree meshes' simple collision primitives | The instrument does not exist — `measure_tree_packs.py` records no collision field, and `collision_prims` comes from the registry tag scan already discredited for `material_slots` | extend it to read the loaded mesh's `body_setup` aggregate geometry |
| Whether `/Game/Alpine8K` holds any `ULandscapeLayerInfoObject` | No script creates one and the level was not opened this session | one live read of the landscape's `LandscapeLayerInfoObjects` |
| Whether a Python write to `collision_profile_name` applies the profile | Held as inference in the physics brief, correctly | a world line trace against a placed instance after the write |

I connected to no editor, launched nothing, and wrote no file. Every citation above is a plugin descriptor, an engine source line, a repo artefact, or a filesystem listing read in this session.