"""THE LIKENESS LOOP. Measure, edit, render, re-measure, correct the gain.

WHAT ONE ITERATION DOES
-----------------------
    1  measure the CURRENT render against the reference  -> per-region delta
    2  for each region outside the deadband, command
           delta_cm / gain,  clamped to max_step_cm
    3  chain those edits into one DNA (geometry only, feathered)
    4  import it through the sanctioned path, preview-assemble, render
    5  re-measure, and CORRECT EACH GAIN from what actually moved
    6  stop when every region is inside the deadband, or when the total
       residual stops improving

WHY THE GAIN IS CORRECTED RATHER THAN ASSUMED
---------------------------------------------
`FitToFaceDna` fits a PARAMETRIC model to the edited geometry, so what the
render does is not what the DNA was told to do. Measured 2026-08-17: a
feathered 2.0 cm chin command produced 2.155 cm of render (gain 1.078), while
the same command through a HARD box produced 1.299 cm (0.650). Attenuation is
a property of (region x mask), so every gain here carries its region's mask
and is re-derived from the render each iteration.

WHAT IT WILL NOT DO
-------------------
It cannot exceed what the MetaHuman face model can express. Ryan's escalation
criterion, ruled 2026-08-17: if a region PLATEAUS -- residual stops improving
while the commanded gain climbs across 2+ iterations -- that region has hit
the model's expressive boundary, and whole-rig import becomes a live option
with evidence in hand. This tool DETECTS and REPORTS a plateau; it does not
act on one.

EXIT CODES
    0  converged, or stopped on a stated criterion
    2  bad arguments, or the manifest lacks fit regions
    3  no editor matched UE_PROJECT_ROOT
    5  a payload error
    6  a capture failed its landmark gate
"""

from __future__ import annotations

import argparse
import copy
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
import capture_landmarks as CL                    # noqa: E402
import use_preview_mesh as UPM                    # noqa: E402
import edit_dna_geometry as EDG                   # noqa: E402
import sanctioned_import as SI                    # noqa: E402


def _stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")


def measure_regions(png, model, fixed_ipd=None):
    """-> dict of region measures from one rendered frame.

    THE RENDER IS MEASURED AT A FIXED SCALE, NOT ITS OWN.
    `CL.canonical` divides by the frame's OWN interpupillary distance, which
    is right for comparing two faces at unknown scale -- the reference photo
    is exactly that case. It is WRONG for the render: the camera is locked
    and the head sits at a fixed distance, so render pixels are already
    absolute at a known cm/px. Dividing by the frame's own IPD made the
    ruler a function of the thing being edited, and every widening edit that
    touched the eye region rescaled every other measure.

    Measured three times before this was believed: eye-band edits drifted IPD
    +2.7%, a region-transform probe drifted it +1.37%, and in both cases
    regions nobody had commanded appeared to move.

    Passing fixed_ipd re-expresses the measures at that scale instead, so the
    only thing that moves a number is the face.
    """
    pts, w, h = CL.detect(png, model)
    c, ipd, roll = CL.canonical(pts)
    checks, fatal, stats = CL.quality(pts, c, w, h, ipd, roll, "fit")
    if fatal:
        raise RuntimeError("; ".join(fatal))
    r = CL.regions(c)
    if fixed_ipd:
        k = ipd / float(fixed_ipd)
        r = {name: v * k for name, v in r.items()}
        stats["scale_factor_vs_fixed"] = round(k, 5)
    return r, stats


