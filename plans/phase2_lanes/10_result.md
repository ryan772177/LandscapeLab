# PHASE2_PLAN.md

*Written 2026-08-15. Synthesised from eight domain briefs, one budget reconciliation and one adversarial completeness critic. **Where a brief and the reconciliation or critic disagreed, the reconciliation or critic won**; each such override is marked `[OVERRULED]` with its one-line reason.*

---

## 1. BOTTOM LINE

**Phase 2 is: the world becomes playable.** A player pawn that walks on the terrain, trees that stop him, a navmesh he shares with enemies, encounters placed by recipe on the difficulty gradient `WORLD_VISION.md:280` already defines, and one enemy archetype that fights. **The first thing to build is not a feature — it is one PIE capture at a recorded resolution**, because every performance number this project owns was taken in an editor viewport with Slate running, all 256 proxies force-resident and no gameplay ticking, and four variables change sign at once the moment a player exists. **The single biggest risk is that the binding budget is the game thread, not the GPU, and it cannot be closed today**: GPU has 8.75 ms free against a measured 7.92 ms spend, but AI perception and EQS at engine *defaults* claim 8.0 ms of game thread before one enemy exists, and no PIE reading exists to say what the real headroom is. Towns, MetaHuman, Chaos fracture and world-scale navmesh are **cut from Phase 2** — towns because `WORLD_VISION.md:208` makes an unmade ruling a tripwire on all placement work and the project owns zero building meshes (45 static meshes on disk, 41 of them vegetation and rock). What is *not* blocked is large: UE 5.8 ships, free and already on this disk, a complete UE5 Manny/Quinn with ~110 animations and a 207-asset StateTree combat template, so characters and enemy AI cost acquisition nothing. **Four things are unknown for stated reasons, each with its instrument in §5:** no navmesh has ever been built here, so all navigation memory and build-cost figures are derived from struct sizes; the tree meshes' collision primitives are unread because no instrument records them; the characters domain returned an empty brief; and no PIE or packaged frame has ever been produced by this project.

---

## 2. THE RULINGS

Settled. Do not re-litigate; if you disagree, overturn it with a measurement and log the supersession.

**Engine and plugins**

1. **`StateTree` is already enabled here; `GameplayStateTree` is not.** `LandscapeLab.uproject` → `AllToolsets` (Enabled: true) → `StateTreeToolset` → `StateTree`. Nothing pulls in `GameplayStateTree` (`EnabledByDefault: false`, `IsBetaVersion: false`, v1.0), and that is the half carrying `StateTreeAIComponent`, `FStateTreeMoveToTask`, `FStateTreeRunEnvQueryTask`. `[OVERRULED]` — `ai-enemies` said both were missing and `pipeline` said both were enabled; each was half right.
2. **Gameplay plugins are enabled through a `LandscapeLabGameplay` project plugin with an explicit dependency list, never by editing `.uproject`.** Standing rule 4 forbids the direct edit and `PluginManager.cpp:420-433` honours `EnabledByDefault` on a project plugin unconditionally. `[OVERRULED]` — `ai-enemies` §9 step 1 proposed the `.uproject` edit; the project's own guard has already refused exactly that once and produced a better design.
3. **`AllToolsets` is Experimental and `NoRedist`; the gameplay foundation must not rest on it.** Adopt ruling 2 and stop depending on the aggregator. `[OVERRULED]` — `pipeline` reported `"EditorOnly": true` as engine-wide inert after a C++-only search; the filtering is C# (`AutomationTool/AutomationUtils/DeploymentContext.cs:580`, `UnrealBuildTool/.../PluginDescriptor.cs`), so the zero came from the wrong path. That is the `LandscapeNanite.cpp` near-miss again.
4. **Behaviour is StateTree on `AAIController`. Mass is rejected.** `MassGameplay`, `MassAI`, `MassCrowd` are all `IsExperimentalVersion: true` at v0.4; `UCrowdManager::MaxAgents = 50` (`CrowdManager.cpp:168`) already exceeds any encounter this game will have.
5. **Movement is `UCharacterMovementComponent`. Mover and ChaosMover are rejected.** Both `IsExperimentalVersion: true`; Mover's own README declares two core subsystems mid-replacement, its dependency array force-enables Water (Experimental), and its purpose is rollback networking on a **confirmed single-player** game (`WORLD_VISION.md:178`).
6. **PCG is production-tier and admitted, but it fills what a recipe has already placed — it never decides placement.** `PCG.uplugin`: `EnabledByDefault: true`, `IsBetaVersion: false`, v1.0.
7. **Chaos fracture is cut.** `GeometryCollectionPlugin` is `IsBetaVersion: true`, v0.1, off by default. Tree-chopping uses `OnInstanceTakeRadialDamage` (`InstancedFoliage.cpp:5866`), which resolves instances by bounds query and needs no physics bodies at all.

**Budget**

