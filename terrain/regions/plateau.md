# plateau.terrain — High plateau and tarns (PARAMETER-ONLY, AND IT IS NOT THE REGION)

**Read the verdict in §1 before the parameter table.** This file passes its
own gates and will build. It will **not** build the region that was asked
for, and the parameter table exists so the next session does not have to
re-derive the approach before reaching the same conclusion.

    source     C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain
               16,227 bytes, Metadata.DateLastSaved 2026-08-09 19:40:40Z
               CONFIRMED CANONICAL, not an autosave: it is the path
               rebuild_terrain.py:90 declares as DEFAULT_PROJECT, it lives in
               the package root rather than under
               %APPDATA%\QuadSpinner\Gaea\2.0\Autosaves\ (121 entries, 90
               .terrain), and read_gaea_graph.py's DEFAULT_PROJECT
               (read_gaea_graph.py:71-72) names the same file.
    output     terrain/regions/plateau.terrain   15,798 bytes
    method     load canonical JSON -> assign 10 scalar leaves + 2 Metadata
               strings -> dump. No node added, removed or rewired.
    gates      --check-refs  exit 0   ($id 82 unchanged, $ref 23 unchanged)
               --check-spec  exit 0   (predicts exactly the SPEC's six
                                       Gaea-sourced files)

---

## 1. VERDICT: NOT ACHIEVABLE BY PARAMETER VARIATION. IT NEEDS TWO NODES.

**Stated first because it is the answer, and the file below is the
consolation prize.**

The graph is:

    Mountain ---.
                 >-- Combine[Max] --> Erosion2 --> Snow --> (height, Snow.Out)
    Ridge ------'                                    |
                                                     '-- Depth --> Autolevel(SnowMask)

Every node in it is either a **peak generator** (`Mountain`, `Ridge`), a
**selector** (`Combine`), a **relief-differentiating simulation**
(`Erosion2`), a **surface veneer** (`Snow`), or a **remap of a mask**
(`Autolevel`). The requested landform needs three things and the graph can
express none of them properly:

| Requirement | Why no parameter reaches it |
|---|---|
| **Broad flat top** | Nothing in the graph compresses or clamps the upper elevation range. `Mountain.Height` is an amplitude multiplier and `Mountain.Scale` a frequency-ish knob; both rescale a domed field, neither flattens its summit. A dome at half amplitude is still a dome. |
| **Abrupt rim** | A rim is a *step* — low gradient inboard, very high gradient over a short horizontal distance, low gradient outboard. That is a discontinuity in the height transfer function. No node here has a transfer function to shape. `Erosion2` moves in the opposite direction: at long duration it *rounds* breaks of slope. |
| **Tarns (closed basins)** | Gaea's hydraulic erosion transports material downslope and **fills** depressions; `Erosion2.Deposits` is literally the fill record. `Snow` adds mass preferentially to low-slope ground, filling hollows further. Both mechanisms in the graph destroy closed basins; none creates one. |

**The relief distribution asked for is the inverse of what this graph
produces.** Alpine's brief is continuous slopes; the plateau's brief is
*low relief across most of the surface, high relief concentrated at the
rim*. That is a redistribution of gradient, and the only knobs available
are global scalars applied to a single continuous field. A global scalar
cannot make gradient bimodal.

### The two nodes it needs — both already exist in this Gaea install

I am not inventing node names. Both types appear, written by Gaea itself,
in `%APPDATA%\QuadSpinner\Gaea\2.0\Autosaves\*.terrain` on this machine
(66 files parsed; type strings and parameter names read from those files):

**(a) `QuadSpinner.Gaea.Nodes.Stratify` — the plateau surface AND the rim,
in one node.** Observed 7 times, parameters `Intensity` (0.38),
`Spacing` (0.24), `Shape` (0.5), `TiltAmount` (0.12), `Seed` (8460).
Stratification quantises height into treads separated by risers — flat
ground with abrupt edges is exactly its output signature, and `Spacing`
controls how many treads the elevation range is cut into. Insert it
**between `Combine` and `Erosion2`**, so erosion then dissects an already
terraced field rather than a dome; that ordering also lets erosion soften
the risers into something geological instead of a staircase.

**(b) `QuadSpinner.Gaea.Nodes.Lake` — the tarns.** Observed 62 times, the
most-used node in that corpus; parameters `WaterLevel` (0.0057–0.32),
`ShoreSize` (0.2–0.40), `Precipitation` (0.35–3.20), `AltitudeBias` (1),
`SizeBias` (1), `Type` (`Simple` | `Advanced`), `RenderSurface`, `X`, `Y`,
`WaterFloor`. It finds closed depressions and fills them, and — the part
that matters downstream — it produces a **water mask** the UE material and
foliage passes can consume as a "do not place anything here" field.
Without it, "tarns" is a word with no artefact behind it: there is no
water surface, no shoreline and no mask anywhere in the current graph.

