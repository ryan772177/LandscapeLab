# Changelog

One line per scene change, per CLAUDE.md hard rule 4.

## 2026-08-02 (evening) — LODs built; 62M triangles/frame -> 6.3M
- **`fir_tree_01_c_LOD0` now has a 4-level chain**, verified by per-level
  triangle count: 505,494 / 126,374 / 30,329 / 7,583 — every level within
  0% of its requested percentage, all four material sections preserved at
  every level, and LOD 0 unchanged.
- **Frame cost, computed from the measured bounding sphere (8.46 m) and
  the 75-degree camera:** 3 trees at LOD0 within 44 m, 14 at LOD1 to
  110 m, 106 at LOD2 to the 300 m cull. **6.3M triangles/frame**, against
  62.2M with the cull alone and 14,306M with neither.
- Captures show no visible difference from the pre-LOD set, which is what
  a correct LOD chain looks like.
- Level saved: 1012 packages, verified on disk.
- `scripts/make_mesh_lods.py` is new; schema v1.12 adds `lods` to a
  species. LOD 0 is deliberately INEXPRESSIBLE in the recipe — see below.

## 2026-08-02 (later) — ruling (c) gates executed live for the first time
- **Both live gates tested in both directions.** `place_foliage --place`
  measured `fir_tree_01_c_LOD0` at pivot 0.0 m horizontal, base 0.0 m,
  bounds [6.3059, 5.9662, 14.5206] m — matching the Blender measurement
  exactly — and placed 28,302 instances. Then the limits were lowered
  below the measured values and BOTH gates refused (exit 4), and
  restoring the limits placed again. A gate that has only seen good input
  has not been tested.
- The measured pivot is now PRINTED on every run. It was being computed
  and gated on without being reported, which makes a passing run and a
  run where the gate never executed look identical.
- `place_foliage` gained `--timeout`; it was the only one of the twenty
  editor-touching scripts without it, and a busy editor took longer than
  the 6 s default to answer discovery — which reads as "no editor is
  running".
- **Level saved: 1222 packages**, verified on disk.
- Recorded but NOT fixed (lesson 23.11): an ad-hoc vendor import of a
  multi-object FBX creates assets for every object in the file, so it can
  overwrite recipe-named meshes even though gate 2 approved the one name
  it was handed.

## 2026-08-02 (late) — real assets in; three silent-wrong defects out
- **Level SAVED: 1227 packages**, verified on disk. The dependency closure
  brought `M_fir_bark`, `M_fir_twig` and `M_grass_medium_01` into the
  allow-list; without them the meshes would have reloaded as
  WorldGridMaterial and reported success doing it.
- **Foliage orphan sweep.** `FT_Scrub` and `FT_Boulder` instances survived
  their removal from the recipe — 28,302 planned against 70,923 in the
  world. Cleared; counts now agree exactly.
- **Every instanced mesh re-imported pivot-normalised.**
  `fir_tree_01_c_LOD0` measured **12.406 m** from its own geometry; all
  23 vendor objects normalised through Blender and verified to 0.0 m
  both in Blender and again off the imported UE asset.
- **Grass rebuilt as five size classes** (tiny / small / mid / tall /
  large) instead of one mesh, density 6 -> 14 per 10 m2 split by share and
  verified to sum back to the species total by read-back.
- **Grass scale corrected from 0.05-0.11 to measured ranges.** The old
  values produced grass 0.7 to 1.6 cm tall, derived from a vendor extent
  that described the whole laid-out set rather than one tuft.
- **New capture camera `forest_floor`**, at eye height in a clearing with
  no trunk within 18 m and 216 within 250 m. The five existing cameras
  are all 1-9 km out and could not resolve foliage at all, so the entire
  foliage milestone had been reviewed with an instrument incapable of
  showing its subject.
- Captures accompany this change: `*_stand.png` (and `*_eye.png`,
  `*_forest.png`, `*_pivotfix.png` from the intermediate steps, kept
  because they are the evidence for the camera lesson above).
- Schema documented up to v1.10; `docs/lessons.md` Session 7 added.
- **Not finished, stated plainly:** the final `forest_floor` capture shows
  no grass meshes at a point whose baked Grass weight is 1.00, and the
  conifers read sparser and smaller than their geometry predicts. The
  editor stopped accepting command connections immediately afterwards, so
  neither was diagnosed. Both are recorded as open item 0 in
  `docs/next-step.md` with the arithmetic beside them and an explicit
  note that no reliable pixel measurement was obtained.
- **Level saved a second time: 1223 packages**, after the editor
  recovered from saturation. The 28,302 conifer instances at their
  corrected pivots are now on disk and verified. Nothing is outstanding.
- The editor became unresponsive three times under heavy load and
  recovered on its own each time; recorded at the top of
  `docs/next-step.md` so it is not misdiagnosed as a crash.


