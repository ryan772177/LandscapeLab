# Content gate (AUDIT S-11) — the prediction treats canopy as opaque

**The threshold is not widened. The model is wrong, and it is wrong in a
way that is measurable and explains itself.**

---

## Where the model lives

`scripts/bench_capture.py:1793-1800`:

    sky   = derived_stations[st]["traced_occlusion"]["pct_sky"] / 100
    slack = still["featureless_fraction"] - sky
    if slack > 0.20:  ->  VOID

The prediction comes from `_verify/bench/<date>/bench_stations_derived.json`,
produced by the station derivation and **not per run** — `bench_capture`
falls back to the most recent file anywhere under `_verify/bench/` when
the run's own date has none. The file in use is dated **2026-09-11**.

## What it assumes

Two assumptions, neither stated at the call site:

1. **A featureless pixel is a sky pixel.** The gate compares TOTAL
   featureless against a SKY-ONLY prediction.
2. **`pct_sky` from the occlusion trace is what the camera will see as
   sky.** The trace classifies each ray as sky / terrain / canopy.

## The measurement, per station, every capture since 2026-09-05

| station | predicted sky | measured featureless | of which sky | of which non-sky | **sky ÷ predicted** |
|---|---|---|---|---|---|
| `mid_slope` (n=16) | 0.5639 | 0.5141–0.9383 | 0.0–0.6091 | — | **0.0×–1.1×** |
| `vista` (n=18) | 0.4646 | 0.4205–0.5843 | 0.107–0.5112 | — | **0.2×–1.1×** |
| `near_ground` (n=76) | **0.0075** | 0.0515–0.8547 | 0.0469–0.1904 | 0.0098–0.0817 | **6.3×–25.4×** |

Recent `near_ground` rows are tight and consistent — predicted 0.0075
against a measured sky fraction of 0.13–0.19, i.e. **17.8×–25.4×**:

    2026-09-13 tint2              pred 0.0075  f_sky 0.1748  non-sky 0.0110  23.3x
    2026-09-14 gr_base            pred 0.0075  f_sky 0.1761  non-sky 0.0132  23.5x
    2026-09-14 grade_after        pred 0.0075  f_sky 0.1822  non-sky 0.0167  24.3x

⭐ **The non-sky featureless fraction is 1–8 %, well inside the 0.20
threshold.** The gate is not tripping on flat terrain. It trips almost
entirely because the SKY PREDICTION IS WRONG.

## Why — and it is one number

The traced occlusion per station:

| station | pct_sky | pct_terrain | **pct_canopy** | observed error |
|---|---|---|---|---|
| `near_ground` | 0.75 | 17.92 | **81.33** | 17.8×–25.4× |
| `mid_slope` | 56.39 | 14.68 | 28.93 | ≤1.1× |
| `vista` | 46.46 | 46.49 | 7.06 | ≤1.1× |

**The error scales with canopy fraction, and only with canopy fraction.**
The one station whose frustum is 81 % canopy is the one station whose
prediction is an order of magnitude low; the two stations with 29 % and
7 % canopy are accurate to within 10 %.

**The trace counts a canopy hit as opaque. The renderer does not.**
Foliage is alpha-tested — leaves have gaps, and sky is visible through a
canopy that stops a ray. So every canopy ray is scored as "not sky" while
a meaningful share of the corresponding pixels render as sky.

Quantified: the prediction misses ≈17.25 points of sky, and those points
come out of the 81.33 % canopy, so **canopy at this station passes
roughly 21 % of its rays through to sky**. That is a testable number, not
a fitted one: it predicts that a station's error should be
≈ 0.21 × pct_canopy, which gives ≈6.1 points for `mid_slope` and ≈1.5 for
`vista` — both inside their observed spread.

## What must NOT be done

Widening 0.20 would make the gate pass at `near_ground` by making it
blind everywhere else. The threshold is doing its job; the comparand is
wrong. `mid_slope` really did read 0.9383 featureless on 2026-09-05,
which is the void this gate exists to catch, and that detection must
survive any fix.

## Two candidate fixes — a ruling, not a tweak

1. **Model canopy porosity in the trace.** `pct_sky_effective =
   pct_sky + porosity × pct_canopy`, with `porosity` MEASURED per foliage
   type from its alpha coverage rather than fitted to this one station.
2. **Compare like with like.** The sidecar already records
   `featureless_sky_fraction` separately from
   `featureless_non_sky_fraction`. Gate the NON-SKY fraction against a
   non-sky expectation and let the sky fraction be reported, not judged.
   This needs no porosity model and uses numbers already measured — but
   it changes what the gate claims, so it needs a ruling.

Option 2 would have passed every `near_ground` capture since 09-05
(non-sky max 0.0817) while still catching `mid_slope`'s 0.9383.

**Not applied. No ruling available overnight.**

## Instrument note

The derivation is dated 2026-09-11 and the foliage was last regenerated
before that, so this is not staleness from a world change — the model
was wrong when it was written, for the station where canopy dominates.
A re-derivation on the current world would reproduce the same 0.75 %.
