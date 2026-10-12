"""Read-only (2026-10-10, flatten review change 3): the flatten's own effect on the cavity map's R channel.
Runs bake_cavity_map.cavity() (pure) on pre_source and on the flattened map with the recipe's scales/depths, and
compares; control = the pre_source result vs the SHIPPED textures/alpine_8k_cavity.png R channel (is the shipped
map reproducible?). Writes only _verify/streets_flatten/cavity_effect.json."""
import io, json, os, sys
import numpy as np
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "scripts"))
Image.MAX_IMAGE_PIXELS = None
import bake_cavity_map as bcm
rec = json.load(io.open(os.path.join(R, "recipes", "alpine_8k.json"), encoding="utf-8"))
cv = rec["material"]["cavity"]
ls = rec["landscape"]
zs = float(ls["z_scale_cm"]) / 100.0
px_m = float(ls["scale_xy_cm"]) / 100.0
sf = rec["heightmap"]["street_flatten"]
out = {}
res = {}
for tag, rel in (("pre", sf["pre_source"]), ("flat", rec["heightmap"]["source"])):
    h = np.asarray(Image.open(os.path.join(R, rel))).astype(np.float64) / 65535.0 * zs
    res[tag] = np.round(bcm.cavity(h, px_m, cv["scales_m"], cv["depths_m"]) * 255.0).astype(np.int16)
ship = np.asarray(Image.open(os.path.join(R, cv["map"])))
ship = (ship[..., 0] if ship.ndim == 3 else ship).astype(np.int16)
side = json.load(io.open(os.path.join(R, "textures", "alpine_8k_street_mask.png.json"), encoding="utf-8"))
x0, y0, sz = side["box_cm"]
m = int(sf["crop_margin_m"])
c0, r0, n = int((x0 - ls["location_cm"][0]) / 100) - m, int((y0 - ls["location_cm"][1]) / 100) - m, int(sz / 100) + 2 * m
inb = np.zeros(ship.shape, bool)
inb[r0:r0 + n, c0:c0 + n] = True
d_ctrl = np.abs(res["pre"] - ship)
d_eff = np.abs(res["flat"] - res["pre"])
out = {"texels": int(ship.size),
       "CONTROL_pre_vs_shipped_differ": int((d_ctrl > 1).sum()), "control_max": int(d_ctrl.max()),
       "effect_differ_outside_crop": int((d_eff[~inb] > 0).sum()),
       "effect_differ_inside_crop": int((d_eff[inb] > 0).sum()),
       "effect_gt_25pct_inside": int((d_eff[inb] > 64).sum()),
       "effect_mean_signed_on_differ_pct": round(float((res["flat"] - res["pre"])[d_eff > 0].mean()) / 2.55, 2)
       if (d_eff > 0).any() else 0.0}
json.dump(out, io.open(os.path.join(R, "_verify", "streets_flatten", "cavity_effect.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
