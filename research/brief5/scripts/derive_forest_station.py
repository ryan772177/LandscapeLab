#!/usr/bin/env python
"""Brief 5 v3 Task 3 -- derive a forest_floor perf station.

READ-ONLY. The 2026-08-15 forest_floor station recorded no camera coordinates
(only "153,796 resident", editor full-residency). So derive one reproducibly:
the camera sits at eye height inside a dense tree cluster and looks in the
heading that maximises in-frustum-in-cull trees (target >= 5000).

Frustum geometry is IDENTICAL to density_census.frustum_geom (verified: for
forward(yaw,pitch), fyaw == yaw_rad and cam_pitch == pitch_rad), just vectorised
with numpy so the position x heading x pitch search is tractable. Base-point
(point_in_frustum) is the reported count; the base->top segment count is also
computed.

Output: research/brief5/input/forest_station.json.
"""
import json
import math
import os
import sys
from collections import Counter

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import perf_standalone as ps  # heightmap_z

TREE_SPECIES = ["Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"]


def load(plans_dir=None):
    plans_dir = plans_dir or os.path.join(REPO, "foliage")
    r8k = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                         encoding="utf-8-sig"))
    perc = r8k["perception"]
    fov_h = float(perc["declared_camera"]["fov_h_deg"])
    res = perc["declared_camera"]["res"]
    sp_arr = {}
    for sp in TREE_SPECIES:
        d = json.load(open(os.path.join(plans_dir, "alpine_8k_%s.json" % sp),
                           encoding="utf-8-sig"))
        inst = np.array([[i[0], i[1], i[2], i[6]] for i in d["instances"]],
                        dtype=np.float64)  # x,y,z,scale
        sp_arr[sp] = {
            "xyz_s": inst,
            "cull_cm": float(d["cull_cm"]),
            "mesh_height_cm": float(d["cull_derivation"]["mesh_height_m"]) * 100.0,
        }
    return r8k, fov_h, res, sp_arr


