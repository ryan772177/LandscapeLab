"""plan_face_sculpt.py — turn the hero's measured face into landmark deltas.

=====================================================================
WHY REGIONS AND NOT INDICES
=====================================================================
The anatomy of the 79 sculpt landmarks was read off an orthographic plot and
cross-checked against the profile view. That reading is good but it is a
READING, and a mis-assigned index silently moves the wrong feature.

So nothing here names an index. Every region is a PREDICATE over normalised
head coordinates:

    u = (x - x_sagittal) / half_width     -1 (subject's left) .. +1
    v = (z - z_min)      / z_span          0 (under-chin) .. 1 (crown)
    w = (y - y_min)      / y_span          0 (back of head) .. 1 (nose tip)

A predicate cannot be off by one. It also prints which landmarks it caught,
so the selection is checkable against the plot before anything is applied.

=====================================================================
WHY FRACTIONS AND NOT CENTIMETRES
=====================================================================
The landmark unit does not reconcile with a real face: nose-tip-to-chin
implies 222 cm/unit, forehead-to-chin 315, tip-to-subnasale over 400. Three
inconsistent answers means these points are a CONTROL CAGE, not surface
positions, and any delta expressed in centimetres would be a number derived
from a premise the data refuses.

Every move below is therefore a fraction of the head's own extent on that
axis, which is well defined whatever a unit is worth.

=====================================================================
WHAT IS MEASURED AND WHAT IS AUTHORED -- the honest split
=====================================================================
MEASURED, from the reference photographs:
  * lateral proportions (skull, cheek and jaw width at height) -- from the
    bald portrait's chroma silhouette, scripts/hero_face/measure_reference_silhouette.py
  * mouth width, lip thickness, eye size and eye-to-mouth distance -- from
    the tracked contour curves, in interpupillary units, and confirmed to
    agree between the bald and haired references to within ~3%.

AUTHORED, and declared as such because no frontal photograph carries it:
  * every DEPTH (+Y) move -- brow protrusion, eye recession, nose projection,
    chin projection. A single frontal view has no depth information at all.
    These come from reading the shading in the reference and are design
    decisions, not measurements. They are the values most worth revisiting.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# name, predicate(u, v, w), (du, dv, dw) as fractions of half_width / z_span /
# y_span, and a note recording whether the amount is measured or authored.
REGIONS = [
    ("crown_dome",
     lambda u, v, w: v >= 0.92,
     (0.0, 0.030, 0.0),
     "MEASURED-ish: the bald reference's cranium is tall and domed; raise the "
     "crown. Silhouette width/W is still 0.87 at d/W 0.40-0.50, a broad skull."),

    ("upper_skull_width",
     lambda u, v, w: v >= 0.70 and abs(u) > 0.35,
     (0.045, 0.0, 0.0),
     "MEASURED: hero silhouette holds 0.874 of cranium width from d/W 0.40 to "
     "0.50, i.e. the skull stays broad well above the ears."),

    ("brow_ridge",
     lambda u, v, w: 0.60 <= v < 0.72 and w > 0.45,
     (0.0, -0.012, 0.038),
     "AUTHORED (depth): the reference's defining feature is a heavy, "
     "low-set brow shelf. Forward and slightly down. No frontal image "
     "measures protrusion."),

    ("eye_recession",
     lambda u, v, w: 0.55 <= v < 0.66 and abs(u) > 0.25 and w > 0.45,
     (0.0, 0.0, -0.022),
     "AUTHORED (depth): deep-set eyes under that brow. Pushed back."),

    ("cheekbone_width",
     lambda u, v, w: 0.42 <= v < 0.60 and abs(u) > 0.55,
     (0.040, 0.0, 0.0),
     "MEASURED: silhouette 0.985-1.0 of cranium width at d/W 0.60-0.70, "
     "the widest part of the face below the skull."),

    ("nose_bridge",
     lambda u, v, w: 0.50 <= v < 0.60 and abs(u) < 0.22 and w > 0.75,
     (0.0, 0.0, 0.030),
     "AUTHORED (depth): a long straight dorsum, prominent in the reference."),

    ("nose_tip",
     lambda u, v, w: 0.40 <= v < 0.50 and abs(u) < 0.22 and w > 0.80,
     (0.0, -0.016, 0.045),
     "AUTHORED (depth): tip carried forward and slightly down, which is what "
     "makes the nose read as long rather than merely large."),

    ("jaw_width",
     lambda u, v, w: 0.10 <= v < 0.30 and abs(u) > 0.45,
     (0.075, 0.0, 0.0),
     "MEASURED: the hero's silhouette is still 0.90 of cranium width at "
     "d/W 0.85 and 0.85 at 0.90 -- the mandible stays broad far down the "
     "face. This is the square jaw and it is the largest single move here."),

    ("chin_projection",
     lambda u, v, w: v < 0.22 and abs(u) < 0.30 and w > 0.55,
     (0.0, 0.0, 0.028),
     "AUTHORED (depth): a firm forward chin. Frontal photograph cannot "
     "measure it."),

    ("mouth_width",
     lambda u, v, w: 0.26 <= v < 0.40 and abs(u) > 0.30,
     (0.035, -0.008, 0.0),
     "MEASURED: mouth_width 0.888 IPD on the bald reference and 0.862 on the "
     "haired one, against a MetaHuman default that is narrower; corners also "
     "sit low, so the same region carries a small downward move."),
]


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(
        root, "hero", "generated", "face_state_baseline.json"))
    ap.add_argument("--out", default=os.path.join(
        root, "hero", "generated", "face_sculpt_spec.json"))
    ap.add_argument("--gain", type=float, default=1.0,
                    help="scale every move; 0.5 halves the sculpt")
    args = ap.parse_args(argv)

    pts = json.load(open(args.state))["landmarks"]
    n = len(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    x_sag = sum(xs) / n
    half_w = max(abs(x - x_sag) for x in xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    y_span, z_span = y_max - y_min, z_max - z_min

    print("head frame")
    print("  sagittal x %.5f   half width %.5f" % (x_sag, half_w))
    print("  y span     %.5f   z span     %.5f" % (y_span, z_span))
    print("  gain       %.2f" % args.gain)
    print("")

    deltas = {}
    membership = {}
    for name, pred, (du, dv, dw), note in REGIONS:
        hit = []
        for i, p in enumerate(pts):
            u = (p[0] - x_sag) / half_w
            v = (p[2] - z_min) / z_span
            w = (p[1] - y_min) / y_span
            if pred(u, v, w):
                hit.append(i)
                # lateral moves are OUTWARD: sign follows the side the point
                # is on, so a single positive du widens rather than shifting
                # the whole face sideways.
                sx = (1.0 if u >= 0 else -1.0)
                d = [sx * du * half_w * args.gain,
                     dw * y_span * args.gain,
                     dv * z_span * args.gain]
                cur = deltas.get(i, [0.0, 0.0, 0.0])
                deltas[i] = [cur[k] + d[k] for k in range(3)]
        membership[name] = hit
        print("%-18s %2d landmarks  du=%+.3f dv=%+.3f dw=%+.3f"
              % (name, len(hit), du, dv, dw))
        print("   %s" % note.replace("\n", " "))
        print("   indices: %s" % (hit if hit else "NONE -- predicate caught nothing"))
        print("")

    # ------------------------------------------------------------------
    # SYMMETRISE. Region predicates have edges, and a landmark can fall on
    # the wrong side of one while its mirror partner does not: the first run
    # caught nose wing 45 without 67, and jaw points 3 and 30 without 43 and
    # 63. Applied as-is that sculpts a CROOKED FACE -- a defect that is
    # instantly visible and tedious to undo.
    #
    # Rather than hand-tune predicates until the edges happen to line up
    # (which would need re-tuning on any future edit), the delta field is
    # made symmetric by construction: each landmark is paired with its mirror
    # across the sagittal plane and the pair receives the averaged move, with
    # the lateral component negated for the partner. A frontal reference
    # carries no information about left/right difference anyway, so a
    # symmetric sculpt is also the honest one.
    # ------------------------------------------------------------------
    partner = {}
    unpaired = []
    for i, p in enumerate(pts):
        mir = (2.0 * x_sag - p[0], p[1], p[2])
        best, bd = None, None
        for j, q in enumerate(pts):
            d = sum((mir[k] - q[k]) ** 2 for k in range(3)) ** 0.5
            if bd is None or d < bd:
                best, bd = j, d
        # tolerance scaled to the cloud: the symmetry test measured a median
        # mirror residual of 0.7% of the lateral span, so 5% is generous
        # while still refusing a point that has no real partner.
        if bd is not None and bd <= 0.05 * (2.0 * half_w):
            partner[i] = best
        else:
            unpaired.append(i)

    sym = {}
    for i in range(n):
        j = partner.get(i)
        di = deltas.get(i, [0.0, 0.0, 0.0])
        if j is None:
            sym[i] = di
            continue
        dj = deltas.get(j, [0.0, 0.0, 0.0])
        # partner's lateral component mirrors back onto this side
        sym[i] = [(di[0] + (-dj[0])) * 0.5,
                  (di[1] + dj[1]) * 0.5,
                  (di[2] + dj[2]) * 0.5]
    before = len(deltas)
    deltas = {i: d for i, d in sym.items()
              if sum(c * c for c in d) > 1e-16}

    print("SYMMETRY")
    print("  paired          : %d of %d landmarks" % (len(partner), n))
    if unpaired:
        print("  UNPAIRED        : %s (left unsymmetrised)" % unpaired)
    print("  moved before/after symmetrisation: %d -> %d" % (before, len(deltas)))
    resid = 0.0
    for i, d in deltas.items():
        j = partner.get(i)
        if j is None or j not in deltas:
            continue
        e = deltas[j]
        resid = max(resid, abs(d[0] + e[0]), abs(d[1] - e[1]), abs(d[2] - e[2]))
    print("  worst residual asymmetry after fix: %.3e units" % resid)
    print("")

    empty = [k for k, v in membership.items() if not v]
    if empty:
        print("WARNING: %d region(s) caught no landmark: %s"
              % (len(empty), ", ".join(empty)))
        print("A region that selects nothing is a silent no-op, not a subtle")
        print("sculpt. Widen the predicate or drop the region deliberately.")
        print("")

    mags = sorted((sum(d[k] ** 2 for k in range(3)) ** 0.5)
                  for d in deltas.values())
    print("landmarks moved : %d of %d" % (len(deltas), n))
    if mags:
        print("move magnitude  : median %.6f  max %.6f units"
              % (mags[len(mags) // 2], mags[-1]))
        print("                : max is %.1f%% of the head's z span"
              % (100.0 * mags[-1] / z_span))

    # Emit TARGET POSITIONS, not offsets. Pipeline rule 3 wants idempotent
    # scripts, and an offset spec is the opposite: applying it twice sculpts
    # the face twice, with no way to tell from the result that it happened.
    # With absolute targets the applier computes (target - current), so a
    # second run is a no-op and a partially-applied run finishes correctly.
    targets = {str(i): [pts[i][k] + deltas[i][k] for k in range(3)]
               for i in deltas}

    json.dump({"source_state": os.path.relpath(args.state, root).replace("\\", "/"),
               "gain": args.gain,
               "frame": {"sagittal_x": x_sag, "half_width": half_w,
                         "y_span": y_span, "z_span": z_span},
               "membership": membership,
               "baseline": {str(i): pts[i] for i in deltas},
               "deltas": {str(k): v for k, v in deltas.items()},
               "targets": targets},
              open(args.out, "w"), indent=2)
    print("")
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
