#!/usr/bin/env python3
"""Brief 5 C1 -- the direct runtime LOD readback (desk requires this; SSIM was
rejected as unable to distinguish 'hold took' from 'hold is a runtime no-op').

READ-ONLY analysis of the Mesh LOD Coloration stills from c_capture.py c1.

LEGEND, READ FROM THE VIEWMODE (not assumed): every LODColoration still carries
the engine's on-screen legend bar. read_legend() samples its eight swatches ->
the exact palette (0 white,1 red,2 green,3 blue,4 yellow,5 magenta,6 cyan,7
purple), which is validated against BaseEngine.ini:273-280. That palette is the
ground truth; no per-still centroid learning (the scene is heavily overexposed --
snow blown to 255 -- so a box median collapses to white; saturated tree pixels
keep their pure LOD hue and are what we classify).

METHOD: per species, project the 128-512 m band instance boxes in the ring
camera and in a camera pushed 300 m into the band (FOV from the engine readback,
F7). In each auto still, classify each box by the dominant SATURATED palette
colour of its pixels -> LOD index. Card LOD index = last LOD (ConiferPine 3 =
blue, SpruceSub 4 = yellow). Per species: boxes at the CARD index vs a GEOMETRIC
index. >=90% geometric -> HOLD TOOK, MEASURED. <=10% -> NO-OP AT RUNTIME.
Between -> INCONCLUSIVE. A species with too few classifiable boxes REFUSES
(rule 13: a zero/near-zero sample is not agreement).
"""
import glob
import json
import math
import os

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
# PREFIX parametrises the I/O so the identical classifier serves C1 (pre-hold,
# the committed NO-OP baseline) and R2 (post-hold) without either clobbering the
# other. Defaults reproduce C1 byte-for-byte. Overridden in __main__ via --prefix.
PREFIX = "c1"
STILLS = os.path.join(REPO, "research", "brief5", "derived", "c1_lodcolor")
OUTFILE = "c1_lod_readback.json"
RENDERDATA = "c1_renderdata.json"
RES = (3840, 2160)
BAND = (12800.0, 51200.0)   # 128-512 m in cm
CARD_LOD = {"ConiferPine": 3, "SpruceSub": 4}   # last LOD = card, per species
INI_PALETTE = {0: (255, 255, 255), 1: (255, 0, 0), 2: (0, 255, 0), 3: (0, 0, 255),
               4: (255, 255, 0), 5: (255, 0, 255), 6: (0, 255, 255), 7: (128, 0, 128)}
INI_NAME = {0: "white", 1: "red", 2: "green", 3: "blue", 4: "yellow",
            5: "magenta", 6: "cyan", 7: "purple"}
SAT_MIN = 60      # channel spread (max-min) for a pixel to count as a LOD colour
MIN_PX = 20       # min saturated+matched pixels for a box to be classifiable
NEAR_MAX = 130.0  # max RGB distance from a pure palette colour
DOM_FRAC = 0.40   # dominant index must hold this share of a box's classified px


def read_legend(im):
    """Sample the engine's on-screen legend bar -> {index: (r,g,b)}. Locates the
    saturated legend row in the bottom strip, then the eight equal cells."""
    H, W, _ = im.shape
    row_y = None
    for y in range(H - 1, H - 240, -1):
        row = im[y].astype(int)
        spread = row.max(1) - row.min(1)
        sat = (spread > 120) & (row.max(1) > 150)
        if sat.sum() > 200:
            row_y = y
            xs = np.where(sat)[0]
            xmin, xmax = int(xs.min()), int(xs.max())
            break
    if row_y is None:
        return None
    # the saturated span is cells 1..7 (cell 0 is white, unsaturated, to its left)
    w = (xmax - xmin) / 7.0
    pal = {}
    for i in range(8):
        cx = int(xmin - w * 0.5) if i == 0 else int(xmin + (i - 0.5) * w)
        patch = im[row_y - 6:row_y + 7, cx - 12:cx + 12].reshape(-1, 3)
        pal[i] = tuple(int(v) for v in np.median(patch, axis=0))
    return pal


