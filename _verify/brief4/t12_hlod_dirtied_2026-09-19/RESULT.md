# T12 — HLOD cells dirtied by the water carve, RECORDED (not rebuilt)

Per R-O1 / X-2 the HLOD rebuild folds into the SINGLE post-Brief-5 rebuild;
this session records WHAT it dirtied so that rebuild is complete. Safe for
the bench because proxies never render in bench frames (B-1). NOT rebuilt.

## What dirtied the HLOD, two sources

### 1. The heightmap re-import (T5a) — ALL 256 landscape proxies
`push_heightmap --push` re-imported the full 8129² heightmap and
`save_level` re-saved **all 256 landscape proxy packages**. The landscape
HLOD source hash therefore moved for **every** landscape L2 cell — the
whole landscape HLOD layer is source-stale, not just the carve neighbourhood.
(The height DELTA is tiny — see below — but the SAVE churned every proxy, so
the later rebuild must treat all 256 as stale, which it does regardless.)

**The actual height delta is confined to the 10 north-cascade lips** (T3, 47
changed px, max cut 0.20 m):
- heightmap col 2528–2900, row 4804–5864 (8129 grid)
- world X −153,600 … −116,400 cm, Y +74,000 … +180,000 cm
- landscape proxy tiles **col idx 4–5, row idx 9–11** (16×16 proxy grid,
  508 quads/proxy) — ~6 proxy tiles carry the only real geometry change.

### 2. The 288 water StaticMeshActors (T5b) — Instanced HLOD cells over the water
288 new StaticMeshActors (277 surface planes + 11 fall placeholders) are new
HLOD source actors. They dirty the **Instanced** HLOD cells covering the §7
water footprint:
- footprint bbox world X −221,600 … 356,400 cm, Y −149,600 … 210,400 cm
- union 119,396 cells = **191.0 ha** across A/B/D + 9 cascade pools.

## Owed to the post-Brief-5 rebuild
- Landscape HLOD: all 256 L2 cells source-stale (re-saved) — real geometry
  change only in proxy tiles col 4–5 / row 9–11.
- Instanced HLOD: cells intersecting the 191 ha water footprint gain 288 new
  source actors.
NOT rebuilt now (R-O1 / X-2). This record names the regions so the later
rebuild is complete.
