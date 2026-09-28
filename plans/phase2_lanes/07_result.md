# Physics, Interaction and Destruction — design brief

> **Audit note.** Two verification passes ran over this document and are folded in: claims stated more firmly than the evidence carried are downgraded to **[INFERENCE]** with their disproofs attached (§3e Trap 1, §3f), and the §0 budget rows are stamped **UNMEASURED** because a table invites a value in every cell and four of those were proposals, not readings. Every mandatory topic of the brief applied to this domain, so no section was filled with work that was not requested. §3f/P3 and §9 are scope extensions, marked inline, discardable without loss.

---

## BOTTOM LINE

**Keep `UCharacterMovementComponent` and do not adopt Mover**: `Mover.uplugin` is `IsExperimentalVersion: true`, its own README states "Many features are incomplete or missing. APIs and data formats are subject to change at any time", and its `Plugins` array force-enables NetworkPrediction (Beta), MotionWarping (Beta) and **Water (Experimental)** — and its whole purpose, rollback networking, buys nothing for a CONFIRMED single-player game. **The budget in the brief is the wrong budget**: physics ticks on the game thread between `TG_StartPhysics` and `TG_EndPhysics` (`LevelTick.cpp:1756-1772`) with `bTickPhysicsAsync = false` by default, so this domain competes for the ~9 ms of *game-thread* headroom left by the recorded 7.48 ms GameThread reading, not for the 8.7 ms of GPU. **The single biggest finding is that the 219,659 trees have no collision at all today** — `UFoliageType`'s constructor sets `BodyInstance.SetCollisionProfileName(NoCollision)` at `InstancedFoliage.cpp:640`, `place_foliage.py` only ever sets `mesh` and `cull_distance`, so the player currently walks through every tree; grass and blueberry can *never* collide because `LandscapeGrass.cpp:3170-3172` hard-codes `NoCollision` + `bDisableCollision = true`. **The biggest risk is that every physics number derived from the editor is measured on the wrong denominator**: the editor loads all 256 proxies, but at the World Partition default `LoadingRange = 25600` cm (`WorldPartitionRuntimeSpatialHash.h:232`) only ~700–1,400 trees are resident at runtime, which is two orders of magnitude cheaper and changes the ruling. **The tree meshes' simple-collision primitives are UNKNOWN and the instrument that would read them does not exist** — `measure_tree_packs.py` records no collision field, and the `collision_prims` field in `recipes/alpine.json` comes from the asset-registry `CollisionPrims` tag (`make_alpine_palette.py:138`), the same scan whose `Materials` tag this project already marked DO-NOT-CONSUME on 23 of 38 meshes.

---

## 0. The budget, re-derived

The brief says "8.7 ms of editor-class GPU budget remains". That is true and it is not this domain's constraint.

| Fact | Citation |
|---|---|
| Sync physics advances inside game-thread tick groups | `Engine/Source/Runtime/Engine/Private/LevelTick.cpp:1756` (`RunTickGroup(TG_StartPhysics)`), `:1772` (`RunTickGroup(TG_EndPhysics)`) |
| Async physics tick is OFF by default | `PhysicsSettings.cpp`, `UPhysicsSettings::UPhysicsSettings` — `bTickPhysicsAsync(false)` |
| Substepping is OFF by default | same ctor — `bSubstepping(false)`, `MaxSubstepDeltaTime(1.f/60.f)`, `MaxSubsteps(6)` |
| Max physics delta is 1/30 s | same ctor — `MaxPhysicsDeltaTime(1.f / 30.f)` |
| This project has configured **none** of it | `grep -i "physic\|chaos\|substep\|Collision" LandscapeLab/Config/*.ini` returns **zero lines** |

Recorded frame at `forest_floor` (CURRENT STATE 2026-08-14/15, editor viewport): **GPU 7.76–8.14 ms, RenderThread 4.88 ms, GameThread 7.48 ms.**

**Proposed budget. Every row is UNMEASURED — a proposal to be tested, NOT a reading.** Do not copy these into a recipe as though measured; that is the derived-record trap (non-negotiable 15).

| Line | Proposed | Status | Reasoning |
|---|---|---|---|
| Chaos solver + scene queries, game thread | 2.0 ms | **UNMEASURED** | leaves ~7 ms of the 16.67 ms frame for AI, gameplay, animation and streaming that is not yet tuned |
| Physics-driven draw cost (ragdolls, debris) | 0.3 ms GPU | **UNMEASURED** | ordinary meshes; the cost is draw calls, not simulation |
| Simultaneously **simulating dynamic** bodies | 64 | **UNMEASURED** | a rockslide, or one two-level fractured prop, or three ragdolls |
| **Static query-only** bodies resident | ~2,000 | **DERIVED** from the WP defaults in §3d — engine defaults, not this level's read values | resident tree count plus props |

