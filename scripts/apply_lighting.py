"""apply_lighting.py — sky, sun and fog from the recipe.

Third leg of the first milestone. Every value comes from
`recipe.lighting`; nothing here is hardcoded (hard rule 2).

Find-or-create by deterministic actor label, so re-running moves and
retunes the existing actors rather than accumulating duplicates
(hard rule 3). Labels are `Lighting_<biome_id>_<role>`.

WHAT IT CREATES / UPDATES
  DirectionalLight    sun angle, intensity, colour temperature,
                      light-shaft bloom
  SkyAtmosphere       physical sky (recipe `sky.type == "physical"`)
  SkyLight            ambient fill, real-time captured
  ExponentialHeightFog density, falloff, start distance, volumetric
  VolumetricCloud     one layer on a /Game child MI of the engine's
                      simple cloud material (Brief 2 Task 6; the
                      coverage override must not dirty engine content)
  PostProcessVolume   unbound, manual exposure so captures are
                      comparable between runs

SUN ANGLE. `elevation_deg` and `azimuth_deg` become a rotator:
pitch = -elevation (Unreal pitches DOWN for a sun above the horizon,
because the light points along its forward vector), yaw = azimuth.
unreal.Rotator's POSITIONAL order is (roll, pitch, yaw) — the opposite
end first — so keywords are used throughout.

EXPOSURE. `exposure.method == "manual"` sets the post-process volume to
manual with the recipe's compensation. This is deliberate: auto-exposure
makes two captures of the same scene incomparable, which defeats the
review loop hard rule 4 exists for.

SCENE MUTATION, AND THE SAVE IS OWNED HERE (R-LIGHTSAVE, ruled
2026-09-10). Spawns and edits actors, then SAVES the packages of the
actors it touched and COMMITS them. Until 2026-09-10 this script said
"saving is the operator's call, and an unsaved lighting pass is
trivially reverted by reloading" — and on 2026-09-09/10 exactly that
happened by accident: Tasks 1–5 were applied, read back, measured and
committed, the close deadlocked, the machine died, and the world
reverted to pre-Brief-2 while every artefact carried the applied state.
A read-back proves the in-memory value only; the save is part of the
apply. The save is BOUNDED to this run's own actors — never a sweep of
all dirty packages — and the verdict comes from the filesystem
(git status delta), not from the editor's reply.

CENSUS SCOPE — READ BEFORE TRUSTING AN EXIT 0. The census is taken with
GameplayStatics.get_all_actors_of_class, which returns LOADED actors in
the currently open world. Under World Partition an actor in an unloaded
cell is invisible to it, so "foreign 0" means "none among the loaded
actors of the open world", NOT "none exist".

The WORLD is now pinned: this script gates on the recipe's
`landscape.level_path` before spawning anything (exit 7), so the census can
no longer be taken against the wrong level. What remains open is
RESIDENCY — the script does not force lighting actors resident, so a stray
in an unloaded cell is still invisible to the census. Actors this script
spawns are created with `is_spatially_loaded = False`, so OUR side is
always visible; the gap is only foreign actors somebody else left
spatially loaded. Until that is closed, an exit 0 is strong evidence, not
proof.

Exit codes:
  8  another heavy operation holds the lock (scripts/resource_guard.py)
  0  lighting applied
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  the editor reported a failure applying lighting, OR the payload came
     back without the census the exactly-one gate depends on. A missing
     census is "I could not look", never "nothing is there", so it fails
     closed here rather than reading as a clean scene.
  5  SAVE OR COMMIT VERDICT FAILED (R-LIGHTSAVE) — the payload returned
     no save report, our packages are still dirty after the save, git
     could not be read for the filesystem verdict, or the commit did not
     land. Lighting IS applied in memory in every one of these cases;
     what is unknown or false is persistence. (Until 2026-09-10 this
     code was unused here; siblings use 5 for "a probe returned
     nothing", and a failed look at the disk is the same shape.)
  6  REFUSED — the lighting classes this recipe governs do not hold
     exactly what the recipe implies: a foreign actor (a second fog, sun,
     sky atmosphere or sky light), more than one actor carrying our own
     label, none carrying it where the recipe asks for one, or one left
     over for a feature the recipe now disables. They light the scene
     regardless of what this script wrote, so hard rule 2 does not hold.
     Remove them or pass --allow-foreign. Added 2026-08-01 after a stray
     fog at density 0.0436 / StartDistance 0 whited out every capture
     while this script reported "fog reused" and exit 0.
  7  LEVEL GATE REFUSED — the editor has a different level open than
     `landscape.level_path`. Nothing was spawned or modified. Distinct
     from 6 because "I wrote to the wrong world" is not "this world has
     strays in it". Ruled 2026-08-01 (LESSONS.md, B1); 7 matches
     the verify_landscape.py precedent rather than colliding with 6.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import resource_guard   # noqa: E402 — RAM check + heavy-op lock
import import_heightmap   # noqa: E402 — shared recipe validation
import landscape_spec     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_LIGHTING__"

# The classes the exactly-one gate covers, each with the role suffix of
# the label this script gives its OWN actor. The payload's census dict
# must carry exactly these keys; the host refuses if one is absent rather
# than reading the gap as "nothing there" (a gate must not be satisfiable
# by the failure it guards against).
#
# PostProcessVolume is deliberately NOT here: multiple post-process
# volumes are legitimate (bounded volumes blend by priority). That
# reasoning only covers BOUNDED volumes, though — a second UNBOUND volume
# overrides exposure exactly as a second fog overrides fog. See the
# 2026-08-01 audit-log entry; adding it is a design decision, not an
# auditor edit.
CENSUS_CLASSES = (
    ("DirectionalLight", "Sun"),
    ("ExponentialHeightFog", "Fog"),
    ("SkyAtmosphere", "SkyAtmo"),
    ("SkyLight", "SkyLight"),
    ("VolumetricCloud", "Clouds"),
)


def _entry(e):
    """(label, path) from one census entry; tolerates a bare label."""
    if isinstance(e, (list, tuple)):
        return (e[0] if len(e) > 0 else None,
                e[1] if len(e) > 1 else None)
    return e, None


# ⛔ `_linear_to_srgb` WAS REMOVED HERE, 2026-09-13 (R-SKYCOLOR), and
# this note stands in its place so it is not helpfully re-added.
#
# It existed to pre-encode `lighting.sky.color` before handing it to
# `set_light_color`, on the belief that the engine would decode. The
# engine ENCODES (LightComponent.cpp:1130-1134 -> Color.cpp:251-267), so
# the helper was the second of two encodes and the recipe colour was
# wrong for the life of the file.
#
# There is no other caller. If a future one needs linear->sRGB, write it
# at that call site with a read-back proving the round trip, rather than
# reviving a helper whose whole history is a cancellation that never
# happened.


def _payload(biome_id, lighting, sun_height_cm):
    # ⛔ THE HOST NO LONGER PRE-ENCODES. R-SKYCOLOR, 2026-09-13.
    # `set_light_color` ENCODES; it does not decode (see the block at
    # the call site). Encoding here as well put the value through the
    # sRGB curve TWICE, and it had done so for the life of this file:
    # recipe linear [0.42, 0.6, 1.0] was stored as FColor(215, 231, 255)
    # = encode(encode(recipe)), giving an effective linear
    # (0.6795, 0.7991, 1.0) -- R 62% high, G 33% high.
    # The raw linear value now goes straight to the setter.
    sky_col = lighting.get("sky", {}).get("color")
    return '''
import json as _json
import unreal as _unreal

_biome = {biome!r}
_L = _json.loads({lighting!r})
_sun_z = float({sun_z!r})

_out = {{"ok": False, "actors": {{}}}}

_ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
_world = _ues.get_editor_world()
_eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)


def _pin(_a, _label):
    """Clear is_spatially_loaded. Applied on REUSE as well as on spawn.

    Applying it only to newly spawned actors would leave every actor from
    an earlier run still spatially loaded, so the failure below would keep
    recurring for exactly the actors that already exist - which is all of
    them, in any project that has run this script before.
    """
    try:
        _a.set_editor_property("is_spatially_loaded", False)
        # rule 12 (closure A-4): read the value back off the actor just
        # written, not the request. dict(), never a brace pair -- this
        # payload is a .format() template.
        _out.setdefault("pin_readbacks", dict())[_label] = bool(
            _a.get_editor_property("is_spatially_loaded"))
    except Exception as _exc:
        _out.setdefault("warnings", []).append(
            "could not clear is_spatially_loaded on " + _label
            + ": {{0}}: {{1}}".format(type(_exc).__name__, _exc))
    return _a


def _find_or_spawn(_cls, _label, _loc):
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(_world, _cls):
        if _a.get_actor_label() == _label:
            return _pin(_a, _label), False
    _a = _eas.spawn_actor_from_class(_cls, _loc)
    _a.set_actor_label(_label)
    # NOT spatially loaded. Lighting is global to the level and has no
    # business being streamed by proximity - but the real reason is
    # idempotency (hard rule 3), and this is almost certainly how
    # /Game/Alpine came to hold a COMPLETE DUPLICATE lighting rig:
    #   spawn spatially-loaded -> save -> restart the editor -> the actor
    #   is in an unloaded cell -> _find_or_spawn (which sees LOADED actors
    #   only) does not find it -> it spawns a SECOND one -> repeat.
    # the capture script (line 273) already does this for its cameras, for
    # exactly this reason. Setting it also makes the census below able to
    # see our own actors regardless of streaming state.
    return _pin(_a, _label), True


def _census(_cls, _label):
    """Every actor of a class the recipe claims to govern, ours or not.

    WHY THIS EXISTS. _find_or_spawn returns the FIRST label match and never
    counts. On 2026-08-01 /Game/Alpine held a COMPLETE DUPLICATE lighting
    rig - two DirectionalLights, two ExponentialHeightFogs, two SkyLights,
    two SkyAtmospheres - whose members carried the engine's default labels.
    So nothing ever matched them, this script reported every actor as
    "reused", and the stray fog (density 0.0436 at StartDistance 0, ~20x
    the recipe's 0.0022 and starting at the camera) whited out every view
    while the run reported success.

    These classes are singletons IN EFFECT: two fogs stack, two
    atmospheres stack, and UE itself warns that multiple directional
    lights compete to be the one used for volumetric fog. So "the recipe
    governs the lighting" (hard rule 2) is FALSE whenever a foreign one
    exists, and this must refuse rather than silently light the scene
    twice.

    SCOPE. get_all_actors_of_class returns LOADED actors of the OPEN
    world only. An actor in an unloaded World Partition cell is not
    reported, so an empty foreign list means "none among the loaded
    actors", not "none exist". The host prints that caveat rather than
    letting an exit 0 read as proof.

    Each entry is [label, path]. The label alone is not identity - the
    duplicate rig carried the ENGINE'S DEFAULT labels, so two actors can
    print the same string (lesson 4.4), and OFPA gives each actor its own
    hash-named package, so the path is what lets an operator find it.

    INERT. A light with bAffectsWorld False is reported as PRESENT BUT
    INERT rather than as a stray. LightComponentBase.h:48-49 is explicit:
    "A disabled light will not contribute to the scene in any way ...
    Setting this to false has the same effect as deleting the light", and
    ULightComponent::CreateRenderState_Concurrent gates the whole
    add-to-scene path on `if (bAffectsWorld)` (LightComponent.cpp:968).

    This matters because the gate's job is "the recipe owns every scene
    parameter", and an actor that contributes nothing to the scene cannot
    break that. Measured 2026-09-09: /Game/Alpine8K carries HeroStage_Key,
    _Fill and _Rim from the parked hero work at intensity 25000/7500/11250,
    visible True and affects_world FALSE, and the gate refused every run on
    them. A gate that refuses correct work is a gate that gets switched
    off -- and the habit it was forming was `--allow-foreign`, which
    disables the check for REAL strays too.

    The third state is still reported and still counted, so an operator
    sees them; it just does not refuse on them.
    """
    _ours, _foreign, _inert = [], [], []
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(_world, _cls):
        _lbl = _a.get_actor_label()
        try:
            _path = _a.get_path_name()
        except Exception:
            # Diagnostics must never fail the run they describe; an
            # unreadable path still leaves the label and the count.
            _path = None
        if _lbl == _label:
            _ours.append([_lbl, _path])
            continue
        # Only a light can be inert in this sense. Anything else -- a fog,
        # an atmosphere -- has no such switch and stays foreign.
        _off = False
        try:
            _lc = _a.get_component_by_class(_unreal.LightComponent)
            if _lc is not None:
                _off = not bool(_lc.get_editor_property("affects_world"))
        except Exception:
            _off = False
        (_inert if _off else _foreign).append([_lbl, _path])
    return {{"ours": _ours, "foreign": _foreign, "inert": _inert}}


def _tag(_role):
    return "Lighting_" + _biome + "_" + _role


_origin = _unreal.Vector(0.0, 0.0, _sun_z)

# ---- sun ------------------------------------------------------------
_sun, _new = _find_or_spawn(_unreal.DirectionalLight, _tag("Sun"), _origin)
_out["actors"]["sun"] = "spawned" if _new else "reused"
# Pitch DOWN by the elevation: a directional light points along its
# forward vector, so a sun 12 degrees above the horizon aims 12 degrees
# below horizontal.
_sun.set_actor_rotation(_unreal.Rotator(
    roll=0.0, pitch=-float(_L["sun"]["elevation_deg"]),
    yaw=float(_L["sun"]["azimuth_deg"])), False)
# ALight declares LightComponent (Light.h:19-20), so the Python name is
# light_component on EVERY light actor — there is no
# directional_light_component / sky_light_component.
_sc = _sun.light_component
_sc.set_editor_property("intensity", float(_L["sun"]["intensity_lux"]))
_sc.set_editor_property("use_temperature", True)
_sc.set_editor_property("temperature",
                        float(_L["sun"]["temperature_kelvin"]))
try:
    # bEnableLightShaftBloom -> enable_light_shaft_bloom (the b- prefix is
    # stripped, the rest of the name is kept).
    _sc.set_editor_property("enable_light_shaft_bloom",
                            bool(_L["sun"]["light_shaft_bloom"]))
except Exception as _exc:
    _out["shaft_note"] = "%s: %s" % (type(_exc).__name__, _exc)
_sc.set_editor_property("atmosphere_sun_light", True)
_sc.set_editor_property("cast_shadows", True)
# ---- rule 12 read-backs (AUDIT P1-11, closure A-4) -------------------
# Rotation off the ACTOR just rotated; booleans off the COMPONENT just
# written. Rotator order is (roll, pitch, yaw) -- the camera-mirror trap.
# (Pass 3 2026-09-16) intensity / temperature read back too -- they were
# written with no read-back while their neighbours had one.
_out["sun_intensity_readback"] = float(_sc.get_editor_property("intensity"))
_out["sun_use_temperature_readback"] = bool(
    _sc.get_editor_property("use_temperature"))
_out["sun_temperature_readback"] = float(
    _sc.get_editor_property("temperature"))
_srr = _sun.get_actor_rotation()
_out["sun_rotation_readback"] = [round(float(_srr.roll), 4),
                                 round(float(_srr.pitch), 4),
                                 round(float(_srr.yaw), 4)]
_out["sun_rotation_expected"] = [
    0.0, -round(float(_L["sun"]["elevation_deg"]), 4),
    round(float(_L["sun"]["azimuth_deg"]), 4)]
# The engine normalises rotators to (-180, 180], so 285 reads back as
# -75. Compare on the circle, not the number line.
_out["sun_rotation_matches"] = all(
    abs(((_ra - _rb + 180.0) % 360.0) - 180.0) < 0.01
    for _ra, _rb in zip(_out["sun_rotation_readback"],
                        _out["sun_rotation_expected"]))
try:
    _out["sun_light_shaft_bloom_readback"] = bool(
        _sc.get_editor_property("enable_light_shaft_bloom"))
except Exception as _exc:
    _out["sun_light_shaft_bloom_readback"] = (
        "unreadable: " + str(_exc)[:80])
_out["sun_atmosphere_sun_light_readback"] = bool(
    _sc.get_editor_property("atmosphere_sun_light"))
_out["sun_cast_shadows_readback"] = bool(
    _sc.get_editor_property("cast_shadows"))

# ---- sky ------------------------------------------------------------
if _L["sky"]["type"] == "physical":
    _atmo, _new = _find_or_spawn(_unreal.SkyAtmosphere, _tag("SkyAtmo"),
                                 _origin)
    _out["actors"]["sky_atmosphere"] = "spawned" if _new else "reused"

    # ---- Brief 2 Task 4: scattering, DECLARED rather than left at default --
    # Names verified against SkyAtmosphereComponent.h:
    #   RayleighScatteringScale :94   MieScatteringScale :108
    #   MieAnisotropy :124  "0 mean light is uniformly scattered ... closer
    #                        to 1 means lights will scatter more forward"
    # Until now these were ENGINE DEFAULTS and nothing declared them, which
    # rule 12 counts as prose: 0.003996 / 0.8 / 0.0331 read back from the
    # live world on 2026-09-09, matching the defaults exactly.
    _ac = _atmo.get_component_by_class(_unreal.SkyAtmosphereComponent)
    if _ac is not None:
        _sk = _L["sky"]
        _ac.set_editor_property(
            "mie_scattering_scale", float(_sk.get("mie_scattering_scale", 0.003996)))
        _ac.set_editor_property(
            "mie_anisotropy", float(_sk.get("mie_anisotropy", 0.8)))
        _ac.set_editor_property(
            "rayleigh_scattering_scale",
            float(_sk.get("rayleigh_scattering_scale", 0.0331)))
        _out["atmo_mie_scattering_scale"] = float(
            _ac.get_editor_property("mie_scattering_scale"))
        _out["atmo_mie_anisotropy"] = float(
            _ac.get_editor_property("mie_anisotropy"))
        _out["atmo_rayleigh_scattering_scale"] = float(
            _ac.get_editor_property("rayleigh_scattering_scale"))
    else:
        _out["atmo_component"] = "NOT FOUND -- scattering not applied"

_skyl, _new = _find_or_spawn(_unreal.SkyLight, _tag("SkyLight"), _origin)
_out["actors"]["skylight"] = "spawned" if _new else "reused"
_slc = _skyl.light_component
_slc.set_editor_property("intensity", float(_L["sky"]["intensity"]))

# ---- Brief 2 Task 3: real-time capture, lower hemisphere black ----------
# Names verified against SkyLightComponent.h:
#   bRealTimeCapture        :108  "the sky will be captured and convolved to
#        achieve dynamic diffuse and specular environment lighting.
#        SkyAtmosphere, VolumetricCloud ... are taken into account"
#   bLowerHemisphereIsBlack :143  "Whether all distant lighting from the lower
#        hemisphere should be set to LowerHemisphereColor. Enabling this is
#        ACCURATE when lighting a scene on a planet where the ground blocks
#        the sky"
#   LowerHemisphereColor    :146
# Both Epic samples with a physical sun run the sky light this way: real-time
# capture on, lower hemisphere black, intensity 1.0. Without real-time
# capture the sky light is a stale cubemap that does not follow the
# atmosphere it is supposed to be sampling.
_slc.set_editor_property("real_time_capture",
                         bool(_L["sky"].get("real_time_capture", True)))
_slc.set_editor_property("lower_hemisphere_is_black",
                         bool(_L["sky"].get("lower_hemisphere_is_black", True)))
_lh = _L["sky"].get("lower_hemisphere_color", [0.0, 0.0, 0.0, 1.0])
_slc.set_editor_property(
    "lower_hemisphere_color",
    _unreal.LinearColor(float(_lh[0]), float(_lh[1]), float(_lh[2]),
                        float(_lh[3]) if len(_lh) > 3 else 1.0))
_out["sky_intensity"] = float(_slc.get_editor_property("intensity"))
_out["sky_real_time_capture"] = bool(
    _slc.get_editor_property("real_time_capture"))
_out["sky_lower_hemisphere_is_black"] = bool(
    _slc.get_editor_property("lower_hemisphere_is_black"))
_lhc = _slc.get_editor_property("lower_hemisphere_color")
_out["sky_lower_hemisphere_color"] = [round(float(_lhc.r), 4),
                                      round(float(_lhc.g), 4),
                                      round(float(_lhc.b), 4)]
# (Pass 3 2026-09-16) A leftover unconditional re-set of
# real_time_capture=True stood HERE, after the recipe-driven write AND
# after the read-back above — with real_time_capture=false declared, the
# sidecar would have recorded False while the engine held True. Removed:
# the recipe-driven write at the top of this block is the only writer.
# Cool tint on the ambient term. With a warm sun, un-tinted ambient
# leaves shadows a flat neutral grey — nothing supplies the sky's own
# colour to surfaces the sun cannot reach.
#
# ⭐ THE ENGINE ENCODES. PASS THE RAW LINEAR VALUE. (R-SKYCOLOR)
#
# The C++ signature is SetLightColor(FLinearColor, bool bSRGB = true)
# and the Python binding exposes ONE argument, so bSRGB is always true.
# What bSRGB=true MEANS is "emit sRGB bytes" -- an ENCODE:
#     LightComponent.cpp:1130-1134  SetLightColor -> NewLightColor.ToFColor(bSRGB)
#     Color.h:429                   ToFColor(true) -> ToFColorSRGB()
#     Color.cpp:251-267             ToFColorSRGB  -> ConvertLinearToSRGB...
#
# ⛔ THE PREVIOUS COMMENT HERE SAID "DECODE" AND WAS WRONG, and the
# code below it pre-encoded to cancel a decode that never happens.
# Measured 2026-09-13 by reading the actor back: recipe linear
# [0.42, 0.6, 1.0] was stored as FColor(215, 231, 255), which is the
# recipe value encoded TWICE. B was exact -- 1.0 is a fixed point of
# the sRGB curve -- so the one channel a human would spot-check was
# guaranteed to look right.
#
# Recipe colours are linear (same as base_color). Handing the linear
# value straight to the setter gives exactly ONE encode, which is the
# whole conversion.
_sky_col = _json.loads({sky_col!r})
if _sky_col:
    _slc.set_light_color(
        _unreal.LinearColor(float(_sky_col[0]), float(_sky_col[1]),
                            float(_sky_col[2]), 1.0))
# READ IT BACK, BOTH WAYS (standing rule 12). `light_color` is an 8-bit
# FColor, so the stored bytes are recorded AND decoded back to linear,
# because "the setter ran" and "the value landed" are different claims
# and only the linear form is comparable to the recipe.
_out["sky_color_requested_linear"] = _sky_col
try:
    _rb = _slc.get_editor_property("light_color")
    _out["sky_color_readback_fcolor"] = [int(_rb.r), int(_rb.g),
                                         int(_rb.b), int(_rb.a)]

    def _srgb_to_linear(_v):
        _v = float(_v) / 255.0
        return _v / 12.92 if _v <= 0.04045 else ((_v + 0.055) / 1.055) ** 2.4

    _out["sky_color_readback_linear"] = [
        round(_srgb_to_linear(_rb.r), 5), round(_srgb_to_linear(_rb.g), 5),
        round(_srgb_to_linear(_rb.b), 5)]
    if _sky_col:
        _out["sky_color_roundtrip_abs_error"] = [
            round(abs(_out["sky_color_readback_linear"][_i]
                      - float(_sky_col[_i])), 5) for _i in range(3)]
        # The 8-bit floor, so the verdict is bounded rather than absolute.
        _out["sky_color_quantisation_floor_linear"] = round(
            _srgb_to_linear(255) - _srgb_to_linear(254), 5)
except Exception as _sce:
    _out["sky_color_readback_error"] = "%s: %s" % (type(_sce).__name__, _sce)

# ---- fog ------------------------------------------------------------
if _L["fog"]["enabled"]:
    _fog, _new = _find_or_spawn(_unreal.ExponentialHeightFog,
                                _tag("Fog"), _origin)
    _out["actors"]["fog"] = "spawned" if _new else "reused"
    _fc = _fog.component

    # THE FOG'S HEIGHT DATUM IS A SCENE PARAMETER AND WAS AN ACCIDENT.
    # Exponential height fog is densest AT the actor's world Z and thins
    # upward, so that Z decides which parts of a world are buried and
    # which are clear — the single most consequential fog setting in
    # terrain with vertical extent. Nothing set it: the actor sat wherever
    # it was first spawned, at Z 192000 (1920 m), while the terrain's 90th
    # percentile is 1610 m. Ninety percent of the world was under the
    # densest fog and only the summit cleared it. Hard rule 2 says every
    # scene parameter comes from the recipe; this one never did.
    _fog.set_actor_location(
        _unreal.Vector(_origin.x, _origin.y,
                       float(_L["fog"]["height_datum_m"]) * 100.0),
        False, False)
    _out["fog_datum_cm"] = float(_L["fog"]["height_datum_m"]) * 100.0

    _fc.set_editor_property("fog_density", float(_L["fog"]["density"]))
    # (Pass 3 2026-09-16) fog_density is the 2026-08-01 whiteout field
    # (0.0436 applied vs recipe 0.0022) and had NO read-back while its
    # neighbours all did.
    _out["fog_density_readback"] = float(
        _fc.get_editor_property("fog_density"))

    # HALF-HEIGHT IN METRES, converted here, because the engine's own
    # number means nothing in world terms. SceneCore.cpp:405 divides
    # FogHeightFalloff by 1000 before use, so the density halves every
    # ln(2) / (falloff/1000) centimetres. The recipe's long-standing
    # 0.12 was therefore a 58 m half-height — a near-vertical wall of
    # fog, which is the hard horizontal line visible across the
    # 2026-08-02 captures. Expressed as metres it is a value someone can
    # reason about; expressed as 0.12 it was a number nobody could.
    _half_m = float(_L["fog"]["half_height_m"])
    # BASE 2, NOT BASE e. Corrected 2026-09-09 against the shader, after this
    # line had shipped a half-height 1/ln2 = 1.4427x LARGER than the recipe
    # asked for since v1.4 (202 m authored -> 291.4 m rendered).
    #
    # HeightFogCommon.ush:206 COMMENTS the density function as
    #   d = GlobalDensity * exp(-HeightFalloff * z)
    # and the CODE does something else, in three places:
    #   :225  PreComputeFogOriginFactor -> FogDensity * pow(2.0f, -F*(z-z0))
    #   :301  RayOriginTerms = ... * exp2(-Exponent)
    #   :394  ExpFogFactor   = exp2(-LineIntegral)
    # Base 2 means density halves when (F/1000) * dz_cm = 1 exactly, so
    #   F = 1000 / half_height_cm = 10 / half_height_m
    # with no ln(2) anywhere. SceneCore.cpp:404-405 supplies the /1000 on
    # BOTH density and falloff.
    #
    # Rule 9's shape, with Epic's comment as the unverified claim: a comment
    # is not the code, and ours followed the comment.
    _falloff = 1000.0 / (_half_m * 100.0)
    _fc.set_editor_property("fog_height_falloff", _falloff)
    _out["fog_half_height_m"] = _half_m
    _out["fog_height_falloff"] = _falloff
    _fc.set_editor_property("start_distance",
                            float(_L["fog"]["start_distance_m"]) * 100.0)
    # bEnableVolumetricFog (ExponentialHeightFogComponent.h:135-136)
    _fc.set_editor_property("enable_volumetric_fog",
                            bool(_L["fog"]["volumetric"]))
    # rule 12 read-back (AUDIT P1-11, closure A-4)
    _out["fog_volumetric_enabled_readback"] = bool(
        _fc.get_editor_property("enable_volumetric_fog"))

    # ---- VOLUMETRIC FOG SHAPE (Brief 2 Task 2) --------------------------
    # Names verified against ExponentialHeightFogComponent.h:
    #   VolumetricFogExtinctionScale        :163  "Scales the height fog
    #        particle extinction amount used by volumetric fog"
    #   VolumetricFogScatteringDistribution :144  "0 scatters equally in all
    #        directions, .9 predominantly in the light direction. In order to
    #        have visible volumetric fog light shafts FROM THE SIDE, the
    #        distribution will need to be closer to 0."
    # 0.4 is forward-biased enough to catch the low sun without collapsing
    # the side-lit shafts the header warns about. The FALLBACK below is
    # 0.4 for the same reason (it was 0.2 — half the justified bias for
    # any recipe omitting the key, while this comment promised 0.4).
    _fc.set_editor_property(
        "volumetric_fog_extinction_scale",
        float(_L["fog"].get("volumetric_extinction_scale", 1.0)))
    _fc.set_editor_property(
        "volumetric_fog_scattering_distribution",
        float(_L["fog"].get("volumetric_scattering_distribution", 0.4)))
    _out["fog_volumetric_extinction_scale"] = float(
        _fc.get_editor_property("volumetric_fog_extinction_scale"))
    _out["fog_volumetric_scattering_distribution"] = float(
        _fc.get_editor_property("volumetric_fog_scattering_distribution"))

    # ---- FOG COLOUR COMES FROM THE ATMOSPHERE, NOT FROM A TYPED TINT ----
    # Brief 2 Task 1. These three were ALREADY at the right values in the
    # live level on 2026-09-09 -- but nothing declared them and nothing
    # applied them, so they were accidentally correct, which rule 12 counts
    # as prose. Declared in the recipe and read back here.
    #
    # Names verified against ExponentialHeightFogComponent.h:
    #   FogInscatteringLuminance                   :43
    #   SkyAtmosphereAmbientContributionColorScale :47   "Only effective when
    #                                r.SupportSkyAtmosphereAffectsHeightFog>0"
    #   DirectionalInscatteringLuminance           :108
    #
    # The header warns that FogInscatteringLuminance is ignored when
    # r.SupportExpFogMatchesVolumetricFog = 1. THAT CVAR DOES NOT EXIST in
    # 5.8 -- it appears in three comments in that header and in no source
    # file, and reads 0 from the live engine. Another comment the code does
    # not back.
    def _lin(_key, _default):
        _v = _L["fog"].get(_key, _default)
        return _unreal.LinearColor(float(_v[0]), float(_v[1]), float(_v[2]),
                                   float(_v[3]) if len(_v) > 3 else 1.0)

    _fc.set_editor_property("fog_inscattering_luminance",
                            _lin("inscattering_luminance", [0.0, 0.0, 0.0, 1.0]))
    _fc.set_editor_property("directional_inscattering_luminance",
                            _lin("directional_inscattering_luminance",
                                 [0.0, 0.0, 0.0, 1.0]))
    _fc.set_editor_property("sky_atmosphere_ambient_contribution_color_scale",
                            _lin("sky_atmosphere_ambient_contribution_scale",
                                 [1.0, 1.0, 1.0, 1.0]))

    def _rb(_name):
        _c = _fc.get_editor_property(_name)
        return [round(float(_c.r), 6), round(float(_c.g), 6),
                round(float(_c.b), 6), round(float(_c.a), 6)]

    _out["fog_inscattering_luminance"] = _rb("fog_inscattering_luminance")
    _out["fog_directional_inscattering_luminance"] = _rb(
        "directional_inscattering_luminance")
    _out["fog_sky_atmosphere_ambient_scale"] = _rb(
        "sky_atmosphere_ambient_contribution_color_scale")
    _out["fog_start_distance_cm"] = float(
        _fc.get_editor_property("start_distance"))
    # The half-height the ENGINE will actually render, from the falloff it
    # now holds -- base 2, so half_height_cm = 1000/F. This is the number
    # that was 291.42 m while the recipe said 202.0 until 2026-09-09.
    _rbf = float(_fc.get_editor_property("fog_height_falloff"))
    _out["fog_implied_half_height_m"] = (
        round((1000.0 / _rbf) / 100.0, 2) if _rbf else None)

# ---- clouds (Brief 2 Task 6, ruled 2026-09-10) ----------------------
_cl = _L.get("clouds")
if _cl and _cl.get("enabled"):
    _cloud, _new = _find_or_spawn(_unreal.VolumetricCloud, _tag("Clouds"),
                                  _origin)
    _out["actors"]["clouds"] = "spawned" if _new else "reused"
    _cc = _cloud.get_component_by_class(_unreal.VolumetricCloudComponent)
    if _cc is None:
        raise RuntimeError("VolumetricCloud actor has no "
                           "VolumetricCloudComponent")

    # THE COVERAGE OVERRIDE LIVES ON A CHILD INSTANCE IN /Game. Setting
    # the parameter on the ENGINE MI would dirty engine content outside
    # both roots (standing rule 1). Find-or-create is the
    # make_nowind_material_instances pattern, verified in this repo.
    _eal = _unreal.EditorAssetLibrary
    _mel = _unreal.MaterialEditingLibrary
    _mi_path = _cl["material_instance"]
    _parent = _eal.load_asset(_cl["material_parent"])
    if _parent is None:
        raise RuntimeError("cloud material parent not loadable: "
                           + _cl["material_parent"])
    if _eal.does_asset_exist(_mi_path):
        _mi = _eal.load_asset(_mi_path)
    else:
        _mi = _unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            _mi_path.rsplit("/", 1)[1], _mi_path.rsplit("/", 1)[0],
            _unreal.MaterialInstanceConstant,
            _unreal.MaterialInstanceConstantFactoryNew())
    if _mi is None:
        raise RuntimeError("cloud MI neither loadable nor creatable: "
                           + _mi_path)
    _mel.set_material_instance_parent(_mi, _parent)
    _mel.set_material_instance_scalar_parameter_value(
        _mi, _cl["coverage_param"], float(_cl["coverage"]))
    _mel.update_material_instance(_mi)
    _eal.save_asset(_mi_path)

    _cc.set_editor_property("material", _mi)
    # KILOMETRES, both -- read_cloud_state's verified reflected names.
    _cc.set_editor_property("layer_bottom_altitude",
                            float(_cl["layer_bottom_km"]))
    _cc.set_editor_property("layer_height", float(_cl["layer_height_km"]))

    # READ BACK: component props re-read; coverage re-read from the
    # RELOADED asset, not the object just written.
    _chk = _eal.load_asset(_mi_path)
    _out["clouds_readback"] = {{
        "layer_bottom_km": float(
            _cc.get_editor_property("layer_bottom_altitude")),
        "layer_height_km": float(_cc.get_editor_property("layer_height")),
        "material": str(_cc.get_editor_property("material").get_path_name()
                        if _cc.get_editor_property("material") else None),
        "coverage": float(_mel.get_material_instance_scalar_parameter_value(
            _chk, _cl["coverage_param"])),
        "cvar_r_VolumetricCloud": float(
            _unreal.SystemLibrary.get_console_variable_float_value(
                "r.VolumetricCloud")),
    }}

# ---- exposure -------------------------------------------------------
_ppv, _new = _find_or_spawn(_unreal.PostProcessVolume, _tag("PostProcess"),
                            _origin)
_out["actors"]["post_process"] = "spawned" if _new else "reused"
_ppv.set_editor_property("unbound", True)
# rule 12 read-back (AUDIT P1-11, closure A-4)
_out["ppv_unbound_readback"] = bool(_ppv.get_editor_property("unbound"))
_s = _ppv.settings
_manual = (_L["exposure"]["method"] == "manual")
_s.set_editor_property("override_auto_exposure_method", True)
_s.set_editor_property(
    "auto_exposure_method",
    _unreal.AutoExposureMethod.AEM_MANUAL if _manual
    else _unreal.AutoExposureMethod.AEM_HISTOGRAM)
_s.set_editor_property("override_auto_exposure_bias", True)
_s.set_editor_property("auto_exposure_bias",
                       float(_L["exposure"]["compensation_ev"]))
if _manual:
    # Pin min == max so nothing adapts between captures.
    _s.set_editor_property("override_auto_exposure_min_brightness", True)
    _s.set_editor_property("override_auto_exposure_max_brightness", True)
    _s.set_editor_property("auto_exposure_min_brightness", 1.0)
    _s.set_editor_property("auto_exposure_max_brightness", 1.0)
# R-METER (RULED 2026-09-12b): APPLY PHYSICAL CAMERA EXPOSURE OFF, so
# Exposure is exactly 1/2^compensation and nothing multiplies it.
#
# MEASURED 2026-09-12 before this line existed: the volume read
# auto_exposure_apply_physical_camera_exposure TRUE with its
# override_ companion FALSE -- so the ENGINE DEFAULT was in force and
# the volume never asserted it either way. An unasserted default is not
# a setting; it is whatever the engine happens to prefer this version,
# and it silently multiplies the manual bias by the camera's
# aperture/shutter/ISO.
#
# Declared from the recipe rather than hardcoded (pipeline rule 2), and
# defaulting to FALSE only when the key is absent so an existing recipe
# does not silently change meaning.
# ⛔ USE dict(), NEVER AN EMPTY BRACE PAIR. This payload is a .format()
# TEMPLATE, so a literal brace is a replacement field. The first draft
# used one and raised "Replacement index 0 out of range" at format time
# -- then the COMMENT explaining that raised it again, because the
# comment typed the characters it was warning about. Both happened
# earlier today in make_landscape_material too. Prose here never types
# the character; that is the only version of this rule that holds.
_apce = bool((_L["exposure"] or dict()).get(
    "apply_physical_camera_exposure", False))
_s.set_editor_property(
    "override_auto_exposure_apply_physical_camera_exposure", True)
_s.set_editor_property(
    "auto_exposure_apply_physical_camera_exposure", _apce)
# ---- Brief 2 Task 5: white balance and a QUIET grade -------------------
# Names verified against Scene.h:
#   WhiteTemp :1507        ColorContrast :1517 (FVector4, not a float --
#     "Control the range of light and dark values"; the 4th component is the
#     MASTER and the shader uses xyz*w, so a global contrast is
#     xyz = 1 and w = the value)
#
# ⛔ CORRECTED 2026-09-13c, AND THE OLD COMMENT WAS THE SEED. It said "the
# 4th component is the master, so a global contrast is all four set
# alike", and the code below did exactly that: Vector4(c, c, c, c). The
# shader is PostProcessCombineLUTs.usf:98 --
#
#     pow( WorkingColor * (1.0/0.18), ColorContrast.xyz*ColorContrast.w ) * 0.18
#
# -- so all four alike gives an exponent of c SQUARED. A declared 0.95
# was an effective 0.9025, and the error was invisible because it is a
# plausible number in the same direction. MEASURED: with the exponent
# read as 0.9025 the two contrast captures agree to 0.001 (residual
# 0.79767 vs 0.79690); read as 0.95 they disagree by 0.039, which is
# what first looked like a "non-multiplicative composition".
# Rule 9: fix the seed as well as the copy.
#   BloomMethod :1487 with EBloomMethod BM_FFT :59 ("Convolution")
#   BloomIntensity :1629   VignetteIntensity :2143
#   FilmGrainIntensity :2181   SceneFringeIntensity :1621 (chromatic ab.)
# Every one needs its bOverride_ companion or the volume ignores it.
_g = _L.get("grade")
if _g:
    # TemperatureType PINNED (Brief 3 Task 1, 2026-09-10). Scene.h:1499-
    # 1504: White Balance treats WhiteTemp as the ILLUMINANT considered
    # white; Color Temperature is "the inverse of the White Balance
    # operation". Unset since the grade existed -- at a 1200 K step the
    # sign of the whole correction rides on it.
    _tt = str(_g.get("temperature_type", "white_balance"))
    # AUDIT 2026-09-10: the two modes are INVERSES; an unrecognised
    # spelling must refuse, never silently pick a sign.
    if _tt not in ("white_balance", "color_temperature"):
        raise RuntimeError("grade.temperature_type %r is not one of "
                           "white_balance/color_temperature" % _tt)
    _tt_enum = (_unreal.TemperatureMethod.TEMP_COLOR_TEMPERATURE
                if _tt == "color_temperature"
                else _unreal.TemperatureMethod.TEMP_WHITE_BALANCE)
    _s.set_editor_property("override_temperature_type", True)
    _s.set_editor_property("temperature_type", _tt_enum)
    _s.set_editor_property("override_white_temp", True)
    _s.set_editor_property("white_temp", float(_g["white_temp_k"]))
    _s.set_editor_property("override_white_tint", True)
    _s.set_editor_property("white_tint", float(_g.get("white_tint", 0.0)))
    # THE RECIPE DECLARES THE EFFECTIVE VALUE. xyz = 1, the value in w,
    # so the shader's xyz*w product IS what the recipe says (ruled
    # 2026-09-13c). The product is read back below and refused on
    # mismatch -- reading back the four components separately would not
    # have caught the squaring, because each component was exactly what
    # the setter wrote.
    _c = float(_g["contrast"])
    _s.set_editor_property("override_color_contrast", True)
    _s.set_editor_property("color_contrast",
                           _unreal.Vector4(1.0, 1.0, 1.0, _c))
    _s.set_editor_property("override_bloom_method", True)
    _s.set_editor_property("bloom_method", _unreal.BloomMethod.BM_FFT)
    _s.set_editor_property("override_bloom_intensity", True)
    _s.set_editor_property("bloom_intensity", float(_g["bloom_intensity"]))
    _s.set_editor_property("override_film_grain_intensity", True)
    _s.set_editor_property("film_grain_intensity", float(_g["grain"]))
    _s.set_editor_property("override_vignette_intensity", True)
    _s.set_editor_property("vignette_intensity", float(_g["vignette"]))
    _s.set_editor_property("override_scene_fringe_intensity", True)
    _s.set_editor_property("scene_fringe_intensity",
                           float(_g["chromatic_aberration"]))

_ppv.set_editor_property("settings", _s)

# READ BACK FROM THE VOLUME, not from the settings struct just written --
# `settings` is a VALUE type here, so reading the local _s would only prove
# the setter ran on a copy.
if _g:
    _rb = _ppv.get_editor_property("settings")
    _cc = _rb.get_editor_property("color_contrast")
    # BRACES ARE DOUBLED: this whole payload is a .format() template, so a
    # bare dict literal here is read as a format field. Cost one run --
    # "KeyError: '\\n        \"white_temp\"'" -- and the existing _census
    # function already showed the convention with {{"ours": ...}}.
    _out["grade_readback"] = {{
        "white_temp": float(_rb.get_editor_property("white_temp")),
        "temperature_type": str(_rb.get_editor_property("temperature_type")),
        "white_tint": float(_rb.get_editor_property("white_tint")),
        "color_contrast": [round(float(_cc.x), 4), round(float(_cc.y), 4),
                           round(float(_cc.z), 4), round(float(_cc.w), 4)],
        # THE PRODUCT IS THE SETTING. The shader applies xyz*w, so the
        # four components are an implementation detail and this is the
        # number the recipe is asserting. Reported per channel because
        # xyz need not be uniform in general.
        "color_contrast_effective_xyz_times_w": [
            round(float(_cc.x) * float(_cc.w), 6),
            round(float(_cc.y) * float(_cc.w), 6),
            round(float(_cc.z) * float(_cc.w), 6)],
        "bloom_method": str(_rb.get_editor_property("bloom_method")),
        "bloom_intensity": float(_rb.get_editor_property("bloom_intensity")),
        "film_grain_intensity": float(
            _rb.get_editor_property("film_grain_intensity")),
        "vignette_intensity": float(
            _rb.get_editor_property("vignette_intensity")),
        "scene_fringe_intensity": float(
            _rb.get_editor_property("scene_fringe_intensity")),
    }}

# EXPOSURE READ-BACK. Added 2026-09-11: compensation_ev had been applied
# and never read back, which is standing rule 12 exactly -- "a profile
# parameter that is not read back is PROSE". It was the one field in this
# payload that answered "is this controlled?" with a false yes, and it is
# also the field a 2026-09-07 defect already caught drifting (benchmark
# said "exposure manual" while auto-exposure ran). Same VOLUME-not-struct
# rule as the grade above.
_rbe = _ppv.get_editor_property("settings")
_out["exposure_readback"] = {{
    "auto_exposure_method": str(_rbe.get_editor_property(
        "auto_exposure_method")),
    "auto_exposure_bias": float(_rbe.get_editor_property(
        "auto_exposure_bias")),
    "auto_exposure_min_brightness": float(_rbe.get_editor_property(
        "auto_exposure_min_brightness")),
    "auto_exposure_max_brightness": float(_rbe.get_editor_property(
        "auto_exposure_max_brightness")),
    # R-METER 2026-09-12b. BOTH the value and its override_ companion:
    # the value alone is meaningless, because it read TRUE for months
    # with the override FALSE, i.e. the engine default rather than
    # anything this project chose.
    "auto_exposure_apply_physical_camera_exposure": bool(
        _rbe.get_editor_property(
            "auto_exposure_apply_physical_camera_exposure")),
    "override_auto_exposure_apply_physical_camera_exposure": bool(
        _rbe.get_editor_property(
            "override_auto_exposure_apply_physical_camera_exposure")),
}}

# Census AFTER the find-or-spawn pass, so anything this run created is
# already labelled as ours and is not reported as foreign.
_out["census"] = {{
    "DirectionalLight": _census(_unreal.DirectionalLight, _tag("Sun")),
    "ExponentialHeightFog": _census(_unreal.ExponentialHeightFog,
                                    _tag("Fog")),
    "SkyAtmosphere": _census(_unreal.SkyAtmosphere, _tag("SkyAtmo")),
    "SkyLight": _census(_unreal.SkyLight, _tag("SkyLight")),
    "VolumetricCloud": _census(_unreal.VolumetricCloud, _tag("Clouds")),
}}

# ---- SAVE OUR OWN PACKAGES (R-LIGHTSAVE, RULED 2026-09-10) --------------
# On 2026-09-09 Tasks 1-5 were applied, read back, measured and committed
# -- and never saved. A deadlocked close plus a dead machine reverted the
# world to pre-Brief-2 while every artefact carried the applied state:
# the measurements outlived the world they measured. The save is owned
# HERE, by the applying tool, not by session hygiene.
#
# Bounded to the actors THIS RUN touched -- never a sweep of all dirty
# packages (the 2026-08-24 city save swept the hero rig into the world).
# set_dirty_flag + save_loaded_assets(only_if_is_dirty=False) is the
# save_tagged_actors pattern: a component-level edit can leave the
# package 0-dirty, and only_if_is_dirty=True would reproduce that defect
# inside the fix. NOTE: a run that SPAWNS an actor may also dirty the map
# package; that is outside this bounded save and is the close ceremony's
# to see.
_touched = [_sun, _skyl, _ppv]
if _L["sky"]["type"] == "physical":
    _touched.append(_atmo)
if _L["fog"]["enabled"]:
    _touched.append(_fog)
if _cl and _cl.get("enabled"):
    _touched.append(_cloud)
_ass = _unreal.get_editor_subsystem(_unreal.EditorAssetSubsystem)
_save = {{"marked": 0, "packages": [], "saved": None,
          "still_dirty_ours": None}}
for _a in _touched:
    try:
        _a.modify()
    except Exception:
        pass
    try:
        if _ass.set_dirty_flag(_a, True):
            _save["marked"] += 1
    except Exception as _exc:
        _out.setdefault("warnings", []).append(
            "set_dirty_flag failed: {{0}}: {{1}}".format(
                type(_exc).__name__, _exc))
    try:
        _n = str(_a.get_outermost().get_name())
    except Exception:
        _n = "UNREADABLE"
    if _n not in _save["packages"]:
        _save["packages"].append(_n)
# The cloud MI is saved by save_asset above (an asset, not an actor);
# its package joins the report so the host's filesystem verdict and
# commit cover it too.
if _cl and _cl.get("enabled"):
    try:
        _n = str(_mi.get_outermost().get_name())
        if _n not in _save["packages"]:
            _save["packages"].append(_n)
    except Exception:
        _save["packages"].append("UNREADABLE")
_save["saved"] = bool(_ass.save_loaded_assets(_touched, False))
# READ BACK the dirty state -- ask the editor again rather than trusting
# the return value. One of OUR packages still dirty is a failed save.
_still = [p.get_name() for p in
          _unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
_still += [p.get_name() for p in
           _unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
_save["still_dirty_ours"] = sorted(
    set(_still).intersection(_save["packages"]))
_out["save"] = _save

_out["ok"] = True
print("{marker}" + _json.dumps(_out))
'''.format(biome=biome_id, lighting=json.dumps(lighting),
           sun_z=float(sun_height_cm),
           sky_col=json.dumps(sky_col), marker=MARKER)


def _git_touched():
    """Paths git sees as changed or untracked under the project Content dir.

    Same instrument as save_tagged_actors.py: the editor's save reply is one
    instrument; the filesystem is a different representation and it is the
    one that decides (R-LIGHTSAVE). None means COULD NOT LOOK, never "no
    change" -- an unreadable git must not read as a clean save.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--short", "-uall", "--", "LandscapeLab/Content"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        return {ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:
        return None


def _pkg_files(package_names):
    """Repo-relative .uasset paths for /Game/... package names.

    EVERY /Game/ name is mapped to a .uasset path — there is no
    external-actor filter here (a docstring once claimed one). On an
    OFPA level every dirty package IS an external-actor content package
    and this is exact; on a NON-OFPA level an actor's outermost is the
    LEVEL package, which maps to a .uasset that does not exist (the
    level is a .umap), and the existence check downstream then reports
    exit 5 for a save that actually landed. Anything not under /Game/
    is skipped and reported by the caller.
    """
    files = []
    for n in package_names:
        if isinstance(n, str) and n.startswith("/Game/"):
            files.append("LandscapeLab/Content/" + n[len("/Game/"):]
                         + ".uasset")
    return files


def _commit_packages(files, biome):
    """git add + commit the saved package files. Returns (ok, detail)."""
    msg_path = None
    try:
        fd, msg_path = tempfile.mkstemp(prefix=".ll_lightsave_",
                                        suffix=".txt", dir=REPO_ROOT)
        with os.fdopen(fd, "w") as fh:
            fh.write("apply_lighting: lighting packages saved (%s)\n\n"
                     % biome)
            fh.write("R-LIGHTSAVE (ruled 2026-09-10): apply -> read back -> "
                     "save -> commit is one unit\nowned by the applying "
                     "tool. Packages:\n")
            for f in files:
                fh.write("  %s\n" % f)
        r = subprocess.run(["git", "add", "--"] + files, cwd=REPO_ROOT,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, "git add failed: " + (r.stderr or r.stdout).strip()
        # Pathspec on the commit so ONLY these files land in it, whatever
        # else the index happens to hold.
        r = subprocess.run(["git", "commit", "-F", msg_path, "--"] + files,
                           cwd=REPO_ROOT, capture_output=True, text=True,
                           timeout=120)
        if r.returncode != 0:
            return False, ("git commit failed: "
                           + (r.stderr or r.stdout).strip())
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=REPO_ROOT, capture_output=True, text=True,
                           timeout=120)
        return True, h.stdout.strip() if h.returncode == 0 else "committed"
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    finally:
        if msg_path and os.path.exists(msg_path):
            try:
                os.remove(msg_path)
            except OSError:
                pass


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(marker):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source, marker=MARKER):
    # THE PAYLOAD GUARD SITS ON THE TRANSPORT, NOT ON THE AUTHOR
    # (2026-09-10c). LESSONS 12.10's rule — never name a .py file inside
    # a remote-exec payload — had a guard, but it was opt-in per tool and
    # this script never adopted it; then the offending ".py " arrived via
    # the RECIPE's prose, which nobody reads as payload text until it is
    # interpolated. Guarding the COMPOSED source at the send point is the
    # only place that sees everything.
    import make_landscape_material as _mlm
    source = _mlm._guard_payload(source)
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        r = remote.run_command(source, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("  command failed: {0}".format((r or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(r), marker)
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=6.0)
    p.add_argument("--allow-foreign", action="store_true",
                   help="proceed even though lighting actors the recipe "
                        "does not govern are present. They light the scene "
                        "regardless of what this script writes.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    # `lighting_ref` — BORROW another recipe's lighting block without
    # copying it.
    #
    # WHY THIS EXISTS. A scratch look-test level needs R13's lighting, and
    # it needs the LEVEL GATE below to name the scratch level rather than
    # /Game/Alpine8K. Before this key there were only two ways to get both,
    # and both are defects this project has a rule against:
    #   - copy the lighting block into the scratch recipe -> two copies of
    #     a physical description that will drift (NN24, and R13 is exactly
    #     the kind of measured block that must not be duplicated);
    #   - add a flag that skips the level gate -> weakening the gate that
    #     exists because lighting was once written to the wrong world.
    # Borrowing keeps ONE declaration of the VALUES and lets the borrower
    # declare its own LEVEL, which is the axis that actually differs.
    #
    # Declaring both is REFUSED rather than resolved by precedence: a
    # recipe carrying a local block and a reference is ambiguous about
    # which one is in effect, and silently preferring either is how a
    # scene gets lit by the block nobody was reading.
    if recipe.get("lighting_ref"):
        if recipe.get("lighting"):
            print("REFUSE: recipe declares BOTH `lighting` and "
                  "`lighting_ref`. Which one is in effect cannot be read "
                  "from the file, so neither is used. Delete one.")
            return 2
        ref_path = os.path.join(landscape_spec.REPO_ROOT,
                                recipe["lighting_ref"])
        ref, ref_err = landscape_spec.load_recipe(ref_path)
        if ref_err:
            print("REFUSE: lighting_ref {0}: {1}".format(
                recipe["lighting_ref"], ref_err))
            return 2
        if not ref.get("lighting"):
            print("REFUSE: lighting_ref {0} has no `lighting` block."
                  .format(recipe["lighting_ref"]))
            return 2
        recipe["lighting"] = ref["lighting"]
        print("lighting borrowed from : {0}  (biome {1})".format(
            recipe["lighting_ref"], ref.get("biome_id")))
        print("  Values are declared ONCE, there. This recipe declares only "
              "its own level.")
        print("")

    lit_errors = import_heightmap._validate_lighting(recipe.get("lighting"))
    if lit_errors:
        print("REFUSE: lighting block invalid:")
        for e in lit_errors:
            print("  - {0}".format(e))
        return 2

    lighting = recipe["lighting"]
    biome = recipe["biome_id"]

    # sky.type "hdri" is accepted by the schema validator and then silently
    # ignored by this script - it only ever builds a SkyAtmosphere for
    # "physical", and `hdri_path` is read nowhere. A recipe asking for an
    # HDRI sky would get a scene with no HDRI and no error, which breaks
    # hard rule 2 quietly. Implementing HDRI is a feature, not a fix, and
    # no recipe needs it; so refuse loudly instead of pretending.
    # Ruled 2026-08-01 (LESSONS.md, F4).
    if lighting.get("sky", {}).get("type") == "hdri":
        print("REFUSE: sky.type 'hdri' is valid in the schema but NOT "
              "implemented by this script.")
        print("  It would build no HDRI and report success, so the recipe "
              "would not govern the sky (hard rule 2).")
        print("  Use 'physical', or implement HDRI here first. See "
              "LESSONS.md 2026-08-01, ruling F4.")
        return 2
    # Park the lighting actors above the terrain so they are easy to find
    # in the viewport and never buried inside the landscape.
    ls = recipe["landscape"]
    # TWO SPELLINGS OF ONE FACT, and the fix is to read either rather than to
    # make a recipe carry both. Biome recipes (alpine.json, schema.md) spell
    # this `location_cm` + `z_scale_cm`; the AlpineLab evaluation recipes spell
    # it `origin_cm` (a scalar, X and Y are equal by construction) + `scale_z`
    # (the UE landscape Z scale, where 100 spans 512 m).
    #
    # Requiring the evaluation recipes to ALSO declare the biome spelling would
    # put the same physical quantity in a recipe twice under two names, which is
    # the structure non-negotiable 24 rejects — and the two copies would be free
    # to disagree with nothing to notice.
    #
    # This value only parks the lighting actors above the terrain so they are
    # findable in the viewport; it is not sampled by anything.
    if "location_cm" in ls and "z_scale_cm" in ls:
        base_z = float(ls["location_cm"][2])
        span_cm = float(ls["z_scale_cm"])
    elif "scale_z" in ls:
        base_z = 0.0
        # UE landscape Z: scale 100 spans 512 m == 51200 cm.
        span_cm = float(ls["scale_z"]) / 100.0 * 51200.0
    else:
        print("REFUSE: recipe['landscape'] declares neither "
              "location_cm+z_scale_cm nor scale_z, so there is no way to work "
              "out where to park the lighting actors.")
        return 2
    sun_z = base_z + span_cm * 0.75

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Biome     : {0}".format(biome))
    print("")
    print("  sun       elevation {0} deg, azimuth {1} deg".format(
        lighting["sun"]["elevation_deg"], lighting["sun"]["azimuth_deg"]))
    print("            {0} lux, {1} K, shafts {2}".format(
        lighting["sun"]["intensity_lux"],
        lighting["sun"]["temperature_kelvin"],
        lighting["sun"]["light_shaft_bloom"]))
    print("  sky       {0}, intensity {1}".format(
        lighting["sky"]["type"], lighting["sky"]["intensity"]))
    print("  fog       enabled {0}, density {1}, volumetric {2}".format(
        lighting["fog"]["enabled"], lighting["fog"]["density"],
        lighting["fog"]["volumetric"]))
    print("  exposure  {0}, {1} EV".format(
        lighting["exposure"]["method"],
        lighting["exposure"]["compensation_ev"]))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        # Level gate (schema v1.2), exit 7. Ruled 2026-08-01 (B1).
        # This was the last editor-touching script without one. Without it
        # the census below measures whichever world happens to be open: with
        # the wrong level loaded it would spawn a rig there, census THAT
        # world, find nothing foreign and exit 0 - the 2026-08-01 incident
        # again, this time wearing a gate's authority.
        print("--- level gate (recipe landscape.level_path) ---")

        def _lvl_runner(source, marker):
            return _run(remote_exec, remote, node["node_id"], source, marker)

        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level, _lvl_runner)
        if not ok_level:
            print("REFUSE (level gate): {0}".format(detail))
            print("  Conduct rule 7 verified the PROJECT; this checks the")
            print("  LEVEL. Nothing was spawned or modified.")
            return 7
        print("  level {0}".format(detail))
        print("")

        # Filesystem baseline BEFORE the payload runs, so the save verdict
        # below can measure what the save actually wrote (R-LIGHTSAVE).
        fs_before = _git_touched()

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(biome, lighting, sun_z))
        if r is None or not r.get("ok"):
            print("FAIL: lighting payload did not complete.")
            return 4
        print("--- actors ---")
        for role, state in (r.get("actors") or {}).items():
            print("  {0:<16} {1}".format(role, state))
        if r.get("shaft_note"):
            print("  note: {0}".format(r["shaft_note"]))

        # EXPOSURE: APPLIED, READ BACK, AND COMPARED (standing rule 12).
        # Added 2026-09-11. The payload had never read exposure back, and
        # the host had never compared the grade read-back it DID collect --
        # so both were computed and discarded, which is the same false yes
        # rule 12 was promoted for. The comparison is against the RECIPE,
        # and a mismatch REFUSES: exposure silently not taking is how a
        # capture ends up measuring a scene nobody declared.
        print("")
        print("--- exposure read-back (rule 12) ---")
        erb = r.get("exposure_readback")
        if not isinstance(erb, dict):
            print("FAIL: the payload returned no exposure read-back.")
            print("  Exposure WAS written. Nothing here shows it took, and")
            print("  'I could not look' is not 'it is correct'.")
            return 4
        want_ev = float(lighting["exposure"]["compensation_ev"])
        want_manual = lighting["exposure"]["method"] == "manual"
        got_ev = float(erb["auto_exposure_bias"])
        got_method = erb["auto_exposure_method"]
        print("  method    {0}  (recipe says {1})".format(
            got_method, lighting["exposure"]["method"]))
        print("  bias      {0:+.4f} EV  (recipe {1:+.4f})".format(
            got_ev, want_ev))
        print("  min/max   {0} / {1}".format(
            erb["auto_exposure_min_brightness"],
            erb["auto_exposure_max_brightness"]))
        # R-METER (RULED 2026-09-12b). Apply Physical Camera Exposure must
        # be OFF so Exposure is exactly 1/2^compensation. Compared against
        # the recipe, and the OVERRIDE is compared too -- the value read
        # TRUE for months with the override FALSE, which is the engine
        # default wearing the appearance of a setting.
        want_apce = bool(lighting["exposure"].get(
            "apply_physical_camera_exposure", False))
        got_apce = bool(erb.get("auto_exposure_apply_physical_camera_exposure"))
        got_apce_ovr = bool(erb.get(
            "override_auto_exposure_apply_physical_camera_exposure"))
        print("  physical  apply={0}  override={1}  (recipe wants apply={2})"
              .format(got_apce, got_apce_ovr, want_apce))
        bad = []
        # CONTRAST: the EFFECTIVE exponent, which is xyz*w, against what
        # the recipe declares. Checked here because checking the four
        # components separately cannot catch the squaring -- each one was
        # exactly what the setter wrote while the product was c^2.
        grb = r.get("grade_readback")
        if isinstance(grb, dict) and lighting.get("grade"):
            want_c = float(lighting["grade"]["contrast"])
            eff = grb.get("color_contrast_effective_xyz_times_w")
            if not isinstance(eff, list) or len(eff) != 3:
                bad.append("no effective contrast read-back; the product "
                           "xyz*w is the setting and was not reported")
            else:
                print("  contrast  effective {0}  (recipe {1})".format(
                    [round(v, 4) for v in eff], want_c))
                for ax, v in zip("RGB", eff):
                    if abs(float(v) - want_c) > 1e-4:
                        bad.append(
                            "effective contrast %s is %.6f, recipe declares "
                            "%.6f -- the shader applies ColorContrast.xyz*w "
                            "(PostProcessCombineLUTs.usf:98), so the PRODUCT "
                            "is the exponent" % (ax, float(v), want_c))
        if got_apce != want_apce:
            bad.append("apply_physical_camera_exposure {0} != recipe {1}"
                       .format(got_apce, want_apce))
        if not got_apce_ovr:
            bad.append("override_auto_exposure_apply_physical_camera_exposure "
                       "is FALSE -- the volume is not asserting it, so the "
                       "engine default governs and Exposure is not "
                       "1/2^compensation")
        if abs(got_ev - want_ev) > 1e-3:
            bad.append("bias {0:+.4f} != recipe {1:+.4f}".format(
                got_ev, want_ev))
        if want_manual and "AEM_MANUAL" not in got_method:
            bad.append("method {0} is not manual".format(got_method))
        if want_manual and not (
                abs(erb["auto_exposure_min_brightness"] - 1.0) < 1e-6
                and abs(erb["auto_exposure_max_brightness"] - 1.0) < 1e-6):
            bad.append("manual exposure with min/max brightness not pinned "
                       "to 1.0 -- the bias would be modulated")
        # SUN + FOG read-backs COMPARED (Pass 3 2026-09-16). The payload
        # computed sun_rotation_matches and the host never looked at it --
        # computed-and-discarded, the pattern this very block was added to
        # kill. fog_density is the 2026-08-01 whiteout field; the sun
        # rotation carries the documented positional-argument trap.
        if r.get("sun_rotation_matches") is not True:
            bad.append("sun rotation did not take: readback {0} vs "
                       "expected {1}".format(
                           r.get("sun_rotation_readback"),
                           r.get("sun_rotation_expected")))
        want_si = float(lighting["sun"]["intensity_lux"])
        got_si = r.get("sun_intensity_readback")
        if not isinstance(got_si, (int, float)):
            bad.append("no sun intensity read-back")
        elif abs(float(got_si) - want_si) > max(1e-6, 1e-4 * abs(want_si)):
            bad.append("sun intensity {0!r} != recipe {1!r}".format(
                got_si, want_si))
        want_tk = float(lighting["sun"]["temperature_kelvin"])
        got_tk = r.get("sun_temperature_readback")
        if r.get("sun_use_temperature_readback") is not True:
            bad.append("use_temperature did not read back True")
        if not isinstance(got_tk, (int, float)):
            bad.append("no sun temperature read-back")
        elif abs(float(got_tk) - want_tk) > max(1e-6, 1e-4 * abs(want_tk)):
            bad.append("sun temperature {0!r} != recipe {1!r}".format(
                got_tk, want_tk))
        # Gate on the payload's OWN predicate (fog["enabled"]), not the
        # key's presence — the schema REQUIRES lighting.fog, so
        # .get("fog") is always truthy and a disabled-fog recipe would
        # spuriously FAIL on "no fog_density read-back" (auditor FIX-1).
        if lighting["fog"]["enabled"]:
            want_fd = float(lighting["fog"]["density"])
            got_fd = r.get("fog_density_readback")
            if not isinstance(got_fd, (int, float)):
                bad.append("no fog_density read-back")
            elif abs(float(got_fd) - want_fd) > max(1e-9,
                                                    1e-4 * abs(want_fd)):
                bad.append("fog_density {0!r} != recipe {1!r}".format(
                    got_fd, want_fd))
        if bad:
            print("FAIL: exposure did not take:")
            for b in bad:
                print("  - {0}".format(b))
            return 4
        print("  MATCHES the recipe.")

        # Exactly-one gate over the classes the recipe claims to govern.
        # These are singletons IN EFFECT - two fogs stack, two atmospheres
        # stack, and UE warns that multiple directional lights compete for
        # volumetric fog - so a foreign one means the recipe does NOT
        # govern this scene's lighting, whatever this script just wrote.
        print("")
        print("--- lighting census (recipe-governed classes) ---")
        census = r.get("census")
        if not isinstance(census, dict):
            print("FAIL: the payload returned no census.")
            print("  Lighting WAS applied, but nothing here shows whether")
            print("  the recipe is the only thing lighting the scene. An")
            print("  absent census is 'I could not look', never 'nothing")
            print("  is there', so this refuses instead of exiting 0.")
            return 4
        missing = [c for c, _role in CENSUS_CLASSES if c not in census]
        if missing:
            print("FAIL: the census did not report {0}.".format(
                ", ".join(missing)))
            print("  Lighting WAS applied. A partial census cannot show")
            print("  those classes are clean, and a silent gap is exactly")
            print("  what this gate exists to stop.")
            return 4

        # What the recipe IMPLIES for each class: exactly one actor of
        # ours where it asks for the feature, none where it does not.
        # "None where it does not" matters — turning fog off in the recipe
        # does not delete a fog this script spawned on an earlier run, and
        # that fog keeps fogging the scene.
        expected = {
            "DirectionalLight": 1,
            "SkyLight": 1,
            "SkyAtmosphere": 1 if lighting["sky"]["type"] == "physical" else 0,
            "ExponentialHeightFog": 1 if lighting["fog"]["enabled"] else 0,
            "VolumetricCloud": 1 if (lighting.get("clouds") or {}).get(
                "enabled") else 0,
        }
        strays = []
        for cls, role in CENSUS_CLASSES:
            entry = census.get(cls) or {}
            ours = [_entry(e) for e in (entry.get("ours") or [])]
            foreign = [_entry(e) for e in (entry.get("foreign") or [])]
            inert = [_entry(e) for e in (entry.get("inert") or [])]
            want = expected[cls]
            label_ours = "Lighting_{0}_{1}".format(biome, role)
            print("  {0:<22} ours {1} (recipe implies {2})  foreign {3}"
                  "  inert {4}"
                  .format(cls, len(ours), want, len(foreign), len(inert)))
            # SHOWN, NOT REFUSED ON. bAffectsWorld False "has the same
            # effect as deleting the light" (LightComponentBase.h:48-49) and
            # the renderer never registers it (LightComponent.cpp:968), so
            # it cannot break "the recipe owns every scene parameter". It is
            # still printed, because an operator should know it is there.
            for label, path in inert:
                print("      inert:   {0!r}  {1}  (affects_world False)"
                      .format(label, path or "<path unreadable>"))
            for label, path in foreign:
                print("      FOREIGN: {0!r}  {1}".format(
                    label, path or "<path unreadable>"))
                strays.append("{0}: foreign actor {1!r} at {2}".format(
                    cls, label, path or "<path unreadable>"))
            if len(ours) != want:
                for label, path in ours:
                    print("      OURS:    {0!r}  {1}".format(
                        label, path or "<path unreadable>"))
                if want == 0:
                    strays.append(
                        "{0}: the recipe does not ask for this class, but "
                        "{1} actor(s) labelled {2!r} remain and still "
                        "affect the scene - this script does not remove "
                        "them".format(cls, len(ours), label_ours))
                elif not ours:
                    strays.append(
                        "{0}: no actor carries our label {1!r} - the census "
                        "cannot see the actor this run just created or "
                        "reused".format(cls, label_ours))
                else:
                    strays.append(
                        "{0}: {1} actors share our own label {2!r} - which "
                        "one this run tuned is ambiguous".format(
                            cls, len(ours), label_ours))
        print("")
        print("  scope: LOADED actors only. The WORLD is pinned — the")
        print("  level gate above proved this is {0!r} — but World".format(
            want_level))
        print("  Partition exposes nothing from unloaded cells, and this")
        print("  script does not force lighting actors resident. Actors it")
        print("  spawns are is_spatially_loaded=False so OUR side is always")
        print("  visible; a foreign actor left spatially loaded in an")
        print("  unloaded cell would not be. So 'foreign 0' is strong")
        print("  evidence, not proof.")

        if strays and not args.allow_foreign:
            print("")
            print("REFUSE: the lighting classes this recipe governs do not")
            print("hold exactly what the recipe implies. What is there")
            print("lights the scene regardless of what was just written:")
            for s in strays:
                print("  - {0}".format(s))
            print("")
            print("  This is not cosmetic. On 2026-08-01 a stray fog at")
            print("  density 0.0436 / StartDistance 0 - about 20x the")
            print("  recipe's 0.0022, starting at the camera - whited out")
            print("  every capture while this script reported 'fog reused'")
            print("  and exit 0. Hard rule 2 says the recipe owns every")
            print("  scene parameter; a foreign fog makes that false.")
            print("")
            print("  Remove them, or re-run with --allow-foreign to")
            print("  proceed with the scene lit by more than the recipe.")
            return 6
        if strays:
            print("")
            print("  --allow-foreign given: proceeding with {0} unresolved "
                  "census finding(s); the scene is lit by more than this "
                  "recipe.".format(len(strays)))

        # ---- sidecar (closure A-4, AUDIT P1-11): persist the payload's
        # read-backs. The formatted sections above are operator output; the
        # sidecar is the CITABLE artefact -- all eight rule-12 read-backs
        # (sun rotation, shaft bloom, atmosphere_sun_light, cast_shadows,
        # volumetric fog, unbound, pin_readbacks, ambient scale) land here.
        import time as _time
        _scp = os.path.join(
            REPO_ROOT, "_verify",
            "lighting_apply_%s_%s.json"
            % (_time.strftime("%Y-%m-%d"), biome))
        with open(_scp, "w", encoding="utf-8") as _fh:
            json.dump(r, _fh, indent=1, default=str)
        print("")
        print("  sidecar: {0}".format(
            os.path.relpath(_scp, REPO_ROOT).replace("\\", "/")))

        # ---- R-LIGHTSAVE: save verdict, then the commit (ruled 2026-09-10)
        print("")
        print("--- save (R-LIGHTSAVE) ---")
        save = r.get("save")
        if not isinstance(save, dict) or save.get("saved") is None:
            print("FAIL: the payload returned no save report.")
            print("  Lighting WAS applied and read back, but whether it")
            print("  reached disk is UNKNOWN. An absent report is 'I could")
            print("  not look', never 'saved' -- this is the exact gap that")
            print("  reverted Brief 2 on 2026-09-10.")
            return 5
        pkgs = save.get("packages") or []
        print("  marked dirty {0}, editor says saved={1}".format(
            save.get("marked"), save.get("saved")))
        for n in pkgs:
            print("    {0}".format(n))
        still = save.get("still_dirty_ours") or []
        if still:
            print("FAIL: {0} of our packages are STILL DIRTY after the "
                  "save:".format(len(still)))
            for n in still:
                print("    {0}".format(n))
            return 5

        # THE VERDICT COMES FROM THE FILESYSTEM, not the editor's reply.
        fs_after = _git_touched()
        if fs_before is None or fs_after is None:
            print("FAIL: could not read the filesystem (git status), so")
            print("  whether the save reached disk is UNKNOWN. The editor's")
            print("  reply is not sufficient here -- that is R-LIGHTSAVE's")
            print("  whole premise.")
            return 5
        delta = fs_after - fs_before
        expected_files = _pkg_files(pkgs)
        unmappable = [n for n in pkgs
                      if not (isinstance(n, str) and n.startswith("/Game/"))]
        for n in unmappable:
            print("  note: package {0!r} not under /Game/, not committed "
                  "by this run".format(n))
        changed = sorted(f for f in expected_files
                         if f.replace("\\", "/") in delta)
        print("  filesystem: {0} of our {1} package file(s) changed".format(
            len(changed), len(expected_files)))
        if not changed:
            # AUDIT 2026-09-10 F1: an empty delta proves "not newly
            # modified in git", NOT "exists". A package whose write never
            # landed produces no untracked entry because there is no file.
            # Existence is asserted, not assumed.
            missing = [f for f in expected_files
                       if not os.path.exists(os.path.join(REPO_ROOT, f))]
            if missing:
                print("FAIL: no file changed AND {0} expected package "
                      "file(s) do not exist on disk:".format(len(missing)))
                for f in missing:
                    print("    {0}".format(f))
                print("  The editor reported a save and the filesystem has")
                print("  no file. Do not record this as saved.")
                return 5
            # AUDIT 2026-09-10 F2: a file already dirty BEFORE this run
            # (a prior run whose commit failed, exit 5) sits in fs_before
            # AND fs_after, so the delta hides it. Any of our files still
            # visible to git at all is uncommitted and goes through the
            # commit now -- the re-run must not mask the prior run's
            # exit-5 condition.
            pending = sorted(f for f in expected_files
                             if f.replace("\\", "/") in fs_after)
            if pending:
                print("  no NEW change, but {0} package file(s) were "
                      "already awaiting commit (a prior run's save?):"
                      .format(len(pending)))
                changed = pending
            else:
                # Our packages read 0-dirty after the save, every file
                # exists, and git sees nothing uncommitted -> the on-disk
                # state already matched (an idempotent re-run). Not the
                # silent-non-write defect, which is caught above by
                # still_dirty_ours, the existence check, and the pending
                # check.
                print("  no file changed: on-disk state already matched "
                      "the")
                print("  applied values (idempotent re-run). Nothing to "
                      "commit.")
                print("")
                print("Lighting applied, read back, and already saved on "
                      "disk.")
                return 0
        for f in changed:
            print("    {0}".format(f))
        ok, detail = _commit_packages(changed, biome)
        if not ok:
            print("FAIL: packages SAVED but the commit did not land: {0}"
                  .format(detail))
            print("  The world and the repo now disagree until this is")
            print("  committed by hand.")
            return 5
        print("  committed: {0}".format(detail))
        print("")
        print("Lighting applied, read back, SAVED and committed.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    # RESOURCE GUARD. Heavy operations log the memory situation before
    # they start and hold a lock so two never drive the same editor at
    # once (scripts/resource_guard.py). Low memory WARNS; a concurrent
    # heavy op REFUSES at exit 8.
    try:
        with resource_guard.HeavyOp('lighting rig application (lighting build)') as _guard_ok:
            if not _guard_ok:
                sys.exit(8)
            sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
