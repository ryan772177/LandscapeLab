> # ⛔ SUPERSEDED — describes the pre-8K / pre-kit design. Do not apply.
>
> Quarantined 2026-08-29 by the doc-consolidation unit. **Nothing in this
> file may drive a decision.** It is kept verbatim because this project
> never deletes a record; the content below the banner is byte-identical to
> what it was before the move.
>
> **Why it is dead.** "ALPINE REGION — VERIFICATION REPORT", Pass 7's
> verification half, generated 2026-08-05 against the pre-8K world.
>
> **And it has a second strike.** This file was **already reverted once for
> containing false claims** — CLAUDE.md's 2026-08-08 audit, item 5, found it
> rewritten from `alpine_execution_plan.md` so that every PLANNED step read
> as a COMPLETED one (Pass 3 talus "placed", Pass 5 "verified", clouds
> "inert" — none true). Treat it as a hazard, not merely as stale.
>
> *Moved from its original path by `git mv`, so `git log --follow` still
> reaches its whole history.*

---

# ALPINE REGION — VERIFICATION REPORT

Generated 2026-08-05. Every number below is a MEASUREMENT with the
instrument named. Nothing here is an estimate, and where something could
not be measured it says so instead of giving a number.

This is Pass 7's verification half. **The clip is NOT here** — see
WHAT IS NOT VERIFIED.

---

## 1. LANDSCAPE — `scripts/verify_landscape.py`

    Landscape actors            1  ('Landscape_Alpine')
    StreamingProxy actors     256  (World Partition)
    components               1024  (32 x 32)
    resolution         2017 x 2017
    scale                X 400.0  Y 400.0  Z 500.0
    VERDICT            PASS — live landscape matches the recipe-derived spec

**DERIVED, not read:** quads/component 63, section size 63, sections per
component 1. UE 5.8 refuses `get_editor_property` on those bare
`UPROPERTY()` fields, so they are derived from measured component
spacing, which determines them uniquely over the dialog-legal values.
The verifier prints this rather than presenting them as engine reads.

## 2. INSTANCES — `scripts/recover_state.py` (live world)

    Medium_Boulder_001      759   cull 14000 cm
    fir_tree_01_c_LOD0  157,554   cull 73000 cm
    InstancedFoliageActors 1,328

The conifer count is **157,554**, not the long-quoted 160,448. That
figure was correct against the PRE-adoption surface; Pass 1 replaced the
terrain, placement re-ran, and the acceptance mask moved. R5's
VERIFICATION section carries the correction.

## 3. GROUNDING — `scripts/verify_grounding.py` (EVERY instance)

    species     count      mean m     p99 m     max m    outside tolerance
    Conifer   157,554      -0.000     0.001     0.001            0
    Boulder       759      -0.008     0.044     0.103            1

Full population, not a sample: a floater is rare by construction, so
sampling would return a clean bill of health for a map with hundreds.

**One boulder of 759 sits 0.103 m outside a DERIVED allowance** and has
NOT been absorbed by widening the tolerance. In BACKLOG.

**What this is not:** it shares the heightmap and world transform with
the planner, so a shared-transform error is invisible to both. It
measures plan-vs-surface agreement, not absolute grounding in the engine.

## 4. GATES — `scripts/prove_gates.py` (no editor, survives cold replay)

    CPU-model mutations refused          7 / 7
    recipe probes rejected              31 / 31
    rock-plan adoption cases correct     5 / 5
    dead-gate sweep          38 checkers, all with call sites

The adoption cases are the highest-stakes: their failure mode is 157,554
conifers deleted by the orphan sweep, and placement is saved, so git does
not undo it.

## 5. LIGHTING — `scripts/atmosphere_solve.py` + measured frames

    transmittance toward sun     [0.7031, 0.4604, 0.2196]
    ground illuminance normal    91,404 / 59,858 / 28,543 lux
    physical band at 12 deg      49,000 - 60,000 lux        -> green 59,858 IN BAND
    sunlit terrain luminance     1059.67 cd/m2
    linear value at -1.786 EV    0.3201                     -> target 0.32

Frame means before -> after the sun correction, same cameras, same world:

    forest_floor   109.1 -> 178.4   blown 0.0108
    player_eye      72.8 -> 133.3   blown 0.0000
    verify_ground   96.7 -> 175.8   blown 0.0000
    ridge_wide     107.4 -> 179.0   blown 0.0000

Acceptance is the BLOWN-WHITE FRACTION, not the mean: a clipped frame has
a high mean and no detail.

## 6. SUN GEOMETRY — `scripts/sun_exposure.py`

    sun bearing            105.0 deg   (MEASURED forward vector, NOT the
                                        recipe field, which is the light
                                        actor's YAW = 285)
    elevation               12.0 deg
    conifers LIT            85,569  (54.3%)
    conifers SHADOWED       71,985  (45.7%)

45.7% in terrain shadow is a property of the TERRAIN at a 12 degree sun,
not a lighting defect. It is why a verification camera must choose its
SUBJECT before its position.

## 7. LOD — `scripts/measure_lod_materials.py` + measured frames

    lod  triangles   screen   sections
    0      505,494   1.0000   4  (bark, twig, bark, bark)
    1      126,374   0.5000   4  (identical)
    2       22,293   0.2100   4  (identical)
    3        3,892   0.0880   4  (identical)

No LOD loses a section or a material. Switch distances from measured
bounds and screen sizes: **46.3 / 110.2 / 263.1 m**.

Colour across the 46.3 m LOD0->LOD1 switch, hue-segmented:

    LOD0 side, 40 m   luma 188.6   hue 1.000/0.919/0.780
    LOD1 side, 53 m   luma 191.3   hue 1.000/0.924/0.790
    delta             +2.7 luma, +1.4%, hue unchanged

## 8. ROCK COST — measured chains, not modelled

All 13 pass-3 rocks: **Nanite FALSE**, **1 material slot each** (the Fab
registry claims 2 and 12 — its `Materials` tag is stale on the whole
set; its `Triangles` tag matched live everywhere checked).

Vendor LOD chains do not follow `percent = screen_size^2`. Measured
against modelled cost per instance ranges from **20.3x understated**
(boulder_small) to **0.4x overstated** (cliff_face_01), so no single
correction factor is valid and the chain is read from each asset.

---

## WHAT IS NOT VERIFIED — stated, not implied

- **The clip.** Pass 7 asks for a filmed result. Not produced.
- **The ground-to-2 km continuous sweep.** Pass 2's outstanding exit
  gate. Not run.
- **Cliff and talus MESH roles.** Specified in R12, NOT PLACED. Only the
  landscape material's scree texture represents them.
- **Frame cost.** `atmosphere_solve` reports a volumetric-cloud ceiling
  of 195M ray-march samples/frame and says explicitly it CANNOT measure
  GPU time offline. No `stat gpu` has been taken. Clouds are OFF.
- **Fog and aerial perspective.** Computed by the solver, never tuned
  against a render at distance.
- **All 13 recipes remain UNPROVEN.** REPLAY BATCH 1 has not run. Not one
  recipe has been executed purely from its own written steps.
- **Pass 5 has no written scope** anywhere in the repo.
- **Every ground-level judgement made before 2026-08-04** was made under
  a 5x underlit scene and needs re-taking.
