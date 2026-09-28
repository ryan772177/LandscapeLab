#!/usr/bin/env python3
"""canopy_cover.py - Brief 5 (desk): is the forest a forest? Measure it, then derive the density.

Pure python + numpy, no UE. Reads the four foliage plans (foliage/alpine_8k_<Species>.json,
instances = [x_cm, y_cm, z_cm, ?, ?, ?, scale, ...], as read by derive_forest_station.py) and the
tree LOD probe (for crown extents), rasterises every crown as a disc on a ground grid, and reports
per 256 m bin:

  canopy_cover   fraction of ground under at least one crown (MEASURED from the plans - no
                 placement-model assumption)
  stems_per_ha   all trees, and large trees (species height >= --large-m)
  class          US National Vegetation Classification physiognomic cover classes:
                 forest >= 0.60, woodland 0.25-0.60, sparse 0.10-0.25, open < 0.10
  sightline_m    mean free path at eye height, 1 / sum(n_i * w_i)  (w_i ASSUMED - see --eye-frac)

and derives the density multiplier m that lifts a bin from cover c to a target T:

      m = ln(1 - T) / ln(1 - c)

(uncovered fraction of independently placed crowns is u = exp(-n*A); multiplying n by m gives u^m.
 If the placer enforces a minimum spacing, crowns overlap less and the true m is SMALLER - so this
 m is an upper bound on the trees needed.)

Usage:
  python canopy_cover.py --plans <repo>/foliage --probe tree_lod_probe_v3.json --out canopy_cover.json
  python canopy_cover.py --selftest
"""
import argparse, json, math, os, sys
import numpy as np

SPECIES = ["Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"]
CLASSES = [(0.60, "forest"), (0.25, "woodland"), (0.10, "sparse"), (0.0, "open")]


def classify(c):
    for lo, name in CLASSES:
        if c >= lo:
            return name
    return "open"


def multiplier(c, target):
    if c <= 0.0:
        return None
    if c >= target:
        return 1.0
    return math.log(1.0 - target) / math.log(1.0 - c)


def stamp(cover, ix, iy, rad_cells):
    """OR a disc of radius rad_cells[i] (in cells, float) at each (ix[i], iy[i]). Vectorised by
    quantised radius and by offset."""
    h, w = cover.shape
    rq = np.maximum(1, np.rint(rad_cells * 2).astype(int))      # half-cell radius quanta
    for q in np.unique(rq):
        sel = rq == q
        r = q / 2.0
        R = int(math.ceil(r))
        x0, y0 = ix[sel], iy[sel]
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                if dx * dx + dy * dy > r * r:
                    continue
                xx, yy = x0 + dx, y0 + dy
                ok = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
                cover[yy[ok], xx[ok]] = True


