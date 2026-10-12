"""bake_cavity_map.py -- schema v1.31 `material.cavity`: a terrain-scale concavity map.

    python scripts/bake_cavity_map.py --recipe recipes/lookdev.json [--write]

WHY. Cliff faces read as one even tone: the rock scans carry detail at 0.2-22 m
and the macro sample at 140 m, but nothing darkens the 5-60 m gullies and
couloirs the heightfield actually has. Real faces collect shadow, water stain
and debris in exactly those concavities (Gemini critique 2026-10-03, item 3).

WHAT. For each scale s in material.cavity.scales_m, L_s = blur(h, s) - h is the
depth (m) a texel sits below its neighbourhood mean -- positive in gullies,
negative on ribs. Each is normalised by its depth_m and clipped to [0, 1]; the
map is their max. One map, one meaning: 0 = not concave, 1 = fully concave.
The material darkens the listed layers' albedo by lerp(1, tint, cavity *
strength), so a 0 texel (or a missing, fully-mipped flat map) is the identity.

Output: material.cavity.map (the path the importer reads), 8-bit RGB (R=G=B), the heightmap's own
resolution, clamped 1:1 over the terrain on the weightmap's UV chain. Without
--write it reports and writes nothing.
"""
import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cavity(h_m, px_m, scales_m, depths_m):
    """Max over scales of clip((blur(h, s) - h) / depth, 0, 1). Pure."""
    out = np.zeros_like(h_m, dtype=np.float64)
    for s, d in zip(scales_m, depths_m):
        lap = gaussian_filter(h_m, sigma=float(s) / px_m, mode="nearest") - h_m
        out = np.maximum(out, np.clip(lap / float(d), 0.0, 1.0))
    return out


def self_test():
    """A V-gully must read concave at its floor and 0 on its ribs and on a
    plane (the identity case), whatever the plane's tilt."""
    fails = []
    y, x = np.mgrid[0:200, 0:200].astype(np.float64)
    plane = 0.7 * x + 0.2 * y
    c = cavity(plane, 1.0, [8.0], [2.0])
    # Margin 40 px = 5 sigma: the blur's border mode bends the plane there.
    if c[40:160, 40:160].max() > 1e-6:
        fails.append("tilted plane reads concave: %g" % c.max())
    gully = plane + np.abs(x - 100.0) * 0.5
    c = cavity(gully, 1.0, [8.0], [2.0])
    if c[100, 100] < 0.5:
        fails.append("gully floor not concave: %g" % c[100, 100])
    if c[100, 140] > 1e-6 or c[100, 60] > 1e-6:
        fails.append("gully flank reads concave")
    ridge = plane - np.abs(x - 100.0) * 0.5
    if cavity(ridge, 1.0, [8.0], [2.0])[100, 100] > 1e-6:
        fails.append("ridge crest reads concave")
    return fails


