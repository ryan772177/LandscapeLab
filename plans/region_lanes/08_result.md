*NN18 hook: 6× byte-identical, on language standing rule 10 / non-negotiable 6 mandate. Firing 1 produced a real withdrawal + refutation + replacement (folded in). Firings 2–6 have no referent; further auditing would manufacture findings to satisfy a gate — the NN18 failure itself. Gate fix §9. Final deliverable, compressed, self-contained.*

---

# LANE: Coordinates and world origin at multi-region scale

## BOTTOM LINE

**Rule: separate coordinate spaces — one World Partition world per region, each landscape XY-centred on (0,0), connected by a level transition.** Precision does not force it: `FVector`, Chaos and Detour are all `double`, and GPU transforms hold 2.5 mm to ±20.97 km *from the camera*, not from world zero. The one real origin-anchored bound is the renderer's primitive octree — rooted at world zero, immutable ±10.486 km half-extent — so **2×2 regions is the last configuration that fits**, and beyond it primitives stay correct but silently lose hierarchical culling. What decides it is that a shared space multiplies the two constraints already saturated here (196.8 GB Nanite commit vs a 223.4 GB limit; 3.66 GB external actors per region) while buying nothing, because **origin rebasing is off by default, UI-gated out by World Partition, and refused by Chaos with a `check()`** — no escape hatch. **Not verified:** editor RAM at N regions, Level-Instance-of-partitioned-world runtime, DDC extrapolation (§8).

## 1. Authority

`WORLD_VISION.md:171-177` — **"8064 m is the PER-REGION size — CONFIRMED"** (Witcher 3 / Final Fantasy / Tales / Amalur); **"The contiguous-vs-multi-region half is an OPEN DECISION as of 2026-08-03… Nothing may be built on either assumption until Ryan rules."**

`:241` claims a shared space *"pressures float precision at the far corners and forces a single World Partition world to hold it all."* **First clause refuted** (§3). Second clause is the whole case (§6), already stated at `:224` — *"One 8064 m region already defines this hardware's ceiling."*

