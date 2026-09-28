# AGENT_sides — left/right sides and their symmetry

Owner knobs: `side_length_scale`, `ear_clearance`, `temple_wing`, `rot_up_deg`,
`rot_side_deg`, `gravity_drop`, `gravity_ramp`. Nothing else was written —
verified mechanically: `mkparam.py` REFUSES any key outside that set, and the
final params differ from `hero_032.json` in exactly two keys.

Baseline / control: `sides_00` = a byte copy of `hero_032.json`.

---

## ⛔ READ FIRST — THE CLAY TARGET WAS CONTAMINATED, AND ONLY THE TARGET

`hero/reference/appearance_groom_clay.jpg` is 1042 px wide and carries an
**11-px solid dark border** (luma ~21 against a background of 59).
`front_metrics.BORDER` is 6, so **five border columns survive the trim and are
classified as HAIR on every row.**

Measured, not inferred: every one of the 16 width bands has its hair mask
reaching column 1029 of a 1030-px frame — including band 15, where the mask is
*only* columns 1025-1029. That is why `clay_front.json`'s `width_profile` is a
constant **3.6453**: it is a frame saturation, not a hair measurement, and it is
unusable as a shape target in its published form.

**The contamination is ONE-SIDED.** Our renders are PNGs with no such border:
`sides_07` measures byte-identical at BORDER 6, 14 and 20. The clay moves and
then goes stable at ≥14. So the bug inflates only the target.

| clay axis | published (BORDER 6) | corrected (BORDER 14) |
|---|---|---|
| band_cover ear | 0.2921 | **0.2828** |
| band_cover jaw | 0.2432 | **0.2285** |
| band_cover forehead | 0.7322 | **0.7912** |
| band_cover brow | 0.4956 | **0.5201** |
| band_cover eye | 0.3738 | **0.3834** |
| central forehead | 0.2158 | **0.2696** |
| central brow | 0.0055 | **0.0185** |
| hair_area_over_face_area | 1.3064 | **1.2471** |
| edge_roughness | 92.44 | **88.44** |
| crown_lift_frac | 0.6016 | **0.5166** |
| width_profile | const 3.6453 | 1.89 → 1.58 → **1.21** (a real taper) |

**This affects the fringe and crown agents too** — their forehead, brow and
crown_lift targets are all in the table above. I did NOT edit
`front_metrics.py`: it is the shared instrument, three agents' numbers and the
v032b baseline are already measured with it, and changing it mid-flight would
silently move everyone's board. The correction is applied in
`survey/score_sides.py` / `summary_sides.py`, which re-measure the clay at
BORDER=14 and print the raw values beside the corrected ones.

Recommended, not taken: raise `BORDER` to 14 and re-baseline every agent in one
commit.

### What the corrected profile actually says

The clay is a **wide-topped wedge that tapers**: 1.89 at the temples → 1.58 at
the ear → **1.21 at the jaw**. v032b is the inverse — narrow on top (1.57),
still wide at the jaw (1.51). So the brief's "RAISE mass" is right, but the
mass belongs **high and pulled in low**, not added uniformly.

---

## SECOND INSTRUMENT CAVEAT — THE DENOMINATOR MOVES UNDER YOU

`width_profile` and `hair_area_over_face_area` are both normalised by `face_w`,
a measurement **my own edits change**. Cycle 2 looked like a 5% narrowing of
every band; it was `face_w` going 259 → 274 because the edit uncovered cheek.
`face_w` is logged every cycle (`survey/faces.py`) and no width claim here is
made without it. Absolute cross-checks used: `mask_frac.hair`, front `hair_px`.

Also: the brief states `scalp_exposed_pct` is "currently ~0.5%". **Measured, the
v032b baseline is 3.21%** — already above the stated 3.0 bar. I treated
"no worse than baseline" as the real constraint; every kept candidate is *better*
than baseline.

---

## CYCLE LOG

