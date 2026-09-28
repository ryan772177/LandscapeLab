"""panel.py -- the three-panel milestone report: clay | previous | current.

    python panel.py <out.png> <view> <label>=<image> [<label>=<image> ...]

    view = front | back

The clay reference is prepended automatically for a front panel, and the photo
rear for a back panel, because the operator's verdict is taken against the
TARGET and a sheet that shows only our own iterations invites judging progress
against progress.

Panels are scaled to a common HEIGHT, not a common width: these are busts of
different heads at different framings, and matching height is what makes the
hair proportions comparable by eye. The clay's title strip is cropped in the
same way front_metrics.py crops it, so what is scored and what is shown are the
same picture.
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw

CLAY = "hero/reference/appearance_groom_clay.jpg"
REAR = "hero/reference/hero_example_pic_rear.jpg"
H = 620


def load(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32).mean(axis=2)
    bg = float(np.median(a))
    cut = 0
    for r in range(min(80, a.shape[0])):
        if float((a[r] < bg - 16.0).mean()) > 0.70:
            cut = r + 1
        else:
            break
    if cut:
        im = im.crop((0, cut, im.width, im.height))
    return im


def main():
    out, view = sys.argv[1], sys.argv[2]
    tiles = []
    ref = CLAY if view == "front" else REAR
    if os.path.isfile(ref):
        tiles.append(("TARGET  " + os.path.basename(ref), ref))
    for spec in sys.argv[3:]:
        label, path = spec.split("=", 1)
        if os.path.isfile(path):
            tiles.append((label, path))
        else:
            tiles.append((label + "  [MISSING]", None))

    ims = []
    for label, path in tiles:
        if path is None:
            im = Image.new("RGB", (int(H * 0.8), H), (40, 20, 20))
        else:
            im = load(path)
            im = im.resize((max(1, int(im.width * H / im.height)), H),
                           Image.LANCZOS)
        ims.append((im, label))

    pad, bar = 6, 24
    W = sum(i.width for i, _ in ims) + pad * (len(ims) + 1)
    sheet = Image.new("RGB", (W, H + bar + pad * 2), (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    x = pad
    for im, label in ims:
        sheet.paste(im, (x, bar + pad))
        d.text((x + 5, 7), label, fill=(238, 238, 238))
        x += im.width + pad
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    sheet.save(out)
    print("__PANEL__%s  %dx%d  %d tiles" % (out, sheet.width, sheet.height,
                                            len(ims)))


if __name__ == "__main__":
    main()
