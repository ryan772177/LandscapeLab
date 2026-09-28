"""Solve a concept's camera from its recorded framing constraints. OFFLINE.

WHAT A "SOLVE" MEANS HERE, precisely
------------------------------------
The concept reader recorded what the IMAGE shows and refused to invent what it
could not see -- `camera.solve` is null and every terrain bearing carries
`_bearing_is_IMAGE_RELATIVE: "NOT a world bearing until the Phase B camera
solve exists"`. This is that solve, and it is the thing that converts those
image-relative bearings into something placeable.

It is arithmetic on three recorded constraints, not a fit to a picture:

    height_m      1.8     the eye height the reader read
    horizon_frac  0.45    where the horizon sits, as a fraction from the TOP
    fov_hint      moderate

⛔ `pitch_hint: "level"` AND `horizon_frac: 0.45` CANNOT BOTH BE LITERAL.
A truly level camera puts the horizon at exactly 0.5. 0.45 means the horizon
sits ABOVE centre, which requires the camera to pitch UP by

    pitch = (0.5 - horizon_frac) * fov_vertical

The reader was right to record both -- they are two different observations, and
the tension between them is information rather than an error. "Level" is the
reader's impression of a near-level camera; 0.45 is a measurement. **The
measurement wins, and the impression is what tells us the answer should be
small.** At a 60 deg horizontal FOV this gives +1.8 deg (1.799: vertical FOV
35.977 x (0.5 - 0.45)), which is indeed "basically level", so the two are
consistent once the arithmetic is done.

FOV IS A CHOICE AND IS LABELLED ONE. "Moderate" is not a number. 60 deg
horizontal is chosen as the midpoint of what a person means by it, and the
solve records `fov_provenance: "chosen"` so no later reader mistakes it for
something measured.
"""
import io
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_FOV_H = 60.0
ASPECT = 16.0 / 9.0


def vertical_fov(fov_h_deg, aspect=ASPECT):
    """UE's FieldOfView is HORIZONTAL. Convert properly, not by dividing."""
    h = math.radians(fov_h_deg)
    return math.degrees(2.0 * math.atan(math.tan(h / 2.0) / aspect))


def solve(concept, fov_h=DEFAULT_FOV_H):
    cam = concept["camera"]
    hf = float(cam["horizon_frac"])
    fov_v = vertical_fov(fov_h)
    pitch = (0.5 - hf) * fov_v
    return {
        "fov_horizontal_deg": fov_h,
        "fov_vertical_deg": round(fov_v, 3),
        "fov_provenance": "chosen -- the concept says 'moderate', not a number",
        "height_m": float(cam["height_m"]),
        "horizon_frac": hf,
        "pitch_deg": round(pitch, 3),
        "_pitch_derivation": ("(0.5 - horizon_frac) * fov_vertical. The "
                              "concept records pitch_hint 'level' AND "
                              "horizon_frac 0.45; a level camera puts the "
                              "horizon at 0.5, so the two are reconciled by "
                              "solving rather than by picking one."),
        "yaw_convention": ("world yaw is NOT solved here -- nothing in the "
                           "image fixes a compass direction, and the concept "
                           "already REFUSED to give the sun an azimuth for "
                           "the same reason. Feature bearings stay relative "
                           "to camera forward, which is what they were "
                           "recorded as."),
    }


def bearings(concept):
    out = []
    for f in concept["terrain"]["features"]:
        out.append((f["kind"], float(f["bearing_deg"]), f.get("prominence")))
    return sorted(out, key=lambda x: x[1])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "recipes/concepts/alpine_village_01.json"
    with io.open(os.path.join(REPO, path), encoding="utf-8") as fh:
        c = json.load(fh)

    print("CAMERA SOLVE -- %s" % c["concept_id"])
    print("  site_id %s   source %s" % (c["site_id"], c["source_image"]))
    print("")
    s = solve(c)
    for k in ("fov_horizontal_deg", "fov_vertical_deg", "height_m",
              "horizon_frac", "pitch_deg"):
        print("  %-22s %s" % (k, s[k]))
    print("  %-22s %s" % ("fov_provenance", s["fov_provenance"]))
    print("")
    print("  FEATURE BEARINGS, relative to camera forward (unchanged --")
    print("  the solve fixes PITCH and FOV, it does not fix a compass yaw):")
    for kind, b, prom in bearings(c):
        print("      %-8s %+6.1f deg   %s" % (kind, b, prom))
    print("")
    print("  placements: %s"
          % ", ".join("%s %s" % (p["class"],
                                 p.get("count") or p.get("count_range"))
                      for p in c["placements"]["items"]))

    out = os.path.join(REPO, "_verify", "20260830_loop",
                       "%s_camera_solve.json" % c["concept_id"])
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump({"concept_id": c["concept_id"],
                   "source_sha256": c["source_sha256"],
                   "solve": s,
                   "feature_bearings_deg": {k: b for k, b, _p in bearings(c)}},
                  fh, indent=1)
    print("")
    print("  wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
