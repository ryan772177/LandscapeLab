"""sides_profile.py -- WHERE the side mass is wrong, per anatomical band.

READ-ONLY DIAGNOSTIC, owned by the sides agent. It does NOT define a second
segmentation: it calls front_metrics.measure() -- the ONE instrument -- with
--dump-mask and aggregates that mask's own hair channel. A rival threshold here
would make every number a difference between two measurements rather than a
difference between two grooms.

Reports, per anat band (the same u-edges front_metrics scores on):
    cover   the judge's anat_cover, reprinted so this file can be checked
            against judge.py rather than trusted
    halfw   hair half-width / face half-width -- the ABSOLUTE extent
            anat_cover's ratio cannot see, because hair widens `subj` and
            `hair` together
    L,R     signed halves, and the symmetry bias (L-R)/(L+R)
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FM = os.path.join(HERE, "..", "scripts", "front_metrics.py")
ANAT = {"jaw": (0.03, 0.14), "ear": (0.14, 0.31), "eye": (0.21, 0.29),
        "brow": (0.29, 0.35), "forehead": (0.35, 0.47), "crown": (0.47, 0.70)}
ORDER = ("jaw", "ear", "eye", "brow", "forehead", "crown")


def profile(png, tag):
    dump = os.path.join(HERE, "_masks", tag + ".png")
    os.makedirs(os.path.dirname(dump), exist_ok=True)
    out = subprocess.run([sys.executable, FM, png, "--dump-mask", dump],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("front_metrics failed on %s:\n%s" % (png, out.stderr))
    rep = json.loads(out.stdout)
    a = np.asarray(Image.open(dump).convert("RGB"))
    hair = a[..., 0] > 128
    chin = rep["anat_anchors"]["chin_row"]
    unit = float(rep["anat_anchors"]["shoulder_w_px"])
    fw = float(rep["anat_anchors"]["face_w_px"])
    cx = rep["face"]["centre_x_px"]
    rows = {}
    for k, (u0, u1) in ANAT.items():
        r0 = int(round(chin - u1 * unit))
        r1 = int(round(chin - u0 * unit))
        r0, r1 = max(0, r0), min(a.shape[0] - 1, r1)
        band = hair[r0:r1 + 1]
        cols = np.nonzero(band.any(axis=0))[0]
        if cols.size == 0:
            rows[k] = None
            continue
        R = max(cols.max() - cx, 0.0)
        L = max(cx - cols.min(), 0.0)
        rows[k] = {"cover": rep["anat_cover"][k],
                   "halfw": round(max(L, R) / (0.5 * fw), 4),
                   "L": round(L / (0.5 * fw), 4), "R": round(R / (0.5 * fw), 4),
                   "bias": round((L - R) / max(L + R, 1e-9), 4)}
    return rep, rows


if __name__ == "__main__":
    for png, tag in zip(sys.argv[1::2], sys.argv[2::2]):
        rep, rows = profile(png, tag)
        print("== %s   face_w=%d shoulder_w=%d chin=%d" %
              (tag, rep["anat_anchors"]["face_w_px"],
               rep["anat_anchors"]["shoulder_w_px"],
               rep["anat_anchors"]["chin_row"]))
        print("%-10s %7s %7s %7s %7s %7s" %
              ("BAND", "cover", "halfw", "L", "R", "bias"))
        for k in ORDER:
            v = rows[k]
            print("%-10s %7s %7s %7s %7s %7s" % (
                k, "n/a" if v is None else v["cover"],
                "n/a" if v is None else v["halfw"],
                "n/a" if v is None else v["L"],
                "n/a" if v is None else v["R"],
                "n/a" if v is None else v["bias"]))
        print()
