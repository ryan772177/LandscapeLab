"""Read-only measurement (2026-10-10, flatten review change 3): the flatten's OWN effect on the derived layer weights.

The shipped textures/alpine_8k_w8{a,b}.png is NOT reproduced by today's derive_layer_weights.py (16.3 M texels differ
outside the town), so a re-derive-and-compare against the shipped bake measures drift, not the flatten. Instead:
run the SAME producer twice -- on pre_source and on the flattened map -- via a scratch recipe copy whose only
change is heightmap.source, and diff the two runs. Outside the town crop they must be identical (control).
Writes only under _verify/streets_flatten/.
"""
import copy, io, json, os, sys
import numpy as np
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "scripts"))
Image.MAX_IMAGE_PIXELS = None
import derive_layer_weights as dlw
OUT = os.path.join(R, "_verify", "streets_flatten")
rec = json.load(io.open(os.path.join(R, "recipes", "alpine_8k.json"), encoding="utf-8"))
pre = rec["heightmap"]["street_flatten"]["pre_source"]
scratch = copy.deepcopy(rec)
scratch["heightmap"]["source"] = pre
sp = os.path.join(OUT, "_recipe_prestreets.json")
json.dump(scratch, io.open(sp, "w", encoding="utf-8"), indent=1)
dlw.RECIPE = sp
if dlw.main(["--out-prefix", "_verify/streets_flatten/pre_w8"]) not in (0, None):
    sys.exit("REFUSE: derive on pre_source failed")
ls = rec["landscape"]
ox, oy = ls["location_cm"][0], ls["location_cm"][1]
side = json.load(io.open(os.path.join(R, "textures", "alpine_8k_street_mask.png.json"), encoding="utf-8"))
x0, y0, sz = side["box_cm"]
m = int(rec["heightmap"]["street_flatten"]["crop_margin_m"])
c0, r0, n = int((x0 - ox) / 100) - m, int((y0 - oy) / 100) - m, int(sz / 100) + 2 * m
H0 = np.asarray(Image.open(os.path.join(R, pre)))
H1 = np.asarray(Image.open(os.path.join(R, rec["heightmap"]["source"])))
changed = H0 != H1
out = {"heightmap_changed_vertices": int(changed.sum())}
LAY = {"a": ["snow", "rock", "scree", "forest_floor"], "b": ["wet_shore", "dirt_path", "gravel", "meadow"]}
for ch in "ab":
    A = np.asarray(Image.open(os.path.join(OUT, "pre_w8%s.png" % ch))).astype(int)
    B = np.asarray(Image.open(os.path.join(OUT, "derived_w8%s.png" % ch))).astype(int)
    d = np.abs(A - B).max(axis=-1)
    inb = np.zeros(d.shape, bool)
    inb[r0:r0 + n, c0:c0 + n] = True
    rows = {"texels_compared": int(d.size), "differ_outside_crop_CONTROL": int((d[~inb] > 0).sum()),
            "differ_inside_crop": int((d[inb] > 0).sum()), "differ_gt_25pct_inside": int((d[inb] > 64).sum()),
            "differ_on_changed_vertices": int((d[changed] > 0).sum())}
    for k, name in enumerate(LAY[ch]):
        rows["mean_delta_%s_on_changed_pct" % name] = round(float((B[..., k] - A[..., k])[changed].mean()) / 2.55, 3)
    out["w8" + ch] = rows
json.dump(out, io.open(os.path.join(OUT, "weights_effect.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
