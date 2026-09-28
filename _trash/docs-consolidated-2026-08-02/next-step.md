# Handoff — start here

> **UPDATED 2026-08-02 (late). Read this block first; the sections below
> it predate the asset work and are corrected here where they disagree.**

## STATE, as of the end of the asset session

| | |
|---|---|
| Level | `/Game/Alpine`, **SAVED: 1227 packages**, every one verified on disk |
| Terrain | isotropic world, relief 0.48, unchanged this session |
| Material | real photogrammetry surfaces (Snow006 / Rock051 / Ground037) with normal + roughness maps; `base_color` is now a TINT |
| Exposure | `compensation_ev` **-1.18** (was -0.6; re-derived after real albedo replaced the mean-0.5 synthetic maps) |
| Foliage | **BUILT.** 28,302 conifers placed and counted; grass as five GPU-spawned size classes at 14 per 10 m2 |
| Assets | 23 vendor objects normalised, measured and on disk in `Free/_normalized/` |
| Schema | documented through **v1.10** in `recipes/schema.md` |

**The FOLIAGE leg is no longer missing.** The "one-line version" section
further down still says it is; that text predates this session. All four
legs of CLAUDE.md's end state — terrain, materials, foliage, lighting —
now build from `recipes/alpine.json` with no editor interaction.

## IF UNREAL OFFERS TO RESTORE FROM AUTOSAVE — the answer was NO, 2026-08-02

