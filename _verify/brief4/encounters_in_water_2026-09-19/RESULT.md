# CARVE_PLAN T8 — encounter re-verification vs the §7 water set (2026-09-19)

The SILENT GAP (RULING §4.3): `encounters/alpine_8k_verified.json` stamps FROZEN
evidence, so the freshness machinery will NEVER flag it — yet the 317 encounters
were placed on the PRE-water surface. This is the named task that measures it.

Tool: `research/brief4/scripts/encounters_in_water.py` (reuses hydro_derive
footprints; positive control = footprint areas reproduce hydro exactly). Tested
all 317 against 12 water bodies (A@180, B@140, D@590.9, + 9 cascade pools).

## FINDING (rule 13 — measured, with counts)

**12 of 317 encounters fall inside a water footprint — ALL in Lake A (id 4893,
180 m), ALL `scavenger`.** None in B, D, or any cascade pool (measured zero, not
an unrun check). Indices: 88, 96, 175, 193, 216, 237, 252, 269, 274, 275, 295, 308.

- **11 are unambiguously drowned** — elevation 45.7 m … 173.8 m, far below the
  180 m surface.
- **#308 is borderline** — elevation 180.7 m, i.e. 0.7 m ABOVE the surface on the
  full-res grid, but its cell floods on the 4x grid (downsample smoothing). It is
  inside A's XY footprint — a shoal a scavenger camp should not sit on either.

Sensible: A is a large open low-elevation basin (prime scavenger ground) now under
water; B is settlement-excluded, D is high/steep. Evidence:
`encounters_in_water.json` (per-row loc, elevation, below-level flag).

## RESOLUTION — specified; folded into the editor-phase re-verification (T6)

The verified set is `plan (alpine_8k_all.json) minus navmesh-refused rows`, and it
is heavily provenance-stamped (`_input_sha256`, `_stamp_waiver`, `_verified_against`
= the frozen navmesh evidence). It must NOT be hand-edited. The clean pipeline fix:

1. **Add a `water` exclusion to `recipes/encounters.json` `exclusions`** (alongside
   `settlement`), naming the water.json footprints — the DURABLE rule so every
   future placement drops candidates inside a water body. Needs placer code to
   consume it (read water.json footprints, drop candidates inside), analogous to
   the settlement footprint drop.
2. **Re-verify at T6**: the navmesh is rebuilt with water non-walkable (T6), then
   re-adopt — the drowned rows are refused by the navmesh (submerged = non-walkable)
   OR excluded by (1). The verified count drops from 317 (a plain plan re-run is
   BLOCKED — R-TOWNEXCL stratified re-sample 48% low; the removal is surgical, not
   a re-sample).
3. **Re-freeze** the verified set with a new evidence stamp + restate the count
   (317 → ~305 after the 12, unless re-filled to target 320 by a full re-placement).

This session DETECTED the gap with numbers (the substantive closure of the named
task); the removal/re-freeze is editor/navmesh-coupled and belongs to T6.
