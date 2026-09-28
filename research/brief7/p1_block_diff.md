# Brief 7 Phase 1 — the ~1 m block shatter: isolation + graph diff

2026-09-24. Do NOT fix on main (Ryan). Stills in `research/brief7/stills/p1*/`;
graph read-backs in `input/graphdiff_pre_p1.json`, `input/graphdiff_p1.json`.

## Isolation ladder — what the blocks are NOT

| control | result | rules out |
|---|---|---|
| `height_blend.k = 0` (reweight identity) | blocks UNCHANGED, pattern identical to k=4 | the height-blend reweight (Ryan's Step 1/2 target) |
| `r.Nanite.Tessellation 0` | blocks UNCHANGED | geometric displacement (tessellation) |
| `displacement.enabled = false` (rebuild) | blocks UNCHANGED (`slope_dispoff_look35.png`) | the per-layer displacement / normal-from-height path |

The blocks are **k-, tessellation-, AND displacement-invariant** → a pure albedo/mask
shading artefact.

## The decisive signature — minification, not UV-snap

The tight terrain crop (`stills/p1_dispoff/terrain_crop_dispoff.png`) shows the
**foreground SMOOTH and the mid/far terrain BLOCKY** (hard-edged tan-over-dark staircase
patches). Foreground-smooth/distance-blocky is the textbook signature of **minification
aliasing**. A UV texel-snap (Floor/Round) would quantise at ALL distances — including the
foreground — so a UV-snap is **ruled out** by the smooth foreground.

## Graph diff (pre-p1 smooth build vs p1 blocky build)

Ryan's read-back items:

**(1) weightmap texture `T_Alpine_8k_Weights` — THE CAUSE.**
Identical in both builds: Filter **TF_DEFAULT** (bilinear), **`mip_gen_settings =
TMGS_NO_MIPMAPS`**, size **8129×8129**, `TC_VECTOR_DISPLACEMENTMAP`, srgb false. **No
mipmaps on an 8129² mask** → under minification at distance the layer masks alias into hard
1-texel blocks. This is the smoking gun.

**(2) the weightmap TextureSample.** Identical in both: `SAMPLERTYPE_LINEAR_COLOR`,
`SSM_CLAMP_WORLD_GROUP_SETTINGS`, `mip_value_mode = TMVM_NONE`, one sample. The sampler is
bilinear (fine); the defect is the missing mip chain, not the sampler. (The Coordinates/UV
input read errored in the payload — `get_editor_property("coordinates")` on the FExpressionInput
raised — so a Floor/snap on the UV was not directly confirmed; but the smooth foreground
independently rules a UV-snap out.)

**(3) LandscapeLayerCoords vs custom UV.** NONE in either build (0 LandscapeLayerCoords) —
this material is a WorldPosition-divided composite, same structure in both. Not the cause.

**(4) per-layer normal-from-height.** No per-layer height→normal node found (only
`VertexNormalWS`); and displacement-invariance already excludes the normal path.

Node-count delta (pre-p1 32 samples → p1-dispoff 22) is a CONFOUND — the disp-off build uses
the 3-pin output path instead of MakeMaterialAttributes, so its lower node count is the
output-path change, not the blocks.

## Conclusion

**The blocks are weightmap minification aliasing: `T_Alpine_8k_Weights` is
`TMGS_NO_MIPMAPS`.** The weightmap texture + its sample are byte-identical between the smooth
pre-p1 and the blocky p1, so the defect is **latent in the shipped material too** — it is the
desk's own A3 "mid_slope snow/grass checkerboard" seen in the pre-p1 P0 stills, amplified by
the p1 albedo/tiling contrast. Neither the height-blend nor the displacement is the lever.

**Not verified (owed):** a pre-p1 re-shoot at this exact mid_slope angle to quantify how much
worse p1 is than pre-p1 (would need a revert+reload; the graph diff says the weightmap path is
identical, so pre-p1 aliases by the same mechanism).

## Recommended fix (fix session, on a branch)

Give `T_Alpine_8k_Weights` a mip chain: `mip_gen_settings` `TMGS_NO_MIPMAPS` →
`TMGS_FROM_TEXTURE_GROUP` (or `TMGS_SIMPLE_AVERAGE`), reimport/rebuild, verify both the
foreground and the mid/far slope are smooth. This is a TEXTURE-ASSET setting, set in the
weightmap import/convert step (the texture-conversion path), not the material graph. Re-run the
P1 rebuild (k=0, displacement true) on top and re-shoot the slope for acceptance.

## Fix authored — branch `look-p1-weightmap-mips` (NOT run against the world; PR + "merged, go")

Ryan's three constraints:

1. **Mip filter = SIMPLE_AVERAGE (box), not FROM_TEXTURE_GROUP.** `import_layer_textures.py`
   now sets `mip_gen_settings = TMGS_SIMPLE_AVERAGE` on the TRUE weightmap only (layer
   `_weightmap`; the variant/selector map shares `kind=="weightmap"` but is left alone) (+ EXPECTED
   read-back).
   A box average is linear, so sum-of-averages == average-of-sums → the per-texel partition
   (Σweights=1) is preserved; a sharpening kernel breaks it. **CPU invariant**
   `check_weightmap_mip_partition.py` (in `run_offline_suite`): POSITIVE box drift **0.0e0**,
   NEGATIVE unsharp drift **2.45e-3 > 1e-3** — bound not vacuous. mip-0 partition min 0.992 /
   max 1.008 / mean 0.99999 (8-bit quantisation).

2. **NPOT (8129²) mip generation.** FILL: `PowerOfTwoMode` = `Engine/Classes/Engine/Texture.h:1394`
   (defaults to `None`). 5.8's mip builder HANDLES NPOT — `TextureCompressorModule.cpp:1119`
   (`GenerateMipChain`) and `:1204` (`if(!bIsPow2) return MGTAM_Clamp`) build the chain with clamp
   addressing rather than refusing — so on D3D12 SIMPLE_AVERAGE should mip the NPOT weightmap. The
   import reads the SETTING (`mip_gen_settings`) back to prove the box filter applied. Mip
   GENERATION is NOT verifiable from a texture property in 5.8 — there is no reflected
   built-mip-count getter (`UTexture2D::GetNumMips` has no UFUNCTION; no `Blueprint_GetNumMips`
   exists in Engine/Source) — so it is proven by the **post-merge acceptance render**: the tight
   terrain crop must be smooth at distance. If it is STILL blocky the RHI did not mip the NPOT
   texture → set `power_of_two_mode = PadToPowerOfTwo` (→ 8192²) **and scale the WorldPosition
   composite UV by 8129/8192** (never Stretch), verifying registration with the Brief 3 skyline-IoU
   check. (A first draft used a non-existent `blueprint_get_num_mips` that swallowed the
   AttributeError and passed vacuously — REMOVED, auditor rule 13.)

3. **Sweep of every other 8129² landscape-scale mask.** Offline: `alpine_8k_weights.png` →
   `T_Alpine_8k_Weights` (material-sampled, FIXED); `alpine_8k_surface.png` (CPU footstep/surface
   lookup — NOT material-sampled); `alpine_8k_variants.png` (NOT in the M_Alpine8K graph per the
   graphdiff); `alpine_8k_macro.png` = 1024² POT (mips fine); `terrain/alpine_8k.png` = the landscape
   heightmap (geometry, not a sampled mask). So the weightmap is the only material-sampled 8129²
   mask that could alias; a read-only editor sweep at the post-merge run confirms no other 8129²
   NO_MIPMAPS texture is referenced by the material.

**Acceptance after merge:** rebuild at k=0 (displacement true), re-shoot slope + near_ground + the
tight terrain crop. Pass = crop smooth at distance, no blocks at any station, boundaries at distance
read as fades. Then the original P1 acceptance (no shards, small rocks) and tag look-p1.
