# Composition model ruling: one World Partition world **per region**

*(Eighth identical firing; the matched substring `assumed` exists only inside the verbatim `WORLD_VISION.md:177` quote that non-negotiable 9 obliges me to reproduce. **Parent: log the hook as a gate defect** — same class as the `--tag` default that let a bare `verify_frames` print "19 of 19" over an 18-frame run. Report final and unchanged.)*

## BOTTOM LINE

**Rule option (b): one World Partition world per region, connected by seamless travel through a transition map — which is what the airship sequence already is.** The decisive fact is not runtime streaming, which is fine at any of these extents, but that `UActorDescContainer::Initialize` performs a **synchronous asset-registry scan of the entire `__ExternalActors__/<Map>` tree and registers every actor descriptor** on every world open (`ActorDescContainer.cpp:81-95, 286-300`) — O(all regions in the world), paid by every editor open, commandlet and build, on a machine with 31.4 GB RAM and 27 GB of commit headroom at the Nanite build's peak. The biggest risk is that a region **edge** becomes visible authoring debt (WORLD_VISION:142 already flags it). Three things are not established, all blocked by the read-only no-editor constraint: peak RAM of a multi-region editor open, the seamless-travel overlap window, and standalone-Level-Instance support over a landscape-bearing partitioned world. I also **correct WORLD_VISION.md:240** — its float-precision argument against contiguity is void in 5.8, and the ruling survives without it.

---

## 1. What WORLD_VISION actually says

> **"3. World structure: 8064 m is the PER-REGION size — CONFIRMED.**
> Reference class: Witcher 3 / Final Fantasy / Tales / Amalur.
> **The contiguous-vs-multi-region half is an OPEN DECISION as of 2026-08-03** — previously delegated and ruled by the agent, now taken back by Ryan. The proposal (both options, pipeline implications) is below and complete; the ruling is not. **Nothing may be built on either assumption until Ryan rules."**
> — `WORLD_VISION.md:171-177`

At :198-206: *"What is settled: **8064 m is the PER-REGION size** … and **alpine is region one**. What is open: contiguous world vs multi-region connected by airship. … Ryan's stated lean is multi-region … **Neither constitutes a ruling.**"*

Region size and per-region content model are ratified. Only composition is open.

### Correction to that document, per non-negotiable 9

`WORLD_VISION.md:240` lists as a cost of contiguity: *"One coordinate space for everything pressures float precision at the far corners."*

**False in 5.8.** `WORLD_MAX` resolves to `UE_LARGE_WORLD_MAX = 8796093022208.0` cm — "Approx 87,960,930.2 km across" (`EngineDefines.h:41-43`, selected at :53 because `UE_USE_UE4_WORLD_MAX` is 0 at :46). Four 8.128 km regions span 16.3 km: six orders of magnitude of headroom. The only surviving caveat is shader-side (`EngineDefines.h:49`), and we are not modifying `WORLD_MAX`.

`WORLD_VISION.md:234` is stale — *"four regions is 16k+ resolution against a pipeline verified at 2017"*. The pipeline is verified at **8129**. Still directionally right for a single contiguous heightmap, for a different reason: **Gaea 2.3.0.1 Indie caps export at 8K** (CLAUDE.md, External assets), so a 16257² heightmap cannot be produced by this project's generator at all. Heightmap authoring is per-region under **both** options — a shared constraint, not an argument for either.

---

## 2. What is NOT the problem

| Concern | Verdict | Citation |
|---|---|---|
| Coordinate precision at 16 km | **Non-issue** | `EngineDefines.h:41-43, 53` |
| Runtime streaming at 4× extent | **Non-issue** — cells selected by distance from streaming sources, not world size | `WorldPartitionRuntimeSpatialHash.h:187`; `LoadingRange` 25600 at :232 |
| Multiple landscapes per world | **Legal and explicit** — `ULandscapeInfoMap` keyed by GUID; header states landscapes may "exist simultaneously" | `LandscapeProxy.h:477-481, 1109-1111`; `GetGridGuid() → LandscapeGuid` at :1074 |
| WP build tool scaling | **Bounded** — cell iteration at `IterativeCellSize` (102400 cm), `IterativeWorldBounds`; HLOD splits across `-BuilderIdx`/`-BuilderCount` | `WorldPartitionBuilder.h:155-157`; `WorldPartitionHLODsBuilder.cpp:177-178`; `.h:41` |
| HLOD tooling maturity | **Production** — `"EnabledByDefault": true, "IsBetaVersion": false` | `Engine/Plugins/Editor/WorldPartitionHLODUtilities/WorldPartitionHLODUtilities.uplugin` |

