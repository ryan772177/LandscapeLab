I verified every number against the artefacts. Findings first, then the entry.

---

## CORRECTIONS — read before the recipe

**Three numbers in the brief are CORRECT and one framing is not.**

Verified correct against `Free/_measured/pn_spruce_forest.json`: the imposter is LOD4 at **4 or 6 triangles** across all 14 big trees (`spruce_half_01` is 6); `SmallProp` is `NumLODs=4` (`BaseEngine.ini:2685`) and the 14 big trees carry **5**; `SpruceSub` culls at **730 m** and `SpruceSapling` at **180 m** (`recipes/alpine_8k.json`).

**The brief's "never normalise the LOD groups" is right for the wrong scope.** The hazard applies to the **14 big trees only**. All **7 saplings, including `spruce_small_05`, already have `lod_count` 4** and already carry `SmallProp` — `SetLODGroup` on the sapling truncates nothing. Stating the rule as "the trees have 5" would have a later session believe `SpruceSapling` is at risk and, worse, believe a mesh with 4 LODs is therefore *safe to regroup* — which is true here by accident, not by rule.

**Four numeric/claim errors found in this repo's own derived records:**

1. **`_verify/20260815_d4_rescatter_220k.md` — "both carry imposter LODs" is FALSE.** `spruce_small_05` has `lod_count` 4 and `lod_triangles [2604, 1301, 650, 326]` — LOD3 is 326 triangles of real geometry, not a 4–6 triangle billboard, and it has 3 material slots, not 4. This is the exact fact the sapling's 180 m cull rests on, asserted backwards in the artefact that placed 53,413 of them.
2. **`_verify/20260815_pn_spruce_forest_intake.md` — "roughly 1.5 px at 730 m on a 1080-line frame" is wrong by 3–12x.** At the recipe's own capture settings (`capture.resolution [1920, 1080]`, `fov_deg` 55 on `ridge_wide` / 75 on `forest_floor`), a 4.529 m sapling at `scale_range [0.6, 1.6]` subtends **4.7 to 18.3 px** at 730 m. The 180 m cull is still correct; its recorded justification is not.
3. **`_verify/20260815_pn_spruce_forest_intake.md` — "the worst (`spruce_half_03`/`_low`, 0.293 m) still clears the 0.258 m limit only marginally" is wrong twice.** 0.2935 **exceeds** 0.258, so "clears" inverts it; and 0.258 m is not the applicable bar — `RECIPES.md:3647` derives it as `0.25 x smallest horizontal dimension`, which for `spruce_half_03` (4.5184 x 4.3748 m) is **1.094 m**, cleared by 3.7x. The enforced repo-wide bar is `MAX_PIVOT_OFFSET_M = 1.0` (`scripts/landscape_spec.py:121`).
4. **`ASSETS.md` — imposter "screen size 0.10–0.17" is narrower than measured.** Across the 14 big trees LOD4 screen sizes span **0.06 to 0.20**.

**And one live defect, which outranks the recipe.** The wind-off requirement is recorded, the seven MIs exist (`Free/_measured/pn_nowind_overrides.json`), and **nothing applies them to the placed trees.** `override_materials` appears in `recipes/alpine_8k.json` only on the eight Blueberry *grass varieties*; the instanced-species key set `_VEG` (`scripts/import_heightmap.py:476-479`) does not admit it, so the recipe *cannot* declare it; and `scripts/place_foliage.py` sets only `mesh` (:673) and `cull_distance` (:700-704) on the FoliageType — zero occurrences of `override_material` in the file. `FoliageType_InstancedStaticMesh.override_materials` **does exist** in 5.8 (`PythonStub:394542`, property at :394610). So **108,417 PN spruce are standing in `/Game/Alpine8K` on vendor materials with wind ON**, and `_verify/20260815_alpine8k_noise_floor_per_station.md` (committed `b87e90d0`, 15:27, *after* D4 landed at 15:07) attributes `forest_floor` 2.99x and `trunk_base` 6.65x to "renderer temporal accumulation" while citing an animation check whose material probes only ever saw the two **pre-D4** tree materials. `ASSETS.md`'s "NOT DONE: not scattered … no wind-off material instances authored" is stale on both counts.

---

