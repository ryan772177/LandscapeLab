"""lookdev_terrain.py -- reshape the look-rig terrain crop OFFLINE and judge it by
hillshade before anything touches the editor (terrain_erosion.hillshade's own
rule: look at the artefact before it goes downstream).

    python scripts/lookdev_terrain.py --iter t01 [--delump 0.7] [--ridged 14]
        [--strata 5] [--droplets 1500000] [--write]

Reads terrain/lookdev_crop_src.png (the PRISTINE crop of alpine_8k, created on
first run from terrain/lookdev_crop.png and never rewritten), applies, in order:

  delump    attenuate the 12-60 m band -- the 28 m synthetic "detail relief"
            that makes every slope a field of round bumps and every layer
            mask a field of blobs (LESSONS 2026-09-30g)
  ridged    ridged multifractal, amplitude in metres at the first octave,
            weighted by slope so flats stay flat and faces get crags
  strata    soft terracing of steep rock (bedding planes), amplitude in metres
  droplets  hydraulic droplet erosion (terrain_erosion.hydraulic_droplets):
            gullies, couloirs, fans

and writes _verify/lookdev/<iter>/hillshade_{before,after}.png + stats. With
--write it also writes terrain/lookdev_crop.png, the _stamped copy, the sidecar
hash, and textures/lookdev_weights.png derived from the NEW heights
(snow / rock / scree by the derive_layer_weights formulas; ForestFloor 0 --
the rig has no trees; Grass = remainder).

Heights are metres throughout: uint16 * 0.0390625 (z_scale_cm 256000 / 65535
... exactly 256000/512/128/100 per unit), 1 m per pixel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import terrain_erosion as te  # noqa: E402

M_PER_UNIT = 0.0390625
SRC = os.path.join(REPO, "terrain", "lookdev_crop_src.png")
CROP = os.path.join(REPO, "terrain", "lookdev_crop.png")
STAMPED = os.path.join(REPO, "terrain", "lookdev_crop_stamped.png")
SIDE = STAMPED + ".stamps.json"
WEIGHTS = os.path.join(REPO, "textures", "lookdev_weights.png")


def smoothstep(lo, hi, x):
    t = np.clip((x - lo) / np.maximum(hi - lo, 1e-9), 0.0, 1.0)   # lo/hi may be arrays (per-aspect snow line)
    return t * t * (3.0 - 2.0 * t)


def slope_deg(h):
    gy, gx = np.gradient(h)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def fbm_ridged(shape, rng, wavelength, octaves=5, gain=0.5, lac=2.0):
    """Ridged multifractal in [0, 1], first octave at `wavelength` px."""
    n = shape[0]
    out = np.zeros(shape, dtype=np.float64)
    amp, tot, wl = 1.0, 0.0, float(wavelength)
    prev = 1.0
    for _ in range(octaves):
        cells = max(2, int(round(n / wl)) + 2)
        g = rng.standard_normal((cells, cells))
        f = ndimage.zoom(g, n / (cells - 1.0), order=3)[:n, :n]
        # Normalise by SPREAD, not by the maximum: dividing by max left |f| near 0
        # almost everywhere, so every octave was ~1 and the field had no contrast
        # (t02 / t04: no crags visible).
        f = np.clip(f / (1.5 * f.std() + 1e-9), -1.0, 1.0)
        r = (1.0 - np.abs(f)) ** 2          # sharp crests where the noise crosses 0
        out += r * amp * prev
        prev = np.clip(r * 1.6, 0.0, 1.0)   # detail gathers on the crests
        tot += amp
        amp *= gain
        wl /= lac
    return out / tot


def scree_shape(h, scree, convex_m=0.0, cluster=0.0, seed=20261003):
    """Hero round 14b (Gemini rock critique, 2026-10-03). Two physical facts the
    slope/apron mask lacks, both identity at 0:

    convex_m > 0: loose rock cannot rest on a convex crest. convexity =
      h - blur(h, convex_m); scree fades to 0 over 0.5 -> 2.0 m of it. Kills the
      row of rocks on the skyline ridge.
    cluster in (0, 1]: rockfall gathers in FANS below gully mouths, not as an
      even film. fan = the gully map (concavity of the >40 deg cells) blurred
      downslope-agnostically by 15 m, normalised; plus 30 m value noise. scree is
      multiplied by lerp(1, clip(0.1 + 1.4*fan + 0.6*(noise-0.5), 0, 1), cluster),
      so density (which the grass system ties to weight) clusters with it.
    """
    out = scree
    if convex_m > 0.0:
        convex = h - ndimage.gaussian_filter(h, sigma=convex_m, mode="nearest")
        out = out * (1.0 - smoothstep(0.5, 2.0, convex))
    if cluster > 0.0:
        sl = slope_deg(h)
        gully = np.clip((ndimage.gaussian_filter(h, 6.0, mode="nearest") - h) / 4.0,
                        0.0, 1.0) * (sl > 40.0)
        fan = ndimage.gaussian_filter(gully, 15.0, mode="nearest")
        # Normalise by the p90 of fan ON SCREE texels: the global p99.5 sits on
        # the cliffs and crushed every scree texel to ~0 (first try: scree
        # 11.9% -> 3.5%, uniformly dim, no clusters).
        on = scree > 0.2
        ref = float(np.percentile(fan[on], 90)) if on.any() else 1.0
        fan = fan / max(ref, 1e-6)
        rng = np.random.default_rng(seed)
        noise = ndimage.zoom(rng.random((h.shape[0] // 30 + 2, h.shape[1] // 30 + 2)),
                             30, order=3)[:h.shape[0], :h.shape[1]]
        field = np.clip(0.15 + 0.85 * fan + 0.5 * (noise - 0.5), 0.0, 1.0)
        out = out * ((1.0 - cluster) + cluster * field)
    return out


def midridge(h, col, row, dir_deg, length_m, width_m, height_m, seed=20261004):
    """Hero round 23 (2026-10-03, Gemini 2nd critique, ruled by Ryan): a low
    grassy terrace/knoll band across the view -- the 'midground tier'. Centred
    at array (col, row), its LONG axis perpendicular to dir_deg (the view
    direction, degrees in array col/row space). Cross-section cos^2 over
    width_m; ends taper over 25% of length_m; height modulated +-30% by 40 m
    noise so the crest undulates. Returns the height DELTA (m); 0 everywhere
    when height_m == 0 (identity)."""
    if height_m == 0.0:
        return np.zeros_like(h)
    rr, cc = np.mgrid[0:h.shape[0], 0:h.shape[1]].astype(np.float64)
    a = np.radians(dir_deg)
    u = (cc - col) * np.cos(a) + (rr - row) * np.sin(a)        # along the view
    v = -(cc - col) * np.sin(a) + (rr - row) * np.cos(a)       # across the view
    cross = np.where(np.abs(u) < width_m / 2.0,
                     np.cos(np.pi * u / width_m) ** 2, 0.0)
    half = length_m / 2.0
    taper = 1.0 - smoothstep(half * 0.75, half, np.abs(v))
    rng = np.random.default_rng(seed)
    n = ndimage.zoom(rng.random((h.shape[0] // 40 + 2, h.shape[1] // 40 + 2)), 40,
                     order=3)[:h.shape[0], :h.shape[1]]
    return height_m * cross * taper * (0.7 + 0.6 * n)


def weights_from(h, snow_line=730.0, scree_apron_m=0.0, scree_convex_m=0.0,
                 scree_cluster=0.0):
    """R=snow G=rock B=scree A=forest_floor(0); grass = remainder. The same band
    logic as derive_layer_weights (snow line with aspect, slope gates).

    scree_apron_m > 0 (hero round 12, 2026-10-03): ALSO scree on ground below
    29 deg within that many metres of a >40 deg cell that is HIGHER -- the
    talus wedge at a cliff foot, which the 20-26 deg band alone never reaches
    (the hero-view cliff bases run straight from rock into flat meadow).
    Fades linearly to 0 at the apron's edge. 0 = the previous output exactly."""
    sl = slope_deg(h)
    gy, gx = np.gradient(h)
    aspect = np.arctan2(-gy, -gx)                      # downslope direction
    north = np.cos(aspect - np.pi / 2.0)               # +1 on north-facing (+y down the array = south)
    line = snow_line - 125.0 * north
    snow = smoothstep(line - 60.0, line + 60.0, h) * (1.0 - smoothstep(30.0, 40.0, sl))
    rock = smoothstep(29.0, 35.0, sl)
    steep = sl > 40.0
    near = ndimage.maximum_filter(np.where(steep, h, -1e9), size=121)
    scree = smoothstep(20.0, 26.0, sl) * (1.0 - smoothstep(29.0, 35.0, sl)) * (near > h)
    if scree_apron_m > 0.0:
        dist = ndimage.distance_transform_edt(~steep)          # px == m on the rig
        reach = int(2 * scree_apron_m) + 1
        above = ndimage.maximum_filter(np.where(steep, h, -1e9), size=reach) > h
        apron = np.clip(1.0 - dist / float(scree_apron_m), 0.0, 1.0) * above \
            * (1.0 - smoothstep(29.0, 35.0, sl))
        scree = np.maximum(scree, apron)
    scree = scree_shape(h, scree, scree_convex_m, scree_cluster)
    rem = np.ones_like(h)
    out = []
    for w in (snow, rock, scree):
        w = np.clip(w, 0, 1) * rem
        out.append(w)
        rem = rem - w
    out.append(np.zeros_like(h))
    rgba = np.stack(out, axis=2)
    rgba = ndimage.gaussian_filter(rgba, sigma=(1.5, 1.5, 0))   # the recipe's feather
    cov = {k: float(rgba[..., i].mean()) for i, k in enumerate(("snow", "rock", "scree", "forest_floor"))}
    cov["grass"] = float(1.0 - rgba.sum(axis=2).mean())
    return (np.clip(rgba, 0, 1) * 255.0 + 0.5).astype(np.uint8), cov