def apply_edits(commands, regions, in_dna, work_dir, timeout):
    """Chain one geometry edit per (region, side) into a single DNA.

    Returns (final_dna_path, [applied records]). Ping-pongs between two
    files so a ten-region iteration does not leave ten 54 MB DNAs behind.
    """
    applied = []
    src = in_dna
    ping = os.path.join(work_dir, "fit_a.dna")
    pong = os.path.join(work_dir, "fit_b.dna")
    dst = ping
    for name, cm in commands:
        reg = regions[name]
        axis = reg["axis"]
        sides = [1.0, -1.0] if reg["mirrored"] else [1.0]
        for side in sides:
            bmin = list(reg["box_min"])
            bmax = list(reg["box_max"])
            if reg["mirrored"] and side < 0:
                # The RIGHT box is the left one reflected through X=0. Written
                # out explicitly rather than inferred, and the delta's X flips
                # with it so both sides move OUTWARD.
                bmin, bmax = [-bmax[0], bmin[1], bmin[2]], \
                             [-bmin[0], bmax[1], bmax[2]]
            delta = [axis[0] * cm * side, axis[1] * cm, axis[2] * cm]
            rc, d, _ = ue_exec.run(
                CS._fill(EDG.PAYLOAD, IN_DNA=src, OUT_DNA=dst,
                         MESH=int(reg["mesh"]), BMIN=bmin, BMAX=bmax,
                         DELTA=delta,
                         FEATHER=float(reg["feather_band_cm"])),
                timeout=timeout, stage_name="fit_edit_%s" % name)
            if rc == 3:
                raise SystemExit(3)
            if d is None or d.get("error"):
                raise RuntimeError(
                    "edit %s side %+.0f: %s"
                    % (name, side, (d or {}).get("error", "no result")))
            applied.append({"region": name, "side": side,
                            "delta_cm": [round(v, 4) for v in delta],
                            "weighted": d["selected"], "core": d.get("core")})
            src = dst
            dst = pong if dst is ping else ping
    return src, applied


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=CS.DEFAULT_MANIFEST)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--iterations", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print the commands; edit nothing")
    args = ap.parse_args(argv)

    man = CS.load_manifest(args.manifest)
    fit = man.get("fit")
    # A region marked addressable=False is SKIPPED, not commanded at zero.
    # brow_height and nose_bridge are driven by landmarks inside the eye band
    # that no edit may enter, so commanding them burns two edits an iteration
    # on regions that provably cannot respond -- measured opposite-direction
    # movement on both, 2026-08-18.
    allr = (man.get("geometry_regions") or {})
    regions = {k: v for k, v in allr.items()
               if isinstance(v, dict) and "measure" in v
               and v.get("addressable", True)}
    skipped = [k for k, v in allr.items()
               if isinstance(v, dict) and "measure" in v
               and not v.get("addressable", True)]
    if skipped:
        print("SKIPPED as not addressable: %s" % ", ".join(skipped))
        for k in skipped:
            print("  %s: %s" % (k, allr[k].get("_not_addressable", "")[:140]))
        print()
    if not fit or not regions:
        print("manifest has no fit block or no fit regions")
        return 2

    model = CS.resolve(man, "mediapipe_model")
    out_dir = CS.resolve(man, "renders_dir")
    canonical = CS.resolve(man, "dna_canonical")
    ref_png = os.path.join(REPO_ROOT, fit["reference_image"])
    work = os.path.join(REPO_ROOT, "LandscapeLab", "Saved", "HeroDNA")
    os.makedirs(work, exist_ok=True)
    dead = float(fit["deadband_ipd"])
    max_step = float(fit["max_step_cm"])
    # FAIL CLOSED ON A MISSING FLOOR. Defaulting to a plausible constant is
    # how the loop ran uncalibrated without anyone noticing.
    floor = man["capture"].get("noise_floor")
    if not floor:
        print("REFUSING: no noise_floor in the manifest. Run")
        print("  capture_shot.py --noise-floor --repeats 4 --settle 2")
        print("A default would be a number that LOOKS calibrated.")
        return 2
    cm_per_ipd = floor["scale"]["cm_per_ipd"]

    ref_regions, ref_stats = measure_regions(ref_png, model)
    # The hero's own canonical IPD, frozen once. Everything the RENDER
    # reports is expressed at this scale from here on.
    fixed_ipd = fit.get("fixed_ipd_px")
    if not fixed_ipd:
        print("no fixed_ipd_px in the manifest -- measuring the first frame "
              "to set it")
    print("=" * 74)
    print("LIKENESS LOOP  ->  %s" % fit["reference_image"])
    print("=" * 74)
    print("deadband %.4f IPD (%.3f cm)   max step %.2f cm   scale %.4f cm/IPD"
          % (dead, dead * cm_per_ipd, max_step, cm_per_ipd))
    print()

    history = []
    # The DNA the CURRENT character state came from. Each iteration edits the
    # canonical file by the CUMULATIVE command, rather than stacking edits on
    # an already-edited DNA, so a gain correction re-aims the whole move
    # instead of adding to a wrong one.
    #
    # IT MUST PERSIST ACROSS PROCESSES. Measured 2026-08-18: run as a series
    # of single-iteration calls, a fresh dict reset the cumulative to zero
    # every time, so the loop OSCILLATED between canonical-1.2 and
    # canonical+1.2 on jaw_width instead of converging -- each call
    # "corrected" a state it had not produced. The character's state is a
    # property of the project, not of one python process.
    cumulative = dict(fit.get("cumulative_cm") or {})
    for k in regions:
        cumulative.setdefault(k, 0.0)
    if any(abs(v) > 1e-9 for v in cumulative.values()):
        print("resuming from cumulative: %s"
              % {k: round(v, 3) for k, v in cumulative.items() if abs(v) > 1e-9})
        print()

    fl_p90 = floor["per_landmark"]["p90_ipd"]

    def settled_capture(stage):
        """A CAPTURE IS NOT A MEASUREMENT UNTIL IT REPRODUCES.

        A freshly imported or reloaded character renders a faceted,
        unresolved preview that resolves after further assembles. Measured
        2026-08-17: an unsettled frame read 7.5x the noise floor away from
        the settled one, which here showed up as iteration 1 measuring
        4.228 cm where the same state settled reads 3.072. sanctioned_import
        already had this guard; this loop did not, which is the guard
        existing and not covering the place the defect appeared.
        """
        prev = None
        for attempt in range(4):
            if attempt:
                UPM.point_stage(args.character, True, args.timeout)
            p2, _ = CS.shoot(man, "%s%s" % (stage, "" if not attempt
                                            else "_r%d" % attempt),
                             out_dir, args.timeout)
            pts, w, h = CL.detect(p2, model)
            c, ipd, roll = CL.canonical(pts)
            if prev is not None:
                dl = CS._delta(prev, c)
                r = dl["p90_ipd"] / fl_p90 if fl_p90 else 99.0
                print("    settle %d: %.2fx floor" % (attempt, r))
                if r <= 2.0:
                    return p2
            prev = c
        raise RuntimeError(
            "%s never settled: two consecutive renders of an unchanged "
            "character never agreed inside the floor" % stage)

    for it in range(1, args.iterations + 1):
        UPM.point_stage(args.character, True, args.timeout)
        try:
            png = settled_capture("fit_i%d" % it)
            cur, stats = measure_regions(png, model, fixed_ipd)
            if not fixed_ipd:
                fixed_ipd = stats["ipd_px"]
                fit["fixed_ipd_px"] = round(fixed_ipd, 3)
                print("  fixed_ipd_px set to %.3f from this frame"
                      % fixed_ipd)
                cur, stats = measure_regions(png, model, fixed_ipd)
        except (LookupError, RuntimeError) as exc:
            print("iteration %d: the render did not measure -- %s" % (it, exc))
            return 6

        rows = []
        total = 0.0
        for name, reg in regions.items():
            key = reg["measure"]
            d = ref_regions[key] - cur[key]
            rows.append((name, ref_regions[key], cur[key], d))
            total += abs(d)

        print("ITERATION %d   %s" % (it, os.path.basename(png)))
        print("  %-14s %9s %9s %9s %9s"
              % ("region", "target", "current", "delta", "cm"))
        for name, r, c, d in rows:
            flag = "" if abs(d) > dead else "   (deadband)"
            print("  %-14s %+9.4f %+9.4f %+9.4f %+9.3f%s"
                  % (name, r, c, d, d * cm_per_ipd, flag))
        print("  TOTAL |delta| %.4f IPD = %.3f cm"
              % (total, total * cm_per_ipd))

        history.append({"iteration": it, "png": os.path.basename(png),
                        "total_abs_delta_ipd": round(total, 5),
                        "ipd_px": round(stats["ipd_px"], 3),
                        "regions": {n: round(d, 5) for n, _, _, d in rows}})

        # THE RULER MUST NOT MOVE. The frame is iris-centred and IPD-scaled,
        # so if an edit reaches the eyes the normaliser changes and every
        # region's number becomes a statement about the ruler. Measured
        # 2026-08-17: IPD went 425.04 -> 436.35 px (+2.7%) in one iteration,
        # the residual went BACKWARDS, and two regions appeared to move
        # against their commands. Refuse rather than iterate on it.
        if len(history) > 1:
            prev_ipd = history[-2]["ipd_px"]
            drift = abs(stats["ipd_px"] - prev_ipd) / max(prev_ipd, 1e-6)
            cap = float(fit.get("max_ipd_drift_frac", 0.015))
            print("  IPD %.2f px (was %.2f, drift %+.2f%%)"
                  % (stats["ipd_px"], prev_ipd, drift * 100.0))
            if drift > cap:
                print()
                print("*** THE MEASUREMENT FRAME MOVED — STOPPING ***")
                print("IPD drifted %.2f%% against a %.2f%% cap. An edit has"
                      % (drift * 100.0, cap * 100.0))
                print("reached the eye region, so every number this iteration")
                print("is about the normaliser and not about the face. No")
                print("region box may enter Y 164.5..169.5 including feather.")
                break

        if all(abs(d) <= dead for _, _, _, d in rows):
            print()
            print("CONVERGED — every region inside the deadband.")
            break

        # --- gain correction, from what the previous command actually did ---
        # THE PREVIOUS ITERATION MAY BE IN A PREVIOUS PROCESS. Measured
        # 2026-08-18: run as single-iteration calls, `it > 1` never fired, so
        # the gain never corrected and the loop clamped at +/-max_step
        # forever. The last iteration is persisted in the manifest for
        # exactly this.
        prev = None
        if it > 1:
            prev = history[-2]
        elif fit.get("iterations_run"):
            prev = fit["iterations_run"][-1]
            if prev.get("commands"):
                print("  (gain correction against the PREVIOUS RUN's "
                      "iteration, from the manifest)")
            else:
                prev = None
        if prev is not None:
            print()
            print("  gain correction (observed / commanded):")
            for name, reg in regions.items():
                cmd = prev.get("commands", {}).get(name)
                if not cmd:
                    continue
                if name not in prev.get("regions", {}):
                    continue
                moved = (prev["regions"][name] - history[-1]["regions"][name])
                moved_cm = moved * cm_per_ipd
                if abs(cmd) < 1e-6:
                    continue
                # A GAIN FROM A MOVE BELOW THE NOISE FLOOR IS NOISE.
                # Measured 2026-08-18: chin_height "moved" +0.029 cm for a
                # +0.324 cm command -- under the 0.078 cm floor -- which gave
                # ratio 0.09 and drove the gain to its 0.15 clamp, so the
                # next command clamped at max_step in the wrong direction.
                # Hold the gain instead; the region is already near target,
                # which is exactly when small commands happen.
                floor_cm = fl_p90 * cm_per_ipd
                if abs(cmd) < 2.0 * floor_cm or abs(moved_cm) < floor_cm:
                    print("    %-14s commanded %+.3f cm, render moved %+.3f "
                          "-> BELOW THE FLOOR (%.3f cm), gain held at %.3f"
                          % (name, cmd, moved_cm, floor_cm, reg["gain"]))
                    continue
                obs = moved_cm / cmd
                if obs <= 0.05:
                    print("    %-14s commanded %+.3f cm, render moved %+.3f "
                          "-> NO RESPONSE, gain held at %.3f"
                          % (name, cmd, moved_cm, reg["gain"]))
                    continue
                # GAIN IS THE RESPONSE ITSELF, not the old gain divided by
                # it. command = want / gain, and moved = R * command, so
                # moved == want exactly when gain == R. `obs` IS R.
                # The inverted form (gain / obs) SHRINKS the gain when the
                # render over-moves, which makes the next command larger and
                # the loop oscillate: measured 2026-08-18, jaw_width swung
                # between cumulative 0.0 and +1.2 while its gain slid
                # 0.448 -> 0.392 -> 0.293 and every step clamped at max_step.
                # DAMPED. A single-iteration gain estimate is noisy -- the
                # response is non-linear and the render carries a floor -- so
                # adopting it outright makes the loop over-steer and ring.
                # Measured 2026-08-18 at fixed scale: undamped, the residual
                # cycled 0.799 -> 2.001 -> 1.127 -> 0.828 instead of settling.
                # The geometric mean moves toward the new estimate without
                # betting the next command on one measurement.
                raw = max(0.15, min(6.0, obs))
                new = max(0.15, min(6.0, (reg["gain"] * raw) ** 0.5))
                print("    %-14s commanded %+.3f cm, render moved %+.3f "
                      "-> ratio %.3f, gain %.3f -> %.3f"
                      % (name, cmd, moved_cm, obs, reg["gain"], new))
                reg["gain"] = round(new, 4)

        commands = []
        cmd_log = {}
        for name, r, c, d in rows:
            if abs(d) <= dead:
                continue
            reg = regions[name]
            want_cm = d * cm_per_ipd
            step = want_cm / max(reg["gain"], 1e-3)
            # Take smaller steps as the region closes, so the last approach
            # is not a full-size jump across the target.
            near = min(1.0, abs(d) / (4.0 * dead))
            cap = max_step * max(0.25, near)
            step = max(-cap, min(cap, step))

            # A COMMAND TOO SMALL TO MEASURE TEACHES NOTHING, AND LOCKS THE
            # GAIN THAT PRODUCED IT. Measured 2026-08-19: temple_width and
            # cheek_width reached gains of 5.6 and 5.1, which make the
            # command about a fifth of the wanted move. That command lands
            # below the noise floor, the sub-floor guard then HOLDS the gain
            # rather than learning from noise, and the region can never
            # recalibrate -- it drifts at a constant offset forever
            # (temple_width sat at +0.024..+0.039 IPD for eight iterations).
            #
            # The guard against learning from noise had become a trap that
            # prevented learning at all. If a region is outside the deadband
            # it gets a command big enough to SEE, even if the gain says
            # smaller -- that is what makes the next gain estimate real.
            floor_cm = fl_p90 * cm_per_ipd
            min_cmd = 2.0 * floor_cm
            if abs(step) < min_cmd:
                step = min_cmd if step >= 0 else -min_cmd
            cumulative[name] += step
            commands.append((name, cumulative[name]))
            cmd_log[name] = round(step, 4)
        history[-1]["commands"] = cmd_log

        print()
        print("  commanding (cumulative from canonical):")
        for name, cm in commands:
            print("    %-14s %+7.3f cm  (this step %+.3f, gain %.3f%s)"
                  % (name, cm, cmd_log[name], regions[name]["gain"],
                     ", MIRRORED" if regions[name]["mirrored"] else ""))

        if args.dry_run:
            print()
            print("--dry-run: nothing edited.")
            break

        final_dna, applied = apply_edits(commands, regions, canonical, work,
                                         args.timeout)
        print("  edits applied: %d" % len(applied))

        SI._run(SI.RESTORE_PAYLOAD, args.timeout, "fit_restore",
                CHARACTER=args.character)
        d = SI._run(SI.IMPORT_PAYLOAD, args.timeout, "fit_import",
                    CHARACTER=args.character,
                    MASTER="/Game/Hero/MHC_AlpineHero_Master",
                    DNA=final_dna, WHOLE_RIG=False)
        if not d["import_success"]:
            print("  IMPORT FAILED: %s" % d.get("import_code"))
            return 5
        print("  imported %s" % d["import_code"])
        print()

    # --- persist ---------------------------------------------------------
    man["geometry_regions"].update(regions)
    man["fit"]["cumulative_cm"] = {k: round(v, 4)
                                   for k, v in cumulative.items()}
    # APPEND, DO NOT OVERWRITE. Measured 2026-08-18: run as single-iteration
    # processes, each run replaced the history with its own one entry, so the
    # cumulative that produced the BEST residual of the session was lost and
    # could not be returned to. A record that only holds the last attempt
    # cannot answer "which state was best".
    prior = list(fit.get("iterations_run") or [])
    for h in history:
        h["cumulative_cm"] = {k: round(v, 4) for k, v in cumulative.items()}
    man["fit"]["iterations_run"] = (prior + history)[-40:]
    man["fit"]["last_run_utc"] = _stamp()
    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2)
        fh.write("\n")

    out = os.path.join(out_dir, "fit_history.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"reference": fit["reference_image"],
                   "reference_regions": ref_regions,
                   "history": history}, fh, indent=2)
        fh.write("\n")
    print("history -> %s" % os.path.relpath(out, REPO_ROOT))

    if len(history) >= 3:
        t = [h["total_abs_delta_ipd"] for h in history]
        if t[-1] >= t[-2] >= t[-3]:
            print()
            print("PLATEAU: total residual has not improved across three")
            print("iterations (%.4f -> %.4f -> %.4f). Ryan's escalation")
            print("criterion is met; whole-rig import is a live option, with")
            print("evidence. NOT acted on here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
