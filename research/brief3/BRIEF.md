# BRIEF 3 — Surface: what the ground is made of, where each thing goes, and when a repeat shows

Status: RESEARCH, written against `_verify/bench/2026-09-10/target_b2b/near_ground.png` (5200 K, target class), the vista pair, `hlod_ladder_vista.json`, and the census. Two tested tools in `scripts/` (`texel_budget.py`, `tiling_score.py`); the depth pass from Brief 2 is the third instrument. VERIFY marks as before.

Scope: the landscape material and its layers, layer weights, the ground textures, snow placement, forest floor, grass appearance, and the HLOD proxies' surface quality. Not in scope: tree density/PCG (Brief 5), water (Brief 4), the town's cubes (a content problem, not a surface one).

---

## 0. What the frames say (MEASURED / OBSERVED)

**0.1 Real surface ends at 256 m.** `hlod_ladder_vista.json`: real landscape and foliage resident to ~640 m by bounds-centre (the 256 m grid range plus actor extents), instanced proxies to ~742 m, merged proxies to ~1.5 km. The vista frame shows it: the snow slopes at left are 4,000-triangle proxies with a marbled 512² bake, standing in the *detail* band. Brief 1's ladder puts the hand-off to proxies at ~700 m (4K detail threshold); City Sample's HLOD0 loads to 768 m. Nothing in this brief is judged until the range matches the ladder — every surface metric below 256 m would be measuring a ring, not a world.

