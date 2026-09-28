"""scan_tile_derive.py — per-scan tile derivation, against each scan's
own STATED physical size.

    python scripts/scan_tile_derive.py --probe <scan_probe.json> [--out J]

RULED 2026-09-12: tile size is PER LAYER, not the 5.03 m global.

TWO NUMBERS, and they answer different questions:

  DERIVED TILE   what the CAMERA needs. texel_budget: at hfov 90,
                 3840x2160, near 3 m, the eye resolves 814.9 texels/m,
                 so a 4096 albedo spans 4096/814.9 = 5.03 m at ~1 texel
                 per render pixel. Depends ONLY on resolution and
                 viewing distance -- not on what the scan photographed.

  STATED SIZE    what the scan IS. A 2x2 m Megascans surface tiled at
                 5.03 m is stretched 2.5x: every pebble in it renders
                 two and a half times life size. Tiled at its native 2 m
                 it is honest but repeats far more often.

THE TENSION IS REAL AND IS REPORTED, NOT AVERAGED. Where the repeat
becomes visible follows from the tile alone: repeat_cpd = d / (T*57.3),
and the eye's sensitive band is 1-8 cpd, so

    T = 5.03 m  ->  visible 288 - 2306 m
    T = 2.00 m  ->  visible 115 -  917 m

A 2 m tile puts its repeat INSIDE the band across the whole useful
ground range; a 5.03 m tile pushes it beyond where ground is legible.
That is the argument for the derived tile over the native size, and it
is an argument about ANGLES, not taste.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from texel_budget import csf_threshold_michelson  # noqa: E402

FOV_H, RES_W, RES_H = 90.0, 3840, 2160
NEAR_M = 3.0
PX_PER_DEG = RES_W / FOV_H
TEXELS_PER_M_NEEDED = PX_PER_DEG * (180.0 / math.pi) / NEAR_M
CSF_LO, CSF_HI = 1.0, 8.0


def parse_size(stated):
    """'2x2 m' or '1x1' -> 2.0 / 1.0 metres, or None."""
    if not stated:
        return None
    m = re.match(r"\s*([0-9.]+)\s*[xX]\s*([0-9.]+)", str(stated))
    if not m:
        return None
    return float(m.group(1))


def visible_band(tile_m):
    """Distances at which a tile's repeat sits in the eye's 1-8 cpd band."""
    return (tile_m * (180.0 / math.pi) * CSF_LO,
            tile_m * (180.0 / math.pi) * CSF_HI)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=os.path.join(
        REPO, "_verify", "intake", "2026-09-12", "scan_probe.json"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    probe = json.load(open(a.probe, encoding="utf-8"))["scans"]
    print("judgement camera: hfov %.0f, %dx%d, near %.0f m"
          % (FOV_H, RES_W, RES_H, NEAR_M))
    print("texels/m the eye resolves at the near distance: %.1f"
          % TEXELS_PER_M_NEEDED)
    print()
    print("%-50s %6s %8s %9s %9s %-18s %s"
          % ("scan", "albedo", "stated", "derived", "stretch", "repeat visible",
             "gate"))
    rows = []
    for s in probe:
        colour = (s["maps"].get("color") or [{}])[0]
        res = colour.get("width")
        stated = parse_size(s["physical_size"]["metres"])
        derived = (res / TEXELS_PER_M_NEEDED) if res else None
        stretch = (derived / stated) if (derived and stated) else None
        lo, hi = visible_band(derived) if derived else (None, None)
        row = {"scan": s["folder"], "albedo_px": res,
               "stated_physical_m": stated,
               "derived_tile_m": round(derived, 3) if derived else None,
               "texels_per_m_at_derived_tile":
                   round(res / derived, 1) if derived else None,
               "texels_per_m_needed": round(TEXELS_PER_M_NEEDED, 1),
               "stretch_vs_stated": round(stretch, 2) if stretch else None,
               "repeat_visible_from_m": round(lo, 0) if lo else None,
               "repeat_visible_to_m": round(hi, 0) if hi else None,
               "height_verdict": s.get("height_verdict")}
        # the CSF threshold at the far end of the useful ground band
        if derived:
            cpd_300 = 300.0 / (derived * (180.0 / math.pi))
            row["repeat_cpd_at_300m"] = round(cpd_300, 3)
            row["csf_threshold_at_300m"] = round(
                csf_threshold_michelson(cpd_300), 4)
            row["in_sensitive_band_at_300m"] = bool(CSF_LO <= cpd_300 <= CSF_HI)
        rows.append(row)
        print("%-50s %6s %8s %9s %9s %-18s %s"
              % (s["folder"], res or "?",
                 ("%.1f m" % stated) if stated else "NOT STATED",
                 ("%.2f m" % derived) if derived else "?",
                 ("%.2fx" % stretch) if stretch else "--",
                 ("%.0f-%.0f m" % (lo, hi)) if lo else "?",
                 "OK" if str(s.get("height_verdict", "")).startswith("OK")
                 else "REFUSED"))
    out = {"_what": "per-scan tile derivation, 2026-09-12",
           "camera": {"fov_h": FOV_H, "res": [RES_W, RES_H],
                      "near_m": NEAR_M,
                      "texels_per_m_needed": round(TEXELS_PER_M_NEEDED, 1)},
           "_note": ("derived tile depends ONLY on resolution and viewing "
                     "distance; stated size says whether the scan is being "
                     "stretched. Both are reported; neither is averaged."),
           "rows": rows}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
