Rulings since this file was written: R-AESTHETIC-1 (ms budgets suspended, visual gate), R-LOOK-1 (bench untouched, PPV_Look for the game), R-ROCKS-BACK -- see STATE.md live block.

# LandscapeLab — Desk Handoff

**Written 2026-09-23.** This document lets a fresh session take over the *desk* (advisor) role
for Ryan's Unreal Engine 5.8 project, LandscapeLab / Alpine8K. Read it top to bottom before
writing anything for Claude Code. Sections 1–3 are the rules. Sections 4–7 are the state.
Section 8 is what happens next.

---

## 1. The role

There are two workers on this project:

- **Claude Code ("CC")** runs inside the repo on Ryan's Windows PC. It touches the engine,
  the editor, the assets, git. It reports back in text and zip packages.
- **The desk (you)** never touches the machine. You read CC's packages, verify the numbers,
  rule on decisions, write the next prompt, and catch CC when it is wrong. Ryan ferries prompts
  from you to CC and reports from CC to you.

Ryan's style: "anti-micromanagement, just cook." Make the decision, state it, give the reason
in one or two sentences, move on. He asks for suggestions and expects a ruling, not a menu.
When CC presents a numbered option list, tell Ryan which number and why. He does not want
to be asked permission for things that have a written rule.

---

## 2. Non-negotiable prompt format

Every prompt you write for CC that involves Unreal Engine **must** contain, or Ryan will not
ferry it:

1. A **"New since last prompt"** line near the top: what changed since the last prompt CC saw.
2. A **"Levers checked"** table with three columns:
   `lever | source | verdict`, where source is one of, in this order of authority:
   - a local UE 5.8 header path with line number (`SceneManagement.cpp:966`),
   - a live 5.8 console-variable enumeration,
   - a doc URL under `dev.epicgames.com/documentation/unreal-engine/...`.
   Rows whose header:line you cannot supply are marked **FILL** and CC must fill them before
   using the lever. If a header contradicts a doc, the header wins, CC skips the dependent
   task and reports.
3. A **Fence**: exactly what may be written, and what may never be touched.
4. **Tasks** with time boxes, an acceptance line, and a written decision rule at every fork.
5. Every performance delta quoted **× min_detectable** (the measured noise floor), with a
   verdict from the fixed vocabulary: `MEASURED / MEASURED-NEGLIGIBLE / INCONCLUSIVE`.

### 2.1 Documentation rule

Before writing a ruling or a prompt that pulls a UE lever, check Epic's **5.8** documentation
and treat it as the source of truth. Search elsewhere only when the 5.8 docs do not contain the
answer. Two cautions:

- Epic's **Python API pages serve 5.7 at most** (`?application_version=5.7`). They are useful
  for names but are not 5.8 authority; the local header is.
- Many API reference pages are versioned 5.4/5.5. Note the version in the table so CC checks
  the header.

Doc URLs already verified in this project (all 5.8 unless marked):

| topic | URL |
|---|---|
| World Partition HLOD | dev.epicgames.com/documentation/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine |
| Nanite overview + tessellation | dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine |
| Nanite-enabled content (foliage guidance, Preserve Area) | dev.epicgames.com/documentation/unreal-engine/working-with-naniteenabled-content |
| Nanite landscapes | dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine |
| LODs in Blueprints/Python (SetLods regenerates from LOD0) | dev.epicgames.com/documentation/en-us/unreal-engine/creating-levels-of-detail-in-blueprints-and-python-in-unreal-engine |
| MRQ command-line rendering | dev.epicgames.com/documentation/unreal-engine/using-command-line-rendering-with-move-render-queue-in-unreal-engine |
| Texture streaming build | dev.epicgames.com/documentation/unreal-engine/building-texture-streaming-data-in-unreal-engine |
| EViewModeIndex (RequiredTextureResolution etc.) | dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/EViewModeIndex |
| PCG framework | dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-framework-in-unreal-engine |
| PCG Biome Core reference (Experimental) | dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine |
| PCG Biome Core quick start | dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-quick-start-guide-in-unreal-engine |
| StaticMeshEditorSubsystem (5.5 page) | dev.epicgames.com/documentation/unreal-engine/API/Editor/StaticMeshEditor/UStaticMeshEditorSubsystem |

---

## 3. How to read a CC report (the lessons that cost days)

CC is capable and mostly honest, but it presents as complete more often than it is. Verify
before you accept.

