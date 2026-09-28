"""Import a Layout Author export (schema forge-layout/1) as a gated
forge layout.

The operator's three.js UI (forge_layout_author.html) is the visual
front-end for the keyless path: a human authors placements, acceptance
bands, camera and water against a live preview, and exports
*.layout.json. This module converts that schema into the forge's
{brief, placements} form and runs it through check_brief — the same
gate the AI author faces.

CONVERSIONS (each one is a measured convention, not a guess):

  axes      UI: east/+north.  Forge: +x east, NEGATIVE y = north
            (the proven-brief convention). y_forge = -north.
  frame     UI frame_m is authorable; the forge world is fixed 4032 m.
            All horizontal quantities scale by 4032/frame_m; heights
            do not scale.
  modes     UI preview: ADD adds amp*w; MAX/MIN pin toward an ABSOLUTE
            surface base_elevation + amp. Forge: ADD amplitude scales
            the stamp; MAX/MIN surface = anchor + s*amplitude. So a UI
            MAX at base+amp maps to anchor 0 / amplitude base+amp, and
            a UI MIN floor at base+amp maps to anchor base+amp /
            amplitude 25 (the proven carve-relief default).
  camera    UI: eye + look-at + VERTICAL fov. Forge: at_m + height
            above ground + pitch/yaw + HORIZONTAL fov.
            yaw = atan2(-dnorth, deast) in degrees (0 = east, matches
            camera_args); hfov = 2*atan(tan(vfov/2) * aspect).
            height_above_ground ~= eye_h - base_elevation (approximate;
            the sightline gate and relight iteration absorb the error).
  water     level_m*100 -> level_cm; centre flipped+scaled to cm;
            scale_xy = diameter in metres (plane is 1 m at scale 1;
            proven: highland 1500 covered its ~1500 m lake). Hex colour
            -> linear RGB via sRGB EOTF.
  stamps    Names matching forge catalogue tags pass through; UI
            built-in profile names map to the nearest surveyed tag.
  criteria  UI metrics -> forge kinds where expressible (peak_m ->
            peak, slope_core_deg -> flat_site); the rest are REPORTED
            as unmapped, never silently dropped. Subject placements
            without any criterion get a synthesized one so the camera
            gate has a target — synthesis is printed.

Usage:
    python -m forge_tool.import_layout <ui.layout.json> <concept image>
        [--out layout.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from analyse_concept import load_image, measure_for_brief  # noqa: E402
from brief_loop import Refuse  # noqa: E402
from forge_tool.check_brief import WORLD_HALF_M, check  # noqa: E402

FRAME_M = WORLD_HALF_M * 2.0

# UI built-in profile/stamp names -> forge catalogue tags
PROFILE_TO_TAG = {
    "massif": "mountain", "ridge": "ridges", "peak": "island_peak",
    "hill": "rise", "plateau": "mesa", "basin": "flat_pad",
    "valley": "basin", "cliff": "terraces", "foothills": "hills",
}
CARVE_RELIEF_M = 25.0  # proven MIN carve relief default


def _srgb_to_linear(hexcol):
    h = str(hexcol).lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise Refuse("water.color %r is not #RRGGBB" % (hexcol,))
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(round(c / 12.92 if c <= 0.04045
                         else ((c + 0.055) / 1.055) ** 2.4, 4))
    return out


def convert(ui, image_path, aspect=None):
    if ui.get("schema") != "forge-layout/1":
        raise Refuse("not a Layout Author export (schema %r)"
                     % ui.get("schema"))
    frame = float(ui.get("frame_m") or 4000.0)
    base = float(ui.get("base_elevation_m") or 0.0)
    s = FRAME_M / frame
    notes = []

    # SHAPE first (audit 2026-09-03): operator-authored JSON must refuse
    # with the missing field named, never KeyError through to a traceback
    cam = ui.get("camera")
    if not isinstance(cam, dict):
        raise Refuse("layout has no camera object")
    for fld in ("position_m", "look_at_m"):
        v = cam.get(fld)
        if not (isinstance(v, (list, tuple)) and len(v) == 3):
            raise Refuse("camera.%s must be [east_m, north_m, height_m]"
                         % fld)
    for i, p in enumerate(ui.get("placements", [])):
        if not isinstance(p, dict):
            raise Refuse("placement %d is not an object" % (i + 1))
        who = p.get("label") or p.get("id") or ("placement %d" % (i + 1))
        for fld in ("stamp", "amplitude_m", "size_m"):
            if fld not in p:
                raise Refuse("%s is missing %r" % (who, fld))
        c = p.get("centre_m")
        if not (isinstance(c, (list, tuple)) and len(c) == 2):
            raise Refuse("%s: centre_m must be [east_m, north_m]" % who)

    cat = json.load(open(os.path.join(
        REPO, "recipes", "forge_stamps_catalogue.json"), encoding="utf-8"))
    tag_to_hash = {m["tag"]: m["hash"] for m in cat["maps"]}

    def flip(e, n):
        return [round(e * s, 1), round(-n * s, 1)]

    # ---- placements -------------------------------------------------
    placements, pl_index = [], {}
    for p in ui.get("placements", []):
        tag = p["stamp"] if p["stamp"] in tag_to_hash \
            else PROFILE_TO_TAG.get(p["stamp"])
        if tag is None:
            raise Refuse("placement %r uses stamp %r, which is neither a "
                         "forge tag nor a known UI profile"
                         % (p.get("label"), p.get("stamp")))
        amp = float(p["amplitude_m"])
        mode = p.get("mode", "ADD")
        entry = {
            "id": (p.get("label") or p.get("id") or tag)
            .strip().lower().replace(" ", "_"),
            "stamp_hash": tag_to_hash[tag],
            "centre_m": flip(*p["centre_m"]),
            "size_m": round(float(p["size_m"]) * s, 1),
            "rotation_deg": float(p.get("heading_deg", 0.0)) % 360.0,
            "blend": mode,
        }
        if mode == "ADD":
            if amp < 0:  # a negative ADD is a carve by intent
                entry["blend"] = "MIN"
                entry["anchor_m"] = round(max(0.0, base + amp), 1)
                entry["amplitude_m"] = CARVE_RELIEF_M
                notes.append("%s: negative ADD converted to MIN floor "
                             "%.1f m" % (entry["id"], entry["anchor_m"]))
            else:
                entry["amplitude_m"] = round(amp, 1)
        elif mode == "MAX":
            entry["anchor_m"] = 0.0
            entry["amplitude_m"] = round(max(1.0, base + amp), 1)
        else:  # MIN: absolute floor at base+amp
            entry["anchor_m"] = round(max(0.0, base + amp), 1)
            entry["amplitude_m"] = CARVE_RELIEF_M
        # id collisions bind criteria to the WRONG geometry silently
        # (audit 2026-09-03): refuse rather than last-wins
        for key in {p.get("id"), entry["id"]} - {None}:
            if key in pl_index and pl_index[key] is not entry:
                raise Refuse("duplicate placement id %r — give each "
                             "placement a unique label" % key)
        placements.append(entry)
        if p.get("id") is not None:
            pl_index[p.get("id")] = entry
        pl_index[entry["id"]] = entry
    if not placements:
        raise Refuse("the layout has no placements")

    # ---- acceptance -------------------------------------------------
    acceptance, covered = [], set()
    for c in ui.get("acceptance", []):
        tgt = pl_index.get(c.get("target"))
        if tgt is None:
            notes.append("criterion on %r unmapped (frame-wide or "
                         "unknown target)" % c.get("target"))
            continue
        metric, mn, mx = c.get("metric"), c.get("min"), c.get("max")
        if metric == "peak_m" and (mn is not None or mx is not None):
            lo = mn if mn is not None else (mx or 0) * 0.45
            hi = mx if mx is not None else lo * 2.2
            acceptance.append({
                "id": tgt["id"] + "_peak", "kind": "peak",
                "placement": tgt["id"], "at_m": tgt["centre_m"],
                "box_m": min(tgt["size_m"] * 0.5, 800.0),
                "max_elev_m": [round(lo, 1), round(hi, 1)]})
            covered.add(tgt["id"])
        elif metric in ("slope_core_deg", "slope_max_deg") \
                and mx is not None:
            if tgt["blend"] == "MIN":
                lo, hi = tgt["anchor_m"], tgt["anchor_m"] + 20.0
            elif tgt["blend"] == "MAX":
                lo, hi = tgt["amplitude_m"] - 10.0, \
                    tgt["amplitude_m"] + 30.0
            else:
                lo, hi = 0.0, base + abs(tgt["amplitude_m"]) + 50.0
            acceptance.append({
                "id": tgt["id"] + "_flat", "kind": "flat_site",
                "placement": tgt["id"], "at_m": tgt["centre_m"],
                "box_m": min(tgt["size_m"] * 0.35, 500.0),
                "elev_m": [round(max(0.0, lo), 1), round(hi, 1)],
                "slope_mean_deg_max": float(mx)})
            covered.add(tgt["id"])
        else:
            notes.append("criterion %s on %s unmapped (no forge kind "
                         "expresses it)" % (metric, tgt["id"]))

    # subjects need an acceptance entry: the camera gate keys off them
    for p in ui.get("placements", []):
        if not p.get("subject"):
            continue
        e = pl_index[p.get("id")]
        if e["id"] in covered:
            continue
        if e["blend"] == "ADD":
            amp = e["amplitude_m"]
            acceptance.append({
                "id": e["id"] + "_peak", "kind": "peak",
                "placement": e["id"], "at_m": e["centre_m"],
                "box_m": min(e["size_m"] * 0.5, 800.0),
                "max_elev_m": [round(amp * 0.5, 1), round(amp * 2.2, 1)]})
        else:
            lvl = e["anchor_m"] if e["blend"] == "MIN" \
                else e["amplitude_m"]
            acceptance.append({
                "id": e["id"] + "_flat", "kind": "flat_site",
                "placement": e["id"], "at_m": e["centre_m"],
                "box_m": min(e["size_m"] * 0.35, 500.0),
                "elev_m": [round(max(0.0, lvl - 10.0), 1),
                           round(lvl + 25.0, 1)],
                "slope_mean_deg_max": 6.0})
        notes.append("synthesized acceptance for subject %s" % e["id"])
        covered.add(e["id"])
    if not acceptance:
        raise Refuse("no acceptance criteria survived conversion — add "
                     "bands (or mark subjects) in the Layout Author")

    # ---- camera -----------------------------------------------------
    cam = ui["camera"]
    pe, pn, ph = cam["position_m"]
    te, tn, th = cam["look_at_m"]
    de, dn, dh = te - pe, tn - pn, th - ph
    yaw = math.degrees(math.atan2(-dn, de))
    horiz = math.hypot(de, dn)
    pitch = math.degrees(math.atan2(dh, max(horiz, 1e-6)))
    if aspect is None:
        _, _, _, ih, iw = load_image(image_path)
        aspect = iw / float(ih)
    vfov = math.radians(float(cam.get("fov_deg", 45.0)))
    hfov = math.degrees(2.0 * math.atan(math.tan(vfov / 2.0) * aspect))
    render_camera = {
        "at_m": flip(pe, pn),
        "height_above_ground_m": max(2.0, min(500.0, ph - base)),
        "pitch_deg": max(-89.0, min(15.0, round(pitch, 1))),
        "yaw_deg": round(yaw, 1),
        "fov": max(30.0, min(120.0, round(hfov, 1))),
    }

    # ---- water ------------------------------------------------------
    water = None
    w = ui.get("water") or {}
    if w.get("present"):
        if w.get("extent") == "radius":
            ce, cn = w.get("centre_m", [0, 0])
            centre = [v * 100.0 for v in flip(ce, cn)]
            dia = max(200.0, 2.0 * float(w.get("radius_m", 600.0)) * s)
        else:
            centre, dia = [0.0, 0.0], 4100.0
        water = {
            "kind": "lake", "label": "WaterPlane_import",
            "centre_cm": [round(v, 1) for v in centre],
            "level_cm": round(float(w.get("level_m", 0.0)) * 100.0, 1),
            "scale_xy": [round(dia, 1)] * 2,
            "color_linear": _srgb_to_linear(w.get("color", "#3e6f7a")),
            "roughness": 0.05, "opacity": 0.75,
        }

    fog = ui.get("fog") or {}
    sun = ui.get("sun") or {}
    layout = {
        "brief": {
            "terrain_entities": [
                {"id": (e.get("name") or "entity").strip().lower()
                 .replace(" ", "_"), "read": e.get("description", "")}
                for e in ui.get("terrain_entities", [])] or
            [{"id": "scene", "read": "imported Layout Author scene"}],
            "lighting_geometry": {
                "sun_elevation_deg": float(sun.get("elevation_deg", 30.0)),
                "sun_azimuth_deg": float(sun.get("azimuth_deg", 180.0)),
                "fog_height_datum_m": float(fog.get("datum_m", 30.0)),
                "fog_half_height_m": float(fog.get("height_m", 60.0)),
                "sky_intensity": 1.0,
                "fog_density_override": None,
            },
            "acceptance": acceptance,
            "render_camera": render_camera,
            "water": water,
        },
        "placements": placements,
    }
    cat_full = json.load(open(os.path.join(
        REPO, "recipes", "forge_stamps_catalogue.json"), encoding="utf-8"))
    layout = check(layout, cat_full)
    layout["brief"]["lighting_measured"] = measure_for_brief(image_path)
    layout["brief"]["source_image"] = os.path.relpath(
        os.path.abspath(image_path), REPO).replace("\\", "/")
    return layout, notes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ui_layout")
    ap.add_argument("image", help="the concept image (measured lighting)")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        ui = json.load(open(a.ui_layout, encoding="utf-8"))
        layout, notes = convert(ui, a.image)
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    for n in notes:
        print("note: %s" % n)
    out = a.out or (os.path.splitext(a.ui_layout)[0] + ".forge.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=1)
        f.write("\n")
    print("converted + GATED: %s  (%d placements, %d acceptance)"
          % (out, len(layout["placements"]),
             len(layout["brief"]["acceptance"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
