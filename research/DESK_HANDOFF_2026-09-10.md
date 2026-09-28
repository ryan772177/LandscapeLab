# Research desk — handoff

Paste this at the start of a new chat. It carries the working arrangement, what
has been ruled, what is proven, what is open, and what the next brief needs.
Everything referenced by path lives in `C:\Users\Admin\UE5LandscapePipeline`.

---

## 1. The arrangement

**Ryan** runs an open-world UE 5.8 RPG (`Alpine8K`) plus two side products. He
operates Claude Code, which has the editor and the repo.

**This chat is the research desk.** It does not touch the repo. It:
- reads the literature (human vision, sampling/perception math), the engine's
  behaviour, and Epic's sample projects;
- derives the numbers that go into recipes, instead of letting them be typed;
- builds and tests pure-Python measurement tools in its sandbox;
- issues per-topic **handoff folders** — `BRIEF.md` (the eye → the math → what
  UE offers → the derived number → the gate → sources), `scripts/` (tested, or
  marked DRAFT), `FOR_CLAUDE_CODE.md` (ordered tasks, each with its acceptance
  measurement and where it lands), `REGISTER_ADDENDUM.md`;
- **rules** when Claude Code asks for a decision, and owns its own errors.

**Ryan ferries** frames, JSON and session reports between the two, and issues
the rulings the desk proposes.

Handoff folders live at `research/brief<n>/`. Sample-project census at
`research/census/`. Bench artefacts at `_verify/bench/<date>/`.

Standard prompt shape for Claude Code:

> Session goal: <one line>. Read research/brief<n>/FOR_CLAUDE_CODE.md and start
> at Task <k>. <scope fences>. Stop and report after <task>.

---

## 2. The three products

| | what | state |
|---|---|---|
| **Alpine8K** (mainline) | 8129 vx @ 1 m, ~220k foliage, town still engine cubes, hero parked | the subject of all briefs |
| **forge 0.4.0** | concept-image → world, shipped to friends, no Fab assets | frozen; separate, smaller product |
| **concept forge** | image → prop meshes (church, wood stack) | idle |

Fab/Megascans assets are allowed in the mainline, **never** in the forge.

---

## 3. Standing rulings (do not re-litigate)

- **Judgement camera**: 3840×2160 at 90° horizontal. 1440p is the floor. 8K is
  inspection only. Every perception-derived distance comes from this.
- **Two instruments**: *player* (PIE/MRQ, partial residency — what a player
  sees) and *truth* (all regions force-loaded). Neither pretends to be the
  other; cross-instrument comparison is not a valid gate basis.
- **Derive, read back, record both sides.** A parameter that is not read back
  is prose. A read-back that shares storage with the write is also prose. An
  instrument with no control is zero measurements. A zero is only trustworthy
  if the lookup reached where the thing lives.
- **Perf** is measured in a standalone `-game` process at 4K, never the editor
  (editor game thread is pinned ~14 ms by its own tick and renders at half the
  pixels). R-PERFBUDGET: GPU = 1.2× standalone p90 per zone, game 6.0 ms,
  frame 16.6 ms.
- **Loading range 512 m** (R-RANGE), after 768 m failed treeline by 0.16 ms.
  Brief 1's detail threshold moved to 512 m with it.
- **Card-based calibration in scene-linear** (MRQ EXR, tone curve disabled):
  18% grey card target 0.18 ±5%; exposure by the measured response slope.
  WB locked at 3481.9 K with a ~3% tint residual; `white_tint` 0 until it has
  a measured slope. `grade.warmth_bias_k` 0 on the bench.
- **shadow_tint_B band 1.10–1.60** under neutral WB (re-derived; the old
  1.3–1.7 PASS had been measured under a blue-amplifying grade).
- **Lighting actors are saved and committed** by `apply_lighting` — a crash
  once reverted five tasks of applied values while every artefact carried them.

---

## 4. Briefs

**Brief 1 — distance as angle** (delivered 2026-09-05). Every authored cull
removed an object 10–39 px tall at 4K; a 27 m conifer is under 6 px only at
4.7 km. Four-band ladder (detail / shape / blob / gone), culls derived from
pixel thresholds, imposters and HLOD as the hand-offs. Tools: `angular_budget`,
`temporal_stability`, `lod_silhouette_check`. **HLOD had never been built** —
the world did not exist beyond ~1 km. Built after five stacked defects (layer
registration under `RuntimeHashSet`, XGE swallowing commandlet shader jobs,
MeshMerge cannot decimate, proxy budget from the blob band, batching per
process). E1–E4 done: derived culls, LOD audit (billboard LODs switch far too
early — a number, not a rebuild), standalone perf, sunlit dolly at −67.5.

**Brief 2 — atmosphere, sky light, grade** (delivered 2026-09-08, completed
2026-09-10). Shadows were 3× bluer than bright (sky light 1.8 → 1.0); no
aerial perspective (fog 0.0015 from 1.5 km → derived 0.00416, falloff 0.0193,
start 0, colour from the SkyAtmosphere). Mie 0.01. Clouds. Tools:
`fog_budget`, `void_mask`, `measure_concept_look`. **The colour sky mask was
never valid** — mid_slope's "40% non-sky band" was ~72% misclassified sky;
replaced by a depth-pass mask, which also showed fog *was* converging toward
the sky while the colour instrument said the opposite.

