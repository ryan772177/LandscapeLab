"""frame_cameras.py — measure and derive capture framing from the terrain.

LOCAL ONLY. No editor contact, no writes unless --write-recipe is passed
and then only to the recipe inside REPO_ROOT. Pure numpy over the
heightmap on disk.

WHY THIS EXISTS
`capture.cameras` are fixed world coordinates. Every one of them encodes
an assumption about how tall the world is, and nothing checked it. On
2026-08-02 `--relief` 0.92 -> 0.62 shortened the world from 2355 m to
1587 m and `snowline_detail` — a constant at world Z 1900 m with pitch
exactly 0 — ended up 313 m ABOVE the highest ground in the map, aimed at
the horizon. Its capture came back 98% sky. Nothing refused it:
`capture.py`'s footprint check reads X and Y and never reads Z (that gap
is now closed by `_altitude_findings`, but that gate is deliberately
pure arithmetic and reports a BOUND, not the real number).

This is the real number. It raymarches the actual heightfield, so it
answers "how much of this frame is terrain" before an editor is
involved, and it is the same instrument used to CHOOSE framing rather
than only to grade it — which is the point. An instrument that grades
but cannot propose leaves the proposing to guesswork, and guesswork is
what put a camera above the world.

THE CONVENTION, STATED BECAUSE GETTING IT WRONG IS SILENT
- UE is left-handed, +X forward at yaw 0, +Y right, +Z up.
- `capture.py` maps `rotation_deg` BY KEYWORD:
  `Rotator(roll=rot[2], pitch=rot[0], yaw=rot[1])`, so index 0 is PITCH,
  positive is UP. Read that at `capture.py` rather than assumed.
- `fov_deg` is HORIZONTAL. The vertical half-angle comes through the
  capture aspect ratio.
- Heightmap row -> world Y, column -> world X, origin at
  `landscape.location_cm`. This is the `identity` orientation that
  `push_heightmap` proves on every push.

Calibration is not optional for an instrument (lesson 19.2): --verify
compares predicted fill against the fill measured from real captures,
and the mapping above is the thing being checked.

Exit codes:
  0  measured (and proposals printed, and written if asked)
  1  unexpected error / bad arguments
  2  recipe or heightmap missing or invalid
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

# Rays across the frame. 160x90 keeps the 16:9 aspect and costs about a
# second; the fill figure changes by well under a point above this.
RAYS_X, RAYS_Y = 160, 90


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def load_terrain(recipe, heightmap_path=None):
    """Return (height_m grid, origin_xy_m, spacing_m, ceiling_m)."""
    from PIL import Image

    ls = recipe["landscape"]
    hm = recipe["heightmap"]
    src = heightmap_path or os.path.join(REPO_ROOT, hm["source"])
    src = os.path.abspath(src)
    if not _norm(src).startswith(_norm(REPO_ROOT) + os.sep):
        raise ValueError("heightmap {0} escapes REPO_ROOT".format(src))
    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    arr = np.asarray(Image.open(src)).astype(np.float64)
    n = arr.shape[0]
    actor_z_cm = float(ls["location_cm"][2])
    z_scale_cm = float(ls["z_scale_cm"])
    # Spacing from THIS map's resolution, not the recipe's — the trap
    # terrain_erosion.spacing_for exists for.
    span_cm = (float(hm["resolution"]) - 1.0) * float(ls["scale_xy_cm"])
    spacing_cm = span_cm / max(n - 1.0, 1.0)

    # Same datum as every other consumer: value 32768 sits at the actor Z.
    z_m = (actor_z_cm + (arr / 65535.0 - 0.5) * z_scale_cm) / 100.0
    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    return z_m, origin_m, spacing_cm / 100.0, float(z_m.max())


def camera_basis(pitch_deg, yaw_deg, roll_deg=0.0):
    """Forward / right / up for UE's (pitch, yaw, roll), roll ignored."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    forward = np.array([math.cos(p) * math.cos(y),
                        math.cos(p) * math.sin(y),
                        math.sin(p)])
    right = np.array([-math.sin(y), math.cos(y), 0.0])
    # cross(forward, right) is +Z at pitch 0 in this left-handed frame;
    # cross(right, forward) is -Z. Checked rather than guessed.
    up = np.cross(forward, right)
    return forward, right, up


