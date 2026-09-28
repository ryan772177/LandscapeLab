# Displacement: what the numbers say, and why the headline metric is the wrong one

**Companion to `20260811_displacement_measurement.txt`. Read that first —
this file interprets it and does not restate it.**

## The verdict in one line

**Displacement works, dramatically, and EDGE ENERGY SAYS IT GOT WORSE.**
Mean edge energy is **−1.02%** across 19 stations. The frames say
otherwise, and the frames are right.

## The instrument the checklist prescribed is not sufficient here

The plan said *"compare with EDGE ENERGY, not mae — mae cannot tell
sharper from differently blurry"*. That reasoning is sound and edge
energy is genuinely the better instrument **for a resolution change**.
It is the wrong instrument for **this** change, and the reason is
structural rather than a tuning problem:

- **Mean gradient magnitude rewards high-frequency ALBEDO contrast.**
- **Displacement replaces stretched high-contrast texture with real
  GEOMETRY, whose shading varies SMOOTHLY across facets.**

So at close range the change *trades away* the very quantity the metric
counts, while adding the thing it was commissioned to find. The metric is
arithmetically correct and answers a question nobody asked — the
misleading-denominator shape (NN22) in a different container.

**The discriminating pair is `sweep_0060`, and it is not subtle.**
That station lost the most edge energy of all 19 (**−23.11%**). Opening
the two frames:

| | |
|---|---|
| `5080sp100` | a FLAT plane wearing a smeared, high-contrast rock texture — sharp albedo streaks everywhere, no form |
| `5080disp` | genuine three-dimensional relief: ledges, facets, crenellation, and self-shadowing |

The second is enormously better and measures 23% worse. **That single
pair is the strongest evidence in this report, and no statistic here
produced it — opening the artefact did** (NN10).

## The spatial pattern, which is what makes the rest evidence

The result is **bimodal**, not noisy. 14 of 19 stations clear the 2.08%
noise floor derived from a same-settings pair.

**GAINED** — distant, aerial, and small-subject stations:

    lod_near      +12.38%     lod_far       +9.67%     trunk_base   +8.57%
    diag_oblique   +8.23%     verify_aerial +7.08%     sweep_2000   +5.40%
    sweep_0700     +5.26%

**LOST** — ground-level stations with terrain filling the frame:

    sweep_0060    −23.11%     verify_ground −15.23%    sweep_0150  −14.34%
    forest_floor  −13.30%     cliff_face     −5.16%    sweep_1200  −4.10%
    sweep_0350     −3.77%

At **distance**, new relief appears as new *edges* — silhouette against
sky and against other terrain — and edge energy rises. At **point-blank
range** the same relief appears as *smooth shading across facets* that
replaces sharp texture streaking, and edge energy falls. Both signs come
from one mechanism.

**NOT ESTABLISHED, and flagged rather than claimed:** `lod_near` and
`lod_far` are conifer close-ups against sky, and why terrain displacement
moves them by +12.4% / +9.7% is **not explained**. The likely cause is the
ground *behind* the tree changing, but that was not measured. Do not cite
these two as silhouette evidence until someone looks.

## A VISIBLE CHANGE IN THE ROCKS — AND I CANNOT YET SAY WHICH CAUSE

`forest_floor` shows **many more rocks on the ground** than the baseline
does: the baseline has a scatter of large, pale, seated boulders; the new
frame has dozens of smaller, darker rocks across the foreground and
midground.

**TWO EXPLANATIONS FIT, THEY IMPLY OPPOSITE ACTIONS, AND THIS SESSION DID
NOT DISCRIMINATE BETWEEN THEM.** Recorded as an open question rather than
resolved, because the first reading I reached for was the second one and
it may well be wrong.

**(a) GRASS-SYSTEM CLUTTER that was not there before.** `GroundClutter`
is a grass species — `SM_Boulder05a` and `SM_River_Rock_01` at 10 per
10 m², cull 40 m — and *many small dark rocks at high density* is exactly
what that looks like. Supporting: the rebuild **modified
`GT_alpine_GroundClutter.uasset`**, and CURRENT STATE recorded the
clutter material rebuild as still owed and attended. If so this is not a
displacement effect at all; it is the clutter finally spawning, and it is
a WIN wearing the costume of a regression.

**(b) HERO BOULDERS EXPOSED by the displaced surface.** Displacement
moves the **render** surface only — collision stays on the heightfield
and all 171,069 instances are grounded to the heightmap. The 759 hero
boulders are embedded **0.18–0.40 m** (R12) against a **±0.40 m**
amplitude, the *same order*, so wherever the surface drops locally an
embedded rock is exposed. If so it is a real cost that scales with
amplitude.

**Against (b), and this is why it is not the default reading:** the new
rocks are numerous and small, while the hero boulders are 759 across
6,503 ha and are the *large pale* ones already visible in the baseline.
Density argues for (a).

**The discriminating test is cheap and was not run:** count
`Medium_Boulder_001` instances in frame, or capture once with
`grass.Enable 0`. If the rocks vanish, it is (a). Until then, BACKLOG's
"re-derive rock embedment" item is **conditional on (b)**, not
established — and the render/collision divergence remains real as
*mechanism* whether or not it is what this frame shows.

## AND A DEFECT FOUND WHILE CHECKING MY OWN ASSERTION

`displacement_scaling.center` was set to 0.5 and justified — in a code
comment *and* in a `prove_gates` assertion — as *"the value the height
maps are neutral at, so a missing sample displaces by zero"*.

**That is a claim about pixels, and it is false.** Measured over the five
surface height maps:

| map | mean | offset at magnitude 0.16 |
|---|---|---|
| Ground037 | 0.5257 | **+2.06 cm** |
| Rock051 | 0.6005 | **+8.04 cm** |
| Snow006 | 0.6490 | **+11.92 cm** |
| Rock026 | 0.7602 | **+20.82 cm** |
| Rock063 | 0.7311 | +18.49 cm *(not in this material)* |

Not one is centred on 0.5. Consequences:

1. Every surface takes a **constant upward lift** — up to +21 cm against
   a ±40 cm amplitude, i.e. **half the signal is a DC offset**.
2. The lift **differs per surface**, so there is a step of up to ~19 cm
   at layer boundaries that is not real relief.
3. A fully-mipped sample returns the map's **mean**, not 0.5, so the
   degraded-state guarantee does not hold either.

`center` is a single material-level scalar and the maps disagree, so no
value of it is neutral for all of them. **The fix is to normalise each
map in the graph** — subtract its own mean before compositing. Logged as
the next unit; the false claim has been removed from both the comment and
the gate in the same commit that records it.

## What would actually settle "is there more silhouette"

Edge energy conditioned on the **horizon band** rather than the whole
frame, or a depth-buffer statistic. Both are unbuilt. Until then the
honest statement is:

> Displacement is confirmed working by rendered pixels at close range,
> and confirmed to add edge structure at distance on 7 stations. The
> whole-frame mean is **not** a summary of its value, and should not be
> quoted as one.
