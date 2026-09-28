# perf_standalone.py VRAM/residency amendment — verification (2026-09-19b)

Closes the T11 rule-12 gap: `perf_standalone.py` previously captured no
VRAM/residency, so its perf numbers could not answer whether the Brief-4
water pushed VRAM toward the DEVICE_HUNG abort ceiling.

## What was added
- **VRAM peak** by polling `nvidia-smi memory.used` through the dwell, peak
  over the steady-state window (a MARGIN_S-wider superset of the timing tail —
  conservative for a ceiling check), vs the **13,312 MiB abort ceiling**.
- **In-engine GPU-mem cross-check** via `r.GPUCsvStatsEnable 1` + a best-effort
  CSV column reader (non-negotiable 8: a second, independent instrument).
- **Residency**: WP streaming-active evidence from the log + the declared
  loading range (no fabricated resident-cell count — not reachable via
  startup-only ExecCmds in `-game`, declared as such).
- Null-with-reason on a missing nvidia-smi / absent CSV columns (rule 13),
  never a fabricated zero.

## Live verification — `--only plaza --noxgecontroller` (this file)
- **VRAM peak 5094 MiB** vs 13,312 abort → **+8218 MiB headroom** (mean 3951.9,
  n_samples 21, peak_window 5094 over n_window 9). Well clear of the ceiling.
- **In-engine cross-check present on this 5.8 build** and AGREES:
  `GPUMem/LocalUsedMB 4921.2` (this process) vs nvidia-smi 5094 (whole-GPU) —
  the ~173 MiB gap is other GPU consumers. `GPUMem/LocalBudgetMB 15235`.
  Also captured: `NaniteStreaming/RootAllocationMB 16.0`,
  `TextureStreaming/{Resident,Streamed}MeshMem`.
- **Residency**: `streaming_active: True` (WP Initialize + GenerateStreaming
  for Alpine8K seen in the log).
- GPU p90 9.494 (matches the ratified plaza ~9.48) — station ok, so the
  amendment did not disturb the timing capture.

## Scope note
This is a SINGLE-zone verification of the amendment; it briefly overwrote the
4-zone T11 artefact in `standalone_2026-09-19/` (same date dir) and that was
restored from HEAD. The ratified T11 4-zone run stays VRAM-less (historical,
accurate); any future full `perf_standalone.py` run now carries VRAM +
residency for all four zones by construction. Auditor: FIX ×4 LOW (labelling),
all applied; measurement logic + rule-12/13 null-handling clean.
