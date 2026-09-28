"""probe_gltf.py -- inventory a .glb/.gltf WITHOUT importing it.

READ-ONLY. Parses the glTF JSON chunk and reports, per scene node that carries
geometry: world-space bounding box, triangle count, materials and textures.

WHY OFFLINE, BEFORE THE IMPORT
An import is a decision with a cost -- assets on disk, a package per mesh, and
in this project an editor that has been fataled by import paths more than once.
Every question that decides HOW to import (how many buildings are in here, what
unit is it in, does a chalet come out 10 m or 0.1 m) is answerable from the file
itself in under a second.

UNITS: glTF 2.0 declares metres. That is the SPEC, not a measurement of this
file, so the number is reported and compared against an expectation rather than
trusted -- an 8-12 m wide chalet confirms metres; 0.08-0.12 confirms something
else and 800-1200 confirms centimetres.

BOUNDING BOXES ARE WORLD-SPACE. Accessor min/max are in the mesh's LOCAL space,
so each is transformed by the accumulated node chain. A model whose parts are
placed by node transforms -- which is exactly what a village scene is -- reports
nonsense if the local boxes are read directly.

Exit codes: 0 probed  2 bad args / file missing  3 not a glTF container
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys


def load_gltf_json(path):
    """Return the glTF JSON dict from a .glb or .gltf."""
    with open(path, "rb") as fh:
        head = fh.read(12)
        if head[:4] == b"glTF":
            _magic, _ver, _total = struct.unpack("<III", head)
            while True:
                hdr = fh.read(8)
                if len(hdr) < 8:
                    break
                clen, ctype = struct.unpack("<II", hdr)
                data = fh.read(clen)
                if ctype == 0x4E4F534A:      # 'JSON'
                    return json.loads(data.decode("utf-8"))
            return None
        fh.seek(0)
        try:
            return json.load(fh)
        except Exception:
            return None


def mat_mul(a, b):
    out = [0.0] * 16
    for r in range(4):
        for c in range(4):
            out[r * 4 + c] = sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
    return out


def trs_matrix(node):
    """glTF column-major matrix, or T*R*S composed from the node's fields."""
    if "matrix" in node:
        m = node["matrix"]           # column-major in the file
        return [m[0], m[4], m[8], m[12],
                m[1], m[5], m[9], m[13],
                m[2], m[6], m[10], m[14],
                m[3], m[7], m[11], m[15]]
    t = node.get("translation", [0.0, 0.0, 0.0])
    r = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    s = node.get("scale", [1.0, 1.0, 1.0])
    x, y, z, w = r
    rot = [
        1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0.0,
        2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0.0,
        2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0.0,
        0.0, 0.0, 0.0, 1.0]
    scl = [s[0], 0, 0, 0, 0, s[1], 0, 0, 0, 0, s[2], 0, 0, 0, 0, 1]
    tr = [1, 0, 0, t[0], 0, 1, 0, t[1], 0, 0, 1, t[2], 0, 0, 0, 1]
    return mat_mul(tr, mat_mul(rot, scl))


