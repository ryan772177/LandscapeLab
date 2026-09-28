"""survey_clay.py -- THE SURVEYOR, target half. Measures the clay reference.

    python hero/groomloop/scripts/survey_clay.py <out.json> [--dump-mask]

WHY THE CLAY IS THE SILHOUETTE TARGET AND THE PORTRAITS ARE NOT. Both photo
references are graded portraits: their hair edge is a lighting decision as much
as a geometry one, and every shape ruling taken against them was taken by eye.
The clay is the target IN THE WORKING MEDIUM -- grey clay, neutral light, the
same bust presentation preview_hair.py already renders -- so a silhouette
comparison against it carries no lighting or grade noise.

IT IS A DIFFERENT HEAD. The clay bust is not the hero, so nothing here overlays
pixels. Every number is normalised by the head's own measured width or height,
which is what makes it transferable to a different skull.

WHAT IT PUBLISHES, and each one answers a brief the styling agents are given:
  crown_lift_frac    silhouette height above the skull top, over head height
                     -> the crown agent's target
  fringe_descent     how far hair reaches DOWN the face from the skull top,
                     over head height, at the midline and at 1/4 offsets
                     -> the fringe agent's target
  brow_band_cover    fraction of the brow band's width carrying hair
                     -> the fringe agent's occlusion-by-design target
  ear_band_cover     fraction of the ear band's width carrying hair
                     -> the sides agent's target
  width_profile      hair half-width per height, over head half-width
                     -> the sides agent's length band, and the overall shape
  edge_roughness     perimeter / sqrt(area), dimensionless
                     -> the chunk/separation axis, comparable to the rear
                        reference's already-measured 27.9648

THE MASK IS DUMPED AND LOOKED AT BEFORE ANY NUMBER IS USED. This project has
already had a rear rubric return two confident, meaningless numbers twice --
once measuring forest, once measuring a hollow ring -- both times passing a
mask_frac band, because a gate on the EXTENT of a region cannot see whether it
is the RIGHT region.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

REF = "hero/reference/appearance_groom_clay.jpg"
TITLE_STRIP_PX = 32          # the source carries a title bar; never edited


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "survey_clay.json"
    dump = "--dump-mask" in sys.argv

    im = Image.open(REF).convert("RGB")
    a = np.asarray(im).astype(np.float32)[TITLE_STRIP_PX:, :, :]
    L = a.mean(axis=2)
    h, w = L.shape
    bg = float(np.median(L))

    # CLAY (bright, neutral) vs HAIR (dark) vs BACKDROP (mid grey).
    # The backdrop is the median; clay is well above it and hair well below.
    clay = L > bg + 16.0
    hair = L < bg - 16.0

    # the bust: largest bright component, by column/row extent
    ys, xs = np.nonzero(clay)
    bust = {"x": [int(xs.min()), int(xs.max())],
            "y": [int(ys.min()), int(ys.max())]}

    # HEAD, not bust: the shoulders are wide and low. Take the narrowest row
    # in the upper 60% -- the neck -- and call everything above it the head.
    widths = np.array([clay[r].sum() for r in range(h)], dtype=np.float64)
    top = int(ys.min())
    lim = top + int(0.62 * (ys.max() - top))
    seg = widths[top:lim].copy()
    seg[seg < 6] = np.inf
    neck_r = top + int(np.argmin(seg))
    head = clay.copy()
    head[neck_r:, :] = False
    hys, hxs = np.nonzero(head)
    head_top, head_bot = int(hys.min()), int(hys.max())
    head_h = head_bot - head_top
    head_w = int(hxs.max() - hxs.min())
    head_cx = 0.5 * (float(hxs.max()) + float(hxs.min()))

    hair_ys, hair_xs = np.nonzero(hair)
    hair_top = int(hair_ys.min())

    rep = {
        "producer": "survey_clay.py",
        "reference": REF,
        "sha256": "d331043ecd6629a40f33744419b140f96b374fc2b698056e6e82e72ca8cc17ac",
        "frame_px": [int(w), int(h)],
        "background_luma": round(bg, 2),
        "bust_bbox_px": bust,
        "head": {"top_row": head_top, "neck_row": neck_r,
                 "bottom_row": head_bot, "height_px": int(head_h),
                 "width_px": head_w, "centre_x_px": round(head_cx, 1)},
        "mask_frac": {"clay": round(float(clay.mean()), 4),
                      "hair": round(float(hair.mean()), 4)},
    }

    # --- crown lift -------------------------------------------------------
    # How far the hair silhouette rises ABOVE the top of the skull. On a clay
    # bust the skull top is hidden under the hair, so it is taken as the
    # highest CLAY row -- which on this image is the forehead -- and the lift
    # is measured from there. Reported as a fraction of head height so it
    # transfers to a different skull.
    rep["crown_lift_px"] = int(head_top - hair_top)
    rep["crown_lift_frac"] = round((head_top - hair_top) / max(head_h, 1), 4)

    # --- fringe descent ---------------------------------------------------
    # THE DEFINING FEATURE OF THIS TARGET. For a set of columns across the
    # face, how far down does hair reach, measured from the head top and
    # normalised by head height.
    desc = {}
    for label, frac in (("midline", 0.0), ("quarter_L", -0.25),
                        ("quarter_R", 0.25), ("half_L", -0.42),
                        ("half_R", 0.42)):
        cx = int(round(head_cx + frac * head_w))
        band = hair[:, max(0, cx - 6):cx + 7]
        rows = np.nonzero(band.any(axis=1))[0]
        if rows.size == 0:
            desc[label] = None
            continue
        desc[label] = {
            "lowest_row": int(rows.max()),
            "descent_from_head_top_frac": round(
                (int(rows.max()) - head_top) / max(head_h, 1), 4)}
    rep["fringe_descent"] = desc

    # --- brow band coverage ----------------------------------------------
    # The brief's occlusion-by-design axis. The brow on a clay bust is not
    # directly measurable, so the band is taken at the proportion the hero's
    # own MEASURED skull gives: brow sits at
    #   (crown_up - brow_up) / (crown_up - neck_cut_up)
    # below the skull top. Read from survey_head.json so the two halves of the
    # surveyor cannot disagree.
    hh = json.load(open("hero/groomloop/survey/survey_head.json"))
    sb = hh["skull_bands"]
    span = sb["crown_up"] - sb["neck_cut_up"]
    brow_frac = (sb["crown_up"] - sb["brow_up"]) / span
    eye_frac = (sb["crown_up"] - sb["eye_socket_up"]) / span
    ear_lo = (sb["crown_up"] - hh["ears"]["L"]["up_span"][0]) / span
    ear_hi = (sb["crown_up"] - hh["ears"]["L"]["up_span"][1]) / span
    rep["_bands_from_head_survey"] = {
        "brow_frac_below_crown": round(brow_frac, 4),
        "eye_frac_below_crown": round(eye_frac, 4),
        "ear_band_frac_below_crown": [round(ear_hi, 4), round(ear_lo, 4)],
        "_note": "fractions of (crown_up - neck_cut_up) from survey_head.json",
    }

    def band_cover(f_lo, f_hi):
        r0 = head_top + int(f_lo * head_h)
        r1 = head_top + int(f_hi * head_h)
        r0, r1 = max(0, min(r0, r1)), min(h - 1, max(r0, r1))
        if r1 <= r0:
            return None
        strip_hair = hair[r0:r1 + 1]
        strip_head = head[r0:r1 + 1] | strip_hair
        wid = strip_head.sum(axis=1).astype(np.float64)
        cov = strip_hair.sum(axis=1).astype(np.float64)
        ok = wid > 4
        return {"rows": [r0, r1],
                "cover_frac": round(float((cov[ok] / wid[ok]).mean()), 4)}

    rep["brow_band_cover"] = band_cover(brow_frac - 0.03, brow_frac + 0.03)
    rep["ear_band_cover"] = band_cover(ear_hi, ear_lo)
    rep["eye_band_cover"] = band_cover(eye_frac - 0.03, eye_frac + 0.03)

    # --- width profile ----------------------------------------------------
    prof = []
    for i in range(20):
        f0, f1 = i / 20.0, (i + 1) / 20.0
        r0 = head_top + int(f0 * head_h)
        r1 = head_top + int(f1 * head_h)
        strip = (hair | head)[r0:max(r1, r0 + 1)]
        cols = np.nonzero(strip.any(axis=0))[0]
        prof.append(None if cols.size == 0 else
                    round(float(max(cols.max() - head_cx,
                                    head_cx - cols.min()))
                          / (0.5 * head_w), 4))
    rep["width_profile_half_over_head_half"] = prof

    # --- edge roughness ---------------------------------------------------
    # perimeter / sqrt(area), dimensionless so it survives a resolution
    # change. Directly comparable to the rear reference's 27.9648.
    pad = np.zeros((h + 2, w + 2), dtype=bool)
    pad[1:-1, 1:-1] = hair
    nb = (pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    perim = int((hair & ~nb).sum())
    area = int(hair.sum())
    rep["edge_roughness"] = round(perim / max(np.sqrt(area), 1e-9), 4)
    rep["hair_area_px"] = area

    if dump:
        vis = np.zeros((h, w, 3), dtype=np.uint8)
        vis[..., 0] = np.where(hair, 235, 25)
        vis[..., 1] = np.where(head, 235, 25)
        vis[..., 2] = np.where(clay & ~head, 160, 25)
        p = "_verify/20260822_hero_authored/CLAY_MASK.png"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        Image.fromarray(vis).save(p)
        rep["mask_dump"] = p

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
    print(json.dumps({k: rep[k] for k in
                      ("head", "crown_lift_frac", "fringe_descent",
                       "brow_band_cover", "eye_band_cover", "ear_band_cover",
                       "edge_roughness", "mask_frac")}, indent=2))


if __name__ == "__main__":
    main()
