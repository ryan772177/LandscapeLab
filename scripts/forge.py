"""forge.py — the generation forge. TEN mandatory stages, one command.

    python scripts/forge.py --asset church

AUTHORIZED 2026-08-30 by Ryan, together with the amendment that made the
acceptance rule ABSOLUTE rather than comparative: ruling 7 declined Hunyuan, so
a comparative winner became impossible by the operator's own hand and a
criterion that cannot be met is a dead letter, not a high bar.

THE STAGES, AND NONE IS OPTIONAL

    1  check_generation_input.py     measured input floors        PROVEN
    2  ai_input_guard.py --strict    BEFORE weights load          PROVEN
    3  generate                      TRELLIS, formats=["mesh"]
    4  retopo / decimate             MANDATORY, headless Blender
    5  pivot to base-centre
    6  UV state (established if absent)
    7  measured intake               against recipes/forge.json floors
    8  ASSETS.md row
    9  FORGE_LOG.md cost line
   10  REAL-WORLD SCALE               orientation gate, then the declared
                                      scale, read back. RATIFIED 2026-08-30.

Stages 1 and 2 are CALLED, never reimplemented. They already exist, they are
already proven, and a second copy of a licence gate is the
two-lists-one-badly-stored defect on the one rule whose violation cannot be
detected after the fact.

WHAT IT REFUSES
    * an asset whose recipe declares no views -- a forge run with no reference
      has no provenance
    * an input that fails the measured floors, naming the figure that failed
    * an input the AI guard does not positively clear (--strict fails closed)
    * an intake result below the sheet-vs-volume floor, or not watertight
    * an asset that declares no `scale` -- a generated mesh carries NO UNITS
      and every other check is scale-invariant, so a 39 cm church passes all
      of them. Checked BEFORE the GPU runs.

WHAT IT REPORTS BUT DOES NOT HIDE
    Genus. Collapse decimation preserves topology, so a mesh can meet its
    triangle budget with every handle intact -- measured on the church,
    genus 61 before and after. The field is named `tri_within_budget` for
    exactly that reason: it is a TRIANGLE claim, not a topology claim.

    And NON-REPRODUCIBILITY. The seed fixes the sampling path; CUDA and spconv
    do not fix bytes. Two runs of identical inputs gave 190,498 and 190,562
    vertices. The VERDICT is reproducible (thin/long 0.4317 both times); the
    MESH is not. The forged .fbx is therefore the artefact of record -- kept
    and committed, never regenerated on demand.

Exit 0 forged and within budget; 2 refused at a gate; 3 a stage failed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
FORGE_RECIPE = os.path.join(REPO, "recipes", "forge.json")
PERF = os.path.join(REPO, "recipes", "perf_budgets.json")
OUTROOT = os.path.join(REPO, "_verify", "20260830_forge")
FORGE_LOG = os.path.join(REPO, "FORGE_LOG.md")
ASSETS_MD = os.path.join(REPO, "ASSETS.md")

# Written at the top of stage10_command.txt. The file exists to be COPY-PASTED,
# so the warning has to travel with it -- the person pasting it has not read
# LESSONS.md.
_STAGE10_HEADER = (
    "# RUN THIS FROM POWERSHELL, NOT GIT BASH.\n"
    "# Git Bash (MSYS2) rewrites arguments that look like absolute POSIX\n"
    "# paths against the Git install root, so --set DEST=/Game/Scratch/X\n"
    "# arrives as DEST=C:/Program Files/Git/Game/Scratch/X and the payload's\n"
    "# delete-guard refuses. In Git Bash, prefix MSYS_NO_PATHCONV=1.\n"
    "# Measured 2026-08-30; see R-FORGE REJECTED.\n")


def _wsl(p):
    """Windows path -> the /mnt/c form WSL sees. One conversion, one place."""
    p = os.path.abspath(p).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        return "/mnt/" + p[0].lower() + p[2:]
    return p


def _load(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _run(cmd, **kw):
    # ⛔ encoding IS NOT OPTIONAL HERE. `text=True` alone decodes with the
    # LOCALE codec -- cp1252 on this machine -- and the TRELLIS subprocess
    # emits UTF-8 tqdm progress bars. U+258F "▏" is E2 96 8F, and 0x8F is
    # UNDEFINED in cp1252, so the reader thread died with UnicodeDecodeError
    # mid-run on 2026-08-30.
    #
    # It survived by WHICH STREAM tqdm uses. tqdm writes to STDERR by
    # default, so the STDERR reader died (Thread-4) and stdout came through
    # intact -- the run finished. Measured, on the exact byte sequence:
    #
    #     text=True alone     rc 0, stdout is None, marker NOT found
    #     + encoding=utf-8    rc 0, stdout 423 chars, marker found
    #
    # Two ways that luck runs out. A child that bars to stdout takes
    # `"__FORGE_GEN__" not in (p.stdout or "")` straight to "could not look"
    # over a perfectly good 56-second GPU run. And stage 3's error path
    # prints p.stderr -- which was already None here, so a GENUINE failure
    # would have been reported with no diagnostic at all.
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--skip-generate", action="store_true",
                    help="reuse an existing stage-3 .obj. For re-running the "
                         "FINISH stages without paying for the GPU again; the "
                         "run is still recorded as a forge run and still says "
                         "in the log that generation was reused.")
    ap.add_argument("--overwrite", action="store_true",
                    help="permit stage 10 to overwrite an existing "
                         "/Game/Scratch/Forge_<asset> level. Levels are keyed "
                         "by asset and new_level OVERWRITES, so re-staging is "
                         "deliberate or it is refused.")
    ap.add_argument("--emit-stage10", action="store_true",
                    help="re-emit stage10_command.txt from the recipe and the "
                         "EXISTING finish_report.json, running no stage. For "
                         "when the payload's parameters change after a forge: "
                         "--skip-generate would re-run stage 4 and overwrite "
                         "the .fbx, which R-FORGE names the artefact of "
                         "record.")
    args = ap.parse_args(argv)

    spec_all = _load(FORGE_RECIPE)
    if args.asset not in spec_all["assets"]:
        print("REFUSE: no such asset %r in recipes/forge.json. Known: %s"
              % (args.asset, ", ".join(sorted(spec_all["assets"]))))
        return 2
    spec = spec_all["assets"][args.asset]
    floors = spec_all["_intake_floors"]

    rules = _load(PERF)["asset_rules"]
    cls = spec["asset_class"]
    if cls not in rules["max_tris"]:
        print("REFUSE: asset_class %r has no max_tris in perf_budgets.json. "
              "The budget is READ, never typed here." % cls)
        return 2
    max_tris = rules["max_tris"][cls]

    name = spec["name"]
    outdir = os.path.join(OUTROOT, args.asset)
    os.makedirs(outdir, exist_ok=True)
    report = {"asset": args.asset, "name": name, "asset_class": cls,
              "max_tris": max_tris, "stages": {}}
    t_start = time.time()

    print("FORGE: %s  (%s, max_tris %d from perf_budgets.json)"
          % (name, cls, max_tris))

    # ---- STAGE 10 PRECONDITION: the scale must be DECLARED ---------------
    # Checked HERE, before a GPU minute is spent, because a forge that
    # generates first and discovers it cannot place the result has already
    # paid for the run. Same refusal class as missing views.
    scale = spec.get("scale") or {}
    if "height_cm" in scale:
        target_cm = float(scale["height_cm"])
        scale_why = "declared height_cm"
    elif all(k in scale for k in ("ratio_against", "ratio", "reference_cm")):
        target_cm = float(scale["ratio"]) * float(scale["reference_cm"])
        scale_why = ("%s x %s (%s)" % (scale["ratio"], scale["reference_cm"],
                                       scale["ratio_against"]))
    else:
        print("REFUSE: %r declares no usable `scale`. A generated mesh carries "
              "NO UNITS -- TRELLIS normalises its output, and every stage 1-9 "
              "check is scale-invariant, so nothing downstream would notice a "
              "39 cm church. Declare `height_cm`, or `ratio_against` + "
              "`ratio` + `reference_cm`, in recipes/forge.json." % args.asset)
        return 2
    report["scale_target_cm"] = target_cm
    report["scale_why"] = scale_why
    print("      scale target %.1f cm  (%s)" % (target_cm, scale_why))

    # ⭐ THE PLAUSIBILITY BAND -- ABSOLUTE, checked BEFORE the GPU runs.
    #
    # Every scale check the forge had was RELATIVE: a ratio against a
    # reference, or a read-back against the target it was told. None of them
    # can see a wrong REFERENCE. The church was built to 2.5 x 536.5 and every
    # check passed, because 536.5 was a sound measurement of a chalet whose
    # roof was buried 201.49 cm in its walls.
    #
    # For a ratio-scored asset the band is declared on the REFERENCE and the
    # target band is DERIVED by the ratio -- one declaration, no second number
    # to drift. For a flat height_cm asset the band is declared directly.
    band_lo = band_hi = None
    if "reference_plausible_cm" in scale:
        rb = scale["reference_plausible_cm"]
        ref = float(scale["reference_cm"])
        if not (float(rb[0]) <= ref <= float(rb[1])):
            print("REFUSE: reference_cm %.1f is OUTSIDE its plausible band "
                  "%.0f-%.0f. The ratio would be scored against a reference "
                  "that is itself wrong -- which is exactly how ruling 1 came "
                  "to be measured against 536.5 instead of 738.0. Fix the "
                  "reference, not the ratio." % (ref, rb[0], rb[1]))
            return 2
        band_lo = float(rb[0]) * float(scale["ratio"])
        band_hi = float(rb[1]) * float(scale["ratio"])
    elif "plausible_cm" in scale:
        band_lo, band_hi = float(scale["plausible_cm"][0]), \
            float(scale["plausible_cm"][1])
    if band_lo is None:
        print("REFUSE: %r declares no plausibility band. Add "
              "`plausible_cm` (flat height) or `reference_plausible_cm` "
              "(ratio-scored). A relative check cannot catch a wrong "
              "reference, so an absolute one is required." % args.asset)
        return 2
    if not (band_lo <= target_cm <= band_hi):
        print("REFUSE: target %.1f cm is OUTSIDE the plausible band "
              "%.0f-%.0f." % (target_cm, band_lo, band_hi))
        return 2
    print("      plausible band %.0f-%.0f cm  -- target is inside"
          % (band_lo, band_hi))

    if args.emit_stage10:
        fin_p = os.path.join(outdir, "finish_report.json")
        if not os.path.exists(fin_p):
            print("REFUSE: no finish_report.json at %s -- there is nothing to "
                  "re-emit a stage-10 command FOR. Forge the asset first."
                  % fin_p)
            return 2
        _fin = _load(fin_p)
        _bb = _fin["bbox_after"]
        _sz = [round(_bb["max"][i] - _bb["min"][i], 5) for i in range(3)]
        _fbx = os.path.join(outdir, name + ".fbx")
        _cmd = _stage10_cmd(args.asset, name, _fbx, target_cm, scale_why,
                            scale, _sz, args.overwrite)
        with io.open(os.path.join(outdir, "stage10_command.txt"), "w",
                     encoding="utf-8") as fh:
            fh.write(_STAGE10_HEADER + _cmd + "\n")
        print("\nRE-EMITTED stage10_command.txt (no stage was run):")
        print(_cmd)
        return 0

    # ---- views -----------------------------------------------------------
    # .get: a recipe OMITTING the key must reach the designed exit-2
    # refusal below, not a KeyError traceback at exit 1 (Pass 3
    # 2026-09-16 F6).
    refs = [os.path.join(REPO, spec.get("refs_dir", ""), v)
            for v in (spec.get("views") or [])]
    if not refs:
        print("REFUSE: %r declares no views. A forge run with no reference "
              "has no provenance, and %s" % (args.asset, spec.get("_views", "")))
        return 2
    missing = [r for r in refs if not os.path.exists(r)]
    if missing:
        print("REFUSE: %d declared view(s) do not exist:" % len(missing))
        for m in missing:
            print("   " + m)
        return 2

    # ---- STAGE 1: measured input floors ----------------------------------
    print("\n[1/9] check_generation_input.py")
    # --set for a multi-view asset: the floors apply per SET, ruled
    # 2026-08-30. The master takes them in full; rotations take set floors
    # plus a GROUND-LINE consistency check. A single-view asset gets the full
    # per-image floors, because there is no master to inherit from.
    _mode = ["--set"] if len(refs) > 1 else []
    p = _run([sys.executable, os.path.join(REPO, "scripts",
                                           "check_generation_input.py")]
             + _mode + refs)
    print(p.stdout.rstrip()[-1200:])
    if p.returncode != 0:
        print("REFUSED at stage 1: an input does not meet the measured floors.")
        return 2
    report["stages"]["1_input_floors"] = "ok (%d views)" % len(refs)

    # ---- STAGE 2+3: guard, then generate ---------------------------------
    obj_path = os.path.join(outdir, name + "_raw.obj")
    gen_report = os.path.join(outdir, "generate_report.json")
    # reused reflects the branch ACTUALLY taken (Pass 3 2026-09-16 F4):
    # --skip-generate with a MISSING .obj runs real generation, and the
    # FORGE_LOG line must not tag that GPU spend as (REUSED).
    reused = args.skip_generate and os.path.exists(obj_path)
    if reused:
        print("\n[2/9] ai_input_guard  -- skipped with generation")
        print("[3/9] generate        -- REUSED %s" % obj_path)
        report["stages"]["2_ai_guard"] = "not run (generation reused)"
        report["stages"]["3_generate"] = "REUSED existing obj"
        gen = _load(gen_report) if os.path.exists(gen_report) else {}
    else:
        job = {
            "asset_key": args.asset,
            "name": name,
            "views": [_wsl(r) for r in refs],
            "model_repo": spec["provenance"]["model_repo"],
            "seed": spec["seed"],
            "sampler": spec["sampler"],
            "out_obj": _wsl(obj_path),
            "out_report": _wsl(gen_report),
        }
        job_path = os.path.join(outdir, "forge_job.json")
        with io.open(job_path, "w", encoding="utf-8") as fh:
            json.dump(job, fh, indent=1)

        print("\n[2/9] ai_input_guard --strict, on every view, before weights")
        print("[3/9] generate -- TRELLIS multi-image, %d views" % len(refs))
        p = _run(["wsl", "-e", "bash",
                  _wsl(os.path.join(REPO, "scripts", "trellis",
                                    "run_forge.sh")),
                  _wsl(job_path)])
        tail = (p.stdout or "")[-400:]
        # An AI-GUARD refusal is a GATE VERDICT, not an instrument
        # failure (Pass 3 2026-09-16 F2): run_forge.sh echoes a marker
        # when the guard loop refuses, and it exits 2 here as the
        # docstring's contract promises — never narrated as
        # could-not-look.
        if "__FORGE_GUARD_REFUSED__" in (p.stdout or ""):
            print("REFUSED at stage 2: the AI input guard did not "
                  "positively clear an input (--strict fails closed). "
                  "R-AIGATE: this is a judgment, not a failure — do not "
                  "retry; fix or remove the offending input.")
            print(tail)
            return 2
        if p.returncode != 0 or "__FORGE_GEN__" not in (p.stdout or ""):
            print("STAGE 3 FAILED (rc=%d). This is 'could not look', not "
                  "'the asset is bad'." % p.returncode)
            print(tail)
            print((p.stderr or "")[-600:])
            report["stages"]["3_generate"] = (
                "FAILED: rc=%d / marker %s" % (
                    p.returncode,
                    "present" if "__FORGE_GEN__" in (p.stdout or "")
                    else "absent"))
            _write_report(report, outdir)
            return 3
        gen = json.loads((p.stdout or "").split("__FORGE_GEN__")[-1].strip())
        if gen.get("error"):
            print("STAGE 3 reported an error: " + str(gen["error"])[:400])
            # cost the failed GPU run when the report carries its cost
            # (F3); stale-report guard: the report on disk reflects THIS
            # failed run, not the previous success
            if gen.get("run_s") is not None:
                _append_forge_log(
                    "| %s | FAILED stage 3 | run %ss | VRAM peak %s MiB |"
                    % (spec.get("name", args.asset), gen.get("run_s"),
                       gen.get("vram_peak_MiB")))
            report["stages"]["3_generate"] = ("FAILED: "
                                              + str(gen["error"])[:200])
            _write_report(report, outdir)
            return 3
        report["stages"]["2_ai_guard"] = "all %d views cleared (--strict)" % len(refs)
        report["stages"]["3_generate"] = "ok"
        print("      %d v / %d f  thin/long %s  watertight %s  genus %s"
              % (gen["vertices"], gen["faces"], gen["thin_over_long"],
                 gen["watertight"], gen["genus"]))
        print("      load %ss  run %ss  VRAM peak %s MiB"
              % (gen.get("load_s"), gen.get("run_s"),
                 gen.get("vram_peak_MiB")))
    report["generate"] = gen

    # ---- STAGE 4/5/6: retopo, pivot, UVs ---------------------------------
    print("\n[4/9] retopo/decimate  [5/9] base-centre pivot  [6/9] UV state")
    fbx = os.path.join(outdir, name + ".fbx")
    finish_report = os.path.join(outdir, "finish_report.json")
    p = _run([BLENDER, "--background", "--python",
              os.path.join(REPO, "scripts", "blender", "forge_finish.py"),
              "--", "--in", obj_path, "--out-fbx", fbx,
              "--report", finish_report,
              "--max-tris", str(max_tris), "--asset-class", cls])
    if not os.path.exists(finish_report):
        print("STAGE 4 FAILED -- no report written.")
        print((p.stdout or "")[-800:])
        report["stages"]["4_finish"] = "FAILED: no report written"
        _write_report(report, outdir)
        return 3
    fin = _load(finish_report)
    if fin.get("error"):
        print("STAGE 4 reported an error: " + str(fin["error"])[:400])
        report["stages"]["4_finish"] = "FAILED: " + str(fin["error"])[:200]
        _write_report(report, outdir)
        return 3
    b, a = fin["before"], fin["after"]
    print("      verts   %7d -> %7d" % (b["verts"], a["verts"]))
    print("      faces   %7d -> %7d" % (b["faces"], a["faces"]))
    print("      tris    %7d -> %7d   (ceiling %d, within: %s)"
          % (b["triangles"], a["triangles"], max_tris, fin["tri_within_budget"]))
    print("      genus   %7s -> %7s   watertight %s -> %s"
          % (b["genus"], a["genus"], b["watertight"], a["watertight"]))
    print("      UVs     %7s -> %7s   (%s)"
          % (b["has_uvs"], a["has_uvs"], fin.get("uv_action")))
    print("      pivot   %s  base_at_origin %s"
          % (fin["pivot"]["rule"], fin["pivot"]["base_at_origin"]))
    if fin.get("_genus_finding"):
        print("      !! " + fin["_genus_finding"])
    report["stages"]["4_retopo"] = ("%d -> %d tris" % (b["triangles"],
                                                       a["triangles"]))
    report["stages"]["5_pivot"] = fin["pivot"]["rule"]
    report["stages"]["6_uv"] = fin.get("uv_action")
    report["finish"] = fin

    # ---- STAGE 7: measured intake ----------------------------------------
    print("\n[7/9] measured intake")
    tol = gen.get("thin_over_long")
    fails = []
    if tol is None:
        fails.append("thin_over_long NOT MEASURED -- that is 'could not look'")
    elif tol < floors["thin_over_long_min"]:
        fails.append("thin_over_long %.4f < floor %.4f (flat-sheet class)"
                     % (tol, floors["thin_over_long_min"]))
    if floors.get("require_watertight") and not a.get("watertight"):
        fails.append("not watertight after finish: %d boundary, %d non-manifold"
                     % (a.get("boundary_edges", -1),
                        a.get("nonmanifold_edges", -1)))
    if not fin["tri_within_budget"]:
        fails.append("%d tris exceeds the %s ceiling of %d"
                     % (a["triangles"], cls, max_tris))
    if fails:
        print("      INTAKE REFUSES:")
        for f in fails:
            print("        - " + f)
        report["stages"]["7_intake"] = "REFUSED: " + "; ".join(fails)
        # THE COST LINE STILL LANDS (Pass 3 2026-09-16 F3): a run refused
        # at intake has already PAID for generation and the Blender
        # finish, and "a forge whose runs are not costed becomes a way to
        # spend a GPU without anyone noticing" — the register's own rule.
        _cost = _forge_log_line(spec, fin, gen,
                                round(time.time() - t_start, 1), reused)
        _append_forge_log(_cost + "  [REFUSED at stage-7 intake]")
        report["forge_log_line"] = _cost + "  [REFUSED at stage-7 intake]"
        _write_report(report, outdir)
        return 2
    print("      thin/long %.4f >= %.4f   watertight %s   %d <= %d tris"
          % (tol, floors["thin_over_long_min"], a["watertight"],
             a["triangles"], max_tris))
    report["stages"]["7_intake"] = "ok (TRIANGLES within budget; NOT a topology claim -- genus %s)" % a.get("genus")

    # ---- STAGE 8 + 9 ------------------------------------------------------
    elapsed = round(time.time() - t_start, 1)
    report["wall_s"] = elapsed
    row = _assets_row(spec, fin, gen, cls, max_tris, args.asset)
    log_line = _forge_log_line(spec, fin, gen, elapsed, reused)
    print("\n[8/9] ASSETS.md row and [9/9] FORGE_LOG cost line")
    written = _append_assets_row(row, spec["name"])
    print("      ASSETS.md: %s" % written)
    print(log_line)
    report["assets_row"] = row
    report["assets_md"] = written
    report["forge_log_line"] = log_line
    _append_forge_log(log_line)
    _write_report(report, outdir)
    # STAGE 8 IS MANDATORY (Pass 3 2026-09-16 F5): the row-NOT-written
    # escapes used to reach exit 0, re-opening the exact
    # exit-0-with-no-register-row defect _append_assets_row's docstring
    # narrates. The report is already on disk, so the row text is
    # recoverable; the exit code now says the register is incomplete.
    if "NOT written" in (written or ""):
        print("REFUSING exit 0: the ASSETS.md row was NOT written (%s). "
              "Stage 8 is mandatory; fix ASSETS.md and re-run, or add "
              "the row from forge_report.json." % written)
        return 3
    # ---- STAGE 10: real-world scale, in the editor ----------------------
    # Emitted rather than run: it needs a live editor on the right level, and
    # standing rule 11 says wait for zero editors then ask which level is
    # loaded. A forge that silently drove an editor it did not verify would be
    # the wrong-level failure class this project just ratified a rule against.
    bb = fin["bbox_after"]
    sz = [round(bb["max"][i] - bb["min"][i], 5) for i in range(3)]
    # The ratio is a RULING, and only an asset that declares `ratio_against`
    # has one. 0.0 means "no ruled ratio" and the payload then reports the
    # companion silhouette as a measurement without scoring anything against
    # it -- see the generalisation note in forge_scale_payload.txt.
    ratio_target, ratio_against = _ratio_of(scale)
    cmd = _stage10_cmd(args.asset, name, fbx, target_cm, scale_why, scale, sz,
                       args.overwrite)
    with io.open(os.path.join(outdir, "stage10_command.txt"), "w",
                 encoding="utf-8") as fh:
        fh.write(_STAGE10_HEADER + cmd + "\n")
    report["stages"]["10_scale"] = "PENDING -- run in a verified editor"
    report["stage10_command"] = cmd
    report["stage10_expected_bbox"] = sz
    print("\n[10/10] real-world scale -- run in a verified editor:")
    print("        " + cmd)
    print("        orientation gate runs first and REFUSES a sideways mesh;")
    print("        target %.1f cm from %s" % (target_cm, scale_why))
    if ratio_target > 0.0:
        print("        ratio: %.2fx %s is ASSERTED (declared in the recipe)"
              % (ratio_target, ratio_against))
    else:
        # Not a warning any more -- a statement of what will be reported.
        # Stage 10 was generalised 2026-08-30; the companion is still built
        # as a scale reference, but nothing is scored against it unless the
        # recipe declares `ratio_against`.
        print("        no ruled ratio: '%s' declares a flat height_cm, so the"
              % args.asset)
        print("        chalet companion is a SCALE REFERENCE and is measured,"
              " not scored.")

    print("\nFORGED: %s" % fbx)
    print("        report %s" % os.path.join(outdir, "forge_report.json"))
    return 0


def _ratio_of(scale):
    """(target, against). A RATIO IS A RULING, and only an asset that declares
    `ratio_against` has one -- 0.0 means there is nothing to score."""
    if "ratio_against" in scale:
        return float(scale.get("ratio", 0.0)), str(scale["ratio_against"])
    return 0.0, ""


def _level_path(asset_key):
    """/Game/Scratch/Forge_<asset>. RULED 2026-08-30: scratch levels are keyed
    BY ASSET. One shared level meant staging a second asset silently destroyed
    the first's staged scene, and `new_level` overwrites without asking."""
    return "/Game/Scratch/Forge_" + asset_key


