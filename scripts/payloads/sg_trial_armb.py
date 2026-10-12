import json as _json
import traceback as _tb
import unreal as _u
# Shape Grammar trial ARM B (research/town_kit/SHAPE_GRAMMAR_TRIAL.md, review changes 1-12). PCG does ONLY the
# grammar fill: CreatePoints (one point per facade run, bounds along local X = run length, per-run seed) ->
# SubdivideSegment (modules_info nominal sizes, grammar string) -> graph Output. Python reads back Symbol + position
# per output point; the host turns them into kit pieces and places them with the SAME build payload as arms A/C.
# MODE "build": graph + PCGVolume + generate_local (async). MODE "read": poll, read back, clean up.
# Scratch only: asset /Game/Scratch/SGTrial/PCG_SGTrial_<tag> (NOT saved), volume label SGTrial_PCG_<tag>, on the
# rig level. Refuses any other level (rule 11).
CFG = _json.loads(r"""__CFG__""")
_out = {"ok": False, "error": None, "mode": CFG["mode"], "tag": CFG["tag"]}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    if _w.get_path_name().split(".")[0] != CFG["level"]:
        raise RuntimeError("REFUSE (rule 11): level is " + _w.get_path_name())
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _label = "SGTrial_PCG_" + CFG["tag"]
    _vols = [a for a in _eas.get_all_level_actors() if a.get_actor_label() == _label]

    def _pin_labels(node, which):
        return [str(p.get_editor_property("properties").get_editor_property("label"))
                for p in node.get_editor_property(which)]

    if CFG["mode"] == "build":
        for a in _vols:                                   # replace an earlier run's volume
            _eas.destroy_actor(a)
        _tools = _u.AssetToolsHelpers.get_asset_tools()
        _dir, _name = "/Game/Scratch/SGTrial", "PCG_SGTrial_" + CFG["tag"]
        _path = _dir + "/" + _name
        if _u.EditorAssetLibrary.does_asset_exist(_path):
            _u.EditorAssetLibrary.delete_asset(_path)
        _g = _tools.create_asset(_name, _dir, _u.PCGGraph, _u.PCGGraphFactory())
        if _g is None:
            raise RuntimeError("create_asset PCGGraph -> None")
        _cn, _cs = _g.add_node_of_type(_u.PCGCreatePointsSettings)
        _sn, _ss = _g.add_node_of_type(_u.PCGSubdivideSegmentSettings)
        _pts = []
        for i, seg in enumerate(CFG["segments"]):
            L = float(seg["length_cm"])
            _t = _u.Transform(location=_u.Vector(0.0, i * 1000.0, 0.0))
            _pts.append(_u.PCGPoint(transform=_t, density=1.0, bounds_min=_u.Vector(-L / 2.0, -50.0, 0.0),
                                    bounds_max=_u.Vector(L / 2.0, 50.0, 100.0), seed=int(seg["seed"])))
        _cs.set_editor_property("points_to_create", _pts)
        _mods = [_u.PCGSubdivisionSubmodule(symbol=_u.Name(k), size=float(v), scalable=False)
                 for k, v in sorted(CFG["modules_cm"].items())]
        _ss.set_editor_property("modules_info", _mods)
        _ss.set_editor_property("grammar_selection", _u.PCGGrammarSelection(grammar_string=CFG["grammar"]))
        _ss.set_editor_property("accept_incomplete_subdivision", bool(CFG["accept_incomplete_subdivision"]))
        _ss.set_editor_property("subdivision_axis", _u.PCGSplitAxis.X)
        _ss.set_editor_property("use_seed_attribute", bool(CFG.get("use_seed_attribute", True)))  # review change 7
        # The struct method selector.set_point_property() returns True and changes NOTHING (measured 2026-10-10:
        # read-back stays "@Last"; the node then fails its seed accessor and skips every input -> 0 points). The
        # Blueprint helper returns the BASE selector, which will not nativize into an InputSelector. import_text in
        # the struct's own export format does take -- and it is READ BACK (rule 12) before anything runs.
        _sel = _ss.get_editor_property("seed_attribute")
        _sel.import_text("PCGBegin($Seed)PCGEnd")
        _ss.set_editor_property("seed_attribute", _sel)
        _seed_txt = str(_ss.get_editor_property("seed_attribute").export_text())
        _out["seed_selector"] = _seed_txt
        if bool(CFG.get("use_seed_attribute", True)) and "$Seed" not in _seed_txt:
            raise RuntimeError("seed_attribute reads back %r, not $Seed" % _seed_txt)
        # READ BACK what the settings hold (rule 12): a setter that ran is not a value that took
        _pts_rb = _cs.get_editor_property("points_to_create")
        _out["readback"] = {
            "modules": [[str(m.get_editor_property("symbol")), m.get_editor_property("size")]
                        for m in _ss.get_editor_property("modules_info")],
            "grammar": _ss.get_editor_property("grammar_selection").get_editor_property("grammar_string"),
            "points_to_create": len(_pts_rb),
            "first_point_bounds": [[_pts_rb[0].bounds_min.x, _pts_rb[0].bounds_max.x]] if len(_pts_rb) else None,
            "axis": str(_ss.get_editor_property("subdivision_axis"))}
        _outn = _g.get_output_node()
        # REAL pin labels, read off the nodes (LESSONS 2026-09-21: Input/Output are not "In"/"Out"; AddEdge is
        # non-raising), and the edges READ BACK after wiring (rule 12)
        _c_out, _s_in, _s_out = _pin_labels(_cn, "output_pins"), _pin_labels(_sn, "input_pins"), _pin_labels(_sn, "output_pins")
        _o_in = _pin_labels(_outn, "input_pins")
        _out["pins"] = {"create_out": _c_out, "subdiv_in": _s_in, "subdiv_out": _s_out, "output_in": _o_in}
        if CFG.get("bypass_subdivide"):
            # DIAGNOSTIC CONTROL: CreatePoints straight to Output -- proves the read-back path independently
            _g.add_edge(_cn, _u.Name(_c_out[0]), _outn, _u.Name(_o_in[0]))
            _g.add_edge(_cn, _u.Name(_c_out[0]), _sn, _u.Name(_s_in[0]))
        else:
            _g.add_edge(_cn, _u.Name(_c_out[0]), _sn, _u.Name(_s_in[0]))
            _g.add_edge(_sn, _u.Name(_s_out[0]), _outn, _u.Name(_o_in[0]))
        _wired = []
        for node, which in ((_cn, "output_pins"), (_sn, "output_pins")):
            for p in node.get_editor_property(which):
                _wired.append(len(p.get_editor_property("edges")))
        _out["edges_per_output_pin"] = _wired
        if (_wired[0] < 2) if CFG.get("bypass_subdivide") else (_wired[0] < 1 or _wired[1] < 1):
            raise RuntimeError("edges did not wire (read-back %s)" % _wired)
        _v = _eas.spawn_actor_from_class(_u.PCGVolume, _u.Vector(*CFG["volume_loc_cm"]))
        _v.set_actor_label(_label)
        _pc = _v.get_component_by_class(_u.PCGComponent)
        _pc.set_graph(_g)
        _pc.set_editor_property("seed", int(CFG["component_seed"]))
        _pc.generate_local(True)
        _out["generation_requested"] = True
        _out["ok"] = True
    else:
        if len(_vols) != 1:
            raise RuntimeError("expected 1 volume %s, found %d" % (_label, len(_vols)))
        _pc = _vols[0].get_component_by_class(_u.PCGComponent)
        _busy = bool(_pc.get_editor_property("generation_in_progress"))
        _done = bool(_pc.get_editor_property("generated"))
        _out.update({"in_progress": _busy, "generated": _done})
        if _busy or not _done:
            _out["ok"] = True                              # caller polls again
        else:
            _col = _pc.get_generated_graph_output()
            # audit F1: 5.8 emits UPCGPointArrayData (pcg.EnablePointArrayData default true, PCGContext.cpp:81),
            # a SIBLING of PCGPointData -- filter on the base class and convert (ToPointData copies points+metadata)
            _datas, _tagged = _col.get_typed_inputs(_u.PCGBasePointData)
            _out["point_datas"] = len(_datas)
            _out["point_data_classes"] = sorted(set(type(_d).__name__ for _d in _datas))
            _rows = []
            for _d in _datas:
                if not isinstance(_d, _u.PCGPointData):
                    _d = _d.to_point_data()
                _md = _d.const_metadata()
                if "first_bounds" not in _out and _d.get_points():
                    _p0 = _d.get_points()[0]
                    _out["first_bounds"] = [_p0.bounds_min.x, _p0.bounds_max.x, _p0.bounds_min.y, _p0.bounds_max.y]
                for _p in _d.get_points():
                    _loc = _p.transform.translation
                    _sym = str(_u.PCGMetadataAccessorHelpers.get_name_attribute(_p, _md, _u.Name("Symbol")))
                    _rows.append([round(_loc.x, 2), round(_loc.y, 2), _sym])
            _out["points"] = _rows
            _out["n_points"] = len(_rows)
            if CFG.get("cleanup", True):
                _pc.cleanup_local(True)
                _eas.destroy_actor(_vols[0])
            _out["ok"] = True
except Exception as _ex:
    _out["error"] = "%s: %s" % (type(_ex).__name__, _ex)
    _out["traceback"] = _tb.format_exc()[-1500:]
print("__LL__" + _json.dumps(_out, default=str))