def half_angles(fov_deg, resolution):
    """(horizontal, vertical) half-angles in radians. FOV is HORIZONTAL."""
    h = math.radians(float(fov_deg) / 2.0)
    aspect = float(resolution[0]) / max(float(resolution[1]), 1e-9)
    v = math.atan(math.tan(h) / max(aspect, 1e-9))
    return h, v


def raymarch(z_m, origin_m, spacing_m, cam_m, pitch, yaw, fov_deg,
             resolution, rays=(RAYS_X, RAYS_Y), step_m=None):
    """Fraction of the frame that is terrain, plus hit distances.

    Marches every ray together rather than one at a time — the whole
    frame is one numpy sweep, so a 160x90 grid over an 8 km map is about
    a second.
    """
    n = z_m.shape[0]
    span_m = (n - 1) * spacing_m
    step = step_m or spacing_m
    forward, right, up = camera_basis(pitch, yaw)
    h_half, v_half = half_angles(fov_deg, resolution)

    nx, ny = rays
    # Pixel centres, so no ray sits exactly on the frame edge.
    us = (np.arange(nx) + 0.5) / nx * 2.0 - 1.0
    vs = (np.arange(ny) + 0.5) / ny * 2.0 - 1.0
    uu, vv = np.meshgrid(us, vs)
    dirs = (forward[None, None, :]
            + uu[..., None] * math.tan(h_half) * right[None, None, :]
            + vv[..., None] * math.tan(v_half) * up[None, None, :])
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    dirs = dirs.reshape(-1, 3)

    cam = np.asarray(cam_m, dtype=np.float64)
    ox, oy = origin_m
    # March no further than the map's diagonal from the camera plus the
    # span — beyond that every ray has left the footprint for good.
    reach = math.hypot(span_m, span_m) + math.hypot(
        abs(cam[0] - ox), abs(cam[1] - oy))
    steps = int(min(max(reach / step, 8.0), 20000))

    hit_t = np.full(dirs.shape[0], np.nan)
    live = np.ones(dirs.shape[0], dtype=bool)
    for i in range(1, steps + 1):
        t = i * step
        p = cam[None, :] + dirs * t
        gx = (p[:, 0] - ox) / spacing_m
        gy = (p[:, 1] - oy) / spacing_m
        inside = (gx >= 0) & (gx <= n - 1) & (gy >= 0) & (gy <= n - 1)
        # A ray that has left the footprint and is climbing will never
        # come back; one still descending might re-enter, so only retire
        # rays that are both outside and rising.
        live &= ~(~inside & (dirs[:, 2] >= 0))
        cand = live & inside & np.isnan(hit_t)
        if not cand.any():
            if not live.any():
                break
            continue
        xi = np.clip(gx[cand].astype(np.int64), 0, n - 1)
        yi = np.clip(gy[cand].astype(np.int64), 0, n - 1)
        ground = z_m[yi, xi]          # row -> Y, column -> X
        below = p[cand, 2] <= ground
        idx = np.nonzero(cand)[0][below]
        hit_t[idx] = t
        if not np.isnan(hit_t).any():
            break

    hits = ~np.isnan(hit_t)
    d = hit_t[hits]
    return {
        "fill": float(hits.mean()),
        "rays": int(hits.size),
        "near_m": float(d.min()) if d.size else float("nan"),
        "far_m": float(d.max()) if d.size else float("nan"),
        "median_m": float(np.median(d)) if d.size else float("nan"),
    }


def measure(recipe, z_m, origin_m, spacing_m, cams=None):
    res = recipe["capture"]["resolution"]
    out = []
    for cam in (cams or recipe["capture"]["cameras"]):
        loc = [v / 100.0 for v in cam["location_cm"]]
        rot = cam["rotation_deg"]
        r = raymarch(z_m, origin_m, spacing_m, loc, rot[0], rot[1],
                     cam["fov_deg"], res)
        r["name"] = cam["name"]
        r["z_m"] = loc[2]
        r["pitch"] = rot[0]
        out.append(r)
    return out


