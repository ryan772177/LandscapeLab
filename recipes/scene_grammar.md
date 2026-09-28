# scene_grammar.md — the normative contract for a CONCEPT recipe

**Schema version 1.0-concept. 2026-08-29.**

A concept recipe is what a 2D image becomes when it is read into something the
pipeline can build. It is **code, not prose** — `scripts/concept_loop.py` reads
it — and it lives under `recipes/concepts/`.

## THE ONE RULE THAT SHAPES EVERYTHING ELSE

**A SCENE IS A PLACE PLUS A CAMERA, AND THOSE ARE DIFFERENT THINGS.**

The 2026-08-29 intake found both concepts are the SAME village from two
viewpoints. If each image had become its own self-contained scene, the pipeline
would have built the village twice, in two incompatible layouts, and no
instrument could have caught it — each would verify perfectly against its own
image.

So the schema separates them:

    site_id          the PLACE. Concepts sharing a site_id describe ONE world.
    camera           the VIEW. Each concept carries exactly one.

Two concepts on one `site_id` are a **cross-check, not a duplication**: build
once, solve both cameras, and a village-to-mountain relationship that is wrong
will fail in one view while passing in the other. **A single view cannot detect
that error at all.**

## PROSE KEYS ARE PERMITTED

Per the 2026-08-27 ruling for planner recipes. `_why_*`, `_what_*`, `_read_*`
are documentation and no script may read them; `scripts/check_prose_keys.py`
enforces that rule against this file's consumers.

## EVERY ENTITY CARRIES ITS EPISTEMIC STATUS

Non-negotiable 6 — an instrument must distinguish *"I looked and it is absent"*
from *"I could not look"*. A concept recipe is a reading of an image and much of
it is inference, so each entity declares:

    "provenance": "read"      directly visible in the image
                  "inferred"  deduced from what is visible, stated as such
                  "assumed"   supplied by the pipeline, NOT in the image
    "confidence": 0.0 .. 1.0

**`assumed` is not a lesser `read`. It is a flag that the image did not say
this**, and anything downstream that treats the three alike has thrown away the
distinction the field exists to carry.

---

## TOP-LEVEL BLOCKS

    schema_version   "1.0-concept"
    concept_id       stable id, matches the filename
    site_id          the PLACE. SHARED across concepts of one location.
    source_image     path under refs/, plus its sha256 at reading time
    _read_by         who/what read it, and when

    terrain          landform features the scene needs
    placements       structures, by class and footprint
    focal_anchor     the one thing the composition is organised around
    clutter          repeated small objects, by class and density
    atmosphere       sun, haze, time of day
    camera           the view this concept is FROM

## `terrain`

    features[]    { kind, bearing_deg | position_hint, prominence, provenance }
      kind        one of: peak, ridge, slope, basin, river, stream, road, track
    ground_cover  dominant surface classes with rough fractions

**`bearing_deg` is IMAGE-RELATIVE unless a camera solve exists.** It is written
as degrees from the camera's forward axis, positive to the right. Converting it
to a world bearing is Phase B's job and the field says so.

## `placements`

    items[]  { class, count | count_range, footprint_class, height_class,
               orientation, arrangement, provenance, confidence }

    footprint_class   small | medium | large   (metres declared in the recipe,
                      never hardcoded in a script)
    height_class      storeys, in whole wall courses -- the kit's course is
                      2.00 m and `buildings.storey_m` is now 2.0 to match
    arrangement       how they sit: terraced_slope | street_lined | clustered |
                      isolated

**Counts are ranges by default.** A concept image shows *some* houses; claiming
exactly seventeen from a hazy midground is false precision. A range with a
confidence is honest and is just as buildable.

### `parts[]` — for an entity that is not one height (added 1.1-concept)

    parts[]  { part, height_ratio, ratio_against, footprint_frac,
               provenance, confidence }

    part            nave | tower | spire | porch | ...
    height_ratio    a multiple of the REFERENCE house height
    ratio_against   what the ratio is measured against. REQUIRED, because the
                    ambiguity is exactly what caused the defect below:
                    `house_silhouette` (walls + roof, what a viewer compares)
                    or `house_walls`
    footprint_frac  fraction of the entity's footprint this part occupies

**⛔ A `parts[]` ENTITY MUST NOT ALSO CARRY `height_class`.** One entity, one
declaration of its height. Carrying both is two sources for one number, which
is the defect this field exists to remove — not a redundancy to keep "for
compatibility". Where an entity is being converted, the old value moves to
`_height_class_superseded` as a string, so the history is readable and the
number is inert.

**WHY THIS EXISTS — the church, 2026-08-30.** `alpine_village_01` described its
church twice and the two disagreed: the prose said *"roughly half again the
height of the houses"* (1.5×) while `height_class: 4` against the chalets' `2`
implied 2×. The Phase B loop measured the built result at **2.24–2.61× the
chalet silhouette** and reported the contradiction rather than averaging it.

The operator's ruling was that **both readings were right about different
things** — the reader had seen a nave *and* a tower and flattened them into one
number. A church is not an average of its nave and its spire, and no single
`height_class` could have been correct. The fix is to let the entity have
parts.

## `focal_anchor`

The single object the composition is organised around, with why. There is at
most one. In both concepts here it is the onion-dome church — the only vertical
accent, and the thing both cameras point at.

## `clutter`

    classes[]  { kind, density, attaches_to, provenance }
      attaches_to   building_wall | street_edge | water_edge | open_ground

Clutter is what makes a village look inhabited rather than built, and it is
cheap. It is a first-class block for that reason, not an afterthought.

## `atmosphere`

    sun          { elevation_deg, azimuth_deg | azimuth_unsolved, colour_rgb,
                   intensity_hint }
    shadow       { colour_rgb, contrast_ratio }
    haze         { far_saturation, near_saturation, ratio, far_luma, near_luma }
    time_of_day  label + evidence
    artificial   lights visible in the image (lit lanterns are a time-of-day
                 witness as much as a light source)

**`azimuth_unsolved` is a legal value and is the honest one here.** A world sun
azimuth cannot be derived from a single image without the camera solve. The
schema refuses to let a guess occupy a field that reads like a measurement.

## `camera`

    position_hint    where the viewer stands, in scene terms
    height_m         eye height above local ground
    pitch_hint       level | slight_down | slight_up
    horizon_frac     where the horizon sits, as a fraction of frame height
    fov_hint         narrow | moderate | wide
    solve            filled by Phase B: the actual location/rotation/FOV that
                     reproduces the framing, plus the residual

**`solve` starts null and is written by the loop, never by the reader.** The
reader's job is to record what the image shows; the solver's job is to find the
camera that reproduces it. Collapsing those two is how a scene gets built to fit
a guessed camera.

---

## VERSIONING

`schema_version` is `MAJOR.MINOR-concept`. A field whose MEANING changes takes a
MAJOR bump; an added optional field takes MINOR. Consumers assert the major
version and refuse otherwise — an unrecognised schema is a refusal, never a
best-effort parse.
