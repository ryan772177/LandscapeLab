"""audit_step_height.py — can the player actually walk this terrain?

PHASE2_PLAN.md unit 2. Offline: no editor, no world, no ASSET/world writes
(an optional `--out` markdown artefact aside). Reads the adopted heightmap and
the recipe, and prints numbers.

=====================================================================
THE PLAN ASKED FOR A METRIC THAT DOES NOT MEASURE WHAT IT SOUNDS LIKE
=====================================================================
Unit 2 as written is: "fraction of the mount-profile mask whose 1 m
neighbour rise exceeds MaxStepHeight = 45 cm". That number is computed here
and reported, because it was asked for. But on its own it is MISLEADING, and
the arithmetic says why in one line:

    a 45 cm rise over a 1 m cell is atan(0.45 / 1.00) = 24.23 degrees

The mount profile admits everything up to 35 degrees. So every slope between
24.23 and 35 degrees exceeds "45 cm of rise per metre" WHILE BEING PERFECTLY
WALKABLE -- because a character walks UP a walkable slope, it does not step
onto it. MaxStepHeight governs impacts with surfaces steeper than the
walkable floor, not the gradient of a ramp.

Worse, at 1 m per vertex the heightmap CANNOT REPRESENT A STEP AT ALL. A
step is a rise over a sub-metre horizontal distance, and sub-metre horizontal
detail is below this map's Nyquist limit by construction. Every transition
this heightmap can express is a ramp of some angle.

So the reading is inverted from what the metric suggests: a large number here
is not a walkability problem, it is a restatement of the slope distribution.

WHAT ACTUALLY BINDS is the walkable SLOPE, and connectivity of the walkable
region -- which is why traversability() is run alongside. A world can be 70%
crossable and still be a thousand isolated shelves.

=====================================================================
ONE DECLARATION, REUSED
=====================================================================
Nothing here re-implements slope, spacing or the movement profiles.
terrain_erosion owns all three (non-negotiable 19 and 24):

    slope_degrees()      the datum the weightmap bake uses
    spacing_for()        guards the resolution-vs-recipe spacing trap
    MOVEMENT_PROFILES    mount 35, walk 44.765083 (the engine's own value)
    traversability()     8-connected components per profile

MaxStepHeight = 45.0f is read from CharacterMovementComponent.cpp:689 and
declared once below with that citation attached.

Exit codes:
  0  audited
  1  could not look (heightmap or recipe unreadable)
  2  bad arguments, OR refused input (heightmap not uint16, or its resolution
     disagrees with the recipe)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import terrain_erosion as te  # noqa: E402

# UE 5.8 UCharacterMovementComponent CDO, CharacterMovementComponent.cpp:689.
# Opened against this install on 2026-08-15, not remembered.
UE_MAX_STEP_HEIGHT_CM = 45.0

# CharacterMovementComponent.cpp:682 SetWalkableFloorZ(0.71f) -> 44.765083 deg.
# terrain_erosion.UE_WALKABLE_FLOOR_DEG carries it; asserted below rather than
# re-typed, so the two cannot drift.


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--out", default="",
                    help="write a markdown artefact to this path")
    args = ap.parse_args(argv)

    # The engine value and the project's shared declaration must agree. If they
    # ever do not, that is two lists that must agree, badly stored.
    assert abs(te.UE_WALKABLE_FLOOR_DEG - 44.765083) < 1e-6, (
        "terrain_erosion.UE_WALKABLE_FLOOR_DEG has drifted from the engine's "
        "SetWalkableFloorZ(0.71f) at CharacterMovementComponent.cpp:682")

    rpath = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    try:
        with open(rpath, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception as e:
        print("COULD NOT READ THE RECIPE: %s: %s" % (type(e).__name__, e))
        return 1

    hm = rec["heightmap"]
    ls = rec["landscape"]
    src = os.path.join(bootstrap.REPO_ROOT, hm["source"].replace("/", os.sep))
    if not os.path.exists(src):
        print("COULD NOT LOOK: heightmap absent at %s" % src)
        return 1

    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(src)
        h = np.asarray(im)
    except Exception as e:
        print("COULD NOT READ THE HEIGHTMAP: %s: %s" % (type(e).__name__, e))
        return 1

    if h.dtype != np.uint16:
        print("REFUSE: %s is %s, not uint16. A step-height audit on an 8-bit "
              "map would quantise every rise to %0.1f cm and read as a "
              "staircase." % (src, h.dtype,
                              float(ls["z_scale_cm"]) / 255.0))
        return 2

    res = int(hm["resolution"])
    if h.shape[0] != res or h.shape[1] != res:
        print("REFUSE: recipe says resolution %d, file is %dx%d."
              % (res, h.shape[1], h.shape[0]))
        return 2

    spacing_cm = te.spacing_for(h.shape[0], res, float(ls["scale_xy_cm"]))
    z_scale_cm = float(ls["z_scale_cm"])
    z_cm = h.astype(np.float64) / 65535.0 * z_scale_cm

    slope = te.slope_degrees(h, spacing_cm, z_scale_cm)
    prof = rec.get("world", {}).get("primary_movement_mode", "mount")
    prof_deg = float(te.MOVEMENT_PROFILES[prof]["max_slope_deg"])

    # The largest 4-neighbour rise at each cell, in cm. Rise, not |difference|:
    # stepping DOWN is not gated by MaxStepHeight.
    up = np.zeros_like(z_cm)
    for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
        nb = np.roll(z_cm, shift, axis=axis)
        np.maximum(up, nb - z_cm, out=up)
    # np.roll wraps; the one-cell border is therefore comparing opposite edges
    # of the map. Excluded rather than left to contribute a false cliff.
    interior = np.zeros(z_cm.shape, dtype=bool)
    interior[1:-1, 1:-1] = True

    mount_mask = (slope <= prof_deg) & interior
    walk_mask = (slope <= te.UE_WALKABLE_FLOOR_DEG) & interior

    n_mount = int(mount_mask.sum())
    over = int((up[mount_mask] > UE_MAX_STEP_HEIGHT_CM).sum()) if n_mount else 0
    frac_over = (over / n_mount) if n_mount else float("nan")

    # The angle at which "45 cm per cell" starts firing, which is the whole
    # reason the metric above does not mean what it sounds like.
    trip_deg = np.degrees(np.arctan(UE_MAX_STEP_HEIGHT_CM / spacing_cm))
    max_rise_at_profile = np.tan(np.radians(prof_deg)) * spacing_cm

    trav = te.traversability(slope)

    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out("=== UNIT 2 — STEP HEIGHT AND WALKABILITY ===")
    out("  heightmap        %s" % hm["source"])
    out("  resolution       %d x %d, uint16" % (h.shape[1], h.shape[0]))
    out("  cell spacing     %.2f cm" % spacing_cm)
    out("  z span           %.1f m over the full 16-bit range" % (z_scale_cm / 100.0))
    out("  terrain relief   %.1f m .. %.1f m" % (z_cm.min() / 100.0, z_cm.max() / 100.0))
    out("  profile          %r, max slope %.3f deg" % (prof, prof_deg))
    out("  MaxStepHeight    %.1f cm  (CharacterMovementComponent.cpp:689)" % UE_MAX_STEP_HEIGHT_CM)
    out("")
    out("--- the number unit 2 asked for ---")
    out("  cells in the %s mask        %d (%.2f%% of the interior)"
        % (prof, n_mount, 100.0 * n_mount / float(interior.sum())))
    out("  of those, 1-cell rise > %.0f cm  %d  = %.4f%%"
        % (UE_MAX_STEP_HEIGHT_CM, over, 100.0 * frac_over))
    out("")
    out("--- and why that number is NOT a walkability finding ---")
    out("  %.0f cm over a %.0f cm cell is %.2f deg." % (UE_MAX_STEP_HEIGHT_CM, spacing_cm, trip_deg))
    out("  The %s profile admits up to %.2f deg, which is %.1f cm of rise per cell."
        % (prof, prof_deg, max_rise_at_profile))
    out("  So EVERY slope between %.2f and %.2f deg trips this metric while" % (trip_deg, prof_deg))
    out("  being entirely walkable. A character walks UP a walkable slope; it")
    out("  does not step onto it. And at %.0f cm per vertex a sub-metre step" % spacing_cm)
    out("  is below the map's Nyquist limit and cannot be represented at all.")
    out("  READ THIS AS A RESTATEMENT OF THE SLOPE DISTRIBUTION, NOT A DEFECT.")
    out("")
    out("--- what actually binds: slope and connectivity ---")
    out("  %-8s %8s %12s %10s %14s" % ("profile", "crossable", "largest", "regions", "reachable"))
    for name in ("walk", "mount", "climb", "air"):
        if name not in trav:
            continue
        t = trav[name]
        out("  %-8s %8.2f%% %11.2f%% %10d %13.2f%%"
            % (name, 100.0 * t["frac"], 100.0 * t["largest_frac"],
               t["regions"], 100.0 * t["reachable_frac"]))
    out("")
    w = rec.get("world", {})
    mc, mconn = w.get("min_crossable_frac"), w.get("min_connected_frac")
    t = trav[prof]
    out("  recipe bars for %r: min_crossable %s, min_connected %s" % (prof, mc, mconn))
    if mc is not None:
        out("    crossable %.4f  vs bar %.4f  -> %s"
            % (t["frac"], mc, "PASS" if t["frac"] >= mc else "FAIL"))
    if mconn is not None:
        out("    reachable %.4f  vs bar %.4f  -> %s"
            % (t["reachable_frac"], mconn,
               "PASS" if t["reachable_frac"] >= mconn else "FAIL"))
    out("")
    out("--- CONTROL: is the connectivity number about the WORLD or about")
    out("--- the RESOLUTION it was measured at? ---")
    out("  A 35 deg mask taken PER 1 m CELL is punched full of holes by")
    out("  individual steep cells that no rider would ever have to cross.")
    out("  Connected-component labelling counts each hole as a boundary, so")
    out("  fragmentation can be an artefact of sampling rather than a fact")
    out("  about the terrain. The recipe's 0.8 bar predates this map: the")
    out("  alpine world it was written for is 4 m per vertex.")
    out("  So the same computation is repeated on box-reduced copies. If")
    out("  reachability climbs steeply with cell size, the 1 m number is")
    out("  about the instrument; if it stays low, the world really is")
    out("  fragmented for mounts.")
    out("")
    out("  %-10s %10s %10s %12s %12s" % ("cell", "crossable", "largest", "regions", "reachable"))
    for factor in (1, 2, 4, 8):
        if factor == 1:
            hh, sp = h, spacing_cm
        else:
            n = (h.shape[0] // factor) * factor
            hh = (h[:n, :n].astype(np.float64)
                  .reshape(n // factor, factor, n // factor, factor)
                  .mean(axis=(1, 3)))
            sp = spacing_cm * factor
        sl = te.slope_degrees(np.asarray(hh), sp, z_scale_cm)
        tv = te.traversability(sl)[prof]
        out("  %-10s %9.2f%% %9.2f%% %12d %11.2f%%"
            % ("%.0f m" % (sp / 100.0), 100.0 * tv["frac"],
               100.0 * tv["largest_frac"], tv["regions"],
               100.0 * tv["reachable_frac"]))
    out("")
    out("--- the corridor half of unit 2: NOT MEASURED, and why ---")
    out("  unit 2's acceptance wants this figure 'restricted to the")
    out("  inter-massif corridor'. THE CORRIDOR HAS NO SPATIAL DEFINITION")
    out("  ANYWHERE IN THIS REPO. WORLD_VISION.md:304 defines it in prose as")
    out("  'the primary traversal route' and gives no coordinates, no mask")
    out("  and no endpoints; nothing in recipes/ declares one.")
    out("  Inventing a rectangle here and calling it the corridor would make")
    out("  every number computed against it unfalsifiable. Reported as")
    out("  I COULD NOT LOOK, which is not the same as a pass.")
    out("  Closing it needs one ruling from Ryan (two endpoints, or a mask),")
    out("  and it is the same open item as WORLD_VISION.md:322.")
    out("")
    out("  The nearest thing this repo CAN compute is the largest connected")
    out("  %s-traversable component, above: %.2f%% of the map and %.2f%% of"
        % (prof, 100.0 * t["largest_frac"], 100.0 * t["reachable_frac"]))
    out("  all %s-crossable ground. That is a PROXY for reachability, not" % prof)
    out("  the corridor.")

    if args.out:
        p = args.out if os.path.isabs(args.out) else os.path.join(bootstrap.REPO_ROOT, args.out)
        _d = os.path.dirname(p)
        if _d:                     # a bare filename has no dir; makedirs("") raises
            os.makedirs(_d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("# Unit 2 — step height and walkability\n\n```\n"
                     + "\n".join(lines) + "\n```\n")
        print("")
        print("ARTEFACT: %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
