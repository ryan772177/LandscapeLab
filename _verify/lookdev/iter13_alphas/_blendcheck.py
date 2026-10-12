import sys, os, numpy as np
from PIL import Image
it = sys.argv[1]
LUM = np.array([0.2126, 0.7152, 0.0722])
COL = np.array([0.839, 0.204, 0.220, 0.14, 0.047])     # Snow Rock Scree ForestFloor Grass, linear lum in engine
dec = lambda a: np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
w = np.asarray(Image.open("textures/lookdev_weights.png")).astype(np.float64) / 255
n = w.shape[0]
org = -(n - 1) / 2 * 100.0
n_ok = 0
spots = [("blend_a", -20400, 84800), ("blend_b", -73200, -17600), ("blend_c", -90500, 66700)]
for name, x, y in spots:
    p = "_verify/lookdev/%s/bc_%s.png" % (it, name)
    if not os.path.exists(p):
        print("%-8s NO FRAME" % name); continue
    px, py = int(round((x - org) / 100)), int(round((y - org) / 100))
    t = w[py - 4:py + 5, px - 4:px + 5].reshape(-1, 4)
    m = np.concatenate([t, np.clip(1 - t.sum(1, keepdims=True), 0, 1)], axis=1)
    wsum = float((m * COL).sum(1).mean())
    leak = float(np.prod(1 - m, axis=1).mean())
    chain = float(((m * COL) * np.stack([np.prod(1 - m[:, :i], axis=1) for i in range(5)], axis=1)).sum(1).mean()) + leak
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255
    h, ww = a.shape[:2]
    tile = a[int(h * 0.03):int(h * 0.21), int(ww * 0.02):int(ww * 0.235)].reshape(-1, 3)
    lum = float(dec(tile).mean(0) @ LUM)
    near = "WEIGHTED SUM" if abs(lum - wsum) < abs(lum - chain) else "RAW LERP CHAIN (background leaks)"
    n_ok += 1
    print("%-8s base colour %.3f   weighted sum %.3f   raw chain %.3f (background share %.3f)   -> %s   texels %d"
          % (name, lum, wsum, chain, leak, near, len(m)))
print("frames read: %d of %d" % (n_ok, len(spots)))
sys.exit(0 if n_ok == len(spots) else 1)
