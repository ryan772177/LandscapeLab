# B-4 — Cloud_GlobalCoverage 0.1 capture and read-back (Q17 / P1-9 / D-2)

2026-09-15, vista, target class, editor verified `/Game/Alpine8K`.
Parameter set on the child instance `/Game/Bench/MI_AlpineClouds`
(never the engine MI — standing rule 1), read back off the asset each
time (`cloud_coverage_set.py`, rule 12):

    before  Cloud_GlobalCoverage  0.30000001  (recipe value)
    set     ->                    0.10000000   read back, matches
    capture vista at 0.1
    restore ->                    0.30000001   read back, matches

## The measurement — sky region from the depth pass, cloud within it

Volumetric clouds do not write scene depth, so the depth "sky" mask (no
opaque geometry) is IDENTICAL at both coverages (0.5822). The coverage
signal is therefore the LUMINANCE within that fixed sky region — how much
of the sky reads as bright cloud vs darker clear sky.

    coverage   sky fraction   sky median luma   bright fraction (luma>0.3)
    0.3        0.5822         0.1875            0.0953
    0.1        0.5822         0.2116            0.2817

## ⛔ FINDING: the parameter is NON-MONOTONIC / inverted at this station —
## 0.3 is NOT "near-total overcast"

Lowering Cloud_GlobalCoverage from 0.3 to **0.1** *raised* the sky median
luminance (0.1875 → 0.2116) and **tripled** the bright-cloud fraction
(9.5% → 28.2%). That is the OPPOSITE of "coverage = amount of sky
covered by cloud." Two readings follow:

1. **Q17's premise is refuted.** The concern was "0.3 → near-total
   overcast." At 0.3 the vista sky is only ~10% bright cloud with a dim
   median (0.19) — not overcast. If anything, 0.1 shows MORE visible
   cloud than 0.3.
2. **`Cloud_GlobalCoverage` does not map to screen cloud fraction as its
   name implies.** In the engine's simple volumetric cloud material,
   "coverage" drives a density/threshold field whose relationship to
   on-screen brightness is not monotonic — higher values here produced a
   thinner/darker cloud presence at the vista horizon band, not more.
   The exact mechanism is the engine material's, not the recipe's.

## Ruling: recipe UNCHANGED at 0.3 (B-4)

B-4: "recipe value unchanged unless the read-back shows 0.3 is not what
the parameter means — then report, don't change." The read-back shows the
parameter's meaning is not "coverage fraction," so this is REPORTED and
the recipe stays at 0.3. Choosing a cloud LOOK deliberately (thin cirrus
vs overcast) is a desk/Ryan ruling that needs a target reference, not a
value to tune from this one measurement.

Caveat on the instrument: "bright fraction of the sky region" conflates
cloud with any bright sky pixel (horizon glow), and vista frames the sky
near the horizon where cloud is thin. The RELATIVE change (same camera,
only coverage differs) is the reliable part; the absolute cloud fraction
is not calibrated. A cloud LOOK ruling should use an up-tilted station or
a measured reference, not this horizon view.

Artefacts: `target_b4_cloud01/` (0.1), `target_b1_vista/` (0.3 baseline,
from B-1). Payload: `scripts/payloads/cloud_coverage_set.py`. The
MI_AlpineClouds package is re-serialized at the unchanged 0.3 value by the
set/restore round trip.
