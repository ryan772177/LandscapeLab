# badlands.terrain — authoring note

**Region:** eroded badlands and canyon. Candidate region two.
**File:** `terrain/regions/badlands.terrain`
**Derived from:** `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain`
sha256 `459d5c2fc9d07b9cc19f4b08b2818d6c503119e95caf5c2cc57e6c7efc283346`
**This file:** 16,368 bytes,
sha256 `95f89b930efbfbb3fdcbb8dba2dd9f0c3ff46be79e8762f26fb02a6339b88bd2`

**Provenance of the source.** The canonical `.terrain` was confirmed as the
one at the documented path, not an autosave. A recursive search of
`C:\Dev\LandscapeLab` returns exactly one `AlpineLabe_v1*.terrain`; the 90
autosaves live under
`C:\Users\Admin\AppData\Roaming\QuadSpinner\Gaea\2.0\Autosaves` and none of
them is named `AlpineLabe_v1`. R-GAEA §9's autosave refusal is satisfied.

---

## 1. WHAT WAS DONE, AND WHAT WAS NOT

**PARAMETER SUBSTITUTION ONLY.** No node was added, removed, retyped,
rewired, or given a key it did not already have. Every `$id` and every
`$ref` is byte-identical to the source, because the edits were exact
unique whole-line string replacements on the source text — no JSON
round-trip, so key order and document order could not move.

That envelope is not caution, it is the constraint recorded at
`scripts/read_gaea_graph.py:38-55`: the file carries 23 `$ref`
back-references assigned in document order, so *changing a parameter value
is safe* and *adding or removing a node is not, without id-allocation
logic*.

The generator asserted four structural invariants **before** writing:
skeleton equality with every leaf value erased; identical node set;
identical `$type` per node; identical key set per node. It refuses rather
than writes if any of them moves.

**18 lines differ from the canonical file. All 18 are values.**

---

## 2. EVERY CHANGE, FROM WHAT TO WHAT, AND WHY

Provenance is tagged per row, because the semantics of most Gaea
parameters are **not recoverable from the `.terrain`, from this repo, or
from any source available offline**. Where I am reasoning from a
parameter's name, it says so. Do not read an inferred row as a fact.

### 2.1 Terrain-level

| Field | From | To | Provenance | Why |
|---|---|---|---|---|
| `Terrain.Height` | `2500.0` | `1200.0` | **MEASURED consequence** | The project's declared vertical range in metres. It is the multiplier in R-GAEA §6's Z derivation (`rebuild_terrain.derive_z_scale:159-163`), read from the file by `read_project_height_m:185-205`, so it propagates automatically and correctly. Badlands are a low-relief landform class; 2500 m is the alpine massif's range and would make a 300 m canyon read as 12% of the project. **UNVERIFIED:** whether `Height` also feeds the erosion simulation's vertical exaggeration. `Snow.RealScale` is `false`, which *suggests* the sim runs in normalised space, but I did not confirm it. |
| `Terrain.Ratio` | `0.5` | `0.24` | **MEASURED** | `Ratio` is `Height/Width`. `2500/5000 = 0.5`; `1200/5000 = 0.24`. Leaving it at 0.5 beside a Height of 1200 would be two stored facts that must agree and don't — non-negotiable 24. Nothing in this repo reads `Ratio`; Gaea may. |
| `Terrain.Width` | `5000.0` | **unchanged** | **decision** | Deliberately not touched. See §4. |

### 2.2 Mountain (node 877) — the base surface

| Parameter | From | To | Provenance | Why |
|---|---|---|---|---|
| `Height` | `2.032038` | `0.62` | **INFERRED (name)** | Base tectonic amplitude in the graph's own units. Lowering it ~70% is the change that makes **erosion the landform rather than decoration on a mountain** — the single highest-leverage edit for landform *class*, and also the least verifiable. The only hard fact is that `2.032038 > 1`, so the field is not 0–1 clamped and 0.62 is trivially inside whatever range that is. The recon report's earlier "keep within ±30%" band was withdrawn as invented; I am not reinstating it. |
| `Scale` | `0.74927175` | `1.34` | **INFERRED (name)** | Larger scale → fewer, broader base forms → wide interfluve blocks between drainages instead of many small summits. This is what should give a mesa-between-canyons reading. Unverified. |
| `Seed` | `22109` | `41881` | **safe class** | A different region must be a different terrain, not the same one rescaled. |

### 2.3 Ridge (node 650)