def wrap_pi(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def count_at(cx, cy, cz, yaw_deg, pitch_deg, sp_arr, half_h, half_v):
    yaw = math.radians(yaw_deg)
    cam_pitch = math.radians(pitch_deg)
    per = {}
    tot_pt = tot_seg = 0
    for sp in TREE_SPECIES:
        a = sp_arr[sp]
        xyz = a["xyz_s"]
        dx = xyz[:, 0] - cx
        dy = xyz[:, 1] - cy
        dz = xyz[:, 2] - cz
        horiz = np.hypot(dx, dy)
        d = np.hypot(horiz, dz)
        in_cull = d <= a["cull_cm"]
        if not in_cull.any():
            per[sp] = {"in_frustum_in_cull": 0, "in_frustum_in_cull_segment": 0}
            continue
        bearing = np.arctan2(dy, dx)
        ang_h = np.abs(wrap_pi(bearing - yaw))
        # guard horiz==0 -> pitch = cam_pitch (at camera column)
        safe = horiz > 0
        pitch_base = np.where(safe, np.arctan2(dz, np.where(safe, horiz, 1.0)),
                              cam_pitch)
        top_cm = dz + a["mesh_height_cm"] * xyz[:, 3]
        pitch_top = np.where(safe, np.arctan2(top_cm, np.where(safe, horiz, 1.0)),
                             cam_pitch)
        az_ok = ang_h <= half_h
        pt = in_cull & az_ok & (np.abs(pitch_base - cam_pitch) <= half_v)
        seg = (in_cull & az_ok
               & (pitch_top >= cam_pitch - half_v)
               & (pitch_base <= cam_pitch + half_v))
        npt = int(pt.sum())
        nseg = int(seg.sum())
        per[sp] = {"in_frustum_in_cull": npt, "in_frustum_in_cull_segment": nseg}
        tot_pt += npt
        tot_seg += nseg
    return tot_pt, tot_seg, per


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plans", default=None,
                    help="dir of alpine_8k_<species>.json (default foliage/)")
    ap.add_argument("--only-bin", default=None,
                    help="ix,iy of a single 256 m bin to stand in (default: "
                         "search the top-20 densest). Used for the open_max "
                         "station: the densest post-ceiling bin outside all discs.")
    ap.add_argument("--out", default=None,
                    help="output station json (default research/brief5/input/"
                         "forest_station.json)")
    ap.add_argument("--name", default="forest_floor",
                    help="station name recorded in _what")
    a = ap.parse_args()
    r8k, fov_h, res, sp_arr = load(a.plans)
    # vfov via the same formula density_census uses
    w, h = res
    half_hf = math.radians(fov_h) / 2.0
    half_v = math.atan(math.tan(half_hf) * (h / float(w)))
    vfov = math.degrees(2.0 * half_v)
    half_h = half_hf
    eye_cm = 175.0

    BIN = 25600.0
    binc = Counter()
    for sp in TREE_SPECIES:
        xy = sp_arr[sp]["xyz_s"][:, :2]
        for x, y in xy:
            binc[(int(x // BIN), int(y // BIN))] += 1

    TOPK = 20
    if a.only_bin:
        _bx, _by = (int(v) for v in a.only_bin.split(","))
        candidates = [((_bx, _by), binc.get((_bx, _by), 0))]
    else:
        candidates = binc.most_common(TOPK)
    best = None
    best_pos = None
    for (bx, by), _n in candidates:
        cx = (bx + 0.5) * BIN
        cy = (by + 0.5) * BIN
        cz = ps.heightmap_z(cx, cy, r8k) + eye_cm
        for pitch in (-5.0, 0.0, 5.0):
            for yaw in range(0, 360, 10):
                tot_pt, tot_seg, per = count_at(cx, cy, cz, float(yaw), pitch,
                                                sp_arr, half_h, half_v)
                if best is None or tot_pt > best["in_frustum_in_cull_total"]:
                    best = {"yaw_deg": float(yaw), "pitch_deg": pitch,
                            "in_frustum_in_cull_total": tot_pt,
                            "in_frustum_in_cull_segment_total": tot_seg,
                            "per_species": per}
                    best_pos = (cx, cy, cz, bx, by)
    cx0, cy0, cz, bx0, by0 = best_pos

    out = {
        "_what": "Brief 5 %s station, DERIVED to maximise in-frustum-in-cull "
                 "trees (target >= 5000)." % a.name,
        "_plans_dir": (a.plans or "foliage"),
        "_only_bin": a.only_bin,
        "_method": "Top-20 densest 256 m tree-bins as candidate camera positions; "
                   "ground z = heightmap + 175 cm eye; yaw swept 0..350 step 10, "
                   "pitch in {-5,0,5}; the (position,yaw,pitch) with the most "
                   "in-frustum-in-cull (base-point) trees is chosen. Frustum "
                   "geometry identical to density_census (numpy-vectorised).",
        "_read_back_source": {
            "instances": (a.plans or "foliage") + "/alpine_8k_<species>.json",
            "cull_cm": "each plan's cull_cm",
            "ground_z": "perf_standalone.heightmap_z(recipe) + 175 cm eye",
            "declared_camera": "recipes/alpine_8k.json perception.declared_camera",
        },
        "chosen_bin": {"bin_size_cm": BIN, "bin_xy_index": [bx0, by0],
                       "densest_bin_xy_index": list(candidates[0][0]),
                       "densest_bin_trees": candidates[0][1],
                       "searched_topk_bins": TOPK,
                       "bin_center_cm": [cx0, cy0]},
        "camera": {"x_cm": round(cx0, 1), "y_cm": round(cy0, 1),
                   "z_cm": round(cz, 1),
                   "pitch_deg": best["pitch_deg"], "yaw_deg": best["yaw_deg"]},
        "fov_h_deg": fov_h, "vfov_deg": vfov, "res": res,
        "in_frustum_in_cull_total": best["in_frustum_in_cull_total"],
        "in_frustum_in_cull_segment_total": best["in_frustum_in_cull_segment_total"],
        "per_species": best["per_species"],
        "meets_5000_target": best["in_frustum_in_cull_total"] >= 5000,
        "_target_note": ("If below 5000: the forest at the declared 90 deg hFOV / "
                         "512 m cull does not put 5000 live trees in one frustum "
                         "anywhere (density ~0.005 trees/m2); this is the MAX "
                         "achievable and is reported as such, not padded."),
    }
    p = a.out or os.path.join(REPO, "research", "brief5", "input",
                              "forest_station.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("densest bin %s (%d); chosen bin (%d,%d) centre (%.0f,%.0f) z %.0f"
          % (candidates[0][0], candidates[0][1], bx0, by0, cx0, cy0, cz))
    print("best yaw %.0f pitch %.0f -> in_frustum_in_cull %d (seg %d) meets>=5000 %s"
          % (best["yaw_deg"], best["pitch_deg"], best["in_frustum_in_cull_total"],
             best["in_frustum_in_cull_segment_total"], out["meets_5000_target"]))
    for sp, v in best["per_species"].items():
        print("   %-14s %5d" % (sp, v["in_frustum_in_cull"]))
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
