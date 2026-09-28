# Biome recipe schema — v1 (revision 1.6)

A recipe is a single JSON file in `recipes/` that fully describes one biome.
Per CLAUDE.md hard rule 2, **every** scene parameter lives here; scripts read
recipes and contain no scene values of their own. Per hard rule 3, applying
the same recipe twice must produce the same scene — every object a recipe
creates is addressed by a deterministic name so re-runs update in place
rather than appending duplicates.

Scope of v1 is the first milestone: heightmap import → auto-material →
sky/fog/sun → capture. Foliage and PCG are reserved (see *Reserved* below).

## File conventions
- Filename: `recipes/<biome_id>.json`, lowercase, matching `biome_id`.
- Encoding UTF-8, 2-space indent.
- Units are explicit in the key name (`_cm`, `_m`, `_deg`, `_kelvin`). Unreal
  works in centimetres; any `_m` value is converted at read time, never
  pre-multiplied in the file.
- Unknown top-level keys are an error, not a warning — a typo'd key silently
  ignored would break rule 2 without anyone noticing.

## Top-level structure

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `schema_version` | int | yes | `1`. Scripts reject versions they don't know. |
| `biome_id` | string | yes | `^[a-z][a-z0-9_]*$`. Matches filename stem. |
| `display_name` | string | yes | Human label; used in log output. |
| `engine` | object | yes | Version gate — see below. |
| `heightmap` | object | yes | Source data + import geometry. |
| `landscape` | object | yes | Actor placement and scale. |
| `material` | object | yes | Slope/height blend definition. |
| `lighting` | object | yes | Sun, sky, fog, exposure. |
| `capture` | object | yes | Screenshot setup for the review loop. |

### `engine`
Guards version-specific API calls (audit criterion 4).

| Key | Type | Notes |
|-----|------|-------|
| `target_version` | string | e.g. `"5.8"`. Scripts compare against the live editor and abort on mismatch of the major.minor pair. |
| `on_version_mismatch` | enum | `"abort"` \| `"warn"`. Default `"abort"`. |

### `heightmap`
| Key | Type | Notes |
|-----|------|-------|
| `source` | string | Path **relative to repo root**, e.g. `terrain/alpine_2017.png`. Absolute paths and any `..` segment are rejected — conduct rule 1. |
| `format` | enum | `"png16"` \| `"raw16"`. 8-bit sources are rejected; they band visibly on slopes. |
| `resolution` | int | Pixels per side; must equal the file's actual dimensions, verified at import. |
| `section_size` | int | Quads per section: 7, 15, 31, 63, 127, or 255. |
| `sections_per_component` | int | **1 or 2** — the integer Unreal stores, not the dialog label. The New Landscape dialog shows "1×1 Section" / "2×2 Sections"; the stored value is the *linear* subsection count, so "2×2" is **2**. Engine authority: `FLandscapeConfig::NumSectionValues[2] = { 1, 2 }` (LandscapeConfigHelper.cpp:24), used linearly as `QuadsPerComponent = SectionsPerComponent * QuadsPerSection`. No other value is buildable. |
| `component_count` | int | Components per side. `resolution` must equal `section_size * sections_per_component * component_count + 1`; the script validates this and reports the nearest legal resolution on failure. |

### `landscape`
| Key | Type | Notes |
|-----|------|-------|
| `level_path` | string | **Required (v1.2).** Content-browser path of the level this biome lives in, e.g. `/Game/Alpine`. Must start with `/Game/`. Every editor-touching script gates on the *live* editor's current level matching this before it reads or mutates anything — see the level gate note below. |
| `actor_name` | string | Deterministic label used for idempotent re-import. |
| `location_cm` | [float, float, float] | World origin of the landscape actor. |
| `scale_xy_cm` | float | Centimetres per heightmap pixel. |
| `z_scale_cm` | float | World height represented by the full 16-bit range. |

### `material`
Slope/height blend. Layers are evaluated in array order; the first layer whose
ranges contain a sample wins, so order from most specific to most general.

| Key | Type | Notes |
|-----|------|-------|
| `parent_material` | string | Content-browser path, e.g. `/Game/Materials/M_AutoLandscape`. **Declared here, find-or-created by script.** Conduct rule 4 forbids direct on-disk `.uasset` edits; creation through `unreal.AssetTools` / `MaterialEditingLibrary` *is* the editor API and is permitted. Per hard rule 3 the script finds an existing asset before creating, so re-runs never duplicate. |
| `layers` | array | ≥1 layer object. |

Layer object:

| Key | Type | Notes |
|-----|------|-------|
| `name` | string | Landscape layer info name. The corresponding `ULandscapeLayerInfoObject` is **declared here and find-or-created by script**, same rule-4 reading and same idempotency requirement as `parent_material`. |
| `base_color` | [float, float, float] | **Required (v1.1).** Linear RGB, each 0–1. What the layer looks like. |
| `roughness` | float | **Required (v1.1).** 0–1. |
| `texture` | string | **Optional (v1.1; semantics fixed in v1.2).** Repo-relative source path, e.g. `textures/alpine_rock.png`, imported find-or-create exactly like `heightmap.source`. **Multiplies `base_color`; it does not override it** — see the texture datum below. Not a content-browser path: declaring the *source* keeps the zero-hand-work intent. |
| `slope_deg` | [float, float] | Inclusive min/max, 0–90. |
| `height_m` | [float, float] | Inclusive min/max in metres, **heightmap-zero-relative** — measured from heightmap value 0, i.e. the bottom of the height range, independent of actor placement. See the datum note below. |
| `blend_sharpness` | float | 0–1; 0 is a wide feather, 1 a hard edge. Width is **normative as of v1.2** — see the feather formula below. |
| `tiling_m` | float | **Detail** texture repeat distance in metres. Live as of v1.2 (was reserved). Inert on a layer with no `texture`. |
| `macro_tiling_m` | float | **Optional (v1.2).** *Macro* repeat distance in metres for a second sample of the same texture. Must exceed `tiling_m`. Omit for detail-only. See "Why two scales" below — without it, texture detail is invisible at kilometre viewing distances. |

#### v1.1 — layer appearance (normative, and the decisions behind it)
**Versioning:** v1.1 is a revision of v1, not a new schema version —
`schema_version` stays `1`. It tightens v1 retroactively: a recipe without
`base_color` and `roughness` on every layer is invalid as of this revision.
The only existing recipe (`alpine.json`) was updated in the same change, so
nothing conformant became non-conformant in practice.

Added because layers previously declared **where** they apply and never **what
they look like**. `name`, `slope_deg`, `height_m`, `blend_sharpness` and
`tiling_m` are all placement predicates; a material cannot output a surface
from placement alone, and hard rule 2 forbids a script inventing appearance.

**`base_color` + `roughness` are required; `texture` is an optional override.**
The schema was opened once, deliberately, so `texture` can be adopted later
without another version bump.

**`roughness` is required rather than defaulted** because snow versus rock is a
roughness distinction as much as an albedo one. Under a low, warm sun a uniform
0.5 makes snow read as matte plaster.

**`specular` and `metallic` are deliberately omitted — this is a decision, not
an oversight.** The engine default specular 0.5 corresponds to F0 ≈ 0.04, which
is physically plausible for every dielectric this biome contains (snow, rock,
soil, vegetation). Metallic is irrelevant to natural terrain. Unused keys are
schema debt, so they stay out until something needs them.

