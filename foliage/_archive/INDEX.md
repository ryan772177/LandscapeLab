# ⛔ ARCHIVED FOLIAGE PLANS — history only, never a source

Moved 2026-09-16 by deputy ruling R5 (E-4, DESK_LOG_2026-09-16.md) —
plans of DEAD WORLDS, selected by their own declared `_recipe`
signature (standing rule 8), never by filename:

| plan | declared `_recipe` | why archived |
|---|---|---|
| coast_bench_{Conifer,ConiferPine,SpruceSapling,SpruceSub}.json | `_verify/20260831_coast_benchmark/coast_bench.json` | evaluation world; recipe lives under `_verify/` evidence |
| highland_lake_{Conifer,ConiferPine,SpruceSapling,SpruceSub}.json | `_verify/20260901_overnight/highland_lake.json` | evaluation world |
| spike_photo2landscape_{Conifer,ConiferPine,SpruceSapling,SpruceSub}.json | `_verify/20260831_spike_photo2landscape/spike_photo2landscape.json` | spike world |
| canyon_SpruceSapling.json | `_verify/20260901_overnight/canyon.json` | evaluation world |
| alpine_Conifer.json | `recipes/alpine.json` | pre-8K world, HISTORY per CLAUDE.md |
| alpine_{Boulder,CliffFace,CliffOutcrop,CliffOutcropB,TalusChannel,TalusField,TalusFieldB,TalusFieldC,TreeStump}.json | `recipes/alpine.json` + `terrain/alpine_heightmap_v2.png` | pre-8K ROCK plans — the rock companions of the archived alpine_Conifer; **ruled 2026-09-16 (R8)** by the SAME R5-4b signature test the deputy deferred them to (declares the pre-8K recipe → dead world). Moved when a Pass-3 edit to `rock_scatter.py` (their `_produced_by`) re-staled them and made the deferral live. |

Waive-forever was REJECTED (it inverts the waiver doctrine) and
regeneration was REJECTED (dead worlds, waste). This archive supersedes
the parked `_frozen` flag (R-PLANSTALE's FROZEN row now points here).
`check_plan_freshness` and `find_walk_heading` list `foliage/`
non-recursively, so nothing consumes these from here. Reversible with
`git mv`. (The nine `alpine_*` rock plans, deferred by R5, are now
ruled and archived above — R8, DESK_LOG_2026-09-16.md.)
