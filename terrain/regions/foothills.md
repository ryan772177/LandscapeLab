# foothills.terrain — authoring note

**Region:** Foothills and river valley. The approach to the alpine region —
lower, gentler, with a drainage trunk a settlement can sit on. Region two.

**File:** `terrain/regions/foothills.terrain`
**sha256:** `ea03912badc373c90faab6607c48f9ca89dd3b7ee1e8d7f33219046d463d5021`
**bytes:** 16,205

**Derived from:** `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain`
**source sha256:** `459d5c2fc9d07b9cc19f4b08b2818d6c503119e95caf5c2cc57e6c7efc283346`
**source bytes:** 16,227

**Provenance of the source — checked, not assumed.** The file above is not
under `%APPDATA%\QuadSpinner\Gaea\2.0\Autosaves`, and its sha256 matches
**none of the 66** `.terrain` autosaves in that directory. That is consistent
with CLAUDE.md's record that Ryan saved it deliberately, and it is the file
`rebuild_terrain.py:90` names as `DEFAULT_PROJECT`. It is the canonical one.
*What this does NOT prove:* that Ryan intended this exact graph state — a
hash cannot carry intent (the same caveat CLAUDE.md's 2026-08-10 handoff
already records).

---

## 1. HOW THIS FILE WAS PRODUCED — and how minimal the change is

Copied verbatim, then **eight scalar leaves substituted by exact unique
string match**. No node added, removed or rewired. No `$id` created or
destroyed. No key added or deleted.

Proven by a full recursive JSON diff of the two documents:

    LEAF DIFFERENCES: 8      (all of them intended, listed in §3)
    $id list identical  : True   (n=82, same order)
    $ref list identical : True   (n=23, same order)
    node ids identical  : True

That is the envelope `read_gaea_graph.py:44-51` declares safe:
*"CHANGING A PARAMETER VALUE is safe … ADDING OR REMOVING A NODE IS NOT SAFE
without id-allocation logic."*

### Gate results — run from `C:\Users\Admin\UE5LandscapePipeline`

    python scripts/read_gaea_graph.py --project terrain/regions/foothills.terrain --check-refs
      -> EXIT 0     "$id defined : 82   $ref used : 23   every $ref resolves to a real $id."

    python scripts/read_gaea_graph.py --project terrain/regions/foothills.terrain --check-spec
      -> EXIT 0     "the graph predicts exactly the SPEC's Gaea-sourced files."

    (both flags in one run)                                    -> EXIT 0

The graph still exports the six files `verify_build.SPEC` requires:
`Erosion2_{Flow,Wear,Deposits}.png`, `Snow_Snow.png`, `SnowMask_Out.png`,
plus the excluded `Snow_Out.png` that `rebuild_terrain.normalize_height`
turns into the heightmap.

---

## 2. WHAT I DELIBERATELY DID NOT CHANGE, AND WHY

Each of these is a lever I considered and rejected. Rejecting them is most of
what makes this "the most conservative parameter departure".

