"""check_weightmap_feather.py -- CPU invariants for the Brief 7 P1 feather.

The composite weightmap `textures/alpine_8k_weights.png` is now FEATHERED: each
stored channel is Gaussian-blurred (sigma texels, recipe
`material.weightmap_feather_sigma_px`) before quantising, so two surfaces meet
along a ~2*sigma m ramp instead of a hard ~1 m mask edge. The un-feathered bake
shattered the terrain into ~1 m blocks under minification
(research/brief7/p1_block_diff.md, feather_handoff.md).

Three invariants, each with the bound made non-vacuous by a control:

  1. FEATHERED AT BOUNDARIES, per channel. In a band of +-ceil(3*sigma) texels
     around each channel's own mask edge, at least FEATHER_MIN of the FEATHERED
     texels are strictly intermediate (0 < x < 255). NEGATIVE CONTROL: the
     pre-feather source (round(w8a*255)) has only a 1-2 texel ramp, so its
     intermediate fraction in the SAME band is far lower -- the feathered
     fraction must exceed it by RAMP_MARGIN. (The smooth w8a source is NOT
     hard-binary at the 1-texel ring -- the derivation's own narrow smoothsteps
     already ramp there -- so an absolute "source < 25%" bound would be fragile;
     the load-bearing claim is that the feather WIDENED the ramp, which the
     band-vs-source comparison proves.)

  2. SUM(stored) <= 255 EVERYWHERE (8-bit). The four feathered channels
     partition with the shader meadow remainder = 1 - sum(stored); a sum over
     255 drives that remainder negative (renders as a black bruise). The
     renormalisation in derive_layer_weights.feather_stored_channels caps it.

  3. SNOW-LINE REGISTRATION HOLDS. The snow must still sit on the flank the sun
     misses -- hillshade_snow_check.score() on the FEATHERED snow channel must
     return PASS (this is the "hillshade_snow_check unchanged" invariant, run on
     the composite the material actually samples, not the w8a source). AND the
     50%-isoline altitude must not drift by more than half the derivation's own
     60 m vertical snow feather: |mean_altitude(feathered snow>=0.5) -
     mean_altitude(pre-feather snow>=0.5)| <= SNOW_FEATHER_M/2. Feathering a
     dappled mask erodes thin low slivers (lifting the mean a little); the
     bound keeps that small and the aspect discrimination is the real proof.
     (The skyline-IoU RENDER is a post-merge acceptance step, not offline.)

READ-ONLY, offline: reads the composite PNG, the w8a source and the heightmap;
no editor.

    python scripts/check_weightmap_feather.py
    python scripts/check_weightmap_feather.py --self-test
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

COMPOSITE = "textures/alpine_8k_weights.png"
SOURCE_A = "textures/alpine_8k_w8a.png"        # smooth 4-channel source (RGBA)
RECIPE = "recipes/alpine_8k.json"
FEATHER_MIN = 0.25                             # invariant 1 (absolute floor)
RAMP_MARGIN = 0.25                             # invariant 1 (feathered - source)
SUM_MAX_8BIT = 255 + 2                          # invariant 2 (quantisation slack)
NAMES = ("snow", "rock", "scree", "forest")


def _edge(binary):
    """Texels where a binary mask differs from a 4-neighbour (both sides)."""
    b = binary
    d = np.zeros_like(b, dtype=bool)
    d[:-1, :] |= b[:-1, :] != b[1:, :]
    d[1:, :] |= b[1:, :] != b[:-1, :]
    d[:, :-1] |= b[:, :-1] != b[:, 1:]
    d[:, 1:] |= b[:, 1:] != b[:, :-1]
    return d


def band_feathered_fractions(comp8, source01, radius):
    """Per channel: fraction of a +-radius boundary BAND that is strictly
    intermediate (0 < x < 255) in `comp8`. Bands come from the SOURCE mask
    edges (an independent map from the feathered composite -- NN0). Returns
    (fracs, counts): a list of 4 fractions (nan for a channel with no boundary)
    and the per-channel band texel counts (reported beside the verdict so a
    zero-count band cannot masquerade as agreement -- rule 13)."""
    fracs, counts = [], []
    for c in range(4):
        band = binary_dilation(_edge(source01[..., c] > 0.5), iterations=radius)
        n = int(band.sum())
        counts.append(n)
        if n == 0:
            fracs.append(float("nan"))
            continue
        v = comp8[..., c][band]
        fracs.append(int(np.count_nonzero((v > 0) & (v < 255))) / n)
    return fracs, counts


def _load_rgba(rel):
    p = os.path.join(REPO, rel)
    if not os.path.isfile(p):
        raise SystemExit("REFUSE: not found: %s" % rel)
    im = np.asarray(Image.open(p))
    if im.ndim != 3 or im.shape[2] < 4:
        raise SystemExit("REFUSE: %s must be 4-channel RGBA, got shape %r"
                         % (rel, getattr(im, "shape", None)))
    return im[..., :4]


def main():
    rec = json.load(io.open(os.path.join(REPO, RECIPE), encoding="utf-8"))
    try:
        sigma = float(rec["material"]["weightmap_feather_sigma_px"])
    except (KeyError, TypeError, ValueError):
        raise SystemExit(
            "REFUSE: recipes/alpine_8k.json material.weightmap_feather_sigma_px "
            "is absent or non-numeric -- the feathered bake is unverifiable "
            "without the sigma it was baked at.")
    if not sigma > 0.0:
        raise SystemExit("REFUSE: weightmap_feather_sigma_px must be > 0, "
                         "got %r" % (sigma,))
    radius = int(math.ceil(3.0 * sigma))

    comp = _load_rgba(COMPOSITE).astype(np.uint16)         # feathered, 0..255
    src01 = _load_rgba(SOURCE_A).astype(np.float32) / 255.0  # smooth source
    src8 = np.round(src01 * 255.0).astype(np.uint16)        # pre-feather (=old)
    if comp.shape[:2] != src8.shape[:2]:
        raise SystemExit("REFUSE: composite %r and source %r differ in size"
                         % (comp.shape[:2], src8.shape[:2]))

    print("weightmap feather invariants (Brief 7 P1)  sigma=%.2f px, band +-%d"
          % (sigma, radius))
    ok = True

    # 1. FEATHERED AT BOUNDARIES, with the source ramp as the negative control
    f_feat, counts = band_feathered_fractions(comp, src01, radius)
    f_src, _ = band_feathered_fractions(src8, src01, radius)
    print("  1. feathered fraction in each channel's boundary band:")
    for nm, ff, fs, n in zip(NAMES, f_feat, f_src, counts):
        good = (n > 0) and (ff >= FEATHER_MIN) and (ff >= fs + RAMP_MARGIN)
        print("     %-7s band %d px  feathered %.3f (>= %.2f and "
              ">= source+%.2f) %s   source %.3f"
              % (nm, n, ff, FEATHER_MIN, RAMP_MARGIN,
                 "ok" if good else "FAIL", fs))
        if not good:
            ok = False

    # 2. SUM(stored) <= 255 everywhere
    ssum = comp.sum(axis=2)
    smax = int(ssum.max())
    over = int(np.count_nonzero(ssum > SUM_MAX_8BIT))
    print("  2. sum(stored) max %d (bound %d = 255 + 2 quantisation slack; "
          "four independently-rounded channels can reach a byte sum of 257 and "
          "the shader Saturates the remainder), texels over bound: %d"
          % (smax, SUM_MAX_8BIT, over))
    if smax > SUM_MAX_8BIT:
        print("     FAIL: stored sum exceeds the 255+2 quantisation bound -- "
              "the meadow remainder would go negative beyond what the shader "
              "Saturate absorbs (black bruise)")
        ok = False

    # 3. SNOW-LINE REGISTRATION: aspect (hillshade) + a bounded altitude drift
    import hillshade_snow_check as hs
    from derive_layer_weights import SNOW_ASPECT_HALF_M, SNOW_FEATHER_M
    ls = rec["landscape"]
    h16 = np.asarray(Image.open(os.path.join(REPO, rec["heightmap"]["source"])))
    z_span = float(ls["z_scale_cm"]) / 100.0
    z_base = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) / 100.0
    h_m = h16.astype(np.float32) / 65535.0 * z_span + z_base
    sp_m = float(ls["scale_xy_cm"]) / 100.0
    sun = rec["lighting"]["sun"]
    L = hs.sun_vector(sun["azimuth_deg"], sun["elevation_deg"])
    base = float([l for l in rec["material"]["layers"]
                  if l["name"] == "Snow"][0]["height_m"][0])
    snow_feat = comp[..., 0].astype(np.float32) / 255.0
    r = hs.score(h_m, snow_feat, sp_m, L, base, SNOW_ASPECT_HALF_M)
    print("  3. snow aspect registration on the FEATHERED snow: %s "
          "(shaded/lit ratio %s, lit frac %s)"
          % (r.get("verdict"), r.get("ratio"), r.get("frac_snow_gt_half_lit")))
    if r.get("verdict") != "PASS":
        print("     FAIL: the feathered snow no longer sits on the shaded flank "
              "(%s)" % r.get("error", "aspect discrimination lost"))
        ok = False
    snow_pre = src8[..., 0] >= 128
    snow_post = comp[..., 0] >= 128
    npre, npost = int(snow_pre.sum()), int(snow_post.sum())
    bound = SNOW_FEATHER_M / 2.0
    if npre == 0 or npost == 0:
        print("     FAIL: snow 50%% mask empty (pre %d, post %d px) -- the "
              "altitude drift cannot be measured; a zero-sample drift is not "
              "agreement (rule 13)" % (npre, npost))
        ok = False
    else:
        drift = abs(float(h_m[snow_post].mean()) - float(h_m[snow_pre].mean()))
        print("     snow-line altitude drift %.1f m over pre %d / post %d px "
              "(bound %.1f m = half the derivation's %.0f m vertical feather)"
              % (drift, npre, npost, bound, SNOW_FEATHER_M))
        if drift > bound:
            print("     FAIL: the feather shifted the snow line more than half "
                  "its own vertical feather")
            ok = False

    print("PASS: weightmap is feathered at boundaries, partitions, and holds "
          "the snow line." if ok else "FAILED")
    sys.exit(0 if ok else 1)


# --------------------------------------------------------------------------
# selftest -- three directions, synthetic (no dependence on the shipped PNG)
# --------------------------------------------------------------------------

def selftest():
    from derive_layer_weights import feather_stored_channels
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # A hard vertical two-layer boundary: left half snow, right half rock.
    n, sigma, radius = 96, 1.5, 5
    snow = np.zeros((n, n), np.float32)
    rock = np.zeros((n, n), np.float32)
    snow[:, : n // 2] = 1.0
    rock[:, n // 2:] = 1.0
    scree = np.zeros((n, n), np.float32)
    forest = np.zeros((n, n), np.float32)
    src = np.stack([snow, rock, scree, forest], axis=-1)
    src8 = np.round(src * 255).astype(np.uint16)

    feat, rem, over = feather_stored_channels(
        [snow, rock, scree, forest], sigma)
    comp8 = np.round(np.clip(np.stack(feat, axis=-1), 0, 1) * 255).astype(
        np.uint16)

    print("direction 1 -- feathered band clears the floor AND beats the source")
    ff, _ = band_feathered_fractions(comp8, src, radius)
    fs, _ = band_feathered_fractions(src8, src, radius)
    check("snow feathered >= 0.25 and >= source + 0.25",
          ff[0] >= 0.25 and ff[0] >= fs[0] + 0.25)
    check("rock feathered >= 0.25 and >= source + 0.25",
          ff[1] >= 0.25 and ff[1] >= fs[1] + 0.25)

    print("direction 2 -- the un-feathered SOURCE is genuinely narrower")
    check("source snow band fraction < feathered (ramp widened)",
          fs[0] < ff[0])
    check("source rock band fraction < feathered (ramp widened)",
          fs[1] < ff[1])

    print("direction 3 -- partition holds and the renorm catches over-sum")
    check("feathered sum <= 1 everywhere (remainder >= 0)",
          float(np.stack(feat, -1).sum(-1).max()) <= 1.0 + 1e-6)
    check("remainder never negative", float(rem.min()) >= -1e-6)
    check("three overlapping full masks renormalise to sum <= 1",
          float(np.stack(feather_stored_channels(
              [np.ones((8, 8), np.float32)] * 3 + [np.zeros((8, 8), np.float32)],
              sigma)[0], -1).sum(-1).max()) <= 1.0 + 1e-6)

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(selftest())
    main()
