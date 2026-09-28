# Lessons — what worked, what didn't

Written 2026-07-31 from the alpine milestone: repo scaffold through verified
heightmap import, one destructive editor mutation, and a failed capture.

This is not a summary of what was built. It is a record of **which practices
caught real defects** and **which mistakes recurred**, so the next project can
skip the tuition. Every item below is traceable to a specific incident in
`docs/audit-log.md` or `docs/decisions.md`.

The headline: the pipeline shipped roughly a dozen scripts. **Every serious
defect in them was caught by an independent review before execution, and
almost every one came from assuming an API's semantics instead of reading the
engine source.** Those two facts are the whole guide.

---

## 1. What worked — repeat these

### 1.1 A mandatory audit gate with an independent reviewer
Non-negotiable, and it paid for itself many times over. Real defects it caught
*before first execution*:

| Defect | Would have caused |
|---|---|
| `set_base_material_usage(MATUSAGE_Landscape)` | `AttributeError` on **every** run — the enum was removed in UE 5.8 — one line after the material graph had been wiped |
| Residency gate compared against a number measured on a *partially loaded* level | The gate would have passed **exactly when loading failed** — an inverted safety check |
| `set_actor_location` on a World Partition landscape | Parent moved, 64 components left behind, torn state **saved to disk** |
| Verifier read only the parent actor's location | Would have **PASSed** that torn state |
| Band masks feathered inward | Diagnostic tool would have painted a fake coverage gap at every layer boundary |
| `biome_id` interpolated into a filename unvalidated | Recipe could steer a file write outside its sandbox |
| Scale-mismatch "refusal" that moved and saved *first*, then printed REFUSE | A persisted mutation reported as a no-op |
| Derived-resolution check fed the expected value into its own verification | Verified nothing, in the tripwire |
| Un-doubled braces in a `.format()` template | `KeyError` at import — the module could never have run |

**The pattern:** the reviewer must be independent of the author, must have
source access, and its verdict must gate execution — not merely inform it.
A review that only advises gets rationalised away under time pressure.

**Corollary that mattered:** when the reviewer gained the ability to *fix* its
own findings, the author must still verify those fixes. It caught things I
missed; I caught nothing wrong in its fixes — but checking cost minutes and the
alternative was a reviewer marking its own homework.

### 1.2 Verify semantics at an engine source line, not just arithmetic
The single highest-value habit, learned the hard way (see 2.1).

The rule that emerged: **every value handed to an editor UI field or API
parameter needs its *meaning* confirmed at a source line — not just its
magnitude derived correctly.** Getting the number right from a wrong premise
produces confident, wrong output.

### 1.3 Fail-closed gates, layered and independent
Every gate refused rather than guessed, and each was independent of the others:

- **Identity** — refuse unless exactly one editor matches the expected project.
- **Residency** — refuse unless loaded counts equal on-disk counts (World
  Partition only exposes *loaded* actors, so a census taken blind is a lie).
- **Exactly-one** — refuse unless precisely one target exists.
- **Positive attribution** — act only on things provably attributed to the
  target; "unknown" is never treated as "yes".
- **Hard assertion** — a final check that *raises* rather than filters. A
  filter silently shrinks a kill list; an assertion stops the run.

**Test each gate can't be satisfied by the failure it guards against.** The
residency gate originally passed when loading failed — the inverse of its job.

### 1.4 Dry-run mode on anything destructive
`--dry-run` printed the full kill list with per-item evidence before deleting
anything. It also surfaced the wrong invariant (68 vs 80) harmlessly. Any
irreversible operation should be runnable in a mode that proves what it *would*
do.

### 1.5 Identify by property signature, never by name
Two landscapes had proxies with **identical labels** — names were generated
from grid coordinates and collided. Deletion by name-matching would have
destroyed the wrong terrain.

The deletion script required **three independent signature conditions** and
aborted on zero or multiple matches. **When an operation is irreversible,
identify by intrinsic properties and require the match to be unique.**

### 1.6 Commit before every irreversible operation
Git was the only undo. A pre-mutation commit made the deletion recoverable and
let an accepted-but-unwanted change be restored later. Cheap, and the one time
it mattered it mattered completely.

### 1.7 Write rulings to disk, not just into the conversation
Decisions recorded in `docs/decisions.md` survived context loss; decisions that
lived only in messages did not. Several times a ruling had to be re-derived
because it existed only in prose.

**If a decision will constrain future work, it belongs in a file** — with the
reasoning, not just the outcome, so it isn't re-litigated.

### 1.8 Deterministic synthetic fixtures unblock real work
A generated heightmap (fixed seed, reproducible) unblocked the whole milestone
while the real source was unavailable — same path, same format, same contract,
so the real export drops in with no downstream change.

**Bonus:** because it was synthetic and regenerable, an accidental edit to it
was a shrug instead of a crisis.

### 1.9 One derivation, shared by producer and checker
The spec printer and the verifier imported the *same* `derive_spec` function,
so what was printed and what was verified could not drift. **If two components
must agree, make them share the code that decides — not a convention.**

### 1.10 Report derived values as derived
When the engine refused to expose three geometry properties, they were computed
from measured spacing and printed under a loud `DERIVED` banner. The value was
trustworthy (a uniqueness proof backed it), but it was never presented as
something the engine had confirmed.

---

## 2. What didn't work — avoid these

### 2.1 Assuming API semantics instead of reading source
**This caused more defects than everything else combined.** The incidents:

- `sections_per_component` documented as "1 or 4"; the engine's legal values are
  `{1, 2}`. The error survived because `63×4×8+1` and `63×2×16+1` both equal
  2017 — **an arithmetic coincidence hid a semantic error.**
- The New Landscape dialog's `Location` is the terrain's **centre**, not the
  actor origin. The actor landed 403200 cm from where intended.
- `fov_deg` never reached the engine — the viewport-camera call copies only
  location and rotation. **Captures were framed at the wrong FOV for days**, and
  analysis of those images rested on a false premise.
- `MATUSAGE_Landscape` was removed from the enum in 5.8.
- `get_outermost()` returns the *map* package; `get_package()` returns the
  actor's own package. Under one-file-per-actor these differ, and the wrong one
  guarantees a false "no match" — on a lookup that gated a deletion.
- `EditorLevelLibrary.get_editor_world` deprecated since 5.0, used in a gate
  intended to front every subsequent script.

**Rule: if a name is being trusted to mean something, find the line that
defines it.** Reading source costs minutes; a wrong assumption costs a
debugging session and sometimes data.

### 2.2 Writing code against a spec that was never traced to source
The schema's own worked example was unbuildable. Everything downstream
inherited the error — two scripts hard-coded the illegal value, and a spec
printer would have told a human to type a number the dialog cannot accept.

**Validate the specification itself before building on it**, especially where
it describes an external system.

### 2.3 Implementing against semantics the spec doesn't have
Material layers were authored as overlapping ranges assuming weighted blending.
The schema plainly specified first-match-wins. Result: the intended 60% snow
line was really 54.7%, and one bound was dead range.

Worse, the fix was initially proposed as *changing the schema* — forking a
specification to justify one artefact's encoding error. **When output disagrees
with spec, first assume the output is wrong.**

### 2.4 Resolving design-level findings unilaterally
A review returned a BLOCK requiring a design decision. It was rewritten,
re-reviewed, and committed before the owner ever saw the finding. The code was
fine; the process was inverted — the implementer chose the design and review
followed.

This produced a standing rule: **design-level findings must be surfaced and
signed off *before* implementation, commit, or re-review. A rewrite does not
retire a design finding — sign-off does.**

### 2.5 Claiming something was recorded when it wasn't
Four rulings were reported as "recorded in decisions.md" when they existed only
in a schema file and commit messages. Caught by the reviewer, which correctly
refused to write the decision record on the author's behalf.

**Before writing "as recorded in X", open X.**

### 2.6 Measuring an invariant on partial state
A proxy count of 68 was measured while most actors were unloaded; the true
total was 80. That number was then baked into a safety gate — which, combined
with a survivable load error, would have passed *only* when loading failed.

**An invariant measured on incomplete state is not an invariant.** Derive it
from an authoritative source (on-disk descriptors), or verify completeness
before trusting the measurement.

### 2.7 Diagnostics that can lie
A debug visualiser is only useful if its failure modes are distinguishable from
the failures it reports. Inward-feathered masks would have shown fake gaps at
layer boundaries — read as a recipe bug that didn't exist.

Likewise, "NO MATCH" originally conflated *"the accessor doesn't work"* with
*"genuinely absent"*. **A diagnostic must distinguish "I looked and it's not
there" from "I couldn't look".**

### 2.8 Truncating your own output on an irreversible run
A destructive script's output was piped through a line limit, discarding the
result. State had to be reconstructed from git and the filesystem.

**Never truncate the output of an operation you cannot repeat.**

### 2.9 Recurring input-validation blind spots
The same class of bug appeared **three separate times** in different files:

- `NaN` / `Infinity` pass numeric range checks (`nan <= 0` is `False`), and
  JSON parsers accept those literals by default.
- A value interpolated into a filename or path without charset validation is a
  traversal vector.

**When a defect class is found once, grep for it everywhere immediately.** It
was fixed three times because it was fixed locally each time.

### 2.10 Config file ordering and glob subtleties
- In `.gitattributes`, **later rules override earlier ones**. Placing a general
  rule after specific ones silently re-enabled text conversion on 162 binaries.
- In `.gitignore`, `*` **does not cross `/`** — `captures/*.png` doesn't match
  `captures/alpine/x.png`. Consequence: the first output file went untracked,
  making the tree permanently "dirty" and destroying a reproducibility marker.

**Verify config files behave as intended (`git check-attr`, `git check-ignore`)
rather than assuming they read top-down like code.**

### 2.11 Circular verification
A check computed its "actual" value using the expected value it was verifying.
It could not fail. **A check that consumes the answer verifies nothing** — trace
each assertion back to an independent measurement.

### 2.12 Referring to context the reader may not have
Reports repeatedly cited option labels, finding IDs, and verdicts the reader
had never received, because messages arrived truncated. This wasted several
exchanges.

**Carry the content, not the label** — or a path where the full text lives.
`(i)`, `F2`, `D1` are indexes, not information.

---

## 3. Domain gotchas (Unreal Engine, World Partition, OFPA)

Cheap to know, expensive to discover:

- **World Partition exposes only *loaded* actors.** Any census, count, or
  geometry derivation is silently partial unless residency is established
  first. A landscape reported "resolution 505" when it was 1009 — that was
  residency, not geometry.
- **One File Per Actor: each actor is its own package**, named by hash. Dirty
  package lists give you hashes with no actor identity; map package → actor via
  the actor's own package accessor.
- **Actor labels are not unique.** Grid-generated names collide across
  different parents.
- **`ALandscape` derives from `ALandscapeProxy`**, so a "proxy count" in the
  details panel may include the parent itself. Off-by-one confusion followed.
- **Deprecation fixups fire on load**, dirtying packages that were never
  touched. A batch of warnings after loading previously-unloaded actors is
  usually pre-existing data, not damage just caused.
- **Bare `UPROPERTY()` fields are not readable from Python.** Only
  editor/Blueprint-exposed properties are. Plan a derivation path.
- **Landscape height datum:** heightmap value 32768 (mid-grey), not 0, maps to
  the actor's Z. Terrain at actor Z 0 spans ±half the height range, not 0..range.
- **Saving a level saves *every* dirty external package**, not just the
  intended one. An unrelated in-progress edit gets committed as a side effect.
- **Editors hold packages in memory.** Restoring a file on disk under a live
  editor desyncs them, and the next save silently overwrites the restore. Close
  the level first.

---

## 4. Process rules worth carrying forward

1. **Audit before first execution**, with an independent reviewer that has
   source access and whose verdict gates execution.
2. **Surface design-level findings for sign-off before implementing.** A
   rewrite doesn't retire them.
3. **Commit before and after anything irreversible.**
4. **Dry-run mode on every destructive operation.**
5. **Fail closed everywhere.** Test that each gate can't be satisfied by the
   failure it guards.
6. **Stop after two consecutive failures** against a live external system.
   Diagnose; don't iterate variations blind.
7. **Reports must carry content, not references** to things the reader may not
   have received.
8. **Record rulings in files**, with reasoning.
9. **State honestly when an obligation wasn't met** — the changelog says "no
   capture accompanies this change" rather than skipping it silently. A process
   that quietly tolerates gaps stops being a process.

---

---

# Session 2 — terrain, material, lighting (2026-08-01)

The first milestone completed end to end. Everything below is new; nothing
above is retracted. The pattern from §2.1 — assuming an API's meaning instead
of reading it — recurred in three fresh disguises, so it is worth studying how
it hid each time.

