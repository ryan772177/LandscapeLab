"""THE MEASURING INSTRUMENT. One capture, at the transform the manifest
locked, with nothing derived from the subject.

WHY THIS EXISTS SEPARATELY FROM build_capture_stage.py
------------------------------------------------------
The stage builder SEARCHES for the framing, so its payload derives the
camera from `get_actor_bounds`. That is correct once and catastrophic
afterwards: a joint edit changes the head's bounds, the camera moves, and
CAMERA MOVEMENT IS INDISTINGUISHABLE FROM JOINT MOVEMENT in the render.
Every comparison after framing therefore sets the transform ABSOLUTELY
from the manifest and reads it back, and this file is the only thing that
takes a picture of the hero from here on -- baseline, moved, restore and
every iteration render use it, so they cannot drift apart
(non-negotiable 24: two lists that must agree are one list, badly stored).

WHAT IS RE-ASSERTED ON EVERY SHOT, AND WHY EACH ONE
---------------------------------------------------
    camera transform      set absolutely, READ BACK, refuse on mismatch
    fov / resolution      compared against the manifest, refuse on mismatch
    exposure              AEM_MANUAL from the manifest; auto-exposure would
                          make the frame a function of the previous frame
    capture_every_frame   asserted FALSE -- a free-running capture has no
                          defined moment and cannot be compared
    persist_rendering_state  TRUE. Without it every capture_scene() starts
                          with no rendering history and the face's virtual
                          textures never leave their white fallback:
                          measured mean 254.85 / nonwhite 0.027 without,
                          161.90 / 1.000 with, converged by 10 frames.
    three-point rig       re-aimed relative to the LOCKED azimuth and its
                          intensity read back. A directional light's
                          rotation is the direction light TRAVELS
                          (DirectionalLightComponent.cpp:1509 -- units are
                          Unitless /* Lux */, which is why ELightUnits has
                          no LUX member and setting it raises).
    grooms                hidden. A hairline over the brow poisons brow
                          landmarks, and brow_height is a fitted region.

THE NOISE FLOOR
---------------
`--noise-floor` takes N captures of the UNCHANGED character seconds apart
and measures how far the landmarks move anyway. That number is what any
later "the joint moved" claim has to beat. It is written into the manifest
so a future session cannot quote a delta without it.

It SETTLES first, and it REFUSES a non-homogeneous run. A cold session has
not converged after one shot's warm-up: measured 2026-08-17, the first floor
taken after a stage build split into two clusters -- p90 0.0722 across them
against 0.0032 within, a 22.6x spread -- and an immediate re-run gave 0.0078
across all six pairs, a 2.18x spread. A spread like that is a STEP, not
noise: something changed mid-run, and the worst pair would be measuring that
change rather than the instrument. So `--settle` throws shots away first and
a pair-spread ratio above 4 writes no floor at all.

EXIT CODES
    0  captured, gate passed
    2  bad arguments / manifest missing the capture block
    3  no editor matched UE_PROJECT_ROOT (standing rule 7)
    5  payload error, or a read-back disagreed with the manifest
    6  the frame was captured but the landmark gate refused it
    7  the noise-floor shots were not homogeneous -- a step, not noise, so
       NO FLOOR WAS WRITTEN rather than a wrong one
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from scripts import ue_exec                      # noqa: E402
import capture_landmarks as CL                   # noqa: E402

DEFAULT_MANIFEST = os.path.join(_HERE, "manifest.json")


SHOOT_LOCKED = r'''
import json as _json
import unreal as _u

LOC      = __LOC__
ROT      = __ROT__
AZ_DEG   = __AZ__
FOV      = __FOV__
RES      = __RES__
EXPOSURE = __EXPOSURE__
WARM     = __WARM__
OUT_DIR  = r"__OUT_DIR__"
OUT_NAME = "__OUT_NAME__"

_out = {"ok": False, "error": None, "camera": {}, "lights": [],
        "hidden": [], "png": None, "cvars": [], "refusals": []}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()

    _subj = _cap = None
    _lights = {}
    for _a in _eas.get_all_level_actors():
        _l = _a.get_actor_label()
        if _l == "HeroStage_Subject":
            _subj = _a
        elif _l == "HeroStage_Camera":
            _cap = _a
        elif _l in ("HeroStage_Key", "HeroStage_Fill", "HeroStage_Rim"):
            _lights[_l] = _a
    if _subj is None or _cap is None:
        raise RuntimeError("stage actors missing; run build_capture_stage.py")

    # GROOMS OFF -- re-asserted, not assumed. Anything re-imported since the
    # stage was built comes back visible.
    for _c in _subj.get_components_by_class(_u.PrimitiveComponent):
        _cn = _c.get_class().get_name()
        if "Groom" in _cn or "Hair" in _cn:
            try:
                _c.set_editor_property("visible", False)
                _out["hidden"].append(_cn)
            except Exception:
                pass

    # THE TRANSFORM IS SET, NEVER DERIVED. Nothing here reads the subject's
    # bounds, so a face that changes shape cannot move the camera.
    _loc = _u.Vector(LOC[0], LOC[1], LOC[2])
    # ROT IS [pitch, yaw, roll]; unreal.Rotator TAKES (roll, pitch, yaw).
    # PythonStub:66750. Passing them positionally in reading order put -90
    # of pitch into roll, and the read-back below is what caught it.
    _rot = _u.Rotator(ROT[2], ROT[0], ROT[1])
    _cap.set_actor_location(_loc, False, False)
    _cap.set_actor_rotation(_rot, False)
    _rl = _cap.get_actor_location()
    _rr = _cap.get_actor_rotation()
    for _nm, _got, _want in (("loc.x", _rl.x, LOC[0]), ("loc.y", _rl.y, LOC[1]),
                             ("loc.z", _rl.z, LOC[2]),
                             ("rot.pitch", _rr.pitch, ROT[0]),
                             ("rot.yaw", _rr.yaw, ROT[1]),
                             ("rot.roll", _rr.roll, ROT[2])):
        if abs(float(_got) - float(_want)) > 1e-3:
            _out["refusals"].append(
                "camera %s read back %.6f, manifest says %.6f"
                % (_nm, _got, _want))

    # The rig follows the LOCKED azimuth, so it is the same light on every
    # shot of the series.
    for _nm, _off, _pitch in (("HeroStage_Key",  -30.0, -22.0),
                              ("HeroStage_Fill",  45.0, -8.0),
                              ("HeroStage_Rim",  180.0, -5.0)):
        _la = _lights.get(_nm)
        if _la is None:
            _out["refusals"].append("light %s MISSING from the stage" % _nm)
            continue
        _yaw = (AZ_DEG + _off + 180.0) % 360.0
        _la.set_actor_rotation(_u.Rotator(0.0, _pitch, _yaw), False)
        _lc = _la.get_component_by_class(_u.LightComponent)
        _out["lights"].append(
            {"name": _nm, "yaw": _yaw, "pitch": _pitch,
             "intensity": _lc.get_editor_property("intensity"),
             "comes_from_az": AZ_DEG + _off})

    _cc = _cap.get_component_by_class(_u.SceneCaptureComponent2D)
    _rt = _cc.get_editor_property("texture_target")

    if bool(_cc.get_editor_property("capture_every_frame")):
        _cc.set_editor_property("capture_every_frame", False)
        _out["refusals"].append(
            "capture_every_frame was TRUE -- a free-running capture has no "
            "defined moment; set False, re-run for a clean shot")
    _cc.set_editor_property("always_persist_rendering_state", True)

    _fov_got = float(_cc.get_editor_property("fov_angle"))
    if abs(_fov_got - float(FOV)) > 1e-3:
        _out["refusals"].append("fov_angle %.4f, manifest says %.4f"
                                % (_fov_got, FOV))
    _rx = int(_rt.get_editor_property("size_x"))
    _ry = int(_rt.get_editor_property("size_y"))
    if (_rx, _ry) != (int(RES[0]), int(RES[1])):
        _out["refusals"].append("render target %dx%d, manifest says %dx%d"
                                % (_rx, _ry, RES[0], RES[1]))

    # FIXED EXPOSURE, re-asserted from the manifest every shot. Auto exposure
    # makes each frame a function of the one before it, which is the one
    # thing a comparison instrument may not be.
    _pp = _u.PostProcessSettings()
    for _k, _v in (("auto_exposure_method", _u.AutoExposureMethod.AEM_MANUAL),
                   ("auto_exposure_bias", float(EXPOSURE)),
                   ("auto_exposure_min_brightness", 1.0),
                   ("auto_exposure_max_brightness", 1.0),
                   ("motion_blur_amount", 0.0)):
        _pp.set_editor_property(_k, _v)
        _pp.set_editor_property("override_" + _k, True)
    _cc.set_editor_property("post_process_settings", _pp)
    _cc.set_editor_property("post_process_blend_weight", 1.0)

    for _cv in ("r.Streaming.FullyLoadUsedTextures 1",
                "r.VT.MaxUploadsPerFrame 512",
                "r.VT.MaxContinuousUpdatesPerFrame 512"):
        try:
            _u.SystemLibrary.execute_console_command(_w, _cv)
            _out["cvars"].append(_cv)
        except Exception as _e2:
            _out["cvars"].append("%s FAILED %s" % (_cv, str(_e2)[:60]))

    for _i in range(WARM):
        _cc.capture_scene()
    _cc.capture_scene()

    _u.RenderingLibrary.export_render_target(_w, _rt, OUT_DIR, OUT_NAME)

    _out["png"] = OUT_DIR + "\\" + OUT_NAME
    _out["camera"] = {
        "location": [_rl.x, _rl.y, _rl.z],
        "rotation": [_rr.pitch, _rr.yaw, _rr.roll],
        "fov_angle": _fov_got,
        "resolution": [_rx, _ry],
        "exposure_bias": float(EXPOSURE),
        "warmup_frames": WARM,
        "capture_every_frame": bool(
            _cc.get_editor_property("capture_every_frame")),
        "persist_rendering_state": bool(
            _cc.get_editor_property("always_persist_rendering_state")),
    }
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out, default=str))
'''


def _fill(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace("__%s__" % k, v if isinstance(v, str) else repr(v))
    return tpl


def _stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as fh:
        man = json.load(fh)
    cap = man.get("capture")
    if not cap or not cap.get("camera"):
        raise SystemExit(
            "manifest has no locked capture transform -- run "
            "build_capture_stage.py first; the framing is searched once, "
            "then never re-derived")
    return man


def resolve(man, key):
    p = man["paths"][key]
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


def shoot(man, stage, out_dir, timeout=25.0, name=None):
    """One capture at the locked transform. -> (png_path, payload_dict)."""
    cap = man["capture"]
    cam = cap["camera"]
    name = name or "%s_%s.png" % (stage, _stamp())
    rc, d, _ = ue_exec.run(
        _fill(SHOOT_LOCKED,
              LOC=[float(v) for v in cam["location"]],
              ROT=[float(v) for v in cam["rotation"]],
              AZ=float(cap["azimuth_deg"]),
              FOV=float(cap["fov_angle_deg"]),
              RES=[int(v) for v in cap["resolution"]],
              EXPOSURE=float(cap["exposure_bias"]),
              WARM=int(cap["warmup_frames"]),
              OUT_DIR=out_dir.replace("\\", "\\\\"),
              OUT_NAME=name),
        timeout=timeout, stage_name="hero_shot_" + stage)
    if rc == 3:
        raise SystemExit(3)
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        raise SystemExit(5)
    if d.get("refusals"):
        print("*** THE INSTRUMENT DISAGREED WITH THE MANIFEST ***")
        for r in d["refusals"]:
            print("  - %s" % r)
        raise SystemExit(5)
    png = os.path.join(out_dir, name)
    if not os.path.isfile(png):
        print("payload reported success and no PNG exists: %s" % png)
        raise SystemExit(5)
    return png, d


def measure(png, model):
    """-> (canonical_points, stats, fatal). Raises LookupError if no face."""
    pts, w, h = CL.detect(png, model)
    c, ipd, roll = CL.canonical(pts)
    checks, fatal, stats = CL.quality(pts, c, w, h, ipd, roll, "capture")
    return c, stats, fatal


def _delta(ca, cb):
    """Per-landmark Euclidean movement, in INTERPUPILLARY UNITS."""
    n = min(len(ca), len(cb))
    d = [math.hypot(ca[i][0] - cb[i][0], ca[i][1] - cb[i][1])
         for i in range(n)]
    d.sort()
    return {
        "landmarks": n,
        "p50_ipd": d[n // 2],
        "p90_ipd": d[int(n * 0.9)],
        "max_ipd": d[-1],
        "mean_ipd": statistics.fmean(d),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--stage", default=None,
                    help="name for this shot, e.g. baseline / moved / restore")
    ap.add_argument("--noise-floor", action="store_true",
                    help="N shots of the UNCHANGED character; write the "
                         "floor any later claim has to beat")
    ap.add_argument("--cycle-assemble", default=None, metavar="CHARACTER",
                    help="run assemble_for_preview + re-point the stage "
                         "BETWEEN measured shots. Use whenever the arms being "
                         "compared do that, because a floor must contain "
                         "every operation the comparison contains -- "
                         "otherwise a preview assemble's own variation is "
                         "scored as a face change")
    ap.add_argument("--settle", type=int, default=2,
                    help="throwaway captures before measuring. A COLD "
                         "session has not converged after one shot's warm-up: "
                         "measured 2026-08-17, the first floor after a stage "
                         "build split into two clusters with p90 0.0722 "
                         "across them and 0.0032 within, and re-running "
                         "immediately gave 0.0078 across all six pairs")
    ap.add_argument("--repeats", type=int, default=3,
                    help="shots for the noise floor; every pair is compared "
                         "and the worst adopted (default 3)")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    if not args.stage and not args.noise_floor:
        ap.error("give --stage NAME or --noise-floor")

    man = load_manifest(args.manifest)
    model = resolve(man, "mediapipe_model")
    out_dir = resolve(man, "renders_dir")
    os.makedirs(out_dir, exist_ok=True)

    if args.noise_floor:
        print("=" * 72)
        print("NOISE FLOOR — %d captures, NOTHING CHANGED BETWEEN THEM"
              % args.repeats)
        print("=" * 72)
        print("Anything this pipeline later calls 'the joint moved' has to")
        print("beat this number, or it is the instrument talking.")
        print()
        # n=2 IS NOT A FLOOR. Two runs of this very test gave p90 0.00240 and
        # 0.00374 -- the floor moves 1.5x between measurements, which is this
        # project's recorded finding about noise floors at small n. Take
        # several shots, compare EVERY pair, and adopt the WORST as the bar.
        for i in range(args.settle):
            shoot(man, "settle_%d" % i, out_dir, args.timeout)
        if args.settle:
            print("  settled with %d throwaway capture(s)" % args.settle)

        cycle = None
        if args.cycle_assemble:
            import use_preview_mesh as UPM
            cycle = args.cycle_assemble
            print("  cycling assemble_for_preview between shots on %s"
                  % cycle)

        shots = []
        tags = ["noise_%s" % chr(ord("a") + i) for i in range(args.repeats)]
        for idx, tag in enumerate(tags):
            if cycle is not None and idx > 0:
                UPM.point_stage(cycle, True, args.timeout)
            png, d = shoot(man, tag, out_dir, args.timeout)
            try:
                c, st, fatal = measure(png, model)
            except LookupError:
                print("%s: NO FACE DETECTED in %s" % (tag, png))
                return 6
            if fatal:
                print("%s: gate refused -- %s" % (tag, "; ".join(fatal)))
                return 6
            print("  %-8s %s" % (tag, os.path.basename(png)))
            print("           ipd %.3f px   roll %+.3f deg   yaw %.4f"
                  % (st["ipd_px"], st["roll_deg"], st["yaw_frac"]))
            shots.append((c, st))

        pairs = []
        for i in range(len(shots)):
            for j in range(i + 1, len(shots)):
                pairs.append(((tags[i], tags[j]),
                              _delta(shots[i][0], shots[j][0])))
        print()
        print("  every pair, per-landmark movement in interpupillary units")
        for (ta, tb), pd in pairs:
            print("    %-8s vs %-8s  p50 %.5f  p90 %.5f  max %.5f"
                  % (ta[6:], tb[6:], pd["p50_ipd"], pd["p90_ipd"],
                     pd["max_ipd"]))
        # THE BAR IS THE WORST PAIR, not the average of them. A floor that
        # averages away its own bad case is a floor a real delta can hide
        # under.
        # HOMOGENEITY, AND IT FAILS CLOSED. If the shots split into
        # clusters the spread is not noise, it is a STEP -- something changed
        # mid-run and the worst pair measures that change, not the
        # instrument. Measured 2026-08-17: an unsettled cold session gave
        # 0.0722 across clusters against 0.0032 within, a ratio of 22.6,
        # where a settled run gives 2.18. The bar is 4.
        _p90s = [p["p90_ipd"] for _, p in pairs]
        _ratio = (max(_p90s) / min(_p90s)) if min(_p90s) > 0 else float("inf")
        print("  pair spread ratio %.2f (worst/best p90)" % _ratio)
        if _ratio > 4.0:
            print()
            print("*** THE SHOTS ARE NOT HOMOGENEOUS — NO FLOOR WRITTEN ***")
            print("A %.1fx spread between pairs is a STEP, not noise: the"
                  % _ratio)
            print("instrument changed mid-run. Most likely the renderer had")
            print("not converged. Re-run; raise --settle if it persists.")
            return 7

        dl = max((p for _, p in pairs), key=lambda p: p["p90_ipd"])
        a = shots[0][1]
        b = shots[-1][1]

        # A FLOOR IN IPD UNITS CANNOT BE COMPARED WITH A MOVE IN CENTIMETRES,
        # and the axis test's move is specified in cm. Pinhole model off the
        # locked camera: the numbers are the manifest's own, not measured on
        # the head, so the irises sitting nearer than the orbit centre makes
        # this an APPROXIMATION -- good to a few percent, which is plenty
        # against a floor three orders of magnitude below the move.
        cam = man["capture"]["camera"]
        dist = float(cam["distance_cm"])
        resx = float(man["capture"]["resolution"][0])
        cm_per_px = 2.0 * dist * math.tan(
            math.radians(float(man["capture"]["fov_angle_deg"])) / 2.0) / resx
        ipd_mean = (a["ipd_px"] + b["ipd_px"]) / 2.0
        cm_per_ipd = ipd_mean * cm_per_px
        print()
        print("  scale (pinhole, APPROXIMATE): %.5f cm/px, IPD %.2f px "
              "= %.3f cm" % (cm_per_px, ipd_mean, cm_per_ipd))
        print("    so the floor is p90 %.4f cm, max %.4f cm"
              % (dl["p90_ipd"] * cm_per_ipd, dl["max_ipd"] * cm_per_ipd))
        print()
        print("  per-landmark movement, in interpupillary units")
        print("    p50 %.5f   p90 %.5f   max %.5f   mean %.5f"
              % (dl["p50_ipd"], dl["p90_ipd"], dl["max_ipd"], dl["mean_ipd"]))
        print("  summary drift")
        print("    ipd   %+.4f px" % (b["ipd_px"] - a["ipd_px"]))
        print("    roll  %+.4f deg" % (b["roll_deg"] - a["roll_deg"]))
        print("    yaw   %+.5f" % (b["yaw_frac"] - a["yaw_frac"]))

        man["capture"]["noise_floor"] = {
            "_what": "Two captures of the UNCHANGED character. This is what "
                     "the instrument does on its own; a later delta smaller "
                     "than p90 is NOT evidence that a joint moved.",
            "_units": "Per-landmark Euclidean movement in interpupillary "
                      "units — the same frame capture_landmarks measures in, "
                      "so a delta and the floor are directly comparable.",
            "_bar_is_the_worst_pair": "Every pair of shots was compared and "
                                      "the WORST p90 adopted. Averaging the "
                                      "pairs would hide the bad case a real "
                                      "delta could then sit under.",
            "measured_utc": _stamp(),
            "shots": tags,
            "all_pairs": [{"a": ta, "b": tb,
                           "p50_ipd": round(pd["p50_ipd"], 6),
                           "p90_ipd": round(pd["p90_ipd"], 6),
                           "max_ipd": round(pd["max_ipd"], 6)}
                          for (ta, tb), pd in pairs],
            "per_landmark": {k: round(v, 6) if isinstance(v, float) else v
                             for k, v in dl.items()},
            "scale": {
                "_how": "Pinhole off the LOCKED camera: cm/px = 2*d*tan(fov/2)"
                        "/res_x, then x IPD in px. APPROXIMATE — the irises "
                        "sit nearer than the orbit centre the distance is "
                        "measured to.",
                "cm_per_px": round(cm_per_px, 6),
                "ipd_px": round(ipd_mean, 3),
                "cm_per_ipd": round(cm_per_ipd, 4),
            },
            "floor_cm": {
                "p50": round(dl["p50_ipd"] * cm_per_ipd, 5),
                "p90": round(dl["p90_ipd"] * cm_per_ipd, 5),
                "max": round(dl["max_ipd"] * cm_per_ipd, 5),
            },
            "summary_drift": {
                "ipd_px": round(b["ipd_px"] - a["ipd_px"], 5),
                "roll_deg": round(b["roll_deg"] - a["roll_deg"], 5),
                "yaw_frac": round(b["yaw_frac"] - a["yaw_frac"], 6),
            },
        }
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=2)
            fh.write("\n")
        print()
        print("written to %s" % os.path.relpath(args.manifest, REPO_ROOT))
        return 0

    png, d = shoot(man, args.stage, out_dir, args.timeout)
    print("captured %s" % os.path.relpath(png, REPO_ROOT))
    cam = d["camera"]
    print("  loc %s  rot %s  fov %.2f  %dx%d  bias %+.2f  warm %d"
          % ([round(v, 4) for v in cam["location"]],
             [round(v, 4) for v in cam["rotation"]], cam["fov_angle"],
             cam["resolution"][0], cam["resolution"][1],
             cam["exposure_bias"], cam["warmup_frames"]))
    print("  lights %s" % ", ".join(
        "%s@%.0f" % (l["name"].replace("HeroStage_", ""), l["intensity"])
        for l in d["lights"]))
    try:
        c, st, fatal = measure(png, model)
    except LookupError:
        print("  GATE: NO FACE DETECTED")
        return 6
    if fatal:
        print("  GATE REFUSED: %s" % "; ".join(fatal))
        return 6
    print("  gate PASS   ipd %.3f px   roll %+.3f   yaw %.4f   asym %.4f"
          % (st["ipd_px"], st["roll_deg"], st["yaw_frac"],
             st["worst_asymmetry"]))
    floor = man["capture"].get("noise_floor")
    if floor:
        print("  noise floor p90 %.5f ipd  (measured %s)"
              % (floor["per_landmark"]["p90_ipd"], floor["measured_utc"]))
    else:
        print("  NO NOISE FLOOR RECORDED — run --noise-floor before any")
        print("  delta from this shot is quoted as evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
