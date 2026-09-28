"""Derive normal + roughness from an albedo, with the CONVENTION MEASURED.

WHY THIS EXISTS
---------------
The C0 donor house ships SEVEN Poly Haven maps and every one of them is a
DIFFUSE. There is no normal and no roughness anywhere in the zip, and the
operator's five generated replacements are albedos too. So every surface in
this unit needs its other channels derived.

WHAT IS MEASURED AND WHAT IS AUTHORED -- stated plainly, because they are not
the same kind of claim (standing rule 10)
------------------------------------------------------------------------------
  MEASURED   the normal-map CONVENTION. ambientCG ships `_NormalDX` and
             `_NormalGL` for the same surface alongside a `_Displacement`, so
             the sign test can be positive-controlled against files the vendor
             has already labelled. `--calibrate` does exactly that and must
             label both correctly before any derivation is trusted.

  DERIVED    the normal ITSELF, from albedo luminance treated as a height
             field. This is an APPROXIMATION, not a measurement: luminance is
             pigment plus shading plus geometry, and only the third belongs in
             a normal. It is high-passed first so that large-scale albedo
             variation (a dark plank beside a light one) does not become a
             large-scale bump. On a photo of a rough surface it is a good
             approximation; on a surface whose colour is decorative it is not.

  AUTHORED   the roughness BASE. There is no route from a diffuse photograph
             to a physical roughness value, and pretending otherwise would be
             a number with no ground truth. Each role declares its base in the
             manifest and the map modulates it slightly by local detail. The
             run prints `roughness_is_authored: TRUE` so no later reader can
             mistake it for a measurement.

THE CONVENTION, AND ITS CITATION
--------------------------------
The project ruled DX for every ambientCG surface and the ruling is recorded at
`scripts/make_asset_manifest.py:340-345`; `make_foliage_material.py:18`
restates it as "green down". This tool writes DX and CHECKS ITS OWN SIGN by
running its output back through the same sign test -- note this shares the
derivation's row-axis premise (non-negotiable 0), so it catches a sign flip,
not a wrong shared premise; only --calibrate (vendor labels) can.

Usage:
    python scripts/derive_material_maps.py --calibrate
    python scripts/derive_material_maps.py --manifest recipes/c0_materials.json
    (--out <dir> chooses the output dir; default refs/derived_v1)
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texture_16bit import load_float          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Image.MAX_IMAGE_PIXELS = None


def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


# THE READ GOES THROUGH texture_16bit.load_float, NOT THROUGH PIL DIRECTLY.
# The first version of this tool used Image.convert("L") on ambientCG's
# `_Displacement.png` and every calibration row came back at correlation
# 0.000. That was not the sign test failing -- those files are `I;16`, and
# PIL truncates them, returning ALL 255 for Ground037. The red CONTROL is
# what caught it: it is supposed to be strongly positive under BOTH
# conventions, so a zero there is an instrument fault and cannot be read as
# a verdict about green. See texture_16bit.load_float.
def load_rgb(p):
    a = load_float(p)
    return a if a.ndim == 3 else np.stack([a, a, a], -1)


def load_gray(p):
    a = load_float(p)
    return a if a.ndim == 2 else luma(a)


def grad(h):
    """Central differences on a WRAPPED field -- the textures tile, so the
    gradient at the border is a real gradient, not an edge artefact."""
    d_col = 0.5 * (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1))
    d_row = 0.5 * (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0))
    return d_col, d_row


def corr(a, b):
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else 0.0


def classify_convention(normal_rgb, height):
    """Return (label, corr_G, corr_R).

    For a height field the tangent normal is proportional to
    (-dH/dx, -dH/dy, 1), with x,y in TEXTURE space. Image rows increase
    DOWNWARD, so y_up = -row and therefore

        -dH/dy_up  =  +dH/drow

    which makes the OpenGL (green-UP) convention the POSITIVE one:

        RED   tracks -dH/dcol under BOTH conventions   <- the CONTROL
        GREEN tracks +dH/drow under GL, -dH/drow under DX

    ⛔ THE SIGN ABOVE IS THE OPPOSITE OF WHAT THIS TOOL FIRST ASSERTED, AND
    THE VENDOR'S OWN LABELS ARE WHY. `--calibrate` reads ambientCG's ten
    files -- five surfaces, each shipping a `_NormalDX` AND a `_NormalGL`
    beside one `_Displacement` -- and with the first sign it labelled ALL TEN
    backwards while the red control sat at +0.53 to +0.90. A control that
    strong rules out a broken height field or a flipped row axis, so the only
    thing left was the predicted sign, and the ten labels outrank it. Fixing
    the bar to match the data would be worthless here precisely because
    nothing was being tuned: the sign is binary and the vendor already knows
    the answer.

    The red channel is what makes this a test rather than a coin flip: it has
    the same expected sign either way, so if red comes back negative the
    instrument is wrong and no verdict about green is worth anything. That is
    not decoration -- it is what caught PIL's 16-bit truncation an hour before
    it caught this.
    """
    d_col, d_row = grad(height)
    cr = corr(normal_rgb[..., 0] - 0.5, -d_col)
    cg = corr(normal_rgb[..., 1] - 0.5, d_row)
    if cr <= 0.0:
        return "INSTRUMENT FAULT (red control failed)", cg, cr
    return ("GL" if cg > 0 else "DX"), cg, cr


def calibrate():
    """Prove the sign test labels vendor-labelled files correctly."""
    print("CALIBRATION -- the convention test against ambientCG's own labels")
    print("  ground truth is the VENDOR FILENAME; the test never sees it")
    print("")
    rows, ok = [], True
    for disp in sorted(glob.glob(os.path.join(
            REPO, "Free", "*_4K-PNG", "*_Displacement.png"))):
        d = os.path.dirname(disp)
        sid = os.path.basename(disp).replace("_Displacement.png", "")
        h = load_gray(disp)
        for conv in ("DX", "GL"):
            p = os.path.join(d, sid + "_Normal" + conv + ".png")
            if not os.path.exists(p):
                continue
            n = load_rgb(p)
            if n.shape[:2] != h.shape[:2]:
                continue
            got, cg, cr = classify_convention(n, h)
            good = (got == conv)
            ok = ok and good
            rows.append((sid, conv, got, cg, cr, good))
    if not rows:
        print("  NO CALIBRATION PAIRS FOUND -- that is 'could not look'.")
        return 5
    print("  %-30s %-9s %-9s %9s %9s  %s"
          % ("surface", "labelled", "measured", "corr(G)", "corr(R)", ""))
    for sid, conv, got, cg, cr, good in rows:
        print("  %-30s %-9s %-9s %9.3f %9.3f  %s"
              % (sid, conv, got, cg, cr, "ok" if good else "!! WRONG"))
    print("")
    print("  red control positive on all rows: %s"
          % ("YES" if all(r[4] > 0 for r in rows) else "NO"))
    print("  %d of %d labelled correctly" % (sum(r[5] for r in rows), len(rows)))
    print("")
    print("convention test %s"
          % ("DISCRIMINATES -- safe to use"
             if ok else "!! DOES NOT DISCRIMINATE -- do not derive normals"))
    return 0 if ok else 4


def highpass(h, sigma_frac=0.06):
    """Remove large-scale albedo variation before treating luma as height.

    Done by a wrapped box blur applied twice (a cheap Gaussian), so it respects
    tiling. sigma_frac is a fraction of the SHORT axis, so the cut-off scales
    with the texture rather than with its pixel count.
    """
    n = max(3, int(round(min(h.shape) * sigma_frac)) | 1)
    k = np.ones(n) / n
    pad = n // 2
    lo = h
    for _ in range(2):
        w = np.concatenate([lo[:, -pad:], lo, lo[:, :pad]], axis=1)
        lo = np.apply_along_axis(lambda m: np.convolve(m, k, "valid"), 1, w)
        w = np.concatenate([lo[-pad:, :], lo, lo[:pad, :]], axis=0)
        lo = np.apply_along_axis(lambda m: np.convolve(m, k, "valid"), 0, w)
    return h - lo


def derive_normal(albedo, strength):
    h = highpass(luma(albedo))
    d_col, d_row = grad(h)
    # DX = green DOWN, so green is NEGATIVE dH/drow (see classify_convention:
    # measured against ambientCG's own labels, not assumed).
    nx, ny = -d_col * strength, -d_row * strength
    nz = np.ones_like(nx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1) * 0.5 + 0.5


def derive_roughness(albedo, base, gain):
    """AUTHORED base, modulated by local detail. Not a measurement."""
    det = np.abs(highpass(luma(albedo), 0.02))
    s = det.std()
    m = np.clip(det / (4.0 * s), 0.0, 1.0) if s > 1e-9 else np.zeros_like(det)
    return np.clip(base + gain * (m - 0.5), 0.0, 1.0)


def save_img(a, p):
    Image.fromarray((np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)).save(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--manifest")
    ap.add_argument("--out", default="refs/derived_v1")
    a = ap.parse_args()
    if a.calibrate:
        return calibrate()
    if not a.manifest:
        ap.error("--manifest or --calibrate")

    with open(os.path.join(REPO, a.manifest), encoding="utf-8") as f:
        man = json.load(f)
    out_dir = os.path.join(REPO, a.out)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    print("derive -- normal (DX, MEASURED convention) + roughness (AUTHORED)")
    print("")
    print("  %-16s %8s %7s %9s  %s"
          % ("role", "strength", "rough", "self-conv", "source"))
    bad, written = [], []
    for role, spec in sorted(man["roles"].items()):
        src = os.path.join(REPO, spec["albedo"])
        if not os.path.exists(src):
            bad.append((role, "albedo missing: " + spec["albedo"]))
            continue
        img = load_rgb(src)
        strength = float(spec.get("normal_strength", 8.0))
        nrm = derive_normal(img, strength)
        rough = derive_roughness(img, float(spec["roughness_base"]),
                                 float(spec.get("roughness_gain", 0.25)))
        # SELF-CHECK: run the output back through the convention test against
        # the height field it was built from. It must read DX.
        got, _, _ = classify_convention(nrm, highpass(luma(img)))
        if got != "DX":
            # A map whose OWN proof reads non-DX is wrong -- do NOT write it and
            # do NOT count it as written (it was previously saved and tallied
            # while also flagged bad, so "wrote N" counted a failed role).
            bad.append((role, "derived normal reads " + got + ", not DX -- "
                        "NOT written"))
            print("  %-16s %8.1f %7.2f %9s  %s  !! NOT WRITTEN"
                  % (role, strength, float(spec["roughness_base"]), got,
                     os.path.basename(spec["albedo"])))
            continue
        save_img(nrm, os.path.join(out_dir, role + "_N.png"))
        save_img(rough, os.path.join(out_dir, role + "_R.png"))
        written.append(role)
        print("  %-16s %8.1f %7.2f %9s  %s"
              % (role, strength, float(spec["roughness_base"]), got,
                 os.path.basename(spec["albedo"])))
    print("")
    if not written and not bad:
        # NN13 / rule 13: an empty manifest derived nothing. Refuse rather than
        # print "wrote 0" and exit 0, matching calibrate()'s no-pairs refusal.
        print("  REFUSE: the manifest declares no roles -- nothing to derive. "
              "That is 'could not look', not success.")
        return 5
    print("  wrote %d roles x 2 maps -> %s" % (len(written), a.out))
    print("  roughness_is_authored: TRUE -- a base per role, never measured")
    if bad:
        print("")
        for r, why in bad:
            print("  !! %-16s %s" % (r, why))
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
