"""brief5_c2_discover.py -- Brief 5 C2 discovery. READ-ONLY.

Assumes the editor was launched on the Showroom demo map (no load, no save).
Gates on the expected level name (rule 11). Enumerates every actor/component
that references spruce_half_01, reports placement class (HISM/ISM/
StaticMeshActor), instance count, material slots (incl. the imposter/last slot),
and any component custom primitive data. Computes a target cluster centroid for
framing and writes it to research/brief5/input/c2_showroom.json. Takes NO shot
(shots are one-per-invocation in brief5_c2_shot.py -- one HighResShot per exec,
because HighResShot mutates ONE global config and the viewport camera is shared
state).
"""
import json
import os
import statistics
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_c2.json"), encoding="utf-8"))
EXPECT_LEVEL = CFG.get("expected_level", "Showroom")
MESH_KEY = "spruce_half_01"

out = {"ok": False}
try:
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name()
    if EXPECT_LEVEL.lower() not in out["level"].lower():
        out["error"] = "WRONG LEVEL: expected %r, editor has %r (rule 11)" % (
            EXPECT_LEVEL, out["level"])
        raise SystemExit

    placements, locs = [], []
    for a in eas.get_all_level_actors():
        for comp in a.get_components_by_class(unreal.StaticMeshComponent):
            sm = comp.static_mesh
            if not sm or MESH_KEY not in sm.get_path_name().lower():
                continue
            rec = {"actor": a.get_actor_label(),
                   "comp_class": comp.get_class().get_name(),
                   "mesh": sm.get_path_name().split(".")[0]}
            try:
                rec["num_lods"] = int(sm.get_num_lods())
            except Exception:
                pass
            try:
                rec["material_slots"] = [m.get_path_name().split(".")[0] if m else None
                                         for m in comp.get_materials()]
            except Exception as e:
                rec["material_error"] = str(e)
            try:
                cpd = comp.get_editor_property("custom_primitive_data")
                rec["custom_primitive_data"] = list(cpd.data) if cpd else []
            except Exception as e:
                rec["cpd_error"] = str(e)
            if isinstance(comp, unreal.InstancedStaticMeshComponent):
                try:
                    n = int(comp.get_instance_count())
                    rec["instance_count"] = n
                    for i in range(min(n, 400)):
                        t = comp.get_instance_transform(i, world_space=True)
                        locs.append((t.translation.x, t.translation.y, t.translation.z))
                except Exception as e:
                    rec["inst_error"] = str(e)
            else:
                loc = a.get_actor_location()
                locs.append((loc.x, loc.y, loc.z))
            placements.append(rec)
    out["placements"] = placements
    out["n_placements"] = len(placements)
    out["n_locations_sampled"] = len(locs)
    if locs:
        out["target_cm"] = [round(statistics.median([p[0] for p in locs]), 1),
                            round(statistics.median([p[1] for p in locs]), 1),
                            round(statistics.median([p[2] for p in locs]), 1)]
    else:
        out["_note"] = "no spruce_half_01 instances found in this level"
    out["ok"] = True
except SystemExit:
    pass
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1400:]
try:
    dest = os.path.join(root, "research", "brief5", "input", "c2_showroom.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written"] = dest
except Exception as e:
    out["write_error"] = str(e)
print("__LL__" + json.dumps({"ok": out.get("ok"), "level": out.get("level"),
                             "n_placements": out.get("n_placements"),
                             "target_cm": out.get("target_cm"),
                             "placements": out.get("placements"),
                             "error": out.get("error")}, default=str))
