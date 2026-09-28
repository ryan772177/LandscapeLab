"""render_head_facing.py — photograph the bare head from +Y and -Y and settle
which way it faces.

    blender.exe --background <authoring.blend> --python this.py -- <out_dir>

WHY A RENDER AND NOT ANOTHER TEST. Two protrusion tests disagreed and both
were wrong: a mid-height slice said the face is at -Y, an eye-band slice said
+Y, and each produced a plausible groom that I misread as a styling problem
for several iterations. A protrusion test cannot tell a nose from an occiput
without knowing where the eyes are, and this mesh carries the neck so height
fractions do not locate them.

A picture of the head can. Solid shading shows a nose, eye sockets and lips
unmistakably, and the two views are a SINGLE VARIABLE apart -- same camera
distance, same framing, same lighting, opposite side. Whichever one has a
face on it is the answer, and it is an answer rather than an inference.

Workbench, because this needs geometry to be legible and nothing else: no
materials, no light rig to get wrong, no wait.
"""

import json
import os
import sys

import bpy
import mathutils


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    out_dir = tail[0] if tail else "."
    os.makedirs(out_dir, exist_ok=True)

    rep = {"blend": bpy.data.filepath, "views": {}}

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        rep["error"] = "no mesh"
        print("__FACING__" + json.dumps(rep))
        return
    head = max(meshes, key=lambda o: len(o.data.vertices))
    rep["head"] = head.name

    mw = head.matrix_world
    pts = [mw @ v.co for v in head.data.vertices]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    lo = mathutils.Vector((min(xs), min(ys), min(zs)))
    hi = mathutils.Vector((max(xs), max(ys), max(zs)))
    centre = (lo + hi) * 0.5
    span = max(hi.x - lo.x, hi.z - lo.z)
    rep["head_bounds"] = {"min": [round(v, 2) for v in lo],
                          "max": [round(v, 2) for v in hi]}

    # HIDE EVERYTHING ELSE. Any hair in the file would be the subject rather
    # than the head, and the question is about the head.
    for ob in bpy.data.objects:
        ob.hide_render = (ob is not head)
    rep["hidden"] = [o.name for o in bpy.data.objects if o.hide_render]

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    try:
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "SINGLE"
    except Exception:
        pass

    cam_data = bpy.data.cameras.new("FacingCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span * 1.35
    cam = bpy.data.objects.new("FacingCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    dist = span * 3.0
    for label, sign in (("plus_Y", 1.0), ("minus_Y", -1.0)):
        cam.location = (centre.x, centre.y + sign * dist, centre.z)
        # Look back along Y at the head centre. Rotation is built from the
        # direction rather than typed, so the two views cannot differ by a
        # hand-entered angle.
        direction = centre - mathutils.Vector(cam.location)
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(out_dir, "head_facing_%s.png" % label)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        rep["views"][label] = {
            "camera_at": [round(v, 2) for v in cam.location],
            "png": path,
            "exists": os.path.isfile(path),
            "bytes": os.path.getsize(path) if os.path.isfile(path) else 0}

    print("__FACING__" + json.dumps(rep))


main()
