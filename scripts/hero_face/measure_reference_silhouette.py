"""measure_reference_silhouette.py — the hero's head width profile, from the photograph.

WHY THIS EXISTS ALONGSIDE THE TRACKER
    The MetaHuman face tracker returns feature CURVES -- eyes, brows, lips,
    nose. It does not return the skull. But the most distinctive thing about
    this hero's head is its OUTLINE: a tall domed bald cranium over a wide
    square mandible. That lives in the silhouette, and the silhouette is
    measurable with nothing but the pixels.

    So this is a second instrument on a different property of the same
    artefact, which is what non-negotiable 0 asks for. Where it and the
    tracker overlap they must agree; where they do not overlap, each covers
    what the other cannot.

METHOD, AND WHY CHROMA AND NOT LUMINANCE
    prepare_hero_input.py established that the grey backdrop sits under a
    radial vignette, so no luminance threshold separates head from background
    across the whole frame. Chroma does: the backdrop is neutral (R~=G~=B)
    and skin is not. Same discriminator, reused deliberately rather than
    re-invented.

WHAT IT REFUSES
    Rows whose silhouette touches an image edge are reported as CLIPPED and
    excluded from the profile, because a head that runs off the crop has no
    measurable width there. Reporting the crop's width as the head's width is
    the failure this guards.

Usage: python scripts/hero_face/measure_reference_silhouette.py [--image PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=os.path.join(
        root, "hero", "reference", "hero_face_bald_headcrop.png"))
    ap.add_argument("--chroma", type=float, default=12.0,
                    help="max |max(RGB)-min(RGB)| still counted as backdrop")
    ap.add_argument("--out", default=os.path.join(
        root, "hero", "generated", "reference_silhouette.json"))
    ap.add_argument("--overlay", default=os.path.join(
        root, "_verify", "20260816_reference_silhouette.png"))
    args = ap.parse_args(argv)

    im = Image.open(args.image).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    chroma = a.max(axis=2) - a.min(axis=2)
    subject = chroma > args.chroma

    rows = []
    for y in range(h):
        xs = np.flatnonzero(subject[y])
        if xs.size == 0:
            rows.append(None)
            continue
        x0, x1 = int(xs[0]), int(xs[-1])
        clipped = (x0 == 0) or (x1 == w - 1)
        rows.append({"y": y, "x0": x0, "x1": x1, "width": x1 - x0 + 1,
                     "centre": (x0 + x1) / 2.0, "clipped": bool(clipped)})

    usable = [r for r in rows if r and not r["clipped"]]
    if not usable:
        print("REFUSE: every row is clipped or empty -- cannot measure a head")
        return 1

    top = usable[0]["y"]
    # The widest UNCLIPPED row above the mid-image is the cranium; below the
    # jaw the collar takes over and is not head.
    head_rows = [r for r in usable if r["y"] <= top + int(0.62 * (h - top))]
    widest = max(head_rows, key=lambda r: r["width"])

    print("image        : %s  (%dx%d)" % (os.path.basename(args.image), w, h))
    print("subject top  : y=%d" % top)
    print("widest head  : y=%d  width=%d px  centre x=%.1f"
          % (widest["y"], widest["width"], widest["centre"]))
    print("clipped rows : %d of %d non-empty"
          % (sum(1 for r in rows if r and r["clipped"]),
             sum(1 for r in rows if r)))

    # Normalise: 0.0 at the crown, 1.0 at the widest-row width.
    Wref = float(widest["width"])
    print("")
    print("WIDTH PROFILE  (depth below crown as a fraction of head width;")
    print("width as a fraction of the widest head row)")
    print("  d/W    width/W   y     note")
    profile = []
    for frac in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
                 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90,
                 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]:
        y = int(round(top + frac * Wref))
        if y >= h:
            break
        r = rows[y]
        if r is None:
            continue
        note = "CLIPPED" if r["clipped"] else ""
        profile.append({"depth_over_W": frac, "y": y,
                        "width_over_W": r["width"] / Wref,
                        "clipped": r["clipped"]})
        print("  %.2f   %.3f    %4d  %s" % (frac, r["width"] / Wref, y, note))

    data = {"image": os.path.relpath(args.image, root).replace("\\", "/"),
            "image_size": [w, h], "chroma_thresh": args.chroma,
            "crown_y": top, "widest_row": widest, "profile": profile}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(data, fh, indent=2)
    print("")
    print("wrote %s" % args.out)

    # Draw the silhouette edges over the photo so the measurement is LOOKED at
    # and not merely tabulated.
    ov = im.copy()
    px = ov.load()
    for r in rows:
        if r is None:
            continue
        col = (255, 60, 60) if r["clipped"] else (60, 255, 120)
        for x in (r["x0"], r["x1"]):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < w:
                    px[x + dx, r["y"]] = col
    os.makedirs(os.path.dirname(os.path.abspath(args.overlay)), exist_ok=True)
    ov.save(args.overlay)
    print("wrote %s" % args.overlay)
    return 0


if __name__ == "__main__":
    sys.exit(main())
