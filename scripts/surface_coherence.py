"""surface_coherence.py — does a surface belong to the PHOTOREAL lane?

⛔ SUPERSEDED AS A GATE — RECIPES.md R16 (RULED 2026-08-05, Ryan).
Photoreal-lane membership is now ruled by PROVENANCE (vendor + capture
method recorded in the ASSETS.md row), NOT by these appearance statistics:
the instrument refused on its own calibration set (see MEASURED STATUS
below), and R16 §2 ruled that adding specimens "cannot make a real
separation worse — it can only reveal there was none." This script is
RETAINED DESCRIPTIVE ONLY — it issues NO verdict that gates intake, and the
exit codes below are HISTORICAL. Use it to spot an outlier against the set,
never to admit or reject a surface.

R-ASSET step 2 is "photoreal-coherence check against WORLD_VISION.md".
Until 2026-08-05 that step was **PROSE WITH NO INSTRUMENT FOR SURFACES**
— `palette_evidence.py` measures triangle density, which only works on
meshes. Rendering a surface verdict from judgement alone is the
unfalsifiable-adjective problem the mesh metric exists to remove,
sitting inside our own recipe. This is the missing instrument.

SCOPE, RULED 2026-08-05: **a BINARY LANE CHECK, not an art-quality
score.** It answers "is this the same KIND of source as our photoscans",
nothing about whether a texture is good.

WHAT CARRIES THE VERDICT, AND WHAT DOES NOT
--------------------------------------------
**SET COMPOSITION IS PACKAGING, NOT CONTENT.** Megascans ship
`B/H/N/ORM`; Pack_Bonus ships
`basecolor/height/normal/roughness/ambientocclusion`. Those set shapes
differ, so set composition *would* separate the classes perfectly — and
a discriminator that did so would have **learned the vendor, not the
lane**. It is reported as a descriptive feature and **EXCLUDED FROM THE
VERDICT**.

The verdict rests on **spatial statistics of the albedo and normal**:

  `spec_slope`  Radially-averaged power-spectrum slope of the albedo.
                Natural images are broadband with a roughly 1/f^a
                falloff. Procedural authoring concentrates energy
                differently — repeated stroke structure and synthetic
                gradients do not produce the same spectrum.

  `norm_hf`     Fraction of the NORMAL map's spectral energy above a
                mid-band cutoff. Photoscanned normals carry measurable
                high-frequency chaos from real micro-geometry; authored
                normals are smoother or patterned.

  `palette`     Shannon entropy of the albedo's colour distribution,
                5 bits per channel. Stylized packs work from constrained
                palettes; photoscans inherit the full spread of a real
                material under real light.

CALIBRATION AND ITS HONEST LIMITS
----------------------------------
Calibrated on two KNOWN classes and reported with a MARGIN:

  photoreal   the ambientCG photoscans already intaken
  stylized    `Content/Pack_Bonus` (Lord Enot, Substance Designer)

**The instrument is not trusted until the two classes separate with
margin**, and a HOLDOUT that played no part in calibration must land on
the correct side. Wild Grass is that holdout.

*Precision note:* the photoreal class here is **ambientCG**, not
Megascans — the same photoscan lane, accurately named. The holdout is
Megascans, so a pass also demonstrates the instrument generalises across
photoscan vendors rather than fitting one.

**ONE CODE PATH.** Every class goes through the identical function.
A metric that differed by class — even by file format handling — would
be measuring the pipeline, not the pixels.

MEASURED STATUS 2026-08-05: **THIS INSTRUMENT REFUSES ON ITS OWN
CALIBRATION SET AND IS NOT YET USABLE.** No feature separates the two
classes — the gap is 0.0000 on all three, with the stylized range lying
entirely INSIDE the photoreal range. The photoreal class spans snow
(palette 2.11) to ground (9.51), and its within-class spread (1.47,
0.70, 7.40) dwarfs a between-class gap of zero.

**MATERIAL IDENTITY DOMINATES AUTHORING METHOD.** The classes are
defined by PROVENANCE; the features measure APPEARANCE; appearance is
driven far more by what a material IS than by how it was authored.

Controlled on material — grass against grass — two of three features DO
separate, consistently:

    spec_slope   photoreal 1.1224   stylized [1.1422, 1.4857]  SEPARATED
    norm_hf      photoreal 0.6509   stylized [0.7521, 0.8574]  SEPARATED

So the signal is real but was being drowned. Conditioning on material
family (non-negotiable 22) would need a photoreal calibration specimen per
family, and at the time only one family had one (the holdout). **R16 §2
CLOSED this path** — "adding specimens cannot make a real separation worse,
it can only reveal there was none" — and ruled the lane by PROVENANCE
instead. This block is kept as the record of WHY, not as a to-do.

Exit codes (HISTORICAL — R16 retired the gate; see the banner above):
  0  calibrated with margin, holdout correct
  2  fewer than 2 specimens in a class (inputs missing or too few)
  4  classes do NOT separate with margin, or the holdout failed
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = 1024          # analysis resolution; power-of-two for the FFT


def _load_gray(path, size=SAMPLE):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert("L").resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float64) / 255.0


def _load_rgb(path, size=SAMPLE):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float64) / 255.0


def _radial_power(gray):
    """(freq, power) radially averaged, DC removed, Hann-windowed."""
    g = gray - gray.mean()
    n = g.shape[0]
    w = np.hanning(n)
    g = g * w[:, None] * w[None, :]        # kill edge-wrap ringing
    f = np.fft.fftshift(np.fft.fft2(g))
    p = (np.abs(f) ** 2)
    cy = cx = n // 2
    y, x = np.indices(p.shape)
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2).astype(np.int64)
    nbins = n // 2
    tot = np.bincount(r.ravel(), p.ravel(), minlength=nbins + 1)[:nbins]
    cnt = np.bincount(r.ravel(), minlength=nbins + 1)[:nbins]
    with np.errstate(invalid="ignore", divide="ignore"):
        prof = tot / np.maximum(cnt, 1)
    freq = np.arange(nbins)
    return freq[1:], prof[1:]


def spectral_slope(gray):
    """Fit power ~ f^-a over a mid band. Returns a (positive = falloff)."""
    freq, prof = _radial_power(gray)
    lo = max(4, len(freq) // 64)
    hi = len(freq) // 2                     # avoid Nyquist/resample artefacts
    f = freq[lo:hi]
    p = prof[lo:hi]
    ok = p > 0
    if ok.sum() < 16:
        return float("nan")
    a = np.polyfit(np.log(f[ok]), np.log(p[ok]), 1)[0]
    return float(-a)


def hf_energy_ratio(gray, cut=0.25):
    """Share of spectral energy above `cut` of Nyquist."""
    freq, prof = _radial_power(gray)
    if prof.sum() <= 0:
        return float("nan")
    # weight each radial bin by its circumference -> true energy share
    w = prof * freq
    k = int(len(freq) * cut)
    return float(w[k:].sum() / max(w.sum(), 1e-12))


def palette_entropy(rgb, bits=5):
    """Shannon entropy (bits) of the quantised colour distribution."""
    q = (rgb * (2 ** bits - 1)).round().astype(np.int64)
    key = (q[:, :, 0] << (2 * bits)) | (q[:, :, 1] << bits) | q[:, :, 2]
    _, counts = np.unique(key.ravel(), return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def features(albedo_path, normal_path):
    """THE ONE CODE PATH. Every class is measured by this function."""
    rgb = _load_rgb(albedo_path)
    gray = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    out = {
        "spec_slope": spectral_slope(gray),
        "palette": palette_entropy(rgb),
        "norm_hf": float("nan"),
    }
    if normal_path and os.path.isfile(normal_path):
        out["norm_hf"] = hf_energy_ratio(_load_gray(normal_path))
    return out


# --------------------------------------------------------------------
def _pair(albedo, normals):
    for n in normals:
        if os.path.isfile(n):
            return albedo, n
    return albedo, None


def collect(spec):
    rows = []
    for name, alb, nrm in spec:
        if not os.path.isfile(alb):
            print("  SKIP {0}: missing {1}".format(name, alb))
            continue
        a, n = _pair(alb, nrm)
        f = features(a, n)
        f["name"] = name
        rows.append(f)
    return rows


def margin(a_vals, b_vals):
    """Gap between the two classes, in units of pooled spread.

    Reported rather than a p-value: with 5 and 6 specimens a p-value
    would imply a precision the sample size does not support. The gap
    and the spread are the honest statement.
    """
    a, b = np.asarray(a_vals, float), np.asarray(b_vals, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    lo_hi = (a.min() - b.max()) if a.min() > b.max() else None
    hi_lo = (b.min() - a.max()) if b.min() > a.max() else None
    gap = lo_hi if lo_hi is not None else hi_lo
    pooled = math.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2.0)
    return {
        "separated": gap is not None,
        "gap": float(gap) if gap is not None else 0.0,
        "pooled_sd": float(pooled),
        "gap_over_sd": float(gap / pooled) if (gap is not None
                                               and pooled > 0) else 0.0,
        "photoreal_range": [float(a.min()), float(a.max())],
        "stylized_range": [float(b.min()), float(b.max())],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-gap-sd", type=float, default=1.0,
                    help="required class gap in pooled SDs for a feature "
                         "to be trusted for the verdict")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args(argv)

    F = os.path.join(REPO_ROOT, "Free")
    photoreal = []
    for sid in ("Ground037", "Rock026", "Rock051", "Rock063", "Snow006"):
        d = os.path.join(F, "{0}_4K-PNG".format(sid))
        photoreal.append((
            "ambientCG/" + sid,
            os.path.join(d, "{0}_4K-PNG_Color.png".format(sid)),
            [os.path.join(d, "{0}_4K-PNG_NormalDX.png".format(sid))]))

    pb = os.path.join(F, "_intake", "packbonus")
    stylized = []
    for alb in sorted(glob.glob(os.path.join(
            pb, "**", "*_basecolor.PNG"), recursive=True)):
        stylized.append(("Pack_Bonus/" + os.path.basename(alb)
                         .replace("T_Pack_Bonus_", "")
                         .replace("_basecolor.PNG", ""),
                         alb, [alb.replace("_basecolor", "_normal")]))

    wg = os.path.join(F, "_intake", "megascans_grass", "unpacked")
    holdout = [("HOLDOUT Megascans/WildGrass",
                os.path.join(wg, "WildGrass_C.png"),
                [os.path.join(wg, "WildGrass_N.png")])]

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("analysis  : {0}x{0}, one code path for every class".format(SAMPLE))
    print("")
    print("--- PHOTOREAL class (ambientCG photoscans) ---")
    pr = collect(photoreal)
    print("--- STYLIZED class (Pack_Bonus, Substance Designer) ---")
    st = collect(stylized)
    print("--- HOLDOUT (played NO part in calibration) ---")
    ho = collect(holdout)
    if len(pr) < 2 or len(st) < 2:
        print("REFUSE: need at least 2 specimens per class")
        return 2

    print("")
    hdr = "{0:<34} {1:>11} {2:>11} {3:>11}"
    print(hdr.format("surface", "spec_slope", "norm_hf", "palette"))
    for row in pr + st + ho:
        print(hdr.format(row["name"][:34], "{0:.4f}".format(row["spec_slope"]),
                         "{0:.4f}".format(row["norm_hf"]),
                         "{0:.3f}".format(row["palette"])))

    print("")
    print("--- CLASS SEPARATION (verdict features only) ---")
    trusted, report = [], {}
    for feat in ("spec_slope", "norm_hf", "palette"):
        m = margin([r[feat] for r in pr], [r[feat] for r in st])
        report[feat] = m
        if m is None:
            print("  {0:<12} insufficient data".format(feat))
            continue
        ok = m["separated"] and m["gap_over_sd"] >= args.min_gap_sd
        if ok:
            trusted.append(feat)
        print("  {0:<12} photoreal [{1:+.4f}, {2:+.4f}]  stylized "
              "[{3:+.4f}, {4:+.4f}]".format(
                  feat, *m["photoreal_range"], *m["stylized_range"]))
        print("  {0:<12} gap {1:+.4f} = {2:.2f} pooled SD   {3}".format(
            "", m["gap"], m["gap_over_sd"],
            "TRUSTED" if ok else "NOT trusted (below {0} SD)".format(
                args.min_gap_sd)))

    # Diagnostics are written BEFORE any early return. A refusal is
    # exactly when the numbers are most worth keeping -- returning
    # without them would make the failure harder to diagnose than a
    # success, which is backwards.
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"photoreal": pr, "stylized": st, "holdout": ho,
                       "separation": report, "trusted": trusted}, fh,
                      indent=1)

    print("")
    if not trusted:
        print("REFUSE: no feature separates the classes with margin. The "
              "instrument is NOT trustworthy and no verdict is issued on "
              "any surface. Reporting this is the correct outcome — a "
              "discriminator that cannot tell the calibration classes "
              "apart cannot tell anything apart.")
        return 4
    print("Verdict features (separated by >= {0} pooled SD): {1}".format(
        args.min_gap_sd, ", ".join(trusted)))
    print("EXCLUDED by ruling: map-set composition — that is PACKAGING, "
          "not content, and would learn the vendor rather than the lane.")

    # --- holdout ---------------------------------------------------
    print("")
    print("--- HOLDOUT TEST ---")
    rc = 0
    for row in ho:
        votes = []
        for feat in trusted:
            m = report[feat]
            pmid = sum(m["photoreal_range"]) / 2.0
            smid = sum(m["stylized_range"]) / 2.0
            v = row[feat]
            if np.isnan(v):
                continue
            votes.append(("photoreal" if abs(v - pmid) < abs(v - smid)
                          else "stylized", feat, v))
        print("  {0}".format(row["name"]))
        if not votes:
            # NN13: a zero-vote holdout must REFUSE, not render a verdict.
            # All trusted features were NaN for this surface (e.g. its normal
            # map was absent), so "ph > len(votes)/2" would be 0 > 0.0 =
            # False and silently print "STYLIZED (0/0)" — silence wearing a
            # verdict's clothes.
            print("      REFUSE: no non-NaN verdict feature for this holdout "
                  "(0 of {0} trusted features usable).".format(len(trusted)))
            rc = 4
            continue
        ph = sum(1 for v in votes if v[0] == "photoreal")
        verdict = "PHOTOREAL" if ph > len(votes) / 2.0 else "STYLIZED"
        for cls, feat, v in votes:
            print("      {0:<12} {1:+.4f}  -> {2}".format(feat, v, cls))
        print("      VERDICT: {0}  ({1}/{2} verdict features)".format(
            verdict, ph, len(votes)))
        if verdict != "PHOTOREAL":
            rc = 4
            print("      HOLDOUT FAILED. The instrument is not trusted: it "
                  "must accept a photoscan it never saw during "
                  "calibration.")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"photoreal": pr, "stylized": st, "holdout": ho,
                       "separation": report, "trusted": trusted}, fh,
                      indent=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
