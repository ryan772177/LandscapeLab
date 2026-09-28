#!/usr/bin/env python3
"""carve_water_notches.py -- Brief-4 CARVE_PLAN T3.

The ONLY heightmap cut of the Brief-4 water carve: the north-cascade pool-lip
notches. The lakes are fill-to-level of existing terrain (static water meshes at
the sec.7 levels) -- NO carve creates their depth. There is NO cut at the (913,1899)
town lip: tarn B is ENDORHEIC (RULING sec.7 #5), the Option II 17 m notch is struck.

Standing rule 4: this edits terrain/alpine_8k.png OFF-DISK through the pipeline,
never by editor sculpt. Rule 8: dry-run by default; --write is required to touch
the PNG, and the write asserts (a) no pixel is RAISED, (b) the changed set is a
subset of the declared notch discs, (c) 0 <= height <= 2560 m (the 16-bit span).

The notch geometry is REFERENCED, not duplicated: pool ids come from
recipes/water.json north_cascade.pool_ids; per-lip lip_col_row / surface_m /
notch_m / outlet_level_m come from research/brief4/input/hydro_amendment.json
pools_over_2m. The cut lowers each lip DISC to outlet_level_m (= surface_m -
notch_m) wherever the terrain there is currently higher -- a controlled
spillway, idempotent (min()), and a no-op where the terrain already drains.

Coordinate map: the hydro grid is the 4x downsample (2033 vertices, 4 m/cell);
the target PNG is 8129 vertices (1 m/vertex). The desk export records "output
vertex i is exactly input vertex 4*i, NO half-pixel shift", so a 2033 lip (c,r)
maps to the 8129 vertex (4c, 4r) exactly.

Usage:
  python carve_water_notches.py [--radius N] [--write]
      [--png terrain/alpine_8k.png] [--water recipes/water.json]
      [--hydro research/brief4/input/hydro_amendment.json]
      [--sidecar research/brief4/input/alpine_8k_height_4x.json]
Default is a DRY RUN (prints the per-lip plan + totals, writes nothing).
"""
import argparse, hashlib, io, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _load_json(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", default=os.path.join(REPO, "terrain", "alpine_8k.png"))
    ap.add_argument("--water", default=os.path.join(REPO, "recipes", "water.json"))
    ap.add_argument("--hydro", default=os.path.join(
        REPO, "research", "brief4", "input", "hydro_amendment.json"))
    ap.add_argument("--sidecar", default=os.path.join(
        REPO, "research", "brief4", "input", "alpine_8k_height_4x.json"))
    ap.add_argument("--radius", type=int, default=2,
                    help="notch disc radius in 8129-space pixels (a 2*R+1 square "
                         "masked to a disc). Default 2 -> ~5 m notch.")
    ap.add_argument("--expect-lips", type=int, default=10,
                    help="required number of north-cascade pool lips (RULING sec.7: "
                         "10). The run REFUSES if fewer resolve, so a truncated "
                         "pool_ids cannot silently cut a partial cascade.")
    ap.add_argument("--coord-tol-m", type=float, default=12.0,
                    help="max allowed |8129 terrain at the mapped lip - hydro "
                         "lip_elev_m| (an INDEPENDENT check of the 2033->8129 "
                         "coordinate map: lip_elev_m is not the field that drives "
                         "the cut, so a wrong map is caught, not masked).")
    ap.add_argument("--downsample", type=int, default=4,
                    help="8129 vertex = downsample * 2033 vertex (no half-pixel shift)")
    ap.add_argument("--write", action="store_true",
                    help="actually write the PNG (default: dry run)")
    a = ap.parse_args()

    water = _load_json(a.water)
    hydro = _load_json(a.hydro)
    side = _load_json(a.sidecar)
    mpu = float(side["z_mapping"]["metres_per_16bit_unit"])
    z0 = float(side["z_mapping"]["height_m_of_unit_0"])
    assert z0 == 0.0, "z0 != 0 not handled"
    ENC_MAX_M = 65535 * mpu + z0  # 2560.0 m

    pool_ids = set(water["north_cascade"]["pool_ids"])
    # per-lip notch parameters, keyed by fill_lake_id, from the tool of record
    lips = []
    for p in hydro["south_river_ladder"]["pools_over_2m"]:
        if p.get("fill_lake_id") in pool_ids:
            lips.append(p)
    got = {p["fill_lake_id"] for p in lips}
    missing = pool_ids - got
    if missing:
        print("ERROR: pool ids with no lip in hydro pools_over_2m: %s" % sorted(missing))
        return 2
    if len(pool_ids) != a.expect_lips or len(lips) != a.expect_lips:
        print("ERROR: expected %d north-cascade lips, resolved %d from %d pool_ids "
              "-- refusing (a partial cascade must not be cut silently)"
              % (a.expect_lips, len(lips), len(pool_ids)))
        return 2
    # guard: the endorheic town lip must NOT be in the cut set
    town_lip = tuple(hydro["town_basin_conflict"]["lip_col_row"])
    for p in lips:
        if tuple(p["lip_col_row"]) == town_lip:
            print("ERROR: the endorheic town lip %s is in the cut set -- forbidden"
                  % (town_lip,))
            return 2

    im = Image.open(a.png)
    assert im.mode == "I;16", "expected I;16, got %s" % im.mode
    arr = np.array(im).astype(np.uint16)
    n = arr.shape[0]
    orig = arr.copy()

    R = a.radius
    ds = a.downsample
    # build the declared notch-cell mask (union of discs) and the target floor
    notch_mask = np.zeros(arr.shape, bool)
    plan = []
    for p in sorted(lips, key=lambda q: -q["surface_m"]):
        c2033, r2033 = p["lip_col_row"]
        cx, cy = c2033 * ds, r2033 * ds
        outlet_m = float(p["outlet_level_m"])
        target_png = int(round(outlet_m / mpu))
        target_png = max(0, min(65535, target_png))
        # disc of radius R around (cy, cx), clipped to the grid
        r0, r1 = max(0, cy - R), min(n, cy + R + 1)
        c0, c1 = max(0, cx - R), min(n, cx + R + 1)
        yy, xx = np.ogrid[r0:r1, c0:c1]
        disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= R * R
        sub = arr[r0:r1, c0:c1]
        # lower to target where currently higher; never raise; clamp >=0 (already uint16)
        lower = disc & (sub > target_png)
        cells_here = int(lower.sum())
        cur_center_png = int(orig[cy, cx])
        cur_center_m = cur_center_png * mpu
        cut_here_m = max(0.0, cur_center_m - target_png * mpu)
        # INDEPENDENT coord-map check (NN rule 0): the 8129 terrain at the mapped
        # lip must agree with hydro's 2033-measured lip_elev_m. lip_elev_m does
        # NOT drive the cut (outlet_level_m does), so a wrong 2033->8129 map is
        # detected here rather than masked by a subset test that shares the map.
        lip_elev_m = float(p["lip_elev_m"])
        coord_err_m = abs(cur_center_m - lip_elev_m)
        if cells_here:
            sub[lower] = target_png
            arr[r0:r1, c0:c1] = sub
        notch_mask[r0:r1, c0:c1][disc] = True
        plan.append(dict(
            fill_lake_id=p["fill_lake_id"], lip_col_row_2033=[c2033, r2033],
            lip_col_row_8129=[cx, cy], surface_m=p["surface_m"],
            notch_m=p["notch_m"], outlet_level_m=round(outlet_m, 2),
            target_png=target_png, cur_center_m=round(cur_center_m, 2),
            lip_elev_m=round(lip_elev_m, 2), coord_err_m=round(coord_err_m, 2),
            center_cut_m=round(cut_here_m, 2), cells_lowered=cells_here))

    changed = orig != arr
    n_changed = int(changed.sum())
    subset_ok = bool((~notch_mask[changed]).sum() == 0) if n_changed else True
    raised = int((arr > orig).sum())
    new_max_m = float(arr.max()) * mpu
    new_min_m = float(arr.min()) * mpu
    max_coord_err = max((e["coord_err_m"] for e in plan), default=0.0)
    coord_ok = max_coord_err <= a.coord_tol_m

    print("=== CARVE PLAN (north-cascade pool-lip notches) ===")
    print("PNG %s  %dx%d %s  radius=%d px  mpu=%.9f" % (
        a.png, n, n, im.mode, R, mpu))
    print("pool lips: %d (from water.json north_cascade.pool_ids)" % len(plan))
    print("%-6s %-16s %-16s %8s %8s %8s %8s %7s" % (
        "lakeid", "lip_2033", "lip_8129", "surf_m", "outlet_m", "coorderr", "cut_m", "cells"))
    for e in plan:
        print("%-6d %-16s %-16s %8.2f %8.2f %8.2f %8.2f %7d" % (
            e["fill_lake_id"], e["lip_col_row_2033"], e["lip_col_row_8129"],
            e["surface_m"], e["outlet_level_m"], e["coord_err_m"],
            e["center_cut_m"], e["cells_lowered"]))
    total_cut = sum(e["center_cut_m"] for e in plan)
    print("--")
    print("changed pixels: %d   declared notch cells: %d   subset(changed<=notch): %s"
          % (n_changed, int(notch_mask.sum()), subset_ok))
    print("pixels RAISED (must be 0): %d" % raised)
    print("coord-map check: max|8129 terrain - hydro lip_elev| = %.2f m  (tol %.1f m) -> %s"
          % (max_coord_err, a.coord_tol_m, "OK" if coord_ok else "FAIL"))
    print("z-span after: min %.3f m  max %.3f m  (encodable 0..%.1f m)"
          % (new_min_m, new_max_m, ENC_MAX_M))
    print("sum of center cuts: %.2f m" % total_cut)

    ok = (coord_ok and n_changed > 0 and subset_ok and raised == 0
          and new_min_m >= 0.0 and new_max_m <= ENC_MAX_M + 1e-6
          and len(plan) == a.expect_lips)
    reasons = []
    if not coord_ok: reasons.append("coord-map err %.2f>%.1f" % (max_coord_err, a.coord_tol_m))
    if n_changed == 0: reasons.append("zero changed pixels (nothing to cut -- rule 13)")
    if not subset_ok: reasons.append("changed pixels outside declared notch cells")
    if raised: reasons.append("%d pixels raised" % raised)
    if new_min_m < 0.0 or new_max_m > ENC_MAX_M + 1e-6: reasons.append("z-span out of encodable range")
    if len(plan) != a.expect_lips: reasons.append("lip count %d != %d" % (len(plan), a.expect_lips))

    if not a.write:
        print("\nDRY RUN -- nothing written. re-run with --write to apply.")
        print("guardrails %s%s" % ("PASS" if ok else "FAIL",
                                    "" if ok else "  (%s)" % "; ".join(reasons)))
        return 0 if ok else 1

    if not ok:
        print("\nREFUSING to write: %s" % "; ".join(reasons))
        return 1

    sha_before = _sha256(a.png)
    # atomic write: encode to a temp file, then os.replace -- an interrupted
    # save cannot leave a half-written 104 MB PNG in place.
    out = Image.fromarray(arr.astype(np.uint16))   # 2D uint16 -> mode inferred
    if out.mode != "I;16":
        print("\nREFUSING to write: fromarray produced mode %r, not I;16" % out.mode)
        return 1
    tmp = a.png + ".carve.tmp"
    out.save(tmp, format="PNG")
    # VERIFY THE TEMP before it replaces the good file: a corrupt encode must
    # never overwrite the original (which is only restorable via the LFS tag).
    tchk = Image.open(tmp)
    tchk_arr = np.array(tchk).astype(np.uint16)
    if not (tchk.mode == "I;16" and tchk_arr.shape == arr.shape
            and np.array_equal(tchk_arr, arr)):
        tchk.close()
        os.remove(tmp)  # our own scratch temp, not the tracked artefact
        print("\nREFUSING to replace: temp round-trip mismatch (mode %r) -- "
              "original untouched" % tchk.mode)
        return 1
    tchk.close()
    os.replace(tmp, a.png)
    sha_after = _sha256(a.png)
    # read back from disk as an INDEPENDENT re-open (rule 12)
    rb = Image.open(a.png)
    rb_arr = np.array(rb).astype(np.uint16)
    rb_ok = (rb.mode == "I;16" and rb_arr.shape == arr.shape
             and np.array_equal(rb_arr, arr))
    rb_changed = int((rb_arr != orig).sum())
    print("\nWROTE %s" % a.png)
    print("sha256 before %s" % sha_before)
    print("sha256 after  %s   bytes-changed=%s" % (sha_after, sha_before != sha_after))
    print("read-back mode %s  identical-to-written %s  changed-vs-orig %d (want %d)"
          % (rb.mode, rb_ok, rb_changed, n_changed))
    write_ok = rb_ok and rb_changed == n_changed
    print("WRITE %s" % ("OK" if write_ok else "FAILED"))
    return 0 if write_ok else 1


if __name__ == "__main__":
    sys.exit(main())
