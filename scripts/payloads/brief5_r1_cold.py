"""brief5_r1_cold.py -- Brief 5 REPAIR R1 COLD readback. READ-ONLY.

Run in a FRESH editor process (launched AFTER the apply editor was closed) to
prove the hold reached disk and survives a load. For each of the two meshes:
get_lod_screen_sizes (the RenderData->ScreenSize array the runtime LOD selection
reads, StaticMeshEditorSubsystem.cpp:986-1018), get_lod_count, last-LOD triangle
count, material-slot count, and the reflected auto_compute_lod_screen_size.

Reports its OWN process PID (os.getpid, which in a MODE_EXEC_FILE payload is the
editor process) so the host driver can prove this reading came from a process
DIFFERENT from the one that applied the hold -- the whole point of a cold check
(C1 rule: a value is not persisted until read back in a different process).

Does NOT write the final probe; the driver stamps provenance (apply-PID vs
cold-PID distinctness) and writes tree_lod_probe_cold.json.
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project on the port (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))

MESHES = [
    {"species": "ConiferPine",
     "path": "/Game/KiteDemo/Environments/Trees/ScotsPineTall_01/ScotsPineTall_01",
     "target": [1.50451, 0.33642, 0.23788, 0.03818],
     "lods": 4, "last_tris": 32, "slots": 5},
    {"species": "SpruceSub",
     "path": "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01",
     "target": [1.0, 0.99, 0.6, 0.35, 0.02642],
     "lods": 5, "last_tris": 6, "slots": 4},
]
_AUTO_NAMES = ["auto_compute_lod_screen_size", "b_auto_compute_lod_screen_size"]
_NONCE = "__NONCE__"   # substituted per-run by the driver (ue_exec --set NONCE=)


def _read_auto(m):
    # 5.8 exposes a reflected GETTER METHOD, not an editor property
    # (brief5_r1_probe_autoname.py, 2026-09-21).
    try:
        return bool(m.is_lod_screen_size_auto_computed())
    except Exception:
        pass
    for nm in _AUTO_NAMES:
        try:
            return bool(m.get_editor_property(nm))
        except Exception:
            continue
    return None


def _eq(a, b, tol=1e-4):
    if a is None or b is None or len(a) != len(b):
        return False
    return all(abs(float(x) - float(y)) < tol for x, y in zip(a, b))


out = {"ok": False, "nonce": _NONCE, "editor_pid": _os.getpid(), "meshes": []}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary
    for spec in MESHES:
        rec = {"species": spec["species"], "path": spec["path"],
               "target_screen_sizes": spec["target"]}
        if not eal.does_asset_exist(spec["path"]):
            rec["error"] = "asset missing"
            out["meshes"].append(rec)
            continue
        m = eal.load_asset(spec["path"])
        nlod = int(ss.get_lod_count(m))
        rec["num_lods"] = nlod
        rec["screen_sizes"] = [round(float(x), 6)
                               for x in ss.get_lod_screen_sizes(m)]
        rec["last_lod_tris"] = int(m.get_num_triangles(nlod - 1))
        rec["slots"] = int(len(m.static_materials))
        rec["auto_compute"] = _read_auto(m)
        rec["matches_target"] = _eq(rec["screen_sizes"], spec["target"])
        rec["invariants_ok"] = (rec["last_lod_tris"] == spec["last_tris"]
                                and rec["slots"] == spec["slots"]
                                and nlod == spec["lods"])
        rec["auto_compute_off"] = (rec["auto_compute"] is False)
        out["meshes"].append(rec)
    out["all_match"] = all(r.get("matches_target") for r in out["meshes"])
    out["all_invariants_ok"] = all(r.get("invariants_ok") for r in out["meshes"])
    out["all_auto_off"] = all(r.get("auto_compute_off") for r in out["meshes"])
    out["ok"] = out["all_match"] and out["all_invariants_ok"]
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "r1_cold_editor.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

print("__LL__" + _json.dumps(out, default=str))
