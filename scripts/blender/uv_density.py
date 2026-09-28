"""Measure METRES PER UV UNIT per material slot, so texture tiling can be
DERIVED rather than left at the machine unwrap's arbitrary scale.

    blender --background --python scripts/blender/uv_density.py -- \
        --in <fbx> --report <json> --scale-to-cm 1845.0 --expect-up 0.9147

WHY
---
The master carries a `Tiling` scalar and nothing ever set it, so every role
renders at 1.0 -- i.e. at whatever density `smart_project` happened to
produce. On the church that put shingle courses at roughly half a metre, which
reads as slate slabs rather than shingles.

Tiling cannot be guessed sensibly because the unwrap's scale is not a property
of anything: it is an artefact of a machine unwrap over an arbitrary mesh. So
this measures it. For each slot:

    metres_per_uv = median( world edge length / UV edge length )

and then, for a texture that depicts `tile_m` metres of real surface:

    tiling = metres_per_uv / tile_m

⛔ THE MESH IS MEASURED AT ITS AUTHORED SIZE AND SCALED UP. The FBX is 0.9147
units tall and stands in the world at 1845 cm, so world size is
`--scale-to-cm` and the ratio matters, not the raw units. Passing the wrong
scale gives a plausible number for the wrong building.

Read-only with respect to the scene/FBX; writes only the --report JSON.
"""
import json
import math
import statistics
import sys

import bpy   # noqa: E402


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = argv_after_ddash()
    src, rep = get(args, "--in"), get(args, "--report")
    # Validate presence before float(): a missing --scale-to-cm/--expect-up
    # would otherwise be float(None) -> an opaque TypeError, inconsistent with
    # this script's clean SystemExit style.
    if not src or not rep or "--scale-to-cm" not in args \
            or "--expect-up" not in args:
        raise SystemExit("usage: --in <fbx> --report <json> --scale-to-cm "
                         "<cm> --expect-up <units>")
    scale_cm = float(get(args, "--scale-to-cm"))
    eu = float(get(args, "--expect-up"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    if not objs:
        raise SystemExit("no mesh objects in " + src)

    # ⛔ EVERY MESH OBJECT, aggregated BY SLOT NAME. The church is one mesh;
    # the C0 donor FBX is three -- house, door, bezier curve -- and its slots
    # are spread across them (Material_002 on the curve, Material_008 on the
    # door). UE imported that with combine_meshes=True, so the engine asset
    # carries every slot on one mesh. Measuring the biggest object alone would
    # silently return NO density for two roles, and the builder would then
    # refuse them -- or worse, if it did not, ship them at 1.0.
    #
    # The up axis is identified on the LARGEST object, because that is the one
    # whose span is the building's; a door is not.
    biggest = max(objs, key=lambda o: len(o.data.polygons))
    if not biggest.data.vertices:
        raise SystemExit("largest object %r has no vertices; cannot measure "
                         "the up-span" % biggest.name)
    spans = {}
    for ax in (0, 1, 2):
        vals = [v.co[ax] for v in biggest.data.vertices]
        spans[ax] = max(vals) - min(vals)
    up = min(range(3), key=lambda a: abs(spans[a] - eu))
    if abs(spans[up] - eu) > 0.02 * eu:
        raise SystemExit(
            "no axis of the largest object matches up-span %.5f (x=%.4f "
            "y=%.4f z=%.4f); refusing rather than picking one"
            % (eu, spans[0], spans[1], spans[2]))
    world_m_per_unit = (scale_cm / 100.0) / spans[up]

    per = {}
    # Seed EVERY slot name across ALL mesh objects (including UV-less ones) so a
    # role that exists only on an unmeasurable object is reported with
    # samples:0 rather than silently absent -- the "no density for a role"
    # failure the docstring warns about. (The consumer skips medians that are
    # None, so a samples:0 row is a visible refusal, not a wrong tiling.)
    for ob in objs:
        for m in ob.data.materials:
            per.setdefault(m.name if m else "<none>", [])
    objs_used = []
    for ob in objs:
        me = ob.data
        if not me.uv_layers:
            objs_used.append({"object": ob.name, "skipped": "no UV layer"})
            continue
        uvs = me.uv_layers[0].data
        slots = [m.name if m else "<none>" for m in me.materials]
        if not slots:
            objs_used.append({"object": ob.name, "skipped": "no slots"})
            continue
        objs_used.append({"object": ob.name, "polys": len(me.polygons),
                          "slots": slots})
        for poly in me.polygons:
            # material_index is stored per-face and is not guaranteed < len
            # (e.g. after a slot is removed); an out-of-range index would abort
            # the whole run. Route those to "<none>" rather than IndexError.
            mi = poly.material_index
            name = slots[mi] if mi < len(slots) else "<none>"
            per.setdefault(name, [])
            n = len(poly.loop_indices)
            for i in range(n):
                l0 = poly.loop_indices[i]
                l1 = poly.loop_indices[(i + 1) % n]
                v0 = me.vertices[me.loops[l0].vertex_index].co
                v1 = me.vertices[me.loops[l1].vertex_index].co
                wl = (v1 - v0).length * world_m_per_unit
                u0, u1 = uvs[l0].uv, uvs[l1].uv
                ul = math.hypot(u1.x - u0.x, u1.y - u0.y)
                if ul > 1e-9 and wl > 1e-9:
                    per[name].append(wl / ul)

    rows = {}
    for name, vals in per.items():
        if not vals:
            rows[name] = {"samples": 0}
            continue
        vals.sort()
        rows[name] = {
            "samples": len(vals),
            "metres_per_uv_median": round(statistics.median(vals), 4),
            "p25": round(vals[len(vals) // 4], 4),
            "p75": round(vals[3 * len(vals) // 4], 4),
        }

    out = {"source": src.split("/")[-1], "scale_to_cm": scale_cm,
           "objects": objs_used,
           "world_m_per_authored_unit": round(world_m_per_unit, 4),
           "up_axis": "xyz"[up], "slots": rows,
           "_how_to_use": ("tiling = metres_per_uv_median / tile_m, where "
                           "tile_m is the real-world size the texture "
                           "depicts. Poly Haven publishes that; the "
                           "operator-generated tiles do not, so theirs is a "
                           "declared intent rather than a measurement.")}
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    # Surface the sample count beside the median so a zero-sample slot reads as
    # n=0 (could not measure), not as a bare null a consumer might treat as
    # present.
    print("__UVDENS__" + json.dumps(
        {k: {"median": v.get("metres_per_uv_median"),
             "n": v.get("samples", 0)} for k, v in rows.items()}))
    for k, v in rows.items():
        if v.get("samples"):
            print("  %-20s median %8.4f m/uv   p25 %.4f  p75 %.4f  n=%d"
                  % (k, v["metres_per_uv_median"], v["p25"], v["p75"],
                     v["samples"]))


main()