8. **The frame ceiling is 16.67 ms, not 11 ms.** `[OVERRULED]` — `assets-inventory` read the 11 ms in `_verify/20260815_d4_rescatter_220k.md:7` as a frame budget; it sits under the heading *"D4 — the closure re-scatter"* and is a **revert condition for one scatter operation**. Its consequences survive (a character A/B before MetaHuman; a settlement station needs its own derived bar); its arithmetic does not. 11 ms is retained as a **tripwire at `forest_floor` only**, because it is the one bar Ryan has actually ruled there.
9. **Every existing frame-cost figure is editor-class and none may be compared into PIE.** `RECIPES.md:5889` already calls PIE *"a different calibration class that does not exist"*. Stamp the class on every artefact.
10. **VRAM ceiling is 15,235 MB (measured RHI budget), not the 16,303 MiB nameplate.**
11. **The binding budget is build-time commit, not runtime anything.** 196.8 GB peak of a 223.42 GB limit leaves 26.6 GB, and navmesh, HLOD and post-patch Nanite rebuilds each want the whole slot. Heavy builds run **alone**, serialized, with `resource_guard.py` first.
12. **All per-domain millisecond allocations in the briefs are PROPOSED, not measured.** They were written in D3/D4's abort-bar format and read like rulings. Only the totals in §6 are load-bearing.

**World and content**

13. **Towns are cut as a placement activity for Phase 2.** Three sufficient grounds: the contiguous-vs-multi-region tripwire (`WORLD_VISION.md:208`) is unmade; there are no building meshes (`KiteDemo/LevelContent/Architecture/` is `SM_1Meter_01`, `SM_AssetPlatform_02`, `SM_CycRoom_01` — a photo-studio lookdev kit, verified); and an HLOD build takes the one build slot §2.11 says we do not have. **Surviving:** the settlement schema, the Level-Instance + three-data-layer structure, and grey-box blockout in `/Game/Scratch`.
14. **MetaHuman is cut from Phase 2.** `MetaHumanCharacter.uplugin`: `IsBetaVersion: true`, 730 MB, and zero GPU measurements exist for any character asset in this project. Use `SKM_Manny` / `SKM_Quinn` from `Templates/TemplateResources/High/Characters/Content/Mannequins/`.
15. **The character skeleton is UE5, not the UE4 mannequin in `Content/Mannequin/`.** Bone probe: `spine_04`, `spine_05`, `clavicle_out_l`, `index_metacarpal_l` all return 0 on `UE4_Mannequin_Skeleton.uasset` with `hand_l → 4` as the positive control. `ASSETS.md:78` calling it the GASP retarget target is **wrong**. `[OVERRULED]` — `physics` P4 built its ragdoll design on that asset.
16. **Trees get `QUERY_ONLY` + `BlockAll` collision AND `CustomNavigableGeometry = No`, in one recipe declaration, with the `recipes/schema.md:468-474` connectivity re-run in the same commit.** `[OVERRULED]` — `physics` ruled collision and `ai-enemies` ruled nav-irrelevance separately; as written, `physics`' change alone triggers the 219,659-carve-out navmesh explosion `ai-enemies` rejects, silently, until the next build.
17. **Grass and blueberry can never collide and nothing should ask.** `LandscapeGrass.cpp:3170-3172` hard-codes `NoCollision` + `bDisableCollision = true`. Berry-picking is a non-physics query against the same deterministic data the grass system uses.
18. **Navmesh is statically built and World-Partition-chunked, never runtime-invoker-generated.** Invokers require runtime voxelisation of a 66,080,641-vertex collision heightfield and destroy reproducibility.
19. **Walkable slope is declared once and derived twice.** `terrain_erosion.MOVEMENT_PROFILES` already carries the engine's own 44.765083° (`CharacterMovementComponent.cpp:682, :7034-7035`); `recipes/alpine_8k.json` → `world.primary_movement_mode` is `"mount"` at 35°. `AgentMaxSlope` derives from it and is gated to never exceed it. Non-negotiable 19 and 24 verbatim.
20. **The encounter density field is the foothill→peak arc, as a gradient, never uniform.** `WORLD_VISION.md:280` states it; D4 already ruled uniformity is as much the defect as the count.
21. **The quest blackboard's ownership model is wrong and is fixed before any quest is authored.** `owner_quest` asserts a quest owns every key; triggers, combat and NPC death write most world facts. Replace with `writers: []`, namespaced `quest:` / `world:` / `system:`. Cost of the fix: one field. Cost of ignoring it: every quest.

---

## 3. WHAT WE ALREADY HAVE

