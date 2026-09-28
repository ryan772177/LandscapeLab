# RESEARCH REGISTER — what is proven, proposed, rejected

Maintained by the research desk. Claude Code appends measured results under each item; the desk moves items between sections. Cite paths.

## PROVEN (measured on this project)

**CC 2026-09-09 — THE HLOD LAYER IS BUILT, AND THE WORLD IS UNIFORM. Task 7's
precondition is discharged.** 12 manifest shards, one fresh commandlet process
each, ~13.5 h. Read back from every cell's OWN saved build report
(`scripts/hlod_report_census.py`), not from package size and not from triangle
count:

    2,267 packages    1,225 Instancing(0) + 1,042 MeshApproximate(3)
    MeshMerge(1)      ZERO          packages over 5 MB   ZERO
    bytes             9.71 GiB -> 1.47 GiB  (8.24 GiB reclaimed)
    per shard         61.2-75.2 min, mean 67.5, ~78 Merged cells each

Q4 ruled Task 7 ahead of imposters because "beyond the streaming range there is
not a cheap proxy, there is nothing at all", and an imposter result measured in
that condition would be measured against a void. **That condition is over.**
Procedure locked in `RECIPES.md` R-HLOD amended 2026-09-09b.

**CC 2026-09-09 — TWO PROXIES FOR "IS THIS CELL STALE" BOTH MISCLASSIFY, and
both were in use.** Package size said 705 stale; triangle count said 468; the
cells' own build reports said 927. `..._Merged/..._Instanced_L1_X-4_Y-2` holds
**8,449 triangles in a 19,071,154-byte package** and is MeshMerge output — a
higher-level merged cell sits under any triangle threshold worth picking, and a
package also carries its baked textures. Both proxies are downstream of the
same event, the geometry a build emitted, so their agreeing would not have made
either right (non-negotiable 0). Use the build report, which records what the
build was CONFIGURED with.

**CC 2026-09-09 — STATION FEATURELESS FRACTION, first measurement with HLOD
present.** 4K, target profile, player instrument:

    station      pre-HLOD 09-06   post 09-07   predicted sky   over prediction
    near_ground  0.1513           0.1745       0.0075          0.1670
    mid_slope    0.9383           0.7464       0.5639          0.1825
    vista        0.5716           0.5782       0.4646          0.1136

**`mid_slope` loses 19.2 points of featureless area** — proxies now occupying
distance that was void. That is the first frame-level evidence the HLOD work
did what it was for. **TREAT AS AN INDICATION, NOT AN ACCEPTED RESULT:** both
runs FAIL the residency gate, and they differ in profile and resolution
(dev/1440p vs target/4K), which is enough to explain near_ground's +2.3 and
vista's +0.7 on its own.

**CC 2026-09-09 — THE RT-ON OPEN SURVIVES. This is an OBSERVATION, a
NON-REPRODUCTION, and NOT A CAUSE.** The editor opened `/Game/Alpine8K` with
hardware ray tracing on and ran 177+ minutes with zero crash lines, against two
prior `DXGI_ERROR_DEVICE_HUNG` failures at 12,434 of 15,235 MB with a page
fault on an HLOD `_Merged_0` buffer and `RayTracingGeometry` in the breadcrumb.

RT confirmed from the engine, not the ini: `Ray tracing is enabled (dynamic)`,
`r.Lumen.HardwareRayTracing:1`, `Bindless (Configuration=RayTracing)`; and
re-read live through `ue_exec`: `r.RayTracing 1.0`,
`r.DynamicGlobalIlluminationMethod 1.0`, `r.ReflectionMethod 1.0`.

The renderer configuration is unchanged since those crashes; only the geometry
differs. **That the hang does not reproduce is not evidence that the old
geometry caused it.** Separately, the commandlet fault (signature 2,
`DRIVER_INTERNAL_ERROR` / `CreateReservedResource`) is a DIFFERENT fault, it
reproduced deterministically on one shard at **9,359 MB and then 7,403 MB** of
the same UE field, and **memory pressure is therefore ELIMINATED** as its
trigger. Still no cause.

