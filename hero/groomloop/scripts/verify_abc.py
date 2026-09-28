"""verify_abc.py -- the INTEGRITY GATE. Fresh session, re-import, compare.

    blender --background --python verify_abc.py -- <abc> <expect_json> <out_json>

Run in its own Blender invocation on purpose. Verifying an export inside the
session that produced it re-reads the objects still in memory, which is the
check-and-checked-share-a-source failure this project keeps paying for. A
fresh process can only see the FILE.

PASS requires, against the expectation file:
    curves  > 0
    curves  within 0.5% of expected
    bbox    every axis within 5% of expected

It reports attributes so the morning report can state which survived rather
than assert it. Exit code is 0 on pass and 7 on fail, so a caller can gate
without parsing.
"""

import json
import os
import sys

import bpy
import mathutils


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def main():
    tail = argv_tail()
    abc, expect_path, out = tail[0], tail[1], tail[2]

    rep = {"ok": False, "abc": abc, "checks": {}, "failures": []}
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    try:
        bpy.ops.wm.alembic_import(filepath=abc, as_background_job=False)
    except Exception as exc:
        rep["failures"].append("import raised: %s" % exc)
        _write(rep, out)
        sys.exit(7)

    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    if not curves:
        rep["failures"].append("no CURVES object after re-import")
        _write(rep, out)
        sys.exit(7)
    ob = curves[0]
    d = ob.data

    pts = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    got = {"curves": len(d.curves), "points": len(d.points),
           "attributes": sorted(a.name for a in d.attributes),
           "bbox_min": [round(min(p[i] for p in pts), 5) for i in range(3)],
           "bbox_max": [round(max(p[i] for p in pts), 5) for i in range(3)]}
    got["bbox_dims"] = [round(got["bbox_max"][i] - got["bbox_min"][i], 5)
                        for i in range(3)]
    rep["got"] = got

    exp = json.load(open(expect_path, encoding="utf-8"))
    rep["expected"] = exp

    if got["curves"] <= 0:
        rep["failures"].append("curve count is zero")
    if exp.get("curves"):
        drift = abs(got["curves"] - exp["curves"]) / float(exp["curves"])
        rep["checks"]["curve_drift"] = round(drift, 6)
        if drift > 0.005:
            rep["failures"].append(
                "curve count %d vs expected %d (%.2f%%)"
                % (got["curves"], exp["curves"], drift * 100))
    if exp.get("bbox_dims"):
        worst = 0.0
        for i, nm in enumerate("xyz"):
            e = exp["bbox_dims"][i]
            g = got["bbox_dims"][i]
            if e > 1e-9:
                dr = abs(g - e) / e
                worst = max(worst, dr)
                rep["checks"]["bbox_drift_%s" % nm] = round(dr, 6)
                if dr > 0.05:
                    rep["failures"].append(
                        "bbox %s %.5f vs expected %.5f (%.2f%%)"
                        % (nm, g, e, dr * 100))
        rep["checks"]["bbox_drift_worst"] = round(worst, 6)

    if exp.get("attributes"):
        lost = [a for a in exp["attributes"] if a not in got["attributes"]]
        rep["checks"]["attributes_lost"] = lost
        # Reported, NOT failed on: the export path dropping a name is a fact
        # for the UE checklist (set Hair Width by hand), not a reason to throw
        # away a geometrically sound candidate.
    rep["ok"] = not rep["failures"]
    _write(rep, out)
    sys.exit(0 if rep["ok"] else 7)


def _write(rep, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print("__VERIFY__" + json.dumps({"ok": rep["ok"],
                                     "failures": rep["failures"],
                                     "checks": rep.get("checks")}))


if __name__ == "__main__":
    main()
