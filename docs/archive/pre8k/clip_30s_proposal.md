> # ⛔ SUPERSEDED — describes the pre-8K / pre-kit design. Do not apply.
>
> Quarantined 2026-08-29 by the doc-consolidation unit. **Nothing in this
> file may drive a decision.** It is kept verbatim because this project
> never deletes a record; the content below the banner is byte-identical to
> what it was before the move.
>
> **Why it is dead — and it is a genuinely SUPERSEDED RULING, not a draft.**
> It reads *"STATUS: RATIFIED 2026-08-08 AS THE SEQUENCE OF RECORD"*, and it
> was ratified. It was written *"against the board as it actually stands"*
> on 2026-08-08 — **six days before** the 8K re-terrain replaced its subject.
> `Alpine8K` appears 0 times.
>
> **A ratified sequence does not stop being ratified; it stops being
> APPLICABLE when the world it sequences is replaced.** Recorded that way
> deliberately, so nobody reads the archive as a reversal of your ruling.
>
> *Moved from its original path by `git mv`, so `git log --follow` still
> reaches its whole history.*

---

# THE 30-SECOND CLIP AT AAA TERRAIN QUALITY — SEQUENCED PROPOSAL

**STATUS: RATIFIED 2026-08-08 AS THE SEQUENCE OF RECORD, with the two
[RYAN] systems still UNRATIFIED individually.** Written 2026-08-08
against the board as it actually stands, not as the campaign table
describes it.

**WHAT RYAN RULED, 2026-08-08:**
- **The 5080 desktop is NOT SOON, and the sequence assumes it never
  arrives.** The iGPU is the permanent target for this clip. The offline
  MRQ path is therefore the deliverable, not a fallback — and **1080p is
  the render target**, because 4K quadruples per-frame cost on the one
  machine we have. Re-open only if the hardware answer changes.
- **Execution order: PHASE 0 → 1.5 → 1.2 → 1.1.** This is the reverse of
  how the phases are numbered below, and it is deliberate: 1.5 (Nanite)
  must be settled before 1.1 places cliff geometry, which §1.5 already
  said, and 1.2 (clutter) is the smaller, lower-risk rehearsal of the
  same R12 machinery that 1.1 then uses at scale.
- Items still marked **[RYAN]** — 1.3 imposters, 2.5 RVT, 1.4 meadow
  intake — remain escalation 1 and are NOT ratified by the above.

**CORRECTION, 2026-08-08 — this document's §1.1 blocker was FALSE.** It
asserted cliff/talus placement was blocked on moving the talus threshold
to landform-scale slope. That was fixed 2026-08-03 in `0b6a412b`; the
claim was inherited from a stale CLAUDE.md paragraph without opening
`rock_scatter.py`. §1.1 is corrected in place and CLAUDE.md's item 4 is
struck. **The largest quality gap was never blocked.**

---

# THE STRUCTURAL FACT THAT REORDERS EVERYTHING

**A 30-second clip at AAA quality is an OFFLINE RENDER, and offline
rendering decouples the deliverable from this machine's 12 fps viewport
entirely.**

`MovieRenderPipeline` is enabled in `LandscapeLab.uproject`, as are
`AccumulationDOF` and `CinematicPrestreaming`. Movie Render Queue renders
frame-by-frame with an unbounded time budget: temporal sub-sampling,
Lumen at cinematic quality, full-resolution shadows, and no requirement
that any frame arrive in 16 ms.

**Consequence, and it is the single most useful thing in this document:**
today's GPU findings — clouds at 4.4-8.6%, both stations draw-thread
bound, the viewport at 11-12 fps — are **NOT on the clip's critical
path.** They govern *editing comfort*, not the deliverable. R13's whole
interactive-budget frame is a separate concern from this.

30 s at 24 fps = **720 frames**. At 10-60 s/frame with heavy sampling on
the iGPU that is 2-12 hours: an overnight job, not an impossibility.
MRQ writes each frame as it completes, so a crash costs one frame, not
the run — which matters, because this GPU has hung once.