**Brief 3 — surface** (delivered 2026-09-10, in progress). Real ground ended
at 256 m so proxies stood in the detail band. Eight-layer set with derived
weights (snow by aspect — proven by hillshade 18–40×, heightmap orientation
against the render by skyline IoU, and a material check), height blend, tile
size derived (4096 → 5.03 m at 815 texels/m), stochastic tiling available but
not yet needed. Tools: `texel_budget`, `tiling_score`, plus
`hillshade_snow_check` and `heightmap_orientation_check` promoted to scripts
of record.

**Briefs queued**: 4 — water (SingleLayerWater, shoreline, depth absorption);
5 — density and PCG (forests, ground clutter, the instanced-HLOD range vs
cost question); 2c — Lumen far-field on the light HLOD proxies (by ruling).

---

## 5. What the census taught (five Epic samples, `research/census/`)

- HLOD is two-level: Instancing 256 m cells to 768 m, Approximate 2 km cells to
  **16 km**; simplification by **geometric tolerance** (0.25 m, 2 tris/m²), not
  a fixed triangle count; texture size **automatic from draw distance**.
- HWRT is fenced by **distance and class** — Electric Dreams 100 m / 2°, City
  150 m / 0.5° with instanced meshes excluded and RT shadows off — not toggled
  globally.
- Electric Dreams: sun 100,000 lux, sky light 1.0 real-time lower-hemisphere
  black, Mie 0.01/g 0.8, fog 0.02 from 0, **cull distance 0 on all 62 Nanite
  clutter types**, `grass.Enable=0` (everything from PCG), TSR tuned for
  foliage flicker.
- Epic's own 5.8 samples still run **Nanite Foliage off** → Brief 1 Task 9
  stays "evaluate, don't migrate".
- `AutomatedPerfTesting` and MRQ are Epic's own station/capture frameworks.
- Valley of the Ancient is **blocked** on a 5.7→5.8 C++ port (FUNC_DECLARE_EVENT
  signature, stricter UE_LOG validation). Its landscape material and lighting
  are the one reference still unread.

---

## 6. On Ryan's desk

1. **Six 4K surface scans** into `Free/` (Fab/Megascans, mainline only), with
   height maps: alpine meadow, conifer needle litter, granite cliff, scree,
   wet river pebbles, snow. Brief 3 Task 3 cannot bind textures until these
   exist; the layer set is on placeholders and says so in its sidecar.
2. **Possibly a hand-picked `Bench_ground` station** from the top-down render —
   the derivation has missed twice (grass not modelled; a uniform rise
   compresses distance). One more derivation is authorised; if it misses, Ryan
   picks the point and it becomes the station by ruling.

---

## 7. Open questions (logged, not chased)

- Exposure response is a power law, log-log slope **0.731** — candidates:
  scene pre-exposure, residual MRQ stages with the tone curve "disabled"
  (expand gamut / blue correction), `r.LocalExposure`. Read the local-exposure
  state once; if non-default, that is the answer.
- `Cloud_GlobalCoverage` 0.3 rendered near-total overcast — not a sky fraction.
  A 0.1 capture with the parameter read back is pending.
- The 0-dirty editor-close wedge (fourth occurrence; window destroyed, process
  idle, remote exec dead) — not a modal, cause unknown.
- Instanced-HLOD layer range (2 km) is most of treeline's GPU cost → Brief 5.
- Q12-class residency stragglers: explained as rim actors against a 256 m
  expectation; the derived gate reads missing 0 at 512 m.
- `.git` still carries ~1.2 GB of dolly-frame history; `filter-repo` never run.

---

## 8. Tools built by the desk (all self-tested, pure Python)

    angular_budget.py            px / distance / UE ScreenSize per species, with verdicts
    temporal_stability.py        moving-camera pop detector (NOTE: single global motion
                                 compensation — a tile-wise replacement is owed before
                                 the dolly is scored)
    lod_silhouette_check.py      LOD chains by coverage/IoU/luma at the shown size
    measure_concept_look.py      palette, sky gradient, skyline, haze, grade on any frame
    fog_budget.py                fog density from a transmittance target; falloff from a
                                 stated halving rule (model verified against the shader)
    void_mask.py                 magenta-ground void counter
    texel_budget.py              texel density, derived tile size, CSF repeat threshold
    tiling_score.py              autocorrelation repeat score on a ground crop
    sample_census.py             read-only census payload for sample projects

Owed by the desk: the **tile-wise temporal tool** (per-tile motion compensation,
so parallax on a walking camera stops registering as change).

---

## 9. How to resume

Open the new chat with this file and say which of these is next:

- **Brief 3 continues** — bind the scans, Task 4 (grass appearance), Task 5
  (proxy rebuild with the sourced HLOD settings), then the Brief 3 send-back.
- **Brief 4 — water** — needs a ruling on whether Alpine8K gets a lake at all.
- **Brief 5 — density and PCG** — the biggest richness jump, and the largest
  asset question.
- **The temporal tool** — if the dolly is about to be scored.

The desk's standing method: every brief ends in a derived number, a measurement
script, or a REJECTED entry with its reason. A brief that ends in prose goes in
`plans/`, not the working set.
