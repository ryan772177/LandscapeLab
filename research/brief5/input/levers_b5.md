# Brief 5 — levers table, header:line filled (overnight, 2026-09-20/21)

**Engine-source reads only (standing rule 1). UE 5.8 at
`C:\Program Files\Epic Games\UE_5.8\Engine`.** Fills every row the desk left as a
doc URL or "FILL header:line". Nothing pulled/set; source verification only.

| lever | verified at (file:line) | value / meaning | status |
|---|---|---|---|
| LOD ScreenSize → distance | `Runtime/Engine/Private/SceneManagement.cpp:966` (`ComputeBoundsScreenSize`) / `:980` (`ComputeBoundsDrawDistance`) | `D = 1.778·R/ScreenSize` at 4K 90° hFOV (P11 dominates) | verified (v3) |
| `foliage.LODDistanceScale` | `Runtime/Engine/Private/HierarchicalInstancedStaticMesh.cpp:96` | default 1.0 | verified |
| `r.StaticMeshLODDistanceScale` | `Runtime/Renderer/Private/SceneVisibility.cpp:173` | default 1.0 ("higher → LODs earlier") | verified |
| `r.ViewDistanceScale` | `Runtime/Core/Private/HAL/ConsoleManager.cpp:4435` + `LandscapeLab/Config/DefaultEngine.ini:207` | 1.0 (default AND ini-pinned) | verified |
| `foliage.ForceLOD` | `HierarchicalInstancedStaticMesh.cpp:48-51` | **int, default -1**; if ≥0 forces every foliage instance to that LOD. Process-local cvar. | FILLED (source). Live enumeration deferred — needs the editor pass that Brief 5 T2 (desk, absent) would have justified. |
| `foliage.DitheredLOD` | `HierarchicalInstancedStaticMesh.cpp:69-72` | **int, default 1**; 1 = dithered LOD crossfade, 0 = popping. Process-local. | FILLED (source). Live enumeration deferred (as above). |
| (related, same file) | `foliage.OnlyLOD` :53 (def -1), `foliage.DisableCull` :58 (def 0), `foliage.CullAll` :63 (def 0, ECVF_Scalability), `foliage.OverestimateLOD` :74 (def 0) | foliage LOD/cull family | recorded for completeness |
| HLOD Instancing layer = ISMs at lowest LOD | `Engine/Plugins/Editor/WorldPartitionHLODUtilities/.../Builders/HLODBuilderInstancing.cpp:61` (`Build`), `:113-127` (creates ISM from source SMComponents, Nanite preserved at `:117` when `HasValidNaniteData()` and not `bDisallowNanite`) | INSTANCING batches source instances into ISMs; per the 5.8 doc it uses the source mesh's lowest LOD (selection is in `UHLODBuilder::BatchInstances`, base). Layer type read back live = INSTANCING (editor_census_v3.json). | verified (doc + read-back); builder file:line filled |
| `SetLodScreenSizes` | `Editor/StaticMeshEditor/Public/StaticMeshEditorSubsystem.h:177` | writes per-LOD ScreenSizes; **Auto Compute LOD Distances must be off** or it is ignored | FILLED. FORBIDDEN on real meshes tonight (regenerates chain) — scratch dupes only; Q5/Q6 desk-blocked anyway. |
| `GetLodScreenSizes` | `StaticMeshEditorSubsystem.h:168` | reads per-LOD ScreenSizes (the read-back used by tree_lod_probe) | FILLED |
| `SetLodReductionSettings` | `StaticMeshEditorSubsystem.h:72` | sets `FMeshReductionSettings` per LOD | FILLED. Real-mesh edits are Q6 (desk-blocked). |
| `SetLodFromStaticMesh` | `StaticMeshEditorSubsystem.h:143` | copies a LOD from another mesh | FILLED. Q6 (desk-blocked). |
| `wp.Runtime.HLOD` | `Runtime/Engine/Private/WorldPartition/HLOD/HLODRuntimeSubsystem.cpp:149` | `FAutoConsoleCommand` (command, no echo); game-world only; sets static `WorldPartitionHLODEnabled` (`:147`) | verified (v3) |
| HLOD `layer_type` | `Runtime/Engine/Classes/WorldPartition/HLOD/HLODLayer.h:112` (read back) | Instanced=INSTANCING, Merged=MESH_APPROXIMATE | verified (v3) |
| `enable_density_scaling` (FoliageType) | `Runtime/Foliage/Public/FoliageType.h:591` (read back) | False ×4 → `foliage.DensityScale` inert | verified (v3) |
| Nanite Foliage (project) | `Runtime/Engine/Classes/Engine/RendererSettings.h:1550` + `LandscapeLab/Config/DefaultEngine.ini:63` | enabled (`r.Nanite.Foliage=True`) | verified (v3) |
| `wp.Runtime.ToggleDrawRuntimeHash2D` | 5.8 WP-HLOD doc (candidate item-8 control) | runtime view of loaded HLOD cells | UNVERIFIED in 5.8 live enumeration — scoped in ITEM8_PLAN, not pulled |

**Deferred (not a header issue — an input/editor issue):**
- `foliage.ForceLOD` / `foliage.DitheredLOD` live process values: need a read-only
  editor (or `-game`) enumeration. The editor pass that would carry it was tied to
  Brief 5 T2 (card-atlas texel read), whose desk script + `derived_ladder.json` are
  absent, so the pass is not justified tonight. Source defaults recorded above.
- `SetLod*` are WRITE APIs, FORBIDDEN on real meshes tonight; their Q5/Q6 consumers
  are desk-blocked. Header:line filled for when the brief arrives.
