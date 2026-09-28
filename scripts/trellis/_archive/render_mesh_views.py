"""Rasterise orthographic depth views of a mesh with numpy only.

No GL, no display, no offscreen context to go wrong. Painter's algorithm over
vertices: nearest-wins per pixel, shaded by depth. Enough to answer the only
question being asked -- IS THIS A HEAD -- without adding a renderer dependency
to a stack that is already four substitutions deep.
"""
import sys
import numpy as np
import trimesh
from PIL import Image

src = sys.argv[1]
out = sys.argv[2]
S = 420

m = trimesh.load(src, process=False)
v = np.asarray(m.vertices, dtype=np.float64)
v = v - v.mean(axis=0)
v = v / np.abs(v).max()

# (axis_right, axis_up, axis_depth, flip_depth, label)
views = [
    (0, 2, 1, +1, "front"),
    (1, 2, 0, +1, "side"),
    (0, 1, 2, -1, "top"),
]

tiles = []
for ax_r, ax_u, ax_d, fd, label in views:
    img = np.zeros((S, S), dtype=np.float32)
    zbuf = np.full((S, S), -1e9, dtype=np.float64)

    x = v[:, ax_r]
    y = v[:, ax_u]
    z = v[:, ax_d] * fd

    px = ((x * 0.46 + 0.5) * (S - 1)).astype(np.int32)
    py = ((0.5 - y * 0.46) * (S - 1)).astype(np.int32)
    ok = (px >= 0) & (px < S) & (py >= 0) & (py < S)
    px, py, z = px[ok], py[ok], z[ok]

    order = np.argsort(z)
    px, py, z = px[order], py[order], z[order]
    zn = (z - z.min()) / max(1e-9, (z.max() - z.min()))
    img[py, px] = 0.25 + 0.75 * zn      # later writes (nearer) overwrite

    tiles.append((label, img))

W = S * len(tiles)
canvas = np.zeros((S, W), dtype=np.float32)
for i, (_lbl, img) in enumerate(tiles):
    canvas[:, i * S:(i + 1) * S] = img

Image.fromarray((canvas * 255).astype(np.uint8), mode="L").save(out)
print("wrote", out, "views:", ",".join(t[0] for t in tiles))
print("verts", v.shape[0])
