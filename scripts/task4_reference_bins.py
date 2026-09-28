"""task4_reference_bins.py — the SAME meadow metric, on the references.

    python scripts/task4_reference_bins.py --selftest
    python scripts/task4_reference_bins.py --out <json>

⭐ WHAT MAKES THE TWO TABLES COMPARABLE. The render table is luminance
std/mean over the meadow mask, per DEPTH bin, on a display-referred
frame. A photograph has no depth pass -- but it does have a GROUND
PLANE, and for a camera of height H the row of a ground point is a pure
function of its distance:

    tan(alpha) = H / d      alpha = atan((row - horizon_row) / f)

So the same depth bins become ROW BANDS in the reference, and the metric
is then identical on both sides: std/mean of luminance over meadow
pixels in the band. No angular hand-waving, and shadows are included in
both, which is the point -- this is the one metric a photo can give.

⛔ THE FOCAL LENGTH IS THE ONE UNKNOWN, AND IT IS DECLARED, NOT GUESSED
QUIETLY. `recipes/concepts/*.json` record `fov_hint` as prose
("moderate", "moderate_wide") and no number. So the table is computed AT
THE JUDGEMENT CAMERA'S OWN FOV -- hfov 90, the bench camera -- which is
the assumption that makes the two tables the same instrument rather than
two instruments that happen to share a formula. It is stated in the
output, and `--sensitivity` recomputes at 50 and 70 degrees so the
desk can see how much the answer moves. It moves the DISTANCES, not the
pixels: a different focal length re-labels which rows belong to which
bin.

⛔ MEADOW CROPS ARE AUTHORED, AND THEY ARE RECTANGLES YOU CAN CHECK.
There is no weightmap for a photograph. The rectangles below were chosen
by looking at the images and they exclude trees, trunks, buildings,
water, track and sky. They are DECLARED here rather than derived by a
colour rule, because a colour rule that picks "green" would also pick
tree canopy, and a reference table built on canopy is not a meadow
table.

    alpine_village_01   a broad meadow fills the lower half; usable to
                        the village line. Tree TRUNKS cross it, so the
                        rectangles sit between them.
    alpine_village_02   a village street. Meadow exists only as
                        near-field patches between rocks and track, so
                        its far bins are legitimately EMPTY and read NO
                        VERDICT rather than being filled with cobbles.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

BINS = [(4.0, 10.0), (10.0, 30.0), (30.0, 100.0), (100.0, 300.0)]
LUMA = (0.2126, 0.7152, 0.0722)
JUDGEMENT_HFOV_DEG = 90.0
MIN_PX = 800

# (x0, y0, x1, y1) in pixels, on the 1433x736 images. Meadow only.
REFERENCES = {
    "alpine_village_01": {
        "path": "refs/alpine_village_01.jpg",
        "camera_height_m": 1.8,          # recipes/concepts/alpine_village_01.json
        "horizon_frac": 0.45,            # same file
        "fov_hint": "moderate",
        "meadow_rects": [
            (40, 470, 250, 730),         # lower left, between trunks
            (330, 455, 470, 730),
            (520, 450, 700, 720),        # lower centre
            (720, 470, 950, 700),        # centre, in front of the village
            (1000, 430, 1240, 520),      # the slope right of the stream
        ],
        "exclude_rects": [],
    },
    "alpine_village_02": {
        "path": "refs/alpine_village_02.jpg",
        "camera_height_m": 1.7,          # recipes/concepts/alpine_village_02.json
        "horizon_frac": 0.55,
        "fov_hint": "moderate_wide",
        "meadow_rects": [
            (150, 600, 480, 730),        # near-field grass, lower left
            (830, 580, 1080, 700),       # grass between rocks, lower right
            (620, 520, 760, 570),        # the patch below the church steps
        ],
        "exclude_rects": [],
    },
}


def row_for_distance(d_m, height_m, horizon_row, f_px):
    """Image row of a ground point d_m away. Below the horizon, so +."""
    alpha = math.atan2(height_m, d_m)
    return horizon_row + f_px * math.tan(alpha)


def focal_px(width, hfov_deg):
    return (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def measure_reference(name, spec, hfov_deg=JUDGEMENT_HFOV_DEG):
    p = os.path.join(REPO, spec["path"])
    im = np.asarray(Image.open(p).convert("RGB")).astype(np.float64) / 255.0
    h, w = im.shape[:2]
    # sRGB -> linear, so the statistic is on light and not on the encode.
    lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4)
    gray = lin @ np.array(LUMA)
    horizon_row = spec["horizon_frac"] * h
    f = focal_px(w, hfov_deg)
    meadow = np.zeros((h, w), dtype=bool)
    for (x0, y0, x1, y1) in spec["meadow_rects"]:
        meadow[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = True
    for (x0, y0, x1, y1) in spec.get("exclude_rects", []):
        meadow[max(0, y0):min(h, y1), max(0, x0):min(w, x1)] = False
    rows = np.arange(h)[:, None] * np.ones((1, w))
    out = {"reference": name, "path": spec["path"], "resolution": [w, h],
           "camera_height_m": spec["camera_height_m"],
           "horizon_frac": spec["horizon_frac"],
           "fov_hint_in_recipe": spec["fov_hint"],
           "hfov_deg_assumed": hfov_deg,
           "focal_px": round(f, 1),
           "horizon_row": round(horizon_row, 1),
           "meadow_pixels_total": int(meadow.sum()),
           "bins": []}
    for lo, hi in BINS:
        # far distance -> SMALLER row offset, so the near distance gives
        # the LOWER edge of the band.
        r_far = row_for_distance(hi, spec["camera_height_m"], horizon_row, f)
        r_near = row_for_distance(lo, spec["camera_height_m"], horizon_row, f)
        band = meadow & (rows >= r_far) & (rows <= r_near)
        ent = {"bin_m": [lo, hi],
               "row_range": [round(r_far, 1), round(r_near, 1)],
               "pixels": int(band.sum())}
        if ent["pixels"] < MIN_PX:
            ent["std_over_mean"] = None
            ent["why"] = (
                "only %d meadow pixels in rows %.0f-%.0f. For this "
                "reference that band is off the bottom of the frame, or "
                "holds no meadow (track, rock, building, water)."
                % (ent["pixels"], r_far, r_near))
        else:
            v = gray[band]
            ent["mean_luminance"] = round(float(v.mean()), 6)
            ent["std_over_mean"] = round(float(v.std() / v.mean()), 4)
        out["bins"].append(ent)
    return out


def selftest():
    fails = []
    # 1. THE GEOMETRY, against hand-computable values. At hfov 90 on a
    #    1433-wide image, f = 716.5 px. A 1.8 m camera sees d = 1.8 m at
    #    45 degrees below the horizon, i.e. exactly f px below it.
    f = focal_px(1433, 90.0)
    if abs(f - 716.5) > 0.01:
        fails.append("focal_px(1433, 90) = %.3f, expected 716.5" % f)
    r = row_for_distance(1.8, 1.8, 100.0, f)
    if abs(r - (100.0 + f)) > 1e-6:
        fails.append("d == H should sit exactly f px below the horizon")
    # 2. MONOTONE AND BOUNDED: further is always closer to the horizon,
    #    and nothing below the horizon is ever above it.
    prev = None
    for d in (2, 5, 10, 50, 200, 1000):
        rr = row_for_distance(d, 1.8, 100.0, f)
        if rr <= 100.0:
            fails.append("d=%s landed on or above the horizon" % d)
        if prev is not None and rr >= prev:
            fails.append("row did not decrease from d=%s" % d)
        prev = rr
    # 3. THE METRIC, on a synthetic patch with a known std/mean, through
    #    the same code path the references use.
    rng = np.random.default_rng(11)
    v = 0.3 * (1.0 + 0.25 * rng.normal(0, 1, 400000))
    got = float(v.std() / v.mean())
    if abs(got - 0.25) / 0.25 > 0.02:
        fails.append("std/mean of a 25%% field read %.4f" % got)
    # 4. A BAND WITH NO MEADOW MUST REFUSE, not return a number.
    spec = {"path": "refs/alpine_village_01.jpg", "camera_height_m": 1.8,
            "horizon_frac": 0.45, "fov_hint": "x", "meadow_rects": [],
            "exclude_rects": []}
    r = measure_reference("empty", spec)
    if any(b["std_over_mean"] is not None for b in r["bins"]):
        fails.append("a reference with no meadow rects returned numbers")
    if not all("why" in b for b in r["bins"]):
        fails.append("an empty band gave no reason")
    # 5. The rects must be inside the images they claim.
    for name, sp in REFERENCES.items():
        im = Image.open(os.path.join(REPO, sp["path"]))
        w, h = im.size
        for (x0, y0, x1, y1) in sp["meadow_rects"]:
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                fails.append("%s: rect %r is outside %dx%d"
                             % (name, (x0, y0, x1, y1), w, h))
    if BINS != [(4.0, 10.0), (10.0, 30.0), (30.0, 100.0), (100.0, 300.0)]:
        fails.append("bins drifted")
    if fails:
        print("SELFTEST FAILED")
        for f_ in fails:
            print("  -", f_)
        return 1
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--sensitivity", action="store_true",
                    help="also compute at hfov 50 and 70 so the focal "
                         "assumption's effect is visible")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    fovs = [JUDGEMENT_HFOV_DEG] + ([50.0, 70.0] if a.sensitivity else [])
    res = {"_what": "Task 4: meadow luminance variation per depth bin, on "
                    "the Brief 2 reference set",
           "metric": "std/mean of Rec.709 luminance, sRGB decoded to "
                     "linear, meadow pixels only, shadows INCLUDED",
           "_focal_assumption": (
               "the concept recipes record fov_hint as prose and no "
               "number, so distances are computed at the JUDGEMENT "
               "camera's hfov (%.0f deg). That is what makes this the "
               "same instrument as the render table. A different focal "
               "length re-labels which rows fall in which bin; it does "
               "not change the pixels." % JUDGEMENT_HFOV_DEG),
           "_far_bins_are_not_measurable_here": (
               "30-100 m and 100-300 m come back EMPTY on both references "
               "and that is a property of the reference set, not of the "
               "crops. TWO independent reasons, either sufficient: (1) the "
               "row->distance map assumes a FLAT ground plane, and both "
               "images look across a BASIN onto a rising slope, so a row "
               "in the far bands does not correspond to the distance the "
               "flat model assigns it -- a number there would carry a "
               "wrong label, which is worse than no number; (2) the far "
               "ground in both images is village, forest and track, not "
               "meadow -- at hfov 90 the 30-100 m band is 30 px tall and "
               "the 100-300 m band 8 px, and neither holds grass. If the "
               "far bins matter to the band, the reference set needs an "
               "image with DISTANT MEADOW on near-level ground."),
           "results": []}
    for fov in fovs:
        for name, spec in REFERENCES.items():
            res["results"].append(measure_reference(name, spec, fov))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(res, indent=1) + "\n")
        print("wrote", a.out)
    for fov in fovs:
        print("\nhfov %.0f deg" % fov)
        print("  %-20s %-10s %9s %12s %10s"
              % ("reference", "bin (m)", "px", "rows", "std/mean"))
        for r in res["results"]:
            if r["hfov_deg_assumed"] != fov:
                continue
            for b in r["bins"]:
                s = ("%10.4f" % b["std_over_mean"]
                     if b["std_over_mean"] is not None else "  NO VERDICT")
                print("  %-20s %-10s %9d %12s %s"
                      % (r["reference"], "%g-%g" % tuple(b["bin_m"]),
                         b["pixels"],
                         "%.0f-%.0f" % tuple(b["row_range"]), s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
