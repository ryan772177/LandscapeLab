"""THE AXIS-DIRECTION TEST — the first DNA write, settled by render.

WHAT THIS ANSWERS, AND IN WHAT ORDER
------------------------------------
The brief fixes Pass 1 as "joints-first: edit ONLY neutral joint
translations". Engine source says that changes the BIND POSE and not the
skin: `USkelMeshDNAUtils::UpdateJoints` is commented "Updates bind pose
using joint positions from DNA" (SkelMeshDNAUtils.cpp:79) and ends with

    InSkelMesh->GetRefBasesInvMatrix().Reset();
    InSkelMesh->CalculateInvRefMatrices();

so the inverse-bind matrices are recomputed FROM THE NEW BIND POSE while the
stored vertex positions are untouched. At the reference pose the skinning
matrix is then NewRef * inverse(NewRef) = identity.

**That is a reading, not a measurement.** This tool measures it. It runs, in
order:

    0  BASELINE            no write. The frame everything is compared to.
    1  POSITIVE CONTROL    scale the SUBJECT ACTOR to Z x 1.02 and capture.
                           IT HAS TO BE A SHAPE CHANGE. The landmark frame
                           is iris-centred and IPD-scaled, so a rigid nudge
                           cancels out of it EXACTLY -- measured: a 0.2 cm
                           translation read 0.9x the floor, indistinguishable
                           from noise. That invariance is the property that
                           makes the metric immune to framing drift, and it
                           is exactly why translation cannot be the control.
                           An X-scale cancels too, since the normalising IPD
                           is measured along X. If the Z-scale does NOT
                           register, the instrument cannot see a shape change
                           and every null below is meaningless. Then scale
                           back and prove the frame returns to baseline.
    2  JOINTS ONLY         write +offset on ONE component of ONE joint,
                           apply with UpdateJoints alone, capture.
    3  ATTACH ONLY         attach the same DNA with NO update stage at all.
                           Tests the one way joints-only could still show:
                           if something poses the bones from the DNA while
                           the bind pose stays put, the skin deforms.
    4  RESTORE             re-apply the canonical DNA and prove the frame
                           comes back to baseline.

**Every arm reports TWO representations**: the mesh's own reference skeleton
(component-space translation of probe bones, from the plugin) and the
rendered landmarks. They can disagree, and the disagreement IS the finding —
a bone that provably moved in the skeleton while the render did not budge is
exactly what the source predicts.

WHAT IS NOT ASSUMED
-------------------
The joint index is CONFIRMED BY NAME against the canonical DNA before
anything is written. Which way +X points on a FACIAL_ joint is a property of
the rig, and DNA neutral translations are PARENT-RELATIVE, so no direction is
inferred from the axis letter -- it is read off the render and recorded.
Nothing here generalises to another region.

EXIT CODES
    0  ran; findings written
    2  bad arguments, or the joint name does not match the index
    3  no editor matched UE_PROJECT_ROOT
    4  THE POSITIVE CONTROL FAILED -- the instrument cannot see a real move,
       so no null result from it means anything
    5  a payload error, or the restore did not come back clean
    6  a capture failed its landmark gate
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (REPO_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import ue_exec                       # noqa: E402
import capture_shot as CS                         # noqa: E402

DEFAULT_MANIFEST = os.path.join(_HERE, "manifest.json")


READ_JOINT = r'''
import json as _json
import unreal as _u

DNA_PATH = r"__DNA__"
INDEX    = __INDEX__

_out = {"ok": False, "error": None}
try:
    _n, _t, _c, _f, _ok, _err = _u.LandscapeLabTools.read_dna_joints(DNA_PATH)
    if not _ok:
        raise RuntimeError(_err)
    _out["joint_count"] = int(_c)
    _out["format"] = _f
    if INDEX < 0 or INDEX >= int(_c):
        raise RuntimeError("index %d outside [0, %d)" % (INDEX, int(_c)))
    _out["name"] = str(_n[INDEX])
    _v = _t[INDEX]
    _out["translation"] = [_v.x, _v.y, _v.z]
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())
print("__LL__" + _json.dumps(_out, default=str))
'''


WRITE_DNA = r'''
import json as _json
import unreal as _u

IN_DNA  = r"__IN_DNA__"
OUT_DNA = r"__OUT_DNA__"
INDEX   = __INDEX__
NEWXYZ  = __NEWXYZ__

_out = {"ok": False, "error": None}
try:
    _c, _layer, _ok, _err = _u.LandscapeLabTools.write_dna_joint_translations(
        IN_DNA, OUT_DNA, [INDEX],
        [_u.Vector(NEWXYZ[0], NEWXYZ[1], NEWXYZ[2])])
    _out["joint_count"] = int(_c)
    _out["layer_note"] = str(_layer)
    if not _ok:
        raise RuntimeError(_err)
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())
print("__LL__" + _json.dumps(_out, default=str))
'''


APPLY = r'''
import json as _json
import unreal as _u

DNA_PATH   = r"__DNA__"
MESH_PATH  = "__MESH__"
DO_JOINTS  = __DO_JOINTS__
DO_BASE    = __DO_BASE__
DO_REBUILD = __DO_REBUILD__
DO_ATTACH  = __DO_ATTACH__
PROBES     = __PROBES__

_out = {"ok": False, "error": None}
try:
    _mesh = _u.EditorAssetLibrary.load_asset(MESH_PATH)
    if _mesh is None:
        raise RuntimeError("could not load %s" % MESH_PATH)

    _before, _after, _bones, _stages, _ok, _err = \
        _u.LandscapeLabTools.apply_dna_to_skeletal_mesh(
            DNA_PATH, _mesh, DO_JOINTS, DO_BASE, DO_REBUILD, DO_ATTACH,
            PROBES)
    _out["bone_count"] = int(_bones)
    _out["stages"] = str(_stages)
    _out["probe_before"] = [[v.x, v.y, v.z] for v in _before]
    _out["probe_after"] = [[v.x, v.y, v.z] for v in _after]
    if not _ok:
        raise RuntimeError(_err)

    # THE STAGE ACTOR HOLDS A COMPONENT, AND A COMPONENT CACHES RENDER STATE.
    # Re-assigning the asset forces it to pick up the rebuilt data, so a null
    # render result cannot be "the component never noticed".
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _touched = []
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroStage_Subject":
            _c = _a.skeletal_mesh_component
            _c.set_skeletal_mesh_asset(None)
            _c.set_skeletal_mesh_asset(_mesh)
            _o, _e2 = _a.get_actor_bounds(False)
            _touched.append({
                "bounds_origin": [round(_o.x, 4), round(_o.y, 4),
                                  round(_o.z, 4)],
                "bounds_extent": [round(_e2.x, 4), round(_e2.y, 4),
                                  round(_e2.z, 4)]})
    _out["subject"] = _touched
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())
print("__LL__" + _json.dumps(_out, default=str))
'''


SCALE_Z = r'''
import json as _json
import unreal as _u

SZ = __SZ__

_out = {"ok": False, "error": None}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _moved = []
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroStage_Subject":
            _a.set_actor_scale3d(_u.Vector(1.0, 1.0, SZ))
            _r = _a.get_actor_scale3d()
            if abs(_r.z - SZ) > 1e-6:
                raise RuntimeError(
                    "scale did not land: asked %.6f, read %.6f" % (SZ, _r.z))
            _moved.append([_r.x, _r.y, _r.z])
    if not _moved:
        raise RuntimeError("HeroStage_Subject not found")
    _out["scale"] = _moved
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())
print("__LL__" + _json.dumps(_out, default=str))
'''


def _run(tpl, timeout, stage, **kw):
    rc, d, _ = ue_exec.run(CS._fill(tpl, **kw), timeout=timeout,
                           stage_name=stage)
    if rc == 3:
        raise SystemExit(3)
    if d is None or d.get("error"):
        print("PAYLOAD ERROR in %s:\n%s"
              % (stage, (d or {}).get("error") or "no result"))
        raise SystemExit(5)
    return d


def _probe_delta(d):
    """Largest component-space movement of any probe bone, in cm."""
    worst = 0.0
    rows = []
    for i, (b, a) in enumerate(zip(d["probe_before"], d["probe_after"])):
        m = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
        rows.append((i, b, a, m))
        worst = max(worst, m)
    return worst, rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--joint-index", type=int, default=804)
    ap.add_argument("--joint-name", default="FACIAL_C_Jaw",
                    help="asserted against the DNA; a mismatch REFUSES")
    ap.add_argument("--axis", choices=["x", "y", "z"], default="x")
    ap.add_argument("--offset-cm", type=float, default=2.0)
    ap.add_argument("--control-z", type=float, default=1.02,
                    help="positive-control Z scale of the subject actor. A "
                         "SHAPE change, because the iris-centred frame "
                         "removes translation and X-scale exactly")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    man = CS.load_manifest(args.manifest)
    floor = man["capture"].get("noise_floor")
    if not floor:
        print("REFUSING: no noise floor in the manifest. Run")
        print("  capture_shot.py --noise-floor --repeats 4")
        print("first — without it a delta is a number, not evidence.")
        return 2
    p90 = floor["per_landmark"]["p90_ipd"]
    cm_per_ipd = floor["scale"]["cm_per_ipd"]
    model = CS.resolve(man, "mediapipe_model")
    out_dir = CS.resolve(man, "renders_dir")
    canonical = CS.resolve(man, "dna_canonical")
    mesh_path = man["unreal"]["face_skeletal_mesh"]
    probes = [args.joint_name, "FACIAL_C_FacialRoot", "head"]

    print("=" * 72)
    print("AXIS-DIRECTION TEST — the first DNA write")
    print("=" * 72)
    print("noise floor  p90 %.5f IPD = %.4f cm   (%s)"
          % (p90, p90 * cm_per_ipd, floor["measured_utc"]))
    print("joint        %d, asserted to be '%s'"
          % (args.joint_index, args.joint_name))
    print("move         %+.2f cm on %s" % (args.offset_cm, args.axis.upper()))
    print()

    # --- the joint is confirmed BY NAME before anything is written --------
    d = _run(READ_JOINT, args.timeout, "axis_read_joint",
             DNA=canonical, INDEX=args.joint_index)
    if d["name"] != args.joint_name:
        print("REFUSING: joint %d is '%s', not '%s'."
              % (args.joint_index, d["name"], args.joint_name))
        print("An index that has drifted would move a different part of the")
        print("face and the render would still show 'something moved'.")
        return 2
    base_xyz = d["translation"]
    print("confirmed    joint %d = '%s'  format %s  (%d joints)"
          % (args.joint_index, d["name"], d["format"], d["joint_count"]))
    print("             neutral translation (PARENT-RELATIVE) "
          "(%.6f, %.6f, %.6f)" % tuple(base_xyz))
    print()

    findings = {"joint_index": args.joint_index, "joint_name": args.joint_name,
                "axis": args.axis, "offset_cm": args.offset_cm,
                "noise_floor_p90_ipd": p90, "cm_per_ipd": cm_per_ipd,
                "arms": []}

    def capture(stage):
        png, _ = CS.shoot(man, stage, out_dir, args.timeout)
        try:
            c, st, fatal = CS.measure(png, model)
        except LookupError:
            print("  %s: NO FACE DETECTED in %s" % (stage, png))
            raise SystemExit(6)
        if fatal:
            print("  %s: gate refused — %s" % (stage, "; ".join(fatal)))
            raise SystemExit(6)
        return png, c, st

    def report(stage, c, ref, probe_worst=None):
        dl = CS._delta(ref, c)
        ratio = dl["p90_ipd"] / p90 if p90 else float("inf")
        verdict = "MOVED" if ratio >= 2.0 else (
            "ambiguous" if ratio >= 1.0 else "NO CHANGE")
        line = ("  %-12s render p90 %.5f IPD = %.4f cm  (%.1fx floor)  %s"
                % (stage, dl["p90_ipd"], dl["p90_ipd"] * cm_per_ipd,
                   ratio, verdict))
        print(line)
        if probe_worst is not None:
            print("  %-12s skeleton  worst probe bone moved %.5f cm"
                  % ("", probe_worst))
        findings["arms"].append({
            "arm": stage, "render_p90_ipd": round(dl["p90_ipd"], 6),
            "render_p90_cm": round(dl["p90_ipd"] * cm_per_ipd, 5),
            "render_max_ipd": round(dl["max_ipd"], 6),
            "x_floor": round(ratio, 2), "verdict": verdict,
            "skeleton_worst_cm": (round(probe_worst, 6)
                                  if probe_worst is not None else None)})
        return dl, verdict

    # --- 0 BASELINE -------------------------------------------------------
    print("0  BASELINE")
    base_png, base_c, base_st = capture("baseline")
    print("  %s   ipd %.2f px  roll %+.3f  yaw %.4f"
          % (os.path.basename(base_png), base_st["ipd_px"],
             base_st["roll_deg"], base_st["yaw_frac"]))
    print()

    # --- 1 POSITIVE CONTROL ----------------------------------------------
    # IT MUST BE A SHAPE CHANGE, NOT A RIGID MOVE. The landmark frame is
    # iris-centred and IPD-scaled, so a translation of the whole head cancels
    # out of it EXACTLY -- which is the property that makes the metric immune
    # to framing drift, and precisely why a nudge cannot be its control. An
    # X-scale cancels too, because the IPD that normalises the frame is itself
    # measured along X. A Z-scale does not cancel, so that is the control.
    print("1  POSITIVE CONTROL — scale the SUBJECT to Z x %.3f" % args.control_z)
    print("   A rigid nudge cannot be the control: the iris-centred frame")
    print("   removes translation exactly. Only a shape change can register.")
    _run(SCALE_Z, args.timeout, "axis_scale", SZ=args.control_z)
    _, ctl_c, _ = capture("control_scale")
    ctl_dl, ctl_verdict = report("control_scale", ctl_c, base_c)
    _run(SCALE_Z, args.timeout, "axis_unscale", SZ=1.0)
    _, back_c, _ = capture("control_back")
    report("control_back", back_c, base_c)
    if ctl_verdict != "MOVED":
        print()
        print("*** THE POSITIVE CONTROL FAILED ***")
        print("A %.1f%% Z-scale of the whole subject did not clear the noise"
              % ((args.control_z - 1.0) * 100.0))
        print("floor. The instrument cannot see a shape change of that size,")
        print("and any 'no change' it reports below would be meaningless.")
        return 4
    print()

    # --- 2 THE WRITE ------------------------------------------------------
    axis_i = {"x": 0, "y": 1, "z": 2}[args.axis]
    new_xyz = list(base_xyz)
    new_xyz[axis_i] += args.offset_cm
    # NOT beside the canonical DNA. A 54 MB test artefact one character away
    # from the only file that puts the head back is the trap this project
    # already recorded for the SM_Tree_* bakes, and it would go into LFS.
    # LandscapeLab/Saved/ is inside UE_PROJECT_ROOT and is generated content.
    test_dir = os.path.join(REPO_ROOT, "LandscapeLab", "Saved", "HeroDNA")
    os.makedirs(test_dir, exist_ok=True)
    test_dna = os.path.join(
        test_dir, "axis_test_%d_%s.dna" % (args.joint_index, args.axis))
    print("2  JOINTS ONLY — UpdateJoints, nothing else")
    d = _run(WRITE_DNA, args.timeout, "axis_write",
             IN_DNA=canonical, OUT_DNA=test_dna, INDEX=args.joint_index,
             NEWXYZ=[float(v) for v in new_xyz])
    print("  wrote %s" % os.path.relpath(test_dna, REPO_ROOT))
    print("  layer: %s" % d["layer_note"])
    print("  (%.6f, %.6f, %.6f) -> (%.6f, %.6f, %.6f), self-verified"
          % (base_xyz[0], base_xyz[1], base_xyz[2],
             new_xyz[0], new_xyz[1], new_xyz[2]))

    ap_d = _run(APPLY, args.timeout, "axis_apply_joints",
                DNA=test_dna, MESH=mesh_path, DO_JOINTS=True, DO_BASE=False,
                DO_REBUILD=False, DO_ATTACH=True, PROBES=probes)
    print("  stages: %s" % ap_d["stages"])
    worst, rows = _probe_delta(ap_d)
    for i, b, a, m in rows:
        print("    %-22s (%9.4f,%9.4f,%9.4f) -> (%9.4f,%9.4f,%9.4f)  d=%.5f"
              % (probes[i], b[0], b[1], b[2], a[0], a[1], a[2], m))
    _, j_c, _ = capture("joints_only")
    report("joints_only", j_c, base_c, worst)
    print()

    # --- 3 ATTACH ONLY ----------------------------------------------------
    print("3  ATTACH ONLY — the DNA is swapped, no update stage runs")
    _run(APPLY, args.timeout, "axis_restore_for_attach",
         DNA=canonical, MESH=mesh_path, DO_JOINTS=True, DO_BASE=False,
         DO_REBUILD=False, DO_ATTACH=True, PROBES=probes)
    at_d = _run(APPLY, args.timeout, "axis_apply_attach",
                DNA=test_dna, MESH=mesh_path, DO_JOINTS=False, DO_BASE=False,
                DO_REBUILD=False, DO_ATTACH=True, PROBES=probes)
    print("  stages: %s" % at_d["stages"])
    at_worst, _ = _probe_delta(at_d)
    _, a_c, _ = capture("attach_only")
    report("attach_only", a_c, base_c, at_worst)
    print()

    # --- 4 RESTORE --------------------------------------------------------
    print("4  RESTORE — canonical DNA back on, and prove it")
    rs_d = _run(APPLY, args.timeout, "axis_restore",
                DNA=canonical, MESH=mesh_path, DO_JOINTS=True, DO_BASE=False,
                DO_REBUILD=False, DO_ATTACH=True, PROBES=probes)
    rs_worst, _ = _probe_delta(rs_d)
    _, r_c, _ = capture("restore")
    r_dl, r_verdict = report("restore", r_c, base_c, rs_worst)
    clean = r_dl["p90_ipd"] <= p90 * 2.0
    print()
    print("  RESTORE %s" % ("CLEAN" if clean else "*** NOT CLEAN ***"))

    findings["restore_clean"] = bool(clean)
    out = os.path.join(out_dir, "axis_findings.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(findings, fh, indent=2)
        fh.write("\n")
    print("  findings -> %s" % os.path.relpath(out, REPO_ROOT))

    if not clean:
        print()
        print("The safety equipment failed. Nothing further gets written")
        print("until the restore proves clean. The Face mesh backup is in")
        print("%s" % os.path.relpath(CS.resolve(man, "backups_dir"),
                                     REPO_ROOT))
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
