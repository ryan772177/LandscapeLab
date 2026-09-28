"""front_metrics.py -- ONE measurement of a front-view clay bust, used for BOTH
the target and our own renders.

    python front_metrics.py <image> [<out.json>] [--dump-mask <png>]

WHY ONE FUNCTION AND NOT TWO. The clay reference and preview_hair.py's output
are the same KIND of picture: a grey bust on a neutral backdrop, measured
background luma 59.0 in both. The moment the target and the candidate are
measured by different code, any difference between them is partly a difference
between the two measurements -- and this project has already had a rear rubric
produce two confident, meaningless numbers because check and checked shared the
wrong source. Non-negotiable 19: when two passes render the same physical fact,
the fact is defined ONCE and both read it.

IT IS A DIFFERENT HEAD, so nothing overlays. Every number is normalised by the
subject's own face height (skull-top-to-chin) or face width, both of which are
measurable on any bust, so a target measured on the clay sculpt transfers to the
hero without assuming the two skulls match.

DEFINITIONS, all measured rather than chosen:
  face_top   topmost CLAY row -- the forehead where it emerges from the hair.
             Not the skull top, which the hair hides on both subjects. Used
             identically on both, so the comparison is like-for-like.
  chin       the narrowest clay row between the face and the shoulders.
  face_h     chin - face_top. The normalising unit for every vertical measure.
  face_w     widest clay row above the chin. The unit for horizontal measures.

THE MASK IS DUMPED AND MUST BE LOOKED AT before any number is believed.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

BORDER = 6          # JPEG edge columns read as "hair"; excluded on both


def measure(path, dump=None):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    # The clay reference carries a title strip; a render does not. Detect it
    # rather than hardcoding: a strip of near-black rows at the very top.
    # THE TITLE BAR IS A FULL-WIDTH DARK BAND, and it must go before anything
    # else: it reads as 1030 px of "hair" on every one of its rows, which puts
    # the top of the hair silhouette at row 0 and makes crown lift meaningless.
    # Detecting it by mean luma alone failed -- the bar carries bright text, so
    # its mean clears any threshold. Detect it by what it IS: a row that is
    # almost entirely dark across the full width. The bar carries bright text so
    # the bar itself measures 0.88 dark, not 1.00 -- a 0.90 cut missed it by two
    # hundredths and left the title band in as hair. Real hair at the top of the
    # silhouette covers 0.13 of a row, so 0.70 separates them with room to spare.
    L0 = a.mean(axis=2)
    bg0 = float(np.median(L0))
    top_cut = 0
    for r in range(min(80, L0.shape[0])):
        if float((L0[r] < bg0 - 16.0).mean()) > 0.70:
            top_cut = r + 1
        else:
            break
    a = a[top_cut:, :, :]
    L = a.mean(axis=2)
    h, w = L.shape
    # THE BORDER IS MEASURED, NOT ASSUMED.
    # A hardcoded BORDER = 6 left FIVE dark columns of the clay reference's
    # 11-px frame inside the image, and they classify as HAIR ON EVERY ROW.
    # That contaminated ONLY THE TARGET -- our PNGs have no border and measure
    # identically at 6, 14 or 20 -- so every axis was being scored against an
    # inflated clay. Its `width_profile` was a constant 3.6453, i.e. the
    # "silhouette edge" was column 1029 of a 1030-px frame, and I never opened
    # that array. Found by the sides agent.
    bg_probe = float(np.median(L))
    dark_col = (L < bg_probe - 16.0).mean(axis=0) > 0.95
    dark_row = (L < bg_probe - 16.0).mean(axis=1) > 0.95
    lb = 0
    while lb < w // 4 and dark_col[lb]:
        lb += 1
    rb = 0
    while rb < w // 4 and dark_col[w - 1 - rb]:
        rb += 1
    bb = 0
    while bb < h // 4 and dark_row[h - 1 - bb]:
        bb += 1
    pad = 2                       # a little slack for the border's soft edge
    lb, rb = lb + pad if lb else BORDER, rb + pad if rb else BORDER
    L = L[:h - bb, lb:w - rb]
    h, w = L.shape
    bg = float(np.median(L))

    clay = L > bg + 16.0
    hair = L < bg - 16.0

    rep = {"image": path, "frame_px": [int(w), int(h)],
           "title_strip_px": int(top_cut), "background_luma": round(bg, 2),
           "mask_frac": {"clay": round(float(clay.mean()), 4),
                         "hair": round(float(hair.mean()), 4)}}

    widths = clay.sum(axis=1).astype(np.float64)
    rows = np.nonzero(widths > 4)[0]
    if rows.size < 20:
        rep["error"] = "REFUSE: no bust found (clay mask nearly empty)"
        return rep
    r_top, r_bot = int(rows.min()), int(rows.max())

    # THE CHIN is the narrowest clay row between the face and the shoulders.
    # Searched in the MIDDLE of the bust: an earlier version searched the upper
    # 62% and found a 3-pixel sliver of forehead showing between locks of hair,
    # returning a head 3 px tall. The search window is the fix.
    span = r_bot - r_top
    lo = r_top + int(0.40 * span)
    hi = r_top + int(0.85 * span)
    seg = widths[lo:hi].copy()
    seg[seg < 6] = np.inf
    chin = lo + int(np.argmin(seg))

    face = clay.copy()
    face[chin:, :] = False
    per_row_w0 = face.sum(axis=1)
    # FACE_TOP NEEDS A FLOOR. Specular highlights on dark hair clear the clay
    # threshold a few pixels at a time -- measured, 1 to 8 px per row from row
    # 70 down on the clay reference -- and a bare `.min()` of the nonzero rows
    # put the forehead 160 px above where it is, giving a 633 px "face" on a
    # 296 px-wide head. The forehead is a wide band, so require real width.
    floor = max(12, int(0.08 * per_row_w0.max()))
    # AND IT MUST BE CENTRED. Width alone is not enough: on a tall wispy crown,
    # RIM-LIT HAIR clears the clay threshold in a broad off-centre band and gets
    # taken for forehead. Found by the crown agent on crown_04 -- the offending
    # pixels sat at x 279-352 against a face centre of 433, which put face_top
    # at 125 instead of 189, inflated face_h 343 -> 407 and reported
    # crown_lift_frac 0.3071 for an iteration whose crown had actually RISEN
    # (height_gain_cm 5.11 -> 5.94). The instrument read a success as a
    # collapse, which is the worst direction for this fault.
    #
    # A forehead spans the midline; a rim-lit lock does not. So the row must
    # also carry clay ON the bust's centre column. The centre is taken from the
    # widest clay row in the whole image -- the shoulders -- which is available
    # before any face measurement and cannot be contaminated by hair.
    all_rows = clay.sum(axis=1)
    wr0 = int(np.argmax(all_rows))
    cc = np.nonzero(clay[wr0])[0]
    cx0 = int(0.5 * (cc.min() + cc.max())) if cc.size else w // 2
    band = slice(max(0, cx0 - 8), min(w, cx0 + 9))
    centred = clay[:, band].any(axis=1)
    solid = np.nonzero((per_row_w0 >= floor) & centred[:len(per_row_w0)])[0]
    if solid.size == 0:
        rep["error"] = ("REFUSE: no forehead band of width >= %d px that also "
                        "crosses the bust centre column" % floor)
        return rep
    rep["_bust_centre_x_px"] = cx0
    face_top = int(solid.min())
    face[:face_top, :] = False
    rep["_face_top_floor_px"] = floor
    face_h = chin - face_top
    per_row_w = face.sum(axis=1)
    face_w = int(per_row_w.max())
    wr = int(np.argmax(per_row_w))
    cols = np.nonzero(face[wr])[0]
    cx = 0.5 * float(cols.min() + cols.max())

    rep["face"] = {"top_row": face_top, "chin_row": int(chin),
                   "height_px": int(face_h), "width_px": face_w,
                   "centre_x_px": round(cx, 1), "neck_width_px": int(widths[chin])}
    if face_h < 40:
        rep["error"] = "REFUSE: face height %d px is implausible" % face_h
        return rep

    subj = clay | hair

    # --- crown lift: hair above the forehead, over face height -------------
    hys = np.nonzero(hair.any(axis=1))[0]
    hair_top = int(hys.min()) if hys.size else face_top
    rep["crown_lift_frac"] = round((face_top - hair_top) / face_h, 4)

    # --- fringe descent: how far hair reaches down the face ----------------
    desc = {}
    for label, f in (("midline", 0.0), ("quarter_L", -0.22),
                     ("quarter_R", 0.22), ("temple_L", -0.40),
                     ("temple_R", 0.40)):
        c = int(round(cx + f * face_w))
        strip = hair[:, max(0, c - 5):c + 6]
        rr = np.nonzero(strip.any(axis=1))[0]
        desc[label] = None if rr.size == 0 else round(
            (int(rr.max()) - face_top) / face_h, 4)
    rep["fringe_descent_frac_of_face_h"] = desc

    # --- coverage in horizontal bands, as fractions of face height ---------
    def cover(f0, f1):
        r0 = face_top + int(f0 * face_h)
        r1 = face_top + int(f1 * face_h)
        r0, r1 = max(0, min(r0, r1)), min(h - 1, max(r0, r1))
        if r1 <= r0:
            return None
        sh, ss = hair[r0:r1 + 1], subj[r0:r1 + 1]
        wid = ss.sum(axis=1).astype(np.float64)
        cov = sh.sum(axis=1).astype(np.float64)
        ok = wid > 4
        if not ok.any():
            return None
        return round(float((cov[ok] / wid[ok]).mean()), 4)

    # CENTRAL COVERAGE -- THE FRINGE, ISOLATED FROM THE CURTAINS.
    # `cover` above spans the FULL width of the silhouette at each band, and at
    # forehead height most of that width is side hair. A groom with a bare
    # forehead and heavy sides scores nearly the same as one with a fringe,
    # which is non-negotiable 22 exactly: a number that is arithmetically true
    # and answers a question nobody asked. This restricts the denominator to
    # the middle half of the FACE, where only a fringe can put hair.
    def cover_central(f0, f1, frac=0.5):
        r0 = face_top + int(f0 * face_h)
        r1 = face_top + int(f1 * face_h)
        r0, r1 = max(0, min(r0, r1)), min(h - 1, max(r0, r1))
        c0 = int(cx - frac * 0.5 * face_w)
        c1 = int(cx + frac * 0.5 * face_w)
        c0, c1 = max(0, c0), min(w - 1, c1)
        if r1 <= r0 or c1 <= c0:
            return None
        return round(float(hair[r0:r1 + 1, c0:c1 + 1].mean()), 4)

    rep["central_cover"] = {
        "_denominator": ("the middle 50% of face width -- only a fringe can "
                         "put hair here, so this is the fringe axis and "
                         "band_cover is the silhouette-width axis"),
        "forehead_0.00_0.15": cover_central(0.00, 0.15),
        "brow_0.15_0.28": cover_central(0.15, 0.28),
        "eye_0.28_0.42": cover_central(0.28, 0.42),
    }

    rep["band_cover"] = {
        "forehead_0.00_0.15": cover(0.00, 0.15),
        "brow_0.15_0.28": cover(0.15, 0.28),
        "eye_0.28_0.42": cover(0.28, 0.42),
        "ear_0.30_0.62": cover(0.30, 0.62),
        "jaw_0.70_0.95": cover(0.70, 0.95),
        "_note": ("LEGACY, face_top-relative. Kept for continuity with earlier "
                  "runs and SUPERSEDED by anat_cover below -- face_top moves "
                  "with the hair, so these bands slide."),
    }

    # ---- ANATOMICAL BANDS: the datum must not move with the hair ----------
    # THE DEFECT THESE REPLACE. Everything above is measured from `face_top`,
    # the topmost centred clay row -- which is the FOREHEAD, and a fringe covers
    # the forehead. So the datum rides DOWN as the fringe succeeds: face_h
    # shrinks, every fraction inflates, and a composed candidate with a real
    # fringe scored central-brow 0.8308 against a 0.0055 target. That is
    # non-negotiable 5 -- a check that consumes the value it is verifying
    # verifies nothing -- and the fringe agent flagged it from the other side
    # ("face_top rides down with the fringe") before it broke anything.
    #
    # THE TWO ANCHORS ARE HAIR-INDEPENDENT ON BOTH SUBJECTS:
    #   chin_row  the narrowest clay row between face and shoulders. No groom
    #             here covers the chin or the neck.
    #   face_w    the widest clay row. Measured on SKIN, so hair cannot widen
    #             it, and it narrows only if hair covers the cheeks -- which it
    #             does on neither the clay nor any candidate so far. Reported,
    #             so a shift is visible rather than silent.
    #
    # u = (chin_row - row) / face_w, i.e. heights in FACE WIDTHS above the chin.
    # Band edges are the HERO'S OWN MEASURED ANATOMY, converted once:
    # survey_head.json gives brow 167.24, eye socket 165.46, crown 178.44, and
    # the ear span 162.72-167.60; his render chin sits at 155.15 cm with a face
    # width of 16.60 cm, so brow = (167.24-155.15)/16.60 = 0.728, and so on.
    # Both subjects are human heads normalised by their own face width, which is
    # what makes one set of edges apply to both.
    # THE HORIZONTAL UNIT IS THE SHOULDERS, NOT THE FACE.
    # face_w looked hair-independent and is not: it is the widest SKIN row, and
    # hair covering the cheeks narrows it. Measured across candidates it swings
    # 235-255 px -- an 8% wobble in the denominator of every band, and it moves
    # in the same direction as the styling being scored. The shoulders are wide,
    # far from any groom, and present on both subjects.
    sh_lo = chin + int(0.35 * (r_bot - chin))
    sh_rows = clay[sh_lo:r_bot + 1].sum(axis=1)
    shoulder_w = int(sh_rows.max()) if sh_rows.size else face_w
    if shoulder_w < face_w:
        shoulder_w = face_w
    unit = float(shoulder_w)

    # Band edges in u = (chin_row - row) / shoulder_w, derived ONCE from the
    # hero's own measured anatomy through preview_hair.py's fixed rig:
    # 18.195 rows/cm with row 0 at z 184.39 cm (recovered from the tool's own
    # reported eye band and confirmed by BROW_CHECK.png landing on his
    # eyebrows). survey_head.json gives brow 167.24, socket 165.46, crown
    # 178.44, ear span 162.72-167.60; his chin row is 532 and his shoulder
    # width 720 px, so u(brow) = (532 - (184.39-167.24)*18.195) / 720 = 0.306.
    ANAT = {
        "jaw":      (0.03, 0.14),
        "ear":      (0.14, 0.31),
        "eye":      (0.21, 0.29),
        "brow":     (0.29, 0.35),
        "forehead": (0.35, 0.47),
        "crown":    (0.47, 0.70),
    }

    def u_to_row(u):
        return int(round(chin - u * unit))

    def anat(u0, u1, frac=None):
        r0, r1 = u_to_row(u1), u_to_row(u0)          # u1 is higher on the head
        r0, r1 = max(0, min(r0, r1)), min(h - 1, max(r0, r1))
        if r1 <= r0:
            return None
        if frac is None:
            sh, ss = hair[r0:r1 + 1], subj[r0:r1 + 1]
            wid = ss.sum(axis=1).astype(np.float64)
            cov = sh.sum(axis=1).astype(np.float64)
            ok = wid > 4
            return None if not ok.any() else round(
                float((cov[ok] / wid[ok]).mean()), 4)
        # THE CENTRAL WINDOW IS HAIR-INDEPENDENT TOO.
        # This used cx and face_w, and BOTH move with the hair: face_w is the
        # widest SKIN row, so hair over the cheek narrows it, and cx follows.
        # The round-2 fringe agent measured one of its own cycles moving face_w
        # 234 -> 281 and cx by 34 px on a SINGLE knob -- which silently widens
        # the "central" window and pulls side-curtain hair into the fringe's own
        # denominator. Rows were re-anchored on the chin and shoulders after the
        # face_top failure; the columns were left half-fixed, and this closes it.
        #
        # cx0 is the bust centre from the widest clay row -- the shoulders --
        # and the half-width is a fraction of SHOULDER width chosen to equal the
        # old "half the face" on the bare head: 0.5 * 302 / 689 = 0.219.
        half = frac * 0.219 * unit
        c0 = max(0, int(cx0 - half))
        c1 = min(w - 1, int(cx0 + half))
        return None if c1 <= c0 else round(
            float(hair[r0:r1 + 1, c0:c1 + 1].mean()), 4)

    rep["anat_cover"] = {k: anat(*v) for k, v in ANAT.items()}
    rep["anat_central"] = {k: anat(*ANAT[k], frac=0.5)
                           for k in ("eye", "brow", "forehead", "crown")}
    rep["anat_anchors"] = {
        "chin_row": int(chin), "face_w_px": face_w, "shoulder_w_px": shoulder_w,
        "_u": "u = (chin_row - row) / shoulder_w",
        "_edges": {k: list(v) for k, v in ANAT.items()},
    }
    # Crown height above the SKULL TOP, anchored the same way -- this replaces
    # crown_lift_frac, whose reference was also face_top.
    rep["anat_crown_height_u"] = round((chin - hair_top) / unit, 4)

    # --- width profile: total silhouette half-width over face half-width ---
    prof = []
    for i in range(16):
        r0 = face_top + int(i / 16.0 * face_h * 1.25)
        r1 = face_top + int((i + 1) / 16.0 * face_h * 1.25)
        strip = subj[r0:max(r1, r0 + 1)]
        cc = np.nonzero(strip.any(axis=0))[0]
        prof.append(None if cc.size == 0 else
                    round(float(max(cc.max() - cx, cx - cc.min()))
                          / (0.5 * face_w), 4))
    rep["width_profile"] = prof

    # --- edge roughness: perimeter / sqrt(area), dimensionless -------------
    pad = np.zeros((h + 2, w + 2), dtype=bool)
    pad[1:-1, 1:-1] = hair
    nb = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    area = int(hair.sum())
    rep["edge_roughness"] = round(int((hair & ~nb).sum())
                                  / max(np.sqrt(area), 1e-9), 4)
    rep["hair_area_over_face_area"] = round(area / max(int(face.sum()), 1), 4)

    if dump:
        vis = np.zeros((h, w, 3), dtype=np.uint8)
        vis[..., 0] = np.where(hair, 235, 25)
        vis[..., 1] = np.where(face, 200, 25)
        vis[..., 2] = np.where(clay & ~face, 150, 25)
        vis[face_top, :, :] = 255
        vis[chin, :, :] = 255
        os.makedirs(os.path.dirname(os.path.abspath(dump)) or ".",
                    exist_ok=True)
        Image.fromarray(vis).save(dump)
        rep["mask_dump"] = dump
    return rep


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    dump = None
    if "--dump-mask" in sys.argv:
        dump = sys.argv[sys.argv.index("--dump-mask") + 1]
        args = [x for x in args if x != dump]
    r = measure(args[0], dump)
    if len(args) > 1:
        os.makedirs(os.path.dirname(os.path.abspath(args[1])) or ".",
                    exist_ok=True)
        json.dump(r, open(args[1], "w", encoding="utf-8"), indent=2)
    print(json.dumps(r, indent=2))
