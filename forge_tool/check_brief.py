"""Semantic gate over an AUTHORED layout (brief + stamp placements).

Structured outputs guarantee the SHAPE of the model's answer; they cannot
express cross-references (acceptance.placement must name a placement) or
numeric ranges (JSON-schema numeric constraints are unsupported). This
module is that missing half, and it REUSES the pipeline's own validators —
brief_loop.validate_acceptance and brief_loop.lint_ordering — so the brief
author is gated by the same law the terrain loop enforces (one
declaration, not two lists).

check(layout, catalogue) raises Refuse with a list of every failure found
(all at once, so one repair round can fix them all), or returns the
normalized layout.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from brief_loop import Refuse, lint_ordering, validate_acceptance  # noqa: E402

# World frame ships fixed in v1: 1009 vertices at 4 m = 4032 m across,
# centred on the origin (the highland/canyon/coast frame). Placements and
# acceptance points must land inside it; edge clip is allowed for stamp
# EXTENT, not for centres.
WORLD_HALF_M = 2016.0
BLENDS = ("ADD", "MIN", "MAX")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pair(v):
    return (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v))


def check(layout, catalogue):
    """layout: {'brief': {...}, 'placements': [...]} as authored.
    catalogue: the loaded forge stamp catalogue dict.
    Raises Refuse listing every problem; returns layout when clean."""
    if not isinstance(layout, dict):
        raise Refuse("layout is not a JSON object")
    errs = []
    stamps = {m["hash"]: m for m in catalogue["maps"]}

    # The author's schema requires every key and uses null for "not
    # applicable" (structured outputs cannot express conditional
    # requirements). The pipeline's validators treat a PRESENT null as
    # malformed, so nulls are stripped here — in place, so downstream
    # consumers of the layout see the same normalized form the gate
    # validated (one artefact, not two).
    def _drop_nulls(obj):
        if isinstance(obj, dict):
            return {k: _drop_nulls(v) for k, v in obj.items()
                    if v is not None}
        if isinstance(obj, list):
            return [_drop_nulls(v) for v in obj]
        return obj

    if isinstance(layout.get("brief"), dict):
        b = layout["brief"]
        if isinstance(b.get("acceptance"), list):
            b["acceptance"] = _drop_nulls(b["acceptance"])
        if isinstance(b.get("lighting_geometry"), dict):
            b["lighting_geometry"] = _drop_nulls(b["lighting_geometry"])
    if isinstance(layout.get("placements"), list):
        layout["placements"] = [
            {k: v for k, v in p.items() if v is not None}
            if isinstance(p, dict) else p
            for p in layout["placements"]]

    brief = layout.get("brief")
    placements = layout.get("placements")
    if not isinstance(brief, dict):
        raise Refuse("layout has no 'brief' object")
    if not isinstance(placements, list) or not placements:
        raise Refuse("layout has no non-empty 'placements' list")

    # ---- placements -------------------------------------------------
    seen = set()
    for i, p in enumerate(placements):
        where = "placements[%d]" % i
        if not isinstance(p, dict):
            errs.append("%s is not an object" % where)
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not pid:
            errs.append("%s: missing string id" % where)
        elif pid in seen:
            errs.append("%s: duplicate id %r" % (where, pid))
        else:
            seen.add(pid)
        h = p.get("stamp_hash")
        if h not in stamps:
            errs.append("%s: stamp_hash %r not in the forge catalogue "
                        "(choose from the digest given)" % (where, h))
        if not _pair(p.get("centre_m")):
            errs.append("%s: centre_m must be [x, y] numbers" % where)
        elif max(abs(p["centre_m"][0]), abs(p["centre_m"][1])) > WORLD_HALF_M:
            errs.append("%s: centre_m outside the ±%.0f m world frame"
                        % (where, WORLD_HALF_M))
        if not _num(p.get("size_m")) or not 50.0 <= p["size_m"] <= 4200.0:
            errs.append("%s: size_m must be 50..4200" % where)
        if not _num(p.get("rotation_deg")) or not 0 <= p["rotation_deg"] < 360:
            errs.append("%s: rotation_deg must be 0..360" % where)
        if p.get("blend") not in BLENDS:
            errs.append("%s: blend must be one of %s" % (where, BLENDS))
        if not _num(p.get("amplitude_m")) or not 1.0 <= p["amplitude_m"] <= 1500.0:
            errs.append("%s: amplitude_m must be 1..1500" % where)
        if p.get("blend") in ("MIN", "MAX"):
            if not _num(p.get("anchor_m")) or not 0.0 <= p["anchor_m"] <= 1500.0:
                errs.append("%s: %s placements need anchor_m 0..1500 "
                            "(the surface's pinned elevation)"
                            % (where, p.get("blend")))

    # ---- brief ------------------------------------------------------
    ents = brief.get("terrain_entities")
    if not isinstance(ents, list) or not ents or not all(
            isinstance(e, dict) and isinstance(e.get("id"), str)
            and isinstance(e.get("read"), str) for e in ents):
        errs.append("brief.terrain_entities must be a non-empty list of "
                    "{id, read} objects")

    lg = brief.get("lighting_geometry")
    if not isinstance(lg, dict):
        errs.append("brief.lighting_geometry missing")
    else:
        for k, lo, hi in (("sun_elevation_deg", 0.0, 90.0),
                          ("sun_azimuth_deg", 0.0, 360.0)):
            if not _num(lg.get(k)) or not lo <= lg[k] <= hi:
                errs.append("lighting_geometry.%s must be %s..%s" % (k, lo, hi))
        if "sky_intensity" in lg and (
                not _num(lg["sky_intensity"])
                or not 0.1 <= lg["sky_intensity"] <= 2.0):
            errs.append("lighting_geometry.sky_intensity must be 0.1..2.0")
        if "fog_density_override" in lg and (
                not _num(lg["fog_density_override"])
                or not 0.0 <= lg["fog_density_override"] <= 0.01):
            errs.append("lighting_geometry.fog_density_override must be "
                        "0..0.01")

    cam = brief.get("render_camera")
    if not isinstance(cam, dict):
        errs.append("brief.render_camera missing")
    else:
        if not _pair(cam.get("at_m")) or max(
                abs(v) for v in cam.get("at_m", [9e9, 9e9])) > WORLD_HALF_M:
            errs.append("render_camera.at_m must be [x, y] inside the "
                        "±%.0f m frame" % WORLD_HALF_M)
        for k, lo, hi in (("height_above_ground_m", 2.0, 500.0),
                          ("pitch_deg", -89.0, 15.0),
                          ("yaw_deg", -180.0, 360.0),
                          ("fov", 30.0, 120.0)):
            if not _num(cam.get(k)) or not lo <= cam[k] <= hi:
                errs.append("render_camera.%s must be %s..%s" % (k, lo, hi))

    water = brief.get("water")
    if water is not None:
        if not isinstance(water, dict):
            errs.append("brief.water must be an object when present")
        else:
            if water.get("kind") not in ("lake", "sea", "river"):
                errs.append("water.kind must be lake|sea|river")
            if not _num(water.get("level_cm")) or not -50000 <= water[
                    "level_cm"] <= 150000:
                errs.append("water.level_cm must be -50000..150000")
            if not _pair(water.get("centre_cm")):
                errs.append("water.centre_cm must be [x, y] numbers (cm)")

    # ---- acceptance: the pipeline's own validators ------------------
    by_id = {p["id"]: p for p in placements
             if isinstance(p, dict) and isinstance(p.get("id"), str)}
    acc = brief.get("acceptance")
    try:
        validate_acceptance(acc, by_id)
    except Refuse as e:
        errs.append(str(e))
    else:
        # normalize for the ordering lint (it reads centre_m/size_m/blend)
        lintable = [p for p in placements if isinstance(p, dict)
                    and isinstance(p.get("id"), str)
                    and _pair(p.get("centre_m")) and _num(p.get("size_m"))
                    and p.get("blend") in BLENDS]
        if len(lintable) == len(placements):
            bad = lint_ordering(lintable, acc)
            for target, blocker in bad:
                errs.append("ordering: flat_site %r is carved before "
                            "non-MIN placement %r whose bbox covers it — "
                            "move the carve after it" % (target, blocker))

    if errs:
        raise Refuse("\n".join("- %s" % e for e in errs))
    return layout