def _stage10_cmd(asset_key, name, fbx, target_cm, scale_why, scale, sz,
                 overwrite=False):
    """Build the stage-10 command. ONE code path, called by the forge run and
    by --emit-stage10, so a re-emitted command cannot drift from the one the
    run would have produced. Duplicating this is how the church's hardcoded
    DEST survived: two constructions, only one of them maintained."""
    ratio_target, ratio_against = _ratio_of(scale)
    camel = "".join(w.capitalize() for w in asset_key.split("_"))
    # A double quote here would close the payload's own string literal.
    why = scale_why.replace('"', "'")
    # ⛔ RUN THIS FROM POWERSHELL, NOT GIT BASH. MSYS2 rewrites any argument
    # that looks like an absolute POSIX path against the Git install root, so
    # --set DEST=/Game/Scratch/X arrives as
    # DEST=C:/Program Files/Git/Game/Scratch/X and the payload's
    # /Game/Scratch/ delete-guard refuses. In Git Bash, prefix
    # MSYS_NO_PATHCONV=1. The church never hit this because DEST and LEVEL
    # were hardcoded IN the payload; parameterising them is what moved them
    # onto a command line. Measured 2026-08-30.
    return ("python scripts/ue_exec.py scripts/forge_scale_payload.txt"
            " --set SRC=%s"
            " --set DEST=%s --set NAME=%s"
            " --set LEVEL=%s"
            " --set LABEL=Forge_%s"
            " --set TARGET_CM=%s"
            " --set \"SCALE_WHY=%s\""
            " --set RATIO_TARGET=%s --set RATIO_AGAINST=%s"
            " --set OVERWRITE=%d"
            " --set EXP_X=%s --set EXP_Y=%s --set EXP_Z=%s"
            " --timeout 25"
            % (fbx.replace("\\", "/"), _dest_path(asset_key), name,
               _level_path(asset_key), camel, target_cm, why,
               ratio_target, ratio_against, 1 if overwrite else 0,
               sz[0], sz[1], sz[2]))


