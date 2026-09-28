"""Author a layout brief from ONE concept image, via Claude vision.

This automates the one pipeline stage that was still done by eye: reading
a 2D concept into (a) terrain entities, (b) stamp placements, (c)
acceptance criteria, (d) lighting geometry, (e) a render camera, and
optionally (f) a water plane.

Division of labour is deliberate and asymmetric:
  MEASURED  lighting_measured (sunlit_rb_split, minluma_rise, sunlit_rgb)
            comes from scripts/analyse_concept.measure_for_brief — a
            measurement, injected AFTER the call. The model is never asked
            for numbers a script can measure.
  READ      everything else is the model's reading of the image, gated by
            forge_tool/check_brief.py (which reuses brief_loop's own
            validators) with a bounded repair loop: max 2 repair rounds,
            then a hard refusal (a cap hit is a refusal, not a retry).

No API credentials -> refusal with instructions; the STANDARD path is
keyless (`forge author` + `build --layout`, ruled 2026-09-04) and this
module is the optional, untested extra. There is deliberately NO heuristic vision
fallback: a schema-valid-but-wrong brief is the plausible-artefact
failure class this repo guards against.

Usage:
    python -m forge_tool.brief_author <image> --out <layout.json>
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from analyse_concept import measure_for_brief  # noqa: E402
from brief_loop import Refuse  # noqa: E402
from forge_tool.check_brief import WORLD_HALF_M, check  # noqa: E402

MODEL = "claude-opus-5"
MAX_REPAIRS = 2
CATALOGUE = os.path.join(REPO, "recipes", "forge_stamps_catalogue.json")

# Proven brief/recipe pairs used as few-shot examples. Placements are
# lifted from each recipe's stamps block with vendor identity replaced by
# the stamp's character (the examples used Fab stamps the forge cannot
# name; the model must choose from the digest instead).
EXAMPLES = [
    ("alpine valley village, midday",
     "_verify/20260831_spike_photo2landscape/layout_brief.json",
     "_verify/20260831_spike_photo2landscape/spike_photo2landscape.json"),
    ("rocky coast harbour, low sun",
     "_verify/20260831_coast_benchmark/layout_brief.json",
     "_verify/20260831_coast_benchmark/coast_bench.json"),
    ("desert canyon, hard light",
     "_verify/20260901_overnight/canyon_brief.json",
     "_verify/20260901_overnight/canyon.json"),
    ("highland lake at dusk",
     "_verify/20260901_overnight/highland_lake_brief.json",
     "_verify/20260901_overnight/highland_lake.json"),
]

_WORLD_M = int(WORLD_HALF_M * 2)  # one declaration: check_brief owns it

SYSTEM = """You turn ONE landscape concept image into a machine-readable \
layout for a terrain pipeline. Output exactly the JSON the schema allows.

World frame: a %(w)d m x %(w)d m heightmap centred on the origin. \
Coordinates are metres; +x is east, NEGATIVE y is north (matches every \
example). Elevations are metres above the terrain datum.

