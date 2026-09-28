"""symmetry.py -- L/R symmetry of the HAIR silhouette in the front view.

The sides agent owns "the left and right sides ... and their symmetry", and no
axis in front_metrics measures it: band_cover and width_profile both collapse
left and right into one number, so a groom that has lost a whole lock on one
side scores identically to a balanced one.

Measured about the face centre cx that front_metrics already derives, in the
SAME rows it uses for its bands, so the two instruments agree on the anatomy.
Reported as (L-R)/(L+R) per band -- signed, so a bias has a direction.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import front_metrics as fm                                   # noqa: E402


def sym(name):
    img = ("_verify/20260822_agents/%s/preview_front.png" % name
           if name.startswith("sides") else
           "_verify/20260822_hero_authored/%s/preview_front.png"
           % name.replace("v", "h"))
    if not os.path.exists(img):
        img = "hero/reference/appearance_groom_clay.jpg"
    fm.BORDER = 14 if img.endswith(".jpg") else 6
    r = fm.measure(img)
    a = np.asarray(Image.open(img).convert("RGB")).astype(np.float32)
    L0 = a.mean(axis=2)
    bg0 = float(np.median(L0))
    top = 0
    for row in range(min(80, L0.shape[0])):
        if float((L0[row] < bg0 - 16.0).mean()) > 0.70:
            top = row + 1
        else:
            break
    L = a[top:, :, :].mean(axis=2)
    B = fm.BORDER
    L = L[:, B:L.shape[1] - B]
    hair = L < float(np.median(L)) - 16.0
    cx = r["face"]["centre_x_px"]
    ft, fh = r["face"]["top_row"], r["face"]["height_px"]
    out = {}
    for lab, f0, f1 in (("forehead", 0.00, 0.15), ("eye", 0.28, 0.42),
                        ("ear", 0.30, 0.62), ("jaw", 0.70, 0.95)):
        r0, r1 = ft + int(f0 * fh), ft + int(f1 * fh)
        band = hair[r0:r1 + 1]
        cols = np.arange(band.shape[1])
        lft = float(band[:, cols < cx].sum())
        rgt = float(band[:, cols > cx].sum())
        out[lab] = round((lft - rgt) / max(lft + rgt, 1.0), 4)
    tot_l = float(hair[:, np.arange(hair.shape[1]) < cx].sum())
    tot_r = float(hair[:, np.arange(hair.shape[1]) > cx].sum())
    out["TOTAL"] = round((tot_l - tot_r) / max(tot_l + tot_r, 1.0), 4)
    return out


if __name__ == "__main__":
    print("(L-R)/(L+R), signed; 0 = balanced, + = heavier on image-left")
    print("%-12s %9s %9s %9s %9s %9s"
          % ("run", "forehead", "eye", "ear", "jaw", "TOTAL"))
    for n in sys.argv[1:]:
        s = sym(n)
        print("%-12s %9.4f %9.4f %9.4f %9.4f %9.4f"
              % (n, s["forehead"], s["eye"], s["ear"], s["jaw"], s["TOTAL"]))
