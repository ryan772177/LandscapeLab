"""surface_tables.py — Brief 3 Task 3 / ruling 4b: the per-layer TILING
and ALBEDO tables, on the PLACEHOLDER layer set.

    python scripts/surface_tables.py --frames <dir> --station ground
        [--out J]
    python scripts/surface_tables.py --selftest

TILING  per layer, `tiling_score`'s autocorrelation repeat at the derived
        5.03 m tile's ON-SCREEN period for that crop's distance, against
        the CSF repeat threshold `texel_budget` gives for the same
        distance. Verdict per layer.
ALBEDO  per layer, mean SCENE-LINEAR RGB over the 50-300 m crop, the
        ratio to the 0.18 grey card, and a stated reference band.

⛔ EVERY ROW SAYS "placeholder". The layer set is bound to ambientCG and
Megascans stand-ins; Ryan's six 4K scans are still on his desk. A number
measured against a placeholder is a number about the placeholder.

⛔ AND THE ALBEDO COLUMN IS A LIT VALUE, NOT AN ALBEDO. The card that
calibrates 0.18 sits at near_ground, not here, and these pixels are 50-300 m
away on slopes of their own. Exposure is shared (one manual value, read
back), so the CARD RATIO is meaningful as a scene-linear magnitude; the
comparison to a reference albedo band is INDICATIVE and confounded by
each surface's own illumination. Said here so no row can be read as a
measured albedo.

REFERENCE BANDS, and their source, stated BEFORE the numbers:
  Oke, *Boundary Layer Climates* (2nd ed.), standard surface-albedo
  tables -- fresh snow 0.80-0.95, old/melting snow 0.40-0.70, grass
  0.16-0.26, bare rock and soil 0.10-0.35. These are FIELD RADIOMETRY
  bands for real surfaces, used here as the target a scanned surface
  should land near. They are not a measurement of this world.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from exr_card import read_rgb  # noqa: E402
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402
from texel_budget import csf_threshold_michelson  # noqa: E402
from tiling_score import score  # noqa: E402
from verify_ground_station import project_terrain  # noqa: E402

MID = (50.0, 300.0)
MIN_CROP = 160
DOMINANT = 0.60
CARD_LINEAR = 0.180072          # measured on near_ground, same exposure
CARD_REFLECTANCE = 0.18

REFERENCE_BANDS = {
    "Snow": (0.40, 0.95, "old/melting 0.40-0.70, fresh 0.80-0.95"),
    "Rock": (0.10, 0.35, "bare rock and soil 0.10-0.35"),
    "Grass": (0.16, 0.26, "grass 0.16-0.26"),
}
BAND_SOURCE = ("Oke, Boundary Layer Climates (2nd ed.), standard "
               "surface-albedo tables -- FIELD RADIOMETRY for real "
               "surfaces, not a measurement of this world")


def largest_run(mask_1d, min_len):
    best, cur, start = (0, 0), 0, 0
    for i, ok in enumerate(mask_1d):
        if ok:
            if cur == 0:
                start = i
            cur += 1
            if cur > best[1] - best[0]:
                best = (start, i + 1)
        else:
            cur = 0
    return best if best[1] - best[0] >= min_len else None


def layer_crop(dom, layer_idx, band):  # noqa: C901
    """Largest row-run x column-run where this layer dominates the band."""
    m = band & (dom == layer_idx)
    rows = m.sum(axis=1) > (band.sum(axis=1) * DOMINANT).clip(1)
    rr = largest_run(rows, MIN_CROP)
    if rr is None:
        return None
    y0, y1 = rr
    # ⛔ THE DENOMINATOR IS THE BAND IN THAT COLUMN, NOT THE RUN HEIGHT.
    # Comparing against (y1-y0) demanded the layer fill 60% of the full
    # run, but the 50-300 m band is a horizontal STRIP -- most columns
    # carry band pixels over only part of the run. That mismatch returned
    # NO CROP for every layer while the ROW test was finding runs of 488
    # and 242. Same class as the earlier "no sky in the column" defect:
    # a fraction measured against the wrong population.
    colband = band[y0:y1].sum(axis=0)
    collyr = m[y0:y1].sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = np.where(colband > 0, collyr / np.maximum(colband, 1), 0.0)
    cols = frac >= DOMINANT
    cc = largest_run(cols, MIN_CROP)
    if cc is None:
        return None
    return (cc[0], y0, cc[1], y1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--station", default="ground")
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--stations-json", default=os.path.join(
        REPO, "_verify", "bench", "2026-09-11",
        "bench_stations_derived.json"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    rec = json.load(open(a.recipe, encoding="utf-8"))
    layers = rec["material"]["layers"]
    tile_m = float(layers[0]["tiling_m"])
    st = json.load(open(a.stations_json, encoding="utf-8"))
    cs = [float(v) for v in
          st["derived_stations"][a.station]["camera_string"].split(",")]
    cam = np.array(cs[:3]) / 100.0
    pitch, yaw = cs[3], cs[4]

    depth = decode_depth_m(os.path.join(
        a.frames, "%sFinalImageSceneDepth.png" % a.station))
    sky = depth > CEILING_M * 0.97
    rgb = read_rgb(os.path.join(a.frames, "%s.exr" % a.station))
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    H, W = depth.shape
    px_per_deg = W / 90.0

    # ⛔ THE LAYER MASK COMES FROM A RAYMARCH, NOT A FORWARD PROJECTION.
    # Forward-projecting the heightmap at stride 2 leaves the buffer
    # SPARSE at range: the first run of this table got 35,729 band pixels
    # where the depth pass says 30.4% of an 8.3 Mpx frame, and every
    # layer came back NO CROP. A march has one hit per ray and no holes.
    # Marched at 960x540 and upsampled x4 -- a full-res march is 8.3M
    # rays and minutes of wall clock for a mask whose features are far
    # larger than 4 px.
    from bench_station_derive import camera_basis, load_terrain, ray_grid, \
        raymarch
    Z, ox, oy, px_m = load_terrain(a.recipe)
    MW, MH = W // 4, H // 4
    F, Rv, Uv = camera_basis(pitch, yaw)
    dirs = ray_grid(F, Rv, Uv, 90.0, MW, MH)
    hit = raymarch(Z, ox, oy, px_m, cam, dirs, 1500.0,
                   math.radians(90.0) / MW).reshape(MH, MW)
    hit_ok = np.isfinite(hit)
    pos = cam[None, None, :] + dirs.reshape(MH, MW, 3) * hit[..., None]
    wa = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8a.png"))).astype(np.float32) / 255.0
    wb = np.asarray(Image.open(os.path.join(
        REPO, "textures", "alpine_8k_w8b.png"))).astype(np.float32) / 255.0
    # the live material carries THREE layers; the derivation's eight are
    # collapsed into them (scree folded into rock, forest_floor a tint)
    weights = {"Snow": wa[..., 0], "Rock": wa[..., 1] + wa[..., 2],
               "Grass": wb[..., 3]}
    names = list(weights)
    ny, nx = Z.shape
    dom_s = np.full((MH, MW), -1, dtype=np.int8)
    if hit_ok.any():
        cx = np.clip(((pos[..., 0][hit_ok] - ox) / px_m).astype(np.int64),
                     0, nx - 1)
        cy = np.clip(((pos[..., 1][hit_ok] - oy) / px_m).astype(np.int64),
                     0, ny - 1)
        stack = np.stack([weights[n][cy, cx] for n in names], axis=0)
        dom_s[hit_ok] = np.argmax(stack, axis=0).astype(np.int8)
    dom = np.repeat(np.repeat(dom_s, 4, axis=0), 4, axis=1)[:H, :W]
    valid = dom >= 0

    # THE BAND COMES FROM THE RENDER'S OWN DEPTH PASS, not the march --
    # binning distance is exactly what that pass is for (R-DEPTHBIN).
    band = (~sky) & (depth >= MID[0]) & (depth <= MID[1]) & valid
    out = {"_what": "Brief 3 Task 3 / ruling 4b -- tiling and albedo, "
                    "PLACEHOLDER layer set",
           "station": a.station, "camera_cm": cs[:3], "yaw": yaw,
           "tile_m": tile_m, "band_m": list(MID),
           "card": {"linear": CARD_LINEAR, "reflectance": CARD_REFLECTANCE,
                    "_where": "measured on near_ground at the same manual "
                              "exposure; there is no card at this station"},
           "albedo_band_source": BAND_SOURCE,
           "_placeholder_note": ("every row is a PLACEHOLDER surface; "
                                 "Ryan's six 4K scans are not yet bound"),
           "band_pixels": int(band.sum()), "rows": []}

    for i, n in enumerate(names):
        lyr = next((l for l in layers if l["name"] == n), {})
        surf = lyr.get("surface")
        sub = (lyr.get("sub_surface") or {}).get("surface")
        row = {"layer": n, "surface": surf, "sub_surface": sub,
               "status": "PLACEHOLDER",
               "pixels_in_band": int((band & (dom == i)).sum())}
        crop = layer_crop(dom, i, band)
        if crop is None:
            row["tiling"] = {"verdict": "NO CROP",
                             "why": "no %dx%d region where this layer "
                                    "dominates the 50-300 m band"
                                    % (MIN_CROP, MIN_CROP)}
        else:
            x0, y0, x1, y1 = crop
            sub_d = depth[y0:y1, x0:x1]
            d_rep = float(np.median(sub_d[np.isfinite(sub_d)]))
            period = px_per_deg * (180.0 / math.pi) * tile_m / d_rep
            cpd = d_rep / (tile_m * (180.0 / math.pi))
            thr = csf_threshold_michelson(cpd)
            s = score(lum[y0:y1, x0:x1], period)
            found = s["period_found_px"]
            w_lo, w_hi = period * 0.6, period * 1.4
            pinned = found is not None and (found <= w_lo * 1.02
                                            or found >= w_hi * 0.98)
            # ⛔ IS THERE A REPEAT AT ALL? michelson is
            # 2*std*sqrt(peak)/mean and a BUSY APERIODIC crop scores high
            # on contrast alone -- that is how this table first reported
            # Grass as a confident FAIL at peak 0.0511, when a radial
            # scan of the whole plausible range found no autocorrelation
            # maximum above 0.06 anywhere. So a verdict now requires a
            # PERIODOGRAM EXCESS, derived on known specimens:
            #     synthetic perfect tile   30.34
            #     real Rock @ 204 m         7.05
            #     aperiodic (noise, busy,
            #       weak-tile-in-noise)  1.44 - 2.38
            # The floor is 4.0, comfortably above everything aperiodic
            # and far below a true tile. k >= 4 is required too: at lower
            # wavenumbers the radial profile has too few samples for the
            # background to be estimable at all.
            exc = s.get("spectral_excess")
            k_t = s.get("spectral_k") or 0
            no_repeat = (exc is None or exc < 4.0 or k_t < 4)
            row["tiling"] = {
                "crop": [x0, y0, x1, y1], "distance_m": round(d_rep, 1),
                "tile_period_px": round(period, 1), "repeat_cpd": round(cpd, 3),
                "csf_threshold": round(thr, 4), "peak": s["peak"],
                "michelson": s["michelson"], "period_found_px": found,
                "spectral_excess": exc, "spectral_k": k_t,
                "search_window_px": [round(w_lo, 1), round(w_hi, 1)]}
            if no_repeat:
                row["tiling"]["verdict"] = "NO REPEAT"
                row["tiling"]["why"] = (
                    "spectral excess %s at k=%d -- below the 4.0 floor "
                    "derived from known specimens (perfect tile 30.34, "
                    "aperiodic 1.44-2.38)%s. There is no periodic "
                    "structure here to measure, so the michelson figure "
                    "beside it is the CROP'S OWN CONTRAST and is NOT a "
                    "repeat. Reporting it as a FAIL, as this table first "
                    "did, was an artefact."
                    % (exc, k_t,
                       "; and k<4 is too few spectral samples for the "
                       "background to be estimable" if k_t < 4 else ""))
            elif pinned:
                row["tiling"]["verdict"] = "NO VERDICT"
                row["tiling"]["why"] = (
                    "the autocorrelation peak sits at the search window's "
                    "edge, so it is the window's boundary and not the "
                    "tile's period -- no periodic structure at %.1f px to "
                    "measure (peak %.4f)" % (period, s["peak"]))
            else:
                row["tiling"]["verdict"] = ("PASS" if s["michelson"] < thr
                                            else "FAIL")

        m = band & (dom == i)
        if m.sum() < 500:
            row["albedo"] = {"verdict": "NO SAMPLE",
                             "pixels": int(m.sum())}
        else:
            mean_rgb = [float(rgb[..., c][m].mean()) for c in range(3)]
            ml = float(lum[m].mean())
            est = CARD_REFLECTANCE * ml / CARD_LINEAR
            lo, hi, desc = REFERENCE_BANDS.get(n, (0.0, 1.0, "unstated"))
            row["albedo"] = {
                "pixels": int(m.sum()),
                "mean_scene_linear_rgb": [round(v, 5) for v in mean_rgb],
                "mean_scene_linear_luma": round(ml, 5),
                "ratio_to_card": round(ml / CARD_LINEAR, 4),
                "implied_reflectance_if_lit_like_the_card": round(est, 4),
                "reference_band": [lo, hi], "reference_desc": desc,
                "verdict": "NO VERDICT",
                "_why_no_verdict": (
                    "⛔ A REFERENCE-ALBEDO COMPARISON IS NOT ADMISSIBLE "
                    "THROUGH 50-300 m OF AERIAL PERSPECTIVE. The measured "
                    "RGB ascends R<G<B on every layer, which is the "
                    "atmosphere's inscattering and not the surface: fog "
                    "density 0.00416/m puts transmittance near 0.5 at "
                    "150 m, so roughly half of what these pixels carry "
                    "was added by the air between. The card that defines "
                    "0.18 also sits at ANOTHER STATION, near_ground, and "
                    "these surfaces face their own way. The scene-linear "
                    "RGB and the card ratio are reported because they "
                    "were ruled; the band comparison is withheld because "
                    "it would be measuring the fog."),
                "_what_would_close_it": (
                    "a NEAR crop of each layer (under ~30 m, where "
                    "transmittance is >0.88) or an inscattering-corrected "
                    "read using fog_budget's model")}
        out["rows"].append(row)

    print("station %s  tile %.2f m  band %s  band pixels %d"
          % (a.station, tile_m, MID, out["band_pixels"]))
    print("\nTILING  (all surfaces are PLACEHOLDERS)")
    print("%-7s %-12s %8s %9s %9s %9s %10s %s"
          % ("layer", "surface", "dist m", "period", "found", "michelson",
             "csf thr", "verdict"))
    for r in out["rows"]:
        t = r["tiling"]
        if "crop" not in t:
            print("%-7s %-12s  %s" % (r["layer"], r["surface"], t["verdict"]))
            continue
        print("%-7s %-12s %8.1f %9.1f %9.1f %9.4f %10.4f %s"
              % (r["layer"], r["surface"], t["distance_m"],
                 t["tile_period_px"], t["period_found_px"], t["michelson"],
                 t["csf_threshold"], t["verdict"]))
    print("\nALBEDO  (scene-linear; card 0.18 -> %.6f linear)" % CARD_LINEAR)
    print("  reference bands: %s" % BAND_SOURCE)
    print("%-7s %-12s %9s %24s %9s %-12s %s"
          % ("layer", "surface", "px", "mean scene-linear RGB", "luma",
             "ref band", "verdict"))
    for r in out["rows"]:
        al = r["albedo"]
        if "mean_scene_linear_rgb" not in al:
            print("%-7s %-12s  %s" % (r["layer"], r["surface"], al["verdict"]))
            continue
        print("%-7s %-12s %9d %24s %9.5f %-12s %s"
              % (r["layer"], r["surface"], al["pixels"],
                 str([round(v, 4) for v in al["mean_scene_linear_rgb"]]),
                 al["mean_scene_linear_luma"],
                 "%.2f-%.2f" % tuple(al["reference_band"]), al["verdict"]))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
