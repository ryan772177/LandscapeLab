"""Option A: split the forged church into FOUR material slots.

    blender --background --python scripts/blender/church_split.py -- \
        --in <fbx> --out <fbx> --report <json> --expect-up 0.9147 \
        --stone-frac 0.115 --copper-frac 0.80

RULED 2026-08-30 (option A, over the option-B Z-blend): a landmark justifies
real per-material parameters, and a blend cannot give the dome its own
roughness and normal behaviour.

⛔ THE UP AXIS IS MEASURED, NOT ASSUMED. The FBX round trip rotates -90 about
X: this mesh's up axis is **Y** in Blender, span 0.9147, with x=0.763 and
z=0.39494. The first profiling run read Z and measured 0.3949 -- a perfectly
plausible-looking number for a building lying on its side. Refuses if no axis
matches the expected span, and refuses if two do.

WHERE THE CUTS COME FROM -- THREE BY HEIGHT, ONE BY SLOPE
    stone   0 .. 0.115    the base course. Vertex DENSITY drops sharply here
                          (1998/1866/1682/1721/2235 per slice below, 637
                          above): a real geometric feature, not a number.
    copper  0.683 .. 1.0  the onion dome and its finial. MEASURED about the
                          TOWER's axis: neck at 0.683 (r_max 0.0600), bulge
                          peaking 0.750 (0.0769), taper to 0.817 (0.0413),
                          then collapse to the finial.
    roof    slope >= 0.55 inside the plaster range -- see below.
    plaster whatever is left.

⛔ THE FIRST COPPER EDGE WAS WRONG AND THE FRAME CAUGHT IT. It was set at 0.80
from r_max decline about the MESH centre, which is flat because the tower is
off-centre by 0.2550 -- distance-from-nave-centre swamps the dome's own
radius. That shipped copper on the FINIAL SPIKE ONLY with the dome still
plaster. Measured about the tower axis instead, the onion is unmistakable.
The lesson is not "check the dome"; it is that a radius is only meaningful
about the axis of the thing being measured.

Faces are assigned by CENTROID height, so a face never lands in two bands.
"""
import json
import os
import sys

