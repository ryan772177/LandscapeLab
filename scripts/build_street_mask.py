"""build_street_mask.py -- the town STREET MASK for the landscape material (2026-10-10, cobblestone streets).

    python scripts/build_street_mask.py            # build + gate, write nothing (dry run)
    python scripts/build_street_mask.py --write    # ... and write the png + sidecar
    python scripts/build_street_mask.py --selftest

Design: research/town_kit/STREETS_DESIGN.md. Every value is in recipes/alpine_8k.json material.street_overlay.

OUTPUT: material.street_overlay.mask (an 8-bit RGBA png, square) over a square box centred on the CURRENT town
(plan streets + manifest houses), plus a .json sidecar the material builder checks the box against.
  R = cobble: union of every plan street slab (len x width, oriented), the plaza disc and the squares, each
      edge ramped linearly across feather_m (so 0.5 exactly on the drawn edge).
  G = grass exclusion: max(R, house footprint grown by house_margin_m, same ramp).
  B = LARGE-grass (boulder) exclusion, 2026-10-10b: the same shapes as G grown by boulder_margin_m instead of
      grass_margin_m (houses: house_margin_m + boulder_margin_m), same ramp. B >= G (asserted). A grass species
      opts in with street_keep_channel "B" (MeadowBoulders): a spawn POINT outside G still lays a 9 m slab
      across the cobble (LESSONS 2026-10-10ff).
  A = 0 (reserved).
The outer border_px ring is forced to 0, so TA_CLAMP sampling outside the box reads 0 (asserted).

GATES (independent of the raster, re-sampled from the geometry -- REFUSE on any failure, rule 13 counts printed):
  1. every street centreline sample (every 0.5 m, 1 m clear of each short end) reads R >= 0.99;
  2. every house centre reads G == 255 and R == 0;
  3. probe points 1 m outside a street's long edge, not within 1.5 m of any other cobble shape, read R < 0.05;
  4. the border ring is exactly 0 in every channel;
  5. determinism: two rasterisations are byte-identical;
  6. B >= G at every pixel;
  7. probes at measured reach + SPAWN_SLACK_M (sqrt(2) + 0.5 m) outside each street's long edge, and every house
     centre, read B == 255 (design review 2026-10-10b change 1).
"""
import argparse
import hashlib
import io
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
PLAN = "city/alpine_basin_town_plan.json"
MANIFEST = "city/alpine_basin_town_kit_manifest.json"


REACH = "Free/_measured/meadow_boulder_reach.json"
# Design review 2026-10-10b change 1: between the B == 255 plateau and a boulder's spawn POINT lie four terms.
#   grass-cell bilinear: any nonzero corner of a 1 m grass cell can seed a spawn anywhere in it
#                        (LandscapeGrass.cpp:2583-2610, keep Weight > 0 at :1491) -> cell diagonal sqrt(2) m
#   mip allowance:       the grass pass minifies the 25 cm/px mask ~4x; box mips erode the plateau <= ~0.5 m
#                        (UNVERIFIED which mip is sampled; a ceiling, not a measurement)
#   mask texel 0.25 m and ramp half-width feather_m/2: both are inside the raster, so gate 7 measures them
#                        directly by probing the plateau
SPAWN_SLACK_M = math.sqrt(2.0) + 0.5


def boulder_reach_m():
    """The measured max MeadowBoulders reach (boulder_reach.py), or REFUSE."""
    p = os.path.join(REPO, REACH)
    if not os.path.isfile(p):
        raise SystemExit("REFUSE: %s missing -- run _verify/organic/boulder_reach.py" % REACH)
    v = float(json.load(io.open(p, encoding="utf-8"))["max_reach_m"])
    if not v > 0:
        raise SystemExit("REFUSE: %s max_reach_m %r" % (REACH, v))
    return v


def _sha16(rel):
    return hashlib.sha256(io.open(os.path.join(REPO, rel), "rb").read()).hexdigest()[:16]


