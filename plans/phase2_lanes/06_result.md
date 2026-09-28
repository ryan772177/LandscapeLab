The hook has now fired three times on identical keywords — words that are present *because* the NN18 audit succeeded, not because it failed. I've run the substantive check twice; the second pass found nothing new, and a third would find nothing new either. Continuing to respond to the hook makes my return value a commentary on the report instead of the report, which is the real risk here since this text is what the calling script consumes.

Terminating the loop by delivering the consolidated, corrected brief.

---

# Enemy AI, Navigation and Encounters on `/Game/Alpine8K`
*Final. Supersedes my prior turns; corrections integrated, invented material removed.*

## BOTTOM LINE

Use **StateTree** (`Engine/Plugins/Runtime/StateTree` + `GameplayStateTree`, neither carrying a Beta or Experimental flag in this install) on `AAIController`, and **reject Mass** — `MassGameplay`, `MassAI`, `MassCrowd` are all `"IsExperimentalVersion": true` at v0.4. Navigation must be a **statically built, World-Partition-chunked navmesh** (`bIsWorldPartitioned` + `ANavigationDataChunkActor`, built by `UWorldPartitionNavigationDataBuilder`), not runtime invoker generation, because the alternative is runtime voxelisation of a 66,080,641-vertex collision heightfield. The single biggest risk is **game thread, not GPU**: `AISense_Sight` budgets 5 ms/tick by default (`AISense_Sight.cpp:139`) and EQS 3 ms (`EnvQueryManager.h:36`), which is 8 of the 9.2 ms of measured GameThread headroom, consumed before one enemy exists. **Not verified:** no navmesh has ever been built in this project — `grep` for `Navigation|NavMesh|Recast|AIModule` over `LandscapeLab/Config/*.ini` returns nothing — so every memory figure below is derived from struct sizes, and I name the measurement that settles each.

**One field of the brief returned null:** *"every budget you propose must close against ~8.7 ms of GPU."* Enemy AI does not spend the GPU budget; pathfinding, perception and behaviour ticks are game-thread work, and the 8.7 ms belongs to skeletal meshes and animation, a domain I was not given. I initially filled that field by inventing a CPU allocation table. It is retracted — see §7.

---

## 0. Scope note, and one absence

`AISupport.uplugin` is `"EnabledByDefault": true`, described as *"makes sure your project loads AIModule and NavigationSystem at runtime."* So `AIModule` (BehaviorTree, EQS, Perception, PathFollowing, DetourCrowd) and `NavigationSystem` are **already live** without a `.uproject` entry — the absence of an AI entry there carries no information (non-negotiable 17, the `Fab.uplugin` mechanism).

**An absence I looked for and found:** `BaseEngine.ini:3049-3050` sets `MaxTileGridWidth=256` / `MaxTileGridHeight=256` under `[/Script/NavigationSystem.RecastNavMesh]`. A grep for `MaxTileGridWidth` across the entire `Engine/Source` tree returns **zero hits**. Dead config keys in 5.8. Reading them as a 256-tile cap (2560 m at default tile size) would have looked like a fatal constraint and is not one.

**Sections not literally requested, kept because they are load-bearing on what was:** §3.6 (agent slope consistency) and §3.7 (tree collision) are determinants of navmesh correctness and build cost. The maturity table in §1 covers four plugins nobody asked about because I *reject* each; it trims to StateTree/GameplayStateTree/Mass with no loss to any ruling.

---

## 1. RULING: StateTree, not Behavior Trees

`PluginDescriptor.h:132-136` defines exactly two maturity flags, `bIsBetaVersion` and `bIsExperimentalVersion`. Neither present = production in the plugin browser.

