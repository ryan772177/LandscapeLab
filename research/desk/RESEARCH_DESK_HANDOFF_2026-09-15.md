# Research desk — handoff (2026-09-15)

Paste this at the start of a new chat, together with `AUDIT.md`. It carries the arrangement, what has been ruled,
what is proven, what is open, and the next prompt. Everything by path lives in `C:\Users\Admin\UE5LandscapePipeline`.
Supersedes the 2026-09-11 handoff.

---

## 1. The arrangement (unchanged)

**Ryan** runs an open-world UE 5.8 RPG (`Alpine8K`) plus two side products, operating Claude Code (editor + repo).
**This chat is the research desk.** It does not touch the repo. It reads the literature and Epic's 5.8 documentation,
derives the numbers, builds pure-Python tools in its sandbox, issues briefs, rules when Claude Code asks, and owns its
own errors. **Ryan ferries** files and session reports between the two and issues the rulings the desk proposes.

Standing method: every brief ends in a derived number, a measurement script, or a REJECTED entry with its reason.
**Doc check comes BEFORE the prompt, not after** — every lever named in a prompt is verified against the 5.8 docs or
the live cvar enumeration (`research/audit/inputs/cvars_5_8_live.txt`, 11,073 entries) first. Three misses this week
(r.TonemapperFilm, r.LandscapeLODBias, r.MaxAnisotropy at runtime) came from naming levers from memory.

Handoff folders: `research/brief<n>/`. Bench artefacts: `_verify/bench/<date>/`. Audit: `research/audit/`.

Standard prompt shape: `Session goal: <one line>. Read <file>. <ordered tasks with acceptance + read-back>.
<scope fences>. Stop and report after <task>.`

---

## 2. Products
| | what | state |
|---|---|---|
| **Alpine8K** (mainline) | 8129 vx @ 1 m, ~217k trees (2,557 cleared from town), five-layer ground, town = engine cubes | subject of all briefs |
| **forge 0.4.0** | concept-image → world; no Fab assets, ever | frozen |
| **concept forge** | image → prop meshes | idle |
Fab/Megascans allowed in the mainline only.

---

## 3. Standing rulings (do not re-litigate)

- **Judgement camera** 3840×2160 @ 90° H; 1440p floor; 8K inspection only.
- **Two instruments.** *Player* = dev/target MRQ, GameOverride absent, project TSR, temporal 8 on target.
  *Truth* = `--truth` only (the `--instrument truth` flag is retired, exits 2) = all regions force-loaded + the FULL
  GameOverride set: view_distance_scale 100, override VDS, flush_streaming_managers, disable_hlods, and the class
  defaults (cinematic_quality, use_lod_zero, high-quality shadows, texture streaming off) — all 20 recorded per truth
  capture, refuses on fewer. Truth cannot see LOD switches or culls. Only 6 of 111 bench captures ever used it; all
  intended it (V-8 CLEAN).
- **Linear vs look instrument (R-INSTRUMENTS).** *PPI0* (BL_SCENE_COLOR_AFTER_DOF pass-through, pre-grade, no WB,
  exposure-linear: −1 EV delivers −1.0000) is the SCENE-LINEAR instrument: exposure solve, albedo, anything absolute.
  *FinalImage* (post-grade) is the LOOK instrument: WB, tint, shade. A "--linear" capture is FinalImage with the tone
  curve off — post-grade, contains WB — and must be labelled as such, never as PPI0. FinalImage acceptances read from
  **EXR** (16-bit float); PNG is 8-bit and has been the look instrument by accident (one code = 1.5% of the card).
- **Bench (R-METER)**: Manual metering, Apply Physical Camera Exposure off, compensation solved on PPI0 to card 0.18
  (currently **−14.2571**), render warm-up **40 frames ON** (`render_warm_up_frames True` — it was False for the whole
  project before 09-13), engine warm-up 300, no wind exists (do not add a wind override).
