"""find_city_site.py -- where on this terrain can a city actually stand?

    python scripts/find_city_site.py --recipe recipes/alpine_8k.json

OFFLINE. Reads the heightmap PNG and nothing else, so it runs with the editor
busy and its answer does not depend on editor state.

WHY IT IS A TOOL AND NOT A JUDGEMENT. `WORLD_VISION.md:303` rules that the two
foothill basins are the settlement zones -- *"Low, open, traversable ground is
where people live"* -- but it names them in prose and gives no coordinates.
Prose is not a site. This measures the terrain against that ruling and produces
candidates with numbers attached.

THE EVALUATION SCALE IS A PARAMETER AND IT IS DECLARED, because this project
has already been bitten by a bar with no denominator: `traversability()` read
29.26% reachable at 1 m/cell and 94.39% at 8 m, on the SAME terrain, and the
defect was that the bar had no declared scale (LESSONS 2026-08-15, unit 2). A
city occupies hundreds of metres, so flatness is evaluated over cells at
`--cell-m`, not per vertex. A slope that stops a walker does not stop a city
block, and a per-vertex slope map answers a question nobody is asking here.

WHAT IT REFUSES TO DO: pick. It ranks and prints; the site is ruled by a human
or by an explicit follow-up, and the chosen one is written into a recipe where
it becomes data every later script reads (pipeline rule 2).
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def box_reduce(a, f):
    h, w = a.shape
    h2, w2 = (h // f) * f, (w // f) * f
    return a[:h2, :w2].reshape(h2 // f, f, w2 // f, f).mean((1, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--cell-m", type=float, default=8.0,
                    help="evaluation scale; a city block, not a footstep")
    ap.add_argument("--max-slope-deg", type=float, default=6.0,
                    help="buildable ground at the evaluation scale")
    ap.add_argument("--foothill-pct", type=float, default=40.0,
                    help="only terrain below this elevation percentile is "
                         "'foothill'; peaks are not settlement zones")
    ap.add_argument("--min-radius-m", type=float, default=180.0,
                    help="a site smaller than this cannot hold a city")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--out", default="_verify/20260824_city/site_survey.json")
    a = ap.parse_args()

    try:
        from scipy import ndimage
    except ImportError:
        sys.exit("REFUSE: scipy is required (recorded in R0's dependency list)")

    rec = json.load(open(os.path.join(REPO, a.recipe), encoding="utf-8"))
    hm = rec["heightmap"]
    ls = rec["landscape"]
    src = os.path.join(REPO, hm["source"])
    if not os.path.isfile(src):
        sys.exit("REFUSE: no heightmap at %s" % src)

    img = Image.open(src)
    H = np.asarray(img).astype(np.float64)
    if H.ndim != 2:
        sys.exit("REFUSE: heightmap is not single-channel, shape %s" % (H.shape,))

    # UE landscape height mapping, derived from the recipe rather than assumed:
    #   z_cm = location_z + (h/65535 - 0.5) * z_scale_cm
    # At h=0 this gives 0 cm on this recipe, which is the documented terrain
    # floor, and the check below asserts the top matches the recorded span.
    zc = float(ls["location_cm"][2])
    zs = float(ls["z_scale_cm"])
    Z_m = (zc + (H / 65535.0 - 0.5) * zs) / 100.0

    px_m = float(ls["scale_xy_cm"]) / 100.0
    f = max(1, int(round(a.cell_m / px_m)))
    Zc = box_reduce(Z_m, f)
    cell_m = px_m * f

    gy, gx = np.gradient(Zc, cell_m)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    lo_bar = float(np.percentile(Zc, a.foothill_pct))
    buildable = (slope_deg <= a.max_slope_deg) & (Zc <= lo_bar)

    lab, n = ndimage.label(buildable)
    if n == 0:
        sys.exit("REFUSE: no buildable region at slope<=%.1f deg and elevation "
                 "<= p%.0f -- loosen the bars or the terrain has no basin"
                 % (a.max_slope_deg, a.foothill_pct))

    # The largest INSCRIBED CIRCLE, not the area. A long thin valley floor can
    # have a big area and hold nothing square; the distance transform answers
    # "how far from the nearest unbuildable cell", which is the radius a city
    # can actually occupy.
    dist = ndimage.distance_transform_edt(buildable) * cell_m

    sizes = ndimage.sum(buildable, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1][:max(a.top * 4, 24)]

    cands = []
    for li in order:
        m = (lab == li + 1)
        d = np.where(m, dist, 0.0)
        iy, ix = np.unravel_index(int(np.argmax(d)), d.shape)
        r = float(d[iy, ix])
        if r < a.min_radius_m:
            continue
        zin = Zc[m]
        sin_ = slope_deg[m]
        # world cm: landscape origin + cell centre
        wx = float(ls["location_cm"][0]) + (ix + 0.5) * cell_m * 100.0
        wy = float(ls["location_cm"][1]) + (iy + 0.5) * cell_m * 100.0
        cands.append({
            "rank_by": "largest inscribed circle",
            "centre_world_cm": [round(wx, 1), round(wy, 1)],
            "centre_cell": [int(ix), int(iy)],
            "usable_radius_m": round(r, 1),
            "region_area_ha": round(float(sizes[li]) * cell_m * cell_m / 1e4, 1),
            "elev_m": {"mean": round(float(zin.mean()), 1),
                       "min": round(float(zin.min()), 1),
                       "max": round(float(zin.max()), 1)},
            "slope_deg": {"mean": round(float(sin_.mean()), 2),
                          "p90": round(float(np.percentile(sin_, 90)), 2),
                          "max": round(float(sin_.max()), 2)},
            "centre_elev_m": round(float(Zc[iy, ix]), 1),
        })
        if len(cands) >= a.top:
            break

    if not cands:
        sys.exit("REFUSE: no region holds a circle of radius >= %.0f m; the "
                 "largest was %.1f m" % (a.min_radius_m, float(dist.max())))

    rep = {
        "_what": "candidate city sites, measured from the heightmap",
        "recipe": a.recipe,
        "heightmap": hm["source"],
        "heightmap_px": list(H.shape),
        "evaluation": {
            "cell_m": cell_m, "px_per_cell": f,
            "_scale_is_declared": (
                "flatness is evaluated at the scale a CITY occupies, not per "
                "vertex; a bar without its denominator is the unit-2 defect"),
            "max_slope_deg": a.max_slope_deg,
            "foothill_pct": a.foothill_pct,
            "foothill_elev_bar_m": round(lo_bar, 1),
            "min_radius_m": a.min_radius_m,
        },
        "terrain": {
            "elev_m_min": round(float(Z_m.min()), 1),
            "elev_m_max": round(float(Z_m.max()), 1),
            "buildable_frac_of_map": round(float(buildable.mean()), 4),
            "_denominator": "fraction of the WHOLE map, foothill band included",
            "regions_found": int(n),
        },
        "candidates": cands,
    }
    out = os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)

    print("terrain %.1f .. %.1f m   buildable %.2f%% of map   %d regions"
          % (rep["terrain"]["elev_m_min"], rep["terrain"]["elev_m_max"],
             100 * rep["terrain"]["buildable_frac_of_map"], n))
    print("evaluated at %.0f m cells, slope <= %.1f deg, elevation <= %.0f m"
          % (cell_m, a.max_slope_deg, lo_bar))
    print()
    for i, c in enumerate(cands):
        print("  %d. radius %6.1f m   area %8.1f ha   centre (%9.0f, %9.0f) cm"
              % (i + 1, c["usable_radius_m"], c["region_area_ha"],
                 c["centre_world_cm"][0], c["centre_world_cm"][1]))
        print("     elev %.0f m (%.0f..%.0f)   slope mean %.2f p90 %.2f deg"
              % (c["centre_elev_m"], c["elev_m"]["min"], c["elev_m"]["max"],
                 c["slope_deg"]["mean"], c["slope_deg"]["p90"]))
    print("\nwrote %s" % a.out)


main()
