"""scalp_probe.py -- how much scalp is actually visible? A MASK render.

    blender --background --python scalp_probe.py -- <blend> <out_dir> <tag>

WHY THIS EXISTS. The geometric scalp metric in measure.py reads 0.00% on
iteration 003, whose render plainly shows a bald patch on the upper side. It
cannot fire: ~375,000 points spread over 504 lat/long cells averages ~745
points per cell, so a "cell is exposed if it holds fewer than 3 points"
threshold is unreachable. It failed the precondition this project puts on any
new metric -- an input that should move the number did not -- and it is marked
UNRELIABLE rather than tuned into agreement.

WHAT THIS DOES INSTEAD. Two flat mask renders through the SAME camera:
    pass A  skull emissive RED, hair emissive BLACK   -> skull still visible
    pass B  skull emissive RED, hair HIDDEN           -> skull silhouette
    scalp_visible_pct = red(A) / red(B)
A difference measurement against a positive control, which is the form this
project trusts: pass B cannot be zero unless the rig itself is broken, and the
script refuses rather than dividing by it.

Flat emission at 4 samples, so it costs seconds rather than a full render.
"""

import json
import os
import sys

import bpy
import mathutils
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proxy_head                                       # noqa: E402

HEAD = mathutils.Vector((0.0, -1.52098, 0.0))
UP = mathutils.Vector((0.0, -1.0, 0.0))
DIST = 0.70


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def look_at(cam, target, up):
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


def emissive(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    e.inputs[1].default_value = 1.0
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def red_fraction(path):
    """Count red pixels using Blender's own image API.

    Blender's bundled Python has no PIL (measured -- the first version raised
    ModuleNotFoundError), so the pixels are read through bpy. img.pixels is
    LINEAR float RGBA, not the sRGB bytes a PNG reader would return, so the
    thresholds are linear: an emission of (1,0,0) arrives as ~1.0 red.
    """
    img = bpy.data.images.load(path)
    try:
        buf = np.zeros(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(-1, 4)
        return int(((a[:, 0] > 0.40) & (a[:, 1] < 0.30)
                    & (a[:, 2] < 0.30)).sum())
    finally:
        bpy.data.images.remove(img)


def main():
    tail = argv_tail()
    blend, out_dir, tag = tail[0], tail[1], tail[2]
    views = (tail[3].split(",") if len(tail) > 3 and tail[3]
             else ["front", "left", "top"])

    bpy.ops.wm.open_mainfile(filepath=blend)
    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    ob = curves[0]
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    P = buf.reshape(n, 3).astype(np.float64)
    starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)
    fit, made = proxy_head.build(P[starts], with_rulers=False)

    red = emissive("MaskRed", (1.0, 0.0, 0.0))
    black = emissive("MaskBlack", (0.0, 0.0, 0.0))
    for o in made:
        o.data.materials.clear()
        o.data.materials.append(red)
    for o in curves:
        o.data.materials.clear()
        o.data.materials.append(black)
        r = o.data.attributes.get("radius")
        if r is not None:
            for i in range(len(r.data)):
                r.data[i].value = 0.00018

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.resolution_x = 640
    sc.render.resolution_y = 640
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("Black")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = w
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.get_devices()
        for dev in prefs.devices:
            dev.use = dev.type != "CPU"
        sc.cycles.device = "GPU"
    except Exception:
        sc.cycles.device = "CPU"

    cam_data = bpy.data.cameras.new("MaskCam")
    cam_data.lens = 85.0
    cam = bpy.data.objects.new("MaskCam", cam_data)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    offsets = {"front": mathutils.Vector((0, 0, 1)),
               "left": mathutils.Vector((-1, 0, 0)),
               "right": mathutils.Vector((1, 0, 0)),
               "back": mathutils.Vector((0, 0, -1)),
               "top": mathutils.Vector((0, -1, 0.001))}

    os.makedirs(out_dir, exist_ok=True)
    rep = {"tag": tag, "views": {}, "refusals": []}
    for v in views:
        off = offsets.get(v)
        if off is None:
            continue
        cam.location = HEAD + off.normalized() * DIST
        look_at(cam, HEAD, UP)

        for o in curves:
            o.hide_render = False
        a_path = os.path.join(out_dir, "%s_mask_%s_A.png" % (tag, v))
        sc.render.filepath = a_path
        bpy.ops.render.render(write_still=True)

        for o in curves:
            o.hide_render = True
        b_path = os.path.join(out_dir, "%s_mask_%s_B.png" % (tag, v))
        sc.render.filepath = b_path
        bpy.ops.render.render(write_still=True)

        a = red_fraction(a_path)
        b = red_fraction(b_path)
        if b <= 0:
            rep["refusals"].append(
                "%s: control pass B has no skull pixels -- the rig is broken, "
                "so this view measures nothing" % v)
            continue
        rep["views"][v] = {"visible_px": a, "silhouette_px": b,
                           "scalp_visible_pct": round(100.0 * a / b, 2)}

    vals = [x["scalp_visible_pct"] for x in rep["views"].values()]
    rep["scalp_visible_pct_mean"] = round(sum(vals) / len(vals), 2) if vals else None
    rep["ok"] = not rep["refusals"] and bool(vals)
    print("__SCALP__" + json.dumps(rep))


if __name__ == "__main__":
    main()
