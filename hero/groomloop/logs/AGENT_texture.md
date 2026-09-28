# AGENT_texture — global texture and mass

Knobs owned: `clump_scale`, `clump_count`, `strand_noise_amp`, `strand_noise_freq`,
`flyaway_density`, `flyaway_amp`, `tip_trim_variance`, `global_length_scale`,
`stray_clamp_m`.

Targets, both REDUCING: `edge_roughness` 102.07 -> 88.44 (clay),
`hair_area_over_face_area` 1.5292 -> 1.2471 (clay).

**RESULT — `tex_08`, ACCEPT, all three vetoes clear.**

    edge_roughness   102.0669 -> 98.3835    (-3.68, 27% of the asked-for gap)
    mass               1.5292 -> 1.3164     (-0.213, 75% of the asked-for gap)
    WEIGHTED ERROR     0.2717 -> 0.0936     (whole head, judge.py)

8 cycles of 8. Two rejected on vetoes; the rejections are the finding.

---

## 1. THE DELTA (texture knobs only)

```json
{
  "clump_scale": 0.6,
  "strand_noise_amp": 0.0,
  "flyaway_density": 0.0,
  "stray_clamp_m": 0.11
}
```

Deliberately UNCHANGED: `clump_count` 180 (60 was measured worse, cycle 1),
`flyaway_amp` 0.01 (inert once density is 0), `tip_trim_variance` 0.6 (both
reductions breached a veto, cycles 4 and 5), `global_length_scale` 1.0,
`strand_noise_freq` default.

## 2. BASELINE vs BEST — the judge's full table

| AXIS | W | CLAY | ROUND2_BASE | rel err | tex_08 | rel err |
|---|---|---|---|---|---|---|
| crown height | 2.0 | 0.7535 | 0.7721 | 0.025 | 0.7707 | 0.023 |
| fringe: forehead | 2.0 | 0.0963 | 0.1604 | 0.666 | 0.1004 | **0.043** |
| fringe: brow | 2.0 | 0.0017 | 0.0351 | 0.668 | 0.0158 | **0.282** |
| width at forehead | 1.0 | 0.5971 | 0.5838 | 0.022 | 0.5421 | 0.092 |
| ear coverage | 1.5 | 0.2341 | 0.2817 | 0.203 | 0.2365 | **0.010** |
| jaw coverage | 1.5 | 0.2352 | 0.2352 | 0.000 | 0.2082 | 0.115 |
| **chunk separation** | 2.0 | 88.4431 | 102.0669 | 0.154 | **98.3835** | **0.112** |
| **overall mass** | 2.0 | 1.2471 | 1.5292 | 0.226 | **1.3164** | **0.056** |
| | | | **0.2717** | | **0.0936** | |

| VETO | LIMIT | ROUND2_BASE | tex_08 |
|---|---|---|---|
| hair in his eyes | <= 0.0040 | 0.0015 | 0.0007 |
| scalp exposed % | <= 6.0 | not measured | 2.92 |
| flare not drape | <= 0.78 | not measured | 0.639 |

The baseline's veto row is blank because no preview stdout was published with
`ROUND2_BASE_front.json`; its front metrics reproduce exactly, and its vetoes
are stated as unmeasured rather than assumed. Every candidate below carries its
own.

## 3. THE CYCLE LOG — one knob per cycle, every cycle attributable