def xform(m, p):
    x, y, z = p
    return (m[0] * x + m[1] * y + m[2] * z + m[3],
            m[4] * x + m[5] * y + m[6] * z + m[7],
            m[8] * x + m[9] * y + m[10] * z + m[11])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    if not os.path.isfile(a.path):
        print("REFUSE: no file at %s" % a.path)
        return 2
    g = load_gltf_json(a.path)
    if not isinstance(g, dict) or "meshes" not in g:
        print("REFUSE: not a glTF container, or it declares no meshes")
        return 3

    meshes = g.get("meshes", [])
    accessors = g.get("accessors", [])
    materials = g.get("materials", [])
    images = g.get("images", [])
    nodes = g.get("nodes", [])

    print("FILE       %s  (%.1f MB)"
          % (os.path.basename(a.path), os.path.getsize(a.path) / 1e6))
    print("generator  %s" % g.get("asset", {}).get("generator"))
    print("meshes %d   nodes %d   materials %d   images %d"
          % (len(meshes), len(nodes), len(materials), len(images)))
    print("")

    def mesh_stats(mi):
        tris, mats, vmin, vmax = 0, set(), None, None
        for prim in meshes[mi].get("primitives", []):
            if prim.get("mode", 4) != 4:
                continue
            if "indices" in prim:
                tris += accessors[prim["indices"]]["count"] // 3
            else:
                pa = prim.get("attributes", {}).get("POSITION")
                if pa is not None:
                    tris += accessors[pa]["count"] // 3
            if prim.get("material") is not None:
                mats.add(prim["material"])
            pa = prim.get("attributes", {}).get("POSITION")
            if pa is not None:
                acc = accessors[pa]
                lo, hi = acc.get("min"), acc.get("max")
                if lo and hi:
                    vmin = lo if vmin is None else [min(x, y) for x, y in zip(vmin, lo)]
                    vmax = hi if vmax is None else [max(x, y) for x, y in zip(vmax, hi)]
        return tris, sorted(mats), vmin, vmax

    found = []

    def walk(ni, parent):
        node = nodes[ni]
        world = mat_mul(parent, trs_matrix(node))
        if node.get("mesh") is not None:
            tris, mats, lo, hi = mesh_stats(node["mesh"])
            box = None
            if lo and hi:
                corners = [(lo[0] if i & 1 else hi[0],
                            lo[1] if i & 2 else hi[1],
                            lo[2] if i & 4 else hi[2]) for i in range(8)]
                pts = [xform(world, c) for c in corners]
                box = ([min(p[k] for p in pts) for k in range(3)],
                       [max(p[k] for p in pts) for k in range(3)])
            found.append({
                "node": ni,
                "name": node.get("name") or meshes[node["mesh"]].get("name")
                        or "mesh_%d" % node["mesh"],
                "mesh": node["mesh"],
                "tris": tris,
                "materials": mats,
                "box": box})
        for c in node.get("children", []):
            walk(c, world)

    ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    scene = g.get("scenes", [{}])[g.get("scene", 0)]
    for root in scene.get("nodes", range(len(nodes))):
        walk(root, ident)

    print("GEOMETRY NODES, world-space, glTF units (spec says METRES)")
    print("  %-34s %8s  %7s %7s %7s   %s"
          % ("name", "tris", "dx", "dy", "dz", "mats"))
    found.sort(key=lambda r: -r["tris"])
    for r in found:
        if r["box"]:
            lo, hi = r["box"]
            d = [hi[i] - lo[i] for i in range(3)]
            print("  %-34s %8d  %7.2f %7.2f %7.2f   %s"
                  % (r["name"][:34], r["tris"], d[0], d[1], d[2],
                     r["materials"]))
        else:
            print("  %-34s %8d  %7s %7s %7s   %s"
                  % (r["name"][:34], r["tris"], "?", "?", "?", r["materials"]))

    tot = sum(r["tris"] for r in found)
    print("")
    print("TOTAL geometry nodes %d, triangles %d" % (len(found), tot))

    if found:
        allpts = [r["box"] for r in found if r["box"]]
        if allpts:
            lo = [min(b[0][i] for b in allpts) for i in range(3)]
            hi = [max(b[1][i] for b in allpts) for i in range(3)]
            print("SCENE bounds  dx %.2f  dy %.2f  dz %.2f"
                  % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
            tall = max((b[1][1] - b[0][1]) for b in allpts)
            print("tallest single node, Y (glTF up) = %.2f" % tall)
            print("")
            print("UNIT READING: a chalet ridge should be 10-14. Tallest node "
                  "is %.2f -> %s" % (tall,
                  "METRES, matches the glTF spec" if 3.0 < tall < 60.0
                  else "NOT metres -- check before importing"))

    print("")
    print("MATERIALS")
    for i, m in enumerate(materials):
        pbr = m.get("pbrMetallicRoughness", {})
        t = []
        if "baseColorTexture" in pbr:
            t.append("baseColor")
        if "metallicRoughnessTexture" in pbr:
            t.append("metalRough")
        if "normalTexture" in m:
            t.append("normal")
        if "occlusionTexture" in m:
            t.append("occlusion")
        print("  [%2d] %-28s %s" % (i, (m.get("name") or "?")[:28],
                                    ",".join(t) or "NO TEXTURES"))

    if a.json_out:
        os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump({"file": os.path.basename(a.path),
                       "generator": g.get("asset", {}).get("generator"),
                       "nodes": found,
                       "materials": [m.get("name") for m in materials],
                       "images": len(images)}, fh, indent=1)
        print("")
        print("wrote %s" % a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