~~**[RYAN] THE BIGGEST LEVER IS NOT ON THIS LIST: the 5080 desktop.**~~
**ANSWERED 2026-08-08: NOT SOON, AND THE PLAN ASSUMES IT NEVER ARRIVES.**
The iGPU is the permanent target. Nothing in this sequence may be
deferred on the expectation of better hardware, and no look decision may
be validated only on a machine we do not have.

**What that costs, stated plainly rather than absorbed:** Lumen (2.1),
high temporal sample counts (4.1) and any Nanite enablement (1.5) are all
now negotiations against a 2-12 hour overnight render on a GPU that has
hung once — not free choices. The 1-second test render (4.2) stops being
good practice and becomes the only way any of those get priced.

**What it does NOT cost:** the offline path still decouples the
deliverable from the 12 fps viewport. That was the document's central
structural claim and the hardware answer does not touch it.

---

# PHASE 0 — FOUR DECISIONS BEFORE ANY WORK  **[RYAN]**

**STATUS 2026-08-08: 1 of 4 ANSWERED (item 3). Items 1, 2 and 4 are
still open and are the first thing to settle when the clip's camera work
starts at 3.6.** They do NOT block 1.5, 1.2 or 1.1, which are content
that any route through this world needs — that is why the ratified order
starts there rather than waiting on them.

Nothing downstream is safe to start until these are answered, because
each one invalidates different work if it comes back the other way.

1. **What is the clip OF?** A camera path is a *subject* decision before
   it is a technical one. The sweep stations exist to prove terrain
   continuity, not to be beautiful; a 30 s walk needs a route with a
   reveal. Current known-good subject: the modest peak at
   `(-1700, -592) z 549.11`, chosen because it is *visible*, and every
   sweep station clears its sight line by 7.5-15.6 m.
2. **Eye-level walk, or camera move?** "Simulator walking through the
   world" implies 1.7 m eye height with footstep bob. That is a much
   harsher test than a crane shot: it puts near-field ground detail,
   foliage contact and LOD transitions directly in frame for 30 seconds.
3. ~~**Render target: 1080p or 4K?**~~ **ANSWERED 2026-08-08: 1080p.**
   Follows from the hardware ruling — 4K quadruples per-frame cost on a
   machine that is now the permanent target, and it exposes the 4 m
   detail tiling on Rock and Snow that 1080p hides. This is a decision
   made *because* of a constraint, not a preference; re-open it if the
   5080 answer changes.
4. **What does "AAA" mean here — name two reference shots.** Without a
   reference this is unfalsifiable, and this project's whole method is
   built on falsifiable claims. Two stills we agree the clip should sit
   beside is enough.

---

# PHASE 1 — CONTENT THAT IS VISIBLY MISSING

These are not polish. Each is a hole a viewer sees.

## 1.1 Cliff and talus MESHES — specified, never placed  **[Pass 3, half done]**
R12 specifies `cliff` and `talus` roles. **Only 759 hero boulders were
ever placed.** Today, cliffs are texture-only and scree is a material
mask at 1.97% of the Rock layer, judged "an outline, not a cone".
A 30 s eye-level walk past a cliff with no rock geometry reads as a
painted backdrop. **This is the largest single quality gap.**

~~Blocked on: the talus threshold must move to landform-scale slope
first.~~ **NOT BLOCKED — CORRECTED 2026-08-08.** That move landed
2026-08-03 in `0b6a412b`. `rock_scatter.landform_slope()` (:173) removes
cell-scale texture before the gradient is taken, `build_context`
(:673-684) feeds it to `talus_deposit` as `source_slope_deg` while every
other consumer keeps reading the real surface, and
`foliage.rock_scatter.source_smooth_m` is **16.0** in the recipe's shared
block. The measurement that motivated it is in the function's own
docstring: cell-scale ≥50° covers **9.152%** of the map against ~**5.3%**
at 16 m landform scale, so roughly **40% of the cell-scale "cliff" area
is texture rather than landform**. The phantom-rockfall hazard is
already engineered out.

**What 1.1 is actually gated on is 1.5**, per that section's own note:
decide Nanite before placing cliff meshes, because it changes which LOD
chain (if any) those meshes need.

## 1.2 Ground clutter — scoped 2026-08-05, never built  **[Pass 5]**
Small rocks, deadfall, foot-level debris from the measured KiteDemo
palette, through R12's existing machinery. Density ruled
sparse-and-clustered. **At 1.7 m eye height this is the difference
between ground and a texture.** Two palette assets already measured and
admitted: `boulder_small`, `vegetation_debris`.