# R-PN-SPRUCE — PN_interactiveSpruceForest sub-canopy and sapling tiers (PROVISIONAL, UNPROVEN)

**Placed and saved 2026-08-15 in `/Game/Alpine8K` as part of D4's single re-scatter. Restore point: tag `pre-d4-rescatter-220k-20260815`.** Written now because two hazards on this pack are one keystroke each and neither raises an error.

**OPEN DEFECT, stated before the values so it cannot be read as green: the wind-off material instances are authored and NOT APPLIED.** See §6.

## 1. PRECONDITIONS

- **UE 5.8.** All three source citations below are against `C:\Program Files\Epic Games\UE_5.8`.
- Level `/Game/Alpine8K` exists with `Landscape_Alpine8K` (`recipes/alpine_8k.json` → `landscape.level_path`, `scale_xy_cm` 100.0, `location_cm [-406400, -406400, 128000]`).
- The pack is on disk at `LandscapeLab/Content/PN_interactiveSpruceForest/` — **gitignored, 0 tracked files, 363 files, 1.46 GB**. It cannot be restored by git and **must never be written to**.
- **Licence UNRECORDED.** No non-`.uasset` file exists in the pack, so terms are not recoverable from disk (`ASSETS.md`). R-ASSET's licence requirement is UNMET and recorded as a gap, not waived.
- Both meshes carry a VERIFIED row in `Free/_measured/engine_derived.json` → `pn_interactive_spruce_forest`, because there is no FBX and `normalize_asset.py` cannot run. Without those rows `landscape_spec` refuses the recipe.
- R13 lighting applied; `foliage.density_per_hectare` 135.0, `foliage.seed` 20260731.

## 2. EXACT VALUES

**The two meshes, measured on the LIVE assets** (`Free/_measured/pn_spruce_forest.json`, by `scripts/measure_tree_packs.py`). Every figure below was read from that file, not from any narrative:

    SpruceSub   /Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01
      height 16.725 m   width 4.012 m   nanite FALSE   slots 4   lod_group "None"
      pivot_offset_xy 0.0645 m   base_offset_z -0.0024 m
      LOD  0      1      2      3       4
      tri  20695  10347  5174   2587    6      <- LOD4 IS THE IMPOSTER
      scr  1.00   0.99   0.60   0.35    0.17

    SpruceSapling  /Game/PN_interactiveSpruceForest/Meshes/small/spruce_small_05
      height 4.529 m    width 4.271 m   nanite FALSE   slots 3   lod_group "SmallProp"
      pivot_offset_xy 0.2307 m   base_offset_z -0.0002 m
      LOD  0     1     2    3
      tri  2604  1301  650  326        <- REAL GEOMETRY. NO IMPOSTER.
      scr  1.00  0.60  0.20 0.10

**Species blocks, verbatim from `recipes/alpine_8k.json` → `foliage.species`:**

| key | SpruceSub | SpruceSapling |
|---|---|---|
| `layer` | Grass | Grass |
| `weight_share` | 0.25 | 0.20 |
| `slope_deg` | [0.0, 24.0] | **[0.0, 28.0]** |
| `height_m` | [120.0, 640.0] | [120.0, 640.0] |
| `flow_bias` | 0.45 | 0.45 |
| `scale_range` | [0.7, 1.15] | [0.6, 1.6] |
| `align_to_normal` | 0.15 | 0.15 |
| `cull_distance_m` | **730.0** | **180.0** |
| `sink_depth_m` | 0.12 | 0.10 |
| `closure.at_low / at_high` | 1.0 / 0.30 | 1.0 / **0.55** |

Resulting placed heights: SpruceSub **11.71 – 19.23 m**, SpruceSapling **2.72 – 7.25 m**. The four instanced `weight_share` values total exactly 1.0.

**The cull distance is a RANGE, not a scalar.** `place_foliage.py:700-704` writes `Int32Interval(int(cull_cm * 0.75), cull_cm)` and reads it back, refusing if the max does not return. So the live values are **fade 547.5 m / hard 730 m** and **fade 135 m / hard 180 m**.

