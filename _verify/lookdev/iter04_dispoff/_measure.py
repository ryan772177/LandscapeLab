import sys, os, numpy as np
from PIL import Image
it = sys.argv[1]
exp = {"Snow": 0.836, "Rock": 0.175, "Scree": 0.220, "Grass": None}
dec = lambda a: np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
n_ok = 0
for n, e in exp.items():
    p = "_verify/lookdev/%s/bc_%s.png" % (it, n)
    if not os.path.exists(p):
        print("%-6s NO FRAME" % n); continue
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255
    h, w = a.shape[:2]
    t = a[int(h * 0.03):int(h * 0.21), int(w * 0.02):int(w * 0.235)].reshape(-1, 3)
    lum = float(dec(t).mean(0) @ np.array([0.2126, 0.7152, 0.0722]))
    n_ok += 1
    if e is None:
        print("%-6s base colour linear %.3f   (source not on this machine; not judged)" % (n, lum))
    else:
        print("%-6s base colour linear %.3f   source %.3f   ratio %.2fx" % (n, lum, e, lum / e))
print("frames read: %d of %d" % (n_ok, len(exp)))
sys.exit(0 if n_ok == len(exp) else 1)
