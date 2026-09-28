#!/usr/bin/env python3
"""Brief 5 isolated_check finder (operator-ordered, R2 follow-up). HOST-side, no
editor.

Picks one ConiferPine and one SpruceSub instance that render UNCONTAMINATED: a
camera at 250-400 m whose screen box for the target contains NO other tree, so the
Mesh LOD Coloration of that single box is the target's own LOD, not a neighbour's
(R2's classifier was contaminated by overlapping boxes with no occlusion).

Method: KDTree nearest-neighbour over all ~185k trees to rank the most isolated
target instances; then for each candidate sweep camera range (250-400 m) x yaw and
KEEP the first (camera, target) where projecting every other tree within the 512 m
cull leaves the target box intruder-free. Writes per-species camera station JSONs
(iso_<sp>_station.json) + iso_targets.json (top candidates, each with its expected
screen box), which the capture drives and the analyzer reads.

Projection matches c1_lod_readback.species_boxes (UE convention, FOV_H 90, 4K).
"""
import json
import math
import os

import numpy as np
from scipy.spatial import cKDTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
FOLIAGE = os.path.join(REPO, "foliage")
SPECIES = ["ConiferPine", "SpruceSub", "Conifer", "SpruceSapling"]
TARGETS = ["ConiferPine", "SpruceSub"]
W, H = 3840, 2160
FOV_H = 90.0
CULL_CM = 51200.0            # 512 m applied cull
RANGES_M = [300, 320, 280, 350, 260, 380, 400]
YAW_STEP = 12
TOPK = 400                   # isolation-ranked candidates to try per species
N_OUT = 3                    # camera stations to emit per species (fallbacks)
# ANCHOR: the first iso pass rendered pure white -- the isolated instances sat at
# ~467 m map-edge alpine (nn 89-119 m) where the cell did not render / snow blew
# the LOD colours to 255. The forest_floor + ring stations DID render (near map
# centre, ~198 m). So constrain candidates to within ANCHOR_RADIUS of the
# forest_floor camera, the proven-rendering region.
ANCHOR_CM = (-166400.0, 192000.0)     # forest_station.json camera xy
ANCHOR_RADIUS_CM = 180000.0           # 1.8 km
MIN_BOX_W, MIN_BOX_H = 8, 16
half_h = math.radians(FOV_H) / 2.0
half_v = math.atan(math.tan(half_h) * (H / float(W)))
tanh, tanv = math.tan(half_h), math.tan(half_v)


