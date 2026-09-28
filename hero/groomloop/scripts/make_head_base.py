"""make_head_base.py -- strip a blend down to the hero's head, for landing into.

    blender --background <in.blend> --python make_head_base.py -- <out.blend>

WHY. `pick_curves_object` selects the Curves object with the MOST curves, which
is the right rule for finding "the groom" in an authoring file and the wrong
outcome if a second groom is sitting beside it. The v2 payload lands at 40,281
curves into a file that still holds the v1 groom at 100,943, so every
downstream pass -- benchmarks, standoff, export -- would measure V1 while
appearing to succeed. That is the silent-wrong-object failure pick_curves.py's
own docstring was written about, arriving from the other direction.

So the base carries the HEAD and nothing that could be mistaken for a groom.
The armature is kept (the head is parented to it and the seating reads the mesh
in world space); cameras are kept, since a framed view costs nothing and an
unframed file reads as empty.
"""

import os
import sys

import bpy


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend = os.path.abspath(tail[0])

    removed = []
    for ob in list(bpy.data.objects):
        if ob.type == "CURVES":
            removed.append((ob.name, len(ob.data.curves)))
            bpy.data.objects.remove(ob, do_unlink=True)

    kept = [(o.name, o.type) for o in bpy.data.objects]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("REFUSE: no MESH left -- nothing to seat a groom onto")
    head = max(meshes, key=lambda o: len(o.data.vertices))

    # ASSERT the head survived intact. A base whose head lost geometry would
    # seat every root onto the wrong surface, and the failure would look like a
    # binding fault three stages later.
    if len(head.data.vertices) < 1000:
        raise SystemExit("REFUSE: largest mesh has only %d verts"
                         % len(head.data.vertices))

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print("__BASE__ removed_curves=%s kept=%s head=%s verts=%d -> %s"
          % (removed, kept, head.name, len(head.data.vertices), out_blend))


main()
