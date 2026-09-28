# Brief 7 A2 — dark far-forest imposter: step-1 read-back (REPORT + STOP, desk rules)

2026-09-25, read-only (offscreen editor). The dark far-forest is the **SpruceSub foliage imposter
LOD** (last turn's `foliage.ForceLOD 0` proof). This step read back the imposter material, its atlas
bindings and their content, and the graph paths. **Verdict: every binding is present, every atlas
asset exists AND its content is correct, and every base-colour parameter is nominal — so this is NOT
a null/missing/stale/black-atlas fault.** Per the desk's step-1 gate, the material-graph paths are
reported below and the fix is left to the desk. The desk's "base colour zero" premise is disproven.

## Which species actually has an imposter — a deviation from the brief

Only **FT_SpruceSub** (mesh `spruce_half_01`, pack `PN_interactiveSpruceForest`) has a dedicated
imposter LOD material. The other three the desk named do NOT:

| FoliageType | mesh | imposter LOD material? |
|---|---|---|
| FT_SpruceSub | spruce_half_01 | **YES** — `half_01_imposter` (slot 3), base `MA_Imposter` |
| FT_Conifer | SM_PVE_Norway_Spruce_01_A | no imposter-named slot |
| FT_ConiferPine | ScotsPineTall_01 (KiteDemo) | no imposter-named slot |
| FT_SpruceSapling | spruce_small_05 | no imposter-named slot (trunk/leaf/branch only) |

So the dark-box cluster is the spruce forest imposter. The Conifer/Pine/SpruceSapling last-LOD
material identity was not resolved this step (they are not `*_imposter`); if they also read dark at
distance it is a separate mesh-LOD material, not this imposter.

## The read-back table — SpruceSub imposter `half_01_imposter` (all 2026-08-14, one coherent import)

| item | value | verdict |
|---|---|---|
| base material | `MA_Imposter` | Epic ImpostorBaker master |
| shading model | `MSM_TWO_SIDED_FOLIAGE` | subsurface foliage |
| blend | `BLEND_MASKED`, two-sided, `opacity_mask_clip` 0.333 | opacity IS wired |
| `Albedo` param | `half_01_imposter_A`, **4096×4096**, RGB (no alpha) | BOUND, exists |
| — content | mean R86 / G77 / B30, 100% nonzero, max 182 | **correct green octahedral spruce sheet** (see albedo_atlas_view.png) — NOT black |
| `Normal` param | `half_01_imposter_N`, **4064×4064**, TC_NORMALMAP, srgb off | BOUND; valid normal map (R/G~128, B~249) |
| `Masks` param | `half_01_imposter_O`, **4064×4064**, RGB | BOUND; **R = sparse silhouette mask 7.2%**, B = 254 constant |
| frame textures | `Imposter_VEC` / `Imposter_PIV` | **1×1 placeholders** (pivot-painter wind, not the imposter frame lookup) |
| base-colour scalars | `Brightness` 1.8, `Saturation` 0.8, `Tint` (1,1,1), `ColorVariation` 0.01, `Specular` 0.2 | **nominal — base colour NOT zeroed** |
| snow | `Snow` static switch = **false**; `SnowBlending` 1.0 / `Snow Saturation` 0.0 (gated off by the switch) | snow path compiled out |
| mtimes | mesh, LOD mats, `MA_Imposter`, MI, all three atlases all 2026-08-14 21:46 | coherent, NOT stale (the 9/11 + 9/19 changes were other species) |
| LODs / cull | 5 LODs, imposter = slot 3; FoliageType cull 384–512 m | imposter draws ~200–512 m (so HLOD, at farther unloaded cells, was never the subject — confirms step-0b) |

## The graph paths (node names) — as the desk asked

**Base colour:** `Albedo` TextureSampleParameter2D → (UVs from the `ImposterUVs` material function
= octahedral frame lookup) → `SpeedTreeColorVariation` → `Desaturation` (Saturation 0.8) →
`Multiply` (× Brightness 1.8) → `Multiply` (× Tint white) → `LinearInterpolate` with the snow path
(gated off by the `Snow` switch) → Base Color. Graph tally: 9 Multiply, 2 LinearInterpolate,
2 Desaturation, 13 ScalarParameter, 8 MaterialFunctionCall (ImposterUVs, SpeedTreeColorVariation ×2,
FlattenNormal, FoliageZRotation, ObjectScale, SmoothThreshold, PN_AnimationShader).

**Opacity:** `Masks` TextureSampleParameter2D (→ half_01_imposter_O; the silhouette is in **R**) →
`SmoothThreshold` material function → Opacity Mask (clip 0.333).

## Ranked suspects for the desk's ruling (all are graph/asset-shape, not bindings)

1. **Atlas SIZE MISMATCH — Albedo 4096² vs Normal/Masks 4064².** `ImposterUVs` computes one UV per
   frame assuming a single frame-grid pitch; a 32 px atlas-size difference makes the Albedo sample
   drift progressively off each tree frame onto the dark green-brown INTER-FRAME fill, which then
   renders as a solid-ish dark card. This is the most likely single root and is concrete + fixable
   (re-export/re-bake the albedo at 4064², or all three at a matched size). Prime suspect.
2. **Opacity channel / registration.** The silhouette lives in `Masks.R` (7.2%); if `SmoothThreshold`
   reads a channel that is near-constant (e.g. the B=254 plane) the quad never clips and the whole
   card (including the dark fill) shows — the "solid box" look. Confirm which channel `SmoothThreshold`
   samples and that it registers against the 4064 vs 4096 albedo.
3. **MSM_TWO_SIDED_FOLIAGE shading** under the 35° Look sun on a camera-facing card with the baked
   normal — least likely (the normal atlas is valid), listed for completeness.

## What is NOT the cause (ruled out this step)

Bindings (all bound), missing/null atlas (all exist), stale bake (coherent 8/14 import), black albedo
(it is green), base-colour parameters (Brightness 1.8, Tint white, Snow off), HLOD / FlattenMaterial_VT
(cull is 384–512 m, imposter draws inside that), r.LumenScene.FarField, VT upload budget.

## Fence honoured

Read-only except the exported atlas views (evidence, in this dir). No FoliageType, mesh, material,
or atlas was modified. `pre-a2-fix` tag stands. Editor closed clean (0 procs).

---

## Step 2 render + the two 5-min checks (2026-09-25, follow-up)

**Check 1 — Albedo PowerOfTwoMode: CLEAN.** `half_01_imposter_A` `power_of_two_mode = NONE` (not
PadToPowerOfTwo). The 4096² is the genuine source size: it was imported from a SEPARATE source file
`half_01_imposter_A_unlit.jpg` (a JPEG, 4096²), whereas `_N.png` / `_O.jpg` are 4064². The source
files live on another machine (`C:/Users/Nils Arenz/Desktop/…`), so reimport-from-file is unavailable.
No pot fix exists.

**Check 2 — opacity channel: could not be read statically** (5.8 Python does not reflect
MaterialFunctionCall `function_inputs` nor the Material's `opacity_mask` input; a reverse-scan over the
reflected input pins found no reference, because the link is a function input). Resolved EMPIRICALLY by
the render below.

**Step-2 render — `foliage.ForceLOD 3` AND `4` at the slope station** (`slope_imp_lod3.png`,
`slope_imp_lod4.png`): the imposter LOD renders as **correct tree SILHOUETTES, not solid quads** —
opacity is working (Masks.R mask applies). The trees are green-ish but **noticeably DARKER and more
desaturated than the near full-geometry trees**. The earlier "solid dark boxes" at auto-LOD were dense
small dark imposters CLUSTERING at ~200–512 m, not a solid-quad opacity failure.

**Consequences for the fix:**
- Opacity is NOT broken (silhouettes, not solid) → no B→R re-wire needed.
- The albedo samples the RIGHT tree frames (silhouettes are tree-shaped, not dark-mud rectangles) →
  the 4096-vs-4064 size mismatch is NOT manifesting as off-frame sampling → **the matched-size re-bake
  is unlikely to fix the darkness** (same source materials, and the frames already sample correctly).
- The real symptom is **imposter BRIGHTNESS / shading**: a flat `MSM_TWO_SIDED_FOLIAGE` card with the
  baked dark-green albedo (mean 86/77/30 × Brightness 1.8) reads darker than 3D geometry under the 35°
  Look sun. "Lit like the near ones" fails on brightness, not on shape or opacity.

**Recommendation (desk to rule — this contradicts the standing re-bake premise, so reporting instead of
re-baking):** try the cheaper, more-targeted fix first — raise the imposter MI `Brightness` (currently
1.8) and/or review the `MA_Imposter` two-sided-foliage lighting/subsurface — on a `_SRC` copy, ForceLOD
4 at slope+vista, compare to the near trees. Re-bake only if a brightness/shading tweak cannot close the
gap. The size mismatch is real but cosmetic here; fold a matched-size re-bake into a future imposter
refresh, not this fix.
