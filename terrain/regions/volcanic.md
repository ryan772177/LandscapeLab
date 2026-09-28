# volcanic.terrain — Volcanic ashlands, authoring note

**Status: PARAMETER VARIANT, BUILT BY NOBODY.** No Gaea build has run
from this file.

**The Z span and z_scale_cm are UNKNOWN, and §4 says so rather than
predicting them.** They depend on the occupancy of the exported height,
which is a property of a build output and cannot be derived from a
project file. An earlier version of §4 published a predicted
`z_scale_cm 244.14`; it was fabricated from an unsupported linearity
assumption and is withdrawn — see §4c, which keeps it as a record.

Everything else here about the *output* — whether the flanks read as
smooth, whether ash plains form, whether reduced erosion reads as young
— is likewise unbuilt and unmeasured. The only measured things in this
document are the file's contents, the two gate results, and the
structural diff.

Source: `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain`
— the canonical project, not one of the autosaves (R-GAEA §9 REJECTED,
"Building from an autosave .terrain"). Confirmed canonical by path: it is
the only `.terrain` at the package root, the 71 rotating autosaves live
under Gaea's own `Autosaves` folder and are named with a timestamp.

---

## 1. THE HEADLINE, FIRST — this file does NOT deliver the region as briefed

**The two defining features of volcanic ashlands — a CONE and RADIAL
DRAINAGE — are not reachable by parameter variation of this graph, and no
value of any knob in it gets close.** Section 6 says why, names the node
that would fix it, and answers the brief's question about erosion
directly. Read section 6 before you build this.

What this file *is*: a young, high-relief, weakly-incised fractal upland
under a thick settled mantle. That is a legitimate and distinct region
from alpine, and it is the closest this graph reaches. It is **not** a
volcanic landform, and the filename is aspirational.

---

## 2. WHAT WAS CHANGED — every leaf, with the old value

18 leaves changed. **0 structural leaves changed**, verified
mechanically: identical key-path set, identical `$id` sequence (82),
identical `$ref` sequence (23), and every `SaveDefinition`
Filename/Format/IsEnabled/Node byte-identical.

**THE FOUR NEW SEEDS ARE ARBITRARY. Do not look for meaning in them.**
48213 / 26907 / 33641 / 51078 were picked to be five-digit integers in
the same magnitude class as the originals and to differ from them. The
*only* requirement a seed carries here is that it is not alpine's, so
that this is a different terrain rather than the same mountain retuned.
They are recorded because a seed must be reproducible, not because they
were chosen.

### Mountain — node 877, `$id` 6, `QuadSpinner.Gaea.Nodes.Mountain`

| Parameter | From | To | Why |
|---|---|---|---|
| `Scale` | 0.74927175 | 0.9 | **INFERRED FROM THE NAME, NOT VERIFIED.** Intent: fewer and broader edifices rather than a dense range, so the map reads as a small number of large volcanic massifs. If the response is the opposite of what the name suggests, this is the first value to invert. |
| `Height` | 2.032038 | 2.75 | Primary relief up 35.3%. The brief asks for *high primary relief*; this is the only amplitude control in the graph (`Ridge` has none — see below). Sanity-checked against a real reference class in §4. |
| `Seed` | 22109 | 48213 | A region must be a different terrain, not the same mountain retuned. |

### Ridge — node 650, `$id` 12, `QuadSpinner.Gaea.Nodes.Ridge`

| Parameter | From | To | Why |
|---|---|---|---|
| `Seed` | 38804 | 26907 | New terrain. |

**`Seed` is the ONLY parameter this node has.** Read from the file: node
650 carries `$id`, `$type`, `Seed`, `Id`, `Name`, `Position`, `Ports`,
`Modifiers` and nothing else. There is no amplitude, scale or sharpness
control. **The ridged-crest contribution to the landform is therefore
FIXED** and cannot be attenuated — which matters, because linear ridge
crests are the wrong texture for a volcanic edifice and I cannot turn
them down. See §6.

### Combine — node 750, `$id` 18 — **UNCHANGED, deliberately**

`Mode: "Max"` and `PortCount: 2` are both untouched.

- `PortCount` is coupled to the four Port objects (`$id` 21/23/24/26) and
  their `Record` back-references. Changing it is a structural edit
  wearing a parameter's clothes.