def analyse(trees, cell_cm, bin_cm, target, large_m, eye_frac, min_trees_bin):
    """trees: {species: {"xy": Nx2 cm, "scale": N, "crown_r_cm": float, "height_m": float}}"""
    allxy = np.vstack([t["xy"] for t in trees.values() if len(t["xy"])])
    lo = np.floor(allxy.min(0) / bin_cm) * bin_cm
    hi = np.ceil(allxy.max(0) / bin_cm) * bin_cm
    w = int(round((hi[0] - lo[0]) / cell_cm)); h = int(round((hi[1] - lo[1]) / cell_cm))
    cover = np.zeros((h, w), dtype=bool)
    nb = (int(round((hi[0] - lo[0]) / bin_cm)), int(round((hi[1] - lo[1]) / bin_cm)))
    stems = np.zeros((nb[1], nb[0])); large = np.zeros_like(stems); block = np.zeros_like(stems)
    for sp, t in trees.items():
        if not len(t["xy"]):
            continue
        ix = ((t["xy"][:, 0] - lo[0]) / cell_cm).astype(int)
        iy = ((t["xy"][:, 1] - lo[1]) / cell_cm).astype(int)
        r_cm = t["crown_r_cm"] * t["scale"]
        stamp(cover, ix, iy, r_cm / cell_cm)
        bx = np.clip(((t["xy"][:, 0] - lo[0]) / bin_cm).astype(int), 0, nb[0] - 1)
        by = np.clip(((t["xy"][:, 1] - lo[1]) / bin_cm).astype(int), 0, nb[1] - 1)
        np.add.at(stems, (by, bx), 1)
        if t["height_m"] >= large_m:
            np.add.at(large, (by, bx), 1)
        np.add.at(block, (by, bx), 2.0 * r_cm / 100.0 * eye_frac.get(sp, 0.5))   # metres of width
    cpb = int(round(bin_cm / cell_cm))
    cov_bin = cover.reshape(nb[1], cpb, nb[0], cpb).mean(axis=(1, 3))
    ha = (bin_cm / 100.0) ** 2 / 1e4
    dom = stems >= min_trees_bin
    out_bins = []
    for by in range(nb[1]):
        for bx in range(nb[0]):
            if not dom[by, bx]:
                continue
            c = float(cov_bin[by, bx])
            area_m2 = (bin_cm / 100.0) ** 2
            sl = area_m2 / block[by, bx] if block[by, bx] > 0 else None
            out_bins.append({"bin": [int(round(lo[0] / bin_cm)) + bx, int(round(lo[1] / bin_cm)) + by],
                             "cover": round(c, 4), "class": classify(c),
                             "stems_per_ha": round(stems[by, bx] / ha, 1),
                             "large_per_ha": round(large[by, bx] / ha, 1),
                             "sightline_m": None if sl is None else round(sl, 1),
                             "m_to_target": None if multiplier(c, target) is None
                             else round(multiplier(c, target), 2)})
    covs = np.array([b["cover"] for b in out_bins]) if out_bins else np.zeros(1)
    q = lambda p: float(np.percentile(covs, p))
    summ = {"bins_in_domain": len(out_bins),
            "domain_rule": "256 m bins holding >= %d trees" % min_trees_bin,
            "cover_percentiles": {k: round(q(v), 4) for k, v in
                                  (("p10", 10), ("p50", 50), ("p75", 75), ("p90", 90), ("max", 100))},
            "class_share_of_domain": {n: round(float(np.mean([b["class"] == n for b in out_bins])), 4)
                                      for _, n in CLASSES} if out_bins else {},
            "target_cover": target,
            "m_for": {k: (None if multiplier(q(v), target) is None else round(multiplier(q(v), target), 2))
                      for k, v in (("p50_bin", 50), ("p75_bin", 75), ("p90_bin", 90), ("densest_bin", 100))},
            "_m_note": "m is an UPPER bound (independent placement). m_for.p90_bin is the desk's "
                       "proposed global multiplier: it makes the densest tenth of the forest a forest "
                       "and leaves the existing density gradient toward the treeline intact."}
    return summ, out_bins


def load_plans(plans_dir, probe, crown_factor):
    pm = {m["species"]: m for m in probe["meshes"]}
    trees = {}
    for sp in SPECIES:
        d = json.load(open(os.path.join(plans_dir, "alpine_8k_%s.json" % sp), encoding="utf-8"))
        a = np.array([[i[0], i[1], i[6]] for i in d["instances"]], dtype=np.float64)
        ext = pm[sp]["bounds_extent_cm"]
        trees[sp] = {"xy": a[:, :2], "scale": a[:, 2],
                     "crown_r_cm": 0.5 * (ext[0] + ext[1]) * crown_factor,
                     "height_m": pm[sp]["height_cm"] / 100.0}
    return trees