| # | cand | knob delta (from) | rough | mass | err | eye | scalp | flare | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0 | ROUND2_BASE | — | 102.07 | 1.5292 | 0.2717 | 0.0015 | — | — | REJECT (unmeasured vetoes) |
| 1 | tex_01 | `clump_count` 180->60 (base) | 102.09 | 1.5706 | 0.4087 | 0.0016 | 0.99 | 0.682 | ACCEPT, **worse** |
| 2 | tex_02 | `clump_scale` 0.35->0.60 (base) | **99.51** | 1.4623 | **0.1298** | 0.0007 | 1.81 | 0.674 | ACCEPT |
| 3 | tex_03 | `clump_scale` 0.35->0.85 (base) | 101.67 | 1.4092 | 0.3085 | **0.0121** | 1.58 | 0.676 | **REJECT — eye** |
| 4 | tex_04 | `tip_trim_variance` 0.6->0.25 (02) | **88.79** | 1.3951 | 0.2064 | 0.0005 | **9.61** | 0.674 | **REJECT — scalp** |
| 5 | tex_05 | `tip_trim_variance` 0.6->0.45 (02) | 95.03 | 1.4490 | 0.3514 | **0.0135** | 2.83 | 0.674 | **REJECT — eye** |
| 6 | tex_06 | `stray_clamp_m` 0.13->0.11 (02) | 100.92 | **1.3412** | **0.1098** | 0.0007 | 1.80 | 0.639 | ACCEPT |
| 7 | tex_07 | `flyaway_density` 0.04->0.0 (06) | 99.45 | 1.3425 | **0.1063** | 0.0007 | 3.24 | 0.639 | ACCEPT |
| 8 | tex_08 | `strand_noise_amp` 0.002->0.0 (07) | **98.38** | **1.3164** | **0.0936** | 0.0007 | 2.92 | 0.639 | **ACCEPT, best** |

Deadband: 1.0 on roughness, 0.01 on mass. Cycle 1 is inside both on roughness
(+0.02) and is recorded as NO MOVE, not as a small gain.

## 4. THE MECHANISM, AND WHY MASS IS EASY AND ROUGHNESS IS NOT

`edge_roughness` is `perimeter / sqrt(area)` where perimeter is a 4-neighbour
erosion, so **interior holes count as perimeter**. The dumped mask
(`logs/tex_08_mask.png`, looked at) shows the crown's interior speckled black
with gaps between strands: the bulk of the perimeter is the POROUS INTERIOR of
the hair mask, not its outline.

For a mask of thin strokes of width w, `perimeter ~ 2*area/w`, so

    edge_roughness ~ 2 * sqrt(area) / w

Two consequences, both measured rather than argued:

**(a) Trimming LENGTH cannot fix roughness.** Perimeter and area both scale with
length, so the ratio barely moves and the `sqrt` makes it move the wrong way.
Cycle 6 cut hair pixels 123,421 -> 113,961 (-7.7%) and roughness ROSE
99.51 -> 100.92. This is the single most useful negative result here: `mass` and
`edge_roughness` look like one axis and are not.

**(b) Only MERGING strands or DELETING isolated frizz lowers roughness**, by
raising `w` or cutting perimeter with no area. That is exactly what worked —
`clump_scale` (-2.56), `flyaway_density` (-1.47), `strand_noise_amp` (-1.07).

`clump_scale` is non-monotone with a minimum near 0.60: 0.35 -> 102.07,
0.60 -> 99.51, 0.85 -> 101.67. Past ~0.6 the strands collapse into thin ropes
separated by large voids, and the voids are perimeter too.

`clump_count` 180 -> 60 did nothing (cycle 1) and made mass worse. Coarser
lat/long cells put each strand's attractor FURTHER away, so the op spreads mass
laterally instead of gathering it. Chunkiness comes from convergence STRENGTH,
not from cell size, on this partition.

## 5. THE TWO REJECTIONS ARE A REAL COUPLING, NOT BAD LUCK

`tip_trim_variance` is the strongest roughness lever on the board — 0.6 -> 0.25
lands `edge_roughness` at **88.79 against a clay target of 88.44**, rel err
0.004, essentially exact. It cannot be used, and the reason is mechanical.

`scalp_exposed_pct` is geometric, not render-side: a head vertex within 1.5 cm
of a root is exposed if no hair POINT lies within 0.8 cm
(`preview_hair.py:215-241`). `tip_trim_variance` is a symmetric multiplier
`1 + v*(r-0.5)*2`, so it has two halves doing two different jobs:

* its **short** half (`length_mul` min 0.35) is a **scalp blanket** — short
  strands hug the skull and are what keeps points inside the 0.8 cm shell;
* its **long** half (max 2.63) is the **ragged outline**.

Cutting `v` removes both. At 0.25 the outline is perfect and the scalp opens to
9.61 against a 6.0 veto. **The knob cannot be asymmetrised from the params** —
that would need an engine change, and `edit_engine.py` is shared.

`stray_clamp_m` is the asymmetric substitute — a hard cap touches only the long
tail — and it is why cycle 6 took mass to 1.3412 with scalp UNMOVED at 1.80.
It buys mass, not roughness, for the reason in §4(a).

