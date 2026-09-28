import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
print("%-12s %8s %8s %8s %8s %10s %10s"
      % ("run", "top_row", "chin", "face_h", "face_w", "cx", "hairfrac"))
for n in sys.argv[1:]:
    p = os.path.join(HERE, n + "_front.json")
    if not os.path.exists(p):
        print(n, "MISSING")
        continue
    r = json.load(open(p, encoding="utf-8"))
    f = r["face"]
    print("%-12s %8d %8d %8d %8d %10.1f %10.4f"
          % (n, f["top_row"], f["chin_row"], f["height_px"], f["width_px"],
             f["centre_x_px"], r["mask_frac"]["hair"]))
