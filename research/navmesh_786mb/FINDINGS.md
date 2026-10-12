# Navmesh 786 MB — findings (2026-10-04, read-only; no editor, nothing edited)

Inputs, not law (research/ rule): every number below came from a read-only scan or an opened engine
line; re-check before acting on it.

## Verdict

The RecastNavMesh actor package is a **near-complete duplicate** of the tiles already stored in the 64
NavigationDataChunkActors, because the actor's `bIsWorldPartitioned` was never set. With it true the actor
saves **zero tiles** (`PImplRecastNavMesh.cpp:522-527`, opened and confirmed by the session author:
"Navmesh data are stored in ANavigationDataChunkActor").

## Measured on disk (scripts in this folder)

    actor     __ExternalActors__/Alpine8K/5/P2/BB9IBCIC8QFTD3SMC11T0V.uasset  786,223,894 B
              273,927 tiles, maxTiles 401,843, tile 1596 cm
    chunks    64 packages, 782,577,829 B, 275,679 tiles
    overlap   1,343 / 1,600 random 96-byte chunk samples found verbatim in the actor (83.9%), all 64
              chunks matched; control 0 / 500 from non-nav packages
    history   21.6 MB (4a5ffd12) -> 36.1 MB (232b83fe, 2026-08-26) -> 786.2 MB (6b3de906, 10-02 re-save)

So the actor carried tiles even before 10-02 (36 MB from the calibration world).

## Engine facts (cited by the research agent; the first is re-opened)

- Flag false, normal editor, static nav (streaming): saves tiles in the level's navigable bounds
  (`PImplRecastNavMesh.cpp:534-538`; streaming per `RecastNavMesh.cpp:4385-4390`). In WP = all volumes.
- `maxTiles` always serialized from the in-memory Detour mesh (`:561-565`), restored at `:697`.
- `bIsWorldPartitioned`: `EditAnywhere, config` (`RecastNavMesh.h:833-835`), default false.
- WorldPartitionNavigationDataBuilder saves ONLY chunk actors (`WorldPartitionNavigationDataBuilder.cpp:200-223`,
  `:262`) — no builder run fixes the actor.
- HAZARD: with the flag on, a normal editor clips nav bounds to LOADED WP regions
  (`NavigationSystem.cpp:4201-4258`); a partial load could shrink maxTiles below 19 bits and re-create the
  19,406-class cap. Load none or all before the save; abort on "Recreating dtNavMesh".

## Procedure — REORDERED by the 2026-10-04 audit (actor flag BEFORE the ini)

Why the order: with the flag true in the CDO at editor start, an Editor world clips nav bounds to loaded
regions (`NavigationSystem.cpp:4159-4257`) and the generator may re-create the Detour mesh with a smaller
maxTiles (`RecastNavMeshGenerator.cpp:5520-5554`). And `set_editor_property` in DEFAULT notify mode runs
PostEditChangeProperty -> RebuildAll (`RecastNavMesh.cpp:4270-4273`), discarding the mesh — so NOTIFY NEVER.

1. Tag restore point (risky op). The 786 MB actor stays in LFS at 6b3de906.
2. Zero editors; launch /Game/Alpine8K with the ini NOT yet written (flag default false: no clipping).
   Level check.
3. `ue_exec scripts/navmesh_set_iwp_payload.txt --set LEVEL=/Game/Alpine8K --set APPLY=True` (notify NEVER),
   read back true. Grep the editor log after it: no "Recreating dtNavMesh", no "UpdateNavigationBounds".
4. `save_tagged_actors --class RecastNavMesh --expect 1 --go`.
5. Offline: nav_params.py on the package — KB-sized, NumTiles 0, maxTiles 401,843. Else restore from LFS.
6. Only then `apply_navigation_config --ini --go`; restart; `--world` read-back (no --go; exits 4 on mismatch).
7. R-GAMESTILL: 0 "tile limit reached" lines; load time vs settle; projection test with sample count (rule 13).

## Open

1. Whether the 786 MB actor is the dominant cause of the >100 s load (plausible: it loads with the persistent
   level). Measure load time before/after.
2. Whether editor-side reachability instruments read the actor's embedded copy (would change after the fix).
3. `bHasNoTileData` -> `NeedsRebuild()` true in game (`PImplRecastNavMesh.cpp:703`,
   `NavigationSystem.cpp:5723-5742`); expected harmless for Static, unverified.
4. TileSizeUU 1600 is effectively 1596 (CellSize 19): 102400 / 1596 is not whole, ~1,752 tiles straddle two
   chunks; CellSize 20 would align. Also a lead for the 401,843 vs 395,505 gap (LESSONS 2026-10-01d).