- `Mode` I could not safely change because **I could not enumerate the
  valid enum set.** An ASCII string scan of `Gaea.Nodes.dll` and
  `Gaea.Engine.dll` does not contain `Max`, `Min` or `Add` as standalone
  strings even though the canonical file plainly uses `"Max"` — so the
  members live somewhere my instrument cannot read. That is
  "I could not look", not "there are no other modes"
  (non-negotiable 6). Writing an unverified enum string is the
  NN23 shape: a plausible name that does not exist, which JSON will
  happily carry and Newtonsoft may silently fall back on.

**This is a real loss.** With no ratio on `Combine` and no amplitude on
`Ridge`, the Mountain:Ridge blend is not tunable at all.

### Erosion2 — node 654, `$id` 28 — **the headline change**

| Parameter | From | To | Why |
|---|---|---|---|
| `Duration` | 21.648195 | 4.2 | **19.4% of alpine's.** This is the "low erosion maturity" lever and the brief's central experiment. |
| `Downcutting` | 0.4531411 | 0.68 | **INFERRED.** Intent: the few channels that do form incise as sharp notches rather than washing out into broad graded valleys — i.e. barranca-like rather than mature-dendritic. Pairing *low duration* with *high downcutting* is the whole shape of the idea: little total erosion, but what there is, is vertical. |
| `ErosionScale` | 1413.2517 | 2300.0 | See the arithmetic below. Coarser, fewer, longer channels. |
| `Seed` | 15025 | 33641 | New terrain. |

**`ErosionScale`, with the numbers, because it is coupled to `Width` and
to the import extent:**

    Terrain.Width (authored)          5000.0 m      (read from the file)
    alpine  ErosionScale 1413.2517 =  0.2827 x Width
    this    ErosionScale 2300.0    =  0.4600 x Width

    UE import extent                  8128 m
    import stretch  8128 / 5000    =  1.6256 x     (CLAUDE.md, ~1.63x)

    alpine ES in world metres      =  2297.4 m
    this   ES in world metres      =  3738.9 m

**The four numbers above are MEASURED** — read from the file, from
CLAUDE.md's import extent, and from division. **What follows from them
is INFERRED and is tagged here because the original draft stated it as
an argument rather than as a hypothesis:**

At 3739 m the erosion characteristic length approaches the size of a
whole edifice on an 8128 m map. The *intent* in raising it is that when
the erosion scale is edifice-sized, the channels that form are few and
long and run the full flank — sparse and flank-length instead of finely
dendritic, which would be the correct *statistics* for a young volcanic
flank even with the wrong *geometry*.

**That chain rests on `ErosionScale` meaning "characteristic length of
the erosion features", which I inferred from the name and did not
verify.** If it instead scales intensity, or is a solver resolution, the
reasoning collapses and the value should go back to alpine's ratio. A
single build settles it: count and measure the channels.

### Snow — node 599, `$id` 41 — **repurposed as an ASH MANTLE**

**This is an interpretation, and it is the least defensible thing in this
file. Flagged, not hidden.** The `Snow` node is in the height path — its
`Out` port is the exported heightmap (`Snow_Out.png`, confirmed at
`rebuild_terrain.py:95` `HEIGHT_SOURCE = "Snow_Out.png"`), so whatever
mass it deposits becomes terrain. Deposition of a fine granular material
that blankets a surface, thins on steep faces and thickens in hollows is
geomorphologically the same operation as airfall ash mantling. I am using
it as one. `SnowMask_Out.png` then becomes the region's **ash-depth
mask**, which is genuinely useful downstream.

| Parameter | From | To | Why |
|---|---|---|---|
| `SnowLine` | 0.056395777 | 0.02 | **THE CONTROL IS INVERTED — LOWER MEANS MORE** (R-GAEA §2, and corroborated by the autosave trace 0.47 -> 0.18 -> 0.056 as Ryan increased snow). Near-total mantle, which is what an ashland is. Alpine was already at 0.056, so this is a small marginal move; do not expect much from it alone. |
| `Intensity` | 0.40226594 | 0.72 | **INFERRED.** More deposited mass = thicker mantle. |
| `SettleThaw` | 0.3619003 | 0.78 | **INFERRED.** More settling = a smoother, better-graded blanket. This is the only *smoothing* lever in the whole graph and it is doing the work that "smooth flanks" asks for. |
| `Duration` | 0.4066604 | 0.55 | **INFERRED.** Longer deposition/settling run. |
| `Melt` | 0.450141 | 0.22 | **THE ONE VALUE WHOSE DIRECTION I CANNOT PREDICT — see below.** |
| `Seed` | 59434 | 51078 | New terrain. |
| `RealScale` | false | *unchanged* | A bool whose semantics (probably: couple the sim to real-world metres) I did not verify. Changing an unverified switch is not a tuning decision. |