**WHY THE CULLS DIFFER, AND IT IS NOT A STYLE CHOICE.** `SpruceSub` affords 730 m *because its chain ends in a baked imposter*: LOD4 is a **6-triangle** billboard bound to material slot 3 (`.../MaterialInstances/imposter/high/half_01_imposter`), selected at screen size 0.17. Across all 14 big trees LOD4 is **4 or 6 triangles** at screen size **0.06–0.20**. `spruce_small_05` has **no such tier** — its chain bottoms out at 326 real triangles — so every metre past the cull is paid in full geometry. 180 m instead.

**Do NOT justify the 180 m on sub-pixel grounds.** At `capture.resolution [1920, 1080]` and the recipe's own `fov_deg` (55 on `ridge_wide`, 75 on `forest_floor`), a `spruce_small_05` at 730 m subtends **4.7 to 18.3 px** depending on scale and station. The "roughly 1.5 px" recorded in `_verify/20260815_pn_spruce_forest_intake.md` is wrong by 3–12x. The absent imposter is the whole argument and it is sufficient.

**`SpruceSapling` takes 28° of slope where the mature tiers take 24°.** The constraint on a 20 m conifer is root-plate stability; a 4.5 m sapling does not have one yet.

## 3. ORDERED STEPS

1. **Tag first.** This is a mass foliage regeneration under THE RISKY-OP CHECKPOINT. The executed run used `pre-d4-rescatter-220k-20260815`.
2. Measure both meshes with `scripts/measure_tree_packs.py` and register the rows in `Free/_measured/engine_derived.json`. **Order is load-bearing:** `landscape_spec` refuses a foliage mesh with no VERIFIED normalisation row, and these can never go through `normalize_asset.py`.
3. Author the wind-off child MIs with `scripts/make_nowind_material_instances.py --go` into `/Game/Materials/PN_NoWind/` (ours, tracked). It writes `Free/_measured/pn_nowind_overrides.json`. **No vendor byte is written** — `check_fab_boundary` must read unchanged after this step.
4. Add the two species blocks to `recipes/alpine_8k.json` and validate. Expect **0 foliage errors**.
5. Plan and place with `place_foliage`, **handing it every vegetation plan in the same run** — the orphan sweep deletes anything not in the current run.
6. Save with `python scripts/save_level.py --recipe recipes/alpine_8k.json`. **The `--recipe` is mandatory:** the default is `recipes/alpine.json` and the tool's LEVEL GATE correctly refused with exit 7 when it was omitted, because the package allow-list is derived from the recipe and would have been scoped to a different world.
7. **NOT YET DONE — apply the wind-off overrides to the foliage types.** See §6.

## 4. VERIFICATION

**Placement, counted by the placer's own verification** (`_verify/20260815_d4_rescatter_220k.md`):

    SpruceSub      55,004 instances   acceptance 24.7%
    SpruceSapling  53,413 instances   acceptance 30.0%
    whole recipe  219,659 planned == 219,659 counted in world
    reserve        30,341 under MAX_INSTANCES 250000  (rock_scatter.py:108)
    saved          1,095 packages, all re-read clean, 0 removed
    frame cost     GPU 7.92 ms at forest_floor, against an 11 ms abort bar

**Grounding — TWO REPRESENTATIONS, which is the bar** (non-negotiable 0):

    heightmap, EVERY instance, tolerance +/-0.050 m
      SpruceSub      55,004   mean 0.000  p99 0.001  max 0.001  outside 0
      SpruceSapling  53,413   mean 0.000  p99 0.001  max 0.001  outside 0

    engine COLLISION, 500 samples per species (trace_grounding)
      SpruceSub      500/500  min -0.127  p50 +0.006  p90 +0.015  max +0.098
      SpruceSapling  500/500  min -0.103  p50 +0.006  p90 +0.013  max +0.104
      float 0, buried 0, both species

The heightmap instrument is COVERAGE, not independence — it and the planner read the same map through the same transform. The collision trace shares no source with it and they agree at p50 +0.006 m.

**The imposter, rendered against LOD0** — single variable, `.ForceLOD` 0 → 4 set and read back both times, same parked camera at 35 m (`_verify/20260815_pn_spruce_forest_intake.md`):

    mae 0.01277   6.91% of px moved >2%   max 0.8039
    tree-ish pixel coverage  LOD0 3.916% -> imposter 3.212%  (ratio 0.820)
    silhouette IoU 0.6892

