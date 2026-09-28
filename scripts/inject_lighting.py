"""inject_lighting.py — write a concept's measured mood into a recipe's
lighting block.

Reads the layout BRIEF (analyse_concept measurements + hand-read sun
geometry) and the concept IMAGE (direct sky sample), and writes the
RECIPE's lighting.sun / fog / sky fields. Every field is labelled by claim
class, R-DERIVEMAT's split:

    MEASURED   sky colour — top-of-frame mean, decoded sRGB->LINEAR before
               averaging, because the consumer (apply_lighting.py:278-287)
               declares "recipe colours are linear" and encodes them
               itself; averaging the raw bytes would double-encode (audit
               2026-08-31 finding 1). Haze strength (min-luma rise) from
               the brief's stored analyse_concept run.
    AUTHORED   the mapping curves below (warmth -> kelvin, haze -> fog
               density), and the half_height = 2*datum fallback. v0
               heuristics, stated, not fitted.
    HAND-READ  sun elevation/azimuth: geometry a human read off the image
               into brief.lighting_geometry. A camera solve could derive
               azimuth later; v0 does not pretend to.
    PORTED     exposure.compensation_ev is NOT touched (alpine_8k's own
               block documents why porting an exposure solve is wrong).
    STALE, DELIBERATELY (audit finding 3 — the full list, not just
    exposure): sun.intensity_lux, sun.light_shaft_bloom, sky.type,
    sky.intensity, fog.enabled, fog.start_distance_m, fog.volumetric all
    keep the recipe's prior values. Intensity is the big one: a moonlit
    concept still renders at the recipe's daylight lux — day-for-night is
    a v0 limitation, stated, not hidden.

Refuses (exit 2) when the brief lacks `lighting_geometry` or the recipe
lacks a `lighting` block — a partial injection would be a silently mixed
mood. Writes ONLY inside the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), ".."))


class Refuse(Exception):
    pass


def _inside_repo(path):
    p = os.path.abspath(path)
    return os.path.commonprefix([p, REPO + os.sep]) == REPO + os.sep


def kelvin_from_warmth(rb_split):
    """AUTHORED v0 curve: sunlit-band R-B split -> colour temperature.
    +0.05 (strong golden hour) -> 5000 K; 0 (neutral) -> 6500 K;
    -0.05 (cool/overcast/moonlit) -> 8000 K. Linear between, clamped."""
    k = 6500.0 - rb_split * 30000.0
    return float(min(8500.0, max(4500.0, k)))


def fog_from_haze(minluma_rise):
    """AUTHORED v0 curve: far-vs-near min-luma rise -> exponential fog
    density. alpine_8k ships 0.0015 and reads as moderate haze; the
    crystal-valley concept measures a rise of ~0.064 and reads strong.
    Map rise 0.03 -> 0.0015 (moderate), 0.10 -> 0.004 (heavy), linear,
    clamped to [0.0008, 0.005]."""
    d = 0.0015 + (minluma_rise - 0.03) * (0.004 - 0.0015) / 0.07
    return float(min(0.005, max(0.0008, d)))


def sample_sky(image_path):
    """MEASURED: mean LINEAR RGB of the top 12% of the frame. The bytes are
    sRGB-encoded; decode per IEC 61966-2-1 BEFORE averaging (the mean of
    encoded values is not the encoding of the mean)."""
    im = np.asarray(Image.open(image_path).convert("RGB")).astype(np.float64)
    band = im[: max(1, int(im.shape[0] * 0.12))] / 255.0
    lin = np.where(band <= 0.04045, band / 12.92,
                   ((band + 0.055) / 1.055) ** 2.4)
    return [round(float(lin[..., i].mean()), 4) for i in range(3)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--brief", required=True)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    try:
        recipe_path = os.path.abspath(a.recipe)
        if not _inside_repo(recipe_path):
            raise Refuse("recipe %s escapes REPO_ROOT" % recipe_path)
        with open(os.path.abspath(a.brief), encoding="utf-8") as fh:
            brief = json.load(fh)
        with open(recipe_path, encoding="utf-8") as fh:
            recipe = json.load(fh)

        geo = brief.get("lighting_geometry")
        if not isinstance(geo, dict):
            raise Refuse("brief has no lighting_geometry object (needs "
                         "sun_elevation_deg, sun_azimuth_deg, hand-read "
                         "off the image with provenance)")
        for k in ("sun_elevation_deg", "sun_azimuth_deg"):
            if not isinstance(geo.get(k), (int, float)):
                raise Refuse("lighting_geometry.%s missing or non-numeric" % k)
        meas = brief.get("lighting_measured")
        if not isinstance(meas, dict):
            raise Refuse("brief has no lighting_measured block")
        lt = recipe.get("lighting")
        if not isinstance(lt, dict):
            raise Refuse("recipe has no lighting block")
        for key in ("sun", "fog", "sky"):
            if not isinstance(lt.get(key), dict):
                raise Refuse("recipe lighting.%s missing or not an object; "
                             "a partial injection would be a silently "
                             "mixed mood" % key)

        # An override exists for instrument-contaminated reads (the coast
        # brief's rb split caught the glowing sea, not sunlit ground); the
        # override is HAND-READ and its provenance lives in the brief.
        rb = meas.get("sunlit_rb_split_override",
                      meas.get("sunlit_rb_split"))
        rise = meas.get("minluma_rise")
        if not isinstance(rb, (int, float)) or not isinstance(
                rise, (int, float)):
            raise Refuse("brief.lighting_measured needs numeric "
                         "sunlit_rb_split and minluma_rise (from "
                         "analyse_concept; store them explicitly)")
        sky_rgb = sample_sky(os.path.abspath(a.image))
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    except (OSError, ValueError) as e:
        print("REFUSE: unreadable inputs: %r" % e)
        return 2

    lt["sun"]["elevation_deg"] = float(geo["sun_elevation_deg"])
    lt["sun"]["azimuth_deg"] = float(geo["sun_azimuth_deg"])
    lt["sun"]["temperature_kelvin"] = kelvin_from_warmth(rb)
    lt["fog"]["density"] = fog_from_haze(rise)
    # AUTHORED overrides for moods the v0 curves cannot express (the
    # day-for-night case: daylight lux through night fog washes the frame
    # white). Optional; absent means the stale-field policy above applies.
    # NOT sun.intensity_lux: apply_lighting's schema refused that route —
    # the field is the TOP-OF-ATMOSPHERE solar constant and the engine
    # attenuates it itself; "make the scene dimmer" belongs to exposure
    # compensation (its own schema note, verified 2026-09-01).
    for src, dst_obj, dst_key in (
            ("exposure_compensation_ev_override",
             lt.setdefault("exposure", {}), "compensation_ev"),
            ("sky_intensity", lt["sky"], "intensity"),
            ("fog_density_override", lt["fog"], "density")):
        if isinstance(geo.get(src), (int, float)):
            dst_obj[dst_key] = float(geo[src])
            print("override %s -> %s (AUTHORED, from brief)" % (src,
                                                               geo[src]))
    datum_note = "datum UNCHANGED (brief lacks fog_height_datum_m)"
    if isinstance(geo.get("fog_height_datum_m"), (int, float)):
        lt["fog"]["height_datum_m"] = float(geo["fog_height_datum_m"])
        # half_height fallback 2*datum is AUTHORED (see docstring)
        lt["fog"]["half_height_m"] = float(
            geo.get("fog_half_height_m", geo["fog_height_datum_m"] * 2.0))
        datum_note = "datum %.1f m (injected)" % lt["fog"]["height_datum_m"]
    lt["sky"]["color"] = sky_rgb

    print("sun    elev %.1f deg  azim %.1f deg  %.0f K (rb split %+.3f)"
          % (lt["sun"]["elevation_deg"], lt["sun"]["azimuth_deg"],
             lt["sun"]["temperature_kelvin"], rb))
    print("fog    density %.5f (min-luma rise %.3f)  %s"
          % (lt["fog"]["density"], rise, datum_note))
    print("sky    color %s (MEASURED linear, top 12%% of frame)" % sky_rgb)
    print("exposure compensation UNTOUCHED: %s (ported approximation; see "
          "alpine_8k _solve_caveat)" % lt.get("exposure", {}).get(
              "compensation_ev"))
    if a.dry_run:
        print("DRY RUN — recipe not written.")
        return 0
    with open(recipe_path, "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("written to %s" % os.path.relpath(recipe_path, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
