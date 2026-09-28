# B-1 — Task 5 acceptance on the uniform-4096 world (2026-09-15)

Instrument = **ppi0** (scene-linear) for contrast; **BaseColor GBuffer**
(÷ 2^compensation) for albedo. Stations: vista (cam 767.3 m), mid_slope
(cam 636.3 m). Editor verified `/Game/Alpine8K`, every capture certified
(residency PASS), sidecars carry the `instrument` field.

**Both acceptances return FINDINGS, not clean passes — reported, not
tuned (B-1).** The findings are about the INSTRUMENT and the METHOD, not
about the world being wrong.

---

## Part A — depth-bin luminance contrast vs fog_budget transmittance (C-T5c)

Metric (Brief 2 R-FOG, now on PPI0): per depth bin, contrast ratio =
luma_std(bin) / luma_std(first populated bin); acceptance is the
300-1000 m ratio within ±30% of the fog's predicted transmittance T at
the bin's mean distance. Tool: `scripts/task5_fog_contrast.py` (selftest
4/4). PPI0 not FinalImage, because the tone curve + grade compress
contrast non-linearly; PPI0 is scene-linear so a contrast ratio there is
the physical transmittance.

    station     bin 300-1000m   predicted_T   contrast_ratio   verdict
    mid_slope   1,496,784 px    0.902         50.90            FAIL
    vista         161,481 px    0.917          1.16            PASS

**⛔ FINDING: the metric is OUT OF CLASS at elevated stations; both
verdicts are content artefacts, not fog.** Evidence:

1. **The fog is thin by design at altitude.** The recipe halves fog
   density every ~172 m of altitude (half_height 517 m over the world
   span). At the cam altitudes (636 / 767 m, ~450-580 m above the
   186.7 m datum) the fog column is small: predicted T is **0.90-0.92 at
   650 m** and only falls to 0.73-0.77 by 2 km. There is little
   attenuation for the test to detect.
2. **luma_std RISES with distance, not falls.** mid_slope: std 0.0011
   (0-100 m foreground) → 0.055 (300-1000 m) → 0.070 (1-3 km). The near
   reference bin is a near-flat 0.3% foreground sliver; the far bins are
   high-variance mountain terrain. The "contrast ratio" of 50 is the
   scene's content gradient (flat foreground vs mountainous distance),
   not transmittance.
3. **vista "passes" non-monotonically.** Its ratios run 1.00, 1.49,
   1.16, 1.64 across bins while T falls 0.99→0.77 — the 300-1000 m bin
   lands within ±30% of T by coincidence of content, not because
   contrast tracks the fog. A metric that FAILs mid_slope and PASSes
   vista on the same thin fog is measuring content, not fog.

The contrast-ratio-as-transmittance premise holds only where scene
texture statistics are roughly stationary across depth and the fog is
thick enough to dominate — i.e. **near_ground / valley views**, where it
was derived and validated (Brief 2). It does not transfer to elevated
vistas. Per the verification-practice rule, the response is a
class-appropriate instrument, never a widened tolerance — and here the
class-appropriate reading is that at these altitudes the fog is
correctly thin (by the recipe's altitude-halving) and there is no
meaningful attenuation to accept against.

---

## Part B — proxy-vs-real albedo per layer (C-T5d)

Design: PROXY = the player capture (HLODs on); REAL = a
`--game-override disable_hlods=true use_lod_zero=true --load-all-regions`
capture (real landscape material, LOD0). Same camera → same rays → a
per-pixel comparison in the 300-1000 m bin; albedo = FinalImageBaseColor
÷ 2^compensation (B3.16). Tool: `scripts/task5_proxy_albedo.py`
(selftest 6/6), segmenting by real-albedo clusters.

    station     overall real    overall proxy    delta      verdict
    mid_slope   0.38875         0.38876          +0.003%    PASS
    vista       0.45930         0.45930          +0.000%    PASS

Every per-cluster delta is 0.0%, every layer within ±15%.

**⛔ FINDING: this is a NULL comparison — the bench force-loads the real
landscape, so the 4096 HLOD PROXIES NEVER RENDER in a bench frame.**
Evidence: proxy and real captures are **pixel-identical** at both
stations across 300-3000 m — depth differs in **0.0%** of pixels and
BaseColor in **0.0%** (|Δ|>0.02). Identical DEPTH means identical
geometry, i.e. both render real landscape cells, not the simplified HLOD
merged mesh.

Why: `bench_capture`'s residency is a **force-loaded precondition**
(R-BENCHCAPTURE — residency is declared and read back to prevent voids).
It loads the visible World Partition cells as real geometry, so the
runtime never falls back to the landscape HLOD proxy. HLOD proxies are a
STREAMING artefact — they render only when cells unload beyond the
runtime loading range in actual play — and the bench, by design, never
lets cells unload. `use_lod_zero` in the "real" arm changes only LOD, and
BaseColor albedo is LOD-invariant, so the two arms match to 3 decimals.

**Consequence:** the RENDERED proxy albedo cannot be verified through the
bench instrument. What CAN be verified — and was, in an earlier session —
is the proxy's BAKED texture off disk: all 256/256 landscape HLOD cells
carry `HLODTextureSize 4096` and bake 4096² BaseColor/Normal/MRS
(`hlod_report_offdisk.py`). To verify the rendered proxy albedo would
require a streaming-respecting capture (cells allowed to unload past the
loading range) — a different instrument than the bench, and a scope
question for the desk.

---

## What is delivered

- Two acceptance tables, above, with the honest verdicts.
- `fog_contrast_{mid_slope,vista}.json`, `proxy_albedo_{mid_slope,vista}.json`.
- Two new self-tested tools: `task5_fog_contrast.py`, `task5_proxy_albedo.py`.
- Captures: `target_b1_{mid_slope,vista}` (player) and
  `target_b1_{mid_slope,vista}_real` (LOD0/HLOD-off), all certified.

## What is NOT delivered, and why (not tuned)

- A clean fog-contrast PASS at the bench stations — the metric is out of
  class there (Part A finding); the fog is correctly thin at altitude.
- A rendered proxy-vs-real albedo verdict — proxies do not render in a
  bench frame (Part B finding); the baked 4096 albedo is verified off
  disk instead.
