# BRIEF 2 — Atmosphere, sky light and grade: making distance read as distance

Status: RESEARCH, written against the Phase C frames (`_verify/bench/2026-09-07/for_research/`, player instrument at 4K plus one truth frame), the five-sample census (`research/census/`), and the sample inis. One tested tool (`scripts/fog_budget.py`), one offline measurement reused from the forge desk (`scripts/measure_concept_look.py`, run on the four frames — numbers below), and one draft editor procedure (the void test). VERIFY marks apply as in Brief 1.

Scope: `/Game/Alpine8K` lighting and post: SkyAtmosphere, ExponentialHeightFog, SkyLight, DirectionalLight, VolumetricCloud, the recipe's PostProcessVolume. Brief 1's ladder (culls, imposters, HLOD range) is a *dependency* here in one place — §0.3 — and nothing else.

---

## 0. What the frames say (MEASURED)

`measure_concept_look.py` on the four stills, linear RGB, ratios are channel / luma of the band median:

| frame | sky (zenith band) | shadow tint R/G/B | highlight tint | haze rise near→far | sky fraction |
|---|---|---|---|---|---|
| near_ground (player) | 0.17 / 0.30 / 0.47 | **0.50 / 0.95 / 3.00** | 1.05 / 1.00 / 0.81 | −0.011 | 0.20 |
| near_ground (truth) | 0.17 / 0.29 / 0.44 | 0.53 / 0.98 / 2.54 | 1.12 / 1.02 / 0.50 | −0.010 | 0.20 |
| mid_slope (player) | 0.44 / 0.58 / 0.74 | 0.88 / 1.02 / 1.17 | ~1 | +0.154 | 0.77 |
| vista (player) | 0.33 / 0.49 / 0.68 | 0.70 / 1.02 / 1.66 | ~1 | −0.026 | 0.58 |

