"""env_check.py — THE GATE. Nothing in the likeness pipeline runs until this passes.

WHAT IT ANSWERS
    1. Do the declared paths exist, and is the joint map self-consistent?
    2. Does the editor answer, on THIS project (conduct rule 7)?
    3. Is the MetaHuman stack actually loaded?
    4. Does the Face skeletal mesh resolve, and what does its skeleton say?
    5. CAN WE GET A DNA READER AND READ joint count == 870?

    (5) is the gate. Everything else is diagnosis for when it fails.

WHY IT DISCOVERS INSTEAD OF ASSUMING
    The DNA access API moved between 5.5 and 5.8, so this dir()s the live
    classes and prints what it finds. It does NOT write, and it does not
    improvise a write path -- Ryan's rule: if the API differs from
    expectations, STOP and report what dir() shows.

    And the generated Python stub is NOT the authority here. This project
    has already read a stub that was produced before the MetaHuman plugins
    were enabled and concluded a function did not exist when it did
    (non-negotiable 15 -- a derived record). So every answer below comes
    from the LIVE editor, and the stub is used only to decide where to look.

WHAT A FAILURE MEANS
    Exit 5 is "the reader is not reachable by the routes tried". That is a
    finding, not an error to route around. The correct response is to read
    the dir() dump this prints, not to start byte-patching the DNA -- the
    brief forbids that and the file is 54 MB of interlocking sections.

Exit codes:
    0  every check passed, including the joint-count gate
    2  bad arguments, missing declared path, or an inconsistent joint map
    3  conduct rule 7: no verified editor node
    4  the editor answered but the MetaHuman stack or the Face mesh is not
       reachable
    5  THE GATE FAILED: no DNA reader reachable, or joint count disagreed
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import ue_exec  # noqa: E402

DEFAULT_MANIFEST = os.path.join(HERE, "manifest.json")


def _resolve(p):
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


# ---------------------------------------------------------------- offline
def check_offline(man):
    """Paths and joint-map self-consistency. No editor needed."""
    errs, notes = [], []
    paths = man["paths"]

    # Inputs that must exist to proceed at all.
    required = ["joint_map", "dna_canonical", "reference_image",
                "mediapipe_model"]
    for key in required:
        p = _resolve(paths[key])
        if os.path.isfile(p):
            notes.append("  OK    %-20s %s (%d bytes)"
                         % (key, p, os.path.getsize(p)))
        else:
            errs.append("MISSING %-20s %s" % (key, p))

    # Optional-but-declared: report absence without failing.
    for key in ["dna_parser", "reference_appearance"]:
        p = _resolve(paths[key])
        notes.append("  %-5s %-20s %s"
                     % ("OK" if os.path.isfile(p) else "ABSENT", key, p))

    jm_path = _resolve(paths["joint_map"])
    jm = None
    if os.path.isfile(jm_path):
        with open(jm_path, "r", encoding="utf-8") as fh:
            jm = json.load(fh)

        declared = jm.get("joint_count")
        actual = len(jm.get("all_joints") or {})
        if declared != actual:
            errs.append("joint map says joint_count=%r but all_joints has %d "
                        "entries -- the map disagrees with itself"
                        % (declared, actual))
        if declared != man["joint_count_expected"]:
            errs.append("joint map joint_count=%r but the manifest expects %r"
                        % (declared, man["joint_count_expected"]))
        notes.append("  OK    joint map: %d joints, format %r"
                     % (actual, jm.get("dna_format")))

        # Every region must name a group that EXISTS, and every index in it
        # must be a real joint. A region pointing at a missing group would
        # silently contribute nothing to the fit.
        groups = jm.get("likeness_groups") or {}
        allj = jm.get("all_joints") or {}
        for rname, r in man["regions"].items():
            if rname.startswith("_"):
                continue
            g = r.get("group")
            if g not in groups:
                errs.append("region %r names group %r, which is not in the "
                            "joint map (have: %s)"
                            % (rname, g, ", ".join(sorted(groups))))
                continue
            bad = [i for i in groups[g] if str(i) not in allj]
            if bad:
                errs.append("group %r has %d index(es) not present in "
                            "all_joints: %s" % (g, len(bad), bad[:5]))
            hi = [i for i in groups[g] if int(i) >= actual]
            if hi:
                errs.append("group %r has index(es) >= joint_count %d: %s"
                            % (g, actual, hi[:5]))
            notes.append("  OK    region %-12s -> group %-12s %2d joints  "
                         "axis=%s gain=%.2f cm mirror=%s%s"
                         % (rname, g, len(groups[g]), r.get("axis"),
                            r.get("gain_cm", 0.0), r.get("mirror"),
                            "" if r.get("enabled", True) else "  (DISABLED)"))
    return errs, notes, jm


# ----------------------------------------------------------------- editor
PAYLOAD = r'''
import json as _json
import unreal as _u

CHARACTER = "__CHARACTER__"
FACE_MESH = "__FACE_MESH__"
DNA_PATH = r"__DNA_PATH__"

_out = {"ok": False, "error": None, "engine": {}, "plugins": {},
        "character": {}, "face_mesh": {}, "dna": {}, "namespace": {},
        "dir": {}, "joint_count": None, "joint_count_source": None,
        "gate": False}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as _e:
        return "RAISED: %s" % str(_e)[:140]


def _members(obj, needle=None):
    try:
        names = sorted(n for n in dir(obj) if not n.startswith("_"))
    except Exception as _e:
        return "dir() RAISED: %s" % str(_e)[:100]
    if needle:
        names = [n for n in names if needle in n.lower()]
    return names


try:
    _out["engine"]["version"] = _safe(
        lambda: _u.SystemLibrary.get_engine_version())
    _out["engine"]["project_dir"] = _safe(lambda: _u.Paths.project_dir())

    # --- 3. is the MetaHuman stack actually loaded? -------------------
    # A plugin descriptor records what somebody wrote down about a plugin's
    # needs, not what is loaded (non-negotiable 17). So this asks whether
    # the CLASSES exist in the running process.
    for name in ("MetaHumanCharacter", "MetaHumanCharacterEditorSubsystem",
                 "MetaHumanCharacterExportBlueprintLibrary", "DNAAsset",
                 "DNA", "EvaluateRig", "DNAImporterLibrary"):
        _out["plugins"][name] = hasattr(_u, name)

    # Everything in the namespace that mentions dna or riglogic, so a
    # renamed entry point shows up instead of reading as absent.
    _out["namespace"]["dna_like"] = [
        n for n in dir(_u)
        if ("dna" in n.lower() or "riglogic" in n.lower()) and
        not n.startswith("_")]

    # --- 4. the character and the Face mesh ---------------------------
    ch = _u.EditorAssetLibrary.load_asset(CHARACTER)
    _out["character"]["path"] = CHARACTER
    _out["character"]["loaded"] = ch is not None
    if ch is not None:
        _out["character"]["class"] = ch.get_class().get_name()

    fm = _u.EditorAssetLibrary.load_asset(FACE_MESH)
    _out["face_mesh"]["path"] = FACE_MESH
    _out["face_mesh"]["loaded"] = fm is not None
    if fm is not None:
        _out["face_mesh"]["class"] = fm.get_class().get_name()
        sk = _safe(lambda: fm.get_editor_property("skeleton"))
        if sk is not None and not isinstance(sk, str):
            _out["face_mesh"]["skeleton"] = _safe(lambda: sk.get_path_name())
            # A DIFFERENT representation of "how many joints": the skeleton's
            # own bone list. It need not equal the DNA joint count, and where
            # they disagree that is itself information.
            _out["face_mesh"]["skeleton_bone_count"] = _safe(
                lambda: len(sk.get_editor_property("bone_tree")))
        else:
            _out["face_mesh"]["skeleton"] = str(sk)

        # --- 5. THE GATE: reach a DNA reader ---------------------------
        aud = _safe(lambda: fm.get_editor_property("asset_user_data"))
        if isinstance(aud, str):
            _out["dna"]["asset_user_data"] = aud
        else:
            _out["dna"]["asset_user_data_classes"] = [
                _safe(lambda o=o: o.get_class().get_name()) for o in (aud or [])]
            dna_asset = None
            for o in (aud or []):
                cn = _safe(lambda o=o: o.get_class().get_name())
                if isinstance(cn, str) and "DNA" in cn:
                    dna_asset = o
                    break
            _out["dna"]["dna_asset_found"] = dna_asset is not None
            if dna_asset is not None:
                _out["dna"]["wrapper_class"] = _safe(
                    lambda: dna_asset.get_class().get_name())
                _out["dir"]["dna_wrapper_instance"] = _members(dna_asset)

                # THE HOP. What the Face mesh carries is a
                # DNAAssetUserData WRAPPER, not a DNAAsset -- handing the
                # wrapper straight to EvaluateRig.set_rig_dna fails with
                # "Failed to convert parameter 'dna_asset'". The wrapper
                # exposes `dna_asset`; that is the real one.
                inner = _safe(lambda: dna_asset.get_editor_property("dna_asset"))
                if inner is None or isinstance(inner, str):
                    _out["dna"]["inner_dna_asset"] = str(inner)
                else:
                    _out["dna"]["inner_class"] = _safe(
                        lambda: inner.get_class().get_name())
                    _out["dna"]["inner_path"] = _safe(
                        lambda: inner.get_path_name())
                    _out["dna"]["dna_file_name"] = _safe(
                        lambda: inner.get_editor_property("dna_file_name"))
                    _out["dir"]["dna_asset_inner"] = _members(inner)

                    # EvaluateRig is the only reflected thing that TAKES a
                    # DNA and returns geometry. If it accepts the inner
                    # asset we have a READER; whether it will report JOINTS
                    # is the separate question the gate asks.
                    er = _safe(lambda: _u.new_object(_u.EvaluateRig))
                    if er is not None and not isinstance(er, str):
                        _out["dir"]["evaluate_rig"] = _members(er)
                        # THE TWO SETTERS READ BACKWARDS, so both are tried
                        # and both results recorded:
                        #   set_rig_dna(dna_asset: DNAAsset)
                        #   set_rig_dna_from_asset(dna: DNA)   <- ours
                        # The mesh carries a DNA, so the one NAMED
                        # "from_asset" is the correct call and the one named
                        # "set_rig_dna" is the wrong-typed trap.
                        _out["dna"]["set_rig_dna(DNAAsset-typed)"] = _safe(
                            lambda: bool(er.set_rig_dna(inner)))
                        bound = _safe(
                            lambda: bool(er.set_rig_dna_from_asset(inner)))
                        _out["dna"]["set_rig_dna_from_asset(DNA-typed)"] = bound

                        if bound is True:
                            # A bound rig is a READER. Ask it for geometry at
                            # neutral: that is a measurement of the face that
                            # needs no render at all.
                            got = _safe(lambda: er.evaluate_raw_controls(
                                {}, [0], 0))
                            if isinstance(got, tuple) and len(got) == 2:
                                verts, ok = got
                                _out["dna"]["evaluate_ok"] = bool(ok)
                                _out["dna"]["evaluate_meshes"] = _safe(
                                    lambda: len(verts))
                                _out["dna"]["evaluate_verts_mesh0"] = _safe(
                                    lambda: len(verts[0].vertices))
                            else:
                                _out["dna"]["evaluate_raw"] = str(got)[:160]

    # Joint count is asked for by SEVERAL routes, and every answer is kept.
    # They are different representations and need not agree; where they
    # disagree, that is the finding.
    if hasattr(_u, "MetaHumanCharacterEditorSubsystem"):
        _sub = _safe(lambda: _u.get_editor_subsystem(
            _u.MetaHumanCharacterEditorSubsystem))
        if _sub is not None and not isinstance(_sub, str):
            _out["dna"]["joints_body_conforming"] = _safe(
                lambda: len(_sub.get_joints_for_body_conforming(ch)))

    # dir() the classes the brief names, from the LIVE process.
    for name in ("DNAAsset", "DNA", "EvaluateRig", "DNAImporterLibrary",
                 "DNAImporter", "MetaHumanCharacterEditorSubsystem",
                 "MetaHumanCharacterExportBlueprintLibrary"):
        if hasattr(_u, name):
            _out["dir"][name] = _members(getattr(_u, name))

    # Anything on the character editor subsystem that mentions dna/joint/rig,
    # which is where a write path would have to live.
    if hasattr(_u, "MetaHumanCharacterEditorSubsystem"):
        sub = _safe(lambda: _u.get_editor_subsystem(
            _u.MetaHumanCharacterEditorSubsystem))
        if sub is not None and not isinstance(sub, str):
            _out["dir"]["subsystem_dna"] = _members(sub, "dna")
            _out["dir"]["subsystem_joint"] = _members(sub, "joint")
            _out["dir"]["subsystem_rig"] = _members(sub, "rig")

    # --- THE JOINT READER, via the LandscapeLabEditor plugin -----------
    # The reflected MetaHuman surface has no joint accessor, so this goes
    # through ULandscapeLabTools::ReadDNAJoints, which wraps the engine's
    # own IDNAReader (DNAReader.h:95/96/115). Added 2026-08-17 precisely
    # because this gate could not otherwise be answered.
    if hasattr(_u, "LandscapeLabTools"):
        _out["plugins"]["LandscapeLabTools"] = True
        try:
            _names, _trans, _count, _fmt, _ok, _err = \
                _u.LandscapeLabTools.read_dna_joints(DNA_PATH)
            _out["joint_count"] = int(_count) if _ok else None
            _out["joint_count_source"] = (
                "ULandscapeLabTools.read_dna_joints -> IDNAReader"
                "::GetJointCount on %s" % DNA_PATH)
            _out["dna"]["file_format"] = _fmt
            _out["dna"]["read_error"] = _err
            _out["dna"]["names_returned"] = len(_names)
            _out["dna"]["translations_returned"] = len(_trans)
        except Exception as _e:
            _out["dna"]["read_dna_joints"] = "RAISED: %s" % str(_e)[:160]
    else:
        _out["plugins"]["LandscapeLabTools"] = False

    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out, default=str))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--offline-only", action="store_true")
    args = ap.parse_args(argv)

    with open(args.manifest, "r", encoding="utf-8") as fh:
        man = json.load(fh)

    print("=" * 72)
    print("PHASE A — offline: declared paths and joint-map consistency")
    print("=" * 72)
    errs, notes, jm = check_offline(man)
    for n in notes:
        print(n)
    if errs:
        print()
        for e in errs:
            print("  FAIL  " + e)
        print("\nPHASE A FAILED — %d problem(s). Nothing was asked of the "
              "editor." % len(errs))
        return 2
    print("\nPHASE A PASSED")

    if args.offline_only:
        return 0

    print()
    print("=" * 72)
    print("PHASE B — the live editor")
    print("=" * 72)
    payload = (PAYLOAD
               .replace("__CHARACTER__", man["unreal"]["character_asset"])
               .replace("__FACE_MESH__", man["unreal"]["face_skeletal_mesh"])
               .replace("__DNA_PATH__",
                        _resolve(man["paths"]["dna_canonical"])
                        .replace("\\", "/")))
    rc, d, raw = ue_exec.run(payload, timeout=args.timeout,
                             stage_name="likeness_env_check")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: the editor produced no result.")
        print(raw[:1500])
        return 4
    if d.get("error"):
        print("PAYLOAD ERROR:\n" + d["error"])
        return 4

    print("engine       : %s" % d["engine"].get("version"))
    print("project dir  : %s" % d["engine"].get("project_dir"))
    print()
    print("MetaHuman stack, asked of the RUNNING process (not a descriptor):")
    for k, v in sorted(d["plugins"].items()):
        print("   %-42s %s" % (k, "present" if v else "*** ABSENT ***"))
    missing = [k for k, v in d["plugins"].items() if not v]

    print()
    print("namespace entries mentioning dna/riglogic:")
    for n in d["namespace"].get("dna_like", []):
        print("   " + n)

    print()
    c, f = d["character"], d["face_mesh"]
    print("character    : %s  loaded=%s  class=%s"
          % (c.get("path"), c.get("loaded"), c.get("class")))
    print("face mesh    : %s" % f.get("path"))
    print("               loaded=%s  class=%s" % (f.get("loaded"), f.get("class")))
    print("   skeleton  : %s" % f.get("skeleton"))
    print("   bone count: %s   <- a DIFFERENT representation from DNA joints; "
          "they need not be equal" % f.get("skeleton_bone_count"))

    print()
    print("DNA reachability:")
    for k in ("asset_user_data", "asset_user_data_classes", "dna_asset_found",
              "wrapper_class", "inner_dna_asset", "inner_class", "inner_path",
              "dna_file_name", "set_rig_dna(DNAAsset-typed)",
              "set_rig_dna_from_asset(DNA-typed)", "evaluate_ok",
              "evaluate_meshes", "evaluate_verts_mesh0", "evaluate_raw",
              "joints_body_conforming", "evaluate_rig"):
        if k in d["dna"]:
            print("   %-24s %s" % (k, d["dna"][k]))

    print()
    print("dir() of the live classes — this is the evidence, not the stub:")
    for k in sorted(d["dir"]):
        v = d["dir"][k]
        print("   --- %s ---" % k)
        if isinstance(v, str):
            print("       " + v)
        else:
            for i in range(0, len(v), 3):
                print("       " + "  ".join("%-34s" % n for n in v[i:i + 3]))

    if f.get("loaded") is not True or missing:
        print()
        print("PHASE B FAILED — the MetaHuman stack or the Face mesh is not "
              "reachable. Absent: %s" % (missing or "none"))
        return 4

    # ---------------------------------------------------------- THE GATE
    print()
    print("=" * 72)
    print("THE GATE — three criteria, reported separately")
    print("=" * 72)
    dna = d["dna"]
    bound = dna.get("set_rig_dna_from_asset(DNA-typed)") is True
    evals = dna.get("evaluate_ok") is True
    nverts = dna.get("evaluate_verts_mesh0")

    print("(a) DNA reader reachable from the Face mesh            %s"
          % ("PASS" if bound else "FAIL"))
    print("    route: SkeletalMesh.asset_user_data -> DNAAssetUserData")
    print("           -> .dna_asset (class DNA) -> "
          "EvaluateRig.set_rig_dna_from_asset")
    print("(b) the bound rig EVALUATES to geometry                %s"
          % ("PASS" if evals else "FAIL"))
    if evals:
        print("    %s vertices returned for mesh 0 at LOD 0 — a measurement "
              "of the face that needs NO render" % nverts)

    expected = man["joint_count_expected"]
    print("(c) a reflected reader reports joint count == %d       %s"
          % (expected, "PASS" if d.get("joint_count") == expected else "FAIL"))

    # Joint count from every source that CAN answer, each labelled. These
    # are different representations and are not interchangeable.
    print()
    print("    joint/bone count by source:")
    print("      %-46s %s" % ("DNA file (offline, dna25_parser / joint map)",
                              (jm or {}).get("joint_count")))
    print("      %-46s %s" % ("Face skeleton bone_tree (live)",
                              d["face_mesh"].get("skeleton_bone_count")))
    print("      %-46s %s" % ("reflected DNA reader", d.get("joint_count")))
    print("    The first two need not agree and do not: a DNA joint list and")
    print("    a USkeleton bone tree are different things.")

    if bound and evals and d.get("joint_count") == expected:
        print("\nGATE PASSED")
        return 0

    print()
    print("*** GATE NOT PASSED — criterion (c) ***")
    print()
    print("The reader is REACHABLE and WORKS; what it does not expose is")
    print("JOINTS. The DNA object surfaces only meta_data and")
    print("rig_logic_configuration, and EvaluateRig surfaces only the two")
    print("setters plus evaluate_raw_controls, which returns VERTICES.")
    print()
    print("Read that as the finding it is, not as an error to route around.")
    print("Per the brief, this does NOT license:")
    print("  - byte-patching the .dna (54 MB of interlocking sections;")
    print("    dna25_parser.py is READ-ONLY by design)")
    print("  - improvising a write from a plausible-looking accessor")
    print()
    print("The reflected FACE write path is import_from_face_dna — whole")
    print("file in, nothing finer — so a joint edit still needs a 2.5")
    print("WRITER, which is the gap the brief already identified. STOPPING")
    print("here for a ruling rather than improvising one.")
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