def selftest():
    rng = np.random.default_rng(5)
    side = 102400.0                                   # 1024 m
    n_per_m2, r_cm = 0.01, 500.0
    n = int(n_per_m2 * (side / 100) ** 2)
    xy = rng.uniform(0, side, size=(n, 2))
    trees = {"Conifer": {"xy": xy, "scale": np.ones(n), "crown_r_cm": r_cm, "height_m": 29.0}}
    summ, bins = analyse(trees, 100.0, 25600.0, 0.70, 15.0, {"Conifer": 0.8}, 10)
    exp = 1 - math.exp(-n_per_m2 * math.pi * 5.0 ** 2)          # 0.5441
    got = float(np.mean([b["cover"] for b in bins]))
    ok = abs(got - exp) < 0.02                                  # interior + edge bins average
    ok &= abs(multiplier(exp, 0.70) - math.log(0.3) / math.log(1 - exp)) < 1e-12
    ok &= abs(multiplier(0.5441, 0.70) - 1.533) < 0.01
    ok &= classify(0.61) == "forest" and classify(0.3) == "woodland" and classify(0.05) == "open"
    # sightline: 1/(n*w) = 1/(0.01 * 10*0.8) = 12.5 m
    sl = float(np.mean([b["sightline_m"] for b in bins]))
    ok &= abs(sl - 12.5) < 0.6
    # doubling density must move cover as u^2
    xy2 = rng.uniform(0, side, size=(2 * n, 2))
    t2 = {"Conifer": {"xy": xy2, "scale": np.ones(2 * n), "crown_r_cm": r_cm, "height_m": 29.0}}
    s2, b2 = analyse(t2, 100.0, 25600.0, 0.70, 15.0, {"Conifer": 0.8}, 10)
    got2 = float(np.mean([b["cover"] for b in b2]))
    ok &= abs(got2 - (1 - (1 - exp) ** 2)) < 0.02
    print("SELFTEST", "PASS" if ok else "FAIL", "cover %.4f (exp %.4f)  x2 %.4f (exp %.4f)  sightline %.1f"
          % (got, exp, got2, 1 - (1 - exp) ** 2, sl))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans"); ap.add_argument("--probe"); ap.add_argument("--out")
    ap.add_argument("--cell-cm", type=float, default=100.0)
    ap.add_argument("--bin-cm", type=float, default=25600.0)
    ap.add_argument("--target", type=float, default=0.70)
    ap.add_argument("--large-m", type=float, default=15.0)
    ap.add_argument("--crown-factor", type=float, default=0.85,
                    help="opaque crown radius / mesh XY half-extent (ASSUMED 0.85; report 0.70 and 1.00 too)")
    ap.add_argument("--min-trees-bin", type=int, default=10)
    ap.add_argument("--eye-frac", nargs="*", default=["Conifer=0.8", "ConiferPine=0.06",
                                                       "SpruceSub=0.8", "SpruceSapling=0.8"],
                    help="fraction of crown diameter that blocks a sightline at eye height (ASSUMED)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.plans and a.probe):
        ap.error("--plans and --probe required")
    probe = json.load(open(a.probe, encoding="utf-8"))
    eye = {x.split("=")[0]: float(x.split("=")[1]) for x in a.eye_frac}
    res = {"_what": "Brief 5 desk tool: canopy cover / stem density / sightline per 256 m bin",
           "params": {"cell_cm": a.cell_cm, "bin_cm": a.bin_cm, "target": a.target,
                      "crown_factor": a.crown_factor, "eye_frac": eye, "large_m": a.large_m},
           "sensitivity": {}}
    for cf in sorted({0.70, a.crown_factor, 1.00}):
        summ, bins = analyse(load_plans(a.plans, probe, cf), a.cell_cm, a.bin_cm, a.target,
                             a.large_m, eye, a.min_trees_bin)
        res["sensitivity"]["crown_factor_%.2f" % cf] = summ
        if cf == a.crown_factor:
            res["summary"], res["bins"] = summ, bins
    s = json.dumps(res, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(s + "\n")
    print(json.dumps(res["summary"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
