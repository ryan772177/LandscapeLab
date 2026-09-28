"""Crop the collar off the TRELLIS head and decimate it for the conform solver.

TWO PROBLEMS, ONE PASS.

CROP. The reconstruction includes the armour collar, because the reference
portraits frame head AND shoulders and cropping the INPUT IMAGE only reduced it.
The collar is why the three bounding-box scale estimates against the MetaHuman
archetype disagree by 2x -- 50.3 on width, 26.4 on depth, 37.4 on height -- and
it is geometry the face solver has no use for.

The neck is found by MEASUREMENT, not by a fraction anybody chose: slice the
mesh in Z, take the cross-sectional width of each slab, and the neck is the
narrowest slab between the head's widest slab and the collar's widest slab
below it. A head is wide, a neck is narrow, a collar is wider again.

DECIMATE. 472,734 vertices is not precision a shape solve needs, and every
vertex crosses the Python binding once when the target array is built inside the
editor -- the first conform attempt ran over ten minutes before it died.

Both steps REPORT what they changed to the bounding box (source, cropped and
decimated extents) so the silhouette can be judged -- a diagnostic report, not
a gate.
"""
import json
import os
import sys

import numpy as np
import open3d as o3d

SRC = "/opt/trellis/output/hero_head.ply"
DST = "/opt/trellis/output/hero_head_conform.obj"
# Derived from DST so the sidecar can never diverge from the mesh it describes
# (defaults to hero_head_conform.json, the previous hardcoded path).
META = os.path.splitext(DST)[0] + ".json"
try:
    TARGET_TRIS = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
except ValueError:
    print("ERROR: TARGET_TRIS must be an integer, got %r" % sys.argv[1])
    sys.exit(6)
if TARGET_TRIS <= 0:
    print("ERROR: TARGET_TRIS must be > 0, got %d" % TARGET_TRIS)
    sys.exit(6)
SLABS = 60

m = o3d.io.read_triangle_mesh(SRC)
v = np.asarray(m.vertices)
print("source verts %d tris %d" % (len(m.vertices), len(m.triangles)))
# NN13: open3d returns an EMPTY mesh (0/0) for a missing/unreadable file without
# raising; the extent reduction below would then crash on a zero-size array.
if len(m.vertices) == 0 or len(m.triangles) == 0:
    print("REFUSE: source mesh is empty or unreadable: %s" % SRC)
    sys.exit(5)
ext0 = v.max(axis=0) - v.min(axis=0)
print("source extent", np.round(ext0, 4).tolist())

# ---- find the neck by cross-sectional width per Z slab ----
zmin, zmax = float(v[:, 2].min()), float(v[:, 2].max())
edges = np.linspace(zmin, zmax, SLABS + 1)
widths, centres = [], []
for i in range(SLABS):
    sel = (v[:, 2] >= edges[i]) & (v[:, 2] < edges[i + 1])
    if sel.sum() < 20:
        widths.append(0.0)
        centres.append(0.5 * (edges[i] + edges[i + 1]))
        continue
    s = v[sel]
    # Width as the XY diagonal of the slab's extent: robust to which way the
    # head faces, which is not being assumed anywhere here.
    w = float(np.hypot(s[:, 0].max() - s[:, 0].min(),
                       s[:, 1].max() - s[:, 1].min()))
    widths.append(w)
    centres.append(0.5 * (edges[i] + edges[i + 1]))
widths = np.asarray(widths)
centres = np.asarray(centres)

top_half = np.arange(SLABS) >= SLABS // 2
head_i = int(np.argmax(np.where(top_half, widths, -1)))
below = np.arange(SLABS) < head_i
collar_i = int(np.argmax(np.where(below, widths, -1)))

print("widest head slab   i=%d z=%.4f width=%.4f" % (head_i, centres[head_i], widths[head_i]))
print("widest collar slab i=%d z=%.4f width=%.4f" % (collar_i, centres[collar_i], widths[collar_i]))

if collar_i >= head_i - 1:
    print("REFUSE: no collar found below the head; the neck test does not apply")
    sys.exit(2)

band = np.arange(SLABS)
mask = (band > collar_i) & (band < head_i)
neck_i = int(band[mask][np.argmin(widths[mask])])
z_cut = float(centres[neck_i])

# THE AUTOMATIC CUT WAS MEASURED TOO HIGH AND IS OVERRIDABLE.
# The head/neck width separation on this reconstruction is only 1.08, which is
# not enough signal for the narrowest-slab rule: it chose z=-0.1406 and took
# the CHIN AND JAW with the collar, which was visible the moment the cropped
# mesh was rendered (_verify/20260816_headtrack_plus_y.png -- the mesh ends
# below the mouth). Jaw shape is exactly what a face conform is fitting, so
# losing it is not a small loss.
#
# An explicit cut is honest here: the automatic rule is kept and reported, and
# a value chosen by LOOKING overrides it.
if len(sys.argv) > 2:
    z_cut = float(sys.argv[2])
    print("EXPLICIT z cut %.4f overrides the measured neck at %.4f"
          % (z_cut, float(centres[neck_i])))
