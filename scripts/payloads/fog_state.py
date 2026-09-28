"""Read back the fog coupling state: the cvar and every property Task 1 touches.

Brief 2 Task 1 says to flip `r.SupportSkyAtmosphereAffectsHeightFog=1`. Before
doing that, VERIFY what it already is -- SkyAtmosphereRendering.cpp:98-102
declares it with a DEFAULT OF 1 and the flags ECVF_ReadOnly, so:

  * it is very likely already on, and "flipping" it is a no-op; and
  * ECVF_ReadOnly means it CANNOT be changed at runtime by console or by the
    Python console-command surface. A read-only cvar takes its value from
    config at startup. Setting it from the editor API and reporting success
    would be rule 12's exact failure -- a value declared, not applied, and
    never read back.

`r.SupportExpFogMatchesVolumetricFog`, which the component header warns would
make FogInscatteringLuminance ignored, DOES NOT EXIST in 5.8: it appears only
in three comments in ExponentialHeightFogComponent.h and in no source file.
Read here anyway, so the claim is measured rather than argued.

Property names verified against ExponentialHeightFogComponent.h:
    FogInscatteringLuminance                   :43
    SkyAtmosphereAmbientContributionColorScale :47
    DirectionalInscatteringLuminance           :108
    bEnableVolumetricFog                       :136
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False, "error": None}


def _cvar(name):
    try:
        return _u.SystemLibrary.get_console_variable_float_value(name)
    except Exception as _e:
        return "unreadable: " + str(_e)


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _out["level_path"] = _ues.get_editor_world().get_path_name()

    _out["cvars"] = {
        "r.SupportSkyAtmosphereAffectsHeightFog": _cvar(
            "r.SupportSkyAtmosphereAffectsHeightFog"),
        "r.SupportSkyAtmosphere": _cvar("r.SupportSkyAtmosphere"),
        "r.SupportExpFogMatchesVolumetricFog": _cvar(
            "r.SupportExpFogMatchesVolumetricFog"),
        "_note": ("SupportSkyAtmosphereAffectsHeightFog is ECVF_ReadOnly with "
                  "default 1 (SkyAtmosphereRendering.cpp:98-102). "
                  "SupportExpFogMatchesVolumetricFog appears only in header "
                  "COMMENTS in 5.8 and in no source file, so an unreadable "
                  "result there is the expected answer, not a failure."),
    }

    _comps = []
    for _a in _eas.get_all_level_actors():
        try:
            _c = _a.get_component_by_class(_u.ExponentialHeightFogComponent)
        except Exception:
            _c = None
        if _c:
            _comps.append((_a, _c))
    _out["fog_actors"] = [a.get_actor_label() for a, _ in _comps]
    if len(_comps) != 1:
        raise RuntimeError("expected exactly 1 ExponentialHeightFogComponent, "
                           "found %d" % len(_comps))
    _actor, _fc = _comps[0]

    def _col(v):
        return [round(float(v.r), 6), round(float(v.g), 6),
                round(float(v.b), 6), round(float(v.a), 6)]

    _loc = _actor.get_actor_location()
    _out["fog"] = {
        "actor_label": _actor.get_actor_label(),
        "actor_z_cm": round(float(_loc.z), 3),
        "fog_density": float(_fc.get_editor_property("fog_density")),
        "fog_height_falloff": float(_fc.get_editor_property("fog_height_falloff")),
        "start_distance_cm": float(_fc.get_editor_property("start_distance")),
        "enable_volumetric_fog": bool(_fc.get_editor_property("enable_volumetric_fog")),
        "fog_inscattering_luminance": _col(
            _fc.get_editor_property("fog_inscattering_luminance")),
        "sky_atmosphere_ambient_contribution_color_scale": _col(
            _fc.get_editor_property("sky_atmosphere_ambient_contribution_color_scale")),
        "directional_inscattering_luminance": _col(
            _fc.get_editor_property("directional_inscattering_luminance")),
    }
    # The half-height the ENGINE is actually rendering, derived from the
    # falloff it holds. Base 2: density halves when (F/1000)*dz_cm = 1, so
    # half_height_cm = 1000/F (HeightFogCommon.ush :225/:301/:394).
    _f = _out["fog"]["fog_height_falloff"]
    _out["fog"]["implied_half_height_m"] = (
        round((1000.0 / _f) / 100.0, 2) if _f else None)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out, default=str))