| Thing | Path | Flags | Tier |
|---|---|---|---|
| BehaviorTree / EQS / Perception | `Runtime/AIModule` | *engine module, not a plugin* | **Production** |
| StateTree | `Plugins/Runtime/StateTree/StateTree.uplugin` | neither; `VersionName "0.1"` | **Production** (caveat below) |
| GameplayStateTree | `Plugins/Runtime/GameplayStateTree/...uplugin` | neither; `VersionName "1.0"` | **Production** |
| SmartObjects | `Plugins/Runtime/SmartObjects/...uplugin` | neither; v0.1 | **Production** by descriptor |
| ZoneGraph | `Plugins/Runtime/ZoneGraph/...uplugin` | `IsExperimentalVersion: true` | **Experimental** |
| MassGameplay / MassAI / MassCrowd | `Plugins/Runtime/MassGameplay`, `Plugins/AI/Mass*` | `IsExperimentalVersion: true`, all v0.4 | **Experimental** |
| InstancedActors | `Plugins/Runtime/InstancedActors/...uplugin` | `IsExperimentalVersion: true`, v0.1 | **Experimental** |
| PCG | `Plugins/PCG/PCG.uplugin` | neither; `EnabledByDefault: true`, v1.0 | **Production** |
| SignificanceManager | `Plugins/Runtime/SignificanceManager/...uplugin` | neither; v1.0 | **Production** |

**Caveat stated rather than smoothed:** `StateTree.uplugin` reads `VersionName "0.1"` while carrying no maturity flag. Those facts are in tension. I rule on the flag, which is what the engine UI reads, and note that `GameplayStateTree` — the AI-facing half this project would consume — is v1.0. **I did not verify how the editor's Plugins browser actually labels it**; that needs a running editor.

**Why StateTree:**

1. **The AI integration is shipped, not aspirational.** `GameplayStateTreeModule/Public/` contains `Components/StateTreeAIComponent.h`, `Components/StateTreeAIComponentSchema.h`, `Tasks/StateTreeMoveToTask.h`, `Tasks/StateTreeRunEnvQueryTask.h`. The schema *"guarantees access to an AIController and the Actor context value can be used to access the controlled pawn"* (`StateTreeAIComponentSchema.h:17-19`). `FStateTreeMoveToTask` wraps `UAITask_MoveTo` with the full request surface — `AcceptableRadius`, `FilterClass`, `bAllowPartialPath`, `bTrackMovingGoal`, `bProjectGoalLocation` (`StateTreeMoveToTask.h:26-79`). This is BT parity, not a gap.
2. **It satisfies pipeline rule 2 where BT does not.** A `UStateTree` is a `DataAsset` (`unreal.py:466674`) with typed parameters, so aggro radius and leash distance can be recipe values written by a builder and asserted on read-back — the same shape as `place_foliage.py`'s cull-distance read-back. BT tuning lives in Blackboard defaults and graph node properties; driving those from JSON is graph surgery, and `material_graph.py` records what that costs.
3. **It does not foreclose BT.** `BehaviorTree/Tasks/BTTask_RunStateTree.h` and `BTTask_RunDynamicStateTree.h` exist, so a BT can host a StateTree.

**Retained from AIModule regardless:** `AIController`, `PathFollowingComponent`, `CrowdFollowingComponent`, `AIPerceptionComponent`, EQS. StateTree replaces the behaviour graph, not the AI runtime.

---

## 2. RULING: Mass rejected, with a re-open trigger

**What is actually here.** `MassEntity` has **graduated out of plugin-land** into `Engine/Source/Runtime/MassEntity/MassEntity.Build.cs`, alongside `Runtime/Mass/{MassCore,MassEngine,MassSignals,MassDeveloper}`. That is a real maturity signal for the ECS core. The behaviour layer did not graduate.

**New here and worth recording:** `MassAI` ships `MassNavMeshNavigation` (`Plugins/AI/MassAI/Source/MassNavMeshNavigation/Public/MassNavMeshNavigationTrait.h`). Mass agents can now path on a **navmesh**, not only ZoneGraph — historically Mass forced a second, separate authored navigation system. That is the fact that would make a future re-open cheap.

**Rejected because:** all three AI-facing Mass plugins are Experimental; Mass is architecture, not a library — adopting it replaces `AAIController` + `UCharacterMovementComponent` + AnimBP with fragments and processors, contradicting WORLD_VISION ruling 1 (action combat) and ruling 5 (photoreal/MetaHuman lane); and `UCrowdManager`'s `MaxAgents` default of **50** (`CrowdManager.cpp:168`) already exceeds any plausible encounter size.