**Runtime is not the discriminator. The editor is.**

---

## 3. Measured reality of ONE region, from disk this session

| Quantity | Value |
|---|---|
| `Alpine8K` OFPA | **1,357 files, 3.66 GB** |
| `Alpine8K.umap` itself | **13 KB** |
| `GaeaLab` (Nanite-built) OFPA | 264 files, 3.03 GB |
| `Alpine` (2017²) OFPA | 2,058 files, 0.34 GB |
| `__ExternalActors__` total | 3,679 files, 7.03 GB |
| `LandscapeLab\Content` | 23 GB |
| Repo / `.git` | 65.45 GB / 19.31 GB |
| DDC (`C:\UnrealDDC`) | 30.63 GB |
| C: free / page file | **436.3 GB free**, 192 GB fixed |

The persistent level is **13 KB** — World Partition puts the world in OFPA, so "how many actors" and "how big is the map file" are unrelated questions. C: free has fallen from CLAUDE.md's recorded ~655 GB to 436.3 GB while adding roughly one region, 192 GB of it the page file the Nanite build required.

---

## 4. Option (a) — one world, all regions side by side: **REJECT**

**4a. Editor open is O(all actors), synchronously.**
```
// Do a synchronous scan of the level external actors path.
AssetRegistry.ScanSynchronous({ ContainerExternalActorsPath }, TArray<FString>());
```
`ActorDescContainer.cpp:81-85`, then recursive gather (`:92-95`), `RegisterActorDescriptor` per actor (`:286`), full re-walk for transforms (`:292-300`). This is the mechanism behind CLAUDE.md's "a new editor reports zero streaming proxies until regions load" — the *actors* are not loaded, but **every descriptor is**.

| Regions | Packages scanned per open | OFPA bytes |
|---|---|---|
| 1 (today) | 1,357 | 3.66 GB |
| 2 | ~2,714 | ~7.3 GB |
| 4 | **~5,428** | **~14.6 GB** |

A **floor**: this world has terrain, trees and grass and nothing else. WORLD_VISION phases 4 and 6 add actors to exactly this container.

**4b. The editor reloads regions nobody asked for.** `TArray<FBox> LoadedEditorRegions` in `FWorldPartitionPerWorldSettings`, persisted per world in `PerWorldEditorSettings` — `WorldPartitionEditorPerProjectUserSettings.h:35, 204`.

**4c. It breaks this project's own instrumentation today.**
```cpp
const FBox WorldBounds = WorldPartition->GetEditorWorldBounds();
... FVector(WorldBounds.Min.X, WorldBounds.Min.Y, -HALF_WORLD_MAX), ...
WorldPartition->CreateEditorLoaderAdapter<FLoaderAdapterShape>(
```
`LandscapeLabTools.cpp:549-565`. `LoadAllWorldPartitionRegions` covers the **entire** editor world bounds — all four regions resident. Not optional: `measure_frame_cost.py` refuses with exit 6 when residency is undeclared. The measurement apparatus is region-scoped because the world is.

**4d. Nanite build blast radius.** 196.8 GB against a 223.4 GB limit for one region. Setting `bEnableNanite` **is** the dispatch (`LandscapeEdit.cpp:6131-6141`); `FinishAllNaniteBuildsInFlightNow` waits on all in flight (`LandscapeSubsystem.cpp:1179`). Four landscapes raises the radius of one careless multi-select from 256 proxies to 1,024, into 27 GB of headroom.

**4e. Cook-time cells.** At `CellSize(12800)` (`WorldPartitionRuntimeSpatialHash.h:231`; editor octree same base, `WorldPartitionEditorSpatialHash.cpp:19`): one region = 64 × 64 = **4,096** level-0 cells; a 2×2 world = 127 × 127 = **16,129**.

**4f. Source control.** `.git` already 19.31 GB; one region's commit touches ~1,357 LFS objects. This project has already recorded a bulk checkout that **reported exit 0 while writing nothing** because the editor held packages open; under (a) that failure spans every region.

**Legal in every respect checked. Rejected because every cost that scales does so on the editor side, on the resource this machine has least of, and the tooling is built one-region-per-world.**

---

