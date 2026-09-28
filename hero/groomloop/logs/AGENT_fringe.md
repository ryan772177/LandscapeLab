# AGENT_fringe — fringe region iteration log

Owner: FRINGE AGENT. Knobs: fringe_length_scale, fringe_clump_count,
fringe_gap_strength, fringe_forward_pull, fringe_zone_fwd, fringe_zone_up_lo,
fringe_zone_up_hi, part_close, fringe_pull_ramp, face_repel, face_repel_margin.

Baseline = v032b. Target = clay (`hero/reference/appearance_groom_clay.jpg`).

| axis | v032b | CLAY | direction |
|---|---|---|---|
| central forehead 0.00-0.15 | 0.2085 | 0.2696 | RAISE |
| central brow 0.15-0.28 | 0.0000 | 0.0185 | RAISE (headline) |
| central eye 0.28-0.42 | 0.0167 | 0.0014 | LOWER (already over) |
| band forehead 0.00-0.15 | 0.6387 | 0.7937 | RAISE |

## READ BEFORE TUNING — three mechanisms established from source, not guessed

1. **`face_repel` CANNOT touch the forehead.** Its ramp is
   `g = smoothstep(0, margin, clip(s_brow,0,None))` with
   `brow_n = [0,0,-1]`, `brow_pt.z = 167.241` — so `s_brow > 0` means BELOW
   the brow. Above z=167.241 the repel is identically zero.
   `edit_engine.py:725-736`, zone from `author_hero_hair.py:510-516`.
   A bare forehead is therefore never the repel's fault. It is the fringe ops.
2. **The final stray clamp preserves DIRECTION.** `stray_clamp_m` (RESERVED,
   0.13) rescales an over-long curve *about its root*
   (`edit_engine.py:686-692`), so it shortens reach but every point stays on
   its own root-to-point ray. The forward pull's ANGULAR effect survives the
   clamp intact; `fringe_length_scale` above the clamp is spent for nothing.
   9,982 of 48,000 curves are clamped at baseline.
3. **`fringe_pull_ramp` is the shape knob, `fringe_forward_pull` is only the
   amount.** The pull is `v * pull * t**ramp * w_fringe`
   (`edit_engine.py:486-493`). At ramp 2.0 nothing moves until t≈0.7, so the
   strand hugs the skull down to the hairline and then swings out — a shelf
   hovering off the face with BARE FOREHEAD UNDER IT. See cycle 1.

---

## cycle 1 — fringe_01

delta vs v032b: `fringe_forward_pull 0.052 -> 0.110` (ONE knob)

| axis | v032b | fringe_01 | clay | verdict |
|---|---|---|---|---|
| central forehead | 0.2085 | **0.1748** | 0.2696 | WORSE |
| central brow | 0.0000 | 0.0323 | 0.0185 | overshot |
| central eye | 0.0167 | **0.4819** | 0.0014 | CATASTROPHIC |
| band forehead | 0.6387 | 0.7599 | 0.7937 | better |

REJECT. The render (`_verify/20260822_agents/fringe_01/preview_front.png`) is a
blunt black bar straight across both eyes — the exact "heavy curtain that hides
the face" the brief rules out — **and the forehead under it is still bare.**
That combination is the finding: at `fringe_pull_ramp` 2.0 the pull is spent
entirely in the last third of the strand, so it does not fall DOWN the
forehead, it LEAPS OFF it. More pull at this ramp buys eye occlusion and
nothing else. `face_top` also fell 189 -> 201, which is why central forehead
went DOWN while the hair went up: the band datum rides down with the fringe.

Next: hold pull at baseline and move the RAMP alone.

## cycle 2 — fringe_02   ** the mechanism cycle **

delta vs v032b: `fringe_pull_ramp 2.0 -> 1.1` (ONE knob, pull HELD at 0.052)

| axis | v032b | fringe_02 | clay | verdict |
|---|---|---|---|---|
| central forehead | 0.2085 | **0.2615** | 0.2696 | +0.0530, near target |
| central brow | 0.0000 | 0.0000 | 0.0185 | unmoved |
| central eye | 0.0167 | 0.0165 | 0.0014 | unmoved (deadband) |
| band forehead | 0.6387 | **0.7178** | 0.7937 | +0.0791 |