The measurement that settles all four: a PIE session with `stat unit`, `stat Chaos`, `stat ChaosCounters`, `stat ChaosCollision` (`Runtime/Experimental/Chaos/Public/ChaosStats.h:8,13,17`), plus the exec `LIST ISM PHYSICS` (`InstancedStaticMesh.cpp:230`), which prints per-component `Num Bodies, Num Shapes`. Note its guard `if (ComponentWorld != InWorld || !ComponentWorld->IsGameWorld()) continue` at `:245-249` — **it returns nothing in the editor viewport and only works in PIE.**

---

## 1. Chaos in 5.8 — what is Production and what is not

**Chaos is the physics engine, full stop.** `ls Engine/Source/ThirdParty/ | grep -i "physx\|apex"` returns nothing — PhysX's third-party libraries are gone from this install. The Chaos runtime modules live at `Engine/Source/Runtime/Experimental/Chaos`, `ChaosCore`, `ChaosSolverEngine`. **That directory name is a directory, not a maturity tier** — these are core Runtime modules with no `.uplugin` and therefore no maturity flag to read. Treat the core rigid-body solver as Production; it is the only option.

Every row below was read from the descriptor in this install.

| Plugin | Path (under `Engine/Plugins/`) | Tier | EnabledByDefault | Ruling |
|---|---|---|---|---|
| **ChaosSolverPlugin** | `Experimental/ChaosSolverPlugin` | **Beta** | **true** | already on; leave it |
| **ChaosVD** (Visual Debugger) | `ChaosVD` | **Beta** | **true** | already on; your debugging instrument |
| **ChaosCloth** | `ChaosCloth` | *(no flags)* → **Production** | **true** | already on; scope limits in §6 |
| **PhysicsControl** | `Animation/PhysicsControl` | `IsBetaVersion: false`, `IsExperimentalVersion: false` → **Production** | false | **the only non-default plugin I recommend enabling**, and only later |
| ChaosClothAsset | `ChaosClothAsset` | v0.1, no flags | false | not needed |
| **GeometryCollectionPlugin** | `Experimental/GeometryCollectionPlugin` | **Beta** | false | conditional — §5 |
| **Fracture** (editor) | `Experimental/Fracture` | **Beta** | false | conditional — §5 |
| **FieldSystemPlugin** | `Experimental/FieldSystemPlugin` | **Beta** | false | **do not enable** — §7 |
| Mover | `Experimental/Mover` | **Experimental** | false | **rejected** — §2 |
| ChaosMover | `Experimental/ChaosMover` | **Experimental** | false | **rejected** — §2 |
| ChaosVehiclesPlugin | `Experimental/ChaosVehiclesPlugin` | **Experimental** | false | **do not enable** — §7 |
| ChaosCaching | `Experimental/ChaosCaching` | **Experimental** | false | **do not enable** — §7 |
| ChaosFlesh, ChaosRigidAsset, ChaosModularVehicle, ChaosDataflowSolver | `Experimental/…` | **Experimental** | false | no RPG need |
| **ApexDestruction** | `Runtime/ApexDestruction` | not beta, but **`UE_DEPRECATED(4.26, "APEX is deprecated…")`** on `ADestructibleActor`, `UDestructibleComponent`, `FUpdateChunksInfo` | false | **never** |

Adjacent plugins a movement/interaction design touches:

| Plugin | Tier | EnabledByDefault |
|---|---|---|
| EnhancedInput | Production (`IsBetaVersion: false`) | **true** |
| GameplayAbilities | `IsBetaVersion: false` → Production | false |
| PoseSearch | *(no flags)* v1.0 → Production | false |
| MotionWarping | **Beta** | false |
| NetworkPrediction | **Beta** | false |
| **Water** | **Experimental** | false |

---

## 2. Character movement — RULING: CharacterMovementComponent. Mover is rejected.

**The Mover plugin does exist in this install** — `Engine/Plugins/Experimental/Mover/Mover.uplugin`, with built binaries (`Binaries/Win64/UnrealEditor-Mover.dll`), a full source tree, and a companion `MoverExamples` plugin with content (`Content/Characters`, `Content/Pawns`, `Content/Maps`). That is the answer to "check whether it exists": **it is here, it is complete, and it is Experimental.**

Reject it, for four independent reasons:

1. **Its descriptor says Experimental.** `Mover.uplugin`: `"IsBetaVersion": false, "IsExperimentalVersion": true`.
2. **Its own README says so louder.** `Engine/Plugins/Experimental/Mover/README.md`: *"**The Mover plugin is Experimental. Many features are incomplete or missing. APIs and data formats are subject to change at any time.**"* In the body: *"There is an alternative version of 'instanced' layered moves in-progress that will replace the existing ones"*, *"We are in the process of replacing SimBlackboard with Rollback Blackboard"*. Two core subsystems declared mid-replacement.
3. **Its dependency array drags in four more non-Production plugins.** `Mover.uplugin` `"Plugins"`: NetworkPrediction (**Beta**), MotionWarping (**Beta**), PoseSearch (Production), **Water (Experimental)**, ChaosVD (Beta). A terrain project with no water bodies would ship an Experimental Water plugin as a transitive dependency of its character controller.
4. **The feature it exists for is one this game does not have.** README: *"support movement of actors with **rollback networking**"*. `WORLD_VISION.md` ruling 4: **Single-player: CONFIRMED.** The README's own CMC comparison lists the remaining differences as modularity conveniences — real, but not worth an Experimental API on a project whose constitution says *"State the maturity tier of any 5.8 feature you recommend."*

