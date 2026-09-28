# INDEX_synthesis — Briefs 1–6 best-proven-state + forensics (2026-09-23)

**10-line summary**

1. **No genuine regression.** The two suspected ones read back as ruled-and-applied: the exposure "14.3" is the correct A-6 comp_ev **−14.2571** (grey card in band) — **[-8,12] is the pre-exposure range, not a comp_ev bound** (a misread); the "spikes" are **ruled Nanite tessellation × 0.40 m displacement** (R-NANITE8129), on a provably-clean heightmap and intact LFS.
2. **No unmerged work worth consolidating.** brief3-task0-range768 & e3-standalone-perf are 0 commits ahead (merged); density-100-experiment is a not-adopted capture on the dead pre-8K world. **Best state of every brief is on main.**
3. **Best proven per brief:** B1 — 2,267-cell HLOD build fills the distance band (mid_slope −19.2 pts). B2 — A-6 R-WB2x2 solve (comp_ev −14.2571, 3438.6 K), the baseline zero. B3 — B3.20 no player-visible tile repeat. B4 — water LIVE + SAVED, R-WATER-CARVE FULLY LANDED. B5 — the T3 card→geometry hold (forest_floor 12.645 ms). B6 — MetaHuman hero prototype (PARKED); caves not started.
4. **The biggest decided-but-unbuilt item:** Brief 3's per-layer tile sizes + 5-layer contract (R-TILE / R-LAYERS5) are ruled offline but the landscape material was never rebuilt in the editor — the surface look is decided but not on screen.
5. **Density is structurally blocked** at forest_floor (~2.7 ms cost, no cheap lever — T4 gate proved it); R-AESTHETIC-1 (ms budgets suspended, visual-gated) may reopen a modest lift where headroom exists (plaza cap 2.157).
6. **Audit:** 405 findings — 381 obsolete, 24 APPLY. The 24 are **mostly stale-ledger** (already applied, text-search missed them — confirmed still applied); no obsolete finding is made live again by the current state.
7. **Genuinely owed from the audit:** (a) city.json:150 `_THRESHOLD_NEEDS_A_RULING` (operator ruling); (b) rule-9 seed/doc corrections (schema band, anim count, MULTI-REGION banner, residency-gate false-negative, "VRAM never measured" line); (c) two ue58-api-protocol casualty-list additions.
8. **Weakest-verified geometry write:** Brief-4 T5's carved-heightmap re-import (2026-09-19) — died mid-transport, verified by only 1280 samples — but forensics since proved the on-disk heightmap is clean, so the geometry is sound.
9. **Forensics verdict (research/forensics/spikes.md):** the spiky look is the Nanite-tessellation×displacement config, not corruption; one-line test (not run): `r.Nanite.Tessellation=0`.
10. **Top-5 consolidation candidates** (visual payoff / hour): (1) rebuild the landscape material with the ruled per-layer tiles; (2) re-judge the Nanite tessellation/displacement look on stills; (3) confirm the live PPV exposure vs −14.2571; (4) a visual-gated modest density lift under R-AESTHETIC-1; (5) the doc/seed corrections.

Contents: `SYNTHESIS.md` (full per-brief ledger + regressions + audit + consolidation), `stills/` (best render per brief + captions), and `../forensics/` (spikes.md + FORENSICS_LOG.md). Read-only inventory; nothing was executed.