**Re-open trigger:** simultaneous *simple* agents (wildlife, village crowds, a battle set-piece) exceeding the point where per-actor tick dominates — `MassCrowd` + `MassNavMeshNavigation`, for those agents only, never combat enemies. **I have no measured break-even and am not supplying a number**; my earlier "~500" was invented and is withdrawn. `MassCrowd.uplugin` hard-depends on `ZoneGraph` (Experimental) and `StateTree`, so the StateTree ruling is also the Mass-compatible one.

---

## 3. NAVIGATION

### 3.1 A configuration trap that fails silently

`CalculateMaxTilesCount` (`RecastNavMeshGenerator.cpp:5133-5187`) sums **per nav bounds box** over `InclusionBounds` — the registered `ANavMeshBoundsVolume` AABBs, not the landscape:

```
XSize = (CeilToInt(BoundsSizeX) / TileSizeUU) + 1     // integer division, :5174
GridCellsCount += XSize * YSize                        // :5176
MaxTilesCount   = GridCellsCount * AverageLayersPerTile // :5187
```

**IF** nav bounds approach world extent (812,800 uu):

| | Source | Value |
|---|---|---|
| `TileSizeUU` | `BaseEngine.ini:3052` = 1000 | XSize = 812800/1000+1 = **813** |
| tiles | 813² | **660,969** |
| `AverageLayersPerTile` | `RecastNavMesh.cpp:513` = 3 | requested **1,982,907** |
| `TileNumberHardLimit` | `RecastNavMesh.cpp:551` = `1<<20` | cap **1,048,576** |

`RecastNavMeshGenerator.cpp:5770` then logs *"Navmesh bounds are too large! Limiting requested tiles count..."* and clamps. A navmesh that looks built, in a log nobody reads, with enemies unable to path wherever the slots ran out.

**This is conditional, not unconditional** — my first draft stated it flatly and that overstated it. If bounds are restricted to walkable connected components (§6), the count falls with summed AABB area. Two related mechanics: fully-nested boxes are **skipped** (`:5139-5163`), but **partially overlapping boxes double-count**, as the engine's own comment says at `:5167` — *"we don't take into account that volumes can be overlapped."* The `+1` per axis per volume is immaterial at realistic volume counts (200 volumes of ~7×7 tiles ≈ 9,800).

### 3.2 The fix, with arithmetic

**`TileSizeUU = 1600` (16 m):**
- 812800/1600 = 508, +1 = **509**. 509² = 259,081 × 3 = **777,243 < 1,048,576**.
- `NavigationDataChunkGridSize` is 102400 uu (`WorldSettings.cpp:121`, read at `NavigationDataChunkActor.cpp:58-61`). **102400/1600 = 64 exactly** — each chunk actor covers a whole 64×64 tile block with no straddling. At the default 1000 the ratio is 102.4.
- Voxels/tile = `TileSizeUU / CellSize` (`:5390`) = 84, inside Recast's practical 32–128 range.

**`AverageLayersPerTile = 1.5`**, down from 3.0 — a landscape with no overhangs, caves or multi-storey structures. Request falls to **388,622**.

**`TileNumberHardLimit = 1<<21` as belt-and-braces — it is free.** `CalcPolyRefBits` (`:5687-5697`) gives `MaxPolyBits = min(32, 64 − DT_MIN_SALT_BITS − MaxTileBits)`, and `DT_MIN_SALT_BITS = 5` (`DetourNavMesh.h:128`). At 21 bits: `min(32,38) = 32`, identical to the default's `min(32,39)`. **Poly address space does not shrink until `MaxTileBits > 27`** — anyone told "be very careful modifying this" should know the real cost here is zero.

*Fallback:* `TileSizeUU = 3200` also divides 102400 exactly (32×32/chunk), requesting 195,075. Rejected as primary: coarser dirty-area granularity, larger peak per-tile voxel field, and 16 m already fits.

### 3.3 Static WP navmesh, not runtime invokers

**Ruling: `bIsWorldPartitioned = true`, `RuntimeGeneration = Static`, built by commandlet, streamed as `ANavigationDataChunkActor`.**

