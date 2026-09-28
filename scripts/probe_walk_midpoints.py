"""Probe the MIDPOINT as well as the end, for the leading candidates.

pick_sunlit_heading.py stands the camera where the walk ENDS. E4's failure was
DAPPLED shadow, not a solid edge, so a heading can be lit at both ends and
still cross shade in between -- and "first and last frames verified" inherits
exactly that blind spot. This measures 0.0, 0.5 and 1.0 along the walk.

-67.5 is included because it is the centre of the lit lobe (-90 and -45 both
score high). A heading at the centre of a broad lobe is more robust to being
slightly wrong than one at its measured peak.
"""
import json
import math
import os
import subprocess
import sys

REPO = r"C:\Users\Admin\UE5LandscapePipeline"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from pick_sunlit_heading import lit_fraction  # noqa: E402

BENCH = os.path.join(REPO, "research", "brief", "brief1_distance_as_angle",
                     "brief1", "benchmark.json")
OUT = os.path.join(REPO, "_verify", "bench", "2026-09-08", "heading_probe")

with open(BENCH, encoding="utf-8-sig") as _fh:
    bm = json.load(_fh)
_matches = [s for s in bm["stations"] if s["name"] == "near_ground"]
if not _matches:
    sys.exit("REFUSE: no 'near_ground' station in %s; it has %s"
             % (BENCH, ", ".join(s.get("name", "?") for s in bm["stations"])))
st = _matches[0]
x0, y0, z0 = st["location_cm"]
pitch = st["rotation_deg"][0]
DIST = 1.4 * 3.0 * 100.0

rows = []
for yaw in (-90.0, -67.5, -45.0):
    p, y = math.radians(pitch), math.radians(yaw)
    fx, fy, fz = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y),
                  math.sin(p))
    per = {"yaw": yaw, "samples": {}}
    for frac in (0.0, 0.5, 1.0):
        d = DIST * frac
        ex, ey, ez = x0 + fx * d, y0 + fy * d, z0 + fz * d
        name = "walk_yaw%+.1f_t%02d" % (yaw, int(frac * 100))
        r = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "shoot.py"),
             "--name", name,
             "--loc= %.1f,%.1f,%.1f" % (ex, ey, ez),
             "--rot=0,%.1f,%.1f" % (pitch, yaw),
             "--fov", "90", "--res", "960x540",
             "--outdir", os.path.relpath(OUT, REPO), "--deadline", "600"],
            capture_output=True, text=True, cwd=REPO)
        png = os.path.join(OUT, name + ".png")
        if r.returncode != 0 or not os.path.exists(png):
            per["samples"]["t%.1f" % frac] = "FAILED"
            print("  yaw %+6.1f  t=%.1f  FAILED" % (yaw, frac))
            continue
        f, m = lit_fraction(png)
        per["samples"]["t%.1f" % frac] = round(f, 4)
        print("  yaw %+6.1f  t=%.1f  sunlit %.3f  mean %.4f" % (yaw, frac, f, m))
    vals = [v for v in per["samples"].values() if isinstance(v, float)]
    if vals:
        per["min"] = min(vals)
        # first_to_last needs BOTH endpoints as floats; a FAILED endpoint is the
        # string "FAILED", and "FAILED" - 0.0 would TypeError and lose the whole
        # run's output (the JSON write is after this loop).
        _t0 = per["samples"].get("t0.0")
        _t1 = per["samples"].get("t1.0")
        if isinstance(_t0, float) and isinstance(_t1, float):
            per["first_to_last"] = _t1 - _t0
    rows.append(per)
    if vals:
        print("    -> min %.3f  first->last %s  (%d/3 frames ok)"
              % (per["min"],
                 ("%+.3f" % per["first_to_last"]) if "first_to_last" in per
                 else "n/a (an endpoint failed)", len(vals)))
    else:
        print("    -> NO usable frames (0/3)")

dest = os.path.join(OUT, "walk_midpoints.json")
with open(dest, "w", encoding="utf-8") as _fh:
    json.dump({"_what": "lit fraction at t=0.0/0.5/1.0 along the 4.2 m walk, "
                        "for the leading headings. The END-ONLY probe cannot "
                        "see a dip in the middle; this can.",
               "station": "near_ground", "walk_cm": DIST, "rows": rows},
              _fh, indent=2)
print("wrote %s" % os.path.relpath(dest, REPO))
# Fail-open guard: a run in which every frame failed still wrote a file of
# "FAILED" markers; the exit code must say nothing was measured.
if not any(isinstance(v, float)
           for per in rows for v in per["samples"].values()):
    sys.exit("REFUSE: no heading produced a usable frame; nothing measured.")
