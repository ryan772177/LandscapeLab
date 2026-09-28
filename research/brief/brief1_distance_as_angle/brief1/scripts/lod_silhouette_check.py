"""lod_silhouette_check.py — judge a LOD chain by what the EYE gets, not
by triangle count. (LESSONS 2026-08-14: "the LOD chain hit its triangle
targets exactly and destroyed the canopy".)

Input: one render per LOD of the same mesh, same camera, on a flat
uniform background (e.g. pure magenta 255,0,255 or an alpha channel),
plus the pixel height at which each LOD is meant to first appear (from
angular_budget.py or the recipe's screen sizes).

For each LOD i:
  1. extract the mask (alpha, or distance from the key colour)
  2. resample LOD0's mask AND LOD i's mask down to the target pixel
     height at which LOD i appears (box filter = what the display does)
  3. report
       coverage_ratio   = area(LOD i) / area(LOD0)        (canopy loss)
       silhouette_iou   = |A & B| / |A | B|              (shape change)
       edge_error_px    = mean distance of LOD i edge to LOD0 edge
       luma_delta       = mean |L_i - L_0| inside BOTH silhouettes, Weber-normed
                          (visible on switch if > jnd over > min blob)
  4. verdict per transition, against thresholds:
       coverage >= 0.85, IoU >= 0.80, luma_delta <= 0.03 at the switch
     A chain can hit 10x fewer triangles and still pass, or hit its
     triangle target and fail — which is the point.

Usage
  python lod_silhouette_check.py --lod LOD0.png 400 --lod LOD1.png 120 \
      --lod LOD2.png 40 --lod LOD3.png 12 [--key 255 0 255] [--out r.json]
  python lod_silhouette_check.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from PIL import Image


def load_mask_and_luma(path, key):
    im = Image.open(path)
    if im.mode == "RGBA":
        a = np.asarray(im).astype(np.float64)
        mask = a[..., 3] > 127
        rgb = a[..., :3] / 255.0
    else:
        a = np.asarray(im.convert("RGB")).astype(np.float64)
        d = np.sqrt(((a - np.array(key)) ** 2).sum(-1))
        mask = d > 60
        rgb = a / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    luma = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    return mask, luma


def box_down(arr, factor):
    if factor <= 1:
        return arr.astype(np.float64)
    h, w = arr.shape
    h2, w2 = h // factor * factor, w // factor * factor
    a = arr[:h2, :w2].astype(np.float64)
    return a.reshape(h2 // factor, factor, w2 // factor, factor).mean(axis=(1, 3))


def edge(mask):
    m = mask > 0.5
    e = m ^ np.roll(m, 1, 0) | m ^ np.roll(m, 1, 1)
    return e


def mean_edge_distance(e_a, e_b):
    ya, xa = np.nonzero(e_a); yb, xb = np.nonzero(e_b)
    if ya.size == 0 or yb.size == 0:
        return float("nan")
    # subsample for cost
    sel = np.linspace(0, ya.size - 1, min(ya.size, 400)).astype(int)
    d = []
    for y, x in zip(ya[sel], xa[sel]):
        d.append(np.sqrt((yb - y) ** 2 + (xb - x) ** 2).min())
    return float(np.mean(d))


def compare(mask0, luma0, maski, lumai, target_px, thresholds):
    h0 = int(mask0.any(axis=1).sum())  # object height in px at render
    factor = max(1, int(round(h0 / max(target_px, 1))))
    m0 = box_down(mask0, factor); mi = box_down(maski, factor)
    l0 = box_down(luma0 * mask0, factor); li = box_down(lumai * maski, factor)
    a0 = m0.sum(); ai = mi.sum()
    inter = np.minimum(m0, mi).sum(); union = np.maximum(m0, mi).sum()
    # luma is judged INSIDE both silhouettes (shading change); the edge is
    # already scored by IoU/edge_error, and mixing them double-counts
    u = np.minimum(m0, mi) > 0.5
    wl = np.abs(li - l0)[u] / np.maximum((li + l0)[u] / 2.0, 0.01)
    r = {"render_px_tall": h0, "target_px_tall": target_px, "downsample": factor,
         "coverage_ratio": round(float(ai / a0) if a0 else 0.0, 4),
         "silhouette_iou": round(float(inter / union) if union else 0.0, 4),
         "edge_error_px": round(mean_edge_distance(edge(m0), edge(mi)), 3),
         "luma_delta_weber": round(float(wl.mean()) if wl.size else 0.0, 4)}
    fails = []
    if r["coverage_ratio"] < thresholds["coverage"]:
        fails.append("coverage %.2f < %.2f (canopy/volume lost)" % (r["coverage_ratio"], thresholds["coverage"]))
    if r["silhouette_iou"] < thresholds["iou"]:
        fails.append("silhouette IoU %.2f < %.2f (shape changed)" % (r["silhouette_iou"], thresholds["iou"]))
    if r["luma_delta_weber"] > thresholds["luma"]:
        fails.append("luma delta %.3f > %.3f (visible brightness step at switch)" % (r["luma_delta_weber"], thresholds["luma"]))
    r["verdict"] = "PASS" if not fails else "FAIL: " + "; ".join(fails)
    return r


def selftest():
    rng = np.random.default_rng(3)
    H = W = 512
    yy, xx = np.mgrid[0:H, 0:W]
    # LOD0: a cone-ish tree: triangle mask
    tree = (np.abs(xx - 256) < (yy - 40) * 0.35) & (yy > 40) & (yy < 480)
    # LOD1: same silhouette, slightly eroded (fine)
    lod1 = (np.abs(xx - 256) < (yy - 40) * 0.33) & (yy > 44) & (yy < 480)
    # LOD2: canopy destroyed: only the trunk
    lod2 = (np.abs(xx - 256) < 12) & (yy > 40) & (yy < 480)
    def img(m, bright):
        rgb = np.full((H, W, 3), [255, 0, 255], dtype=np.uint8)
        rgb[m] = int(bright)
        return Image.fromarray(rgb)
    files = {}
    for name, m, b in (("l0", tree, 90), ("l1", lod1, 90), ("l2", lod2, 90)):
        p = "/tmp/_lod_%s.png" % name; img(m, b).save(p); files[name] = p
    key = (255, 0, 255)
    m0, l0 = load_mask_and_luma(files["l0"], key)
    th = {"coverage": 0.85, "iou": 0.80, "luma": 0.03}
    r1 = compare(m0, l0, *load_mask_and_luma(files["l1"], key), 120, th)
    r2 = compare(m0, l0, *load_mask_and_luma(files["l2"], key), 40, th)
    ok = r1["verdict"] == "PASS" and r2["verdict"].startswith("FAIL")
    print("selftest:", "PASS" if ok else "FAIL")
    print(json.dumps({"lod1": r1, "lod2": r2}, indent=1))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lod", nargs=2, action="append", metavar=("PNG", "TARGET_PX"))
    ap.add_argument("--key", type=int, nargs=3, default=(255, 0, 255))
    ap.add_argument("--coverage", type=float, default=0.85)
    ap.add_argument("--iou", type=float, default=0.80)
    ap.add_argument("--luma", type=float, default=0.03)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.lod or len(a.lod) < 2:
        print("give --lod LOD0.png px --lod LOD1.png px ..."); return 2
    th = {"coverage": a.coverage, "iou": a.iou, "luma": a.luma}
    m0, l0 = load_mask_and_luma(a.lod[0][0], a.key)
    out = {"lod0": a.lod[0][0], "thresholds": th, "lods": []}
    for i, (p, px) in enumerate(a.lod[1:], 1):
        mi, li = load_mask_and_luma(p, a.key)
        r = compare(m0, l0, mi, li, float(px), th); r["file"] = p; r["lod"] = i
        out["lods"].append(r)
    js = json.dumps(out, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
