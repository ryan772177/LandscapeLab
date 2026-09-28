# GPU readings — 2026-08-08, attended, editor viewport

Editor PID 25720, `/Game/Alpine` opened cold from disk this session.
Material `M_AutoLandscape` sha256 `3d38821e…` (129,174 B) — triplanar LIVE,
`_wz_axis` fixed. Foliage at the reverted 157,554 conifers / 759 boulders.

**CALIBRATION CLASS** — travels with every number here. Editor viewport,
Intel Core Ultra 5 225U integrated GPU, **RenderRes 100% (1049×593)**,
editor perf config, Lumen off. **NOT shipping, NOT PIE, NOT the future
5080.** Stations parked by `scripts/park_viewport.py`, every park verified
to **0.000 cm** worst-axis error against `recipes/alpine.json`.

## THE SCENE MUST SETTLE, AND THE FIRST READING IS ALWAYS WRONG

Prims after parking `sweep_0060`: **121.7K → 81.3K → 73.3K → 73.3K**. The
scene drains for roughly three readings before steady state. Everything
below uses SETTLED readings only, and **two readings are comparable only
if their Prims agree** — that is the validity gate, and it is what caught
the first attempt at this measurement reporting clouds as *cheaper* than
no clouds.

## sweep_0060 — six readings

| # | clouds | Frame | Draw | **GPU** | Prims | Draws | |
|---|---|---|---|---|---|---|---|
| 1 | OFF | 48.38 | 48.35 | 44.51 | 121.7K | 1786 | *settling — discard* |
| 2 | ON | 46.10 | 46.09 | 42.58 | 81.3K | 1754 | *settling — discard* |
| 3 | ON | 45.70 | 45.66 | **41.98** | 73.3K | 1751 | settled |
| 4 | OFF | 45.04 | 45.00 | **40.94** | 73.3K | 1747 | settled |
| 5 | OFF | 43.60 | 43.56 | **39.88** | 73.3K | 1746 | settled |
| 6 | ON | 46.08 | 46.07 | **42.40** | 81.3K | 1754 | settled |

**NOISE FLOOR, measured not assumed:** the OFF/OFF pair (#4 vs #5) differs
by **1.06 ms** at identical Prims. Any claim smaller than that is noise.

    OFF mean 40.41   ON mean 42.19   ->  clouds +1.78 ms GPU  (+4.4%)

## sweep_2000 — settled pair

| clouds | Frame | Draw | **GPU** | Prims | Draws |
|---|---|---|---|---|---|
| OFF | 79.12 | 79.08 | **75.50** | 284.2K | 1976 |
| ON | 86.14 | 86.11 | **81.98** | 284.3K | 1982 |

    clouds +6.48 ms GPU  (+8.6%)   Prims matched to 0.04%

**Corroborated by a field that is not GPU time:** Draws separate with NO
OVERLAP at both stations — OFF {1746, 1747, 1976} vs ON {1751, 1754,
1982}, clouds consistently adding ~6 draw calls. Two different quantities
agreeing that the configs differ beats the millisecond alone.

# FINDING 1 — R13's CLOUDS PREMISE IS MEASURED FALSE

R13 ADDENDUM rules clouds **OFF for interactive** on the grounds that
*"75-95 ms baseline leaves zero headroom; a per-pixel volumetric on a
saturated iGPU takes the viewport from slow to unusable."*

Measured: **+4.4% and +8.6% of GPU time.** At the wide station the frame
goes 79.12 → 86.14 ms — **12.6 fps versus 11.6 fps**. That was never the
difference between usable and unusable, because **the viewport is unusable
in both states.** The ruling optimised a term worth 8% and left the other
92% unexamined.

The ADDENDUM asked for exactly this measurement and said not to re-rule
without it. It now exists, so **the ruling is re-openable** — the standing
config can keep clouds off for other reasons, but not for this one.

# FINDING 2 — BOTH STATIONS ARE DRAW-THREAD BOUND, WHICH INVERTS R13's LEVER

Every settled reading, both stations, unanimous — Frame tracks **Draw**,
with the GPU 3.5-4 ms behind:

    sweep_0060  #3  Frame 45.70  Draw 45.66  GPU 41.98
                #4        45.04       45.00      40.94
                #5        43.60       43.56      39.88
                #6        46.08       46.07      42.40
    sweep_2000  OFF       79.12       79.08      75.50
                ON        86.14       86.11      81.98

R13 records the opposite and draws a conclusion from it: *"GPU-bound at
both stations … the cost is PER-PIXEL SHADING — terrain material plus
foliage — not scene bloat. That distinction matters: it means the lever is
shader/material cost and resolution, not instance counts or draw
batching."*

At steady state the draw thread is the critical path, so **the lever is
the thing R13 rules out.** A shader that cost nothing would not shorten
these frames.

**HOW THE ORIGINAL CONCLUSION HAPPENED, and I nearly repeated it.** My
first `sweep_2000` reading — the unsettled one — showed **Draw 0.02 ms**,
which is not a plausible draw-thread time. Taken at face value it makes
the frame look purely GPU-bound. The settled value is **79.08**, nearly
four thousand times larger. The same unsettled-first-frame defect produced
both my contaminated baseline and, plausibly, R13's "GPU-bound at both
stations".

**SCOPE, HONESTLY.** This is an EDITOR viewport measurement and the editor
draw thread carries editor-only work. It firmly changes the EDITOR
conclusion. It does **not** establish that a shipping build is draw-bound,
and it does not license a foliage-reduction campaign on its own — that
needs a PIE or packaged reading, which is a different calibration class
and does not yet exist. What it does retire is the claim that this project
has *measured* its frame cost to be per-pixel shading.

# STILL NOT MEASURED — the triplanar cost itself

Isolating it needs a build at `material.triplanar.layers = []`, a reading,
and a rebuild back. `resource_guard` reported **1.4 GB free of 15.4**
against the builder's 4.0 GB floor, on a machine that has lost its GPU to
a driver timeout once. Deferred on RAM, not on difficulty.

**And Finding 2 changes what that measurement can even show.** If the
draw thread is the critical path at both stations, triplanar's extra two
rock albedo samples may be invisible in FRAME time while still costing
real GPU milliseconds. The reading to take is **GPU Time**, not Frame, and
the expectation should be set accordingly — otherwise a genuine cost gets
recorded as "free".

# THE 2026-08-06 NUMBERS ARE RETIRED AS A COMPARISON BASIS

`sweep_2000` 94.45 ms and `sweep_0060` 75.71 ms were taken at **971×752**
(730,192 px) with clouds ON and triplanar INERT. Today is 1049×593
(622,057 px). Normalising per-pixel looks principled and is still wrong:

    sweep_2000   1.2935 -> 1.3256 ms/Mpx    +2.5%
    sweep_0060   1.0369 -> 0.7155 ms/Mpx   -31.0%

**A material cost cannot be +2.5% at one station and −31% at another.**
Corroborating: `sweep_0060` Prims fell 302.8K → 121.7K while Draws ROSE
1255 → 1786. Only A/B pairs taken inside one session, at one viewport
size, with matched Prims, are used above.