## 6. New failure modes

### 6.1 A header signature is not the binding signature
`ULightComponent::SetLightColor(FLinearColor, bool bSRGB = true)` is what the
C++ header declares. The Python binding exposes **one** argument:
`set_light_color() takes at most 1 argument (2 given)`.

Reading the header told me the function existed and what it accepted. It did
not tell me what the *binding* accepted. **When calling into a foreign runtime,
the reflected surface is the contract — not the native declaration behind it.**

### 6.2 A value that arrives but means something else
Because `bSRGB` is unreachable and defaults true, the engine decodes whatever
you pass as sRGB. Recipe colours are linear. Passing linear values directly
would have produced a deeper, more saturated tint than specified — **with no
error, and no way to notice from the image alone.**

Same class as the `fov_deg` bug that framed every capture wrong for days: the
call succeeds, the value lands, and the meaning is wrong. These are the
expensive ones, because nothing fails.

**Ask not only "did it arrive" but "in what units, in what space, against what
datum."**

### 6.3 Verify the dispatch path, not just the line
`LandscapeEdit.cpp:6644-6652` puts `RelativeScale3D` in the list that triggers
`FixupProxiesTransform`. I read that, concluded a property-system write would
reach it, and set the property **on the root component**. That fires the
*component's* handler. The trigger list lives in
`ALandscapeProxy::PostEditChangeProperty` — the **actor's**.

Result: 1024 components disagreeing on the landscape origin by 7,812 m.

**Finding the line that does what you want is half the work. The other half is
proving your call actually reaches it.**

### 6.4 Implausible magnitudes render as "broken", not "wrong"
`intensity_lux: 5.0` produced a **fully black frame**. Not dark — black,
including the sky, because `SkyAtmosphere` is driven by the sun and 5 lux makes
the atmosphere itself unlit. Real golden-hour sun is 10,000–20,000 lux.

That value had been flagged as an exposure risk in the *first* recipe audit and
was carried unchallenged through the entire project. **A flagged risk that
nobody actions is just a defect with paperwork.** Sanity-check magnitudes
against physical reality before assuming the renderer is at fault.

### 6.5 Libraries remove things across major versions
`ndarray.ptp()` was removed in numpy 2.0; this project runs 2.5.1. Use
`np.ptp(a)`. Cost one failed run. Pinning a version in docs is not the same as
checking the version's API.

### 6.6 Manual steps need verification every single time
The import dialog silently produced `sections_per_component` 1 instead of 2 and
kept scale 800 instead of 400 — twice across two imports. Both were caught only
because a verifier compared the live scene against the recipe.

**Any step a human performs by hand needs a machine check afterwards.** Not
because people are careless, but because a dialog with a dozen fields will
eventually disagree with the instructions in ways nobody notices.

## 7. New things that worked

### 7.1 Instrument a risky inference so failure is immediate
Before setting the scale by script — an action I believed safe but had inferred
rather than proven — the same script was written to re-read every component's
implied origin afterwards and refuse to report success unless they agreed.

The inference was wrong. The check caught it **in the same run**, before a save,
before a capture, before anything downstream consumed a torn landscape.

**When you must act on an inference, build the disproof into the same
operation.** Being wrong is survivable; being wrong silently is not.

### 7.2 Inspect the artefact before shipping it downstream
Viewing the generated heightmap as an image — before asking for a manual import
— caught two bad terrains in seconds each: a single blob crushed by an
over-aggressive radial mask, then ridges with no mass beneath them. Each would
otherwise have cost a full import cycle to discover.

**Look at the intermediate output. It is nearly always cheaper than the next
step.**

### 7.3 Batch API verification against a limited attempt budget
Conduct rule 6 stops after two consecutive failures against the live editor. On
the lighting script, the first failure revealed one wrong property name — so
instead of guessing the next one, a single source read checked **four** names at
once. Three of them were wrong. Guessing one per attempt would have exhausted
the budget without ever applying lighting.

**When attempts are scarce, spend one read verifying everything rather than one
attempt verifying one thing.**

### 7.4 Gates paid for themselves again
The residency gate refused a capture because the level held 2 landscapes and 272
proxies **on disk** against 1 and 256 in memory — an old landscape's deletion
had never been saved. Without it the capture would have proceeded against an
inconsistent scene.

## 8. New domain gotchas

- **`SkyAtmosphere` has a ground plane at world Z 0.** Terrain below it is
  inside the planet. Combined with the heightmap datum (32768 → actor Z), a
  landscape at Z 0 has *half its height range buried*, which reads convincingly
  as a fog bank rather than as geometry.
- **The sun drives the sky.** With `atmosphere_sun_light`, directional light
  intensity governs the atmosphere too — one implausible value blacks out
  everything, not just the terrain.
- **Property naming strips the `b` and keeps the rest.**
  `bEnableVolumetricFog` → `enable_volumetric_fog`, not `volumetric_fog`.
  `bEnableLightShaftBloom` → `enable_light_shaft_bloom`.
- **`ALight` declares `LightComponent`**, so it is `light_component` on *every*
  light actor — there is no `directional_light_component` or
  `sky_light_component`.
- **Ridged multifractal alone has no mass.** It renders as thin bright ridges on
  a dark field — dramatic crests over a flat plain. Blending a smooth fBm back
  in supplies the shoulders that make mountains look solid.
- **Thermal erosion caps the slope distribution** near the angle of repose,
  which is what makes a slope-threshold material select coherent faces instead
  of speckle.
- **UE landscape resolutions are always N+1** (1009, 2017, 4033) and Gaea builds
  at powers of two. They never agree; crop rather than resample.

## 9. The one-line version, second pass

**Prove the call reaches the code, prove the value keeps its meaning, and when
you have to guess anyway — make the guess check itself.**

---

# Session 3 — textures, and the MCP editor bridge (2026-08-01)

First session with full editor write access and no audit gate on MCP calls.
Nothing above is retracted. The §2.1 pattern — trusting a name instead of
reading it — recurred again, but the more interesting failures this session
were **checks that were looking at the wrong thing entirely** rather than
looking at the right thing wrongly.

## 10. New failure modes

### 10.1 The identity gate answered a question next to the one that mattered
Conduct rule 7 verifies the connected editor's **project**. It passed, and it
was right to. But the editor had an unsaved `/Temp/Untitled_1` open — a New
Level → Open World instance — not `/Game/Alpine`. Every scene-facing script
was operating on **the wrong world inside the right project**, and
`make_landscape_material.py` built, compiled clean, and reported success.

What stopped the assignment was the exactly-one-label gate finding 0 actors
named `Landscape_Alpine`. That gate exists for label collisions. It caught
this by **luck**: the stray landscape still carried the New Landscape dialog's
default name `Landscape`. Rename it and the recipe's material binds to a
stranger's terrain with every gate green.

**A gate proves exactly its predicate and nothing adjacent to it.** "Right
project" was never "right world", and the gap sat unnoticed for two sessions
because the predicate sounded like the thing we cared about. Fixed with
`landscape.level_path` and `verify_landscape.gate_level`, but the transferable
part is the habit: for every gate, say out loud what it does *not* prove.

### 10.2 `dir()` on a UE Python class is a LOWER BOUND, not the property list
`probe_texture_api.py` was written specifically to stop guessing property
names — and its first answer was wrong. It reported
`MaterialExpressionComponentMask` as having only `material_expression_editor_x/y`,
because it enumerated non-callable attributes via `dir()`. But `r`, `g`, `b`,
`a` are real and settable: the shipping material sets them, and reading a live
instance returns `r=False, g=False, b=True, a=False`.

Cause: UE Python generates class descriptors only for some properties, whereas
`get_editor_property`/`set_editor_property` go through the reflection system
by `FName` and accept any editor-accessible `UPROPERTY`. So
`dir(cls)` ⊂ settable properties, strictly.

**A tool built to prevent guessing will itself produce confident wrong answers
if its own premise is unverified.** Absence from `dir()` is not evidence of
absence. `ObjectTools.list_properties` on a live instance is the authoritative
list; that is what caught it.

### 10.3 `blueprint_get_size_x()` returns the resident MIP, not the asset size
A freshly imported 1024x1024 texture reported `[32, 32]`. That reads exactly
like "the importer silently downsampled" — and would have sent a future
session hunting a nonexistent import bug. The asset was always 1024:
`TextureTools.get_size` and the source PNG header both say so.

The proof it measures streaming state and not the asset: the **same call**
returned 32 on the first run and 1024 on the second, after the first run had
made the mips resident.

