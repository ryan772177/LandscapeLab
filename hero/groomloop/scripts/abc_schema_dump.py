"""abc_schema_dump.py -- read the ALEMBIC FILE, not the arrays inside it.

    blender --background --python this.py -- <a.abc> [<b.abc> ...]

WHY THIS AND NOT ANOTHER VALUE CHECK. Every probe so far has measured VALUES --
Blender's arrays going in, UE's properties coming out -- and every one of them
agrees between a groom that draws and a groom that does not. What no instrument
has read is the PAIRING of arrays to schema in the file itself: curve TYPE,
WRAP, BASIS, the nVertices topology array, and the SCOPE and length of every
geom param.

That matters because a wrong scope or an off-by-one topology array passes every
value read-back and still mis-strides the consumer. Corrupted curve topology
with pristine point positions is the one mechanism left that yields correct
bounds and zero strands, deterministically.

AND IT RE-GRADES AN OBSERVATION ALREADY ON THE BOARD. Blender's generic
`wm.alembic_import` reported "5 points per curve" for a file whose curves carry
28, and that was dismissed as a liar. A cubic-basis encoding is exactly the kind
of thing that makes a generic reader compute a different point count from the
same bytes. If the two files differ in `getType()`, that dismissal was wrong.

Reports every field; a field that RAISES is recorded as RAISED, never skipped,
because this dump is being used to eliminate suspects and "the accessor was not
there" must not read as "the value is absent".
"""

import json
import sys

from alembic.Abc import IArchive, IArrayProperty
from alembic import AbcGeom


def g(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return "RAISED: " + type(e).__name__


def gattr(obj, name, *a):
    """Attribute lookup AND call, both guarded.

    `g(o.getFoo)` evaluates the attribute BEFORE g() is entered, so a
    misremembered accessor raises AttributeError outside the guard -- which is
    how `getUsingVersion` took this script down on its first run. The wrapper
    that exists to make guessing safe cannot itself be reached by a guess.
    """
    fn = getattr(obj, name, None)
    if fn is None:
        return "ABSENT: no attribute " + name
    return g(fn, *a)


def sval(v):
    s = str(v)
    return s if len(s) < 90 else s[:90] + "..."


def dump_curves(parent, name):
    cu = AbcGeom.ICurves(parent, name)
    sc = cu.getSchema()
    sm = sc.getValue()
    out = {"name": name}

    out["schema"] = {
        "num_samples": gattr(sc, "getNumSamples"),
        "topology_variance": sval(gattr(sc, "getTopologyVariance")),
        "is_constant": gattr(sc, "isConstant"),
    }
    out["sample"] = {
        "type": sval(gattr(sm, "getType")),
        "wrap": sval(gattr(sm, "getWrap")),
        "basis": sval(gattr(sm, "getBasis")),
        "num_curves": gattr(sm, "getNumCurves"),
    }

    # -- the topology array. This is the one that mis-strides a consumer.
    nv = gattr(sm, "getCurvesNumVertices")
    if isinstance(nv, str):
        out["nVertices"] = nv
    else:
        vals = [int(x) for x in nv]
        out["nVertices"] = {"len": len(vals), "min": min(vals) if vals else None,
                            "max": max(vals) if vals else None,
                            "sum": sum(vals),
                            "first8": vals[:8]}

    P = gattr(sm, "getPositions")
    out["P_len"] = "RAISED" if isinstance(P, str) else len(P)
    if isinstance(out["nVertices"], dict) and isinstance(out["P_len"], int):
        out["topology_consistent"] = (out["nVertices"]["sum"] == out["P_len"])
        out["nVertices_len_vs_num_curves"] = (
            out["nVertices"]["len"] == out["sample"]["num_curves"])

    # optional curve properties that only a cubic/variable-order file carries
    for nm, fname in (("knots", "getKnotsProperty"),
                      ("orders", "getOrdersProperty"),
                      ("position_weights", "getPositionWeightsProperty"),
                      ("velocities", "getVelocitiesProperty"),
                      ("normals", "getNormalsParam"),
                      ("widths", "getWidthsParam"),
                      ("uvs", "getUVsParam")):
        p = gattr(sc, fname)
        if isinstance(p, str):
            out[nm] = p
            continue
        try:
            if not p.valid():
                out[nm] = "absent"
                continue
        except Exception:
            out[nm] = "absent"
            continue
        rec = {"present": True}
        try:
            rec["scope"] = sval(p.getScope())
        except Exception:
            try:
                rec["scope"] = p.getHeader().getMetaData().get("geoScope")
            except Exception:
                rec["scope"] = "RAISED"
        for k, f in (("data_type", "getDataType"), ("num_samples",
                                                    "getNumSamples")):
            try:
                rec[k] = sval(getattr(p, f)())
            except Exception:
                rec[k] = "RAISED"
        try:
            rec["len"] = len(p.getExpandedValue().getVals())
        except Exception:
            try:
                rec["len"] = len(p.getValue())
            except Exception:
                rec["len"] = "RAISED"
        out[nm] = rec

    # -- arbitrary geom params: name, scope, POD, length vs denominator
    ag = gattr(sc, "getArbGeomParams")
    params = []
    if not isinstance(ag, str) and ag.valid():
        for j in range(ag.getNumProperties()):
            h = ag.getPropertyHeader(j)
            rec = {"name": h.getName(),
                   "data_type": sval(gattr(h, "getDataType")),
                   "is_array": gattr(h, "isArray"),
                   "is_compound": gattr(h, "isCompound"),
                   "is_uv": gattr(h, "isUV")}
            try:
                rec["scope"] = h.getMetaData().get("geoScope")
            except Exception:
                rec["scope"] = "RAISED"
            try:
                rec["metadata"] = sval(h.getMetaData().serialize())
            except Exception:
                rec["metadata"] = "RAISED"
            # length: this is where an off-by-one topology hides
            try:
                if h.isCompound():
                    from alembic.Abc import ICompoundProperty
                    cp = ICompoundProperty(ag, h.getName())
                    rec["sub"] = [cp.getPropertyHeader(k).getName()
                                  for k in range(cp.getNumProperties())]
                    inner = IArrayProperty(cp, cp.getPropertyHeader(0).getName())
                    rec["len"] = len(inner.getValue())
                else:
                    rec["len"] = len(IArrayProperty(ag, h.getName()).getValue())
            except Exception as e:
                rec["len"] = "RAISED: " + type(e).__name__
            params.append(rec)
    out["arb_geom_params"] = params
    return out


def walk(o, acc):
    for i in range(o.getNumChildren()):
        c = o.getChild(i)
        md = c.getMetaData()
        if AbcGeom.ICurves.matches(md):
            acc.append(dump_curves(o, c.getName()))
        else:
            walk(c, acc)


def main():
    files = sys.argv[sys.argv.index("--") + 1:]
    rep = {}
    for f in files:
        ar = IArchive(f)
        acc = []
        walk(ar.getTop(), acc)
        rep[f] = {"alembic_version": gattr(ar, "getUsingVersion"),
                  "curve_objects": acc}
    print("__ABC__" + json.dumps(rep, default=str))


main()
