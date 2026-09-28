"""AUTHORING TOOL — offline stamp-composition iteration. NOT pipeline code.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A scratch harness for ITERATING a terrain composition: its `build()` writes a
`stamps` block into a recipe from a filename-keyed list, runs the real
compositor, and `render()`s before/after at both scales. It exists because
composition is a design loop and the loop should be cheap. There is NO
`__main__` / argparse driver -- running the file bare only loads the
catalogue and exits; you edit a `composition` in place and call
`build()`/`render()` yourself. That is what "scratch harness" means.

**It is not part of the pipeline.** Nothing in `scripts/` calls it, no
recipe references it, and it must never appear in a recipe's ORDERED STEPS.
The committed composition lives in `recipes/alpine.json` → `stamps` and is
reproduced by `scripts/composite_stamps.py` alone. This file is how that
block was AUTHORED, not how it is applied — the leading underscore is the
marker for that distinction.

It REWRITES `recipes/alpine.json` in place. Treat it accordingly.

It is cheap PNG math. Nothing here touches the editor and nothing adopts
the result -- `stamps.output` is never `heightmap.source`, which the
recipe validator enforces.
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

# DERIVED, never hardcoded. An absolute path baked into a committed file is
# broken on every other machine, and silently wrong on this one the moment
# the repo moves. (It was hardcoded while this lived in the scratchpad; it
# should not have survived the copy into scripts/.)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

CAT = json.load(open('terrain/stampit_catalogue.json', encoding='utf-8'))
BY_FILE = {e['filename']: e for e in CAT['maps']}


def build(composition, tag):
    pls = []
    for c in composition:
        e = BY_FILE[c['file']]
        p = {
            "id": c['id'],
            "stamp_sha256": e['hash'],
            "centre_m": [float(c['x']), float(c['y'])],
            "size_m": float(c['size']),
            "rotation_deg": float(c.get('rot', 0.0)),
            "flip_x": bool(c.get('fx', False)),
            "flip_y": bool(c.get('fy', False)),
            "blend": c['blend'],
            "amplitude_m": float(c['amp']),
            "falloff": float(c.get('falloff', 0.4)),
            "falloff_shape": c.get('shape', 'chebyshev'),
            "opacity": float(c.get('opacity', 1.0)),
            "falloff_jitter": float(c.get('jit', 0.0)),
            "falloff_jitter_scale": float(c.get('jscale', 0.35)),
        }
        if c['blend'] == 'ADD':
            p['datum'] = c.get('datum', 'min')
        else:
            p['anchor_m'] = float(c['anchor'])
        pls.append(p)

    rec = json.load(open('recipes/alpine.json', encoding='utf-8'))
    rec['stamps'] = {
        "base": "terrain/alpine_heightmap.png",
        "output": "terrain/alpine_stamped.png",
        "catalogue": "terrain/stampit_catalogue.json",
        "allow_edge_clip": False,
        "placements": pls,
    }
    json.dump(rec, open('recipes/alpine.json', 'w', encoding='utf-8'), indent=2)
    open('recipes/alpine.json', 'a', encoding='utf-8').write('\n')

    r = subprocess.run([sys.executable, 'scripts/composite_stamps.py'],
                       capture_output=True, text=True)
    print(r.stdout[-2500:])
    if r.returncode != 0:
        print('COMPOSITE FAILED rc=%d' % r.returncode)
        print(r.stderr[-2000:])
        return False
    render(tag)
    return True


def hillshade(h, sp):
    gy, gx = np.gradient(h, sp)
    az, alt = np.radians(315.), np.radians(45.)
    sl = np.arctan(np.hypot(gx, gy)); asp = np.arctan2(-gx, gy)
    return (np.sin(alt) * np.cos(sl) +
            np.cos(alt) * np.sin(sl) * np.cos(az - asp)).clip(0, 1), \
           np.degrees(np.arctan(np.hypot(gx, gy)))


def bands(H):
    out = np.zeros(H.shape + (3,))
    cols = [(0, (0.30, 0.36, 0.24)), (400, (0.45, 0.42, 0.28)),
            (730, (0.48, 0.44, 0.40)), (1100, (0.72, 0.74, 0.78)),
            (1600, (0.97, 0.98, 1.00))]
    for i in range(len(cols) - 1):
        lo, c0 = cols[i]; hi, c1 = cols[i + 1]
        m = (H >= lo) & (H < hi)
        t = np.clip((H - lo) / max(hi - lo, 1e-6), 0, 1)[..., None]
        out = np.where(m[..., None], np.array(c0) * (1 - t) + np.array(c1) * t, out)
    return np.where((H >= cols[-1][0])[..., None], np.array(cols[-1][1]), out)


def render(tag):
    rec = json.load(open('recipes/alpine.json', encoding='utf-8'))
    ls = rec['landscape']; sp = ls['scale_xy_cm'] / 100.; zs = ls['z_scale_cm'] / 100.
    a = np.asarray(Image.open('terrain/alpine_heightmap.png')).astype(np.float64) / 65535. * zs
    b = np.asarray(Image.open('terrain/alpine_stamped.png')).astype(np.float64) / 65535. * zs
    N = 820
    out = []
    for h, name in ((a, 'BEFORE'), (b, 'AFTER')):
        hs, slope = hillshade(h, sp)
        S = np.asarray(Image.fromarray((hs * 255).astype(np.uint8)).resize((N, N), Image.BOX)).astype(np.float64) / 255.
        Hs = np.asarray(Image.fromarray((np.clip(h / zs, 0, 1) * 65535).astype(np.uint16)).resize((N, N), Image.BOX)).astype(np.float64) / 65535. * zs
        col = bands(Hs) * (0.35 + 0.75 * S[..., None])
        out.append((col, S, h, slope, name))
    sheet2_parts = []
    sheet = Image.new('RGB', (N * 2 + 30, N + 64), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, (col, S, h, slope, name) in enumerate(out):
        sheet.paste(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)),
                    (10 + i * (N + 10), 44))
        d.text((14 + i * (N + 10), 8), '%s   relief %.0f..%.0f m' % (name, h.min(), h.max()),
               fill=(240, 240, 250))
        d.text((14 + i * (N + 10), 24),
               'slope>=45 %.2f%%   >=50 %.2f%%   snow>=730m %.1f%%' % (
                   100 * (slope >= 45).mean(), 100 * (slope >= 50).mean(),
                   100 * (h >= 730).mean()),
               fill=(190, 200, 215))
    # DUAL SCALE (standing rule): the 2 km airship read is the whole map;
    # the ground read is a 2000 m crop through the inter-massif corridor.
    crop_c = (0, 400)   # world m, the traversal corridor
    cw = 2000.0
    px = int(cw / sp)
    cx = int((crop_c[0] + 4032.0) / sp); cy = int((crop_c[1] + 4032.0) / sp)
    x0 = max(0, cx - px // 2); y0 = max(0, cy - px // 2)
    for col, S, h, slope, name in out:
        sub = h[y0:y0 + px, x0:x0 + px]
        hs2, _ = hillshade(sub, sp)
        im = Image.fromarray((hs2 * 255).astype(np.uint8)).resize((N, N), Image.LANCZOS)
        sheet2_parts.append((im, name))
    # NB: '20260803' is a FIXED authoring-run label, not the render date --
    # a later run overwrites the same-tag file under that date. `tag` is the
    # only real differentiator; change it per iteration.
    p = '_verify/20260803_compose_%s.png' % tag
    sheet.save(p)
    print('wrote', p)
    if sheet2_parts:
        s2 = Image.new('RGB', (N * 2 + 30, N + 40), (18, 18, 22))
        d2 = ImageDraw.Draw(s2)
        for i, (im, name) in enumerate(sheet2_parts):
            s2.paste(im, (10 + i * (N + 10), 30))
            d2.text((14 + i * (N + 10), 8),
                    '%s  GROUND SCALE  2000 m crop @ corridor' % name,
                    fill=(240, 240, 250))
        p2 = '_verify/20260803_compose_%s_ground.png' % tag
        s2.save(p2); print('wrote', p2)
    for col, S, h, slope, name in out:
        print('  %-6s relief %.0f..%.0f  mean %.0f  slope>=45 %.3f%%  >=50 %.3f%%' % (
            name, h.min(), h.max(), h.mean(),
            100 * (slope >= 45).mean(), 100 * (slope >= 50).mean()))
