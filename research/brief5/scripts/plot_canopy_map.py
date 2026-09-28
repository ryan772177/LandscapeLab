#!/usr/bin/env python3
"""Brief 5 T6 — cover-class map: canopy_cover bins (256 m) over the heightmap
hillshade. READ-ONLY, offline. Writes research/brief5/derived/canopy_cover_map.png.

Bin index -> world: world_cm = bin_index * bin_cm; heightmap px =
(world_cm - origin_cm) / scale_xy_cm. Origin + scale from recipes/alpine_8k.json.
"""
import json
import os

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from matplotlib.patches import Rectangle

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CLASS_COLOR = {"forest": "#0b6b2f", "woodland": "#5fbf5f",
               "sparse": "#e6d24a", "open": "#d9b38c"}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(
        REPO, "research", "brief5", "derived", "canopy_cover.json"))
    ap.add_argument("--out", default=os.path.join(
        REPO, "research", "brief5", "derived", "canopy_cover_map.png"))
    ap.add_argument("--zone-map", default=None,
                    help="if given, overlay the three 512 m cull-disc edges "
                         "so the forest_floor density blend ring is visible")
    A = ap.parse_args()
    r = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                       encoding="utf-8-sig"))
    lm = r["landscape"] if "landscape" in r else r
    # origin + scale (cm). loc is the landscape actor location (recipe/spec).
    loc = r.get("landscape", {}).get("location") or r.get("location") or [-406400, -406400, 128000]
    scale = (r.get("sampling", {}) or {}).get("scale_xy_cm") or 100.0
    origin_x, origin_y = float(loc[0]), float(loc[1])

    cc = json.load(open(A.inp, encoding="utf-8"))
    bins = cc["bins"]
    bin_cm = cc["params"]["bin_cm"]

    # heightmap -> downsampled hillshade
    hm_path = os.path.join(REPO, "terrain", "alpine_8k.png")
    im = Image.open(hm_path)
    W, H = im.size
    ds = max(1, W // 1200)
    small = im.resize((W // ds, H // ds), Image.BILINEAR)
    z = np.asarray(small, dtype=np.float64)
    if z.ndim == 3:
        z = z[..., 0]
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(z, vert_exag=0.02)

    fig, ax = plt.subplots(figsize=(11, 11), dpi=110)
    # extent in world metres for the hillshade
    x0_m = origin_x / 100.0
    x1_m = (origin_x + W * scale) / 100.0
    y0_m = origin_y / 100.0
    y1_m = (origin_y + H * scale) / 100.0
    ax.imshow(hs, cmap="gray", extent=[x0_m, x1_m, y0_m, y1_m], origin="upper")

    binm = bin_cm / 100.0
    counts = {"forest": 0, "woodland": 0, "sparse": 0, "open": 0}
    for b in bins:
        ix, iy = b["bin"]
        cls = b["class"]
        counts[cls] = counts.get(cls, 0) + 1
        wx = (ix * bin_cm) / 100.0
        wy = (iy * bin_cm) / 100.0
        ax.add_patch(Rectangle((wx, wy), binm, binm,
                               facecolor=CLASS_COLOR.get(cls, "#888888"),
                               edgecolor="none", alpha=0.55))
    if A.zone_map:
        from matplotlib.patches import Circle
        zm = json.load(open(A.zone_map, encoding="utf-8"))
        dcol = {"forest_floor": "#ff3030", "plaza": "#30a0ff", "treeline": "#ffd000"}
        for name, c in zm["params"]["disc_centers_m"].items():
            ax.add_patch(Circle((float(c[0]), float(c[1])), 512.0, fill=False,
                                edgecolor=dcol.get(name, "#ffffff"), lw=1.6, ls="--"))
            # inner/outer blend edges for the density ramp (448 / 576 m)
            for rr in (float(zm["params"]["inner_edge_m"]),
                       float(zm["params"]["outer_edge_m"])):
                ax.add_patch(Circle((float(c[0]), float(c[1])), rr, fill=False,
                                    edgecolor=dcol.get(name, "#ffffff"), lw=0.6, ls=":"))
    ax.set_xlim(x0_m, x1_m)
    ax.set_ylim(y0_m, y1_m)
    ax.set_title("Brief 5 T6 — canopy cover class per 256 m bin\n"
                 "forest >=0.60  woodland 0.25-0.60  sparse 0.10-0.25  open <0.10")
    ax.set_xlabel("world X (m)")
    ax.set_ylabel("world Y (m)")
    handles = [Rectangle((0, 0), 1, 1, facecolor=CLASS_COLOR[c], alpha=0.55,
                         label="%s (%d bins)" % (c, counts.get(c, 0)))
               for c in ("forest", "woodland", "sparse", "open")]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.9)
    out = A.out
    fig.savefig(out, bbox_inches="tight")
    print("wrote", os.path.relpath(out, REPO), "| bin classes:", counts)


if __name__ == "__main__":
    main()