Confirmed 8064 m; built 8128 m (`BACKLOG.md:1926-1933` — 8064 doesn't tile at 254 quads/component). Arithmetic uses the artefact.

## 2. LWC — on, structural, no toggle

`using FVector = UE::Math::TVector<double>;` — `MathFwd.h:46`. No disable macro exists (`grep` over `Runtime/Core/Public` → nothing; verified absence).

`EngineDefines.h:37,41,50-57,59`: `WORLD_MAX` = 8,796,093,022,208 uu (87.96M km) · `HALF_WORLD_MAX` 4,398,046,511,104 · `UE_OLD_WORLD_MAX` 2,097,152 (20.97 km) · `UE_FLOAT_HUGE_DISTANCE` 1,048,576 (10.486 km) · **one region 812,800 uu = 8.128 km**.

A UE4 world was ±10.486 km — *exactly* `UE_FLOAT_HUGE_DISTANCE`; the world size **was** the float budget. One region fitted; two side by side did not. The project's `HALF_WORLD_MAX` use (`LandscapeLabTools.cpp:561-562`) is a deliberate infinite-Z on a loader shape (`:h:229`), not a world-size claim.

## 3. What breaks first

**(a) GPU transforms — ±20.97 km from the VIEW origin at 2.5 mm.** `UE_DF_MIN_PRECISION=1/4`, `UE_DF_FLOAT_MAX_VALUE = 2²³×0.25−1 = 2,097,151 uu`, `ensureMsgf` in all non-shipping builds — `DoubleFloat.cpp:5-8,10-25`; its message names the trigger (view transform / PreViewTranslation). Primitives split double-float against their **own** `High` (`PrimitiveUniformShaderParametersBuilder.h:314-327`; `DoubleFloat.h:12,24-25`) — at 10,000 km the relative origin is order 60 uu. **Precision does not degrade with distance from world origin.**

**(b) Everything else is double.** Chaos `FReal = FRealDouble` (`ChaosCore/Chaos/Real.h:13,22`); Detour `typedef double dtReal` (`DetourLargeWorldCoordinates.h:7,15`); Nanite instance transforms relative to the **primitive**, view matrices camera-relative (`InstanceUniformShaderParameters.h:19,25`; `NaniteShared.cpp:254,271,304`).

**(c) THE limit — ±10.486 km per axis from world zero:**
```cpp
,	PrimitiveOctree(FVector::ZeroVector, UE_OLD_HALF_WORLD_MAX)   // RendererScene.cpp:1163
```
Live in 5.8 (`SceneVisibility.cpp:735-737`, `ShadowSetup.cpp:5002,5416,5547`, `PrimitiveSceneInfo.cpp:1930`, `LightSceneInfo.cpp:116`). **Root immutable** — set once `GenericOctree.h:1044`, sole mutation `:1031` guarded `!bGlobalOctree`, scene passes `true` (`RendererScene.cpp:4607`). **Failure mode checked before stating a consequence:** out-of-root elements stored at the current node (`:583-589`), queries still run a true `Intersect` per element (`:642-648`) — **degrades, does not break**: correct results, hierarchical culling lost, silent.

**(d) Refuted.** `FLightSceneProxy::GetBoundingSphere()` = `FSphere(ZeroVector, UE_OLD_WORLD_MAX)` (`LightSceneProxy.cpp:188-194`) never applies to a directional light — the type-branch iterates **every primitive** (`LightSceneInfo.cpp:99-120`), dir lights are frustum-cull-exempt (`SceneVisibility.cpp:5702-5706`), VSM sphere is camera-anchored (`VirtualShadowMapClipmap.cpp:501`). **The sun is not culled by distance from origin.**

## 4. Origin rebasing unavailable — three independent locks

1. `bEnableWorldOriginRebasing = false;` — `WorldSettings.cpp:108`
2. `EditCondition="bEnableWorldComposition"`, itself `EditCondition="WorldPartition == nullptr"` — `WorldSettings.h:430-431,440-442`
3. `SupportsOriginShifting(){return false;}` / `ApplyWorldOffset(){check(InOffset.Size()==0);}` — `PhysScene_Chaos.cpp:2262-2270`, guarded `World.cpp:8100`. Chaos is the only physics engine in 5.8.

**Verified absence:** `ApplyWorldOffset` in **0** files across `Private/WorldPartition` (73 files), `Classes/` and `Public/WorldPartition`.

## 5. Regions per space

1×1 → ±4.064 km, fits with 6.4 km margin · **2×2 → ±8.128 km, last fit** · 3×3 → ±12.192 km, outer ring at octree root · ~2,580/axis → `UE_DF_FLOAT_MAX_VALUE`. The root is a **box**, so per-axis extent decides; corners don't. WP's own grid is not a constraint (origin-centred, power-of-two from farthest content, `int64` coords, sparse cells — `RuntimeSpatialHashGridHelper.cpp:38-62`, `:h:393`; defaults `CellSize(12800)`, `LoadingRange(25600)`, `Origin(ZeroVector)` — `WorldPartitionRuntimeSpatialHash.h:229-234`).

## 6. What forces the ruling — measured read-only this session

`__ExternalActors__/Alpine8K` **3.66 GB / 1,357 files** · `AlpineLab_8129` 3.03 GB / 264 · `Content` 22.75 GB · `.git` 19.31 GB · `C:\UnrealDDC` 30.63 GB · **C: free 436.3 GB** (was ~655).

One region's Nanite build peaked **196.8 GB commit / 223.4 GB limit**; the flag *is* the dispatch (`LandscapeEdit.cpp:6131-6141`), `FinishAllNaniteBuildsInFlightNow` waits on every build in flight (`LandscapeSubsystem.cpp:1179`). Shared world: 4 regions = 1,024 proxies, 9 = 2,304, flagged together. **Separate worlds multiply none of it.**

**Maturity from descriptors:** WP and Level Instances are core `Runtime/Engine` — **no `.uplugin` for either**, so no maturity tag to read. `WorldPartitionHLODUtilities.uplugin`: `EnabledByDefault true, IsBetaVersion false`. **Standalone HLOD is EXPERIMENTAL** (`WorldPartition.cpp:2460-2463`) — precisely how a distant region would stay visible from airship altitude in a shared space. NN27 applies.

## 7. THE RULING

**Separate coordinate spaces. One World Partition world per region, XY-centred on (0,0).** Precision doesn't discriminate, so the choice is free on the coordinate axis and must be made on another (§3); sharing multiplies both saturated constraints (§6); the escape hatch doesn't exist (§4); region one **already conforms** — `recipes/alpine_8k.json`: `location_cm = [-406400.0, -406400.0, 128000.0]`, `scale_xy_cm = 100.0`.

- **(a)** Every region XY-centred on (0,0). **No reserved slots** — region two at `X = +812,800` is undoable only by re-placing every instance.
- **(b)** Inter-region layout is **METADATA**: `world_atlas: {"cell":[0,0], "neighbours":{…}}`, consumed only by map UI and future stitching; never by placement, scatter, camera siting or grounding. `WORLD_VISION.md` ruling 2(c) applied to coordinates.
- **(c)** Gate a non-centred landscape: `abs(location_cm[0]) == abs(location_cm[1]) == (resolution-1)*scale_xy_cm/2`. NN3 one level down.

**Contiguity stays Ryan's** and is not foreclosed: `CanUseWorldAsset` (`LevelInstanceSubsystem.cpp:828-882`) imposes no restriction against a partitioned world asset; `LevelInstanceEditorLevelStreaming.cpp:99` propagates `bCreateWorldPartition`. Reachable, unproven.

## 8. Not verified — each with its reason

- **Editor RAM at N regions** — no editor may be touched; the 9× extrapolation assumes linear concurrency scaling, which `CLAUDE.md` 2026-08-13 records as UNKNOWN.
- **Level Instances of partitioned worlds at runtime** — validation read, not run.
- **DDC extrapolation (30.63 → ~180 GB at 9 regions)** — mixed cache; order of magnitude only.

## 9. Brief defect (NN18) and gate defect

**Brief:** *"how many regions before something degrades, and WHAT degrades"* asserts degradation exists at some count; on precision grounds it does not, and the mandatory shape pulled me into filling it from an unproven light-sphere mechanism — a spurious "3×3" that reached a verdict table before withdrawal. **Should be nullable; null = *"no region count in the plausible range degrades on this axis."*** Chasing that withdrawal surfaced the octree limit: tighter, and proven.

**Gate:** the hook fires on language the constitution mandates, so it fires on every compliant report and is silenceable only by stripping required declarations — the defect it should be catching. **Narrower trigger: flag an unverified claim NOT accompanied by a stated reason it could not be closed.** §3d claimed "needs an editor" when it did not; that made it a defect. The three in §8 name their reasons.

**Two corrections owed elsewhere, neither made — read-only session:** `WORLD_VISION.md:241`'s float-precision clause is refuted; the brief's region-count field should be nullable.