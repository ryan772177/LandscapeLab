# Brief 7 — THE LOOK: index of what changed, what was measured, what was skipped

Written 2026-09-28 at the P4 checkpoint (Ryan: "continue through phase 4, I'm
heading to bed"). Every number below is a pointer to an artefact; nothing here
is the source. Visual gate on every phase = Ryan on stills (R-AESTHETIC-1).

## What changed per phase

| phase | tag | what changed in the world | stills |
|---|---|---|---|
| P0 housekeeping | `look-p0` | Look profile (PPV_Look + sg Epic/TSR) beside the untouched bench; L0 ruling WB 5600, contrast 0.90, shafts ON, rig off, clouds off; sun 35° in the profile; read-backs (`p0_readback.md`) | `stills/p0`, `p0_L0` |
| P1 ground | `look-p1` | weightmap FEATHER σ=1.5 (the 1 m block shatter root: a near-binary mask, not mips, not height-blend, not displacement); per-layer displacement (Snow 0.02 / Rock 0.20 / Scree 0.06 / ForestFloor 0.04 / Grass 0.03 m), R-TILE per-layer tiling, height-blend k=0, GroundClutter + Meadow + Blueberry grass restored on the material | `stills/p1_feather` |
| P2 rocks | (withdrawn) | rocks placed then WITHDRAWN on Ryan's stills ("they add nothing"); world restored to `pre-rocks-place-20260927`. A2 (dark far forest) CLOSED: it is the conifer imposter LOD, not HLOD/VT/FarField; four atmosphere ladders cannot blue-shift; Look profile owns fog 0.0015 / start 150 m / Mie 0.010 / Rayleigh 0.0331 (`a2_imposter/`) | `stills/p2_rocks`, `p2_a2` |
| P3a density | `look-p3` | 797,500 trees (×4.30) at the ruled caps under D_max 1,691; `r.LumenScene.FarField=0` (root cause of the post-placement game-thread freeze) | `stills/p3_density` |
| P3b clutter | `look-p3b` | four grass species (MeadowFar 512 m coarse tier; ForestLitter / ForestShrub / ForestStones on ForestFloor); cull ceiling 512 m + disc guard; landscape proxies RE-SAVED (the game had never spawned landscape grass); `grass.GrassMap.UseRuntimeGeneration=1` | `stills/p3b_clutter` |
| P4 far field / HLOD | (in progress) | FarField: DROPPED by measurement (below). HLOD: `-SetupHLODs` re-run (2,107 HLOD actors, 886 unreferenced destroyed), 24-way manifest, incremental `--no-force` rebuild running (approve ≈ 90 %, ~50 s/cell → ~26 h; see below) | P4 stills owed after the rebuild |

## VRAM peaks (MiB, abort ceiling 13,312)

| phase | editor | -game (max of stations) | source |
|---|---|---|---|
| P2 world run | 5,049 | — | STATE 2026-09-27 P2 |
| P3a world run | 6,159 | 5,057 | `p3/d3_verdict.json` |
| P3b stills session | 7,234 | 5,276 | `p3b/verdict_stills2.json`, `p3b/verdict_perf_final.json` |
| P4 HLOD batch 0 | commandlet 10,455 | — | `_verify/hlod/p4b_20260928/run_only0_noforce.log` |

RAM, not VRAM, is the constraint now: the Alpine8K editor is ~25 GB private at
797k trees on a 31.4 GB host (LESSONS 2026-09-27c #2); assets are built on a
light level (`/Game/Canyon`).

## One perf number per station (-game GPU p90, ms; recorded, not gated)

| station | P3a (no landscape grass, see note) | P3b final | delta |
|---|---|---|---|
| forest_floor | 12.377 | 12.904 | +0.53 |
| open_max | 12.689 | 13.057 | +0.37 |
| plaza | 9.62 | 9.940 | +0.32 |

NOTE (LESSONS 2026-09-27c #4): every -game number before 2026-09-28 was taken
with NO landscape grass — the proxies' grass-type lists had never been saved.
P3b's delta therefore contains Meadow/Blueberry/GroundClutter as well as the
four new species. Instance count at forest_floor: 49,863 → 57,126.

## What was skipped, and why

- **P2 rocks** — withdrawn by Ryan on the stills; everything authored is kept
  (`--place-committed`, landform router, derived saturation) for a later ruling.
- **A2 blue shift at 1 km** — four ladders (fog density/start, extinction+albedo,
  AP view-distance, Mie×Rayleigh) all fail the +15° clause; ruled fallback
  persisted (a2-closed); "stronger blue" is a grade/sun/tint Look ruling (BACKLOG).
- **PCG graph** for P3b — replaced by the grass system on CC's determination
  (builder + validator + read-back exist; PCG-from-Python was a 3-node spike).
  Deviations stated in the recipe (`foliage._p3b_2026_09_27`).
- **P4 Lumen Far Field** — the brief's criterion is "keep if the far slopes gain
  shading, drop if not". Measured twice: the 2026-09-25 vista/slope A/B showed the
  far band UNCHANGED at FarField 1 (`stills/p1_feather/{vista,slope}_farfield_look.png`),
  and on 2026-09-27 FarField 1 was the root cause of the post-placement
  game-thread freeze (LESSONS 2026-09-27 FarField). It is 0 in `DefaultEngine.ini`
  with the reasoning. No third A/B was shot; the two measurements are the ruling.
- **P4 HLOD "changed cells"** — the incremental path works (hash policy approves
  34 of 37 in batch 0) but at ~50 s per approved cell the full set is ~26 h of
  commandlet time. Batch 0 is the measured sample; the remaining batches run
  unattended via `hlod_build_batched.py run --no-force --start N` (resumable,
  crash-bounded) and the P4 station stills (`p3b_clutter_run.py --stills-only
  --station-set p4`) follow the rebuild. Not delivered in this session — stated.
- **Deadwood proper** — asset gap (DragonCave / Atlantis_Ruins not on disk).

## Every FILL that stayed FILL (from the brief's levers table)

- `r.EyeAdaptation.CachedLightingPreExposure` header:line — filled in P0 (`p0_readback.md`).
- DirectionalLight light-shaft property names — filled from the live stub in P0 (`p0_readback.md`).
- `r.LumenScene.FarField` cvar header:line — filled: applied and read back 2026-09-25 (0→1), then set 0 on 2026-09-27 (ini comment carries the line).
- PCG runtime hierarchical grid — NOT filled as PCG (see above); the grass-system equivalent is on the board.
- No other FILL in the table is still open; anything not listed here was filled before its phase or was never a FILL.

## Pointers

STATE live block · RECIPES: R-LOOK-1, R-FOG, R-P3-DENSITY, R-P3-CLUTTER, R-CULLDERIVE (amended 2026-09-28), R-HLOD · LESSONS 2026-09-24 … 2026-09-27c · `research/brief7/{p0_readback,p1_amendments,p1_block_diff,feather_handoff,p2_rocks_handoff}.md`, `a2_imposter/*.md`, `p3/`, `p3b/`, `p4/`.