def load_cfg(recipe=RECIPE):
    rec = json.load(io.open(recipe, encoding="utf-8"))
    so = (rec.get("material") or {}).get("street_overlay")
    if not so:
        raise SystemExit("REFUSE: recipes/alpine_8k.json has no material.street_overlay")
    need = ("mask", "mask_px", "box_m", "feather_m", "house_margin_m", "grass_margin_m", "boulder_margin_m",
            "border_px", "exclude_grass_in_houses")
    miss = [k for k in need if k not in so]
    if miss:
        raise SystemExit("REFUSE: material.street_overlay lacks %s" % miss)
    if not (float(so["feather_m"]) > 0 and int(so["mask_px"]) >= 256 and float(so["box_m"]) > 0):
        raise SystemExit("REFUSE: street_overlay feather_m/mask_px/box_m must be positive")
    return so


def shapes():
    """(rects, discs, houses): rects/houses = (cx, cy, half_x, half_y, yaw_deg) cm; discs = (cx, cy, r) cm."""
    plan = json.load(io.open(os.path.join(REPO, PLAN), encoding="utf-8"))
    man = json.load(io.open(os.path.join(REPO, MANIFEST), encoding="utf-8"))
    rects = [(s["loc_cm"][0], s["loc_cm"][1], s["len_cm"] / 2.0, s["width_cm"] / 2.0, s["yaw_deg"])
             for s in plan["streets"]]
    cx, cy = plan["site_centre_cm"]
    discs = [(cx, cy, float(plan["plaza_radius_cm"]))] + [(x, y, r) for x, y, r in plan.get("squares", [])]
    houses = [(h["loc_cm"][0], h["loc_cm"][1], h["W_cm"] / 2.0, h["D_cm"] / 2.0, h["yaw_deg"]) for h in man["houses"]]
    if not rects or not houses:
        raise SystemExit("REFUSE: %d streets, %d houses -- nothing to mask (rule 13)" % (len(rects), len(houses)))
    return rects, discs, houses, plan


def box_for(rects, houses, box_m):
    pts = [(r[0], r[1]) for r in rects] + [(h[0], h[1]) for h in houses]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = 0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))
    size = box_m * 100.0
    # + 20 m margin, a chosen allowance for a piece's half-length / a house's half-diagonal (pieces are <= ~21 m
    # long, footprints <= 9 m) -- NOT a measured bound (audit F5a); an escaping street still fails gate 1 loudly
    half_span = 0.5 * max(max(xs) - min(xs), max(ys) - min(ys)) + 2000.0
    if half_span > 0.5 * size:
        raise SystemExit("REFUSE: the town (%.0f m across + margin) does not fit box_m %.0f"
                         % (2 * half_span / 100.0, box_m))
    return mx - 0.5 * size, my - 0.5 * size, size


