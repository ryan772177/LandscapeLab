> # ⛔ SUPERSEDED — describes the pre-8K / pre-kit design. Do not apply.
>
> Quarantined 2026-08-29 by the doc-consolidation unit. **Nothing in this
> file may drive a decision.** It is kept verbatim because this project
> never deletes a record; the content below the banner is byte-identical to
> what it was before the move.
>
> **Why it is dead.** It grades `/Game/Alpine` — the **2017², 4 m/vertex**
> world — against Pass 7's criteria. Its whole provenance block is about
> `alpine_heightmap.png` vs `alpine_heightmap_v2.png`, both maps of that
> terrain. The string `Alpine8K` appears **0 times**.
>
> **Superseded by** the 8K re-terrain of 2026-08-14: `/Game/Alpine8K`,
> 8129², 1 m/vertex, 66,080,641 vertices. Every per-criterion verdict below
> was measured on a surface the project no longer contains.
>
> *Moved from its original path by `git mv`, so `git log --follow` still
> reaches its whole history.*

---

# STEP 7 — THE SWEEP: report, re-established 2026-08-06 on the CORRECTED terrain

The campaign's acceptance condition. Per-criterion verdicts, each with
the instrument that produced it. Renders dated into `_verify/`.

**PROVENANCE — read this before any number below.** Every frame in the
previous revision of this report was captured against the WRONG TERRAIN:
the world carried the pre-stamp map (`alpine_heightmap.png`) while the
sweep stations were derived from `alpine_heightmap_v2.png` — the
2026-08-03 "adoption" never pushed (root cause: commit 20f6e5eb; repair:
959ec140, v2 pushed, flushed, gated, saved). This revision re-runs R17 in
full on the world that now matches the file, tag `v2sweep`, commit
fb9a1bc2, frames `captures/alpine/*20260806T152224Z__fb9a1bc2_v2sweep*`.
§8 is the explicit ledger of what SURVIVES from the old report and what
is SUPERSEDED. The old numbers are quoted there, not deleted.

**HEADLINE: every render criterion with usable evidence now PASSES; the
gate still does not close, on three named evidence gaps** (close-range
cliff stretch, `spine_aretes` CV re-test, the two polished falloff
spots) — see §7. Nothing failed; the remaining gaps are absences of
evidence, not defects found.

---

## 1. THE R17 RUN OF RECORD — 2026-08-06, tag `v2sweep`

Full procedure, in order, on the corrected world:

    step 0  check_collision_truth --n 100   PASS  p50 0.030  p90 0.200
                                            max 0.467 m  (thr p90<=0.30)
                                            100/100 landscape hits
                                            FIRST sweep-context PASS of
                                            this gate (was p90 94-170 m)
    step 1  resource_guard                  1.7-1.9 GB free (warn band)
    step 2  editor foregrounded             main window was INVISIBLE, not
                                            minimized; restored + verified
                                            by GetForegroundWindow read-back
    step 3  open_level                      /Game/Alpine already open
    step 4  sweep_cameras --resite --write-recipe
                                            stations IDENTICAL to recipe
                                            (delta +0.00 m, drift 0.040 m)
    step 5  capture --filename-tag v2sweep  exit 0, 19/19 cameras
    step 6  verify_frames --tag v2sweep     19/19 present and usable,
                                            1920x1080, no flat/crushed/blown

Editor identity verified against `UE_PROJECT_ROOT` before every remote
call (the node's project field, standing rule 7). No scene mutation was
made; no save was needed or performed.

## 2. GROUNDING — TWO INSTRUMENTS, MEASURED, NOTHING MOVED. FLOATING TREES CLOSED.

R-FOLIAGE-GROUND step 1 (reprojection) is REVOKED and was not
performed. Both instruments ran; neither moved an instance.

| Instrument | Source artefact | Result |
|---|---|---|
| `verify_grounding` (all instances) | v2 heightmap file | Conifer max **0.001 m** over 157,554, 0 outside; Boulder max 0.103 m, the 1 known outlier |
| `trace_grounding --n 500` (engine) | live landscape collision | 500/500 hits; gap p50 +0.006 / p90 +0.068 / p99 +0.202 / **max +0.392 m** |
| cross-check at the same 500 points | collision vs heightmap | \|d\| p50 0.018 / p90 0.091 / max 0.431 m, signed mean **−0.007** |

The reconciliation: the engine-trace residual equals the collision
heightfield's own quantization against the heightmap (Gate B measured
the same class: p90 0.209 / max 0.716 m), symmetric about zero. The
plan matches the RENDER surface (proven = v2 file at 161 texels delta
0.0) to millimetres; the trace disagrees only by what collision itself
disagrees with the heightmap. **The instances are grounded.**

Pixel confirmation: no sky-hung conifer in any of 19 frames; trunk
bases meet ground with contact shadows (`trunk_base`, `rock_grounding`,
`sweep_0350/1200/2000`). The old report's §2 "TREES FLOATING IN THE
SKY" defect is **CLOSED — it was the terrain divergence itself**:
instances planned on v2 hung over a v1 world (divergence >10 m across
37.94% of the map, max 770 m). The landscape-LOD hypothesis chased for
it was investigating a world that should never have been rendering.

