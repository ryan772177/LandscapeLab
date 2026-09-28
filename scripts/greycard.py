"""greycard.py — the 18% neutral reference card, placed and measured.

RULED BY RYAN 2026-09-10. highlight_tint measured on the sunlit meadow
was measuring GRASS ALBEDO, not the grade (LESSONS 2026-09-09e; Brief 2b
confirmed it at a third white balance). The instrument is replaced: one
small 18% grey LIT plane per bench station (label Bench_GreyCard_<st>),
lower-right of frame, angled on the camera/sun bisector so it is sunlit;
highlight_tint and WB are measured on ITS pixel region, and the scene
metrics mask that region out (featureless / haze / palette-derived
tints take --greycard exclusion).

  python scripts/greycard.py --place            # editor: spawn + save cards
  python scripts/greycard.py --measure FRAME --station near_ground

--place also writes `_verify/bench/greycard_regions.json`: the per-station
pixel rect, PROJECTED FROM READ-BACK STATE (the card and camera transforms
the engine returned, not the request), through the ruled camera model
(hfov 90, 3840x2160; f = W/2). Stations' cameras are fixed actors, so the
region is stable until a camera or card moves — the file records the
transforms it was derived from so staleness is checkable.

WB ON THE CARD. The card's albedo is neutral by construction, so any
channel imbalance in its SUNLIT pixels is the light+grade chain, not the
surface: wb_ratio_R = R/G and wb_ratio_B = B/G on the card median are
direct white-balance error readings (1.0 = neutral).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

REPO = bootstrap.REPO_ROOT
REGIONS = os.path.join(REPO, "_verify", "bench", "greycard_regions.json")
RES = (3840, 2160)
# THE INNER CROP, AS ONE DECLARATION. The recorded rect is the projected
# AABB of a ROTATED card, so its corners hold background and its edges
# hold AA blend -- only the central fraction is card. `exr_card` measures
# the same cards on the scene-linear pass and must crop identically;
# importing this constant is what stops the two from drifting into "two
# lists that must agree" (NN24). Measured consequence of getting it
# wrong: the full rect is 66,443 px of which only 23,976 are card, so a
# median over the whole rect returns the BACKGROUND.
INNER_FRAC = 0.6


def inner_rect(rect, inner_frac=INNER_FRAC):
    """The card-only sub-rect of a recorded region."""
    x0, y0, x1, y1 = rect
    mx = (x1 - x0) * (1 - inner_frac) / 2.0
    my = (y1 - y0) * (1 - inner_frac) / 2.0
    return (int(x0 + mx), int(y0 + my), int(x1 - mx), int(y1 - my))
HFOV_DEG = 90.0
STATIONS = ["near_ground", "mid_slope", "vista"]
DIST_CM = 300.0
SCALE = 0.3
HALF_CM = 50.0  # engine Plane is 100x100 cm


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def project_rect(cam, card):
    """Pixel AABB of the card's four corners through the ruled camera.

    f = (W/2)/tan(hfov/2) = W/2 at 90 deg. Basis vectors come from the
    ENGINE's read-back (camera actor forward/right/up), so no yaw/pitch
    convention is re-derived here.
    """
    W, H = RES
    f = (W / 2.0) / math.tan(math.radians(HFOV_DEG) / 2.0)
    cp, fwd, rgt, up = (cam["loc_cm"], cam["forward"], cam["right"],
                        cam["up"])
    half = HALF_CM * card["scale"]
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            corners.append([
                card["loc_cm"][i]
                + sx * half * card["forward"][i]
                + sy * half * card["right"][i]
                for i in range(3)])
    px = []
    for c in corners:
        d = [c[i] - cp[i] for i in range(3)]
        z = _dot(d, fwd)
        if z <= 1.0:
            raise ValueError("card corner behind the camera (z=%.1f)" % z)
        x = _dot(d, rgt)
        y = _dot(d, up)
        px.append((W / 2.0 + f * x / z, H / 2.0 - f * y / z))
    xs = [p[0] for p in px]
    ys = [p[1] for p in px]
    x0, x1 = max(0, int(min(xs))), min(W, int(math.ceil(max(xs))))
    y0, y1 = max(0, int(min(ys))), min(H, int(math.ceil(max(ys))))
    if x1 - x0 < 24 or y1 - y0 < 24:
        raise ValueError("projected card region %dx%d is too small to "
                         "measure" % (x1 - x0, y1 - y0))
    return [x0, y0, x1, y1]


def place(timeout):
    rec = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                         encoding="utf-8-sig"))
    sun = rec["lighting"]["sun"]
    text = open(os.path.join(REPO, "scripts", "payloads",
                             "greycard_place.py"), encoding="utf-8").read()
    for k, v in (("STATIONS", repr(STATIONS)),
                 ("SUN_AZ", str(float(sun["azimuth_deg"]))),
                 ("SUN_EL", str(float(sun["elevation_deg"]))),
                 ("DIST_CM", str(DIST_CM)), ("SCALE", str(SCALE))):
        text = text.replace("__" + k + "__", v)
    code, d, raw = ue_exec.run(text, marker="__LL__", timeout=timeout,
                               stage_name="ll_greycard_place", quiet=True)
    # Gate on HARD failure only, not the payload's aggregate `ok`.
    # greycard_place sets `ok = all(station ok)` (:228), so a single bad
    # station (no camera actor, no rotation constructor) would flip `ok`
    # False and, under the old `not d.get("ok")` gate, skip the whole
    # per-station loop and the regions file -- the exact discard AUDIT F2
    # (below) says must not happen, since the spawns already ran editor-side.
    # A hard failure is d is None (no marker), a payload exception
    # (d["error"]/["trace"]), or a malformed reply missing "stations".
    if d is None or "stations" not in d or d.get("error"):
        print("FAIL: placement payload did not complete cleanly:")
        print(json.dumps(d, indent=1)[:2000] if d else raw[-1500:])
        return 4
    print("material: %s" % d["material"])
    regions = {"_what": ("Grey-card pixel regions per station, projected "
                         "from READ-BACK transforms through the ruled "
                         "camera (hfov 90, %dx%d). Regenerate with "
                         "--place whenever a station camera or card "
                         "moves." % RES),
               "camera_model": {"res": list(RES), "hfov_deg": HFOV_DEG},
               "stations": {}}
    for st, row in d["stations"].items():
        if not row.get("ok"):
            print("  %-12s FAILED: %s" % (st, row.get("error")))
            continue
        # AUDIT 2026-09-10 F2: one bad station must not discard the
        # others' results or skip the regions file -- the spawns already
        # happened editor-side.
        try:
            rect = project_rect(row["camera"], row["card"])
        except ValueError as exc:
            print("  %-12s PROJECTION REFUSED: %s" % (st, exc))
            continue
        regions["stations"][st] = {
            "rect_px": rect,
            "card": row["card"], "camera": row["camera"],
            "rot_via": row.get("rot_via"), "state": row.get("state")}
        print("  %-12s %-8s rect_px %s  dist %.0f cm  (rot via %s)"
              % (st, row.get("state"), rect,
                 row["card"]["dist_from_cam_cm"], row.get("rot_via")))
    save = d.get("save") or {}
    print("save: marked %s saved %s packages %s"
          % (save.get("marked"), save.get("saved"),
             len(save.get("packages") or [])))
    os.makedirs(os.path.dirname(REGIONS), exist_ok=True)
    with open(REGIONS, "w", encoding="utf-8") as fh:
        json.dump(regions, fh, indent=1)
    print("wrote %s" % os.path.relpath(REGIONS, REPO))
    return 0 if len(regions["stations"]) == len(STATIONS) else 4


def region_for(station):
    """The station's card rect, or None if the regions file or station is
    absent OR the file is unreadable/corrupt (any read failure = no card;
    measure() then fails closed with 'run --place first')."""
    try:
        j = json.load(open(REGIONS, encoding="utf-8"))
        return j["stations"][station]["rect_px"]
    except Exception:
        return None


def measure(frame, station, inner_frac=INNER_FRAC):
    import numpy as np
    from PIL import Image
    rect = region_for(station)
    if rect is None:
        return {"error": "no grey-card region recorded for %r -- run "
                         "--place first" % station}
    # inner region only: the projected AABB includes background at the
    # rotated card's corners, and edge pixels carry AA blend.
    ix0, iy0, ix1, iy1 = inner_rect(rect, inner_frac)
    srgb = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64) / 255.0
    # AUDIT 2026-09-10 F1: exact shape, both directions. A LARGER frame
    # would sample the recorded rect at the wrong image location and
    # return a plausible number from the wrong pixels.
    if srgb.shape[:2] != (RES[1], RES[0]):
        return {"error": "frame is %sx%s, the recorded regions are for "
                         "%sx%s -- wrong resolution class"
                         % (srgb.shape[1], srgb.shape[0], RES[0], RES[1])}
    px = srgb[iy0:iy1, ix0:ix1].reshape(-1, 3)
    lin = np.where(px <= 0.04045, px / 12.92,
                   ((px + 0.055) / 1.055) ** 2.4)
    med = np.median(lin, axis=0)
    luma = 0.2126 * med[0] + 0.7152 * med[1] + 0.0722 * med[2]
    out = {"frame": frame.replace("\\", "/"), "station": station,
           "rect_px": rect, "inner_px": [ix0, iy0, ix1, iy1],
           "pixels": int(px.shape[0]),
           "card_median_linear": [round(float(v), 5) for v in med],
           "card_luma": round(float(luma), 5)}
    if luma <= 0.0:
        out["error"] = "card reads black -- not sunlit or not in frame"
        return out
    out["highlight_tint_R"] = round(float(med[0] / luma), 4)
    out["highlight_tint_G"] = round(float(med[1] / luma), 4)
    out["highlight_tint_B"] = round(float(med[2] / luma), 4)
    if med[1] > 0:
        out["wb_ratio_R"] = round(float(med[0] / med[1]), 4)
        out["wb_ratio_B"] = round(float(med[2] / med[1]), 4)
    # Occlusion guard (audit 2026-09-10 QUESTION): the card is a constant
    # plane, so its inner region must be near-uniform. Scene content in
    # the rect (an occluder, a mis-projection) carries structure. The
    # 0.10 ceiling is PROVISIONAL-GENEROUS -- calibrate it down from the
    # first good capture's measured std, which is always reported.
    lum_px = 0.2126 * lin[:, 0] + 0.7152 * lin[:, 1] + 0.0722 * lin[:, 2]
    out["card_luma_std"] = round(float(lum_px.std()), 5)
    if out["card_luma_std"] > 0.10:
        out["error"] = ("card region is not uniform (luma std %.4f > "
                        "0.10 provisional ceiling) -- occluded or "
                        "mis-projected; not a card reading"
                        % out["card_luma_std"])
        return out
    # Band RULED 2026-09-10: the Brief 2b acceptance (highlight_tint R,B
    # 0.85-1.15) carried onto the card by the grey-card ruling -- the
    # card is now the surface that acceptance is ABOUT.
    out["acceptance"] = ("highlight_tint R,B in 0.85-1.15 on the card "
                         "(ruled 2026-09-10)")
    r_ok = 0.85 <= out["highlight_tint_R"] <= 1.15
    b_ok = 0.85 <= out["highlight_tint_B"] <= 1.15
    out["verdict"] = "PASS" if (r_ok and b_ok) else "FAIL"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--place", action="store_true")
    ap.add_argument("--measure", metavar="FRAME")
    ap.add_argument("--station")
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=25.0)
    a = ap.parse_args(argv)
    if a.place:
        return place(a.timeout)
    if a.measure:
        if not a.station:
            ap.error("--measure needs --station")
        r = measure(a.measure, a.station)
        print(json.dumps(r, indent=1))
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(r, fh, indent=1)
            print("wrote %s" % a.out)
        return 0 if "error" not in r else 4
    ap.error("give --place or --measure")


if __name__ == "__main__":
    raise SystemExit(main())
