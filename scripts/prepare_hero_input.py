#!/usr/bin/env python
"""Crop a hero portrait to head-and-neck for TRELLIS, from MEASUREMENT.

WHY THIS EXISTS
    The reference portraits frame head AND shoulders. TRELLIS reconstructs
    whatever is in frame, so the armour collar becomes geometry that Mesh to
    MetaHuman then has to be protected from. Removing it from the INPUT is
    strictly cheaper than stripping it from the OUTPUT, and cannot take skull
    geometry with it.

HOW THE BOX IS DERIVED, AND THE ONE ASSUMPTION IN IT
    The background of these renders is neutral grey under a RADIAL vignette.
    Luminance is therefore useless as a discriminator -- a per-row background
    model reads the bright centre of the vignette as subject and returns a
    bounding box of the whole image (measured, 2026-08-15, before this tool
    existed). CHROMA (max channel - min channel) is invariant to that shading:
    neutral grey is ~0 to 6 at every luminance, skin is ~46.

    From the chroma mask the tool measures the top of the skull, the widest
    head row, and that row's horizontal centre. The crop is a square of
    FRAME_FACTOR x head-width centred there.

    THE ASSUMPTION, stated rather than buried: the widest row in the upper
    HEAD_SEARCH_FRAC of the subject is the head at ear level, not a shoulder.
    That holds for a framed portrait and fails for a full-body shot -- which is
    why the tool REFUSES when the measured head width is a large fraction of
    the image (see _refuse_if_not_a_portrait).

POSITIVE CONTROL
    Chroma must separate: image corners must read neutral AND the centre-upper
    region must read as skin. If it does not, the tool exits 2 and writes
    NOTHING. A crop derived from a mask that did not find a head is worse than
    no crop, because it looks like a head crop.

USAGE
    python scripts/prepare_hero_input.py \
        --src hero/reference/hero_face_bald_frontal.jpg \
        --out hero/reference/hero_face_bald_headcrop.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Fraction of the subject's vertical span searched for the head's widest row.
HEAD_SEARCH_FRAC = 0.55
# Square side as a multiple of measured head width. 1.42 puts the skull top and
# the chin inside the frame with a small margin, verified by eye 2026-08-15.
FRAME_FACTOR = 1.42
# Chroma above this is subject. Neutral grey measures 0-6; skin measures ~46.
CHROMA_THRESH = 12.0
# Rows/cols carrying less than this fraction of subject pixels are speckle.
SPECKLE_FRAC = 0.02
# A head wider than this fraction of the image is not a framed portrait.
MAX_HEAD_FRAC = 0.75


def _refuse(msg: str) -> None:
    print(f"REFUSE: {msg}")
    sys.exit(2)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def measure(arr: np.ndarray) -> dict:
    """Measure head geometry. Returns a dict; never guesses on failure."""
    height, width, _ = arr.shape
    chroma = arr.max(axis=2) - arr.min(axis=2)

    # POSITIVE CONTROL -- both directions, before any measurement is trusted.
    # All FOUR corners (docstring says "corners"): a subject/prop intruding
    # into one corner, or a vignette that leaves only one corner neutral, must
    # still trip the control, so take the WORST (max) corner median.
    ch, cw = max(1, height // 20), max(1, width // 20)
    corner = float(max(
        np.median(chroma[:ch, :cw]), np.median(chroma[:ch, -cw:]),
        np.median(chroma[-ch:, :cw]), np.median(chroma[-ch:, -cw:])))
    skin_slice = chroma[height // 3: height // 2,
                        width // 2 - width // 20: width // 2 + width // 20]
    skin = float(np.median(skin_slice)) if skin_slice.size else float("nan")
    if corner >= 10.0:
        _refuse(f"image corners are not neutral (chroma {corner:.1f}); "
                "this tool's background model does not apply to this image")
    # NN13: an empty skin slice (tiny image) gives nan, and nan <= 15.0 is
    # False -- a PASS on zero samples. Refuse on a non-finite skin reading too.
    if not np.isfinite(skin) or skin <= 15.0:
        _refuse(f"centre-upper region does not read as skin (chroma {skin:.1f}); "
                "no head found, and a crop would be fiction")

    mask = chroma > CHROMA_THRESH
    row_w = mask.sum(axis=1)
    rows = np.where(row_w > width * SPECKLE_FRAC)[0]
    if rows.size == 0:
        _refuse("no subject rows survived the speckle filter")

    top, bottom = int(rows.min()), int(rows.max())
    search_end = top + int((bottom - top) * HEAD_SEARCH_FRAC)
    band = row_w[top : search_end + 1]
    widest_y = int(top + int(np.argmax(band)))
    head_w = int(row_w[widest_y])

    xr = np.where(mask[widest_y])[0]
    cx = int((int(xr.min()) + int(xr.max())) // 2)

    if head_w > width * MAX_HEAD_FRAC:
        _refuse(f"measured head width {head_w} is {head_w / width:.0%} of the "
                "image; this is not a framed portrait and the widest-row "
                "assumption does not hold")

    return {
        "image_w": width, "image_h": height,
        "chroma_corner": round(corner, 1), "chroma_skin": round(skin, 1),
        "subject_top": top, "subject_bottom": bottom,
        "head_widest_row": widest_y, "head_width": head_w, "head_centre_x": cx,
    }


def derive_box(m: dict) -> tuple[int, int, int, int]:
    side = int(round(m["head_width"] * FRAME_FACTOR))
    x0 = m["head_centre_x"] - side // 2
    y0 = m["subject_top"] - int(round(side * 0.05))
    # Clamp into the image, preserving the square.
    x0 = max(0, min(x0, m["image_w"] - side))
    y0 = max(0, min(y0, m["image_h"] - side))
    if side > m["image_w"] or side > m["image_h"]:
        _refuse(f"derived square side {side} exceeds image "
                f"{m['image_w']}x{m['image_h']}; cannot crop without distorting")
    return x0, y0, x0 + side, y0 + side


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--measure-only", action="store_true",
                    help="print the measurement and the derived box, write nothing")
    args = ap.parse_args()

    if not args.src.is_file():
        _refuse(f"source does not exist: {args.src}")

    # A present-but-unreadable/non-image file must give the documented clean
    # REFUSE (exit 2), not an uncaught PIL traceback (exit 1).
    try:
        img = Image.open(args.src).convert("RGB")
    except (OSError, Image.UnidentifiedImageError) as exc:
        _refuse(f"cannot read image {args.src}: {exc}")
    arr = np.asarray(img).astype(np.float32)

    m = measure(arr)
    box = derive_box(m)

    print(f"source          {args.src}  {m['image_w']}x{m['image_h']}")
    print(f"  sha256        {_sha256(args.src)}")
    print(f"chroma control  corner {m['chroma_corner']}  skin {m['chroma_skin']}  PASS")
    print(f"subject rows    {m['subject_top']}..{m['subject_bottom']}")
    print(f"head            widest row y={m['head_widest_row']} "
          f"width={m['head_width']} centre_x={m['head_centre_x']}")
    print(f"derived box     {box}  side={box[2] - box[0]}")

    if args.measure_only:
        print("measure-only: nothing written")
        return 0

    crop = img.crop(box)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(args.out)

    sidecar = args.out.with_suffix(".json")
    sidecar.write_text(json.dumps({
        "source": str(args.src).replace("\\", "/"),
        "source_sha256": _sha256(args.src),
        "measurement": m,
        "frame_factor": FRAME_FACTOR,
        "chroma_thresh": CHROMA_THRESH,
        "crop_box_x0y0x1y1": list(box),
        "output": str(args.out).replace("\\", "/"),
        "output_sha256": _sha256(args.out),
        "output_size": list(crop.size),
    }, indent=2) + "\n", encoding="utf-8")

    print(f"WROTE           {args.out}  {crop.size[0]}x{crop.size[1]}")
    print(f"  sha256        {_sha256(args.out)}")
    print(f"sidecar         {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
