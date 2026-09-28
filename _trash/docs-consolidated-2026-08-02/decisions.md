# Decisions

## 2026-08-02 — RULING (c): a mesh a RECIPE names must be pivot-normalised

Ryan chose option (c) from `docs/proposals/asset-pipeline.md`: make
`--normalized` mandatory for any mesh a recipe names, and leave ad-hoc
vendor imports ungated. Implemented in four places, because they guard
four different failures and no one of them is sufficient.

**1. The recipe gate** — `import_heightmap._validate_foliage`, via
`landscape_spec.recipe_normalization_errors()`. Every recipe-named mesh
(species AND grass varieties) must trace to a verified row in
`Free/_measured/normalized.json`. Reported as an ordinary validation
error, so every script that validates a recipe inherits it without
knowing about it.

**2. The creation gate** — `import_static_mesh.main()`. If the target
asset path is named by any recipe under `recipes/` and `--normalized`
was not passed, refuse at exit 2. This is the half the recipe gate
cannot cover: importing a vendor file as
`--name grass_medium_01_tiny_a_LOD0` leaves the recipe validating
perfectly, because the validator matches NAMES and that name is
verified — the asset behind it would just have been silently rebuilt
with the vendor pivot.

**3 and 4. The measurement that cannot be fooled** — `place_foliage`
before it adds a single instance, and `make_landscape_material` before
it builds a GrassVariety. Both read `get_bounds()` off the asset
actually loaded and refuse on offset, on degenerate bounds, or on a
failed read. Gates 1 and 2 are NAME checks against a file on disk;
these two measure the thing itself, at the moment it is about to be
instanced 28,302 times.

Why the boundary is where Ryan drew it: the importer cannot tell whether
a vendor import is for measurement or for instancing, but the RECIPE
can, because the recipe is what decides that something gets instanced.
An import under a name no recipe claims still works and is still
useful — that is what "ad-hoc vendor imports stay ungated" means, and
`import_static_mesh` says so in its refusal text.

### Ruled by the implementer at the same time: the VERTICAL half
Audit finding F5 was that nothing gated the vertical pivot. A mesh with
a correct XY pivot and its origin at the bounding-box CENTRE passes all
three measured gates and buries every instance to half its height —
minus 7.26 m for `fir_tree_01_c`. Ryan's ruling settled WHEN
normalisation is mandatory, not WHAT counts as normalised, so this was
ruled here under the standing autonomy grant.

`landscape_spec.MAX_BASE_OFFSET_M = 0.25`, absolute rather than
proportional: the quantity is a distance from the ground plane and does
not scale with the object. A 0.05 m grass tuft and a 14.5 m fir both
want their base at zero. `normalize_asset.py` puts the pivot at the
bounding-box minimum exactly, and the FBX round-trip preserved that to
3 micrometres across all 23 objects, so 0.25 m is generous by four
orders of magnitude.

### Still open, and NOT ruled
Object names in `Free/_normalized/` are a single flat namespace, so two
vendor sets shipping the same object name would collide silently. No
collision exists today (23 objects, all distinct). Flagged rather than
solved because the fix — namespacing by source file — changes every
asset path in the recipe, and that is not a change to make at the tail
of a session.

## 2026-08-02 (late) — the vendor assets, and what reverse-engineering them cost and returned

Ryan supplied ambientCG surface sets and Poly Haven meshes with the brief:
reverse-engineer their files to improve the pipeline, replace what we have
where theirs is better, run wide open. Four decisions came out of it, all
made under the standing autonomy grant of 2026-08-02.

### D1. `measured` outranks `vendor`. Full stop.
`Free/manifest.json` carried `mesh_extent_m: 7.3` for `grass_medium_01`
and `3.6` for `grass_medium_02`, both `source: vendor`, both correctly
transcribed from the publisher's listing. Both describe the WHOLE SET laid
out in a row for the product shot. The largest single tuft is 0.327 m.

That value had already propagated: the recipe's `scale_range` of
`[0.05, 0.11]` against a 0.147 m mesh produced grass **0.7 to 1.6 cm
tall**, which is invisible, and nothing in the pipeline reported anything
wrong.

**Ruled:** once `normalize_asset.py` has measured an object, `measured`
wins and the vendor value is DROPPED — not averaged, not kept as a
cross-check. The vendor entries for both grass sets have been removed from
`FOOTPRINTS` entirely, because `FOOTPRINTS` is consulted first and a stale
entry there would silently outrank the measurement.

**This closes proposal open question 6** ("how does an assumed footprint
get promoted to a calibrated one after visual tuning"). The premise was
wrong. Visual tuning is not the promotion path and never should have been:
a number that was never a measurement does not become one by being tuned
until the picture looks acceptable. The promotion path is measurement, and
it is cheap — one headless Blender run over the source file.

`assumed` footprints (the four ambientCG rock/snow sets at 4.0 m) are NOT
affected: those are tiling periods of a repeating surface, which no file
measurement can recover. They remain `assumed` and remain flagged.

### D2. Pivot normalisation is mandatory for anything instanced
Measured on the live editor: `/Game/Meshes/fir_tree_01_c_LOD0` had its
geometry **12.406 m** from its own pivot, because the vendor FBX lays its
three trees side by side. Every instance was displaced by that much, every
random yaw swept it around a 12.4 m circle, and `align_to_normal` levered
it about a point 12 m away.

`FbxStaticMeshImportData.import_translation` cannot fix this — one FBX
yields all its objects in a single import and the property is per-import,
so the same offset would apply to every object. The fix has to precede UE.

**Ruled:** `scripts/blender/normalize_asset.py` is now a required step for
any mesh that will be instanced, and `import_static_mesh.py --normalized`
REFUSES unless the normalisation report names the object as verified. It
does not fall back to the vendor file.

**Deliberately NOT ruled, and left for Ryan:** whether the vendor-path
import should also hard-fail on a large pivot offset. It currently WARNS.
The script cannot tell whether a vendor import is for measurement or for
instancing, and making `--normalized` mandatory by force would break the
measurement use. See "Needs Ryan" in docs/next-step.md.

### D3. Grass is five size classes, not one mesh
`LandscapeGrassType` holds a LIST of `GrassVariety` and the vendor sets are
authored as size classes for exactly that. Using one mesh threw away the
variation the asset was built to provide.

**Ruled:** schema v1.10 `varieties`, with `share` as a normalised WEIGHT
rather than a fraction that must sum to 1. Requiring a sum of 1 would
reject a list that rounds to 0.99 — a validation error about arithmetic
rather than about intent. `density_per_10m2` stays the species total and is
split, so editing the variety list does not change how much cover there is.

Five varieties chosen, not sixteen: each variety is a separate GPU spawn
pass, and the documented hardware is an integrated GPU on Medium
scalability. The remaining eleven `grass_medium_01` objects and all five
`grass_medium_02` objects are normalised and on disk, so widening the set
is a recipe edit, not an import job.

### D4. Nanite stays OFF for the alpha-masked foliage
Not a new decision, but it was re-examined this session and the answer did
not change: 505,494 triangles at 28,302 instances is a lot to leave to
conventional rasterisation, but Nanite's masked support in 5.8 costs the
fast path, and the mesh currently has ONE LOD. The right fix is LODs, not
Nanite — recorded as an open item rather than done, because generating and
verifying LODs is its own audited change and this session did not have room
for it honestly.

**Stated plainly:** the scene as saved has 28,302 single-LOD 505k-triangle
trees in it. It renders, and the captures are evidence of that, but this is
the least defensible number in the project right now.

## 2026-08-02 — P3 fog: the height DATUM was unmanaged, and the falloff was meaningless
Two defects, both structural rather than aesthetic, both now fixed in the
recipe rather than by nudging a slider.

**1. The fog's world Z governed nothing and was set by nobody.**
Exponential height fog is densest AT the actor's Z and thins upward, so
that one number decides which part of a world is buried and which is
clear. `apply_lighting` only ever did `_find_or_spawn` — it never set the
location. The actor sat at **Z 192000 (1920 m)**, wherever it was first
spawned, while the new terrain's 90th percentile is **1610 m**. Ninety
percent of the world was under the densest fog and only the 2355 m summit
cleared it. Hard rule 2 says every scene parameter comes from the recipe;
this one never did. Now `lighting.fog.height_datum_m`.

**2. `height_falloff: 0.12` did not mean what it looked like.**
`SceneCore.cpp:405` divides FogHeightFalloff by 1000 before use, so
density halves every `ln(2) / (falloff/1000)` centimetres. The recipe's
long-standing 0.12 was therefore a **57.8 m half-height** — a near-
vertical wall of fog, which is the hard horizontal line visible across
the 2026-08-02 captures and which nobody chose. Replaced by
`lighting.fog.half_height_m`, in metres, converted at apply time as
`falloff = 1000 * ln(2) / (half_height_m * 100)`. A number a person can
reason about instead of one nobody could.

**Schema v1.4.** `lighting.fog.height_falloff` is REMOVED and the
validator refuses it by name with the explanation, rather than silently
ignoring it — a recipe carrying the old key is a recipe whose author
believed something false about it.

Set from the terrain's own distribution (p50 267 m, p90 1610 m, max
2355 m): datum 150 m, half-height 300 m, density 0.0015, start 1500 m.

**Measured effect**, same cameras, same terrain, fog alone:

| camera | contrast before | after |
|---|---|---|
| diag_topdown | 32.6 | **41.7 (+28%)** |
| diag_oblique | 29.5 | **35.8 (+21%)** |
| snowline_detail | 26.5 | 28.0 (+6%) |
| ridge_wide | 28.3 | 27.1 (-4%) |

The two that improved most are the ones looking across the world. The two
that barely moved are looking at terrain the cameras no longer frame
correctly — which is item 2, and expected.


## 2026-08-01 — DIRECTION: this is a world pipeline, not a landscape
Ryan, setting the frame: the target is a world-exploration RPG, movement
includes airships and flight, and there will be multiple worlds and
dimensions. **Environment development is first priority, and the priority
within it is the PROCESS** — approach, quality bar, lessons and recipes
locked in so generation can then go fast.

Three things follow, and they change how work is judged from here.

**1. "Good terrain" is now a measurement, not a taste.** The pipeline
gained `traversability()` and `landmarks()`. Every world is scored before
it ships:
- crossable fraction PER MOVEMENT MODE (walk / mount / climb / air),
- the LARGEST CONNECTED region for each, because a map can be 70%
  crossable and still broken if that 70% is a thousand isolated shelves,
- navigation landmarks: peaks with enough PROMINENCE to orient by from
  the air, which is what matters once travel leaves the ground.

**2. Movement limits are DATA (`MOVEMENT_PROFILES`), not policy.** Only
`walk` carries an engine-derived number — 44.765 deg, read live from the
`UCharacterMovementComponent` CDO, not from documentation. The rest are
starting points to be moved per world. Hardcoding "walkable" as though it
were physics would have quietly made every future world a walking world;
that was caught before it set.

**3. A correction to my own judgement, on the record.** I reported the
eroded terrain as a regression because its median slope fell from 44.2 to
22.1 degrees. I was scoring it as a hero landscape. Against the actual
goal that reading is backwards: a median of 44.2 means the MEDIAN CELL
sits at the walkable limit, i.e. half the world is wall. The erosion moved
toward the goal, and I only saw it once the right metric existed. **The
lesson generalises past terrain: when the measure is aesthetic, "better"
is unfalsifiable — build the metric that encodes the purpose first.**

### What the CURRENT, PUSHED terrain actually is
Measured, 2017 at 400 cm spacing:

| mode | crossable | largest region | in one piece | regions |
|---|---|---|---|---|
| walk | 52.0% | 26.4% | 50.8% | 20760 |
| mount | 18.6% | 0.2% | 1.3% | 67515 |
| climb | 98.5% | 98.5% | 100.0% | 10 |
| air | 100% | 100% | 100% | 1 |

Landmarks: 76 peaks over 120 m prominence across an 8.1 km square
(116.9 per 100 km2), greatest local prominence 469 m.

**So the world we have is a CLIMBING AND FLYING world** — not by design,
by accident. A walker arrives on one of twenty thousand disconnected
shelves; a rider cannot go anywhere at all. That is a legitimate kind of
world, and if it is the one we want it should be chosen rather than
inherited. It is also exactly the kind of fact that no amount of looking
at captures would have revealed.

### Standing quality gate, to be applied to every world recipe
A world declares its intended PRIMARY movement mode, and the generator
refuses to call itself done unless that mode reaches a stated
`largest connected` target. Fragmented walk regions beside a whole climb
region is a FEATURE when the design is "gain an ability, unlock the map"
— and a defect when it is not. The recipe should say which.


## 2026-08-01 — SIZE PROBE: it is NEITHER batching nor extent. It TILES.
Diagnostic only; nothing written. This overturns my own "one quadrant,
rest empty" reading from the previous probe.

**The extent is absolute and correct.** Exporting into 1009, 2017 and 3025
targets:

    RT 1009  -> data to index 1008, covered fraction 1.000, 11/11 correct
    RT 2017  -> data to index 2016, covered fraction 1.000, 11/18 correct
    RT 3025  -> data to index 2016, covered fraction 0.667, zero beyond

The drawn region is 2017 vertices per axis whatever the target size — it
does not scale with the target, so the canvas-extent hypothesis is dead.
And the region beyond 1008 is NOT empty, which is what I reported last
time: it is full of real terrain values.

**The defect is that the content REPEATS with period 1008:**

    RT(x, y) = arr[y mod 1008, x mod 1008]