**0.2 The meadow does not visibly tile.** `tiling_score.py` on the sunlit meadow crop of near_ground: autocorrelation peaks 0.05–0.15 at every period from 12 to 150 px — no dominant repeat. Whatever the ground's defects are up close, tiling isn't the first one. (`texel_budget.py`'s CSF table says a 2 m tile is most detectable at 50–200 m, where the depth-binned score will be taken.)

**0.3 What the near ground is.** A single meadow layer under a spiky, uniform grass card, the same under the trees as in the open, with no wear, no litter, no stones, no colour variation between shade and sun beyond lighting. It reads as "green plane with grass on it." The snow line is a height band with no aspect term, so south-facing sunlit slopes hold as much snow as north-facing ones at the vista.

**0.4 The grey card says the sun is warm at the horizon**, R/G 1.26, B/G 0.74 at WB = 5200 K: the atmosphere reddens the sun past its source temperature at 12° elevation, as it should. That is a grade decision (§3.7), and it's made here because Brief 3's albedo targets are measured through it.

---

## 1. What the eye does with surfaces (LITERATURE)

**Texture masking and the CSF.** The eye's contrast sensitivity peaks at 3–5 cycles/degree and falls steeply above 20. Two consequences: fine texture (above ~20 cpd, i.e. sub-3-px detail at 4K) is invisible and only aliases; and a *repeat* whose angular period sits in 1–8 cpd is detected at contrasts as low as 0.5–1% — the visual system is a pattern detector first. A tile that is invisible at 3 m (period 0.02 cpd, far below the band) becomes a grid at 100 m (period ~1 cpd). Anti-tiling is therefore a *distance-band* problem, and the measurement must be taken by depth bin. (Campbell & Robson 1968; Barten 1999.)

**Texel density vs acuity.** At 4K/90°, the render gives ~2,445/d pixels per metre at distance d: 815 px/m at 3 m. A texture sampled below ~1 texel per pixel blurs; above ~2 it aliases into the mip chain. So the ground texture's texels per metre — the tile size for a given resolution — is derived from the nearest distance the player attends to, not chosen (§3.1). (Nyquist; Heckbert 1989 on texture filtering.)

**Albedo variation is what makes ground read as ground.** Natural surfaces have low-frequency albedo variation of 10–30% Michelson at metre scales (soil moisture, litter, wear) and spatially correlated hue shifts. A surface whose albedo is flat at that scale reads as painted, however good the normal map. Just-noticeable albedo difference for adjacent patches is ~2–3%; variation below that is wasted. (Motoyoshi et al. 2007 on surface-quality perception; standard field radiometry.)

**Slope, aspect and wear are read as evidence.** The eye infers *history* from surfaces: snow that stays on the shaded side, scree below the cliff, bare earth under trees, darker wet ground by water. When those correlations are present the terrain reads as a place; when snow sits evenly on both aspects it reads as a texture applied to a shape. This is not a photorealism detail; it is the cue set the brain uses to accept a landscape as having weather. (Gibson's ecological optics; every matte painter's checklist.)

**Height-blended layer edges.** A linear blend between grass and rock reads as a fade — nothing in nature fades. Blending by the layers' height maps (grass fills the low points between pebbles) produces the interpenetration the eye expects at every boundary. This is the single most recognisable difference between a 2010 terrain and a 2020 one, and it costs a few instructions.

**Shade must not be sky-coloured everywhere.** Under canopy the ground receives bounce from trunks and litter, not sky; forest floor is warmer and darker than open shade. That is a *layer* difference (albedo), not a lighting one — Brief 2 fixed the sky light; Brief 3 puts the right albedo under the trees.

---

## 2. What the engine and the census provide (VERIFY names)

| need | engine feature | reference |
|---|---|---|
| real surface to the detail band | WorldPartition runtime grid `loading_range`; HLOD0 Instancing layer range; approximate layer beyond | City: grid 256 m → HLOD0 to 768 m → HLOD1 (2 km cells) to 16 km |
| more than 3 layers | second weightmap / layer-info assets; `LandscapeLayerBlend` with `LB_HEIGHT_BLEND` per layer | ED landscape material: 21 expression types, 10 texture samples |
| layer masks from erosion | Gaea flow / wear / deposit / slope / curvature exports (`import_alpinelab_masks.py` already imports) | — |
| real scanned surfaces | Megascans/Fab surfaces are allowed in the mainline (the forge's refusal does not apply here); RVT for blending decals | Valley, Dark Ruins |
| anti-tiling | macro variation map (exists), hex/stochastic tiling function (engine `MF_HexagonalTiling`-style material functions; VERIFY availability in 5.8 content), per-layer rotation by world position | Valley |
| displacement | Nanite tessellation with real height maps (exists; amplitude re-centred per texture) | Dark Ruins |
| snow by aspect | world-normal dot sun/north in the material or a baked aspect mask from the heightmap | — |
| grass | `grass.GrassMap.UseRuntimeGeneration=1` (Titan) for weightmap-driven grass; per-instance colour variation via `PerInstanceRandom` | Titan, ED |
| proxy surface quality | HLOD material settings `TEXTURE_SIZING_TYPE_AUTOMATIC_FROM_MESH_DRAW_DISTANCE`; roughness 1, specular 0 on proxies; geometric-tolerance simplification | City |
| distance fade | normal/roughness fade to flat beyond ~1.5 km (material distance blend) | Valley (distance field settings), standard |

---

## 3. Derived numbers and rulings

**3.1 Texel density and tile size (DERIVED, `texel_budget.py`).** At 4K/90° with the player attending ~3 m ahead: 815 texels/m needed. Tile size = texture / 815: **4096 → 5.0 m, 2048 → 2.5 m**. The recipe's `tiling_m` per layer is written from this rule with its texture resolution, never typed. Macro variation tiles at 20–50× the base tile.

**3.2 Repeat visibility (DERIVED, `texel_budget.py` + `tiling_score.py`).** For a 5 m tile the repeat enters the CSF-sensitive band at 100–250 m (1–2.5 cpd) where the threshold is ~0.6–1.2% Michelson. Acceptance per depth bin: the periodic component's Michelson contrast measured by `tiling_score.py` at the bin's expected on-screen period is below the CSF threshold for that period. Below 30 m the threshold is ~10% — a repeat there is not seen and need not be fought.

**3.3 Loading range (RULING, precondition).** Runtime grid `loading_range` from 256 m to **768 m** (City's HLOD0 range; between Brief 1's 4K detail threshold of ~700 m and a power-of-two cell multiple), with the Instancing HLOD0 layer covering 768 m → 2 km and the approximate layer beyond, as the two-level design from the census. Memory and streaming cost are measured in E3's standalone instrument before and after; if the 768 m range fails the frame budget at any zone, 512 m is the fallback and the ladder's detail threshold moves with it.

**3.4 Layer set (design).** Eight layers, two weightmaps: **meadow, forest_floor, rock, scree, wet_shore, snow, dirt_path (existing), gravel**. Weights derived, in order of precedence: snow (height *and* aspect *and* slope, §3.5) > rock (slope > 32°) > scree (flow-accumulation proxy: 20–32° and within 60 m downhill of >40°) > forest_floor (canopy mask from the foliage instance density, §3.6) > wet_shore (within 4 m above water level; Brief 4 supplies the level) > gravel (Gaea deposit mask) > meadow (remainder). Each derivation is a script over the heightmap + masks, written into the weightmap sidecar; nothing painted.

**3.5 Snow by aspect (DERIVED).** Snow weight = smoothstep(height band) × smoothstep(slope < 35°) × (0.5 + 0.5 · cos(aspect − north)) shaped so a north-facing slope holds snow ~250 m lower than a south-facing one at the recipe's sun azimuth (the number from alpine snow-line asymmetry, ~200–300 m between aspects at mid-latitudes). Measured: snow fraction by aspect octant from the depth+normal pass at vista must show the asymmetry.

**3.6 Forest floor (DERIVED).** Canopy mask = foliage instance density (from the placement JSON) blurred by each species' crown radius; forest_floor weight = smoothstep(density above 0.3 crowns/m²). Albedo: litter/needle scan, ~30% darker and warmer than meadow. Measured: forest_floor weight under the near_ground trees > 0.8, in the open < 0.1.

**3.7 White balance (RULING).** WB is set so the grey card reads neutral: iterate `white_temp` (and `white_tint` for the green axis) at most twice from the card's R/G and B/G ratios — the correction is `T_new = T · (B/G)/(R/G)`-shaped, one step gets within 3%. Warmth is then an explicit grade offset stated in the recipe (`grade.warmth_bias_k`, default 0 for the bench; a look value later). The card is the instrument; albedo targets in §4 are measured after this.

**3.8 Grass appearance.** Density stays (Brief 5); appearance changes: per-instance hue/brightness variation ±8% via `PerInstanceRandom`, card base colour sampled from the underlying layer's albedo (ground-colour matching, so grass and meadow are one surface), taller cards only where meadow weight > 0.7. Measured: the meadow band's albedo variation (std/mean of low-passed luma at 1–4 m scale) rises from ~0 to 10–20%.

**3.9 Proxies (sourced).** Texture sizing → automatic from draw distance; simplification → geometric tolerance 0.25 m; roughness 1 / specular 0 on the generated material; bake capture resolution 2048. Rebuild via the batched builder. Measured: the depth-binned contrast in the 300 m–1 km bin, versus `fog_budget`'s prediction, should sit within ±30% (the proxies carry the terrain's own contrast, not a flat bake).

---

## 4. Measurements (acceptance)

All on the bench, target class, after the loading range is applied:

- **range**: residency at near_ground shows real landscape/foliage to ≥ 700 m by bounds-centre; standalone frame budget holds at every zone.
- **tiling**: `tiling_score.py` per depth bin (30–100, 100–300 m) below the CSF threshold for the bin's expected period.
- **albedo variation**: meadow band low-pass luma std/mean 0.10–0.20 at 1–4 m scale (from the near_ground frame, ground mask from depth+normal).
- **forest floor**: weight > 0.8 under canopy, < 0.1 in the open (from the weightmap sidecar and a pixel check on the frame under the near_ground trees: shade luma/chroma differs from open shade).
- **snow asymmetry**: vista snow fraction north-octant − south-octant ≥ 0.2 at the same height band.
- **height blend**: layer boundaries show interpenetration — measured as edge sharpness of the meadow/rock transition (gradient magnitude histogram) versus the linear-blend baseline; must rise.
- **card**: R/G and B/G within 0.97–1.03 after WB; warmth bias 0 on the bench.
- **proxies**: 300 m–1 km depth-bin contrast within ±30% of predicted.
- **dolly**: score not above baseline by > 10% (tile-wise tool when delivered; otherwise keep frames).

---

## 5. Experiments, in order

0. **Loading range 768 m + HLOD0 range to 2 km** (one variable). Residency read back; standalone perf at all zones; vista and near_ground recaptured. This is the precondition and the biggest visible change.
1. **Grey-card WB** to neutral, warmth bias 0. Recapture near_ground.
2. **Layer set + derived weights** (§3.4–3.6) — offline scripts first (weightmap sidecars with derivations), then import; height-blend on. Recapture all three; forest floor, snow asymmetry, height-blend metrics.
3. **Scanned surfaces** at the derived tile sizes (§3.1), displacement re-centred, macro variation and stochastic tiling on. Recapture; tiling by depth bin; albedo variation.
4. **Grass appearance** (§3.8). Recapture near_ground + dolly.
5. **Proxy rebuild** with the sourced settings (§3.9). Recapture vista; depth-bin contrast.
6. Send-back.

---

## 6. Sources

- Campbell & Robson (1968); Barten (1999) — CSF, as in Brief 1.
- Heckbert, P. (1989). *Fundamentals of Texture Mapping and Image Warping.* UC Berkeley. (Texel density and filtering.)
- Motoyoshi, I., Nishida, S., Sharan, L., Adelson, E.H. (2007). Image statistics and the perception of surface qualities. *Nature* 447.
- Gibson, J.J. (1979). *The Ecological Approach to Visual Perception.* (Surfaces as evidence of history.)
- Census: `ElectricDreams__ElectricDreams_PCG.json` (landscape material graph), `CitySample__Small_City_LVL.json` (HLOD layer settings), sample inis (Titan runtime grass maps).
- Engine source to VERIFY: `RuntimePartition.cpp:27` (loading range), `LandscapeLayerBlend` blend types, HLOD material `TextureSizingType`, `MaterialExpressionPerInstanceRandom`, hex-tiling material functions in 5.8 engine content.
