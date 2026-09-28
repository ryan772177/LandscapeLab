"""build_capture_stage.py — the measuring instrument. Framed ONCE, then locked.

WHY THIS EXISTS
    Hand screenshots are rejected as an instrument: framing drift between
    shots is indistinguishable from joint movement, which is the signal
    under measurement. Offline rasterisation is rejected too -- it renders
    exported geometry, not the assembled character, and neutral-joint edits
    only become visible through engine skinning. The camera must observe
    the target.

THE SUBJECT IS THE FACE SKELETAL MESH
    It is what BOTH update routes write: import_from_face_dna -> Assemble
    -> this mesh, and USkelMeshDNAUtils::UpdateJoints -> this mesh
    directly. Choosing it means the stage stays valid whichever route Task
    2 takes.

WHY NO DEDICATED CAPTURE LEVEL, AND IT IS NOT LAZINESS
    A payload that calls load_level or new_level FATALS THE EDITOR --
    EditorServer.cpp:1951 "World Memory Leaks": the teardown asserts that
    nothing references the outgoing world, and the executing Python frame
    IS a reference. This project root-caused that crash twice and put the
    only safe route behind scripts/open_level.py, which scrubs those
    references first. open_level takes a RECIPE, and a capture stage is not
    a biome, so the sanctioned route does not reach here.

    So the stage is built in whatever level is already open, and the
    subject is lifted high above the terrain against empty sky -- the same
    trick this project used to photograph a TRELLIS head. Nothing is saved,
    every actor is labelled HeroStage_*, and a rebuild destroys the
    previous set rather than accumulating.

    Determinism, not studio aesthetics, is the requirement -- and the
    noise-floor test measures whether it was achieved rather than assuming.

THE FACING IS SEARCHED, NOT ASSUMED
    Which way a MetaHuman Face mesh points in its own space is a property
    of the asset. This orbits the head, captures at each azimuth, and picks
    the one whose landmarks pass the frontal gate -- the same discipline
    that settled the TRELLIS mesh's facing by measurement. Afterwards the
    gate is passed BY CONSTRUCTION for every capture.

FIXED EXPOSURE, AND WHY BOTH DEFENCES GO IN
    Ryan's hypothesis for this project's historical pure-white renders is
    auto-exposure with no adaptation history. The RECORDED cause is
    different and was measured: the preview mesh is ~0.12 units tall with
    components pinned at the world origin, so it sat inside the near clip
    plane. Both defences are cheap, so both are here -- AEM_MANUAL with a
    fixed bias, and a camera distance derived from the subject's MEASURED
    bounds rather than guessed.

Exit codes:
    0  stage built, framing found, manifest updated
    2  bad arguments / no Face mesh / manifest unwritable
    3  rule 7: no verified editor node
    4  no azimuth produced a face the gate accepts -- reported, not fudged
    5  the editor payload failed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import ue_exec  # noqa: E402

sys.path.insert(0, HERE)
import capture_landmarks as CL  # noqa: E402

DEFAULT_MANIFEST = os.path.join(HERE, "manifest.json")

BUILD = r'''
import json as _json
import unreal as _u

FACE_MESH = "__FACE_MESH__"
RES       = __RES__
FOV       = __FOV__
EXPOSURE  = __EXPOSURE__
STAGE_Z   = __STAGE_Z__

_out = {"ok": False, "error": None, "level": None, "subject": {},
        "actors": [], "notes": [], "destroyed": 0}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level"] = _w.get_path_name()

    # NO load_level / new_level here, deliberately. See this file's header:
    # a world switch from inside a payload fatals the editor and the only
    # safe route is scripts/open_level.py, which does not take a raw path.

    # Idempotent: a rebuild replaces the stage rather than stacking one.
    for _a in list(_eas.get_all_level_actors()):
        if _a.get_actor_label().startswith("HeroStage_"):
            _eas.destroy_actor(_a)
            _out["destroyed"] += 1

    _mesh = _u.EditorAssetLibrary.load_asset(FACE_MESH)
    if _mesh is None:
        raise RuntimeError("could not load Face mesh " + FACE_MESH)

    # High above the terrain, against sky. Keeps the background constant
    # and keeps the landscape's geometry out of a portrait framing.
    _base = _u.Vector(0.0, 0.0, float(STAGE_Z))
    _subj = _eas.spawn_actor_from_class(
        _u.SkeletalMeshActor, _base, _u.Rotator(0, 0, 0))
    _subj.set_actor_label("HeroStage_Subject")
    _subj.skeletal_mesh_component.set_skeletal_mesh_asset(_mesh)

    # MEASURE the subject. Every distance below derives from this box, so
    # a mesh at an unexpected scale reframes itself instead of landing in
    # the near clip plane.
    _o, _e = _subj.get_actor_bounds(False)
    _out["subject"] = {"origin": [_o.x, _o.y, _o.z],
                       "extent": [_e.x, _e.y, _e.z],
                       "height_cm": _e.z * 2.0}
    _h = max(_e.z * 2.0, 1.0)

    # --- three-point rig ------------------------------------------------
    # INTENSITY IS IN LUX AND MUST COMPETE WITH THE LEVEL'S OWN SUN.
    # Measured the hard way: at the engine-default intensity these lights
    # were invisible beside Alpine8K's 130,000 lux sun and the subject
    # photographed as a pure backlit silhouette. Orientation is set per
    # capture in SHOOT, relative to the chosen azimuth, because a rig
    # aimed at a fixed world direction lights the back of the head for
    # half the possible framings.
    def _light(cls, label, intensity, color):
        _a = _eas.spawn_actor_from_class(
            cls, _u.Vector(_o.x, _o.y, _o.z + _h), _u.Rotator(0, 0, 0))
        _a.set_actor_label(label)
        # NO intensity_units HERE. ELightUnits has no LUX member because a
        # DIRECTIONAL light's units are fixed:
        # DirectionalLightComponent.cpp:1509 -- GetLightUnits() returns
        # Unitless /* Lux */. Setting it raised AttributeError while
        # EVALUATING THE ARGUMENT, so the intensity line below never ran and
        # the rig sat at engine default while the report said it was built.
        _c = _a.get_component_by_class(_u.LightComponent)
        _c.set_editor_property("intensity", intensity)
        _c.set_editor_property("light_color", color)
        _rb = _c.get_editor_property("intensity")
        if abs(float(_rb) - float(intensity)) > 1e-3:
            raise RuntimeError(
                "%s intensity read back %s, asked %s" % (label, _rb, intensity))
        _out["actors"].append(label)

    # THE FIRST WORKING NUMBERS WERE TOO HIGH, AND THE REASON IS INSTRUCTIVE:
    # they were chosen while the rig was MIS-AIMED (a Rotator argument-order
    # bug), so the level's own 130,000 lux sun was doing all the modelling and
    # 90,000 looked harmless. With the aim corrected the key lands square on
    # the face and blows it out -- and a blown face has no shape for the
    # landmarks to measure, which is the whole point of the instrument.
    # A value tuned against a broken version of the thing it lights is not a
    # value; it is a compensation.
    _light(_u.DirectionalLight, "HeroStage_Key", __KEY_LUX__,
           _u.Color(255, 250, 244))
    _light(_u.DirectionalLight, "HeroStage_Fill", __KEY_LUX__ * 0.30,
           _u.Color(238, 243, 255))
    _light(_u.DirectionalLight, "HeroStage_Rim", __KEY_LUX__ * 0.45,
           _u.Color(255, 255, 255))
    _out["actors"].append("HeroStage_Subject")

    # --- capture rig ---------------------------------------------------
    _rt = _u.RenderingLibrary.create_render_target2d(
        _w, RES, RES, _u.TextureRenderTargetFormat.RTF_RGBA8)
    _cap = _eas.spawn_actor_from_class(_u.SceneCapture2D, _base,
                                       _u.Rotator(0, 0, 0))
    _cap.set_actor_label("HeroStage_Camera")
    _cc = _cap.get_component_by_class(_u.SceneCaptureComponent2D)
    _cc.set_editor_property("texture_target", _rt)
    _cc.set_editor_property("fov_angle", FOV)
    _cc.set_editor_property("capture_source",
                            _u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    # Triggered only. A frame is taken when this says so and never
    # otherwise, so two captures differ by what changed and nothing else.
    for _flag in ("capture_every_frame", "capture_on_movement"):
        try:
            _cc.set_editor_property(_flag, False)
        except Exception as _e2:
            _out["notes"].append("%s: %s" % (_flag, _e2))

    # FIXED EXPOSURE. AEM_MANUAL with min == max brightness, the mechanism
    # R13 already proved on this project's alpine scene.
    _pp = _u.PostProcessSettings()
    _sets = [("auto_exposure_method", _u.AutoExposureMethod.AEM_MANUAL),
             ("auto_exposure_bias", float(EXPOSURE)),
             ("auto_exposure_min_brightness", 1.0),
             ("auto_exposure_max_brightness", 1.0),
             ("motion_blur_amount", 0.0)]
    for _k, _v in _sets:
        try:
            _pp.set_editor_property(_k, _v)
        except Exception as _e2:
            _out["notes"].append("pp.%s: %s" % (_k, _e2))
        try:
            _pp.set_editor_property("override_" + _k, True)
        except Exception as _e2:
            _out["notes"].append("pp.override_%s: %s" % (_k, _e2))
    _cc.set_editor_property("post_process_settings", _pp)
    _cc.set_editor_property("post_process_blend_weight", 1.0)
    _out["actors"].append("HeroStage_Camera")
    _out["render_target"] = _rt.get_path_name()
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out, default=str))
'''

SHOOT = r'''
import json as _json
import math as _math
import unreal as _u

AZ_DEG   = __AZ__
DIST_MUL = __DIST_MUL__
HEIGHT_F = __HEIGHT_F__
WARM     = __WARM__
OUT_DIR  = r"__OUT_DIR__"
OUT_NAME = "__OUT_NAME__"

_out = {"ok": False, "error": None, "camera": {}, "hidden": [], "png": None,
        "lights": [], "cvars": []}

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
        raise RuntimeError("stage actors missing; build the stage first")

    # GROOMS OFF. A hairline over the brow poisons the brow landmarks, and
    # brow_height is a region this pipeline fits.
    for _c in _subj.get_components_by_class(_u.PrimitiveComponent):
        _cn = _c.get_class().get_name()
        if "Groom" in _cn or "Hair" in _cn:
            try:
                _c.set_editor_property("visible", False)
                _out["hidden"].append(_cn)
            except Exception:
                pass

    _o, _e = _subj.get_actor_bounds(False)
    _tgt = _u.Vector(_o.x, _o.y, _o.z + _e.z * HEIGHT_F)
    _r = max(_e.x, _e.y, _e.z) * DIST_MUL
    _a = _math.radians(AZ_DEG)
    _camloc = _u.Vector(_tgt.x + _r * _math.cos(_a),
                        _tgt.y + _r * _math.sin(_a), _tgt.z)
    _cap.set_actor_location(_camloc, False, False)
    _rot = _u.MathLibrary.find_look_at_rotation(_camloc, _tgt)
    _cap.set_actor_rotation(_rot, False)

    # RE-AIM THE RIG RELATIVE TO THE CAMERA. A directional light's rotation
    # is the direction light TRAVELS (this project's own recorded trap: the
    # sun is at bearing 105, not 285), so a light that COMES FROM azimuth A
    # has yaw A+180. Fixing the rig in world space instead lights the back
    # of the head for half the framings -- measured, az 270 photographed a
    # pure silhouette.
    for _nm, _off, _pitch in (("HeroStage_Key",  -30.0, -22.0),
                              ("HeroStage_Fill",  45.0, -8.0),
                              ("HeroStage_Rim",  180.0, -5.0)):
        _la = _lights.get(_nm)
        if _la is None:
            _out["lights"].append({"name": _nm, "state": "MISSING"})
            continue
        _yaw = (AZ_DEG + _off + 180.0) % 360.0
        # unreal.Rotator TAKES (roll, pitch, yaw) -- PythonStub:66750.
        _lr = _u.Rotator(0.0, _pitch, _yaw)
        _la.set_actor_rotation(_lr, False)
        _rr = _la.get_actor_rotation()
        if abs(_rr.pitch - _pitch) > 1e-3 or abs(
                ((_rr.yaw - _yaw + 180.0) % 360.0) - 180.0) > 1e-3:
            raise RuntimeError(
                "%s rotation read back (p %.3f y %.3f), asked (p %.3f y %.3f)"
                % (_nm, _rr.pitch, _rr.yaw, _pitch, _yaw))
        _li = "UNREADABLE"
        try:
            _lc = _la.get_component_by_class(_u.LightComponent)
            _li = _lc.get_editor_property("intensity")
        except Exception as _e2:
            _li = "UNREADABLE: %s" % str(_e2)[:60]
        _out["lights"].append({"name": _nm, "comes_from_az": AZ_DEG + _off,
                               "pitch": _pitch, "yaw": _yaw,
                               "intensity": _li})

    _cc = _cap.get_component_by_class(_u.SceneCaptureComponent2D)
    _rt = _cc.get_editor_property("texture_target")

    # WITHOUT THIS EVERY CAPTURE STARTS WITH NO RENDERING HISTORY and the
    # virtual textures the MetaHuman face uses (MID_MI_Face_Skin_Baked_*_VT_*)
    # never resolve off their white fallback. Measured: mean 254.85 /
    # nonwhite 0.027 before, 161.90 / 1.000 after, converged by 10 frames.
    _cc.set_editor_property("always_persist_rendering_state", True)
    for _cv in ("r.Streaming.FullyLoadUsedTextures 1",
                "r.VT.MaxUploadsPerFrame 512",
                "r.VT.MaxContinuousUpdatesPerFrame 512"):
        try:
            _u.SystemLibrary.execute_console_command(_w, _cv)
            _out["cvars"].append(_cv)
        except Exception as _e2:
            _out["cvars"].append("%s FAILED %s" % (_cv, str(_e2)[:60]))

    # WARM-UP: repeated TRIGGERED captures so shader compilation and
    # texture streaming settle. Only the last frame is exported.
    for _i in range(WARM):
        _cc.capture_scene()
    _cc.capture_scene()

    _u.RenderingLibrary.export_render_target(_w, _rt, OUT_DIR, OUT_NAME)

    _out["png"] = OUT_DIR + "\\" + OUT_NAME
    _out["camera"] = {
        "location": [_camloc.x, _camloc.y, _camloc.z],
        "rotation": [_rot.pitch, _rot.yaw, _rot.roll],
        "target": [_tgt.x, _tgt.y, _tgt.z],
        "azimuth_deg": AZ_DEG, "distance_cm": _r,
        "fov_angle": _cc.get_editor_property("fov_angle"),
        "warmup_frames": WARM,
        "subject_extent": [_e.x, _e.y, _e.z],
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
        tpl = tpl.replace("__%s__" % k, str(v))
    return tpl


def exposure_stats(png):
    """Blown and crushed fraction over the CENTRE of the frame.

    Scoped to the middle half deliberately: the subject fills it and the sky
    does not, so a bright background cannot flatter the number. That is the
    misleading-denominator rule -- a statistic about the face conditioned on
    the whole frame answers a question nobody asked.
    """
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    c = a[h // 4:3 * h // 4, w // 4:3 * w // 4, :]
    # BLOWN MEANS ALL THREE CHANNELS CLIPPED -- no information left. Testing
    # max(channel) instead calls a warm skin highlight blown because its RED
    # is near saturation, and reported 0.738 on a frame with ZERO actual
    # clipping and a centre mean of (245, 206, 174). A metric that fires on
    # skin tone is not an exposure metric.
    lo = c.min(axis=2)
    per_channel = c.reshape(-1, 3).mean(axis=0)
    return {"blown": float((lo >= 250).mean()),
            "crushed": float((c.max(axis=2) <= 5).mean()),
            "mean": float(c.mean()),
            "rgb": [float(v) for v in per_channel],
            # Any single channel pinned at the ceiling still loses shape in
            # that channel, so it is reported -- as a warning, not as "blown".
            "hottest_channel": float(per_channel.max())}


def gate_report(png, model):
    """Run a capture through capture_landmarks' OWN gate, so the framing is
    accepted by exactly the check every later measurement applies."""
    try:
        pts, w, h = CL.detect(png, model)
    except LookupError:
        return False, {"why": "no face detected"}
    except Exception as exc:
        return False, {"why": "detect raised: %s" % str(exc)[:120]}
    c, ipd, roll = CL.canonical(pts)
    checks, fatal, stats = CL.quality(pts, c, w, h, ipd, roll, "capture")
    return (not fatal), {"stats": stats, "fatal": fatal}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--res", type=int, default=2048)
    ap.add_argument("--fov", type=float, default=24.0,
                    help="horizontal FOV; 24 deg ~= 85 mm on a 36 mm sensor")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--stage-z", type=float, default=250000.0)
    ap.add_argument("--key-lux", type=float, default=25000.0,
                    help="key light in lux; fill and rim are 0.30 and 0.45 "
                         "of it. The level's own sun is 130,000 lux, so this "
                         "shapes rather than replaces it. Judged by the "
                         "BLOWN-PIXEL fraction the gate now prints, not by eye")
    ap.add_argument("--dist-mul", type=float, default=3.2)
    ap.add_argument("--height-frac", type=float, default=0.62)
    ap.add_argument("--azimuths", default="90,270,0,180,45,135,225,315")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    with open(args.manifest, "r", encoding="utf-8") as fh:
        man = json.load(fh)

    def _res(p):
        return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)

    model = _res(man["paths"]["mediapipe_model"])
    out_dir = _res(man["paths"]["renders_dir"])
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 72)
    print("BUILDING THE CAPTURE STAGE")
    print("=" * 72)
    rc, d, _ = ue_exec.run(
        _fill(BUILD, KEY_LUX=args.key_lux,
              FACE_MESH=man["unreal"]["face_skeletal_mesh"],
              RES=args.res, FOV=args.fov, EXPOSURE=args.exposure,
              STAGE_Z=args.stage_z),
        timeout=args.timeout, stage_name="hero_build_stage")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        return 5
    print("level    : %s  (stage built in the OPEN level; nothing saved)"
          % d["level"])
    print("subject  : height %.2f cm  extent %s"
          % (d["subject"]["height_cm"],
             [round(v, 2) for v in d["subject"]["extent"]]))
    print("destroyed: %d previous stage actor(s)" % d["destroyed"])
    print("actors   : %s" % ", ".join(d["actors"]))
    for n in d["notes"]:
        print("  note   : %s" % n)
    print()

    print("=" * 72)
    print("FINDING THE FRONT — the facing is a property of the asset, so it")
    print("is SEARCHED and confirmed by the gate, not recalled.")
    print("=" * 72)
    best = None
    for az in [float(a) for a in args.azimuths.split(",")]:
        name = "frame_az%03d.png" % int(az)
        rc, s, _ = ue_exec.run(
            _fill(SHOOT, AZ=az, DIST_MUL=args.dist_mul,
                  HEIGHT_F=args.height_frac, WARM=args.warmup,
                  OUT_DIR=out_dir.replace("\\", "\\\\"), OUT_NAME=name),
            timeout=args.timeout, stage_name="hero_shoot")
        if s is None or s.get("error"):
            print("  az %6.1f  payload error: %s"
                  % (az, str((s or {}).get("error", "no result"))[:90]))
            continue
        png = os.path.join(out_dir, name)
        if not os.path.isfile(png):
            print("  az %6.1f  NO PNG WRITTEN" % az)
            continue
        passed, rep = gate_report(png, model)
        st = rep.get("stats", {})
        ex = exposure_stats(png)
        if passed:
            print("  az %6.1f  GATE PASS   yaw %.3f  roll %+.2f  asym %.3f"
                  % (az, st.get("yaw_frac", 0), st.get("roll_deg", 0),
                     st.get("worst_asymmetry", 0)))
            print("            centre  clipped %.4f  crushed %.4f  "
                  "rgb %.0f/%.0f/%.0f"
                  % (ex["blown"], ex["crushed"],
                     ex["rgb"][0], ex["rgb"][1], ex["rgb"][2]))
            if ex["blown"] > 0.01:
                print("            OVER-EXPOSED — lower --key-lux or the "
                      "manifest's exposure_bias")
            elif ex["hottest_channel"] > 240.0:
                print("            hottest channel %.0f — no clipping, but "
                      "little headroom" % ex["hottest_channel"])
            score = abs(st.get("yaw_frac", 0.5) - 0.5)
            if best is None or score < best[0]:
                best = (score, az, s["camera"], rep)
        else:
            why = rep.get("why") or "; ".join(rep.get("fatal", []))[:100]
            print("  az %6.1f  reject      %s" % (az, why))

    if best is None:
        print()
        print("*** NO AZIMUTH PRODUCED A FACE THE GATE ACCEPTS ***")
        print()
        print("Reported, not fudged. OPEN THE FRAMES before touching a")
        print("threshold: %s" % os.path.relpath(out_dir, REPO_ROOT))
        print("A white or black frame is lighting or exposure, not framing,")
        print("and no amount of reframing fixes it.")
        return 4

    score, az, cam, rep = best
    print()
    print("CHOSEN azimuth %.1f deg  (yaw offset %.4f from frontal)"
          % (az, score))

    # PRESERVE WHAT WAS MEASURED. This block is REPLACED wholesale when the
    # framing is locked, and it used to take the measured noise floor and the
    # presence manifest with it. Nothing complained, because every consumer
    # fell back to a hardcoded default (fl_p90 = 0.01) that sits near the
    # real 0.0104 -- so the fit loop ran UNCALIBRATED while reporting numbers
    # that looked calibrated. A silent fallback to a plausible constant is
    # worse than a missing key, and the fit loop now refuses instead.
    _keep = {k: v for k, v in (man.get("capture") or {}).items()
             if k in ("noise_floor", "presence")}
    man["capture"] = {
        "_what": "The measuring instrument. Framed ONCE, by search, and "
                 "confirmed by the same gate capture_landmarks applies, so "
                 "every capture afterwards passes it by construction.",
        "_level_note": "Built in whatever level is open, subject lifted "
                       "against sky. A payload that switches levels fatals "
                       "the editor (EditorServer.cpp:1951) and open_level.py "
                       "takes a recipe, not a raw path.",
        "resolution": [args.res, args.res],
        "fov_angle_deg": args.fov,
        "_lens": "%.1f deg horizontal FOV ~= 85 mm on a 36 mm sensor; long, "
                 "to keep perspective out of the landmark solve." % args.fov,
        "exposure_bias": args.exposure,
        "_exposure": "AEM_MANUAL, min == max brightness. No auto-anything.",
        "warmup_frames": args.warmup,
        "stage_z_cm": args.stage_z,
        "dist_mul": args.dist_mul,
        "height_frac": args.height_frac,
        "azimuth_deg": az,
        "hide_grooms": True,
        "camera": cam,
        "subject_actor": "HeroStage_Subject",
        "camera_actor": "HeroStage_Camera",
        "gate_at_framing": rep.get("stats", {}),
        **_keep,
    }
    if _keep:
        print("preserved across the rebuild: %s" % ", ".join(sorted(_keep)))
    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2)
    print("locked into %s" % os.path.relpath(args.manifest, REPO_ROOT))
    print("   camera loc %s" % [round(v, 2) for v in cam["location"]])
    print("   camera rot %s" % [round(v, 3) for v in cam["rotation"]])
    print()
    print("NEXT: the noise floor. Two captures of the UNCHANGED character")
    print("bound what any later 'the joint moved' claim has to beat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
