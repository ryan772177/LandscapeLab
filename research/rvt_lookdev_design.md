# RVT on the look rig — design (2026-10-03)

Requested by Ryan (Gemini brief): Runtime Virtual Texturing to (1) let meshes blend into the landscape and
(2) cut the cost of the 5-layer landscape material, measured before the Alpine8K carry-over. Rig only
(/Game/LookDevMtn). API surface researched from 5.8 source with citations (summary below).

## Stages (each measured: perf_standalone, rig hero station, n=3, editor closed, GPUSceneInstanceCount beside ms)

A. **Baseline** — the current rig (rounds 1-27), no RVT.
B. **Write-only** — landscape renders into two RVTs; the main pass is UNCHANGED. Measures pure RVT overhead.
C. **Boulder grounding** — MeadowBoulders sample the RVTs: the bottom `blend_cm` of each rock takes the
   landscape colour/normal. Measured on top of B.
D. **Landscape samples its own RVT** (the optimisation) — main-pass BaseColor/Roughness/Normal come from the
   colour RVT via `MaterialExpressionRuntimeVirtualTextureReplace` (Default = RVT sample, VirtualTextureOutput =
   the existing layer graph). Displacement stays computed (never from RVT). Measured on top of C. Highest risk:
   Substrate is on (DefaultEngine.ini:54) and RVT Output under Substrate is unverified; normal space of the
   BASE_COLOR_NORMAL_ROUGHNESS sample must be verified by a positive control frame before D is kept.

## Assets and actors (recipe: `recipes/rvt_lookdev.json`, tool: `scripts/make_rvt.py`, find-or-create, idempotent)

- `/Game/Lookdev/RVT/RVT_Lookdev_Color` — material_type BASE_COLOR_NORMAL_ROUGHNESS, tile_size 2 (256 px),
  tile_count 9 (512 tiles -> 131,072 px over 2,016 m = 1.54 cm/texel), compress True, adaptive False.
- `/Game/Lookdev/RVT/RVT_Lookdev_Height` — WORLD_HEIGHT, tile_size 2, tile_count 6 (16,384 px = 12.3 cm/texel).
- Two `RuntimeVirtualTextureVolume` actors tagged `LL_RVT_Color` / `LL_RVT_Height` (find-or-spawn by tag, never by
  label). Transform set by hand (SetBounds is C++-only): location = landscape min corner, scale3d = world size in
  cm, rotation = landscape rotation. Rig: location (-100800, -100800, 0), scale (201600, 201600, 256000)
  (2016 quads x 100 cm; z_scale 256000 cm, landscape z 128000 -> world z 0..256000). Read back after set.
- Landscape: parent `runtime_virtual_textures = [Color, Height]` (LandscapeOverridable; propagates unless a proxy
  overrode it), then re-save all proxies (actor descriptors carry the RVT property). Read back on 3 proxies.
- `r.VirtualTextures` live value read back first; refuse if 0.

## Material changes

- `make_landscape_material.py`: optional `material.rvt_output {color, height}` -> a
  `MaterialExpressionRuntimeVirtualTextureOutput` fed BaseColor = final composite colour, Roughness = final
  roughness, Normal = final normal, WorldHeight = AbsoluteWorldPosition.Z. Added after the composite, so the
  existing graph and its assertions are untouched. Plan rows: none (no texture sampled in stage B).
- Stage D (separate change, separate audit): `material.rvt_main_pass` -> RVT Sample nodes + Replace.
- Boulders (stage C): `make_rvt_blend_material.py` duplicates the GroundRevealRock materials into
  `/Game/Materials/Lookdev/` (no vendor edit), injects: `h = saturate(1 - (WorldPos.Z - RVTHeight.WorldHeight) /
  LL_RVTBlendCm)`, BaseColor = lerp(rock, RVTColor.BaseColor, h * LL_RVTBlendStrength), Normal likewise; child MIs
  per source instance; MeadowBoulders varieties `override_materials`. blend_cm 25 (Gemini: bottom 20-30 cm).

