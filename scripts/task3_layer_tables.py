"""task3_layer_tables.py — Task 3 verdicts PER LAYER, no first-tile fallback.

    python scripts/task3_layer_tables.py --selftest
    python scripts/task3_layer_tables.py --frames <dir> --station ground

⭐ WHY PER LAYER. `surface_report` derives ONE on-screen period for a
frame and takes it from the first layer's tile. That was tolerable while
every bound layer tiled at 5.03 m; it is wrong now that R-TILE gives each
layer its own tile (Rock 1.80, Scree 2.00, ForestFloor 2.14, Snow and
Grass 5.03-UNSTATED). A single period puts the autocorrelation search
window around the wrong scale, and the peak then pins at the window edge
and the report correctly refuses a verdict. Measured 2026-09-13: window
+/-40% of 58.0 px, the 1.8 m tile at 75.9 m, while a 5.03 m tile peaks at
162 px -- nowhere near it.

HOW A LAYER IS IDENTIFIED ON SCREEN. Depth gives distance along the
camera ray; the ray is built from the camera's OWN basis vectors, read
back from the actor (`_verify/bench/station_cameras.json`); world XY then
indexes the weightmap, and the layer is the argmax of the five weights
under the SAME five-layer contract the shader blends (four stored
channels plus the remainder), imported from the material builder rather
than restated.

⛔ THE DEPTH PASS IS 8-BIT LOG DEPTH, about 5.6% per LSB. It is used ONLY
as a distance -- to bin, and to place a world point along a known ray.
Nothing here reconstructs geometry from it.

ALBEDO VARIATION is std/mean of linear luma inside a layer's mask. The
band 0.10-0.20 is the brief's MEADOW band and is applied to MEADOW ONLY;
every other layer gets a NUMBER and no verdict, because a band borrowed
across denominators is how the shade band went wrong.

⛔ THIS IS AN UPPER BOUND, NOT ALBEDO. It is measured on a LIT pass, so
it carries shading. For the real thing use `task4_meadow_albedo.py`,
which measures on BaseColor where lighting was never applied
(R-MEADOWALBEDO): Grass reads 0.4447 here and 0.2278 there.

⭐⭐ THE INSTRUMENT THE REPEAT VERDICT IS DEFINED ON, AND IT IS THE ONLY
ONE IT IS VALID ON.

    REPEAT VERDICTS ARE PLAYER-INSTRUMENT ONLY:
        Bench_ground, FinalImage, display-referred (tone curve ON),
        temporal_sample_count 8, TSR resolved, render warm-up 40.

A verdict from any other configuration is not a verdict. This is not a
style rule -- it is the measured difference between the two instruments
at 30-100 m, same station, same code state, temporal samples the only
variable:

    layer   temporal 1 (TRUTH)        temporal 8 (PLAYER)
    Rock    0.10143  87 px  FAIL      0.00000  NO PEAK
    Scree   0.09040  85 px  FAIL      0.00000  NO PEAK
    Grass   0.10925 199 px  FAIL      0.03969 195 px  PASS (thr 0.05338)

The temporal-1 figures are REAL and are recorded as the TRUTH-INSTRUMENT
result -- "aliasing at temporal 1, NOT PLAYER-VISIBLE". They measure
sub-pixel detail aliasing against the sampling grid (REGISTER B3.17),
which is a true property of the frame and is exactly what temporal
supersampling exists to resolve. Judging a player-facing visibility
threshold on a single-sample frame asks whether a repeat would be
visible in an image no player is ever shown.

⛔ SO DO NOT RE-DERIVE A VERDICT FROM A DEPTH CAPTURE. MRQ forces
temporal samples to 1 whenever a depth pass is present, so every capture
carrying its own depth is a TRUTH capture. The player instrument borrows
depth from one (`--depth-from`); depth is deterministic here.

⛔ THE HISTORY, kept because each item was a real defect:

  1. THE NULL WAS A ZERO. `tile_peak` returned exactly 0.00000 when the
     window held no strict local maximum, so "no repeat" and "a repeat
     just under the bar" were the same number -- and it proved BISTABLE
     at the edge: Rock read 0.10142 / 0.10125 / 0.00000 / 0.00000 across
     four builds of a material that never touched it. FIXED: the largest
     residual is always reported, with `tile_peak_is_local_max` saying
     which kind of peak it is, and value / threshold / verdict are three
     separate columns.
  2. CAPTURES WERE COMPARED ACROSS CONFIGURATIONS. Within one held
     configuration the spread is 0.2-0.5%; the tone curve alone moves
     the number ~1.4x. A verdict without its configuration is not a
     measurement, and this tool now REFUSES a tone-curve-disabled
     capture (see `analyse`).
  3. ⛔ THE PEAK'S SOURCE IS NOT KNOWN. Rock 87 px, Scree 85 px and
     Grass 199 px at 30-100 m. Stochastic tiling on Scree -- which
     randomises the texture's UV offset per cell -- did NOT move its
     peak at any swept value, so the structure is not the scan
     repeating; and Scree's peak sits at 1.20x its predicted tile
     period, not 1.0x. Until the source is named, a "texture-tile"
     verdict at this bin would be a label on the wrong mechanism.
     REGISTER B3.17.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402
from make_landscape_material import mask_plan  # noqa: E402
import exr_card  # noqa: E402

RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
CAMS = os.path.join(REPO, "_verify", "bench", "station_cameras.json")
BINS = [(30.0, 100.0), (100.0, 300.0)]
MEADOW_LAYER = "Grass"
ALBEDO_BAND = (0.10, 0.20)
LUMA = (0.2126, 0.7152, 0.0722)
MIN_PX = 20000          # below this a layer's mask is not a measurement


def csf_threshold(cpd):
    """Michelson contrast a repeat must stay under to be invisible."""
    if cpd <= 0:
        return 1.0
    return float(np.clip(1.0 / (75.0 * cpd * math.exp(-0.2 * cpd)), 1e-4, 1.0))


def world_xy(depth_m, cam, res):
    """(X, Y) in cm for every pixel, from depth along the camera ray."""
    h, w = depth_m.shape
    fwd = np.array(cam["forward"], dtype=np.float64)
    rgt = np.array(cam["right"], dtype=np.float64)
    up = np.array(cam["up"], dtype=np.float64)
    hfov = math.radians(float(cam.get("fov_deg") or 90.0))
    tan_h = math.tan(hfov * 0.5)
    tan_v = tan_h * (h / float(w))
    xs = (np.arange(w) + 0.5) / w * 2.0 - 1.0          # -1..1 left..right
    ys = 1.0 - (np.arange(h) + 0.5) / h * 2.0          # +1..-1 top..bottom
    X, Y = np.meshgrid(xs, ys)
    dx = fwd[0] + X * tan_h * rgt[0] + Y * tan_v * up[0]
    dy = fwd[1] + X * tan_h * rgt[1] + Y * tan_v * up[1]
    dz = fwd[2] + X * tan_h * rgt[2] + Y * tan_v * up[2]
    n = np.sqrt(dx * dx + dy * dy + dz * dz)
    d_cm = depth_m * 100.0
    return (cam["loc_cm"][0] + dx / n * d_cm,
            cam["loc_cm"][1] + dy / n * d_cm)


def layer_index_map(wx, wy, rec):
    """Dominant layer index per pixel, under the five-layer contract."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    wm = (np.asarray(Image.open(os.path.join(
        REPO, rec["material"]["weightmap"])).convert("RGBA"))
        .astype(np.float32) / 255.0)
    n = wm.shape[0]
    ls = rec["landscape"]
    ox, oy = float(ls["location_cm"][0]), float(ls["location_cm"][1])
    s = float(ls["scale_xy_cm"])
    gx = np.clip(np.round((wx - ox) / s).astype(np.int32), 0, n - 1)
    gy = np.clip(np.round((wy - oy) / s).astype(np.int32), 0, n - 1)
    names = [layer["name"] for layer in rec["material"]["layers"]]
    direct, has_rem = mask_plan(len(names))
    w = wm[gy, gx, :]                                   # (H, W, 4)
    stack = [w[..., i] for i in range(direct)]
    if has_rem:
        stack.append(np.clip(1.0 - w.sum(axis=2), 0.0, 1.0))
    return np.argmax(np.stack(stack, axis=-1), axis=-1), names


