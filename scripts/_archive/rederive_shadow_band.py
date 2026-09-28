"""rederive_shadow_band.py — the shadow_tint_B band AT THE GRADE IN FORCE.

    python scripts/rederive_shadow_band.py

RULED BY RYAN 2026-09-12.

THE PROBLEM. The acceptance `shadow_tint_B in 1.10-1.60` was ruled on
2026-09-10 "under NEUTRAL white balance" -- WB equal to the sun. The
grade has since moved to 3481.9 K against a 5200 K sun, 1718 K below it.
The band's own docstring retires its predecessor for exactly this reason:
the old 1.3-1.7 was "calibrated in an era whose only PASS carried a WB
1300 K BELOW the sun -- a blue-amplifying grade".

So the band cannot simply be applied here. It has to be TRANSFORMED to
the white point in force, because the band describes a PHYSICAL SHADE and
the white point changes what that shade MEASURES.

WHY THIS IS NOW DERIVABLE, WHEN IT WAS NOT THIS MORNING. Earlier the only
route was extrapolating from two historical points that differed in SUN
as well as WB, on a response known to saturate; both a linear and a log
model over-predicted the actual reading by 28-58%. The WB test replaced
that guesswork with a DIRECT MEASUREMENT of the response, same station,
same world, same instrument, one variable:

    WB 5200.0  (neutral, = the sun)   B 0.7674
    WB 3481.9  (the grade in force)   B 1.8051

INDEPENDENT CROSS-CHECK. The measured factor is compared against the
project's own Planck two-channel slope (9454 K, the same constant the
white-balance steps were derived with). Agreement means the scaling is
not an artefact of two captures; disagreement would mean the transform is
not a pure white-point effect and the re-derivation must stop.

⛔ WHAT IS *NOT* EVIDENCE. The scene's deficit expressed as a fraction of
the floor is IDENTICAL in both conditions -- and that is ALGEBRA, not
corroboration: scaling the band and the reading by the same factor
cannot change their ratio. It is reported because it is easy to mistake
for a second confirmation, and it is not one.
"""
from __future__ import annotations

import json
import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The ruled band, and the condition it was ruled under (RECIPES R-GRADE,
# 2026-09-10): Brief 2b measured 1.1243 at sun 5200 / WB 5200 and the
# band was set to admit it.
BAND_NEUTRAL = (1.10, 1.60)
SUN_K = 5200.0

# MEASURED, near_ground, target class, 2026-09-12. Same world, same
# instrument, one variable; frames verified distinct by SHA-256.
WB_NEUTRAL_K, B_AT_NEUTRAL = 5200.0, 0.7674
WB_GRADE_K, B_AT_GRADE = 3481.9, 1.8051

# The project's Planck two-channel slope, used for every white-balance
# step in this recipe: d(ln r)/d(1/T) = c2 * (1/470nm - 1/680nm).
PLANCK_SLOPE_K = 9454.0


def mired(t):
    return 1e6 / float(t)


def main():
    d_mired = mired(WB_GRADE_K) - mired(WB_NEUTRAL_K)
    measured_factor = B_AT_GRADE / B_AT_NEUTRAL
    planck_factor = math.exp(PLANCK_SLOPE_K * d_mired * 1e-6)
    disagree = abs(measured_factor - planck_factor) / planck_factor

    lo = BAND_NEUTRAL[0] * measured_factor
    hi = BAND_NEUTRAL[1] * measured_factor

    print("THE GRADE IN FORCE")
    print("  sun                     %8.1f K" % SUN_K)
    print("  white_temp_k            %8.1f K  (%.0f K BELOW the sun)"
          % (WB_GRADE_K, SUN_K - WB_GRADE_K))
    print("  delta from neutral      %8.2f mired" % d_mired)
    print()
    print("THE MEASURED WHITE-BALANCE RESPONSE (near_ground, target class)")
    print("  B at WB %.1f K          %8.4f" % (WB_NEUTRAL_K, B_AT_NEUTRAL))
    print("  B at WB %.1f K          %8.4f" % (WB_GRADE_K, B_AT_GRADE))
    print("  measured factor         %8.4f" % measured_factor)
    print()
    print("CROSS-CHECK AGAINST THE PLANCK TWO-CHANNEL SLOPE (independent)")
    print("  predicted factor        %8.4f  (slope %.0f K)"
          % (planck_factor, PLANCK_SLOPE_K))
    print("  disagreement            %7.2f%%" % (100.0 * disagree))
    verdict = ("CORROBORATED -- the transform is a white-point effect"
               if disagree <= 0.10 else
               "REFUSED -- too far from the model to be a pure white-point "
               "effect; do not re-derive on this basis")
    print("  %s" % verdict)
    print()
    print("THE RE-DERIVED BAND, AT THIS GRADE")
    print("  neutral-WB band         %.2f - %.2f" % BAND_NEUTRAL)
    print("  x measured factor       %.3f - %.3f" % (lo, hi))
    print()
    print("THE VERDICT ON THE WORLD")
    print("  measured B              %8.4f" % B_AT_GRADE)
    print("  re-derived floor        %8.4f" % lo)
    ratio = B_AT_GRADE / lo
    print("  fraction of the floor   %8.4f   -> %s"
          % (ratio, "PASS" if lo <= B_AT_GRADE <= hi else "FAIL"))
    if B_AT_GRADE < lo:
        print("  SHADE IS UNDER-BLUE by %.1f%% -- it needs MORE sky fill,"
              % (100.0 * (1.0 - ratio)))
        print("  not less. The direction is the OPPOSITE of what the band")
        print("  said when applied untransformed (1.8051 over a 1.60"
              " ceiling).")
    print()
    print("NOT EVIDENCE: the same fraction appears at BOTH white points")
    print("  (%.4f at WB %.0f, %.4f at WB %.1f) because scaling the band"
          % (B_AT_NEUTRAL / BAND_NEUTRAL[0], WB_NEUTRAL_K, ratio, WB_GRADE_K))
    print("  and the reading by one factor cannot change their ratio.")
    print("  It is ALGEBRA, not a second confirmation.")

    out = {
        "_what": "shadow_tint_B band re-derived at the grade in force",
        "_ruled": "Ryan 2026-09-12",
        "sun_k": SUN_K, "white_temp_k": WB_GRADE_K,
        "delta_mired": round(d_mired, 3),
        "band_neutral": list(BAND_NEUTRAL),
        "measured_factor": round(measured_factor, 5),
        "planck_factor": round(planck_factor, 5),
        "planck_disagreement_frac": round(disagree, 5),
        "corroborated": bool(disagree <= 0.10),
        "band_at_grade": [round(lo, 4), round(hi, 4)],
        "measured_B": B_AT_GRADE,
        "verdict": "PASS" if lo <= B_AT_GRADE <= hi else "FAIL",
        "fraction_of_floor": round(ratio, 5),
    }
    p = os.path.join(REPO, "_verify", "bench", "2026-09-12",
                     "shadow_band_rederived.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print()
    print("wrote %s" % os.path.relpath(p, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
