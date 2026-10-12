"""flatten_streets.py -- smooth the town's streets into the heightmap, OFFLINE (2026-10-10).

    python scripts/flatten_streets.py --init-prestreets   # once: copy the shipped heightmap to pre_source
    python scripts/flatten_streets.py                     # build + every gate, write nothing (dry run)
    python scripts/flatten_streets.py --write             # ... and write terrain/alpine_8k.png + sidecar
    python scripts/flatten_streets.py --selftest

Design: research/town_kit/FLATTEN_DESIGN.md (design review 2026-10-10 GO-WITH-CHANGES, changes 1-8).
Every parameter is recipes/alpine_8k.json heightmap.street_flatten. Standing rule 4: the heightmap PNG is edited
off-disk through the pipeline (the carve_water_notches.py precedent), never by an editor sculpt.

THE SURFACE (read from pre_source, ALWAYS -- a re-run never flattens twice):
  S      = pre-streets ground, Gaussian-smoothed at sigma_m. On a street T = S: the bumps go, the natural
           cross-slope stays. (Levelling across the width put 105 of 349 doorsteps on a > 0.3 m step, because houses
           stand on ground traced at their door edge -- LESSONS 2026-10-10gg.)
  discs  = plaza + squares: least-squares plane of the ground over the disc, natural tilt kept (review Q4: no cap).
  blend  = alpha 1 on each shape, smoothstep to 0 across that shape's shoulder. The shoulder is
           max(shoulder_m, 1.5 x the shape's max |T - Z| / tan(bank_max_deg)), so a big cut gets a wide bank
           (smoothstep's peak slope is 1.5x the linear one).
  houses = alpha 0 inside footprint + guard_m (byte-identical: houses are not moved), then x smoothstep(distance
           outside / house_fade_m) on every wall, and x smoothstep(distance to the door-edge midpoint / door_apron_m).
  H'     = H + alpha (T - H), rounded to the uint16 grid.

GATES (refuse = nothing written; every count printed; a 0 count refuses -- rule 13):
  1 locality: everything outside the town crop is byte-identical; the changed set lies where alpha > 0
  2 houses: every footprint + guard_m byte-identical to pre_source
  3 doorsteps (town_kit_reachability.doorsteps, the reachability tool's own points): the step to the door-edge
    trace point may WORSEN by <= doorstep_max_m (|Znew_ds - z_edge| - |Z_ds - z_edge|); the absolute after-step is
    reported only. (Raw |delta| was the first semantics; it counted stamp-spike removal as damage, 2026-10-10hh.)
  4 bound: |delta| <= max_abs_delta_m everywhere
  5 effect: street centreline deviation from chord, p90 after < p90 before
  5b house edge: the step from each vertex one outside a footprint + guard to its protected neighbours' mean may
    WORSEN by <= house_edge_step_max_m
  5c bank: no NEW bank -- 0 vertices with slope <= bank_max_deg before and > bank_max_deg (+1 deg) after; ground
    already steeper than bank_max that is steepened further is reported (count + worst pair), not gated
  6 consumers on changed ground (|delta| >= changed_threshold_cm): foliage plan instances (minus the town clearance
    record), verified encounters, water planes/falls -- printed; nonzero is a decision recorded before the push
  7 determinism: two runs byte-identical
  overwrite guard (review change 4): terrain/alpine_8k.png on disk must equal pre_source (first run) or this tool's
  LAST output (sidecar) -- anything else is a later in-place edit a re-run would silently revert: REFUSE.
"""
import argparse
import hashlib
import io
import json
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
from town_kit_manifest import _world  # noqa: E402  (one declaration of the house frame)
from town_kit_reachability import doorsteps  # noqa: E402  (one declaration of the doorstep points)