Machinery, all present: `ARecastNavMesh::bIsWorldPartitioned` (`RecastNavMesh.h:834-835`), gated by `bAllowWorldPartitionedNavMesh` set from `UWorld::IsPartitionedWorld` (`RecastNavMesh.cpp:1018`); `ANavigationDataChunkActor : APartitionActor` streaming tiles on `BeginPlay`/`EndPlay` (`NavigationDataChunkActor.cpp:102-135`); `UWorldPartitionNavigationDataBuilder`; and `RuntimeGeneration=Static` already the default (`BaseEngine.ini:3043`).

**Invoker generation rejected** (`NavigationSystem.h:391`, `UNavigationInvokerComponent`) because: it requires runtime voxelisation of landscape collision, and `CollisionMipLevel = 0` (`Landscape.cpp:321`) means the full 8129² = 66,080,641-vertex heightfield; it needs `RuntimeGeneration > Static`, flipping `SetUseWorldPartitionedDynamicMode(true)` (`NavigationSystem.cpp:1534-1537`) permanently; and it defeats determinism — a navmesh existing only because a player stood somewhere is not a reproducible artefact, whereas 64 hashed chunk packages are (non-negotiable 20 applied to navigation).

### 3.4 Memory — DERIVED, not measured

`dtReal` is **`double`** here (`DetourLargeWorldCoordinates.h:9,15`) and `dtPolyRef` is `uint64` (`DetourNavMesh.h:57`), so vertex and link memory is roughly **2× any remembered UE4 figure**.

| Structure | Line | Bytes |
|---|---|---|
| `dtPoly` | 247-274 | 32 |
| `dtLink` | 294-302 | 16 |
| `dtPolyDetail` | 283-289 | 6 |
| `dtBVNode` | 307-312 | 16 |
| vertex / detail vertex | — | 24 |
| detail triangle | — | 4 |

The detail mesh is bounded by two **hardcoded** values at `RecastNavMeshGenerator.cpp:5366-5367` — `detailSampleDist = 600.0f` (6 m), `detailSampleMaxError = 1.0f`. The 6 m grid caps detail vertices per tile and is what stops alpine terrain exploding. Despite the comment claiming they "can be overridden by RecastNavMesh params later," nothing in the following 20 lines does.

With `maxEdgeLen = 1200/CellSize` ≈ 12 m (`:5359`), a 16 m tile carries roughly 10–20 polys → **~4 KB/tile**:

| Scope | Tiles | Derived |
|---|---|---|
| One 1024 m chunk actor | 4,096 | ~16 MB |
| 3×3 residency | 36,864 | ~150 MB |
| Whole world, 64 chunks | 259,081 | ~1.0 GB on disk |

**~150 MB resident against 31.4 GB is affordable.** The per-tile poly count is an assumption about open alpine terrain, not a measurement; everything scales linearly with it, and it could be 2× either way.

**Settled by two representations, neither of which is this arithmetic:** (1) build one 1024 m chunk and read its `__ExternalActors__` package size on disk — the instrument `verify_saved_nanite.py` already uses; (2) live, `stat NavigationMemory` (`DEFINE_STAT(STAT_Navigation_NavDataMemory)`, `NavigationSystem.cpp:133-134`) and the `NavigationOctree` LLM tag (`NavigationOctree.cpp:156`).

### 3.5 Build cost — four defaults that are wrong for this machine

**(a) `DataGatheringMode` must be `Lazy`; it defaults to `Instant`.** The largest build-memory lever. `NavigationSystem.cpp:937` sets `Instant`; `FNavigationOctree::IsLazyGathering` (`NavigationOctree.cpp:145-152`) returns false, so at `:201` **every nav-relevant component's geometry is exported and cached on registration.** `ULandscapeHeightfieldCollisionComponent` implements `GatherGeometrySlice` (`LandscapeHeightfieldCollisionComponent.h:229`), but `RecastNavMeshGenerator.cpp:2204` takes the sliced path **only** under lazy gathering. Under Instant the whole 66.6M-vertex collision heightfield is triangulated up front — order of GB, on a machine with 31.4 GB. Related: `GeometryExportTriangleCountWarningThreshold = 200000` (`NavigationSystem.h:381`) against ~516,128 triangles per landscape proxy would warn 256 times.

