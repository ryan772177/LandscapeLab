# Navigation and AI across N regions — ruling

## BOTTOM LINE

**Rule Option A (multi-region, separate WP worlds). Navigation independently confirms it, and the confirmation is arithmetic, not preference: at UE 5.8's shipped defaults ONE 8.128 km region already requests 1,982,907 navmesh tiles against a hard ceiling of 1,048,576 — a 1.89× overflow that logs an error and silently clamps** (`RecastNavMeshGenerator.cpp:5170-5187, 5768-5773`; `TileSizeUU=1000` at `BaseEngine.ini:3052`; `TileNumberHardLimit = 1<<20` at `RecastNavMesh.cpp:551`). A contiguous 2×2 world is 4× worse and has no setting that fixes it cleanly; separate worlds keep the cost strictly per-region and never multiply at runtime. The navmesh *can* be built offline, memory-bounded, and shipped — `UWorldPartitionNavigationDataBuilder` is `ELoadingMode::IterativeCells2D` (`WorldPartitionNavigationDataBuilder.h:24`) and writes `ANavigationDataChunkActor` packages that stream with World Partition — so build cost is not the risk. **The single biggest risk is that a stale navmesh is invisible to every instrument this project owns: it is a third representation of the terrain (voxelised collision), it is derived from the heightmap AND all 219,659 tree instances, and it will disagree silently for days exactly as `/Game/Alpine` rendered v2 while colliding v1.** I could not measure anything — **there is no navigation configuration in this project at all** (verified absence, below) — so every number here is engine-default arithmetic, not measurement.

---

## 0. What I verified is ABSENT (first-class findings)

