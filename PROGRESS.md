# PROGRESS — overnight autonomy window, 2026-09-14 21:52 →

One line per completed item. Desk consults are logged in
`research/audit/DESK_LOG_2026-09-14.md`.

## A — closeouts

- **A.1 GPU p90 delta, pass 2 − 09-10 — DONE (earlier this session, `9a561d07`/`e8fe3b15`).** plaza −0.317, main_street −0.320, treeline −0.388, vista −0.506 ms; mean −0.383. ⛔ **NOT the cost of 4096** — negative in all four zones, so the sign is wrong for a 16× texel increase; confounded by the 2,267-cell HLOD rebuild and the grade re-solve, both on 09-14. The cost of 4096 is **UNMEASURED**; isolating it needs an A/B at one commit. Parked in OPEN.md.
- **A.2 check_perf ambiguity — DONE (`e8fe3b15`, `53867f96`).** `by_declared_range` returns every match; >1 match REFUSES and names `--label`. Never first-sorted, never newest. Self-test 16/16. Ambiguity resolved non-destructively via `_superseded_by` on the 09-10 artefact (file stays citable; only gate discovery changes).
- **A.3 base_args commandlet test — DONE (`53867f96`). Verdict: KEEP the flag.** A commandlet without `-noxgecontroller` logs `Using 14 local workers`, so the ini reaches the commandlet path — but both it and `batch_31` show 9 shader-compile lines and no dispatch (warm DDC, nothing substantial compiled). The test proves the dispatcher *initialises* local, not that a heavy-compile commandlet will not wedge. Zero-cost mitigation kept on the project's most expensive operation.
- **A.4 R-XGE — DONE (`53867f96`).** Symptom, one-line recognition test (`ls "$TEMP/UnrealXGEWorkingDir" | wc -l`), CPU-delta discriminator, both switches vs their shared gate (`ShaderCompiler.cpp:223-233`), ini fix + read-back, agent inventory, 4 REJECTED entries, and the rule *a launcher flag documented as mandatory applies to every launcher*. **IncrediBuild uninstall ruling: see OPEN.md — not executed, and the engineering case says unnecessary.**

## Brief 5

- **Brief 5 Task 0 — density + cost baseline DONE (`e6bf116e`, 2026-09-19).** Read-only except two -game perf A/B pairs. `research/brief5/input/density_baseline.json` + `BASELINE.md`. 185,385 trees, all culled inside their detail band; foliage GPU cost tiny (treeline 0.116 ms, plaza ground-cover 0.286 ms) — the forest's weight is HLOD + landscape, not live instances. Clutter = Meadow + Blueberry grass only; only Conifer is Nanite; PCG core/PyInterop/ProcVegEditor enabled, Biome available-not-enabled. Audit FIX applied pre-execution (F1 quoted-cvar regex, F2 ShowFlag.Foliage, F3 sidecar collision). Suite green (31). Owed: a read-only editor pass for PCGWorldActor / Nanite-fallback tris / per-mesh imposter ScreenSize / measured HLOD GPU share.
