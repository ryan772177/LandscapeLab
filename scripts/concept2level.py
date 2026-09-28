"""concept2level.py — drive one concept recipe from adopted terrain to a lit
UE level and a camera-matched render. THE ORCHESTRATOR INVENTS NOTHING: every
stage is an existing, proven script invoked with its proven arguments, and a
non-zero exit at any stage stops the run cold (fail closed — an unattended
overnight run must never improvise past a refusal).

Stages (--phase offline | editor | all):

  OFFLINE (no editor):
    1 adoption check     heightmap.source hashes to the compositor sidecar
    2 inject_lighting    brief mood -> recipe lighting block
    3 make_layer_weightmap / make_variant_map / make_macro_variation

  EDITOR (one fresh editor per world — create_landscape_from_recipe requires
  a process whose Python namespace has never bound an object):
    4 close any editor   R-EDITOR-CLOSE: dirty census via ue_exec, host-side
                         Content quiet window, CloseMainWindow, wait for
                         exit. REFUSES to kill: if the graceful close is not
                         honoured in 120 s this stops and says so — an
                         unattended kill against a busy editor is the one
                         irreversible move here, so it stays manual.
    5 launch fresh       /Engine/Maps/Entry, -DisablePlugins=MetaHumanGenerator
                         (the engine's own init_unreal binds a global the
                         freshness gate correctly refuses), restore-data
                         moved aside exactly as launch_editor.ps1 does.
    6 create_landscape_from_recipe --go     (first payload, its own gates)
    7 import_layer_textures
    8 make_landscape_material --assign
    9 apply_lighting
   10 save_level --save
   11 shoot.py from brief.render_camera, Z derived from the adopted
      heightmap: world_z_m = px/65535 * z_scale_m + (loc_z_cm - z_scale_cm/2)/100

Camera contract (in the BRIEF):
    "render_camera": {"at_m": [x, y], "height_above_ground_m": 40.0,
                      "pitch_deg": -10.0, "yaw_deg": -90.0, "fov": 70.0}

Exit codes: 0 all stages done; 2 refused (preflight or a stage refused);
4 editor lifecycle failure (close not honoured / init marker never seen).
"""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
UPROJECT = os.path.join(REPO, "LandscapeLab", "LandscapeLab.uproject")
sys.path.insert(0, HERE)
from engine_paths import EDITOR_EXE  # noqa: E402  (env-overridable, engine_paths.py)
LOG = os.path.join(REPO, "LandscapeLab", "Saved", "Logs", "LandscapeLab.log")
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")


class Refuse(Exception):
    pass


def game_view(on):
    """Editor viewport game view: game post-processing (the PPV's manual
    exposure) governs the frame and editor decorations drop out of shots.
    Found 2026-09-01: every shot was +0.2..+0.4 luma over its concept
    because the viewport's exposure override beat the PPV; game view is
    the reflected control (LevelEditorSubsystem.editor_set_game_view)."""
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "ue_exec.py"),
         os.path.join(HERE, "game_view_payload.txt"),
         "--set", "GV=%d" % (1 if on else 0), "--timeout", "25"],
        cwd=HERE, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120)
    ok = '"ok": true' in (r.stdout or "")
    print("== game view %s: %s" % ("ON" if on else "OFF",
                                   "ok" if ok else "FAILED (shot proceeds "
                                   "with editor exposure)"))
    return ok


def run(label, args, timeout=900, ok_exits=(0,)):
    """Run one proven script; an exit outside ok_exits stops the
    orchestrator."""
    print("== %s" % label)
    r = subprocess.run([sys.executable] + args, cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    tail = "\n".join((r.stdout or "").splitlines()[-6:])
    print("   " + tail.replace("\n", "\n   "))
    if r.returncode not in ok_exits:
        raise Refuse("%s exited %d\nstderr tail: %s"
                     % (label, r.returncode, (r.stderr or "")[-400:]))
    if r.returncode != 0:
        print("   (exit %d tolerated for this stage)" % r.returncode)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def editor_pids():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe",
                        "/FO", "CSV", "/NH"], capture_output=True, text=True)
    pids = []
    for line in (r.stdout or "").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0] == "UnrealEditor.exe":
            pids.append(int(parts[1]))
    return pids


def newest_content_age_s():
    newest = 0.0
    for root, _dirs, files in os.walk(CONTENT):
        for f in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, f)))
            except OSError:
                pass
    return time.time() - newest


