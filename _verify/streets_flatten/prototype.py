"""OFFLINE, READ-ONLY prototype (2026-10-10): how much ground would street flattening move, and where?

Writes only _verify/streets_flatten/prototype_<sigma>.json (+ a delta preview png). Never touches terrain/.

Target surface T (candidate design, not law):
  S      = natural heightmap H Gaussian-smoothed with sigma_m (removes bumps; keeps the long profile).
  piece  = every plan street: T at a vertex = S sampled at the vertex's projection onto the piece CENTRELINE
           (levelled across the width). Where pieces overlap, inverse-distance-to-centreline weighting.
           A side street's end lies on the main street's centreline, so both sample S at the same point there.
  disc   = plaza + squares: least-squares plane of H over the disc; inside a disc the plane wins.
  blend  = alpha 1 on the street/disc, smoothstep to 0 across shoulder_m outside it.
  houses = footprint + guard_m: alpha forced 0 (houses stand on traced ground; they are not moved).
Reports: changed vertices, |delta| distribution on streets, residual grade, the step left at house edges and
doorsteps, and the cross-street roll removed.
"""
import argparse, io, json, math, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigma-m", type=float, default=6.0)
    ap.add_argument("--shoulder-m", type=float, default=3.0)
    ap.add_argument("--guard-m", type=float, default=0.5)
    ap.add_argument("--mode", choices=("level", "smooth"), default="level",
                    help="level: S at the centreline projection (no cross-slope); smooth: S itself (keeps it)")
    ap.add_argument("--door-apron-m", type=float, default=0.0,
                    help="alpha fades to 0 within this radius of each doorstep point (door continuity)")
    a = ap.parse_args()
    rec = json.load(io.open(os.path.join(R, "recipes", "alpine_8k.json"), encoding="utf-8"))
    ls = rec["landscape"]
    ox, oy, oz = [float(v) for v in ls["location_cm"]]
    px, zs = float(ls["scale_xy_cm"]), float(ls["z_scale_cm"])
    H16 = np.asarray(Image.open(os.path.join(R, rec["heightmap"]["source"])))
    if H16.ndim != 2 or H16.dtype != np.uint16:
        sys.exit("REFUSE: heightmap not single-channel uint16 (%s %s)" % (H16.shape, H16.dtype))
    side = json.load(io.open(os.path.join(R, "textures", "alpine_8k_street_mask.png.json"), encoding="utf-8"))
    bx0, by0, bsz = side["box_cm"]
    c0, r0 = int((bx0 - ox) / px) - 20, int((by0 - oy) / px) - 20
    n = int(bsz / px) + 40
    Hc = H16[r0:r0 + n, c0:c0 + n].astype(np.float64)
    zcm = lambda h: oz + (h / 65535.0 - 0.5) * zs
    cm_per_unit = zs / 65535.0
    Z = zcm(Hc)                                           # world cm, row = y, col = x
    X = ox + (c0 + np.arange(n)) * px
    Y = oy + (r0 + np.arange(n)) * px
    S = ndimage.gaussian_filter(Z, a.sigma_m * 100.0 / px, mode="nearest")

    def s_at(x, y):                                       # bilinear S in world cm
        sc = np.ndim(x) == 0                              # map_coordinates refuses rank-0 coordinates
        fx = (np.atleast_1d(x) - X[0]) / px; fy = (np.atleast_1d(y) - Y[0]) / px
        v = ndimage.map_coordinates(S, [fy, fx], order=1, mode="nearest")
        return float(v[0]) if sc else v

    plan = json.load(io.open(os.path.join(R, "city", "alpine_basin_town_plan.json"), encoding="utf-8"))
    man = json.load(io.open(os.path.join(R, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    sh = a.shoulder_m * 100.0
    num = np.zeros_like(Z); den = np.zeros_like(Z)
    dmin = np.full(Z.shape, np.inf)
    roll_cm = []
    grade_deg = []
    for s in plan["streets"]:
        cx, cy = s["loc_cm"][0], s["loc_cm"][1]
        hx, hy = s["len_cm"] / 2.0, s["width_cm"] / 2.0
        ang = math.radians(s["yaw_deg"]); ca, sa = math.cos(ang), math.sin(ang)
        reach = math.hypot(hx, hy) + sh + 2 * px
        i0 = max(0, int((cx - reach - X[0]) / px)); i1 = min(n, int((cx + reach - X[0]) / px) + 2)
        j0 = max(0, int((cy - reach - Y[0]) / px)); j1 = min(n, int((cy + reach - Y[0]) / px) + 2)
        GX, GY = np.meshgrid(X[i0:i1], Y[j0:j1])
        lx = (GX - cx) * ca + (GY - cy) * sa
        ly = -(GX - cx) * sa + (GY - cy) * ca
        qx, qy = np.abs(lx) - hx, np.abs(ly) - hy
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
        sel = d <= sh
        t = np.clip(lx, -hx, hx)
        prof = s_at(cx + t * ca, cy + t * sa) if a.mode == "level" else S[j0:j1, i0:i1]
        w = 1.0 / (np.abs(ly) + 50.0)
        sl = (slice(j0, j1), slice(i0, i1))
        num[sl] += np.where(sel, w * prof, 0.0); den[sl] += np.where(sel, w, 0.0)
        dmin[sl] = np.minimum(dmin[sl], d)
        # roll removed: natural ground across the width at the piece centre
        zl0 = ndimage.map_coordinates(Z, [[(cy + hy * ca - Y[0]) / px], [(cx - hy * sa - X[0]) / px]], order=1)
        zr0 = ndimage.map_coordinates(Z, [[(cy - hy * ca - Y[0]) / px], [(cx + hy * sa - X[0]) / px]], order=1)
        roll_cm.append(float(abs(zl0[0] - zr0[0])))
        za, zb = s_at(cx - hx * ca, cy - hx * sa), s_at(cx + hx * ca, cy + hx * sa)
        grade_deg.append(math.degrees(math.atan(abs(float(zb - za)) / max(2 * hx, 1.0))))
    T = np.where(den > 0, num / np.maximum(den, 1e-12), Z)
    # discs: plane fit of Z over the disc
    cxp, cyp = plan["site_centre_cm"]
    discs = [(cxp, cyp, float(plan["plaza_radius_cm"]))] + [(x, y, r) for x, y, r in plan.get("squares", [])]
    GX, GY = np.meshgrid(X, Y)
    disc_rows = []
    for x, y, r in discs:
        dd = np.hypot(GX - x, GY - y) - r
        ins = dd <= 0
        A = np.c_[GX[ins] - x, GY[ins] - y, np.ones(int(ins.sum()))]
        coef, *_ = np.linalg.lstsq(A, Z[ins], rcond=None)
        P = coef[0] * (GX - x) + coef[1] * (GY - y) + coef[2]
        wdisc = np.where(dd <= 0, 1.0, np.clip(1.0 - dd / sh, 0.0, 1.0))   # 1 inside, 0 at the shoulder edge
        T = T + wdisc * (P - T)                           # T is Z wherever no street piece reached
        dmin = np.minimum(dmin, dd)
        disc_rows.append({"r_m": r / 100.0, "plane_slope_deg": round(math.degrees(math.atan(math.hypot(coef[0], coef[1]))), 2),
                          "max_abs_delta_m": round(float(np.abs(P - Z)[ins].max()) / 100.0, 3)})
    u = np.clip(1.0 - dmin / sh, 0.0, 1.0)
    alpha = np.where(dmin <= 0, 1.0, u * u * (3 - 2 * u))
    alpha[~np.isfinite(dmin)] = 0.0
    # houses protected
    prot = np.zeros(Z.shape, bool)
    gm = a.guard_m * 100.0
    door_pts = []
    for h in man["houses"]:
        cx, cy = h["loc_cm"][0], h["loc_cm"][1]
        hx, hy = h["W_cm"] / 2.0 + gm, h["D_cm"] / 2.0 + gm
        ang = math.radians(h["yaw_deg"]); ca, sa = math.cos(ang), math.sin(ang)
        lx = (GX - cx) * ca + (GY - cy) * sa; ly = -(GX - cx) * sa + (GY - cy) * ca
        prot |= (np.abs(lx) <= hx) & (np.abs(ly) <= hy)
        tx, ty = h["trace_local_xy"]                      # door-edge midpoint (local), step 1 m further out
        k = 1.0 + (gm + 100.0) / max(math.hypot(tx, ty), 1.0)
        dx, dy = tx * k, ty * k
        door_pts.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    alpha[prot] = 0.0
    if a.door_apron_m > 0:
        # door apron: alpha scaled by smoothstep(distance to the nearest door-edge midpoint / apron)
        ap_cm = a.door_apron_m * 100.0
        dd = np.full(Z.shape, np.inf)
        for h in man["houses"]:
            cx, cy = h["loc_cm"][0], h["loc_cm"][1]
            ang = math.radians(h["yaw_deg"]); ca, sa = math.cos(ang), math.sin(ang)
            tx, ty = h["trace_local_xy"]
            ex, ey = cx + tx * ca - ty * sa, cy + tx * sa + ty * ca
            i0 = max(0, int((ex - ap_cm - X[0]) / px)); i1 = min(n, int((ex + ap_cm - X[0]) / px) + 2)
            j0 = max(0, int((ey - ap_cm - Y[0]) / px)); j1 = min(n, int((ey + ap_cm - Y[0]) / px) + 2)
            sl = (slice(j0, j1), slice(i0, i1))
            dd[sl] = np.minimum(dd[sl], np.hypot(GX[sl] - ex, GY[sl] - ey))
        v = np.clip(dd / ap_cm, 0.0, 1.0)
        alpha *= v * v * (3 - 2 * v)
    Znew = Z + alpha * (T - Z)
    D = Znew - Z
    on_street = dmin <= 0
    # the OPEN item's own measurand: deviation of the street surface from the straight chord along each centreline,
    # every 0.5 m (plan_city street gate), BEFORE vs AFTER
    dev_old, dev_new = [], []
    for s in plan["streets"]:
        cx, cy = s["loc_cm"][0], s["loc_cm"][1]
        hx = s["len_cm"] / 2.0
        ang = math.radians(s["yaw_deg"]); ca, sa = math.cos(ang), math.sin(ang)
        t = np.linspace(-hx, hx, max(15, int(math.ceil(2 * hx / 50.0)) + 1))
        rr, cc = (cy + t * sa - Y[0]) / px, (cx + t * ca - X[0]) / px
        for arr, acc in ((Z, dev_old), (Znew, dev_new)):
            z = ndimage.map_coordinates(arr, [rr, cc], order=1)
            chord = z[0] + (z[-1] - z[0]) * (t + hx) / (2 * hx)
            acc.append(float(np.abs(z - chord).max()))
    ring = (~prot) & ndimage.binary_dilation(prot, iterations=1)
    dp = np.array(door_pts)
    ddoor = ndimage.map_coordinates(D, [(dp[:, 1] - Y[0]) / px, (dp[:, 0] - X[0]) / px], order=1)
    q = lambda v: {p: round(float(np.percentile(v, p)) / 100.0, 3) for p in (50, 90, 99)} | {"max": round(float(np.max(v)) / 100.0, 3)}
    out = {"_what": "street flattening PROTOTYPE measurement (read-only); see the docstring",
           "sigma_m": a.sigma_m, "shoulder_m": a.shoulder_m, "guard_m": a.guard_m,
           "vertices_changed_gt_1cm": int((np.abs(D) > 1.0).sum()),
           "street_vertices": int(on_street.sum()),
           "abs_delta_on_street_m": q(np.abs(D[on_street])),
           "cut_m_max": round(float(-D.min()) / 100.0, 3), "fill_m_max": round(float(D.max()) / 100.0, 3),
           "house_edge_step_m": q(np.abs(D[ring])),
           "doorstep_delta_m": q(np.abs(ddoor)), "doorsteps_over_0p3m": int((np.abs(ddoor) > 30).sum()),
           "houses": len(door_pts),
           "street_roll_natural_m": q(np.array(roll_cm)), "street_grade_after_deg": q(np.array(grade_deg) * 100.0),
           "discs": disc_rows,
           "centreline_dev_from_chord_before_m": q(np.array(dev_old)),
           "centreline_dev_from_chord_after_m": q(np.array(dev_new)),
           "pieces": len(dev_old),
           "height_quantum_cm": round(cm_per_unit, 4)}
    os.makedirs(os.path.join(R, "_verify", "streets_flatten"), exist_ok=True)
    out.update({"mode": a.mode, "door_apron_m": a.door_apron_m})
    tag = "s%g_sh%g_%s_ap%g" % (a.sigma_m, a.shoulder_m, a.mode, a.door_apron_m)
    json.dump(out, io.open(os.path.join(R, "_verify", "streets_flatten", "prototype_%s.json" % tag), "w", encoding="utf-8"), indent=1)
    v = np.clip(D / 100.0, -1.5, 1.5)
    img = np.zeros(D.shape + (3,), np.uint8)
    img[..., 0] = np.clip(-v / 1.5 * 255, 0, 255); img[..., 2] = np.clip(v / 1.5 * 255, 0, 255)
    img[..., 1] = np.where(prot, 90, 0)
    Image.fromarray(img[::-1]).save(os.path.join(R, "_verify", "streets_flatten", "prototype_%s_delta.png" % tag))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
