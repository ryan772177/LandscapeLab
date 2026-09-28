"""root_uv_forensics.py -- which attribute does the EXPORTER read, and which did I write?

    blender --background --python this.py -- <blend> [<blend> ...]   (blends)
    blender --background --python this.py -- --abc <abc> [<abc> ...]  (files)

The ABC schema diff found `groom_root_uv` present in the groom that DRAWS and
ABSENT from the groom that does not. Both files carry a standard `uvs` param at
uniform scope with the right length, so this is not "no UVs" -- it is the
UE-specific NAMED arb geom param that UE's Alembic hair translator looks for.

Before that is believed, two things have to be true and neither has been read:

  1. the arb param really is absent, not merely mis-parsed by my dumper
  2. the BLENDER side explains it

Because there is a specific way I could have fooled myself. `land_difflocks.py`
and `resample_groom.py` both CREATE an attribute literally named
`groom_root_uv`, and `export_hero_groom.py` then REFUSES to export unless an
attribute named `groom_root_uv` exists. If the exporter actually reads Blender's
NATIVE hair attribute -- `surface_uv_coordinate` on the CURVE domain -- then my
hand-made attribute satisfies my gate and feeds the exporter nothing.

That would be non-negotiable 5 exactly: a check that consumes the value it is
verifying verifies nothing. The gate would be confirming my own naming
convention rather than the exporter's contract.
"""

import json
import sys

tail = sys.argv[sys.argv.index("--") + 1:]

if tail and tail[0] == "--abc":
    from alembic.Abc import IArchive
    from alembic import AbcGeom

    rep = {}

    def walk(o, acc):
        for i in range(o.getNumChildren()):
            c = o.getChild(i)
            if AbcGeom.ICurves.matches(c.getMetaData()):
                sc = AbcGeom.ICurves(o, c.getName()).getSchema()
                ag = sc.getArbGeomParams()
                names = []
                if ag.valid():
                    names = [ag.getPropertyHeader(j).getName()
                             for j in range(ag.getNumProperties())]
                acc.append({"object": c.getName(),
                            "arb_param_names": names,
                            "num_arb_params": len(names)})
            else:
                walk(c, acc)

    for f in tail[1:]:
        acc = []
        walk(IArchive(f).getTop(), acc)
        rep[f] = acc
    print("__RUV__" + json.dumps(rep))
    raise SystemExit(0)

import bpy

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])

rep = {}
for o in bpy.data.objects:
    if o.type != "CURVES":
        continue
    d = o.data
    attrs = {}
    for a in d.attributes:
        attrs[a.name] = {"domain": a.domain, "data_type": a.data_type,
                         "len": len(a.data)}
    rep[o.name] = {
        "curves": len(d.curves), "points": len(d.points),
        "attributes": attrs,
        # the two names that matter, asked separately so an absence is explicit
        "has_surface_uv_coordinate": "surface_uv_coordinate" in d.attributes,
        "has_groom_root_uv": "groom_root_uv" in d.attributes,
        "surface": getattr(d.surface, "name", None),
        "surface_uv_map": d.surface_uv_map,
    }
print("__RUV__" + json.dumps(rep))
