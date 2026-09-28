"""Measure the forged church's vertical profile, so the material bands are
READ OFF THE MESH instead of guessed.

    blender --background --python scripts/blender/church_profile.py -- \
        --in <fbx> --report <json>

Option A (ruled 2026-08-30) splits the church into three material slots by
vertex-height band: stone base, plaster body, copper dome. The band edges have
to come from somewhere. The concept gives RATIOS (nave 1.5x the chalet
silhouette, spire 2.5x) but no floor line and no dome spring point, so the
ratios alone cannot place two of the three edges.

What the mesh can say is where its own RADIUS changes. A dome bulges: its
cross-sectional radius grows again after the tower shaft narrows. This reports
radius vs height in slices so that inflection is visible as a number rather
than picked by eye off a render.

READ-ONLY. Imports, measures, writes a JSON report, changes nothing.
"""
import json
import math
import os
import sys

import bpy   # noqa: E402


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def get(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = argv_after_ddash()
    src = get(args, "--in")
    rep = get(args, "--report")
    slices = int(get(args, "--slices", "40"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(meshes) != 1:
        raise SystemExit("expected exactly 1 mesh, got %d" % len(meshes))
    ob = meshes[0]
    me = ob.data

    # ⛔ DO NOT ASSUME Z IS UP. The FBX round trip rotates -90 about X, and
    # this script's first run measured a span of 0.3949 -- which is the
    # church's exported Y (0.39494), not its Z (0.9147). Reading the profile
    # off the wrong axis would have produced perfectly plausible band edges
    # for a building lying on its side, and nothing downstream would have
    # noticed: the same failure the forge's own orientation gate exists for.
    #
    # So UP IS IDENTIFIED BY MEASUREMENT: the axis whose span matches the
    # exported height, passed in. Ambiguity is a refusal, not a guess.
    spans = {}
    for ax in (0, 1, 2):
        vals = [v.co[ax] for v in me.vertices]
        spans[ax] = (min(vals), max(vals), max(vals) - min(vals))
    expect_up = get(args, "--expect-up")
    if expect_up is None:
        raise SystemExit("--expect-up <span> is required: the up axis must be "
                         "identified by measurement, not assumed")
    eu = float(expect_up)
    scored = sorted(spans.items(), key=lambda kv: abs(kv[1][2] - eu))
    up, best = scored[0][0], scored[0][1]
    if abs(best[2] - eu) > 0.02 * eu:
        raise SystemExit(
            "NO AXIS MATCHES the expected up-span %.5f. Spans are "
            "x=%.5f y=%.5f z=%.5f -- refusing rather than picking one."
            % (eu, spans[0][2], spans[1][2], spans[2][2]))
    second = scored[1][1]
    if abs(second[2] - eu) <= 0.02 * eu:
        raise SystemExit(
            "AMBIGUOUS up axis: two axes match %.5f within 2%%. Refusing."
            % eu)
    lateral = [a for a in (0, 1, 2) if a != up]
    zmin, zmax, span = best
    axis_name = "xyz"[up]

    # ⛔ RADIUS MUST BE MEASURED ABOUT THE TOWER'S OWN AXIS, NOT THE MESH
    # CENTRE. The tower is OFF-CENTRE from the nave, so radius about the mesh
    # centroid mixes lateral offset with local radius and the dome shows no
    # bulge at all. The first split used that flat profile, put the copper
    # edge at 0.80, and the frame showed copper on the FINIAL SPIKE ONLY while
    # the onion dome stayed plaster -- the concept's one specific material
    # call, missed.
    #
    # The tower axis is the XY centroid of the vertices ABOVE `--axis-from`
    # (default 0.65 of height): high enough to be tower-only, low enough to
    # have vertices. Radius about THAT resolves the dome.
    la, lb = lateral
    axis_from = float(get(args, "--axis-from", "0.65"))
    cut = zmin + span * axis_from
    upper = [v for v in me.vertices if v.co[up] >= cut]
    if len(upper) < 32:
        raise SystemExit("only %d vertices above %.2f of height -- cannot fix "
                         "a tower axis" % (len(upper), axis_from))
    ca = sum(v.co[la] for v in upper) / len(upper)
    cb = sum(v.co[lb] for v in upper) / len(upper)
    mesh_ca = (spans[la][0] + spans[la][1]) / 2.0
    mesh_cb = (spans[lb][0] + spans[lb][1]) / 2.0
    axis_offset = math.hypot(ca - mesh_ca, cb - mesh_cb)

    rows = []
    for i in range(slices):
        lo = zmin + span * i / slices
        hi = zmin + span * (i + 1) / slices
        rad, n = [], 0
        for v in me.vertices:
            h = v.co[up]
            if lo <= h < hi or (i == slices - 1 and h == hi):
                rad.append(math.hypot(v.co[la] - ca, v.co[lb] - cb))
                n += 1
        rows.append({
            "i": i,
            "z_lo_frac": round(i / float(slices), 4),
            "z_hi_frac": round((i + 1) / float(slices), 4),
            "z_lo": round(lo, 4), "z_hi": round(hi, 4),
            "verts": n,
            "r_max": round(max(rad), 4) if rad else 0.0,
            "r_mean": round(sum(rad) / len(rad), 4) if rad else 0.0,
        })

    # the dome: scanning DOWN from the top, radius grows then collapses at the
    # neck. Report the highest slice whose r_max is a local minimum below the
    # bulge -- that is the spring line, and it is a measurement.
    top_half = [r for r in rows if r["z_lo_frac"] >= 0.5 and r["verts"] > 0]
    neck = None
    if top_half:
        # walk down from the top until r_max stops decreasing
        best = None
        for r in reversed(top_half):
            if best is None or r["r_max"] <= best["r_max"]:
                best = r
            else:
                neck = best
                break
        if neck is None:
            neck = best

    out = {
        "source": os.path.basename(src),
        "verts": len(me.vertices), "polys": len(me.polygons),
        "material_slots": [m.name if m else None for m in ob.data.materials],
        "up_min": round(zmin, 4), "up_max": round(zmax, 4),
        "up_span": round(span, 4),
        "up_axis": axis_name,
        "up_axis_index": up,
        "axis_spans": {"x": round(spans[0][2], 5),
                       "y": round(spans[1][2], 5),
                       "z": round(spans[2][2], 5)},
        "expected_up_span": eu,
        "tower_axis": [round(ca, 4), round(cb, 4)],
        "mesh_centre": [round(mesh_ca, 4), round(mesh_cb, 4)],
        "tower_axis_offset": round(axis_offset, 4),
        "axis_from_frac": axis_from,
        "_axis_note": (
            "radius is measured about the TOWER axis, not the mesh centre. "
            "The offset between them is why the first profile showed no dome "
            "bulge: it was measuring distance-from-nave-centre, which grows "
            "with the tower's lateral offset and swamps the dome's own "
            "radius."),
        "slices": rows,
        "dome_neck_slice": neck,
        "_dome_neck_meaning": (
            "walking DOWN from the top, the first slice where r_max stops "
            "decreasing -- i.e. the narrowest point under the bulge. That is "
            "the dome spring line, measured from the geometry rather than "
            "picked off a render."),
    }
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("__PROFILE__" + json.dumps({
        "up_axis": axis_name, "up_span": out["up_span"],
        "axis_spans": out["axis_spans"], "verts": out["verts"],
        "slots": out["material_slots"],
        "neck_frac": neck["z_lo_frac"] if neck else None,
        "neck_r": neck["r_max"] if neck else None}))


main()
