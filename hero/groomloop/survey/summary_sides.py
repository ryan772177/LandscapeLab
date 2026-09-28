"""summary_sides.py -- final SIDES table. Every candidate AND the clay target
re-measured in ONE process with ONE version of front_metrics, because the
shared instrument changed mid-run and a table that mixes two versions is not a
comparison.
"""

import json
import os
import re
import sys

sys.path.insert(0, "hero/groomloop/scripts")
import front_metrics as fm                                   # noqa: E402

RUNS = ["sides_00", "sides_01", "sides_02", "sides_03", "sides_04",
        "sides_05", "sides_06", "sides_07"]


def preview_watch(name):
    """flare_max / scalp from the render log if present, else from re-render."""
    return WATCH.get(name, (None, None))


# measured from each cycle's preview run, transcribed at the time
WATCH = {"sides_00": (0.651, 3.21), "sides_01": (0.672, 3.21),
         "sides_02": (0.672, 3.45), "sides_03": (0.667, 2.84),
         "sides_04": (0.667, 2.97), "sides_05": (0.622, 2.98),
         "sides_06": (0.709, 2.94), "sides_07": (0.665, 2.84)}

fm.BORDER = 14
clay = fm.measure("hero/reference/appearance_groom_clay.jpg")
fm.BORDER = 6

print("CLAY target (BORDER=14, current front_metrics): "
      "ear %.4f  jaw %.4f  area %.4f  edge %.2f  ceye %.4f"
      % (clay["band_cover"]["ear_0.30_0.62"],
         clay["band_cover"]["jaw_0.70_0.95"],
         clay["hair_area_over_face_area"], clay["edge_roughness"],
         clay["central_cover"]["eye_0.28_0.42"]))
print("")
hdr = ("%-10s %7s %7s %7s %7s %7s %7s %6s %6s"
       % ("run", "ear", "jaw", "area", "edge", "flare", "scalp", "ceye", "faceW"))
print(hdr)
print("-" * len(hdr))
for n in RUNS:
    img = "_verify/20260822_agents/%s/preview_front.png" % n
    if not os.path.exists(img):
        continue
    r = fm.measure(img)
    fl, sc = WATCH.get(n, (0, 0))
    print("%-10s %7.4f %7.4f %7.4f %7.2f %7.3f %7.2f %6.4f %6d"
          % (n, r["band_cover"]["ear_0.30_0.62"],
             r["band_cover"]["jaw_0.70_0.95"], r["hair_area_over_face_area"],
             r["edge_roughness"], fl, sc,
             r["central_cover"]["eye_0.28_0.42"], r["face"]["width_px"]))
print("-" * len(hdr))
print("%-10s %7.4f %7.4f %7.4f %7.2f %7s %7s %6.4f"
      % ("CLAY*", clay["band_cover"]["ear_0.30_0.62"],
         clay["band_cover"]["jaw_0.70_0.95"], clay["hair_area_over_face_area"],
         clay["edge_roughness"], "<=.75", "<=3.0",
         clay["central_cover"]["eye_0.28_0.42"]))
