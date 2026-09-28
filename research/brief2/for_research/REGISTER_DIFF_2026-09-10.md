# REGISTER diff — Brief 2 close-out + Brief 2b (2026-09-10)

Diffs against `REGISTER_ADDENDUM.md` (Brief 2), by row.

## MEASURED rows
- **B2.1** shadow tint 3.00 → journey complete: 1.4456 (sun 7800/WB 6500,
  the only PASS row — WB sat 1300 K BELOW the sun) → 0.9829 (WB 8800,
  REJECTED) → 1.2580 (7800/7800, truth class) → **1.1243 (5200/5200,
  target class, Brief 2b, one attempt)**. Finding: under the ruled
  neutral WB (= sun), 1.3–1.7 may be unreachable from temperature; the
  remaining lever is the sky-light side. Full table: `TINTS_brief2b.json`.
- **B2.3** the "band does not converge on the sky" — RETIRED AS AN
  INSTRUMENT ARTEFACT at mid_slope: the colour sky mask was never valid
  there (Task 2 era: 0.255 colour vs 0.744 depth). Under the depth mask
  the vista dE FELL task-over-task (0.224 → 0.194): the fog WAS
  converging on the sky. `sky_rejudge_depth.json`.

## PROPOSED rows
- **B2.10** "WB = sun + 1000 K" — REJECTED BY RULING (contradicted its
  own citation; rendered the sun warm). Replaced: WB = the sun, never
  above (R-GRADE). Measured at 5200/5200 above.
- **B2.11** clouds — DONE as proposed (2.0 km / 1.5 km, engine material,
  coverage 0.3 on a /Game child MI). Both acceptance clauses PASS;
  R-CLOUDS locked.
- **B2.12** name collision RESOLVED BY RULING (2026-09-10): Lumen
  far-field is **Brief 2c**. "Brief 2b" = the sun-temperature
  correction, executed today. Brief 2c (FOR_CLAUDE_CODE Task 7) remains
  NOT RUN and ruling-gated; relabelled in REGISTER_ADDENDUM and BACKLOG.

## OPEN QUESTIONS
- **Q13** CLOSED (Task 0: not void; band owned by content/instrument, and
  mostly by the colour mask per the depth re-judge).
- **Q14** CLOSED (base 2, verified in shader source; R-FOG).
- **NEW**: the sky-light lever for shadow_tint_B under neutral WB — the
  one tint question Brief 2's levers did not close.

## Perf (same date, separate ruling)
Budgets re-ratified from the E3 STANDALONE 4K p90 (GPU 10.5/7.5/7.0/8.5,
game 6.0 flat, frame 16.6); editor-derived budgets REJECTED; the standing
plaza-Game RED closed as the editor's 60 Hz clamp. check_perf refuses
editor-class artefacts. The register's "game thread is the binding
thread" reading was the same clamp: in standalone the GPU binds
everywhere.