| Parameter | From | To | Provenance | Why |
|---|---|---|---|---|
| `Seed` | `38804` | `58207` | **safe class** | Same reason. `Seed` is the node's **only** serialised parameter — Ridge has no amplitude knob in this file, which is a load-bearing limitation. See §4. |

### 2.4 Erosion2 (node 654) — the region rests on this node

| Parameter | From | To | Provenance | Why |
|---|---|---|---|---|
| `ErosionScale` | `1413.2517` | `340.0` | **best-evidenced change in the file** | See §3. This is *the* change. |
| `Duration` | `21.648195` | `30.5` | **INFERRED + observed band** | Longer erosion → more mature drainage network, deeper incision, and — the badlands-specific part — **flatter interfluves**, because lowering and rounding the un-channelled ground is what long erosion does to it. 30.5 sits inside a band Gaea itself has written: `Duration` across the 90 autosaves ranges **23.1607–32.0**, e.g. `Erosion_Main` at `32.0` in `Migration_Bisect_A_LakeNode_2026-08-13_22-13-45.terrain`. **I measured nothing about build cost.** The recon report's claim that Duration dominates build time was withdrawn and I am not repeating it. |
| `Downcutting` | `0.4531411` | `0.78` | **INFERRED (name) — most speculative number here** | Vertical incision relative to lateral widening. High → narrow, steep-walled, V-to-slot channels, which is the canyon signature. The observed band in the autosaves is only **0.191123–0.42**, but the canonical AlpineLab file itself carries `0.4531411`, which proves the parameter accepts values above 0.42. **0.78 is an extrapolation beyond anything observed anywhere.** If one number in this file needs a build to justify it, it is this one. |
| `Seed` | `15025` | `70413` | **safe class** | Different region. |

### 2.5 Snow (node 599) — repurposed as a CAPROCK mask

Read §5 before changing any of these. Snow **cannot be turned off**.

| Parameter | From | To | Provenance | Why |
|---|---|---|---|---|
| `SnowLine` | `0.056395777` | `0.88` | **MEASURED (inverted control)** | The control is inverted — a **lower** value produces **more** snow (R-GAEA §2), corroborated independently by the autosaves: snowy alpine projects carry `SnowLine` **0.68–0.78** while this file's heavily-snowed alpine build carries **0.056**. Badlands are arid, so this goes high. **Deliberately not 1.0** — §5. |
| `Intensity` | `0.40226594` | `0.11` | **INFERRED (name)** | Minimal deposited mass, so deposition cannot smooth the incision the erosion budget just paid for. Observed `0.22` in the autosaves. |
| `Melt` | `0.450141` | `0.72` | **INFERRED (name)** | Survives only where sheltered → a tighter, higher-contrast cap mask. |
| `Duration` | `0.4066604` | `0.22` | **INFERRED (name)** | Short deposition. This is a cap mask, not a snowfield. Observed `0.2` in the autosaves. |
| `SettleThaw` | `0.3619003` | `0.62` | **INFERRED (name)** | Intended to sharpen the graded falloff on the `Depth` channel that `SnowMask` autolevels. |
| `Seed` | `59434` | `12960` | **safe class** | Different region. |
| `RealScale` | `false` | **unchanged** | **decision** | Flipping normalised↔real-scale semantics mid-region, unbuilt, is exactly the R-GAEA §6 class of trap. |

### 2.6 Metadata

`Metadata.Name` `""` → `"Badlands"` and `Metadata.Description` `""` → a
sentence recording the derivation. Both were **empty**, so this is filling
a blank, not overwriting a record.

**Deliberately NOT touched:** `DateCreated`, `DateLastBuilt`,
`DateLastSaved` (fabricating a save history), `Edition: "Community"`
(stale — CLAUDE.md records Gaea 2.3.0.1 **Indie** activated 2026-08-09 —
but it is Gaea's record of when the file was written, not mine to
rewrite), `Terrain.Id` and the top-level `Id` GUIDs (no `$ref` targets
them; changing an identifier is inventing one, and `BuildDefinition
.Destination` is `<Builds>\[Filename]\[+++]`, keyed by filename, so two
projects sharing a GUID do not collide on output paths).

---

## 3. THE ONE CHANGE THAT CARRIES THE REGION: `ErosionScale` 1413.25 → 340.0

This is the best-evidenced edit in the file and the only one I would
defend without a build.

**Fact 1, measured.** `ErosionScale` is a length in the same units as
`Terrain.Width`. The canonical value is `1413.2517 / 5000 = 0.28265` of the
authoring extent.

**Fact 2, measured.** CLAUDE.md records — and the arithmetic confirms —
that importing a graph authored at 5000 m into an 8128 m landscape
stretches its erosion features by `8128 / 5000 = 1.6256`.