- **Grade (R-GRADE)**: temperature_type white_balance, **white_temp_k 3415.7**, **white_tint −0.0113** (re-solved
  09-14 after R-SKYCOLOR; slopes re-measured), contrast **0.95 effective** (was 0.9025 until 3525bc87 — the shader uses
  xyz·w; recipe value now goes to w with xyz = 1). Q12 CLOSED: the exposure "power law" was contrast × a 0.797
  output-encoding term, no film curve; the 0.797 stage is unnamed, measured, cancelled at the card.
- **R-SKYCOLOR (09-14)**: sky light colour **white (1,1,1)**; the old [0.42,0.6,1.0] was double sRGB-encoded (red 62%
  high, green 33%). apply_lighting passes linear once. Census: all four Epic sample sky lights are white.
- **Shade acceptance (R-SHADE)**: two 18% grey cards, one sunlit, one blocker-occluded; on PPI0, each card's channels
  ÷ the lit card's channels (numerical WB), B/luma (Rec.709) per card, ratio shade/lit. Band from
  `research/brief3/scripts/shade_reference.py --white <white_temp_k>`: **2.254–3.029 at 3415.7 K** (was 2.184–2.940
  at 3481.9). Re-derive whenever white_temp moves. The 1.10–1.60 band is STRUCK. 09-14's "0.5592" was not this metric.
- **Tiling verdicts are player-instrument only.** At temporal 1 the 30–100 m peaks are aliasing (moiré of 815 texels/m
  against the pixel grid at a grazing angle); under TSR history they cease to be local maxima. Task 3 tiling: PASS all
  layers, both bins, on the player instrument. Automatic View Mip Bias already on for all 32 samples; no RVT.
- **Tile size per layer from the scan's stated physical size**: Rock 1.80, Scree 2.00, ForestFloor 2.14; Snow007A and
  WildGrass UNSTATED → 5.03 ceiling. Stochastic tiling: proven plumbing, NOT adopted (it did not move the peak).
- **R-RANGE 512 m**; **R-PERFBUDGET** GPU 1.2× standalone p90 per zone, game 6.0 ms, frame 16.6 ms, standalone -game at 4K.
- **Landscape HLOD (R-HLODTEX, 09-14)**: landscape HLOD runs through Instanced → Merged by world-default fallback;
  `Alpine8K_HLODLayer_Landscape` and `FoliageApprox` are unreferenced/inert (REDUNDANT, deletion deferred). The
  landscape levers are ALandscapeProxy.HLODTextureSizePolicy / HLODTextureSize / HLODMaterialOverride /
  HLODMeshSourceLODPolicy. **HLODTextureSize 4096** (was 256 = 8 m/texel on 2 km cells), SPECIFIC_SIZE, 257/257.
  Derivation: cell 2000 m ÷ (512 m ÷ 1920 px) ≈ 7,500 → 8192 at the hand-off, 4096 accepts a 1 km judgement distance.
- **Foliage regeneration** is gated on the planting-field contract: planting field = terrain-only meadow;
  render weightmap = planting + canopy. Trees never plant on a field their own placement shaped. Acceptance ±2% of
  219,659 and independence ~0.1% (was 22%). Plus a FLOOR gate (refuse below −20% of the ruled count) — the
  ceiling-only gate let a 152-instance regeneration pass.
- **Rule 12** (derive, read back, record both sides) and **Rule 13** (every comparison reports its sample count beside
  its verdict — a bare sg.X console query prints nothing and once produced "two instruments agree" with zero samples).
- **Lighting actors are saved and committed by apply_lighting.** `make_foliage_material` saved nothing for five weeks
  (empty name) — disk-read checks in that window are suspect; graph-read audits stand.

---

## 4. Briefs

**Brief 1 — distance as angle** DONE (09-05/07). Four-band ladder; culls from pixel thresholds; HLOD built after five
stacked defects. OWED: detail threshold re-derived at 512 m (`angular_budget`), never reported.
**Brief 2 — atmosphere / sky / grade** DONE (09-10). Fog model confirmed against 5.8 docs (both inscattering colours
black → Sky Atmosphere colours the fog). OWED: `Cloud_GlobalCoverage` 0.1 capture with read-back (0.3 = near overcast).
**Brief 3 — surface** NEAR CLOSE:
- Task 0–3 DONE. Five real layers (snow, gray_rocks 1.8 m, rocks_ground_04 2.0, forest_floor 2.14, WildGrass), all
  licensed, 16-bit height, DX/GL normal convention was inverted on 6/6 packs and fixed. Tiling PASS on player instrument.
