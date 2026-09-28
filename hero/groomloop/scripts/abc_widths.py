"""abc_widths.py -- do the exported widths carry values, or zeros?

    blender --background --python this.py -- <a.abc> <b.abc> ...

The pointer audit found a SECOND silently-skipped attribute. Clay resolves
`att_groom_width` to its `radius` attribute and the exporter WRITES; DiffLocks
has the pointer empty and the exporter SKIPS.

`groom_width` is not an arb geom param -- it feeds the ICurves schema's own
`widths`, which is why the schema diff showed `widths` PRESENT on both files and
only flagged its LENGTH. Presence was never the question. `getAttributeArray`
returns early when the attribute is invalid (ExporterOperators.py:51-52), so a
skipped width leaves `out_widths` at whatever it was allocated with.

And a groom with zero width draws zero pixels -- that is the first line of
`validate_groom_export.py`'s own docstring.

Same mistake as root_uv, one field over: the diff reported a length and I read
it as "present and fine".
"""

import json
import sys

import numpy as np
from alembic.Abc import IArchive
from alembic import AbcGeom


def collect(path):
    rows = []

    def walk(o):
        for i in range(o.getNumChildren()):
            c = o.getChild(i)
            if AbcGeom.ICurves.matches(c.getMetaData()):
                sc = AbcGeom.ICurves(o, c.getName()).getSchema()
                row = {"object": c.getName()}
                w = sc.getWidthsParam()
                if not w.valid():
                    row["widths"] = "ABSENT"
                else:
                    v = w.getExpandedValue().getVals()
                    A = np.array([float(x) for x in v], dtype=np.float64)
                    row["widths"] = {
                        "n": int(A.size),
                        "min": round(float(A.min()), 8),
                        "mean": round(float(A.mean()), 8),
                        "max": round(float(A.max()), 8),
                        "all_zero": bool((A == 0.0).all()),
                        "zero_count": int((A == 0.0).sum()),
                        "unique": int(len(np.unique(np.round(A, 8))))}
                rows.append(row)
            else:
                walk(c)

    walk(IArchive(path).getTop())
    return rows


rep = {f: collect(f) for f in sys.argv[sys.argv.index("--") + 1:]}
print("__W__" + json.dumps(rep, default=str))
