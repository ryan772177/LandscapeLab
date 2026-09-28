# Forensics — spiky landscape / rocks — findings (read-only, 2026-09-23)

## Verdict (most likely cause)

**Nanite landscape tessellation × 0.4 m displacement — a render/config interaction,
NOT a data corruption and NOT a regression from the density or T3 briefs.**

The per-vertex spikes are micro-geometry the Nanite tessellator adds on top of a
*clean* base landscape, displaced by the material. Every data-corruption and
recent-asset-change hypothesis was eliminated:

- **Source heightmap is clean.** `terrain/alpine_8k.png` (8129², I;16): max
  deviation of any pixel from its 3×3 median = **163 / 65535 (~0.4 m)**, ZERO
  spike pixels at any threshold ≥ 2000. The landscape geometry SOURCE has no
  spikes — so the imported mesh is not spiked, and the Brief-4 T5 push that died
  mid-transport (LESSONS 2026-09-19) did not leave spike vertices.
- **LFS is intact.** `git lfs fsck` = OK; every landscape / mesh / texture object
  is present and hash-valid. The 2026-09-21 LFS migrate did NOT corrupt or dangle
  any object. CLEARED.
- **No committed-asset regression in the recent window.** HEAD == pre-density-
  daylight for `__ExternalActors__` (the D4 revert holds). The density brief's D3
  commit (2372d8d0) touched ONLY 1084 `InstancedFoliageActor` packages (1067
  in-tree + 17 added, now in `_trash/d4_revert_added`) + 4 `foliage/*.json` — Task 1
  class×count: **InstancedFoliageActor 1084, zero landscape/mesh/HLOD** — and D4
  reverted all of it. No `.umap`, material, mesh, or Config in that commit.
- **Neither geometry script executed.** Task 2: `import_heightmap.py` and
  `rock_scatter.py` each changed only cosmetically since both tags
  (validator keys / MAX_INSTANCES constant); neither ran a re-import or re-scatter
  in the density or T3 windows. Landscape proxies last written **2026-09-19
  (Brief-4 T5 carve, commit 30043cfa)**; M_Alpine8K material + rock/cliff meshes
  last written **2026-09-13**; unchanged since.

## The mechanism

- `LandscapeLab/Config/DefaultEngine.ini:263` **`r.Nanite.Tessellation=1`**
  ("the gate landscape displacement rides on"; ":287 — the landscape itself
  became Nanite") and **`r.Nanite.MaxPixelsPerEdge=1`** (":285, was 4"), with
  `M_Alpine8K` displacement **0.4 m** triplanar Rock. Nanite tessellation at 1
  px/edge + a 0.4 m displacement generates dense displaced micro-geometry on the
  near-field surface — the "per-vertex spikes."
- The config cvars are OLD (793f7bc9 / 5f0e5393), so tessellation is not a recent
  edit. What is recent is the **per-landscape Nanite enable carried in the
  landscape proxies, last rewritten 2026-09-19 (T5 re-import)** — the plausible
  moment the smooth carved landscape started rendering as Nanite-tessellated +
  displaced.

## Bisect (Task 3)

- Latest render I could date: **item8, 2026-09-21** (`research/brief5/derived/
  item8/frame_treeline_A1.png`) — already shows spiky near-field ground. So the
  spikes **predate the density brief (9/22)**.
- The 2026-09-10 bench slope (`_verify/bench/2026-09-10/target_b2b/mid_slope.png`)
  is overexposed and ambiguous. **No clean, well-lit slope/rock render exists on
  disk after the 9/19 landscape write**, so the good→bad frame cannot be pinned
  tighter than "clean at/before the 9/13–9/19 asset writes, spiked by 9/21."
- Commits in the bracket touching landscape/material/mesh/Config since 9/10:
  Config bb554b97 (-noxge), 00eff7fe (HLODMaxTextureSize 1024→4096 + landscape
  batched rebuild); material/mesh efbf1cd1 / 0053ae36 / 9ee3d206 (Brief-3 tiling,
  all ≤ 9/13). 00eff7fe (landscape rebuild path) is the one Config commit that
  could have re-touched the landscape near the window.

## Evidence is split → two ranked candidates

1. **(LEADING) Nanite landscape tessellation × 0.4 m displacement.** Heightmap +
   LFS clean; the spikes are displaced micro-geometry, not data. Introduced when
   the landscape became Nanite (proxies rewritten 9/19 T5), config old.
   **Last clean revert point:** none for *data* (the data is clean); the fix is a
   render/config toggle, so revert is not the lever.
   **Proposed fix (one line, NOT executed):** set `r.Nanite.Tessellation=0` (or
   drop `M_Alpine8K` displacement to 0 / disable landscape Nanite) and re-view a
   well-lit slope + rock still to confirm the spikes vanish.

2. **The meadow / ground-cover grass foliage rendering.** The item8 foreground
   spikes could be grass cards, not the landscape surface — the dark crop cannot
   separate them. If so the cause is the landscape-material grass output or the
   grass mesh, unchanged since 9/13.
   **Proposed fix (one line, NOT executed):** at a well-lit forest_floor station,
   toggle `grass.Enable 0` (or `foliage.ForceLOD`) and re-view — if the spikes
   vanish it is grass, not the landscape.

## What would decide it (owed, not done — read-only fence)

One well-lit `-game` (or MRQ) still of a slope + a rock cluster, first as-is, then
with `r.Nanite.Tessellation=0`, then with `grass.Enable 0`. The pair that removes
the spikes names the layer. (A capture is a write path; out of this read-only task.)
