# Cobblestone streets — design (2026-10-10, Ryan: "do the streets with cobblestone next")

Status: DRAFT for design review. Nothing built.
Roots (docs/environment.md): REPO_ROOT `C:\Users\Admin\UE5LandscapePipeline`, UE_PROJECT_ROOT
`C:\Users\Admin\UE5LandscapePipeline\LandscapeLab`.

## The problem, measured

The 371 street pieces are engine Cubes scaled into 20 cm slabs (`scripts/payloads/town_kit_place_streets.py`),
seated on a straight chord between the piece ends. Stills `_verify/lookdev/townkit_organic01/street_lane_s.png`
and `street_main_e.png` show three defects:

1. **Grass on the road.** The landscape GRASS types (Meadow*, **MeadowBoulders**, …) grow on and through the
   slabs, because they are spawned from the landscape's layer weights, which know nothing about the slabs. A
   MeadowBoulders boulder sits on the main road 10 m from the plaza. No IFA clearing can remove them: they are
   not foliage instances.
2. **Slabs buried or floating.** The slab is a flat chord over terrain that undulates (cut/fill up to the
   1.8 m street gate), so it dips under the ground in places and the road reads as broken grey patches.
3. **Engine-grey primitive** material.

## The design: streets are PART OF THE LANDSCAPE SURFACE

One offline street mask texture, consumed by the landscape material in two places:

- **Surface.** Base colour, roughness and normal of `M_Alpine8K` lerp to a cobblestone surface by the mask.
  The road then follows the terrain exactly (defect 2 cannot occur), and is lit, shadowed, displaced and
  RVT-written by the same pass as the ground.
- **Grass.** Every LandscapeGrassOutput input is `_masks[layer]` (`make_landscape_material.py:4256-4259`).
  Each one is multiplied by (1 − G), where G is the mask's grass-exclusion channel. That cuts grass and
  boulders off the roads, and (new) out of the house footprints, so no grass grows through house floors.
  The albedo masks are NOT changed, so the ground colour is unaffected outside the streets.

Then the 371 primitive slabs are deleted. Street geometry comes from the landscape.

### The mask: `textures/alpine_8k_street_mask.png` (new, generated, stamped)

- **Producer:** new `scripts/build_street_mask.py`. Offline and deterministic, it reads
  `city/alpine_basin_town_plan.json` (streets, plaza, squares) and the kit manifest (house footprints).
- **Coverage:** a square 1024 m box over the town, from `town_kit_load_region.town_points` (one declaration),
  sampled at 4096² = **25 cm/px** (streets are 3.5–7 m, so 14–28 px wide).
- **R = cobble.** The union of street slabs (len × width, oriented), the plaza disc and the 4 squares.
  Edge feathered by a recipe sigma (`feather_m`, initial 0.35 m), so the stone→grass transition is not a
  pixel step.
- **G = grass exclusion.** R ∪ (house footprint + `house_margin_m`, initial 0.5 m).
- **B, A = 0** (reserved).
- **Border:** the outer 2 px are forced to 0, so TA_CLAMP sampling outside the box reads 0. Asserted by the
  producer.
- **Sidecar:** `.json` with box origin/size, px/m, plan + manifest sha16, per-channel coverage.
  `stamp_plan.py` style.
- **Import:** `import_layer_textures.py`, a new kind `street_mask` with the SAME settings as `weightmap`
  (srgb False, TC_VECTOR_DISPLACEMENTMAP uncompressed, TA_CLAMP, TMGS_SIMPLE_AVERAGE), read back by the
  existing gate.

### Material (make_landscape_material.py, recipe `material.street_overlay`, schema row)

```
street_overlay: {
  mask:            "textures/alpine_8k_street_mask.png",
  box_cm:          [x0, y0, size]           # copied from the mask sidecar AND checked equal (refuse)
  surface:         {albedo, normal, roughness: /Game/Megascans/Surfaces/Cobblestone/T_Cobblestone_*}
  tile_m:          2.0                      # world-aligned UV = WorldPos.xy / tile
  albedo_tint:     [1,1,1]
  displacement:    "flatten"                # lerp _dsp toward displacement center on R
  grass_exclude:   true                     # multiply every grass input by (1 - G)
}
```

- **Insertion point:** immediately before `# OUTPUTS` (:3857), after the macro-variation multiply. So
  `_col/_rgh/_nrm/_dsp` change ONCE and both the main outputs and the RVT output (:3885) see the streets.
- **Mask UV:** (WorldPosition.xy − box.xy) / box.size, sampled with `SAMPLERTYPE_LinearColor`, the same
  sampler class as the weightmap (to be confirmed against the weightmap's declared sampler in the builder:
  ONE declaration).
