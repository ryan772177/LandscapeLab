"""cull_degenerate.py -- remove curves with fewer than 2 points, via the
supported operator path, then export.

    blender --background --python cull_degenerate.py -- <blend> <out_abc> <log>

WHY THIS IS MANDATORY, AND WHY THAT REVERSES AN EARLIER DECISION.
APPROACHES A1 marked the cull DEAD on the argument that the source .abc, with
all 1,210 of its one-point curves, had already imported into UE at full curve
count. That argument was about the VENDOR file. Importing OUR re-exported file
killed the editor outright:

    Assertion failed: CurveNumVertices >= 2
    GroomBuilder.cpp:2403

So Blender's exporter writes those degenerates in a form UE's groom builder
asserts on, whatever the vendor file did. New evidence, so the requirement is
un-killed -- which is the only sanctioned way to revive a dead approach.

WHY THE OPERATOR AND NOT A REBUILD. The first cull built a replacement Curves
with bpy.data.hair_curves.new + add_curves and crashed Blender with
EXCEPTION_ACCESS_VIOLATION; bpy.types.Curves in 5.2 exposes no supported
add/remove (recon/curves_api.json). bpy.ops.curves.delete DOES exist, operates
on the selection attribute, and is the path the UI itself uses.

IT ASSERTS ITS OWN RESULT. The curve count must drop by EXACTLY the number of
degenerates found, and no remaining curve may have fewer than 2 points. A cull
that silently removed the wrong strands would look identical in a render.
"""

import json
import os
import sys

import bpy
import numpy as np



