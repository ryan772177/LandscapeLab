"""Point the capture stage at the character's PREVIEW face mesh.

WHY
---
`import_from_face_dna` changes the character's parametric face STATE. The
assembled `/Game/MetaHumans/.../SKM_..._FaceMesh` is the OUTPUT of a full
Assemble and does not move until one is run — and a full Assemble needs a
rig, then writes 252 packages, and has hung this editor once on memory. That
is far too heavy to sit inside a render-compare-iterate loop.

`assemble_for_preview(character)` runs the editor pipeline at preview quality
and `spawn_meta_human_actor(character, keep_transient=True)` gives an actor
whose meshes "reflect any changes made to the character while it's added to
the subsystem". Its Face component carries a transient 875-bone SkeletalMesh.
Pointing HeroStage_Subject at that mesh keeps the LOCKED camera, the locked
lights and the measured noise floor, and makes an import visible in one
preview assemble instead of a rig-and-build.

THE MESH IS TRANSIENT AND IS REPLACED BY EVERY PREVIEW ASSEMBLE, so this must
be re-run after each `assemble_for_preview`. Re-pointing at a stale object
would render the PREVIOUS state and call it the current one — the exact
"reports success over the wrong artefact" failure this pipeline keeps finding.
It therefore prints the mesh's object path every time, and refuses if the
Face component or its mesh is missing rather than leaving the stage pointed
at whatever it had before.

EXIT CODES
    0  stage now renders the preview face mesh
    3  no editor matched UE_PROJECT_ROOT
    5  payload error, or the preview actor/mesh was not found
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (REPO_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import ue_exec                       # noqa: E402
import capture_shot as CS                         # noqa: E402


PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

CHARACTER = "__CHARACTER__"
ASSEMBLE  = __ASSEMBLE__

_out = {"ok": False, "error": None}

try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)

    _ch = _eal.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        if not _sub.try_add_object_to_edit(_ch):
            raise RuntimeError("try_add_object_to_edit refused " + CHARACTER)
    _out["added_for_editing"] = True

    if ASSEMBLE:
        _sub.assemble_for_preview(_ch)
        _out["assembled_for_preview"] = True

    # Find the preview actor. Spawn one only if none exists -- a second
    # spawn would leave a stale twin in the level rendering old state.
    _actor = None
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroPreview_Working":
            _actor = _a
    if _actor is None:
        _actor = _sub.spawn_meta_human_actor(_ch, True)
        if _actor is None:
            raise RuntimeError("spawn_meta_human_actor returned None")
        _actor.set_actor_label("HeroPreview_Working")
        _out["spawned"] = True
    else:
        _out["spawned"] = False

    _face = None
    for _c in _actor.get_components_by_class(_u.SkeletalMeshComponent):
        if _c.get_name() == "Face":
            _face = _c
    if _face is None:
        raise RuntimeError("preview actor has no Face component")
    _mesh = _face.get_editor_property("skeletal_mesh_asset")
    if _mesh is None:
        raise RuntimeError("preview Face component carries no mesh")
    _out["preview_mesh"] = _mesh.get_path_name()
    _sk = _mesh.get_editor_property("skeleton")
    _out["preview_bones"] = (len(_sk.get_editor_property("bone_tree"))
                             if _sk else None)

    # The preview actor itself must not appear in frame beside the subject.
    for _c in _actor.get_components_by_class(_u.PrimitiveComponent):
        _c.set_editor_property("visible", False)
    _out["preview_actor_hidden"] = True

    _subj = None
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroStage_Subject":
            _subj = _a
    if _subj is None:
        raise RuntimeError("HeroStage_Subject missing; build the stage first")

    _sc = _subj.skeletal_mesh_component
    _sc.set_skeletal_mesh_asset(None)
    _sc.set_skeletal_mesh_asset(_mesh)

    # THE SUBJECT MUST BE VISIBLE, ASSERTED NOT ASSUMED. The presentation
    # preview payload hides HeroStage_Subject so it does not double-render
    # beside the full-body actor, and it does not put it back -- the same
    # borrowed-setting class as the FOV it also left at 32. A hidden subject
    # renders empty sky and the landmark gate reports NO FACE DETECTED,
    # which reads as a broken face rather than a missing one.
    _sc.set_editor_property("visible", True)
    _subj.set_actor_hidden_in_game(False)
    if not bool(_sc.get_editor_property("visible")):
        raise RuntimeError("HeroStage_Subject stayed hidden after being set "
                           "visible; the stage cannot be photographed")
    _out["subject_visible"] = True
    _back = _sc.get_editor_property("skeletal_mesh_asset")
    if _back is None or _back.get_path_name() != _mesh.get_path_name():
        raise RuntimeError(
            "stage subject read back %s, asked %s"
            % (_back.get_path_name() if _back else None, _mesh.get_path_name()))

    # Grooms off again: a fresh mesh on the component brings fresh components.
    _hidden = []
    for _c in _subj.get_components_by_class(_u.PrimitiveComponent):
        _cn = _c.get_class().get_name()
        if "Groom" in _cn or "Hair" in _cn:
            _c.set_editor_property("visible", False)
            _hidden.append(_cn)
    _out["grooms_hidden"] = _hidden

    # PRESENCE CHECK. Settling proves a frame is STABLE, not COMPLETE,
    # so the components that must render are asserted by NAME rather
    # than inferred from a statistic. Reported; the caller decides.
    _present = {}
    for _pc in _actor.get_components_by_class(_u.PrimitiveComponent):
        if "Groom" not in _pc.get_class().get_name():
            continue
        _ga = None
        try:
            _ga = _pc.get_editor_property("groom_asset")
        except Exception:
            pass
        _present[_pc.get_name()] = {
            "has_asset": _ga is not None,
            "visible": bool(_pc.get_editor_property("visible"))}
    _out["groom_presence"] = _present

    _o, _e = _subj.get_actor_bounds(False)
    _out["subject_bounds"] = {
        "origin": [round(_o.x, 3), round(_o.y, 3), round(_o.z, 3)],
        "extent": [round(_e.x, 3), round(_e.y, 3), round(_e.z, 3)]}
    _out["dirty"] = [str(_p.get_name()) for _p in
                     _u.EditorLoadingAndSavingUtils
                     .get_dirty_content_packages()]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:600]

print("__LL__" + _json.dumps(_out, default=str))
'''


def point_stage(character, assemble, timeout=60.0):
    rc, d, _ = ue_exec.run(
        CS._fill(PAYLOAD, CHARACTER=character, ASSEMBLE=bool(assemble)),
        timeout=timeout, stage_name="hero_use_preview")
    if rc == 3:
        raise SystemExit(3)
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        raise SystemExit(5)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--no-assemble", action="store_true",
                    help="skip assemble_for_preview (only when nothing has "
                         "changed since the last one)")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    d = point_stage(args.character, not args.no_assemble, args.timeout)
    print("character   %s" % args.character)
    print("assembled   %s" % d.get("assembled_for_preview", False))
    print("spawned     %s" % d.get("spawned"))
    print("mesh        %s  (%s bones)"
          % (d["preview_mesh"], d.get("preview_bones")))
    print("grooms off  %s" % (d.get("grooms_hidden") or "none found"))
    b = d["subject_bounds"]
    print("subject     origin %s  extent %s" % (b["origin"], b["extent"]))
    if d.get("dirty"):
        print("DIRTY       %s" % d["dirty"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
