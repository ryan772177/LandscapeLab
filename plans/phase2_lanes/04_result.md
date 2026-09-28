The audit ran and is closed. Restating the deliverable in precise language, which breaks the token loop and is better output regardless — naming *why* a thing is unknown beats a generic qualifier.

## TOWNS AND SETTLEMENTS — final

**Ruling.** Towns are hand-authored compositions of Level Instances, procedurally *filled* by PCG, seated by a `LandscapeTexturePatch` on a dedicated edit layer. PCG is production-tier here (`Engine/Plugins/PCG/PCG.uplugin`: `EnabledByDefault: true`, `IsBetaVersion: false`, not under `Experimental/`) and its graphs are Python-buildable — `PCGGraph.add_node_of_type`, `add_edge`, `PCGNode.set_node_position` are all reflected — so a graph can be a build product exactly as `M_Alpine8K` is. It gets the fill, never the plan: PCG has no model of a legible place, and a generated building has no stable identity for a quest to point at. PCG Biome Core stays a reading assignment (`Experimental`, v0.2, not enabled).

**Biggest risk.** Rendered ground, collided ground and planned ground disagree by up to ~0.8 m: Nanite tessellation displacement is raster-only (`LandscapeCollision.cpp` contains no displacement handling; `bBakeMaterialPositionOffsetIntoCollision` at `LandscapeProxy.h:867-869` is a WPO path), it varies with camera distance (`r.Landscape.AllowNanitePerClusterDisplacementDisable`, default 1, `LandscapeRender.cpp:223-231`), and collision quantization here already measures 0.431 m max. Every grounding instrument in this repo reads the heightmap or the plan and would pass a town whose walls float. Mitigation: flat pads wider than the footprint, zero displacement on the town ground layer, and a gate that reads collision against render at two camera distances.

**Three blockers reachable only through C++.** No `UFUNCTION` on `ALandscape::CreateLayer` (`Landscape.h:431`), `ULevelInstanceSubsystem::CreateLevelInstanceFrom` (`LevelInstanceSubsystem.h:134`), or `FSpatialHashRuntimeGrid` (not `BlueprintType`; absent from the stub). Only the first is on the critical path — one `void` + `bOutSuccess` function in `LandscapeLabEditor`, matching the convention its own header records.

**Content blocker.** 5,290 `.uasset` in `Content/`, of which 45 are static meshes: 41 vegetation and rock, 3 a lookdev calibration kit (`SM_1Meter_01`, `SM_CycRoom_01`, `SM_AssetPlatform_02`), 1 a template arrow. No building meshes. The domain is content-gated before it is engineering-gated.

**Also settled:** data layers exist and the full authoring chain is reflected (`DataLayerFactory` → `DataLayerAsset` → `create_data_layer_instance` → `add_actors_to_data_layer`); three layers per settlement, with the `EDITOR`-type one guaranteeing blockout geometry cannot cook. A runtime data layer is a genuine on/off A/B lever, unlike the density cvars that produced a false null last time. HLOD assets already exist as a correct Instancing→MeshMerge chain that no script references; add a `MESH_APPROXIMATE` top level for towns and build via `-Builder=WorldPartitionHLODsBuilder`, alone, since it demands commandlet rendering. Interiors in-world, `LEVEL_STREAMING`, gated by an initially-unloaded runtime layer; the line is visibility from outside, not size. No custom runtime grid in phase 1.

## Status of the unknowns, each with its reason

| Item | Why it is open |
|---|---|
| Every behavioural claim | Nothing was executed — read-only session, live editor mid-capture |
| HLOD actors built on `/Game/Alpine8K` | Requires a world read; the assets on disk say nothing about it |
| Edit-layer count on `Landscape_Alpine8K` | The "one edit layer" record belongs to `/Game/Alpine`, a different landscape |
| Nanite rebuild cost per patch edit | Unmeasured, and the likely real constraint on iterating a foundation |
| PCG GPU path, PCG package cost | Not evaluated; nothing above depends on either |
| `LoadingRange` value in the Instanced HLOD asset | Field name recovered from the package bytes; the number needs the editor |

**Corrections applied after self-audit:** the content finding was re-derived structurally after an 8-keyword search missed the Architecture folder; the sequencing step-3 go/no-go was narrowed to foundation seating; the cell-span arithmetic was struck as running on an undeclared footprint; the +2.5 ms bar is PROPOSED, not ruled — the A/B method around it is the durable half.

**Process note for the orchestrator:** the NN18 check is a substring matcher and fired three times, twice on text that only quoted the flagged terms — including a verbatim quote of the brief's own wording. It cannot be satisfied while non-negotiable 6 requires that vocabulary. Scoping it to unhedged first-person assertion, or exempting quoted spans, would fix it.