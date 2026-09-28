# CARVE_PLAN T3 — north-cascade pool-lip notches (executed 2026-09-19)

Tool: `scripts/carve_water_notches.py --write` (dry-run default; audited FIX
findings applied + isolation-tested I;16 round-trip on PIL 12.3.0).
Target: `terrain/alpine_8k.png` (8129×8129, I;16, LFS). Restore: tag
`pre-brief4-water-carve` → `git checkout pre-brief4-water-carve -- terrain/alpine_8k.png`.

## The cut (ONLY the 10 north-cascade pool lips; NO town-lip notch — endorheic)

Datum: height_m = png·0.039063096 (z0=0). Map: 2033 (c,r) → 8129 (4c,4r), exact.
Each lip lowered within a radius-2 disc to `outlet_level_m` (= surface_m − notch_m)
where terrain was higher; never raised; clamped ≥0.

    lakeid  lip_2033      lip_8129      surf_m  outlet_m  coorderr  cut_m  cells
    8377    [632,1201]    [2528,4804]   591.88  590.88    0.47      0.00   1
    10980   [632,1221]    [2528,4884]   588.95  587.95    0.15      0.00   0
    11074   [641,1225]    [2564,4900]   586.81  585.81    0.08      0.00   3
    11171   [640,1263]    [2560,5052]   582.27  581.27    0.55      0.00   3
    11471   [643,1313]    [2572,5252]   469.42  468.42    1.29      0.00   4
    11556   [646,1330]    [2584,5320]   466.30  465.30    0.12      0.04   9
    11696   [678,1355]    [2712,5420]   436.26  435.26    0.59      0.00   3
    11796   [702,1391]    [2808,5564]   412.39  411.39    0.08      0.20   9
    11868   [725,1417]    [2900,5668]   374.26  373.26    0.15      0.08   8
    12017   [716,1466]    [2864,5864]   327.04  326.04    0.90      0.00   7

## Read-backs (all PASS)

- changed pixels: **47**; declared notch cells: 130; subset(changed ⊆ notch): **True**
- pixels RAISED: **0**
- INDEPENDENT coord-map check: max|8129 terrain − hydro lip_elev_m| = **1.29 m**
  (tol 12 m) → OK. lip_elev_m is not the field driving the cut, so this validates
  the 2033→8129 map against a different instrument (NN rule 0).
- z-span after: **min 0.000 m, max 1552.485 m** (encodable 0..2560) — unchanged.
- sha256 **cac37b86… → 13789791…** (bytes changed).
- read-back: mode I;16, identical-to-written **True**, changed-vs-orig **47** (want 47).

## FINDING (rule 10/13)

On the full-res 8129 terrain the north-cascade lips already sit at/near their
outlet levels: total center cut **0.32 m** (max 0.20 m at pool 11796); most lips
cut 0.00 m. **The fill-to-level premise holds strongly — the notches are minimal
refinements, not excavation.** The carve moves the terrain hash (T10 freshness
cascade) and must be re-imported into the landscape at the editor phase (T5),
but the geometric change is sub-decimetre.

Re-running `--write` now REFUSES (0 changed pixels — the rule-13 guard); the carve
is one-shot by construction.
