"""brief5_c1_renderdata.py -- Brief 5 C1 no-op branch: read back the LOD
ScreenSize arrays actually carried by the meshes the placed HISM foliage
components reference, and compare against t3_hold.json.

READ-ONLY. Enumerates every foliage/HISM/ISM component in the loaded level,
resolves its StaticMesh, and reports, per unique mesh: get_num_lods and the
editor-subsystem get_lod_screen_sizes array. That accessor returns the
RENDER-DATA array (RenderData->ScreenSize[i], StaticMeshEditorSubsystem.cpp:
1003-1008) -- the array the runtime LOD selection actually reads, not the source
model. So a NO-OP colour verdict PLUS render-data sizes that match t3_hold.json
rules out a stale render-data array (the DDC/proxy-cache hypothesis) and points
at a component override or a runtime selection path; a MISMATCH here is itself
the DDC/build-staleness smoking gun. Only run this branch when C1's colour
verdict is NO-OP.
"""
import json
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CARD = {"/Game/KiteDemo/Environments/Trees/ScotsPineTall_01/ScotsPineTall_01":
        ("ConiferPine", [1.50451, 0.33642, 0.23788, 0.03818]),
        "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01":
        ("SpruceSub", [1.0, 0.99, 0.6, 0.35, 0.02642])}

out = {"ok": False, "_note": "get_lod_screen_sizes returns the RENDER-DATA "
       "ScreenSize array (StaticMeshEditorSubsystem.cpp:1003-1008) -- what the "
       "runtime reads; compared to t3_hold.json targets. Mismatch = stale "
       "render-data/DDC; match under a NO-OP colour verdict = not staleness."}
try:
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name()
    _rd_out = "c1_renderdata.json"
    try:
        _cfg = json.load(open(os.path.join(root, "_scratch_c1.json"),
                              encoding="utf-8"))
        expect = _cfg.get("expected_level", "Alpine8K")
        # basename only -- never let a scratch value escape research/brief5/input
        _rd_out = os.path.basename(_cfg.get("renderdata_out", "c1_renderdata.json"))
    except Exception:
        expect = "Alpine8K"
    if expect.lower() not in out["level"].lower():
        out["error"] = "WRONG LEVEL: expected %r, editor has %r (rule 11)" % (
            expect, out["level"])
        raise SystemExit

    seen = {}   # mesh_path -> {num_lods, screen_sizes, n_components, n_instances}
    for a in eas.get_all_level_actors():
        for comp in a.get_components_by_class(
                unreal.InstancedStaticMeshComponent):
            sm = comp.static_mesh
            if not sm:
                continue
            p = sm.get_path_name().split(".")[0]
            rec = seen.setdefault(p, {"n_components": 0, "n_instances": 0})
            rec["n_components"] += 1
            try:
                rec["n_instances"] += int(comp.get_instance_count())
            except Exception:
                pass
            if "num_lods" not in rec:
                try:
                    rec["num_lods"] = int(sm.get_num_lods())
                except Exception as e:
                    rec["num_lods"] = "err: %s" % e
                try:
                    rec["screen_sizes"] = [round(float(x), 5)
                                           for x in smes.get_lod_screen_sizes(sm)]
                except Exception as e:
                    rec["screen_sizes"] = "err: %s" % e
    # focus report on the two card species
    report = {}
    for p, (sp, target) in CARD.items():
        rec = seen.get(p)
        if rec is None:
            report[sp] = {"present_in_level": False}
            continue
        ss = rec.get("screen_sizes")
        match = (isinstance(ss, list) and len(ss) == len(target) and
                 all(abs(a - b) < 1e-3 for a, b in zip(ss, target)))
        report[sp] = {"present_in_level": True, "n_components": rec["n_components"],
                      "n_instances": rec["n_instances"], "num_lods": rec.get("num_lods"),
                      "screen_sizes": ss, "t3_hold_target": target,
                      "matches_t3_hold": bool(match)}
    out["card_species"] = report
    out["all_ism_meshes"] = {p: {k: v for k, v in r.items()
                                 if k in ("n_components", "n_instances", "num_lods")}
                             for p, r in seen.items()}
    out["ok"] = True
    dest = os.path.join(root, "research", "brief5", "input", _rd_out)
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written"] = dest
except SystemExit:
    pass
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1200:]
print("__LL__" + json.dumps({"ok": out.get("ok"), "card_species": out.get("card_species"),
                             "error": out.get("error"), "written": out.get("written")},
                            default=str))
