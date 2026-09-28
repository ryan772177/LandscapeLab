"""Overnight comparison: same instrument on concept and render.

For each world: luma mean/std, saturation, sunlit-band R-B split, and the
haze proxy (min-luma near vs far) measured identically on the concept and
the locked render, plus a 2-column contact sheet. The numbers say how far
the MOOD is from the target; the sheet says how far the LAYOUT is. Both
are evidence for the morning report, not gates.
"""
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

PAIRS = [
    ("crystal_valley", "Free/gemini_v1/concept_crystal_valley.jpg",
     "_verify/20260901_overnight/renders/crystal_final2.png"),
    ("coast", "Free/gemini_v1/concept_coast.jpg",
     "_verify/20260901_overnight/renders/coast2_ev_test.png"),
    ("highland_lake", "Free/gemini_v1/concept_highland_lake.jpg",
     "_verify/20260901_overnight/renders/highland_final2.png"),
    ("canyon", "Free/gemini_v1/concept_canyon.jpg",
     "_verify/20260901_overnight/renders/canyon_gv.png"),
]


def measure(path):
    im = np.asarray(Image.open(os.path.join(REPO, path)).convert("RGB"))
    f = im.astype(np.float64) / 255.0
    luma = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
    mx = f.max(axis=2)
    mn = f.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    h = f.shape[0]
    band = f[int(h * 0.55):int(h * 0.80)]
    bl = 0.2126 * band[..., 0] + 0.7152 * band[..., 1] + 0.0722 * band[..., 2]
    k = max(1, int(bl.size * 0.15))
    idx = np.argsort(bl, axis=None)
    sunlit = band.reshape(-1, 3)[idx[-k:]]
    rb = float(sunlit[:, 0].mean() - sunlit[:, 2].mean())
    near = luma[int(h * 0.80):]
    far = luma[int(h * 0.05):int(h * 0.20)]
    return {"luma": round(float(luma.mean()), 3),
            "sat": round(float(sat.mean()), 3),
            "sunlit_rb": round(rb, 3),
            "minluma_far": round(float(np.percentile(far, 2)), 3),
            "minluma_near": round(float(np.percentile(near, 2)), 3)}


rows = {}
tiles = []
TW, TH = 960, 540
for name, cpath, rpath in PAIRS:
    rows[name] = {"concept": measure(cpath), "render": measure(rpath)}
    pair_imgs = []
    for p in (cpath, rpath):
        im = Image.open(os.path.join(REPO, p)).convert("RGB")
        im.thumbnail((TW, TH))
        canvas = Image.new("RGB", (TW, TH), (12, 12, 12))
        canvas.paste(im, ((TW - im.width) // 2, (TH - im.height) // 2))
        pair_imgs.append(canvas)
    strip = Image.new("RGB", (TW * 2 + 8, TH), (12, 12, 12))
    strip.paste(pair_imgs[0], (0, 0))
    strip.paste(pair_imgs[1], (TW + 8, 0))
    tiles.append(strip)

sheet = Image.new("RGB", (TW * 2 + 8, (TH + 8) * len(tiles) - 8),
                  (12, 12, 12))
for i, t in enumerate(tiles):
    sheet.paste(t, (0, i * (TH + 8)))
sheet.save(os.path.join(HERE, "comparison_sheet.png"))
json.dump(rows, open(os.path.join(HERE, "comparison_metrics.json"), "w"),
          indent=2)
for name, r in rows.items():
    c, rr = r["concept"], r["render"]
    print("%-14s luma %+.3f  sat %+.3f  rb %+.3f  haze(far-near) c=%+.3f "
          "r=%+.3f" % (name, rr["luma"] - c["luma"], rr["sat"] - c["sat"],
                       rr["sunlit_rb"] - c["sunlit_rb"],
                       c["minluma_far"] - c["minluma_near"],
                       rr["minluma_far"] - rr["minluma_near"]))
print("wrote comparison_sheet.png + comparison_metrics.json")