**`Melt`, stated plainly as an unknown.** The recon report's guess
("pools in hollows vs sheds off faces") was explicitly withdrawn as
name-inference, and I did not recover the real semantics either. Two
candidate meanings point opposite ways for this region:

- if `Melt` = **mass loss**, then LOWER preserves mantle thickness. Good.
- if `Melt` = **redistribution into hollows**, then lower means LESS
  hollow-filling — which works *against* the ash plains the brief asks
  for.

I chose 0.22 (down), which is conservative toward *mantle uniformity* and
**against** *plain formation*. **If the first build shows a uniform
blanket and no distinct ash plains in the low ground, `Melt` is the first
parameter to raise**, and 0.45–0.70 is where I would look. This is
recorded as a decision with a known failure mode, not as a tuned value.

### Autolevel / SnowMask — node 849, `$id` 55 — **UNCHANGED**

`RenderIntentOverride: "Mask"` left alone. No reason to touch it, and its
`SaveDefinition.Filename` is load-bearing for `--check-spec`.

### Terrain extent — **UNCHANGED, and this is a decision**

`Width` 5000.0, `Height` 2500.0, `Ratio` 0.5 are all untouched.

`Ratio` is exactly `Height / Width` = 0.5. Those three are **two lists
that must agree** (non-negotiable 24): I do not know whether Gaea
recomputes `Ratio` on load or reads it, so editing `Height` without
knowing which would risk a silent inconsistency in the one number the Z
scale is derived from. **Leaving `Height` at 2500 also keeps the Z-scale
derivation directly comparable to alpine's**, which is worth more than
the tuning it costs — the vertical scale is then carried entirely by
occupancy, which is a *measured* quantity after a build.

### Project identity — changed, and provably safe

| Path | From | To |
|---|---|---|
| `/Id` | `816bb8b4` | `c47a1f92` |
| `/Assets/$values[0]/Terrain/Id` | `9381bbdc-...-48a6539aa50b` | `5f2c8ae1-...-1ea77b30d942` |
| `/Metadata/Name` | `""` | `"Volcanic Ashlands"` |
| `/Metadata/Description` | `""` | provenance pointer to this file |

Both identifiers are **plain string values, format-preserved** (8 hex
chars; a well-formed GUID). Neither is a `$ref` target — `$ref` resolves
only against numeric `$id`, and `--check-refs` confirms 23/23 resolve
after the edit. Changed so that two regions are two projects; if Gaea's
build cache keys on `Terrain.Id`, a duplicate would collide, and
`rebuild_terrain.py --ignore-cache` is the existing mitigation either way.

**`DateLastSaved` / `DateCreated` / `DateLastBuilt` deliberately NOT
touched.** They still read 2026-08-09, inherited from the canonical file.
This file was not saved from Gaea, so writing a date claiming it was
would be a fabricated record. The staleness is visible and honest;
Gaea will rewrite them the first time it saves this project.

---

## 3. THE GATES — run from `C:\Users\Admin\UE5LandscapePipeline`

    python scripts/read_gaea_graph.py --project terrain/regions/volcanic.terrain --check-refs
      -> exit 0     "$id defined : 82   $ref used : 23   every $ref resolves to a real $id."

    python scripts/read_gaea_graph.py --project terrain/regions/volcanic.terrain --check-spec
      -> exit 0     "the graph predicts exactly the SPEC's Gaea-sourced files."
                    Erosion2_Deposits / Erosion2_Flow / Erosion2_Wear /
                    SnowMask_Out / Snow_Snow  all ok;
                    Snow_Out excluded by design.

Both passed on the first run; nothing needed fixing.

**A stronger check than either gate, because both gates would pass a file
with a rewired node.** Comparing the two documents leaf by leaf:

    key-path set identical            True   (0 added, 0 removed)
    $id sequence identical            True   (82 ids, in document order)
    $ref sequence identical           True   (23 refs, in document order)
    leaves changed                    18
    STRUCTURAL leaves changed          0
    SaveDefinition Filename/Format/IsEnabled/Node   all identical

That is what makes "parameter edits only" a measurement rather than an
intention.