**Fact 3, observed.** Gaea itself has written `ErosionScale` values as low
as **122.996** (range across the 90 autosaves: 122.996–726.028). Low
hundreds is a legal, Gaea-authored magnitude, not something I invented.

Putting those together:

```
                     authored     as fraction     stretched to
                     scale        of Width        an 8128 m import
canonical (alpine)   1413.3 m     0.28265         2297.4 m
badlands             340.0 m      0.06800          552.7 m
```

**At 1413.25 the erosion operates at massif scale** — one or two enormous
valleys across the whole region, which is exactly right for an alpine
massif and is why the alpine terrain reads the way it does. Badlands need
the opposite: a **dense dendritic network** whose master channels are
hundreds of metres apart, not kilometres, with a finer sub-network filling
in between them.

**Why 340 and not 123.** At ~123 the master drainages would land near
200 m apart after the import stretch. At 1 m/vertex that risks reading as
a fine eroded *texture* — noise at gameplay range — rather than as canyons
a player walks into and along. 340 keeps the master drainages at ~550 m
after stretch, which is a walkable, streamable spacing that still leaves
room for the sub-network. **This is a judgement, and it is stated as one.**
It is the first parameter to move if the first build reads wrong.

---

## 4. WHAT PARAMETERS CANNOT DO HERE — READ THIS BEFORE BUILDING

**The graph's base surface is `Mountain + Ridge → Combine[Max]`, and no
parameter in this file can turn that into a plateau.**

That matters because **badlands are a dissected plateau**. The defining
features are *flat interfluves with sharp rims*, and the erosion is what
cuts into them. This graph's base is a mountain field maximum-blended with
a ridge field — peaked and ridged by construction.

- `Mountain.Height` scales the base **amplitude**, not its **shape**.
  Lowering it to 0.62 gives *low hills*, not *flat interfluves separated by
  sharp rims*.
- `Ridge` serialises **only `Seed`** in this file. There is no amplitude,
  weight or scale knob, so ridgelines — the opposite of a flat interfluve —
  cannot be attenuated.
- `Combine.Mode` is `"Max"`. `"Subtract"` is a legal value (observed in the
  autosaves), and `Mountain − Ridge` would carve ridge-shaped valleys,
  which is superficially canyon-like. **I did not take it**: the result is
  unpredictable without a build, it can drive the field negative, and
  shipping a mode flip I cannot reason about would be guessing dressed as
  authoring.
- `Combine.PortCount` is **FORBIDDEN**. Each port is an `$id`; changing the
  count is an id-allocation problem, i.e. a structural edit.

**So what this file will actually build is a heavily dissected, low-relief
eroded upland with a dense dendritic drainage network — arroyo country.**
That is genuinely a different landform class from the alpine massif. It is
**not** badlands-with-a-canyon, and the gap is structural, not a tuning
problem. §7 names the two nodes that close it.

---

## 5. THE SNOW EXPORTS ARE LOAD-BEARING, AND THIS IS THE MOST LIKELY BUILD FAILURE

**Snow cannot be switched off, even though this region is arid.**

`verify_build.SPEC` (`scripts/verify_build.py:65-84`) requires both
`Snow_Snow.png` and `SnowMask_Out.png` in the package, and
`MIN_UNIQUE = 16` (`:58`) with the refusal at `:294-295` declares that *"a
channel carrying fewer distinct values than this is not data."* R-GAEA §2
records that Gaea 2.3 exports the Snow channel as a **degenerate
near-1-bit PNG when the sim output is uniform** — present, correctly named,
correctly sized, and carrying nothing.

`SnowLine 1.0` / `Intensity 0` would produce exactly that uniform field.
Both masks would go degenerate and **`verify_build.py` would refuse the
build** — correctly, with the cause sitting here in the `.terrain` rather
than in the package.

Hence `SnowLine 0.88` and `Intensity 0.11` rather than off.

**Consequence, stated plainly: on this region the two snow exports are
REPURPOSED.** At `SnowLine 0.88` they should mark only the highest
surviving interfluve caps — which is, usefully, a **caprock / mesa-top
mask**, and the resistant caprock is precisely what preserves a mesa. A
badlands surface material wants that mask. But **the file still calls them
`Snow` and `SnowMask`, and `verify_build.SPEC` still describes them as
`"hard snow coverage mask"` and `"graded snow depth mask"`.** That is a
naming mismatch a later reader will trip over, and it is outside my write
permission to fix.