Placements build the terrain, applied IN ORDER onto a gentle procedural \
base:
- blend ADD raises terrain: the stamp's relief is scaled to amplitude_m \
and added over a size_m x size_m footprint with soft falloff.
- blend MAX raises terrain TO a surface: anchor_m + amplitude_m x stamp \
is a level the terrain cannot fall below. Pair with the mesa stamp for a \
flat site on sloped ground (anchor_m 0, amplitude_m = the plateau \
elevation, set ABOVE the local terrain so the whole site flattens — the \
adjustment loop cannot repair a plateau set below the flank it sits on, \
so aim near the TOP of the site's acceptance elev band).
- blend MIN carves DOWN to a floor: anchor_m is the floor elevation, \
amplitude_m the carve's relief depth above that floor. A MIN carve must \
be ordered AFTER any overlapping ADD placement, or the ADD fills it back \
in (the gate refuses that ordering).
Choose each placement's stamp_hash from the STAMP DIGEST by character.

Acceptance criteria are what the terrain loop will enforce by probing the \
built heightmap:
- kind "flat_site": a site the camera story needs flat-ish; fields \
placement (the placement id that shapes it), at_m, box_m, elev_m \
[lo, hi], slope_mean_deg_max.
- kind "peak": a summit band; fields placement, at_m, box_m, max_elev_m \
[lo, hi].
Every acceptance entry's "placement" must be one of your placement ids.

Lighting: give geometry only (sun_elevation_deg, sun_azimuth_deg \
compass-style 0=N 90=E, fog datum/half-height, sky_intensity, \
fog_density_override). Colour temperature and exposure are derived from \
measurements a script makes; never invent them.

render_camera: place it to reproduce the concept's framing. A sightline \
check runs on the BUILT terrain and refuses a camera whose acceptance \
subjects are hidden behind intervening ground — prefer elevated \
vantages (height_above_ground_m 60-150) with clear lines to every \
acceptance at_m. \
height_above_ground_m is above the terrain at at_m; pitch_deg negative \
looks down; yaw_deg 0 faces +x east, 90 faces +y south (UE convention, \
matches examples).

water: null unless the concept clearly shows standing water. level_cm is \
in CENTIMETRES above the landscape z datum (metres x 100), and must sit \
just above the carved floor of its basin placement.

Be faithful to the image: entity reads name what is visibly there; do \
not invent features the image does not show. v0 scope is terrain + \
lighting + a flat water plane — buildings and vegetation are placed by \
later stages and are NOT part of this layout.""" % {"w": _WORLD_M}

# ---------------------------------------------------------------- schema
_PAIR = {"type": "array", "items": {"type": "number"},
         "minItems": 2, "maxItems": 2}
_TRIPLE = {"type": "array", "items": {"type": "number"},
           "minItems": 3, "maxItems": 3}
_NUM_OR_NULL = {"anyOf": [{"type": "number"}, {"type": "null"}]}
_PAIR_OR_NULL = {"anyOf": [_PAIR, {"type": "null"}]}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["brief", "placements"],
    "properties": {
        "brief": {
            "type": "object",
            "additionalProperties": False,
            "required": ["terrain_entities", "lighting_geometry",
                         "acceptance", "render_camera", "water"],
            "properties": {
                "terrain_entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "read"],
                        "properties": {"id": {"type": "string"},
                                       "read": {"type": "string"}},
                    },
                },
                "lighting_geometry": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["sun_elevation_deg", "sun_azimuth_deg",
                                 "fog_height_datum_m", "fog_half_height_m",
                                 "sky_intensity", "fog_density_override"],
                    "properties": {
                        "sun_elevation_deg": {"type": "number"},
                        "sun_azimuth_deg": {"type": "number"},
                        "fog_height_datum_m": _NUM_OR_NULL,
                        "fog_half_height_m": _NUM_OR_NULL,
                        "sky_intensity": _NUM_OR_NULL,
                        "fog_density_override": _NUM_OR_NULL,
                    },
                },
                "acceptance": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "kind", "placement", "at_m",
                                     "box_m", "elev_m", "max_elev_m",
                                     "slope_mean_deg_max"],
                        "properties": {
                            "id": {"type": "string"},
                            "kind": {"type": "string",
                                     "enum": ["flat_site", "peak"]},
                            "placement": {"type": "string"},
                            "at_m": _PAIR,
                            "box_m": {"type": "number"},
                            "elev_m": _PAIR_OR_NULL,
                            "max_elev_m": _PAIR_OR_NULL,
                            "slope_mean_deg_max": _NUM_OR_NULL,
                        },
                    },
                },
                "render_camera": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["at_m", "height_above_ground_m",
                                 "pitch_deg", "yaw_deg", "fov"],
                    "properties": {
                        "at_m": _PAIR,
                        "height_above_ground_m": {"type": "number"},
                        "pitch_deg": {"type": "number"},
                        "yaw_deg": {"type": "number"},
                        "fov": {"type": "number"},
                    },
                },
                "water": {
                    "anyOf": [
                        {"type": "object",
                         "additionalProperties": False,
                         "required": ["kind", "label", "centre_cm",
                                      "level_cm", "scale_xy",
                                      "color_linear", "roughness",
                                      "opacity"],
                         "properties": {
                             "kind": {"type": "string",
                                      "enum": ["lake", "sea", "river"]},
                             "label": {"type": "string"},
                             "centre_cm": _PAIR,
                             "level_cm": {"type": "number"},
                             "scale_xy": _PAIR,
                             "color_linear": _TRIPLE,
                             "roughness": {"type": "number"},
                             "opacity": {"type": "number"},
                         }},
                        {"type": "null"},
                    ],
                },
            },
        },
        "placements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "stamp_hash", "centre_m", "size_m",
                             "rotation_deg", "blend", "amplitude_m",
                             "anchor_m"],
                "properties": {
                    "id": {"type": "string"},
                    "stamp_hash": {"type": "string"},
                    "centre_m": _PAIR,
                    "size_m": {"type": "number"},
                    "rotation_deg": {"type": "number"},
                    "blend": {"type": "string",
                              "enum": ["ADD", "MIN", "MAX"]},
                    "amplitude_m": {"type": "number"},
                    "anchor_m": _NUM_OR_NULL,
                },
            },
        },
    },
}


# ------------------------------------------------------------- few-shot
def _strip_private(obj):
    """Drop provenance keys ('_'-prefixed) and fields the model must not
    author (measurements, source paths) from a proven brief."""
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items()
                if not k.startswith("_")
                and k not in ("lighting_measured", "source_image")}
    if isinstance(obj, list):
        return [_strip_private(v) for v in obj]
    return obj


def _example_text():
    parts = []
    for label, brief_rel, recipe_rel in EXAMPLES:
        bp = os.path.join(REPO, brief_rel)
        rp = os.path.join(REPO, recipe_rel)
        if not (os.path.isfile(bp) and os.path.isfile(rp)):
            continue
        brief = _strip_private(json.load(open(bp, encoding="utf-8")))
        recipe = json.load(open(rp, encoding="utf-8"))
        pls = []
        for p in recipe.get("stamps", {}).get("placements", []):
            pls.append({
                "id": p["id"],
                "stamp_hash": "(chosen by character; this example used a "
                              "stamp not in your digest)",
                "centre_m": p["centre_m"],
                "size_m": p["size_m"],
                "rotation_deg": p.get("rotation_deg", 0),
                "blend": p["blend"],
                "amplitude_m": p["amplitude_m"],
                "anchor_m": p.get("anchor_m"),
            })
        brief.setdefault("water", None)
        ex = {"brief": {
                  "terrain_entities": brief.get("terrain_entities", []),
                  "lighting_geometry": brief.get("lighting_geometry", {}),
                  "acceptance": brief.get("acceptance", []),
                  "render_camera": brief.get("render_camera", {}),
                  "water": brief.get("water"),
              },
              "placements": pls}
        parts.append("EXAMPLE (%s):\n%s" % (label, json.dumps(ex, indent=1)))
    return "\n\n".join(parts)


def _digest_text(catalogue):
    lines = ["STAMP DIGEST — every stamp_hash you output MUST be one of "
             "these (full hash string):"]
    for m in catalogue["maps"]:
        rs = m["relief_stats"]
        lines.append("- hash %s  tag %-12s relief std %.0f/65535  %s"
                     % (m["hash"], m["tag"], rs["std"], m["character"]))
    return "\n".join(lines)


# ---------------------------------------------------------------- author
def author(image_path, out_path, catalogue_path=CATALOGUE,
           max_repairs=MAX_REPAIRS):
    try:
        import anthropic
    except ImportError:
        raise Refuse("the 'anthropic' package is not installed "
                     "(pip install anthropic)")

    catalogue = json.load(open(catalogue_path, encoding="utf-8"))
    media = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("ascii")

    user_content = [
        {"type": "image",
         "source": {"type": "base64", "media_type": media, "data": b64}},
        {"type": "text",
         "text": ("%s\n\n%s\n\nAuthor the layout for the image above."
                  % (_digest_text(catalogue), _example_text()))},
    ]
    messages = [{"role": "user", "content": user_content}]

    client = anthropic.Anthropic()
    layout = None
    for attempt in range(1 + max_repairs):
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                messages=messages,
                output_config={"format": {"type": "json_schema",
                                          "schema": SCHEMA}},
            ) as stream:
                resp = stream.get_final_message()
        except (anthropic.AuthenticationError, TypeError):
            # TypeError is the SDK's "could not resolve authentication
            # method" (raised while building headers, before any request);
            # AuthenticationError is a key the server rejected.
            raise Refuse(
                "no valid Anthropic credentials. The standard path needs "
                "none: run 'forge author', export a layout, then "
                "forge build <image> --layout <world>.layout.json")
        except anthropic.APIError as e:
            raise Refuse("Anthropic API error: %s" % e)
        if resp.stop_reason == "refusal":
            raise Refuse("the model declined this image (stop_reason "
                         "refusal); no layout was produced")
        if resp.stop_reason == "max_tokens":
            raise Refuse("response truncated at max_tokens; the layout "
                         "would be incomplete JSON")
        text = next((b.text for b in resp.content if b.type == "text"),
                    None)
        if text is None:
            raise Refuse("response carried no text block (stop_reason "
                         "%s)" % resp.stop_reason)
        candidate = json.loads(text)
        try:
            layout = check(candidate, catalogue)
            break
        except Refuse as e:
            if attempt >= max_repairs:
                raise Refuse(
                    "layout still failing after %d repair round(s) — "
                    "REFUSING (cap hit). Last failures:\n%s"
                    % (max_repairs, e))
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content":
                             "These machine checks failed:\n%s\n"
                             "Return the corrected complete JSON." % e})

    # measurements are injected, never authored
    layout["brief"]["lighting_measured"] = measure_for_brief(image_path)
    layout["brief"]["source_image"] = os.path.relpath(
        os.path.abspath(image_path), REPO).replace("\\", "/")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=1)
        f.write("\n")
    return layout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", required=True)
    ap.add_argument("--catalogue", default=CATALOGUE)
    a = ap.parse_args(argv)
    try:
        layout = author(a.image, a.out, a.catalogue)
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    print("layout written: %s  (%d placements, %d acceptance)"
          % (a.out, len(layout["placements"]),
             len(layout["brief"]["acceptance"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
