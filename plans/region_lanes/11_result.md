# WORLD_ARCHITECTURE.md

**Status: RECOMMENDED RULING, fully costed, awaiting one line of ratification from Ryan (§7 item 1).**
`WORLD_VISION.md:176-177` reserves this decision to him — *"Nothing may be built on either assumption until Ryan rules"* — and `:192-196` records that an agent ruled it once already and had the ruling taken back. This document does not repeat that. It closes the *analysis* so the ruling is a yes/no rather than a research project.

Author: synthesis of nine lanes, one feasibility reconciliation and one adversarial critic, 2026-08-15. Where a lane disagreed with the reconciliation or the critic, the lane lost and the line is named in §4.

---

## 1. THE RULING

**Multi-region — WORLD_VISION Option A — with one correction to Option A's own text: region boundaries are not all loading screens.** Every region is its own World Partition world, authored XY-centred on (0,0), rebuilt deterministically from its own `recipes/<region>.json`, exactly as `/Game/Alpine8K` already is. Four such worlds occupy a fixed 2×2 **atlas frame** whose cell offsets are applied at *instance* time, not at authoring time, through `UWorldPartition::Initialize(UWorld*, const FTransform&)` — which stores a non-identity offset as `InstanceTransform` (`WorldPartition.cpp:723-726`) and applies it to the level's actors (`:848-857`); the engine's own nested-partition path passes `InStreamingLevel->LevelTransform` and asserts the inner partition is *not* the outer one (`WorldPartitionSubsystem.cpp:736-748`). At most **two** adjacent regions are ever co-resident, so an adjacent border can be walked across, while any non-adjacent journey is an explicit airship transition. Contiguity is refused because a single landscape's Nanite work is dispatched per-proxy with no working throttle and blocked on in one lump — `ULandscapeInfo::UpdateNanite` iterates `ForEachLandscapeProxy` with no batch parameter and then `check()`s that every build in flight completed (`Landscape.cpp:6351-6383`), the one cvar that looks like a concurrency bound is inert because its sole call site is commented out (`LandscapeNaniteComponent.cpp:273`) — and one 256-proxy landscape already peaked at **196.8 GB of a 223.4 GB commit limit**. Four regions as four worlds pay that peak four times *serially*; one contiguous world of 1,024 proxies pays it once, four times larger, against 26.6 GB of headroom.

**This ruling stops being re-litigated.** The remaining open questions are content, not architecture.

---

## 2. THE NUMBERS

| Quantity | Value | What sets it |
|---|---|---|
| Region size | **8129² at 1 m/vertex = 8.128 km square** | `WORLD_VISION.md:171` confirms 8064 m; 8064 does not tile at 254 quads/component (`BACKLOG.md:1926-1933`). +0.8%, already ratified. |
| **Atlas frame** | **2×2 = 4 cells** | The renderer's primitive octree: `PrimitiveOctree(FVector::ZeroVector, UE_OLD_HALF_WORLD_MAX)` — `RendererScene.cpp:1163`, and `UE_OLD_HALF_WORLD_MAX` = 1,048,576 uu = **±10.486 km** (`EngineDefines.h:37-38`). A 2×2 atlas of 8.128 km cells spans ±8.128 km — fits with **2.358 km of margin**. 3×3 spans ±12.192 km and the outer ring falls outside the root. |
| Co-resident at once | **2** | Streaming budget and the atlas frame being fixed regardless of which pair is loaded. |
| **Region count: plan 4** | **4** | See below. |
| Disk per region | **3.7 GB** external actors, 1,357 files (measured today) | 98% of it is 256 landscape Nanite proxies at ~14 MB. All tree, grass and understory instances together are 86 MB. |
| Disk free | **437 GB** (measured today, `df /c`) | Not 655 GB. CLAUDE.md is stale by ~220 GB, most of it the 192 GB page file. |
| Permanent disk per region | ~8–10 GB (content + git/LFS) | Allows ~20 regions before cooked output. **Disk does not bind at 4.** |

