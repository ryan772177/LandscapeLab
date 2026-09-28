# coastal.terrain — authoring note

**Region brief:** coastal cliffs and headlands. Sea-level datum at one
edge, cliffs, headlands and coves, rising inland.

**Verdict up front, because it governs how the file should be read:
THE SEA-LEVEL DATUM IS NOT EXPRESSIBLE BY PARAMETER VARIATION IN THIS
GRAPH. It needs a structural change — one node minimum, two for the
region as briefed.** Section 6 names them, with citations. Section 4
says plainly what this file *will* build instead, which is not the
region asked for.

---

## 1. WHAT THIS FILE IS

    source      C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain
                (the CANONICAL saved project, 16,227 bytes, DateLastSaved
                2026-08-09 19:40:40Z, Metadata.Version 2.3.0.1 —
                confirmed canonical because it is the file at
                rebuild_terrain.py:90 DEFAULT_PROJECT and it is NOT under
                %APPDATA%\QuadSpinner\Gaea\2.0\Autosaves, which is where
                rebuild_terrain.py:296-305 `_hint_autosaves` looks)

    output      terrain/regions/coastal.terrain   16,196 bytes

    method      the source document was loaded as JSON, TEN NUMERIC LEAF
                VALUES inside `Nodes` were replaced, and the document was
                re-serialised at the same indent and the same CRLF line
                endings. No `$id` was created or destroyed. No `$ref` was
                touched. No node was added, removed, renamed or rewired.
                No JSON KEY was added or removed.

**Proven, not asserted — a full line diff against the canonical file
returns exactly the ten edited leaves and nothing else:**

    16,18c16,18   Mountain  Scale / Height / Seed
    57c57         Ridge     Seed
    171,174c171,174  Erosion2  Duration / Downcutting / ErosionScale / Seed
    273c273       Snow      SnowLine
    275c275       Snow      Seed

The 31-byte size difference (16,227 → 16,196) is exactly the sum of the
shortened numeric literals, which is an independent arithmetic check
that nothing else moved.

### Gate results — run from `C:\Users\Admin\UE5LandscapePipeline`

    python scripts/read_gaea_graph.py --project terrain/regions/coastal.terrain --check-refs
      $id defined : 82
      $ref used   : 23
      every $ref resolves to a real $id.
      EXIT 0

    python scripts/read_gaea_graph.py --project terrain/regions/coastal.terrain --check-spec
      the graph predicts exactly the SPEC's Gaea-sourced files.
      EXIT 0

`$id` 82 and `$ref` 23 are IDENTICAL to the canonical file's counts,
which is the point: a parameter edit cannot move them, and if it had,
that would mean the edit was not a parameter edit.

Note on invocation: `read_gaea_graph.py` takes `--project <path>`, not a
positional argument. `--check-refs <file>` exits **2** with
*"unrecognized arguments"* — an argparse refusal, not a graph verdict.

The instrument's own negative controls were re-run in the same session:
`python scripts/prove_gaea_reader.py` → **exit 0**, 1 positive control
accepted and 5 corruptions refused (rc 4/4/4/3/6). So a passing
`--check-refs` here is a measurement, not a gate that says yes to
everything.

---

## 2. EVERY PARAMETER CHANGED — with its provenance class

The classes matter. The recon report's own self-audit withdrew a set of
per-parameter landform explanations as **name-inferred, not measured**,
and that withdrawal is respected here rather than quietly re-committed.

| Node | Parameter | From | To | Class |
|---|---|---|---|---|
| 877 Mountain | `Scale` | 0.74927175 | **0.42** | HYPOTHESIS |
| 877 Mountain | `Height` | 2.032038 | **1.05** | TOPOLOGY (mechanism read; magnitude unmeasured) |
| 877 Mountain | `Seed` | 22109 | **41027** | re-roll |
| 650 Ridge | `Seed` | 38804 | **51163** | re-roll |
| 654 Erosion2 | `ErosionScale` | 1413.2517 | **400.0** | MEASURED ratio |
| 654 Erosion2 | `Downcutting` | 0.4531411 | **0.78** | HYPOTHESIS |
| 654 Erosion2 | `Duration` | 21.648195 | **14.0** | HYPOTHESIS (coupled to ErosionScale) |
| 654 Erosion2 | `Seed` | 15025 | **30871** | re-roll |
| 599 Snow | `SnowLine` | 0.056395777 | **0.62** | MEASURED mechanism |
| 599 Snow | `Seed` | 59434 | **20514** | re-roll |