def _dest_path(asset_key):
    """/Game/Scratch/Forge<CamelKey> -- matches the church's existing row."""
    camel = "".join(w.capitalize() for w in asset_key.split("_"))
    return "/Game/Scratch/Forge" + camel


def _assets_row(spec, fin, gen, cls, max_tris, asset_key):
    """A row for the SIX columns ASSETS.md's forge table actually declares:
    asset | source | licence | role | coherence | verified in engine.

    The previous version emitted SEVEN fields in a different order. Nothing
    ever forced the two into agreement, because the row was never written to
    the file -- see _append_assets_row.
    """
    a = fin["after"]
    views = ",".join(spec.get("views", []))
    licence = spec["provenance"].get(
        "licence",
        "TRELLIS **MIT**; the references are the operator's own. All %d "
        "cleared `ai_input_guard.py --strict` BEFORE the weights loaded "
        "(R-AIGATE)" % gen.get("n_views", 0))
    return ("| `%s/%s` | **GENERATED** -- %s from %d operator concept "
            "references (`%s/{%s}`), seed %s | %s | %s | %d tris (%s ceiling "
            "%d), watertight %s, **genus %s -- topological noise NOT "
            "removed**, UVs: %s | %s |"
            % (_dest_path(asset_key), spec["name"],
               spec["provenance"]["engine"], gen.get("n_views", 0),
               spec.get("refs_dir", "?"), views, spec.get("seed"),
               licence, spec["provenance"]["source"],
               a["triangles"], cls, max_tris, a["watertight"], a["genus"],
               fin.get("uv_action"),
               "NO -- stage 10 not yet run in a verified editor"))