- **Cobble textures:** sampler types are read from the engine's own choice before any overwrite (skill rule:
  AutoSetSampleType). Albedo Color, normal Normal, roughness per its compression.
  `audit_material_samplers.py` verifies the built graph.
- **Normal:** lerp(terrain_n, cobble_n, R), then normalize. Same tangent space; the landscape is
  near-horizontal under streets.
- **PREFLIGHT** loads the mask texture and all 3 cobble textures and refuses BEFORE the destructive clear
  (skill: "preflight everything before the clear").
- **CPU model:** `_cpu_street_blend(base, cobble, r)` mirrors the lerp, and `_cpu_grass_exclude(m, g)`
  mirrors the multiply. Invariants at import:
  - r = 0 is the identity, byte-equal to the pre-change composite;
  - r = 1 is pure cobble;
  - grass(g = 1) == 0;
  - an INDEPENDENT reference: the grass multiply equals numpy elementwise on a random mask.
- **Off switch:** absent `street_overlay` reproduces today's graph exactly (positive control: the
  expression set and wiring are identical, as the displacement route already does).

### Order (each verified before the next)

1. build_street_mask.py → png + sidecar. Offline gate:
   - every street centreline sample reads R ≥ 0.99;
   - every house centre reads G = 1 and R = 0;
   - 1 m outside a street edge reads R < 0.05;
   - border = 0.
2. Recipe block + schema row; `import_layer_textures.py` (street_mask kind) → read-back.
3. make_landscape_material.py rebuild. Then:
   - post-build assertion;
   - audit_material_samplers;
   - compile clean;
   - landscape RVT unchanged in structure.
4. **Stills BEFORE deleting slabs** (the slabs hide the road): street_lane_s, street_main_e, ridge.
5. Delete the 371 City streets (town_kit_clear --tag City --kinds streets --expect 371, from the plan),
   then save.
6. **Downstream, measured:**
   - **R-NAVBUILD:** the slabs had collision, and removing them changes the walk surface by ≤ 20 cm.
   - **Reachability:** reinstall.
   - **Lattice:** reinstall, 0 changes outside the town.
   - **Encounters:** re-verify the adopted file.
   - **HLOD:** setup, because source actors left; then census, then cells (town_points), then check.
7. Stills again: street level + ridge. RECIPES R-TOWNKIT amendment + REJECTED.

### Costs and risks

- `M_Alpine8K` is the main world material (129 KB binary). The rebuild is the proven path, and the off-switch
  is the recipe block.
- **Landscape HLOD** uses an override material (`make_hlod_override_material.py`). Streets will NOT show in
  far-field HLOD unless that material also gets the overlay. At ≥ 256 m a 5 m road is ~0.3 % of a frame
  (judge on the ridge still; follow-up if visible).
- **Grass exclusion** removes cover inside house footprints and roads only. Meadow ALBEDO is untouched.
- **Cobble aligned to the world grid**, not to each street. Megascans cobblestone is near-isotropic; judge by
  still. Per-street rotation would need a direction channel (B/A reserved).
- **Texture memory:** 4096² RGBA8 uncompressed with mips ≈ 85 MB. Measure VRAM before/after (perf check).

## Cobblestone assets, MEASURED offline (registry analyst 2026-10-10; package AR tags + serialized props)

| asset | measured | consequence |
|---|---|---|
| SM_Cobblestone_00 / _01 | 100 x 100 x 4 / 11 cm flat patches; LOD0 9,201 / 7,156 tris; Nanite **False**; 4 LODs; box collision | mesh tiling would be 1 patch per m² (~1,900 m² of road); confirms the TEXTURE overlay for v1 |
| MI_Cobblestone | parent `/Game/Materials/Masters/M_BlendMaster`, mesh-UV (NOT world-aligned), tiling 1; PhysMaterial PM_Cobblestone; RVT refs (inert) | the vendor MI is NOT usable on the landscape; we sample its textures in M_Alpine8K |
| T_Cobblestone_A | 8192², DXT5, TC_Default, **sRGB True** | albedo sampler Color |
| T_Cobblestone_N | 8192², BC5, TC_Normalmap, sRGB False | sampler Normal |
| T_Cobblestone_R | 8192², DXT1, TC_Default, **sRGB True**, channel packing UNKNOWN (vendor param "MRF") | **NOT used in v1**: roughness = recipe constant `roughness` (with albedo-luminance variation) until the packing is measured |
| hazard | 8K sources on a cold DDC trigger 8K encodes (GroundRevealRock hang class) | set `MaxTextureSize` = `max_texture_px` (recipe, initial 2048) on A and N via the API BEFORE the first material compile, and read it back. A 2 m tile at 2048² is 1 mm/texel |