| Left alone | Value | Why not touched |
|---|---|---|
| `Terrain.Width` | 5000.0 | Every one of the 66 autosaves on this machine carries Width 5000 / Height 2500 / Ratio 0.5 — these are the project defaults, never varied by any Gaea project here. `ErosionScale` is tuned against this width (CLAUDE.md). Moving it moves an unmeasured coupling. |
| `Terrain.Height` | 2500.0 | **It is the denominator of the Z scale.** `rebuild_terrain.derive_z_scale:147-163` computes `span_m = project_height_m * occupancy`, and `read_project_height_m:166-205` reads this exact field. Changing it silently re-scales every metre figure R-GAEA §6 derives. |
| `Terrain.Ratio` | 0.5 | Equals `Height/Width`. Coupled to two fields I am not touching; changing one of three would make them disagree. |
| `Mountain.Scale` | 0.74927175 | **I could not establish which direction it moves the landform.** The recon report withdrew its own explanation as name-inferred, no autosave on this machine carries a `Mountain` node to give an observed band, and `Gaea.Nodes.dll` yields no usable semantics. An uncited direction on a landform-defining knob is exactly the guess NN23 forbids. Peak *spacing* therefore stays alpine's; the foothill reading comes from amplitude and erosion instead. |
| `Combine.Mode` | `"Max"` | The only other value I can *read* anywhere is `"Subtract"` (14 Combine nodes across the autosave corpus carry only these two). I could not recover the enum's member list from `Gaea.Nodes.dll`. `"Average"`, `"Blend"`, `"Min"` etc. would be invented values — the brief forbids that, and so does NN23. |
| `Combine.PortCount` | 2 | Structural: it governs how many `In` ports exist, and the ports carry `$id`s. |
| `Erosion2.ErosionScale` | 1413.2517 | **Deliberate, and load-bearing — see §4.** Holding feature size constant while amplitude drops is what flattens the valley profile. |
| `Snow.Intensity/Melt/SettleThaw/Duration` | unchanged | Snow mass is kept high **on purpose**, as protection against the degenerate-export failure in §5. |
| `Autolevel.RenderIntentOverride` | `"Mask"` | No reason to touch it. |
| `Metadata` block | verbatim | Left exactly as inherited. **It is NOT a record of this file's authorship** — `DateLastSaved 2026-08-09`, `Edition "Community"` and the version stamps all describe the alpine project as Gaea last wrote it. Editing them would fabricate a Gaea save that never happened; leaving them and saying so is the honest option. |
| `Terrain.Id` GUID | `9381bbdc-…` | Left, but **see the build hazard in §7** — this file shares the alpine project's GUID and every node `Id`. |

---

## 3. WHAT CHANGED — every leaf, with the mechanism

Line numbers are identical in both files (the edit preserved structure).

| Node (`Id`) | Parameter | Alpine | Foothills | Line |
|---|---|---|---|---|
| Mountain (877) | `Height` | 2.032038 | **1.0** | 17 |
| Mountain (877) | `Seed` | 22109 | **30411** | 18 |
| Ridge (650) | `Seed` | 38804 | **51862** | 57 |
| Erosion2 (654) | `Duration` | 21.648195 | **28.0** | 171 |
| Erosion2 (654) | `Downcutting` | 0.4531411 | **0.25** | 172 |
| Erosion2 (654) | `Seed` | 15025 | **27703** | 174 |
| Snow (599) | `SnowLine` | 0.056395777 | **0.35** | 273 |
| Snow (599) | `Seed` | 59434 | **44190** | 275 |

### 3.1 `Mountain.Height` 2.032038 → 1.0 — the relief lever

This is the only parameter in the graph that plausibly sets the primitive's
vertical amplitude, and amplitude is what the brief asks to reduce.

**Why 1.0 specifically, and not a tuned number.** I have no observed band for
this field — no other project on this machine contains a `Mountain` node — so
any value I pick is a choice, not a measurement. **1.0 is the least arbitrary
point available:** it is the natural unit value of a normalised amplitude, so
it is the value least likely to be pathological, and it is not a number I
reverse-engineered from a relief target. It is 49.2% of alpine's 2.032038.

**The resulting span is UNMEASURED and no value is offered for it.** See §6.

**The named risk, stated before the build rather than after it.** The graph is
`Max(Mountain, Ridge)` (`Combine.Mode "Max"`, wiring 877→750.In and
650→750.Input2). `Ridge` exposes **only a `Seed`** — it has no amplitude
parameter at all. So if lowering Mountain takes it *below* Ridge's amplitude,
`Max` hands the surface to Ridge, and Ridge is a ridged fractal: the region
would read as a low, sharp arête network rather than as foothills.
**I cannot rule this out without a build.** 1.0 was chosen partly to stay at
or above unit amplitude for exactly this reason. If the first build comes back
spiky rather than rolling, the diagnosis is Ridge dominance and the escalation
is in §8 — *not* another cut to `Mountain.Height`, which would make it worse.