- Task 4 (grass appearance) — baseline 0.6695 at 4–10 m vs references 1.22–1.26 (FinalImage std/mean, shadows in);
  ±8% hue/brightness applied and kept, moved the metric 0.09%: the variation is LIGHTING STRUCTURE (self-shadow,
  contact, soil). Stage 2 = shadow read-backs (foliage cast_dynamic_shadow, VSM, sun contact_shadow_length, card
  normal) + one discriminator capture each → NOT YET RUN. Mid-distance flatness re-scoped to Brief 5 (clutter density).
  Band 1.0–1.5 at 4–10 m is provisional from two references; Ryan owes 4–6 more meadow photos.
- Task 5 (proxy rebuild) — RUNNING: 24-way incremental HLOD build (started 09-15 ~01:50, ~12 h, batches commit
  themselves). Every cell approving (texture-size hash change). Acceptance still owed: at vista/mid_slope on PPI0,
  300 m–1 km contrast within ±30% of fog_budget's transmittance; proxy-vs-real albedo ±15% per layer; standalone perf.
  **Check first thing: landscape cell count in the completion table — zero means 4096 never reached the landscape hash.**
- Send-back — not produced.
**Brief 4 — water** RULED YES (lakes, rivers, waterfalls, caves — fantasy RPG). Desk derivation delivered
(`research/brief4/scripts/hydro_derive.py`, `research/brief4/input/hydro.json`, `hydro_map.png`): three lake
proposals (A east basin 180 m/125 ha — drowns Bench_ground; B town tarn 140 m/13.6 ha; C west lake 268 m/89 ha), the
south river past the town (5.3 km, cuts 10 m mean/47 m max — chain-of-pools recommended), 78 waterfall candidates.
Terrain is hydrologically closed (17% in depressions). Water carves BEFORE foliage regeneration. Awaiting Ryan's pick.
**Brief 5 — density/PCG** after 4. **Brief 6 — caves/hero locations** after 5. Foliage + Merged HLOD rebuild once, after 5.

---

## 5. The audit (read `AUDIT.md` — running record, §1–§10)
Passes: 1 levers DONE (amended §8–§9); 2 properties PARTIAL (copy-trap CLEAN, API-name pass pending); 3 scripts vs
own claims NOT STARTED (needs sidecars — received); 4 rewrite NOT STARTED (needs `history_diffs.txt`, 8 MB, on Ryan's
disk); 5 findings 405 → 4 ruled.
Biggest finds: sky light double-encode; landscape HLOD 256-texel bakes; truth instrument never defined; lever scan blind
to setters (+32 levers); contrast 0.9025; foliage floor gate never merged; look instrument 8-bit by accident.
Corrections to the audit itself: "94 verdict sites" → 4 live bare save_asset sites (54 were under dist/); cvar
inventory v1 misclassified reads as writes; sky.color was a setter, not missing.
Open rulings for Ryan (AUDIT §7): archive 620 uncalled / 899 untested scripts; LESSONS/RECIPES append-only vs curated.
Content gate: model fixed (canopy is alpha-tested, passes ~21% of rays; near_ground 81% canopy explains 17.8–25.4×
error) — RULED apply, threshold unchanged, not yet applied.

---

## 6. On Ryan's desk
1. Lake / river rulings for Brief 4 (A, B, C; south river; carve vs chain-of-pools).
2. 4–6 alpine meadow photos, ground level, two looking across level meadow (Task 4 band).
3. `history_diffs.txt` to the desk when Pass 4 starts.
4. Copy the desk's `AUDIT.md` into `research/audit/` after each update so both sides read one record.

---

