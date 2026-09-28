"""shade_over_sun.py — shade blue RELATIVE TO SUNLIT, on the same terrain.

    python scripts/shade_over_sun.py <frames...> --greycard-station near_ground

⛔ DIAGNOSTIC ONLY. NOT AN ACCEPTANCE. RULED 2026-09-12b.
The acceptance is `scripts/shade_card_pair.py`: two 18% cards of one
KNOWN albedo, one sunlit and one occluded by a blocker cube, metric
(B/luma shade)/(B/luma lit) on a scene-linear EXR, against the band in
`shade_card_pair.BAND` at `BAND_WHITE_K`, shade floor `BAND_FLOOR_K`.
The band TRACKS the recipe white point AND the sun-elevation floor, so
read it from that module -- no value is quoted here, on purpose.

This tool still measures TERRAIN, so its denominator moves with ground
albedo -- the defect that sank `shadow_tint_B`. It is kept because a
terrain-side reading is useful for SPOTTING a change, and because its
disagreement with the card pair is itself evidence. MEASURED 2026-09-13
on the same world: the card pair reads 2.2598, in band, while the lit
card confirms the light is neutral at B/luma 1.0055. A terrain number
from this tool that contradicts that is measuring the ground.

RULED BY RYAN 2026-09-12: re-derive the shadow band against the current
content. This is that re-derivation -- of the METRIC, not the band,
because the band cannot be re-derived against our own content without
fitting the acceptance to the artefact.

⛔ WHAT IS WRONG WITH shadow_tint_B. It is B_shadow / luma_shadow: a
property of whatever SURFACE happens to lie in shade. It presumes a
NEUTRAL shaded surface and there is none -- so it moves when the terrain
changes even though the light has not.

MEASURED PROOF, 2026-09-12: the five-layer material replaced WildGrass
and Rock051 with warm litter (linear luma 0.2760) and grey scree
(0.2228) across much of near_ground's land region, and B fell from
1.1243 (Brief 2b, 2026-09-10) to 0.7674 at IDENTICAL grade and lighting
-- 32%. Meanwhile the GREY CARD in the same frame reads highlight_tint
R 1.026 / B 1.0455, PASS: on a known 18% neutral plane the light is
neutral to within 6%. Both cannot describe the illuminant. The card is
right and shadow_tint_B is measuring albedo.

THIS IS THE SIBLING METRIC'S DEFECT, ALREADY RULED. `highlight_tint`
"remains a measurement of the meadow's albedo ... its instrument is now
the GREY CARD (ruled 2026-09-10)", because it "presumes a neutral sunlit
surface". shadow_tint_B is the same error one step over, and the card
cannot fix it the same way because the card is in SUN, not shade.

THE FIX: DIVIDE BY THE SUNLIT HALF OF THE SAME TERRAIN.

    shade_over_sun_B = (B_shadow/luma_shadow) / (B_lit/luma_lit)

Surface albedo appears in BOTH terms and cancels to first order. So does
any GLOBAL colour transform -- the white balance, the grade -- because it
scales shadow and lit alike. What does NOT cancel is the difference
between the two ILLUMINANTS: sun versus sky. That difference is the
thing the acceptance was always trying to name.

THE DISCRIMINATING TEST, and it is run on every invocation: the white
balance swing that moved shadow_tint_B by 2.35x must move this ratio
hardly at all, while the sky-intensity change must still move it. A
metric that cancels the grade and keeps the sky signal is measuring the
light; one that moves with both is measuring neither.

CANCELLATION IS FIRST-ORDER, NOT EXACT. The median split separates by
LUMINANCE, and luminance correlates with albedo, so the shaded and
sunlit populations are not the same surfaces in the same proportions.
The residual is reported rather than assumed away.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import greycard  # noqa: E402
import shadow_tint as st  # noqa: E402


def ratio(path, exclude_rect_px=None):
    m = st.measure(path, exclude_rect_px=exclude_rect_px)
    if "shadow_median_linear" not in m:
        return {"frame": path, "_why": m.get("_why", "not measurable")}
    sm = m["shadow_median_linear"]
    lm = m["lit_median_linear"]
    s_luma, l_luma = m["shadow_luma"], m["lit_luma"]
    if not s_luma or not l_luma:
        return {"frame": path, "_why": "zero luma in one population"}
    out = {"frame": os.path.basename(os.path.dirname(path)) or path}
    for i, ch in enumerate("RGB"):
        s = sm[i] / s_luma
        l = lm[i] / l_luma
        out["shadow_" + ch] = round(s, 4)
        out["lit_" + ch] = round(l, 4)
        out["ratio_" + ch] = round(s / l, 4) if l else None
    out["shadow_luma"] = s_luma
    out["lit_luma"] = l_luma
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--greycard-station")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    rect = None
    rect_error = None
    if a.greycard_station:
        try:
            rect = greycard.inner_rect(
                greycard.card_rect_px(a.greycard_station))
        except Exception as exc:
            # The exclusion was explicitly requested; dropping it silently lets
            # the grey card contaminate the terrain populations. Say so loudly.
            rect_error = str(exc)
            print("WARNING: --greycard-station %s given but its rect could not "
                  "be resolved (%s); the grey card is NOT excluded and will "
                  "contaminate the terrain medians."
                  % (a.greycard_station, exc))

    rows = []
    print("%-22s %8s %8s %8s   %8s %8s"
          % ("frame", "shadowB", "litB", "RATIO_B", "sh_luma", "lit_luma"))
    for f in a.frames:
        r = ratio(f, exclude_rect_px=rect)
        rows.append(r)
        if "_why" in r:
            print("%-22s  %s" % (r["frame"], r["_why"]))
            continue
        print("%-22s %8.4f %8.4f %8.4f   %8.5f %8.5f"
              % (r["frame"], r["shadow_B"], r["lit_B"], r["ratio_B"],
                 r["shadow_luma"], r["lit_luma"]))

    good = [r for r in rows if "ratio_B" in r]
    if len(good) > 1:
        bs = [r["shadow_B"] for r in good]
        rs = [r["ratio_B"] for r in good]
        print()
        print("SPREAD ACROSS THE SERIES (max/min), the discriminating test "
              "(n=%d frames):" % len(good))
        if min(bs) > 0 and min(rs) > 0:
            print("  shadow_tint_B      %.3fx" % (max(bs) / min(bs)))
            print("  shade_over_sun_B   %.3fx" % (max(rs) / min(rs)))
            print("  A metric that cancels the grade and keeps the sky signal")
            print("  is measuring the LIGHT; one that moves with both is not.")
        else:
            print("  NOT computed: a zero shadow_B/ratio_B in the series makes "
                  "the max/min ratio undefined.")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "shade blue relative to sunlit, same terrain",
                       "greycard_rect_error": rect_error,
                       "n_measured": len(good), "rows": rows}, fh, indent=1)
        print("\nwrote %s" % a.out)
    # A diagnostic that measured NOTHING must not exit 0.
    if not good:
        print("REFUSE: no frame produced a measurable ratio.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
