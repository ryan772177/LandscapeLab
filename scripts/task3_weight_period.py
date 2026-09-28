"""task3_weight_period.py — WHERE does the weight-driven component sit?

    python scripts/task3_weight_period.py --selftest
    python scripts/task3_weight_period.py --frames <dir> --station ground \
        --channel FinalImageBaseColor

⭐ WHY THIS EXISTS, AND WHAT IT MAY NOT DO AGAIN.

`task3_layer_tables` searches a window centred on a PREDICTED period --
the layer's own tile. Right question for split (a), the texture repeat.
Wrong question for split (b): the weight-driven component has no
predicted period, so a window built around the tile can only report its
own edge. It did exactly that, and the edge was written up as "1.07 m,
the landscape's 1 m vertex pitch" -- right order of magnitude, tempting
physical story, and entirely an artefact of the search (LESSONS
2026-09-13d).

⛔ AN OPEN WINDOW DOES NOT FIX THIS, AND A PROMINENCE SWEEP DOES NOT
EITHER. Both were built and both were rejected on measurement:

  * OPEN WINDOW, take the max. The autocorrelation decays with lag, so
    the max over ANY window is at the window's short end. This would
    have reported "0.3 m" with exactly the confidence it once reported
    1.07 m.
  * SWEEP THE PREDICTED PERIOD, take the best local-peak prominence.
    Prominence is conditioned on the hypothesis: on a synthetic 1.0 m
    grating the sweep reported 2.013 m, because the autocorrelation of a
    repeat has peaks at every multiple and the window picks whichever
    multiple it is pointed at.

THE INSTRUMENT THAT WORKS: THE SPECTRUM OF THE AUTOCORRELATION. The
autocorrelation of a sinusoid is a COSINE at the same period, so its
spectrum is a SINGLE LINE -- every harmonic peak in the AC belongs to
that one line and they stop competing. A pure decay puts all its power
below the band and shows no line at all, which is the distinction split
(b) actually needs: a REPEAT versus a CORRELATION LENGTH.

WHERE the period comes from and WHAT its contrast is are then two
different instruments over the same data (NN8): the spectrum locates the
line, the autocorrelation at that lag gives the Michelson.

THE SIGNIFICANCE FLOOR IS DERIVED, NOT CHOSEN. Measured on controls
before the instrument was pointed at the world (probe, 2026-09-13):

    POSITIVE   grating 0.5 m   found 0.500 m   snr 3.59e6
               grating 1.0 m   found 1.000 m   snr 3.52e6
               grating 2.4 m   found 2.401 m   snr 3.17e6
               grating 4.0 m   found 4.001 m   snr 3.95e6
               grating 8.0 m   found 7.963 m   snr 3.66e5
               1.0 m at 1/3 the amplitude of the noise around it
                                found 1.000 m  snr 6.92e5
               1.0 m under an IRREGULAR mask
                                found 1.000 m  snr 1.96e6
    NEGATIVE   smoothed noise (decays, no repeat)     snr 18.06
               white noise under a striped mask       snr  9.82
               a pure smooth gradient                 snr  3.89

    floor = 100   -- 5.5x above the worst negative, 3600x below the
                     weakest positive. There is no tuning room in a gap
                     that wide, which is the point of measuring it.

THE CANDIDATE PITCHES, derived here rather than recalled:
  * OUR weightmap is 8129 square over 8128 m = 1.000 m/texel.
  * UE's own per-component weightmap is (127+1)*2 = 256 texels over a
    254 m component = 0.992 m/texel. It agrees with ours to 0.8%, so a
    line near 1 m CANNOT distinguish them and this says so rather than
    picking one.
  * The landscape COMPONENT is 254 m and its SECTION 127 m. Both are far
    outside the band; component-scale structure appears here as decay
    with no line, never as a period.

⛔ THE BAND'S TOP IS NOT 20 m AND THE REPORT SAYS SO. Resolving a period
needs several cycles inside the lag range, so the honest ceiling is
L/3 where L is the longest lag with enough masked overlap. It is
reported per measurement as `resolvable_max_m`; on a full-width crop it
lands near 17 m, not 20.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402
from task3_layer_tables import (BINS, CAMS, LUMA, MIN_PX, RECIPE,  # noqa: E402
                                layer_index_map, masked_autocorr,
                                masked_box_blur, world_xy)
import exr_card  # noqa: E402

BAND_M = (0.3, 20.0)
SNR_FLOOR = 100.0                # DERIVED -- see the control table above
WEIGHTMAP_TEXEL_M = 1.000        # ours: 8129 samples over 8128 m
UE_WEIGHTMAP_TEXEL_M = 254.0 / 256.0
COMPONENT_M = 254.0
SECTION_M = 127.0
MATCH_TOL = 0.15


def metres_per_px(dist_m, px_per_deg):
    """Ground metres subtended by ONE pixel at `dist_m`, small-angle."""
    return dist_m * (math.pi / 180.0) / px_per_deg


def name_the_pitch(period_m):
    """Which known pitch this matches. Returns EVERY match, never one."""
    hits = []
    for label, val in (("our weightmap texel (1.000 m)", WEIGHTMAP_TEXEL_M),
                       ("UE component weightmap texel (0.992 m)",
                        UE_WEIGHTMAP_TEXEL_M),
                       ("landscape section (127 m)", SECTION_M),
                       ("landscape component (254 m)", COMPONENT_M)):
        if abs(period_m - val) / val <= MATCH_TOL:
            hits.append(label)
    return hits


def correlation_length_px(ac, hi):
    """First lag at or below 1/e, interpolated. None if it never falls."""
    target = 1.0 / math.e
    for i in range(1, min(hi, len(ac) - 1) + 1):
        if not np.isfinite(ac[i]):
            continue
        if ac[i] <= target:
            prev = ac[i - 1] if np.isfinite(ac[i - 1]) else ac[i]
            if prev <= ac[i]:
                return float(i)
            return float(i - 1 + (prev - target) / (prev - ac[i]))
    return None


def analyse_one(gray, mask, dist_m, px_per_deg, band=BAND_M):
    """Open-band period search on one crop. Never returns a bare number."""
    mpp = metres_per_px(dist_m, px_per_deg)
    w = gray.shape[1]
    top_px = int(round(band[1] / mpp))
    L = min(w // 2, 3 * top_px)
    r = max(4, min(top_px, w // 4))
    res = {"metres_per_px": round(mpp, 5),
           "band_m": list(band),
           "max_lag_px": int(L),
           "resolvable_max_m": round(L / 3.0 * mpp, 2),
           "detrend_cutoff_m": round(r * mpp, 3),
           "detrend_clamped": bool(r < top_px),
           "snr_floor": SNR_FLOOR}
    if L < 24 or not mask.any():
        res["verdict"] = "NO VERDICT"
        res["why"] = ("crop gives only %d usable lags; that is not a search"
                      % L)
        return res
    hp = np.where(mask, gray - masked_box_blur(gray, mask, r), 0.0)
    hi_std = float(hp[mask].std())
    ac = masked_autocorr(hp, mask)
    if ac is None:
        res["verdict"] = "NO VERDICT"
        res["why"] = "no usable autocorrelation (flat or empty crop)"
        return res
    mean_l = float(gray[mask].mean())
    res["detrended_std"] = round(hi_std, 6)
    res["crop_mean_luma"] = round(mean_l, 6)
    cl = correlation_length_px(ac, L)
    res["correlation_length_px"] = round(cl, 2) if cl is not None else None
    res["correlation_length_m"] = (round(cl * mpp, 3)
                                   if cl is not None else None)

    a = np.nan_to_num(ac[:L + 1], nan=0.0)
    # ⭐ A CONTRAST NUMBER THAT EXISTS EVEN WHEN THERE IS NO PERIOD.
    # The split-(b) Michelson used to be read at a period, so a
    # "NO PERIOD" result reported no contrast at all -- and "there is
    # structure but I will not say how much" is not a measurement. This
    # is the same formula (NN0: same instrument, so the numbers compare)
    # evaluated at the CORRELATION LENGTH, which is the broadband
    # component's own scale rather than a period borrowed from a tile.
    if cl is not None and 0 <= int(round(cl)) < len(a):
        ac_cl = float(a[int(round(cl))])
        res["broadband_michelson"] = round(
            2.0 * hi_std * math.sqrt(max(ac_cl, 0.0)) / max(mean_l, 1e-6), 5)
        res["_broadband_michelson_at"] = ("the correlation length, %.3f m"
                                          % (cl * mpp))
    k = max(3, L // 8) | 1
    osc = (a - ndi.uniform_filter1d(a, k, mode="nearest")) * np.hanning(len(a))
    nfft = 1 << int(np.ceil(np.log2(8 * len(a))))
    S = np.abs(np.fft.rfft(osc, n=nfft)) ** 2
    f = np.fft.rfftfreq(nfft, d=1.0)
    per_m = np.divide(mpp, f, out=np.full_like(f, np.inf), where=f > 0)
    top = min(band[1], L / 3.0 * mpp)
    ok = (per_m >= band[0]) & (per_m <= top)
    if ok.sum() < 8:
        res["verdict"] = "NO VERDICT"
        res["why"] = "the band holds fewer than 8 spectral bins"
        return res
    floor = ndi.median_filter(S, size=max(9, int(ok.sum() // 6)) | 1,
                              mode="nearest")
    snr = np.where(floor > 0, S / np.maximum(floor, 1e-30), 0.0)
    idx = np.where(ok)[0]
    best = int(idx[np.argmax(snr[idx])])
    period_m = float(per_m[best])
    res["line_snr"] = round(float(snr[best]), 2)
    res["line_period_m"] = round(period_m, 4)
    if snr[best] < SNR_FLOOR:
        res["verdict"] = "NO PERIOD"
        res["period_m"] = None
        res["why"] = ("the strongest spectral line in 0.3-%.1f m stands "
                      "only %.1fx above the local noise floor, under the "
                      "derived %.0fx. This component is BROADBAND, not "
                      "periodic -- the correlation length is the number "
                      "that describes it." % (top, snr[best], SNR_FLOOR))
        return res
    lag = int(round(period_m / mpp))
    ac_at = float(a[lag]) if 0 <= lag < len(a) else 0.0
    mich = 2.0 * hi_std * math.sqrt(max(ac_at, 0.0)) / max(mean_l, 1e-6)
    res.update({"period_m": round(period_m, 4),
                "period_lag_px": lag,
                "autocorr_at_period": round(ac_at, 5),
                "michelson": round(mich, 5),
                "matches": name_the_pitch(period_m),
                "verdict": "PERIODIC"})
    return res


def analyse(frames, station, recipe_path=RECIPE, channel=None):
    rec = json.load(open(recipe_path, encoding="utf-8"))
    cams = json.load(open(CAMS, encoding="utf-8"))["cameras"]
    if station not in cams:
        raise SystemExit("no camera for station %r in %s" % (station, CAMS))
    cam = cams[station]
    exr = os.path.join(frames, "%s.exr" % station)
    dep = None
    for cand in ("%sFinalImageSceneDepth.png" % station,
                 "%s_SceneDepth.png" % station):
        p = os.path.join(frames, cand)
        if os.path.exists(p):
            dep = p
            break
    if not os.path.exists(exr) or dep is None:
        raise SystemExit("need %s and a SceneDepth png in %s" % (exr, frames))
    rgb = exr_card.read_rgb(exr, channel)
    depth = decode_depth_m(dep)
    if rgb.shape[:2] != depth.shape:
        raise SystemExit("beauty %s and depth %s differ"
                         % (rgb.shape[:2], depth.shape))
    h, w = depth.shape
    sky = depth > CEILING_M * 0.97
    px_per_deg = w / float(cam.get("fov_deg") or 90.0)
    wx, wy = world_xy(depth, cam, (w, h))
    lay, names = layer_index_map(wx, wy, rec)
    gray = (rgb[..., 0] * LUMA[0] + rgb[..., 1] * LUMA[1]
            + rgb[..., 2] * LUMA[2])
    out = {"_what": "Task 3 split (b): the weight-driven component. Open "
                    "band, NO predicted period; the spectrum of the "
                    "autocorrelation locates the line, the "
                    "autocorrelation gives its contrast.",
           "station": station, "frames": frames,
           "channel": channel or "RGBA (FinalImage)",
           "px_per_deg": round(px_per_deg, 3),
           "snr_floor": SNR_FLOOR,
           "candidate_pitches_m": {
               "our_weightmap_texel": WEIGHTMAP_TEXEL_M,
               "ue_component_weightmap_texel": round(UE_WEIGHTMAP_TEXEL_M, 4),
               "landscape_section": SECTION_M,
               "landscape_component": COMPONENT_M},
           "bins": []}
    for lo_m, hi_m in BINS:
        inbin = (~sky) & (depth >= lo_m) & (depth <= hi_m)
        row = {"bin_m": [lo_m, hi_m], "layers": []}
        for li, nm in enumerate(names):
            m = inbin & (lay == li)
            npx = int(m.sum())
            ent = {"layer": nm, "pixels": npx}
            if npx < MIN_PX:
                ent["verdict"] = "NO VERDICT"
                ent["why"] = ("only %d px, below the %d-px floor"
                              % (npx, MIN_PX))
                row["layers"].append(ent)
                continue
            dist = float(np.median(depth[m]))
            ys_, xs_ = np.where(m)
            y0, y1 = ys_.min(), ys_.max() + 1
            x0, x1 = xs_.min(), xs_.max() + 1
            ent["mean_distance_m"] = round(dist, 1)
            ent.update(analyse_one(gray[y0:y1, x0:x1], m[y0:y1, x0:x1],
                                   dist, px_per_deg))
            row["layers"].append(ent)
        out["bins"].append(row)
    out["cross_bin"] = cross_bin_check(out)
    return out


def cross_bin_check(out):
    """⭐ IS THE CORRELATION LENGTH A PROPERTY OF THE WORLD OR THE IMAGE?

    A world-fixed pitch -- the weightmap texel, a landscape component --
    is a fixed number of METRES and its apparent size in PIXELS must
    shrink with distance. A screen-space process -- filtering, mip
    selection, the pass's own resolution -- is a fixed number of PIXELS
    and its footprint in METRES must GROW with distance.

    The two bins are at different distances, so they separate these, and
    the separation is the whole reason this check exists: at the near bin
    Rock's correlation length lands on 1.002 m, which is the weightmap
    texel pitch to three decimals. That coincidence is exactly the shape
    of the 1.07 m error, and one bin cannot tell the difference. Two can.

    Whichever unit is CONSERVED across the bins names the domain. This
    returns the ratios and says which, and refuses to say when they are
    too close to call.
    """
    seen = {}
    for row in out["bins"]:
        for e in row["layers"]:
            if e.get("correlation_length_px") is None:
                continue
            seen.setdefault(e["layer"], []).append(
                (tuple(row["bin_m"]), e["correlation_length_px"],
                 e["correlation_length_m"]))
    res = []
    for layer, vals in sorted(seen.items()):
        if len(vals) < 2:
            continue
        px = [v[1] for v in vals]
        m = [v[2] for v in vals]
        spread_px = max(px) / max(min(px), 1e-9) - 1.0
        spread_m = max(m) / max(min(m), 1e-9) - 1.0
        ent = {"layer": layer,
               "bins": [list(v[0]) for v in vals],
               "correlation_length_px": px,
               "correlation_length_m": m,
               "spread_px": round(spread_px, 4),
               "spread_m": round(spread_m, 4)}
        if spread_px < spread_m / 2.0:
            ent["conserved"] = "PIXELS"
            ent["reading"] = ("constant in pixels (%.0f%% spread) while the "
                              "metre figure moves %.0f%%: this is a "
                              "SCREEN-SPACE property, so it is NOT the "
                              "weightmap texel, the section or the "
                              "component, whatever the near bin happens "
                              "to coincide with."
                              % (spread_px * 100, spread_m * 100))
        elif spread_m < spread_px / 2.0:
            ent["conserved"] = "METRES"
            ent["reading"] = ("constant in metres (%.0f%% spread) while the "
                              "pixel figure moves %.0f%%: a WORLD-FIXED "
                              "pitch. Compare it against the candidate "
                              "pitches." % (spread_m * 100, spread_px * 100))
        else:
            ent["conserved"] = "TOO CLOSE TO CALL"
            ent["reading"] = ("pixels move %.0f%% and metres %.0f%%; "
                              "neither is conserved clearly enough to name "
                              "a domain from two bins."
                              % (spread_px * 100, spread_m * 100))
        res.append(ent)
    return res


# ---------------------------------------------------------------------
def _grating(h, w, period_px, amp=0.06, base=0.35):
    x = np.arange(w)
    return base + amp * np.sin(2 * np.pi * x / period_px)[None, :] \
        * np.ones((h, 1))


def selftest():
    fails = []
    rng = np.random.default_rng(20260913)
    ppd, dist = 3840 / 90.0, 60.0
    mpp = metres_per_px(dist, ppd)
    H, W = 400, 4096
    full = np.ones((H, W), bool)

    # 1. PASS THE LEGITIMATE CASE, across the band and at a period that
    #    matches NOTHING known (2.4 m), so a match is never assumed.
    for tgt in (0.5, 1.0, 2.4, 4.0, 8.0):
        g = _grating(H, W, tgt / mpp)
        r = analyse_one(g, full, dist, ppd)
        if r.get("verdict") != "PERIODIC":
            fails.append("grating %.1f m: %r (%s)"
                         % (tgt, r.get("verdict"), r.get("why", "")[:60]))
        elif abs(r["period_m"] - tgt) / tgt > 0.03:
            fails.append("grating %.1f m found at %.3f m"
                         % (tgt, r["period_m"]))

    # 2. ⭐ THE FAILURE THIS INSTRUMENT EXISTS FOR. A monotone decay has
    #    NO period and must not be given one -- least of all at a band
    #    edge. This is the 1.07 m error, reproduced as a test.
    sm = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), 12.0)
    sm = 0.35 + 0.05 * sm / sm.std()
    r = analyse_one(sm, full, dist, ppd)
    if r.get("verdict") != "NO PERIOD":
        fails.append("monotone decay reported %r at %s m -- the "
                     "window-edge failure is back"
                     % (r.get("verdict"), r.get("period_m")))
    if r.get("correlation_length_m") is None:
        fails.append("monotone decay gave no correlation length, so it "
                     "reported nothing at all")

    # 3. NEGATIVE CONTROLS: noise under an irregular mask, and a pure
    #    gradient. Neither may manufacture a period.
    wn = 0.35 + 0.02 * rng.normal(0, 1, (H, W))
    mk = np.zeros((H, W), bool)
    mk[:, ::3] = True
    mk[:, 1::3] = True
    if analyse_one(wn, mk, dist, ppd).get("verdict") == "PERIODIC":
        fails.append("striped mask over noise manufactured a period")
    grad = 0.35 + 0.1 * (np.arange(W) / W)[None, :] * np.ones((H, 1))
    if analyse_one(grad, full, dist, ppd).get("verdict") == "PERIODIC":
        fails.append("a smooth gradient was called periodic")

    # 4. THE MASK MUST NOT MOVE THE PERIOD, and a weak line must still be
    #    found: 1.0 m under an irregular mask, and 1.0 m buried under
    #    noise three times its own amplitude.
    irr = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), 30.0)
    r = analyse_one(_grating(H, W, 1.0 / mpp), irr > np.percentile(irr, 45),
                    dist, ppd)
    if r.get("verdict") != "PERIODIC" or abs(r.get("period_m", 0) - 1) > 0.03:
        fails.append("irregular mask moved the 1.0 m period to %s"
                     % r.get("period_m"))
    buried = (_grating(H, W, 1.0 / mpp, amp=0.01)
              + 0.03 * rng.normal(0, 1, (H, W)))
    r = analyse_one(buried, full, dist, ppd)
    if r.get("verdict") != "PERIODIC" or abs(r.get("period_m", 0) - 1) > 0.03:
        fails.append("a 1.0 m line under 3x its amplitude in noise was "
                     "missed: %r at %s" % (r.get("verdict"),
                                           r.get("period_m")))

    # 5. BLOCK WHEN BROKEN: empty mask, constant field, tiny crop must
    #    all REFUSE -- not crash, not return a number.
    for name, g, m in (("empty mask", np.full((H, W), 0.35),
                        np.zeros((H, W), bool)),
                       ("constant field", np.full((H, W), 0.35), full),
                       ("tiny crop", np.zeros((50, 40)),
                        np.ones((50, 40), bool))):
        v = analyse_one(g, m, dist, ppd).get("verdict")
        if v != "NO VERDICT":
            fails.append("%s did not refuse: %r" % (name, v))

    # 6. THE CEILING IS REPORTED HONESTLY, not as the requested 20 m.
    r = analyse_one(_grating(H, W, 1.0 / mpp), full, dist, ppd)
    if not (10.0 < r["resolvable_max_m"] < 20.0):
        fails.append("resolvable_max_m %.1f is not a credible ceiling"
                     % r["resolvable_max_m"])

    # 7. name_the_pitch matches what it should and NOTHING else.
    if "our weightmap texel (1.000 m)" not in name_the_pitch(1.02):
        fails.append("1.02 m did not match the weightmap texel")
    if name_the_pitch(2.40):
        fails.append("2.40 m matched %r; it should match nothing"
                     % name_the_pitch(2.40))

    # 8. THE CROSS-BIN DISCRIMINATOR, all three directions. Synthetic
    #    bins, because the question is arithmetic, not rendering.
    def _bins(px_a, m_a, px_b, m_b):
        return {"bins": [
            {"bin_m": [30, 100], "layers": [
                {"layer": "L", "correlation_length_px": px_a,
                 "correlation_length_m": m_a}]},
            {"bin_m": [100, 300], "layers": [
                {"layer": "L", "correlation_length_px": px_b,
                 "correlation_length_m": m_b}]}]}

    got = cross_bin_check(_bins(35.5, 1.002, 32.2, 2.193))[0]["conserved"]
    if got != "PIXELS":
        fails.append("a pixel-conserved pair read %r" % got)
    got = cross_bin_check(_bins(35.5, 1.000, 15.0, 1.010))[0]["conserved"]
    if got != "METRES":
        fails.append("a metre-conserved pair read %r" % got)
    got = cross_bin_check(_bins(35.5, 1.000, 44.0, 1.240))[0]["conserved"]
    if got != "TOO CLOSE TO CALL":
        fails.append("an ambiguous pair was called %r" % got)
    # and it must not invent a verdict from ONE bin
    one = {"bins": [{"bin_m": [30, 100], "layers": [
        {"layer": "L", "correlation_length_px": 35.5,
         "correlation_length_m": 1.002}]}]}
    if cross_bin_check(one):
        fails.append("cross_bin_check gave a verdict from a single bin")

    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--channel", default=None)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        ap.error("--frames is required")
    res = analyse(a.frames, a.station, channel=a.channel)
    txt = json.dumps(res, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(txt + "\n")
        print("wrote", a.out)
    print("channel %s   station %s   snr floor %.0f"
          % (res["channel"], res["station"], res["snr_floor"]))
    for row in res["bins"]:
        print("  bin %s" % row["bin_m"])
        for e in row["layers"]:
            if "line_snr" not in e:
                print("    %-12s %-10s %s"
                      % (e["layer"], e["verdict"], e.get("why", "")[:66]))
                continue
            print("    %-12s %-9s line %7.3f m  snr %10.1f  bb-mich %-8s "
                  "corr-len %-7s %s"
                  % (e["layer"], e["verdict"], e["line_period_m"],
                     e["line_snr"], e.get("michelson") or e.get("broadband_michelson"),
                     e.get("correlation_length_m"),
                     ", ".join(e.get("matches") or [])
                     if e.get("verdict") == "PERIODIC" else ""))
    print("\n  CROSS-BIN: is the correlation length the WORLD's or the "
          "IMAGE's?")
    for e in res.get("cross_bin", []):
        print("    %-12s px %s (%.0f%%)  m %s (%.0f%%)  -> %s"
              % (e["layer"],
                 " ".join("%.1f" % v for v in e["correlation_length_px"]),
                 e["spread_px"] * 100,
                 " ".join("%.3f" % v for v in e["correlation_length_m"]),
                 e["spread_m"] * 100, e["conserved"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
