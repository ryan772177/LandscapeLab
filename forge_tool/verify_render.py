"""Closed-loop render fidelity: measure the RENDER with the same
instrument that measured the CONCEPT, and report the deltas.

This is the T2 acceptance measurement, runnable without any API key:
analyse_concept.measure_for_brief (band light split + min-luma rise) on
both images, plus whole-frame mean luma for the exposure delta in EV
(the proven relight rule: EV_new = EV_old - log2(render/concept) —
2026-09-02 calibration closed coast at -0.017 and crystal at +0.112
luma delta with exactly this arithmetic).

The output is a MEASUREMENT REPORT, not a gate: numbers plus the
suggested next knob. Deciding whether a delta is acceptable is a
judgement the calibration history informs; inventing a hard threshold
here would be an underived tolerance (verification practice).

Usage:
    python -m forge_tool.verify_render <concept> <render> [--out f.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from analyse_concept import load_image, measure_for_brief  # noqa: E402


def mean_luma(path):
    _, lum, _, _, _ = load_image(path)
    return float(lum.mean())


def report(concept_path, render_path):
    c = measure_for_brief(concept_path)
    r = measure_for_brief(render_path)
    cl, rl = mean_luma(concept_path), mean_luma(render_path)
    ev_delta = math.log2(max(rl, 1e-6) / max(cl, 1e-6))
    return {
        "concept": os.path.relpath(os.path.abspath(concept_path), REPO)
        .replace("\\", "/"),
        "render": os.path.relpath(os.path.abspath(render_path), REPO)
        .replace("\\", "/"),
        "concept_measured": c,
        "render_measured": r,
        "delta": {
            "sunlit_rb_split": round(
                r["sunlit_rb_split"] - c["sunlit_rb_split"], 3),
            "minluma_rise": round(
                r["minluma_rise"] - c["minluma_rise"], 3),
            "sunlit_rgb": [round(rv - cv, 3) for rv, cv in
                           zip(r["sunlit_rgb"], c["sunlit_rgb"])],
            "mean_luma": round(rl - cl, 4),
            "exposure_ev": round(ev_delta, 3),
        },
        "_instrument_caveat": (
            "the 0.60-0.85 ground band and the min-luma depth proxy "
            "assume comparable framing; when the render's composition "
            "differs from the concept's, part of each delta is FRAMING, "
            "not lighting — read the deltas as a trend across relight "
            "iterations at a FIXED camera, not as an absolute score"),
        "_suggested_knob": (
            "exposure: apply EV_new = EV_old - (%.3f) via "
            "lighting_geometry (the proven relight rule); NOTE the "
            "parked anomaly — canyon/highland-class worlds showed zero "
            "EV response, so verify the knob responds before trusting "
            "one application" % ev_delta),
        "_calibration_reference": {
            "coast_final_luma_delta": -0.017,
            "crystal_final_luma_delta": 0.112,
            "_source": "2026-09-02 EV luma-matching session "
                       "(MORNING_REPORT addenda)",
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("concept")
    ap.add_argument("render")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    for p in (a.concept, a.render):
        if not os.path.isfile(p):
            print("REFUSE: missing image %s" % p)
            return 2
    rep = report(a.concept, a.render)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
            f.write("\n")
    d = rep["delta"]
    print("fidelity (render - concept):")
    print("  sunlit R-B split : %+0.3f" % d["sunlit_rb_split"])
    print("  min-luma rise    : %+0.3f" % d["minluma_rise"])
    print("  sunlit RGB       : %+0.3f %+0.3f %+0.3f" % tuple(d["sunlit_rgb"]))
    print("  mean luma        : %+0.4f  (%+0.3f EV)"
          % (d["mean_luma"], d["exposure_ev"]))
    if a.out:
        print("report: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
