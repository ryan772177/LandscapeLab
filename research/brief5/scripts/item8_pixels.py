#!/usr/bin/env python3
"""item8_pixels.py -- Item-8 I3 pixel fraction + I4 far-forest crops. READ-ONLY.

Inputs (per station): the last output frames from arm A1, A2 and B, collected by
item8_capture.py at _verify/perf/item8/<station>_<arm>/frame_last.png.

I3 PIXEL FRACTION.
  diff mask = |A1 - B| > THRESH. Because the ONLY difference between arm A and
  arm B is `wp.Runtime.HLOD 0`, every differing pixel is an HLOD proxy pixel,
  which is beyond the 512 m streaming band by construction. non-sky mask comes
  from the declared sky-colour band (blue-minus-red, monotonic BGR) on arm A
  (benchmark.json's method; sky is identical in both arms so it never differs).
  differing_fraction = diff_px / non_sky_px. The A/A diff (A1 vs A2) is the
  pixel NOISE FLOOR (deterministic static render -> ~0; any residue is temporal
  jitter). The fraction is quoted x that floor and compared to the derived
  proxy_fraction 0.05727 -- CORROBORATION not equality: 0.05727 was a
  depth-based beyond-512 fraction at vista at the bench FOV / 1440p, while this
  is a 90 deg / 4K differing fraction, a DIFFERENT framing and a subset (proxies
  occupy only part of the beyond-512 ground).

I4 FAR-FOREST CROPS.
  Five 512 px crops per station at target ground distances (~700/1000/1400/1800/
  2200 m) plus one 512-600 m boundary crop. Distance-to-row is the flat-ground
  camera solution (eye height / tan(down-angle)); it is APPROXIMATE (terrain is
  not flat) and declared so. Each crop is centred on the proxy-densest column in
  its row band (the A-B diff marks the proxies), taken from arm A. A repetition
  score (horizontal autocorrelation secondary peak) is a HEURISTIC hint at
  imposter tiling; the yes/no is Ryan's visual call on the crops themselves.
"""
import json
import math
import os

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(REPO, "_verify", "perf", "item8")
DERIVED = os.path.join(REPO, "research", "brief5", "derived", "item8")
INPUT = os.path.join(REPO, "research", "brief5", "input")

DIFF_THRESH = 8               # /255 per-channel; above per-frame jitter
SKY_MIN_BMR = 0.06            # blue-minus-red, benchmark.json band
CROP = 512
TARGET_DIST_M = [700, 1000, 1400, 1800, 2200]
BOUNDARY_M = 560             # 512-600 m live/HLOD boundary
DERIVED_PROXY_FRACTION = 0.05727    # vista depth-based beyond-512, bench FOV/1440p
EYE_CM = 175.0

def _stations():
    """Single-source the station pitch/yaw from the capture manifest (audit
    #11); fall back to the derivation values only if the manifest is absent."""
    p = os.path.join(INPUT, "item8_capture_manifest.json")
    if os.path.isfile(p):
        try:
            m = json.load(open(p, encoding="utf-8"))
            sts = {s["name"]: {"pitch_deg": float(s["pitch_deg"]),
                               "yaw_deg": float(s["yaw_deg"])}
                   for s in (m.get("stations") or [])}
            if sts:
                return sts
        except Exception:
            pass
    return {"vista": {"pitch_deg": -4.0, "yaw_deg": 60.0},
            "treeline": {"pitch_deg": -2.0, "yaw_deg": 105.0}}


STATIONS = _stations()


def _load(station, arm):
    p = os.path.join(OUT, "%s_%s" % (station, arm), "frame_last.png")
    if not os.path.isfile(p):
        p2 = os.path.join(OUT, "%s_%s_lo" % (station, arm), "frame_last.png")
        p = p2 if os.path.isfile(p2) else p
    if not os.path.isfile(p):
        return None, None
    im = Image.open(p).convert("RGB")
    return np.asarray(im).astype(np.int16), p


def _sky_mask(rgb):
    a = rgb.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (b - r >= SKY_MIN_BMR) & (b >= g) & (g >= r)


def _row_distance_m(h, w, pitch_deg, fov_h_deg=90.0):
    """Flat-ground horizontal distance for each image row (approximate)."""
    aspect = w / float(h)
    vfov = 2.0 * math.degrees(math.atan(
        math.tan(math.radians(fov_h_deg / 2.0)) / aspect))
    eye_m = EYE_CM / 100.0
    dist = np.full(h, np.inf)
    for py in range(h):
        phi = (0.5 - (py + 0.5) / h) * vfov          # + = up from centre
        down = -(pitch_deg + phi)                    # degrees below horizontal
        if down > 0.05:
            dist[py] = eye_m / math.tan(math.radians(down))
    return dist


def _repetition_score(crop_gray):
    """Max normalised horizontal autocorrelation over lags 4..64 (excl 0)."""
    a = crop_gray.astype(np.float32)
    a = a - a.mean()
    denom = float((a * a).sum()) or 1.0
    best = 0.0
    n = a.shape[1]
    for lag in range(4, min(65, n)):
        c = float((a[:, :n - lag] * a[:, lag:]).sum()) / denom
        best = max(best, c)
    return round(best, 4)