`hair_area_over_face_area` 1.0743 -> 1.3115 against clay's 1.3008 — matched.

ACCEPT. Two axes moved well past deadband, neither cost axis moved at all, and
NO extra displacement was spent: the same 5.2 cm of pull, distributed earlier
along the strand, lies DOWN the forehead instead of leaping off it. The render
turns a hard hairline arc into a ragged edge with locks breaking downward.

## cycle 3 — fringe_03

delta vs fringe_02: `fringe_forward_pull 0.052 -> 0.075` (ONE knob)

| axis | fringe_02 | fringe_03 | clay |
|---|---|---|---|
| central forehead | 0.2615 | 0.4156 | 0.2696 |
| central brow | 0.0000 | 0.1192 | 0.0185 |
| central eye | 0.0165 | 0.2164 | 0.0014 |
| band forehead | 0.7178 | 0.8356 | 0.7937 |

REJECT — but informative. A +0.023 pull step (44%) took forehead 59% up and
brow from nothing to 6.4x the target. **The pull response is threshold-like,
not linear**, so the usable window sits between 0.052 and 0.075.

## cycle 4 — fringe_04   ** NEGATIVE RESULT, and it closes a lever **

delta vs fringe_03: `face_repel 0.5 -> 1.0` (ONE knob). Run deliberately on
fringe_03's over-covered state, not on the best-so-far: at fringe_02 the brow
axis reads exactly 0.0000 and an experiment that cannot move the number it
measures proves nothing.

| axis | fringe_03 | fringe_04 | delta |
|---|---|---|---|
| central forehead | 0.4156 | 0.4280 | +0.0124 |
| central brow | 0.1192 | 0.1029 | -0.0163 |
| central eye | 0.2164 | 0.1940 | **-0.0224** |
| band eye | 0.7065 | 0.6350 | -0.0715 |

**DOUBLING the repel removed 10% of the eye coverage.** It is a weak lever and
it is NOT selective — it took brow down almost as hard as eye. Two reasons,
both structural: (a) it displaces in Y only, so hair beside the head at eye
height is pushed back and still renders; (b) the metric bands are fractions of
face height below a face_top that the fringe itself pushes DOWN, so at heavy
coverage the "eye" band rides up onto anatomy above z=167.241 where the repel
is identically zero.

CONSEQUENCE: `face_repel` cannot rescue an over-pulled fringe, and it cannot
take central eye from 0.0165 to the clay's 0.0014. Held at the baseline 0.5 for
the rest of the run.

CONSEQUENCE 2, and it decides what "success" can mean here: central eye reads
0.0167 at v032b and 0.0165 at fringe_02 — **identical across a change that
moved both forehead axes hard.** The fringe ops are not what puts hair in that
band; it is side-curtain strands crossing the face, which is the SIDE agent's
territory. 0.0014 is not reachable from my knobs. The honest goal on that axis
is to HOLD ~0.0165, not to hit target.

## cycle 5 — fringe_05

delta vs fringe_02: `fringe_forward_pull 0.052 -> 0.058` (ONE knob)

cf 0.3867 | cb 0.0246 | ce 0.0326 | bf 0.7527 — abs-err 0.1954

Brow lands near target (0.0246 vs 0.0185) but central forehead goes 43% over.
A +0.006 pull step moved forehead by +0.125. REJECT on total error.

## cycle 6 — fringe_06   ** decoupling attempt 1: WHICH roots **

delta vs fringe_05: `fringe_zone_fwd -0.05 -> 0.25` (ONE knob). Fringe curve
count 13,282 -> 7,046.

cf 0.2923 | cb 0.0008 | ce 0.0199 | bf 0.7276 — abs-err 0.1250

