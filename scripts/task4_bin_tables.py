"""task4_bin_tables.py — meadow luminance variation per DEPTH BIN.

    python scripts/task4_bin_tables.py --selftest
    python scripts/task4_bin_tables.py --frames <dir> [<dir> ...] \
        --station ground --channel FinalImage
    python scripts/task4_bin_tables.py --frames <dir> --channel BaseColor

⭐ WHY BINS AND NOT ONE NUMBER. Task 4's acceptance was a single band
(0.10-0.20) over 1-4 m. That band is unusable here for two measured
reasons: the 1-4 m band DOES NOT EXIST at a 1.70 m camera (the frame's
nearest non-sky pixel is 4.110 m, because the bottom of frame looks
29.36 deg below the horizon and flat ground enters view at 3.47 m), and
the statistic is strongly distance-dependent, so a band quoted without
its distance is the same class of error as a shade band quoted without
its white point (B3.8/B3.12). RULED 2026-09-13: report per bin over
4-10, 10-30, 30-100 and 100-300 m and let the desk derive the band from
the reference spread.

TWO CHANNELS, AND THEY ANSWER DIFFERENT QUESTIONS.

  FinalImage   display-referred luminance, shadows INCLUDED. This is the
               metric a PHOTOGRAPH can also give, which is the whole
               point -- it is the only one of the two that a reference
               image can be measured on. Requires the TONE CURVE ON.

  BaseColor    GBuffer albedo, lighting never applied. Divided by
               2^compensation_ev, and asserted to land in a plausible
               albedo range. Requires the tone curve OFF (--linear): the
               pass is written at BL_SCENE_COLOR_AFTER_DOF and the
               tonemapper still runs on it afterwards, so with the curve
               ON this is not a linear albedo at all.

⛔ EACH CHANNEL REFUSES THE WRONG CAPTURE rather than returning a number
from it. Measured 2026-09-13, same station and code state, tone curve
the only difference: the tiling Michelson moves by ~1.4x and Rock's peak
appears only with the curve on. A channel read off the wrong capture is
the silent-wrong class.

⭐ EVERY NUMBER IS A MEAN OVER CAPTURES WITH ITS SPREAD. A single-capture
figure has unknown variance, and this project has already published one
("5 of 6 measurable PASS") that three later captures contradicted. Pass
as many --frames as you have. With one, the spread is reported as None
and the row says so rather than implying zero.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402
from task3_layer_tables import (CAMS, LUMA, RECIPE,  # noqa: E402
                                layer_index_map, tone_curve_state, world_xy)
import exr_card  # noqa: E402

MEADOW_LAYER = "Grass"
BINS = [(4.0, 10.0), (10.0, 30.0), (30.0, 100.0), (100.0, 300.0)]
MIN_PX = 5000
COMPENSATION_EV = -13.5898
# A GBuffer albedo has to be a reflectance. Anything outside this after
# the exposure divide means the divide is wrong, not that the world is.
ALBEDO_PLAUSIBLE = (0.01, 1.0)


def read_channel(frames, station, channel):
    """(gray, depth) for one capture, refusing a capture of the wrong kind."""
    exr = os.path.join(frames, "%s.exr" % station)
    dep = os.path.join(frames, "%sFinalImageSceneDepth.png" % station)
    for p in (exr, dep):
        if not os.path.exists(p):
            raise SystemExit("missing %s" % p)
    disabled, sidecar = tone_curve_state(frames)
    if channel == "FinalImage":
        if disabled:
            raise SystemExit(
                "REFUSE: %s has the tone curve DISABLED. The FinalImage "
                "metric is the display-referred one a PHOTOGRAPH can also "
                "give; off a linear capture it is not that number."
                % os.path.basename(frames))
        rgb = exr_card.read_rgb(exr, None)
        scale = 1.0
    elif channel == "BaseColor":
        if disabled is False:
            raise SystemExit(
                "REFUSE: %s has the tone curve ON. The BaseColor pass is "
                "written at BL_SCENE_COLOR_AFTER_DOF and the tonemapper "
                "still runs on it, so with the curve on this is not a "
                "linear albedo. Re-capture with --linear."
                % os.path.basename(frames))
        rgb = exr_card.read_rgb(exr, "FinalImageBaseColor")
        scale = 2.0 ** COMPENSATION_EV
    else:
        raise SystemExit("unknown channel %r" % channel)
    gray = (rgb[..., :3] @ np.array(LUMA)) / scale
    return gray, decode_depth_m(dep), sidecar


def measure_one(frames, station, channel, recipe_path=RECIPE):
    rec = json.load(open(recipe_path, encoding="utf-8"))
    cam = json.load(open(CAMS, encoding="utf-8"))["cameras"][station]
    gray, depth, sidecar = read_channel(frames, station, channel)
    if gray.shape != depth.shape:
        raise SystemExit("passes disagree on size")
    h, w = depth.shape
    sky = depth > CEILING_M * 0.97
    wx, wy = world_xy(depth, cam, (w, h))
    lay, names = layer_index_map(wx, wy, rec)
    gi = names.index(MEADOW_LAYER)
    out = {"frames": os.path.basename(frames), "sidecar": sidecar, "bins": {}}
    if channel == "BaseColor":
        v = gray[(~sky) & (lay == gi)]
        if v.size:
            p99 = float(np.percentile(v, 99))
            out["albedo_p99"] = round(p99, 4)
            if not (ALBEDO_PLAUSIBLE[0] <= p99 <= ALBEDO_PLAUSIBLE[1]):
                raise SystemExit(
                    "REFUSE: meadow BaseColor p99 is %.4f after dividing by "
                    "2^%.4f. A GBuffer albedo must be a reflectance in "
                    "%s. The exposure divide is wrong."
                    % (p99, COMPENSATION_EV, ALBEDO_PLAUSIBLE))
    for lo, hi in BINS:
        m = (~sky) & (depth >= lo) & (depth <= hi) & (lay == gi)
        n = int(m.sum())
        if n < MIN_PX:
            out["bins"]["%g-%g" % (lo, hi)] = {
                "pixels": n, "std_over_mean": None,
                "why": "only %d meadow pixels, below the %d floor"
                       % (n, MIN_PX)}
            continue
        v = gray[m]
        out["bins"]["%g-%g" % (lo, hi)] = {
            "pixels": n,
            "mean": round(float(v.mean()), 6),
            "std_over_mean": round(float(v.std() / v.mean()), 4),
            "median_distance_m": round(float(np.median(depth[m])), 1),
            "metres_per_px": round(
                float(np.median(depth[m])) * (math.pi / 180.0)
                / (w / float(cam.get("fov_deg") or 90.0)), 5)}
    return out


def aggregate(runs):
    """Mean and spread per bin across captures. n=1 reports spread None."""
    keys = []
    for r in runs:
        for k in r["bins"]:
            if k not in keys:
                keys.append(k)
    rows = []
    for k in keys:
        vals = [r["bins"][k]["std_over_mean"] for r in runs
                if r["bins"].get(k, {}).get("std_over_mean") is not None]
        ent = {"bin_m": k, "n_captures": len(vals), "values": vals}
        one = next((r["bins"][k] for r in runs
                    if r["bins"].get(k, {}).get("std_over_mean") is not None),
                   None)
        if one:
            ent["pixels"] = one["pixels"]
            ent["median_distance_m"] = one["median_distance_m"]
            ent["metres_per_px"] = one["metres_per_px"]
        if not vals:
            ent["mean"] = None
            ent["why"] = next((r["bins"][k].get("why") for r in runs
                               if k in r["bins"]), "no data")
        else:
            ent["mean"] = round(float(np.mean(vals)), 4)
            ent["spread"] = (round(float(np.std(vals, ddof=1)), 5)
                             if len(vals) > 1 else None)
            if len(vals) == 1:
                ent["_spread_note"] = ("ONE capture: the spread is UNKNOWN, "
                                       "not zero")
        rows.append(ent)
    return rows


def selftest():
    fails = []
    rng = np.random.default_rng(7)
    # aggregate: mean and spread, and n=1 must not claim zero spread
    runs = [{"bins": {"a": {"std_over_mean": v, "pixels": 9, "mean": 1,
                            "median_distance_m": 1, "metres_per_px": 1}}}
            for v in (0.10, 0.12, 0.14)]
    r = aggregate(runs)[0]
    if abs(r["mean"] - 0.12) > 1e-9:
        fails.append("mean %r" % r["mean"])
    if abs(r["spread"] - 0.02) > 1e-9:
        fails.append("spread %r, expected 0.02" % r["spread"])
    r1 = aggregate(runs[:1])[0]
    if r1["spread"] is not None:
        fails.append("n=1 reported a spread of %r" % r1["spread"])
    if "_spread_note" not in r1:
        fails.append("n=1 did not say the spread is unknown")
    # a bin with no usable data must carry its reason, not a number
    r0 = aggregate([{"bins": {"a": {"std_over_mean": None,
                                    "why": "too few"}}}])[0]
    if r0["mean"] is not None or "why" not in r0:
        fails.append("an empty bin returned %r" % r0)
    # the constants are the ruled ones
    if BINS != [(4.0, 10.0), (10.0, 30.0), (30.0, 100.0), (100.0, 300.0)]:
        fails.append("bins drifted: %r" % (BINS,))
    if abs(COMPENSATION_EV + 13.5898) > 1e-9:
        fails.append("compensation drifted: %r" % COMPENSATION_EV)
    # std/mean itself, against a hand-computable case
    v = np.array([1.0, 2.0, 3.0])
    if abs(v.std() / v.mean() - (np.sqrt(2.0 / 3.0) / 2.0)) > 1e-12:
        fails.append("std/mean is not population std over mean")
    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", nargs="+")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--channel", default="FinalImage",
                    choices=["FinalImage", "BaseColor"])
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        ap.error("--frames is required")
    runs = [measure_one(f, a.station, a.channel) for f in a.frames]
    res = {"_what": "Task 4: meadow luminance variation per depth bin",
           "channel": a.channel, "station": a.station,
           "captures": [r["frames"] for r in runs],
           "compensation_ev": (COMPENSATION_EV if a.channel == "BaseColor"
                               else None),
           "per_capture": runs, "table": aggregate(runs)}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(res, indent=1) + "\n")
        print("wrote", a.out)
    print("channel %s   %d capture(s): %s"
          % (a.channel, len(runs), ", ".join(res["captures"])))
    print("  %-10s %9s %8s %9s %10s %s"
          % ("bin (m)", "px", "dist", "m/px", "std/mean", "spread"))
    for r in res["table"]:
        if r["mean"] is None:
            print("  %-10s %9s  %s" % (r["bin_m"], "-", r.get("why", "")[:50]))
            continue
        print("  %-10s %9d %8.1f %9.4f %10.4f %s"
              % (r["bin_m"], r["pixels"], r["median_distance_m"],
                 r["metres_per_px"], r["mean"],
                 ("+-%.5f" % r["spread"]) if r["spread"] is not None
                 else "UNKNOWN (n=1)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
