"""derive_ground_station.py — derive Bench_ground, the station the
surface metrics can actually be measured at.

    python scripts/derive_ground_station.py [--out J]
    python scripts/derive_ground_station.py --selftest

RULED BY RYAN 2026-09-11: standing height, ~20 deg down, over open
meadow, 30 m AND 300 m both in frame, no trees in the lower half.

WHY IT HAS TO BE DERIVED RATHER THAN PLACED. On FLAT ground a standing
camera cannot satisfy the ruling at all:

    eye 1.7 m, vFOV 58.72 deg, 36.8 px per degree at 2160
    ground 30 m  -> 3.243 deg depression
    ground 100 m -> 0.974 deg
    ground 300 m -> 0.325 deg
    band  30-100 m  =  2.269 deg =  83 px
    band 100-300 m  =  0.649 deg =  24 px

Both are below `surface_report`'s 160 px floor, and the far band is
below it by 6.6x. Distance compresses into the horizon faster than any
choice of pitch can fix -- pitch moves the bands up and down the frame,
it does not make them thicker. **The only thing that thickens them is
ground that RISES away from the camera**, so that is what this search
scores: a site whose forward view climbs, not one that is merely open.

That is also why the three existing bench stations cannot serve
(LESSONS 2026-09-11g): they were derived for Brief 1's angular budget,
which never asked for a ground band at a controlled distance.

THE CONSTRAINTS, each measured rather than eyeballed:
  * MEADOW      derived meadow weight at the camera foot >= MEADOW_MIN
  * OPEN        no tree instance projects into the LOWER HALF of frame
  * BOTH BANDS  terrain hits in 30-100 m and 100-300 m, each at least
                MIN_BAND_PX rows when scaled to 2160
  * STANDING    eye EYE_M above the sampled ground, pitch PITCH_DEG
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from bench_station_derive import (camera_basis, load_species,  # noqa: E402
                                  load_terrain, ray_grid, raymarch,
                                  sample_height, splat_canopy)

EYE_M = 1.7
PITCH_DEG = -20.0
FOV_H = 90.0
FULL_RES = (3840, 2160)
SEARCH_RES = (256, 144)
REFINE_RES = (640, 360)
BANDS = [(30.0, 100.0), (100.0, 300.0)]
MIN_BAND_PX = 160          # surface_report's MIN_CROP, at full res
MEADOW_MIN = 0.55
T_MAX_M = 900.0

# ---- v2, 2026-09-11 -----------------------------------------------------
# The v1 station predicted 405/375 band rows and the render gave 55/0.
# Three defects, all fixed here (LESSONS 2026-09-11l):
#
# 1 QUANTISATION. Scoring ran at 256x144 and multiplied by 15 to reach
#   full res, so ONE scored row WAS the whole margin. Now: a coarse pass
#   shortlists, and the shortlist is re-scored at 640x360 (1 row = 6).
# 2 GROUND COVER WAS NOT MODELLED -- and modelling it turns out to HELP,
#   because it is CULLED. Meadow's authored cull is 50 m and Blueberry's
#   is 45 m (species_heights, measured), so beyond 50 m there is no
#   ground cover at all and the landscape material is directly visible.
#   The 100-300 m bin is entirely bare by construction; only part of
#   30-100 m is grassed. Within the cull, occlusion is modelled as
#   Beer-Lambert extinction along the grazing path through a layer of
#   the MEASURED placed height.
# 3 CONCAVITY WAS REQUIRED OF THE FIXTURE AND NOT OF THE SEARCH. A
#   uniform rise puts every distance at the same view angle and collapses
#   the ground to a line; only a profile that curves UP spreads the
#   distances. Now an explicit gate.
GRASS_H_M = 0.484          # Meadow placed_height_max_m
GRASS_CULL_M = 50.0        # Meadow authored cull; Blueberry's is 45
GRASS_SIGMA_PER_M = 2.6    # areal extinction: ~13.2 clumps/m2 x ~0.2 m
GRASS_MIN_TRANSMISSION = 0.5
SHORTLIST = 40


def _meadow():
    b = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8b.png")))
    return b[..., 3].astype(np.float32) / 255.0     # B-map alpha = meadow


def grass_transmission(terr, dirs_z, rh, rw):
    """Fraction of ground still visible through the ground-cover layer.

    Beer-Lambert along the GRAZING path: a ray descending at angle theta
    to the surface crosses the layer over a horizontal distance
    h/tan(theta), and the chance of missing every clump over that run is
    exp(-sigma * run). Beyond the cull there is no cover, so transmission
    is 1 -- which is the whole reason a far band is measurable at all.
    """
    sin_t = np.clip(np.abs(dirs_z.reshape(rh, rw)), 1e-4, 1.0)
    tan_t = sin_t / np.sqrt(np.maximum(1.0 - sin_t * sin_t, 1e-8))
    run = GRASS_H_M / np.maximum(tan_t, 1e-4)
    t = np.exp(-GRASS_SIGMA_PER_M * run)
    return np.where(terr > GRASS_CULL_M, 1.0, t)


def forward_profile_concave(Z, ox, oy, px_m, cam, yaw):
    """Does the ground RISE and CURVE UP along the view azimuth?

    Sampled at 30..300 m; concave means the second difference of height
    against distance is positive on average. A uniform slope scores 0 and
    is rejected: it places every distance at the same view angle."""
    d = np.linspace(30.0, 300.0, 19)
    ux, uy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    h = sample_height(Z, ox, oy, px_m, cam[0] + ux * d, cam[1] + uy * d)
    if not np.isfinite(h).all():
        return None, None
    d2 = np.diff(h, 2)
    return float(np.mean(d2)), float(h[-1] - h[0])


def evaluate(Z, ox, oy, px_m, species, x_m, y_m, yaw, res=SEARCH_RES):
    """Band row heights, ground-cover transmission and canopy, for one
    candidate. A band row counts only where the GROUND is visible: not
    sky, not canopy, and not behind ground cover."""
    g = float(sample_height(Z, ox, oy, px_m, np.array([x_m]),
                            np.array([y_m]))[0])
    if not np.isfinite(g):
        return None
    cam = np.array([x_m, y_m, g + EYE_M])
    F, R, U = camera_basis(PITCH_DEG, yaw)
    rw, rh = res
    dirs = ray_grid(F, R, U, FOV_H, rw, rh)
    ang = math.radians(FOV_H) / rw
    terr = raymarch(Z, ox, oy, px_m, cam, dirs, T_MAX_M, ang).reshape(rh, rw)
    canopy = splat_canopy(species, cam, F, R, U, FOV_H, rw, rh, terr, T_MAX_M)
    trans = grass_transmission(terr, dirs[:, 2], rh, rw)
    visible_ground = (np.isfinite(terr) & ~np.isfinite(canopy)
                      & (trans >= GRASS_MIN_TRANSMISSION))
    scale = FULL_RES[1] / float(rh)
    rows = []
    for lo, hi in BANDS:
        inb = visible_ground & (terr >= lo) & (terr <= hi)
        # ROWS, not pixels: surface_report crops a contiguous row band, so
        # the quantity that has to clear its floor is the band's HEIGHT.
        nrows = int((inb.sum(axis=1) > rw * 0.5).sum())
        rows.append(nrows * scale)
    lower = canopy[rh // 2:, :]
    curv, rise = forward_profile_concave(Z, ox, oy, px_m, cam, yaw)
    return {"ground_z_m": g, "cam": cam, "yaw": yaw,
            "band_rows_full_res": [round(r, 1) for r in rows],
            "canopy_px_lower_half": int(np.isfinite(lower).sum()),
            "canopy_px_total": int(np.isfinite(canopy).sum()),
            "forward_curvature": (round(curv, 6) if curv is not None
                                  else None),
            "forward_rise_m": round(rise, 2) if rise is not None else None,
            "grass_occluded_frac": round(float(
                (trans < GRASS_MIN_TRANSMISSION).mean()), 4),
            "res": [rw, rh],
            "score": min(rows)}


def _load_water_filter(exclude_water, near_world_cm, radius_m):
    """Return a predicate keep(x_m, y_m) -> bool + a rejection Counter,
    for Brief-4 T7.

    Excludes submerged candidates (inside a §7 water footprint) and, if a
    centre+radius is given, restricts candidates to that neighbourhood
    (Lake A's shore). Both are ADDITIVE filters over the ruled search; the
    concavity/canopy/meadow gates in evaluate() are untouched.

    The centre is WORLD CENTIMETRES `[x_cm, y_cm]` -- NOT a grid col/row --
    so there is no metres-vs-centimetres or which-grid ambiguity (audit
    W1/W2, 2026-09-19). The mask read is in cm, matching plan_encounters.
    WaterMask and encounters_in_water.to_grid exactly.
    """
    rejected = {"water": 0, "outside_radius": 0}
    wmask = wox = woy = wcell_cm = None
    if exclude_water:
        z = np.load(exclude_water, allow_pickle=False)
        wmask = z["mask"]
        wox, woy = (float(v) for v in z["origin_cm"])
        wcell_cm = float(z["cell_m"][0]) * 100.0
    cx = cy = r_cm = None
    if near_world_cm is not None:
        cx, cy = float(near_world_cm[0]), float(near_world_cm[1])
        r_cm = float(radius_m) * 100.0

    def keep(x_m, y_m):
        x_cm, y_cm = x_m * 100.0, y_m * 100.0
        if wmask is not None:
            wc = int(round((x_cm - wox) / wcell_cm))
            wr = int(round((y_cm - woy) / wcell_cm))
            if 0 <= wr < wmask.shape[0] and 0 <= wc < wmask.shape[1] \
                    and wmask[wr, wc]:
                rejected["water"] += 1
                return False
        if cx is not None and math.hypot(x_cm - cx, y_cm - cy) > r_cm:
            rejected["outside_radius"] += 1
            return False
        return True

    return keep, rejected


def search(step_m=260.0, yaws=8, res=SEARCH_RES, limit=None,
           exclude_water=None, near_world_cm=None, radius_m=None):
    rec = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                         encoding="utf-8"))
    Z, ox, oy, px_m = load_terrain(os.path.join(REPO, "recipes",
                                                "alpine_8k.json"))
    keep, filt_rejected = _load_water_filter(exclude_water, near_world_cm,
                                             radius_m)
    fol = rec["foliage"]
    paths, widths, heights = {}, {}, {}
    for sp in fol["species"]:
        p = "foliage/alpine_8k_%s.json" % sp["name"]
        if os.path.isfile(os.path.join(REPO, p)):
            paths[sp["name"]] = p
            widths[sp["name"]] = float(sp.get("mesh_width_m", 6.0))
            heights[sp["name"]] = float(sp.get("mesh_height_m", 20.0))
    species = load_species(paths, widths, heights)
    meadow = _meadow()

    ny, nx = Z.shape
    stride = int(step_m / px_m)
    cands, tried, considered, rejected = [], 0, 0, {"canopy": 0, "convex": 0}
    for iy in range(stride, ny - stride, stride):
        for ix in range(stride, nx - stride, stride):
            if meadow[iy, ix] < MEADOW_MIN:
                continue
            x_m = ox + ix * px_m
            y_m = oy + iy * px_m
            if not keep(x_m, y_m):
                continue
            considered += 1
            for k in range(yaws):
                yaw = 360.0 * k / yaws
                r = evaluate(Z, ox, oy, px_m, species, x_m, y_m, yaw, res)
                tried += 1
                if r is None:
                    continue
                if r["canopy_px_lower_half"] > 0:
                    rejected["canopy"] += 1
                    continue
                # CONCAVITY IS A GATE, not a tiebreak. A uniform or convex
                # profile cannot spread the distances however well it
                # scores on a coarse grid -- that is what v1 selected.
                if not r["forward_curvature"] or r["forward_curvature"] <= 0:
                    rejected["convex"] += 1
                    continue
                cands.append(dict(r, x_m=x_m, y_m=y_m,
                                  meadow=float(meadow[iy, ix])))
                if limit and tried >= limit:
                    break
            if limit and tried >= limit:
                break
        if limit and tried >= limit:
            break

    # RE-SCORE THE SHORTLIST AT HIGHER RESOLUTION. The coarse grid's row
    # quantisation was v1's entire margin, so a coarse WINNER is only a
    # candidate; the number that gets reported comes from the fine pass.
    cands.sort(key=lambda r: -r["score"])
    short = cands[:SHORTLIST]
    refined = []
    for c in short:
        r = evaluate(Z, ox, oy, px_m, species, c["x_m"], c["y_m"], c["yaw"],
                     REFINE_RES)
        if r is None or r["canopy_px_lower_half"] > 0:
            continue
        refined.append(dict(r, x_m=c["x_m"], y_m=c["y_m"],
                            meadow=c["meadow"],
                            coarse_score=c["score"]))
    refined.sort(key=lambda r: -r["score"])
    best = refined[0] if refined else None
    return best, considered, tried, {"rejected": rejected,
                                     "filter_rejected": dict(filt_rejected),
                                     "candidates": len(cands),
                                     "shortlisted": len(short),
                                     "refined": len(refined),
                                     "top5": [r["band_rows_full_res"]
                                              for r in refined[:5]]}


def selftest():
    """1 rising ground beats flat; 2 a treed site is rejected; 3 a camera
    off the heightmap refuses."""
    fails = []

    def check(name, cond):
        print("  %-56s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    n, sp = 700, 4.0
    ox = oy = 0.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    flat = np.full((n, n), 100.0, dtype=np.float32)
    # GROUND THAT RISES AWAY, CONCAVELY. A UNIFORM slope is the wrong
    # fixture and the first draft used one: at 0.35 (19.3 deg) it buries a
    # 1.7 m eye within 5 m and both bands read 0 rows. Worse, even a
    # gentle uniform slope is degenerate here -- every distance sits at
    # the same angle atan(s), so the whole ground plane collapses onto one
    # line. What actually thickens a far band is a CONCAVE profile
    # (a valley floor curving up into a facing slope): for h = d^2/2R the
    # view angle atan(d/2R - eye/d) GROWS with distance instead of
    # compressing toward the horizon.
    d_fwd = np.clip((yy - n / 2) * sp, 0, None)
    rising = (100.0 + d_fwd * d_fwd / (2.0 * 2000.0)).astype(np.float32)
    cx = cy = n / 2 * sp
    rf = evaluate(flat, ox, oy, sp, {}, cx, cy, 90.0)
    rr = evaluate(rising, ox, oy, sp, {}, cx, cy, 90.0)
    print("    flat   bands %s" % rf["band_rows_full_res"])
    print("    rising bands %s" % rr["band_rows_full_res"])
    check("rising ground gives a THICKER far band than flat",
          rr["band_rows_full_res"][1] > rf["band_rows_full_res"][1])
    check("flat ground's far band is below the 160 px floor",
          rf["band_rows_full_res"][1] < MIN_BAND_PX)

    # a tree right in front must land in the lower half
    treed = {"T": {"xyz_m": np.array([[cx, cy + 3.0, 100.0]]),
                   "scale": np.array([1.0]), "mesh_h_m": 18.0,
                   "mesh_w_m": 6.0, "count": 1, "cull_cm": None,
                   "path": "synthetic"}}
    rt = evaluate(flat, ox, oy, sp, treed, cx, cy, 90.0)
    check("a tree 3 m ahead is seen in the lower half",
          rt["canopy_px_lower_half"] > 0)
    check("with no trees the lower half is clear",
          rf["canopy_px_lower_half"] == 0)

    off = evaluate(flat, ox, oy, sp, {}, -9e5, -9e5, 90.0)
    check("a camera off the heightmap refuses", off is None)

    # T7 filter (audit W1/W2/W4): world-cm centre + radius, and a water
    # mask, exercised in cm so a metres/centimetres slip cannot hide. A
    # point 500 m from the centre is admitted at radius 600 and rejected
    # at radius 400; a masked cell is rejected regardless.
    import tempfile
    m = np.zeros((10, 10), dtype=np.uint8)
    m[5, 5] = 1                                  # one water cell
    tf = os.path.join(tempfile.gettempdir(), "_gs_selftest_mask.npz")
    np.savez(tf, mask=m, origin_cm=np.array([0.0, 0.0]),
             cell_m=np.array([4.0]))             # 4 m/px, cell (5,5)=~2000 cm
    keepA, rejA = _load_water_filter(tf, [10000.0, 0.0], 600.0)
    check("filter: point at the centre (world cm) is kept",
          keepA(100.0, 0.0) is True)             # 100 m -> 10000 cm == centre
    check("filter: 500 m from centre kept at radius 600",
          keepA(100.0 + 500.0, 0.0) is True)
    keepB, rejB = _load_water_filter(tf, [10000.0, 0.0], 400.0)
    check("filter: 500 m from centre rejected at radius 400",
          keepB(100.0 + 500.0, 0.0) is False)
    # water rejection, no radius constraint: cell (col 5,row 5) at 4 m/px,
    # origin 0 -> world 20 m = 2000 cm is masked.
    keepW, rejW = _load_water_filter(tf, None, None)
    check("filter: a masked cell is rejected as water",
          keepW(20.0, 20.0) is False and rejW["water"] >= 1)
    check("filter: a dry cell is kept",
          keepW(0.0, 0.0) is True)

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--step-m", type=float, default=260.0)
    ap.add_argument("--yaws", type=int, default=8)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--exclude-water", default=None,
                    help="npz mask of section-7 water footprints; submerged "
                         "candidates are skipped (Brief-4 T7)")
    ap.add_argument("--near-world-cm", default=None,
                    help="'x_cm,y_cm' WORLD centimetres; restrict candidates "
                         "to --radius-m of this (e.g. Lake A shore). World cm, "
                         "NOT a grid col/row -- no grid/unit ambiguity.")
    ap.add_argument("--radius-m", type=float, default=600.0)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    nwc = None
    if a.near_world_cm:
        nwc = [float(v) for v in a.near_world_cm.split(",")]
    best, considered, tried, stats = search(
        a.step_m, a.yaws, exclude_water=a.exclude_water,
        near_world_cm=nwc, radius_m=a.radius_m)
    print("search: %d meadow sites, %d views, %s"
          % (considered, tried, json.dumps(stats)))
    if best is None:
        print("REFUSE: no candidate met the constraints "
              "(%d meadow sites, %d views tried)" % (considered, tried))
        return 4
    cam = best["cam"]
    out = {"_what": "Bench_ground, derived 2026-09-11 (RULED)",
           "label": "Bench_ground",
           "camera_string": "%.1f,%.1f,%.1f,%.1f,%.1f,0.0"
                            % (cam[0] * 100.0, cam[1] * 100.0, cam[2] * 100.0,
                               PITCH_DEG, best["yaw"]),
           "location_cm": [round(cam[0] * 100.0, 1), round(cam[1] * 100.0, 1),
                           round(cam[2] * 100.0, 1)],
           "rotation_deg_pitch_yaw_roll": [PITCH_DEG, best["yaw"], 0.0],
           "eye_m": EYE_M, "ground_z_m": round(best["ground_z_m"], 2),
           "meadow_weight": round(best["meadow"], 4),
           "band_rows_full_res": best["band_rows_full_res"],
           "min_band_rows_required": MIN_BAND_PX,
           "canopy_px_lower_half": best["canopy_px_lower_half"],
           "canopy_px_total": best["canopy_px_total"],
           "forward_curvature": best["forward_curvature"],
           "forward_rise_m": best["forward_rise_m"],
           "grass_occluded_frac": best["grass_occluded_frac"],
           "scored_at_res": best["res"],
           "coarse_score": best.get("coarse_score"),
           "search_stats": stats,
           "meadow_sites_considered": considered, "views_tried": tried,
           "fov_h_deg": FOV_H, "res": list(FULL_RES),
           "_v2": ("grass modelled as Beer-Lambert extinction inside its "
                   "50 m cull; concavity a GATE; shortlist re-scored at "
                   "640x360. v1 predicted 405/375 and the render gave "
                   "55/0 (LESSONS 2026-09-11l).")}
    out["bands_clear_floor"] = all(r >= MIN_BAND_PX
                                   for r in best["band_rows_full_res"])
    print(json.dumps(out, indent=1))
    if not out["bands_clear_floor"]:
        print("NOTE: the best site in the world still does not give both "
              "bands %d rows. That is a fact about this terrain, not a "
              "failure of the search -- report it rather than lowering the "
              "floor." % MIN_BAND_PX)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