REJECT (2nd best overall, but 2 knobs off baseline for a worse score than
cycle 2's 1 knob). **The decoupling FAILED and the reason is worth keeping:**
restricting the fringe to front-hairline roots removed mass and reach TOGETHER.
The crown-recruited strands were the ones reaching lowest — they are longer, so
the same rotation carries their tips further down. Excluding them cost the brow
axis everything (0.0246 -> 0.0008) to buy back 0.094 of forehead.

## cycle 7 — fringe_07   ** decoupling attempt 2: splay the fringe **

delta vs fringe_05: `part_close +0.02 -> -0.02` (ONE knob)

cf 0.3628 | cb 0.0893 | ce **0.1471** | bf **0.7978** — abs-err 0.3138

REJECT. Band forehead landed essentially exactly on clay (0.7978 vs 0.7937),
which is the one thing this knob did well — but every central axis got worse.
**And the mechanism was not the one intended:** splaying pushed hair off the
sides of the face, so measured `face_w` went 232 -> 286, which WIDENS the
central 50% window and pulls side-curtain hair into the central denominator.
Much of that cb/ce rise is the datum moving, not hair arriving. face_w is a
second moving datum on top of face_top; a large lateral move is not cleanly
readable on this rubric.

## cycle 8 — fringe_08   ** decoupling attempt 3: bottom-weighted displacement **

delta vs fringe_02: `fringe_length_scale 1.55 -> 2.10` (ONE knob)

cf 0.3442 | cb **0.0522** | ce 0.0947 | bf 0.6910 — abs-err 0.3043

REJECT at this magnitude, but this is the one mechanism that behaved as
predicted. Pull ROTATES a strand and deposits coverage along the whole
forehead; length scales about the ROOT and extends the strand along its
existing forward-and-down path, adding at the LOWER end. It took brow from a
hard 0.0000 to 0.0522 — the first non-pull route to move that axis at all.
It overshot: 1.55 -> 0.0000 and 2.10 -> 0.0522 interpolates the 0.0185 target
to **fringe_length_scale ~= 1.75**, which was not run (cycle cap).
Note the reserved `stray_clamp_m` damps this knob: clamped curves 9,562 ->
10,312, so part of the increase is discarded at 13 cm.

---

# RESULT

| cand | knob delta vs v032b | c_fore | c_brow | c_eye | b_fore | abs-err |
|---|---|---|---|---|---|---|
| CLAY | — | 0.2696 | 0.0185 | 0.0014 | 0.7937 | — |
| v032b | (baseline) | 0.2085 | 0.0000 | 0.0167 | 0.6387 | 0.2499 |
| fringe_01 | pull 0.110 | 0.1748 | 0.0323 | 0.4819 | 0.7599 | 0.6229 |
| **fringe_02** | **ramp 1.1** | **0.2615** | 0.0000 | **0.0165** | **0.7178** | **0.1176** |
| fringe_03 | ramp 1.1 + pull .075 | 0.4156 | 0.1192 | 0.2164 | 0.8356 | 0.5036 |
| fringe_04 | + repel 1.0 | 0.4280 | 0.1029 | 0.1940 | 0.8356 | 0.4773 |
| fringe_05 | ramp 1.1 + pull .058 | 0.3867 | 0.0246 | 0.0326 | 0.7527 | 0.1954 |
| fringe_06 | + zone_fwd 0.25 | 0.2923 | 0.0008 | 0.0199 | 0.7276 | 0.1250 |
| fringe_07 | + part_close -0.02 | 0.3628 | 0.0893 | 0.1471 | 0.7978 | 0.3138 |
| fringe_08 | ramp 1.1 + len 2.10 | 0.3442 | 0.0522 | 0.0947 | 0.6910 | 0.3043 |

**BEST = fringe_02, a ONE-KNOB delta: `fringe_pull_ramp 2.0 -> 1.1`.**
Total absolute error 0.2499 -> 0.1176, **47% of baseline**. Two axes improved
well past deadband, neither cost axis moved. `hair_area_over_face_area` 1.0743
-> 1.3115 against clay's 1.3008.

**NOT ACHIEVED: central brow is still exactly 0.0000 against a 0.0185 target.**
Every route that raised it (pull in cycles 3/5/7, length in cycle 8) raised
central forehead 5-10x faster and pushed it past 0.2696 before brow cleared the
0.005 deadband. Named next step, predicted not measured: `fringe_length_scale
~1.75` on top of fringe_02, interpolated from the 1.55 -> 2.10 pair.

**ALSO NOT ACHIEVABLE FROM THESE KNOBS: central eye 0.0014.** It reads 0.0167
at v032b and 0.0165 at fringe_02, unmoved by a change that moved both forehead
axes hard — so it is side-curtain hair crossing the face, not fringe. Cycle 4
proved `face_repel` cannot remove it either.