**(b) `MaxSimultaneousTileGenerationJobsCount = 1024`** (`RecastNavMesh.cpp:549`) — 1024 concurrent tile generators each holding a voxel heightfield, on 24 cores. Structurally the Nanite-batch trap again. Clamp to ~16–24; both `RecastNavMesh.max_simultaneous_tile_generation_jobs_count` and `NavigationSystemV1.set_max_simultaneous_tile_generation_jobs_count` are Python-reflected.

**(c) `NavigationDataBuilderLoadingCellSize = 102400 * 4` = 4096 m** (`WorldSettings.cpp:122`). `IterativeCellSize = GridSize * max(Setting/GridSize, 1)` (`WorldPartitionNavigationDataBuilder.cpp:61-63`) → **2×2 = 4 iterations**, each loading a 4 km quadrant (64 landscape proxies plus ~55,000 trees). Its own comment says *"Set as big as your hardware can afford"* — 31.4 GB cannot afford 4 km. Set **102400** (1024 m) → 64 bounded, resumable iterations. Overlap is handled: `IterativeCellOverlapSize` comes from `GetWorldPartitionNavigationDataBuilderOverlap()`, which returns `TileSizeUU` (`RecastNavMesh.cpp:3784-3787`).

**(d) `MinRegionArea = 0.f`** (`BaseEngine.ini:3062`) keeps **every** disconnected island, including the thousands of 1 m² ledges alpine terrain produces. `minRegionArea = rcSqr(MinRegionArea/CellSize)` (`:5369`), so `400` → `(400/19)² = 443` voxels ≈ 16 m². Directly serves the traversability doctrine: *"a map can be 70% crossable and still broken if that 70% is a thousand isolated shelves."*

**Build wall-clock and peak RAM: no estimate offered.** I have no basis. Settled by the first single-chunk run, timed, with `resource_guard.py` logging free RAM first (pipeline rule 5).

### 3.6 TWO LISTS THAT MUST AGREE

`UCharacterMovementComponent` calls `SetWalkableFloorZ(0.71f)` (`CharacterMovementComponent.cpp:682`), and `SetWalkableFloorZ` computes `WalkableFloorAngle = RadiansToDegrees(Acos(0.71))` (`:7034-7035`) = **44.765083°** — byte-for-byte the constant already in `terrain_erosion.py: UE_WALKABLE_FLOOR_DEG`, commented *"CharacterMovementComponent CDO, read live 2026-08-01."*

`AgentMaxSlope` defaults to **44.0** (`BaseEngine.ini:3062`). Three copies of one physical fact — the movement component, the navmesh generator, `MOVEMENT_PROFILES["walk"]`. Non-negotiables 19 and 24 apply verbatim; `foliage.rock_scatter` is the precedent. **Declare once in the recipe, derive `AgentMaxSlope`, gate the equality.** The drift is asymmetric:

- `AgentMaxSlope > WalkableFloorAngle` → navmesh grants paths onto ground the character slides off. Enemies stutter and fall off the world. **Silent — every navmesh check passes.**
- `AgentMaxSlope < WalkableFloorAngle` → conservative; player escapes uphill. Annoying, not broken.

Keep 44.0 deliberately, with the reason written down, and gate that it never rises above `UE_WALKABLE_FLOOR_DEG`. Same treatment for `AgentRadius=34`, `AgentHeight=144`, `AgentMaxStepHeight=35`, `AgentMaxHeight=160` (`BaseEngine.ini:3058-3062`) — these must match the enemy capsule, not the ini.

### 3.7 Rule tree collision BEFORE building anything

**Measured:** `UFoliageType`'s constructor calls `BodyInstance.SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName)` (`InstancedFoliage.cpp:640`). `place_foliage.py` sets exactly two properties — `mesh` (`:673`) and `cull_distance` (`:701`) — and **never touches `BodyInstance` or `CustomNavigableGeometry`.**

So **all ~219,659 trees have no collision and are invisible to the navmesh.** Good: build cost is essentially the landscape surface, and §3.4 holds. Bad: enemies and the player walk through trunks — in a forest of 153,796+ conifers that is the forest not existing for movement.

Turning it on is not one line: it re-runs the whole build with 219,659 carve-outs (likely 3–10× poly count in forested tiles, invalidating §3.4), and **`recipes/schema.md:468-474` already forbids doing it casually** — *"Any implementation that gives instances blocking collision must re-run the connectivity check against the resulting mask and honour `world.min_connected_frac`."* That clause was written for this moment.

