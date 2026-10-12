# Landscape HLOD faceting + black seams — findings (2026-10-05, read-only research)

Inputs, not law: re-open each cited line before relying on it.

## A/B (measured)

`_verify/lookdev/world_carry02/cliff_overlook.png` (HLOD on) vs `_verify/lookdev/seams01/cliff_overlook_hlodoff.REJECTED.png`
(`wp.Runtime.HLOD 0`): the faceted far wall with straight black seams disappears entirely with HLOD off. All
512 landscape HLOD cells were freshly rebuilt 2026-10-04, so not staleness.

## Cause (engine source, cited by the research agent)

- `LandscapeHLODBuilder.cpp:330` `ComputeRequiredLandscapeLOD`; under `LowestDetailLOD` (`:201-203`) the last LOD
  = 6 for 127-quad components (`Landscape.cpp:2005-2009`). LOD6 = 2 quads per component side, 127 m quads; a
  cell (4 components) = 4×4 quads, 32 triangles per 508 m. -> FACETING.
- Nanite landscape -> the builder always adds a skirt one LOD quad deep (`:351-359`), in local Z, scaled by the
  landscape Z scale 500 -> 635 m down, 127 m out (`LandscapeEdit.cpp:4290-4312`), on every cell edge. Where the
  coarse surface misses the real 1 m terrain beside it, the skirts show -> straight dark WEDGES. Cell census:
  L2_X-2_Y-1 EditorBounds Z min 633 m below its RuntimeBounds Z min.
- Not texture bleed: the bake is a clamped top-down ortho of the cell's own rectangle (`MaterialUtilities.cpp:
  283-290, 1002-1028`).
- Built with (all 256 cell reports): HLODMeshSourceLODPolicy LowestDetailLOD, texture SpecificSize 4096,
  MinVisibleDistance 51200, Instancing layer.

## Fix chosen

`HLODMeshSourceLODPolicy = SpecificLOD`, `HLODMeshSourceLOD = 2` on all 257 landscape actors
(`LandscapeProxy.h:969-975`, LandscapeOverridable; hashed at `LandscapeHLODBuilder.cpp:117-121` so only the
256 landscape cells go stale). LOD2: 4.1 m quads, ~30.7k tris/cell, ~7.9 M world, skirt 20.5 m. Payload
`scripts/payloads/set_landscape_hlod_mesh_lod.py`; rebuild with `hlod_build_landscape_cells.py --built-before`.
NOT AutomaticLOD (`:183` scales the radius by Z 500 -> likely LOD0). Parents: A/B before any rebuild (R-HLODCAP).

## Open

- A vertical crack BETWEEN two HLOD cells on the far wall (cliff_overlook x≈780): source says two LOD6 cells meet
  exactly; re-check after the LOD2 rebuild.
- Disk/stream cost of LOD2 cells unmeasured (~100-150 MB guessed); re-measure treeline perf (7.2 / 10.0 ms).
- Optional: HLODTextureSize 4096 -> 2048 to offset (budget ruling R-HLODCAP).
