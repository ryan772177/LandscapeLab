"""Measure the SWAPPED house's timber colour before and after the tiling fix.

    python scripts/measure_timber_colour.py

WHY A MEASUREMENT AND NOT AN EYE
The operator's open question is whether "the swapped timber reads warm orange,
close to new sawn wood" survives at correct texel density. That is a colour
judgement, and my eye had two confounds working on it: the re-shoot is at a
different distance and looks brighter. So the timber band is sampled
numerically instead.

⭐ THE MECHANISM BEING TESTED. Tiling changes SPATIAL FREQUENCY, not per-texel
hue. But perceived saturation is not per-texel: coarse texture presents large
uniform patches of colour, while fine texture optically mixes toward its own
mean. So a texture rendered too coarse can read markedly more saturated than
the same texture at correct scale, with no pixel of it having changed colour.
That is the hypothesis; this measures whether it happened here.

METHOD, and its limits stated plainly
  * The timber band is the UPPER STOREY of each house -- a horizontal strip
    that is almost entirely beam_wood/wall_planks_b on the swapped side and
    the same geometry on the original.
  * The band is located as a FRACTION of each house's own bounding box in
    frame, found by thresholding against the near-white background, so it
    tracks the house rather than fixed pixel coordinates.
  * Saturation is measured in HSV, and VALUE (HSV V, the max channel -- NOT
    HSL lightness) is reported beside it, printed as `val`,
    because the two frames differ in exposure and a saturation change that is
    really a brightness change must be visible as such.
  * A RATIO between the swapped and original house within the SAME frame is
    the primary number. Exposure and camera distance divide out of a ratio
    taken inside one image; they do not divide out of a cross-frame absolute.
"""
from __future__ import annotations

import io
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = [
    ("BEFORE (Tiling 1.0)",
     "_verify/20260830_overnight/C0_side_by_side_stage.png"),
    ("AFTER (derived tiling)",
     "_verify/20260830_c0/c0_stage_tiled_matched.png"),
]


def rgb_to_hsv(a):
    a = a.astype(np.float32) / 255.0
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return s, mx


def house_boxes(im):
    """Find the two houses as the two largest non-background column runs."""
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    # background: very bright and very desaturated (the white plane and sky)
    s, v = rgb_to_hsv(a)
    subject = (v < 0.93) | (s > 0.10)
    # ignore the top 25% (sky gradient) and the bottom 20% (ground shading)
    h, w = subject.shape
    subject[:int(h * 0.25), :] = False
    subject[int(h * 0.80):, :] = False
    # ⛔ DROP FULL-WIDTH ROWS. Both frames carry a dark horizontal band where
    # the ground plane's far edge meets the sky. It is dark, so it passes the
    # subject test, and it spans the whole frame -- which merged the two
    # houses into a single run and the detector correctly refused rather than
    # guessing. A house cannot occupy 90% of the frame width; a horizon can.
    rowfrac = subject.sum(axis=1) / float(w)
    subject[rowfrac > 0.90, :] = False
    cols = subject.sum(axis=0)
    thr = max(8, cols.max() * 0.15)
    runs, start = [], None
    for x in range(w):
        if cols[x] >= thr and start is None:
            start = x
        elif cols[x] < thr and start is not None:
            if x - start > w * 0.05:
                runs.append((start, x))
            start = None
    if start is not None and w - start > w * 0.05:
        runs.append((start, w))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    runs = sorted(runs[:2])
    boxes = []
    for x0, x1 in runs:
        rows = subject[:, x0:x1].sum(axis=1)
        ys = np.nonzero(rows >= max(4, rows.max() * 0.15))[0]
        boxes.append((x0, x1, int(ys.min()), int(ys.max())))
    return boxes, subject


