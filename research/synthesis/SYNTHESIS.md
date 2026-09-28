# SYNTHESIS — Briefs 1–6 + audit: the best proven state (read-only, 2026-09-23)

Read-only inventory. Sources: RECIPES.md, LESSONS.md, STATE.md, REGISTER(s),
research/brief{1..5}/, hero/, research/audit/, git. Six per-brief agents +
direct read-backs. Nothing written outside research/synthesis/.

---

## 0. REGRESSIONS (read back from ini/recipe, not memory)

**No genuine regression found.** The two suspected ones both read back as the
ruled-and-applied state:

| suspected | read-back | verdict |
|---|---|---|
| **Exposure 14.3 outside safe [-8,12]** | The value near 14.3 is **compensation_ev = −14.2571**, the RULED A-6 R-WB2x2 manual-exposure solve (grey card R/G 1.0014, PPI0 0.1805 in band; RECIPES.md:15,19750). **[-8,12] is NOT a comp_ev bound** — it is "the exposure range the default pre-exposure PRODUCES" (LESSONS.md:32908-32920); the pre-exposure cvar reads **4.0** live, not 14. The warning **conflates comp_ev with the pre-exposure range.** | NOT a regression |
| **Spiky landscape/rocks** (forensics) | The per-vertex spikes are **Nanite landscape tessellation × 0.40 m displacement** — a RULED config (R-NANITE8129 RECIPES.md:91; `r.Nanite.Tessellation=1` DefaultEngine.ini:263; `MaxPixelsPerEdge=1` :295, ruled 4→1; displacement 0.40 m RECIPES.md:1365). Source heightmap CLEAN (max 3×3 dev 163/65535); LFS fsck OK; HEAD==pre-density-daylight; no landscape/mesh/material changed since 9/13–9/19. | NOT a regression — ruled config, but visually questioned (see forensics/spikes.md) |

Ruled levers that DID read back correct on main: streaming `main_loading_range_cm`
= **51200 (512 m)** = R-RANGE fallback ✓; `r.Nanite.MaxPixelsPerEdge=1` ✓;
`r.Nanite.Tessellation=1` ✓; foliage `density_per_hectare` = 135 (m=1) ✓.

The one live-only item that CANNOT be read back offline (PPV lives in the .umap):
whether the live editor's on-screen exposure matches comp_ev −14.2571. If Ryan's
editor shows a different number, that is an editor/PPV-override drift to confirm
with an in-editor read (out of this read-only fence) — but the ruled+proven value
is −14.2571 and the [-8,12] comparison is the wrong test.

---

## 1. PER-BRIEF LEDGER

### Brief 1 — distance / HLOD / LOD-as-angle
- **Goal:** derive cull/LOD/HLOD switch distances from on-screen pixels so nothing pops as it is deleted; fill the band past the streaming range with HLOD.
- **Rulings:** R-ANGBUDGET (detail 40 / silhouette 6 / vanish 1.5 px @4K/90°, RECIPES.md:15110); R-RANGE (512 m, RECIPES.md:18668); R-HLOD / R-HLOD-INFORCE (registration is the gate, :20265); R-HLODTEX (landscape HLOD 4096, 0.49 m/texel, :20918); R-INSTRUMENTS (player vs truth, :25).
- **Applied on main:** full HLOD build **2,267 packages** (1,225 Instancing + 1,042 MeshApproximate), 9.71→1.47 GiB — **PROVEN**; mid_slope featureless 0.9383→0.7464 (−19.2 pts) — PROVEN (indication). Angular culls: all 4 species cull above the 40 px threshold — PROVEN.
- **Branch/unmerged:** none (e3-standalone-perf 0 ahead, merged).
- **Rejected:** metres-chosen cull (pops); editor viewport as frame instrument; tri-count as LOD acceptance.
- **Best proven:** the 2,267-cell HLOD build fills the previously-void distance band.

### Brief 2 — atmosphere / exposure / white balance / tonemap
- **Goal:** physical atmosphere + manual exposure + neutral WB, verified by grey card not eye.
- **Rulings:** R-METER (AEM_MANUAL, physical-camera-exposure OFF, RECIPES.md:19733); **A-6 R-WB2x2 (comp_ev −14.2571, white_temp 3438.6 K, tint −0.0248, RECIPES.md:15,18,19)**; R-BENCH (PPV owns exposure, no profile sets AutoExposure, :17133); R-SKYCOLOR (sky white, :20637); Q12 CLOSED (under-delivery was tonemap contrast×encoding, not adaptation, LESSONS.md:34535).
- **Applied on main:** comp_ev −14.2571 (V, card 0.1805 in band); WB 3438.6 K (V, R/G 1.0014). DefaultEngine.ini sets only ExtendDefaultLuminanceRange + LocalExposure contrast (0.8/0.8, read back overridden=False → inert); no AutoExposure pin (correct per R-BENCH).
- **Branch/unmerged:** none.
- **Rejected:** AutoExposure=0 (overwrites the PPV, 4-stop blow-out); white_temp 8800 K (renders warm — REJECTED by Ryan); comp_ev by eye.
- **Best proven:** the A-6 R-WB2x2 joint solve — the baseline-zero for every comparison since 2026-09-15.