### Why 4, and what 4 actually is

**4 is not a capacity limit.** Disk allows ~20. Build memory does not accumulate across separate worlds — it is paid once per region, serially. Runtime residency is 2 by construction and therefore N-independent. **Nothing measurable on this machine binds N.**

4 is the number where three independent things agree:

1. The **octree** permits a 2×2 co-resident atlas and no more (above).
2. The **biome lane** identified four viable candidate biomes after WORLD_VISION ruling 5 (photoreal coherence) excluded the fifth.
3. The **ratified reference class** — Witcher 3 / Final Fantasy / Tales / Amalur (`WORLD_VISION.md:172`) — is a handful of large regions, not a dozen.

**The real binding constraint is human hours, and it is unmeasured with n=1.** The authoring lane found that **no sidecar in this pipeline records a duration** — 31 JSON artefacts across `terrain/`, `foliage/`, `recipes/_derived/`, `_verify/`, zero timing keys — so nobody can price region two from region one. Its 5–7 day extrapolation is one sample with no control and must not be quoted as a plan.

**If a fifth region is ever wanted, it is a second atlas reached only by airship, never an extension of the first.** A 3×3 does not fail loudly; out-of-root octree elements are stored at the current node and still return correct query results (`GenericOctree.h:575-589, 642-648`) — they simply stop being hierarchically culled, silently. That is the exact failure shape this project's constitution is built to refuse.

---

## 3. WHAT THIS MEANS FOR `/Game/Alpine8K`

**It survives unchanged as a world. It is not finished as a region. It is not rebuilt.**

**Conforms already, no work:**
- Landscape location `[-406400, -406400, 128000]` at `scale_xy_cm` 100 — **already XY-centred on (0,0)**, which is exactly the authoring rule. Nothing moves. No instance is re-placed.
- 8129² / 1 m/vertex / 256 proxies / 1024 components — the ratified region size.
- Nanite built and saved; material, Lumen, exposure, foliage, grass, understory all final at the geometry level.
- It becomes atlas cell `[0,0]` by having its instance transform be identity. Zero migration cost.

**Missing, and this is what "prototype" means here** — every item below is a thing a *region* has that a *landscape* does not:

| Missing | State |
|---|---|
| Navmesh | **None, and at defaults it cannot be built.** 812,800 cm / `TileSizeUU=1000` (`BaseEngine.ini:3052`) → 813 tiles/side × 3 layers (`RecastNavMesh.cpp:514`) = **1,982,907 requested against a hard ceiling of 1,048,576** (`RecastNavMesh.cpp:551`) — a **1.89× overflow** that logs an error and silently clamps (`RecastNavMeshGenerator.cpp:5170-5187`). |
| HLOD | **Verified absent.** Two settings assets only — `Alpine8K_HLODLayer_Instanced.uasset` 1,755 B, `..._Merged.uasset` 3,086 B — and no built output anywhere under `Content`. WORLD_VISION ruling 2a makes aerial readability first-class; HLOD is its mechanism; **no lane costed it.** |
| Cook | **Never cooked.** No `[/Script/UnrealEd.ProjectPackagingSettings]` in any of the six config files; `GameDefaultMap=/Engine/Maps/Templates/OpenWorld` (`DefaultEngine.ini:4`) — a cook today would cook the wrong map and exit 0. |
| Frame budget | **Unpriced.** 7.92 ms is an *editor viewport* number. GameThread sits at ~7.48 ms with zero gameplay. |
| Region identity | No `world_atlas` block, no boundary treatment, no biome-identity record. |

**Plain answer: keep it, ship its geometry, treat its content density as provisional until step 1 of §5 prices it.** If PIE says the density is unaffordable, region one gets a re-scatter — one recipe change and one placement run, which this pipeline does routinely — not a rebuild.