## 2026-08-02 (night) — asset inventory; an unaudited script is now load-bearing
- **`scripts/blender/inspect_fbx.py` originated OUTSIDE the audit gate.**
  Written by Ryan, not produced by this pipeline, and swept into commit
  `951274d` by a `git add -A` that nobody reviewed. It is now
  load-bearing: it supplied `fir_tree_01`'s `mesh_extent_m` (6.306 m,
  source `measured`) and the face-assignment reading that answered the
  Stage 2 material gate. Both facts are now cited in `Free/manifest.json`
  and in Stage 2 reasoning. Extended since (bounding boxes,
  materials-used-by-faces, JSON output) but never audited. Flagged here
  rather than quietly relied on.
- **`Free/manifest.json`** generated by `scripts/make_asset_manifest.py`
  — 9 assets, every file assigned a role, zero unclassified.
- **Size fields split** (ruling 2): `surface_tile_m` for surfaces,
  `mesh_extent_m` for meshes, mutually exclusive, ABSENT never null,
  wrong-field-for-type raises. Provenance carried in `*_source`:
  vendor / assumed / measured.
- **Normals are DX, not GL** (ruling 1) — reversing an asserted fact.
  Consumed directly, no green-channel flip; GL maps marked UNUSED.
- No editor contact, no landscape or material change, level not saved.

## 2026-08-02 (late) — isotropic terrain pushed, saved, captured
- **The lattice grid is gone from the terrain.** Per-octave rotation in
  `_value_noise`; axis/diagonal power ratio 2.015 -> 0.549. The ground
  view now shows ridgelines, spurs and gullies where it showed smooth
  blobs. Captures: `alpine__*__20260802T055432Z__7bee671-dirty_iso.png`.
- **The world gate earned itself.** At the old relief 0.62 the isotropic
  terrain FAILED its own recipe — mount 57.0% crossable, 35.3% in one
  piece — and exited 3 instead of shipping. Decorrelating the octaves
  removed their interference and left the terrain rougher (p50 24.5 ->
  31.6 deg). Relief 0.62 -> 0.48 after a sweep found a percolation
  threshold between 0.52 and 0.48 where mount-in-one-piece jumps
  50.4% -> 94.9%.
- **Adopted world:** walk 92.7% / 99.7% in one piece, mount 72.1% /
  94.9%, border flat 3.3%, max height 1229 m, 26 peaks. Bands retuned
  against the bake: Snow 22.19 / Rock 32.68 / Grass 45.12, none
  unmatched.
- **Cameras re-derived**, including `player_eye`, which was framed
  against the old terrain and came back at 100% fill — the new ground
  had risen above it. Re-derived from the new heightmap: eye 142 m,
  763 m rise, 51.5% fill.
- Pushed, verified PASS, material assigned, lighting applied, **level
  SAVED (257 packages, all verified on disk)**.
- **STILL PRESENT AND NOW ISOLATED: a texture weave.** A regular
  diagonal crosshatch on the tan slopes in the ground view. It is NOT
  the heightmap — that is fixed and measured. It is the layer textures
  themselves (`make_layer_textures.py`) or their tiling. Next.
- Also visible: "rock" renders tan/sand rather than the recipe's dark
  grey `base_color` [0.22, 0.22, 0.24], because albedo is
  `base_color * 4 * texture` and the texture hue dominates.

## 2026-08-02 (night) — THE LEVEL IS SAVED, and S1 is closed
- **`save_level.py --save` ran for the first time in the project.** 257
  packages: `Landscape_Alpine` + 256 streaming proxies. Engine reported
  success, every owned package came back clean, and **every one was
  verified present on disk**. `/Game/Debug/T_PushHeight_Source` correctly
  excluded — it is a scratch asset, not recipe-governed.
  Captures: `alpine__*__saved.png`.
- **The world is no longer editor-memory-only.** Every previous handoff
  since the first milestone has said "Level NOT saved". It is saved.
- **S1 CLOSED.** Half disproven at source (`save_packages` DOES delete
  emptied OFPA packages, `FileHelpers.cpp:4520-4524` →
  `CleanupAfterSuccessfulDelete` → `IFileManager::Delete`), half fixed:
  the surviving blindness is now an ON-DISK check, host-side and outside
  the engine's own bookkeeping, so a deletion is verified as a missing
  file and a package written-by-nothing/deleted-by-nothing is exit 5
  rather than silence.
- **Autonomy grant recorded** (Ryan, 2026-08-02): full autonomy and
  design authority including destructive paths. Approval gates, conduct
  rule 8 and the mandatory audit gate are retired; the error-detection
  rules are kept and the reasoning for keeping them is in
  `docs/decisions.md` so the grant is not later read as "delete the
  safety code".

## 2026-08-02 (evening) — v1.5 gates, lesson-9 sweep, S1 disproven
- **A world can now be REFUSED for missing its own target.** Schema v1.5
  `world` block; `make_alpine_terrain` exits 3. Tested both ways: the
  adopted world passes, the old island world refuses on the flatness
  ceiling *while passing the connectivity target* — which is the whole
  argument for pairing them in one measurement. End-to-end refusal
  confirmed by generating a deliberate island.
