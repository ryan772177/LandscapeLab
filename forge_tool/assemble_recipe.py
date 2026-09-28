"""Assemble a schema-valid biome recipe from an authored layout.

The layout ({brief, placements}, gated by check_brief) carries what the
image DECIDED; this module supplies what the pipeline REQUIRES — the
world frame, compositor defaults, material chain, exposure baseline —
from values proven on the four benchmark worlds. Every default carries
its provenance in _TEMPLATE_NOTES.

v1 scope, deliberate: NO foliage, rock_scatter, or Megascans 'surface'
references — those depend on Fab/KiteDemo/PN content the emitted project
cannot ship. Layers are texture-only (make_landscape_material treats
'surface' as optional). The dressing stages come back when a shippable
asset base exists.

Outputs (into the given directory):
    <biome_id>.json        the biome recipe (drives everything)
    <biome_id>_brief.json  the brief (acceptance, lighting, camera, water)
"""
from __future__ import annotations

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_TEMPLATE_NOTES = {
    "frame": "1009 vx @ 400 cm = 4032 m, centred: highland/canyon/coast "
             "frame (location -201800 cm, z_scale 200000, z0 100000)",
    "placement_defaults": "falloff/jitter/datum values from the proven "
                          "highland_lake.json placements",
    "material": "highland layer bands, texture-only (no Megascans "
                "surface refs — Fab content cannot ship)",
    "exposure": "-1.923: the solved family baseline (highland recipe "
                "_solve provenance); inject_lighting may override from "
                "the brief",
}

ADD_DEFAULTS = {"falloff": 0.5, "falloff_shape": "euclidean",
                "opacity": 1.0, "falloff_jitter": 0.35,
                "falloff_jitter_scale": 0.25, "datum": "min"}
MIN_DEFAULTS = {"falloff": 0.6, "falloff_shape": "euclidean",
                "opacity": 1.0, "falloff_jitter": 0.2,
                "falloff_jitter_scale": 0.25}

# schema v1.27 (Brief 7 Phase 1): per-layer Nanite displacement amplitude
# in metres, by layer name. The assembled `material.displacement.per_layer`
# is built from this keyed by the LAYERS names below; a name not listed here
# falls back to 0.04 m (a mid ground-scan amplitude).
_DISP_PER_LAYER_M = {"Snow": 0.02, "Rock": 0.20, "Scree": 0.06,
                     "ForestFloor": 0.04, "Grass": 0.03}

LAYERS = [
    {"name": "Snow",
     "base_color": [0.9, 0.88, 0.86], "roughness": 0.8,
     "slope_deg": [0.0, 34.0], "height_m": [480.0, 2000.0],
     "blend_sharpness": 0.35, "texture": "textures/spike_scree.png",
     "tiling_m": 4.0, "macro_tiling_m": 188.0},
    {"name": "Rock",
     "base_color": [1.0, 1.0, 1.0], "roughness": 0.85,
     "slope_deg": [30.0, 90.0], "height_m": [0.0, 2000.0],
     "blend_sharpness": 0.7, "texture": "textures/spike_rock.png",
     "tiling_m": 4.0, "macro_tiling_m": 188.0},
    {"name": "Grass",
     "base_color": [1.0, 1.0, 1.0], "roughness": 0.6,
     "slope_deg": [0.0, 30.0], "height_m": [0.0, 480.0],
     "blend_sharpness": 0.5, "texture": "textures/spike_forest.png",
     "tiling_m": 2.1, "macro_tiling_m": 98.7},
]


