"""void_mask.py — count pixels that show the SkyAtmosphere's virtual planet
surface (i.e. NOTHING rendered there) after the ground albedo has been set
to magenta for one capture. Hue-based, so aerial-perspective tinting does
not hide it: a magenta ground under blue inscatter still has R and B far
above G.

  python void_mask.py frame.png [--out void.json]

Reports void_fraction and a bbox, and writes frame_void.png with the void
pixels painted green so a human can see where the world ends.
"""
import argparse, json, sys
import numpy as np
from PIL import Image

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("frame"); ap.add_argument("--out"); ap.add_argument("--thresh", type=float, default=0.25)
    a = ap.parse_args(argv)
    im = np.asarray(Image.open(a.frame).convert("RGB")).astype(np.float64) / 255.0
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # magenta-ness: both R and B exceed G by a margin, and R,B are not tiny
    m = ((r - g) > a.thresh) & ((b - g) > a.thresh) & (r > 0.2) & (b > 0.2)
    frac = float(m.mean())
    ys, xs = np.nonzero(m)
    rep = {"frame": a.frame, "void_fraction": round(frac, 5),
           "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if xs.size else None,
           "_read": "0.0 = the whole frame has geometry; anything else is world that is not loaded/rendered at that station"}
    out = (im * 255).astype(np.uint8).copy(); out[m] = (0, 255, 0)
    Image.fromarray(out).save(a.frame.rsplit(".", 1)[0] + "_void.png")
    js = json.dumps(rep, indent=1)
    if a.out: open(a.out, "w").write(js)
    print(js)

if __name__ == "__main__":
    sys.exit(main())
