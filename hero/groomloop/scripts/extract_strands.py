"""extract_strands.py -- bank an in-Blender hair cloud as a canonical npz.

    blender --background <in.blend> --python extract_strands.py -- <out.npz> <object>

WHY THE PAYLOAD IS EXTRACTED AT ALL. The AI panel's server deletes its output
directories on shutdown -- `outputs/.aihair_session.json` reads `{"dirs": []}`
and nothing was written outside the repo -- so an in-file cloud can be the ONLY
copy of a generation in existence. A generation is a diffusion sample and is
not reproducible: re-running the same prompt on the same image gives different
strands. So it is banked before anything else happens to it.

THE FRAME IS CONVERTED BACK, AND THAT IS THE WHOLE POINT OF THIS FILE.

`land_difflocks.py` applies `swap(p) = [x, -z, y]` to whatever npz it is given,
because the DiffLocks payload is Y-up in metres and Blender is Z-up. The AI
panel's IN-BLEND cloud has ALREADY had that swap applied by the addon --
measured against the v1 raw payload, whose axes line up under exactly that
permutation:

    v1 RAW npz   X [-0.110, 0.116]   Y [ 0.169, 0.442]   Z [-0.151, 0.127]
    v2 in-blend  X [-0.117, 0.118]   Y [-0.124, 0.152]   Z [ 0.169, 0.432]

Banking the in-blend coordinates directly would make the landing tool swap a
SECOND time, and a double swap is a 90-degree rotation -- the exact symptom
already seen once on this hero. So the inverse is applied here:

    raw = [blend_x, blend_z, -blend_y]

and the banked file is in the SAME convention as v1. One landing tool then
serves both versions, and the two payloads stay interchangeable inputs rather
than each needing its own special case.

The conversion is ASSERTED, not assumed: the round trip through swap() must
return the input.
"""

import json
import os
import sys

import bpy
import numpy as np


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_npz, obj_name = tail[0], tail[1]

    ob = bpy.data.objects.get(obj_name)
    if ob is None or ob.type != "CURVES":
        raise SystemExit("REFUSE: no CURVES object named %r (have: %s)"
                         % (obj_name, [o.name for o in bpy.data.objects]))

    M = np.array(ob.matrix_world)
    ident = np.allclose(M, np.eye(4), atol=1e-6)

    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    P = buf.reshape(n, 3).astype(np.float64)
    if not ident:
        # PLACEMENT IS OWNED BY THE REGISTRATION, so a viewport nudge is baked
        # out here rather than carried forward as a silent offset.
        P = P @ M[:3, :3].T + M[:3, 3]

    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    if sizes.min() != sizes.max():
        raise SystemExit("REFUSE: ragged cloud, k %d..%d -- every downstream "
                         "pass assumes uniform points-per-curve"
                         % (sizes.min(), sizes.max()))
    if (sizes < 2).any():
        raise SystemExit("REFUSE: %d curves under 2 points; UE asserts on "
                         "these (GroomBuilder.cpp:2403)" % int((sizes < 2).sum()))
    k = int(sizes[0])
    B = P.reshape(-1, k, 3)

    # blend -> raw, the inverse of land_difflocks' swap
    R = np.stack([B[..., 0], B[..., 2], -B[..., 1]], axis=-1)

    # ASSERT the inverse: swap(raw) must reproduce the blend coordinates.
    back = np.stack([R[..., 0], -R[..., 2], R[..., 1]], axis=-1)
    err = float(np.abs(back - B).max())
    if err > 1e-9:
        raise SystemExit("REFUSE: frame round trip is not exact, max err %g"
                         % err)

    np.savez_compressed(out_npz, positions=R.astype(np.float32))

    L = np.linalg.norm(np.diff(R, axis=1), axis=2).sum(1)
    rep = {
        "out": out_npz, "object": obj_name,
        "identity_transform": bool(ident),
        "transform_baked": bool(not ident),
        "strands": int(R.shape[0]), "points_per_strand": k,
        "frame": "raw DiffLocks (Y-up, metres) -- same convention as v1",
        "inverse_swap_max_err": err,
        "raw_min": [round(float(v), 4) for v in R.reshape(-1, 3).min(0)],
        "raw_max": [round(float(v), 4) for v in R.reshape(-1, 3).max(0)],
        "strand_len_m": {
            "mean": round(float(L.mean()), 5),
            "p10": round(float(np.percentile(L, 10)), 5),
            "p50": round(float(np.percentile(L, 50)), 5),
            "p90": round(float(np.percentile(L, 90)), 5),
            "max": round(float(L.max()), 5)},
        "bytes": os.path.getsize(out_npz),
    }
    print("__EXTRACT__" + json.dumps(rep))


main()
