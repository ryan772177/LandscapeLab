#!/usr/bin/env python3
"""encounters_in_water.py -- Brief-4 CARVE_PLAN T8.

The SILENT GAP (RULING §4.3): encounters/alpine_8k_verified.json stamps FROZEN
evidence, so the freshness machinery will never flag it -- yet the 317 encounters
were placed on the PRE-water surface and some may sit inside a §7 water footprint.

This detector reports, with sample counts (rule 13 -- a zero must be a MEASURED
zero, not an unrun check), how many of the 317 fall inside each water body's
connected-component footprint: A@180 (id 4893), B@140 (id 11877), D@590.9
(id 8377), and the 10 north-cascade pools at their spill surfaces.

Footprint = the flood-fill connected component at the level (hydro level_slice) --
NOT an elevation band: an encounter is drowned only if it is INSIDE the water
body's footprint, so terrain elsewhere at the same height is not falsely flagged.
Reuses research/brief4/scripts/hydro_derive.py (NN24, one derivation).

This script only DETECTS + reports; relocation/removal is a separate step run
only if the count is non-zero.

Usage:
  python encounters_in_water.py --png <4x.png> --json <sidecar> --hydro <hydro_amendment>
      --water <recipes/water.json> --encounters <verified.json> --out <dir>
"""
import argparse, io, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hydro_derive as hd


def _load(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", required=True)
    ap.add_argument("--json", required=True)      # 4x sidecar
    ap.add_argument("--hydro", required=True)      # hydro_amendment.json
    ap.add_argument("--water", required=True)      # recipes/water.json
    ap.add_argument("--encounters", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    side = _load(a.json)
    cell = side["image"]["metres_per_pixel"]
    mpu = side["z_mapping"]["metres_per_16bit_unit"]
    z0 = side["z_mapping"]["height_m_of_unit_0"]
    ox, oy = side["world_origin"]["landscape_location_cm"][:2]
    from PIL import Image
    h = np.array(Image.open(a.png)).astype(np.float64) * mpu + z0
    nrow, ncol = h.shape
    hf = hd.fill_sinks(h)
    _L, lab, _d = hd.lakes(h, hf, cell, 2.0, 4000.0)

    water = _load(a.water)
    hydro = _load(a.hydro)
    pool_surface = {p["fill_lake_id"]: p["surface_m"]
                    for p in hydro["south_river_ladder"]["pools_over_2m"]}

    # build the water bodies to test: the 3 lakes + the 10 cascade pools
    bodies = []
    for lk in water["lakes"]:
        bodies.append((lk["name"], lk["id"], lk["level_m"]))
    for pid in water["north_cascade"]["pool_ids"]:
        if pid in {b[1] for b in bodies}:
            continue  # D (8377) is both a lake and the top cascade pool
        lvl = pool_surface.get(pid)
        if lvl is None:
            print("WARN: no surface_m for cascade pool %d" % pid)
            continue
        bodies.append(("cascade_%d" % pid, pid, lvl))

    masks = {}
    for name, bid, lvl in bodies:
        sl = hd.level_slice(lab, h, bid, lvl, cell)
        masks[name] = (sl["mask"] if sl is not None
                       else np.zeros(h.shape, bool), bid, lvl)

    enc = _load(a.encounters)
    rows = enc["encounters"]

    def to_grid(x_cm, y_cm):
        col = int(round((x_cm - ox) / (cell * 100.0)))
        row = int(round((y_cm - oy) / (cell * 100.0)))
        return col, row

    per_body = {name: [] for name, _, _ in bodies}
    drowned = []
    off_grid = 0
    for i, r in enumerate(rows):
        x, y, z = r["loc_cm"]
        col, row = to_grid(x, y)
        if not (0 <= row < nrow and 0 <= col < ncol):
            off_grid += 1
            continue
        hit = None
        for name, (m, bid, lvl) in masks.items():
            if m[row, col]:
                hit = (name, bid, lvl)
                break
        if hit:
            name, bid, lvl = hit
            per_body[name].append(i)
            drowned.append(dict(index=i, archetype=r.get("archetype"),
                                loc_cm=r["loc_cm"], elevation_m=r.get("elevation_m"),
                                col_row=[col, row], body=name, level_m=lvl,
                                below_level=bool(r.get("elevation_m", 1e9) < lvl)))

    result = dict(
        _what="Brief-4 T8: encounters inside a §7 water footprint",
        total_encounters=len(rows), off_grid=off_grid,
        bodies_tested=[dict(name=n, id=b, level_m=l) for n, b, l in bodies],
        drowned_total=len(drowned),
        drowned_by_body={n: len(ix) for n, ix in per_body.items() if ix},
        drowned=drowned)
    json.dump(result, open(os.path.join(a.out, "encounters_in_water.json"), "w"),
              indent=1)

    print("encounters tested: %d  (off-grid: %d)" % (len(rows), off_grid))
    print("water bodies tested: %d (3 lakes + %d cascade pools)"
          % (len(bodies), len(bodies) - 3))
    print("DROWNED TOTAL: %d" % len(drowned))
    for n, ix in per_body.items():
        if ix:
            print("  %-14s : %d  (indices %s)" % (n, len(ix), ix[:10]))
    if not drowned:
        print("  (measured zero -- no encounter falls inside any water footprint)")
    else:
        for d in drowned[:20]:
            print("  #%d %-14s in %-12s elev %.1f m vs level %.1f m  below=%s"
                  % (d["index"], d["archetype"], d["body"], d["elevation_m"],
                     d["level_m"], d["below_level"]))
    print("wrote", os.path.join(a.out, "encounters_in_water.json"))


if __name__ == "__main__":
    main()
