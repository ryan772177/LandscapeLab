# UNRESOLVED — 2026-09-12

**For an external consult.** Written by the session that produced the
findings. Every number here was measured today unless marked inherited;
every claim that is a hypothesis is labelled one.

**Repo state:** clean, all levers at settled values, engine confirmed to
match the recipe by read-back.

    sky 1.0   Mie 0.01   pre-exposure 4   WB 3481.9   exposure -4.1268 EV

---

## 1. THE BIG ONE — an acceptance that no longer measures what it names

### The failure

`shadow_tint_B` at station `near_ground` reads **1.8051** against a ruled
band of **1.10–1.60**. It is the only station that band governs
(`shadow_tint.py` docstring line 3).

### Why it is not a lighting fault

Two instruments on the **same frame** disagree:

| instrument | reading | verdict |
|---|---|---|
| `shadow_tint_B`, measured on TERRAIN | 1.8051 | 80% blue excess |
| grey card, a known 18% NEUTRAL plane | highlight_tint R 1.026 / G 0.9877 / B 1.0455 | **PASS**, neutral to 6% |

Both cannot describe the illuminant. The card is the controlled surface,
so `shadow_tint_B` is measuring **terrain albedo**, not light.

Corroborating: the five-layer material (landed today) replaced WildGrass
and Rock051 across much of the land region with warm litter (linear luma
0.2760) and grey scree (0.2228). At **identical grade and lighting**, B
fell from **1.1243** (Brief 2b, 2026-09-10) to **0.7674** — a 32% drop.
The light never moved.

### Every lever, measured — one variable each, same station and instrument

| sky | Mie | pre-exp | WB | shadow_tint_B | Δ |
|---|---|---|---|---|---|
| 1.0 | 0.01 | 4 | 3481.9 | 1.8051 | baseline |
| 1.0 | 0.02 | 4 | 3481.9 | 1.8379 | +0.033 |
| 1.0 | 0.01 | 16 | 3481.9 | 1.8051 | 0.000 |
| 1.0 | 0.01 | 4 | **5200** | 0.7674 | **−1.038** |
| **1.6** | 0.01 | 4 | 3481.9 | 1.9885 | +0.183 |

- **Sky slope measured: 0.3057 B/unit.** Reaching the re-derived floor
  would need sky ≈ **3.56** — nearly double the 1.8 rejected 2026-09-09
  for over-filling.
- **Pre-exposure 4→16: bit-identical output.** Pre-exposure is neutral
  unless something clips; nothing was clipping. Kills the
  sky-capture-clipping hypothesis.
- **Only white balance has authority** (1.038 of swing) — and it is
  **locked** by R-GRADE on grey-card evidence.

**Every lever free to move is too weak; the only strong one is locked.**

### The band's own premise has expired, twice

Its docstring: band `1.10–1.60` was re-derived 2026-09-10 **"under
NEUTRAL white balance"**, and it explicitly retires its predecessor
because that one was *"calibrated in an era whose only PASS carried a WB
1300 K BELOW the sun — a blue-amplifying grade"*.

Current grade: sun 5200 K, `white_temp_k` **3481.9 K = 1718 K below the
sun** — *further* than the condition the band was rewritten to exclude.
R-GRADE set that value from the card on 2026-09-11, **after** the band
was fixed on 09-10.

So **two locked rulings disagree**:

- **R-GRADE** — WB from the grey card → 3481.9 (the measured effective
  illuminant; the atmosphere reddens the ground-level sun below its
  source temperature)
- **the band** — assumes WB *at* the sun → 1.10–1.60

### Transforming the band to the grade in force

