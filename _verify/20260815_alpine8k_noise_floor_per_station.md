# The Alpine8K noise floor is PER-STATION, and spans 8x

Measured 2026-08-15. Three same-settings frames per station, 4 s apart, one
parked camera, nothing touched between them. Tool:
`scripts/check_scene_animation.py`. Raw per-station JSON beside this file.

    station          mae        vs 0.00298   px>2%    peak
    ridge_wide       0.002449      0.82x      1.27%   0.3569
    diag_topdown     0.002827      0.95x      2.15%   0.2314
    forest_floor     0.008899      2.99x     12.76%   0.6745
    sweep_2000       0.016410      5.51x     21.61%   0.8510
    trunk_base       0.019815      6.65x     31.49%   0.8745

## The finding

**There is no single noise floor for this world.** It spans **8x** between
the quietest and noisiest station, and the pattern is not subtle:

- The two stations with LITTLE OR NO VEGETATION in frame -- `ridge_wide`
  (aerial, fog-dominated) and `diag_topdown` (straight down from 9 km) --
  sit essentially AT the project's long-standing 0.00298, at 0.82x and 0.95x.
- The three stations packed with vegetation run **3.0x to 6.6x** it, rising
  with how much of the frame is foliage: `trunk_base` is a 35-degree
  close-up of a trunk and canopy and is the worst at 31.49% of pixels moving.

**So 0.00298 was never wrong. It was measured on bare terrain and it remains
correct for bare-terrain-like frames.** What is wrong is quoting it against a
vegetation-filled frame, which this project has been doing since foliage was
added.

The mechanism is renderer temporal accumulation over high-frequency
alpha-tested geometry -- established separately in
`_verify/20260815_alpine8k_animation_check.md`, where culling the grass
left the variance unchanged and neither tree material declares a wind
parameter.

## What this changes

**Any per-station verdict must use ITS OWN station's floor.** A sweep that
grades `trunk_base` against 0.00298 would call a 6x-noise-floor difference
a finding on every comparison. Concretely: an edge-energy or mae A/B at
`trunk_base` needs to clear ~0.020, not ~0.003, before it means anything.

**The estimate is itself noisy at n=3.** `forest_floor` read 0.011745
earlier the same session and 0.008899 here -- a 32% spread on the same
station under the same conditions. Three frames give three pairs, which is a
thin sample. **Treat these as the right ORDER OF MAGNITUDE per station, not
as calibrated constants**, and raise the frame count before using any of them
as a hard gate threshold.

## Not established

- Only 5 of the 20 stations were measured. The other 15 are unmeasured, and
  the spread here says they cannot be interpolated with confidence -- the
  floor tracks frame CONTENT, not station distance.
- The mechanism was not decomposed. TSR history, Lumen accumulation,
  volumetric fog reprojection and light shafts are all candidates and no
  single-variable cvar A/B was run on any of them.
