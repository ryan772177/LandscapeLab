"""Measure a MetaHuman face DNA's head mesh, and simulate a region edit,
WITHOUT AN EDITOR.

WHY THIS EXISTS
---------------
`scripts/hero_face/likeness/edit_dna_geometry.py` reaches the running Unreal
editor (`ue_exec` -> `LandscapeLabTools.ReadDNAMeshes` /
`WriteDNAVertexDeltaInBox`). On 2026-08-23 the editor was held by another
process and a second remote-execution client wins silently while the victim
hangs (CLAUDE.md, 2026-08-10). Every number in
`_verify/20260823_face/face_plan.md` therefore comes from the DNA BYTES
instead, which is a genuinely different representation from DNACalib's
reader -- and that is what makes the agreement below evidence rather than a
restatement.

POSITIVE CONTROL FOR THE PARSE
------------------------------
`RECIPES.md` R-HEROGEOM:9109-9111 records, from the plugin's DNACalib
reader, that `head_lod0_mesh` spans
    X -19.034..19.034   Y 140.878..178.439   Z -11.616..14.988
`--baseline` prints the same three ranges off the bytes. If they disagree,
the parse is wrong and nothing else in this file may be believed.

FORMAT, read from the header rather than remembered
---------------------------------------------------
    00  "DNA"
    03  u16 BE generation (2)
    05  u16 BE version (5)
    07  u32 BE section count (9)
    0B  9 x { char name[4], u16 verMajor, u16 verMinor,
              u32 absolute offset, u32 size }
Section "geom": u32 mesh count, u32 payload size, then mesh 0's positions as
THREE separate u32-count-prefixed big-endian float32 arrays (xs, ys, zs).

THE MASK IS NOT REIMPLEMENTED FROM MEMORY. `_weights` is a line-for-line
transcription of
`LandscapeLab/Plugins/LandscapeLabEditor/Source/LandscapeLabEditor/Private/
LandscapeLabTools.cpp:1341-1372`.

USAGE
    python measure_dna_offline.py --baseline <dna>
    python measure_dna_offline.py --simulate <dna>
    python measure_dna_offline.py --verify <edited.dna> --against <base.dna>
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

HEAD_VERTS = 24049

# R-HEROGEOM:9109-9111, produced by the plugin's DNACalib reader.
RECORDED_BOUNDS = ((-19.034, 19.034), (140.878, 178.439), (-11.616, 14.988))

# The eight edits of the angular-hero pass (J1/J2/M1/M2/A1/A2/B1/B2). Boxes and
# deltas are in the DNA's OWN space: X=Left, Y=Up, Z=Front, centimetres.
# TWO WIDTH REGIONS (jaw, mid), TWO DEPTH REGIONS (buccal, malar). Width and
# depth are separated because
# a lateral component on the malar box fights the narrowing it sits above:
# measured, a +0.08 cm lateral malar delta took buccal/zygomatic the WRONG WAY,
# 0.9466 -> 0.9548.
#
# EVERY box's FEATHER REACH stays below Y 164.5. manifest.json:467
# (`_eye_band_rule`) forbids any edit box, INCLUDING ITS REACH, from entering
# Y 164.5..169.5. Reach is box_max.Y + feather:
#   M 163.2 + 1.1 = 164.3    A 160.5 + 2.0 = 162.5    B 163.5 + 0.9 = 164.4
#
# ORDER IS PART OF THE SPEC. Each call re-evaluates its mask on the CURRENT
# positions, so W (lateral) before A/B (depth) is not interchangeable with the
# reverse.
EDITS = [
    ("J1 jaw wid L", (4.0, 153.2, 0.0), (7.8, 158.5, 12.5), 1.5,
     (-0.28, 0.0, 0.0)),
    ("J2 jaw wid R", (-7.8, 153.2, 0.0), (-4.0, 158.5, 12.5), 1.5,
     (0.28, 0.0, 0.0)),
    ("M1 mid wid L", (4.0, 158.8, 4.0), (7.4, 163.2, 12.5), 1.1,
     (-0.15, 0.0, 0.0)),
    ("M2 mid wid R", (-7.4, 158.8, 4.0), (-4.0, 163.2, 12.5), 1.1,
     (0.15, 0.0, 0.0)),
    ("A1 buccal L", (3.8, 157.5, 5.0), (7.6, 160.5, 12.5), 2.0,
     (0.0, 0.0, -0.35)),
    ("A2 buccal R", (-7.6, 157.5, 5.0), (-3.8, 160.5, 12.5), 2.0,
     (0.0, 0.0, -0.35)),
    ("B1 malar  L", (5.0, 162.2, 5.0), (8.0, 163.5, 12.5), 0.9,
     (0.0, 0.0, 0.22)),
    ("B2 malar  R", (-8.0, 162.2, 5.0), (-5.0, 163.5, 12.5), 0.9,
     (0.0, 0.0, 0.22)),
]


def read_head(path):
    """-> dict with sha, header facts and the head mesh's X/Y/Z arrays."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:3] != b"DNA":
        raise SystemExit("%s does not start with the DNA magic" % path)
    gen, ver = struct.unpack_from(">HH", data, 3)
    (nsec,) = struct.unpack_from(">I", data, 7)
    off, sec = 11, {}
    for _ in range(nsec):
        nm = data[off:off + 4].decode("ascii")
        vmaj, vmin, so, sz = struct.unpack_from(">HHII", data, off + 4)
        sec[nm] = (vmaj, vmin, so, sz)
        off += 16
    if "geom" not in sec:
        raise SystemExit("no geom section in %s" % path)
    gs = sec["geom"][2]
    (meshes,) = struct.unpack_from(">I", data, gs)
    p = gs + 8
    arrs = []
    for k in range(3):
        q = p + k * (4 + HEAD_VERTS * 4)
        (cnt,) = struct.unpack_from(">I", data, q)
        if cnt != HEAD_VERTS:
            raise SystemExit(
                "expected %d vertices in mesh 0, array %d says %d -- this "
                "file is not laid out as assumed and the parse REFUSES "
                "rather than guessing" % (HEAD_VERTS, k, cnt))
        arrs.append(np.frombuffer(data, ">f4", HEAD_VERTS,
                                  q + 4).astype(np.float64))
    return {"path": path, "bytes": len(data), "gen": gen, "ver": ver,
            "meshes": meshes, "sha": hashlib.sha256(data).hexdigest(),
            "P": np.stack(arrs, axis=1)}