def sha(path):
    m = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            m.update(b)
    return m.hexdigest()


_D8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def fluvial(h, iters, k, m=0.45, n=1.0, diffuse=0.0, talus_deg=0.0, a0=150.0, widen=0.0,
            jitter=0.06, seed=7, log=None):
    """Detachment-limited stream-power erosion: dz = k * A^m * S^n per pass.

    WHY THIS AND NOT MORE DROPLETS (2026-09-30g): droplets blur before they
    carve at 1 m cells (t03/t04 came out smooth). Stream power erodes in
    proportion to DRAINAGE AREA, so incision concentrates into a dendritic
    network -- gullies, couloirs and the sharp divides between them -- which
    is the signature the 2026-08-01 capture read said was missing.

    Each pass: fill pits (grey reconstruction), D8 receivers, drainage area by
    ONE sparse lower-triangular solve (cells ordered high to low, so every
    donor precedes its receiver), then incise, capped so a cell never drops
    below its receiver. Returns (h, area of the last pass).
    """
    from scipy import sparse
    from scipy.sparse.linalg import spsolve_triangular
    from skimage.morphology import reconstruction

    jitter_rng = np.random.default_rng(seed)
    ny, nx = h.shape
    N = ny * nx
    flat = np.arange(N).reshape(ny, nx)
    area = None
    for it in range(iters):
        seed = h.copy()
        seed[1:-1, 1:-1] = h.max()
        hf = reconstruction(seed, h, method="erosion")
        # D8 on a smooth slope routes along the grid axes (t06: horizontal
        # hatching on every gentle face). A few cm of per-pass jitter on the
        # ROUTING surface only breaks the alignment; h itself is not touched.
        hf = hf + jitter_rng.uniform(0.0, jitter, size=hf.shape)
        hp = np.pad(hf, 1, mode="constant", constant_values=np.inf)
        best = np.zeros_like(hf)
        rec = flat.copy()
        for dy, dx in _D8:
            nb = hp[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx]
            dist = 1.41421356 if (dy and dx) else 1.0
            drop = (hf - nb) / dist
            ok = np.isfinite(nb) & (drop > best)
            best = np.where(ok, drop, best)
            ridx = np.clip(np.arange(ny)[:, None] + dy, 0, ny - 1) * nx + np.clip(np.arange(nx)[None, :] + dx, 0, nx - 1)
            rec = np.where(ok, ridx, rec)
        order = np.argsort(-hf, axis=None, kind="stable")
        pos = np.empty(N, dtype=np.int64)
        pos[order] = np.arange(N)
        d = flat.ravel()
        r = rec.ravel()
        has = r != d
        M = sparse.csr_matrix((np.concatenate([np.ones(N), -np.ones(int(has.sum()))]),
                               (np.concatenate([np.arange(N), pos[r[has]]]),
                                np.concatenate([np.arange(N), pos[d[has]]]))), shape=(N, N))
        a_sorted = spsolve_triangular(M, np.ones(N), lower=True)
        area = a_sorted[pos].reshape(ny, nx)
        # CHANNEL THRESHOLD: below ~a0 m^2 of drainage a cell is hillslope, not
        # channel. Without it every cell cuts its own 1 px rill (t05: parallel
        # hatching everywhere, p90 slope 74 deg).
        chan = smoothstep(a0, a0 * 6.0, area)
        dz = k * chan * np.power(area, m) * np.power(best, n)
        h_rec = hf.ravel()[r].reshape(ny, nx)
        dz = np.minimum(dz, np.maximum(hf - h_rec, 0.0) * 0.85)
        if widen > 0:
            # spread each pass's incision sideways: V-shaped gullies instead of
            # 1 px slots (t06), with the eroded volume preserved by the blur
            dz = ndimage.gaussian_filter(dz, widen)
        # Incise the ORIGINAL surface, not the pit-filled one: writing hf back
        # turned every closed depression into a flat disc (t05).
        h = h - dz
        if talus_deg > 0:
            # one relaxation pass toward the angle of repose (thermal): move the
            # excess over the talus drop to the lower neighbour, 4-connected
            t = np.tan(np.radians(talus_deg))
            for ax in (0, 1):
                dd = np.diff(h, axis=ax)
                ex = np.clip(np.abs(dd) - t, 0.0, None) * 0.25 * np.sign(dd)
                if ax == 0:
                    h[:-1] += ex; h[1:] -= ex
                else:
                    h[:, :-1] += ex; h[:, 1:] -= ex
        if diffuse > 0:
            h = h + diffuse * ndimage.laplace(h, mode="nearest")
    if log is not None:
        log.append({"fluvial_iters": iters, "k": k, "m": m, "n": n, "area_max": float(area.max()) if area is not None else None})
    return h, area


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", required=True)
    ap.add_argument("--fluvial", type=int, default=0, help="stream-power passes")
    ap.add_argument("--fluvial-k", type=float, default=0.02)
    ap.add_argument("--fluvial-m", type=float, default=0.45)
    ap.add_argument("--talus", type=float, default=0.0, help="thermal relaxation angle, deg (0 = off)")
    ap.add_argument("--diffuse", type=float, default=0.0)
    ap.add_argument("--channel-area", type=float, default=150.0, help="drainage area (m^2) where channels begin")
    ap.add_argument("--jitter", type=float, default=0.06, help="routing-surface jitter, m")
    ap.add_argument("--widen", type=float, default=0.0, help="gaussian sigma (px) applied to each pass's incision")
    ap.add_argument("--delump", type=float, default=0.0, help="0..1 attenuation of the 12-60 m band")
    ap.add_argument("--ridged", type=float, default=0.0, help="ridged detail amplitude, m")
    ap.add_argument("--ridged-wavelength", type=float, default=90.0)
    ap.add_argument("--strata", type=float, default=0.0, help="terrace amplitude on steep rock, m")
    ap.add_argument("--strata-step", type=float, default=14.0)
    ap.add_argument("--droplets", type=int, default=0)
    ap.add_argument("--lifetime", type=int, default=90)
    ap.add_argument("--droplet-scale", type=float, default=200.0, help="metres per unit of the normalised droplet field")
    ap.add_argument("--erode", type=float, default=0.30)
    ap.add_argument("--deposit", type=float, default=0.30)
    ap.add_argument("--inertia", type=float, default=0.05)
    ap.add_argument("--drop-smooth", type=float, default=0.7)
    ap.add_argument("--capacity", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=20260930)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--snow-line", type=float, default=730.0,
                    help="snow line, m (aspect shifts it +-125 m)")
    ap.add_argument("--weights-only", action="store_true",
                    help="re-derive textures/lookdev_weights.png from the CURRENT "
                         "terrain/lookdev_crop.png; heights untouched")
    ap.add_argument("--scree-apron", type=float, default=0.0,
                    help="talus apron at cliff feet, m (0 = off; weights_from)")
    ap.add_argument("--scree-convex", type=float, default=0.0,
                    help="no scree on convex crests, blur sigma m (0 = off)")
    ap.add_argument("--scree-cluster", type=float, default=0.0,
                    help="0..1, cluster scree into fans below gullies (0 = off)")
    ap.add_argument("--cliffrelief", default=None,
                    help="amp_m,wavelength_m,slope_lo,slope_hi -- ridged ledge-scale relief on "
                         "the CURRENT crop, gated to rock slopes (needs --write to adopt)")
    ap.add_argument("--midridge", default=None,
                    help="col,row,dir_deg,length_m,width_m,height_m -- add a midground "
                         "terrace to the CURRENT crop (needs --write to adopt)")
    a = ap.parse_args()

    if a.midridge or a.cliffrelief:
        hc = np.asarray(Image.open(CROP)).astype(np.float64) * M_PER_UNIT
        if a.cliffrelief:
            # Hero round 27b (2026-10-03): the mountains read "melted" because the
            # heightfield has no sub-10 m ledges (LESSONS 2026-10-03x). Ridged
            # multifractal at ledge scale, gated to rock slopes; NOT terraces
            # (the 09-30 strata read as contour lines). Identity at amp 0.
            amp, wl, s_lo, s_hi = [float(x) for x in a.cliffrelief.split(",")]
            rng = np.random.default_rng(a.seed + 27)
            r = fbm_ridged(hc.shape, rng, wl, octaves=3)
            gate = smoothstep(s_lo, s_hi, slope_deg(hc))
            dh = amp * gate * (r - r.mean())
            col = row = ddeg = ln = wd = ht = 0.0
        else:
            col, row, ddeg, ln, wd, ht = [float(x) for x in a.midridge.split(",")]
            dh = midridge(hc, col, row, ddeg, ln, wd, ht)
        h2 = hc + dh
        out = os.path.join(REPO, "_verify", "lookdev", a.iter)
        os.makedirs(out, exist_ok=True)
        for name, arr in (("before", hc), ("after", h2)):
            hs = te.hillshade(arr, scale=float(arr.max() - arr.min()))
            Image.fromarray((np.clip(hs, 0, 1) * 255).astype(np.uint8)).resize(
                (1009, 1009), Image.LANCZOS).save(os.path.join(out, "hillshade_%s.png" % name))
        info = {"midridge": [col, row, ddeg, ln, wd, ht], "dh_max_m": float(dh.max()),
                "dh_area_m2_gt_0p5m": int((dh > 0.5).sum()), "crop_sha256_before": sha(CROP)}
        if a.write:
            u16 = np.clip(np.rint(h2 / M_PER_UNIT), 0, 65535).astype(np.uint16)
            Image.fromarray(u16).save(CROP)
            shutil.copyfile(CROP, STAMPED)
            rgba, cov = weights_from(h2, a.snow_line, a.scree_apron,
                                     a.scree_convex, a.scree_cluster)
            Image.fromarray(rgba, "RGBA").save(WEIGHTS)
            info.update(written=True, crop_sha256_after=sha(CROP), weights_coverage=cov)
        json.dump(info, open(os.path.join(out, "midridge.json"), "w"), indent=1)
        print(json.dumps(info))
        return 0

    if a.weights_only:
        hc = np.asarray(Image.open(CROP)).astype(np.float64) * M_PER_UNIT
        rgba, cov = weights_from(hc, a.snow_line, a.scree_apron,
                                 a.scree_convex, a.scree_cluster)
        Image.fromarray(rgba, "RGBA").save(WEIGHTS)
        out = os.path.join(REPO, "_verify", "lookdev", a.iter)
        os.makedirs(out, exist_ok=True)
        json.dump({"weights_only": True, "snow_line_m": a.snow_line,
                   "scree_apron_m": a.scree_apron,
                   "scree_convex_m": a.scree_convex,
                   "scree_cluster": a.scree_cluster,
                   "crop_sha256": sha(CROP), "weights_coverage": cov},
                  open(os.path.join(out, "weights.json"), "w"), indent=1)
        print("weights-only, snow line", a.snow_line,
              {k: round(v, 3) for k, v in cov.items()})
        return 0

    if not os.path.exists(SRC):
        shutil.copyfile(CROP, SRC)
    h0 = np.asarray(Image.open(SRC)).astype(np.float64) * M_PER_UNIT
    h = h0.copy()
    rng = np.random.default_rng(a.seed)
    log = {"args": vars(a), "steps": []}

    if a.delump > 0:
        # 28 / 14 / 7 m octaves: take everything between ~3 m and ~45 m (t02 with a
        # 4-20 sigma band left the pocking in place).
        band = ndimage.gaussian_filter(h, 1.2) - ndimage.gaussian_filter(h, 18.0)
        h = h - a.delump * band
        log["steps"].append({"delump": a.delump, "band_rms_m": float(band.std())})
    if a.ridged > 0:
        sl = slope_deg(ndimage.gaussian_filter(h, 6.0))
        gate = smoothstep(18.0, 38.0, sl)
        r = fbm_ridged(h.shape, rng, a.ridged_wavelength)
        h = h + a.ridged * gate * (r - r.mean())
        log["steps"].append({"ridged_m": a.ridged, "gate_mean": float(gate.mean())})
    if a.strata > 0:
        sl = slope_deg(ndimage.gaussian_filter(h, 3.0))
        gate = smoothstep(32.0, 48.0, sl)
        warp = ndimage.gaussian_filter(rng.standard_normal(h.shape), 60.0)
        warp = warp / (np.abs(warp).max() + 1e-9) * a.strata_step * 1.5   # beds are not level
        ph = (h + warp) / a.strata_step
        fr = ph - np.floor(ph)
        tread = smoothstep(0.0, 0.75, fr) - fr          # flat tread, steep riser
        h = h + gate * a.strata * tread * 2.0
        log["steps"].append({"strata_m": a.strata, "step_m": a.strata_step, "gate_mean": float(gate.mean())})
    area = None
    if a.fluvial > 0:
        h, area = fluvial(h, a.fluvial, a.fluvial_k, m=a.fluvial_m, diffuse=a.diffuse,
                          talus_deg=a.talus, a0=a.channel_area, widen=a.widen, jitter=a.jitter,
                          log=log["steps"])
    if a.droplets > 0:
        # The droplet model is tuned for a NORMALISED field: fed metres it took
        # +2147 / -1344 m out of the crop (t01, 2026-09-30). Run it on h / scale.
        hn, flow, depo = te.hydraulic_droplets(h / a.droplet_scale, rng, count=a.droplets,
                                               lifetime=a.lifetime, erode_rate=a.erode,
                                               capacity_factor=a.capacity, deposit_rate=a.deposit,
                                               inertia=a.inertia, smooth=a.drop_smooth)
        h = hn * a.droplet_scale
        depo = depo * a.droplet_scale
        log["steps"].append({"droplets": a.droplets, "flow_max": float(flow.max()), "depo_max_m": float(depo.max())})
    h = np.clip(h, 0.0, 65535 * M_PER_UNIT)

    d = h - h0
    sl0, sl1 = slope_deg(h0), slope_deg(h)
    log["delta_m"] = {"min": float(d.min()), "max": float(d.max()), "rms": float(d.std())}
    log["slope_deg_p50_p90_p99"] = {"before": [float(np.percentile(sl0, p)) for p in (50, 90, 99)],
                                    "after": [float(np.percentile(sl1, p)) for p in (50, 90, 99)]}
    out = os.path.join(REPO, "_verify", "lookdev", a.iter)
    os.makedirs(out, exist_ok=True)
    for name, arr in (("before", h0), ("after", h)):
        hs = te.hillshade(arr, scale=float(arr.max() - arr.min()))   # true slopes: 1 m cells, metres
        Image.fromarray((np.clip(hs, 0, 1) * 255).astype(np.uint8)).resize((1009, 1009), Image.LANCZOS).save(
            os.path.join(out, "hillshade_%s.png" % name))
    if a.write:
        u16 = np.clip(np.rint(h / M_PER_UNIT), 0, 65535).astype(np.uint16)
        Image.fromarray(u16).save(CROP)
        shutil.copyfile(CROP, STAMPED)
        json.dump({"output": "terrain/lookdev_crop_stamped.png", "output_sha256": sha(CROP),
                   "adopted_as": "terrain/lookdev_crop.png (byte copy)",
                   "provenance": "lookdev_terrain.py on terrain/lookdev_crop_src.png (the pristine crop, rows/cols "
                                 "3056..5072 of terrain/alpine_8k.png); steps in _verify/lookdev/%s/terrain.json" % a.iter,
                   "source": "terrain/lookdev_crop_src.png", "source_sha256": sha(SRC)}, open(SIDE, "w"), indent=1)
        # Pass EVERY weight argument: this call used to drop the scree apron /
        # convex / cluster shaping (rounds 12-17) on any terrain write.
        rgba, cov = weights_from(h, a.snow_line, a.scree_apron,
                                 a.scree_convex, a.scree_cluster)
        Image.fromarray(rgba, "RGBA").save(WEIGHTS)
        log["weights_coverage"] = cov
        log["written"] = True
    json.dump(log, open(os.path.join(out, "terrain.json"), "w"), indent=1, default=str)
    print(json.dumps({k: log[k] for k in ("delta_m", "slope_deg_p50_p90_p99")}, default=str))
    if a.write:
        print("weights", {k: round(v, 3) for k, v in log["weights_coverage"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