Measured on the diagonal: every sample at index <= 1008 matches the source
under identity (12/12), and every sample beyond it matches mod-1008
(RT 1009 = arr[1,1] = 140; RT 1200 = arr[192,192]; RT 1512 = arr[504,504]
= 41043, the same value the probe read at 504; RT 1800 = arr[792,792]).
Overall 17 of 19 diagonal samples fit the tiling law and only 12 fit
identity. The two that fit neither are the tile edges at exact multiples
of 1008, which take the 1008 value — consistent with tiles being 1009
vertices wide and sharing their edges.

    1009 = 16 x 63 + 1  ->  16 x 16 = 256 components of distinct content
    2017 = 32 x 63 + 1  ->  the terrain is 32 x 32 components

So the engine renders one quarter of the components' worth of DISTINCT
content and repeats it 2x2 to fill the full extent. That is a
heightmap-texture / UV-offset problem inside the export, not a residency,
extent, encoding, layout or read problem — all five of those are now
settled by measurement.

**Correcting my previous entry:** I read the beyond-1008 region as
"unpopulated, near-zero" from values like 140 and 527. Those are not
empty — they are the terrain's own low corner, `arr[1,1]` and neighbours,
tiled in. I inferred "empty" from small numbers without checking whether
small numbers were *expected* there. The per-block extent gate then
faithfully reported 0/256, which was true but pointed at the wrong cause.

**Consequence for P0, and the recommendation.** The export cannot verify
this landscape outside the first 1009x1009 block; inside it, it is exact
(256/256 at block (504,504)). The verification should therefore be
restructured, and it is the same shape already recommended for D4:

  * **Primary verification: the pre-import RENDER TARGET readback.** It is
    already implemented, reads the exact buffer that is about to be
    written, at full resolution, and compares it texel-for-texel against
    the source PNG. It has none of these problems because it never goes
    through the engine's export path.
  * **Secondary: the export read-back, restricted to the region it can
    represent**, as a "the write actually landed" check rather than as the
    authority — and gated so it can never silently be trusted outside
    x,y <= 1008.

That removes the last dependency on a path that has now cost four probes,
and it is strictly more rigorous than what it replaces: the RT check
compares every texel, not 1280 samples.


## 2026-08-01 — Residency is NOT the cause; the quadrant is exact
Residency load and extent gate added and re-run. Diagnostic only; nothing
written.

**The extent gate works and names the defect precisely.** Per-block, under
the identity mapping:

    block (504, 504)      256/256  within tolerance
    block (1496, 504)       0/256
    block (504, 1496)       0/256
    block (1496, 1496)      0/256
    block (1008, 1008)        1/256   <- the single boundary texel

That is the quadrant hypothesis confirmed to the texel: everything at
x,y <= 1008 is exact, everything beyond is empty. The gate refuses with
"the export is PARTIAL" instead of the old degenerate-orientation message,
which named the wrong component.

**The residency load did NOT fix it, and that is the finding.** The new
stage enumerates actor DESCRIPTORS via
`WorldPartitionBlueprintLibrary.get_actor_descs` and calls `load_actors` on
every landscape one — capture's audited pattern — and it passed: want and
have agreed, so 1 landscape and all 256 proxies are loaded. The export
still covered only 256 of 1024 components.

So the World Partition explanation is **eliminated**. Everything is
resident, every component is enumerable (`components: 1024`,
`min_section_base: [0, 0]`), and the export still writes a quarter of the
target. The cause is inside
`LandscapeExportHeightmapToRenderTarget` itself, not in what is loaded.

**What is still unexplained, stated as unexplained:** why 16x16 components
of 32x32. Candidates not yet tested, cheapest first:
1. **Heightmap-texture batching.** The engine groups triangles per
   `Component->GetHeightmap()` into one `FCanvasTriangleItem` per texture
   (`LandscapeEdit.cpp:8240-8300`). If only the first batch draws — or the
   MIDs share state — coverage would be a subset tied to texture count,
   not to residency. A 2017 landscape has multiple heightmap textures, and
   the covered region being exactly one quadrant is consistent with one
   batch of four drawing.
2. **Canvas extent.** `FCanvas` is constructed on the render-target
   resource directly; if it takes a smaller effective viewport than the
   2017 target, everything outside is never rasterised.
3. **RT size dependence.** Export into a 1009x1009 target and see whether
   coverage is still one quadrant (points at batching) or becomes the whole
   target (points at extent).

**Do not treat this as a terrain problem.** Block (504,504) matched
256/256 exactly — where the export writes, it writes the right values with
the right layout and the right encoding. Read, layout, encoding and
residency are all now settled; only coverage is not.


## 2026-08-01 — LAYOUT PROBE: the read is correct; the EXPORT is partial
Diagnostic only; nothing written. This closes the layout question and
leaves one concrete defect.

**Two things settled, both by measurement:**

1. **The area-read arguments are (MinX, MinY, WIDTH, HEIGHT).** Passing
   `(1008, 1008, 8, 8)` returned exactly 64 values; passing
   `(1008, 1008, 1015, 1015)` returned **1,018,081 = 1009²**, i.e. the rect
   ran to the target edge and clipped. The audit's correction stands, and
   it is now backed by measurement rather than a source trace.
2. **The read layout is identity and correct.** A block read at (100,200)
   matched the source heightmap `arr[200, 100:108]` and the four rows below
   it — **40 of 40 values, exactly**. A per-pixel control
   (`read_render_target_raw_pixel`) agreed with the area read at every
   coordinate tested. So RT texel (x, y) IS `arr[y, x]`, and neither the
   arguments nor the un-flattening is at fault.

**The defect: the export only fills the first quadrant.**
The block at (1008,1008) is correct at exactly one texel — `arr[1008,1008]
= 44883` — and wrong at every texel beyond it, with values collapsing to
near-zero (140, 527, 437, 485 …). The last correct index on both axes is
**1008**, so the populated region is 1009 × 1009.

    1009 = 16 × 63 + 1      → 16 components per axis
    2017 = 32 × 63 + 1      → 32 components per axis (the whole terrain)

So the export covered **256 of the 1024 components** — and at 4 components
per streaming proxy, **64 of the 256 proxies**. Exactly one quadrant.

This also explains the pre-flight's degenerate score: of its five sample
blocks only (504,504) lies inside the populated quadrant, so roughly one
sample in five could match under the true mapping and every mapping scored
alike. The decisiveness guard refused rather than picking a winner, which
is what it is for.

**Leading cause and the fix to try first.** `LandscapeExportHeightmapToRender
Target` builds its component list from `Proxy->LandscapeComponents` over
`LandscapeInfo->ForEachLandscapeProxy` (`LandscapeEdit.cpp:8194-8208`), and
under World Partition that sees only what is loaded — CLAUDE.md's standing
gotcha, *"WP exposes only loaded actors; every census is silently
partial."* Note our own census counted 1024 components in the same payload,
so the actors were enumerable to `get_all_actors_of_class` while the export
still missed three quarters of them: **actor-loaded is not the same as
component-registered-for-export**, and the census gate the auditor added
does not catch this. `capture.py` already solves the general problem with
`WorldPartitionBlueprintLibrary.get_actor_descs` + `load_actors`, and that
audited pattern should be applied before the export.

**The gate to add regardless of cause:** compare the exported extent
against the expected one. A partial export is invisible today until the
scoring goes degenerate; it should be its own named refusal, because a
quadrant of correct data is exactly the kind of result that would pass a
looser check.


## 2026-08-01 — PROBE RESULTS: encoding SOLVED, layout is the remaining defect
Three probes run at Ryan's instruction. All diagnostic; nothing written.

### Probe 1 — the log. No warning, and the export does real work.
`LogLandscapeBP: Took 4.141328 seconds to export heightmap to render
target.` Four seconds is not the zero-component early-out, and there is no
material or shader warning anywhere around it. The draw runs.

### Probes 2 and 3 — the matrix. THE ENCODING IS SOLVED.
Reading an 8x8 block at the terrain centre, varying one input at a time:

| format | flag | normalize | R range | first texel |
|---|---|---|---|---|
| RGBA32F | False | False | 140 .. 44883 | R=G=44883 |
| RGBA32F | False | True | 0.0031 .. 1.0 | clamped |
| RGBA32F | True | False | 0 .. 0.686 | R=0.686275, G=0.325490 |
| RGBA8 | False | — | 255 .. 255 | saturated |
| RGBA8 | True | — | 0 .. 175 | R=175, G=83 |

**With the flag FALSE, R carries the RAW uint16 height, broadcast to RGB.**
Cross-validated rather than trusted: with the flag TRUE the same texel
gives bytes 175 and 83, and 175*256 + 83 = **44883** — exactly the
flag-False raw value. Two independent encodings agreeing on one number.

So the flag does exactly what its name says, and export IS symmetric with
import's `(uint16)LinearColor.R` (`LandscapeEdit.cpp:8138`).

**I HAD THIS WRONG, and the method is what failed.** I read the material's
`If` node through `MaterialTools.get_expression_inputs`, saw `A > B` and
`A == B` apparently wired to the same TextureSample, and concluded the flag
changed nothing and the output was a byte split. The measurement
contradicts that flatly. **Reading a node graph through an introspection
API is not the same as reading source**, and I reported it with more
confidence than it had earned. The probe matrix settled in one run what two
rounds of inference could not. Recorded as a lesson, not just a correction.

Also learned: the FIRST export after the editor has been idle returned an
all-zero target; every export after the probe warmed it returned data. Do
not diagnose a cold first export as a failure.

### The remaining defect: RT LAYOUT, and it is now sharply isolated.
With the encoding fixed, no mapping matches — all eight score ~12600-13500
median units, which is the degenerate signature the decisiveness guard
exists to catch, and it correctly refused.

The probe's first four values at block (1008,1008) were
`44883, 35192, 35196, 35214`. In the source PNG:
- `arr[1008,1008] = 44883` — element 0 matches exactly;
- `arr[1008, 1:4] = 35192, 35196, 35214` — elements 1-3 match **column 1
  onwards of the same row**, and that three-value sequence occurs exactly
  ONCE in the whole 2017x2017 image, so it is not coincidence;
- `arr[1008, 0] = 35171`, so the run does not simply start at column 0.

Element 0 is at (1008,1008); elements 1+ are at (1,1008), (2,1008),
(3,1008). Either the read's rectangle arguments do not mean what either
reading of `ReadRenderTargetRawPixelArea` assumed, or the returned array is
not laid out row-major over the requested rect. Note this is the same call
the audit already corrected once (MaxX/MaxY vs Width/Height); the
correction was applied on a source trace and is now contradicted by
measurement, exactly as the encoding was.

**Next probe, one run, decisive:** dump ~32 consecutive returned values for
a known block under BOTH argument interpretations — `(x0, y0, w, h)` and
`(x0, y0, x0+w-1, y0+h-1)` — and match each against the PNG offline. The
layout falls out of that immediately, and no other question is left.


## 2026-08-01 — OPEN: the export render target comes back BLACK
Dry run after the D4 ruling. **Nothing was written** — the pre-flight gate
refused before the push stage. Recorded so the next session starts from the
evidence rather than the symptom.

What passed: rule 7, the level gate, identification by property signature
(`Landscape_Alpine`, res 2017, step 63, 1024 components), the runtime
reflected-name resolution, and the new resident-census gate
(`components: 1024, min_section_base: [0, 0]` — so the export's
`ExportBaseOffset` really is the origin and RT texel == vertex holds).

What failed: **every exported texel is 0.0.** `raw R range 0.0 .. 0.0`
across 1280 vertices in 5 blocks spread over the terrain.

**It is not a race.** `LandscapeExportHeightmapToRenderTarget` ends with
`Canvas.Flush_GameThread(true)`, an `ENQUEUE_RENDER_COMMAND` doing
`TransitionAndCopyTexture`, and then `FlushRenderingCommands()`
(`LandscapeEdit.cpp:8305-8315`). The draw is complete and synchronous
before the call returns, so a black target is a real result.

**It is not an empty component list.** The engine early-outs at
`:8210-8213` returning true when `LandscapeComponentsToExport.Num() == 0`,
which is why the auditor had `export_returned` relabelled "not evidence" —
but our own census counted 1024 components across the resident proxies, and
`InExportLandscapeProxies=True` with `GetLandscapeActor() == this` appends
every proxy's components at `:8199-8208`.

**Leading hypothesis, and the one thing left unverified:** the engine draws
the heightmap through `FCanvasTriangleItem` with
`TriItemList.MaterialRenderProxy = MID->GetRenderProxy()` and
`BlendMode = SE_BLEND_Opaque` (`:8293-8300`), and that material is
**`MD_Surface`**, not `MD_UI` — confirmed by reading the asset:
`materialDomain: MD_Surface, blendMode: BLEND_Opaque,
shadingModel: MSM_Unlit`. A Surface-domain material rendered through a
canvas tile is exactly the combination that silently produces nothing,
and it is the same class of problem that forced `M_PushHeight` to MD_UI on
the write side. Whether the canvas path compiles the required shader
permutation for a Surface material in an editor RT context is the open
question.

**Cheapest next probes, in order:**
1. Check the editor Output Log for a material/shader warning emitted during
   the export call — the `LogLandscapeBP` "Took N seconds to export
   heightmap to render target" line will bracket it.
2. Try `bInExportHeightIntoRGChannel=True`. It routes to the SAME texture
   sample node (`A > B` and `A == B` are wired identically), so it should
   not change the output — if it DOES, the graph reading is wrong and that
   is worth knowing.
3. Export into an `RTF_RGBA8` target. If that comes back non-black, the
   problem is the fp32 target rather than the draw.

**Do not conclude the terrain is flat.** The landscape renders correctly in
every capture; this is a read-back instrument failure, not a terrain
failure. The distinction is exactly what lesson 9 exists to preserve.


