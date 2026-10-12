"""Refit the far-field layer colours WITH Rock's cavity/lichen/damp modulation (recipe formula),
against the same 6 baked cells as fit_layer_colors. Adopt into M_Alpine8K_HLODFar only if R2 rises.
Run from the repo root."""
import glob, io, json, re, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
W = np.asarray(Image.open('textures/alpine_8k_weights.png')).astype(np.float32) / 255.0
L = np.dstack([W, np.clip(1.0 - W.sum(axis=2), 0, 1)])
CV = np.asarray(Image.open('textures/alpine_8k_cavity.png').convert('RGB')).astype(np.float32) / 255.0
cav = json.load(io.open('recipes/alpine_8k.json', encoding='utf-8'))['material']['cavity']
def lerp(a, b, t):
    return a + (b - a) * t
def rock_mod(cv):
    m = np.ones(cv.shape[:2] + (3,), np.float32)
    for ch, block in ((0, cav), (1, cav['lichen']), (2, cav['damp'])):
        t = (cv[..., ch] * float(block['strength']))[..., None]
        m *= lerp(1.0, np.array(block['tint'], np.float32), t)
    return m
def lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
files = {'L2_X-4_Y2': glob.glob('_verify/lookdev/seams05/*BaseColor.png')[0]}
for f in glob.glob('_verify/lookdev/seams05/L2_*/*BaseColor.png'):
    files[f.replace('\\', '/').split('/')[-2]] = f
m = 8
rows = {False: [[], []], True: [[], []]}
for lab, f in files.items():
    i, j = map(int, re.match(r'L2_X(-?\d+)_Y(-?\d+)', lab).groups())
    a = lin(np.asarray(Image.open(f).convert('RGB').resize((508, 508), Image.BOX)).astype(np.float32))
    c0, r0 = (i * 50800 + 406400) // 100, (j * 50800 + 406400) // 100
    w = L[r0:r0 + 508, c0:c0 + 508][m:-m, m:-m]
    mod = rock_mod(CV[r0:r0 + 508, c0:c0 + 508][m:-m, m:-m])
    y = a[m:-m, m:-m]
    for use in (False, True):
        rows[use][0].append((w.reshape(-1, 5), mod.reshape(-1, 3)))
        rows[use][1].append(y.reshape(-1, 3))
out = {}
for use in (False, True):
    Y = np.vstack(rows[use][1])
    C = np.zeros((5, 3)); r2 = []
    for k in range(3):
        X = np.vstack([np.column_stack([w[:, 0], w[:, 1] * (md[:, k] if use else 1.0), w[:, 2], w[:, 3], w[:, 4]])
                       for w, md in rows[use][0]])
        c, *_ = np.linalg.lstsq(X, Y[:, k], rcond=None)
        C[:, k] = c
        r2.append(1 - ((Y[:, k] - X @ c) ** 2).sum() / ((Y[:, k] - Y[:, k].mean()) ** 2).sum())
    out[use] = (C, r2)
    print('cavity modulation' if use else 'plain            ', 'R2 per channel', ['%.4f' % x for x in r2],
          'n', len(Y))
names = ['Snow', 'Rock', 'Scree', 'ForestFloor', 'Grass']
C, r2 = out[True]
for nm, c in zip(names, C):
    print('  %-12s [%.4f, %.4f, %.4f]' % (nm, *c))
json.dump({'n_texels': int(len(Y)), 'cells': sorted(files),
           'r2_plain': [float(x) for x in out[False][1]], 'r2_cavity': [float(x) for x in r2],
           'layers_cavity': {nm: [round(float(v), 4) for v in c] for nm, c in zip(names, C)}},
          open('_verify/lookdev/seams05/layer_fit_cavity.json', 'w'), indent=1)
