"""build_water_exclusion_mask.py -- Brief-4 T8: the placer's water mask.

Produces encounters/alpine_8k_water_exclusion.npz: the UNION of the §7
water-body connected-component footprints — 12 distinct bodies (13 declared
entries; cascade pool 8377 IS lake D, deduped, D at the ruled 590.9) — on
the committed 4x heightmap grid, plus the grid origin/cell so the placer
maps world cm -> grid with numpy alone (no scipy/skimage at placer time).

ONE DECLARATION (non-negotiable 24): the footprints are DERIVED here from
recipes/water.json + the committed 4x heightmap via hydro_derive.level_slice
(the SAME derivation the detector and water_derive use, NN24) -- the placer
does NOT re-describe water geometry, it reads this derived mask. The npz is
regenerable and provenance-stamped; re-running is deterministic.

Read-back (rule 13): reports the union cell count and per-body counts; A/B/D
are asserted byte-equal to the saved 2026-09-19 masks.

Usage:
  python build_water_exclusion_mask.py [--out encounters/alpine_8k_water_exclusion.npz]
"""
import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import hydro_derive as hd  # noqa: E402


def _load(p):
    with io.open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        REPO, "encounters", "alpine_8k_water_exclusion.npz"))
    a = ap.parse_args()

    side = _load(os.path.join(REPO, "research/brief4/input/alpine_8k_height_4x.json"))
    cell = float(side["image"]["metres_per_pixel"])
    mpu = float(side["z_mapping"]["metres_per_16bit_unit"])
    z0 = float(side["z_mapping"]["height_m_of_unit_0"])
    ox, oy = [float(v) for v in side["world_origin"]["landscape_location_cm"][:2]]
    h = np.array(Image.open(os.path.join(
        REPO, "research/brief4/input/alpine_8k_height_4x_2033.png"))).astype(
            np.float64) * mpu + z0
    hf = hd.fill_sinks(h)
    _L, lab, _d = hd.lakes(h, hf, cell, 2.0, 4000.0)

    water = _load(os.path.join(REPO, "recipes/water.json"))
    hydro = _load(os.path.join(REPO, "research/brief4/input/hydro_amendment.json"))
    pool_surface = {p["fill_lake_id"]: p["surface_m"]
                    for p in hydro["south_river_ladder"]["pools_over_2m"]}

    bodies = [(lk["name"], lk["id"], float(lk["level_m"]))
              for lk in water["lakes"]]
    for pid in water["north_cascade"]["pool_ids"]:
        if pid in {b[1] for b in bodies}:
            continue
        lvl = pool_surface.get(pid)
        if lvl is None:
            sys.exit("REFUSE: no surface_m for cascade pool %d" % pid)
        bodies.append(("cascade_%d" % pid, pid, float(lvl)))

    saved = {4893: "footprint_A_id4893.npy", 11877: "footprint_B_id11877.npy",
             8377: "footprint_D_id8377.npy"}
    union = np.zeros(h.shape, dtype=bool)
    per_body = {}
    for name, bid, lvl in bodies:
        sl = hd.level_slice(lab, h, bid, lvl, cell)
        if sl is None:
            sys.exit("REFUSE: level_slice None for %s (id %d)" % (name, bid))
        m = sl["mask"]
        if bid in saved:
            ref = np.load(os.path.join(
                REPO, "_verify/brief4/water_derive_2026-09-19",
                saved[bid])).astype(bool)
            if not np.array_equal(ref, m):
                sys.exit("REFUSE: %s mask != saved 2026-09-19 (%d vs %d)"
                         % (name, m.sum(), ref.sum()))
        union |= m
        per_body[name] = int(m.sum())

    np.savez_compressed(
        a.out, mask=union, origin_cm=np.array([ox, oy]),
        cell_m=np.array([cell]),
        meta=np.array([json.dumps({
            "_what": "Brief-4 T8 placer water exclusion: UNION of 12 distinct "
                     "§7 water-body footprints (13 declared; pool 8377 == "
                     "lake D, deduped) on the 4x grid.",
            "bodies": len(bodies), "union_cells": int(union.sum()),
            "per_body": per_body,
            "derivation": "research/brief4/scripts/build_water_exclusion_mask.py",
            "grid_shape": list(h.shape)})]))
    print("wrote %s: %d bodies, union %d cells (%.1f ha)"
          % (a.out, len(bodies), int(union.sum()),
             union.sum() * cell * cell / 1e4))
    print("  per body:", per_body)


if __name__ == "__main__":
    main()