**This is a harder test than reality and it passes.** LOD4 is selected at screen size 0.17, ~100 m+ for a 16.7 m tree; the comparison forces it at 35 m. **What does NOT hold, stated plainly:** cast shadows are largely lost (a camera-facing billboard cannot cast a tree-shaped shadow), and the 0.56–2.56 m saplings degrade to dark blocky clumps under forced LOD4 — which is one more reason the sapling tier is culled rather than imposter'd.

**Frames:** `_verify/20260815_alpine8k_d4_forest_floor.png` (mean 0.5195, 0.088% blown) and `_verify/20260815_alpine8k_d4_ridge_wide.png` (mean 0.7553, 0.047% blown).

**Grade any pixel A/B against the STATION's own floor, never 0.00298.** Measured post-D4 (`_verify/20260815_alpine8k_noise_floor_per_station.md`): `ridge_wide` 0.002449, `diag_topdown` 0.002827, `forest_floor` 0.008899, `sweep_2000` 0.016410, `trunk_base` 0.019815. An n=3 estimate that moved 32% on `forest_floor` within one session — right order of magnitude, not a calibrated constant.

## 5. TWO HAZARDS, EACH ONE KEYSTROKE, NEITHER RAISING AN ERROR

### 5a. NEVER SET A LOD GROUP ON THE 14 BIG TREES

`SmallProp` is declared `NumLODs=4` (`BaseEngine.ini:2685`). The 14 big trees have **5**. `UStaticMesh::SetLODGroup` calls `SetNumSourceModels(DefaultLODCount)` **unconditionally** (`StaticMesh.cpp:5605-5607`), and `SetNumSourceModels` (`StaticMesh.cpp:5944-5974`) takes a shrink branch when `OldNum > Num`: it calls `ClearMeshDescription()`, `GetMeshDescriptionBulkData()->Empty()`, removes the section info from both `GetSectionInfoMap()` and `GetOriginalSectionInfoMap()` for every LOD above the new count, then `SourceModels.SetNum(Num)`.

**So assigning any 4-LOD group to a big tree deletes LOD4 — the imposter.**

**The engine's own comment three lines above says the opposite.** `StaticMesh.cpp:5604`: *"Set the number of LODs to at least the default. If there are already LODs they will be preserved, with default settings of the new LOD group."* The code below it does not preserve them. This is the prose-claims-rot class (non-negotiable 25), in engine source.

**The trap is that the obvious tidy-up is the destructive act.** 15 of the 21 meshes carry `SmallProp` and 6 carry `NAME_None`, inconsistently — `spruce_half_01` is `None` while `spruce_half_01_low` is `SmallProp`; `spruce_full_01` is `SmallProp` while `spruce_full_02`/`_03` are `None`. **RULING: the inconsistency is cosmetic; the fix is not. Do not normalise it.**

Not currently firing — the big trees already sit at 5 LODs *with* `SmallProp` where it is set, so nothing re-applies the group today. **Latent, not active**, and recorded so it stays that way. **Scope: the 7 saplings already have 4 LODs and are unaffected. This is a 14-mesh rule, not a 21-mesh one.**

### 5b. NEVER ENABLE NANITE ON EITHER MESH

`nanite_enabled` is **false on 21 of 21** meshes in the pack and must stay false. `FStaticMeshComponentHelper::CreateSceneProxy` computes `bUseNanite = Component.ShouldCreateNaniteProxy(&NaniteMaterials)` and, when true, returns `Component.CreateStaticMeshSceneProxy(NaniteMaterials, true)` immediately (`StaticMeshComponentHelper.h:533-539`). **The classic LOD chain is never consulted, so LOD4 — the imposter — becomes unreachable.**

The contrast is on disk in this project: the placed `SM_PVE_Norway_Spruce_01_A` reads `nanite_enabled true, lod_count 1` (`Free/_measured/pve_spruce.json`). A Nanite tree has no chain to reach an imposter through. These two are the opposite design and must be left that way.

Corroborating cost, already paid here once: Nanite replaces LOD0 with a reduced fallback (`boulder_medium_01` 4,136 → 1,796), so enabling it on these would both lose the billboard tier *and* decimate LOD0.

