"""Score one fringe candidate against the v032b baseline and the clay target.

Read-only. Prints the four rubric axes plus the datum row, because face_top is
a MOVING DATUM -- the band stack rides down with the fringe -- and a forehead
number that fell while the hair rose is explained by that row and nothing else.
"""
import json
import sys

CLAY = {"cf": 0.2696, "cb": 0.0185, "ce": 0.0014, "bf": 0.7937}
BASE = {"cf": 0.2085, "cb": 0.0000, "ce": 0.0167, "bf": 0.6387}
LABEL = (("cf", "central forehead"), ("cb", "central brow"),
         ("ce", "central eye"), ("bf", "band forehead"))


def load(name):
    d = json.load(open("hero/groomloop/survey/%s_front.json" % name))
    c, b = d["central_cover"], d["band_cover"]
    return d, {"cf": c["forehead_0.00_0.15"], "cb": c["brow_0.15_0.28"],
               "ce": c["eye_0.28_0.42"], "bf": b["forehead_0.00_0.15"]}


def main():
    name = sys.argv[1]
    d, cur = load(name)
    print("%-18s %8s %8s %8s %9s" % ("axis", "v032b", name, "clay", "d_vs_base"))
    for k, lab in LABEL:
        print("%-18s %8.4f %8.4f %8.4f %+9.4f"
              % (lab, BASE[k], cur[k], CLAY[k], cur[k] - BASE[k]))
    f, b = d["face"], d["band_cover"]
    print("face_top=%d face_h=%d face_w=%d | band_brow=%.4f band_eye=%.4f "
          "| crown_lift=%.4f edge_rough=%.2f hair/face=%.4f"
          % (f["top_row"], f["height_px"], f["width_px"],
             b["brow_0.15_0.28"], b["eye_0.28_0.42"],
             d["crown_lift_frac"], d["edge_roughness"],
             d["hair_area_over_face_area"]))


if __name__ == "__main__":
    main()
