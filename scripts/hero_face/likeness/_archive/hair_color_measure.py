"""hair_color_measure.py -- the rendered colour OF THE HAIR, not of the frame.

    python hair_color_measure.py <all.png> <minus_Hair.png> [label]

WHY A MASK. On 2026-08-19 a hair colour was measured by averaging a difference
mask over a sparse groom and the number came back as SKIN -- the mean of a
region that is mostly the gaps between strands. So the mask here is the gate's
own hidden/shown difference, and pixels are kept only where hiding the hair
changed the picture by a real margin. That is the same instrument the presence
gate trusts, used for a different question.

WHY PERCENTILES AND NOT A MEAN. The operator's target is three zones -- deep
shadow, midtone body, highlight -- and a single mean collapses exactly the
structure being asked for. p10 / p50 / p90 of the hair pixels, by luminance,
map onto those three.

WHAT THIS CANNOT SETTLE, and it must be said before any number is quoted: the
target RGBs come from a reference image with its own lamps and its own
tonemapper. An absolute RGB match between that and our render is a statement
about the lighting, not about the hair -- `compare_to_reference.py`'s docstring
says so and it is why that tool refuses to compare colour numerically. What IS
comparable is the STRUCTURE: the hue direction (cool or warm) and the ratios
between the three zones.
"""

import os
import sys

import numpy as np
from PIL import Image


def white_point(A):
    """The studio backdrop, used as an in-frame neutral reference.

    Every zone of the first measurement came back warm (midtone R-B +19,
    highlight +51) at EVERY mask threshold. That is not a finding about the
    hair, because the lamps are warm-white (255,253,250) and the alpine sun is a
    low warm sun -- warm light on neutral hair gives warm pixels, and no
    threshold separates the two.

    The backdrop is `/Engine/EngineMaterials/DefaultMaterial`, a flat neutral
    grey, lit by the same lamps in the same frame. Dividing by it removes the
    lamp from the answer. This is a white balance, not a correction factor
    invented to make a number agree.
    """
    mx, mn = A.max(2), A.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    plain = (mx > 110) & (sat < 0.14)
    if plain.sum() < 5000:
        return None, int(plain.sum())
    wp = A[plain].astype(np.float64).mean(0)
    return wp / wp.mean(), int(plain.sum())


def measure(all_png, minus_png, label="", thr=90, balance=True):
    A = np.asarray(Image.open(all_png).convert("RGB")).astype(np.int16)
    H = np.asarray(Image.open(minus_png).convert("RGB")).astype(np.int16)
    diff = np.abs(A - H).max(2)
    mask = diff > thr
    n = int(mask.sum())
    if n < 500:
        return {"label": label, "error":
                "only %d hair pixels -- I could not measure this" % n}

    px = A[mask].astype(np.float64)
    wp, n_plain = white_point(A)
    wb = "none"
    if balance and wp is not None:
        px = px / wp
        wb = "[%.3f %.3f %.3f] from %d backdrop px" % (wp[0], wp[1], wp[2],
                                                       n_plain)
    elif balance:
        wb = "NOT APPLIED -- only %d backdrop px found, could not balance" \
             % n_plain
    lum = px @ np.array([0.2126, 0.7152, 0.0722])
    order = np.argsort(lum)
    px = px[order]
    zones = {}
    for name, lo, hi in (("shadow", 0.02, 0.15),
                         ("midtone", 0.40, 0.60),
                         ("highlight", 0.88, 0.99)):
        seg = px[int(len(px) * lo):int(len(px) * hi)]
        rgb = seg.mean(0)
        zones[name] = {
            "rgb": [int(round(x)) for x in rgb],
            "hex": "#%02X%02X%02X" % tuple(int(round(x)) for x in rgb),
            "warm_R_minus_B": round(float(rgb[0] - rgb[2]), 2)}
    return {"label": label, "hair_pixels": n, "threshold": thr,
            "white_balance": wb,
            "frac_of_frame": round(float(mask.mean()), 5), "zones": zones}


def report(r, target=None):
    if "error" in r:
        print("  %-14s %s" % (r["label"], r["error"]))
        return
    print("  %s   %d hair px (%.2f%% of frame), mask thr %d"
          % (r["label"], r["hair_pixels"], r["frac_of_frame"] * 100,
             r["threshold"]))
    print("     white balance %s" % r["white_balance"])
    for k in ("shadow", "midtone", "highlight"):
        z = r["zones"][k]
        line = "     %-10s %-8s %-16s  R-B %+6.1f" % (
            k, z["hex"], str(z["rgb"]), z["warm_R_minus_B"])
        if target and k in target:
            t = target[k]
            line += "   | target %s R-B %+d" % (
                "#%02X%02X%02X" % t, t[0] - t[2])
        print(line)


TARGET = {"shadow": (20, 21, 23), "midtone": (42, 44, 49),
          "highlight": (82, 86, 93)}

if __name__ == "__main__":
    a, m = sys.argv[1], sys.argv[2]
    lab = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(a)
    report(measure(a, m, lab), TARGET)
    print()
    print("  target warm undertone #3A3432 (58,52,50) R-B +8 -- that zone is"
          " ambient/skin bounce,")
    print("  not hair pigment, so it is not something a hair dye parameter"
          " should be made to produce.")
