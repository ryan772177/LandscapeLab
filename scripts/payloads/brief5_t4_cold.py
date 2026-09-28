"""brief5_t4_cold.py -- Brief 5 D1a cold read-back of the T4 gate meshes.

Runs in a FRESH editor process (distinct PID from the build pass). Reads each
/Game/Scratch/T4/<species>_gate: get_lod_count, per-LOD triangle count,
get_lod_screen_sizes, auto-compute -- and compares to the target chain. A value
is not persisted until it reads back correctly in a DIFFERENT process (r1 rule).

READ-ONLY: loads assets, no set/save. Fence-neutral.
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project on the port (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
_NONCE = "__NONCE__"
SCRATCH = "/Game/Scratch/T4"

TARGETS = [
    {"species": "ConiferPine",
     "final_tris": [27824, 11062, 5777, 1444, 361, 32],
     "final_ss": [1.50451, 0.33642, 0.23788, 0.11894, 0.05947, 0.03818],
     "card_tris": 32, "g_index": 2, "rung_tol": 0.35},
    {"species": "SpruceSub",
     "final_tris": [20695, 10347, 5174, 2587, 647, 162, 6],
     "final_ss": [1.0, 0.99, 0.6, 0.35, 0.17503, 0.08752, 0.02642],
     "card_tris": 6, "g_index": 3, "rung_tol": 0.35},
]

out = {"ok": False, "nonce": _NONCE, "editor_pid": _os.getpid(), "meshes": []}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary
    for t in TARGETS:
        rec = {"species": t["species"]}
        path = "%s/%s_gate" % (SCRATCH, t["species"])
        rec["path"] = path
        if not eal.does_asset_exist(path):
            rec["error"] = "gate asset absent"
            out["meshes"].append(rec); continue
        m = eal.load_asset(path)
        if m is None:
            rec["error"] = "load None"
            out["meshes"].append(rec); continue
        n = int(ss.get_lod_count(m))
        tris = [int(m.get_num_triangles(i)) for i in range(n)]
        ssz = [round(float(x), 6) for x in ss.get_lod_screen_sizes(m)]
        rec["lod_count"] = n
        rec["chain_tris"] = tris
        rec["screen_sizes"] = ssz
        try:
            rec["auto_compute"] = bool(m.is_lod_screen_size_auto_computed())
        except Exception as e:
            rec["auto_compute"] = "raised: %s" % e
        # verdicts
        len_ok = (n == len(t["final_tris"]))
        ss_ok = (len(ssz) == len(t["final_ss"])
                 and all(abs(a - b) < 1e-3 for a, b in zip(ssz, t["final_ss"])))
        card_ok = (tris[-1] == t["card_tris"]) if tris else False
        g = t["g_index"]
        geo_ok = all(tris[i] == t["final_tris"][i] for i in range(0, g + 1)) if len_ok else False
        rung_ok = True
        if len_ok:
            for i in range(g + 1, n - 1):   # the new rung indices (exclude card)
                tgt = t["final_tris"][i]
                lo, hi = tgt * (1 - t["rung_tol"]), tgt * (1 + t["rung_tol"])
                if not (lo <= tris[i] <= hi):
                    rung_ok = False
        rec["len_ok"] = bool(len_ok)
        rec["ss_ok"] = bool(ss_ok)
        rec["card_tris_ok"] = bool(card_ok)
        rec["geometric_lods_ok"] = bool(geo_ok)
        rec["rungs_within_tol"] = bool(rung_ok)
        rec["auto_off"] = (rec.get("auto_compute") is False)
        rec["match"] = bool(len_ok and ss_ok and card_ok and geo_ok and rung_ok and rec["auto_off"])
        out["meshes"].append(rec)
    out["all_match"] = bool(out["meshes"]) and all(r.get("match") for r in out["meshes"])
    out["ok"] = out["all_match"] and (len(out["meshes"]) == len(TARGETS))
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "t4_cold_editor.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

print("__LL__" + _json.dumps(out, default=str))