def assemble(layout, out_dir, biome_id="forge_world"):
    """Write <biome_id>.json + <biome_id>_brief.json into out_dir.
    Returns (recipe_path, brief_path)."""
    brief = layout["brief"]

    placements = []
    for p in layout["placements"]:
        base = dict(ADD_DEFAULTS if p["blend"] == "ADD" else MIN_DEFAULTS)
        entry = {
            "id": p["id"],
            "stamp_sha256": p["stamp_hash"],
            "centre_m": p["centre_m"],
            "size_m": p["size_m"],
            "rotation_deg": p.get("rotation_deg", 0),
            "flip_x": False, "flip_y": False,
            "blend": p["blend"],
            "amplitude_m": p["amplitude_m"],
        }
        entry.update(base)
        if p["blend"] in ("MIN", "MAX"):
            entry["anchor_m"] = p["anchor_m"]
        placements.append(entry)

    cam = brief["render_camera"]
    recipe = {
        "schema_version": 1,
        "biome_id": biome_id,
        "display_name": "Forge: %s" % biome_id,
        "heightmap": {
            "source": "terrain/%s.png" % biome_id,
            "format": "png16",
            "resolution": 1009,
            "section_size": 63,
            "sections_per_component": 2,
            "component_count": 8,
        },
        "landscape": {
            # per-biome level: a fixed "/Game/ForgeWorld" made every run
            # overwrite the previous world's level and terrain files
            # (caught before the coastforge editor phase, 2026-09-03)
            "level_path": "/Game/Forge_%s" % biome_id,
            "actor_name": "Landscape_%s" % biome_id,
            "location_cm": [-201800.0, -201800.0, 100000.0],
            "scale_xy_cm": 400.0,
            "z_scale_cm": 200000.0,
        },
        "stamps": {
            "base": "terrain/%s_base.png" % biome_id,
            "output": "terrain/%s_stamped.png" % biome_id,
            "catalogue": "recipes/forge_stamps_catalogue.json",
            "allow_edge_clip": True,
            "placements": placements,
        },
        "engine": {"target_version": "5.8", "on_version_mismatch": "abort"},
        "material": {
            "parent_material": "/Game/Materials/M_%s" % biome_id,
            "height_jitter_m": 45.0,
            "height_jitter_scale_m": 700.0,
            "layers": [dict(l) for l in LAYERS],
            "weightmap": "textures/%s_weights.png" % biome_id,
            "variant_map": "textures/%s_variants.png" % biome_id,
            "triplanar": {"layers": ["Rock"], "slope_deg": [45.0, 50.0],
                          "sharpness": 2.0},
            "macro_variation": {"seed": 20260902, "map_resolution": 1024,
                                "feature_scale_m": [800.0, 2700.0],
                                "strength": 0.1, "chroma_ratio": 0.3},
            # schema v1.27 (Brief 7 Phase 1): per-layer displacement in
            # metres, keyed EXACTLY by the emitted layer names, replacing
            # the retired global amplitude_m (import_heightmap
            # ._validate_displacement hard-refuses the old key). Keys are
            # derived from LAYERS so a layer added there cannot desync the
            # displacement map; unknown names fall back to a mid ground
            # amplitude.
            "displacement": {
                "enabled": True,
                "center": 0.5,
                "per_layer": {
                    l["name"]: _DISP_PER_LAYER_M.get(l["name"], 0.04)
                    for l in LAYERS
                },
            },
        },
        "lighting": {
            "sun": {"elevation_deg": 35.0, "azimuth_deg": 100.0,
                    "intensity_lux": 130000.0,
                    "temperature_kelvin": 6500.0,
                    "light_shaft_bloom": True},
            "sky": {"type": "physical", "intensity": 1.0,
                    "color": [0.1, 0.12, 0.2]},
            "fog": {"enabled": True, "density": 0.0015,
                    "start_distance_m": 1500.0, "volumetric": True,
                    "height_datum_m": 30.0, "half_height_m": 60.0},
            "exposure": {"method": "manual", "compensation_ev": -1.923,
                         "_solve": _TEMPLATE_NOTES["exposure"]},
        },
        "capture": {
            "output_dir": "captures/%s" % biome_id,
            "resolution": [2032, 1273],
            "cameras": [{
                "name": "%s_render" % biome_id,
                # z is a PLACEHOLDER: the CLI recomputes it from the
                # built heightmap (camera height is above-ground in the
                # brief; world z needs the terrain that does not exist
                # yet). shoot refuses a below-ground camera either way.
                "location_cm": [cam["at_m"][0] * 100.0,
                                cam["at_m"][1] * 100.0,
                                100000.0],
                "rotation_deg": [cam["pitch_deg"], cam["yaw_deg"], 0.0],
                "fov_deg": cam["fov"],
            }],
        },
        # foliage exists for its SHARED PHYSICAL FACTS: the variant map's
        # scree selector refuses without foliage.rock_scatter (schema
        # v1.17), and a foliage block, once present, requires a species
        # list. v1 NEVER RUNS place_foliage — the species below is a
        # schema-satisfying declaration whose mesh is never dereferenced
        # (density 0 in an empty project). rock_scatter values are the
        # highland-proven physical constants; max_steps 2400 is the
        # 4 m/cell figure (same spacing as this frame).
        "foliage": {
            "density_per_hectare": 0.0,
            "seed": 20260902,
            # INSTANCED, not grass-system: make_landscape_material
            # builds grass types for grass-system species and VERIFIES
            # their meshes in the editor — which a fresh emitted project
            # cannot satisfy (measured on the dist T0 run: "meshes
            # missing"). An instanced species is dereferenced only by
            # place_foliage, which v1 never runs.
            "species": [{
                "name": "Meadow",
                "mesh": "/Game/Meshes/grass_medium_01_large_a_LOD0",
                "layer": "Grass",
                "weight_share": 1.0,
                "slope_deg": [0.0, 29.0],
                "height_m": [0.0, 500.0],
                "scale_range": [0.9, 1.6],
                "cull_distance_m": 50.0,
                "collision": {
                    "enabled": "query_only",
                    "profile": "FoliageBlockQueryOnly",
                    "navigable_geometry": "yes",
                },
            }],
            "rock_scatter": {
                "repose_deg": 35.0,
                "cliff_source_slope_deg": 45.0,
                "source_smooth_m": 16.0,
                "runout_m": 120.0,
                "mfd_exponent": 1.3,
                "max_steps": 2400,
                "saturation": 0.03,
            },
        },
        # NOTE: no _template_notes key — the schema refuses unknown
        # TOP-LEVEL keys (import_heightmap validator); provenance lives
        # in this module's _TEMPLATE_NOTES and docstring instead.
    }

    os.makedirs(out_dir, exist_ok=True)
    rp = os.path.join(out_dir, "%s.json" % biome_id)
    bp = os.path.join(out_dir, "%s_brief.json" % biome_id)
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(recipe, f, indent=1)
        f.write("\n")
    with open(bp, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=1)
        f.write("\n")
    return rp, bp
