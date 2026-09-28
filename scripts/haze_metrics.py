"""haze_metrics.py — aerial perspective binned by TRUE DISTANCE.

RULED 2026-09-09, replacing a row-banded version. The old metric split the
region below the skyline into IMAGE ROWS (far = top 40%, near = bottom 30%)
and called that distance. Rows are only a proxy for depth when the frame
actually contains depth: at near_ground the "far" rows are shaded canopy a few
hundred metres away, so `haze_rise` reported CANOPY SHADOW with a minus sign
and no fog density could move it. R-FOG strikes those lines for that station.

    ROWS ARE NOT DEPTH. Bin by depth.

DEPTH SOURCE. `bench_capture.py --depth` renders an additional post-process
pass through the authored material /Game/Bench/M_SceneDepth. There is no
depth pass class in 5.8, so depth arrives as an AdditionalPostProcessMaterial;
the material emits log2 depth because MRQ writes that pass as an 8-bit PNG and
raw centimetres clamp to white (measured: two unique values in a 4K frame).

    encoded  = log2(max(depth_cm, 1)) / 20          in the material
    depth_m  = 2 ** (srgb_to_linear(px/255) * 20) / 100

THE sRGB STEP IS NOT OPTIONAL AND WAS NOT ASSUMED. MRQ writes the pass
sRGB-encoded. Validated against camera geometry rather than by preference: at
near_ground the camera sits 1.75 m above ground at pitch -2 deg with a 58.72
deg vertical FOV, so the bottom of frame looks 31.36 deg below the horizon and
the ground there must be 1.75/sin(31.36) = 3.36 m away. Decoding through sRGB
measures 3.28 m; reading the bytes as linear gives 121.50 m. One of those is
the geometry and the other is 36x wrong.

WHAT IS MEASURED, PER DISTANCE BIN

    p10 luma    the blacks. Aerial perspective LIFTS them: inscattered light
                fills shadows, so far bins should have higher p10 than near.
    luma std    the contrast. Transmittance scales scene contrast toward the
                sky's uniform value, so far bins should have lower std.
    predicted T fog_budget's transmittance at the bin's representative
                distance, from the recipe's own fog numbers.

ACCEPTANCE
    1. p10 luma RISES monotonically with distance (blacks lift), and
    2. luma std FALLS monotonically with distance (contrast drops), and
    3. each bin's measured contrast ratio (std_bin / std_nearest) is within
       +/-30% of that bin's predicted transmittance.

(3) is the one that makes this a physical check rather than a vibe: Beer-
Lambert says a distant object's contrast is scaled by T, so if the fog is
doing what the recipe says, the measured contrast ratio IS the transmittance.
A world can satisfy (1) and (2) by accident of content; satisfying (3) means
the haze matches the model that was solved for.

SKY IS EXCLUDED by depth, not by colour -- anything at or beyond the
encoding's 10.49 km ceiling is sky or beyond the world and carries no
transmittance information.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fog_budget import transmittance  # noqa: E402

LOG_DIVISOR = 20.0
CEILING_M = (2.0 ** LOG_DIVISOR) / 100.0          # 10485.76 m
BINS = [(0.0, 100.0), (100.0, 300.0), (300.0, 1000.0),
        (1000.0, 3000.0), (3000.0, 8000.0)]


def srgb_to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def decode_depth_m(path):
    px = np.asarray(Image.open(path).convert("RGB")).astype(np.float64)[..., 0] / 255.0
    return (2.0 ** (srgb_to_linear(px) * LOG_DIVISOR)) / 100.0


def luma_linear(path):
    srgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    lin = srgb_to_linear(srgb)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def measure(beauty, depth, fog, cam_z_m, datum_m, exclude_rect_px=None):
    lm = luma_linear(beauty)
    dm = decode_depth_m(depth)
    if lm.shape != dm.shape:
        return {"error": "beauty %s and depth %s differ in shape"
                         % (lm.shape, dm.shape)}
    # The grey card (R-GREYCARD) sits a few metres out -- squarely in the
    # nearest bin -- and is a synthetic 18% plane, not aerial perspective.
    excl = np.zeros(lm.shape, dtype=bool)
    if exclude_rect_px:
        x0, y0, x1, y1 = exclude_rect_px
        excl[max(0, y0):y1, max(0, x0):x1] = True
    rows = []
    for lo, hi in BINS:
        m = (dm >= lo) & (dm < hi) & (dm < CEILING_M * 0.999) & ~excl
        n = int(m.sum())
        rep = (lo + hi) / 2.0   # lo==0 gives hi/2 anyway, so no special case
        T = transmittance(fog["density"], fog["falloff"], datum_m * 100.0,
                          cam_z_m * 100.0, rep * 100.0)
        row = {"bin_m": [lo, hi], "pixels": n,
               "representative_m": rep, "predicted_T": round(T, 5)}
        if n >= 500:
            v = lm[m]
            row["p10_luma"] = round(float(np.percentile(v, 10)), 5)
            row["luma_std"] = round(float(v.std()), 5)
            row["median_luma"] = round(float(np.median(v)), 5)
        rows.append(row)

    # MONOTONICITY IS JUDGED OVER POPULATED BINS ONLY (ruled 2026-09-09).
    # An empty bin is NO VERDICT for that bin, not a failure and not a pass:
    # it means the frame does not reach that distance, which is a fact about
    # the STATION. near_ground's 3-8 km bin holds zero pixels because a
    # ground-level camera in a valley cannot see 8 km, and treating that as a
    # broken monotonic chain would charge the world for the station's
    # geometry. The bins that ARE populated still have to behave.
    have = [r for r in rows if "luma_std" in r]
    empty = [r for r in rows if "luma_std" not in r]
    for r in empty:
        r["verdict"] = "NO VERDICT"
        r["_why"] = ("%d pixels -- this frame does not reach %g-%g m, which "
                     "is a fact about the station, not about the fog"
                     % (r["pixels"], r["bin_m"][0], r["bin_m"][1]))
    out = {"beauty": beauty.replace("\\", "/"), "depth": depth.replace("\\", "/"),
           "bins": rows, "populated_bins": len(have),
           "no_verdict_bins": ["%g-%g" % tuple(r["bin_m"]) for r in empty],
           "_judging_rule": ("monotonicity is judged over POPULATED bins only; "
                             "an empty bin is NO VERDICT for that bin")}
    if len(have) < 2:
        out["verdict"] = "NO VERDICT"
        out["_why"] = ("only %d bin(s) have enough pixels -- this frame does "
                       "not span distance, so there is nothing here to "
                       "measure. That is a fact about the STATION, not a "
                       "failure of the world." % len(have))
        return out

    base = have[0]
    for r in have:
        r["contrast_ratio"] = (round(r["luma_std"] / base["luma_std"], 5)
                               if base["luma_std"] else None)
        if r["contrast_ratio"] is not None and r["predicted_T"] > 0:
            r["contrast_vs_predicted"] = round(
                (r["contrast_ratio"] - r["predicted_T"]) / r["predicted_T"], 4)
            r["within_30pc"] = abs(r["contrast_vs_predicted"]) <= 0.30

    p10s = [r["p10_luma"] for r in have]
    stds = [r["luma_std"] for r in have]
    out["blacks_rise_monotonic"] = all(b >= a - 1e-9 for a, b in zip(p10s, p10s[1:]))
    out["contrast_falls_monotonic"] = all(b <= a + 1e-9 for a, b in zip(stds, stds[1:]))
    checked = [r for r in have[1:] if "within_30pc" in r]
    out["contrast_matches_model"] = bool(checked) and all(
        r["within_30pc"] for r in checked)
    out["verdict"] = ("PASS" if (out["blacks_rise_monotonic"]
                                 and out["contrast_falls_monotonic"]
                                 and out["contrast_matches_model"])
                      else "FAIL")
    out["acceptance"] = ("blacks rise and contrast falls monotonically with "
                         "distance; contrast ratio within +/-30% of predicted T")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--beauty", required=True)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--cam-z", type=float, required=True, help="camera Z, m")
    ap.add_argument("--greycard-station", default=None,
                    help="exclude this station's grey-card region "
                         "(R-GREYCARD) from every bin")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    rec = json.load(open(a.recipe, encoding="utf-8-sig"))["lighting"]["fog"]
    fog = {"density": float(rec["density"]),
           "falloff": 10.0 / float(rec["half_height_m"])}
    gc = None
    if a.greycard_station:
        import greycard
        gc = greycard.region_for(a.greycard_station)
        if gc is None:
            print("REFUSE: --greycard-station %r has no recorded region "
                  "-- run greycard --place first" % a.greycard_station)
            return 2
    r = measure(a.beauty, a.depth, fog, a.cam_z,
                float(rec["height_datum_m"]), exclude_rect_px=gc)
    if r.get("error"):
        # a shape mismatch (or any measure() refusal) is NOT a verdict — do
        # not fall through to the table and print "None -> None" at exit 0.
        print("  ERROR: %s" % r["error"])
        return 1
    r["fog_used"] = {"density": fog["density"], "falloff": round(fog["falloff"], 6),
                     "half_height_m": rec["half_height_m"],
                     "datum_m": rec["height_datum_m"]}

    print("  %-13s %8s %9s %9s %9s %9s %7s"
          % ("bin (m)", "pixels", "p10", "std", "ratio", "pred_T", "±30%"))
    for b in r.get("bins", []):
        lo, hi = b["bin_m"]
        if "luma_std" not in b:
            print("  %-13s %8d   (too few pixels)" % ("%g-%g" % (lo, hi), b["pixels"]))
            continue
        print("  %-13s %8d %9.5f %9.5f %9s %9.5f %7s"
              % ("%g-%g" % (lo, hi), b["pixels"], b["p10_luma"], b["luma_std"],
                 ("%.5f" % b["contrast_ratio"]) if b.get("contrast_ratio") is not None else "-",
                 b["predicted_T"],
                 ("yes" if b.get("within_30pc") else "no") if "within_30pc" in b else "-"))
    print("  blacks rise %s | contrast falls %s | matches model %s -> %s"
          % (r.get("blacks_rise_monotonic"), r.get("contrast_falls_monotonic"),
             r.get("contrast_matches_model"), r.get("verdict")))
    if r.get("_why"):
        print("  %s" % r["_why"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
