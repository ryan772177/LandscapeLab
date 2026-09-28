"""THE SANCTIONED DNA ROUND TRIP — import_from_face_dna, and its control.

WHY THIS PATH AND NOT UpdateJoints
-----------------------------------
`USkelMeshDNAUtils::UpdateJoints` failed the identity round trip on ALL THREE
readers available in 5.8 — 164 cm off with the plain reader, 205 cm with the
legacy one whose docs promise the Maya->UE swizzle, and identically 164 cm
with the DNA the mesh itself carries. That is not a pipeline needing a
conversion patch; it is a pipeline this mesh did not come from. Deriving a
swizzle to make a provably-wrong apply path agree with the mesh would be
calibrating the instrument to the answer. Ruled closed 2026-08-17.

`MetaHumanCharacterEditorSubsystem::ImportFromFaceDna` is the round trip as
originally specified: UE's own tooling, mutating project content through the
path that produced it.

FACE-ONLY IMPORT EXISTS, AND THE DOCSTRING SAYS OTHERWISE
---------------------------------------------------------
The reflected doc for `import_whole_rig` claims that when unchecked "the head
DNA file will only be used for neck alignment". The CODE disagrees
(`MetaHumanCharacterEditorSubsystem.cpp:6647-6656`): the false branch calls
the SAME `FitToFaceDna` as the whole-rig branch and then `CommitFaceState`.
`FitToFaceDna` calls `FaceState->FitToFaceDna(...)` then `ApplyFaceState`
(`:6504-6520`) — a genuine parametric fit of the face state to the DNA.

What `import_whole_rig=True` adds is `CommitFaceDNA` (baking the rig itself,
which is what makes the body type fixed and non-editable) plus forcing
`AlignmentOptions=None` and `bAdaptNeck=false`.

**So we import with `import_whole_rig=False` and the body stays editable.**
The trade is real and is stated rather than hidden: a parametric fit is
limited by what the MetaHuman face model can express, which is the same
effect already measured as the model resisting the mandible. The whole-rig
path would reproduce the DNA exactly and lock the body; this one fits and
does not.

WHAT IS RENDERED
----------------
Not the assembled `/Game/MetaHumans/...` meshes — those are the output of a
full Assemble, which needs a rig, writes 252 packages and has hung this
editor on memory. `assemble_for_preview` + the transient preview Face mesh
carry the change instead, and `use_preview_mesh.py` points the LOCKED stage
at them. Identical bounds to the assembled mesh, so the framing and the
measured noise floor carry over.

THE IDENTITY ROUND TRIP IS NOT A FORMALITY
------------------------------------------
`--identity` imports the UNEDITED canonical DNA and requires the render to
come back inside the noise floor. It is the same control arm that caught
UpdateJoints, and this path earns trust the same way the other lost it.
Two representations, not one: the RENDER, and `compare_face_state` against
the untouched master character.

EXIT CODES
    0  ran; for --identity, the round trip PASSED
    2  no noise floor recorded, or bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  payload error
    6  a capture failed its landmark gate
    8  THE IDENTITY ROUND TRIP FAILED — the render moved more than the floor
    9  a capture never settled: two consecutive renders of an unchanged
       character never agreed inside the floor, so nothing here is a
       measurement
"""

from __future__ import annotations

import argparse
import datetime
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
import use_preview_mesh as UPM                    # noqa: E402


IMPORT_PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

CHARACTER  = "__CHARACTER__"
MASTER     = "__MASTER__"
DNA_PATH   = r"__DNA__"
WHOLE_RIG  = __WHOLE_RIG__

_out = {"ok": False, "error": None}

try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)

    _ch = _eal.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        if not _sub.try_add_object_to_edit(_ch):
            raise RuntimeError("try_add_object_to_edit refused the character")

    _params = _u.ImportFromDNAParams()
    _params.set_editor_property("import_whole_rig", WHOLE_RIG)
    _params.set_editor_property("isolate_head_from_body", False)
    _params.set_editor_property("alignment_options",
                                _u.MetaHumanAlignmentOptions.NONE)
    # READ THEM BACK. A params struct that silently kept its default would
    # import the wrong thing and report success.
    _out["params"] = {
        "import_whole_rig":
            bool(_params.get_editor_property("import_whole_rig")),
        "isolate_head_from_body":
            bool(_params.get_editor_property("isolate_head_from_body")),
        "alignment_options":
            str(_params.get_editor_property("alignment_options")),
    }
    if _out["params"]["import_whole_rig"] != bool(WHOLE_RIG):
        raise RuntimeError("import_whole_rig did not take")

    _code = _sub.import_from_face_dna(_ch, DNA_PATH, _params)
    _out["import_code"] = str(_code)
    _out["import_success"] = (_code == _u.ImportErrorCode.SUCCESS)

    # SECOND REPRESENTATION: the state itself, against the untouched master.
    _mst = _eal.load_asset(MASTER)
    if _mst is not None:
        if not _sub.is_object_added_for_editing(_mst):
            _sub.try_add_object_to_edit(_mst)
        for _tol in (0.001, 0.01, 0.1, 1.0):
            try:
                if bool(_sub.compare_face_state(_ch, _mst, _tol)):
                    _out["face_state_matches_master_within_norm"] = _tol
                    break
            except Exception as _e3:
                _out["compare_raised"] = str(_e3)[:150]
                break
        else:
            _out["face_state_matches_master_within_norm"] = "NOT within 1.0"

    _out["dirty"] = [str(_p.get_name()) for _p in
                     _u.EditorLoadingAndSavingUtils
                     .get_dirty_content_packages()]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:600]

