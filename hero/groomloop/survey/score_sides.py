"""score_sides.py -- SIDES AGENT scoreboard. Read-only; writes nothing but its
own survey json. Uses the SHARED front_metrics measurement for the candidate so
my numbers stay comparable with the other agents and with v032b.

THE CLAY TARGET IS RE-MEASURED AT BORDER=14, and that is the whole point of
this file. front_metrics.BORDER is 6, but the clay JPEG carries an 11-px solid
dark border (luma ~21 against a background of 59), so five border columns
survive the trim and are classified as HAIR on every row. Measured: it puts the
clay silhouette edge at column 1029 of a 1030-px frame in all 16 width bands,
which is why clay_front.json's width_profile is a constant 3.6453 -- a frame
saturation, not a hair measurement.

The candidate PNG has no such border: its metrics are byte-identical at
BORDER 6, 14 and 20. So the contamination is ONE-SIDED, inflating only the
target. Corrected targets are used for the deltas below; the raw ones are
printed beside them so the correction is visible rather than assumed.

    python score_sides.py <name>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import front_metrics as fm                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CLAY = os.path.join(HERE, "..", "..", "reference", "appearance_groom_clay.jpg")

# WATCH AXES -- not mine to improve, must not break. From the brief.
WATCH = {"flare_max_ratio": ("<=", 0.75),
         "scalp_exposed_pct": ("<=", 3.0),
         "central_eye": ("<=", 0.020)}


def clay_target():
    old = fm.BORDER
    fm.BORDER = 14
    try:
        return fm.measure(CLAY)
    finally:
        fm.BORDER = old


def main():
    name = sys.argv[1]
    img = os.path.join(HERE, "..", "..", "..", "_verify", "20260822_agents",
                       name, "preview_front.png")
    fm.BORDER = 6
    cand = fm.measure(img)
    json.dump(cand, open(os.path.join(HERE, name + "_front.json"), "w",
                         encoding="utf-8"), indent=2)
    c = clay_target()

    base = json.load(open(os.path.join(HERE, "v032b_front.json"),
                          encoding="utf-8"))

    print("=" * 74)
    print("%-22s %9s %9s %9s %9s" % (name, "v032b", "CAND", "CLAY*", "gap"))
    print("=" * 74)
    rows = [("ear_0.30_0.62", "band_cover"), ("jaw_0.70_0.95", "band_cover"),
            ("forehead_0.00_0.15", "band_cover"),
            ("brow_0.15_0.28", "band_cover"), ("eye_0.28_0.42", "band_cover")]
    for k, grp in rows:
        b, v, t = base[grp][k], cand[grp][k], c[grp][k]
        print("%-22s %9.4f %9.4f %9.4f %+9.4f  (d_base %+.4f)"
              % (k, b, v, t, v - t, v - b))
    for k in ("hair_area_over_face_area", "edge_roughness"):
        b, v, t = base[k], cand[k], c[k]
        print("%-22s %9.4f %9.4f %9.4f %+9.4f  (d_base %+.4f)"
              % (k, b, v, t, v - t, v - b))
    print("%-22s %9.4f %9.4f %9.4f"
          % ("central eye (watch)", base["central_cover"]["eye_0.28_0.42"],
             cand["central_cover"]["eye_0.28_0.42"],
             c["central_cover"]["eye_0.28_0.42"]))

    print("")
    print("width_profile   band: cand  CLAY*   delta   region")
    for i, (a, bb) in enumerate(zip(cand["width_profile"],
                                    c["width_profile"])):
        tag = ("crown/temple" if i <= 5 else "EAR" if i <= 9
               else "JAW" if i <= 13 else "below jaw(bust)")
        flag = ""
        if i <= 9:
            flag = "  <-- TOO NARROW" if a - bb < -0.08 else (
                "  <-- too wide" if a - bb > 0.08 else "")
        print("  %2d          %6.3f %6.3f  %+6.3f  %s%s"
              % (i, a, bb, a - bb, tag, flag))
    print("")
    print("* CLAY re-measured at BORDER=14; raw clay_front.json values are")
    print("  ear 0.3042 jaw 0.2414 area 1.3008 wp=const 3.6453 (border bug).")


if __name__ == "__main__":
    main()
