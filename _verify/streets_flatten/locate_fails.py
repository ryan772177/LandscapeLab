"""Read-only diagnosis of a refused flatten dry run: WHERE do gates 3/4/5b/5c fail, and which shape is responsible.
Writes nothing except _verify/streets_flatten/locate_fails.json."""
import io, json, math, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "scripts"))
import flatten_streets as fs
from town_kit_reachability import doorsteps
rec = json.load(io.open(fs.RECIPE, encoding="utf-8"))
cfg = fs.load_cfg(rec)
H16 = np.asarray(Image.open(os.path.join(R, cfg["pre_source"])))
Hnew, rep, fails = fs.run(rec, cfg, H16)
r0, c0, n = rep["crop_rc"]
ls = rec["landscape"]; ox, oy, oz = ls["location_cm"]; px, zs = ls["scale_xy_cm"], ls["z_scale_cm"]
zc = lambda h: oz + (h.astype(np.float64) / 65535.0 - 0.5) * zs
Z = zc(H16[r0:r0 + n, c0:c0 + n]); Zn = zc(Hnew[r0:r0 + n, c0:c0 + n]); D = Zn - Z
X = ox + (c0 + np.arange(n)) * px; Y = oy + (r0 + np.arange(n)) * px
plan = json.load(io.open(os.path.join(R, fs.PLAN), encoding="utf-8"))
man = json.load(io.open(os.path.join(R, fs.MANIFEST), encoding="utf-8"))
cxp, cyp = plan["site_centre_cm"]
discs = [(cxp, cyp, float(plan["plaza_radius_cm"]))] + [tuple(s) for s in plan.get("squares", [])]


def where(j, i):
    x, y = float(X[i]), float(Y[j])
    dd = min(((math.hypot(x - a, y - b) - r) / 100.0, k) for k, (a, b, r) in enumerate(discs))
    return {"xy_cm": [round(x), round(y)], "nearest_disc": dd[1], "dist_to_disc_edge_m": round(dd[0], 1)}
out = {}
j, i = np.unravel_index(np.argmax(np.abs(D)), D.shape); out["max_delta"] = dict(where(j, i), delta_m=round(float(D[j, i]) / 100, 3))
gy, gx = np.gradient(D, px); g = np.hypot(gx, gy)
j, i = np.unravel_index(np.argmax(g), g.shape); out["steepest_edit"] = dict(where(j, i), deg=round(math.degrees(math.atan(g[j, i])), 1))
# new-surface slope vs old slope: where did the flatten make ground STEEPER than bank_max that was not already
sy0, sx0 = np.gradient(Z, px); sy1, sx1 = np.gradient(Zn, px)
s0 = np.degrees(np.arctan(np.hypot(sx0, sy0))); s1 = np.degrees(np.arctan(np.hypot(sx1, sy1)))
made = (s1 > float(cfg["bank_max_deg"])) & (s1 > s0 + 1.0)
out["vertices_made_steeper_than_bank"] = int(made.sum())
if made.any():
    j, i = np.unravel_index(np.argmax(np.where(made, s1 - s0, -1)), s1.shape)
    out["worst_made_steeper"] = dict(where(j, i), old_deg=round(float(s0[j, i]), 1), new_deg=round(float(s1[j, i]), 1))
# house-edge failures, grouped by nearest disc
ring = np.zeros(D.shape, bool)
GX, GY = np.meshgrid(X, Y)
prot = np.zeros(D.shape, bool)
for h in man["houses"]:
    d, _ = fs._rect_sdf(GX, GY, h["loc_cm"][0], h["loc_cm"][1], h["W_cm"] / 2 + 50, h["D_cm"] / 2 + 50, h["yaw_deg"])
    prot |= d <= 0
ring = ndimage.binary_dilation(prot) & ~prot
bad = ring & (np.abs(D) > float(cfg["house_edge_step_max_m"]) * 100)
out["house_edge_fails"] = [dict(where(j, i), delta_m=round(float(D[j, i]) / 100, 3)) for j, i in zip(*np.nonzero(bad))]
ds = doorsteps(man)
dd = {k: float(ndimage.map_coordinates(D, [[(v[1] - Y[0]) / px], [(v[0] - X[0]) / px]], order=1)[0]) for k, v in ds.items()}
out["doorstep_fails"] = [{"house": k, "delta_m": round(v / 100, 3), **where(int(round((ds[k][1] - Y[0]) / px)), int(round((ds[k][0] - X[0]) / px)))}
                         for k, v in dd.items() if abs(v) > float(cfg["doorstep_max_m"]) * 100]
json.dump(out, io.open(os.path.join(R, "_verify", "streets_flatten", "locate_fails.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