**ChaosMover is rejected for the same reasons plus one more.** `ChaosMover.uplugin` is also `IsExperimentalVersion: true`, and it makes the character a *simulated physics body* on a 1 m/vertex heightfield — strictly more failure modes (tunnelling, jitter on displaced Nanite geometry, mount-speed CCD) for zero single-player benefit.

### What CMC gives you, with the numbers that matter here

| Default | Value | Citation |
|---|---|---|
| Walkable floor | `SetWalkableFloorZ(0.71f)` → **44.77°** | `CharacterMovementComponent.cpp:682` |
| Max step height | **45 cm** | `:689` |
| Max walk speed | **600 cm/s** | `:694` |
| Max simulation timestep / iterations | 0.05 s / 8 | `:697-698` |

**Do not take those defaults. Take them from the recipe.** `scripts/terrain_erosion.py:247-257` already declares `MOVEMENT_PROFILES` — `walk` at the engine's own 44.77°, `climb` 70°, **`mount` 35°**, `air` 90° — and `recipes/alpine_8k.json` → `world.primary_movement_mode` is **`"mount"`** with `min_crossable_frac: 0.6`. That is the single declaration non-negotiable 19 demands: the terrain generator gates on 35° and the character must walk on 35°, or the two silently disagree and the gate was meaningless. A `recipes/character.json` block that both `terrain_erosion.MOVEMENT_PROFILES` and the pawn's `SetWalkableFloorAngle` read is the correct structure.

**A measurable hazard nobody has looked at.** `MaxStepHeight = 45 cm` on a 1 m/vertex heightfield means any adjacent-vertex rise above 45 cm is a wall. The terrain spans 0–1552.5 m. **Measurable offline, today, with no editor**: take the heightmap, compute per-vertex neighbour rise in cm, report the fraction above 45 cm inside the `mount` 35° mask. If non-trivial, the corridor the world design calls "the primary traversal route" is not walkable, and the fix is a terrain or `MaxStepHeight` decision, not a physics one.

**Also rejected: `p.AsyncCharacterMovement`.** Default 0, and the engine's own help text at `CharacterMovementComponent.cpp:264-266` reads *"1 enables asynchronous simulation of character movement on physics thread. Toggling this at runtime is not recommended. **This feature is not fully developed, and its use is discouraged.**"*

**Escape hatch, and it costs nothing.** Put every movement value in `recipes/character.json`, never in a Blueprint default. If Mover reaches Beta in 5.9/5.10 the port is then a new backend reading the same recipe. Pipeline rule 2 applied to a system that does not exist yet.

**One content mismatch, flagged not designed (animation-domain adjacent).** The skeleton on disk is the **UE4** mannequin: `Content/Mannequin/Character/Mesh/SK_Mannequin.uasset` + `UE4_Mannequin_Skeleton.uasset` + `ThirdPerson_AnimBP`. MoverExamples, the Game Animation Sample and most modern Epic locomotion content target UE5 `SKM_Manny`/`SKM_Quinn`. Whatever movement system is chosen, the skeleton decision comes first. `SK_Mannequin_PhysicsAsset.uasset` **does** exist — a usable ragdoll asset is already on disk.

**And: there is no player at all yet.** `LandscapeLab/Config/DefaultEngine.ini:3-4` sets only `GameDefaultMap=/Engine/Maps/Templates/OpenWorld`. No `GlobalDefaultGameMode`, no default pawn. `/Game/Alpine8K` has never been played. That is the actual P0.

---

## 3. Interaction with the existing world — the 219,659 instances

### 3a. They do not collide. Current state, measured at source.

`UFoliageType::UFoliageType`, at `Engine/Source/Runtime/Foliage/Private/InstancedFoliage.cpp:640`:

```
BodyInstance.SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
```

copied verbatim onto every created component at `:1822`:

```
Component->BodyInstance.CopyBodyInstancePropertiesFrom(&FoliageType->BodyInstance);
```

`scripts/place_foliage.py` sets exactly two properties on the foliage type — `mesh` (`:673`) and `cull_distance` (`:701`). `grep -n "collision\|BodyInstance\|BlockAll" scripts/place_foliage.py` returns **no matches**. So every one of the 219,659 trees is `NoCollision`, and `UInstancedStaticMeshComponent::ShouldCreatePhysicsState()` (`InstancedStaticMesh.cpp:4728`) requires `(bAlwaysCreatePhysicsState || IsCollisionEnabled())` — so **not one physics body exists for the forest**.