def masked_box_blur(gray, mask, r):
    """Low-pass of `gray` over `mask` only: box(L*m) / box(m).

    The same normalisation idea as the autocorrelation below, for the
    same reason: a plain blur across an irregular mask drags non-layer
    pixels into the estimate and the detrend then removes the wrong
    thing.
    """
    m = mask.astype(np.float64)
    g = np.where(mask, gray, 0.0).astype(np.float64)

    def box(a):
        k = 2 * r + 1
        c = np.cumsum(np.pad(a, ((r, r), (0, 0)), mode="edge"), axis=0)
        a2 = (c[k - 1:] - np.vstack([np.zeros((1, a.shape[1])), c[:-k]]))
        c = np.cumsum(np.pad(a2, ((0, 0), (r, r)), mode="edge"), axis=1)
        return (c[:, k - 1:]
                - np.hstack([np.zeros((a2.shape[0], 1)), c[:, :-k]]))

    num, den = box(g), box(m)
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0)


def masked_autocorr(gray, mask):
    """Mask-NORMALISED horizontal autocorrelation, lag 0..W-1.

    ⛔ WHY NOT A BOUNDING-BOX CROP WITH THE HOLES FILLED. A layer's mask
    is an irregular region. Cropping to its bounding box and filling the
    non-layer pixels with a mean injects the MASK's own structure into
    the signal, and the autocorrelation then finds the shape of the
    region rather than the repeat of the texture -- an instrument that
    manufactures the thing it is looking for.

    The standard fix, and the one used here:

        AC(k) = SUM m(x)m(x+k) g(x)g(x+k)  /  SUM m(x)m(x+k)

    so every lag is normalised by how much VALID overlap it actually had.
    Computed by FFT on (g*m) and on (m) separately.
    """
    m = mask.astype(np.float64)
    g = np.where(mask, gray, 0.0).astype(np.float64)
    tot = m.sum()
    if tot < 1.0:
        return None
    mean = g.sum() / tot
    g = np.where(mask, g - mean, 0.0)
    if g[mask].std() < 1e-9:
        return None
    w = gray.shape[1]
    nfft = 1 << int(np.ceil(np.log2(2 * w)))
    F = np.fft.rfft(g, n=nfft, axis=1)
    M = np.fft.rfft(m, n=nfft, axis=1)
    num = np.fft.irfft(F * np.conj(F), n=nfft, axis=1)[:, :w].sum(axis=0)
    den = np.fft.irfft(M * np.conj(M), n=nfft, axis=1)[:, :w].sum(axis=0)
    ok = den > (den[0] * 0.02)      # lags with too little overlap are noise
    ac = np.full(w, np.nan)
    ac[ok] = num[ok] / den[ok]
    if not np.isfinite(ac[0]) or ac[0] == 0:
        return None
    return ac / ac[0]