- **Snowline jitter** (`material.height_jitter_m` 45 m / scale 700 m),
  applied ONCE to the elevation so Snow's lower bound and Grass's upper
  bound wander together instead of opening a seam. Baked coverage
  21.6 / 30.9 / 47.6, nothing unmatched, two bakes byte-identical.
  Captures: `alpine__*__20260802T042152Z__f009497-dirty_jitter.png`.
- **`push_tolerance_units` may only TIGHTEN** the built-in 4. Audit D1 was
  a self-widening tolerance; a recipe-settable budget with no ceiling
  re-creates it with an extra step.
- **Lesson-9 sweep done, and the LIST was wrong.** `verify_landscape` ×3
  were not defects; the `delete_stray_landscape` entry concealed the
  worst site in the set — a swallowed read dropped a keeper's proxy out
  of the KEEPER PROTECTION SET while the same proxy could still reach the
  kill list, so the safety assertion could pass with a keeper queued for
  deletion.
- **S1 disproven at source.** `save_packages()` DOES delete OFPA packages
  emptied by an actor deletion (`FileHelpers.cpp:4520-4524` →
  `ObjectTools::CleanupAfterSuccessfulDelete` → `IFileManager::Delete`).
  Option (ii) moot; option (iii) survives as a FIX awaiting sign-off.
- Level NOT saved.

## 2026-08-02 (later still) — cameras re-framed by measurement, fog rescaled
- **`snowline_detail` went from 98% sky to a summit portrait.** It sat at
  world Z 1900 m with pitch 0 against a 1587 m ceiling — above every piece
  of ground in the world. Captures:
  `alpine__*__20260802T040039Z__bae4d1a_framed.png`.
- **New instrument, `scripts/frame_cameras.py`.** Raymarches the real
  heightfield and reports terrain fill per camera, no editor involved.
  Calibrated against all four previous renders before being trusted, and
  its reading of the old world (31.9 / 86.6 / 37.4) independently
  reproduces a raymarch written by a review agent that never saw it.
- **`--preserve-from` is the part worth keeping.** Each camera targets the
  fill it achieved on the world it was ART DIRECTED against, per camera,
  rather than a global number. Restoring a composition is the job.
  | camera | Z | terrain fill | intended |
  |---|---|---|---|
  | ridge_wide | 2600 → 2248 m | 24.0% → **31.8%** | 31.9% |
  | diag_oblique | 3000 → 2737 m | 80.7% → **86.7%** | 86.6% |
  | diag_topdown | unchanged | 81.1% | 77.5% |
  | snowline_detail | 1900 → 1527 m | 2.2% → **37.6%** | 37.4% |
- **`capture.py` now has an altitude gate.** Hard error when it is provable
  no terrain can be in frame; warning when a provable upper bound on frame
  terrain content falls below 45%. Took two calibrations: keying on "camera
  above the ceiling" fired on all four cameras including the flawless
  top-down, and 0.60 flagged `ridge_wide`, which is meant to be sky-heavy.
- **Fog rescaled**, `height_datum_m` 150 → 101, `half_height_m` 300 → 202,
  restoring the relative density at the terrain p90 from 0.117 back to
  0.035 — the relationship that was originally tuned.
- **HONEST LIMIT ON THAT LAST CLAIM.** Fog and camera altitude changed in
  the SAME capture cycle, so three of four frames are confounded and no
  image-level claim can be made for the fog. The one camera that did not
  move, `diag_topdown`, changed by **+0.8% contrast — nothing** — which is
  consistent with the datum governing horizontal sight lines a top-down
  does not have. Recorded as `docs/lessons.md` §21.7: when a capture cycle
  is the measurement, change one thing per cycle.
- Level NOT saved.

## 2026-08-02 (later) — MASSIF MASK: the world reaches its edges
- **Terrain now fills the whole map.** The radial mask confined every world
  to a disc; it is replaced by N best-candidate massif centres joined by a
  minimum spanning tree of ridge corridors, over a floor that keeps the
  outskirts as foothills. `--edge-falloff` REMOVED — no value of a single
  radial term puts mountains on a border.
  Captures: `alpine__*__20260802T031901Z__a89faf9-dirty_massif.png`.
- **New metric, `terrain_erosion.composition()`.** Local relief over 250 m
  windows, flat fractions, and an edge ratio. It is what made the island
  falsifiable: 82.9% of the map BORDER carried under 20 m of relief, and
  no existing gate could see it — traversability scores a billiard table
  100% crossable in one piece.
- **THE FINDING OF THE DAY: the old headline number was being paid by the
  defect.** `mount-in-one-piece 84.9%` was substantially the dead frame
  itself — the flattened third of the map WAS the largest connected
  rideable region. Filling the map dropped it to 22.1%.
- **And the lever was not the one I was sure of.** Mask floor 0.30 -> 0.10
  bought 22.1% -> 28.3% while letting flat ground back to 13.8% of the
  border. The cause was total relief: 2355 m across 8064 m is Himalayan.
  `--relief` 0.92 -> 0.62 (world max 1587 m) moved it to 92.1%.
