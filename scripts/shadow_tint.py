"""shadow_tint.py — how blue is the shade, relative to how bright it is?

Acceptance: `shadow_tint_B` at near_ground in **1.10-1.60** (RE-DERIVED BY
RYAN 2026-09-10 for NEUTRAL white balance, from daylight-shade
photographic reference). The original 1.3-1.7 band below was calibrated
in an era whose only PASS carried a WB 1300 K BELOW the sun — a
blue-amplifying grade the R-GRADE rule has since retired; under neutral
WB the same shade reads lower by construction.

    shadow_tint_B = B_shadow / luma_shadow      (linear RGB)

WHY THE RATIO AND NOT THE BLUE VALUE. Shade under a clear sky IS blue -- sky
light is blue and it is what fills the shadows. The question is never "is
there blue" but "how much blue PER UNIT BRIGHTNESS", because that is what the
eye judges. Dividing by luma removes exposure from the answer entirely, which
matters here: the recipe's -1.923 EV was itself a compensation for the sky
light being too strong, so any absolute measure would move when either lever
moved and tell you nothing about which.

THE BAND. Photographic reference and the Epic frames put shade under a clear
sky at roughly 1.3-1.7. Below ~1.3 the shade reads dead and unlit; above ~1.7
no viewer accepts it as shade -- it reads as a blue LIGHT rather than as an
absence of the sun. near_ground measured 3.00 before this task.

SHADOW IS SPLIT AT THE MEDIAN, not at a fixed luma: the frame's own median
divides lit from shaded, so the split follows the exposure rather than
fighting it. That is measure_concept_look's convention (measure_palette),
reused here so the two describe the same pixels.

THE WHOLE LAND REGION below the skyline, not a sub-band. BRIEF §4 says
"shadow_tint_B (near_ground, B/luma of shadow median)" -- `near_ground` there
names the STATION, not measure_palette's `near` band, and the two are very
different at this station. Measured 2026-09-09 on one frame:

    far band    B/luma 1.871
    mid band    B/luma 1.772
    near band   B/luma 0.971      <- sunlit meadow grass, GREEN-dominant
    whole land  B/luma 1.753

The `near` band is the bottom 30% of the land region, which at a ground-level
station in a meadow is mostly grass in sun -- its shadow median is green, not
blue, and reading it as "the shade" answers a different question. Taking the
whole land region includes canopy shade, which is what the acceptance is
about.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure_concept_look as mcl  # noqa: E402


def measure(path, band=(0.0, 1.0), exclude_rect_px=None):
    srgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    sk = mcl.measure_skyline(srgb, lin)
    h, w = lin.shape[:2]
    sky_row = np.interp(np.arange(w), np.linspace(0, w - 1, 64),
                        np.array(sk["row_frac"]) * (h - 1))
    land = np.zeros((h, w), dtype=bool)
    for x in range(w):
        land[int(sky_row[x]) + 2:, x] = True
    if exclude_rect_px:
        # The grey card (R-GREYCARD) is a synthetic neutral plane inside
        # the land region; measured on its own, masked out of the scene.
        x0, y0, x1, y1 = exclude_rect_px
        land[max(0, y0):y1, max(0, x0):x1] = False
    rows = np.nonzero(land.any(axis=1))[0]
    out = {"frame": path.replace("\\", "/")}
    if rows.size == 0:
        out["_why"] = "no land below the skyline"
        return out
    top, bot = rows.min(), rows.max()
    span = max(1, bot - top)
    ra, rb = int(top + band[0] * span), int(top + band[1] * span)
    m = land[ra:rb]
    px = lin[ra:rb][m]
    if px.shape[0] < 500:
        out["_why"] = "land region has too few pixels"
        return out

    lm = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
    med = np.median(lm)
    shadow = px[lm < med]
    lit = px[lm >= med]
    sm = np.median(shadow, axis=0)
    lmed = np.median(lit, axis=0)
    s_luma = 0.2126 * sm[0] + 0.7152 * sm[1] + 0.0722 * sm[2]
    l_luma = 0.2126 * lmed[0] + 0.7152 * lmed[1] + 0.0722 * lmed[2]

    out["shadow_median_linear"] = [round(float(v), 5) for v in sm]
    out["lit_median_linear"] = [round(float(v), 5) for v in lmed]
    out["shadow_luma"] = round(float(s_luma), 5)
    out["lit_luma"] = round(float(l_luma), 5)
    out["shadow_tint_R"] = round(float(sm[0] / s_luma), 4) if s_luma else None
    out["shadow_tint_G"] = round(float(sm[1] / s_luma), 4) if s_luma else None
    out["shadow_tint_B"] = round(float(sm[2] / s_luma), 4) if s_luma else None
    out["highlight_tint_R"] = round(float(lmed[0] / l_luma), 4) if l_luma else None
    out["highlight_tint_G"] = round(float(lmed[1] / l_luma), 4) if l_luma else None
    out["highlight_tint_B"] = round(float(lmed[2] / l_luma), 4) if l_luma else None
    b = out["shadow_tint_B"]
    out["acceptance"] = "shadow_tint_B in 1.10-1.60 (re-derived 2026-09-10, neutral WB)"
    out["verdict"] = "PASS" if (b is not None and 1.10 <= b <= 1.60) else "FAIL"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--greycard-station", default=None,
                    help="exclude this station's grey-card region "
                         "(R-GREYCARD) from the land region; applies to "
                         "every frame given, so give same-station frames")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    gc = None
    if a.greycard_station:
        import greycard
        gc = greycard.region_for(a.greycard_station)
        if gc is None:
            print("REFUSE: --greycard-station %r has no recorded region "
                  "-- run greycard --place first" % a.greycard_station)
            return 2
    rows = []
    for f in a.frames:
        r = measure(f, exclude_rect_px=gc)
        rows.append(r)
        n = os.path.splitext(os.path.basename(f))[0]
        if "shadow_tint_B" not in r:
            print("  %-22s -- %s" % (n, r.get("_why")))
            continue
        print("  %-22s shadow_tint B %.4f %-4s  (R %.2f G %.2f)  "
              "shadow_luma %.5f  lit_luma %.5f"
              % (n, r["shadow_tint_B"], r["verdict"], r["shadow_tint_R"],
                 r["shadow_tint_G"], r["shadow_luma"], r["lit_luma"]))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "Brief 2 Task 3: shadow B/luma over the WHOLE "
                                "land region below the skyline, split "
                                "lit/shadow at that region's own median. "
                                "Acceptance 1.10-1.60 (re-derived "
                                "2026-09-10, neutral WB).",
                       "rows": rows}, fh, indent=1)
        print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
