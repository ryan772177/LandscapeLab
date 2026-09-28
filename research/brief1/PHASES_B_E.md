# PHASES B–E — the overnight programme, as ruled

**Operator instruction, 2026-09-09, recorded verbatim in intent so it exists in
the repo.** Until now the only trace of this lineage anywhere was one line in
an archived `CURRENT STATE` block — `DDC fill, Phase E (E1-E4) BLOCKED on
Phase A` — and three sessions searched for the rest without finding it.

**Do not confuse this with the `PHASE2_PLAN.md` Phase B/C/D lineage**, which is
the concept and city pipeline (Phase D there is the church candidate). Same
letters, different programme.

Phase A — the HLOD rebuild — is COMPLETE (`R-HLOD` amended 2026-09-09b,
LESSONS 2026-09-09 through 2026-09-09i).

---

## PHASE B — subsumed by the RT-on survival

Done by the survival: **skip the DDC fill.** Record in `bench_run.json` that
the open was RT-on at project default, with VRAM peak and open time.

## PHASE C — acceptance frames

1. **PIE capture all three bench stations at the player instrument** — 4K, with
   FOV read back, residency read back, exposure read back.
   `featureless_fraction` per station against predicted sky; pass/fail each.
2. **One `near_ground` still at the truth instrument** — all regions loaded,
   `HighResShot` with `r.HighResScreenshotDelay=8` read back.
3. Everything under `_verify/bench/<date>/` with `bench_run.json`; 1920-wide
   copies of the four stills in `_verify/bench/<date>/for_research/`.
4. Close via **R-EDITOR-CLOSE**. Commit.

## PHASE D — housekeeping

5. Zero orphan shells and monitors; zero `UnrealEditor` processes.
6. **`REGISTER.md`**: HLOD built = PROVEN with manifest numbers; RT-on open
   survives = **observation** (non-reproduction, not cause); MeshMerge-cannot-
   proxy and proxy-budget-from-blob-band as rules; station featureless
   results; the metres-not-centimetres catch as a lesson.
7. **`CURRENT STATE`**: proven vs decided-but-unbuilt; paths to the four
   stills.

## PHASE E — ONLY IF PHASE C PASSED

Sequential. Commit each. **Branch before E3.**

- **E1 — Task 6, derived culls.** `perception` block in the schema and in
  `alpine_8k.json` (4K/90 declared, 1440p floor, thresholds 1.5 / 6 / 40, fade
  0.35); species `height_m` from `_measured` at placed scale;
  `place_foliage.py` derives `cull_cm` at the **detail** threshold — HLOD now
  exists — with the derivation written into the sidecar; suite check for
  authored culls; re-place at the same seed; RECIPES + LESSONS.
- **E2 — Task 8, LOD silhouette audit.** Each tree/rock LOD on magenta via
  `r.ForceLOD` at 1024²; `lod_silhouette_check.py` at the switch pixel sizes;
  `_verify/bench/<date>/lod_silhouette.json`; FAILs to `BACKLOG.md`.
- **E3 — Task 4, standalone perf.** `-game -windowed 3840x2160`, trace,
  `ViewActor` each bench camera 25 s, p50/p90 per station to
  `perf_standalone.json`; viewport size read back. **No budget
  re-ratification.**
- **E4 — sunlit dolly path.** 3 s from `near_ground` staying out of canopy
  shadow (check the first and last frame); capture once at the player
  instrument; **do not score**.

---

## STANDING PROHIBITIONS FOR THIS PROGRAMME

    Do not touch budgets.
    Do not re-score the dolly with the current tool.
    Do not attempt filter-repo.

## CONTINGENCY for the Phase B step-5 open — see R-RTFENCE

If an RT-on open crashes with the light proxies, do **not** fall back to RT
off. Keep HWRT and fence it. **⚠ Two of that contingency's three values do not
do what it assumes** — `r.RayTracing.Culling=3` is already the engine default
and `Radius=70000` LOOSENS the fence from the 300 m default. Full analysis and
the corrected shape: `RECIPES.md` → `R-RTFENCE`.

The contingency's trigger never fired: the RT-on open succeeded unfenced
(LESSONS 2026-09-09i).
