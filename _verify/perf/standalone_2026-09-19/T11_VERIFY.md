# Brief-4 CARVE_PLAN T11 — perf verification vs R-PERFBUDGET (2026-09-19b)

Explicit per-zone hold of this session's standalone 4K run
(`perf_standalone.json`) against the ratified budgets
(`recipes/perf_budgets.json`; R-PERFBUDGET). Water is new GPU cost on a
DEVICE_HUNG-history machine — this is the acceptance for CARVE_PLAN T11.

**Class:** STANDALONE `-game` process, res **3840×2160 read back ×4**
(`res_matches_request: true` all zones), `-noxgecontroller` true. GPUTime
**p90** is the binding metric (a budget is about the frames that hurt);
GameThreadTime and FrameTime p90 are judged too. Budget bar = `budget ×
(1 + 0.10)` tolerance (`gates.tolerance_frac`).

## GPU p90 — the binding thread (ms)

| zone | measured p90 | n frames | budget | red-bar (×1.1) | verdict |
|---|---|---|---|---|---|
| plaza | 9.479 | 2378 | 10.5 | 11.55 | **PASS** (0.90× budget) |
| main_street | 6.630 | 3291 | 7.5 | 8.25 | **PASS** (0.88×) |
| treeline | 7.139 | 3055 | 7.0 | 7.70 | **PASS** (1.02× budget, inside tolerance) |
| vista | 8.164 | 2742 | 8.5 | 9.35 | **PASS** (0.96×) |

`treeline` is the only zone above its raw budget (7.139 vs 7.0); it sits
at 1.02× budget, well under the 7.70 red-bar. Every other zone is under
its raw budget.

## Game thread p90 (budget 6.0 flat, red-bar 6.6 ms)

| zone | measured | verdict |
|---|---|---|
| plaza | 3.958 | PASS |
| main_street | 3.470 | PASS |
| treeline | 3.531 | PASS |
| vista | 3.650 | PASS |

## FrameTime p90 (budget 16.6, red-bar 18.26 ms)

| zone | measured | verdict |
|---|---|---|
| plaza | 11.169 | PASS |
| main_street | 8.103 | PASS |
| treeline | 8.576 | PASS |
| vista | 9.877 | PASS |

**VERDICT: all four zones PASS on GPU, Game and Frame (+10% tolerance).**

## Independent confirmation (non-negotiable 8)

`check_perf.py` (the suite's enforcement instrument) selects the
range-matched standalone artefact `_verify/perf/20260914_standalone4k_pass2.json`
— a DIFFERENT run of the same world/cameras — and returns **PASS, exit 0**:
plaza GPU 9.45, main_street 6.58, treeline 7.13, vista 8.31, all within
budget. Two independent runs agree; treeline reproduces at ~7.13 in both,
so the 1.02×-budget reading is the station's steady-state cost, not run
noise.

## VRAM peak vs abort ceiling — UNMET BY INSTRUMENT (rule-12 gap)

`perf_standalone.py` captures FrameTime / GameThreadTime / RenderThreadTime
/ GPUTime / RHIThreadTime from the CsvProfiler and **nothing else** — no
VRAM residency, no exposure. So:

- **VRAM peak this run: NOT MEASURED.** The "VRAM peak vs abort ceiling"
  acceptance line (CARVE_PLAN T11) is UNMET-by-instrument, not passed. Not
  fabricated (rule 10/13).
- Abort ceiling = **13,312 MiB** (the HLOD-era VRAM budget); physical VRAM
  = 16,303 MiB (RTX 5080 Laptop, `docs/environment.md`).
- Nearest bound: the far heavier HLOD 4096 bake peaked **10.0–11.9 GiB**
  VRAM against the 13.3 GiB abort and never tripped (STATE 09-14 window). A
  single static perf frame is lighter than a bake, so a VRAM breach is
  unlikely — but this is a bound, not a measurement of this run.
- **FOV** is declared 90° in the artefact but NOT applied to the `-game`
  process and NOT read back (`_fov_h_deg_note`) — a second rule-12 prose
  field; treat as engine-default, not a measured parameter.

**UPDATE 2026-09-19b — VRAM acceptance now MET WITH DATA, all four zones.**
`perf_standalone.py` was amended (VRAM via nvidia-smi poll, in-engine GPU-mem
cross-check via `r.GPUCsvStatsEnable`, WP streaming-active residency + the
declared loading range) then re-run for all four zones. This
`perf_standalone.json` is now the VRAM-augmented 4-zone artefact (it replaced
the earlier VRAM-less run of the same date; that is in git history).

VRAM peak per zone (nvidia-smi, steady-state window, vs the 13,312 MiB abort
ceiling; in-engine `GPUMem/LocalUsedMB` agrees within ~170 MiB = other GPU
consumers):

| zone | VRAM peak MiB | GPUMem/LocalUsedMB | streaming_active |
|---|---|---|---|
| plaza | 5092 | 4919.1 | True |
| main_street | 5116 | 4943.6 | True |
| treeline | 4782 | 4608.8 | True |
| vista | 4749 | 4576.4 | True |

**Peak across zones 5116 MiB vs 13,312 abort → +8196 MiB headroom, well
clear** (over_abort_ceiling False). declared_loading_range_cm 51200 (512 m,
the ruled range). GPU p90 reproduced within run noise (plaza 9.418,
main_street 6.599, treeline 7.118, vista 8.104) — all still PASS. The T11
VRAM line is CLOSED by measurement. Only exposure read-back remains
uncaptured (smaller residual, not gating). See also
`_verify/perf/vram_amendment_2026-09-19/` (the plaza-only amendment proof).