### Brief 3 — surface materials / tiling / layers / displacement
- **Goal:** per-layer scanned surfaces at camera-correct tile sizes + multi-layer weightmap.
- **Rulings:** R-RANGE 768→512 (RECIPES.md:114); R-LAYERS (8 derived weights LOCKED, precedence snow>rock>scree>ff>wet_shore>dirt_path>gravel>meadow, :18310); R-TILE (per-layer tiles: **Rock 1.80 / Scree 2.00 / ForestFloor 2.14 m**, :19949); R-LAYERS5 (5 layers from 4 channels, **OFFLINE HALF-LOCKED**, :19520); displacement 0.40 m (:1365).
- **Applied on main:** B3.20 no player-visible texture-tile repeat at 30–100/100–300 m — **M, ADOPTED**; 8 layer weights shipped (w8). **R-TILE/R-LAYERS5 tile sizes RULED OFFLINE but the material graph is NOT rebuilt in the editor** → the per-layer surface pass is **WITHHELD from the live material** (RECIPES.md:19577).
- **Branch/unmerged:** brief3-task0-range768 merged (0 ahead).
- **Rejected:** scree stochastic tiling NOT ADOPTED (peak never moved); typed tiling_m; one-period-for-multi-tile.
- **Best proven:** B3.20 (no visible tiling on the player instrument). **Owed:** rebuild the material with the ruled per-layer tiles + 5-layer contract.

### Brief 4 — water
- **Goal:** place the ruled water set as static meshes on /Game/Alpine8K, carve navmesh, re-freeze encounters + foliage.
- **Rulings:** R-WATER-CARVE (static Plane + M_SideWater at level-Z, NOT the Water plugin, RECIPES.md:21277); lakes A@180 m/125.5 ha, B@140 m endorheic, D@590.9 m; reachable **35.32 km²**, walkable 47.77.
- **Applied on main:** **288 water actors spawned + SAVED**; navmesh carved (277 NavArea_Null + rebuild); encounters re-frozen **317→305**; foliage regen 185,385==planned; suite green. **R-WATER-CARVE FULLY LANDED** (RECIPES.md:21279). (Brief 4 predates the M/D/P letter convention → effective = Done.)
- **Branch/unmerged:** none.
- **Rejected:** UE Water plugin; plane-to-bbox (over-floods); fall pitch +90.
- **⚠ verification-quality flag:** the landscape proxies were last rewritten by **T5's carved-heightmap re-import (2026-09-19)** — the FIRST 8129 push, the 25 s run **DIED mid-transport**, re-ran at 120 s, **verified by only 1280 samples**; collision truth ~50% blind. (Forensics since proved the on-disk heightmap is clean, so the geometry is sound; but T5 remains the weakest-verified geometry write.)
- **Best proven:** the water is LIVE + SAVED, R-WATER-CARVE FULLY LANDED.

### Brief 5 — density / foliage / PCG / T4
- **Goal:** make the densest decile read as real forest (cover 0.70) without busting the forest_floor GPU budget.
- **Rulings:** R5-1 forest_floor budget **13.0 ms** (desk revision; lives only in STATE/REGISTER, not RECIPES); **R-AESTHETIC-1 (2026-09-23): ms budgets SUSPENDED, perf recorded not gated, visual gate = Ryan on stills** (hard stops: VRAM 13,312, DEVICE_HUNG, persist, tag-before-write, fence); density-ceiling D_max 1,691/bin; T4 rungs DEMOTED to BACKLOG.
- **Applied on main:** shipped foliage **m=1, 185,385 trees**; T3 card→geometry hold applied + persisted + proven live (forest_floor 12.645 ms, REGISTER.md:98). Recalibration (T4 gate): ff cap 2.38→**1.162**, plaza 2.157. B5.14 M (cover 0.197→0.519 woodland), B5.18 M-FALSIFIED (model ~9× low), B5.23–B5.29 M.
- **Branch/unmerged:** density-100-experiment (dead pre-8K world, not adopted); the D3 812k regen was **REVERTED (07ee6246)** — not on main. Brief-5 NOT PUSHED at the time (now pushed through the T4 records).
- **Rejected:** the density upgrade (busts GPU: ff 15.34/plaza 12.94); the cvar levers (≤0.128 ms vs ~2.7 ms deficit); T4 tri-rungs (≥3.50 ms untouchable floor).
- **Best proven:** the T3 hold (12.645 ms). **No density increase is currently shippable at forest_floor — the cost is structural.** R-AESTHETIC-1 may reopen the path (visual-gated, budgets suspended).

