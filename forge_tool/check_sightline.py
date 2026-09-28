"""Camera sightline over the ADOPTED heightmap, before the editor pays
for a blocked vista.

The first duskhighland render (2026-09-03) framed a ridge instead of
the lake: the camera was geometrically valid and the subject simply not
visible. That failure is detectable in seconds on the heightmap —
march the ray from the camera to each acceptance target and compare
terrain height against the ray.

Target heights per kind:
    flat_site  ground at the target + 5 m (you must see the site floor)
    peak       the MEASURED maximum inside the acceptance box, minus
               5 m (calibrated 2026-09-03: aiming at the band's lower
               bound flagged the working overlook, whose ray grazed the
               basin rim 10.7 m below a summit that stands 66 m higher
               and renders fine — the target is the summit that EXISTS,
               not the minimum the band guarantees)

check(recipe, brief, repo) returns a list of blockage dicts (empty =
clear). The CLI refuses on any blockage BEFORE the editor phase, naming
the blocker's position and the camera height that would clear it —
actionable, not just "failed".
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

REPO_DEFAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DEFAULT, "scripts"))

CLEAR_MARGIN_M = 2.0    # ray must clear terrain by this much
NEAR_SKIP_M = 40.0      # ignore ground right at the camera's feet.
# Consequence (audit F5): rays shorter than 2*NEAR_SKIP_M are vacuously
# clear — a subject within 80 m of the camera is never flagged. The
# worst blockage reported per check is worst-by-overshoot, not
# worst-by-height-to-clear (a deliberate, calibrated choice).


def _terrain(recipe, repo):
    ls = recipe["landscape"]
    h = np.asarray(Image.open(
        os.path.join(repo, recipe["heightmap"]["source"])))
    if h.dtype != np.uint16:
        raise ValueError("adopted heightmap is not 16-bit")
    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    zoff_m = (float(ls["location_cm"][2])
              - float(ls["z_scale_cm"]) / 2.0) / 100.0
    hm = h.astype(np.float64) / 65535.0 * z_scale_m + zoff_m
    spacing = float(ls["scale_xy_cm"]) / 100.0
    ox = float(ls["location_cm"][0]) / 100.0
    oy = float(ls["location_cm"][1]) / 100.0
    return hm, spacing, ox, oy


def _sample(hm, spacing, ox, oy, x, y):
    r = int(round((y - oy) / spacing))
    c = int(round((x - ox) / spacing))
    if not (0 <= r < hm.shape[0] and 0 <= c < hm.shape[1]):
        return None
    return float(hm[r, c])


def check(recipe, brief, repo=REPO_DEFAULT):
    hm, spacing, ox, oy = _terrain(recipe, repo)
    cam = brief["render_camera"]
    cx, cy = cam["at_m"]
    cg = _sample(hm, spacing, ox, oy, cx, cy)
    if cg is None:
        return [{"check": "(camera)", "reason": "camera off the map"}]
    cz = cg + float(cam["height_above_ground_m"])

    # Frustum first (2026-09-03, coastforge attempt 5): the ray test
    # proves a subject is UNOCCLUDED, not that the camera LOOKS at it —
    # the coast camera passed every ray while facing 230 deg away from
    # the sea. Horizontal check only: bearing from camera to target
    # must sit inside yaw ± (fov/2 + margin). UE convention: yaw 0
    # faces +x, 90 faces +y (matches camera_args / the author prompt).
    # Margin calibrated on specimens, not taste: the duskhighland
    # village sat 43 deg off-axis on a 32 deg half-fov (11 deg beyond)
    # and still rendered acceptably at the frame edge; the coast misses
    # were 66 and 127 deg off. +12 deg admits the proven edge case and
    # flags the misses with room to spare.
    yaw = float(cam["yaw_deg"])
    half_fov = float(cam.get("fov", 60.0)) / 2.0 + 12.0
    blocked = []
    for c in brief.get("acceptance", []):
        tx, ty = c["at_m"]
        bearing = float(np.degrees(np.arctan2(ty - cy, tx - cx)))
        off = (bearing - yaw + 180.0) % 360.0 - 180.0
        if abs(off) > half_fov:
            blocked.append({
                "check": c["id"],
                "reason": "outside the camera frustum: bearing %.0f deg "
                          "vs yaw %.0f ± %.0f — aim the camera (yaw "
                          "%.0f would centre it)"
                          % (bearing, yaw, half_fov, bearing),
            })
            continue
        tg = _sample(hm, spacing, ox, oy, tx, ty)
        if tg is None:
            # authoring gate bounds at_m to the frame, so this is a
            # broken input, not a legitimate skip (audit F2)
            blocked.append({"check": c["id"],
                            "reason": "acceptance target off the map"})
            continue
        if c["kind"] == "peak":
            half = float(c["box_m"]) / 2.0
            r0 = int(round((ty - half - oy) / spacing))
            r1 = int(round((ty + half - oy) / spacing)) + 1
            c0 = int(round((tx - half - ox) / spacing))
            c1 = int(round((tx + half - ox) / spacing)) + 1
            box = hm[max(0, r0):max(0, r1), max(0, c0):max(0, c1)]
            tz = (float(box.max()) if box.size else tg) - 5.0
        else:
            tz = tg + 5.0
        dist = float(np.hypot(tx - cx, ty - cy))
        if dist < spacing * 2:
            continue
        n = max(8, int(dist / spacing))
        worst = None
        for i in range(1, n):
            t = i / float(n)
            px, py = cx + (tx - cx) * t, cy + (ty - cy) * t
            if dist * t < NEAR_SKIP_M or dist * (1 - t) < NEAR_SKIP_M:
                continue
            pz_ray = cz + (tz - cz) * t
            pz_ter = _sample(hm, spacing, ox, oy, px, py)
            if pz_ter is None:
                continue
            over = pz_ter - (pz_ray - CLEAR_MARGIN_M)
            if over > 0 and (worst is None or over > worst["over_m"]):
                # camera height that would lift the ray over this point:
                # solve cz' from  pz_ter + margin = cz' + (tz - cz')*t
                need_cz = ((pz_ter + CLEAR_MARGIN_M) - tz * t) / (1 - t)
                worst = {
                    "check": c["id"],
                    "blocked_at_m": [round(px, 1), round(py, 1)],
                    "dist_from_cam_m": round(dist * t, 1),
                    "terrain_m": round(pz_ter, 1),
                    "ray_m": round(pz_ray, 1),
                    "over_m": round(over, 1),
                    "camera_height_to_clear_m": round(need_cz - cg, 1),
                }
        if worst is not None:
            blocked.append(worst)
    return blocked