## 1.3 Tree imposters beyond 730 m  **[RYAN — new system]**
`WORLD_VISION.md:135` already names foliage HLOD/imposters as *"the only
way real forest"* works. Conifer cull is **730 m**. Beyond it the forest
is a tint in the landscape material (`forest_floor`, schema v1.11) and
nothing else. **In a 30 s move with any distant view, forest visibly
ends at a circle around the camera.** This is a system, not a tune.

## 1.4 The meadow surface — Pass 2 delivers 4 of 5  **[RYAN — asset intake]**
No meadow-grass surface exists; the Grass sub-surface is wired as a
declared no-op. Needs a Megascans/Fab intake, which no script here can
do. Also: measured meadow is **0.41% of the world**, ruled unreadable at
both scales, and Ryan already REJECTED the current share — an expansion
proposal is in BACKLOG.

## 1.5 Nanite is DISABLED on 38 of 38 palette meshes
Measured 2026-08-07, zero could-not-reads.

**HALF OF THIS SECTION'S ARGUMENT IS WITHDRAWN, 2026-08-08, ON THE
MEASUREMENT THIS PROJECT ALREADY OWNS.** `Free/_measured/palette_live.json`
records `triangles` for all 38 (the field the pass audit confirmed
agrees on **38 of 38** — it is the positive control, unlike
`material_slots`). The whole palette is **already low-poly**: largest
`ScotsPine_01` at 60,120, largest rock `Scree_001` at 33,855,
`SM_Cliff01` at 29,154, and the only rock actually placed —
`Medium_Boulder_001` — at **4,136** triangles across 4 LODs
`[4136, 1186, 892, 596]`.

So the claim *"Nanite gives full-density rock silhouettes"* **carries no
content here**: full density already IS 4,136 triangles, and Nanite
cannot add detail an asset never had. Nanite pays for itself on
million-triangle source geometry, which this project does not have and
has not intaken.

**What survives, and it is still worth having:** Nanite removes discrete
LOD transitions, and **LOD popping across a moving camera is the single
worst artefact class in a 30 s shot** — the one defect class no still
frame in this project has ever been able to test (see 3.1). That is the
real case, and it should be argued on its own rather than on a silhouette
benefit that is not there.

**Scope note:** any enablement is **rock only**. The palette's tall
entries are foliage (`ScotsPine_01`, `HillTree_*`, ferns, grass), which
use masked materials — a materially different and more expensive Nanite
path, and not a free win.

## 1.5 RESOLVED — **RULED 2026-08-08: NANITE STAYS OFF. ITEM CLOSED.**

The recommendation in this section is **withdrawn in full**, and not on
cost. It was unbuildable as written, and one `grep` of `RECIPES.md` said
so before any measurement was needed.

**Three independent grounds, each measured, none sharing a source:**

1. **The benefit does not exist.** `Free/_measured/palette_live.json`:
   largest rock 33,855 tris, the only placed rock **4,136**. Nanite adds
   no silhouette an asset never had. *(withdrawn above)*
2. **THE FAB BOUNDARY, AND THIS IS THE DECISIVE ONE.** `git check-ignore`
   over every rock mesh: **17 of 17 are gitignored vendor content**,
   caught by `.gitignore:92` on `LandscapeLab/Content/KiteDemo/`. 0 are
   authorable. `RECIPES.md`'s Fab-boundary rule 2 names *"enabling Nanite
   on a Fab static mesh"* **as its worked example** of an in-place
   modification that is not a committable derivative — the asset
   re-downloads in its original state and the change vanishes, with no
   error. **A quality decision that cannot survive a fresh clone is not a
   quality decision.** Enforced by `scripts/check_fab_boundary.py`.
3. **A standing ruling already existed.** `RECIPES.md` R12 §2c:
   *"Nanite is FALSE on all 13 — measured from the reflected
   `nanite_settings`, definitively, not absent. Pass 3 does not enable
   it."* This section proposed reversing a locked ruling without citing
   it.