import bpy   # noqa: E402


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = argv_after_ddash()
    src, dst, rep = get(args, "--in"), get(args, "--out"), get(args, "--report")
    eu = float(get(args, "--expect-up"))
    stone_f = float(get(args, "--stone-frac", "0.115"))
    copper_f = float(get(args, "--copper-frac", "0.80"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(meshes) != 1:
        raise SystemExit("expected 1 mesh, got %d" % len(meshes))
    ob = meshes[0]
    me = ob.data

    spans = {}
    for ax in (0, 1, 2):
        vals = [v.co[ax] for v in me.vertices]
        spans[ax] = (min(vals), max(vals), max(vals) - min(vals))
    scored = sorted(spans.items(), key=lambda kv: abs(kv[1][2] - eu))
    up = scored[0][0]
    if abs(scored[0][1][2] - eu) > 0.02 * eu:
        raise SystemExit("NO AXIS MATCHES up-span %.5f; refusing" % eu)
    if abs(scored[1][1][2] - eu) <= 0.02 * eu:
        raise SystemExit("AMBIGUOUS up axis; refusing")
    lo, hi = scored[0][1][0], scored[0][1][1]
    span = hi - lo
    z_stone = lo + span * stone_f
    z_copper = lo + span * copper_f

    # four slots, in a FIXED order the importer and the read-back agree on
    me.materials.clear()
    for name in ("M_Church_Stone", "M_Church_Plaster", "M_Church_Copper",
                 "M_Church_Roof"):
        me.materials.append(bpy.data.materials.new(name=name))

    # ⭐ THE ROOF IS NOT A HEIGHT BAND, AND CANNOT BE ONE.
    #
    # Stone, plaster and dome stack vertically, so height separates them. The
    # nave roof and the tower shaft occupy the SAME heights -- any horizontal
    # cut that catches the roof also catches the tower. What distinguishes a
    # roof is that it is SLOPED, so the fourth material is selected by FACE
    # NORMAL inside the existing plaster height range.
    #
    # The threshold is read off the measured distribution, not chosen
    # (church_normals.py, area-weighted, inside the plaster band):
    #
    #     0.00-0.05   42.91%   vertical walls, 89 deg -- the dominant mode
    #     0.25-0.60   <=1.01%  each: the TROUGH
    #     0.60-0.70   25.45%   48-51 deg -- the roof mode
    #
    # 0.55 sits in the trough, just below the roof mode.
    #
    # ⛔ SIGNED, not |n.up|. A deep eave's SOFFIT faces down with the same
    # steepness as the roof above it; on abs() it would come out shingled.
    # Only upward-facing slopes are roof.
    roof_min = float(get(args, "--roof-normal-min", "0.55"))
    counts = [0, 0, 0, 0]
    for poly in me.polygons:
        c = sum((me.vertices[i].co[up] for i in poly.vertices),
                0.0) / len(poly.vertices)
        if c < z_stone:
            idx = 0
        elif c >= z_copper:
            idx = 2
        elif poly.normal[up] >= roof_min:
            idx = 3
        else:
            idx = 1
        poly.material_index = idx
        counts[idx] += 1

    # ⛔ EVERY SLOT MUST RECEIVE FACES. An empty slot is a band edge that fell
    # outside the mesh, and it would import as a slot nothing can be assigned
    # to -- a silent no-op dressed as a three-material asset.
    if min(counts) == 0:
        raise SystemExit(
            "A BAND IS EMPTY: stone=%d plaster=%d copper=%d roof=%d. An "
            "empty slot is a cut that selected nothing, and it would import "
            "as a slot nothing can address -- a silent no-op dressed as a "
            "four-material asset."
            % (counts[0], counts[1], counts[2], counts[3]))

    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=dst, use_selection=True,
                             add_leaf_bones=False)

    out = {
        "source": os.path.basename(src), "out": os.path.basename(dst),
        "up_axis": "xyz"[up], "up_span": round(span, 5),
        "axis_spans": {"x": round(spans[0][2], 5), "y": round(spans[1][2], 5),
                       "z": round(spans[2][2], 5)},
        "band_fracs": {"stone": [0.0, stone_f],
                       "plaster": [stone_f, copper_f],
                       "copper": [copper_f, 1.0]},
        "band_edges_local": {"stone_top": round(z_stone, 5),
                             "copper_bottom": round(z_copper, 5)},
        "slots": [m.name for m in me.materials],
        "roof_normal_min": roof_min,
        "_roof_is_not_a_height_band": (
            "The roof is selected by FACE NORMAL inside the plaster height "
            "range, because the nave roof and the tower shaft occupy the same "
            "heights and no horizontal cut separates them. The threshold sits "
            "in the measured trough (0.25-0.60, <=1.01% area each) just below "
            "the roof mode (0.60-0.70, 25.45%). Signed, so eave soffits stay "
            "plaster."),
        "faces_per_slot": {"M_Church_Stone": counts[0],
                           "M_Church_Plaster": counts[1],
                           "M_Church_Copper": counts[2],
                           "M_Church_Roof": counts[3]},
        "faces_total": len(me.polygons),
        "_dome_caveat": (
            "The copper edge is read off r_max decline plus the concept's "
            "1.5/2.5 nave ratio, NOT off a radial dome inflection -- the "
            "tower is off-centre from the nave, so radius about the mesh "
            "centre mixes offset with local radius and shows no clean bulge. "
            "Defensible, not surveyed. The frame settles it."),
    }
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("__SPLIT__" + json.dumps({
        "slots": out["slots"], "faces": out["faces_per_slot"],
        "roof_normal_min": roof_min,
        "total": out["faces_total"], "up": out["up_axis"]}))


main()