def check_parse(r, quiet=False):
    P = r["P"]
    ok = True
    for i, axis in enumerate("XYZ"):
        lo, hi = RECORDED_BOUNDS[i]
        got = (P[:, i].min(), P[:, i].max())
        good = abs(got[0] - lo) < 0.05 and abs(got[1] - hi) < 0.05
        ok = ok and good
        if not quiet:
            print("  %s  bytes %9.4f..%9.4f   R-HEROGEOM %9.4f..%9.4f   %s"
                  % (axis, got[0], got[1], lo, hi, "AGREE" if good else
                     "DISAGREE"))
    return ok


def _weights(P, bmin, bmax, band):
    """LandscapeLabTools.cpp:1341-1372, transcribed."""
    bmin = np.asarray(bmin, float)
    bmax = np.asarray(bmax, float)
    dd = np.maximum.reduce([bmin - P, np.zeros_like(P), P - bmax])
    dist = np.sqrt((dd * dd).sum(axis=1))
    W = np.zeros(dist.shape)
    core = dist <= 0.0
    W[core] = 1.0
    if band > 0.0:
        bm = (~core) & (dist < band)
        t = dist[bm] / band
        W[bm] = 1.0 - t * t * (3.0 - 2.0 * t)
    return W, int(core.sum())


def apply_edits(P0, edits=EDITS, report=True):
    P = P0.copy()
    if report:
        print("%-12s %7s %9s %10s   selected-vertex extents"
              % ("edit", "core", "weighted", "untouched"))
    for name, bmin, bmax, band, delta in edits:
        W, core = _weights(P, bmin, bmax, band)
        sel = W > 0.0
        S = P[sel]
        if report:
            print("%-12s %7d %9d %10d   X %7.3f..%7.3f  Y %7.3f..%7.3f  "
                  "Z %7.3f..%7.3f"
                  % (name, core, int(sel.sum()), int((~sel).sum()),
                     S[:, 0].min(), S[:, 0].max(), S[:, 1].min(),
                     S[:, 1].max(), S[:, 2].min(), S[:, 2].max()))
        P = P + W[:, None] * np.asarray(delta, float)
    return P


