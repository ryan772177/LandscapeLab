"""task5_fog_contrast.py -- Task 5 fog acceptance on the SCENE-LINEAR PPI0 pass.

    python scripts/task5_fog_contrast.py --exr <multilayer.exr> \
        --depth <SceneDepth.png> --station <name> --cam-z <m> [--out <json>]
    python scripts/task5_fog_contrast.py --selftest

THE SAME METRIC AS haze_metrics (Brief 2 R-FOG): per depth bin, luminance
contrast = luma_std(bin) / luma_std(first populated bin); the fog model
predicts transmittance T at the bin's mean distance; acceptance is
contrast_ratio within +/-30% of predicted_T. The rationale
(haze_metrics:46): if the world is doing what the recipe says, the
measured contrast ratio IS the transmittance.

⭐ WHY PPI0 AND NOT FinalImage (closure B-1). haze_metrics reads the
FinalImage PNG, which carries the tonemap power law and the grade -- both
COMPRESS contrast non-linearly, so a contrast ratio read there is not the
physical transmittance. PPI0 (BL_SCENE_COLOR_AFTER_DOF, pre-tonemap,
exposure-linear) is scene-linear: luma_std ratios ARE the transmittance
the fog applied. The fog (height fog + aerial perspective) is upstream of
the tonemap, so it is present in PPI0. Instrument: ppi0.

⛔ DIAGNOSTIC ONLY, NOT THE ACCEPTANCE (closure D-1 item 3). B-1 showed
this luma_std contrast-ratio is OUT OF CLASS at elevated stations: the
near reference bin is a near-flat foreground sliver while the far bins are
high-variance mountains, so the ratio measures scene CONTENT (which rises
with distance), not fog -- and at altitude the fog is thin by design
(predicted T > 0.9). The Task 5 fog ACCEPTANCE is Brief 2's depth-pass
CONVERGENCE instrument (haze_metrics.measure: blacks rise + contrast falls
monotonically, contrast ratio within +/-30% of predicted T) at a VALLEY
station (Bench_ground, 300-650 m) where the fog column is thick and the
near reference is representative. This tool's `verdict` is reported as a
diagnostic; the acceptance verdict comes from haze_metrics.

Depth comes from the SceneDepth PNG via haze_metrics.decode_depth_m (the
multilayer EXR's depth CHANNEL is post-processed and unreliable -- it
reads 0.4-2.2 where cm are expected; the log-encoded PNG is the trusted
decode). Luminance is Rec.709 on the FinalImagePPI0 EXR channel.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fog_budget import transmittance  # noqa: E402
from haze_metrics import BINS, CEILING_M, decode_depth_m  # noqa: E402

REC709 = (0.2126, 0.7152, 0.0722)
MIN_PIXELS = 500
TOL = 0.30


def ppi0_luma(exr_path, channel="FinalImagePPI0"):
    import OpenEXR
    f = OpenEXR.File(exr_path)
    chans = f.channels()
    if channel not in chans:
        raise ValueError("no channel %r in %s; found %s"
                         % (channel, exr_path, list(chans.keys())))
    a = np.asarray(chans[channel].pixels)[..., :3].astype(np.float64)
    return REC709[0] * a[..., 0] + REC709[1] * a[..., 1] + REC709[2] * a[..., 2]


def contrast_rows(luma, depth_m, fog, cam_z_m, datum_m):
    rows = []
    for lo, hi in BINS:
        m = (depth_m >= lo) & (depth_m < hi) & (depth_m < CEILING_M * 0.999)
        n = int(m.sum())
        rep = (lo + hi) / 2.0 if lo > 0 else hi / 2.0
        T = transmittance(fog["density"], fog["falloff"], datum_m * 100.0,
                          cam_z_m * 100.0, rep * 100.0)
        row = {"bin_m": [lo, hi], "pixels": n,
               "representative_m": rep, "predicted_T": round(T, 5)}
        if n >= MIN_PIXELS:
            v = luma[m]
            row["luma_std"] = round(float(v.std()), 6)
            row["median_luma"] = round(float(np.median(v)), 6)
            row["p10_luma"] = round(float(np.percentile(v, 10)), 6)
        rows.append(row)
    have = [r for r in rows if "luma_std" in r]
    if have:
        base = have[0]
        for r in have:
            r["contrast_ratio"] = (round(r["luma_std"] / base["luma_std"], 5)
                                   if base["luma_std"] else None)
            if r["contrast_ratio"] is not None and r["predicted_T"] > 0:
                r["contrast_vs_predicted"] = round(
                    (r["contrast_ratio"] - r["predicted_T"]) / r["predicted_T"], 4)
                r["within_30pc"] = bool(abs(r["contrast_vs_predicted"]) <= TOL)
    return rows, have


def measure_arrays(luma, depth_m, fog, cam_z_m, datum_m):
    """Core measure on arrays, so the selftest can build its own inputs."""
    rows, have = contrast_rows(luma, depth_m, fog, cam_z_m, datum_m)
    out = {"instrument": "ppi0", "bins": rows, "populated_bins": len(have)}
    # THE ACCEPTANCE BIN is 300-1000 m (closure B-1).
    target = next((r for r in rows if r["bin_m"] == [300.0, 1000.0]), None)
    # If 300-1000 m is itself the FIRST populated bin, it is the contrast
    # BASELINE: its ratio is 1.0 by construction (luma_std/itself), so
    # judging it would compare the fog model against 1.0, not the image.
    # That is rule 13's "a read that returned nothing counted as
    # confirmation" -- refuse (haze_metrics excludes the base bin the same
    # way, haze_metrics.py:156).
    if have and have[0]["bin_m"] == [300.0, 1000.0]:
        out["target_bin_300_1000"] = None
        out["verdict"] = "NO VERDICT"
        out["_why"] = ("the 300-1000 m bin is the nearest populated bin, so "
                       "it IS the contrast baseline (ratio 1.0 by "
                       "construction) -- there is no nearer content to "
                       "measure attenuation against")
        return out
    if target is None or "within_30pc" not in target:
        out["target_bin_300_1000"] = None
        out["verdict"] = "NO VERDICT"
        out["_why"] = ("the 300-1000 m bin has %s -- this station does not "
                       "populate it, which is a fact about the station"
                       % (("%d px" % target["pixels"]) if target else "no bin"))
        return out
    out["target_bin_300_1000"] = {
        "pixels": target["pixels"],
        "representative_m": target["representative_m"],
        "predicted_T": target["predicted_T"],
        "contrast_ratio": target["contrast_ratio"],
        "contrast_vs_predicted": target["contrast_vs_predicted"],
        "base_bin_m": have[0]["bin_m"],
    }
    out["verdict"] = "PASS" if target["within_30pc"] else "FAIL"
    out["verdict_is"] = ("DIAGNOSTIC ONLY -- out of class at elevated stations "
                         "(B-1). The Task 5 fog ACCEPTANCE is haze_metrics' "
                         "convergence instrument at Bench_ground 300-650 m "
                         "(closure D-1 item 3).")
    out["acceptance"] = "300-1000 m contrast ratio within +/-30% of predicted T"
    return out


def measure(exr_path, depth_path, fog, cam_z_m, datum_m):
    luma = ppi0_luma(exr_path)
    depth_m = decode_depth_m(depth_path)
    if luma.shape != depth_m.shape:
        return {"error": "ppi0 %s and depth %s differ in shape"
                         % (luma.shape, depth_m.shape)}
    out = measure_arrays(luma, depth_m, fog, cam_z_m, datum_m)
    out["exr"] = exr_path.replace("\\", "/")
    out["depth"] = depth_path.replace("\\", "/")
    return out


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-56s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond

    # Synthetic: a near bin (T~1) and a far bin whose contrast is exactly
    # the predicted T of the far bin -> must PASS; scale it 50% off -> FAIL.
    fog = {"density": 0.00416, "falloff": 10.0 / 517.49}
    datum, cam = 186.74, 636.0
    # near bin ~50 m, far bin ~650 m
    T_far = transmittance(fog["density"], fog["falloff"], datum * 100,
                          cam * 100, 650 * 100)
    h = w = 200
    depth = np.full((h, w), 650.0)
    depth[:20, :] = 50.0                      # a near strip (base bin)
    rng = np.arange(w) / w
    luma = np.zeros((h, w))
    luma[:20, :] = rng                        # near contrast, std = s0
    luma[20:, :] = rng * T_far                # far contrast = s0 * T_far
    rows, have = contrast_rows(luma, depth, fog, cam, datum)
    far = next(r for r in rows if r["bin_m"] == [300.0, 1000.0])
    check("far-bin contrast ratio ~ predicted T (matches within 30%)",
          far.get("within_30pc") is True)
    check("...and the ratio itself is close to T",
          abs(far["contrast_ratio"] - far["predicted_T"]) < 0.05)
    luma[20:, :] = rng * T_far * 0.5          # far contrast half of T
    rows2, _ = contrast_rows(luma, depth, fog, cam, datum)
    far2 = next(r for r in rows2 if r["bin_m"] == [300.0, 1000.0])
    check("a far contrast 50% off predicted T FAILS the 30% band",
          far2.get("within_30pc") is False)
    empty = np.full((h, w), 5000.0)           # nothing in 300-1000
    rows3, _ = contrast_rows(luma, empty, fog, cam, datum)
    far3 = next(r for r in rows3 if r["bin_m"] == [300.0, 1000.0])
    check("an unpopulated far bin has no verdict (rule 13)",
          "within_30pc" not in far3 and far3["pixels"] == 0)
    # direction 4: when 300-1000 IS the only populated bin, it is the
    # baseline -> NO VERDICT, never a spurious PASS against T~1.
    only_far = np.full((60, 60), 650.0)
    only_luma = (np.arange(60) / 60.0)[None, :] * np.ones((60, 60))
    r4 = measure_arrays(only_luma, only_far, fog, cam, datum)
    check("300-1000 as the base bin refuses (not a PASS vs T~1)",
          r4["verdict"] == "NO VERDICT")
    print("selftest %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exr")
    ap.add_argument("--depth")
    ap.add_argument("--station", default="")
    ap.add_argument("--cam-z", type=float)
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.exr and a.depth and a.cam_z is not None):
        ap.error("--exr, --depth and --cam-z required (or --selftest)")
    rec = json.load(open(a.recipe, encoding="utf-8-sig"))["lighting"]["fog"]
    fog = {"density": float(rec["density"]),
           "falloff": 10.0 / float(rec["half_height_m"])}
    r = measure(a.exr, a.depth, fog, a.cam_z, float(rec["height_datum_m"]))
    r["station"] = a.station
    r["cam_z_m"] = a.cam_z
    r["fog_used"] = {"density": fog["density"], "falloff": round(fog["falloff"], 6),
                     "half_height_m": rec["half_height_m"],
                     "datum_m": rec["height_datum_m"]}
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
