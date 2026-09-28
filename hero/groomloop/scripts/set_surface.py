"""Set the Curves emitter SURFACE, which land_difflocks.py never did.

The groom that draws carries data.surface = the hero face mesh and
data.surface_uv_map = "DiffuseUV". The DiffLocks groom carried None and "",
and drew nothing in UE bound OR unbound. Everything else about the two is
identical: same attributes, same width, same bounds, same interpolation.

Patches the saved blend in place of a full re-land, because the roots are
already snapped and re-running closest_point_on_mesh over 100,943 roots costs
ten minutes for a value that is one assignment.
"""
import sys, os, json
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

a = sys.argv
tail = a[a.index("--") + 1:] if "--" in a else []
out = tail[0]
uvmap = tail[1] if len(tail) > 1 else "DiffuseUV"

ob = pick_curves_object(bpy)
head = max([o for o in bpy.data.objects if o.type == "MESH"],
           key=lambda o: len(o.data.vertices))
d = ob.data
d.surface = head
d.surface_uv_map = uvmap
bpy.ops.wm.save_as_mainfile(filepath=out)
print("__SURF__" + json.dumps({
    "object": ob.name, "surface": d.surface.name if d.surface else None,
    "surface_uv_map": d.surface_uv_map, "saved": out,
    "uv_layers_on_head": [l.name for l in head.data.uv_layers]}))
