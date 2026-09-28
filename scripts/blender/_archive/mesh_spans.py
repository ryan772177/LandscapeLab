"""Print a mesh's per-axis spans, vertex count and material slots.

    blender --background --python scripts/blender/mesh_spans.py -- --in <fbx>

Exists because every other Blender tool here REFUSES until it can identify the
up axis by matching a known span -- which is correct, and useless when you do
not yet know what the span is. This is the probe that answers that, and it
asserts nothing.
"""
import json
import sys

import bpy   # noqa: E402


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    src = args[args.index("--in") + 1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    out = []
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        me = ob.data
        sp = {}
        for ax, nm in ((0, "x"), (1, "y"), (2, "z")):
            vals = [v.co[ax] for v in me.vertices]
            sp[nm] = round(max(vals) - min(vals), 5)
        out.append({"object": ob.name, "verts": len(me.vertices),
                    "polys": len(me.polygons), "spans": sp,
                    "uv_layers": [u.name for u in me.uv_layers],
                    "slots": [m.name if m else None for m in me.materials]})
    print("__SPANS__" + json.dumps(out))


main()