### Brief 6 — caves / hero
- **Goal:** never formally run — a forward slot in the desk sequence.
- **Rulings:** HERO PARKED (Ryan, CLAUDE.md:397); R-HEROHAIR (Hair_M_SideSweptFringe @0.75, working model, RECIPES.md:12466). No R-CAVE, no cave ruling (caves are only a Brief-4 lore hook — the 140 m tarn shaft).
- **Applied on main:** the locked MetaHuman hero recipe chain (R-HERO…R-HEROHAIR) — the BUILT hero assets are gitignored/derived, only recipes + external-actor refs on main. Caves: nothing.
- **Branch/unmerged:** none.
- **Rejected/parked:** the DNA route (superseded by the sanctioned round trip); custom grooms (~40 dead probes); whole hero effort PARKED.
- **Best proven:** the working MetaHuman hero prototype (parked). **Cave half not started.**

---

## 2. AUDIT CARRY-OVER (research/audit/, 405 findings ruled)

**381 OBSOLETE, 24 APPLY.** Reading the 24: **most are stale-ledger** — the finding
was ALREADY applied and the ledger's text-search missed it (e.g. Rock051
retirement done in the recipe; B-APPEND-GUARD built; grounding epsilon 0.45 m in
trace_grounding.py:187; cull-ladder + declared_camera res in alpine_8k.json;
save_level on-disk existence check; F-1 floor gate — now armed via place_foliage
--ruled-count, added in Brief-5 D3). Confirmed still applied.

**Obsolete-now-live:** none found — the 381 obsolete are closed/superseded records;
the current state does not resurrect any.

**Genuinely owed (unapplied, ranked by cost):**
1. **city.json:150 `_THRESHOLD_NEEDS_A_RULING`** (0.05 provisional) — a LIVE operator ruling still owed. (needs Ryan)
2. **Seed/doc corrections (rule 9)** — cheap, high-integrity: schema.md:832-833 (unreproducible band stated normative, LESSONS:11584); PHASE2_PLAN.md:81 (~110 anims vs measured 102); PHASE2_PLAN.md:248 (banner omits the MULTI-REGION ruling); RECIPES.md:6602 (false "no residency gate"); WORLD_ARCHITECTURE.md:206 ("VRAM never measured on the 5080" — it has been); PHASE2_PLAN.md:142 (Unit 6 CustomNavigableGeometry stale).
3. **ue58-api-protocol.md casualty-list additions** — `hit_actor` (LESSONS:1734), `ReadRenderTargetRawPixelArea` min/max semantics (LESSONS:1878).

---

## 3. UNMERGED WORK

**None worth consolidating.** brief3-task0-range768 (R-RANGE 512) and
e3-standalone-perf (E1-E3) are both **0 commits ahead of main** (merged).
density-100-experiment-20260808 is 1 commit on the **DEAD pre-8K `Alpine` world**
(conifer 68→100/ha, "CAPTURE ONLY, NOT ADOPTED"), 1,312 merge-tree conflicts vs
main → reject. **The best proven state of every brief is already on main.**

---

## 4. CONSOLIDATION CANDIDATES — best-of-everything, ranked by visual payoff / hour

| # | what | brief/source | state | fence class | payoff/hr |
|---|---|---|---|---|---|
| 1 | **Rebuild the landscape material with the ruled per-layer tile sizes + 5-layer contract** (R-TILE/R-LAYERS5) | Brief 3 | RULED OFFLINE, never rebuilt in editor | asset (material graph) | HIGH — the surface look is decided but not on screen |
| 2 | **Re-examine Nanite landscape tessellation × 0.40 m displacement** (the "spikes"): shoot as-is / Tessellation=0 / displacement-reduced stills, let Ryan rule the look | Brief 3 + forensics | ruled config, visually questioned | ini/asset (test is ini-only) | HIGH — directly addresses the reported defect, cheap to test |
| 3 | **Resolve the exposure display confusion** — confirm the live PPV shows comp_ev −14.2571 (not "14.3"); if an override drifted, re-pin manual | Brief 2 | ruled −14.2571, live read owed | world (PPV read) | MED — clears a false alarm or catches a real drift |
| 4 | **Density under R-AESTHETIC-1** — with ms budgets suspended + visual gate, re-open a MODEST density lift where headroom exists (plaza cap 2.157) and judge on stills | Brief 5 | blocked under old budget; reopened by R-AESTHETIC-1 | world (foliage regen) | MED — the daylight-density goal, now visual-gated |
| 5 | **Seed/doc corrections** (audit §2.2) | audit | owed | doc (research/plans only) | LOW effort, HIGH integrity — one commit |

Not executed. Every line is a proposal.
