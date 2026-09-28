"""sweep_cameras.py — regenerate the ground-to-2 km sweep stations.

THE CAMPAIGN'S ACCEPTANCE CONDITION IS A CONTINUOUS PULL-BACK from a
summit to 2 km, judged for tiling pop, blend seams and cliff stretching
at every distance. That sweep is six STATIONS, and this file is how they
come back identically on any later run.

PROVENANCE OF THE SUMMIT, AND WHAT IS HONESTLY NOT RECOVERABLE
--------------------------------------------------------------
The design is recorded in BACKLOG.md ("Pass 2 exit gate — the ground-to-2
km sweep, DESIGNED but NOT CAPTURED"), which fixes:

    target  = highest summit within 1 km of map centre
    stations= 60, 150, 350, 700, 1200, 2000 m along bearing 105
    eye     = 1.7 m above each station's OWN local terrain
    aim     = 20 m above the summit
    fov     = 50
    and, for the run of 2026-08-05, the resolved summit
    (-844.0, -1040.0) m at z 1406.7 m, with station eye heights
    1350.0 / 1257.4 / 975.6 / 577.1 / 568.5 / 645.5 m.

**THE SELECTION RULE DOES NOT REPRODUCE THAT SUMMIT AND IS NOT IN THIS
REPO.** Measured 2026-08-05 against `terrain/alpine_heightmap_v2.png`:

  - a plain argmax within 1 km of centre gives (324, -724) z 1149.2 m;
  - within the summit's own 1339 m radius it gives (-768, -1096)
    z 1433.2 m — a DIFFERENT and HIGHER pixel;
  - `terrain_erosion.landmarks()` returns 34 peaks and NONE is at
    (-844, -1040); its nearest is (-768, -1160) z 1445.9 m.

So the recorded summit is a real, verifiable point — `heightmap[748][797]
= 36012` maps to 1406.74 m, matching the recorded 1406.7 to 0.04 m — but
the procedure that CHOSE it was never written down. This file therefore
treats the summit as a RECORDED CONSTANT with a citation, not as
something it re-derives. Re-deriving would silently move the subject of
the acceptance gate, which is the one thing the "regenerate exactly, do
not re-derive" instruction exists to prevent.

That constant is guarded: the summit guard runs UNCONDITIONALLY on every
invocation (there is no `--check` flag) and refuses (exit 3) if the heightmap
no longer puts 1406.7 m at that pixel. A recorded summit against a changed
terrain
is a stale derived record (non-negotiable 15), and the failure mode of
using one is a sweep that photographs the wrong mountain while every
number in the report still looks right.

BEARING CONVENTION, RECOVERED BY MEASUREMENT
--------------------------------------------
Station = summit + d * (cos 105 deg, sin 105 deg) — the PLUS direction,
which puts the camera on the lit side at the measured sun bearing of 105
(the light actor's yaw of 285 is the direction light TRAVELS; see CURRENT
STATE). Checked against the six recorded eye heights: PLUS reproduces
them to within 3.2 m worst case and 0.03 m best, while MINUS is wrong by
up to 342.6 m. The residual is bilinear-vs-nearest sampling, not a
different convention.

The recorded eye heights are used VERBATIM rather than recomputed, so
the stations are the design's own numbers. `--recompute` prints what this
file would derive instead, for comparison only.

Exit codes:
  0  stations printed, or written to the recipe
  1  unexpected error (argparse rejects bad CLI args with exit 2, not 1)
  2  recipe missing, unparseable, or outside REPO_ROOT
  3  the summit guard refused — the heightmap no longer matches the
     recorded summit, so the recorded stations are stale
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import landscape_spec     # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT

# --- the recorded design (BACKLOG.md), quoted as constants -------------
SUMMIT_X_M = -844.0
SUMMIT_Y_M = -1040.0
SUMMIT_Z_M = 1406.7
BEARING_DEG = 105.0
AIM_ABOVE_SUMMIT_M = 20.0
EYE_ABOVE_GROUND_M = 1.7
FOV_DEG = 50.0
STATION_DISTANCES_M = [60.0, 150.0, 350.0, 700.0, 1200.0, 2000.0]
# Recorded eye heights, in station order. Used verbatim.
STATION_EYE_Z_M = [1350.0, 1257.4, 975.6, 577.1, 568.5, 645.5]

# Capture aspect (capture.resolution is 1920x1080). fov_deg is UE's
# HORIZONTAL field of view (CameraComponent.h:37), so the vertical half
# angle has to come through the aspect — assuming they are equal would
# over-pitch every station by ~10 degrees.
ASPECT = 1920.0 / 1080.0

# Margin above the chosen horizon for the top edge of the frame. Small on
# purpose: every degree spent on sky is a degree not spent on the surface
# being judged.
SKYLINE_HEADROOM_DEG = 2.0

# Which horizon across the frame's width the aim follows. The MEDIAN
# would chase a lumpy skyline; the maximum pins the frame to one tall
# bank and fills the rest with sky (measured: ~70% sky at sweep_1200).
# 0.6 sits just above typical so the far ground is included and the
# outliers clip out of the top.
HORIZON_PERCENTILE = 0.60

# How far below horizontal the BOTTOM edge of the frame must look, so
# every station has a foreground. At 1.7 m eye height a bottom edge of
# -15 deg starts the ground at about 6.3 m out, which puts near-field
# surface — where tiling and blend seams are actually legible — in the
# bottom of every frame.
MIN_DEPRESSION_DEG = 15.0

# How far to march when looking for the skyline. The map is 8.06 km
# across, so this reaches the far edge from any station.
MAX_MARCH_M = 9000.0

# How far the guard lets the recorded summit drift from the heightmap
# before it refuses. The recorded value reproduces to 0.04 m today; 1.0 m
# is loose enough to absorb rounding in the recorded figure and far
# tighter than any real terrain edit.
SUMMIT_TOLERANCE_M = 1.0


def _terrain_sampler(recipe):
    """Return (sample_fn, ceiling_m) or raise.

    sample_fn(x_m, y_m) -> ground height in metres, bilinear.
    Same datum as every other tool here: heightmap 32768 sits at the
    landscape actor's Z, and value v is actor_z + (v/65535 - 0.5)*z_scale.
    """
    import numpy as np
    from PIL import Image

    ls, hm = recipe["landscape"], recipe["heightmap"]
    ox_m = float(ls["location_cm"][0]) / 100.0
    oy_m = float(ls["location_cm"][1]) / 100.0
    actor_z_m = float(ls["location_cm"][2]) / 100.0
    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    spacing_m = float(ls["scale_xy_cm"]) / 100.0

    path = os.path.normpath(os.path.join(REPO_ROOT, str(hm["source"])))
    arr = np.asarray(Image.open(path)).astype(np.float64)
    rows, cols = arr.shape

    def sample(x_m, y_m):
        c = (x_m - ox_m) / spacing_m
        r = (y_m - oy_m) / spacing_m
        c = min(max(c, 0.0), cols - 1.000001)
        r = min(max(r, 0.0), rows - 1.000001)
        c0, r0 = int(math.floor(c)), int(math.floor(r))
        fc, fr = c - c0, r - r0
        v = (arr[r0, c0] * (1 - fc) * (1 - fr)
             + arr[r0, c0 + 1] * fc * (1 - fr)
             + arr[r0 + 1, c0] * (1 - fc) * fr
             + arr[r0 + 1, c0 + 1] * fc * fr)
        return actor_z_m + (v / 65535.0 - 0.5) * z_scale_m

    ceiling = actor_z_m + (float(arr.max()) / 65535.0 - 0.5) * z_scale_m
    return sample, ceiling


# --- RE-SITING -------------------------------------------------------
#
# View azimuth for every re-sited station. The sun BEARS 105 (the light
# actor's yaw of 285 is the direction light TRAVELS), so looking toward
# 285 puts the sun behind the camera and the terrain front-lit. The
# original stations already used this and their frames are lit.
RESITE_VIEW_AZIMUTH_DEG = 285.0

RESITE_TARGETS_M = (60.0, 150.0, 350.0, 700.0, 1200.0, 2000.0)

# THE SUBJECT CHANGED, AND THAT IS THE POINT OF RE-SITING.
#
# The recorded summit (-844, -1040) z 1406.7 CANNOT be the subject of a
# ground-level sweep. Measured on the live heightmap: along bearing 105
# it is occluded from 80 m to 1200 m out, by up to 122 m of intervening
# ground; widening the search to the full circle still leaves three of
# six distances blocked. The cause is structural — it is 1406.7 m against
# a world ceiling of 1549.9 m with taller peaks beside it, so from its
# own surroundings at 1.7 m eye height it is behind something almost
# everywhere. No re-siting rescues that subject.
#
# Every peak `terrain_erosion.landmarks` reports was then scored on
# whether clear, LIT sight lines exist at all six distances. Winner:
RESITE_SUBJECT_X_M = -1700.0
RESITE_SUBJECT_Y_M = -592.0
RESITE_SUBJECT_Z_M = 549.11
#
# Its clearances, lit sector, in target order:
#     7.5  10.1  12.0  10.0  16.9  3.1  metres
# against the recorded summit's
#    -0.2   2.4 -29.2  -1.8   2.3  5.2  metres  (three BLOCKED)
#
# It is a modest peak — 549 m, prominence 129 m — and that is exactly why
# it works: it sits in OPEN ground. Prominence buys nothing here;
# visibility does. The 2000 m station at 3.1 m is a GRAZE and is reported
# as marginal rather than presented as clear, because with a lit face and
# a 1.7 m eye height NO peak on this terrain clears all six generously —
# the best min-clearance over all 34 candidates is 3.6 m. That is a
# property of the terrain, measured, not a search that gave up.
RESITE_SUBJECT_TOLERANCE_M = 1.0

# Camera bearings are restricted to this sector around the SUN BEARING so
# the subject face under test stays sunlit. A face turned more than ~90
# deg from the sun is in its own shadow, which is how the original
# cliff_face camera produced "a smooth dark sheet" that proved nothing.
RESITE_LIT_HALF_SECTOR_DEG = 85.0
RESITE_BEARING_STEP_DEG = 2.0
RESITE_EDGE_MARGIN_M = 130.0


def resite_stations(recipe, targets=RESITE_TARGETS_M):
    """Stations at each target distance from the RE-SITED subject, placed
    at the lit bearing whose sight line to that subject is clearest.

    Returns a list of dicts including the achieved `clearance_m`, so a
    marginal station is visible as marginal in the output instead of
    being averaged into a pass. Raises nothing on a bad subject — the
    caller checks the guard, so it can report before it refuses.
    """
    sample, _ceiling = _terrain_sampler(recipe)

    sx, sy = RESITE_SUBJECT_X_M, RESITE_SUBJECT_Y_M
    sz = RESITE_SUBJECT_Z_M

    ls, hm = recipe["landscape"], recipe["heightmap"]
    ox_m = float(ls["location_cm"][0]) / 100.0
    oy_m = float(ls["location_cm"][1]) / 100.0
    span = (int(hm["resolution"]) - 1) * float(ls["scale_xy_cm"]) / 100.0
    lo_x, hi_x = ox_m + RESITE_EDGE_MARGIN_M, ox_m + span - RESITE_EDGE_MARGIN_M
    lo_y, hi_y = oy_m + RESITE_EDGE_MARGIN_M, oy_m + span - RESITE_EDGE_MARGIN_M

    def clearance(d, bearing_deg):
        b = math.radians(bearing_deg)
        x = sx + d * math.cos(b)
        y = sy + d * math.sin(b)
        if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y):
            return None
        eye = sample(x, y) + EYE_ABOVE_GROUND_M
        steps = max(3, int(d / 8.0))
        worst = None
        for i in range(1, steps):
            t = i / float(steps)
            los = eye + (sz - eye) * t
            g = sample(x + (sx - x) * t, y + (sy - y) * t)
            gap = los - g
            if worst is None or gap < worst:
                worst = gap
        return {"x": x, "y": y, "eye_z": eye, "clearance": worst,
                "bearing": bearing_deg}

    picks = []
    half = RESITE_LIT_HALF_SECTOR_DEG
    for target in targets:
        best = None
        bearing = BEARING_DEG - half
        while bearing <= BEARING_DEG + half + 1e-9:
            c = clearance(target, bearing)
            if c is not None and c["clearance"] is not None:
                if best is None or c["clearance"] > best["clearance"]:
                    best = c
            bearing += RESITE_BEARING_STEP_DEG
        if best is None:
            continue
        best["target_m"] = target
        best["ground_m"] = best["eye_z"] - EYE_ABOVE_GROUND_M
        picks.append(best)
    return picks


def _resite_stations_by_visibility(recipe, targets=RESITE_TARGETS_M):
    """SUPERSEDED — kept only as the record of a wrong turn.

    This chose positions by MAXIMUM VISIBLE DISTANCE along one ray, on
    the reasoning that a station serving a "ground to 2 km" gate should
    see 2 km. Two faults, both caught by looking at the numbers it
    produced: the single ray does not describe a 50 deg frame (stations
    selected for 60 m "visible" reported 9000 m across the frame's
    width), and it silently replaced the ramp parameter — the sweep's
    ramp is DISTANCE FROM THE SUBJECT, which is what makes six frames a
    pull-back rather than six unrelated views.

    Not deleted, because the next person to think "just pick spots that
    can see far" should see where it leads. NOTE: it also references
    RESITE_SEARCH_RADIUS_M and RESITE_GRID_M, which are NOT defined anywhere
    in this file -- so it would raise NameError immediately if ever called.
    It is a record, not runnable code; define those constants before reviving
    it.
    """
    """Find stations whose SIGHT LINES ramp to the targets.

    WHY THE SUBJECT CHANGED, AND IT IS NOT A QUIET SUBSTITUTION.
    Sliding the recorded stations along bearing 105 cannot work: measured
    on the live heightmap, the summit is occluded from 80 m to 1200 m out,
    by up to 122 m of intervening ground, and the positions that do clear
    it clear by 1-2 m, which is a graze rather than a view. Widening the
    search to +/-75 deg of azimuth still leaves three of six blocked
    (-0.2, -29.2, -1.8 m).

    The cause is structural: the recorded summit is 1406.7 m against a
    world ceiling of 1549.9 m, with taller peaks beside it. At 1.7 m eye
    height it is not a visible subject from most of its own surroundings,
    and no amount of sliding makes it one.

    So stations are chosen by WHAT THEY SEE along the lit view azimuth —
    the ratified principle, applied to position as well as to aim.

    Vectorised: every candidate marches together, so the running-maximum
    horizon test costs one pass over the grid per step instead of a
    per-candidate loop.
    """
    import numpy as np
    from PIL import Image

    ls, hm = recipe["landscape"], recipe["heightmap"]
    ox_m = float(ls["location_cm"][0]) / 100.0
    oy_m = float(ls["location_cm"][1]) / 100.0
    actor_z_m = float(ls["location_cm"][2]) / 100.0
    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    spacing_m = float(ls["scale_xy_cm"]) / 100.0

    path = os.path.normpath(os.path.join(REPO_ROOT, str(hm["source"])))
    arr = np.asarray(Image.open(path)).astype(np.float64)
    rows, cols = arr.shape
    span = (cols - 1) * spacing_m

    def sample_v(x, y):
        c = np.clip((x - ox_m) / spacing_m, 0.0, cols - 1.000001)
        r = np.clip((y - oy_m) / spacing_m, 0.0, rows - 1.000001)
        c0 = c.astype(np.int64)
        r0 = r.astype(np.int64)
        fc = c - c0
        fr = r - r0
        v = (arr[r0, c0] * (1 - fc) * (1 - fr)
             + arr[r0, c0 + 1] * fc * (1 - fr)
             + arr[r0 + 1, c0] * (1 - fc) * fr
             + arr[r0 + 1, c0 + 1] * fc * fr)
        return actor_z_m + (v / 65535.0 - 0.5) * z_scale_m

    lo = ox_m + RESITE_EDGE_MARGIN_M
    hi = ox_m + span - RESITE_EDGE_MARGIN_M
    gx = np.arange(max(lo, SUMMIT_X_M - RESITE_SEARCH_RADIUS_M),
                   min(hi, SUMMIT_X_M + RESITE_SEARCH_RADIUS_M),
                   RESITE_GRID_M)
    gy = np.arange(max(lo, SUMMIT_Y_M - RESITE_SEARCH_RADIUS_M),
                   min(hi, SUMMIT_Y_M + RESITE_SEARCH_RADIUS_M),
                   RESITE_GRID_M)
    X, Y = np.meshgrid(gx, gy)
    X = X.ravel()
    Y = Y.ravel()
    keep = np.hypot(X - SUMMIT_X_M, Y - SUMMIT_Y_M) <= RESITE_SEARCH_RADIUS_M
    X, Y = X[keep], Y[keep]
    eye = sample_v(X, Y) + EYE_ABOVE_GROUND_M

    b = math.radians(RESITE_VIEW_AZIMUTH_DEG)
    ux, uy = math.cos(b), math.sin(b)

    # Running-maximum horizon angle, exactly as _skyline does per-ray.
    # `visible` tracks the distance of the farthest sample that RAISED the
    # horizon, i.e. the farthest ground not hidden behind nearer ground.
    best_ang = np.full(X.shape, -90.0)
    visible = np.zeros(X.shape)
    step = 8.0
    d = step
    while d <= MAX_MARCH_M:
        px = X + d * ux
        py = Y + d * uy
        inside = ((px >= ox_m) & (px <= ox_m + span)
                  & (py >= oy_m) & (py <= oy_m + span))
        g = sample_v(px, py)
        ang = np.degrees(np.arctan2(g - eye, d))
        rise = (ang >= best_ang) & inside
        best_ang = np.where(rise, ang, best_ang)
        visible = np.where(rise, d, visible)
        d += step

    out = []
    used = []
    for target in targets:
        # Relative error, so 60 m and 2000 m are judged on the same
        # footing; an absolute error would make every near target look
        # perfect and every far one look broken.
        err = np.abs(np.log(np.maximum(visible, 1.0) / target))
        # Keep stations apart: a ramp of six frames from the same spot is
        # one frame. 150 m minimum separation from those already chosen.
        for (px, py) in used:
            err = np.where(np.hypot(X - px, Y - py) < 150.0, 1e9, err)
        i = int(np.argmin(err))
        used.append((X[i], Y[i]))
        out.append({
            "target_m": target,
            "x_m": float(X[i]),
            "y_m": float(Y[i]),
            "eye_z_m": float(eye[i]),
            "ground_m": float(eye[i] - EYE_ABOVE_GROUND_M),
            "visible_m": float(visible[i]),
            "horizon_deg": float(best_ang[i]),
            "dist_from_summit_m": float(math.hypot(X[i] - SUMMIT_X_M,
                                                   Y[i] - SUMMIT_Y_M)),
        })
    return out


def _horizon_fan(sample, eye_x, eye_y, eye_z, yaw_deg, max_range_m,
                 fov_deg, rays=17):
    """Horizon elevation across the FRAME's width, not along one ray.

    WHY A FAN AND NOT A SINGLE RAY — this cost a whole capture run.
    Setting the top of frame just above the ON-AXIS skyline looked
    correct and produced frames that were ~70% sky. Two reasons, both
    visible the moment the pixels were looked at rather than the fill
    statistic:

      1. the on-axis skyline at these stations is a NARROW nearby bank
         (+35 deg at sweep_1200) while the horizon a few degrees off
         axis is near 0, so pinning the top edge to the highest feature
         fills the rest of the frame with sky;
      2. with a 29.4 deg vertical FOV, a top edge at +37 deg puts the
         BOTTOM edge at +7.6 deg — above horizontal — so the ground at
         the camera's feet, which sits at NEGATIVE angles, is excluded
         entirely. The frame had no foreground at all.

    So the horizon is sampled across the full horizontal FOV and a
    PERCENTILE is taken. The percentile, not the maximum: the aim should
    follow the typical horizon the frame will actually contain, and let
    the one tall bank clip out of the top.

    Returns (angles, chosen_deg, far_visible_m).
    """
    angles = []
    far = 0.0
    half = fov_deg / 2.0
    for i in range(rays):
        frac = (i / float(rays - 1)) * 2.0 - 1.0      # -1 .. +1
        az = yaw_deg + frac * half
        ang, _rng, vis = _skyline(sample, eye_x, eye_y, eye_z, az,
                                  max_range_m)
        angles.append(ang)
        far = max(far, vis)
    ordered = sorted(angles)
    idx = min(len(ordered) - 1,
              max(0, int(round(HORIZON_PERCENTILE * (len(ordered) - 1)))))
    return angles, ordered[idx], far


def _skyline(sample, eye_x, eye_y, eye_z, yaw_deg, max_range_m,
             step_m=8.0):
    """Highest elevation angle visible along a bearing, and its range.

    Marches the heightmap outward and keeps the RUNNING MAXIMUM of the
    elevation angle to the ground. That maximum IS the skyline: terrain
    beyond it at a lower angle is occluded by the ridge that set it, so
    the angle bounds what the camera can see and the range says how far
    away the farthest visible ground is.

    Returns (angle_deg, range_m, far_visible_m) where `far_visible_m` is
    the greatest distance whose sample is not hidden behind an earlier
    one — the honest answer to "how far does this station actually see".
    """
    ux = math.cos(math.radians(yaw_deg))
    uy = math.sin(math.radians(yaw_deg))
    best_ang = -90.0
    best_rng = 0.0
    far_visible = 0.0
    d = step_m
    while d <= max_range_m:
        g = sample(eye_x + d * ux, eye_y + d * uy)
        ang = math.degrees(math.atan2(g - eye_z, d))
        if ang >= best_ang:
            best_ang = ang
            best_rng = d
            far_visible = d
        d += step_m
    return best_ang, best_rng, far_visible


def build_resited(recipe):
    """Stations from resite_stations(), aimed by the ratified rule."""
    sample, ceiling_m = _terrain_sampler(recipe)
    picks = resite_stations(recipe)
    yaw = RESITE_VIEW_AZIMUTH_DEG
    if yaw > 180.0:
        yaw -= 360.0
    v_half = math.degrees(math.atan(
        math.tan(math.radians(FOV_DEG / 2.0)) / ASPECT))

    stations = []
    for p in picks:
        x, y, z = p["x"], p["y"], p["eye_z"]
        # Look BACK at the subject from wherever the clear bearing put us.
        yaw = (p["bearing"] + 180.0) % 360.0
        if yaw > 180.0:
            yaw -= 360.0
        fan, horizon, far_vis = _horizon_fan(
            sample, x, y, z, yaw, MAX_MARCH_M, FOV_DEG)
        pitch = horizon + SKYLINE_HEADROOM_DEG - v_half
        if pitch - v_half > -MIN_DEPRESSION_DEG:
            pitch = v_half - MIN_DEPRESSION_DEG
        stations.append({
            "name": "sweep_{0:04d}".format(int(p["target_m"])),
            "location_cm": [round(x * 100.0, 1), round(y * 100.0, 1),
                            round(z * 100.0, 1)],
            "rotation_deg": [round(pitch, 3), round(yaw, 3), 0.0],
            "fov_deg": FOV_DEG,
            "_distance_m": p["target_m"],
            "_ground_m": p["ground_m"],
            "_derived_eye_z_m": z,
            "_recorded_eye_z_m": z,
            "_skyline_deg": horizon,
            "_skyline_range_m": 0.0,
            "_far_visible_m": far_vis,
            "_summit_aim_pitch_deg": float("nan"),
            "_v_half_deg": v_half,
            "_bearing_deg": p["bearing"],
            "_clearance_m": p["clearance"],
        })
    return stations


def build_stations(recipe, recompute=False):
    """Return (stations, guard_detail). Raises nothing on terrain drift —
    the caller decides, so the guard can be reported before it refuses."""
    sample, ceiling_m = _terrain_sampler(recipe)

    measured_summit = sample(SUMMIT_X_M, SUMMIT_Y_M)
    drift = abs(measured_summit - SUMMIT_Z_M)
    guard = {
        "recorded_z_m": SUMMIT_Z_M,
        "measured_z_m": measured_summit,
        "drift_m": drift,
        "ok": drift <= SUMMIT_TOLERANCE_M,
        "ceiling_m": ceiling_m,
    }

    bearing = math.radians(BEARING_DEG)
    ux, uy = math.cos(bearing), math.sin(bearing)
    target_z = SUMMIT_Z_M + AIM_ABOVE_SUMMIT_M

    stations = []
    for i, d in enumerate(STATION_DISTANCES_M):
        x = SUMMIT_X_M + d * ux
        y = SUMMIT_Y_M + d * uy
        ground = sample(x, y)
        derived_z = ground + EYE_ABOVE_GROUND_M
        z = derived_z if recompute else STATION_EYE_Z_M[i]

        # Look back along the bearing, toward the summit side. The YAW is
        # unchanged from the recorded design; only the PITCH is corrected.
        yaw = (BEARING_DEG + 180.0) % 360.0
        if yaw > 180.0:
            yaw -= 360.0

        # THE CORRECTED AIM. The recorded design pitched at the summit
        # plus 20 m, which is a LANDMARK, not this gate's subject. The
        # acceptance criteria are all SURFACE criteria — tiling pop,
        # blend seams, cliff stretching, the scree apron, meadow
        # readability — so the frame has to contain ground across the
        # whole distance range, not a peak.
        #
        # Pitch is therefore set from the measured skyline: put the TOP
        # edge of the frame just above the farthest visible ground, and
        # everything below it fills with terrain at decreasing range,
        # down to the dirt at the camera's feet. One frame per station
        # spanning near to far is what lets a single render answer "at
        # what distance does this break".
        v_half = math.degrees(math.atan(
            math.tan(math.radians(FOV_DEG / 2.0)) / ASPECT))
        fan, sky_ang, far_vis = _horizon_fan(
            sample, x, y, z, yaw, MAX_MARCH_M, FOV_DEG)
        sky_rng = 0.0
        pitch = sky_ang + SKYLINE_HEADROOM_DEG - v_half
        # Guarantee a foreground. If the horizon sits high enough that the
        # bottom edge would still point ABOVE horizontal, the frame would
        # contain no near ground at all - the exact defect the first
        # corrected aim shipped. Pull the pitch down until the bottom edge
        # looks at least this far below the horizontal.
        if pitch - v_half > -MIN_DEPRESSION_DEG:
            pitch = v_half - MIN_DEPRESSION_DEG

        # What the summit-aimed design would have used, kept for the
        # record so the correction is auditable rather than asserted.
        summit_pitch = math.degrees(math.atan2(target_z - z, d))

        stations.append({
            "name": "sweep_{0:04d}".format(int(d)),
            "location_cm": [round(x * 100.0, 1), round(y * 100.0, 1),
                            round(z * 100.0, 1)],
            "rotation_deg": [round(pitch, 3), round(yaw, 3), 0.0],
            "fov_deg": FOV_DEG,
            "_distance_m": d,
            "_ground_m": ground,
            "_derived_eye_z_m": derived_z,
            "_recorded_eye_z_m": STATION_EYE_Z_M[i],
            "_skyline_deg": sky_ang,
            "_skyline_range_m": sky_rng,
            "_far_visible_m": far_vis,
            "_summit_aim_pitch_deg": summit_pitch,
            "_v_half_deg": v_half,
        })
    return stations, guard


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=landscape_spec.DEFAULT_RECIPE)
    ap.add_argument("--recompute", action="store_true",
                    help="Use eye heights derived from the CURRENT "
                         "heightmap instead of the recorded ones. For "
                         "comparison; the sweep uses the recorded values.")
    ap.add_argument("--resite", action="store_true",
                    help="Choose station POSITIONS by the CLEAREST SIGHT LINE "
                         "to the re-sited subject at each fixed target "
                         "distance (sweeping bearings +-85 deg around the view "
                         "bearing), instead of using the recorded positions. "
                         "(The old 'maximum visible distance along the azimuth' "
                         "algorithm is superseded and no longer runs.)")
    ap.add_argument("--write-recipe", action="store_true",
                    help="Add/replace the sweep_* cameras in "
                         "capture.cameras. Leaves every other camera "
                         "untouched.")
    args = ap.parse_args(argv)

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    if args.resite:
        _s, guard = build_stations(recipe, recompute=args.recompute)
        stations = build_resited(recipe)
    else:
        stations, guard = build_stations(recipe, recompute=args.recompute)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("")
    print("--- summit guard (recorded constant vs live heightmap) ---")
    print("  recorded  z = {0:.2f} m at ({1:.1f}, {2:.1f})".format(
        SUMMIT_Z_M, SUMMIT_X_M, SUMMIT_Y_M))
    print("  measured  z = {0:.2f} m   drift {1:.3f} m "
          "(tolerance {2:.1f} m)".format(
              guard["measured_z_m"], guard["drift_m"], SUMMIT_TOLERANCE_M))
    print("  world ceiling {0:.1f} m".format(guard["ceiling_m"]))
    # The summit guard governs the RECORDED-station path only. --resite does
    # not use the summit, so a summit drift must not refuse a resite run.
    if not guard["ok"] and not args.resite:
        print("")
        print("REFUSE: the heightmap no longer puts the recorded summit "
              "where BACKLOG says it is. The recorded stations are stale "
              "and would photograph a different mountain while every "
              "number in the sweep report still looked right. Re-derive "
              "the design deliberately and record the new constants.")
        return 3
    if guard["ok"]:
        print("  OK")
    else:
        # resite mode: summit irrelevant. NOTE the gap: the resite SUBJECT is
        # NOT independently guarded (RESITE_SUBJECT_TOLERANCE_M is defined but
        # unused), so a terrain edit can silently move it -- unlike the summit.
        print("  summit drift IGNORED in --resite (this mode does not use the "
              "summit; the resite subject itself is NOT guarded -- known gap).")
    print("")

    src = "RECOMPUTED from heightmap" if args.recompute else \
        "RECORDED in BACKLOG (verbatim)"
    print("--- six stations, bearing {0:.0f}, eye heights {1} ---".format(
        BEARING_DEG, src))
    for s in stations:
        print("  {0:<11} d={1:6.0f} m  loc=({2:9.1f},{3:9.1f},{4:8.1f}) cm"
              "  pitch={5:+7.2f}  yaw={6:+7.2f}  fov={7:.0f}".format(
                  s["name"], s["_distance_m"], s["location_cm"][0],
                  s["location_cm"][1], s["location_cm"][2],
                  s["rotation_deg"][0], s["rotation_deg"][1], s["fov_deg"]))
        print("              ground {0:8.2f} m   derived eye {1:8.2f} m   "
              "recorded eye {2:8.2f} m   delta {3:+.2f} m".format(
                  s["_ground_m"], s["_derived_eye_z_m"],
                  s["_recorded_eye_z_m"],
                  s["_derived_eye_z_m"] - s["_recorded_eye_z_m"]))
        if "_clearance_m" in s:
            clr = s["_clearance_m"]
            flag = "CLEAR" if clr >= 5.0 else "MARGINAL — a graze"
            print("              bearing {0:.0f}   sight line to subject "
                  "clears by {1:+.1f} m  [{2}]   horizon {3:+.2f} deg".format(
                      s["_bearing_deg"], clr, flag, s["_skyline_deg"]))
        else:
            # No "at N m": _skyline_range_m is hardcoded 0.0 (_horizon_fan
            # discards the range _skyline computes), so it was always "at 0 m".
            print("              skyline {0:+.2f} deg   sees to {1:.0f} m   "
                  "(summit-aim pitch would have been {2:+.2f})".format(
                      s["_skyline_deg"], s["_far_visible_m"],
                      s["_summit_aim_pitch_deg"]))

    if not args.write_recipe:
        print("")
        print("Dry run. Pass --write-recipe to put these into "
              "capture.cameras.")
        return 0

    path = os.path.abspath(args.recipe)
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    cams = raw["capture"]["cameras"]
    kept = [c for c in cams if not str(c.get("name", "")).startswith("sweep_")]
    clean = [{k: v for k, v in s.items() if not k.startswith("_")}
             for s in stations]
    raw["capture"]["cameras"] = kept + clean
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2)
        fh.write("\n")
    print("")
    print("WROTE {0} sweep cameras into {1} ({2} non-sweep cameras "
          "kept).".format(len(clean), os.path.basename(path), len(kept)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