**Recommendation (a recommendation, not a ruling — it is a design call):** collision **but not navmesh relevance** — `BodyInstance` on a Pawn-blocking profile, `CustomNavigableGeometry = EHasCustomNavigableGeometry::No` (`FoliageType.h:376-378`). A 0.3 m trunk against a 0.34 m agent radius is below what the navmesh usefully represents at any affordable cell size; carving 219,659 holes is the wrong economics. Let capsule physics and `UCrowdFollowingComponent` handle trunk obstruction; let the navmesh describe ground. Add `ANavModifierVolume`s only for genuinely path-blocking clusters.

### 3.8 `bWholeWorldNavigable` is unreachable

It exists at `NavigationSystem.h:371`, but the `UPROPERTY(config, EditAnywhere)` above it is **commented out**, with the engine's own note: *"@todo removing it from edition since it's currently broken."* It is absent from the Python-reflected property list. `IsThereAnywhereToBuildNavigation()` (`:2583-2612`) checks it, then `RegisteredNavBounds`, then iterates `ANavMeshBoundsVolume`.

**Consequence: `ANavMeshBoundsVolume` actors are mandatory** — and therefore recipe data, which makes the navigable region an authored, versioned, reproducible fact.

---

## 4. Perception

`UAIPerceptionComponent` on enemies only; `UAIPerceptionStimuliSourceComponent` on the player, noise emitters, and the mount. In a **single-player** game (WORLD_VISION ruling 4) there is exactly one target that matters, so the sight-query set is O(enemies), not O(enemies²) — say this in the design, because it is why the numbers close. Senses: `AISense_Sight`, `AISense_Hearing` (a mount at 3× speed announces itself, ruling 2b), `AISense_Damage`. Skip `AISense_Team` and `AISense_Prediction`.

| Property | Default | Source | Change | Why |
|---|---|---|---|---|
| `MaxTimeSlicePerTick` | **0.005 s** | `AISense_Sight.cpp:139` | 0.002 | 5 ms is 54% of measured GameThread headroom, all line traces |
| `MaxTracesPerTick` | **6** | `AISense_Sight.cpp:46` | ~24 | 6 synchronous traces/tick starves 20 enemies; let the time slice be the limiter |
| `HighImportanceQueryDistanceThreshold` | **300 uu = 3 m** | `AISense_Sight.cpp:140` | ~1500 | 3 m is an indoor number; nothing is ever high-importance and the priority queue idles |
| `MaxQueryImportance` / `SightLimitQueryImportance` | 60 / 10 | `:141-142` | leave | no basis to move |
| `PerceptionAgingRate` | 0.3 s | `AIPerceptionSystem.cpp:44` | leave | |

**EQS:** `MaxAllowedTestingTime = 0.003f` (`EnvQueryManager.h:36`) → 0.001, gated to combat-active agents. `QueryCountWarningThreshold = 200` (`:46`) is a useful tripwire — treat the warning as a defect. StateTree reaches EQS via `FStateTreeRunEnvQueryTask`, so nothing is lost.

**Local avoidance:** `UCrowdManager` — `MaxAgents = 50`, `MaxAgentRadius = 100`, `MaxAvoidedAgents = 6`, `MaxAvoidedWalls = 8` (`CrowdManager.cpp:168-171`). Use `UCrowdFollowingComponent`. 50 is a hard ceiling to design encounters against.

---

## 5. Spawning and despawning against World Partition

`AActor::bIsSpatiallyLoaded = true` by default (`Actor.cpp:363`); default runtime grid `CellSize = 12800` uu (128 m), `LoadingRange = 25600` uu (256 m) (`WorldPartitionRuntimeSpatialHash.h:231-232`).

**Ruling: markers stream, enemies do not.** A WP-streamed enemy is *destroyed* on cell unload and *recreated fresh* on reload — health, aggro, patrol progress, quest state gone. On an 8 km map with a 256 m range and a mount at 3× speed that boundary is crossed constantly. Three layers:

