"""shade_card_pair.py — the R-SHADE acceptance: two cards, one blocker.

    python scripts/shade_card_pair.py --selftest
    python scripts/shade_card_pair.py --place
    python scripts/shade_card_pair.py --measure <near_ground.exr>

⭐ THE ACCEPTANCE, AND ITS WHITE POINT. The metric is

    shade_over_lit = (B/luma of the SHADED card) / (B/luma of the LIT card)

with Rec.709 luma (0.2126, 0.7152, 0.0722) on a SCENE-LINEAR EXR.

**BAND 2.065 - 2.998, DERIVED AT WHITE POINT 3438.6 K, SHADE FLOOR D6000**
by `research/brief3/scripts/shade_reference.py --white 3438.6 --shade
6000 10000` (selftest OK), which maps a D6000-D10000 skylight-shade range
through that white point:

    D6000 2.065  D6500 2.229  D7000 2.376  D7500 2.509
    D8000 2.628  D8500 2.734  D9000 2.831  D10000 2.998

⭐ WHY THE FLOOR IS D6000, NOT D6500 (R-SHADEBAND amendment 2026-09-15).
The shade sees skylight only, and hemispherical skylight CCT depends on
SUN ELEVATION: at a low sun the diffuse sky is less blue (warmer) than
the D6500 overhead-daylight default (Hernandez-Andres et al., "Color and
spectral analysis of daylight in southern Europe", J. Opt. Soc. Am. A 18
(2001) — low-sun hemispherical skylight sits warmer than D6500). This
recipe's sun is at 12 deg elevation (< ~30 deg), so the shade illuminant
floor moves from D6500 to D6000. `BAND_FLOOR_K` carries it.

THE BAND TRACKS THE RECIPE'S white_temp_k (R-SHADEBAND): whenever it
moves, `shade_reference.py --white <K> --shade <BAND_FLOOR_K> 10000` runs
FIRST and these constants are reset to its output. History: 2.184-2.940 @
3481.9 D6500 (R-SHADE 09-13); 2.254-3.029 @ 3415.7 D6500 (desk 09-15a);
2.229-2.998 @ 3438.6 D6500 (A-6 joint WB solve); now 2.065-2.998 @ 3438.6
D6000 (this amendment, low-sun floor). The recipe's FinalImage pair
2.587-3.764 is STRUCK -- FinalImage is not this band's domain.

THE WHITE POINT IS PART OF THE BAND. The band this replaces (1.10-1.60)
was derived at WB 5200 and then applied at 3481.9, which is how a
correct instrument produced a wrong verdict. A band quoted without its
white point is not a band.

⛔ WHY `shadow_tint_B` WAS REJECTED. It compared SHADOWED TERRAIN to LIT
TERRAIN, so its denominator moved with ground albedo: the grey card read
the light as neutral (R 1.026 / B 1.0455) while the metric reported 80%
blue excess. Same defect already ruled for `highlight_tint`. Two cards
of one KNOWN albedo remove the albedo from the ratio by construction.
`shade_over_sun.py` stays as a DIAGNOSTIC, never an acceptance.

WHY A BLOCKER RATHER THAN TERRAIN SHADOW: terrain shadow is cast by
ground whose albedo, orientation and bounce are uncontrolled. A blocker
card occludes the sun disc and nothing else.

Exit codes:
  0  measured and inside the band (or placed successfully)
  1  bad arguments / unreadable inputs
  3  placement refused, or the projected blocker overlaps a card
  4  measured and OUTSIDE the band
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import greycard  # noqa: E402  -- ONE camera model, one projection

REGIONS = os.path.join(REPO, "_verify", "bench", "shade_pair_regions.json")
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")

# Straight from shade_reference.py's printed output at white BAND_WHITE_K
# (3438.6 K -- see the docstring for the re-derivation history).
# ⛔ THIS IS THE SCENE-LINEAR BAND. It is derived from illuminant spectra,
# so it lives in linear light -- and the pair is MEASURED on FinalImage,
# which is the LOOK instrument and carries the tonemap pass's power law.
# The band must therefore be TRANSFORMED before it is compared to a
# FinalImage reading. See transformed_band().
BAND = (2.065, 2.998)
BAND_WHITE_K = 3438.6
# The shade illuminant FLOOR (bluest shade modelled). D6500 is the
# overhead-daylight default; a sun below ~30 deg warms hemispherical
# skylight, so the floor moves to D6000 (see docstring, Hernandez-Andres
# 2001). The ceiling stays D10000.
BAND_FLOOR_K = 6000
BAND_CEIL_K = 10000
BAND_SOURCE = ("research/brief3/scripts/shade_reference.py --white 3438.6 "
               "--shade 6000 10000 (D6000 low-sun floor, R-SHADEBAND "
               "amendment 2026-09-15)")

# Measured 2026-09-13 by scripts/tonemap_transfer.py on target_ppi0a,
# per-pixel FinalImage against the PPI0 pass: the tonemap pass is a
# straight power law (decade slope spread 0.041, no shoulder).
TRANSFER_EXPONENTS = {"R": 0.80398, "G": 0.76885, "B": 0.76536,
                      "luma": 0.76334}
TRANSFER_SOURCE = ("scripts/tonemap_transfer.py on "
                   "_verify/bench/2026-09-13/target_ppi0a/near_ground.exr")


def transformed_band(band=BAND, e=TRANSFER_EXPONENTS):
    """The scene-linear band, carried through the tonemap power law.

    The metric is a ratio of ratios, (B_s/L_s)/(B_l/L_l). If every
    channel maps as c' = k_c * c^e_c then

        measured' = (B_s/B_l)^e_B * (L_l/L_s)^e_L

    and the per-channel gains k_c cancel because each appears once above
    and once below. When e_B == e_L that collapses to (measured)^e, so
    the BAND transforms the same way -- band^e.

    ⛔ THAT COLLAPSE IS A CONDITION, NOT AN ASSUMPTION. It only holds
    while the blue and luma exponents agree; if they drift apart the
    ratio stops being a power of the linear ratio and no single
    transformed band is correct. Measured here: e_B 0.76536 vs e_luma
    0.76334, a difference of 0.002. The function REFUSES above 0.02.
    """
    eb, el = float(e["B"]), float(e["luma"])
    if abs(eb - el) > 0.02:
        raise RuntimeError(
            "e_B %.5f and e_luma %.5f differ by %.5f; above 0.02 the "
            "ratio-of-ratios is not a power of the linear ratio and the "
            "band cannot be transformed by a single exponent"
            % (eb, el, abs(eb - el)))
    return (round(band[0] ** eb, 4), round(band[1] ** eb, 4)), eb

DIST_CM = 300.0     # same as the lit card
SCALE = 0.3         # same as the lit card
# THE BLOCKER, sized from the card rather than guessed. The sun is
# effectively a directional source, so a blocker's shadow is its own
# cross-section: it only has to exceed the card's 30 cm, not scale with
# distance. 50 cm gives 10 cm of margin on every side. Placed at 60 cm,
# which at the card's 300 cm range puts it about 384 px from the card
# centre -- clear of the card's ~139 px half-width, and the overlap gate
# checks that rather than trusting this arithmetic.
# MEASURED, not estimated: at 60 cm the projected separation came out
# 300 px against a blocker half-width of 210 px and a card half-width of
# 139 px -- 49 px of overlap, which the gate refused. 90 cm scales the
# separation to ~450 px and a 40 cm cube drops the half-width to ~168,
# leaving ~280 px of clearance. The sun is directional, so moving the
# blocker along its ray costs nothing in shadow coverage; a 40 cm cube
# still exceeds the 30 cm card by 5 cm a side against a penumbra of
# under 1 cm at this range.
BLOCKER_CM = 90.0    # along the card->sun ray
BLOCKER_SCALE = 0.4  # 40 cm CUBE (the engine cube is 100 cm)

LUMA = (0.2126, 0.7152, 0.0722)


def rects_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def b_over_luma(rgb):
    lum = LUMA[0] * rgb[0] + LUMA[1] * rgb[1] + LUMA[2] * rgb[2]
    if lum <= 0.0:
        raise ValueError("card luma is %r -- a card that reads zero is not "
                         "a measurement, it is an occluded or missing card"
                         % lum)
    return rgb[2] / lum


def place(timeout, stations_arg=None):
    with open(RECIPE, encoding="utf-8") as fh:
        rec = json.load(fh)
    sun = rec["lighting"]["sun"]
    # The lit card's regions file decides which stations exist -- the pair
    # can only be placed where a lit card already is, since the two must
    # share one material and one camera.
    if not os.path.exists(greycard.REGIONS):
        print("REFUSE: %s is absent -- place the lit grey cards first"
              % os.path.relpath(greycard.REGIONS, REPO))
        return 3
    with open(greycard.REGIONS, encoding="utf-8") as fh:
        lit_all = json.load(fh)
    # NEAR_GROUND ONLY by default, as ruled: "two 18% grey cards in the
    # near_ground frame". It is also the only station whose geometry
    # admits the blocker -- at mid_slope the camera faces such that the
    # card-to-sun ray projects ONTO the card, and the overlap gate below
    # refuses it. Widening this needs a station whose sun-to-camera angle
    # is measured, not assumed.
    stations = [s for s in stations_arg if s in lit_all["stations"]] \
        if stations_arg else ["near_ground"]
    missing = [s for s in (stations_arg or []) if s not in lit_all["stations"]]
    if missing:
        print("REFUSE: no lit card at %s" % ", ".join(missing))
        return 3

    src = open(os.path.join(REPO, "scripts", "payloads",
                            "shade_pair_place.py"), encoding="utf-8").read()
    for k, v in (("__STATIONS__", json.dumps(stations)),
                 ("__SUN_AZ__", str(float(sun["azimuth_deg"]))),
                 ("__SUN_EL__", str(float(sun["elevation_deg"]))),
                 ("__DIST_CM__", str(DIST_CM)), ("__SCALE__", str(SCALE)),
                 ("__BLOCKER_CM__", str(BLOCKER_CM)),
                 ("__BLOCKER_SCALE__", str(BLOCKER_SCALE))):
        src = src.replace(k, v)

    import ue_exec
    code, parsed, raw = ue_exec.run(src, timeout=timeout,
                                    stage_name="ll_shade_pair", quiet=True)
    if parsed is None:
        print("REFUSE: payload produced no marker")
        print(raw[-1500:])
        return 3
    if not parsed.get("ok"):
        print("REFUSE: %s" % parsed.get("error"))
        print(parsed.get("trace", ""))
        return 3

    lit = lit_all["stations"]
    out = {"_what": ("R-SHADE card-pair regions, projected from READ-BACK "
                     "transforms through the ruled camera."),
           "band": list(BAND), "band_white_k": BAND_WHITE_K,
           "band_source": BAND_SOURCE,
           "camera_model": {"res": list(greycard.RES),
                            "hfov_deg": greycard.HFOV_DEG},
           "stations": {}}
    for st, row in parsed["stations"].items():
        cam = row["camera"]
        r_card = greycard.project_rect(cam, row["card"])
        r_block = greycard.project_rect(cam, row["blocker"])
        r_lit = lit[st]["rect_px"]
        # ⛔ THE CHECK THAT MAKES THE GEOMETRY A FACT. If the blocker lands
        # on either card it is occluding the CAMERA, not the sun, and the
        # measurement would read the blocker's own surface as a card.
        for name, other in (("shade card", r_card), ("lit card", r_lit)):
            if rects_overlap(r_block, other):
                print("REFUSE: at %s the blocker's projected rect %s "
                      "overlaps the %s %s -- it would occlude the camera, "
                      "not the sun." % (st, r_block, name, other))
                return 3
        out["stations"][st] = {
            "shade_rect_px": r_card, "lit_rect_px": r_lit,
            "blocker_rect_px": r_block,
            "sun_tocam_angle_deg": row.get("sun_tocam_angle_deg"),
            "card": row["card"], "blocker": row["blocker"],
            "camera": cam,
        }
        print("  %-14s shade %s  lit %s  blocker %s  (sun-to-camera %s deg)"
              % (st, r_card, r_lit, r_block,
                 row.get("sun_tocam_angle_deg")))
    os.makedirs(os.path.dirname(REGIONS), exist_ok=True)
    with open(REGIONS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print("wrote %s" % os.path.relpath(REGIONS, REPO))
    print("save: %r" % (parsed.get("save"),))
    return 0


PPI0_CHANNEL = "FinalImagePPI0"


def _median_rgb(exr_path, rect, channel=None):
    """Median linear RGB over a rect's INNER crop.

    The reader is `exr_card.read_rgb` -- the one already ruled for this
    project (OpenEXR 3.3.2; cv2 was tried and rejected). Imported rather
    than reimplemented so the pair is read by the same code that reads
    the single card, and a change to the reader cannot reach one and
    miss the other.
    """
    import numpy as np
    import exr_card
    arr = exr_card.read_rgb(exr_path, channel)
    x0, y0, x1, y1 = greycard.inner_rect(rect)
    crop = arr[y0:y1, x0:x1, :]
    if crop.size == 0:
        raise ValueError("empty crop for rect %r" % (rect,))
    return [float(np.median(crop[..., i])) for i in range(3)], crop


def measure_ppi0(exr_path, station):
    """⭐ THE ACCEPTANCE, on the SCENE-LINEAR instrument (2026-09-13d).

    PPI0 carries no white balance -- its lit card reads B/luma 0.4667 --
    so a shade ratio taken off it raw is in camera-native space and the
    band does not apply. The fix needs no grade and no capture: DIVIDE
    EACH CHANNEL BY THE LIT CARD'S OWN CHANNEL VALUE. The lit card is an
    18% NEUTRAL, so it IS the white reference; normalising by it is a von
    Kries adaptation performed with the reference that is physically in
    the frame.

    After that the lit card is exactly (1,1,1), its B/luma is 1, and the
    ratio reduces to the shaded card's normalised B/luma.

    THE BAND IS THEN THE UNTRANSFORMED `BAND` at `BAND_WHITE_K`, because
    this measurement is in linear light -- which is the whole point of
    moving the acceptance here. The FinalImage reading is recorded beside
    it and is no longer the acceptance.
    """
    import numpy as np
    with open(REGIONS, encoding="utf-8") as fh:
        reg = json.load(fh)
    if station not in reg["stations"]:
        print("REFUSE: no region for station %r" % station)
        return 1
    st = reg["stations"][station]

    lit_rgb, _lc = _median_rgb(exr_path, st["lit_rect_px"], PPI0_CHANNEL)
    sh_rgb, sh_crop = _median_rgb(exr_path, st["shade_rect_px"],
                                  PPI0_CHANNEL)
    if min(lit_rgb) <= 0.0:
        print("REFUSE: the lit card has a non-positive channel %r -- it "
              "cannot be a white reference" % (lit_rgb,))
        return 3
    norm_sh = [sh_rgb[i] / lit_rgb[i] for i in range(3)]
    norm_lit = [1.0, 1.0, 1.0]
    sh_bl = b_over_luma(norm_sh)
    lit_bl = b_over_luma(norm_lit)          # exactly 0.0722/1.0 ... = 1.0
    ratio = sh_bl / lit_bl
    lo, hi = BAND
    ok = lo <= ratio <= hi

    lit_lum = sum(LUMA[i] * lit_rgb[i] for i in range(3))
    sh_lum = sum(LUMA[i] * sh_rgb[i] for i in range(3))
    res = {
        "station": station, "exr": exr_path,
        "instrument": "PPI0 (the SCENE-LINEAR instrument, R-INSTRUMENTS)",
        "channel": PPI0_CHANNEL,
        "lit_median_linear_rgb": [round(v, 6) for v in lit_rgb],
        "shade_median_linear_rgb": [round(v, 6) for v in sh_rgb],
        "shade_normalised_by_lit_rgb": [round(v, 6) for v in norm_sh],
        "normalisation": ("each channel divided by the lit card's own "
                          "channel; the lit 18% neutral IS the white "
                          "reference (von Kries, reference in frame)"),
        "shade_over_lit_luma": round(sh_lum / lit_lum, 4)
        if lit_lum > 0 else None,
        "shade_over_lit_B_over_luma": round(ratio, 4),
        "band_scene_linear": list(BAND), "band_white_k": BAND_WHITE_K,
        "band_source": BAND_SOURCE,
        "band_transformed": False,
        "why_untransformed": ("PPI0 is upstream of the tonemap pass, so "
                              "the reading is already in linear light and "
                              "the scene-linear band applies directly"),
        "shade_crop_std_luma": round(float(np.std(
            sh_crop[..., 0] * LUMA[0] + sh_crop[..., 1] * LUMA[1]
            + sh_crop[..., 2] * LUMA[2])), 8),
        "verdict": "PASS" if ok else "FAIL",
    }
    print(json.dumps(res, indent=1))
    if res["shade_over_lit_luma"] and res["shade_over_lit_luma"] > 0.9:
        print("")
        print("⛔ the shaded card is %.1f%% as BRIGHT as the lit one -- the "
              "blocker is not occluding it. GEOMETRY failure, not a "
              "lighting reading." % (100.0 * res["shade_over_lit_luma"]))
        return 3
    return 0 if ok else 4


def measure(exr_path, station):
    import numpy as np
    with open(REGIONS, encoding="utf-8") as fh:
        reg = json.load(fh)
    if station not in reg["stations"]:
        print("REFUSE: no region for station %r" % station)
        return 1
    st = reg["stations"][station]

    lit_rgb, lit_crop = _median_rgb(exr_path, st["lit_rect_px"])
    sh_rgb, sh_crop = _median_rgb(exr_path, st["shade_rect_px"])
    lit_bl = b_over_luma(lit_rgb)
    sh_bl = b_over_luma(sh_rgb)
    ratio = sh_bl / lit_bl

    lit_lum = sum(LUMA[i] * lit_rgb[i] for i in range(3))
    sh_lum = sum(LUMA[i] * sh_rgb[i] for i in range(3))
    # THE BAND IS TRANSFORMED, because the reading is on FinalImage.
    # Comparing a FinalImage ratio against the scene-linear band was a
    # DOMAIN ERROR: it happened to pass, with far more apparent margin
    # than it had.
    (lo, hi), e_used = transformed_band()
    ok = lo <= ratio <= hi

    res = {
        "station": station, "exr": exr_path,
        "lit_rect_px": st["lit_rect_px"],
        "shade_rect_px": st["shade_rect_px"],
        "lit_median_linear_rgb": [round(v, 6) for v in lit_rgb],
        "shade_median_linear_rgb": [round(v, 6) for v in sh_rgb],
        "lit_luma": round(lit_lum, 6), "shade_luma": round(sh_lum, 6),
        "shade_over_lit_luma": round(sh_lum / lit_lum, 4)
        if lit_lum > 0 else None,
        "lit_B_over_luma": round(lit_bl, 4),
        "shade_B_over_luma": round(sh_bl, 4),
        "shade_over_lit_B_over_luma": round(ratio, 4),
        "instrument": "FinalImage (the LOOK instrument, R-INSTRUMENTS)",
        "band_scene_linear": list(BAND), "band_white_k": BAND_WHITE_K,
        "band_source": BAND_SOURCE,
        "band_applied": [lo, hi],
        "band_transform": ("scene-linear band ^ e_B, e_B = %.5f, valid "
                           "because e_B and e_luma agree to %.5f"
                           % (e_used,
                              abs(TRANSFER_EXPONENTS["B"]
                                  - TRANSFER_EXPONENTS["luma"]))),
        "transfer_source": TRANSFER_SOURCE,
        "shade_crop_std_luma": round(float(np.std(
            sh_crop[..., 0] * LUMA[0] + sh_crop[..., 1] * LUMA[1]
            + sh_crop[..., 2] * LUMA[2])), 6),
        "verdict": "PASS" if ok else "FAIL",
    }
    print(json.dumps(res, indent=1))
    # THE SHADED CARD MUST ACTUALLY BE SHADED. If the blocker missed, the
    # pair reads ~1.0 and that is a geometry failure wearing a lighting
    # verdict -- say so rather than reporting a number.
    if res["shade_over_lit_luma"] and res["shade_over_lit_luma"] > 0.9:
        print("")
        print("⛔ the shaded card is %.1f%% as BRIGHT as the lit one -- the "
              "blocker is not occluding it. This is a GEOMETRY failure, not "
              "a lighting reading; the ratio above means nothing."
              % (100.0 * res["shade_over_lit_luma"]))
        return 3
    return 0 if ok else 4


def selftest():
    """Directions that need no editor: the metric, and the overlap gate."""
    fails = []
    # 1 a neutral pair reads 1.0
    n = b_over_luma([0.5, 0.5, 0.5]) / b_over_luma([0.2, 0.2, 0.2])
    print("  neutral pair -> %.4f  %s" % (n, "OK" if abs(n - 1) < 1e-9
                                          else "WRONG"))
    if abs(n - 1) > 1e-9:
        fails.append("a neutral pair did not read 1.0")
    # 2 a bluer shade reads > 1
    b = b_over_luma([0.1, 0.1, 0.3]) / b_over_luma([0.2, 0.2, 0.2])
    print("  bluer shade  -> %.4f  %s" % (b, "OK" if b > 1 else "WRONG"))
    if b <= 1:
        fails.append("a bluer shade did not read above 1")
    # 3 zero luma REFUSES rather than dividing
    try:
        b_over_luma([0.0, 0.0, 0.0])
        print("  black card   -> DID NOT REFUSE  WRONG")
        fails.append("a black card did not refuse")
    except ValueError:
        print("  black card   -> refused         OK")
    # 4 the overlap gate
    cases = [((0, 0, 10, 10), (5, 5, 15, 15), True),
             ((0, 0, 10, 10), (10, 0, 20, 10), False),
             ((0, 0, 10, 10), (11, 11, 20, 20), False)]
    for a, b2, want in cases:
        got = rects_overlap(a, b2)
        print("  overlap %s vs %s -> %-5s %s"
              % (a, b2, got, "OK" if got == want else "WRONG"))
        if got != want:
            fails.append("overlap %s/%s read %s" % (a, b2, got))
    # 5 the band is the one the desk printed, at its white point
    # Re-derive from shade_reference at BAND_WHITE_K so the band can never
    # drift from its stated white point (R-SHADEBAND's "runs first" made
    # mechanical). If the recipe white point moved, this fails LOUDLY.
    import importlib.util as _ilu
    _srp = os.path.join(REPO, "research", "brief3", "scripts",
                        "shade_reference.py")
    _spec = _ilu.spec_from_file_location("shade_reference", _srp)
    _sr = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_sr)
    _lit, _lo, _hi = _sr.band(BAND_WHITE_K, BAND_FLOOR_K, BAND_CEIL_K)
    _match = round(_lo, 3) == BAND[0] and round(_hi, 3) == BAND[1]
    print("  scene-linear band %s at %.1f K  (shade_reference: %.3f-%.3f)  %s"
          % (list(BAND), BAND_WHITE_K, _lo, _hi, "OK" if _match else "WRONG"))
    if not _match:
        fails.append("band %s drifted from shade_reference at %.1f K (%.3f-%.3f)"
                     % (list(BAND), BAND_WHITE_K, _lo, _hi))
    tb, te = transformed_band()
    print("  transformed for FinalImage  -> %s at e_B %.5f" % (list(tb), te))
    if not (tb[0] < BAND[0] and tb[1] < BAND[1]):
        fails.append("an exponent below 1 must LOWER both band edges")
    try:
        transformed_band(e={"B": 0.80, "luma": 0.70})
        print("  divergent exponents         -> DID NOT REFUSE  WRONG")
        fails.append("divergent exponents did not refuse the transform")
    except RuntimeError:
        print("  divergent exponents         -> refused          OK")
    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", action="store_true")
    ap.add_argument("--measure", metavar="EXR",
                    help="measure on FinalImage (the LOOK instrument); the "
                         "band is transformed through the tonemap power "
                         "law. Recorded, but NOT the acceptance.")
    ap.add_argument("--measure-ppi0", metavar="EXR",
                    help="[*] THE ACCEPTANCE: measure on PPI0, the "
                         "scene-linear instrument, against the "
                         "UNTRANSFORMED band. Each channel is divided by "
                         "the lit card's own channel first, since the lit "
                         "18%% neutral is the white reference.")
    ap.add_argument("--station", default="near_ground")
    ap.add_argument("--stations", nargs="+", default=None,
                    help="stations to place the pair at. Default "
                         "near_ground -- the station the acceptance is "
                         "ruled for, and the only one whose blocker "
                         "geometry has been measured to clear the card.")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.place:
        return place(a.timeout, a.stations)
    if a.measure_ppi0:
        return measure_ppi0(a.measure_ppi0, a.station)
    if a.measure:
        return measure(a.measure, a.station)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