def _append_assets_row(row, name):
    """Write the row into ASSETS.md's forge table, REPLACING any row for the
    same asset.

    ASSETS.md is a REGISTER -- one row per asset -- not a run log like
    FORGE_LOG.md, which correctly appends once per run. Appending here would
    add a second row for the same asset on every re-forge, and pipeline rule 3
    says a re-run rebuilds deterministically.

    Stage 8 previously COMPUTED this row, stashed it in forge_report.json, and
    wrote it nowhere. The stage printed its own header either way, so the wood
    stack forged to exit 0 with no register row at all. The church's row had
    been written BY HAND, which is exactly why nothing noticed -- and
    ASSETS.md's own preamble claims "scripts/forge.py writes the row", a claim
    that was false for as long as it has existed. That is the
    unverified-claim-in-our-own-artefact class, non-negotiable 9.
    """
    if not os.path.exists(ASSETS_MD):
        return "ASSETS.md missing -- row NOT written"
    with io.open(ASSETS_MD, encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    hdr = "| asset | source | licence | role | coherence |"
    sep = None
    for i, ln in enumerate(lines):
        if ln.startswith(hdr):
            sep = i + 1
            break
    if sep is None or sep >= len(lines) or not lines[sep].startswith("|---"):
        return "forge table not found -- row NOT written"
    end = sep + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    body = lines[sep + 1:end]
    key = "/" + name + "`"
    for j, ln in enumerate(body):
        if key in ln:
            if ln == row:
                return "row already current (unchanged)"
            body[j] = row
            verb = "REPLACED"
            break
    else:
        body.append(row)
        verb = "ADDED"
    lines[sep + 1:end] = body
    with io.open(ASSETS_MD, "w", encoding="utf-8", newline="") as fh:
        fh.write(nl.join(lines))
    return "row %s for %s" % (verb, name)


def _forge_log_line(spec, fin, gen, elapsed, reused):
    a = fin["after"]
    b = fin["before"]
    return ("| %s | %s | %d views | gen %ss / VRAM %s MiB%s | %d -> %d tris | "
            "genus %s -> %s | UVs %s | %.1f s total |"
            % (spec["name"], spec["asset_class"], gen.get("n_views", 0),
               gen.get("run_s"), gen.get("vram_peak_MiB"),
               " (REUSED)" if reused else "",
               b["triangles"], a["triangles"], b["genus"], a["genus"],
               a["has_uvs"], elapsed))


def _append_forge_log(line):
    head = ("# FORGE_LOG.md — every generation run, with what it cost\n\n"
            "Appended by `scripts/forge.py`. One line per run. A forge whose\n"
            "runs are not costed becomes a way to spend a GPU without anyone\n"
            "noticing, and a generated asset with no logged provenance is the\n"
            "one thing R-AIGATE cannot check after the fact.\n\n"
            "| asset | class | inputs | generate | retopo | genus | UVs | wall |\n"
            "|---|---|---|---|---|---|---|---|\n")
    if not os.path.exists(FORGE_LOG):
        with io.open(FORGE_LOG, "w", encoding="utf-8") as fh:
            fh.write(head)
    with io.open(FORGE_LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write_report(report, outdir):
    with io.open(os.path.join(outdir, "forge_report.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)


if __name__ == "__main__":
    sys.exit(main())
