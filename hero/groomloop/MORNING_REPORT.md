# MORNING REPORT — AlpineHero groom vs the hero reference

**Bottom line.** The loop ran end to end: 24 iterations, a working
author→edit→export→gate→UE-import pipeline, and **three ranked candidates that
import into Unreal cleanly at full curve count and correct scale**. The best of
them takes the source from a smooth centre-part bob to a directional layered
shag with a fringe over the brow.

**One caveat, stated precisely because I first stated it too strongly:**
Blender mis-reads a SMALL TAIL of the source `.abc` -- 1.28% degenerate
one-point curves and 1.98% over-long ones. **96.73% of the 94,408 curves read
plausibly.** Both tails are already handled in the pipeline. See §6, which
corrects an earlier draft of itself.

---

## 0. WHERE THE FILES ARE — AND ONE DEVIATION YOU SHOULD KNOW ABOUT

**WORKDIR is `hero/groomloop/` inside the repo, not `Desktop\GroomLoop\`.**

The project's own `guard.py` hook blocks writes outside the repo (standing rule
1 in `CLAUDE.md`) and it fired on the first file I tried to create. I did not
route around a ratified gate with a different tool. The Desktop skeleton and a
source copy exist from before the guard fired; nothing was written there after.
Everything is otherwise exactly as briefed. Move it if you want it there.

    hero/groomloop/
      source/    SC_Hairstyle_Male_11.abc   sha 5dfbf1b4…  NEVER modified
      ref/       hero_reference_front.jpg   sha F62B53FF…  = the repo's declared
                                            appearance target for AlpineHero
      params/    iter_NNN.json              every run's exact parameters
      blends/    iter_NNN.blend
      exports/   iter_NNN.abc               scale 1.0, faithful to source space
                 iter_NNN_ue.abc            scale 100.0, UE-ready  <-- USE THESE
      renders/   iter_NNN_*.png, final/, masks/, SHEET_*.png
      logs/      run_NNN.json, measure_NNN.json, verify_NNN.json, cull_NNN.json
      recon/     recon.json, geometry.json, ops.json, curves_api.json
      scripts/   the whole loop

**Blender 5.2.0 LTS**, Cycles on GPU (3 devices). A full iteration —
edit, export, integrity gate, measure, render — costs **~60 s**.

---

## 1. TOP THREE CANDIDATES

All three are **UE-verified**: exported, culled, imported into a live UE 5.8
editor, and their curve count and bounds read back off the imported asset.

### #1 — `iter_028_ue.abc`  (score 42)  ⬅ THE ONE TO TAKE

    render     renders/final/final028_{front,left,threequarter,back}.png
    params     params/iter_028.json
    export     exports/iter_028_ue.abc   scale 100.0, radius 0.018 UE cm
    cull       94,408 -> 93,198 (exactly the 1,210 degenerates)
    UE import  GroomAsset, 93,198 curves
    metrics    fringe +0.96 cm past the brow | forehead cover 70.3%
               grade 0.487 | tip scatter 0.606
               scalp front 20.8 / left 11.4 / top 36.6 -- mean 22.93%

Against the untouched source's 43.88% mean scalp visibility, this is roughly
half. The fringe reaches the brow with separated pieces, the locks read as
locks, and the face is still readable.

### #2 — `iter_026_ue.abc`  (score 40)

    render     renders/final/final026_*.png     params  params/iter_026.json
    metrics    fringe +0.03 | cover 50.7% | grade 0.523 | scatter 0.585
               scalp front 26.4 / left 19.5 / top 41.2 -- mean 29.03%

The restrained one: same lock structure, much lighter fringe. Take this if #1
reads as too much hair on the forehead.

### #3 — `iter_021_ue.abc`  (score 40)

    render     renders/final/final021_*.png     params  params/iter_021.json
    metrics    fringe +0.34 | cover 61.1% | grade 0.544 | scatter 0.524
               scalp front 24.4 / left 28.5 / top 51.2 -- mean 34.70%

The pre-consult leader, kept because it uses the lat/long lock partition rather
than the index one — a different mechanism, so it fails differently.

### Rejected at the top of the range: `iter_029`

Scored the BEST metrics of the entire run (mean scalp 18.90%, fringe +2.02 cm,
cover 85.3%) **and it is not the pick.** It covers the face. See §7 for why the
metric rewarded that.

**Contact sheets:**
- `renders/FINAL_top3.png` — the three candidates beside the frontal reference.
- `renders/FINAL_021_views.png` — candidate #1 in four views, flanked by BOTH
  references (frontal and rear), so the back of the cut can be judged too.
- `renders/ue/UE_iter021_width_*.png` — a candidate rendered in Unreal. This is
  iteration **021**, shot before 028 became the pick. 028 is verified as an
  imported ASSET in UE (93,198 curves) but was **not** re-rendered there — said
  plainly rather than implied.

---

## 2. WHAT ACTUALLY CHANGED, BASE → BEST

| criterion | base | #1 (021) |
|---|---|---|
| fringe reach past brow | −3.65 cm (bare forehead) | **+0.34 cm** |
| forehead covered | 22.5% | **61.1%** |
| nape/crown length grading | 0.124 | **0.544** |
| scalp visible, front | 50.4% | **24.4%** |
| scalp visible, top | 55.9% | **51.2%** |
| texture breakup (tip scatter) | 0.433 cm | **0.524 cm** |
| silhouette | smooth curtain bob | directional layered shag |

---

## 3. THE FIVE MECHANISMS THAT MATTERED

Full detail in `APPROACHES.md`; each is a mechanism, not a parameter.

1. **Spatial tip-convergent clumping (A2).** The first attempt assigned clumps
   randomly across all 94,408 curves, so every clump centre averaged to the head
   centroid and "clump" meant "pull to the middle" — it rendered as a fuzzy
   ball. Clumps became lat/long patches of nearby roots converging at their
   mean TIP. Frizz → real pieciness in one change.
2. **Fringe recruitment (003).** The source is a centre PART: there is almost no
   hair rooted at the front-centre, so no amount of lengthening builds a fringe.
   The fringe zone had to be widened back over the crown to make the mass
   available.
3. **`fringe_pull_ramp` (004).** Sweeping a whole strand forward uncovers the
   scalp behind its own root. Ramping the pull to `t^2.8` swings only the tip
   and leaves the mid-strand lying on the skull — reach without exposure.
4. **Rigid rotation about the root (A4) — the biggest single win.** Every
   earlier attempt at direction TRANSLATED tips, which drags them off the head.
   Rotation preserves each point's distance from its root. Single variable, it
   improved *every* view at once and beat the untouched source on all three.
   Rotation and translation **fight**; the translation sweep is now zero.
5. **The final stray clamp (020+).** A bound applied before other operations is
   not a bound — UE measured iteration 016 at 114 cm max strand. Re-applied to
   the result, it holds at exactly 24.0 cm.

---

## 4. UE RE-ENTRY CHECKLIST

1. **Enable plugins:** Groom, and the **Alembic Groom Importer**. (Both are
   already enabled in this project — `AlembicHairImporter` is in the
   `.uproject`.)
2. **Import `exports/iter_028_ue.abc`** (candidate #1).
   - **These files are pre-scaled ×100, so DO NOT also apply Convert Scene** —
     you would get a groom 100× too large. If you prefer to import the
     unscaled `iter_021.abc` instead, then Convert Scene must be ON.
   - Measured, so you can check it landed: the imported asset should read
     **93,198 curves** with bounds spanning roughly **z 120 → 176 cm**. If it
     lands at the origin with a ~2 cm extent, the scale did not apply.
   - Rotation needed no correction on import; the groom arrives upright.
3. **HAIR WIDTH IS ALREADY FIXED IN THE EXPORT — do not set it again.**
   This is better than the checklist assumed, and it took a UE render to find
   out. The width attribute is NOT stripped: the source carries a constant
   `radius` of **0.436611** for every point, which at this file's metre scale
   is a 44 cm strand, **and `global_scale` multiplies it too** — so the first
   x100 export produced 43.7 UE units and the groom rendered as giant blocky
   ribbons (`renders/ue/UE_iter021_*.png`, kept as the evidence).
   The `_ue.abc` files now write `radius` explicitly at 0.00018 Blender units,
   which lands as **0.018 UE cm = 0.18 mm** — the width the review renders
   used. Read back and asserted at export time; `logs/cull_*.json` records both
   the written value and the value it becomes in UE.
   **If you re-export from a blend yourself, pass the radius argument** —
   `cull_degenerate.py <blend> <out.abc> <log> 100.0 0.00018` — or you will get
   the ribbons.
4. **Create a fresh Groom Binding** against the MetaHuman head skeletal mesh.
   Note from this project's own history, worth having in hand: for a groom
   authored on a *different* head than the target, an identity binding seats it
   wrong (this pack's grooms land on the jaw); the pack's own binding declares
   `SKM_MH_Groom_Head` as the head it was authored on, and that is the SOURCE
   mesh a transfer needs.
5. **Swap groom + binding on the hair slot in the BP.** Assign BOTH — the
   binding alone is not enough.
6. **Re-enable physics settings manually.**

---

## 5. WHAT SURVIVED THE EXPORT — MEASURED, NOT ASSUMED

The integrity gate re-imports every export in a **fresh Blender process** and
diffs it against what the exporter said it wrote.

| attribute | survives? |
|---|---|
| `position` | yes |
| `radius` (the width carrier) | **yes** |
| `curve_type` (Bézier = 2) | yes |
| `handle_left` / `handle_right` | yes |
| `handle_type_left` / `handle_type_right` | yes |

**`attributes_lost: []` on every run.** Curve drift 0.0%, worst bbox drift
0.0026%.

**Not present in the source at all, so they cannot survive:** `groom_root_uv`,
`groom_group_id`. The file has no root UVs. That is a property of the download,
not of the export path, and it is why UE builds its own guides (9,319 for
93,198 curves) rather than reading a declared guide set.

**Export path chosen: native `bpy.ops.wm.alembic_export`.** The turbocheke
GroomExporter addon IS installed and enabled, but it is a NODE-GRAPH tool — its
operators are `add_export_node` / `add_attribute_node` / `buttonexport`, i.e.
it wants a node tree authored in the UI. The native path is proven in this
project and loses nothing measurable, so it was used. **The addon remains the
obvious first move if root UVs ever need to be authored and exported.**

---

## 6. THE INPUT FIDELITY QUESTION -- AND A CORRECTION TO MY OWN FIRST DRAFT

**I first wrote this section as "Blender is mis-reading the source file" and
called everything downstream "a corrupted read". Then I measured the size of
the bad tail, and that was overstated.** The corrected version:

    curves                                94,408
    degenerate, 1 point                    1,210   1.28%   <- crashes UE
    longer than UE's 26.10 cm max          1,873   1.98%   <- clamped
    in 0.40-0.80 m                             0   0.00%
    over 0.80 m                                1      --
    PLAUSIBLE                                       96.73%

**96.73% of the groom reads fine.** The damage is a 1.3% degenerate tail, a 2%
mildly-over-long tail (26-40 cm, not wild), and exactly one 142 cm outlier.
Blender's own p01-p99 tip band is ~21 cm against UE's 26 cm read of the vendor
file -- those AGREE. The bulk of the geometry is not in question.

**And both tails are already handled**, which is why this is a caveat rather
than a blocker: the degenerates are culled before every export (section 5) and
the over-long tail is bounded by the final clamp at 24 cm.

### The evidence that a tail IS wrong, which still stands

1. **1,210 curves arrive with a single point.** A one-point curve is not a
   hair. UE's builder asserts on them --
   `Assertion failed: CurveNumVertices >= 2, GroomBuilder.cpp:2403` -- and that
   assertion **killed the editor** the first time I imported an unculled
   export.
2. **UE's own translator logged a mechanism** in this project's editor log:
   `Ensure condition failed: GlobalKnotIndex + CurveNumKnots <= NumKnots`,
   `AlembicHairTranslator.cpp:869`. A knot-indexing failure produces exactly
   this shape of damage -- a few curves with too few points, a few with
   inflated extents, and the rest fine.

### The 8,678 sub-millimetre curves: ANSWERED, and they are not damage

`stub_probe.py` asked the three questions length alone cannot answer, and all
three say authored layer rather than parse artefact:

    roots      centroid y -1.4615 against the normal strands' -1.527
               -- rooted 6.5 cm LOWER, i.e. at the nape / neckline
    spread     0.165/0.200/0.186 against 0.209/0.229/0.216 -- concentrated
               there, not scattered over the whole scalp
    index      5,049 runs, mean length 1.72 against 1.10 if placed at random,
               one run of 300 -- generated as batches, the way a DCC writes a
               separate layer
    points     1-4 per curve against the normal strands' 2-9

**That is a vellus / neckline layer**, which grooms routinely carry. **Leave
them.** Only the 1,210 one-point curves inside that population are degenerate,
and those are already culled; the remaining ~7,468 are doing a job.

### What to do about it, now correctly ranked

1. **Nothing, probably.** With the cull and the clamp in place the pipeline
   already produces UE-valid grooms from a 96.7%-good read. This is the
   cheapest correct answer and it is the recommended one.
2. **If exactness matters**, compare an alternative Blender import path's
   strand statistics against UE's `max_curve_length` **26.10** -- that is now a
   known-good number to check against.
3. **Or style in UE instead.** The groom already imports there correctly and
   this project has a working UE-side binding pipeline.

## 6b. TEST ASSETS LEFT IN THE UE PROJECT

Created while proving the pipeline. All are under
`/Game/Characters/AlpineHero/Grooms/` and all are gitignored derived content,
so deleting them is safe and costs nothing.

    GL_iter000, GL_iter016, GL_iter016_ue          scale + cull experiments
    GL_iter020_ue, GL_iter021_ue, GL_iter023_ue    the three candidates
    GL_021_w                                        the width-corrected import
    Hair_v22_gi / BND_Hair_v22gi                    from the earlier session
    Hair_vendorTest / BND_vendorTest                vendor-through-our-builder
    Hair_v22_nostack(_bound) / BND_v22_nostack      no-guide-stack test
    Hair_v22_g1(_bound) / BND_v22_g1                guide density sweep
    Hair_v22_g4(_bound) / BND_v22_g4                     "
    Hair_v22_g20(_bound) / BND_v22_g20                   "
    Hair_Male11_bound / BND_Male11
    Hair_Male11_xfer / BND_Male11_xfer

**Keep `GL_iter021_ue` (or whichever candidate you pick) and delete the rest.**
Nothing was saved into the level, and the hero is on his committed groom.

## 7. HONEST GAPS

- **Length grading topped out at 6/10.** `grade_ratio` reached 0.547 against a
  target above 1.0. The mechanism is provably linear (2.2× → 0.30, 6.0× →
  0.547); the source is a curtain cut whose length lives in the crown. Reaching
  1.0 needs ~11× on the nape, and iteration 022 showed what happens when strand
  lengths are pushed to serve a metric instead of the picture.
- **⚠ THE SCALP METRIC REWARDS COVERING THE FACE, and it caught me out at the
  last iteration.** The proxy head is an ellipsoid with NO FACE, so hair hanging
  over where the face would be counts as "scalp covered". Iteration 029 scored
  the best numbers of the whole run — mean 18.90%, fringe +2.02 cm, cover 85.3%
  — by hiding him. **029 is rejected and 028 is the pick**, on the picture.
  This is the third time in this run that a metric and the render disagreed and
  the render was right; the metric is kept because its DELTAS are informative,
  but it must never be the tie-breaker.
- **The proxy head is an instrument, not anatomy.** There was no head mesh in
  the download, so it is an ellipsoid fitted to the strand roots with a brow
  band and ear markers placed by declared proportion. **Absolute scalp-exposure
  percentages are meaningless** — the ellipsoid pokes through the top even on
  the untouched source (55.9%). Only the deltas are evidence, and they are used
  that way throughout.
- **One geometric metric was built, failed its own test, and was discarded
  rather than tuned.** `scalp_exposed_pct` in `measure.py` reads 0.00% on an
  iteration whose render plainly shows a bald patch — with ~745 points per
  lat/long cell a "fewer than 3 points" threshold can never fire. It is
  **marked UNRELIABLE and left in place, unused**, and replaced by the mask
  render. Do not read it.
- **Thin near-straight strands are visible in the finals.** These are clamped
  strays: scaling a 60 cm control polygon down to 24 cm leaves a long, nearly
  straight segment. Cosmetic, and downstream of §6.
- **A UE render of a candidate now exists, and it is NOT on the character.**
  `renders/ue/UE_iter021_width_*.png` shows a candidate (iteration 021)
  imported, at correct strand width, drawing as fine hair in UE — but seated at the jaw rather than
  the scalp. That is not a defect in the candidate: an UNBOUND groom placed at
  the actor root carries the pack head's origin, and this project has already
  measured the same offset on the vendor groom. **Correct seating needs a
  binding, and binding a third-party groom to this hero is a known unsolved
  problem** (the pack's own binding declares `SKM_MH_Groom_Head` as its source;
  an identity binding seats it on the jaw and a source-transfer binding
  rendered bald). So the candidate is proven to IMPORT and DRAW correctly in
  UE; it is not yet proven to SIT correctly on the hero.
- **The 3 candidates differ modestly.** 021/020/023 score 40/40/39; they are
  three points on one ridge, not three different haircuts. If none is right,
  the lever is a new mechanism, not a re-tune — `APPROACHES.md` lists what has
  already been ruled out.