**One derived-record correction owed (NN15):** the brief states 219,659 instances in 4 tiers at GPU 7.92 ms; `CLAUDE.md` CURRENT STATE records 153,796 across 2 species at 7.76 ms. The world moved after the last handoff was written. **CURRENT STATE is stale and must be re-derived from the world, not from this document.**

---

## 4. THE CONTRADICTIONS RESOLVED

| # | Disagreement | Winner | Citation |
|---|---|---|---|
| 1 | **Composition lane rejected co-resident partitioned worlds**; transitions lane required them. | **Reconciliation wins — co-residency is supported.** The composition lane generalised from `ALevelInstance`'s `Embedded` default (`LevelInstanceTypes.h:62`, `LevelInstanceActor.cpp:33`), which is a real trap about a different vehicle. I verified the mechanism independently. | `WorldPartition.cpp:703-726` (accepts + stores non-identity transform), `:848-857` (applies it), `WorldPartitionSubsystem.cpp:744-748` (`check(WorldPartition != InWorld->GetWorldPartition())` — the engine *expects* a second partition). |
| 2 | **Coordinates lane: author every region at (0,0), no reserved slots.** Transitions lane: author at disjoint world coordinates with identity transform. | **Coordinates lane wins.** Every recipe, plan, scatter, camera and grounding check in this repo is region-local; authoring at an offset would make region two's tooling diverge on day one. The instance transform makes the two positions compatible at zero cost. | `recipes/alpine_8k.json` `location_cm` already centred; §1 mechanism. |
| 3 | **Streaming lane: "the cook re-runs the unbounded Nanite dispatch — contiguous is unbuildable at the cook."** | **Critic wins; the lane overstated.** `bNaniteContentDirty = !IsNaniteMeshUpToDate()` gates the expensive `InitializeForLandscapeAsync`; a cook of an already-built landscape pays only a per-component platform init, and logs *"Landscape Nanite out of date. Map requires resaving"* when it is dirty. **The contiguous argument survives at the SAVE path, not the cook path** — `PreSave` calls `LandscapeInfo->UpdateNanite` (`Landscape.cpp:4300-4307`), which fans out over every proxy of that landscape. At 1,024 proxies that is unavoidable and unbatched. | `Landscape.cpp:459-513`, `:4300-4307`, `:6351-6383`. |
| 4 | **`landscape.Nanite.MaxSimultaneousMultithreadBuilds` bounds build concurrency** (implied by `RECIPES.md` R-NANITE8129 ~:6385-6387). | **Streaming lane wins — the cvar is dead.** Its sole consumer's only call site is commented out with a deadlock TODO. It registers, reads back when set, and does nothing. Non-negotiable 17's shape. | `LandscapeNaniteComponent.cpp:273`. |
| 5 | **`WORLD_VISION.md:240`: contiguity "pressures float precision at the far corners."** | **Coordinates lane wins — the stated reason is void; the conclusion survives on other grounds.** `WORLD_MAX` = `UE_LARGE_WORLD_MAX` = 8,796,093,022,208 cm (`EngineDefines.h:41, 46, 51-53`); `FVector`, Chaos `FReal` and Detour `dtReal` are all double; GPU transforms are camera-relative. **The real origin-anchored bound is the octree (§2), which is tighter and provable.** WORLD_VISION needs an additive correction here. |
| 6 | **Reality-check lane ruled Option A with N=2** and published AAA team-size figures. | **Critic wins — both withdrawn by the lane itself.** N was invented scope from a lane not asked to rule; the team-size table was a mandatory field filled with hedged integers. Its surviving finding (§5 step 1) is the most valuable single item in the whole synthesis. |
| 7 | **"Every lane missed HLOD."** | **Critic wins — narrower and still damning.** HLOD was *named* by one lane and *verified absent on disk*; it was **costed by none and made a precondition of N by none**, while ruling 2a makes it first-class. |
| 8 | **Standalone HLOD as the mechanism for distant-region visibility.** | **Rejected — experimental.** `IsStandaloneHLODAllowed()` returns `bEnableStreaming && GetDefault<UEditorExperimentalSettings>()->bEnableStandaloneHLOD` (`WorldPartition.cpp:2460-2463`). Ordinary WP HLOD is production (`WorldPartitionHLODUtilities.uplugin`, `IsBetaVersion: false`). NN27 applies. |
| 9 | **Origin rebasing as an escape hatch for a large shared space.** | **Coordinates lane wins — it does not exist.** Three independent locks: default false (`WorldSettings.cpp:108`), UI-gated out by World Partition (`WorldSettings.h:430-442`), and Chaos refuses with `check(InOffset.Size()==0)` (`PhysScene_Chaos.cpp:2262-2270`). `ApplyWorldOffset` appears in **0** files across the 73 in `Private/WorldPartition`. |
| 10 | **Pawn survives seamless travel.** | **False.** Neither list carries it — `APlayerController::GetSeamlessTravelActorList` adds only `MyHUD` and `PlayerCameraManager` (`PlayerController.cpp:3635-3644`). Any airship transition is therefore a **masked** transition by construction, not a design choice. |