REPO = bootstrap.REPO_ROOT
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
PLAN = "city/alpine_basin_town_plan.json"
MANIFEST = "city/alpine_basin_town_kit_manifest.json"
MASK_SIDE = "textures/alpine_8k_street_mask.png.json"
REMOVED = "city/alpine_basin_town_kit_foliage_removed.json"
VERIFIED_ENC = "encounters/alpine_8k_verified.json"
WATER = "water/alpine_8k_water_plan.json"
REPORT = "_verify/streets_flatten/flatten_report.json"
Image.MAX_IMAGE_PIXELS = None
KEYS = ("pre_source", "pre_source_sha256", "sigma_m", "shoulder_m", "bank_max_deg", "guard_m", "house_fade_m",
        "door_apron_m", "max_abs_delta_m", "doorstep_max_m", "house_edge_step_max_m", "changed_threshold_cm",
        "crop_margin_m")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cfg(rec):
    sf = (rec.get("heightmap") or {}).get("street_flatten")
    if not sf:
        raise SystemExit("REFUSE: recipes/alpine_8k.json has no heightmap.street_flatten")
    miss = [k for k in KEYS if k not in sf]
    if miss:
        raise SystemExit("REFUSE: heightmap.street_flatten lacks %s" % miss)
    return sf


def _smooth01(v):
    v = np.clip(v, 0.0, 1.0)
    return v * v * (3.0 - 2.0 * v)


def _rect_sdf(GX, GY, cx, cy, hx, hy, yaw_deg):
    a = math.radians(yaw_deg)
    ca, sa = math.cos(a), math.sin(a)
    lx = (GX - cx) * ca + (GY - cy) * sa
    ly = -(GX - cx) * sa + (GY - cy) * ca
    qx, qy = np.abs(lx) - hx, np.abs(ly) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0), lx


