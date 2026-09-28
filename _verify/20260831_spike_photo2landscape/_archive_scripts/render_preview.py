"""Spike-only top-down preview: hillshade + flow-derived river + city plan.

One-off evidence renderer for the side-project spike. World->pixel mapping
verified against composite_stamps' own dry-run readout: world (1550,100) m
-> px (row 529.5, col 892) with origin -201800 cm and 400 cm spacing.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

OX_CM = -201800.0
PX_CM = 400.0


def to_px(x_cm, y_cm):
    return ((x_cm - OX_CM) / PX_CM, (y_cm - OX_CM) / PX_CM)  # (col, row)


hill_raw = np.asarray(Image.open(os.path.join(REPO, "terrain", "spike_photo2landscape_hillshade.png"))).astype(np.float64)
lo, hi = hill_raw.min(), hill_raw.max()
hill8 = ((hill_raw - lo) / (hi - lo) * 255.0).astype(np.uint8)
hill = Image.fromarray(np.stack([hill8] * 3, axis=2), "RGB")
W, H = hill.size

flow = np.asarray(Image.open(os.path.join(REPO, "terrain", "spike_photo2landscape_flow.png"))).astype(np.float64)
thresh = np.percentile(flow, 99.0)
river = flow >= thresh

img = np.asarray(hill).astype(np.float64)
blue = np.array([70.0, 120.0, 200.0])
img[river] = img[river] * 0.35 + blue * 0.65
canvas = Image.fromarray(img.astype(np.uint8))
draw = ImageDraw.Draw(canvas)

plan = json.load(open(os.path.join(HERE, "city_plan.json"), encoding="utf-8"))

for s in plan["streets"]:
    x, y = s["loc_cm"][0], s["loc_cm"][1]
    yaw = math.radians(s["yaw_deg"])
    hx = math.cos(yaw) * s["len_cm"] / 2.0
    hy = math.sin(yaw) * s["len_cm"] / 2.0
    c0, r0 = to_px(x - hx, y - hy)
    c1, r1 = to_px(x + hx, y + hy)
    draw.line([(c0, r0), (c1, r1)], fill=(90, 70, 50), width=1)

for b in plan["buildings"]:
    x, y = b["loc_cm"][0], b["loc_cm"][1]
    yaw = math.radians(b["yaw_deg"])
    sx, sy = b["size_cm"][0] / 2.0, b["size_cm"][1] / 2.0
    corners = []
    for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
        wx = x + dx * math.cos(yaw) - dy * math.sin(yaw)
        wy = y + dx * math.sin(yaw) + dy * math.cos(yaw)
        corners.append(to_px(wx, wy))
    draw.polygon(corners, fill=(212, 175, 55))

for key, colour in (("landmark", (255, 90, 40)), ("spire", (255, 220, 60))):
    ent = plan.get(key)
    if isinstance(ent, dict) and "loc_cm" in ent:
        c, r = to_px(ent["loc_cm"][0], ent["loc_cm"][1])
        draw.ellipse([c - 3, r - 3, c + 3, r + 3], outline=colour, width=2)

canvas.save(os.path.join(HERE, "preview_full.png"))

# city closeup: 1200 m square around the site, upscaled x3
sc, sr = to_px(plan["site_centre_cm"][0], plan["site_centre_cm"][1])
half = int(600.0 / 4.0)
box = (int(sc - half), int(sr - half), int(sc + half), int(sr + half))
crop = canvas.crop(box).resize((half * 6, half * 6), Image.NEAREST)
crop.save(os.path.join(HERE, "preview_city.png"))

print("river px:", int(river.sum()), "of", river.size)
print("wrote preview_full.png and preview_city.png")
