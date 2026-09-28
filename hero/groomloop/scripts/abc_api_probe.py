"""abc_api_probe.py -- enumerate the PyAlembic surface before writing against it.

    blender --background --python this.py -- <some.abc>

An API remembered is an API guessed. PyAlembic's Python bindings are a thin,
undocumented wrapper and this project has already paid for
`get_inputs_for_material_function`, an accessor that read as knowledge and did
not exist. So the schema dumper is written from THIS output, not from memory.
"""

import sys

path = sys.argv[sys.argv.index("--") + 1]

from alembic.Abc import IArchive
from alembic import AbcGeom

print("__P__ AbcGeom top-level:",
      [a for a in dir(AbcGeom) if not a.startswith("_")])

ar = IArchive(path)
top = ar.getTop()
print("__P__ IObject:", [a for a in dir(top) if not a.startswith("_")])


def walk(o, d=0):
    for i in range(o.getNumChildren()):
        c = o.getChild(i)
        md = c.getMetaData()
        print("__P__ %s%s  schema=%s  ICurves=%s"
              % ("  " * d, c.getName(), md.get("schema"),
                 AbcGeom.ICurves.matches(md)))
        if AbcGeom.ICurves.matches(md):
            cu = AbcGeom.ICurves(o, c.getName())
            sc = cu.getSchema()
            print("__P__   ICurvesSchema:",
                  [a for a in dir(sc) if not a.startswith("_")])
            sm = sc.getValue()
            print("__P__   Sample:",
                  [a for a in dir(sm) if not a.startswith("_")])
            ag = sc.getArbGeomParams()
            print("__P__   ArbGeomParams:",
                  [a for a in dir(ag) if not a.startswith("_")])
            if ag.valid():
                for j in range(ag.getNumProperties()):
                    h = ag.getPropertyHeader(j)
                    print("__P__     hdr:", h.getName(),
                          [a for a in dir(h) if not a.startswith("_")])
                    break
            return
        walk(c, d + 1)


walk(top)