### 0.1 Shadows are three times bluer than they are bright
At near_ground the shadow median is R 0.50 × luma, B 3.0 × luma. A sunlit alpine meadow under a clear sky does have blue-tinted shade — sky light is blue — but the natural ratio is on the order of 1.3–1.7 in B, not 3. Two causes stack: `sky.intensity 1.8` against a physical sun (both Epic samples with a physical sun run the sky light at **1.0**, real-time capture, lower hemisphere black), and a very saturated zenith (0.17/0.30/0.47 linear is a deep-blue sky; Electric Dreams pushes Mie scattering to 0.01 — 2.5× default — which whitens the horizon and desaturates the sky light's capture). The −1.9 EV exposure compensation the recipe needed is the symptom: the sky light was over-filling, and exposure was pulled down to compensate, which darkened the sun side too.

### 0.2 There is no aerial perspective
Haze rise near→far is *negative* in the near_ground frames: the far band's darkest tones are darker than the near band's. The truth frame shows the snow massif behind the town at full contrast and full saturation. With the recipe's fog (density 0.0015 from 1.5 km) transmittance at 4 km is 0.70 and at 8 km 0.49 — the world reads as 2 km wide. `fog_budget.py` derivation in §3.

### 0.3 The elevated stations show a flat band, and it is probably not fog
mid_slope: 77% of the frame is featureless, 40 points of it non-sky, a pale pink-grey band with a razor-sharp horizontal top edge, beginning ~600 m out. Its colour (0.70/0.69/0.70 linear) does *not* match the horizon sky above it (0.74/0.79/0.86): the band is neutral-pink, the sky is blue.

Fog cannot do this: at 0.0015 density the fog is 95% transparent at 500 m from any height, and real height fog seen from above has a soft top. What *does* look exactly like this is **the SkyAtmosphere's virtual planet surface** — a flat ground at the atmosphere's `ground_albedo`, lit by a low sun, seen wherever no geometry is rendered. That is the void, back again, past whatever HLOD is loaded. Two facts support it: the player near_ground frame is missing the snow massif that the truth frame shows behind the town (so the far world is not loaded in PIE beyond some range), and the HLOD layer's loading range was set to 2 km, while City Sample's far layer loads to **16 km** — the whole world.

This is decidable in one capture (§5, experiment 0): set the atmosphere's ground albedo to magenta and count magenta pixels. Zero means the band is fog and §3 owns it; non-zero means it's void and the HLOD loading range owns it. The brief proceeds on the void reading but does not need it to be right — both fixes are in the task list and the test comes first.

### 0.4 What is fine
Sun angle and warmth read correctly; the sun disc is present; snow coverage at the vista's altitude is plausible; exposure is manual and read back; the truth/player pair differ only in residency (luma 0.363 vs 0.375), which is what two instruments should do.

---

## 1. What the eye does with light and distance (LITERATURE)

**Colour constancy.** The visual system discounts the illuminant: shade under a blue sky is *perceived* as less blue than a photometer measures, because the brain attributes part of the blue to the light rather than the surface. A renderer is a photometer. If the sky light is physically right, shadows come out slightly bluer than memory expects — acceptable; if the sky light is 1.8× too strong on top, shadows come out at a ratio no viewer accepts as "shade." The target band for B/luma in shade under clear sky, from photographic reference and from the Epic frames, is ~1.3–1.7. (Foster 2011, *Color constancy*, Vision Research 51.)

**Aerial perspective is a depth cue in its own right.** Contrast falling with distance, and hue shifting toward the sky's, tells the brain how far things are — independently of size. Leonardo wrote it down; Cutting & Vishton (1995) rank it among the reliable cues beyond 30 m. A far ridge rendered at near-field contrast reads as *nearer* and *smaller* than it is; the whole world reads as a diorama. The physics is Beer–Lambert: transmittance T = e^(−βd), and the contrast of a distant object is scaled by T while sky-coloured inscatter fills the gap. What the eye needs: enough contrast left to *read* the far object (the CSF says ~5–10% is the floor for large forms at low frequency; 25–40% keeps it legible and still "far"), and a colour that converges on the horizon sky, not on grey or pink.

**Adaptation and the white point.** The eye adapts to the dominant illuminant; a scene with a warm low sun and a blue sky adapts to somewhere between. Rendering with a fixed 6500 K white balance against a 4500 K sun leaves everything sunlit reading orange; Epic's samples set the PPV white balance to 4800–5600 K to meet the scene halfway. This is a grade decision, but it is a *perceptual* one, and it belongs in the recipe as a number derived from the sun's temperature, not left at default.

**Contrast and saturation are judged relative to the frame.** A frame whose shadows are crushed to near-black loses shadow detail the eye expects (the CSF is most sensitive at low contrast in mid-tones, and a viewer scans shadows for detail); a frame whose global contrast exceeds ~1.1 of neutral reads "gamey." Epic's samples sit at contrast 0.87 (a hazy forest) to 1.14 (a dungeon) with saturation 0.8–1.1 — a narrow band, and none at the tonemapper's neutral.

**Temporal note.** Volumetric fog and clouds shimmer under TSR; the dolly instrument catches it. Not in scope here beyond noting that every atmosphere change is re-scored on the dolly once E4 has a sunlit path.

---

## 2. What the engine provides (from the census; VERIFY property names)

| system | what to use | what Epic sets | ours today |
|---|---|---|---|
| SkyAtmosphere | Rayleigh/Mie scattering scales, Mie anisotropy, aerial perspective start depth, ground albedo, multi-scattering | ED: Mie 0.01 / g 0.8 / Rayleigh 0.0331 (default) / AP start 0.1; DR: Mie 1.2 (a cave) | defaults |
| ExponentialHeightFog | density, height falloff, datum Z, start distance 0, inscattering from the atmosphere (`r.SupportSkyAtmosphereAffectsHeightFog=1`, `fog_inscattering_luminance` black), directional inscattering, volumetric fog, second fog | ED: 0.02 / 0.1 / start 0 / volumetric on, extinction 1.2, distance 55 m; City: 0.01 / 0.07 / start 200 m; DR: 0.05 / 0.001 | 0.0015 from 1.5 km, no atmosphere coupling |
| SkyLight | intensity, real-time capture, lower hemisphere colour | 1.0, real-time, black — both ED and DR | 1.8 |
| DirectionalLight | lux, temperature, source angle, light shafts | ED/DR: 100,000 lux, 6500 K (no temp), angle 0.5357°; City: 2,000 lux 4,500 K (overcast) | recipe |
| VolumetricCloud | bottom altitude, layer height, material | ED: 2.25 km / 1.5 km, custom MI; engine ships `m_SimpleVolumetricCloud` | none |
| PostProcessVolume | white balance, contrast, saturation, bloom (FFT), grain, vignette, DoF, exposure | ED: WB 5600 K, contrast 0.87, bloom FFT + dirt, grain 0.8; DR: contrast 1.12–1.14, sat 1.1, WB 4800–5000, vignette 0.7 | manual EV −1.923 only |
| Lumen | far-field against HLOD proxies (`r.LumenScene.FarField`, proxy RT on) | City on; ED off | off (proxies RT off) — Brief 2b, after the ladder is stable |
| HLOD layer | loading range | City far layer 16 km | 2 km |

The one project setting to flip first, because three Epic projects run it and it removes a whole class of "wrong colour fog": `r.SupportSkyAtmosphereAffectsHeightFog=1` with the fog's own inscattering luminance set to black. Fog then takes its colour from the same atmosphere the sky does, at every sun angle, with no tint to type.

---

## 3. Derived numbers (DERIVED, tool in `scripts/`)

**Fog.** `fog_budget.py` solves density from a stated transmittance target under UE's exponential-height model (T = 2^(−D·2^(−F·Δz/1000)·L/1000), constants VERIFY against `HeightFogCommon.ush`), and takes height falloff from a stated rule — density halves every (world height / 3) metres, so the ridge sees ~4× farther than the valley:

```
world 0–1552 m, datum 120 m (valley floor), camera 130 m
target: T(1 km) = 0.75      →  D = 0.0042,  F = 0.019 (halves every 517 m)
reported: T(4 km) = 0.32, T(8 km) = 0.10   (valley)
          T(4 km) = 0.83, T(8 km) = 0.69   (ridge)
ridge looking down 20°:  T(2 km) = 0.86, T(4 km) = 0.57
```

For comparison the recipe's 0.0015 gives T(4 km) = 0.70 and 1.0 from any elevated station; Electric Dreams' 0.02 gives T(1 km) = 0.27 in the valley — a forest interior, not an alpine view. The derived 0.0042 sits between, and it is chosen by a *legibility* target (25–40% contrast at the far edge of the shape band) rather than by taste. Start distance **0** (all three samples); volumetric fog **on** with extinction ~1.0 so the near haze catches light shafts; second fog off until the datum is proven.

**Sky light.** 1.0, real-time capture, lower hemisphere black — sourced, not derived; the derivation is the measurement: shadow B/luma at near_ground must land in 1.3–1.7 (§0.1). If 1.0 leaves the ratio above 1.7, the next lever is atmosphere Mie (§3, sky saturation), not sky-light intensity below 1.0.

**Sky saturation.** Mie scattering scale from the concept references, not from ED: `atmosphere_solve.py` already fits Mie/Rayleigh to a measured horizon-to-zenith gradient (Brief 1 register); run it on the Alpine8K references' skies. Until then, ED's 0.01 / 0.8 is the sourced starting point.

**White balance.** PPV `white_temp` = the sun's temperature + ~1000 K (ED: sun 6500 K uncorrected / WB 5600; DR: WB 4800–5000 with a low warm sun). For a recipe sun at 4500–5000 K that lands at 5500–6000 K. Stated as a rule with its source; confirm by the highlight-tint ratio moving toward 1/1/1 on the sunlit meadow.

**Grade.** Contrast 0.9–1.0, saturation 1.0, FFT bloom at low intensity (0.3–0.5), grain ≤ 0.5, vignette ≤ 0.4, no chromatic aberration — a *quieter* version of the Epic grades, because the bench compares frames and every grade element is noise in that comparison. Applied on the recipe's unbound PPV; the bench profile may zero grain and vignette for scoring (read back).

**Exposure** stays manual, from the lighting block, read back — but its value must be re-derived after the sky-light change: expect it to move toward −1.0 EV as the fill drops. Re-run `polish` rather than typing it.

**HLOD loading range.** The far layer's range must exceed the world's half-diagonal plus the camera's furthest station: 8.13 km world → ~12 km; City uses 16 km. Set 16 km, spatially loaded, and re-check the void test.

---

## 4. Measurements (the acceptance for every experiment below)

All from `measure_concept_look.py` on the bench stills, player instrument, target profile:

- **shadow_tint_B** (near_ground, B/luma of shadow median): 1.3–1.7
- **haze_rise** (near_ground, far p10 luma − near p10 luma): > +0.01 (positive: distance lifts blacks)
- **far_contrast** (near_ground, far band luma std / near band luma std): 0.25–0.45
- **fog_vs_sky ΔE** (mid_slope/vista: linear-RGB distance between the featureless non-sky median and the horizon-sky median): < 0.08 — fog converges on the sky
- **void_fraction** (experiment 0): 0.000
- **highlight_tint** (near_ground, sunlit meadow median / luma): each channel within 0.9–1.1 after white balance
- **skyline_iou** (near_ground player vs truth): > 0.9 — the far world is present in the player frame
- **dolly score** (E4 path, tile-wise tool when delivered): does not rise vs pre-Brief-2 baseline

---

## 5. Experiments, in order

0. **Void test.** One player capture at mid_slope and vista with the SkyAtmosphere `ground_albedo` set to magenta (255,0,255) — read back — then restored. Count magenta-hue pixels (`void_mask.py`). Non-zero → set the HLOD far layer loading range to 16 km, rebuild nothing (range is a layer property; VERIFY whether a Setup pass is needed), recapture, recount. This must be zero before any atmosphere number is judged, because a void band scores as "fog" in every other measurement.
1. **Fog coupling.** `r.SupportSkyAtmosphereAffectsHeightFog=1` in DefaultEngine.ini (standing rule 4: via the editor API, read back), fog inscattering luminance black, start distance 0. Recapture; fog_vs_sky ΔE must drop.
2. **Fog density and falloff** from `fog_budget.py` with the world's measured Z range and the recipe's valley floor as datum; volumetric fog on. Recapture near_ground: haze_rise positive, far_contrast in band; recapture vista: the far ridges soften but remain legible.
3. **Sky light 1.0**, real-time capture, lower hemisphere black. Recapture near_ground: shadow_tint_B in band. Re-derive exposure with `polish`.
4. **Mie / Rayleigh** from `atmosphere_solve.py` on the references' sky gradients (or ED's 0.01 / 0.8 as the sourced start). Recapture: sky zenith less saturated, shadow_tint_B unchanged or lower.
5. **White balance and grade** on the recipe PPV: WB from the sun rule, contrast 0.95, bloom FFT 0.4, grain 0, vignette 0 for the bench profile. Recapture: highlight_tint in band.
6. **Volumetric clouds**: engine `m_SimpleVolumetricCloud`, bottom 2.0 km, height 1.5 km, coverage low. Recapture vista; the dolly re-score decides whether they shimmer.
7. **Lumen far-field on HLOD proxies** (Brief 2b): proxies rebuilt with `support_ray_tracing=True` now that they are 4k tris; `r.LumenScene.FarField=1`; scored on the vista's shaded slopes (shadow_tint_B on the far band) and on VRAM. Only after 0–6 are locked.

