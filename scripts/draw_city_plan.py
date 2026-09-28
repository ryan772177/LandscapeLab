"""draw_city_plan.py -- look at the city plan before it costs an editor run.

    python scripts/draw_city_plan.py

Draws the planned streets and building footprints over the terrain's own
hillshade, in world coordinates. Offline, seconds, no editor.

WHY IT EXISTS. Every number in the plan can be right while the town sits in a
lake, straddles a ridge, or has its streets running up a cliff -- a statistic
about 240 buildings says nothing about where they are. This project's rule is
to open the pixels before trusting the statistic, and it has been paid for
repeatedly: a groom that gated PRESENT over a bald scalp, a crown height that
measured the forest, a scree apron that read as an outline.

THE HILLSHADE IS 16-BIT and `convert("RGB")` clips it to white -- which happened
on the first attempt at this view and produced a blank image that looked like a
missing file rather than a broken read. It is scaled by percentile here, and
the stretch is printed so the contrast is a stated choice.
"""

import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    plan = json.load(open(os.path.join(REPO, "city",
                                       "alpine_basin_town_plan.json"),
                          encoding="utf-8"))
    biome = json.load(open(os.path.join(REPO, plan["_biome"]), encoding="utf-8"))
    ls = biome["landscape"]
    ox, oy = float(ls["location_cm"][0]), float(ls["location_cm"][1])
    px = float(ls["scale_xy_cm"])

    cx, cy = plan["site_centre_cm"]
    R = plan["extent_radius_cm"]
    pad = R * 1.5
    x0 = int((cx - pad - ox) / px); x1 = int((cx + pad - ox) / px)
    y0 = int((cy - pad - oy) / px); y1 = int((cy + pad - oy) / px)

    hs = np.asarray(Image.open(os.path.join(REPO, "terrain",
                                            "alpine_8k_hillshade.png"))
                    .crop((x0, y0, x1, y1))).astype(np.float64)
    lo, hi = np.percentile(hs, 1), np.percentile(hs, 99)
    g = np.clip((hs - lo) / max(1e-9, hi - lo), 0, 1)
    # darken so the overlay reads
    img = Image.fromarray((np.dstack([g, g, g]) * 190).astype(np.uint8))
    S = 1400.0 / img.width
    img = img.resize((1400, int(img.height * S)), Image.LANCZOS)
    d = ImageDraw.Draw(img)

    def to_px(wx, wy):
        return ((wx - ox) / px - x0) * S, ((wy - oy) / px - y0) * S

    for s in plan["streets"]:
        sx, sy = s["loc_cm"][0], s["loc_cm"][1]
        a = math.radians(s["yaw_deg"])
        hl = s["len_cm"] * 0.5
        ax, ay = to_px(sx - hl * math.cos(a), sy - hl * math.sin(a))
        bx, by = to_px(sx + hl * math.cos(a), sy + hl * math.sin(a))
        d.line([ax, ay, bx, by], fill=(90, 170, 255),
               width=max(1, int(s["width_cm"] / px * S)))

    for b in plan["buildings"]:
        bx, by = b["loc_cm"][0], b["loc_cm"][1]
        sx, sy = b["size_cm"][0], b["size_cm"][1]
        a = math.radians(b["yaw_deg"])
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for ux, uy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
            lx, ly = ux * sx, uy * sy
            pts.append(to_px(bx + lx * ca - ly * sa, by + lx * sa + ly * ca))
        # storey count as brightness, so height reads in plan
        t = min(1.0, b["storeys"] / 5.0)
        col = (int(255 * t) , int(120 + 80 * t), 40)
        d.polygon(pts, fill=col, outline=(20, 20, 20))

    if plan.get("landmark"):
        lmk = plan["landmark"]
        lx, ly = to_px(lmk["loc_cm"][0], lmk["loc_cm"][1])
        r = lmk["size_cm"][0] / px * S * 0.5
        d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=(255, 60, 200),
                  outline=(255, 255, 255))

    for rr, col in ((plan["usable_radius_cm"], (255, 60, 60)),
                    (plan["extent_radius_cm"], (255, 210, 60))):
        ux, uy = to_px(cx, cy)
        rp = rr / px * S
        d.ellipse([ux - rp, uy - rp, ux + rp, uy + rp], outline=col, width=2)

    d.text((10, 10), "%s  --  %d buildings, %d street segments"
           % (plan["city_id"], plan["counts"]["buildings"],
              plan["counts"]["streets"]), fill=(255, 255, 0))
    d.text((10, 26), "red = flat core %.0f m   yellow = extent %.0f m   "
                     "pink = landmark"
           % (plan["usable_radius_cm"] / 100, plan["extent_radius_cm"] / 100),
           fill=(255, 255, 0))
    d.text((10, 42), "building fill brightens with storey count",
           fill=(255, 255, 0))

    out = os.path.join(REPO, "_verify", "20260824_city", "PLAN_topdown.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("hillshade stretch %.0f..%.0f" % (lo, hi))
    print("wrote %s (%dx%d)" % (out, img.width, img.height))


main()
