#!/usr/bin/env python3
"""item8_share.py -- I5 synthesis: fold item8_perf.json (I2 counter control +
I3 number) and item8_pixels.json (I3 pixel fraction + I4 crops) into the single
research/brief5/input/item8_share.json deliverable. READ-ONLY of the JSONs.

THE COMBINED POSITIVE CONTROL. The plan names TWO controls; the frame pixel diff
is the STRONGER one. The command is proven APPLIED if EITHER a render counter
dropped in B (perf I2) OR the A-vs-B frame differs beyond the A/A pixel floor
(pixels). So a counter set that is UNMEASURABLE (absent CSV columns) does NOT
sink the measurement -- the pixel diff carries it. Only when BOTH controls say
"no change" is the arm INCONCLUSIVE.

FINAL VERDICT per station (ITEM8 vocab):
  INCONCLUSIVE          neither control shows the command applied
  MEASURED              applied, GPU share >= 1x the A/A noise floor, windows steady
  MEASURED-NEGLIGIBLE   applied, GPU share < 1x the floor
  INCOMPLETE-*          a run/window/resolution problem upstream (passed through)
"""
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
INPUT = os.path.join(REPO, "research", "brief5", "input")
DERIVED_PROXY_FRACTION = 0.05727
PIXEL_APPLIED_X_FLOOR = 2.0        # A/B diff must beat the A/A floor by >=2x


def _load(name):
    p = os.path.join(INPUT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def _pixel_applied(pf):
    """Did the A/B frame diff show the command applied (beyond the A/A floor)?"""
    if not pf or "error" in pf:
        return None, "pixels unavailable"
    dfrac = pf.get("differing_fraction")
    xfloor = pf.get("differing_x_aa_floor")
    if dfrac is None:
        return None, "no differing_fraction"
    if isinstance(xfloor, str) and xfloor.startswith("inf"):
        return (dfrac > 0), "A/A floor 0 px; A/B diff %s (inf x floor)" % dfrac
    if isinstance(xfloor, (int, float)):
        return (xfloor >= PIXEL_APPLIED_X_FLOOR and dfrac > 0), \
            "A/B diff %s = %sx the A/A floor" % (dfrac, xfloor)
    return (dfrac > 0), "A/B diff %s, floor unavailable" % dfrac


def synth():
    perf = _load("item8_perf.json")
    pix = _load("item8_pixels.json")
    out = {"_what": "Item-8 HLOD proxy GPU-share -- I5 synthesis.",
           "_derived_proxy_fraction_vista": DERIVED_PROXY_FRACTION,
           "inputs": {"perf": "item8_perf.json", "pixels": "item8_pixels.json"},
           "stations": {}}
    if not perf:
        out["verdict"] = "INCOMPLETE: item8_perf.json missing (no renders?)"
        return out
    for st in ("vista", "treeline"):
        prep = (perf.get("stations") or {}).get(st, {})
        ppix = ((pix or {}).get("stations") or {}).get(st, {})
        pf = ppix.get("pixel_fraction_I3", {})
        counter_state = (prep.get("positive_control_I2") or {}).get(
            "counter_control_state")
        pix_applied, pix_reason = _pixel_applied(pf)
        applied = (counter_state == "APPLIED") or bool(pix_applied)
        num = prep.get("number_I3", {})
        perf_verdict = prep.get("verdict", "?")
        # combine: a genuine INCONCLUSIVE only when NEITHER control applied
        if perf_verdict.startswith("INCOMPLETE"):
            final = perf_verdict
        elif not applied:
            final = "INCONCLUSIVE"
        elif perf_verdict in ("MEASURED", "MEASURED-NEGLIGIBLE"):
            final = perf_verdict
        elif perf_verdict == "INCONCLUSIVE" and applied:
            # counters said not-applied but pixels say applied: trust the
            # stronger control, fall back to the share magnitude
            share = num.get("hlod_share_ms")
            floor = num.get("noise_floor_ms_AA")
            final = ("MEASURED" if (share is not None and floor is not None
                                    and share >= floor) else
                     "MEASURED-NEGLIGIBLE")
        else:
            final = perf_verdict
        out["stations"][st] = {
            "verdict": final,
            "hlod_share_ms": num.get("hlod_share_ms"),
            "hlod_share_pct_of_A": num.get("hlod_share_pct_of_A"),
            "hlod_share_x_noise_floor": num.get("hlod_share_x_noise_floor"),
            "noise_floor_ms_AA": num.get("noise_floor_ms_AA"),
            "gpu_p90_ms": num.get("gpu_p90_ms"),
            "per_pass_delta_A_minus_B_ms": num.get("per_pass_delta_A_minus_B_ms"),
            "positive_control": {
                "counter_state": counter_state,
                "counter_verdict": (prep.get("positive_control_I2") or {}).get(
                    "verdict"),
                "pixel_applied": pix_applied, "pixel_reason": pix_reason,
                "command_applied": applied},
            "pixel_fraction": {
                "differing_fraction": pf.get("differing_fraction"),
                "differing_x_aa_floor": pf.get("differing_x_aa_floor"),
                "vs_derived_0_05727": DERIVED_PROXY_FRACTION,
                "_note": pf.get("_comparison_note")},
            "far_forest_crops_I4": (ppix.get("crops_I4") or {}).get("crops"),
        }
    # overall
    verdicts = [out["stations"][s]["verdict"] for s in out["stations"]]
    out["verdict"] = ("MEASURED" if any(v == "MEASURED" for v in verdicts) else
                      "MEASURED-NEGLIGIBLE" if any(
                          v == "MEASURED-NEGLIGIBLE" for v in verdicts) else
                      "INCONCLUSIVE" if any(v == "INCONCLUSIVE" for v in verdicts)
                      else verdicts[0] if verdicts else "INCOMPLETE")
    return out


def main():
    out = synth()
    p = os.path.join(INPUT, "item8_share.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    for st, r in out.get("stations", {}).items():
        print("%-9s %-20s share %s ms (x%s floor)  pixel %s vs 0.05727"
              % (st, r["verdict"], r["hlod_share_ms"],
                 r["hlod_share_x_noise_floor"],
                 r["pixel_fraction"]["differing_fraction"]))
    print("OVERALL:", out.get("verdict"))
    print("wrote", os.path.relpath(p, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