**PREDICTION, NOT MEASUREMENT.** Whether `SnowLine 0.88` leaves ≥16
distinct values in *both* exports is unverified and is **the single most
likely reason a first build of this file fails its gate.** If it does:
lower `SnowLine` (more coverage) and change nothing else. Do not reach for
`Intensity` or `Duration` first.

---

## 6. EXPECTED Z SPAN AND UE `z_scale_cm` — A PREDICTION, NOT A MEASUREMENT

**R-GAEA §6's method, single definition at `rebuild_terrain.derive_z_scale`
(`:147-163`):**

```
occupancy = (source_max - source_min) / 65535      measured from the
                                                   built Snow_Out.png
span_m    = Terrain.Height * occupancy
Z         = span_m / 512.0 * 100                   512 m is UE's 16-bit
                                                   height range at Z=100
```

`Terrain.Height` for this file is **1200.0**.

**The occupancy is unknowable until a build runs and is normalised.** The
only empirical anchor available is a *different parameter set* — AlpineLab
build 006, whose `height_normalization.json` records `occupancy
0.37035172`, `project_height_m 2500.0`, `span_m 925.879`, `ue_z_scale
180.8358`. Long erosion at high downcutting lowers the mean and deepens
the tail, so this region's occupancy will move, in a direction I cannot
predict.

So the honest answer is a band, not a number:

| occupancy | span_m | derived `z_scale_cm` |
|---|---|---|
| 0.25 | 300.0 m | **58.594** |
| 0.30 | 360.0 m | **70.312** |
| **0.37035** (alpine 006 anchor) | **444.42 m** | **86.801** |
| 0.45 | 540.0 m | **105.469** |
| 0.55 | 660.0 m | **128.906** |

**Best single estimate: span ≈ 444 m, `z_scale_cm` ≈ 86.8** — but that
carries the alpine build's occupancy, which is the weakest assumption on
this page.

**NONE OF THIS IS MEASURED.** It is arithmetic on an unbuilt file. R-GAEA
§9's rule stands unchanged: `rebuild_terrain.py` writes
`height_normalization.json` **before** the stretch, and *that sidecar* is
the Z scale of record. Do not type any number from this table into an
import dialog. And do not fall back to 100 if the range is unreadable —
`derive_z_scale` returns `None` for exactly that reason (R-GAEA REJECTED).

**Downstream naming defect, flagged, not fixed.** `rebuild_terrain.py:96`
hardcodes `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"` and
asserts it against `verify_build.SPEC` at `:277`. Building *this* project
therefore emits a badlands heightmap under an **alpine** filename. The
`--project` flag is parameterised; the output name is not. That wants
fixing before a second region is built for real, and it is outside my
write permission.

---

## 7. HONEST VERDICT ON ACHIEVABILITY

**Partially. Parameter variation produces a genuinely different landform
class — but not the region as briefed.**

**What parameter variation DOES deliver, and it is real:** a low-relief,
erosion-dominated upland with a dense dendritic drainage network at
arroyo spacing, deeply incised, with steep channel walls and no snow.
That is not "the same mountain rescaled" — the base amplitude is down 70%,
the erosion operates at 24% of its previous scale, every seed is different,
and the project's vertical range is less than half. Held against the alpine
massif it should read as a different place, not a re-tint.

**What it does NOT deliver, and cannot:**

1. **Flat interfluves / mesa tops.** Badlands are a *dissected plateau*.
   `Mountain + Ridge → Combine[Max]` is peaked by construction, and no
   parameter in this file flattens it (§4). What builds is *dissected
   hills*, not *dissected plateau* — and that distinction is most of what
   makes badlands look like badlands.

2. **A canyon.** A master canyon is a discrete landform: one deep trunk
   with a flat floor and near-vertical walls. `Erosion2` produces a
   *drainage network statistic* at any `Duration`. No amount of downcutting
   turns a dendritic network into a Grand-Canyon trunk, because the node is
   not modelling one.

3. **Stratified banding.** The horizontal sedimentary layering exposed in
   canyon walls is the visual signature of the whole landform class, and
   nothing in this six-node graph produces it.

### The structural change I recommend, with the node names read from real files

Both node types below were **read from Gaea-written `.terrain` files on
this machine**, with their real `$type` strings and real parameter names.
Neither is invented. I am naming them, not adding them — adding either is
an `$id`-allocation problem and is outside the safe envelope.

