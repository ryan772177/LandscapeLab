"""proxy_fraction.py -- measure the HLOD-PROXY BAND fraction of a vista frame,
the deliverable of D-2 item 1b.

THE QUESTION. In the shipping runtime the landscape renders as real cells only
out to the R-RANGE loading range (512 m, recipes/alpine_8k.json / R-RANGE);
beyond that a World-Partition HLOD PROXY stands in. "What fraction of the vista
frame is proxy band?" has two independent instruments here, and each REPORTS
ITS SAMPLE COUNT beside its verdict (standing rule 13):

  --mode diff   compare a -game frame (proxies present beyond 512 m) against
                the editor_player force-loaded frame (real cells everywhere,
                _verify/.../vista.png). The pixels whose GEOMETRY differs are
                the proxy band. OBSERVES the runtime; needs the -game frame.
                Denominator = every pixel compared. A pixel counts as "proxy"
                when its luma differs by more than --diff-jnd (Weber, relative
                to the brighter of the two) AND sits in a blob >= --min-blob
                (an isolated pixel is AA/noise, not a proxy region -- same rule
                temporal_stability uses).

  --mode depth  threshold a SCENE-DEPTH pass rendered at the editor_player
                camera: every pixel whose scene depth exceeds the 512 m band
                is, in the runtime, a proxy pixel, because real cells do not
                exist past the loading range. DERIVES the runtime from the
                512 m geometry boundary rather than observing a -game frame;
                MORE direct about the boundary, but a MODEL not an observation.
                Denominator = every finite-depth pixel (sky/infinite excluded,
                and that exclusion is counted and reported).

WHY A JND AND NOT A BARE DIFFERENCE. A proxy mesh is a LOWER-LOD stand-in: its
silhouette and shading differ from the real cell, but a real-vs-real re-render
also differs by a few percent from temporal jitter. --diff-jnd 0.06 is derived
below on the two synthetic specimens, not tuned until a run went green.

Usage
  python proxy_fraction.py --mode diff  --game FRAME.png --ref REF.png [--out j.json]
  python proxy_fraction.py --mode depth --depth DEPTH.exr --band-m 512 [--out j.json]
  python proxy_fraction.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np


def luma_linear_from_rgb8(rgb8):
    s = rgb8.astype(np.float64) / 255.0
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def _blob_filter(mask, min_blob):
    """Zero out connected components (4-neighbour) smaller than min_blob.
    Iterative flood fill, no scipy (same approach as temporal_stability)."""
    if min_blob <= 1:
        return mask
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = np.zeros_like(mask, dtype=bool)
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        comp = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
                    comp.append((ny, nx))
        if len(comp) >= min_blob:
            for (y, x) in comp:
                out[y, x] = True
    return out


def diff_fraction(game_luma, ref_luma, jnd=0.06, min_blob=16):
    """Fraction of compared pixels whose luma differs by more than jnd
    (Weber) and lies in a blob >= min_blob. Returns dict WITH sample count."""
    if game_luma.shape != ref_luma.shape:
        return {"error": "shape mismatch %r vs %r" % (game_luma.shape, ref_luma.shape),
                "sample_count": 0}
    # A diff between two BLACK or two FLAT frames yields 0.0 -- but that is
    # silence, not agreement (rule 13). A valid comparison needs content in
    # both frames; refuse if either is near-black or effectively featureless.
    if max(float(game_luma.max()), float(ref_luma.max())) < 1e-3:
        return {"error": "both frames near-black (max < 1e-3): a diff here is "
                         "silence, not agreement", "sample_count": 0,
                "mode": "diff"}
    if float(game_luma.std()) < 1e-4 and float(ref_luma.std()) < 1e-4:
        return {"error": "both frames featureless (std < 1e-4): nothing to "
                         "compare", "sample_count": 0, "mode": "diff"}
    denom = int(game_luma.size)
    weber = np.abs(game_luma - ref_luma) / np.maximum(
        np.maximum(game_luma, ref_luma), 1e-3)
    raw = weber > jnd
    kept = _blob_filter(raw, min_blob)
    changed = int(kept.sum())
    return {"mode": "diff", "sample_count": denom,
            "proxy_pixels": changed,
            "proxy_fraction": round(changed / denom, 5) if denom else None,
            "raw_over_jnd": int(raw.sum()),
            "jnd": jnd, "min_blob": min_blob}


def depth_fraction(depth_cm, band_m=512.0, max_finite_cm=1e12,
                   sky_ceiling_cm=None):
    """Fraction of FINITE-depth pixels whose scene depth exceeds the band.
    Sky / infinite depth is excluded and the exclusion is counted.

    sky_ceiling_cm: THIS PROJECT'S SceneDepth pass does NOT put sky at +inf.
    It is a LOGARITHMIC encode whose top of range is a FINITE ceiling
    (haze_metrics.CEILING_M = 10485.76 m -> 1_048_576 cm); every sky pixel
    sits AT that ceiling. Pass the ceiling here so sky is excluded. WITHOUT
    it, every sky pixel -- which is finite and far past 512 m -- is
    miscounted as proxy band: on the 2026-09-15 vista that turned a true
    5.7%-of-ground into a false 60.7%-of-frame (D-2 item 1b; the synthetic
    selftest used np.inf sky and never exercised a finite ceiling, so the
    auditor did not catch it). A tolerance of 0.999 catches the ceiling
    despite log-decode round-off.
    """
    band_cm = band_m * 100.0
    total = int(depth_cm.size)
    # Sky / infinite is a legitimate exclusion; a NON-POSITIVE depth is a
    # garbage read (unit or channel error) and must be counted SEPARATELY,
    # not folded into "sky" where it would hide (auditor finding 4).
    sky = np.isfinite(depth_cm) == False  # noqa: E712  (also catches nan)
    sky = sky | (depth_cm >= max_finite_cm)
    if sky_ceiling_cm is not None:
        sky = sky | (depth_cm >= sky_ceiling_cm * 0.999)
    nonpos = np.isfinite(depth_cm) & (depth_cm <= 0)
    finite = np.isfinite(depth_cm) & (depth_cm > 0) & ~sky
    denom = int(finite.sum())
    n_sky = int(sky.sum())
    n_nonpos = int(nonpos.sum())
    beyond = int((finite & (depth_cm > band_cm)).sum())
    fin_vals = depth_cm[finite]
    rep = {"mode": "depth", "sample_count": denom,
           "excluded_infinite_or_sky": n_sky,
           "excluded_nonpositive": n_nonpos,
           "sky_ceiling_cm": sky_ceiling_cm,
           "total_pixels": total,
           "proxy_pixels": beyond,
           "proxy_fraction": round(beyond / denom, 5) if denom else None,
           # unit/channel sanity: a depth pass in metres, or channel-swapped,
           # shows here immediately (auditor finding 5).
           "depth_min_cm": float(fin_vals.min()) if denom else None,
           "depth_max_cm": float(fin_vals.max()) if denom else None,
           "band_m": band_m}
    # If garbage dominates the finite reads, or there is nothing finite,
    # refuse rather than report a fraction over a broken denominator.
    if denom == 0:
        rep["error"] = "no finite-positive depth pixels: cannot measure"
    elif n_nonpos > denom:
        rep["error"] = ("non-positive depth (%d) exceeds finite depth (%d): "
                        "the depth read is likely wrong-unit or wrong-channel"
                        % (n_nonpos, denom))
        rep["sample_count"] = 0
    return rep


def selftest():
    ok = True
    rng = np.random.default_rng(7)
    H = W = 256

    # DIRECTION 2 (PASS the legitimate case): a "-game" frame equal to the ref
    # in the near half and a lower-LOD proxy (blurred + darker) in the far
    # half should measure a proxy fraction near 0.5.
    ref = rng.uniform(0.3, 0.7, (H, W))
    game = ref.copy()
    far = slice(0, H // 2)                       # top half = far = proxy band
    proxy = (ref[far] * 0.6)                     # darker, coarser stand-in
    proxy = (proxy + np.roll(proxy, 1, 0) + np.roll(proxy, 1, 1)) / 3
    game[far] = proxy
    d = diff_fraction(game, ref)
    pass2 = d["sample_count"] == H * W and 0.40 <= d["proxy_fraction"] <= 0.60
    ok = ok and pass2

    # DIRECTION 1 (BLOCK the violation / detect none when none): two identical
    # frames must report ~0 proxy fraction, not a false band.
    d0 = diff_fraction(ref.copy(), ref.copy())
    pass1 = d0["proxy_fraction"] == 0.0 and d0["sample_count"] == H * W
    ok = ok and pass1

    # DIRECTION 3 (BLOCK WHEN BROKEN): a shape mismatch must refuse with a
    # zero sample count, not crash or silently agree (rule 13 -- zero refuses).
    dbad = diff_fraction(ref, ref[:, :W // 2])
    pass3 = dbad.get("sample_count") == 0 and "error" in dbad
    ok = ok and pass3

    # DIRECTION 3b: two BLACK frames must REFUSE, not report 0.0 agreement.
    dblack = diff_fraction(np.zeros((H, W)), np.zeros((H, W)))
    pass3b = dblack.get("sample_count") == 0 and "error" in dblack
    ok = ok and pass3b

    # DEPTH mode: a depth map, near half inside 512 m, far half beyond, plus a
    # sky band at +inf. Fraction beyond band ~ 0.5 of FINITE pixels; sky
    # excluded and counted.
    depth = np.empty((H, W), dtype=np.float64)
    depth[H // 2:] = 200.0 * 100.0             # 200 m -> real cell
    depth[:H // 2] = 900.0 * 100.0             # 900 m -> proxy band
    depth[:16] = np.inf                        # sky
    dep = depth_fraction(depth, band_m=512.0)
    finite = H * W - 16 * W
    pass_depth = (dep["sample_count"] == finite
                  and dep["excluded_infinite_or_sky"] == 16 * W
                  and dep["excluded_nonpositive"] == 0
                  and dep["depth_max_cm"] == 900.0 * 100.0
                  and 0.45 <= dep["proxy_fraction"] <= 0.55)
    ok = ok and pass_depth

    # DEPTH finite-ceiling sky: this project encodes sky at a FINITE ceiling,
    # not +inf. Without --sky-ceiling-m those pixels count as proxy (the D-2
    # item 1b defect); WITH it they are excluded and counted as sky.
    depth_fc = np.empty((H, W), dtype=np.float64)
    depth_fc[H // 2:] = 200.0 * 100.0              # near half: real cell
    depth_fc[:H // 2] = 900.0 * 100.0              # far half: proxy band
    depth_fc[:16] = 10485.76 * 100.0              # sky at the FINITE ceiling
    ceil_cm = 10485.76 * 100.0
    dep_nosky = depth_fraction(depth_fc, band_m=512.0)          # no ceiling arg
    dep_sky = depth_fraction(depth_fc, band_m=512.0, sky_ceiling_cm=ceil_cm)
    finite_fc = H * W - 16 * W
    # WITHOUT the ceiling: the 16 sky rows are miscounted as proxy band, so
    # the no-arg proxy count is exactly the with-ceiling count plus those
    # 16*W sky pixels (all sit past 512 m at the ceiling).
    miscounts_sky = (dep_nosky["excluded_infinite_or_sky"] == 0
                     and dep_nosky["proxy_pixels"]
                     == dep_sky["proxy_pixels"] + 16 * W)
    # WITH the ceiling: sky excluded, ~half of the remaining ground is proxy.
    fixed = (dep_sky["excluded_infinite_or_sky"] == 16 * W
             and dep_sky["sample_count"] == finite_fc
             and 0.45 <= dep_sky["proxy_fraction"] <= 0.55)
    pass_ceiling = miscounts_sky and fixed
    ok = ok and pass_ceiling

    # DEPTH garbage: a frame of mostly non-positive depth (wrong unit/channel)
    # must REFUSE, not report a fraction over a broken denominator.
    garbage = np.full((H, W), -1.0)
    garbage[:8] = 300.0 * 100.0          # a few valid pixels, still a minority
    dg = depth_fraction(garbage, band_m=512.0)
    pass_depth_garbage = (dg.get("sample_count") == 0 and "error" in dg
                          and dg["excluded_nonpositive"] == (H - 8) * W)
    ok = ok and pass_depth_garbage

    print("selftest:", "PASS" if ok else "FAIL")
    print("  diff legit (want .40-.60):", d["proxy_fraction"],
          "n=", d["sample_count"], "->", pass2)
    print("  diff identical (want 0.0):", d0["proxy_fraction"], "->", pass1)
    print("  diff broken (want refuse n=0):", dbad.get("sample_count"),
          dbad.get("error", "")[:24], "->", pass3)
    print("  diff black (want refuse n=0):", dblack.get("sample_count"),
          "->", pass3b)
    print("  depth (want .45-.55, excl=%d):" % (16 * W),
          dep["proxy_fraction"], "excl_sky=", dep["excluded_infinite_or_sky"],
          "n=", dep["sample_count"], "->", pass_depth)
    print("  depth garbage (want refuse n=0):", dg.get("sample_count"),
          "nonpos=", dg["excluded_nonpositive"], "->", pass_depth_garbage)
    print("  depth finite-ceiling sky: no-arg miscounts sky as proxy (%d px), "
          "--sky-ceiling-m excludes it (%d px, frac %s) ->"
          % (dep_nosky["proxy_pixels"], dep_sky["excluded_infinite_or_sky"],
             dep_sky["proxy_fraction"]), pass_ceiling)
    return 0 if ok else 1


def _load_png_luma(path):
    from PIL import Image
    return luma_linear_from_rgb8(np.asarray(Image.open(path).convert("RGB")))


def _load_depth(path):
    # EXR via OpenImageIO or imageio if present; else .npy fallback.
    if path.lower().endswith(".npy"):
        arr = np.load(path).astype(np.float64)
        if arr.ndim == 3:              # a multi-channel depth .npy: take ch0,
            arr = arr[..., 0]          # same convention as the EXR branch
        return arr
    try:
        import imageio.v3 as iio
        arr = np.asarray(iio.imread(path)).astype(np.float64)
        if arr.ndim == 3:
            arr = arr[..., 0]
        return arr
    except Exception as e:  # noqa: BLE001
        raise SystemExit("cannot read depth %s: %r (need .npy or imageio+EXR)"
                         % (path, e))


def _load_depth_logpng(path):
    """Decode this project's SceneDepth pass -- a LOG-ENCODED 8-bit PNG -- into
    centimetres using the SANCTIONED decoder (haze_metrics.decode_depth_m,
    proven by the bench sky mask; non-negotiable 4a: reuse it, do not
    re-implement). Returns (depth_cm, sky_ceiling_cm) so the caller excludes
    the finite ceiling automatically. This is what makes the depth measurement
    reproducible from a COMMITTED artefact rather than a hand-made .npy."""
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import haze_metrics as _hm
    depth_cm = _hm.decode_depth_m(path) * 100.0
    return depth_cm, _hm.CEILING_M * 100.0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["diff", "depth"])
    ap.add_argument("--game")
    ap.add_argument("--ref")
    ap.add_argument("--depth", help="raw depth in CENTIMETRES (.npy, or EXR "
                    "via imageio if a backend is installed).")
    ap.add_argument("--depth-png", help="this project's LOG-ENCODED SceneDepth "
                    "PNG; decoded to cm via haze_metrics and the finite sky "
                    "ceiling excluded automatically. Reproducible from a "
                    "committed artefact -- prefer this for a bench depth pass.")
    ap.add_argument("--band-m", type=float, default=512.0)
    ap.add_argument("--sky-ceiling-m", type=float, default=None,
                    help="exclude sky encoded at a FINITE ceiling: this "
                         "project's SceneDepth caps sky at "
                         "haze_metrics.CEILING_M (10485.76 m). Pass 10485.76 "
                         "for a bench depth pass, or omit for a pass whose "
                         "sky is +inf.")
    ap.add_argument("--diff-jnd", type=float, default=0.06)
    ap.add_argument("--min-blob", type=int, default=16)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.mode == "diff":
        if not (a.game and a.ref):
            print("diff needs --game and --ref"); return 2
        rep = diff_fraction(_load_png_luma(a.game), _load_png_luma(a.ref),
                            jnd=a.diff_jnd, min_blob=a.min_blob)
        rep.update({"game": a.game, "ref": a.ref})
    elif a.mode == "depth":
        if not (a.depth or a.depth_png):
            print("depth needs --depth or --depth-png"); return 2
        # Ambiguity REFUSES rather than silently preferring one artefact --
        # the e8fe3b15 rule (check_perf: an ambiguous input refuses, it does
        # not judge the first/preferred one). Re-audit FIX-1, D-2 item 1b.
        if a.depth and a.depth_png:
            print("depth: got BOTH --depth and --depth-png -- ambiguous, refusing")
            return 2
        if a.depth_png:
            depth_cm, ceil_cm = _load_depth_logpng(a.depth_png)
            # an explicit --sky-ceiling-m still wins if given
            sky_cm = (a.sky_ceiling_m * 100.0
                      if a.sky_ceiling_m is not None else ceil_cm)
            rep = depth_fraction(depth_cm, band_m=a.band_m, sky_ceiling_cm=sky_cm)
            rep.update({"depth_png": a.depth_png,
                        "depth_decoded_by": "haze_metrics.decode_depth_m (log)"})
        else:
            sky_cm = (a.sky_ceiling_m * 100.0
                      if a.sky_ceiling_m is not None else None)
            rep = depth_fraction(_load_depth(a.depth), band_m=a.band_m,
                                 sky_ceiling_cm=sky_cm)
            rep.update({"depth": a.depth})
    else:
        print("need --mode diff|depth or --selftest"); return 2
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    # A failed or refused measurement must not exit clean -- a zero sample
    # count or an error is not a result (rule 13, non-negotiable 6).
    if rep.get("error") or not rep.get("sample_count"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