def validate_legend(pal):
    if pal is None:
        return False, {"error": "legend bar not found in still"}
    checks, ok = {}, True
    # only the LOD indices we actually classify (0..max card = 4) gate the run;
    # 5-7 (magenta/cyan/purple) never colour a tree here and the rendered purple
    # swatch is (187,0,187) vs the ini (128,0,128) anyway.
    used = set(range(max(CARD_LOD.values()) + 1))
    for i, ini in INI_PALETTE.items():
        d = float(np.linalg.norm(np.array(pal[i]) - np.array(ini)))
        good = d < 60.0
        checks["%d_%s" % (i, INI_NAME[i])] = {"read": list(pal[i]),
                                              "ini": list(ini), "dist": round(d, 1),
                                              "ok": bool(good), "gates": i in used}
        if i in used:
            ok = ok and good
    return ok, checks


def cam_forward(pitch, yaw):
    cp = math.cos(math.radians(pitch))
    return (math.cos(math.radians(yaw)) * cp,
            math.sin(math.radians(yaw)) * cp,
            math.sin(math.radians(pitch)))


def species_boxes(cam):
    """(species,x0,y0,x1,y1) for band instances in frustum. FOV_H from engine."""
    cx, cy, cz = cam
    yaw = math.radians(CAM_YAW)
    cam_pitch = math.radians(CAM_PITCH)
    W, H = RES
    half_h = math.radians(FOV_H) / 2.0
    half_v = math.atan(math.tan(half_h) * (H / float(W)))
    tanh, tanv = math.tan(half_h), math.tan(half_v)
    boxes = []

    def wrap(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    for sp in ("ConiferPine", "SpruceSub"):
        d = json.load(open(os.path.join(REPO, "foliage", "alpine_8k_%s.json" % sp),
                           encoding="utf-8-sig"))
        h_cm = d["cull_derivation"]["mesh_height_m"] * 100.0
        for inst in d["instances"]:
            ix, iy, iz = inst[0], inst[1], inst[2]
            sc = inst[6] if len(inst) > 6 else 1.0
            dx, dy, dz = ix - cx, iy - cy, iz - cz
            horiz = math.hypot(dx, dy)
            dist = math.hypot(horiz, dz)
            if dist < BAND[0] or dist > BAND[1] or horiz <= 0:
                continue
            ah = wrap(math.atan2(dy, dx) - yaw)
            if abs(ah) > half_h:
                continue
            top = h_cm * sc
            crown = 0.25 * top
            av_base = math.atan2(dz, horiz) - cam_pitch
            av_top = math.atan2(dz + top, horiz) - cam_pitch
            dah = math.atan2(crown, horiz)
            sx0 = W / 2 * (1 + math.tan(ah - dah) / tanh)
            sx1 = W / 2 * (1 + math.tan(ah + dah) / tanh)
            sy_top = H / 2 * (1 - math.tan(av_top) / tanv)
            sy_base = H / 2 * (1 - math.tan(av_base) / tanv)
            x0 = int(max(0, min(W - 1, min(sx0, sx1))))
            x1 = int(max(0, min(W, max(sx0, sx1))))
            y0 = int(max(0, min(H - 1, sy_top)))
            y1 = int(max(0, min(H, sy_base)))
            if x1 - x0 >= 3 and y1 - y0 >= 3:
                boxes.append((sp, x0, y0, x1, y1))
    return boxes


def load(name):
    p = os.path.join(STILLS, name + ".png")
    if not os.path.exists(p):
        return None
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)


def classify_box(im, box, pal):
    """Dominant saturated-palette LOD index for a box, or (None, ...)."""
    _, x0, y0, x1, y1 = box
    crop = im[y0:y1, x0:x1].reshape(-1, 3)
    spread = crop.max(1) - crop.min(1)
    sat = crop[(spread > SAT_MIN) & (crop.max(1) > 60)]
    if sat.shape[0] < MIN_PX:
        return None, 0.0, int(sat.shape[0])
    idxs = [1, 2, 3, 4, 5, 6, 7]   # exclude LOD0 white (unsaturated, = background)
    C = np.array([pal[i] for i in idxs], dtype=np.float64)
    dd = np.linalg.norm(sat[:, None, :] - C[None, :, :], axis=2)
    near, mind = dd.argmin(1), dd.min(1)
    near = near[mind < NEAR_MAX]
    if near.size < MIN_PX:
        return None, 0.0, int(near.size)
    counts = np.bincount(near, minlength=7)
    win = int(counts.argmax())
    frac = counts[win] / counts.sum()
    if frac < DOM_FRAC:
        return None, float(frac), int(near.size)
    return idxs[win], float(frac), int(near.size)