## 2026-08-01 — RULING: push the current heightmap despite D4 (Ryan)
**"push anyway, it's idempotent — record the ruling and go".**

**The finding is not retired by the ruling.** Audit finding D4 stands:
`--expect-change` is unreachable, because the encoding gate and the
orientation-decisiveness gate both run against the LIVE terrain and refuse
at exit 6 before the classification that would consult it. The instrument
is calibrated against the terrain it is about to overwrite, so it is only
well-defined when the push is a no-op.

**Scope of the ruling, exactly:** it covers pushing the heightmap the
landscape was already built from. That push *is* idempotent, both gates
pass on it, and D4's limitation is not engaged. **It does not cover a push
of changed terrain.** The first eroded heightmap (P1) will hit D4 and must
not be forced past it on the strength of this ruling.

Recommended fix shape when that day comes, recorded now so it is not
re-derived: verify a changed push against the **render target** — which is
already read back and compared exactly, texel by texel, before the import —
and demote the export read-back to confirming that the write landed. That
removes the circularity rather than widening a tolerance.

## 2026-08-01 — FINDING: the export encoding is a BYTE SPLIT, read off the graph
Both hypotheses in the audit were wrong, and the disagreement was settled by
reading the engine material's graph in the running editor rather than
inferring from the mirror import path.

`LandscapeExportHeightmapToRenderTarget` renders through
`/Engine/EditorLandscapeResources/Landscape_Heightmap_To_RenderTarget2D`
(`LandscapeEdit.cpp:8187`). Its `MP_EmissiveColor`:

    If
      A      = ScalarParameter "ExportHeightIntoRGChannel"
      B      = (unconnected -> 0)
      A > B  -> TextureSampleParameter2D "Heightmap" .RGB
      A == B -> TextureSampleParameter2D "Heightmap" .RGB
      A < B  -> Add (arithmetic chain)

The flag is passed **False**, so `A == B` is taken and the landscape's
internal heightmap TEXTURE's RGB is passed through **unchanged**. That
texture stores height as a byte split — R the high byte, G the low byte:

    value = round(R * 255) * 256 + round(G * 255)

Note the flag changes nothing at 0 or 1 (both inputs are the same node);
the arithmetic branch is unreachable for a non-negative flag.

