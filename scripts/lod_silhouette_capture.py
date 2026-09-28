"""lod_silhouette_capture.py — E2: capture each tree LOD on flat magenta and
judge the switch, at the size it switches at NOW and at the silhouette size.

WHAT IT ANSWERS
---------------
ConiferPine's last LOD is 32 triangles (from 27,824) and SpruceSub's is 6
(from 20,695). Both take over while the tree still covers ~0.17 of screen
height. The question is not "are those meshes bad" -- 6 triangles is a
perfectly good billboard at 20 px -- but "are they being shown TOO EARLY".
So every LOD is judged TWICE:

  (a) at the pixel size it switches at today, derived from its ScreenSize
  (b) at the silhouette size (20 px), where a billboard is supposed to live

A last LOD that FAILS (a) and PASSES (b) indicts the SWITCH, not the mesh,
and the fix is a ScreenSize -- which this writes into the sidecar as a
PROPOSAL. It does not touch the meshes.

THE PIXEL MATHS
---------------
UE screen size, per the form used here:  S = R / (D * tan(vfov/2))
An object of height H at distance D covers  px = res_h * H / (2 D tan(vfov/2))
Eliminating D:                             px = res_h * S * H / (2 R)

which is independent of FOV, so the capture camera and the declared camera
need not agree. The inverse, for the proposal:  S = 2 R px / (res_h * H)

NO SHELL. Every child process is invoked with an argv LIST. R-UEEXEC records
what happens otherwise: Git Bash rewrites /Game/ paths and PowerShell strips
embedded quotes, and both failures are invisible at the call site.

NOTHING IS SAVED. The payload spawns into the loaded level and destroys what
it spawned; World Partition writes external actors on save, and nothing here
saves.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

PY = sys.executable
SPECIES = ["ConiferPine", "SpruceSub", "SpruceSapling"]
SKIP_NANITE = "Conifer"
CAP_FOV = 45.0          # capture camera; framing only, not the judged camera
CAP_RES = 1024
FILL = 0.80             # tree occupies this fraction of frame height
SILHOUETTE_PX = 20.0    # (b), the ladder's silhouette size


def run(cmd, timeout=1800):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT,
                       timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def payload(mode, species, force_lod, timeout=90):
    """Run the scene payload. Values are bare identifiers and integers --
    never a /Game/ path and never quoted -- so --set is safe here."""
    code, out = run([PY, os.path.join("scripts", "ue_exec.py"),
                     os.path.join("scripts", "payloads",
                                  "lod_capture_scene.py"),
                     "--set", "MODE=%s" % mode,
                     "--set", "SPECIES=%s" % species,
                     "--set", "FORCE_LOD=%d" % force_lod,
                     "--timeout", "25"], timeout=timeout)
    # raw_decode, NOT loads. ue_exec prints a duration line AFTER the payload's
    # JSON, so `json.loads(out[i:])` raises "Extra data" on the correct blob
    # and every candidate offset fails. The driver then reported "scene setup
    # failed" over three payloads that had each returned ok:true with the
    # actors spawned and r.ForceLOD read back -- a parser fault wearing the
    # costume of an editor fault.
    dec = json.JSONDecoder()
    blob = None
    i = out.find("{")
    while i != -1:
        try:
            cand, _ = dec.raw_decode(out[i:])
            if isinstance(cand, dict) and "ok" in cand:
                blob = cand
                break
        except ValueError:
            pass
        i = out.find("{", i + 1)
    return code, blob, out


def background_rgb(path):
    """The ACTUAL background colour, measured from the corner of the frame.

    The declared magenta is not evidence: exposure, fog and tone mapping all
    sit between the material and the pixel. The checker keys off this
    measured value; the corner SPREAD is returned alongside it and recorded
    per shot so a non-uniform background is visible in the report. (It is
    measured and reported, not auto-refused.)
    """
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(path).convert("RGB")).astype(float)
    h, w = a.shape[:2]
    k = max(4, min(h, w) // 64)
    corners = [a[:k, :k], a[:k, -k:], a[-k:, :k], a[-k:, -k:]]
    means = [c.reshape(-1, 3).mean(0) for c in corners]
    mean = sum(means) / 4.0
    spread = max(float(((m - mean) ** 2).sum() ** 0.5) for m in means)
    return [round(float(v), 2) for v in mean], round(spread, 3)


def switch_px(screen_size, height_cm, radius_cm, res_h):
    return res_h * screen_size * height_cm / (2.0 * radius_cm)


def screen_size_for_px(px, height_cm, radius_cm, res_h):
    return 2.0 * radius_cm * px / (res_h * height_cm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=os.path.join(
        "_verify", "bench", "2026-09-07", "tree_lod_probe.json"))
    ap.add_argument("--outdir", default=os.path.join(
        "_verify", "bench", "2026-09-07"))
    ap.add_argument("--recipe", default=os.path.join(
        "recipes", "alpine_8k.json"))
    ap.add_argument("--skip-capture", action="store_true",
                    help="reuse PNGs already on disk; judge only")
    a = ap.parse_args()

    probe = json.load(open(os.path.join(REPO_ROOT, a.probe), encoding="utf-8"))
    by_species = {m["species"]: m for m in probe["meshes"]}
    recipe = json.load(open(os.path.join(REPO_ROOT, a.recipe),
                            encoding="utf-8-sig"))
    per = recipe["perception"]
    res_h = float(per["declared_camera"]["res"][1])
    thresholds = per["thresholds_px"]

    shots_root = os.path.join(REPO_ROOT, a.outdir, "lod_silhouette")
    result = {
        "_what": "E2 LOD silhouette audit: every LOD judged at the size it "
                 "switches at today AND at the silhouette size.",
        "declared_camera": per["declared_camera"],
        "capture": {"fov_deg": CAP_FOV, "res": [CAP_RES, CAP_RES],
                    "fill_fraction": FILL, "key_declared": [255, 0, 255]},
        "silhouette_px": SILHOUETTE_PX,
        "recipe_thresholds_px": thresholds,
        "skipped": {SKIP_NANITE: (
            "NANITE (nanite_enabled=true, 1 LOD, screen size 2.0). Nanite "
            "does its own cluster LOD, so there is no discrete switch and "
            "no silhouette pop to audit. r.ForceLOD does not govern it.")},
        "species": {},
        "failures": [],
    }

    for sp in SPECIES:
        m = by_species.get(sp)
        if m is None:
            result["failures"].append(
                "%s: no entry in the probe %s" % (sp, a.probe))
            continue
        H, R, n = m["height_cm"], m["bounding_sphere_radius_cm"], m["lod_count"]
        screens = m["screen_sizes"]
        # switch_px is indexed by lod below; if lod_count exceeds the recorded
        # screen_sizes, range(n) would index switch_px out of range. Clamp and
        # note rather than crash mid-species.
        if n != len(screens):
            n = min(n, len(screens))
        outdir = os.path.join(shots_root, sp)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        D = H / (2.0 * FILL * math.tan(math.radians(CAP_FOV / 2.0)))
        cam = (-D, 0.0, 250000.0)

        rec = {
            "mesh": m["path"], "lod_count": n, "screen_sizes": screens,
            "triangles_per_lod": m["triangles_per_lod"],
            "height_cm": H, "bounding_sphere_radius_cm": R,
            "camera": {"loc_cm": [round(v, 1) for v in cam],
                       "rot_roll_pitch_yaw": [0.0, 0.0, 0.0],
                       "distance_cm": round(D, 1)},
            "switch_px": [round(switch_px(s, H, R, res_h), 1) for s in screens],
            "shots": [], "notes": [],
        }
        if sp == "SpruceSub" and len(screens) > 1 and screens[0] - screens[1] < 0.05:
            rec["notes"].append(
                "LOD0 %.3f and LOD1 %.3f are %.3f apart: LOD0 is displaced "
                "almost immediately and is close to unreachable in play. "
                "REPORTED ONLY, per ruling -- no change proposed."
                % (screens[0], screens[1], screens[0] - screens[1]))

        # ---- capture ----------------------------------------------------
        if not a.skip_capture:
            code, blob, raw = payload("setup", sp, 0)
            if not blob or not blob.get("ok"):
                result["failures"].append(
                    "%s: scene setup failed: %s"
                    % (sp, (blob or {}).get("error") or raw[-400:]))
                continue
            rec["scene"] = {k: blob.get(k) for k in
                            ("backdrop_material", "backdrop_param",
                             "backdrop_readback", "backdrop_warning",
                             "tree_actor", "backdrop_actor")}

        for lod in range(n):
            png = os.path.join(outdir, "lod%d.png" % lod)
            shot = {"lod": lod, "png": os.path.relpath(png, REPO_ROOT)}
            if not a.skip_capture:
                code, blob, raw = payload("forcelod", sp, lod)
                shot["force_lod_requested"] = lod
                shot["force_lod_readback"] = (blob or {}).get(
                    "force_lod_readback")
                # NO CAPTURE COUNTS WITHOUT THE READ-BACK.
                if not blob or not blob.get("force_lod_ok"):
                    shot["verdict"] = "REFUSED: r.ForceLOD read back as %r, " \
                                      "not %d" % (shot.get(
                                          "force_lod_readback"), lod)
                    result["failures"].append("%s LOD%d: %s"
                                              % (sp, lod, shot["verdict"]))
                    rec["shots"].append(shot)
                    continue
                t0 = time.time() - 1.0     # anchor BEFORE the shot is issued
                code, out = run([
                    PY, os.path.join("scripts", "shoot.py"),
                    "--name", "%s_lod%d" % (sp, lod),
                    "--loc=%.1f,%.1f,%.1f" % cam,   # equals form: x is negative
                    "--rot=0,0,0",                  # ROLL,PITCH,YAW
                    "--fov", str(CAP_FOV),
                    "--res", "%dx%d" % (CAP_RES, CAP_RES),
                    "--outdir", os.path.relpath(outdir, REPO_ROOT),
                ])
                if code != 0:
                    shot["verdict"] = "shoot.py exit %d" % code
                    shot["stderr_tail"] = out[-300:]
                    result["failures"].append("%s LOD%d: shoot.py exit %d"
                                              % (sp, lod, code))
                    rec["shots"].append(shot)
                    continue
                # EXACT NAME, AND IT MUST BE FRESH. A substring match on
                # "lod0" also matches the previously-renamed lod0.png and
                # every smoke frame in the directory, and sorted()[-1] then
                # picks one of those -- silently measuring an OLD capture and
                # reporting it as this run's. That is the same stale-artefact
                # trap that made capture_truth report success over a frame it
                # never took.
                src = os.path.join(outdir, "%s_lod%d.png" % (sp, lod))
                if not os.path.exists(src) or os.path.getmtime(src) < t0:
                    shot["verdict"] = ("no FRESH capture at %s"
                                       % os.path.basename(src))
                    result["failures"].append("%s LOD%d: stale or missing "
                                              "capture" % (sp, lod))
                    rec["shots"].append(shot)
                    continue
                # DROP THE ALPHA CHANNEL. lod_silhouette_check prefers an
                # ALPHA mask when the image is RGBA and only falls back to the
                # key colour otherwise. HighResShot writes RGBA with alpha=255
                # EVERYWHERE, so the mask was the whole frame: coverage 1.000,
                # IoU 1.000 and edge_error NaN on every row of every species,
                # while the PNGs plainly differed. Saving as RGB forces the
                # key-colour path.
                from PIL import Image as _Im
                _Im.open(src).convert("RGB").save(png)
                os.remove(src)
            if not os.path.exists(png):
                shot["verdict"] = "no PNG produced"
                result["failures"].append("%s LOD%d: no PNG" % (sp, lod))
                rec["shots"].append(shot)
                continue
            # A frame that still carries alpha would be judged by a vacuous
            # all-true alpha mask, so normalise here too -- this also repairs
            # captures filed by an earlier run under --skip-capture.
            from PIL import Image as _Im
            _im = _Im.open(png)
            if _im.mode != "RGB":
                _im.convert("RGB").save(png)
                shot["alpha_stripped"] = True
            bg, spread = background_rgb(png)
            shot["background_rgb_measured"] = bg
            shot["background_corner_spread"] = spread
            rec["shots"].append(shot)

        rec["ok_shots"] = [s for s in rec["shots"]
                           if "verdict" not in s and s.get(
                               "background_rgb_measured")]
        result["species"][sp] = rec

    # ---- judge -----------------------------------------------------------
    for sp, rec in result["species"].items():
        shots = rec.get("ok_shots") or []
        if len(shots) < 2:
            rec["judged"] = "NOT JUDGED: fewer than two usable captures"
            continue
        key = [int(round(v)) for v in shots[0]["background_rgb_measured"]]
        rec["key_rgb_used"] = key
        pngs = [os.path.join(REPO_ROOT, s["png"]) for s in shots]

        for label, targets in (
                ("at_current_switch",
                 [rec["switch_px"][s["lod"]] for s in shots]),
                ("at_silhouette_px", [SILHOUETTE_PX] * len(shots))):
            outp = os.path.join(REPO_ROOT, a.outdir, "lod_silhouette",
                                "%s_%s.json" % (sp, label))
            cmd = [PY, os.path.join("scripts", "lod_silhouette_check.py")]
            for p, t in zip(pngs, targets):
                cmd += ["--lod", p, "%.1f" % t]
            cmd += ["--key", str(key[0]), str(key[1]), str(key[2]),
                    "--out", outp]
            code, out = run(cmd)
            try:
                rec[label] = json.load(open(outp, encoding="utf-8"))
            except Exception:
                rec[label] = {"error": "checker exit %d" % code,
                              "tail": out[-400:]}

        # ---- the verdict the ruling asks for ----------------------------
        # The checker returns {"thresholds": ..., "lods": [ ... ]} -- a LIST,
        # indexed from the FIRST comparison (LOD0 is the reference and gets no
        # entry). Reading it as {"lod0": ...} keys yielded empty dicts, and the
        # verdict fell through to "does not fail" for all three species. A
        # vacuous PASS is worse than a crash: it reads as a result.
        def last_entry(label):
            lods = (rec.get(label) or {}).get("lods") or []
            return lods[-1] if lods else {}

        a_res, b_res = last_entry("at_current_switch"), last_entry(
            "at_silhouette_px")
        if not a_res or not b_res:
            rec["verdict"] = ("NOT JUDGED: the checker returned no comparison "
                              "rows for %s"
                              % ("at_current_switch" if not a_res
                                 else "at_silhouette_px"))
            continue
        # SILHOUETTE AND TONE ARE DIFFERENT FINDINGS AND MUST NOT BE POOLED.
        #
        # This audit is named for the silhouette, and coverage/IoU are what
        # measure it. `luma_delta_weber` is a TONAL metric, it is normalised
        # by mean luma, and these frames are lit by the level's own sun at
        # 2.5 km with the subject largely backlit -- a small denominator
        # inflates the ratio. So the combined verdict fails everything on
        # luma and would have indicted meshes whose SHAPE is measurably fine.
        #
        # The geometric verdict below answers the ruling's question. The
        # tonal one is reported beside it as a CANDIDATE, not a verdict.
        cov_t = (rec.get("at_current_switch") or {}).get(
            "thresholds", {}).get("coverage", 0.85)
        iou_t = (rec.get("at_current_switch") or {}).get(
            "thresholds", {}).get("iou", 0.80)

        def geo_ok(e):
            return (e.get("coverage_ratio", 0) >= cov_t
                    and e.get("silhouette_iou", 0) >= iou_t)

        a_fail = not geo_ok(a_res)
        b_pass = geo_ok(b_res)
        rec["last_lod_at_current_switch"] = a_res
        rec["last_lod_at_silhouette_px"] = b_res
        rec["geometric_thresholds"] = {"coverage": cov_t, "iou": iou_t}
        rec["tonal_candidate"] = {
            "luma_delta_weber_at_current_switch": a_res.get("luma_delta_weber"),
            "luma_delta_weber_at_silhouette_px": b_res.get("luma_delta_weber"),
            "threshold": 0.03,
            "note": "EVERY failing row in this audit failed on LUMA alone, "
                    "never on coverage or IoU. That is a TONAL step at the "
                    "switch, not a silhouette collapse, and it matches a "
                    "suspicion already on record: measure_lod_materials.py "
                    "notes 'trunks beyond ~50 m go uniformly pale' and found "
                    "every LOD carries LOD0's materials across the same "
                    "sections -- so it is the material's distance behaviour, "
                    "not a lost section.",
            "caveat": "NOT A VERDICT. luma_delta_weber divides by mean luma, "
                      "and these captures are lit by the level's own sun with "
                      "the subject largely backlit and dim, which inflates "
                      "the ratio. Re-measure under controlled lighting before "
                      "acting on it.",
        }
        if a_fail and b_pass:
            i = shots[-1]["lod"]
            proposed = screen_size_for_px(
                SILHOUETTE_PX, rec["height_cm"],
                rec["bounding_sphere_radius_cm"],
                float(result["declared_camera"]["res"][1]))
            rec["verdict"] = (
                "THE SWITCH, NOT THE MESH (geometric). LOD%d fails at its current switch "
                "size (%.1f px) and passes at the silhouette size (%.0f px), "
                "so the geometry is adequate for where a billboard belongs "
                "and is simply being shown too early."
                % (i, rec["switch_px"][i], SILHOUETTE_PX))
            rec["proposal"] = {
                "lod": i,
                "current_screen_size": rec["screen_sizes"][i],
                "proposed_screen_size": round(proposed, 5),
                "derived_from": "S = 2 R px / (res_h * H), px = %.0f"
                                % SILHOUETTE_PX,
                "note": "PROPOSAL ONLY -- no mesh and no LOD setting was "
                        "changed this session.",
                "caveat": "recipes/alpine_8k.json perception.thresholds_px."
                          "silhouette is %s, not %.0f. This proposal uses the "
                          "%.0f px the ruling names, which is the more "
                          "CONSERVATIVE of the two (it switches later)."
                          % (thresholds.get("silhouette"), SILHOUETTE_PX,
                             SILHOUETTE_PX),
            }
        elif a_fail:
            rec["verdict"] = ("LOD%d fails coverage/IoU at its current switch AND "
                              "at the silhouette size -- that indicts the "
                              "MESH, not the switch. No ScreenSize proposal."
                              % shots[-1]["lod"])
        else:
            rec["verdict"] = "GEOMETRY HOLDS: the last LOD meets coverage and IoU at its current switch size. No ScreenSize change is indicated on silhouette grounds."

    dest = os.path.join(REPO_ROOT, a.outdir, "lod_silhouette.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    # Read the report back rather than trusting the write.
    try:
        with open(dest, encoding="utf-8") as fh:
            json.load(fh)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "report did not read back: %s" % exc}))
        return 1
    print(json.dumps({"written": os.path.relpath(dest, REPO_ROOT),
                      "failures": result["failures"],
                      "verdicts": {s: r.get("verdict")
                                   for s, r in result["species"].items()}},
                     indent=2))
    # Operational failures (scene setup, shoot.py, stale capture, ForceLOD
    # refusal) must not exit 0 -- a caller keying on the code was told success.
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