## Questions for the design reviewer

1. Is a landscape-material overlay the right engine mechanism here? Alternatives: DBuffer decals per piece
   (do not cut grass); landscape layer painting (the world uses a baked weightmap, not painted layers);
   **landscape splines** with a road mesh (cut grass? deform landscape?); RVT-based decals. Cite source.
2. Grass exclusion via the grass-output mask: confirm a (1−G) multiply on the GrassOutput input reaches the
   grass density (LandscapeGrass compute), and the grass maps rebuild without a manual step.
3. Uncompressed 4096² RGBA vs a smaller format (G8 per channel, BC4/BC5)?
4. Any order or downstream step missing (RVT invalidation, the grass map cache, HLOD).

## Design review 2026-10-10: GO-WITH-CHANGES, and how each change landed

1. **The "<= 20 cm walk-surface" claim is withdrawn.** Slabs bridged dips by up to the 1.8 m street gate.
   Acceptance is counts against the baseline instead: streets 371/371, doors >= 348/349 (TownKit_101 expected
   still open), and 0 lattice cells changed outside the town.
2. **Fence tag:** `pre-cobble-streets-20261010`, set before the material build (runbook step 3).
3. **One declaration, twice:**
   - (i) the `street_mask` import uses kind `"weightmap"`, the same EXPECTED dict, aliased. Box-average mips via
     `import_layer_textures.BOX_MIP_LAYERS`, one list for set and read-back;
   - (ii) the recipe holds the producer inputs, and the SIDECAR holds the derived box. `street_overlay_spec`
     refuses on any mismatch or stale input hash. CORRECTION to the text above: the box is centred on the
     bounding box of the CURRENT plan streets + manifest houses (`build_street_mask.box_for`), not on
     `town_points` (that union includes the deleted lattice town).
4. **Read-backs:**
   - (i) the existing plan-driven preflight checks size class/srgb/compression for the mask and the cobble pair;
   - (ii) `scripts/cap_street_textures.py --apply` sets `max_texture_size` = `max_texture_px` (2048) with a
     property re-read, and the material preflight REFUSES before the clear unless the cap holds in its own
     session (the persistence proof);
   - (iii) `num_samplers` is read back after compile;
   - (iv) VRAM is measured before and after (runbook).
5. **Stills carry counted acceptance:** grass/boulder instances on road samples = 0, and the RVT-blended
   boulder bases at street edges are judged by name.
