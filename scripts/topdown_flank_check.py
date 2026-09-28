"""topdown_flank_check.py — read snow against the lit/shaded flank in a
TOP-DOWN frame, in screen space, with no depth reconstruction.

    python scripts/topdown_flank_check.py --frame <png> \
        --cam-cm X,Y,Z [--fov 90] [--out J]
    python scripts/topdown_flank_check.py --selftest

WHY SCREEN SPACE AND NOT REPROJECTION.  The scene-depth pass is 8-bit
LOG depth -- 5.6% of distance per LSB, 56 m at 1 km (measured
2026-09-11) -- so positions and normals cannot be recovered from it.
Here nothing is recovered: every heightmap texel is FORWARD-projected
through a known camera, which needs no inversion and no depth pass at
all.  Validated against the landscape's own square edge in the frame.

THE TWO CONFOUNDS, AND HOW EACH IS HELD FIXED.  A top-down frame's
brightness is albedo x illumination x atmosphere, and the last two both
track altitude:

  * ATMOSPHERE.  High ground is nearer the camera, so it is less hazed.
    Snow is also on high ground.  Comparing snow to bare across
    altitudes would measure the haze gradient and call it albedo.
    HELD FIXED by binning: every comparison runs inside one narrow
    altitude bin.
  * ILLUMINATION.  At 12 deg sun elevation the lit flanks are far
    brighter than the shaded ones whatever they are made of.  HELD FIXED
    by comparing snowy against bare WITHIN one flank class.

So the albedo question asked here is: on the SAME flank class, at the
SAME altitude, does high derived snow weight render BRIGHTER than low?
That is the link the offline checks cannot reach -- `hillshade_snow_check`
proves the map puts snow on the shaded flank, and
`heightmap_orientation_check` proves the map is oriented as the engine
imported it, but neither can see whether the MATERIAL samples it.

A frame whose terrain contrast is below `MIN_STD` is reported
NON-PROBATIVE rather than scored: at 9 km the aerial perspective flattens
this world to luma std 0.0206 and no amount of binning recovers a signal
that the 8-bit quantisation has already eaten (R-CITYSHOT step 6).
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
from haze_metrics import srgb_to_linear  # noqa: E402
from hillshade_snow_check import hillshade, sun_vector  # noqa: E402

MIN_STD = 0.05          # terrain luma std below this cannot carry the signal
MIN_BIN_PX = 2000       # per altitude bin, per class
N_ALT_BINS = 5
SHADE_NDL, LIT_NDL = 0.02, 0.5
SNOWY, BARE = 0.5, 0.1


def project(x_m, y_m, h_m, cam_m, fov_h_deg, res):
    """Forward-project world points through a pitch -90, yaw 0 camera.

    forward (0,0,-1), right +Y, up +X -- `camera_basis(-90, 0)`'s own
    values, restated here so the mapping is auditable at the call site.
    Returns (col, row, t) in pixels and metres; t is depth along view."""
    W, H = res
    th = math.tan(math.radians(fov_h_deg) / 2.0)
    tv = th * H / W
    t = cam_m[2] - h_m
    with np.errstate(divide="ignore", invalid="ignore"):
        u = (y_m - cam_m[1]) / (t * th)
        v = (x_m - cam_m[0]) / (t * tv)
    return (u + 1.0) * 0.5 * W, (1.0 - v) * 0.5 * H, t


def measure(frame, h_m, snow_w, spacing_m, ox, oy, cam_m, L, fov_h_deg,
            snow_base_m, swing_m, stride=2):
    lin = srgb_to_linear(np.asarray(frame.convert("RGB")).astype(np.float64)
                         / 255.0)
    lum = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    H, W = lum.shape
    ndl, slope = hillshade(h_m, spacing_m, L)

    ny, nx = h_m.shape
    ys, xs = np.mgrid[0:ny:stride, 0:nx:stride]
    hx = ox + xs * spacing_m
    hy = oy + ys * spacing_m
    hh = h_m[::stride, ::stride]
    col, row, t = project(hx, hy, hh, cam_m, fov_h_deg, (W, H))
    ci = np.round(col).astype(np.int64)
    ri = np.round(row).astype(np.int64)
    on = (ci >= 0) & (ci < W) & (ri >= 0) & (ri < H) & (t > 1.0)
    if on.sum() < 10000:
        return {"error": "only %d texels project into the frame" % int(on.sum())}

    px = np.full(hh.shape, np.nan)
    px[on] = lum[ri[on], ci[on]]
    terr_std = float(np.nanstd(px))
    out = {"texels_in_frame": int(on.sum()),
           "terrain_luma_mean": round(float(np.nanmean(px)), 5),
           "terrain_luma_std": round(terr_std, 5),
           "min_std_required": MIN_STD}
    if terr_std < MIN_STD:
        out["verdict"] = "NON-PROBATIVE"
        out["why"] = ("terrain luma std %.4f < %.2f -- aerial perspective has "
                      "flattened the frame below what 8-bit quantisation can "
                      "carry, so no binning recovers the albedo signal"
                      % (terr_std, MIN_STD))
        return out

    sl = slope[::stride, ::stride]
    nd = ndl[::stride, ::stride]
    sw = snow_w[::stride, ::stride]
    band = (on & (hh > snow_base_m - swing_m) & (hh < snow_base_m + swing_m)
            & (sl > 10.0))
    edges = np.linspace(snow_base_m - swing_m, snow_base_m + swing_m,
                        N_ALT_BINS + 1)
    classes = {"shaded": band & (nd < SHADE_NDL), "lit": band & (nd > LIT_NDL)}
    out["flank_summary"] = {
        k: {"px": int(m.sum()),
            "mean_snow_weight": round(float(sw[m].mean()), 4) if m.any() else None,
            "mean_rendered_luma": round(float(np.nanmean(px[m])), 5)
            if m.any() else None}
        for k, m in classes.items()}

    rows, ok_any = [], False
    for k, m in classes.items():
        for i in range(N_ALT_BINS):
            b = m & (hh >= edges[i]) & (hh < edges[i + 1])
            snowy = b & (sw > SNOWY)
            bare = b & (sw < BARE)
            if snowy.sum() < MIN_BIN_PX or bare.sum() < MIN_BIN_PX:
                continue
            ls_, lb = float(np.nanmean(px[snowy])), float(np.nanmean(px[bare]))
            ok_any = True
            rows.append({"flank": k,
                         "alt_m": [round(edges[i], 1), round(edges[i + 1], 1)],
                         "snowy_px": int(snowy.sum()), "bare_px": int(bare.sum()),
                         "luma_snowy": round(ls_, 5), "luma_bare": round(lb, 5),
                         "delta": round(ls_ - lb, 5),
                         "brighter": bool(ls_ > lb)})
    out["albedo_rows"] = rows
    if not ok_any:
        out["verdict"] = "NO PAIRED BINS"
        out["why"] = ("no altitude bin held both >=%d snowy and >=%d bare "
                      "texels in one flank class" % (MIN_BIN_PX, MIN_BIN_PX))
        return out
    n_bright = sum(1 for r in rows if r["brighter"])
    out["bins_where_snow_is_brighter"] = "%d/%d" % (n_bright, len(rows))
    out["verdict"] = "PASS" if n_bright == len(rows) else "FAIL"
    return out


def derive_camera(h_m, snow_w, spacing_m, ox, oy, L, snow_base_m, swing_m,
                  fov_h_deg=90.0, aspect=16.0 / 9.0, clearance_m=1000.0):
    """Pick the top-down station that can actually answer the question.

    The ruled (0,0,9000 m) camera is NON-PROBATIVE -- measured 2026-09-11,
    terrain luma std 0.0334 against a 0.05 floor -- because 9 km of aerial
    perspective flattens the frame.  Altitude is therefore set by
    CLEARANCE over the terrain rather than by covering the whole world,
    and the centre is DERIVED: the window holding the most band texels of
    the SCARCER flank class, since a window rich in one flank and empty of
    the other cannot compare them.
    """
    ndl, slope = hillshade(h_m, spacing_m, L)
    band = ((h_m > snow_base_m - swing_m) & (h_m < snow_base_m + swing_m)
            & (slope > 10.0))
    shaded = band & (ndl < SHADE_NDL)
    lit = band & (ndl > LIT_NDL)
    half_w = clearance_m * math.tan(math.radians(fov_h_deg) / 2.0)
    half_h = half_w / aspect
    # screen right is +Y and screen up is +X, so the frame is half_w wide
    # in Y and half_h tall in X
    step = 200
    ny, nx = h_m.shape
    best = None
    for cx in range(int(half_h / spacing_m), nx - int(half_h / spacing_m), step):
        for cy in range(int(half_w / spacing_m), ny - int(half_w / spacing_m),
                        step):
            x0, x1 = cx - int(half_h / spacing_m), cx + int(half_h / spacing_m)
            y0, y1 = cy - int(half_w / spacing_m), cy + int(half_w / spacing_m)
            s = int(shaded[y0:y1, x0:x1].sum())
            l = int(lit[y0:y1, x0:x1].sum())
            sc = min(s, l)
            if best is None or sc > best[0]:
                best = (sc, cx, cy, s, l,
                        float(np.median(h_m[y0:y1, x0:x1][band[y0:y1, x0:x1]]))
                        if band[y0:y1, x0:x1].any() else float(h_m[cy, cx]))
    sc, cx, cy, s, l, med_h = best
    return {"camera_cm": [round((ox + cx * spacing_m) * 100.0, 1),
                          round((oy + cy * spacing_m) * 100.0, 1),
                          round((med_h + clearance_m) * 100.0, 1)],
            "clearance_m": clearance_m, "median_band_height_m": round(med_h, 1),
            "shaded_band_px": s, "lit_band_px": l, "score_min_class": sc,
            "footprint_m": [round(2 * half_w, 1), round(2 * half_h, 1)]}


def selftest():
    """Direction 1 a synthetic frame built to the contract passes;
    direction 2 inverting the material's response FAILS; direction 3
    malformed/flat input refuses."""
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # The fixture must clear the REAL thresholds -- a fixture tuned
    # smaller than MIN_BIN_PX, or dimmer than MIN_STD, would force the
    # gate to be widened to admit it, which is the failure mode
    # verification-practice names outright.  So: large enough, and
    # EXPOSED like a real frame rather than left at raw reflectance.
    n, sp = 800, 8.0
    ox = oy = -n * sp / 2.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    az = 285.0
    L = sun_vector(az, 12.0)
    sh = math.atan2(math.cos(math.radians(az)), math.sin(math.radians(az)))
    across = ((xx - n / 2) * math.sin(sh) + (yy - n / 2) * math.cos(sh)) * sp
    h = (730.0 + 150.0 * np.exp(-(across / 300.0) ** 2)
         - np.abs(across) * 0.30).astype(np.float32)
    ndl, _ = hillshade(h, sp, L)
    # Snow follows the aspect-swung line AND loses to a competitor field
    # standing in for rock/scree precedence.  Without the competitor the
    # shaded class would be uniformly snowy and the lit class uniformly
    # bare, so no altitude bin would hold BOTH populations and the test
    # would silently score nothing -- which is what the first draft did.
    line = np.where(ndl < 0.02, 730.0 - 125.0, 730.0 + 125.0)
    rng = np.random.default_rng(11)
    comp = np.repeat(np.repeat(rng.random((n // 16, n // 16)), 16, 0), 16, 1)
    snow = ((h > line) & (comp[:n, :n] > 0.5)).astype(np.float32)
    cam = np.array([0.0, 0.0, 5000.0])
    W, H = 640, 360
    EXPOSURE = 2.5

    def render(albedo_of_snow):
        col, row, t = project(ox + xx * sp, oy + yy * sp, h, cam, 90.0, (W, H))
        img = np.zeros((H, W), dtype=np.float64)
        alb = 0.20 + (albedo_of_snow - 0.20) * snow
        val = np.clip(alb * (0.25 + 0.75 * ndl) * EXPOSURE, 0, 1)
        ci = np.clip(np.round(col).astype(int), 0, W - 1)
        ri = np.clip(np.round(row).astype(int), 0, H - 1)
        img[ri, ci] = val
        srgb = np.clip(img, 0, 1) ** (1 / 2.4)
        return Image.fromarray(np.uint8(np.stack([srgb] * 3, -1) * 255))

    print("direction 1 -- snow rendered BRIGHTER than rock passes")
    r = measure(render(0.80), h, snow, sp, ox, oy, cam, L, 90.0, 730.0, 125.0,
                stride=1)
    print("    %s" % json.dumps({k: r.get(k) for k in
                                 ("terrain_luma_std", "bins_where_snow_is_brighter",
                                  "verdict")}))
    check("snow brighter -> PASS", r.get("verdict") == "PASS")

    print("direction 2 -- a material that ignores the weightmap is BLOCKED")
    r2 = measure(render(0.06), h, snow, sp, ox, oy, cam, L, 90.0, 730.0, 125.0,
                 stride=1)
    print("    %s" % json.dumps({k: r2.get(k) for k in
                                 ("bins_where_snow_is_brighter", "verdict")}))
    check("snow DARKER than rock -> FAIL", r2.get("verdict") == "FAIL")

    print("direction 3 -- a flattened frame REFUSES rather than scoring")
    grey = Image.fromarray(np.uint8(np.full((H, W, 3), 200)))
    r3 = measure(grey, h, snow, sp, ox, oy, cam, L, 90.0, 730.0, 125.0, stride=1)
    check("flat frame -> NON-PROBATIVE", r3.get("verdict") == "NON-PROBATIVE")
    r4 = measure(render(0.80), h, snow, sp, ox, oy,
                 np.array([0.0, 0.0, 300.0]), L, 90.0, 730.0, 125.0, stride=1)
    check("camera below the terrain refuses", "error" in r4 or
          r4.get("verdict") in ("NON-PROBATIVE", "NO PAIRED BINS"))

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--frame")
    ap.add_argument("--cam-cm", help="x,y,z in cm (pitch -90, yaw 0)")
    ap.add_argument("--fov", type=float, default=90.0)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--derive-camera", action="store_true",
                    help="print the station that can answer the question, "
                         "instead of scoring a frame")
    ap.add_argument("--clearance-m", type=float, default=1000.0)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.derive_camera and (not a.frame or not a.cam_cm):
        sys.exit("REFUSE: --frame and --cam-cm are required")

    from derive_layer_weights import SNOW_ASPECT_HALF_M  # constant only
    rec = json.load(open(a.recipe, encoding="utf-8"))
    ls = rec["landscape"]
    h16 = np.asarray(Image.open(os.path.join(REPO, rec["heightmap"]["source"])))
    z_span = float(ls["z_scale_cm"]) / 100.0
    z_base = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) / 100.0
    h_m = h16.astype(np.float32) / 65535.0 * z_span + z_base
    snow_w = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8a.png"))).astype(np.float32)[..., 0] / 255.0
    sun = rec["lighting"]["sun"]
    base = float([l for l in rec["material"]["layers"]
                  if l["name"] == "Snow"][0]["height_m"][0])
    if a.derive_camera:
        d = derive_camera(h_m, snow_w, float(ls["scale_xy_cm"]) / 100.0,
                          float(ls["location_cm"][0]) / 100.0,
                          float(ls["location_cm"][1]) / 100.0,
                          sun_vector(sun["azimuth_deg"], sun["elevation_deg"]),
                          base, SNOW_ASPECT_HALF_M,
                          fov_h_deg=a.fov, clearance_m=a.clearance_m)
        print(json.dumps(d, indent=1))
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump({"_what": "topdown station derivation", "result": d},
                          fh, indent=1)
            print("wrote %s" % a.out)
        return 0

    cam = np.array([float(v) for v in a.cam_cm.split(",")]) / 100.0
    r = measure(Image.open(a.frame), h_m, snow_w,
                float(ls["scale_xy_cm"]) / 100.0,
                float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0, cam,
                sun_vector(sun["azimuth_deg"], sun["elevation_deg"]),
                a.fov, base, SNOW_ASPECT_HALF_M, stride=a.stride)
    r["frame"] = a.frame
    r["camera_m"] = list(cam)
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "topdown_flank_check", "result": r}, fh, indent=1)
        print("wrote %s" % a.out)
    return 0 if r.get("verdict") == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