- **Adopted world vs the one it replaces:**
  | | old | new |
  |---|---|---|
  | walk crossable | 81.2% | **90.5%** |
  | walk in one piece | 87.5% | **99.7%** |
  | mount crossable | 68.4% | **72.9%** |
  | mount in one piece | 84.9% | **92.1%** |
  | map border flat | 82.9% | **1.3%** |
  | slope p50 | 22.1 deg | 24.5 deg |
- **Layer bands retuned against the BAKE, not against a model of it.** The
  hard-bound search said Snow 22.05%; the bake said 27.58%, because the
  material feathers the height bound outward by 115 m. Final baked
  coverage **Snow 21.79 / Rock 30.70 / Grass 47.51**, nothing unmatched.
- **The push returned exit 5 (UNKNOWN) — the response was too large to
  deserialize — and the write had in fact landed.** Settled read-only by
  the export read-back: identity orientation, median |dv| **0.000 units**
  over 1280 vertices, all 5 blocks 256/256 within tolerance. Not retried
  against the editor; measured instead (conduct rule 6).
- **NOT DONE, and visible in the capture: the fog is now mis-scaled.**
  `height_datum_m` 150 and `half_height_m` 300 were tuned against the old
  height distribution. Fog halves every 300 m above 150 m, so at the new
  p90 (1078 m) relative density is 0.117 where the old p90 (1610 m) sat at
  0.034 — 3.4x more fog over the top of the world. Predicted from the
  arithmetic BEFORE the capture, and the capture agrees: distant terrain
  washes to a flat cream field. Scaling both by the 0.674 the relief moved
  (datum 101 m, half-height 202 m) restores the measured relationship
  exactly. Left for Ryan — those values were tuned and measured (+28% /
  +21% contrast), and re-tuning them is an art call, not a unit fix.
- `ridge_wide` and `snowline_detail` still framed for terrain that no
  longer exists — next-step item 2, unchanged.
- Level NOT saved.

## 2026-08-02 — FULL LOOP: generate -> push -> material -> capture, scripted
- **The pipeline ran end to end with no dialog and no hand-work.** Eroded
  terrain generated, heights pushed by script, weightmap re-baked and
  imported, material rebuilt and assigned, four cameras captured:
  `alpine__*__20260802T021437Z__21f7ea9-dirty.png`.
- **First CHANGED push.** `--push --expect-change` wrote genuinely
  different terrain, which the previous push could not do (audit D4).
  `verify_landscape.py` PASS afterwards — 1024 components, 2017x2017,
  scale 400/400/500.
- **Terrain quality is up where it was measured to be down.** Old vs new,
  on the traversability gates:
  | mode | old | new |
  |---|---|---|
  | walk crossable | 52.0% | **81.2%** |
  | walk in one piece | 50.8% | **87.5%** |
  | mount crossable | 18.6% | **68.4%** |
  | mount in one piece | 1.3% | **84.9%** |
  | climb | 98.5%, 10 regions | **100%, 1 region** |
  The terracing, the stair-steps and the dark ridgeline spikes are gone.
  Layer bands retuned to the new distribution: Snow 22.2 / Rock 29.4 /
  Grass 48.4, nothing unmatched.
- **A REAL DEFECT FOUND BY THE FIRST CHANGED PUSH, and it would not have
  shown up any other way.** The post-push verification failed with all
  1280 vertices ~16000 units out — then a re-read moments later matched
  the source EXACTLY at median 0.000. The import applies DEFERRED, so an
  export taken immediately after it reads the pre-push terrain. The write
  was always correct; the check was early. Verification now polls and
  reports the attempt count rather than sleeping a magic number.
- **What the capture shows, and it is not a rendering fault:** the massif
  is an island in a low fog-filled plain, and the cameras still frame the
  old layout. Predicted from the hillshade before the capture was taken —
  the massif mask confines terrain to a circle and leaves roughly a third
  of the map flat. That is the next lever, not erosion parameters.
- Level NOT saved.


## 2026-08-01 (night) — P0 DONE: heights pushed by script, dialog retired
- **`scripts/push_heightmap.py --push` executed against `/Game/Alpine` and
  the terrain was written by script for the first time.** The New Landscape
  dialog is no longer on the heightmap iteration path.
- **Verified, in three independent ways:**
  1. **Primary — the pre-import render-target check.** 2304 texels across
     9 blocks spanning the whole terrain, **0 mismatches**, `rt_min 0.5`,
     `rt_max 45995.5` (non-flat, and exactly the `v + 0.5` encoding). This
     reads the buffer that is about to be written, before the write.
  2. **Post-push export read-back**: all 5 blocks **256/256 within
     tolerance**, orientation `identity`, median |dz| **0.00 cm**, encoding
     confirmed at median 0.000 units.
  3. **`verify_landscape.py` PASS** — 1024 components (32x32), 2017x2017,
     scale 400/400/500. Geometry undisturbed by the height write.
