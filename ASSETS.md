# ASSETS.md — the intake register

Every asset entering the project gets a row here **before** it is
imported. Governed by **R-ASSET** in `RECIPES.md`.

**`verified in engine` flips to YES only after a spawn + RENDER.** Not
after a successful import, not after a settings read-back. The grass
imported successfully and was invisible for two sessions.

**Columns.** `asset` — the `/Game/...` path or vendor object name.
`source` — vendor, product, version/date. `licence` — the actual licence
terms, not "free". `role` — what names it. `coherence` — verdict against
the WORLD_VISION photoreal lane. `verified in engine` — YES only with a
render, and name the frame.

---

## Static meshes

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `/Game/Meshes/fir_tree_01_c_LOD0` | **UNRECORDED** — predates R-ASSET | **UNRECORDED** | `recipes/alpine.json` foliage species `Conifer` | not assessed | YES — `_verify/20260803-0039_alpine_ground-player-eye.png`, but see BACKLOG: renders as a bare spindly pole, not a fir |
| `/Game/Meshes/fir_tree_01_b*` | **UNRECORDED** | **UNRECORDED** | unused | not assessed | NO |
| `/Game/Meshes/grass_medium_01_tiny_a_LOD0` | **UNRECORDED** | **UNRECORDED** | `GT_alpine_Meadow` variety, 66.0 /10 m² | not assessed | YES — same frame |
| `/Game/Meshes/grass_medium_01_tall_a_LOD0` | **UNRECORDED** | **UNRECORDED** | `GT_alpine_Meadow` variety, 30.0 /10 m² | not assessed | YES — same frame |
| `/Game/Meshes/grass_medium_01_small_a_LOD0` | **UNRECORDED** | **UNRECORDED** | `GT_alpine_Meadow` variety, 14.4 /10 m² | not assessed | YES — same frame |
| `/Game/Meshes/grass_medium_01_mid_b_LOD0` | **UNRECORDED** | **UNRECORDED** | `GT_alpine_Meadow` variety, 9.6 /10 m² | not assessed | YES — same frame |
| `grass_medium_02`, `leafy_grass` | **UNRECORDED** | **UNRECORDED** | unused — BACKLOG candidate | not assessed | NO |
| `/Game/Scratch/ForgeWoodStack/SM_WoodStack_Forge` | **GENERATED** -- TRELLIS (MIT) from 4 operator concept references (`refs/wood_stack_refs/{wood_stack_az000.png,wood_stack_az035.png,wood_stack_az090.png,wood_stack_az180.png}`), seed 20260830 | TRELLIS **MIT**; the references are the operator's own. All 4 cleared `ai_input_guard.py --strict` BEFORE the weights loaded (R-AIGATE) | generated from operator concept references | 15000 tris (prop_small ceiling 15000), watertight True, **genus 392 -- topological noise NOT removed**, UVs: smart_project (MACHINE unwrap, greybox-grade) | YES — 120.0 cm top vs a 120.0 cm target (error 0.0 cm), footprint [158.4, 97.8] cm, orientation gate PASSED, 14996 tris in engine — `forge_lineup.png`, `woodstack_closeup.png`. `woodstack_beside_kit.png` is SUPERSEDED (buried-roof chalet) |
| `/Game/Scratch/ForgeCrystalSpire/SM_CrystalSpire_Forge` | **GENERATED** -- TRELLIS (MIT) from 3 operator concept references (`refs/crystal_spire_refs/{crystal_az000.jpg,crystal_az045.jpg,crystal_az090.jpg}`), seed 20260901 | TRELLIS **MIT**; the references are the operator's own. All 3 cleared `ai_input_guard.py --strict` BEFORE the weights loaded (R-AIGATE) | generated from operator concept reference | 60000 tris (hero_prop ceiling 60000), watertight True, **genus 11 -- topological noise NOT removed**, UVs: smart_project (MACHINE unwrap, greybox-grade) | NO -- stage 10 not yet run in a verified editor |

## Surface sets

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `T_Snow006_C/_N/_R` | **UNRECORDED** | **UNRECORDED** | `alpine.json` layer `Snow` | not assessed | YES — alpine captures |
| `T_Rock051_C/_N/_R` | **UNRECORDED** | **UNRECORDED** | ~~layer `Rock`~~ **REPLACED 2026-09-13** | not assessed | **NO — unbound** |
| `T_Ground037_C/_N/_R` | **UNRECORDED** | **UNRECORDED** | layer `Grass` | not assessed | YES |
| `Rock026`, `Rock063` | **UNRECORDED** | **UNRECORDED** | unused | not assessed | NO |

### 2026-09-12 intake — eight ground scans, TWO pass the height gate

**RULED 2026-09-12.** Every row was measured before anything bound:
height-map bit depth from the file header (PNG IHDR / JPEG SOF precision
byte), physical size from the vendor's own metadata, never assumed.
Probe artefact: `_verify/intake/2026-09-12/scan_probe.json`.

**⛔ THE GATE IS 16-BIT HEIGHT, and six of eight fail it.** The layer
blend is a HEIGHT blend — it picks a winner per texel by comparing two
surfaces' heights — so the height map is the blend's INPUT, not
decoration. Megascans ships Displacement and Bump as **JPEG**, and JPEG
is 8-bit: over a few centimetres of relief that quantises to ~0.4 mm
steps and the blend edge becomes a staircase of ties. R-LAYERS' mushy
fraction (0.2131 against a linear 0.5551) was measured on a blend with
real height to work with.

**Nothing here is CC BY, so `CREDITS.md` is UNCHANGED.** ambientCG is
CC0 (no attribution required, no conditions); Megascans via Fab is Fab
Standard (UE projects only, no attribution clause). Neither creates a
credit debt. Stated explicitly because a silent no-change is
indistinguishable from a forgotten one.

| asset | source | licence | stated size | height | status |
|---|---|---|---|---|---|
| `Gravel021_4K-PNG` | ambientCG | **CC0** | **NOT STATED** — absent from the mtlx, tres and usdc it ships | Displacement 4096² **16-bit PNG** | **ACCEPTED, NOT BOUND** — passes the gate; the material has no `scree` layer to bind it to |
| `Snow007A_4K-PNG` | ambientCG | **CC0** | **NOT STATED** — same | Displacement 4096² **16-bit PNG** | **BOUND** → layer `Snow`, replacing Snow006 |
| `rock_shopk_high` | Megascans via Fab, id `shopk` | Fab Standard — UE only | 1x1 (scan area of an OBJECT) | Displacement 4096² **8-bit JPEG** | **REFUSED** — 8-bit height; and it is a **`3d` asset** (ships `Rock_shopk_High.fbx`), a scanned rock MESH, not a tiling surface |
| `rock_shopk_raw` | Megascans via Fab, id `shopk` | Fab Standard — UE only | 1x1 | Bump 8K **8-bit JPEG** | **SOURCE TIER, registered, on disk, NOT BOUND** by ruling — and would have been refused anyway |
| `forest_floor_vktfeilaw_4k` | Megascans via Fab, id `vktfeilaw` | Fab Standard — UE only | **2x2 m** | Displacement 4096² **8-bit JPEG** | **REFUSED** — 8-bit height. Needle-litter candidate A |
| `nordic_forest_ground_root_moss_coarse_xiekec0_4k` | Megascans via Fab, id `xiekec0` | Fab Standard — UE only | **2x2 m** | Displacement 4096² **8-bit JPEG** | **REFUSED** — 8-bit height. Needle-litter candidate B |
| `wild_grass_xbreagf_4k` | Megascans via Fab, id `xbreagf` | Fab Standard — UE only | **2x2 m** | Displacement 4096² **8-bit JPEG** | **REFUSED** — 8-bit height. **NOT a duplicate**: the WildGrass already intaken is `sfknaeoa`, a different asset |
| `nordic_beach_rocky_ground_ukoncdamw_high` | Megascans via Fab, id `ukoncdamw` | Fab Standard — UE only | 1x1 | Displacement 4096² **8-bit JPEG** | **REFUSED** — 8-bit height; also a **`3d` asset**, not a surface. Was to be ALTERNATE scree only |

**THE NEEDLE-LITTER BAKE-OFF DID NOT HAPPEN.** Both candidates failed the
gate, so there was nothing to compare and nothing to bind. Neither is
recorded as ALTERNATE with numbers beside it, because neither produced
numbers.

**NO STAND-IN WAS SUBSTITUTED.** Rock keeps `Rock051` and Grass keeps
`WildGrass (sfknaeoa)` — the bindings they already had. That is the world
left unchanged, not a replacement chosen.

**⚠ THE TWO FAB-PLUGIN SURFACES ARE NOT ON THIS MACHINE.** The ruling
expected two Megascans surfaces added through the plugin rather than
downloaded. `Content/Fab/Megascans/Surfaces` holds nine surfaces, **all
dated 2026-08-10**, and none carries a ruled id (`Forest_Floor_sfjmafua`
and `Wild_Grass_sfknaeoa` are different assets from `vktfeilaw` and
`xbreagf`). Nothing under `Content/`, the plugin caches, or the user
profile was modified on 2026-09-12. So no id appears both as a zip and in
`Content/Fab/`, the dual-source rule never fires, and there is no tier to
report for a plugin pull that did not happen.

**⚠ ambientCG STATES NO PHYSICAL SIZE.** It is absent from the `.mtlx`,
`.tres` and `.usdc` the pack ships (`heightmap_scale = 1.0` in the tres
is a Godot import parameter, not a size). The derived tile does not
depend on it — `texel_budget` derives from RESOLUTION and viewing
distance — but the scale-fidelity check does: without it there is no way
to say whether the surface is being stretched or squashed relative to the
real thing it was photographed from. Recorded as a gap.

**⛔ CLOSED SAME DAY, AT THE VENDOR.** ambientCG's own API returns
`dimensionX = dimensionY = dimensionZ = 0` for these assets
(`/api/v2/full_json?id=Rock016&include=dimensionsData`), and the asset
page states no size either. So the gap is not this pack's packaging —
**the vendor holds no physical dimension for these surfaces at all**, and
no amount of re-downloading will produce one. The stretch column is
permanently `--` for ambientCG, and that is a measured property of the
source, not an omission of ours.

### 2026-09-12 intake, second batch — three scans, ONE is bindable

Sourced by Ryan against the shortfall list from the first batch. Probe
`_verify/intake/2026-09-12/scan_probe_2.json`, tiles `…/scan_tiles_2.json`,
surface stats `…/scan_stats_2.json`.

**ALL THREE PASS THE HEIGHT GATE** — ambientCG ships 16-bit PNG
displacement, which is exactly why the first batch's Megascans JPEGs
were refused. The gate is not what stops them now.