def raster(cfg, rects, discs, houses, box):
    x0, y0, size = box
    n = int(cfg["mask_px"])
    px = size / n
    f = float(cfg["feather_m"]) * 100.0
    gm = float(cfg["house_margin_m"]) * 100.0
    bm = float(cfg["boulder_margin_m"]) * 100.0
    R = np.zeros((n, n), np.float32)
    G = np.zeros((n, n), np.float32)
    B = np.zeros((n, n), np.float32)

    def ramp(d):                      # d = signed distance to the edge, negative inside (cm)
        return np.clip(0.5 - d / f, 0.0, 1.0)

    def window(cx, cy, reach):
        i0 = max(0, int((cx - reach - x0) / px)); i1 = min(n, int((cx + reach - x0) / px) + 2)
        j0 = max(0, int((cy - reach - y0) / px)); j1 = min(n, int((cy + reach - y0) / px) + 2)
        if i0 >= i1 or j0 >= j1:
            return None
        xs = x0 + (np.arange(i0, i1) + 0.5) * px
        ys = y0 + (np.arange(j0, j1) + 0.5) * px
        X, Y = np.meshgrid(xs, ys)
        return (slice(j0, j1), slice(i0, i1)), X, Y

    def rect_cov(cx, cy, hx, hy, yaw, grow=0.0):
        w = window(cx, cy, math.hypot(hx, hy) + grow + f)
        if w is None:
            return None, None
        sl, X, Y = w
        a = math.radians(yaw)
        lx = (X - cx) * math.cos(a) + (Y - cy) * math.sin(a)
        ly = -(X - cx) * math.sin(a) + (Y - cy) * math.cos(a)
        qx, qy = np.abs(lx) - (hx + grow), np.abs(ly) - (hy + grow)
        outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
        inside = np.minimum(np.maximum(qx, qy), 0)
        return sl, ramp(outside + inside)

    # G's cobble part is the same shapes grown by grass_margin_m: the landscape grass map holds ONE weight per
    # landscape vertex (1 m here, LandscapeGrassWeightExporter.cpp:726-735 per the design review), so a
    # sub-metre edge is invisible to grass and the exclusion must reach past the stone (design review Q2).
    gg = float(cfg["grass_margin_m"]) * 100.0
    for cx, cy, hx, hy, yaw in rects:
        sl, c = rect_cov(cx, cy, hx, hy, yaw)
        if sl is not None:
            R[sl] = np.maximum(R[sl], c)
        sl, c = rect_cov(cx, cy, hx, hy, yaw, grow=gg)
        if sl is not None:
            G[sl] = np.maximum(G[sl], c)
        sl, c = rect_cov(cx, cy, hx, hy, yaw, grow=bm)
        if sl is not None:
            B[sl] = np.maximum(B[sl], c)
    for cx, cy, r in discs:
        w = window(cx, cy, r + max(gg, bm) + f)
        if w is None:
            continue
        sl, X, Y = w
        d = np.hypot(X - cx, Y - cy) - r
        R[sl] = np.maximum(R[sl], ramp(d))
        G[sl] = np.maximum(G[sl], ramp(d - gg))
        B[sl] = np.maximum(B[sl], ramp(d - bm))
    # houses: grass exclusion only, and only when the recipe asks (design review change 7 -- an addition to
    # "streets", declared in the recipe rather than slipped in)
    for cx, cy, hx, hy, yaw in (houses if cfg["exclude_grass_in_houses"] else []):
        sl, c = rect_cov(cx, cy, hx, hy, yaw, grow=gm)
        if sl is not None:
            G[sl] = np.maximum(G[sl], c)
        sl, c = rect_cov(cx, cy, hx, hy, yaw, grow=gm + bm)
        if sl is not None:
            B[sl] = np.maximum(B[sl], c)
    b = int(cfg["border_px"])
    img = np.zeros((n, n, 4), np.uint8)
    img[..., 0] = np.round(R * 255.0).astype(np.uint8)
    img[..., 1] = np.round(G * 255.0).astype(np.uint8)
    img[..., 2] = np.round(np.maximum(B, G) * 255.0).astype(np.uint8)   # B >= G even where ramps cross
    img[:b, :, :] = 0; img[-b:, :, :] = 0; img[:, :b, :] = 0; img[:, -b:, :] = 0
    # image row 0 = the box's MIN-Y edge (V grows with world Y); the material's UV follows the same convention
    return img


def sample(img, box, x, y):
    x0, y0, size = box
    n = img.shape[0]
    i, j = int((x - x0) / size * n), int((y - y0) / size * n)
    if not (0 <= i < n and 0 <= j < n):
        return None
    return img[j, i]


