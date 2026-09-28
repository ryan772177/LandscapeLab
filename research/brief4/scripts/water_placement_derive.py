"""water_placement_derive.py — derive the water-surface PLACEMENT PLAN (T5b).

OFF-DISK, read-only over inputs; writes ONE plan JSON + evidence. No engine
API. The engine step (scripts/payloads/spawn_water_set.py) READS the plan —
pipeline rule 2: every scene parameter comes from JSON, never hardcoded.

WHY CLIPPING NEEDS MORE THAN A BBOX (recipes/water.json
_placement_MUST_clip_to_connected_component, measured 2026-09-19): a plane
sized to a lake's bbox covers terrain BELOW the water level that is OUTSIDE
the lake's connected component — D@590.9 reads 98.7 ha over its bbox vs the
true 49.6 ha basin, because the bbox contains the cascade descent. A plane
at level Z renders water over every covered cell with terrain < level; cells
with terrain >= level occlude the plane and are harmless. So the unit of
correctness is the SAFE CELL: safe = (in component) OR (terrain >= level).

DECOMPOSITION. Per surface, on the 4 m/px grid:
  1. component mask via hydro_derive.level_slice (NN24: the ONE derivation —
     the same function that produced the ruled areas; for A/B/D the saved
     _verify masks are asserted BYTE-EQUAL to the recomputation first).
  2. If every cell in the component's tight bbox is safe → ONE plane over
     the bbox.
  3. Else: row-band strips. Bands of BAND_ROWS rows; within a band, maximal
     column runs of all-rows-safe columns that contain >= 1 component cell
     become planes. Component cells in columns unsafe elsewhere in the band
     are retried at band height 1 (4 m). Guarantees, both MEASURED after
     placement synthesis (rule 13, counts beside verdicts):
       coverage: every component cell under >= 1 plane (uncovered == 0)
       cleanliness: no plane covers an unsafe cell (stray == 0)
     Planes within a surface never overlap (coplanar same-Z overlap would
     z-fight): each band owns its rows exclusively; runs are disjoint.

FALLS. 10 by-construction cascade lips (hydro_amendment pools_over_2m rows
whose fill_lake_id is in north_cascade.pools_ids — count ASSERTED == 10) +
lake A's inflow fall from recipes/water.json (count 1) = 11 placeholders
(water.json total_placed_falls == 11, asserted). Each is DATA + a minimal
vertical plane: width FALL_WIDTH_M, height = the lip's drop, top at the
pool's outlet level, yawed to face the D8 downhill direction at the lip.

Z RULE: world_cm = level_m * 100 (water.json _placement; do NOT add
landscape z — that spelling is superseded/WRONG).

Inputs (all committed):
  research/brief4/input/alpine_8k_height_4x_2033.png + alpine_8k_height_4x.json
  recipes/water.json, research/brief4/input/hydro_amendment.json
  _verify/brief4/water_derive_2026-09-19/footprint_{A,B,D}_id*.npy
Output:
  water/alpine_8k_water_plan.json      (the plan the payload reads)
  _verify/brief4/water_placement_<date>/RESULT.md (evidence)
"""
import argparse
import datetime as _dt
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import hydro_derive as hd  # noqa: E402

BAND_ROWS = 16          # 64 m strips first; refined to 1 row where needed
FALL_WIDTH_M = 8.0
PLANE_MESH_CM = 100.0   # /Engine/BasicShapes/Plane is 100 cm across

# D8 neighbour order must match hydro_derive.d8_receivers
D8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def tight_bbox(mask):
    rr, cc = np.nonzero(mask)
    return int(cc.min()), int(rr.min()), int(cc.max()), int(rr.max())