Not a defect report; nothing has needed it. It is the starting condition for every ruling below.

### 3b. Grass and blueberry can NEVER collide. Engine constraint.

`recipes/alpine_8k.json` puts `Meadow` and `Blueberry` on `"system": "grass"`. At `Engine/Source/Runtime/Landscape/Private/LandscapeGrass.cpp:3170-3172`:

```
static FName NoCollision("NoCollision");
GrassInstancedStaticMeshComponent->SetCollisionProfileName(NoCollision);
GrassInstancedStaticMeshComponent->bDisableCollision = true;
```

`bDisableCollision` is the first term of `ShouldCreatePhysicsState()` (`InstancedStaticMesh.cpp:4728`), so it is unconditional. **Berry-picking cannot be a physics interaction.** Any harvest mechanic on the blueberry understory must be a non-physics query against the same deterministic data the grass system uses, or a separate sparse actor layer. Design for that now.

### 3c. The trees ARE on damage-capable components, and radial damage needs no collision

The IFA instantiates `UFoliageInstancedStaticMeshComponent` (`InstancedFoliage.cpp:1515`, `:1519`). That class carries two Blueprint-assignable delegates (`FoliageInstancedStaticMeshComponent.h:26-30`):

- `OnInstanceTakePointDamage` — dispatched at `InstancedFoliage.cpp:5839`, gated on `PerInstanceSMData.IsValidIndex(PointDamageEvent->HitInfo.Item)` at `:5837`. `HitInfo.Item` is the instance index from a **real hit result**, so point damage **requires collision**.
- `OnInstanceTakeRadialDamage` — dispatched at `:5866`, resolving instances with `GetInstancesOverlappingSphere(Origin, MaxRadius, true)` at `:5848`. A bounds query on the HISM cluster tree. **No physics bodies required.**

Two tiers of tree interaction, completely different costs.

### 3d. RULING — enable `QueryOnly` collision on the four tree species only