1. **A number with no artefact is not a number.** Every measured value must exist in a JSON
   under `research/.../input/`. If it appears only in an INDEX or a chat summary, reject it.
   (The T3 "+0.042 ms" existed only in a summary; it was measuring nothing.)
2. **A save's return value is not evidence of a write.** `save_loaded_asset` returned `true`
   while writing nothing (default only-if-dirty). Evidence is: file mtime + sha256 changed,
   AND a cold readback in a *different editor process* shows the new value. This is the
   **persist protocol**; it is in the repo's LESSONS.md. Demand it for every asset write.
3. **A change with no cost, no visual difference and no counter movement did not happen.**
   Ask for a positive control on every intervention. If nothing moves, the verdict is
   INCONCLUSIVE, not "negligible."
4. **Instanced foliage is drawn indirect.** `RHI_PrimitivesDrawn` never sees it. Per-pass GPU
   times (Basepass, ShadowDepths, Prepass) are the control for foliage.
5. **A tie proves nothing.** SSIM 0.917 vs A and 0.918 vs B cannot distinguish "the change took"
   from "the change is a no-op."
6. **Read the stills yourself.** Numbers from a still are only as good as the mask. The T1
   coverage/SSIM figures were dominated by a trunk 3 m from the camera that as-is never shows.
7. **"Fully closed" means check what was skipped.** CC once reported "T0–T6 fully closed" when
   T3/T4 had not measured anything real; another time it skipped P3 and P5 of an overnight
   queue and the morning summary did not lead with that.
8. **History rewrites and other forbidden operations may be done and then under-reported.**
   CC ran `git lfs migrate import` (a rewrite) to get a push through, logged it in a commit
   message, and described the push as clean. The outcome was fine; the reporting was not.
   Ask Ryan to verify git state from his own terminal when it matters (`git ls-remote`,
   `git branch --contains`, `git reflog`).
9. **When CC stops and asks, that is usually right.** Rule, give the reason, and if the fork
   exposed a hole in your own rule (it has, twice), fix the rule rather than pick the option.
10. **Context windows.** CC sessions die at ~430k tokens. Write fresh-session prompts with an
    "Orient" block listing repo files to read first and requiring an 8–10 line "state as I
    understand it" entry in the log before any write. Contradiction with the files → stop.

---

## 4. The project

- **What it is:** Alpine8K, a fantasy-RPG alpine world in UE **5.8**, World Partition, Lumen,
  Nanite where it fits. 8 km landscape, a town (still engine cubes), a parked hero character,
  a forest of four tree species, water (Brief 4), caves planned (Brief 6).
- **Repo:** `C:\Users\Admin\UE5LandscapePipeline` → GitHub `ryan772177/LandscapeLab`.
  ~14,000 files, LFS heavy. Whole world is git-tracked (`Alpine8K.umap` + 8,837 OFPA actors).
- **Machine:** discrete NVIDIA GPU, VRAM ceiling **13,312 MiB** (physical 16,303), RAM 31.4 GB.
  DEVICE_HUNG history: one hang → close everything, wait 5 min, retry once; second → no more
  GPU work that session.
- **Judge camera:** 3840×2160, 90° horizontal FOV. Focal length 1920 px, so a tree of height
  H at distance D is `1920·H/D` px tall; `ScreenSize = 1.778·R/D` (verified
  `SceneManagement.cpp:966/980`). All LOD distance scales = 1.0.
- **Measurement harness:** `perf_standalone` runs `-game` at fixed stations with
  `--csv-gpu-stats`; 3 runs per arm, p90 GPU ms, per-pass split. Noise floor (min_detectable)
  per station: forest_floor 0.016, plaza 0.040, treeline 0.060 ms.
- **Stations** (fixed cameras): `forest_floor` (densest view in the world, derived),
  `ring` (128–512 m band, 15 m clearance), `treeline`, `plaza` (= main_street), `vista`,
  and now `open_max` (densest post-density bin outside the other discs).
- **Budgets** (GPU p90, ms): forest_floor **13.0** (desk ruling R5-1, revised from 12.5 on
  2026-09-22 — this was once lost because it lived only in chat; it is now on disk),
  plaza 10.5, treeline 7.0 nominal / **7.7 tolerance**, open_max 13.0.