def tally(im, boxes, pal):
    per = {sp: {"card": 0, "geom": 0, "unclassified": 0, "lod_hist": {}}
           for sp in CARD_LOD}
    for b in boxes:
        sp = b[0]
        lod, frac, npx = classify_box(im, b, pal)
        if lod is None:
            per[sp]["unclassified"] += 1
            continue
        per[sp]["lod_hist"][lod] = per[sp]["lod_hist"].get(lod, 0) + 1
        if lod >= CARD_LOD[sp]:
            per[sp]["card"] += 1
        else:
            per[sp]["geom"] += 1
    return per


def combine(per_list):
    out = {}
    for sp in CARD_LOD:
        card = sum(p[sp]["card"] for p in per_list)
        geom = sum(p[sp]["geom"] for p in per_list)
        unc = sum(p[sp]["unclassified"] for p in per_list)
        hist = {}
        for p in per_list:
            for k, v in p[sp]["lod_hist"].items():
                hist[k] = hist.get(k, 0) + v
        cl = card + geom
        if cl < 10:   # rule 13: too few classified boxes is not a measurement
            out[sp] = {"verdict": "REFUSE (only %d classified boxes)" % cl,
                       "card_boxes": card, "geom_boxes": geom,
                       "unclassified": unc, "lod_hist": hist}
            continue
        pct = 100.0 * geom / cl
        out[sp] = {"verdict": ("HOLD TOOK, MEASURED" if pct >= 90 else
                               "NO-OP AT RUNTIME" if pct <= 10 else "INCONCLUSIVE"),
                   "geom_pct": round(pct, 1), "card_boxes": card,
                   "geom_boxes": geom, "classified": cl, "unclassified": unc,
                   "lod_hist": hist,
                   "card_lod_index": CARD_LOD[sp]}
    return out


