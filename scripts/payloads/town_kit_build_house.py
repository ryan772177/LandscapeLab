"""town_kit_build_house -- build kit house actors from planner piece lists (2026-10-06).

Input (substituted): SPEC = JSON, either ONE house spec or {"batch": [spec, ...]} (2026-10-06 kit town: 385
houses at one editor round trip each was ~an hour of discovery windows). One house spec:
    {"level": "/Game/...", "label": "...", "tags": [...],
     "loc_cm": [x, y, z], "yaw_deg": f,
     "ground_trace": bool, "ground_offset_cm": f,
     "trace_local_xy": [x, y]   (optional: trace the ground at this HOUSE-FRAME point instead of the centre --
                                 the kit town traces the door-side midpoint, so the door sits at grade),
     "box_center_cm": [x, y, z], "box_extent_cm": [x, y, z],
     "replace": bool, "update_in_place": bool (re-set the instances of the ONE existing same-label house; checked by tags, class, location and yaw),
     "pieces": [{"mesh": "SM_...", "x":, "y":, "z":, "yaw":, "scale"?, "path"?, "fit"?}, ...]}
                                (house frame, from scripts/town_kit_plan)

Uses LandscapeLabEditor UFUNCTIONs SpawnKitHouse + SetKitInstances (ISM instance components, one per mesh,
authored box collision). Mesh paths: /Game/Megascans/3D_Assets/<name without SM_>/<name> (the kit closure), or
the piece's own "path".
Refuses (per house): wrong level; any mesh that does not load; an existing actor with the label unless
replace=true (then it is destroyed first, by label AND tag match). Read back: per-component instance count ==
pieces. A batch STOPS at the first failed house (standing rule 6 shape: no brute-forcing through failures).
Does NOT save.
"""
import json as _json
import math as _m
import traceback as _tb
from collections import defaultdict as _dd
import unreal as _u

SPEC = _json.loads(r'''__SPEC__''')

_w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
_eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
_mesh_cache = {}
_mat_cache = {}
_by_label = None


def _p(o):
    return o.get_path_name().split(".")[0] if o is not None else None


def _override(house, name, ps):
    """Set the ISM's material override EXPLICITLY both ways -- [mic] when the pieces carry a "material", [] when
    not -- because SetKitInstances REUSES a same-named ISM and SetStaticMesh never touches OverrideMaterials
    (StaticMeshComponent.cpp:2335-2426), so a stale grade would survive an update-in-place. Through
    set_editor_property, whose PreEditChange -> Modify dirties the OFPA package (PyWrapperObject.cpp:994-998);
    SetMaterial does not (MeshComponent.cpp:63-142). Design review 2026-10-11 Q1/Q2.
    Read back: the SERIALIZED override list (primary), and get_material(0) as the functional check -- reported,
    not gated, since GetMaterial may substitute a Nanite override material (StaticMeshComponentHelper.h:150-161,
    review S1)."""
    cname = "ISM_" + name[3:]
    ism = [c for c in house.get_components_by_class(_u.InstancedStaticMeshComponent) if c.get_name() == cname]
    if len(ism) != 1:
        return {"ok": False, "err": "override: %d ISMs named %s" % (len(ism), cname)}
    ism = ism[0]
    mp = ps[0].get("material")
    want = [_mat_cache[mp]] if mp else []
    have = [_p(m) for m in (ism.get_editor_property("override_materials") or [])]
    if have != [_p(m) for m in want]:
        ism.set_editor_property("override_materials", want)
    rb = [_p(m) for m in (ism.get_editor_property("override_materials") or [])]
    ok = rb == ([mp] if mp else [])
    r = {"material_want": mp, "override_readback": rb, "material0": _p(ism.get_material(0))}
    if not ok:
        r.update(ok=False, err="override read-back %s, wanted %s" % (rb, mp))
    return r


def _labels():
    global _by_label
    if _by_label is None:
        _by_label = _dd(list)
        for a in _eas.get_all_level_actors():
            _by_label[a.get_actor_label()].append(a)
    return _by_label


def _trace_landscape(x, y, out):
    # Seat on the LANDSCAPE only (the 2026-08-29 canopy-trace lesson, LESSONS 26170). LineTraceMulti stops at
    # the FIRST BLOCKING hit (KismetSystemLibrary.h:1273), so a blocking tree/boulder/house is added to the
    # ignore list and the trace repeated (at most 4 passes) -- audit F3.
    ignore, land, hits = [], [], []
    for _pass in range(4):
        hits = _u.SystemLibrary.line_trace_multi(
            _w, _u.Vector(x, y, 500000.0), _u.Vector(x, y, -500000.0),
            _u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore, _u.DrawDebugTrace.NONE, True) or []
        land = [h for h in hits
                if h.to_tuple()[9] is not None
                and h.to_tuple()[9].get_class().get_name() in ("Landscape", "LandscapeStreamingProxy")]
        if land:
            break
        block = [h.to_tuple()[9] for h in hits if h.to_tuple()[0] and h.to_tuple()[9] is not None]
        if not block:
            break
        ignore.extend(block)
    out["trace_ignored"] = [a.get_actor_label() for a in ignore]
    out["trace_hits"] = len(hits)
    if not land:
        raise RuntimeError("ground trace found no landscape hit under (%.0f, %.0f) (n hits %d)" % (x, y, len(hits)))
    return land[0].to_tuple()[4].z


