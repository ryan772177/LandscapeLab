"""render_harness.py -- Phase 1. One fixed rig, so every iteration is comparable.

    blender --background --python render_harness.py -- <blend_or_abc> <out_dir>
                                                       <tag> [views] [samples]

THE GROOM IS NEVER MOVED. Recon says this file's up axis is -Y and the head
sits at (0, -1.52, 0); Blender's world is Z-up. The tempting fix is to rotate
the object 90 degrees for rendering, and that is exactly how a transform ends
up baked into an export. So the CAMERA is built in the groom's frame instead,
with an explicit up vector, and the object keeps its identity matrix forever.

RADIUS IS OVERRIDDEN FOR RENDERING ONLY. The source carries a constant radius
of 0.43661, which at this file's metre scale is a 44 cm thick strand -- the
frame would be a solid blob. The override is applied to a COPY of the render
scene and never written to an export. The source value is reported so the UE
import checklist can set Hair Width deliberately rather than inheriting a
fallback.
"""

import json
import math
import os
import sys

import bpy
import mathutils
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proxy_head                                # noqa: E402

HEAD = mathutils.Vector((0.0, -1.52098, 0.0))   # root centroid, from recon
UP = mathutils.Vector((0.0, -1.0, 0.0))          # -Y is up in this file
RENDER_RADIUS = 0.00018                          # 0.18 mm, render only


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def look_at(cam, target, up):
    """Aim a camera at a point with an explicit up vector.

    Blender's to_track_quat assumes world +Z is up, which is false here, so the
    basis is built by hand. Getting this wrong tilts every render by 90 degrees
    and makes iterations incomparable in a way that looks like a hair change.
    """
    fwd = (target - cam.location).normalized()
    right = fwd.cross(up)
    if right.length < 1e-6:
        right = fwd.cross(mathutils.Vector((1, 0, 0)))
    right.normalize()
    trueup = right.cross(fwd).normalized()
    m = mathutils.Matrix(((right.x, trueup.x, -fwd.x, 0.0),
                          (right.y, trueup.y, -fwd.y, 0.0),
                          (right.z, trueup.z, -fwd.z, 0.0),
                          (0.0, 0.0, 0.0, 1.0)))
    cam.rotation_euler = m.to_euler()


def build_world():
    w = bpy.data.worlds.new("GroomWorld")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.32, 0.32, 0.34, 1.0)
    bg.inputs[1].default_value = 1.0
    bpy.context.scene.world = w


def build_lights(dist):
    """Three-point rig in the groom's frame. Key from camera-left and above,
    fill opposite and lower, rim from behind -- so silhouette and clump
    separation both read, which is what the scoring criteria ask for."""
    specs = [("key", mathutils.Vector((-1.0, -1.0, 1.2)), 900.0),
             ("fill", mathutils.Vector((1.2, -0.2, 0.9)), 320.0),
             ("rim", mathutils.Vector((0.2, -0.9, -1.4)), 700.0)]
    for name, d, power in specs:
        lp = bpy.data.lights.new(name, type="AREA")
        lp.energy = power
        lp.size = 1.2
        lo = bpy.data.objects.new(name, lp)
        bpy.context.collection.objects.link(lo)
        lo.location = HEAD + d.normalized() * dist * 1.6
        look_at(lo, HEAD, UP)


def hair_material():
    m = bpy.data.materials.new("HairMatte")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    # Principled Hair would be physically nicer, but a matte diffuse reads
    # SHAPE better, and shape is what is being scored. Colour is UE's job.
    bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
    bsdf.inputs[0].default_value = (0.045, 0.042, 0.040, 1.0)
    bsdf.inputs[1].default_value = 0.35
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


