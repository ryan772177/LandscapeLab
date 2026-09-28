"""frame_blend_view.py -- make a groom .blend OPEN looking at the head.

    blender --background <in.blend> --python frame_blend_view.py -- <out.blend>

WHY. These blends are in the DNA's own space: centimetres, with the head at
Z 140.9 to 180.4. Blender's startup view is framed on a two-unit cube at the
origin and its viewport far-clip is finite, so opening one of these files shows
an EMPTY VIEWPORT with a complete character sitting a hundred and seventy units
overhead. Nothing is hidden and no collection is excluded -- it is purely where
the camera is pointed, and it reads exactly like a broken file.

THE GEOMETRY IS NOT MOVED, and that is deliberate. Every root sits where it was
snapped onto the hero's face mesh and its root UV was read from that surface;
sliding the objects to the origin to make them convenient would move the groom
in UE and void the seating. The VIEW moves instead.

Two things are set, because either one alone still shows nothing:
  - the saved 3D view's location and distance, so it opens framed on the head
  - the view's clip range, since a far-clip shorter than the head's distance
    from the origin removes it from the frame even when it is centred

A CAMERA is added as well, so `Numpad 0` gives a known-good framing even if the
saved view is reset.
"""

import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def bounds():
    lo = mathutils.Vector((1e9, 1e9, 1e9))
    hi = mathutils.Vector((-1e9, -1e9, -1e9))
    for o in bpy.context.scene.objects:
        if o.type not in ("MESH", "CURVES"):
            continue
        try:
            pts = [o.matrix_world @ v.co for v in o.data.vertices]
        except AttributeError:
            pts = [o.matrix_world @ p.position for p in o.data.points]
        for p in pts:
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    return lo, hi


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend = tail[0]

    lo, hi = bounds()
    centre = (lo + hi) * 0.5
    span = max((hi - lo).x, (hi - lo).y, (hi - lo).z)
    # frame the HEAD, not the whole rig: the curves top out at the crown and the
    # mesh runs down into the neck, so the midpoint of the combined bounds sits
    # low. Bias upward by a quarter of the span.
    centre.z += span * 0.10

    n_view = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.clip_start = 0.1
                space.clip_end = max(10000.0, span * 100.0)
                r = getattr(space, "region_3d", None)
                if r is not None:
                    r.view_location = centre
                    r.view_distance = span * 1.9
                    r.view_perspective = "PERSP"
                n_view += 1

    cam_data = bpy.data.cameras.new("HeadCam")
    cam_data.clip_start = 1.0
    cam_data.clip_end = max(10000.0, span * 100.0)
    cam = bpy.data.objects.new("HeadCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (centre.x, centre.y - span * 2.2, centre.z)
    cam.rotation_euler = (1.5708, 0.0, 0.0)          # look along +Y at the face
    bpy.context.scene.camera = cam

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend))
    print("__FV__ bounds z %.1f..%.1f  centre %s  span %.1f  view_spaces %d -> %s"
          % (lo.z, hi.z, tuple(round(v, 1) for v in centre), span, n_view,
             out_blend))


main()
