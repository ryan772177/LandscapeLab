"""Derive a WEATHERED-COPPER PLACEHOLDER albedo from an existing base.

    python scripts/make_copper_placeholder.py

⛔ THIS IS A PLACEHOLDER AND MUST NEVER BECOME THE ARTEFACT OF RECORD.
The operator is generating the real copper/patina tile. Ruled 2026-08-30:
"until then derive a placeholder from an existing base, mark it
pipeline-derived, and never let it become the artefact of record."

Three things make that stick rather than being a hope:
  * the filename carries PLACEHOLDER, so it cannot be cited by accident,
  * `Free/_measured/copper_placeholder.json` records base + method + hash and
    says PLACEHOLDER in its own `status`,
  * `recipes/church_materials.json` marks the role `placeholder: true`, and
    the build reports which slots are waiting on the real tile.

WHAT IS DERIVED AND WHAT IS INVENTED -- they are different claims
  DERIVED   the STRUCTURE. Luminance of the base tile, high-passed to keep
            the fine surface variation and drop its large-scale shading.
            Structure is the half a placeholder can honestly borrow.
  INVENTED  the COLOUR. A luminance ramp into weathered-copper hues: dark
            red-brown in the lows through to green patina in the highs. There
            is no measurement anywhere behind those hues -- they are read off
            the concept's own words ("WEATHERED COPPER ONION DOME, dark
            red-brown") and nothing else.

The base is `plaster_wall_tiled.jpg`: fine and non-directional, which is the
closest available structure to a beaten metal sheet. Using `roof_tiles` would
have imported a shingle pattern onto a dome.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "refs/textures_v1/plaster_wall_tiled.jpg"
OUT = "refs/derived_placeholder/copper_patina_PLACEHOLDER.png"
MAN = "Free/_measured/copper_placeholder.json"

# Weathered copper, read off the concept's words. Low luminance -> the dark
# red-brown the concept names; high -> the green patina that collects in the
# raised and washed areas. Deliberately only four stops: a placeholder that
# looks too resolved invites being kept.
STOPS = [
    (0.00, (61, 28, 20)),      # deep shadow, dark red-brown
    (0.40, (124, 60, 38)),     # body copper, oxidised
    (0.72, (96, 124, 96)),     # patina beginning
    (1.00, (140, 176, 150)),   # pale green patina on the washed highs
]


def ramp(x):
    """Piecewise-linear colour ramp over luminance in [0,1]."""
    out = np.zeros(x.shape + (3,), dtype=np.float32)
    for i in range(len(STOPS) - 1):
        x0, c0 = STOPS[i]
        x1, c1 = STOPS[i + 1]
        m = (x >= x0) & (x <= x1)
        if not m.any():
            continue
        t = ((x[m] - x0) / (x1 - x0))[:, None]
        out[m] = np.array(c0, np.float32) * (1 - t) + np.array(c1, np.float32) * t
    return out


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    bp = os.path.join(REPO, BASE)
    if not os.path.exists(bp):
        print("REFUSE: base %s is absent" % BASE)
        return 2
    with Image.open(bp) as im:
        a = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]

    # HIGH-PASS: keep fine structure, drop the base's own large-scale shading.
    # Without this the plaster's broad light/dark drifts would read as dents in
    # a metal dome -- borrowing the base's lighting, not its surface.
    k = 33
    pad = np.pad(lum, k // 2, mode="reflect")
    cs = np.cumsum(np.cumsum(pad, 0), 1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    h, w = lum.shape
    box = (cs[k:k + h, k:k + w] - cs[0:h, k:k + w]
           - cs[k:k + h, 0:w] + cs[0:h, 0:w]) / float(k * k)
    detail = lum - box
    # normalise the detail to [0,1] about its own midpoint
    s = float(np.percentile(np.abs(detail), 99)) or 1e-6
    x = np.clip(0.5 + detail / (2.0 * s), 0.0, 1.0)

    rgb = ramp(x)
    out_p = os.path.join(REPO, OUT)
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(out_p)

    with Image.open(out_p) as _oi:      # close the handle rather than leak it
        out_size = list(_oi.size)
    man = {
        "status": "PLACEHOLDER -- NOT THE ARTEFACT OF RECORD",
        "role": "copper_patina",
        "file": OUT,
        "base": BASE,
        "base_sha256": sha(bp),
        "sha256": sha(out_p),
        "size": out_size,
        "method": ("luminance of the base, high-passed with a %d px box to "
                   "keep fine structure and drop large-scale shading, then "
                   "mapped through a 4-stop weathered-copper ramp" % k),
        "derived": "the STRUCTURE only",
        "invented": ("the COLOUR. The hues are read off the concept's words "
                     "-- 'WEATHERED COPPER ONION DOME, dark red-brown' -- and "
                     "nothing else. No measurement stands behind them."),
        "retires_when": ("the operator's generated copper/patina tile lands. "
                         "This file is then deleted from the role table, not "
                         "kept as a fallback."),
        "adopted": "2026-08-31",
    }
    man_p = os.path.join(REPO, MAN)
    with io.open(man_p, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    # Read the manifest back: it is the record that keeps this file honestly
    # marked PLACEHOLDER, so a write that did not persist must not report success.
    with io.open(man_p, encoding="utf-8") as fh:
        if not str(json.load(fh).get("status", "")).startswith("PLACEHOLDER"):
            print("REFUSE: %s did not read back with its PLACEHOLDER status."
                  % MAN)
            return 2
    print("wrote %s  (%dx%d)" % (OUT, man["size"][0], man["size"][1]))
    print("  base   %s" % BASE)
    print("  sha256 %s" % man["sha256"][:16])
    print("  STATUS %s" % man["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
