# Street flattening — design (2026-10-10, Ryan: "do the street flattening next")

Status: DESIGN, pre-review. Nothing built. Open item from R-TOWNKIT AMENDED 2026-10-10b: *"Streets follow terrain
undulation (cut/fill up to 1.8 m): Landscape Patch / heightmap flattening is the next street-quality step."*

## The problem, measured

The cobble is part of the landscape surface (`material.street_overlay`), so the streets have exactly the terrain's
bumps. The plan gated each street piece at <= 1.8 m deviation of natural ground from the straight run between its
ends (plan_city `street_gates`). Measured over all 371 pieces, every 0.5 m, on the shipped heightmap
(`_verify/streets_flatten/prototype_*.json`): **deviation from chord p90 0.83 m, max 1.74 m.**

## Approach, ruled here: an OFFLINE HEIGHTMAP EDIT + PUSH (the R-WATER-CARVE precedent)

- **Not Landscape Patch / edit layers.** The heightmap PNG is the world's recipe source
  (`recipes/alpine_8k.json heightmap.source`). The proven push path (`push_heightmap.py`, R-WATER-CARVE step 1)
  changes heights only and keeps the landscape geometry. A patch actor would be a second, editor-side source of
  truth for heights that no offline tool (planners, foliage, reachability) reads. Standing rule 4 and pipeline
  rules 2 and 3 point the same way. `carve_water_notches.py` already did exactly this kind of edit.

### The surface (prototype variants compared; chosen = sigma 4, smooth, apron 3)

| variant | street abs-delta p50/p90 | doorsteps > 0.3 m (of 349) | chord deviation after p90/max |
|---|---|---|---|
| level across width, sigma 4 | 0.16 / 0.42 m | **105** | 0.30 / 0.88 m |
| keep cross-slope ("smooth"), sigma 4 | 0.12 / 0.34 | 16 | 0.29 / 0.88 |
| level, sigma 4, door apron 3 m | 0.16 / 0.42 | 14 | 0.30 / 0.88 |
| **smooth, sigma 4, door apron 3 m** | **0.12 / 0.34** | **0** (p90 0.13 m) | **0.29 / 0.88** |
| smooth, sigma 8, door apron 3 m | 0.19 / 0.50 | 10 | 0.17 / 0.83 |

How the chosen surface is built:
- **S** = the natural heightmap Gaussian-smoothed at `sigma_m` 4. On a street, the target is S. This removes the
  bumps and keeps the natural cross-slope. Levelling across the width was rejected: houses stand on traced
  ground at their door edge, so a levelled street leaves 105 doors on a step over 0.3 m.
- **Plaza and squares:** a least-squares plane of the natural ground over each disc.
- **Blend:** alpha 1 on the street (signed distance <= 0), smoothstep to 0 across `shoulder_m` 3.
  - Houses: alpha is 0 inside every house footprint + `guard_m` 0.5. Houses are NOT moved.
  - Doors: alpha is multiplied by smoothstep(distance to the door-edge midpoint / `door_apron_m` 3), so every
    threshold stays on its own ground.
- **New height:** H' = H + alpha (T - H), quantised to the uint16 grid.

## Sources and idempotency

- `terrain/alpine_8k_prestreets.png` (NEW) holds the CURRENT shipped heights, copied once and recorded by sha256.
  `flatten_streets.py` always reads it and writes `terrain/alpine_8k.png`, so a re-run is deterministic and never
  flattens twice.
- **plan_city reads the pre-streets source.** `Terrain` reads `heightmap.street_flatten.pre_source` when it is
  declared. Otherwise a town re-plan would gate streets on already-flattened ground, a circular input.
- New recipe block `heightmap.street_flatten`:

  ```
  {pre_source, sigma_m 4.0, shoulder_m 3.0, guard_m 0.5, door_apron_m 3.0, max_abs_delta_m, doorstep_max_m 0.30}
  ```

  It has a schema row and validator. Absent block = no flattening, and the heightmap source is used directly.

## Gates in flatten_streets.py (refuse = nothing written; counts printed, a 0 count refuses)

1. **Locality.** The changed set (|delta| >= 1 quantum) lies inside the union of streets + discs grown by
   `shoulder_m`. Outside the town box the result is byte-identical to the source.
2. **Houses.** Every house footprint + `guard_m` is byte-identical to the source (349 footprints).
3. **Doorsteps.** |delta| at each doorstep (trace point + 1.5 m along the door normal, the reachability tool's own
   convention) is <= `doorstep_max_m`.
4. **Bound.** |delta| <= `max_abs_delta_m` everywhere. The prototype max is 3.3 m, on a square disc (see Q4).
5. **Effect.** Centreline deviation from chord: p90 after < p90 before, and the result is printed. A
   flattening that does not flatten refuses.
6. **Consumers.** Offline counts of what stands on changed ground: foliage plan instances (minus the town
   clearance list), verified encounters, water plan planes. Each is printed; any nonzero count is a decision
   recorded before the push.
7. **Determinism.** Two runs are byte-identical.
8. **Self-test.** A synthetic bump under a synthetic street is removed. A synthetic house is untouched. A mutated
   output, with a house pixel changed, is refused.

## Order (R-WATER-CARVE + R-TOWNKIT cobble order)

1. Tag `pre-street-flatten-20261010` (the risky-op checkpoint).
2. Copy prestreets; `flatten_streets.py --write`. Gates must pass. Commit.
3. Zero editors, then launch Alpine8K. `push_heightmap.py --push --expect-change --timeout 120`, settling an
   UNKNOWN through the log import line.
4. Collision flush, same session (`scripts/payloads/landscape_collision_flush.py`).
5. The push re-saves the proxies. Then:
   - verify the grass on the streets (G exclusion unchanged);
   - check that the street mask R still registers (same XY).