**CC 2026-09-09 — RULE: `MeshMerge` CANNOT PRODUCE A BLOB-BAND PROXY, and the
proxy budget comes from the blob band.** `MeshMerge` has no decimator — it
welds and bakes, so a merged cell keeps its sources' triangle count (~329,000
per L0 cell here). The blob band (1.5-6 px, BRIEF §2) needs coverage and mean
colour only, which is a few thousand triangles. The layer must therefore be
`MeshApproximate`, whose voxel remesh does have a triangle target, and the
budget is DERIVED from the band rather than chosen: 4,000 triangles per 254 m
L0 cell. R-HLOD 08f and 08g.

**CC 2026-09-09 — LESSON: `ApproximationAccuracy` IS IN METRES, and 150 is
accepted silently.** It is the voxel size for the remesh, default 1.0 m. Read
as centimetres it becomes 150, which is ~2 voxels across a 254 m cell — a
proxy with no shape at all, and no error is raised. Derive it from the quad
size the triangle budget implies (1.5 m here) and have the tool refuse anything
above 10. **The unit was not in the field name and the engine does not
validate it**; the same class as the cull distances being metres in a recipe
whose neighbours are centimetres.

**CC 2026-09-08 — THERE IS A WORLD-LEVEL DEFAULT HLOD LAYER IN 5.8, AND IT DOES
NOT DIRTY A SINGLE ACTOR PACKAGE.** Established from engine source, chain
complete, every link opened:

    UWorldPartition::DefaultHLODLayer
        WorldPartition.h:610-612   UPROPERTY(EditAnywhere,
                                   DisplayName "Default HLOD Layer",
                                   EditCondition "bEnableStreaming")
        WorldPartition.h:343-344   GetDefaultHLODLayer / SetDefaultHLODLayer
      -> WorldPartitionStreamingGeneration.cpp:1384
             MainContainerCollectionInstance.HLODLayer =
                 FSoftObjectPath(WorldPartitionContext->GetDefaultHLODLayer())
      -> :1425  ResolveHLODLayer(ActorDescView,
                                 ContainerCollectionInstanceDescriptor.HLODLayer)
      -> :868-875  ResolveHLODLayer
             if (!ActorDescView.GetHLODLayer().IsValid()
                 && ActorDescView.GetIsSpatiallyLoaded()
                 && ActorDescView.GetActorIsHLODRelevant())
                     ActorDescView.SetRuntimeHLODLayer(ParentHLODLayer);

**`SetRuntimeHLODLayer` (:549-553) writes `RuntimeHLODLayer` on the streaming
generation VIEW, not on the actor** — `FStreamingGenerationActorDescView::GetHLODLayer()`
(:254-265) returns the runtime value in preference to `Super::GetHLODLayer()`,
which is the persisted `FWorldPartitionActorDesc::HLODLayer` baked into the
external actor package at `WorldPartitionActorDesc.cpp:153`. So the default is
applied at GENERATION time and **nothing is written to `__ExternalActors__`**.
This is the route around the 2026-09-07 save spin: one property on one object,
one save, zero of the 2,796.

The three classes this world needs all qualify as HLOD relevant:

    ULandscapeComponent::IsHLODRelevant    Landscape.cpp:2178-2190 -> bEnableAutoLODGeneration
    UStaticMeshComponent::IsHLODRelevant   StaticMeshComponent.cpp:3037
    UInstancedStaticMeshComponent::         InstancedStaticMesh.cpp:2515-2523
        IsHLODRelevant                      (false only when instance count == 0)