---

## 4. Z SPAN AND z_scale_cm — **UNKNOWN. R-GAEA's METHOD RETURNS None HERE.**

> **CORRECTED 2026-08-15, after the first version of this section was
> withdrawn as fabricated.** It published a three-row table with a
> bolded "central" `z_scale_cm 244.14`, derived by *assuming* occupancy
> responds linearly to `Mountain.Height` and inventing a ±0.05 band.
> **There was no basis for either.** The original wording and the reason
> it was wrong are preserved in §4c, because a withdrawn number that
> reached a report is worth more as a record than as a deletion.

### 4a. The honest answer

R-GAEA §6's method, unchanged:

    occupancy   = (source_max - source_min) / 65535   [from Snow_Out.png,
                                                       BEFORE normalisation]
    span_m      = Terrain.Height * occupancy
    z_scale_cm  = span_m / 512 * 100

**`occupancy` is a property of the BUILD OUTPUT, not of the project
file.** It is measured by decoding the exported `Snow_Out.png` before the
normalising stretch destroys it. **No build has run from
`volcanic.terrain`, so occupancy is unmeasured, and therefore:**

    span_m      UNKNOWN
    z_scale_cm  UNKNOWN

This is not a gap in this document — it is R-GAEA behaving as specified.
`derive_z_scale` **returns `None`** rather than a default when the range
is unreadable, and *"Defaulting Z scale to UE's 100 when the project
range is unreadable → an unmeasured vertical scale that reads as a
decision → report UNKNOWN"* is a REJECTED entry in R-GAEA's own list.
**A predicted z_scale_cm is that REJECTED pattern with better
manners.**

### 4b. What CAN be stated without inventing an input

One thing, and it is an arithmetic identity rather than a prediction.
With `Terrain.Height` = 2500.0 (read from the file, unchanged):

    span_m     = 2500 * occupancy
    z_scale_cm = 2500 * occupancy / 512 * 100
               = occupancy * 488.28125

So `z_scale_cm` is **occupancy × 488.28**, exactly. Two consequences that
cost nothing:

- **488.28 is the occupancy = 1.0 case, and it is precisely R-GAEA §6's
  "2.7× too tall" naive answer** (`2500/512*100 = 488.3`). The trap and
  the identity are the same equation. Reading the project range as the
  span is the same error as assuming occupancy = 1.
- Alpine build 006 measured occupancy 0.37035172 → 0.37035172 × 488.28125
  = **180.8358**, which is the recorded `ue_z_scale` exactly. The
  identity is confirmed against a real build, so it is not my arithmetic
  being trusted.

**This says nothing about what occupancy volcanic will have.** It says
what to multiply by once a build measures it.

### 4c. The withdrawn prediction, and why it was withdrawn

The original section assumed `occupancy_volcanic = 0.37035 × (2.75 /
2.032038) = 0.5012` and built a 0.45–0.55 band around it, yielding
219.73 / **244.14** / 268.55.

**Three things were wrong with it, and I had written the second one down
myself before quoting the number anyway:**

1. **The linear-response premise is unsupported.** Nothing measured
   relates `Mountain.Height` to the occupancy of the *exported* height.
2. **It is implausible on the graph's own structure.** `Combine [Max]`
   with an unchanged `Ridge`, then `Erosion2`, then `Snow` all sit
   between the primitive and `Snow_Out`. `Max` in particular is
   non-linear by definition. The thicker mantle raises the max (mass on
   summits) *and* the min (fill in hollows), so its effect on the
   *range* is **unsigned** — I said so in the same paragraph as the
   number.
3. **Two decimals on an unsigned quantity is false precision in an
   import-dialog value** — the exact position this project's worst
   terrain trap occupies. A "USE NONE OF THESE" warning above a bolded
   central row does not make the row safe; a plausible number is more
   likely to be typed than a bare UNKNOWN.

The ±0.05 band was invented too. It was not derived from any sensitivity
analysis, and it conveyed a confidence interval that did not exist.

### 4d. `Mountain.Height` 2.75 — the amplitude *ambition*, sanity-checked

**Scoped narrowly, because in the withdrawn version this reference class
was attached to the fabricated span and made it read as corroborated.**
A real reference lending credibility to an invented number is worse than
no reference. It checks the *choice of `Height`*, and nothing downstream
of it.