Evidence: `_verify/20260806_v2sweep_trace500.json`, frames below.

## 3. THE STATIONS — NUMBERS UNCHANGED, VALIDITY NEW, ONE NEW FINDING

`sweep_cameras --resite` re-run against the (now live-matching)
heightmap reproduces the previous station set EXACTLY — every eye
height delta +0.00 m, clearances +7.5/+10.2/+12.0/+15.6/+12.5/+8.3 m,
summit drift guard 0.040 m. Expected in hindsight: the derivation reads
the FILE, which never changed; the WORLD changed to match it. The
station numbers were never wrong about the file — they were unverified
about the world. Collision truth (step 0) is what promotes them to
world-valid.

**NEW FINDING — the near stations sit in TERRAIN SHADOW on the real
world.** `sweep_0060`/`sweep_0150` return luma std 0.047/0.048
(full-frame shadowed rock at 12–40 m) against 0.24–0.32 at the far
stations. The "lit sector" constraint is a BEARING SECTOR (sun 105
± 85°): it guarantees the camera faces the sun-facing side and never
ray-marches the sun path, so a near bank cast into shadow by higher
ground passes it. The `resite` frames that validated the design were
lit only because they were captured on the v1 world. Two-altitude
logged (LESSONS 2026-08-06; R17 REJECTED). Near-range criteria below
take their evidence from the LIT ground stations (`trunk_base`,
`forest_floor`, `rock_grounding`, `verify_ground`, `player_eye`).

## 4. PER-CRITERION VERDICTS — adjudicated by LOOKING AT THE FRAMES

Statistics support; the pixels decide. Key frames:
`_verify/20260806_v2sweep_*.png` (12 frames + trace dump).

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Tiling pop | **PASS at every lit range** | near: `trunk_base`/`forest_floor`/`rock_grounding` (no lattice in ground detail); mid: `sweep_0350/0700`; far: `sweep_1200/2000`, `verify_aerial`, `ridge_wide`. One small cross-hatch detail patch bottom-left of `forest_floor`, noted, not a repeating lattice |
| 2 | Blend seams | **PASS** | snow/rock/grass transitions in `sweep_0350`, `sweep_2000`, `verify_aerial` blend without hard boundaries |
| 3 | Cliff stretching | **NO DEFECT FOUND — evidence partial** | the LIT wall in `sweep_0700` (~500–1000 m) shows striated rock without taffy-pull smears; `sweep_1200`'s upper-left wall shows vertical banding consistent with striation; the DEDICATED `cliff_face` station is in terrain shadow (luma mean 0.157) and cannot judge — close-range stretch remains unproven |
| 4 | Sampler audit | **PASS — 43/43, gap CLOSED** | `M_AutoLandscape` 31/31; foliage now auditable through the narrowed hook: `M_fir_bark` 3/3, `M_fir_twig` 4/4, `M_grass_medium_01` 5/5 (independently reproduced by the parallel session, cf8dd941) |
| 5 | Scree `saturation` | **LOCKED 0.03 — carried** | ruling stands: the knob cannot make the apron a cone; the levers are the shared physical params (runout_m / mfd_exponent / repose_deg) |
| 6 | `spine_aretes` CV 0.089 | **NOT RE-TESTED** | no render-side instrument exists yet; the polished cone is plainly visible in `player_eye` (smooth against rugged neighbours) |
| 7 | Two polished falloff spots | **NOT RE-TESTED** | same; `player_eye` carries the visual for one of them |
| 8 | Meadow readability | **EVIDENCE DELIVERED — and RULED** | no meadow readable at any range in any frame, consistent with 0.41% world coverage; Ryan REJECTED 1.87%/0.41% (LESSONS 2026-08-06) and ordered an expansion PROPOSAL (BACKLOG, cf8dd941) scored against the post-expansion state; sweep evidence stands regardless |
| 9 | Ground→2 km continuity | **PASS with the §3 caveat** | the ramp delivers: 12 m wall → 40 m slope → 256 m vista → 1140 m wall+valley → shadowed foothills → 2 km lit vista; far stations are real views (`sweep_2000`: grass foreground, forest, snow peak) |
| 10 | Ground exposure | **CORRECT — re-proven on the right world** | `diag_topdown` linear mean **0.3169** vs solved 0.3201, within 1.0%; −1.786 EV stays locked |
| 11 | Floating trees | **CLOSED** | §2: two instruments + cross-check + pixels |
| 12 | Collision truth | **PASS — p50 0.030 / p90 0.200 / max 0.467 m** | `check_collision_truth --n 100`, fresh seed, run of record |

Additional observations, not criteria: `ridge_wide` shows the map's
western boundary as a visible terrain edge at 8.7 km (expected; the
world ends) and heavy untuned aerial haze — fog tuning remains a named
not-done. `sweep_0700`'s foreground valley and `sweep_1200`'s foothills
are in terrain shadow, correct for a 12° sun (45.7% of conifers are in
terrain shadow, `sun_exposure.py`).