**and `ULandscapeNaniteComponent::IsHLODRelevant` returns a hard `false`**
(`LandscapeNaniteComponent.cpp:222-226`, comment: "This component doesn't need
to be included in HLOD, as we're already including the non-nanite LS
components"). That is evidence AGAINST this session's stated hypothesis that
dirtying Nanite landscape proxies triggers a Nanite rebuild *via the HLOD path*
— the Nanite component is excluded from HLOD relevance by construction. It does
not rule out a rebuild triggered by the package dirty itself; it rules out the
HLOD system asking for one.

`AActor::IsHLODRelevant` (`Actor.cpp:6830-6883`) additionally requires
non-transient, not hidden, not editor-only, `bEnableAutoLODGeneration`, and — in
a partitioned world — `GetIsSpatiallyLoaded()`.

An engine-wide default exists too, but it is config-driven and says nothing
about this world's current value: `UHLODLayer::GetEngineDefaultHLODLayersSetup()`
(`HLODLayer.cpp:58-78`) reads `[/Script/Engine.Engine] DefaultWorldPartitionHLODLayer`
from `Engine.ini`, and `WorldPartition.cpp:1273` seeds `DefaultHLODLayer` from it
**only at world-partition creation**. What Alpine8K holds today is a read-back,
not an inference.

**NOT the same thing as `AWorldSettings`.** Every HLOD field in
`WorldSettings.h` (:486, :706-724) is gated `EditCondition="WorldPartition == nullptr"`
— that is the legacy non-WP HLOD system, and it is inert in this world.

**CC 2026-09-08d — HLOD IS BUILT AND MEASURED, for one cell. The blocker was
XGE.** Commandlets exempt themselves from `AvoidUsingLocalMachine`
(`XGEControllerModule.cpp:97-111`), so shader jobs went to a local IncrediBuild
that never returned them. `-noxgecontroller` is now MANDATORY on every HLOD
commandlet here; without it 0 workers / 0.044 cores / never finishes, with it
14 workers / 0.44 cores / **`Built 6 HLOD actors`, 1:20 min**.

Read back from the built cell `..._Merged/..._Instanced_L0_X-10_Y11`:

    bounds     26544 x 27092 x 9052 cm, NON-ZERO (Setup-only descs read zero)
    triangles  329,364    vertices 951,468    LODs 1    nanite FALSE
    material   MI_Alpine8K_HLODLayer_Instanced_L0_X-10_Y11 (MIC, in-package)
    package    130 B -> 13,959,833 B

The bounds contain the point the cell was selected for, confirming the
label-grid derivation independently.

**The 25 subtractive assignments are cleared** — 25 cleared, 25 saved in
3.94 s, read-back clean — and `-SetupHLODs` rerun gives **2,267 HLOD actors and
ZERO invalid-layer errors** (was 2,775, then 25, now 0). Single variable.

**STILL NOT ESTABLISHED: anything about `featureless_fraction`.** One built cell
of 2,267 cannot move a frame metric, and the full build is NOT yet authorised —
roughly 4-5 h and **15-20 GB of new tracked binary content** into a 41 GB repo
whose history bloat is unresolved, with HLOD packages hash-mixed into
`__ExternalActors__` alongside real actors so no `.gitignore` pattern separates
them. Git strategy first, build second. Detail: R-HLOD 08d.

**CC 2026-09-08b — HLOD ACTORS NOW EXIST: 2,230 of them. And the cause recorded
below is WRONG — twice over.** The entry that follows says HLOD was "never
assigned", and that "`SetupHLODActors` creates HLOD actors only for actors that
have a layer, so with all of them at `None` there was nothing to create". Both
halves fail:

1. **`hlod_layer: None` is the NORMAL state.** `UWorldPartition::DefaultHLODLayer`
   supplies a layer to every unassigned, spatially-loaded, HLOD-relevant actor
   at streaming-generation time (`WorldPartitionStreamingGeneration.cpp:868-875`).
   This world's default was already set to `Alpine8K_HLODLayer_Instanced`
   before anything was touched on 2026-09-07.
2. **Assignment was never the gate. REGISTRATION is.** Under
   `UWorldPartitionRuntimeHashSet` — which is what `/Game/Alpine8K` uses, read
   back from `...WorldPartition_0.WorldPartitionRuntimeHashSet_0` — a layer is
   valid only if a runtime partition lists it in
   `RuntimePartitions[].HLODSetups[].HLODLayers`
   (`WorldPartitionRuntimeHashSet.cpp:377-380`, resolver at :388-435). The two
   layer assets created on 2026-09-07 are registered by nothing and are inert;
   the 2,796 assignments were inert by construction.

Single-variable measurement, nothing else changed between the runs:

    default = Alpine8K_HLODLayer_Landscape   0 actors, 2,775 invalid-layer errors
    default = Alpine8K_HLODLayer_Instanced   2,230 actors, 25 errors

External actor packages 3,269 -> 5,499. The 25 residual errors are exactly the
2026-09-07 bounded assignment (21 IFA + 4 proxies), which is now *subtractive*:
an explicit invalid layer overrides the valid default, so those 25 are the only
actors excluded from HLOD.

**What this does NOT yet establish.** Setup creates actors with NO geometry —
all 2,230 report zero-extent bounds at the origin. `featureless_fraction` at
`mid_slope` is UNMOVED and the HLOD-absent precondition below stands until a
built cell is measured in a frame. Detail and the six-step order: R-HLOD,
amended 2026-09-08b; LESSONS 2026-09-08 and 2026-09-08b.

**LEAD, not a measurement, for the three-levers entry further down:** that entry
derived `-grid=MainGrid` from `WorldPartitionRuntimeSpatialHash.cpp` on the
evidence of zero `SpatialHashRuntimeGridInfo` actors. That absence is also what
"there is no spatial hash" looks like, and this world's grids are named
`MainPartition:HLODLayer_Instanced` / `MainPartition:HLODLayer_Merged`. Lever 2
may have been aimed at a namespace this world does not have. Not re-tested.

**CC 2026-09-06/07 — HLOD IS ABSENT, AND THAT IS THE PRECONDITION FOR THE SHAPE
AND BLOB BANDS.** Not "not built" — **never assigned**. `hlod_probe.py` on the
live `/Game/Alpine8K`: zero `WorldPartitionHLOD` actors, and every actor class
reporting `hlod_layer: None` — Landscape, 256 `LandscapeStreamingProxy`, 1093
`InstancedFoliageActor`, 1446 `StaticMeshActor`. Two layer ASSETS
(`Alpine8K_HLODLayer_Instanced`, `..._Merged`) existed and **nothing referenced
either**. `SetupHLODActors` creates HLOD actors only for actors that have a
layer, so with all of them at `None` there was nothing to create; "never built"
was the consequence, "never assigned" the cause.
Beyond the ~1 km World Partition streaming range, WP shows a proxy if one was
built and **nothing** if not — which is precisely what `mid_slope.png` (93.8%
featureless) and `vista.png` are. **Nothing in the shape band (6–40 px) or the
blob band (1.5–6 px) can be measured until HLOD exists**, which is why Q4 puts
Task 7 ahead of imposters. Layers now assigned (2,796 actors); build pending.

**CC 2026-09-06 — near_ground's "confirmed by render" is WITHDRAWN.** It was
recorded on 2026-09-05 after visual inspection. The in-PIE residency probe then
measured that frame's world at **12 of 1024 landscape components (1.2%)**. The
frame looks correct because the town is close and the camera low, so the few
resident cells fill it — but nothing about it established that the world was
there. A frame is evidence about the frame. **No station is confirmed.**

**CC 2026-09-06 — the dolly baseline is PENDING EXPOSURE and its score must not
be quoted.** 180 frames scored **0.66877**, but mean luma drifts 0.3486 → 0.2749
across the 8.4 m walk and 15.2% of pixels change by >0.10 between frames **4.7 cm
apart**. That is auto-exposure adapting; `temporal_stability` Weber-normalises to
LOCAL luminance, so a global exposure ramp survives normalisation and dominates
the residual, burying any pop. `benchmark.json` declared `"exposure manual"` in
prose and nothing applied or read it back. The recipe's own
`lighting.exposure` (`method: manual`, `compensation_ev: -1.923`) and
`apply_lighting.py:333-345` (`AEM_MANUAL` + bias on a PostProcessVolume) already
exist; the missing piece was always the READ-BACK. **No baseline until that
read-back passes and the drift is shown gone.**

**CC 2026-09-05, Task 1 — B1.1 CONFIRMED AND STRENGTHENED; the heights it rested on were not.**
Re-run on MEASURED heights (`_verify/bench/2026-09-05/species_heights.json`, one cited
`Free/_measured/` row per species) and MEASURED placed scales (the four
`foliage/alpine_8k_*.json` lists, 219,659 instances). Result:
`_verify/bench/2026-09-05/angular_budget_2026-09-05_SUMMARY.json`, four runs
(4K + 1440p × typical p50 / worst-case max placed height).

At 4K, typical placed scale, px tall at the moment the recipe deletes the object:

    Conifer        730 m  62.9 px   DETAIL band
    SpruceSapling  180 m  53.0 px   DETAIL band
    ConiferPine    730 m  48.0 px   DETAIL band
    SpruceSub      730 m  40.7 px   DETAIL band
    Boulder        140 m  21.8 px   shape band  (alpine.json, PRE-8K only)
    Blueberry       45 m  20.3 px   shape band
    Meadow          50 m  14.9 px   shape band

- The range is **14.9–62.9 px at 4K / 9.9–42.0 px at 1440p**, not 10–28 px.
- **All four TREE species are culled ABOVE the 40 px detail threshold** — deleted while
  internal structure is still resolvable, not merely while they read as a shape. That is
  a different and worse class of failure than §0 anticipated.
- Nothing in the recipe is within 6× of the 1.5 px vanish threshold at either resolution.

**CC 2026-09-05 — B1.2 CONFIRMED, with the constant corrected.** The spruce is not 14.7 m.
Measured 27.317 m (SOURCE_MODEL; the 29.313 m in `pve_spruce.json` is a Nanite fallback-proxy
RENDER_DATA bound, +7.3%), placed at 0.600–1.150×. The typical conifer reaches 6 px at
**7.66 km** and 1.5 px at **30.6 km**, against an 8.129 km world. Conclusion unchanged and
stronger: **no legal cull-to-nothing distance exists for a tree anywhere inside this world.**
Even Meadow grass (0.387 m placed) has a 124 m silhouette boundary against its 50 m cull.

**CC 2026-09-05 — B1.3 CONFIRMED and re-derived for 4K.** At 90°/3840 the render is
**42.67 ppd, 1.406 arcmin/px**, against a 27" 1440p reference display's ~45 ppd. The render
is still the limiting instrument at 4K, so thresholds stay in render pixels. (At 90°/2560:
28.4 ppd, 2.11 arcmin/px — matches the brief.)

**CC 2026-09-05 — NEW, not in the brief: two of three tree species already ship the
shape-band representation, and the 730 m cull throws it away.** `SpruceSub`'s LOD chain ends
in `MI_half_01_imposter_nowind` (listed in `recipes/alpine_8k.json`'s own `override_materials`);
`ScotsPineTall_01` ships `..._Atlas_Billboards_Tex`, `..._Normal_Tex` and
`ScotsPineTall_01_Billboard_Mat` (`Free/_measured/fab_registry_KiteDemo.json`). Task 7 is
closer to "stop deleting the imposters we have" than to "generate imposters" for these two.

**CC 2026-09-05 — NEW: the cull is already a RANGE, so a fade band exists.** Live `FT_Conifer`
carries `cull_distance {min: 54750, max: 73000}` cm (start = 75% of end) — a 182.5 m band.
Whether anything fades across it is Q3 (`PerInstanceFadeAmount`), still UNVERIFIED. It does
not soften the finding: a fade makes the transition a ramp, but a detail-band object still
ends the ramp at zero with nothing standing where it was.

## DERIVED (from tools, awaiting engine confirmation)
- B1.1 / B1.2 / B1.3 — **moved to PROVEN above** by Task 1, with corrected constants.
- **CC 2026-09-05 — CORRECTION, applies to §0a of the brief and to anything built on it:
  not one of the seven heights in that table survived measurement.** Conifer 14.7 → 27.317 m
  (×1.86); SpruceSub 9.0 → 16.725 (×1.86); SpruceSapling 4.0 → 4.529; Blueberry 0.6 → 0.432;
  Meadow 0.4 → 0.322; Boulder 2.5 → 1.30; ConiferPine had no height at all (a literal `<h>`).
  The table also ignores instance scale, which this world applies to every tree it plants.
  Six of seven errred in the direction that UNDERSTATES the defect. **Every distance in §0a
  and §4 should be re-derived from `species_heights.json` before it is quoted again.**
- **CC 2026-09-05 — CORRECTION: Boulder is not in the mainline.** `recipes/alpine_8k.json`
  `foliage.rock_scatter` holds only the shared physical constants and no species array;
  there is no `foliage/alpine_8k_Boulder.json`. The 140 m cull lives in `recipes/alpine.json`,
  the PRE-8K world that CLAUDE.md declares HISTORY. Carried through Task 1 for completeness;
  it sets nothing shipped today.
- **CC 2026-09-05 — the tool's `ue_screen_size` column is still UNPROVEN** and is explicitly
  fenced off in R-ANGBUDGET until Task 2 opens `SceneManagement.cpp`. Only the pixel columns
  were used for anything above.

## PROPOSED (design, not yet built)
- B1.4 Four-band representation ladder keyed on px height (detail/shape/blob/gone) with a rule: cull only at a boundary where the next band exists. BRIEF §4.
- B1.5 `perception` recipe block; `cull_distance_m` becomes derived. FOR_CLAUDE_CODE Task 6.
- B1.6 Frame time measured in a standalone `-game` process; editor numbers retired. Task 4.
- B1.7 Benchmark rig (3 stations, 1 dolly, 2 profiles, MRQ). `benchmark.json`.
- B1.8 Imposters for the shape band, HLOD Approximated Mesh for the blob band. Task 7.
- B1.9 Nanite Foliage / PVE as a possible single-representation replacement — evaluate only. Task 9.

## TOOLS (tested here, pure Python)
- `scripts/angular_budget.py` — px/distance/ScreenSize per species; verdicts. Formula VERIFY pending (Task 2).
- `scripts/temporal_stability.py` — moving-camera pop detector; self-test PASS (synthetic pop found at the right frame and place).
- `scripts/lod_silhouette_check.py` — LOD chain by coverage/IoU/luma at shown size; self-test PASS.

## REJECTED (with reason)
- Culling to nothing at a distance chosen in metres — pops at every recipe value (B1.1). Replace by derived pixel thresholds + next-band hand-off.
- Editor viewport as the frame-time instrument — game thread pinned ~14 ms by editor overhead across all stations (Ryan's 2026-09-05 report). **CC 2026-09-05 — HALF OF THIS ENTRY IS WITHDRAWN.** The pinned game thread stands. The `get_viewport_size` half does not: `unreal.SystemLibrary.get_viewport_size` **does not exist in UE 5.8** and never did. `measure_frame_cost.py:217` called it inside a `try/except` that wrote `viewport_size: null`, so every artefact carries a null that was then read as evidence of editor overhead. It was an `AttributeError`. Real API: `UnrealEditorSubsystem.get_level_viewport_size()` (editor), `WidgetLayoutLibrary.get_viewport_size(world)` / `PlayerController.get_viewport_size()` (game). Fixed; live read-back **[1321, 1421]**. **Consequence: the editor viewport is 1.88 Mpx against the declared target's 3.69 Mpx — the ratified GPU budgets were measured at roughly half the pixel count the world is judged at.** Task 4's acceptance ("the `viewport_size` field is a number... it answers in `-game`") is therefore testing the wrong thing: it would have answered in the editor too, had the right function been called.
- Triangle count as the LOD acceptance — canopy destroyed while hitting targets (LESSONS 2026-08-14); replaced by silhouette/coverage at shown size.

## REJECTED — FORCING PIE TO HOLD THE WHOLE WORLD (three levers, no cause found)

**CC 2026-09-06.** Recorded as eliminations, with **no invented mechanism**.
Residency in PIE sat at 12–16 of 1024 landscape components throughout.

1. **Warm-up frames.** `EngineWarmUpCount` 180 then 300, with
   `bUseCameraCutForWarmUp` set false so the count actually applies; both read
   back. No change. Warm-up buys TIME, and cells outside the loading RANGE are
   not late — they are not requested.
2. **`wp.Runtime.OverrideRuntimeLoadingRange -grid=MainGrid -range=1200000`**
   in `start_console_commands`. The engine log confirms the command executed
   before the shot, and the sibling `wp.Runtime.MaxLoadingStreamingCells`
   echoed its new value on the next line, so the channel is not at fault. The
   grid name was established from source, not guessed (zero
   `SpatialHashRuntimeGridInfo` actors ⇒ the engine default `MainGrid`,
   `WorldPartitionRuntimeSpatialHash.cpp:1387-1388`; the lookup is an exact
   FName match, `WorldPartitionSubsystem.cpp:563-571`). No change.
3. **`LandscapeLabTools.load_all_world_partition_regions()` in the EDITOR**
   immediately before the render. It works — the editor reached 256 proxies,
   **1024 of 1024** components, 217,102 foliage instances. PIE then reported
   **16 of 1024**. PIE does not inherit editor region loading, notwithstanding
   `UWorldPartition::PostDuplicatePIE` in the log.

**Why none of them worked is UNEXPLAINED.** The obvious next diagnostic,
`wp.Runtime.DumpWorldPartitions`, produces no log output in either the editor
or PIE and needs fixing before it can be used.
**CONSEQUENCE, and it is a design decision rather than a workaround:** stop
trying to force-load PIE. Two instruments instead — `--instrument player`
(PIE/MRQ, near-field residency, what a player sees) and `--instrument truth`
(editor, force-loaded to 1024/1024, HighResShot via `shoot.py`, what is
there). Neither pretends to be the other.

## ORDERING (operator rulings, 2026-09-06)

- **Q4 RULED — Task 7 (HLOD) moves AHEAD of imposters.** Recorded here because
  the session then measured *why* it is right: `Alpine8K` has HLOD **layer
  assets** (`Alpine8K_HLODLayer_Instanced`, `..._Merged`) but **no built HLOD
  actors anywhere** — no `WorldPartitionHLOD` packages exist under
  `Content/__ExternalActors__/Alpine8K/`. So beyond the World Partition
  streaming range there is not a cheap proxy, there is **nothing at all**. An
  imposter result measured in that condition would be measured against a void,
  and the 1–3 km band cannot be judged until something occupies it. HLOD first
  is not a preference; it is the precondition.
- **Q5 RULED — Task 4 (standalone frame time) comes BEFORE any budget
  re-ratification.** The `treeline` and `vista` budgets already carry
  `basis_invalidated: true` from the station re-derivation, and this session
  added a second reason they cannot be re-ratified from editor numbers: the
  editor viewport measured **1321×1421 = 1.88 Mpx against the declared
  3.69 Mpx**, so the existing figures are not at the judged pixel count either.
  Re-ratifying from the editor would lock in two known-wrong bases at once.

## OPEN QUESTIONS (need a ruling or a measurement)
- **Q6 OPEN — the editor idles `/Game/Alpine8K` at 8.2 cores and nobody knows
  why.** Measured 2026-09-08 with the world loaded and NOTHING of ours running:
  8.19 cores over 20 s, 8.28 over 45 s, editor log byte-identical across the
  window (401,071 bytes), no `ShaderCompileWorker` children, working set
  15.1 GB. Sustained, not a transient. This is not merely curious: it is the
  BASELINE every "is the editor busy or hung" judgement is made against, and
  its absence caused the 2026-09-07 misdiagnosis of the HLOD save as a spin at
  5–6.6 cores — *below* idle. Until it is explained, every CPU reading on this
  world is a differential against an unexplained 8.2, and any frame-cost figure
  taken in-editor carries it as unattributed load. Candidates not yet tested:
  a background task with no log category, World Partition editor-side cell
  churn, RVT/Nanite streaming, an editor tick doing work proportional to
  3,269 actors. **Do not treat any of those as the answer without measuring.**
- **Q7 OPEN — the dolly crosses a shadow boundary; is that the dolly's fault or
  the scorer's?** Established 2026-09-08e that the luma drift is scene shading,
  not auto-exposure (percentiles: mean −30% while p10 and p90 both −11%, plus a
  turnaround at frame ~140 and visual confirmation of tree shadows sweeping the
  meadow). So the walk genuinely traverses lit ground into shade. Either
  re-site the dolly to a path that does not cross the boundary, or require the
  incoming tile-wise motion-compensated scorer to tolerate one. A question for
  the new scorer, not for the exposure system.
- Q1 RULED 2026-09-05 (Ryan): judgement camera 3840×2160 / 90°; 2560×1440 is the floor; 8K = inspection only. Both columns in BRIEF §0a.
- Q2 Does the Intel iGPU dev profile run Nanite Foliage at all? Task 9 answers it.
- Q3 Do the PN / KiteDemo foliage materials sample PerInstanceFadeAmount (needed for instance fade)? Task 5 VERIFY.

**CC 2026-09-15 — B1.10 the 512 m detail threshold re-derivation, REPORTED at last (P1-10 / D-1).**
`angular_budget` was re-run at the R-RANGE 512 m fallback on 2026-09-12
(`_verify/bench/2026-09-12/angular_budget_512.json`) and never reported.
Here it is. The angular geometry is loading-range-INDEPENDENT — it maps an
object's height to on-screen pixels at distance — so the thresholds and
the Conifer numbers are IDENTICAL to the 768 m derivation
(`angular_budget_3840x2160.json`): thresholds 40 / 6 / 1.5 px, Conifer
(27.31 m) detail at **1310.9 m**, silhouette at **8739.2 m**, vanish at
**34956.8 m**. Nothing in the angular math moved; the 512-tagged run
re-confirmed Conifer only.
**What moved is the loading-range RULING, not the geometry:** R-RANGE fell
768 → 512 m on the perf gate. The consequence the angular budget makes
concrete: at a 512 m loading range the REAL surface ends at 512 m, but a
Conifer is detail-resolvable to 1310 m and silhouette-visible to 8739 m,
so the band from 512 m outward is carried entirely by the HLOD ladder —
and the recipe's 730 m cull still deletes a **71.8 px** tree (well above
the 6 px silhouette threshold), the visible-pop finding, unchanged by the
range. The 512 vs 768 choice does not change WHERE detail is perceptible;
it changes how much of that perceptible band is real vs proxy.

## NEXT BRIEFS (queued)
- B2 Atmosphere, sky light and grade: blue shadows (sky.intensity 1.8), no aerial perspective (fog start 1500 m), sun disc, height fog second layer; scored on the near_ground and vista stations. Needs bench frames.
- B3 Surface: tiling autocorrelation vs CSF, height-blend layers, forest-floor under canopy, snow by aspect; scored on near_ground and mid_slope.
- B4 Terrain micro-relief at walking scale (pockmarks): slope-gated smoothing in Gaea; RMS relief in 5 m windows on flat ground.
- B5 Density and PCG: perceptual density bands (individuals / texture), PCG migration, canopy material beyond the shape band.
