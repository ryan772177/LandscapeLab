"""F2 (Brief 7 Phase 1) — does the height-weighted blend flip the dominant
surface bake_surface_lookup reports?

Ryan's ruling 2026-09-23: MEASURE, offline, on the REAL weightmap, the
fraction of WALKABLE texels whose argmax layer flips under the height
reweight. <= 2% -> accept (record the number). > 2% -> model the reweight
in bake_surface_lookup before Phase 1's world run.

The shader (make_landscape_material) reweights each STORED layer's mask by
w_i' = w_i*(h_i+eps)^k and renormalises to preserve sum(stored); the
remainder (Grass/meadow) is unchanged. bake_surface_lookup.dominant is the
argmax over the RAW channels. This script reproduces both and compares.

Height per texel is the layer's Displacement map sampled at the texel's
WORLD position under that layer's tiling_m (what the shader does), bilinear.
Walkable = terrain slope <= 44.765 deg (the walk agent bar, recipe nav) AND
not inside the water-exclusion footprint.

Pure offline: PIL + numpy, no editor. Writes research/brief7/input/
f2_argmax_flip.json. Run: python research/brief7/scripts/f2_argmax_flip.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # the 8129^2 maps are trusted project artefacts

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
STRIDE = 4          # 8129 -> 2033 sample grid (the 4x heightmap lineage)
WALK_DEG = 44.765   # recipe navigation walk bar
DISP = {
    "Snow": "Free/Snow007A_4K-PNG/Snow007A_4K-PNG_Displacement.png",
    "Rock": "Free/gray_rocks_4k/gray_rocks_4K_Displacement.png",
    "Scree": "Free/rocks_ground_04_4k/rocks_ground_04_4K_Displacement.png",
    "ForestFloor": "Free/forest_floor_4k/forest_floor_4K_Displacement.png",
}


def _load_gray01(path):
    im = Image.open(os.path.join(REPO, path))
    a = np.asarray(im)
    if a.ndim == 3:
        a = a[:, :, :3].mean(axis=2)
    a = a.astype(np.float64)
    return a / (65535.0 if a.max() > 255.0 else 255.0)


def _bilinear_tiled(dmap, u, v):
    """Sample dmap (H,W) at fractional tiled coords u,v in [0,1) (wrapped)."""
    H, W = dmap.shape
    fx = (u % 1.0) * W - 0.5
    fy = (v % 1.0) * H - 0.5
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    dx = fx - x0
    dy = fy - y0
    x0m = x0 % W
    x1m = (x0 + 1) % W
    y0m = y0 % H
    y1m = (y0 + 1) % H
    c00 = dmap[y0m, x0m]
    c10 = dmap[y0m, x1m]
    c01 = dmap[y1m, x0m]
    c11 = dmap[y1m, x1m]
    return (c00 * (1 - dx) * (1 - dy) + c10 * dx * (1 - dy)
            + c01 * (1 - dx) * dy + c11 * dx * dy)


def main():
    recipe = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                            encoding="utf-8"))
    mat = recipe["material"]
    layers = [L["name"] for L in mat["layers"]]         # order = channel order
    stored = layers[:4]                                  # R,G,B,A stored
    hb = mat["height_blend"]
    k = float(hb["k"])
    eps = float(hb["eps"])
    eps_norm = (eps ** k) * 1e-7                          # HEIGHT_BLEND_NORM_REL
    tiling = {L["name"]: float(L["tiling_m"]) for L in mat["layers"]}
    ls = recipe["landscape"]
    loc = ls["location_cm"]
    sxy = float(ls["scale_xy_cm"])
    zc = float(ls["z_scale_cm"])

    # --- weightmap (stored channels + derived remainder) --------------
    wm = np.asarray(Image.open(
        os.path.join(REPO, "textures", "alpine_8k_weights.png")))
    wm = wm[::STRIDE, ::STRIDE, :4].astype(np.float64) / 255.0
    ny, nx = wm.shape[:2]
    base = [wm[:, :, i] for i in range(4)]               # Snow,Rock,Scree,FF
    s = sum(base)
    remainder = np.clip(1.0 - s, 0.0, None)

    # --- world coords per sampled texel (cm), then per-layer tiled UV --
    jj = np.arange(nx) * STRIDE
    ii = np.arange(ny) * STRIDE
    wx = loc[0] + jj * sxy                                # (nx,) cm
    wy = loc[1] + ii * sxy                                # (ny,) cm
    WX, WY = np.meshgrid(wx, wy)                          # (ny,nx)

    # --- per-layer height at each texel -------------------------------
    heights = []
    for name in stored:
        d = _load_gray01(DISP[name])
        tile_cm = tiling[name] * 100.0
        u = WX / tile_cm
        v = WY / tile_cm
        heights.append(_bilinear_tiled(d, u, v))

    # --- reweight the stored masks, renormalise (shader model) --------
    hk = [(heights[i] + eps) ** k for i in range(4)]
    wp = [base[i] * hk[i] for i in range(4)]
    sp = sum(wp)
    norm = s / (sp + eps_norm)
    rew = [wp[i] * norm for i in range(4)]

    # --- argmax over [stored..., remainder], before vs after ----------
    before = np.stack(base + [remainder], axis=2)        # (ny,nx,5)
    after = np.stack(rew + [remainder], axis=2)
    dom_before = np.argmax(before, axis=2)
    dom_after = np.argmax(after, axis=2)
    flip = dom_before != dom_after

    # --- walkable mask: slope <= WALK_DEG, not water ------------------
    hm = np.asarray(Image.open(
        os.path.join(REPO, "terrain", "alpine_8k.png"))).astype(np.float64)
    hm = hm / 65535.0
    hm = hm[::STRIDE, ::STRIDE]
    # gradient in cm: dz = dv*zc over dx = sxy*STRIDE
    gy, gx = np.gradient(hm * zc, sxy * STRIDE)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
    walk = slope_deg <= WALK_DEG

    water_path = os.path.join(REPO, "encounters",
                              "alpine_8k_water_exclusion.npz")
    water_note = "absent"
    if os.path.isfile(water_path):
        wz = np.load(water_path)
        wkey = wz.files[0]
        wmask = wz[wkey]
        if wmask.dtype != bool:
            wmask = wmask.astype(bool)
        # resample nearest to our grid
        wy_i = (np.linspace(0, wmask.shape[0] - 1, ny)).astype(np.int64)
        wx_i = (np.linspace(0, wmask.shape[1] - 1, nx)).astype(np.int64)
        water = wmask[np.ix_(wy_i, wx_i)]
        walk = walk & (~water)
        water_note = "npz key %r shape %s" % (wkey, wmask.shape)

    n_walk = int(walk.sum())
    if n_walk == 0:
        sys.exit("REFUSE: zero walkable texels -- a fraction over nothing is "
                 "not a measurement (rule 13)")
    flip_walk = int((flip & walk).sum())
    frac_walk = flip_walk / n_walk
    frac_all = float(flip.mean())

    # among flips, how far did the winner actually diverge (the two shares
    # at the flipped texel) -- a flip between two near-tied layers is
    # cosmetically different from one that overturns a clear winner.
    fw = flip & walk
    if flip_walk:
        b = before[fw]
        margin = np.sort(b, axis=1)[:, -1] - np.sort(b, axis=1)[:, -2]
        margin_p50 = float(np.median(margin))
        margin_p90 = float(np.percentile(margin, 90))
    else:
        margin_p50 = margin_p90 = 0.0

    verdict = "ACCEPT" if frac_walk <= 0.02 else "MODEL"
    out = {
        "what": "F2 argmax-flip: bake_surface_lookup raw-argmax vs the "
                "height-reweighted shader dominant, walkable area only",
        "ruling": "<=2% accept (record); >2% model the reweight in "
                  "bake_surface_lookup before Phase 1 world run (Ryan "
                  "2026-09-23)",
        "k": k, "eps": eps, "eps_norm": eps_norm,
        "stride": STRIDE, "grid": [ny, nx],
        "walk_deg": WALK_DEG, "water": water_note,
        "layers_order": layers, "stored": stored,
        "tiling_m": tiling,
        "n_sampled": int(ny * nx),
        "n_walkable": n_walk,
        "flips_walkable": flip_walk,
        "frac_flip_walkable": frac_walk,
        "frac_flip_all_terrain": frac_all,
        "flip_margin_p50": margin_p50,
        "flip_margin_p90": margin_p90,
        "verdict": verdict,
    }
    outdir = os.path.join(REPO, "research", "brief7", "input")
    os.makedirs(outdir, exist_ok=True)
    outp = os.path.join(outdir, "f2_argmax_flip.json")
    json.dump(out, open(outp, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))
    print("\nwrote", os.path.relpath(outp, REPO))


if __name__ == "__main__":
    main()