print("NECK slab          i=%d z=%.4f width=%.4f" % (neck_i, z_cut, widths[neck_i]))
print("  head/neck width ratio %.2f  collar/neck %.2f"
      % (widths[head_i] / max(1e-9, widths[neck_i]),
         widths[collar_i] / max(1e-9, widths[neck_i])))

keep_v = v[:, 2] >= z_cut
print("keeping %d of %d vertices above the neck" % (int(keep_v.sum()), len(v)))
if keep_v.sum() < 1000:
    print("REFUSE: the crop kept almost nothing; refusing to ship it")
    sys.exit(3)

cropped = m.select_by_index(np.where(keep_v)[0])
cropped.remove_degenerate_triangles()
cropped.remove_duplicated_vertices()
cropped.remove_unreferenced_vertices()
# Keep only the largest connected piece: the crop can leave stray shards.
try:
    labels, counts, _ = cropped.cluster_connected_triangles()
    labels = np.asarray(labels)
    counts = np.asarray(counts)
    if counts.size > 1:
        biggest = int(np.argmax(counts))
        cropped.remove_triangles_by_mask(labels != biggest)
        cropped.remove_unreferenced_vertices()
        print("kept largest of %d connected pieces (%d tris)"
              % (counts.size, int(counts[biggest])))
except Exception as e:
    print("connected-component pass skipped:", type(e).__name__, e)

print("cropped verts %d tris %d" % (len(cropped.vertices), len(cropped.triangles)))
_ce = np.asarray(cropped.vertices)
if len(_ce):   # F6: the crop step reported only counts, not its extent
    print("cropped extent",
          np.round(_ce.max(axis=0) - _ce.min(axis=0), 4).tolist())

d = cropped.simplify_quadric_decimation(target_number_of_triangles=TARGET_TRIS)
d.remove_degenerate_triangles()
d.remove_duplicated_vertices()
d.remove_unreferenced_vertices()
print("decimated verts %d tris %d (target %d)"
      % (len(d.vertices), len(d.triangles), TARGET_TRIS))
# F1/NN13: a decimation that collapsed to nothing, or that did not reduce toward
# the target, is not a success -- guard BEFORE the write and before the extent
# reduction below (which would crash on a zero-size array).
if len(d.vertices) == 0 or len(d.triangles) == 0:
    print("REFUSE: decimation produced an empty mesh (target %d too aggressive?)"
          % TARGET_TRIS)
    sys.exit(4)
if len(d.triangles) > TARGET_TRIS * 1.5:
    print("REFUSE: decimation left %d triangles, >1.5x the %d target -- it did "
          "not take" % (len(d.triangles), TARGET_TRIS))
    sys.exit(4)
a = np.asarray(d.vertices)

# NO NORMALS IN THE OBJ, DELIBERATELY -- AND THIS REVERSES MY OWN "FIX".
#
# I added compute_vertex_normals() + write_vertex_normals=True believing that
# Unreal was computing per-FACE normals for a normal-less OBJ and that supplying
# smooth ones would fix the faceted render. IT IS THE OTHER WAY ROUND, measured:
# the run that TRACKED (16 curves) used an OBJ written WITHOUT normals, and
# every run after the normals were added rendered hard-edged facets.
#
# Unreal computes SMOOTH normals when an OBJ carries none. When it carries
# normals it honours them -- and open3d's decimation splits vertices, so its
# "vertex normals" are effectively per-face. Supplying them replaced Unreal's
# smoothing with faceting.
#
# The face tracker reads SHADING to find eyes, nose and lips, so this is not
# cosmetic: it is the difference between 16 curves and None.
# F2: verify the write landed -- write_triangle_mesh returns False on failure
# without raising; capture it, then read the triangle count back off disk.
if not o3d.io.write_triangle_mesh(DST, d, write_vertex_normals=False):
    print("REFUSE: write_triangle_mesh returned False for %s" % DST)
    sys.exit(4)
_chk = o3d.io.read_triangle_mesh(DST)
if len(_chk.triangles) == 0:
    print("REFUSE: re-read of %s has 0 triangles; write did not persist" % DST)
    sys.exit(4)

ext1 = a.max(axis=0) - a.min(axis=0)
meta = {
    "source": SRC, "output": DST,
    "target_triangles": TARGET_TRIS,
    "source_vertices": len(v), "vertices": int(len(d.vertices)),
    "triangles": int(len(d.triangles)),
    "triangles_on_disk": int(len(_chk.triangles)),
    "neck_z_cut": z_cut,
    "head_slab_width": float(widths[head_i]),
    "neck_slab_width": float(widths[neck_i]),
    "collar_slab_width": float(widths[collar_i]),
    "source_extent": ext0.tolist(),
    "extent": ext1.tolist(),
}
with open(META, "w") as fh:
    json.dump(meta, fh, indent=2)
print(json.dumps(meta, indent=2))
print("CROP+DECIMATE OK")