Each experiment is one variable, one capture set, one measurement line in the register, in that order.

---

## 6. Sources

- Foster, D.H. (2011). Color constancy. *Vision Research* 51(7).
- Cutting, J.E. & Vishton, P.M. (1995). Perceiving layout and knowing distances: the integration, relative potency, and contextual use of different information about depth. In *Perception of Space and Motion*.
- Preetham, A.J., Shirley, P., Smits, B. (1999). A practical analytic model for daylight. *SIGGRAPH.* (Aerial perspective as inscatter + extinction.)
- Hillaire, S. (2020). A scalable and production ready sky and atmosphere rendering technique. *EGSR / Epic.* (UE's SkyAtmosphere; the Mie/Rayleigh parameterisation used here.)
- Barten (1999) and Campbell & Robson (1968) as in Brief 1 for the contrast floor.
- Census: `research/census/ElectricDreams__ElectricDreams_PCG.json` (lighting, PPV), `DarkRuins__Main.json` (PPV set), `CitySample__Small_City_LVL.json` (HLOD1 16 km range, Lumen far-field); sample inis in `samples_text/`.
- Engine source to VERIFY: `HeightFogCommon.ush` (density/falloff constants), `ExponentialHeightFogComponent.cpp`, `SkyAtmosphereComponent.h` (ground_albedo), `HLODLayer.h` (loading range semantics for HLOD actors).
