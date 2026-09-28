# Spike v0 — concept image → UE-ready landscape (side project)

**Date:** 2026-08-31. **Input:** `Downloads/side_project/Gemini_Generated_Image_4zvs9q4zvs9q4zvs.jpg`
(AI-generated fantasy concept art, 1408×768). **Question the spike answers:**
does "image → layout brief → existing pipeline" hold up end to end with zero
new ML? **Answer: yes.**

## What ran, in order

1. `analyse_concept.py` — measured lighting from the image: warm sun / cool
   shadow (R-B +0.048 / −0.039), strong aerial haze (min-luma 0.087→0.151
   with distance). Recorded in `layout_brief.json`.
2. **`layout_brief.json`** — the new artifact type this spike tested: terrain
   intent read from the image by eye (9 terrain entities, biome reads, camera
   hypothesis). This is the step a vision model automates in the real tool.
3. `make_alpine_terrain.py` — subdued rolling base, 1009², relief 18%.
4. `composite_stamps.py` — 9 placements from the brief (basin MIN, river
   corridor MIN, 5 rim massifs ADD, south vantage ADD, city rise ADD).
   Result: 55–1214 m, 71% of pixels moved, zero clamping.
5. Adoption per R-STAMP: copy at a stable name, SHA-256 asserted against the
   sidecar (`fdb090ce…`).
6. `derive_aux_maps.py` — flow / deposition / hillshade; source verified
   unchanged by read-back.
7. `find_city_site.py` — found a 25.2 ha basin-floor site at (242 m, 154 m),
   elev 56 m — right where the brief placed the city.
8. `plan_city.py` — **196 buildings, 475 street segments, landmark + spire**,
   with terrain-aware refusals working (107 streets refused on grade, 89 pads
   on cut/fill).
9. `render_preview.py` (spike-local) — hillshade + flow-river + city overlay.

## Verdict per layer

| Layer | Status |
|---|---|
| Lighting from image | measured, in brief; not yet injected into recipe `lighting` |
| Terrain layout from image | **works** — the hillshade reads as the image's bones |
| River | approximated (valley-corridor stamp + flow map); real meander spline is v1 work |
| City | **works end to end** on the new terrain, zero code changes |
| UE import | not run (recipe is import-ready: 1009², section 63×2, legal) |
| Crystal spire / waterfalls / ruins | out of scope v0, as declared |

## What the spike taught (for the tool's design)

- **The brief is the product.** Everything after `layout_brief.json` was
  existing, deterministic machinery. The tool's core job is producing that
  brief from an image — by vision model with human-editable JSON in between.
- **Concept art ≠ photo, and that's fine.** No geometry reconstruction was
  attempted or needed; intent extraction was sufficient to make a terrain
  that reads as the image.
- **Repo tooling has repo-shaped walls**: compositor and generators refuse
  paths outside `terrain/` and REPO_ROOT; recipe schema is strict (datum
  required per ADD, biome_id must match filename, no unknown keys). The
  extraction into a standalone package must carry the gates but parameterize
  the roots.
- **Licensing wall for the tool:** StampIT stamps are Fab-licensed for UE
  projects only — the standalone tool cannot bundle them. It needs its own
  stamp library (public-domain DEM crops are the obvious source).
- **One failure logged** (LESSONS.md 2026-08-31): `draw_city_plan.py` runs on
  any invocation (`--help` included) — it overwrote a committed evidence
  artifact, recovered via git.

## Files

- `layout_brief.json` — image-derived intent (the v0 "vision model output")
- `spike_photo2landscape.json` — schema-valid biome recipe driving everything
- `city_recipe.json`, `city_sites.json`, `city_plan.json`
- `terrain/spike_photo2landscape{_base,_stamped,}.png` + flow/deposition/hillshade
- `preview_full.png`, `preview_city.png`

## Addendum 2026-08-31b — the Gemini stamp-seed experiment, measured

`erode_stamp_seeds.py` (this folder): border crop, JPEG blur, seed-specific
cleanup, then the project's own `hydraulic_droplets` (seed imported from the
generator, 60k droplets), 16-bit output + hillshade.

| seed | verdict | why |
|---|---|---|
| river_basin | **USABLE** | channel + banks + rim survive erosion; faint JPEG blocks in flats |
| terraced_cliffs | usable, soft | terraces survive; droplets add pockmark pits, not channels — smooth gradients give erosion nothing to bite |
| spire_peaks | **REJECTED** | the baked light rays and the mountain skirt share a luma band; the floor-clamp that removes one removes both |

**The class finding:** an image model keeps sneaking LIGHTING into DATA. A
seed is salvageable when its signal and its contamination occupy different
luma bands (river_basin), and unsalvageable when they overlap (spire_peaks).
For the side-project stamp library: request seeds as PNG, prefer landforms
describable as ramps and channels, and treat every seed as needing a
per-seed cleanup judgement — there is no uniform fix. Real DEM crops remain
the primary source; Gemini seeds are the fantastical supplement, at roughly
a one-in-three usable rate on this first attempt.
