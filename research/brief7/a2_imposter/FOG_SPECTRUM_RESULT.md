# Brief 7 — Mie/Rayleigh spectrum ladder (ruled 2026-09-26): no cell blue-shifts; fallback persisted as Look-profile fields; A2 CLOSED

2026-09-27, Look profile (sun 35°, PPV_Look, sg Epic, TSR), windowed editor, 3840×2160, 25 s settle per
camera. Fence `pre-a2-fog`. Every cell read back from the SkyAtmosphere / fog components; baseline restored
(density 0.00416, start 0, AP 1.0, mie 0.010, rayleigh 0.0331) and read back. Frames + raw numbers:
`ap/camA_m*.png`, `ap/camB_m*.png`, `ap/ladder_spectrum_run.log`, `ap/ladder_spectrum_measure.json`.

## The ruling being executed

Mie {0.010, 0.005, 0.0025} × Rayleigh {0.0331, 0.05} at d15_s150 (density 0.0015, start 150 m, AP 1.0).
Hue at ~800 m (camA far crop) and 1140 m (camB, the dark cluster). Winner = first cell with hue shift
≥ 15° toward blue AND sat300 ≥ 0.6·sat40; ties to the higher Mie. If no cell hits 15°: persist the largest
blue shift that keeps sat300 ≥ 0.6·sat40, BACKLOG the table, no re-ask. Either way tag a2-closed and
re-shoot vista + slope + near_ground. One bench A/A still must match.

## The table (shift800 = camA far hue − camA 40 m hue; + = toward blue)

| cell | mie | rayleigh | sat40 | sat300 | sat800 | shift800 | sat300 ≥ 0.6·sat40 | camB 1140 m sat / hue / lum |
|---|---|---|---|---|---|---|---|---|
| base_d42 (on-disk) | 0.010 | 0.0331 | 0.529 | 0.475 | 0.257 | −7.8° | PASS | 0.161 / 233.1 / 94.2 |
| ap1_white (= d15_s150) | 0.010 | 0.0331 | 0.530 | 0.487 | 0.294 | −6.1° | PASS | 0.192 / 232.7 / 86.6 |
| m010_r033 | 0.010 | 0.0331 | 0.537 | 0.499 | 0.312 | −6.0° | PASS | 0.191 / 232.0 / 86.4 |
| m005_r033 | 0.005 | 0.0331 | 0.536 | 0.494 | 0.305 | −5.5° | PASS | 0.214 / 226.8 / 84.3 |
| m0025_r033 | 0.0025 | 0.0331 | 0.537 | 0.495 | 0.304 | −5.6° | PASS | 0.227 / 225.3 / 83.1 |
| m010_r050 | 0.010 | 0.05 | 0.576 | 0.538 | 0.330 | −5.9° | PASS | 0.183 / 226.2 / 90.9 |
| m005_r050 | 0.005 | 0.05 | 0.577 | 0.539 | 0.334 | **−5.3°** | PASS | 0.201 / 221.5 / 89.2 |
| m0025_r050 | 0.0025 | 0.05 | 0.578 | 0.540 | 0.334 | −5.5° | PASS | 0.212 / 219.8 / 88.3 |

Pixel counts per cell: camA near ~680–718k, mid ~423–442k, far ~11.6–13.1k; camB far ~178–182k.

## Reading it

- **No cell approaches +15°.** Every spectrum cell sits between −5.3° and −6.0°: the far band stays
  warmer than the near band on every cell, and the whole spread (0.7°) is inside the hue noise — the near
  band, which no lever should move, jitters 0.8° between cells (43.3–44.1° across the r033 group).
- **What the levers DO move:** Rayleigh 0.05 raises saturation everywhere (near 0.53 → 0.58, far 0.29 →
  0.33) — a bluer, more saturated sky lighting the scene, not a distance effect. Lower Mie raises the 1140 m
  cluster's saturation (0.19 → 0.23) and moves its hue 232 → 220° (toward CYAN, away from pure blue) while
  darkening it (86 → 83 lum): less white haze on the shadow side, not blue aerial perspective.
- **Why:** the far band's colour is dominated by the warm sunlit haze under a 35° sun and PPV_Look's WB 6200;
  at 0.8–1.1 km the atmosphere's Rayleigh contribution is a few percent of the pixel. Blue aerial perspective
  in this world appears at the 4–8 km ridges (they fade to the sky correctly on every cell), not at 1 km.

## Verdict — fallback executed, no re-ask (per the ruling)

Largest blue shift keeping sat300 ≥ 0.6·sat40: literally m005_r050 at −5.3°, ahead of m0025_r050 /
m005_r033 (−5.5°), m0025_r033 (−5.6°), m010_r050 (−5.9°), m010_r033 (−6.0°) — by 0.2–0.7°, inside the
0.8° noise. A tie, so the ladder's tie rule applies: **higher Mie = 0.010**; between r033 and r050 at
Mie 0.010 (−6.0 vs −5.9, a tie) Rayleigh stays at the **bench 0.0331** (the rule's own rationale: less risk
to the sun and horizon look). **Persisted Look-profile fields: fog density 0.0015, start 150 m, AP scale
1.0, mie 0.010, rayleigh 0.0331** — i.e. the de-greying cell d15_s150 with the bench atmosphere.
If the desk prefers the literal maximum, `m005_r050` is one constant in `brief7_p0e_setprofile_payload.txt`
(`LOOK_ATMOS`), with the table above as the evidence either way. BACKLOG: "aerial perspective: stronger
blue at 1 km".

## Bench restore and A/A

- Profile switcher (`brief7_p0e_setprofile_payload.txt`) sets fog + atmosphere per profile and reads them
  back from the components: Look → 0.0015 / 15000 / 1.0 / 0.01 / 0.0331; bench → 0.00416 / 0 / 1.0 /
  0.01 / 0.0331 — the on-disk Brief 2 / 0d values, exact.
- Bench-profile A/A at camA, 3840×2160 (8,294,400 px): `benchAA2_pre.png` (before the switcher gained the
  fields) vs `benchAA2_post.png` (after, bench profile restored): **MAD 3.10, p99 27** against the 26th's
  pre/pre control pair MAD 5.58, p99 46 → inside control noise. Channel means 62.92/68.99/72.74 vs
  62.87/68.95/72.72.

## Re-shoot (Look profile with the persisted fields)

`research/brief7/stills/p2_a2/{near_ground,slope,vista}_look_a2.png` — bench stations, +1.75 m traced eye,
FOV 90, 25 s settle.
