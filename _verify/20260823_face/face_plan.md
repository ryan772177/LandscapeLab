# ANGULAR HERO — a DNA geometry edit, AUTHORED AND NOT APPLIED

**2026-08-23.** Operator's words: *"needs more less puffy cheeks to create
that angular hero look"*.

    REPO_ROOT        C:\Users\Admin\UE5LandscapePipeline
    UE_PROJECT_ROOT  C:\Users\Admin\UE5LandscapePipeline\LandscapeLab

---

## 0. WHAT WAS NOT DONE, FIRST, BECAUSE IT CHANGES HOW TO READ THE REST

**DELIVERABLE 3 — `hero/dna/MHC_AlpineHero_Head_angular_v1.dna` — DOES NOT
EXIST. I COULD NOT PRODUCE IT.**

`scripts/hero_face/likeness/edit_dna_geometry.py` is not an offline tool. Its
entire payload runs **inside the editor**: it imports `scripts.ue_exec`
(`edit_dna_geometry.py:56`) and calls `unreal.LandscapeLabTools.read_dna_meshes`
and `unreal.LandscapeLabTools.write_dna_vertex_delta_in_box`
(`edit_dna_geometry.py:76, 91`), which are `UFUNCTION`s in
`LandscapeLab/Plugins/LandscapeLabEditor/Source/LandscapeLabEditor/Public/
LandscapeLabTools.h:468, 537`. There is no path through it that does not open a
remote-execution connection. The brief forbade touching the editor, so the
eight commands in §6 are written down for the operator to run and were **not
run by me**.

Everything else in this document was produced **from the DNA bytes**, by a
parser that shares no code with DNACalib — `measure_dna_offline.py`, beside
this file. That is a genuinely different representation from the plugin's
reader, which is what makes §2's agreement evidence rather than a restatement.

**Three further things I did not do or could not verify**, each expanded where
it belongs:

- I did not verify that the untouched vertices come out byte-identical. Nothing
  offline can: no DNA has been written. §7 says exactly what the plugin's own
  self-verify does and does not cover, and gives an offline check that covers
  the rest **once the file exists**.
- **No attenuation has ever been measured for a LATERAL (X) or DEPTH (Z)
  region edit on this rig.** Every gain-table entry is vertical. §5.
- The reference comparison in §3 puts a 2-D photographic outline beside a 3-D
  mesh half-width. Those are different constructions and I say so wherever the
  number appears.

---

## 1. THE BASE IS NOT THE CANONICAL DNA, AND THAT IS THE FIRST FINDING

The brief said to treat `hero/dna/MHC_AlpineHero_Head.dna` as canonical and
never edit it in place. Both hold. But **the canonical DNA is not the hero's
current face.**

`_verify/hero_likeness/shape_chain_converged.json` records seven feathered
geometry edits applied to the canonical DNA and then imported **whole-rig** on
2026-08-19 (the lock recorded in `CLAUDE.md` CURRENT STATE 2026-08-19: working
character `a31981e2`, "whole-rig import + shape chain 7c3a0dc6"). Its
`final_dna.sha256` is `7c3a0dc6f312…`.

I measured that file:

    LandscapeLab/Saved/HeroDNA/shape_i5.dna
      sha256 measured  7c3a0dc6f3127195076640c731d2b71ae3c2e4176a87feabcb31b36a86ab9b9e
      sha256 recorded  7c3a0dc6f3127195076640c731d2b71ae3c2e4176a87feabcb31b36a86ab9b9e   MATCH

Hash-proven against its own record before anything was measured against it
(non-negotiable 20). `measure_dna_offline.py` **exits** on a mismatch rather
than planning against an unproven base.

**How far the two differ, measured on `head_lod0_mesh`:**

    shape_i5 minus canonical
      moved 14,592 of 24,049 vertices, max 0.4168 cm, mean(moved) 0.1735 cm
      per-axis mean over moved:  dX -0.0002   dY -0.0992   dZ -0.0000

    anterior half-width, canonical -> shape_i5
      Y 158  6.5666 -> 6.7546   +0.1880
      Y 161  7.2118 -> 7.3485   +0.1367
      Y 166  7.6147 -> 7.7627   +0.1480

    jaw/zygomatic   canonical 0.8624    shape_i5 0.8701

**The shape chain made the lower face slightly FULLER**, because four of its
seven edits are outward width moves (`jaw_width` +0.09/side, `cheek_width`
+0.098/side, `temple_width` +0.148/side). So the operator's read of "puffy" is
a read of `shape_i5`, not of the canonical, and the plan is authored against
`shape_i5`.

**Editing the canonical instead would silently discard the converged chain**
and hand back a hero whose likeness residual is no longer 0.1633 cm. That is
the choice this section exists to make explicit.

**⚠ `shape_i5.dna` IS GITIGNORED.** `git check-ignore -v` returns
`.gitignore:30: LandscapeLab/Saved/`. The only artefact that reproduces the
hero's current locked face lives where git cannot hold it. It is *re-derivable*
— `shape_chain_converged.json` carries all seven commands and the target hash
— but this is the same shape as the 2026-08-16 loss of
`Content/Hero/Generated/`. Worth a deliberate ruling; the angular DNA below is
written into `hero/dna/`, which **is** tracked (`.gitattributes:62` puts
`*.dna` through LFS).

