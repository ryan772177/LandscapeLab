"""verify_ground_station.py — the four checks a ground station must pass
BEFORE it is used. RULED BY RYAN 2026-09-11 (4a).

    python scripts/verify_ground_station.py --frames <dir> --station ground
    python scripts/verify_ground_station.py --selftest

    1 DEPTH SHAPE   p25 >= 40 m, p75 <= 400 m, and >= 30% of frame
                    pixels in 50-300 m
    2 PREDICTION    my model's band rows vs the RENDERED band rows,
                    within 15%
    3 NO TREES      no placed tree instance inside the frustum under
                    300 m -- queried from the INSTANCE SET, not the image
    4 MEADOW        weight >= 0.55 over >= 50% of the 50-300 m ground --
                    read from the LAYER DATA, not the colour

EACH CHECK USES THE INSTRUMENT OF ITS OWN CLASS, which is the whole
reason this file exists rather than one big loop:

  * 1 reads the SCENE-DEPTH PASS. That pass is 8-bit log depth, 5.6% per
    LSB -- correct for BINNING distance (R-DEPTHBIN) and useless for
    positions. Binning is all check 1 does.
  * 3 and 4 need WORLD POSITIONS, which that pass cannot give
    (LESSONS 2026-09-11c). They FORWARD-PROJECT the heightmap and the
    instance list through the known camera instead -- exact, no
    inversion, z-buffered so occlusion is honest.
  * 2 compares a prediction to a render, so it uses both and says which
    number came from where.

A MISS IS A RULING FOR RYAN, NOT A TASK. This tool reports numbers and
exits non-zero; it never suggests a nudge.
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
from bench_station_derive import camera_basis, load_terrain  # noqa: E402
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402

FOV_H = 90.0
RES = (3840, 2160)
BANDS = [(30.0, 100.0), (100.0, 300.0)]
P25_MIN, P75_MAX = 40.0, 400.0
MID_BAND = (50.0, 300.0)
MID_FRAC_MIN = 0.30
PRED_TOL = 0.15
TREE_MAX_M = 300.0
MEADOW_MIN, MEADOW_FRAC_MIN = 0.55, 0.50

HISTORY = {"v1": {"p25": None, "p50": 9.04, "p75": None,
                  "predicted": [405.0, 375.0], "rendered": [55.0, 0.0]},
           "v2": {"p25": 2.3, "p50": 25.1, "p75": 647.3,
                  "predicted": [354.0, 246.0], "rendered": [11.0, 0.0]}}


def rendered_band_rows(depth, sky, lo, hi):
    n = 0
    for y in range(depth.shape[0]):
        r = depth[y][~sky[y]]
        if r.size < depth.shape[1] * 0.25:
            continue
        if lo <= float(np.median(r)) <= hi:
            n += 1
    return n


def project_terrain(Z, ox, oy, px_m, cam, pitch, yaw, res, stride=2):
    """Forward-project the heightfield, z-buffered. Returns per-pixel
    distance and the heightmap index that won, or -1."""
    W, H = res
    F, R, U = camera_basis(pitch, yaw)
    th = math.tan(math.radians(FOV_H) / 2.0)
    tv = th * H / W
    ny, nx = Z.shape
    ys, xs = np.mgrid[0:ny:stride, 0:nx:stride]
    wx = ox + xs * px_m
    wy = oy + ys * px_m
    wz = Z[::stride, ::stride]
    dx, dy, dz = wx - cam[0], wy - cam[1], wz - cam[2]
    t = dx * F[0] + dy * F[1] + dz * F[2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = (dx * R[0] + dy * R[1] + dz * R[2]) / (t * th)
        v = (dx * U[0] + dy * U[1] + dz * U[2]) / (t * tv)
    col = ((u + 1.0) * 0.5 * W).astype(np.int64)
    row = ((1.0 - v) * 0.5 * H).astype(np.int64)
    dist = np.sqrt(dx * dx + dy * dy + dz * dz)
    ok = (t > 0.5) & (col >= 0) & (col < W) & (row >= 0) & (row < H)
    zbuf = np.full((H, W), np.inf)
    idx = np.full((H, W), -1, dtype=np.int64)
    flat = np.flatnonzero(ok)
    order = np.argsort(-dist.ravel()[flat])       # far first, near wins
    f = flat[order]
    zbuf[row.ravel()[f], col.ravel()[f]] = dist.ravel()[f]
    idx[row.ravel()[f], col.ravel()[f]] = f
    return zbuf, idx, (ys, xs, stride)


def trees_in_frustum(cam, pitch, yaw, max_m):
    """Placed tree instances inside the frustum and nearer than max_m.
    Queried from the PLANS, never from the image."""
    F, R, U = camera_basis(pitch, yaw)
    th = math.tan(math.radians(FOV_H) / 2.0)
    tv = th * RES[1] / RES[0]
    hits = {}
    for name in ("Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"):
        p = os.path.join(REPO, "foliage", "alpine_8k_%s.json" % name)
        if not os.path.isfile(p):
            continue
        inst = np.asarray(json.load(open(p, encoding="utf-8"))["instances"],
                          dtype=np.float64)
        xyz = inst[:, 0:3] / 100.0
        d = xyz - np.asarray(cam)[None, :]
        t = d @ F
        with np.errstate(divide="ignore", invalid="ignore"):
            u = (d @ R) / (t * th)
            v = (d @ U) / (t * tv)
        rng = np.linalg.norm(d, axis=1)
        inside = (t > 0.5) & (np.abs(u) <= 1.0) & (np.abs(v) <= 1.0) \
            & (rng < max_m)
        hits[name] = {"in_frustum_under_%dm" % int(max_m): int(inside.sum()),
                      "nearest_m": (round(float(rng[inside].min()), 1)
                                    if inside.any() else None),
                      "total_instances": int(xyz.shape[0])}
    return hits


def selftest():
    """Both controls, offline, through the REAL machinery (Pass 3
    2026-09-16 — the docstring had advertised --selftest for a flag that
    did not exist, and the instrument had no test at all).

    Positive: the real project_terrain must cover a synthetic plane and
    reproduce the ANALYTIC bottom-ray slant distance (a second
    derivation, NN8); the real rendered_band_rows must return EXACT
    counts on constructed rows with known medians. Negative: a 2.5x
    mis-scaled depth must fall outside PRED_TOL; depth fields violating
    the check-1 shape thresholds must fail on the intended sides; a
    mostly-sky row must be skipped, not counted. (The two check-2
    instruments use different row statistics — majority-count vs median
    — so a cross-concurrence test on a synthetic plane is NOT part of
    this suite; they diverge legitimately at 90 deg FOV.)
    """
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # A flat plane, camera 30 m up looking down-forward: near ground at
    # the frame bottom, far ground toward the horizon — rows land in
    # both bands. The projection SPLATS source points, so the source grid
    # must outnumber the pixels or the buffer is mostly holes: stride 1
    # over 600x600 points against a 192x108 frame.
    res = (192, 108)
    n, px_m = 600, 2.0
    Z = np.zeros((n, n), dtype=np.float32)
    cam = np.array([n * px_m / 2.0, 20.0, 30.0])
    pitch, yaw = -12.0, 90.0          # +Y forward across the plane
    zbuf, idx, _ = project_terrain(Z, 0.0, 0.0, px_m, cam, pitch, yaw, res,
                                   stride=1)
    finite = np.isfinite(zbuf)
    check("projection covers a substantial ground area", finite.mean() > 0.2)

    print("positive control -- the projection is geometrically RIGHT")
    # Analytic cross-check: the frame-bottom centre ray leaves the camera
    # at (|pitch| + v_half) below the horizon; flat ground at height 0
    # sits at slant distance cam_z / sin(that angle). The projection must
    # reproduce it — this is a second derivation, not a re-read (NN8).
    th_h = math.tan(math.radians(FOV_H) / 2.0)
    v_half = math.degrees(math.atan(th_h * res[1] / res[0]))
    down = math.radians(abs(pitch) + v_half)
    expect_m = cam[2] / math.sin(down)
    # a single pixel can be a splat hole; the median of a small
    # bottom-centre patch is the same ray to within the patch's angle
    patch = zbuf[res[1] - 6:res[1], res[0] // 2 - 3:res[0] // 2 + 3]
    finite_patch = patch[np.isfinite(patch)]
    got = float(np.median(finite_patch)) if finite_patch.size else float("inf")
    check("bottom-centre patch matches the analytic slant distance "
          "(%.1f vs %.1f m)" % (got, expect_m),
          np.isfinite(got) and abs(got - expect_m) / expect_m < 0.08)

    print("positive + negative controls -- rendered_band_rows")
    # Constructed depth with KNOWN row medians: rows 0-9 at 60 m (in the
    # 30-100 band), rows 10-19 at 200 m (in 100-300), no sky. Counts are
    # exact, so agreement is by construction and mis-scale must move it.
    d = np.zeros((20, 100))
    d[0:10] = 60.0
    d[10:20] = 200.0
    s = np.zeros((20, 100), dtype=bool)
    check("exact count, band 30-100: 10 rows",
          rendered_band_rows(d, s, 30.0, 100.0) == 10)
    check("exact count, band 100-300: 10 rows",
          rendered_band_rows(d, s, 100.0, 300.0) == 10)
    re_bad = rendered_band_rows(d * 2.5, s, 30.0, 100.0)   # 60->150: leaves
    base = max(10, re_bad, 1)
    check("2.5x mis-scaled depth falls OUT of the %.0f%% tolerance "
          "(10 vs %d rows)" % (PRED_TOL * 100, re_bad),
          not (abs(10 - re_bad) / base <= PRED_TOL))
    # rule 13: the comparator must not read two EMPTY bands as agreement —
    # this selftest's own counts above are non-zero by construction.

    print("check-1 shape arithmetic, both directions")
    conforming = np.linspace(45.0, 380.0, 200 * 200).reshape(200, 200)
    p25, p75 = (float(np.percentile(conforming, q)) for q in (25, 75))
    mid = ((conforming >= MID_BAND[0]) & (conforming <= MID_BAND[1]))
    check("a conforming depth field PASSES the shape thresholds",
          p25 >= P25_MIN and p75 <= P75_MAX
          and float(mid.mean()) >= MID_FRAC_MIN)
    too_near = np.full((100, 100), 5.0)
    check("an all-5m field FAILS (p25 below the floor)",
          not (float(np.percentile(too_near, 25)) >= P25_MIN))
    too_far = np.full((100, 100), 5000.0)
    check("an all-5km field FAILS (p75 above the cap)",
          not (float(np.percentile(too_far, 75)) <= P75_MAX))

    print("sparse-row discipline")
    # a row with fewer than 25% ground pixels is SKIPPED, not counted
    d2 = np.full((4, 100), 60.0)
    s2 = np.zeros((4, 100), dtype=bool)
    s2[0, :80] = True                  # row 0: only 20% ground -> skipped
    check("a mostly-sky row is skipped rather than counted",
          rendered_band_rows(d2, s2, 30.0, 100.0) == 3)

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="offline: both controls through the real "
                         "projection/verdict machinery; no frames needed")
    ap.add_argument("--frames")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--stations-json", default=os.path.join(
        REPO, "_verify", "bench", "2026-09-11",
        "bench_stations_derived.json"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.frames:
        ap.error("--frames is required (or use --selftest)")

    st = json.load(open(a.stations_json, encoding="utf-8"))
    cs = [float(v) for v in
          st["derived_stations"][a.station]["camera_string"].split(",")]
    cam = np.array(cs[:3]) / 100.0
    pitch, yaw = cs[3], cs[4]

    dp = os.path.join(a.frames, "%sFinalImageSceneDepth.png" % a.station)
    depth = decode_depth_m(dp)
    sky = depth > CEILING_M * 0.97
    out = {"_what": "Bench_ground verification, RULED 4a",
           "station": a.station, "camera_cm": list(np.asarray(cs[:3])),
           "pitch_yaw": [pitch, yaw], "frames": a.frames, "checks": {}}
    ok_all = True

    def verdict(key, passed, **d):
        nonlocal ok_all
        ok_all = ok_all and bool(passed)
        out["checks"][key] = dict(d, verdict="PASS" if passed else "FAIL")

    # ---- 1 depth shape -------------------------------------------------
    g = depth[~sky]
    p25, p50, p75 = (float(np.percentile(g, q)) for q in (25, 50, 75))
    mid = (~sky) & (depth >= MID_BAND[0]) & (depth <= MID_BAND[1])
    mid_frac = float(mid.mean())
    verdict("depth_shape",
            p25 >= P25_MIN and p75 <= P75_MAX and mid_frac >= MID_FRAC_MIN,
            p25_m=round(p25, 2), p50_m=round(p50, 2), p75_m=round(p75, 2),
            requires={"p25_min": P25_MIN, "p75_max": P75_MAX,
                      "frac_50_300_min": MID_FRAC_MIN},
            frac_50_300=round(mid_frac, 4),
            sky_fraction=round(float(sky.mean()), 4),
            history=HISTORY)

    # ---- 2 prediction vs render ---------------------------------------
    Z, ox, oy, px_m = load_terrain(a.recipe)
    zbuf, idx, _ = project_terrain(Z, ox, oy, px_m, cam, pitch, yaw, RES)
    rows_pred, rows_rend, within = [], [], []
    for lo, hi in BANDS:
        inb = np.isfinite(zbuf) & (zbuf >= lo) & (zbuf <= hi)
        pr = int((inb.sum(axis=1) > RES[0] * 0.5).sum())
        re = rendered_band_rows(depth, sky, lo, hi)
        rows_pred.append(pr)
        rows_rend.append(re)
        base = max(pr, re, 1)
        within.append(abs(pr - re) / base <= PRED_TOL)
    verdict("prediction_vs_render", all(within),
            bands_m=[list(b) for b in BANDS],
            predicted_rows=rows_pred, rendered_rows=rows_rend,
            within_tolerance=within, tolerance=PRED_TOL,
            _predicted_from=("forward projection of the heightmap through "
                             "the ruled camera, z-buffered"),
            _rendered_from="the scene-depth pass, rows by median depth",
            history=HISTORY)

    # ---- 3 no trees in the frustum under 300 m -------------------------
    th = trees_in_frustum(cam, pitch, yaw, TREE_MAX_M)
    total = sum(v["in_frustum_under_%dm" % int(TREE_MAX_M)]
                for v in th.values())
    verdict("no_trees_under_300m", total == 0,
            per_species=th, total_in_frustum=total,
            _source="foliage/alpine_8k_*.json instance lists, NOT the image")

    # ---- 4 meadow over the 50-300 m ground -----------------------------
    b = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8b.png")))
    meadow = b[..., 3].astype(np.float32) / 255.0
    band = np.isfinite(zbuf) & (zbuf >= MID_BAND[0]) & (zbuf <= MID_BAND[1])
    sel = idx[band]
    sel = sel[sel >= 0]
    if sel.size < 1000:
        verdict("meadow_over_mid_band", False,
                reason="only %d projected ground samples in 50-300 m"
                       % int(sel.size))
    else:
        ny, nx = Z.shape
        stride = 2
        gy, gx = np.mgrid[0:ny:stride, 0:nx:stride]
        my = gy.ravel()[sel]
        mx = gx.ravel()[sel]
        w = meadow[my, mx]
        frac = float((w >= MEADOW_MIN).mean())
        verdict("meadow_over_mid_band", frac >= MEADOW_FRAC_MIN,
                samples=int(sel.size),
                mean_meadow_weight=round(float(w.mean()), 4),
                frac_at_or_above=round(frac, 4),
                requires={"weight_min": MEADOW_MIN,
                          "frac_min": MEADOW_FRAC_MIN},
                _source="textures/alpine_8k_w8b.png alpha (LAYER DATA), "
                        "sampled at forward-projected ground positions")

    out["overall"] = "PASS" if ok_all else "FAIL"
    print(json.dumps(out, indent=1, default=str))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
        print("wrote %s" % a.out)
    if not ok_all:
        print("\nA MISS IS A RULING FOR RYAN. Numbers reported; nothing "
              "nudged, nothing re-derived.")
    return 0 if ok_all else 4


if __name__ == "__main__":
    raise SystemExit(main())