def flatten(Z, X, Y, streets, discs, houses, door_edges, cfg):
    """Pure. Z = ground in world cm on the grid (rows = Y, cols = X); returns (Znew float cm, diagnostics).
    streets: (cx, cy, len, width, yaw); discs: (cx, cy, r); houses: (cx, cy, W, D, yaw); door_edges: (x, y)."""
    px = float(X[1] - X[0])
    tb = math.tan(math.radians(float(cfg["bank_max_deg"])))
    sh0 = float(cfg["shoulder_m"]) * 100.0
    GX, GY = np.meshgrid(X, Y)
    # Plain Gaussian (a street-masked normalised convolution was tried and REJECTED: it rested on a wrong root
    # cause and moved 9 doorsteps > 0.3 m instead of 1 -- LESSONS 2026-10-10hh correction).
    S = ndimage.gaussian_filter(Z, float(cfg["sigma_m"]) * 100.0 / px, mode="nearest")
    T = S.copy()
    alpha = np.zeros_like(Z)
    diag = {"discs": [], "pieces_widened": 0, "max_shoulder_m": sh0 / 100.0}
    for cx, cy, r in discs:
        dd = np.hypot(GX - cx, GY - cy) - r
        ins = dd <= 0
        if int(ins.sum()) < 3:
            raise ValueError("disc at (%.0f, %.0f) r %.0f covers %d vertices" % (cx, cy, r, int(ins.sum())))
        A = np.c_[GX[ins] - cx, GY[ins] - cy, np.ones(int(ins.sum()))]
        coef, *_ = np.linalg.lstsq(A, Z[ins], rcond=None)
        P = coef[0] * (GX - cx) + coef[1] * (GY - cy) + coef[2]
        dmax = float(np.abs(P - Z)[ins].max())
        sh = max(sh0, 1.5 * dmax / tb)
        w = np.where(ins, 1.0, np.clip(1.0 - dd / sh, 0.0, 1.0))
        T = T + w * (P - T)
        alpha = np.maximum(alpha, np.where(ins, 1.0, _smooth01(1.0 - dd / sh)))
        diag["discs"].append({"centre_cm": [round(cx, 1), round(cy, 1)], "r_m": r / 100.0,
                              "plane_slope_deg": round(math.degrees(math.atan(math.hypot(coef[0], coef[1]))), 2),
                              "max_abs_delta_m": round(dmax / 100.0, 3), "shoulder_m": round(sh / 100.0, 2)})
        diag["max_shoulder_m"] = max(diag["max_shoulder_m"], sh / 100.0)
    def win(cx, cy, reach, strict=False):
        a0, a1 = int((cx - reach - X[0]) / px), int((cx + reach - X[0]) / px) + 2
        b0, b1 = int((cy - reach - Y[0]) / px), int((cy + reach - Y[0]) / px) + 2
        if strict and (a0 < 0 or b0 < 0 or a1 > len(X) or b1 > len(Y)):
            # audit F1: a street/disc whose support leaves the grid would be flattened partially, silently
            raise ValueError("shape at (%.0f, %.0f) reach %.0f cm leaves the crop -- raise crop_margin_m"
                             % (cx, cy, reach))
        i0, i1, j0, j1 = max(0, a0), min(len(X), a1), max(0, b0), min(len(Y), b1)
        return (slice(j0, j1), slice(i0, i1)) if i0 < i1 and j0 < j1 else None

    for cx, cy, ln, wd, yaw in streets:
        hx, hy = ln / 2.0, wd / 2.0
        sl = win(cx, cy, math.hypot(hx, hy) + px, strict=True)
        d, _ = _rect_sdf(GX[sl], GY[sl], cx, cy, hx, hy, yaw)
        ins = d <= 0
        if not ins.any():
            raise ValueError("street at (%.0f, %.0f) covers no vertex" % (cx, cy))
        dmax = float(np.abs(T[sl] - Z[sl])[ins].max())
        sh = max(sh0, 1.5 * dmax / tb)
        if sh > sh0:
            diag["pieces_widened"] += 1
            diag["max_shoulder_m"] = max(diag["max_shoulder_m"], sh / 100.0)
        sl = win(cx, cy, math.hypot(hx, hy) + sh + px, strict=True)
        d, _ = _rect_sdf(GX[sl], GY[sl], cx, cy, hx, hy, yaw)
        alpha[sl] = np.maximum(alpha[sl], np.where(d <= 0, 1.0, _smooth01(1.0 - d / sh)))
    # houses: hard zero inside footprint + guard, faded on every wall, and the door apron
    gm = float(cfg["guard_m"]) * 100.0
    fade = float(cfg["house_fade_m"]) * 100.0
    dh = np.full(Z.shape, np.inf)
    for cx, cy, W, D, yaw in houses:
        sl = win(cx, cy, math.hypot(W / 2.0 + gm, D / 2.0 + gm) + fade + px)
        if sl is None:
            continue
        d, _ = _rect_sdf(GX[sl], GY[sl], cx, cy, W / 2.0 + gm, D / 2.0 + gm, yaw)
        dh[sl] = np.minimum(dh[sl], d)
    prot = dh <= 0
    if fade > 0:
        alpha *= np.where(prot, 0.0, _smooth01(dh / fade))
    alpha[prot] = 0.0
    ap = float(cfg["door_apron_m"]) * 100.0
    if ap > 0:
        dd = np.full(Z.shape, np.inf)
        for ex, ey in door_edges:
            sl = win(ex, ey, ap + px)
            if sl is not None:
                dd[sl] = np.minimum(dd[sl], np.hypot(GX[sl] - ex, GY[sl] - ey))
        alpha *= _smooth01(dd / ap)
    return Z + alpha * (T - Z), dict(diag, protected_vertices=int(prot.sum()), prot=prot, alpha=alpha)


def gate_houses(new, old, prot):
    """Gate 2 (shared by run() and the selftest, audit F4): every protected vertex byte-identical, or a reason."""
    if not prot.any():
        return "gate 2: 0 protected house vertices -- nothing to check (rule 13)"
    nbad = int((new[prot] != old[prot]).sum())
    return "gate 2: %d of %d house vertices changed" % (nbad, int(prot.sum())) if nbad else None