**The sanctioned path, if it is ever wanted, is already written** —
express it as a **REPLAYABLE STEP in the recipe**, which is how
`import_static_mesh.py:245` handles it for assets we import
(`foliage.nanite`, schema v1.9 → `build_nanite`, set at import time,
never toggled afterwards). That is strictly better than an in-place edit:
idempotent, and it survives a vendor update.

**WHAT THE ITEM LEAVES BEHIND, AND IT IS REAL.** LOD popping across a
move is still the one defect class no still frame in this project can
test. **Nanite was never the lever for it on this content — the recipe
is.** `lod_depth`, the LOD chain and `cull_distance_m` are all recipe
data we own outright, and R12 already measured the thing that makes
popping likely: `boulder_medium_01`'s vendor LOD screen sizes are
**1.504 / 0.752 / 0.319 / 0.238** against the cost model's assumed
1.0 / 0.5 / 0.21 / 0.088 — **the vendor drops to its deepest LOD much
nearer the camera than assumed.** Re-homed to 1.1, where more rock gets
placed and the question becomes answerable on content that exists.

**Consequence for the ratified order: 1.1 is no longer gated on 1.5.**

---

# PHASE 2 — SHADING AND LOOK

## 2.1 Lumen ON, and validated
Standing config has Lumen **off for editing, on for final renders**
(`RECIPES.md` R7). It has never been validated on this world — the
exposure solve (-1.786 EV), the sun (130,000 lux at 12°) and the
forest-floor tint were all tuned under Lumen-off. **Turning Lumen on
changes every one of those, and the -1.786 will likely need re-solving.**
Do this BEFORE tuning anything else in this phase.

## 2.2 Fog and aerial perspective — applied, rendering, NEVER TUNED
Density 0.0015, start 1500 m, volumetric on, datum 101 m — all live and
matching the recipe, and showing **heavy aerial haze at 8.7 km**. Untuned
fog is the fastest way to make terrain read as flat cardboard at range.

## 2.3 Clouds — re-rule on today's measurement
Measured **+1.78 ms (4.4%) / +6.48 ms (8.6%)**. R13 permits clouds for
offline renders already, conditional on measuring the delta at first
enablement — **that condition is now satisfied for the editor class**,
though R13 correctly notes the RENDER class is a different measurement.
For a 30 s sky-visible clip, clouds are almost certainly worth it.

## 2.4 Triplanar — cost unmeasured, look unjudged
Wiring is proven (262/262 reachable, `T_Rock026_C`/`T_Rock051_C` at 4
connected samples). The render difference is measured (8.3× noise floor).
**Whether it looks right is still a judgement nobody has made**, and its
GPU cost is still blocked on RAM. For an offline render the cost is
nearly irrelevant; the *look* is not.

## 2.5 Runtime Virtual Texture — never built  **[RYAN — allocates GPU memory]**
Pass 2 step 4 lists RVT after macro variation, and it was deferred. RVT
is how placed rock/talus meshes blend into the terrain instead of
intersecting it visibly. **With 1.1 in scope, this stops being optional.**
Flagged: non-negotiable 27 held an earlier RVT design for carrying 20
uncited API names, on a machine that has lost its GPU once. **A design
review is mandatory before any RVT work.**

## 2.6 Macro variation — built, never judged at its own scale
Designed to be judged at 2 km. No frame has ever been assessed for it.

---

# PHASE 3 — MOTION, WHICH NO STILL HAS EVER TESTED

**Every verification this project owns is a STILL FRAME.** A 30 s move
tests a class of defect that 19 static captures cannot see, and this is
where a clip most often falls apart.

## 3.1 LOD popping across the move
Measured at a single transition: +1.4% luma across the 46.3 m LOD0→LOD1
switch, hue unchanged, ruled not-a-defect. **That was one subject, one
distance, standing still.** A walking camera crosses thousands of
transitions. Nanite (1.5) removes this for rock; trees still pop.

## 3.2 Foliage wind — does not exist
157,554 static conifers. In a 30 s shot, perfectly rigid trees read as
plastic. Needs a wind setup on the fir material.

## 3.3 Streaming hitches
World Partition streaming during a moving camera. MRQ's
`CinematicPrestreaming` plugin is enabled and exists precisely for this —
pre-warm the streaming for the whole camera path before rendering.