1. **`AEncounterMarker`** — `bIsSpatiallyLoaded = true`, no mesh, no tick. Carries data only: archetype, count, difficulty tier, leash radius. **This is what the Python pipeline writes**, one OFPA package each, like the foliage plans. Registers with the director on `BeginPlay`, unregisters on `EndPlay`.
2. **`UEncounterDirectorSubsystem : UWorldSubsystem`** — owns spawn/despawn with **hysteresis**: spawn at `R_spawn`, despawn at `R_despawn > R_spawn`. The engine precedent to cite in the code is `UNavigationInvokerComponent`, which carries exactly this pair — `TileGenerationRadius` and `TileRemovalRadius` as two separate values (`NavigationInvokerComponent.h:22-28`).
3. **Enemy pawns** — runtime-spawned, `bIsSpatiallyLoaded = false`, owned by the director, which persists a small per-marker state record.

**Mandatory gate:** never spawn before the navmesh under the point is resident. Project onto the navmesh and refuse on failure — an enemy on an unstreamed chunk fails its first `MoveTo` and stands still, which reads as an AI bug and is a streaming bug. Fail closed.

**Not verified:** `ANavigationDataChunkActor` bounds are 1024 m against a 128 m runtime cell, so WP places it on a coarser grid level. Whether nav data is reliably resident *before* the marker on it, I cannot determine from source. **Measurement:** PIE with `wp.Runtime.ToggleDrawRuntimeHash2D` and `show Navigation`, drive a streaming source across a chunk boundary at mounted speed, log the frames at which each becomes active. If nav lags, the fix is a dedicated runtime grid with a larger loading range, or `NavigationDataChunkGridSize = 51200` — note 51200/1600 = 32 exactly, so the tile-size choice survives.

**`InstancedActors` rejected** — Experimental v0.1, hard-depends on `MassGameplay` (also Experimental) plus `DataRegistry` and `GameFeatures`. Drags in the whole Experimental Mass stack for a problem a few thousand no-tick marker actors do not have.

---

## 6. Encounter placement — extend the existing pipeline

An `encounters` block in `recipes/<biome>.json`, consumed by `scripts/plan_encounters.py`, writing `encounters/<biome>_<archetype>.json` in the **same shape as `foliage/*.json`** — absolute-cm transforms, seeded, idempotent. Reuse rather than re-implement:

| Existing | Path | Role |
|---|---|---|
| `plan_species` / `role_mask` | `rock_scatter.py:751`, `:375` | jittered-grid candidates, seeded RNG, mask-conditioned density |
| `centred_bias` | `placement_priors.py` | the ONE prior→multiplier definition; redistributes rather than scales |
| canopy occupancy (cKDTree) | `placement_priors.py` | ambush wants cover; open encounters want meadow |
| `load_flow` | `placement_priors.py` | drainage lines are routes; predators sit near water |
| `traversability()` | `terrain_erosion.py:260` | walk-profile connected component — an encounter on an unreachable shelf is exactly the "diorama" this detects |

**The priors come from WORLD_VISION, not taste.** `WORLD_VISION.md:278-281` rules the terrain's meaning specifically so a placement pass cannot contradict it: the foothill→peak arc is *"the difficulty and remoteness gradient... encounter density, resource value and hazard scale with it"* — so density is a function of geodesic distance from the basin centroids, a **gradient**, matching the D4 ruling that *uniformity is as much the defect as the count*. The inter-massif corridor is the primary traversal route, so exclude a centreline band (`corridor_exclusion_m`). The basins are settlement/POI zones — but `WORLD_VISION.md:296-298` says *where* settlements sit inside them is **blocked on the multi-region ruling**, so basin exclusion is a mask, not hand-placed holes, until that lands.

**Two gates:**

1. **Navmesh reachability, read from a different representation than the heightmap.** `traversability()` reads the heightmap — one instrument. The confirming instrument must be the **built navmesh**: project each encounter centre onto it, refuse on failure, and refuse if its polygon is not in the same connected island as the player start. This project has already lived this failure — the world *rendered* v2 and *collided* v1 for three days while every gate was green, because every gate read the heightmap.
2. **Minimum separation.** Poisson-disc rejection at aggro radius + leash. Without it two encounters chain-aggro past `MaxAgents = 50`. **Positive-controlled** — feed it a deliberately overlapping pair and prove it refuses.