def _chord_dev(arr, X, Y, streets):
    px = float(X[1] - X[0])
    out = []
    for cx, cy, ln, wd, yaw in streets:
        hx = ln / 2.0
        a = math.radians(yaw)
        t = np.linspace(-hx, hx, max(15, int(math.ceil(2 * hx / 50.0)) + 1))
        z = ndimage.map_coordinates(arr, [(cy + t * math.sin(a) - Y[0]) / px, (cx + t * math.cos(a) - X[0]) / px],
                                    order=1)
        chord = z[0] + (z[-1] - z[0]) * (t + hx) / (2 * hx)
        out.append(float(np.abs(z - chord).max()))
    return np.array(out)


def _q(v):
    v = np.asarray(v, dtype=np.float64)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "p50": round(float(np.percentile(v, 50)), 3), "p90": round(float(np.percentile(v, 90)), 3),
            "max": round(float(v.max()), 3)}


def run(rec, cfg, H16):
    """Build + gates on the full pre-streets array. Returns (Hnew uint16, report dict, fails list)."""
    ls = rec["landscape"]
    ox, oy, oz = [float(v) for v in ls["location_cm"]]
    px, zs = float(ls["scale_xy_cm"]), float(ls["z_scale_cm"])
    side = json.load(io.open(os.path.join(REPO, MASK_SIDE), encoding="utf-8"))
    bx0, by0, bsz = side["box_cm"]
    m = int(float(cfg["crop_margin_m"]) * 100.0 / px)
    c0, r0 = int((bx0 - ox) / px) - m, int((by0 - oy) / px) - m
    n = int(bsz / px) + 2 * m
    if c0 < 0 or r0 < 0 or c0 + n > H16.shape[1] or r0 + n > H16.shape[0]:
        raise SystemExit("REFUSE: the town crop leaves the heightmap")
    Hc = H16[r0:r0 + n, c0:c0 + n].astype(np.float64)
    Z = oz + (Hc / 65535.0 - 0.5) * zs
    X = ox + (c0 + np.arange(n)) * px
    Y = oy + (r0 + np.arange(n)) * px
    plan = json.load(io.open(os.path.join(REPO, PLAN), encoding="utf-8"))
    man = json.load(io.open(os.path.join(REPO, MANIFEST), encoding="utf-8"))
    streets = [(s["loc_cm"][0], s["loc_cm"][1], s["len_cm"], s["width_cm"], s["yaw_deg"]) for s in plan["streets"]]
    cxp, cyp = plan["site_centre_cm"]
    discs = [(cxp, cyp, float(plan["plaza_radius_cm"]))] + [(x, y, r) for x, y, r in plan.get("squares", [])]
    houses = [(h["loc_cm"][0], h["loc_cm"][1], h["W_cm"], h["D_cm"], h["yaw_deg"]) for h in man["houses"]]
    door_edges = [_world(h["loc_cm"][0], h["loc_cm"][1], h["yaw_deg"], h["trace_local_xy"][0], h["trace_local_xy"][1])
                  for h in man["houses"]]
    if not streets or not houses:
        raise SystemExit("REFUSE: %d streets, %d houses (rule 13)" % (len(streets), len(houses)))
    Znew, diag = flatten(Z, X, Y, streets, discs, houses, door_edges, cfg)
    hq = np.clip(np.round((Znew - oz) / zs * 65535.0 + 0.5 * 65535.0), 0, 65535).astype(np.uint16)
    Hnew = H16.copy()
    Hnew[r0:r0 + n, c0:c0 + n] = hq
    Zq = oz + (hq.astype(np.float64) / 65535.0 - 0.5) * zs
    D = Zq - Z
    fails, rep = [], {"crop_rc": [r0, c0, n], "streets": len(streets), "discs": len(discs), "houses": len(houses)}
    # 1 locality
    outside = np.ones(H16.shape, bool)
    outside[r0:r0 + n, c0:c0 + n] = False
    if not np.array_equal(Hnew[outside], H16[outside]):
        fails.append("gate 1: pixels outside the town crop changed")
    # audit F1: the flatten's support must lie inside the crop interior (a disc shoulder reaching the crop edge
    # would be cut off there and leave a step at the crop boundary)
    al = diag["alpha"]
    edge = np.concatenate([al[:2].ravel(), al[-2:].ravel(), al[:, :2].ravel(), al[:, -2:].ravel()])
    rep["crop_edge_alpha_max"] = float(edge.max())
    if edge.max() > 0:
        fails.append("gate 1: alpha %.3f on the crop's outer ring -- raise crop_margin_m" % edge.max())
    changed = hq != Hc.astype(np.uint16)
    stray = int((changed & (diag["alpha"] <= 0)).sum())
    rep["changed_vertices"] = int(changed.sum())
    if rep["changed_vertices"] == 0:
        fails.append("gate 1: 0 vertices changed -- nothing was flattened (rule 13)")
    if stray:
        fails.append("gate 1: %d changed vertices where alpha = 0" % stray)
    # 2 houses
    prot = diag["prot"]
    rep["protected_vertices"] = int(prot.sum())
    f2 = gate_houses(hq, Hc.astype(np.uint16), prot)
    if f2:
        fails.append(f2)
    # 3 doorsteps
    ds = np.array(list(doorsteps(man).values()), dtype=np.float64).reshape(-1, 2)
    if ds.shape[0] == 0:
        fails.append("gate 3: 0 doorsteps -- nothing to check (rule 13)")     # audit F5: reachable now
    else:
        fr, fc = (ds[:, 1] - Y[0]) / px, (ds[:, 0] - X[0]) / px
        if fr.min() < 0 or fc.min() < 0 or fr.max() > n - 1 or fc.max() > n - 1:
            fails.append("gate 3: a doorstep lies outside the crop")         # audit F1
        dd = ndimage.map_coordinates(D, [fr, fc], order=1)
        rep["doorstep_abs_delta_m"] = _q(np.abs(dd) / 100.0)
        # the step a resident walks: doorstep vs the door EDGE the house was traced on (inside the protected
        # footprint, so unchanged). Gate = how much the flatten made that step WORSE (LESSONS 2026-10-10hh:
        # removing a stamp spike AT a doorstep is a raw delta and an improvement).
        eg = np.array([_world(h["loc_cm"][0], h["loc_cm"][1], h["yaw_deg"], h["trace_local_xy"][0],
                              h["trace_local_xy"][1]) for h in man["houses"]], dtype=np.float64)
        ze = ndimage.map_coordinates(Z, [(eg[:, 1] - Y[0]) / px, (eg[:, 0] - X[0]) / px], order=1)
        z0 = ndimage.map_coordinates(Z, [fr, fc], order=1)
        worse = (np.abs(z0 + dd - ze) - np.abs(z0 - ze)) / 100.0
        rep["doorstep_step_before_m"] = _q(np.abs(z0 - ze) / 100.0)
        rep["doorstep_step_after_m"] = _q(np.abs(z0 + dd - ze) / 100.0)
        rep["doorstep_step_worsened_m"] = _q(worse)
        nd = int((worse > float(cfg["doorstep_max_m"])).sum())
        if nd:
            fails.append("gate 3: %d of %d doorstep steps worsen by more than doorstep_max_m" % (nd, len(ds)))
    # 4 bound
    rep["max_abs_delta_m"] = round(float(np.abs(D).max()) / 100.0, 3)
    if rep["max_abs_delta_m"] > float(cfg["max_abs_delta_m"]):
        fails.append("gate 4: max |delta| %.3f m > %.3f" % (rep["max_abs_delta_m"], float(cfg["max_abs_delta_m"])))
    # 5 effect
    before, after = _chord_dev(Z, X, Y, streets) / 100.0, _chord_dev(Zq, X, Y, streets) / 100.0
    rep["chord_dev_before_m"], rep["chord_dev_after_m"] = _q(before), _q(after)
    if not (rep["chord_dev_after_m"]["p90"] < rep["chord_dev_before_m"]["p90"]):
        fails.append("gate 5: centreline deviation p90 did not fall (%.3f -> %.3f)"
                     % (rep["chord_dev_before_m"]["p90"], rep["chord_dev_after_m"]["p90"]))
    # 5b house edge: one vertex outside each protected footprint
    ring = ndimage.binary_dilation(prot, iterations=1) & ~prot
    rep["house_edge_abs_delta_m"] = _q(np.abs(D[ring]) / 100.0)
    # the step at the wall: ring vertex vs the mean of its protected (unchanged) neighbours, before vs after;
    # gate = how much the flatten WORSENED it
    k3 = np.ones((3, 3))
    pn = ndimage.convolve(prot.astype(np.float64), k3, mode="constant")
    zp = ndimage.convolve(np.where(prot, Z, 0.0), k3, mode="constant") / np.maximum(pn, 1.0)
    st0, st1 = np.abs(Z - zp)[ring], np.abs(Zq - zp)[ring]
    rep["house_edge_step_before_m"], rep["house_edge_step_after_m"] = _q(st0 / 100.0), _q(st1 / 100.0)   # audit D4
    rep["house_edge_step_worsened_m"] = _q((st1 - st0) / 100.0)
    nh = int(((st1 - st0) > float(cfg["house_edge_step_max_m"]) * 100.0).sum())
    if not ring.any() or nh:
        fails.append("gate 5b: %d house-edge steps worsen by more than house_edge_step_max_m" % nh)
    # 5c bank: ground the flatten made STEEPER than bank_max_deg (a removed spike lowers slope; a raw
    # |grad delta| counted it as a 68 deg edit -- LESSONS 2026-10-10hh)
    sy0, sx0 = np.gradient(Z, px)
    sy1, sx1 = np.gradient(Zq, px)
    s0 = np.degrees(np.arctan(np.hypot(sx0, sy0)))
    s1 = np.degrees(np.arctan(np.hypot(sx1, sy1)))
    bm = float(cfg["bank_max_deg"])
    # a NEW bank: ground at or under bank_max before, over it after. Ground already steeper than bank_max that the
    # shoulder steepens further is reported, not gated (12 vertices, worst 33.4 -> 39.2 deg, on the first real run).
    made = (s1 > bm) & (s0 <= bm) & (s1 > s0 + 1.0)
    rep["vertices_made_steeper_than_bank"] = int(made.sum())
    st = (s0 > bm) & (s1 > s0 + 1.0)
    rep["already_steep_vertices_steepened"] = int(st.sum())
    if st.any():                                         # audit D3: the magnitude on the record, not only the count
        k = int(np.argmax(np.where(st, s1 - s0, -1e9)))
        rep["already_steep_worst_deg"] = [round(float(s0.flat[k]), 1), round(float(s1.flat[k]), 1)]
    rep["slope_increase_on_changed_deg"] = _q((s1 - s0)[changed])
    if made.any():
        fails.append("gate 5c: %d vertices made steeper than bank_max_deg %.0f (worst %.1f -> %.1f deg)"
                     % (int(made.sum()), float(cfg["bank_max_deg"]), float(s0[made][np.argmax((s1 - s0)[made])]),
                        float(s1[made][np.argmax((s1 - s0)[made])])))
    # 6 consumers on changed ground
    thr = float(cfg["changed_threshold_cm"])
    on = np.abs(D) >= thr

    def hit(x, y):
        i, j = int(round((x - X[0]) / px)), int(round((y - Y[0]) / px))
        return 0 <= i < n and 0 <= j < n and bool(on[j, i])
    rdoc = json.load(io.open(os.path.join(REPO, REMOVED), encoding="utf-8"))
    removed = rdoc["removed"]
    fol = {}
    import glob
    live_plans = {os.path.relpath(f, REPO).replace("\\", "/")
                  for f in glob.glob(os.path.join(REPO, "foliage", "alpine_8k_*.json"))}
    for k in sorted(set(removed) - live_plans):      # audit R2: an absent plan is not a verified one
        fails.append("gate 6: %s is in the town clearance record but not on disk" % k)
    for f in sorted(glob.glob(os.path.join(REPO, "foliage", "alpine_8k_*.json"))):
        rel = os.path.relpath(f, REPO).replace("\\", "/")
        # audit F2: the removed INDICES are only meaningful against the plan bytes they were taken from
        want = (rdoc.get("plans_sha16") or {}).get(rel)
        if rel in removed and want != _sha(f)[:16]:
            fails.append("gate 6: %s changed since the town clearance record (plans_sha16 %s) -- its removed "
                         "indices cannot be applied" % (rel, want))
        gone = set(removed.get(rel, []))
        inst = json.load(io.open(f, encoding="utf-8")).get("instances") or []
        k = sum(1 for i, r in enumerate(inst) if i not in gone and hit(r[0], r[1]))
        fol[rel] = {"instances": len(inst), "on_changed_ground": k}
    enc = json.load(io.open(os.path.join(REPO, VERIFIED_ENC), encoding="utf-8"))["encounters"]
    wat = json.load(io.open(os.path.join(REPO, WATER), encoding="utf-8"))
    wpts = [(p["cx"], p["cy"]) for s in wat["surfaces"] for p in s["planes"]] + [(f["cx"], f["cy"]) for f in wat["falls"]]
    rep["consumers_on_changed_ground"] = {
        "foliage": fol, "foliage_total": sum(v["on_changed_ground"] for v in fol.values()),
        "foliage_instances_checked": sum(v["instances"] for v in fol.values()),
        "encounters": sum(1 for e in enc if hit(e["loc_cm"][0], e["loc_cm"][1])), "encounters_checked": len(enc),
        "water_centres": sum(1 for x, y in wpts if hit(x, y)), "water_checked": len(wpts)}
    if rep["consumers_on_changed_ground"]["foliage_instances_checked"] == 0 or not enc or not wpts:
        fails.append("gate 6: a consumer set was empty -- nothing to check (rule 13)")
    rep.update({"discs_detail": diag["discs"], "pieces_widened": diag["pieces_widened"],
                "max_shoulder_m": round(diag["max_shoulder_m"], 2)})
    return Hnew, rep, fails


