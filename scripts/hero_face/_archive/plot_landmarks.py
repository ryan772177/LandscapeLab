"""plot_landmarks.py — draw the 79 sculpt landmarks so their anatomy is SEEN, not assumed.

X is lateral and Z is up (established by the bilateral-symmetry test in
analyse_landmarks.py), so an orthographic X-Z scatter of the landmark cloud
IS a front view of the face, and a Y-Z scatter IS the profile. Plotting them
identifies the eyes, nose, mouth and jaw by their arrangement.

This exists because the alternative was assigning anatomy to indices by
reasoning about extremes -- which I tried, and which produced a nose-to-chin
distance of 13.7 cm against a scale that three independent axis ratios agree
on. The arithmetic was fine; the premise was invented. Looking is cheaper
than being wrong.

Usage: python scripts/hero_face/plot_landmarks.py [--state PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(
        here, "..", "..", "hero", "generated", "face_state_baseline.json"))
    ap.add_argument("--out", default=os.path.join(
        here, "..", "..", "_verify", "20260816_face_landmarks_indexed.png"))
    ap.add_argument("--label-every", type=int, default=1)
    ap.add_argument("--w", type=int, default=620)
    ap.add_argument("--h", type=int, default=760)
    ap.add_argument("--front-only", action="store_true")
    args = ap.parse_args(argv)

    with open(args.state, "r") as fh:
        pts = json.load(fh)["landmarks"]
    n = len(pts)
    if not n:
        print("REFUSE: no landmarks")
        return 1

    PAD, W, H = 60, args.w, args.h
    npanel = 1 if args.front_only else 2
    img = Image.new("RGB", (W * npanel, H), (18, 18, 22))
    d = ImageDraw.Draw(img)

    def panel(ox, hor, ver, title, flip_h):
        hs = [p[hor] for p in pts]
        vs = [p[ver] for p in pts]
        lo_h, hi_h = min(hs), max(hs)
        lo_v, hi_v = min(vs), max(vs)
        # one shared scale on both axes, so the drawing keeps the real aspect
        # ratio -- a face stretched to fill a box is a different face.
        sc = min((W - 2 * PAD) / (hi_h - lo_h), (H - 2 * PAD) / (hi_v - lo_v))
        cx_h, cx_v = (lo_h + hi_h) / 2.0, (lo_v + hi_v) / 2.0

        def to_px(p):
            x = (p[hor] - cx_h) * sc
            if flip_h:
                x = -x
            # +ver is up, screen y grows down
            return (ox + W / 2 + x, H / 2 - (p[ver] - cx_v) * sc)

        d.text((ox + 12, 10), title, fill=(220, 220, 120))
        d.text((ox + 12, 26), "scale %.0f px/unit" % sc, fill=(120, 120, 140))
        for i, p in enumerate(pts):
            x, y = to_px(p)
            r = 3.5
            d.ellipse([x - r, y - r, x + r, y + r],
                      fill=(90, 200, 255), outline=(255, 255, 255))
            if i % args.label_every == 0:
                d.text((x + 5, y - 6), str(i), fill=(255, 210, 120))

    # front view: mirror horizontally so the image reads like a photograph
    # (subject's right on the viewer's left)
    panel(0, 0, 2, "FRONT  (X lateral, Z up)", True)
    if not args.front_only:
        panel(W, 1, 2, "PROFILE  (Y depth ->, Z up)", False)
        d.line([(W, 0), (W, H)], fill=(70, 70, 80))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    img.save(args.out)
    print("wrote %s  (%d landmarks)" % (args.out, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
