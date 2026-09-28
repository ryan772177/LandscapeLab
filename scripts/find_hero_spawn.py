"""find_hero_spawn.py — find a CLEARING to spawn the player in.

WHY THIS EXISTS, AND IT IS A MEASURED DEFECT NOT A PREFERENCE.
The PlayerStart was placed by tracing the ground and adding 120 cm, with no
regard for what is STANDING there. 219,659 tree instances occupy this world, so
the trace put the player inside a stand. Two consequences were photographed on
2026-08-16:

  * the third-person spring arm probes for collision, hits a trunk, and
    collapses -- the first frame of the game is a 1 m close-up of the player's
    back (_verify/20260816_hero_pie_forestfloor.png);
  * disabling the probe is not the cure, it puts the camera inside the canopy
    instead.

Shrinking the probe helped and did not fix it, because the cause is WHERE the
player stands. This tool answers that directly: where, on this terrain, is
there ground far enough from every trunk for a camera to sit behind the player.

INSTRUMENT AND ITS SOURCE, DECLARED (non-negotiable 0).
Instance positions come from foliage/alpine_8k_*.json -- the PLACEMENT PLANS,
which is the same source place_foliage wrote into the world and which unit 4's
grounding work verified matches the world by two representations. Ground height
and slope come from the HEIGHTMAP. Those are two different artefacts, but they
are NOT independent confirmations of each other and nothing here claims they
are: the plan is used only for "is a trunk near", the heightmap only for "is
this ground walkable". Neither is asked to corroborate the other.

The final Z is NOT taken from either -- place_player_start traces the live
COLLISION surface, which is a third representation and the only one that
decides where a character actually stands.

USAGE
    python scripts/find_hero_spawn.py
    python scripts/find_hero_spawn.py --clear-radius-m 14 --top 10
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

try:
    from scipy.spatial import cKDTree
except ImportError:
    print("REFUSE: scipy is required (recorded in R0's dependency list).")
    raise SystemExit(2)

RECIPE = "recipes/alpine_8k.json"

# UE landscape png16 datum: 32768 is mid-range (z=0 relative to the landscape
# origin), full 16-bit range maps to z_scale_cm.
HEIGHT_DATUM = 32768.0


def trunk_plans(rec):
    """The trunk placement-plan names, DERIVED from the recipe (pipeline rule 2)
    rather than hardcoded: every foliage species whose system is not 'grass'.
    A fifth tree added to the recipe is then included automatically instead of
    being silently excluded from the clearance test."""
    return ["alpine_8k_" + s["name"]
            for s in rec.get("foliage", {}).get("species", [])
            if s.get("system") != "grass"]


def load_instances(repo: str, plans):
    xs, ys, per = [], [], {}
    if not plans:
        print("REFUSE: the recipe declares no non-grass (trunk) species.")
        raise SystemExit(2)
    for name in plans:
        p = os.path.join(repo, "foliage", name + ".json")
        if not os.path.isfile(p):
            print("REFUSE: missing placement plan: %s" % p)
            raise SystemExit(2)
        with open(p, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if "species" not in d or "instances" not in d:
            print("REFUSE: plan %s lacks 'species'/'instances'." % p)
            raise SystemExit(2)
        inst = d["instances"]
        if not inst:
            print("REFUSE: plan %s has zero instances." % p)
            raise SystemExit(2)
        per[d["species"]] = len(inst)
        a = np.asarray([(r[0], r[1]) for r in inst], dtype=np.float64)
        xs.append(a[:, 0])
        ys.append(a[:, 1])
    return np.concatenate(xs), np.concatenate(ys), per


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clear-radius-m", type=float, default=12.0,
                    help="required distance to the nearest trunk")
    ap.add_argument("--grid-m", type=float, default=20.0)
    ap.add_argument("--max-slope-deg", type=float, default=20.0,
                    help="candidate ground must be gentler than this")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--near-cm", default=None, metavar="X,Y",
                    help="rank by closeness to this X,Y instead of by clearance")
    args = ap.parse_args(argv)

    repo = bootstrap.REPO_ROOT
    with open(os.path.join(repo, RECIPE), "r", encoding="utf-8") as fh:
        rec = json.load(fh)
    ls = rec["landscape"]
    hm = rec["heightmap"]
    ox, oy = ls["location_cm"][0], ls["location_cm"][1]
    sxy = float(ls["scale_xy_cm"])
    res = int(hm["resolution"])

    x, y, per = load_instances(repo, trunk_plans(rec))
    print("instances loaded:")
    for k, v in per.items():
        print("  %-16s %d" % (k, v))
    print("  %-16s %d" % ("TOTAL", x.size))

    tree = cKDTree(np.column_stack([x, y]))

    # Candidate grid in WORLD cm, inset so a candidate cannot fall off the map.
    step = args.grid_m * 100.0
    inset = 400.0 * 100.0
    gx = np.arange(ox + inset, ox + res * sxy - inset, step)
    gy = np.arange(oy + inset, oy + res * sxy - inset, step)
    GX, GY = np.meshgrid(gx, gy, indexing="ij")
    pts = np.column_stack([GX.ravel(), GY.ravel()])
    print("candidates: %d on a %.0f m grid" % (pts.shape[0], args.grid_m))

    dist, _ = tree.query(pts, k=1)
    keep = dist >= args.clear_radius_m * 100.0
    pts, dist = pts[keep], dist[keep]
    print("clear of %.1f m: %d candidates" % (args.clear_radius_m, pts.shape[0]))
    if pts.shape[0] == 0:
        print("REFUSE: no clearing at that radius. Lower --clear-radius-m.")
        return 1

    # Slope from the heightmap, as a SEPARATE question from tree proximity.
    from PIL import Image
    hpath = os.path.join(repo, hm["source"].replace("/", os.sep))
    if not os.path.isfile(hpath):
        print("REFUSE: heightmap absent: %s" % hpath)
        return 2
    im = Image.open(hpath)
    H = np.asarray(im).astype(np.float64)
    if H.ndim != 2 or H.shape != (res, res):
        print("REFUSE: heightmap is %s, not the recipe's %dx%d; indices would "
              "map to the wrong pixels." % (H.shape, res, res))
        return 2
    zscale = float(ls["z_scale_cm"])
    # UE landscape: 16-bit heightmap, 32768 is the datum, full range maps to
    # z_scale_cm. Slope is computed on the SAME grid the candidates sit on.
    px = np.clip(((pts[:, 0] - ox) / sxy).astype(np.int64), 1, res - 2)
    py = np.clip(((pts[:, 1] - oy) / sxy).astype(np.int64), 1, res - 2)
    cm_per_unit = zscale / 65535.0

    def hz(ix, iy):
        return H[iy, ix] * cm_per_unit

    dzdx = (hz(px + 1, py) - hz(px - 1, py)) / (2.0 * sxy)
    dzdy = (hz(px, py + 1) - hz(px, py - 1)) / (2.0 * sxy)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    gentle = slope <= args.max_slope_deg
    pts, dist, slope = pts[gentle], dist[gentle], slope[gentle]
    print("and gentler than %.0f deg: %d candidates"
          % (args.max_slope_deg, pts.shape[0]))
    if pts.shape[0] == 0:
        print("REFUSE: nothing both clear and walkable. Relax a bound.")
        return 1

    if args.near_cm:
        nx, ny = [float(v) for v in args.near_cm.split(",")]
        d2 = np.hypot(pts[:, 0] - nx, pts[:, 1] - ny)
        order = np.argsort(d2)
    else:
        order = np.argsort(-dist)

    print()
    print("%-4s %14s %14s %10s %8s %10s" %
          ("#", "world_x_cm", "world_y_cm", "clear_m", "slope", "height_m"))
    out = []
    for i in order[:args.top]:
        ix = int(np.clip((pts[i, 0] - ox) / sxy, 1, res - 2))
        iy = int(np.clip((pts[i, 1] - oy) / sxy, 1, res - 2))
        # Subtract the datum: the comment above declared 32768 as the datum but
        # the height was reported WITHOUT subtracting it, inflating every
        # approx_height_m by 32768*cm_per_unit (~1280 m over a world capped at
        # 1552.5 m). Slope is unaffected (the datum cancels in the difference).
        zc = (H[iy, ix] - HEIGHT_DATUM) * cm_per_unit + ls["location_cm"][2]
        print("%-4d %14.1f %14.1f %10.1f %8.1f %10.1f"
              % (len(out), pts[i, 0], pts[i, 1], dist[i] / 100.0,
                 slope[i], zc / 100.0))
        out.append({"x_cm": float(pts[i, 0]), "y_cm": float(pts[i, 1]),
                    "clear_m": float(dist[i] / 100.0),
                    "slope_deg": float(slope[i]),
                    "approx_height_m": float(zc / 100.0)})

    art = os.path.join(repo, "_verify", "20260816_hero_spawn_candidates.json")
    os.makedirs(os.path.dirname(art), exist_ok=True)
    with open(art, "w", encoding="utf-8") as fh:
        json.dump({"clear_radius_m": args.clear_radius_m,
                   "max_slope_deg": args.max_slope_deg,
                   "grid_m": args.grid_m,
                   "instances_considered": int(x.size),
                   "candidates": out}, fh, indent=2)
    # Read the artefact back rather than trusting the write succeeded.
    try:
        with open(art, "r", encoding="utf-8") as fh:
            n_written = len(json.load(fh).get("candidates", []))
    except (OSError, ValueError) as exc:
        print("REFUSE: report did not write back cleanly: %s" % exc)
        return 2
    print()
    print("wrote", art, "(%d candidates verified on disk)" % n_written)
    print("Z above is the HEIGHTMAP's; the spawn's real Z must come from a")
    print("collision trace, which place_player_start does.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