def half_width(P, y0, y1, depth=8.0):
    """max |X| among vertices within `depth` cm of the band's frontmost point.

    EAR-FREE, and this was CHECKED rather than argued. Over |X| > 8 (the ear;
    n = 2,500, Y 161.32..171.95) the frontmost surface reaches Z 4.256, p95
    2.673, while the face front sits at Z 12.2..15.0. Band by band, from
    Y 153 to Y 168, the number of |X| > 8 vertices at or above the `zf - 8`
    gate is ZERO, worst margin 0.976 cm. A first version of this comment
    claimed the ear "never exceeds Z 2.4" -- that was the CANONICAL DNA's p95
    read as a maximum, and it was wrong by 1.9 cm on this file.
    """
    X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
    m = (Y >= y0) & (Y < y1)
    if m.sum() < 20:
        return float("nan")
    zf = Z[m].max()
    return float(np.abs(X[m & (Z >= zf - depth)]).max())


def ref_curve():
    """The SHAPE reference's own silhouette taper, normalised the same way.

    Reads hero/landmarks/bald_mediapipe.json, which capture_landmarks.py wrote
    from hero/reference/hero_face_bald_frontal.jpg -- the json names the image
    itself, so which reference this is comes from the artefact. Indices are the
    project's single declaration at capture_landmarks.py:70-80.

    LIMIT: the reference is a 2-D projection at an unmeasured pose and these
    are photographic outline points; the mesh number is a 3-D anterior
    half-width. DIFFERENT CONSTRUCTIONS. Direction-setting, not a tolerance.
    """
    import json
    with open(os.path.join(REPO_ROOT, "hero", "landmarks",
                           "bald_mediapipe.json"), "r") as fh:
        j = json.load(fh)
    P = np.array(j["landmarks_px"], float)
    ipd = j["ipd_px"]
    o = 0.5 * (P[468, :2] + P[473, :2])          # iris midpoint == origin
    u = (P[:, 0] - o[0]) / ipd
    v = (P[:, 1] - o[1]) / ipd
    oval = [356, 127, 454, 234, 323, 93, 361, 132, 288, 58, 397, 172, 365,
            136, 379, 150, 378, 149, 400, 176, 377, 148, 152]
    zyg = max(abs(u[i]) for i in (234, 454))     # CHEEK_L/R
    rows = sorted((v[i], abs(u[i]) / zyg) for i in oval)
    return (np.array([r[0] for r in rows]), np.array([r[1] for r in rows]),
            float(v[152]), j["image"])


def ref_jaw_cheek_ratio():
    """The reference silhouette's jaw/cheek ratio, COMPUTED from the landmarks
    rather than hardcoded: (|u[172]|+|u[397]|)/(|u[234]|+|u[454]|) in IPD units,
    the "172/397 over 234/454" the prints name. Reproduces the value that was
    previously a 0.8069 literal in two print statements."""
    import json
    with open(os.path.join(REPO_ROOT, "hero", "landmarks",
                           "bald_mediapipe.json"), "r") as fh:
        j = json.load(fh)
    P = np.array(j["landmarks_px"], float)
    ipd = j["ipd_px"]
    o = 0.5 * (P[468, :2] + P[473, :2])
    u = (P[:, 0] - o[0]) / ipd
    jaw = abs(u[172]) + abs(u[397])
    cheek = abs(u[234]) + abs(u[454])
    return jaw / cheek if cheek else float("nan")