## 5. EXPOSURE — the retraction SURVIVES and is now proven on the right world

The old report's §3 retraction (the "0.9 stop over" claim was a
misleading-denominator error, measured on sun-facing slopes) survives
unchanged — it was a lesson about measurement, not about terrain. What
the terrain fix could have invalidated is the on-target verification,
and it did not: `diag_topdown` on the v2 world measures linear mean
0.3169 vs the solved 0.3201 (within 1.0%; the v1-world measurement was
0.3228). `read_exposure`'s live-volume read (one unbound volume,
AEM_MANUAL, bias −1.786 OVERRIDDEN, 1/60 s ISO 100 f/4) is
world-independent and stands.

## 6. WHAT THE GATE STILL NEEDS

1. Close-range cliff-stretch evidence: a LIT cliff face station
   (re-site `cliff_face` or add a shadow test to station siting).
2. `spine_aretes` CV and the two polished falloff spots, re-tested
   under full materials — needs an instrument, not just a look.
3. The near-station shadow fix (R17 REJECTED entry): shadow-march the
   sun ray in `sweep_cameras`, or accept lit-ground-station evidence
   for near range permanently and say so in the recipe.
4. Meadow: non-blocking for this gate by ruling; scored against the
   post-expansion state.

**The clip comes after this gate passes. It has not passed — but for
the first time, nothing measured on it is failing.**

---

## 7. SURVIVES / SUPERSEDED — the ledger

### SURVIVES from the 2026-08-05/06 report (terrain-independent)

- **§0 capture-path root cause**: run A wrote 2 frames then the editor
  was closed by the user; run B fataled at `EditorServer.cpp:1951` via
  `LevelEditorSubsystem.LoadLevel`. Log-based; stands.
- **`verify_frames` as a mandatory instrument**, proven to FIRE against
  synthetic flat/black frames before being trusted.
- **§3 exposure retraction** and its misleading-denominator lesson;
  re-proven here (§5). The REJECTED entries it produced stand.
- **§5 instrument fixes**: the `open_level` reachability scrub
  (13/13, no editor), the `.p`+`y` payload root cause
  (`PythonScriptPlugin.cpp:813-830`), the byte-ceiling correction.
- **Station-design lessons**: aim = surface not landmark; horizon
  sampled across frame width; bottom edge ≤ −15°; subject choice by
  visibility not prominence ("PROMINENCE IS NOT VISIBILITY"); the
  measured constraint that no peak clears all six distances generously
  (best min-clearance 3.6 m over 34 candidates). All are properties of
  the v2 FILE, which is now the world.
- **Noise-floor control**: identical-capture run-to-run variation
  0.012–0.035 mean |diff| (19–33% of px >2%), stranded-pixel metric
  ±26%. A property of the renderer, not the terrain.
- **`ForcedLOD`/`r.LandscapeLODBias` observations**: the cvar silently
  fails to set; ForcedLOD sets and verifies on 1024 components without
  moving pixels; `enable_nanite` False on all 257 landscape actors.
  Real editor behaviours, still unexplained, no longer load-bearing —
  their motivating defect is closed.
- **The governance defect** (hook blocking its own remedies) — since
  FIXED and proven: 167/167 (fb9a1bc2).

### SUPERSEDED — measured on the wrong terrain; old numbers preserved

- **All 19 frames of the `resite`/`step7` runs and every verdict drawn
  from them** (tiling "PASS near+mid only", seams "PASS near+mid only",
  cliff "NOT PROVEN", the luma-std band 0.22–0.32 as design
  validation). Replaced by §4.
- **§2 "NEW DEFECT — TREES FLOATING IN THE SKY"** — closed as the
  terrain divergence itself (§2 above). The whole landscape-LOD
  investigation it spawned was premised on a world that should not
  have been rendering.
- **§0b run-of-record collision figures** — `step7`'s step 0 FAIL (p50
  0.840 / p90 170.226 / max 291.491 m) and the earlier seeded p90
  94.410: true measurements of the now-repaired defect. Replaced by
  PASS p50 0.030 / p90 0.200 / max 0.467 m.
- **Station world-claims from the old table**: "sees to" distances
  (16/128/80/520/1456/40 m), terrain fill (100/100/100/100/100/98.8%
  and 100/100/86/96/95/94%), median ranges (12/40/256/1140/224/452 m)
  — derived from the v2 file while the world was v1. The FILE-side
  numbers reproduce exactly (§3); their world-side validity begins
  2026-08-06. The near-station LIGHTING those runs exhibited does NOT
  reproduce (§3 new finding).
- **`diag_topdown` 0.3228** as exposure verification — measured on v1
  ground; replaced by 0.3169 on v2 (same conclusion).
- **"trees grounded" render judgements from 2026-08-03/04** — made
  over terrain where 62% of texels agreed between v1 and v2; the claim
  is now made by two instruments plus a cross-check on the real world.

### The one number that moved and matters

The meadow statistics (98.06%/1.94%/0.93%) are FILE-side and stand;
what changed is their status — Ryan REJECTED the current meadow share
and ordered an expansion proposal, sequenced AFTER this sweep, scored
against the post-expansion state.