def main():
    tail = argv_tail()
    src, out_dir, tag = tail[0], tail[1], tail[2]
    views = (tail[3].split(",") if len(tail) > 3 and tail[3]
             else ["front", "back", "left", "right", "threequarter"])
    samples = int(tail[4]) if len(tail) > 4 else 48

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    if src.lower().endswith(".abc"):
        bpy.ops.wm.alembic_import(filepath=src, as_background_job=False)
    else:
        bpy.ops.wm.open_mainfile(filepath=src)

    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    if not curves:
        print("__RENDER__" + json.dumps({"ok": False,
                                         "error": "no CURVES object"}))
        return
    rep = {"ok": False, "tag": tag, "objects": [o.name for o in curves],
           "render_radius": RENDER_RADIUS, "views": {}}

    mat = hair_material()
    src_radius = None
    for ob in curves:
        d = ob.data
        r = d.attributes.get("radius")
        if r is not None:
            if src_radius is None and len(r.data):
                src_radius = round(float(r.data[0].value), 6)
            for i in range(len(r.data)):
                r.data[i].value = RENDER_RADIUS
        d.materials.clear()
        d.materials.append(mat)
    rep["source_radius"] = src_radius

    # PROXY HEAD, fitted to this file's own roots so the rulers sit in the
    # same frame as the hair. Without it a render cannot answer "does the
    # fringe reach the brow", which is the spec's headline criterion.
    try:
        ob0 = curves[0]
        d0 = ob0.data
        npts = len(d0.points)
        buf = np.zeros(npts * 3, dtype=np.float32)
        d0.attributes["position"].data.foreach_get("vector", buf)
        allp = buf.reshape(npts, 3).astype(np.float64)
        starts = np.array([c.first_point_index for c in d0.curves],
                          dtype=np.int64)
        roots = allp[starts]
        fit, _made = proxy_head.build(roots, with_rulers=True)
        rep["proxy_fit"] = {k: (list(np.round(v, 5)) if hasattr(v, "__len__")
                                else round(float(v), 5))
                            for k, v in fit.items()}
    except Exception as exc:
        rep["proxy_error"] = str(exc)

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x = 900
    sc.render.resolution_y = 900
    sc.render.film_transparent = False
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.get_devices()
        for dev_type in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = dev_type
                break
            except Exception:
                continue
        enabled = 0
        for dev in prefs.devices:
            dev.use = dev.type != "CPU"
            enabled += 1 if dev.use else 0
        sc.cycles.device = "GPU" if enabled else "CPU"
        rep["compute"] = "%s (%d devices)" % (sc.cycles.device, enabled)
    except Exception as exc:
        sc.cycles.device = "CPU"
        rep["compute"] = "CPU (%s)" % exc

    build_world()

    # Frame from the ROOT cloud, not the scene bbox: recon showed ~1,890 stray
    # tips inflating the bbox to 2.5 m, and framing on those would render a
    # head three pixels wide.
    #
    # DISTANCE IS DERIVED, NOT EYEBALLED. The groom is ~0.25 m across; an 85 mm
    # lens on a 36 mm sensor sees 2*atan(18/85) = 23.9 deg, so fitting 0.36 m
    # of subject needs 0.36/2 / tan(11.95 deg) = 0.85 m. The first pass used
    # 0.42 and rendered the inside of the hair.
    dist = 0.70
    build_lights(dist)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 85.0
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam

    # Face direction is not yet known, so the four cardinals are all rendered
    # and named by AXIS, not by anatomy. Naming one "front" before looking is
    # how a wrong assumption gets into every later filename.
    offsets = {
        "posz": mathutils.Vector((0, 0, 1)),
        "negz": mathutils.Vector((0, 0, -1)),
        "posx": mathutils.Vector((1, 0, 0)),
        "negx": mathutils.Vector((-1, 0, 0)),
        "front": mathutils.Vector((0, 0, 1)),
        "back": mathutils.Vector((0, 0, -1)),
        "left": mathutils.Vector((-1, 0, 0)),
        "right": mathutils.Vector((1, 0, 0)),
        "threequarter": mathutils.Vector((0.75, -0.25, 0.75)),
        "top": mathutils.Vector((0, -1, 0.001)),
    }
    os.makedirs(out_dir, exist_ok=True)
    for v in views:
        off = offsets.get(v)
        if off is None:
            continue
        cam.location = HEAD + off.normalized() * dist
        look_at(cam, HEAD, UP)
        path = os.path.join(out_dir, "%s_%s.png" % (tag, v))
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        rep["views"][v] = path

    rep["ok"] = True
    print("__RENDER__" + json.dumps(rep))


if __name__ == "__main__":
    main()