### DELIBERATELY NOT CHANGED, and why that is a decision

- **`Snow.Duration` / `Intensity` / `SettleThaw` / `Melt`** — left at the
  alpine values. `SnowLine` is the one snow parameter whose mechanism is
  MEASURED (R-GAEA §2: *"Snow Line is INVERTED. A LOWER value produces
  MORE snow"*). The other four govern how snow behaves once deposited and
  I have no measured basis for retuning them. Inventing four plausible
  numbers is the exact defect the recon self-audit named.
- **`Combine.Mode`** — stays `"Max"`. Other values (`Min` would give a
  drowned-intersection landform that is superficially coastal) are enum
  strings I did **not** read anywhere. Writing an unverified enum member
  into a Newtonsoft-deserialised field is a guess with an unknown failure
  mode. NN23: an API remembered is an API guessed, and that applies to
  enum members.
- **`Combine.PortCount`**, **`Snow.RealScale`**, **`SnowMask.RenderIntentOverride`** —
  `PortCount` is structure wearing a parameter's clothes (it governs how
  many `Ports` entries exist, each with its own `$id`); the other two had
  no motivated change.
- **Everything outside `Nodes`** — `Terrain.Id` GUID, project `Id`,
  `Metadata`, `BuildDefinition`, `State`, `GraphTabs`. Left byte-identical
  so the provenance claim in §1 is checkable by a line diff.

### The reasoning, parameter by parameter

**`Erosion2.ErosionScale` 1413.2517 → 400.0 — the strongest change, and
the only one resting on arithmetic rather than on a parameter's name.**
MEASURED: `Terrain.Width` is 5000.0 and `ErosionScale` is 1413.2517, so
alpine's erosion features are authored at **0.28265 of the canvas**. The
region is imported at 8128 m (CURRENT STATE, `/Game/Alpine8K`), which
stretches every authored feature by **8128 / 5000 = 1.6256×** — so
alpine's erosion feature scale lands at ~2,297 m in UE, which is a
glacial-valley scale. Headlands and coves are 200–800 m features. 400.0
is **0.08 of the canvas**, landing at **400 × 1.6256 = 650.2 m** in UE.
That is the size of an inlet, not a valley. This is the parameter that
changes the *texture* of the landform from alpine to coastal, and it is
the one I would defend hardest.

**`Mountain.Height` 2.032038 → 1.05 — argued from the wiring, not the
name.** READ at node 750: `Mode: "Max"`, with `Mountain.Out` on the `In`
port (`$id` 21) and `Ridge.Out` on `Input2` (`$id` 24). The Combine is a
per-pixel MAX arbitration between the two generators. `Ridge` carries no
`Height` in this file (only `Seed`), so its amplitude is fixed at the
node default. Lowering `Mountain.Height` therefore shifts the arbitration
toward Ridge across more of the canvas, and the landform reads less as
one massif and more as a field of linear crests and troughs — which is
the closest available analogue to a spur-and-inlet headland coast.
**The mechanism is read from the file; the magnitude is not.** Where the
crossover sits depends on Ridge's default amplitude, which I could not
measure. 1.05 is a directional move, and the first build must be looked
at rather than trusted.

**`Mountain.Scale` 0.74927175 → 0.42 — HYPOTHESIS, from the parameter
name only.** Intent: more, smaller promontories rather than one broad
massif. I have no citation for what `Scale` does and the recon's
explanation of it was explicitly withdrawn. If the first build shows
this went the wrong way, invert it; the cost is one rebuild.

**`Erosion2.Downcutting` 0.4531411 → 0.78 — HYPOTHESIS.** Intent: steep
sided inlets rather than broad graded valleys. Name-inferred.

**`Erosion2.Duration` 21.648195 → 14.0 — HYPOTHESIS, with a coupling
argument.** The alpine pair (Duration 21.65, ErosionScale 1413.25) was
tuned together at the coarse scale. At 3.53× finer `ErosionScale` the
same Duration does proportionally more work per feature, so holding
Duration constant is not a neutral choice either. 14.0 is a modest
reduction rather than a swing, deliberately, because I cannot predict
the direction confidently and a small step is cheaper to correct.