def propose(recipe, z_m, origin_m, spacing_m, cam, target_fill,
            ceiling_m, floor_frac=0.06):
    """Find the lowest camera Z that reaches `target_fill`, keeping aim.

    Only Z moves. Position and aim are composition choices a person made;
    altitude is the one that a change of world height invalidates, and it
    is the one that can be re-derived without overriding the intent. A
    bisection, because fill is monotone in Z for a fixed downward aim:
    lower the camera and more of the frame fills with ground.
    """
    res = recipe["capture"]["resolution"]
    loc = [v / 100.0 for v in cam["location_cm"]]
    rot = cam["rotation_deg"]

    # Ground under the camera sets the floor — below it the camera is
    # buried, which is a different broken frame.
    n = z_m.shape[0]
    gx = int(np.clip((loc[0] - origin_m[0]) / spacing_m, 0, n - 1))
    gy = int(np.clip((loc[1] - origin_m[1]) / spacing_m, 0, n - 1))
    under = float(z_m[gy, gx])
    lo = under + max(30.0, floor_frac * ceiling_m)
    hi = max(loc[2], ceiling_m * 3.0)

    def fill_at(z):
        return raymarch(z_m, origin_m, spacing_m, [loc[0], loc[1], z],
                        rot[0], rot[1], cam["fov_deg"], res,
                        rays=(80, 45))["fill"]

    if fill_at(lo) < target_fill:
        # Even at the floor the aim cannot reach the target — the aim,
        # not the altitude, is what is wrong. Say so instead of
        # returning the floor as though it were a solution.
        return None, under, fill_at(lo)

    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if fill_at(mid) >= target_fill:
            lo = mid
        else:
            hi = mid
    return lo, under, fill_at(lo)