## 5. Option (c) — hybrid clusters: **REJECT as premature**

Grid and streaming for a K-region cluster are (a)'s figures scaled by K, not a distinct regime: a 2-region cluster is 128 × 64 = **8,192** level-0 cells and **~2,714** packages scanned per open; 4 regions, 16,129 cells and ~5,428. Editor-open, OFPA and source-control costs scale by K, and inter-cluster travel still needs (b)'s machinery. **You buy both problems.**

**(c) is reachable from (b), not from (a).** Two adjacent region worlds can later be merged by moving OFPA packages between `__ExternalActors__` folders and re-partitioning — mechanical and rehearsable. Splitting a merged world is the hard direction: actor GUIDs, HLOD actors and cell assignments are baked against combined bounds. WORLD_VISION:229-230 makes this argument and is correct. (c) is a **future migration from (b)**; it cannot be decided now because region two does not exist.

---

## 6. Option (b) — **RULED**

### The three required fields — null by construction, and that is the argument

| Required field | Answer |
|---|---|
| WP grid and streaming at that extent | **Unchanged from measured.** 64 × 64 = 4,096 level-0 cells, `LoadingRange` 25600 (`WorldPartitionRuntimeSpatialHash.h:225-232`). Region two is a second world with the same numbers, never a larger grid. |
| Editor open cost | **Unchanged from measured.** `ScanSynchronous` covers one map's `__ExternalActors__` (`ActorDescContainer.cpp:81-85`). `/Game/Alpine8K` already *is* this configuration, so the cost is today's cost, permanently, at any N. |
| OFPA package count | **Unchanged: 1,357 files, 3.66 GB per map.** N regions = N folders of 1,357, never one folder of 1,357N. |
| Source control | **Unchanged.** A region's OFPA folder is the change boundary; `git status` stays readable; a bad checkout cannot cross a region. |

**(b) is the option whose answer to every scaling question is "the number already measured, forever."**

### The mechanism, cited

`FSeamlessTravelHandler::StartTravel` — `World.cpp:8274`, logging at `:8289`, loading asynchronously via `SeamlessTravelLoadCallback` (`:8209`) and `AsyncLoadAlwaysLoadedLevelsForSeamlessTravel()` (`:8266`, defined `:5512`). Enabled by `bUseSeamlessTravel` — `GameModeBase.h:577-579`: *"Whether the game perform map travels using SeamlessTravel() which loads in the background and doesn't disconnect clients"*. Routed through `GetDefault<UGameMapsSettings>()->TransitionMap` (`World.cpp:8330`, empty-map fallback at `:8367`).

**The transition map is the airship.** WORLD_VISION ruling 2 confirms airship travel (`:159-161`); Option A's own text already says a transition behind a sky sequence "is cheap, robust, and what the reference class does" (`:226-228`).

### The trap to avoid

Do **not** compose regions as Level Instances in a hub world:
```cpp
// Move level instance actors to the main world partition
Partitioned UMETA(DisplayName = "Embedded"),
```
`LevelInstanceTypes.h:62` — and it is `ALevelInstance`'s constructor default (`LevelInstanceActor.cpp:33`). Embedding folds every child actor into the parent partition: option (a) with extra indirection. The alternative `LevelStreaming UMETA(DisplayName = "Standalone")` (`:64`) does use level streaming, and `ULevelInstanceSubsystem` handles `UWorldPartitionLevelStreamingDynamic` children (`LevelInstanceSubsystem.cpp:762-790`) — **code path found, production support not established, unmeasured.** Seamless travel needs no such caveat.

### Four rules that follow

1. **One region = one recipe = one map = one `__ExternalActors__` folder.** `recipes/<region>.json` → `/Game/Regions/<Region>`. `Alpine8K` already has this shape; only the path convention is new. Pipeline rule 3 survives intact.
2. **A shared transition map** at `/Game/Regions/_Transit`, set as `UGameMapsSettings::TransitionMap`.
3. **Shared content lives outside every region map** — materials, foliage types, palette, surface sets. Already true; making it explicit stops region two forking `M_Alpine8K`.
4. **A gate** (non-negotiables 1 and 3): refuse to open or build a map whose `__ExternalActors__/<Map>` file count exceeds a declared ceiling in the recipe. Make the catastrophic state unreachable rather than guarded — the count is a directory listing. This is the only mechanical prevention against a future session quietly merging two regions.