def close_editor():
    """R-EDITOR-CLOSE, minus the kill (refused unattended)."""
    if not editor_pids():
        print("== close: no editor running")
        return
    print("== close: census")
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "ue_exec.py"),
         os.path.join(HERE, "dirty_package_census_payload.txt"),
         "--timeout", "25"], cwd=HERE, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    if '"clean": true' not in (r.stdout or ""):
        raise Refuse("census not clean (or could not look) — refusing to "
                     "close an editor that may hold unsaved work:\n%s"
                     % (r.stdout or "")[-500:])
    age = newest_content_age_s()
    if age < 120:
        print("   quiet window: newest write %.0f s ago; waiting" % age)
        time.sleep(120 - age)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(Get-Process UnrealEditor).CloseMainWindow()"],
                   capture_output=True, text=True, timeout=60)
    for _ in range(40):
        if not editor_pids():
            print("   closed gracefully")
            return
        time.sleep(3)
    raise Refuse("EDITOR LIFECYCLE: CloseMainWindow not honoured in 120 s. "
                 "Killing unattended is refused (R-EDITOR-CLOSE authorizes "
                 "a kill only after census+quiet, and a human retry comes "
                 "first). Editor left as-is.")


def launch_editor():
    restore = os.path.join(REPO, "LandscapeLab", "Saved", "Autosaves",
                           "PackageRestoreData.json")
    if os.path.isfile(restore):
        dest = os.path.join(REPO, "_trash",
                            "autosaves_c2l_%d" % int(time.time()))
        os.makedirs(dest, exist_ok=True)
        os.replace(restore, os.path.join(dest, "PackageRestoreData.json"))
        print("   restore data moved aside")
    before = time.time()
    subprocess.Popen([EDITOR_EXE, UPROJECT, "/Engine/Maps/Entry", "-log",
                      "-DisablePlugins=MetaHumanGenerator"], cwd=REPO)
    print("== launch: waiting for engine init marker")
    for _ in range(120):
        time.sleep(5)
        try:
            if os.path.getmtime(LOG) < before:
                continue
            with open(LOG, encoding="utf-8", errors="replace") as fh:
                if "Engine Initialization" in fh.read():
                    print("   editor initialized")
                    return
        except OSError:
            continue
    raise Refuse("EDITOR LIFECYCLE: init marker never appeared in 600 s")


