"""tonemap_transfer.py — the tonemap pass's transfer, measured per pixel.

    python scripts/tonemap_transfer.py --selftest
    python scripts/tonemap_transfer.py --exr <near_ground.exr>

⭐ WHAT THIS SETTLES. `MoviePipelineColorSetting.disable_tone_curve` is
the property the SETTER wrote; it is not proof the tonemapper honoured
it (rule 12). The honest test is the transfer itself: the SAME FRAME
carries the buffer BEFORE the tonemap pass (channel `FinalImagePPI0`,
written by a pass-through material at BL_SCENE_COLOR_AFTER_DOF) and
AFTER it (channel `RGBA`). Every pixel is one sample of the pass's
input/output relation.

    STRAIGHT in log-log  -> a POWER LAW. The film curve is OFF, and the
                            residual slope is some other op.
    BENT, esp. a rolled  -> the FILM CURVE IS ON. A filmic curve's whole
    top decade              purpose is a shoulder, and a shoulder is a
                            bend that a power law cannot produce.

so the shape of the top decade is the discriminator, not the fit quality
in the middle where any smooth curve looks straight over one decade.

PER CHANNEL AS WELL AS LUMA, because a per-channel power is what a
colour-grading contrast would be, and a luma-only fit cannot see a
channel spread.

⛔ PIXELS ARE NOT INDEPENDENT SAMPLES of the transfer if anything spatial
sits between the two taps -- bloom moves energy sideways. Bloom IS in
this chain, so the fit is reported with its residual and the bloom
caveat rather than as a clean law; the DISCRIMINATOR (bend vs straight)
survives it because bloom cannot manufacture a shoulder.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

LUMA = (0.2126, 0.7152, 0.0722)
LIN_CH = "FinalImagePPI0"      # before the tonemap pass
OUT_CH = "RGBA"                # after it
FLOOR = 1e-4                   # below this the float16 output quantises


def read_pair(path):
    import OpenEXR
    with OpenEXR.File(path) as f:
        ch = f.parts[0].channels
        for need in (LIN_CH, OUT_CH):
            if need not in ch:
                raise SystemExit(
                    "%s has no %r channel; found %s -- this needs a capture "
                    "made with --pp-pass PPI0=/Game/Bench/M_PPI0_Passthrough"
                    % (path, need, sorted(ch)))
        a = np.asarray(ch[LIN_CH].pixels, dtype=np.float64)[..., :3]
        b = np.asarray(ch[OUT_CH].pixels, dtype=np.float64)[..., :3]
    return a, b


def fit_loglog(x, y, name, decades=None):
    """Least-squares slope of log2(y) on log2(x), with its residual."""
    m = (x > FLOOR) & (y > FLOOR) & np.isfinite(x) & np.isfinite(y)
    if decades is not None:
        lo, hi = decades
        m &= (x >= lo) & (x < hi)
    n = int(m.sum())
    if n < 1000:
        return {"name": name, "n": n, "slope": None,
                "why": "fewer than 1000 usable pixels"}
    lx = np.log2(x[m])
    ly = np.log2(y[m])
    A = np.vstack([lx, np.ones_like(lx)]).T
    (slope, intercept), res, _rank, _sv = np.linalg.lstsq(A, ly, rcond=None)
    pred = slope * lx + intercept
    resid = ly - pred
    return {"name": name, "n": n,
            "slope": round(float(slope), 5),
            "intercept": round(float(intercept), 5),
            "rms_residual_ev": round(float(np.sqrt((resid ** 2).mean())), 5),
            "max_abs_residual_ev": round(float(np.abs(resid).max()), 4),
            "x_range": [round(float(x[m].min()), 6),
                        round(float(x[m].max()), 6)]}


def analyse(path):
    lin, out = read_pair(path)
    lin_l = lin @ np.array(LUMA)
    out_l = out @ np.array(LUMA)
    res = {"exr": path, "linear_channel": LIN_CH, "output_channel": OUT_CH,
           "fits": [], "decades": [], "per_channel_exponents": {}}

    res["fits"].append(fit_loglog(lin_l, out_l, "luma (all pixels)"))
    for i, c in enumerate("RGB"):
        f = fit_loglog(lin[..., i], out[..., i], "channel %s" % c)
        res["fits"].append(f)
        res["per_channel_exponents"][c] = f.get("slope")

    # ⭐ THE DISCRIMINATOR: fit each decade of input SEPARATELY. A power
    # law has the SAME slope in every decade. A film curve's shoulder
    # makes the top decade shallower, and its toe makes the bottom one
    # steeper -- so a monotone drift in slope across decades IS the bend.
    edges = [1e-4, 1e-3, 1e-2, 1e-1, 1e0, 1e1]
    for lo, hi in zip(edges[:-1], edges[1:]):
        f = fit_loglog(lin_l, out_l, "luma %g..%g" % (lo, hi), (lo, hi))
        res["decades"].append(f)
    good = [d for d in res["decades"] if d.get("slope") is not None]
    if len(good) >= 2:
        slopes = [d["slope"] for d in good]
        res["decade_slope_spread"] = round(max(slopes) - min(slopes), 5)
        res["top_decade_slope"] = good[-1]["slope"]
        res["bottom_decade_slope"] = good[0]["slope"]
        res["verdict"] = (
            "STRAIGHT — power law, film curve OFF"
            if res["decade_slope_spread"] < 0.05 else
            "BENT — slope varies across decades; a film curve is ON")
    return res


def selftest():
    """A synthetic power law must read straight; a filmic curve, bent."""
    fails = []
    rng = np.random.default_rng(0)
    x = 10 ** rng.uniform(-4, 1, 400000)

    y = 0.9 * x ** 0.73
    f = fit_loglog(x, y, "pure power law")
    ok = abs(f["slope"] - 0.73) < 1e-6 and f["rms_residual_ev"] < 1e-9
    print("  pure power law 0.73 -> slope %.5f rms %.2e  %s"
          % (f["slope"], f["rms_residual_ev"], "OK" if ok else "WRONG"))
    if not ok:
        fails.append("a pure power law did not read as its own exponent")

    # ACES-ish shoulder: saturating, so the TOP decade must go shallow.
    yf = x / (1.0 + x)
    hi = fit_loglog(x, yf, "filmic top", (1e0, 1e1))
    lo = fit_loglog(x, yf, "filmic bottom", (1e-4, 1e-3))
    bent = (lo["slope"] - hi["slope"]) > 0.2
    print("  saturating curve   -> bottom %.4f top %.4f  %s"
          % (lo["slope"], hi["slope"], "OK" if bent else "WRONG"))
    if not bent:
        fails.append("a saturating curve did not read as bent")

    # and a power law is NOT called bent
    yp = 0.5 * x ** 0.8
    hi2 = fit_loglog(x, yp, "power top", (1e0, 1e1))
    lo2 = fit_loglog(x, yp, "power bottom", (1e-4, 1e-3))
    flat = abs(lo2["slope"] - hi2["slope"]) < 0.01
    print("  power law across decades -> %.4f vs %.4f  %s"
          % (lo2["slope"], hi2["slope"], "OK" if flat else "WRONG"))
    if not flat:
        fails.append("a power law read as bent across decades")

    if fails:
        print("\nSELFTEST FAIL")
        for f2 in fails:
            print("  - %s" % f2)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exr")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.exr:
        ap.print_help()
        return 1
    res = analyse(a.exr)
    print(json.dumps(res, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