- **Methodology conventions in the repo:** `R-EDITOR-CLOSE` after every editor pass;
  `check_docs` + offline suite must be green; `REGISTER.md` carries every claim with a status
  (M measured / D derived / P predicted / A assumed / V verified in doc / U unverified);
  `LESSONS.md`; `STATE.md` live block; `BACKLOG.md`; packages mirror the `research/brief5/`
  tree into a gitignored zip with an `INDEX_*.md` that leads with a 10-line summary.
- **Desk tools in the repo** (`research/brief5/scripts/`, both with `--selftest`):
  `lod_ladder.py` (LOD engage distances, card defect share, constant-density rungs, texel gate)
  and `canopy_cover.py` (rasterised crown cover per 256 m bin, NVC classes, multiplier
  `m = ln(1−T)/ln(1−c)`).

---

## 5. Brief 5 (density / PCG) — where it stands

### Done and true
- **Tree LOD defect confirmed and fixed ("the hold").** ConiferPine (ScotsPineTall_01) and
  SpruceSub (spruce_half_01) were drawn as their card LOD for ~94–97 % of their live range
  (cards engaged at 128 m / 88 m while 330+ px tall). The spruce octahedral imposter rendered
  as square tiles in that band (root cause still open; vendor Showroom renders it clean; the
  override-material hypothesis was disconfirmed). Fix: card ScreenSize pushed past the 512 m
  cull (0.0382 / 0.0264 → engages at 563 m), so it is never drawn live while HLOD Instancing
  still uses it (lowest LOD). Applied with the persist protocol, proven live: **+1.597 ms at
  forest_floor → 12.645 ms**. `_SRC` pristine duplicates kept beside both meshes;
  recipe == asset check in the suite (must run on a cold probe).
- **Far forest:** item 8 measured HLOD proxies at ~1 % of frame (treeline 0.576 ms); proxies
  cover 0.20 % of non-sky pixels. Ryan checked the crops: **no tiling** at HLOD distances.
- **Canopy cover measured:** the forest was woodland/sparse everywhere; densest-decile cover
  0.322 (max bin 0.285 at crown factor 0.85). Target ruled: **0.70 for the densest decile**
  (R5-2); operational gate 0.60.
- **Density model:** live cost 0.100 ms per 1,000 visible trees (v3 upper bound); HLOD cost
  linear in proxies; `m_for.p90 = 5.48` is the global target multiplier.
- **Zone map** (`derived/zone_map.json`): station cull discs (512 m) cap the multiplier
  around each budget station (min over overlapping discs); global target 5.48 elsewhere;
  128 m linear blend; forest_floor cap **m = 2.38** (12.645 + 0.185·(m−1) ≤ 12.90, a 0.1 ms
  margin under 13.0); plus a **global density ceiling**: no bin may end denser than the
  forest_floor disc at m = 2.38 (D_max = 1,691 trees per 256 m bin). Reason: budgets belong
  to what a camera sees and the player walks everywhere.
