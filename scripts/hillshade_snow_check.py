"""hillshade_snow_check.py — does the DERIVED snow sit on the flank the
sun misses?

    python scripts/hillshade_snow_check.py [--recipe R] [--out J]
    python scripts/hillshade_snow_check.py --selftest

THE POINT IS INDEPENDENCE (NN8). `derive_layer_weights` places snow by
`cos(aspect - shaded_rad)`, where `shaded_rad` comes from its own
`shaded_aspect_rad`.  A check that called either of those would verify
the arithmetic against itself and pass however the axis was bound --
which is exactly the defect audited out on 2026-09-11 (LESSONS
2026-09-11b), where `cos(aspect)` was bound to map +Y instead of the sun
and the selftest passed throughout.

So this module computes a STANDARD HILLSHADE -- max(0, N.L) from the
heightmap gradients and the recipe's sun -- and imports NOTHING from the
derivation for scoring.  `derive()` is imported by the SELFTEST ONLY, to
manufacture a known-good specimen.

THE DATUM (docs/ue58-api-protocol.md, the casualty list):
`lighting.sun.azimuth_deg` is the light actor's YAW -- the direction
light TRAVELS.  The sun SITS at azimuth-180.  L below points from the
surface toward the sun; reading azimuth as the sun's bearing puts the
shaded flank on the wrong side, which is the whole failure this check
exists to catch.

THE THRESHOLD IS DERIVED, NOT TUNED.  Scoring runs in the band
`snow_base +- SNOW_ASPECT_HALF_M`, the altitudes the two flanks' snow
lines straddle.  The lines sit 2*125 = 250 m apart while the feather is
only 2*60 = 120 m wide, so the two transitions DO NOT OVERLAP: at every
altitude in the band at most one flank can be part-snowy, and the lit
flank cannot reach snow > 0.5 at all (that needs h > base + 125, the
band's own top edge).  Hence:

    lit  fraction(snow > 0.5)  must be  < LIT_CEIL  (0.05, the sliver)
    shaded/lit ratio           must be  >= MIN_RATIO (4.0, conservative
                               against a non-overlap that predicts
                               unbounded)

What this does NOT establish: that the ENGINE renders the map, and that
the heightmap's row/col axes map to world X/Y as assumed -- a mirrored
import flips the derivation and this check TOGETHER (NN0).  Those are
`check_layer_acceptance.py` and `heightmap_orientation_check.py`
respectively.
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

SLOPE_FLOOR_DEG = 10.0      # flat ground has no aspect worth scoring
LIT_CEIL = 0.05             # derived above: the lit flank's snow sliver
MIN_RATIO = 4.0             # derived above: non-overlap predicts >> this
SHADE_NDL = 0.02            # "the sun misses it"
LIT_NDL = 0.5               # "the sun plainly hits it"


def sun_vector(azimuth_deg, elevation_deg):
    """Unit vector from the surface TOWARD the sun.

    azimuth_deg is the light's YAW (direction of travel), so the sun is
    at azimuth-180 and the horizontal part negates."""
    az = math.radians(float(azimuth_deg))
    el = math.radians(float(elevation_deg))
    return np.array([-math.cos(az) * math.cos(el),
                     -math.sin(az) * math.cos(el),
                     math.sin(el)], dtype=np.float64)


def hillshade(h_m, spacing_m, L):
    """Standard max(0, N.L) and slope degrees, from gradients only."""
    gy, gx = np.gradient(h_m.astype(np.float32), spacing_m)
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    ndl = np.clip((-gx * nz) * L[0] + (-gy * nz) * L[1] + nz * L[2], 0.0, 1.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return ndl, slope


def score(h_m, snow_w, spacing_m, L, snow_base_m, swing_m):
    """Shaded-vs-lit snow over the straddled band. Returns a dict; every
    refusal path returns a reason instead of a number (NN6 -- a failed
    measurement reports that it failed)."""
    if h_m.shape != snow_w.shape:
        return {"error": "heightmap %s and snow weightmap %s differ in shape"
                         % (h_m.shape, snow_w.shape)}
    if not np.isfinite(h_m).all():
        return {"error": "heightmap holds non-finite values; a NaN compares "
                         "False everywhere and would empty both flanks"}
    if not np.isfinite(snow_w).all():
        return {"error": "snow weightmap holds non-finite values"}
    ndl, slope = hillshade(h_m, spacing_m, L)
    band = ((h_m > snow_base_m - swing_m) & (h_m < snow_base_m + swing_m)
            & (slope > SLOPE_FLOOR_DEG))
    shade = band & (ndl < SHADE_NDL)
    lit = band & (ndl > LIT_NDL)
    if shade.sum() < 1000 or lit.sum() < 1000:
        return {"error": "band holds too few flank texels to judge "
                         "(shaded %d, lit %d, need 1000 each)"
                         % (int(shade.sum()), int(lit.sum())),
                "band_px": int(band.sum())}
    f_sh = float((snow_w[shade] > 0.5).mean())
    f_lit = float((snow_w[lit] > 0.5).mean())
    ratio = f_sh / f_lit if f_lit > 0 else float("inf")
    ok = (f_lit < LIT_CEIL) and (ratio >= MIN_RATIO)
    return {"band_px": int(band.sum()),
            "shaded_px": int(shade.sum()), "lit_px": int(lit.sum()),
            "mean_snow_shaded": round(float(snow_w[shade].mean()), 4),
            "mean_snow_lit": round(float(snow_w[lit].mean()), 4),
            "frac_snow_gt_half_shaded": round(f_sh, 4),
            "frac_snow_gt_half_lit": round(f_lit, 4),
            "ratio": (round(ratio, 2) if math.isfinite(ratio) else "inf"),
            "band_m": [round(snow_base_m - swing_m, 1),
                       round(snow_base_m + swing_m, 1)],
            "thresholds": {"lit_ceiling": LIT_CEIL, "min_ratio": MIN_RATIO},
            "verdict": "PASS" if ok else "FAIL"}


def _load(recipe_path):
    rec = json.load(open(recipe_path, encoding="utf-8"))
    ls = rec["landscape"]
    h16 = np.asarray(Image.open(os.path.join(REPO, rec["heightmap"]["source"])))
    if h16.ndim != 2:
        sys.exit("REFUSE: heightmap is not single-channel, shape %s"
                 % (h16.shape,))
    z_span = float(ls["z_scale_cm"]) / 100.0
    z_base = (float(ls["location_cm"][2])
              - float(ls["z_scale_cm"]) / 2.0) / 100.0
    h_m = h16.astype(np.float32) / 65535.0 * z_span + z_base
    snow_w = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8a.png"))).astype(np.float32)[..., 0] / 255.0
    sun = rec["lighting"]["sun"]
    base = float([l for l in rec["material"]["layers"]
                  if l["name"] == "Snow"][0]["height_m"][0])
    return (rec, h_m, snow_w, float(ls["scale_xy_cm"]) / 100.0,
            sun_vector(sun["azimuth_deg"], sun["elevation_deg"]), base)


# --------------------------------------------------------------------------
# selftest -- three directions
# --------------------------------------------------------------------------

def selftest():
    from derive_layer_weights import (SNOW_ASPECT_HALF_M, derive,  # noqa
                                      shaded_aspect_rad)
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # A ridge running 75 deg (map frame) so its flanks face the sun axis
    # for azimuth 285.  Height rises to straddle the snow band.
    n, sp = 600, 4.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    az = 285.0
    shaded = shaded_aspect_rad(az)
    ax, ay = math.sin(shaded), math.cos(shaded)     # across-ridge unit vector
    across = ((xx - n / 2) * ax + (yy - n / 2) * ay) * sp
    h = 730.0 + 180.0 * np.exp(-(across / 260.0) ** 2) - np.abs(across) * 0.34
    h = h.astype(np.float32)
    flat = np.zeros_like(h)
    w, _sl, _as = derive(h, sp, flat, flat, flat, snow_base_m=730.0,
                         shaded_rad=shaded)
    L = sun_vector(az, 12.0)

    print("direction 1 -- the legitimate case PASSES")
    r = score(h, w["snow"], sp, L, 730.0, SNOW_ASPECT_HALF_M)
    print("    %s" % json.dumps({k: r[k] for k in
                                 ("frac_snow_gt_half_shaded",
                                  "frac_snow_gt_half_lit", "ratio", "verdict")
                                 if k in r}))
    check("snow derived for az 285 passes against az 285's hillshade",
          r.get("verdict") == "PASS")

    print("direction 2 -- the violation is BLOCKED")
    # Same terrain and same snow, but the sun is on the other side: the
    # snow now sits on the LIT flank and the check must say so.  This is
    # the direction the derivation's own selftest structurally lacked.
    r2 = score(h, w["snow"], sp, sun_vector(az + 180.0, 12.0), 730.0,
               SNOW_ASPECT_HALF_M)
    print("    %s" % json.dumps({k: r2[k] for k in
                                 ("frac_snow_gt_half_shaded",
                                  "frac_snow_gt_half_lit", "ratio", "verdict")
                                 if k in r2}))
    check("flip the sun 180 deg -> FAIL", r2.get("verdict") == "FAIL")
    # and snow derived for the FLIPPED sun must pass against it, so the
    # failure above is the axis and not the specimen
    w2, _s2, _a2 = derive(h, sp, flat, flat, flat, snow_base_m=730.0,
                          shaded_rad=shaded_aspect_rad(az + 180.0))
    r3 = score(h, w2["snow"], sp, sun_vector(az + 180.0, 12.0), 730.0,
               SNOW_ASPECT_HALF_M)
    check("flip BOTH sun and derivation -> PASS again",
          r3.get("verdict") == "PASS")

    print("direction 3 -- malformed input REFUSES, does not crash through")
    bad = h.copy()
    bad[10, 10] = np.nan
    check("NaN heightmap refuses", "error" in score(
        bad, w["snow"], sp, L, 730.0, SNOW_ASPECT_HALF_M))
    check("NaN weightmap refuses", "error" in score(
        h, np.full_like(h, np.nan), sp, L, 730.0, SNOW_ASPECT_HALF_M))
    check("shape mismatch refuses", "error" in score(
        h, w["snow"][:-1, :], sp, L, 730.0, SNOW_ASPECT_HALF_M))
    flat_t = np.full((400, 400), 730.0, dtype=np.float32)
    check("flat terrain (no flanks) refuses rather than passing",
          "error" in score(flat_t, np.zeros_like(flat_t), sp, L, 730.0,
                           SNOW_ASPECT_HALF_M))

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    from derive_layer_weights import SNOW_ASPECT_HALF_M  # constant only
    rec, h_m, snow_w, sp_m, L, base = _load(a.recipe)
    sun = rec["lighting"]["sun"]
    print("sun azimuth %.0f deg (light TRAVEL yaw), elevation %.0f deg"
          % (sun["azimuth_deg"], sun["elevation_deg"]))
    print("  -> unit vector toward the sun [%.4f %.4f %.4f]" % tuple(L))
    r = score(h_m, snow_w, sp_m, L, base, SNOW_ASPECT_HALF_M)
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "hillshade_snow_check", "recipe": a.recipe,
                       "result": r}, fh, indent=1)
        print("wrote %s" % a.out)
    if "error" in r:
        return 6
    return 0 if r["verdict"] == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