def _build(spec):
    out = {"ok": False, "label": spec.get("label")}
    try:
        lvl = _w.get_path_name().split(".")[0]
        out["level"] = lvl
        if lvl != spec["level"]:
            raise RuntimeError("open level is %s, spec wants %s" % (lvl, spec["level"]))
        tags = [str(t) for t in spec.get("tags", [])]
        # Audit F1: an empty tag list would make the replace guard vacuous (all() over nothing is True).
        if not tags:
            raise RuntimeError("tags must not be empty")

        # Audit F2: load and check EVERY mesh before anything is destroyed (atomic replace).
        groups = _dd(list)
        for p in spec["pieces"]:
            groups[p["mesh"]].append(p)
        meshes = {}
        for name in groups:
            path = groups[name][0].get("path") or "/Game/Megascans/3D_Assets/%s/%s" % (name[3:], name)
            m = _mesh_cache.get(path)
            if m is None:
                m = _u.EditorAssetLibrary.load_asset(path)
                if m is None or not isinstance(m, _u.StaticMesh):
                    raise RuntimeError("mesh does not load as StaticMesh: " + path)
                _mesh_cache[path] = m
            meshes[name] = m
            # 2026-10-11 roof variety: an optional per-piece "material" (one ISM per mesh -> the group must agree),
            # loaded BEFORE anything is destroyed, like the meshes (audit F2's atomic replace)
            mats = set(p.get("material") for p in groups[name])
            if len(mats) != 1:
                raise RuntimeError("pieces of %s disagree on material: %s" % (name, sorted(str(x) for x in mats)))
            mp = mats.pop()
            if mp and mp not in _mat_cache:
                mi = _u.EditorAssetLibrary.load_asset(mp)
                if mi is None or not isinstance(mi, _u.MaterialInterface):
                    raise RuntimeError("material does not load as MaterialInterface: " + mp)
                _mat_cache[mp] = mi

        same = [a for a in _labels().get(spec["label"], []) if a is not None]
        house = None
        if spec.get("update_in_place"):
            # 2026-10-08: change the instance lists of an EXISTING house without destroying it, so its actor
            # identity (external package, GUID) survives -- HLOD setup's source lists and the saved navmesh both
            # refer to it. Exactly one same-label actor, carrying the tags, a plain AActor; else refuse.
            if len(same) != 1:
                raise RuntimeError("update_in_place: %d actors labelled %s (need exactly 1)" % (len(same), spec["label"]))
            house = same[0]
            if not all(_u.Name(t) in house.tags for t in tags) or house.get_class().get_name() != "Actor":
                raise RuntimeError("update_in_place: %s is not a tagged kit-house AActor" % spec["label"])
            # identity by PROPERTY too (rule 8, audit 2026-10-09 F6): the placed actor must still be where the
            # manifest says, or the new instances would land on a drifted house silently
            _hl, _hy = house.get_actor_location(), house.get_actor_rotation().yaw
            _dyaw = abs((_hy - float(spec["yaw_deg"]) + 180.0) % 360.0 - 180.0)
            if abs(_hl.x - spec["loc_cm"][0]) > 1.0 or abs(_hl.y - spec["loc_cm"][1]) > 1.0 or _dyaw > 0.01:
                raise RuntimeError("update_in_place: %s is at (%.1f, %.1f) yaw %.3f, manifest says (%.1f, %.1f) yaw %.3f"
                                   % (spec["label"], _hl.x, _hl.y, _hy, spec["loc_cm"][0], spec["loc_cm"][1],
                                      float(spec["yaw_deg"])))
            same = []
            out["updated_in_place"] = True
        if same:
            if not spec.get("replace"):
                raise RuntimeError("an actor labelled %s exists (pass replace)" % spec["label"])
            for a in same:
                if not all(_u.Name(t) in a.tags for t in tags):
                    raise RuntimeError("label %s matches an actor WITHOUT the house tags -- refusing to destroy it"
                                       % spec["label"])
            for a in same:
                if not _eas.destroy_actor(a):
                    raise RuntimeError("destroy_actor returned False for %s" % spec["label"])
            _labels()[spec["label"]] = []
            out["replaced"] = len(same)

        loc = list(spec["loc_cm"])
        yaw0 = float(spec["yaw_deg"])
        if house is not None:
            pass   # update in place: the actor keeps its transform; only instance lists change below
        elif spec.get("ground_trace"):
            tl = spec.get("trace_local_xy") or [0.0, 0.0]
            c0, s0 = _m.cos(_m.radians(yaw0)), _m.sin(_m.radians(yaw0))
            tx = loc[0] + c0 * float(tl[0]) - s0 * float(tl[1])
            ty = loc[1] + s0 * float(tl[0]) + c0 * float(tl[1])
            out["trace_xy"] = [tx, ty]
            loc[2] = _trace_landscape(tx, ty, out) + float(spec.get("ground_offset_cm", 0.0))
            out["ground_z"] = loc[2]
        if house is None:
            t = _u.Transform(_u.Vector(*loc), _u.Rotator(0.0, 0.0, yaw0), _u.Vector(1, 1, 1))
            r = _u.LandscapeLabTools.spawn_kit_house(t, spec["label"], [_u.Name(x) for x in tags],
                                                     _u.Vector(*spec["box_center_cm"]), _u.Vector(*spec["box_extent_cm"]))
            house, ok, err = (r if isinstance(r, tuple) else (None, False, "unexpected return %r" % (r,)))
            if not ok or house is None:
                raise RuntimeError("SpawnKitHouse failed: %s" % err)
            _labels()[spec["label"]] = [house]

        def _xf(p, mesh):
            s = p.get("scale") or [1.0, 1.0, 1.0]
            x, y, z, yaw = float(p["x"]), float(p["y"]), float(p["z"]), float(p["yaw"])
            if p.get("fit") == "bounds":
                # x, y = where the BOUNDS CENTRE goes, z = where the BOUNDS BOTTOM goes (house frame). Read the
                # mesh's local bounds LIVE (pivots on these roofs sit 20-201 cm off and are not base-centred).
                # get_bounds() includes any bounds EXTENSION (StaticMesh.cpp:7303-7315), which would shift the
                # fit silently -- refuse unless both extensions are zero (roof audit 2026-10-06 question).
                for pn in ("positive_bounds_extension", "negative_bounds_extension"):
                    v = mesh.get_editor_property(pn)
                    if abs(v.x) + abs(v.y) + abs(v.z) > 0.01:
                        raise RuntimeError("%s has a non-zero %s %s -- bounds fit would be off" % (p["mesh"], pn, v))
                b = mesh.get_bounds()
                o, e = b.origin, b.box_extent
                ox, oy = o.x * s[0], o.y * s[1]
                c, sn = _m.cos(_m.radians(yaw)), _m.sin(_m.radians(yaw))
                x -= c * ox - sn * oy
                y -= sn * ox + c * oy
                z -= (o.z - e.z) * s[2]
            return _u.Transform(_u.Vector(x, y, z), _u.Rotator(0.0, 0.0, yaw), _u.Vector(*[float(v) for v in s]))

        comp = {}
        for name, ps in groups.items():
            xs = [_xf(p, meshes[name]) for p in ps]
            n, ok2, err2 = _u.LandscapeLabTools.set_kit_instances(house, meshes[name], xs, _u.Name("ISM_" + name[3:]))
            comp[name] = {"want": len(ps), "got": int(n), "ok": bool(ok2), "err": str(err2)}
            if ok2:
                comp[name].update(_override(house, name, ps))
        out["components"] = comp
        lo = house.get_actor_location()
        out["actor"] = {"label": house.get_actor_label(), "loc": [lo.x, lo.y, lo.z],
                        "yaw": house.get_actor_rotation().yaw, "tags": [str(x) for x in house.tags]}
        out["n_pieces"] = len(spec["pieces"])
        out["ok"] = all(c["ok"] and c["got"] == c["want"] for c in comp.values())
        if not out["ok"]:
            out["error"] = "instance read-back mismatch"
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
        out["traceback"] = _tb.format_exc()
    return out


if "batch" in SPEC:
    _res = []
    for _s in SPEC["batch"]:
        _o = _build(_s)
        # keep the batch result small: per house only what the verifier needs
        _res.append({k: _o.get(k) for k in ("ok", "label", "error", "traceback", "ground_z", "trace_xy",
                                             "actor", "n_pieces", "replaced", "trace_ignored", "updated_in_place")})
        if not _o["ok"]:
            break
    _final = {"ok": bool(_res) and all(r["ok"] for r in _res) and len(_res) == len(SPEC["batch"]),
              "n_requested": len(SPEC["batch"]), "n_done": sum(1 for r in _res if r["ok"]), "houses": _res}
else:
    _final = _build(SPEC)
print("__LL__" + _json.dumps(_final, indent=1, default=str))
