"""exr_card.py — read the grey card in SCENE-LINEAR from an MRQ EXR.

    python scripts/exr_card.py --exr <f> --station <s> [--out J]
    python scripts/exr_card.py --selftest

RULED BY RYAN 2026-09-11. Every card reading before this was taken off a
DISPLAY-REFERRED frame, and the filmic curve is compressive there: a
ruled -1.5943 EV exposure step delivered 65% of itself, matching the
white-balance chain's 68%/40%. Both corrections passed through the same
tone curve. Measuring on the scene-linear pass removes the curve from
the loop, so a one-step correction should land.

THE PASS MUST ACTUALLY BE LINEAR, AND THAT IS CHECKED HERE, NOT ASSUMED.
`MoviePipelineColorSetting.bDisableToneCurve` is force-disabled when OCIO
is enabled (MoviePipelineColorSetting.h), so the flag can be set and
ignored. A display-referred EXR clamps at exactly 1.0 -- measured
2026-09-11 on the pre-ruling captures, RGBA max EXACTLY 1.00000 -- so a
frame whose maximum sits at 1.0 is REFUSED as "still tonemapped" rather
than measured.

Reader: OpenEXR 3.3.2 (docs/environment.md). cv2 5.0.0 was tried first
and cannot read EXR in its pip wheel.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS = os.path.join(REPO, "_verify", "bench", "greycard_regions.json")
TARGET = 0.18
TOL_FRAC = 0.05                 # ruled: +/-5% in scene-linear
LINEAR_MAX_FLOOR = 1.0001       # a linear frame must EXCEED display white


def read_rgb(path, channel=None):
    """(H, W, 3) float32 scene-linear RGB from an MRQ EXR.

    `channel` names an ADDITIONAL post-process pass stored as its own
    channel group in the same file -- MRQ writes e.g. `FinalImagePPI0`
    beside `RGBA` when a post-process material pass is enabled. Naming it
    explicitly matters: the default RGBA is the FINAL IMAGE, and reading
    a probe pass by accident (or the final image when a probe was asked
    for) would answer the wrong question with a plausible number.
    """
    import OpenEXR
    with OpenEXR.File(path) as f:
        ch = f.parts[0].channels
        if channel is not None:
            if channel not in ch:
                raise ValueError(
                    "no channel %r in %s; found %s"
                    % (channel, path, sorted(ch)))
            a = np.asarray(ch[channel].pixels, dtype=np.float32)
            return a[..., :3]
        if "RGBA" in ch:
            a = np.asarray(ch["RGBA"].pixels, dtype=np.float32)
            return a[..., :3]
        for k in ("RGB",):
            if k in ch:
                return np.asarray(ch[k].pixels, dtype=np.float32)[..., :3]
        need = ("R", "G", "B")
        if all(k in ch for k in need):
            return np.stack([np.asarray(ch[k].pixels, dtype=np.float32)
                             for k in need], axis=-1)
        raise ValueError("no RGB channels in %s; found %s"
                         % (path, sorted(ch)))


def measure(rgb, rect, tone_curve_readback=None):
    # SAME INNER CROP AS greycard, FROM greycard. The recorded rect is a
    # rotated card's AABB: measured 2026-09-11, 66,443 px of rect hold
    # only 23,976 px of card, so a median over the whole rect returns the
    # BACKGROUND and not the reference. Imported rather than re-stated so
    # the two tools cannot drift (NN24).
    from greycard import inner_rect
    x0, y0, x1, y1 = inner_rect(rect)
    patch = rgb[y0:y1, x0:x1, :]
    if patch.size == 0:
        return {"error": "card rect %s is empty for a %s frame"
                         % (rect, rgb.shape[:2])}
    # nanmax IGNORES NaN, so testing ITS result for finiteness is a guard
    # that can never fire -- caught by the selftest 2026-09-11. Ask the
    # ARRAY, not the statistic that was built to hide the answer.
    finite = bool(np.isfinite(rgb).all())
    frame_max = float(np.nanmax(rgb)) if finite else float("nan")
    out = {"rect_px": [int(v) for v in rect],
           "inner_px": [x0, y0, x1, y1],
           "pixels": int(patch.shape[0] * patch.shape[1]),
           "frame_max_linear": round(frame_max, 5) if finite else None}
    if not finite:
        return dict(out, error="frame holds non-finite values")
    # IS THIS FRAME LINEAR? A THREE-STATE QUESTION, NOT A THRESHOLD.
    #
    # The first draft demanded frame_max > 1.0 and REFUSED a frame that
    # read 0.89844. That test was wrong: EXPOSURE IS APPLIED BEFORE THE
    # TONE CURVE, so at this world's -3.5173 EV every scene value is
    # scaled by 2^-3.5173 = 0.0873 and a perfectly linear frame can max
    # well below 1.0. The threshold was assumed, not derived -- exactly
    # what this project keeps paying for.
    #
    # What IS sound:
    #   max > 1        UNBOUNDED -- proof of linear, display white cannot
    #                  be exceeded
    #   max == 1       clamped at display white -- proof of tonemapped
    #                  (the pre-ruling EXRs read EXACTLY 1.00000)
    #   max < 1        INCONCLUSIVE from pixels alone
    # so the last case defers to the ENGINE READ-BACK and refuses only
    # when that is absent too.
    if abs(frame_max - 1.0) < 1e-4:
        return dict(out, linear_evidence="max == 1.0", error=(
            "frame maximum is %.5f -- clamped at display white, so the "
            "tone curve was applied. Re-render with --linear and confirm "
            "OCIO is off (it force-disables bDisableToneCurve)." % frame_max))
    if frame_max > LINEAR_MAX_FLOOR:
        out["linear_evidence"] = ("frame max %.5f EXCEEDS display white, "
                                  "which a tonemapped frame cannot"
                                  % frame_max)
    elif tone_curve_readback is True:
        out["linear_evidence"] = (
            "frame max %.5f is below display white, which is INCONCLUSIVE "
            "on its own (exposure is applied before the curve, and this "
            "world sits at a large negative EV). Linearity rests on the "
            "engine read-back disable_tone_curve=True." % frame_max)
    else:
        return dict(out, error=(
            "frame maximum is %.5f -- below display white, which proves "
            "nothing either way once exposure is this negative, and there "
            "is no engine read-back of disable_tone_curve to fall back "
            "on. Pass --sidecar so linearity is established from the "
            "ENGINE rather than guessed from pixels." % frame_max))
    med = np.median(patch.reshape(-1, 3), axis=0)
    lum = float(0.2126 * med[0] + 0.7152 * med[1] + 0.0722 * med[2])
    out.update({
        "card_median_linear_rgb": [round(float(v), 6) for v in med],
        "card_luma_linear": round(lum, 6),
        "card_luma_std": round(float(np.std(
            0.2126 * patch[..., 0] + 0.7152 * patch[..., 1]
            + 0.0722 * patch[..., 2])), 6),
        "wb_ratio_R": round(float(med[0] / med[1]), 4) if med[1] else None,
        "wb_ratio_B": round(float(med[2] / med[1]), 4) if med[1] else None,
        "target": TARGET,
        "band": [round(TARGET * (1 - TOL_FRAC), 5),
                 round(TARGET * (1 + TOL_FRAC), 5)],
        "exposure_correction_ev": round(-float(np.log2(lum / TARGET)), 4)
        if lum > 0 else None,
    })
    out["verdict"] = ("PASS" if abs(lum - TARGET) <= TARGET * TOL_FRAC
                      else "FAIL")
    return out


def selftest():
    fails = []

    def check(name, cond):
        print("  %-56s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    rect = (10, 10, 40, 40)
    # 1 a frame whose card sits exactly on target PASSES
    img = np.zeros((60, 60, 3), dtype=np.float32)
    img[..., :] = 0.02
    img[5:50, 5:50, :] = TARGET
    img[0, 0, :] = 12.0                 # a highlight: the pass is unbounded
    r = measure(img, rect)
    print("    on target: luma %.5f corr %+.4f EV"
          % (r["card_luma_linear"], r["exposure_correction_ev"]))
    check("a card exactly on 0.18 PASSES", r["verdict"] == "PASS")
    check("...and asks for a 0 EV correction",
          abs(r["exposure_correction_ev"]) < 1e-3)

    # 2 a card off target FAILS and names the exact step
    img2 = img.copy()
    img2[5:50, 5:50, :] = TARGET * 2.0
    r2 = measure(img2, rect)
    print("    2x       : luma %.5f corr %+.4f EV"
          % (r2["card_luma_linear"], r2["exposure_correction_ev"]))
    check("a card 2x over FAILS", r2["verdict"] == "FAIL")
    check("...and the correction is exactly -1 EV",
          abs(r2["exposure_correction_ev"] + 1.0) < 1e-3)
    img3 = img.copy()
    img3[5:50, 5:50, :] = TARGET * 1.04          # inside +/-5%
    check("a card 4% over PASSES (inside the ruled band)",
          measure(img3, rect)["verdict"] == "PASS")
    img4 = img.copy()
    img4[5:50, 5:50, :] = TARGET * 1.06          # outside
    check("a card 6% over FAILS (outside the ruled band)",
          measure(img4, rect)["verdict"] == "FAIL")

    # 3 malformed / still-tonemapped REFUSES
    clamped = np.full((60, 60, 3), 0.1, dtype=np.float32)
    clamped[0, 0, :] = 1.0            # a tonemapped frame's ceiling
    r5 = measure(clamped, rect)
    check("a frame clamped at display white REFUSES",
          "error" in r5)
    check("...and says WHY", "tone curve" in r5.get("error", ""))
    # below display white with NO read-back is INCONCLUSIVE,
    # and must refuse rather than guess in either direction
    dim = np.full((60, 60, 3), 0.05, dtype=np.float32)
    dim[5:50, 5:50, :] = TARGET
    check("dim frame with no read-back refuses as inconclusive",
          "error" in measure(dim, rect))
    check("...the SAME frame passes once the engine says linear",
          measure(dim, rect, tone_curve_readback=True)
          .get("verdict") == "PASS")
    check("an empty rect refuses",
          "error" in measure(img, (5000, 5000, 5001, 5001)))
    nan = img.copy()
    nan[0, 1, 0] = np.nan
    check("a non-finite frame refuses", "error" in measure(nan, rect))

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exr")
    ap.add_argument("--station", default="near_ground")
    ap.add_argument("--sidecar", help="bench_run_*.json, for the ENGINE read-back of disable_tone_curve")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--channel", default=None,
                    help="read this EXR channel group instead of the "
                         "default RGBA. MRQ writes an additional "
                         "post-process pass as its own group, e.g. "
                         "FinalImagePPI0. RGBA is the FINAL IMAGE.")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.exr:
        sys.exit("REFUSE: --exr is required")

    regions = json.load(open(REGIONS, encoding="utf-8"))
    # the rects live under "stations"; the file also carries _what and
    # camera_model at the top level
    v = (regions.get("stations") or {}).get(a.station) or regions.get(a.station)
    if not isinstance(v, dict) or not v.get("rect_px"):
        sys.exit("REFUSE: no card rect for station %r in %s"
                 % (a.station, REGIONS))
    tcr = None
    if a.sidecar:
        sc = json.load(open(a.sidecar, encoding="utf-8"))
        # the payload keys this by JOB name ("Bench_target_near_ground"),
        # not by station, so match either form rather than silently
        # finding nothing and reporting "no read-back"
        _lr = sc.get("linear_readback") or {}
        lb = _lr.get(a.station) or next(
            (v for k, v in _lr.items() if a.station in k), {})
        tcr = lb.get("disable_tone_curve_readback")
        if lb.get("ocio_is_enabled_readback"):
            sys.exit("REFUSE: OCIO is ENABLED, which FORCE-DISABLES "
                     "bDisableToneCurve -- the frame is not linear "
                     "however the flag reads.")
    rgb = read_rgb(a.exr, a.channel)
    # EXACT SHAPE, both directions: a recorded rect sampled on a
    # different-sized frame returns a plausible number from the wrong
    # pixels (greycard's own 2026-09-10 audit finding).
    import greycard as _gc
    if rgb.shape[:2] != (_gc.RES[1], _gc.RES[0]):
        sys.exit("REFUSE: EXR is %dx%d, the recorded regions are for %dx%d "
                 "-- wrong resolution class"
                 % (rgb.shape[1], rgb.shape[0], _gc.RES[0], _gc.RES[1]))
    r = measure(rgb, [int(x) for x in v["rect_px"]], tcr)
    r["disable_tone_curve_readback"] = tcr
    r["station"] = a.station
    r["exr"] = a.exr
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "scene-linear grey card", "result": r}, fh,
                      indent=1)
        print("wrote %s" % a.out)
    if "error" in r:
        return 6
    return 0 if r["verdict"] == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
