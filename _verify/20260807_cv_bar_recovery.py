"""Can the recorded CV band 0.089-0.367 be recovered from any plausible
definition? Tests candidate statistics against the same placements."""
import json
import math
import os
import sys

import numpy as np

# Derive the repo from this file's location rather than a hardcoded absolute
# path -- the original literals pointed at C:\Users\ryanb\... and could not run
# on any other machine (this repo is under a different user).
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import composite_stamps as cs          # noqa: E402
import measure_falloff_contours as mfc  # noqa: E402
w = mfc.load_world(os.path.join(REPO, "recipes", "alpine.json"))
placements = w["placements"]
origin_m, spacing_m = w["origin_m"], w["spacing_m"]
n = w["height_m"].shape[0]

print("%-30s %6s %6s | %7s %7s %7s %7s" % (
    "placement", "jitter", "jscale", "MINE", "H_r1", "H_n01", "H_mult"))
rows = []
for p in placements:
    stamp = w["stamps_by_id"][p["id"]]
    mask, r0, c0, cx, cy, half = mfc.placement_mask(
        p, stamp, origin_m, spacing_m, n)
    mine, _, _ = mfc.outer_contour_cv(mask, r0, c0, cx, cy, half, n)

    j = float(p["falloff_jitter"])
    sc = float(p["falloff_jitter_scale"])

    # Sample the SAME noise the compositor uses, on a dense ring at r=1
    # in normalised stamp space, to get n01 around the contour.
    th = np.linspace(0, 2 * np.pi, 4096, endpoint=False)
    un = np.cos(th)
    vn = np.sin(th)
    seed = ((int(p["stamp_sha256"][:8], 16)
             ^ __import__("zlib").crc32(p["id"].encode("utf-8")))
            & 0xFFFFFFFF)
    n01 = 0.5 * (cs._value_noise(un, vn, sc, seed) + 1.0)

    # H_r1  : CV of the outer contributing radius r = 1/(1+j*n01)
    r_out = 1.0 / (1.0 + j * n01)
    h_r1 = r_out.std() / r_out.mean()
    # H_n01 : CV of the raw noise field itself
    h_n01 = n01.std() / n01.mean()
    # H_mult: CV of the jitter multiplier (1 + j*n01)
    mult = 1.0 + j * n01
    h_mult = mult.std() / mult.mean()

    print("%-30s %6.2f %6.2f | %7.3f %7.3f %7.3f %7.3f" % (
        p["id"], j, sc, mine if mine is not None else float("nan"),
        h_r1, h_n01, h_mult))
    rows.append((p["id"], mine, h_r1, h_n01, h_mult))

print()
print("recorded band (schema.md:824, EIGHT placements): 0.089 - 0.367")
for name, idx in (("MINE", 1), ("H_r1", 2), ("H_n01", 3), ("H_mult", 4)):
    vals = [r[idx] for r in rows if r[idx] is not None]
    if not vals:
        # NN13: min()/max() over an empty list would crash; a stat with no
        # values is not a range.
        print("%-7s no values (every placement returned None)" % name)
        continue
    inside = sum(1 for v in vals if 0.089 <= v <= 0.367)
    print("%-7s range %.3f - %.3f   inside recorded band: %d/%d" % (
        name, min(vals), max(vals), inside, len(vals)))
