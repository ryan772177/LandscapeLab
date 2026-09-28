"""Decimate the TRELLIS head for the conform solver.

472,734 vertices is not precision the conform needs -- it is a shape solve, not
a scan registration -- and every vertex crosses the Python binding one at a
time when the target array is built inside the editor. Decimating to a few tens
of thousands keeps the silhouette that matters and removes the cost that does
not.

Usage: decimate_head.py [TARGET_TRIS [SRC [DST]]]
Exits non-zero on any failure (bad/zero target, empty or unreadable source, a
degenerate result, decimation that did not reduce, or a write that did not
land); prints "DECIMATE OK" only on a verified success.
"""
import json
import os
import sys

import numpy as np
import open3d as o3d

SRC = sys.argv[2] if len(sys.argv) > 2 else "/opt/trellis/output/hero_head.ply"
DST = (sys.argv[3] if len(sys.argv) > 3
       else "/opt/trellis/output/hero_head_decimated.obj")
# Derived from DST so it can never silently diverge from the mesh it describes
# (defaults to hero_head_decimated.json, the previous hardcoded path).
META = os.path.splitext(DST)[0] + ".json"

try:
    TARGET_TRIS = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
except ValueError:
    print("ERROR: TARGET_TRIS must be an integer, got %r" % sys.argv[1])
    sys.exit(2)
if TARGET_TRIS <= 0:
    print("ERROR: TARGET_TRIS must be > 0, got %d" % TARGET_TRIS)
    sys.exit(2)

m = o3d.io.read_triangle_mesh(SRC)
v0, t0 = len(m.vertices), len(m.triangles)
print("source  verts %d  tris %d" % (v0, t0))
# NN13: open3d returns an EMPTY mesh (0/0) for a missing/unreadable file WITHOUT
# raising -- an empty source must fail, not be "decimated" to nothing and then
# crash on the extent reduction (or, worse, be reported OK).
if v0 == 0 or t0 == 0:
    print("ERROR: source mesh is empty or unreadable: %s" % SRC)
    sys.exit(1)

d = m.simplify_quadric_decimation(target_number_of_triangles=TARGET_TRIS)
d.remove_degenerate_triangles()
d.remove_duplicated_vertices()
d.remove_unreferenced_vertices()
v1, t1 = len(d.vertices), len(d.triangles)
print("decimated verts %d  tris %d  (target %d)" % (v1, t1, TARGET_TRIS))
# A decimation that collapsed to nothing is not a success.
if v1 == 0 or t1 == 0:
    print("ERROR: decimation produced an empty mesh (target %d too aggressive?)"
          % TARGET_TRIS)
    sys.exit(1)
# ...and one that did NOT reduce (well above target) means simplify did not take;
# cleanup only reduces, so the achieved count should be at or below the target.
if t1 > TARGET_TRIS * 1.5:
    print("ERROR: decimation left %d triangles, >1.5x the %d target -- it did "
          "not take" % (t1, TARGET_TRIS))
    sys.exit(1)

# Write, and VERIFY it landed: write_triangle_mesh returns False on failure
# without raising, so capture it AND read the triangle count back off disk (the
# round-trip is the persistence evidence, not the in-memory object).
if not o3d.io.write_triangle_mesh(DST, d):
    print("ERROR: write_triangle_mesh returned False for %s" % DST)
    sys.exit(1)
_chk = o3d.io.read_triangle_mesh(DST)
t_disk = len(_chk.triangles)
if t_disk == 0:
    print("ERROR: re-read of %s has 0 triangles; write did not persist" % DST)
    sys.exit(1)

a0 = np.asarray(m.vertices)
a1 = np.asarray(d.vertices)
meta = {
    "source": SRC, "output": DST,
    "target_triangles": TARGET_TRIS,
    "source_vertices": v0, "source_triangles": t0,
    "vertices": v1, "triangles": t1,
    "triangles_on_disk": t_disk,
    "source_extent": (a0.max(axis=0) - a0.min(axis=0)).tolist(),
    "extent": (a1.max(axis=0) - a1.min(axis=0)).tolist(),
}
# Extent REPORT (diagnostic, not a gate): if decimation moved the bounding box the
# shape changed, and this is a shape job -- surfaced for the reader to judge, not
# thresholded here (a hard tolerance is not calibrated).
meta["extent_change_pct"] = [
    round(100.0 * (meta["extent"][i] - meta["source_extent"][i])
          / max(1e-9, meta["source_extent"][i]), 3) for i in range(3)]
print(json.dumps(meta, indent=2))
with open(META, "w") as fh:
    json.dump(meta, fh, indent=2)
print("DECIMATE OK")