---

## 2. THE PARSE, AND ITS POSITIVE CONTROL

`measure_dna_offline.py` reads the DNA 2.5 header off the bytes (`"DNA"`, u16
BE generation, u16 BE version, u32 BE section count, then nine 16-byte section
entries) and takes `head_lod0_mesh`'s positions from the `geom` section as
three u32-count-prefixed big-endian float32 arrays.

    parse control vs RECIPES.md R-HEROGEOM:9109-9111 (the plugin's DNACalib reader)
      X   bytes  -19.0505 ..  19.0505    R-HEROGEOM  -19.034 ..  19.034   AGREE
      Y   bytes  140.8777 .. 178.4386    R-HEROGEOM  140.878 .. 178.439   AGREE
      Z   bytes  -11.6156 ..  14.9879    R-HEROGEOM  -11.616 ..  14.988   AGREE

(The X figure is `shape_i5`'s; the canonical reads `-19.0336..19.0336`, matching
R-HEROGEOM to four decimals. `shape_i5` is 0.0169 cm wider at the extreme
because the chain's `temple_width` edit moved it.)

The mask arithmetic in `measure_dna_offline._weights` is a line-for-line
transcription of `LandscapeLabTools.cpp:1341-1372` — clamped per-axis distance
to the box, Euclidean, `W = 1 - t²(3-2t)` inside the band, and
`result = P + Delta·W` under `EDNACalibVectorOperation::Interpolate`. So the
core / weighted counts in §6 are **predictions the operator can compare against
the tool's own printed counts**.

**Space, not re-derived:** `axes X=Left, Y=Up, Z=Front`, centimetres. The jaw is
LOW Y; down is −Y. Every box and delta below is in that space.

---

## 3. THE BASELINE — WHY "PUFFY" IS A MEASUREMENT AND NOT AN ADJECTIVE

Full output: `BASELINE.txt` (shape_i5) and `BASELINE_canonical.txt`.

### 3a. The face front has no buccal hollow at all

Anterior depth map, `max Z` per (|X|, Y) cell, left/right pooled, shape_i5.
This is the front surface of the face as a heightfield. The columns quoted are
|X| 4–8, which is inside the face: the ear is |X| > 8 (n = 2,500,
Y 161.32–171.95) and its frontmost surface reaches Z 4.256, against a face
front of Z 12.2–15.0.

**A CORRECTION I MADE TO MYSELF, because it is the exact defect class this
project keeps paying for.** I first wrote that the ear "never exceeds Z 2.4".
That was the **canonical** DNA's p95 read as a maximum, quoted against
**shape_i5** — wrong by 1.9 cm, and it was load-bearing for the ear-exclusion
argument. Replaced with a direct check: band by band from Y 153 to Y 168, the
number of |X| > 8 vertices at or above the `zf − 8` anterior gate is **zero**,
worst margin **0.976 cm**. Argument replaced by measurement.

           Y  |  x4.0   x5.0   x6.0   x7.0
        156.0 | 10.25   8.69   2.70    ---
        157.0 | 10.85   9.67   7.96    ---
        158.0 | 11.24  10.08   8.44    ---
        159.0 | 11.42  10.55   9.04   6.02
        160.0 | 11.55  10.77   9.43   6.79
        161.0 | 11.65  11.01   9.74   6.99
        162.0 | 11.66  11.14  10.17   8.62
        163.0 | 11.55  11.07  10.23   8.64
        164.0 | 11.43  10.96  10.27   8.84
        165.0 | 11.31  10.74   9.93   8.68
        166.0 | 11.35  10.53   9.60   8.19

**Every mid-cheek column rises monotonically from the mandible to a peak at
Y 162–164 and then falls. There is no local minimum anywhere between the jaw
and the cheekbone.** An angular face has one: the buccal hollow, a depression
below the zygomatic arch. This one is a continuously convex slab. That is the
measurable content of "puffy", and it is the strongest single piece of
evidence here because it needs no reference image at all.

*(Transcribed from `BASELINE.txt`, which carries the full 0–8 cm map. Read the
file, not this excerpt, if the two ever disagree.)*

### 3b. The face barely tapers below the cheekbone

Anterior half-width per 1 cm band — `max |X|` among vertices within 8 cm of
that band's frontmost point, so ear-free by construction:

    Y 158 (mouth / gonion line)   6.7546 cm
    Y 161                          7.3485
    Y 163                          7.4233
    Y 166 (zygomatic)              7.7627

    buccal / zygomatic   0.9466
    jaw    / zygomatic   0.8701

The face is **94.7 %** as wide at the buccal region as at the cheekbone. It is
close to a cylinder over that whole span.

### 3c. Against the SHAPE reference, the mesh is wider at EVERY height below
the cheekbone

Source: `hero/landmarks/bald_mediapipe.json`, which names its own image —
`hero\reference\hero_face_bald_frontal.jpg`, the **SHAPE** target.
`hero/reference/hero_example_pic.jpg` (appearance) is **not used anywhere in
this document**; R-HEROFIT:9213-9217 measures what confusing them costs
(jaw +0.570 cm, chin −0.514, cheek +0.202 — about 1.29 cm of a 2.616 cm
residual was beard).

Landmark indices are the project's single declaration at
`capture_landmarks.py:70-80` — `CHEEK_L/R 234/454`, `JAW_L/R 172/397`,
`CHIN 152`, `IRIS_L/R 468/473`.

Both sides are made dimensionless the same way, so no scale, no IPD and no
camera model enters: vertical 0 at the iris line and 1.9318 at the chin;
lateral = half-width ÷ that side's **own** zygomatic half-width.

      v      Y      REFERENCE   MESH base    base − ref
    +1.562  156.0     0.6210      0.7474      +0.1264
    +1.413  157.0     0.7244      0.8267      +0.1022
    +1.265  158.0     0.7984      0.8701      +0.0718
    +1.117  159.0     0.8581      0.9019      +0.0437
    +0.969  160.0     0.8885      0.9280      +0.0394
    +0.821  161.0     0.9264      0.9466      +0.0202
    +0.673  162.0     0.9399      0.9445      +0.0046
    +0.525  163.0     0.9731      0.9563      −0.0169
    +0.377  164.0     0.9739      0.9814      +0.0075
    +0.228  165.0     0.9656      0.9968      +0.0312
    +0.080  166.0     0.9979      1.0000      +0.0021
    −0.068  167.0     0.9642      1.0022      +0.0380

    MEAN ABSOLUTE RESIDUAL 0.0420

**Sign is uniform through the whole lower face**: the mesh carries more width
than the reference at every height from the mouth to the jaw, and the excess
grows the further down it goes. That is the same finding as 3a and 3b from a
third source.

**LIMITS, STATED.** The reference is a 2-D projection of a head at an
unmeasured pose and mediapipe placed those points on a photographic outline;
the mesh number is a 3-D anterior half-width. **Different constructions.** The
mesh chin anchor (Y 154.00) was found by walking down in 0.25 cm bands to the
Z discontinuity where the face front ends — a naive "lowest vertex with a big
Z" returns Y 140.92, the mesh minimum, because this mesh carries a
chest/shoulder cap whose front reaches Z 11.22. Rows above v +1.65 are dropped
for the same reason: there the anterior half-width starts measuring the
under-jaw. **This comparison sets direction. It is not a target with a
tolerance, and §5 explains why I refused to let it choose the magnitudes.**

### 3d. What I could not measure

- **The rendered face.** Every number here is DNA geometry. Nothing in this
  document is a render measurement, because rendering needs the editor.
- **IPD drift.** IPD is horizontal iris separation and no vertex of
  `head_lod0_mesh` defines it; the eye meshes are separate meshes in the DNA.
  I did not enumerate them. §8 makes it an editor-side check.
- **Teeth and eye coherence under a reshaped mid-face.** BACKLOG
  B-FITCOHERENCE, open since 2026-08-17, unaddressed here.

---

## 4. THE EDIT — FOUR REGIONS, EIGHT CALLS

The tool applies **one uniform translation** per call, feathered by a
smoothstep on distance from a box. It cannot scale, taper or sculpt. Every
shape below is therefore built from translations, and where that limits the
result I say so.

**Order is part of the spec.** Each call re-evaluates its mask on the
**current** positions, so width-before-depth is not interchangeable with the
reverse.

### The eye-band rule, which cost the first two designs

`scripts/hero_face/likeness/manifest.json:467` (`_eye_band_rule`):

> "NO edit box, including its feather reach, may enter Y 164.5..169.5. The
> measurement frame is iris-centred and IPD-scaled, so editing near the eyes
> changes the normaliser and every other region appears to move. Measured
> 2026-08-17: IPD moved +2.7% in one iteration and the residual went
> backwards."

My first cheekbone box was `Y 162.8..166.0` with a 1.2 cm feather. Reach
164.5 + . **It violated the rule and I rewrote it.** Every box below satisfies
`box_max.Y + feather < 164.5`:

    J  158.5 + 1.5 = 160.0      M  163.2 + 1.1 = 164.3
    A  160.5 + 2.0 = 162.5      B  163.5 + 0.9 = 164.4

Verified on the vertices, not on the arithmetic: **0 of 8,262 vertices in
Y 164.5..169.5 move at all** (max displacement 0.0000 cm).

### The four regions

| id | what it is | box_min | box_max | feather | delta (per side) |
|---|---|---|---|---|---|
| **J** | mandible / jowl WIDTH | `(4.0, 153.2, 0.0)` | `(7.8, 158.5, 12.5)` | 1.5 | medial 0.28 |
| **M** | mid-face WIDTH | `(4.0, 158.8, 4.0)` | `(7.4, 163.2, 12.5)` | 1.1 | medial 0.15 |
| **A** | buccal DEPTH | `(3.8, 157.5, 5.0)` | `(7.6, 160.5, 12.5)` | 2.0 | `Z −0.35` |
| **B** | malar DEPTH | `(5.0, 162.2, 5.0)` | `(8.0, 163.5, 12.5)` | 0.9 | `Z +0.22` |

(Left side shown; the right side is the mirrored box with the X sign of the
delta flipped. "medial 0.28" means `−0.28` on the left, `+0.28` on the right,
i.e. both toward the midline. The mirror is **two explicit boxes**, never a
sign flip of one translated box — a single box moved sideways shifts the face
off-centre instead of narrowing it, which is the reason
`manifest.json:_fit_note` gives for the same construction.)

### Why each region, and why that direction

**J — mandible/jowl width, medial 0.28 cm per side.** §3c's residual is
largest and most systematic here (+0.126 and +0.102 at Y 156–157). The
reference's silhouette closes in toward the chin far faster than the mesh's.
Narrowing the soft tissue over the mandible is what produces a jaw that reads
as a *line* rather than as a continuation of the cheek. **`Z_min = 0.0`** so
the box reaches the lateral jaw surface, which sits at Z 2–4, not only the
front. Ear-safe by height, not by luck: the ear's lowest vertex is **Y 161.3**
(measured) and this box's reach stops at Y 160.0.

**M — mid-face width, medial 0.15 cm per side.** Half of J's magnitude,
deliberately: the residual shrinks going up, so a uniform narrowing would
over-correct the buccal region and under-correct the jaw. Two bands is the
coarsest thing this tool can do that is *graded*. This is the one box whose
height overlaps the ear (Y 161.3+), so it is the one that had to be checked
rather than reasoned about. **`Z_min = 4.0`** lifts it above the ear's
frontmost Z 4.256, and the box was tightened from X 7.6 / feather 1.2 to
**X 7.4 / feather 1.1** after the first version left only **0.02 cm** of
Euclidean margin on the ten worst ear vertices. Measured on the result:
**0 of 2,500 ear vertices move at all, max 0.000000 cm.** The tightening cost
nothing — the taper residual is 0.0272 either way.

**A — buccal depth, `Z −0.35` cm.** This is the operator's actual ask. §3a
shows a convex slab where a hollow belongs. Pulling Y 157.5–160.5 back 0.35 cm
against an unmoved Y 162–164 produces the concavity the frontal key light needs
to cast a shadow into. **No lateral component**, because a medial move is
already supplied by M and doubling it here would over-narrow.

**B — malar depth, `Z +0.22` cm.** The other half of the same contrast: the
cheekbone reads as a cheekbone when it is *in front of* what is below it. A
+0.22 against A's −0.35 gives **0.57 cm of malar relief** where there is
currently a monotone ramp. The band is thin (1.3 cm core) and its feather is
0.9 because the eye-band rule caps the reach at 164.4.

**No lateral component on B**, and this was measured rather than assumed: an
earlier design gave the malar box +0.08 cm of lateral, and it took
buccal/zygomatic the **wrong way**, 0.9466 → 0.9548, because it widened the
band immediately above the region being narrowed. Width and depth are separated
for that reason.

### What I deliberately did NOT edit

- **A sub-mandibular / under-jaw tuck**, which is the other classic route to a
  defined jawline. R-HEROCAP's camera is a locked **frontal** view
  (`RECIPES.md:8641`, azimuth 90, rot `[0.0, -90.0, 0.0]`). It cannot see under
  the jaw, so the edit would be **unverifiable with the available instrument**.
  Non-negotiable 6: I would rather say I did not do it.
- **Anything in the eye band.** See above.
- **The chin.** `chin_height` was already moved −0.372 cm by the converged
  chain; nothing in the operator's ask concerns it.

### The blast radius, measured, with negative controls

    band                          n   mean|d|  max|d|   mean medial   mean dZ
    chin        Y152-156 |X|<4   741   0.0362  0.2810     +0.0362    -0.0005
    jowl/jaw    Y154-158 |X|4-8  571   0.2674  0.4597     +0.2263    -0.1012
    buccal      Y158-163 |X|4-8 1312   0.1863  0.5425     +0.1179    -0.0934
    zygomatic   Y163-167 |X|5-8 2492   0.0130  0.2663     +0.0066    +0.0104
    nose+lips   Y156-166 |X|<3  7682   0.0195  0.2253     +0.0007    -0.0194
    periorbital Y164-170 |X|<6  5386   0.0001  0.0889     +0.0000    +0.0001
    EAR   ctrl  |X|>8 Y161-172  2500   0.0000  0.0000     +0.0000    +0.0000
    forehead ctrl Y169+         2252   0.0000  0.0000     +0.0000    +0.0000
    neck  ctrl  Y<152           1385   0.0002  0.0278     +0.0002    +0.0000

    total: 5,196 of 24,049 vertices move; max displacement 0.5425 cm

**Ear, forehead and eye band are exact zeros.** Those are the negative
controls, and they are the reason the non-zero rows can be read as the edit
rather than as spill.

**One row that is NOT a control and needs declaring: the mouth.** Against the
R-HEROCAP noise floor (0.057 cm, `RECIPES.md:8665`), **918 of 4,561** vertices
in `Y 156.5..161, |X| < 3` move above it, worst 0.2253 cm. That is region A's
medial feather reaching the mouth corners and the nasolabial fold, pulling them
back with the cheek. It is intended — a hard stop at X 3.8 is exactly the
vertical crease R-HEROGEOM REJECTED:9169 records ("visible vertical seams on
the chin … the fit smooths but does not remove it") — but it *is* a change to
the mouth and it should be looked at in the render, not only counted. The nose
sees 183 of 5,303 above the floor, worst 0.0983 cm. Four periorbital vertices
exceed the floor, worst 0.0889 cm, all below Y 164.5.

### Predicted result, PRE-IMPORT

    anterior half-width, cm      base -> predicted
      Y 156   5.8018 -> 5.5218   -0.2800
      Y 157   6.4172 -> 6.1293   -0.2879
      Y 158   6.7546 -> 6.3426   -0.4120
      Y 159   7.0009 -> 6.7914   -0.2095
      Y 161   7.3485 -> 7.1985   -0.1500
      Y 163   7.4233 -> 7.3481   -0.0753
      Y 164+  unchanged, exactly

    buccal / zygomatic   0.9466 -> 0.9273
    jaw    / zygomatic   0.8701 -> 0.8171      (reference 0.8069)

    normalised taper residual vs the SHAPE reference
      0.0420 -> 0.0272      -35%

Full per-row table in `SIMULATION.txt`. Every row of the taper curve below the
cheekbone moves toward the reference; two rows near v +0.5..+0.7 cross slightly
past it (−0.015, −0.028), which is inside the construction mismatch §3c
declares.

**What this edit CANNOT do:** the tool translates, so region A produces a
*plane shift with a smooth ramp*, not a true concavity. The buccal region ends
up further back and the transition to the malar steeper; it does not gain a
curvature inflection. If the render says the cheek reads flat rather than
hollow, the lever is a third depth band between A and B, not a larger A.

---

## 5. ATTENUATION — WHAT IS MEASURED, WHAT IS NOT, AND WHY I DID NOT LET THE
REFERENCE PICK THE MAGNITUDES

**The brief's 0.650 is superseded and I should say so.** `RECIPES.md`
R-HEROGEOM:9143 records `ATTENUATION 0.650` — but `manifest.json:283-291`
marks that entry `boxed_2026_08_17`, `feather_band_cm 0.0`, *"PROVISIONAL BY
CONSTRUCTION — hard box, visible chin seams. Superseded by the feathered
entry."* The **current** gain-table entry is `feathered_2026_08_17`,
attenuation **1.078** (commanded −2.0 cm, chin measured −2.1553 cm) with a
2.5 cm feather. Attenuation is a property of *(region × mask)*, and a feathered
edit is a different mask from a boxed one.

**The route decides the number, and this hero is on the whole-rig route.**

    fit path   (import_whole_rig=False)   chin ratio 1.078   RECIPES.md:9362
    whole-rig  (import_whole_rig=True)    chin ratio 0.981   RECIPES.md:9361

`import_whole_rig=True` **replaces** the rig from the DNA instead of fitting a
parametric state to it, so application is near-exact by construction, and 0.981
is the measurement of that. The hero's current face came from a whole-rig
import (§1), so §8 uses `--whole-rig` and the plan budgets attenuation at
**≈ 0.98–1.0 in every axis**. The predicted geometry in §4 is therefore also
the predicted *rendered* geometry, to within ~2 %.

**BUT: NO LATERAL OR DEPTH GAIN HAS EVER BEEN MEASURED ON THIS RIG.** Every
number above is a **vertical** chin move. `manifest.json` carries
`jaw_width` gain 5.1448 and `cheek_width` gain 5.0976 — and its own
`_gain_reset_note` (line 468) says *"Gains reset 2026-08-17. Anything learned
while the IPD normaliser was moving was fitted to a ruler that changed between
measurements. Only chin_height's 1.078 survives."* Those two numbers were
measured 2026-08-18 on the **fit** path and I am **not** budgeting on them.
State it plainly: **the X and Z attenuations for these four regions are
UNKNOWN, and the first run measures them.**

**Why the magnitudes are what they are.** I swept J ∈ {0.20…0.36} and
M ∈ {0.12…0.18} against the §3c residual. The residual falls **monotonically**
across the whole range — 0.0307 at J 0.20 down to 0.0243 at J 0.36 — with no
minimum. An objective with no minimum inside the plausible range is not
choosing a magnitude; it is telling you it disagrees with the artefact at the
bottom of the face, which is where §3c's two constructions diverge most.
R-HEROFIT REJECTED:9302 is the precedent: *"An objective function is a claim
about what matters, and it is the least tested claim in any fitting
pipeline."*

So the magnitudes were chosen on three grounds instead:

1. **Measurable.** 0.28 cm at gain ~1.0 is **4.9×** the R-HEROCAP noise floor
   (0.057 cm p90, `RECIPES.md:8665`). The smallest, M at 0.15, is 2.6×.
2. **Short of the target on both instruments.** jaw/zygomatic lands 0.8171
   against the reference's 0.8069 — **84 % of the gap**, deliberately not
   100 %, so an over-response is still under the target rather than past it.
3. **Recoverable if the gain is far from 1.** Even at a 2× response, jaw/zyg
   lands ~0.765 — visibly over-narrow, and fully reversible (§8 step 8).

**A conservative half-strength variant**, if the operator would rather spend an
extra round trip than risk an over-narrow jaw: J 0.14, M 0.08, A −0.18,
B +0.11. Measured, not estimated:

    variant   buccal/zyg   jaw/zyg   taper residual
    base        0.9466     0.8701       0.0420
    HALF        0.9363     0.8430       0.0338
    FULL        0.9273     0.8171       0.0272
    reference      --      0.8069          0

Half strength is still 2.5× the noise floor on J and closes 42 % of the ratio
gap instead of 84 %.

**R-HEROWHOLERIG's own OPEN item applies here and I am not going to pretend it
does not:** *"ONE EDIT, NOT AN ACCUMULATION … Chain a second edit onto the
edited DNA and re-measure before the loop relies on it."* This plan chains
**eight** edits onto `shape_i5`, which is itself the product of seven. The
mitigating evidence is that `shape_i5`'s own seven-edit chain went through
whole-rig and produced a measured 0.1633 cm residual, so a chained stack has in
fact survived this route once. Thirteen deep is still further than anything
measured.

---

## 6. THE EXACT COMMANDS

**Not run.** Run them in order, from `REPO_ROOT`, with an editor attached and
rule 7 satisfied.

**`--in-dna` MUST BE ABSOLUTE.** `edit_dna_geometry.py:147` passes it through
untouched, while `:148-150` joins a relative `--out-dna` to `REPO_ROOT`. The
payload runs inside the editor, whose working directory is the engine
`Binaries\Win64` folder (`CLAUDE.md` CURRENT STATE 2026-08-21, "PASS AN
ABSOLUTE `--out-dir` TO EVERY CAPTURE TOOL"). A relative `--in-dna` resolves
there.

**Use `--flag=value` for every coordinate**, per R-HEROGEOM:9127 — argparse
reads a bare `-7.8,…` as an option and exits 2 with no message.

`--feather` is mandatory without `--region` (`edit_dna_geometry.py:175-178`):
a hard box is a measurement decision, not a fallback.

Let `R = C:/Users/Admin/UE5LandscapePipeline` and
`H = C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA`.

```
REM 1of8  J1  mandible/jowl width, LEFT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/shape_i5.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s1.dna --mesh 0 ^
  "--box-min=4.0,153.2,0.0" "--box-max=7.8,158.5,12.5" ^
  --feather 1.5 "--delta=-0.28,0,0"

REM 2of8  J2  mandible/jowl width, RIGHT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s1.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s2.dna --mesh 0 ^
  "--box-min=-7.8,153.2,0.0" "--box-max=-4.0,158.5,12.5" ^
  --feather 1.5 "--delta=0.28,0,0"

REM 3of8  M1  mid-face width, LEFT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s2.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s3.dna --mesh 0 ^
  "--box-min=4.0,158.8,4.0" "--box-max=7.4,163.2,12.5" ^
  --feather 1.1 "--delta=-0.15,0,0"

REM 4of8  M2  mid-face width, RIGHT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s3.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s4.dna --mesh 0 ^
  "--box-min=-7.4,158.8,4.0" "--box-max=-4.0,163.2,12.5" ^
  --feather 1.1 "--delta=0.15,0,0"

REM 5of8  A1  buccal depth, LEFT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s4.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s5.dna --mesh 0 ^
  "--box-min=3.8,157.5,5.0" "--box-max=7.6,160.5,12.5" ^
  --feather 2.0 "--delta=0,0,-0.35"

REM 6of8  A2  buccal depth, RIGHT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s5.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s6.dna --mesh 0 ^
  "--box-min=-7.6,157.5,5.0" "--box-max=-3.8,160.5,12.5" ^
  --feather 2.0 "--delta=0,0,-0.35"

REM 7of8  B1  malar depth, LEFT
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s6.dna ^
  --out-dna LandscapeLab/Saved/HeroDNA/angular_v1_s7.dna --mesh 0 ^
  "--box-min=5.0,162.2,5.0" "--box-max=8.0,163.5,12.5" ^
  --feather 0.9 "--delta=0,0,0.22"

REM 8of8  B2  malar depth, RIGHT  -> THE DELIVERABLE
python scripts/hero_face/likeness/edit_dna_geometry.py ^
  --in-dna  C:/Users/Admin/UE5LandscapePipeline/LandscapeLab/Saved/HeroDNA/angular_v1_s7.dna ^
  --out-dna hero/dna/MHC_AlpineHero_Head_angular_v1.dna --mesh 0 ^
  "--box-min=-8.0,162.2,5.0" "--box-max=-5.0,163.5,12.5" ^
  --feather 0.9 "--delta=0,0,0.22"
```

**Reversing them** needs no undo: nothing is edited in place, so deleting the
eight new files restores the file system exactly. Reversing the *character*
is §8 step 8. To reverse a single stage, re-run from the previous `angular_v1_sN`
with the delta negated — but note the mask re-evaluates on moved positions, so
that is an approximate inverse, not an exact one; **re-running the chain from
`shape_i5.dna` is the exact route.**

**Cost:** eight ~54 MB DNAs, ≈ 430 MB, all under gitignored
`LandscapeLab/Saved/`. Only the last lands in tracked `hero/dna/`.

**If `shape_i5.dna` is ever missing**, rebuild it first by replaying the seven
commands in `_verify/hero_likeness/shape_chain_converged.json` from
`hero/dna/MHC_AlpineHero_Head.dna` and asserting sha256 `7c3a0dc6f312…`.

---

## 7. SELF-VERIFICATION — WHAT THE TOOL CHECKS, AND THE HOLE IN IT

### What the plugin does, at source

`LandscapeLabTools.cpp:1424-1484`, after `SaveDNAToFile`:

1. reloads the written file — `"Wrote %s but it did not parse back as DNA"` if
   it will not;
2. checks the vertex count round-trips;
3. checks **every weighted vertex** equals `original + Delta·weight`, tolerance
   `1e-3` (`:1435`) — this is where the `Interpolate` mask semantic is *proven*
   rather than assumed;
4. checks zero-weight vertices have not moved — **but the loop is
   `Checked < 512` (`:1458`)**.

It then prints `"; self-verified N weighted (against original + Delta*w) and
K zero-weight vertices"`.

### The predicted counts, per call

Computed offline with the transcribed mask. The operator should compare these
against what the tool prints; a disagreement means the base is not the file I
measured.

    call  region        core   weighted   zero-weight
     1    J1 jaw L       274        863        23,186
     2    J2 jaw R       272        869        23,180
     3    M1 mid L       269        873        23,176
     4    M2 mid R       265        855        23,194
     5    A1 buccal L    155      2,025        22,024
     6    A2 buccal R    155      2,022        22,027
     7    B1 malar L      63        221        23,828
     8    B2 malar R      62        220        23,829

    net over all eight: 5,196 moved, 18,853 untouched, max 0.5425 cm

The tool's `weighted` is its `OutSelectedCount`, its `at full weight` is
`OutCoreCount`, and both are printed by `edit_dna_geometry.py:204-205`.

### THE HOLE, STATED PLAINLY

**The brief asked me to "confirm the untouched set is byte-identical". The
tool cannot do that and neither could I.**

- It samples at most **512** of ~23,000 zero-weight vertices per call
  (`:1458`). That is **2.2 %**.
- The guarantee is **per call**, against that call's own input. Eight chained
  calls give eight local guarantees, not one end-to-end one.
- No DNA exists yet, so I have nothing to check.

**The offline check that closes it**, once the file exists — it compares **all
24,049** vertices against an independently computed prediction, from a parser
that shares no code with DNACalib:

```
python _verify/20260823_face/measure_dna_offline.py ^
  --verify  hero/dna/MHC_AlpineHero_Head_angular_v1.dna ^
  --against LandscapeLab/Saved/HeroDNA/shape_i5.dna
```

It prints the max `|predicted − file|` separately for weighted and zero-weight
vertices and returns **4** if either exceeds 1e-3 cm — the plugin's own
tolerance. **Run it before the import**, not after: a bad DNA caught on disk
costs nothing, and caught after a whole-rig import costs the disk restore in
§8 step 8.

**Its refusal direction is proven, not asserted.** Handed `shape_i5.dna` as
the "edited" file — i.e. a DNA on which the eight edits were never applied —
it returns:

    weighted vertices    5200   max |predicted - file|  0.414441 cm
    zero-weight         18849   max |predicted - file|  0.000000 cm
    VERDICT FAIL     exit 4

The zero-weight side reads **exactly 0.000000** while the weighted side fails
by 0.42 cm, so the refusal is driven by the vertices that were supposed to
move and the check discriminates rather than simply objecting.

---

## 8. THE EDITOR STEPS, IN ORDER

Each step names the recipe that owns it. **None of this was run.**

**0. Verify the editor.** `python scripts/bootstrap.py` — one node, MATCH
against `UE_PROJECT_ROOT`. Standing rule 7. Nothing else may touch the editor
while any of this runs (`CLAUDE.md` CURRENT STATE 2026-08-10: a second command
client wins silently and the victim hangs).

**1. RISKY-OP CHECKPOINT, and it must include an ON-DISK copy.**
`git tag pre-angular-face-20260823`. Then **copy
`/Game/Hero/MHC_AlpineHero`'s `.uasset` to
`_trash/hero_likeness_backups/<UTC>/` and record its SHA-256.** A git tag cannot
hold gitignored content, and the whole-rig undo is a *disk* restore. R-HEROIMPORT
"THE SAFETY EQUIPMENT, MANDATORY" (`RECIPES.md:8964-8968`).

**2. Build the capture stage.** `build_capture_stage.py --azimuths "90"`.
R-HEROCAP. It searches the framing once and locks it; `capture_shot.py` reads
no property of the subject, so a face that changes shape cannot move the camera.

**3. Re-measure the noise floor IN THIS SESSION.**
`capture_shot.py --noise-floor --repeats 4`. R-HEROGEOM REJECTED:9187 —
*"Judging an arm against another session's floor … 0.01114 IPD where the
previous two measured 0.00835 and 0.00758 — same stage, same script, same
subject, different process."* Everything in §4–5 is quoted against **0.057 cm**;
if this session's floor differs, re-scale the judgements, do not re-use mine.

**4. Baseline render, settled.** `sanctioned_import.py` will not accept an
unsettled baseline (exit 9). R-HEROIMPORT: a freshly reloaded character renders
a faceted, unresolved preview that reads as a 7.5× "effect".

**5. Run the eight edits.** §6.

**6. Verify the DNA offline.** §7. Do this *before* the import.

**7. Import — WHOLE RIG.**

```
python scripts/hero_face/likeness/sanctioned_import.py ^
  --dna hero/dna/MHC_AlpineHero_Head_angular_v1.dna --whole-rig --timeout 25
```

R-HEROWHOLERIG (`RECIPES.md:9307`). Whole-rig because that is the route the
hero's current face came from (§1) and because it applies the DNA near-exactly
(chin ratio 0.981) instead of re-solving a parametric state (1.078, and a 4×
worse reproducibility once edits accumulate).

`--timeout` is a **discovery window spent in full**, not a budget
(R-HEROWHOLERIG REJECTED). Use 12–25 and raise the shell's timeout instead.

The tool assembles for preview, re-points the stage at the transient preview
Face mesh (R-HEROIMPORT: *"re-point after EVERY assemble"*), renders at the
locked camera and reports the landmark delta. **It leaves the character
IMPORTED by design.**

**8. THE UNDO IS A CLOSED-EDITOR DISK RESTORE. `--restore` WILL REFUSE, AND IT
IS RIGHT TO.** R-HEROGEOM's own VERIFICATION block still says
`sanctioned_import.py --restore`; that is **superseded**.
`sanctioned_import.py:309-339` refuses for every character, because
`reload_packages` fataled this editor twice out of two attempts on 2026-08-19
(`EXCEPTION_ACCESS_VIOLATION` reading `0x470`), on a whole-rig character *and*
on the master that had never taken one. The procedure it prints:

    1  close the editor (read the dirty list empty FIRST)
    2  copy the timestamped backup .uasset back over it
    3  assert SHA-256 against the backup's recorded hash
    4  reopen and RE-MEASURE -- bytes are not the proof, the render is

**9. Judge, on four things, in this order.**

- **The frame, opened.** Non-negotiable 10 and 16, and R-HEROGEOM found the
  hard-box seam *in the frame while the statistics were clean*. Look for a
  crease beside the mouth (region A's medial feather, §4's mouth row), a line
  under the eye at Y ≈ 164.4 (region B's top edge), and whether the buccal area
  reads as **hollow** or merely as **set back** — §4 says the tool can only do
  the latter.
- **The named landmark deltas** the import prints: `jaw_width`, `cheek_width`,
  `chin_height`, and the negative controls `brow_height` and `nose_bridge`.
  Expect movement in the first two, and **note that R-HEROWHOLERIG's OPEN item
  already records `brow_height` −0.125 cm and `nose_bridge` −0.211 cm moving
  2–4× the floor from OUTSIDE an edit box on this route**, attributed to
  landmark-model bias rather than geometry. Do not read that as spill without
  checking the geometry, which §4's table says is exactly zero there.
- **IPD.** R-HEROFIT refuses above 1.5 % drift between iterations. Nothing in
  §4 moves an eye-band vertex, so a drift here is the landmark model, not the
  mesh — but it must be *looked at*, because I could not measure IPD offline
  (§3d).
- **The gain.** Divide the measured `jaw_width`/`cheek_width` change by the
  commanded 0.28/0.15 per side. **That number is the deliverable of the first
  run**, because §5 says no lateral gain exists yet. Record it into
  `manifest.json`'s `geometry_regions` **with its box and feather**, since
  attenuation is a property of *(region × mask)*.

**10. Log at both altitudes and lock a recipe.** Four new named regions is a
new element under CLAUDE.md's NEW-ELEMENT RULE. Whatever the first run
measures — including "it over-shot" — belongs in `LESSONS.md` before any
retry, and in R-HEROGEOM's REJECTED section if it failed.

---

## 9. FILES

    _verify/20260823_face/face_plan.md            this
    _verify/20260823_face/measure_dna_offline.py  the instrument; --baseline,
                                                  --simulate, --verify
    _verify/20260823_face/BASELINE.txt            shape_i5, the hero's face today
    _verify/20260823_face/BASELINE_canonical.txt  the canonical, for §1
    _verify/20260823_face/SIMULATION.txt          the predicted edit, in full

    NOT PRODUCED: hero/dna/MHC_AlpineHero_Head_angular_v1.dna  -- needs the editor
