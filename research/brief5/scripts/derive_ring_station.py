#!/usr/bin/env python3
"""Brief 5 T1 — derive the second station: the camera whose 128-512 m ring holds
the most in-frustum ConiferPine + SpruceSub (the two card species). Reuses
derive_forest_station's geometry (numpy, same frustum). READ-ONLY.

The ring is where the card is drawn LIVE (card engages ~88-128 m, cull 512 m), so
this station maximises the pixels under test in T1's 128-512 m band.
Output: research/brief5/input/ring_station.json.
"""
import json
import math
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import derive_forest_station as dfs  # load, wrap_pi

REPO = dfs.REPO
CARD_SPECIES = ["ConiferPine", "SpruceSub"]
RING_MIN_CM = 12800.0   # 128 m
RING_MAX_CM = 51200.0   # 512 m


def count_ring(cx, cy, cz, yaw_deg, pitch_deg, sp_arr, half_h, half_v):
    yaw = math.radians(yaw_deg)
    cam_pitch = math.radians(pitch_deg)
    per = {}
    tot = 0
    for sp in CARD_SPECIES:
        a = sp_arr[sp]
        xyz = a["xyz_s"]
        dx = xyz[:, 0] - cx
        dy = xyz[:, 1] - cy
        dz = xyz[:, 2] - cz
        horiz = np.hypot(dx, dy)
        d = np.hypot(horiz, dz)
        in_ring = (d >= RING_MIN_CM) & (d <= RING_MAX_CM) & (d <= a["cull_cm"])
        if not in_ring.any():
            per[sp] = 0
            continue
        bearing = np.arctan2(dy, dx)
        ang_h = np.abs(dfs.wrap_pi(bearing - yaw))
        safe = horiz > 0
        pitch_base = np.where(safe, np.arctan2(dz, np.where(safe, horiz, 1.0)),
                              cam_pitch)
        pt = in_ring & (ang_h <= half_h) & (np.abs(pitch_base - cam_pitch) <= half_v)
        n = int(pt.sum())
        per[sp] = n
        tot += n
    return tot, per


def nearest_infrustum_m(cx, cy, cz, yaw_deg, pitch_deg, sp_arr, half_h, half_v):
    """Distance (m) to the nearest tree of ANY species inside the frustum -- used
    to reject a camera with a trunk filling the near frame (V1: no tree < 15 m)."""
    yaw = math.radians(yaw_deg)
    cam_pitch = math.radians(pitch_deg)
    best = 1e18
    for sp in sp_arr:
        xyz = sp_arr[sp]["xyz_s"]
        dx = xyz[:, 0] - cx
        dy = xyz[:, 1] - cy
        dz = xyz[:, 2] - cz
        horiz = np.hypot(dx, dy)
        d = np.hypot(horiz, dz)
        bearing = np.arctan2(dy, dx)
        ang_h = np.abs(dfs.wrap_pi(bearing - yaw))
        safe = horiz > 0
        pitch_base = np.where(safe, np.arctan2(dz, np.where(safe, horiz, 1.0)),
                              cam_pitch)
        infr = (ang_h <= half_h) & (np.abs(pitch_base - cam_pitch) <= half_v)
        if infr.any():
            best = min(best, float(d[infr].min()))
    return best / 100.0


def main():
    r8k, fov_h, res, sp_arr = dfs.load()
    w, h = res
    half_h = math.radians(fov_h) / 2.0
    half_v = math.atan(math.tan(half_h) * (h / float(w)))
    vfov = math.degrees(2.0 * half_v)
    eye_cm = 175.0

    BIN = 25600.0
    binc = Counter()
    for sp in CARD_SPECIES:
        for x, y in sp_arr[sp]["xyz_s"][:, :2]:
            binc[(int(x // BIN), int(y // BIN))] += 1
    MIN_CLEAR_M = 15.0  # V1: reject a camera with a tree closer than 15 m in frame
    candidates = binc.most_common(25)
    best = None
    best_pos = None
    rejected_near = 0
    for (bx, by), _n in candidates:
        cx = (bx + 0.5) * BIN
        cy = (by + 0.5) * BIN
        cz = dfs.ps.heightmap_z(cx, cy, r8k) + eye_cm
        for pitch in (-5.0, 0.0, 5.0):
            for yaw in range(0, 360, 10):
                if nearest_infrustum_m(cx, cy, cz, float(yaw), pitch, sp_arr,
                                       half_h, half_v) < MIN_CLEAR_M:
                    rejected_near += 1
                    continue
                tot, per = count_ring(cx, cy, cz, float(yaw), pitch, sp_arr,
                                      half_h, half_v)
                if best is None or tot > best["ring_card_trees_total"]:
                    best = {"yaw_deg": float(yaw), "pitch_deg": pitch,
                            "ring_card_trees_total": tot, "per_species": per}
                    best_pos = (cx, cy, cz, bx, by)
    cx0, cy0, cz, bx0, by0 = best_pos
    clear = nearest_infrustum_m(cx0, cy0, cz, best["yaw_deg"], best["pitch_deg"],
                                sp_arr, half_h, half_v)
    out = {
        "_what": "Brief 5 V1 ring station: camera maximising ConiferPine + "
                 "SpruceSub in the 128-512 m ring, with NO tree within 15 m of the "
                 "camera in frame (V1 clearance rule).",
        "_method": "top-25 densest card-species 256 m bins x yaw(0..350/10) x "
                   "pitch{-5,0,5}; reject any camera with a tree < 15 m in the "
                   "frustum; then count in-frustum ConiferPine+SpruceSub with "
                   "128 m <= d <= min(512 m, cull). Same frustum as "
                   "derive_forest_station.",
        "min_clearance_m": MIN_CLEAR_M,
        "nearest_infrustum_tree_m": round(clear, 1),
        "candidates_rejected_for_near_tree": rejected_near,
        "ring_m": [RING_MIN_CM / 100.0, RING_MAX_CM / 100.0],
        "chosen_bin": [bx0, by0],
        "camera": {"x_cm": round(cx0, 1), "y_cm": round(cy0, 1),
                   "z_cm": round(cz, 1), "pitch_deg": best["pitch_deg"],
                   "yaw_deg": best["yaw_deg"]},
        "fov_h_deg": fov_h, "vfov_deg": vfov, "res": res,
        "ring_card_trees_total": best["ring_card_trees_total"],
        "per_species": best["per_species"],
    }
    p = os.path.join(REPO, "research", "brief5", "input", "ring_station_v1.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("ring station bin (%d,%d) centre (%.0f,%.0f) z %.0f yaw %.0f pitch %.0f "
          "-> ring card trees %d %s"
          % (bx0, by0, cx0, cy0, cz, best["yaw_deg"], best["pitch_deg"],
             best["ring_card_trees_total"], best["per_species"]))
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