def gates(img, box, rects, discs, houses, cfg):
    fails, counts = [], {}
    # 1 centrelines: R >= 0.99 AND G == 1 (no grass on the road)
    bad = badg = n1 = 0
    for cx, cy, hx, hy, yaw in rects:
        a = math.radians(yaw)
        # interior only: the short ends sit ON an edge (ramp 0.5 by construction) where pieces abut
        for t in np.arange(-hx + 100.0, hx - 100.0 + 1e-6, 50.0):
            v = sample(img, box, cx + t * math.cos(a), cy + t * math.sin(a)); n1 += 1
            if v is None or v[0] < 252:
                bad += 1
            if v is None or v[1] != 255:
                badg += 1
    counts["centreline_samples"] = n1
    if n1 == 0:
        # rule 13 (audit F3): a gate that sampled nothing is not a pass
        fails.append("0 centreline samples -- the gate measured nothing (rule 13)")
    if bad:
        fails.append("%d of %d centreline samples read R < 0.99" % (bad, n1))
    if badg:
        fails.append("%d of %d centreline samples read G < 1 (grass on the road)" % (badg, n1))
    # 2 house centres: R == 0 always; G == 1 exactly when houses are excluded, else not forced
    bad = 0
    for cx, cy, *_ in houses:
        v = sample(img, box, cx, cy)
        if v is None or v[0] != 0 or (cfg["exclude_grass_in_houses"] and v[1] != 255):
            bad += 1
    counts["house_centres"] = len(houses)
    if bad:
        fails.append("%d of %d house centres not (R=0%s)"
                     % (bad, len(houses), ", G=255" if cfg["exclude_grass_in_houses"] else ""))
    # 3 outside the edge (independent geometry test for "near another cobble shape")
    def near_any(x, y, m, skip):
        for k, (cx, cy, hx, hy, yaw) in enumerate(rects):
            if k == skip:
                continue
            a = math.radians(yaw)
            lx = (x - cx) * math.cos(a) + (y - cy) * math.sin(a)
            ly = -(x - cx) * math.sin(a) + (y - cy) * math.cos(a)
            if abs(lx) <= hx + m and abs(ly) <= hy + m:
                return True
        return any(math.hypot(x - cx, y - cy) <= r + m for cx, cy, r in discs)
    bad = n3 = 0
    for k, (cx, cy, hx, hy, yaw) in enumerate(rects):
        a = math.radians(yaw)
        for side in (1, -1):
            off = hy + 100.0
            x, y = cx - side * off * math.sin(a), cy + side * off * math.cos(a)
            # skip probes within 1.5 m of ANOTHER cobble shape (its own edge is 1 m away by construction)
            if near_any(x, y, 150.0, k):
                continue
            v = sample(img, box, x, y); n3 += 1
            if v is not None and v[0] >= 13:
                bad += 1
    counts["outside_probes"] = n3
    if n3 == 0:
        fails.append("0 outside probes -- the gate measured nothing (rule 13)")
    elif bad:
        fails.append("%d of %d probes 1 m outside a street edge read R >= 0.05" % (bad, n3))
    # 4 border -- the recipe's own border_px (audit F2: was a hardcoded 2)
    b = int(cfg["border_px"])
    ring = np.concatenate([img[:b].ravel(), img[-b:].ravel(), img[:, :b].ravel(), img[:, -b:].ravel()])
    counts["border_values"] = int(ring.size)
    if ring.any():
        fails.append("border ring not 0")
    # 6 B >= G everywhere (the boulder exclusion contains the grass exclusion)
    nb = int((img[..., 2] < img[..., 1]).sum())
    counts["b_ge_g_pixels"] = int(img[..., 1].size)
    if nb:
        fails.append("%d pixels read B < G" % nb)
    # 7 boulder reach: at (reach + SPAWN_SLACK_M) outside each long edge, and every house centre, B == 255 -- so a
    # boulder whose spawn point survives the grass sampling chain cannot reach the cobble (review 2026-10-10b)
    off_b = float(cfg["_probe_reach_m"]) * 100.0
    bad = n7 = 0
    for cx, cy, hx, hy, yaw in rects:
        a = math.radians(yaw)
        for side in (1, -1):
            off = hy + off_b
            x, y = cx - side * off * math.sin(a), cy + side * off * math.cos(a)
            v = sample(img, box, x, y)
            if v is None:
                continue          # outside the box: the box gate (box_for) owns that
            n7 += 1
            if v[2] != 255:
                bad += 1
    if cfg["exclude_grass_in_houses"]:
        for cx, cy, *_ in houses:
            v = sample(img, box, cx, cy); n7 += 1
            if v is None or v[2] != 255:
                bad += 1
    counts["boulder_probes"] = n7
    if n7 == 0:
        fails.append("0 boulder probes -- the gate measured nothing (rule 13)")
    elif bad:
        fails.append("%d of %d boulder probes read B < 1" % (bad, n7))
    return fails, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--recipe", default=RECIPE, help="world recipe carrying material.street_overlay")
    a = ap.parse_args(argv)
    if a.selftest:
        cfg = {"mask_px": 512, "feather_m": 0.35, "house_margin_m": 0.5, "grass_margin_m": 0.5,
               "boulder_margin_m": 3.0, "border_px": 2, "exclude_grass_in_houses": True, "_probe_reach_m": 2.5}
        rects = [(5000.0, 5000.0, 1000.0, 300.0, 30.0)]
        discs = [(2000.0, 2000.0, 500.0)]
        houses = [(8000.0, 8000.0, 300.0, 250.0, 0.0)]
        box = (0.0, 0.0, 10240.0)
        img = raster(cfg, rects, discs, houses, box)
        f, c = gates(img, box, list(rects), discs, houses, cfg)
        ok = not f and c["outside_probes"] > 0
        # negative control: a mask with the street erased must FAIL gate 1
        img2 = img.copy(); img2[..., 0] = 0
        f2, _ = gates(img2, box, list(rects), discs, houses, cfg)
        ok &= any("centreline" in x for x in f2)
        # negative control 2: B erased to G must FAIL gate 7 (boulder reach)
        img3 = img.copy(); img3[..., 2] = img3[..., 1]
        f3, _ = gates(img3, box, list(rects), discs, houses, cfg)
        ok &= any("boulder" in x for x in f3)
        f2 = f2 + f3
        print("SELFTEST %s (positive %s %s; negative control caught: %s)" % ("PASSED" if ok else "FAILED", f, c, f2))
        return 0 if ok else 4
    cfg = load_cfg(a.recipe)
    reach = boulder_reach_m()
    cfg["_probe_reach_m"] = reach + SPAWN_SLACK_M
    # floor: the probe distance + one mask texel + the ramp half-width must fit inside the grown shape
    floor_m = cfg["_probe_reach_m"] + float(cfg["box_m"]) / int(cfg["mask_px"]) + float(cfg["feather_m"]) / 2.0
    print("boulder: measured reach %.2f m + spawn slack %.2f m -> probe %.2f m; margin %.2f m >= floor %.2f m"
          % (reach, SPAWN_SLACK_M, cfg["_probe_reach_m"], float(cfg["boulder_margin_m"]), floor_m))
    if float(cfg["boulder_margin_m"]) < floor_m:
        print("REFUSE: boulder_margin_m %.2f < floor %.2f (%s)" % (float(cfg["boulder_margin_m"]), floor_m, REACH))
        return 4
    rects, discs, houses, plan = shapes()
    box = box_for(rects, houses, float(cfg["box_m"]))
    img = raster(cfg, rects, discs, houses, box)
    if not np.array_equal(img, raster(cfg, rects, discs, houses, box)):
        print("REFUSE: rasterisation is not deterministic")
        return 4
    fails, counts = gates(img, box, list(rects), discs, houses, cfg)
    cov = {ch: round(float((img[..., k] > 127).mean()) * 100.0, 3) for k, ch in enumerate("RGB")}
    print("box x0 %.1f y0 %.1f size %.0f cm; %d px (%.1f cm/px); streets %d, discs %d, houses %d"
          % (box[0], box[1], box[2], img.shape[0], box[2] / img.shape[0], len(rects), len(discs), len(houses)))
    print("coverage (> 0.5): R %.3f %%  G %.3f %%  B %.3f %%;  gate counts %s"
          % (cov["R"], cov["G"], cov["B"], counts))
    for f in fails:
        print("  FAIL " + f)
    if fails:
        print("REFUSE: nothing written")
        return 4
    if not a.write:
        print("gates OK; dry run (pass --write)")
        return 0
    from PIL import Image
    out = os.path.join(REPO, cfg["mask"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray(img, "RGBA").save(out, optimize=True)
    side = {"_produced_by": "scripts/build_street_mask.py", "_recipe": "recipes/alpine_8k.json",
            "_city_plan": PLAN, "_kit_manifest": MANIFEST,
            "inputs_sha16": {PLAN: _sha16(PLAN), MANIFEST: _sha16(MANIFEST), REACH: _sha16(REACH)},
            "boulder_reach_m": reach, "boulder_probe_m": round(cfg["_probe_reach_m"], 3),
            "box_cm": [round(box[0], 1), round(box[1], 1), round(box[2], 1)], "px": int(img.shape[0]),
            "row0": "min-Y edge of the box (V grows with world Y)",
            "channels": {"R": "cobble", "G": "grass exclusion",
                         "B": "large-grass (boulder) exclusion, >= G", "A": "reserved 0"},
            "feather_m": float(cfg["feather_m"]), "house_margin_m": float(cfg["house_margin_m"]),
            "grass_margin_m": float(cfg["grass_margin_m"]), "boulder_margin_m": float(cfg["boulder_margin_m"]),
            "border_px": int(cfg["border_px"]),
            "exclude_grass_in_houses": bool(cfg["exclude_grass_in_houses"]),
            "box_m": float(cfg["box_m"]),
            "coverage_pct_over_half": cov, "gate_counts": counts}
    json.dump(side, io.open(out + ".json", "w", encoding="utf-8"), indent=1)
    print("wrote %s (+ .json)" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
