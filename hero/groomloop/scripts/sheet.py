"""sheet.py -- lay renders side by side with captions. Plain CPython.

    python sheet.py <out.png> <label=path> [<label=path> ...]

Existence is checked per tile and a missing file becomes a visible RED tile
rather than a silently shorter sheet, because a contact sheet that quietly
drops a view is a sheet you will draw conclusions from without noticing.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

H = 520
BAR = 30
GAP = 8


def main():
    out = sys.argv[1]
    items = []
    for a in sys.argv[2:]:
        label, _, path = a.partition("=")
        items.append((label, path))
    tiles = []
    for label, path in items:
        if path and os.path.isfile(path):
            im = Image.open(path).convert("RGB")
            im = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
        else:
            im = Image.new("RGB", (H, H), (120, 20, 20))
            d = ImageDraw.Draw(im)
            d.text((10, H // 2), "MISSING", fill=(255, 255, 255))
        tiles.append((im, label))

    width = sum(t.width for t, _ in tiles) + GAP * (len(tiles) - 1)
    sheet = Image.new("RGB", (width, H + BAR), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("arial.ttf", 17)
    except Exception:
        f = ImageFont.load_default()
    x = 0
    for im, label in tiles:
        sheet.paste(im, (x, BAR))
        d.text((x + 6, 7), label, fill=(235, 235, 235), font=f)
        x += im.width + GAP
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print("wrote %s %s" % (out, sheet.size))


if __name__ == "__main__":
    main()
