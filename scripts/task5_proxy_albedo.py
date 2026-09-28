"""task5_proxy_albedo.py -- Task 5: does the 4096 HLOD bake preserve albedo?

    python scripts/task5_proxy_albedo.py \
        --proxy <player.exr> --real <truth.exr> --depth <player SceneDepth.png> \
        --station <name> [--out <json>]
    python scripts/task5_proxy_albedo.py --selftest

PROXY = the player capture (HLODs on): at 300-1000 m the landscape is the
4096-baked HLOD proxy. REAL = the --truth capture (disable_hlods +
use_lod_zero): the SAME camera view rendered with the real landscape
material at LOD0. Same rays -> same world points, so the far bin is a
per-pixel proxy-vs-real comparison; the truth instrument is a DIFFERENT
representation of the ground truth (non-negotiable 0), not the proxy
grading itself.

Albedo = FinalImageBaseColor / 2^compensation_ev (B3.16: the BaseColor
GBuffer carries the bench's exposure exactly as the lit passes do; divide
it out and the result is reflectance, bounded by ~1).

PER LAYER, self-contained: the far-bin pixels are clustered by their REAL
albedo (1-D k-means, k up to 5 for the 5 surfaces). Each cluster IS a
layer; the check is that the proxy preserves that cluster's real median
albedo within +/-15%. No external albedo library is needed -- the truth
capture measures the real per-layer albedo. Snow's known 0.836 (B3.10)
anchors the brightest cluster's label only.

Depth: the player SceneDepth PNG via haze_metrics.decode_depth_m (the
multilayer depth channel is post-processed and unreliable).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402

MIN_CLUSTER_PX = 2000
TOL = 0.15
BIN = (300.0, 1000.0)
SNOW_ALBEDO = 0.8357  # B3.10, the one current-surface albedo on record


def basecolor_albedo(exr_path, comp_ev, channel="FinalImageBaseColor"):
    import OpenEXR
    f = OpenEXR.File(exr_path)
    chans = f.channels()
    if channel not in chans:
        raise ValueError("no channel %r in %s; found %s"
                         % (channel, exr_path, list(chans.keys())))
    bc = np.asarray(chans[channel].pixels)[..., :3].astype(np.float64)
    lum = 0.2126 * bc[..., 0] + 0.7152 * bc[..., 1] + 0.0722 * bc[..., 2]
    return lum / (2.0 ** comp_ev)


def kmeans1d(x, k, iters=50):
    """Deterministic 1-D k-means: seed on quantiles, Lloyd iterations."""
    x = np.asarray(x, dtype=np.float64)
    qs = np.linspace(0.0, 1.0, k + 2)[1:-1]
    centers = np.quantile(x, qs)
    for _ in range(iters):
        d = np.abs(x[:, None] - centers[None, :])
        lab = d.argmin(axis=1)
        new = np.array([x[lab == j].mean() if np.any(lab == j) else centers[j]
                        for j in range(k)])
        if np.allclose(new, centers):
            centers = new
            break
        centers = new
    d = np.abs(x[:, None] - centers[None, :])
    lab = d.argmin(axis=1)
    return centers, lab


def label_for(real_med):
    if real_med >= 0.55:
        return "snow-like (anchor Snow007A %.3f)" % SNOW_ALBEDO
    if real_med >= 0.28:
        return "bright ground (meadow/forest-floor-like)"
    if real_med >= 0.13:
        return "mid (rock-like)"
    return "dark (scree/gravel-like)"


def analyse(proxy_alb, real_alb, depth_m, k=5):
    mask = (depth_m >= BIN[0]) & (depth_m < BIN[1]) & (depth_m < CEILING_M * 0.999)
    n = int(mask.sum())
    out = {"bin_m": list(BIN), "pixels": n}
    if n < MIN_CLUSTER_PX:
        out["verdict"] = "NO VERDICT"
        out["_why"] = ("%d px in the 300-1000 m bin -- too few to segment; "
                       "a fact about the station" % n)
        return out
    pr = proxy_alb[mask]
    re = real_alb[mask]
    out["overall"] = {
        "real_median": round(float(np.median(re)), 5),
        "proxy_median": round(float(np.median(pr)), 5),
        "delta_pct": round(100.0 * (np.median(pr) - np.median(re))
                           / np.median(re), 3) if np.median(re) > 0 else None,
    }
    out["overall"]["within_15pc"] = bool(
        out["overall"]["delta_pct"] is not None
        and abs(out["overall"]["delta_pct"]) <= TOL * 100)
    # cap k so no cluster is starved
    k = max(1, min(k, n // MIN_CLUSTER_PX))
    centers, lab = kmeans1d(re, k)
    order = np.argsort(centers)
    layers = []
    for j in order:
        sel = lab == j
        m = int(sel.sum())
        if m < MIN_CLUSTER_PX:
            continue
        rm = float(np.median(re[sel]))
        pm = float(np.median(pr[sel]))
        dpct = 100.0 * (pm - rm) / rm if rm > 0 else None
        layers.append({
            "label": label_for(rm), "pixels": m,
            "real_median_albedo": round(rm, 5),
            "proxy_median_albedo": round(pm, 5),
            "delta_pct": round(dpct, 3) if dpct is not None else None,
            "within_15pc": bool(dpct is not None and abs(dpct) <= TOL * 100),
        })
    out["layers"] = layers
    checked = [L for L in layers if L["delta_pct"] is not None]
    out["verdict"] = ("PASS" if (out["overall"]["within_15pc"]
                                 and checked
                                 and all(L["within_15pc"] for L in checked))
                      else "FAIL")
    out["acceptance"] = ("proxy median albedo within +/-15%% of real, overall "
                         "and per real-albedo cluster (>= %d px)" % MIN_CLUSTER_PX)
    return out


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-58s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond

    h = w = 300
    depth = np.full((h, w), 650.0)
    depth[:10, :] = 5000.0                       # some out-of-bin pixels
    # three real layers: dark 0.05, mid 0.18, bright 0.80
    real = np.zeros((h, w))
    real[:100] = 0.05
    real[100:200] = 0.18
    real[200:] = 0.80
    proxy = real.copy()
    r = analyse(proxy, real, depth, k=5)
    check("identical proxy==real -> PASS", r["verdict"] == "PASS")
    check("clusters recovered (3 layers with pixels)",
          len([L for L in r["layers"] if L["pixels"] >= 2000]) == 3)
    check("overall delta ~ 0", abs(r["overall"]["delta_pct"]) < 1e-6)
    proxy2 = real.copy()
    proxy2[200:] = 0.80 * 1.25                    # snow layer +25% in the proxy
    r2 = analyse(proxy2, real, depth, k=5)
    snow = [L for L in r2["layers"] if L["real_median_albedo"] > 0.5][0]
    check("a +25% proxy shift on one layer FAILS that layer",
          snow["within_15pc"] is False and r2["verdict"] == "FAIL")
    check("the unshifted layers still pass",
          all(L["within_15pc"] for L in r2["layers"]
              if L["real_median_albedo"] < 0.5))
    empty = np.full((h, w), 5000.0)
    r3 = analyse(proxy, real, empty)
    check("no far-bin pixels -> NO VERDICT (rule 13)",
          r3["verdict"] == "NO VERDICT")
    print("selftest %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy")
    ap.add_argument("--real")
    ap.add_argument("--depth")
    ap.add_argument("--station", default="")
    ap.add_argument("--comp-ev", type=float, default=None,
                    help="override; default reads the recipe's "
                         "lighting.exposure.compensation_ev (pipeline rule 2)")
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.proxy and a.real and a.depth):
        ap.error("--proxy, --real and --depth required (or --selftest)")
    comp_ev = a.comp_ev
    if comp_ev is None:
        comp_ev = float(json.load(open(a.recipe, encoding="utf-8-sig"))
                        ["lighting"]["exposure"]["compensation_ev"])
    proxy = basecolor_albedo(a.proxy, comp_ev)
    real = basecolor_albedo(a.real, comp_ev)
    depth = decode_depth_m(a.depth)
    if not (proxy.shape == real.shape == depth.shape):
        print("REFUSE: shape mismatch proxy %s real %s depth %s"
              % (proxy.shape, real.shape, depth.shape))
        return 3
    r = analyse(proxy, real, depth)
    r["station"] = a.station
    r["comp_ev"] = comp_ev
    r["proxy_exr"] = os.path.abspath(a.proxy)
    r["real_exr"] = os.path.abspath(a.real)
    r["instrument"] = "basecolor: proxy=player HLOD, real=truth LOD0"
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
