"""brief5_t4_build.py -- Brief 5 D1a (T4 rungs): BUILD the rung LOD chain on
SCRATCH DUPLICATES, then self-verify by read-back. NO shipped mesh is touched.

For each card species (ConiferPine, SpruceSub) this:
  1. duplicates the REAL mesh -> /Game/Scratch/T4/<species>_gate  (the gate mesh),
  2. builds each rung as a reduced copy of LOD G on a throwaway duplicate,
     via set_lod_reduction_settings(throwaway, G, MeshReductionSettings(
        base_lod_model=G, termination_criterion=TRIANGLES,
        max_num_of_triangles=target)) -- "base LOD = G" per FOR_CLAUDE_CODE.md:84,
  3. assembles the gate chain [authored geometric LODs.., rung1, rung2, card]
     with set_lod_from_static_mesh, PRESERVING the authored card by copying it
     from the REAL mesh (never a decimation), and
  4. sets proposed.screen_sizes, forces auto-compute off, persists (r1 protocol:
     modify(True) + save_loaded_asset(only_if_is_dirty=False)).

SELF-VERIFY (rule 12/13): after EVERY set_lod_from_static_mesh the chain length
(get_lod_count) and per-LOD triangle count (get_num_triangles) are read back and
asserted against the expected chain. The grow-vs-replace behaviour of
set_lod_from_static_mesh (append when dest_index == count, replace when <count)
is NOT assumed -- it is proven by these read-backs; a mismatch marks that species
built=False and the gate mesh is NOT saved.

FENCE (Brief 5 D1a): writes ONLY under /Game/Scratch/T4 (gitignored, non-shipping).
The shipped meshes (ScotsPineTall_01, spruce_half_01) and their _SRC duplicates
are LOADED READ-ONLY (as the card source) and NEVER modified or saved. The driver
snapshots their .uasset sha256 before/after to prove byte-identity. The throwaway
rung-source duplicates are deleted at the end; the *_gate meshes are LEFT on disk
(gitignored) for the render-gate phase.

API resolved from the reflected surface (research/brief5/input/t4_api_resolved.json;
unreal.py:367729 set_lod_reduction_settings, :367742 set_lod_from_static_mesh,
:92129 MeshReductionSettings.base_lod_model). set_lods is NOT used (it regenerates
from LOD0 and would decimate the authored card -- casualty list).
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project on the port (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))

SCRATCH = "/Game/Scratch/T4"
_NONCE = "__NONCE__"   # substituted per-run by the driver (ue_exec --set NONCE=)

# FENCE + spec: hard-coded from t4_api_resolved.json target_chains (derived_ladder
# proposed). tol on rung tris is generous -- the reducer will not hit the target
# exactly; the VISUAL gate (deferred) judges the rung, achieved tris are recorded.
SPECS = [
    {"species": "ConiferPine",
     "real": "/Game/KiteDemo/Environments/Trees/ScotsPineTall_01/ScotsPineTall_01",
     "g_index": 2, "card_src_lod": 3, "card_tris": 32,
     "authored_count": 4,
     "rungs": [{"target_tris": 1444}, {"target_tris": 361}],
     "final_tris": [27824, 11062, 5777, 1444, 361, 32],
     "final_ss": [1.50451, 0.33642, 0.23788, 0.11894, 0.05947, 0.03818]},
    {"species": "SpruceSub",
     "real": "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01",
     "g_index": 3, "card_src_lod": 4, "card_tris": 6,
     "authored_count": 5,
     "rungs": [{"target_tris": 647}, {"target_tris": 162}],
     "final_tris": [20695, 10347, 5174, 2587, 647, 162, 6],
     "final_ss": [1.0, 0.99, 0.6, 0.35, 0.17503, 0.08752, 0.02642]},
]
RUNG_TOL = 0.35   # fractional; make_mesh_lods.COUNT_TOLERANCE. Applies to rung tris only.


def _tris(m, lod):
    return int(m.get_num_triangles(lod))


def _chain_tris(ss, m):
    return [_tris(m, i) for i in range(int(ss.get_lod_count(m)))]


def _reduce_rung(ss, eal, real_path, g_index, target_tris, dest_path, rec):
    """Duplicate the real mesh to a throwaway and reduce its LOD g_index down to
    ~target_tris, built FROM LOD g_index (base_lod_model=g). Return the reduced
    StaticMesh (unsaved throwaway) or None; append notes to rec."""
    if eal.does_asset_exist(dest_path):
        eal.delete_asset(dest_path)
    if not eal.duplicate_asset(real_path, dest_path):
        rec["error"] = "duplicate_asset failed: %s" % dest_path
        return None
    tw = eal.load_asset(dest_path)
    if tw is None:
        rec["error"] = "load throwaway None: %s" % dest_path
        return None
    mrs = _u.MeshReductionSettings()
    mrs.set_editor_property("base_lod_model", int(g_index))
    mrs.set_editor_property("termination_criterion",
                            _u.StaticMeshReductionTerimationCriterion.TRIANGLES)
    mrs.set_editor_property("max_num_of_triangles", int(target_tris))
    ss.set_lod_reduction_settings(tw, int(g_index), mrs)
    rec["achieved_tris"] = _tris(tw, int(g_index))
    rec["target_tris"] = int(target_tris)
    lo, hi = target_tris * (1.0 - RUNG_TOL), target_tris * (1.0 + RUNG_TOL)
    rec["within_tol"] = bool(lo <= rec["achieved_tris"] <= hi)
    return tw


def _cleanup_rungsrc(eal, species, n):
    """Delete the throwaway rung-source scratch dupes (scratch-only, all paths).
    Leaves the *_gate mesh. Called on success, chain-fail and except (MINOR-5:
    a leftover dirty scratch package would hang the close census)."""
    for i in range(n):
        p = "%s/%s_rungsrc%d" % (SCRATCH, species, i)
        try:
            if eal.does_asset_exist(p):
                eal.delete_asset(p)
        except Exception:
            pass


out = {"ok": False, "nonce": _NONCE, "editor_pid": _os.getpid(), "scratch": SCRATCH,
       "species": []}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary

    for spec in SPECS:
        sp = {"species": spec["species"], "real": spec["real"],
              "final_tris_target": spec["final_tris"],
              "final_ss_target": spec["final_ss"], "rung_build": [], "steps": []}
        try:
            real = eal.load_asset(spec["real"])
            if real is None:
                sp["error"] = "real mesh load None"
                out["species"].append(sp); continue
            sp["real_lod_count"] = int(ss.get_lod_count(real))
            sp["real_chain_tris"] = _chain_tris(ss, real)
            # invariant: the real mesh must still be the authored chain we expect
            sp["real_matches_authored"] = (sp["real_lod_count"] == spec["authored_count"]
                                           and _tris(real, spec["card_src_lod"]) == spec["card_tris"])
            # MINOR-6: refuse early if the real mesh is not the authored chain we
            # expect (e.g. re-run after D1 applied rungs to the shipped mesh, where
            # card_src_lod would no longer be the card). Fail before building.
            if not sp["real_matches_authored"]:
                sp["error"] = ("REFUSE: real mesh is not the authored chain "
                               "(lod_count/card mismatch) -- card_src_lod would be wrong")
                out["species"].append(sp); continue

            gate_path = "%s/%s_gate" % (SCRATCH, spec["species"])
            if eal.does_asset_exist(gate_path):
                eal.delete_asset(gate_path)
            if not eal.duplicate_asset(spec["real"], gate_path):
                sp["error"] = "duplicate gate failed"
                out["species"].append(sp); continue
            gate = eal.load_asset(gate_path)
            sp["gate_path"] = gate_path
            sp["gate_start_count"] = int(ss.get_lod_count(gate))

            # build rung sources
            rung_meshes = []
            for i, rg in enumerate(spec["rungs"]):
                rrec = {"idx": i}
                tw = _reduce_rung(ss, eal, spec["real"], spec["g_index"],
                                  rg["target_tris"],
                                  "%s/%s_rungsrc%d" % (SCRATCH, spec["species"], i),
                                  rrec)
                sp["rung_build"].append(rrec)
                if tw is None:
                    raise RuntimeError("rung %d reduce failed: %s" % (i, rrec.get("error")))
                rung_meshes.append(tw)

            # assemble: replace card slot with rung1, append rung2, append card.
            # For ConiferPine authored=[0,1,2(G),3(card)] -> replace idx3, append 4,5.
            # For SpruceSub authored=[0,1,2,3(G),4(card)] -> replace idx4, append 5,6.
            card_slot = spec["authored_count"] - 1
            g = spec["g_index"]

            def _place(dest_idx, src_mesh, src_lod, label):
                # set_lod_from_static_mesh returns the index of the LOD that was set;
                # NEGATIVE means the LOD was NOT set (stub :677643, MINOR-3). Gate it.
                ri = int(ss.set_lod_from_static_mesh(gate, dest_idx, src_mesh, src_lod, True))
                sp["steps"].append({"op": label, "dest_idx": dest_idx, "ret_index": ri,
                                    "count": int(ss.get_lod_count(gate))})
                if ri < 0:
                    raise RuntimeError("set_lod_from_static_mesh %s returned %d (not set)"
                                       % (label, ri))

            # rung1 -> card slot (REPLACE); rung2 -> +1 (APPEND); card -> +2 (APPEND,
            # copied from the REAL mesh so the authored billboard is preserved).
            _place(card_slot, rung_meshes[0], g, "rung1->%d" % card_slot)
            _place(card_slot + 1, rung_meshes[1], g, "rung2->%d" % (card_slot + 1))
            _place(card_slot + 2, real, spec["card_src_lod"], "card->%d" % (card_slot + 2))

            built_count = int(ss.get_lod_count(gate))
            built_tris = _chain_tris(ss, gate)
            sp["built_count"] = built_count
            sp["built_chain_tris"] = built_tris
            # SELF-VERIFY the chain: length exact, card tris EXACT (authored, not
            # decimated), geometric LODs 0..G EXACT (untouched), rungs within tol.
            expected_len = len(spec["final_tris"])
            len_ok = (built_count == expected_len)
            card_ok = (built_tris[-1] == spec["card_tris"]) if built_tris else False
            geo_ok = all(built_tris[i] == spec["final_tris"][i]
                         for i in range(0, g + 1)) if len_ok else False
            # MINOR-6: guard empty (rule 13 -- all([]) is True).
            rungs_ok = bool(sp["rung_build"]) and all(r.get("within_tol")
                                                      for r in sp["rung_build"])
            # MAJOR-1: assert the ASSEMBLED chain's rung slots equal the reduced
            # sources' achieved tris. within_tol was measured on the THROWAWAY, not
            # the gate -- copied geometry preserves tri count, so exact equality here
            # catches a swapped/wrong-source rung that would otherwise save to scratch.
            rungs_placed_ok = (len_ok and all(
                built_tris[card_slot + i] == r["achieved_tris"]
                for i, r in enumerate(sp["rung_build"]))) if len_ok else False
            sp["chain_len_ok"] = bool(len_ok)
            sp["card_tris_ok"] = bool(card_ok)
            sp["geometric_lods_ok"] = bool(geo_ok)
            sp["rungs_within_tol"] = bool(rungs_ok)
            sp["rungs_placed_ok"] = bool(rungs_placed_ok)
            sp["chain_ok"] = bool(len_ok and card_ok and geo_ok and rungs_ok
                                  and rungs_placed_ok)

            if not sp["chain_ok"]:
                sp["_WARN"] = "chain self-verify FAILED -- gate mesh deleted, not saved"
                # MINOR-4: the gate was duplicate_asset'd this run and never saved, so
                # there is nothing on disk to reload; DELETE the scratch gate to leave
                # the package set clean (a lingering dirty scratch package would make
                # the close census non-clean and hang the editor). Scratch-only.
                try:
                    eal.delete_asset(gate_path)
                except Exception:
                    pass
                _cleanup_rungsrc(eal, spec["species"], len(spec["rungs"]))
                out["species"].append(sp); continue

            # set screen sizes + persist (r1 protocol). SetLodScreenSizes forces
            # auto-compute OFF internally (StaticMeshEditorSubsystem.cpp:1060); there
            # is NO Python setter for the property (MINOR-2), so read it back here
            # rather than call a setter that only raises into a silent except.
            ss.set_lod_screen_sizes(gate, [float(x) for x in spec["final_ss"]])
            try:
                sp["auto_compute_after"] = bool(gate.is_lod_screen_size_auto_computed())
            except Exception as e:
                sp["auto_compute_after"] = "raised: %s" % e
            sp["ss_after"] = [round(float(x), 6) for x in ss.get_lod_screen_sizes(gate)]
            sp["ss_match"] = all(abs(a - b) < 1e-3 for a, b in
                                 zip(sp["ss_after"], spec["final_ss"])) \
                if len(sp["ss_after"]) == len(spec["final_ss"]) else False
            try:
                gate.modify(True)
            except Exception:
                pass
            sp["saved_return"] = bool(eal.save_loaded_asset(gate, only_if_is_dirty=False))
            sp["built"] = bool(sp["chain_ok"] and sp["ss_match"] and sp["saved_return"])
            _cleanup_rungsrc(eal, spec["species"], len(spec["rungs"]))
        except Exception as e:
            sp["error"] = "%s: %s" % (type(e).__name__, e)
            sp["traceback"] = _tb.format_exc()[-1200:]
            # MINOR-5: clean throwaways on the except path too, else a dirty scratch
            # package hangs the close census.
            try:
                _cleanup_rungsrc(eal, spec["species"], len(spec["rungs"]))
            except Exception:
                pass
        out["species"].append(sp)

    out["ok"] = (len(out["species"]) == len(SPECS)
                 and all(s.get("built") for s in out["species"]))
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    _dest = _os.path.join(_root, "research", "brief5", "input", "t4_build_editor.json")
    _json.dump(out, open(_dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = _dest
except Exception as e:
    out["write_error"] = str(e)

_st = {"ok": out.get("ok"), "error": out.get("error"), "nonce": out.get("nonce"),
       "editor_pid": out.get("editor_pid"),
       "species": [{"species": s["species"], "built": s.get("built"),
                    "chain_ok": s.get("chain_ok"), "built_count": s.get("built_count"),
                    "built_chain_tris": s.get("built_chain_tris"),
                    "rung_achieved": [r.get("achieved_tris") for r in s.get("rung_build", [])],
                    "ss_match": s.get("ss_match"), "error": s.get("error")}
                   for s in out["species"]]}
print("__LL__" + _json.dumps(_st, default=str))
