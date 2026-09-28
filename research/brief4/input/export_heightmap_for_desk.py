"""export_heightmap_for_desk.py — a 4x heightmap and its frame, for Brief 4.

    python scripts/export_heightmap_for_desk.py --selftest
    python scripts/export_heightmap_for_desk.py --out research/brief4/input

Writes a 16-bit PNG downsampled 4x and a JSON sidecar carrying
everything needed to put a pixel back in the world: the Z mapping, the
ORIENTATION that was proven against the engine, the world origin, and
the town and Bench_ground in the SAME pixel coordinates as the image.

⭐ AREA-AVERAGE, CENTRED, NOT NEAREST. Output vertex i corresponds
EXACTLY to input vertex 4i, and the average is taken over an ODD 5x5
window centred on it. An even 4x4 window would centre on 4i-0.5 and put
a HALF-PIXEL SHIFT between the image and every coordinate in the
sidecar -- which is precisely the error that would be impossible to see
from the far end and would quietly bias anything the desk derives.

⛔ THE GRID IS VERTEX-BASED. 8129 vertices span 8128 intervals, so the
4x grid is 2032 intervals = 2033 vertices. Downsampling to 8129/4 would
break the landscape's +1 convention.

WHAT IS NOT INVENTED HERE. The orientation is not re-derived: it is
copied from `_verify/bench/2026-09-11/orientation_vista.json`, which
tested four mappings against an ENGINE depth pass. The Z span is
MEASURED off the file, not taken from the recipe's encodable range --
the two are different numbers and the difference matters.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import sys

import numpy as np

def _find_repo(start):
    """Walk up to the repo root, identified by CLAUDE.md.

    This file lives beside the artefacts it produces rather than in
    `scripts/`, because the ruling that commissioned it allowed no repo
    changes outside `research/brief4/input/`. So the root cannot be
    assumed to be two levels up.
    """
    d = os.path.dirname(os.path.abspath(start))
    for _ in range(8):
        if os.path.exists(os.path.join(d, "CLAUDE.md")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    raise SystemExit("could not find the repo root above %s" % start)


REPO = _find_repo(__file__)
sys.path.insert(0, os.path.join(REPO, "scripts"))

RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
ORIENT = os.path.join(REPO, "_verify", "bench", "2026-09-11",
                      "orientation_vista.json")
CAMS = os.path.join(REPO, "_verify", "bench", "station_cameras.json")
FACTOR = 4


def downsample_centred(a, factor=FACTOR):
    """(N-1)/f + 1 vertices, each the mean of a centred odd window."""
    n = a.shape[0]
    if (n - 1) % factor:
        raise ValueError("%d vertices is not f*k+1 for f=%d" % (n, factor))
    out_n = (n - 1) // factor + 1
    r = factor // 2                      # 2 for factor 4
    pad = np.pad(a.astype(np.float64), r, mode="edge")
    win = 2 * r + 1                      # 5, ODD, centred on 4i
    out = np.empty((out_n, out_n), dtype=np.float64)
    for i in range(out_n):
        rows = pad[i * factor: i * factor + win, :]
        col_sum = rows.sum(axis=0)
        for j in range(out_n):
            out[i, j] = col_sum[j * factor: j * factor + win].sum()
    return out / float(win * win), out_n


def px_of_world(x_cm, y_cm, origin, scale_xy_cm, factor=FACTOR):
    """World cm -> DOWNSAMPLED pixel (col, row), orientation 'ours'."""
    col = (x_cm - origin[0]) / scale_xy_cm / factor
    row = (y_cm - origin[1]) / scale_xy_cm / factor
    return col, row


def build(out_dir):
    rec = json.load(io.open(RECIPE, encoding="utf-8"))
    hm, ls = rec["heightmap"], rec["landscape"]
    src_rel = hm["source"]
    src = os.path.join(REPO, src_rel)

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(src)
    if im.mode != "I;16":
        raise SystemExit("expected I;16, got %s" % im.mode)
    a = np.asarray(im)
    n = a.shape[0]

    origin = [float(v) for v in ls["location_cm"]]
    scale_xy = float(ls["scale_xy_cm"])
    z_scale_cm = float(ls["z_scale_cm"])

    # ---- Z MAPPING. UE places the landscape's Z CENTRE at location_cm[2]
    # and spans z_scale_cm across the full 16-bit range, so unit 32768 is
    # the centre. Stated as an affine map AND as measured min/max, because
    # the ENCODABLE span and the span the DATA uses are different numbers.
    half_cm = z_scale_cm / 2.0
    m_per_unit = (z_scale_cm / 65535.0) / 100.0
    z0_m = (origin[2] - half_cm) / 100.0          # height of unit 0
    lo_u, hi_u = int(a.min()), int(a.max())
    lo_m = z0_m + lo_u * m_per_unit
    hi_m = z0_m + hi_u * m_per_unit

    small, out_n = downsample_centred(a, FACTOR)
    small_u16 = np.clip(np.rint(small), 0, 65535).astype(np.uint16)

    os.makedirs(out_dir, exist_ok=True)
    png_name = "alpine_8k_height_4x_%d.png" % out_n
    png_path = os.path.join(out_dir, png_name)
    Image.fromarray(small_u16, mode="I;16").save(png_path)

    orient = json.load(io.open(ORIENT, encoding="utf-8"))["result"]
    best = max(orient["rows"], key=lambda r: r["iou"])

    # ---- town footprint, in the SAME pixel coordinates -----------------
    import town_exclusion
    plan_rel = rec["foliage"]["settlement_exclusion"]["from_city_plan"]
    shapes, plaza, margins = town_exclusion.load(
        os.path.join(REPO, plan_rel))
    xs, ys = [], []
    for cx, cy, yaw, hx, hy in shapes:
        rr = math.hypot(hx, hy)          # conservative: rotation-agnostic
        xs += [cx - rr, cx + rr]
        ys += [cy - rr, cy + rr]
    bb = {
        "min_col_row": list(px_of_world(min(xs), min(ys), origin, scale_xy)),
        "max_col_row": list(px_of_world(max(xs), max(ys), origin, scale_xy)),
    }
    bb["min_col_row"] = [round(v, 3) for v in bb["min_col_row"]]
    bb["max_col_row"] = [round(v, 3) for v in bb["max_col_row"]]
    plaza_px = None
    if plaza:
        pc, pr = px_of_world(plaza[0], plaza[1], origin, scale_xy), None
        plaza_px = {
            "centre_col_row": [round(pc[0], 3), round(pc[1], 3)],
            "radius_px": round(math.sqrt(plaza[2]) / scale_xy / FACTOR, 3),
            "radius_m": round(math.sqrt(plaza[2]) / 100.0, 2),
        }

    cams = json.load(io.open(CAMS, encoding="utf-8"))["cameras"]
    stations = {}
    for name in ("ground", "near_ground", "mid_slope", "vista"):
        if name not in cams:
            continue
        loc = cams[name]["loc_cm"]
        c, r = px_of_world(loc[0], loc[1], origin, scale_xy)
        stations[name] = {
            "loc_cm": loc,
            "col_row": [round(c, 3), round(r, 3)],
            "forward": cams[name]["forward"],
            "fov_deg": cams[name].get("fov_deg"),
        }

    side = {
        "_what": ("Alpine8K heightmap downsampled 4x, with the frame "
                  "needed to put a pixel back in the world."),
        "_generated_by": os.path.relpath(
            os.path.abspath(__file__), REPO).replace("\\", "/"),
        "source": {
            "path": src_rel,
            "resolution": [int(n), int(n)],
            "mode": "I;16",
            "sha256": hashlib.sha256(
                io.open(src, "rb").read()).hexdigest(),
        },
        "image": {
            "path": png_name,
            "resolution": [int(out_n), int(out_n)],
            "mode": "I;16",
            "downsample_factor": FACTOR,
            "method": ("area average over a CENTRED %dx%d window; output "
                       "vertex i is exactly input vertex %d*i, so there is "
                       "NO half-pixel shift against the coordinates below"
                       % (2 * (FACTOR // 2) + 1, 2 * (FACTOR // 2) + 1,
                          FACTOR)),
            "metres_per_pixel": scale_xy / 100.0 * FACTOR,
            "_vertex_grid": ("%d vertices span %d intervals; 4x gives %d "
                             "intervals = %d vertices"
                             % (n, n - 1, (n - 1) // FACTOR, out_n)),
            "edge_caveat": ("The FIRST and LAST row and column are "
                            "slightly biased inward: a centred window "
                            "cannot stay symmetric at a boundary, so "
                            "those vertices average replicate-padded "
                            "samples. On a unit ramp the bias is 0.6 of "
                            "one input sample. The interior is exact -- a "
                            "linear field reproduces to 1e-9. Treat the "
                            "1-px border as soft."),
        },
        "z_mapping": {
            "metres_per_16bit_unit": round(m_per_unit, 9),
            "height_m_of_unit_0": round(z0_m, 6),
            "formula": "height_m = height_m_of_unit_0 + unit * metres_per_16bit_unit",
            "encodable_span_m": [round(z0_m, 3),
                                 round(z0_m + 65535 * m_per_unit, 3)],
            "measured_units": [lo_u, hi_u],
            "measured_span_m": [round(lo_m, 3), round(hi_m, 3)],
            "_encodable_is_not_measured": (
                "the ENCODABLE span is what 16 bits can address at this "
                "z_scale; the MEASURED span is what this terrain actually "
                "uses. Use the measured one for anything about this "
                "landscape."),
            "z_scale_cm": z_scale_cm,
            "landscape_location_cm": origin,
            "world_z_cm": "height_m * 100",
            "⛔_do_not_add_landscape_location_z": (
                "world_z_cm = height_m * 100. The landscape actor's "
                "location z is NOT added -- it is already spent. UE stores "
                "landscape height as a SIGNED 16-bit value about midpoint "
                "32768, and this landscape's location z (%.1f cm) is "
                "EXACTLY 32768 * (z_scale_cm / 65536) = %.2f cm, i.e. the "
                "midpoint offset itself. Adding it again double-counts. "
                "Measured, not argued: on world_z = height_m*100 all four "
                "station cameras sit +1.66 to +2.17 m above the terrain at "
                "the pixel this sidecar names (eye height, four "
                "independent stations); on the additive formula every one "
                "of them sits 1278 m UNDERGROUND."
                % (origin[2], 32768.0 * (z_scale_cm / 65536.0))),
            "_divisor_note": (
                "metres_per_16bit_unit above is z_scale_cm/65535/100. The "
                "engine's own divisor is 65536 -- which is what makes the "
                "midpoint land on %.2f cm EXACTLY rather than %.2f cm -- "
                "giving 0.0390625 m/unit. The two differ by %.4f m over "
                "the measured span, below anything downstream resolves, so "
                "the shipped value is left as-is to stay in step with "
                "hydro.json, which was derived from it."
                % (32768.0 * (z_scale_cm / 65536.0),
                   32768.0 * (z_scale_cm / 65535.0),
                   hi_u * abs(m_per_unit - z_scale_cm / 65536.0 / 100.0))),
        },
        "orientation": {
            "mapping": best["mapping"],
            "world_x_cm": "origin_cm[0] + col * metres_per_pixel * 100",
            "world_y_cm": "origin_cm[1] + row * metres_per_pixel * 100",
            "established_by": "scripts/heightmap_orientation_check.py",
            "evidence": os.path.relpath(ORIENT, REPO).replace("\\", "/"),
            "iou_by_mapping": {r["mapping"]: r["iou"]
                               for r in orient["rows"]},
            "margin": orient["margin"],
            "required_margin": orient["required_margin"],
            "verdict": orient["verdict"],
            "_tested_against": ("an ENGINE depth pass at station %s, not "
                               "against another derivation of the same "
                               "heightmap" % orient["station"]),
        },
        "world_origin": {
            "landscape_location_cm": origin,
            "scale_xy_cm_per_vertex": scale_xy,
            "_pixel_0_0_is": ("the landscape's minimum-X, minimum-Y corner "
                              "vertex, at world (%.1f, %.1f) cm"
                              % (origin[0], origin[1])),
        },
        "town_footprint": {
            "from_city_plan": plan_rel,
            "oriented_rectangles": len(shapes),
            "bounding_box_col_row": bb,
            "plaza": plaza_px,
            "margins_m": {"building": margins[0], "street": margins[1],
                          "plaza": margins[2]},
            "_margins_are_included": ("the rectangles already carry the "
                                      "foliage-clearing margins from "
                                      "recipes/city.json"),
        },
        "stations": stations,
        "_station_note": ("Bench_ground is the surface-metrics station and "
                          "is deliberately NOT in the ratified "
                          "near_ground/mid_slope/vista comparison set."),
    }
    side_path = os.path.join(out_dir, "alpine_8k_height_4x.json")
    io.open(side_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(side, indent=1))
    return png_path, side_path, side


def selftest():
    """The downsample's alignment and conservation, with no repo state."""
    fails = []
    # 1 a linear ramp must survive exactly: a centred average of a linear
    #   field is the centre value, so ramp[4i] must come back.
    n = 33
    ramp = np.tile(np.arange(n, dtype=np.float64), (n, 1))
    out, on = downsample_centred(ramp, 4)
    want = np.arange(0, n, 4, dtype=np.float64)
    # INTERIOR exactness is the alignment test. A centred average of a
    # linear field returns the centre sample, so any half-pixel shift
    # shows up here immediately.
    inner = slice(1, on - 1)
    err = float(np.abs(out[0, inner] - want[inner]).max())
    print("  linear ramp, INTERIOR  -> max err %.3e over %d px  %s"
          % (err, on - 2, "OK" if err < 1e-9 else "WRONG"))
    if err >= 1e-9:
        fails.append("a centred average shifted a linear ramp (half-pixel)")
    # ⛔ THE EDGE IS BIASED AND THAT IS INHERENT. A centred window cannot
    # stay symmetric at a boundary, so the first and last vertices pull
    # inward: on a unit ramp, vertex 0 reads 0.6 instead of 0. Replicate
    # padding is the least-wrong choice (truncating to valid samples
    # would read 1.0). MEASURED and reported rather than asserted away --
    # the desk needs to know the border row and column are soft.
    edge = max(abs(float(out[0, 0]) - want[0]),
               abs(float(out[0, -1]) - want[-1]))
    print("  edge bias, unit ramp   -> %.3f sample(s) inward (inherent)"
          % edge)
    if edge > 1.0:
        fails.append("edge bias %.3f exceeds one sample" % edge)
    # 2 the vertex count follows the +1 convention
    print("  33 vertices -> %d      %s" % (on, "OK" if on == 9 else "WRONG"))
    if on != 9:
        fails.append("33 vertices did not give 9")
    # 3 a non-conforming size REFUSES
    try:
        downsample_centred(np.zeros((32, 32)), 4)
        print("  32 vertices            -> DID NOT REFUSE  WRONG")
        fails.append("a non f*k+1 size did not refuse")
    except ValueError:
        print("  32 vertices            -> refused         OK")
    # 4 a constant field is preserved exactly (no edge darkening)
    c, _ = downsample_centred(np.full((33, 33), 1234.0), 4)
    ok = abs(float(c.min()) - 1234.0) < 1e-9 and \
        abs(float(c.max()) - 1234.0) < 1e-9
    print("  constant field         -> min %.4f max %.4f  %s"
          % (c.min(), c.max(), "OK" if ok else "WRONG"))
    if not ok:
        fails.append("edge padding altered a constant field")
    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("research", "brief4",
                                                  "input"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    out_dir = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    png, side, doc = build(out_dir)
    print("wrote %s" % os.path.relpath(png, REPO))
    print("wrote %s" % os.path.relpath(side, REPO))
    print()
    print("  image      %s  %s m/px" % (doc["image"]["resolution"],
                                        doc["image"]["metres_per_pixel"]))
    print("  z measured %s m  (encodable %s)"
          % (doc["z_mapping"]["measured_span_m"],
             doc["z_mapping"]["encodable_span_m"]))
    print("  m per unit %.9f" % doc["z_mapping"]["metres_per_16bit_unit"])
    print("  orient     %s  (margin %.4f over %.4f, %s)"
          % (doc["orientation"]["mapping"], doc["orientation"]["margin"],
             doc["orientation"]["required_margin"],
             doc["orientation"]["verdict"]))
    print("  town bbox  %s .. %s"
          % (doc["town_footprint"]["bounding_box_col_row"]["min_col_row"],
             doc["town_footprint"]["bounding_box_col_row"]["max_col_row"]))
    for k, v in doc["stations"].items():
        print("  station    %-12s col,row %s" % (k, v["col_row"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
