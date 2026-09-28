"""unpack_orm.py — split a packed ORM texture into discrete role maps.

RULED 2026-08-05: **UNPACK TO DISCRETE ROLES AT INTAKE. Do not teach the
material declaration a packed form.**

WHY THE PACKED FORM IS REFUSED AT THE MATERIAL LAYER
----------------------------------------------------
`make_landscape_material`'s preflight, its sampler-type rules and its
post-build assertion are all THREE PROJECTIONS OF ONE DECLARATION over
discrete roles. NN21's channel discipline — every channel computed or
explicitly declared inert — is stated per role as well. A packed branch
would fork every one of those guarantees for one vendor's packaging
convention.

So ORM-PACKED is an **INTAKE PATH THAT ENDS IN DISCRETE ASSETS**, never
a material-side format. R-ASSET's ORM-PACKED branch (written for
`rock_collection_04`) describes the same thing.

THE CHANNEL MAPPING IS VERIFIED PER PACK, NOT ASSUMED
------------------------------------------------------
R-ASSET records the mapping as **confirmed by convention + consistency,
NOT by a nonzero specimen**, and says to verify per pack rather than
trust the acronym. This tool re-runs that verification on every pack.

**TWO DISCRIMINATORS, and the primary one is HEIGHT.**

    PRIMARY   corr(R, height) POSITIVE, and larger IN MAGNITUDE than
              corr(G, height)  (the gate is on abs value, not signed)
              -> R is occlusion. Occlusion tracks DEPTH: high points are
              exposed, low points are occluded, whatever colour they are.
    SUPPORT   |corr(G, albedo)| > |corr(R, albedo)|
              -> G is roughness, the pigment-tracking channel.

**The albedo-only test is ROCK-CALIBRATED and does not transfer.** Its
premise — cavities darken in albedo and occlusion together — holds for
photoscanned rock, where albedo variation is largely geometry-driven
shading. On GRASS the albedo varies by PIGMENT, and pigment has no
reason to track occlusion. Measured on Wild Grass the rock test FAILED
a mapping that is in fact correct:

    R  corr(height) +0.189   corr(albedo) -0.134   <- AO
    G  corr(height) -0.051   corr(albedo) -0.623   <- Roughness

R tracks height 3.7x more than G; G tracks albedo 4.6x more than R. Two
ORTHOGONAL signals giving opposite assignments is a stronger result than
the original rock case, which rested on one.

Without a height map the tool falls back to the rock-calibrated albedo
test **and says in its report that it used the weaker instrument.**

**B REMAINS UNDISCRIMINATED.** A flat-zero B is consistent with
"metallic, correctly zero on a dielectric" AND with "unused padding",
and no dielectric specimen can separate them. Grass is dielectric like
the rocks, so this pack cannot settle it either. B is therefore reported
and **declared inert per NN21** — NOT written as a role (its measured mean
and sd are recorded in provenance, it is not emitted as a zero map) — with the
upgrade condition unchanged: promote the mapping to *measured* the first
time a metallic-bearing asset shows a nonzero B landing where metal is
visibly present.

PROVENANCE
----------
The original ORM is retained and every unpacked output is hash-linked to
it, so an unpacked map can always be traced to the packed source it came
from (NN20: adopted artefacts are copies at stable names, hash-proven
against their source at adoption time).

Exit codes:
  0  unpacked, mapping verified
  2  inputs missing or unreadable
  4  the channel mapping FAILED verification — nothing written
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_rgb(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path)
    return np.asarray(im.convert("RGB"))


def luminance(rgb):
    """Rec.709 luminance of an 8-bit RGB array, float64."""
    a = rgb.astype(np.float64)
    return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]


def verify_mapping(orm, albedo_lum, height=None, sample=2048):
    """(ok, report). Correlate each ORM channel against HEIGHT (the PRIMARY
    discriminator and gate, when a height map is supplied) and against albedo
    luminance (the rock-calibrated support/fallback).

    Subsampled on a regular grid: a 4K pair is 16.7M px per channel and
    the correlation is stable long before that. The grid is regular, not
    random, so the result is reproducible without carrying a seed.
    """
    step = max(1, min(orm.shape[0], orm.shape[1]) // sample)
    o = orm[::step, ::step].astype(np.float64)
    lum = albedo_lum[::step, ::step]
    if o.shape[:2] != lum.shape:
        n0 = min(o.shape[0], lum.shape[0])
        n1 = min(o.shape[1], lum.shape[1])
        o, lum = o[:n0, :n1], lum[:n0, :n1]
    flat_lum = lum.ravel()
    rep = {"samples": int(flat_lum.size), "step": int(step), "channels": {}}
    corrs = {}
    for i, name in enumerate("RGB"):
        ch = o[:, :, i].ravel()
        sd = ch.std()
        if sd < 1e-9:
            corrs[name] = None
            rep["channels"][name] = {
                "mean": float(ch.mean()) / 255.0, "sd": float(sd) / 255.0,
                "corr_vs_albedo": None,
                "note": "FLAT — no variance, correlation undefined"}
            continue
        c = float(np.corrcoef(ch, flat_lum)[0, 1])
        corrs[name] = c
        rep["channels"][name] = {
            "mean": float(ch.mean()) / 255.0, "sd": float(sd) / 255.0,
            "corr_vs_albedo": c}

    # ---- HEIGHT CORRELATION: the PRIMARY discriminator ----------------
    # THE ALBEDO TEST IS ROCK-CALIBRATED AND DOES NOT TRANSFER.
    # Its premise is "cavities darken in the albedo and in the occlusion
    # map together", which is true of photoscanned ROCK, where albedo
    # variation is largely geometry-driven shading. On GRASS the albedo
    # varies by PIGMENT -- green, yellow, dead-brown blades -- and that
    # has no reason to track occlusion. Measured on Wild Grass:
    # corr(R, albedo) = -0.134, so the rock test FAILED a mapping that
    # is in fact correct. Same class as costing a vendor LOD chain with
    # a model solved for generated chains.
    #
    # Height is pigment-independent and physical: OCCLUSION TRACKS
    # DEPTH. High points are exposed, low points are occluded, whatever
    # colour they are. Roughness is a surface property and has no such
    # depth relationship. Measured on Wild Grass:
    #     R  corr(height) +0.189   corr(albedo) -0.134
    #     G  corr(height) -0.051   corr(albedo) -0.623
    # R tracks height 3.7x more than G; G tracks albedo 4.6x more than
    # R. Two orthogonal signals, opposite assignments, one conclusion.
    hcorr = {}
    if height is not None:
        hs = height[::step, ::step]
        n0 = min(hs.shape[0], lum.shape[0])
        n1 = min(hs.shape[1], lum.shape[1])
        hflat = hs[:n0, :n1].astype(np.float64).ravel()
        for i, name in enumerate("RGB"):
            ch = o[:n0, :n1, i].ravel()
            if ch.std() < 1e-9 or hflat.std() < 1e-9:
                hcorr[name] = None
            else:
                hcorr[name] = float(np.corrcoef(ch, hflat)[0, 1])
            rep["channels"][name]["corr_vs_height"] = hcorr[name]

    ok = True
    reasons = []
    primary = "height" if hcorr.get("R") is not None else "albedo"
    rep["primary_discriminator"] = primary

    if primary == "height":
        # AO tracks depth positively; roughness must track it far less.
        if hcorr["R"] is None or hcorr["R"] <= 0:
            ok = False
            reasons.append(
                "R must correlate POSITIVELY with HEIGHT to be occlusion "
                "(high points exposed, low points occluded); got {0!r}"
                .format(hcorr["R"]))
        elif hcorr["G"] is not None and abs(hcorr["G"]) >= abs(hcorr["R"]):
            ok = False
            reasons.append(
                "R must track height MORE than G does; got R {0:+.4f} vs "
                "G {1:+.4f}".format(hcorr["R"], hcorr["G"]))
        # And roughness must still be the albedo-tracking channel.
        if (corrs["G"] is None or corrs["R"] is None
                or abs(corrs["G"]) <= abs(corrs["R"])):
            ok = False
            reasons.append(
                "G must track ALBEDO more than R does to be roughness; got "
                "G {0!r} vs R {1!r}".format(corrs["G"], corrs["R"]))
    else:
        # No height map: fall back to the rock-calibrated albedo test,
        # and SAY that the weaker instrument was used.
        rep["caveat"] = ("no height map supplied; fell back to the "
                         "ROCK-CALIBRATED albedo test, which does not "
                         "transfer to pigment-varying surfaces")
        if corrs["R"] is None or corrs["R"] <= 0:
            ok = False
            reasons.append("R must correlate POSITIVELY with albedo "
                           "luminance; got {0!r}".format(corrs["R"]))
        if corrs["G"] is None or corrs["G"] >= 0:
            ok = False
            reasons.append("G must correlate NEGATIVELY with albedo "
                           "luminance; got {0!r}".format(corrs["G"]))
    rep["verdict"] = "PASS" if ok else "FAIL"
    rep["reasons"] = reasons
    return ok, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--orm", required=True, help="packed ORM image")
    ap.add_argument("--albedo", required=True,
                    help="albedo/basecolor, for the correlation check")
    ap.add_argument("--height", default=None,
                    help="height/displacement map. STRONGLY PREFERRED: it "
                         "is the pigment-independent discriminator; "
                         "without it the weaker rock-calibrated albedo "
                         "test is used and the report says so.")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", required=True,
                    help="surface id, e.g. WildGrass")
    args = ap.parse_args(argv)

    for p in (args.orm, args.albedo):
        if not os.path.isfile(p):
            print("REFUSE: missing input {0}".format(p))
            return 2

    try:
        orm = _load_rgb(args.orm)
        alb = _load_rgb(args.albedo)
    except Exception as _e:                       # noqa: BLE001
        # exit 2 = "inputs missing OR UNREADABLE" -- a present-but-corrupt
        # image would otherwise raise past here and exit 1.
        print("REFUSE: could not read an input image ({0}: {1})".format(
            type(_e).__name__, _e))
        return 2
    print("ORM    : {0}  {1}x{2}".format(os.path.basename(args.orm),
                                         orm.shape[1], orm.shape[0]))
    print("albedo : {0}  {1}x{2}".format(os.path.basename(args.albedo),
                                         alb.shape[1], alb.shape[0]))
    print("")

    hgt = None
    if args.height:
        if not os.path.isfile(args.height):
            print("REFUSE: missing height map {0}".format(args.height))
            return 2
        from PIL import Image as _I
        _I.MAX_IMAGE_PIXELS = None
        try:
            hgt = np.asarray(_I.open(args.height).convert("L"))
        except Exception as _e:                   # noqa: BLE001
            print("REFUSE: could not read height map ({0}: {1})".format(
                type(_e).__name__, _e))
            return 2
        print("height : {0}  {1}x{2}".format(os.path.basename(args.height),
                                             hgt.shape[1], hgt.shape[0]))
    ok, rep = verify_mapping(orm, luminance(alb), height=hgt)
    print("--- channel mapping verification (per pack, not assumed) ---")
    for name in "RGB":
        c = rep["channels"][name]
        cv = c["corr_vs_albedo"]
        hv = c.get("corr_vs_height")
        print("  {0}  mean {1:.4f}  sd {2:.4f}  corr(height) {3:>10}  "
              "corr(albedo) {4:>10}".format(
                  name, c["mean"], c["sd"],
                  "{0:+.4f}".format(hv) if hv is not None else "n/a",
                  "{0:+.4f}".format(cv) if cv is not None else "flat"))
    print("  primary discriminator: {0}".format(
        rep.get("primary_discriminator", "?")))
    print("  verdict: {0}".format(rep["verdict"]))
    for r in rep["reasons"]:
        print("    - {0}".format(r))
    if not ok:
        print("")
        print("REFUSE: the channel mapping did not verify on THIS pack. "
              "Nothing written. R-ASSET records the mapping as convention "
              "plus consistency, never as a standard, and this is the "
              "check that makes that caveat load-bearing.")
        return 4

    os.makedirs(args.out_dir, exist_ok=True)
    from PIL import Image
    written = []
    # R -> ambient occlusion, G -> roughness. Single-channel, linear.
    for idx, role in ((0, "AO"), (1, "R")):
        out = os.path.join(args.out_dir,
                           "{0}_{1}.png".format(args.name, role))
        Image.fromarray(orm[:, :, idx], mode="L").save(out)
        written.append((role, out))
        print("  wrote {0:<28} from ORM channel {1}".format(
            os.path.basename(out), "RGB"[idx]))

    b = rep["channels"]["B"]
    print("")
    print("--- channel B: DECLARED INERT (non-negotiable 21) ---")
    print("  mean {0:.6f}  sd {1:.6f}".format(b["mean"], b["sd"]))
    print("  NOT written as a role. A flat-zero B is consistent with")
    print("  'metallic, correctly zero on a dielectric' AND with 'unused")
    print("  padding'; grass is dielectric, so this pack cannot separate")
    print("  them either. Reported and declared inert rather than")
    print("  silently dropped. Upgrade condition unchanged: a")
    print("  metallic-bearing asset with a nonzero B landing where metal")
    print("  is visibly present.")

    prov = {
        "surface": args.name,
        "source_orm": os.path.relpath(args.orm, REPO_ROOT).replace("\\", "/"),
        "source_orm_sha256": _sha256(args.orm),
        "source_albedo": os.path.relpath(args.albedo,
                                         REPO_ROOT).replace("\\", "/"),
        "source_albedo_sha256": _sha256(args.albedo),
        "mapping_verification": rep,
        "channel_b": {"status": "DECLARED INERT",
                      "mean": b["mean"], "sd": b["sd"]},
        "outputs": {},
    }
    for role, path in written:
        prov["outputs"][role] = {
            "path": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
            "sha256": _sha256(path)}
    pj = os.path.join(args.out_dir, "{0}_orm_provenance.json".format(args.name))
    with io.open(pj, "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=1, sort_keys=True)
    print("")
    print("  provenance {0}".format(os.path.relpath(pj, REPO_ROOT)))
    print("  every output hash-linked to the ORM it came from, and the")
    print("  original ORM is retained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