def mesh_chin_y(P):
    """Lowest Y of the FACE FRONT.

    A plain "lowest vertex with a large Z" search returns Y 140.92, the mesh
    minimum: this mesh carries a chest/shoulder cap (|X| reaches 19.05 at
    Y 146) whose front reaches Z 11.2. Walk DOWN in 0.25 cm bands and stop at
    the discontinuity where the face front ends.
    """
    X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
    prev = None
    for y0 in np.arange(160.0, 150.0, -0.25):
        m = (Y >= y0) & (Y < y0 + 0.25) & (np.abs(X) < 4.0)
        if m.sum() < 5:
            continue
        zf = Z[m].max()
        if prev is not None and zf < prev - 1.5:
            return float(y0 + 0.25)
        prev = zf
    raise SystemExit("could not find the chin discontinuity")


def taper_curve_residual(P, iris_y=167.0425):
    """Mean |mesh - reference| over the normalised taper, and the rows."""
    rv, rw, vchin, img = ref_curve()
    chin = mesh_chin_y(P)
    span = iris_y - chin
    zyg = max(half_width(P, y, y + 1) for y in (163.0, 164.0, 165.0, 166.0))
    rows = []
    for y0 in np.arange(154, 168, 1.0):
        w = half_width(P, y0, y0 + 1)
        v = (iris_y - (y0 + 0.5)) / span * vchin
        if v < -0.2 or v > 1.65:      # above 1.65 the mesh measure is
            continue                  # contaminated by the under-jaw / neck
        rows.append((v, float(np.interp(v, rv, rw)), w / zyg, y0))
    # NN13: mean over zero usable bands is nan, not a residual. Refuse.
    if not rows:
        raise SystemExit("taper curve: 0 usable bands after filtering; "
                         "refusing to report a nan residual")
    res = float(np.mean([abs(m - r) for _, r, m, _ in rows]))
    return res, rows, chin, vchin, img


def taper(P):
    zyg = max(half_width(P, y, y + 1) for y in (163.0, 164.0, 165.0, 166.0))
    buc = max(half_width(P, y, y + 1) for y in (159.0, 160.0, 161.0, 162.0))
    jaw = half_width(P, 158.0, 159.0)
    return zyg, buc, jaw


def cmd_baseline(path):
    r = read_head(path)
    print("DNA        %s" % os.path.relpath(path, REPO_ROOT))
    print("  gen %d.%d  meshes %d  bytes %d" % (r["gen"], r["ver"],
                                                r["meshes"], r["bytes"]))
    print("  sha256 %s" % r["sha"])
    print()
    print("PARSE CONTROL vs R-HEROGEOM:9109-9111 (DNACalib reader)")
    ok = check_parse(r)
    print("  -> %s" % ("PARSE CORROBORATED" if ok else
                       "PARSE NOT CORROBORATED; stop here"))
    if not ok:
        # "stop here" must actually stop: nothing below may be believed if the
        # parse control disagreed, and the exit code must reflect it.
        return 1
    P = r["P"]
    print()
    print("ANTERIOR DEPTH MAP  max Z per (|X|, Y) cell, L/R pooled")
    cols = np.arange(0.0, 9.0, 1.0)
    AX = np.abs(P[:, 0])
    print("      Y  |" + "".join("  x%4.1f" % c for c in cols))
    for y0 in np.arange(153, 169, 1.0):
        row = []
        for x0 in cols:
            m = ((P[:, 1] >= y0) & (P[:, 1] < y0 + 1) & (AX >= x0)
                 & (AX < x0 + 1))
            row.append(P[m, 2].max() if m.sum() >= 3 else float("nan"))
        print("   %5.1f  |" % y0
              + "".join(" %6.2f" % v if np.isfinite(v) else "    ---"
                        for v in row))
    print()
    print("ANTERIOR HALF-WIDTH (D=8 cm), cm")
    for y0 in np.arange(153, 169, 1.0):
        print("   Y %5.1f   %7.4f" % (y0, half_width(P, y0, y0 + 1)))
    zyg, buc, jaw = taper(P)
    print()
    print("  zygomatic %.4f   buccal %.4f   jaw@Y158 %.4f" % (zyg, buc, jaw))
    print("  buccal/zygomatic %.4f   jaw/zygomatic %.4f"
          % (buc / zyg, jaw / zyg))
    print("  SHAPE reference hero_face_bald_frontal.jpg, mediapipe 172/397 "
          "over 234/454: %.4f" % ref_jaw_cheek_ratio())
    return 0


