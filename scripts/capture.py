"""capture.py — recipe-driven high-res screenshot capture.

Exists so pipeline rule 4 ("After any scene change: run
scripts/capture.py") is satisfiable rather than perpetually flagged as a
gap. (The rule once also required a one-line LESSONS.md note; the live
CLAUDE.md dropped that clause — noting the capture in LESSONS is this
script's suggestion now, not law.)

SCENE MUTATION, narrowly. It spawns or reuses ONE CameraActor per recipe
camera and sets its transform from the recipe. It touches nothing else:
no landscape, no materials, no lighting, no level save. Cameras are
addressed by a deterministic label derived from the recipe, so re-running
moves the existing camera rather than accumulating duplicates
(hard rule 3).

Conduct rule 7 is delegated to bootstrap.py's audited gate. Nothing
reaches a node that has not matched UE_PROJECT_ROOT.

FILENAMES
  <biome_id>__<camera>__<UTC timestamp>__<git short hash><-dirty>.png
Written under `capture.output_dir` from the recipe, which the schema
requires to resolve inside captures/. The commit hash ties an image to
the exact repo state that produced it; `-dirty` marks an uncommitted
tree, because an image from uncommitted work is not reproducible and
should say so. The timestamp is UTC so captures sort chronologically
regardless of local clock changes.

WHY CAMERAS ARE ACTORS, NOT JUST A VIEW
`take_high_res_screenshot` captures the active viewport. Driving the
viewport camera directly would make captures depend on wherever the
editor camera happened to be. Spawning a deterministic CameraActor and
piloting the viewport to it makes the framing a property of the recipe,
which is the whole point — captures must be comparable across runs.

HOST SUSPENSION (added 2026-08-01)
A capture run holds a Windows sleep inhibitor for its duration and
measures its timeouts in editor time rather than wall-clock time. Both
exist because a run that looked like a rendering collapse — 1h49m and
6h51m between shots — was the laptop entering Modern Standby. See
_SleepGuard and SUSPEND_GAP_S for the evidence.

Exit codes:
  0  all requested captures written
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  camera setup or screenshot request failed in the editor
     (takes precedence over 5 when both kinds of failure occur)
  5  screenshot requested successfully but the file never appeared
  6  a pre-capture gate refused. Two distinct causes share this code:
     (a) the LEVEL gate — the editor has a different level open than
         `landscape.level_path`; or
     (b) the World Partition RESIDENCY gate — the terrain on disk could
         not be confirmed fully loaded, and capturing would record holes
         silently.
     Both print which one refused. (verify_landscape.py splits these into
     6 and 7 because 6 already means INCOMPLETE there; exit codes are a
     per-script contract, not a shared table.)

Unreal APIs used (long-stable for UE5 except where flagged):
  unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
      .get_editor_world / .set_level_viewport_camera_info
  unreal.EditorActorSubsystem.spawn_actor_from_class
  unreal.GameplayStatics.get_all_actors_of_class / unreal.CameraActor
  unreal.WorldPartitionBlueprintLibrary.get_actor_descs / load_actors
      (FActorDesc.NativeClass and .Guid are BlueprintReadOnly —
      WorldPartitionBlueprintLibrary.h:31-37)
  unreal.AutomationLibrary.take_high_res_screenshot(..., camera=)
      (5.8 signature returns a UAutomationEditorTask, not a bool —
      AutomationBlueprintFunctionLibrary.h:143. The `camera` argument is
      what makes the engine pilot the viewport to the CameraActor for
      the shot, and therefore what makes fov_deg govern the framing;
      see the payload note below.)
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import landscape_spec     # noqa: E402 — shared recipe loading
import verify_landscape   # noqa: E402 — shared node selection

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
CAPTURES_ROOT = os.path.join(REPO_ROOT, "captures")
PROBE_MARKER = "__LANDSCAPELAB_CAPTURE__"

# How long to wait for the engine to flush a screenshot to disk.
#
# 120 s was WRONG and cost a false failure report. Evidence, from the
# 2026-07-31 run stamped 20260731T221353Z: that stamp is the RUN-START
# time shared by every filename in a run, not the per-capture request
# time. ridge_wide ran first and burned its full 120 s; the saved
# capture (snowline_detail) was therefore requested at ~22:16, and the
# engine logged "High resolution screenshot saved as ..." for it at
# 22:23:47 — a draw stalled ~8 minutes past its own request (~10 past
# run start), ~6 minutes after the script had already given up and
# declared the run a regression. The file was fine; the wait was not.
#
# Cause: assigning a freshly-created material triggers shader
# compilation (that run translated 246 materials), and on Software Lumen
# with an integrated GPU that stalls the draw the screenshot is waiting
# on. Any run that follows a material change should expect minutes, not
# seconds. 900 s is ~2x the observed worst-case stall.
#
# The engine-side task poll is the real signal — this ceiling only
# bounds a genuinely hung editor (worst case 15 min per camera; the
# conduct-rule-6 stop caps a run at two such failures).
SCREENSHOT_TIMEOUT_S = 900.0
POLL_INTERVAL_S = 1.0

# Warn once the wait exceeds this, so a long wait reads as "probably
# compiling shaders" rather than "hung".
SLOW_CAPTURE_NOTICE_S = 90.0

# --- Host suspension ---------------------------------------------------
#
# THE 2026-08-01 "CAPTURE THROUGHPUT COLLAPSE" WAS THE MACHINE SLEEPING.
# The run stamped 20260801T083731Z appeared to take hours per shot:
# ridge_wide landed 10 minutes after its request, diag_oblique 1h49m
# after, diag_topdown 6h51m after, and snowline_detail never. Nothing was
# slow. The editor was not running.
#
# Proof is the engine's own frame counter, the number in the second
# bracket of every log line. LandscapeLab.log:
#   [2026.08.01-08.48.00:504][842]  last line before the gap
#   [2026.08.01-10.36.04:091][843]  first line after it
# ONE frame in 108 minutes. A throttled-but-awake editor still ticks at
# 3-4 FPS (~25,000 frames over that span), and the DDC and EOS timers
# stalled with it. Windows agrees: Kernel-Power event 507 "The system is
# exiting Modern Standby" at 03:36:04 and 10:27:44 local, which are
# 10:36:04Z and 17:27:44Z — each within seconds of a screenshot finally
# being written. The shots completed on RESUME, in order, exactly as a
# suspended process would.
#
# Two consequences, both handled here:
#
# 1. A capture run must not let the host idle-sleep out from under it.
#    _SleepGuard asks Windows to keep the system up for the duration.
#    This is a per-process runtime request, not a machine setting: it is
#    released on exit and changes nothing on disk (conduct rule 1).
#
# 2. time.time() keeps advancing across a suspend, so the 900 s ceiling
#    expired during standby and the run was declared a failure while the
#    engine went on to write three of the four files hours later. The
#    wait now detects the suspend and does not charge it to the timeout —
#    the ceiling is meant to bound a hung EDITOR, and an editor that is
#    not being scheduled at all has not hung.
#
# A gap between poll iterations this far above POLL_INTERVAL_S cannot be
# ordinary scheduling jitter on an otherwise idle loop; it means this
# process was not running. 30 s is ~30x the poll interval and well under
# the shortest standby transition observed.
SUSPEND_GAP_S = 30.0

# winbase.h. ES_CONTINUOUS makes the request STICKY for this thread until
# it is cleared with a bare ES_CONTINUOUS; without it the flags apply to
# one idle-timer reset only.
#
# ES_DISPLAY_REQUIRED IS NOT BELT-AND-BRACES ON THIS HOST — do not
# "simplify" it away. The observed failure was MODERN STANDBY (S0 low
# power idle, Kernel-Power 507), not classic S3 sleep, and the two are
# entered by different paths: Modern Standby follows the screen turning
# off. ES_SYSTEM_REQUIRED resets the system idle timer, which is the S3
# path; ES_DISPLAY_REQUIRED is what keeps the panel on and therefore
# what keeps the machine out of the transition actually observed here.
# Dropping the display flag would most likely remove the half of this
# request that does the work, and the symptom (a capture run that
# silently pauses for hours) takes hours to reproduce.
# Maturity: SetThreadExecutionState is Win32, stable since XP; no UE
# involvement and nothing version-gated.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class _SleepGuard:
    """Ask Windows not to idle-sleep while captures are outstanding.

    Reports what it actually achieved rather than assuming. A rejected
    request (return value 0) is reported as rejected, not silently
    treated as held — "I could not look" is not "yes" (lesson 2.10), and
    the whole point is that a future unexplained multi-hour gap should be
    attributable.

    LIMITS, stated because they are the ones that will bite: this blocks
    the IDLE path to sleep only. A lid close, a user-initiated sleep, or
    battery-critical hibernation still suspends the host, and the wait
    below is what covers those.

    "held" MEANS THE REQUEST WAS ACCEPTED, NOT THAT SLEEP DID NOT HAPPEN.
    The four states are reported distinctly on purpose — never asked
    ("not requested"), asked and refused ("Windows REJECTED"), could not
    ask ("not a Windows host" / "request failed"), and accepted ("held")
    — so that a future unexplained gap can be attributed rather than
    guessed at. If a run ever prints "held" AND the wait below reports a
    suspend, that combination is itself the finding: the inhibitor was
    accepted and the host suspended anyway. Record it; do not assume the
    guard is working because it said "held".
    """

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.held = False
        self.detail = "not requested"

    def acquire(self):
        """Request the inhibitor. Never raises; records what happened."""
        if not self.enabled:
            self.detail = "NOT held — disabled by --allow-sleep"
            return self
        if sys.platform != "win32" or not hasattr(ctypes, "windll"):
            self.detail = "NOT held — not a Windows host"
            return self
        try:
            fn = ctypes.windll.kernel32.SetThreadExecutionState
            fn.argtypes = [ctypes.c_uint]
            fn.restype = ctypes.c_uint
            prev = fn(ctypes.c_uint(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED))
        except Exception as exc:
            self.detail = "NOT held — request failed ({0}: {1})".format(
                type(exc).__name__, exc)
            return self
        if prev == 0:
            self.detail = ("NOT held — Windows REJECTED the request "
                           "(SetThreadExecutionState returned 0)")
            return self
        self.held = True
        self.detail = "held (system + display) for this process only"
        return self

    def release(self):
        """Clear the inhibitor. Safe to call when nothing was held.

        A bare ES_CONTINUOUS is the documented way to drop a sticky
        request; it must run on the SAME thread that made it, which is
        why both calls live on the host's main thread.
        """
        if self.held:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ctypes.c_uint(ES_CONTINUOUS))
            except Exception:
                pass
            self.held = False


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def git_stamp():
    """Return '<shorthash>' or '<shorthash>-dirty', or 'nogit'."""
    try:
        head = subprocess.run(
            ["git", "-C", REPO_ROOT, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=15)
        if head.returncode != 0:
            return "nogit"
        stamp = head.stdout.strip()
        status = subprocess.run(
            ["git", "-C", REPO_ROOT, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15)
        if status.returncode == 0 and status.stdout.strip():
            stamp += "-dirty"
        return stamp
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def validate_capture(recipe):
    """Validate the capture block. Returns (config, errors)."""
    errors = []
    # biome_id becomes part of every capture FILENAME and actor label.
    # schema.md requires ^[a-z][a-z0-9_]*$; enforcing it HERE is what keeps
    # path separators and '..' out of the os.path.join in main() — without
    # this, a recipe could steer the engine's PNG write outside the
    # validated output_dir (conduct rule 1).
    biome = recipe.get("biome_id")
    if not isinstance(biome, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", biome):
        return None, ["biome_id must match ^[a-z][a-z0-9_]*$ — it becomes "
                      "part of filenames and actor labels; got "
                      "{0!r}".format(biome)]
    cap = recipe.get("capture")
    if not isinstance(cap, dict):
        return None, ["recipe has no 'capture' object"]

    out = cap.get("output_dir")
    if not isinstance(out, str) or not out:
        return None, ["capture.output_dir must be a non-empty string"]
    resolved = os.path.join(REPO_ROOT, out)
    captures_norm = _norm(CAPTURES_ROOT)
    if _norm(resolved) != captures_norm and not _norm(resolved).startswith(
            captures_norm + os.sep):
        return None, ["capture.output_dir must resolve inside captures/, "
                      "got {0!r}".format(out)]

    res = cap.get("resolution")
    if not (isinstance(res, list) and len(res) == 2 and
            all(isinstance(v, int) and not isinstance(v, bool) and v > 0
                for v in res)):
        errors.append("capture.resolution must be [width, height] "
                      "positive ints")

    cams = cap.get("cameras")
    if not isinstance(cams, list) or not cams:
        errors.append("capture.cameras must be a non-empty array")
        cams = []

    seen, clean = set(), []
    for i, cam in enumerate(cams):
        tag = "capture.cameras[{0}]".format(i)
        if not isinstance(cam, dict):
            errors.append("{0} must be an object".format(tag))
            continue
        name = cam.get("name")
        if not isinstance(name, str) or not name:
            errors.append("{0}.name must be a non-empty string".format(tag))
            continue
        # Filenames are built from this; keep it filesystem-safe and
        # deterministic rather than sanitising silently.
        if not all(c.isalnum() or c in "_-" for c in name):
            errors.append("{0}.name {1!r} must be alphanumeric, '_' or "
                          "'-' — it becomes a filename".format(tag, name))
        if name in seen:
            errors.append("{0}.name {1!r} is duplicated; captures would "
                          "overwrite each other".format(tag, name))
        seen.add(name)

        loc, rot = cam.get("location_cm"), cam.get("rotation_deg")
        for key, val in (("location_cm", loc), ("rotation_deg", rot)):
            # isfinite: json.load accepts the non-standard literals
            # NaN/Infinity, and repr(nan) is a bare name that would break
            # the interpolated payload (landscape_spec.py finding L2).
            if not (isinstance(val, list) and len(val) == 3 and
                    all(isinstance(v, (int, float))
                        and not isinstance(v, bool)
                        and math.isfinite(v) for v in val)):
                errors.append("{0}.{1} must be three finite numbers".format(
                    tag, key))
        fov = cam.get("fov_deg")
        if not isinstance(fov, (int, float)) or isinstance(fov, bool) \
                or not (1.0 <= fov <= 170.0):
            errors.append("{0}.fov_deg must be a number in [1, 170]".format(
                tag))
        clean.append({"name": name, "location": loc, "rotation": rot,
                      "fov": fov})

    errors.extend(_footprint_errors(recipe, clean))
    alt_errors, alt_warnings = _altitude_findings(recipe, clean, res)
    errors.extend(alt_errors)

    if errors:
        return None, errors
    return {"biome_id": biome, "output_dir": resolved, "resolution": res,
            "cameras": clean, "warnings": alt_warnings}, []


# Warn when the provable upper bound on a frame's terrain content falls
# below this.
#
# CALIBRATED SO IT DOES NOT FIRE ON A SKY-HEAVY SHOT THAT IS MEANT TO BE
# SKY-HEAVY. The bound is loose — it assumes ground at the world ceiling
# at maximum range — so a legitimate wide establishing frame scores low
# on it. `ridge_wide` is deliberately 32% terrain and bounds at 58%; at
# a 0.60 threshold this warned about a camera that was framed exactly as
# intended, which is the wrong-reason firing that lesson 14.3 says is
# worse than no diagnostic at all.
#
# 0.45 sits between that and the frame that was actually broken:
# `snowline_detail` above the world ceiling bounds at 40% and rendered
# 2%. What a frame ACTUALLY contains is not knowable from arithmetic —
# `scripts/frame_cameras.py` raymarches it and is the instrument to
# reach for. This is only the cheap always-correct tripwire.
FRAME_FILL_WARN = 0.45


def _terrain_ceiling_m(recipe):
    """Highest ground in the world, in metres, or (None, why-not).

    Returns (ceiling_m, note). Exactly one of the two is None, so a caller
    can never confuse "the world tops out at X" with "I could not find
    out" — lesson 2.10, which this file has already paid for once.
    """
    ls = recipe.get("landscape")
    hm = recipe.get("heightmap")
    if not isinstance(ls, dict) or not isinstance(hm, dict):
        return None, "landscape/heightmap block missing or malformed"
    try:
        actor_z = float(ls["location_cm"][2])
        z_scale = float(ls["z_scale_cm"])
        src = str(hm["source"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None, "landscape/heightmap fields missing or malformed"

    path = os.path.normpath(os.path.join(bootstrap.REPO_ROOT, src))
    if not os.path.isfile(path):
        return None, "heightmap {0} is not on disk".format(src)
    try:
        # numpy and Pillow are in the recorded dependency register
        # (docs/environment.md), and
        # make_layer_weightmap already relies on both. Guarded anyway: a
        # missing optional import must not take the capture path down,
        # and must not silently masquerade as "the check passed".
        import numpy as _np
        from PIL import Image as _Image
        peak = int(_np.asarray(_Image.open(path)).max())
    except Exception as exc:                      # noqa: BLE001
        return None, "could not read {0}: {1}: {2}".format(
            src, type(exc).__name__, exc)

    # Same datum as everywhere else: heightmap 32768 maps to the actor's
    # Z, so value v sits at actor_z + (v/65535 - 0.5) * z_scale.
    return (actor_z + (peak / 65535.0 - 0.5) * z_scale) / 100.0, None


def _altitude_findings(recipe, cams, res):
    """Catch a camera aimed ABOVE every piece of ground in the world.

    WHY, and it is the sibling of `_footprint_errors` above. That check
    was written after two cameras sat OUTSIDE the terrain in X/Y and
    photographed empty sky. It reads `loc[0]` and `loc[1]` and never
    reads `loc[2]` — so the same failure through the Z axis walked
    straight past it.

    On 2026-08-02 it did. `--relief` 0.92 -> 0.62 shortened the world
    from 2355 m to 1587 m, and `snowline_detail` is a CONSTANT at world
    Z 1900 m with pitch exactly 0. The camera ended up 313 m above the
    highest ground in the map, aimed at the horizon, and its capture came
    back 98% sky with one peak in the corner — which reads as a fog or
    exposure fault, not as a camera-altitude fault, and the fog was
    ALSO mis-scaled by the same change, so the wrong explanation fit.

    Two findings, deliberately different severities:

    - HARD ERROR when it is PROVABLE that no terrain can be in frame:
      the camera is above the ceiling and the bottom edge of the frustum
      still points at or above the horizon. No heightmap detail can
      rescue that; it is geometry.
    - WARNING when an UPPER BOUND on the fraction of the frame that can
      contain terrain falls below FRAME_FILL_WARN. Ground at the world
      ceiling, at the farthest corner of the map, subtends the shallowest
      possible downward angle; everything nearer or lower sits below it.
      So terrain is confined to the frame band between the frustum's
      bottom edge and that angle, and the bound holds whatever the
      heightmap looks like.

    "Camera above the ceiling" is deliberately NOT the warning predicate.
    Every downward aerial shot is above the ceiling — the first version
    of this check keyed on it and fired on all four cameras including
    the top-down, which is flawless. A diagnostic that fires for the
    wrong reason is worse than none (lesson 14.3): it writes a false
    attribution into the record where a later session reads it as fact.

    This stays pure arithmetic so it cannot itself fail. What fraction
    ACTUALLY lands in frame is a raymarch question and
    `scripts/frame_cameras.py` answers it.

    FOV is HORIZONTAL in UE, so the vertical half-angle is derived
    through the capture aspect ratio rather than assumed equal.
    """
    errors, warnings = [], []
    ceiling_m, why = _terrain_ceiling_m(recipe)
    if ceiling_m is None:
        # Not silence. A gate that cannot run says so, or the next
        # session reads its absence as a pass.
        warnings.append(
            "camera altitude NOT CHECKED against the terrain: {0}. This "
            "check is what catches a camera aimed above the whole world; "
            "treat the capture as unvalidated in Z.".format(why))
        return errors, warnings

    try:
        width, height = float(res[0]), float(res[1])
        aspect = width / height if height > 0 else 1.0
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        aspect = 1.0

    for cam in cams:
        loc, rot = cam.get("location"), cam.get("rotation")
        fov = cam.get("fov")
        if not (isinstance(loc, list) and len(loc) == 3
                and isinstance(rot, list) and len(rot) == 3
                and isinstance(fov, (int, float))):
            continue
        cam_z_m = float(loc[2]) / 100.0
        margin = cam_z_m - ceiling_m
        if margin <= 0.0:
            continue

        pitch = float(rot[0])
        v_half = math.degrees(math.atan(
            math.tan(math.radians(float(fov) / 2.0)) / max(aspect, 1e-9)))
        bottom_edge = pitch + (-v_half if v_half > 0 else 0.0)

        if bottom_edge >= 0.0:
            errors.append(
                "capture.cameras {0!r} sits at Z {1:.0f} m, {2:.0f} m ABOVE "
                "the highest ground in the world ({3:.0f} m), and the "
                "bottom edge of its frustum points {4:+.1f} deg — at or "
                "above the horizon. NO terrain can appear in this frame at "
                "any distance; it is geometry, not a rendering fault. "
                "Lower the camera below {3:.0f} m or pitch it down past "
                "{5:.1f} deg.".format(
                    cam.get("name"), cam_z_m, margin, ceiling_m,
                    bottom_edge, -v_half))
            continue

        # Shallowest downward angle at which any ground can possibly sit:
        # the world ceiling, at the farthest corner of the map footprint.
        # Terrain is confined to the frame band below it.
        far = _max_ground_distance_m(recipe, loc)
        if far is None or far <= 0.0:
            continue
        band_top = -math.degrees(math.atan(margin / far))
        top_edge = pitch + v_half
        visible = max(0.0, min(band_top, top_edge) - bottom_edge)
        span = max(top_edge - bottom_edge, 1e-9)
        fill_bound = visible / span
        if fill_bound >= FRAME_FILL_WARN:
            continue
        warnings.append(
            "capture.cameras {0!r} at Z {1:.0f} m is {2:.0f} m above the "
            "world ceiling ({3:.0f} m), and AT MOST {4:.0f}% of its "
            "vertical FIELD OF VIEW can contain terrain — an ANGULAR "
            "bound (the screen-area fraction runs somewhat higher, since "
            "screen height goes as tan of the angle and the band sits at "
            "the frame bottom); it assumes ground at the ceiling at "
            "maximum range. The rest is sky. Run scripts/frame_cameras.py "
            "for the measured fill.".format(cam.get("name"), cam_z_m,
                                            margin, ceiling_m,
                                            100.0 * fill_bound))

    return errors, warnings


def _max_ground_distance_m(recipe, loc):
    """Farthest horizontal distance from `loc` to any point of terrain."""
    ls, hm = recipe.get("landscape"), recipe.get("heightmap")
    try:
        ox, oy = float(ls["location_cm"][0]), float(ls["location_cm"][1])
        span = (int(hm["resolution"]) - 1) * float(ls["scale_xy_cm"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    cx, cy = float(loc[0]), float(loc[1])
    dx = max(abs(cx - ox), abs(cx - (ox + span)))
    dy = max(abs(cy - oy), abs(cy - (oy + span)))
    return math.hypot(dx, dy) / 100.0


def _footprint_errors(recipe, cams):
    """Refuse a camera parked OUTSIDE the landscape's XY footprint.

    WHY. On 2026-08-01 two recipe cameras sat outside the terrain and every
    capture came back as empty sky. World Partition streams around the
    camera as a streaming source; parked beyond the loaded regions there is
    nothing to stream, so the shot is empty no matter how correct the aim,
    the FOV or the geometry. Four capture cycles and five discarded
    hypotheses - fog, lighting, aim, distance, LOD - went by before anyone
    tabulated camera POSITION.

    This is pure arithmetic against `landscape`, needs no editor, and
    turns that whole episode into one refusal before the first screenshot.

    Deliberately a HARD ERROR, not a warning: the failure it prevents is a
    capture that looks like a rendering bug, and a warning in a wall of
    output is what let it run four times. A legitimate outside-the-terrain
    camera is possible in principle (a distant establishing shot once HLOD
    exists) - when one is wanted, this refusal is the place to revisit,
    with the reason recorded.
    """
    e = []
    ls = recipe.get("landscape")
    hm = recipe.get("heightmap")
    if not isinstance(ls, dict) or not isinstance(hm, dict):
        return e
    try:
        ox, oy = float(ls["location_cm"][0]), float(ls["location_cm"][1])
        sc = float(ls["scale_xy_cm"])
        res = int(hm["resolution"])
    except (KeyError, TypeError, ValueError, IndexError):
        # The landscape/heightmap validators own these fields; if they are
        # malformed this check stays silent rather than reporting a second,
        # confusing error for the same root cause.
        return e
    if not (math.isfinite(ox) and math.isfinite(oy) and sc > 0 and res > 1):
        return e

    span = (res - 1) * sc
    x0, x1 = ox, ox + span
    y0, y1 = oy, oy + span
    for cam in cams:
        loc = cam.get("location")
        if not (isinstance(loc, list) and len(loc) == 3):
            continue
        cx, cy = float(loc[0]), float(loc[1])
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            continue
        e.append(
            "capture.cameras {0!r} at x={1:.0f} y={2:.0f} is OUTSIDE the "
            "landscape footprint x[{3:.0f}, {4:.0f}] y[{5:.0f}, {6:.0f}] "
            "(cm). World Partition streams around the camera, so a camera "
            "parked outside the loaded regions photographs empty sky "
            "regardless of where it is aimed. Move it inside the "
            "footprint.".format(cam.get("name"), cx, cy, x0, x1, y0, y1))
    return e


def _capture_source(biome_id, camera, out_path, resolution):
    """Build the per-camera capture payload.

    `rotation_deg` is [pitch, yaw, roll] per schema.md. unreal.Rotator's
    POSITIONAL order is (roll, pitch, yaw) — the opposite end first — so
    keywords are used here deliberately. Getting this wrong silently
    tilts every capture.
    """
    return '''
import builtins as _builtins
import json as _json
import unreal as _unreal

_label = {label!r}
_loc = {loc!r}
_rot = {rot!r}
_fov = float({fov!r})
_path = {path!r}
_w = int({width!r})
_h = int({height!r})

_out = {{"ok": False, "spawned": False}}

_ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
_world = _ues.get_editor_world()
_eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)

# Deterministic reuse: find the camera by label, spawn only if absent.
# ALL matches are counted — a hand-made duplicate label makes the pick
# arbitrary, so the count is reported and the caller warns.
_found = []
for _a in _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.CameraActor):
    if _a.get_actor_label() == _label:
        _found.append(_a)
_out["label_matches"] = len(_found)
_cam = _found[0] if _found else None

if _cam is None:
    _cam = _eas.spawn_actor_from_class(
        _unreal.CameraActor, _unreal.Vector(0.0, 0.0, 0.0))
    _cam.set_actor_label(_label)
    _out["spawned"] = True

# World Partition: a spatially-loaded camera in an unloaded region is
# invisible to the label search above, so a re-run would spawn a
# duplicate (hard rule 3). Mark the camera always-loaded.
try:
    _cam.set_editor_property("is_spatially_loaded", False)
except Exception:
    _out["spatial_flag_failed"] = True

_cam.set_actor_location(
    _unreal.Vector(_loc[0], _loc[1], _loc[2]), False, True)
_cam.set_actor_rotation(
    _unreal.Rotator(roll=_rot[2], pitch=_rot[0], yaw=_rot[1]), False)
_cam.camera_component.set_editor_property("field_of_view", _fov)

# Pre-position the viewport near the shot. Framing AND field of view are
# enforced by the camera= argument to take_high_res_screenshot below;
# this call alone copies only location/rotation — the viewport would
# keep its own FOV and fov_deg would be silently ignored. Kept so the
# editor is left looking at the captured framing after the engine
# releases the camera lock.
_ues.set_level_viewport_camera_info(
    _cam.get_actor_location(), _cam.get_actor_rotation())

_out["camera_location"] = [
    _cam.get_actor_location().x,
    _cam.get_actor_location().y,
    _cam.get_actor_location().z,
]
_out["requested_path"] = _path
# camera= makes the engine pilot the viewport to this CameraActor for
# the shot (SetActorLock + UpdateViewForLockedActor,
# AutomationBlueprintFunctionLibrary.cpp:1242-1252) and release the lock
# when the screenshot is done — so field_of_view IS honoured. The 5.8
# return is a UAutomationEditorTask, never a bool; None is the only
# refusal signal.
#
# THE TASK MUST OUTLIVE THIS PAYLOAD. Nothing engine-side roots it:
# TakeHighResScreenshot guards the UAutomationEditorTask with an
# FGCObjectScopeGuard lasting only the C++ call
# (AutomationBlueprintFunctionLibrary.cpp:1225-1226), and the deferred
# ticker (:1259) captures only the viewport pointer plus value copies —
# never the task or its state. If the task is collected before the shot
# is processed, ~FScreenshotTakenState runs with Done == false and calls
# UnlockViewport() (:629-639, :656-689): actor lock released, game view
# toggled back, mid-flight. Epic's comment at :1246-1247 assumes the
# caller holds the task: "We unset the actor lock later when the
# screenshot is done."
#
# Scope of that hazard, verified in engine source (audit 2026-07-31):
# premature collection MISFRAMES the shot; it cannot suppress the file.
# The capture is latched on the FViewport with a forced redraw
# (UnrealClient.cpp:1593-1596), serviced unconditionally in Draw
# (:1797-1811), and the PNG write completes or fails SYNCHRONOUSLY
# before OnScreenshotRequestProcessed broadcasts
# (EditorViewportClient.cpp:6960-7008 blocking Get, broadcast :7095) —
# none of which consults the state object. Also: MODE_EXEC_FILE literal
# code runs in the PERSISTENT console dicts (PythonScriptPlugin.cpp:1858
# resolving to :1807-1810), so payload top-level names do not die at
# command end; builtins is used because it is explicit and immune to a
# later payload reassigning the name. Keeping the task alive is what
# makes the actor lock — and therefore fov_deg — hold until SetDone. It
# is NOT a confirmed explanation for the missing-file regression; the
# engine poll driven by the host exists to bisect that.
_stash = getattr(_builtins, "_LANDSCAPELAB_SHOT_TASKS", None)
if _stash is None:
    _stash = {{}}
    setattr(_builtins, "_LANDSCAPELAB_SHOT_TASKS", _stash)

_task = _unreal.AutomationLibrary.take_high_res_screenshot(
    _w, _h, _path, camera=_cam, delay=0.25)
if _task is not None:
    _stash[_path] = _task
_out["accepted"] = _task is not None
try:
    _out["valid_task"] = bool(_task.is_valid_task()) if _task else False
except Exception as _exc:
    _out["valid_task"] = None
_out["ok"] = True

print("{marker}" + _json.dumps(_out))
'''.format(label=camera["_label"], loc=[float(v) for v in camera["location"]],
           rot=[float(v) for v in camera["rotation"]],
           fov=float(camera["fov"]), path=out_path,
           width=resolution[0], height=resolution[1], marker=PROBE_MARKER)


# A screenshot is LATCHED ON THE VIEWPORT and serviced inside Draw()
# (UnrealClient.cpp:1593-1596, :1797-1811). If the level viewport never
# draws, the request is accepted, the task is valid, and is_task_done()
# stays false FOREVER — there is no error anywhere, because nothing has
# failed; nothing has happened.
#
# An editor level viewport does not draw continuously by default. It draws
# when it is invalidated, and an unfocused editor invalidates it rarely.
# Observed 2026-08-01, twice: a capture sat outstanding for 11 and then 13
# minutes with the engine's frame counter advancing normally at ~3 FPS —
# so the editor was awake and ticking, and simply not drawing THAT
# viewport. Bringing the window to the front completed the pending shot
# within seconds, every time. That is a diagnosis, not a fix: it means
# every capture silently depended on somebody looking at the editor.
#
# ULevelEditorSubsystem exposes both halves of the fix as BlueprintCallable
# in 5.8 (LevelEditorSubsystem.h:65-69, both DevelopmentOnly):
#     void EditorSetViewportRealtime(bool bInRealtime, FName ConfigKey)
#     void EditorInvalidateViewports()
# Realtime makes the viewport draw continuously regardless of focus;
# invalidating on every poll is the belt-and-braces that does not depend on
# realtime having been accepted. Both are VIEWPORT UI state, not scene
# state: nothing is spawned, no actor or asset is touched, and nothing is
# saved, so this does not make a capture a scene change.
REALTIME_SOURCE = '''
import json as _json
import unreal as _unreal

_want = {want!r}
_out = {{"realtime_set": False, "previous": None}}

_les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
if _les is not None:
    try:
        _les.editor_set_viewport_realtime(bool(_want))
        _out["realtime_set"] = True
    except Exception as _exc:
        _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    try:
        _les.editor_invalidate_viewports()
        _out["invalidated"] = True
    except Exception as _exc:
        _out["invalidate_error"] = "%s: %s" % (type(_exc).__name__, _exc)
else:
    _out["error"] = "LevelEditorSubsystem unavailable"

print("{marker}" + _json.dumps(_out))
'''

# Sent on every poll while a shot is outstanding. Deliberately minimal.
INVALIDATE_SOURCE = '''
import json as _json
import unreal as _unreal

_out = {{"invalidated": False}}
_les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
if _les is not None:
    try:
        _les.editor_invalidate_viewports()
        _out["invalidated"] = True
    except Exception as _exc:
        _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''.format(marker=PROBE_MARKER)


RESIDENCY_SOURCE = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

# World Partition loading is NOT viewport-driven. A fresh editor session
# can have most of the landscape unloaded, and a screenshot taken then
# shows holes where terrain should be — silently, with no error. Every
# capture is evidence, so residency is established before any shot.
_want_landscapes, _want_proxies = 0, 0
_guids = []
try:
    for _d in _unreal.WorldPartitionBlueprintLibrary.get_actor_descs():
        _cls = _d.get_editor_property("native_class")
        _name = _cls.get_name() if _cls is not None else ""
        if _name == "Landscape":
            _want_landscapes += 1
        elif _name == "LandscapeStreamingProxy":
            _want_proxies += 1
        else:
            continue
        _guids.append(_d.get_editor_property("guid"))
    if _guids:
        _unreal.WorldPartitionBlueprintLibrary.load_actors(_guids)
    _out["load_error"] = None
except Exception as _exc:
    _out["load_error"] = "%s: %s" % (type(_exc).__name__, _exc)

_have_landscapes = len(list(
    _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape)))
_have_proxies = len(list(
    _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy)))

_out["want"] = [_want_landscapes, _want_proxies]
_out["have"] = [_have_landscapes, _have_proxies]
# A ZERO COUNT REFUSES (conduct rule 13): a world whose actor descs
# enumerate no landscape at all gives want == have == [0, 0], and that
# is silence, not residency. The gate must not pass on nothing.
_out["ok"] = (_out["load_error"] is None
              and _want_landscapes + _want_proxies > 0
              and _have_landscapes == _want_landscapes
              and _have_proxies == _want_proxies)
if _out["load_error"] is None and _want_landscapes + _want_proxies == 0:
    _out["reason"] = ("zero landscape actor descs enumerated -- nothing "
                      "to confirm residency against")

print("{marker}" + _json.dumps(_out))
'''.format(marker=PROBE_MARKER)


def _poll_source(out_path, release):
    """Ask the engine whether a stashed screenshot task has completed.

    Authoritative where the filesystem is not: IsTaskDone() flips in
    FScreenshotTakenState::SetDone (AutomationBlueprintFunctionLibrary
    .cpp:641-648), which is bound to
    FScreenshotRequest::OnScreenshotRequestProcessed (:625; the
    non-automation branch applies — GIsAutomationTesting is false under
    remote exec). That broadcast fires only AFTER the PNG write has
    completed or failed: RequestSaveScreenshot blocks on the
    ImageWriteQueue future (EditorViewportClient.cpp:6960-7008) before
    ProcessScreenShots broadcasts (:7095). So "done + no file" means no
    file is coming, ever — it cannot be a race with a slow writer.
    Caveat: an UNBOUND task (engine refused the shot at the resolution
    guard, cpp:1231-1289 — no BindTask, no ticker) reports done False
    forever, since IsTaskDone is IsValidTask() && Task->IsDone()
    (cpp:92-95); the caller screens that out via valid_task instead of
    waiting on it. Releasing the stashed reference afterwards lets the
    task be collected normally — once Done is true the destructor no
    longer tears down the viewport.
    """
    return '''
import builtins as _builtins
import json as _json

_path = {path!r}
_release = {release!r}
_out = {{"known": False, "done": None}}

_stash = getattr(_builtins, "_LANDSCAPELAB_SHOT_TASKS", None) or {{}}
_task = _stash.get(_path)
_out["known"] = _task is not None
if _task is not None:
    try:
        _out["done"] = bool(_task.is_task_done())
    except Exception as _exc:
        _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    if _release:
        _stash.pop(_path, None)
_out["outstanding"] = len(_stash)

print("{marker}" + _json.dumps(_out))
'''.format(path=out_path, release=bool(release), marker=PROBE_MARKER)


def _parse(text, marker=PROBE_MARKER):
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source, marker=PROBE_MARKER):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  command did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(result), marker)
    except Exception as exc:
        print("  command errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _wait_for(path, remote_exec=None, remote=None, node_id=None,
              timeout=SCREENSHOT_TIMEOUT_S):
    """Wait for a screenshot to land, consulting the engine as well as disk.

    Returns (ok, task_done). The file is authoritative for "usable
    output"; the task is authoritative for "the engine finished". Asking
    both distinguishes "still rendering" from "the engine gave up and no
    file is coming", which the previous filesystem-only wait could not.

    The timeout is measured in EDITOR time, not wall-clock time: any
    interval in which this process was not scheduled at all (host
    suspend — see SUSPEND_GAP_S) is added back to the deadline. Before
    that, a standby overnight consumed the whole 900 s ceiling while the
    editor did zero frames, and the run was reported as a failure that
    the engine then completed on resume.

    WHAT COUNTS AS A SUSPEND, AND WHY IT IS MEASURED SO NARROWLY.
    The gap is measured ACROSS THE SLEEP ONLY — from just before
    time.sleep() to the top of the next iteration — never across the
    loop body. The body contains a BLOCKING remote-exec round trip to
    the editor, and the documented normal case for this script is an
    editor stalled for minutes compiling shaders. Measured across the
    body, such a stall reads as a >30 s gap and would (a) extend the
    ceiling that exists precisely to bound a stalled editor, and (b)
    print "the host was suspended" as though it were evidence — a false
    attribution in the one log a future multi-hour gap will be diagnosed
    from. A sleep of POLL_INTERVAL_S that takes 30x longer than asked
    cannot be the editor's fault and cannot be scheduling jitter on an
    idle loop; it means this process was not running.

    The cost of the narrow measurement is deliberate and one-directional:
    a host suspend that happens to land inside the blocking poll is
    charged to the timeout rather than credited. That fails toward
    timing out, never toward waiting forever.
    """
    started = time.time()
    deadline = started + timeout
    last_size = -1
    task_done = None
    warned_slow = False
    suspended_s = 0.0
    slept_at = None
    next_task_poll = started + 5.0

    while time.time() < deadline:
        # Suspension check FIRST: everything below (including the file
        # test and the slow-capture notice) should reason about editor
        # time, not wall-clock time.
        now = time.time()
        if slept_at is not None:
            gap = now - slept_at
            if gap > SUSPEND_GAP_S:
                deadline += gap
                suspended_s += gap
                next_task_poll = now + 5.0
                print("    a {0:.0f}s sleep took {1:.0f}s — this process was "
                      "NOT SCHEDULED for that interval (host suspend); not "
                      "charging it against the {2:.0f}s ceiling.".format(
                          POLL_INTERVAL_S, gap, timeout))

        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size > 0 and size == last_size:
                return True, task_done
            last_size = size

        waited = time.time() - started - suspended_s
        if not warned_slow and waited > SLOW_CAPTURE_NOTICE_S:
            warned_slow = True
            print("    still waiting after {0:.0f}s — if a material was "
                  "just created or changed, the engine is most likely "
                  "compiling shaders; this can take minutes on an "
                  "integrated GPU.".format(waited))

        if remote is not None and time.time() >= next_task_poll:
            next_task_poll = time.time() + 5.0
            # Kick the viewport before asking whether the shot is done.
            # Without this the answer is "not done" forever whenever the
            # editor is unfocused — see INVALIDATE_SOURCE.
            _run(remote_exec, remote, node_id, INVALIDATE_SOURCE)
            poll = _run(remote_exec, remote, node_id,
                        _poll_source(path, release=False))
            if poll is not None:
                task_done = poll.get("done")
                # Engine reports finished but nothing on disk: no file
                # is coming — the write completes or fails BEFORE the
                # done broadcast (EditorViewportClient.cpp:6960-7008,
                # broadcast :7095). One grace poll for filesystem
                # visibility lag only, then stop rather than burn the
                # full timeout.
                if task_done and not os.path.isfile(path):
                    time.sleep(POLL_INTERVAL_S * 3)
                    if not os.path.isfile(path):
                        return False, True

        # Set immediately before the sleep, so the next iteration's gap
        # measures the sleep and nothing else. Anything blocking above
        # (notably the remote poll) is charged to the editor, which is
        # what the ceiling is there to bound.
        slept_at = time.time()
        time.sleep(POLL_INTERVAL_S)
    if suspended_s > 0.0:
        print("    (host was suspended for {0:.0f}s in total during this "
              "wait; the ceiling was extended by that much and still "
              "expired.)".format(suspended_s))
    return False, task_done


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--note", default="",
                        help="Free text appended to the printed summary, "
                             "for pasting into LESSONS.md.")
    parser.add_argument("--filename-tag", default="",
                        help="Suffix appended to every filename in this "
                             "run, e.g. --filename-tag debug produces "
                             "..._<hash>_debug.png. Exists so a DIAGNOSTIC "
                             "capture is marked as one at the moment it is "
                             "written, rather than by a manual rename that "
                             "can be forgotten (the debug-material fence "
                             "requires the _debug suffix).")
    parser.add_argument("--allow-sleep", action="store_true",
                        help="Do NOT ask Windows to stay awake during the "
                             "run. Default is to hold a sleep inhibitor: "
                             "on 2026-08-01 the host entered Modern "
                             "Standby mid-run and three captures completed "
                             "hours later, on resume.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    config, errors = validate_capture(recipe)
    if errors:
        print("REFUSE: capture block invalid:")
        for e in errors:
            print("  - {0}".format(e))
        return 2
    for w in config.get("warnings") or []:
        print("WARNING: {0}".format(w))

    biome_id = config["biome_id"]  # validated ^[a-z][a-z0-9_]*$ above
    # Same charset rule the camera names get, and for the same reason:
    # this string lands in a filesystem path. Validated here rather than
    # sanitised silently, so a tag containing a separator or '..' is a
    # refusal and not a quietly-relocated write (conduct rule 1). The
    # host-side escape check before the engine sees the path still stands
    # as the backstop.
    tag = args.filename_tag
    if tag and not all(c.isalnum() or c in "_-" for c in tag):
        print("REFUSE: --filename-tag {0!r} must be alphanumeric, '_' or "
              "'-' — it becomes part of a filename.".format(tag))
        return 2
    suffix = ("_" + tag) if tag else ""
    stamp = git_stamp()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("Output dir      : {0}".format(config["output_dir"]))
    print("Commit          : {0}".format(stamp))
    print("Cameras         : {0}".format(
        ", ".join(c["name"] for c in config["cameras"])))
    if stamp.endswith("-dirty"):
        print("")
        print("NOTE: the working tree is dirty, so these captures are not")
        print("reproducible from a commit. Filenames are marked -dirty.")
    print("")

    os.makedirs(config["output_dir"], exist_ok=True)

    # --- CAPTURE GUARD (adopted 2026-08-06) --------------------------
    #
    # WHY. Run A of the 2026-08-05 sweep wrote two frames and was then
    # killed by UUnrealEdEngine::CloseEditor() 40 seconds later, from the
    # UI, with 11 cameras still to go. It cost a session of misdiagnosis
    # ("zero frames", "the editor stayed alive" — both false). A capture
    # in flight was simply not visible to the person at the keyboard.
    #
    # Two halves, and the second is the one that survives a crash:
    #   BANNER   — unmissable, on stdout, naming what is about to run.
    #   SENTINEL — a file at the repo root for the duration.
    #
    # THE SENTINEL IS DIAGNOSTIC BY DESIGN. It is removed on any clean
    # exit, including a refusal. So a sentinel found lying around means
    # the run DIED — and it carries the pid, start time and camera list
    # to say which run and how far it should have got. An absent sentinel
    # after a failed run means the script exited in an orderly way and
    # the fault is elsewhere. That distinction is exactly the one that
    # was missing on 2026-08-05.
    sentinel = os.path.join(REPO_ROOT, "CAPTURE_IN_PROGRESS")
    names = [c["name"] for c in config["cameras"]]
    print("=" * 70)
    print("  CAPTURE IN PROGRESS — DO NOT CLOSE THE EDITOR")
    print("  {0} camera(s): {1}".format(len(names), ", ".join(names)))
    print("  Closing the editor mid-run kills the capture and leaves the")
    print("  log ending mid-camera with no summary — see LESSONS 2026-08-05.")
    print("=" * 70)
    print("")
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("pid {0}\nstarted {1}\ncameras {2}\n".format(
                os.getpid(), ts, ",".join(names)))
    except OSError as exc:
        # Never take the capture down over the guard. A guard that can
        # break the thing it guards is worse than no guard.
        print("WARNING: could not write the capture sentinel ({0}). The "
              "run continues; a crashed run will not be "
              "self-identifying.".format(exc))

    # Acquired BEFORE the editor is contacted and released in the outer
    # finally, so it covers every wait in the run.
    guard = _SleepGuard(enabled=not args.allow_sleep)
    guard.acquire()
    # SETUP IS INSIDE A RELEASE PATH TOO. _load_remote_execution() raises
    # when the engine module has moved, and RemoteExecution()/start() can
    # fail on a socket — all three run BEFORE the try whose finally
    # releases the guard, so without this they would leave the inhibitor
    # held. Process exit would clear it today (the request is per-thread
    # and dies with the thread), but that is an accident of being run as
    # a script: main() is importable, and "released because we happened
    # to exit" is not a release path.
    try:
        print("Sleep inhibitor : {0}".format(guard.detail))
        print("")
        print("--- editor identity gate (conduct rule 7) ---")

        remote_exec = bootstrap._load_remote_execution()
        remote = remote_exec.RemoteExecution()
        remote.start()
    except BaseException:
        guard.release()
        # The sentinel was written above but the finally that removes it
        # belongs to the NEXT try — without this, a remote-exec setup
        # failure exits in an orderly way and still leaves the sentinel,
        # which reads as "the run DIED" (the exact 2026-08-05 misread the
        # sentinel exists to prevent). Same guarded remove as the finally.
        try:
            if os.path.isfile(sentinel):
                os.remove(sentinel)
        except OSError:
            pass
        raise
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        # Level gate (schema v1.2). Must precede residency: residency asks
        # "is all of THIS world loaded", which answers nothing if this is
        # the wrong world. A capture of the wrong level is the purest form
        # of evidence that lies — it is a real, correct, well-exposed
        # photograph of somewhere else.
        print("--- level gate (recipe landscape.level_path) ---")

        def _lvl_runner(source, marker):
            return _run(remote_exec, remote, node["node_id"], source, marker)

        # .get(), not [] — validate_capture() never looks at the landscape
        # block, so a recipe missing level_path would raise KeyError and
        # exit 1, which this script's exit-code contract does not define
        # for a recipe fault. gate_level validates its own expected value
        # and refuses (exit 6) instead.
        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level, _lvl_runner)
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            print("  Conduct rule 7 verified the PROJECT; this checks the")
            print("  LEVEL. Open {0!r} and re-run.".format(want_level))
            return 6
        print("  level {0}".format(detail))
        print("")

        # Make the level viewport draw without needing the editor focused.
        # This is what stops a capture from silently waiting forever while
        # nobody is looking at the editor (see REALTIME_SOURCE).
        print("--- viewport realtime ---")
        rt = _run(remote_exec, remote, node["node_id"],
                  REALTIME_SOURCE.format(want=True, marker=PROBE_MARKER))
        if rt is None or not rt.get("realtime_set"):
            print("  WARNING: could not put the level viewport in realtime "
                  "({0}). Captures may wait until the editor window is "
                  "brought to the front.".format(
                      (rt or {}).get("error", "no result")))
        else:
            print("  realtime on; viewport invalidated")
        print("")

        # Residency gate. Unloaded World Partition terrain photographs as
        # holes, silently. Captures are evidence; refuse rather than
        # produce a picture that lies about the scene.
        print("--- residency (World Partition) ---")
        res = _run(remote_exec, remote, node["node_id"], RESIDENCY_SOURCE)
        if res is None:
            print("FAIL: the residency probe returned nothing.")
            return 6
        if res.get("load_error"):
            print("  load error: {0}".format(res["load_error"]))
        if res.get("reason"):
            print("  {0}".format(res["reason"]))
        print("  landscapes  {0} of {1} on disk".format(
            (res.get("have") or [None])[0], (res.get("want") or [None])[0]))
        print("  proxies     {0} of {1} on disk".format(
            (res.get("have") or [None, None])[1],
            (res.get("want") or [None, None])[1]))
        if not res.get("ok"):
            print("")
            print("REFUSE: World Partition terrain is not fully resident. A")
            print("capture taken now would show holes where terrain should")
            print("be, with no error and no way to tell later. Captures are")
            print("evidence; a silently wrong one poisons the record.")
            return 6
        print("  fully resident")
        print("")

        written, setup_failed, shot_failed = [], [], []
        out_root = _norm(config["output_dir"])
        for cam in config["cameras"]:
            # Shot timeouts count too: two 120s waits that produced
            # nothing are two in-editor failures (conduct rule 6), and
            # a released-but-never-done task's deferred GC teardown
            # (~FScreenshotTakenState with Done == false) could strip a
            # LATER camera's actor lock mid-shot — stopping bounds both.
            if len(setup_failed) + len(shot_failed) >= 2:
                print("Stopping: two in-editor failures — not continuing "
                      "against the live editor (conduct rule 6).")
                break
            filename = "{0}__{1}__{2}__{3}{4}.png".format(
                biome_id, cam["name"], ts, stamp, suffix)
            out_path = os.path.join(config["output_dir"], filename)
            # Unreachable given the biome_id/name validation, but this is
            # the last host-side line before a path reaches the engine:
            # fail closed rather than trust the interpolation upstream.
            if not _norm(out_path).startswith(out_root + os.sep):
                print("REFUSE: computed path escapes output_dir: "
                      "{0!r}".format(out_path))
                return 2
            cam = dict(cam)
            cam["_label"] = "Capture_{0}_{1}".format(biome_id, cam["name"])

            print("--- {0} ---".format(cam["name"]))
            result = _run(remote_exec, remote, node["node_id"],
                          _capture_source(biome_id, cam, out_path,
                                          config["resolution"]))
            if not result or not result.get("ok"):
                print("  FAIL: camera setup or capture call failed.")
                # The payload may have stashed the task before its
                # output was lost (parse/connection failure). Best-
                # effort release so that path cannot pin the task —
                # and, if the shot never processes, the pilot lock —
                # for the whole editor session.
                _run(remote_exec, remote, node["node_id"],
                     _poll_source(out_path, release=True))
                setup_failed.append(cam["name"])
                continue
            if result.get("label_matches", 0) > 1:
                print("  WARNING: {0} actors share the label {1!r}; the "
                      "first found was moved. Remove hand-made duplicates "
                      "in-editor.".format(
                          result["label_matches"], cam["_label"]))
            if result.get("spatial_flag_failed"):
                print("  WARNING: could not mark the camera always-loaded; "
                      "if its World Partition region unloads, a re-run "
                      "will spawn a duplicate.")
            print("  camera {0} at {1}".format(
                "spawned" if result.get("spawned") else "reused",
                result.get("camera_location")))
            if result.get("accepted") is False:
                print("  FAIL: the editor refused the screenshot request.")
                setup_failed.append(cam["name"])
                continue
            # An unbound task means the engine refused the shot at its
            # resolution guard (AutomationBlueprintFunctionLibrary
            # .cpp:1231-1289): no ticker was registered, no file can
            # ever come, and is_task_done() never flips for an unbound
            # task (cpp:92-95). Waiting 120s would learn nothing — fail
            # fast as a setup failure and release the stashed task.
            # (None means the probe errored; only a definite False
            # short-circuits.)
            if result.get("valid_task") is False:
                print("  FAIL: the editor returned a task with nothing "
                      "bound — the request was refused before scheduling "
                      "(engine resolution guard). Not waiting.")
                _run(remote_exec, remote, node["node_id"],
                     _poll_source(out_path, release=True))
                setup_failed.append(cam["name"])
                continue
            print("  waiting for {0} ...".format(filename))
            ok, task_done = _wait_for(out_path, remote_exec, remote,
                                      node["node_id"])
            # Release the stashed task either way: once the engine has
            # finished, the reference is no longer protecting anything,
            # and leaking it would pin a UObject for the session.
            _run(remote_exec, remote, node["node_id"],
                 _poll_source(out_path, release=True))
            if ok:
                size_kb = os.path.getsize(out_path) / 1024.0
                print("  WROTE {0} ({1:.0f} KiB)".format(out_path, size_kb))
                written.append(out_path)
            elif task_done:
                print("  FAIL: the engine reported the screenshot task "
                      "DONE but no file was written. That is an engine-"
                      "side write failure, not a timeout.")
                shot_failed.append(cam["name"])
            else:
                print("  FAIL: screenshot did not appear within {0:.0f}s "
                      "(engine task_done={1}).".format(
                          SCREENSHOT_TIMEOUT_S, task_done))
                shot_failed.append(cam["name"])
            print("")

        print("=" * 70)
        for path in written:
            print("  {0}".format(path))
        if setup_failed:
            print("")
            print("FAILED in-editor: {0}".format(", ".join(setup_failed)))
        if shot_failed:
            print("")
            print("FAILED to appear on disk: {0}".format(
                ", ".join(shot_failed)))
        print("=" * 70)
        print("")
        print("Pipeline rule 4 satisfied (capture after scene change). A "
              "one-line LESSONS.md note is suggested, not required.")
        if args.note:
            print("  suggested: {0} — {1} ({2})".format(
                args.note, ", ".join(os.path.basename(p) for p in written),
                stamp))
        if setup_failed:
            return 4
        return 5 if shot_failed else 0
    finally:
        remote.stop()
        guard.release()
        # Removed on EVERY orderly exit, refusals included. A surviving
        # sentinel therefore means the process died, which is the signal.
        try:
            if os.path.isfile(sentinel):
                os.remove(sentinel)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