def tile_peak(ac, period_px):
    """The TEXTURE-TILE component alone: a local peak's PROMINENCE.

    ⭐ SPLIT (a), ruled 2026-09-13d. Inside the +/-40% window the
    autocorrelation of this world DECAYS MONOTONICALLY -- the sub-tile
    structure the weightmap carries dominates every lag. Taking the
    window MAX therefore reports the window's lower edge and calls it a
    tile, which is how every layer read FAIL against a threshold meant
    for a repeat.

    This masks that: a straight line is fitted ACROSS the window and
    subtracted, so the monotone component (the 1 m structure and the
    pixel-scale decay it sits on) goes with it, and what remains is
    whatever BUMPS above the trend. A tile repeat is a bump. A
    featureless decay has none.

    ⛔ IT NO LONGER RETURNS 0.00000 FOR "NO LOCAL MAXIMUM". That null was
    a defect, ruled out 2026-09-13: a metric whose null output is exactly
    zero cannot distinguish "there is no repeat here" from "there is a
    repeat just under the bar", and it turned out to be BISTABLE at the
    edge -- Rock read 0.10142 / 0.10125 / 0.00000 / 0.00000 across four
    builds of a material that never touched it. Reporting zero made a
    near-miss look like a clean pass.

    So the largest residual in the window is ALWAYS returned, with a flag
    saying whether it is a strict local maximum. The VERDICT is the
    caller's, from the Michelson against the threshold, and it is a
    separate column from the value.

    Returns (peak, lag, is_local_max), or (None, None, None) when the
    window is too narrow to be a search at all -- which is a refusal,
    not a zero.
    """
    lo = max(2, int(period_px * 0.6))
    hi = min(len(ac) - 2, int(period_px * 1.4))
    if hi - lo < 4:
        return None, None, None
    seg = ac[lo:hi + 1]
    if not np.all(np.isfinite(seg)):
        seg = np.nan_to_num(seg, nan=float(np.nanmean(seg)))
    x = np.arange(seg.size, dtype=np.float64)
    A = np.vstack([x, np.ones_like(x)]).T
    coef, _r, _rank, _sv = np.linalg.lstsq(A, seg, rcond=None)
    resid = seg - (coef[0] * x + coef[1])
    # The strongest STRICT local maximum, if the window holds one.
    best, best_k = None, None
    for i in range(1, seg.size - 1):
        if resid[i] > resid[i - 1] and resid[i] >= resid[i + 1]:
            if best is None or resid[i] > best:
                best, best_k = float(resid[i]), lo + i
    if best is not None:
        return best, best_k, True
    # No local maximum: report the largest residual anyway, so the number
    # is a measurement of how close this got rather than a zero.
    j = int(np.argmax(resid))
    return float(resid[j]), lo + j, False


def autocorr_peak(gray, period_px, mask=None, detrend=True):
    """(peak, period found, global peak, global period) around period_px.

    ⭐ DETREND FIRST, as the desk's `tiling_score` does. Without it the
    autocorrelation is dominated by the smooth lighting gradient and
    peaks at the shortest lag with a correlation near 1, so EVERY layer
    reads as "no tile repeat found" for the wrong reason — measured
    2026-09-13, global peak at 2 px with 0.77-0.98 on all five layers.
    The high-pass is a box blur at the period's own scale, so it removes
    what is SLOWER than the repeat being looked for and keeps the repeat.
    """
    if mask is None:
        mask = np.ones(gray.shape, dtype=bool)
    hi_std = None
    if detrend:
        r = max(4, int(round(period_px)))
        gray = np.where(mask, gray - masked_box_blur(gray, mask, r), 0.0)
        hi_std = float(gray[mask].std()) if mask.any() else None
    ac = masked_autocorr(gray, mask)
    if ac is None:
        return None, None, None, None, hi_std, None, None, None
    lo = max(2, int(period_px * 0.6))
    hi = min(len(ac) - 1, int(period_px * 1.4))
    if hi <= lo:
        return None, None, None, None, hi_std, None, None, None
    win = ac[lo:hi + 1]
    if not np.any(np.isfinite(win)):
        return None, None, None, None, hi_std, None, None, None
    k = int(np.nanargmax(win)) + lo
    # The GLOBAL peak over all usable lags, reported so a NO VERDICT says
    # WHERE the frame's real periodicity is rather than only that it is
    # not at the tile.
    tail = ac[2:]
    gk = int(np.nanargmax(tail)) + 2 if np.any(np.isfinite(tail)) else None
    prom, prom_k, prom_is_max = tile_peak(ac, period_px)
    return (float(ac[k]), k,
            (float(ac[gk]) if gk is not None else None), gk, hi_std,
            prom, prom_k, prom_is_max)


def _capture_camera(frames, station):
    """The camera a capture was rendered from, per its sidecar, or None.

    Returns None when the sidecar cannot be read -- "I could not look" is
    not "they match" (NN6), so the caller treats None as unknown rather
    than as agreement.
    """
    d = os.path.dirname(os.path.abspath(frames))
    base = os.path.basename(os.path.abspath(frames))
    p = os.path.join(d, "bench_run_%s.json" % base)
    if not os.path.exists(p):
        return None
    try:
        sc = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    for job in (sc.get("jobs") or []):
        loc = job.get("camera_location_cm") or job.get("camera_loc_cm")
        if loc:
            return [round(float(v), 3) for v in loc]
    return None