def selftest():
    """Synthetic: a bump under a street is removed, a house is untouched, and a gate-2 mutation is caught by the
    real gate (gate 5 is not mutation-tested here; the real run prints before/after counts)."""
    px = 100.0
    X = np.arange(0, 6000.0, px)
    Y = np.arange(0, 6000.0, px)
    GX, GY = np.meshgrid(X, Y)
    Z = 0.02 * GX + 60.0 * np.exp(-((GX - 3000) ** 2 + (GY - 3000) ** 2) / (2 * 300.0 ** 2))   # slope + 0.6 m bump
    cfg = {"sigma_m": 4.0, "shoulder_m": 3.0, "bank_max_deg": 30.0, "guard_m": 0.5, "house_fade_m": 1.0,
           "door_apron_m": 2.0}
    streets = [(3000.0, 3000.0, 4000.0, 600.0, 0.0)]
    houses = [(3000.0, 4200.0, 500.0, 400.0, 0.0)]
    door_edges = [(3000.0, 4000.0)]
    Zn, diag = flatten(Z, X, Y, streets, [], houses, door_edges, cfg)
    on = np.abs(GY - 3000) <= 300
    bump_before = float(np.abs(Z - 0.02 * GX)[on].max())
    bump_after = float(np.abs(Zn - 0.02 * GX)[on].max())
    ok = bump_after < 0.5 * bump_before
    ok &= gate_houses(Zn, Z, diag["prot"]) is None
    Zm = Zn.copy(); Zm[diag["prot"]] += 1.0
    caught = gate_houses(Zm, Z, diag["prot"]) is not None          # the REAL gate must refuse the mutation
    ok &= caught
    print("SELFTEST %s (bump %.1f -> %.1f cm under the street; house vertices %d untouched; mutation caught %s)"
          % ("PASSED" if ok else "FAILED", bump_before, bump_after, diag["protected_vertices"], caught))
    return 0 if ok else 4


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--init-prestreets", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rec = json.load(io.open(RECIPE, encoding="utf-8"))
    live = os.path.join(REPO, rec["heightmap"]["source"])
    sf = (rec.get("heightmap") or {}).get("street_flatten") or {}
    if a.init_prestreets:
        pre = os.path.join(REPO, sf.get("pre_source") or "")
        if not sf.get("pre_source"):
            raise SystemExit("REFUSE: declare heightmap.street_flatten.pre_source first")
        if os.path.exists(pre):
            raise SystemExit("REFUSE: %s exists -- re-basing prestreets is a deliberate act, not an init"
                             % sf["pre_source"])
        shutil.copyfile(live, pre)
        print("copied %s -> %s; sha256 %s (put it in pre_source_sha256)" % (rec["heightmap"]["source"],
                                                                            sf["pre_source"], _sha(pre)))
        return 0
    cfg = load_cfg(rec)
    pre = os.path.join(REPO, cfg["pre_source"])
    if not os.path.isfile(pre) or _sha(pre) != cfg["pre_source_sha256"]:
        raise SystemExit("REFUSE: %s missing or its sha256 != heightmap.street_flatten.pre_source_sha256"
                         % cfg["pre_source"])
    H16 = np.asarray(Image.open(pre))
    if H16.ndim != 2 or H16.dtype != np.uint16:
        raise SystemExit("REFUSE: pre_source is not single-channel uint16")
    Hnew, rep, fails = run(rec, cfg, H16)
    Hnew2, _, _ = run(rec, cfg, H16)
    if not np.array_equal(Hnew, Hnew2):
        fails.append("gate 7: two runs differ")
    print(json.dumps(rep, indent=1))
    for f in fails:
        print("  FAIL " + f)
    os.makedirs(os.path.dirname(os.path.join(REPO, REPORT)), exist_ok=True)
    rep_doc = dict(rep, fails=fails, cfg={k: cfg[k] for k in KEYS}, write=bool(a.write))
    json.dump(rep_doc, io.open(os.path.join(REPO, REPORT), "w", encoding="utf-8"), indent=1)
    if fails:
        print("REFUSE: nothing written")
        return 4
    if not a.write:
        print("gates OK; dry run (pass --write)")
        return 0
    # overwrite guard (design review change 4)
    side_p = live + ".flatten.json"
    cur = _sha(live)
    last = json.load(io.open(side_p, encoding="utf-8")).get("out_sha256") if os.path.isfile(side_p) else None
    if cur not in (cfg["pre_source_sha256"], last):
        raise SystemExit("REFUSE: %s (sha %s) is neither pre_source nor this tool's last output -- it was edited "
                         "after the flatten; re-base prestreets deliberately instead of reverting that edit"
                         % (rec["heightmap"]["source"], cur[:12]))
    Image.fromarray(Hnew).save(live)
    out_sha = _sha(live)
    if not np.array_equal(np.asarray(Image.open(live)), Hnew):
        raise SystemExit("REFUSE: the written PNG does not read back equal")
    json.dump({"_produced_by": "scripts/flatten_streets.py", "pre_source": cfg["pre_source"],
               "pre_source_sha256": cfg["pre_source_sha256"], "out_sha256": out_sha,
               "inputs_sha16": {p: _sha(os.path.join(REPO, p))[:16] for p in (PLAN, MANIFEST)},
               "cfg": {k: cfg[k] for k in KEYS}, "report": REPORT},
              io.open(side_p, "w", encoding="utf-8"), indent=1)
    print("wrote %s (sha %s) + sidecar" % (rec["heightmap"]["source"], out_sha[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