**`Snow.SnowLine` 0.056395777 → 0.62 — MEASURED mechanism, chosen value
constrained by a gate.** R-GAEA §2 records the inversion, and the
autosave trace 0.47 → 0.18 → 0.056 confirms alpine was tuned *down* to
get *more* snow. A coastline at sea level has none. **But it cannot go to
~1.0, and the reason is a gate:** `Snow_Snow.png` is a required member of
`verify_build.SPEC` (`scripts/verify_build.py:80-83`), and
`verify_build.py:59` sets `MIN_UNIQUE = 16` with `:294` reporting
`DEGENERATE` below it — precisely the Gaea 2.3 uniform-sim export R-GAEA
§2 warns about. **A genuinely snow-free region cannot pass
`verify_build.py` as the SPEC currently stands.** 0.62 keeps snow on the
high inland ground only, which is both a defensible coastal reading (a
sea cliff with mountains behind it — Norway, Skye, British Columbia) and
keeps the mask non-degenerate. **This is a PREDICTION and the gate is the
test:** if a build reports `Snow_Snow.png DEGENERATE`, lower `SnowLine`
until it does not, or change the SPEC deliberately.

**The four seeds** are re-rolled so this is a different landform rather
than the alpine one re-dressed. They are opaque integers; no meaning is
claimed for the specific values.

---

## 3. A DISCREPANCY FOUND IN OUR OWN RECORD

**`RECIPES.md` R-GAEA §1 states the graph's Snow node runs at
`Snow Line ~0.65`. The canonical file says `0.056395777`** — an order of
magnitude apart, and on the inverted axis, the opposite end of the
control. R-GAEA §1's figure appears to predate the tuning trace
(0.47 → 0.18 → 0.056) and was never corrected.

Reported, **not fixed** — `RECIPES.md` is one of the two files a standing
escalation covers and this note has no authority over it. Flagged because
§1 is a summary block, which is exactly the position where a stale value
is most dangerous (the struck talus-threshold entry, same shape).

Coincidence worth naming so nobody reads it as corroboration: my chosen
0.62 is close to R-GAEA §1's stale 0.65. That is an accident. My value
comes from the degeneracy constraint in §2, not from R-GAEA §1.

---

## 4. WHAT THIS FILE WILL ACTUALLY BUILD — stated honestly

**Not a coastline.** There is no sea, no datum, no shoreline, no cove.

What it should build is a **finely dissected, ridge-dominated upland with
inlet-scale incision and snow confined to the high inland ground** — the
*texture* of a headland coast applied to a landform that still runs from
peak to valley with no water in it. Set beside `/Game/Alpine8K` it will
read as a different, lower, more finely cut massif.

Against `WORLD_VISION.md`'s standard — *"regions must belong to the
world, not be a tech demo of terrain types"* — **this file does not yet
earn a region slot.** It is a parameter study that answers "can the
alpine graph be re-tuned to coastal feature scales" (yes) and not "can it
express a coast" (no). It is committed as the evidence for §6, not as a
region.

---

## 5. Z SPAN AND UE `z_scale_cm` — A PREDICTION, NOT A MEASUREMENT

**No build has been run. Everything in this section is a prediction and
stays a prediction until `height_normalization.json` exists.**

The method is R-GAEA §6, implemented at `rebuild_terrain.py:160-163`:

    occupancy = (source_max - source_min) / 65535
    span_m    = Terrain.Height * occupancy          # Terrain.Height = 2500.0
    z_scale   = span_m / 512.0 * 100                # UE_HEIGHT_SPAN_M_AT_Z100

`Terrain.Height` is **2500.0** in `coastal.terrain`, unchanged from the
canonical file. **It is the PROJECT RANGE, not this build's span.** Typing
it straight in gives `2500 / 512 * 100 = 488.3` and a landscape 2.7× too
tall that looks entirely plausible. Do not.

Alpine build 006, for reference (`006/height_normalization.json`, read):

    source_min 495.0   source_max 24766.0
    occupancy  0.37035   span 925.879 m   ue_z_scale 180.8358