def render_settings(frames):
    """Temporal samples and AA method AS THE RENDER REPORTED THEM.

    The ruling asks for both to be read BACK from the render, not from
    the command line: `--temporal-samples 8` records what was asked, and
    MRQ silently forces 1 whenever a depth pass is present. A capture
    that quietly fell back to 1 while the report says 8 is exactly the
    silent-wrong class this bench exists to catch.
    """
    d = os.path.dirname(os.path.abspath(frames))
    base = os.path.basename(os.path.abspath(frames))
    p = os.path.join(d, "bench_run_%s.json" % base)
    out = {"sidecar": os.path.basename(p)}
    if not os.path.exists(p):
        out["_error"] = "no sidecar beside %s" % base
        return out
    sc = json.load(open(p, encoding="utf-8"))
    out["temporal_samples_requested"] = sc.get("temporal_samples_requested")
    # The READ-BACKS live per job, not at the top level: the request is
    # `temporal_samples_requested`, and what MRQ actually holds is
    # `jobs[N].temporal_sample_count_readback`. Reporting the request as
    # if it were the read-back is exactly what rule 12 forbids, and MRQ
    # silently forces 1 when a depth pass is present, so the two really
    # do diverge.
    for job in (sc.get("jobs") or []):
        for k in ("temporal_sample_count_readback",
                  "spatial_sample_count_readback",
                  "render_warm_up_count_readback",
                  "render_warm_up_frames_readback",
                  "engine_warm_up_count_readback"):
            if k in job:
                out[k] = job[k]
        break
    if (out.get("temporal_sample_count_readback") is not None
            and out.get("temporal_samples_requested") is not None
            and out["temporal_sample_count_readback"]
            != out["temporal_samples_requested"]):
        out["_temporal_mismatch"] = (
            "MRQ held %s temporal samples against a request of %s -- it "
            "forces 1 whenever a depth pass is present."
            % (out["temporal_sample_count_readback"],
               out["temporal_samples_requested"]))
    cvars_req = {}
    for job in (sc.get("jobs") or []):
        cvars_req = job.get("cvars_requested") or {}
        break
    out["anti_aliasing"] = {
        "r.AntiAliasingMethod_overridden_by_this_capture":
            "r.AntiAliasingMethod" in cvars_req,
        "_means": ("when false, the capture did NOT set the AA method and "
                   "the editor's own value applied. That value is read "
                   "separately (r.AntiAliasingMethod = 4 = TSR on this "
                   "project, enumerated 2026-09-13); it is not in this "
                   "sidecar because the capture never touched it."),
        "sg.AntiAliasingQuality_applied":
            (sc.get("cvars_applied_readback") or {}).get(
                "sg.AntiAliasingQuality"),
    }
    cv = sc.get("cvars_applied_readback") or {}
    for k in ("r.AntiAliasingMethod", "r.TemporalAA.Quality",
              "r.ScreenPercentage"):
        if k in cv:
            out[k] = cv[k]
    out["engine_cvars_before_render"] = {
        k: v for k, v in (sc.get("engine_cvars_before_render") or {}).items()
        if "AntiAlias" in k or "Temporal" in k or "ScreenPercentage" in k}
    return out


def tone_curve_state(frames):
    """(disabled, sidecar_path) for the capture `frames` came from.

    The sidecar lives beside the frame directory as
    bench_run_<profile>_<tag>.json for frames .../<profile>_<tag>.
    Returns (None, path_or_None) when it cannot be read -- "I could not
    look" is not "it was on" (NN6).
    """
    d = os.path.dirname(os.path.abspath(frames))
    base = os.path.basename(os.path.abspath(frames))
    p = os.path.join(d, "bench_run_%s.json" % base)
    if not os.path.exists(p):
        return None, None
    try:
        sc = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None, p
    lr = sc.get("linear_readback")
    if not lr:
        return False, p
    vals = [bool(v.get("disable_tone_curve_readback"))
            for v in lr.values() if isinstance(v, dict)]
    return (bool(vals and all(vals)), p)