6. **`tile_m` 2.0 is tagged `_tile_size_UNSTATED`** in the recipe (the scan's physical size is unpublished).
   1024 texels/m >= the 814.9 budget.
7. **House-footprint grass exclusion is DECLARED** as an addition: `exclude_grass_in_houses` (true), with
   `_exclude_grass_in_houses` prose.
8. **Surface is albedo + normal only.** T_Cobblestone_R is not used; roughness = `saturate(roughness +
   variation x (0.5 - lum))`, with CPU mirror `_cpu_street_rough` and invariants (identity at variation 0,
   [0,1], monotone in luminance). Mutation-tested: 4 mutations, 4 caught.

**DEVIATION from the text above:** the street normal is a PLAIN lerp, not lerp-then-normalize. Every layer
normal in this builder is a plain lerp, and the engine normalizes the Normal input. Consistency with the
existing chain wins.

**Grass caveat (review Q2):** the grass map is 1 m per texel. So G's cobble part is grown by `grass_margin_m`
0.75 m, and sub-metre feathers are invisible to grass.

## Addendum 2026-10-10b: boulder exclusion (B channel) -- the "two rocks on the street"

**Finding (LESSONS 2026-10-10ff).** The two rocks at the main road's east end
(`_verify/lookdev/townkit_cobble01/top_main_east.png`) are **MeadowBoulders** landscape-grass instances
(`foliage.species[12]`, GroundRevealRock001/002, scale up to 4.0 / 3.5). They exist only at runtime. Grass spawns at a
POINT, and (1 - G) stops only points within `grass_margin_m` 0.75 m of the cobble. A boulder rooted 1 m off the street
lies across it. Editor census: 0 rock instances in the town box (386 resident actors), 0 rock meshes within 15 m of
either rock (87 sources, all kit pieces).

**Design.**
- **Mask B = large-grass exclusion.** It uses the same shapes as G (streets, plaza, squares, and house footprints +
  `house_margin_m` when `exclude_grass_in_houses`), grown by `boulder_margin_m` instead of `grass_margin_m`. It uses
  the same ramp. B >= G everywhere by construction, and that is asserted.
- **`boulder_margin_m`** = measured max reach (`Free/_measured/meadow_boulder_reach.json`: max horizontal
  pivot-to-bounds-corner distance x max variety scale) + `grass_margin_m` (the 1 m grass-map quantisation already
  justified for G). The builder REFUSES if the recipe value is below that sum, reading the measurement file.
- **Per-species channel.** Each grass species takes `street_keep_channel`: "G" (default, today's behaviour) or "B".
  MeadowBoulders = "B". The material multiplies that species' grass input by (1 - B) instead of (1 - G). No other
  species changes, so meadow grass still reaches 0.75 m from the cobble.
- **Gates added to build_street_mask.py:**
  - 6. B >= G at every pixel.
  - 7. Probes at measured reach + sqrt(2) + 0.5 m outside each street's long edge read B == 255 (superseded the
    pre-review "boulder_margin_m - 0.5 m"; see the review section below).
  - House centres read B == 255 when houses are excluded.
  - Every gate prints its counts, and a count of 0 refuses.
- **Sidecar.** Adds `boulder_margin_m`, and B is described as a real channel. `street_overlay_spec` checks
  `boulder_margin_m` equal to the sidecar's, like the other producer keys.
- **Material.** Adds `_street_keep_b = OneMinus(mask.B)` when any species asks for B. The payload reports the
  channel used per grass input, and the build REFUSES if the report disagrees with the recipe. CPU invariant:
  keep_B <= keep_G for every pixel of the built mask (offline, on the real png) -- implemented in
  `street_overlay_spec`, which reads the png on disk, so a post-bake edit is caught (audit F2).

**Order.**
1. Measure the reach.
2. Make the recipe + schema rows.
3. `build_street_mask.py --write`, with gates.
4. `import_layer_textures.py --only street_mask`, with read-back.
5. Material rebuild on `/Game/LookDevMtn`, then audit_material_samplers, then rebuild again (the audit dirties).
6. Re-save the landscape proxies (R-P3-CLUTTER step 3: proxy-saved GrassData).
7. `-game` stills top_main_east (same pose) + ridge: the two rocks are gone, and meadow boulders still stand
   outside the town.

**Not touched:** navmesh, reachability, lattice, encounters, HLOD. Grass varieties carry no collision and no HLOD
representation, so removing grass instances changes none of them. The design reviewer is asked to confirm the
collision claim.

### Design review 2026-10-10b: GO-WITH-CHANGES, and how each change landed

- **Q1/Q2 confirmed.** Grass components are NoCollision, cannot affect navigation (LandscapeGrass.cpp:3170-3173),
  and are RF_Transient, so never HLOD-relevant (ActorComponent.cpp:3424-3438). Navmesh, reachability, lattice,
  encounters and HLOD are untouched.
- **Q4 confirmed.** TC_VectorDisplacementmap is BGRA8 (Texture.cpp:4301-4304), and B is another pin of the same
  TextureSample.
- **Q6 confirmed.** The proxy re-save is required (R-TOWNKIT REJECTED; `grass.GrassMap.UseRuntimeGeneration` 0).
- **Change 1, landed.** The margin is not reach + 0.75 m. It is reach + the spawn slack, which has four terms:
  - sqrt(2) m grass-cell diagonal;
  - 0.5 m mip allowance, UNVERIFIED (a ceiling);
  - one 0.25 m mask texel;
  - feather_m/2.

  `build_street_mask.py` refuses below this floor. Gate 7 probes B == 255 at reach + sqrt(2) + 0.5 m, so the
  raster terms are measured.
- **Change 2, landed.** The tilt bound is Rock slope lo 29 deg + Grass band feather 6 deg = 35 deg, JUDGED. The
  species `slope_deg` is unenforced for grass. With it, reach = 9.70 m, floor = 12.04 m, and the recipe sets 12.25 m.
- **Change 3, landed.** The instrument formula is (pivot-to-bounds-corner + (|origin.z| + extent.z) x sin(tilt))
  x max scale.
- **Change 4, recorded.** `ALandscapeProxy::AddExclusionBox` (LandscapeProxy.h:1177-1183) was considered and
  rejected on four grounds:
  - it is not Python-reachable;
  - it is transient and not recipe-driven;
  - it applies to every species;
  - it still tests only the spawn point.
- **Change 5, landed.** An unknown `street_keep_channel` refuses at validation and in the reducer. The channel
  travels in `_chan` beside `_wire`, and is read back as `grass_keep_channels` and checked against the recipe.
- **Change 6, adopted.** Acceptance uses the same-pose still and `grass.GrassMap.Dump`, never
  `GetOverlappingXxxCount` (it has no CPU copy, so it reads 0).
