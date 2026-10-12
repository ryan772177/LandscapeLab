import glob, json, re, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
W = np.asarray(Image.open('textures/alpine_8k_weights.png')).astype(np.float32) / 255.0
L = np.dstack([W, np.clip(1.0 - W.sum(axis=2), 0, 1)])
names = ['Snow', 'Rock', 'Scree', 'ForestFloor', 'Grass']
def lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
files = {'L2_X-4_Y2': glob.glob('_verify/lookdev/seams05/*BaseColor.png')[0]}
for f in glob.glob('_verify/lookdev/seams05/L2_*/*BaseColor.png'):
    files[f.replace('\\', '/').split('/')[-2]] = f
cells = []
for lab, f in files.items():
    i, j = map(int, re.match(r'L2_X(-?\d+)_Y(-?\d+)', lab).groups())
    img = Image.open(f).convert('RGB').resize((508, 508), Image.BOX)
    a = lin(np.asarray(img).astype(np.float32))
    c0, r0 = (i * 50800 + 406400) // 100, (j * 50800 + 406400) // 100
    cells.append((lab, a, L[r0:r0 + 508, c0:c0 + 508]))
def tf(a, k):
    a = np.rot90(a, k % 4)
    return np.fliplr(a) if k >= 4 else a
m = 8
best = None
for k in range(8):
    X, Y = [], []
    for lab, a, w in cells:
        aa = tf(a, k)[m:-m, m:-m].reshape(-1, 3)
        X.append(w[m:-m, m:-m].reshape(-1, 5)); Y.append(aa)
    X = np.vstack(X); Y = np.vstack(Y)
    C, res, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r2 = 1 - ((Y - X @ C) ** 2).sum() / ((Y - Y.mean(0)) ** 2).sum()
    if best is None or r2 > best[0]:
        best = (r2, k, C, len(X))
r2, k, C, n = best
print('best orientation k=%d  R2=%.3f  n=%d texels (%d cells)' % (k, r2, n, len(cells)))
for nm, c in zip(names, C):
    print('  %-12s linear [%.4f, %.4f, %.4f]' % (nm, *c))
json.dump({'orientation_k': k, 'r2': float(r2), 'n_texels': n, 'cells': list(files),
           'layers': {nm: [round(float(v), 4) for v in c] for nm, c in zip(names, C)}},
          open('_verify/lookdev/seams05/layer_fit.json', 'w'), indent=1)
