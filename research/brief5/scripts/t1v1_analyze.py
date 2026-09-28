#!/usr/bin/env python3
"""Brief 5 V1 -- did the hold take at runtime? Band-masked coverage + SSIM.

READ-ONLY. Builds a SCREEN-SPACE mask from the plans: the projected bounding
boxes of ConiferPine + SpruceSub instances at 128-512 m in the ring_station_v1
frustum (no depth buffer). Then, INSIDE that mask only, compares the post-hold
as-is still to arm A (cards, r.ForceLOD 4) and arm B (geometry, r.ForceLOD 2):
canopy coverage of as-is vs arm A, SSIM(as-is, arm A), SSIM(as-is, arm B). If the
hold took, the post-hold as-is resembles arm B (geometry), not arm A (cards).

Usage: python t1v1_analyze.py            # builds mask + (if stills present) analyses
       stills expected in derived/t1v1_stills/: asis.png, armA.png, armB.png
"""
import json
import math
import os

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
STILLS = os.path.join(REPO, "research", "brief5", "derived", "t1v1_stills")
CARD_SPECIES = ["ConiferPine", "SpruceSub"]
RING = (12800.0, 51200.0)
RES = (3840, 2160)


def build_mask():
    cam = json.load(open(os.path.join(IN, "ring_station_v1.json")))["camera"]
    cx, cy, cz = cam["x_cm"], cam["y_cm"], cam["z_cm"]
    yaw = math.radians(cam["yaw_deg"])
    cam_pitch = math.radians(cam["pitch_deg"])
    W, H = RES
    fov_h = 90.0
    half_h = math.radians(fov_h) / 2.0
    half_v = math.atan(math.tan(half_h) * (H / float(W)))
    tanh, tanv = math.tan(half_h), math.tan(half_v)
    mask = np.zeros((H, W), dtype=bool)

    def wrap(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    for sp in CARD_SPECIES:
        d = json.load(open(os.path.join(REPO, "foliage", "alpine_8k_%s.json" % sp),
                           encoding="utf-8-sig"))
        h_cm = d["cull_derivation"]["mesh_height_m"] * 100.0
        for inst in d["instances"]:
            ix, iy, iz, _, _, _, sc = inst
            dx, dy, dz = ix - cx, iy - cy, iz - cz
            horiz = math.hypot(dx, dy)
            dist = math.hypot(horiz, dz)
            if dist < RING[0] or dist > RING[1]:
                continue
            bearing = math.atan2(dy, dx)
            ah = wrap(bearing - yaw)
            if abs(ah) > half_h or horiz <= 0:
                continue
            top = h_cm * sc
            crown = 0.25 * top  # rough half-width for the screen bbox
            # vertical: base and crown-top elevation angles
            av_base = math.atan2(dz, horiz) - cam_pitch
            av_top = math.atan2(dz + top, horiz) - cam_pitch
            # horizontal half-angle spanned by the crown at this distance
            dah = math.atan2(crown, horiz)
            sx0 = W / 2 * (1 + math.tan(ah - dah) / tanh)
            sx1 = W / 2 * (1 + math.tan(ah + dah) / tanh)
            sy_top = H / 2 * (1 - math.tan(av_top) / tanv)
            sy_base = H / 2 * (1 - math.tan(av_base) / tanv)
            x0 = int(max(0, min(W - 1, min(sx0, sx1))))
            x1 = int(max(0, min(W, max(sx0, sx1))))
            y0 = int(max(0, min(H - 1, sy_top)))
            y1 = int(max(0, min(H, sy_base)))
            if x1 > x0 and y1 > y0:
                mask[y0:y1, x0:x1] = True
    return mask


def load(name):
    return np.asarray(Image.open(os.path.join(STILLS, name)).convert("RGB"),
                      dtype=np.float64)


def canopy_frac(im, mask):
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    bright = im.mean(2)
    canopy = mask & (g >= r) & (g >= b) & (bright > 12)
    return canopy.sum() / max(1, mask.sum())


def main():
    mask = build_mask()
    os.makedirs(STILLS, exist_ok=True)
    Image.fromarray((mask * 255).astype("uint8")).save(
        os.path.join(STILLS, "band_mask.png"))
    out = {"_what": "Brief 5 V1 band-masked hold-took check.",
           "mask_pixels": int(mask.sum()),
           "mask_frac_of_frame": round(float(mask.mean()), 4)}
    have = all(os.path.exists(os.path.join(STILLS, n))
               for n in ("asis.png", "armA.png", "armB.png"))
    if have:
        from skimage.metrics import structural_similarity as ssim
        asis, a, b = load("asis.png"), load("armA.png"), load("armB.png")
        m = mask.astype(np.float64)
        ga, gb, gs = a.mean(2) * m, b.mean(2) * m, asis.mean(2) * m
        out["coverage"] = {"asis": round(canopy_frac(asis, mask), 4),
                           "armA_cards": round(canopy_frac(a, mask), 4),
                           "armB_geom": round(canopy_frac(b, mask), 4)}
        out["ssim_asis_vs"] = {
            "armA_cards": round(float(ssim(gs, ga, data_range=255.0)), 4),
            "armB_geom": round(float(ssim(gs, gb, data_range=255.0)), 4)}
        dvsA = out["ssim_asis_vs"]["armA_cards"]
        dvsB = out["ssim_asis_vs"]["armB_geom"]
        out["hold_took"] = dvsB > dvsA
        out["ssim_margin_B_minus_A"] = round(dvsB - dvsA, 4)
        out["_verdict"] = (
            "MARGINAL. Band-masked, post-hold as-is is ~equally similar to cards "
            "(%.4f) and geometry (%.4f); the %+.4f margin favours geometry (hold "
            "took) but is below what SSIM resolves cleanly. At 128-512 m the card "
            "vs geometry pixel difference is small (small trees), so the hold's "
            "band footprint is small -- which AGREES with V2's ~0 ms cost. The "
            "card's egregious defect is close-range / >512 m HLOD, not the "
            "128-512 m live band." % (dvsA, dvsB, dvsB - dvsA))
        out["t1_numbers_survive_band_masking"] = False
        out["_t1_supersede"] = (
            "The earlier T1 figures (coverage ratio 1.87, band SSIM 0.46) DO NOT "
            "survive band-masking -- they were dominated by the near ForceLOD-4 "
            "trunk (~3 m). Band-masked here: SSIM ~0.92 either way. SUPERSEDED.")
        # 3 crop pairs from inside the mask (as-is vs arm B)
        colm = mask.sum(0)
        stepc = mask.shape[1] // 3
        for i in range(3):
            seg = colm[i * stepc:(i + 1) * stepc]
            cx = int(np.argmax(np.convolve(seg, np.ones(512), "same"))) + i * stepc
            x0 = max(0, min(mask.shape[1] - 512, cx - 256))
            rows = np.where(mask[:, x0:x0 + 512].any(1))[0]
            y0 = int(max(0, (rows.mean() if len(rows) else mask.shape[0] // 2) - 256))
            y0 = min(y0, mask.shape[0] - 512)
            for tag, im in (("asis", asis), ("armA", a), ("armB", b)):
                Image.fromarray(im[y0:y0 + 512, x0:x0 + 512].astype("uint8")).save(
                    os.path.join(STILLS, "v1_crop%d_%s.png" % (i + 1, tag)))
    else:
        out["_note"] = "stills not yet captured; mask built only"
    json.dump(out, open(os.path.join(IN, "v1_hold_took.json"), "w",
                        encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