def camera_args(recipe, brief):
    cam = brief.get("render_camera")
    if not isinstance(cam, dict):
        raise Refuse("brief has no render_camera object")
    for k in ("at_m", "height_above_ground_m", "pitch_deg", "yaw_deg",
              "fov"):
        if k not in cam:
            raise Refuse("render_camera missing %s" % k)
    ls = recipe["landscape"]
    spacing = float(ls["scale_xy_cm"]) / 100.0
    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    ox = float(ls["location_cm"][0]) / 100.0
    oy = float(ls["location_cm"][1]) / 100.0
    zoff_m = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) \
        / 100.0
    hm = np.asarray(Image.open(os.path.join(
        REPO, recipe["heightmap"]["source"])))
    if hm.dtype != np.uint16:
        raise Refuse("adopted heightmap is not 16-bit")
    x, y = cam["at_m"]
    r0 = int(round((y - oy) / spacing))
    c0 = int(round((x - ox) / spacing))
    if not (0 <= r0 < hm.shape[0] and 0 <= c0 < hm.shape[1]):
        raise Refuse("render_camera.at_m leaves the map")
    ground_m = hm[r0, c0] / 65535.0 * z_scale_m + zoff_m
    z_cm = (ground_m + float(cam["height_above_ground_m"])) * 100.0
    # shoot.py's argparse eats a leading '-' as a flag; its own usage
    # example ships a leading space as the workaround. Same for rot.
    loc = " %.0f,%.0f,%.0f" % (x * 100.0, y * 100.0, z_cm)
    rot = " 0,%s,%s" % (cam["pitch_deg"], cam["yaw_deg"])
    print("== camera: ground %.1f m -> loc %s rot %s" % (ground_m, loc, rot))
    return loc, rot, str(cam["fov"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", required=True, help="repo-relative")
    ap.add_argument("--brief", required=True, help="repo-relative")
    ap.add_argument("--name", required=True,
                    help="shot name, e.g. coast_render")
    ap.add_argument("--outdir", required=True,
                    help="ABSOLUTE dir for the shot (launcher lesson: the "
                         "editor resolves relative paths against itself)")
    ap.add_argument("--phase", choices=("offline", "editor", "relight",
                                        "all"), default="all")
    a = ap.parse_args(argv)

    try:
        rp = os.path.join(REPO, a.recipe)
        with open(rp, encoding="utf-8") as fh:
            recipe = json.load(fh)
        with open(os.path.join(REPO, a.brief), encoding="utf-8") as fh:
            brief = json.load(fh)
        if not os.path.isabs(a.outdir):
            raise Refuse("--outdir must be absolute")
        if os.path.commonprefix([os.path.abspath(a.outdir), REPO + os.sep]) \
                != REPO + os.sep:
            raise Refuse("--outdir must live under REPO_ROOT (the 2026-08-21 "
                         "frames-in-the-engine-install incident)")

        # stage 1: the adopted map must still hash to its producer
        side_p = os.path.join(REPO, recipe["stamps"]["output"]
                              + ".stamps.json")
        with open(side_p, encoding="utf-8") as fh:
            want = json.load(fh)["output_sha256"]
        got = sha256_file(os.path.join(REPO, recipe["heightmap"]["source"]))
        if got != want:
            raise Refuse("adoption hash mismatch: %s vs sidecar %s"
                         % (got[:16], want[:16]))
        print("== adoption verified %s" % got[:16])

        loc, rot, fov = camera_args(recipe, brief)  # validate BEFORE editor

        if a.phase in ("offline", "all"):
            img = os.path.join(REPO, brief["source_image"]) \
                if not os.path.isabs(brief["source_image"]) \
                else brief["source_image"]
            run("inject_lighting", ["inject_lighting.py", "--brief",
                os.path.join(REPO, a.brief), "--recipe", rp, "--image", img])
            run("layer weightmap", ["make_layer_weightmap.py", "--recipe",
                                    rp])
            run("variant map", ["make_variant_map.py", "--recipe", rp])
            run("macro variation", ["make_macro_variation.py", "--recipe",
                                    rp])

        if a.phase == "relight":
            # Lighting/camera iteration on the ALREADY-BUILT level in the
            # ALREADY-OPEN editor. inject first so the recipe carries the
            # new mood; apply_lighting's own level gate protects against
            # the wrong level being loaded.
            img = os.path.join(REPO, brief["source_image"]) \
                if not os.path.isabs(brief["source_image"]) \
                else brief["source_image"]
            run("inject_lighting", ["inject_lighting.py", "--brief",
                os.path.join(REPO, a.brief), "--recipe", rp, "--image", img])
            loc, rot, fov = camera_args(recipe, brief)
            run("apply lighting", ["apply_lighting.py", "--recipe", rp,
                                   "--timeout", "25"], timeout=600)
            # exit 6 = "nothing in the allow-list was dirty": for a relight
            # iteration the SHOT is the product and the recipe is the
            # persistent truth, so an empty save is a warning, not a stop
            run("save level", ["save_level.py", "--recipe", rp,
                               "--timeout", "25", "--save"], timeout=900,
                ok_exits=(0, 6))
            game_view(True)
            try:
                run("shoot", ["shoot.py", "--name", a.name, "--loc", loc,
                              "--rot", rot, "--fov", fov, "--outdir",
                              a.outdir], timeout=900)
            finally:
                game_view(False)
            print("DONE (relight): %s" % a.name)
            return 0

        if a.phase in ("editor", "all"):
            close_editor()
            launch_editor()
            # audit F1: children run with cwd=scripts/ and resolve --recipe
            # against THEIR cwd; pass the absolute path, never the
            # repo-relative one
            run("create landscape", ["create_landscape_from_recipe.py",
                "--recipe", rp, "--material",
                recipe["material"]["parent_material"], "--timeout", "25",
                "--go"], timeout=1200)
            run("import layer textures", ["import_layer_textures.py",
                "--recipe", rp, "--timeout", "25"], timeout=900)
            run("build material", ["make_landscape_material.py", "--recipe",
                rp, "--timeout", "25", "--assign"], timeout=1200)
            run("apply lighting", ["apply_lighting.py", "--recipe", rp,
                                   "--timeout", "25"], timeout=600)
            run("save level", ["save_level.py", "--recipe", rp,
                               "--timeout", "25", "--save"], timeout=900)
            game_view(True)
            try:
                run("shoot", ["shoot.py", "--name", a.name, "--loc", loc,
                              "--rot", rot, "--fov", fov, "--outdir",
                              a.outdir], timeout=900)
            finally:
                game_view(False)
        print("DONE: %s" % a.name)
        return 0
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 4 if "EDITOR LIFECYCLE" in str(e) else 2
    except subprocess.TimeoutExpired as e:
        print("REFUSE: stage timed out: %r — editor left as-is" % e)
        return 2
    except (KeyError, ValueError, OSError) as e:
        print("REFUSE: unreadable inputs: %r" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
