"""root_uv_values.py -- are the root UVs that now exist actually CORRECT?

    blender --background --python this.py -- <a.abc> <b.abc> ...

The param is present and the groom still renders nothing. Presence was never the
claim worth making -- `land_difflocks.py` derives root UVs from a nearest-vertex
KDTree lookup into the head's active UV map, and a lookup into the WRONG map, or
one that collapses, produces a well-formed array of useless numbers. That binds
cleanly and renders nothing in exactly the same way an absent array does.

So this reads the distribution and puts it beside the groom that DRAWS. What
would convict them: everything outside [0,1], a near-zero unique fraction, a
degenerate range, or a distribution that does not resemble the working groom's.
What would acquit them: a spread comparable to the control.
"""

import json
import sys

import numpy as np
from alembic.Abc import IArchive, IArrayProperty
from alembic import AbcGeom


def collect(path):
    rows = []

    def walk(o):
        for i in range(o.getNumChildren()):
            c = o.getChild(i)
            if AbcGeom.ICurves.matches(c.getMetaData()):
                sc = AbcGeom.ICurves(o, c.getName()).getSchema()
                ag = sc.getArbGeomParams()
                names = [ag.getPropertyHeader(j).getName()
                         for j in range(ag.getNumProperties())] if ag.valid() \
                    else []
                if "groom_root_uv" not in names:
                    rows.append({"object": c.getName(),
                                 "groom_root_uv": "ABSENT"})
                    continue
                v = IArrayProperty(ag, "groom_root_uv").getValue()
                A = np.array([[p[0], p[1]] for p in v], dtype=np.float64)
                uniq = len(np.unique(np.round(A, 6), axis=0))
                rows.append({
                    "object": c.getName(),
                    "n": int(A.shape[0]),
                    "u": [round(float(A[:, 0].min()), 5),
                          round(float(A[:, 0].mean()), 5),
                          round(float(A[:, 0].max()), 5)],
                    "v": [round(float(A[:, 1].min()), 5),
                          round(float(A[:, 1].mean()), 5),
                          round(float(A[:, 1].max()), 5)],
                    "outside_0_1": int(((A < 0.0) | (A > 1.0)).any(1).sum()),
                    "nonfinite": int((~np.isfinite(A)).any(1).sum()),
                    "exactly_zero": int((A == 0.0).all(1).sum()),
                    "unique": uniq,
                    "unique_frac": round(uniq / max(1, A.shape[0]), 5),
                    "std": [round(float(A[:, 0].std()), 5),
                            round(float(A[:, 1].std()), 5)],
                })
            else:
                walk(c)

    walk(IArchive(path).getTop())
    return rows


rep = {f: collect(f) for f in sys.argv[sys.argv.index("--") + 1:]}
print("__UV__" + json.dumps(rep, default=str))