| asset | source | licence | height | derived tile | status |
|---|---|---|---|---|---|
| `Rock016_4K-PNG` | ambientCG | **CC0** | Displacement 4096² **16-bit PNG** | 5.03 m | **ACCEPTED, NOT BOUND — albedo ruling needed.** Linear luma **0.0712**, against `Rock051` (bound) at **0.1805**: binding it would darken the rock layer **2.5×** |
| `PineNeedles001_4K-PNG` | ambientCG | **CC0** | Displacement 4096² **16-bit PNG** | 5.03 m | **REFUSED — NOT A SURFACE.** 96.7% of texels are transparent: a cutout decal, not a tiling ground layer |
| `Ground037_4K-PNG` | ambientCG | **CC0** | Displacement 4096² **16-bit PNG** | 5.03 m | **DUPLICATE — already on disk since 2026-08-10.** All 11 files SHA-256 identical; nothing was overwritten |

**`PineNeedles001` PASSED THE GATE AND IS STILL NOT A LAYER.** It ships
an Opacity map and no ambient occlusion — the packaging signature of an
overlay — and the measurement confirms it: opaque fraction **0.033**. A
ground layer must cover the texel it is asked to cover. Its linear luma
of 0.0171 is not a surface albedo either; it is mostly the black under
the alpha. **Recorded, not corrected, and no stand-in substituted** —
needle litter still has no bindable scan, and the forest-floor layer it
would bind to still does not exist.

**THE DERIVED TILE IS 5.03 m FOR ALL THREE — BY DERIVATION, NOT BY
DEFAULT.** Tile size is per layer (RULED), and the per-layer derivation
returns the same number here because all three are 4096² and the
judgement camera and near distance are shared. Same figure, different
provenance: it was derived three times, not applied once.

**CREDITS.md UNCHANGED**, stated rather than left silent: all three are
ambientCG CC0, which requires no attribution and carries no conditions.

### 2026-09-12 — SELF-SOURCED, GATED AT DOWNLOAD TIME (R-FETCH)

**RULED BY RYAN 2026-09-12:** the agent sources its own materials,
because picking packs by eye kept landing on ones that are subtly wrong.
`scripts/fetch_surface.py` fetches from **Poly Haven** and **ambientCG**
(both CC0, both open APIs) and **promotes to `Free/` only on a pass** —
a refusal stays in `Free/_staging/` beside a `REFUSED.json`.

**Fab is NOT automatable, and it is not a permissions problem.**
`Bridge`, `Fab` and `MegascansPlugin` ship **zero Python**; they are C++
around an authenticated embedded browser. Recorded so it is not reopened.

**⭐ POLY HAVEN PUBLISHES PHYSICAL SIZE, SO STRETCH IS COMPUTABLE THERE.**
This is the capability ambientCG structurally cannot give us.

**SEVEN FETCHED, SEVEN PASSED.** All Poly Haven, all CC0, all 4096²
16-bit PNG displacement, all five required maps, all fully covering, all
normals confirmed **DX** and honest to their filenames. Artefacts:
`_verify/intake/2026-09-12/scan_probe_ph.json`, `…_tiles_ph.json`,
`…_stats_ph.json`.

| asset | layer it serves | stated size | albedo (linear) | stretch @5.03 m | status |
|---|---|---|---|---|---|
| `gray_rocks_4k` | **rock** | 1.80 m | **0.1795** | 2.79× | **matches bound `Rock051` (0.1805) to 0.6%** — and has a licence |
| `forest_floor_4k` | **forest_floor** | 2.14 m | 0.2760 | 2.35× | gap FILLED — no layer yet |
| `rocks_ground_04_4k` | **scree** | 2.00 m | 0.2228 | 2.51× | gap FILLED — no layer yet |
| `gravel_ground_01_4k` | **gravel** | 3.00 m | 0.2495 | 1.68× | gap FILLED — no layer yet |
| `river_small_rocks_4k` | **wet_shore** | 2.90 m | 0.1634 | 1.73× | gap FILLED — no layer yet |
| `rocky_trail_4k` | **dirt_path** | 2.00 m | 0.2375 | 2.51× | gap FILLED — no layer yet |
| `snow_02_4k` | snow (alternate) | 2.00 m | 0.3797 | 2.51× | **NOT an upgrade** — bound `Snow007A` is 0.8357; this is far darker |

**⭐ EVERY ONE OF THE EIGHT PLANNED LAYERS NOW HAS A MEASURED, GATED, CC0
CANDIDATE ON DISK.** The shortfall list is closed on the ASSET side. What
remains is not an asset problem and never was: the material carries
THREE layers, so `forest_floor`, `scree`, `gravel`, `wet_shore` and
`dirt_path` have nothing to bind to. That is a weightmap-channel and
graph change, and a ruling.

**⚠ `Rock051` HAS NO RECORDED SOURCE OR LICENCE** (this file, row 37:
UNRECORDED / UNRECORDED). `gray_rocks` reproduces its albedo to within
0.6%, is CC0 with a named author, and publishes its physical size. The
rock layer can therefore gain a licence without changing its appearance
— which makes this a different decision from the `Rock016` one, where
binding meant accepting a 2.5× darkening.

> **DONE 2026-09-13.** `Rock051` is RETIRED and its row closed
> **REPLACED / source unrecorded**; the `Rock` layer now binds
> `gray_rocks` (Poly Haven, CC0, Dimitrios Savva, 4K, 16-bit
> Displacement, NormalDX, all five maps). Measured albedo 0.1795 against
> the retired 0.1805 — **0.6% apart, so the layer's tonal contribution
> is preserved and what changed is that the asset now has a provenance.**
> `tiling_m` for the layer moves 5.03 → **1.80 m**, the scan's own
> `stated_size_m`: 5.03 is the texel-budget CEILING, and tiling there
> would have stretched a 1.8 m scan by the 2.79× this file already
> recorded. Tighter tiling costs no sharpness — 4096/1.8 = 2276
> texels/m against the 814.9 required.
>
> The textures remain on disk and are not deleted: an unbound asset with
> no licence is a liability only if it SHIPS, and `CREDITS.md` tracks
> what ships. Nothing else in the recipe references it.

**STRETCH IS COMPUTABLE FOR THE FIRST TIME**, on all seven rows. A 1.8 m
scan tiled at the derived 5.03 m renders everything 2.79× life size.
Recorded, not corrected — the tile is derived from the camera, and
choosing between honest scale and visible repeat is a ruling, not a
default. Note the spread: `gravel_ground_01` at 3.0 m stretches only
1.68×, so the larger-format scans are the cheaper ones to tile honestly.

### 2026-09-12 — THE CUPBOARD, MEASURED BEFORE THE SHOPPING LIST

Before sourcing anything new, the ambientCG packs already on disk since
2026-08-10 were measured for the first time. Artefact:
`_verify/intake/2026-09-12/scan_stats_ondisk.json`. All pass the 16-bit
height gate and all are fully covering.

| asset | linear luma | note |
|---|---|---|
| `Rock063_4K-PNG` | **0.2067** | **IN the granite band, beside the bound `Rock051` (0.1805).** A candidate the shortfall list never knew it had |
| `Rock026_4K-PNG` | 0.3839 | too bright for granite |
| `Snow006_4K-PNG` | 0.5796 | the layer `Snow007A` (0.8357) replaced — the replacement is the brighter and more snow-like of the two, confirmed after the fact |

**THE GRANITE GAP MAY NOT BE AN ASSET GAP.** `Rock016` (0.0712) was
sourced to fill it; `Rock063` was already here and sits 2.9× closer to
the bound specimen. The ruling is now a CHOICE between two in-band rocks,
not a decision to accept a 2.5× darkening. **Step (a) is a search, not a
recall** — and that applies to the asset shelf, not only to `scripts/`.

### 2026-09-12 — NINE FAB SURFACES ALREADY IMPORTED, THREE MAP TO UNBOUND LAYERS

`LandscapeLab/Content/Fab/Megascans/Surfaces`, all dated 2026-08-10:

    Forest_Floor_sfjmafua        _H present   -> forest_floor
    Dirt_Ground_xdhhdgq          _H present   -> dirt_path
    Soil_Mud_pjuph20             _H present   -> wet_shore
    Dry_Fallen_Leaves_vetladiaw  ⛔ NO _H      -> REFUSED on absence
    Wild_Grass_sfknaeoa          bound        -> meadow
    Clover / Cut_Grass / Lush_Grass / Uncut_Grass -- grass variants

**`Dry_Fallen_Leaves` REFUSED WITHOUT THE EDITOR**: it ships B, N and ORM
only. No height map is the same refusal as an 8-bit one, and it was the
best-named needle-litter candidate on the machine.

**⚠ THE OTHER THREE ARE UNDECIDED, AND THE FILE SIZE CANNOT DECIDE THEM.**
They are `.uasset`; a compressed 7 MB `_H` is consistent with either
depth. The source depth is readable only through the engine
(`blueprint_get_texture_source_disk_and_memory_size` over pixel count —
4 bytes/px is BGRA8, 8 is 16-bit RGBA). **No tool exists for this yet.**
Until it is measured, forest_floor, dirt_path and wet_shore have
CANDIDATES, not assets — and whether anything needs downloading at all
turns on that one measurement.

**⚠ THE SHORTFALL LIST IS NOT CLOSED.** Of the three gaps the first
batch left — a tiling granite surface, a needle-litter surface, and a
scree layer to bind `Gravel021` to — this batch supplies one candidate
(`Rock016`, pending an albedo ruling), fails one (`PineNeedles001`), and
does not touch the third, which was never an asset problem.


## Materials (authored, not imported)

| asset | authored by | role |
|---|---|---|
| `/Game/Materials/M_AutoLandscape` | `scripts/make_landscape_material.py` | landscape auto-material, 97 expressions |
| `/Game/Meshes/Materials/M_fir_bark` | `scripts/make_foliage_material.py` | fir slots 0, 2, 3 |
| `/Game/Meshes/Materials/M_fir_twig` | `scripts/make_foliage_material.py` | fir slot 1 (canopy) |

---

## INTAKE BATCH 1 — 2026-08-03

`verified in engine` is **NO** for every row below: nothing here has been
spawn-tested and render-proved yet. Format/scale facts marked *measured*
were measured this session; everything else is unverified.

### Pipeline inputs (never engine assets)

| asset | source | licence | format | tier | category | verified |
|---|---|---|---|---|---|---|
| 50 external heightmaps | GameDevGary, *50 Free .PNG Heightmaps for Unreal Engine* (itch.io) | **CC0** | *measured:* `I;16` 16-bit single channel, no alpha, 50/50 R11-conforming | 505 / 1009 / 2017 / 4033 / 8129 px — **all already UE-legal N+1, 50/50, no crop** | **TERRAIN** | n/a — pipeline input. Catalogued: `terrain/external_heightmaps/catalogue.json` |
| 52 terrain stamps | *Ultimate StampIT Collection for UE* (Fab) | Fab Standard — UE projects only | *measured:* `I;16`, no alpha, 52/52 R11-conforming | 4096² — N+1 legality **does not apply**, stamps composite into a base | **STAMP** | n/a. Catalogued: `terrain/stampit_catalogue.json` |

Both catalogues are **keyed by SHA-256 of file bytes**; 102/102 distinct.
Name, folder and index are metadata only — both were measured to drift.
**No cross-tier "same map" relationship is recorded**: the resolution
folders hold independently generated terrains.

### FAB-PLUGIN branch — native uassets already on disk

