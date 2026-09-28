"""brief5_t2_cards.py -- Brief 5 T2: read back the two card LODs + all tree
materials. READ-ONLY (loads assets, reads properties; no set, no save, no spawn).

For ScotsPineTall_01 (billboard) and spruce_half_01 (imposter): last-LOD material
(via get_lod_material_slot -> get_material), its atlas textures + dims, frame grid
inference, whether view-dependent (tri count + name), and dithered_lod_transition
on EVERY tree material. Also T6 crown geometry (box extent XY -> crown radius;
z-extent -> proxy for blocked width) as a cheap read.

APIs verified (recon 2026-09-21): get_lod_material_slot (returns -1 past last
section), get_material(slot), MaterialEditingLibrary.get_material_used_textures,
tex.blueprint_get_size_x/y (RESIDENT-MIP caveat), material dithered_lod_transition
(Material.h:569), len(mesh.static_materials), get_num_triangles(lod).
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
# the four tree species meshes from the recipe (same source as tree_lod_probe)
_recipe = _json.load(open(_os.path.join(_root, "recipes", "alpine_8k.json"),
                          encoding="utf-8-sig"))
MESHES = [[s["name"], s["mesh"]]
          for s in (_recipe.get("foliage") or {}).get("species") or []
          if s.get("system") != "grass" and "role" not in s]
CARD_SPECIES = {"ConiferPine", "SpruceSub"}

out = {"ok": False, "meshes": [], "all_tree_material_dithered": {}}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary
    mel = _u.MaterialEditingLibrary

    def tex_dims(tex):
        try:
            return [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]
        except Exception as e:
            return "UNKNOWN: %s" % e

    for name, path in MESHES:
        rec = {"species": name, "path": path}
        m = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if not m:
            rec["error"] = "not found"
            out["meshes"].append(rec)
            continue
        nlod = int(ss.get_lod_count(m))
        rec["lod_count"] = nlod
        rec["num_material_slots"] = len(m.static_materials)
        # Auto Compute LOD Screen Size: the direct property is UE_DEPRECATED(5.7)
        # and not reflected to Python. Read via the reflected accessor if present;
        # else leave it to T3. Never abort the read-back over it.
        for _acc in ("get_auto_compute_lod_screen_size",):
            try:
                rec["auto_compute_lod_screen_size"] = bool(getattr(m, _acc)())
                break
            except Exception as _e:
                rec["auto_compute_lod_screen_size"] = "UNKNOWN(%s)" % _e
        rec["last_lod_triangles"] = int(m.get_num_triangles(nlod - 1))
        # last-LOD material slot(s)
        last = nlod - 1
        slots = []
        sec = 0
        while True:
            sl = ss.get_lod_material_slot(m, last, sec)
            if sl is None or int(sl) < 0:
                break
            slots.append(int(sl))
            sec += 1
        rec["last_lod_slots"] = slots
        # all-material dithered read + card material detail
        mats_info = []
        for i in range(len(m.static_materials)):
            mi = m.get_material(i)
            info = {"slot": i, "material": mi.get_path_name() if mi else None}
            if mi:
                base = mi.get_base_material() if hasattr(mi, "get_base_material") else None
                tgt = base or mi
                try:
                    info["dithered_lod_transition"] = bool(
                        tgt.get_editor_property("dithered_lod_transition"))
                except Exception as e:
                    info["dithered_lod_transition"] = "UNKNOWN: %s" % e
                out["all_tree_material_dithered"]["%s[%d]" % (name, i)] = \
                    info.get("dithered_lod_transition")
                # only detail the CARD material (last-LOD slot)
                if i in slots:
                    try:
                        texs = mel.get_material_used_textures(mi)
                        info["used_textures"] = [
                            {"path": t.get_path_name(),
                             "resident_dims": tex_dims(t)}
                            for t in texs if t]
                    except Exception as e:
                        info["used_textures_error"] = str(e)
                    info["is_card"] = True
                    info["view_dependent_guess"] = (
                        "octahedral_imposter" if rec["last_lod_triangles"] <= 8
                        else "crossed_billboard")
            mats_info.append(info)
        rec["materials"] = mats_info
        # T6 crown geometry (cheap): bounds box extent
        try:
            b = m.get_bounds()
            be = b.box_extent
            rec["bounds_extent_cm"] = [float(be.x), float(be.y), float(be.z)]
            rec["crown_radius_xy_cm"] = (float(be.x) + float(be.y)) / 2.0
            rec["height_cm"] = float(be.z) * 2.0
            rec["bounding_sphere_radius_cm"] = float(b.sphere_radius)
        except Exception as e:
            rec["bounds_error"] = str(e)
        out["meshes"].append(rec)
    out["ok"] = True
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "t2_cards.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

_status = {"ok": out.get("ok"), "error": out.get("error"),
           "written_to": out.get("written_to"),
           "dithered": out.get("all_tree_material_dithered")}
print("__LL__" + _json.dumps(_status, default=str))