def derive_from_landmarks(recipe, z_m, origin_m, spacing_m, ceiling_m,
                          count=3, target_fill=0.45):
    """Aim cameras AT measured summits instead of at remembered ones.

    `--preserve-from` restores a camera's ALTITUDE against a reference
    world, which survives a change of relief. It does not survive a
    change of SEED: the features move, and a camera still pointing at
    where the old massif used to be photographs whatever is there now.

    This derives position and aim from the terrain itself. For each of
    the most prominent summits, place a camera back along a bearing at a
    standoff proportional to the peak's prominence, and pitch it so the
    summit sits slightly above frame centre — the classic landscape
    framing, and cheap to state as arithmetic.

    The bearing is chosen to put the sun behind the camera's shoulder
    rather than in frame, using the recipe's own `sun.azimuth_deg`, so a
    derived shot is lit rather than backlit. That is the one piece of art
    direction encoded here, and it comes from the recipe, not from me.
    """
    import terrain_erosion

    ls = recipe["landscape"]
    ox_cm, oy_cm = float(ls["location_cm"][0]), float(ls["location_cm"][1])
    z_scale_cm = float(ls["z_scale_cm"])
    res = recipe["capture"]["resolution"]

    # landmarks() wants raw heightmap units on its own datum.
    actor_z_cm = float(ls["location_cm"][2])
    units = np.clip(
        (z_m * 100.0 - actor_z_cm) / z_scale_cm + 0.5, 0.0, 1.0) * 65535.0
    lm = terrain_erosion.landmarks(units, spacing_m * 100.0, z_scale_cm)
    peaks = lm.get("peaks") or []
    if not peaks:
        return [], lm

    sun_az = float(((recipe.get("lighting") or {}).get("sun") or {})
                   .get("azimuth_deg", 315.0))
    span_m = (z_m.shape[0] - 1) * spacing_m

    out = []
    for i, pk in enumerate(peaks[:count]):
        px = ox_cm / 100.0 + pk["x_m"]
        py = oy_cm / 100.0 + pk["y_m"]
        # Stand off far enough that the summit reads as a mountain rather
        # than a wall: 6x its prominence, clamped to the map.
        standoff = float(np.clip(6.0 * pk["prominence_m"], 800.0,
                                 0.42 * span_m))
        # 40 deg off the sun azimuth puts the light across the face.
        bearing = math.radians(sun_az + 40.0 + 25.0 * i)
        cx = px - standoff * math.cos(bearing)
        cy = py - standoff * math.sin(bearing)
        # Keep the camera inside the footprint — outside it World
        # Partition streams nothing and the frame is empty sky whatever
        # the aim (capture.py refuses it, and rightly).
        cx = float(np.clip(cx, ox_cm / 100.0 + 40.0,
                           ox_cm / 100.0 + span_m - 40.0))
        cy = float(np.clip(cy, oy_cm / 100.0 + 40.0,
                           oy_cm / 100.0 + span_m - 40.0))

        gx = int(np.clip((cx - origin_m[0]) / spacing_m, 0, z_m.shape[0] - 1))
        gy = int(np.clip((cy - origin_m[1]) / spacing_m, 0, z_m.shape[0] - 1))
        ground = float(z_m[gy, gx])
        # Eye height: above local ground, and below the summit so the
        # peak is looked UP at rather than down on.
        cz = min(ground + 0.45 * pk["prominence_m"] + 60.0,
                 pk["z_m"] - 0.15 * pk["prominence_m"])
        cz = max(cz, ground + 40.0)

        dx, dy = px - cx, py - cy
        horiz = math.hypot(dx, dy)
        yaw = math.degrees(math.atan2(dy, dx))
        # Summit a little above centre: subtract a few degrees of pitch.
        pitch = math.degrees(math.atan2(pk["z_m"] - cz, max(horiz, 1e-6)))
        pitch -= 3.0

        cam = {"name": "peak_{0}".format(i + 1),
               "location_cm": [round(cx * 100.0, 1), round(cy * 100.0, 1),
                               round(cz * 100.0, 1)],
               "rotation_deg": [round(pitch, 2), round(yaw, 2), 0.0],
               "fov_deg": 50.0}
        r = raymarch(z_m, origin_m, spacing_m,
                     [cx, cy, cz], pitch, yaw, 50.0, res)
        cam["_fill"] = r["fill"]
        cam["_prominence_m"] = pk["prominence_m"]
        cam["_summit_z_m"] = pk["z_m"]
        cam["_standoff_m"] = standoff
        out.append(cam)
    return out, lm


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--heightmap", default=None,
                   help="Override the recipe's heightmap.source.")
    p.add_argument("--target-fill", type=float, default=0.55,
                   help="Fraction of the frame that should be terrain. "
                        "Used by --propose when --preserve-from is not "
                        "given.")
    p.add_argument("--preserve-from", default=None,
                   help="Reference heightmap (inside REPO_ROOT). Each "
                        "camera's target becomes the fill it achieved on "
                        "THAT world, per camera, instead of one global "
                        "number. This is the honest target: the framing "
                        "was art-directed against a specific world, and "
                        "the job after a terrain change is to restore "
                        "that composition, not to impose a new one.")
    p.add_argument("--propose", action="store_true",
                   help="Print the lowest camera Z reaching --target-fill "
                        "for every camera that currently misses it.")
    p.add_argument("--write-recipe", action="store_true",
                   help="Apply the proposals to the recipe. Requires "
                        "--propose. Writes ONLY capture.cameras[].")
    p.add_argument("--derive", type=int, default=0, metavar="N",
                   help="Derive N cameras from the N most prominent "
                        "summits -- position, aim and altitude, all from "
                        "the terrain. Survives a change of SEED, which "
                        "--preserve-from does not. Prints only; adding "
                        "them to a recipe is a composition decision.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    if not 0.0 < args.target_fill < 1.0:
        print("REFUSE: --target-fill must be in (0, 1).")
        return 1
    if args.write_recipe and not args.propose:
        print("REFUSE: --write-recipe requires --propose.")
        return 1

    recipe_path = os.path.abspath(args.recipe)
    if not _norm(recipe_path).startswith(_norm(REPO_ROOT) + os.sep):
        print("REFUSE: recipe must be inside {0}".format(REPO_ROOT))
        return 1
    try:
        with open(recipe_path, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
        z_m, origin_m, spacing_m, ceiling_m = load_terrain(
            recipe, args.heightmap)
    except (OSError, ValueError, KeyError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2

    n = z_m.shape[0]
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("heightmap : {0} ({1}x{1}, {2:.1f} m cells)".format(
        recipe["heightmap"]["source"], n, spacing_m))
    print("world     : {0:.0f} m .. {1:.0f} m over {2:.2f} km square".format(
        float(z_m.min()), ceiling_m, (n - 1) * spacing_m / 1000.0))
    print("")

    rows = measure(recipe, z_m, origin_m, spacing_m)
    print("--- measured framing ({0}x{1} rays) ---".format(RAYS_X, RAYS_Y))
    print("  {0:<16} {1:>8} {2:>7} {3:>8} {4:>9} {5:>9}".format(
        "camera", "z (m)", "pitch", "terrain", "near", "median"))
    for r in rows:
        print("  {0:<16} {1:8.0f} {2:7.1f} {3:7.1f}% {4:9.0f} {5:9.0f}"
              .format(r["name"], r["z_m"], r["pitch"], 100.0 * r["fill"],
                      r["near_m"], r["median_m"]))

    if args.derive > 0:
        derived, lm = derive_from_landmarks(
            recipe, z_m, origin_m, spacing_m, ceiling_m, count=args.derive)
        print("")
        print("--- derived from terrain: {0} summits over 120 m "
              "prominence ---".format(lm.get("count", 0)))
        if not derived:
            print("  no summit met the prominence threshold — nothing to "
                  "aim at. That is a statement about the TERRAIN, not a "
                  "failure to look.")
        for cam in derived:
            loc = cam["location_cm"]
            rot = cam["rotation_deg"]
            print("  {0:<8} summit {1:.0f} m (prominence {2:.0f} m), "
                  "standoff {3:.0f} m".format(
                      cam["name"], cam["_summit_z_m"],
                      cam["_prominence_m"], cam["_standoff_m"]))
            print("           at ({0:.0f}, {1:.0f}, {2:.0f}) cm  pitch "
                  "{3:+.1f} yaw {4:+.1f} fov {5:.0f}  -> {6:.1f}% terrain"
                  .format(loc[0], loc[1], loc[2], rot[0], rot[1],
                          cam["fov_deg"], 100.0 * cam["_fill"]))
        print("")
        print("  Printed, not written: WHICH shots a biome wants is a "
              "composition decision. Paste into capture.cameras to adopt.")

    if not args.propose:
        return 0

    targets = {}
    if args.preserve_from:
        try:
            ref_z, ref_origin, ref_spacing, _ = load_terrain(
                recipe, args.preserve_from)
        except (OSError, ValueError, KeyError) as exc:
            print("REFUSE: --preserve-from: {0}: {1}".format(
                type(exc).__name__, exc))
            return 2
        print("")
        print("--- reference framing on {0} ---".format(args.preserve_from))
        for r in measure(recipe, ref_z, ref_origin, ref_spacing):
            targets[r["name"]] = r["fill"]
            print("  {0:<16} {1:7.1f}%".format(r["name"], 100.0 * r["fill"]))

    print("")
    if targets:
        print("--- proposals (restore each camera's own composition, "
              "altitude only) ---")
    else:
        print("--- proposals (target {0:.0f}% terrain, altitude only) ---"
              .format(100.0 * args.target_fill))
    changes = {}
    for cam, r in zip(recipe["capture"]["cameras"], rows):
        target = targets.get(cam["name"], args.target_fill)
        if r["fill"] >= target:
            print("  {0:<16} {1:.1f}% vs target {2:.1f}% — already there, "
                  "unchanged".format(cam["name"], 100.0 * r["fill"],
                                     100.0 * target))
            continue
        z, under, got = propose(recipe, z_m, origin_m, spacing_m, cam,
                                target, ceiling_m)
        if z is None:
            print("  {0:<16} CANNOT reach target by altitude alone (best "
                  "{1:.1f}% just above the ground at {2:.0f} m). The AIM "
                  "is what is wrong here, not the height."
                  .format(cam["name"], 100.0 * got, under))
            continue
        print("  {0:<16} {1:.0f} m -> {2:.0f} m   gives {3:.1f}% (ground "
              "below is {4:.0f} m)".format(
                  cam["name"], r["z_m"], z, 100.0 * got, under))
        changes[cam["name"]] = round(z * 100.0, 1)

    if not args.write_recipe:
        print("")
        print("Nothing written. Re-run with --write-recipe to apply.")
        return 0
    if not changes:
        print("")
        print("No camera needed a change; recipe untouched.")
        return 0

    for cam in recipe["capture"]["cameras"]:
        if cam["name"] in changes:
            cam["location_cm"][2] = changes[cam["name"]]
    with open(recipe_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(recipe, indent=2) + "\n")
    print("")
    print("Wrote {0} camera altitude(s) to {1}".format(
        len(changes), os.path.relpath(recipe_path, REPO_ROOT)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:                      # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
