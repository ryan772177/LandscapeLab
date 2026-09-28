# AGENT_nape — back/nape of the hero groom, 2026-08-22

Owns: `nape_length_scale`, `layer_falloff`, `hem_tuck`.
Base: `hero/groomloop/params/hero_032.json`. Source: `hero_src/hero_base.blend`.

**RESULT: `hem_tuck` 0.02 -> 0.16. taper_ratio 0.8989 -> 0.5924 against a
0.5533 reference target — 87% of the gap closed, on the one metric that
separates "short at the back" from "tapered at the back".** The other two
knobs were tested and REJECTED, each for a measured reason.

---

## 0. THE ROOT CENSUS: THE TWO SOURCES DISAGREE BY 28x, AND BOTH ARE RIGHT

The brief said this region has ~622 roots. The two declared sources disagree:

    survey/survey_head.json  region_census.nape.roots_w>0.5   18,531
    logs/hero_032.json       stats.region_curve_counts.nape      661

I reproduced BOTH numbers from one root cloud with an independent probe
(scratchpad `nape_census_probe.py`, 48,000 roots out of `hero_base.blend`,
frame taken from the surveyor so the frame is not a variable):

    A  survey as declared     fwd ss(-0.20,-0.75) * up ss(-0.70, 0.10)   18,531  <- matches survey
    B  survey, up transposed  fwd ss(-0.20,-0.75) * up ss( 0.10,-0.70)      284  (weight_sum 621.9)
    C  engine (edit_engine    fwd ss(-0.10,-0.70) * (1 - ss(-0.55,0.15))     661  <- matches engine
       .py:320)

**Neither producer is buggy; the DECLARATION is.** `survey_head.py:273`
writes nape `up: [-0.70, 0.10]` — an ASCENDING smoothstep, so it weights
roots that are HIGH on the skull. Every other survey range that means
"descending" is written descending (`side_R side: [-0.25,-0.80]`), so the
nape `up` endpoints are transposed relative to their own convention. As
declared, the survey's "nape" selects the **occiput/upper back**, which is
why it counts 18,531 — almost exactly the crown's 18,076.

The transposed reading (arm B) has **weight_sum 621.9**, which is where the
brief's "622 roots" came from. It is a weight sum, not a root count.

**Recommended fix (not mine to make):** `survey_head.py:273` nape `up`
`[-0.70, 0.10]` -> `[0.10, -0.70]`. That makes the surveyor agree with the
engine and stops the census advertising 28x the material that exists.

### How much material is actually down there — measured, mask-independent

    root up range (normalised)          [-0.5915, +1.0232]   nothing below -0.59
    roots at the back (fwd < -0.20)               24,571
      ... of those, below up = -0.55                  10
      ... below up = -0.30                           575
      ... below up =  0.00                         2,299
    back-root up percentiles       p0 -0.568  p1 -0.458  p5 -0.170  p50 +0.515

`preview_hair.py` corroborates from its own normalisation:
`root_bands.below_0.60 = 0`, `lower_0.60-0.70 = 1,381`.

**Verdict: the region IS stylable, but not through the nape mask.** The back
of the head has 24,571 roots; they simply sit high (median up +0.515). The
nape hem is therefore made of TIPS falling from occiput-rooted strands, not
of roots in the nape band. That distinction is what decided the session.

---

## 1. THE INSTRUMENT: `rear_metrics.py` REFUSED, CORRECTLY

    python scripts/hero_face/likeness/rear_metrics.py --image .../preview_back.png
    -> mask is 0.751 of frame, outside [0.005, 0.50]   EXIT 4

Measured cause, not tuning: on `preview_back.png` the **background luma is
58.5 and the hair luma is 51.9**. They are 6.6 apart and share one histogram
bin holding 69% of the frame. No `--luma-max` separates them; lowering it
would only move the failure. This is the third instance of the rear-rubric
mask class (after the forest blob and the hollow ring) and the first where
the refusal fired before any number was quoted.

**Route taken instead:** `preview_hair.py` renders a bare-head control from
the same camera (`preview_back_nohair.png`), so hair = pixels that CHANGED.
That needs no absolute luminance assumption. The mask is binarised and handed
to `rear_metrics.measure()`, so `taper_ratio` / `edge_roughness` /
`width_profile` come from the SAME implementation that produced the reference
constants. Tool: scratchpad `nape_rear.py`.

Corroboration that the mask is the right region: diff mask at threshold 6
covers **18.86%** of frame against `preview_hair.py`'s independently computed
back `hair_px` of **19.23%**. Two instruments, different code, same region.
The mask was dumped and opened every cycle
(`_verify/20260822_agents/_napemasks/`) — clean hair silhouette, no
background, no shoulders, no shadow bleed.

**WHAT THIS LICENSES.** Cycle-to-cycle comparison: sound. Against the
registry's `taper_ratio` 0.5533: indicative — a width ratio travels
reasonably between a photo and a render. Against `edge_roughness` 27.9648:
**NOT comparable and not quoted as such** — that is perimeter/sqrt(area) and
this render resolves individual wisps that a photograph renders as a solid
mass. Our absolute values sit near 60; only their direction is used.

---

## 2. CYCLE LOG

All from the `hero_032` base, one knob per cycle. taper/width from
`nape_rear.py`; scalp and silhouette from `preview_hair.py`.