def load():
    xyz, hcm, sp = [], [], []
    for s in SPECIES:
        d = json.load(open(os.path.join(FOLIAGE, "alpine_8k_%s.json" % s),
                           encoding="utf-8-sig"))
        h_m = d["cull_derivation"]["mesh_height_m"]
        for inst in d["instances"]:
            xyz.append((inst[0], inst[1], inst[2]))
            scale = inst[6] if len(inst) > 6 else 1.0
            hcm.append(h_m * 100.0 * scale)
            sp.append(s)
    return np.array(xyz, dtype=np.float64), np.array(hcm), np.array(sp)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def project(cam, cyaw, cpitch, ipos, top_cm):
    """Screen box (x0,y0,x1,y1) for a tree, or None if out of frustum/behind."""
    cx, cy, cz = cam
    dx, dy, dz = ipos[0] - cx, ipos[1] - cy, ipos[2] - cz
    horiz = math.hypot(dx, dy)
    if horiz <= 1.0:
        return None
    ah = wrap(math.atan2(dy, dx) - cyaw)
    if abs(ah) > half_h:
        return None
    crown = 0.25 * top_cm
    av_base = math.atan2(dz, horiz) - cpitch
    av_top = math.atan2(dz + top_cm, horiz) - cpitch
    dah = math.atan2(crown, horiz)
    sx0 = W / 2 * (1 + math.tan(ah - dah) / tanh)
    sx1 = W / 2 * (1 + math.tan(ah + dah) / tanh)
    sy_top = H / 2 * (1 - math.tan(av_top) / tanv)
    sy_base = H / 2 * (1 - math.tan(av_base) / tanv)
    x0 = max(0, min(W - 1, min(sx0, sx1)))
    x1 = max(0, min(W, max(sx0, sx1)))
    y0 = max(0, min(H - 1, sy_top))
    y1 = max(0, min(H, sy_base))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return (x0, y0, x1, y1)


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def main():
    xyz, hcm, sp = load()
    tree = cKDTree(xyz)
    out = {"_what": "isolated ConiferPine + SpruceSub camera stations for an "
           "uncontaminated single-box LOD read (R2 follow-up).",
           "fov_h_deg": FOV_H, "res": [W, H], "cull_cm": CULL_CM, "targets": {}}
    for tsp in TARGETS:
        idx_all = np.where(sp == tsp)[0]
        # constrain to the proven-rendering region around the forest_floor anchor
        dxy = xyz[idx_all][:, :2] - np.array(ANCHOR_CM)
        near = np.hypot(dxy[:, 0], dxy[:, 1]) <= ANCHOR_RADIUS_CM
        idx = idx_all[near]
        # nearest OTHER tree (k=2: self + nearest neighbour)
        dists, _ = tree.query(xyz[idx], k=2)
        nn_other = dists[:, 1]
        order = idx[np.argsort(-nn_other)]          # most isolated first
        chosen = []
        for ti in order[:TOPK]:
            tpos = xyz[ti]
            ttop = hcm[ti]
            # candidate neighbours once (max range + margin)
            ball = tree.query_ball_point(tpos, CULL_CM + 5000.0)
            ball = [j for j in ball if j != ti]
            nb_pos = xyz[ball]
            nb_top = hcm[ball]
            done = False
            for Rm in RANGES_M:
                if done:
                    break
                R = Rm * 100.0
                for yaw_deg in range(0, 360, YAW_STEP):
                    a = math.radians(yaw_deg)
                    # camera ABOVE the treetop, aimed DOWN at the crown, so the
                    # background behind the target is TERRAIN, not sky (the first
                    # pass looked ~horizontal into blown-white alpine sky -> 0 px).
                    cam = (tpos[0] + R * math.cos(a), tpos[1] + R * math.sin(a),
                           tpos[2] + ttop + 1500.0)
                    # look at crown centre
                    lx, ly, lz = tpos[0] - cam[0], tpos[1] - cam[1], \
                        (tpos[2] + 0.5 * ttop) - cam[2]
                    cyaw = math.atan2(ly, lx)
                    cpitch = math.atan2(lz, math.hypot(lx, ly))
                    tbox = project(cam, cyaw, cpitch, tpos, ttop)
                    if tbox is None:
                        continue
                    if (tbox[2] - tbox[0] < MIN_BOX_W or
                            tbox[3] - tbox[1] < MIN_BOX_H):
                        continue
                    # intruder test: any other tree box overlapping the target box
                    intruder = False
                    for k in range(len(ball)):
                        d = math.dist(cam, nb_pos[k])
                        if d > CULL_CM:
                            continue
                        b = project(cam, cyaw, cpitch, nb_pos[k], nb_top[k])
                        if b is not None and overlap(tbox, b):
                            intruder = True
                            break
                    if intruder:
                        continue
                    rng_m = round(math.dist(cam, tpos) / 100.0, 1)
                    if not (250.0 <= rng_m <= 400.0):
                        continue
                    chosen.append({
                        "instance_index_in_species": int(np.where(idx == ti)[0][0]),
                        "world_cm": [round(float(x), 1) for x in tpos],
                        "top_cm": round(float(ttop), 1),
                        "nn_other_m": round(float(nn_other[np.where(idx == ti)[0][0]]) / 100.0, 1),
                        "camera": {"x_cm": round(cam[0], 1), "y_cm": round(cam[1], 1),
                                   "z_cm": round(cam[2], 1),
                                   "pitch_deg": round(math.degrees(cpitch), 3),
                                   "yaw_deg": round(math.degrees(cyaw), 3)},
                        "range_m": rng_m,
                        "expected_box": [round(v, 1) for v in tbox]})
                    done = True
                    break
            if len(chosen) >= N_OUT:
                break
        out["targets"][tsp] = chosen
        # emit the primary station for the capture payload
        if chosen:
            st = {"_what": "isolated %s camera for uncontaminated LOD read" % tsp,
                  "camera": chosen[0]["camera"], "fov_h_deg": FOV_H,
                  "res": [W, H], "target_world_cm": chosen[0]["world_cm"],
                  "target_top_cm": chosen[0]["top_cm"],
                  "expected_box": chosen[0]["expected_box"]}
            json.dump(st, open(os.path.join(IN, "iso_%s_station.json" % tsp), "w",
                               encoding="utf-8"), indent=1)
        print("%s: %d isolated camera(s); primary range %s m, nn_other %s m"
              % (tsp, len(chosen),
                 chosen[0]["range_m"] if chosen else "-",
                 chosen[0]["nn_other_m"] if chosen else "-"))
    json.dump(out, open(os.path.join(IN, "iso_targets.json"), "w",
                        encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