The eye-band breaches at cycles 3 and 5 are non-monotone in the knob
(0.0007 / 0.0121 / 0.0135 / 0.0005 across `clump_scale` 0.60/0.85 and
`tip_trim_variance` 0.45/0.25) and the absolute numbers are small — 0.0135 is
1.35% of a narrow box. Stated as measured, with no mechanism claimed. `tex_08`
sits at 0.0007, a factor of 5.7 inside the bar, so the shipped candidate is not
near that edge.

## 6. LOOKED AT, NOT ONLY SCORED (rule 7)

`ROUND2_BASE/preview_front.png` against `tex_08/preview_front.png`:

* **Improved, and for the right reason.** The fringe now breaks into distinct
  pointed wedges over the brow instead of a continuous frizz curtain, the side
  hair reads as a few chunky pieces rather than one uniform mass, and the wide
  temple flare is gone (`flare_max_ratio` 0.674 -> 0.639). The silhouette is
  tighter without being smoother.
* **NOT fixed: the crown is still a fine spiky halo**, and it looks about as
  ragged as the baseline. See §7.

## 7. WHAT I COULD NOT ACHIEVE, PLAINLY

**Roughness closed 27% of its gap; mass closed 75%.** The residual roughness is
concentrated in the crown halo, and the art note names its cause —
`crown_spike_noise` displaces each strand along its own sine with no coherence
between neighbours. That knob is **reserved to the crown agent**, and at 0.035
it is re-introducing exactly the incoherent high-frequency displacement my
cycles 7 and 8 removed globally. My clumping acts at `t^1.6` on the tip and
cannot gather what a per-strand sine is pushing apart at the same t.

**RECOMMENDATION TO THE COMPOSITOR, offered as a hypothesis and not a
measurement:** `crown_spike_noise` toward 0 on top of `tex_08` is the obvious
next probe for the remaining roughness. I did not test it and must not — a
number I produce by moving a reserved knob is unattributable against the crown
agent's own sweep.

**Second residual: `jaw coverage` regressed** 0.2352 -> 0.2082 (rel err
0.000 -> 0.115) and `width at forehead` 0.022 -> 0.092. Both are the honest
price of `stray_clamp_m` 0.11: capping the longest strands is what took mass
down, and the longest strands are the ones reaching the jaw. Net on the weighted
score it is strongly positive (my two axes are weight 2.0 each against jaw's
1.5), but it is a real cost and the nape/sides agents should know their axes
moved under a global knob.

**Not attempted: `global_length_scale`.** It is a symmetric length lever and
§4(a) shows length cannot move roughness; `stray_clamp_m` already delivered the
mass cut with a better coverage trade. Left at 1.0.

## 8. INSTRUMENTS ADDED (agent-owned; no shared instrument was edited)

    scripts/_tex_mkparam.py   derives a variant, REFUSES any non-texture knob
                              (proven both directions before first use)
    scripts/_tex_run.sh       edit -> preview -> front_metrics -> judge, one cycle

No fault was found in `front_metrics.py`, `judge.py` or `preview_hair.py` this
round. The `tex_08` mask was dumped and opened before its numbers were believed:
clean, no border or title-strip contamination, face/chin datums correct.

## 9. REPORTED, NOT PATCHED — a shared-instrument observation

`edit_engine.py`'s `face_repel` block reports `points_in_zone_before` and
`points_in_zone_after` as **exactly equal on every candidate from every agent**:

    crown_01 4622 -> 4622    fringe_02 5545 -> 5545    tex_02 5692 -> 5692
    crown_06 4561 -> 4561    sides_00  4622 -> 4622    tex_08 5666 -> 5666

Six candidates, four agents, six exact ties. Either the op moves nothing at
`face_repel` 0.5, or the counter is taken at a point where it cannot see its own
effect. This is the guard the engine's own comment calls "the fifth guard on
this region and the only one that acts AFTER styling", so a self-report of zero
effect is worth someone's attention — the hair-in-eyes veto is currently being
held by other mechanisms, whichever it is.

NOT INVESTIGATED and NOT PATCHED: `edit_engine.py` is shared, and changing it
mid-loop would break comparability across all four round-2 agents. Raised for
the compositor.