| # | run | knob moved | ear | jaw | area | flare | scalp | ceye | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0 | sides_00 | (control, = hero_032) | 0.3064 | 0.2046 | 1.0743 | 0.651 | 3.21 | 0.0167 | reproduces v032b to +0.0000 on every axis |
| 1 | sides_01 | side_length_scale 1.15→1.40 | 0.3230 | **0.2308** | **1.1073** | 0.672 | 3.21 | 0.0173 | **KEEP** jaw +0.0262, area +0.0330 |
| 2 | sides_02 | temple_wing 0→0.02 | 0.3073 | 0.2309 | 1.0807 | 0.672 | 3.45 | 0.0194 | **REJECT** |
| 3 | sides_03 | gravity_ramp 2.0→3.0 | 0.3030 | 0.2232 | 1.0861 | 0.667 | **2.84** | 0.0179 | **KEEP** scalp/flare/width up high |
| 4 | sides_04 | side_length_scale 1.40→1.65 | 0.3115 | **0.2329** | **1.1064** | 0.667 | 2.97 | 0.0177 | **KEEP** best mass |
| 5 | sides_05 | ear_clearance −0.018→−0.030 | 0.3000 | 0.2167 | 1.0685 | 0.622 | 2.98 | 0.0186 | **REJECT** |
| 6 | sides_06 | len 1.90 **+** ramp 3.5 (paired) | 0.3094 | 0.2404 | 1.1038 | 0.709 | 2.94 | **0.0271** | **REJECT — watch axis breached** |
| 7 | sides_07 | gravity_ramp 3.0→3.5 | 0.3079 | 0.2324 | 1.1019 | 0.665 | **2.84** | 0.0174 | **KEEP — shipped** |

Stopped at the 8-cycle cap, which coincided with the 3-consecutive-no-improvement
rule (C5 regressed, C6 breached, C7 flat).

### Why each rejection was rejected — the mechanism, not the number

**C2, `temple_wing` — it does not widen the silhouette, it lifts hair off the
head.** Bands 0-6 read *narrower*, which is impossible for an outward push until
you notice `face_w` went 259 → 274: the wing uncovered cheek, enlarging the face
mask that every width is divided by. Corroborated by two independent axes moving
the right way for that story — scalp 3.21 → 3.45 and ear cover 0.3230 → 0.3073.
The knob's 0.0 default is correct and I put it back.
Its one real gain was `edge_roughness` 86.3 → 88.2, which is not my axis.

**C5, `ear_clearance` more negative — it hides hair behind the head.** In a front
view, pulling side tips inward past a point moves them *behind the face mesh*,
where they leave the silhouette entirely: jaw 0.2329 → 0.2167, area 1.1064 →
1.0685 (below baseline), `mask_frac.hair` 0.0880 → 0.0841. It did tighten the
over-wide jaw bands as predicted — the tightening works, the cost is larger than
the gain. **−0.018 is already near optimal.**

**C6, length 1.90 + ramp 3.5 — overshoot, and it bought nothing.** Area went
1.1064 → 1.1038, i.e. **flat, inside the deadband, despite +15% side length**:
past ~1.65 the extra length stops adding mass and only adds spread. It breached
`central_cover eye` at **0.0271 against the 0.020 bar**, pushed flare to 0.709,
overshot edge_roughness to 93.8, and took bands 7-13 from near-target to +0.23…+0.59.
C6 also **corrects C3's attribution**: the bands 0-4 gain I had credited to the
ramp was the *length*. C7 isolated the ramp and bands 0-4 did not move.

---

## SHIPPED: `sides_07`

```json
{ "side_length_scale": 1.65, "gravity_ramp": 3.5 }
```

Everything else at v032b: `ear_clearance` −0.018, `temple_wing` 0.0,
`rot_up_deg` 14.0, `rot_side_deg` −6.0, `gravity_drop` 0.045.

`sides_04` (`side_length_scale` 1.65, `gravity_ramp` 3.0) is the max-mass
alternative — jaw +0.0005 and area +0.0045, **both inside the 0.005 deadband**,
so it is a tie on my headline, not a better result. Tie broken on the watch axis
with the least margin: sides_04 leaves 0.03 of scalp headroom (2.97 vs 3.0),
sides_07 leaves 0.16 (2.84). The reserved texture knobs another agent owns
(`clump_scale`) are known to *open* scalp, so the margin is worth more than a
deadband-sized mass gain.

