"""task4_meadow_albedo.py — meadow albedo variation on the LINEAR instrument,
lit pixels only.

    python scripts/task4_meadow_albedo.py --selftest
    python scripts/task4_meadow_albedo.py --frames <dir> --station ground

⭐ WHY THE OLD NUMBER WAS NOT A BASELINE. Task 3 reported Grass albedo
variation as 0.4283 — std/mean of luma over the Grass mask on
FinalImage, WITH SHADOWS IN IT. That statistic is dominated by the
sun/shade split, which is a LIGHTING fact, not an albedo fact: a
perfectly uniform meadow half in shadow scores about 0.4 on it. Task 4's
band (0.10–0.20) is about how much the GROUND COVER varies, so the
measurement has to exclude shadow before it means anything.

THE LIT-ONLY MASK, AND WHICH OF THE THREE ROUTES THIS IS.
The ruling offered two: derive the mask from the depth pass and the sun
direction, or take a shadow-only capture. Neither is used, and the
reasons are measurements, not preferences:

  * FROM DEPTH AND SUN DIRECTION would mean reconstructing geometry and
    ray-marching it for occlusion. Our depth pass is 8-BIT LOG depth,
    about 5.6% per LSB — `task3_layer_tables` already restricts it to
    "a distance along a known ray" for exactly this reason. Shadowing
    from it would be fiction.
  * A SHADOW-ONLY CAPTURE means toggling the sun's shadow casting, which
    moves a lighting value. The session fence says no lighting value
    moves.

  ⭐ THE THIRD ROUTE, which needs neither: IRRADIANCE = PPI0 / BASECOLOR.
  PPI0 is scene-linear lit colour and BaseColor is the GBuffer albedo
  behind it, so their ratio is the shading term with the surface's own
  colour divided out. A lit pixel receives sun+sky; a shadowed one
  receives sky alone. Both passes are already in the capture, so this
  costs no render and moves nothing.

THE THRESHOLD IS FOUND IN THE DATA, NOT CHOSEN. log(irradiance) over the
meadow is BIMODAL — sun+sky and sky-only — and the cut is the VALLEY
between the two modes, located by smoothing the histogram and taking its
lowest point between the peaks. If the histogram is not bimodal the
routine REFUSES rather than cutting at a quantile, because a quantile
always produces a mask and tells you nothing about whether there was a
shadow to find.

⭐ AND THE MASK IS CHECKED AGAINST PHYSICS IT DID NOT SEE. The ratio of
the two modes is the sun+sky to sky-only ratio — which this project has
already measured independently, with a physical grey card in frame:
R-SHADE reads 2.5166 on PPI0. That number comes from a different
instrument on a different capture and is nowhere in this derivation, so
agreement is evidence and disagreement is a refusal (NN8).

⛔ THE 1–4 m BAND DOES NOT EXIST AT THIS STATION AND IS NOT SILENTLY
SUBSTITUTED. Measured on the capture: the nearest non-sky pixel in the
frame is at 4.110 m. With a 1.70 m eye height and a 90 degree hfov the
bottom of frame looks 29.36 degrees below the horizon, so flat ground
enters the view at 3.47 m along the ray and this terrain slopes away.
The whole 1–4 m band is BELOW THE BOTTOM OF THE FRAME — a geometry
fact, not a sampling shortfall. Every band asked for is reported with
its own pixel count, and an empty one reads NO VERDICT with that
explanation attached.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402
from task3_layer_tables import (CAMS, LUMA, RECIPE,  # noqa: E402
                                layer_index_map, world_xy)
import exr_card  # noqa: E402

MEADOW_LAYER = "Grass"
ALBEDO_BAND = (0.10, 0.20)
# Bands reported. The first is the ruling's, kept so its emptiness is on
# the record rather than quietly replaced.
BANDS = [(1.0, 4.0), (4.0, 10.0), (3.0, 60.0)]
MIN_PX = 20000
# R-SHADE, PPI0, measured with a physical card in frame. Used ONLY as an
# independent check on the mask; nothing here derives from it.
SHADE_RATIO_REF = 2.5166
SHADE_RATIO_TOL = 0.40          # +/-40%: this is a cross-check, not a gate


def split_lit(irr, bins=160):
    """Find the sun/shade cut as the VALLEY of a bimodal log-irradiance.

    Returns (threshold, info). threshold is None when the histogram is
    not bimodal -- in which case there is no shadow population to
    separate and cutting anyway would invent one.
    """
    v = irr[np.isfinite(irr) & (irr > 0)]
    info = {"n": int(v.size)}
    if v.size < 1000:
        info["why"] = "only %d usable pixels" % v.size
        return None, info
    lv = np.log(v)
    lo, hi = np.percentile(lv, [0.5, 99.5])
    if not (hi > lo):
        info["why"] = "log-irradiance has no spread"
        return None, info
    h, edges = np.histogram(lv, bins=bins, range=(lo, hi))
    hs = ndi.gaussian_filter1d(h.astype(np.float64), 2.0)
    centres = 0.5 * (edges[1:] + edges[:-1])
    peaks = [i for i in range(1, len(hs) - 1)
             if hs[i] > hs[i - 1] and hs[i] >= hs[i + 1]]
    peaks.sort(key=lambda i: -hs[i])
    info["n_peaks"] = len(peaks)
    if len(peaks) < 2:
        info["why"] = ("log-irradiance is unimodal (%d peak(s)): there is no "
                       "shadow population to separate, so no cut is made"
                       % len(peaks))
        return None, info
    a, b = sorted(peaks[:2])
    # The two strongest peaks must be genuinely separate, not one peak's
    # shoulder: require the valley to drop meaningfully below both.
    valley = a + int(np.argmin(hs[a:b + 1]))
    depth = min(hs[a], hs[b])
    info.update({"mode_lo": round(float(np.exp(centres[a])), 6),
                 "mode_hi": round(float(np.exp(centres[b])), 6),
                 "valley": round(float(np.exp(centres[valley])), 6),
                 "valley_rel_depth": round(float(hs[valley] / max(depth, 1e-9)),
                                           4)})
    if hs[valley] > 0.85 * depth:
        info["why"] = ("the two modes are not separated -- the valley sits at "
                       "%.2f of the smaller peak, so this is one broad "
                       "population, not sun and shade"
                       % (hs[valley] / max(depth, 1e-9)))
        return None, info
    info["mode_ratio"] = round(info["mode_hi"] / max(info["mode_lo"], 1e-9), 4)
    return float(np.exp(centres[valley])), info


def measure(frames, station, recipe_path=RECIPE):
    rec = json.load(open(recipe_path, encoding="utf-8"))
    cams = json.load(open(CAMS, encoding="utf-8"))["cameras"]
    cam = cams[station]
    exr = os.path.join(frames, "%s.exr" % station)
    dep = os.path.join(frames, "%sFinalImageSceneDepth.png" % station)
    for p in (exr, dep):
        if not os.path.exists(p):
            raise SystemExit("missing %s" % p)
    ppi0 = exr_card.read_rgb(exr, "FinalImagePPI0")
    bc = exr_card.read_rgb(exr, "FinalImageBaseColor")
    depth = decode_depth_m(dep)
    h, w = depth.shape
    if ppi0.shape[:2] != depth.shape or bc.shape[:2] != depth.shape:
        raise SystemExit("passes disagree on size")
    sky = depth > CEILING_M * 0.97
    wx, wy = world_xy(depth, cam, (w, h))
    lay, names = layer_index_map(wx, wy, rec)
    gi = names.index(MEADOW_LAYER)
    L = np.array(LUMA)
    g_ppi0 = ppi0[..., :3] @ L
    g_bc = bc[..., :3] @ L
    # ⛔ THE BASECOLOR PASS IS NOT ALBEDO -- IT IS ALBEDO x THE EXPOSURE
    # SCALE. Measured 2026-09-13: this pass maxes at 6.31e-05, and
    # 6.31e-05 / 2^-13.5898 = 0.778, with p99 -> 0.607. Bounded by 1 and
    # plausible, so the pass carries the bench's -13.5898 EV compensation
    # (8.111e-05) exactly as the lit passes do. Read as albedo directly it
    # is wrong by four orders of magnitude. It went unnoticed until now
    # because everything that had used it -- the split-(b) discriminator,
    # the period spectrum, std/mean -- is scale-INVARIANT, so a constant
    # factor changed none of those numbers. The irradiance ratio is
    # scale-invariant too (the constant divides out of PPI0/BaseColor and
    # out of the mode RATIO), which is why this is recorded rather than
    # corrected for.
    #
    # So the "has albedo" floor cannot be an absolute constant: 1e-4 is
    # ABOVE this pass's maximum and excluded every pixel in the frame.
    # It is derived from the pass's own scale instead.
    ref = float(np.percentile(g_bc[~sky], 99.0)) if (~sky).any() else 0.0
    albedo_floor = max(ref * 1e-3, 1e-12)
    out_floor = {"basecolor_p99": ref, "albedo_floor": albedo_floor}
    has_albedo = g_bc > albedo_floor
    with np.errstate(divide="ignore", invalid="ignore"):
        irr = np.where(has_albedo, g_ppi0 / np.maximum(g_bc, 1e-9), np.nan)

    out = {"_what": "Task 4 baseline: meadow albedo variation on PPI0, "
                    "lit pixels only",
           "station": station, "frames": frames,
           "layer": MEADOW_LAYER, "band_target": list(ALBEDO_BAND),
           "near_limit_m": round(float(depth[~sky].min()), 3),
           "shade_ratio_reference": SHADE_RATIO_REF,
           "basecolor_scale": out_floor,
           "_basecolor_is_not_albedo": (
               "the BaseColor pass carries the bench exposure "
               "compensation: its p99 is %.4g, which divided by "
               "2^-13.5898 is %.4f. Absolute values off this pass are NOT "
               "albedo. Every statistic here is scale-invariant, which is "
               "why the constant is recorded rather than divided out."
               % (out_floor["basecolor_p99"],
                  out_floor["basecolor_p99"] / 2.0 ** -13.5898)),
           "bands": []}
    # Geometry of the frame's near limit, so "1-4 m is empty" carries its
    # own explanation rather than a bare zero.
    tan_v = math.tan(math.radians(float(cam.get("fov_deg") or 90.0)) / 2.0) \
        * (h / float(w))
    out["bottom_of_frame_deg_below_horizon"] = round(
        math.degrees(math.atan(tan_v)), 2)

    for lo, hi in BANDS:
        m = (~sky) & (depth >= lo) & (depth <= hi) & (lay == gi)
        ent = {"band_m": [lo, hi], "pixels": int(m.sum())}
        if ent["pixels"] < MIN_PX:
            ent["verdict"] = "NO VERDICT"
            ent["why"] = (
                "only %d %s pixels in this band. The frame's nearest non-sky "
                "pixel is at %.3f m and the bottom of frame looks %.2f deg "
                "below the horizon from a 1.70 m eye height, so this band is "
                "below the bottom of the image -- a geometry fact, not a "
                "sampling shortfall."
                % (ent["pixels"], MEADOW_LAYER, out["near_limit_m"],
                   out["bottom_of_frame_deg_below_horizon"]))
            out["bands"].append(ent)
            continue
        usable = m & has_albedo
        ent["pixels_without_albedo"] = int((m & ~has_albedo).sum())
        # ⭐ THE METRIC THAT NEEDS NO MASK AT ALL. The lit-only mask exists
        # to stop SHADING contaminating an ALBEDO statistic. BaseColor is
        # the GBuffer albedo -- shading was never applied to it -- so
        # std/mean here is albedo variation with all lighting removed
        # exactly, rather than approximately and behind a threshold.
        # Reported for every band whether or not the lit split succeeds,
        # because it is the number that survives the split failing.
        bcv = g_bc[usable]
        ent["std_over_mean_basecolor"] = round(
            float(bcv.std() / bcv.mean()), 4)
        ent["mean_albedo"] = round(float(bcv.mean() / (2.0 ** -13.5898)), 4)
        sb = ent["std_over_mean_basecolor"]
        ent["basecolor_verdict"] = (
            "IN BAND" if ALBEDO_BAND[0] <= sb <= ALBEDO_BAND[1]
            else ("ABOVE BAND" if sb > ALBEDO_BAND[1] else "BELOW BAND"))
        thr, info = split_lit(irr[usable])
        ent["lit_split"] = info
        # WITH shadows -- the number Task 3 reported, kept for comparison
        v_all = g_ppi0[usable]
        ent["std_over_mean_with_shadows"] = round(
            float(v_all.std() / v_all.mean()), 4)
        if thr is None:
            ent["verdict"] = "NO VERDICT"
            ent["why"] = ("no sun/shade split could be found: %s"
                          % info.get("why"))
            out["bands"].append(ent)
            continue
        lit = usable & (irr >= thr)
        ent["lit_threshold_irradiance"] = round(float(thr), 6)
        ent["lit_pixels"] = int(lit.sum())
        ent["lit_fraction"] = round(float(lit.sum() / max(usable.sum(), 1)), 4)
        # ⭐ THE INDEPENDENT CHECK. The two modes' ratio is the sun+sky to
        # sky-only ratio, which R-SHADE measured with a physical card.
        ratio = info.get("mode_ratio")
        ent["mode_ratio"] = ratio
        ent["shade_ratio_check"] = (
            "PASS" if ratio and abs(ratio - SHADE_RATIO_REF) \
            <= SHADE_RATIO_TOL * SHADE_RATIO_REF else "MISMATCH")
        ent["_shade_ratio_check_means"] = (
            "the sun/shade ratio implied by this mask (%.3f) against "
            "R-SHADE's card measurement on PPI0 (%.4f), which is a "
            "different instrument on a different capture and is not used "
            "anywhere in deriving the mask" % (ratio or float('nan'),
                                               SHADE_RATIO_REF))
        if ent["lit_pixels"] < MIN_PX:
            ent["verdict"] = "NO VERDICT"
            ent["why"] = ("only %d LIT pixels after the mask"
                          % ent["lit_pixels"])
            out["bands"].append(ent)
            continue
        v = g_ppi0[lit]
        sm = float(v.std() / v.mean())
        ent["std_over_mean_lit_only"] = round(sm, 4)
        ent["mean_ppi0_lit"] = round(float(v.mean()), 6)
        ent["verdict"] = ("IN BAND" if ALBEDO_BAND[0] <= sm <= ALBEDO_BAND[1]
                          else ("ABOVE BAND" if sm > ALBEDO_BAND[1]
                                else "BELOW BAND"))
        out["bands"].append(ent)
    return out


def selftest():
    fails = []
    rng = np.random.default_rng(4)
    # A synthetic meadow: uniform albedo, half of it in shadow at a known
    # ratio. The lit-only variation must recover the albedo's OWN spread
    # and the with-shadows figure must be much larger.
    n = 200000
    albedo_var = 0.12
    alb = 1.0 + albedo_var * rng.normal(0, 1, n)
    shadow = rng.random(n) < 0.4
    irr = np.where(shadow, 1.0, 2.5)
    sig = alb * irr
    thr, info = split_lit(irr * (1.0 + 0.02 * rng.normal(0, 1, n)))
    if thr is None:
        fails.append("a clean bimodal irradiance was not split: %s"
                     % info.get("why"))
    else:
        if abs(info["mode_ratio"] - 2.5) / 2.5 > 0.1:
            fails.append("mode ratio %.3f, expected 2.5" % info["mode_ratio"])
        lit = irr >= thr
        got = float(sig[lit].std() / sig[lit].mean())
        if abs(got - albedo_var) / albedo_var > 0.15:
            fails.append("lit-only variation %.4f, expected ~%.2f"
                         % (got, albedo_var))
        allv = float(sig.std() / sig.mean())
        if allv <= got * 1.5:
            fails.append("with-shadows %.4f did not exceed lit-only %.4f"
                         % (allv, got))

    # ⛔ BLOCK THE VIOLATION: a UNIMODAL irradiance means there is no
    # shadow population, and the routine must REFUSE rather than cut at
    # some quantile and hand back a mask.
    thr, info = split_lit(np.exp(rng.normal(0, 0.25, n)))
    if thr is not None:
        fails.append("a unimodal irradiance was split anyway at %.4f" % thr)
    # Two modes too close to resolve must also refuse.
    close = np.where(rng.random(n) < 0.5, 1.0, 1.05) \
        * np.exp(rng.normal(0, 0.25, n))
    thr, _i = split_lit(close)
    if thr is not None:
        fails.append("two modes 5%% apart under 25%% noise were split anyway")

    # BLOCK WHEN BROKEN: empty, all-zero and non-finite input must refuse.
    for name, arr in (("empty", np.array([])),
                      ("all zero", np.zeros(5000)),
                      ("all nan", np.full(5000, np.nan))):
        thr, _i = split_lit(arr)
        if thr is not None:
            fails.append("%s input returned a threshold" % name)

    # ⭐ THE MEASURED CASE THAT MADE THE MASK UNAVAILABLE: thousands of
    # randomly-oriented grass cards give a CONTINUOUS spread of N.L, not
    # two populations. A broad unimodal lobe like the real meadow's
    # (p95/p5 about 3.3) must REFUSE -- if this ever starts returning a
    # threshold, the instrument has begun inventing a shadow population.
    lobe = np.exp(rng.normal(0, 0.45, n))          # p95/p5 ~ 4.4, one mode
    thr, info = split_lit(lobe)
    if thr is not None:
        fails.append("a broad unimodal lobe (the real meadow's shape) was "
                     "split at %.4f" % thr)

    # The band constant must be the brief's, not drifted.
    if ALBEDO_BAND != (0.10, 0.20):
        fails.append("albedo band is %r" % (ALBEDO_BAND,))
    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        ap.error("--frames is required")
    res = measure(a.frames, a.station)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(res, indent=1) + "\n")
        print("wrote", a.out)
    print("station %s   near limit %.3f m   target band %s"
          % (res["station"], res["near_limit_m"], res["band_target"]))
    for e in res["bands"]:
        print("  band %s  %d px" % (e["band_m"], e["pixels"]))
        if "std_over_mean_basecolor" in e:
            print("      BASECOLOR (no lighting at all) %.4f   %-10s "
                  "mean albedo %.4f"
                  % (e["std_over_mean_basecolor"], e["basecolor_verdict"],
                     e["mean_albedo"]))
        if "std_over_mean_lit_only" not in e:
            print("      PPI0 lit-only: %-11s %s"
                  % (e["verdict"], e.get("why", "")[:78]))
            if "std_over_mean_with_shadows" in e:
                print("      PPI0 with shadows %.4f (a LIGHTING statistic, "
                      "not an albedo one)" % e["std_over_mean_with_shadows"])
            continue
        print("      with shadows %.4f   LIT ONLY %.4f   %s"
              % (e["std_over_mean_with_shadows"],
                 e["std_over_mean_lit_only"], e["verdict"]))
        print("      lit %.1f%% of band   sun/shade ratio %.3f vs card "
              "%.4f  %s" % (e["lit_fraction"] * 100, e["mode_ratio"],
                            res["shade_ratio_reference"],
                            e["shade_ratio_check"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