**Rejected: deriving colour from layer name via a table in the script.** That
is a hard rule 2 violation — base colour reaches the assembled scene directly,
so it is a scene parameter and belongs in the recipe. The source-authoring
ruling (`LESSONS.md`, 2026-07-28, "if a parameter shapes the source data
rather than the assembled scene, it belongs to the tool that authors the
source") does **not** shelter it, because appearance is assembled-scene data.
Recorded here so it is not re-proposed.

#### v1.2 — textures (normative)
**Versioning:** v1.2 is a revision of v1; `schema_version` stays `1`. It adds
`macro_tiling_m`, promotes `tiling_m` from reserved to live, fixes the meaning
of `texture`, and makes the feather width normative. No previously-valid
recipe becomes invalid: every added key is optional, and `texture` was
specced-but-unused, so its semantics had no dependants to break.

##### Texture datum (normative) — textures MULTIPLY, they do not replace
v1.1 said `texture` "overrides `base_color`". **That is superseded.** A layer's
final albedo is:

    final_albedo = base_color * 4 * detail_sample.rgb * macro_sample.rgb

Each texture is a **linear multiplicative variation map** authored so that its
per-channel mean is exactly **0.5**. Two samples multiplied and scaled by 4
therefore have mean `0.5 * 0.5 * 4 = 1.0`, which gives the property the whole
design rests on:

> **A layer whose texture has fully mipped out renders *exactly* its recipe
> `base_color`.**

Three consequences, all deliberate:
- **Hard rule 2 holds.** Colour stays in the recipe. Changing snow's colour is
  a one-line recipe edit with no asset regeneration. Had the texture carried
  the albedo, colour would have moved into a PNG — out of the recipe and out of
  review.
- **Degradation is graceful and provable.** As a scale fades with distance it
  approaches its mean, and its mean is a multiplicative identity. A fading
  texture cannot tint the terrain.
- **The mean is asserted, not assumed.** `scripts/make_layer_textures.py`
  refuses to write a PNG whose post-quantisation mean is off by more than
  4e-4. A mean of 0.48 would darken every surface using that layer by 8%, with
  nothing erroring and nothing visible in the texture itself.

**The `4` is an encoding constant of the texture format, not a scene
parameter** — the exact analogue of the heightmap's 32768 datum. It exists
because an unsigned 8-bit texture cannot store a multiplier centred on 1.0.

**sRGB must be OFF.** These bytes are linear multipliers, not colours. If the
importer leaves `srgb=True`, byte 128 decodes to 0.216 instead of 0.502 and
every textured layer darkens by ~57% — silently, with a clean compile.
`scripts/import_layer_textures.py` reads the flag back after setting it and
refuses rather than trusting that the set took.

##### Why two scales (`tiling_m` + `macro_tiling_m`)
`tiling_m` alone is **not sufficient**, and this is arithmetic, not taste. At
`alpine.json`'s cameras the nearest terrain is ~1.1 km and most of frame is
3–14 km. At 1920 px and 55° horizontal FOV, one pixel subtends 1.5 m at 3 km
and 7.2 m at 14 km. A 4 m repeat therefore spans **0.55–2.7 pixels** across the
wide shot: it mips to its mean and contributes nothing. A ~300 m repeat spans
41–200 px and reads clearly.

So `tiling_m` is the close-up scale (correct, and it will matter for foliage
and ground-level cameras), and `macro_tiling_m` is the one that survives to
the horizon. The validator requires `macro_tiling_m > tiling_m`, because
inverting them silently removes all visible variation — the failure would look
exactly like "textures didn't work".

Both scales sample the **same** texture asset, so adding the macro scale costs
no extra asset. Samplers use `SSM_Wrap_WorldGroupSettings` (shared samplers),
so doubling the sample count does not consume sampler slots.

##### Level gate (normative, v1.2) — conduct rule 7 checks the PROJECT, not the LEVEL
`landscape.level_path` exists because of a real incident on 2026-08-01. The
conduct rule 7 identity gate verifies that the connected editor's *project*
matches `UE_PROJECT_ROOT`. It passed — correctly. But the editor had an
unsaved `/Temp/Untitled_1` open (a New Level → Open World instance), not
`/Game/Alpine`, so every scene-facing script was reading and would have
written against **the wrong world inside the right project**.

The census made it obvious once looked at — actor packages read
`/Temp/Untitled_1_InstanceOf_/Engine/__ExternalActors__/Maps/Templates/
OpenWorld/…` — but nothing was *checking*, so the material build reported
success and only the exactly-one-label gate stopped the assignment. That gate
was never designed to catch this; it caught it by luck, because the stray
landscape happened to still carry the dialog's default name `Landscape`. Had
anyone renamed it, the material would have bound to the wrong terrain and
reported success.

So: **which world a recipe applies to is a scene parameter**, and under hard
rule 2 it belongs in the recipe. Scripts refuse rather than guess, and the
refusal names both paths so the fix is obvious.

##### Feather width (normative — closes audit finding R2)
`blend_sharpness` is 0–1 with no intrinsic unit. As of v1.2 its width is:

    slope feather (deg) = (1 - blend_sharpness) * 12
    height feather (m)  = (1 - blend_sharpness) * 0.06 * z_scale_m

So 1.0 is a hard edge and 0.0 is a 12° / 6%-of-vertical-range feather,
interpolating linearly between. Feathering is **outward**: the mask is 1
across the whole inclusive band and ramps to 0 outside it, so two layers
sharing a boundary (Snow/Grass at 1200 m) both read 1 at the boundary and
first-match-wins resolves it. An inward ramp would reach 0 *at* the threshold
and paint a seam of "no layer" along every shared edge.

These are defensible defaults, not physics: 12° is roughly the width over
which snow and rock interfinger on a real mountainside, and 6% of vertical
range is a plausible snowline transition band.

`scripts/make_layer_debug_material.py` must use these same constants. It
previously carried its own (10° / 5%), which meant the instrument disagreed
with the thing it was measuring — see `LESSONS.md`, 2026-08-01, R2.

#### Height datum (normative)
`height_m` is **heightmap-zero-relative**: measured from heightmap value 0 —
the bottom of the height range — independent of actor placement. A layer band
of `[1536, 2560]` against a `z_scale_cm` of 256000 means the top 40% of the
16-bit range, and means that regardless of where the landscape actor sits.

Material rules are a function of the terrain data, not of where the actor sits
in the world. Actor Z is presentation; recipe semantics are data.

**The trap this exists to avoid.** Unreal maps heightmap value **32768**
(mid-grey), not 0, to the landscape actor's Z — `LANDSCAPE_ZSCALE = 1/128`,
`LandscapeDataAccess.h:13`. So a landscape at actor Z 0 with `z_scale_cm`
256000 occupies world Z of −128000 to +128000 cm, and a recipe band of
`[1536, 2560]` is **not** world Z 153600–256000. Any script that samples in
world space must apply the offset:

    world_z_cm = actor_z_cm + (height_m * 100) - (z_scale_cm / 2)

Scripts that sample normalised heightmap values need no offset at all — which
is the point of choosing this datum.

### `lighting`
Every value here is scene-artist territory; none may be hardcoded in scripts.

| Key | Type | Notes |
|-----|------|-------|
| `sun.elevation_deg` | float | −90–90. Negative is below horizon. |
| `sun.azimuth_deg` | float | 0–360. |
| `sun.intensity_lux` | float | Directional light intensity. |
| `sun.temperature_kelvin` | float | 1700–12000. |
| `sun.light_shaft_bloom` | bool | |
| `sky.type` | enum | `"hdri"` \| `"physical"`. |
| `sky.hdri_path` | string | Required when `type` is `"hdri"`; content-browser path. |
| `sky.intensity` | float | Multiplier on the captured sky. 1.0 is physically neutral; higher exaggerates ambient fill. |
| `sky.color` | [float, float, float] | **Optional (v1.1).** Linear RGB tint on the sky light, each 0–1. Omit for no tint. A cool tint is how you get blue bounce into shadows: with a warm sun, neutral ambient leaves shadows grey and flat, because nothing in the scene supplies the sky's own colour to surfaces the sun cannot reach. |
| `fog.enabled` | bool | |
| `fog.density` | float | Exponential height fog density. |
| `fog.half_height_m` | float | **v1.4.** Metres over which fog density HALVES. Converted at apply time to the engine's raw `FogHeightFalloff` = `10 / half_height_m`, which `SceneCore.cpp:405` divides by 1000 — the old `height_falloff: 0.12` therefore meant an **83.3 m** half-height, a near-vertical wall of fog nobody chose. **The conversion is BASE 2** (`HeightFogCommon.ush` :225/:301/:394 use `pow(2.0f,·)`/`exp2`), with NO `ln(2)`; only that file's :206 *comment* says `exp`, and following the comment is what put a stray `ln(2)` in `apply_lighting.py` and `atmosphere_solve.py` from v1.4 until 2026-09-09 — authored half-heights rendered 1.4427× larger than written, and the 57.8 m quoted here was that same wrong formula. |
| `fog.height_datum_m` | float | **v1.4.** The fog actor's world Z in metres. Fog is densest AT this height and thins upward, so it decides which of a world is buried and which is clear. Before v1.4 nothing set it and the actor sat wherever it was first spawned (1920 m) while the terrain's p90 was 1610 m. |
| ~~`fog.height_falloff`~~ | — | **REMOVED in v1.4.** The validator refuses it by name: a recipe carrying it is one whose author believed something false about it. |
| `fog.start_distance_m` | float | |
| `fog.volumetric` | bool | Costs real frame time on the integrated GPU — see the environment note in CLAUDE.md. |
| `exposure.method` | enum | `"manual"` \| `"auto_histogram"`. Prefer `"manual"` so captures are comparable between runs. |
| `exposure.compensation_ev` | float | |
| `clouds` | object | **Optional (v1.5, Brief 2 Task 6, 2026-09-10).** One `VolumetricCloud` layer. Absent = no clouds, and `apply_lighting`'s census then expects ZERO cloud actors of ours. |
| `clouds.enabled` | bool | |
| `clouds.material_parent` | string | The engine cloud material the /Game child instances, e.g. `/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst`. Never written to. |
| `clouds.material_instance` | string | MUST live under `/Game/` (validator refuses otherwise): the coverage override lives on this child MIC because writing a parameter to the ENGINE MI would dirty engine content outside both roots (standing rule 1). Find-or-created by `apply_lighting`. |
| `clouds.coverage_param` | string | The scalar's name on the parent — `Cloud_GlobalCoverage` for the engine simple cloud, VERIFIED on the reflected surface 2026-09-10 (`cloud_mi_probe.py`), never assumed. |
| `clouds.coverage` | float | 0–1. |
| `clouds.layer_bottom_km` | float | **KILOMETRES** — the component's `layer_bottom_altitude` is km, not cm (read_cloud_state.py's verified reads). 0–20. |
| `clouds.layer_height_km` | float | **KILOMETRES**, 0.1–20. |