import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pick_curves import pick_curves_object
def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def main():
    tail = argv_tail()
    blend, out_abc, log = tail[0], tail[1], tail[2]
    # EXPORT SCALE, DECLARED. Measured 2026-08-22: an export at 1.0 lands in UE
    # at 1/100 scale and at the origin (bounds 1.96 cm at z~1, against the
    # vendor file's 26.1 cm at z~151). Blender writes raw metres; UE reads them
    # as centimetres because the vendor .abc carries unit metadata Blender's
    # exporter does not write. 100.0 makes our export land exactly where the
    # vendor's does. This is a CONVERSION, not a styling transform, and it is
    # passed explicitly so it can never be a surprise.
    scale = float(tail[3]) if len(tail) > 3 else 1.0
    # RADIUS, WRITTEN EXPLICITLY. The source carries a constant radius of
    # 0.436611 for every point, which at this file's metre scale is a 44 cm
    # thick strand. global_scale multiplies it too, so a x100 export turns it
    # into 43.7 UE units and the groom renders as giant blocky ribbons --
    # measured in UE, not predicted.
    #
    # 0 keeps whatever the source had. A positive value is written in BLENDER
    # units before export, so the value that lands in UE is radius*scale: at
    # scale 100 a radius of 0.00018 gives 0.018 UE cm = 0.18 mm, which is the
    # width the Blender review renders used.
    radius = float(tail[4]) if len(tail) > 4 else 0.0
    # SEATING OFFSET, in BLENDER units, applied along the file's UP axis (-Y).
    #
    # This groom was authored on the PACK's head (SKM_MH_Groom_Head), not on
    # the hero's. Measured in UE: the hero's face mesh spans z 140.9-178.4
    # while this groom's ROOTS span 138.3-161.2 -- about 17 cm low. A binding
    # projects each root onto the nearest triangle of the target, so from 17 cm
    # below the scalp the nearest triangle is the JAW, which is exactly the
    # symptom every attempt has produced.
    #
    # This is a RETARGETING offset between two different heads, which is a
    # different thing from the round-trip fidelity rule -- that rule exists so
    # a transform never sneaks in unnoticed, and this one is passed explicitly,
    # recorded in the log, and asserted below.
    seat_cm = float(tail[5]) if len(tail) > 5 else 0.0
    rep = {"ok": False, "blend": blend, "out": out_abc, "export_scale": scale,
           "radius_written": radius, "seat_offset_cm": seat_cm}

    bpy.ops.wm.open_mainfile(filepath=blend)
    ob = pick_curves_object(bpy)
    d = ob.data

    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    bad = np.nonzero(sizes < 2)[0]
    rep["curves_before"] = int(len(sizes))
    rep["degenerate_found"] = int(bad.size)

    if bad.size:
        for o in bpy.data.objects:
            o.select_set(o is ob)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.curves.set_selection_domain(domain="CURVE")
        except Exception as exc:
            rep["set_domain_error"] = str(exc)
        try:
            bpy.ops.curves.select_all(action="DESELECT")
        except Exception as exc:
            rep["deselect_error"] = str(exc)

        sel = d.attributes.get(".selection")
        if sel is None:
            sel = d.attributes.new(".selection", "BOOL", "CURVE")
        buf = np.zeros(len(sizes), dtype=bool)
        buf[bad] = True
        try:
            sel.data.foreach_set("value", buf)
        except Exception:
            for i in bad:
                sel.data[int(i)].value = True
        rep["selected"] = int(buf.sum())

        bpy.ops.curves.delete()
        bpy.ops.object.mode_set(mode="OBJECT")

    d = ob.data
    sizes2 = np.array([c.points_length for c in d.curves], dtype=np.int64)
    rep["curves_after"] = int(len(sizes2))
    rep["still_degenerate"] = int((sizes2 < 2).sum())
    rep["removed"] = rep["curves_before"] - rep["curves_after"]

    # ASSERT THE RESULT, do not hope for it.
    if rep["still_degenerate"] != 0:
        rep["error"] = ("%d curves still have <2 points after the cull"
                        % rep["still_degenerate"])
        json.dump(rep, open(log, "w", encoding="utf-8"), indent=2)
        print("__CULL__" + json.dumps(rep))
        return
    if rep["removed"] != rep["degenerate_found"]:
        rep["error"] = ("removed %d but found %d degenerates -- the cull did "
                        "not remove the set it was given"
                        % (rep["removed"], rep["degenerate_found"]))
        json.dump(rep, open(log, "w", encoding="utf-8"), indent=2)
        print("__CULL__" + json.dumps(rep))
        return

    m = ob.matrix_world
    if not all(abs(m[r][c] - (1.0 if r == c else 0.0)) < 1e-9
               for r in range(4) for c in range(4)):
        rep["error"] = "transform is not identity; refusing to export"
        json.dump(rep, open(log, "w", encoding="utf-8"), indent=2)
        print("__CULL__" + json.dumps(rep))
        return

    if seat_cm != 0.0:
        # up is -Y in this file, so raising by S cm means y -= S/100 metres.
        dy = -seat_cm / 100.0
        n_pts = len(d.points)
        for attr in ("position", "handle_left", "handle_right"):
            at = d.attributes.get(attr)
            if at is None:
                continue
            buf = np.zeros(n_pts * 3, dtype=np.float32)
            at.data.foreach_get("vector", buf)
            arr = buf.reshape(n_pts, 3)
            arr[:, 1] += dy
            at.data.foreach_set("vector", arr.ravel())
        chk = np.zeros(n_pts * 3, dtype=np.float32)
        d.attributes["position"].data.foreach_get("vector", chk)
        rep["seated_root_z_min_ue"] = round(
            float(-chk.reshape(n_pts, 3)[:, 1].max()) * scale, 2)
        rep["seated_root_z_max_ue"] = round(
            float(-chk.reshape(n_pts, 3)[:, 1].min()) * scale, 2)

    if radius > 0:
        r = d.attributes.get("radius")
        if r is None:
            r = d.attributes.new("radius", "FLOAT", "POINT")
        n_pts = len(d.points)
        r.data.foreach_set("value", np.full(n_pts, radius, dtype=np.float32))
        chk = np.zeros(n_pts, dtype=np.float32)
        r.data.foreach_get("value", chk)
        rep["radius_readback"] = round(float(chk[0]), 8)
        if abs(float(chk[0]) - radius) > 1e-9:
            rep["error"] = "radius did not take: wrote %g read %g" % (
                radius, chk[0])
            json.dump(rep, open(log, "w", encoding="utf-8"), indent=2)
            print("__CULL__" + json.dumps(rep))
            return
        rep["radius_in_ue"] = round(radius * scale, 6)

    for o in bpy.data.objects:
        o.select_set(o is ob)
    bpy.context.view_layer.objects.active = ob
    os.makedirs(os.path.dirname(os.path.abspath(out_abc)), exist_ok=True)
    res = bpy.ops.wm.alembic_export(
        filepath=out_abc, check_existing=False, selected=True,
        flatten=False, curves_as_mesh=False, global_scale=scale,
        export_hair=True, export_particles=False,
        export_custom_properties=True, evaluation_mode="RENDER",
        as_background_job=False)
    rep["export_result"] = list(res)
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["attributes"] = [a.name for a in d.attributes]
    rep["ok"] = rep["bytes"] > 0
    json.dump(rep, open(log, "w", encoding="utf-8"), indent=2)
    print("__CULL__" + json.dumps(rep))


if __name__ == "__main__":
    main()