def _slope_deg(h, px_m):
    gy, gx = np.gradient(h, px_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _smooth(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lichen(h, px_m, slope_deg, noise_m, seed, slope_fade_deg=3.0,
           convex_blur_m=6.0, convex_depth_m=1.5, convex_weight=0.6,
           noise_band=(0.35, 0.65)):
    """G channel (v1.33): exposed, less-steep rock where lichen grows -- slope
    inside slope_deg (faded slope_fade_deg each side), boosted on convex edges
    (height above the convex_blur_m mean, normalised by convex_depth_m, weight
    convex_weight), broken into patches by value noise of noise_m kept over
    noise_band. Every constant comes from the recipe (audit F4). 0..1."""
    sl = _slope_deg(h, px_m)
    f = float(slope_fade_deg)
    band = _smooth(slope_deg[0] - f, slope_deg[0] + f, sl) * \
        (1.0 - _smooth(slope_deg[1] - f, slope_deg[1] + f, sl))
    convex = np.clip((h - gaussian_filter(h, convex_blur_m / px_m, mode="nearest"))
                     / convex_depth_m, 0.0, 1.0)
    rng = np.random.default_rng(seed)
    cell = max(2, int(round(noise_m / px_m)))
    from scipy.ndimage import zoom
    n = zoom(rng.random((h.shape[0] // cell + 2, h.shape[1] // cell + 2)), cell,
             order=3)[:h.shape[0], :h.shape[1]]
    return np.clip(np.maximum(band, convex_weight * convex)
                   * _smooth(noise_band[0], noise_band[1], n), 0.0, 1.0)


def damp(h, px_m, reach_m, gentle_deg, steep_ramp_deg=(5.0, 15.0), slope_smooth_m=0.0):
    """B channel (v1.33): the wet foot of a cliff -- steep cells (ramping in
    from gentle_deg + steep_ramp_deg[0] to + [1]) within reach_m of gentle
    ground (< gentle_deg), fading with distance. 0..1.

    slope_smooth_m (2026-10-04): slope measured on a Gaussian-smoothed height.
    On the raw 8K world heightmap 1 m micro-relief scatters 'gentle' cells
    through the rock, so ~43% of a tile read as cliff-foot (4 m: 3.8%, the
    rig's eroded crop gave 4.3%). 0 = the original behaviour."""
    from scipy.ndimage import distance_transform_edt
    hs = gaussian_filter(h, slope_smooth_m / px_m, mode="nearest") if slope_smooth_m > 0 else h
    sl = _slope_deg(hs, px_m)
    gentle = sl < gentle_deg
    dist = distance_transform_edt(~gentle) * px_m
    return np.clip(1.0 - dist / float(reach_m), 0.0, 1.0) * \
        _smooth(gentle_deg + steep_ramp_deg[0], gentle_deg + steep_ramp_deg[1], sl)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    fails = self_test()
    if fails:
        print("SELF-TEST FAILED:\n  " + "\n  ".join(fails))
        return 3
    if a.self_test:
        print("self-test ok")
        return 0
    r = json.load(io.open(a.recipe, encoding="utf-8"))
    cv = (r.get("material") or {}).get("cavity")
    if not cv:
        print("recipe declares no material.cavity")
        return 2
    hm = r["heightmap"]
    if hm.get("format") != "png16":
        print("heightmap format must be png16, got %r" % hm.get("format"))
        return 2
    src = os.path.join(REPO, hm["source"])
    raw = np.asarray(Image.open(src), dtype=np.float64)
    if raw.max() <= 255:
        print("heightmap %s does not look 16-bit (max %g)" % (src, raw.max()))
        return 2
    z_m = float(r["landscape"]["z_scale_cm"]) / 100.0
    px_m = float(r["landscape"]["scale_xy_cm"]) / 100.0
    h = raw / 65535.0 * z_m
    c = cavity(h, px_m, cv["scales_m"], cv["depths_m"])
    print("heightmap %s %dx%d, %.2f m/px, h %.1f..%.1f m"
          % (hm["source"], raw.shape[1], raw.shape[0], px_m, h.min(), h.max()))
    for t in (0.1, 0.3, 0.5, 0.8):
        print("  cavity > %.1f : %5.1f %% of texels" % (t, 100.0 * (c > t).mean()))
    # The recipe's `map` is the ONE path: the importer reads the same field.
    out = os.path.realpath(os.path.join(REPO, cv["map"]))
    if os.path.commonpath([out, os.path.realpath(REPO)]) != \
            os.path.realpath(REPO):
        print("material.cavity.map escapes the repo: %r" % cv["map"])
        return 2
    if not a.write:
        print("dry run; would write " + out)
        return 0
    q = np.round(c * 255.0).astype(np.uint8)
    # v1.33: G = lichen, B = damp, each only when declared; otherwise the
    # channel repeats R exactly as before (the identity the material ignores).
    g = b = q
    if cv.get("lichen"):
        lc = cv["lichen"]
        g = np.round(lichen(
            h, px_m, lc["slope_deg"], lc["noise_m"], int(lc.get("seed", 20261003)),
            lc.get("slope_fade_deg", 3.0), lc.get("convex_blur_m", 6.0),
            lc.get("convex_depth_m", 1.5), lc.get("convex_weight", 0.6),
            tuple(lc.get("noise_band", (0.35, 0.65))))
            * 255.0).astype(np.uint8)
        print("  lichen > 0.5 : %5.1f %% of texels" % (100.0 * (g > 127).mean()))
    if cv.get("damp"):
        dp = cv["damp"]
        _sr = float(dp.get("steep_ramp_deg", 10.0))
        b = np.round(damp(h, px_m, dp["reach_m"], dp["gentle_deg"],
                          (_sr * 0.5, _sr * 1.5), float(dp.get("slope_smooth_m", 0.0)))
                     * 255.0).astype(np.uint8)
        print("  damp   > 0.5 : %5.1f %% of texels" % (100.0 * (b > 127).mean()))
    Image.fromarray(np.dstack([q, g, b]), "RGB").save(out)
    # Sidecar: which channels this bake filled, so the importer can refuse a
    # STALE map whose G/B still hold cavity copies (audit F3).
    json.dump({"R": "cavity", "G": "lichen" if cv.get("lichen") else "cavity",
               "B": "damp" if cv.get("damp") else "cavity"},
              io.open(out + ".channels.json", "w", encoding="utf-8"), indent=1)
    print("wrote " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
