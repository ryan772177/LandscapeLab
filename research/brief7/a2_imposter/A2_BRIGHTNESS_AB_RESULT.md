# Brief 7 A2 — imposter Brightness A/B: MEASURED, no imposter fix warranted

2026-09-25, Look profile, windowed. Measured (not eyeballed) the SpruceSub imposter against LOD0.
The `_SRC` copy of `half_01_imposter` was made, the ladder run on the live MI, then the MI restored
to default (Brightness 1.8, SS Strength 1.0) and `_SRC` deleted — **no material changed on disk.**

## Method

Fixed camera 40 m from one SpruceSub instance (world (-201186, 212516), cam
(-201186, 208516, 20021), yaw 90, FOV 50). One LOD0 reference (`foliage.ForceLOD 0`) and the six
imposter cells (`foliage.ForceLOD 4`, 3 Brightness × SS Strength on/off). Foliage measured by a
green-dominant pixel mask; luminance = 0.299R+0.587G+0.114B; hue from HSV. Note: MA_Imposter exposes
**no Subsurface Color parameter** (the two-sided-foliage subsurface is internal), so the SS arm is the
`SS Strength` scalar (1.0 on / 0.0 off), not a colour match.

## The 6-cell table (imposter foliage vs LOD0 ref @ 40 m; ref lum 49.5, hue 65.9)

| cell | Brightness | SS Strength | lum | hue | ΔLum% | ΔHue% | verdict |
|---|---|---|---|---|---|---|---|
| b18_ss1 | 1.8 | 1.0 | 46.3 | 65.9 | −6.4 | 0.0 | PASS |
| b24_ss1 | 2.4 | 1.0 | 46.5 | 65.8 | −5.9 | −0.2 | PASS |
| b30_ss1 | 3.0 | 1.0 | 46.7 | 65.8 | −5.6 | −0.2 | PASS |
| b18_ss0 | 1.8 | 0.0 | 44.9 | 66.2 | −9.2 | 0.5 | PASS |
| b24_ss0 | 2.4 | 0.0 | 44.6 | 66.2 | −9.9 | 0.5 | PASS |
| b30_ss0 | 3.0 | 0.0 | 44.4 | 66.2 | −10.1 | 0.5 | FAIL-lum |

**At matching distance the imposter already matches LOD0 within 10%** at the DEFAULT (b18_ss1, −6.4%
lum, 0% hue). `Brightness` 1.8→3.0 barely moves it (+0.4 lum): a weak lever. `SS Strength` ON adds
~2 lum (ON is closer to LOD0). So the best cell is the default (Brightness 1.8, SS 1.0).

## The decisive test — imposter vs full geometry at the SAME distance (~300 m, slope station)

Relaxed veg mask (catches the desaturated distant foliage):

| still @ ~300 m | lum | sat | RGB |
|---|---|---|---|
| full geometry (`foliage.ForceLOD 0`) | 73.2 | 0.051 | 74/73/71 (gray) |
| imposter (`foliage.ForceLOD 4`) | 72.8 | 0.039 | 73/73/70 (gray) |

**At ~300 m the full-geometry trees are ALSO gray/desaturated (sat 0.05), and the imposter matches
them within <1% luminance.** The distant "dark forest" is **atmospheric fog desaturating everything at
distance — identical for LOD0 geometry and the imposter.** The imposter is faithful.

## Verdict — NO imposter fix applied (and none warranted)

- The imposter matches LOD0 within 10% at equal distance, and matches full geometry within <1% at the
  actual complaint distance. Raising `Brightness`/`SS` would make imposters BRIGHTER than the real
  full-geometry trees at that distance — a mismatch, not a fix.
- The A2 "dark far-forest" is **aerial perspective / atmospheric fog** (a dense dark-green conifer
  forest desaturating to gray at ~300 m), which hits full geometry and imposter equally. If the desk
  wants the distant forest to read greener/less gray, the lever is the **ExponentialHeightFog /
  atmosphere aerial-perspective density**, NOT the imposter material.
- MI left at default; `_SRC` deleted; no `.uasset` modified on disk. `pre-a2-fix` stands. NOT tagged
  `a2-fixed` — there was nothing to fix in the imposter.

## Recommendation (desk to rule)

If the distant forest greyness is undesired for the Look, tune the fog / aerial perspective (a Look
atmosphere decision affecting all distant content), and re-judge. The imposter thread is closed:
faithful to full geometry, no change.