def cmd_simulate(path):
    r = read_head(path)
    print("base       %s" % os.path.relpath(path, REPO_ROOT))
    print("  sha256 %s" % r["sha"])
    if not check_parse(r, quiet=True):
        raise SystemExit("parse control failed; refusing to simulate")
    P0 = r["P"]
    print()
    P = apply_edits(P0)
    D = P - P0
    n = np.linalg.norm(D, axis=1)
    print()
    print("net over all %d: moved %d, untouched %d, max %.4f cm"
          % (len(EDITS), int((n > 1e-6).sum()), int((n <= 1e-6).sum()),
             n.max()))
    print()
    AX0 = np.abs(P0[:, 0])
    dmed = -np.sign(P0[:, 0]) * D[:, 0]
    Y0 = P0[:, 1]
    print("DISPLACEMENT BY BAND (bands defined on the BASE positions)")
    print("  band                        n  mean|d|  max|d|  mean medial"
          "  mean dZ")
    for nm, m in [
        ("chin        Y152-156 |X|<4", (Y0 >= 152) & (Y0 < 156) & (AX0 < 4)),
        ("jowl/jaw    Y154-158 |X|4-8", (Y0 >= 154) & (Y0 < 158)
         & (AX0 >= 4) & (AX0 < 8)),
        ("buccal      Y158-163 |X|4-8", (Y0 >= 158) & (Y0 < 163)
         & (AX0 >= 4) & (AX0 < 8)),
        ("zygomatic   Y163-167 |X|5-8", (Y0 >= 163) & (Y0 < 167)
         & (AX0 >= 5) & (AX0 < 8)),
        ("nose+lips   Y156-166 |X|<3", (Y0 >= 156) & (Y0 < 166) & (AX0 < 3)),
        ("periorbital Y164-170 |X|<6", (Y0 >= 164) & (Y0 < 170) & (AX0 < 6)),
        ("EAR ctrl    |X|>8 Y161-172", (AX0 > 8.0) & (Y0 >= 161) & (Y0 < 172)),
        ("forehead ctrl Y169+", Y0 >= 169),
        ("neck ctrl   Y<152", Y0 < 152),
    ]:
        print("  %-26s %5d  %7.4f %7.4f    %+8.4f %+8.4f"
              % (nm, int(m.sum()), n[m].mean(), n[m].max(), dmed[m].mean(),
                 D[m, 2].mean()))
    print()
    print("ANTERIOR HALF-WIDTH (D=8), cm    base -> predicted PRE-IMPORT")
    for y0 in np.arange(153, 169, 1.0):
        a = half_width(P0, y0, y0 + 1)
        b = half_width(P, y0, y0 + 1)
        print("   Y %5.1f   %7.4f -> %7.4f   %+7.4f" % (y0, a, b, b - a))
    print()
    for tag, Q in (("base     ", P0), ("predicted", P)):
        zyg, buc, jaw = taper(Q)
        print("  %s  zyg %.4f  buccal %.4f  jaw %.4f  buccal/zyg %.4f  "
              "jaw/zyg %.4f" % (tag, zyg, buc, jaw, buc / zyg, jaw / zyg))
    print("  reference hero_face_bald_frontal.jpg: jaw/cheek %.4f"
          % ref_jaw_cheek_ratio())
    print()
    rb, rowsb, chin, vchin, img = taper_curve_residual(P0)
    re_, rowse, _, _, _ = taper_curve_residual(P)
    print("NORMALISED TAPER CURVE vs %s" % img)
    # The chin's normalised v is the REFERENCE value (ref_curve's v[152]),
    # read back and printed -- not a hardcoded 1.9318 behind an `if False`.
    print("  vertical 0 at the iris line, %.4f at the chin; mesh chin Y %.2f"
          % (vchin, chin))
    print("  lateral = half-width / that side's OWN zygomatic half-width")
    print("      v     Y     REFERENCE   MESH base  MESH pred   base-ref"
          "   pred-ref")
    # Align base and predicted rows by Y0, not by a positional zip: the two
    # come from independently filtered passes and can differ in membership, so
    # zip would silently truncate/mis-pair.
    pred_by_y0 = {row[3]: row for row in rowse}
    paired = [(b, pred_by_y0[b[3]]) for b in rowsb if b[3] in pred_by_y0]
    print("  (%d of %d base bands paired with a predicted band by Y)"
          % (len(paired), len(rowsb)))
    for (v, r, mb, y0), (_, _, me, _) in paired:
        print("   %+6.3f %5.1f     %7.4f     %7.4f    %7.4f   %+7.4f  %+7.4f"
              % (v, y0, r, mb, me, mb - r, me - r))
    print("  MEAN ABSOLUTE RESIDUAL   base %.4f   predicted %.4f   %+.4f"
          % (rb, re_, re_ - rb))
    return 0


