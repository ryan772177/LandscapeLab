"""pick_sunlit_heading.py — choose a dolly heading by MEASURING, not by
reasoning about azimuth conventions.

WHY NOT COMPUTE IT
------------------
The first attempt at E4 used the station's own forward vector and walked INTO
dappled shadow: the lit share of the ground half fell 41.1% -> 17.7% over
4.2 m. Picking a replacement analytically needs two things this project cannot
supply cleanly:

  * the azimuth->yaw convention. `lighting.sun.azimuth_deg` is 285, and
    sun_exposure.py's own docstring records that the bearing TOWARD the sun is
    not simply that number -- it takes the light's forward vector as measured
    instead. Guessing the sign or the offset is how a -25 deg roll got set
    three times believing it was pitch.
  * canopy shadow. sun_exposure.py marches the HEIGHTMAP, so it sees terrain
    shadow and is blind to the tree shadows that actually dapple this meadow.

So this measures the thing that matters: for each candidate heading, stand the
camera where the walk would END and ask whether the ground there is lit.

WHAT IT REPORTS
---------------
`sunlit_fraction` -- the share of the frame's GROUND HALF above 0.20 linear
luma, the same metric check_dolly_sunlit.py uses, so the numbers are
comparable with E4's own verdict. The upper half is sky and canopy and says
nothing about whether the camera stands in sun.

It picks nothing on its own. It prints a table; the heading is a decision.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(REPO, "research", "brief", "brief1_distance_as_angle",
                     "brief1", "benchmark.json")
SUN_L = 0.20


def lit_fraction(path):
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    L = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    ground = L[L.shape[0] // 2:, :]
    return float((ground > SUN_L).mean()), float(ground.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--speed", type=float, default=1.4, help="m/s")
    ap.add_argument("--step", type=float, default=45.0, help="yaw step, deg")
    ap.add_argument("--outdir", default=os.path.join(
        "_verify", "bench", "2026-09-08", "heading_probe"))
    a = ap.parse_args()

    if a.step <= 0:
        raise SystemExit("REFUSE: --step must be positive (got %g)." % a.step)

    with open(BENCH, encoding="utf-8-sig") as fh:
        bm = json.load(fh)
    matches = [s for s in bm["stations"] if s["name"] == "near_ground"]
    if not matches:
        raise SystemExit("REFUSE: no 'near_ground' station in %s; it has %s"
                         % (BENCH, ", ".join(s.get("name", "?")
                                             for s in bm["stations"])))
    st = matches[0]
    x0, y0, z0 = st["location_cm"]
    pitch = st["rotation_deg"][0]
    dist_cm = a.speed * a.seconds * 100.0

    out = os.path.join(REPO, a.outdir)
    os.makedirs(out, exist_ok=True)
    rows = []
    yaws = [round(-180.0 + i * a.step, 1)
            for i in range(int(360.0 / a.step))]
    print("probing %d headings, walk %.0f cm from near_ground" %
          (len(yaws), dist_cm))

    for yaw in yaws:
        p = math.radians(pitch)
        y = math.radians(yaw)
        fx, fy, fz = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y),
                      math.sin(p))
        ex, ey, ez = x0 + fx * dist_cm, y0 + fy * dist_cm, z0 + fz * dist_cm
        name = "end_yaw%+.0f" % yaw
        r = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "shoot.py"),
             "--name", name,
             "--loc=%.1f,%.1f,%.1f" % (ex, ey, ez),
             "--rot=0,%.1f,%.1f" % (pitch, yaw),
             "--fov", "90", "--res", "960x540",
             "--outdir", os.path.relpath(out, REPO), "--deadline", "600"],
            capture_output=True, text=True, cwd=REPO)
        png = os.path.join(out, name + ".png")
        if r.returncode != 0 or not os.path.exists(png):
            msg = ""
            for ln in (r.stdout or "").splitlines():
                if "REFUSE" in ln:
                    msg = ln.strip()[:80]
            rows.append({"yaw": yaw, "error": msg or "exit %d" % r.returncode})
            print("  yaw %+7.1f  %s" % (yaw, msg or "FAILED"))
            continue
        frac, mean = lit_fraction(png)
        rows.append({"yaw": yaw, "sunlit_fraction": round(frac, 4),
                     "ground_mean_luma": round(mean, 4),
                     "end_cm": [round(ex, 1), round(ey, 1), round(ez, 1)]})
        print("  yaw %+7.1f  sunlit %.3f  mean %.4f" % (yaw, frac, mean))

    dest = os.path.join(out, "heading_probe.json")
    json.dump({"_what": "END-POINT lit fraction per candidate heading. The "
                        "heading is a DECISION, not an output.",
               "station": "near_ground", "walk_cm": dist_cm,
               "sun_luma_threshold": SUN_L, "rows": rows},
              open(dest, "w", encoding="utf-8"), indent=2)
    ok = [r for r in rows if r.get("sunlit_fraction") is not None]
    print("wrote %s" % os.path.relpath(dest, REPO))
    if not ok:
        # Fail-open guard: a run where every heading shot failed measured
        # nothing; the exit code must not read as success.
        print("NO heading produced a measurement (%d/%d failed)"
              % (len(rows), len(rows)))
        return 1
    best = max(ok, key=lambda r: r["sunlit_fraction"])
    # NN13: report the candidate count beside the "highest" so a highest-of-1
    # does not read like a highest-of-8.
    print("\nhighest end-point lit fraction (of %d/%d headings measured): "
          "yaw %+.1f at %.3f"
          % (len(ok), len(rows), best["yaw"], best["sunlit_fraction"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
