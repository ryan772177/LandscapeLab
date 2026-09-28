"""render_face_mesh_offline.py — draw the sculpted face from its own geometry.

WHY OFFLINE
    Four engine captures of this character came back pure white (mean RGB
    255/255/255, nonwhite fraction 0.0000). The cause is understood -- the
    preview mesh is about 0.12 units tall, its components sit at world origin
    and do not follow the actor, so the subject falls inside the near clip
    plane -- but every attempt to work around it cost an editor restart.

    The mesh vertices are a different representation of the same fact and
    they are already on disk. Rasterising them here answers "what shape is
    this face" without asking the renderer anything, and it cannot come back
    white.

WHAT IT DRAWS
    An orthographic front view and a profile, z-buffered, shaded by surface
    normal estimated from the depth buffer. Plus the SILHOUETTE WIDTH PROFILE
    measured the same way scripts/hero_face/measure_reference_silhouette.py
    measures it on the photograph -- which is the comparison
    compare_profiles.py could not do soundly, because 79 landmarks are not a
    silhouette but 33,845 mesh vertices are.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image


def rasterise(pts, hor, ver, dep, W, H, flip_h=False, flip_d=False):
    """Splat vertices into a z-buffer. Returns (depth, mask) with +dep nearer."""
    h = pts[:, hor].astype(np.float64)
    v = pts[:, ver].astype(np.float64)
    d = pts[:, dep].astype(np.float64)
    if flip_h:
        h = -h
    if flip_d:
        d = -d
    pad = 0.06
    hs = (h - h.min()) / (h.max() - h.min())
    vs = (v - v.min()) / (v.max() - v.min())
    # one shared scale keeps the real aspect ratio; a face stretched to fill
    # a box is a different face
    span = max(h.max() - h.min(), v.max() - v.min())
    hs = (h - (h.max() + h.min()) / 2) / span
    vs = (v - (v.max() + v.min()) / 2) / span
    side = min(W, H) * (1 - 2 * pad)
    x = (W / 2 + hs * side).astype(np.int32)
    y = (H / 2 - vs * side).astype(np.int32)
    ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    x, y, d = x[ok], y[ok], d[ok]

    depth = np.full((H, W), -np.inf)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            xx = np.clip(x + dx, 0, W - 1)
            yy = np.clip(y + dy, 0, H - 1)
            np.maximum.at(depth, (yy, xx), d)
    mask = np.isfinite(depth)
    return depth, mask


def shade(depth, mask):
    d = np.where(mask, depth, np.nan)
    # fill small holes so the normal estimate is not dominated by gaps
    filled = d.copy()
    for _ in range(3):
        pad = np.pad(filled, 1, constant_values=np.nan)
        stack = np.stack([pad[0:-2, 1:-1], pad[2:, 1:-1],
                          pad[1:-1, 0:-2], pad[1:-1, 2:]])
        with np.errstate(invalid="ignore"):
            nb = np.nanmean(stack, axis=0)
        filled = np.where(np.isnan(filled), nb, filled)
    dd = np.nan_to_num(filled, nan=np.nanmin(filled))
    gy, gx = np.gradient(dd)
    # light from upper left, in front
    n = np.stack([-gx, -gy, np.full_like(dd, 0.010)], axis=-1)
    n /= (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12)
    L = np.array([-0.45, -0.55, 0.70])
    L = L / np.linalg.norm(L)
    lam = np.clip((n * L).sum(-1), 0, 1)
    amb = 0.22
    img = np.clip(amb + 0.95 * lam, 0, 1)
    out = (img * 255).astype(np.uint8)
    return np.where(mask, out, 18)


def width_profile(pts, hor, ver, nbins=40):
    h = pts[:, hor]
    v = pts[:, ver]
    vmax, vmin = v.max(), v.min()
    rows = []
    for b in range(nbins):
        hi = vmax - (vmax - vmin) * b / nbins
        lo = vmax - (vmax - vmin) * (b + 1) / nbins
        sel = (v >= lo) & (v <= hi)
        if sel.sum() < 3:
            rows.append(None)
            continue
        rows.append({"depth": float(vmax - (hi + lo) / 2),
                     "width": float(h[sel].max() - h[sel].min())})
    return rows


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=os.path.join(
        root, "hero", "generated", "face_mesh_sculpted.json"))
    ap.add_argument("--out", default=os.path.join(
        root, "_verify", "20260816_face_mesh_sculpted.png"))
    ap.add_argument("--silhouette", default=os.path.join(
        root, "hero", "generated", "reference_silhouette.json"))
    args = ap.parse_args(argv)

    d = json.load(open(args.mesh))
    pts = np.asarray(d["vertices"], dtype=np.float64)
    print("mesh      : %s" % d.get("mesh"))
    print("vertices  : %d" % len(pts))

    W = H = 620
    # X lateral, Z up, Y depth (+Y anterior) -- established by the
    # bilateral-symmetry test in analyse_landmarks.py
    df, mf = rasterise(pts, 0, 2, 1, W, H, flip_h=True)
    dp, mp = rasterise(pts, 1, 2, 0, W, H)
    front = shade(df, mf)
    prof = shade(dp, mp)
    canvas = Image.new("L", (W * 2, H), 18)
    canvas.paste(Image.fromarray(front), (0, 0))
    canvas.paste(Image.fromarray(prof), (W, 0))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    canvas.convert("RGB").save(args.out)
    print("wrote %s" % args.out)

    # --- the comparison compare_profiles.py could not make soundly ---
    rows = [r for r in width_profile(pts, 0, 2) if r]
    top_half = [r for r in rows if r["depth"] <= 0.5 * (pts[:, 2].max() - pts[:, 2].min())]
    mh_cran = max(r["width"] for r in top_half)

    sil = json.load(open(args.silhouette))
    Wmax = float(sil["widest_row"]["width"])
    ref = [(p["depth_over_W"] * Wmax, p["width_over_W"] * Wmax)
           for p in sil["profile"] if not p["clipped"]]
    ref_top = [w for dp2, w in ref if dp2 <= 0.55 * Wmax]
    ref_cran = max(ref_top) if ref_top else Wmax

    print("")
    print("WIDTH PROFILE, mesh vs photograph, each as a fraction of its OWN")
    print("cranium width. This is the sound version of the comparison")
    print("compare_profiles.py could not make: 33,845 mesh vertices ARE a")
    print("silhouette where 79 landmarks are not.")
    print("")
    print("  depth/W    mesh w/W   hero w/W    ratio")
    curve = []
    for r in rows:
        dw = r["depth"] / mh_cran
        mw = r["width"] / mh_cran
        best = None
        for dp2, w in ref:
            dd = abs(dp2 / ref_cran - dw)
            if best is None or dd < best[0]:
                best = (dd, w / ref_cran)
        if best is None or best[0] > 0.05:
            continue
        # the photograph stops being head below d/W ~0.95: the collar is
        # chromatic too and the silhouette wraps it
        note = "  (photo is collar here)" if dw > 0.95 else ""
        ratio = best[1] / mw if mw > 1e-9 else float("nan")
        print("   %.3f     %.3f      %.3f      %.3f%s"
              % (dw, mw, best[1], ratio, note))
        # Only the head region is comparable. Below d/W 0.95 the photograph's
        # chroma silhouette has wrapped the armour collar, which is not head,
        # so those rows are printed for completeness and EXCLUDED from the
        # curve any correction is derived from.
        if dw <= 0.95:
            curve.append({"depth_over_W": round(dw, 4),
                          "mesh_over_W": round(mw, 4),
                          "hero_over_W": round(best[1], 4),
                          "ratio": round(ratio, 4)})

    prof_out = os.path.join(root, "hero", "generated", "mesh_vs_hero_ratio.json")
    json.dump({"mesh": d.get("mesh"), "mesh_cranium_width": mh_cran,
               "z_min": float(pts[:, 2].min()), "z_max": float(pts[:, 2].max()),
               "curve": curve}, open(prof_out, "w"), indent=2)
    print("")
    print("wrote %s  (%d comparable bands, collar excluded)"
          % (prof_out, len(curve)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