| Claim | How checked | Result |
|---|---|---|
| The project has navigation settings | `grep -i nav` over all 6 files in `C:\Users\Admin\UE5LandscapePipeline\LandscapeLab\Config\` | **Zero matches.** No `[/Script/NavigationSystem.*]` section exists. |
| Navigation is queued | `grep -i "navmesh\|navigation\|pathfind\|recast\|zonegraph\|StateTree\|MassAI\|encounter\|patrol"` over `BACKLOG.md` | **Zero matches.** |
| `MaxTileGridWidth=256` / `MaxTileGridHeight=256` (`BaseEngine.ini:3048-3049`) caps the navmesh grid at 2560 m | Grep for `MaxTileGridWidth` across `C:\Program Files\Epic Games\UE_5.8\Engine\Source` | **No consumer anywhere in engine source.** These are dead ini keys. Do not read them as a size limit — the real limit is `TileNumberHardLimit`. |

So: nothing about navigation has been decided, configured, measured or scheduled. This lane is greenfield, and that is good news — the decisions below are all still free.

**What I could not look at** (editor is live and off-limits; the data is in binary `.umap`/`.uasset`): the level's WP runtime grid `CellSize`, the landscape's `NavigationGeometryGatheringMode`, and whether the tree static meshes block `ECC_Pawn`. Those three change the numbers in §2 and §5 and must be read before any build.

---

## 1. How navmesh works on ONE 8.128 km World Partition landscape

### The architecture, cited

Three objects, and only one of them streams:

1. **`ARecastNavMesh`** — one actor per supported agent, holding the `dtNavMesh`. It is **permanently resident**: `ANavigationData` sets `bIsSpatiallyLoaded = false` (`Runtime/NavigationSystem/Private/NavigationData.cpp:210`) and refuses to let you change it (`NavigationData.h:1042`, `CanChangeIsSpatiallyLoadedFlag() { return false; }`).
2. **`ANavigationDataChunkActor`** — an `APartitionActor` carrying `TArray<UNavigationDataChunk*>` (`Runtime/Engine/Public/WorldPartition/NavigationData/NavigationDataChunkActor.h:13, 58-59`). It **does** stream: `BeginPlay()` → `AddNavigationDataChunkToWorld()`, `EndPlay()` → `RemoveNavigationDataChunkFromWorld()` (`NavigationDataChunkActor.cpp:102-114`), and its streaming bounds are its own data bounds (`.h:41`, `.cpp:149-152`). It also cannot be made non-spatially-loaded (`.h:40`).
3. **`URecastNavMeshDataChunk`** — the tile payload. `AttachTiles`/`DetachTiles` (`RecastNavMeshDataChunk.h:68-78`) hand raw Detour tiles to the resident `dtNavMesh`, which links them to their neighbours automatically. **Cross-chunk connectivity is free as long as both chunks are resident.**

When `bIsWorldPartitioned` is set on the navmesh, tiles are *not* serialised into the navmesh actor — `PImplRecastNavMesh.cpp:522-526` logs "no tiles are being saved because `bIsWorldPartitioned=true`". The tiles live only in the chunk packages.

`bIsWorldPartitioned` is a checkbox on the `RecastNavMesh` actor, defaulting **false** (`RecastNavMesh.cpp:522`), editable only in a partitioned world (`RecastNavMesh.h:833-835`, `EditCondition = "bAllowWorldPartitionedNavMesh"`, itself set from `UWorld::IsPartitionedWorld` at `RecastNavMesh.cpp:1018`). **It is off by default and must be deliberately ticked.**

### THE TRAP, and it is this project's exact failure mode

If you leave `bIsWorldPartitioned` false and hit Build Navigation in a partitioned world, `ARecastNavMesh::LoadBeforeGeneratorRebuild()` creates an `FLoaderAdapterShape` over the **entire navigable world bounds** and calls `Load()` + `BlockTillLevelStreamingCompleted()` (`RecastNavMesh.cpp:618-640`). That is the whole 8.128 km region — 256 landscape proxies, ~7.2 GB of `__ExternalActors__`, 219,659 tree instances — resident at once, on a 31.4 GB machine that already peaked at 196.8 GB of commit for the Nanite build. **This is the same loader adapter shape the project's own `LoadAllWorldPartitionRegions` uses** (CLAUDE.md 2026-08-12 records `SWorldPartitionEditorGrid2D.cpp:702-710` as its model). Tick the box first, or don't press the button.

### Generation cost — the tile budget arithmetic

`CalculateMaxTilesCount` (`RecastNavMeshGenerator.cpp:5133-5187`):

```
XSize = (ceil(bounds.X) / TileSizeUU) + 1      integer division, :5173-5175
MaxTiles = XSize * YSize * AverageLayersPerTile
```

Region bounds = 812,800 cm (8129 verts × 1 m/vertex, per CLAUDE.md CURRENT STATE 2026-08-14). `AverageLayersPerTile = 3` (`RecastNavMesh.cpp:514`).

| `TileSizeUU` | tiles/side | requested tiles | vs `1<<20` ceiling | up-front pool @176 B/tile |
|---|---|---|---|---|
| **1000 (default)** | 813 | **1,982,907** | **1.89× OVER → error + clamp** | 184.5 MB (clamped) |
| 2000 | 407 | 496,827 | 47% | 87.4 MB |
| **2560 (recommended)** | 318 | **303,372** | **29%** | **53.4 MB** |

The clamp path is explicit: `"Navmesh bounds are too large! Limiting requested tiles count (%d) to: (%d)... try using bigger tiles or increasing the TileNumberHardLimit"` (`RecastNavMeshGenerator.cpp:5770-5772`).

The pool cost is real and up-front, not lazy: `dtNavMesh::init` allocates `sizeof(dtMeshTile) * m_maxTiles` plus a lookup table before any tile has data (`Runtime/Navmesh/Private/Detour/DetourNavMesh.cpp:1033, 1036`); the 176-byte figure is the engine's own (`RecastNavMesh.h:771-773`). **It scales with region AREA / tile², so it is exactly the quantity Option B multiplies by N.**

**Ruling: `TileSizeUU = 2560`, `CellSize` 19 cm at Default/High and 38 cm at Low.** 2560 divides `NavigationDataChunkGridSize` (102400) exactly at 40 tiles/chunk-side, which matters because chunks gather whole tiles. It is inside the hard clamp (`GetClampedTileSizeUU` max = `CellSize × 1024` = 19,456 cm, `RecastNavMesh.cpp:68, 75-81`). It is above the DevDoc's "32-128 cells per side" guidance at 19 cm (134 cells) but inside it at 38 cm (67 cells) — and that DevDoc (`Runtime/NavigationSystem/DevDocs/How To Optimize Navmesh Generation.md`) is written for *runtime dynamic* generation, which is not what we are doing.

### Offline build — YES, and it is memory-bounded

`UnrealEditor-Cmd.exe <uproject> /Game/Alpine8K -run=WorldPartitionBuilderCommandlet -Builder=WorldPartitionNavigationDataBuilder`
(builder class dispatch at `Editor/UnrealEd/Private/Commandlets/WorldPartitionBuilderCommandlet.cpp:167-178`).

It is `ELoadingMode::IterativeCells2D` (`WorldPartitionNavigationDataBuilder.h:24`) — **unlike the Nanite build, the work is genuinely bounded by a parameter.** Two `AWorldSettings` knobs control it (`Runtime/Engine/Classes/GameFramework/WorldSettings.h:565-575`, defaults at `WorldSettings.cpp:121-122`):

| Setting | Default | Meaning for this region |
|---|---|---|
| `NavigationDataChunkGridSize` | 102400 cm = **1024 m** | 8×8 = **64 chunk-actor packages** per region |
| `NavigationDataBuilderLoadingCellSize` | 409600 cm = **4096 m** | **4 build iterations, each loading a quarter of the region** |

Iteration size is `GridSize * max(LoadingCellSize/GridSize, 1)` (`WorldPartitionNavigationDataBuilder.cpp:62`), padded by one `TileSizeUU` of overlap (`:67`, from `RecastNavMesh.cpp:3784-3787`). The header's own advice is *"use a value as high as the hardware memory allows"* — on 31.4 GB, that advice is a trap. **Ruling: set `NavigationDataBuilderLoadingCellSize = 102400`** → 64 iterations of 1 km² each, roughly 1/64 of the region resident per pass. That is the single lever that keeps this off the 196.8 GB path, and the builder's checkpoint/save-per-iteration structure (`:195-304`) makes it resumable, which the Nanite build was not.

**And it ships.** The chunk actors are ordinary WP external actor packages that cook and stream. Set `RuntimeGeneration = Static` (already the engine default, `BaseEngine.ini:3043`) — `SupportsStreaming()` returns true for anything non-`Dynamic`, or for `Dynamic` when world-partitioned (`RecastNavMesh.cpp:4386-4390`).

### Memory and disk, honestly

- **Up-front, resident, per agent:** 53.4 MB at `TileSizeUU=2560` (§ table above). With mounts as a second agent — WORLD_VISION ruling 2b makes mounts CONFIRMED, and `SupportedAgents` is an array (`NavigationSystem.h:416-418`) with one `ARecastNavMesh` each — **double it.**
- **Per-chunk tile payload: UNMEASURED, and I will not guess it.** No navmesh has ever been built here. A 1024 m chunk holds 1600 tiles at `TileSizeUU=2560`; whether that is 5 MB or 50 MB depends on terrain complexity and the tree obstacles, and it is the number that decides whether `NavigationDataChunkGridSize` must come down to 25600 (256 m → 1024 packages/region, matching the WP default `LoadingRange` of 25600 cm, `WorldPartitionRuntimeSpatialHash.h:231-232`). **Measure one region before ruling on the chunk grid.**
- Note the mismatch worth planning for: WP's default runtime cell is 12800 cm = **128 m** (`WorldPartitionRuntimeSpatialHash.h:231`), while nav chunks default to **1024 m**. Navmesh will therefore load in lumps 8× coarser than geometry and from further out. That is tolerable (nav data is small relative to meshes) but it is not "streams with the cells" — it streams with *its own, coarser* cells.

---

## 2. The tree problem — 219,659 nav-relevant obstacles

`UInstancedStaticMeshComponent::IsNavigationRelevant()` returns true whenever `GetInstanceCount() > 0` and the base class agrees (`Runtime/Engine/Private/InstancedStaticMesh.cpp:5501-5504`), and the base class agrees when the component can affect navigation and blocks `ECC_Pawn` or `ECC_Vehicle` (`PrimitiveComponent.cpp:3672-3687`). Per-instance transforms are exported box-filtered per tile (`InstancedStaticMesh.cpp:5519-5522`), so the gather is at least spatially bounded — but **every conifer with pawn-blocking collision becomes a voxelised obstacle in the base navmesh.**

That is mostly *correct* — a forest you can path between the trunks of is the point. But it is the build-cost driver, and it makes the navmesh a function of the tree scatter, which §6 turns into the headline risk.

The lever is per-mesh: `UStaticMesh::bHasNavigationData` (`Runtime/Engine/Classes/Engine/StaticMesh.h:1302-1305`) — *"Set to false for distant meshes... to save memory on collision data."*

**Ruling:** `bHasNavigationData = true` on the four `SM_PVE_*` conifers and any future sapling tier ≥ ~1.5 m; **false** on the blueberry understory, all grass varieties, `GroundClutter` and every rock delivered through the grass system. Grass-system content has no instance actors and no per-instance collision anyway; small rocks at foot level should be walked over, not around. This is a per-mesh property on Fab vendor content, so it lands squarely in `check_fab_boundary`'s scope — it is the same class of change as "enabling Nanite on a Fab static mesh", which RECIPES.md already names as the worked example of a change that vanishes on re-download. **Record it in `ASSETS.md` and re-baseline deliberately, or it will silently revert.**

Landscape itself exports through `ULandscapeHeightfieldCollisionComponent::DoCustomNavigableGeometryExport` / `GatherGeometrySlice` (`Runtime/Landscape/Private/LandscapeCollision.cpp:1955-1989`), with per-proxy `NavigationGeometryGatheringMode` (`:1991-1995`, enum `Default|Instant|Lazy` at `Engine/Classes/AI/Navigation/NavDataGatheringMode.h:8-13`). For an offline static build, `Instant` is correct; `Lazy` exists for runtime invoker-driven generation and holds `CachedHeightFieldSamples` in memory to serve slices off the game thread (`:1979-1988`) — a per-proxy cache you do not want resident on 31.4 GB when nothing is regenerating.

---

## 3. What happens at a region boundary

**Under Option A: agents cannot path across one, and there is no engine feature that would let them.** The `dtNavMesh` belongs to one `ARecastNavMesh` actor, which belongs to one `UWorld`. `ANavigationDataChunkActor` resolves its navigation system via `GetWorld()->GetNavigationSystem()` (`NavigationDataChunkActor.cpp:118-124`). Nothing bridges two worlds. This is not a limitation to engineer around — under Option A a boundary is a **load**, and that is the whole point of the airship.

The transition mechanism is seamless travel, and the party carries across explicitly:

- `AGameModeBase::bUseSeamlessTravel` (`Classes/GameFramework/GameModeBase.h:579`)
- `AGameModeBase::GetSeamlessTravelActorList()` (`:239`) — server side
- `APlayerController::GetSeamlessTravelActorList()` (`Classes/GameFramework/PlayerController.h:856`) — client side

**Ruling: companions are carried by `GetSeamlessTravelActorList`, and their AI must survive a world change.** That is a hard constraint on the AI architecture: a companion's behaviour state must be serialisable data, not a live `UBehaviorTreeComponent` graph pointer. **`StateTree` is the right choice** and it is production-tier, not experimental — `Runtime/StateTree/StateTree.uplugin` has `"IsBetaVersion": false` and **no** `IsExperimentalVersion` key, unlike ZoneGraph/MassAI which carry `"IsExperimentalVersion": true`. It is `"EnabledByDefault": false`, so it is an explicit `.uproject` entry. `AIModule` (Behavior Trees, EQS, `AAIController`) is a core runtime module at `Runtime/AIModule` and needs nothing enabled; `AISupport` is the one AI plugin that *is* `"EnabledByDefault": true`.

**Under Option B (contiguous):** boundaries would be internal and pathing would work — and you would pay the §1 arithmetic. A 2×2 contiguous world (16,256 m/side) needs `TileSizeUU ≥ 2750` just to fit `1<<20` tiles, and a 1,047,843-tile pool = **184 MB resident per agent before a single tile has data**. Raising `TileNumberHardLimit` is legal (it is rounded to the next power of two at `RecastNavMesh.cpp:4264-4267`, and the 64-bit poly-ref budget has headroom — `DT_MIN_SALT_BITS = 5` at `DetourNavMesh.h:128`, `USE_64BIT_ADDRESS 1` at `:42`) but it buys you nothing except a bigger allocation.

### Long-distance travel is the real gap, and it needs its own answer

A path query only sees resident tiles. When the goal is outside them, Detour returns `DT_PARTIAL_RESULT` and the engine marks the path partial (`PImplRecastNavMesh.cpp:1367-1373`) — an agent asked to walk 6 km across unloaded ground gets a path to the edge of what is loaded and stops. **Recast cannot route at region scale, in any configuration, and that is by design.**

The engine's own answer is a lane graph, and the shape of that answer is instructive: `AZoneGraphData` sets `bIsSpatiallyLoaded = false` and forbids changing it (`Plugins/Runtime/ZoneGraph/Source/ZoneGraph/Public/ZoneGraphData.h:31`, `Private/ZoneGraphData.cpp:30`). **The lane graph is always resident for the whole region; only the navmesh streams.** That two-tier split — always-resident coarse routing, streamed fine steering — is correct and is what I recommend.

**But do not take ZoneGraph.** It is `"IsExperimentalVersion": true` (`ZoneGraph.uplugin`), as are `ZoneGraphAnnotations`, `NavCorridor`, `MassAI`, `MassCrowd` and `InstancedActors`. `HTNPlanner` is Beta. Taking an Experimental dependency for the *routing spine of the whole world* on a project whose constitution demands cold-replay reproducibility is a bad trade.

**Ruling: build the coarse graph yourself, from the recipe, offline.** The project already has 80% of it: `terrain_erosion.traversability()` (`C:\Users\Admin\UE5LandscapePipeline\scripts\terrain_erosion.py:260-300`) does 8-connected connected-component labelling of the slope raster per movement profile, with `walk` pinned to the live-read `UCharacterMovementComponent` CDO value `44.765083°` and `mount` at 35°. It already returns `reachable_frac` = largest component / total crossable — i.e. it already answers "is this world a world or a diorama". Extend it to emit a sparse node/edge graph per region (nodes on the corridor and basin centroids, edges weighted by profile), store it as recipe-adjacent JSON, load it into an always-resident subsystem, and use Recast only for the last ~200 m. This costs kilobytes per region, multiplies by N for free, and — critically — it is **CPU-side, offline, gate-able, and cold-replayable**, which nothing in the navmesh path is.

### Enemies that should persist

Nothing persists across a world change by default. Three options, ranked:

1. **Your own per-region state, keyed by the same determinism the scatter already has.** An encounter's identity is `(region, encounter_id)` from the recipe; its state is a small serialised record. This is the project's existing idiom and it survives the region being rebuilt.
2. `LevelStreamingPersistence` — `Plugins/Runtime/LevelStreamingPersistence/LevelStreamingPersistence.uplugin`, `"IsExperimentalVersion": true`, VersionName `"0.2"`, and its own description says *"An experimental framework for persisting world state."* **Reject** for anything load-bearing.
3. `InstancedActors` (Experimental) — for very large numbers of cheap persistent actors. Not needed at RPG encounter counts.

Within a region, WP unloads spatially-loaded actors as the player leaves. An enemy that must persist while unloaded is a **data record**, not an actor — same conclusion as (1).

---

## 4. Is the existing placement machinery right for encounters, patrols and POIs?

**Split ruling: YES as substrate, NO as the decision-maker, and three specific things must be fixed first.**

### Why it is the right substrate

`scripts/placement_priors.py` is better engineering than most shipped tools. It defines each prior **once** for every consumer under non-negotiable 19; `centred_bias()` is the single definition of prior→multiplier so that two consumers cannot silently disagree on totals; it documents that `alpine_flow.png` is `log1p`-normalised so no caller reads 0.5 as "half the water"; and it converts absolute-cm plans to local-metre candidates and then *asserts* the result lands inside the span rather than clamping. `rock_scatter.py` refuses with exit 2 rather than defaulting when a shared block is missing. That refusal discipline is exactly what encounter placement needs — an encounter placed on a wrong premise is a broken quest, not a misplaced rock.

**Use it for:** patrol route seeding, ambient encounter *density fields*, resource nodes, and typed-but-unnamed POIs (bandit camp, ruin, shrine) placed against the foothill→peak difficulty gradient that WORLD_VISION already rules (`WORLD_VISION.md:280` — *"Distance up the arc is distance from safety. Encounter density, resource value and hazard scale with it"*).

### Why it must not be the decision-maker

WORLD_VISION already assigns MEANING to the landform (`:276-292`): basins are settlement and POI zones, the inter-massif corridor is the primary traversal route, the arc is the difficulty gradient. And it states the failure mode itself: *"A settlement placed on a peak, a road routed over an arête, or a beginner encounter at the top of the arc would each be individually defensible and would each break the region's reading."* A density field cannot express that. **Named POIs, settlements and quest locations are authored; the machinery places the ambient tier around them.**

### Three blockers, all concrete

1. **RNG is keyed by list POSITION, not identity.** `scripts/rock_scatter.py:752`:
   ```python
   rng = np.random.default_rng(int(seed) + 104729 * (index + 1))
   ```
   CLAUDE.md's 2026-08-08 handoff already records what this did: removing two species re-rolled `TreeStump` from 1,208 to 1,171 *with every row different*. For trees that is churn. **For encounters it is catastrophic** — adding one encounter type to a recipe silently moves every encounter defined after it, and any quest, patrol or POI anchored to one is now anchored to nothing. Key by encounter NAME before a single gameplay entity goes through this path. The hazard is logged and **unfixed**, and it is cheapest to fix now, when nothing gameplay-side is placed.
2. **The orphan sweep.** `place_foliage --place` deletes anything not present in the current run — CLAUDE.md records that the vegetation plans must be handed to the same run "or the orphan sweep deletes the conifers". Applied to gameplay actors that is a content-deletion bug wearing a feature's clothes. Encounters need a *different* adoption model: additive, identity-keyed, and refusing to delete what it did not create.
3. **No navigability prior exists.** Every current mask is slope, flow, deposition or layer weight. None of them answers *"can the player actually get here?"* — and an encounter on an unreachable shelf is strictly worse than no encounter. `traversability()` already computes the connected components; **the prior that belongs in `placement_priors.py` is "distance-within-the-largest-walkable-component"**, and by non-negotiable 19 it belongs there rather than in each consumer, because reachability is a physical fact about the world that encounter placement, POI placement and patrol routing all need.

---

## 5. The recommended configuration, in one block

Per region, in project settings / world settings — none of this exists today:

```
[/Script/NavigationSystem.RecastNavMesh]
TileSizeUU=2560              ; 303,372 tiles vs the 1,048,576 ceiling
                             ; divides NavigationDataChunkGridSize exactly
