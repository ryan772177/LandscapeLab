# Unit 2 — step height and walkability

```
=== UNIT 2 — STEP HEIGHT AND WALKABILITY ===
  heightmap        terrain/alpine_8k.png
  resolution       8129 x 8129, uint16
  cell spacing     100.00 cm
  z span           2560.0 m over the full 16-bit range
  terrain relief   0.0 m .. 1552.5 m
  profile          'mount', max slope 35.000 deg
  MaxStepHeight    45.0 cm  (CharacterMovementComponent.cpp:689)

--- the number unit 2 asked for ---
  cells in the mount mask        40062984 (60.66% of the interior)
  of those, 1-cell rise > 45 cm  7959079  = 19.8664%

--- and why that number is NOT a walkability finding ---
  45 cm over a 100 cm cell is 24.23 deg.
  The mount profile admits up to 35.00 deg, which is 70.0 cm of rise per cell.
  So EVERY slope between 24.23 and 35.00 deg trips this metric while
  being entirely walkable. A character walks UP a walkable slope; it
  does not step onto it. And at 100 cm per vertex a sub-metre step
  is below the map's Nyquist limit and cannot be represented at all.
  READ THIS AS A RESTATEMENT OF THE SLOPE DISTRIBUTION, NOT A DEFECT.

--- what actually binds: slope and connectivity ---
  profile  crossable      largest    regions      reachable
  walk        75.94%       72.03%      77479         94.84%
  mount       60.67%       17.75%     219828         29.26%
  climb       99.54%       99.51%       1523         99.97%
  air        100.00%      100.00%          1        100.00%

  recipe bars for 'mount': min_crossable 0.6, min_connected 0.8
    crossable 0.6067  vs bar 0.6000  -> PASS
    reachable 0.2926  vs bar 0.8000  -> FAIL

--- CONTROL: is the connectivity number about the WORLD or about
--- the RESOLUTION it was measured at? ---
  A 35 deg mask taken PER 1 m CELL is punched full of holes by
  individual steep cells that no rider would ever have to cross.
  Connected-component labelling counts each hole as a boundary, so
  fragmentation can be an artefact of sampling rather than a fact
  about the terrain. The recipe's 0.8 bar predates this map: the
  alpine world it was written for is 4 m per vertex.
  So the same computation is repeated on box-reduced copies. If
  reachability climbs steeply with cell size, the 1 m number is
  about the instrument; if it stays low, the world really is
  fragmented for mounts.

  cell        crossable    largest      regions    reachable
  1 m            60.67%     17.75%       219828       29.26%
  2 m            64.17%     21.36%        64546       33.28%
  4 m            68.57%     51.16%        14225       74.61%
  8 m            72.83%     68.75%         2340       94.39%

--- the corridor half of unit 2: NOT MEASURED, and why ---
  unit 2's acceptance wants this figure 'restricted to the
  inter-massif corridor'. THE CORRIDOR HAS NO SPATIAL DEFINITION
  ANYWHERE IN THIS REPO. WORLD_VISION.md:304 defines it in prose as
  'the primary traversal route' and gives no coordinates, no mask
  and no endpoints; nothing in recipes/ declares one.
  Inventing a rectangle here and calling it the corridor would make
  every number computed against it unfalsifiable. Reported as
  I COULD NOT LOOK, which is not the same as a pass.
  Closing it needs one ruling from Ryan (two endpoints, or a mask),
  and it is the same open item as WORLD_VISION.md:322.

  The nearest thing this repo CAN compute is the largest connected
  mount-traversable component, above: 17.75% of the map and 29.26% of
  all mount-crossable ground. That is a PROXY for reachability, not
  the corridor.
```
