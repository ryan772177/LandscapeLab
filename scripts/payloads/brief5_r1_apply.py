"""brief5_r1_apply.py -- Brief 5 REPAIR R1 (APPLY with a PERSIST protocol).

MUTATES exactly two StaticMesh assets and SAVES them so the T3 hold finally
reaches disk. C1 proved the T3 save was a false-success NO-OP: SetLodScreenSizes
(StaticMeshEditorSubsystem.cpp:1020-1097) writes RenderData->ScreenSize and the
SourceModel ScreenSize but NEVER calls Modify()/MarkPackageDirty(), so
save_loaded_asset() with its default only_if_is_dirty=True saw a clean package,
skipped the write, and returned True. This payload closes that gap:

    b. read auto_compute_lod_screen_size; if True set False; read back
    c. set_lod_screen_sizes(targets); read back WARM (RenderData array)
    d. mark the package DIRTY explicitly (Object.modify), then
       save_loaded_asset(only_if_is_dirty=False) -- log the return value but do
       NOT treat it as success (evidence is the host-side mtime/sha diff).

Invariants verified UNCHANGED: last-LOD triangle count (32 / 6) and material
slot count (5 / 4).

FENCE (Brief 5 repair): writes ONLY the two meshes named in ALLOWED below. The
_SRC pristine duplicates are NOT touched (no duplicate, no load, no save). No
actor, FoliageType, level, material, HLOD or Nanite change. The two paths are
hard-coded, not read from a recipe, so a recipe edit cannot widen the blast
radius.

The auto-compute member is a reflected UPROPERTY (StaticMesh.h:719-722,
bAutoComputeLODScreenSize) with NO Python UFUNCTION accessor -- T3's
get_/set_auto_compute_lod_screen_size() raised "no attribute". The correct call
form is get_editor_property / set_editor_property with the reflected snake_case
name; a small name-candidate list makes the read robust and REPORTS which name
worked rather than guessing.
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project on the port (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))

# --- FENCE: the only two assets this payload may write. Hard-coded. ---
ALLOWED = [
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
    """Return (value_or_None, name_that_worked_or_error). 5.8 exposes a reflected
    GETTER METHOD (is_lod_screen_size_auto_computed) -- NOT an editor property;
    probed live 2026-09-21 (brief5_r1_probe_autoname.py). bAutoComputeLODScreenSize
    is deprecated 5.7 so get_editor_property raises."""
    try:
        return bool(m.is_lod_screen_size_auto_computed()), \
            "is_lod_screen_size_auto_computed()"
    except Exception:
        pass
    for nm in _AUTO_NAMES:
        try:
            return bool(m.get_editor_property(nm)), nm
        except Exception:
            continue
    return None, "no reflected getter (method or property)"


def _set_auto(m, val):
    for nm in _AUTO_NAMES:
        try:
            m.set_editor_property(nm, val)
            return nm
        except Exception:
            continue
    return None


def _eq(a, b, tol=1e-4):
    if a is None or b is None or len(a) != len(b):
        return False
    return all(abs(float(x) - float(y)) < tol for x, y in zip(a, b))


out = {"ok": False, "nonce": _NONCE, "meshes": []}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary

    for spec in ALLOWED:
        path, species = spec["path"], spec["species"]
        rec = {"species": species, "path": path,
               "target_screen_sizes": spec["target"]}
        # precondition: the pristine _SRC backup must exist (read-only check).
        src = path.rsplit(".", 1)[0] + "_SRC"
        rec["src_backup_present"] = bool(eal.does_asset_exist(src))
        if not rec["src_backup_present"]:
            rec["error"] = "REFUSE: pristine _SRC backup absent (%s)" % src
            out["meshes"].append(rec)
            continue
        if not eal.does_asset_exist(path):
            rec["error"] = "asset does not exist"
            out["meshes"].append(rec)
            continue
        m = eal.load_asset(path)
        if m is None:
            rec["error"] = "load_asset returned None"
            out["meshes"].append(rec)
            continue

        # baseline invariants + warm state BEFORE
        nlod = int(ss.get_lod_count(m))
        rec["lod_count"] = nlod
        rec["last_lod_tris_before"] = int(m.get_num_triangles(nlod - 1))
        rec["slots_before"] = int(len(m.static_materials))
        rec["screen_sizes_before"] = [round(float(x), 6)
                                      for x in ss.get_lod_screen_sizes(m)]

        # (b) auto-compute: read, set False if True, read back
        av, aname = _read_auto(m)
        rec["auto_compute_before"] = av
        rec["auto_compute_prop_name"] = aname
        if av is True:
            setnm = _set_auto(m, False)
            rec["auto_compute_set_via"] = setnm
        av2, _ = _read_auto(m)
        rec["auto_compute_after_explicit"] = av2

        # (c) apply, read back WARM
        ok = ss.set_lod_screen_sizes(m, [float(x) for x in spec["target"]])
        rec["set_returned"] = bool(ok)
        got = [round(float(x), 6) for x in ss.get_lod_screen_sizes(m)]
        rec["screen_sizes_after_warm"] = got
        rec["readback_matches_warm"] = _eq(got, spec["target"])
        # the subsystem forces auto-compute off internally (cpp:1060); confirm
        av3, _ = _read_auto(m)
        rec["auto_compute_after_set"] = av3

        # invariants unchanged
        rec["last_lod_tris_after"] = int(m.get_num_triangles(nlod - 1))
        rec["slots_after"] = int(len(m.static_materials))
        rec["invariants_ok"] = (
            rec["last_lod_tris_after"] == rec["last_lod_tris_before"] == spec["last_tris"]
            and rec["slots_after"] == rec["slots_before"] == spec["slots"]
            and nlod == spec["lods"])

        # only proceed to the write if the warm state is exactly right, AND
        # auto-compute is confirmed OFF (True on disk => the next LOD build
        # recomputes the ScreenSizes and undoes the hold -- the root-cause
        # contract, MAJOR-3).
        rec["auto_off_ok"] = (rec.get("auto_compute_after_set") is False)
        if not (rec["readback_matches_warm"] and rec["invariants_ok"]
                and rec["auto_off_ok"]):
            rec["saved_return"] = False
            rec["_WARN"] = ("NOT saved -- warm read-back mismatch, invariant "
                            "broke, or auto-compute not confirmed OFF. Reloading "
                            "the package from disk so no later save-all can "
                            "persist the refused state.")
            try:
                _u.EditorLoadingAndSavingUtils.reload_packages([m.get_package()])
                rec["reverted"] = True
            except Exception as e:
                rec["reverted"] = "revert failed: %s" % e
            out["meshes"].append(rec)
            continue

        # (d) mark the package DIRTY explicitly, then FORCE the save.
        # Object.modify() opens a transaction and marks the outer package dirty
        # (UObject::Modify -> MarkPackageDirty). This is the step T3 was missing.
        try:
            rec["modify_returned"] = bool(m.modify(True))
        except Exception as e:
            rec["modify_returned"] = "modify raised: %s" % e
        try:
            pkg = m.get_package()
            rec["package_is_dirty_pre_save"] = bool(pkg.is_dirty())
        except Exception as e:
            rec["package_is_dirty_pre_save"] = "is_dirty raised: %s" % e
        # FORCE the write regardless of the dirty flag (the decisive lever).
        rec["saved_return"] = bool(
            eal.save_loaded_asset(m, only_if_is_dirty=False))
        # the save's return is NOT evidence (C1); the driver's host-side
        # mtime/sha diff is. Record the in-editor post-save readback too.
        rec["screen_sizes_after_save_warm"] = [
            round(float(x), 6) for x in ss.get_lod_screen_sizes(m)]
        out["meshes"].append(rec)

    out["ok"] = (len(out["meshes"]) == len(ALLOWED)
                 and all(r.get("saved_return") for r in out["meshes"])
                 and all(r.get("readback_matches_warm") for r in out["meshes"])
                 and all(r.get("auto_off_ok") for r in out["meshes"]))
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "r1_apply_editor.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

_st = {"ok": out.get("ok"), "error": out.get("error"), "nonce": out.get("nonce"),
       "meshes": [{"species": r["species"],
                   "auto_before": r.get("auto_compute_before"),
                   "auto_after_set": r.get("auto_compute_after_set"),
                   "auto_off_ok": r.get("auto_off_ok"),
                   "warm_match": r.get("readback_matches_warm"),
                   "invariants_ok": r.get("invariants_ok"),
                   "dirty_pre_save": r.get("package_is_dirty_pre_save"),
                   "saved_return": r.get("saved_return"),
                   "after": r.get("screen_sizes_after_warm")}
                  for r in out["meshes"]]}
print("__LL__" + _json.dumps(_st, default=str))
