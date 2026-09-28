"""capture_landmarks.py — dense landmarks for reference and MetaHuman, and the deltas.

TASK 1 of the likeness pipeline. Produces `deltas.json`: per-region offsets
in IPD units, plus the raw 478-point arrays for both images so every number
here is auditable against its source.

THE FRAME
    origin  midpoint of the two IRIS CENTRES (468, 473)
    unit    interpupillary distance between those same two points
    X       image +x, i.e. toward the image's right
    Z       image -y  <-- SIGN FLIP, ON PURPOSE

    Image y grows DOWNWARD; UE Z grows UP. Carrying image-y into a
    joint-space edit unflipped puts every vertical correction backwards,
    and it would look plausible the whole way. Z is negated here, once, at
    the point of measurement, and nothing downstream has to remember.

WHAT "X" DOES NOT MEAN
    X here is an IMAGE-SPACE width, and that is all it is. DNA neutral
    joint translations are PARENT-RELATIVE, so image +x is NOT known to be
    joint +x for any joint, and the relationship need not be the same for
    two joints in different regions. This file measures; the axis test
    decides what the measurements drive. Nothing here assumes a mapping.

WHY MEDIAPIPE 1.0.1 HAS NO static_image_mode / refine_landmarks FLAGS
    Those are the legacy `mp.solutions.face_mesh` parameters, and 1.0.1
    removed `mp.solutions` entirely. The tasks API's default running mode
    IS the static-image mode, and the face_landmarker model returns 478
    landmarks with irises, so refinement is already on. Rather than claim
    flags that do not exist, this ASSERTS the observable consequence: 478
    landmarks, or it stops.

THE QUALITY GATE, AND WHY EACH CHECK IS THERE
    A degraded landmark set does not look degraded in a JSON file. Each
    check below turns a specific way of being wrong into a refusal:

      478 landmarks     iris points present at all
      index selftest    chin below eyes, forehead above, eyes left-of-right,
                        nose between them -- catches a renumbered model
      roll              a "frontal" image whose eye line is tilted
      YAW PROXY         the one that matters most: a yawed MetaHuman render
                        compared against a frontal reference manufactures
                        width deltas out of perspective, and the fit would
                        then chase them with real joint moves
      symmetry residual gross left/right disagreement on a frontal view,
                        which is what a half-occluded face produces

Exit codes:
    0  measured (both images, or reference-only with --reference-only)
    2  bad arguments / missing file / missing model
    3  NO FACE DETECTED -- "could not look", never a face with no features
    5  QUALITY GATE FAILED -- landmarks are degraded; nothing is written
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DEFAULT_MANIFEST = os.path.join(HERE, "manifest.json")

# --- MediaPipe canonical face mesh indices -------------------------------
# Named so a reader can check them, and SELFTESTED below so a renumbered
# model refuses instead of measuring the wrong points (non-negotiable 23).
IRIS_L, IRIS_R = 468, 473        # iris CENTRES -- the frame
EYE_INNER_L, EYE_INNER_R = 133, 362
EYE_OUTER_L, EYE_OUTER_R = 33, 263
NOSE_TIP = 4
NASION = 168                      # bridge root, between the eyes
BRIDGE_L, BRIDGE_R = 193, 417     # bridge width
CHIN = 152
FOREHEAD = 10
JAW_L, JAW_R = 172, 397           # mandible angle (gonion)
CHEEK_L, CHEEK_R = 234, 454       # widest point (zygomatic)
TEMPLE_L, TEMPLE_R = 127, 356     # above the cheek, on the face oval
BROW_L = [70, 63, 105, 66, 107]
BROW_R = [300, 293, 334, 296, 336]
# Mirrored pairs on the face oval, for the symmetry residual.
SYM_PAIRS = [(172, 397), (234, 454), (127, 356), (33, 263), (133, 362),
             (58, 288), (93, 323), (21, 251), (54, 284), (103, 332)]

EXPECTED_LANDMARKS = 478


def detect(image_path, model_path):
    """-> (points_px, width, height). Raises LookupError if no face."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not os.path.isfile(model_path):
        raise RuntimeError("missing MediaPipe model: " + model_path)
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("could not read image: " + image_path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        # Default running mode is IMAGE == the legacy static_image_mode.
        num_faces=1,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False)
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        res = lm.detect(img)
    if not res.face_landmarks:
        raise LookupError("NO FACE DETECTED in " + image_path)
    pts = [(p.x * w, p.y * h, p.z * w) for p in res.face_landmarks[0]]
    return pts, w, h


