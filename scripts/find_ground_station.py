"""find_ground_station.py — search for a ground station ON THE RULED
ACCEPTANCE STATISTICS THEMSELVES, not on a proxy for them.

    python scripts/find_ground_station.py [--top 5] [--out J]
    python scripts/find_ground_station.py --selftest

WHY A THIRD TOOL. Two earlier searches scored a PROXY -- "band rows" from
a coarse forward projection -- and both winners collapsed against the
render (405/375 -> 55/0, then 354/246 -> 11/0). `verify_ground_station`
now defines exactly what a station must satisfy, so this searches for
THOSE NUMBERS and nothing else.

THE BINDING CONSTRAINT IS GEOMETRIC, AND IT RULES OUT MOST OF THE WORLD.
At pitch 0 with a 1.7 m eye, ground at 50-300 m lies between 1.95 deg and
0.32 deg below the horizon: **1.62 deg of a 58.72 deg frame = 2.76%**.
The ruled floor is 30%. On flat ground that is not hard, it is
IMPOSSIBLE -- no yaw and no luck can help. 30% needs the band to subtend
17.6 deg, which means ground about 80 m ABOVE the camera at 300 m, an
opposing slope of ~15 deg. So the station is "stand low, look at a wall",
and that is what the prefilter looks for.

TWO STAGES, cheap then honest:
  A PROFILE PREFILTER  sample the terrain along the azimuth at 50-300 m
    and compute the ELEVATION SPAN of that segment from the camera. No
    raymarch. Rejects the flat world in one pass.
  B RAYMARCH           survivors get a real per-pixel depth image, from
    which the SAME statistics verify_ground_station measures are
    computed. Raymarch, not forward projection: a marched image has one
    depth per pixel and no holes, which is what the depth pass has.
    Forward projection at stride 2 under-samples at range and reported
    0 rows where the render found 174 (LESSONS 2026-09-11r).

THIS TOOL DOES NOT BLESS A STATION. Its output is a CANDIDATE; the
station is whatever survives `verify_ground_station` against a real
capture.
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
from bench_station_derive import (camera_basis, load_terrain,  # noqa: E402
                                  ray_grid, raymarch, sample_height)

EYE_M = 1.7
FOV_H = 90.0
FULL = (3840, 2160)
MARCH_RES = (320, 180)
MID = (50.0, 300.0)
MID_FRAC_MIN = 0.30
P25_MIN, P75_MAX = 40.0, 400.0
MEADOW_MIN, MEADOW_FRAC_MIN = 0.55, 0.50
TREE_MAX_M = 300.0
SPAN_MIN_DEG = 14.0          # prefilter: below this, 30% is unreachable
T_MAX_M = 1200.0


def _meadow():
    b = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8b.png")))
    return b[..., 3].astype(np.float32) / 255.0


def _trees():
    out = []
    for name in ("Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"):
        p = os.path.join(REPO, "foliage", "alpine_8k_%s.json" % name)
        if os.path.isfile(p):
            inst = np.asarray(json.load(open(p, encoding="utf-8"))["instances"],
                              dtype=np.float64)
            out.append(inst[:, 0:3] / 100.0)
    return np.vstack(out) if out else np.zeros((0, 3))


def elevation_span(Z, ox, oy, px_m, cam, yaw, n=24, meadow=None, ox0=None,
                   oy0=None):
    """Elevation angle of the terrain along the azimuth, 50..300 m, and
    the MEADOW WEIGHT along that same line.

    ⛔ THE MEADOW TEST BELONGS ON THE VIEW, NOT THE CAMERA. The first run
    required meadow only at the camera cell and every surviving candidate
    came back with meadow_frac 0.002-0.03: the sites that fill the mid
    band do it by facing a wall, and the WALL is rock. What check 4
    measures is the ground at 50-300 m, so that is what gets filtered.
    """
    d = np.linspace(MID[0], MID[1], n)
    ux, uy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    px = cam[0] + ux * d
    py = cam[1] + uy * d
    h = sample_height(Z, ox, oy, px_m, px, py)
    if not np.isfinite(h).all():
        return None
    ang = np.degrees(np.arctan2(h - cam[2], d))
    mfrac = None
    if meadow is not None:
        cx = np.clip(((px - ox) / px_m).astype(np.int64), 0,
                     meadow.shape[1] - 1)
        cy = np.clip(((py - oy) / px_m).astype(np.int64), 0,
                     meadow.shape[0] - 1)
        mfrac = float((meadow[cy, cx] >= MEADOW_MIN).mean())
    return (float(ang.max() - ang.min()), float(ang.min()), float(ang.max()),
            float(h[-1] - h[0]), mfrac)


def march_stats(Z, ox, oy, px_m, meadow, cam, pitch, yaw, res=MARCH_RES):
    """The statistics verify_ground_station checks, from a marched image."""
    rw, rh = res
    F, R, U = camera_basis(pitch, yaw)
    dirs = ray_grid(F, R, U, FOV_H, rw, rh)
    ang = math.radians(FOV_H) / rw
    hit = raymarch(Z, ox, oy, px_m, cam, dirs, T_MAX_M, ang).reshape(rh, rw)
    sky = ~np.isfinite(hit)
    if sky.all():
        return None
    g = hit[~sky]
    p25, p50, p75 = (float(np.percentile(g, q)) for q in (25, 50, 75))
    mid = (~sky) & (hit >= MID[0]) & (hit <= MID[1])
    frac = float(mid.mean())
    # meadow over the mid band, from the LAYER DATA at the hit points
    mw = None
    if mid.any():
        d3 = dirs.reshape(rh, rw, 3)[mid]
        t = hit[mid][:, None]
        p = cam[None, :] + d3 * t
        cx = np.clip(((p[:, 0] - ox) / px_m).astype(np.int64), 0,
                     Z.shape[1] - 1)
        cy = np.clip(((p[:, 1] - oy) / px_m).astype(np.int64), 0,
                     Z.shape[0] - 1)
        w = meadow[cy, cx]
        mw = (float(w.mean()), float((w >= MEADOW_MIN).mean()))
    return {"p25": p25, "p50": p50, "p75": p75, "frac_mid": frac,
            "sky": float(sky.mean()),
            "meadow_mean": None if mw is None else mw[0],
            "meadow_frac": None if mw is None else mw[1]}


def trees_in_frustum(trees, cam, pitch, yaw):
    F, R, U = camera_basis(pitch, yaw)
    th = math.tan(math.radians(FOV_H) / 2.0)
    tv = th * FULL[1] / FULL[0]
    d = trees - np.asarray(cam)[None, :]
    t = d @ F
    with np.errstate(divide="ignore", invalid="ignore"):
        u = (d @ R) / (t * th)
        v = (d @ U) / (t * tv)
    rng = np.linalg.norm(d, axis=1)
    inside = (t > 0.5) & (np.abs(u) <= 1.0) & (np.abs(v) <= 1.0) \
        & (rng < TREE_MAX_M)
    return int(inside.sum()), (float(rng[inside].min()) if inside.any()
                               else None)


def search(step_m=200.0, yaws=12, pitch=0.0, top=5):
    Z, ox, oy, px_m = load_terrain(os.path.join(REPO, "recipes",
                                                "alpine_8k.json"))
    meadow = _meadow()
    trees = _trees()
    ny, nx = Z.shape
    stride = int(step_m / px_m)
    stats = {"sites": 0, "views": 0, "span_ok": 0, "meadow_site_ok": 0,
             "marched": 0, "tree_reject": 0,
             "meadow_view_reject": 0, "meadow_view_ok": 0}
    cands = []
    for iy in range(stride, ny - stride, stride):
        for ix in range(stride, nx - stride, stride):
            if meadow[iy, ix] < MEADOW_MIN:
                continue
            stats["meadow_site_ok"] += 1
            x_m, y_m = ox + ix * px_m, oy + iy * px_m
            g = float(Z[iy, ix])
            cam = np.array([x_m, y_m, g + EYE_M])
            stats["sites"] += 1
            for k in range(yaws):
                yaw = 360.0 * k / yaws
                stats["views"] += 1
                es = elevation_span(Z, ox, oy, px_m, cam, yaw, meadow=meadow)
                if es is None or es[0] < SPAN_MIN_DEG:
                    continue
                stats["span_ok"] += 1
                if (es[4] or 0.0) < MEADOW_FRAC_MIN:
                    stats["meadow_view_reject"] += 1
                    continue
                stats["meadow_view_ok"] += 1
                nt, nearest = trees_in_frustum(trees, cam, pitch, yaw)
                if nt:
                    stats["tree_reject"] += 1
                    continue
                ms = march_stats(Z, ox, oy, px_m, meadow, cam, pitch, yaw)
                stats["marched"] += 1
                if ms is None:
                    continue
                passes = (ms["p25"] >= P25_MIN and ms["p75"] <= P75_MAX
                          and ms["frac_mid"] >= MID_FRAC_MIN
                          and (ms["meadow_frac"] or 0) >= MEADOW_FRAC_MIN)
                cands.append({"x_cm": round(x_m * 100.0, 1),
                              "y_cm": round(y_m * 100.0, 1),
                              "z_cm": round((g + EYE_M) * 100.0, 1),
                              "yaw": yaw, "pitch": pitch,
                              "ground_z_m": round(g, 2),
                              "elevation_span_deg": round(es[0], 2),
                              "rise_over_band_m": round(es[3], 1),
                              "meadow_frac_along_view": round(es[4] or 0.0, 3),
                              "trees_in_frustum": nt,
                              "nearest_tree_m": nearest,
                              "predicted": {k: (round(v, 4)
                                                if isinstance(v, float)
                                                else v)
                                            for k, v in ms.items()},
                              "all_four_predicted_pass": bool(passes)})
    cands.sort(key=lambda c: (-int(c["all_four_predicted_pass"]),
                              -c["predicted"]["frac_mid"]))
    return cands[:top], stats


def selftest():
    """1 a bowl (low camera, rising far side) clears the span filter and
    a flat plain does not; 2 a tree in the frustum is seen; 3 a camera off
    the map refuses."""
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    n, sp = 900, 2.0
    ox = oy = 0.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    flat = np.full((n, n), 100.0, dtype=np.float32)
    fwd = np.clip((yy - n / 2) * sp, 0, None)
    bowl = (100.0 + fwd * fwd / (2.0 * 520.0)).astype(np.float32)
    cx = cy = n / 2 * sp
    cam = np.array([cx, cy, 100.0 + EYE_M])
    sf = elevation_span(flat, ox, oy, sp, cam, 90.0)
    sb = elevation_span(bowl, ox, oy, sp, np.array([cx, cy, 100.0 + EYE_M]),
                        90.0)
    print("    flat span %.2f deg   bowl span %.2f deg" % (sf[0], sb[0]))
    check("flat ground is REJECTED by the span filter",
          sf[0] < SPAN_MIN_DEG)
    check("a rising far side CLEARS it", sb[0] >= SPAN_MIN_DEG)
    check("...and the flat span matches the analytic 1.62 deg",
          abs(sf[0] - 1.62) < 0.25)

    tr = np.array([[cx, cy + 100.0, 100.0]])
    nt, near = trees_in_frustum(tr, cam, 0.0, 90.0)
    check("a tree 100 m ahead is inside the frustum", nt == 1)
    nt2, _ = trees_in_frustum(tr, cam, 0.0, 270.0)
    check("...and is NOT, looking the other way", nt2 == 0)
    check("a camera off the map refuses",
          elevation_span(flat, ox, oy, sp, np.array([-9e5, -9e5, 0.0]),
                         90.0) is None)
    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step-m", type=float, default=200.0)
    ap.add_argument("--yaws", type=int, default=12)
    ap.add_argument("--pitch", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    cands, stats = search(a.step_m, a.yaws, a.pitch, a.top)
    print("search: %s" % json.dumps(stats))
    if not cands:
        print("NO CANDIDATE clears the geometry. At pitch %.1f the 50-300 m "
              "band cannot reach %.0f%% anywhere this search looked."
              % (a.pitch, 100 * MID_FRAC_MIN))
        return 4
    print("\n%-26s %5s %7s %7s %7s %7s %7s %6s %s"
          % ("x,y,z cm", "yaw", "span", "p25", "p50", "p75", "frac", "meadow",
             "all4"))
    for c in cands:
        p = c["predicted"]
        print("%-26s %5.0f %7.2f %7.1f %7.1f %7.1f %7.3f %6.3f %s"
              % ("%.0f,%.0f,%.0f" % (c["x_cm"], c["y_cm"], c["z_cm"]),
                 c["yaw"], c["elevation_span_deg"], p["p25"], p["p50"],
                 p["p75"], p["frac_mid"], p["meadow_frac"] or 0.0,
                 c["all_four_predicted_pass"]))
    print("\nThese are CANDIDATES. A station is what survives "
          "verify_ground_station against a real capture.")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "ground station candidates, scored on the "
                                "ruled acceptance statistics",
                       "stats": stats, "candidates": cands}, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