A third candidate, **`QuadSpinner.Gaea.Nodes.Canyon`** (observed twice;
`Depth`, `Scale`, `Valley`, `StructualWarp`, `Seed` — Gaea's spelling),
is the alternative rim mechanism if `Stratify` reads too regular: it cuts
abrupt-walled incision *into* a flat surface, which is the Hardangervidda
edge condition seen from below rather than above. It is a second choice,
not a substitute for `Stratify`, because it does not produce the flat top.

**Both insertions are STRUCTURAL and I did not attempt them.** The file
carries 23 `$ref` back-references into 82 `$id`s assigned in document
order; a new node needs new `$id`s for itself, its `Ports` collection,
each `Port`, each `Port.Parent` `$ref`, its `Modifiers`, its `Record`s and
its `SaveDefinition`. Getting that wrong yields a file that still parses
as JSON and is a **different graph, or no graph** —
`read_gaea_graph.py:44-51`. The cheap correct route is not a writer at
all: **open `plateau.terrain` in the Gaea GUI, drop the two nodes in, wire
them, save.** Gaea allocates the ids. `--check-refs` then verifies the
result, which is what that gate is for.

---

## 2. WHAT THE FILE ACTUALLY IS

**A broad, mature-eroded, moderate-relief upland with a discriminating
snow mask, at a different seed from alpine.** It is the *surface* half of
the brief and none of the *structure* half. Calling it "high plateau and
tarns" in a recipe would be the derived-record failure this project keeps
paying for (non-negotiable 15) — so it is named `PlateauLab_v1` in
`Metadata.Name` with `Metadata.Description` carrying the disclaimer and a
pointer to this file.

### Every parameter changed

| Node | Parameter | From | To | Basis |
|---|---|---|---|---|
| 877 `Mountain` | `Scale` | 0.74927175 | **0.38** | band MEASURED, direction INFERRED — see §3.1 |
| 877 `Mountain` | `Height` | 2.032038 | **1.45** | direction INFERRED, magnitude reasoned — §3.2 |
| 877 `Mountain` | `Seed` | 22109 | **31427** | decorrelation only |
| 650 `Ridge` | `Seed` | 38804 | **14159** | decorrelation only |
| 654 `Erosion2` | `Duration` | 21.648195 | **31.0** | band MEASURED (23.16–32, n=36), direction INFERRED |
| 654 `Erosion2` | `Downcutting` | 0.4531411 | **0.20** | band MEASURED (0.191–0.42, n=8), direction INFERRED |
| 654 `Erosion2` | `ErosionScale` | 1413.2517 | **2297.4** | MEASURED arithmetic — §3.3 |
| 654 `Erosion2` | `Seed` | 15025 | **26535** | decorrelation only |
| 599 `Snow` | `SnowLine` | 0.056395777 | **0.30** | direction MEASURED (R-GAEA §2), value reasoned — §3.4 |
| 599 `Snow` | `Seed` | 59434 | **48979** | decorrelation only |
| — `Metadata` | `Name` | `""` | `"PlateauLab_v1"` | provenance |
| — `Metadata` | `Description` | `""` | disclaimer + pointer here | provenance |

Seeds are the digits of π taken in runs (3.1427 / 1.4159 / 2.6535 /
4.8979 — recorded so they are reproducible rather than arbitrary), each
inside the [8451, 60797] band every Gaea-written seed in the 66-file
autosave corpus falls in.

### Everything deliberately NOT changed, and why

- **`Combine.Mode` stays `Max`.** It is a parameter and it does have a
  large landform effect, so leaving it is a decision. Only two values are
  evidenced anywhere on this machine — `Max` and `Subtract`. `Subtract`
  incises ridge-shaped channels into the mountain, which is further from a
  plateau, not closer. **I did not reach for `Min`, `Clamp` or any other
  plausible-sounding mode**: an unobserved enum string is a guess, and
  Newtonsoft's enum handling on an unknown member is not something I can
  read from any source here (non-negotiable 23 applied to a value rather
  than an accessor).
- **`Terrain.Width` 5000.0, `Terrain.Height` 2500.0, `Ratio` 0.5 —
  untouched, and this is load-bearing.** `Ratio` is exactly
  `Height/Width`, so the three are one fact stored three times. Setting
  `Width` to 8128 to match the import extent would leave `Ratio` and
  `Height` disagreeing with it, and `Terrain.Height` is the *sole* input
  to `rebuild_terrain.read_project_height_m` (`rebuild_terrain.py:166-203`)
  and therefore to the whole Z-scale chain. The extent mismatch is fully
  addressable through `ErosionScale` alone (§3.3), so the coupled triple
  is left alone. Verified harmless in passing: that walk only accepts a
  `Height` found under a key named `Terrain` (`:185-189`), so
  `Mountain.Height` cannot contaminate it and make the read AMBIGUOUS.
- **`Snow.Duration`, `Intensity`, `SettleThaw`, `Melt` — untouched.** I
  cannot establish what any of them does to the landform from the
  `.terrain`, the repo, or the autosave corpus. Changing a knob whose
  direction is unknown adds noise to a build and then pollutes the record
  with a "we tried X" that means nothing. Left at alpine's values.
- **`Snow.SlipOffAngle` and `Snow.AdheredSnowMass` — NOT added.** They are
  real members (Gaea wrote them, 35 and 2, in 7 autosaved Snow nodes) and
  absent from the canonical file, so they are sitting at defaults.
  `SlipOffAngle` is the single most plateau-relevant snow knob available.
  Adding a key creates no `$id` and so cannot break `--check-refs`, but it
  is still a widening of the file's surface on an unmeasured direction —
  **flagged as the cheapest next experiment**, not taken.
- **The three `SaveDefinition.Filename` bases stay `Erosion2` / `Snow` /
  `SnowMask`.** They *must*: `--check-spec` compares predicted filenames
  against `verify_build.SPEC`, and renaming them to `Plateau_*` refuses
  with exit 4. Collision with alpine's outputs is avoided by the build
  destination, not the filenames — `BuildDefinition.Destination` is
  `<Builds>\[Filename]\[+++]` and `[Filename]` resolves from the
  `.terrain` basename, so this project builds into a `plateau` folder.
  **But see the hazard in §5.**

---

## 3. THE REASONING, WITH ITS PROVENANCE MARKED

### 3.1 `Mountain.Scale` 0.749 → 0.38 — AND THIS IS THE ONE MOST LIKELY TO BE BACKWARDS

MEASURED: the closest analogous parameter Gaea actually wrote in this
install, `MountainRange.Scale`, spans **0.3–0.82** over 49 instances, so
0.38 is inside a real authored band and not an out-of-range value.

INFERRED, and I cannot resolve it: the two readings of "Scale" give
opposite landforms.

- If `Scale` is **feature frequency**, 0.38 gives fewer, broader
  landform units → a broad upland → what the region wants.
- If `Scale` is **feature size**, 0.38 gives smaller, more numerous
  peaks → busier terrain → the opposite.

**The alternative value is 0.95.** It is written here so that if a build's
hillshade comes back busy rather than broad, the next session flips one
number instead of re-deriving this paragraph. One build discriminates;
nothing else on this machine does.

### 3.2 `Mountain.Height` 2.032 → 1.45 — with a named disproof

The obvious plateau move is "lower the amplitude a lot". **It is a trap,
and the mechanism is worth writing down.**

`Combine` is `Max(Mountain, Ridge)`, and **`Ridge` has exactly one
parameter — `Seed`. There is no amplitude control on it at all.** So
lowering `Mountain.Height` does not lower the terrain's relief; past some
crossover it hands the landform to `Ridge`, whose character is continuous
sharp ridge-and-valley — the *worst* available shape for a plateau. That
`Mountain.Height` is 2.032038 (> 1, so not a 0–1-clamped slider) while
Gaea's 0–1 primitives sit in [0,1] suggests `Mountain` currently dominates
the `Max` almost everywhere and `Ridge` only fills the low ground.

1.45 is chosen to stay clearly above that presumed ~1.0 crossover while
dropping amplitude ~29%. Ridge then contributes slightly more in the
basins, which *raises the floor* — and raising the floor is
plateau-favourable.

**The disproof, built into the same operation (non-negotiable 13):** the
first build writes `height_normalization.json`. Compare its `occupancy`
against alpine's **0.37035172045471887**.

- occupancy falls roughly in proportion to 1.45/2.032038 = **0.7136**
  → `Mountain` still dominates, `Height` is still the amplitude lever,
  and the model above holds.
- occupancy barely moves → **`Ridge` is setting the ceiling**,
  `Mountain.Height` has stopped being an amplitude control, and every
  amplitude statement in this file is void.

### 3.3 `ErosionScale` 1413.2517 → 2297.4 — the one MEASURED change

`ErosionScale` is tuned to the extent the graph was authored at:

    1413.2517 / 5000.0 (Terrain.Width)  =  0.2826503

The target import extent is **8128 m** (8129² at 1 m/vertex —
CLAUDE.md CURRENT STATE 2026-08-11/14), so features are stretched by

    8128 / 5000  =  1.6256

Preserving the authored ratio at the target extent:

    1413.2517 x 1.6256  =  2297.38  ->  2297.4

**Both readings of the parameter recommend the same move, which is rare
and is why this change is the most defensible one in the file.** If
`ErosionScale` is a physical-size hint, raising it keeps drainage features
at their authored physical size after the 1.63× stretch. If it is a
feature-size-in-graph-units knob, raising it produces broader, shallower,
more widely spaced drainage — which is independently what a dissected
plateau surface wants. The *justification* differs by reading; the number
does not.

**Disproof:** measure the dominant drainage wavelength in the plateau's
`Erosion2_Flow.png` against alpine build 006's, both at the same export
resolution. ~1.63× coarser in pixels means the correction went the
intended way.

### 3.4 `Snow.SnowLine` 0.0564 → 0.30 — direction is MEASURED, and it costs something

**R-GAEA §2 (locked, and independently corroborated by the autosave trace
0.47 → 0.18 → 0.056): Snow Line is INVERTED — a LOWER value produces MORE
snow.** Alpine sits at 0.0564, i.e. near-maximum snow.

Raising it to 0.30 reduces coverage. 0.30 is inside the union of values
Gaea has written on this machine (0.0564 … 0.78, the upper cluster being
0.68–0.78 across 7 nodes).

**Why less snow on a region defined as above the treeline — this is a real
tension and the resolution is a judgement, not a measurement.** Two
effects pull opposite ways:

- *For more snow:* snow deposition is the **only** mechanism in this graph
  that preferentially adds mass to low-slope ground and sheds off steep
  faces — i.e. the only thing that flattens flats while leaving the rim
  alone. It is a genuine plateau mechanism.
- *Against:* `SnowMask_Out.png` is the mask the UE material uses to
  discriminate snow from rock and ground. At 0.0564 that mask saturates
  and the plateau reads as uniform white — **the saturated-modulator
  defect non-negotiable 22 was written for, which this project has already
  hit at 99.03% coverage.** And the flattening is a metres-scale veneer
  against a ~660 m span (R-GAEA §2 records `Snow_Snow.png` at 12% coverage
  on build 002); the mask damage is certain and large, the flattening
  benefit is small.

Certain-and-large beats speculative-and-small, so: less snow. **If a build
shows the mask discriminating well at 0.30, lowering it back toward 0.15
is the right experiment** — the flattening is worth having if it can be
had without saturating the mask.

---

## 4. EXPECTED Z SPAN AND UE z_scale_cm — **A PREDICTION, NOT A MEASUREMENT**

R-GAEA §6 method, applied:

    span_m   = project_height_m x occupancy
    z_scale  = span_m / 512 x 100

`project_height_m` is **2500.0**, read from `Terrain.Height` in this file
(unchanged from canonical) — and per R-GAEA §6 that is the PROJECT range,
**never this build's span**. Taking 2500 as the span gives
`2500/512x100 = 488.3`, a landscape **2.7× too tall and entirely
plausible**. That is the trap, restated here because this section is where
someone reaches for a number.

`occupancy` is **UNKNOWN**. It is a property of a build that has not
happened. The only estimate available assumes the §3.2 model — that
`Mountain` dominates the `Max` and the field scales linearly with
`Mountain.Height`:

    amplitude ratio      1.45 / 2.032038          =  0.71359
    occupancy (est.)     0.37035172 x 0.71359     =  0.26428
    span_m   (est.)      2500 x 0.26428           =  660.7 m
    z_scale  (est.)      660.7 / 512 x 100        =  129.0

    for comparison, alpine build 006, MEASURED:
    occupancy 0.37035172045471887   span 925.8793 m   z_scale 180.8358

**DO NOT TYPE 129.0 INTO THE LANDSCAPE IMPORT DIALOG.** It is a
prediction from an unverified model of one parameter, and it ignores
`Ridge`'s floor contribution, `Erosion2`'s redistribution and snow mass
entirely. `Ridge` raising the minimum would push occupancy *lower*;
`Ridge` raising the maximum would push it *higher*; I cannot tell which
without a build, so **660.7 m is a point estimate with no error bar, not
a bound.**

The z_scale becomes a measured value at exactly one moment: when
`rebuild_terrain.py` writes `height_normalization.json` for a plateau
build, recording `source_min`, `source_max`, `occupancy`, `span_m` and
`ue_z_scale` with `z_scale_provenance: "measured"`. Until that file
exists, R-GAEA's own REJECTED entry applies —
*"Defaulting Z scale to UE's 100 when the project range is unreadable →
an unmeasured vertical scale that reads as a decision → report UNKNOWN"*.
**A predicted z_scale is not a measured one. Report it UNKNOWN.**

---

## 5. HAZARDS FOR WHOEVER BUILDS THIS — read before running anything

Not one of these is hypothetical; each is a value read out of the tooling.

1. **`rebuild_terrain.py --root` defaults to alpine's package tree.**
   `rebuild_terrain.py:89` — `DEFAULT_ROOT =
   C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1`. Building this project
   without an explicit `--root` writes plateau output into alpine's `NNN`
   sequence. This is the same class as the talus cache path that
   **overwrote** alpine's cache (CLAUDE.md, 2026-08-14 table: "all
   per-biome or per-resolution quantities written as though only one of
   each would ever exist").

2. **The normalised heightmap will be named `AlpineLab_v1_Height_normalized.png`
   whatever region it belongs to.** `rebuild_terrain.py:96` hardcodes
   `HEIGHT_OUTPUT`, `:103` hardcodes the alias `AlpineLabHeight.png`, and
   `verify_build.SPEC` requires that exact name. A plateau build produces
   an alpine-named heightmap. Fixing it means moving one constant to a
   per-region declaration in **both** producer and consumer — and those
   are two lists that must agree (non-negotiable 24), so they want one
   declaration, not two edits.

3. **`Metadata.Edition` reads `"Community"` in the canonical file** and is
   inherited verbatim here. CLAUDE.md records Gaea **2.3.0.1 Indie**
   activated 2026-08-09 with an 8K export cap — and this file's
   `DateLastSaved` is 2026-08-09 19:40:40Z, i.e. the same day. Whether the
   field is stale or records the edition at authoring time, **it is not a
   readable source for the licence or the export cap.** Do not answer the
   8K-cap question from it. (Non-negotiable 17: the file records what was
   written, not what is in effect.)

4. **`Metadata.DateCreated` / `DateLastBuilt` / `DateLastSaved` describe
   the CANONICAL file's history, not this one.** They are inherited
   unchanged and were deliberately not rewritten — inventing a timestamp
   for a file Gaea has never saved would be fabricating a record. The
   first save from the Gaea GUI will correct them.

5. **`BuildDefinition.Resolution` is 4096**, inherited. The 1 m/vertex
   target needs 8192 at build time (then 8192→8129 via
   `resize_gaea_build.py`, R-GAEA §4 step 2). Pass
   `rebuild_terrain.py --resolution 8192`; do not edit the field here,
   because the CLI flag is the declared route and CLAUDE.md records
   `--resolution 8192` as the proven invocation.

6. **The `.terrain` seed fields are NOT `rebuild_terrain.py --seed`.**
   Two different seed surfaces exist; nothing in this file constrains what
   the CLI flag does. If both are used, say which one produced a build.

---

## 6. WHAT I COULD NOT VERIFY — stated plainly (standing rule 10)

- **Nothing here has been built.** No Gaea run, no export, no import, no
  render. Every landform claim in §2 and §3 is a prediction. The file is
  proven *well-formed* and proven *parameter-only*; it is not proven to
  produce anything in particular.
- **The direction of `Mountain.Scale`, `Mountain.Height`,
  `Erosion2.Duration` and `Erosion2.Downcutting` is INFERRED from the
  parameter names.** The recon report withdrew exactly these semantics as
  unrecoverable from the `.terrain`, the repo or `Gaea.Nodes.dll`, and I
  did not find a better source. The observed *bands* are measured; the
  *directions* are hypotheses.
- **`Ridge`'s output range is unread.** The entire §3.2 argument — that
  `Mountain` dominates the `Max` — rests on 2.032038 > 1 and on Gaea's
  other primitives sitting in [0,1]. That is circumstantial. The
  occupancy disproof in §3.2 is how it gets settled.
- **Whether `Stratify` at this scale reads as geology or as a staircase**
  is unknown. It is recommended on mechanism (flat treads + abrupt
  risers), not on a picture. `Canyon` is named as the fallback for the
  same reason.
- **Whether `Lake` writes an exportable mask through a `SaveDefinition`**
  the way `SnowMask` does is not established — 62 `Lake` nodes were read
  for their *parameters*, not for their export wiring. If it does not, the
  tarn mask needs a separate route and `verify_build.SPEC` needs a row.
- **`--against-build` was not run** on this file. There is no plateau
  build to run it against; that is "could not look", not a pass
  (non-negotiable 6).
