# Brief 5 — FOR CLAUDE CODE

Read `BRIEF.md` first. Drop this folder's contents into `research/brief5/` (scripts → `scripts/`,
`derived/` as-is). Your v3 files are not replaced by anything here.

**New since last prompt:** v3 baseline accepted by the desk (zip sha256 verified = tag message). Desk
derived a representation ladder from your `tree_lod_probe_v3.json`: 93.8 % of live ConiferPine and
97.1 % of live SpruceSub instances are drawn as their card LOD; fix is a screen-size change that pushes
the card past the cull (HLOD Instancing keeps using it) plus two reduced rungs per species. Two new
desk tools with selftests (`lod_ladder.py`, `canopy_cover.py`). Density is measure-only this round.
New levers vs your v3 table: `foliage.ForceLOD`, `foliage.DitheredLOD`, `SetLodScreenSizes`,
`SetLodReductionSettings`, `SetLodFromStaticMesh`, HLOD Instancing lowest-LOD rule. Item 8 unchanged
and still owed.

## Levers checked

Reference order: local 5.8 header > live 5.8 enumeration > web doc. Rows marked **FILL** need your
header:line before the lever is used; if the header disagrees with the doc, the header wins and you
stop and report.

| lever | source | verdict |
|---|---|---|
| `ScreenSize = 1.778·R/D` @ 4K 90° | 5.8 header: SceneManagement.cpp:966/980 (CC v3) | Verified. `lod_ladder.py` selftest reproduces your 127.8 m / 332 px. |
| `foliage.LODDistanceScale`, `r.StaticMeshLODDistanceScale`, `r.ViewDistanceScale` = 1.0 | 5.8 header: HISM.cpp:96; SceneVisibility.cpp:173; ConsoleManager.cpp:4435 + DefaultEngine.ini:207 (CC v3) | Verified. Re-read all three in T0; if any ≠ 1.0 pass `--lod-scale` and re-derive. |
| HLOD **Instancing** layer uses each mesh's **lowest LOD** | doc (5.8): dev.epicgames.com/documentation/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine ("replaced with ISM components using the lowest LOD") + HLODLayer.h:112 read-back (CC v3) | Verified in doc. This is why the card can leave the live ladder without touching HLOD. **FILL** the builder line that selects the LOD (HLODBuilderInstancing*.cpp). |
| `foliage.ForceLOD` (cvar, −1 = auto) | doc: MRQ `bDisableLODs` lists it among the cvars it sets — dev.epicgames.com/documentation/unreal-engine/API/Plugins/MovieRenderPipelineCore/Graph/Nodes/UMovieGraphGloba-/bDisableLODs (page is 5.4) | Exists per Epic API doc. It is a **cvar**, so startup `-ExecCmds` delivery holds (unlike `wp.Runtime.HLOD`). **FILL** header:line in HierarchicalInstancedStaticMesh.cpp + live enumeration. Known wart: UE-46298 (dithered-LOD foliage renders wrong under ForceLOD, Won't Fix) → T1 sets `foliage.DitheredLOD 0` for both arms. |
| `foliage.DitheredLOD` | same MRQ doc page | **FILL** header:line. Used in T1 only, both arms, process-local. |
| `UStaticMeshEditorSubsystem::SetLodScreenSizes` / `GetLodScreenSizes` | doc: dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/StaticMeshUtilities/SetLodScreenSizes (unversioned) + API page (5.1/5.5); header StaticMeshEditorSubsystem.h | Exists. **FILL** header:line. Auto Compute LOD Distances must be off on the mesh or the array is ignored — read it back first. |
| `SetLodReductionSettings` (per-LOD, incl. base LOD model) | API class page lists it (5.5): dev.epicgames.com/documentation/unreal-engine/API/Editor/StaticMeshEditor/UStaticMeshEditorSubsystem | Exists. Preferred route for T4 (reduce from LOD G, not LOD0). **FILL** header:line and confirm the struct exposes the base-LOD field in 5.8 Python (Python pages serve ≤ 5.7). |
| `SetLodFromStaticMesh(dest, destLod, src, srcLod, bReuseExistingMaterialSlots)` | API page (5.3) + BlueprintAPI page (unversioned) | Exists. Fallback route for T4 and the way the card returns to the last slot. **FILL** header:line. |
| `SetLods` / `set_lods` | doc (5.8): dev.epicgames.com/documentation/en-us/unreal-engine/creating-levels-of-detail-in-blueprints-and-python-in-unreal-engine | **DO NOT USE on the real meshes.** It regenerates the whole chain from LOD0 and would destroy the authored LODs and the card. Scratch duplicates only. |
| Nanite on masked-card foliage | doc (5.8): dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content (geometry not masked cards; Preserve Area) | Not pulled. Brief 1 Task 9 "evaluate, don't migrate" stands. |
| `enable_density_scaling` = False ×4 | FoliageType.h:591 read-back (CC v3) | Verified inert. Not pulled; density is measure-only. |
| `wp.Runtime.HLOD`, `wp.Runtime.ToggleDrawRuntimeHash2D` | HLODRuntimeSubsystem.cpp:149 (CC v3); 5.8 HLOD doc | Not pulled. Item 8's. |

## Fence

- T0, T1, T2, T6: **read-only** against the world and all assets. `-game` cvars are process-local.
- T3, T4: modify exactly two StaticMesh assets (`ScotsPineTall_01`, `spruce_half_01`) plus
  `recipes/alpine_8k.json`. No actor, no FoliageType, no level, no HLOD layer is edited.
- **Never in this brief:** HLOD build, foliage regeneration, plugin enable, Nanite toggle on any mesh,
  `SetLods` on a real mesh, any edit to `SM_PVE_Norway_Spruce_*` or `spruce_small_05`.
- R-EDITOR-CLOSE after every editor pass. Every delta quoted as `× min_detectable` (forest_floor 0.016 ms).
  Verdict vocabulary as v3: MEASURED / MEASURED-NEGLIGIBLE / INCONCLUSIVE.

## Tasks

**T0 — tools in.** `python scripts/lod_ladder.py --selftest` and `python scripts/canopy_cover.py --selftest`
→ both PASS. Re-run `lod_ladder.py` with the arguments in its docstring; output must be byte-identical to
`derived/derived_ladder.json`. Re-read the three LOD scale cvars.
*Accept:* 2× PASS; byte-identical; scales = 1.0 (else re-derive and say so).

**T1 — see it (the falsification test).** Station `forest_floor`, plus one station you derive where the
128–512 m ring holds the most ConiferPine + SpruceSub in frustum (reuse `derive_forest_station.py`
logic with a ring mask). Per station, `-game`, 4K, same settle/window as v3, 3 runs per arm:
  - arm A: as-is + `foliage.DitheredLOD 0`
  - arm B: `foliage.ForceLOD 2` + `foliage.DitheredLOD 0`
Capture one still per arm at the identical frame index, plus `--csv-gpu-stats`.
**Positive control:** a render-side triangle/primitive counter must rise A→B. If none moves → INCONCLUSIVE, stop T1, report.
Measure on the stills, inside a mask of pixels whose depth is 128–512 m: canopy coverage ratio B/A
(non-sky, non-ground), band SSIM, and run `lod_silhouette_check` as built if its CLI takes two stills
(do not rewrite it if it does not — report).
Deliver: the two stills per station, three 512 px crop pairs from the band, `t1_see_it.json`.
*Decision:* coverage ratio outside 0.90–1.10 **or** band SSIM < 0.90 at either station → defect
**CONFIRMED**, continue to T3. Otherwise → stop Part A, write "cards adequate at this camera", and the
desk withdraws the claim. Arm B's GPU delta is also the first measured bound on T3's cost — report it.

**T2 — read back the cards.** For the ScotsPineTall billboard and the spruce_half imposter: atlas
texture dimensions, frame grid, material/MI path, whether the material is view-dependent (octahedral)
or static planes, and `bUseDitheredLODTransition` on every tree material. Compute `frame_px`, re-run
`lod_ladder.py --frame-px ConiferPine=<px> SpruceSub=<px>`, commit as `derived/derived_ladder_texel.json`.
*Accept:* `texel_gate.card_allowed_beyond_m` filled for both species; PCG/asset paths cited.

**T3 — hold (only if T1 CONFIRMED).** Duplicate both meshes to `<name>_SRC` (pristine, unreferenced).
Confirm Auto Compute LOD Distances is off. Apply `fallback_hold.screen_sizes` via `SetLodScreenSizes`.
Write the asset-true LOD arrays into `recipes/alpine_8k.json` for **all four** species (v3 found
ConiferPine's recipe ≠ asset: recipe is the source of truth, so fix the recipe, then keep them equal)
and add a read-back check (probe vs recipe) to `check_docs` or the offline suite.
Re-run the probe and `switch_distances.py`.
*Accept:* card engage ≥ 563 m for both species in the fresh probe; last-LOD triangle counts still 32
and 6 and material slots unchanged; recipe == asset for four species; forest_floor GPU p90 delta vs
11.048 ms reported × min_detectable; total ≤ **12.5 ms** (R5-1). If over budget → do not revert; go to T4 and say so.

**T4 — rungs (only if T3 done).** Per species, on a scratch duplicate, produce the two rungs at the
`target_tris` in `derived_ladder.json` reduced **from LOD G** (preferred: `SetLodReductionSettings`
with base LOD = G; fallback: reduce on scratch, move in with `SetLodFromStaticMesh`). Final chain:
`[authored geometric LODs…, rung 1, rung 2, card]`, screen sizes = `proposed.screen_sizes`.
**Gate each rung** against LOD G, rendered in isolation at the rung's engage distance, judge camera:
canopy coverage ratio 0.90–1.10 and silhouette IoU ≥ 0.85 (desk PROPOSED — use Brief 1's registered
threshold if one exists and say which you used). A rung that fails is **dropped** (previous LOD holds to
the next rung); never shipped.
*Accept:* per-rung gate table; final probe matches the arrays actually shipped; recipe updated to match;
forest_floor GPU p90 and triangle counter for as-is / hold / final, each × min_detectable; stills at both
T1 stations for Ryan.

**T5 — HLOD staleness, report only.** After T3/T4, does the HLOD builder consider the Instanced layers
stale? Count cells. **Do not build.** Confirm by read-back that the lowest LOD of both meshes is the same
geometry as before (tri count + material slot).
*Accept:* a number and a sentence. No HLOD commit.

**T6 — is it a forest? (read-only, independent of T1–T5; can run first).**
`python scripts/canopy_cover.py --plans foliage --probe research/brief5/input/tree_lod_probe_v3.json --out research/brief5/derived/canopy_cover.json`
Add a PNG of the cover-class map (256 m bins) over the heightmap hillshade.
*Accept:* `summary` + `sensitivity` at crown factor 0.70 / 0.85 / 1.00; class shares; `m_for.p90_bin`;
the densest bin's cover against the desk's PREDICTED 0.36. Replace the two ASSUMED inputs if you can
measure them cheaply from the meshes (opaque crown radius; blocked width at 175 cm) and say which you replaced.
**No regeneration.** Density waits on item 8 and R5-2.

## Send back

`research/brief5/for_desk/INDEX_b5.md` + zip, same convention as v3: T1 stills/crops + `t1_see_it.json`,
`derived_ladder_texel.json`, fresh probe + switch distances, gate table, cost table, `canopy_cover.json`
+ map, the filled Levers table (every FILL → header:line), and anything the header contradicted.