## 3.4 Temporal artefacts
TSR/TAA ghosting on foliage against sky is the classic failure. Offline
MRQ with high temporal sample counts largely solves it — this is another
argument for the render path over a real-time grab.

## 3.5 Shadow cascade transitions
Sun at 12° means very long shadows and cascades under stress.
45.7% of conifers are in terrain shadow at this sun angle.

## 3.6 Camera path authoring — does not exist
Needs a Level Sequence with the path, an eye-height solve against v2
terrain, and a collision check so the camera never clips ground. The
sweep stations give six known-good, sight-line-cleared positions to
anchor a route to.

---

# PHASE 4 — RENDER PIPELINE

## 4.1 MRQ configuration, as EXACT VALUES in a recipe
Per pipeline rule 2 this is recipe data, not a saved preset: resolution,
frame rate, temporal sample count, spatial samples, warm-up frames,
shutter angle, output format (EXR for grading, PNG for direct).

## 4.2 A ONE-SECOND TEST RENDER FIRST
24 frames before 720. Measures per-frame cost, catches config errors, and
gives a real time estimate. **Non-negotiable: never launch a multi-hour
render on an untested config.**

## 4.3 Thermal and stability plan
This GPU has hung once. A multi-hour render needs `resource_guard`, a
known-free-RAM floor, and the acceptance that MRQ resumes per frame.

## 4.4 Colour grading and DOF
`AccumulationDOF` is enabled — real DOF rather than a post approximation.

---

# PHASE 5 — VERIFICATION OF THE CLIP ITSELF

## 5.1 Frame QC
`verify_frames.py` already refuses a verdict unless every frame is
present, correctly sized and tonally non-trivial. Extend to a sequence:
**no missing frames, no black frames, no sudden luma discontinuity**
(which catches a streaming pop or a shadow flick that the eye may miss
at 24 fps).

## 5.2 Watch it, at full size, more than once
Non-negotiable 10: inspect the artefact before shipping it. The whole
project's history says the eye finds what the statistic cannot, and the
reverse — so do both.

---

# WHAT I WOULD CUT, AND WHY

**The verification debt is NOT on this critical path.** 13 UNPROVEN
recipes, REPLAY BATCH 1, Pass 0's palette verification (0 of 38), the
`spine_aretes` CV bar, the two polished falloff spots — these govern
whether the world is *reproducible*, not whether the clip looks right.

Two exceptions that DO block:
- **The two polished falloff spots** are terrain defects at 16-19°,
  0.082 km² each, and could appear in frame. Fixing them re-composites
  the terrain and invalidates 157,554 conifer + 759 boulder placements —
  a Pass-1-scale event. **Recommend: route the camera away from them.
  They are located, so this is cheap.**
- **Pass 7's close-range cliff evidence** is the same question 1.1
  answers with geometry. It stops being a separate item.

---

# HONEST SHAPE OF THE WORK

**RATIFIED ORDER, 2026-08-08.** Ordered by *what blocks what*, not by
size. The content items run in REVERSE of their section numbering:

    PHASE 0   items 1, 2, 4 still open   [RYAN]  hours, needed by 3.6
    1.5       Nanite: MEASURE, then decide       small, gates 1.1
    1.2       ground clutter                     the rehearsal for 1.1
    1.1       cliff + talus meshes               the bulk, NOT blocked
    2.1       Lumen on + re-solve exposure       medium, gates 2.2-2.6
    1.3       imposters                  [RYAN]  a system, unratified
    2.5       RVT + design review        [RYAN]  a system, GPU risk
    3.6       camera path                        small; needs Phase 0
    3.2/3.3   wind + prestreaming                small-medium
    4.2       1-second test render               hours; prices 2.1 + 1.5
    4/5       full render + QC                   overnight

**The two [RYAN] systems (1.3 imposters, 2.5 RVT) are the difference
between "good terrain clip" and "AAA".** Both are real engineering with
real GPU risk on this hardware, both remain unratified, and both are
Ryan's call, not mine.

~~**And if the 5080 is close…**~~ **It is not.** See the hardware ruling
at the head of this document: every estimate here is an iGPU estimate,
and 4.2 is the only instrument that turns those into real numbers.
