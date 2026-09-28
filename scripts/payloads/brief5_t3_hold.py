"""brief5_t3_hold.py -- Brief 5 T3 (HOLD). MUTATES two StaticMesh assets.

Duplicates ScotsPineTall_01 and spruce_half_01 to <name>_SRC (pristine,
unreferenced) FIRST, then applies fallback_hold.screen_sizes via
StaticMeshEditorSubsystem.set_lod_screen_sizes so the CARD LOD engages past the
512 m cull (never drawn live; HLOD Instancing still uses it). Read-back-driven:
if the set does not stick, Auto Compute LOD Screen Size is on -- turn it off and
retry. Verifies last-LOD triangle count + material-slot count UNCHANGED. Saves.

Fence (Brief 5 FOR_CLAUDE_CODE): modifies exactly these two meshes; no actor, no
FoliageType, no level, no HLOD layer, no Nanite toggle, no SetLods on a real mesh.

APIs verified (recon 2026-09-21): EditorAssetLibrary.duplicate_asset(src,dst);
StaticMeshEditorSubsystem.set_lod_screen_sizes(mesh,list)->bool /
get_lod_screen_sizes; StaticMesh.get_num_triangles(lod); len(static_materials);
set_auto_compute_lod_screen_size accessor (property deprecated 5.7);
EditorAssetLibrary.save_loaded_asset.
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project on the port (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
_ladder = _json.load(open(_os.path.join(_root, "research", "brief5", "derived",
                                        "derived_ladder.json")))


def _fh(species):
    for e in _ladder.get("species", []):
        if (e.get("species") or e.get("name")) == species:
            return (e.get("fallback_hold") or {}).get("screen_sizes")
    return None


# recipe gives the mesh paths (same source as the probe)
_recipe = _json.load(open(_os.path.join(_root, "recipes", "alpine_8k.json"),
                          encoding="utf-8-sig"))
_MESH = {s["name"]: s["mesh"]
         for s in (_recipe.get("foliage") or {}).get("species") or []}
TARGETS = [("ConiferPine", _MESH.get("ConiferPine")),
           ("SpruceSub", _MESH.get("SpruceSub"))]

out = {"ok": False, "meshes": []}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary

    def eq_list(a, b, tol=1e-4):
        if a is None or b is None or len(a) != len(b):
            return False
        return all(abs(float(x) - float(y)) < tol for x, y in zip(a, b))

    for species, path in TARGETS:
        rec = {"species": species, "path": path}
        new_sizes = _fh(species)
        rec["target_screen_sizes"] = new_sizes
        if path is None:
            rec["error"] = "no mesh path in recipe"
            out["meshes"].append(rec)
            continue
        m = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if m is None or new_sizes is None:
            rec["error"] = "mesh missing or no fallback_hold"
            out["meshes"].append(rec)
            continue
        # 0) pristine duplicate to _SRC (build before touching the original).
        # A FAILED duplicate STOPS this mesh -- never mutate the original without
        # its backup (auditor BLOCKER).
        src_path = path.rsplit(".", 1)[0] + "_SRC"
        if not eal.does_asset_exist(src_path):
            dup = eal.duplicate_asset(path, src_path)
            if not dup:
                rec["error"] = "DUPLICATE FAILED -- original NOT mutated"
                rec["saved"] = False
                out["meshes"].append(rec)
                continue
            rec["src_duplicate"] = src_path
            rec["src_saved"] = bool(eal.save_loaded_asset(dup))
        else:
            rec["src_duplicate"] = src_path + " (already existed)"
        # baseline invariants
        nlod = int(ss.get_lod_count(m))
        rec["lod_count"] = nlod
        rec["last_lod_tris_before"] = int(m.get_num_triangles(nlod - 1))
        rec["slots_before"] = len(m.static_materials)
        rec["screen_sizes_before"] = [float(x) for x in ss.get_lod_screen_sizes(m)]
        # 1) Auto Compute LOD Screen Size: record BEFORE, set OFF, read BACK
        # (rule 12 -- capture the pre-state and confirm the change).
        try:
            rec["auto_compute_before"] = bool(m.get_auto_compute_lod_screen_size())
        except Exception as e:
            rec["auto_compute_before"] = "no getter: %s" % e
        try:
            m.set_auto_compute_lod_screen_size(False)
            rec["auto_compute_after"] = bool(m.get_auto_compute_lod_screen_size())
        except Exception as e:
            rec["auto_compute_after"] = "no accessor: %s" % e
        # 2) apply, read back
        ok = ss.set_lod_screen_sizes(m, [float(x) for x in new_sizes])
        rec["set_returned"] = bool(ok)
        got = [float(x) for x in ss.get_lod_screen_sizes(m)]
        rec["screen_sizes_after"] = got
        rec["readback_matches"] = eq_list(got, new_sizes)
        # invariants unchanged
        rec["last_lod_tris_after"] = int(m.get_num_triangles(nlod - 1))
        rec["slots_after"] = len(m.static_materials)
        rec["invariants_ok"] = (rec["last_lod_tris_after"] == rec["last_lod_tris_before"]
                                and rec["slots_after"] == rec["slots_before"])
        # 3) save only if the read-back matched and invariants held
        if rec["readback_matches"] and rec["invariants_ok"]:
            rec["saved"] = bool(eal.save_loaded_asset(m))
        else:
            rec["saved"] = False
            rec["_WARN"] = ("NOT saved -- read-back mismatch or invariant broke. "
                            "The asset is DIRTY in editor memory (screen sizes + "
                            "auto-compute already applied); do NOT bulk-save. "
                            "Reverting from disk now.")
            # best-effort revert so a later save-all cannot persist the refused state
            try:
                _u.EditorLoadingAndSavingUtils.reload_packages([m.get_package()])
                rec["reverted"] = True
            except Exception as e:
                try:
                    _u.EditorAssetLibrary.load_asset(path)  # touch; no-op fallback
                except Exception:
                    pass
                rec["reverted"] = "revert failed: %s" % e
        out["meshes"].append(rec)
    out["ok"] = all(r.get("saved") for r in out["meshes"])
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "t3_hold.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

_st = {"ok": out.get("ok"), "error": out.get("error"),
       "meshes": [{"species": r["species"], "readback_matches": r.get("readback_matches"),
                   "invariants_ok": r.get("invariants_ok"), "saved": r.get("saved"),
                   "after": r.get("screen_sizes_after")} for r in out["meshes"]]}
print("__LL__" + _json.dumps(_st, default=str))