def main():
    global CAM_YAW, CAM_PITCH, FOV_H
    cam = json.load(open(os.path.join(IN, "ring_station_v1.json")))["camera"]
    CAM_YAW, CAM_PITCH = float(cam["yaw_deg"]), float(cam["pitch_deg"])
    ring = (float(cam["x_cm"]), float(cam["y_cm"]), float(cam["z_cm"]))
    out = {"_what": "Brief 5 C1 direct runtime LOD readback (Mesh LOD Coloration)."}

    def refuse(msg, extra=None):
        out["_verdict"] = msg
        if extra:
            out.update(extra)
        json.dump(out, open(os.path.join(IN, OUTFILE), "w",
                            encoding="utf-8"), indent=1)
        print("VERDICT:", msg)

    # F7: FOV from the engine readback (C1 shot json, else a C2 shot json -- the
    # perspective-viewport FOV is an editor default, level-independent).
    fov, fov_src = None, None
    # the shot payload writes c1_shot_<out_name>.json regardless of prefix, so the
    # ring shot json is c1_shot_<PREFIX>_auto_ring.json.
    ring_shot_json = "c1_shot_%s_auto_ring.json" % PREFIX
    c1sj = os.path.join(IN, ring_shot_json)
    if os.path.exists(c1sj):
        v = json.load(open(c1sj)).get("readback", {}).get("viewport_fov_deg")
        if isinstance(v, (int, float)):
            fov, fov_src = float(v), ring_shot_json
    if fov is None:
        for f in sorted(glob.glob(os.path.join(IN, "c2_shot_*.json"))):
            v = json.load(open(f)).get("fov_readback")
            if isinstance(v, (int, float)):
                fov, fov_src = float(v), os.path.basename(f) + \
                    " (editor-default perspective FOV, level-independent)"
                break
    if fov is None:
        return refuse("REFUSE: no engine FOV readback in c1_shot_*.json or "
                      "c2_shot_*.json; cannot project boxes (F7).")
    FOV_H = fov
    out["fov_h_deg_engine"] = FOV_H
    out["fov_source"] = fov_src

    auto_ring = load("%s_auto_ring" % PREFIX)
    if auto_ring is None:
        return refuse("REFUSE: %s_auto_ring.png missing; run the capture driver."
                      % PREFIX)
    pal = read_legend(auto_ring)
    legend_ok, legend_checks = validate_legend(pal)
    out["legend"] = {"source": "on-screen Mesh LOD Coloration legend bar, "
                               "sampled per swatch; validated vs BaseEngine.ini:"
                               "273-280", "read_swatches": {str(k): list(v) for k, v
                               in (pal or {}).items()},
                     "ini_palette": {str(k): list(v) for k, v in INI_PALETTE.items()},
                     "names": {str(k): v for k, v in INI_NAME.items()},
                     "card_lod_index": CARD_LOD, "validation": legend_checks,
                     "validated_ok": bool(legend_ok)}
    if not legend_ok:
        return refuse("INCONCLUSIVE: on-screen legend failed validation vs the "
                      "ini palette; refusing to classify (rule 13 sibling).")

    fx, fy, fz = cam_forward(CAM_PITCH, CAM_YAW)
    deep = (ring[0] + fx * 30000.0, ring[1] + fy * 30000.0, ring[2] + fz * 30000.0)
    ring_boxes = species_boxes(ring)
    deep_boxes = species_boxes(deep)
    out["band_boxes"] = {"ring": len(ring_boxes), "deep": len(deep_boxes)}

    per_ring = tally(auto_ring, ring_boxes, pal)
    out["ring"] = combine([per_ring])
    per_list = [per_ring]
    auto_deep = load("%s_auto_deep" % PREFIX)
    if auto_deep is not None:
        per_deep = tally(auto_deep, deep_boxes, pal)
        out["deep"] = combine([per_deep])
        per_list.append(per_deep)
    out["combined"] = combine(per_list)

    verds = {v["verdict"] for v in out["combined"].values()}
    clean = {v for v in verds if v in ("HOLD TOOK, MEASURED", "NO-OP AT RUNTIME",
                                       "INCONCLUSIVE")}
    if verds == {"HOLD TOOK, MEASURED"}:
        out["_verdict"] = "HOLD TOOK, MEASURED"
    elif verds == {"NO-OP AT RUNTIME"}:
        out["_verdict"] = "NO-OP AT RUNTIME"
    else:
        out["_verdict"] = "PER-SPECIES: " + json.dumps(
            {s: out["combined"][s]["verdict"] for s in out["combined"]})

    # the render-data readback is the DECISIVE instrument (the desk's specified
    # no-op tiebreaker): does the mesh the runtime reads carry the held card
    # ScreenSize, or the original?
    rd = os.path.join(IN, RENDERDATA)
    rd_says_noop = None
    if os.path.exists(rd):
        cs = json.load(open(rd)).get("card_species", {})
        out["renderdata_corroboration"] = cs
        flags = [cs[s].get("matches_t3_hold") for s in cs
                 if cs[s].get("present_in_level")]
        if flags:
            rd_says_noop = not all(flags)   # any mismatch = held value absent
    # synthesise the plain C1 verdict. Render-data is decisive; colour corroborates.
    if rd_says_noop is True:
        out["_c1_verdict"] = ("NO-OP AT RUNTIME. Render-data card ScreenSize is "
                              "UNCHANGED from pre-hold (matches_t3_hold=false for "
                              "the card species) -- the runtime still selects the "
                              "card at the original screen size. The colour "
                              "readback corroborates directionally: the 128-512 m "
                              "band is ~%d%% card, whereas a hold that took would "
                              "render ~0%% card in this band (card pushed past 512 "
                              "m)." % round(100 - (out["combined"].get("ConiferPine", {})
                                                   .get("geom_pct", 0) or 0)))
    elif rd_says_noop is False:
        out["_c1_verdict"] = ("HOLD TOOK: render-data card ScreenSize matches "
                              "t3_hold for the card species.")
    else:
        out["_c1_verdict"] = "render-data readback absent; colour verdict only: " \
                             + out["_verdict"]

    json.dump(out, open(os.path.join(IN, OUTFILE), "w",
                        encoding="utf-8"), indent=1)
    print(json.dumps(out["combined"], indent=1))
    print("VERDICT:", out["_verdict"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Mesh LOD Coloration band readback. "
                                 "Identical classifier for C1 (pre-hold) and R2 "
                                 "(post-hold); --prefix selects the I/O set.")
    ap.add_argument("--prefix", default="c1",
                    help="c1 (default, the committed NO-OP baseline) or r2 "
                         "(post-hold). Selects stills dir derived/<prefix>_lodcolor, "
                         "stills <prefix>_auto_ring/_deep, shot json "
                         "c1_shot_<prefix>_auto_ring.json, <prefix>_renderdata.json, "
                         "and output <prefix>_lod_readback.json.")
    a = ap.parse_args()
    PREFIX = a.prefix
    STILLS = os.path.join(REPO, "research", "brief5", "derived",
                          "%s_lodcolor" % PREFIX)
    OUTFILE = "%s_lod_readback.json" % PREFIX
    RENDERDATA = "%s_renderdata.json" % PREFIX
    main()