An 8128 m region can physically host a young volcanic edifice of order
1 km relief: **Mount St Helens** stands ~1300 m above its surrounding
plateau on a ~10 km base, giving 13–17° flanks. **Mount Fuji is the
wrong reference** — ~2800 m over a ~35–40 km base — and a
Fuji-proportioned cone on an 8128 m map would be only ~600 m tall.

> **PROVENANCE OF THOSE FIGURES: my own general knowledge, NOT a source
> I opened.** Nothing in this repo, the `.terrain` or the engine carries
> them. Under the Tier-3 standard (*cite or it didn't happen*, and the
> reviewer opens the citation) they are **uncited and should be checked
> before anyone leans on them.** They are approximate by construction —
> "~1300 m above its plateau" is a round number, not a survey. The
> *shape* of the argument survives being off by 30%: it only needs
> "a real young volcanic edifice of roughly 1 km relief on a roughly
> 10 km base exists", which is a weak claim. **The 8128 m extent and the
> 925.9 m alpine span are the two figures here that ARE measured**, and
> they are the ones the argument actually turns on.

So *aiming* higher than alpine's 925.9 m is defensible for this region.
**That is an argument about ambition, not a prediction of the result**,
and it does not license a number.

**The caveat that matters more than the reference class:** `Mountain`
produces a fractal **range**. Whatever relief the build lands on will be
spread across several massifs — which is not the same thing as one
edifice of that height, and is the same limitation §6 is about.

---

## 5. TWO DOWNSTREAM COUPLINGS THIS FILE DOES NOT FIX

Both are outside my write permission and are flagged rather than changed.

1. **`rebuild_terrain.py:96` hardcodes
   `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"`**, and
   `verify_build.SPEC` requires that exact filename. Building
   `volcanic.terrain` through the existing pipeline will therefore write
   a volcanic heightmap under an **alpine** filename. That is a
   provenance collision, not a crash: `verify_build` will pass and the
   file will be mislabelled. Both are single hardcoded constants; making
   them region-derived is the fix, and it is a
   two-lists-that-must-agree (NN24) job because SPEC's key and
   `HEIGHT_OUTPUT` must move together.

2. **`--check-spec` passes only because I did not rename any
   `SaveDefinition.Filename`.** `Erosion2`, `Snow` and `SnowMask` are
   the base names the whole SPEC is keyed on. A future region that
   renames them for clarity will fail this gate — correctly, and the
   cause will be in the `.terrain`, which is exactly what
   `read_gaea_graph.py`'s docstring says the gate is for.

---

## 6. IS THIS LANDFORM ACHIEVABLE BY PARAMETER VARIATION? — **NO, NOT THE PART THAT MATTERS**

### 6a. What the parameters DO reach

| Brief | Reachable? | Lever |
|---|---|---|
| Low erosion maturity | **YES** | `Erosion2.Duration` 21.65 -> 4.20 |
| High primary relief | **YES** | `Mountain.Height` 2.032 -> 2.75 |
| Smooth flanks | **PARTIALLY** | only via `Snow.SettleThaw`; see 6c |
| Ash plains | **MAYBE** | `Snow` deposition; direction depends on the unresolved `Melt` semantics |
| **Cones** | **NO** | no lever exists |
| **Radial drainage** | **NO** | no lever exists |

### 6b. Why cones are not reachable — read from the file, not inferred

The graph has exactly two primitives:

- **`Mountain`** (node 877, `$id` 6) — `Scale`, `Height`, `Seed`.
- **`Ridge`** (node 650, `$id` 12) — `Seed`, and nothing else.

Both are fractal generators. **Neither is radially symmetric, and no
parameter on either makes a fractal field into a single radially
symmetric edifice** — a cone is a shape, not a frequency setting. They
meet at `Combine [Max]`, which has no ratio, so I cannot even suppress
the ridged crests that most contradict a cone.

**Radial drainage is downstream of that, not a separate problem.**
Drainage geometry is *emergent* — `Erosion2` routes flow over whatever
substrate it is given. A fractal ridge network produces dendritic and
trellis drainage on linear divides. Radial drainage is what you get when
the substrate is a radially symmetric edifice, so it cannot be obtained
without first obtaining the cone. And the two briefed goals actively
fight: turning `Erosion2.Duration` down to express *youth* also
suppresses the channel incision that would make any drainage pattern
legible at all.

### 6c. The brief's question, answered: **an unweathered fake**

> *"whether turning erosion DOWN produces convincing youth or just an
> unweathered fake"*

