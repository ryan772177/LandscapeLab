"""probe_skeleton.py — which mannequin skeleton is which, measured not assumed.

PHASE2_PLAN.md unit 4's acceptance requires a brief that "cites its skeleton
by BONE PROBE". This is that probe. READ-ONLY against the editor: loads assets
and reads properties; spawns nothing and mutates nothing in-engine. It DOES
write one measurement artefact to Free/_measured/skeletons.json.

=====================================================================
WHY A BONE PROBE AND NOT THE ASSET NAME
=====================================================================
Both candidate skeletons in this project are called some variant of
"Mannequin", and one folder is named `Mannequin` while containing UE4-era
content. `ASSETS.md:78` already calls the UE4 asset the GASP retarget target,
which PHASE2_PLAN.md ruling 15 records as WRONG.

A name is a label someone typed. The bone list is what the animations
actually bind to, and a retarget that targets the wrong skeleton fails at the
worst possible time -- after the animation budget has been written against
it. So the skeleton is identified by asking which bones exist.

=====================================================================
THE MARKERS, AND WHY A POSITIVE CONTROL COMES FIRST
=====================================================================
The UE5 mannequin skeleton carries bones the UE4 one does not:

    spine_04, spine_05        UE5 has spine_01..05; UE4 stops at spine_03
    clavicle_out_l            UE5 shoulder detail bone
    index_metacarpal_l        UE5 hand detail bone

`hand_l` and `pelvis` exist in BOTH and are the POSITIVE CONTROLS. If a
control is missing the probe is broken, and every "marker absent" result that
run is "I could not look" rather than "UE4" -- non-negotiable 6 and 2. The
tool refuses a verdict in that case rather than reporting a skeleton
generation.

=====================================================================
THE REFLECTED SURFACE, RESOLVED AGAINST THIS INSTALL
=====================================================================
    SkeletalMesh.skeleton                PythonStub 514883
    SkeletalMesh.physics_asset           PythonStub 514871
    SkeletalMesh.materials               PythonStub 514856
    Skeleton.get_reference_pose()        PythonStub 255138  -> AnimPose
    AnimPose.get_bone_names()            PythonStub 49356
    Skeleton.bone_tree                   PythonStub 255050
    SkeletalMeshEditorSubsystem
      .get_lod_count / get_num_verts / get_num_sections
                                         PythonStub 633577 / 633508 / 633521

NOTE `get_num_bones` and `get_bone_name` are on SkinnedMeshCOMPONENT
(PythonStub 656055, 656130), not on Skeleton or SkeletalMesh -- they need a
spawned component, which a read-only probe will not do. The reference-pose
route reaches the same names off the asset.

Exit codes:
  0  probed -- at least one asset loaded and every loaded asset got a clean
     UE4/UE5 verdict
  1  could not look -- no marker, payload error, or no target asset loaded
  2  bad arguments
  3  rule 7: no verified editor node
  4  NO VERDICT for at least one loaded asset: a positive control failed, its
     reference pose could not be read, or the marker set was mixed/partial
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_SKEL__"
OUT = os.path.join(bootstrap.REPO_ROOT, "Free", "_measured", "skeletons.json")

# Present in BOTH generations. If one of these is missing the probe is broken.
CONTROLS = ("pelvis", "hand_l")
# Present in UE5 only.
UE5_MARKERS = ("spine_04", "spine_05", "clavicle_out_l", "index_metacarpal_l")

DEFAULT_TARGETS = [
    "/Game/Mannequin/Character/Mesh/SK_Mannequin",
    "/Game/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton",
    "/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SKM_Manny",
    "/Game/GV_FreeShrubsPack/Demo/Mannequin/Meshes/SK_Mannequin",
]


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "assets": []}
_targets = __TARGETS__
_probe = __PROBE__
try:
    _sub = _unreal.get_editor_subsystem(_unreal.SkeletalMeshEditorSubsystem)
    for _p in _targets:
        _rec = {"path": _p, "loaded": False, "class": None, "why": None,
                "skeleton_path": None, "bone_count": None, "bones_found": {},
                "physics_asset": None, "material_slots": None,
                "lods": None, "verts_per_lod": [], "sections_per_lod": [],
                "bone_tree_len": None}
        try:
            _a = _unreal.load_asset(_p)
        except Exception as _le:
            _rec["why"] = "load raised: " + type(_le).__name__ + ": " + str(_le)
            _out["assets"].append(_rec)
            continue
        if _a is None:
            _rec["why"] = "load_asset returned None -- asset absent?"
            _out["assets"].append(_rec)
            continue
        _rec["loaded"] = True
        _rec["class"] = _a.get_class().get_name()

        _skel = None
        if isinstance(_a, _unreal.SkeletalMesh):
            try:
                _skel = _a.get_editor_property("skeleton")
                _rec["skeleton_path"] = _skel.get_path_name() if _skel else None
            except Exception as _se:
                _rec["why"] = "skeleton unreadable: " + str(_se)
            try:
                _pa = _a.get_editor_property("physics_asset")
                _rec["physics_asset"] = _pa.get_path_name() if _pa else "NONE"
            except Exception:
                pass
            try:
                _rec["material_slots"] = len(_a.get_editor_property("materials"))
            except Exception:
                pass
            try:
                _n = int(_sub.get_lod_count(_a))
                _rec["lods"] = _n
                for _i in range(max(_n, 0)):
                    try:
                        _rec["verts_per_lod"].append(int(_sub.get_num_verts(_a, _i)))
                    except Exception:
                        _rec["verts_per_lod"].append(None)
                    try:
                        _rec["sections_per_lod"].append(int(_sub.get_num_sections(_a, _i)))
                    except Exception:
                        _rec["sections_per_lod"].append(None)
            except Exception as _lo:
                _rec["why"] = "lod count unreadable: " + str(_lo)
        elif isinstance(_a, _unreal.Skeleton):
            _skel = _a
            _rec["skeleton_path"] = _a.get_path_name()
        else:
            _rec["why"] = "not a SkeletalMesh or Skeleton"

        if _skel is not None:
            try:
                _bt = _skel.get_editor_property("bone_tree")
                _rec["bone_tree_len"] = 0 if _bt is None else len(_bt)
            except Exception:
                pass
            try:
                # Reference pose -> bone names. The names animations bind to.
                _pose = _skel.get_reference_pose()
                _names = [str(_n) for _n in _pose.get_bone_names()]
                _rec["bone_count"] = len(_names)
                _lower = set(_n.lower() for _n in _names)
                for _b in _probe:
                    _rec["bones_found"][_b] = (_b.lower() in _lower)
            except Exception as _pe:
                # Unreadable is NOT absent. Leave bones_found empty and say why.
                _rec["why"] = ("reference pose unreadable: "
                               + type(_pe).__name__ + ": " + str(_pe))
        _out["assets"].append(_rec)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_SKEL__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload):
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    try:
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    except ValueError:
        # Marker present but the trailing text is not valid JSON: that is
        # "could not look" (handled by the d is None branch), not a traceback.
        return None, text
    return d, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--asset", action="append", default=None,
                    help="asset path to probe (repeatable). Defaults to the "
                         "project's two mannequin candidates.")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)

    targets = args.asset or DEFAULT_TARGETS
    probe = list(CONTROLS) + list(UE5_MARKERS)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        d, raw = _run(remote, remote_exec,
                      PAYLOAD.replace("__TARGETS__", repr(targets))
                             .replace("__PROBE__", repr(probe)))
        if d is None:
            print("NO MARKER — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    assets = d.get("assets") or []
    if not assets:
        print("REFUSE: the payload returned zero assets — could not look.")
        return 1
    rc = 0
    n_loaded = 0
    print("=== UNIT 4 — SKELETON IDENTIFICATION BY BONE PROBE ===")
    for a in assets:
        print("")
        print("%s" % a["path"])
        if not a["loaded"]:
            print("  NOT LOADED: %s" % a.get("why"))
            continue
        n_loaded += 1
        print("  class            %s" % a["class"])
        if a.get("why"):
            print("  note             %s" % a["why"])
        print("  skeleton         %s" % a.get("skeleton_path"))
        print("  bones            %s (bone_tree %s)"
              % (a.get("bone_count"), a.get("bone_tree_len")))
        if a.get("lods") is not None:
            print("  LODs             %s" % a["lods"])
            print("  verts per LOD    %s" % a["verts_per_lod"])
            print("  sections per LOD %s" % a["sections_per_lod"])
            print("  material slots   %s" % a.get("material_slots"))
            print("  physics asset    %s" % a.get("physics_asset"))

        bf = a.get("bones_found") or {}
        if not bf:
            print("  BONE PROBE       COULD NOT LOOK — no verdict")
            rc = max(rc, 4)
            continue
        ctrl_ok = all(bf.get(c) for c in CONTROLS)
        print("  controls         %s"
              % ", ".join("%s=%s" % (c, bf.get(c)) for c in CONTROLS))
        print("  UE5 markers      %s"
              % ", ".join("%s=%s" % (m, bf.get(m)) for m in UE5_MARKERS))
        if not ctrl_ok:
            print("  VERDICT          NO VERDICT — a positive control is")
            print("                   MISSING, so the probe is broken and an")
            print("                   absent marker carries no information.")
            rc = max(rc, 4)
            continue
        n5 = sum(1 for m in UE5_MARKERS if bf.get(m))
        if n5 == len(UE5_MARKERS):
            print("  VERDICT          UE5 SKELETON (all %d markers present,"
                  % n5)
            print("                   controls pass)")
        elif n5 == 0:
            print("  VERDICT          UE4 SKELETON (0 of %d UE5 markers,"
                  % len(UE5_MARKERS))
            print("                   controls pass — so this is a real absence)")
        else:
            print("  VERDICT          MIXED / UNKNOWN — %d of %d markers. A"
                  % (n5, len(UE5_MARKERS)))
            print("                   partial match is not a generation; treat")
            print("                   as a modified or third-party skeleton.")
            rc = max(rc, 4)

    # NN13: exit 0 must mean "probed", not "found nothing to probe". If not one
    # target loaded, this is could-not-look, not success.
    if n_loaded == 0:
        print("")
        print("REFUSE: no target asset loaded — could not look, not 'probed'.")
        rc = max(rc, 1)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"measured_by": "probe_skeleton",
                   "controls": list(CONTROLS),
                   "ue5_markers": list(UE5_MARKERS),
                   "assets": assets}, fh, indent=1)
    # Read the artefact back rather than asserting its presence.
    try:
        with open(args.out, encoding="utf-8") as fh:
            _n = len(json.load(fh).get("assets", []))
    except (OSError, ValueError) as exc:
        print("REFUSE: artefact did not read back: %s" % exc)
        return max(rc, 1)
    print("")
    print("ARTEFACT: %s (%d assets verified on disk)" % (args.out, _n))
    return rc


if __name__ == "__main__":
    sys.exit(main())
