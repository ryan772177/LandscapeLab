# R-HLODTEX acceptance — ⛔ FAILS. 4096 reaches no baked texture.

**Measured over all 2,267 cells, 0 unloadable. 2,058 baked textures, every
one 1024×1024. Zero at 4096.**

Acceptance was "4096 in all three [landscape cells]". The sample is not
three — it is the whole population — and the answer is uniform.

**Task 6 (Task 5 acceptance) is therefore NOT RUN, per its gate.**

---

## The numbers, each with its denominator

| measurement | value | denominator |
|---|---|---|
| HLOD cells, Alpine8K | **2,267** | matches the build manifest exactly |
| cells across all worlds | 2,395 | 128 belong to Canyon / CoastBench / ForgeWorld etc. |
| cells unloadable | **0** | 2,267 |
| layer tally | **Merged 1,042 / Instanced 1,225** | 2,267 |
| baked textures, Merged layer | 2,058 | all `_Material_*` generated |
| …at 1024 | **2,058** | 2,058 |
| …at 4096 | **0** | 2,058 |
| source textures, Instanced layer | 6,018 | referenced, not baked |
| landscape-named textures | **768, all 1024** | Instanced layer, source not bake |

The layer tally **independently reproduces the build attribution**
(1,042 Merged + 1,225 Instanced) from the asset registry rather than the
build log — two instruments, one answer (NN8).

Per-batch `written` series, against the 2,267 approvals:

    98 98 98 98 98 98 98 97 96 96 93 93 93 93 92 92 92 92 92 92 92 92 92 92
    sum written 2,267   sum cells 2,267   manifest 2,267   torn 0

## Why 4096 never appears

`ALandscapeProxy.HLODTextureSize` is read **only** by
`ULandscapeHLODBuilder`, and only when that builder BAKES
(`LandscapeHLODBuilder.cpp:109-115`; it is hashed only under
`SpecificSize`). In this world's layer configuration the landscape never
reaches a baking builder:

* **Instanced layer** (`INSTANCING`) — instances the ORIGINAL meshes.
  It bakes nothing. Its 6,018 textures are source assets
  (`T_Norway_Spruce_Bark_01_C` and friends at 4096/2048/1024) whose
  sizes are properties of the vendor art, not of any HLOD setting.
* **Merged layer** (`MESH_APPROXIMATE`) — builds from the **Instanced
  layer's HLOD actors**, not from landscape components. Its bake size
  comes from that layer's own material settings, which read
  **1024×1024** in the 2026-09-13 dump. All 2,058 baked textures match
  that number exactly.

So R-HLODTEX set a real property to a real value on all 257 actors —
verified 257/257, 0 outliers — and **that value governs nothing in the
current configuration.** It is the same shape as the Task 5 write ruled
VOID on 09-13 (B3.21): a correct write to a lever that is not in the
path.

⭐ **The build was not wasted.** Every cell still rebuilt (2,267 approvals,
0 rejects) because the hash changed — `HLODTextureSize` is hashed even
though the value is never consumed by these builders. The world is
uniform and current; it simply is not 4096 anywhere.

## What could not be measured, and why

Task 1 asked for cells containing `LandscapeStreamingProxy` and proxies
found vs 257. **That cannot be asked through the Python API.**

`AWorldPartitionHLOD`'s editor-only data is not reflected. All 15
candidate names from `HLODActor.h:214-245` raise *"Failed to find
property"*, enumerated in one pass rather than guessed:

    source_actors  input_stats  hlod_bounds  min_visible_distance
    hlod_stats  hlod_build_report  hlod_resources_package_path
    lod_level  require_warmup  hlod_rebuild_policy_data_set
    subactors_hlod_layer  sub_actors_hlod_layer  hlod_sub_actors
    source_cell_name  source_cell

They are `private` bare `UPROPERTY()` under `WITH_EDITORONLY_DATA`. The
only method of interest on the class is `export_hlod_assets`. This is
the same class of limitation as `HLODLayer` (23 names, all methods, zero
properties) — **editor-only private UPROPERTYs are not part of the
Python contract**, and a source-actor census needs a different
instrument entirely.

The adjacent evidence that IS available: 768 landscape-named textures
appear in Instanced cells, all as SOURCE references at 1024 — consistent
with the landscape being present in the Instanced layer and never baked.

## Getter used for the texture dimensions

`Texture2D.blueprint_get_size_x()` / `blueprint_get_size_y()`, with
`get_editor_property("imported_size")` as the fallback. Both were read
per texture so a disagreement would be visible; none disagreed.

Route to the texture, after two dead ends worth recording:

1. `MaterialEditingLibrary.get_used_textures` → returned nothing.
2. Asset registry on the cell's package → lists only the
   `WorldPartitionHLOD` actor; the baked mesh is an INNER OBJECT
   (`<package>.StaticMesh_Alpine8K_HLODLayer_Merged_0`), so it has no
   registry row.
3. **Worked:** component → `get_num_materials()` → `get_material(i)` →
   `texture_parameter_values` → `parameter_value`.

## Reference used

Local **UE 5.8 C++ headers** in the installed engine, plus live
enumeration of the reflected Python surface. Epic's published Python API
pages serve 5.7 at most, so they were not relied on; the headers are
ground truth for this engine and the enumeration is ground truth for
what Python can reach.

## What needs a ruling

Making 4096 mean something requires the landscape to reach a baking
builder — i.e. a layer change, not a property change. Options, neither
applied:

1. Give the landscape proxies their own MESH_MERGE/MESH_APPROXIMATE
   layer (`Alpine8K_HLODLayer_Landscape` already exists and is ruled
   REDUNDANT — it would be revived rather than deleted).
2. Raise the Merged layer's own `material_settings.texture_size` from
   1024, which WOULD change every one of the 2,058 baked textures and
   costs a full rebuild.

Option 2 is the only one that changes what renders today. Both are
rulings.