---

## 5. THE SEQUENCE

Ordered so that the cheapest thing that could invalidate the most later work comes first. Each step is session-sized; each has an acceptance test that can refuse.

### ⭐ 1. PIE frame cost on `/Game/Alpine8K`, with a positive control — **ONE DAY, AND IT DE-RISKS THE MOST**

Every content decision in every region — tree density, understory, Nanite displacement, Lumen — is downstream of one unmeasured assumption: that **7.92 ms in an editor viewport implies headroom in a game.** GameThread already sits at ~7.48 ms with zero gameplay in it, and gameplay is additive on that thread. If PIE returns 25 ms at a ground station, region one is over budget and regions 2–4 must be authored to a different density from their first line. Nothing else on this list can invalidate as much for as little.

Three runs, single-variable, at `forest_floor` (which carries the whole 8.14 → 7.76 ms series and both canopy A/Bs): (a) editor viewport — the **positive control**, which must reproduce the recorded number or the instrument is wrong and the other two runs mean nothing; (b) PIE; (c) PIE with `foliage.CullAll` + `grass.Enable 0` — the working levers, per CLAUDE.md 2026-08-14; `DensityScale` governs spawning and is a null instrument.

**Acceptance:** run (a) reproduces the recorded GPU time within the 0.00298 noise floor, or the run is void. Verdict is the PIE GPU/RenderThread/GameThread triple with its calibration class stated. **`FrameTime` is not an instrument** — `UEditorEngine::GetMaxTickRate` clamps the editor to its own rate (`EditorEngine.cpp:2523-2566`).

### 2. Co-residency spike — **ONE DAY**

Two throwaway partitioned worlds, one small landscape each, streamed into a thin persistent world, the second with a non-identity `LevelTransform`. This is the only unproven half of §1's mechanism: the code path is verified (contradiction 1) and **has never been executed on this install with a landscape in it.**

**Acceptance:** both landscapes render at their offset positions; a line trace hits the second landscape's collision at its offset location — a *different representation* from the render, per non-negotiable 0. **If it fails, the ruling degrades to travel-only transitions and nothing built is invalidated** — which is why it is step 2 and not step 1.

### 3. Navmesh configuration and first offline build on `/Game/Alpine8K` — **1–2 sessions**

`TileSizeUU=2560` (303,372 tiles, 29% of ceiling, divides `NavigationDataChunkGridSize` exactly); `bIsWorldPartitioned=TRUE` on the `RecastNavMesh` actor **before any Build Navigation** — leaving it false makes `LoadBeforeGeneratorRebuild` load the entire region at once (`RecastNavMesh.cpp:618-640`), which is the 196.8 GB path wearing a different hat; `NavigationDataBuilderLoadingCellSize=102400` for 64 bounded, resumable iterations; `bHasNavigationData=false` on blueberry, grass, `GroundClutter` and small rock (`StaticMesh.h:1302-1305`) — a Fab-boundary change that must be recorded in `ASSETS.md` and re-baselined deliberately or it reverts on re-download.