def decompose(comp, safe):
    """Return list of (r0, r1, c0, c1) inclusive px rects; planes for comp.

    Every returned rect is all-safe. Rects never overlap (bands own rows,
    runs are disjoint columns). Cells missed by a BAND_ROWS band fall
    through to height-1 bands, which cannot miss: a single-row run over
    safe columns covers every safe component cell in that row, and every
    component cell is safe by construction (comp implies safe).
    """
    rects = []
    covered = np.zeros_like(comp, dtype=bool)
    c0b, r0b, c1b, r1b = tight_bbox(comp)

    def emit_band(r0, r1, target):
        # target: which cells this band must serve — comp on the first
        # pass, the uncovered residue on the fixup pass. Restricting the
        # fixup to residue columns keeps rects non-overlapping (coplanar
        # same-Z overlap would z-fight).
        sub_safe = safe[r0:r1 + 1, :].all(axis=0)
        sub_tgt = target[r0:r1 + 1, :].any(axis=0)
        cols = np.nonzero(sub_safe & sub_tgt)[0]
        if cols.size == 0:
            return
        breaks = np.nonzero(np.diff(cols) > 1)[0]
        starts = np.r_[cols[0], cols[breaks + 1]]
        ends = np.r_[cols[breaks], cols[-1]]
        for cs, ce in zip(starts, ends):
            rects.append((r0, r1, int(cs), int(ce)))
            covered[r0:r1 + 1, cs:ce + 1] = True

    r = r0b
    while r <= r1b:
        r_end = min(r + BAND_ROWS - 1, r1b)
        emit_band(r, r_end, comp)
        r = r_end + 1
    # anything missed: single-row bands over the residue only
    residue = comp & ~covered
    for row in np.nonzero(residue.any(axis=1))[0]:
        emit_band(int(row), int(row), comp & ~covered)
    return rects


def rect_world(rect, ox, oy, cell_m):
    """px rect (r0,r1,c0,c1) inclusive -> centre cm + scale for the plane."""
    r0, r1, c0, c1 = rect
    px_cm = cell_m * 100.0
    x0 = ox + (c0 - 0.5) * px_cm
    x1 = ox + (c1 + 0.5) * px_cm
    y0 = oy + (r0 - 0.5) * px_cm
    y1 = oy + (r1 + 0.5) * px_cm
    return ([0.5 * (x0 + x1), 0.5 * (y0 + y1)],
            [(x1 - x0) / PLANE_MESH_CM, (y1 - y0) / PLANE_MESH_CM])