**Predicted direction for coastal: occupancy BELOW 0.37035, therefore
span below 925.9 m and `z_scale` below 180.84.** Both height levers moved
down — `Mountain.Height` 2.03 → 1.05 lowers the Max's ceiling over the
Mountain-dominated area, and `SnowLine` 0.056 → 0.62 removes snow mass
that was being added on top of the exported height (the heightmap is the
**Snow** node's `Out`, `rebuild_terrain.py:95` `HEIGHT_SOURCE =
"Snow_Out.png"`). Nothing moved the other way.

**A magnitude is NOT predicted**, because `Ridge` carries no `Height` in
this file and its default amplitude sets a floor on the span that I could
not measure. Illustratively only — if occupancy comes back at 0.22, then
span = 550.0 m and `z_scale_cm` = **107.4**. That number is an
illustration of the arithmetic, not a forecast.

**What to do instead of trusting any of this:** run
`scripts/rebuild_terrain.py`, read `ue_z_scale` out of the sidecar it
writes, and use that. `derive_z_scale` returns `None` rather than a
default when the range is unreadable (R-GAEA REJECTED), and that refusal
is the right behaviour to lean on.

---

## 6. THE STRUCTURAL CHANGE THIS REGION NEEDS

### Why parameters cannot do it

The whole graph is:

    Mountain ──┐
               ├─ Combine[Max] ── Erosion2 ── Snow ── (SnowMask)
    Ridge ─────┘

Read against the brief, three things are missing and none of them is a
number:

1. **Nothing in the graph has a concept of ABSOLUTE HEIGHT.** No node
   clamps, floors or floods. `Combine[Max]`, `Erosion2` and `Snow` all
   transform a field; none of them declares "below this value is water".
   A flat datum is a *floor operation*, and there is no floor operation
   in the file.
2. **Nothing in the graph has a concept of DIRECTION.** `Mountain` and
   `Ridge` are both whole-canvas generators, and neither carries an
   offset in this file. There is no ramp, no gradient, no axis. "Low at
   one edge, rising inland" is a directional statement and the graph has
   no directional term to vary.
3. **The normalisation downstream is a linear stretch, so it preserves a
   flat region but cannot create one.** `rebuild_terrain.normalize_height`
   maps min → 0 and max → 65535. If the field had a plateau at its
   minimum, that plateau would survive as a flat 0 region. It does not
   have one, and no parameter in these six nodes makes one.

**Erosion2 does deposit sediment into low ground, and enough of it will
partially level valley floors.** That is the closest a parameter gets,
and it is not close: it produces locally flattened valley bottoms at many
different elevations, not one datum, and not on one edge.

### The node that would fix it — cited, with a worked instance

`QuadSpinner.Gaea.Nodes.Sea` is a real node in this Gaea install. It is
not a name I am proposing; it is a node I read, with its parameters and
its ports, from a shipped project file:

    C:\Program Files\QuadSpinner\Gaea 2\Examples\Canyon River with Sea.terrain
      node 243
        "$type": "QuadSpinner.Gaea.Nodes.Sea, Gaea.Nodes"
        "Level":       0.02
        "ShoreSize":   0.4672725
        "ShoreHeight": 0.34018856
        "Variation":   1.0
      ports
        In      PrimaryIn, Required     (wired from node 199, HydroFix.Out)
        Out     PrimaryOut              <- the height WITH the sea flattened
        Edge    In
        Water   Out
        Depth   Out
        Shore   Out
        Surface Out

A second instance in `Cartography - Mineral Map.terrain` additionally
carries `CoastalErosion` and `UniformVariations`, so the node's parameter
surface is wider than the four above.

`Level` is the datum. `Shore*` are the cliff-and-beach transition the
brief's "cliffs" wants. `Water` / `Depth` / `Shore` are ready-made masks
for a coastal material — the same role `Erosion2_Flow` plays today.

**`Sea` alone gets you a real coastline, and it is worth saying which
kind.** A `Level` above the minimum floods every low area, so a finely
dissected upland becomes a **drowned-valley (ria) coast** — exactly
headlands and coves, the Brittany/Cornwall/Galicia form. That is one
node, and this file's fine `ErosionScale` is precisely the input that
makes it work.

**What `Sea` alone does NOT give you is "sea at one edge, rising
inland".** For that you also need a directional ramp added into the
height before the `Sea`. Also cited, also read from shipped projects:

    QuadSpinner.Gaea.Nodes.LinearGradient, Gaea.Nodes
      Cartography - Mineral Map.terrain, node 616:  "Direction": 270
      Structure - Side Carved Mountains.terrain, node 470: defaults only
      ports: In (PrimaryIn), Out (PrimaryOut)

`Direction` is in degrees (270 in the observed instance). Combining a
`LinearGradient` into the terrain tilts it along a chosen bearing, which
is what puts the sea on one edge and the rise inland.

### The consequence chain, so nobody discovers it mid-build

Adding these is not just an id-allocation problem. It moves two contracts:

- **The heightmap export moves.** The height is currently the **Snow**
  node's `Out` port — `Snow_Out.png`, `rebuild_terrain.py:95`
  `HEIGHT_SOURCE`, and `verify_build.EXCLUDED`. If a `Sea` node is placed
  after `Snow`, the height becomes `Sea_Out.png` and `HEIGHT_SOURCE`,
  `verify_build.SPEC` and `verify_build.EXCLUDED` must all move together.
  `rebuild_terrain.py:274-286` already refuses when those three disagree,
  which is the right failure and will fire.
- **`Combine.PortCount` is 2 and both inputs are used.** Feeding a third
  field in means either `PortCount: 3` plus a new `Ports` entry with a new
  `$id`, or a second `Combine` node. Both are structural.

### Recommended sequence

1. **A `.terrain` writer with id allocation**, whose acceptance test is
   `--check-refs` — which already exists and already refuses a dangling
   `$ref` with rc=3 (`prove_gaea_reader.py`, re-run this session).
2. **`Sea` first, alone**, on top of this file's parameters. One node,
   one contract move, and it delivers a genuine ria coastline that can be
   looked at.
3. **`LinearGradient` second**, only if the ria form is judged not to be
   the region wanted. It is the more invasive change and it is the one
   that needs a second `Combine`.

---

## 7. TWO MORE THINGS A BUILDER OF THIS FILE WILL HIT

**`rebuild_terrain.py` CANNOT BUILD A SECOND REGION AS IT STANDS, and it
is the 8129 defect class again.** Three region-specific quantities are
written as though only one region would ever exist:

    :89   DEFAULT_ROOT   C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1
    :96   HEIGHT_OUTPUT  "AlpineLab_v1_Height_normalized.png"
    :103  HEIGHT_IMPORT_ALIAS  "AlpineLabHeight.png"

and `verify_build.SPEC` keys on that same `AlpineLab_v1_…` filename.
Building `coastal.terrain` without `--root` drops the build into
AlpineLab_v1's `NNN` sequence, and its heightmap is emitted under a name
that says "AlpineLab_v1" regardless. `--root` fixes the directory; the
**filename** cannot be fixed by a flag. This is the same shape as the
seven parameters in CURRENT STATE 2026-08-14's table, and it is
non-negotiable 19: a per-region quantity stored as a module constant.

**Strict JSON is a safe subset here, but not a symmetric one.** At least
one shipped example (`Cartography - Mineral Map.terrain`) fails Python's
strict `json.load`; Newtonsoft accepts it. `coastal.terrain` was produced
*by* Python's serialiser, so it is strict JSON and therefore also valid
Newtonsoft JSON. A future writer must not assume the reverse.

---

## 8. WHAT I COULD NOT VERIFY — stated plainly

- **No build was run.** Gaea was not launched (forbidden by the brief and
  by the live-editor condition). Every landform claim in §2 and §4 is a
  prediction. The file has been proven to be *well-formed and
  id-consistent*, and proven to be *the canonical graph with ten leaves
  changed*. It has **not** been proven to build, to build something
  coastal, or to build something good.
- **The Z span in §5 is a prediction**, and the illustrative 107.4 is an
  arithmetic example rather than a forecast.
- **Six of the ten parameter changes rest on the parameter's NAME**, not
  on any measured or cited semantics. They are tagged HYPOTHESIS in §2's
  table and must be judged against the first build, not trusted.
- **Ridge's default amplitude is unmeasured**, which is why §2's
  `Mountain.Height` argument gives a direction and no crossover point,
  and why §5 gives no span magnitude.
- **`Snow_Snow.png` non-degeneracy at `SnowLine` 0.62 is unverified.**
  The gate that decides it is `verify_build.py:294` and it has not run.
- **`Mountain` carries `X`, `Y`, `Style`, `Bulk`, `ReduceDetails`, and
  `Erosion2` carries `Direction`, `RainShadow`, `DirectionalPrecipitation`,
  `Altitude`** — read from the example corpus, absent from our canonical
  file because Newtonsoft omits defaults. `Erosion2.Direction` in
  particular would give directional (onshore-wind) erosion, and
  `Mountain.X`/`Y` would offset the massif toward one edge. **I did not
  add them.** Adding a key preserves every `$id` and `$ref` and would pass
  `--check-refs`, so it is arguably inside the safe envelope — but their
  DEFAULT values are unknown to me, so I could not state what a written
  value would change *from*, and neither of them produces a datum anyway.
  Recorded as the highest-value next parameter-level experiment, and as an
  open question about where the "parameter edit" envelope really ends.