## 7. Open questions (logged, not chased)
- The 0.797 output-encoding term in the tonemap pass with the curve off — unnamed, cancelled.
- Bench_ground station sits on lake A's floor (63 m) — moves when Brief 3 closes.
- 18 foliage plans fail freshness (pre-existing, waivers expired on recipe edits) — Pass 4 keys waivers to consumed fields.
- `.git` still carries ~1.2 GB of dolly frames; `filter-repo` never run. `dist/forge-*` 428 .py inside the landscape repo.
- Temporal tool (tile-wise motion compensation) still owed by the desk before the dolly is scored.
- Re-census: Epic samples' landscape HLOD proxy properties were never collected (sample_census reads material only).

---

## 8. Tools of record (desk-built, pure Python, self-tested)
angular_budget, temporal_stability (global-motion only — tile-wise owed), lod_silhouette_check, measure_concept_look,
fog_budget, void_mask, texel_budget, tiling_score, sample_census, **shade_reference** (band from white point),
**hydro_derive** (basins, flow network, waterfalls from a heightmap). Claude Code's instruments of record for Brief 3:
tile_peak (three-column: value / threshold / verdict; signed prominence), task3_weight_period, tonemap_transfer,
warmup_settle, ll_must (must_exist / must_save / must_connect / cvar_must).

---

## 9. Next prompt (morning of 09-15, after the build) — confirmed against 5.8 docs (EXR output class, high_precision_output)

```
Session goal: close the overnight build, then Part C of the 09-14 overnight prompt with the re-derived shade band.

Read research/audit/AUDIT.md §10 and the handoff §3. No lighting, grade, material or foliage values move.

1. Build: if the last batch commit is older than 45 min, read the log before anything else. On completion: per-layer and
   per-cell attribution table, LANDSCAPE cell count (zero = 4096 did not reach the landscape hash → stop and report),
   total elapsed, VRAM peak series, tree clean.
2. Item 10: confirm in the editor which buffer the 09-14 WB solve read (expected: tone-curve-off FinalImage from --linear,
   post-grade). Correct every sidecar/register line that called it PPI0. Add an `instrument` field to the sidecar with
   one of: ppi0 | finalimage_linear | finalimage_look | truth.
3. Item 11: run the EXR look-instrument construction once at Bench_ground (MoviePipelineImageSequenceOutput_EXR,
   compression ZIP, multilayer False; PPI0 pass high_precision_output True); dump the config as held (closes V-6);
   re-read card temp/tint on the EXR FinalImage; report codes-per-card replaced.
4. Item 12: shade pair on the 09-13 instrument (PPI0, channels ÷ lit card, B/luma Rec.709, ratio shade/lit) against
   **2.254–3.029** (shade_reference.py --white 3415.7). Docstring carries the white point. The 1.10–1.60 row does not appear.
5. Content gate: apply the transmissive-canopy model (~21% pass), threshold unchanged; re-derive predicted fractions for
   all three stations; read back against the last ten captures.
6. Task 5 acceptance on the rebuilt proxies: vista + mid_slope on PPI0, 300 m–1 km contrast vs fog_budget ±30%;
   proxy-vs-real albedo per layer ±15% (BaseColor ÷ 2^compensation); standalone -game 4K perf vs R-PERFBUDGET.
7. Item 13: re-census with the four landscape HLOD proxy properties; Electric Dreams beside our 4096 / SPECIFIC_SIZE.

Stop and report after 6 (7 if time). Report: build table, instrument correction, EXR card readings, shade ratio vs the
new band, gate read-backs, Task 5 acceptance table + perf, census values.
```

After that: Task 4 stage 2 (shadow read-backs + discriminators), then the Brief 3 send-back, then Brief 4 opens on
Ryan's lake/river ruling.

---

> AMENDMENT 2026-09-15 (Block A): §3 shade band is now 2.065–2.998 @ 3438.6 K (floor D6000, sun < 30°) per R-SHADEBAND; white_temp 3438.6 / white_tint −0.0248 / compensation −14.2571 per R-WB2x2 (A-6). The CURRENT VALUES table in RECIPES.md (Pass 4) is the in-force record from here on; this file is the desk's state as of 09-15 morning.