def fall_yaw(h, lip_rc):
    """Yaw (deg) of the downhill D8 direction at the lip, UE convention:
    yaw 0 = +X, 90 = +Y. col -> +X, row -> +Y (the world() mapping)."""
    r, c = lip_rc
    best, vec = None, None
    for dr, dc in D8:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h.shape[0] and 0 <= cc < h.shape[1]:
            d = h[r, c] - h[rr, cc]
            if best is None or d > best:
                best, vec = d, (dc, dr)  # (dx, dy)
    return float(np.degrees(np.arctan2(vec[1], vec[0])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-plan", default=os.path.join(REPO, "water", "alpine_8k_water_plan.json"))
    ap.add_argument("--evidence", default=None)
    a = ap.parse_args()
    date = _dt.date.today().isoformat()
    ev_dir = a.evidence or os.path.join(REPO, "_verify", "brief4",
                                        "water_placement_%s" % date)
    os.makedirs(ev_dir, exist_ok=True)
    os.makedirs(os.path.dirname(a.out_plan), exist_ok=True)

    side = json.load(open(os.path.join(REPO, "research/brief4/input/alpine_8k_height_4x.json")))
    cell = float(side["image"]["metres_per_pixel"])
    mpu = float(side["z_mapping"]["metres_per_16bit_unit"])
    z0 = float(side["z_mapping"]["height_m_of_unit_0"])
    ox, oy = [float(v) for v in side["world_origin"]["landscape_location_cm"][:2]]
    h = np.array(Image.open(os.path.join(
        REPO, "research/brief4/input/alpine_8k_height_4x_2033.png"))).astype(np.float64) * mpu + z0

    water = json.load(open(os.path.join(REPO, "recipes/water.json"), encoding="utf-8"))
    hydro_am = json.load(open(os.path.join(REPO, "research/brief4/input/hydro_amendment.json"),
                              encoding="utf-8"))

    hf = hd.fill_sinks(h)
    _L, lab, _depth = hd.lakes(h, hf, cell, 2.0, 4000.0)

    surfaces = []   # (key, lake_id, level_m, role)
    for lk in water["lakes"]:
        surfaces.append((lk["name"], lk["id"], float(lk["level_m"]), "lake"))
    pool_ids = list(water["north_cascade"]["pool_ids"])
    ladder = {p["pool"]: float(p["surface_m"])
              for p in hydro_am["south_river_ladder"]["ladder_downstream_first"]}
    for pid in pool_ids:
        if pid == 8377:
            continue  # lake D IS pool 8377; already placed at the RULED 590.9
        if pid not in ladder:
            raise SystemExit("REFUSE: cascade pool %d has no ladder surface" % pid)
        surfaces.append(("cascade_pool_%d" % pid, pid, ladder[pid], "cascade_pool"))

    saved = {4893: "footprint_A_id4893.npy", 11877: "footprint_B_id11877.npy",
             8377: "footprint_D_id8377.npy"}
    plan_surfaces, report = [], []
    for key, lake_id, level_m, role in surfaces:
        sl = hd.level_slice(lab, h, lake_id, level_m, cell)
        if sl is None:
            raise SystemExit("REFUSE: level_slice None for %s (id %d @ %.2f m)"
                             % (key, lake_id, level_m))
        comp = sl["mask"]
        if lake_id in saved:
            ref = np.load(os.path.join(REPO, "_verify/brief4/water_derive_2026-09-19",
                                       saved[lake_id])).astype(bool)
            if not np.array_equal(ref, comp):
                raise SystemExit("REFUSE: recomputed component for id %d differs "
                                 "from the saved 2026-09-19 mask (%d vs %d px)"
                                 % (lake_id, comp.sum(), ref.sum()))
        safe = comp | (h >= level_m)
        c0, r0, c1, r1 = tight_bbox(comp)
        bbox_all_safe = bool(safe[r0:r1 + 1, c0:c1 + 1].all())
        wet_rect = int(((h < level_m)[r0:r1 + 1, c0:c1 + 1]).sum())
        stray_rect = wet_rect - int(comp.sum())
        if bbox_all_safe:
            rects = [(r0, r1, c0, c1)]
        else:
            rects = decompose(comp, safe)
        # rule-13 read-backs on the synthesized placement
        cover = np.zeros_like(comp, dtype=bool)
        stray_px = 0
        for (rr0, rr1, cc0, cc1) in rects:
            cover[rr0:rr1 + 1, cc0:cc1 + 1] = True
            stray_px += int((~safe[rr0:rr1 + 1, cc0:cc1 + 1]).sum())
        uncovered = int((comp & ~cover).sum())
        if uncovered or stray_px:
            raise SystemExit("REFUSE %s: uncovered=%d stray=%d (must both be 0)"
                             % (key, uncovered, stray_px))
        planes = []
        for i, rect in enumerate(rects):
            centre, scale = rect_world(rect, ox, oy, cell)
            planes.append({"label": "Water_%s_%02d" % (key, i),
                           "cx": centre[0], "cy": centre[1],
                           "cz": level_m * 100.0,
                           "sx": scale[0], "sy": scale[1],
                           "yaw": 0.0, "pitch": 0.0, "vertical": False})
        plan_surfaces.append({"key": key, "lake_id": lake_id, "level_m": level_m,
                              "role": role, "area_ha": sl["area_ha"],
                              "component_px": int(comp.sum()),
                              "bbox_col_row": [c0, r0, c1, r1],
                              "single_plane": bbox_all_safe,
                              "plane_count": len(planes), "planes": planes})
        report.append("%-22s id %-6d @ %8.2f m  comp %6d px  %s  planes %3d  "
                      "bbox-stray %5d px" % (key, lake_id, level_m, comp.sum(),
                                             "BBOX " if bbox_all_safe else "STRIP",
                                             len(planes), max(stray_rect, 0)))

    # ---- falls -----------------------------------------------------------
    north = [p for p in hydro_am["south_river_ladder"]["pools_over_2m"]
             if p["fill_lake_id"] in pool_ids]
    if len(north) != 10:
        raise SystemExit("REFUSE: expected 10 by-construction cascade lips, got %d"
                         % len(north))
    drops = {p["pool"]: float(p["drop_to_downstream_m"])
             for p in hydro_am["south_river_ladder"]["ladder_downstream_first"]}
    falls = []
    for p in north:
        c, r = p["lip_col_row"]
        drop = drops.get(p["fill_lake_id"])
        if drop is None or drop <= 0:
            raise SystemExit("REFUSE: no positive drop for cascade lip of pool %d"
                             % p["fill_lake_id"])
        top_m = float(p["outlet_level_m"])
        # pitch -90 about Y: local +Z (the face normal) -> +X, then yaw
        # turns +X onto the downhill heading, so the SINGLE rendered face
        # (M_SideWater two_sided False) looks DOWNSTREAM. Local X becomes
        # the vertical span -> drop rides sx; width rides sy. (Audit F1.)
        falls.append({"label": "Fall_cascade_%d" % p["fill_lake_id"],
                      "cx": ox + c * cell * 100.0, "cy": oy + r * cell * 100.0,
                      "cz": (top_m - drop / 2.0) * 100.0,
                      "sx": drop * 100.0 / PLANE_MESH_CM,
                      "sy": FALL_WIDTH_M * 100.0 / PLANE_MESH_CM,
                      "yaw": fall_yaw(h, (r, c)), "pitch": -90.0, "vertical": True,
                      "drop_m": drop, "lip_col_row": [int(c), int(r)]})
    a_fall = water["waterfalls"]["by_coupling_inflow"]["A_4893"]
    c, r = a_fall["col_row"]
    drop = float(a_fall["drop_m"])
    top_m = float(h[r, c])
    falls.append({"label": "Fall_inflow_A", "cx": float(a_fall["world_cm"][0]),
                  "cy": float(a_fall["world_cm"][1]),
                  "cz": (top_m - drop / 2.0) * 100.0,
                  "sx": drop * 100.0 / PLANE_MESH_CM,
                  "sy": FALL_WIDTH_M * 100.0 / PLANE_MESH_CM,
                  "yaw": fall_yaw(h, (r, c)), "pitch": -90.0, "vertical": True,
                  "drop_m": drop, "lip_col_row": [int(c), int(r)]})
    if len(falls) != int(water["waterfalls"]["total_placed_falls"]):
        raise SystemExit("REFUSE: %d falls synthesized, water.json says %d"
                         % (len(falls), water["waterfalls"]["total_placed_falls"]))

    plan = {"_what": "Brief-4 T5b water placement plan — planes clipped to "
                     "connected components (recipes/water.json), falls as "
                     "vertical placeholders. DERIVED by "
                     "research/brief4/scripts/water_placement_derive.py; "
                     "consumed by scripts/payloads/spawn_water_set.py.",
            "date": date, "cell_m": cell,
            "z_rule": "world_cm = level_m * 100 (water.json _placement)",
            "mesh": water["mesh"], "material": water["material"],
            "surfaces": plan_surfaces, "falls": falls,
            "totals": {"surface_planes": sum(s["plane_count"] for s in plan_surfaces),
                       "fall_planes": len(falls),
                       "surfaces": len(plan_surfaces)}}
    with open(a.out_plan, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(ev_dir, "RESULT.md"), "w", encoding="utf-8") as f:
        f.write("# water_placement_derive %s\n\n" % date)
        f.write("plan: %s\n\n```\n" % os.path.relpath(a.out_plan, REPO))
        f.write("\n".join(report))
        f.write("\nfalls: %d (10 cascade + 1 A inflow)\n" % len(falls))
        f.write("total planes: %d surface + %d fall\n"
                % (plan["totals"]["surface_planes"], len(falls)))
        f.write("```\n\nCoverage and stray both asserted ZERO per surface "
                "(REFUSE otherwise); A/B/D components byte-equal to the "
                "2026-09-19 saved masks.\n")
    print("\n".join(report))
    print("falls %d | surface planes %d | plan -> %s"
          % (len(falls), plan["totals"]["surface_planes"], a.out_plan))


if __name__ == "__main__":
    main()