| cycle | knob | taper_ratio | edge_r | nape_w | crown_w | scalp% | verdict |
|---|---|---|---|---|---|---|---|
| nape_00 | *control, hero_032 verbatim* | **0.8989** | 67.40 | 362.2 | 403.0 | 3.21 | baseline, blunt |
| nape_01 | hem_tuck 0.02 -> 0.10 | 0.7574 | 66.67 | 305.2 | 403.0 | 3.15 | big move, crown untouched |
| nape_02 | hem_tuck -> 0.20 | 0.4378 | 57.27 | 176.0 | 402.0 | 3.25 | overshot, over-pinched |
| nape_03 | hem_tuck -> 0.16 | **0.5924** | 61.54 | 238.8 | 403.0 | 3.22 | **BEST** |
| nape_04 | hem_tuck -> 0.17 | 0.4913 | 59.78 | 198.0 | 403.0 | 3.24 | cliff; see noise note |
| nape_05 | nape_length_scale 1.3 -> 2.2 | 0.4585 | 61.30 | 185.2 | 404.0 | 3.26 | REJECT — rat-tail |
| nape_06 | layer_falloff 0.12 -> 0.22 | 0.5889 | 62.52 | 236.8 | 402.0 | **3.47** | REJECT — no gain, costs scalp |
| nape_07 | nape_length_scale 1.3 -> 1.0 | 0.5995 | 62.64 | 241.0 | 402.0 | 3.22 | no change; keep 1.3 |

Stopped at cycle 7 on the rule-2 condition: cycles 04, 05, 06, 07 are four
consecutive without improvement on `taper_ratio`.

**Width profile, bottom six bands** — the taper made visible:

    nape_00  0.92 0.91 0.91 0.91 0.90 0.88   holds full width to the last row = BLUNT
    nape_03  0.92 0.78 0.72 0.68 0.62 0.34   narrows continuously = TAPERED
    reference target                    0.42 (last band)

---

## 3. MECHANISM, ONE SENTENCE PER KNOB

**`hem_tuck` — the only lever that works, and NOT for the reason the brief
gave.** It pulls tips radially toward the head axis, ramped `t^1.6` so the
effect is at the tip, and gated on `low = clip(-up, 0, 1.5)` — i.e. on ROOT
HEIGHT, not on the nape mask. That gate admits ~3,900 roots (every root with
`up < 0`), roughly **6x the engine nape mask's 661**, which is exactly why it
can move a silhouette the nape mask cannot. The brief predicted it would be
"very likely INERT here"; it is measured to be the strongest knob I own, and
the prediction was based on the 0.60-normalised-height band, which is a
different coordinate from the `up` the code actually tests.

**`nape_length_scale` — measured near-inert in the useful direction, harmful
when pushed.** Across 1.0 / 1.3 / 2.2 it moves taper 0.5995 / 0.5924 / 0.4585.
At 2.2 (+69% length) it added only **+1.7% of back hair pixels** and produced
a single narrow dark spike hanging down the centre of the neck — a rat-tail,
not the reference's full-depth layering. That is the low-material signature:
661 curves clustered centre-back-low lengthen into one clump. Left at 1.3.

**`layer_falloff` — rejected on cost.** `grade = 1 - layer_falloff * up`, so
it shortens the crown as much as it lengthens the nape. 0.12 -> 0.22 moved
taper by **-0.0035** (inside the discretisation noise below) while pushing
`scalp_exposed_pct` 3.22 -> 3.47, my watch metric, the wrong way. Left at 0.12.

---

## 4. THINGS THAT WOULD MISLEAD THE NEXT SESSION

**`taper_ratio` has a discretisation cliff between hem_tuck 0.16 and 0.17.**
0.16 -> 0.5924, 0.17 -> 0.4913, 0.20 -> 0.4378. `nape_w` is the mean of the
lowest four of twenty bands, and near a wispy point small changes flip
whether the last band is populated at all. **Treat any taper difference below
about 0.05 as noise.** 0.16 was chosen over 0.17 on residual (+0.039 vs
-0.062) AND on the render, not on the metric alone. Do not chase 0.5533 with
finer steps — that is tuning to a number.

**`hem_tuck` IS NOT NAPE-SCOPED, and it bills other regions.** Because it is
gated on `up < 0` it also tucks low-rooted FRONT and SIDE strands. At 0.16,
measured against the control:

    front hair_px   98,519 -> 90,227   -8.4%
    side  hair_px  178,838 -> 168,053  -6.0%
    back  hair_px  155,728 -> 145,773  -6.4%
    scalp midline    5.57% -> 4.50%    improved
    scalp lateral    2.41% -> 2.79%    slightly worse
    over_face / tips_in_face / flare   unchanged

The side and fringe agents should be told: **hem_tuck 0.16 costs them ~6-8%
of silhouette.** If that is unacceptable, hem_tuck 0.10 gives taper 0.7574 at
front -5.8% / side -2.7% — roughly half the taper for a third of the cost.

**The brief's watch value for `scalp_exposed_pct` was wrong.** It stated
"currently ~0.5%". The measured control is **3.21%**, and it stated "above 3%
is a regression", which the baseline already exceeds. I tracked change
against the measured 3.21 instead; the shipped setting is 3.22, i.e. flat.

---

## 5. WHAT WOULD ACTUALLY FINISH THIS REGION

The remaining gap is not tuneable from my three knobs. The reference wants
full-depth layering down the nape; this groom has **10 roots below up=-0.55**
and none below -0.59, so there is no hair rooted where a nape hem grows.
Everything achieved above is occiput-rooted tips tucked inward to fake the
taper — which works for the silhouette and will not survive close inspection
or motion.

The fix belongs to `scripts/blender/author_hero_hair.py`, which owns root
placement and is not mine to edit: **extend the root cap further down the
occiput**, to roughly `up = -0.75` (about z 162 cm on this head, against the
current floor of z 163.5), so that the nape band has material of its own.
That would also make `nape_length_scale` a real knob instead of a rat-tail
generator, and would let the surveyor's corrected nape mask select something.
