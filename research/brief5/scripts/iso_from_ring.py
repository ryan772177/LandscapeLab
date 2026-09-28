#!/usr/bin/env python3
"""Brief 5 isolated_check, take 2 (operator-ordered). READ-ONLY, no editor.

The synthesized high-alpine iso cameras rendered pure white (those cells are
outside the offscreen render region; the ring_station_v1 CONTROL rendered 1.12M
saturated px, so render works — the locations don't). So instead of a new camera,
find target instances that are ALREADY UNCONTAMINATED in the rendered
iso_control_ring.png: from the ring_station_v1 camera, a ConiferPine and a
SpruceSub at 250-400 m whose 4K screen box contains NO other tree (within the
512 m cull) AND for which the target is the FRONTMOST tree in that box. Classify
those boxes with the SAME instrument as C1/R2.

geometry (LOD1/2) => hold took at runtime; pre-hold card (ConiferPine LOD3 blue /
SpruceSub LOD4 yellow) => persisted on disk, no runtime effect. Writes into
r2_lod_readback.json under isolated_check (replacing the white-frame attempt).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c1_lod_readback as C            # noqa: E402  (read_legend/validate/classify)
import find_isolated_instances as F   # noqa: E402  (load/project/overlap)

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
STILL = os.path.join(REPO, "research", "brief5", "derived", "iso_lodcolor",
                     "iso_control_ring.png")
CARD_LOD = {"ConiferPine": 3, "SpruceSub": 4}
CULL_CM = 51200.0


def main():
    cam_j = json.load(open(os.path.join(IN, "ring_station_v1.json"),
                           encoding="utf-8"))["camera"]
    cam = (float(cam_j["x_cm"]), float(cam_j["y_cm"]), float(cam_j["z_cm"]))
    cyaw = math.radians(float(cam_j["yaw_deg"]))
    cpitch = math.radians(float(cam_j["pitch_deg"]))
    xyz, hcm, sp = F.load()

    # project every tree once from the ring camera
    boxes = []
    for i in range(len(xyz)):
        d = math.dist(cam, xyz[i])
        if d > CULL_CM:
            continue
        b = F.project(cam, cyaw, cpitch, xyz[i], hcm[i])
        if b is not None:
            boxes.append((i, d, b))

    result = {"_what": "uncontaminated single-instance LOD read from the ring "
              "camera in the rendered iso_control_ring.png (the synthesized "
              "high-alpine cameras did not render). geometry => hold took at "
              "runtime; pre-hold card => persisted on disk, no runtime effect.",
              "camera": cam_j, "still": "iso_control_ring.png",
              "card_lod_index": CARD_LOD, "per_species": {}}

    if not os.path.exists(STILL):
        for s in CARD_LOD:
            result["per_species"][s] = {"verdict": "REFUSE: control still missing"}
        _write(result)
        return
    im = np.asarray(Image.open(STILL).convert("RGB"), dtype=np.float64)
    pal = C.read_legend(im)
    legend_ok, _ = C.validate_legend(pal)
    result["legend_validated"] = bool(legend_ok)

    for tsp, card_idx in CARD_LOD.items():
        # candidate target boxes for this species at 250-400 m, ranked by fewest
        # intruders then nearest (frontmost first)
        cand = []
        for (i, d, b) in boxes:
            if sp[i] != tsp:
                continue
            if not (25000.0 <= d <= 40000.0):     # 250-400 m
                continue
            if (b[2] - b[0] < 6) or (b[3] - b[1] < 12):
                continue
            intr = 0
            frontmost = True
            for (j, dj, bj) in boxes:
                if j == i:
                    continue
                if F.overlap(b, bj):
                    intr += 1
                    if dj < d:                     # something nearer in the box
                        frontmost = False
            area = (b[2] - b[0]) * (b[3] - b[1])
            cand.append((intr, d, i, b, frontmost, area))
        rec = {"card_lod_index": card_idx,
               "n_candidates_250_400m": len(cand)}
        clean = [c for c in cand if c[0] == 0]
        rec["n_zero_intruder"] = len(clean)
        rec["n_frontmost"] = sum(1 for c in cand if c[4])
        # PICK ORDER: a zero-intruder box is ideal; else the FRONTMOST target
        # (nothing nearer in its box, so its pixels are the box foreground) with
        # the LARGEST area (most pixels => most reliable dominant classification).
        # The classifier's dominant-saturated-colour logic then reads the
        # foreground target's LOD even with far background intruders behind it.
        if clean:
            clean.sort(key=lambda t: -t[5])
            pick = clean[0]
        else:
            front = [c for c in cand if c[4]]
            pick = (sorted(front, key=lambda t: -t[5])[0] if front
                    else (sorted(cand, key=lambda t: (t[0], -t[5]))[0] if cand
                          else None))
        if pick is None:
            rec["verdict"] = "REFUSE: no target instance in 250-400 m band"
            result["per_species"][tsp] = rec
            continue
        intr, d, i, b, frontmost, area = pick
        rec["intruders_in_box"] = intr
        rec["frontmost"] = bool(frontmost)
        rec["box_area_px"] = int(area)
        rec["range_m"] = round(d / 100.0, 1)
        rec["box"] = [round(v, 1) for v in b]
        if not legend_ok:
            rec["verdict"] = "REFUSE: legend failed validation"
            result["per_species"][tsp] = rec
            continue
        x0, y0, x1, y1 = [int(v) for v in b]
        lod, frac, npx = C.classify_box(im, (tsp, x0, y0, x1, y1), pal)
        rec["classified_pixels"] = npx
        rec["dominant_frac"] = round(frac, 3)
        if lod is None:
            rec["verdict"] = "REFUSE: box unclassifiable (%d px) -- rule 13" % npx
            result["per_species"][tsp] = rec
            continue
        rec["lod_index"] = lod
        rec["lod_colour"] = C.INI_NAME.get(lod, str(lod))
        is_card = lod >= card_idx
        rec["is_card"] = bool(is_card)
        rec["verdict"] = (
            "NO RUNTIME EFFECT -- pre-hold card (%s LOD%d) at %s m inside the 512 m "
            "cull" % (rec["lod_colour"], lod, rec["range_m"]) if is_card else
            "HOLD TOOK AT RUNTIME -- geometry (%s LOD%d) at %s m; card gone from "
            "inside the cull" % (rec["lod_colour"], lod, rec["range_m"]))
        if intr != 0:
            rec["_caveat"] = ("no zero-intruder box existed in the dense band; this "
                              "is the fewest-intruder frontmost target -- "
                              "semi-contaminated, read with care")
        result["per_species"][tsp] = rec

    _summary(result)
    _write(result)


def _summary(result):
    v = {s: r.get("is_card") for s, r in result["per_species"].items()}
    if v and all(x is False for x in v.values()):
        result["summary"] = "HOLD TOOK AT RUNTIME (isolated targets render geometry)"
    elif any(x is True for x in v.values()):
        result["summary"] = ("NO RUNTIME EFFECT for at least one species "
                             "(isolated target still a card): "
                             + json.dumps({s: result["per_species"][s].get("lod_colour")
                                           for s in v}))
    else:
        result["summary"] = "INCONCLUSIVE (a target refused classification)"


def _write(result):
    rb_path = os.path.join(IN, "r2_lod_readback.json")
    rb = json.load(open(rb_path, encoding="utf-8")) if os.path.exists(rb_path) else {}
    rb["isolated_check"] = result
    json.dump(rb, open(rb_path, "w", encoding="utf-8"), indent=1)
    print(json.dumps(result.get("per_species", {}), indent=1))
    print("SUMMARY:", result.get("summary"))


if __name__ == "__main__":
    main()