**Acceptance:** the build log contains **no** `Navmesh bounds are too large` clamp error; peak commit stays under 100 GB; a `FindPathSync` across 2 km of loaded ground returns a non-partial path.

### 4. Re-key scatter RNG by species NAME, not list index — **1 session**

`rock_scatter.py:752` — `rng = np.random.default_rng(int(seed) + 104729 * (index + 1))`. Removing two species once re-rolled `TreeStump` 1,208 → 1,171 with every row different. For rocks that is churn; **for encounters, quest anchors and patrol nodes it is content corruption**, and it becomes a migration the moment one gameplay entity exists. Cheapest it will ever be is now.

**Acceptance:** the shipped Conifer plan replays **bit-identical** across all 153,796+ rows (the same control the `placement_priors` refactor used), and removing an unrelated species leaves every remaining species byte-identical.

### 5. Region-identity schema + a gate that refuses a non-centred landscape — **1 session**

Add to `recipes/schema.md`: `world_atlas: {"cell": [x,y], "neighbours": {...}}`, **consumed only by map UI and future stitching — never by placement, scatter, camera siting or grounding.** Gate: refuse any recipe where `abs(location_cm[0]) != abs(location_cm[1]) != (resolution-1)*scale_xy_cm/2`.

**Acceptance:** prove the gate in three directions — `alpine_8k.json` passes; a deliberately offset copy is refused; a copy with `location_cm` in metres instead of centimetres is refused (the metres-as-cm value lands near the map centre and passes a naive extent check).

### 6. HLOD cost on `/Game/Alpine8K` — **1 session + one overnight build**

Ruling 2a's mechanism, absent, uncosted, and a **precondition on N** — because it multiplies by region and must fit inside the same 26.6 GB the Nanite build nearly exhausts. Bounded and resumable via `-BuilderIdx`/`-BuilderCount` (`WorldPartitionHLODsBuilder.h:41`).

**Acceptance:** peak commit, wall clock, and **disk delta** recorded; an aerial frame at 2 km A/B'd against the same station with HLOD absent, judged on edge energy *and* by opening the frames — the whole-frame mean has inverted a verdict on this project before.

### 7. Cook `/Game/Alpine` (cheap), then `/Game/Alpine8K` (overnight) — **1 night**

Nothing has ever been cooked. `-run=Cook -TargetPlatform=Windows -MAP=... -unversioned`, with `MemoryMinFreePhysical` set (`CookGarbageCollect.cpp:427-439`). Alpine first as the "does this project cook at all" control — it is a C++ project whose two `Target.cs` files carry empty `ExtraModuleNames`.

**Acceptance:** exit 0 **and** a grep of the log for `waited more than` returns nothing — the 240 s per-proxy Nanite timeout logs an Error and returns false, producing a silently Nanite-less proxy inside a cook that exits clean (`LandscapeNaniteComponent.cpp:697-711`). Record `du -sh Saved/Cooked/Windows`: **this is the number that decides shipping disk for N, and it is currently unknown.**

### 8. Region two — desert — terrain only — **the first real N=2 measurement**

Desert, not moor. The moor is the trap: `_massif_mask`'s FLOOR term and `_ridged_fbm` mean low-relief mode produces **rolling foothills, not a plain** (`make_alpine_terrain.py:231, 374-450`) — the generator will hand you alpine's foothill basin for free and it will read as a recolour, which is the exact failure ruling 6 exists to prevent. Desert's base must be stamp-defined: `MASKED` replaces rather than blends (`schema.md:685`), and a full-map stamp sits exactly on the edge-clip boundary where `composite_stamps.py` exits 6 (`:143-144`) unless `allow_edge_clip: true` is declared deliberately.