Delivered by the in-editor Fab window into **named top-level `Content/`
folders, not `Content/Fab/`**. Not committed to git (15.9 GB,
re-downloadable); paths recorded here instead.

| asset | source | licence | on disk | tier | role | verified |
|---|---|---|---|---|---|---|
| Open World Demo Collection (Kite) | Fab / Epic | Fab Standard — UE only | `Content/KiteDemo` — 272 files, 6,527 MB (270 uasset + 2 umap; 110 T, 37 M, 29 SM, 25 MI) | as shipped | **highest-value batch** — rocks, cliffs, ground, vegetation. Highland rocks/cliffs are alpine candidates | **NO** |
| Dragon Cave | Fab | Fab Standard — UE only | `Content/DragonCave` — 333 files, 5,050 MB (115 SM, 130 T, 66 MI) **— NOT ON DISK 2026-09-27** (gitignored pack; absent from Content/, measured live: `asset does not exist`; the registry dump `Free/_measured/fab_registry_DragonCave.json` survives it) | as shipped | POI / dungeon inventory | **NO** |
| Atlantis Ruins | Fab | Fab Standard — UE only | `Content/Atlantis_Ruins` — 274 files, 3,369 MB (37 SM, 158 T, 54 MI, **12 SK** skeletal fish/turtle/crab) **— NOT ON DISK 2026-09-27** (gitignored pack; absent from Content/, measured live; registry dump survives) | as shipped | POI / dungeon inventory | **NO** |
| UE template content | Engine template | Epic EULA | `Content/Mannequin` (26), `ThirdPerson` (6), `ThirdPersonBP` (5), `Geometry` (4) | n/a | mannequin is the **retarget target** for GASP | **NO** |

### WEB-DOWNLOAD branch — staged, not yet imported

| asset | source | licence | staged at | format | verified |
|---|---|---|---|---|---|
| `rock_collection_04` — 7 rocks | web download | **UNRECORDED — vendor not identified** | `Free/_intake/rock_collection_04` | FBX + TGA, **ORM-packed**; *measured:* B channel identically 0.000 → `R=AO, G=Roughness, B=Metallic` | **NO** |
| `tree_english_oak_forest_01` | web download (Megascans-style USD) | **UNRECORDED** | `Free/_intake/tree_english_oak_forest_01` | 5 USD + 4 `_DynamicWind.json` | **NO** — **LOWLAND inventory; must NOT be placed in the alpine region** |
| `animations.zip` — 1,374 FBX | community re-pack, GASP-style naming | **RISK: community re-pack of Epic-origin animations. UE-only, and the redistribution terms of the re-pack are NOT verifiable from the files** | `Free/_intake/animations` (sampled, not fully extracted) | FBX, animation-only | **NO** — quarantine on import |

---

## PLANNED — acquisition plan, ratified by Ryan 2026-08-03

**Nothing below is imported, verified, or licence-checked.** These are
intentions. A row moves out of this section only by going through
**R-ASSET** and earning a render proof.

### Characters and creatures — Paragon packs (Epic, free)

| asset | role | status |
|---|---|---|
| Grux | monster | PLANNED |
| Rampage | monster | PLANNED |
| Khaimera | monster | PLANNED |
| Greystone | character | PLANNED |
| Shinbi | character | PLANNED |
| Sparrow | character | PLANNED |

### Animation

| asset | role | status |
|---|---|---|
| Game Animation Sample (GASP) | **the locomotion baseline** — the retarget target every character drives | PLANNED |

### Environment

| asset | role | status |
|---|---|---|
| Infinity Blade environment packs | environment kit | PLANNED — **some are launcher-Vault-only, NOT on Fab web**; acquisition path differs per pack |

### THE KNOWN IMPORT CONSTRAINT — pre-recorded for R-ASSET's REJECTED

**The Paragon packs are UE4-era.** They cannot be dropped into a 5.8
project directly. Expected path, to be confirmed on first execution:

```
1. Add the pack to a 4.27 project.
2. Migrate / convert that content to 5.8.
3. IK-retarget the UE4 skeleton to the UE5 skeleton,
   so GASP's locomotion drives them.
```

This is **R-ASSET's first worked example**, and the reason R-ASSET is
PROVISIONAL rather than LOCKED: its skeletal/retarget half has never
been executed, so the IK Rig / IK Retargeter chain mappings per source
skeleton are `VALUE UNVERIFIED`. Do not write them from memory — run it,
measure it, then lock it.

**Photoreal-coherence check still applies to every row above.** Paragon
is stylised-realistic and MetaHuman is photoreal; that seam is a real
risk to the WORLD_VISION art direction and must be judged per asset on
render, not assumed because the pack is on the approved list.

---

## Why so many UNRECORDED rows

Every asset above predates R-ASSET. **These are gaps, not blanks to be
filled from memory** — CLAUDE.md forbids inventing a value, and a
licence is exactly the kind of value that must never be guessed. The
back-fill is a `BACKLOG.md` item; until it is done, treat the licence
status of everything above as genuinely unknown.

No asset in this register may be shipped outside the project until its
licence row is real.

---

## 2026-08-05 intake — three Fab items, three different verdicts

The principle these were ruled under, and the one to apply to future
packs: **ASSETS ENTER THE PROJECT; SYSTEMS GET STUDIED.**

### MW Landscape Auto Material (MAWI United) — REFERENCE-ONLY

| field | value |
|---|---|
| path | `/Game/MWLandscapeAutoMaterial` (97 assets) |
| plus | `/Game/watermaterials` (83), `/Game/WaterPlane` (31) |
| source | Fab, MAWI United |
| licence | UNRECORDED — Fab standard licence assumed, NOT verified |
| role | **REFERENCE-ONLY. Never a dependency.** |
| verified in engine | N/A — deliberately not integrated |

**Ruling 2026-08-05.** It is a complete shader-side auto-material: a
parallel implementation of our entire landscape material, with runtime
slope/height selection that **R2's rulings reject**, and no assertable
internals. **It does NOT enter the project's material path and never
becomes a dependency.**

*Permitted use:* a scratch level or project applying it to a COPY of our
terrain for side-by-side calibration renders at the standard viewpoints.
Observed differences become BACKLOG candidates implemented **through OUR
builder with our assertions** — never by importing theirs. Techniques it
teaches enter through the front door: designed, cited, asserted,
recipe'd.

*Provenance of the water folders:* `watermaterials` and `WaterPlane`
both date **2026-08-03 22:22**, one minute after
`MWLandscapeAutoMaterial` at **22:21** — the same install session. They
are MW example content and **fold under the same REFERENCE-ONLY
ruling**. Install-session timestamps are accepted here as provenance.

### Pack Bonus Textures (Lord Enot Store) — VERDICT PENDING AN INSTRUMENT

| field | value |
|---|---|
| path | `/Game/Pack_Bonus` (Grass_1/2/3, Stone_1/2/3, Tile_1/2/3, Wall_1/2/3, Wooden_Floor_1/2/3 — 5 maps each) |
| source | Fab, Lord Enot Store. Substance Designer, stylized |
| licence | UNRECORDED |
| role | candidate surface set |
| verdict | **PENDING** — see below |

Held deliberately. R-ASSET step 2 is *"photoreal-coherence check against
`WORLD_VISION.md`"* — **prose, with no instrument for SURFACES.** The
only implemented metric, `palette_evidence.py`'s triangle density, works
on meshes. Rendering a verdict here from judgement alone would be the
unfalsifiable-adjective problem the metric exists to remove, sitting
inside our own recipe.

**Expected outcome is EXCLUDED-WITH-REASON.** It is being held so the
exclusion comes from an instrument rather than from taste, because *a
gate that has only seen coherent input is untested by our own rule*.

### Wild Grass + Uncut Grass (Quixel Megascans, High tier) — NOT PRESENT

**Not in the project as of 2026-08-05.** `Content/Fab/` holds only the
Megascans base material library — 14 `M_MS_*` masters, 28 `QMF_*`
functions, 6 `T_Default*` placeholders — which is the shared dependency
the Fab plugin installs alongside any Megascans asset, and carries zero
surface content.

Wild Grass is the **meadow intake** and, when it lands, the clean
HOLDOUT for the coherence instrument: it plays no part in calibration,
so the instrument must ACCEPT it having been built only on ambientCG
photoscans and Pack_Bonus.

### Wild Grass (Quixel Megascans, High tier, `sfknaeoa`) — INTAKEN 2026-08-05

| field | value |
|---|---|
| source | Quixel Megascans via Fab, High tier |
| origin path | `/Game/Fab/Megascans/Surfaces/Wild_Grass_sfknaeoa/High/sfknaeoa_tier_1` |
| imported to | `/Game/Surfaces/T_WildGrass_{C,N,R,AO,D}` |
| licence | UNRECORDED — Fab standard assumed, NOT verified |
| role | **the meadow surface.** The 5th mandated surface Pass 2 could not deliver against a 3-channel weightmap |
| normal convention | **DX — MEASURED, not assumed** |
| verified in engine | **imports + read-back YES; render proof NOT YET** |

**Normal convention measured against the pack's own height map.** For a
heightfield the normal is ∝ `(-dH/dx, -dH/dy, 1)`. Rows increase
downward, so DX (green = −Y) predicts `corr(G−128, dH/drow)` POSITIVE
and GL predicts negative.

    corr(G-128, dH/drow) = +0.6709   -> DX
    corr(R-128, dH/dcol) = -0.6754   -> CONTROL, must be negative

The red channel is the **control that validates the method**: it must
correlate negatively regardless of convention, and it does, at a
symmetric magnitude. DX needs no green flip (ruling 1).

**ORM unpacked to discrete roles** per the 2026-08-05 ruling, R→AO and
G→Roughness verified per pack by the **height discriminator** — the
rock-calibrated albedo test failed here and was the wrong instrument for
a pigment-driven surface. Channel B **declared inert**: source
`min = max = 0.0`. Source is 8-bit (4 bytes/px), so the editor export is
lossless.

All five textures read back with their required settings: `C` sRGB
TC_DEFAULT; `N` linear TC_NORMALMAP; `R` and `AO` linear TC_MASKS; `D`
linear TC_GRAYSCALE.

**NOT YET DONE:** wired into the landscape material, and no render
proof — so `verified in engine` stays NO by R-ASSET's own rule that the
flag flips only after spawn + render.

### Uncut Grass (Quixel Megascans, High tier, `oilpt20`) — INVENTORY

| field | value |
|---|---|
| source | Quixel Megascans via Fab, High tier |
| origin path | `/Game/Fab/Megascans/Surfaces/Uncut_Grass_oilpt20/High/oilpt20_tier_1` |
| licence | UNRECORDED |
| role | **INVENTORY ONLY — not intaken** |
| verified in engine | N/A |

**Ruled 2026-08-05: catalogs as inventory. Use only if the selector
genuinely wants a third identity — do not add surfaces to spend them.**

Deliberately NOT unpacked or imported. It ships the same `B/H/N/ORM`
shape as Wild Grass and would intake by the same path if a third
identity is ever justified; until then it is recorded so it is neither
forgotten nor silently consumed.