### `capture`
| Key | Type | Notes |
|-----|------|-------|
| `output_dir` | string | Repo-relative; must resolve inside `captures/`. |
| `resolution` | [int, int] | |
| `cameras` | array | Each: `name` (alphanumeric/`_`/`-` only — it becomes a filename), `location_cm` [3], `rotation_deg` **[pitch, yaw, roll]** in degrees (NOT `unreal.Rotator`'s positional order, which is roll-first; scripts must map by keyword), `fov_deg` (1–170). `fov_deg` is the camera's **horizontal** field of view (`UCameraComponent::FieldOfView`, CameraComponent.h:37); vertical FOV follows from the output aspect: `vfov = 2*atan(tan(fov/2)/aspect)` — 45° → 26.23° at 16:9. Composition arithmetic must use the vertical figure. Capture scripts must hand the CameraActor to the screenshot call (`take_high_res_screenshot(..., camera=)`) — moving the viewport alone copies location/rotation but NOT FOV. |

#### v1.5 — world targets, push tolerance, snowline jitter (normative)
**Versioning:** v1.5 is a revision of v1; `schema_version` stays `1`.
Every added key is optional, so no previously-valid recipe becomes
invalid.

##### `world` (optional top-level) — what the world is FOR
| Key | Type | Notes |
|-----|------|-------|
| `primary_movement_mode` | enum | `"walk"` \| `"mount"` \| `"climb"` \| `"air"`. **Required when `world` is present.** Must name a mode `terrain_erosion.MOVEMENT_PROFILES` reports; the generator refuses if the two disagree rather than silently skipping the check. |
| `min_crossable_frac` | float | 0–1. Minimum fraction of the map crossable in that mode. |
| `min_connected_frac` | float | 0–1. Minimum fraction of the crossable ground that must be in ONE connected region. |
| `max_border_flat_frac` | float | 0–1. Maximum fraction of the map BORDER allowed to be flat. **Required whenever `min_connected_frac` is set** — see below. |
| `flat_relief_m` | float | Optional. Relief threshold defining "flat"; defaults to `composition()`'s 20 m. |

**Why the connectivity target may not be declared alone.** A connectivity
measure is maximised by featurelessness: a billiard table is 100%
crossable in one piece. On 2026-08-02 this project's best-ever number —
`mount-in-one-piece 84.9%` — turned out to be substantially the dead
frame a radial mask had left around the terrain; the flat third of the
map *was* the largest connected rideable region. A recipe that sets
`min_connected_frac` without `max_border_flat_frac` is therefore
**rejected by the validator**, because it defines a target that the
worst possible terrain satisfies best.

`make_alpine_terrain.py` evaluates these after generating and **exits 3**
when any is missed. The heightmap is still written — it is real and
inspectable, and looking at the artefact is how the fault gets
understood — but it should not be pushed. An analysis that fails to run
is treated as a failure, not a pass: a gate that could not be evaluated
has proved nothing.

##### `heightmap.push_tolerance_units` (optional int ≥ 1)
Height-unit budget for `push_heightmap`'s read-back comparison. **May
only TIGHTEN the built-in value of 4; a larger number is refused and the
built-in is used, with a printed note.** Audit finding D1 was a
self-widening tolerance, and a recipe-settable budget with no ceiling
re-creates it with an extra step, because the recipe is edited by
whoever wants the push to succeed. Tightening can only turn a pass into
a refusal, so it is always safe.

Hard rule 2 does not bind this: Ryan ruled 2026-08-01 that verification
thresholds are properties of the measuring instrument, not of the scene.

##### `material.height_jitter_m` / `material.height_jitter_scale_m`
| Key | Type | Notes |
|-----|------|-------|
| `height_jitter_m` | float | 0–500. Amplitude, in metres, of a wander applied to the elevation the height bands are tested against. 0 or absent = the previous behaviour exactly. |
| `height_jitter_scale_m` | float | 10–20000. Approximate feature size of that wander. Default 600 m. |

A height band tested against a bare elevation yields a boundary that is a
perfect contour line, and a perfectly level snowline is among the
strongest procedural tells there is.

**Normative: the jitter is applied ONCE, to the elevation, not per
layer.** Snow's lower bound and Grass's upper bound are the same number;
perturbing them independently slides them apart and opens a seam that
first-match-wins fills with whichever layer is listed earlier. Applying
it to the shared input keeps every boundary locked together and makes
them wander as one.

The field is Gaussian-blurred white noise seeded from `biome_id` —
deliberately NOT the terrain generator's value noise, since sharing that
stream would let a future change to terrain synthesis silently move the
weightmap. Verified deterministic: two consecutive bakes are
byte-identical.

##### `material.displacement` — PER LAYER (v1.27, Brief 7 Phase 1)

Optional; strict when present. Nanite tessellation displacement, declared
in **metres** and converted once to the engine's unitless
`displacement_scaling.magnitude` by `make_landscape_material.displacement_spec`.

| Key | Type | Notes |
|-----|------|-------|
| `enabled` | bool | Required. `false` keeps the pre-displacement (three-pin) material path reachable; it may not be truthy-by-accident. |
| `center` | float | Required, 0–1. The height value that displaces by nothing; the graph re-centres every layer's height map onto it (`_centred_height`), so it stays a genuinely free choice and is kept 0.5 for a symmetric ±magnitude/2. |
| `per_layer` | object | Required. `{layer_name: metres}`, keyed **exactly** by the `material.layers` names — a missing layer would silently displace by zero, an extra key names a layer that does not exist. Each value in **[0.02, 2.0] m** (peak deviation either side of the undisplaced surface; below 0.02 m invisible, above 2.0 m it invents landforms and diverges render from collision). |

**Normative: the engine magnitude carries the LARGEST layer, and the
graph scales the others down.** `displacement_spec` sets
`displacement_scaling.magnitude` from `max(per_layer.values())`
(`amplitude_ref`); the payload multiplies each surfaced band's centred
height *deviation* by `amplitude_layer / amplitude_ref` before the
composite, so the engine's single `(v − Center) · Magnitude` reproduces
each layer's own peak amplitude exactly. A band with no height map
contributes `center` and is never scaled, so the degraded state stays the
identity. Proven on the CPU at import by `_assert_displacement_invariants`.

**RETIRED (v1.27):** the single global `material.displacement.amplitude_m`.
`_validate_displacement` refuses it with a migration message. It predated
the Brief 3 per-layer 16-bit height scans, which are what make per-layer
amplitude meaningful (crisp snow at 0.02 m, cliff mass at 0.20 m).

##### `material.height_blend` — height-weighted layer blend (v1.28, Brief 7 Phase 1 addendum)

Optional; strict when present. The effect of `LB_HeightBlend`, implemented
inside the weightmap composite because `M_Alpine8K` has no
`LandscapeLayerBlend` node.

| Key | Type | Notes |
|-----|------|-------|
| `k` | float | Required, 0–16. Height exponent. `0` disables the reweighting (identical to omitting the block). Above ~16 the blend is a hard height-ordered cut that stair-steps at boundaries. |
| `eps` | float | Required, (0, 1]. Added to the height before the power so a zero-height texel keeps a floor weight instead of vanishing, and so `(h+eps)**k` is strictly positive (the renormalisation's divide-by-zero guard rests on this). |

**What it does.** For each **stored** layer (Snow/Rock/Scree/ForestFloor —
the weightmap channels, not the remainder), the mask is scaled
`w_i' = w_i · (h_i + eps)^k` where `h_i` is that layer's **raw** height-map
sample in `[0,1]`, then the stored masks are renormalised to preserve their
sum. So the higher-elevation surface wins where two stored layers overlap,
and the meadow/Grass **remainder** (`1 − sum(stored)`) is unchanged —
`_cpu_height_blend` proves the sum is preserved, and `prove_gates` proves it
over the real baked weightmap.

**Normative: the height is RAW, not the displacement-centred value.** An even
power on a height re-centred on its own mean (which straddles 0) would fold a
texel far *below* its mean onto one far *above* — not a height blend. The
re-centring in `material.displacement` is a displacement-only transform and
must not feed `(h+eps)^k`.

**Reuse:** the per-layer height sample is created once and feeds the blend
weight, the sub-surface HeightLerp and the displacement chain — one texture
fetch, three consumers.

##### `material.weightmap_feather_sigma_px` — boundary feather (v1.29, Brief 7 Phase 1)

| Key | Type | Notes |
|-----|------|-------|
| `weightmap_feather_sigma_px` | float | **Required for the ≥4-layer (five-layer expand) stored contract when `material.weightmap` is set.** Gaussian sigma in **texels** applied to the four stored channels at bake, `(0, 8]`. `1.5` gives ~3 m cross-fades (1 texel = 1 m at this landscape). |

**What it does.** `derive_layer_weights.expand()` blurs each stored channel
(Snow/Rock/Scree/ForestFloor) by this sigma before quantising the composite
`weightmap` PNG, then renormalises so the per-texel stored sum stays `≤ 1`
(the meadow/Grass **shader remainder** `1 − sum(stored)` must stay `≥ 0`).

**Why it is required, not optional.** The un-feathered bake was NEAR-BINARY
(~83–98 % of texels pure 0/255 per channel), so two surfaces met along a
**hard 1 m mask edge** and the terrain shattered into ~1 m blocks under
minification (`research/brief7/p1_block_diff.md`, `feather_handoff.md`). An
**absent** field is that retired path, so `_validate_material` **refuses** a
`≥ 4`-layer recipe that declares a `weightmap` without this field rather than
silently running the old bake. The legacy 3-layer bake (`recipes/alpine.json`)
is **exempt** — it is produced by a different pipeline that reads no such field,
so requiring it there would be prose (rule 12). It is inert without a
`weightmap` and is refused there too.

**Not the same lever as `height_blend` or the mip filter.** `height_blend`
reweights by elevation; the SIMPLE_AVERAGE mip (`import_layer_textures.py`)
fixes distance aliasing of an already-soft mask. This feathers the FULL-RES
mask itself — the primary block cause. Invariant: `check_weightmap_feather.py`
(feathered ≥ 25 % at boundaries, Σ ≤ 255, and snow-line registration — hillshade
aspect PASS on the feathered snow + a bounded altitude drift; the skyline IoU is
the post-merge render acceptance).

**Versioning:** v1.29 is a revision of v1; `schema_version` stays `1`.

## Example — `recipes/alpine.json`

```json
{
  "schema_version": 1,
  "biome_id": "alpine",
  "display_name": "Alpine — golden hour ridgeline",
  "engine": { "target_version": "5.8", "on_version_mismatch": "abort" },
  "heightmap": {
    "source": "terrain/alpine_heightmap.png",
    "format": "png16",
    "resolution": 1009,
    "section_size": 63,
    "sections_per_component": 2,
    "component_count": 8
  },
  "landscape": {
    "actor_name": "Landscape_Alpine",
    "location_cm": [-403200.0, -403200.0, 0.0],
    "scale_xy_cm": 800.0,
    "z_scale_cm": 256000.0
  },
  "material": {
    "parent_material": "/Game/Materials/M_AutoLandscape",
    "layers": [
      { "name": "Snow",  "base_color": [0.86, 0.89, 0.94], "roughness": 0.3,
        "slope_deg": [0.0, 35.0], "height_m": [1536.0, 2560.0],
        "blend_sharpness": 0.25, "tiling_m": 4.0 },
      { "name": "Rock",  "base_color": [0.34, 0.32, 0.30], "roughness": 0.85,
        "slope_deg": [35.0, 90.0], "height_m": [0.0, 2560.0],
        "blend_sharpness": 0.7,  "tiling_m": 6.0 },
      { "name": "Grass", "base_color": [0.19, 0.28, 0.12], "roughness": 0.6,
        "slope_deg": [0.0, 35.0], "height_m": [0.0, 1536.0],
        "blend_sharpness": 0.5,  "tiling_m": 2.0 }
    ]
  },
  "lighting": {
    "sun": {
      "elevation_deg": 12.0, "azimuth_deg": 285.0,
      "intensity_lux": 5.0, "temperature_kelvin": 3200.0,
      "light_shaft_bloom": true
    },
    "sky": { "type": "physical", "intensity": 1.0 },
    "fog": {
      "enabled": true, "density": 0.02, "height_falloff": 0.12,
      "start_distance_m": 150.0, "volumetric": true
    },
    "exposure": { "method": "manual", "compensation_ev": -0.25 }
  },
  "capture": {
    "output_dir": "captures/alpine",
    "resolution": [1920, 1080],
    "cameras": [
      { "name": "ridge_wide", "location_cm": [-600000.0, -600000.0, 200000.0],
        "rotation_deg": [-7.0, 45.0, 0.0], "fov_deg": 70.0 },
      { "name": "snowline_detail",
        "location_cm": [-250000.0, -250000.0, 120000.0],
        "rotation_deg": [-14.0, 45.0, 0.0], "fov_deg": 45.0 }
    ]
  }
}
```

Note on the example: `63 * 2 * 8 + 1 = 1009`, which is why the heightmap is
1009px rather than a round 1024. Non-conforming resolutions force Unreal to
resample on import and the result stops being deterministic.

Corrected 2026-07-28: an earlier revision of this example (then sized
`component_count` 16, resolution 2017) derived its resolution as
`63 * 4 * 8 + 1`, using a `sections_per_component` of 4 that Unreal cannot
build. The arithmetic happened to reach the same 2017, which is why it
survived unexamined. See the `sections_per_component` row above for the
engine authority.

Updated 2026-07-31 (v1.1): example synced to the live `recipes/alpine.json`
so it demonstrates the required `base_color`/`roughness` appearance fields.
The previous example predated them and would have failed the v1.1 validator
it sits beside.

#### v1.6 — `foliage` (normative)
**Versioning:** v1.6 is a revision of v1; `schema_version` stays `1`.
`foliage` moves out of *Reserved* and becomes an optional top-level
block, strict when present. `water` followed in the Brief-4 carve
(2026-09-19 — see the WATER RECIPE section below). `pcg` and `weather`
stay reserved and are still rejected.

`foliage` is the fourth leg of the project's end state and the first one
whose placement is decided by **measurements that already exist**. It
declares WHERE things grow in the same vocabulary the material already
uses — layer weight, slope, height — plus the two erosion maps that have
been on disk and unused since 2026-08-02.

| Key | Type | Notes |
|-----|------|-------|
| `density_per_hectare` | float | 0–100000. Instances per hectare at weight 1.0, before every multiplier below. Expressed per hectare, not per square metre or per cell, because that is the unit a person can picture — 400/ha is open woodland, 4000/ha is dense scrub. |
| `seed` | int | Optional. Placement RNG. Defaults to the recipe's terrain seed so a biome is reproducible from one number. |
| `species` | array | One entry per plant type. Non-empty. |

Each `species` entry:

| Key | Type | Notes |
|-----|------|-------|
| `name` | string | `^[A-Za-z][A-Za-z0-9_]*$`, unique within the recipe. Becomes an asset and instance name, so it is charset-validated like `biome_id` and camera names. |
| `mesh` | string | Content-browser path (`/Game/...`). Declared here and **find-or-created by script**, same rule-2 reading as `parent_material`. |
| `layer` | string | Which material layer's BAKED WEIGHT drives density. Must name a layer in `material.layers`, and the generator refuses if it does not — a species keyed to a layer that does not exist would silently never place. |
| `weight_share` | float | 0–1. Fraction of this layer's density budget this species takes. Shares within one layer must sum to ≤ 1. |
| `slope_deg` | [float, float] | Inclusive. Nothing grows on a cliff; this is also how scree stays bare. |
| `height_m` | [float, float] | Inclusive, **heightmap-zero-relative**, the same datum as `material.layers[].height_m`. |
| `flow_bias` | float | −1–1. **v1.6, and the reason the erosion maps exist.** Positive concentrates instances where `terrain/alpine_flow.png` says water collects; negative pushes them onto dry ground. 0 ignores flow. |
| `scale_range` | [float, float] | Uniform random scale per instance, both > 0, min ≤ max. |
| `align_to_normal` | float | 0–1. 0 stands every instance vertical, 1 lays it flat to the slope. |

##### Normative: density is measured on the BAKE, not on the bands
A species' density comes from the **baked weightmap channel** for its
layer, not from re-evaluating `slope_deg`/`height_m` against the
heightmap. Those two are not the same number: the material feathers each
band outward by `(1 - blend_sharpness) * 0.06 * z_scale_m`, which is
115 m of height on this world, and the bake is what actually renders.
Re-deriving placement from the raw bands would put grass where the
render shows rock — the two instruments disagreeing about the same
decision, which §1.9 and §14.5 both exist to prevent.

The species' own `slope_deg` and `height_m` are an ADDITIONAL mask on
top, not a re-derivation: they express "this plant does not grow on a
40-degree face" independently of where the layer happens to be.

##### Normative: `foliage` cannot make a world non-traversable
Instance placement must not be allowed to close a route the world gate
just certified. `traversability()` measures the terrain, and terrain is
unchanged by foliage — but blocking collision on dense instances changes
what a player can cross in practice. Any implementation that gives
instances blocking collision must re-run the connectivity check against
the resulting mask and honour `world.min_connected_frac`, or it has
quietly invalidated the guarantee the generator prints.

#### v1.7 — `system`, and why grass is not foliage (normative)
**Versioning:** revision of v1; `schema_version` stays `1`.

A species now declares WHICH ENGINE MECHANISM places it. The two are not
interchangeable and the difference is economic, not stylistic.

| `system` | Mechanism | Cost |
|-----|-----|-----|
| `instanced` (default) | `InstancedFoliageActor`, transforms computed by `place_foliage.py` and saved into the level. | One stored transform per instance, plus OFPA package weight. Right for sparse large objects. Capped by `MAX_INSTANCES`. |
| `grass` | `LandscapeGrassType` driven from the landscape material's own weight mask; the engine spawns and discards instances on the GPU near the camera. | Stores nothing. Count bounded by view distance, not map area. |

This map is 6503 hectares. Ground cover at any believable density is
millions of instances, which on the documented hardware is not a slow
scene but a dead editor. `grass` is the only mechanism that reaches it.

Extra keys, `grass` only. Supplying them on an `instanced` species is a
validation error rather than an ignored field:

| Key | Type | Notes |
|-----|------|-------|
| `density_per_10m2` | float | Engine unit, passed through unchanged. NOT converted from `density_per_hectare`, and grass does NOT draw from the persistent-instance budget — nothing is stored, so there is nothing to cap. |
| `cull_distance_m` | float | End cull distance. Start cull is derived at 75% of it. |

`weight_share` is meaningless for `grass` and must be absent: there is no
shared instance budget to take a share of. `place_foliage.py` skips
`system: "grass"` entirely — iterating it raised `KeyError: 'weight_share'`,
which was the RIGHT failure. The wrong one would have been placing the
species twice, once per mechanism.

#### v1.8 — `surface` on a layer (normative)
**Versioning:** revision of v1; `schema_version` stays `1`.

| Key | Type | Notes |
|-----|------|-------|
| `surface` | string | Optional. Names a surface set in `Free/manifest.json`. When present, the layer's albedo, normal and roughness come from the imported photogrammetry maps and `base_color` becomes a **TINT** applied on top, not the colour itself. |

##### Normative: real albedo has no mean-0.5 datum
The synthetic layer textures this replaced were generated around a mean
of 0.5 and the material compensated with a gain of 4. A photographed
albedo map is already the surface's reflectance and needs no such
correction; applying one blows it out. When `surface` is present the gain
is dropped and `base_color` multiplies the sampled albedo. A layer with
`surface` and `base_color: [1,1,1]` therefore renders the material
exactly as photographed, which is the useful default.

`texture`, `tiling_m` and `macro_tiling_m` remain in force: the surface
set supplies the maps, the tiling keys supply the scale, and both a
detail and a macro sample are taken and averaged to break the repeat.

#### v1.9 — `foliage.nanite` (normative)
**Versioning:** revision of v1; `schema_version` stays `1`.

| Key | Type | Notes |
|-----|------|-------|
| `nanite` | bool | Optional, default **false**. Whether imported foliage meshes are built with Nanite. |

Set AT IMPORT TIME, never toggled on the asset afterwards: toggling
rebuilds the mesh a second time and leaves a window where the asset on
disk disagrees with the recipe. Default false because the foliage here is
alpha-masked, and Nanite's masked support in 5.8 costs the fast path; the
cheap, certain configuration is Nanite off with real LODs. `verify`
reports what LANDED, not what was asked for.

#### v1.10 — `varieties`, and the pivot contract (normative)
**Versioning:** revision of v1; `schema_version` stays `1`, like every
other v1.x revision. It was briefly set to `"1.10"` for traceability and
that was wrong — `_validate_recipe` requires exactly `1`, so the recipe
stopped validating. The version of the SCHEMA lives in this document; the
recipe's `schema_version` states which schema GENERATION it targets, and
those are different facts.

A `grass` species may drive several meshes. `LandscapeGrassType` holds a
LIST of `GrassVariety`, and the vendor sets are authored as size classes
for exactly that — `grass_medium_01` ships tiny/small/mid/tall/large,
spanning 0.048 m to 0.323 m. One mesh scaled across that whole span reads
as a stamped texture at any density worth having.

| Key | Type | Notes |
|-----|------|-------|
| `varieties` | array | Optional, `grass` only. Non-empty when present. |
| `varieties[].mesh` | string | Content-browser path. |
| `varieties[].share` | float | > 0, finite. A **WEIGHT, not a fraction.** |
| `varieties[].scale_range` | [float, float] | Optional; falls back to the species' own. |

##### Normative: shares are normalised, not required to sum to 1
`density_per_10m2` stays the species TOTAL and is split across varieties
in proportion to their shares, normalised by their own sum. Changing the
variety list therefore does not change how much ground cover there is.
Requiring the shares to sum to 1 would reject a list that rounds to 0.99
— a validation error about arithmetic rather than about intent. Every
share must be positive and finite; a list whose shares are all zero is
refused, because "place nothing" should be expressed by removing the
species.

`mesh` stays REQUIRED even when `varieties` is present, as the documented
fallback. A recipe that loses its variety list should thin, not break.

##### Normative: every instanced mesh must be pivot-normalised
This is the hard-won half of v1.10.

The vendor files lay their objects out SIDE BY SIDE in one scene, the way
a human wants to see a set. Imported directly, UE keeps the offset as the
StaticMesh pivot: `/Game/Meshes/fir_tree_01_c_LOD0` measured **12.406 m**
from its own geometry, and `grass_medium_01_large_a_LOD0` 2.394 m — on a
0.147 m mesh, a sixteen-fold displacement.

Nothing errors. The asset imports, binds its materials, and reports every
check green. What it does is displace every instance by that distance,
sweep the geometry around a circle of that radius under random yaw, and
lever anything using `align_to_normal` into or out of the ground. For
`grass` there is no correction available at any level: `GrassVariety` has
no pivot offset, so the density mask and the visible grass simply
disagree.

The contract:

1. `scripts/blender/normalize_asset.py` re-centres each object to the
   **base centre** — x and y at the bounding-box centre, z at the
   bounding-box MINIMUM — and exports one FBX per object, then re-reads
   each file from disk and verifies the pivot landed within 1 mm.
2. `import_static_mesh.py --normalized OBJECT` imports only from that
   output and REFUSES if the report does not name the object as verified.
   It does not fall back to the vendor file: "I could not check" is not
   "it is fine".
3. The importer reads `get_bounds()` back off the imported asset and
   FAILS if the pivot is more than 1 m from the geometry — a different
   instrument than the Blender check, measuring the same quantity after
   the FBX round-trip.

Base centre, not bounding-box centre in z: a plant is placed by where it
meets the ground, and a centred pivot buries half of it.

##### Normative: a published footprint is not a measurement
`grass_medium_01` carried a vendor extent of 7.3 m and `grass_medium_02`
3.6 m. Both are real numbers from the publisher's own listing, and both
describe the WHOLE SET arranged in a row for the product shot. The largest
single tuft is 0.327 m. Used as a footprint, 7.3 m is wrong by a factor of
22, in the direction that makes every derived scale invisible — which is
what happened: a `scale_range` of 0.05–0.11 against a 0.147 m mesh
produced grass 0.7 to 1.6 cm tall, and nothing anywhere reported a
problem.

So `vendor` does not outrank `measured`; it answers whatever question the
publisher was asking. Once `normalize_asset.py` has measured the object,
`measured` wins and the vendor value is DROPPED, not averaged with.
`Free/manifest.json` records which instrument produced every number in
`<field>_source`, and consumers that would behave differently for an
assumed value must branch on it.

#### v1.12 — `stamps`, terrain feature compositing (normative)
**Versioning:** revision of v1; `schema_version` stays `1`. `stamps` is a
new OPTIONAL top-level key (`import_heightmap.OPTIONAL_TOP`), strict when
present, so no previously-valid recipe becomes invalid.

**Gap noted, not filled:** this document jumps v1.11. `material.forest_floor`
is live in `alpine.json` and documented in `RECIPES.md` R2 as "schema
v1.11", but was never written up here. That is a pre-existing
documentation defect and is left for whoever authored it; inventing its
normative text now would be worse than the gap.

`terrain/stampit_catalogue.json` holds 52 maps all catalogued
`category: "STAMP"`. R1's catalogue spec defines a STAMP as a terrain
FEATURE that is **composited INTO a base heightmap before import, never
imported alone**. Before v1.12 there was no way to express that in a
recipe and no step that performed it. `scripts/composite_stamps.py` is
the step; `stamps` is how it is declared.

| Key | Type | Notes |
|---|---|---|
| `base` | string | Repo-relative. The ORIGINAL heightmap. Read every run; never written. |
| `output` | string | Repo-relative. The composited heightmap. Written every run. |
| `catalogue` | string | Repo-relative. The STAMP catalogue the hashes are resolved against. |
| `allow_edge_clip` | bool | Fail-closed gate. `false` refuses any placement whose footprint leaves the map. |
| `placements` | array | Non-empty. One entry per stamp application. |

Each `placements` entry — **every key is required**, except the two that
are mode-exclusive:

| Key | Type | Notes |
|---|---|---|
| `id` | string | `^[a-z][a-z0-9_]*$`, unique. Keys the per-stamp report. |
| `stamp_sha256` | string | 64 lowercase hex. **The catalogue key.** |
| `centre_m` | [float, float] | **WORLD metres**, same origin as `landscape.location_cm`. |
| `size_m` | float | > 0. The on-map side length the whole stamp spans. |
| `rotation_deg` | float | [0, 360). Counter-clockwise in the world XY plane. |
| `flip_x` / `flip_y` | bool | Mirror in stamp-local u / v before sampling. |
| `blend` | enum | `ADD` \| `MAX` \| `MIN` \| `MASKED`. |
| `amplitude_m` | float | > 0. Metres spanned by the stamp's full 0..1 value range. |
| `datum` | enum | **`ADD` only, required there, forbidden elsewhere.** `zero` \| `min` \| `mean` \| `median`. |
| `anchor_m` | float | **`MAX`/`MIN`/`MASKED` only, required there, forbidden on `ADD`.** The heightmap-zero-relative elevation stamp value 0 sits at. |
| `falloff` | float | (0, 1]. Fraction of the HALF-WIDTH over which the mask ramps 1 → 0. |
| `falloff_shape` | enum | `chebyshev` \| `euclidean`. |
| `opacity` | float | (0, 1]. Scales the whole mask. |

##### Normative: a stamp is a FULL FIELD, not a delta
All 52 catalogue entries report `relief_stats.min == 0` and
`max >= 65534`. A stamp value of 0 therefore means "the bottom of the
stamp's own range", **not** "no change". `amplitude_m` supplies the
vertical scale and `datum`/`anchor_m` supply the vertical pin. Neither
may be inferred: this is the same class as the heightmap's 32768 datum,
where a number arrived and meant something other than what was assumed.

##### Normative: every blend mode is applied through the mask
With `H` the base surface in metres (heightmap-zero-relative), `s` the
resampled stamp in 0..1, `m` the falloff mask:

    ADD     target = H + (s - D) * amplitude_m       D from `datum`
    MAX     target = max(H, anchor_m + s * amplitude_m)
    MIN     target = min(H, anchor_m + s * amplitude_m)
    MASKED  target =     anchor_m + s * amplitude_m

    H' = H + m * (target - H)          for EVERY mode

so at `m == 0` every mode is exactly the identity. A raw
`np.maximum(H, stamp)` cannot be feathered and leaves the rectangular
seam. `D` is measured over the pixels where `m > 0` — the only pixels
that contribute.

##### Normative: the falloff is smoothstep, and that is a correctness choice
    r    = max(|u|,|v|)  (chebyshev)   or   sqrt(u²+v²)  (euclidean)
    t    = clamp((1 - r) / falloff, 0, 1)
    m    = t·t·(3 - 2t) · opacity

A LINEAR ramp is C0 but not C1: its derivative jumps at `r = 1-falloff`
and at `r = 1`. Terrain shading reads the SLOPE, so a derivative
discontinuity draws a visible crease even though the height field is
continuous. Smoothstep's derivative is zero at both ends. Measured on the
alpine base: max |slope change| in the edge annulus is **0.410°** with the
smoothstep mask against **12.751°** for a hard-cut control, on a 16-bit
quantisation floor of 0.559°.

`chebyshev` keeps the whole square and feathers to its edge; `euclidean`
inscribes a circle and discards the corners (21.5% of area).

##### Normative: `base` ≠ `output`, and `output` ≠ `heightmap.source`
Both are enforced by the validator, not by the script. Compositing onto
the previous output accumulates stamps on every re-run **while reporting
success**, which is exactly what hard pipeline rule 3 forbids; making the
configuration unrepresentable is stronger than rejecting it at runtime
(CLAUDE.md non-negotiable 3). The second rule means adopting a stamped
map is always a deliberate recipe edit and never a side effect of running
the compositor — which matters because adopting one orphans 160,448
placed instances (see `RECIPES.md` R-STAMP).

##### Normative: no key has a default
Every knob above is required. A default living in `composite_stamps.py`
would be a scene parameter living in a script, which is the hard rule 2
violation the recipe system exists to prevent. `stamps.placements` must
be non-empty for the same reason `varieties[].share` may not be all-zero
(v1.10): "composite nothing" is expressed by removing the block, not by
an empty list that reports success and does nothing.

#### v1.16 — `stamps.detail_relief`, cliff-scale texture on every steep face (normative)
**Versioning:** revision of v1; `schema_version` stays `1`. New OPTIONAL
key inside `stamps`, strict when present. Every sub-key is REQUIRED.

A slope-masked ridged-noise pass applied **after every placement**.

##### Normative: this is a MEASURED need, not a preference
After the Pass 1 composition, on faces steeper than 45°:

    |laplacian| < 0.5 m   on 24.7% of steep faces
    |laplacian| < 1.0 m   on 45.2% of steep faces
    |laplacian| < 2.0 m   on 70.8% of steep faces

and the STAMPED surface was **smoother on steep ground than the base it
came from** — median |laplacian| **1.133 m** against **1.289 m**. Stamps
add large-scale SLOPE faster than they add fine RELIEF, so composing more
of them makes this worse, not better.

A steep face with no cell-scale relief renders as a **glossy featureless
wall**, and no material can rescue it: the landscape's normal is derived
from this height field. Fixing it in the material would be fixing the
symptom at the wrong layer.

| Key | Type | Notes |
|---|---|---|
| `amplitude_m` | float | `(0, 25]`. **Bounded on purpose** — this is DETAIL, not landform. An unbounded amplitude would let a "texture" pass silently rewrite the approved composition. |
| `wavelength_m` | float | `[4, 2000]`. Base octave. Below one cell (4 m here) it is aliasing, not relief. |
| `octaves` | int | `[1, 8]`. |
| `lacunarity` | float | `[1.1, 4.0]`. Frequency step per octave. |
| `gain` | float | `(0, 1)`. Amplitude step. `>= 1` makes each octave louder than the last and the sum diverges with octave count. |
| `slope_deg` | [lo, hi] | `0 <= lo < hi <= 90`. Where detail applies. |
| `slope_feather_deg` | float | `(0, 30]`. `0` would put a hard slope edge into the mask — the crease the smoothstep falloff exists to avoid. |
| `seed` | int | Deterministic. The seed is part of the RECIPE, not of the run. |

##### Normative: RIDGED noise, not smooth fbm
`1 − |noise|`, squared, summed over octaves. Ridged puts **crests** where
plain noise puts zero-crossings, which is what broken rock looks like.
Smooth fbm would turn a glossy wall into a *lumpy* glossy wall.

##### Normative: the mask is the slope of the FINISHED composition
Slope is computed once, from the post-placement surface, **before** the
detail is added. Two consequences, both deliberate:
- Detail lands on steep ground **no stamp reached** — which is most of
  the problem.
- The pass never re-derives its mask from its own output. Adding relief
  changes slope; a second derivation would feed the pass its own result.

##### Normative: the field is mean-centred
`field -= field.mean()` before scaling. A one-sided addition would lift
every steep face, raising the mean surface and **shifting the snowline** —
a scene change disguised as a texture change. The sidecar records
`net_mean_m` so the claim is checkable.

#### v1.15 — `falloff_jitter`, breaking the mask's own symmetry (normative)
**Versioning:** revision of v1; `schema_version` stays `1`. Two new keys
on every `stamps.placements` entry, **both required**, consistent with
v1.12's "no key has a default".

| Key | Type | Notes |
|---|---|---|
| `falloff_jitter` | float | `[0, 0.5]`. `0` is the exact geometric falloff and **must be stated**, never defaulted. |
| `falloff_jitter_scale` | float | `(0, 2]`. Noise wavelength in stamp-local units, where the stamp spans 2.0. Required even when jitter is 0, so the pair is always a complete description. |

##### Normative: why a geometric falloff is a defect at altitude
A `euclidean` falloff ends on a **perfect circle**; `chebyshev` ends on a
**square**. The height field is continuous across that contour — the
smoothstep guarantees it — and the shape is still legible at airship
altitude as a soft tonal ring, because **nothing in real terrain is a
circle**. Continuity is not sufficient; the *iso-contour's shape* is
itself an artefact.

##### Normative: the jitter is ONE-SIDED, and that is a safety property
    n01 = (value_noise(u, v, scale, seed) + 1) / 2      in [0, 1]
    r_j = r * (1 + falloff_jitter * n01)                >= r  ALWAYS

Because `r_j ≥ r`, `r_j ≥ 1` wherever `r ≥ 1`, so **the mask is exactly
zero on and outside the geometric footprint** and no seam can be created.
The zero-contour moves INWARD by a varying amount, which is what makes it
non-circular.

**A two-sided jitter is REJECTED.** It permits `r_j < 1` at the footprint
edge, leaving `mask > 0` against a hard cut — reintroducing the exact
seam the smoothstep falloff exists to prevent, as a side effect of fixing
a cosmetic problem. Verified by sampling dense rings at
`r = 1.0, 1.0001, 1.2, 1.5` over every jitter/scale combination: max mask
**1.5e-31**.

##### Normative: the noise is deterministic and smoothstep-faded
Seeded from `stamp_sha256` and `id` via `zlib.crc32`, never from the
clock or `np.random` global state — `composite_stamps` must be idempotent
(hard pipeline rule 3). The lattice fade is **smoothstep, not linear**:
linear interpolation's derivative jumps on every lattice line and would
draw a faint rectangular grid into the falloff, trading one geometric
fingerprint for a worse one.

##### The acceptance bar
Coefficient of variation of the outer contributing radius **≥ 0.05**. The
eight locked alpine placements measure **0.089 – 0.367**.
> ⚠ **NOT REPRODUCIBLE AS A NORMATIVE GATE (Pass 5, 2026-09-16, from
> LESSONS.md 2026-08-06).** That 0.089–0.367 band was hand-measured ONCE over
> eight placements and cannot be recovered: `measure_falloff_contours` reads
> **0.033–0.152** over nine, and the `≥ 0.05` bar was **never enforced** by any
> tool. Treat the bar as a RANKING baseline (higher CoV = less regular), not a
> pass/fail threshold; do not gate a build on it until it is re-derived on a
> reproducible instrument. Cite LESSONS.md 2026-08-06.

#### v1.13 — `palette`, the region's approved asset list (normative)
**Versioning:** revision of v1; `schema_version` stays `1`. `palette` is a
new OPTIONAL top-level key (`import_heightmap.OPTIONAL_TOP`), strict when
present, so no previously-valid recipe becomes invalid.

The region campaign needs one answer to "what may this region be built
from". Before v1.13 that answer lived nowhere, so every placement pass
would have re-derived it from vendor folder names.

##### Normative: the palette is GENERATED, and the split is the contract
Two files, and they may never merge:

| File | Holds | Never holds |
|---|---|---|
| `recipes/<biome>_palette_curation.json` | judgements: `id`, `path`, `role`, `pass`, `admit`, `note` | any measurement |
| `Free/_measured/fab_registry_*.json` | measurements, read with **zero assets loaded** | any judgement |

`scripts/make_alpine_palette.py` joins them and writes `palette` into the
recipe. **A curated `path` absent from every registry is a REFUSAL that
writes nothing** — not a warning, and not an entry with null
measurements. A palette entry whose triangle count was typed by hand is
exactly the derived record CLAUDE.md non-negotiable 15 forbids; here the
curation file *cannot express* a measurement, so the class is
unrepresentable rather than merely discouraged.

| Key | Type | Notes |
|---|---|---|
| `id` | string | `^[a-z][a-z0-9_]*$`, unique within the palette. |
| `path` | string | Must start `/Game/`. The engine asset, not a source file. |
| `role` | string | What it is FOR (`cliff_face`, `talus_field`, `understory`, …). Placement recipes select by role, never by vendor name. |
| `pass` | int | Which campaign pass places it. |
| `admit` | enum | `YES` \| `CONDITIONAL` \| `HAZARD`. |
| `measured` | object | Written by the generator from registry tags. Absent tags are listed in `measured.unmeasured`, never defaulted. |
| `verified` | bool | See below. |
| `verified_proof` | string | **Required when `verified` is true.** |
| `verified_reason` | string | **Required when `verified` is false.** |

##### Normative: `verified: true` must cite the render that proves it
The validator refuses `verified: true` with no `verified_proof`. The
campaign rule is that verified flags stay NO until render-proved, and a
bare `true` is a state claim written from narrative rather than checked
against the artefact. Requiring the proof PATH means the claim can always
be re-opened and re-checked (non-negotiable 9), and it means promotion
happens in the pass that renders the asset — **editing the flag is not a
way to promote an asset**, because the flag alone will not validate.

The validator does **not** check that the proof file exists on disk: it
runs during recipe load on machines where `_verify/` may be empty, and a
missing render is a finding for the pass that owns it, not a reason to
refuse a heightmap import. What is enforced is that *the claim carries its
citation*.

##### Normative: `admit` is not a quality score
- `YES` — passes the tier gate and the biome read.
- `CONDITIONAL` — passes the TIER gate; the BIOME read is unresolved and
  needs a render against the region's own surfaces first. This is the
  value for "the mesh is good and I do not yet know that it belongs here".
- `HAZARD` — usable, with a recorded cost or failure risk in `note`. The
  motivating case is `SM_GroundRevealRock001`, whose 8192×8192 texture
  reported a **4608.99 MB** first-build encode estimate against ~1.8 GB
  free and hung the editor for 20+ minutes.

##### Normative: absent registry tags are UNKNOWN, never a value
`NaniteEnabled` was requested on all 940 meshes across the three packs and
**came back on none of them**. The generator writes
`"nanite": "UNKNOWN — registry tag absent"` rather than `false`. A failed
measurement reports that it could not measure, never the number the broken
measurement produced (non-negotiable 6). **Absent is not OFF**, and Pass 3
must confirm Nanite in the editor before placing anything.

##### The tier gate, and the shape class that limits it
`tier_gate` records the metric that admitted or excluded each asset:
`triangles / bbox_area_m2`, computed from registry tags alone. It
discriminates **only within a shape class** — the bounding box of a fern
or a scree slab is mostly air, so planar and spanning assets are measured
and reported but never gated by it.

Measured 2026-08-03, and the reason DragonCave is excluded from alpine:

    KiteDemo  /Rocks/       n=12   median 299.5 tri/m2   range 105.8 .. 1490.0
    DragonCave SM_LargeRock n=7    median  14.5 tri/m2   range  10.7 ..   16.5
    DragonCave SM_CaveRock  n=4    median  21.9 tri/m2   range  20.1 ..   23.9

**The ranges do not overlap**: the sparsest KiteDemo rock is 105.8 and the
densest DragonCave rock is 23.9. That is an exclusion by measurement, not
by taste, and it is why `admit` needs no "quality" field — quality is the
gate, not an attribute.

## Reserved (not yet implemented)
`pcg`, `weather`. Scripts must reject these keys under
schema_version 1 rather than silently ignore them.

`foliage` was reserved until 2026-08-02 and is now live — see v1.6 above.
`water` was reserved until 2026-09-19 and is now live — see the WATER
RECIPE section below and the top-level `water` pointer block it defines.

---

## WATER RECIPE — `recipes/water.json` (schema `water-1.0`)

Added 2026-09-19 for the Brief-4 water carve (`research/brief4/CARVE_PLAN.md`
T2; `RULING.md` §7). Two pieces:

**1. The top-level `water` POINTER block, inside a landscape recipe.**
`water` graduated out of *Reserved* the same way `foliage` did in v1.6. It
is **not** inline water data — it names the water recipe FILE, exactly the
city.json precedent (`foliage.settlement_exclusion.from_city_plan` names a
plan file, and the margins live in that file, not duplicated). Validated by
`import_heightmap._validate_water`.

| key | type | required | meaning |
|---|---|---|---|
| `from_water_recipe` | str | yes | repo-relative path to the `water-1.0` recipe (`recipes/water.json`). The file must exist and load. |

Underscore-prefixed keys (`_what`, …) are tolerated as comments, as
elsewhere in the landscape recipe; any other key is an ERROR.

**2. The `recipes/water.json` body (schema `water-1.0`).** A different recipe
KIND, **not** loaded by `landscape_spec.load_recipe`. `_validate_water` loads
it and enforces the invariants below — so the town-safety ceiling and the
fall cap are **machine-readable, never prose** (rule 12). Geometry provenance
(levels/extents/route/notches) is `RULING.md` §7 + `hydro_amendment.json`,
REFERENCED not duplicated (NN19); the A/B inflow falls are DERIVED by
`research/brief4/scripts/water_derive.py` (footprints reproduce the hydro
areas exactly — positive control).

| key | type | required | meaning |
|---|---|---|---|
| `schema_version` | str | yes | `"water-1.0"` |
| `lakes` | array | yes, non-empty | one entry per carved lake |
| `waterfalls` | object | yes | the fall policy + cap |
| `north_cascade` | object | — | D→tarn ladder; `route_and_notches` REFERENCES `hydro_amendment.json` |
| `encodable_span_m` | [float,float] | — | the 16-bit 0–2560 m carve span |

Each `lakes[]` entry (enforced fields in **bold**):

| key | type | meaning |
|---|---|---|
| **`id`** | int, unique | hydro lake id (`level_slice` key) |
| **`name`** | str, non-empty | label |
| **`level_m`** | float | adopted water surface (RULING §7) |
| `closed` / `endorheic` | bool | endorheic = no outlet |
| `never_exceed_level_m` | float | **REQUIRED when `endorheic` is true**, and must be ≥ `level_m`. The town-safety ceiling (a raise past it floods committed buildings). |
| `area_ha`, `centroid_col_row`, `bbox_col_row`, `shoreline_km` | — | connected-component geometry (clip target — the bbox over-floods) |
| `inflow_fall` | object or null | derived fall draining INTO the lake, or `null` (measured none) |

`waterfalls` (enforced fields in **bold**): **`cap_min`**/**`cap_max`**
(ints, `0 < cap_min ≤ cap_max`), **`total_placed_falls`** (int, within the
cap), `by_construction` (the cascade lips), `by_coupling_inflow` (A/B).

**REFUSALS** (`_validate_water` / `_validate_water_recipe`): a `water` block
that is not a pointer to an existing loadable file; `schema_version` ≠
`water-1.0`; empty/`non-array `lakes`; a duplicate or non-int lake `id`; an
endorheic lake with no numeric `never_exceed_level_m` or one below its
`level_m`; a `cap` that is not `0 < min ≤ max`; a `total_placed_falls`
outside the cap. Each was exercised with a negative control at authoring.

## CHARACTER RECIPE — `recipes/character.json` (schema `character-1.0`)

Added 2026-08-15 for `PHASE2_PLAN.md` unit 5. **This is a different recipe
KIND from a landscape recipe and is NOT loaded by
`landscape_spec.load_recipe`.** Its validator is
`scripts/verify_walkable_profile.py`.

**No prose keys.** The recipe is data. Reasoning lives in `RECIPES.md`
→ R-CHARACTER; this section is the contract. R-ALPINE8K REJECTED already
ruled that a schema key holding prose is the "invent a key to get past the
validator" antipattern, and R-CHARACTER REJECTED records the run where a
documentation key tripped the recipe's own gate.

### Top level

| key | type | required | meaning |
|---|---|---|---|
| `schema_version` | str | yes | `"character-1.0"` |
| `character_id` | str | yes | stable id, e.g. `"player"` |
| `display_name` | str | yes | human label |
| `movement` | object | yes | see below |
| `capsule` | object | yes | see below |
| `navigation` | object | yes | see below |
| `assets` | object | yes | see below |

### `movement`

| key | type | meaning |
|---|---|---|
| `profile` | str | **A KEY into `terrain_erosion.MOVEMENT_PROFILES`, never an angle.** The walkable angle is derived at read time. |
| `max_walk_speed_cm_s` | float | `CharacterMovementComponent.cpp:694` |
| `max_step_height_cm` | float | `:689` |
| `jump_z_velocity_cm_s` | float | `:679` |
| `max_acceleration_cm_s2` | float | `:733` |
| `gravity_scale` | float | `:677` |

**REFUSAL:** any key under `movement` whose name contains `angle` or `slope`
is an ERROR, whatever its value. Ruling 19 makes the angle derived; a typed
one is a second copy that will drift.

### `capsule`

| key | type | meaning |
|---|---|---|
| `radius_cm` | float | `Character.cpp:78` `InitCapsuleSize(34.0f, 88.0f)` |
| `half_height_cm` | float | as above |

Verified against the **`Character` CDO's `capsule_component`**, never against
`CapsuleComponent`'s own CDO — that is the generic component default (22/44)
and is about a different object.

### `navigation`

| key | type | meaning |
|---|---|---|
| `agent_profile` | str | key into `MOVEMENT_PROFILES`; `AgentMaxSlope` derives from it |
| `agent_radius_cm` | float | navmesh agent radius |
| `agent_height_cm` | float | navmesh agent height; convention is `2 x capsule.half_height_cm` |

**REFUSAL (ruling 19):** the angle for `navigation.agent_profile` must be
**≤** the angle for the PAWN's `movement.profile` in the character recipe.
One-directional, not equality. Drift upward is silent and grants paths onto
ground the character slides off. **The comparand is the PAWN, not the world**
— comparing against `world.primary_movement_mode` was a MEASURED defect,
corrected 2026-08-26 (RECIPES.md:12715, :13221; LESSONS.md 2026-08-26): a
"walk" navmesh refused under a "mount" world left the town's outer third
unreachable. `world.primary_movement_mode` is a world-scale POI-spacing
declaration, not this gate's bar.

### `assets`

| key | type | meaning |
|---|---|---|
| `status` | str | `"not_migrated"` until the content is in `/Game/` |
| `source_root` | str | where it comes from |
| `skeletal_mesh` / `skeleton` / `physics_asset` / `anim_blueprint` | str | asset names, not paths, until migrated |

While `status` is `"not_migrated"` these are INTENT and nothing may resolve
them as `/Game/` paths.

#### v1.23 — `collision` on a species (normative)

**REQUIRED on every INSTANCED species — vegetation and rock alike.
REFUSED on a grass species.** There is no default.

| key | type | meaning |
|---|---|---|
| `enabled` | str | `"none"` or `"query_only"`. Nothing else is admitted. |
| `profile` | str | Collision profile name, e.g. `"BlockAll"`. **Required** when `enabled` is not `"none"`; **refused** when it is. |
| `navigable_geometry` | str | `"yes"` / `"no"` / `"dont_export"` / `"even_if_not_collidable"`. Always required. |
| `capsule` | object | **Optional.** A simple collision capsule this project AUTHORS onto a mesh it owns. |

`capsule` takes `radius_cm`, `z_min_cm`, `z_max_cm` and a non-empty
`basis` string. All four are required when the block is present.

##### Normative: why REQUIRED and not defaulted

Measured 2026-08-16 on the live project: **all fourteen `FT_*` foliage
types read `NoCollision`**, so nothing in either world collided except the
landscape — 219,659 trees and 13,515 rock instances were pass-through,
**including the three tree species whose MESHES carry a vendor-authored
trunk capsule.**

The cause was not a wrong value. It was silence: `place_foliage.py`
contained no occurrence of the word "collision" in any form, so
`UFoliageType`'s constructor default stood —
`InstancedFoliage.cpp:640` does
`BodyInstance.SetCollisionProfileName(NoCollision)` — and
`InstancedFoliage.cpp:1822` copies that onto the component
**unconditionally**, overriding whatever the mesh's own `BodySetup` says.

An optional field with a sensible default reproduces exactly that failure:
silent, invisible, and green on every asset-level check. A required field
cannot be forgotten. **Non-negotiable 3 — prefer an input that cannot
express the catastrophic value over a gate that rejects it.**

##### Normative: the mesh's profile is NOT the runtime profile

`Free/_measured/mesh_collision.json` reports `collision_profile` off the
**mesh's** `BodySetup.default_instance`, and every one of the six meshes
reads `BlockAll`. That number says nothing about whether anything collides,
because the foliage component's `BodyInstance` is overwritten from the
FOLIAGE TYPE at `:1822`. **Two different objects; only one is on the path
that decides whether a trace hits.** Read both, and never quote the mesh's
as the runtime answer.

##### Normative: `navigable_geometry` `"no"` does NOT mean "keep it out"

`EHasCustomNavigableGeometry` (`NavRelevantInterface.h`) reads:

- `No` — the custom export callback is **not** called, *but the default
  collision export still runs*.
- `Yes` — the custom callback **is** called. For an
  `InstancedStaticMeshComponent` that callback is
  `DoCustomNavigableGeometryExport` (`InstancedStaticMesh.cpp:5435-5438`),
  which exports **per-instance transforms** via
  `GetNavigationPerInstanceTransforms`. That is the path that makes 63,981
  tree instances into navmesh obstacles at all.
- `DontExport` — the value that actually excludes.

`Yes` is the engine default for foliage (`InstancedFoliage.cpp:868`) and is
correct for instanced trees. `PHASE2_PLAN.md` unit 6 prescribes
`CustomNavigableGeometry = No`, which is **backwards** — it reads as "keep
trees out of the navmesh" while in fact disabling the per-instance export.
Not applied; flagged for unit 8 to settle against a built navmesh.

##### Normative: the capsule is a SPAN, never a `length`

`KSphylElem.length` is documented as the **line segment only** — *"add
Radius to both ends to find total length"* (`SphylElem.h`, 5.8 stub
`:183555`). A recipe declaring `length` would read as a total height and be
short by one diameter, silently, in the one field nobody re-measures. So
the recipe declares the physical fact — the vertical span the shape
occupies — and the tool derives

    length   = (z_max_cm - z_min_cm) - 2 * radius_cm
    center_z = (z_min_cm + z_max_cm) / 2

refusing any span that does not exceed its own diameter. `length_cm` is a
**refused key**, with a probe in `prove_gates.py` holding that refusal.

##### Normative: measure a Nanite mesh from its SOURCE MODEL

Sizing an authored capsule reads the mesh's geometry, and on a Nanite mesh
the obvious accessors return the wrong mesh.
`ProceduralMeshLibrary.get_section_from_static_mesh` and GeometryScript's
`RENDER_DATA` LOD both return the **Nanite fallback proxy**. Measured on
`SM_PVE_Norway_Spruce_01_A`: the fallback overstates the mesh by **6.6% in
Z and ~36% in X**, and its low-Z vertices — 1 to 8 per 25 cm band — are far
too sparse to contain a trunk, yielding radii scattered 7–63 cm with no
cylinder in them.

`GeometryScript_AssetUtils.copy_mesh_from_static_mesh` with
`GeometryScriptLODType.SOURCE_MODEL` returned **76,343 vertices** and a
clean, consistent trunk. **`build_scale` was `[1,1,1]`, so the two
representations are different meshes, not the same mesh in different
units** — check that before assuming a conversion factor.

##### Normative: never author collision onto vendor content

`RECIPES.md`'s Fab-boundary rule names *"changing its LOD or collision"* on
a Fab static mesh as its worked example of an edit that vanishes on
re-download. A `capsule` is therefore legal only on a **repo-tracked**
mesh, and the applier refuses by `git check-ignore` rather than by
convention. Of the four tree meshes, only
`/Game/Meshes/Trees/SM_PVE_Norway_Spruce_01_A` is tracked — it is the one
this project exported itself, and the only one with no simple collision,
which is not a coincidence: an asset we generate has no vendor doing the
unglamorous parts.


---

## CITY RECIPE — `recipes/city.json` (schema `1.0-draft`)

Added 2026-08-26, discharging the debt `city.json` carried in its own
`_schema_status` since 2026-08-24. **A different recipe KIND from a landscape
recipe**; not loaded by `landscape_spec.load_recipe`. Read by
`scripts/plan_city.py`; consumed downstream by
`scripts/city_clear_foliage_payload.txt` and `scripts/plan_encounters.py`.

**⚠ PROSE KEYS — UNRESOLVED, SEE THE RULING NOTE AT THE END OF THIS SECTION.**

### Top level

| key | type | required | meaning |
|---|---|---|---|
| `schema_version` | str | yes | `"1.0-draft"` |
| `city_id` | str | yes | stable id; names the output `city/<id>_plan.json` |
| `display_name` | str | yes | human label |
| `biome` | str | yes | which world recipe the terrain comes from |
| `level_path` | str | yes | `/Game/...` target level |
| `site` | object | yes | where the town stands |
| `plan` | object | yes | the street/plot form |
| `buildings` | object | yes | footprint, height, pad limits |
| `roofs` | object | no | gables; omitted means flat-topped masses |
| `landmark` | object | no | one silhouette anchor |
| `foliage_clearing` | object | no | margins for the tree clear |
| `gates` | object | yes | refusals, all evaluated BEFORE the write |

### `site`

| key | type | meaning |
|---|---|---|
| `centre_world_cm` | [float, float] | measured by `find_city_site.py`, not chosen |
| `usable_radius_m` | float | largest inscribed circle under the slope bar |
| `context_radius_m` | float | surrounding area considered |
| `centre_elev_m` | float | measured |
| `region_area_ha` | float | measured |

### `plan`

| key | type | meaning |
|---|---|---|
| `core_radius_m` | float | inner ring radius |
| `extent_radius_m` | float | how far the town MAY reach; the pad gates decide the real edge |
| `ring_count` | int | **the real extent**: plots exist only between rings |
| `ring_spacing_m` | float | |
| `spoke_count` | int | radial streets |
| `candidates_per_plot` | int | placement attempts per plot |
| `street_width_m` | float | |
| `max_street_slope_deg` | float | **END-TO-END GRADE**, not roughness — see R-CITY REJECTED |
| `max_street_cut_fill_m` | float | max deviation of ground from the straight run |
| `street_join_tol_m` | float | centrelines within this are one network |
| `plaza_radius_m` | float | open centre; no buildings inside |

### `buildings`

| key | type | meaning |
|---|---|---|
| `footprint_m` | {min,max} | |
| `aspect_max` | float | |
| `height_m` | {centre,edge} | falls outward |
| `storey_m` | float | heights snap to this |
| `gap_min_m` | float | |
| `max_pad_cut_fill_m` | float | a pad needing more is REFUSED, never floated or buried |
| `max_pad_slope_deg` | float | |
| `seed` | int | the plan is deterministic on this |

### `roofs`

| key | type | meaning |
|---|---|---|
| `enabled` | bool | |
| `pitch_deg` | float | **FIXED AT 45 by the primitive.** One Cube rolled 45° gives a symmetric gable; any other roll gives an asymmetric shed. Arbitrary pitch needs two slabs per building and doubles the package count. |
| `eaves_overhang_m` | float | widens the gable, so it also RAISES the ridge: ridge = (width + 2·eaves)/2 |
| `gable_overhang_m` | float | projection past the gable ends |
| `mesh` | str | `/Engine/BasicShapes/Cube.Cube` — the Cube, not the Cone |

### `foliage_clearing`

| key | type | meaning |
|---|---|---|
| `building_margin_m` | float | |
| `street_margin_m` | float | |

**Tested as ORIENTED RECTANGLES per structure, never as a radius.** A radial
clear leaves a circular bald patch — the error the town boundary itself already
made once. Not expressible as a foliage-recipe parameter: re-running
`place_foliage` restores every tree and an exclusion mask re-rolls all 217,118
positions, so the clear is a re-runnable operation, idempotent by construction.

### `gates`

| key | type | meaning |
|---|---|---|
| `min_buildings` | int | below this it is a hamlet |
| `min_street_segments` | int | floor on the CONNECTED network, after pruning |
| `streets_are_one_network` | bool | ASSERTED by re-deriving the component count, not printed |
| `max_building_to_street_m` | float | whole-network gate: every building near the connected network |
| `max_orphan_building_fraction` | float | **PROVISIONAL — needs a ruling, see below** |

**Every gate runs BEFORE the write.** A refused run must leave the previous good
plan on disk; writing then exiting non-zero leaves the refused plan at exactly
the path the placer reads.

---

## ENCOUNTER RECIPE — `recipes/encounters.json` (schema `1.0-draft`)

Added 2026-08-26. Read by `scripts/plan_encounters.py`. `PHASE2_PLAN.md` unit 9.

### Top level

| key | type | required | meaning |
|---|---|---|---|
| `schema_version` | str | yes | `"1.0-draft"` |
| `region` | str | yes | names the output `encounters/<region>_all.json` |
| `level_path` | str | yes | |
| `seed` | int | yes | the plan is deterministic on this |
| `area` | object | yes | **scoped to navmesh coverage** — planning where the gate cannot measure is worse than not planning |
| `density` | object | yes | |
| `archetypes` | list | yes | |
| `exclusions` | object | yes | |
| `slope` | object | yes | |
| `reachable_sidecar` | str | yes | path to the MEASURED reachable region |
| `gates` | object | yes | |

### `density`

| key | type | meaning |
|---|---|---|
| `reference_elevation_m` | float | the basin floor |
| `base_per_km2` | float | density at the reference elevation |
| `per_100m_above_reference` | float | the foothill→peak gradient, `WORLD_VISION:305` |
| `max_per_km2` | float | clamp |

**The target is computed over AVAILABLE ground, not the area box** — outside the
settlement, outside the spawn-safe radius, connected to the player, near
measured reachable ground. Computing it over the box asks for encounters in
ground that does not exist for the purpose (non-negotiable 22).

### `archetypes[]`

| key | type | meaning |
|---|---|---|
| `name` | str | |
| `weight` | float | relative selection weight among eligible archetypes |
| `min_elevation_m` | float | eligibility floor |
| `aggro_radius_m` | float | |
| `leash_radius_m` | float | |
| `party_size` | [int, int] | inclusive range |

Required separation between two encounters is `aggro + leash` of the LARGER of
the pair, computed **per pair**. A single global radius cannot express that two
scavengers may sit closer than a scavenger and a highland beast.

### `exclusions`

| key | type | meaning |
|---|---|---|
| `settlement.from_city_plan` | str | the town is NOT re-described; it derives from the committed plan |
| `settlement.building_margin_m` | float | must exceed the largest aggro radius, or an encounter can aggro from inside the town |
| `settlement.street_margin_m` | float | |
| `player_start_safe_radius_m` | float | must exceed every leash radius |
| `max_distance_from_reachable_m` | float | proximity to ground MEASURED reachable |

### `gates`

| key | type | meaning |
|---|---|---|
| `min_fraction_of_target` | float | **RELATIVE, not a constant floor.** A constant is satisfied by lowering the constant; what can go wrong is exclusions or separation eating a plan |
| `min_encounters_floor` | int | backstop for a target that is itself near zero |
| `all_reachable_from_player_start` | bool | verified IN THE EDITOR against the BUILT navmesh |

**Reachability is not checkable in this planner and must not be faked here.**
The planner reads the heightmap; the navmesh is built from collision. The gate
is `scripts/city_encounter_verify_payload.txt`.

---

## ⚠ RULING NEEDED — PROSE KEYS IN THE CITY AND ENCOUNTER RECIPES

The CHARACTER RECIPE section above states the convention plainly: **"No prose
keys. The recipe is data."** It cites R-ALPINE8K REJECTED, which rules a schema
key holding prose to be the "invent a key to get past the validator"
antipattern, and R-CHARACTER REJECTED, which records a run where a documentation
key tripped the recipe's own gate.

`recipes/city.json` and `recipes/encounters.json` are the opposite: roughly half
their keys are `_why_…` / `_what_…` prose carrying the reasoning and the
measured evidence behind each value.

**This is a real inconsistency and it is NOT resolved here.** Both readings have
force:

- **Strip the prose** — consistent with the stated convention; the reasoning
  moves to `RECIPES.md` R-CITY, which is where the character recipe puts it.
  Cost: the evidence stops travelling with the value it justifies, which is
  exactly what made these recipes readable.
- **Bless the prose for PLANNER recipes** — they are not validated by
  `landscape_spec` and no gate can trip on them. The landscape schema already
  permits one prose field (`bounds_volumes[].basis`), so the convention is
  already not absolute.
- **A single `_notes` object per section**, keeping prose but confining it.

**Operator ruling needed. Nothing was changed.** Note the landscape validator
DOES refuse unknown keys — it rejected `_extension_note` in
`navigation.bounds_volumes[1]` on 2026-08-26 — so this question is only open for
recipes that validator does not read.
---

## RULED 2026-08-27 — PROSE KEYS ARE PERMITTED IN PLANNER RECIPES, UNDER A RULE

**Versioning:** v1.6 is a revision of v1; `schema_version` stays `1` for
landscape recipes. The planner recipes carry `schema_version: "1.1-planner"`,
which is a SEPARATE line from the landscape schema and always was — they are not
read by `landscape_spec` and never have been.

**Correcting the framing above before answering it:** the section says an
operator ruling is needed and lists three options *neutrally*. None was marked
recommended. The one the surrounding text actually argues for is the second, and
that is what is adopted — said plainly rather than pretending a recommendation
was already there.

### THE RULE

Prose keys are **permitted** in recipes that `landscape_spec` does not validate
— today `recipes/city.json` and `recipes/encounters.json` — subject to all
three of:

1. **Every prose key is prefixed `_`.** The prefix is the whole mechanism: it
   makes "is this data or commentary" answerable by a machine rather than by
   reading the key name and guessing.
2. **No code may READ a `_`-prefixed key** from these files. Prose that a
   consumer reads is not prose, it is an undeclared field, and the next person
   to reword it changes behaviour.
3. **A prose key may not be the only record of a decision.** It travels with the
   value; the DECISION lives in `RECIPES.md`. If the two disagree, `RECIPES.md`
   governs and the prose key is stale — the same ranking every derived record in
   this project gets.

### WHY THIS RATHER THAN STRIPPING IT

The character recipe's convention — *"no prose keys, the recipe is data"* — was
ruled for recipes the VALIDATOR reads, and it was ruled because a documentation
key tripped that recipe's own gate (R-CHARACTER REJECTED) and because inventing
a key to get past a validator is an antipattern (R-ALPINE8K REJECTED). **Neither
mechanism can occur here**: nothing validates these files, so no key can trip a
gate, and there is no validator to get past.

Against that, 46 of 117 keys in `city.json` and 19 of 48 in `encounters.json`
are `_why_…` / `_what_…` carrying the measured evidence behind each value.
Stripping them moves that evidence away from the number it justifies, and the
project's own experience is that a value separated from its reasoning gets
re-tuned by someone who never saw the reasoning.

**The convention was already not absolute** — the landscape schema itself
permits `bounds_volumes[].basis`, which is prose.

### ENFORCED, NOT STATED

Rule 25 says a claim worth making in a warning string is a claim worth
asserting, and a schema rule nothing checks is exactly that kind of claim.
`scripts/check_prose_keys.py` enforces 1 and 2 offline and is in the offline
suite:

- every non-underscore key must be consumed or declared; every `_`-prefixed key
  must be prose-shaped
- **no script may subscript one of these recipes with a `_`-prefixed literal**,
  which is the mechanical form of rule 2

**The landscape recipes are unaffected and still refuse unknown keys** — it
rejected `_extension_note` in `navigation.bounds_volumes[1]` on 2026-08-26, and
that refusal remains correct.

#### v1.17 — the planting-field contract (normative)
**Versioning:** revision of v1; `schema_version` stays `1`. This section
adds no new recipe KEY. It is the normative CONTRACT that separates the two
weight fields the foliage pipeline already computes, so that tree placement
can never be driven by a field its own output shaped. D-4
(`research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md:65`), implemented by
`scripts/derive_planting_field.py`.

##### The circularity this closes (the reason the contract exists)
The four tree species in `recipes/alpine_8k.json` (`Conifer`, `ConiferPine`,
`SpruceSub`, `SpruceSapling`) are keyed to material layer `Grass`. `Grass`
is the FIFTH of five layers, and a five-layer material stores only four
weightmap channels, so `Grass` is the SHADER REMAINDER —
`1 − (snow + rock + scree + forest_floor)` (`make_landscape_material.mask_plan(5)
→ (4, True)`; `derive_layer_weights.expand`, `scripts/derive_layer_weights.py:425`).

`place_foliage.load_inputs` samples that remainder from
`recipe.material.weightmap` = `textures/alpine_8k_weights.png`
(`scripts/place_foliage.py:366`, `:595-620`, `:683`) to decide where each
tree goes. But `forest_floor` in that weightmap **is canopy cover splatted
from the PLACED tree instances** (`scripts/derive_layer_weights.py:29-35`,
`:192`, `:215-235`). So a regeneration would place trees against a field the
previous placement moved: trees where trees already are → `forest_floor`
high → `Grass` remainder low → the field that decides the next placement has
been shaped by the last one. That is feedback, not suitability — the exact
defect §1.9/§14.5 forbid, one instrument's output feeding its own input.

##### The two fields, and the ONE-WAY dependency
| Field | Definition | Inputs | Who reads it |
|---|---|---|---|
| **PLANTING FIELD** | the layer weights with the canopy term forced to **zero**: `forest_floor ≡ 0`, so the tree layer (`Grass` remainder) = `1 − (snow + rock + scree)` | terrain only — height, slope, aspect (`slope_aspect`), and the Gaea `deposition` map (gravel term). **NO canopy term.** | **tree PLACEMENT** samples this |
| **RENDER WEIGHTMAP** | the same derivation with the real canopy cover: `forest_floor = canopy_cover(placed trees)`, and the `Grass` remainder shrinks to match | the planting field **plus** canopy cover computed from the placed instances | the **material / render only** |

The dependency is a chain, never a cycle:

    PLANTING FIELD ──▶ tree PLACEMENT ──▶ canopy cover ──▶ RENDER WEIGHTMAP

**The render weightmap is NEVER read back into placement.** Because the
planting field takes no canopy input, it cannot be moved by the trees it
decides — the loop is cut *structurally*, not by a convention a future
edit could quietly break.

##### Normative: the mask formulae come from ONE derivation; the remainder mapping is a CITED MIRROR pending dedup
`derive_planting_field.py` calls `derive_layer_weights.derive` twice —
`cover=0` for the planting field, `cover=canopy_cover(...)` for the render
weightmap — so the mask formulae and their thresholds are genuinely
single-sourced there (non-negotiable 24 holds for them). Every threshold
(`SNOW_BASE_M` from the recipe's Snow band, `ROCK_DEG`, `SCREE_DEG`,
`CANOPY_COVER_BAND = (0.15, 0.45)`, `GRAVEL_MAX_SLOPE_DEG`, the ±125 m
snow-line asymmetry) is the one already carried and cited in
`derive_layer_weights.py` (sec 3.4–3.6); **this contract invents none.**
The only new operation is forcing the canopy term to zero for the planting
field, which introduces no numeric constant.
⚠ **ONE duplication remains, stated honestly (desk review 2026-09-16):** the
REMAINDER mapping — which shader layer index is the tree-bearing `Grass`
remainder that placement samples — is a CITED MIRROR at
`derive_planting_field.py:91-107` of `place_foliage.py:611-620`, not a shared
import; a future edit to one could disagree with the other. Collapsing the two
into a single shared helper — and annotating both call sites with a mutual
cross-reference so a lone edit is caught — is deferred to the Brief-4 adoption,
together with N2 (a channel-name/order guard, not just a count check, at
`derive_planting_field.py:420-427`) and N3 (unifying the missing-deposition
policy: `derive_layer_weights.py:547` hard-fails where
`derive_planting_field.py:395-403` warns-and-records-ABSENT). This spec is the
record that the mirror exists, so the dedup is not forgotten at adoption.

##### Normative: a canopy that is silently absent REFUSES
If tree instances are declared but **none** land on the grid (wrong origin
or units), `canopy_cover` returns an all-zero field and the render
weightmap would equal the planting field — a split that reads as done but
never happened. `check_canopy` REFUSES that case (`n_declared > 0` while
`n_splatted == 0`), as it refuses a non-finite or out-of-`[0,1]` cover. A
failed measurement reports that it failed; it never reports the zero it
could not tell from a real reading (non-negotiable 6).

##### The rewire is GATED, and that is recorded, not decided here
Today `place_foliage` still samples the render weightmap. Pointing it at the
planting field regenerates the forest and is therefore **deferred to the
Brief-4 water carve** (X-1 / F-2); this contract and its selftest are built
and proven now so the rewire has a verified field to adopt. The persistence
question the rewire must answer — bake the planting field to its own PNG for
`place_foliage` to read, versus compute it inline — is left to that gated
step; it is an implementation choice, not an ambiguity in this spec.
