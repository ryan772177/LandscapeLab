"""ground_station_map.py — a top-down map for PICKING a ground station.

RULED BY RYAN 2026-09-11: if the derived station misses twice, stop and
let Ryan pick from the top-down. This draws the SAME constraints the
search scored, so the pick is informed rather than blind:

    grey       hillshade (the sun the world actually has)
    green      MEADOW weight >= 0.55, the ground cover class
    dark red   TREE instances, from the PLACED plans
    markers    the two stations that were derived and MISSED, each
               labelled with what it PREDICTED and what it RENDERED

Concavity is computed and REPORTED but deliberately NOT drawn -- 98.6%
of cells have some concave azimuth, so it would colour the whole map and
look like information. That number is also why the v2 gate could never
have been the discriminator.

Offline. No editor.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from hillshade_snow_check import hillshade, sun_vector  # noqa: E402

FAILED = [
    ("v1", -68400.0, 243600.0, [405.0, 375.0], [55.0, 0.0]),
    ("v2", 373600.0, 269600.0, [354.0, 246.0], [11.0, 0.0]),
]


def concavity_map(h, sp_m, step=32, dists=(30.0, 300.0), n=10):
    """Best-over-azimuth mean second difference of height vs distance."""
    ny, nx = h.shape
    ys = np.arange(0, ny, step)
    xs = np.arange(0, nx, step)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    best = np.full(gy.shape, -1e9, dtype=np.float32)
    d = np.linspace(dists[0], dists[1], n) / sp_m
    for k in range(8):
        a = math.radians(360.0 * k / 8.0)
        ux, uy = math.cos(a), math.sin(a)
        prof = []
        for dd in d:
            jy = np.clip((gy + uy * dd).astype(np.int64), 0, ny - 1)
            jx = np.clip((gx + ux * dd).astype(np.int64), 0, nx - 1)
            prof.append(h[jy, jx])
        p = np.stack(prof, axis=0)
        c = np.diff(p, 2, axis=0).mean(axis=0)
        best = np.maximum(best, c)
    return best, ys, xs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        REPO, "_verify", "bench", "2026-09-11", "ground",
        "ground_station_map.png"))
    ap.add_argument("--width", type=int, default=1800)
    a = ap.parse_args(argv)

    rec = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                         encoding="utf-8"))
    ls = rec["landscape"]
    sp = float(ls["scale_xy_cm"]) / 100.0
    ox = float(ls["location_cm"][0]) / 100.0
    oy = float(ls["location_cm"][1]) / 100.0
    h16 = np.asarray(Image.open(os.path.join(REPO, rec["heightmap"]["source"])))
    zs = float(ls["z_scale_cm"]) / 100.0
    zb = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) / 100.0
    h = h16.astype(np.float32) / 65535.0 * zs + zb
    sun = rec["lighting"]["sun"]
    ndl, _sl = hillshade(h, sp, sun_vector(sun["azimuth_deg"],
                                           sun["elevation_deg"]))
    _w8b = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8b.png")))
    if _w8b.ndim != 3 or _w8b.shape[2] < 4:
        sys.exit("REFUSE: alpine_8k_w8b.png is %s, not a 4-channel image; "
                 "meadow lives in its alpha channel." % (_w8b.shape,))
    meadow = _w8b.astype(np.float32)[..., 3] / 255.0

    ny, nx = h.shape
    img = np.stack([ndl, ndl, ndl], axis=-1).astype(np.float32)
    img[meadow >= 0.55] *= np.array([0.45, 1.0, 0.45], dtype=np.float32)

    # trees, from the placed plans
    tree_px = 0
    for sp_name in ("Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"):
        p = os.path.join(REPO, "foliage", "alpine_8k_%s.json" % sp_name)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as _fh:
            _data = json.load(_fh)
        inst = np.asarray(_data.get("instances") or [], dtype=np.float64)
        # An empty (or missing) instances list gives a 1-D shape-(0,) array, so
        # inst[:, 0] would IndexError; skip such a plan.
        if inst.ndim != 2 or inst.shape[0] == 0:
            continue
        cx = np.clip(((inst[:, 0] / 100.0 - ox) / sp).astype(np.int64), 0, nx - 1)
        cy = np.clip(((inst[:, 1] / 100.0 - oy) / sp).astype(np.int64), 0, ny - 1)
        img[cy, cx] = img[cy, cx] * np.array([1.0, 0.25, 0.25],
                                             dtype=np.float32)
        tree_px += cx.size

    # ⛔ CONCAVITY IS NOT DRAWN, AND THAT IS THE POINT. Measured
    # 2026-09-11: 98.6% of cells have SOME concave azimuth, so the v2
    # gate ("this view's profile curves up") was nearly free -- it
    # rejected 387 of 1760 views and could never have been the
    # discriminator. It is computed and REPORTED as a fraction rather
    # than painted over the map, where it would colour everything and
    # look like information.
    conc, ys, xs = concavity_map(h, sp)
    good = conc > 0

    out = Image.fromarray(np.uint8(np.clip(img, 0, 1) ** (1 / 2.2) * 255))
    scale = a.width / float(nx)
    out = out.resize((a.width, int(ny * scale)), Image.LANCZOS)
    dr = ImageDraw.Draw(out)
    for name, X, Y, pred, got in FAILED:
        px = (X / 100.0 - ox) / sp * scale
        py = (Y / 100.0 - oy) / sp * scale
        # Clamp BOTH axes into the canvas; the old code clamped px only, so a
        # station off the top/bottom drew its marker off-image and vanished.
        px = min(max(px, 30), out.size[0] - 30)
        py = min(max(py, 30), out.size[1] - 30)
        dr.ellipse([px - 13, py - 13, px + 13, py + 13], outline=(255, 90, 0),
                   width=5)
        dr.text((px + 15, py - 8),
                "%s  predicted %s  rendered %s" % (name, pred, got),
                fill=(255, 140, 0))
    out.save(a.out)
    if not (os.path.isfile(a.out) and os.path.getsize(a.out) > 0):
        sys.exit("REFUSE: map %s did not write to disk." % a.out)
    print("wrote %s  (%d x %d)" % (a.out, out.size[0], out.size[1]))
    print("meadow>=0.55 %.1f%% of map; concave cells %.1f%%; tree instances %d"
          % (100 * (meadow >= 0.55).mean(), 100 * good.mean(), tree_px))
    print("BOTH derived stations MISSED; this map is for a human pick "
          "(RULED 2026-09-11).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