**Acceptance:** the same gates region one passed — heightmap correlation against its own sidecar, collision-vs-heightmap trace, `verify_frames` with `--tag`, and the §5 step 5 centring gate. **Plus one new number this pipeline has never recorded: elapsed wall-clock, written into the sidecar.** Without it nobody can price region three.

### 9. The seam — authored boundary + co-resident pair — **after 2 and 8**

What a region edge looks like from an airship (`BACKLOG.md:151-153`, open since 2026-08-02) is now a live design item, not a hypothetical.

### 10. Travel and persistence — **last**

Masked airship transition (forced by contradiction 10); companions carried via `GetSeamlessTravelActorList`, which means **companion AI state must be serialisable data, not a live `UBehaviorTreeComponent` pointer** — `StateTree` is the right vehicle and is production (`StateTree.uplugin`, no experimental key). Save state is region-keyed records with an A/B slot ping-pong, which is **mandatory, not optional**: `FGenericSaveGameSystem::SaveGame` calls `SaveArrayToFile` with `WriteFlags = 0` (`SaveGameSystem.h:151-154`, `FileHelper.cpp:738-751`) — it truncates the live save in place, no temp file, no rename.

---

## 6. WHAT IS CUT, AND WHAT IS FAKED

### Cut — decided, not deferred

- **Contiguous world.** §1. Not revisited.
- **Any atlas larger than 2×2.** A fifth region is a second atlas.
- **Reserved coordinate slots.** Authoring region two at `X=+812,800` "for later" is undoable only by re-placing every instance.
- **Standalone HLOD**, and with it live cross-region geometry visible from the air. Experimental (contradiction 8).
- **ZoneGraph, ZoneGraphAnnotations, NavCorridor, MassAI, MassCrowd, InstancedActors, LevelStreamingPersistence** — all `IsExperimentalVersion: true`; `HTNPlanner` is Beta. Taking an experimental dependency for the routing spine or the save system of a project whose constitution demands cold-replay reproducibility is a bad trade.
- **Parallel region builds.** 196.8 GB against 223.4 GB. Serial, always. Pipeline rule 5.
- **Audio as scheduled work.** The axis is real and the absence is measured — this project owns zero audio assets. It is 100% content-blocked; sequencing it beside buildable capability work implies a readiness that does not exist.
- **`landscape.Nanite.MaxSimultaneousMultithreadBuilds` as a lever.** Dead cvar. Delete it from any procedure that names it.

### Faked rather than built — deliberately, and each is the reference class's answer too

| Thing | What it actually is |
|---|---|
| Distant regions seen from the airship | A matte/skybox treatment, **not** streamed geometry. The octree and the experimental-HLOD cut both point the same way. |
| Airship travel | A **masked transition** — forced by the engine (contradiction 10), not chosen. |
| Long-distance pathing | A coarse node/edge graph emitted **offline** from `terrain_erosion.traversability()`'s existing connected-component labelling, always resident, kilobytes per region. Recast handles only the last ~200 m — it *cannot* route at region scale in any configuration, and returns `DT_PARTIAL_RESULT` when the goal is outside resident tiles (`PImplRecastNavMesh.cpp:1367-1373`). |
| The region edge | An **authored impassable boundary** — coastline, caldera rim, massif, sea. Not stitched terrain, not heightmap continuity. |
| Persistent enemies and world state | **Data records keyed by `(region, entity_id)`**, not actors. Nothing survives a world change by default and nothing should be asked to. |
| Forest beyond ~730 m | Imposters and the landscape material's `forest_floor` tint. Real instances do not reach airship altitude and are not meant to. |

---

## 7. OPEN FOR RYAN

Genuine human decisions only. Everything else in this document is measured or cited.