**(a) `QuadSpinner.Gaea.Nodes.Stratify` — the highest-value single node.**
Read from `Migration_Bisect_A_LakeNode_2026-08-13_22-13-45.terrain`
(node id 328, named `Fantasy_Shelves`), carrying
`Spacing 0.24`, `Intensity 0.38`, `Shape 0.5`, `TiltAmount 0.12`, `Seed`.
Inserted **between `Combine` (750) and `Erosion2` (654)** it imposes
horizontal sedimentary bedding *before* erosion cuts into it — which is
both the stepped, banded wall texture and, because bedded rock erodes
differentially, the mechanism that produces flat caprock-held interfluves.
**One node buys items 1 and 3 together.** It needs one new node `$id`, one
new port pair, and the existing `750→654` record retargeted.

**(b) `QuadSpinner.Gaea.Nodes.Canyon` — for item 2.**
Read from `Untitled_2026-08-11_22-27-09.terrain` (node id 645, named
`Canyon`), serialising `Seed` and nothing else, meaning the rest of its
parameters sat at Gaea's defaults in that file. **I have not read its full
parameter surface and will not guess it.** It is a discrete landform
generator, which is the right shape of tool for a master canyon that
`Erosion2` cannot make.

**Recommended order:** build *this* file first. It is valid, it passes its
own gates, and it is the controlled single-variable answer to the question
the brief actually asks — *can parameter variation alone change landform
class?* Building it settles that empirically instead of by argument, and
it produces the occupancy figure §6 is missing. **Then** add `Stratify`
first and alone; it is the cheaper node, it closes two of the three gaps,
and adding one node at a time is the only way the `$id` allocation stays
reviewable.

---

## 8. VALIDATION — run from `C:\Users\Admin\UE5LandscapePipeline`

```
python scripts/read_gaea_graph.py --check-refs --project terrain/regions/badlands.terrain
    -> exit 0    $id defined 82, $ref used 23, every $ref resolves

python scripts/read_gaea_graph.py --check-spec --project terrain/regions/badlands.terrain
    -> exit 0    the graph predicts exactly the SPEC's Gaea-sourced files
                 (Erosion2_Flow/Wear/Deposits, Snow_Snow, SnowMask_Out;
                  Snow_Out excluded by design)
```

**The gates that passed are live gates, not dead ones.** `python
scripts/prove_gaea_reader.py` was re-run against this working tree and
still refuses all five corruptions (`rc=4, 4, 4, 3, 6`) while accepting
the shipped graph (`rc=0`), exit 0. A gate that has only seen good input
has not been tested — this one has.

**`--against-build` was NOT run**, and could not be: it compares a
prediction against a build that actually happened, and this project has
never been built. That is *"I could not look"*, not a pass.

---

## 9. STATED PLAINLY — WHAT IS NOT VERIFIED

- **Nothing here has been built.** No Gaea run, no editor, no pixels. Every
  landform claim in §2–§4 and §7 is a prediction.
- **Most parameter semantics are inferred from parameter names.** Every
  such row is tagged INFERRED in §2. Gaea ships no offline documentation of
  these fields that I could reach, and the `.terrain` carries names and
  values only. Treat the inferred rows as hypotheses a build must confirm.
- **`Erosion2.Downcutting 0.78` is extrapolated beyond every observed
  value** (autosave band 0.191–0.42; canonical 0.453). Most likely single
  number to be wrong.
- **Whether `Terrain.Height` affects the erosion simulation** — as opposed
  to only the export's metre mapping — is unverified. `Snow.RealScale
  false` suggests normalised-space simulation; I did not confirm it.
- **Whether `SnowLine 0.88` keeps both snow exports above `MIN_UNIQUE`**
  is unverified and is the most likely build-gate failure (§5).
- **The Z span and `z_scale_cm` in §6 are arithmetic on an assumed
  occupancy borrowed from a different parameter set.** They are a
  prediction until `height_normalization.json` exists for a real build.
- **No `ASSETS.md` row, no `recipes/badlands.json`, no `RECIPES.md`
  entry.** This session's write permission was scoped to
  `terrain/regions/` only. The new-element rule is therefore **not
  satisfied** — a region recipe is owed before this is treated as region
  two.
- **`WORLD_VISION.md:171-177` records that contiguous-vs-multi-region is an
  OPEN DECISION Ryan took back, with a tripwire that nothing may be built
  on either assumption.** This file is a terrain candidate, not a claim
  that region two exists. `WORLD_VISION.md:263-292` also records that a
  region's landform *means* something — the alpine massif's basins are its
  settlement zones, its corridor is its traversal axis. **This file has no
  such reading authored for it.** Badlands are hostile, low-water,
  navigationally confusing ground; what that means for settlement,
  traversal and difficulty is a design act, and it has not been done.