This is the World Partition residency lesson (§3, "WP exposes only *loaded*
actors") in a second costume: **an engine reading back "how much of this is
currently in memory" while you read it as "how big this is."** Fixed by taking
dimensions from the PNG header before import and relabelling the engine number
`resident_mip`.

### 10.4 An instrument that disagreed with what it measures
`make_layer_debug_material.py` used feather constants of 10 deg / 5%;
`make_landscape_material.py` used 12 deg / 6%. The diagnostic therefore
rendered every band ~20% narrower than the shipping material, so its coverage
readings were not comparable to the material, to the numpy prediction, or to
anything else. It had been shipped as the tool for judging blend geometry.

Worse, `make_landscape_material.py` claimed "This script uses, and schema.md
records:" — and schema.md recorded nothing of the kind. That is §2.5 verbatim
("before writing 'as recorded in X', open X"), and it is the second time.

**When one artefact exists to measure another, they must share the constants
by import, not by transcription.** Now imported; verified equal afterwards
(Snow 11520.0 cm, Rock 4608.0 cm, Grass 7680.0 cm in both).

### 10.5 A "verification" that verified the mean and missed the catastrophe
`make_layer_textures.py` was written with an assertion on the one number
believed load-bearing: per-channel mean exactly 0.5, so a mipped-out texture
multiplies by 1.0. That assertion **passed on the first run** — and the
textures were still unusable. Contrast was near-binary: rock at c=1.15 gave an
albedo multiplier range of **x0.00 to x3.92**, black to four times blown out.
A perfectly-centred mean says nothing about the spread around it.

Caught by **looking at the PNGs** (§7.2), not by any check. The fix added the
missing gate — the generator now also refuses on the realised 95% multiplier
range — but the lesson is that the assertion I chose was the one I had already
thought about.

**Ask what a passing check still permits.** Mean 0.5 permitted every pixel
being 0 or 1.

### 10.6 Repairing a value afterwards, instead of making it an identity
The first texture generator added a per-channel tint and then restored each
channel's mean by re-fitting through `arctanh`. `arctanh` diverges at the
extremes, so a 4% tint became saturated magenta and green blobs.

Replaced with a gain on the deviation: `ch = 0.5 + (scalar - 0.5) * (1 + k)`,
whose mean is 0.5 **algebraically, for any k** — nothing to converge, nothing
to repair.

**Prefer an invariant that holds by construction over one restored by a
correction pass.** The correction pass is where the artefacts live.

## 11. New things that worked

### 11.1 One read resolving the whole surface, again
§7.3 held. A single read-only probe resolved `texture`/`sampler_type`, the
`UVs`/`Tex` pin names, `SAMPLERTYPE_LINEAR_COLOR`, `TC_BC7`, `TA_WRAP` and the
`AssetImportTask` fields together. The one name it *didn't* cover —
`SamplerSourceMode` — I noticed before calling it and re-probed rather than
spending a live attempt. Cost: one extra probe run. That is the right trade
against a 2-failure budget.

### 11.2 Read-back as a gate, not as logging
`import_layer_textures.py` sets `srgb=False` and then reads it back and
refuses on mismatch. This one matters more than it looks: a stuck sRGB flag
darkens every textured layer by ~57% with a clean compile, a correct-looking
asset, and no error anywhere. There is no later step that would catch it —
the capture would just look a bit dark, which is indistinguishable from
art direction.

**Where a wrong value is invisible rather than loud, verification has to be
part of the write, not a downstream check.**

### 11.3 Doing the arithmetic before building the feature
Before writing any shader nodes, one calculation asked whether a 4 m texture
repeat is even *visible* from cameras 3–14 km away. Answer: 0.55–2.7 pixels —
it mips to its mean and contributes nothing. The whole milestone would have
shipped a capture identical to the pre-texture one, and the natural conclusion
would have been "textures don't work" rather than "the scale is wrong".

That single calculation is why `macro_tiling_m` exists.

**Before implementing, compute what the result will look like at the size it
will actually be seen.** §6.4 said sanity-check magnitudes against physical
reality; this is the same rule pointed at spatial frequency.

### 11.4 Refusing to destroy something that wasn't mine to destroy
Finishing the milestone required `/Game/Alpine` open. Opening it discards the
unsaved `/Temp/Untitled_1`, which git cannot restore and which is not this
pipeline's work. Stopped and reported instead, having completed everything
that did not depend on it.

The instruction was "don't come back for approvals". That covers implementation
choices; it does not extend to irreversibly discarding someone's unsaved work
on their behalf. **Autonomy over how to do the task is not authority to
destroy state the task didn't create.**

## 12. MCP-specific notes

- `list_toolsets` / `describe_toolset` / `call_tool` behave as advertised, and
  the schemas were accurate everywhere they were checked.
- **`SlateInspectorToolset` really is a Playwright-style UI automation
  toolset** — snapshot, screenshot and interaction tools, with a depth-0 root
  observer and explicit `Observe()`/`Unobserve()` on a window before deep
  widget access. That is a direct answer to the open question about driving
  the New Landscape dialog: the capability exists. Untested here.
- `ProgrammaticToolset` remains sandboxed with no `unreal` module — it cannot
  substitute for remote execution.
- MCP `list_properties` returns camelCase keys (`materialExpressionEditorX`)
  while `get_properties` accepts and echoes PascalCase (`R`, `G`, `B`).
  Python's `set_editor_property` wants snake_case. Three conventions for one
  property; do not assume the casing carries across tools.
- Creating a scratch asset to introspect pin names is cheap and fine, but it
  is editor state: `/Game/Debug/M_ApiProbe` was created for one read and
  deleted in the same session. Log MCP mutations or they become the
  undocumented hand-state route B exists to prevent.

### 12.1 Slate automation: two traps found in the first hour
Both are the same shape — **a reading that is absent is not a thing that is
absent** — and both would silently mislead an implementer.

- **The accessibility tree lags the UI.** After clicking a tab or a tool, two
  consecutive `Snapshot` calls returned an *empty* panel while a `Screenshot`
  of the same widget showed it fully rendered with nine buttons. Anything that
  treats an empty snapshot as "the control isn't there" will misfire. The
  screenshot was the reliable readback every time the tree disagreed.
- **Refs die on a details-panel rebuild.** After writing one combobox, cached
  refs for the *whole* subtree went dead — including tabs that had not visibly
  changed — and snapshots returned an empty tree until the root observer was
  re-registered. The toolset's own documentation says *"Refs discovered by a
  previous Snapshot remain usable. You do NOT need to call Snapshot again
  before every action."* **That is false across a rebuild**, which is another
  instance of §6.1: the documented contract is not the binding contract.

### 12.2 Prove a UI write the same way you prove an API call
Setting `Sections Per Component` to `2x2 Sections` returned `true`. That proves
the click was delivered, not that the value took. The actual proof was reading
back a *derived* field: `Overall Resolution` went 505 -> 1009, which is exactly
`63 x 2 x 8 + 1`.

**A UI automation tool's success return is the same kind of evidence as a
setter that does not raise — it says the call happened, not that the meaning
landed** (§6.3). Drive UI the way you drive an API: change something, then read
back something *downstream* of the change.

### 12.3 A process being alive is not the resource being available
Chasing an unresponsive editor produced two wrong inferences in a row, both
from reading one signal as if it answered a different question.

- **A changed remote-exec node ID was read as "the editor restarted."** It was
  not. `Get-Process` showed the same PID with a `StartTime` days earlier — the
  node GUID is per *registration* of the Python remote-execution service, not
  per process. An entire chain of reasoning ("so this must be a fresh empty
  Untitled_1, so the earlier work is already gone") rested on it. The
  conclusion happened to be corroborated by an independent check — the dry
  run's dirty-package query reported nothing pending — but the premise was
  invented.
- **`Responding=True` was nearly read as "the editor is fine."** Windows'
  `Responding` only says the window message pump is answering. It says nothing
  about the game thread, and nothing at all about whether an in-editor service
  is listening. The signal that actually mattered was that **UDP 6766 and TCP
  8000 had no owning process** — the services were gone while the process was
  not.

**When something is unreachable, check the specific resource, not a proxy for
it.** Process alive, window responsive, port listening, and service answering
are four different facts, and only the last one is the question.

### 12.4 The engine's own safety prompt is disabled on the scripted path
Worth knowing before writing anything that transitions maps.
`ULevelEditorSubsystem::LoadLevel` sets `GIsRunningUnattendedScript = true`
(`LevelEditorSubsystem.cpp:540`). The engine's protection against losing an
unsaved world is a `FMessageDialog` asking *"The unsaved level {0} will be
lost. Continue?"* with default `Yes` (`EditorServer.cpp:2131`) — and under the
unattended guard a dialog returns its default. **So the engine does not warn
and does not abort; it discards silently.**

The general rule: **an interactive safeguard is not a safeguard once you are
driving the API.** Any guard you were relying on the editor to provide has to
be re-implemented on the calling side, and the only way to know which ones
vanish is to read the path.

### 12.5 Reading the world is enough to kill the editor across a map load
The single most expensive finding of the session, and it cost two editor
crashes to reach because the symptom pointed away from the cause.

**Symptom:** `open_level.py` returned `ConnectionResetError` at `load_level`,
twice, and the editor became unreachable. Everything about that reads as
"the load is slow and the remote-exec connection timed out." It was not.

**Actual cause**, from the crash log:

    Fatal error: [EditorServer.cpp] [Line: 1951]
    World Memory Leaks: 1 leaks objects and packages.

That is `UEditorEngine::VerifyLoadMapWorldCleanup`. On a map transition the
engine verifies nothing still references the world being torn down, and a
survivor is a **fatal error, not a warning** — it takes the editor down.

**What was referencing it: my own payload.** The guard read the current level
via `get_editor_world()` in the same Python frame that then called
`load_level`. A `unreal.World` handed to Python is a wrapper holding a real
UObject reference, so *merely having looked at the world* was the leak. The
guard could not simply be moved — it has to be atomic with the load or it is a
TOCTOU (that was a prior audit finding). So the references have to be
explicitly released: `del` the wrappers, and `gc.collect()` immediately before
`load_level`, with nothing touching the world in between.

**Three transferable rules:**
1. **A read is not free.** In a foreign runtime, reading an object can extend
   its lifetime, and lifetime can be a correctness property rather than a
   performance one. "It's only a read" is not a safety argument.
2. **`ConnectionResetError` from a live editor means the editor died, not that
   the call was slow.** Two sessions were spent on the timeout hypothesis
   because the transport error looked like a transport problem.
3. **Read the crash log before theorising.** The log named the file, the line,
   and the failure mode. Every minute spent on process working-set numbers and
   port ownership (§12.3) was a substitute for the one artefact that actually
   said what happened.

**Status: hypothesis validated by root cause, NOT yet by a successful run.**
The fix is in `open_level.py:_release_world_refs`, ordering verified
statically. It has not yet loaded a level successfully.

### 12.6 "Reused" is not "exactly one"
`apply_lighting.py` found its actors with `_find_or_spawn`, which returns the
FIRST actor whose label matches and never counts. `/Game/Alpine` held a
complete duplicate lighting rig - two DirectionalLights, two
ExponentialHeightFogs, two SkyLights, two SkyAtmospheres - carrying the
engine's DEFAULT labels. So nothing ever matched them, the script reported
every actor as "reused", exited 0, and the stray fog (density 0.0436 at
StartDistance 0, ~20x the recipe's 0.0022 and starting at the camera) whited
out every capture.

The landscape scripts have had an exactly-one gate since the two-landscape
incident. The lighting script never got one, because "find mine by label"
*feels* like identification. It is not: it answers "is there one of mine",
never "is mine the only one". These classes are singletons IN EFFECT - fogs
stack, atmospheres stack, and UE itself warns that multiple directional lights
compete for volumetric fog - so hard rule 2 ("the recipe owns every scene
parameter") is simply false while a foreign one exists.

**A find-by-name that ignores what else is there is not identification.** Fixed
with a census over every recipe-governed class and a refusal (exit 6) when
anything foreign is present.

### 12.7 Distance was the variable nobody was controlling
Three cameras disagreed and it took far too long to notice the axis they
disagreed on. Oblique at ~4.2 km rendered fully; top-down at 9 km rendered in
blocks; the two ground cameras at 3-14 km rendered nothing at all. Two whole
theories - fog density, then camera aim - were tested and discarded before
"how far away is it" was even considered, and the aim theory was disproved by
arithmetic that had been available from the start (the summit sits at +5.6 deg
and +10.5 deg, comfortably inside both frames).

**When several instruments disagree, sort them by the parameter that differs
and look for monotonicity before theorising about any one of them.** The
answer was in the ordering, not in any single image.

### 12.8 A camera outside the streamed region photographs nothing
Five hypotheses were tested before the right one: stray fog, recipe lighting,
camera aim, view distance, landscape LOD. Each was eliminated with evidence,
which was right - but the actual variable was never in the list until the
cameras were sorted by POSITION rather than by what they were looking at.

World Partition streams around the camera as a streaming source. A capture
camera parked outside the loaded regions has nothing to stream, so it renders
empty sky no matter how correct its aim, its FOV, or the geometry. The split
was perfectly clean once looked at: the two cameras inside the +/-4032 m
footprint rendered, the two outside did not.

**When several instruments disagree, enumerate every way they differ before
theorising about any one difference.** Distance, altitude, pitch and position
were all confounded here; only position separated them, and it was the one
attribute nobody had tabulated. Sorting by the wrong axis produced two
plausible, well-argued, wrong theories in a row.

Corollary for this repo: `capture.py` should refuse, or at least warn, when a
recipe camera sits outside the landscape footprint. It is a cheap, purely
arithmetic check against `landscape.location_cm` and the derived span, and it
would have turned four wasted capture cycles into one refusal.

### 12.9 The material rendered, compiled clean, and was 92% wrong
The auto-material shipped, built without error, produced captures, and was
inspected by eye across several sessions. Snow's and Grass's slope masks were
identically ZERO over the entire terrain the whole time. Only Rock ever
rendered; the green filling every capture was the flat background constant.

Two independent defects compounded:

1. **The outward feather was clamped in DEGREE space, where the cosine range
   is closed.** No angle has a cosine outside [0, 1], so for any band touching
   0 or 90 degrees the clamp collapses the OUTER bound onto the INNER one and
   hands the ramp a zero-width span. Snow `[0, 52]` and Grass `[0, 35]` both
   start at 0. Naively dropping the clamp is WORSE: cos is even about 0, so
   the bound folds back INSIDE the band and inverts the ramp.
2. **The ramp's degenerate-span guard chose its sign from the span, not from
   the caller.** `_ramp` took a `_rising` argument and never referenced it,
   picking `+1e-9` whenever `span >= 0`. That turns a degenerate FALLING edge
   into a rising step: `saturate((nz - 1.0) / +1e-9)` is 0 for every possible
   input, including a perfectly flat quad.

Every constant reached the shader with the correct magnitude. The graph
compiled. Nothing errored. **Getting the number right from a wrong premise
produces confident, wrong output** (section 2.1) - and the wrong premise here
was geometric, not numeric: that a feather can always be pushed outward.

Three things would each have caught it, and none were in place:
- The numbers were checkable on the CPU. `_assert_band_invariant` now
  evaluates the SAME ramp arithmetic host-side and refuses a band whose mask
  does not read ~1 at its own centre. No editor, no shader, no capture.
- The debug false-colour material was NOT affected - it floors its feather
  widths and lets the outer bound exceed 1.0. So the one instrument built to
  validate layer coverage was validating a DIFFERENT code path from the thing
  it was meant to validate. Two implementations of one idea drifted, which is
  exactly what section 1.9 says to prevent by sharing the deciding code.
- The defect was visible in the image: the green had ZERO texture variation,
  because the background constant bypasses the texture path entirely. "Flat
  where everything else is textured" sat in every capture for hours.

**A first version of the new gate checked bound ORDERING instead of mask
behaviour.** It rejected a legitimate `blend_sharpness: 1.0`, and a non-strict
version would have passed the very bug it existed for. Test the behaviour, not
a proxy for it.

### 12.10 A helpful error message broke the transport
`make_landscape_material` failed four consecutive runs with
`Could not load Python file '<engine dir>/<the entire script>'`, while every
sibling script kept working.

Cause, from `PythonScriptPlugin.cpp:813-830` - ExecuteFile mode scans the
WHOLE command for the substring `.py`, across code, comments and STRING
LITERALS alike, and treats the payload as a path if it finds one. The
offending text was an error message added hours earlier to be helpful:

    " -- run scripts/import_layer_textures.py first. "

**The cost was not the bug, it was the theory.** The failing script has by far
the largest payload in the repo, so "the big one, and only the big one, fails"
was extremely plausible. Two rounds of shaving prose off the payload went by -
one of which reduced the size while the error persisted, which should have
killed the theory on the spot and did not. A tokenizer-based comment stripper
was written for it and later deleted, having solved nothing. The engine source
settled it in one grep.

**When a component fails and its siblings do not, list what is ACTUALLY unique
about it, not what is merely conspicuous about it.** Size was conspicuous.
Naming a .py file was unique - and only one of those was in the code path.

Two rules fall out:
- **Never name a .py file inside a remote-exec payload**, in any context,
  including comments and error strings. `_guard_payload` now refuses one and
  cites the engine source.
- Correlation that survives a partial fix is not confirmation. Payload size
  went 13556 -> 12797 -> 10840 and the failure never moved; the final WORKING
  payload was 12797, the exact size that had "failed".

## 13. The one-line version, third pass

**Say what each gate does not prove; check what a passing check still permits;
and take the measurement from the thing that knows, not the thing that
answers.**

---

# Session 4 — the throughput collapse was the machine sleeping (2026-08-01)

One diagnosis, and it is worth its own section because of how far the
plausible explanation was from the real one, and how cheap the decisive
evidence turned out to be.

## 14. New failure modes

### 14.1 A performance symptom that was not a performance problem at all
`docs/changelog.md` recorded, under its own heading: *"Capture throughput has
collapsed: the three shots in this run landed 1h49m and then 6h51m apart, and
the fourth never completed. Worth investigating before the next
capture-heavy session."*

Every hypothesis available at that point was a rendering hypothesis — Software
Lumen on an integrated GPU, 313 materials recompiling, World Partition
streaming, the 900 s ceiling being too low. All of them were wrong. **The
laptop entered Windows Modern Standby.** The editor was not slow; it was not
running.

### 14.2 The evidence was in a field nobody had ever read
Every UE log line carries two brackets: `[timestamp][frame]`. The second is
the frame counter, and it is the only field in the log that measures *engine
work* rather than *wall-clock time*.

    [2026.08.01-08.48.00:504][842]   last line before the gap
    [2026.08.01-10.36.04:091][843]   first line after it

**One frame in 108 minutes.** That single comparison discriminates between
every rendering hypothesis and the real cause, because a throttled-but-awake
editor still runs 3-4 FPS — about 25,000 frames over that span. Two rendering
sessions had already gone past those two lines without reading the number in
the second bracket.

Windows confirmed it independently: Kernel-Power event 507 *"The system is
exiting Modern Standby"* at 03:36:04 and 10:27:44 local, which are 10:36:04Z
and 17:27:44Z — each within seconds of a screenshot finally being written.
The captures completed **on resume**, in request order, exactly as a suspended
process would.

**The general rule: when something is slow, first establish that it was
running.** Elapsed time is not work. Find the counter that only advances when
work happens — frames, ticks, samples, sequence numbers — and read that
instead. Every clock in the system keeps ticking through a suspend; the frame
counter is the one thing that does not lie about it.

### 14.3 A timeout measured in wall-clock time cannot bound a suspended process
`SCREENSHOT_TIMEOUT_S = 900.0` was compared against `time.time()`, which keeps
advancing across a suspend. So standby burned the entire ceiling, the run was
declared a failure, and the engine then wrote three of the four files hours
later. **The script reported a failure that had not happened, about work that
subsequently succeeded.**

The ceiling exists to bound a *hung editor*. An editor that is not being
scheduled at all has not hung. The wait now measures in editor time: a
detected suspend is added back to the deadline rather than charged against it.

The auditor then caught the mirror-image defect in that very fix (C2): the gap
was being measured across the whole loop body, which contains a blocking
remote-exec round trip, so a **shader-compile stall** — this script's
documented normal case — would exceed the 30 s threshold, extend the ceiling,
and print `host was SUSPENDED`, an assertion the code had no evidence for.
Measuring across the `sleep()` alone is what makes the claim true. **A
diagnostic that can fire for the wrong reason is worse than none: it writes a
false attribution into the record where a future session will read it as
fact.**

### 14.4 …and the SECOND cause, found only because the fix exposed it
With the sleep inhibitor held, the very next capture run stalled anyway.
`ridge_wide` sat outstanding for eleven minutes with the frame counter
advancing normally at ~3 FPS — so the editor was awake, ticking, and simply
not producing the screenshot. That combination is exactly what §14.2's rule
predicts you should look at next: the machine was running, so the explanation
had to be somewhere else.

**The editor window was MINIMIZED.** `IsIconic()` on its main window returned
true. A minimized editor does not draw its level viewport, and
`take_high_res_screenshot` is latched on the `FViewport` and serviced in
`Draw()` — so the request is accepted, the task is valid, the engine reports
`done: false` forever, and nothing is wrong anywhere except that no frame is
being drawn to satisfy it.

Restoring the window with `ShowWindow(SW_RESTORE)` completed the pending shot
**within seconds**, and the remaining three cameras finished in the seconds
after that.

This also retro-explains the one number that never fitted the standby theory:
in the 08:37Z run, `ridge_wide` took 9m54s while the machine was demonstrably
awake. That was this defect, not the other one. **Two independent causes were
producing one symptom, and fixing the first is what made the second
visible** — which is the ordinary case, not the exceptional one. A symptom
that persists after a correct fix is not evidence the fix was wrong.

**The rule: a headless-looking automation can still depend on a window being
drawn.** Remote execution makes the editor feel like a service. It is not
one — it is a GUI application, and anything that ultimately requires a frame
requires the window to be in a state that produces frames.

## 15. New things that worked

### 15.1 The three-way cross-check
The diagnosis rested on three independent sources agreeing: the engine's frame
counter, the Windows event log, and the on-disk mtimes of the capture files.
No one of them alone would have been conclusive — the frame counter could have
been a logging artefact, the Kernel-Power events could have been coincidence —
but they are produced by three systems that do not consult each other. **When
a conclusion has to be right and cannot be re-run, get it from sources that
have no way of agreeing by construction.**

### 15.2 A dry run that found nothing was the most valuable output of the day
`save_level.py` was written to persist a scene believed to be unsaved, on the
strength of three consecutive handoffs saying *"Level still NOT saved"*. Its
dry run reported **zero dirty packages**, and the git history then showed
`a853f8f` had already deleted the four stray lighting actor packages from
disk. The scene had been persisted two commits earlier and the handoff note
was simply stale — carried forward, unverified, three times.

Had the script not defaulted to a dry run, the first thing it would have done
is write. It would have "succeeded", and the stale note would have been
retired by a save that saved nothing. **Dry-run-by-default is not only a
safety property; it is how you discover that the premise of the task was
false.**

### 15.3 The audit gate caught a refusal that mutated first — again
Finding S2: `save_level.py` enumerated, classified, **saved**, and then let
the host print `REFUSE` on unclassifiable packages. This is verbatim the
pattern recorded in CLAUDE.md's non-negotiable 1 (*"a 'refusal' that mutated
and saved before printing REFUSE"*), reintroduced by an author who had read
that line the same day. **A gate placed on the wrong side of the operation is
the single most repeatable defect in this project.** The rule it implies:
when a refusal and a mutation live in the same payload, the refusal must be
evaluated *in that payload*, before the mutation — host-side checking is
reporting, not gating.

### 14.5 A diagnostic instrument that drifted from the thing it measures
`make_layer_debug_material.py` built its false-colour masks from
`MaterialExpressionVertexNormalWS`. That is precisely the measurement the
baked weightmap was created to REPLACE — the shader normal is the normal of
the decimated mesh, so it flattens with LOD.

Nobody changed the debug material when the shipping material changed. It kept
compiling, kept rendering, and would have visualised — in confident,
maximally-legible false colour — **a decision the shipping material no longer
makes**, while being used to diagnose that very material. It was caught only
because the diagnosis started by reading the instrument's source.

The fix was to import the UV derivation from the shipping script
(`weightmap_uv_params`) so the two cannot drift again. **The general rule: an
instrument is code too, and it rots exactly like code. When you change what
the system decides, the thing that visualises the decision is part of the
change, not a bystander.**

### 14.6 An unlit readout is an ABSOLUTE luminance, and this scene is bright
Making the debug material unlit + emissive was correct — a lit false colour is
tinted by sun, sky and fog, so a warm cast is ambiguous between "different
layer here" and "differently lit here", which was the exact ambiguity being
diagnosed.

But emissive is an absolute scene luminance, and the scene is exposed for an
18000 lux sun. At the natural-looking value of 1.0 the entire readout rendered
**black** — and black is the instrument's own "no layer matched" colour. The
first debug frame therefore said *"nothing matches anywhere"*, which is a
specific, alarming, and completely false claim.

Two full assign-and-capture cycles went into it. The tell that it was exposure
rather than zero masks was available for free and was not read first: a
crushed magenta is still *magenta-hued*, and the frame was perfectly neutral —
consistent with everything being multiplied toward zero, not with one channel
being selected. The scale is now derived from the recipe's own
`sun.intensity_lux` so it tracks the lighting instead of being a magic number.

**The general rule: when you take a measurement out of the lighting path, you
also take it out of the exposure path — and an instrument whose failure mode
renders as one of its own legend colours cannot be read.**

### 14.7 The capture stall, third refinement: FOREGROUND, not visible
§14.4 said a minimized editor does not draw. That was right but not the whole
rule, and the difference cost another two runs.

With the window restored but the editor merely *unfocused*, captures stalled
again — 11 and 13 minutes, frame counter advancing normally at ~3 FPS. The fix
attempted from the engine side did not work either, and it is worth recording
that it did not: `ULevelEditorSubsystem` exposes both
`EditorSetViewportRealtime(true)` and `EditorInvalidateViewports()` as
BlueprintCallable in 5.8 (`LevelEditorSubsystem.h:65-69`), both were called,
both **returned success on every poll** (`realtime_set: true`,
`invalidated: true`), and the screenshot still never serviced. Bringing the
window to the front completed it in seconds, every time.

So the gate is not viewport invalidation and not realtime — it is that an
editor which is not the foreground application does not render at all. The
lever is almost certainly the editor preference **"Use Less CPU when in
Background"** (`EditorPerformanceSettings.bThrottleCPUWhenNotForeground`),
which is a settings change on Ryan's machine and therefore his call, not
mine.

**Recorded as a negative result on purpose.** A plausible fix that was tried
and did not work is worth as much as one that did: without this note the next
session spends its budget re-implementing `EditorInvalidateViewports`.

## 16. Lesson 9 — a failed probe is not a negative result (RYAN, 2026-08-01)

**A negative result from an API probe must be distinguishable from a failed
probe.** Any branch on a falsy attribute read against an engine type must
fail loud rather than fall through to "not found".

This is lesson 2.10 ("diagnostics must distinguish 'I looked and it's
absent' from 'I couldn't look'") promoted to a coding rule, because 2.10
kept being satisfied in prose and violated in code. The instance that
prompted it: `push_heightmap.py` read `hit_actor` off an `FHitResult`,
which does not exist in 5.8 — `HitResult.h:126-131` declares
`HitObjectHandle` and `Component`, and `hit_actor` is a *break-node pin
name*. The read raised on every sample, a bare `except Exception` swallowed
it, and the run would have reported **"no trace hit the landscape under any
mapping"** — an assertion about the world, produced entirely by a broken
probe, in the script that writes terrain.

The shape to watch for:

    try:
        value = obj.get_editor_property("name")
    except Exception:
        pass            # <-- the defect: absence and failure now identical

Both a missing landscape and an unreadable property arrive at the same
branch, and the message names the first.

### The sweep (run 2026-08-01, 17 hits)
Fixed in `push_heightmap.py` (2 sites, both on the identification gate of
the write path): an unreadable `section_base_x` now refuses with *"the
signature could not be COMPUTED, which is not the same as not matching"*
rather than degrading into "no landscape matched".

**Reported and NOT yet fixed** — every one is in a script that was not
running, and they are listed here so the next session does not have to
re-derive the sweep: `verify_landscape.py` ×3 (`landscape_guid`,
`landscape_actor_ref` membership), `save_level.py` ×4 (package-name and
actor-label reads), `landscape_inventory.py` ×3 (owner label, guid,
package getter), `delete_stray_landscape.py` ×2 and
`set_landscape_scale.py` ×1 (`landscape_actor_ref` — note these two are on
DESTRUCTIVE paths and should be first in the queue),
`apply_lighting.py` ×1 and `push_heightmap.py` ×1 (both diagnostics-only,
where the fallback is itself reported — arguably benign).

### Sweep completed 2026-08-02, and the audit of the list changed it
Working the list turned up something worth more than the fixes: **three
of the entries were not defects, and one was worse than recorded.** A
list of findings is itself a claim that needs checking before it is
acted on.

**`delete_stray_landscape.py` — FIXED, and the second site was the
dangerous one.** Site 1 (`_derived_resolution`) swallowed the read while
deriving the resolution that IDENTIFIES what gets deleted, so an
unreadable proxy became "belongs to someone else" and the signature was
computed from a partial census — lesson 2.6 feeding a deletion gate. It
now raises.

Site 2 was already correct (it recorded `READ FAILED` and routed the
proxy to `unattributed`). Site 3 was the one the sweep under-rated: it
builds the KEEPER PROTECTION SET, and a swallowed read dropped a
keeper's proxy silently OUT of the protected set — while that same proxy
could still enter the kill list through site 2, where its read
succeeded. So the hard assertion could pass with a keeper's proxy queued
for deletion. **A guard that weakens precisely when reads are
unreliable, which is precisely when it is needed.** Now refuses at a new
`keeper_set_incomplete` stage, evaluated in the same payload as the
mutation and before it (lesson 15.3).

**`set_landscape_scale.py` — FIXED.** The swallow removed proxies from
the census the TEAR CHECK measures. Fewer components read means fewer
chances to disagree, so the swallow made the check weaker exactly as
reads became less reliable — and this is the operation that has already
torn a landscape into 1024 pieces disagreeing by 7.8 km (§6.3). `ok` now
requires a COMPLETE census, not merely an agreeing one.

**`verify_landscape.py` ×3 — NOT DEFECTS.** The swallows degrade to
`proxy_attribution_verified: False`, which the host treats as failure
and exits 6 with *"a tripwire that cannot read the thing it guards is
not a tripwire."* That is what lesson 9 asks for; it was already done.

**`landscape_inventory.py` ×3 — FIXED, and it was the subtler kind.**
Nothing here gates anything, so by the triage principle it looked benign
— but the principle's condition is that the degradation is REPORTED, and
`except Exception: pass` reports nothing. An unreadable owner and an
absent owner both rendered as an entry under "PROXIES WITH NO READABLE
OWNER", and that section is what a deletion checklist gets built from.
The report now separates "looked, and there is none" from "could not
find out", and says outright not to build a kill list from the second.

**The general rule this leaves:** a sweep list is a hypothesis per
entry. Re-derive each one against the code before fixing it — three of
these needed nothing, and the one entry recorded as a plain duplicate
("`delete_stray_landscape.py` ×2") concealed the most dangerous site of
the set.

**Triage principle that came out of it:** the defect is only a defect where
the swallowed value feeds a GATE or a user-facing claim about the world. A
swallow that degrades a *diagnostic field* to `None`, and says so, is fine.
A swallow that degrades a *decision* is the bug.

---

# Session 5 — the pipeline closes; measurement replaces taste (2026-08-02)

The session P0 was finished, erosion was built, and the project became a
WORLD pipeline rather than a landscape one. The recurring theme is sharper
than in any previous session: **almost every wrong answer came from reading
a name, a header or a signature; almost every right one came from a
measurement.**

## 18. The failure modes

### 18.1 When the measure is aesthetic, "better" is unfalsifiable
I reported the eroded terrain as a REGRESSION because its median slope fell
from 44.2° to 22.1°. I was scoring it as a hero landscape. The project's
actual goal is a world to explore, and against that the reading is
backwards: a median of 44.2° means the MEDIAN CELL sits at the engine's
walkable limit — half the world is wall. The erosion had moved toward the
goal and I called it a step back.

Nothing about the terrain changed when I understood this. What changed was
that a metric existed. Once `traversability()` was written the answer was
not debatable: walk-crossable 52%→81%, walk-in-one-piece 51%→88%,
mount-in-one-piece **1.3%→84.9%**.

**The rule: build the metric that encodes the purpose BEFORE judging the
artefact.** Until it exists, "better" is a matter of who is more confident,
and confidence is not evidence. This generalises past terrain to anything
where the deliverable is judged by eye.

### 18.2 Reflected names are not derivable, and the stub only half-helps
Three live editor runs were lost to invented Python names, each costing a
conduct-rule-6 attempt:
- `landscape_actor` → the property is `landscape_actor_ref`, and the
  DEPRECATED one right above it in the header is literally called
  `LandscapeActor`, while `LandscapeActorRef` carries
  `DisplayName = "Landscape Actor"`. Every human-facing surface says the
  wrong thing.
- `landscape_components` → not a property at all; the working idiom is
  `get_components_by_class`, which two audited scripts already used live.
- `create_render_target2_d` → it is `create_render_target2d`.

Then the generated stub arrived and settled all three offline in seconds —
and immediately produced a fourth example: `GetEditLayersBP` has
`DisplayName = GetEditLayers` and reflects as **`get_edit_layers_bp`**.

**But the stub is an oracle for EXISTENCE, not for SEMANTICS.** It is
generated from the same headers and inherits their misleading names. It
told me `ReadRenderTargetRawPixelArea` takes `min_x, min_y, max_x, max_y` —
so I "corrected" working code and told Ryan the tiling analysis had to be
re-derived. It didn't: `KismetRenderingLibrary.cpp:454` forwards those into
the helper's `X, Y, WIDTH, HEIGHT` slots and `:326` builds
`SampleRect(X, Y, X + Width, Y + Height)`. They behave as width and height.
The measurements had been right the whole time.

**The rule: reuse the idiom already proven live before inventing one, and
when a name and a measurement disagree, the measurement wins.**

### 18.3 A source trace is a hypothesis; a probe matrix is an answer
Three separate conclusions this session were derived carefully from engine
source and then overturned by a single measurement:
- the export encoding (I said normalised, the auditor said raw, the probe
  said **raw** — the auditor was right and my material-graph reading was
  wrong);
- the read-back argument semantics (above);
- "the export writes only one quadrant" (it actually TILES with period
  1008, and what I had read as empty was the terrain's own low corner
  repeated — I inferred "empty" from small numbers without checking whether
  small numbers were expected there).

The thing that settled each was the same shape: **vary one input at a time
and watch the output.** The size probe ran three render-target sizes and
killed the canvas-extent hypothesis outright. One run, no argument.

**Reading a node graph through an introspection API is not reading source
either** — I presented the material's `If` node wiring with more confidence
than it had earned, and the flag matrix contradicted it flatly.

### 18.4 An idempotent test cannot exercise the thing it is testing
The first push was the heightmap the terrain was already built from. It
passed everything. The first CHANGED push immediately exposed a real defect:
all 1280 verification vertices came back ~16000 units out, and a re-read
moments later matched **exactly, median 0.000**. The import applies
DEFERRED; the export was reading the pre-push terrain. The write was always
correct and the check was early.

That defect was invisible to the idempotent case by construction — before
and after look identical. It is why "the mechanism ran" and "the mechanism
is verified" had to stay separate claims, and why the docstring said so
before the changed push existed to prove it.

**The rule: a test whose pass and fail states are indistinguishable is not
a test. Say so at the time, not afterwards.**

### 18.5 A parameter nobody can reason about will be wrong
`lighting.fog.height_falloff: 0.12` had sat in the recipe unchallenged
since the first milestone. `SceneCore.cpp:405` divides it by 1000 before
use, so it meant a **57.8 m half-height** — a near-vertical wall of fog,
and the hard horizontal line visible across every capture for days.
Meanwhile the fog actor's world Z — which decides which of a world is
buried, since fog is densest at that height — was set by **nothing at all**
and sat at 1920 m while the terrain's p90 was 1610 m.

Both are now recipe fields in metres. **Express a parameter in units a
person can picture, or it will be inherited unexamined forever.**

## 19. What worked

### 19.1 Gates that name the right component
Every refusal this session pointed at the right thing, and several were the
only reason a wrong answer did not ship: the extent gate said "the export
is PARTIAL" instead of "the orientation search is not decisive"; the
transport guard caught a `.py` in my own explanatory comment three separate
times; the exit-code contract distinguished "never sent" from "sent,
outcome unknown" and turned a lost response into a diagnosis instead of a
false failure report.

### 19.2 Previews are cheaper than captures, and they predicted the capture
The hillshade said "good mountain, empty plain" before a single frame was
rendered, and the capture agreed exactly. It also caught two bugs in my own
instruments — a hillshade that saturated because it was handed raw uint16,
and a slope report that used the recipe's cell spacing regardless of the
resolution actually generated, making every cross-resolution comparison
nonsense.

**Instruments need calibrating against something known before they are
trusted, and they rot when the thing they measure changes.** The debug
material was still computing masks from the vertex normal months after the
shipping material stopped doing so.

## 20. The one-line version, fifth pass

**Build the measurement that encodes the purpose, then let it — not the
header, not the name, not the confident reading — decide who is right.**

---

# Session 6 — the metric was being paid by the defect (2026-08-02)

The massif mask was replaced so terrain reaches the map edges. Nothing
above is retracted. The theme of session 5 was "build the metric that
encodes the purpose"; this session is what happens the FIRST time two
such metrics disagree, and the answer is uncomfortable.

## 21. New failure modes

### 21.1 The headline number was substantially produced by the defect
`mount-in-one-piece 1.3% -> 84.9%` was this project's best result and the
evidence that measurement had replaced taste. Filling the map to its
edges dropped it to **22.1%** — with better terrain by every other
reading.

The reason is that the old world's radial mask flattened roughly a third
of the map, and **that dead frame WAS the largest connected rideable
region.** The metric was not wrong and it was not gamed on purpose; it
was answering "how much crossable ground is in one piece" perfectly
truthfully about a world whose crossable ground was mostly a plain
nobody would want to cross. Removing the plain removed the number.

**The rule: when a metric jumps after a change that also created a large
uniform region, check whether the uniform region IS the metric.** A
connectivity measure is maximised by featurelessness, so it must never
be read without a measure of whether there is anything there — which is
why `composition()` now runs beside `traversability()` and why the
generator prints both. Neither describes a world alone. The pair does.

Corollary, and the more general form: **a single metric optimised alone
will be satisfied by the cheapest thing that satisfies it, and for
terrain the cheapest thing is always flat.**

### 21.2 The lever I was sure of moved the number by 6 points; the one I
### had not considered moved it by 70
The obvious reading of "the map is now uniformly steep" was that the
mask floor — the mask value away from any massif — was set too high, so
the outskirts got too much of the height field. It is a plausible,
mechanical, wrong explanation. Measured:

| mask floor | mount in one piece | border cells flat |
|---|---|---|
| 0.30 | 22.1% | 0.0% |
| 0.22 | 26.4% | 0.6% |
| 0.16 | 27.6% | 2.3% |
| 0.10 | 28.3% | 13.8% |

Six points of traversability for the entire re-introduction of the
island. The actual cause was never in the mask at all: the world carried
**2355 m of relief across 8064 m**, which is Himalayan, and no
arrangement of that much rock is rideable. Relief 0.92 -> 0.62 moved
mount-in-one-piece 22.1% -> 92.1%.

**The rule: sweep the parameter you believe in FIRST, and let it fail
cheaply, but do not stop at one parameter when the sweep comes back
flat.** A lever that produces a small monotone response to a large input
change is usually not the lever — that shape is the signature of a
second-order effect, and reading it as "needs more of the same" is how
a wrong parameter gets pushed to an extreme.

### 21.3 A threshold chosen before the data conflated two different things
`composition()` shipped with a NOTE firing on `edge_ratio < 0.5`. The
first replacement mask scored 0.0% flat everywhere at an edge ratio of
0.615, and a later variant scored 0.0% flat at 0.447 and got called an
ISLAND by its own gate — while being terrain to all four edges.

The two are separable and I had assumed they were the same thing. A low
edge ratio says the outskirts are GENTLER than the peaks, which is what
foothills are. The island's defect was that its border was DEAD: 82.9%
of border cells under 20 m of relief. The gate now keys on
`border_flat_frac`, with the ratio kept as context.

**Moving a threshold after seeing the data it judges is exactly how a
gate gets quietly tuned into agreement with its author**, so the change
is recorded here, in the docstring, and in the commit — with the reason
it is a correction of a conflated definition rather than a relaxation.
The test that makes it defensible: the new gate still fires on the OLD
terrain (82.9% >> 20%), which is the case it exists for. A threshold
change that stops flagging the original defect would have been a
retreat.

### 21.4 A hard max between two smooth fields is a visible seam
The first mask combined massifs and ridge corridors with `np.maximum`.
Both inputs are smooth; the combination is not — `max` is
C0-discontinuous where the arguments cross, and a hillshade differentiates,
so the corridors surfaced through the massifs as **lens-shaped blades
with a hard rim**, unmistakably artificial from altitude. Neither obvious
alternative works either: summing saturates the middle of the map into
one blob, which is the island in a new shape.

Fixed with a p-norm soft maximum, `(sum f^p)^(1/p)` at p = 6, which
tracks the max within a few percent where one component dominates and
rounds the seam where they meet.

**Caught by a preview that cost two seconds, before three minutes of
erosion and any editor contact** (section 19.2 again). The preview is
now the first thing run after any mask change.

### 21.5 An O(1) search written as an O(n) search, 12800 times
The band tuner grid-searched snowline x rock-slope x snow-slope with a
full pass over 4.1 M cells per candidate. It had to be killed. Replaced
with a 2-D (slope, height) histogram and an integral image, making each
candidate a four-lookup rectangle sum; the same search then ran in under
a second.

Minor next to the rest, but worth the line: **when a search is over
thresholds on two quantities, the histogram of those quantities is the
search space, not the array.**

### 21.6 The tuned number and the rendered number were 5.5 points apart
The band search said Snow 22.05%. The bake said **27.58%**, because
`make_landscape_material` feathers the height bound OUTWARD by
`(1 - blend_sharpness) * 0.06 * z_scale_m` = 115 m, which the hard-bound
search did not model. Tuning was redone against the bake, which is what
actually renders.

Same shape as section 10.4 (an instrument using different constants from
the thing it measures) but a degree milder: the tuner was never wrong
about what it computed, it was answering a slightly different question
than the one that mattered. **Tune against the artefact that ships, not
against a model of it** — and note that the feather is a fraction of
`z_scale_cm`, not of the world's actual relief, so shortening the world
by 33% widened every blend in relative terms without anything changing.

## 22. What worked

### 22.1 An exact sweep from one artefact, then checked against a real run
`--relief` is applied on the generator's last line, after every erosion
stage, so it is a pure vertical rescale of a fixed shape. That means a
nine-point sweep needed ONE generated terrain and some arithmetic, not
nine three-minute runs.

That is a reading of one line of code, and this repo's most expensive
mistakes are all confident readings (sections 2.1, 18.2, 18.3). So the
chosen value was regenerated for real and compared: walk 90.5 / 99.7,
mount 72.9 / 92.1, border flat 1.3% — identical to the analytic row.

**An inference that saves an hour is worth one run to falsify.**

### 22.2 Exit 5 meant UNKNOWN, and UNKNOWN was resolved by a different
### instrument
The push returned exit 5 with a JSON deserialisation failure: the
response was too large for the transport. The exit-code contract calls
that *"the push ran but verification FAILED or could not be
completed — terrain state UNKNOWN"*, which is precisely correct and
precisely unhelpful on its own.

The state was then settled read-only, by the thing that had no stake in
the answer: a dry run's export read-back reported identity orientation at
**median |dv| 0.000 units** over 1280 vertices, all five blocks 256/256
within tolerance. The write had landed; only the report was lost.

**A transport that loses the answer has not lost the fact.** Conduct
rule 6 says stop after two consecutive failures — this was one, and the
correct response to one was to measure the world rather than to retry
against it.

### 22.3 An adversarial review found the thing the change actually broke
A read-only review fanned out over four lenses — downstream breakage,
mask correctness, metric integrity, repo-rule conformance — with every
finding then handed to a separate agent told to REFUTE it. 24 raised,
**17 refuted, 7 survived**, and the refutations were as valuable as the
survivors: several were plausible, well-argued and rested on baselines
that did not exist.

The top survivor is the shape worth remembering. `--relief` shortened the
world by 33%, and `snowline_detail`'s camera is a CONSTANT at world Z
1900 m with pitch exactly 0. The world's new ceiling is 1587 m, so the
camera ended up **313 m above the highest ground in the map, aimed at the
horizon**. Its capture is 98% sky.

Three things make this worth its own entry:
- **Nothing would have caught it.** `capture.py:367` `_footprint_errors`
  checks camera X and Y against the landscape footprint and never reads
  `loc[2]`. A camera above the entire world passes validation.
- **It would have been misdiagnosed.** An empty pale frame reads as a fog
  or exposure failure — and this repo has already burned two full
  capture cycles on exactly that confusion (sections 14.6, 12.8). The
  fog IS also mis-scaled by the same change, which would have made the
  wrong explanation fit.
- **It was predicted, then confirmed.** A raymarch of the heightfield
  said terrain fill would go 37.4% -> 2.1%; the render came back at
  visibly ~2%. The verifier also corrected its own reviewer's numbers
  (the reviewer's "84%" before-figure did not reproduce) — which is the
  refutation step doing precisely its job.

**The general rule: a change to a global scale invalidates every
CONSTANT expressed in that scale, and the ones that hurt are in files the
change never touched.** Grep for the units, not for the feature.

### 21.9 A spectral test that found the DESIGN and called it the defect
The terrain carried a rectangular lattice of bright ridge lines, visible
in the engine's render and in a local hillshade. Two wrong turns before
the cause, and both are instructive.

**Wrong turn one: I measured frequency when the question was
orientation.** An FFT of the heightmap's high-pass returned dominant
periods of 672, 155, 78 and 36 px, against value-noise octave lattices
at 672.3, 160.0, 78.0 and 38.1 px. That looked like a smoking gun and I
reported it as one. It is not: **a nine-octave fBm has power at its
octave frequencies by construction.** I had measured the design.

The question was never "is there power at 78 px" — it is "is that power
concentrated along the AXES". The right instrument is the 2-D power
spectrum binned by ANGLE, and the statistic is the ratio of mean power
in wedges around 0/90 degrees to wedges around 45/135. It reads 1.0 for
an isotropic field. The old terrain read **2.015**.

**Wrong turn two: I fixed the thing I had a story for.** Smoothstep is
C1 but not C2, its second derivative jumps at every lattice boundary,
shading is a derivative, and Perlin replaced smoothstep with a quintic
in Improved Noise for exactly this reason. Compelling, well-sourced, and
wrong here: the quintic measured **2.552 — worse.** A fade curve governs
SMOOTHNESS at a boundary. It cannot change the boundary's ORIENTATION.

**The actual mechanism** is the ridge fold. `_ridged_fbm` folds each
octave as `1 - |2v - 1|`, creasing wherever v crosses 0.5, and in
SEPARABLE value noise those level sets run along lattice rows and
columns. The fold converts a mild axis alignment into sharp bright
ridges, and because every octave shared the same axes, nine octaves
stacked into a grid. Sampling each octave through its own random
rotation took the ratio to **0.549**, and the high-pass crop went from
rectangular boxes to organic branching networks.

**Three rules fall out:**
1. **Look at the pixels before running a statistic.** A high-pass crop
   showed the grid in seconds and would have killed both wrong turns
   immediately. Section 7.2 has said "inspect the artefact" since the
   first milestone; I reached for a spectrum because it felt more
   rigorous, and it was less.
2. **Check what your measurement would say about a CORRECT artefact.**
   The FFT test had no failing case — a healthy fBm produces exactly
   the peaks I treated as evidence. A test that cannot come back clean
   is not a test (§2.11, in a new costume).
3. **A mechanism you can explain is not a mechanism you have
   demonstrated.** The smoothstep story was true about smoothstep and
   irrelevant to this defect. The A/B is what separated them, and it
   cost one run.

**Note the ratio overshot to 0.549**, i.e. power now leans slightly
diagonal, because nine fixed random angles do not average to isotropy.
Recorded rather than tuned away: a faint bias at a seed-dependent angle
is categorically better than one aligned to the map axes, which is the
one orientation a player reads as artificial.

### 21.10 Three failed close-ups before the view nothing can occlude
86,626 foliage instances were placed and COUNTED in the world, and the
capture showed essentially nothing. The count proves existence; it says
nothing about whether anything draws them. Diagnosis took four
viewpoints and only the last was decisive.

1. **The wide shot.** Nothing visible. Inconclusive — sparse small
   objects at kilometre range are legitimately invisible.
2. **Scaled the meshes up** (placeholders are 1 m; a conifer is 8-22 m)
   and re-shot. Still nothing. **I should have done this arithmetic
   first**: at 65 deg over 1920 px, one pixel subtends 0.00066 rad, so a
   1 m object at 1 km is under two pixels. Section 11.3 says compute
   what the result will look like at the size it will be seen, and I
   placed 66k instances before doing it.
3. **A close-up 127 m from a known instance** — which came back looking
   at the UNDERSIDE of the terrain, because I picked the camera position
   without checking the ground height there. `frame_cameras.propose`
   does exactly that check and I bypassed it to move quickly.
4. **A second close-up**, this time clear of the ground — and the target
   was hidden behind a foreground ridge. Clearance from local ground is
   not line of sight.
5. **Straight down over the densest cluster.** Instances and their long
   12-degree-sun shadows, unmistakable. **A top-down cannot be occluded
   and cannot be underground**, which is why it should have been the
   FIRST diagnostic rather than the fifth.

**The rule: when an object is missing from a render, choose the view
that has no failure modes of its own before choosing a flattering one.**
Every intermediate attempt could fail for a reason unrelated to the
question, and each one that did cost a capture cycle and taught nothing.

Two smaller things fell out. The footprint gate refused one of my
throwaway cameras for being outside the map — a gate written for a real
incident catching a careless experiment months later, which is what
gates are for. And the honest conclusion is not "foliage works": it is
that **the instance budget on this hardware cannot make scattered
per-instance meshes read as forest at 8 km**. 34/ha is 86k instances and
100/ha would breach the 250k ceiling. Density is not the lever; the
landscape grass system, or fewer and much larger meshes, is.

### 21.8 The scratch asset nobody cleaned up was doing real work
`/Game/Debug/T_PushHeight_Source` is the staging texture
`push_heightmap` imports the PNG into before drawing it to a render
target. It is ~65 MB of RGBA32F, it duplicates a 7 MB file already in
the repo, it is re-imported on every run, and it sits DIRTY in the
editor afterwards — one "Save All" away from the repository. Deleting it
after a successful push looked like unambiguous tidying.

**It broke the next push.** Deleting it forces a re-import, and a
freshly imported texture is not streamed in yet. Two consecutive runs
after the delete reported `resident mip [2017, 2017]` and
`resident mip [32, 32]`. On the second, the material sampled a 32x32 mip
and `draw_material_to_render_target` produced a FLAT render target
(min 0.500, max 0.500) — refused at stage `verify_rt`, nothing imported.

So the texture surviving between runs was **load-bearing for mip
residency**, and nothing anywhere said so. It read as leftover litter
and was actually the thing making the draw deterministic. This is
section 10.3 from a new direction: the engine answering "how much of
this is in memory" while the caller needs "how big this is" — except
here nobody was even asking, the residency was just quietly inherited
from the previous run.

Two things went right and are worth as much as the finding:
- **The `verify_rt` gate caught it.** A flat render target is exactly
  what a still-streaming texture draws, and that gate exists because
  a flat landscape is a perfectly valid landscape. It refused BEFORE
  the import, so the terrain was never touched — confirmed by a
  read-back afterwards at median 0.000 units.
- **The cleanup could not corrupt the verdict.** It was placed after
  the import and never reassigned `_out["ok"]`, so the run that failed
  its delete still reported the push honestly as succeeded.

**The rule: before removing something that looks like litter, ask what
it is doing while it sits there.** An artefact's value is not only what
it contains; being ALREADY LOADED is a state that costs nothing to keep
and is expensive to rebuild. The tidier version of a system is not
automatically the better one.

**And the corollary that decided it:** the actual problem — 65 MB one
click from the repo — was already solved by a `.gitignore` line that
cannot introduce a race into the terrain write path. Given two fixes for
the same footgun, prefer the one that cannot fail in the critical path
over the one that is conceptually cleaner. The delete was reverted and
the code now carries a DO-NOT-RE-ADD comment with this reasoning,
because it will look like obvious tidying again to the next reader.

### 21.7 I batched two changes into one capture and lost the attribution
The fog rescale and the camera altitude corrections went into the SAME
capture cycle. Three of the four cameras therefore moved AND had their
atmosphere changed, so the contrast measurements across those frames
cannot be attributed to either change:

| camera | contrast (std) | note |
|---|---|---|
| ridge_wide | 0.1194 -> 0.1139 | camera moved 352 m, confounded |
| diag_oblique | 0.1175 -> 0.1215 | camera moved 263 m, confounded |
| snowline_detail | 0.1039 -> 0.0957 | was 98% sky; different image entirely |
| **diag_topdown** | **0.1634 -> 0.1648** | **did not move — clean** |

The one camera that held still says the fog rescale changed it by
**+0.8%, which is nothing.** That is a legitimate result and it is the
only one I am entitled to: the datum and half-height govern how much fog
sits in a HORIZONTAL sight line, and a top-down at 9 km has none. The
frames where it should matter are exactly the frames I confounded.

This is section 12.7/12.8 in a new costume — "when several instruments
disagree, enumerate every way they differ" — except this time the
confound was not pre-existing, **I introduced it.** The fog change was
justified by its own arithmetic (relative density at the terrain p90
going 0.117 -> 0.035, restoring the tuned relationship) and that
justification stands on its own. But an image-level claim for it cannot
be made from this capture set, and saying so is cheaper than a claim
that later turns out to be unsupported.

**The rule: when a capture cycle is the measurement, change one thing
per cycle.** Captures are ~2 minutes. Attribution is worth far more than
the minute saved by batching, and the temptation to batch is strongest
exactly when several fixes are ready at once.

---

# Session 7 — the vendor files were lying about their own dimensions (2026-08-02)

Ryan supplied real terrain, foliage and grass assets and asked for them
to be reverse-engineered into the pipeline. The assets went in. What came
out of the exercise was worth more than the assets: three defects, all of
the silent-wrong class, none of which any check in the project would have
caught, and all three inherited from believing a file about itself.

## 23. New failure modes

### 23.1 The pivot was twelve metres from the tree, and every gate was green
`import_static_mesh.py` imported `fir_tree_01_c_LOD0`, verified the
triangle count, the LOD count, the Nanite state and all four material
slots by read-back, and reported success. `place_foliage.py` then placed
28,302 instances and verified the world count matched the plan exactly.
Both were right about what they measured.

Neither measured the PIVOT. The vendor FBX lays its three trees side by
side for the product shot, so `fir_tree_01_c_LOD0` sits at x = 9.25 m in
its own file, and UE bakes that into the StaticMesh: measured on the live
editor, `get_bounds().origin` was **12.406 m** from the geometry.

What that does, none of it observable from any number the pipeline was
already printing:

  * every instance is displaced 12.41 m from the point the placement
    script computed, so the slope and height masks that decided WHERE a
    tree may grow were evaluated at one place and the tree appeared at
    another — on a 30-degree face, 6 m of altitude,
  * random yaw sweeps the geometry around a 12.41 m radius CIRCLE
    instead of spinning it about its trunk,
  * `align_to_normal` tilts about that far-away pivot, levering trees
    into or out of the ground,
  * and for GPU grass there is NO correction available at any level.
    `GrassVariety` has no pivot offset, so the density mask and the
    visible grass simply disagree, forever.

**Rule: an asset's pivot is a property you must MEASURE, not one you may
assume the exporter got right.** The importer now reads `get_bounds()`
back off every mesh and reports the offset unconditionally, and FAILS if
a mesh imported from a normalised source is still more than 1 m out.

Note also what could NOT fix it. `FbxStaticMeshImportData.import_translation`
looks exactly like the answer and is not: one FBX yields ALL of its
objects in a single import and the property is per-IMPORT, so it applies
the same offset to every object, and each object needs a different one.
The fix had to happen before the file reached UE.

### 23.2 The vendor published a real number that answered a different question
`Free/manifest.json` carried `mesh_extent_m: 7.3` for `grass_medium_01`,
source `vendor`, transcribed from the publisher's own listing. It is
correct. It is the width of the WHOLE SET laid out in a row.

The largest single tuft is **0.327 m**. As a footprint the vendor value
is wrong by a factor of 22, in the direction that makes everything
derived from it invisible — and that is exactly what happened. The recipe
carried `scale_range: [0.05, 0.11]` against a 0.147 m mesh, producing
grass **0.7 to 1.6 cm tall**. Nothing errored. Nothing looked wrong in
any report. The grass was simply not there, and the captures that would
have shown it were all long-range.

This retires the assumption behind proposal open question 6 ("how does an
assumed footprint get promoted to a calibrated one"). The answer is not
"visually tune it until it looks right". The answer is that **`vendor` does
not outrank `measured`, because a published dimension answers whatever
question the publisher was asking.** `measured` now wins outright and the
vendor value is DROPPED, not averaged with.

Corollary to §7.2 (inspect every external artefact before it goes
downstream): inspecting the artefact means measuring the thing you are
about to USE it as, not reading what someone said about it.

### 23.3 Every long-range camera agreed the scene was fine
Five capture cameras. All of them 1–9 km out. Trees at 4.4/ha and grass
tufts at 0.15 m are sub-pixel at that range, so for the entire foliage
milestone the captures were *incapable of showing* whether foliage
existed — and they came back looking good, because the terrain and
lighting they COULD resolve were good.

**Rule: a capture set must contain at least one camera at the scale of
the smallest thing being verified.** A review loop whose instrument
cannot resolve the subject is not a weak review loop, it is a review loop
that reports success by construction.

The `forest_floor` camera that now exists took three attempts, and the
first two failures are the lesson:

  1. Derived its Z from a TREE's Z 55 m away. Tree Z is the terrain
     height AT THE TREE; the ground under the camera was 200 m lower.
     Result: a vista, no foliage.
  2. Derived from the ground under the camera, correctly, and landed
     inside a canopy — 28,302 trees over 6503 ha averages 48 m apart, and
     "45 m from a chosen tree" says nothing about the nearest OTHER tree.

The working derivation constrains three things at once — standing on
grass-weighted ground, no trunk within 18 m, many trunks between 30 and
250 m — because optimising them one at a time is what produced the first
two failures.

### 23.4 A deleted species kept its instances forever
`InstancedFoliageActor.remove_all_instances(world, type)` clears only the
type it is HANDED. A species removed from the recipe is never handed to
it, so its instances survive every subsequent run: 28,302 planned against
**70,923** in the world, the difference being `FT_Scrub` and `FT_Boulder`
from a recipe that no longer mentions them.

Hard rule 3 says re-running a recipe rebuilds deterministically. It was
not, and the only reason it was caught is that `place_foliage` verifies
the world count against the plan rather than reporting what it added.

**Rule: an idempotent rebuild must clear by ENUMERATING what is there,
not by iterating what it is about to write.** The two sets are equal only
until something is deleted.

### 23.5 Three sampler-type mismatches, one root cause
Importing real surfaces produced three material-compiler errors in a row:
`LINEAR_COLOR` used for an sRGB albedo (needs `COLOR`), a `TC_Masks`
roughness sampled as the wrong type, and `TC_Alpha`. Each was a separate
line, and each was the same mistake: the sampler type in the material
must match the COMPRESSION SETTING the texture was imported with, and the
two are set in different files by different scripts.

The compiler named all three, which is the good case. The bad case is the
one that does not error — see §23.6.

### 23.6 Real albedo has no mean-0.5 datum
The synthetic layer textures were generated around a mean of 0.5, and the
material compensated with a gain of 4. A photographed albedo map is
already the surface's reflectance. Applying the same gain to it does not
error, does not warn, and produces a blown-out surface that reads as
"the lighting is too bright" — which is how it was nearly fixed, by
lowering exposure, which would have darkened the correctly-exposed sky to
hide an incorrectly-gained ground.

**Rule: when a value's DATUM changes, every correction derived from the
old datum is now a defect, not a setting.** Ask what the number is
relative to before touching what it is multiplied by.

### 23.7 A mean over an alpha-cut texture measures the background
"Are the fir needles green?" The twig albedo averaged over the WHOLE map
is RGB [88.2, 93.1, 52.5] — green above red, so: green. Averaged only
over the texels the alpha actually keeps (23.6% coverage) it is
[85.3, 81.3, 49.3] — green 3.9 BELOW red. Olive.

The whole-map answer is not approximate, it is measuring a different
thing: 76% of that texture is the dead background the alpha cuts away,
and its colour is an artefact of however the vendor filled it.

**Rule: any statistic over a masked texture must be taken under the
mask.** Same shape as §14.5 and §1.9 — the instrument agreed with the
question it was asked, and the question was wrong.

Swept the class immediately (§2.8): `grass_medium_01` reads
[36.2, 36.9, 17.7] under its mask against [15.5, 15.8, 7.6] over the
whole map, a factor of 2.3 in brightness. Any exposure or tint decision
taken from the whole-map figure would have been two stops out.

### 23.8 I bumped a version field the validator pins
`recipes/alpine.json` got `schema_version: "1.10"` "for traceability".
`_validate_recipe` requires exactly `1`, so the recipe stopped
validating — caught by running the validator over it, not by anything
noticing at authoring time.

The mistake underneath is conflating two facts. The version of the
SCHEMA lives in `recipes/schema.md` and moves with every revision; a
recipe's `schema_version` states which schema GENERATION it targets and
moves only on a breaking change. v1.7 through v1.10 are all additive.

**Rule: before changing a field a validator pins, run the validator.**
It costs one command and it is the whole reason the validator exists.

### 23.9 I reported a measurement that had measured nothing (caught, not shipped)
Trying to check whether the rendered conifer matched its predicted 467 px,
I isolated "tree pixels" by contrast against a reference column of sky.
The reference column contained cloud and hillside. The method returned
rows 0 to 759 — the entire usable frame — and I nearly wrote "759 px
against a predicted 467" into the handoff as a discrepancy.

It is not a discrepancy. It is the instrument reporting its own
background. Exactly §9's shape: a failed measurement is not a negative
result, and it is not a positive one either.

What went into the handoff instead is the prediction, the observation
that the tree looks smaller and sparser than that, and an explicit
statement that **the measurement failed and there is no measured number**.

**Rule: when a measurement fails, the output is "I could not measure
this", never the number the broken measurement produced.** The pull
toward reporting it is strongest when it happens to agree with what you
already suspect — which it did.

### 23.10 A crash-recovery prompt is a question about timestamps, not about trust
Unreal offered to restore from autosave after going down. The prompt
presents itself as "recover your work", which frames declining as
throwing something away. The actual question is which side is newer, and
the prompt does not say.

Here the on-disk packages were 11-32 minutes NEWER than every autosave,
and the autosave files carried the same OFPA hash names as the
InstancedFoliageActor packages — so accepting would have restored 28,302
trees to their pre-pivot-fix positions and silently undone the session's
main fix.

Two traps in reading the timestamps:

  - `Saved/Autosaves/PackageRestoreData.json` is written as the editor
    goes DOWN, so it can be newer than the last real save by a second
    while every autosave it indexes is far older. It is a manifest, not
    content.
  - `Content/<level>.umap` can be days stale and mean nothing under OFPA,
    because the actors live in external packages. Judging freshness by
    the .umap points the wrong way.

**Rule: answer a recovery prompt by comparing
`Content/__ExternalActors__/<level>/` against `Saved/Autosaves/`, never
by which option sounds safer.** "Restore" is not the conservative choice;
it is a write.

### 23.11 An ad-hoc vendor import can clobber recipe-named assets as a SIDE EFFECT
Reasoned, not tested — and deliberately not tested, because the test is
the defect.

Ruling (c) gate 2 refuses to import a vendor source under a name that a
recipe claims. It checks the `--name` TARGET. But UE's FBX importer
creates one StaticMesh per OBJECT in the file, so importing a
multi-object vendor file ad-hoc — the case ruling (c) explicitly leaves
ungated — also creates or overwrites assets named after every OTHER
object in that file, and `replace_existing` is True.

`Free/grass_medium_01_4k.fbx` holds 17 objects, five of which the recipe
names. An import of that file under any scratch name would rebuild all
five with vendor pivots, and gate 2 would not fire, because the name it
was handed was innocent.

Evidence it is real rather than theoretical: `/Game/Meshes` holds all 17
grass variants and all three firs, from imports that only ever named one
object each.

**This is why gates 3 and 4 measure `get_bounds()` at the point of use.**
They are not belt-and-braces for the name checks; they are the only layer
that survives this. A name check upstream of an importer that writes
names it was not given cannot be sufficient.

**Rule: when an operation writes more than the thing you named, a gate on
the name you gave it is not a gate on what it wrote.**

Not fixed here. The fix is either importing multi-object vendor files
into a quarantine path, or extending gate 2 to enumerate the file's
objects before importing — both are real changes, and inventing one at
the end of a session to close a hazard that the measured gates already
catch is the wrong order.

### 23.12 A wrong fact in a validator does not fail to help — it forbids the fix
This is the most expensive shape found so far, and it took down the GPU.

`place_foliage` set exactly one property on each FoliageType: `mesh`.
Cull distance was therefore whatever the engine constructor left, and
`InstancedFoliage.cpp:602-603` leaves it 0, which `FoliageType.h:292`
documents as "0 disables". So 28,302 instances of a 505,494-triangle
single-LOD mesh were submitted every frame across an 8 km map — 14.3
BILLION triangles — until the frame missed the Windows TDR deadline and
D3D12 returned `DXGI_ERROR_DEVICE_HUNG`. Not memory: 3998 MB of an
8283 MB budget was in use.

That alone is a hard rule 2 break of the ordinary kind: a scene parameter
that came from nowhere. What makes it worth its own section is the
second half.

The recipe validator carried this rule, which I wrote:

> `cull_distance_m` applies only to `system='grass'`; instanced species
> are not view-culled by the foliage type

It is exactly backwards. `FoliageType::CullDistance` IS the instanced
cull distance (`FoliageType.h:296` → `InstancedFoliage.cpp:224`
`SetCullDistances`). GRASS is the one that uses a different field —
`GrassVariety`'s own `start_cull_distance`/`end_cull_distance`.

So the validator did not merely miss the problem. **It rejected the only
key that would have prevented it.** Anyone who had reached for
`cull_distance_m` on the Conifer — the correct instinct, the correct key,
the correct value — would have been told by the pipeline that they were
wrong, in a confident sentence with a rationale attached.

**Rule: a validator encodes beliefs, and a wrong belief in a validator is
worse than no validator, because it converts a correct action into a
refusal.** Every restriction of the form "X applies only to Y" is a claim
about the engine and needs a source line beside it, exactly like a value
does. §2.1 said read the source before trusting a NAME; this extends it:
read the source before writing a RULE.

The tell was available and I did not look for it. The grass path in
`make_landscape_material` sets `start_cull_distance` and
`end_cull_distance` on a `GrassVariety`; the instanced path sets nothing.
Two mechanisms, one with a cull distance and one without, and I explained
the asymmetry to myself instead of checking it.

### 23.13 The safe harbour had its own failure mode
To repair a FoliageType whose asset-on-disk was what hung the GPU, I
started the editor on `/Engine/Maps/Templates/OpenWorld` via the command
line so it never rendered the uncullable scene. That part worked: the
repair ran with no level loaded, read back `[0, 0] -> [22500, 30000]`,
and persisted to disk at 11:35:15.

Then loading `/Game/Alpine` from that template asserted:

    EditorServer.cpp:1951
    World Memory Leaks: 1 leaks objects and packages

— a scripted `LevelEditorSubsystem.LoadLevel` failing to tear the
template world down. Nothing to do with the GPU, the foliage, or the
thing being fixed.

The recovery was to relaunch DIRECTLY onto `/Game/Alpine`, which needs no
transition at all and gets the repaired asset from the first frame. Which
raises the obvious question: why stage through a template rather than
launch onto the target once the asset was fixed? Because the asset could
not be fixed until the editor was up, and the editor could not come up on
Alpine without rendering the thing that hung it. The staging was
necessary; only the second HOP was avoidable.

**Rule: a workaround that adds a state transition adds that transition's
failure modes.** The correct shape here is: stage in, do the minimum,
then RESTART onto the target — not stage in, fix, and transition. A
process restart is cheaper and far more predictable than a live world
teardown, and it was available the whole time.

Also worth keeping: `open_level.py` refused the transition first, because
the template counted as an unsaved world and discarding it needed
`--discard`. That guard was written for a different scenario entirely and
was correct here too — the refusal was the last clean checkpoint before
the assert.

### 23.14 The catastrophic input was made inexpressible, not rejected
`FStaticMeshReductionOptions::ReductionSettings[0]` **is LOD 0**
(`StaticMeshEditorSubsystem.cpp:400-402`, which literally comments
`// Set up LOD 0`). So the obvious recipe shape — a list of the LODs you
want below the source, `[0.25, 0.06, 0.015]` — does not mean that at all.
It means *decimate the source mesh to a quarter, then add two levels
below it*. The 505,494-triangle asset would have been permanently reduced
to 126k, every future LOD chain would have been built from the damaged
base, and the run would have printed success.

The obvious defence is a validator rule: refuse `percent_triangles == 1.0`
at index 0. That works and it is not what was built.

Instead the recipe describes LOD1..N only and the script prepends LOD 0
at 1.0 itself. There is no key, no index, no value a recipe author can
write that decimates LOD 0 — the dangerous state is not reachable from
the input language. The validator rules exist too (strictly between 0 and
1, strictly decreasing), but they are guarding ordinary mistakes, not the
catastrophic one.

**Rule: when an API has an index whose meaning is easy to get backwards,
do not accept the index from the caller.** A gate that rejects a bad
value is good; an input that cannot represent the bad value is better,
because the gate is a thing that can be wrong and the absence of an
expressible state is not.

Belt and braces anyway, because this project has been wrong about its own
guards before: the read-back asserts LOD 0's triangle count is *identical*
before and after, not merely close. And verification is by PER-LEVEL
TRIANGLE COUNT, never by `get_num_lods()` — four identical LODs would
satisfy a count check and change nothing about the frame cost.

### 23.15 Two reflected-API orderings, both wrong, both caught only by read-back
Chasing the grass, two calls did something other than what they read as,
and in both cases the ONLY thing that revealed it was reading the value
back afterwards.

**`unreal.Rotator` takes (ROLL, PITCH, YAW).** The recipe stores
`rotation_deg` as `[pitch, yaw, roll]`, and passing that tuple straight
into the constructor put the editor viewport at **pitch 135** — aimed at
the sky — while reporting nothing wrong. The read-back printed
`pitch 135, yaw 0, roll 3.05` against a requested `[3.05, 135.0, 0.0]`
and the transposition was obvious. Without it I would have concluded
"still no grass" from a camera pointed at the clouds.

**`delete_material_expression` returns something falsy while succeeding.**
The cleanup reported `deleted: 0` and `grass_nodes_after: 0` in the same
breath. Trusting the return value would have said the deletion failed;
trusting the read-back said it worked, and the recompile agreed. A return
value is a claim; the state is the fact.

Both are the §6.1 shape — the reflected surface is the contract, not the
name and not the docstring — and both are why every mutation in this
project reads its own result back rather than trusting that the call
returned.

### 23.16 `delete_all_material_expressions` does not delete all material expressions
`make_landscape_material` calls it before every rebuild, on the
assumption that the graph is then empty. It is not: custom-output nodes
(`MaterialExpressionCustomOutput` subclasses, of which
`LandscapeGrassOutput` is one) survive it.

The consequence was invisible until a saved intermediate state exposed
it: the rebuild added a SECOND grass node beside the surviving one and
the material stopped compiling with "The material can contain only one
Landscape Grass node". Every previous run had been leaving the old node
and adding a new one too — it simply had not accumulated past the limit
in a single session before.

**Rule: a clear-then-rebuild is only idempotent if the clear is total,
and "delete_all_X" is a name, not a guarantee.** Verify emptiness after
clearing, not just that the clear was called.

**Now fixed**, and the scale of what it had been leaving behind is the
part worth recording. After deleting the survivors explicitly and
rebuilding, `M_AutoLandscape` went from **158 expressions to 80**. Nearly
half the graph was orphaned debris accumulated across earlier rebuilds —
nodes connected to nothing, invisible in every report, and silently
compiled into the material on every run. The material had "compiled
clean" throughout.

A rebuild that leaves half the previous build in place is not a rebuild,
and hard rule 3 says re-running a recipe rebuilds deterministically. It
did not. `make_landscape_material` now deletes every surviving
expression after the built-in clear and records the residual count, so
"the graph was empty before I started" is measured rather than assumed.

### 23.17 GrassVariety has TWO density fields and I set the one nobody reads
`FGrassVariety` carries both `GrassDensity` (FPerPlatformFloat) and
`GrassDensityQuality` (FPerQualityLevelFloat), and likewise
`StartCullDistance`/`StartCullDistanceQuality` and
`EndCullDistance`/`EndCullDistanceQuality`. Which pair the engine reads
is a runtime switch:

    LandscapeGrass.cpp:1542
      float FGrassVariety::GetDensity() const
      {
          if (IsGrassQualityLevelEnable())
              return GrassDensityQuality.GetValue(GGrassQualityLevel);
          else
              return GrassDensity.GetValue();
      }

    :1513  IsGrassQualityLevelEnable() -> GEngine->UseGrassVarityPerQualityLevels
    :204   GGrassQualityLevel is r.grass.DensityQualityLevel, default -1

`make_landscape_material` sets `grass_density`, `start_cull_distance` and
`end_cull_distance` — every one of them the NON-quality field. The
read-back this project insists on read those same fields back and
confirmed them, so the verification agreed with the setter and neither
was looking at what the engine consumes. **A read-back only proves the
value landed where you put it. It cannot tell you the engine reads
somewhere else.**

Measured on this editor: `r.grass.DensityQualityLevel` was **-1**.

**AND IT IS NOT THIS BUG.** Setting the level to 3 (Epic) and flushing
changed the render by 0.007 in near-ground contrast — nothing. Combined
with `unreal.Engine` not being reflected at all (so the switch cannot be
read from Python), the evidence is that
`UseGrassVarityPerQualityLevels` is FALSE here, the non-quality fields
ARE the live ones, and the values I set are the values in force. The
hazard is real and will bite the moment that switch flips; it is not the
cause of the missing grass. Recorded as a trap, not as a diagnosis —
writing it up as the answer because it was a satisfying find would have
been the more expensive mistake.

This is the §6.1 family again — the reflected surface is the contract —
with a sharper edge: the reflected surface offered TWO plausible fields
with nearly identical names, and the one with the obvious name is the
one that is conditionally ignored. Grepping the header for "Density"
would have shown both; I stopped at the first match whose comment said
"Instances per 10 square meters".

**Rule: when a struct exposes two spellings of the same quantity, find
the code that CHOOSES between them before setting either.** The
existence of a second field is itself the warning.

## 24. What worked

### 24.1 Normalisation that re-reads its own output from disk
`scripts/blender/normalize_asset.py` bakes the pivot, exports, and then
**re-imports the exported file and re-measures it**, failing any object
whose re-read base centre is not within 1 mm. All 23 objects came back at
`pivot_error_m: 0.0`.

This matters because a normalisation that quietly did nothing looks
exactly like one that worked. The in-memory numbers are what we intended;
only the file is what UE sees.

And then the UE-side read-back caught the same quantity a third time,
after the FBX round-trip and UE's own import transform — a different
instrument, which is the only kind of confirmation worth having (§15.1).

### 24.2 The auditor caught two allow-list defects I would have shipped
On `save_level.py`:

  * seeding the dependency closure from the LEVEL package would have
    admitted `<level>_BuiltData` and everything else the map references,
    silently reversing a documented skip;
  * my `"/Game/Surfaces/<name>/"` prefix **matched nothing** — the
    importer is flat (`T_<id>_<suffix>`), not foldered.

The second is the more instructive. A prefix that matches nothing fails
in the SAFE direction: the run succeeds, saves slightly less, and reports
no problem. It would have survived indefinitely. **A guard that is
inactive is indistinguishable from a guard that is satisfied unless
something counts what it matched.**

### 24.3 Negative tests on a new validator, before trusting it
The `varieties` validation was written and then attacked with eleven
mutations — NaN share, zero share, negative share, all-zero shares,
non-path mesh, inverted `scale_range`, NaN in `scale_range`, zero minimum,
unknown key, empty list, and the field applied to the wrong `system`. All
eleven refused. A validator that has only ever seen valid input has not
been tested (§1.2), and NaN-passes-range-checks is a defect class this
project has now paid for four times.

### 24.4 One probe answering four questions
"Why is nothing visible" had at least four candidate causes with
different fixes. One read-only probe returned the ground height under the
camera, the instance counts near the camera and near the target, the
foliage type's cull distances, and every grass variety's density and
scale — and the answer (camera far above ground, foliage present and
unculled) was immediate. §15's rule generalises: when attempts are
scarce, spend one read verifying everything.

### 24.5 Looking at the pixels, again
The forest camera "showed no trees". Cropping the near ground and
upscaling it settled in seconds what no amount of reasoning about cull
distances would have: the ground in frame was kilometres away, so the
question was never about foliage at all. Third time this session's family
of problems has been solved by looking instead of computing.

## 25. The one-line version, seventh pass
**A file's own account of itself is a claim, not a measurement.** The
vendor said 7.3 m and meant something else; the FBX said x = 9.25 and UE
believed it; the recipe said scale 0.05 and produced nothing visible. In
all three the number arrived intact and meant the wrong thing, and in all
three the fix was to measure the quantity you are about to depend on,
with an instrument that is not the one that made the claim.

## 17. The one-line version, fourth pass

**Before explaining why something was slow, prove it was running — and put
every refusal on the same side of the operation as the thing it refuses.**

---

## 5. The one-line version

**Read the source before trusting a name; make every gate refuse rather than
guess; and let something other than the author decide whether the work is
ready.**