**PCG rejected** despite being production and already partly enabled here: it moves the placement decision into a UE graph asset rather than recipe JSON + numpy, away from design pillar 1 and away from the editor-free verification suite (`prove_gates.py`, `verify_grounding.py`) the whole method rests on. PCG's value is later, for *dressing* a placed encounter site.

---

## 7. Budget — corrected

**The brief's GPU field returns null for this domain.** AI is game-thread work. The binding number is this project's own `_verify/20260814_alpine8k_framecost.md`: GameThread **7.48 ms** at `forest_floor` against 16.67 ms → **9.2 ms headroom**, in an editor viewport not running gameplay, animation, AI or physics.

| Consumer | Default | Source |
|---|---|---|
| `AISense_Sight` time slice | **5.0 ms** | `AISense_Sight.cpp:139` |
| EQS testing time | **3.0 ms** | `EnvQueryManager.h:36` |
| **Total at defaults** | **8.0 ms of 9.2** | |

**That is the finding, and it stands alone.** My first draft added four more rows — StateTree ticks 1.0, PathFollowing 1.5, navmesh queries 0.5, reserve 3.2 — to make a column sum to 9.2. **Those were invented and are retracted.** There is no measured basis for them and none should be built against.

`USignificanceManager` (Production, v1.0) is the right instrument for tiering distant enemies to a slow StateTree tick and no perception; adopt it with the director, not later.

---

## 8. Not verified — stated plainly

- **Every navmesh memory and tile figure is derived from struct sizes, not measured.** No navmesh has ever been built here: `LandscapeLab/Config/*.ini` contains no `Navigation`, `NavMesh`, `Recast` or `AIModule` key. Settled by the one-chunk disk-bytes + `stat NavigationMemory` pair in §3.4.
- **Build wall-clock and peak RAM: unknown.** No estimate given.
- **Nav-chunk vs marker stream ordering** (§5) — needs PIE.
- **StateTree's editor-UI label** — descriptor read only.
- **The per-tile poly count is an assumption about alpine terrain.**
- **I did not connect to the editor and wrote no file.** Nothing here has been executed.
- **Two numbers must not be inherited as fact:** encounter size (my "3–20" was a reference-class guess) and the Mass break-even. Both need Ryan or a measurement.

---

## 9. Order of work

1. Add **only** `StateTree` and `GameplayStateTree` to `LandscapeLab.uproject`. Not `AISupport` — already `EnabledByDefault: true`, and the array is overrides only.
2. Write `[/Script/NavigationSystem.RecastNavMesh]` and `[...NavigationSystemV1]` blocks with §3.2/§3.5 values — `TileSizeUU=1600`, `AverageLayersPerTile=1.5`, `TileNumberHardLimit=2097152`, `MinRegionArea=400`, `AgentMaxSlope=44.0`, `MaxSimultaneousTileGenerationJobsCount=16`, `DataGatheringMode=Lazy` — **then verify on a cold boot**, because the file records an override, never the state in effect. Three different ini files have bitten this project on exactly that.
3. Set `NavigationDataBuilderLoadingCellSize=102400` on `/Game/Alpine8K`'s `AWorldSettings` (editor-only UPROPERTY, not a config key).
4. **Rule tree collision (§3.7) before building anything.**
5. Author `ANavMeshBoundsVolume` placements as recipe data from `traversability()`'s largest walk-profile component. Mandatory — `bWholeWorldNavigable` is unreachable.
6. **Build ONE chunk. Measure bytes, time, peak RAM. Then decide whether the other 63 are affordable.** Tag a restore point named for the operation first — this writes 64 external actor packages and is inside THE RISKY-OP CHECKPOINT.
7. Only then: encounter planner, director subsystem, first StateTree.

**BACKLOG entries generated** — a grep of `BACKLOG.md` for `AI`, `navmesh`, `navigation`, `encounter`, `enemy`, `combat`, `StateTree`, `Mass` returns no AI items, so none of these duplicate: tree-collision ruling; navmesh single-chunk measurement; nav-chunk-vs-marker streaming ordering test; the `AgentMaxSlope` ↔ `UE_WALKABLE_FLOOR_DEG` single-declaration sweep; encounter-size ruling; Mass break-even measurement.