## 6. THE WIND-OFF REQUIREMENT — AUTHORED, AND NOT IN EFFECT

**The wind animates with no Blueprint present.** Three frames 5 s apart from one parked camera in a level containing no `PN_GlobalUpdater` and no `PN_Bending_Component`: mean mae 0.005275, and the amplified difference image is a clean filled silhouette of the tree with sky and ground black (`_verify/20260815_pn_wind_is_live.md`). The spatial pattern matches the mechanism, which is what makes it evidence.

**The removal touches no vendor byte.** Wind rides **STATIC SWITCH** parameters — `Level 1 Wind`, `Level 2 Wind`, `Level 3 Wind`, `Level 1 Bending`, `Level 2 Bending`, `Level 3 Bending` — on `MA_Summer` / `MA_Winter` / `MA_Imposter`. A static switch set false in a child MI **compiles the branch out**. Seven child MIs exist under `/Game/Materials/PN_NoWind/` and proved it: mean mae **0.005275 → 0.002310**, 2.3x quieter and **0.78x** the bare-terrain floor, with the diff character changing from a filled silhouette to sparse edge speckle.

**The override lists are POSITIONAL and the two meshes order their slots DIFFERENTLY** (`Free/_measured/pn_nowind_overrides.json`):

    spruce_half_01   trunk, BRANCH, LEAF, imposter
      MI_spruce_half_01_trunk_nowind / _branch_nowind / _leaf_nowind
      MI_half_01_imposter_nowind
    spruce_small_05  trunk, LEAF, BRANCH
      MI_spruce_small_05_trunk_nowind / _leaf_nowind / _branch_nowind

A list built by name-guessing rather than read from `static_materials` silently repaints the tree.

**AND THEY ARE NOT APPLIED TO ANYTHING IN `/Game/Alpine8K`.** Stated plainly because nothing else states it:

- `recipes/alpine_8k.json` carries `override_materials` on the **eight Blueberry grass varieties only**. Neither tree species has it.
- It could not carry it if someone tried: the instanced-species key set `_VEG` (`scripts/import_heightmap.py:476-479`) lists `name, mesh, layer, weight_share, slope_deg, height_m, flow_bias, scale_range, align_to_normal, system, cull_distance_m, density_per_10m2, varieties, lods, sink_depth_m, closure` — **no `override_materials`** — and the validator refuses unknown keys. The grass path admits it (`import_heightmap.py:805-806`, and `GrassVariety.override_materials` at `PythonStub:121628`); the instanced path does not.
- `scripts/place_foliage.py` sets `mesh` (:673) and `cull_distance` (:700-704) on the FoliageType and nothing else. `grep override_material scripts/place_foliage.py` returns nothing.
- `scripts/make_nowind_material_instances.py --apply-in-open-level` walks `get_all_level_actors()` and writes `override_materials` on `StaticMeshComponent`s (:240-262). That is the **scratch-scene proof path**. It never touches a FoliageType.

**The mechanism exists in 5.8 and is unused:** `FoliageType_InstancedStaticMesh.override_materials` (`PythonStub:394542`, property :394610-394616) and `nanite_override_materials` (:394534).

**Consequence: 108,417 PN spruce are standing on vendor materials with wind ON**, and `_verify/20260815_alpine8k_noise_floor_per_station.md` — committed **after** D4 placed them — attributes `forest_floor` 2.99x and `trunk_base` 6.65x to renderer temporal accumulation on the strength of an animation check whose material probes only ever saw the two **pre-D4** tree materials. **Those two station floors are confounded and must be re-measured, or the overrides applied first.**

## 7. REJECTED