### 3.2 `Erosion2.Downcutting` 0.4531411 → 0.25 — broad valley floor, not a V-notch

`Downcutting` is the vertical-incision term. **The direction of its effect is
an inference from the parameter name, flagged as such** — but the value is
not invented: **0.25 sits inside the band Gaea's own projects use**, 0.191123
to 0.42 across 8 `Erosion2` nodes in the autosave corpus. Alpine's 0.4531411
sits *above* that band, which is consistent with it being an alpine setting.

Intent: a foothill river valley is defined by lateral width and a flat floor,
not by a deep slot. Less vertical incision at the same erosion scale gives a
wider, shallower valley cross-section.

### 3.3 `Erosion2.Duration` 21.648195 → 28.0 — drainage maturity

**This is justified on drainage development, not on relief**, because
duration's effect on relief is genuinely two-directional: longer erosion cuts
deeper channels *and* deposits more sediment. What it reliably does more of is
run the network — more discharge, more tributary capture, more deposition —
which is what makes the trunk channel legible as a river valley rather than a
scatter of gullies.

28.0 is **inside the observed band** 23.16074–32.0 (36 `Erosion2` nodes in the
corpus). Alpine's 21.648195 is *below* it.

Expected cost: a longer build than alpine's. **Not measured** — the only
timing evidence in the repo is CLAUDE.md's ~100 s for a whole 8192 rebuild,
which does not decompose by node.

### 3.4 `Snow.SnowLine` 0.056395777 → 0.35 — the region sits below the permanent snowline

**`SnowLine` is INVERTED — a LOWER value produces MORE snow.** That is
R-GAEA §2, ground truth, and it is why this number goes *up* to get *less*
snow. It is corroborated by the corpus: the one other `Snow` node on this
machine runs `SnowLine` 0.68/0.78 in a non-alpine project.

**Why snow has to be reduced explicitly rather than falling out of the lower
terrain.** `Snow.RealScale` is **`false`** (foothills.terrain:274, unchanged
from the canonical). The snow sim is therefore not working in real-world
metres — it is working relative to the terrain's own range, which the export
then normalises to full 16-bit anyway. **Lowering the mountain does not lower
the snowline.** Without this edit the foothills would carry alpine's snow
distribution over a third of the relief, which is the wrong region.

**Measured baseline, so the target is not blind.** Build 006
(`AlpineLab_v1\006\UE5_Ready`) at `SnowLine 0.056`:

    Snow_Snow.png       12.60% of pixels non-zero,  64,766 unique values
    SnowMask_Out.png    12.36% non-zero,            58,708 unique values
    lowest snowy pixel sits at height percentile 9.17
    median height under snow 0.3424  vs  median height overall 0.2663

Note the 9.17 — snow is **not** a clean altitude cut even at 0.056, so the
response of coverage to `SnowLine` is not a simple threshold and I am not
going to pretend to predict it. 0.35 is a large move toward less snow while
staying well short of the 0.68–0.78 the corpus shows, i.e. it is not at the
extreme end of anything anyone here has built. **It is the parameter most
likely to need one correction after the first build.** §5 says which way.

### 3.5 The four seeds

Alpine 22109 / 38804 / 15025 / 59434 → **30411 / 51862 / 27703 / 44190**.

These are arbitrary and recorded here so the region is reproducible. **They
are also the single most important change in this file:** without them the
foothills would be alpine's exact landform at lower amplitude — a shrunken
copy of region one, not a different place. All four are integers, inside the
range Gaea's own projects use (8464–60797), and carry zero structural risk.

---

## 4. WHY `ErosionScale` STAYS AT 1413.2517 — the one non-obvious choice

`ErosionScale 1413.2517` against `Width 5000.0` is **0.28265 of the map**.
CLAUDE.md records that it was tuned to that authored width, and that importing
at 8128 m stretches erosion features **8128/5000 = 1.6256x**. At that import
size the erosion scale lands at ~2,297 m of UE ground.

