"""atmosphere_solve.py — OFFLINE solver for the P6 atmosphere pass.

NO UNREAL IMPORT. NO EDITOR. This runs on a laptop with nothing open and
answers the questions the atmosphere recipe has to answer with numbers
instead of adjectives:

  1. What ground illuminance does a given `sun.intensity_lux` actually
     produce, GIVEN that `atmosphere_sun_light` is set?
  2. What exposure compensation puts sunlit terrain at a chosen linear
     scene value?
  3. How much aerial perspective does a ridge 8 km away get, from the
     ground and from 2 km airship altitude?
  4. How much exponential height fog does that same ridge get?
  5. What does a volumetric cloud layer cost, in ray-march samples per
     frame, at this project's screen percentage?

WHY THIS EXISTS. `intensity_lux: 5.0` once produced a fully black frame
including the sky. The lesson recorded was "sanity-check magnitudes
against physical reality" — but nothing in the repo could actually
compute the physical reality, so the check stayed a slogan. This is the
instrument.

THE ONE FINDING THAT DRIVES EVERYTHING ELSE, at a source line:

    Engine/Source/Runtime/Engine/Private/Components/
    DirectionalLightComponent.cpp:602-617

        GetSunIlluminanceAccountingForSkyAtmospherePerPixelTransmittance()
          if (IsUsedAsAtmosphereSunLight())
              if (bPerPixelTransmittanceEnabled)   // NON-default: the multiply moves into the shader
                  return GetOuterSpaceIlluminance()
              else                                 // DEFAULT (per-pixel transmittance off): CPU-side attenuation
                  return GetOuterSpaceIlluminance() * GetAtmosphereTransmittanceTowardSun()

    and DirectionalLightComponent.cpp:581-584

        GetOuterSpaceIlluminance() { return GetColor(); }   // == Intensity * colour

  So when `atmosphere_sun_light` is True — which `apply_lighting.py:330`
  always sets — the light's `intensity` is the TOP-OF-ATMOSPHERE
  illuminance, and (with per-pixel transmittance OFF, the default) the
  engine attenuates it by the atmosphere itself before it touches a
  surface. Feeding it a ground-level number attenuates twice.

  Ground-truth top-of-atmosphere illuminance is the luminous solar
  constant: solar constant 1361 W/m^2 x luminous efficacy of AM0
  sunlight ~93-98 lm/W = 126,000-134,000 lux. This module uses 130,000
  as the locked default.

TRANSMITTANCE IS THE ENGINE'S OWN, NOT A MODEL OF IT. `transmittance()`
below is a line-by-line port of

    Engine/Source/Runtime/Engine/Public/Rendering/
    SkyAtmosphereCommonData.cpp:182-267
    FAtmosphereSetup::GetTransmittanceAtGroundLevel

including its 15-sample loop, its `BottomRadius + 0.5 km` sample origin,
and its `TransmittanceMinLightElevationAngle` clamp. The coefficient
derivation is ported from the same file, lines 78-135
(`FAtmosphereSetup::InternalInit`). A different integrator would be a
different instrument measuring a different thing.

Usage:
    python scripts/atmosphere_solve.py
    python scripts/atmosphere_solve.py --recipe recipes/alpine.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------
# ENGINE DEFAULTS, transcribed with their source lines. Every number
# here was read out of UE 5.8 on this machine, never remembered.
# ---------------------------------------------------------------------
# SkyAtmosphereComponent.cpp:99-138 (USkyAtmosphereComponent ctor)
EARTH_BOTTOM_RADIUS_KM = 6360.0
EARTH_ATMOSPHERE_HEIGHT_KM = 60.0          # 6420 - 6360
RAYLEIGH_SCATTERING_RAW = (0.005802, 0.013558, 0.033100)   # 1/km at 0 km
RAYLEIGH_SCALE_HEIGHT_KM = 8.0
MIE_SCATTERING_SCALE_DEFAULT = 0.003996    # 1/km, coefficient is White
MIE_ABSORPTION_SCALE_DEFAULT = 0.000444    # 1/km, coefficient is White
MIE_SCALE_HEIGHT_KM = 1.2
MIE_ANISOTROPY_DEFAULT = 0.8
OZONE_ABSORPTION_RAW = (0.000650, 0.001881, 0.000085)      # 1/km
OZONE_TENT_TIP_ALTITUDE_KM = 25.0
OZONE_TENT_TIP_VALUE = 1.0
OZONE_TENT_WIDTH_KM = 15.0
TRANSMITTANCE_MIN_LIGHT_ELEVATION_DEG = -90.0

# Scene.cpp:490-607 — post-process manual-exposure camera defaults
CAMERA_FSTOP = 4.0
CAMERA_SHUTTER = 60.0        # the "60" of 1/60 s; used as 1/t
CAMERA_ISO = 100.0
# PostProcessEyeAdaptation.cpp:376-389 with LensAttenuation 0.78 and
# r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True
# (LandscapeLab/Config/DefaultEngine.ini) -> 0.78/0.78 = 1.0
LUMINANCE_MAX = 1.0

# SceneCore.cpp:404-405 — the artist-facing fog numbers are divided by
# 1000 before use.
FOG_DENSITY_DIVISOR = 1000.0
FOG_FALLOFF_DIVISOR = 1000.0

# VolumetricCloudRendering.cpp:67 / VolumetricRenderTarget.cpp:33
CLOUD_VIEW_RAY_SAMPLE_MAX_COUNT = 768.0
CLOUD_VRT_MODE_0_TRACE_DIVISOR = 4        # "trace quarter resolution"


def _srgb_encode(c):
    """Linear -> sRGB (IEC 61966-2-1). Color.h:838 decodes with this."""
    c = max(0.0, min(1.0, float(c)))
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def linear_rgb_to_fcolor(rgb):
    """Linear RGB -> the 0-255 ints an FColor property needs.

    `SkyAtmosphereComponent.GroundAlbedo` and
    `ExponentialHeightFogComponent.VolumetricFogAlbedo` are FColor, and
    FColor -> FLinearColor goes through `sRGBToLinearTable`
    (Core/Public/Math/Color.h:838-844). So the bytes are sRGB-encoded,
    exactly like `set_light_color`. Storing a linear triple straight into
    the bytes lightens it by roughly 1.7x in the midtones.
    """
    return tuple(int(round(_srgb_encode(c) * 255.0)) for c in rgb)


class Atmosphere(object):
    """Port of FAtmosphereSetup (SkyAtmosphereCommonData.cpp:78-135)."""

    def __init__(self, bottom_radius_km=EARTH_BOTTOM_RADIUS_KM,
                 atmosphere_height_km=EARTH_ATMOSPHERE_HEIGHT_KM,
                 rayleigh_scale=None, mie_scattering_scale=None,
                 mie_absorption_scale=None,
                 rayleigh_exp_dist_km=RAYLEIGH_SCALE_HEIGHT_KM,
                 mie_exp_dist_km=MIE_SCALE_HEIGHT_KM,
                 transmittance_min_elev_deg=(
                     TRANSMITTANCE_MIN_LIGHT_ELEVATION_DEG)):
        self.bottom_km = float(bottom_radius_km)
        self.top_km = self.bottom_km + max(0.1, float(atmosphere_height_km))

        # The component stores a NORMALISED colour plus a scale; the
        # product is the physical coefficient. Defaults reproduce
        # RAYLEIGH_SCATTERING_RAW exactly.
        r_scale = (RAYLEIGH_SCATTERING_RAW[2] if rayleigh_scale is None
                   else float(rayleigh_scale))
        norm = [c / RAYLEIGH_SCATTERING_RAW[2]
                for c in RAYLEIGH_SCATTERING_RAW]
        self.rayleigh = [c * r_scale for c in norm]
        self.rayleigh_exp = -1.0 / float(rayleigh_exp_dist_km)

        ms = (MIE_SCATTERING_SCALE_DEFAULT if mie_scattering_scale is None
              else float(mie_scattering_scale))
        ma = (MIE_ABSORPTION_SCALE_DEFAULT if mie_absorption_scale is None
              else float(mie_absorption_scale))
        self.mie_scattering = [ms, ms, ms]     # coefficient colour is White
        self.mie_absorption = [ma, ma, ma]
        self.mie_extinction = [ms + ma] * 3
        self.mie_exp = -1.0 / float(mie_exp_dist_km)

        o_scale = OZONE_ABSORPTION_RAW[1]
        o_norm = [c / o_scale for c in OZONE_ABSORPTION_RAW]
        self.ozone = [c * o_scale for c in o_norm]
        # TentToCoefficients, SkyAtmosphereCommonData.cpp:55-76
        slope = OZONE_TENT_TIP_VALUE / OZONE_TENT_WIDTH_KM
        self.abs_layer_width = OZONE_TENT_TIP_ALTITUDE_KM
        self.abs_lin0 = slope
        self.abs_lin1 = -slope
        self.abs_const0 = (OZONE_TENT_TIP_VALUE
                           - OZONE_TENT_TIP_ALTITUDE_KM * self.abs_lin0)
        self.abs_const1 = (OZONE_TENT_TIP_VALUE
                           - OZONE_TENT_TIP_ALTITUDE_KM * self.abs_lin1)
        self.min_elev_deg = float(transmittance_min_elev_deg)

    def _density(self, height_km):
        d_mie = max(0.0, math.exp(self.mie_exp * height_km))
        d_ray = max(0.0, math.exp(self.rayleigh_exp * height_km))
        if height_km < self.abs_layer_width:
            d_ozo = self.abs_lin0 * height_km + self.abs_const0
        else:
            d_ozo = self.abs_lin1 * height_km + self.abs_const1
        d_ozo = max(0.0, min(1.0, d_ozo))
        return d_mie, d_ray, d_ozo

    def extinction_per_km(self, height_km):
        """RGB extinction coefficient (1/km) at an altitude above ground."""
        d_mie, d_ray, d_ozo = self._density(height_km)
        return [d_mie * self.mie_extinction[i]
                + d_ray * self.rayleigh[i]
                + d_ozo * self.ozone[i] for i in range(3)]

    def scattering_per_km(self, height_km):
        """RGB SCATTERING coefficient (1/km) — what makes haze visible."""
        d_mie, d_ray, _ = self._density(height_km)
        return [d_mie * self.mie_scattering[i] + d_ray * self.rayleigh[i]
                for i in range(3)]

    def _ray_sphere_nearest(self, origin, direction, radius):
        ox, oy, oz = origin
        dx, dy, dz = direction
        a = dx * dx + dy * dy + dz * dz
        b = 2.0 * (dx * ox + dy * oy + dz * oz)
        c = ox * ox + oy * oy + oz * oz - radius * radius
        disc = b * b - 4.0 * a * c
        if disc < 0.0:
            return -1.0
        s = math.sqrt(disc)
        s0 = (-b - s) / (2.0 * a)
        s1 = (-b + s) / (2.0 * a)
        if s0 < 0.0 and s1 < 0.0:
            return -1.0
        if s0 < 0.0:
            return max(0.0, s1)
        if s1 < 0.0:
            return max(0.0, s0)
        return max(0.0, min(s0, s1))

    def transmittance_at_ground_level(self, sun_elevation_deg):
        """Port of GetTransmittanceAtGroundLevel, 15 samples and all.

        Returns linear RGB in [0,1]. This is the factor the engine
        multiplies `intensity_lux` by before the sun lights anything —
        DirectionalLightComponent.cpp:601-615.
        """
        elev = math.radians(max(self.min_elev_deg, float(sun_elevation_deg)))
        origin = (0.0, 0.0, self.bottom_km + 0.5)
        direction = (math.cos(elev), 0.0, math.sin(elev))
        t_max = self._ray_sphere_nearest(origin, direction, self.top_km)
        depth = [0.0, 0.0, 0.0]
        if t_max > 0.0:
            n = 15.0
            step = 1.0 / n
            seg = step * t_max
            t = 0.0
            while t < 1.0:
                pos = tuple(origin[i] + direction[i] * (t_max * t)
                            for i in range(3))
                r = math.sqrt(sum(p * p for p in pos))
                h = r - self.bottom_km
                ext = self.extinction_per_km(h)
                for i in range(3):
                    depth[i] += seg * ext[i]
                t += step
        return [math.exp(-d) for d in depth]


# ---------------------------------------------------------------------
# Exposure — PostProcessEyeAdaptation.cpp:520-531, 652-656
# ---------------------------------------------------------------------
def manual_white_point_luminance(fstop=CAMERA_FSTOP, shutter=CAMERA_SHUTTER,
                                 iso=CAMERA_ISO,
                                 luminance_max=LUMINANCE_MAX):
    """cd/m^2 that maps to 1.0 under AEM_MANUAL, before compensation."""
    ev100 = math.log(fstop * fstop * shutter * 100.0 / max(1.0, iso), 2.0)
    return luminance_max * (2.0 ** ev100), ev100


def lambert_luminance(albedo, illuminance_normal_lux, incidence_deg):
    """cd/m^2 off a Lambertian surface. L = rho * E * cos(theta) / pi."""
    return (albedo * illuminance_normal_lux
            * math.cos(math.radians(incidence_deg)) / math.pi)


def required_exposure_bias(scene_luminance, target_linear,
                           white_point_luminance):
    """AutoExposureBias in EV that puts `scene_luminance` at `target`."""
    return math.log(target_linear * white_point_luminance
                    / max(scene_luminance, 1e-9), 2.0)


# ---------------------------------------------------------------------
# Exponential height fog — SceneCore.cpp:400-406
# ---------------------------------------------------------------------
def fog_falloff_from_half_height(half_height_m):
    """The raw FogHeightFalloff for a given metric half-height.

    BASE 2, NOT BASE e. Corrected 2026-09-09; the previous form carried a
    ln(2) and returned a falloff 0.693x too small, i.e. a half-height
    1/ln2 = 1.4427x too large.

    HeightFogCommon.ush:206 COMMENTS the density function as
    `d = GlobalDensity * exp(-HeightFalloff * z)`; the CODE is base 2 in
    three places -- :225 `pow(2.0f, -F*(z-z0))`, :301 `exp2(-Exponent)`,
    :394 `exp2(-LineIntegral)`. So density halves when (F/1000)*dz_cm = 1
    exactly, giving F = 1000 / half_height_cm with no ln(2).

    Engine divides it by 1000 (SceneCore.cpp:405), which is the /1000 here.
    """
    return 1000.0 / (float(half_height_m) * 100.0)


def fog_opacity(density, half_height_m, datum_m, camera_height_m,
                distance_m, start_distance_m):
    """Fog opacity 0-1 for a HORIZONTAL ray at a constant altitude.

    A horizontal ray keeps its height, so the height term is a constant
    and the integral collapses to density(h) * path length. Slanted rays
    get more fog than this; treat it as the optimistic bound.
    """
    # BASE 2 THROUGHOUT, matching the shader. Corrected 2026-09-09: both
    # exponentials here were math.exp(). The height term was at least
    # self-consistent with the old base-e falloff, so half-heights came out
    # right in this function's own model; the TRANSMITTANCE term was wrong
    # against the engine either way, by a factor of ln(2) in the exponent.
    #   :225 pow(2.0f, ...)   :301 exp2(...)   :394 exp2(-LineIntegral)
    d0 = float(density) / FOG_DENSITY_DIVISOR                    # per cm
    f = fog_falloff_from_half_height(half_height_m) / FOG_FALLOFF_DIVISOR
    dh_cm = (float(camera_height_m) - float(datum_m)) * 100.0
    local = d0 * 2.0 ** (-f * dh_cm)
    path_cm = max(0.0, float(distance_m) - float(start_distance_m)) * 100.0
    return 1.0 - 2.0 ** (-local * path_cm)


# ---------------------------------------------------------------------
# Aerial perspective — the physical part of SkyAtmosphere's contribution
# ---------------------------------------------------------------------
def aerial_optical_depth(atmo, altitude_m, distance_m, view_scale=1.0):
    """RGB optical depth along a horizontal ray at a fixed altitude.

    `view_scale` is the component's `AerialPespectiveViewDistanceScale`,
    documented as "scaling distances from view to surfaces", so it
    multiplies the path length and nothing else.
    """
    h_km = float(altitude_m) / 1000.0
    d_km = float(distance_m) / 1000.0 * float(view_scale)
    ext = atmo.extinction_per_km(h_km)
    return [e * d_km for e in ext]


def aerial_haze_fraction(atmo, altitude_m, distance_m, view_scale=1.0):
    """1 - transmittance per channel: how much of a distant ridge is haze."""
    depth = aerial_optical_depth(atmo, altitude_m, distance_m, view_scale)
    return [1.0 - math.exp(-d) for d in depth]


# ---------------------------------------------------------------------
# Volumetric cloud cost
# ---------------------------------------------------------------------
def cloud_trace_budget(width, height, screen_percentage,
                       vrt_mode_divisor=CLOUD_VRT_MODE_0_TRACE_DIVISOR,
                       ray_sample_max=CLOUD_VIEW_RAY_SAMPLE_MAX_COUNT):
    """Worst-case primary-ray volume samples per frame.

    r.VolumetricRenderTarget=1 with Mode 0 traces at quarter resolution
    (VolumetricRenderTarget.cpp:33), and each traced pixel marches up to
    r.VolumetricCloud.ViewRaySampleMaxCount samples
    (VolumetricCloudRendering.cpp:67). This is the ceiling, not the mean:
    the actual count scales with traced distance and stops early at
    r.VolumetricCloud.StopTracingTransmittanceThreshold.
    """
    w = width * screen_percentage / 100.0
    h = height * screen_percentage / 100.0
    traced = (w / math.sqrt(vrt_mode_divisor)) * (h / math.sqrt(
        vrt_mode_divisor))
    return traced, traced * ray_sample_max


def _fmt3(v):
    return "[{0:.4f}, {1:.4f}, {2:.4f}]".format(*v)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe",
                   default=os.path.join(REPO_ROOT, "recipes", "alpine.json"))
    p.add_argument("--outer-space-lux", type=float, default=130000.0,
                   help="Top-of-atmosphere illuminance. 126000-134000 is "
                        "the physical range; 130000 is locked.")
    p.add_argument("--target-linear", type=float, default=0.32,
                   help="Linear scene value wanted for SUNLIT terrain of "
                        "the measured albedo, before tonemapping.")
    p.add_argument("--mie-scale", type=float, default=None,
                   help="Override MieScatteringScale (1/km).")
    p.add_argument("--view-scale", type=float, default=1.0,
                   help="AerialPespectiveViewDistanceScale to evaluate.")
    p.add_argument("--albedo", type=float, default=0.2675,
                   help="Linear green-channel ground albedo. The measured "
                        "area-weighted value for alpine is 0.2675.")
    args = p.parse_args(argv)

    with open(args.recipe, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)
    lit = recipe["lighting"]
    elev = float(lit["sun"]["elevation_deg"])

    atmo = Atmosphere(mie_scattering_scale=args.mie_scale)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("recipe    : {0}".format(args.recipe))
    print("")
    print("=== 1. SUN: what the engine actually delivers =================")
    t = atmo.transmittance_at_ground_level(elev)
    print("  sun elevation                 {0:.1f} deg".format(elev))
    print("  MieScatteringScale            {0:.6f} 1/km".format(
        atmo.mie_scattering[0]))
    print("  transmittance toward sun RGB  {0}".format(_fmt3(t)))
    print("    (DirectionalLightComponent.cpp:601-615 multiplies")
    print("     intensity by this when atmosphere_sun_light is True)")
    print("")
    recipe_lux = float(lit["sun"]["intensity_lux"])
    for lux, tag in ((recipe_lux, "recipe as written"),
                     (args.outer_space_lux, "top-of-atmosphere")):
        ground = [lux * c for c in t]
        print("  intensity_lux {0:>9.0f}  ({1})".format(lux, tag))
        print("      -> ground illuminance normal to sun  "
              "{0:.0f} / {1:.0f} / {2:.0f} lux (RGB)".format(*ground))
        print("      -> horizontal-surface illuminance    "
              "{0:.0f} lux (green)".format(
                  ground[1] * math.sin(math.radians(elev))))
    print("")
    print("  physical reference: clear-sky DIRECT-NORMAL illuminance at")
    print("  {0:.0f} deg solar elevation is ~49,000-60,000 lux at sea".format(
        elev))
    print("  level. Anything an order of magnitude away is wrong.")

    print("")
    print("=== 2. EXPOSURE ==============================================")
    wp, ev100 = manual_white_point_luminance()
    print("  manual EV100 (f/{0:.0f}, 1/{1:.0f}s, ISO {2:.0f})   "
          "{3:.4f}".format(CAMERA_FSTOP, CAMERA_SHUTTER, CAMERA_ISO, ev100))
    print("  white-point luminance                {0:.1f} cd/m2".format(wp))
    for lux, tag in ((recipe_lux, "recipe as written"),
                     (args.outer_space_lux, "top-of-atmosphere")):
        ground_g = lux * t[1]
        lum = lambert_luminance(args.albedo, ground_g, 90.0 - elev)
        bias = required_exposure_bias(lum, args.target_linear, wp)
        print("  intensity {0:>9.0f} ({1})".format(lux, tag))
        print("      sunlit terrain luminance   {0:.2f} cd/m2".format(lum))
        print("      linear value at bias {0:+.2f}   {1:.4f}".format(
            float(lit["exposure"]["compensation_ev"]),
            lum * (2.0 ** float(lit["exposure"]["compensation_ev"])) / wp))
        print("      bias needed for {0:.2f}       {1:+.3f} EV".format(
            args.target_linear, bias))

    print("")
    print("=== 3. AERIAL PERSPECTIVE ====================================")
    print("  ridge distance   altitude   view_scale   haze fraction RGB")
    for alt in (400.0, 1200.0, 2000.0):
        for dist in (2000.0, 4000.0, 8000.0):
            for vs in (1.0, args.view_scale):
                hz = aerial_haze_fraction(atmo, alt, dist, vs)
                print("  {0:>8.0f} m    {1:>6.0f} m      {2:>4.1f}      "
                      "{3}".format(dist, alt, vs, _fmt3(hz)))
        print("")

    print("=== 4. EXPONENTIAL HEIGHT FOG ================================")
    fog = lit["fog"]
    print("  density {0}  half_height {1} m  datum {2} m  start {3} m"
          .format(fog["density"], fog["half_height_m"],
                  fog["height_datum_m"], fog["start_distance_m"]))
    print("  raw fog_height_falloff = {0:.6f}".format(
        fog_falloff_from_half_height(fog["half_height_m"])))
    print("  camera height   ridge distance   fog opacity")
    for cam in (300.0, 800.0, 1200.0, 2000.0):
        for dist in (2000.0, 4000.0, 8000.0):
            print("  {0:>8.0f} m       {1:>8.0f} m     {2:.4f}".format(
                cam, dist,
                fog_opacity(fog["density"], fog["half_height_m"],
                            fog["height_datum_m"], cam, dist,
                            fog["start_distance_m"])))
    print("")

    print("=== 5. VOLUMETRIC CLOUD COST =================================")
    res = recipe["capture"]["resolution"]
    for sp in (100.0, 70.0):
        traced, samples = cloud_trace_budget(res[0], res[1], sp)
        print("  {0}x{1} at r.ScreenPercentage {2:.0f}".format(
            res[0], res[1], sp))
        print("      traced pixels/frame   {0:,.0f}".format(traced))
        print("      worst-case samples    {0:,.0f}".format(samples))
    print("")
    print("  Each sample reads the cloud material: 2 volume textures plus")
    print("  a weather texture. This is a CEILING, not a measurement of")
    print("  this GPU — no frame time here is measured. COULD NOT MEASURE")
    print("  frame cost offline; it needs `stat gpu` in the editor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