## Rollback
Tag before each stage. Removing: clear the landscape array, delete the two volumes by tag (dry run first),
drop the recipe blocks, rebuild. RVT assets left unreferenced are harmless.

## Measured in the editor 2026-10-03 (read back, not assumed)
r.VirtualTextures 1; r.VT.RVT.EnableBaseColorRoughness 1; r.VT.RVT.EnableWorldHeight 1; r.Substrate 1.
64 streaming proxies; union of proxy bounds X/Y -100800 .. ~101200 cm, Z 41488 .. 136738 cm (414.9 .. 1367.4 m);
landscape actor location (-100800, -100800, 128000); 0 RVT volumes. Proposed tighter Z for the volumes:
min 40000 cm, size 100000 cm (400 .. 1400 m) -> height precision ~2.5x better than 0 .. 2560 m.

## Open questions for the reviewer
1. Is the volume transform mapping (min corner + scale = size) right for a landscape whose actor is NOT at the
   min corner? (Rig landscape location (-100800, -100800, 128000).)
2. Substrate + RVT Output: any known incompatibility in 5.8?
3. Is WorldHeight = AbsoluteWorldPosition.Z correct, or does the output expect a value in the volume's local 0..1?
4. Does a Nanite landscape still render RVT pages (research says yes: the regular component proxy draws them,
   LandscapeRender.cpp:2489-2512)?

## REVIEW 2026-10-03 (design-reviewer, Opus): HOLD -> changes adopted

Answers (citations from the review): volume transform min-corner + size is right (RuntimeVirtualTextureSetBounds.cpp:84-88,
RuntimeVirtualTextureComponent.cpp:273, RuntimeVirtualTexture.cpp:615-620); no Substrate incompatibility found for the
Output node (VirtualTextureMaterial.usf:100-108, RuntimeVirtualTextureRender.cpp:569-573), stage D unverified; WorldHeight
is world Z in cm, packed against the volume Z range (VirtualTextureMaterial.usf:66-69,155; VirtualTextureCommon.ush:1002-1005)
and MUST be connected (unconnected = constant 0, MaterialExpressions.cpp:3087); a Nanite landscape still renders RVT pages
from the regular component proxy (LandscapeRender.cpp:2166-2185, 2498-2513) but from the UNDISPLACED heightfield; VRAM
~126 MB (264 px physical tiles incl. border, RuntimeVirtualTexture.h:113,116; 64 MB default pool per type,
VirtualTexturePoolConfig.h:64; editor pools auto-grow, -game does not, :72).

Adopted changes:
1. RVT normal is WORLD space: TransformVector tangent->world before the Output node; boulders transform world->tangent.
2. WorldHeight connected to AbsoluteWorldPosition.Z; pin wiring proved by a positive-control frame (boulders fully
   landscape-tinted at strength 1, large band) before any tuning -- refuse to continue if the frame is unchanged.
3. compress_textures (not compress); landscape virtual_texture_render_pass_type pinned ALWAYS and read back (LandscapeProxy.h:663).
4. ONE declaration: recipes/rvt_lookdev.json names the RVT assets; the landscape material and the boulder material read
   the paths from it (material.rvt_output = the recipe path, not the asset paths).
5. Each perf run reports VT pool residency (rhi.dumpresourcememory summary name=VirtualTexture).
6. Boulder blend_cm validated against DISPLACED ground before it is trusted (RVT height is undisplaced; Rock disp 2 m).
7. STAGE D DROPPED on the rig: RVT lookup is XY-only (RuntimeVirtualTexture.cpp:616-617), so vertical faces collapse to a
   strip -- it would undo the r7 triplanar fix on the cliffs -- and displacement still samples every layer's height map, so
   the saving is partial. Gemini's "optimize the 5-layer material" premise is recorded as not holding for this terrain.
