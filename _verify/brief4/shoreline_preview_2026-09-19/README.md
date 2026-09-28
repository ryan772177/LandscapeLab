# Shoreline preview — A / B / D (2026-09-19)

For Ryan's reserved aesthetic (RULING §5.2): the static-water-mesh shoreline is the
terrain contour at the water level. Rendered offline from the 4x heightmap hydro was
derived from (`research/brief4/input/alpine_8k_height_4x_2033.png`, 4 m/px), no editor.
Water = the **connected component** at the level (flood-fill from the lake centroid) =
what hydro's `level_slice(lake_id)` measures.

## Positive control (instrument agrees with hydro)

Connected-component areas reproduce hydro's stated areas EXACTLY:

| lake | level | preview ha | hydro ha |
|---|---|---|---|
| A east basin (id 4893) | 180.0 | 125.5 | 125.5 |
| B town tarn (id 11877) | 140.0 | 13.6 | 13.6 |
| D headwater (id 8377) | 590.9 | 49.6 | 49.6 |

## Lake A — the one adjustable knob (RULING §5.2 band)

| level | connected ha |
|---|---|
| 175 m | 114.7 |
| **180 m (desk pick)** | **125.5** |
| 185 m | 132.2 |

A@180 reads as a natural basin lake: rounded main body, a distinct eastern lobe/bay,
scalloped western shore, ~5.9 km shoreline. Files: `A_east_basin_{175,180,185}m.png`
(the 180 image shows the 185 ring as a faint lighter halo).

## Lake B — fixed 140 m, town-adjacent

`B_town_tarn_140m.png` — a compact elongated alpine tarn in a steep pocket. The TOWN
marker sits just south of this crop; see `overview_ruled.png` for the adjacency
(tarn ~north of the town, a short overlook walk, 0 town cells wet).

## Lake D — adopted 590.9 m

`D_headwater_591m.png` — the headwater basin at the top of the hero cascade (49.6 ha).

## Finding that feeds T2/T3 (recorded in the draft recipe)

A water plane sized to the **hydro bbox over-floods** — D@590.9 is 98.7 ha over its
bbox vs 49.6 ha connected, because the bbox includes the cascade descent below 590.9.
**T2/T3 must size/shape each water surface to the connected component, not the bbox.**
The superseded bbox-threshold previews are in `_trash/20260919_shoreline_bbox_preview/`.

Rendered by `scratchpad/shoreline_preview.py` (throwaway analysis; scipy.ndimage +
PIL). Overview: `overview_ruled.png` (A blue, B cyan, D violet, town red).