- Engine's own evidence: `LogLandscapeBP: Took 1.114571 seconds to import
  heightmap from render target`, and the payload reported
  `stage: done, engine_returned: true`.
- **The host lost the response** ("Remote party failed to send a valid
  response") and correctly reported terrain state as UNKNOWN rather than
  guessing. The log and the follow-up verification are what resolved it —
  the transport failed, the push did not.
- Texture settings all read back as set: `TC_HDR_F32`, `srgb False`,
  `TMGS_NO_MIPMAPS`, `TF_NEAREST`, `TA_CLAMP`, built size `[2017, 2017, 1]`.
- **This push was IDEMPOTENT by design** — the same heightmap the terrain
  was already built from — so it proves the mechanism, not that changed
  terrain lands. That is what P1's first eroded heightmap will exercise,
  and audit finding D4 governs it.
- **Level NOT saved.** The heights are in editor memory; a reload reverts
  them to the on-disk terrain, which is identical anyway.


## 2026-08-01 (evening, later) — sepia stain SOLVED; captures now unattended
- **DIAGNOSTIC captures** `*__193740Z__bc19d3e-dirty_debug4.png`, all four
  cameras, exit 0, **taken with the editor deliberately MINIMIZED**.
- **CAPTURE STALL FIXED AT THE ROOT.** Ryan ruled: turn off "Use Less CPU
  when in Background". With
  `EditorPerformanceSettings.bThrottleCPUWhenNotForeground = false`, the run
  that had stalled indefinitely twice completed every camera while
  minimized. Captures no longer require anyone to be looking at the editor.
  Scope note: this wrote to a MACHINE-GLOBAL editor config outside both
  roots — see `docs/decisions.md`.
- **THE SEPIA STAIN IS ATMOSPHERIC INSCATTER.** Not the material, not a band
  leak, not a texture tint. Measured, not eyeballed: in the UNLIT debug
  frame the material emits `G = 0` for Snow, yet G over the near face
  measures 211-255 (mean 225 of 255) — **all of it atmosphere, because the
  material cannot produce it**. The stain region carries **+11.6 G** more
  atmospheric contribution than adjacent terrain at the same depth on the
  same layer; in the shipping frame that same region swings **33 points
  warm** (R-B of +9.6 against -23.5 adjacent). The layer under the entire
  stain is uniformly Snow.
- **Consequence for the lighting pass (P3), from the same measurement:**
  atmosphere is contributing roughly 88% of near-field pixel value at
  `snowline_detail` range. The fog is not "adding depth" there, it is
  **drowning the terrain** — which is also why the massif reads as flat
  fabric: inscatter is eating the contrast that would show form. Reduce
  density or push `start_distance_m` out before touching anything else.
- Landscape reverted to `/Game/Materials/M_AutoLandscape`.

## 2026-08-01 (evening) — DIAGNOSTIC: sepia stain is NOT a layer leak
- **DIAGNOSTIC captures, not scene output.** `_debug` / `_debug2` suffixes,
  produced by `/Game/Debug/M_LayerDebug`, now written by `capture.py`'s new
  `--filename-tag` instead of a manual rename.
- **The debug instrument was corrected before it was trusted.** It built its
  masks from the VERTEX NORMAL — the measurement the baked weightmap exists
  to replace — so it would have visualised a decision the shipping material
  no longer makes. It now samples the weightmap through the shared
  `weightmap_uv_params`, and is unlit/emissive so lighting cannot tint the
  readout. Details: `docs/lessons.md` §14.5-14.6.
- **Result (`alpine__ridge_wide__20260801T185857Z__325ca11-dirty_debug2.png`):
  the layer assignment is clean.** Magenta (Snow) caps the massif, cyan
  (Rock) dominates as the 75.44% figure predicts, yellow (Grass) appears as
  sparse specks, and there is **no near-black "unmatched" anywhere** — no
  coverage gap and no band anomaly through the couloir where the stain is.
- **Conclusion: the sepia stain is not the grass/rock band leaking.** It is
  lighting or fog inscatter. **Not yet narrowed further, and stated rather
  than guessed:** the frame that would settle it — `snowline_detail` in
  false colour, which is where the stain actually is — was not obtained,
  because the capture run stalled twice (see below) and conduct rule 6 says
  stop after two.
- Landscape **reverted to `/Game/Materials/M_AutoLandscape`** and confirmed
  by live read-back. The scene is back to its shipping state.
- **Capture stall, third refinement — a NEGATIVE result worth having.**
  Un-minimizing is not sufficient; the editor must be the FOREGROUND
  application. `EditorSetViewportRealtime(true)` and
  `EditorInvalidateViewports()` were both wired in, both reported success on
  every poll, and the screenshot still never serviced. Bringing the window
  to the front completed it in seconds, every time. The remaining lever is
  the "Use Less CPU when in Background" editor preference — Ryan's call, not
  taken. Full text: `docs/lessons.md` §14.7.

## 2026-08-01 (later) — FIRST RENDER of the baked weightmap; throughput solved
- **All four cameras captured at `251a1bb`, exit 0**, fully resident (1 of 1
  landscape, 256 of 256 proxies), level gate passed on `/Game/Alpine`:
  `alpine__ridge_wide__20260801T181704Z__251a1bb.png`,
  `alpine__diag_oblique__…`, `alpine__diag_topdown__…`,
  `alpine__snowline_detail__…`. First images of the CPU-baked weightmap
  material committed at `30bf698`.
- **The layers separate and they are placed where the recipe puts them.**
  Snow caps the high massifs, rock carries the ridgelines and the mid
  slopes, grass appears as sparse green in the low flats. `ridge_wide` is a
  genuine golden-hour establishing shot — layered ridgelines receding into
  haze under a clouded sky. The all-snow render is gone.
- **What these frames do NOT show, stated rather than glossed: terrain-wide
  coverage.** All four cameras aim at the 2349 m peak, so every frame is
  snow-dominated by composition. Frame coverage is not terrain coverage and
  no coverage claim should be read off these images. The terrain-wide
  numbers were instead verified from the SHIPPED weightmap bytes:
  **Snow 20.76% / Rock 75.44% / Grass 3.80%**, channels summing to 1.0000
  (min 0.9961, max 1.0039 — inside the 1/255 quantisation bound). That is
  what the shader samples, and it matches the bake's own self-check exactly.
- **NOTHING WAS SAVED, because there was nothing to save.** `save_level.py`'s
  dry run reported **zero dirty packages**. The handoff note "Level still NOT
  saved", carried through three sessions, was stale: the material assignment
  was persisted earlier, and `a853f8f` deleted the four stray lighting actor
  packages from git. Live read-back confirms `LandscapeMaterial =
  /Game/Materials/M_AutoLandscape` on `Landscape_Alpine`.
- **Capture throughput: root-caused, and it was two separate faults.**
  (1) The 1h49m/6h51m gaps were **Windows Modern Standby** — the engine's
  frame counter went `[842]` to `[843]` across 108 minutes, and Kernel-Power
  event 507 lands within seconds of each delayed screenshot. (2) With that
  fixed, this run still stalled 11 minutes on shot 1 while ticking at 3 FPS:
  **the editor window was MINIMIZED**, and a minimized editor never draws the
  viewport the screenshot is latched on. `ShowWindow(SW_RESTORE)` completed
  the pending shot within seconds and the other three followed immediately.
  Full text: `docs/lessons.md` §14.
- **Still open, unchanged by this run** (both pre-existing, neither caused by
  the weightmap): `diag_topdown` at 9 km still renders with missing
  axis-aligned World Partition cells; and the detail texture still shows a
  visible repeating lattice at `snowline_detail` range.

## 2026-08-01 (overnight) — mask fix CONFIRMED; snow now dominates
- Post-fix captures at `cdd5329` confirm the mask defect is fixed: **snow
  renders**, which was mathematically impossible before (its slope mask was
  identically zero over the entire terrain).
- **New problem, revealed rather than caused by the fix:** the layers now
  select almost entirely SNOW, at 8.7 km (`ridge_wide`) AND at 4.2 km
  (`diag_oblique`). The close camera rules out LOD-at-distance.
- **Cause is a measurement mismatch.** The numpy prediction (Snow 41.71% /
  Rock 49.06% / Grass 9.23%) derives slope from `np.gradient` on the 4 m
  heightmap grid, where erosion detail gives a MEDIAN slope of 44 deg. The
  shader reads the landscape's VERTEX NORMAL, which is far smoother. Flatter
  normals push normal.z toward 1, so Snow's [0, 52] band matches nearly
  everywhere above its 1200 m line - and half the terrain is above it, mean
  height 1260 m - while Rock's [35, 90] matches almost nowhere. The recipe's
  slope thresholds were tuned against a measurement the shader does not make.
- Recorded, NOT unilaterally changed: this is art direction. Options are to
  raise the snow line, lower Rock's slope threshold, or derive slope from the
  heightmap instead of the vertex normal.
- **Capture throughput has collapsed**: the three shots in this run landed
  1h49m and then 6h51m apart, and the fourth never completed. Worth
  investigating before the next capture-heavy session.
- Level still NOT saved.

## 2026-08-01 (final) — both recipe cameras render textured terrain
- **Root cause of the empty frames found: a capture camera parked OUTSIDE the
  landscape footprint renders nothing.** World Partition streams around the
  camera as a streaming source; parked beyond the loaded regions there is
  nothing to stream. The split was exact - `diag_oblique` (-3000,-3000) and
  `diag_topdown` (0,0) are INSIDE the +/-4032 m footprint and rendered;
  `ridge_wide` (-6200,-6200) and `snowline_detail` (-4800,-4800) were OUTSIDE
  and rendered nothing. Not fog, not aim, not distance, not LOD - all four
  were tested and eliminated first, and the terrain-elevation arithmetic
  confirms both old cameras had terrain in frame the whole time.
- `ridge_wide` moved to (-3800,-3800,2600) pitch -6 yaw 67.7, and
  `snowline_detail` to (-3200,-1200,1900) pitch 0 yaw 57.7 - both inside the
  footprint, both aimed at the real peak at (-1876, 896, 2349).
- **Both now render textured terrain.** `ridge_wide` is a proper wide ridge
  shot with layered ridgelines receding into fog.
- Stray lighting rig DELETED (4 actors: DirectionalLight, ExponentialHeightFog,
  SkyLight, SkyAtmosphere under UAID_A85E45CFE40401D200). Verified exactly one
  of each class remains, and it is ours. **NOT SAVED** - reverts on reload.
- **New finding, from the close-up:** at `snowline_detail` range the detail
  texture shows a VISIBLE REPEATING LATTICE in shaded areas. The macro scale
  holds at distance, but the 2 m detail tile is legible close up. Open.
- No snow is visible in either camera despite peaks at 2349 m against a
  1200 m snow line. Not yet investigated.

## 2026-08-01 (later still) — TEXTURED MATERIAL RENDERS. Milestone visually confirmed.
- `alpine__diag_oblique__20260801T071252Z__1c77b24-dirty.png` is the first
  ground-level image of the textured auto-material and it works: green meadow
  on gentle slopes, pale rock exposed on steep faces and ridge lines, with
  large-scale patchy variation across hundreds of metres. Slope-based layer
  separation is doing exactly what the recipe asks.
- **The two flagged texture risks, assessed against the image:**
  - `E[det*mac]` mid-field HOLDS. Variation reads as coherent terrain at
    several km; no visible tiling, repetition, or flat wash. The macro scale
    is doing the work it was added for.
  - Far-corner UV shimmer: **NOT ASSESSABLE from a still.** Shimmer is
    temporal, and the far field here is fog-obscured. Recorded as open, not
    as passed.
- **Remaining defect: the landscape does not render at long range.** Oblique
  at ~4.2 km renders fully; top-down at 9 km renders in blocks with voids;
  `ridge_wide` (3-14 km) and `snowline_detail` render NOTHING. The pattern is
  distance-dependent with hard axis-aligned edges, which points at World
  Partition cells without built HLOD rather than at geometry - `verify_landscape`
  PASSES on complete state (1024 components, 2017x2017, scale 400/400/500).
  Next thing to try: Build > Build HLODs.
- Stray fog (density 0.0436, StartDistance 0) left HIDDEN, unsaved.
- `apply_lighting.py` gained an exactly-one gate (new exit 6) - see below.

## 2026-08-01 (later still) — FIRST RENDER of the textured material
- `/Game/Alpine` opened interactively; `verify_landscape.py` **PASS** on fully
  resident state (1024 components, 32x32, 2017x2017, scale 400/400/500). The
  level gate's SUCCESS path ran clean for the first time, closing the auditor's
  standing caveat.
- Captures: `alpine__ridge_wide__20260801T062709Z__283cabd-dirty.png`,
  `alpine__snowline_detail__...`, `alpine__diag_topdown__...`.
- **The textures WORK.** The top-down diagnostic shows the slope/height blend
  rendering with real per-layer variation - green meadow, tan rock, organic
  macro patchiness at hundreds of metres. That was the milestone's goal.
- **But large chunks of terrain do not render**, including the centre, which is
  where both ground cameras aim - so `ridge_wide` and `snowline_detail` are
  empty sky and fog. ONE root cause, not three. Geometry is verified intact, so
  this is a render/streaming state problem, not a torn landscape.
- Added a `diag_topdown` camera to the recipe. Straight down from 9 km; it is
  what isolated "is the terrain rendering" from "is the camera aimed wrong".
- The UE warning `LandscapeStreamingProxy_14_3_0 ... TargetLayers` is the
  documented benign deprecation fixup (decisions.md 2026-07-28). It fires on
  LOAD, so forcing residency on all 256 proxies is simply what made the engine
  look. Not damage.

## 2026-08-01 (later) — attempted render; editor became unreachable
- **NO CAPTURE, AND THE MATERIAL HAS STILL NEVER BEEN RENDERED.** Stated
  plainly rather than omitted (lesson 4.9). The textures milestone is NOT done.
- Level gate wired into `verify_landscape.py` at a new **exit 7** (audited PASS,
  Ryan approved the code). Its first live run correctly refused on
  `/Temp/Untitled_1`. **Its success path against `/Game/Alpine` has still
  never executed.**
- New `scripts/open_level.py` (audited PASS, 11 auditor corrections). Dry run
  reported no dirty map, actor, or content packages, so nothing was pending in
  the open untitled level. The real run reached `load_level` and returned
  **exit 5**: the remote-exec connection was reset mid-load and the script
  reported the editor's state as UNKNOWN rather than guessing.
- **Scripted `load_level('/Game/Alpine')` appears to CRASH the editor —
  reproduced twice.** Both attempts ended in `ConnectionResetError` at the same
  point, and a `CrashReportClientEditor` process is running (started 7/31
  22:44:33) alongside a `UnrealEditor` that is still PID 35796 from 7/27 at
  ~0.13 GB with no world loaded. Correlation is strong; root cause is NOT
  established, so this is recorded as an observation, not a diagnosis.
- Between the two attempts the editor was reported restarted, but **PID and
  StartTime were unchanged** — the crash reporter was holding the dead process
  open, so no restart had actually taken effect.
- No scene change was made and no asset was written by either attempt.
- **Next step is the INTERACTIVE path:** dismiss the crash reporter, let the
  editor process exit, relaunch, and open `/Game/Alpine` from the editor UI
  (File → Open Level). That path does not run under
  `GIsRunningUnattendedScript` and shows a real progress bar. `open_level.py`
  is unaffected as a gate — it refused correctly and never reported success.

## 2026-08-01 — textures (asset changes only; scene NOT updated)
- **NO CAPTURE ACCOMPANIES THIS ENTRY, and the scene is unchanged.** Stated
  plainly per lesson 4.9 rather than omitted. The editor had an unsaved
  `/Temp/Untitled_1` open instead of `/Game/Alpine`, so the material could not
  be assigned and nothing could be photographed. See `docs/decisions.md`,
  2026-08-01, "Level identity is a recipe parameter".
- Imported `/Game/Textures/T_Alpine_Snow`, `T_Alpine_Rock`, `T_Alpine_Grass`
  (1024x1024, BC7, srgb=False, TA_WRAP, TEXTUREGROUP_WORLD), each verified by
  read-back. Sources are `textures/alpine_*.png`, generated by the new seeded
  `scripts/make_layer_textures.py`.
- Rebuilt `/Game/Materials/M_AutoLandscape` from the recipe with per-layer
  texturing at two world-space scales — **compiled clean** — but it is
  **NOT assigned to any landscape**, because the assign step correctly
  refused. The asset on disk is textured; the scene still shows the previous
  material until a run against `/Game/Alpine` assigns it.
- Deleted `/Game/Debug/M_ApiProbe`, a scratch asset created this session to
  read TextureSample pin names and removed in the same session.
- R2 closed: the debug material now imports its feather constants from
  `make_landscape_material` instead of carrying its own. The caveat recorded
  on 2026-07-31 (below) that debug coverage is not comparable because the
  widths differ is **resolved** — they are now identical by construction.

## 2026-07-31 (later)
- **DIAGNOSTIC**, not scene output. Full layer-debug capture pair at the
  re-derived camera framing, first run with `fov_deg` actually reaching the
  engine: `alpine__ridge_wide__20260731T232408Z__cde83b1-dirty_debug.png` and
  `alpine__snowline_detail__20260731T232408Z__cde83b1-dirty_debug.png`.
  Exit 0, residency confirmed (1 landscape, 16 of 16 proxies). `ridge_wide`
  took ~90 s (shader warm-up), `snowline_detail` returned promptly — the 900 s
  ceiling was never approached.
- Blend geometry confirmed terrain-wide: bands land where the recipe places
  them, feathering is smooth, **no unmatched samples anywhere**. Caveat on the
  record: rendered coverage is *not* directly comparable to the numpy
  prediction, because feather widths in the debug material are instrument
  constants, not recipe-derived (audit finding R2, still open).

## 2026-07-31
- **DIAGNOSTIC, not scene output.** Created `/Game/Debug/M_LayerDebug`, the
  layer-visualisation material (Snow magenta, Rock cyan, Grass yellow,
  unmatched near-black); compiled clean; assigned to `Landscape_Alpine`
  **in memory only** — the level was not saved, previous material was `None`.
- **DIAGNOSTIC capture** (corrected entry — see below):
  `alpine__snowline_detail__20260731T221353Z__f1c2a13-dirty_debug.png`.
  Layer-debug render; blend geometry confirmed sound, full coverage, no
  unmatched samples.
- *Correction to the entry originally filed here:* it stated that no capture
  accompanied this change and that `camera=` had regressed
  `take_high_res_screenshot`. **Both were wrong.** The engine logged
  "High resolution screenshot saved as …" at 22:23:47 — ten minutes after the
  request and about six minutes after the script's 120 s wait had already
  declared failure. The filesystem sweep that "found nothing" simply ran too
  early. The capture was slow (shader compilation after a new material), not
  broken.

## 2026-07-29
- Deleted stray landscape `Landscape` (2017 geometry, default scale) and its 64
  streaming proxies; `Landscape_Alpine` and its 16 proxies untouched. Level
  saved. Captures: `alpine__ridge_wide__20260729T041024Z__90ad0f1-dirty.png`,
  `alpine__snowline_detail__20260729T041024Z__90ad0f1-dirty.png`.
- **RETROACTIVE** — sculpt dent accepted on `LandscapeStreamingProxy_1_1_0`
  (owner `Landscape_Alpine`), saved earlier at commit `07865c5` with capture
  pending because `capture.py` could not run against the then-broken
  two-landscape scene. The captures listed above are the first images of the
  scene and therefore include this dent; they are the retroactive coverage for
  it. Pre-dent bytes remain recoverable at `3ca1771`.

## 2026-07-27
- Repo scaffolded; git initialised with baseline commit. No scene changes yet.