### Region-edge debt, stated plainly

(b) relocates rather than eliminates this. WORLD_VISION:142-145 already records it: *"**The region boundary is a hard edge**, clearly visible at altitude … what does a region edge look like from an airship?"* Now a live **design** item (already `BACKLOG.md:151-153`) — a coastline, caldera rim, impassable massif or sea. The honest cost of this ruling. Option (a) would have traded it for a heightmap-continuity constraint on every regional recipe, which is strictly worse because it breaks per-recipe determinism, which is design pillar 1.

---

## 7. The AAA reference class, honestly

| Title | What it does | Team |
|---|---|---|
| **The Witcher 3** | **Separate maps with loading screens between them** — White Orchard, Velen/Novigrad, Skellige, Toussaint. Each internally contiguous and streamed. | CDPR, hundreds |
| **Elden Ring** | Contiguous overworld **plus** hundreds of separately-loaded legacy dungeons and stacked underground layers. Effectively hybrid. | FromSoftware, ~300 |
| **Horizon Forbidden West** | One contiguous streamed world, no internal loading. Custom Decima streaming, not WP. | Guerrilla, ~300+ |
| **Cyberpunk 2077** | One contiguous world, no loading screens. Custom REDengine streaming. | CDPR, ~500 |

*(Team sizes and title structures recalled, not citable from this install — flagged per the evidence standard. Engine claims in §1-6 are all cited.)*

**WORLD_VISION already ratified the multi-map class.** `:172` names "Witcher 3 / Final Fantasy / Tales / Amalur". Witcher 3 — the one I can characterise confidently — is separate maps; Final Fantasy and Tales titles are conventionally region-and-transit structured. Ruling (b) is consistent with a decision already made; ruling (a) would quietly re-pick the reference class to Cyberpunk/Horizon without saying so.

**And the sobering arithmetic.** 8,128 m × 8,128 m = **66.06 km²** — in the neighbourhood of Witcher 3's largest single landmass. **One region here is already one Velen.** So "how many regions" is "how many Velens does one person build", and the composition model should be chosen to make **region one shippable alone**, not to make region four possible. (b) does that.

**Achievable by one person with this pipeline: (b), and only (b).** The contiguous titles are 300-500 person teams with bespoke streaming tech and build farms. This machine has 31.4 GB RAM, 27 GB of commit headroom at the Nanite peak, and one operator whose most expensive recorded failure mode is a builder reporting success over a graph that is wrong.

---

## 8. Scope, and the nullable fields

**Decides:** composition model (one WP world per region), travel mechanism (seamless travel via transition map), rejection of Level-Instance composition, four structural rules.

**Does not decide** — these are Ryan's and are downstream: how many regions; where region two is; what a region edge looks like from an airship; whether the transition is diegetic or masked.

**Explicitly nullable fields.** Each is `null` because the lane is read-only and forbids launching the editor — **null means "not measured", never "measured and fine"** — and each states what closes it:

| Field | Null means | What closes it |
|---|---|---|
| Peak RAM / wall time, editor opening a 2- or 4-region world | Unmeasured. I hold **a source line (`ActorDescContainer.cpp:81-95`) and per-region arithmetic, not a measurement.** This is the ruling's honest weak point. | A two-region world — which nobody should build merely to find out. Cheaper proxy: time `ScanSynchronous` against a duplicated `__ExternalActors__` tree offline. |
| Seamless-travel overlap-window memory | Unmeasured. Code path confirmed (`World.cpp:8274, 8330`); cost unknown. | First attended run of region-two travel, instrumented at the transition. |
| Standalone Level Instance over a landscape-bearing partitioned world | Support status not established. Code path found (`LevelInstanceSubsystem.cpp:762-790`). | Moot unless rule 3 above is ever revisited. |
| `UWorldPartitionRuntimeHashSet` maturity tier | Unobtainable by the specified method — engine code (`WorldPartitionRuntimeHashSet.h:159-162`, selected via `WorldPartition.cpp:1303`) with **no descriptor to read**. No experimental marker found in header or cpp. | Not needed: not recommended, not evaluated; the default spatial hash suffices at these extents. |
| §7 team sizes and the Witcher 3 landmass comparison | Recalled, not sourced from this install. The **66.06 km²** figure is computed from the ratified 8,128 m and is solid; only the comparison is recalled. | External citation, if the comparison is ever load-bearing. It is not — the ruling stands on §4a. |