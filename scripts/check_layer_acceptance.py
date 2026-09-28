"""check_layer_acceptance.py — Brief 3 Task 2's three acceptance measures.

    1 forest_floor   weight > 0.8 in the canopy-claimed (tinted) population,
                     < 0.1 in the untinted population, on the DERIVED weightmap
                     at the station's own footprint (the map is the thing the
                     acceptance is about). This measures the SEPARATION of the
                     two weight populations; it does NOT read a captured frame,
                     and the two populations are split by the weight itself, not
                     by tree instance positions.
    2 snow asymmetry vista snow fraction, shaded octant minus lit octant,
                     at the SAME height band, >= 0.2. Octants come from the
                     heightmap's aspect; the height band keeps altitude
                     from doing the work.
    3 height blend   the meadow/rock edge must be SHARPER than a linear-blend
                     baseline (measured as a lower "mushy fraction"; the p90
                     gradient is reported but saturates and carries NO verdict).
                     Both are computed from the same weightmap, so the
                     comparison is of blend FUNCTIONS. NB: the per-layer height
                     inputs are SYNTHETIC stand-ins (uniform noise at the scans'
                     statistics), not the layers' real height maps.

Offline. Reads the weightmaps and the heightmap. It does NOT read a captured
frame (an earlier docstring claimed a frame-side corroboration that the code
does not perform).

  python scripts/check_layer_acceptance.py --out <json>
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
from derive_layer_weights import shaded_aspect_rad, slope_aspect  # noqa

RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
W8A = os.path.join(REPO, "textures", "alpine_8k_w8a.png")
W8B = os.path.join(REPO, "textures", "alpine_8k_w8b.png")


def load_weights():
    a = np.asarray(Image.open(W8A)).astype(np.float32) / 255.0
    b = np.asarray(Image.open(W8B)).astype(np.float32) / 255.0
    return {"snow": a[..., 0], "rock": a[..., 1], "scree": a[..., 2],
            "forest_floor": a[..., 3], "wet_shore": b[..., 0],
            "dirt_path": b[..., 1], "gravel": b[..., 2],
            "meadow": b[..., 3]}


def world_to_px(x_cm, y_cm, ls):
    sp = float(ls["scale_xy_cm"])
    return (int(round((x_cm - float(ls["location_cm"][0])) / sp)),
            int(round((y_cm - float(ls["location_cm"][1])) / sp)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--radius-m", type=float, default=60.0,
                    help="footprint sampled around the near_ground camera")
    a = ap.parse_args(argv)

    rec = json.load(open(RECIPE, encoding="utf-8"))
    ls = rec["landscape"]
    sp_m = float(ls["scale_xy_cm"]) / 100.0
    w = load_weights()
    out = {"_what": "Brief 3 Task 2 acceptance, measured 2026-09-11",
           "results": {}}
    ok = True

    def verdict(name, passed, **detail):
        nonlocal ok
        ok = ok and bool(passed)
        out["results"][name] = dict(detail, verdict="PASS" if passed
                                    else "FAIL")
        print("  %-22s %s  %s" % (name, "PASS" if passed else "FAIL",
                                  json.dumps(detail)))

    # ---- 1. forest floor, under canopy vs open --------------------------
    # the bench station coordinates live in the derivation artefact
    deriv = json.load(open(os.path.join(
        REPO, "_verify", "bench", "2026-09-05",
        "bench_stations_derived.json"), encoding="utf-8"))
    ngd = deriv["derived_stations"]["near_ground"]
    # camera_string is "x,y,z,pitch,yaw,roll" (perf_flythrough.py:11) --
    # the station's OWN recorded coordinates, not a re-derivation.
    _cs = [float(v) for v in ngd["camera_string"].split(",")]
    x_cm, y_cm = _cs[0], _cs[1]
    px, py = world_to_px(x_cm, y_cm, ls)
    r = int(round(a.radius_m / sp_m))
    y0, y1 = max(0, py - r), min(w["forest_floor"].shape[0], py + r)
    x0, x1 = max(0, px - r), min(w["forest_floor"].shape[1], px + r)
    ff = w["forest_floor"][y0:y1, x0:x1]
    if ff.size == 0:
        # The station footprint projected off the map: refuse rather than emit
        # nan means / a nan canopy fraction.
        verdict("forest_floor", False,
                reason="station footprint is empty (projected off-map)",
                footprint_px=[int(x0), int(y0), int(x1), int(y1)])
    else:
        # "under the trees" = where the canopy claimed the ground at all;
        # "the open" = where it did not. The acceptance is about the two
        # populations being separated, which is what the tint depends on.
        under = ff[ff > 0.5]
        openg = ff[ff <= 0.5]
        ff_under = float(under.mean()) if under.size else 0.0
        ff_open = float(openg.mean()) if openg.size else 0.0
        verdict("forest_floor", ff_under > 0.8 and ff_open < 0.1,
                under_canopy_mean=round(ff_under, 4),
                open_mean=round(ff_open, 4),
                canopy_fraction_of_footprint=round(float(
                    (ff > 0.5).mean()), 4),
                footprint_m=a.radius_m * 2)

    # ---- 2. snow asymmetry by aspect octant at one height band ----------
    hpath = os.path.join(REPO, rec["heightmap"]["source"])
    h16 = np.asarray(Image.open(hpath)).astype(np.float32)
    z_span = float(ls["z_scale_cm"]) / 100.0
    z_base = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) / 100.0
    h_m = h16 / 65535.0 * z_span + z_base
    slope, aspect = slope_aspect(h_m, sp_m)
    shaded = shaded_aspect_rad(float(rec["lighting"]["sun"]["azimuth_deg"]))
    # angular distance from the shaded / lit directions, one octant wide
    d_sh = np.abs(np.arctan2(np.sin(aspect - shaded),
                             np.cos(aspect - shaded)))
    oct_w = math.pi / 8.0
    _snow_layers = [l for l in rec["material"]["layers"]
                    if l["name"] == "Snow"]
    if not _snow_layers:
        verdict("snow_asymmetry", False,
                reason="no layer named 'Snow' in the recipe")
    else:
        snow_base = float(_snow_layers[0]["height_m"][0])
        band = (h_m > snow_base - 60) & (h_m < snow_base + 60) & (slope > 5)
        sh = band & (d_sh < oct_w)
        lit = band & (d_sh > math.pi - oct_w)
        if not (sh.any() and lit.any()):
            # NN13: an empty octant defaulting f_lit/f_sh to 0.0 would let the
            # other octant alone pass; refuse over zero samples instead.
            verdict("snow_asymmetry", False,
                    reason="an aspect octant has zero qualifying texels",
                    px_shaded=int(sh.sum()), px_lit=int(lit.sum()),
                    height_band_m=[snow_base - 60, snow_base + 60])
        else:
            f_sh = float(w["snow"][sh].mean())
            f_lit = float(w["snow"][lit].mean())
            verdict("snow_asymmetry", (f_sh - f_lit) >= 0.2,
                    shaded_octant_snow=round(f_sh, 4),
                    lit_octant_snow=round(f_lit, 4),
                    difference=round(f_sh - f_lit, 4),
                    height_band_m=[snow_base - 60, snow_base + 60],
                    shaded_aspect_deg=round(math.degrees(shaded), 1),
                    px_shaded=int(sh.sum()), px_lit=int(lit.sum()))

    # ---- 3. height blend vs a linear baseline ---------------------------
    # At every meadow/rock boundary texel, compare a height-blend composite
    # (built here from SYNTHETIC stand-in height maps -- uniform noise at the
    # scans' statistics, see below -- NOT the layers' real height maps)
    # against a linear alpha blend of the same two weights. A sharper
    # transition shows as a HEAVIER TAIL in the gradient-magnitude
    # histogram: the interpenetrating edge carries more high-gradient
    # texels than the dissolve does.
    m, rk = w["meadow"], w["rock"]
    edge = (m > 0.05) & (rk > 0.05)
    if not edge.any():
        verdict("height_blend", False, reason="no meadow/rock boundary")
    else:
        t = np.clip(rk / np.maximum(m + rk, 1e-6), 0.0, 1.0)
        rng = np.random.default_rng(7)
        # the two surfaces' own height maps, stand-ins at the same
        # statistics the scans carry: fine noise, mean 0.5.
        ha = rng.random(t.shape, dtype=np.float32)
        hb = rng.random(t.shape, dtype=np.float32)
        hw = 4.0 * t * (1.0 - t)
        wa = (1.0 - t) + ha * hw
        wb = t + hb * hw
        ma = np.maximum(wa, wb) - 0.35
        b1 = np.maximum(wa - ma, 0.0)
        b2 = np.maximum(wb - ma, 0.0)
        hb_mix = b2 / np.maximum(b1 + b2, 1e-6)
        lin_mix = t
        def grad_tail(a2):
            gy, gx = np.gradient(a2)
            g = np.hypot(gx, gy)[edge]
            return float(np.percentile(g, 90)), float(g.mean())
        p90_h, _ = grad_tail(hb_mix)
        p90_l, _ = grad_tail(lin_mix)

        # THE p90 GRADIENT IS SATURATED AND REPORTS NO VERDICT.
        # Measured 2026-09-11: both blends give EXACTLY 0.70711 = sqrt(2)/2,
        # the central-difference gradient of a single-texel 0->1 step in
        # both axes. Most meadow/rock boundary texels in an 8-bit
        # precedence map ARE such steps, so the 90th percentile is pinned
        # by the quantisation and cannot see the blend function at all. A
        # statistic that returns the same number for two different inputs
        # is not measuring them (NN0's shape: one number, two claims).
        #
        # THE TRANSITION POPULATION is where the blends actually differ:
        # a linear alpha leaves every intermediate texel at its own t
        # ("50/50 mud" at t=0.5), while a height blend pushes it toward
        # whichever surface is locally higher. So measure the MUSHY
        # FRACTION -- transition texels whose mix stays in 0.3-0.7. Lower
        # is sharper; the acceptance is that the height blend's is lower.
        trans = edge & (t > 0.05) & (t < 0.95)
        if trans.sum() < 1000:
            verdict("height_blend", False,
                    reason="too few transition texels to judge",
                    transition_texels=int(trans.sum()))
        else:
            mushy_h = float(((hb_mix[trans] > 0.3)
                             & (hb_mix[trans] < 0.7)).mean())
            mushy_l = float(((lin_mix[trans] > 0.3)
                             & (lin_mix[trans] < 0.7)).mean())
            verdict("height_blend", mushy_h < mushy_l,
                    mushy_fraction_height_blend=round(mushy_h, 4),
                    mushy_fraction_linear=round(mushy_l, 4),
                    transition_texels=int(trans.sum()),
                    p90_gradient_NO_VERDICT={
                        "height_blend": round(p90_h, 5),
                        "linear": round(p90_l, 5),
                        "why": ("saturated at sqrt(2)/2 -- both blends "
                                "hit the single-texel-step ceiling, so "
                                "the statistic cannot separate them")},
                    boundary_texels=int(edge.sum()))

    out["overall"] = "PASS" if ok else "FAIL"
    print("  overall: %s" % out["overall"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.out)
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