def timber_band(im, box, subject):
    """The upper-storey band: 0.42-0.62 of the house's own height."""
    x0, x1, y0, y1 = box
    h = y1 - y0
    ya = y0 + int(h * 0.42)
    yb = y0 + int(h * 0.62)
    a = np.asarray(im.convert("RGB"), dtype=np.float32)[ya:yb, x0:x1]
    m = subject[ya:yb, x0:x1]
    if m.sum() < 50:
        return None
    s, v = rgb_to_hsv(a)
    # ⛔ SAMPLE THE MATERIAL, NOT THE BACKGROUND SHOWING THROUGH THE BOX.
    # The first version returned rgb [233,233,236] for the swapped timber --
    # the white ground plane visible beside the house inside its bounding box.
    # A mean over a box is a mean over whatever is in the box.
    m = m & (v < 0.90) & (v > 0.08)
    if m.sum() < 50:
        return None
    return {"sat_mean": float(s[m].mean()), "val_mean": float(v[m].mean()),
            "px": int(m.sum()),
            "rgb_mean": [round(float(a[..., i][m].mean()), 1)
                         for i in range(3)],
            "_crop": (a, m)}


def main():
    out = []
    for label, rel in FRAMES:
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            print("MISSING: " + rel)
            return 2
        with Image.open(p) as im:
            boxes, subject = house_boxes(im)
            if len(boxes) != 2:
                print("%s: found %d houses, expected 2 -- refusing to guess"
                      % (label, len(boxes)))
                return 3
            orig = timber_band(im, boxes[0], subject)
            swap = timber_band(im, boxes[1], subject)
        if orig is None or swap is None:
            # timber_band returns None when the sampled band is under 50 px;
            # main never checked it, so the next line (_crop.pop) crashed on
            # None. Refuse cleanly instead (matches the house-count refusal).
            print("%s: a timber band is under 50 px -- refusing to guess a "
                  "colour from too few pixels" % label)
            return 4
        # ⭐ DUMP WHAT WAS MEASURED. An instrument whose sample cannot be
        # looked at is one that cannot be checked, and this one already
        # returned the white ground plane once while reporting a confident
        # number.
        tag = "before" if "BEFORE" in label else "after"
        for nm, row in (("original", orig), ("swapped", swap)):
            arr, mask = row.pop("_crop")
            vis = arr.copy()
            vis[~mask] = [255, 0, 255]      # magenta = NOT sampled
            Image.fromarray(vis.astype(np.uint8)).save(
                os.path.join(REPO, "_verify", "20260830_c0",
                             "sample_%s_%s.png" % (tag, nm)))
        ratio = swap["sat_mean"] / max(1e-6, orig["sat_mean"])
        out.append({"frame": label, "file": rel,
                    "original": orig, "swapped": swap,
                    "sat_ratio_swapped_over_original": round(ratio, 3)})
        print("%s" % label)
        print("   ORIGINAL  sat %.4f  val %.4f  rgb %s  (n=%d px)"
              % (orig["sat_mean"], orig["val_mean"], orig["rgb_mean"],
                 orig["px"]))
        print("   SWAPPED   sat %.4f  val %.4f  rgb %s  (n=%d px)"
              % (swap["sat_mean"], swap["val_mean"], swap["rgb_mean"],
                 swap["px"]))
        print("   SWAPPED/ORIGINAL saturation ratio: %.3f" % ratio)
        print("")

    b, a_ = out[0], out[1]
    print("THE COMPARISON THAT SURVIVES EXPOSURE AND DISTANCE:")
    print("   before  swapped timber is %.2fx the original's saturation"
          % b["sat_ratio_swapped_over_original"])
    print("   after   swapped timber is %.2fx the original's saturation"
          % a_["sat_ratio_swapped_over_original"])
    ch = (a_["sat_ratio_swapped_over_original"]
          / max(1e-6, b["sat_ratio_swapped_over_original"]))
    print("   the swapped-vs-original excess changed by %.2fx" % ch)
    with io.open(os.path.join(REPO, "_verify", "20260830_c0",
                              "timber_colour.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"frames": out, "excess_change": round(ch, 3)}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