| axis | v032b | sides_07 | CLAY* | note |
|---|---|---|---|---|
| band_cover ear_0.30_0.62 | 0.3064 | 0.3079 | 0.2828 | **held**, +0.0015; floor 0.28 respected |
| band_cover jaw_0.70_0.95 | 0.2046 | **0.2324** | 0.2285 | **+0.0278 — target met and passed** |
| hair_area_over_face_area | 1.0743 | **1.1019** | 1.2471 | +0.0276; **still −0.145 short** |
| edge_roughness | 81.86 | 90.00 | 88.44 | +8.1, slightly past |
| flare_max_ratio (watch) | 0.651 | 0.665 | ≤0.75 | pass |
| scalp_exposed_pct (watch) | 3.21 | **2.84** | ≤3.0 | pass, **better than baseline** |
| central_cover eye (watch) | 0.0167 | 0.0174 | ≤0.020 | pass |
| symmetry ear (L−R)/(L+R) | +0.3369 | **+0.1400** | −0.1159 | bias more than halved |
| symmetry TOTAL | +0.0602 | **+0.0296** | −0.2419 | halved |

\* clay at BORDER=14.

---

## SYMMETRY — a new instrument, because no existing axis could see it

`band_cover` and `width_profile` both collapse left and right into one number, so
a groom that has lost a lock on one side scores identically to a balanced one.
`survey/symmetry.py` reports signed `(L−R)/(L+R)` per band about the same `cx`
front_metrics derives.

Baseline was strongly **left-biased** — ear **+0.3369**, eye +0.3273, total
+0.0602. sides_07 more than halves it: ear **+0.1400**, total **+0.0296**. Not
targeted; it fell out of loading the sides evenly with length instead of leaving
them dependent on the global yaw.

**The clay leans the other way** (total −0.2419, forehead −0.3700). Perfect
symmetry is *not* the target — the reference is a deliberately wind-blown shag —
but our lean is **opposite in sign** to it. The knob that sets it is
`rot_up_deg` (+14.0, mine). **Untested, and deliberately so:** ops 6a is applied
with **no region mask**, so `rot_up_deg` and `rot_side_deg` rotate *every* strand
— fringe, crown and nape included. They are listed as mine but they are global,
and moving them would silently restyle two other agents' regions. Flagged rather
than spent.

---

## NEXT, RANKED

1. **`rot_up_deg` −14 instead of +14** would flip the lean to match the clay's
   direction. One cycle. **Needs cross-agent agreement first** — it is unmasked
   and moves the fringe and crown too.
2. **Area (−0.145) is not reachable from the sides.** C6 proves length past 1.65
   adds spread, not mass, and breaks `central_cover eye`. The remaining deficit is
   volume, which lives in the reserved knobs (`clump_scale`, `clump_count`,
   `strand_noise_amp`) and in the crown.
3. **Bands 0-4 stay −0.18…−0.37 narrow.** The clay's width there is its big
   spiky crown mass projecting laterally, above the `side` mask's reach —
   `crown_lift` / `crown_spike_noise` territory, reserved.
4. **Bands 11-13 stay +0.31…+0.48 too wide** — hair hanging past the jaw where
   the clay tapers to 1.21. `ear_clearance` is the wrong lever (C5). `hem_tuck`
   is the right shape of tool and is **inert on this hero** — it acts on roots
   below 0.60 normalised height and `root_bands.below_0.60` is **0**.
5. Raise `front_metrics.BORDER` to 14 and re-baseline all agents in one commit.

---

## ⚠ THE LOOP'S `.abc` ARGUMENT IS SILENTLY DISCARDED

The loop command every agent was briefed with passes an out-path
`exports/<N>.abc`. **`edit_engine.py` never writes it.** It unpacks the argument
at line 603 (`src, params_path, out_blend, out_abc, log_path = tail[:5]`) and
`out_abc` appears nowhere else in the file; `grep -c alembic_export` returns
**0**. Only the `.blend` is saved.

So `hero/groomloop/exports/` contains no `sides_*.abc` and never could. The
`iter_*.abc` files there were written by `export_abc.py`, which its own docstring
calls "the ONE export path" and which also runs the **mandatory degenerate cull**
— UE asserts `CurveNumVertices >= 2` and an unculled export has already killed an
editor on this project.

Not a failure of any cycle here, and nothing was lost: the shipped groom is
`blends/sides_07.blend`. But **anyone who assumes a cycle produced an `.abc` gets
a stale file or none**, and taking the winner to UE needs a separate
`export_abc.py` run with the cull. I did not run it — picking the winner across
agents comes first, and an unculled export is the one step here with a
known editor-crash mode.