- **Density.** 219,659 instances over 8.128 km × 8.128 km = 66.06 km² → **33.25 trees/ha**.
- **Runtime residency.** WP defaults `CellSize(12800)` cm and `LoadingRange(25600)` cm — `WorldPartitionRuntimeSpatialHash.h:231-232`. A 256 m radius on a 128 m grid loads at most a 5×5 cell block = 640 m square = 40.96 ha → **≈1,360 trees resident**; ~685 inside the true 256 m circle. Not 219,659. *(Engine defaults — this level's actual values are unread; see §8.)*
- **Local interaction radius.** Within 50 m: 0.785 ha → **26 trees**. Within 30 m: **9**.

Per-instance bodies are created for the whole component at once, with no distance culling — `CreateAllInstanceBodies()` builds `WorldTransforms` for `PerInstanceSMData.Num()` and calls `InstancePhysicsBodies->CreateAll(...)` (`InstancedStaticMesh.cpp:2868-2896`). At ~1,360 resident that is fine. At the 219,659 the *editor* holds with `--load-all-regions`, it is not.

**The ruling:**

1. Set `body_instance.collision_enabled = QUERY_ONLY` and `collision_profile_name = BlockAll` on `Conifer`, `ConiferPine`, `SpruceSub`, `SpruceSapling` **from the recipe**. Writable from Python — stub `unreal.py:394362` and `:394491`, ``body_instance`` (BodyInstance) [Read-Write] "Custom collision for foliage"`; `BodyInstance` exposes `collision_enabled` and `collision_profile_name` (stub `:167214` onward).
2. **QueryOnly, not QueryAndPhysics.** Foliage is `Mobility = EComponentMobility::Static` (`InstancedFoliage.cpp:616`). Nothing should push a tree. Physics-enabled bodies enter narrow-phase for no gameplay benefit.
3. **Never on the grass-system species** — impossible anyway (§3b); asking would be a silent no-op, which is worse.
4. **Editor guard.** Any tool doing `--load-all-regions` on a world with tree collision on will instantiate 219,659 static bodies. `measure_frame_cost.py` already refuses undeclared residency (exit 6); the same gate should refuse an all-regions load once collision is on, or the editor becomes a failure the runtime never sees.

### 3e. Four traps in that one change

**Trap 1 — [INFERENCE] `collision_profile_name` written from Python probably does not apply the profile.** **Established:** `FBodyInstance::SetCollisionProfileName` calls `LoadProfileData(false)` (`BodyInstance.cpp`, `SetCollisionProfileName` body) — that is what populates `CollisionEnabled` and the response container; and `UFoliageType::PostLoad` runs `BodyInstance.FixupData(this)` (`InstancedFoliage.cpp:810`) → `LoadProfileData(...)`. **Inferred, not tested:** that a reflected `set_editor_property` on the struct member is a plain UPROPERTY write bypassing that method. It follows from how UHT treats a UPROPERTY with no BlueprintSetter, but it was not executed. If right, a read-back shows the correct name over collision that is still off until the next asset load — the "a value can arrive and still mean something else" class. **Build the disproof into the same operation** (non-negotiable 13): set `collision_enabled` explicitly too, then verify with a **different instrument** — a world line trace against a placed instance, the shape of the existing `check_collision_truth.py` / `trace_grounding.py`. That trace settles the inference either way and costs one run.

**Trap 2 — `FoliageType.CollisionWithWorld` is not runtime collision.** `FoliageType.h:265-267`, `Category=Placement`: *"If checked, an overlap test with existing world geometry is performed before each instance is placed."* A painting-time rejection test. Constructor default `false` (`InstancedFoliage.cpp:613`). Belongs on the casualty list beside `CullDistance` 0 and `MATUSAGE_Landscape`.

**Trap 3 — never call `LineTraceComponent` on a foliage ISM.** `FInstancedMeshComponentBodies::LineTrace` (`Private/InstancedMeshComponentBodies.cpp`) is a bare `for (FBodyInstance* Body : Bodies)` over every body. World traces use the Chaos acceleration structure and are fine; a component-scoped trace on a 10,000-instance foliage component is O(N) per call.

**Trap 4 — Nanite does not give a mesh collision.** `SM_PVE_Norway_Spruce_01_A` is `nanite_enabled: true, lod_count: 1, lod_triangles: [2335]` (`Free/_measured/pve_spruce.json`). Collision comes from the mesh's `BodySetup`, which Nanite has nothing to do with. `CreateAllInstanceBodies()` returns early with `"Instance Static Mesh Component unable to create InstanceBodies!"` if `GetBodySetup()` is null (`InstancedStaticMesh.cpp:2876-2881`). **Whether these meshes have any simple collision primitive is UNKNOWN, and the instrument that would answer it does not exist** — `measure_tree_packs.py` records `nanite_enabled`, `lod_count`, `material_slots`, `lod_triangles`, `pivot_offset_xy_m`, `base_offset_z_m` and **no collision field**; `collision_prims` in `recipes/alpine.json` comes from the asset-registry `CollisionPrims` **tag** (`make_alpine_palette.py:136-138`), the same scan whose `Materials` tag CURRENT STATE records as contradicted on 23 of 38 meshes. **Extend `measure_tree_packs.py` to read the loaded mesh's `body_setup` aggregate geometry before enabling anything.** If the meshes have no simple collision, the fix is a single capsule authored per trunk — not `UseComplexAsSimple`, which puts a 2,335-triangle trimesh in the query scene per instance.

### 3f. Surface type — free on paper, not free here *(scope extension; discardable)*

`ULandscapeLayerInfoObject::PhysMaterial` exists (`LandscapeLayerInfoObject.h:69`) and `ULandscapeHeightfieldCollisionComponent` cooks `DominantLayerData` plus `PhysicalMaterialRenderObjects` (`LandscapeHeightfieldCollisionComponent.h:136,143`), so a landscape trace *can* return a per-texel physical material.

**[INFERENCE] This project probably cannot use it as built.** **Established:** `recipes/alpine_8k.json` → `material.weightmap` is `textures/alpine_8k_weights.png`, a baked RGB **texture**, with the three surfaces selected inside `M_Alpine8K`; and `grep -rn "LandscapeLayerInfoObject\|PhysMaterial" scripts/*.py` returns one comment and **zero code**, so no script ever created a layer info. **Not established:** whether one was created by hand in the editor — the level was never opened. If none exists, `DominantLayerData` is empty, `GeomData.MaterialIndices.Num() == 1` (`Chaos/HeightField.h:322`), and every landscape hit returns the same default physical material. One live read of the landscape's `LandscapeLayerInfoObjects` settles it.

Two conditional consequences:

- Collision memory would be 2 B/sample, not 3. `Chaos::FHeightField` stores `TArray<uint16> Heights` plus `TArray<uint8> MaterialIndices` (`HeightField.h:42, :443`). 8129² = 66,080,641 samples × 2 B ≈ **132 MB** with all 256 proxies resident, plus ~13 MB for the `LowResInc = 6` min/max grid (`HeightField.h:422`). Per 508 m proxy ~0.5 MB; at a 256 m loading range, single-digit MB. Per-layer physical materials would add ~66 MB fully resident.
- Footsteps, decals, VFX and "what am I standing on" must read the **same weightmap PNG the material reads**, on the CPU, or the two disagree — non-negotiable 19 exactly. Recommended: a Blueprint-callable subsystem sampling a baked lookup derived from `textures/alpine_8k_weights.png`, produced by the existing pipeline and hashed into place per non-negotiable 20. **Do not** paint landscape layers to get this; it forks the surface definition.

**A related mechanism that does NOT work, checked because it sounds right:** "make scree unwalkable" cannot be done per-surface. `UCharacterMovementComponent::IsWalkable` reads `HitComponent->GetWalkableSlopeOverride()` — a **per-component** override (`CharacterMovementComponent.cpp`, `IsWalkable` body; `PrimitiveComponent.h:1642`). One landscape component is 254 m × 254 m. Per-surface walkability must be gameplay logic on top of the weightmap query, not a physics property.

---

## 4. Ragdoll and physical animation — RULING: PhysicsAsset + RBAN, PhysicsControl later, never for crowds

Everything in the first tier is Production and already present. No plugin needed.

| Capability | Where | Tier |
|---|---|---|
| `UPhysicsAsset`, `FConstraintInstance` | `Engine/Classes/PhysicsEngine/PhysicsAsset.h`, `ConstraintInstance.h` | Engine core, Production |
| `UPhysicalAnimationComponent` | `Engine/Classes/PhysicsEngine/PhysicalAnimationComponent.h` | Engine core, Production |
| Rigid Body anim node (RBAN) | `Runtime/AnimGraphRuntime/Public/BoneControllers/AnimNode_RigidBody.h` | Engine core, Production |
| `PhysicsControl` + "Rigid Body With Control" node | `Engine/Plugins/Animation/PhysicsControl` — `IsBetaVersion: false, IsExperimentalVersion: false` | **Production**, `EnabledByDefault: false` |
| Existing ragdoll asset on disk | `Content/Mannequin/Character/Mesh/SK_Mannequin_PhysicsAsset.uasset` | — |

**Build, in this order:**

1. **Death ragdoll.** `SetSimulatePhysics(true)`, a short blend, then **freeze**. A corpse that keeps simulating is 15+ bodies and their constraints permanently in the solver. Pose snapshot, then `SetSimulatePhysics(false)` on sleep. This alone is 90% of what "ragdoll" means to a player.
2. **RBAN for secondary motion** — a small chain (cloak clasp, quiver, satchel) on the player only. `SimulationSpace = ComponentSpace` (`AnimNode_RigidBody.h:275`, enum at `:24`) and `bEnableWorldGeometry = false` (`:290`) unless there is a reason: world-geometry collision in RBAN queries the scene per tick per character.
3. **PhysicsControl / "Rigid Body With Control"** only if hit reactions must blend physics against animation while the character stays player-controlled. Production, which is rare in this space, and the right answer for that problem. Not before the game has combat.

**Two configuration hazards:**

- `p.RigidBodyNode` is `ECVF_Scalability` (`AnimNode_RigidBody.cpp:63`) — *"Enables/disables the whole rigid body node system. When disabled, avoids all allocations and runtime costs. Can be used to disable RB Nodes on low-end platforms."* **A scalability group can silently turn off every ragdoll and every physical animation in the game.** I looked: `Engine/Config/BaseScalability.ini` contains no `RigidBodyNode` entry and no `AnimationQuality` group, and `LandscapeLab/Config/*.ini` contains no physics keys at all. Nothing sets it today — but this project has been bitten three times by `sg.*` groups setting values without running the group, and this cvar is the same shape. Pin it explicitly and read it back from the live editor, per non-negotiable 17.
- `RBAN_MaxSubSteps` via `p.RigidBodyNode.MaxSubSteps` (`AnimNode_RigidBody.cpp:71`) multiplies per-character solver cost. Leave it.

---

## 5. Destruction — RULING: one authored fracture class, ISMPool-rendered, remove-on-sleep. Terrain and trees are not destructible.

**What Chaos Destruction is in 5.8:** `GeometryCollectionEngine` is a core Runtime module (`Runtime/Experimental/GeometryCollectionEngine`), but the plugins that make it usable are Beta and off by default — `GeometryCollectionPlugin` (`IsBetaVersion: true`, `EnabledByDefault: false`) and `Fracture` (`IsBetaVersion: true`, `EnabledByDefault: false`, editor-only `FractureEngine` module).

**The real cost, and why it is affordable if scoped.** A Geometry Collection at rest is not free by default — it is a bespoke renderer per actor. The lever that makes destruction shippable is the **ISM pool custom renderer**: `UGeometryCollectionComponent::CustomRendererType` (`GeometryCollectionComponent.h:1560`), defaulting to `UGeometryCollectionISMPoolRenderer::StaticClass()` (`GeometryCollectionComponent.cpp:7428`), with `AGeometryCollectionISMPoolActor` / `UGeometryCollectionISMPoolSubSystem` batching unbroken pieces into shared instanced components. Un-fractured props then cost roughly what a static mesh costs.

| Knob | Where | Use |
|---|---|---|
| `MaxSimulatedLevel` | `GeometryCollectionComponent.h:1020` | **cap at 1**. Two levels of an 8-piece fracture is 64 bodies from one prop |
| `EnableClustering` | `:1002` | leave on; it keeps unbroken pieces as a single body |
| `DamageThreshold` (array, per level) | `:1029-1030` | recipe-driven, per prop class |
| `DamagePropagationData` | `:1050-1051` | off unless a chain reaction is wanted |
| `bRemoveOnMaxSleep`, `MaximumSleepTime`, `RemovalDuration` | `GeometryCollectionObject.h:794, 802, 806` | **mandatory.** Debris that never despawns is a permanent body-count leak |
| `p.GeometryCollectionNavigationSizeThreshold` | `GeometryCollectionComponent.cpp:490` | keeps small debris out of navmesh export |

**The ruling:** enable `GeometryCollectionPlugin` + `Fracture` **only when a specific prop must break**, author exactly one class first (a KiteDemo boulder — the palette is measured in `Free/_measured/rock_pivots.json`), and gate it on: `MaxSimulatedLevel = 1`; `bRemoveOnMaxSleep = true` with declared `MaximumSleepTime`/`RemovalDuration`; `CustomRendererType = UGeometryCollectionISMPoolRenderer`; a before/after `stat Chaos` + `stat unit` reading in PIE, single-variable, in R-FRAMECOST's shape; and an abort bar declared **before** the measurement (suggest +1.0 ms game thread at a ground station with the prop shattered).

**Do NOT make destructible:**

- **The terrain.** It is a `Chaos::FHeightField` — a regular grid of uint16 heights. There is no fracture representation for it, at any cost. Deformable terrain means replacing the landscape with meshes, invalidating 219,659 placements, the collision truth guard, and R-ALPINE8K.
- **The trees.** 219,659 Geometry Collections is a category error, not a budget question. Chopped trees are a *swap*: remove the instance (the delegates in §3c give you the index), spawn one short-lived rigid-body trunk actor, despawn on sleep. One body, not thousands.
- **Anything with `FieldSystemPlugin`.** §7.

---

## 6. What to build, in order, with the gate for each

*The gates are requirements; the ordering is a proposal.*

| # | Unit | Gate | Why here |
|---|---|---|---|
| **P0** | A player exists. `recipes/character.json` → GameMode + `ACharacter` + CMC, spawned at a recipe-declared, surface-traced start. Walkable angle from `MOVEMENT_PROFILES`, not the CMC default | Walk 1 km along the inter-massif corridor without falling through, without a step-height stall; measured, trace log kept | There is no `GlobalDefaultGameMode` in `DefaultEngine.ini`. Everything else is untestable until someone can stand on the terrain |
| **P0.5** | Offline step-height audit: fraction of `mount`-mask terrain whose 1 m neighbour rise exceeds `MaxStepHeight` | A number, recorded | Needs no editor, costs minutes, could change the terrain decision |
| **P1** | Measure the tree meshes' `body_setup` live; extend `measure_tree_packs.py` | `collision_prims` replaced by a **loaded-mesh** reading, per the `material_slots` precedent | The registry tag is untrustworthy; gates P2 |
| **P2** | Tree collision: QueryOnly on the four instance species, recipe-driven | `LIST ISM PHYSICS` in PIE reports non-zero bodies **and** a world line trace hits a trunk; and an all-regions editor load is refused | The biggest gameplay gap. Cheap at ~1,360 resident |
| **P3** | Surface-type query from the weightmap, CPU-side, one declaration shared with the material *(scope extension)* | Positive control: the query agrees with the material's own layer choice at N sampled points | Footsteps, VFX, "what am I on" |
| **P4** | Death ragdoll + freeze on `SK_Mannequin_PhysicsAsset` | `stat ChaosCounters` body count returns to baseline after N seconds | Highest visible value per millisecond spent |
| **P5** | Tree-chop: radial damage → instance removal → one trunk rigid body → despawn | The dynamic-body ceiling (§0, UNMEASURED) never exceeded under repeated chopping | Uses shipped delegates; needs no new plugin |
| **P6** | One fracture-capable prop class | §5's four conditions | Only if the game design actually asks for it |

**Cloth (already Production and enabled):** restrict `ChaosCloth` to the player and named NPCs. Per-character CPU on the game thread. A crowd in simulated cloth is the classic way this budget dies.

---

## 7. What NOT to build — named, with the reason

1. **Mover / ChaosMover / NetworkPrediction.** Experimental, Experimental, Beta. Rollback networking on a CONFIRMED single-player game. §2.
2. **`p.AsyncCharacterMovement 1`.** The engine's own help text discourages it (`CharacterMovementComponent.cpp:264-266`).
3. **Physics substepping.** Default false. Multiplies solver cost by up to `MaxSubsteps = 6`; exists for fast light vehicles and long constraint chains. A walking RPG at 60 fps does not need it. If something jitters, fix the body, not the tick rate.
4. **Async physics tick.** Decouples physics from the render frame — a networked-determinism feature — and changes what every `stat` reading means. Not now.
5. **Chaos Vehicles** (Experimental). Mounts are *not* vehicles: a mount is a Character with a different mesh and ~3× `MaxWalkSpeed` (`WORLD_VISION` ruling 2b). The airship is a scripted travel sequence between regions (`WORLD_VISION` Option A: *"Airship travel IS the region connector … a region transition behind a sky sequence"*). Neither needs a wheeled-vehicle solver.
6. **`FieldSystemPlugin`** (Beta). Force fields over a Geometry Collection are a VFX-authoring tool for set-piece destruction. An RPG's "explosion knocks things over" is one radial impulse call.
7. **`ChaosCaching`** (Experimental). Pre-baked simulation playback is a cinematics feature, and it is a *derived record* of a simulation — non-negotiable 20 territory — with no gameplay payoff.
8. **`ChaosFlesh`, `ChaosRigidAsset`, `ChaosModularVehicle`, `ChaosRigidPhysicsAsync`, `ChaosDataflowSolver`** — all Experimental, no RPG use case.
9. **`ApexDestruction`.** `UE_DEPRECATED(4.26, "APEX is deprecated. Destruction in future will be supported using Chaos Destruction.")` on every public class. It has binaries in this install; that is not permission.
10. **Destructible terrain.** §5.
11. **Per-tree Geometry Collections.** §5.
12. **`UseComplexAsSimple` on any foliage or scatter mesh.** A 2,335-triangle trimesh per instance in the query scene, ~1,360 times.
13. **Physical materials with per-surface walkability.** The mechanism is per-component, not per-texel (`IsWalkable` → `HitComponent->GetWalkableSlopeOverride()`). §3f.
14. **Collision on the grass system.** Engine-impossible (`LandscapeGrass.cpp:3171-3172`). Asking for it is a silent no-op.
15. **Raising `SimpleCollisionMipLevel`** to cheapen landscape queries. The lever exists (`LandscapeComponent.h:625`, used at `LandscapeEdit.cpp:1496,1651`) and it degrades exactly the collision surface whose agreement with the render surface this project spent three days proving. `CollisionMipLevel = 0` (`Landscape.cpp:321`) stays.

---

## 8. Open items — the reading that does not yet exist, and what produces it

Each row names the missing instrument, not just the gap. This work was done offline and read-only by instruction, so every row below is a measurement that was out of reach, never a measurement that was attempted and failed.

| Open item | State | What produces the reading |
|---|---|---|
| Simple collision geometry on the tree meshes | **UNKNOWN — instrument absent.** `measure_tree_packs.py` has no collision field; `collision_prims` derives from the registry tag scan already DO-NOT-CONSUME for `material_slots` | one loaded-mesh read of `body_setup`'s aggregate geometry per mesh |
| Whether a Python write to `collision_profile_name` applies the profile | **[INFERENCE]**, §3e Trap 1 | one world line trace against a placed instance, after the write |
| Whether `/Game/Alpine8K` has any `ULandscapeLayerInfoObject` | **[INFERENCE]**, §3f — no script creates one; the level was not opened | one live read of the landscape's `LandscapeLayerInfoObjects` |
| Chaos solver cost at any body count on this machine | **UNMEASURED** — all four §0 budget rows are proposals | PIE + `stat unit` / `stat Chaos` / `stat ChaosCounters` / `LIST ISM PHYSICS`, single-variable against the `forest_floor` series |
| `/Game/Alpine8K`'s real WP cell size and loading range | engine defaults read (128 m / 256 m, `WorldPartitionRuntimeSpatialHash.h:231-232`); the level's own values unread | one read of the level's `WorldPartitionRuntimeSpatialHash` grids. Every §3d residency figure scales linearly with it |
| Whether the 730 m foliage cull is reachable at runtime | never observed — every measurement was taken with all 256 proxies resident | a PIE residency count at a ground station. **Streaming-domain question**, listed only because it moves this domain's denominator by two orders of magnitude |
| Memory of one `FBodyInstance` + its Chaos particle | not counted, and not guessed | `stat ChaosCounters` plus `LIST ISM PHYSICS`'s `Num Shapes` column |
| Whether `SK_Mannequin_PhysicsAsset` is well-formed | exists on disk, not opened; UE4-era asset against a UE4 skeleton | open it in the Physics Asset editor, or read its body/constraint counts |

---

## 9. Instruments this domain should add *(scope extension beyond "what measurement would settle it"; discardable)*

| Instrument | What it reads | Why it is a *different* representation |
|---|---|---|
| `measure_foliage_collision.py` | `LIST ISM PHYSICS` output in PIE | body/shape counts from the **physics scene**, not from the foliage type's property |
| extend `measure_tree_packs.py` | loaded mesh `body_setup` aggregate geom | replaces a registry **tag** with a loaded-asset reading — the exact fix already applied to `material_slots` |
| `check_step_height.py` | heightmap PNG, offline | neighbour rise vs `MaxStepHeight`; needs no editor, survives a cold replay |
| `verify_walkable_profile.py` | live CMC CDO vs `recipes/character.json` vs `terrain_erosion.MOVEMENT_PROFILES` | proves the three have not drifted — non-negotiable 24, three places that must agree |
| ChaosVD capture | the solver's own recorded state | Beta, `EnabledByDefault: true`, already available; the only instrument that sees inside a step |

Every one should fail closed and be positive-controlled before it is trusted: a foliage-collision checker that has only ever seen a world **with** collision has not been tested.