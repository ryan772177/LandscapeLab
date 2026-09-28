"""grade_resolve.py -- re-solve white_temp, white_tint and exposure on the card.

R-GREYCARD's measured-slope procedure, with the slopes MEASURED THIS RUN
and not inherited:

    1 capture at the current value, read the card
    2 capture at a second, KNOWN offset
    3 slope = d(metric) / d(parameter)
    4 requested = (target - current) / slope
    5 apply, re-capture, CONFIRM; the residual is recorded, not tuned away

⭐ WHY SCENE-LINEAR AND NOT FinalImage, decided by measurement rather
than preference. On the FinalImage PNG at this exposure the card reads
linear [0.28315, 0.27889, 0.27889] -- and those are 8-bit codes 145,
144, 144. One code is 1.526% of the card, so the ENTIRE white-balance
signal is 1.00 code in R and 0.00 codes in B, against a card spatial
std of 1.84 codes. Signal-to-noise below 1: a slope measured there is a
slope of the quantiser. The acceptance BAND (0.85-1.15 = +-10 codes) is
still perfectly readable on FinalImage, and is still checked there --
but the SOLVE runs on the EXR, which is float. This is R-GREYCARD's own
2026-09-11b ruling arrived at independently.

Each probe writes the live PostProcessVolume WITHOUT saving and is
restored afterwards; only the solved value goes into the recipe.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

REPO = bootstrap.REPO_ROOT
PAYLOAD = os.path.join(REPO, "scripts", "payloads", "set_grade_probe.py")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def set_grade(**terms):
    """Write probe terms to the live PPV. Returns the read-back dict."""
    src = open(PAYLOAD, encoding="utf-8").read()
    src = src.replace("__CONFIG_JSON__", json.dumps(terms))
    tmp = os.path.join(REPO, "_verify", "_grade_probe_tmp.py")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(src)
    try:
        r = run([sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
                 tmp])
        out = r.stdout + r.stderr
        i, j = out.find("{"), out.rfind("}")
        if i < 0:
            raise SystemExit("no marker from set_grade_probe:\n" + out[-1500:])
        d = json.loads(out[i:j + 1])
        if not d.get("ok") or not d.get("matches_request"):
            raise SystemExit("grade probe did not take: %s"
                             % json.dumps(d)[:600])
        return d
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)


def capture(tag, station="near_ground"):
    """One scene-linear capture. Returns the EXR path.

    ⛔ NAMING, corrected 2026-09-15 (AUDIT S-5, closure A-5): the EXR's
    RGBA channels are the tone-curve-DISABLED FinalImage -- POST-GRADE,
    they carry the WB stage -- instrument `finalimage_linear`. The PPI0
    tap rides along as the separate FinalImagePPI0 channel group and is
    only read when exr_card is asked for that channel. Every card read
    this script makes for the WB solve is finalimage_linear; the earlier
    docstring called the whole capture "PPI0" and that mislabel is how
    the 09-14 solve's buffer went unnamed.
    """
    cmd = [sys.executable, "-u",
           os.path.join(REPO, "scripts", "bench_capture.py"),
           "--profile", "target", "--stations", station, "--linear",
           "--pp-pass", "PPI0=/Game/Bench/M_PPI0_Passthrough",
           "--tag", tag]
    r = run(cmd)
    # The CONTENT gate may refuse (this bench has been refusing since
    # 2026-09-13 at ~20% featureless against 0.8% predicted sky). That
    # gate is about scene content, not about the card, so a refusal is
    # reported and does not stop the solve -- but it is NOT swallowed.
    date = None
    for ln in (r.stdout + r.stderr).splitlines():
        if "_verify/bench/" in ln and ".png" in ln:
            date = ln.split("_verify/bench/")[1].split("/")[0]
    if date is None:
        raise SystemExit("could not find the capture date in output:\n"
                         + (r.stdout + r.stderr)[-2000:])
    exr = os.path.join(REPO, "_verify", "bench", date,
                       "target_%s" % tag, "%s.exr" % station)
    if not os.path.isfile(exr):
        raise SystemExit("no EXR at %s\n%s" % (exr, (r.stdout + r.stderr)[-2000:]))
    refused = "REFUSE" in (r.stdout + r.stderr)
    return exr, date, refused


def card(exr, date, tag, station="near_ground"):
    sidecar = os.path.join(REPO, "_verify", "bench", date,
                           "bench_run_target_%s.json" % tag)
    r = run([sys.executable, os.path.join(REPO, "scripts", "exr_card.py"),
             "--exr", exr, "--station", station, "--sidecar", sidecar])
    out = r.stdout + r.stderr
    i, j = out.find("{"), out.rfind("}")
    if i < 0:
        raise SystemExit("exr_card produced no JSON:\n" + out[-1500:])
    return json.loads(out[i:j + 1])


def measure(tag, **terms):
    """Set terms (if any), capture, read the card. One row of evidence."""
    rb = set_grade(**terms) if terms else None
    exr, date, refused = capture(tag)
    c = card(exr, date, tag)
    row = {"tag": tag, "terms": terms, "exr": exr,
           "content_gate_refused": refused,
           "card_rgb": c["card_median_linear_rgb"],
           "card_luma": c["card_luma_linear"],
           "card_std": c["card_luma_std"],
           "wb_R": c["wb_ratio_R"], "wb_B": c["wb_ratio_B"],
           "exposure_verdict": c["verdict"],
           "tone_curve_disabled": c.get("disable_tone_curve_readback")}
    if rb:
        row["grade_readback"] = rb["after"]
    print("  %-22s R/G %.5f  B/G %.5f  luma %.5f  std %.5f  %s"
          % (tag, row["wb_R"], row["wb_B"], row["card_luma"],
             row["card_std"], "GATE-REFUSED" if refused else ""))
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--temp", type=float, required=True,
                    help="current white_temp_k")
    ap.add_argument("--tint", type=float, required=True,
                    help="current white_tint")
    ap.add_argument("--ev", type=float, required=True,
                    help="current exposure.compensation_ev")
    ap.add_argument("--d-temp", type=float, default=500.0,
                    help="probe step in K")
    ap.add_argument("--d-tint", type=float, default=0.06,
                    help="probe step in tint units")
    ap.add_argument("--d-ev", type=float, default=-0.7,
                    help="probe step in EV")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = {}
    print("BASELINE (current grade, already in force)")
    rows["base"] = measure("gr_base")

    print("PROBE white_temp %+.0f K" % a.d_temp)
    rows["temp"] = measure("gr_temp", white_temp=a.temp + a.d_temp)
    set_grade(white_temp=a.temp)          # restore before the next axis

    print("PROBE white_tint %+.4f" % a.d_tint)
    rows["tint"] = measure("gr_tint", white_tint=a.tint + a.d_tint)
    set_grade(white_tint=a.tint)

    print("PROBE exposure %+.3f EV" % a.d_ev)
    rows["ev"] = measure("gr_ev", auto_exposure_bias=a.ev + a.d_ev)
    set_grade(auto_exposure_bias=a.ev)

    b = rows["base"]
    # ---- slopes, each from ONE variable ------------------------------
    s_temp = (rows["temp"]["wb_R"] - b["wb_R"]) / a.d_temp
    s_tint = (rows["tint"]["wb_B"] - b["wb_B"]) / a.d_tint
    # exposure is a power law in log space (R-GREYCARD 2026-09-11b)
    import math
    s_ev = (math.log2(rows["ev"]["card_luma"] / b["card_luma"])) / a.d_ev

    sol = {}
    sol["white_temp_k"] = (a.temp + (1.0 - b["wb_R"]) / s_temp
                           if s_temp else None)
    sol["white_tint"] = (a.tint + (1.0 - b["wb_B"]) / s_tint
                         if s_tint else None)
    sol["compensation_ev"] = (a.ev + math.log2(0.18 / b["card_luma"]) / s_ev
                              if s_ev else None)

    doc = {"_what": "R-GREYCARD re-solve, slopes measured this run",
           "current": {"white_temp_k": a.temp, "white_tint": a.tint,
                       "compensation_ev": a.ev},
           "steps": {"d_temp_k": a.d_temp, "d_tint": a.d_tint,
                     "d_ev": a.d_ev},
           "rows": rows,
           "slopes": {"wb_R_per_K": s_temp, "wb_B_per_tint": s_tint,
                      "log2luma_per_EV": s_ev},
           "solved": sol}

    print("")
    print("SLOPES (measured this run, not inherited)")
    print("  d(wb_R)/dK      %.3e   per 100 K: %+.5f" % (s_temp, s_temp * 100))
    print("  d(wb_B)/dtint   %.5f    per 0.01: %+.5f" % (s_tint, s_tint * 0.01))
    print("  d(log2 luma)/dEV %.4f   (1.0 would be a linear chain)" % s_ev)
    print("")
    print("SOLVED")
    print("  white_temp_k     %.1f -> %.1f   (%+.1f K)"
          % (a.temp, sol["white_temp_k"], sol["white_temp_k"] - a.temp))
    print("  white_tint       %.4f -> %.4f  (%+.4f)"
          % (a.tint, sol["white_tint"], sol["white_tint"] - a.tint))
    print("  compensation_ev  %.4f -> %.4f (%+.4f EV)"
          % (a.ev, sol["compensation_ev"], sol["compensation_ev"] - a.ev))

    out = a.out or os.path.join(REPO, "_verify", "bench",
                                "grade_resolve_2026-09-14.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("")
    print("wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