### Pack Bonus Textures — EXCLUDED (provenance), ruled 2026-08-05

| field | value |
|---|---|
| path | `/Game/Pack_Bonus` |
| source | Fab, Lord Enot Store — Substance Designer, procedurally authored |
| verdict | **EXCLUDED — PROVENANCE** |

Coherence is ruled by **provenance, not appearance** (R16). This pack is
procedurally authored, not captured, so it is outside the photoreal lane
**regardless of what its pixels measure** — and no measurement is needed
to establish that.

The appearance instrument was retired for cause: it could not separate
its own calibration classes. Grass at n=4 photoreal vs 3 stylized
OVERLAPS on all three features, and the apparent separation at n=1 was an
artefact of sample size.

### Calibration surfaces (7) — CALIBRATION USE ONLY, not intaken

`Clover_vlzlbjon`, `Cut_Grass_sfenffsa`, `Dirt_Ground_xdhhdgq`,
`Dry_Fallen_Leaves_vetladiaw`, `Forest_Floor_sfjmafua`,
`Lush_Grass_xbrffjd`, `Soil_Mud_pjuph20` — all Quixel Megascans via Fab,
High tier, under `Content/Fab/Megascans/Surfaces`.

Used as descriptive reference only. **No R-ASSET intake, no material
wiring.** `Dry_Fallen_Leaves` ships **no `_H`** (4 maps, not 5) and
cannot feed the HeightLerp path without one — recorded before it is ever
wired.

### Megaplants conifers (2) — MEASURED 2026-08-14, **NOT ADOPTED**

