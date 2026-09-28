"""proxy_head.py -- a measured stand-in for the head that did not ship.

The download contains only the .abc; the grooming head exists in the UE project
as SKM_MH_Groom_Head but bringing it across means a cm/m + axis-convention
transform between two apps, and a wrong alignment there would silently move
every landmark this is supposed to provide. The root cloud is already a
measurement of the scalp, so the proxy is FITTED TO IT and lives in exactly the
same frame as the hair by construction.

WHAT IT IS AND IS NOT. It is a skull ellipsoid plus two RULERS -- a brow band
and two ear markers -- placed from the fitted skull by human proportion. It is
NOT anatomy, and the report must not quote it as if a real face had been
measured. It exists so "does the fringe reach the brow" is a thing you can SEE
in a render instead of a thing you assert.

Roots never move under the edit engine (every op is anchored at t=0), so the
proxy computed from a given file is identical across iterations and the rulers
stay put while the hair changes -- which is what makes iterations comparable.
"""

import numpy as np

import bpy
import bmesh


def fit_from_roots(roots):
    """Skull centre + per-axis radius, and the derived landmarks."""
    c = roots.mean(axis=0)
    loc = roots - c
    # p97 rather than max: recon found ~1,890 stray tips, and a max-based fit
    # would inflate the skull to the scene. p90 was tried first and fitted an
    # X radius of only 5.9 cm -- because this is a CENTRE PART, most roots sit
    # near the midline, so a low percentile measures the parting, not the
    # skull. The percentile has to sit above the parting's mass.
    r = np.percentile(np.abs(loc), 97, axis=0)

    # Frame: up = -Y, front = +Z.
    front_mask = loc[:, 2] > 0.55 * r[2]
    hairline_y = float(np.median(roots[front_mask, 1])) if front_mask.any() \
        else float(c[1])
    # Brow sits below the hairline; +Y is down in this file. 5 cm is the
    # ordinary forehead height and is declared here rather than hidden.
    brow_y = hairline_y + 0.050
    front_z = float(np.percentile(roots[:, 2], 97))
    ear_x = float(np.percentile(np.abs(roots[:, 0]), 95))
    ear_y = hairline_y + 0.030
    return {"centre": c, "radius": r, "hairline_y": hairline_y,
            "brow_y": brow_y, "front_z": front_z,
            "ear_x": ear_x, "ear_y": ear_y}


def _mat(name, rgb, rough=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    b = nt.nodes.new("ShaderNodeBsdfDiffuse")
    b.inputs[0].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    b.inputs[1].default_value = rough
    nt.links.new(b.outputs[0], out.inputs[0])
    return m


def build(roots, with_rulers=True):
    """Create the proxy objects and return the fit dict."""
    f = fit_from_roots(roots)
    c, r = f["centre"], f["radius"]

    me = bpy.data.meshes.new("ProxySkull")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("ProxySkull", me)
    bpy.context.collection.objects.link(ob)
    ob.location = tuple(c)
    # Slightly inside the roots so strands are not buried by the proxy; the
    # skull is a shading occluder, not a collision surface.
    ob.scale = (r[0] * 0.94, r[1] * 0.99, r[2] * 0.94)
    me.materials.append(_mat("ProxySkin", (0.28, 0.24, 0.22)))
    for p in me.polygons:
        p.use_smooth = True

    if not with_rulers:
        return f, [ob]

    made = [ob]
    # BROW BAND -- a thin bar across the front face at the estimated brow
    # height. Fringe tips reaching it is the spec's "eyebrow-to-upper-eyelid".
    bme = bpy.data.meshes.new("BrowBand")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(bme)
    bm.free()
    bo = bpy.data.objects.new("BrowBand", bme)
    bpy.context.collection.objects.link(bo)
    bo.location = (float(c[0]), f["brow_y"], f["front_z"] * 0.86)
    bo.scale = (r[0] * 1.05, 0.004, 0.004)
    bme.materials.append(_mat("RulerRed", (0.75, 0.05, 0.05), 0.9))
    made.append(bo)

    # EAR MARKERS -- spheres at the estimated ear tops. "Feathered over the top
    # half of the ears" is scoreable only if the ear position is visible.
    for sgn in (-1.0, 1.0):
        eme = bpy.data.meshes.new("EarMark")
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
        bm.to_mesh(eme)
        bm.free()
        eo = bpy.data.objects.new("EarMark", eme)
        bpy.context.collection.objects.link(eo)
        eo.location = (sgn * f["ear_x"] * 0.99, f["ear_y"], 0.012)
        eo.scale = (0.008, 0.022, 0.014)
        eme.materials.append(_mat("RulerBlue", (0.05, 0.25, 0.85), 0.9))
        made.append(eo)
    return f, made
