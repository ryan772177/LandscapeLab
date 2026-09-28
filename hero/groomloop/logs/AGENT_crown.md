# AGENT_crown — the crown region

Knobs owned: `crown_lift`, `crown_spike_noise`, `gravity_crown_shield`.
Target: `hero/reference/appearance_groom_clay.jpg`, primary axis `crown_lift_frac`
(clay **0.5524**, v032b baseline **0.4198**).

**RESULT: `crown_lift_frac` 0.4198 -> 0.5510 against a clay target of 0.5524.**
All three watch axes held. 6 cycles of a permitted 8; stopped deliberately, see §5.

---

## 1. THE CONTROL REPRODUCED THE PUBLISHED BASELINE EXACTLY

`crown_01` is byte-equal in knobs to `hero_032.json`. Measured against the
published `v032b_front.json`:

    crown_lift_frac  0.4198 / 0.4198      band ear   0.3064 / 0.3064
    central eye      0.0167 / 0.0167      roughness 81.8578 / 81.8578
    frame_px    [888,900] / [888,900]     face_h      343 / 343

Identical on every axis, so every delta below is single-variable inside this
agent's own pipeline. Worth the cycle it cost.

## 2. TWO INSTRUMENT FAULTS FOUND, AND THEY CHANGE THE NUMBERS

**(a) `front_metrics.py`'s `face_top` breaks on a tall crown, and it fails in the
direction that HIDES success.** `face_top` is the first clay-mask row wider than
`max(12, 0.08*maxwidth)` = 20 px. The script's own docstring records the trap —
specular highlights on dark hair clear the clay threshold a few pixels at a time
— and the 20 px floor holds for a low crown and stops holding once the crown is
tall and wispy enough to put 20 lit pixels on one row.

Measured on `crown_04`: `face_top` jumped **189 -> 125** with the chin unchanged
at 532, inflating `face_h` 343 -> 407 and deflating every ratio that divides by
it. The raw reading was `crown_lift_frac` **0.3071**, which reads as a collapse.

It was caught because a second representation disagreed: `height_gain_cm`
(geometry, from `preview_hair.py`) went UP 5.11 -> 5.94 in the same run. Locating
the offending pixels settled it — the topmost "clay" rows sit at **x 279-352**,
the upper-left crown periphery, against a face centre of x=433. Rim-lit hair, not
forehead.

The head mesh and camera are identical in every render in this series, so the
forehead row is a CONSTANT. Everything in §3 is rescored at a fixed
`face_top=189 / chin=532`. `front_metrics.py` was NOT edited — it is the shared
instrument every agent's numbers are compared through, and changing it mid-loop
would silently break comparability. The rescoring lives in the agent's own
side-car.

**(b) `crown_lift_frac` is a bare `.min()` on hair rows — a one-pixel statistic.**
Reported at three widths below (1 px is the published definition and the one the
clay target was measured with; 4 and 20 px are robustness cross-checks, read on
BOTH subjects by the same code).

**Consequence, stated plainly: the clay itself is clipped at its frame top**
(hair_top 0 at both 1 px and 4 px), so the target 0.5524 is a FLOOR, not a
bracket. At the best iterations our hair also reaches the frame top, so
`crown_lift_frac` saturates at 0.5510 and cannot resolve an overshoot.

## 3. THE CYCLE LOG — one knob per cycle, fixed frame

    iter      lift  spike  shield |   clf1   clf4  clf20  top1 | cc_eye  band_ear   rough
    CLAY         -      -       - | 0.5524 0.5524 0.5013     0 | 0.0014    0.3042    92.4
    ---------------------------------------------------------------------------------------
    crown_01  0.016  0.010   0.75 | 0.4198 0.4111 0.4023    45 | 0.0167    0.3064    81.9   control
    crown_02  0.032  0.010   0.75 | 0.4461 0.4402 0.4286    36 | 0.0167    0.3066    82.3   lift x2
    crown_03  0.032  0.035   0.75 | 0.5044 0.5044 0.4636    16 | 0.0167    0.3094    97.0   spike
    crown_04  0.032  0.035   1.00 | 0.5510 0.5394 0.5190     0 | 0.0167    0.3095   101.1   <-- BEST
    crown_05  0.032  0.024   1.00 | 0.5102 0.4898 0.4723    14 | 0.0167    0.3071    88.4   spike down
    crown_06  0.058  0.024   1.00 | 0.5510 0.5510 0.5510     0 | 0.0167    0.3076    97.7   lift up

    scalp_exposed_pct   3.21 -> 3.14 -> 3.13 -> 3.10 -> 3.07 -> 3.07   (IMPROVED throughout)
      midline zone      5.57 -> 5.09 -> 5.14 -> 4.98 -> 4.87 -> 4.66
    height_gain_cm      3.52 -> 4.07 -> 5.11 -> 5.94 -> 5.17 -> 5.94
    hair_over_face_px  14437 ->14426 ->14421 ->14422 ->14421 ->14424   (flat: crown does not reach the face)

**MEASURED GAIN RATES**, both solved rather than groped for:

    crown_lift          +0.0164 of crown_lift_frac per cm   (only ~30% of nominal
                        lift becomes silhouette height)
    crown_spike_noise   +0.0371 per cm   -- 2.3x cheaper per cm, because
                        crown_lift_frac is a MAX statistic and a variance op
                        raises the topmost row far more cheaply than a mean op
    gravity_crown_shield 0.75 -> 1.00 returned ~1.1 cm of withheld gravity_drop
                        as free height and IMPROVED midline scalp 5.14 -> 4.98

## 4. WHY `crown_04` AND NOT `crown_06`

By mean relative error across all five measured axes they are a dead heat —
**crown_04 0.0344, crown_06 0.0345** — a separation of one ten-thousandth, which
is noise. The tie-break is not a score:

`crown_06`'s `clf20` is **0.5510** — its hair reaches the frame top even at full
20 px width, so it is saturated on the ROBUST measure too and there is no
headroom left. Any height another agent adds (fringe, global length, side scale)
would clip it and make the shared instrument unreadable for everyone.
`crown_04` keeps 11 rows of headroom at 20 px and 4 rows at 4 px.

`crown_06` is the better answer on roughness (97.7 vs 101.1) and on `band_ear`,
and if the frame is ever widened it is worth re-testing.

## 5. WHY IT STOPPED AT 6 OF 8

Not fatigue — the remaining move is provably unavailable with these three knobs.
`crown_05` walked the spike-light path and `crown_06` the lift-heavy path from
the same optimum; both scored worse or tied. At the clay's crown height this
groom's silhouette is rougher than the clay's (101 vs 92) no matter which of my
knobs carries the height, because the height is made of INDIVIDUAL STRANDS and
the clay's is made of CLUMPS. Clumping is `clump_scale` / `clump_count`, which
belong to another agent.

## 6. THE LOOK, STATED HONESTLY

The crown now stands up and its top edge is genuinely ragged rather than the
baseline's smooth combed dome. It does NOT read as the clay's chunky separated
locks — it reads as fine frizz radiating from the skull. `crown_spike_noise`
displaces each strand along a per-strand sine with no spatial coherence between
neighbours, so it produces raggedness without gathering. Raggedness and
chunkiness score the same on `edge_roughness` and look completely different, and
the score alone would have told me to push spike harder. It should not be pushed
harder: `edge_roughness` already overshoots the clay by 9%.