The editor went down after the final save and offered a restore on next
launch. **Declined, and the reasoning generalises**, so do not answer this
from instinct next time — check the timestamps, because the prompt gives
no indication of which side is newer.

    real actor packages   Content/__ExternalActors__/Alpine/*.uasset
                          08-02 03:30:53   <- the verified save_level run
    newest autosave       Saved/Autosaves/*_Auto9.uasset
                          08-02 03:19:25   (the bulk at 02:58:26)

The on-disk packages were 11 to 32 minutes NEWER than every autosave, so
restoring would have overwritten verified-good state with an older
snapshot — and the autosave files carry the same OFPA hash names as the
InstancedFoliageActor packages, meaning what it offered to restore was
the 28,302 conifers back at their PRE-PIVOT-FIX positions, 12.4 m off.
The restore would have re-introduced the exact defect the session existed
to remove.

Two things that look alarming in that listing and are not:

  - `Saved/Autosaves/PackageRestoreData.json` was dated ONE SECOND AFTER
    the real save. That is UE writing the restore manifest on its way
    down; it is the index that triggers the prompt, not newer content.
    Do not read its mtime as "the autosave is newer".
  - `Content/Alpine.umap` was dated 07-28, four days stale. Expected
    under OFPA — the actors live in external packages and the .umap
    barely changes. It is not evidence that the level is old.

**The check, when this recurs:** compare the newest file under
`Content/__ExternalActors__/<level>/` against the newest under
`Saved/Autosaves/`. Restore only if the autosave is genuinely newer, and
remember that `save_level.py` verifies its writes are present on disk —
so a completed save is stronger evidence than an autosave ever is.

Independent confirmation after declining, if wanted:
`python scripts/verify_landscape.py` measures the geometry rather than
trusting the save's own report.

## READ THIS BEFORE TOUCHING THE EDITOR

**Everything is saved. 1223 packages, written and verified present on
disk**, including the 28,302 conifer instances at their CORRECTED pivots.
Nothing needs recovering.

**But the editor saturates, repeatedly, and this will bite you.** Three
times this session it stopped accepting command connections while still
answering UDP discovery, with Windows reporting the process alive around
3.3 GB and `Responding` flipping between True and False. Each time it
recovered on its own after a few minutes. The trigger is heavy work —
placing 28,302 single-LOD 505k-triangle instances, saving 1223 packages,
rendering six captures of that scene.

What that means in practice:

  - A `REFUSE (rule 7): no editor nodes answered discovery` right after a
    heavy operation is **saturation, not a crash and not a
    misconfiguration**. Wait several minutes and re-check with
    `python scripts/bootstrap.py`.
  - Do NOT retry the failing script against it. Conduct rule 6 exists for
    this, and the failure mode here is genuinely transient.
  - This is a symptom of open item 1 (no LODs on the fir), not an
    independent problem. Fixing the LODs should fix this too.

The last capture set could not be retaken because of exactly this, so the
newest images on disk predate the final save. They are still accurate:
the save wrote instance positions, it did not change them.

## THE LOOP, CORRECTED

The asset stages are new and go BEFORE the existing loop. They only need
re-running when the vendor files change.

```
# once per vendor file, or when Free/ changes
python scripts/make_asset_manifest.py
blender --background --factory-startup --python-exit-code 1 \
    --python scripts/blender/normalize_asset.py \
    -- "Free/<name>_4k.fbx/<name>_4k.fbx" "Free/_normalized"
python scripts/import_surface_set.py <SurfaceId>
python scripts/import_static_mesh.py <asset_id> --normalized <OBJECT> --name <OBJECT>
python scripts/make_foliage_material.py <asset_id> --mesh-asset /Game/Meshes/<OBJECT> \
    --name M_<something> --masked
```

Then the existing loop, plus foliage:

```
python scripts/make_alpine_terrain.py --resolution 2017
python scripts/make_layer_weightmap.py
python scripts/push_heightmap.py --push [--expect-change]
python scripts/verify_landscape.py
python scripts/import_layer_textures.py
python scripts/make_landscape_material.py --assign     # also builds grass types
python scripts/place_foliage.py                        # plan, offline
python scripts/place_foliage.py --place                # into the editor
python scripts/apply_lighting.py
python scripts/capture.py [--filename-tag foo]
python scripts/save_level.py            # dry run first, then --save
```

Note `--normalized OBJECT` is not optional for anything that gets
instanced. It refuses unless `Free/_measured/normalized.json` names the
object as verified, and that refusal is the point — see below.

## THE THREE DEFECTS THIS SESSION FOUND, because they will recur

Full write-ups in `docs/lessons.md` section 23. Short forms, because each
is a class rather than an incident:

1. **The pivot was 12.4 m from the tree and every gate was green.** The
   vendor FBX lays its objects side by side; UE bakes that into the
   StaticMesh pivot. Triangle counts, LOD counts, material slots and
   world instance counts were all verified and all correct. Nothing
   measured the pivot. *Rule: an asset's pivot is a property you must
   measure, not one you may assume the exporter got right.*
2. **The vendor published a correct number that answered a different
   question.** `mesh_extent_m: 7.3` for `grass_medium_01` is the width
   of the whole set laid out for the product shot; one tuft is 0.327 m.
   Derived scale produced grass 0.7 cm tall and nothing reported a
   problem. *Rule: `vendor` does not outrank `measured`.*
3. **Every capture camera was 1-9 km out.** Trees at 4.4/ha and 0.15 m
   grass are sub-pixel at that range, so for the whole foliage milestone
   the review loop was incapable of showing its subject — and came back
   looking good, because the terrain and lighting it COULD resolve were
   good. *Rule: a capture set needs at least one camera at the scale of
   the smallest thing being verified.* The `forest_floor` camera now
   exists for exactly this and took three attempts to place; the two
   failures are in section 23.3 and are instructive.

## GPU HANG, 2026-08-02 — cause found, one fix applied, levers left

`DXGI_ERROR_DEVICE_HUNG` on D3D12. A Windows TDR — the GPU missed the
driver's frame deadline. **Not** memory: 3998 MB of an 8283 MB budget.

**Cause:** `place_foliage` set exactly one property on each FoliageType,
`mesh`. `FoliageType.h:292` documents `CullDistance` as "0 disables" and
`InstancedFoliage.cpp:602-603` defaults both ends to 0, so nothing was
ever culled: 28,302 instances of a 505,494-triangle single-LOD mesh every
frame across an 8 km map. 14.3 billion triangles.

**Applied:** `cull_distance_m` is now a recipe key valid on instanced
species, set to 300 m for the Conifer, applied with read-back. ~124 trees
in view, 63M triangles. See `docs/lessons.md` §23.12 for the part worth
remembering — the validator actively FORBADE this key with a rule I wrote
from a wrong premise.

**NOT applied, deliberately — one change at a time.** A sweep of every
property this pipeline leaves at engine default turned up two more that
matter, both confirmed at source, both still uncontrolled:

  - `bCastDynamicShadow` defaults **true** (`InstancedFoliage.cpp:618`,
    reaching the component at :1629). 28,302 shadow-casting high-poly
    trees.
  - `bAffectDynamicIndirectLighting` defaults **true** (:621, → :1672).
    On Software Lumen, on an integrated GPU.

The grass path sets `cast_dynamic_shadow=False` explicitly; the instanced
path sets neither. That asymmetry was the tell for §23.12 and it is still
there. Both are hard rule 2 gaps — scene parameters coming from nowhere —
and both are levers if 63M triangles still hangs.

They are not applied yet because stacking a second change onto an
unverified first makes it ambiguous which one worked. Verify the cull fix
first.

**The real fix remains LODs.** 63M triangles per frame is still far too
much for this GPU; it is three orders better than 14.3 billion, which is
what makes the level openable so the LODs can be built. That is open item
1 and it has not moved.

**Reopening safely:** the editor was relaunched on
`/Engine/Maps/Templates/OpenWorld` via the command line, so it never
rendered the uncullable scene, and the FoliageType was repaired as an
ASSET with no level loaded. If this recurs, that is the sequence —
a FoliageType is not level state.

## THE LOAD, IN NUMBERS — quality vs quantity vs hardware (2026-08-02)

Computed from the recipe and the measured triangle counts. Worth reading
before tuning anything, because the intuitive answer is wrong.

    TREES (persistent instances)
      density              4.4 / ha        real alpine forest: 200-1000
      placed               28,302
      triangles each       505,494         LODs: 1
      before (no cull)     28,302 drawn -> 14,306M triangles/frame
      now (300 m cull)        123 drawn ->     62M triangles/frame

    GRASS (GPU-spawned, per view)
      cull distance        900 m
      density              14 per 10 m2
      instances in view    3,562,566
      avg triangles        1,043          share-weighted over 5 varieties
      COMPUTED             3,717M triangles/frame

**The crash was a defect, not a hardware limit.** 14.3 billion triangles
per frame is unbounded work; no GPU survives it, and a top-end discrete
card would have managed roughly 1 fps. Lack of resources did not cause
it — a missing cull distance did.

**Quantity is not the problem. There are too FEW trees.** 4.4/ha is
sparse for alpine forest by two orders of magnitude, and 28,302 instances
is trivial for UE when they are cheap.

**Quality is the problem.** 505,494 triangles with ONE LOD is a
source-resolution photogrammetry asset used as a game asset. Game-ready
is ~5k-30k at LOD0 and a few hundred at distance. It is 20-100x too heavy
near the camera and unboundedly too heavy far from it, because there is
no LOD to fall to. The assets are good; the delivery step was skipped.

**Hardware is a real but secondary constraint.** The integrated GPU
lowers the ceiling so the quality problem bites sooner. It does not
create it.

### UNVERIFIED, and the two facts do not reconcile
The grass figure above says 3.7 BILLION triangles/frame — comparable to
the pre-fix tree load — and `enable_density_scaling` is set FALSE, which
deliberately opts out of the engine's own scalability thinning on Medium.

But `alpine__forest_floor__*` shows NO grass, and the scene now renders
six cameras without incident. Both cannot be true of a grass system that
is actually spawning. Either the arithmetic overestimates what UE's grass
submits (it manages density per cell in ways this does not model), or the
grass is not spawning — which is open item 0a.

**Do not tune grass density on the strength of this number until 0a is
settled.** Resolve what is actually spawning first; a number computed
from a config that may not be in effect is not a measurement.

### Why LODs are the leverage
Auto-LOD at 25/6/1.5% gives ~126k/30k/7.6k. At a 300 m cull most trees
sit at LOD2-3, taking 62M to roughly 5-8M — an order of magnitude, on the
asset that is actually expensive.

The reason that matters more than it sounds: once per-tree cost drops
~10x, density can rise toward something that reads as forest (50-100/ha
rather than 4.4) and still be lighter than the scene is today. **Fixing
quality is what buys quantity.**

## GRASS — NOT SOLVED. Read this before spending another hour on it.

Three real bugs were found and fixed along the way. None of them was the
cause. The grass still does not render, and this section exists so the
next attempt starts from the frontier rather than the beginning.

### The engine says its grass data is BUILT
`grass.DumpGrassData -detailed -bygrasstype` (the command is at
LandscapeGrass.cpp:212 and I found it far too late — it is the only
direct instrument in this whole area):

    Num landscape actors with grass data:      1
    Num landscape proxies with grass data:     256
    Num landscape components with grass data:  1024
    Num grass types used:                      1
    Total grass data size (KB):                11800.00
    GT_alpine_Meadow: Num components = 902, total data size = 3608.00 KB

`FLandscapeGrassWeightPS` also appears in the shader-compile log, so the
grass weight pass compiled and ran.

**CAUTION on that evidence.** A per-component weight array occupies the
same bytes whether its values are 1 or 0. "3608 KB of grass data exists"
does NOT establish that the weights are non-zero, and that is the single
most likely place the remaining fault lives. The next attempt should
start by proving the grass weight is non-zero somewhere, not by
re-verifying assets.

### Ruled out, each by experiment, each measured
  - material assigned; exactly one LandscapeGrassOutput; pin `Meadow`
    accepts a connection (True) and every wrong spelling refuses
  - the MASK — a flat Constant 1.0 wired straight to the grass output
    changed the render by 0.007 in near-ground contrast. Nothing.
  - stale grass cache — `grass.FlushCache` took components 16 -> 0 and
    they rebuilt to 16
  - the builder throttles — `grass.MaxCreatePerFrame` 1 -> 64,
    `MaxAsyncTasks` 4 -> 16, `TickInterval` -> 0
  - view dwell — the editor viewport parked at the exact capture
    position for 90 s, on the theory that grass builds around views and
    capture.py teleports a camera in for a single frame
  - the quality-level fields — see the hazard below; setting
    `r.grass.DensityQualityLevel` from -1 to 3 changed nothing
  - the grass material — BLEND_MASKED, two-sided, OPACITY_MASK
    CONNECTED, alpha texture with SAMPLERTYPE_ALPHA, clip 0.333
  - the components — right mesh, right material, `visible=True`,
    `hidden_in_game=False`, cull 9000/12000
  - the weightmap — baked Grass channel reads **1.000** at the exact
    camera, 45.1% of the map above 0.5
  - cvars — `grass.Enable`, `grass.DensityScale`, `foliage.DensityScale`,
    `grass.CullDistanceScale` all 1.0

### TWO INSTRUMENTS LIE HERE. Do not repeat these.
  - **`get_instance_count()` always returns 0 for grass.** It reads
    `PerInstanceSMData`, which landscape grass never populates —
    `LandscapeGrass.cpp:3387` hands `AcceptPrebuiltTree` a prebuilt
    buffer instead. 0 is expected and means nothing.
  - **`get_local_bounds()` returns the MESH bounds** (±9.4 cm), not the
    instance cloud.

Both were briefly mistaken for evidence of absence.

### A hazard found, and deliberately NOT written up as the cause
`FGrassVariety` carries TWO density fields and two cull pairs —
`GrassDensity`/`GrassDensityQuality`,
`EndCullDistance`/`EndCullDistanceQuality` — and `GetDensity()` chooses
between them on `GEngine->UseGrassVarityPerQualityLevels`
(LandscapeGrass.cpp:1542). `make_landscape_material` sets the
NON-quality ones, and `r.grass.DensityQualityLevel` measured -1, which
looked exactly like the answer. Setting it to 3 and flushing moved
nothing, so the switch is false and the fields being set are the live
ones. Real trap for later; not this bug. See lessons 23.17.

### What WAS genuinely broken, and is now fixed
  1. **The config could not finish building.** At 900 m and 14 per
     10 m2 each landscape component needed ~355,000 instances against
     the 65,536 cap (`GMaxInstancesPerComponent`, :118), so it
     subdivided 9 ways x 5 varieties x ~12 components in range — which
     is where the 595 components came from — and the builder makes ONE
     per frame (:181). Now 120 m / 10 per 10m2 / 4 varieties:
     3.7 BILLION triangles down to 16.4M, 16 components.
  2. **The material graph was half orphaned debris.** 158 expressions
     down to 80 once leftovers were deleted explicitly.
     `delete_all_material_expressions` does not delete all material
     expressions; custom outputs and much else survive it, so every
     rebuild had been layering on top of the last. Hard rule 3 was
     failing silently.
  3. **Two LandscapeGrassOutput nodes**, a consequence of (2), which
     stopped the material compiling entirely.

### Where I would go next
  1. Prove the grass WEIGHT is non-zero. The data exists; its values are
     unverified. `grass.DumpGrassData -detailed -bycomponent` may show
     more, and the landscape's grass map can be inspected in the
     material editor's landscape visualisers.
  2. Try a trivially simple grass mesh (a single quad) and a stock
     engine material. If that renders, the fault is in the imported
     asset or its material despite everything above reading correct; if
     it does not, the fault is in the landscape/grass plumbing.
  3. Only then consider hardware — Software Lumen on an integrated GPU —
     which is the least likely explanation and the hardest to act on.

## OPEN ITEMS, in the order I would take them

**0. TWO THINGS THE FINAL CAPTURE SHOWS AND I COULD NOT CHASE DOWN.**
The editor became unresponsive immediately after
`alpine__forest_floor__20260802T101245Z__53eb067-dirty_stand.png` was
written, so both of these are OBSERVATIONS with an arithmetic prediction
beside them, not diagnoses. Look at that image first.

  **0a. The grass meshes do not appear at all. INVESTIGATED 2026-08-02;
  see the GRASS INVESTIGATION section above for what was ruled out.** The `forest_floor`
  camera stands at eye height on ground whose baked Grass weight is
  **1.00** (sampled offline from the weightmap, not estimated). The
  landscape material's grass output is wired to that layer's mask, and
  `GT_alpine_Meadow` read back with five varieties whose densities sum to
  exactly the recipe's 14.0 per 10 m2. Everything upstream verifies. No
  grass is visible.

  The most likely explanation, UNTESTED: `LandscapeGrassType` spawns per
  VIEW on the GPU, and whatever view `capture.py` renders through may not
  drive grass spawning — or the grass map build had not completed. If
  that is what it is, then the grass system is fine and the CAPTURE
  cannot see it, which would mean the review loop is blind to grass the
  same way it was blind to all foliage before `forest_floor` existed.
  That would be the third instance of §23.3 this session and is worth
  treating as the prime suspect. Second suspect: the grass output needs
  the landscape's grass data rebuilt after a material change.

  **0b. The conifers read as sparse skeletons and look smaller than the
  geometry says they should be.** The nearest tree inside the frustum is
  37.9 m away at scale 0.973, so 14.1 m tall, which at this camera's
  75-degree FOV over 1920 px predicts **467 px** on screen — about 43% of
  frame height. What renders is a thin trunk with a few frond tufts, and
  it looks considerably smaller than that.

  **I tried to measure the rendered height and the measurement failed** —
  isolating tree pixels by contrast against a reference column caught
  clouds and hillside and returned the full frame height, which is
  obviously wrong. So there is NO measured number here, only the
  prediction and an eyeball impression. Do not treat the discrepancy as
  established; it may be that the tree in that crop is a much more
  distant one.

  What is established: the mesh imports at 505,494 triangles with the
  measured 14.52 m bounds and a 0.0 m pivot, and its four material slots
  bind. Candidate causes for the sparse canopy, in the order I would
  test: the twig material's opacity-mask clip (`--clip`, default 0.333)
  cutting away needle mass; the alpha map not reaching the opacity input
  at all; or the single LOD being screen-size-culled. One look at
  `M_fir_twig` in the material editor should separate them.


1. **LODs for `fir_tree_01_c_LOD0`.** 505,494 triangles, ONE LOD, 28,302
   instances. It renders and the captures prove it, but this is the least
   defensible number in the project. `StaticMeshEditorSubsystem.set_lods`
   is the route; it is an audited change and wants a fresh session, not
   the tail of this one.
2. **Terrain texture stretches badly on steep faces.** Visible in
   `alpine__forest_floor__*_eye.png` — the landscape material samples in
   XY only, so anything near-vertical smears. Triplanar projection on the
   Rock layer is the fix and is a contained change to
   `make_landscape_material.py`.
3. **The fir's needles read dark brown, not green — MEASURED, and it is
   NOT a defect.** `fir_tree_01_twig_diff_4k.png` averaged over the
   texels the alpha actually KEEPS (23.6% coverage) is RGB
   [85.3, 81.3, 49.3]: green is 3.9 BELOW red and only 32 above blue —
   a desaturated olive, which is what the render shows. Averaging the
   whole map instead gives [88.2, 93.1, 52.5] and would have said
   "green", because it includes the background the alpha cuts away.
   The `dead_branches` substitution is not bleeding into the canopy;
   the vendor scanned an olive branch.

   So this is an ART DIRECTION question, not a bug: if you want green
   firs, the fix is a tint parameter on the foliage material, which is a
   schema addition. Left undone deliberately — inventing an appearance
   parameter at the tail of a session is how hardcoded values get in.
3b. **The grass MESHES and the ground TEXTURE may not agree in colour,
   and both are faithful.** Measured the same way as item 3:
   `grass_medium_01`'s albedo over its opaque texels (42.6% coverage) is
   RGB [36.2, 36.9, 17.7] — about 14% reflectance, a dark dry olive.
   `grass_medium_02` is much lighter at [135.0, 133.8, 91.5]. The
   landscape's Grass layer meanwhile renders the `Ground037` surface.
   Nothing is wrong with any of them individually; they were simply
   photographed under different conditions. If the sward reads as
   speckled rather than continuous, this is why, and the lever is
   choosing a matching pair rather than tinting one to the other.

4. **`grass_medium_02` and `leafy_grass` are inventoried and unused.**
   `grass_medium_02` is normalised and ready; it would add shape variety
   the current five size classes cannot, since they are all one species.
5. **Widen the grass variety list.** Eleven more `grass_medium_01`
   objects are normalised and on disk. Adding them is a recipe edit, not
   an import job. Each variety is a separate GPU spawn pass, so this
   trades against frame time on the documented hardware.
6. **`Rock026` and `Rock063` are imported but unused**, as is the second
   fir (`fir_tree_01_b_LOD0`, 2.3M triangles).

## NEEDS RYAN — nothing outstanding

The one open item, the vendor-import pivot gate, was **ruled by Ryan on
2026-08-02: option (c)** — `--normalized` is mandatory for any mesh a
RECIPE names; ad-hoc vendor imports stay ungated. Built, audited (PASS,
auditor-corrected) and tested offline. Full text in `docs/decisions.md`
under "RULING (c)" and the audit-log row of the same date.

Enforced at four points, because they guard four different failures:

  1. the recipe validator (`landscape_spec.recipe_normalization_errors`)
  2. `import_static_mesh`, refusing a recipe-claimed target without
     `--normalized`
  3. `place_foliage`, measuring `get_bounds()` before adding an instance
  4. `make_landscape_material`, same, before building a GrassVariety

1 and 2 are NAME checks against a report on disk and are defeated by
importing a vendor file under a verified name. 3 and 4 measure the asset
itself and are not.

**GATE 3 HAS NOW RUN LIVE, IN BOTH DIRECTIONS.** `place_foliage --place`
measured `fir_tree_01_c_LOD0` at pivot 0.0 m horizontal / base 0.0 m,
bounds [6.3059, 5.9662, 14.5206] m — matching Blender exactly — and
placed 28,302. Then the limits were lowered below the measured values and
both the horizontal and vertical branches refused at exit 4, and
restoring the limits placed again. So it does not false-refuse, it does
refuse, and it is not stuck.

**GATE 4 (the grass path in `make_landscape_material`) IS STILL
UNEXERCISED.** It is the same code shape as gate 3 and was audited
alongside it, but it has not run. Rebuilding the material is the cheap
way to close that: `python scripts/make_landscape_material.py --assign`.

Known hole, recorded not fixed — see `docs/lessons.md` §23.11. Gate 2
checks the `--name` it is handed, but UE's FBX importer writes one asset
per OBJECT in the file, so an ad-hoc vendor import of a multi-object file
can overwrite recipe-named meshes that gate 2 never looked at. This is
precisely why gates 3 and 4 measure `get_bounds()` at the point of use
rather than trusting the name checks.

The audit also surfaced, and I ruled under the standing autonomy grant:
`MAX_BASE_OFFSET_M = 0.25`, gating the VERTICAL pivot. Nothing had been
checking it, so a mesh with a correct XY pivot and its origin at the
bounding-box centre passed every gate and would bury each instance to
half its height — minus 7.26 m for `fir_tree_01_c`.

Two judgement calls made rather than asked about, easy to reverse:

- **Grass density 6 -> 14 per 10 m2**, and five varieties rather than
  sixteen. Both frame-time trades on an integrated GPU.
- **`grass_medium_01` vendor extents deleted** from the manifest's
  `FOOTPRINTS` table rather than kept beside the measurement. Keeping
  them would leave a stale value in the table that is consulted FIRST,
  which is how the wrong number won originally.

## Schema v1.4 — fog, changed 2026-08-02

`lighting.fog.height_falloff` is **REMOVED**; the validator refuses it by
name. Two replacements:

- `fog.height_datum_m` — the fog's world Z. Fog is densest AT this height
  and thins upward, so it decides which of a world is buried. It was
  previously governed by NOTHING: the actor sat wherever it was first
  spawned (1920 m) while the terrain's p90 was 1610 m, burying 90% of the
  world. Hard rule 2 applies and never had been.
- `fog.half_height_m` — metres over which density halves. The engine's raw
  number is divided by 1000 before use (`SceneCore.cpp:405`), so the old
  `0.12` meant a **57.8 m** half-height: a near-vertical wall of fog, and
  the hard horizontal line in the pre-2026-08-02 captures.

Current values, set from the terrain's own distribution: datum 150 m,
half-height 300 m, density 0.0015, start 1500 m. Contrast gain measured at
+28% (topdown) and +21% (oblique).

## OWED FROM THE 2026-08-02 REVIEW (24 findings, 17 refuted, 7 survived)

Read-only adversarial review of the massif mask and the relief change.
Camera findings are item 2 above. The rest, with full text:

- **Fog is tuned to a world that no longer exists — RYAN'S CALL, not
  applied.** `height_datum_m` 150 and `half_height_m` 300 were set from
  the OLD height distribution and measured at +28% / +21% contrast gain.
  Fog halves every 300 m above 150 m, so at the new p90 (1078 m) relative
  density is 0.117 where the old p90 (1610 m) sat at 0.034 — **3.4x more
  fog over the top of the world**. Predicted from the arithmetic before
  the capture; the capture agrees, distant terrain washing to a flat
  cream field. Scaling both by the 0.674 the relief moved gives **datum
  101 m, half-height 202 m** and restores the measured relationship
  exactly. Left alone because re-tuning a value that was deliberately
  art-directed is a design call, not a unit fix.
- **FIXED in the same session** (both were defect classes this repo had
  already committed to sweeping, so they are not left owed):
  `report_relief()` took cell spacing from the recipe regardless of
  `--resolution` — lesson 19.2 recurring in the same file that fixed it
  fourteen lines further down; and the NaN sweep covered only the ten new
  flags while thirteen pre-existing float arguments stayed unguarded
  (`--talus nan` propagated into every cell). Both verified by execution.

## STILL BLOCKED / OWED

- **`save_level.py --save` — S1's PREMISE IS DISPROVEN, one small
  hardening awaits your sign-off.** `save_packages()` DOES remove OFPA
  packages emptied by an actor deletion. Chain read at source, every hop:
  `FileHelpers.cpp:6019` → `:5960` → `:5967` → `:5945` → **`:4520-4524`**
  (*"if the package we are saving is considered empty, mark it for
  deletion on disk instead"*) → `ObjectTools::CleanupAfterSuccessfulDelete`
  at `:4536` → `IFileManager::Get().Delete(*PackageFilename)`. Option (ii)
  is moot. What survives is option (iii), now a FIX not a BLOCK: the
  script's own check is still blind, because `still_dirty` is empty
  whether a package was correctly deleted or silently not written. A
  positive on-disk existence check per owned package fixes it. NOT
  implemented — it is still code addressing a BLOCK-raised finding.
  Full text and the two corrections to S1's own reasoning:
  `docs/decisions.md`, 2026-08-02.
- ~~**Lesson-9 sweep: 15 hits unfixed.**~~ **DONE 2026-08-02**, and the
  list itself needed auditing: `verify_landscape` ×3 were NOT defects
  (already fail closed at exit 6), the entry recorded as
  "`delete_stray_landscape` ×2" concealed the most dangerous site of the
  set (the KEEPER PROTECTION SET weakening silently), and
  `landscape_inventory` ×3 were real but of the subtler kind. Only
  `save_level` ×4 remain, deliberately deferred into the S1 work above
  so they are not fixed twice. `docs/lessons.md` §16.
- ~~**Flow and deposition maps not on disk.**~~ **DONE** — written by the
  2026-08-02 canonical regeneration.
- **The engine's heightmap EXPORT tiles** with period 1008 — it reproduces
  vertices 0..1008 and repeats them. Worked around, not fixed: the export
  read-back is a landing check restricted to that region, and the AUTHORITY
  is the pre-import render-target check. Do not widen its sample blocks.

## THINGS THAT WILL BITE A FRESH SESSION

- **Reflected Python names are NOT derivable from headers.** Three live runs
  were lost to invented names this session. The stub is an oracle for
  EXISTENCE only — it is generated from the same headers and inherits their
  misleading parameter names. `landscape_actor_ref` not `landscape_actor`;
  `get_components_by_class` not a `landscape_components` property;
  `create_render_target2d` not `create_render_target2_d`;
  `get_edit_layers_bp` even though the DisplayName is `GetEditLayers`;
  `post_edit_change` does not exist on Texture2D at all.
- **`push_heightmap --push` can exit 5 with a JSON deserialisation error
  and STILL HAVE WRITTEN THE TERRAIN.** The response outgrew the
  transport; the write was fine. Exit 5 means UNKNOWN, so do not retry
  against the editor (conduct rule 6) — settle it read-only with a plain
  `python scripts/push_heightmap.py` dry run, which reports the live
  terrain against the file. On 2026-08-02 that came back identity,
  median |dv| 0.000 units over 1280 vertices, 5/5 blocks 256/256. A
  transport that loses the answer has not lost the fact.
- **The heightmap import applies DEFERRED.** An export taken immediately
  after it reads the PRE-push terrain. `push_heightmap` polls and reports
  its attempt count; do not replace that with a sleep.
- **The first export after an editor restart returns an all-zero target.**
  A discarded warm-up export handles it. Do not diagnose a cold first
  export as a broken draw — that cost a full probe cycle.
- **Conduct rule 7 verifies the PROJECT, not the LEVEL, and a stray editor
  will answer the port.** A `MyProject` editor was open at one point and
  every gate correctly refused. That project now lives in `_trash/`.
- World Partition exposes only LOADED actors. `push_heightmap` forces
  residency; other scripts may not.
- Saving the level saves EVERY dirty external package, not just yours.

## Standing process — CHANGED 2026-08-02

**Full autonomy and design authority, including destructive paths**
(Ryan, 2026-08-02; full text `docs/decisions.md`). No approval gates, no
BLOCK sign-offs, no mandatory audit. Destructive scripts are cleared to
run. Design decisions are yours to make and to record.

Still standing, because none of them require Ryan and all of them catch
your own errors: stay inside REPO_ROOT / UE_PROJECT_ROOT; no recursive
deletes (move to `_trash/`); commit before and after anything
irreversible; no direct `.uasset` edits; stop after two consecutive
live-editor failures and diagnose; verify the connected editor is the
right PROJECT before every remote execution; dry-run destructive work;
identify by property signature, never by label; carry full text in
reports; and say plainly when something was not done or not verified.

**The lessons loop is now the only thing catching defect classes.** With
no independent reviewer in the path, `docs/lessons.md` is load-bearing
in a way it was not before. Append in the same session a defect is
found, never deferred.