Downloaded from Fab into `Content/Megaplant_Library/` (gitignored). Rows
recorded at intake time per "no asset without a row"; `verified in engine`
stays NO because nothing has been spawned or rendered.

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/Tree_Norway_Spruce_01_{A,B,C,D}` | Quixel Megaplants via Fab, listing `f87364c9-10a2-4834-8566-a0291c717758`, build `Megaplan6269b53162feV1`, published/updated 17 Jun 2026 | Fab Standard License | CANDIDATE replacement for `Conifer` (`fir_tree_01`) per `plans/conifer_asset_spec.md` (MOVED 2026-08-29 to `docs/archive/pre8k/conifer_asset_spec.md` — that spec is COMPLETE; the PVE Norway spruce was adopted 2026-08-15) | photogrammetry-derived, same lane as the Megascans surfaces | **NO** — not spawned, not rendered |
| `/Game/Megaplant_Library/Tree_Baltic_Pine/Tree_Baltic_Pine_01/Tree_Baltic_Pine_01_{A,B,C,D}` | Quixel Megaplants via Fab, listing `a2b04e81-5075-479f-a9d2-4940022f330a`, build `Megaplan043adaebd7d2V2` | Fab Standard License | CANDIDATE second species (currently `ConiferPine` = `ScotsPineTall_01`) | as above | **NO** — not spawned, not rendered |

**BLOCKING FACT, measured not assumed: all eight tree variants are
`SkeletalMesh`.** The foliage system instances `StaticMesh` only, so neither
pack can join the 153,796-instance forest as shipped. Only the `Instances/`
component parts (`Branch_*`, `Twig_*`, `Needle_*`, `Decoration_*`) are
`StaticMesh`, and a `find_assets` filtered to `StaticMesh` under
`/Game/Megaplant_Library` with name `Tree_` returns **zero rows**.

**Both foliage materials are `BLEND_Opaque` with the override ON**
(`MI_Norway_Spruce_Foliage_01`, `MI_Baltic_Pine_01_Foliage`, parent
`/ProceduralVegetationEditor/.../MA_Foliage_Trees`). The needles are real
geometry, not alpha-tested cards — so the spec's ">= 45% atlas opaque
coverage" criterion is **inapplicable to these assets**, not merely a weak
predictor of canopy density.

Measurements: `Free/_measured/tree_packs.json`, tool
`scripts/measure_tree_packs.py`. Requires the **Experimental**
`ProceduralVegetationEditor` plugin, enabled 2026-08-14.

### CORRECTION 2026-08-15 — the Megaplants section above is STALE

The section is headed **"NOT ADOPTED"** and both rows read *"**NO** — not
spawned, not rendered"*. **Both statements are now false**, and they are
corrected here rather than edited above so the record of what was believed
at intake survives.

The Norway Spruce WAS adopted on 2026-08-15. It was not adopted as shipped —
the `SkeletalMesh` blocking fact recorded above is correct and is exactly why
the route had to change. The armatures were re-exported from the Procedural
Vegetation Editor as **Static Meshes** (`Export Mesh Type` per node), and
those exports are the assets in the world.

**Baltic Pine remains genuinely NOT ADOPTED** — its row above stands. Its
four PVE exports are DEFERRED by the D2 ruling; Scots pine already covers
that role.

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `/Game/Meshes/Trees/SM_PVE_Norway_Spruce_01_{A,B,C,D}` | PVE Static-Mesh export of the Megaplants Norway Spruce armature above (listing `f87364c9-…`, build `Megaplan6269b53162feV1`) | Fab Standard License, inherited from the source pack | **THE LIVE CONIFER.** `recipes/alpine_8k.json` species `Conifer`, variant A, 92,519 instances | photogrammetry-derived, same lane as the Megascans surfaces | **YES** — `_verify/20260815_alpine8k_pve_spruce_forest_floor.png`; four-variant sheet `_verify/20260815_pve_spruce_four_variants.png` |

These four are **tracked in git**, unlike the vendor pack they derive from —
they are our exports, not vendor bytes.

**Also on disk and NOT the same thing:** `SM_Tree_Norway_Spruce_01_{A–D}` and
`SM_Tree_Baltic_Pine_01_{A–D}`, the eight ARMATURE bakes. They are a faithful
copy of trunk-and-branches with **no needles**, one prefix character away from
the four real exports in the same folder. Kept as the record of the route that
failed. **Do not scatter them.**

---

### PN_interactiveSpruceForest — MEASURED 2026-08-15, **NOT YET SCATTERED**

Already on disk at `LandscapeLab/Content/PN_interactiveSpruceForest/`
(**gitignored, 0 tracked files**, 363 files, 1.46 GB). No download and no
Fab session was needed for this intake — unlike the Megaplants packs.

| field | value |
|---|---|
| source | Fab, "interactive Spruce Forest" (PN prefix). **Listing id and publisher NOT RECORDED** — see the licence gap below |
| licence | **UNRECORDED.** No non-`.uasset` file exists anywhere in the pack, so terms are not recoverable from disk |
| role | D2's ruled tree intake: sapling tier, imposters, winter set |
| coherence | not assessed — no instrument for this, same hold as the surfaces |
| verified in engine | **PARTIAL** — spawned and rendered in a SCRATCH level (`_verify/20260815_pn_spruce_spread_wide.png`), **not** in `/Game/Alpine8K` and not scattered |

**Contents**, counted from disk:

    meshes            21   ALL StaticMesh -> all scatterable as foliage
    materials        106   MA_Summer / MA_Winter / MA_Imposter + instances
    textures          86   1.24 GB, incl. 21 imposter maps at 4096x4096
    Blueprints         2   PN_GlobalUpdater, PN_Bending_Component (wind)
    ExampleContent   118   demo content, not needed
    UE4_Mannequin     28   demo content, not needed

**The 21 meshes** are 14 "big" trees (7 base forms x high/low) at
**10.52–16.95 m**, plus **7 saplings at 0.56–7.74 m** — a size tier the
forest entirely lacked. Largest LOD0 is **28,510 triangles**, 17.7x lighter
than the incumbent `fir_tree_01`'s 505,494. Full table:
`_verify/20260815_pn_spruce_forest_intake.md`, raw
`Free/_measured/pn_spruce_forest.json`.

**THE IMPOSTER IS LOD4 OF THE MESH**, bound as material slot 3 at 4–6
triangles, screen size 0.10–0.17 — not a separate system. That closes
BACKLOG's aerial-readability item with vendor content. `MA_Imposter`
**recompiles clean in 5.8, 0 errors, 57 expressions.**

**Correction to the D2 ruling's wording:** it records "21 baked 4096²
atlases". It is **7 imposters x 3 maps** (A/N/O), all 4096². Every base tree
has one; the count is a texture count.

**TWO HAZARDS, both measured, both recorded before anything is scattered:**

1. **One `lod_group` write destroys every imposter.** 15 of 21 meshes carry
   the engine group `SmallProp` and 6 carry `NAME_None`, inconsistently — the
   same tree differs between its high and low variants. `SmallProp` declares
   `NumLODs=4` (`BaseEngine.ini:2685`); the big trees have **5**.
   `UStaticMesh::SetLODGroup` calls `SetNumSourceModels(4)` unconditionally
   (`StaticMesh.cpp:5605-5607`), which clears the mesh description and bulk
   data for every LOD above the new count (`StaticMesh.cpp:5944-5974`). The
   engine's own comment three lines above promises they "will be preserved".
   **The obvious tidy-up is the destructive act. Do not normalise the LOD
   groups.**

2. **The wind ANIMATES with no Blueprint present** — measured, three frames
   5 s apart, diff is a clean silhouette of the tree
   (`_verify/20260815_pn_wind_is_live.md`). It makes every pixel comparison
   non-deterministic. Removal needs **no vendor edit**: wind rides STATIC
   SWITCH parameters (`Level 1/2/3 Wind`, `Level 1/2/3 Bending`) on the three
   masters, and false in a child MI compiles the branch out.

**LICENCE GAP, stated plainly.** This pack has no licence record, and neither
do the other Fab packs pulled on 2026-08-14 (~3.5 GB total). R-ASSET requires
"the actual licence terms, not 'free'". Terms are not recoverable from disk
because the packs contain nothing but `.uasset` files. **Recovering them
needs Ryan's Fab library page** — it is his account, and no script here can
read it. Recorded as a known gap rather than assumed to be Fab Standard.

**NOT DONE:** not scattered, not in `/Game/Alpine8K`, no wind-off material
instances authored, and no `RECIPES.md` entry. `verified in engine` stays
**PARTIAL** until it is rendered in the real world.

---

## CORRECTION 2026-08-15 — THE ROW AT `ASSETS.md` "UE template content" IS WRONG ABOUT ITS ROLE

**Appended rather than edited, so the intake-time belief survives.**

That row records `Content/Mannequin` (26 assets) with the role *"mannequin is
the **retarget target** for GASP"*. **Measured, it is not, and cannot be.**

`scripts/probe_skeleton.py`, run 2026-08-15 against the live editor, artefact
`Free/_measured/skeletons.json`:

    /Game/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton
      bones 68
      pelvis TRUE   hand_l TRUE          <- positive controls pass
      spine_04 FALSE  spine_05 FALSE
      clavicle_out_l FALSE  index_metacarpal_l FALSE
      VERDICT: UE4 SKELETON

Because the two controls pass, those four absences are a **real absence** and
not a broken probe (non-negotiable 6). This is the **UE4** mannequin, 68
bones. GASP and every UE5-era animation set target the **UE5** skeleton, 161
bones. A retarget aimed here would fail, and it would fail after an animation
budget had been written against it.

**The role claim is retracted.** The row's other columns stand — the content
is on disk, it is Epic EULA, and its `verified` column always read **NO**,
which is the part of the record that behaved correctly.

**What IS the UE5 skeleton, measured in the same run:**

| asset | bones | verdict |
|---|---|---|
| `/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SK_Mannequin` | **161** | UE5, all 4 markers |
| `/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SKM_Manny` | 161 | UE5, all 4 markers |

**AND THAT PACK NEEDS A ROW IT DOES NOT HAVE.**
`GV_FreeShrubsPack/Demo/Mannequin` is 64 uassets including a 27.44 MB
`SKM_Manny`, and it is part of the ~3.5 GB licence gap recorded above. It is
gitignored vendor content carrying the only UE5 character rig currently inside
this project — and it has **no physics asset**, so it cannot support ragdoll.

**Ruled in `plans/characters_brief.md` (unit 4): adopt the ENGINE TEMPLATE
mannequin instead**, from
`UE_5.8/Templates/TemplateResources/High/Characters/Content/Mannequins/`,
which carries `PA_Mannequin`, 3 Control Rigs, `SKM_Manny_Simple`,
`SKM_Quinn_Simple` and 102 animations under the engine EULA. That set needs
its own `ASSETS.md` row at migration time, and **this note is not that row** —
nothing has been migrated yet.

---

## HERO GROOMS — MetaHuman wardrobe items, adopted 2026-08-16

Selected onto `MHC_AlpineHero` to match Ryan's ruled product look
(`hero/reference/hero_face_haired_frontal.jpg`: long layered dark hair, full
stubble beard and moustache, thick flat brows).

| Slot | Wardrobe item | Resolved binding | Role |
|---|---|---|---|
| Hair | `/MetaHumanCharacter/Optional/Grooms/Bindings/Hair/WI_Hair_M_Layered` | `Hair_M_Layered_Binding` | hero hair |
| Beard | `.../Beards/WI_Beard_M_Stubble` | `Beard_M_Stubble_Binding` | hero beard |
| Mustache | `.../Mustaches/WI_Mustache_M_Stubble` | `Mustache_M_Stubble_Binding` | hero moustache |
| Eyebrows | `.../Eyebrows/WI_Eyebrows_M_Dense` | `Eyebrows_M_Dense_Binding` | hero brows |

**Source and licence:** shipped with the `MetaHumanCharacter` plugin in the
UE 5.8 installation at
`C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\MetaHuman\MetaHumanCharacter\Content\Optional\Grooms\`.
Engine content under the Unreal Engine EULA — the same footing as the
template mannequin. **Not part of the ~3.5 GB Fab licence gap.** 108 groom
assets are reachable in total (86 hair, 16 beard, 16 moustache, 37 eyebrow
entries including thumbnails).

**Render proof:** NONE YET, and stated plainly rather than implied. These are
selected in the character asset and verified from its saved bytes
(`scripts/hero_face/verify_grooms_on_disk.py`, positive-controlled: four
selected names present at 3 hits each, five unselected names at 0 hits), but
they reach a rendered frame only through the UI Assemble, which has not been
pressed. `verified` = **NO**.

**Nothing was copied into the project.** These are references to plugin
content, so there is no vendor-boundary concern and no hash baseline to keep;
the reference lives in `MHC_AlpineHero.uasset`, which git tracks.

---

## Architecture evaluation — 2026-08-25 (LOOK TEST, NOT ADOPTED)

**These are NOT adopted assets and they carry no recipe.** They live in
`/Game/Scratch/FabEval/` and exist to answer one question: what should the
Alpine8K town's buildings be, once the greybox blockout is replaced. They were
never saved into a level. Rows are here because R-ASSET's rule is a row BEFORE
import, and an evaluation import is still an import.

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `/Game/Scratch/FabEval/SM_alps_chalet` | **Blenderust**, "Village in Alps", `village_in_alps.zip`, downloaded 2026-08-25, `source/Willage_in_alps.glb` (vendor's own typo) | **CC BY 4.0 — ATTRIBUTION REQUIRED, see below** | evaluation only — alpine roofline massing at range | alpine vernacular, but see the triangle counts | YES — `_verify/20260825_fabeval/FABEVAL_oblique.png` |
| `/Game/Scratch/FabEval/SM_alps_church_tower` | same | same | evaluation only — the one substantial building in the pack | 32,204 of the pack's 43,404 triangles are this tower | YES — same frame |
| `/Game/Scratch/FabEval/SM_alps_barn` | same | same | evaluation only | | YES — same frame |
| `/Game/Scratch/FabEval/SM_medieval_house_10` | **Darek Dubiniec**, free sample of "20 Medieval Houses", `medieval_houses_10.fbx` + `medieval_houses_textures.zip`, downloaded 2026-08-25 | **NOT RECORDED — free sample, terms not captured at download.** Sample of a paid pack; terms must be read from the product page before ANY use beyond this evaluation | evaluation only — candidate for a paid 20-house pack | | YES — `_verify/20260825_fabeval/FABEVAL_eyelevel_medieval.png` |

### ⚠ CC BY 4.0 — WHAT THIS OBLIGES US TO DO

**"Village in Alps" by Blenderust is CC BY 4.0.** Attribution is a CONDITION of
the licence, not a courtesy. If any part of this asset ships — in a build, a
screenshot used publicly, or a video — the credit must appear:

    "Village in Alps" by Blenderust, licensed under CC BY 4.0
    https://creativecommons.org/licenses/by/4.0/

**This is not satisfied by a row in this file.** A row records the obligation;
discharging it needs the credit to reach the shipped artefact. There is no
credits screen in this project yet, so **the obligation is OPEN**, and it
becomes due the moment anything derived from this asset leaves the machine.

**PARTIALLY DISCHARGED 2026-08-27 by `CREDITS.md`** at the repo root, which
carries the credit string itself. A credits SCREEN is still a later unit; until
one exists, `CREDITS.md` is what must ship with — or be reachable from —
anything derived from this asset. The obligation is no longer merely recorded;
it is also not yet inside a build.

**AND THE SAME SWEEP FOUND A WORSE GAP.** The ambientCG surfaces (Snow006,
Rock026, Rock051, Rock063, Ground037) have **no licence row in this file and no
licence file on disk** — checked across every `Free/*_4K-PNG/` directory. Unlike
the rows above they are not evaluation-only: they are load-bearing in the
shipped landscape material. Recorded as an OPEN gap rather than filled in from
memory — asserting a PERMISSIVE licence without a source is the direction of
error that actually costs something.

**It also survives modification.** The three meshes here are split, re-scaled
and re-pivoted derivatives of the original scene — CC BY covers derivatives, so
the credit is owed for these exactly as for the untouched glb.

### THE DUBINIEC LICENCE IS NOT RECORDED, AND THAT IS THE HONEST STATE

The mesh and its textures were downloaded as a free sample. **No licence text
came with either archive** — the mesh zip holds one FBX and the texture zip
holds 16 PNGs, nothing else. "Free sample of a paid pack" is a description of
how it was obtained, not a licence.

This is the same gap `ASSETS.md` already records for ~3.5 GB of Fab packs:
terms are not recoverable from disk. **Needs the product page before use.**

### PROVENANCE

Vendor archives extracted to `Free/FabEval/` — gitignored, per this repo's
convention that vendor binaries stay out of git and MEASUREMENTS go in
(`Free/_measured/*.json` is the tracked exception).

    Free/_measured/fabeval_village_in_alps.json   node inventory of the glb
    scripts/probe_gltf.py                          the tool that produced it
    scripts/blender/split_scene_clusters.py        the split + pivot + scale

---

## MEDIEVAL VILLAGE MEGASCANS SAMPLE — INTAKE BEGUN 2026-08-28, NOT COMPLETE

**Source, on disk and verified:**
`C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\MedievalGame_5.3`
— 9,777 files, **22.6 GB**, 9,685 `.uasset`. Pack is built for **UE 5.3**; this
project is 5.8. Packages load forward and all 15 probed meshes loaded clean;
recorded because it is a real difference, not because it failed.

**Licence: Fab Standard**, as an Epic-published Megascans sample. Not
independently re-read from the product page this session, so it is recorded at
the operator's statement — weaker than a licence file on disk and stronger than
the Dubiniec row below it, which has nothing at all.

**⚠ ONLY 15 MESHES HAVE CROSSED OVER, AND ONLY AS A MEASUREMENT PROBE.** No
materials, no textures, no maps, no lights, no foliage, no config. The probe
lives at `/Game/Kit/MedievalVillage/_probe/` and exists to answer one question —
what SIZE are the modules — because bounds and triangle counts are intrinsic to
a mesh and unaffected by a missing material. 5.4 MB against the ~800 MB the
textures for these 15 would have cost.

**The vendor source is gitignored** (`.gitignore` → `LandscapeLab/Content/Kit/`)
on the same line this repo draws for all vendor content: SOURCE is
re-downloadable and ignored, DERIVATIVES are committed. The measurement is the
derivative and it is committed at
`Free/_measured/kit_medievalvillage.json`.

### ⛔ THE PACK CONTAINS NO WHOLE-HOUSE MESHES

Confirmed by two independent listings — the OneDrive project skeleton's folder
names, and the vault cache's actual assets:

    Content/Meshes/Houses/          387 uasset
      MODULAR_ASSETS                259   Gable, Porch, Shingles, VerticalPosts,
                                          HorizontalBeams, RoofConst01-03,
                                          WindowShutter, Outcrop, Facade, Forge
      Roofs                          56
      Thatch_Cards                   61
      Construction_Pieces            10
      House1                          1   <- and it is SM_Plank_Base1, a PART

    Content/Megascans/3D_Assets/    the modular wall set, below

**It is a component kit.** Every asset is a wall, door, gable, roof piece, beam,
porch or shutter. There is nothing to place per building.

### MEASURED MODULES — live, 2026-08-28

| mesh | size m (x,y,z) | fallback tris LOD0 | Nanite tris | pivot base err |
|---|---|---|---|---|
| `SM_MedievalModularWall1x2MA` | 1.00 × 0.16 × 2.00 | 2,491 | 12,774 | +0.0 |
| `SM_MedievalModularWall1x2MB` | 1.00 × 0.49 × 2.00 | 1,788 | 10,597 | −0.0 |
| `SM_MedievalModularWall15x2M` | 1.50 × 0.18 × 2.00 | 2,944 | 10,186 | −0.0 |
| `SM_MedievalModularWall2x2MD` | 2.00 × 0.17 × 2.00 | 1,951 | 10,105 | −0.0 |
| `SM_MedievalModularWall2x2MG` | 2.00 × 0.20 × 2.00 | 1,874 | 10,318 | −0.0 |
| `SM_MedievalModularWall2x2MH` | 2.00 × 0.16 × 2.00 | 2,088 | 11,583 | +0.0 |
| `SM_MedievalModularWall3x2M` | 3.01 × 0.18 × 2.01 | 1,902 | 10,088 | −0.4 |
| `SM_MedievalModularCornerWall1x2M` | 1.03 × 1.03 × 2.00 | 705 | 12,358 | +0.0 |
| `SM_MedievalModularDoor1x2M` | 1.00 × 0.17 × 2.00 | 1,719 | 11,029 | −0.4 |
| `SM_MedievalModularDoor15x2M` | 1.51 × 0.19 × 2.01 | 2,524 | 13,785 | −0.5 |
| `SM_MedievalModularDoor2x2MA` | 2.00 × 0.18 × 2.00 | 2,024 | 10,080 | −0.3 |
| `SM_MedievalModularDoor2x2MB` | 2.00 × 0.18 × 2.00 | 2,294 | 12,004 | −0.0 |
| `SM_MedievalModularDoor3x2M` | 3.00 × 0.22 × 2.00 | 1,960 | 16,765 | −0.2 |
| `SM_MedievalModularGable4` | 4.82 × 0.17 × 2.18 | 1,249 | 19,724 | **−27.8** |
| `SM_MedievalModularGable4M` | 4.30 × 0.13 × 2.76 | 1,040 | 12,388 | **−14.9** |

**Nanite is already ENABLED on all 15**, so the "Nanite on unless a measured
reason says otherwise" instruction is satisfied by the vendor and no decision
was needed. One material slot each; 4–8 LODs.

**Pivots are base-centred to within 0.5 cm on every wall and door** — no
re-pivoting needed. **The two GABLES are the exception at −27.8 and −14.9 cm**,
which is correct for a roof-end piece that seats at eaves height rather than on
the ground, and is a trap for anything that assumes base-centred pivots
uniformly.

**Both triangle densities are recorded deliberately.** `fallback_tris_by_lod` is
the chain that renders with Nanite OFF; `nanite_tris` is what actually draws.
R-TREECOLLIDE was bitten once by reading a Nanite fallback and calling it the
source mesh.

**Rough budget, stated as arithmetic not as a measurement:** a 10 × 8 m
perimeter is ~18 m of wall ≈ 9 modules ≈ 110k Nanite triangles per house, so
303 houses ≈ 33M. Nanite's territory, but not free, and no frame cost has been
measured.

### MATERIALS AND TEXTURES — INTAKE COMPLETED 2026-08-29

**The dependency CLOSURE of the 15 modules, not a folder.** The pack is 22.6 GB;
the 15 measured modules need **106 packages, 942.7 MB**. That set was computed by
walking every `/Game/` reference in every package's name table to a **fixed
point** — and it closed with **0 dangling references**, which is the evidence
that it is complete rather than merely large.

    static meshes            15        5.5 MB
    material instances       15        1.3 MB   one per module
    textures                 69      935.3 MB
    material functions        5        0.4 MB
    master material           1        0.1 MB   M_GlobalRGB_Blend
    parameter collection      1        0.0 MB   GPC_GloablRGB_Blend (vendor typo)
                            ---      --------
                            106       942.7 MB

**Every module binds ONE material instance to the SAME master**,
`/Game/Materials/Masters/M_GlobalRGB_Blend`, plus a shared blend set at
`/Game/Meshes/Houses/MODULAR_ASSETS/BlendTextures/` (195.2 MB, the single
largest shared cost).

**Package paths are PRESERVED.** A `.uasset` references its dependencies by
package path, so the layout is not cosmetic: the earlier flat `_probe/` copy had
a material reference pointing at `/Game/Megascans/3D_Assets/...` that resolved to
nothing. Copying into the pack's own layout is what makes the references resolve.

**Hash-proven at adoption (NN20).** Every file was SHA-256'd at source and
destination and the pair recorded in `Free/_measured/kit_medievalvillage_closure.json`
— the committed derivative. Source stays gitignored and re-downloadable.
Spot-checked afterwards with `sha256sum`, a different tool from the `hashlib` the
copier used.

**The copier REFUSES rather than overwrites**, and it was proven to: a planted
decoy at `Content/Materials/Masters/` made it exit 3 with `--go` set. This
matters because `Content/Materials` and `Content/Meshes` are SHARED with 49
tracked project-owned files (`M_Alpine8K`, `M_AutoLandscape`, `PN_NoWind`, the
fir materials). The `.gitignore` entries are correspondingly narrow — only the
subtrees the vendor closure creates.

#### ⚠ THE TEXTURE SETS ARE NOT UNIFORM, AND THIS IS A VENDOR FACT

Anything that assumes one texture layout per module will be wrong on three of
them. All fifteen are COMPLETE as shipped — 0 dangling refs — so this is the
pack's own inconsistency, not an intake defect:

    12 of 15    _A  _MRF  _MaskRGB  _N          the common set
    CornerWall1x2M, Gable4    _A _MaskRGB _N _R   separate roughness, no packed MRF
    Wall2x2MH                 _A _MRF _MaskRGB    ** NO NORMAL MAP AT ALL **

`Wall2x2MH`'s material instance references no `_N` of its own; its only normal
comes from the shared `T_WellBlend_N`. Expect it to read flatter than its
fourteen siblings. Same class as the gable pivots above: **the exception is real,
and it is in the vendor's data, not in ours.**

#### ORM: NOT UNPACKED, AND THAT IS DELIBERATE

R-ASSET's ORM rule ("unpack to discrete roles at intake") governs SOURCE maps we
import and wire into OUR material declaration. It does not apply here: `_MRF` and
`_MaskRGB` arrive as already-imported `.uasset` textures wired by the VENDOR's
own master material, which we adopt whole. Unpacking them would mean rebuilding
`M_GlobalRGB_Blend`, which is a different unit and needs a reason. **Recorded so
the absence of an unpack step reads as a decision, not an oversight.**

#### ✅ VERIFIED IN ENGINE: **YES** — 2026-08-29

R-ASSET step 6 ran: all 15 modules spawned into `/Game/Alpine8K` and rendered.
Frames: `_verify/20260829_kit/KIT_row.png` (materials legible) and
`KIT_row_seated.png` + `CROP_seated_contact.png` (ground contact).

    master material   M_GlobalRGB_Blend  recompile -> 0 ERRORS
    bindings          15 of 15 modules bound to their own MI
    bound to default  0        <- WorldGridMaterial is non-null and IS failure
    live vs asset     the SPAWNED COMPONENT's material read back and compared
                      to the asset's; matched on all 15
    frame 1           2032x1273, luma mean 0.5264 std 0.2213,
                      0.000% blown, 0.000% black, 430,862 unique colours
    frame 2           luma mean 0.3592 std 0.2355, 0.000% blown

**The pixels show plaster and timber, not a checkerboard.** The near module in
frame 1 is a cream limewashed wall with a timber-shuttered window; the crop from
frame 2 is a plank door in a frame, seated on grass with no daylight under it.

**Nothing was saved.** `recompile_material` dirtied `M_GlobalRGB_Blend` and it
was left dirty in memory deliberately — saving it would rewrite bytes the
closure manifest has SHA-256'd, which is the whole basis of the copy being
hash-proven. Re-checked afterwards: **all 106 packages still match the manifest,
0 mismatches.** The eval actors were destroyed and the 1,446 city actors
unhidden; the world is as it was.

**⚠ THE FIRST FRAME HAS THE MODULES 27 m IN THE AIR, AND THAT IS MY DEFECT, NOT
THE KIT'S.** The placement traced ONE ground point with an EMPTY ignore list, so
it hit the forest CANOPY; measured afterwards at 2717.7–2815.4 cm of float
across the row. Reseated onto the cleared plaza with a PER-MODULE trace ignoring
foliage, the city and the eval actors: ground span 93.8 cm over 56 m, read-back
error 0.0 cm. **The frame is kept because it is the clearest view of the
materials, with its defect stated.**

Still not established: **frame cost**, and whether the 5.3 → 5.8 step is clean
beyond loading and rendering.

The 15 mesh-only probe copies were retired to
`LandscapeLab/Saved/superseded_probe_20260829/` — not deleted, and no longer in
`Content`, because a second copy of every module at a path nothing references is
a binding trap.

## ART-DIRECTION REFERENCES — operator concept art, intake 2026-08-29

**The project's first art-direction references.** Everything the concept
pipeline builds is judged against these.

| asset | source | licence | role | verified in engine |
|---|---|---|---|---|
| `refs/alpine_village_01.jpg` | **operator-supplied concept art**, copied from `Downloads/Village image 1.jpg` on 2026-08-29 | operator-supplied; **reference use only** — not shipped, not derived from, not redistributed | art-direction reference: the APPROACH view of site `alpine_village` | n/a — reference, never an engine asset |
| `refs/alpine_village_02.jpg` | **operator-supplied concept art**, copied from `Downloads/Village image 2.jpg` on 2026-08-29 | as above | art-direction reference: the INTERIOR view of the SAME site | n/a |

**Both 1433×736 JPEG, hash-proven at adoption** against the operator's
originals: `bf7cae76…` and `abf43d56…`. **Copied, never moved** — the Downloads
originals are untouched and nothing in this pipeline writes back to them.
Downloads was checked and is a plain local folder, not OneDrive-backed, and both
files carry only the `Archive` attribute — no placeholder/offline flag — so
there was no hydration question to settle.

**THEY ARE ONE PLACE, NOT TWO SCENES** — same horn peak, same onion-dome church,
same building vocabulary, same firewood. Both concept recipes therefore carry
`site_id: alpine_village`, and the two views are a CROSS-CHECK rather than two
builds. Reading of record: `_verify/20260829_concepts/READING.md`.

**⚠ THESE APPEAR TO BE ENGINE RENDERS, NOT PAINTINGS** — depth of field, god
rays, tonemapping and foliage cards. Recorded because it cuts two ways: the look
is *achievable* rather than illustrative, but if they originate in an existing
marketplace pack then "match the concept" may partly mean "acquire that pack".
Not established either way, and it does not change the reading.

---

## 2026-08-30 — C0 DONOR HOUSE AND ITS TEXTURE SET

**Recorded LATE, and that is the defect worth naming.** R-ASSET step 1 puts the
licence row BEFORE the import, and the C0 session imported the house first. The
row is written here rather than quietly backfilled into the table above, so the
ordering failure stays visible.

**Nothing in this block ships.** C0 is the texture-swap warm-up; its output is
`/Game/Scratch/C0House`, editor-only, and is not in any saved level.

| Asset | Source | Licence | Role | Verified in engine |
|---|---|---|---|---|
| `Medival House _.fbx` | operator download, `medieval-house.zip`, 31.7 MB, 2026-08-27 | **NOT RECORDED** | C0 donor mesh, scratch only | mesh YES (23,700 tris, 10 slots, measured 2026-08-30); materials pending |
| `rock_wall_08_diff_2k` | Poly Haven, shipped inside the zip's `.fbm` | CC0 **by filename convention, not verified against polyhaven.com** | kept albedo, `Material_007` | pending |
| `concrete_floor_worn_001_diff_4k` | Poly Haven, same | CC0, same caveat | kept albedo, `Material_008` | pending |
| `brown_planks_03`, `concrete_wall_003`, `grey_roof_01`, `rough_wood`, `wood_planks_grey` (all `_diff`) | Poly Haven, same | CC0, same caveat | REPLACED by the generated set; retained as the fallback the tiling ruling names | n/a |
| `refs/textures_v1/*.jpg` (5) | **operator-authored**, generated 2026-08-29 | operator's own work | C0 albedo swap | pending |
| `refs/textures_v1/*_tiled.jpg` (5) | derived from the above by `repair_tileable.py` | follows the source | the maps actually consumed | pending |
| `refs/derived_v1/*_N.png`, `*_R.png` (14) | derived from the albedos by `derive_material_maps.py` | follows each source | normal + roughness | pending |

**THE DONOR'S LICENCE IS UNRECORDED AND THAT IS A REAL CONSTRAINT, NOT A
FORMALITY.** It is the same position `medieval_houses_10.fbx` (Dubiniec) is in,
and the fingerprint check that chose between them is the reason C0 is on this
file at all. It is fit for a pipeline warm-up on scratch content and **is not
clearable for shipped content until the operator supplies the source page.**

**THE CC0 CLAIM ON THE POLY HAVEN MAPS IS PROVENANCE BY FILENAME.** Poly Haven
publishes everything CC0, and these carry its exact naming convention
(`<name>_diff_<res>`), which is why the claim is plausible. It has not been
checked against the site, and non-negotiable 9 says a claim inherited from a
naming convention is not a citation. Recorded as what it is.

**The seven Poly Haven maps are DIFFUSE ONLY** — no normal, no roughness
anywhere in the zip. Every other channel in this unit is derived, and
`recipes/c0_materials.json` carries the split between what is measured, what is
derived and what is authored.

---

## 2026-08-30 — MEDIEVAL VILLAGE KIT, SECOND INTAKE (wider seed)

Approved at Gate A. Same pack, same licence position as the 2026-08-29 rows:
Fab / Epic Games Launcher VaultCache `MedievalGame_5.3`, taken in by dependency
CLOSURE rather than by folder.

| Group | Meshes | Packages copied | Bytes | Verified in engine |
|---|---|---|---|---|
| Roofs | 10 | — | — | measured live 2026-08-30 |
| HBeam_* horizontal beams | 11 | — | — | measured live |
| GableSet, BoardWall, PorchBase, LanternPost | 8 | — | — | measured live |
| Props: bench, 2 wheels, wheelbarrow | 4 | — | — | measured live |
| **closure total** | **33 seeds** | **152 new packages** | **1871.7 MB** | resolution 0 dangling |

Seed: `recipes/kit_seed_v2.txt` — resolved against DISK by
`scripts/kit_seed_v2.py`, which REFUSES if any approved name matches nothing,
so a typo cannot silently shrink the intake.
Closure: `recipes/kit_closure_v2.txt` (169 packages) minus the 17 already
adopted → `recipes/kit_closure_v2_delta.txt` (152).
Manifest: `Free/_measured/kit_medievalvillage_v2_closure.json`, every file
SHA-256'd at both ends (NN20).
Measurements: `Free/_measured/kit_medievalvillage_v2.json`, 33 rows.

**Verified-in-engine is MEASURED, not RENDERED.** R-ASSET step 6 is a spawn and
a render and step 7 says the flag flips only then. These 33 meshes have been
loaded and measured; **none has been spawned or photographed**, so the column
above says what was actually done.

### ⛔ TWO NAME COLLISIONS INSIDE THE PACK — discriminate by PATH

`SM_LanternPost` and `SM_PorchBase` each exist TWICE, in `Construction_Pieces`
and in `MODULAR_ASSETS`, and they are **different meshes**:

    SM_LanternPost  Construction_Pieces  4612 nanite tris  pivot  -10.4 cm
                    MODULAR_ASSETS       2932              pivot  -85.2 cm
    SM_PorchBase    Construction_Pieces 23727              pivot  -32.4 cm
                    MODULAR_ASSETS       3798              pivot  -32.4 cm

A 6x triangle difference and, for the lantern, a 75 cm pivot difference. This
project has the rule already — equal names are not identity, compare the
resolved PATH — and here it is inside a single vendor pack.

### ⛔ THIS SEED IS NOT BASE-PIVOTED AND THE FIRST ONE WAS

The v1 modular walls all measured `pivot_base_error_cm 0.0`. **Every mesh in
this seed is negative**: the HBeams are centre-pivoted (~-8.6 cm on a 17 cm
beam), and the roofs run to **-201.5 cm**. Stacking the two seeds by arithmetic
without a per-mesh correction is wrong by up to two metres.

### WHAT THE WIDER SEED ADDS, AGAINST THE REAL TOWN

    303 buildings, footprints 7.03-14.95 m
    a SINGLE roof piece fits at +-20% on   132 of 303   (43.6%)
    footprints over the biggest piece (10.19 m)   245

**43.6% of the town can be roofed by one kit piece; the rest need a COMPOSED
roof, and the Roofs set does not ship ridge and slope as separate parts.** That
is the gap, stated rather than averaged away. The HBeams (1.45 / 2.54 / 2.56 /
2.74 m) supply the half-timbered banding the concept art shows, and they ARE
modular, so they tile any length.

---

## 2026-08-30 — POLYTRICITY HAIR CARDS (staging only)

| Asset | Source | Licence | Role | Verified in engine |
|---|---|---|---|---|
| `HairCards_FBX.fbx` | operator download, `hair-cards-fbx.zip`, 27 MB, archive dated 2024-06-17 | **NOT RECORDED** | hair-card strip, scratch staging | imported + measured 2026-08-30; **not rendered** |
| `HSD_Skecthfab_{Mask,RGBMask,Depth,AO,Frizz,NormalMap}.png` | same archive | **NOT RECORDED** | the six channels the card material reads | imported, settings read back |

**THE LICENCE IS NOT RECOVERABLE FROM DISK.** The archive holds seven entries
and **not one is a licence or readme** — the full list is
`source/HairCards_FBX.fbx` plus six `textures/HSD_Skecthfab_*.png`. The brief
allowed "licence from the Sketchfab page or Downloads note"; there is no note
in Downloads and no page reachable from the file. The filenames say *Skecthfab*
(the vendor's own typo), which is a hint about origin and **not a licence**.

**Staging only.** Everything lives in `/Game/Scratch/Hair` and
`/Game/Scratch/Hair_Stage`. **Nothing may enter the build until the operator
supplies the source page**, which is the same position the C0 donor is in.

### MEASURED

    SM_HairCards   40.4 x 0.7 x 31.1 cm   1256 tris   1 slot   1 UV channel
    M_HairCards    18 expressions, BLEND_MASKED, two-sided, clip 0.33
                   compiles clean, 0 errors
    staged         3 strips at yaw 0 / +40 / -40, material read back on each

**ONE UV CHANNEL**, so there is no second set to confuse with the Mask sheet.
Whether the cards land on that sheet correctly is a question only the render
answers, and per the brief it is REPORTED rather than re-UV'd.

**Root and tip colours are PLACEHOLDERS and are traceable:** concept 02's own
measured shadow rgb `(0.087, 0.101, 0.083)` for the root and sun rgb
`(0.663, 0.597, 0.480)` for the tip, so the frame shows something defensible
while the operator's swatches remain gated.

---

## 2026-08-30b — C0 DONOR IDENTIFIED AND CLEARED, WITH AN AI PROHIBITION

**Supersedes the 2026-08-30 "NOT RECORDED" row above.** Identified by the
operator, who owns the listing.

| Asset | Source | Licence | `no_ai_input` | Role | Verified in engine |
|---|---|---|---|---|---|
| **Medieval House** (`Medival House _.fbx`) | **Fab**, listing `69623e2f-f444-4dfc-a76d-3c7f795152bc`, by **Darek Dubiniec**, published Dec 2025, FBX, in the operator's Fab library | **Fab Standard License** — recorded | **`no_ai_input: true`** | C0 donor mesh | mesh YES (23,700 tris, 10 slots, measured); materials YES (7 instances, compile clean); **rendered YES** |

**SHIPPABLE. No longer scratch-only.** The licence is recorded, the listing is
in the operator's library, and the earlier "fit for a warm-up, not clearable
for shipped content" caveat is **withdrawn**.

### ⛔ `no_ai_input: true` — THE FAB LISTING SAYS *"Allows usage with AI: No"*

**This mesh, and renders of it, must never be used as input to TRELLIS or any
generation model.**

This is enforced in code, not by memory:

- `recipes/ai_restrictions.json` is the **single machine-readable register** —
  source globs, UE packages, levels, and render outputs.
- `scripts/ai_input_guard.py` **refuses** a restricted input and **fails
  closed** under `--strict`. Proven to discriminate: it refuses the FBX, its
  textures, the UE package and every C0 render, and passes the concept art, the
  kit and the operator's own generated textures.
- It is wired into `scripts/trellis/run_church.sh` and `run_control.sh` **ahead
  of the model load**, under `set -e`, so a refusal aborts the run.
- `scripts/check_ai_restrictions.py` asserts this document and the register
  agree.

**Why a hard gate rather than a note:** a generated mesh carries no provenance.
Once a restricted asset has been through a model there is no artefact to
inspect, no hash to compare, and no way to detect or undo it afterwards. The
only moment the check can work is before the run.

**Verified retrospectively: nothing restricted has ever reached a model.** The
only two TRELLIS runs took `refs/alpine_village_01.jpg` (the operator's concept
art) and TRELLIS's own bundled castle example. Both cleared by the guard.

### The Poly Haven maps inside the package — scope note

The seven Poly Haven diffuse maps ship inside this Fab package but are
separately CC0 by their own licence, and the operator's restriction names *the
mesh and renders of it*. They are **not** in the register. If that reading is
too narrow, the register is the one place to widen it.

### `medieval_houses_10` — STILL OPEN, and now restricted precautionarily

| Asset | Source | Licence | `no_ai_input` | Status |
|---|---|---|---|---|
| `medieval_houses_10.fbx` | same author, **Darek Dubiniec** | **STILL NOT RECORDED** | **`true` — PRECAUTIONARY** | not shippable |

**I checked the local Fab library database and it cannot close this row.**
`VaultCache/FabLibrary/listings_v1.db` holds **exactly one** listing — *Medieval
Village Megascans Sample* (`2e11a225-…`, cached to `MedievalGame_5.3`, 22.6 GB).
Neither Dubiniec asset appears.

**That is not evidence about the operator's web library.** The launcher DB
caches only what was downloaded *through the launcher*; the C0 donor arrived as
a zip from the Fab website and is legitimately absent too. So
`medieval_houses_10`'s presence in the Fab library is **UNKNOWN** and only the
operator can settle it.

Pending that, it is registered `no_ai_input: true` **precautionarily** — an
unknown licence from an author whose other work carries an explicit AI
prohibition is restricted until established otherwise. The cost of being wrong
is asymmetric and irreversible.

### One observation, deliberately not treated as a finding

The Fab DB has an **`is_ai_forbidden` column**, and for the Medieval Village kit
it reads **0**. But that row is largely unpopulated — empty description, no
tags, no formats, rating 0.0 over 0 reviews — so a `0` cannot be distinguished
from an unset default. **It is recorded as an observation, not as evidence that
the kit permits AI use** (NN21: an inert field reads exactly like a set one).

---

## 2026-08-30c — RULINGS 3 AND 7

### Poly Haven — CC0, CLEARED FOR SHIPPED USE

**Supersedes the "provenance by filename, unchecked" caveat.** Ruled by the
operator 2026-08-30 on the basis of Poly Haven's **site-wide CC0** licence.

| Assets | Licence | Provenance | Cleared |
|---|---|---|---|
| `rock_wall_08_diff_2k`, `concrete_floor_worn_001_diff_4k`, `concrete_wall_003_diff_2k`, `brown_planks_03_diff_2k`, `grey_roof_01_diff_4k`, `rough_wood_diff_2k`, `wood_planks_grey_diff_2k` | **CC0** | **Poly Haven, provenance by filename match, licence page cited: `polyhaven.com/license`** | **YES — shipped use** |
| `fir_tree_01_*`, `bark_willow_*`, `clay_roof_tiles_*`, `brick_wall_11_*`, `church_bricks_02_*`, `old_wood_floor_*`, `painted_plaster_wall_*`, `cracked_concrete_wall_*`, `roof_tiles_14_*`, `rusty_metal_sheet_*`, `wood_trunk_wall_*` | **CC0** | same — site-wide CC0 covers every asset | **YES** |

The ruling is that **filename convention plus content match is sufficient
provenance** when the licence is site-wide and unconditional. It is recorded as
what it is — a match against a naming convention, with the licence page cited —
rather than as a per-asset verification, so a later reader can see the basis
and disagree with it if they want to.

These are the KEPT albedos on `Material_007` and `Material_008` of the C0
house, and the fallbacks the tiling ruling names. **`CREDITS.md` needs no CC0
attribution line** — CC0 waives it — but the entry is kept for traceability.

### Hunyuan3D 2.1 — DECLINED, not deferred

Ruled **do not install**. TRELLIS is MIT and pipeline-proven (a positive
control produced a volumetric mesh through the identical code path).
**Revisit only if TRELLIS fails on a good input.**

Recorded here because a declined candidate that looks merely un-attempted
invites someone to attempt it. Its VRAM requirement remains **unmeasured on
this machine**, and no figure for it appears anywhere in this repo.

## Generated assets (the forge)

**Every row here was produced by a model.** `scripts/forge.py` writes
the row and `FORGE_LOG.md` carries the cost line. The AI-input
restriction is the one licence term whose violation cannot be detected
after the fact, so the guard runs before the weights load and the
clearance is recorded here rather than remembered.

| asset | source | licence | role | coherence | verified in engine |
|---|---|---|---|---|---|
| `/Game/Scratch/ForgeChurch/SM_Church_Forge` | **GENERATED** — TRELLIS multi-view from 4 operator concept references (`refs/church_refs/church_az{000,035,090,270}.png.jpg`), seed 20260830 | TRELLIS **MIT**; the references are the operator's own. All four cleared `ai_input_guard.py --strict` BEFORE the weights loaded (R-AIGATE) | Ruling 1 landmark church for the concept village; forged through the full 9-stage wrapper on 2026-08-30 | 60000 tris (hero_prop ceiling 60000), watertight, **genus 61 — topological noise NOT removed**, 1 UV channel (machine unwrap, greybox-grade), NO textures yet | YES — 1845.0 cm top vs a 1845.0 cm target (error 0.0 cm), footprint [1539.0, 796.6] cm, orientation gate PASSED, 60000 tris in engine — `forge_lineup.png` (church, chalet and wood stack at true scale). `church_beside_kit.png` is SUPERSEDED: it shows the pre-correction 1341.3 cm church beside a chalet whose roof was buried 201.49 cm in its walls |

## 2026-08-30d — POLY HAVEN TEXTURES, SOURCED DIRECT (and the .fbm provenance PROVEN)

**RULED by the operator 2026-08-30:** the AI-input restriction belongs to
Dubiniec's mesh and renders of it, **not** to the third-party CC0 textures he
bundled in the `.fbm`. `rock_wall_08` is Poly Haven's, CC0, cleared for
shipped use.

**The guard's directory rule is UNCHANGED and was not touched.** The fix is to
stop *sourcing* from that directory. These three came down from
polyhaven.com over its public API.

| file | source | licence | authors | download URL | integrity |
|---|---|---|---|---|---|
| `refs/polyhaven/rock_wall_08_diff_2k.jpg` | Poly Haven `rock_wall_08` @ 2k, downloaded DIRECT from polyhaven.com | **CC0** — [licence page](https://polyhaven.com/license), [asset page](https://polyhaven.com/a/rock_wall_08) | Amal Kumar | `https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/rock_wall_08/rock_wall_08_diff_2k.jpg` | sha256 `d01a1cbadd402ca0…` — **MATCHES the .fbm copy byte-for-byte** |
| `refs/polyhaven/wood_planks_grey_diff_2k.jpg` | Poly Haven `wood_planks_grey` @ 2k, downloaded DIRECT from polyhaven.com | **CC0** — [licence page](https://polyhaven.com/license), [asset page](https://polyhaven.com/a/wood_planks_grey) | Rob Tuytel | `https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/wood_planks_grey/wood_planks_grey_diff_2k.jpg` | sha256 `31bdd475c6f1520f…` — **MATCHES the .fbm copy byte-for-byte** |
| `refs/polyhaven/concrete_floor_worn_001_diff_4k.jpg` | Poly Haven `concrete_floor_worn_001` @ 4k, downloaded DIRECT from polyhaven.com | **CC0** — [licence page](https://polyhaven.com/license), [asset page](https://polyhaven.com/a/concrete_floor_worn_001) | Dimitrios Savva, Rico Cilliers | `https://dl.polyhaven.org/file/ph-assets/Textures/jpg/4k/concrete_floor_worn_001/concrete_floor_worn_001_diff_4k.jpg` | sha256 `73a4f3fe96a2c31d…` — **MATCHES the .fbm copy byte-for-byte** |

### ⭐ THE HASH COMPARISON PROVED THE PROVENANCE CLAIM

**All three downloads are byte-identical to the copies inside
`Medival House _.fbm/`.** That was the point of matching the resolution
exactly (2k, 2k, 4k) rather than taking the largest available: a comparison
between different renders of the same source proves nothing.

A match means the bundled copies really *are* the Poly Haven assets their
filenames claim — the naming was evidence, not just a claim. Had they
mismatched, the filenames would have been an assertion about re-encoded or
edited files and the direct download would have been the only trustworthy
copy. **We now know which of those two worlds we are in, and it is the good
one.**

`Free/_measured/polyhaven_v1.json` carries the full hashes both sides.

### THE OTHER FOUR TEXTURES IN THE `.fbm`, NOT YET SOURCED

    brown_planks_03_diff_2k.jpg      concrete_wall_003_diff_2k.jpg
    grey_roof_01_diff_4k.jpg         rough_wood_diff_2k.jpg

All four follow the same Poly Haven `<asset>_<map>_<res>` convention, and
`rough_wood` is the one four C0 slots consolidate onto (the `beam_wood` role).
**Not downloaded tonight** because nothing in the queue needs them; the same
one-command fetch serves them when something does.

### ⛔ WHAT THIS DOES NOT CHANGE

The `.fbm` copies stay off-limits as generation input, because the guard
refuses the directory and **the guard's scope was deliberately not modified**
(HARD LIMIT 2). Anything feeding a model uses `refs/polyhaven/`. The hash
comparison read the `.fbm` bytes to compute a digest, which is not a
generation input.

## Gemini v1 pack (side project) — intake 2026-08-31

**Source for every row:** generated by the operator with Google Gemini,
2026-08-31, from prompts authored this session. **Licence for every row:**
operator-owned AI output (Google generative AI terms); no third-party asset
fed to the model. Originals + SHA-256 manifest: `Free/gemini_v1/MANIFEST.json`.
Coherence: instrument uncalibrated (no photoreal specimen per family) — BY-EYE
notes only, recorded as judgement, not measurement.

| asset | role | tileability (measured) | by-eye note | verified in engine |
|---|---|---|---|---|
| `tex_valley_grass.jpg` | material layer Grass | ok (1.52x/1.83x) | flat albedo, no baked shadow | NO |
| `tex_cliff_rock.jpg` | material layer Rock | ok (1.60x/1.65x) | flat; minor crack AO | NO |
| `tex_forest_floor.jpg` | material layer ForestFloor | REFUSED 2.48x -> REPAIRED 1.12x (`_tiled`) | flat; teal biolum specks | NO |
| `tex_scree.jpg` | material layer Scree | REFUSED 2.50x -> REPAIRED 1.05x (`_tiled`) | flat | NO |
| `tex_river_gravel.jpg` | material layer Gravel | REFUSED 4.80x -> REPAIRED 1.17x (`_tiled`) | ⚠ wet specular gloss BAKED IN; roughness derivation will misread | NO |
| `tex_stony_dirt.jpg` | material layer Path | ok (1.66x/1.92x) | prompt asked mossy ruin stone, DELIVERED stony dirt — reassigned to the missing path slot | NO |
| `stamp_river_basin.jpg` | stamp seed (erode before use) | n/a | good: meander channel + rim | NO |
| `stamp_terraced_cliffs.jpg` | stamp seed | n/a | drew a terraced PIT not cliffs; usable as MIN carve or inverted; crop black border | NO |
| `stamp_spire_peaks.jpg` | stamp seed | n/a | ⚠ radial light rays baked in — lighting posing as height; needs floor-clamp | NO |
| `landmark_crystal_spire.jpg` | forge input | n/a | clean isolation, single front view only | NO |
| `landmark_stone_bridge.jpg` | forge input | n/a | clean isolation, single view | NO |
| `landmark_ruin_arch.jpg` | forge input | n/a | clean isolation, single view | NO |
| `concept_crystal_valley.jpg` | brief-extractor benchmark 1 (PROVEN — the spike) | n/a | the anchor concept | terrain YES — `spike_vista_south_lit.png` |
| `concept_coast.jpg` | benchmark 2 — adds sea level | n/a | harbor cove, waterfalls | NO |
| `concept_highland_lake.jpg` | benchmark 3 — night lighting | n/a | hardest lighting case | NO |
| `concept_canyon.jpg` | benchmark 4 — carve-dominant terrain | n/a | ledge city, hardest siting | NO |

## VAULT HOLDINGS — owned library content, NOT project working state (KEEP)

These are FAB/vault holdings the project OWNS but does not reference in a recipe.
"Unreferenced" is NOT grounds for deletion — a reference scan says nothing about
whether a purchased/claimed library asset should be kept (Ryan's criterion, not
the project's). Recorded here so a reference-scan tool finds them (Pass 5 2026-09-16).

| holding | size | what it is | ruling |
|---|---|---|---|
| `VaultCache/AncientGame_5.7` | 88.9 GB | Epic's *Valley of the Ancient* sample (ships as a project named `AncientGame`) | **KEEP** per Ryan (LESSONS.md:30229, 2026-09-13); re-acquiring is an 89 GB download. Do NOT propose deletion on reference-scan grounds. |
