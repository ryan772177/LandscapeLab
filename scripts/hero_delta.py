"""hero_delta.py -- per-depth-bin luma delta between two captures (R-HERO, closure A-3).

    python scripts/hero_delta.py --baseline <a.exr> --test <b.exr> \
        --depth <SceneDepth png> [--exclude x0 y0 x1 y1] --out <json>
    python scripts/hero_delta.py --selftest

Question ruled by R-HERO: do the three HeroStage_* DirectionalLights
reach the bench frame? Two captures differing ONLY in the lights'
affects_world, same station, same construction, same session. This tool
reports, PER DEPTH BIN, the mean and max |delta luma| as a percentage of
the bin's baseline mean luma.

THE TRIGGER, stated here so the verdict is mechanical: a bin with
>= 500 pixels whose MEAN delta is >= 0.5% triggers the ruling (lights
disabled for the bench). The max is reported beside it as the tail
statistic but does not trigger alone -- a single-pixel speckle at
temporal 1 is aliasing, not a light.

Instruments: luma is Rec.709 on the scene-linear EXR RGBA channels
(instrument finalimage_linear -- the tone-curve-disabled FinalImage);
depth is the log-encoded SceneDepth PNG decoded by
haze_metrics.decode_depth_m, the same decode every haze measurement
uses. Depth >= ceiling is the SKY row, reported separately.

Rule 13: every row carries its pixel count; a zero-pixel bin reports
"insufficient", never a delta of 0.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402

BINS_M = [(0.0, 10.0), (10.0, 30.0), (30.0, 100.0), (100.0, 300.0),
          (300.0, 1000.0), (1000.0, CEILING_M * 0.999)]
MIN_PIXELS = 500
TRIGGER_MEAN_PCT = 0.5


def luma709(rgb):
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1]
            + 0.0722 * rgb[..., 2])


def compare(la, lb, dm, exclude_rect_px=None):
    """Core comparison on arrays, separated from IO so the selftest can
    construct its inputs analytically."""
    if la.shape != lb.shape or la.shape != dm.shape:
        raise ValueError("shape mismatch: baseline %s test %s depth %s"
                         % (la.shape, lb.shape, dm.shape))
    excl = np.zeros(la.shape, dtype=bool)
    if exclude_rect_px:
        x0, y0, x1, y1 = exclude_rect_px
        excl[max(0, y0):y1, max(0, x0):x1] = True
    delta = np.abs(la - lb)
    rows = []
    trigger = False
    masks = [((dm >= lo) & (dm < hi), [lo, hi]) for lo, hi in BINS_M]
    masks.append(((dm >= CEILING_M * 0.999), "sky"))
    for m, label in masks:
        m = m & ~excl
        n = int(m.sum())
        row = {"bin_m": label, "pixels": n}
        if n < MIN_PIXELS:
            row["verdict"] = "insufficient (< %d px)" % MIN_PIXELS
            rows.append(row)
            continue
        base_mean = float(la[m].mean())
        if base_mean <= 0.0:
            row["verdict"] = "baseline mean luma 0 -- cannot normalise"
            rows.append(row)
            continue
        mean_pct = 100.0 * float(delta[m].mean()) / base_mean
        max_pct = 100.0 * float(delta[m].max()) / base_mean
        hit = mean_pct >= TRIGGER_MEAN_PCT
        trigger = trigger or hit
        row.update({"baseline_mean_luma": round(base_mean, 6),
                    "mean_delta_pct": round(mean_pct, 4),
                    "max_delta_pct": round(max_pct, 4),
                    "triggers": bool(hit)})
        rows.append(row)
    return {"rows": rows, "trigger": trigger,
            "trigger_rule": "mean_delta_pct >= %.1f in any bin with >= %d px"
                            % (TRIGGER_MEAN_PCT, MIN_PIXELS)}


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-52s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and cond

    h, w = 64, 64
    dm = np.full((h, w), 50.0)          # everything in the 30-100 m bin
    dm[:8, :] = CEILING_M               # a sky band
    la = np.full((h, w), 0.2)
    lb = la.copy()
    r = compare(la, lb, dm)
    check("identical frames trigger nothing", r["trigger"] is False)
    row = next(x for x in r["rows"] if x["bin_m"] == [30.0, 100.0])
    check("identical frames read 0.0 mean delta",
          row["mean_delta_pct"] == 0.0)
    lb2 = la * 1.01                     # a uniform 1% lift
    r2 = compare(la, lb2, dm)
    row2 = next(x for x in r2["rows"] if x["bin_m"] == [30.0, 100.0])
    check("a 1.0% uniform lift measures 1.0%",
          abs(row2["mean_delta_pct"] - 1.0) < 1e-6)
    check("...and triggers at the 0.5% rule", r2["trigger"] is True)
    lb3 = la.copy()
    lb3[32, 32] += 0.2                  # one bright pixel: 100% at one px
    r3 = compare(la, lb3, dm)
    row3 = next(x for x in r3["rows"] if x["bin_m"] == [30.0, 100.0])
    check("a single-pixel speckle does NOT trigger the mean rule",
          r3["trigger"] is False and row3["max_delta_pct"] > 50.0)
    empty = next(x for x in r["rows"] if x["bin_m"] == [0.0, 10.0])
    check("an empty bin refuses rather than reading 0 (rule 13)",
          "insufficient" in empty.get("verdict", ""))
    r4 = compare(la, lb3, dm, exclude_rect_px=(0, 0, w, h))
    check("a full-frame exclusion leaves only insufficient rows",
          all("verdict" in x for x in r4["rows"]))
    print("selftest %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline")
    ap.add_argument("--test")
    ap.add_argument("--depth")
    ap.add_argument("--exclude", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.baseline and a.test and a.depth):
        ap.error("--baseline, --test and --depth are required (or --selftest)")
    from exr_card import read_rgb
    la = luma709(np.asarray(read_rgb(a.baseline), dtype=np.float64))
    lb = luma709(np.asarray(read_rgb(a.test), dtype=np.float64))
    dm = decode_depth_m(a.depth)
    r = compare(la, lb, dm, exclude_rect_px=tuple(a.exclude) if a.exclude else None)
    r["_what"] = "R-HERO discriminator: |delta luma| per depth bin, % of baseline bin mean"
    r["baseline"] = os.path.abspath(a.baseline)
    r["test"] = os.path.abspath(a.test)
    r["depth"] = os.path.abspath(a.depth)
    r["instrument"] = "finalimage_linear"
    print(json.dumps(r, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