Using the **measured** WB response (not a model):

    measured factor   2.3522   (B 0.7674 → 1.8051 across 94.89 mired)
    Planck predicted  2.4525   (9454 K, this project's own slope)
    disagreement      4.09%    → corroborated, it is a white-point effect

    band at neutral WB   1.10 – 1.60
    band AT THIS GRADE   2.587 – 3.764
    measured             1.8051  = 0.6976 of floor

Transformed, the verdict **reverses**: the shade is **30% UNDER-blue**,
not over. **Caveat:** back-predicting the *historical* band gives
[1.402, 2.039] against the actually-ruled [1.3, 1.7] — 8% and 20% out —
so treat the transform as good to 10–20%, not three decimals.

### The metric re-derived (`scripts/shade_over_sun.py`, new today)

    shade_over_sun_B = (B_shadow/luma_shadow) / (B_lit/luma_lit)

Albedo appears in both terms and cancels to first order; so does any
global colour transform.

| frame | shadowB | litB | RATIO_B |
|---|---|---|---|
| baseline | 1.8042 | 0.7573 | 2.3825 |
| Mie 0.02 | 1.8352 | 0.7708 | 2.3809 |
| pre-exp 16 | 1.8042 | 0.7573 | 2.3825 |
| WB 5200 | 0.7258 | 0.3763 | 1.9289 |
| sky 1.6 | 1.9891 | 0.8770 | 2.2681 |

    spread:  shadow_tint_B 2.741x     shade_over_sun_B 1.235x

**2.2× more stable.** Cancels Mie to 0.07% and pre-exposure exactly.

**But two real failures:**
1. **19% WB residual** (down from 60%, not zero) — the shadow/lit split
   is by *median luminance*, so changing the image reshuffles which
   pixels land in each half and cancellation is approximate by
   construction.
2. **Sky response is inverted** — sky 1.6 raised blue in the LIT half
   (+16%) more than in the shade (+10%), so the ratio *fell* 4.8%. It
   moves the wrong way for the one lever it should track.

**It has no band and is not an acceptance.** Calibrating it needs a
daylight-shade reference measured the same way.

### Questions for the consult

1. Is `shade_over_sun_B` the right correction, or is there a standard
   metric for "shade colour independent of surface albedo"? The inverted
   sky response suggests the shadow/lit split is the wrong partition —
   should it be a *geometric* shadow mask (sun-occlusion) rather than a
   luminance median?
2. How should a shade-colour acceptance be calibrated? The project's
   reference is "daylight-shade photographic reference" — is there a
   defensible published value for B/luma of clear-sky shade, at a stated
   white point?
3. **The structural question:** R-GRADE sets WB from a grey card to the
   measured effective illuminant (1718 K below the source sun, because
   atmosphere reddens a 12°-elevation sun). Is that correct practice, or
   should WB track the *source* temperature and the warmth be carried as
   an explicit grade offset? The band assumes the latter; R-GRADE
   implements the former. **One of these two locked rulings has to give.**

---

## 2. Q12 — the 0.731 power law (inherited, still open)

Exposure response is a **power law with log-log slope 0.731**, tone curve
disabled and read back true. A requested −1.000 EV delivered −0.7266; a
requested −0.4453 delivered −0.3276. Two step sizes, one answer.

Candidates and their status:

- **PreExposure** — **ELIMINATED TODAY.** 4→16 produced bit-identical
  output; it is mathematically neutral absent clipping, and nothing was
  clipping.
- **`r.LocalExposure`** — ELIMINATED 2026-09-11. The cvars do not exist
  in 5.8; the PPV fields are all default.
- **MRQ tone-curve-disabled residual stages** (expand gamut / blue
  correction) — **LAST CANDIDATE STANDING, by elimination.**

The measured-slope solve stands as the exposure instrument (R-GREYCARD,
card lands at 0.180072). **Question:** what runs after
`bDisableToneCurve` in UE 5.8's MRQ deferred path that would compress by
a 0.731 power law?

---

## 3. The town stands on forest floor (needs a ruling, not analysis)

Measured: of 303 town buildings, **131 (43.2%) stand on `ForestFloor`**.

    Grass        165   54.5%
    ForestFloor  131   43.2%
    Scree          5    1.7%
    Rock           2    0.7%

Cause: `place_foliage.py` has **no settlement exclusion** — its only
exclusion is ground cover. `plan_encounters` has one. So trees are placed
through the town and the canopy-derived mask correctly reports canopy.
**The mask is right; the placement is the gap.**

Pre-existing — the alpha channel was already 255 there driving a tint.
Promoting forest_floor to a real surface made it visible.

---

## 4. Layers that exist as assets but not as layers

The material carries **five** layers (Snow, Rock, Scree, ForestFloor,
Grass); the plan calls for eight.

| layer | asset | blocker |
|---|---|---|
| `gravel` | Gravel021 (gated, CC0) | 0.52% coverage — folded into meadow |
| `wet_shore` | river_small_rocks (fetched, gated) | **derived weight is identically ZERO** (needs Brief 4's water level) |
| `dirt_path` | rocky_trail (fetched, gated) | **identically ZERO** (streets are ACTORS, no mask) |

Not built deliberately: a sampler and a blend for an always-zero mask is
cost for nothing. `derive_layer_weights --expand` **refuses** if either
stops being zero, so the omission cannot outlive its reason.

---

## 5. Rock layer provenance (needs a ruling)

`Rock051` is **bound** and its source and licence are **UNRECORDED**
(`ASSETS.md` row 37) — a shipping risk carried silently.

`gray_rocks` (Poly Haven, CC0, fetched today) measures linear luma
**0.1795** against Rock051's **0.1805** — a 0.6% match, with a named
author and a published 1.8 m physical size.

So the rock layer could gain a licence **without changing appearance**.
Different decision from `Rock016` (0.0712), where binding meant accepting
a 2.5× darkening.

---

## 6. A rule with four recurrences and no enforcement

A `.py` filename in recipe prose breaks remote execution — the engine
treats the first such substring as a pathname
(`PythonScriptPlugin.cpp:813-830`). It has now recurred **four times**
(LESSONS 12.10, 2026-09-10c, twice today).

The recipe warns about it **twice, in the block it governs**, and nothing
checks. A scan over the interpolated blocks would end it permanently.
Current state, measured today:

    foliage     1   rock_scatter
    material    2   derive_layer_weights, make_variant_map
    palette     2   make_alpine_palette, palette_evidence
    perception  2   angular_budget, place_foliage
    lighting    0   (cleaned today)

The `material` ones are harmless **only because** `layer_bands()` copies
named fields and never the underscore-prefixed prose — luck about a data
path, not a guarantee.

---

## 7. Smaller open items

- ~~**The editor's pre-exposure warning cannot be read from code.**~~
  **CLOSED 2026-09-13.** UE 5.8 still exposes no MessageLog API
  (enumerated: `module_names` empty) and the notification is still
  absent from every log file — but the question the item actually asked,
  *does the "14" name a setting or a computed scene value*, is now
  answered by arithmetic rather than by reading the toast.

  **It is the EXPOSURE COMPENSATION, which is ours, and it is a computed
  scene value — not the pre-exposure setting.** Read back from the
  engine this session: `r.EyeAdaptation.CachedLightingPreExposure` = **4**
  and `r.EyeAdaptation.PreExposureOverride` = **0**. Neither is 14 and
  neither ever was during the warning. The grey-card solve, meanwhile,
  put `auto_exposure_bias` at **−13.882** and then **−14.2554** — the
  only quantity in the chain whose magnitude is 14, and the warning's own
  "safe range −8 to 12" is an EV window, which a pre-exposure multiplier
  is not measured in.

  So the toast was reporting our own deliberately large negative EV. It
  has to be large: with Apply Physical Camera Exposure OFF the manual
  bias is the *whole* transfer from a 3481.9 K sun-lit scene to an 0.18
  card, where before it was a bias silently multiplied by the camera's
  aperture, shutter and ISO. The warning is EXPECTED at this bench's
  working point and is not evidence of a defect.

  Kept as evidence, not deleted: the pre-exposure elimination below
  (4→16 bit-identical) stands, and this closure explains why it had to —
  pre-exposure was never the quantity the warning named.
- ~~**`bench_capture.py --help` crashes**~~ **CLOSED 2026-09-12.** The
  cause was a literal `65%` in the `--linear` help string: argparse
  formats help as `help % params` with `params` a dict, so `%` followed
  by a letter is read as a conversion. Escaped to `65%%`; `--help` now
  renders, which is how this session found `--drop-cvar` and added
  `--add-cvar` beside it.
- **Remote exec is intermittently flaky** — one capture died with
  `RuntimeError: Remote party failed to send a valid response!`
  (`remote_execution.py:471`) during setup; a straight retry succeeded.
  RECIPES records a case where this accompanied a build that had
  **completed** and only the response was truncated, so the client-side
  error cannot distinguish the two. Ask the artefact, not the error.
- **The 09-10 baseline (1.1243) was measured against a weightmap dated
  14 August.** The engine held a stale `T_Alpine_8k_Weights` until it was
  reimported today. Every acceptance taken at that station in between
  described a world drawing month-old layer data.

---

## BRIEF 3 — FULL STATUS, TASK BY TASK

The brief: *the landscape material and its layers, layer weights, ground
textures, snow placement, forest floor, grass appearance, HLOD proxy
surface quality.* Out of scope by its own terms: tree density/PCG
(Brief 5), water (Brief 4), the town's cubes.

### Task 0 — Loading range — **DELIVERED, on the fallback**

Ruled as B3.6: 768 m target, **512 m fallback on perf**. The fallback is
what is live — every residency probe today reads
`loading range 51200 cm (512 m)`. HLOD0 to 2 km. Locked as the
precondition for all surface work.

**Consequence not yet chased:** Brief 1's 4K detail threshold (~700 m)
was said to move with this. At 512 m it has moved and nothing has
re-derived it.

### Task 1 — Grey-card white balance — **DELIVERED, with a live residual**

R-GRADE locked at **3481.9 K**, `temperature_type` pinned to
`white_balance`, `white_tint` 0, `warmth_bias_k` 0. Derived in two
Planck steps from the card, not tuned.

**Recorded residual:** R/G 1.0307 against a 0.97–1.03 band — misses by
0.0007 on a card std of 0.0046.

**⚠ Open, found today:** the card on today's *display-referred* target
frame reads `wb_ratio_R 1.0388 / wb_ratio_B 1.0586`, both outside
0.97–1.03. R-GRADE was locked on the **scene-linear** pass, and the
recipe explicitly warns these are different calibration classes — so
this is **not** a demonstrated regression, but it has not been re-checked
on a linear capture since the five-layer material landed. `highlight_tint`
on the same card PASSES (R 1.026 / B 1.0455, band 0.85–1.15).

### Task 2 — Layer set and derived weights — **PARTIAL**

**Done:** `derive_layer_weights` produces **eight** weights, locked as
R-LAYERS on three independent strands (hillshade direction, heightmap
orientation IoU, top-down flank). Acceptance measured: forest_floor
under canopy 0.9985 / open 0.0007; snow asymmetry shaded 0.4116 vs lit
0.0000; height-blend mushy fraction 0.2131 vs linear 0.5551.

**Not done:** the brief asked for **eight layers across two weightmaps**.
The material carries **five**, in one RGBA weightmap plus a shader
remainder:

    R=Snow  G=Rock  B=Scree  A=ForestFloor  remainder=Grass(meadow)

`gravel` (0.52%) is folded into meadow; `wet_shore` and `dirt_path` are
**identically zero** and deliberately not built (see §4 above). So the
eight-layer schema is *derived* but not *realised*, and the second
weightmap was never needed.

### Task 3 — Scanned surfaces at derived tiles — **MOSTLY DELIVERED**

**Done:**
- `tiling_m` **5.03 m** derived from texel budget (4096 tex / 814.9
  texels-per-m at the judgement camera), macro 188 m = 37.4× — inside
  the ruled 20–50× band.
- Five surfaces bound and verified in the built graph (32 samplers, 0
  mismatches): `Snow007A`, `Rock051`, `rocks_ground_04`, `forest_floor`,
  `WildGrass`.
- **The vendor plan changed under measurement.** The brief named six
  Megascans/Fab surfaces; **six of eight Megascans scans were REFUSED on
  8-bit JPEG displacement** — the layer blend is a height blend and 8
  bits over a few cm quantises to ~0.4 mm. Replaced with ambientCG and
  Poly Haven CC0 at 16-bit. `fetch_surface.py` now gates this at download
  time.

**Not done:**
- **Stochastic / hex tiling — OFF.** Ruled to stay off "until a layer
  needs it and the need is a number". Not declared anywhere in the
  recipe.
- **The acceptance tables have not been re-run on the five-layer world.**
  `tiling_score` per depth bin (30–100, 100–300 m) and albedo variation
  0.10–0.20 were last run at `Bench_ground` on the *three-layer* material
  against a **month-stale weightmap**. Both need repeating.
- **`wet pebbles`** (one of the six named roles) is fetched and gated
  (`river_small_rocks`) but unbound — its layer is identically zero.

### Task 4 — Grass appearance — **NOT STARTED**

PerInstanceRandom hue/brightness ±8%, card base colour sampled from the
underlying layer albedo, taller cards only where meadow > 0.7.
Acceptance: the meadow albedo-variation metric rises into 0.10–0.20 band
with the card mask unchanged.

### Task 5 — Proxy rebuild — **NOT STARTED**

HLOD approximate layer: texture sizing automatic-from-draw-distance,
geometric tolerance 0.25 m, capture 2048, roughness 1 / specular 0.
Acceptance: depth-bin contrast 300 m–1 km within ±30% of `fog_budget`'s
predicted transmittance.

### Send-back — **NOT PRODUCED**

`research/brief3/for_research/` **does not exist**. It should carry
near_ground / mid_slope / vista at 1920-wide after Tasks 3 and 5, the
weightmap sidecars, tiling and albedo tables, card readings, Task 0 perf
tables, and the REGISTER diff.

### Brief 3 in one line

**Tasks 0–3 are substantially delivered; 4, 5 and the send-back are not
started — and Task 3's own acceptance tables are unverified on the world
that now exists.** The blocking issue for closing Task 3 is §1 above:
the shade metric it would be judged against measures terrain albedo, and
the world's terrain just changed.

---

## What IS resolved today, for context

- **Five-layer material built and verified.** Scree and forest_floor are
  real surfaces with derived weights and scanned textures. 32 samplers, 0
  mismatches; 197 expressions, 0 orphaned — both audits share no code
  with the builder.
- **A month-stale weightmap found and fixed.** No audit could catch it;
  it took a render and a file timestamp.
- **Self-sourcing CC0 asset pipeline** (`fetch_surface.py`) that gates at
  download time — refuses no-height, 8-bit height, and decals.
- **A latent NN24 defect removed**: the variant map was being indexed
  with the weightmap's channel list.
