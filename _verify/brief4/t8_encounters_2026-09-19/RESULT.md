# T8 — drowned encounters removed + placer water-exclusion (2026-09-19)

## Resolution
`resolve_encounters_water.py --write`: **encounters/alpine_8k_verified.json
317 → 305** — removed the 12 drowned encounters (all scavenger, all inside
Lake A's 180 m §7 footprint; indices 88/96/175/193/216/237/252/269/274/275/295/308).
By REMOVAL per RULING §4.3 (density is a MAX; −12 of 317 stays inside every
gate; separation + settlement exclusion unaffected). Re-frozen with a
`_water_removal` provenance block. Idempotent (re-run: "0 drowned rows
present, set already resolved").

New counts by archetype: scavenger 198 (was 210), raider_camp 81, highland_beast 26.

## Forward guard — the placer will not re-drown
- `encounters/alpine_8k_water_exclusion.npz` (DERIVED, `build_water_exclusion_mask.py`):
  UNION of 12 distinct §7 water-body footprints, **119,396 cells = 191.0 ha**
  on the 4 m/px grid (A 78,425 + B 8,528 + D 30,996 + 9 cascade pools). A/B/D
  asserted byte-equal to the saved 2026-09-19 water_derive masks.
- `recipes/encounters.json` gained `exclusions.water` (ONE_DECLARATION_DERIVED
  — references water.json + the derived mask, no re-described geometry).
- `scripts/plan_encounters.py` gained `WaterMask` (numpy-only, world-cm→grid
  mapping token-identical to the T8 detector) + an `in_water` rejection;
  REFUSES if the mask is declared but absent (rule 13). Selftest PASSED.

The 305 figure supersedes 317 in the one-screen spec (encounters row).
Auditor PASS on all three files (3 advisories applied).
