#!/usr/bin/env python3
"""water_derive.py -- Brief-4 CARVE derivations shared by T2 (inflow falls) and
T8 (encounters-in-water).

Reuses research/brief4/scripts/hydro_derive.py (the tool of record) rather than
re-implementing the flood/flow machinery (NN24: one derivation). Produces, for the
FIXED water set (RULING §7):

  * connected-component footprint masks for A@180 (id 4893), B@140 (id 11877),
    D@590.9 (id 8377) -- the CLIP the T0 finding requires (bbox over-floods),
  * a positive control: footprint areas must reproduce the hydro figures
    (A 125.5, B 13.6, D 49.6 ha) to 0.1 ha,
  * inflow-fall candidates for A and B by the RULING §3 coupling + MANDATORY
    elevation test: a waterfall candidate (research/brief4/input/hydro.json
    `waterfalls`, 78) qualifies if (a) it lies within `--near-m` of the lake's
    connected-component footprint, (b) its elevation is ABOVE the adopted water
    surface, and (c) its steepest-descent flow path reaches the footprint within
    `--trace-steps` (it actually drains INTO the lake). The POSITIVE CONTROL is
    the footprint-area reproduction above; the method's DISCRIMINATION shows in
    A (candidates drain in) vs B (endorheic: the draft's (696,1493) candidate is
    a south-river point and the drains-into test REJECTS it, so B has no separate
    inflow fall -- its inflow is the north-cascade terminus).

Masks are saved for T8 to test the 317 encounters against without re-deriving.

Usage:
  python water_derive.py --png <4x.png> --json <sidecar.json> \
      --hydro <hydro.json> --out <dir>
Everything is deterministic; no editor, no network.
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hydro_derive as hd  # tool of record; reused, not reimplemented

# The three carved lakes (RULING §7). C (6587) is DEFERRED -> not derived here.
LAKES = [
    dict(key="A", name="A_east_basin", id=4893, level_m=180.0, area_ha=125.5, inflow=True),
    dict(key="B", name="B_town_tarn", id=11877, level_m=140.0, area_ha=13.6, inflow=True),
    dict(key="D", name="D_headwater", id=8377, level_m=590.9, area_ha=49.6, inflow=False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--hydro", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--near-m", type=float, default=500.0,
                    help="inflow candidate must lie within this of the footprint")
    ap.add_argument("--trace-steps", type=int, default=400,
                    help="max steepest-descent steps to prove a candidate drains into the lake")
    ap.add_argument("--elev-margin-m", type=float, default=0.0,
                    help="candidate elevation must exceed level_m by this")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    side = json.load(open(a.json))
    cell = side["image"]["metres_per_pixel"]
    mpu = side["z_mapping"]["metres_per_16bit_unit"]
    z0 = side["z_mapping"]["height_m_of_unit_0"]
    from PIL import Image
    h = np.array(Image.open(a.png)).astype(np.float64) * mpu + z0
    ox, oy, oz = side["world_origin"]["landscape_location_cm"][:3]

    def world(col, row):
        return [ox + col * cell * 100, oy + row * cell * 100]

    hf = hd.fill_sinks(h)
    _L, lab, _depth = hd.lakes(h, hf, cell, 2.0, 4000.0)
    rec, _hr = hd.receivers_and_order(hf, cell)
    m = h.shape[1]

    hydro = json.load(open(a.hydro))
    wf = hydro["waterfalls"]

    near_cells = a.near_m / cell
    result = {"_what": "Brief-4 water-set footprints + A/B inflow falls (RULING §7)",
              "cell_m": cell, "near_m": a.near_m, "trace_steps": a.trace_steps,
              "z_mapping": {"metres_per_16bit_unit": mpu, "height_m_of_unit_0": z0,
                            "world_origin_cm": [ox, oy, oz]},
              "lakes": []}
    control_ok = True

    from scipy import ndimage as ndi
    for lk in LAKES:
        sl = hd.level_slice(lab, h, lk["id"], lk["level_m"], cell)
        if sl is None:
            result["lakes"].append({**lk, "error": "level_slice returned None"})
            control_ok = False
            continue
        mask = sl["mask"]
        area_ha = sl["area_ha"]
        # positive control vs the hydro figure (level_slice rounds area to 0.1 ha,
        # so 0.1 is the tightest tolerance that is not rounding-flaky; the control
        # exists to catch GROSS errors -- wrong lake/level move area by whole ha)
        control_pass = abs(area_ha - lk["area_ha"]) <= 0.1
        control_ok = control_ok and control_pass
        np.save(os.path.join(a.out, "footprint_%s_id%d.npy" % (lk["key"], lk["id"])),
                mask.astype(np.uint8))
        # distance (in cells) from every cell to the footprint, for the near test
        dist_cells = ndi.distance_transform_edt(~mask)

        entry = {**{k: lk[k] for k in ("key", "name", "id", "level_m")},
                 "area_ha_derived": area_ha, "area_ha_hydro": lk["area_ha"],
                 "control_pass": bool(control_pass),
                 "max_depth_m": sl["max_depth_m"], "shoreline_km": sl["shoreline_km"],
                 "centroid_col_row": sl["centroid_col_row"], "bbox_col_row": sl["bbox_col_row"],
                 "footprint_cells": int(mask.sum())}

        if lk["inflow"]:
            cands = []
            for w in wf:
                c, r = w["col_row"]
                if dist_cells[r, c] > near_cells:
                    continue
                if w["elevation_m"] <= lk["level_m"] + a.elev_margin_m:
                    continue
                # does it drain INTO the lake? trace steepest descent from the candidate
                j = r * m + c
                reaches = False
                for _ in range(a.trace_steps):
                    if mask.ravel()[j]:
                        reaches = True
                        break
                    nj = rec[j]
                    if nj < 0:
                        break
                    j = int(nj)
                cands.append({
                    "col_row": [c, r], "drop_m": round(w["drop_m"], 1),
                    "elevation_m": round(w["elevation_m"], 1),
                    "contributing_km2": round(w["contributing_km2"], 3),
                    "dist_to_shore_m": round(float(dist_cells[r, c]) * cell, 1),
                    "world_cm": world(c, r),
                    "drains_into_lake": reaches})
            # keep only candidates that actually drain in; rank by drop (readability)
            drain = [x for x in cands if x["drains_into_lake"]]
            drain.sort(key=lambda x: -x["drop_m"])
            entry["inflow_candidates_considered"] = len(cands)
            entry["inflow_candidates_draining"] = len(drain)
            entry["inflow_candidates"] = drain
            entry["inflow_fall_pick"] = drain[0] if drain else None
        result["lakes"].append(entry)

    result["positive_control_pass"] = bool(control_ok)
    json.dump(result, open(os.path.join(a.out, "water_derive.json"), "w"), indent=1)

    # human summary
    print("positive control (footprint area vs hydro, <=0.1 ha):",
          "PASS" if control_ok else "FAIL")
    for e in result["lakes"]:
        if "error" in e:
            print("  %s id%d: ERROR %s" % (e.get("key"), e.get("id"), e["error"]))
            continue
        print("  %s id%d @ %.1f m: derived %.1f ha vs hydro %.1f ha  %s"
              % (e["key"], e["id"], e["level_m"], e["area_ha_derived"],
                 e["area_ha_hydro"], "OK" if e["control_pass"] else "MISMATCH"))
        if "inflow_fall_pick" in e:
            print("     inflow: %d near+high, %d drain-in; pick=%s"
                  % (e["inflow_candidates_considered"], e["inflow_candidates_draining"],
                     e["inflow_fall_pick"]))
    print("wrote", os.path.join(a.out, "water_derive.json"))


if __name__ == "__main__":
    main()