def cmd_verify(edited, base):
    """Cross-instrument check of a DNA the EDITOR wrote.

    The plugin self-verifies every weighted vertex and at most 512
    zero-weight ones (LandscapeLabTools.cpp:1436-1480). This checks ALL
    24,049 against an independently computed prediction, from a parser that
    shares no code with DNACalib.
    """
    rb, re_ = read_head(base), read_head(edited)
    print("base   %s" % os.path.relpath(base, REPO_ROOT))
    print("  sha256 %s" % rb["sha"])
    print("edited %s" % os.path.relpath(edited, REPO_ROOT))
    print("  sha256 %s" % re_["sha"])
    if not check_parse(rb, quiet=True):
        raise SystemExit("parse control failed on the base")
    # Corroborate the EDITED file's parse too, not only the base: read_head
    # already enforces the vertex count, but a gross X/Y/Z layout error would
    # otherwise flow into the diff unremarked.
    if not check_parse(re_, quiet=True):
        raise SystemExit("parse control failed on the edited file")
    want = apply_edits(rb["P"], report=False)
    got = re_["P"]
    d = np.abs(got - want).max(axis=1)
    W = np.zeros(rb["P"].shape[0])
    P = rb["P"].copy()
    for _n, bmin, bmax, band, delta in EDITS:
        w, _ = _weights(P, bmin, bmax, band)
        W = np.maximum(W, w)
        P = P + w[:, None] * np.asarray(delta, float)
    weighted = W > 0.0
    if not weighted.any():
        raise SystemExit("no vertices were weighted by any edit box -- the "
                         "boxes selected nothing; refusing rather than reducing "
                         "an empty array")
    print()
    print("  weighted vertices  %6d   max |predicted - file|  %.6f cm"
          % (int(weighted.sum()), d[weighted].max()))
    print("  zero-weight        %6d   max |predicted - file|  %.6f cm"
          % (int((~weighted).sum()), d[~weighted].max()))
    print("  ALL %d checked, not a 512 sample" % d.size)
    # float32 storage; 1e-3 is the plugin's own tolerance at :1435
    ok = d.max() <= 1e-3
    print()
    print("  VERDICT %s (tolerance 1e-3 cm, the plugin's own at "
          "LandscapeLabTools.cpp:1435)" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 4


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baseline", metavar="DNA")
    g.add_argument("--simulate", metavar="DNA")
    g.add_argument("--verify", metavar="EDITED_DNA")
    ap.add_argument("--against", metavar="BASE_DNA",
                    help="required with --verify")
    a = ap.parse_args(argv)
    if a.baseline:
        return cmd_baseline(a.baseline)
    if a.simulate:
        return cmd_simulate(a.simulate)
    if not a.against:
        raise SystemExit("--verify needs --against <base dna>")
    return cmd_verify(a.verify, a.against)


if __name__ == "__main__":
    sys.exit(main())
