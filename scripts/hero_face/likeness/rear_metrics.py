"""rear_metrics.py — the REAR rubric, one implementation for both sides.

THE REFERENCE AND THE RENDER GO THROUGH THIS SAME CODE. That is the whole
design constraint. A rubric with one measurement path for the target and
another for the candidate is two lists that must agree (non-negotiable 24),
and it fails silently: both sides compute, both look reasonable, and the
residual they produce is meaningless.

WHAT IT MEASURES, AND WHY EACH ONE
----------------------------------
The rear reference constrains exactly what the frontal cannot see, so every
metric here is about the BACK of the cut:

    hair_height_px   the vertical extent of the hair mask in pixels (raw; a
                     fraction-of-head-height `nape_frac` is NOT computed here --
                     no head-height reference is measured). The reference tapers
                     ABOVE the collar; a groom that runs past it is the failure.
    taper_ratio      width at the nape divided by width at the crown. A
                     taper is a NUMBER less than one; a blunt bottom edge
                     reads near one. This is the metric that distinguishes
                     "short at the back" from "tapered at the back", which
                     eyeballing a silhouette does not.
    width_profile    hair-mask width sampled down the head, normalised. The
                     reference is widest at crown/upper skull and narrows.
    edge_roughness   silhouette perimeter divided by sqrt(area). A smooth
                     helmet scores low; choppy feathered chunks score high.
                     Dimensionless, so it survives a scale change between
                     reference and render -- which matters, because they are
                     photographed by different cameras at different sizes.

EVERY METRIC IS SCALE-FREE OR NORMALISED BY HEAD HEIGHT. The reference is a
1375x768 portrait and the render is a 2048x2048 SceneCapture; a metric in
pixels would compare a photograph's framing to ours and call it a hair
difference.

THE MASK IS THE WEAK LINK AND IT IS WRITTEN OUT
-----------------------------------------------
Every run can dump its mask as a PNG (`--dump-mask`). Look at it before
believing any number here. This project has repeatedly produced correct
arithmetic over a wrong region, and a hair mask that has quietly swallowed a
dark background or a shadowed collar is exactly that failure.

Exit codes:
    0  measured
    2  bad arguments or unreadable image
    4  the mask is degenerate (near-empty, <0.5% of frame, or more than half the
       frame), OR the largest-component correction could not run (scipy missing)
       -- refuses to report numbers rather than reporting numbers about nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

# A mask covering over half the frame is not a head of hair, it is a
# thresholding failure. Refuse rather than report.
MASK_MAX_FRAC = 0.50
MASK_MIN_FRAC = 0.005


def hair_mask(img: np.ndarray, luma_max: float, sat_max: float) -> np.ndarray:
    """Dark, unsaturated pixels. Hair in both the reference and our renders is
    near-black; skin is bright and warm, the reference background is mid-grey,
    and the collar is a saturated green. Saturation is what separates hair
    from the shadowed side of a green collar, which luminance alone does not.
    """
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return (luma <= luma_max) & (sat <= sat_max)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    """Keep only the biggest blob. The reference has a dark pauldron shadow in
    a corner and our renders have a whole dark forest; without this the mask's
    bounding box is the frame and every normalised metric is garbage.
    """
    try:
        from scipy import ndimage
    except Exception:
        # Returns (mask, applied=False) so the caller can surface that the
        # load-bearing correction was SKIPPED rather than pass silently.
        return mask, False
    lab, n = ndimage.label(mask)
    if n <= 1:
        return mask, True
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (int(np.argmax(sizes)) + 1), True


def measure(path: str, luma_max: float, sat_max: float,
            dump_mask: str | None = None) -> dict:
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, dtype=np.float32)
    m, lc_applied = _largest_component(hair_mask(a, luma_max, sat_max))

    frac = float(m.mean())
    if dump_mask:
        Image.fromarray((m * 255).astype(np.uint8)).save(dump_mask)
    if not lc_applied:
        # The largest-component correction is load-bearing (docstring): without
        # it a dark forest/pauldron shadow inflates the bounding box. If scipy
        # is missing it was skipped -- say so rather than report clean numbers.
        return {"ok": False, "mask_frac": frac,
                "largest_component_applied": False,
                "error": "scipy unavailable, so the largest-component "
                         "correction was skipped; metrics would be computed "
                         "over a multi-blob bounding box. Refusing."}
    if frac < MASK_MIN_FRAC or frac > MASK_MAX_FRAC:
        return {"ok": False, "mask_frac": frac,
                "largest_component_applied": True,
                "error": "mask is %.3f of frame, outside [%.3f, %.2f] -- this "
                         "is a thresholding failure, not a hairstyle"
                         % (frac, MASK_MIN_FRAC, MASK_MAX_FRAC)}

    ys, xs = np.nonzero(m)
    y0, y1 = int(ys.min()), int(ys.max())
    h = max(1, y1 - y0 + 1)

    # width profile down the mask, in 20 bands
    bands = 20
    widths = []
    for i in range(bands):
        a0 = y0 + int(h * i / bands)
        a1 = y0 + int(h * (i + 1) / bands)
        seg = m[a0:max(a1, a0 + 1)]
        cols = np.nonzero(seg.any(axis=0))[0]
        widths.append(float(cols.max() - cols.min() + 1) if cols.size else 0.0)
    wmax = max(widths) or 1.0
    prof = [w / wmax for w in widths]

    # crown width = widest band in the upper half; nape width = mean of the
    # non-empty bands among the LOWEST FOUR. Taper is their ratio.
    crown_w = max(widths[: bands // 2]) or 1.0
    low = [w for w in widths[-4:] if w > 0] or [0.0]
    nape_w = sum(low) / len(low)

    # perimeter via a 4-neighbour boundary count, area via the mask sum.
    pad = np.pad(m, 1)
    per = int((pad[1:-1, 1:-1] & ~pad[:-2, 1:-1]).sum()
              + (pad[1:-1, 1:-1] & ~pad[2:, 1:-1]).sum()
              + (pad[1:-1, 1:-1] & ~pad[1:-1, :-2]).sum()
              + (pad[1:-1, 1:-1] & ~pad[1:-1, 2:]).sum())
    area = int(m.sum())

    return {
        "ok": True,
        "image": path,
        "largest_component_applied": True,
        "mask_frac": round(frac, 4),
        "mask_luma_max": luma_max,
        "mask_sat_max": sat_max,
        "hair_height_px": h,
        "taper_ratio": round(float(nape_w / crown_w), 4),
        "edge_roughness": round(float(per / (area ** 0.5)), 4),
        "width_profile": [round(p, 3) for p in prof],
        "crown_width_px": round(crown_w, 1),
        "nape_width_px": round(nape_w, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True)
    ap.add_argument("--luma-max", type=float, default=70.0)
    ap.add_argument("--sat-max", type=float, default=0.35)
    ap.add_argument("--dump-mask")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.image):
        print("REFUSE: no such image:", args.image)
        return 2
    try:
        rep = measure(args.image, args.luma_max, args.sat_max, args.dump_mask)
    except (OSError, Image.UnidentifiedImageError) as exc:
        # A present-but-undecodable image is the "unreadable image" the exit-2
        # doc names; without this it crashed with a traceback (exit 1).
        print("REFUSE: unreadable image %s: %s" % (args.image, exc))
        return 2
    print(json.dumps(rep, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        # Read the sidecar back rather than trusting the write.
        try:
            with open(args.out, encoding="utf-8") as fh:
                json.load(fh)
        except (OSError, ValueError) as exc:
            print("REFUSE: --out %s did not read back: %s" % (args.out, exc))
            return 2
    return 0 if rep.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