**The two wrong answers, both plausible, both silent:**
- `R * 65535` — the natural "it must be normalised" reading (mine).
- `R` as a raw uint16 — inferred from the import side, which genuinely does
  `HeightData.Add((uint16)LinearColor.R)` at `LandscapeEdit.cpp:8138`
  (the auditor's). **Export and import are not symmetric here.**

Either would have used **R alone, which is the top 8 bits**, quantising
65536 height levels to 256 — terracing that looks almost right. The payload
was in fact only returning R; it now returns `[R, G]`, and `decode_export()`
is verified exact against 20000 random values plus the boundaries.


## 2026-08-01 — FINDING: the line-trace read-back is a dead end, whole route
**The push cannot verify heights with line traces, and no amount of fixing
the trace code changes that.** Found by the pre-flight gate refusing on a
dry run — read-only, nothing written.

The trace itself runs fine. **Its result cannot be read from Python.**
Every field of `FHitResult` is a bare `UPROPERTY()` with no
`BlueprintReadOnly` and no `EditAnywhere` (`HitResult.h:100-140`:
`bBlockingHit`, `PhysMaterial`, `HitObjectHandle`, `Component`, … all
bare), and this project already knows what that means — CLAUDE.md's
hard-won list: *"Bare `UPROPERTY()` fields are unreadable from Python —
plan a derivation."* The editor reports them as protected:

    HitResult: Property 'Location' for attribute 'location' on
    'HitResult' is protected and cannot be read

The engine's intended accessor is the break node, and that is not reachable
either: `UGameplayStatics::BreakHitResult` is
`UFUNCTION(BlueprintPure, meta=(NativeBreakFunc, ...))`
(`GameplayStatics.h:1077-1078`), and the Python plugin does not expose
NativeBreakFunc helpers — `GameplayStatics` simply has no
`break_hit_result` attribute. That is lesson 6.1 again: **a header
signature is not the binding signature.**

So all three routes to a hit are closed: the fields are protected, the
break function is unexposed, and `ALandscapeProxy::GetHeightAtLocation`
(`LandscapeProxy.h:1101`) is `LANDSCAPE_API` but not BlueprintCallable.

**The replacement, and it is strictly better than what it replaces:**
`LandscapeExportHeightmapToRenderTarget` IS BlueprintCallable
(`LandscapeProxy.h:1258-1259`). Export the landscape's heights into an
`RTF_RGBA32f` target and read it with
`read_render_target_raw_pixel_area(..., bNormalize=False)` — the exact
mechanism already built and source-verified for the D2 pre-import check.
Advantages over traces, all of them real:
- reads the **heightfield**, not the collision proxy, so the whole
  "collision may be built at a lower mip" worry disappears and with it the
  need to calibrate the instrument at all;
- same read path as D2, already proven correct on `RCM_MinMax`;
- touches no `FHitResult`;
- reads **every** texel rather than 289 sampled points, so the orientation
  search stops being a sampling argument and becomes an exact comparison.

Its encoding needs one source read before use (it renders through
`/Engine/EditorLandscapeResources/Landscape_Heightmap_To_RenderTarget2D`,
so the value mapping is a material's, not a memcpy's) — and the
`InExportHeightIntoRGChannel` flag has the same two-branch shape as the
import side, so the same care applies.

**What the failed dry run DID establish, and it is most of the script:**
the rule 7 gate, the level gate, and identification by property signature
all work — `Landscape_Alpine` matched at res=2017, step=63, 1024
components. Only the height-reading instrument is unusable.

## 2026-08-01 — RULING: hard rule 2 does not bind verification thresholds
**Ryan, explicitly, on the D1 audit finding.** Hard rule 2 says *"every
scene parameter comes from recipe JSON, never hardcoded."* A verification
tolerance is **not a scene parameter** — it is a property of the measuring
instrument, not of the world being measured. It therefore does not fall
under rule 2, and a fixed module-level constant is the correct home for it.

Conditions attached to the ruling, all met:
- It is a **named module-level constant** (`push_heightmap.TOLERANCE_UNITS
  = 4`), never a bare literal at the use site. The use site reads
  `tol = TOLERANCE_UNITS * unit_cm`.
- Its docstring states that the value is **fixed pending a schema bump**,
  and that it becomes a recipe field (`heightmap.push_tolerance_units`)
  when pushes start carrying changed terrain and different biomes want
  different budgets.

**Open item, tied to the schema bump:** `heightmap.push_tolerance_units`
joins the schema-change queue alongside the noisy-snowline field (D-B
above). Both are deferred for the same reason — no second caller needs
them yet — and both should land in the same version bump rather than two.

## 2026-08-01 — "Use Less CPU when in Background" turned OFF (Ryan's call)
Ryan instructed this directly after the capture-stall finding was reported.
`EditorPerformanceSettings.bThrottleCPUWhenNotForeground` set from `true` to
`false` via the unreal-mcp ConfigSettingsToolset, confirmed by read-back.

**IT WAS THE ROOT CAUSE, AND THE FIX IS COMPLETE.** With it off, a capture
run completed all four cameras with the editor **deliberately MINIMIZED** —
the exact condition that had stalled indefinitely twice. Captures no longer
depend on anyone looking at the editor, which is what a background session
needs.

**Scope disclosure, because this one matters.** It wrote to
`C:\Users\ryanb\AppData\Local\UnrealEngine\5.8\Saved\Config\WindowsEditor\
EditorSettings.ini` — **outside both REPO_ROOT and UE_PROJECT_ROOT**, and it
is a MACHINE-GLOBAL editor preference: it affects every UE 5.8 project this
user opens, not just LandscapeLab. Normally conduct rule 1 forbids exactly
this; it was done only because Ryan asked for it by name. Recorded here so
it is not later mistaken for a project-scoped setting.

Cost of leaving it off: the editor now uses full CPU/GPU while in the
background, which on a laptop means battery and heat. To reverse, set it
back to `true` in the same place, or Editor Preferences > Performance >
"Use Less CPU when in Background".

Supersedes the earlier speculation in `docs/lessons.md` §14.7 that this was
"almost certainly" the lever — it was, and the two engine-side alternatives
recorded there (`EditorSetViewportRealtime`, `EditorInvalidateViewports`)
remain wired into `capture.py` but are NOT what fixed it.

## 2026-08-01 — P0 render-target height push: the encoding, read at source
Not a ruling — a **finding**, recorded because it is the expensive part of
Priority 0 and it contradicts the obvious assumption.

`Engine/Source/Runtime/Landscape/Private/LandscapeEdit.cpp:8117-8141`,
`ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget`:

    case RTF_RGBA16f:
    case RTF_RGBA32f:
        ...
        for (const FLinearColor& LinearColor : OutputRTHeightmap)
        {
            if (InImportHeightFromRGChannel) { ... }
            else { HeightData.Add((uint16)LinearColor.R); }   // :8138

**The red channel is the RAW uint16 height, not a normalised 0..1 value.**
The natural assumption — that a float render target carries 0..1 and the
engine scales it into the height range — produces a landscape 65535x too
flat, silently, because a flat landscape is a valid landscape. The drawing
material must therefore emit `value * 65535`, and because `(uint16)` is a C
cast that TRUNCATES, it should emit `value * 65535 + 0.5` to round to
nearest rather than lose up to a full height unit per texel.

Three further constraints from the same function:
- **RTF_RGBA32f, never RTF_RGBA16f.** Both are accepted by the switch,
  which is the trap. fp16's 10-bit mantissa cannot represent consecutive
  integers above 2048; at the 32768 datum the spacing is 32, so a 16f
  target would quantise the terrain to ~1.6 m steps while succeeding. This
  confirms the constraint already recorded in `next-step.md`, now with the
  reason read rather than asserted.
- `InImportHeightFromRGChannel` must be **False**. The True branch does
  `LinearColor.ToFColor(false)` then `(R << 8) | G` — an 8:8 byte split
  that clamps the float channels to 0..255 first.
- **An undersized render target does not error.** `:8113` computes
  `SampleRect = FIntRect(0, 0, Min(1 + MaxX - MinX, RT->SizeX),
  Min(1 + MaxY - MinY, RT->SizeY))`, so a too-small RT imports a
  SUB-RECTANGLE and leaves the rest of the terrain untouched. Silent
  partial write; must be gated before drawing.

Also confirmed: `LandscapeImportHeightmapFromRenderTarget`
(`LandscapeProxy.h:1571-1572`) is the ONLY `BlueprintCallable` height-import
path. `ALandscapeProxy::Import` (`:1418`) is `LANDSCAPE_API` C++ but not
Blueprint-exposed, so it is unreachable from Python. The route-B ruling
stands unchanged.

## 2026-08-01 — OPEN, NEEDS RYAN: two design findings from the P2 brief
Surfaced before implementation per conduct rule 8. **Neither is
implemented.** Both change what the recipe means, not just what it says.

**(D-A) Slope-driven snow retreat.** The brief asks that snow coverage fall
off between ~50 deg and ~62 deg so rock punches through on headwalls and
couloir walls. The design question is *where that lives*, and there are two
materially different answers:
- **(i) In the bake.** `make_layer_weightmap.py` already resolves layers
  first-match-wins from the full-resolution heightmap, where the slope is
  measured honestly. A retreat term is a few lines there, costs nothing at
  runtime, and needs NO schema change — the existing `slope_deg` upper
  bound already expresses "snow stops at N degrees", so this may be pure
  retuning (Snow's upper bound is currently 52.0, which is already inside
  the requested 50-62 range).
- **(ii) In the material, as a new blend semantic.** This is the one that
  changes schema meaning: a *gradual* falloff between two slope values is
  not what first-match-wins v1 describes, and reinterpreting bands as
  weighted blending is exactly the mistake recorded in lessons §2.3.
Recommendation: **(i)**, and probably as retuning rather than new code. It
is reversible, needs no schema change, and keeps the shader dumb.

**(D-B) Noisy snowline — new recipe field.** Perturbing the altitude
threshold with low-frequency world-space noise by ±3-5% of vertical range
so the snowline meanders. This unambiguously needs a new field (something
like `snowline_jitter_frac` plus a wavelength), and therefore a schema
version bump and a ruling on whether the jitter is baked (deterministic,
seeded, visible in the weightmap PNG) or evaluated in the shader (free to
change, but invisible to the CPU coverage numbers that are currently the
project's ground truth).
Recommendation: **bake it**, for the same reason the weights are baked —
the coverage percentages stay measurable on the CPU, and "rendered
coverage equals predicted coverage" survives.

## 2026-08-01 — Capture runs hold a sleep inhibitor (implementer ruling)
**Ruled by the implementer, provisional, cheap to overturn.** Ryan was away;
this was a defect fix with no aesthetic content, so it was not held for
sign-off. What I would have asked: *"may a script make a Windows runtime
request on your behalf?"*

`capture.py` now calls `SetThreadExecutionState(ES_CONTINUOUS |
ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` for the duration of a run,
released in the outer `finally`. **Conduct rule 1 was checked explicitly and
this is inside it:** the call is a per-process, per-thread runtime request. It
writes no registry key, edits no power plan, touches no file, and evaporates
when the process exits. Nothing persists.

`ES_DISPLAY_REQUIRED` is kept deliberately, on the auditor's argument (C3):
the observed failure was Modern Standby (S0 idle, Kernel-Power 507), which is
entered from the display turning off — `ES_SYSTEM_REQUIRED` alone resets the
*system* idle timer, which is the classic S3 path. The display flag is the one
plausibly blocking the transition actually observed. It is recorded here
because it looks redundant and the symptom takes hours to reproduce, so
"tidying it away" would silently un-fix this.

Opt-out is `--allow-sleep`. The inhibitor reports whether it was **held**,
**rejected by Windows**, or **never requested** — a future unexplained gap
must be attributable, and a false "held" would make it un-attributable.

## 2026-08-02 — RULING 1: normals are DX, and an asserted fact was wrong
**The normal convention is the small part. The failure worth recording
is how the wrong fact travelled.**

**The ruling.** Every ambientCG surface in `Free/` uses `_NormalDX`
directly. No green-channel flip anywhere in the pipeline. The `_NormalGL`
maps also ship and are marked UNUSED. `Free/manifest.json` and
`scripts/make_asset_manifest` reflect this.

**How it went wrong.** The Stage 1 brief stated, under a heading of
facts "already established, do not re-derive":

> Every normal map in Free/ is GL convention. Uniform, no exceptions.

That is false — ambientCG ships both conventions for all five surfaces,
and it is DX this pipeline consumes. The listing showed
`Rock026_4K-PNG_NormalDX.png` and `Rock026_4K-PNG_NormalGL.png` side by
side, identical in size, for every set.

**What made it dangerous was the framing, not the error.** "Established,
do not re-derive" is a legitimate instruction — it exists so a session
does not burn its budget re-measuring settled things, and this project
uses it well. But it converts a claim into something that is not
supposed to be checked, and a claim that is not supposed to be checked
is one that cannot be corrected by the normal working of the process.
Had the file listing not made the contradiction unmissable, a
green-channel flip would have been designed in to fix an inversion that
was never there, and every lit surface would have been subtly wrong in a
way that reads as a lighting problem.

**The rule this leaves.** An instruction not to RE-DERIVE a fact is not
an instruction to ignore evidence that contradicts it. Re-deriving means
spending work to recompute something; noticing that the artefacts on
disk disagree with the premise costs nothing and must still be reported.
Where the two conflict, say so and stop — do not silently adopt either
one. Ryan reversed this within one exchange because the observation was
reported rather than smoothed over; that is the loop working, and it
only works if the observation gets made.

Related: §2.1 of `docs/lessons.md` is about trusting a NAME instead of
reading the source. This is the same failure one level up — trusting an
ASSERTION instead of looking at the directory.

### Same class, two more instances the same session (2026-08-02)

**Fact 2 — "materials per mesh: bark, trunk_x, twig, dead_branches".**
There are SIX materials, not four. `trunk_x` is three distinct per-LOD
materials: `trunk_a` on `a_LOD0`, `trunk_b` on `b`, `trunk_c` on `c`.
Read out of the FBX; the wildcard in the brief concealed a one-to-many.
Consequence had it stood: an import script written for four materials
would have silently bound the wrong trunk, or none, on two of three
LODs.

**Fact 3 — "`_trash` contains `fir_tree_01_4k.blend`".** It does not,
and no such file exists anywhere on the machine. `_trash/free-cleanup-
20260802-004555/` holds five Blends — `grass_medium_01`,
`grass_medium_02`, `jacaranda_tree`, `leafy_grass`,
`othonna_cerarioides` — and no fir. The only fir source is
`~/Downloads/fir_tree_01_4k.fbx.zip`, whose nine entries are one FBX
and eight PNGs, extensions `['fbx', 'png']`, **no `.blend`**. Poly Haven
offers a format choice at download and this asset was taken as FBX.

That third one matters beyond the file. The Step A question was framed
as *"textures the FBX export dropped"*, which presumes a richer source
that was reduced. There was no such source: the FBX package IS the
whole delivery, and the eight PNGs are everything the vendor ships.
`dead_branches` and `trunk_c` are not missing their maps — **they never
had any.** Answering the question as asked would have produced "no
textures found in the Blend", which is true, useless, and would have
implied the maps exist somewhere.

**The pattern across all three.** Each was stated as settled, each was
wrong in a way that a look at the artefacts contradicted immediately,
and each would have propagated into code had it not been checked. None
of them was a hard thing to verify. The cost of checking a stated fact
against the directory is seconds; the cost of not checking is a wrong
premise compiled into a script.

**Standing rule, applying to all three:** an instruction not to
RE-DERIVE a fact is not an instruction to ignore evidence that
contradicts it. Where a stated premise and the artefacts on disk
disagree, report the disagreement and stop. Do not silently adopt
either.

## 2026-08-02 — RULING: full autonomy and design authority (Ryan)
**Ryan's words, verbatim, carried per conduct rule 9:**

> "update the .md and remove wave all restrictions consider this my
> official sign off allowing you full autonomy and design authority
> including destructive paths."

**Standing, not per-session.** What it retires:

- **Approval gates, all of them.** No stopping to ask before
  implementing, committing, or running. Design decisions — how the world
  looks, what a gate refuses, what a schema means — are mine.
- **Conduct rule 8** (design-level BLOCKs need explicit sign-off before
  implementation). Retired. A design finding is now resolved by
  resolving it and recording the ruling here.
- **The mandatory audit gate**, including on destructive paths.
- **Destructive execution is cleared**: `delete_stray_landscape.py`,
  `set_landscape_scale.py`, `save_level.py --save`, actor deletion,
  level saves.
- **S1 option (iii)** is signed off by this and implemented.

**What was deliberately NOT removed, and the reasoning, because a future
session will otherwise read the grant as "delete the safety code".**

The old rule list mixed two different things under one heading. Some
were *approval gates* — they existed because Ryan had to be asked. Those
are gone; asking was the whole content.

The rest are *error detection*: stay inside the repo, no recursive
deletes, commit before anything irreversible, don't edit .uasset on
disk, stop after two consecutive live-editor failures, verify the
connected editor is the right project, dry-run destructive work,
identify by signature not by label, carry full text in reports, and say
plainly when something was not done or not verified.

**Not one of those requires Ryan.** They catch MY mistakes. Deleting
them would not have granted an ounce of additional autonomy — it would
only have removed what makes autonomy survivable, and it is precisely
under full autonomy that they matter most, because with the audit gate
gone there is nothing else in the path. The conduct-rule 7 identity
check is the sharpest example: autonomy over THIS project was never
authority over whatever other editor happens to hold the port.

Ryan can retire any of these too by saying so. This entry exists so that
"remove all restrictions" is not silently read as having already done
it.

**The cost of the grant, stated plainly rather than glossed.**
`docs/lessons.md` §1.1 lists defects the independent review caught
before first execution — an enum removed in 5.8 that would have crashed
every run, a residency gate that would have passed exactly when loading
failed, a landscape move that would have torn parent from components and
saved it, a verifier that would have PASSed that torn state, and a
"refusal" that mutated and saved before printing REFUSE. None was found
by the author. Throughput is the thing bought; that assurance is the
thing spent. The lessons loop is now the only mechanism that stops a
defect class recurring, which makes it more load-bearing, not less.

## 2026-08-02 — S1 RESEARCH COMPLETE: the premise is FALSE, source read
**This is option (i) of the S1 block below, carried out. It is a LOOKUP,
not an implementation: no code addressing S1 has been written or
committed, and the block is not treated as retired. Conduct rule 8 says
sign-off retires a block, not evidence — but the evidence changes what
there is to sign off on, because the thing S1 feared does not happen.**

**`save_packages()` DOES remove OFPA packages emptied by an actor
deletion.** Chain read at source lines in the 5.8 install
(`C:\Program Files\Epic Games\UE_5.8`), every hop verified:

1. `EditorLoadingAndSavingUtils.save_packages()` →
   `UEditorLoadingAndSavingUtils::SavePackages`,
   **`FileHelpers.cpp:6019`**
2. → `InternalCheckoutAndSavePackages(Packages)`, **`:5960`**
3. → the two-argument overload, **`:5967`**
4. → `InternalPromptForCheckoutAndSave(...)`, **`:5945`**
5. → **`:4520-4524`**, and this is the line that answers it:

       // if the package we are saving is considered empty, mark it for
       // deletion on disk instead
       if (UPackage::IsEmptyPackage(Package))
       {
           PackagesToClean.Add(Package);
       }
       else
       {
           PackagesToSave.Add(Package);
       }

6. → `ObjectTools::CleanupAfterSuccessfulDelete(PackagesToClean, true)`,
   **`:4536`**
7. → `IFileManager::Get().Delete(*PackageFilename)`,
   **`ObjectTools.cpp:2501` +~170**. With source control DISABLED — which
   is this project, it uses git — the unconditional branch is taken.

**Two corrections to the finding's own reasoning, recorded because the
finding was careful and still slightly wrong:**

- S1 said `save_packages()` "routes to
  `FEditorFileUtils::PromptForCheckoutAndSave`". It does not. It routes
  to `InternalPromptForCheckoutAndSave`, the shared internal that
  `PromptForCheckoutAndSave` also calls (`:4917`). The distinction does
  not change the outcome — the empty-package handling lives in the
  internal, so BOTH paths delete — but "I traced it to the public
  function" was not the same as "I traced it to the code that acts".
  Section 6.3 exactly: finding the line is half the work, proving your
  call reaches it is the other half.
- Option (i) proposed doing this lookup "via SemanticSearchToolset
  against the running editor". **That toolset cannot answer it.**
  `list_toolsets` describes it as *"the SemanticSearch plugin's hybrid
  vector + BM25 ASSET search"* — it searches project assets, not engine
  C++. The lookup was done by reading the installed engine source
  instead. A method named in a plan is itself an assumption.

**What SURVIVES of S1, downgraded from BLOCK to FIX.** The second half
stands on its own: `still_dirty` is empty whether a package was
correctly deleted or silently not written, so the script's verification
is blind either way. The engine doing the right thing is not the same as
the script being able to tell. That is option (iii) — a positive on-disk
existence check per owned package, so a deletion is verified as a
MISSING FILE rather than as an absent dirty flag.

**NOT IMPLEMENTED, awaiting Ryan.** It is now a small hardening with no
design content, but it is still code addressing a finding raised as a
BLOCK, so it waits. Option (ii) — splitting the save — is moot and
should not be built.

## 2026-08-01 — OPEN, NEEDS RYAN: how save_level.py persists a DELETION
**Audit finding S1, BLOCK, returned unfixed under conduct rule 8. No
implementation, commit, or re-audit of a fix may proceed before sign-off.
`scripts/save_level.py` has NOT been run with `--save`; its dry run is
unaffected and was run.**

Full text of the problem, carried inline per conduct rule 9:

`save_level.py` saves an EXPLICIT list of packages via
`EditorLoadingAndSavingUtils.save_packages()`, chosen precisely so that
"saving a level saves every dirty external package" stops being true. That
choice has a hole. `save_packages()` routes to
`FEditorFileUtils::PromptForCheckoutAndSave`. It is **not** the path this repo
has already read and recorded in `scripts/delete_stray_landscape.py:66-68,95`
as the one that removes deleted OFPA actor packages: *"save_current_level ->
FEditorFileUtils::SaveLevel -> SaveWorld -> SaveExternalPackages saves EVERY
dirty external actor package of the level (FileHelpers.cpp:835, :1220 in UE
5.8)"* and *"Deleted OFPA actor packages are removed on the final save through
the engine's own checkout+save path."*

Whether `PromptForCheckoutAndSave` deletes the *files* of external packages
emptied by an actor deletion has not been read at a source line and has not
been proven against the running editor. Under the 5.8 RESOLUTION PROTOCOL the
lookup wins, and no lookup has been done.

**Why this is a BLOCK and not a FIX: the script's own verification cannot
detect the failure.** A package emptied and correctly deleted leaves the dirty
set. A package emptied and silently *not* written also leaves the dirty set.
`still_dirty` is empty either way, so the run prints success in both cases and
the deleted actors return on the next reload. That is the silent-wrong class
this project pays most for.

Options, content carried rather than indexed:
- **(i)** Read `PromptForCheckoutAndSave`'s empty-package handling in 5.8
  (`FileHelpers.cpp`, `InternalSavePackages`, `UPackage::IsEmptyPackage`) via
  SemanticSearchToolset against the running editor. If it does delete, add a
  positive on-disk check so the verification stops being blind.
- **(ii)** Split the save: `LevelEditorSubsystem.save_current_level` for the
  world and its external packages — accepting that this saves every dirty
  external package of that level, which the allow-list can then no longer
  restrict — and keep `save_packages` for the named content assets only.
- **(iii)** Keep `save_packages` and add an explicit post-save on-disk
  existence check for every owned package, so a deletion is verified as a
  *missing file* rather than as an absent dirty flag.

**Practical urgency is currently LOW and this is why:** the dry run found zero
dirty packages, so there is nothing this script would have saved today. The
scene is already consistent on disk. The ruling is needed before the next time
an actor is deleted in the editor, not before the next capture.

## 2026-07-27 — Repo location
Repo lives at `C:\Users\ryanb\UE5LandscapePipeline`. Not the home directory:
`git init` there would place version control over `.claude`, `AppData`, and
the unrelated Unity projects (`GameAutomationLab`, `SanctuaryHD`).

## 2026-07-27 — Engine version
UE 5.8, installed at `C:\Program Files\Epic Games\UE_5.8`. Confirmed from
disk, not assumed. Version-specific API calls target 5.8; anything gated on
an older API needs an explicit guard (CLAUDE.md audit criterion 4).

## 2026-07-27 — UE project directory
`LandscapeLab`, to be created inside the repo at
`C:\Users\ryanb\UE5LandscapePipeline\LandscapeLab` (blank project, no starter
content). Until the `.uproject` exists, UE_PROJECT_ROOT is *pending*: conduct
rule 1 scope is REPO_ROOT only and nothing executes against a live editor.

Consequence of nesting the project inside the repo: `LandscapeLab/Content/`
`.uasset` and `.umap` files become tracked git objects. Generated dirs
(DerivedDataCache, Intermediate, Saved, Binaries) are gitignored, but content
binaries are not — they are the project. Worth revisiting git-lfs before the
Content dir grows past a few hundred MB.

## 2026-07-27 — UE_PROJECT_ROOT set (pending resolved)
`LandscapeLab.uproject` confirmed on disk at
`C:\Users\ryanb\UE5LandscapePipeline\LandscapeLab\LandscapeLab.uproject`
(blank project, no starter content; Config/, Content/, DerivedDataCache/,
Intermediate/, Saved/ present). UE_PROJECT_ROOT in CLAUDE.md changed from
*pending* to that absolute path.

Consequences: conduct rule 1 scope widens from REPO_ROOT alone to REPO_ROOT
plus UE_PROJECT_ROOT, and live-editor execution is unlocked. Unlocked is not
unguarded — every remote execution still passes the conduct rule 7 identity
check, and `scripts/bootstrap.py` refuses on no match, ambiguous match, a
malformed reported path, or disagreement between discovery data and the live
editor.

Editor configuration reported at handover: Python Editor Script Plugin,
PCG Python Interop, and Remote Execution all enabled, default multicast
settings (239.0.0.1:6766).

## 2026-07-27 — First live editor contact (bootstrap.py)
Logged here per hard rule 4's non-scene-change clause: `scripts/bootstrap.py`
executed against the live editor, exit 0, no scene mutation.

Result: one node discovered (`60F2C7454A24CA68CA5EE6ABA60BC6DF`, user `ryanb`,
machine `RYANN`), pong `project_root` matched UE_PROJECT_ROOT, and the
post-selection confirmation probe agreed. Engine reported
`5.8.0-55116800+++UE5+Release-5.8` at `C:/Program Files/Epic Games/UE_5.8/
Engine/` — matches the 5.8 pin.

Worth recording: the editor reports its project dir as
`C:/Users/ryanb/UE5LandscapePipeline/LandscapeLab/` — forward slashes *and* a
trailing separator. `_norm` collapses that to the Windows-native form before
comparison. Without that normalisation the rule 7 gate would have refused a
legitimate match (exit 3), so any future path comparison against editor-
reported values must go through the same function.

## 2026-08-01 (overnight) — Layer masks: correctness is now gated on the CPU
Not a design choice so much as a correction, recorded because it changes what
the pipeline guarantees.

**What was wrong.** Snow's and Grass's slope masks were identically zero over
the whole terrain. The material compiled clean and rendered for several
sessions while ~92% of the landscape was painted by the flat background
constant. Full mechanism in `docs/lessons.md` 12.9.

**What is now guaranteed.** `make_landscape_material.layer_bands()` runs
`_assert_band_invariant`, which evaluates the SAME ramp arithmetic the shader
will, on the CPU, and raises unless every band's mask reads ~1 at its own
centre and ~0 well outside. It runs before any editor contact — no shader
compile, no capture, no editor at all.

**Ruling on where that check belongs:** in `layer_bands()`, not in the
payload. A shader-side check could only report after the graph was already
built and the old one destroyed, and the whole point is to refuse before
touching live state. The cost is that `_cpu_ramp` must stay identical to the
payload's `_ramp` — a duplication the repo normally forbids (lesson 1.9).
Accepted deliberately, with both copies commented as mirrors, because the
alternative is a correctness gate that can only fire after the damage. **If
they ever drift, the gate silently stops testing the shipped arithmetic** —
that is the failure mode to watch for.

**Also ruled: no `.py` filename may appear in a remote-exec payload.**
`PythonScriptPlugin.cpp:813-830` scans the entire command for `.py` — code,
comments and string literals alike — and treats the payload as a FILE PATH if
found. `_guard_payload` refuses one and quotes the offending line. This is a
transport constraint, not a style preference: naming a script in an error
message silently breaks the script that carries it.

## 2026-08-01 (overnight) — RULINGS MADE UNDER DELEGATED AUTHORITY
Ryan delegated design rulings before going to bed ("audit yourself as you see
fit", "requires no inputs"). Every ruling in this block was therefore made by
the implementer, which is the inversion conduct rule 8 normally forbids. They
are recorded here in full **so they can be overturned cheaply**, and each one
states what I would have asked. Treat them as provisional.

**What I did NOT take from the delegation:** the safety gates. Fail-closed
refusals, identity checks, commit-before-destructive and read-back
verification all stayed on. Unsupervised work needs more verification, not
less — there is nobody to notice a silently-wrong result — and this session
alone had the exactly-one gate catch a duplicate lighting rig, the level gate
catch the wrong world, and the audit gate catch a destructive graph clear
placed before a step that could fail.

### B1 — apply_lighting.py gets a level gate at exit 7
**Ruled: adopt, exit 7.** `recipes/schema.md` is normative that every
editor-touching script gates on `landscape.level_path`, and this script is the
last one that did not. Exit **7**, matching the `verify_landscape.py`
precedent Ryan approved earlier today, deliberately not 6 (which this script
now uses for the census refusal, and which `make_landscape_material.py` uses
for its own level gate — exit codes are per-script contracts here).

### B2 — the lighting census fails OPEN under World Partition; adopt "refuse on partial"
**Ruled: option (a), refuse on partial coverage.** The census uses
`get_all_actors_of_class`, which returns LOADED actors only, so a stray in an
unloaded cell reads as "foreign 0" — the gate inverts in exactly the direction
that reproduces the incident it was written for. Option (c), report-only, was
what the auditor left in place; it is honest but it still exits 0 on an
unknown. Option (b), forcing residency, mutates streaming state as a side
effect of a *reporting* pass, which is the wrong shape for a gate.

So: the payload additionally counts World Partition actor descriptors for the
four governed classes (read-only, the pattern already proven in `capture.py`
and `delete_stray_landscape.py`) and refuses when the on-disk count exceeds
what the census could see. **One-directional by design** — actors spawned this
run have no descriptor yet, so only `on_disk > loaded` is a refusal.

### F3 — lighting actors get `is_spatially_loaded = False`
**Ruled: adopt.** This is almost certainly the mechanical origin of the
duplicate rig, and it is a hard rule 3 (idempotency) break across editor
sessions: an actor spawned spatially-loaded can be unloaded after a restart,
`_find_or_spawn` (loaded actors only) then fails to find it, and spawns a
SECOND one. `capture.py` already does exactly this for its cameras, for
exactly this reason, so there is precedent in-repo. Lighting is global to the
level and has no business being spatially streamed.

### F1 — PostProcessVolume joins the census, but only when UNBOUND
**Ruled: adopt, narrowly.** The auditor is right that bounded volumes blending
by priority are legitimate and would cause constant false refusals, and right
that a second UNBOUND volume overrides exposure exactly as a second fog
overrides fog. Since this script sets `unbound = True` and leaves priority at
0, a foreign unbound volume at priority >= 0 wins non-deterministically. Only
`unbound == True` volumes count as strays.

### F2 — `--allow-foreign` stays a CLI flag, NOT a recipe key
**Ruled: reject the recipe change, for now.** The auditor is correct in
principle — whether a scene legitimately holds a second directional light is a
scene fact, and hard rule 2 says scene facts live in the recipe. But adding
`lighting.allow_foreign` is a schema change to encode an *exception*, and no
recipe needs the exception today. Encoding a hypothetical exception into the
schema is the kind of speculative debt the `tiling_m`-reserved-for-two-versions
episode already taught us to avoid. **Trigger to revisit: the first recipe that
legitimately needs a second light.**

### F4 — `sky.type: "hdri"` stays validated-but-unimplemented, now loudly
**Ruled: refuse rather than implement.** Implementing HDRI skies overnight is
a feature, not a fix, and no recipe uses it. But silently accepting a value and
ignoring it breaks hard rule 2 without saying so. `apply_lighting.py` now
refuses `hdri` outright with a message naming this ruling, so the failure is
loud and the schema stops promising something the pipeline does not do.

## 2026-08-01 — SPIKE: Slate automation of the New Landscape dialog WORKS (not adopted)
Spike only, no commitment. **The documented manual procedure in
`docs/next-step.md` stands unchanged.** Run on the throwaway landscape in the
unsaved `/Temp/Untitled_1`, never on `Landscape_Alpine`. Nothing was created,
nothing was saved.

**This overturns a source-traced framing, which is why it is recorded.**
`docs/next-step.md` said the import step is manual *"and always will be until
route A"*. The engine fact behind that is still true — UE 5.8 exposes no
script-callable landscape import from a file — but the conclusion that a C++
plugin is the only way out was wrong, because `SlateInspectorToolset` did not
exist when the fork was ruled. Route C is now a real third option.

**What worked, end to end, driven entirely over MCP:**
- Editor mode switch Selection → Landscape via the toolbar combobox. Options
  read from the live dropdown before clicking, not guessed: `Selection`,
  `Landscape`, `Foliage`, `Mesh Paint`, `Modeling`, `Fracture`,
  `Brush Editing`, `Animation`, `PCG`.
- Tab switch Sculpt → **Manage**, then tool switch Select → **Import** → **New**.
- The **New Landscape panel is fully discoverable**, with every field the
  manual procedure types: `Create New` / `Import from File` toggle, World
  Partition Grid Size, Region Size, Material, Location, Rotation, **Scale**,
  **Section Size**, **Sections Per Component**, **Number of Components**,
  **Overall Resolution**, **Total Components**, and the `Fill World` /
  `Fit To Data` / `Create` / `Import` buttons.
- **Values are readable, not just the labels** — `Location 0.0/0.0/0.0`,
  `Scale 100.0/100.0/100.0`, `Number of Components 8x8`,
  `Overall Resolution 505x505`.
- **A write landed and was PROVEN to land.** `Sections Per Component` was set
  from `1x1 Section` to `2x2 Sections` — the dropdown options confirming the
  engine-source finding that the dialog renders the linear count {1,2} as NxN
  labels — and **`Overall Resolution` changed 505 -> 1009**, exactly
  `63 x 2 x 8 + 1`. The proof is the *derived* field, not the setter's return
  value (lesson 6.3: prove the call reaches the code).

**Why this is strategically interesting.** The whole cost of route B is lesson
6.6: the dialog silently disagrees with what you typed, and it did so on both
imports. Route C can *read the dialog's own state back before pressing Create*.
That converts a blind hand-entry into a verified one, and would catch the
error at the dialog instead of after the landscape exists.

**What was NOT proven, and must be before adoption:**
- **Typing into numeric fields.** `Scale` and `Number of Components` are
  `SNumericEntryBox` widgets exposed with role `slider`. Reading them works;
  `Type` into them was never attempted.
- **The file-browse dialog** behind `Import from File`. If it resolves to an OS
  modal rather than a Slate window, Slate automation cannot reach it at all.
  This is the single most likely blocker.
- **Pressing `Create`.** Deliberately not done.

**Two real hazards found, both of which would bite an implementer:**
1. **The accessibility tree lags the UI, badly.** After clicking a tab or tool,
   two consecutive snapshots returned an *empty* panel while a screenshot
   showed it fully rendered with nine tool buttons. An automation that treats
   an empty snapshot as "the control is absent" will misfire. Screenshots were
   the reliable readback throughout.
2. **Refs are invalidated by a details-panel rebuild.** After the combobox
   write, cached refs for the whole subtree — including tabs that had not
   visibly changed — went dead, and `Snapshot` returned an empty tree until the
   root observer was re-registered. The toolset's own docs say "Refs discovered
   by a previous Snapshot remain usable"; **that is not true across a rebuild.**

**Ruling deferred to Ryan.** Adoption would mean a new script owning a UI
automation surface with no audit gate on MCP calls, replacing a procedure whose
failure mode is already known and already caught. Not a decision to make inside
a spike.

## 2026-08-01 — verify_landscape still catches the manual-path errors (re-confirmed)
Recorded because the claim "it has caught a wrong value on every single import
so far" was load-bearing in the handoff and had never been re-tested after the
D3 derivation landed.

Fed `verify_landscape.compare` a synthetic live reading of exactly the failure
the dialog produces — `sections_per_component` 2 instead of 1 (component
spacing 126 rather than 63) with `Scale` left at the dialog default 100 — and
it reported eleven mismatches, including verbatim:

- `sections per component: recipe expects 1, DERIVED 2 (from measured component spacing 126)`
- `section size (subsection quads): recipe expects 63, DERIVED 126 (from measured component spacing 126)`
- `quads per component: recipe expects 63, DERIVED 126 (from measured component spacing 126)`
- `total components: recipe expects 1024, live is 256`
- `scale X: recipe expects 400.0, live is 100.0` (and Y, and Z)

The correct-geometry control — spacing 63, scale 400/400/500 — passed clean, so
this is not a checker that fails on everything. **The tripwire is intact and
the D3 derivation did not weaken it.**

## 2026-08-01 — D3 (bare-UPROPERTY geometry reads): CLOSED, no action needed
Ruled. **D3 was already signed off as option (a) on 2026-07-28 and is
implemented; the "still open" framing carried in the handoff was stale.**

The premise of the open question was that `verify_landscape.py` "exits 6
permanently" because UE 5.8's `get_editor_property` refuses bare `UPROPERTY()`
fields (`num_subsections`, `subsection_size_quads`, `component_size_quads`).
It does not. `scripts/verify_landscape.py:399-440` implements
`check_or_derive`, which falls back to the measured-component-spacing
derivation when a property read returns `None`, records the row in
`derived[]`, and routes a *disagreeing* derivation to `mismatches` rather
than to a pass. The ruling's stated condition is met at
`verify_landscape.py:601-607`: `*** DERIVED — not read from the engine ***`
prints on **every** outcome, before the verdict.

**The one thing worth checking was whether the derivation is circular**, since
it divides measured spacing by the *recipe's* value for the other term —
`section_size = spacing // spc_recipe` and `spc = spacing // section_size_recipe`.
If a recipe could declare an illegal factorisation, both rows would pass by
construction. It cannot: the shared `derive_spec` validates against
`LEGAL_SECTION_SIZES` and `LEGAL_SPC` (`landscape_spec.py:62-63, 117-122`)
before the spec exists, so the uniqueness proof's premise is enforced
upstream. The derivation is sound.

**No verifier fix was required.** The standing instruction was to fix the
verifier rather than work around a dead tripwire if D3 left it unpassable —
it does not, so nothing was changed. Retirement condition unchanged: when a
route-A C++ plugin exposes a direct geometry accessor, the `DERIVED` labels go.

## 2026-08-01 — R2 (feather widths): NORMATIVE at 12 deg / 6%, instrument fixed
Ruled, and implemented. `blend_sharpness` is 0–1 with no intrinsic unit; the
debug material had invented its own constants. As of schema v1.2 the width is
normative and recorded in `recipes/schema.md`:

    slope feather (deg) = (1 - blend_sharpness) * 12
    height feather (m)  = (1 - blend_sharpness) * 0.06 * z_scale_m

**Why these numbers:** 12 degrees is roughly the width over which snow and
rock interfinger on a real mountainside; 6% of vertical range is a plausible
snowline transition band. Defensible defaults, not physics — and now written
down, which was the actual complaint.

**Why not recipe keys.** Explicit `feather_deg`/`feather_m` per layer was the
alternative. Rejected: it adds two keys per layer to express what one already
expresses, and `blend_sharpness` is the more useful authoring control (one
normalised knob). If a biome ever needs a feather that this formula cannot
express, that is the trigger to revisit — the same "a second recipe that
fights this" test used for the layer-transition ruling.

**Two defects found while ruling it, both fixed:**
1. **The instrument disagreed with the instrument's subject.**
   `make_layer_debug_material.py` used 10 deg / 5% while
   `make_landscape_material.py` used 12 deg / 6% — so the diagnostic rendered
   every band ~20% narrower than the shipping material, and its coverage
   readings were not comparable to anything. It now **imports** the constants
   from `make_landscape_material` rather than copying them. Verified equal
   after the change: Snow 11520.0 cm, Rock 4608.0 cm, Grass 7680.0 cm in both.
2. **A false citation.** `make_landscape_material.py:19` said "This script
   uses, and schema.md records:" — schema.md recorded no such thing; its only
   mention of `blend_sharpness` was "0–1; 0 is a wide feather, 1 a hard edge".
   That is lesson 2.5 recurring verbatim ("before writing 'as recorded in X',
   open X"). The claim is now true because schema.md was made to say it.

Consequence for the record: `docs/changelog.md`'s caveat that rendered
coverage is not comparable to the numpy prediction "because feather widths in
the debug material are instrument constants (audit finding R2, still open)"
is now resolved for the width mismatch.

## 2026-08-01 — Textures MULTIPLY base_color; two scales are mandatory
Signed off as part of the textures milestone. Schema v1.2. Full normative text
in `recipes/schema.md` under "v1.2 — textures".

**The design.** A layer's texture is not an albedo map. It is a linear
multiplicative variation map with a per-channel mean of exactly 0.5:

    final_albedo = base_color * 4 * detail_sample.rgb * macro_sample.rgb

so the mean product is 1.0 and **a fully-mipped layer renders exactly its
recipe `base_color`**.

**Why not put the albedo in the texture**, which is what "textured layer"
normally means: colour would move out of the recipe and into a PNG. Hard rule
2 says every scene parameter comes from the recipe; the art-directed albedos
signed off on 2026-07-31 (Snow `[0.86,0.89,0.94]`, Rock `[0.22,0.22,0.24]`,
Grass `[0.19,0.28,0.12]`) would become unreviewable binary data, and retuning
snow's colour would mean regenerating an asset instead of editing one line.
Keeping the texture multiplicative preserves the whole existing review loop.

The `4` is an **encoding constant** of the texture format, not a scene
parameter — the exact analogue of the heightmap's 32768 datum. An unsigned
8-bit texture cannot store a multiplier centred on 1.0.

**Two scales, and this is arithmetic rather than taste.** At this recipe's
cameras the nearest terrain is ~1.1 km and most of frame is 3–14 km. At 1920 px
and 55 deg horizontal FOV one pixel subtends 1.5 m at 3 km and 7.2 m at 14 km,
so the recipe's 4 m `tiling_m` spans **0.55–2.7 pixels** across the wide shot:
it mips to its mean and contributes nothing. Measured, not guessed. A ~300 m
repeat spans 41–200 px. Hence `macro_tiling_m`, required to exceed `tiling_m`,
with the validator refusing the inversion because inverted scales would look
exactly like "textures didn't work". Both scales sample the same asset, so the
macro scale costs no extra texture.

**Choices made and why:**
- **1024x1024, 8-bit RGB, three assets** at `/Game/Textures/T_Alpine_<Layer>`.
  1024 serves both scales; at macro 300 m it is 3.4 px/m, and the detail scale
  is mip-limited by distance long before resolution matters.
- **TC_BC7, not the DXT1 default.** Multiplier maps band worse than albedo,
  and BC7 costs ~1 MB per texture with mips — nothing, for three textures,
  even on the integrated GPU.
- **srgb=False, SAMPLERTYPE_LINEAR_COLOR.** These are linear multipliers. This
  is the highest-risk setting in the whole feature: leaving srgb on decodes
  byte 128 as 0.216 instead of 0.502 and darkens every textured layer by ~57%
  with a clean compile and nothing visibly wrong in the asset. Hence the
  read-back gate in `import_layer_textures.py` (exit 5).
- **SSM_Wrap_WorldGroupSettings** shared samplers, so six samples consume no
  sampler slots and wrapping does not depend on each texture asset's own
  address settings.
- **Generator parameters stay out of the recipe** — seed, octaves, contrast,
  per-layer shaping — under the standing 2026-07-28 source-authoring ruling.
  They author the source asset the recipe points at, exactly as Gaea's `.tor`
  settings would. The recipe owns *which* file and *how it repeats*.

**Deferred deliberately: normal maps.** Albedo variation is the change that
breaks up flat shading at this viewing distance; normals would triple the
asset count and add a tangent-space correctness surface for a benefit that is
mostly sub-kilometre. Trigger to revisit: a ground-level or foliage camera.

## 2026-08-01 — Level identity is a recipe parameter (`landscape.level_path`)
Signed off, prompted by an incident the same day. Schema v1.2, **required**.

**What happened.** Conduct rule 7 verified the connected editor's *project* —
correctly, it matched `UE_PROJECT_ROOT`. But the editor had an unsaved
`/Temp/Untitled_1` open, a New Level → Open World instance, not `/Game/Alpine`.
Every scene-facing script was therefore reading **the wrong world inside the
right project**. `landscape_inventory.py` showed it plainly once run — actor
packages read `/Temp/Untitled_1_InstanceOf_/Engine/__ExternalActors__/Maps/
Templates/OpenWorld/…` and the landscape was labelled `Landscape` at scale
100 — but nothing was *checking*, so `make_landscape_material.py` built and
compiled clean and reported success.

**What stopped it was luck.** The assignment refused only because the
exactly-one-label gate found 0 actors named `Landscape_Alpine`. That gate
exists to prevent binding when labels collide; it was never designed to catch
a wrong level, and it caught this one only because the stray landscape still
carried the dialog's default name. Rename it and the recipe's material binds
to a stranger's terrain, with every gate green.

**The ruling.** Which world a recipe applies to is a scene parameter, so under
hard rule 2 it belongs in the recipe. `landscape.level_path` is required, must
start with `/Game/`, and `verify_landscape.gate_level` refuses unless the live
editor's current level package matches it. Fails closed: an unreadable level,
an absent world, or a probe returning nothing are all refusals — "I could not
determine the level" is never "the level is correct".

Wired into `make_landscape_material.py` (exit 6) and `capture.py` (exit 6),
both **before** their residency gates, because residency asks "is all of this
world loaded", which answers nothing if it is the wrong world.

**Amended 2026-08-01 (exit-code ruling):** a third call site now exists —
`verify_landscape.py` gates on it too, at **exit 7**. It needed a distinct
code because `6` in that script already means "INCOMPLETE — one or more fields
could not be read back", and "I read the wrong world" is not "I could not read
a field"; collapsing them would have made a wrong-level run indistinguishable
from the bare-`UPROPERTY` refusal the D3 ruling depends on. Ryan approved the
new code. Exit codes remain a per-script contract in this repo, not a shared
table, which is why the numbers deliberately do not line up across scripts. A capture of
the wrong level is the purest form of evidence that lies: a real, correct,
well-exposed photograph of somewhere else.

Verified against the live failure rather than a hypothetical — with
`/Temp/Untitled_1` still open, both scripts refuse with
`recipe targets '/Game/Alpine' but the editor has '/Temp/Untitled_1' open`.

**The unsaved level was NOT discarded.** Opening `/Game/Alpine` would destroy
it, it is not this project's work to destroy, and git cannot restore an
unsaved level. Left for Ryan to resolve. Its landscape shows component step
126 = 63x2 sections against the recipe's 63x1x32 — the same 2017 resolution by
a different factorisation, which is the signature of an in-progress manual
import that hit the dialog defect recorded in lesson 6.6.

## 2026-08-01 — Gaea is blocked by LICENSING, not by a broken install
Supersedes the "Gaea was misbehaving" framing below and the
"`Gaea.BuildManager.dll` is **missing**" framing in `docs/next-step.md` and
`CLAUDE.md`. Both were wrong in the same way: they described a symptom as an
installation defect, which invites a fix attempt that cannot work.

**Confirmed 2026-08-01, Help > About: Gaea 2.3.0.1, licence type Community.**

**Two independent blocks, either one sufficient.**

1. **Headless CLI build is a paid feature.** `Gaea.BuildManager.dll` is absent
   *by design under this licence*, not lost. `Gaea.BuildManager.exe` is only a
   .NET apphost stub and fails with **"The application to execute does not
   exist"** — the launcher is shipped, the payload is not.
2. **Community export caps at 1024x1024.** The landscape is **2017**. So even
   the manual GUI route — the fallback the old framing assumed was still
   open — cannot feed the pipeline at the current resolution.

The second is the larger of the two: fixing headless build alone would not
unblock anything, because the export ceiling would still be hit.

**What was ruled out, so it is not re-attempted.**
- **Two full reinstalls** of the current version from the offline installer.
  The DLL did not return. A third will not either.
- **Anti-virus quarantine.** Windows Defender protection history shows
  **zero detections**. Not an AV false positive.

**Consequence — no pipeline change.** `terrain/alpine_heightmap.png` stays
synthetic, produced by `scripts/make_alpine_terrain.py`, which already
satisfies the export contract at 2017: same path, same `png16` format, same
legal-N+1 constraint. Nothing downstream knows or cares which produced it, so
this costs the pipeline nothing — it costs terrain *quality*, which is a
separate matter from terrain *plumbing*.

**Revisit triggers — only these two.**
- **A paid Gaea edition is purchased.** Both blocks lift together.
- **The landscape drops to 1009.** A 1024 Community export crops to 1009
  (`63 x 2 x 8 + 1 = 1009`, and 1009 <= 1024), which is a legal N+1 — crop,
  never resample. Note the two knock-on effects before choosing this: setting
  `scale_xy_cm` 400 -> 800 preserves the 8064 m span exactly
  ((2017-1) x 400 cm == (1009-1) x 800 cm == 806400 cm), so every coverage and
  median-slope number signed off to date still holds; but per-quad detail
  halves from 4 m to 8 m, and 4 m with flat colours is *already* the stated
  visual ceiling. Trading resolution for a real erosion model may still be
  worth it — that is an art call, not a plumbing one, and it needs its own
  sign-off.

Recorded rather than silently edited into the entry below, because the
"missing DLL" reading was quoted in several places and anyone following it
would have spent the time on a reinstall that has already failed twice.

## 2026-07-28 — Milestone heightmap is synthetic, pending Gaea
**CORRECTION (2026-08-01):** "Gaea was misbehaving" is not what happened —
the blocker is **licensing**, and it blocks both headless build and GUI
export. See the 2026-08-01 entry above. The rest of this entry stands, with
one clause now moot: the `.gitignore` note below contemplates "a real Gaea PNG
export of 2017px or larger", which the Community 1024 cap makes impossible.

`terrain/alpine_heightmap.png` is **generated, not exported**. Gaea was
misbehaving and the milestone should not wait on it, so
`scripts/make_test_heightmap.py` produces a stand-in: layered value noise
(fBm) with a central peak bias, written as a 16-bit greyscale PNG.

The stand-in holds the same contract as a real export — same path, same
format (`png16`), same legal-resolution constraint — so **a Gaea export
overwrites the same file with no recipe change and no schema change**. Nothing
downstream needs to know which one it is reading.

Generated at 1009x1009, seed 20260728. Reproduce the committed fixture with:

    python scripts/make_test_heightmap.py --relief 0.9

Note `--relief` defaults to 0.55; the committed fixture uses 0.9, so the flag
is required. Deterministic: same seed and parameters reproduce the same PNG on
the same numpy and zlib versions.

Two consequences recorded deliberately:
- **Resolution mismatch.** `recipes/alpine.json` declares `resolution` 2017
  with `component_count` 8; this fixture is 1009. The import script will
  refuse the pair until one side moves. The generator detects and reports
  the mismatch rather than silently resolving it.
- **The fixture does not yet exercise the material rules.** At the recipe's
  `scale_xy_cm` 200 and `z_scale_cm` 256000, 1408 m of relief across a 2016 m
  span gives a median slope of 50 degrees, so Rock takes 79% of samples and
  Snow 0.05% — and at relief 0.55 the summit (1408 m) never reaches a 60%
  snow line (1536 m) at all. Fixing this needs `scale_xy_cm` around 800 and
  `--relief` around 0.9; both await sign-off, and `scale_xy_cm` is a scene
  parameter in a recipe already carrying an unresolved audit finding.

Note on `.gitignore`: it excludes `terrain/*.raw` and `terrain/*.r16` but not
`terrain/*.png`, so this fixture is tracked. That is fine while it is ~1.7 MiB
and useful as a reproducible milestone input, but a real Gaea PNG export of
2017px or larger should be reconsidered against the same "large binaries"
rationale the existing entries cite.

## 2026-07-28 — Recipe geometry: predicting median slope from relief and extent
Signed off: `landscape.scale_xy_cm` 200 -> 800, generator `--relief` 0.55 -> 0.9.

| | run 1 | run 2 (current) |
|---|---|---|
| `scale_xy_cm` | 200 | 800 |
| `--relief` | 0.55 | 0.9 |
| span across | 2016 m | 8064 m |
| summit | 1408 m | 2304 m |
| median slope | 50.2 deg | 26.1 deg |
| Rock / Snow / Grass | 79.25 / 0.05 / 20.70 % | 22.87 / 10.77 / 66.36 % |

**The rule that falls out.** Define the aspect ratio
`R = (relief * z_scale_m) / ((resolution - 1) * scale_xy_m / 2)` — summit
height over half-span. Then

    median_slope ~= atan(0.857 * R)

Both runs give the same constant to three digits: run 1 R = 1.397, tan(50.2) =
1.199, ratio 0.858; run 2 R = 0.571, tan(26.1) = 0.490, ratio 0.857. The 0.857
is a *shape* constant for this generator's profile and holds only while the
noise parameters are unchanged (peak_bias 0.55, octaves 7, base_freq 3,
lacunarity 2.0, gain 0.5). Change those and it must be re-measured — but at
fixed shape it predicts median slope from geometry alone, so target a slope
distribution by solving for `scale_xy_cm` instead of guessing and re-running.

**Practical reading.** A material rule keyed at 35 degrees wants a median well
below it or the steep layer swallows the terrain — at median 50 degrees, Rock
took 79%. Median ~26 degrees puts the 35-degree threshold near the 80th
percentile, which is where a "steep slopes only" rule belongs.

**Snow needs headroom, not just slope.** Snow was 0.05% in run 1 because the
summit (1408 m) sat *below* a 60% snow line (1536 m) — no amount of slope
tuning fixes a peak that never reaches the threshold. Relief must exceed the
snow-line fraction with margin: at relief 0.9 the summit is 2304 m against a
1536 m line, and Snow lands at 10.77%.

## 2026-07-28 — Source-authoring parameters stay out of recipe JSON (ruling)
Signed off, agreeing with the auditor: generator seed, octaves, gain,
lacunarity and peak bias are **source-data authoring parameters**, not scene
parameters. They are the direct analogue of Gaea's internal `.tor` settings,
which also live outside recipe JSON. Hard rule 2 governs values that reach the
editor; these produce the source asset that the recipe then *points at*.

Consequence: **`heightmap.seed` is NOT being added to the schema**, in v1.1 or
otherwise. `scripts/make_test_heightmap.py` keeps its hardcoded default seed
with CLI override.

Recorded as a general ruling so it is not re-litigated per script: if a
parameter shapes the source data rather than the assembled scene, it belongs
to the tool that authors the source, not to the recipe.

## 2026-07-28 — Material layer transitions: option (i), first-match-wins stands
Signed off on audit finding F2 (`recipes/alpine.json`). Snow lower bound and
Grass upper bound both set to **1536.0** — a hard boundary at 60% of the
2560 m range — with Snow's `blend_sharpness` 0.25 providing the feather. The
dead 1670 m range is deleted. Coverage after: Snow 8.43%, Rock 22.87%, Grass
68.69%, unmatched 0.00%.

**Why not option (ii).** Changing v1 semantics from first-match-wins to
weighted overlap blending is a real feature, but it was proposed to justify
*one recipe's encoding error* — the overlap band was written assuming
semantics the schema does not have. That is the wrong reason to fork a schema.

**Logged as a schema v2 candidate:** overlap-driven cross-blending with band
width expressed in metres. **Trigger for revisiting is "a second recipe that
fights this" — not aesthetics.** If one more biome needs a transition that
`blend_sharpness` cannot express, that is evidence of a missing primitive. One
recipe getting it wrong is evidence of a mistake.

## 2026-07-28 — Import route: (B) now with a spec/verify bracket, (A) as v2
Signed off. UE 5.8 exposes no script-callable API that builds a landscape from
a heightmap file (`LandscapeProxy.h:1572` is render-target only and needs an
existing landscape; `Engine/Source/Editor/LandscapeEditor` has zero
BlueprintCallable functions; `ALandscape` has no exposed `Import()`).

**Route (B) adopted:** the landscape is created by hand once, then scripts push
heights via render target. Route B's stated danger was that the hand-made
landscape becomes undocumented state the recipe does not govern. That is
neutralised by bracketing the manual step with script on both sides:

1. `scripts/landscape_spec.py` — reads the recipe, prints the exact New
   Landscape dialog values derived from recipe geometry. No editor contact.
2. Manual creation, once, from that printout.
3. `scripts/verify_landscape.py` — remote-exec under the rule 7 flow, reads the
   live landscape's actual extents/components/scale, compares against the
   recipe-derived spec, exits non-zero on any mismatch. **Runs at the top of
   every subsequent scene script as a gate**, the same pattern as bootstrap's
   isdir guard.

Net effect: undocumented hand state becomes verified state with a tripwire. A
fat-fingered dialog entry stops everything downstream rather than silently
producing a wrong world.

**Route (A) — a C++ plugin wrapping the internal import — is the v2 target**,
contingent on a Visual Studio toolchain install, to be revisited after the
first full milestone loop. It is the only route that keeps "zero hand-work
in-editor" literally true, at the cost of depending on internal APIs with no
compatibility guarantee across engine versions.

**Route (C), commandlet/console automation, is dead.** Not to be revisited for
landscape import. If commandlets earn a place later it will be for batch
cooking.

**Baked in for the render-target script when it is written:** the render target
must be `RTF_RGBA32f`, not `RTF_RGBA16f`. fp16 carries a 10-bit mantissa and
cannot represent all 65536 discrete levels of a 16-bit heightmap, so 16f would
silently quantise the terrain. Cite this reason in the code comment.

## 2026-07-28 — Level path and World Partition (project state)
**CORRECTION (2026-07-31):** the level path recorded below as `/Game/Maps/Alpine`
is **wrong**. The actual path is **`/Game/Alpine`** — on disk
`LandscapeLab/Content/Alpine.umap`, and live actor paths read
`/Game/Alpine.Alpine:PersistentLevel.…`. There is no `Maps/` folder. Recorded
rather than silently edited, because the wrong path was quoted in several
places and anyone following it would have found nothing.

The milestone level is **`/Game/Maps/Alpine`**. The landscape actor inside it is
labelled `Landscape_Alpine` per the recipe; "Alpine" is the map name, not the
actor name. No conflict — recorded because the two were briefly confused.

**The level is World Partition.** Established empirically: the first
`verify_landscape.py` run returned `component_total` 0 on the `ALandscape`
actor, which is the WP signature — components are parcelled onto
`ALandscapeStreamingProxy` actors. This is not incidental; it changes how
every future script must reach landscape geometry, and it is why moving the
landscape is not a one-line operation (see the transform blocker below).

Consequence for verification: only **loaded** actors are enumerable. With WP
regions unloaded, component counts undershoot and `verify_landscape.py` fails
as a mismatch. Load the full landscape before verifying.

## 2026-07-31 — Layer appearance: schema v1.1 (option (c) + roughness)
Signed off. `base_color` [r,g,b] and `roughness` (0–1) **required** per layer;
`texture` **optional**, declared as a repo-relative source path imported
find-or-create like `heightmap.source`; `tiling_m` marked
**reserved-until-textures**. The schema was opened once, deliberately, so
`texture` can arrive later without another revision.

`roughness` is required rather than defaulted because snow versus rock is a
roughness distinction as much as an albedo one — a uniform 0.5 makes snow read
as matte plaster under a low warm sun.

**`specular` and `metallic` deliberately omitted — a decision, not an
oversight.** Engine default specular 0.5 gives F0 ≈ 0.04, physically plausible
for every dielectric in this biome; metallic is irrelevant to natural terrain;
unused keys are schema debt.

**Rejected: colour-from-layer-name table in the script.** Hard rule 2
violation — base colour reaches the assembled scene, so it is a scene
parameter. The source-authoring ruling does not shelter it. Recorded so it is
not re-proposed.

Starting values in `alpine.json` are physically plausible linear albedos to be
art-directed against the first capture rather than theorycrafted: Snow
`[0.86, 0.89, 0.94]` @ 0.3, Rock `[0.34, 0.32, 0.30]` @ 0.85, Grass
`[0.19, 0.28, 0.12]` @ 0.6.

## 2026-07-31 — Debug layer-visualisation material: approved, with a fence
Signed off. A diagnostic material paints each layer in flat, deliberately
artificial colours so the slope/height blend **geometry** can be judged
independently of appearance — if the blend is wrong it should be visible in
flat colours, not hidden behind plausible terrain.

**The fence, inviolable:** it writes only under a clearly-named debug asset
path (`/Game/Debug/M_LayerDebug`), never to `material.parent_material`;
captures from it carry a `_debug` suffix; changelog entries for debug renders
are marked **DIAGNOSTIC**, never presented as scene output; and it does not
satisfy the auto-material milestone deliverable.

Its fixed false-colour palette is *not* recipe data and does not violate hard
rule 2 — it is an instrument reading, like a thermal camera's palette. The real
material takes its colours from the recipe.

## 2026-07-31 — Captures are evidence: residency gate required
Signed off. `capture.py` establishes World Partition residency before any
shot and refuses otherwise. WP loading is not viewport-driven, so a fresh
editor session can photograph holes where terrain should be — silently, with no
error and no way to tell later. Unloaded-terrain screenshots would poison the
record, so the gate is a precondition of every capture from here on.

## 2026-07-31 — Camera composition serves the boundary, not the horizon
Signed off. `snowline_detail` pitch −5° → **−14°** so the near snow boundary
sits in the lower third of frame; going beyond −23° would have been acceptable
if needed. At 45° **horizontal** FOV and 16:9 the vertical FOV is 26.23°, so
the frame spans −27.11°..−0.89° and the ~23° boundary lands ~16% up from the
bottom, with the +1024 m summit still in frame near the top. The horizon falls
out of shot deliberately.

**This ruling only became real on 2026-07-31.** Until then `fov_deg` never
reached the engine — `set_level_viewport_camera_info` copies location and
rotation only, so every capture used the viewport's own FOV (~90°). Fixed by
passing `camera=` to `take_high_res_screenshot`. Captures taken before that fix
are not framed as their recipe describes.

## 2026-07-29 — Conduct rule 4 reading: scripted asset creation is permitted
Ruling. Conduct rule 4 ("never modify .uproject, .uasset, or .umap files
directly on disk; all editor-side changes go through the UE Python API only")
forbids **direct on-disk edits**. It does **not** forbid creating assets through
the editor API — `unreal.AssetTools`, `MaterialEditingLibrary` and friends *are*
the UE Python API, and are exactly what the rule directs work through.

Consequence: `material.parent_material` and the per-layer
`ULandscapeLayerInfoObject`s are **declared by the recipe and find-or-created by
script**. Hard rule 3 applies — the script must find an existing asset before
creating one, so re-runs update in place and never duplicate.

The earlier schema gloss ("must already exist — scripts never author materials
on disk") was a misreading and has been corrected in `recipes/schema.md`.

## 2026-07-29 — BLOCKED: recipe layers declare WHERE, not WHAT
The auto-material script is blocked, and the blocker is the schema, not the
UE API. `MaterialEditingLibrary` is fully capable —
`CreateMaterialExpression`, `ConnectMaterialExpressions`,
`ConnectMaterialProperty`, `SetBaseMaterialUsage`, `RecompileMaterial` are all
BlueprintCallable in 5.8 and reachable from Python.

**The gap:** a layer object is `name`, `slope_deg`, `height_m`,
`blend_sharpness`, `tiling_m`. Every one of those says *where* the layer
applies. **None says what it looks like** — no base colour, no texture, no
roughness. A material cannot output a surface from that, and hard rule 2
forbids the script inventing one.

`tiling_m` compounds it: a texture repeat distance with no texture to repeat.

Needs a ruling before any material script is written. Options in
`docs/audit-log.md`.

## 2026-07-28 — Map-check "shared properties not in sync": predates our work
Twelve `Landscape_Alpine` proxies were flagged with *"had some shared properties
not in sync with its parent landscape actor. This has been fixed…"*
(`Landscape.cpp:5208`). Attribution confirmed by package identity, not label —
`Landscape_Alpine` owns exactly the 4×4 grid `0_0`–`3_3`, and the flagged set is
precisely the 12 that were newly loaded by our `load_actors()` call; all four
previously-resident proxies (`1_1`, `1_2`, `2_1`, `2_2`) are clean.

**Cause: pre-existing, not us.** This is UE's deprecation fixup for data
authored before shared-property enforcement was introduced
(`landscape.SilenceSharedPropertyDeprecationFixup`, `Landscape.cpp:223`). It
fires on *load*, so loading 76 previously-unloaded proxies for the first time is
simply what made the engine look. The accepted sculpt dent is **not**
implicated — the dented proxy `1_1` is among the clean four. The engine fixed
the discrepancy automatically; the only consequence is cooking behaviour.

## 2026-07-28 — OPEN: shared properties are not on the verify surface
`verify_landscape.py` checks geometry only — component spacing, derived
resolution, scale, location. Shared properties (landscape material, LOD
distribution, collision settings) are a different class and nothing verifies
them.

Deferred deliberately. **Trigger: when the recipe starts owning landscape
material assignment**, that property joins the verify surface, and we scope at
the same time which *other* shared properties the recipe owns. Scoping that
before the recipe has an opinion would be guessing.

## 2026-07-28 — Sculpt dent on the synthetic fixture: ACCEPTED
Signed off. A stray sculpt edit survived an undo and was saved to disk.

**What changed.** Exactly one package in the repo:
`/Game/__ExternalActors__/Alpine/3/59/Q51STS97C1YLQEXOJMYDAK` =
`LandscapeStreamingProxy_1_1_0`, owned by **`Landscape_Alpine`** (the keeper).
LFS oid `d38ed466…` → `8008e87d…`, 564117 → 564891 bytes (+774 B, ~0.14%).
No other package changed.

**Maximum extent.** That proxy holds 4 components at section base 252 — 2×2 ×
126 quads × 800 cm ≈ a **2 km × 2 km tile**, one-sixteenth of the 8 km
terrain. The actual edit is presumably far smaller; a `.uasset` cannot be
diffed semantically, and because landscape heightmaps are stored as compressed
textures, a small pixel edit and an engine metadata fixup produce
indistinguishable size deltas. What tipped the reading toward a real edit: a
load-time fixup would normally dirty many proxies, and exactly one changed.

**Why accepted rather than restored.** `terrain/alpine_heightmap.png` is a
deterministic synthetic fixture that a real Gaea export will overwrite
wholesale; the landscape is then re-imported and the dent evaporates. The dab
does not move the slope distribution or layer coverage meaningfully. Both
restore paths cost more than the thing they protect.

**Recoverable regardless.** The pre-save bytes are committed at **`3ca1771`**
and can be restored at any time with
`git checkout 3ca1771 -- LandscapeLab/Content/__ExternalActors__/Alpine/3/59/Q51STS97C1YLQEXOJMYDAK.uasset`.

**Hazard recorded for whoever tries that later.** Overwriting a `.uasset` on
disk while the editor holds that package in memory desyncs the two: the editor
keeps its in-memory version and the next save silently overwrites the restore.
The only safe order is **close the level → `git checkout` → reopen**. Never
restore while `Alpine` is open.

**Hard rule 4 status: satisfied late and labelled.** This scene change is
committed with capture pending, because `capture.py` cannot safely run against
the known-broken two-landscape scene. Its first run (post-deletion) covers the
current scene state including this dent, and the changelog entry is written
then, marked retroactive.

## 2026-07-28 — Landscape placement is CENTRED on world origin (intent change)
Signed off, resolving the move fork as **option (iv)**. Not a fix — an
**intent change**, recorded as such.

`landscape.location_cm` becomes `[-403200, -403200, 0]`. Since the actor
origin is the landscape's corner and the terrain spans 8064 m, a corner at
−403200 cm puts the terrain **centred on the world origin**, spanning ±4032 m
on both axes.

**Why this is legitimate and not the recipe chasing reality.** The original
`[0, 0, 0]` was arbitrary — it was never a decision, just the obvious default
when the recipe was first written. Centred-on-origin is defensible placement on
its own merits. Had the original value been load-bearing, amending it to match
an accident would be exactly the inversion the route-B bracket exists to
prevent, and the answer would have been (iii), a manual UI move.

**Why not the alternatives:**
- (i) delete and recreate — discards a good 1009 import to fix a placement
  error that turned out not to be an error.
- (ii) proxy-aware Python mover — reimplements `FixupProxiesTransform`; the
  most reimplemented-invariant risk for the least benefit.
- (iii) manual UI move to 0,0,0 — legitimate and clean (the editor's own
  transform path runs `FixupProxiesTransform` in-engine), but costs a hand-step
  to reach a placement no better than the one already on disk.
- **(iv) amend the recipe — chosen.** Zero mutations. The cheapest correct
  state is the one requiring no change to the world at all.

**Proxy transforms are unaffected.** Each proxy sits at
`landscape_location + scale · section_base` (`Landscape.cpp:6164`) — systematic
offsets derived from section base, not per-actor quirks. `verify_landscape.py`'s
implied-origin check passes identically at either placement.

**Consequence — `capture.cameras[]` are now stale.** They are the one
genuinely world-space thing in the recipe. `ridge_wide` at
`[-60000, -60000, 150000]` was authored for terrain spanning 0..8064 m
(outside the SW corner, looking in); against centred terrain it sits near the
map's middle at 1500 m, below a 2304 m summit. Both cameras need re-deriving.
They were already flagged as needing tuning after first capture, so this is
brought-forward work, not new work — but it is **not** done, and the values in
the recipe currently frame the wrong place. Per the D2 ruling, material rules
are heightmap-relative and are unaffected.

## 2026-07-28 — D3: geometry may be DERIVED from component spacing
Signed off as **option (a)**. UE 5.8's `get_editor_property` refuses bare
`UPROPERTY()` fields, so `num_subsections`, `subsection_size_quads` and
`component_size_quads` cannot be read back. Rather than leave
`verify_landscape.py` permanently red, the measured component spacing is
accepted as confirmation — **an arithmetic independent confirmation rather
than a property read**, not a weakening.

**The proof, recorded so it travels with the decision.** Component spacing
equals `section_size × sections_per_component`. Over the dialog-legal values —
`section_size ∈ {7, 15, 31, 63, 127, 255}` (`SubsectionSizeQuadsValues`,
`LandscapeConfigHelper.cpp:25`) and `sections_per_component ∈ {1, 2}`
(`NumSectionValues`, `LandscapeConfigHelper.cpp:24`) — the products are:

| section_size | ×1 | ×2 |
|---|---|---|
| 7   | 7   | 14  |
| 15  | 15  | 30  |
| 31  | 31  | 62  |
| 63  | 63  | 126 |
| 127 | 127 | 254 |
| 255 | 255 | 510 |

All twelve products are **distinct**: 7, 14, 15, 30, 31, 62, 63, 126, 127,
254, 255, 510. A measured spacing therefore determines
`(section_size, sections_per_component)` uniquely. The observed 126 can only
be 63 × 2. The ambiguity feared earlier — 63×2 versus 126×1 — requires
`section_size = 126`, which the dialog cannot produce.

**Conditions of the ruling:** the verifier prints `DERIVED` loudly on those
three rows so no reader mistakes them for property reads. When the route-A C++
plugin exists, it should expose a direct geometry accessor and the `DERIVED`
labels retire — recorded as a route-A deliverable, option (c) of the finding.

## 2026-07-28 — BLOCKED: moving a World Partition landscape
Unresolved; needs a ruling. `scripts/apply_landscape_transform.py` is written,
audited, and **refuses (exit 7) on the current level by design**.

**The bug it was written to fix.** The New Landscape dialog's Location field is
the landscape's *centre*, not the actor origin
(`LandscapeEditorDetailCustomization_NewLandscape.cpp:1219`).
`landscape_spec.py` printed `location_cm` straight into it, so the actor was
created at −403200, −403200 instead of the origin. `landscape_spec.py` is now
fixed to pre-compensate.

**Why the obvious fix is unsafe.** Proxies are realigned to the parent only by
`ALandscape::PostEditMove` → `ULandscapeInfo::FixupProxiesTransform(true)`
(`LandscapeEdit.cpp:5140-5146`), which the editor's interactive move tools fire.
Python's `set_actor_location` calls `AActor::SetActorLocation` and never
triggers it. On this WP level that would have moved the empty parent to the
origin, left all 64 components at −403200, and saved the torn result.

**And the tripwire would have passed it.** `verify_landscape.py` read only the
parent's location, so a torn landscape would have satisfied every check. The
verifier now cross-checks each component's implied origin
(`world − scale · section_base`, per `Landscape.cpp:6164`) against the recipe
origin, closing that blind spot.

**Options:**
- **(i) Delete and recreate by hand** from the corrected printout. Uses the
  engine's own placement path; consistent with route B; costs one manual redo.
- **(ii) Proxy-aware mover** — set each proxy absolutely to
  `recipe_origin + scale · section_base`. Reimplements `FixupProxiesTransform`
  in Python; larger surface; needs its own audit.

## 2026-07-28 — Height datum: `height_m` is heightmap-zero-relative
Signed off, resolving audit finding D2.

`height_m` is measured from **heightmap value 0** — the bottom of the height
range — independent of actor placement. Rationale: material rules must be a
function of the terrain data, not of where the actor sits in the world. Actor Z
is presentation; recipe semantics are data.

**The trap, documented so the material script can cite it.** Unreal maps
heightmap value **32768** (mid-grey), not 0, to the landscape actor's Z —
`LANDSCAPE_ZSCALE = 1/128`, `LandscapeDataAccess.h:13`. Consequences:
- A landscape at actor Z 0 with `z_scale_cm` 256000 spans world Z −128000 to
  +128000 cm. It is NOT 0..256000.
- A recipe band of `[1536, 2560]` is therefore **not** world Z 153600–256000.
- Any script sampling in **world space** must offset:
  `world_z_cm = actor_z_cm + (height_m * 100) - (z_scale_cm / 2)`
- Any script sampling **normalised heightmap values** needs no offset. That is
  precisely why this datum was chosen.

Confirmed as part of this ruling:
- **`alpine.json` needs no edit.** Snow `[1536, 2560]`, Grass `[0, 1536]`,
  Rock `[0, 2560]` against `z_scale_cm` 256000 already read as
  heightmap-zero-relative. The recipe was conformant under both readings; only
  the schema wording was ambiguous.
- **The re-run coverage numbers stand.** `make_test_heightmap.report_relief`
  computes `height_m = (value / 65535) * z_scale_m`, which is exactly
  heightmap-zero-relative. Snow 8.43% / Rock 22.87% / Grass 68.69% /
  unmatched 0.00% remain valid without recomputation.

## 2026-07-28 — sections_per_component semantics (RESOLVED, option α)
Signed off. `sections_per_component` is **the engine-stored integer**, legal
values **{1, 2}**. The dialog's "2x2 Sections" label is a rendering of the
linear subsection count 2, not a count of 4.

**Where the "4" came from:** conflating the dialog's `NxN` label with a total.
The arithmetic coincidence that `63 * 4 * 8 + 1` and `63 * 2 * 16 + 1` both
equal 2017 is why the error survived unexamined in the schema's worked example.

**Why α over the alternatives:** the recipe value must be the same integer
`verify_landscape.py` reads back off the live landscape. The bracket's
integrity depends on zero translation layers between recipe and live
comparison — (β) would have put a square root inside the gate, and (γ) bought
a better name at the cost of churn with no verification benefit.

Applied: `schema.md` row rewritten with engine authority and the worked example
corrected; `alpine.json` to 63 / 2 / 8 -> 1009; `LEGAL_SPC = (1, 2)` in
`make_test_heightmap.py` and `import_heightmap.py`.

### Original finding, retained for the record
Needed a ruling before `landscape_spec.py` could be written.

`recipes/schema.md:51` states `sections_per_component` is **1 or 4**. Unreal
has no 4. Verified in engine source:
- `LandscapeConfigHelper.cpp:24` — `FLandscapeConfig::NumSectionValues[2] =
  { 1, 2 }`. Those are the only legal values.
- The New Landscape dialog renders them as "1x1 Section" / "2x2 Sections"
  (`LandscapeEditorDetailCustomization_NewLandscape.cpp:866`), so the stored
  integer is the **linear** subsection count, not the total.
- `QuadsPerComponent = SectionsPerComponent * QuadsPerSection`
  (`LandscapeEditorDetailCustomization_NewLandscape.cpp:1185`), confirming
  linear use. `LandscapeEdit.cpp:151` asserts the same identity.
- `SubsectionSizeQuadsValues[6] = { 7, 15, 31, 63, 127, 255 }` — the schema's
  `section_size` values are correct.

The schema's resolution identity (`section_size * sections_per_component *
component_count + 1`) is structurally right; it simply permits an illegal
value. Consequences: `recipes/alpine.json` currently carries
`sections_per_component: 4`, which cannot be entered into the dialog, and the
schema's own worked example (`63 * 4 * 8 + 1 = 2017`) is likewise unbuildable.
`scripts/make_test_heightmap.py` and `scripts/import_heightmap.py` both inherit
`LEGAL_SPC = (1, 4)` from the schema and will report illegal factorisations.

Under corrected semantics the fixture's 1009 is `63 * 2 * 8 + 1` — section size
63, sections per component **2** (2x2), component count **8**.

## 2026-07-27 — Audit requests carry both roots
The auditor's first criterion is scope safety, which is a judgement about
paths relative to REPO_ROOT and UE_PROJECT_ROOT. Since the auditor is
read-only and has no other way to learn them, every audit request states both
verbatim; a missing root is an automatic BLOCK rather than an inference.
