"""mediapipe_landmarks.py — dense face landmarks for the hero reference.

WHY THIS EXISTS, AND WHAT IT ADDS THAT WE DID NOT HAVE
    `face_metrics.py` says its own limit out loud: the MetaHuman tracker
    returns eyelids, lips, philtrum and nasolabial folds, and **NO brow
    curve, NO nose curve and NO jaw curve**. So every measurement this
    project has made about the hero's JAW came from the chroma silhouette,
    and the jaw is exactly where the sculpt was measured to stop:

        pass 2 moved the jaw +1.0% / +0.2% and the hero remains 13-22%
        wider there; the in-game face is 0.99-1.27 of the reference width

    MediaPipe returns 478 points including the full face oval, brow ridge
    and nose. That is a real instrument for the one region that has only
    ever been measured indirectly.

THE FRAME IS THE ONE THIS PROJECT ALREADY USES
    Origin at the eye midpoint, scale = interpupillary distance, rotation =
    the eye line -- identical to `face_metrics.canonical`, so the outputs
    are comparable with everything already measured rather than being a
    second, private coordinate system (non-negotiable 24).

THE INDEX CONVENTION IS CHECKED, NOT TRUSTED
    The landmark numbers below are the MediaPipe canonical face-mesh
    convention. A convention is a remembered API (non-negotiable 23), so
    `--selftest` asserts the geometry those indices MUST have on any real
    frontal face -- chin below eyes, forehead above, left/right eyes on
    opposite sides, nose between them. If the model ever renumbers, this
    refuses instead of silently measuring the wrong points.

Exit codes:
    0  landmarks written
    2  bad arguments, or the model file is missing
    3  NO FACE DETECTED -- reported as "could not look", never as a face
       with zero features
    5  the index convention selftest failed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
MODEL = os.path.join(REPO_ROOT, "hero", "models", "face_landmarker.task")

# --- MediaPipe canonical face mesh indices -------------------------------
# Eye corners, used for the canonical frame.
L_EYE_OUTER, L_EYE_INNER = 33, 133
R_EYE_OUTER, R_EYE_INNER = 263, 362
NOSE_TIP = 4
CHIN = 152
FOREHEAD = 10
# The face oval, in order. This is the curve the MetaHuman tracker cannot
# produce and the reason for this whole file.
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
# Widest points of the mandible and the cheekbones, left and right.
JAW_L, JAW_R = 172, 397          # gonion-ish
CHEEK_L, CHEEK_R = 234, 454      # zygomatic
BROW_L = [70, 63, 105, 66, 107]
BROW_R = [300, 293, 334, 296, 336]


def _load_image(path):
    import mediapipe as mp
    import cv2
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("could not read image: " + path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), w, h


def detect(image_path, model_path=MODEL):
    """-> (landmarks_px, width, height). Raises if no face is found."""
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not os.path.isfile(model_path):
        raise RuntimeError("missing model file: " + model_path)

    img, w, h = _load_image(image_path)
    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        num_faces=1,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False)
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        res = lm.detect(img)
    if not res.face_landmarks:
        # NOT an empty landmark set. "I could not look" is not "the face has
        # no features" (non-negotiable 6).
        raise LookupError("NO FACE DETECTED in " + image_path)
    pts = [(p.x * w, p.y * h, p.z * w) for p in res.face_landmarks[0]]
    return pts, w, h


def selftest(pts, w, h):
    """The index convention must produce a real face, or refuse.

    Every assertion here is about geometry any frontal portrait has, so it
    can only fail if the numbering is wrong -- which is the failure this
    guards against.
    """
    errs = []
    lx = (pts[L_EYE_OUTER][0] + pts[L_EYE_INNER][0]) / 2.0
    rx = (pts[R_EYE_OUTER][0] + pts[R_EYE_INNER][0]) / 2.0
    ly = (pts[L_EYE_OUTER][1] + pts[L_EYE_INNER][1]) / 2.0
    ry = (pts[R_EYE_OUTER][1] + pts[R_EYE_INNER][1]) / 2.0
    if not lx < rx:
        errs.append("eye indices are not left-of-right in image space "
                    "(L x=%.1f, R x=%.1f)" % (lx, rx))
    ipd = math.hypot(rx - lx, ry - ly)
    if not 0.05 * w < ipd < 0.6 * w:
        errs.append("interpupillary distance %.1f px is implausible against "
                    "an image %d px wide" % (ipd, w))
    if not pts[CHIN][1] > max(ly, ry):
        errs.append("chin (152) is not BELOW the eye line")
    if not pts[FOREHEAD][1] < min(ly, ry):
        errs.append("forehead (10) is not ABOVE the eye line")
    if not min(lx, rx) < pts[NOSE_TIP][0] < max(lx, rx):
        errs.append("nose tip (4) is not horizontally between the eyes")
    if not pts[CHIN][1] > pts[NOSE_TIP][1]:
        errs.append("chin is not below the nose tip")
    return errs, ipd


def canonical(pts):
    """Eye-midpoint origin, IPD scale, eye line horizontal.

    Same definition as face_metrics.canonical, deliberately, so these
    numbers sit in the frame everything else already uses.
    """
    lx = (pts[L_EYE_OUTER][0] + pts[L_EYE_INNER][0]) / 2.0
    ly = (pts[L_EYE_OUTER][1] + pts[L_EYE_INNER][1]) / 2.0
    rx = (pts[R_EYE_OUTER][0] + pts[R_EYE_INNER][0]) / 2.0
    ry = (pts[R_EYE_OUTER][1] + pts[R_EYE_INNER][1]) / 2.0
    ox, oy = (lx + rx) / 2.0, (ly + ry) / 2.0
    ipd = math.hypot(rx - lx, ry - ly)
    ang = math.atan2(ry - ly, rx - lx)
    ca, sa = math.cos(-ang), math.sin(-ang)
    out = []
    for (x, y, z) in pts:
        dx, dy = x - ox, y - oy
        out.append(((dx * ca - dy * sa) / ipd,
                    (dx * sa + dy * ca) / ipd,
                    z / ipd))
    return out, ipd


def proportions(c):
    """The measurements the MetaHuman tracker could not make."""
    def d(a, b):
        return math.hypot(c[a][0] - c[b][0], c[a][1] - c[b][1])
    oval_x = [c[i][0] for i in FACE_OVAL]
    oval_y = [c[i][1] for i in FACE_OVAL]
    return {
        "jaw_width": d(JAW_L, JAW_R),
        "cheek_width": d(CHEEK_L, CHEEK_R),
        "face_height_forehead_to_chin": abs(c[CHIN][1] - c[FOREHEAD][1]),
        "eye_to_chin": abs(c[CHIN][1]),
        "nose_tip_y": c[NOSE_TIP][1],
        "oval_width": max(oval_x) - min(oval_x),
        "oval_height": max(oval_y) - min(oval_y),
        "jaw_over_cheek": (d(JAW_L, JAW_R) / d(CHEEK_L, CHEEK_R)
                           if d(CHEEK_L, CHEEK_R) else None),
        "brow_y_l": sum(c[i][1] for i in BROW_L) / len(BROW_L),
        "brow_y_r": sum(c[i][1] for i in BROW_R) / len(BROW_R),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "hero",
                                                      "landmarks"))
    ap.add_argument("--labels", default=None,
                    help="comma-separated labels, one per image")
    args = ap.parse_args(argv)

    labels = (args.labels.split(",") if args.labels
              else [os.path.splitext(os.path.basename(p))[0]
                    for p in args.images])
    if len(labels) != len(args.images):
        print("REFUSE: %d labels for %d images"
              % (len(labels), len(args.images)))
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    results = {}
    for path, label in zip(args.images, labels):
        p = path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)
        print("=== %s" % os.path.relpath(p, REPO_ROOT))
        try:
            pts, w, h = detect(p, args.model)
        except LookupError as exc:
            print("   COULD NOT LOOK: %s" % exc)
            return 3
        except RuntimeError as exc:
            print("   REFUSE: %s" % exc)
            return 2

        errs, ipd = selftest(pts, w, h)
        if errs:
            print("   *** INDEX CONVENTION SELFTEST FAILED ***")
            for e in errs:
                print("     - " + e)
            return 5
        print("   %d landmarks, image %dx%d, IPD %.1f px  (selftest OK)"
              % (len(pts), w, h, ipd))

        c, _ = canonical(pts)
        pr = proportions(c)
        results[label] = pr
        for k in sorted(pr):
            print("     %-32s %s" % (k, round(pr[k], 4)
                                     if pr[k] is not None else None))

        out = os.path.join(args.out_dir, label + "_mediapipe.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"image": os.path.relpath(p, REPO_ROOT),
                       "width": w, "height": h, "ipd_px": ipd,
                       "landmarks_px": [[round(v, 3) for v in q] for q in pts],
                       "landmarks_ipd": [[round(v, 5) for v in q] for q in c],
                       "proportions": pr}, fh, indent=1)
        print("   wrote %s" % os.path.relpath(out, REPO_ROOT))

    # POSITIVE CONTROL. The two references are the SAME FACE -- the project
    # already measured them agreeing within ~3% in IPD units. If this run
    # says otherwise, the instrument is wrong, not the face.
    if len(results) == 2:
        a, b = list(results)
        print()
        print("=== AGREEMENT BETWEEN %s AND %s (same face, so this is a "
              "control on the INSTRUMENT) ===" % (a, b))
        worst = 0.0
        for k in sorted(results[a]):
            va, vb = results[a][k], results[b][k]
            if va is None or vb is None or abs(va) < 1e-9:
                continue
            r = vb / va
            worst = max(worst, abs(r - 1.0))
            print("   %-32s %8.4f / %8.4f = %.3f" % (k, vb, va, r))
        print("   worst deviation from 1.000: %.1f%%" % (worst * 100.0))
        if worst > 0.15:
            print("   *** the two views of one face disagree by more than "
                  "15%; treat these numbers as UNSAFE until that is "
                  "explained (hair occluding the jaw is the likely cause, "
                  "and is exactly why the bald frame is the shape input) ***")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