```
SetLODGroup / lod_group on any of the 14 big trees  ->  LOD4 is DELETED,
the mesh reports lod_count 4, the imposter tier is gone and distant forest
disappears at the cull instead of flattening to a billboard; NO ERROR IS
RAISED  ->  leave the groups exactly as shipped, 15 SmallProp / 6 NAME_None
->  BaseEngine.ini:2685; StaticMesh.cpp:5605-5607 and 5944-5974
```
```
Trusting the engine's own comment "If there are already LODs they will be
preserved"  ->  it is FALSE three lines above the code that truncates them
->  read SetNumSourceModels before believing SetLODGroup  ->  StaticMesh.cpp:5604
```
```
"Normalising the inconsistent LOD groups" as tidy-up  ->  the same tree
differs between high and low (spruce_half_01 None vs spruce_half_01_low
SmallProp) and the tidy-up is the destructive act  ->  the inconsistency is
cosmetic; RULED not to normalise  ->  Free/_measured/pn_spruce_forest.json
```
```
nanite_enabled True on either mesh  ->  the Nanite proxy is returned and the
classic LOD chain is never consulted, so the imposter is unreachable; LOD0 is
additionally replaced by a reduced fallback  ->  FALSE on both, as shipped
->  StaticMeshComponentHelper.h:533-539
```
```
cull_distance_m 730 on SpruceSapling  ->  53,413 instances drawn to 730 m at
326 real triangles each with no billboard tier to fall to  ->  180.0
->  Free/_measured/pn_spruce_forest.json lod_triangles [2604,1301,650,326]
```
```
"Both new tiers carry imposter LODs"  ->  written into the artefact that
placed them (_verify/20260815_d4_rescatter_220k.md) and FALSE for
SpruceSapling; it is 4 LODs and 3 material slots  ->  only SpruceSub has an
imposter; the sapling's cull is what stands in for it
```
```
Justifying the 180 m cull as "sub-pixel at 730 m, ~1.5 px"  ->  a 4.529 m
sapling at scale 0.6-1.6 subtends 4.7-18.3 px at 730 m at the recipe's own
1920x1080 and fov 55/75  ->  justify it on the ABSENT IMPOSTER, which is
sufficient  ->  recipes/alpine_8k.json capture block
```
```
Declaring override_materials on an instanced species in the recipe  ->
"unknown key in foliage.species[N]: override_materials", exit non-zero; the
key set is CLOSED  ->  the schema admits it on grass varieties ONLY, so the
wind-off MIs are currently unreachable from the instanced path and the
placed trees run vendor materials with wind ON  ->  import_heightmap.py:476-479
vs :805-806; place_foliage.py:673; PythonStub:394542
```
```
Building an override list by material NAME  ->  spruce_half_01 orders its
slots trunk/branch/leaf and spruce_small_05 orders trunk/leaf/branch, so a
name-guessed list silently repaints the tree  ->  read static_materials and
keep the list POSITIONAL  ->  Free/_measured/pn_nowind_overrides.json
```
```
Grading a pixel A/B on this world against the 0.00298 floor  ->  the
vegetation stations run 2.99x to 6.65x it and a real difference cannot be
separated from the floor  ->  use the station's own floor
->  _verify/20260815_alpine8k_noise_floor_per_station.md
```
```
Using foliage.CullAll to isolate these trees' cost  ->  it reads back 1, the
tool reports CONDITION SET, and the trees stay on screen: it is the HISM path
and r.Nanite.Foliage is 1  ->  it does not apply to the PN trees (they are
NOT Nanite) but the recorded Alpine8K decomposition taken with it is
confounded  ->  HierarchicalInstancedStaticMesh.cpp:63-67
```

## 8. WHAT IS NOT ESTABLISHED

- **The wind-off overrides are not applied to the placed forest.** §6. Until they are, no frame-to-frame comparison on a vegetation station on this world is trustworthy.
- **The imposters' value at altitude is unproven in the real world.** `ridge_wide` does not adjudicate it — untuned aerial perspective swamps the forest at that range, a pre-existing recorded issue. The only imposter evidence is the 35 m forced-LOD comparison.
- **The `_branch` material is lost mid-chain, before the imposter.** `spruce_half_01` drops it at LOD3 (screen 0.35); trunk and leaf survive. Plausibly benign on a conifer whose branches are needle-occluded, but it is a real composition change and no render has adjudicated it.
- **The licence is unrecorded** and not recoverable from disk. Recovering it needs Ryan's Fab library page.
- **No frame A/B against the pre-D4 state** at a matched resolution, so no pixel-difference claim is made for this intake.
- **`RECIPES.md:1545` still names `fir_tree_01_c_LOD0` as the live conifer** and `R-BAKE` is stamped PROVEN while superseded for this pack. Both need supersession notes.