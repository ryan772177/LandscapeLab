"""brief5_c2_showroom.py -- Brief 5 C2: view spruce_half_01 in the vendor demo
map and read how the demo places it.

READ-ONLY. Assumes the editor was launched on the Showroom map (no load here,
no save). Enumerates every actor/component that references spruce_half_01,
reports placement class (HISM/ISM/StaticMeshActor), instance count, the material
on the imposter (last) slot, and any component custom primitive data. Frames a
cluster and takes stills:
  - lit auto at ~150 m and ~300 m (the desk's ask; viewmode off)
  - lit forced-card at ~150 m: our T3 hold lowered spruce_half_01's card
    screen-size on the SHARED asset (0.17 -> 0.02642), so the imposter no longer
    onsets until ~600 m even here; forcing the last LOD exhibits the imposter
    under the demo's OWN placement, apples-to-apples with the original defect.
Reads a scratch {out_prefix}. Prints placement + shot names.
"""
import json
import math
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_c2.json"), encoding="utf-8"))
PFX = CFG["out_prefix"]
MESH_KEY = "spruce_half_01"

out = {"ok": False}
try:
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name()

    placements = []
    locs = []   # world locations of spruce_half instances/actors
    for a in eas.get_all_level_actors():
        # instanced components
        for comp in a.get_components_by_class(unreal.StaticMeshComponent):
            sm = comp.static_mesh
            if not sm or MESH_KEY not in sm.get_path_name().lower():
                continue
            rec = {"actor": a.get_actor_label(), "comp_class": comp.get_class().get_name(),
                   "mesh": sm.get_path_name().split(".")[0]}
            try:
                rec["num_lods"] = int(sm.get_num_lods())
            except Exception:
                pass
            # material on the last (imposter) slot
            try:
                mats = comp.get_materials()
                rec["material_slots"] = [m.get_path_name().split(".")[0] if m else None
                                         for m in mats]
            except Exception as e:
                rec["material_error"] = str(e)
            # custom primitive data (component level)
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
                        loc = t.translation
                        locs.append((loc.x, loc.y, loc.z))
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
        # pick a target cluster = the densest instance's neighbourhood centroid
        import statistics
        cx = statistics.median([p[0] for p in locs])
        cy = statistics.median([p[1] for p in locs])
        cz = statistics.median([p[2] for p in locs])
        top = max(p[2] for p in locs)
        target = unreal.Vector(cx, cy, cz + 800.0)  # aim ~8 m up the trunks
        out["target_cm"] = [round(cx, 1), round(cy, 1), round(cz, 1)]

        def shoot(dist_m, name, force_card):
            # place camera dist_m south of target, at target height, look north
            d = dist_m * 100.0
            eye = unreal.Vector(cx - d, cy, cz + 800.0)
            look = target - eye
            yaw = math.degrees(math.atan2(look.y, look.x))
            pitch = math.degrees(math.atan2(look.z, math.hypot(look.x, look.y)))
            ues.set_level_viewport_camera_info(
                eye, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
            les.editor_set_game_view(True)
            unreal.SystemLibrary.execute_console_command(w, "viewmode lit")
            fl = 8 if force_card else -1
            unreal.SystemLibrary.execute_console_command(w, "r.ForceLOD %d" % fl)
            unreal.SystemLibrary.execute_console_command(w, "foliage.ForceLOD %d" % fl)
            unreal.AutomationLibrary.take_high_res_screenshot(3840, 2160, name)
            return {"name": name, "dist_m": dist_m, "force_card": force_card,
                    "eye_cm": [round(eye.x, 1), round(eye.y, 1), round(eye.z, 1)],
                    "yaw": round(yaw, 1), "pitch": round(pitch, 1),
                    "r.ForceLOD_readback": int(
                        unreal.SystemLibrary.get_console_variable_int_value("r.ForceLOD"))}

        out["shots"] = [
            shoot(150.0, PFX + "_150_lit", False),
            shoot(300.0, PFX + "_300_lit", False),
            shoot(150.0, PFX + "_150_card", True),
        ]
    else:
        out["_note"] = "no spruce_half_01 instances found in this level"
    out["ok"] = True
    dest = os.path.join(root, "research", "brief5", "input", "c2_showroom.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written"] = dest
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1400:]
print("__LL__" + json.dumps({"ok": out.get("ok"), "n_placements": out.get("n_placements"),
                             "placements": out.get("placements"), "shots": out.get("shots"),
                             "error": out.get("error"), "written": out.get("written")},
                            default=str))
