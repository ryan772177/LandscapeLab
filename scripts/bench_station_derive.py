"""bench_station_derive.py -- choose a benchmark camera by MEASURING what it
frames, instead of computing a bearing and hoping.

WHY THIS EXISTS. `recipes/perf_budgets.json` derives its four stations from
bearings: "treeline at 1.25x the town extent radius", "vista at 2.6x extent on
the opposite side, looking back over the town to the peak". Those are correct
POSITIONS and they were never checked for OCCLUSION. On 2026-09-05
(`_verify/20260905_stations/STATIONS_READ.md`) the first renders ever taken at
those stations showed `treeline` as a near-vertical rock face filling ~85% of
frame and `vista` showing neither the town nor the peak. A bearing tells you
where a thing is; it does not tell you whether anything is in the way.

WHAT IT MEASURES. For a candidate camera it ray-marches the SAME heightmap the
landscape was imported from, and projects the SAME placed instance lists the
world was built from, then reports:

  - percentage of frame per DEPTH BAND (near <100 m / mid 100 m-1 km / far >1 km)
  - percentage of frame that is SKY
  - percentage of frame that is NEAR TERRAIN (<100 m) -- the "pressed against a
    rock face" number; the 2026-09-05 treeline frame would score ~85% here
  - percentage of frame that is CANOPY inside a named pixel band (e.g. the
    6-40 px shape band), which is the quantity Brief 1's ladder actually needs
  - whether a RIDGE SILHOUETTE exists: terrain meeting sky beyond a distance

and a PASS/FAIL against a declared requirement, so the station choice is a
measurement with a recorded verdict rather than a judgement call.

INSTRUMENT CLASS, STATED PLAINLY. This is an OFFLINE model of the world built
from the heightmap and the instance lists. It is NOT the renderer. It does not
know about the town's building actors (engine primitives placed separately),
alpha-tested gaps in foliage cards, LOD, or the landscape material. Two
consequences:

  1. Canopy coverage here is SILHOUETTE coverage -- a cone-shaped solid per
     tree. Real alpha-tested foliage has gaps, so this is an UPPER BOUND on
     opaque canopy. Good enough to answer "are there trees in this band at
     all", which is what the old stations failed.
  2. A station derived here MUST be confirmed by an actual render before it is
     locked. Non-negotiable 8: verify with a different instrument than the one
     that made the claim. This tool proposes; the editor disposes.

CONVENTIONS, taken from the repo and not invented (standing rule 9):
  height mapping   Z_m = (location_cm[2] + (h/65535 - 0.5) * z_scale_cm) / 100
  cell to world    world_cm = location_cm[xy] + (i + 0.5) * scale_xy_cm
  both from scripts/find_city_site.py:80-85 and :124-125
  camera string    x,y,z,pitch,yaw,roll  (scripts/perf_flythrough.py:11)
  pixels tall      h / (2*D*tan(vFOV/2)) * H  (scripts/angular_budget.py,
                   verified against engine source 2026-09-05, R-ANGBUDGET)

USAGE
  python bench_station_derive.py --selftest
  python bench_station_derive.py --evaluate X Y YAW PITCH [--eye-m 1.75]
  python bench_station_derive.py --scan --profile mid_slope --out cands.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Image.MAX_IMAGE_PIXELS = None

# Depth band edges in metres. "near" is the pressed-against-terrain detector.
NEAR_M = 100.0
MID_M = 1000.0


# --------------------------------------------------------------------------
# terrain
# --------------------------------------------------------------------------

def load_terrain(recipe_path):
    """Return (Z_m float32 [ny, nx], ox_m, oy_m, px_m). Z_m[iy, ix] is the
    terrain height in metres at world (ox + (ix+0.5)*px, oy + (iy+0.5)*px)."""
    rec = json.load(open(recipe_path, encoding="utf-8"))
    ls = rec["landscape"]
    hm = rec["heightmap"]
    src = os.path.join(REPO, hm["source"])
    if not os.path.isfile(src):
        sys.exit("REFUSE: no heightmap at %s" % src)
    H = np.asarray(Image.open(src))
    if H.ndim != 2:
        sys.exit("REFUSE: heightmap is not single-channel, shape %s" % (H.shape,))
    zc = float(ls["location_cm"][2])
    zs = float(ls["z_scale_cm"])
    Z = ((zc + (H.astype(np.float32) / 65535.0 - 0.5) * zs) / 100.0).astype(np.float32)
    px_m = float(ls["scale_xy_cm"]) / 100.0
    ox = float(ls["location_cm"][0]) / 100.0
    oy = float(ls["location_cm"][1]) / 100.0
    return Z, ox, oy, px_m


def sample_height(Z, ox, oy, px_m, x, y):
    """Bilinear terrain height at world metres (x, y), vectorised.

    Out-of-bounds samples return -inf so a ray that leaves the landscape never
    reports a hit -- it should see sky, not a phantom wall at the edge."""
    fx = (np.asarray(x, dtype=np.float64) - ox) / px_m - 0.5
    fy = (np.asarray(y, dtype=np.float64) - oy) / px_m - 0.5
    ny, nx = Z.shape
    ok = (fx >= 0) & (fy >= 0) & (fx <= nx - 1.001) & (fy <= ny - 1.001)
    x0 = np.clip(np.floor(fx), 0, nx - 2).astype(np.int32)
    y0 = np.clip(np.floor(fy), 0, ny - 2).astype(np.int32)
    tx = np.clip(fx - x0, 0.0, 1.0)
    ty = np.clip(fy - y0, 0.0, 1.0)
    z00 = Z[y0, x0]; z10 = Z[y0, x0 + 1]
    z01 = Z[y0 + 1, x0]; z11 = Z[y0 + 1, x0 + 1]
    z = (z00 * (1 - tx) * (1 - ty) + z10 * tx * (1 - ty)
         + z01 * (1 - tx) * ty + z11 * tx * ty)
    return np.where(ok, z, -np.inf)


# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------

def camera_basis(pitch_deg, yaw_deg):
    """UE-convention forward/right/up for roll 0. X fwd, Y right, Z up.

    Verified by selftest: pitch -90 must give forward (0,0,-1)."""
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)
    F = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    R = np.array([-math.sin(y), math.cos(y), 0.0])
    U = np.cross(F, R)          # F x R, not R x F: at pitch 0 this is +Z
    return F, R, U


def ray_grid(F, R, U, fov_h_deg, res_w, res_h):
    """Unit ray directions for a res_w x res_h grid of pixel centres.
    Returns (dirs [N,3], N) with row 0 = top of frame."""
    th = math.tan(math.radians(fov_h_deg) / 2.0)
    tv = th * res_h / res_w
    u = (np.arange(res_w) + 0.5) / res_w * 2.0 - 1.0          # -1 .. +1, left to right
    v = 1.0 - (np.arange(res_h) + 0.5) / res_h * 2.0          # +1 .. -1, top to bottom
    uu, vv = np.meshgrid(u, v)
    d = (F[None, None, :]
         + (uu * th)[:, :, None] * R[None, None, :]
         + (vv * tv)[:, :, None] * U[None, None, :])
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    return d.reshape(-1, 3)


def march_schedule(t_start, t_max, ang_res_rad, min_step, max_step):
    """Shared distance schedule for all rays. Step tracks the angular size of a
    pixel so the march never strides past a feature that would be visible."""
    ts = []
    t = t_start
    while t < t_max:
        ts.append(t)
        t += min(max(t * ang_res_rad * 2.0, min_step), max_step)
    ts.append(t_max)
    return np.asarray(ts, dtype=np.float64)


def raymarch(Z, ox, oy, px_m, cam, dirs, t_max, ang_res_rad,
             min_step=0.5, max_step=6.0):
    """March all rays in lockstep. Returns hit distance per ray, inf for sky.

    Refines each hit by bisection between the last clear step and the first
    occluded one, so the returned distance is not quantised to the schedule."""
    ts = march_schedule(max(min_step, 1.0), t_max, ang_res_rad, min_step, max_step)
    n = dirs.shape[0]
    hit = np.full(n, np.inf)
    prev_t = np.zeros(n)
    live = np.ones(n, dtype=bool)
    for t in ts:
        idx = np.flatnonzero(live)
        if idx.size == 0:
            break
        p = cam[None, :] + t * dirs[idx]
        zt = sample_height(Z, ox, oy, px_m, p[:, 0], p[:, 1])
        below = p[:, 2] <= zt
        if np.any(below):
            newly = idx[below]
            lo = prev_t[newly].copy()
            hi = np.full(newly.size, t)
            for _ in range(24):               # ~1e-5 m at 8 km; overkill is cheap
                mid = 0.5 * (lo + hi)
                pm = cam[None, :] + mid[:, None] * dirs[newly]
                zm = sample_height(Z, ox, oy, px_m, pm[:, 0], pm[:, 1])
                under = pm[:, 2] <= zm
                hi = np.where(under, mid, hi)
                lo = np.where(under, lo, mid)
            hit[newly] = hi
            live[newly] = False
        prev_t[idx] = t
    return hit


# --------------------------------------------------------------------------
# instances
# --------------------------------------------------------------------------

def load_species(paths, widths_m, heights_m):
    """Load placed instance lists. Returns dict name -> dict with arrays."""
    out = {}
    for name, path in paths.items():
        full = os.path.join(REPO, path)
        if not os.path.isfile(full):
            continue
        d = json.load(open(full, encoding="utf-8"))
        inst = np.asarray(d["instances"], dtype=np.float64)
        out[name] = {
            "xyz_m": inst[:, 0:3] / 100.0,     # plan is cm
            "scale": inst[:, 6],
            "mesh_h_m": heights_m[name],
            "mesh_w_m": widths_m[name],
            "count": int(inst.shape[0]),
            "cull_cm": d.get("cull_cm"),
            "path": path,
        }
    return out


def splat_canopy(species, cam, F, R, U, fov_h_deg, res_w, res_h,
                 terrain_depth, t_max):
    """Rasterise tree silhouettes as cones into a depth buffer.

    Returns (canopy_depth [res_h, res_w] inf where no tree, species_id).
    A cone of base width w and height h covers half its bounding box, which is
    what the triangular half-width ramp below produces."""
    th = math.tan(math.radians(fov_h_deg) / 2.0)
    tv = th * res_h / res_w
    depth = np.full((res_h, res_w), np.inf)
    for name, sp in species.items():
        P = sp["xyz_m"]
        rel = P - cam[None, :]
        d = rel @ F
        keep = (d > 1.0) & (d < t_max)
        if not np.any(keep):
            continue
        rel = rel[keep]; d = d[keep]; sc = sp["scale"][keep]
        h = sp["mesh_h_m"] * sc
        w = sp["mesh_w_m"] * sc
        # screen position of the BASE of the tree, in pixels
        sx = (rel @ R) / (d * th)
        sz = (rel @ U) / (d * tv)
        px = (sx + 1.0) * 0.5 * res_w
        py = (1.0 - sz) * 0.5 * res_h
        # tree extends UPWARD from its base by h; in pixels:
        h_px = h / (2.0 * d * tv) * res_h
        w_px = w / (2.0 * d * th) * res_w
        vis = (h_px > 0.05) & (px > -res_w) & (px < 2 * res_w)
        px = px[vis]; py = py[vis]; h_px = h_px[vis]; w_px = w_px[vis]; dd = d[vis]
        for k in range(px.size):
            top = py[k] - h_px[k]
            bot = py[k]
            j0 = max(0, int(math.floor(top)))
            j1 = min(res_h - 1, int(math.ceil(bot)))
            if j1 < j0:
                continue
            hh = max(bot - top, 1e-6)
            for j in range(j0, j1 + 1):
                frac = (j + 0.5 - top) / hh          # 0 at apex, 1 at base
                if frac < 0.0 or frac > 1.0:
                    continue
                half = 0.5 * w_px[k] * frac
                i0 = max(0, int(math.floor(px[k] - half)))
                i1 = min(res_w - 1, int(math.ceil(px[k] + half)))
                if i1 < i0:
                    continue
                seg = depth[j, i0:i1 + 1]
                np.minimum(seg, dd[k], out=seg)
    return np.minimum(depth, np.inf)


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def evaluate(Z, ox, oy, px_m, species, x_m, y_m, eye_m, yaw, pitch,
             fov_h_deg, res_w, res_h, t_max, band_px=(6.0, 40.0),
             band_species="Conifer", judge_res=(3840, 2160)):
    """Measure one camera. Returns a dict of frame statistics and the bands."""
    ground = float(sample_height(Z, ox, oy, px_m, np.array([x_m]), np.array([y_m]))[0])
    cam = np.array([x_m, y_m, ground + eye_m])
    F, R, U = camera_basis(pitch, yaw)
    dirs = ray_grid(F, R, U, fov_h_deg, res_w, res_h)
    ang = math.radians(fov_h_deg) / judge_res[0]
    terrain = raymarch(Z, ox, oy, px_m, cam, dirs, t_max, ang).reshape(res_h, res_w)
    canopy = splat_canopy(species, cam, F, R, U, fov_h_deg, res_w, res_h,
                          terrain, t_max)

    # nearest surface per pixel, and what it is
    depth = np.minimum(terrain, canopy)
    is_canopy = canopy < terrain
    is_terrain = (terrain < np.inf) & ~is_canopy
    is_sky = ~np.isfinite(depth)
    total = float(res_w * res_h)

    # the pixel band the ladder cares about, converted to a DISTANCE band for
    # the named species, using the verified projection
    sp = species.get(band_species)
    band_m = None
    if sp is not None:
        tv = math.tan(math.radians(fov_h_deg) / 2.0) * judge_res[1] / judge_res[0]
        h_typ = sp["mesh_h_m"] * float(np.median(sp["scale"]))
        far = h_typ * judge_res[1] / (2.0 * band_px[0] * tv)
        near = h_typ * judge_res[1] / (2.0 * band_px[1] * tv)
        band_m = (near, far)

    def pct(mask):
        return round(float(np.count_nonzero(mask)) / total * 100.0, 2)

    near_t = is_terrain & (depth < NEAR_M)
    res = {
        "camera": "%.1f,%.1f,%.1f,%.1f,%.1f,0.0" % (x_m * 100, y_m * 100,
                                                    (ground + eye_m) * 100, pitch, yaw),
        "location_cm": [round(x_m * 100, 1), round(y_m * 100, 1),
                        round((ground + eye_m) * 100, 1)],
        "rotation_deg": [pitch, yaw, 0.0],
        "ground_m": round(ground, 2),
        "eye_m": eye_m,
        "fov_h_deg": fov_h_deg,
        "probe_res": [res_w, res_h],
        "judge_res": list(judge_res),
        "pct_sky": pct(is_sky),
        "pct_terrain": pct(is_terrain),
        "pct_canopy": pct(is_canopy),
        "pct_near_terrain_lt100m": pct(near_t),
        "depth_bands_pct": {
            "near_lt_100m": pct(np.isfinite(depth) & (depth < NEAR_M)),
            "mid_100m_1km": pct(np.isfinite(depth) & (depth >= NEAR_M) & (depth < MID_M)),
            "far_gt_1km": pct(np.isfinite(depth) & (depth >= MID_M)),
            "sky": pct(is_sky),
        },
    }
    # canopy and terrain broken out by distance, which is the record the
    # station choice has to justify itself with
    EDGES = [0.0, 100.0, 300.0, 1000.0, 1500.0, 3000.0, 8000.0, float("inf")]
    hist = {}
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = np.isfinite(depth) & (depth >= lo) & (depth < hi)
        lbl = "%g_%s" % (lo, "inf" if math.isinf(hi) else "%g" % hi)
        hist[lbl] = {"canopy_pct": pct(m & is_canopy),
                     "terrain_pct": pct(m & is_terrain)}
    res["by_distance_m"] = hist

    if band_m:
        inb = is_canopy & (depth >= band_m[0]) & (depth <= band_m[1])
        inband_any = np.isfinite(depth) & (depth >= band_m[0]) & (depth <= band_m[1])
        n_any = float(np.count_nonzero(inband_any))
        res["shape_band"] = {
            "species": band_species,
            "px_band": list(band_px),
            "distance_band_m": [round(band_m[0], 1), round(band_m[1], 1)],
            "typical_placed_height_m": round(h_typ, 3),
            "pct_canopy_in_band": pct(inb),
            "pct_frame_in_band": pct(inband_any),
            "canopy_share_of_band": (round(float(np.count_nonzero(inb)) / n_any * 100.0, 1)
                                     if n_any > 0 else None),
            "_basis": ("distance band derived from the MEASURED typical placed "
                       "height at the judgement resolution, R-ANGBUDGET"),
            "_two_readings": ("pct_canopy_in_band is canopy as a share of the WHOLE "
                              "FRAME; canopy_share_of_band is canopy as a share of "
                              "the frame that lies in the band at all. The first is "
                              "capped by how much frame the terrain puts beyond the "
                              "band's near edge (measured max ~9.4% from a ground "
                              "camera in this world); the second is the one a "
                              "station can actually be judged on."),
        }
    # ridge silhouette: a terrain pixel beyond RIDGE_M with sky directly above
    RIDGE_M = 3000.0
    sky_above = np.vstack([np.ones((1, res_w), dtype=bool), is_sky[:-1, :]])
    ridge = is_terrain & (depth > RIDGE_M) & sky_above
    res["ridge_silhouette"] = {
        "beyond_m": RIDGE_M,
        "pct_of_frame": pct(ridge),
        "columns_with_ridge": int(np.count_nonzero(ridge.any(axis=0))),
        "columns_total": res_w,
    }
    res["max_terrain_depth_m"] = (round(float(np.max(terrain[np.isfinite(terrain)])), 1)
                                  if np.any(np.isfinite(terrain)) else None)
    return res


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------

def march_multi(Z, ox, oy, px_m, origins, dirs, t_max, min_step, max_step,
                ang_res_rad=4.0e-4):
    """Like raymarch but one origin per ray. Coarse: no bisection refinement,
    because this is a PRE-FILTER and its only job is to rank reach."""
    ts = march_schedule(max(min_step, 1.0), t_max, ang_res_rad, min_step, max_step)
    n = origins.shape[0]
    hit = np.full(n, np.inf)
    live = np.ones(n, dtype=bool)
    for t in ts:
        idx = np.flatnonzero(live)
        if idx.size == 0:
            break
        p = origins[idx] + t * dirs[idx]
        zt = sample_height(Z, ox, oy, px_m, p[:, 0], p[:, 1])
        below = p[:, 2] <= zt
        if np.any(below):
            hit[idx[below]] = t
            live[idx[below]] = False
    return hit


def tree_density_grid(species, ox, oy, extent_m, cell_m=100.0):
    """Trees per cell on a coarse grid, for a cheap 'is there forest that way'
    probe along a view axis."""
    n = int(math.ceil(extent_m / cell_m))
    g = np.zeros((n, n), dtype=np.float32)
    for sp in species.values():
        P = sp["xyz_m"]
        ix = ((P[:, 0] - ox) / cell_m).astype(np.int32)
        iy = ((P[:, 1] - oy) / cell_m).astype(np.int32)
        ok = (ix >= 0) & (iy >= 0) & (ix < n) & (iy < n)
        np.add.at(g, (iy[ok], ix[ok]), 1.0)
    return g, cell_m


def density_along(g, cell_m, ox, oy, x, y, yaw_deg, d0, d1, samples=40):
    """Mean trees-per-cell along a view axis between d0 and d1 metres."""
    yr = math.radians(yaw_deg)
    ds = np.linspace(d0, d1, samples)
    xs = x + ds * math.cos(yr)
    ys = y + ds * math.sin(yr)
    ix = ((xs - ox) / cell_m).astype(np.int32)
    iy = ((ys - oy) / cell_m).astype(np.int32)
    n = g.shape[0]
    ok = (ix >= 0) & (iy >= 0) & (ix < n) & (iy < n)
    return float(g[iy[ok], ix[ok]].mean()) if np.any(ok) else 0.0


def scan(Z, ox, oy, px_m, species, profile, eye_m, fov_h, t_max,
         judge_res, band_px, band_species, grid_m, top_n, probe_res,
         elev_range, max_slope_deg, pitch_list, verbose=True):
    """Coarse-to-fine station search. Returns ranked full evaluations."""
    ny, nx = Z.shape
    extent_m = nx * px_m

    # --- coarse terrain + slope, for candidate positions -------------------
    f = max(1, int(round(grid_m / px_m)))
    ncy, ncx = ny // f, nx // f
    Zc = Z[:ncy * f, :ncx * f].reshape(ncy, f, ncx, f).mean(axis=(1, 3))
    gy, gx = np.gradient(Zc.astype(np.float64), grid_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    okpos = ((Zc >= elev_range[0]) & (Zc <= elev_range[1])
             & (slope <= max_slope_deg))
    iy, ix = np.nonzero(okpos)
    if iy.size == 0:
        sys.exit("REFUSE: no candidate position in elevation %s at slope <= %.1f"
                 % (elev_range, max_slope_deg))
    cx = ox + (ix + 0.5) * grid_m
    cy = oy + (iy + 0.5) * grid_m
    cz = Zc[iy, ix] + eye_m
    if verbose:
        print("candidate positions: %d (grid %.0f m, elev %s, slope <= %.0f)"
              % (iy.size, grid_m, elev_range, max_slope_deg))

    # --- cheap forest-in-view probe ---------------------------------------
    dg, dcell = tree_density_grid(species, ox, oy, extent_m)
    tv = math.tan(math.radians(fov_h) / 2.0) * judge_res[1] / judge_res[0]
    sp = species[band_species]
    h_typ = sp["mesh_h_m"] * float(np.median(sp["scale"]))
    band_far = h_typ * judge_res[1] / (2.0 * band_px[0] * tv)
    band_near = h_typ * judge_res[1] / (2.0 * band_px[1] * tv)
    band_far_probe = min(band_far, t_max * 0.6)
    if verbose:
        print("shape band for %s (%.2f m typical placed): %.0f m - %.0f m"
              % (band_species, h_typ, band_near, band_far))

    # --- openness pre-filter over yaws ------------------------------------
    yaws = np.arange(0, 360, 15.0)
    pairs = []
    origins = np.stack([cx, cy, cz], axis=1)
    for yaw in yaws:
        yr = math.radians(yaw)
        for pitch in pitch_list:
            pr = math.radians(pitch)
            d = np.tile(np.array([math.cos(pr) * math.cos(yr),
                                  math.cos(pr) * math.sin(yr),
                                  math.sin(pr)]), (origins.shape[0], 1))
            reach = march_multi(Z, ox, oy, px_m, origins, d, t_max, 6.0, 40.0)
            reach = np.where(np.isinf(reach), t_max, reach)
            for k in np.flatnonzero(reach >= band_near):
                dens = density_along(dg, dcell, ox, oy, cx[k], cy[k], yaw,
                                     band_near, min(band_far_probe, reach[k]))
                if dens <= 0.0 and profile == "mid_slope":
                    continue
                pairs.append((float(reach[k]) * (1.0 + dens), float(cx[k]),
                              float(cy[k]), float(yaw), float(pitch),
                              float(reach[k]), dens))
        if verbose:
            print("  yaw %5.1f -> %d viable pairs so far" % (yaw, len(pairs)))
    if not pairs:
        sys.exit("REFUSE: no candidate reached the shape band; loosen the search")
    pairs.sort(key=lambda t: -t[0])

    # keep the best yaw per position so the shortlist is not one hill twelve times
    seen, short = set(), []
    for p in pairs:
        key = (round(p[1] / 400.0), round(p[2] / 400.0))
        if key in seen:
            continue
        seen.add(key)
        short.append(p)
        if len(short) >= top_n:
            break
    if verbose:
        print("shortlist: %d positions -> full evaluation" % len(short))

    out = []
    for i, (_s, x, y, yaw, pitch, reach, dens) in enumerate(short):
        r = evaluate(Z, ox, oy, px_m, species, x, y, eye_m, yaw, pitch,
                     fov_h, probe_res[0], probe_res[1], t_max,
                     tuple(band_px), band_species, tuple(judge_res))
        r["_scan"] = {"coarse_reach_m": round(reach, 1),
                      "coarse_forest_density": round(dens, 2)}
        out.append(r)
        if verbose:
            sb = r.get("shape_band", {}).get("pct_canopy_in_band", 0.0)
            print("  [%2d/%2d] %9.0f,%-9.0f yaw %6.1f pitch %5.1f | "
                  "band %5.2f%% sky %5.1f%% near %5.1f%% far %5.1f%% ridge %4.1f%%"
                  % (i + 1, len(short), x * 100, y * 100, yaw, pitch, sb,
                     r["pct_sky"], r["pct_near_terrain_lt100m"],
                     r["depth_bands_pct"]["far_gt_1km"],
                     r["ridge_silhouette"]["pct_of_frame"]))
    return out


def judge(r, profile):
    """Apply the declared requirement. Returns (verdict, [reasons])."""
    fails = []
    if profile == "mid_slope":
        sb = r.get("shape_band", {}).get("pct_canopy_in_band", 0.0)
        if sb < 30.0:
            fails.append("canopy in shape band %.2f%% < 30%%" % sb)
        if r["pct_sky"] < 2.0:
            fails.append("sky %.2f%% < 2%% (no sky visible)" % r["pct_sky"])
        if r["pct_near_terrain_lt100m"] > 40.0:
            fails.append("near terrain %.1f%% > 40%% (pressed against a surface)"
                         % r["pct_near_terrain_lt100m"])
    elif profile == "vista":
        mid = r["depth_bands_pct"]["mid_100m_1km"]
        far = r["depth_bands_pct"]["far_gt_1km"]
        if far < 10.0:
            fails.append("far band (>1 km) %.2f%% < 10%%" % far)
        if r["ridge_silhouette"]["columns_with_ridge"] < 0.25 * r["probe_res"][0]:
            fails.append("ridge silhouette in %d of %d columns, want >= 25%%"
                         % (r["ridge_silhouette"]["columns_with_ridge"],
                            r["probe_res"][0]))
        if r["pct_sky"] < 5.0:
            fails.append("sky %.2f%% < 5%%" % r["pct_sky"])
        if r["pct_near_terrain_lt100m"] > 40.0:
            fails.append("near terrain %.1f%% > 40%%" % r["pct_near_terrain_lt100m"])
        _ = mid
    return ("PASS" if not fails else "FAIL"), fails


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %-58s %s" % (label, "PASS" if cond else "FAIL"))

    print("camera basis")
    F, R, U = camera_basis(0.0, 0.0)
    check("pitch 0 yaw 0 -> forward +X", np.allclose(F, [1, 0, 0]))
    check("pitch 0 yaw 0 -> up +Z", np.allclose(U, [0, 0, 1], atol=1e-9))
    F, _, _ = camera_basis(-90.0, 0.0)
    check("pitch -90 -> forward straight DOWN", np.allclose(F, [0, 0, -1], atol=1e-9))
    F, _, _ = camera_basis(0.0, 90.0)
    check("yaw 90 -> forward +Y", np.allclose(F, [0, 1, 0], atol=1e-9))

    print("flat terrain, known answers")
    # 2 km square of dead-flat ground at z=0, 1 m cells
    n = 2000
    Z = np.zeros((n, n), dtype=np.float32)
    ox = oy = 0.0
    px = 1.0
    cam_x = cam_y = 1000.0
    # Looking level from 1.75 m over flat ground: the horizon is at the centre
    # row, so the LOWER half of frame is terrain and the UPPER half is sky.
    r = evaluate(Z, ox, oy, px, {}, cam_x, cam_y, 1.75, 0.0, 0.0,
                 90.0, 96, 54, 3000.0)
    check("flat ground, level camera -> sky within 2%% of 50%% (%.1f)" % r["pct_sky"],
          abs(r["pct_sky"] - 50.0) < 2.0)
    check("flat ground -> no ridge silhouette beyond 3 km",
          r["ridge_silhouette"]["pct_of_frame"] == 0.0)

    # Straight down at flat ground: every pixel is terrain, none is sky.
    r = evaluate(Z, ox, oy, px, {}, cam_x, cam_y, 1.75, 0.0, -90.0,
                 90.0, 48, 27, 3000.0)
    check("looking straight down -> 0%% sky (%.1f)" % r["pct_sky"], r["pct_sky"] == 0.0)
    check("looking straight down -> near band is everything (%.1f)"
          % r["depth_bands_pct"]["near_lt_100m"],
          r["depth_bands_pct"]["near_lt_100m"] > 99.0)

    # Straight up: nothing but sky.
    r = evaluate(Z, ox, oy, px, {}, cam_x, cam_y, 1.75, 0.0, 89.0,
                 90.0, 48, 27, 3000.0)
    check("looking straight up -> 100%% sky (%.1f)" % r["pct_sky"], r["pct_sky"] == 100.0)

    print("a wall in the way -- the defect this tool exists to catch")
    Zw = np.zeros((n, n), dtype=np.float32)
    Zw[:, 1010:1015] = 200.0        # a 200 m wall 10 m in front, spanning the view
    r = evaluate(Zw, ox, oy, px, {}, cam_x, cam_y, 1.75, 0.0, 0.0, 90.0, 96, 54, 3000.0)
    check("wall at 10 m -> near-terrain over 40%% (%.1f)"
          % r["pct_near_terrain_lt100m"], r["pct_near_terrain_lt100m"] > 40.0)
    check("wall at 10 m -> nothing in the far band (%.1f)"
          % r["depth_bands_pct"]["far_gt_1km"],
          r["depth_bands_pct"]["far_gt_1km"] < 1.0)

    print("canopy projection agrees with angular_budget's pixel formula")
    sp = {"T": {"xyz_m": np.array([[1500.0, 1000.0, 0.0]]), "scale": np.array([1.0]),
                "mesh_h_m": 20.0, "mesh_w_m": 6.0, "count": 1,
                "cull_cm": None, "path": "synthetic"}}
    RW, RH = 400, 225
    F, R, U = camera_basis(0.0, 0.0)
    cam = np.array([cam_x, cam_y, 1.75])
    dep = splat_canopy(sp, cam, F, R, U, 90.0, RW, RH, np.full((RH, RW), np.inf), 3000.0)
    got = int(np.count_nonzero(np.isfinite(dep).any(axis=1)))
    tv = math.tan(math.radians(45.0)) * RH / RW
    want = 20.0 / (2.0 * 500.0 * tv) * RH
    check("tree 20 m at 500 m spans %.1f rows, formula says %.1f" % (got, want),
          abs(got - want) <= 2.0)

    print()
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

SPECIES_PATHS = {
    "Conifer": "foliage/alpine_8k_Conifer.json",
    "ConiferPine": "foliage/alpine_8k_ConiferPine.json",
    "SpruceSub": "foliage/alpine_8k_SpruceSub.json",
    "SpruceSapling": "foliage/alpine_8k_SpruceSapling.json",
}
# Heights: SOURCE_MODEL where known, else the measured render bound.
# Widths: measured extents. Both cited in _verify/bench/2026-09-05/species_heights.json
SPECIES_H = {"Conifer": 27.317, "ConiferPine": 22.10,
             "SpruceSub": 16.725, "SpruceSapling": 4.529}
SPECIES_W = {"Conifer": 10.369, "ConiferPine": 8.52,
             "SpruceSub": 4.012, "SpruceSapling": 3.827}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--evaluate", nargs=4, type=float,
                    metavar=("X_CM", "Y_CM", "YAW", "PITCH"))
    ap.add_argument("--eye-m", type=float, default=1.75)
    ap.add_argument("--fov-h", type=float, default=90.0)
    ap.add_argument("--probe-res", nargs=2, type=int, default=[240, 135])
    ap.add_argument("--judge-res", nargs=2, type=int, default=[3840, 2160])
    ap.add_argument("--t-max", type=float, default=9000.0)
    ap.add_argument("--band-species", default="Conifer")
    ap.add_argument("--band-px", nargs=2, type=float, default=[6.0, 40.0])
    ap.add_argument("--no-foliage", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--profile", choices=["mid_slope", "vista"])
    ap.add_argument("--grid-m", type=float, default=200.0)
    ap.add_argument("--top-n", type=int, default=24)
    ap.add_argument("--elev-range", nargs=2, type=float)
    ap.add_argument("--max-slope-deg", type=float, default=22.0)
    ap.add_argument("--pitch-list", nargs="+", type=float)
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    Z, ox, oy, px_m = load_terrain(os.path.join(REPO, a.recipe))
    species = {} if a.no_foliage else load_species(SPECIES_PATHS, SPECIES_W, SPECIES_H)

    if a.scan:
        if not a.profile:
            ap.error("--scan needs --profile")
        elev = a.elev_range or ({"mid_slope": [120.0, 900.0],
                                 "vista": [500.0, 1600.0]}[a.profile])
        pitches = a.pitch_list or ({"mid_slope": [-2.0, 0.0],
                                    "vista": [-4.0, -8.0]}[a.profile])
        res = scan(Z, ox, oy, px_m, species, a.profile, a.eye_m, a.fov_h,
                   a.t_max, tuple(a.judge_res), tuple(a.band_px),
                   a.band_species, a.grid_m, a.top_n, tuple(a.probe_res),
                   elev, a.max_slope_deg, pitches)
        for r in res:
            r["verdict"], r["fails"] = judge(r, a.profile)
        key = ((lambda r: -r.get("shape_band", {}).get("pct_canopy_in_band", 0.0))
               if a.profile == "mid_slope"
               else (lambda r: -(r["depth_bands_pct"]["far_gt_1km"]
                                 + r["ridge_silhouette"]["pct_of_frame"])))
        res.sort(key=key)
        rep = {"profile": a.profile, "requirement_source": "operator ruling 2026-09-05",
               "elev_range_m": elev, "pitches": pitches, "grid_m": a.grid_m,
               "candidates": res}
        if a.out:
            open(os.path.join(REPO, a.out), "w", encoding="utf-8").write(
                json.dumps(rep, indent=1))
        print()
        print("RANKED (%s)" % a.profile)
        for r in res[:12]:
            print("  %-7s %s | band %5.2f%% sky %5.1f%% near %5.1f%% far %5.1f%% "
                  "ridge %4.1f%% (%d cols)"
                  % (r["verdict"], r["camera"],
                     r.get("shape_band", {}).get("pct_canopy_in_band", 0.0),
                     r["pct_sky"], r["pct_near_terrain_lt100m"],
                     r["depth_bands_pct"]["far_gt_1km"],
                     r["ridge_silhouette"]["pct_of_frame"],
                     r["ridge_silhouette"]["columns_with_ridge"]))
            if r["fails"]:
                print("            fails: %s" % "; ".join(r["fails"]))
        return 0

    if a.evaluate:
        x_cm, y_cm, yaw, pitch = a.evaluate
        r = evaluate(Z, ox, oy, px_m, species, x_cm / 100.0, y_cm / 100.0,
                     a.eye_m, yaw, pitch, a.fov_h, a.probe_res[0], a.probe_res[1],
                     a.t_max, tuple(a.band_px), a.band_species, tuple(a.judge_res))
        js = json.dumps(r, indent=1)
        if a.out:
            open(os.path.join(REPO, a.out), "w", encoding="utf-8").write(js)
        print(js)
        return 0

    ap.error("give --selftest or --evaluate")


if __name__ == "__main__":
    sys.exit(main())