def canonical(pts):
    """Iris-centred, IPD-scaled, eye line levelled. Z is UP (image -y).

    Returns (canonical_points, ipd_px, roll_deg).
    """
    lx, ly = pts[IRIS_L][0], pts[IRIS_L][1]
    rx, ry = pts[IRIS_R][0], pts[IRIS_R][1]
    ox, oy = (lx + rx) / 2.0, (ly + ry) / 2.0
    ipd = math.hypot(rx - lx, ry - ly)
    ang = math.atan2(ry - ly, rx - lx)
    ca, sa = math.cos(-ang), math.sin(-ang)
    out = []
    for (x, y, z) in pts:
        dx, dy = x - ox, y - oy
        rx2 = (dx * ca - dy * sa) / ipd
        ry2 = (dx * sa + dy * ca) / ipd
        # ry2 is still image-space (down-positive). NEGATE for Z-up.
        out.append((rx2, -ry2, z / ipd))
    return out, ipd, math.degrees(ang)


def quality(pts, c, w, h, ipd, roll, label):
    """Every way these landmarks could be quietly wrong, as a checklist."""
    checks, fatal = [], []

    def add(name, ok, detail, is_fatal=True):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok and is_fatal:
            fatal.append("%s: %s (%s)" % (label, name, detail))

    add("landmark_count", len(pts) == EXPECTED_LANDMARKS,
        "%d landmarks (need %d, including irises)"
        % (len(pts), EXPECTED_LANDMARKS))
    if len(pts) < max(IRIS_R, TEMPLE_R) + 1:
        return checks, fatal, {}

    add("eyes_left_of_right", pts[IRIS_L][0] < pts[IRIS_R][0],
        "iris L x=%.1f, iris R x=%.1f" % (pts[IRIS_L][0], pts[IRIS_R][0]))
    add("chin_below_eyes", c[CHIN][1] < 0.0,
        "chin Z=%.3f (must be negative: below the eye line)" % c[CHIN][1])
    add("forehead_above_eyes", c[FOREHEAD][1] > 0.0,
        "forehead Z=%.3f (must be positive)" % c[FOREHEAD][1])
    add("nose_between_eyes",
        min(c[IRIS_L][0], c[IRIS_R][0]) < c[NOSE_TIP][0] < max(c[IRIS_L][0], c[IRIS_R][0]),
        "nose tip X=%.3f between iris X %.3f and %.3f"
        % (c[NOSE_TIP][0], c[IRIS_L][0], c[IRIS_R][0]))
    add("ipd_plausible", 0.03 * w < ipd < 0.6 * w,
        "IPD %.1f px against image width %d px" % (ipd, w))
    add("roll_small", abs(roll) < 8.0,
        "eye line tilted %.2f deg from horizontal" % roll)

    # YAW PROXY. On a true frontal the nose tip sits halfway between the
    # irises. Perspective from a yawed view moves it, and every width
    # measured from that view is then wrong in a direction the fit would
    # chase with real joint translations.
    span = c[IRIS_R][0] - c[IRIS_L][0]
    frac = ((c[NOSE_TIP][0] - c[IRIS_L][0]) / span) if abs(span) > 1e-9 else 0.0
    add("yaw_small", abs(frac - 0.5) < 0.08,
        "nose tip sits %.3f of the way between the irises (0.500 is frontal)"
        % frac)

    # Symmetry residual: mirrored oval pairs should straddle X=0 evenly.
    res = [abs(c[a][0] + c[b][0]) for a, b in SYM_PAIRS]
    # NN13: an empty sample must REFUSE, not pass on a 0.0 default. Report the
    # count beside the verdict (SYM_PAIRS is fixed today, so this is a guard
    # against a future edit that empties it).
    worst = max(res) if res else float("inf")
    add("symmetry", bool(res) and worst < 0.20,
        "n=%d pairs, worst mirrored-pair X asymmetry %.3f IPD"
        % (len(res), worst))

    return checks, fatal, {"ipd_px": ipd, "roll_deg": roll,
                           "yaw_frac": frac, "worst_asymmetry": worst}


