"""Measure the distribution of face SLOPE inside the church's plaster band.

    blender --background --python scripts/blender/church_normals.py -- \
        --in <fbx> --report <json> --expect-up 0.9147 \
        --lo-frac 0.115 --hi-frac 0.683

WHY SLOPE AND NOT HEIGHT
------------------------
The first three bands are HEIGHT bands and that worked because stone, plaster
and dome stack vertically. **The roof does not.** The nave roof and the tower
shaft occupy the SAME height range, so no horizontal cut separates them: any
height band that catches the roof also catches the tower, and any band that
misses the tower also misses the roof.

What actually distinguishes a roof is that it is SLOPED. Walls are vertical
(face normal's up-component near 0); a pitched roof sits near cos(pitch);
flat caps and sills sit near 1. So the fourth material is selected by NORMAL,
inside the existing plaster height range -- not by a fourth height band.

This measures the distribution first so the threshold is read off the mesh
rather than chosen. Read-only.
"""
import json
import math
import sys

import bpy   # noqa: E402


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = argv_after_ddash()
    src, rep = get(args, "--in"), get(args, "--report")
    eu = float(get(args, "--expect-up"))
    lo_f = float(get(args, "--lo-frac", "0.115"))
    hi_f = float(get(args, "--hi-frac", "0.683"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    me = ob.data

    spans = {}
    for ax in (0, 1, 2):
        vals = [v.co[ax] for v in me.vertices]
        spans[ax] = (min(vals), max(vals), max(vals) - min(vals))
    scored = sorted(spans.items(), key=lambda kv: abs(kv[1][2] - eu))
    up = scored[0][0]
    if abs(scored[0][1][2] - eu) > 0.02 * eu:
        raise SystemExit("no axis matches up-span %.5f" % eu)
    zmin, _, span = scored[0][1]
    lo, hi = zmin + span * lo_f, zmin + span * hi_f

    # 20 buckets of |normal . up|, over faces INSIDE the plaster band only
    buckets = [0] * 20
    area = [0.0] * 20
    n_in = 0
    for poly in me.polygons:
        c = sum((me.vertices[i].co[up] for i in poly.vertices),
                0.0) / len(poly.vertices)
        if not (lo <= c < hi):
            continue
        n_in += 1
        u = abs(poly.normal[up])
        b = min(19, int(u * 20))
        buckets[b] += 1
        area[b] += poly.area

    tot_a = sum(area) or 1.0
    rows = [{"lo": round(i / 20.0, 2), "hi": round((i + 1) / 20.0, 2),
             "faces": buckets[i], "area": round(area[i], 6),
             "area_pct": round(100.0 * area[i] / tot_a, 2)}
            for i in range(20)]
    out = {"faces_in_band": n_in, "band_fracs": [lo_f, hi_f],
           "up_axis": "xyz"[up], "buckets": rows,
           "_meaning": ("|normal . up| per face, area-weighted. ~0 is a "
                        "vertical wall, ~1 a flat cap, and a pitched roof "
                        "sits at cos(pitch): 0.87 at 30 deg, 0.71 at 45.")}
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    print("__NORMALS__ faces_in_band=%d" % n_in)
    for r in rows:
        if r["faces"]:
            print("  %.2f-%.2f  faces %6d  area %6.2f%%   pitch %s"
                  % (r["lo"], r["hi"], r["faces"], r["area_pct"],
                     ("%.0f deg" % math.degrees(math.acos(
                         min(1.0, max(1e-9, (r["lo"] + r["hi"]) / 2)))))))


main()