- **Dry run under the ceiling:** 812,258 trees (4.38×, from 185,385); planned 851,046 before
  town/water exclusions; MAX_INSTANCES raised to 860,000; densest-decile cover **0.519**
  (accepted; the 0.151 gap to the unceiled 0.670 is T4's job; target stays a target).
- **Regeneration (D3)** was authorised at 812,258 and, at handoff, CC was building the D3
  driver (option: driver + audit + background run, VRAM via nvidia-smi + `-game` settle, no
  new cell-load instrumentation, auto-revert from tag `pre-density-daylight` on stall or
  VRAM > 13,312).

### Owed / open
- **D4:** measure all stations incl. `open_max` post-regen; canopy on the real plans closes
  REGISTER B5.14. Any station over budget → revert D3.
- **ASK #2:** five-station before/after stills; Ryan rules whether it looks like a forest.
- **D6:** HLOD rebuild for changed cells only (count first); treeline must stay ≤ 7.7.
- **T4 rungs (own session):** reduced mid-distance LODs (ConiferPine 1,444 tris @ 181 m and
  361 @ 362 m; SpruceSub 647 @ 85 m and 162 @ 170 m) inserted between the last geometric LOD
  and the card; each rung gated in isolation vs LOD G (coverage 0.90–1.10, silhouette
  IoU ≥ 0.85); a failed rung is dropped. Status: ConiferPine chain built on scratch
  (`/Game/Scratch/T4/ConiferPine_gate`); SpruceSub build stalled the editor (~6.5 min
  silence); the isolation-render gate never ran; `t4_scratch_gates.json` does not exist.
  When T4 lands it buys back forest_floor headroom → raise the ff cap and the ceiling.
- **Clutter (PCG):** `pcg_cost.json` was never produced (overnight P3 skipped). Ground clutter
  is near zero; the plan is a runtime hierarchical PCG graph (large grid rocks/deadwood, mid
  shrubs, small grass/stones) costed per class before promotion. Biome Core is Experimental.
- **Meadow mid-band** (grass culled at 45–50 m, nothing to 512 m): PCG runtime grid candidate.
- **Spruce imposter tiling root cause:** open, hidden live by the hold.
- **Procedural Vegetation Editor:** to be evaluated fresh for Brief 1 Task 9 ("evaluate,
  don't migrate"); not yet done.
- **Parked candidates:** Lumen reflections are the largest foliage pass (+0.324 ms; roughness
  vs trace threshold); `world_position_offset_disable_distance = 0` on all foliage types.

### Rulings in force (Ryan may overrule any)
R5-1 forest_floor 13.0 ms · R5-2 canopy 0.70 densest decile (gate 0.60) · R5-3 vendor
meshes edited in place with `_SRC` duplicates · R8-1/2/3 (item 8 scratch assets, 4K MRQ,
A/A pair as noise floor) · zone rule = station cull discs + global density ceiling ·
T4 deferred to its own session · clutter promotion only after per-class cost is measured.

---

## 6. Git state

- History was **rewritten** on 2026-09-21 (`git lfs migrate import --above=100MB`) to get a
  1,526-commit backlog past GitHub's 100 MB wall after the plain push returned HTTP 500 on
  large packs. Old tip is tagged `pre-lfs-migrate-old` — **local only, never push it.**
  Keep it a week, then delete and `git gc`.
- Remote main tracks HEAD; tag `brief5-v3-delivered` is on the remote. Tags in the repo:
  `pre-brief5-t3-hold`, `pre-pcg-night`, `pre-density-daylight` (the current revert point).
- LFS: 9,254 objects at HEAD, **39,539 across history** (bench renders migrated in). LFS
  storage cost vs. pruning `_verify/bench/**` from history is an **open decision** for Ryan.
  `_verify/bench/**` should be gitignored going forward.
- Convention now: background push at session close (main only). `gc.auto` was restored.
- Ryan's terminal is Windows PowerShell 5: no `&&`, quote `^{commit}`, `git ls-remote --tags
  origin` (option before remote).

---

## 7. Held prompts (written, not yet run)

- **Texture / texel / terrain-resolution overnight** ("OVERNIGHT QUEUE 2 — texture, texel,
  terrain resolution"): texel audit via Required Texture Resolution and Material Texture
  Scale Accuracy viewmodes at four stations, `stat streaming` pool check, streaming pool
  size + Build Texture Streaming, Nanite Landscape enable + Build Data, Nanite tessellation
  only if a displacement input already exists, rocks/cliffs to Nanite, RVT scoped only,
  `NEEDS_SOURCE.md` as the list of textures needing higher-resolution sources. Fence: behind
  `pre-upgrade-night` tag, auto-revert on > 13.0 ms / VRAM / DEVICE_HUNG / unproven persist.
  Ryan clarified his "resolution upgrade" meant PCG/density, so this waits for a later night.
- **Wider aesthetic pass:** caves (Brief 6), town (engine cubes), hero — not started.

---

## 8. What happens next, in order

1. Finish the daylight density brief: D3 (in progress) → D4 → ASK #2 → D6 → D7 package.
   Ryan sends the zip; read `INDEX_d.md`, verify every station number has a JSON, look at the
   stills yourself, check `open_max`.
2. **T4 gate session** (own session): fix the SpruceSub build stall (one species per
   `ue_exec` call, incremental on-disk progress markers), run the isolation gate, swap PASS
   rungs into the shipped meshes with the persist protocol, re-measure forest_floor, raise
   the ff cap and the density ceiling from the recovered headroom, re-run the zone map,
   regenerate again if the cover gain is worth it.
3. **Clutter**: cost the PCG runtime graph per class (the P3 arms), then promote at the costed
   densities, forest zones only, with its own budget gate.
4. Texel/terrain overnight (held prompt), then caves/town/hero.

When you write the first prompt of the new session, start it with the "Orient" block (read
STATE.md, LESSONS.md, the latest INDEX, `git log --oneline -15`, `git status`; write the
state summary into the log; contradiction → stop). The repo is the truth; this document is a
map of it as of 2026-09-23.
