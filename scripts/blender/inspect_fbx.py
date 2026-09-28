"""Headless FBX inspector: objects, triangle counts, materials, bounds.

Run:
    blender --background --factory-startup --python inspect_fbx.py -- <file>

EXTENDED 2026-08-02 (original by Ryan; the human table below is his and
is unchanged). Two additions, both needed by the asset-pipeline work:

  BOUNDING BOXES. Ruling 3 requires fir_tree_01's mesh_extent_m to be
  MEASURED from the file rather than sourced from a vendor page, and a
  measurement needs a number a caller can read, not a printed table.
  World-space dims are taken AFTER the object matrix is applied —
  bound_box is local space, and skipping the matrix would silently
  report a unit-cube extent for anything carrying a scale.

  MATERIALS ACTUALLY USED BY FACES, as opposed to merely present in the
  slot list. An unused slot reads as "this mesh needs that texture" and
  would answer the Stage 2 gate wrongly in the direction that costs
  most: claiming a dependency on a material whose textures do not ship.

A JSON block follows a marker so a caller parses a value instead of
scraping the table.
"""
import json
import sys

import bpy
import mathutils

MARKER = "__FBX_INSPECT_JSON__"

path = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)

if not hasattr(bpy.ops.wm, "fbx_import"):
    raise RuntimeError("bpy.ops.wm.fbx_import not present - check Blender version")

bpy.ops.wm.fbx_import(filepath=path)
print("importer: bpy.ops.wm.fbx_import")

total = 0
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

print("\n=== OBJECTS ===")
rows = []
for ob in meshes:
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total += tris
    mats = [m.name for m in me.materials] or ["<none>"]
    print(f"{ob.name:40s} {tris:>12,d} tris   verts={len(me.vertices):>10,d}   mats={mats}")

    corners = [ob.matrix_world @ mathutils.Vector(c) for c in ob.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    dims = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]

    used_idx = {p.material_index for p in me.polygons}
    used = sorted({me.materials[i].name for i in used_idx
                   if i < len(me.materials) and me.materials[i]})

    print(f"{'':40s} used-by-faces={used or ['<none>']}")
    print(f"{'':40s} dims={dims[0]:.4f} x {dims[1]:.4f} x {dims[2]:.4f}")

    rows.append({
        "object": ob.name,
        "tris": tris,
        "verts": len(me.vertices),
        "material_slots": mats,
        "materials_used_by_faces": used,
        "dims_xyz": [round(d, 6) for d in dims],
        "bbox_min": [round(min(xs), 6), round(min(ys), 6), round(min(zs), 6)],
        "bbox_max": [round(max(xs), 6), round(max(ys), 6), round(max(zs), 6)],
    })

if not meshes:
    raise RuntimeError("no mesh objects after import - import failed or file is empty")

print(f"\nTOTAL: {total:,d} tris across {len(meshes)} mesh objects")

scene = bpy.context.scene
print(MARKER + json.dumps({
    "file": path,
    "unit_system": scene.unit_settings.system,
    "unit_scale_length": round(scene.unit_settings.scale_length, 8),
    "length_unit": scene.unit_settings.length_unit,
    "total_tris": total,
    "objects": rows,
}))