**The world.** `/Game/Alpine8K` — 8129², 1 m/vertex, 8.128 km square, 66,080,641 vertices, World Partition, 256 proxies / 1024 components, Nanite built on 256/256, Lumen on, exposure solved at −1.923 EV. **219,659 tree instances in four tiers** (Conifer 63,981 · ConiferPine 47,261 · SpruceSub 55,004 · SpruceSapling 53,413) plus grass and blueberry understory. Measured cost **GPU 7.92 ms, VRAM 6,241 MB, working set 8.25 GB** at `forest_floor`, editor-class (`_verify/20260815_d4_rescatter_220k.md`).

**The pipeline.** 114 Python scripts, recipe-first, idempotent, with an offline verification suite that runs with no editor (`prove_gates.py`, `verify_grounding.py`, `check_collision_truth.py`). A C++ editor plugin at `LandscapeLab/Plugins/LandscapeLabEditor`. `PROJECT_STATE.json` machine-recovered. The reusable shape for everything in §5: plan → adopt → orphan-sweep, seeded, gated, positive-controlled.

**Placement machinery that transfers directly.** `placement_priors.py` (flow, canopy occupancy via cKDTree, `centred_bias`, `closure_ramp`), `rock_scatter.plan_species` / `role_mask`, `terrain_erosion.traversability()` (per-movement-profile connected components — the instrument that detects "a thousand isolated shelves"). An encounter is foliage scatter with a different payload.

**Content on disk — 15.9 GB, and it is all environment.** KiteDemo 6.5 GB (11 rock sets, 1 cliff, 6 trees, 7 foliage sets, 10 ground tiles — including `ForestPath_001`, `RockyPath`, `GravelTile_01`, unspent, for the inter-massif corridor). Fab/Megascans 1.8 GB. Megaplant 1.9 GB, PN_interactiveSpruceForest 1.5 GB (21 StaticMesh spruces + 7 imposters), GV_FreeShrubsPack 1.4 GB, PN_WildBerries 635 MB, StampIt 920 MB. **45 static meshes project-wide, 41 vegetation and rock, 3 lookdev, 1 template arrow. Zero Niagara assets. Zero sound assets. Three Blueprints, all vendor.**

**Free in the engine install, EULA-covered, unlisted anywhere in this project.**

