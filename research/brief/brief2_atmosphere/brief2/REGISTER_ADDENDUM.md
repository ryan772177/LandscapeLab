# REGISTER addendum — Brief 2 (append to research/brief1/REGISTER.md, or start research/REGISTER.md as the shared one)

## MEASURED (Phase C frames, 2026-09-07, player instrument at 4K)
- B2.1 near_ground shadow tint B/luma = 3.00 (truth 2.54); highlight tint warm. Sky light over-filling. `measure_concept_look.py`.
- B2.2 near_ground haze rise near→far = −0.011: no aerial perspective; truth frame shows the massif at full contrast.
- B2.3 mid_slope non-sky featureless band colour 0.70/0.69/0.70 vs horizon sky 0.74/0.79/0.86 — the band does not converge on the sky.
- B2.4 near_ground player frame lacks the massif the truth frame shows: far world absent in PIE beyond the loaded range.

## PROPOSED (design; Task numbers in Brief 2)
- B2.5 The flat band is the SkyAtmosphere planet ground (void), not fog — decided by the magenta ground-albedo capture (Task 0). Fix if so: far HLOD layer loading range 16 km (City Sample).
- B2.6 Fog colour from the atmosphere: r.SupportSkyAtmosphereAffectsHeightFog=1, inscattering black, start 0 (three Epic samples).
- B2.7 Fog density derived from a legibility target: T(1 km)=0.75 → D≈0.0042, F≈0.019 (halving 517 m) for a 0–1552 m world; `fog_budget.py`, UNIT constant VERIFY.
- B2.8 Sky light 1.0 real-time, lower hemisphere black (ED, DR); exposure re-derived by `polish` afterwards.
- B2.9 Mie 0.01 / anisotropy 0.8 as sourced start; fit to references with atmosphere_solve when available.
- B2.10 White balance = sun temperature + 1000 K; contrast 0.95; quiet grade; bench profile zeroes grain/vignette.
- B2.11 Volumetric clouds on the engine material, 2.0 km / 1.5 km.
- B2.12 Lumen far-field on RT-enabled light proxies — **Brief 2c** (RELABELLED BY RULING 2026-09-10: "Brief 2b" now names the executed sun-temperature correction; this row keeps its ruling-required status under the new label), ruling required.

## SOURCED FROM THE CENSUS (five projects)
- HLOD: two-level (Instancing 256 m cells to 768 m; Approximate 2 km cells to 16 km), simplification by geometric tolerance (0.25 m, 2 tris/m²), texture size AUTOMATIC_FROM_MESH_DRAW_DISTANCE, Nanite proxies with RT for far-field (City). → R-HLOD PROPOSED.
- Foliage: cull distance 0 on all 62 Nanite clutter types; single-LOD Nanite (ED). → Brief 5.
- HWRT fenced by distance (100–150 m) and class (ISM excluded, RT shadows off) (ED, City). → R-RTFENCE corrected shape.
- Lumen scene reduced for scale (card res, texel density) (Valley, City).
- MRQ + AutomatedPerfTesting as the capture and perf frameworks (Valley, Titan, City).
- Nanite Foliage still off in Epic's own 5.8 samples → Task 9 stays "evaluate".

## TOOLS (tested here)
- `fog_budget.py` — density from a transmittance target, falloff from a halving rule; self-test PASS (default fog reproduces T(1 km)=0.25).
- `void_mask.py` — magenta-hue void counter; synthetic test PASS.
- `measure_concept_look.py` — palette/sky/skyline/haze/grade on any frame (from the forge desk; ran on the four bench frames above).

## REJECTED
- Typed fog tint / fixed inscattering colour — no Epic project does it; fog that does not converge on the sky is measurable (B2.3).
- Sky light > 1.0 with a physical sun — shadow tint 3.0 (B2.1).
- Fog start distance 1.5 km — all samples start at 0; a hard start is a wall, not haze.
- Global HWRT on/off as the lever — the census shows fencing is the lever.

## OPEN QUESTIONS
- Q13 Is the elevated-station band void or fog? (Task 0 decides.)
- Q14 HeightFogCommon.ush density/falloff constants (UNIT) in 5.8.
- Q15 Does an HLOD layer loading-range change require a Setup pass?
