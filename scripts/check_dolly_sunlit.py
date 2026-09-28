"""check_dolly_sunlit.py — E4: is the dolly's FIRST and LAST frame sunlit?

WHAT THIS IS AND IS NOT
-----------------------
E4 says: capture once, check the first and last frame, DO NOT SCORE. So this
reports numbers and a sunlit/not judgement on the two frames it was asked
about, plus a composite `stayed_out_of_canopy_shadow` (first lit AND last lit
AND the first->last drop within DROP_MAX) and a 5-sample walk profile for
attribution. It does NOT compare against a budget or emit a graded/temporal
score for the walk.

HOW "SUNLIT" IS DECIDED, AND WHY NOT BY MEAN BRIGHTNESS
-------------------------------------------------------
Mean luma cannot separate "in canopy shadow" from "a darker scene": a frame
half-filled with dark buildings and half with lit grass has the same mean as
an evenly dim one. Direct sun at this station produces a POPULATION of bright
pixels -- the lit grass reads 0.3-0.9 linear luma while shadowed grass sits
near 0.02-0.05 -- so the discriminator is the SIZE OF THE BRIGHT POPULATION,
not the average.

  sunlit_fraction  share of pixels above SUN_L, measured on the GROUND HALF
                   of the frame (the lower half). The upper half is sky,
                   buildings and canopy, and their brightness says nothing
                   about whether the CAMERA is standing in shadow.

The near_ground still measured 0.399 of the full frame above 0.20 linear, so
the threshold sits well inside the lit population rather than at its edge.

The absolute numbers depend on the level's lighting and exposure, so the
LOAD-BEARING comparison is FIRST vs LAST: a walk that starts lit and ends in
shadow shows a collapse in sunlit_fraction, and that is what E4 asks about.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

SUN_L = 0.20        # linear luma; inside the lit population, not at its edge
SUNLIT_MIN = 0.15   # share of the ground half that must be lit
DROP_MAX = 0.50     # first->last relative collapse that means "walked into shadow"


def luma(path):
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def measure(path):
    L = luma(path)
    h = L.shape[0]
    ground = L[h // 2:, :]
    return {
        "file": path,
        "luma_mean_full": round(float(L.mean()), 4),
        "luma_p50_full": round(float(sorted(L.flatten())[L.size // 2]), 4),
        "ground_half": {
            "luma_mean": round(float(ground.mean()), 4),
            "luma_p90": round(float(
                sorted(ground.flatten())[int(ground.size * 0.90)]), 4),
            "sunlit_fraction": round(float((ground > SUN_L).mean()), 4),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="directory of dolly frames")
    ap.add_argument("--out", default="")
    ap.add_argument("--baseline-from", default="",
                    help="walk_midpoints.json from probe_walk_midpoints.py. "
                         "Embeds the chosen heading's KNOWN shade profile in "
                         "the sidecar so a future temporal score can be "
                         "attributed to shade rather than to pop.")
    ap.add_argument("--baseline-yaw", type=float, default=None,
                    help="which row of --baseline-from to embed")
    a = ap.parse_args()

    # The baseline args are useless singly: --baseline-from without a yaw (or
    # vice-versa) silently produced a sidecar with no baseline. Require both.
    if bool(a.baseline_from) != (a.baseline_yaw is not None):
        print("REFUSE: --baseline-from and --baseline-yaw must be given "
              "together (got only one).")
        return 2

    frames = sorted(glob.glob(os.path.join(a.dir, "*.png")))
    if len(frames) < 2:
        print("REFUSE: %d frame(s) in %s -- need at least a first and a last"
              % (len(frames), a.dir))
        return 3

    first, last = measure(frames[0]), measure(frames[-1])
    f = first["ground_half"]["sunlit_fraction"]
    l = last["ground_half"]["sunlit_fraction"]
    drop = (f - l) / f if f > 0 else 1.0

    out = {
        "_what": "E4: first and last frame of the 3 s sunlit dolly, checked "
                 "for canopy shadow, plus a composite stayed_out_of_canopy_"
                 "shadow and a 5-sample profile. NOT a budgeted/temporal SCORE.",
        "method": {
            "sun_luma_threshold": SUN_L,
            "sunlit_fraction_min": SUNLIT_MIN,
            "max_relative_drop": DROP_MAX,
            "_region": "lower half of the frame only: the upper half is sky, "
                       "buildings and canopy, whose brightness says nothing "
                       "about whether the CAMERA stands in shadow.",
            "_why_not_mean": "mean luma cannot separate 'in shadow' from 'a "
                             "darker scene'. Direct sun produces a bright "
                             "POPULATION; its size is the discriminator.",
        },
        "frame_count": len(frames),
        "first": first,
        "last": last,
        "sunlit_fraction_first": f,
        "sunlit_fraction_last": l,
        "relative_drop": round(drop, 4),
    }
    ok_first = f >= SUNLIT_MIN
    ok_last = l >= SUNLIT_MIN
    ok_drop = drop <= DROP_MAX
    out["first_sunlit"] = ok_first
    out["last_sunlit"] = ok_last
    out["stayed_out_of_canopy_shadow"] = bool(ok_first and ok_last and ok_drop)
    out["statement"] = (
        "First frame %.1f%% of the ground half above %.2f linear, last frame "
        "%.1f%%, a %.0f%% change. %s"
        % (100 * f, SUN_L, 100 * l, 100 * drop,
           "Both frames are sunlit and the lit share holds across the walk."
           if out["stayed_out_of_canopy_shadow"] else
           "The path does NOT stay sunlit by this measure."))

    # ---- THE WALK PROFILE ------------------------------------------------
    # first-and-last is what E4 asks for, and it cannot tell a smooth decline
    # from a cliff, nor either from a dip that recovers by the last frame.
    # Five samples cost five frame reads and make the sidecar self-contained
    # for the attribution the baseline exists to support.
    prof = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        idx = min(len(frames) - 1, int(round(frac * (len(frames) - 1))))
        pm = measure(frames[idx])
        prof.append({"t": frac, "frame_index": idx,
                     "sunlit_fraction": pm["ground_half"]["sunlit_fraction"],
                     "luma_mean_full": pm["luma_mean_full"]})
    out["walk_profile"] = prof
    out["walk_lit_floor"] = min(p["sunlit_fraction"] for p in prof)

    # ---- the KNOWN SUNLIT BASELINE ---------------------------------------
    # RULED 2026-09-09: record the chosen heading's measured shade profile
    # beside the capture, so a later temporal score can be attributed to
    # SHADE or to POP rather than guessed at. Without it the sidecar says how
    # bright the walk was and nothing about how bright it was SUPPOSED to be.
    if a.baseline_from and a.baseline_yaw is not None:
        with open(a.baseline_from, encoding="utf-8") as fh:
            doc = json.load(fh)
        hit = [r for r in doc.get("rows", [])
               if abs(float(r.get("yaw", 1e9)) - a.baseline_yaw) < 1e-6]
        if not hit:
            print("REFUSE: no yaw %.4f row in %s"
                  % (a.baseline_yaw, a.baseline_from))
            return 4
        r = hit[0]
        # The baseline's whole point is a MEASURED shade profile; a matched-but-
        # incomplete row would embed lit_floor/first_to_last/samples as null and
        # read as a profile it does not carry. Refuse instead.
        _missing = [k for k in ("min", "first_to_last", "samples")
                    if r.get(k) is None]
        if _missing:
            print("REFUSE: baseline row for yaw %.4f is missing %s"
                  % (a.baseline_yaw, _missing))
            return 4
        out["sunlit_baseline"] = {
            "_what": "the chosen heading's lit share MEASURED ALONG THE WALK "
                     "before capture, at t=0.0/0.5/1.0. Its purpose is "
                     "ATTRIBUTION: a future temporal score that moves can be "
                     "checked against this to say whether the world got "
                     "darker (shade) or changed (pop).",
            "heading_yaw_deg": r["yaw"],
            "lit_floor": r.get("min"),
            "first_to_last": r.get("first_to_last"),
            "samples_t": r.get("samples"),
            "source": os.path.relpath(a.baseline_from).replace("\\", "/"),
            "_instrument": "shoot.py stills, 960x540, FOV 90 -- the dolly "
                           "renders at the profile's own resolution. FOV and "
                           "16:9 aspect match, so the FRAMING is identical "
                           "and the fractions are comparable; sampling "
                           "density is not, so treat small absolute "
                           "differences as instrument, not world.",
            "_drift": "headings re-measured ~30 min apart in the same session "
                      "moved +0.025 and +0.022 as DDC finished building. Any "
                      "absolute here carries roughly +/-0.03.",
        }

    print(json.dumps(out, indent=2))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        # Read the sidecar back rather than trusting the write.
        try:
            with open(a.out, encoding="utf-8") as fh:
                json.load(fh)
        except (OSError, ValueError) as exc:
            print("REFUSE: sidecar %s did not read back: %s" % (a.out, exc))
            return 4
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