| Thing | Path under `C:\Program Files\Epic Games\UE_5.8\` | What it is |
|---|---|---|
| UE5 Manny / Quinn | `Templates/TemplateResources/High/Characters/Content/Mannequins/` | `SKM_Manny_Simple`, `SKM_Quinn_Simple`, `SK_Mannequin` (UE5 skeleton, bone-verified), `PA_Mannequin`, three Control Rigs |
| ~110 animations | same, `Anims/{Unarmed,Death,Rifle,Pistol}` | 8-way walk + jog, jump/fall/land, `MM_Attack_01/02/03`, `MM_ChargedAttack`, 6 directional deaths, 8 hit reacts |
| StateTree combat template | `Templates/TemplateResources/Standard/Variant_Combat/` | **207 uassets**: `ST_CombatEnemy`, `BP_CombatEnemy`, `BP_CombatAIController`, `BP_Combat_EnemySpawner`, 9 StateTree tasks/conditions, 4 EQS queries, damage interfaces |
| Grey-box kit | `Templates/TemplateResources/High/LevelPrototyping/` | the correct way to block out a settlement before buying architecture |
| One more UE5 Manny | `LandscapeLab/Content/GV_FreeShrubsPack/Demo/Mannequin/` | 184 MB, uncatalogued, gitignored — **no `ASSETS.md` row** |

**A ragdoll asset exists**: `Content/Mannequin/Character/Mesh/SK_Mannequin_PhysicsAsset.uasset` — UE4-era, against the wrong skeleton per ruling 15, but it exists.

---

## 4. WHAT MUST BE ACQUIRED OR AUTHORED

Ranked by how blocking it is.

| # | Item | Blocking | Acquire or author | Note |
|---|---|---|---|---|
| 1 | **A player** — GameMode, pawn, `UInputMappingContext` + `UInputAction` set | **Everything.** Nothing below is testable without it | author | `DefaultEngine.ini:4` sets only `GameDefaultMap`; **no `GlobalDefaultGameMode`, no default pawn, and `/Game/Alpine8K` is not the default map** — a cook today ships Epic's template world. `DefaultInput.ini:79-80` sets the EnhancedInput classes but declares **zero mappings** |
| 2 | **The characters domain brief** | Skeleton choice, retarget, anim budget, LOD policy | re-run the domain | It returned one sentence. Three other briefs filled the vacuum incompatibly. Do not proceed on the union of three partial guesses |
| 3 | **A tree-collision instrument** | Ruling 16 | author (~1 session) | `measure_tree_packs.py` records no collision field; `collision_prims` in the recipe comes from the asset-registry tag scan already DO-NOT-CONSUME for `material_slots` on 23 of 38 meshes. Extend it to read the loaded mesh's `body_setup` |
| 4 | **`ALandscape::CreateLayer` as a `UFUNCTION`** in `LandscapeLabEditor` | Any non-destructive terrain edit (roads, town pads) | author (small) | `Landscape.h:431`, no `UFUNCTION` today. Convention already set: `void` + `bOutSuccess`, never `bool` + out-params |
| 5 | **Modular architecture kit** — walls, roofs, doors, windows, stairs as snapping pieces | Towns, and only towns (cut from Phase 2) | **acquire — the only thing that must be bought** | No fallback anywhere on this machine or in the engine. A ~40-part kit is data a recipe can place; a hero building is a hand-placement the pipeline cannot reproduce. `BACKLOG.md:238` already carries "Medieval Village" |
| 6 | Creatures / non-human enemies | Enemy variety, not enemy existence | acquire later | Manny is the stand-in. Do the Paragon retarget when a specific creature needs it, not speculatively |
| 7 | Props / set dressing | Towns and POIs | acquire later | Deferred with towns |
| 8 | VFX, audio | Nothing in Phase 2 | author later | Zero of each on disk. Footstep audio has a hard dependency on the surface-type query (§5 unit 11) — it is not independent |

**Rejected acquisitions, with reasons:** Paragon-first (UE4-era, needs 4.27 → migrate → retarget with chain mappings `ASSETS.md:119-135` marks `VALUE UNVERIFIED`; the engine already ships a larger combat set on a modern skeleton; `ASSETS.md:136-140` flags its stylised look against ruling 5's photoreal lane). The 1,374 GASP-shaped FBX in `Free/_intake` (`animations.json` records `"licence_or_readme_files_present": 0`; Epic's own Game Animation Sample is strictly better and carries a licence).

---

## 5. THE SEQUENCE

Ordered so the cheap measurements that could invalidate later work come first. Units 1–4 buy or destroy the premises of units 5–12 and together cost about two sessions.

### PHASE A — measure before building

**Unit 1 — The PIE capture.** *No authoring. ~15 min of editor time.*
Three stations on `/Game/Alpine8K`: `forest_floor` as control (must reproduce 7.92 ± 0.2), a **250 m elevated station inside the 730 m cull radius** where ~167 ha of forest is simultaneously in-cull and unoccluded, and a **1500 m airship station**. Streaming live, **not** force-resident. Enable `CsvCategory VSM 1` and `CsvCategory GPUScene 1` (both default-OFF, `VirtualShadowMapArray.cpp:104`, `GPUScene.cpp:48`). **Record the viewport pixel size** — `measure_frame_cost.py:38` does not, and it is the denominator of every GPU number this project owns.
**Acceptance:** a `_verify/` artefact carrying GPU / RenderThread / **GameThread** / VRAM / `SceneCulling/NumStaticInstances` at all three stations, with resolution recorded and calibration class stamped. **The discriminating field is `VSM/SinglePageCount` + `VSM/FullCount` against the 2048-page pool, not GPUTime** — page saturation and instance count produce the same frame time and lead to opposite work.
**Why first:** it converts the entire historical record and is the precondition for every game-thread figure in §6 being more than a proposal. If the elevated station exceeds 11 ms, D4's 219,659 gets re-derived before any other domain is allocated a millisecond.

**Unit 2 — Offline step-height audit.** *No editor. Minutes.*
Over the heightmap: fraction of the `mount`-profile mask whose 1 m neighbour rise exceeds `MaxStepHeight = 45 cm` (`CharacterMovementComponent.cpp:689`).
**Acceptance:** a number, recorded, plus the same figure restricted to the inter-massif corridor.
**Why here:** if the corridor `WORLD_VISION.md:279` calls *"the primary traversal route"* is not walkable at 1 m/vertex, the fix is a terrain or `MaxStepHeight` decision, and it invalidates encounter and POI placement along it. Costs nothing to find out.

**Unit 3 — Read the tree meshes' collision primitives live.** *Extends `measure_tree_packs.py`.*
Read each species mesh's `body_setup` aggregate geometry from the **loaded** asset.
**Acceptance:** `Free/_measured/` gains a per-mesh collision record; `collision_prims` in the recipe is superseded by it with a note, exactly as `material_slots` was.
**Why here:** if the PVE spruce and pine have no simple collision primitive, `CreateAllInstanceBodies()` returns early (`InstancedStaticMesh.cpp:2876-2881`) and unit 6 silently does nothing. The fix is one authored capsule per trunk — **never** `UseComplexAsSimple`, which puts a 2,335-triangle trimesh in the query scene per instance.

**Unit 4 — Re-run the characters domain.** *Analysis, not build.*
Skeleton ruling, retarget chain, per-character animation and LOD budget, root-motion policy.
**Acceptance:** a brief that cites its skeleton by bone probe and proposes a measurable per-character cost. **Blocking:** units 5 and 12.

### PHASE B — the player exists

**Unit 5 — A player walks on the terrain.**
`recipes/character.json` as the single declaration: capsule, `MaxWalkSpeed`, `MaxStepHeight`, and **walkable angle derived from `MOVEMENT_PROFILES`, not the CMC default** (ruling 19). A GameMode, an `ACharacter` on `SKM_Manny`, a spawn point traced onto the collidable surface, an `UInputMappingContext` with mappings generated from the recipe. Set `GlobalDefaultGameMode` and make `/Game/Alpine8K` the default map.
**Acceptance:** walk 1 km along the inter-massif corridor without falling through and without a step-height stall, trace log kept; **and** `verify_walkable_profile.py` proves the CMC CDO, `recipes/character.json` and `terrain_erosion.MOVEMENT_PROFILES` have not drifted (three places, one declaration).

**Unit 6 — Trees stop him.**
One recipe declaration on the four instance species: `collision_enabled = QUERY_ONLY`, `collision_profile_name = BlockAll`, `CustomNavigableGeometry = No`. The `schema.md:468-474` connectivity re-run against `world.min_connected_frac` **in the same commit**.
**Acceptance:** `LIST ISM PHYSICS` in PIE reports non-zero bodies **and** a world line trace hits a trunk — a different representation from the property read, because `FBodyInstance::SetCollisionProfileName` calls `LoadProfileData` and a reflected property write probably bypasses it (inferred, not tested; the trace settles it either way). Plus: an all-regions editor load with collision on must be **refused**, or the editor instantiates 219,659 static bodies the runtime never sees.
**Note:** at the World Partition default `LoadingRange = 25600` cm (`WorldPartitionRuntimeSpatialHash.h:232`), roughly **1,360 trees are resident**, not 219,659. That is what makes this cheap, and it is derived from engine defaults — this level's actual grid values are unread.

**Unit 7 — `LandscapeLabGameplay` plugin.**
Project plugin, `EnabledByDefault: true`, explicit dependencies including `GameplayStateTree`.
**Acceptance:** verified on a **cold boot** — the file records an override, never the state in effect. Three different ini files have bitten this project on exactly that.

### PHASE C — navigation and encounters

**Unit 8 — Build ONE navmesh chunk. Measure. Then decide.**
Tag a restore point named for the operation first; this writes external actor packages and is inside THE RISKY-OP CHECKPOINT. Config, all of it a departure from defaults and each one load-bearing:

| Key | Default | Set | Why |
|---|---|---|---|
| `DataGatheringMode` | `Instant` | **`Lazy`** | under `Instant` the whole 66.6M-vertex collision heightfield is triangulated up front (`NavigationOctree.cpp:201`; the sliced landscape path at `RecastNavMeshGenerator.cpp:2204` is lazy-only) |
| `TileSizeUU` | 1000 | **1600** | 812800/1600+1 = 509; 509² × 1.5 = 388,622 tiles, under the 1,048,576 hard limit. And 102400 / 1600 = **64 exactly**, so chunk actors do not straddle tiles |
| `AverageLayersPerTile` | 3.0 | 1.5 | no overhangs, caves or multi-storey structures |
| `MaxSimultaneousTileGenerationJobsCount` | 1024 | 16 | 1024 concurrent voxel heightfields on 24 cores is the Nanite-batch trap again |
| `NavigationDataBuilderLoadingCellSize` | 4096 m | **1024 m** | 4 km/iteration loads 64 landscape proxies plus ~55,000 trees; 31.4 GB cannot afford it |
| `MinRegionArea` | 0 | 400 | keeps the thousands of 1 m² alpine ledges out |
| `AgentMaxSlope` | 44.0 | derived (ruling 19) | drift upward is **silent** — the navmesh grants paths onto ground the character slides off |

**Acceptance:** package bytes on disk, wall clock, and peak commit logged by `resource_guard.py`, for one 1024 m chunk. **Abort:** > 200 GB peak commit or > 30 min. Note `MaxTileGridWidth=256` in `BaseEngine.ini:3049` is a **dead key** — zero hits across `Engine/Source`; reading it as a 2560 m cap is a false blocker.
**Also:** `bWholeWorldNavigable` is unreachable — its `UPROPERTY` is commented out at `NavigationSystem.h:371` with the engine's own *"currently broken"*. `ANavMeshBoundsVolume` actors are therefore mandatory, which makes the navigable region authored, versioned recipe data derived from `traversability()`'s largest walk-profile component.

**Unit 9 — Encounter planner.** *Offline, no editor.*
`recipes/encounters.json` → `scripts/plan_encounters.py` → `encounters/<region>_<archetype>.json`, same shape as `foliage/*.json`: absolute-cm transforms, seeded, idempotent. Density from the foothill→peak gradient (ruling 20). Exclude a corridor centreline band and the basins (settlement zones, blocked on Ryan's ruling — a mask, not hand-placed holes).
**Acceptance, two gates, both positive-controlled:** (a) **navmesh reachability** — project every encounter centre with `project_point_to_navigation` and refuse if its polygon is not in the same connected island as the player start. This must read the **built navmesh**, a collision-derived representation, so it *corroborates* `traversability()`'s heightmap rather than agreeing with it — this project rendered v2 and collided v1 for three days while every gate was green because every gate read the heightmap. Test `== SUCCESS` explicitly: `ENavigationQueryResult` is `INVALID=0, ERROR=1, FAIL=2, SUCCESS=3`, so truthiness inverts the gate. (b) **minimum separation** — Poisson-disc at aggro + leash radius, fed a deliberately overlapping pair first and proven to refuse.

**Unit 10 — Encounter markers stream; enemies do not.**
`AEncounterMarker` (`bIsSpatiallyLoaded = true`, no mesh, no tick, data only — one OFPA package each, like the foliage plans) + `UEncounterDirectorSubsystem` owning spawn/despawn with **hysteresis** (spawn radius < despawn radius, the shape `UNavigationInvokerComponent` already uses at `NavigationInvokerComponent.h:22-28`) + runtime-spawned pawns at `bIsSpatiallyLoaded = false`.
**Why:** a WP-streamed enemy is *destroyed* on cell unload and recreated fresh — health, aggro, patrol progress gone — and at 256 m range with a 3× mount that boundary is crossed constantly.
**Acceptance:** drive a streaming source across a chunk boundary at mounted speed in PIE with `wp.Runtime.ToggleDrawRuntimeHash2D` and `show Navigation`; **nav data must be resident before the marker on it**. Spawning must refuse when navmesh projection fails — an enemy on an unstreamed chunk stands still, which reads as an AI bug and is a streaming bug.

**Unit 11 — Surface type from the weightmap, CPU-side.**
A subsystem sampling a baked lookup derived from `textures/alpine_8k_weights.png` — the **same declaration the material reads** (non-negotiable 19), hashed into place per non-negotiable 20. Do **not** paint landscape layers to get this; it forks the surface definition.
**Acceptance:** positive control — the query agrees with the material's own layer choice at N sampled points.
**Caveat:** per-surface *walkability* is not achievable this way. `IsWalkable` reads `HitComponent->GetWalkableSlopeOverride()`, a **per-component** override, and one landscape component is 254 m square. "Scree is unwalkable" must be gameplay logic on top of the query.

### PHASE D — it fights

**Unit 12 — One StateTree enemy archetype + death ragdoll.**
`ST_CombatEnemy` as the reference implementation, on `SKM_Manny`, ≤12 simultaneous. **Cut AI config to size before the first enemy exists:**

| Property | Default | Set | Source |
|---|---|---|---|
| `AISense_Sight` `MaxTimeSlicePerTick` | **5.0 ms** | 2.0 | `AISense_Sight.cpp:139` |
| `MaxTracesPerTick` | 6 | ~24 | `AISense_Sight.cpp:46` — let the time slice be the limiter |
| `HighImportanceQueryDistanceThreshold` | **300 uu = 3 m** | ~1500 | `AISense_Sight.cpp:140` — 3 m is an indoor number; nothing is ever high-importance and the priority queue idles |
| EQS `MaxAllowedTestingTime` | **3.0 ms** | 1.0 | `EnvQueryManager.h:36` |

That is **8.0 ms → 3.0 ms** on the game thread. Adopt `USignificanceManager` (Production, v1.0) with the director in the same unit, not later. Death ragdoll on the UE5 `PA_Mannequin`: simulate, blend, **freeze on sleep** — a corpse that keeps simulating is 15+ bodies permanently in the solver.
**Acceptance:** `stat ChaosCounters` body count returns to baseline N seconds after death; GameThread at `forest_floor` with 12 enemies engaged stays within the §6 allocation.
**Pin explicitly and read back:** `p.RigidBodyNode` is `ECVF_Scalability` (`AnimNode_RigidBody.cpp:63`) — a scalability group can silently disable every ragdoll in the game. Nothing sets it today, and this project has been bitten three times by `sg.*` groups setting a value without running the group.

---

## 6. THE BUDGET

Baseline measured: **GPU 7.92 ms · VRAM 6,241 MB · working set 8.25 GB** (`_verify/20260815_d4_rescatter_220k.md`, `Profile(20260815_144921).csv`). Ceilings: 16.67 ms / **15,235 MB** measured RHI budget / 31.44 GB / 223.42 GB commit.

**`null` means no domain brief supplied a figure — distinct from 0, which means measured or ruled at no cost.**

| Subsystem | GPU ms | VRAM MB | RAM | GameThread ms | Build commit | Basis |
|---|---:|---:|---:|---:|---:|---|
| **Terrain + vegetation (spent)** | **7.92** | **6,241** | **8.25 GB** | 8.88¹ | 196.8 GB peak | **measured** |
| Player character | **null**² | **null**² | **null**² | **null**² | — | **no design delivered** |
| Enemies, ≤12 visible, Significance-tiered | 1.10 | 600 | 0.3 GB | 3.0³ | — | proposed |
| Navmesh (one region, not the world) | 0.00 | 0 | ~150 MB⁴ | 0.3 | **UNKNOWN** | derived from struct sizes |
| Physics: tree query collision + ragdoll | 0.10 | 0 | 0.1 GB | 1.5³ | — | proposed |
| Tree-chop swap (no GeometryCollection) | 0.10 | 100 | trivial | 0.2 | — | proposed |
| Encounters (data + no-tick markers) | 0.00 | 0 | trivial | 0.1 | — | derived |
| Quest / dialogue / save (data + UMG) | 0.20 | 100 | trivial | 0.3 | — | proposed |
| VFX | **null**² | **null**² | **null**² | **null**² | — | **no domain proposed any** |
| **Phase 2 allocated** | **1.50** | **800** | **~0.5 GB** | **5.4** | serialized | |
| **Held unallocated** | **7.25** | **8,194** | **22.6 GB** | — | **26.6 GB** | |
| **SUM** | **9.42 / 16.67** | **7,041 / 15,235** | **8.8 / 31.4 GB** | **14.3 / 16.67** | **196.8 / 223.4** | |

**Closes: GPU yes. VRAM yes. Runtime RAM yes — stop calling it the constraint. GameThread NO, unclosable until unit 1. Build commit NO — serialized, not closed.**

¹ Editor-class, and 6.03 ms of it is Slate/editor UI absent from a shipping build, while gameplay/anim/AI/physics that *will* exist is not running. Two errors of opposite sign; not a budget.
² Retracted rather than estimated. Filling these would make an undesigned subsystem read as cheap.
³ Post-cut. At engine defaults AI alone is 8.0 ms. The `physics` brief stamps all four of its own rows UNMEASURED.
⁴ `DetourNavMesh.h` / `RecastNavMeshGenerator.cpp` struct sizes. `dtReal` is `double` here, so any remembered UE4 figure is ~2× low.

**The 7.25 ms hold is not slack.** It is the measured size of the unknown: this project has never produced a PIE or packaged frame, and three of the four differences between the editor and the game make the frame *cheaper* while one makes it dearer, with the sum unknown. Unit 1 converts the hold into a real number.

### Abort bars

| Bar | Value | Applies to |
|---|---|---|
| **Frame tripwire at `forest_floor`** | **11.0 ms GPU** | any unit. It is 5.67 ms below the ceiling and is the one bar Ryan has actually ruled at that station. **It is a tripwire, not the budget** |
| Elevated 250 m station | **11.0 ms GPU** | unit 1. Above it, D4's 219,659 is re-derived before anything else is allocated |
| GameThread, all Phase 2 units combined | **+5.4 ms** over the PIE baseline unit 1 establishes | units 6, 8, 10, 12 |
| Tree collision | GameThread **+0.5 ms** at `forest_floor` | unit 6 |
| Navmesh, one chunk | **200 GB peak commit** or **30 min** wall clock | unit 8 |
| Enemies, 12 engaged | GameThread **+3.0 ms** | unit 12 |
| VRAM, all Phase 2 | **+800 MB** over 6,241 | all — non-streaming textures already ratcheted 846 → 978 MB across the forest campaign and are unevictable |
| Any heavy build | runs **alone**, `resource_guard.py` first | units 8 and any future HLOD or Nanite rebuild |

---

## 7. OPEN QUESTIONS FOR RYAN

Only decisions a measurement cannot settle.

1. **Contiguous world vs multi-region connected by airship.** `WORLD_VISION.md:190-208` — taken back from delegation, unmade, and an explicit tripwire on *any* placement work. It blocks settlements, POIs and the region-edge treatment. Your lean is recorded as multi-region; the analysis recommends Option A; **neither is a ruling.** Phase 2 as sequenced above deliberately touches nothing that depends on it.
2. **Buy a modular architecture kit — yes/no, and which one.** It is the only Phase-2-adjacent thing with no free fallback anywhere on this machine or in the engine (§4 item 5). Acquisition and placement are separable: buying now costs nothing but money and unblocks town work the moment question 1 is answered. `BACKLOG.md:238` carries "Medieval Village".
3. **Fab licence terms.** No non-`.uasset` file exists in any Fab pack, so terms are **not recoverable from disk** — including KiteDemo, on which the entire rock and cliff population depends. Five packs, 3.5 GB, have no `ASSETS.md` row, no licence record and no hash baseline. Only your Fab library page can close this.
4. **`DragonCave` (5,050 MB) and `Atlantis_Ruins` (3,369 MB) are recorded in `ASSETS.md:76-77` and are absent from every path I can read** — `LandscapeLab/Content/`, the untracked `LandscapeLab 5.8/` duplicate, `C:\Migration\`, `C:\Dev\`. They contain the project's only 12 creature skeletals. Were they deleted deliberately, and are they re-downloadable?
5. **Art direction for enemies.** Manny-as-everything is fine for prototyping. When creatures arrive, ruling 5's photoreal coherence filter applies and Paragon's stylised look is flagged as a risk (`ASSETS.md:136-140`). Your call on whether that filter is strict.
6. **Encounter scale.** How many enemies is a fight — 3, 6, 12? It sizes the AI budget, the director's hysteresis and `MaxAgents = 50`. No brief had a basis for a number; one of them guessed and the guess is withdrawn.
7. **Two world-reading questions `WORLD_VISION.md:297-298` leaves open, which the encounter planner would otherwise guess:** does the inter-massif corridor carry a **built road** or only a natural route, and is the treeline a **gameplay boundary** or purely visual?

---

## 8. WHAT THIS PLAN DOES NOT COVER

Stated plainly. Several are named by the completeness critic and are being deferred deliberately, not overlooked.

**Deferred with a reason:**

- **Towns, settlements, interiors, props.** Ruling 13. The schema survives; the placement does not happen until question 1 is answered and a kit exists.
- **MetaHuman.** Ruling 14. Re-opens on one measured spawn-N A/B against the `forest_floor` series.
- **Chaos fracture, destructible terrain, per-tree GeometryCollections.** Ruling 7. Terrain is a `Chaos::FHeightField` — there is no fracture representation for it at any cost, and deformable terrain would invalidate 219,659 placements and R-ALPINE8K.
- **World-scale navmesh.** Unit 8 builds one chunk. The other 63 are a decision, not a plan.
- **Quest and dialogue authoring.** Ruling 21 — the ownership defect is fixed first, and that is a design ruling about who owns world state, not a field rename. The next evidence comes from authoring a **second, chained** quest against the corrected schema, since chain gating is the structure the first authoring pass never exercised.
- **Mounts and the airship.** `WORLD_VISION.md:168` ruling 2c: encode the constraints, build nothing. Phase 2 honours that — mount speed sizes the streaming hysteresis and nothing else.

**Named by the critic, genuinely absent from this plan and from `BACKLOG.md`:**

- **Audio.** Zero assets on disk. Not blocking Phase 2 engineering; it blocks nothing *while the surface-representation decision in unit 11 is being made without it in the room*, which is the real coupling.
- **UI / HUD.** `DefaultGame.ini` opens with a `CommonUI` block inherited from a template in a project that has never shown a widget. The quest schema rests entirely on `title_key` / `summary_key` / `text_key` / `progress_bar` — every one a UI contract with no consumer designed.
- **Localisation.** No `Content/Localization` directory. The quest schema is correctly key-based and names no mechanism.
- **The gameplay camera.** No brief mentioned one; `Engine/Plugins/Runtime/Cameras` exists here and nobody opened it. **Every GPU figure this project owns was measured from a parked station at fixed FOV**, and a third-person spring arm with player yaw and a raised pivot yields a different frustum, Nanite cluster set and VSM page load. Unit 1 partially covers this by adding stations; it does not cover the camera *system*.
- **Save / load format.** Ruling 21 fixes the ownership model; the World Partition OFPA save architecture — actor identity across streaming, `FActorInstanceGuid` stability, a killed enemy in an unloaded cell — is unspecified and is the hardest Phase-2 data problem.
- **Cinematics.** `MovieRenderPipeline` is enabled. The airship region transition is *"a region transition behind a sky sequence"* — a cutscene requirement, ruled by Ryan, owned by no brief.
- **Cook and packaging.** Never attempted. `LandscapeLab.uproject` ships `AllToolsets` (Experimental, NoRedist), `MCPClientToolset` (Experimental, NoRedist), and a **remote-control web server** (`RemoteControl` + `RemoteControlWebInterface`) in its plugin array.
- **In-engine automated testing.** The 114-script offline suite covers none of the runtime. No functional test enters PIE and asserts anything — a doctrinal contradiction in a project whose rule is *a gate that has only seen good input has not been tested*.
- **Time-of-day lighting.** The entire lighting record is one 12° sun and one exposure solve. Any day/night work re-opens the budget, the exposure solve and the shadow instrumentation together.
- **Region-transition loading.** Nobody owns crossing between regions, which Option A makes the primary traversal mechanic.
- **VFX.** Zero Niagara assets; no domain proposed any; no budget line exists for them.

**One process defect worth fixing before the next round of briefs:** the domain-brief output contract mandated a field for unproven claims but had none for *"what is blocked on an unmade decision"*, which is how a settlement placer came to be designed confidently for work sitting behind Ryan's reserved ruling. Add `blocked_by_ruling`, nullable, and make the unproven-claims field nullable too — so a clean brief is not pushed to manufacture a gap. That is non-negotiable 18 landing on our own tooling.