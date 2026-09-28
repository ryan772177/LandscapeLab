# T5a — carved 8129 heightmap re-imported + collision flushed (2026-09-19)

## Push
`push_heightmap.py --recipe recipes/alpine_8k.json --push --timeout 120`
(the first run at `--timeout 25` died in the transport window — see LESSONS
2026-09-19 / R1 REJECTED; settled UNKNOWN via the absent LandscapeEdit.cpp:8175
log line, then re-run at 120 s).

- editor identity gate MATCH (rule 7); level gate `/Game/Alpine8K`; landscape
  identified BY SIGNATURE `Landscape_Alpine8K` res=8129 step=254 comps=1024.
- ENCODING CONFIRMED (raw-R decode reproduces the value, median 0.000).
- ORIENTATION identity (median |dz| 0.00 cm).
- render-target check: 2304 texels across 9 blocks (the 3×3 full-res grid —
  the authority that sees the whole map, incl. the 47-px north-cascade carve
  outside the export's trusted x,y≤1008 window).
- verification vs SOURCE: 1280 samples, worst 0.0000 units, 0 outside
  tolerance; relief preserved (pushed 3189 units vs source 3189).
- engine log carries `Took N seconds to import heightmap from render target`
  (LandscapeEdit.cpp:8175) — the mechanism RAN.

**NOTE:** the push is IDEMPOTENT on the trusted-region samples (the world was
built from this heightmap's landform; only 47 carve px differ, all in the
north cascade). The RT check is what proves the carve went in.

## Collision flush (R1 adoption step 4, SAME SESSION)
`scripts/payloads/landscape_collision_flush.py` — `force_layers_full_update()`
on the single `Landscape_Alpine8K` actor (rule 8 class census; rule 11 world
gate). Called ok.

## Collision truth — the gate CANNOT MEASURE on this world, and here is why (rule 10)
`check_collision_truth.py --recipe recipes/alpine_8k.json --n 100` exits 4
("only ~50% of traces found the landscape", floor 60%) across three
seeds/runs — NOT a fail, a COULD-NOT-MEASURE.

Root cause, measured by `scripts/payloads/collision_nohit_probe.py` (40 pts,
seed 12345, gate's exact trace: TRACE_TYPE_QUERY1, trace_complex, +50/−300 m,
line_trace_multi): **20 of 40 first-hits are `WorldPartitionHLOD` proxies**
(e.g. `Alpine8K_HLODLayer_Instanced_L1_X-3_Y-5` at z 54523 vs expected 53746 —
~8 m above), blocking the trace before it reaches the landscape. The HLOD
proxies were built collision-enabled (the 4096 L2 rebuild, 09-14/09-19); a
force-load of all WP regions did NOT change the hit set — the proxy collides
whether or not the real cell is resident. **This is a pre-existing world
condition, not a carve regression, and collision-truth is R1 adoption
discipline, not a CARVE_PLAN T5 acceptance.**

**Where the landscape IS reachable (20 pts), collision matches the carved
heightmap: p50 0.013 m, p90 0.064 m, max 0.074 m — well under the 0.30 m
gate.** So the flush propagated the carve into collision correctly; the gate
is blind, not failing. (The proxies are stale-and-owed-rebuild anyway — T12.)

## State
Heightmap + collision are IN EDITOR MEMORY. Not yet saved. Water planes
spawned (T5b, 288 actors). Capture + save follow (T5c).