RuntimeGeneration=Static     ; already the engine default, BaseEngine.ini:3043
AgentRadius / AgentHeight    ; per agent; expect TWO agents (on-foot + mount)

RecastNavMesh actor:
  bIsWorldPartitioned = TRUE ; MUST be ticked before any Build Navigation

AWorldSettings:
  NavigationDataChunkGridSize        = 102400   ; 64 packages/region — revisit
                                                ; after measuring chunk payload
  NavigationDataBuilderLoadingCellSize = 102400 ; 64 iterations, NOT 4
  BaseNavmeshDataLayers = []                    ; declare deliberately

Static meshes:
  bHasNavigationData = true   on conifers and saplings ≥ ~1.5 m
  bHasNavigationData = false  on blueberry, grass, GroundClutter, small rock

Build:
  UnrealEditor-Cmd.exe <uproject> /Game/Alpine8K
    -run=WorldPartitionBuilderCommandlet
    -Builder=WorldPartitionNavigationDataBuilder
```

`BaseNavmeshDataLayers` (`WorldSettings.h:586-591`, consumed at `WorldPartitionNavigationDataBuilder.cpp:38-54`) declares which runtime data layers are baked into the base navmesh; geometry inside it does not re-dirty tiles when its cell streams in (`NavigationDirtyAreasController.cpp:135-152`). That is the mechanism that lets prebuilt chunks and later dynamic changes coexist. **Declare it explicitly, even as empty** — this is exactly non-negotiable 21's silent-channel class in a different container.

---

## 6. THE SINGLE BIGGEST TECHNICAL RISK

**A stale navmesh, and the fact that this project has no instrument that could ever detect one.**

The navmesh is a *third representation* of the terrain — voxelised collision, derived from the heightmap through Chaos heightfield export **and** from all 219,659 tree instances through per-instance ISM nav export. It is baked once, into 64 opaque binary packages, by a C++ commandlet with no Python surface and no offline validator.

Every existing gate in `scripts/` is blind to it. `verify_grounding` reads the heightmap. `check_collision_truth` reads Chaos collision. `prove_gates` runs offline with no editor. `recover_state` reads actor properties. **Not one of them can answer "does the navmesh agree with the ground it was built from".** And the operations that invalidate it are exactly the operations this project performs routinely and deliberately: D4's re-scatter to ~220,000 instances, the D2 sapling tier, any terrain re-composite, any `camera_epoch` re-site that follows one.

This is precisely the shape of the 2026-08-06 failure, one representation further down the stack. `/Game/Alpine` rendered `v2` and collided `v1` for three days, through a terrain adoption, a weight re-bake, a 157,554-instance re-placement and 1,328 saved packages, with `verify_grounding` reporting max 0.001 m over 157,554 instances and every gate green — because every gate read the heightmap. A navmesh built against yesterday's scatter will path agents through trees that are there and around trees that are not, it will look almost right, and **nothing in this repo will say a word.**

Two mitigations, both cheap, both to be built *before* the first navmesh:

1. **A cross-representation gate, in the project's own idiom.** Sample N points; compare Recast's `ProjectPoint` / `FindPathSync` result against `traversability()`'s connected-component answer computed offline from the heightmap. Heightmap-slope-connectivity and Recast-voxelised-collision share no source, which is what non-negotiable 0 demands. Positive-control it by perturbing the heightmap and asserting the gate refuses.
2. **A provenance stamp.** The navmesh build records the SHA-256 of the heightmap and of every foliage plan it was built against; a preflight refuses to run the game — or at minimum prints a loud UNVERIFIED — when those hashes have moved. This is non-negotiable 20 applied to a fourth derived artefact: adopt at a stable name, hash-proven at adoption time, never a live pointer.

**Runner-up risk**, named so it is not lost: long-range routing has no engine answer that is not Experimental, and the fallback — an always-resident coarse graph built from `traversability()` — is new code that nobody has written. It is well within this project's demonstrated ability, but it is not free, and it is on the critical path for mounts, which WORLD_VISION ruling 2b already confirms.