print("__LL__" + _json.dumps(_out, default=str))
'''


RESTORE_PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

CHARACTER = "__CHARACTER__"

_out = {"ok": False, "error": None}
try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _ch = _eal.load_asset(CHARACTER)

    # DESTROY THE PREVIEW ACTOR FIRST. It was spawned against the PREVIOUS
    # registration of this character, so after a remove-and-reload it is
    # bound to an object that no longer exists and its transient mesh is a
    # picture of the state we are discarding. Leaving it in place makes
    # point_stage reuse it (it matches by label) and the next "baseline"
    # renders the OLD face -- measured 2026-08-17 as a post-restore baseline
    # reading yaw 0.4837 where the true canonical state renders 0.4993, which
    # then showed up as a 7.48x "effect" that was really the restore.
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _killed = []
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroPreview_Working":
            _killed.append(_a.get_actor_label())
            _eas.destroy_actor(_a)
    _out["preview_actors_destroyed"] = len(_killed)

    # Drop it from the edit session; reloading a package the subsystem holds
    # live is how a stale editor-side copy survives a "restore".
    if _sub.is_object_added_for_editing(_ch):
        _sub.remove_object_to_edit(_ch)
        _out["removed_from_edit"] = True

    _pkg = _eal.load_asset(CHARACTER).get_outermost()
    _ok, _txt = _u.EditorLoadingAndSavingUtils.reload_packages(
        [_pkg], _u.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
    _out["reload_ok"] = bool(_ok)
    _out["dirty"] = [str(_p.get_name()) for _p in
                     _u.EditorLoadingAndSavingUtils
                     .get_dirty_content_packages()]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:600]

print("__LL__" + _json.dumps(_out, default=str))
'''


LEDGER_NAME = "wholerig_imported.json"


def _ledger_path(out_dir):
    return os.path.join(out_dir, LEDGER_NAME)