6. Navmesh: R-NAVBUILD, then `town_kit_reachability --install` (streets 371/371, doors 349/349 expected), then
   `lattice --install`, then encounters re-verify.
7. HLOD: landscape proxies stale, so setup + census + cells + check (cobble order).
8. Stills: street level (street_lane_s, street_main_e), top_main_east, ridge.
9. Freshness: `check_plan_freshness`. The terrain hash moves for the town plan and roofbias; their consumed-input
   routing is recorded, not laundered.
10. RECIPES amendment + REJECTED; LESSONS; STATE.

## Costs and risks

- **Push on 8129.** Proven (water carve), 120 s transport.
- **HLOD.** All landscape HLOD becomes source-stale (as after the carve). Rebuilt here, not deferred, because the
  town's look at range depends on it.
- **Navmesh rebuild** is ~15 min.
- **Foliage.** Planned instances on the shoulders may float or bury by up to the local delta. Gate 6 counts them
  first.

## Questions for the design reviewer

1. Is push_heightmap's edit-layer import safe for a landscape whose material now carries the street overlay and
   B channel? It is a material-agnostic height import, but please cite.
2. Does the push re-save the landscape proxies so GrassData rebuilds (R-WATER-CARVE says "re-saved all 256
   proxies")? Or is the explicit proxy save still owed?
3. Do kit house actors (ISMs on placed actors) hold any landscape-relative state that a height import changes?
   For example, a foliage-style "attached to landscape" component that would be re-snapped.
4. The 13.6 deg square: does a plane fit on a disc that steep make a level-looking square or a tilted one? Should
   a disc's plane be capped (e.g. <= 8 deg, the street bar) or left as the natural tilt?
5. Is sigma 4 m right against the 1 m grid and the 0.25 m street mask? Is there a smoothing scale at which the
   street visibly decouples from the shoulder?

## Design review 2026-10-10: GO-WITH-CHANGES, and how each change landed

- **Q1 safe.** The import writes only heights (LandscapeEdit.cpp:8078-8178); grass flushes and rebuilds from
  the same material.
- **Q2 no save.** push_heightmap.py:3183-3185 leaves the write in memory only.
- **Q3 houses do not move.** Foliage snapping defaults to DontSnap (LandscapeSettings.h:144), so placed foliage
  does not re-snap either.
- **Q4 no cap.** The tilted square keeps its natural tilt; the real outlier is the 6 deg square's 3.1 m bump.
- **Q5 sigma 4 is right.**
- **(a) Readers.** Most heightmap readers want the live map; town_kit_manifest inherits Terrain.
- **(c) Derived textures.** The weightmap and cavity map are heightmap-derived, and no freshness check sees
  them go stale.
- **(d) Push scope.** The push is full-map only, so the whole landscape must be resident.

1. **Order step 5 rewritten.** push -> collision flush -> EXPLICIT save (save_level.py --save or
   save_proxies_driver.py), ~257 proxy packages. Grass is checked by same-pose still or grass.GrassMap.Dump.
2. **Routing landed.** `plan_city.Terrain(biome, town=False)` exposes `source_rel`. Only the town tools pass
   `town=True` and read pre_source:
   - plan_city main;
   - town_kit_manifest (both its gate and its record use T.source_rel);
   - check_organic_plan.

   Every other Terrain caller keeps the live map.
3. **Derived textures.** The weightmap (derive_layer_weights) and the cavity map (bake_cavity_map) are MEASURED
   after the flatten by re-deriving to scratch and counting changed texels. The decision is recorded beside the
   counts. The planting field is record-only.
4. **Overwrite guard landed.** The live sha must equal pre_source or the sidecar's last out_sha256, else REFUSE.
5. **Edges.** Gate 5b covers house-edge steps, and gate 5c covers bank (shoulder grade). The shoulder widens
   adaptively to 1.5 x delta / tan(bank_max_deg), and `house_fade_m` fades every wall.
6. **Door geometry.** Doorsteps come from `town_kit_reachability.doorsteps` and door-edge centres from
   `town_kit_manifest._world`.
7. **Push and bound.** Full residency is required for the push. `max_abs_delta_m` is 3.5, above the measured
   3.433.
8. **Freshness.** The town plan is re-gated against pre_source, not restamped as unchanged. The routing decision
   for roofbias, foliage and encounter stamps is recorded with gate 6's counts.

## Change 3 result: derived textures (2026-10-10, measured after the offline write)

- **Weightmap (w8a/b).**
  - **Reproducibility.** Today's `derive_layer_weights.py` does NOT reproduce the shipped bake:
    16,284,388 texels differ OUTSIDE the town. Re-baking would repaint the world, so it is not done here.
    The non-reproducibility goes to BACKLOG.
  - **Measuring the flatten's own effect.** The same producer ran on pre_source and on the flattened map
    (`_verify/streets_flatten/weights_effect.py`). The control holds: 0 texels differ outside the crop.
  - **Effect.** 5,239 w8a texels change (4,275 on moved vertices); on moved ground rock is -1.7 %, scree
    -3.3 %, forest_floor +3.1 % and meadow +1.8 %. 1,920 w8b texels change.
  - **DECISION: keep the shipped bake.** About 0.5 ha of slightly less rock on the streets and shoulders is
    below what the cobble overlay leaves visible.
- **Cavity.** The shipped map IS reproducible: the control is 0 differences.
  - **Effect.** 50,175 texels change inside the crop and 0 outside; the mean change is -0.9 %, and only 84 change
    by more than 25 % (`cavity_effect.json`).
  - **DECISION: keep the shipped map.** The change is negligible, and the streets render cobble over the
    composite.
- **Planting field.** Record-only. It matters at the next foliage regen, and gate 6 counted 0 instances on
  changed ground.
