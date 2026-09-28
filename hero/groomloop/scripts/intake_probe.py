"""intake_probe.py -- read a hand-authored .blend before anything is trusted.

    blender --background <in.blend> --python intake_probe.py

READ-ONLY. Reports every object, its type, its element count, and -- the point
of the exercise -- its TRANSFORM, because a groom that has been nudged in the
viewport seats wrong in a way that looks like a binding fault.

WHAT IT IS LOOKING FOR, and each item cost something once:

  MULTIPLE CLOUDS. A generate step run after an optimize step leaves two
  candidate point clouds in one file, and they are DIFFERENT DIFFUSION SAMPLES.
  Every object of type CURVES is listed with its counts so the lineage question
  is answered by reading rather than by assuming there is only one.

  A NON-IDENTITY TRANSFORM. Placement is owned by the registration -- the roots
  are snapped onto the hero's own face mesh and the root UVs read from it. A
  leftover viewport nudge silently offsets that whole solve.

  UNIFORM vs RAGGED point counts. The exporter and every restyle pass assume a
  uniform points-per-curve; a ragged cloud must be caught here, not three
  stages downstream.

  DEGENERATE CURVES. One-point curves crash the UE groom builder outright
  (Assertion failed: CurveNumVertices >= 2, GroomBuilder.cpp:2403).
"""

import json

import bpy
import numpy as np


def stats(ob):
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    P = buf.reshape(n, 3).astype(np.float64)
    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    out = {
        "curves": int(len(d.curves)), "points": n,
        "k_min": int(sizes.min()), "k_max": int(sizes.max()),
        "uniform_k": bool(sizes.min() == sizes.max()),
        "degenerate_lt2": int((sizes < 2).sum()),
        "attributes": sorted(a.name for a in d.attributes),
        "local_min": [round(float(v), 3) for v in P.min(0)],
        "local_max": [round(float(v), 3) for v in P.max(0)],
    }
    M = np.array(ob.matrix_world)
    W = P @ M[:3, :3].T + M[:3, 3]
    out["world_min"] = [round(float(v), 3) for v in W.min(0)]
    out["world_max"] = [round(float(v), 3) for v in W.max(0)]
    if out["uniform_k"]:
        k = int(sizes[0])
        A = P.reshape(-1, k, 3)
        L = np.linalg.norm(np.diff(A, axis=1), axis=2).sum(1)
        out["strand_len_mean"] = round(float(L.mean()), 4)
        out["strand_len_p10"] = round(float(np.percentile(L, 10)), 4)
        out["strand_len_p90"] = round(float(np.percentile(L, 90)), 4)
        out["strand_len_max"] = round(float(L.max()), 4)
    return out


def main():
    rep = {"file": bpy.data.filepath,
           "unit_scale": bpy.context.scene.unit_settings.scale_length,
           "length_unit": bpy.context.scene.unit_settings.length_unit,
           "objects": []}
    for ob in bpy.data.objects:
        M = ob.matrix_world
        ident = all(abs(M[r][c] - (1.0 if r == c else 0.0)) < 1e-6
                    for r in range(4) for c in range(4))
        row = {
            "name": ob.name, "type": ob.type,
            "identity_transform": bool(ident),
            "location": [round(v, 4) for v in ob.location],
            "rotation_euler": [round(v, 5) for v in ob.rotation_euler],
            "scale": [round(v, 5) for v in ob.scale],
            "parent": ob.parent.name if ob.parent else None,
            "modifiers": [m.type for m in ob.modifiers],
        }
        if ob.type == "CURVES":
            row.update(stats(ob))
        elif ob.type == "MESH":
            row["verts"] = len(ob.data.vertices)
        rep["objects"].append(row)
    print("__INTAKE__" + json.dumps(rep))


main()
