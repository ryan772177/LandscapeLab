# COPIED 2026-10-10 from C:/Users/Admin/Gemini2UE/scripts/town_from_topdown.py (sha256 4848657c923a2084...). Town-from-image adapter for plan.layout "image".
# Dependencies (standing rule 5): opencv-contrib-python 5.0 (cv2.ximgproc), shapely 2.2.0, sknw 0.15, numba 0.68.0 (host Python 3.12, pip).
"""town_from_topdown.py - flat-colour top-down town map -> town plan JSON (streets + building lots).

The adapter the town lane needs: the proven kit route on this machine (UE5LandscapePipeline
R-TOWNKIT) reads a plain plan JSON and never an image. This tool produces a plan in that row
shape from the class masks that classify_topdown.py wrote, so the same downstream placer (kit
houses where the kit exists, greybox cubes otherwise) can consume it.

Method (standard CV; the segmentation -> thinning -> skeleton-graph -> vectorise chain is
published for scanned maps, and its transfer to AI-painted maps is INFERRED, not benchmarked):
  roads      class mask -> morphological close/open -> cv2.ximgproc.thinning (Guo-Hall)
             -> sknw skeleton graph -> polylines -> straight segments <= --segment-max-m,
             width from the distance transform at the skeleton (x2), tiered main/lane/alley
  buildings  class mask -> open -> connected components >= --min-building-m2
             -> cv2.minAreaRect -> loc, W x D snapped to 50 cm, yaw, door_side = the side
             whose midpoint is nearest to a street segment, storeys from --storeys
  water      class mask -> contours -> polygons (metres), for the exclusion mask downstream

Axis mapping "A" (same as the proven stamp compositor: array column = world X, array row =
world Y): world_X_cm = col * m_per_px * 100 + origin_x, world_Y_cm = row * m_per_px * 100 +
origin_y. Verify in the editor with two marker cubes before trusting it (capture_ortho frame).

Usage:
    python scripts/town_from_topdown.py data/layers/town/town_classes.json --roads class03 \
        --buildings class04 --water class00 --m-per-px 1.0 --out data/town/town_plan.json

Exit codes: 0 written, 2 bad input, 3 nothing extracted (no roads and no buildings).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SNAP_CM = 50.0


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_mask(classes, name, size):
    by = {}
    for p in classes["palette"]:
        by[f"class{p['class']:02d}"] = p
        if p.get("name"):
            by[p["name"]] = p
    if name not in by:
        raise KeyError(f"class {name!r} not in {sorted(by)}")
    m = cv2.imread(by[name]["mask"], cv2.IMREAD_GRAYSCALE)
    if m is None or m.shape[:2] != (size[1], size[0]):
        raise ValueError(f"mask {by[name]['mask']} unreadable or wrong size")
    return (m > 127).astype(np.uint8)


def road_segments(mask, m_per_px, seg_max_m, min_len_m):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    m = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    skel = cv2.ximgproc.thinning(m * 255, thinningType=cv2.ximgproc.THINNING_GUOHALL)
    import sknw
    g = sknw.build_sknw((skel > 0).astype(np.uint8), multi=True)
    segs, chain = [], 0
    for u, v, key, data in g.edges(keys=True, data=True):
        pts = data.get("pts")
        if pts is None or len(pts) < 2:
            continue
        pts = np.asarray(pts, dtype=np.float64)  # rows, cols
        # polyline length in metres
        d = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1)) * m_per_px
        if d.sum() < min_len_m:
            continue
        chain += 1
        # resample into straight pieces <= seg_max_m
        cum = np.concatenate([[0.0], np.cumsum(d)])
        n = max(1, int(math.ceil(cum[-1] / seg_max_m)))
        targets = np.linspace(0, cum[-1], n + 1)
        rc = np.stack([np.interp(targets, cum, pts[:, 0]), np.interp(targets, cum, pts[:, 1])], axis=1)
        widths = []
        for r, c in pts[::max(1, len(pts) // 20)]:
            widths.append(2.0 * dist[int(r), int(c)] * m_per_px)
        w_m = float(np.median(widths)) if widths else 3.5
        kind = "main" if w_m >= 6.0 else ("lane" if w_m >= 4.0 else "alley")
        for i in range(n):
            segs.append({"kind": kind, "chain": chain, "seq": i, "width_m": round(w_m, 2),
                         "a_px": [float(rc[i][1]), float(rc[i][0])], "b_px": [float(rc[i + 1][1]), float(rc[i + 1][0])]})
    return segs, skel


def building_lots(mask, m_per_px, min_m2, storeys, segs):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(m, connectivity=4)
    lots = []
    seg_pts = np.array([[(s["a_px"][0] + s["b_px"][0]) / 2, (s["a_px"][1] + s["b_px"][1]) / 2] for s in segs]) if segs else None
    for i in range(1, n):
        area_m2 = stats[i, cv2.CC_STAT_AREA] * m_per_px * m_per_px
        if area_m2 < min_m2:
            continue
        ys, xs = np.where(labels == i)
        pts = np.stack([xs, ys], axis=1).astype(np.float32)
        (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
        if w < h:
            w, h, ang = h, w, ang + 90.0
        W_cm = max(SNAP_CM, round(w * m_per_px * 100.0 / SNAP_CM) * SNAP_CM)
        D_cm = max(SNAP_CM, round(h * m_per_px * 100.0 / SNAP_CM) * SNAP_CM)
        yaw = float(ang % 180.0)
        # side midpoints in pixel space: 0 = -Y local (front), 1 = +X, 2 = +Y, 3 = -X
        a = math.radians(yaw)
        ux, uy = math.cos(a), math.sin(a)          # local +X in pixels
        vx, vy = -math.sin(a), math.cos(a)         # local +Y in pixels
        hw, hh = w / 2.0, h / 2.0
        mids = [(cx - vx * hh, cy - vy * hh), (cx + ux * hw, cy + uy * hw), (cx + vx * hh, cy + vy * hh), (cx - ux * hw, cy - uy * hw)]
        door = 0
        if seg_pts is not None and len(seg_pts):
            dmin = [float(np.min(np.hypot(seg_pts[:, 0] - mx, seg_pts[:, 1] - my))) for mx, my in mids]
            door = int(np.argmin(dmin))
        lots.append({"kind": "building", "centre_px": [float(cx), float(cy)], "size_cm": [W_cm, D_cm, storeys * 400.0],
                     "yaw_deg": yaw, "storeys": storeys, "door_side": door, "area_m2": round(area_m2, 1),
                     "roof_candidate": None, "roof_servable": False})
    return lots


def water_polys(mask, m_per_px):
    cs, _ = cv2.findContours(mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        if cv2.contourArea(c) * m_per_px * m_per_px < 25.0:
            continue
        c = cv2.approxPolyDP(c, 1.5, True)
        out.append([[float(p[0][0]), float(p[0][1])] for p in c])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes_json")
    ap.add_argument("--roads", required=True)
    ap.add_argument("--buildings", required=True)
    ap.add_argument("--water", default=None)
    ap.add_argument("--m-per-px", type=float, required=True, help="metres per pixel of the class masks")
    ap.add_argument("--origin-cm", nargs=2, type=float, default=[0.0, 0.0], help="world X,Y of pixel (0,0)")
    ap.add_argument("--segment-max-m", type=float, default=15.0)
    ap.add_argument("--min-road-m", type=float, default=8.0)
    ap.add_argument("--min-building-m2", type=float, default=16.0)
    ap.add_argument("--storeys", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    with open(a.classes_json, "r", encoding="utf-8") as fh:
        classes = json.load(fh)
    size = classes["size_px"]
    try:
        roads = load_mask(classes, a.roads, size)
        blds = load_mask(classes, a.buildings, size)
        water = load_mask(classes, a.water, size) if a.water else None
    except (KeyError, ValueError) as e:
        print(f"REFUSE: {e}")
        return 2

    segs, skel = road_segments(roads, a.m_per_px, a.segment_max_m, a.min_road_m)
    lots = building_lots(blds, a.m_per_px, a.min_building_m2, a.storeys, segs)
    wpolys = water_polys(water, a.m_per_px) if water is not None else []
    if not segs and not lots:
        print("NOTHING EXTRACTED: no road segments and no building lots")
        return 3

    ox, oy = a.origin_cm
    f = a.m_per_px * 100.0

    def to_cm(px):
        return [px[0] * f + ox, px[1] * f + oy]

    streets = []
    for i, s in enumerate(segs):
        streets.append({"kind": s["kind"], "id": f"street_{i:04d}", "chain": s["chain"], "seq": s["seq"],
                        "a_cm": to_cm(s["a_px"]), "b_cm": to_cm(s["b_px"]), "width_cm": round(s["width_m"] * 100.0)})
    buildings = []
    for i, b in enumerate(lots):
        c = to_cm(b["centre_px"])
        buildings.append({"kind": "building", "id": f"bld_{i:04d}", "loc_cm": [c[0], c[1], 0.0], "pad_z_cm": 0.0,
                          "yaw_deg": b["yaw_deg"], "size_cm": b["size_cm"], "storeys": b["storeys"], "door_side": b["door_side"],
                          "roof_candidate": None, "roof_servable": False, "area_m2": b["area_m2"]})
    plan = {
        "schema_version": "g2ue-town-plan-0.1",
        "_contract": "rows follow the proven R-TOWNKIT plan shape (buildings: loc_cm, size_cm on the 50 cm snap, storeys, yaw_deg, door_side; streets: segments <= segment_max_m with width_cm); roof fields are left for the kit's roof_servability step",
        "source_classes": os.path.abspath(a.classes_json), "source_image": classes.get("source"), "source_sha256": classes.get("source_sha256"),
        "m_per_px": a.m_per_px, "origin_cm": [ox, oy], "axis_mapping": "A: image column -> world X, image row -> world Y (verify with marker cubes)",
        "classes": {"roads": a.roads, "buildings": a.buildings, "water": a.water},
        "streets": streets, "buildings": buildings,
        "water_polygons_cm": [[to_cm(p) for p in poly] for poly in wpolys],
        "counts": {"streets": len(streets), "chains": len({s['chain'] for s in segs}), "buildings": len(buildings), "water_polygons": len(wpolys)},
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)

    # overlay for a visual check
    src = cv2.imread(classes["clusters_preview"]) if classes.get("clusters_preview") and os.path.isfile(classes["clusters_preview"]) else None
    canvas = src.copy() if src is not None else np.full((size[1], size[0], 3), 255, np.uint8)
    canvas[skel > 0] = (0, 0, 255)
    for s in segs:
        a_, b_ = s["a_px"], s["b_px"]
        cv2.line(canvas, (int(a_[0]), int(a_[1])), (int(b_[0]), int(b_[1])), (0, 0, 200), 2)
    for b in lots:
        cx, cy = b["centre_px"]
        w = b["size_cm"][0] / 100.0 / a.m_per_px
        h = b["size_cm"][1] / 100.0 / a.m_per_px
        box = cv2.boxPoints(((cx, cy), (w, h), b["yaw_deg"]))
        cv2.polylines(canvas, [box.astype(np.int32)], True, (255, 0, 0), 2)
        ang = math.radians(b["yaw_deg"])
        side = b["door_side"]
        dirs = [(math.sin(ang), -math.cos(ang)), (math.cos(ang), math.sin(ang)), (-math.sin(ang), math.cos(ang)), (-math.cos(ang), -math.sin(ang))]
        dx, dy = dirs[side]
        half = (h if side in (0, 2) else w) / 2.0
        cv2.circle(canvas, (int(cx + dx * half), int(cy + dy * half)), 3, (0, 180, 0), -1)
    ov = os.path.splitext(a.out)[0] + ".overlay.png"
    cv2.imwrite(ov, canvas)
    print(json.dumps(plan["counts"], indent=1))
    print("overlay:", ov)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