**For this graph it produces an unweathered fake, and the reason is
structural rather than a matter of finding the right value.**

Erosion here is not a weathering *overlay* on a landform — it is what
makes the fractal read as a landform at all. `Combine [Max]` of two
fractals is high-frequency noise with amplitude; `Erosion2` is the step
that organises it into divides, valleys, sediment and coherent slopes.
Cut its `Duration` by 80% and what is exposed is not youthful terrain,
it is *unresolved* terrain: high relief with no drainage organisation,
which reads as an unfinished heightmap rather than as a young one.

Real volcanic youth is **constructional**. The relief was *built*, by
radially organised deposition, and it looks young because its form is
depositional and its drainage has not yet organised on it. Youth is a
property of *how the relief was made*. **You cannot subtract your way to
a constructional landform** — removing the erosion from an erosional
landform leaves the erosional substrate, not a volcanic one.

The one thing that partially rescues it is the `Snow`-as-ash-mantle
reading: mantling *is* a constructional, depositional process, and
`SettleThaw` 0.78 over `Intensity` 0.72 is a genuine additive smoothing
pass that did not exist in alpine. That gets *smooth mantled flanks*.
It does not get *a cone under them*.

**AND THE VERDICT DOES NOT DEPEND ON THAT INTERPRETATION — which is what
makes it safe to act on.** The ash-mantle reading is the least verified
thing in this document (§2), so it is worth being explicit about which
direction its failure moves the conclusion. If the `Snow` node does not
behave as I read it, the mantle does not materialise, the only smoothing
lever in the graph disappears, and the landform is **further** from the
brief, not closer. **The interpretation can only make the verdict more
optimistic than the truth**, and the verdict is already NO. A build that
refutes the ash-mantle reading strengthens §6d's case for a structural
change rather than weakening it.

### 6d. THE STRUCTURAL CHANGE THIS REGION NEEDS — named, not invented

**`QuadSpinner.Gaea.Nodes.Volcano`.** The string `Volcano` is present in
`C:\Program Files\QuadSpinner\Gaea 2\Gaea.Nodes.dll`, in the primitive
node-name table immediately alongside `Ridge`, `Rugged`, `Uplift`,
`Voronoi`, `Sand`, `Slump` and `Stones` — i.e. among the same generator
family as the `Ridge` node this graph already uses. Also present in the
same table: **`Crater`**, **`Craterfield`** / `CraterfieldGenerator`,
`Cone`, `CraterStyle`, `RenderCrater`, and the fields `craterRadius`,
`craterProfile`, `craterDepthCoeff`.

**What I verified and what I did not:**

- **VERIFIED:** the literal strings `Volcano`, `Crater`, `Craterfield`,
  `Cone` exist in `Gaea.Nodes.dll`, in the node-name region of the
  metadata strings, adjacent to node names this project already uses.
- **NOT VERIFIED — inferred from the pattern in the canonical file:**
  the `$type` would be
  `"QuadSpinner.Gaea.Nodes.Volcano, Gaea.Nodes"`, by analogy with
  `"QuadSpinner.Gaea.Nodes.Ridge, Gaea.Nodes"` at line 56 of the
  canonical file.
- **COULD NOT LOOK:** `Volcano`'s parameter set. A string scan cannot
  tell me which properties belong to which type. Anyone adding this node
  must read the parameters out of Gaea's own UI or out of a `.terrain`
  Gaea itself saved with the node in it — **not out of this document.**

**The recommended shape**, for whoever does it in the Gaea GUI (which is
the right way to do it — it allocates the ids correctly and for free):

    Volcano       ->  Combine.In       (the edifice; radial by construction,
                                        and it brings its own crater)
    Mountain      ->  Combine.Input2   (demoted to low-amplitude basement /
                                        surrounding uplands)
    [Ridge removed, or kept at low influence]
      -> Erosion2 [Duration low, Downcutting high]   radial barrancas
                                                      form BECAUSE the
                                                      substrate is radial
      -> Snow     [as the ash mantle above]
      -> SnowMask [ash depth]

**And `Craterfield` may be the better node for "ashlands" specifically.**
A field of small monogenetic cones studding a flat ash plain is arguably
more characteristic of an *ashland* than one large stratocone — and it is
a landform that reads at 8128 m extent, which a single Fuji-class cone
does not (§4).