def _wholerig_ledger_says(character, out_dir):
    """-> (refuse, why). FAILS CLOSED: an unreadable ledger REFUSES.

    A character that has taken a whole-rig import must not be restored with
    `reload_packages` -- that fataled the editor on 2026-08-19. The ledger is
    a DERIVED RECORD, so it cannot be trusted to say "safe"; it is trusted
    only to say "dangerous", and the absence of an answer is treated as
    dangerous too. That is the difference between this and a config file read
    as state: the unknown case refuses instead of proceeding.
    """
    p = _ledger_path(out_dir)
    if not os.path.isfile(p):
        return True, ("no whole-rig ledger at %s, so this cannot be shown "
                      "SAFE" % os.path.relpath(p, REPO_ROOT))
    try:
        with open(p, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception as e:
        return True, "whole-rig ledger unreadable (%s)" % str(e)[:60]
    hits = [r for r in rec.get("imports", [])
            if r.get("character") == character]
    if hits:
        return True, ("%s took %d whole-rig import(s), latest %s"
                      % (character, len(hits), hits[-1].get("utc")))
    # NOT "therefore safe". The master had never taken a whole-rig import and
    # the reload fataled the editor on it anyway, so absence from this ledger
    # carries no safety claim -- it is context, not clearance.
    return False, ("%s is not in the whole-rig ledger (%d entries), which is "
                   "NOT a safety claim" % (character,
                                           len(rec.get("imports", []))))


def _ledger_record(character, dna, out_dir):
    """Append a whole-rig import. Written AFTER the import reports success."""
    p = _ledger_path(out_dir)
    rec = {"_what": "Characters that have taken a whole-rig import, and are "
                    "therefore UNSAFE to restore with reload_packages. Read "
                    "by --restore, which fails closed.",
           "imports": []}
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            pass
    rec.setdefault("imports", []).append({
        "character": character,
        "dna": os.path.basename(dna),
        "utc": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")})
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.write("\n")


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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=CS.DEFAULT_MANIFEST)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--master", default="/Game/Hero/MHC_AlpineHero_Master")
    ap.add_argument("--dna", default=None,
                    help="DNA to import; defaults to the canonical one")
    ap.add_argument("--identity", action="store_true",
                    help="import the UNEDITED canonical DNA and require the "
                         "render to return inside the noise floor")
    ap.add_argument("--whole-rig", action="store_true",
                    help="LOCKS THE BODY TYPE PERMANENTLY on this asset")
    ap.add_argument("--restore", action="store_true",
                    help="discard in-memory changes to the character")
    ap.add_argument("--force", action="store_true",
                    help="run --restore even on a whole-rig-imported "
                         "character. It fataled the editor once; the refusal "
                         "text says what to do instead.")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    man = CS.load_manifest(args.manifest)
    model = CS.resolve(man, "mediapipe_model")
    out_dir = CS.resolve(man, "renders_dir")
    dna = args.dna or CS.resolve(man, "dna_canonical")

    if args.restore:
        listed, why = _wholerig_ledger_says(args.character, out_dir)
        if not args.force:
            print("=" * 72)
            print("REFUSING TO RELOAD — reload_packages fatals this editor")
            print("=" * 72)
            print("ledger: %s" % why)
            print()
            print("MEASURED TWICE ON 2026-08-19, and the second one is why")
            print("this refuses for EVERY character rather than only for")
            print("whole-rig ones:")
            print("  MHC_AlpineHero_Scratch  (3 whole-rig imports)  FATAL")
            print("  MHC_AlpineHero_Master   (NEVER whole-rig)      FATAL")
            print("Both: EXCEPTION_ACCESS_VIOLATION reading 0x470, seconds")
            print("after `LogUObjectGlobals: Reloading 1 Package(s)`, inside")
            print("the Python frame. Whole-rig is NOT the discriminating")
            print("variable — the first crash only looked that way because it")
            print("was the only arm that had been run.")
            print("Crash context: _verify/20260819_wholerig_restore_crash/")
            print()
            print("THE UNDO ON THIS PATH IS A DISK RESTORE, PROVEN THE SAME")
            print("DAY and 0.0007 cm from the state it restored:")
            print("  1  close the editor (nothing dirty first)")
            print("  2  copy the timestamped backup .uasset back over it")
            print("  3  assert the SHA-256 matches the backup's recorded hash")
            print("  4  reopen and RE-MEASURE — bytes are not the proof,")
            print("     the render is")
            print()
            print("--force runs the reload anyway. It has taken the editor")
            print("twice out of two attempts on this build.")
            return 2
        print("--force: reloading anyway. ledger: %s" % why)
        d = _run(RESTORE_PAYLOAD, args.timeout, "hero_restore",
                 CHARACTER=args.character)
        print("preview destroyed : %s" % d.get("preview_actors_destroyed"))
        print("removed from edit : %s" % d.get("removed_from_edit", False))
        print("reload            : %s" % d.get("reload_ok"))
        print("dirty             : %s" % (d.get("dirty") or "none"))
        return 0

    floor = man["capture"].get("noise_floor")
    if not floor:
        print("REFUSING: no noise floor. Run capture_shot.py --noise-floor")
        return 2
    p90 = floor["per_landmark"]["p90_ipd"]
    cm = floor["scale"]["cm_per_ipd"]

    print("=" * 72)
    print("SANCTIONED IMPORT — import_from_face_dna")
    print("=" * 72)
    print("character   %s" % args.character)
    print("dna         %s" % os.path.relpath(dna, REPO_ROOT))
    print("whole_rig   %s%s" % (args.whole_rig,
                                "   <-- LOCKS THE BODY TYPE"
                                if args.whole_rig else ""))
    print("floor       p90 %.5f IPD = %.4f cm  (%s)"
          % (p90, p90 * cm, floor["measured_utc"]))
    print()

    def capture_once(stage):
        png, _ = CS.shoot(man, stage, out_dir, args.timeout)
        try:
            c, st, fatal = CS.measure(png, model)
        except LookupError:
            print("  %s: NO FACE DETECTED" % stage)
            raise SystemExit(6)
        if fatal:
            print("  %s: gate refused — %s" % (stage, "; ".join(fatal)))
            raise SystemExit(6)
        return png, c, st

    def capture(stage):
        """A capture is not a measurement until it REPRODUCES.

        A freshly reloaded character renders a faceted, unresolved preview --
        pointed crown, polygonal facets, an asymmetric mouth -- and it
        resolves into a proper head after further assembles. Measured
        2026-08-17: a single post-restore baseline sat 7.50x the noise floor
        from the settled face, and that difference was very nearly reported
        as "importing the canonical DNA changed the face". It was the preview
        converging.

        So take shots, re-assembling between them, until two CONSECUTIVE ones
        agree inside the floor. Refuse rather than return an unsettled frame.
        """
        prev = None
        for attempt in range(4):
            if attempt:
                UPM.point_stage(args.character, True, args.timeout)
            png, c, st = capture_once(
                stage if attempt == 0 else "%s_r%d" % (stage, attempt))
            if prev is not None:
                d = CS._delta(prev, c)
                r = d["p90_ipd"] / p90 if p90 else float("inf")
                print("   settle %d: %.2fx floor" % (attempt, r))
                if r <= 2.0:
                    return png, c, st
            prev = c
        print("   *** %s NEVER SETTLED in 4 attempts ***" % stage)
        print("   Two consecutive renders of an unchanged character never")
        print("   agreed inside the floor, so no frame here is a measurement.")
        raise SystemExit(9)

    # --- BASELINE, through the same preview path the import will use -----
    print("0  BASELINE (preview mesh, pre-import)")
    UPM.point_stage(args.character, True, args.timeout)
    base_png, base_c, base_st = capture("sanctioned_baseline")
    print("   %s  ipd %.2f  roll %+.3f  yaw %.4f"
          % (os.path.basename(base_png), base_st["ipd_px"],
             base_st["roll_deg"], base_st["yaw_frac"]))
    print()

    # --- THE IMPORT ------------------------------------------------------
    print("1  IMPORT")
    d = _run(IMPORT_PAYLOAD, args.timeout, "hero_import",
             CHARACTER=args.character, MASTER=args.master, DNA=dna,
             WHOLE_RIG=bool(args.whole_rig))
    print("   params     %s" % d["params"])
    print("   code       %s   success=%s"
          % (d["import_code"], d["import_success"]))
    # NOT CENTIMETRES. compare_face_state documents its tolerance only as
    # "vector norm" over vertices AND vertex normals; normals are unit-ish
    # and their differences do not map to a distance. Measured 2026-08-17:
    # this read "NOT within 1.0" on a face whose RENDER moved 0.043 cm, and
    # >1 cm of surface would be >57 px at this scale and unmissable.
    print("   vs master  face state within norm %s  (NOT a distance)"
          % d.get("face_state_matches_master_within_norm"))
    if not d["import_success"]:
        print("   IMPORT DID NOT REPORT SUCCESS — stopping before the render")
        return 5
    if args.whole_rig:
        # RECORD IT NOW, not at the end. The render step can raise, and a
        # whole-rig import that happened but was never recorded is exactly
        # the case the ledger exists to catch.
        _ledger_record(args.character, dna, out_dir)
        print("   ledger     recorded — --restore will now REFUSE this "
              "character")
    print()

    # --- THE RENDER ------------------------------------------------------
    print("2  RENDER after import")
    UPM.point_stage(args.character, True, args.timeout)
    aft_png, aft_c, aft_st = capture(
        "sanctioned_identity" if args.identity else "sanctioned_imported")
    dl = CS._delta(base_c, aft_c)
    ratio = dl["p90_ipd"] / p90 if p90 else float("inf")
    print("   %s  ipd %.2f  roll %+.3f  yaw %.4f"
          % (os.path.basename(aft_png), aft_st["ipd_px"],
             aft_st["roll_deg"], aft_st["yaw_frac"]))
    print("   render delta p90 %.5f IPD = %.4f cm   (%.2fx floor)"
          % (dl["p90_ipd"], dl["p90_ipd"] * cm, ratio))
    print()

    rec = {
        "character": args.character, "dna": dna,
        "whole_rig": bool(args.whole_rig),
        "import_code": d["import_code"],
        "face_state_vs_master_norm":
            d.get("face_state_matches_master_within_norm"),
        "baseline_png": os.path.basename(base_png),
        "after_png": os.path.basename(aft_png),
        "render_p90_ipd": round(dl["p90_ipd"], 6),
        "render_p90_cm": round(dl["p90_ipd"] * cm, 5),
        "floor_p90_ipd": p90, "x_floor": round(ratio, 3),
    }

    if args.identity:
        passed = ratio <= 2.0
        rec["identity_passed"] = bool(passed)
        print("=" * 72)
        if passed:
            print("IDENTITY ROUND TRIP PASSED — %.2fx the floor" % ratio)
            print("Importing the UNEDITED canonical DNA returned the same")
            print("face. The sanctioned path reproduces what it is given,")
            print("which is what UpdateJoints could not do at 164 cm.")
        else:
            print("*** IDENTITY ROUND TRIP FAILED — %.2fx the floor ***"
                  % ratio)
            print("Importing the UNEDITED canonical DNA CHANGED the face.")
            print("Nothing further gets written through this path until that")
            print("is understood. Restore with --restore.")
        print("=" * 72)
        out = os.path.join(out_dir, "identity_roundtrip.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
            fh.write("\n")
        print("findings -> %s" % os.path.relpath(out, REPO_ROOT))
        return 0 if passed else 8

    print("delta recorded; character left IMPORTED (use --restore to undo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