For alpine that stretch is a caveat. **For foothills it is help.** Broad
valleys and a wide floodplain are precisely what this region wants, so the
1.63x stretch is working in the right direction and does not need correcting.

More importantly: **holding feature size constant while cutting amplitude in
half halves every gradient.** A valley of the same width over half the relief
is, by construction, twice as gentle — which is the whole brief. Changing
`ErosionScale` as well would confound that, and would also push the value
outside anything observed (the only two `ErosionScale` values in the corpus
are 122.996475 and 726.0276, both *below* alpine's).

One change fewer, and the mechanism is better for it.

---

## 5. THE FAILURE MODE THIS FILE IS MOST LIKELY TO HIT

**A foothills region wants little snow. The package gate requires snow.**

Two of the six files `verify_build.SPEC` demands are snow-derived —
`Snow_Snow.png` and `SnowMask_Out.png` (the Autolevel of `Snow.Depth`). And
`verify_build.py:59` sets `MIN_UNIQUE = 16`, with `:294-295` reporting
**DEGENERATE** and exiting **4** for any channel below it. R-GAEA §2 records
that Gaea 2.3 exports the Snow channel as a near-1-bit PNG *when the sim
output is uniform* — and "no snow anywhere" is uniform.

**So the graph structurally requires the region to keep some snow.** That is
why:

- `SnowLine` went to 0.35 and not to the 0.68–0.78 the corpus shows;
- **`Snow.Intensity` was deliberately left at 0.40226594** rather than dropped
  to the 0.22 the corpus offers. Two snow reductions compound; one does not.
  Keeping snow *mass* high means whatever snow does form is graded rather than
  near-binary, which is what keeps the unique-value count off the floor.

This is the "prefer an input that cannot express the catastrophic value"
posture (NN3) applied where it can be: one lever, not two.

**IF THE BUILD COMES BACK `DEGENERATE (n unique values)` / EXIT 4 ON
`Snow_Snow.png` OR `SnowMask_Out.png`:** the fix is to **lower `SnowLine`
toward 0.15** and rebuild. Do not change `Intensity`, `Melt`, `SettleThaw` or
`Duration` to chase it — one variable at a time, and `SnowLine` is the one
that was moved.

A thin snow cap on the highest ground is also the *correct* reading for this
region: foothills below the permanent snowline still get seasonal snow on the
tops, and the alpine region next door is where the permanent snow lives.

---

## 6. Z SPAN AND UE `z_scale_cm` — **UNKNOWN UNTIL A BUILD IS NORMALISED**

R-GAEA §6's method, `rebuild_terrain.derive_z_scale:147-163`:

    occupancy = (vmax - vmin) / 65535          measured from the build's Snow_Out.png
    span_m    = Terrain.Height * occupancy     Terrain.Height = 2500.0 (unchanged)
    z_scale   = span_m / 512.0 * 100.0

**Alpine, measured** (`AlpineLab_v1\006\height_normalization.json`):

    source 495 .. 24766      occupancy 0.37035172      span 925.879 m      z 180.8358

**Foothills:**

    occupancy  UNKNOWN — no build exists
    span_m     UNKNOWN
    z_scale_cm UNKNOWN

**`UNKNOWN` here means exactly what `derive_z_scale` means by `None`:** the
measurement the method requires has not been taken, and no number may be
substituted for it. Not "roughly 89". Not "assume linear for now". **UNKNOWN.**

### Why this field is UNKNOWN and not a prediction — I got this wrong first

The task asked me to *"include the expected Z span and the derived UE
z_scale_cm using R-GAEA's method"*. **R-GAEA's method takes occupancy as an
input measured from a built `Snow_Out.png`** (`derive_z_scale:147-163`,
`normalize_height:465`). With no build there is no occupancy, so the method
has no input and the field has no value.

The first version of this note answered anyway. It asserted
`occupancy_new = occupancy_alpine x (Height_new / Height_old)` and printed
**455.64 m** and **z_scale_cm 88.99**. **That linearity has no basis** — not a
weak basis, none. `Mountain.Height` is one input to a `Max` combine (which
floors the result against an un-parameterised `Ridge`, §3.1) feeding a
hydraulic sim that redistributes mass afterwards. There is no reason the ratio
should survive that chain, and I did not have one.

It was labelled a prediction in prose, which is not sufficient: **the hedge sat
in a paragraph and the numbers sat in a table, and numbers get quoted.**

**And the pattern is one R-GAEA explicitly REJECTS.** Its own entry reads:
*"Defaulting Z scale to UE's 100 when the project range is unreadable → an
unmeasured vertical scale that reads as a decision → **report UNKNOWN** →
`derive_z_scale` returns `None`."* The script refuses to invent a Z from an
unreadable range; I invented one from an unbuilt range and gave it two
decimal places. Same defect, one step earlier in the chain.

### What IS known, and it is a direction, not a magnitude

`Mountain.Height` went **2.032038 → 1.0**, a 50.8% cut to the only amplitude
parameter in the graph. **The direction is not in doubt: this region will have
less relief than alpine.** How much less is a measurement nobody has taken.

The `Max`-against-`Ridge` floor (§3.1) means the *plausible* outcomes span from
"roughly half of alpine's 925.88 m" down to "barely reduced, because Ridge set
the ceiling and Mountain never touched it". **That range is wide enough that
quoting any single value from it would be misleading**, which is the whole
reason this field is UNKNOWN rather than bracketed.

### How to fill it — one command, and then it is measured

    python scripts/rebuild_terrain.py --project <this file> --root <foothills root> ...

writes `height_normalization.json` beside the build, carrying `occupancy`,
`span_m` and `ue_z_scale` derived by the single definition
(`derive_z_scale:147-163`). **Take the number from that file and from nowhere
else.** Then replace this section with the measured values and delete this
explanation.

**Do not type a Z scale into an import dialog before that file exists.** The
naive answer (`2500/512*100 = 488.3`) is 2.7x too tall *and looks plausible* —
that is the trap R-GAEA §6 exists for, and an unmeasured occupancy produces
exactly the same shape of confidently-wrong number.

**One physical bound that IS available (NN11), and it bounds nothing tightly:**
alpine's 925.88 m over 8,128 m is a 0.114 average grade; foothill country
generally runs a few hundred metres of local relief over that distance. A
result anywhere from ~200 m to ~900 m would be physically unremarkable. A
result *above* alpine's 925.88 m would mean `Mountain.Height` does not do what
this file assumes and the whole §3.1 reading is wrong — **that is the one
outcome this check can actually refuse**, so it is worth running it as a check
rather than as a formality.

---

## 7. HOW TO BUILD THIS — three pipeline hazards a second region exposes

None of these are defects in *this* file. All three are the pipeline meeting
its first non-alpine input, and all three are `NN24` / WORLD_VISION §6
("nothing in the pipeline may hardcode alpine-isms") landing for real.

1. **`--root` must be given, or a foothills build lands inside the alpine
   package tree.** `rebuild_terrain.py:89` sets
   `DEFAULT_ROOT = C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1`, and
   `next_build_dir` takes the next free `NNN` under it. A bare run would drop
   foothills into `AlpineLab_v1\007` and it would look like an alpine build.

2. **`--ignore-cache` on the first build.** This file shares the alpine
   project's `Terrain.Id` GUID (`9381bbdc-419f-4850-8201-48a6539aa50b`) and
   every node `Id` (877/650/750/654/599/849), because preserving them is what
   keeps `--check-refs` green. `rebuild_terrain.py:321-322` passes
   `--ignorecache` when asked. Whether Gaea's cache keys on those ids is
   **unverified** — I could not read the cache format. Paying one cold build
   is cheaper than debugging a stale one.

3. **The normalised heightmap will be named for region one.**
   `rebuild_terrain.py:96` hardcodes
   `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"`, and
   `verify_build.SPEC` declares that exact key, and `preflight` **refuses**
   (`:274-283`) if the two ever disagree — so the two are correctly coupled,
   and both are correctly *alpine*. A foothills build through this pipeline
   emits `AlpineLab_v1_Height_normalized.png` describing foothills.
   **That is a naming defect waiting to become a provenance defect** the first
   time two regions' packages sit in the same tree. Fixing it means making the
   region name a single declaration both files read — not editing two strings.
   **Not fixed here:** it is outside this task's write permission, and it is a
   change to a proven gate that deserves its own single-variable commit.

Suggested first invocation, dry-run first (bare = dry run, R-GAEA §9):

    python scripts/rebuild_terrain.py \
      --project C:\Users\Admin\UE5LandscapePipeline\terrain\regions\foothills.terrain \
      --root <a foothills package root, NOT AlpineLab_v1> \
      --resolution 8192 --ignore-cache

then `resize_gaea_build.py --size 8129 --archive-excluded` to match the
alpine8k path, then `verify_build.py` at both sizes.

**Nothing above has been executed.** No Gaea process was started, no build
exists, no editor was contacted. Every number in §6 is arithmetic.

---

## 8. HONEST VERDICT ON ACHIEVABILITY

**Partly achievable by parameter variation, and one half of the brief is
NOT.** Splitting it, because "foothills and river valley" is two requests:

### ACHIEVABLE — and this file does it

- **Lower relief.** `Mountain.Height` is the amplitude lever and it works
  through the whole chain into `occupancy` and the derived Z scale. The
  *magnitude* is a prediction (§6); the *direction* is not in doubt.
- **Gentler slopes.** Falls out of amplitude down + `ErosionScale` held (§4).
  Gradient is relief over run, and only relief moved.
- **A drainage network with a legible trunk channel.** `Erosion2` is a
  hydraulic sim and already exports `Flow` — the alpine flow map is a working
  drainage field this project has consumed. More `Duration`, less
  `Downcutting`: a mature, wide, dendritic network. **That is a river valley
  in the heightmap sense.**
- **A snow-light region.** §3.4.

### NOT ACHIEVABLE — three things, and I am not going to pretend otherwise

1. **BROAD TERRACES ARE ALMOST CERTAINLY NOT REACHABLE FROM THESE SIX NODES —
   and here is the actual basis, which is not "no parameter is named for it".**
   A bare negative inferred from parameter names would be the same
   name-guessing this note refuses elsewhere (§2, `Mountain.Scale`). The
   argument that does carry weight is this: **Gaea ships `Stratify` as a
   separate node** (proven in §8's recommendation, two sources). A shipped
   node that produced a behaviour `Erosion2` already had would be redundant,
   so stratification is evidence-backed as *outside* `Erosion2`'s scope rather
   than merely unnamed within it.

   **The residual, stated because it is not zero:** our `Erosion2` omits two
   properties the corpus shows on that node type —
   `ShapeDetailScale` (0.05) and `CoarseSedimentsDischargeAmount` (0.5),
   both at their defaults here. **I did not establish what either does.**
   Neither is named for stratification, but that is a name-inference and I am
   not resting the claim on it. If someone wants to close this properly, those
   two are the cheapest thing to test — they are parameter additions of keys
   proven to exist on this node type, so they cost no `$id` and cannot affect
   `--check-refs`.

   **As it stands: the brief asked for broad terraces and this file does not
   deliver them.** That much is not in doubt regardless of how the residual
   resolves, because nothing in the shipped parameter set was set to produce
   them.

2. **THE VALLEY LANDS WHERE THE SEED PUTS IT, NOT WHERE THE TOWN GOES.**
   WORLD_VISION.md:278 says the foothill basins are *"the region's settlement
   and POI zones"* and :279 that the corridor is *"the primary traversal
   route"* — i.e. the valley's **position** is a design decision. From
   parameters it is a function of `Erosion2.Seed` and nothing else. The only
   route to an authored trunk valley inside this graph is the `Combine` node's
   **`Mask` input port, which exists and is UNWIRED** (`$id` 26, `Name "Mask"`,
   `Type "In"`, no `Record` — foothills.terrain:152-160). Wiring it needs a
   node to wire *into* it.

3. **NO FLAT BUILDABLE GROUND.** A town needs a level pad. Nothing here
   flattens.

### THE STRUCTURAL CHANGE I RECOMMEND — one node, named, with evidence

**Insert `QuadSpinner.Gaea.Nodes.Stratify, Gaea.Nodes` between `Combine` (750)
and `Erosion2` (654).**

**Why this node is real and not a guess** — two independent sources:
- an autosave on this machine carries one, with its exact `$type` string and
  its full parameter set:
  `%APPDATA%\QuadSpinner\Gaea\2.0\Autosaves\Migration_Bisect_A_LakeNode_2026-08-13_22-13-45.terrain`
  → `{"Spacing": 0.24, "Intensity": 0.38, "Shape": 0.5, "Seed": 8460, "TiltAmount": 0.12}`
- `Stratify` appears as a null-delimited metadata string in
  `C:\Program Files\QuadSpinner\Gaea 2\Gaea.Nodes.dll` at offset 712708,
  alongside `Mountain` (689946), `Combine` (677307) and `Erosion2` (645282).

**Why before `Erosion2` and not after** — so erosion runs *on* the stratified
surface and weathers the risers into real terrace shoulders, rather than
stamping pristine steps across a finished drainage network. **This ordering is
an inference from how the two processes relate physically, not something I
read.** Flagged.

**What `Spacing`, `Shape`, `TiltAmount` and `Intensity` actually do is NOT
established** — the same withdrawal the recon report made for `Mountain.Scale`
applies here, and I will not fill that column from the names.

**What inserting it costs, precisely.** A new node needs: one `Nodes` key with
a new Gaea `Id`; new `$id`s for the node, its `Position`, its `Ports`
collection, each `Port`, each `Record`, and its `Modifiers`; `$ref`s from each
port back to the node; and the existing `750 → 654` `Record` split into
`750 → NEW` and `NEW → 654`. **`$id` values are assigned in document order and
`$ref` points at them by number** (`read_gaea_graph.py:47-51`), so this is the
id-allocation problem the project deliberately has not built a writer for.
`--check-refs` is the acceptance test that work must pass, and it exists
already — which is the good news.

**I did not do it, and that is the right call under this brief.** The brief
says: *"If a region you want genuinely needs a new node, SAY SO and describe
the node — do not invent ids."*

### A SMALLER ESCALATION, if the first build reads as Ridge-dominated (§3.1)

`Combine` in this graph carries only `PortCount` and `Mode`. **28 `Combine`
nodes in the autosave corpus additionally carry `Ratio`**, observed at
0.35 / 0.48 / 0.55 / 1.0. Adding a `Ratio` key is a *parameter* addition, not
a structural one — no `$id` is created and `--check-refs` cannot be affected —
so it is the smallest available lever for rebalancing Mountain against Ridge.
**It is still an addition of an absent key, and whether `Ratio` is even read
under `Mode "Max"` is unverified.** Named here as the next thing to try, not
applied.

### WHAT THIS FILE HONESTLY IS

**A correct, gate-passing, minimal-departure foothills *base*: lower, gentler,
seeded as its own place, with a mature drainage network and light snow.**
It is not yet the terraced, authored river valley the region description asks
for, and one `Stratify` node is the difference.

Given that this is the cheapest second region and the most likely to be built
first, **build this file as-is, measure the occupancy, and decide about
`Stratify` against a render rather than against this note.** The occupancy
measurement alone retires the largest unknown in §6, and it costs one build.