**Why I did not build it here.** Adding a node means new `$id` values,
new `Ports` entries each carrying `Parent: {"$ref": <node id>}`, and a
`Record` on the receiving port. `read_gaea_graph.py`'s docstring states
the rule directly: *"ADDING OR REMOVING A NODE IS NOT SAFE without
id-allocation logic ... getting it wrong produces a file that still
parses as JSON and is a different graph — or no graph."* Inventing ids to
hit a deliverable is precisely the failure mode the writer was withheld
to prevent.

---

## 7. WHAT I COULD NOT VERIFY — stated plainly (standing rule 10)

- **No build has run.** Every claim about the *output* of this file —
  whether the flanks are smooth, whether ash plains form, whether the
  reduced erosion looks young or unresolved — is unmeasured. The span
  and z_scale_cm are not even predictions; they are **UNKNOWN** (§4).
  The only measured things here are the file's contents, the two gate
  results and the structural diff.

- **THE FIRST VERSION OF §4 WAS FABRICATED, AND IT REACHED A REPORT.**
  It published `z_scale_cm 244.14` to two decimals from an invented
  linearity assumption and an invented ±0.05 band, and attached a Mount
  St Helens reference class that made the invented number read as
  physically corroborated. Withdrawn in §4c; the reference class is
  re-scoped in §4d to check only the *ambition* of `Mountain.Height`.
  **Cause, named:** the brief required "the expected Z span and the
  derived z_scale_cm" as a mandatory field, and a mandatory field
  asserts that the thing exists (non-negotiable 18). It does not exist
  without a build, and rather than say so I invented a mechanism to fill
  the field. **The correct brief wording is "the Z span and z_scale_cm
  where a build makes them derivable, or UNKNOWN with the reason" —
  explicitly nullable, with null meaning "no build, so R-GAEA returns
  None by design."**
- **Per-parameter landform semantics are NOT recoverable** from the
  `.terrain`, from this repo, or from a DLL string scan. Every row
  tagged *INFERRED* above is a hypothesis about what a name means, in
  the class the recon report withdrew for exactly this reason. They are
  directional guesses that a single build will settle.
- **`Combine.Mode`'s valid enum members could not be enumerated**, so
  the Mountain:Ridge combination rule was left alone (§2).
- **`Snow.RealScale`'s semantics were not verified**, so the bool was
  left alone.
- **`Snow.Melt`'s direction is genuinely unknown** and is the declared
  first thing to flip (§2).
- **Whether Gaea will open this file at all is untested.** The JSON is
  well-formed, ref-integral and structurally identical to a file Gaea
  wrote, which is strong — but "Gaea loads it" has not been observed,
  because launching Gaea was outside this task's permissions.
- **`Mountain.Height` 2.75 is not bounded by anything I read.** The only
  hard fact is that the canonical value 2.032038 is greater than 1, so
  the field is not 0–1 clamped. 2.75 is a +35% step chosen to be
  moderate, and the recon report's "+/-30% band" was explicitly withdrawn
  as invented — so it is not a constraint I am honouring, and there may
  be no constraint at all.

---

## 8. SCOPE I TOOK ON MYSELF — flagged so it is weighted correctly

Three things in this deliverable were not asked for. None is padding, but
a reader should know which parts answer the brief and which are mine.

- **Changing `/Id` and `/Assets/$values[0]/Terrain/Id`.** The brief said
  change only parameter values. These *are* values and not structure —
  neither is a `$ref` target, and `--check-refs` proves 23/23 still
  resolve — but "parameter" most naturally means a node knob, and these
  are project identifiers. Justified in §2 (two regions should be two
  projects; possible build-cache collision) and **trivially revertible**
  to `816bb8b4` / `9381bbdc-419f-4850-8201-48a6539aa50b` if that reading
  is not wanted.

- **The structural diff in §3.** The brief asked only for the two gates.
  Both gates would pass a file with a node rewired between existing
  ids, so neither actually tests the brief's real requirement —
  *"changing only PARAMETER VALUES"*. The key-path / `$id`-sequence /
  `$ref`-sequence comparison does test it. It is a throwaway script run
  in-session, **not** a committed tool, and it should not be cited as
  though the repo owns it.

- **§5, the `HEIGHT_OUTPUT` / SPEC coupling.** Not requested, and it
  concerns files I had no permission to change. Kept because it is a
  finding about *this file being unusable in the existing pipeline*,
  which is squarely about the deliverable rather than about adjacent
  work.
