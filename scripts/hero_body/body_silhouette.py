"""THE SHOULDER RULER. Body widths in absolute centimetres, from a render.

WHY THIS EXISTS
    The face was measured to 0.0007 cm all night while nobody measured his
    shoulders, and the first body-framed picture of the hero read androgynous.
    A parameter nobody can measure is a parameter nobody can verify, so this
    is built BEFORE anything is changed -- ruling 3, 2026-08-19.

WHY ORTHOGRAPHIC, AND IT IS THE WHOLE DESIGN
    A perspective camera makes a width a function of distance, so "wider"
    and "nearer" are the same measurement. `projection_type` ORTHOGRAPHIC
    with a locked `ortho_width` makes centimetres per pixel a CONSTANT OF THE
    CAMERA:  cm_per_px = ortho_width / res_x.  The subject cannot move the
    ruler, which is the same lesson the face loop learned when it stopped
    normalising the render by its own IPD.

WHY A DIFFERENCE MASK RATHER THAN A COLOUR THRESHOLD
    Segmenting "body" from "sky" by hue works until the hero wears a grey
    tank top against a grey-blue horizon. So the subject is photographed
    TWICE -- visible, then hidden -- and the silhouette is every pixel that
    CHANGED. That is a difference of two renders taken seconds apart with one
    variable, and it carries its own presence check for free: an empty mask
    means the subject did not render, which a colour threshold would have
    reported as a very thin man.

WHAT IS MEASURED
    Stature, then widths at fractions of stature measured up from the feet:
    hip 0.50, waist 0.62, chest 0.72, shoulder 0.81, plus the widest row in
    the shoulder band (0.78..0.86), which is less sensitive to a one-row
    sampling accident than any single height.

EXIT CODES
    0  measured
    2  bad arguments, or no manifest
    3  no editor matched UE_PROJECT_ROOT
    5  payload error
    6  the silhouette mask was empty or degenerate -- the subject did not
       render, and no width here would have been a measurement
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_LIKENESS = os.path.join(REPO_ROOT, "scripts", "hero_face", "likeness")
for _p in (REPO_ROOT, _HERE, _LIKENESS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import ue_exec                        # noqa: E402

DEFAULT_MANIFEST = os.path.join(_LIKENESS, "manifest.json")


PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

CHARACTER   = "__CHARACTER__"
OUT_DIR     = r"__OUT_DIR__"
STAMP       = "__STAMP__"
RES         = __RES__
ORTHO_WIDTH = __ORTHO_WIDTH__
STAGE_Z     = __STAGE_Z__
SUBJ_YAW    = __SUBJ_YAW__
LOCKED      = __LOCKED__

_out = {"ok": False, "error": None, "refusals": []}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _w = _ues.get_editor_world()

    _ch = _u.EditorAssetLibrary.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        _sub.try_add_object_to_edit(_ch)
    _sub.assemble_for_preview(_ch)
    _prev = _sub.spawn_meta_human_actor(_ch, True)
    _prev.set_actor_label("HeroBodyPreview")

    # THE BODY MESH IS TRANSIENT and is replaced by every preview assemble,
    # so it is re-read here every run rather than remembered.
    _body = None
    for _c in _prev.get_components_by_class(_u.SkeletalMeshComponent):
        if "body" in str(_c.get_name()).lower():
            _body = _c
            break
    if _body is None:
        raise RuntimeError("preview actor has no Body component")
    _mesh = _body.get_editor_property("skeletal_mesh_asset")
    if _mesh is None:
        raise RuntimeError("Body component carries no mesh")
    _out["body_mesh"] = str(_mesh.get_path_name())

    # subject actor at a fixed, known place against sky
    _subj = None
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroBodyStage_Subject":
            _subj = _a
    if _subj is None:
        _subj = _eas.spawn_actor_from_class(
            _u.SkeletalMeshActor, _u.Vector(0.0, 0.0, STAGE_Z),
            _u.Rotator(0.0, 0.0, 0.0))
        _subj.set_actor_label("HeroBodyStage_Subject")
    # FACING IS MEASURED, NOT ASSUMED. At yaw 0 this mesh photographed in
    # PROFILE, so the widths would have been depths -- the same wrong-axis
    # trap the assembled Blueprint sprang in the landscape shot.
    _subj.set_actor_rotation(_u.Rotator(0.0, 0.0, SUBJ_YAW), False)
    _subj.set_actor_location(_u.Vector(0.0, 0.0, STAGE_Z), False, False)
    _sc = _subj.skeletal_mesh_component
    _sc.set_skeletal_mesh_asset(_mesh)
    _prev.set_actor_location(_u.Vector(0.0, 0.0, STAGE_Z - 100000.0),
                             False, False)

    _b = _sc.get_editor_property("skeletal_mesh_asset").get_bounds()
    _ext = _b.box_extent
    _org = _b.origin
    _out["mesh_extent"] = [round(_ext.x, 3), round(_ext.y, 3), round(_ext.z, 3)]
    _out["mesh_origin"] = [round(_org.x, 3), round(_org.y, 3), round(_org.z, 3)]

    # lights: two, aimed along the view, only so the body is not black
    for _nm, _yaw, _pitch, _lux in (("HeroBodyStage_Key", 0.0, -12.0, 12000.0),
                                    ("HeroBodyStage_Fill", 40.0, 0.0, 6000.0)):
        _la = None
        for _a in _eas.get_all_level_actors():
            if _a.get_actor_label() == _nm:
                _la = _a
        if _la is None:
            _la = _eas.spawn_actor_from_class(
                _u.DirectionalLight, _u.Vector(0.0, 0.0, STAGE_Z + 500.0),
                _u.Rotator(0.0, 0.0, 0.0))
            _la.set_actor_label(_nm)
        _la.set_actor_rotation(_u.Rotator(0.0, _pitch, _yaw), False)
        _lc = _la.get_component_by_class(_u.LightComponent)
        _lc.set_editor_property("intensity", _lux)

    _cap = None
    for _a in _eas.get_all_level_actors():
        if _a.get_actor_label() == "HeroBodyStage_Camera":
            _cap = _a
    if _cap is None:
        _cap = _eas.spawn_actor_from_class(
            _u.SceneCapture2D, _u.Vector(0.0, 0.0, STAGE_Z),
            _u.Rotator(0.0, 0.0, 0.0))
        _cap.set_actor_label("HeroBodyStage_Camera")
    _cc = _cap.get_component_by_class(_u.SceneCaptureComponent2D)

    _rt = _u.RenderingLibrary.create_render_target2d(
        _w, RES, RES, _u.TextureRenderTargetFormat.RTF_RGBA8)
    _cc.set_editor_property("texture_target", _rt)
    _cc.set_editor_property("capture_source",
                            _u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    _cc.set_editor_property("capture_every_frame", False)
    _cc.set_editor_property("always_persist_rendering_state", True)
    # ORTHOGRAPHIC: cm per pixel becomes a constant of the camera, so the
    # subject cannot move the ruler.
    _cc.set_editor_property("projection_type",
                            _u.CameraProjectionMode.ORTHOGRAPHIC)
    _cc.set_editor_property("ortho_width", float(ORTHO_WIDTH))

    # camera looks along -X at the subject's own centre, level
    _cam_loc = _u.Vector(-600.0, 0.0, STAGE_Z + float(_org.z))
    _cap.set_actor_location_and_rotation(
        _cam_loc, _u.Rotator(0.0, 0.0, 0.0), False, False)
    _rb = _cap.get_actor_location()
    if abs(_rb.z - _cam_loc.z) > 0.5:
        _out["refusals"].append("camera z read back %.3f, set %.3f"
                                % (_rb.z, _cam_loc.z))
    _got = float(_cc.get_editor_property("ortho_width"))
    if abs(_got - float(ORTHO_WIDTH)) > 1e-3:
        _out["refusals"].append("ortho_width read back %.4f, set %.4f"
                                % (_got, ORTHO_WIDTH))
    _out["camera"] = {"location": [round(_rb.x, 4), round(_rb.y, 4),
                                   round(_rb.z, 4)],
                      "ortho_width": _got, "res": RES,
                      "cm_per_px": round(_got / float(RES), 6),
                      "projection": str(
                          _cc.get_editor_property("projection_type"))}

    for _cv in ("r.Streaming.FullyLoadUsedTextures 1",):
        _u.SystemLibrary.execute_console_command(_w, _cv)

    # ANATOMY COMES FROM THE SKELETON, NOT FROM A GUESSED FRACTION OF HEIGHT.
    # The first version sampled 0.81 of stature for "shoulder" and got a
    # waist wider than the shoulders, because this mesh is the BODY ONLY --
    # no head -- so every fraction was aimed one landmark too low, and the
    # A-pose arms sit in the lower rows. Bone world-Z is unambiguous.
    _bones = {}
    for _bn in ("root", "pelvis", "spine_01", "spine_03", "spine_05",
                "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r",
                "neck_01", "head", "foot_l", "thigh_l"):
        try:
            _p = _sc.get_socket_location(_bn)
            _bones[_bn] = round(float(_p.z), 4)
        except Exception:
            pass
    _out["bone_world_z"] = _bones

    def _shoot(name):
        for _i in range(24):
            _cc.capture_scene()
        _cc.capture_scene()
        _fn = "body_%s_%s.png" % (name, STAMP)
        _u.RenderingLibrary.export_render_target(_w, _rt, OUT_DIR, _fn)
        return _fn

    # TWO FRAMES, ONE VARIABLE: subject visible, then hidden. The silhouette
    # is what CHANGED, which needs no assumption about the hero's colours.
    _subj.set_is_temporarily_hidden_in_editor(False)
    _out["png_subject"] = _shoot("subject")
    _subj.set_is_temporarily_hidden_in_editor(True)
    _out["png_plate"] = _shoot("plate")
    _subj.set_is_temporarily_hidden_in_editor(False)

    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:600]

print("__LL__" + _json.dumps(_out, default=str))
'''


def _stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")


def measure_at_bones(subject_png, plate_png, cam, bones):
    """Widths in cm at BONE-ANCHORED heights, from the difference mask.

    Orthographic, so a world Z maps to a row by a constant:
        row = (cam_z + half_height - z) / cm_per_px
    """
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(subject_png).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(plate_png).convert("RGB")).astype(np.int16)
    diff = np.abs(a - b).max(axis=2)
    mask = diff > 12
    rows = np.where(mask.any(axis=1))[0]
    if rows.size < 32 or float(mask.mean()) < 0.005:
        print("*** SILHOUETTE DEGENERATE — the subject did not render ***")
        raise SystemExit(6)

    cm_per_px = cam["cm_per_px"]
    half = cam["ortho_width"] / 2.0
    cam_z = cam["location"][2]
    res = cam["res"]

    # THE TORSO IS THE RUN THROUGH THE CENTRE, NOT THE FULL SPAN OF THE ROW.
    # In A-pose the arms hang away from the body, so a min-to-max span at
    # chest height measures ARM TO ARM: the first front-on run read chest
    # 94.5 cm and waist 110.7 cm on a 178 cm man. Taking only the connected
    # run that contains the body's centre column excludes a detached arm and
    # still includes the deltoid where it genuinely joins the shoulder.
    def _longest_run(row):
        """Longest contiguous run of mask pixels in a row -> (start, length).

        No assumption about WHERE the body sits in frame. A centre-column
        walk was tried first and returned zeros, because with the arms out
        the midpoint of the silhouette's extent can fall in the GAP between
        torso and arm. The torso is simply the longest run at every height
        that matters, and at shoulder height the deltoids merge into it,
        which is exactly what a shoulder width should include.
        """
        best_len = best_start = 0
        cur_len = 0
        cur_start = 0
        for x in range(row.size):
            if row[x]:
                if cur_len == 0:
                    cur_start = x
                cur_len += 1
                if cur_len > best_len:
                    best_len, best_start = cur_len, cur_start
            else:
                cur_len = 0
        return best_start, best_len

    def width_at_z(z, full_span=False):
        r = int(round((cam_z + half - z) / cm_per_px))
        if r < 0 or r >= res:
            return None
        xs = np.where(mask[r])[0]
        if xs.size == 0:
            return 0.0
        if full_span:
            return round(float(xs.max() - xs.min() + 1) * cm_per_px, 4)
        _s, _l = _longest_run(mask[r])
        return round(float(_l) * cm_per_px, 4)

    out = {}
    # SHOULDER IS ANCHORED AT upperarm, NOT clavicle. Measured 2026-08-19:
    # clavicle_l sits 3 cm below the top of the BODY mesh (which ends at the
    # neck, the head being a separate mesh), so a width sampled there reads
    # the NECK -- 7.6 cm. The acromion line is the upperarm joint, 5.4 cm
    # below the mesh top, and it is where deltoid-to-deltoid actually spans.
    pairs = (("shoulder", "upperarm_l"), ("chest", "spine_03"),
             ("waist", "spine_01"), ("hip", "pelvis"))
    for name, bone in pairs:
        z = bones.get(bone)
        out[name + "_cm"] = None if z is None else width_at_z(z)
        out[name + "_z"] = z
    # widest row anywhere in the deltoid band: clavicle +- 6 cm
    cz = bones.get("upperarm_l")
    if cz is not None:
        ws = [width_at_z(cz + d) for d in (-6, -4, -2, 0, 2, 4, 6)]
        ws = [w for w in ws if w]
        out["shoulder_band_max_cm"] = round(max(ws), 4) if ws else None
        # the full row span at shoulder height, kept ONLY as the arms-included
        # figure so the two are never confused for each other
        out["shoulder_full_span_cm"] = width_at_z(cz, full_span=True)
    out["body_top_z"] = round(cam_z + half - float(rows.min()) * cm_per_px, 3)
    out["body_bottom_z"] = round(cam_z + half - float(rows.max()) * cm_per_px, 3)
    out["body_height_cm"] = round((rows.max() - rows.min() + 1) * cm_per_px, 3)
    out["coverage_frac"] = round(float(mask.mean()), 5)
    if out.get("shoulder_cm") and out.get("hip_cm"):
        out["shoulder_over_hip"] = round(out["shoulder_cm"] / out["hip_cm"], 4)
    return out


def measure(subject_png, plate_png, cm_per_px):
    """-> dict of body widths in cm, from the difference mask.

    Raises SystemExit(6) on a degenerate mask rather than returning a number,
    because a thin or empty silhouette is the subject failing to render and
    every width computed from it would be a confident fiction.
    """
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(subject_png).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(plate_png).convert("RGB")).astype(np.int16)
    if a.shape != b.shape:
        raise SystemExit(5)
    diff = np.abs(a - b).max(axis=2)
    mask = diff > 12

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    cover = float(mask.mean())
    if rows.size < 32 or cols.size < 8 or cover < 0.005:
        print("*** SILHOUETTE DEGENERATE — rows %d cols %d coverage %.4f%% ***"
              % (rows.size, cols.size, 100.0 * cover))
        print("The subject did not render. No width here is a measurement.")
        raise SystemExit(6)

    top, bot = int(rows.min()), int(rows.max())
    stature_px = bot - top + 1

    def width_at(frac):
        """Width in cm at a fraction of stature measured UP from the feet."""
        y = int(round(bot - frac * (stature_px - 1)))
        y = max(top, min(bot, y))
        xs = np.where(mask[y])[0]
        if xs.size == 0:
            return 0.0
        return float(xs.max() - xs.min() + 1) * cm_per_px

    band = [(int(round(bot - f * (stature_px - 1)))) for f in
            (0.78, 0.80, 0.82, 0.84, 0.86)]
    band_w = []
    for y in band:
        xs = np.where(mask[max(top, min(bot, y))])[0]
        band_w.append(0.0 if xs.size == 0
                      else float(xs.max() - xs.min() + 1) * cm_per_px)

    return {
        "stature_cm": round(stature_px * cm_per_px, 4),
        "hip_cm": round(width_at(0.50), 4),
        "waist_cm": round(width_at(0.62), 4),
        "chest_cm": round(width_at(0.72), 4),
        "shoulder_cm": round(width_at(0.81), 4),
        "shoulder_band_max_cm": round(max(band_w), 4),
        "coverage_frac": round(cover, 5),
        "mask_rows": int(stature_px),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero_Scratch2")
    ap.add_argument("--label", default=None,
                    help="tag recorded with the measurement")
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--ortho-width", type=float, default=260.0,
                    help="world cm across the frame. LOCKED once: it is the "
                         "ruler, and a ruler that changes per run is not one")
    ap.add_argument("--stage-z", type=float, default=250000.0)
    ap.add_argument("--subject-yaw", type=float, default=90.0,
                    help="yaw that turns the mesh FRONT-ON. Measured, not "
                         "assumed: at yaw 0 this mesh photographs in PROFILE "
                         "and every width is really a depth")
    ap.add_argument("--settle", action="store_true", default=True,
                    help="take shots until two consecutive agree (default)")
    ap.add_argument("--no-settle", dest="settle", action="store_false",
                    help="one shot only. The result may be the PREVIOUS body")
    ap.add_argument("--settle-tol", type=float, default=0.30,
                    help="cm of body-height drift allowed between two "
                         "consecutive runs")
    ap.add_argument("--out", default=None)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    with open(args.manifest, "r", encoding="utf-8") as fh:
        man = json.load(fh)
    out_dir = man["paths"]["renders_dir"]
    out_dir = (out_dir if os.path.isabs(out_dir)
               else os.path.join(REPO_ROOT, out_dir))
    out_dir = os.path.join(out_dir, "body")
    os.makedirs(out_dir, exist_ok=True)

    stamp = _stamp()
    src = PAYLOAD
    for k, v in (("__CHARACTER__", args.character),
                 ("__OUT_DIR__", out_dir.replace("\\", "\\\\")),
                 ("__STAMP__", stamp),
                 ("__RES__", str(int(args.res))),
                 ("__ORTHO_WIDTH__", repr(float(args.ortho_width))),
                 ("__STAGE_Z__", repr(float(args.stage_z))),
                 ("__SUBJ_YAW__", repr(float(args.subject_yaw))),
                 ("__LOCKED__", "True")):
        src = src.replace(k, v)

    def _one(tag):
        s2 = src.replace(stamp, stamp + tag) if tag else src
        rc, d, _ = ue_exec.run(s2, timeout=args.timeout,
                               stage_name="body_silhouette")
        if rc == 3:
            raise SystemExit(3)
        if d is None or d.get("error"):
            print("PAYLOAD ERROR:\n%s"
                  % ((d or {}).get("error") or "no result"))
            raise SystemExit(5)
        if d.get("refusals"):
            print("*** THE INSTRUMENT DISAGREED WITH ITS OWN SETTINGS ***")
            for r in d["refusals"]:
                print("  - %s" % r)
            raise SystemExit(5)
        return d

    # A MEASUREMENT TAKEN RIGHT AFTER A BODY-CONSTRAINT WRITE IS THE PREVIOUS
    # BODY. Measured 2026-08-19: Height 178.196 -> 190 -> 205 read 159.45,
    # 159.45, 149.30 -- each run showing the state before it -- while two runs
    # with NOTHING changed agree to three decimals. The parametric body lands
    # asynchronously, so the same reproduce-gate the face captures use applies
    # here: take shots until two CONSECUTIVE ones agree, and refuse rather
    # than return a frame that is still catching up.
    d = _one("")
    if args.settle:
        prev = measure_at_bones(
            os.path.join(out_dir, d["png_subject"]),
            os.path.join(out_dir, d["png_plate"]),
            d["camera"], d.get("bone_world_z") or {})
        for attempt in range(1, 4):
            d2 = _one("_s%d" % attempt)
            cur = measure_at_bones(
                os.path.join(out_dir, d2["png_subject"]),
                os.path.join(out_dir, d2["png_plate"]),
                d2["camera"], d2.get("bone_world_z") or {})
            drift = abs((cur.get("body_height_cm") or 0)
                        - (prev.get("body_height_cm") or 0))
            print("   settle %d: body height moved %.3f cm" % (attempt, drift))
            d, prev = d2, cur
            if drift <= args.settle_tol:
                break
        else:
            print("*** NEVER SETTLED — the body kept changing between runs ***")
            return 6

    cam = d["camera"]
    print("=" * 72)
    print("BODY SILHOUETTE — %s" % args.character)
    print("=" * 72)
    print("projection %s   ortho_width %.2f cm over %d px = %.6f cm/px"
          % (cam["projection"], cam["ortho_width"], cam["res"],
             cam["cm_per_px"]))
    print("body mesh  %s" % d["body_mesh"])
    print()

    m = measure_at_bones(os.path.join(out_dir, d["png_subject"]),
                         os.path.join(out_dir, d["png_plate"]),
                         cam, d.get("bone_world_z") or {})
    for k in ("body_height_cm", "shoulder_band_max_cm", "shoulder_cm",
              "chest_cm", "waist_cm", "hip_cm"):
        v = m.get(k)
        print("  %-22s %s" % (k, "COULD NOT MEASURE" if v is None
                              else "%9.3f cm" % v))
    if m.get("shoulder_over_hip"):
        print("  %-22s %9.4f" % ("shoulder / hip", m["shoulder_over_hip"]))
    print("  %-22s %9.4f" % ("coverage_frac", m["coverage_frac"]))
    m["bone_world_z"] = d.get("bone_world_z")

    rec = {"utc": stamp, "character": args.character,
           "label": args.label or "", "camera": cam,
           "body_mesh": d["body_mesh"],
           "png_subject": d["png_subject"], "png_plate": d["png_plate"],
           "measures": m}
    out = args.out or os.path.join(out_dir, "body_measures.json")
    hist = {"_what": "Body silhouette measurements, orthographic, absolute cm.",
            "runs": []}
    if os.path.isfile(out):
        try:
            with open(out, "r", encoding="utf-8") as fh:
                hist = json.load(fh)
        except Exception:
            pass
    hist.setdefault("runs", []).append(rec)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(hist, fh, indent=1)
        fh.write("\n")
    print()
    print("recorded -> %s" % os.path.relpath(out, REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
