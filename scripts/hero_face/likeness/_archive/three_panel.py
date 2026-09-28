"""three_panel.py -- reference | best prior | this cut, on one sheet.

    python three_panel.py --out <ABS.png> --title "..." PANEL=path [PANEL=path ...]

Every panel is CROPPED TO THE HEAD before scaling, not letterboxed whole. A
reference portrait and a 4064x2546 game frame have wildly different subject
fractions, and pasting them side by side at equal width compares a head against
a landscape -- which is how this project has twice produced a sheet that looked
like a difference in hair and was a difference in framing.

The crop is stated per panel in the burned-in caption, so what was cut is
visible rather than implied.
"""

import argparse
import os

from PIL import Image, ImageDraw

CELL_W, CELL_H = 900, 1150
PAD, CAPTION = 18, 78
BG = (18, 18, 20)
FG = (232, 230, 226)
DIM = (150, 148, 144)


def fit(im, box_w, box_h, crop):
    """crop = (left, top, right, bottom) as fractions of the source."""
    w, h = im.size
    im = im.crop((int(w * crop[0]), int(h * crop[1]),
                  int(w * crop[2]), int(h * crop[3])))
    im.thumbnail((box_w, box_h), Image.LANCZOS)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("panels", nargs="+",
                    help="LABEL=path[:l,t,r,b] crop fractions, default 0,0,1,1")
    a = ap.parse_args()
    if not os.path.isabs(a.out):
        raise SystemExit("REFUSE: --out must be ABSOLUTE.")

    parsed = []
    for spec in a.panels:
        label, rest = spec.split("=", 1)
        crop = (0.0, 0.0, 1.0, 1.0)
        if ":" in rest:
            rest, c = rest.rsplit(":", 1)
            crop = tuple(float(x) for x in c.split(","))
        if not os.path.isfile(rest):
            raise SystemExit("REFUSE: missing panel image " + rest)
        parsed.append((label, rest, crop))

    n = len(parsed)
    W = PAD + n * (CELL_W + PAD)
    H = PAD + 46 + CELL_H + CAPTION + PAD
    sheet = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    if a.title:
        dr.text((PAD + 4, PAD + 6), a.title, fill=FG)

    for i, (label, path, crop) in enumerate(parsed):
        im = fit(Image.open(path).convert("RGB"), CELL_W, CELL_H, crop)
        x = PAD + i * (CELL_W + PAD) + (CELL_W - im.size[0]) // 2
        y = PAD + 46 + (CELL_H - im.size[1]) // 2
        sheet.paste(im, (x, y))
        cx = PAD + i * (CELL_W + PAD)
        cy = PAD + 46 + CELL_H + 8
        dr.text((cx + 4, cy), label, fill=FG)
        dr.text((cx + 4, cy + 16), os.path.basename(path), fill=DIM)
        dr.text((cx + 4, cy + 32),
                "crop l%.2f t%.2f r%.2f b%.2f  src %dx%d"
                % (crop[0], crop[1], crop[2], crop[3],
                   *Image.open(path).size), fill=DIM)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sheet.save(a.out)
    print("wrote", a.out, sheet.size)


if __name__ == "__main__":
    main()