def _pixel_fraction(station):
    A1, pA1 = _load(station, "A1")
    A2, pA2 = _load(station, "A2")
    B, pB = _load(station, "B")
    if A1 is None or B is None:
        return {"error": "missing A1 or B frame"}, None, None
    if A1.shape != B.shape:
        return {"error": "A1 %s vs B %s shape mismatch" % (A1.shape, B.shape)}, \
            None, None
    h, w, _ = A1.shape
    sky = _sky_mask(A1)
    non_sky = ~sky
    n_non_sky = int(non_sky.sum())
    diff_ab = (np.abs(A1 - B).max(axis=2) > DIFF_THRESH) & non_sky
    n_diff = int(diff_ab.sum())
    res = {
        "frame_shape": [h, w],
        "arm_A1": os.path.relpath(pA1, REPO).replace("\\", "/"),
        "arm_B": os.path.relpath(pB, REPO).replace("\\", "/"),
        "non_sky_px": n_non_sky,
        "diff_px_A_vs_B": n_diff,
        "differing_fraction": round(n_diff / n_non_sky, 5) if n_non_sky else None,
        "diff_thresh_per_channel": DIFF_THRESH,
    }
    if A2 is not None and A2.shape == A1.shape:
        diff_aa = (np.abs(A1 - A2).max(axis=2) > DIFF_THRESH) & non_sky
        n_aa = int(diff_aa.sum())
        res["arm_A2"] = os.path.relpath(pA2, REPO).replace("\\", "/")
        res["diff_px_AA_floor"] = n_aa
        res["aa_floor_fraction"] = round(n_aa / n_non_sky, 5) if n_non_sky else None
        res["differing_x_aa_floor"] = (round(n_diff / n_aa, 1) if n_aa
                                       else "inf (A/A diff is 0 px)")
    else:
        # N2: declare the missing floor rather than leaving the keys silently
        # absent (a dropped noise floor must not read as "no floor needed").
        res["aa_floor"] = ("unavailable (A2 %s)" % (
            "missing" if A2 is None else "shape mismatch %s vs %s"
            % (A2.shape, A1.shape)))
        res["differing_x_aa_floor"] = None
    res["derived_proxy_fraction_reference"] = DERIVED_PROXY_FRACTION
    res["_comparison_note"] = ("differing_fraction vs 0.05727 is CORROBORATION, "
                               "not equality: different framing (90/4K here vs "
                               "bench FOV/1440p depth there) and a subset "
                               "(proxies are part of the beyond-512 ground).")
    return res, A1, diff_ab


def _crops(station, A1, diff_ab):
    if A1 is None:
        return {"error": "no arm-A frame for crops"}
    h, w, _ = A1.shape
    gray = np.asarray(Image.fromarray(A1.astype(np.uint8)).convert("L"))
    rowdist = _row_distance_m(h, w, STATIONS[station]["pitch_deg"])
    os.makedirs(DERIVED, exist_ok=True)
    crops = []

    max_flat = float(np.max(rowdist[np.isfinite(rowdist)])) \
        if np.isfinite(rowdist).any() else 0.0

    def crop_at(target_m, label):
        # nearest row whose flat-ground distance matches the target
        finite = np.isfinite(rowdist)
        if not finite.any():
            return {"target_m": target_m, "error": "no finite ground rows"}
        row = int(np.argmin(np.where(finite, np.abs(rowdist - target_m), 1e9)))
        # beyond the flat-ground horizon (~max_flat m at this pitch) the target
        # cannot be placed by distance; the crop lands in the near-horizon band
        # instead. Flagged, not hidden (rule 10) -- rising alpine terrain puts
        # far forest ABOVE the flat-ground horizon, so exact distance there
        # needs a depth pass this run did not take.
        beyond = target_m > max_flat
        cy = min(max(row, CROP // 2), h - CROP // 2)
        # centre column on the proxy-densest column within the crop's row band
        band = diff_ab[max(0, cy - CROP // 2):cy + CROP // 2, :]
        colsum = band.sum(axis=0)
        cx = int(np.argmax(colsum)) if colsum.max() > 0 else w // 2
        cx = min(max(cx, CROP // 2), w - CROP // 2)
        x0, y0 = cx - CROP // 2, cy - CROP // 2
        sub = A1[y0:y0 + CROP, x0:x0 + CROP].astype(np.uint8)
        subg = gray[y0:y0 + CROP, x0:x0 + CROP]
        fn = "crop_%s_%s.png" % (station, label)
        Image.fromarray(sub).save(os.path.join(DERIVED, fn))
        proxy_px = int(diff_ab[y0:y0 + CROP, x0:x0 + CROP].sum())
        return {"target_m": target_m, "label": label,
                "approx_row_dist_m": round(float(rowdist[row]), 1),
                "target_beyond_flatground_horizon": bool(beyond),
                "max_flatground_dist_m": round(max_flat, 1),
                "crop_px": [x0, y0, CROP, CROP],
                "proxy_px_in_crop": proxy_px,
                "proxy_frac_in_crop": round(proxy_px / (CROP * CROP), 4),
                "repetition_score": _repetition_score(subg),
                "file": "research/brief5/derived/item8/" + fn,
                "_tiling": "REVIEW crop visually -- repetition_score is a hint, "
                           "not a verdict"}

    crops.append(crop_at(BOUNDARY_M, "boundary_512_600m"))
    for d in TARGET_DIST_M:
        crops.append(crop_at(d, "%dm" % d))
    return {"station": station,
            "_distance_method": "flat-ground eye/tan(down-angle); APPROXIMATE "
                                "(terrain not flat), declared per rule 10",
            "crops": crops}


def main():
    out = {"_what": "Item-8 I3 pixel fraction + I4 far-forest crops.",
           "stations": {}}
    for st in STATIONS:
        frac, A1, diff_ab = _pixel_fraction(st)
        crops = _crops(st, A1, diff_ab) if A1 is not None else {
            "error": "no frames"}
        out["stations"][st] = {"pixel_fraction_I3": frac, "crops_I4": crops}
        print("%-9s differing_frac %s (x%s floor)  vs 0.05727" % (
            st, frac.get("differing_fraction"),
            frac.get("differing_x_aa_floor")))
    p = os.path.join(INPUT, "item8_pixels.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    print("wrote", os.path.relpath(p, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