def regions(c):
    """The seven per-region measurements, all in IPD units.

    Widths are |dx| so they are sign-free. Heights are signed Z, so
    negative means BELOW the eye line -- the chin is negative and the brow
    is positive, and that is the whole point of flipping Z at measurement.
    """
    def wid(a, b):
        return abs(c[a][0] - c[b][0])

    return {
        "jaw_width": wid(JAW_L, JAW_R),
        "cheek_width": wid(CHEEK_L, CHEEK_R),
        "temple_width": wid(TEMPLE_L, TEMPLE_R),
        "nose_bridge": wid(BRIDGE_L, BRIDGE_R),
        # Intercanthal, NOT interpupillary. Interpupillary is 1.000 by
        # construction here -- it is the unit -- so using it would feed the
        # fit a delta that is identically zero and read as "already right".
        "eye_spacing": wid(EYE_INNER_L, EYE_INNER_R),
        "chin_height": c[CHIN][1],
        "brow_height": (sum(c[i][1] for i in BROW_L) +
                        sum(c[i][1] for i in BROW_R)) / float(
                            len(BROW_L) + len(BROW_R)),
    }


def measure(path, model, label):
    pts, w, h = detect(path, model)
    # The landmark-count gate must fire BEFORE canonical()/regions() index the
    # iris (473) and temple points: a short set would otherwise be an
    # IndexError (exit 1) instead of the documented QUALITY GATE (exit 5).
    if len(pts) != EXPECTED_LANDMARKS:
        checks = [{"check": "landmark_count", "ok": False,
                   "detail": "%d landmarks (need %d, including irises)"
                             % (len(pts), EXPECTED_LANDMARKS)}]
        fatal = ["%s: landmark_count: %d landmarks (need %d)"
                 % (label, len(pts), EXPECTED_LANDMARKS)]
        return {
            "label": label,
            "image": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
            "width": w, "height": h, "stats": {},
            "quality": checks, "regions": {},
            "landmarks_px": [[round(v, 3) for v in p] for p in pts],
            "landmarks_ipd_xz": [],
        }, fatal
    c, ipd, roll = canonical(pts)
    checks, fatal, stats = quality(pts, c, w, h, ipd, roll, label)
    return {
        "label": label,
        "image": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
        "width": w, "height": h,
        "stats": stats,
        "quality": checks,
        "regions": regions(c),
        "landmarks_px": [[round(v, 3) for v in p] for p in pts],
        "landmarks_ipd_xz": [[round(p[0], 5), round(p[1], 5)] for p in c],
    }, fatal


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--reference", default=None,
                    help="front reference image; defaults to the manifest's")
    ap.add_argument("--metahuman", default=None,
                    help="neutral frontal render of the CURRENT MetaHuman")
    ap.add_argument("--reference-only", action="store_true",
                    help="measure the reference alone; writes no deltas")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # A missing/malformed manifest is "bad arguments / missing file" -> exit 2,
    # not an uncaught traceback (exit 1) as the docstring documents.
    try:
        with open(args.manifest, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: cannot read manifest %s: %s" % (args.manifest, exc))
        return 2

    def _res(p):
        return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)

    try:
        model = _res(man["paths"]["mediapipe_model"])
        ref = _res(args.reference or man["paths"]["reference_image"])
    except (KeyError, TypeError) as exc:
        print("REFUSE: manifest is missing a required paths key: %s" % exc)
        return 2
    # A file NAMED deltas.json that contains no deltas is the inert-field
    # class in a filename: it reads like the pipeline's output when it is
    # half of one. Reference-only runs get their own name.
    try:
        out_path = args.out or os.path.join(
            _res(man["paths"]["landmarks_dir"]),
            "reference_landmarks.json" if args.reference_only else "deltas.json")
    except (KeyError, TypeError) as exc:
        print("REFUSE: manifest is missing paths.landmarks_dir: %s" % exc)
        return 2

    # Reference-only means no deltas by definition; a --metahuman passed
    # alongside it would otherwise write deltas into reference_landmarks.json,
    # the inverse of the inert-field name guard above. Ignore it, loudly.
    if args.reference_only and args.metahuman:
        print("NOTE: --reference-only given; ignoring --metahuman (no deltas).")
        args.metahuman = None

    if not args.metahuman and not args.reference_only:
        print("REFUSE: no --metahuman render given.")
        print()
        print("  deltas need BOTH faces. Measuring the reference alone and")
        print("  calling the result a delta would be a number about one")
        print("  image presented as a comparison of two.")
        print()
        print("  Provide a neutral frontal render of the current MetaHuman,")
        print("  or pass --reference-only to measure just the reference.")
        return 2

    payload = {"_frame": {
        "origin": "midpoint of iris centres (landmarks %d and %d)"
                  % (IRIS_L, IRIS_R),
        "unit": "interpupillary distance between those iris centres",
        "X": "image +x (toward image right)",
        "Z": "image -y, so Z is UP. The flip happens once, here.",
        "depth": "Y/depth is NOT measured this phase; frontal only.",
        "caution": "X is an IMAGE-space width. DNA neutral joint "
                   "translations are PARENT-RELATIVE, so image +x is not "
                   "known to be joint +x for any joint, and may differ "
                   "between regions. The axis test decides that, not this.",
    }}

    fatal_all = []
    try:
        r, fatal = measure(ref, model, "reference")
    except LookupError as exc:
        print("COULD NOT LOOK: %s" % exc)
        return 3
    except RuntimeError as exc:
        print("REFUSE: %s" % exc)
        return 2
    payload["reference"] = r
    fatal_all += fatal

    m = None
    if args.metahuman:
        mh = _res(args.metahuman)
        try:
            m, fatal = measure(mh, model, "metahuman")
        except LookupError as exc:
            print("COULD NOT LOOK: %s" % exc)
            print()
            print("  A MetaHuman render that MediaPipe cannot find a face in")
            print("  is usually the render, not the face: check exposure and")
            print("  that the head fills a reasonable part of the frame.")
            return 3
        except RuntimeError as exc:
            print("REFUSE: %s" % exc)
            return 2
        payload["metahuman"] = m
        fatal_all += fatal

    # ---- report ---------------------------------------------------------
    for who in ([r] + ([m] if m else [])):
        print("=== %s: %s" % (who["label"], who["image"]))
        s = who["stats"]
        print("    %dx%d px   IPD %.1f px   roll %+.2f deg   yaw_frac %.3f   "
              "asym %.3f" % (who["width"], who["height"], s.get("ipd_px", -1),
                             s.get("roll_deg", 0.0), s.get("yaw_frac", 0.0),
                             s.get("worst_asymmetry", 0.0)))
        for chk in who["quality"]:
            print("      %-22s %-4s %s" % (chk["check"],
                                           "OK" if chk["ok"] else "FAIL",
                                           chk["detail"]))
        print()

    if fatal_all:
        print("*** QUALITY GATE FAILED — LANDMARKS ARE DEGRADED ***")
        for f in fatal_all:
            print("   " + f)
        print()
        print("Nothing written. A degraded landmark set does not look")
        print("degraded downstream: it produces confident deltas that the")
        print("fit then chases with real joint translations.")
        return 5

    if m:
        # delta = reference - metahuman. POSITIVE means the reference is
        # WIDER / HIGHER than the MetaHuman, i.e. the direction the fit
        # must move. Stated here so no consumer has to infer the sign.
        payload["deltas"] = {k: round(r["regions"][k] - m["regions"][k], 6)
                             for k in r["regions"]}
        payload["_delta_sign"] = ("delta = reference - metahuman. Positive "
                                  "means the REFERENCE is wider (widths) or "
                                  "higher in Z (heights).")

        print("REGION            reference   metahuman       delta")
        for k in sorted(r["regions"]):
            print("  %-16s %9.4f   %9.4f   %+9.4f"
                  % (k, r["regions"][k], m["regions"][k],
                     payload["deltas"][k]))
        print()
        print("Units are IPD. Delta = reference - metahuman; positive means")
        print("the reference is wider/higher.")
    else:
        print("REFERENCE ONLY — no deltas written.")
        for k in sorted(r["regions"]):
            print("  %-16s %9.4f" % (k, r["regions"][k]))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print()
    print("wrote %s" % os.path.relpath(out_path, REPO_ROOT))
    print("  (includes the raw 478-point arrays for both images, in pixels")
    print("   and in the canonical XZ frame, so every number above is")
    print("   auditable against its source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