def analyse(frames, station, recipe_path=RECIPE, channel=None,
            allow_linear=False, cams_path=None, depth_from=None,
            prefer_png=False):
    # ⭐ WHY A CAPTURE MAY BORROW ANOTHER'S DEPTH PASS. MRQ forces
    # temporal_samples to 1 whenever a depth pass is requested -- depth
    # cannot be multisampled and still line up with the beauty. So the
    # PLAYER instrument (temporal 8, TSR resolved) and a depth pass are
    # mutually exclusive in one render.
    #
    # They do not have to be in one render. The depth pass is a function
    # of GEOMETRY and CAMERA, and both are deterministic here: measured
    # 2026-09-13, depth differs on 0.0000% of pixels across four captures
    # of this station, and the per-layer pixel counts are identical TO
    # THE PIXEL. So a temporal-1 capture's depth is the correct depth for
    # a temporal-8 beauty from the same camera.
    #
    # ⛔ THE PRECONDITION IS THE CAMERA, NOT THE TAG. Borrowing depth
    # from a capture taken at a DIFFERENT camera would mis-assign every
    # layer mask, so the two sidecars' stations are compared and a
    # mismatch refuses.
    # ⛔ THE CSF THRESHOLD IS PERCEPTUAL, SO IT BELONGS ON THE LOOK
    # INSTRUMENT. `csf_threshold` returns the Michelson contrast at which
    # a repeat becomes VISIBLE to a viewer, and a viewer sees the
    # display-referred frame. Measuring it on a scene-linear capture
    # (bDisableToneCurve) compares a perceptual bound against values in
    # the wrong space.
    #
    # This is not hypothetical. Measured 2026-09-13 across FOUR captures
    # of this same station, Scree at 30-100 m:
    #
    #     tone curve ON   (task3d)              0.02678
    #     tone curve OFF  (t3f / t3v / t4base)  0.06203 0.06122 0.06448
    #
    # A FACTOR OF 2.3 in a number that is compared against a perceptual
    # threshold, and the peak sits at the same 85 px lag in all four --
    # so the STRUCTURE is identical and only its measured contrast moves.
    # Reporting a linear figure against the CSF bound is a units error,
    # so the tool refuses rather than leaving it to whoever reads the
    # table.
    #
    # ⛔ AND THIS GUARD DOES NOT EXPLAIN THE GRASS INSTABILITY. It was
    # first written claiming it did, citing Grass 30-100 flipping
    # 0.00000 -> 0.08023. That was WRONG and the data refuted it within
    # the hour: t3f and t4base have IDENTICAL settings (temporal 1, tone
    # curve off, warm-up 40) and give 0.00000 PASS and 0.08023 FAIL.
    # See the Grass note in the module docstring.
    if not allow_linear:
        disabled, sidecar = tone_curve_state(frames)
        if disabled:
            raise SystemExit(
                "REFUSE: %s was captured with the tone curve DISABLED "
                "(linear_readback in %s). The CSF threshold this tool "
                "compares against is a PERCEPTUAL contrast bound and "
                "belongs on the display-referred frame. Re-capture "
                "without --linear, or pass --allow-linear if you are "
                "deliberately measuring structure rather than "
                "visibility -- in which case do NOT compare the verdict "
                "against a tone-curve-on table."
                % (frames, os.path.basename(sidecar or "?")))
    rec = json.load(open(recipe_path, encoding="utf-8"))
    cams = json.load(open(cams_path or CAMS, encoding="utf-8"))["cameras"]
    if station not in cams:
        raise SystemExit("no camera for station %r in %s" % (station, CAMS))
    cam = cams[station]

    exr = os.path.join(frames, "%s.exr" % station)
    dep = None
    for cand in ("%sFinalImageSceneDepth.png" % station,
                 "%s_SceneDepth.png" % station):
        p = os.path.join(frames, cand)
        if os.path.exists(p):
            dep = p
            break
    borrowed = None
    if dep is None and depth_from:
        for cand in ("%sFinalImageSceneDepth.png" % station,
                     "%s_SceneDepth.png" % station):
            p = os.path.join(depth_from, cand)
            if os.path.exists(p):
                dep = p
                borrowed = depth_from
                break
        if dep is None:
            raise SystemExit("no SceneDepth png in --depth-from %s"
                             % depth_from)
        # THE CAMERA MUST MATCH, and the sidecars are the witness.
        a_cam = _capture_camera(frames, station)
        b_cam = _capture_camera(depth_from, station)
        if a_cam is not None and b_cam is not None and a_cam != b_cam:
            raise SystemExit(
                "REFUSE: %s was rendered from %r and the borrowed depth "
                "from %r. A depth pass from a different camera mis-places "
                "every pixel and mis-assigns every layer mask."
                % (os.path.basename(frames), a_cam, b_cam))
    # ⭐ THE BEAUTY MAY BE A PNG, AND FOR THE PLAYER INSTRUMENT IT SHOULD
    # BE. MRQ writes an EXR only when a render has MORE THAN ONE PASS, so
    # a plain temporal-8 capture (no depth, no probe pass) emits
    # `ground.png` alone. That is not a shortfall: the PNG is the
    # display-referred image a player actually sees, which is exactly the
    # domain the CSF threshold is defined in.
    #
    # ⛔ BUT IT IS A DIFFERENT INSTRUMENT FROM THE EXR and the two must
    # not be mixed in one table. `beauty_source` is reported so a
    # comparison across capture kinds is visible rather than silent.
    # sRGB is decoded to linear before luma, because the statistic is
    # about light and not about the encode.
    beauty_png = None
    if prefer_png or not os.path.exists(exr):
        for cand in ("%sFinalImage.png" % station, "%s.png" % station):
            p = os.path.join(frames, cand)
            if os.path.exists(p):
                beauty_png = p
                break
    if beauty_png is None and not os.path.exists(exr):
        raise SystemExit("no %s and no beauty PNG in %s" % (exr, frames))
    if dep is None:
        raise SystemExit("need a SceneDepth png in %s (or --depth-from)"
                         % frames)

    if beauty_png is not None:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        srgb = (np.asarray(Image.open(beauty_png).convert("RGB"))
                .astype(np.float64) / 255.0)
        rgb = np.where(srgb <= 0.04045, srgb / 12.92,
                       ((srgb + 0.055) / 1.055) ** 2.4)
        beauty_source = os.path.basename(beauty_png) + " (sRGB -> linear)"
    else:
        rgb = exr_card.read_rgb(exr, channel)
        beauty_source = os.path.basename(exr) + (
            ":%s" % channel if channel else ":RGBA")
    depth = decode_depth_m(dep)
    if rgb.shape[:2] != depth.shape:
        # ⛔ A SCREEN-PERCENTAGE CAPTURE WRITES THE DEPTH PASS AT THE
        # RENDER RESOLUTION AND THE BEAUTY AT THE OUTPUT RESOLUTION.
        # Measured at r.ScreenPercentage 50: beauty 3840x2160, depth
        # 1920x1080. That is not a fault -- it is what the pass is -- but
        # the two must be brought to one grid before any per-pixel work.
        #
        # NEAREST NEIGHBOUR, never interpolation: the depth pass is an
        # 8-bit LOG code and the mean of two codes is not the code of the
        # mean distance. Only an INTEGER ratio is accepted; anything else
        # refuses, because a fractional resample would shift the layer
        # masks against the beauty by a sub-pixel amount nobody declared.
        bh, bw = rgb.shape[:2]
        dh, dw = depth.shape
        if bh % dh or bw % dw or (bh // dh) != (bw // dw):
            raise SystemExit(
                "beauty %s and depth %s differ by a non-integer ratio; "
                "refusing to resample" % (rgb.shape[:2], depth.shape))
        f = bh // dh
        depth = np.repeat(np.repeat(depth, f, axis=0), f, axis=1)
        out_depth_note = (
            "the depth pass was written at %dx%d (render resolution) "
            "against a %dx%d beauty and was NEAREST-upsampled by %dx. "
            "Every period below is therefore in OUTPUT pixels."
            % (dw, dh, bw, bh, f))
    else:
        out_depth_note = None
    h, w = depth.shape
    sky = depth > CEILING_M * 0.97
    px_per_deg = w / float(cam.get("fov_deg") or 90.0)

    wx, wy = world_xy(depth, cam, (w, h))
    lay, names = layer_index_map(wx, wy, rec)
    tiles = {layer["name"]: layer.get("tiling_m")
             for layer in rec["material"]["layers"]}
    unstated = {layer["name"]: ("_tile_size_UNSTATED" in layer)
                for layer in rec["material"]["layers"]}

    gray = (rgb[..., 0] * LUMA[0] + rgb[..., 1] * LUMA[1]
            + rgb[..., 2] * LUMA[2])

    out = {"station": station, "frames": frames,
           "channel": channel or "RGBA (FinalImage)",
           "sky_fraction": round(float(sky.mean()), 4),
           "px_per_deg": round(px_per_deg, 3),
           "depth_resample": out_depth_note,
           "beauty_source": beauty_source,
           "depth_borrowed_from": (os.path.basename(borrowed)
                                   if borrowed else None),
           "render_settings_readback": render_settings(frames),
           "bins": [], "albedo": []}

    for lo, hi in BINS:
        inbin = (~sky) & (depth >= lo) & (depth <= hi)
        row = {"bin_m": [lo, hi], "pixels": int(inbin.sum()), "layers": []}
        for li, nm in enumerate(names):
            m = inbin & (lay == li)
            npx = int(m.sum())
            ent = {"layer": nm, "pixels": npx, "tile_m": tiles[nm],
                   "tile_unstated": bool(unstated[nm])}
            if npx < MIN_PX or tiles[nm] is None:
                ent["verdict"] = "NO VERDICT"
                ent["why"] = ("only %d px of this layer in the bin; below "
                              "the %d-px floor a crop is not a measurement"
                              % (npx, MIN_PX))
                row["layers"].append(ent)
                continue
            dist = float(np.median(depth[m]))
            period = px_per_deg * (180.0 / math.pi) * tiles[nm] / dist
            cpd = 1.0 / (period / px_per_deg) if period > 0 else 0.0
            thr = csf_threshold(cpd)
            ys_, xs_ = np.where(m)
            y0, y1 = ys_.min(), ys_.max() + 1
            x0, x1 = xs_.min(), xs_.max() + 1
            (peak, found, gpeak, gfound, hi_std, prom, prom_k,
             prom_is_max) = autocorr_peak(
                gray[y0:y1, x0:x1], period, m[y0:y1, x0:x1])
            ent.update({"mean_distance_m": round(dist, 1),
                        "period_px": round(period, 1),
                        "cycles_per_deg": round(cpd, 4),
                        "threshold_michelson": round(thr, 4)})
            if peak is None:
                ent["verdict"] = "NO VERDICT"
                ent["why"] = "no usable autocorrelation window"
            else:
                lo_w, hi_w = period * 0.6, period * 1.4
                pinned = found <= lo_w * 1.02 or found >= hi_w * 0.98
                # MICHELSON, the desk's formula: the repeating component's
                # contrast relative to the crop's own mean luminance.
                # `peak` is a normalised autocorrelation and the threshold
                # is a Michelson contrast -- comparing them directly was a
                # UNITS ERROR, so the conversion is explicit.
                mean_l = float(gray[y0:y1, x0:x1][m[y0:y1, x0:x1]].mean())
                mich = (2.0 * (hi_std or 0.0) * math.sqrt(max(peak, 0.0))
                        / max(mean_l, 1e-6))
                ent.update({"autocorr_peak": round(peak, 4),
                            "michelson": round(mich, 5),
                            "period_found_px": found,
                            "search_window_px": [round(lo_w, 1),
                                                 round(hi_w, 1)],
                            "global_autocorr_peak": (round(gpeak, 4)
                                                     if gpeak else None),
                            "global_period_px": gfound,
                            "detrended_std": round(hi_std, 6)
                            if hi_std else None,
                            "crop_mean_luma": round(mean_l, 6)})
                # A peak pinned at the window edge is no longer a refusal
                # by itself: after detrending, the autocorrelation no
                # longer decays monotonically, so the window max is a real
                # local peak. It is reported, and the VERDICT is the
                # michelson against the CSF threshold.
                ent["pinned_at_window_edge"] = bool(pinned)
                # ---- SPLIT (b): the sub-tile / grid component ----------
                # The window MAX, which in this world is the monotone
                # decay the weightmap carries. Recorded as its own number
                # with NO tile verdict attached to it.
                ent["grid_michelson"] = round(mich, 5)
                # ---- SPLIT (a): the TEXTURE-TILE repeat ---------------
                # The local peak's PROMINENCE above the window's trend,
                # converted the same way. No local peak at all means no
                # tile repeat to see, which is a PASS.
                if prom is None:
                    ent["tile_verdict"] = "NO VERDICT"
                    ent["why"] = ("the +/-40% window is narrower than 5 "
                                  "lags, which is not a search")
                else:
                    tmich = (2.0 * (hi_std or 0.0) * math.sqrt(max(prom, 0.0))
                             / max(mean_l, 1e-6))
                    # ⭐ VALUE, THRESHOLD AND VERDICT ARE THREE COLUMNS.
                    # `tile_michelson` is ALWAYS a real measurement now --
                    # never 0.00000 standing in for "no local maximum" --
                    # and `tile_peak_is_local_max` says which kind of peak
                    # produced it. The verdict is computed from the value
                    # against the threshold and from nothing else, so a
                    # sub-threshold peak reads as a NUMBER under a bar
                    # rather than as an absence.
                    lo_w2, hi_w2 = max(2, int(period * 0.6)), int(period * 1.4)
                    at_edge = bool(prom_k is not None
                                   and (prom_k <= lo_w2 + 1
                                        or prom_k >= hi_w2 - 1))
                    ent["tile_prominence"] = round(prom, 6)
                    ent["tile_period_px"] = prom_k
                    ent["tile_michelson"] = round(tmich, 5)
                    ent["tile_threshold"] = round(thr, 5)
                    ent["tile_margin"] = round(tmich - thr, 5)
                    ent["tile_ratio_to_threshold"] = (round(tmich / thr, 3)
                                                      if thr > 0 else None)
                    ent["tile_peak_is_local_max"] = bool(prom_is_max)
                    ent["tile_peak_at_window_edge"] = at_edge
                    ent["tile_window_px"] = [lo_w2, hi_w2]
                    # ⭐ THE VERDICT IS ITS OWN COLUMN AND IT IS NOT A
                    # NUMBER. Three outcomes, and only one of them is a
                    # comparison against the threshold:
                    #
                    #   NO PEAK  the largest residual is at or below the
                    #            window trend (prominence <= 0), so there
                    #            is nothing standing above it to see. The
                    #            prominence -- which is NEGATIVE here --
                    #            is the number that says how far below.
                    #   NO PEAK (window edge)
                    #            no strict local maximum, so the reported
                    #            lag pins at the window bound. That is a
                    #            property of the SEARCH, and this project
                    #            has published a window bound as a world
                    #            period once already. It must not produce
                    #            a FAIL.
                    #   PASS / FAIL
                    #            a real local maximum, judged on its
                    #            Michelson against the CSF threshold.
                    if prom <= 0.0:
                        ent["tile_verdict"] = "NO PEAK"
                        ent["why"] = (
                            "the largest residual in the window is %+.6f, "
                            "at or BELOW the window trend -- nothing stands "
                            "above it. Reported as a signed number rather "
                            "than as a Michelson of 0.00000." % prom)
                    elif not prom_is_max or at_edge:
                        ent["tile_verdict"] = "NO PEAK (window edge)"
                        ent["why"] = (
                            "no strict local maximum in the window, so the "
                            "reported lag %s pins at the window bound %r. "
                            "That is a property of the SEARCH, not of the "
                            "world; the Michelson %.5f is a noise-floor "
                            "reading and is NOT judged against the "
                            "threshold." % (prom_k, [lo_w2, hi_w2], tmich))
                    else:
                        ent["tile_verdict"] = ("PASS" if tmich <= thr
                                               else "FAIL")
                ent["verdict"] = ent["tile_verdict"]
            row["layers"].append(ent)
        out["bins"].append(row)

    # ---- albedo variation, per layer, near ground ----------------------
    near = (~sky) & (depth >= 3.0) & (depth <= 60.0)
    for li, nm in enumerate(names):
        m = near & (lay == li)
        npx = int(m.sum())
        ent = {"layer": nm, "pixels": npx}
        if npx < MIN_PX:
            ent["verdict"] = "NO VERDICT"
            ent["why"] = "only %d px" % npx
        else:
            v = gray[m]
            mean = float(v.mean())
            ent["std_over_mean"] = round(float(v.std() / mean), 4) \
                if mean > 1e-6 else None
            if nm == MEADOW_LAYER:
                ent["band"] = list(ALBEDO_BAND)
                ent["verdict"] = ("PASS" if ALBEDO_BAND[0]
                                  <= ent["std_over_mean"] <= ALBEDO_BAND[1]
                                  else "FAIL")
            else:
                ent["verdict"] = "NO VERDICT"
                ent["why"] = ("the 0.10-0.20 band is the brief's MEADOW "
                              "band; this layer has no band of its own")
        out["albedo"].append(ent)
    return out


def _selftest_tile_peak():
    """tile_peak must never answer 'no repeat' with a bare zero."""
    fails = []
    x = np.arange(400, dtype=np.float64)
    # 1. A REAL LOCAL MAXIMUM is found, flagged as one, at the right lag.
    ac = np.exp(-x / 300.0) + 0.05 * np.cos(2 * np.pi * x / 70.0)
    p, k, is_max = tile_peak(ac, 70.0)
    if not is_max:
        fails.append("a cosine bump at lag 70 was not read as a local max")
    if k is None or abs(k - 70) > 4:
        fails.append("cosine bump found at lag %r, expected ~70" % k)
    if p is None or p <= 0:
        fails.append("cosine bump prominence %r" % p)
    # 2. ⭐ THE DEFECT THIS FIXES. A MONOTONE decay has no local maximum,
    #    and must return a REAL number with is_local_max False -- never
    #    0.00000, which made a near-miss indistinguishable from a pass.
    ac2 = np.exp(-x / 300.0)
    p2, k2, is_max2 = tile_peak(ac2, 70.0)
    if is_max2:
        fails.append("a pure decay was read as having a local maximum")
    if p2 is None or k2 is None:
        fails.append("a pure decay returned None instead of a value")
    elif p2 == 0.0:
        fails.append("a pure decay returned exactly 0.00000 -- the null "
                     "this change exists to remove")
    # 3. MONOTONICITY: a stronger repeat must score higher than a weaker
    #    one, so the number means something as a magnitude.
    amps = [0.01, 0.03, 0.09]
    got = [tile_peak(np.exp(-x / 300.0)
                     + a * np.cos(2 * np.pi * x / 70.0), 70.0)[0]
           for a in amps]
    if not (got[0] < got[1] < got[2]):
        fails.append("prominence is not monotone in repeat amplitude: %r"
                     % got)
    # 4. A window too narrow to search REFUSES, and a refusal is None --
    #    distinct from a measured zero.
    p4, k4, m4 = tile_peak(np.exp(-np.arange(8) / 3.0), 3.0)
    if (p4, k4, m4) != (None, None, None):
        fails.append("a 3-lag window did not refuse: %r" % ((p4, k4, m4),))
    # 5. ⭐ A LOCAL MAXIMUM THAT SITS BELOW THE TREND must come back
    #    NEGATIVE. This is the second null the fix had to remove, and it
    #    was found on real data, not imagined: Grass at 100-300 m reads
    #    prominence -0.0108 with a strict local max at lag 97, and the
    #    Michelson clamped that to 0.00000 -- indistinguishable from "no
    #    structure" in the table.
    #
    #    Built DIRECTLY rather than from a plausible-looking signal: a
    #    strongly convex decay puts the chord above the curve everywhere
    #    in the middle, so a small bump there is a strict local maximum
    #    whose residual is still negative. Two attempts at a "natural"
    #    construction (a dip at the tile lag, a convex decay plus a tiny
    #    ripple) both produced NO local maximum instead, which is a
    #    different case.
    ac5 = np.full(400, 0.05)
    w = np.arange(57, dtype=np.float64)
    conv = 1.0 / (1.0 + 0.25 * w)          # convex, far below its chord
    # The bump must out-rise the CHORD's slope, not merely its
    # neighbours: the residual is seg minus a steeply falling line, so a
    # bump smaller than the slope still leaves the residual increasing
    # and produces no local maximum at all (measured: 1e-3 gave none).
    conv[28] = conv[27] + 0.05             # a STRICT local maximum
    ac5[42:99] = conv
    p5, k5, m5 = tile_peak(ac5, 70.0)
    if p5 is None:
        fails.append("the convex-with-bump case refused")
    elif not m5:
        fails.append("the convex-with-bump case found no local maximum, "
                     "so it does not exercise the negative-prominence path")
    elif p5 >= 0:
        fails.append("a local maximum BELOW the trend returned %+.6f; it "
                     "must be negative, not clamped to zero" % p5)
    return fails


def selftest():
    fails = _selftest_tile_peak()
    print("  tile_peak value/null/local-max contract   %s"
          % ("OK" if not fails else "WRONG"))
    # csf_threshold falls as spatial frequency rises through the band
    a, b = csf_threshold(0.5), csf_threshold(2.0)
    print("  csf 0.5 cpd %.4f > csf 2.0 cpd %.4f  %s"
          % (a, b, "OK" if a > b else "WRONG"))
    if a <= b:
        fails.append("csf_threshold did not fall with frequency")
    # a synthetic grating is found at its own period, and noise is not
    x = np.arange(512)
    grating = np.tile(np.sin(2 * np.pi * x / 40.0), (64, 1))
    peak, found, _g, _gp, _s, _p, _pk, _im = autocorr_peak(grating, 40.0)
    print("  grating period 40 -> found %s peak %.3f  %s"
          % (found, peak, "OK" if found and abs(found - 40) <= 2 else "WRONG"))
    if not found or abs(found - 40) > 2:
        fails.append("a 40 px grating was not found at 40 px")
    noise = np.random.default_rng(0).random((64, 512))
    pk, _f, _g2, _gp2, _s2, _p2, _pk2, _im2 = autocorr_peak(noise, 40.0)
    print("  white noise            -> peak %.3f  %s"
          % (pk, "OK" if pk < 0.2 else "WRONG"))
    if pk >= 0.2:
        fails.append("white noise scored as a repeat")
    # a flat field refuses rather than dividing by zero
    pk2, _, _, _, _, _, _, _ = autocorr_peak(np.ones((16, 256)), 40.0)
    print("  flat field             -> %s  %s"
          % (pk2, "OK" if pk2 is None else "WRONG"))
    if pk2 is not None:
        fails.append("a flat field did not refuse")

    # ⭐ THE DIRECTION THAT MATTERS FOR THIS TOOL: an IRREGULAR MASK over
    # pure noise must NOT score as a repeat. The bounding-box-and-fill
    # version this replaced would find the MASK's own shape.
    rng2 = np.random.default_rng(7)
    field = rng2.random((128, 512))
    blob = np.zeros((128, 512), dtype=bool)
    for cx0 in range(30, 500, 57):
        blob[:, max(0, cx0 - 12):cx0 + 12] = True
    pk3, _f3, _g3, _gp3, _s3, _p3, _pk3, _im3 = autocorr_peak(field, 40.0, blob)
    print("  noise under a striped mask -> peak %.3f  %s"
          % (pk3, "OK" if pk3 is not None and pk3 < 0.2 else "WRONG"))
    if pk3 is None or pk3 >= 0.2:
        fails.append("an irregular mask over noise scored as a repeat "
                     "(peak %r) -- the mask is leaking into the signal"
                     % pk3)
    # and a real grating UNDER the same mask is still DETECTED.
    #
    # The assertion is on the PEAK, not on the exact period. Measured: an
    # irregular striped mask degrades period LOCALISATION (the 40 px
    # grating localises at 44) while leaving the peak at 0.922 -- the
    # repeat is still plainly there. Localisation is not what the verdict
    # rests on; the michelson against the CSF threshold is. Asserting
    # +/-2 px here would be asserting a precision the masked estimator
    # does not have, and tightening a test until it fails is how a real
    # capability gets thrown away.
    pk4, f4, _g4, _gp4, _s4, _p4, _pk4, _im4 = autocorr_peak(grating[:64], 40.0, blob[:64])
    ok4 = pk4 is not None and pk4 > 0.5 and f4 is not None
    print("  grating under the same mask -> found %s peak %.3f  %s"
          % (f4, pk4, "OK" if ok4 else "WRONG"))
    if not ok4:
        fails.append("the mask hid a real 40 px grating (peak %r)" % pk4)
    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames")
    ap.add_argument("--station", default="ground")
    ap.add_argument("--out")
    ap.add_argument("--channel", default=None,
                    help="EXR channel group to measure. Default RGBA = "
                         "FinalImage. FinalImageBaseColor is the GBuffer "
                         "albedo: it carries the weightmap blend and the "
                         "surface textures and NO lighting, so it "
                         "discriminates a weights/texture period from a "
                         "shading one.")
    ap.add_argument("--prefer-png", action="store_true",
                    help="read the beauty from the display-referred PNG "
                         "even when an EXR exists. Use it to put an "
                         "EXR-bearing capture on the SAME instrument as "
                         "a PNG-only one, so a comparison between them "
                         "differs in ONE variable instead of two.")
    ap.add_argument("--depth-from", default=None,
                    help="borrow the SceneDepth pass from another "
                         "capture of the SAME camera. Needed for the "
                         "PLAYER instrument: MRQ forces temporal "
                         "samples to 1 whenever a depth pass is "
                         "requested, so temporal 8 and depth cannot be "
                         "in one render. Depth is deterministic here "
                         "(0.0000%% of pixels differ across captures).")
    ap.add_argument("--cams", default=None,
                    help="camera JSON to use instead of the ratified "
                         "station file. For a DIAGNOSTIC capture where "
                         "the station was moved: the projection must use "
                         "the camera the frame was actually rendered "
                         "from, read back from the actor.")
    ap.add_argument("--allow-linear", action="store_true",
                    help="measure STRUCTURE on a tone-curve-disabled "
                         "capture. The CSF verdict is then not a "
                         "VISIBILITY verdict and must not be compared "
                         "against a tone-curve-on table.")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        ap.print_help()
        return 1
    res = analyse(a.frames, a.station, channel=a.channel,
                  allow_linear=a.allow_linear, cams_path=a.cams,
                  depth_from=a.depth_from, prefer_png=a.prefer_png)
    print(json.dumps(res, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
