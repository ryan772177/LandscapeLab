#!/usr/bin/env python3
"""Brief 5 isolated_check analyzer (operator-ordered R2 follow-up). READ-ONLY.

For the isolated ConiferPine and SpruceSub stills, classify the SINGLE target box
by the SAME instrument as C1/R2 (on-screen-legend palette + saturated-pixel
dominant LOD colour), reusing c1_lod_readback's read_legend / validate_legend /
classify_box unchanged. Because the box is intruder-free
(find_isolated_instances.py), this is an UNCONTAMINATED per-instance LOD read.

At 300 m, inside the 512 m cull: geometry (LOD1/2 = red/green) => the hold TOOK at
runtime; the pre-hold card (ConiferPine LOD3 = blue / SpruceSub LOD4 = yellow) =>
persisted on disk but NO runtime effect. Writes into r2_lod_readback.json under
"isolated_check". A box too small to classify REFUSES (rule 13).
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c1_lod_readback as C  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
STILLS = os.path.join(REPO, "research", "brief5", "derived", "iso_lodcolor")
CARD_LOD = {"ConiferPine": 3, "SpruceSub": 4}
STILL = {"ConiferPine": "iso_conifer", "SpruceSub": "iso_spruce"}


def main():
    iso = json.load(open(os.path.join(IN, "iso_targets.json"), encoding="utf-8"))
    result = {"_what": "uncontaminated single-instance LOD read at 300 m (inside "
              "the 512 m cull). geometry => hold took at runtime; pre-hold card => "
              "persisted on disk, no runtime effect.",
              "card_lod_index": CARD_LOD, "per_species": {}}
    for sp, card_idx in CARD_LOD.items():
        cand = (iso["targets"].get(sp) or [])
        rec = {"card_lod_index": card_idx}
        if not cand:
            rec["verdict"] = "REFUSE: no isolated camera found"
            result["per_species"][sp] = rec
            continue
        primary = cand[0]
        rec["range_m"] = primary["range_m"]
        rec["nn_other_m"] = primary["nn_other_m"]
        rec["expected_box"] = primary["expected_box"]
        png = os.path.join(STILLS, STILL[sp] + ".png")
        if not os.path.exists(png):
            rec["verdict"] = "REFUSE: still %s.png missing" % STILL[sp]
            result["per_species"][sp] = rec
            continue
        im = np.asarray(Image.open(png).convert("RGB"), dtype=np.float64)
        pal = C.read_legend(im)
        legend_ok, _ = C.validate_legend(pal)
        rec["legend_validated"] = bool(legend_ok)
        if not legend_ok:
            rec["verdict"] = "REFUSE: on-screen legend failed validation"
            result["per_species"][sp] = rec
            continue
        x0, y0, x1, y1 = [int(v) for v in primary["expected_box"]]
        lod, frac, npx = C.classify_box(im, (sp, x0, y0, x1, y1), pal)
        rec["classified_pixels"] = npx
        rec["dominant_frac"] = round(frac, 3)
        if lod is None:
            rec["verdict"] = ("REFUSE: target box unclassifiable (%d px, frac %.2f) "
                              "-- rule 13" % (npx, frac))
            result["per_species"][sp] = rec
            continue
        rec["lod_index"] = lod
        rec["lod_colour"] = C.INI_NAME.get(lod, str(lod))
        is_card = lod >= card_idx
        rec["is_card"] = bool(is_card)
        rec["verdict"] = ("NO RUNTIME EFFECT -- still the pre-hold card (%s LOD%d) "
                          "at %s m, inside the 512 m cull" % (rec["lod_colour"], lod,
                                                              rec["range_m"])) \
            if is_card else \
            ("HOLD TOOK AT RUNTIME -- geometry (%s LOD%d) at %s m, the card is gone "
             "from inside the cull" % (rec["lod_colour"], lod, rec["range_m"]))
        result["per_species"][sp] = rec

    # summarise
    verds = {sp: r.get("is_card") for sp, r in result["per_species"].items()}
    if all(v is False for v in verds.values()) and len(verds) == 2:
        result["summary"] = "HOLD TOOK AT RUNTIME (both isolated targets geometry)"
    elif any(v is True for v in verds.values()):
        result["summary"] = ("NO RUNTIME EFFECT for at least one species (isolated "
                             "target still a card): %s"
                             % {sp: result["per_species"][sp].get("lod_colour")
                                for sp in verds})
    else:
        result["summary"] = "INCONCLUSIVE (a target refused classification)"

    # merge into r2_lod_readback.json
    rb_path = os.path.join(IN, "r2_lod_readback.json")
    rb = json.load(open(rb_path, encoding="utf-8")) if os.path.exists(rb_path) else {}
    rb["isolated_check"] = result
    json.dump(rb, open(rb_path, "w", encoding="utf-8"), indent=1)
    print(json.dumps(result["per_species"], indent=1))
    print("SUMMARY:", result["summary"])


if __name__ == "__main__":
    main()