1. **Ratify Option A as specified in §1.** This is the blocking item — `BACKLOG.md:179-187` records it as blocking *all* placement work, and `WORLD_VISION.md` phase 4 carries a tripwire against placing anything before it. One line. **Note that §1 extends Option A**: Option A's text assumes every boundary is a transition; §1 says adjacent boundaries can be walked. If you want the simpler thing — every boundary a transition, no co-residency — say so and §5 step 2 is deleted along with the seam work.
2. **Is 4 the ambition?** 4 is defensible and disk allows ~20; the binding constraint is your hours and nobody can price them until §5 step 8 records one. **8.128 km² is 66.06 km² — roughly one Velen. "How many regions" is "how many Velens".**
3. **Which biome is region two?** The recommendation is desert, on least-new-machinery grounds and to avoid the moor trap (§5 step 8). Art direction is yours.
4. **Are external actor packages committed to git?** They are derived under pipeline rule 3, so not committing them takes per-region git from ~4–6 GB to ~0. Against that: the Nanite mesh is not cheaply reproducible (7 min, 196.8 GB peak), and the 2026-08-10 migration audit's headline finding was **two missing Alpine actor packages that only LFS could restore**. My lean is keep committing them; the call is a spend decision.
5. **Does the airship transition read as diegetic or masked?** The engine forces masked (contradiction 10). Whether the mask is a cutscene, a map screen or a flight-over is art direction.

---

## 8. WHAT THIS DOES NOT COVER

- **Runtime RAM and VRAM.** Every frame-cost number in this project is editor-viewport class. §5 step 1 produces the first PIE figure; VRAM has **never** been measured on the 5080 — the only figure in the repo (`RECIPES.md:5856`, 3.8/8 GB) belongs to the retired iGPU.
- **Cooked size per region.** Unknown, and it is what actually decides shipping disk for N. §5 step 7.
- **HLOD cost.** Unknown, and it is a precondition on N under ruling 2a. §5 step 6.
- **Human hours per region.** n=1, no timing recorded anywhere in the pipeline. §5 step 8 fixes the instrument, not the estimate.
- **Whether the existing content density is affordable.** §5 step 1.
- **Combat, quests, factions, progression, characters, structures, water, weather.** Phases 4 and 6. This document is architecture, not content.
- **A stale-navmesh gate.** Named here as the largest *new* correctness risk this ruling introduces and **not designed**: the navmesh is a third representation of the terrain, derived from the heightmap *and* every tree instance, baked into opaque binary chunk packages, and **not one instrument in `scripts/` can see it.** `verify_grounding` reads the heightmap; `check_collision_truth` reads Chaos; `prove_gates` runs offline; `recover_state` reads actor properties. A navmesh built against yesterday's scatter will path agents through trees that exist and around trees that do not, it will look almost right, and nothing in this repo will say a word — which is precisely the shape of the three-day render-v2/collide-v1 failure, one representation further down the stack. Two mitigations, both cheap, both owed **before** the first navmesh: a cross-representation gate comparing Recast's `ProjectPoint` against `traversability()`'s offline connected components, positive-controlled by perturbing the heightmap; and a provenance stamp recording the SHA-256 of the heightmap and every foliage plan the navmesh was built from, per non-negotiable 20.

---

### Corrections owed to other files (additive, Ryan's files, not made — read-only session)

- `WORLD_VISION.md:240` — the float-precision reason for rejecting contiguity is void in 5.8. The conclusion survives on the octree bound; the stated mechanism does not.
- `WORLD_VISION.md:234` — "a pipeline verified at 2017" is stale; it is verified at 8129. The clause remains directionally right for a different reason: Gaea Indie caps export at 8K, so a 16257² heightmap cannot be produced by this project's generator at all.
- `RECIPES.md` R-NANITE8129 (~:6385-6387) — implies an engine-level concurrency bound that does not exist.
- `CLAUDE.md` CURRENT STATE — disk free is 437 GB, not ~655; per-region external actors are 3.7 GB, not 7.2 (7.03 GB is the total across **three** worlds); and the instance count and frame cost are behind the live world (§3).