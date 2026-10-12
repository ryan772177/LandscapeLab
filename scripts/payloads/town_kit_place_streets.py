"""town_kit_place_streets -- place the plan's STREETS (only) as primitive slabs (2026-10-10, organic re-layout).

Input (substituted): CFG = JSON {"level": "/Game/Alpine8K", "plan": "<abs path>", "commit": bool}

The organic layout replaces the street network but not the landmark/spire (same plaza rule, same place) and the
kit houses are placed by town_kit_place. So this places ONLY kind "streets", tagged [LandscapeLab.City, "streets"]
and labelled City_St_%03d, exactly as scripts/city_place_payload.txt did (same mesh, scale, seat convention:
pitch +, roll NEGATED -- measured there over 838 streets). A COMMIT REFUSES if any City "streets" actor already
exists (clear them first with town_kit_clear.py --tag LandscapeLab.City --kinds streets --expect N); a dry run
reports them and still traces. Refuses any street missing pitch_deg/roll_deg.
Ground is PRE-TRACED for every street before anything spawns, ignoring foliage, WorldPartitionHLOD proxies and
both town tags (check_trace_ignores; LESSONS 2026-10-08f). Counted back from the world by tag+kind (rule 12).
Dry run (commit false): traces EVERY street and reports plan-vs-trace drift; spawns nothing. Does NOT save.
"""
import json as _json
import traceback as _tb
import unreal as _u

CFG = _json.loads(r'''__CFG__''')
TAG, KIND = "LandscapeLab.City", "streets"
TOWN_TAGS = (TAG, "LandscapeLab.TownKit")
_out = {"ok": False, "commit": bool(CFG.get("commit"))}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    if _w.get_path_name().split(".")[0] != CFG["level"]:
        raise RuntimeError("open level is %s, cfg wants %s" % (_w.get_path_name(), CFG["level"]))
    with open(CFG["plan"], "r", encoding="utf-8") as _fh:
        _p = _json.load(_fh)
    _S = _p["streets"]
    if not _S:
        raise RuntimeError("the plan has no streets")
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _existing = [a for a in _actors if TAG in [str(t) for t in a.tags] and KIND in [str(t) for t in a.tags]]
    _out["existing_city_streets"] = len(_existing)
    # refuse only a COMMIT over existing streets: a dry run must be able to validate the new network BEFORE the
    # destructive teardown (world-tools audit 2026-10-10 F3); City-tagged actors are trace-ignored either way
    if _existing and CFG.get("commit"):
        raise RuntimeError("%d City streets already in the level -- clear them first" % len(_existing))
    _bad = [i for i, s in enumerate(_S) if "pitch_deg" not in s or "roll_deg" not in s]
    if _bad:
        # F4: the organic planner always writes both; a missing key is a defect, never a flat slab
        raise RuntimeError("%d plan streets lack pitch_deg/roll_deg (first %s)" % (len(_bad), _bad[:5]))
    _mesh = _u.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    _b = _mesh.get_bounds().box_extent
    if abs(_b.x - 50.0) > 1.0 or abs(_b.z - 50.0) > 1.0:
        raise RuntimeError("engine Cube half-extent %s, not 50 cm" % _b)
    _ign, _n_hlod, _n_town = [], 0, 0
    for _a in _actors:
        if isinstance(_a, _u.InstancedFoliageActor):
            _ign.append(_a)
        elif _a.get_class().get_name() == "WorldPartitionHLOD":
            _ign.append(_a)
            _n_hlod += 1
        elif any(t in [str(x) for x in _a.tags] for t in TOWN_TAGS):
            _ign.append(_a)
            _n_town += 1
    _out["trace_ignored"] = {"hlod": _n_hlod, "town": _n_town, "total": len(_ign)}

    def _ground(x, y, zh):
        _h = _u.SystemLibrary.line_trace_single(_w, _u.Vector(x, y, zh + 20000.0), _u.Vector(x, y, zh - 20000.0),
                                                _u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, _ign,
                                                _u.DrawDebugTrace.NONE, True)
        if _h and _h.to_tuple()[9] is not None and _h.to_tuple()[9].get_class().get_name() in (
                "Landscape", "LandscapeStreamingProxy"):
            return float(_h.to_tuple()[4].z), True
        return float(zh), False
    # EVERY street, dry run included: the dry run is the validation BEFORE the teardown, and "0 misses" over a
    # 40-street sample was a verdict over 40 of 371 (design review 2026-10-10 C2)
    _sample = _S
    _z = [_ground(s["loc_cm"][0], s["loc_cm"][1], s["loc_cm"][2]) for s in _sample]
    _miss = sum(1 for z, h in _z if not h)
    _d = sorted(z - s["loc_cm"][2] for (z, h), s in zip(_z, _sample) if h)
    _out["traced"], _out["trace_misses"] = len(_sample), _miss
    if _d:
        _out["plan_vs_trace_cm"] = {"n": len(_d), "p50": round(_d[len(_d) // 2], 2), "min": round(_d[0], 2),
                                    "max": round(_d[-1], 2)}
    if not CFG.get("commit"):
        _out["ok"] = _miss == 0
    else:
        if _miss:
            raise RuntimeError("%d of %d street traces missed the landscape -- refusing to place" % (_miss, len(_S)))
        for _i, (_s, (_gz, _h)) in enumerate(zip(_S, _z)):
            _a2 = _eas.spawn_actor_from_class(_u.StaticMeshActor, _u.Vector(_s["loc_cm"][0], _s["loc_cm"][1], _gz + 10.0),
                                              _u.Rotator(-_s["roll_deg"], _s["pitch_deg"], _s["yaw_deg"]))
            _a2.static_mesh_component.set_editor_property("static_mesh", _mesh)
            _a2.set_actor_scale3d(_u.Vector(_s["len_cm"] / 100.0, _s["width_cm"] / 100.0, 0.2))
            _a2.set_actor_label("City_St_%03d" % _i)
            _a2.tags = [TAG, KIND]
        _n = sum(1 for a in _eas.get_all_level_actors()
                 if TAG in [str(t) for t in a.tags] and KIND in [str(t) for t in a.tags])
        _out["counted_in_world"] = _n
        _out["ok"] = _n == len(_S)
        if not _out["ok"]:
            _out["error"] = "counted %d City streets, plan has %d" % (_n, len(_S))
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, default=str))
