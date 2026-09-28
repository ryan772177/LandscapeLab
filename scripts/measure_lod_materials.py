"""measure_lod_materials.py — which material does each LOD section use?

Pass 4's third exit gate is "trunks beyond ~50 m go uniformly pale", and
the logged suspicion is that the LOD tier is not colour-matched to LOD0.
Before rebuilding anything, ask the engine what each LOD actually
renders with.

WHY SECTIONS AND NOT JUST SLOTS
-------------------------------
A static mesh LOD is a list of SECTIONS, and each section names a
material SLOT. The simplifier is free to drop a section entirely, and
this project has already been bitten by exactly that: R3 REJECTED
records a 5th LOD that returned 2 sections instead of 4, where the
survivors were both `M_fir_bark` and the DROPPED section was the twig
canopy — distant trees rendered as bare sticks.

So a LOD that has "the same materials" can still look wrong, because it
lost the geometry that used one of them. The section count per LOD is
the number that catches it; the slot mapping alone is not.

Accessors confirmed against the RUNNING 5.8 editor by enumerating the
reflected surface, not recalled (non-negotiable 23):
  StaticMeshEditorSubsystem.get_lod_count(mesh)
  StaticMeshEditorSubsystem.get_lod_material_slot(mesh, lod, section)
  StaticMeshEditorSubsystem.get_lod_screen_sizes(mesh)
  StaticMesh.get_num_triangles(lod)
  StaticMesh.static_materials  -> slot name + material

Exit codes:
  0  measured
  2  editor gate refused, or the mesh is missing
  4  a LOD lost a material that LOD0 had, or lost sections — UNLESS it is
     a COMPLETE substitution on the FINAL LOD (an imposter or billboard:
     it carries nothing over from LOD0), which is reported and passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_LODMAT__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "error": None, "lods": [], "slots": []}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _m = _unreal.EditorAssetLibrary.load_asset(_p)
        _ss = _unreal.get_editor_subsystem(_unreal.StaticMeshEditorSubsystem)
        for _i, _sm in enumerate(_m.static_materials):
            _mi = _sm.get_editor_property("material_interface")
            _out["slots"].append({{
                "index": _i,
                "slot_name": str(_sm.get_editor_property("material_slot_name")),
                "material": (_mi.get_path_name().split(".")[0]
                             if _mi is not None else None)}})
        _n = int(_ss.get_lod_count(_m))
        try:
            _screens = [float(_v) for _v in _ss.get_lod_screen_sizes(_m)]
        except Exception:
            _screens = [None] * _n
        for _lod in range(_n):
            _sections, _s = [], 0
            # There is no get_num_sections on the subsystem; walk until
            # the accessor refuses. A section index that raises is the
            # end of the list, not an error to report.
            # STOPS ON -1, NOT ON AN EXCEPTION. `get_lod_material_slot`
            # RETURNS -1 for an out-of-range section rather than
            # raising, so the first version walked to 64 every time and
            # the section-count comparison below compared 64 with 64 --
            # a check that could not fail, created while writing a
            # session-long lesson about checks that cannot fail.
            while _s < 64:
                _slot = int(_ss.get_lod_material_slot(_m, _lod, _s))
                if _slot < 0:
                    break
                _sections.append(_slot)
                _s += 1
            try:
                _tris = int(_m.get_num_triangles(_lod))
            except Exception:
                _tris = None
            _out["lods"].append({{
                "lod": _lod, "sections": _sections, "triangles": _tris,
                "screen_size": (_screens[_lod] if _lod < len(_screens)
                                else None)}})
        _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mesh", default="/Game/Meshes/fir_tree_01_c_LOD0")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("mesh      : {0}".format(args.mesh))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(
                PAYLOAD.format(path=args.mesh, marker=MARKER),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            data = _parse(bootstrap._collect_output(r) if r else "")
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None or not data.get("ok"):
        print("REFUSE: {0}".format((data or {}).get("error",
                                                    "no parseable result")))
        return 2

    slots = {s["index"]: s for s in data["slots"]}
    print("MATERIAL SLOTS")
    for s in data["slots"]:
        print("  [{0}] {1:<28} {2}".format(
            s["index"], s["slot_name"], s["material"]))
    print("")
    print("PER-LOD SECTIONS  (section -> slot index)")
    print("  {0:<5} {1:>9} {2:>12}  {3}".format(
        "lod", "triangles", "screen", "sections -> materials"))
    base = None
    rc = 0
    subs = 0
    for row in data["lods"]:
        mats = [slots.get(i, {}).get("material") for i in row["sections"]]
        short = ", ".join(
            "{0}->{1}".format(i, (m or "?").split("/")[-1])
            for i, m in zip(row["sections"], mats))
        print("  {0:<5} {1:>9,} {2:>12}  {3}".format(
            row["lod"], row["triangles"] or 0,
            "{0:.4f}".format(row["screen_size"])
            if row["screen_size"] is not None else "?", short))
        used = set(m for m in mats if m)
        if base is None:
            base = used
            base_n = len(row["sections"])
        else:
            lost = base - used
            gained = used - base
            # A LOSS and a SUBSTITUTION are different facts and were
            # reported as the same one until 2026-08-15.
            #
            # LOSS      -- materials disappear and nothing replaces them.
            #              The simplifier dropped geometry; the tree renders
            #              as strictly less of itself. This is the defect.
            # SUBSTITUTION -- materials disappear AND a material LOD0 never
            #              had appears. The LOD is a deliberate replacement
            #              representation: a billboard or octahedral
            #              imposter standing in for the whole tree. Every
            #              imposter LOD ever authored trips the loss test
            #              by construction, so calling it a loss makes the
            #              tool cry wolf on CORRECT vendor content.
            #
            # Motivating case: PN_interactiveSpruceForest binds its imposter
            # as LOD4 slot 3 at 4-6 triangles. The tool exited 4 on all 14
            # big trees and told the reader to "stop the chain before the
            # loss" -- which would have discarded the imposters that are the
            # entire reason the pack was chosen.
            # THE EXEMPTION IS NARROW, AND IT WAS NOT ON 2026-08-15.
            #
            # As first written this branch fired on `lost and gained`, i.e.
            # ANY LOD that swapped ANY material — and because `elif` guards
            # the loss check and `and not gained` guarded the section check,
            # ONE swapped material disabled BOTH refusals at once. A LOD
            # that dropped {branch, leaf} and gained {branch_lowpoly} —
            # the canopy gone — printed "expected, and NOT a defect".
            #
            # That is the exact defect this tool exists to catch: R3
            # REJECTED, a 5th LOD returning 2 sections instead of 4 where
            # the dropped section was the twig canopy, so distant trees
            # rendered as bare sticks.
            #
            # It survived "verified both directions" because in the PN pack
            # the loss and the substitution land on DIFFERENT LODs — a
            # property of the content measured, not of the logic. The
            # previous version was criticised in LESSONS for having seen
            # only one kind of input; the replacement had seen exactly one
            # content shape.
            #
            # Both conditions below were ALREADY ASSERTED by the printed
            # text and tested by nothing (NN25): "Expected at the last LOD"
            # and "a REPLACEMENT REPRESENTATION". Now they are the gate.
            #   last     — an imposter is the END of a chain, not a rung
            #   complete — a true replacement carries NOTHING over from
            #              LOD0, so `used & base` must be empty
            is_last = row["lod"] == len(data["lods"]) - 1
            complete = not (used & base)
            if lost and gained and is_last and complete:
                subs += 1
                print("        SUBSTITUTION: this LOD drops {0} and binds "
                      "{1}, which LOD0 never had.".format(
                          ", ".join(sorted(m.split('/')[-1] for m in lost)),
                          ", ".join(sorted(m.split('/')[-1] for m in gained))))
                print("        That is a REPLACEMENT REPRESENTATION (a "
                      "billboard or imposter), not simplifier loss. Expected "
                      "at the last LOD. Judge it by whether the imposter "
                      "MATCHES the tree, not by section count.")
            elif lost:
                rc = 4
                print("        LOST MATERIAL(S): {0}".format(
                    ", ".join(sorted(m.split('/')[-1] for m in lost))))
                print("        This LOD cannot render what LOD0 renders. "
                      "The geometry using that material was dropped by the "
                      "simplifier, so the tree changes COMPOSITION, not "
                      "just detail, at this transition.")
            # Section count indicts every LOD except a COMPLETE, FINAL
            # substitution. The guard was `and not gained` until
            # 2026-08-15, which let one swapped material silence this
            # check too — so a LOD could lose sections AND lose materials
            # and trip neither refusal.
            if len(row["sections"]) < base_n and not (
                    lost and gained and is_last and complete):
                rc = 4
                print("        SECTION COUNT {0} < LOD0's {1}".format(
                    len(row["sections"]), base_n))
    print("")
    if rc:
        print("At least one LOD lost a material or a section relative to "
              "LOD0. A colour POP at that transition is EXPECTED, and no "
              "amount of material tuning fixes it — the fix is to stop the "
              "chain before the loss, or to rebuild that LOD.")
    elif subs:
        print("No LOD lost a material without replacing it. {0} LOD(s) "
              "SUBSTITUTE a replacement representation (imposter or "
              "billboard) — expected, and NOT a defect. A pop at that "
              "transition is judged by whether the imposter matches the "
              "tree, which this tool does not measure.".format(subs))
    else:
        print("Every LOD carries LOD0's materials across the same number of "
              "sections. A colour pop, if seen, is therefore NOT caused by "
              "a lost section — look at the material's own distance "
              "behaviour instead.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
