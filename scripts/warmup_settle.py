"""warmup_settle.py — how many RENDERED warm-up frames the bench needs.

    python scripts/warmup_settle.py --selftest
    python scripts/warmup_settle.py --date 2026-09-13 --station near_ground \
        --tags settle32 settle64 settle128 settle256

RULED 2026-09-13c. Two readings per count, because they settle at
different rates and the slower one governs:

  1. the GREY CARD on **PPI0** — the scene-linear instrument, a small
     patch of known albedo near the camera;
  2. the MEAN LUMA of a **300 m - 1 km depth crop** — far content, which
     is what streaming, virtual shadow maps and Lumen are still resolving
     while the near field already looks settled.

THE RULE: the settle count is the smallest N whose readings BOTH differ
from the NEXT count by less than 0.5%. The shipped
`render_warm_up_count` is that N plus 25% headroom, because a threshold
met exactly is a threshold with no margin, and the cost of one extra
rendered frame is milliseconds.

⛔ WHY THIS HAD TO BE MEASURED AT ALL. Until 2026-09-13 the bool gating
the count was FALSE, so every capture rendered ZERO warm-up frames while
its sidecar recorded an engine warm-up of 300 — a number that ticks the
game thread and renders nothing. 32 was then adopted as the count
because it is the ENGINE'S DEFAULT for the field, which is not evidence
about this world.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import exr_card  # noqa: E402
import greycard  # noqa: E402
from haze_metrics import decode_depth_m  # noqa: E402

LUMA = (0.2126, 0.7152, 0.0722)
FAR_BIN_M = (300.0, 1000.0)
TOL = 0.005          # 0.5%
HEADROOM = 1.25      # +25%
PPI0_CH = "FinalImagePPI0"


def read_one(date, tag, station):
    d = os.path.join(REPO, "_verify", "bench", date, "target_%s" % tag)
    exr = os.path.join(d, "%s.exr" % station)
    dep = os.path.join(d, "%sFinalImageSceneDepth.png" % station)
    if not os.path.exists(exr):
        raise SystemExit("missing %s" % exr)
    rgb = exr_card.read_rgb(exr, PPI0_CH)
    rect = greycard.inner_rect(
        json.load(open(greycard.REGIONS, encoding="utf-8"))
        ["stations"][station]["rect_px"])
    x0, y0, x1, y1 = rect
    crop = rgb[y0:y1, x0:x1, :]
    card = float(np.median(crop @ np.array(LUMA)))

    far = None
    far_px = 0
    if os.path.exists(dep):
        depth = decode_depth_m(dep)
        g = rgb @ np.array(LUMA)
        if g.shape == depth.shape:
            m = (depth >= FAR_BIN_M[0]) & (depth <= FAR_BIN_M[1])
            far_px = int(m.sum())
            if far_px > 1000:
                far = float(g[m].mean())
    return {"tag": tag, "card_ppi0": card, "far_mean_luma": far,
            "far_px": far_px}


def analyse(date, station, tags):
    rows = [read_one(date, t, station) for t in tags]
    # The count is the digits AFTER the last underscore. Taking every
    # digit in the tag read "s3_32" as 332 -- the run-series prefix is
    # digits too. A label that silently mis-parses is worse than one that
    # refuses, so a tag whose tail is not numeric raises.
    counts = []
    for r in rows:
        tail = r["tag"].rsplit("_", 1)[-1]
        digits = "".join(c for c in tail if c.isdigit())
        if not digits:
            raise SystemExit(
                "tag %r does not end in a warm-up count" % r["tag"])
        counts.append(int(digits))
    for r, c in zip(rows, counts):
        r["render_warm_up_count"] = c

    print("%-10s %8s %14s %16s %10s"
          % ("count", "card", "far mean luma", "far px", "vs next"))
    settle = None
    for i, r in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        note = ""
        if nxt:
            dc = abs(r["card_ppi0"] - nxt["card_ppi0"]) / max(
                nxt["card_ppi0"], 1e-9)
            if r["far_mean_luma"] is not None and nxt["far_mean_luma"]:
                df = abs(r["far_mean_luma"] - nxt["far_mean_luma"]) / max(
                    nxt["far_mean_luma"], 1e-9)
            else:
                df = None
            r["delta_card"] = round(dc, 5)
            r["delta_far"] = round(df, 5) if df is not None else None
            both = dc < TOL and (df is not None and df < TOL)
            note = "card %.3f%% far %s %s" % (
                100 * dc,
                ("%.3f%%" % (100 * df)) if df is not None else "n/a",
                "BOTH < 0.5%" if both else "")
            if both and settle is None:
                settle = r["render_warm_up_count"]
        print("%-10s %8.6f %14s %16d %10s"
              % (r["render_warm_up_count"], r["card_ppi0"],
                 ("%.6f" % r["far_mean_luma"]) if r["far_mean_luma"]
                 else "n/a", r["far_px"], note))

    out = {"station": station, "date": date, "rows": rows,
           "tolerance": TOL, "headroom": HEADROOM,
           "far_bin_m": list(FAR_BIN_M), "settle_count": settle}
    if settle is None:
        out["recommended_render_warm_up_count"] = None
        out["why"] = ("no count settled to better than 0.5% against the "
                      "next; the sweep needs to go higher before a value "
                      "can be fixed")
    else:
        out["recommended_render_warm_up_count"] = int(
            round(settle * HEADROOM))
    print()
    if settle is None:
        print("NO SETTLE within the sweep — %s" % out["why"])
    else:
        print("settles at %d; shipped count = %d x 1.25 = %d"
              % (settle, settle, out["recommended_render_warm_up_count"]))
    return out


def selftest():
    """The settle rule itself, on synthetic series."""
    fails = []

    def rule(cards, fars):
        s = None
        for i in range(len(cards) - 1):
            dc = abs(cards[i] - cards[i + 1]) / cards[i + 1]
            df = abs(fars[i] - fars[i + 1]) / fars[i + 1]
            if dc < TOL and df < TOL and s is None:
                s = i
        return s

    # card settles early, far settles late -> the LATE one must govern
    s = rule([1.00, 1.001, 1.001, 1.001], [1.0, 1.10, 1.001, 1.001])
    print("  card early, far late -> index %s  %s"
          % (s, "OK" if s == 2 else "WRONG"))
    if s != 2:
        fails.append("the slower reading did not govern")
    # nothing settles -> None
    s2 = rule([1.0, 1.2, 1.4, 1.7], [1.0, 1.2, 1.4, 1.7])
    print("  nothing settles      -> %s  %s"
          % (s2, "OK" if s2 is None else "WRONG"))
    if s2 is not None:
        fails.append("a drifting series reported a settle")
    # THE THRESHOLD IS SHARP, tested from BOTH sides.
    #
    # ⛔ NOT "exactly at the tolerance". Two attempts at that failed for
    # the same reason: the exact boundary is NOT REPRESENTABLE. 1.0/(1-TOL)
    # lands a hair below; 1.0+TOL is stored as 1.00499999999999989, so the
    # subtraction gives 0.00499999999999989 and also lands below. A test
    # that cannot construct the value it claims to test is not a test --
    # so this checks the two sides instead, which is what the rule's
    # behaviour actually has to be right about.
    s3 = rule([1.0 + TOL * 1.02, 1.0], [1.0, 1.0])
    print("  2%% ABOVE tolerance   -> %s  %s"
          % (s3, "OK" if s3 is None else "WRONG"))
    if s3 is not None:
        fails.append("a series above the tolerance counted as settled")
    s4 = rule([1.0 + TOL * 0.98, 1.0], [1.0, 1.0])
    print("  2%% BELOW tolerance   -> %s  %s"
          % (s4, "OK" if s4 == 0 else "WRONG"))
    if s4 != 0:
        fails.append("a series below the tolerance did not count as settled")
    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-09-13")
    ap.add_argument("--station", default="near_ground")
    ap.add_argument("--tags", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.tags:
        ap.print_help()
        return 1
    res = analyse(a.date, a.station, a.tags)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
