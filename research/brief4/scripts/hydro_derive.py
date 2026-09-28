#!/usr/bin/env python3
"""hydro_derive.py — lake basins, stream network and waterfall candidates from a heightmap.

Pure Python (numpy, scipy, scikit-image). Reads the desk's 4x export and its sidecar.
    python hydro_derive.py --png alpine_8k_height_4x_2033.png --json alpine_8k_height_4x.json --out outdir
Self-test: python hydro_derive.py --selftest
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import reconstruction

# D8 neighbour offsets (row, col) and step lengths in cell units
D8 = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
DL = np.array([1,2**.5,1,2**.5,1,2**.5,1,2**.5])

def fill_sinks(h, quantum=1e-4):
    """Priority-flood equivalent via grayscale reconstruction: fill every depression to its spill level."""
    seed = np.full_like(h, h.max())
    seed[0,:]=h[0,:]; seed[-1,:]=h[-1,:]; seed[:,0]=h[:,0]; seed[:,-1]=h[:,-1]
    hf = reconstruction(seed, h, method='erosion')
    # quantise: reconstruction leaves sub-1e-9 residues that turn spill cells into pits once flats are nudged
    return np.round(hf / quantum) * quantum

def resolve_flats(hf, eps=1e-9, max_iter=20000):
    """Nudge filled flats toward their exits with a geodesic distance inside the flat (BFS, 8-connected).
    Flat = no strictly lower neighbour. Exit seed = a draining cell adjacent to the flat at or below its level."""
    n, m = hf.shape; pad = np.pad(hf, 1, mode='edge')
    has_lower = np.zeros(hf.shape, bool)
    for dr, dc in D8:
        has_lower |= pad[1+dr:1+dr+n, 1+dc:1+dc+m] < hf
    has_lower[0,:]=has_lower[-1,:]=has_lower[:,0]=has_lower[:,-1]=True   # the border drains off-map
    flat = ~has_lower
    if not flat.any(): return hf
    st = np.ones((3,3), bool)
    # seeds: draining cells adjacent to a flat cell, not higher than that flat cell
    padf = np.pad(flat, 1); padh = pad
    seed = np.zeros(hf.shape, bool)
    for dr, dc in D8:
        nb_flat = padf[1+dr:1+dr+n, 1+dc:1+dc+m]; nb_h = padh[1+dr:1+dr+n, 1+dc:1+dc+m]
        seed |= has_lower & nb_flat & (hf <= nb_h)
    dist = np.zeros(hf.shape); reached = seed.copy(); todo = flat & ~reached
    def shifted(arr, dr, dc, fill):
        p = np.pad(arr, 1, constant_values=fill); return p[1+dr:1+dr+n, 1+dc:1+dc+m]
    for k in range(1, max_iter):
        grow = np.zeros(hf.shape, bool)
        for dr, dc in D8:   # grow only from a reached neighbour at or below this cell's level
            grow |= shifted(reached, dr, dc, False) & (shifted(hf, dr, dc, np.inf) <= hf)
        grow &= todo
        if not grow.any(): break
        dist[grow] = k; reached |= grow; todo &= ~grow
    if todo.any():
        raise RuntimeError("%d flat cells have no exit -- fill_sinks and resolve_flats disagree" % todo.sum())
    return hf + eps*dist

def d8_receivers(hf, cell_m):
    """Steepest-descent receiver index for each cell on the FILLED surface (flats resolved by a tiny gradient)."""
    n, m = hf.shape
    pad = np.pad(hf, 1, mode='edge')
    best = np.full(hf.shape, -1.0); rec = np.full(hf.shape, -1, dtype=np.int64)
    idx = np.arange(n*m).reshape(n,m)
    for k,(dr,dc) in enumerate(D8):
        nb = pad[1+dr:1+dr+n, 1+dc:1+dc+m]
        slope = (hf - nb) / (DL[k]*cell_m)
        better = slope > best
        best = np.where(better, slope, best)
        rr = np.clip(np.arange(n)[:,None]+dr, 0, n-1); cc = np.clip(np.arange(m)[None,:]+dc, 0, m-1)
        rec = np.where(better, idx[rr, cc], rec)
    rec[best <= 0] = -1          # pits with no lower neighbour
    rec[0, :] = rec[-1, :] = rec[:, 0] = rec[:, -1] = -1   # the border drains off-map: every border cell is an outlet (2026-09-16 fix — border cells used to collect laterally)
    return rec.ravel()

def receivers_and_order(hf, cell_m):
    hr = resolve_flats(hf)
    return d8_receivers(hr, cell_m), hr

def flow_accumulation(hf, rec):
    order = np.argsort(hf.ravel())[::-1]      # high to low
    acc = np.ones(hf.size, dtype=np.float64)
    r = rec[order]; valid = r >= 0
    # sequential accumulation (upstream cells are processed before downstream)
    for i, ri in zip(order[valid], r[valid]):
        acc[ri] += acc[i]
    return acc.reshape(hf.shape)

def lakes(h, hf, cell_m, min_depth_m=2.0, min_area_m2=4000.0):
    depth = hf - h
    wet = depth > 0.05
    lab, nlab = ndi.label(wet)
    out = []
    for i in range(1, nlab+1):
        mask = lab == i
        dmax = depth[mask].max()
        area = mask.sum() * cell_m**2
        if dmax < min_depth_m or area < min_area_m2: continue
        rr, cc = np.nonzero(mask)
        out.append(dict(id=i, surface_m=float(hf[mask].mean()), max_depth_m=float(dmax),
                        mean_depth_m=float(depth[mask].mean()), area_m2=float(area),
                        area_ha=float(area/1e4), centroid_col_row=[float(cc.mean()), float(rr.mean())],
                        bbox_col_row=[int(cc.min()), int(rr.min()), int(cc.max()), int(rr.max())],
                        volume_m3=float(depth[mask].sum()*cell_m**2)))
    out.sort(key=lambda d: -d['area_m2'])
    return out, lab, depth

def waterfalls(h, acc, rec, cell_m, min_acc_cells, min_drop_m=8.0, run_cells=3):
    """Channel cells where the ORIGINAL surface drops >= min_drop_m within run_cells downstream steps."""
    n, m = h.shape
    hr = h.ravel(); out = []
    chan = np.nonzero(acc.ravel() >= min_acc_cells)[0]
    for i in chan:
        j = i; drop = 0.0
        for _ in range(run_cells):
            if rec[j] < 0: break
            j = rec[j]
        drop = hr[i] - hr[j]
        if drop >= min_drop_m:
            out.append((i, drop))
    # keep local maxima along channels: suppress within 6 cells
    out.sort(key=lambda t: -t[1]); kept = []
    for i, drop in out:
        r, c = divmod(int(i), m)
        if all(abs(r-kr) > 6 or abs(c-kc) > 6 for kr, kc, _ in kept):
            kept.append((r, c, float(drop)))
    return kept

def hillshade(h, cell_m, az=315, alt=45):
    gy, gx = np.gradient(h, cell_m)
    slope = np.pi/2 - np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(az), np.radians(alt)
    hs = np.sin(alt)*np.sin(slope) + np.cos(alt)*np.cos(slope)*np.cos(az - aspect)
    return np.clip(hs, 0, 1)

def selftest():
    # bowl with a spillway: fill must reach exactly the spill height; flow must leave through the spill
    n = 61; y, x = np.mgrid[:n, :n]; h = ((x-30)**2 + (y-30)**2)/40.0
    h[30, 30:] = np.minimum(h[30, 30:], 5.0)        # notch to the east at 5 m
    h[:, -1] = -1; h[:, 0] = 40; h[0,:] = 40; h[-1,:] = 40
    hf = fill_sinks(h)
    assert abs(hf[30,30] - 5.0) < 1e-6, hf[30,30]
    rec, hr = receivers_and_order(hf, 1.0); acc = flow_accumulation(hr, rec)
    assert acc[30, n-2] > 1000, acc[30, n-2]          # basin drains through the notch
    L, _, _ = lakes(h, hf, 1.0, min_depth_m=1, min_area_m2=10)
    assert len(L) == 1 and abs(L[0]['surface_m'] - 5.0) < 1e-6
    print("selftest OK")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--png'); ap.add_argument('--json'); ap.add_argument('--out', default='out')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--min-lake-depth', type=float, default=2.0)
    ap.add_argument('--min-lake-area', type=float, default=4000.0)   # m² (0.4 ha)
    ap.add_argument('--stream-km2', type=float, default=1.0)        # contributing area to call it a stream
    ap.add_argument('--river-km2', type=float, default=6.0)
    a = ap.parse_args()
    if a.selftest: selftest(); return
    side = json.load(open(a.json)); cell = side['image']['metres_per_pixel']
    mpu = side['z_mapping']['metres_per_16bit_unit']; z0 = side['z_mapping']['height_m_of_unit_0']
    h = np.array(Image.open(a.png)).astype(np.float64)*mpu + z0
    os.makedirs(a.out, exist_ok=True)
    hf = fill_sinks(h)
    L, lab, depth = lakes(h, hf, cell, a.min_lake_depth, a.min_lake_area)
    rec, hr = receivers_and_order(hf, cell)
    acc = flow_accumulation(hr, rec)
    acc_km2 = acc * cell**2 / 1e6
    stream_cells = int(a.stream_km2*1e6/cell**2); river_cells = int(a.river_km2*1e6/cell**2)
    wf = waterfalls(h, acc, rec, cell, stream_cells)
    ox, oy = side['world_origin']['landscape_location_cm'][:2]
    def world(col, row): return [ox + col*cell*100, oy + row*cell*100]
    for l in L:
        l['centroid_world_cm'] = world(*l['centroid_col_row'])
        l['surface_world_z_cm'] = side['world_origin']['landscape_location_cm'][2] + l['surface_m']*100
    wfj = [dict(col_row=[c, r], drop_m=d, contributing_km2=float(acc_km2[r, c]), world_cm=world(c, r),
                elevation_m=float(h[r, c])) for r, c, d in wf]
    # network summary: main channel = max accumulation outlet trace
    out = dict(_what='Brief 4 hydrology derivation from the 4x heightmap', cell_m=cell,
               terrain_span_m=[float(h.min()), float(h.max())],
               lakes=L, n_lakes=len(L),
               stream_threshold_km2=a.stream_km2, river_threshold_km2=a.river_km2,
               stream_cells=int((acc_km2 >= a.stream_km2).sum()), river_cells=int((acc_km2 >= a.river_km2).sum()),
               stream_length_km=float((acc_km2 >= a.stream_km2).sum()*cell/1000),
               river_length_km=float((acc_km2 >= a.river_km2).sum()*cell/1000),
               max_contributing_km2=float(acc_km2.max()),
               outlet_col_row=[int(np.argmax(acc_km2) % h.shape[1]), int(np.argmax(acc_km2) // h.shape[1])],
               waterfalls=wfj, town_bbox_col_row=side['town_footprint']['bounding_box_col_row'])
    json.dump(out, open(os.path.join(a.out, 'hydro.json'), 'w'), indent=1)
    np.save(os.path.join(a.out, 'acc_km2.npy'), acc_km2.astype(np.float32))
    np.save(os.path.join(a.out, 'fill_depth_m.npy'), depth.astype(np.float32))
    # map
    hs = hillshade(h, cell)
    rgb = np.stack([hs]*3, -1)*0.85 + 0.1
    streams = acc_km2 >= a.stream_km2; rivers = acc_km2 >= a.river_km2
    rgb[streams] = [0.35, 0.65, 1.0]; rgb[rivers] = [0.05, 0.25, 0.95]
    for l in L:
        rgb[lab == l['id']] = [0.0, 0.45, 0.85]
    tb = side['town_footprint']['bounding_box_col_row']
    c0, r0 = map(int, tb['min_col_row']); c1, r1 = map(int, tb['max_col_row'])
    rgb[r0:r1, c0:c0+3] = rgb[r0:r1, c1-3:c1] = rgb[r0:r0+3, c0:c1] = rgb[r1-3:r1, c0:c1] = [1, 0.85, 0]
    for w in wfj:
        c, r = w['col_row']; rgb[max(r-4,0):r+5, max(c-4,0):c+5] = [1, 0.2, 0.2]
    Image.fromarray((rgb*255).astype(np.uint8)).save(os.path.join(a.out, 'hydro_map.png'))
    print(json.dumps({k: v for k, v in out.items() if k not in ('lakes', 'waterfalls')}, indent=1))
    for l in L[:12]:
        print(f"lake {l['id']:5d}  {l['area_ha']:7.1f} ha  surface {l['surface_m']:7.1f} m  maxdepth {l['max_depth_m']:5.1f}  col,row {l['centroid_col_row'][0]:.0f},{l['centroid_col_row'][1]:.0f}")
    print(f"{len(wfj)} waterfall candidates; top:")
    for w in wfj[:10]: print(f"  drop {w['drop_m']:5.1f} m  {w['contributing_km2']:5.2f} km2  col,row {w['col_row']}  elev {w['elevation_m']:.0f}")

if __name__ == '__main__': main()


# ---------------------------------------------------------------------------
# Brief 4 amendment (2026-09-16): reproducible proposals + the south-river pool ladder.
# Added so the lake_proposals and the ladder are produced by the tool of record, not by desk post-processing.
# ---------------------------------------------------------------------------
def trace_channel(rec, acc_cells, outlet_idx, thresh_cells, shape):
    """Walk UPSTREAM from an outlet cell along the max-accumulation tributary while acc >= thresh_cells.
    Returns the flat indices from outlet (first) to headwater (last)."""
    n, m = shape
    up = {}
    src = np.nonzero(rec >= 0)[0]
    for s, t in zip(src, rec[src]): up.setdefault(int(t), []).append(int(s))
    path = [int(outlet_idx)]; cur = int(outlet_idx)
    while True:
        cands = [c for c in up.get(cur, []) if acc_cells[c] >= thresh_cells]
        if not cands: break
        cur = max(cands, key=lambda c: acc_cells[c]); path.append(cur)
    return np.array(path)

def pool_ladder(h, hf, depth, lab, rec, acc, cell_m, outlet_col_row, thresh_km2=1.0, min_pool_depth_m=0.5, notch_m=1.0):
    """Chain-of-pools along one channel: every depression the channel crosses becomes a pool at its natural spill
    level (the filled surface), the downstream end of the flat is the lip, and a notch of notch_m is the only cut."""
    n, m = h.shape
    thresh_cells = int(thresh_km2 * 1e6 / cell_m ** 2)
    outlet = outlet_col_row[1] * m + outlet_col_row[0]
    path = trace_channel(rec, acc.ravel(), outlet, thresh_cells, h.shape)
    r, c = np.divmod(path, m)
    d = depth[r, c]; hr_ = h[r, c]; hf_ = hf[r, c]
    inpool = d >= min_pool_depth_m
    pools = []; i = 0; k = 0
    dist_along = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(r), np.diff(c)) * cell_m)])  # from outlet, metres
    while i < len(path):
        if not inpool[i]: i += 1; continue
        j = i
        while j + 1 < len(path) and inpool[j + 1]: j += 1
        seg = slice(i, j + 1)
        level = float(np.median(hf_[seg]))
        comp = lab[r[i], c[i]]
        mask = (lab == comp) & (depth > 0.05) if comp > 0 else np.zeros_like(lab, bool)
        area_ha = float(mask.sum() * cell_m ** 2 / 1e4)
        pools.append(dict(
            id=k, surface_m=round(level, 2), floor_m=round(float(hr_[seg].min()), 2), max_depth_m=round(float(d[seg].max()), 2),
            length_along_channel_m=round(float(dist_along[j] - dist_along[i]), 1), area_ha=round(area_ha, 2),
            lip_col_row=[int(c[i]), int(r[i])],            # downstream end of the flat = the spill
            head_col_row=[int(c[j]), int(r[j])],
            lip_elev_m=round(float(hr_[i]), 2), notch_m=notch_m, outlet_level_m=round(level - notch_m, 2),
            dist_from_outlet_m=round(float(dist_along[i]), 1), fill_lake_id=int(comp)))
        k += 1; i = j + 1
    route = [[int(cc), int(rr)] for rr, cc in zip(r, c)]
    profile = dict(length_m=round(float(dist_along[-1]), 1), head_elev_m=round(float(hr_[-1]), 2), outlet_elev_m=round(float(hr_[0]), 2),
                   cells=len(path), cells_in_pool=int(inpool.sum()),
                   full_carve_would_be=dict(mean_cut_m=round(float(d.mean()), 2), max_cut_m=round(float(d.max()), 2),
                                            cells_cut_over_2m=int((d > 2).sum())))
    total_notch = sum(p['notch_m'] for p in pools)
    return dict(channel='south_river', threshold_km2=thresh_km2, route_col_row=route, profile=profile,
                pools=pools, n_pools=len(pools), total_cut_m_chain_of_pools=round(total_notch, 1),
                waterfalls_by_construction=[dict(pool_id=p['id'], at_col_row=p['lip_col_row'],
                                                 drop_to_next_pool_m=round(p['surface_m'] - (pools[q + 1]['surface_m'] if q + 1 < len(pools) else profile['outlet_elev_m']), 2))
                                            for q, p in enumerate(pools)][::-1])

def level_slice(lab, h, lake_id, level_m, cell_m):
    mm = (lab == lake_id) & (h < level_m)
    l2, n2 = ndi.label(mm)
    if n2 == 0: return None
    sizes = ndi.sum(mm, l2, range(1, n2 + 1)); big = int(np.argmax(sizes)) + 1; pm = l2 == big
    rr, cc = np.nonzero(pm); shore = pm & ~ndi.binary_erosion(pm)
    return dict(area_ha=round(float(pm.sum() * cell_m ** 2 / 1e4), 1), max_depth_m=round(float(level_m - h[pm].min()), 1),
                mean_depth_m=round(float((level_m - h[pm]).mean()), 1), shoreline_km=round(float(shore.sum() * cell_m / 1000), 1),
                centroid_col_row=[round(float(cc.mean()), 1), round(float(rr.mean()), 1)],
                bbox_col_row=[int(cc.min()), int(rr.min()), int(cc.max()), int(rr.max())], mask=pm)

def selftest_ladder():
    # synthetic: a sloping valley with two bowls, walled borders, one outlet notch -> two pools at natural spill, notch cut only
    n = 80; y, x = np.mgrid[:n, :n]; h = 100 - 0.5 * y.astype(float) + 0.01 * (x - 40) ** 2 + 0.0003 * x
    for cy, dep in ((25, 4.0), (55, 6.0)):
        rr = np.hypot(x - 40, y - cy); h -= dep * np.clip(1 - rr / 5.0, 0, 1)
    hf = fill_sinks(h); depth = hf - h; lab, _ = ndi.label(depth > 0.05)
    rec, hr = receivers_and_order(hf, 1.0); acc = flow_accumulation(hr, rec)
    out = pool_ladder(h, hf, depth, lab, rec, acc, 1.0, [40, n - 1], thresh_km2=1e-6 * 30, min_pool_depth_m=0.5)
    assert out['n_pools'] == 2, out['n_pools']
    assert out['pools'][0]['surface_m'] < out['pools'][1]['surface_m'], 'downstream pool must be lower'
    assert out['total_cut_m_chain_of_pools'] == 2.0 and out['profile']['full_carve_would_be']['max_cut_m'] > 2
    print('ladder selftest OK')
